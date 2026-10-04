#!/usr/bin/env python3
"""W1-a3: 中間職のレビュー(review.r3.md §1.1・§2)が挙げた入口の反例の回帰確認(必須 1)。

評価バンクではない(凍結の対象ではない)。入口(verantyx.semantic_read)の文だけを持つ。読解器は W1-a3 で変えていないので読解器の部分は無い。
入口が無い木(基点 dev)では「入口なし」と表示して終了コード 0。
 - ENTRY_NOT_PASSIVE: 尊敬の型(人の語彙に無い主語・に 句の動詞が類に無い型)と、授受・委任の受身。入口が `readable: false` か、`voice: passive` と
   patient=主語 を出さないこと(違反は終了コード 1)。
 - ENTRY_KEPT: 受身のまま返るべき文(動作主の句の動詞が閉じた類 _NI_KARA_FREE_PREDICATES)。
 - ENTRY_KNOWN_MISREAD: 経路・起点の を の主語(必須 2 (b)。入口がまだ誤って読む。直さない。docs K40)。結果を表示するだけで違反に数えない。
 - ENTRY_WAS_PASSIVE: 第 3 ラウンドでは passive だった文(review.r3 §1.1 が「正しく passive」とした文)。いまは棄権になる(方針 1 で許される)。表示だけ。
隔離検査: 読み込んだ verantyx* が PYTHONPATH の木の配下か(外れたら 2)。
使い方: PYTHONPATH=<木> python tests/reading_soundness/w1a3_review_r3_check.py
"""
import os
import sys

ENTRY_NOT_PASSIVE = [
    # 人の語彙に無い主語・動作主の句なし
    '陛下が視察された。', '恩師が執筆された。', '皇后が訪問された。', '大臣が視察された。', '博士が研究された。', '総理が謝罪された。',
    # 人の語彙に無い主語・に 句あり
    '陛下が子供に話しかけられた。', '大臣が国民に謝罪された。',
    # 人の語彙にある主語・動詞が類に無い他動詞
    '先生が生徒に謝罪された。', '校長が生徒に注意された。',
    # 物の主語の授受・委任の受身(に 句の agent/recipient は同点)
    '賞状が優勝者に手渡された。', '設計が建築家に任された。',
]
ENTRY_KEPT = [('子どもが先生に叱られた。', '叱る', '先生', '子ども'), ('少年は犬に追いかけられた。', '追いかける', '犬', '少年')]
ENTRY_KNOWN_MISREAD = ['子供たちが公園を回った。', '車がトンネルを抜けた。', '行列が大通りを練り歩いた。', '船が港を出航した。']
ENTRY_WAS_PASSIVE = ['窓が少年に割られた。', '財布が泥棒に盗まれた。', '書類が提出された。']


def main():
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    try:
        from verantyx import semantic_read as SR
    except ImportError:
        SR = None
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    print('tree=' + root + ' entry=' + ('yes' if SR else 'no (nothing to check)'))
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    if not SR:
        print('checks=0 violations=0'); sys.exit(0)
    violations = 0; checks = 0

    def say(bad, kind, text, extra=''):
        nonlocal violations, checks
        checks += 1; violations += bool(bad)
        print(f"{'VIOLATION' if bad else 'ok       '} {kind:9} {text} {extra}")

    for text in ENTRY_NOT_PASSIVE:
        subject = text.split('が')[0]
        out = SR.read(text)
        bad = out['readable'] and any(c.get('voice') == 'passive' and c['roles'].get('patient') == subject for c in out['clauses'])
        say(bad, 'entry', text, out['clauses'] if out['readable'] else out['abstain']['reasons'])
    for text, predicate, agent, patient in ENTRY_KEPT:
        out = SR.read(text)
        ok = out['readable'] and out['clauses'][0]['predicate'] == predicate and out['clauses'][0]['voice'] == 'passive' \
            and out['clauses'][0]['roles'] == {'patient': patient, 'agent': agent}
        say(not ok, 'entry-ok', text, '' if ok else out)
    for text in ENTRY_KNOWN_MISREAD:
        out = SR.read(text)
        print(f"known     misread   {text} {out['clauses'] if out['readable'] else out['abstain']['reasons']}")
    for text in ENTRY_WAS_PASSIVE:
        out = SR.read(text)
        print(f"info      was-pass  {text} {out['clauses'] if out['readable'] else out['abstain']['reasons']}")
    print(f'checks={checks} violations={violations}')
    sys.exit(1 if violations else 0)


if __name__ == '__main__':
    main()
