#!/usr/bin/env python3
"""W1-a2 第 3 ラウンド X2: 中間職のレビュー(review.r2.md)が挙げた反例(必須 1〜4)が、対応済みの誤読にならないことの回帰確認。

評価バンクではない(凍結の対象ではない)。読解(document_view)の部分は基点 dev でも動く(dev で流すと違反が出る = 検査が効いている証拠。ただし
dev は必須 1 の文を recipient と読む=違反に数えない)。入口(verantyx.semantic_read)の部分は入口がある木でだけ流す(dev には無いので飛ばす)。
各文に「supported 節に出てはいけない (役割, 値)」(読解)、「readable: false を要求する / 出力に出てはいけない (役割, 値)」(入口)を持たせ、違反があれば
終了コード 1。隔離検査: 読み込んだ verantyx* が PYTHONPATH の木の配下か(外れたら 2)。
使い方: PYTHONPATH=<木> python tests/reading_soundness/w1a2_review_r2_check.py
"""
import os
import sys

# ---- 読解: (文, 禁じる (役割, 値)) ----
READER_FORBIDDEN = [
    # 必須 1: 他動詞の目的語が省略された文の に 句(人)は result ではない
    ('先生が素人に言い換えた。', [('result', '素人')]), ('姉が甥に訳した。', [('result', '甥')]), ('社長が新顔に変えた。', [('result', '新顔')]),
    ('係員が留学生に翻訳した。', [('result', '留学生')]), ('講師が受講者に言い換えた。', [('result', '受講者')]),
    # 必須 4: 姓+家 は受身の動作主ではない
    ('絵が田中家に飾られた。', [('agent', '田中家')]), ('看板が鈴木家に掲げられた。', [('agent', '鈴木家')]),
]
# 読解: 読めたままであるべき文 (文, 必ず supported 節にある (役割, 値))
READER_KEPT = [('彼は医者になった。', ('result', '医者')), ('信号が赤に変わった。', ('result', '赤')), ('専門家に意見が求められた。', ('agent', '専門家'))]

# ---- 入口 ----
ENTRY_UNREADABLE = [      # 必須 2: 人が主語の れる/られる は受身と尊敬に割れる。必須 1 / 4 / 3 の文も、読めない(棄権)が正しい
    '先生が説明された。', '先生が話された。', '先生が発表された。', '先生が書かれた。', '先生が教えられた。',
    '先生が生徒に説明された。', '社長が社員に話された。', '部長が部下に伝えられた。', '校長が保護者に挨拶された。',
    '先生が素人に言い換えた。', '姉が甥に訳した。', '社長が新顔に変えた。', '係員が留学生に翻訳した。', '講師が受講者に言い換えた。',
    '絵が田中家に飾られた。', '看板が鈴木家に掲げられた。',
    '窓が割られた。',      # W1-a3 (H63): moved from ENTRY_KEPT: a thing without evidence of a thing may be a person owed respect (review.r3 必須 1)
    'Ann sent the package to London.', 'Kate mailed the letter to Tokyo.', 'The letter was sent to Paris.', 'Ann showed the photo to Rome.',
]
ENTRY_KEPT = [('少年は犬に追いかけられた。', '追いかける'), ('Lisa sent Paul a message.', 'send'), ('Ann opened the door.', 'open'),
              ('彼は医者になった。', 'なる')]


def main():
    from verantyx.semantic_reader import document_view
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    try:
        from verantyx import semantic_read as SR
    except ImportError:
        SR = None
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    print('tree=' + root + ' entry=' + ('yes' if SR else 'no (reader part only)'))
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    violations = 0; checks = 0

    def say(bad, kind, text, extra=''):
        nonlocal violations, checks
        checks += 1; violations += bool(bad)
        print(f"{'VIOLATION' if bad else 'ok       '} {kind:8} {text} {extra}")

    def supported(text):
        return [c for c in document_view({'d': text}).clauses if not c.unsupported]

    for text, forbidden in READER_FORBIDDEN:
        hits = [(c.predicate, r.name, r.span.text) for c in supported(text) for r in c.roles if (r.name, r.span.text) in forbidden]
        say(hits, 'reader', text, hits or '')
    for text, pair in READER_KEPT:
        have = any((r.name, r.span.text) == pair for c in supported(text) for r in c.roles)
        say(not have, 'kept', text, '' if have else f'{pair} is gone')
    if SR:
        for text in ENTRY_UNREADABLE:
            out = SR.read(text)
            say(out['readable'], 'entry', text, out['clauses'] if out['readable'] else out['abstain']['reasons'])
        for text, predicate in ENTRY_KEPT:
            out = SR.read(text)
            ok = out['readable'] and out['clauses'][0]['predicate'] == predicate
            say(not ok, 'entry-ok', text, '' if ok else out)
    print(f'checks={checks} violations={violations}')
    sys.exit(1 if violations else 0)


if __name__ == '__main__':
    main()
