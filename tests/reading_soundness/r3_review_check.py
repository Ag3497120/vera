#!/usr/bin/env python3
"""W1-a2 X2: 第 3 ラウンドのレビュー(review.r3.md)の反例と docs K14・K15 の文が、対応済み(supported)の節で誤読されないことの回帰確認。

評価バンクではない(凍結の対象ではない)。review.r3.md の N1(13 文)・N2(5 文)・N3(1 文)・N4(2 文)・docs K14・K15(4 文)と、QA の 6 行。
各文に「supported 節に出てはいけない (役割, 値)」と「supported の copula/否定の名詞文を禁じる」を持たせ、違反があれば終了コード 1。
QA は Vera.from_texts({'d': 文}, mode='semantic').ask(問) が ANSWER を返したら違反。隔離検査: 読み込んだ verantyx* が PYTHONPATH の木の配下か(外れたら 2)。
使い方: PYTHONPATH=<木> python tests/reading_soundness/r3_review_check.py
"""
import os
import sys

# (文, 禁じる (役割, 値) の一覧, supported の名詞文(rule が copula / negation)を禁じるか)
PASSIVE_WORD_AGENT = [  # N1: 受身の に 句の語は動作主ではない
    ('土手に桜の木が植えられた。', '土手'), ('芝生に水がまかれた。', '芝生'), ('裏手に倉庫が建てられた。', '裏手'), ('分母に数字が書き込まれた。', '分母'),
    ('体長に目盛りが記された。', '体長'), ('器官に異常が見つけられた。', '器官'), ('酵母に糖が加えられた。', '酵母'), ('空母に戦闘機が積まれた。', '空母'),
    ('川の土手に看板が立てられた。', '川の土手'), ('民家に火が放たれた。', '民家'), ('空き家に看板が掛けられた。', '空き家'),
    ('隠れ家に宝が隠された。', '隠れ家'), ('古い民家に新しい屋根が付けられた。', '古い民家'),
    # docs K14
    ('全長に印が付けられた。', '全長'), ('身長に印が付けられた。', '身長'), ('個人に責任が負わされた。', '個人'),
]
PERSON_RESULT = [  # N2: 語彙に無い人が目的語の後ろにあっても result ではない
    ('母が着物を園児に仕立てた。', '園児'), ('先生が作文を児童に直した。', '児童'), ('母が浴衣を末っ子に仕立てた。', '末っ子'),
    ('係長が資料を新入りに整理した。', '新入り'), ('美容師が髪を花嫁に染めた。', '花嫁'),
]
AMBIGUOUS_SELECTION = [  # N3 / K15: 「…によって選ばれた」と「…として選ばれた」に割れる。どちらの役割でも supported にしてはいけない
    ('町内会に新しい会長が選ばれた。', '町内会'), ('自治会に新しい役員が選ばれた。', '自治会'),
]
DEGREE_COMPARISON = ['この町は昔ほど賑やかではない。', 'この村は都会ほど便利ではない。']
QA = [('土手に桜の木が植えられた。', '誰が桜の木を植えた？'), ('芝生に水がまかれた。', '誰が水をまいた？'), ('裏手に倉庫が建てられた。', '誰が倉庫を建てた？'),
      ('空母に戦闘機が積まれた。', '誰が戦闘機を積んだ？'), ('分母に数字が書き込まれた。', '誰が数字を書き込んだ？'), ('器官に異常が見つけられた。', '誰が異常を見つけた？')]


def main():
    from verantyx.semantic_reader import document_view
    from verantyx.one import Vera
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    print('tree=' + root)
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    violations = 0

    def supported(text):
        return [c for c in document_view({'d': text}).clauses if not c.unsupported]

    def report(kind, text, hits):
        nonlocal violations
        violations += bool(hits)
        print(f"{'VIOLATION' if hits else 'ok       '} {kind:5} {text} {hits if hits else ''}")

    for text, word in PASSIVE_WORD_AGENT:
        report('N1', text, [(c.predicate, r.name, r.span.text) for c in supported(text) for r in c.roles if r.name == 'agent' and word in r.span.text])
    for text, word in PERSON_RESULT:
        report('N2', text, [(c.predicate, r.name, r.span.text) for c in supported(text) for r in c.roles if r.name == 'result' and r.span.text == word])
    for text, word in AMBIGUOUS_SELECTION:
        report('N3', text, [(c.predicate, r.name, r.span.text) for c in supported(text) for r in c.roles
                            if r.name in ('agent', 'result') and r.span.text == word])
    for text in DEGREE_COMPARISON:
        report('N4', text, [(c.rule, c.predicate) for c in supported(text) if c.rule in ('copula', 'negation')])
    for text, question in QA:
        answer = Vera.from_texts({'d': text}, mode='semantic').ask(question)
        verdict = str(answer.get('verdict')); values = [str(v) for v in (answer.get('values') or [])]
        bad = verdict.startswith('ANSWER') or bool(values)
        violations += bad
        print(f"{'VIOLATION' if bad else 'ok       '} QA    {text} / {question} -> {verdict} {values}")
    n = len(PASSIVE_WORD_AGENT) + len(PERSON_RESULT) + len(AMBIGUOUS_SELECTION) + len(DEGREE_COMPARISON) + len(QA)
    print(f'checks={n} violations={violations}')
    sys.exit(1 if violations else 0)


if __name__ == '__main__':
    main()
