#!/usr/bin/env python3
"""W1-a2 第 2 ラウンド X2: 中間職のレビュー(review.r1.md)が挙げた反例(M1〜M8)が、対応済みの誤読にならないことの回帰確認。

評価バンクではない(凍結の対象ではない)。読解(document_view)の部分は基点 dev でも動く(dev で流すと違反が出る = 検査が効いている証拠)。
入口(verantyx.semantic_read)の部分は入口がある木でだけ流す(dev には無いので飛ばす)。
各文に「supported 節に出てはいけない (役割, 値)」(読解)、「出力に出てはいけない述語・役割・readable・abstain の型」(入口)を持たせ、違反があれば終了コード 1。
隔離検査: 読み込んだ verantyx* が PYTHONPATH の木の配下か(外れたら 2)。
使い方: PYTHONPATH=<木> python tests/reading_soundness/w1a2_review_r1_check.py
"""
import os
import sys

# ---- 読解: (文, 禁じる (役割, 値)) ----
READER_FORBIDDEN = [
    # M1 カタカナ語(frames._LEARNED)は人ではない
    ('ピアノに細かい傷が付けられた。', [('agent', 'ピアノ')]),
    # M2 変換の動詞の に 句は、結果の型の証拠が無ければ result ではない(基点は recipient)
    ('先生が説明を新米に言い換えた。', [('result', '新米')]), ('父が話を末っ子に言い換えた。', [('result', '末っ子')]), ('母が名前を園児に変えた。', [('result', '園児')]),
    # M3 受身の から 句は、証拠なしに source ではない
    ('結果が事務局から通知された。', [('source', '事務局')]), ('2004年10月6日にキングレコードから発売された。', [('source', 'キングレコード')]),
    # M5 証拠の無い終点を goal / direction / recipient にしない
    ('姉は買い物に行った。', [('goal', '買い物'), ('direction', '買い物'), ('recipient', '買い物')]),
    ('彼は買い物に行った。', [('goal', '買い物'), ('direction', '買い物'), ('recipient', '買い物')]),
    ('支部に資料が送られた。', [('goal', '支部'), ('direction', '支部'), ('recipient', '支部'), ('agent', '支部')]),
    ('戦後は若者が都会へ移った。', [('goal', '都会'), ('direction', '都会'), ('recipient', '都会')]),
]
# 読解: 読めたままであるべき文 (文, 必ず supported 節にある (役割, 値))
READER_KEPT = [('マキは研究室へ行った。', ('recipient', '研究室')), ('妹が学校へ行った。', ('recipient', '学校')), ('叔父が弟に時計をくれた。', ('recipient', '弟'))]

# ---- 入口: 述語・役割を禁じる / readable false を要求する ----
ENTRY_UNREADABLE_OR_NOT_THESE = [
    # (文, 禁じる述語, 禁じる (役割, 値))
    ('兄は弟から本を借りた。', ['貸す'], []), ('兄は弟に本をもらった。', ['あげる'], []), ('兄は姉から手紙を受け取った。', ['渡す'], []),
    ('弟は先生に英語を教わった。', ['教える'], []),                                            # M7
    ('兄は東京に住んでいる。', [], [('goal', '東京')]),                                         # M6
    ('結果が事務局から通知された。', [], [('source', '事務局')]),                                # M3
    ('先生が説明を新米に言い換えた。', [], [('result', '新米')]),                                # M2
    ('ピアノに細かい傷が付けられた。', [], [('agent', 'ピアノ')]),                              # M1
    ('姉は買い物に行った。', [], [('goal', '買い物')]),                                         # M5
]
ENTRY_UNREADABLE = ['Rain stopped.', 'Snow fell.', 'Prices dropped.']                          # M4: 文頭の大文字は固有名の証拠ではない
ENTRY_KEPT = [('Ann opened the door.', 'open'), ('叔父が弟に時計をくれた。', 'くれる'), ('妹が学校へ行った。', '行く')]
ENTRY_NOT_UNREADABLE_INPUT = ['Ann received a letter from Ben.']                                # M8: not_supported であって unreadable_input ではない


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
        print(f"{'VIOLATION' if bad else 'ok       '} {kind:7} {text} {extra}")

    def supported(text):
        return [c for c in document_view({'d': text}).clauses if not c.unsupported]

    for text, forbidden in READER_FORBIDDEN:
        hits = [(c.predicate, r.name, r.span.text) for c in supported(text) for r in c.roles if (r.name, r.span.text) in forbidden]
        say(hits, 'reader', text, hits or '')
    for text, pair in READER_KEPT:
        have = any((r.name, r.span.text) == pair for c in supported(text) for r in c.roles)
        say(not have, 'kept', text, '' if have else f'{pair} is gone')
    if SR:
        for text, predicates, roles in ENTRY_UNREADABLE_OR_NOT_THESE:
            out = SR.read(text)
            hits = [(c['predicate'], k, v) for c in out['clauses'] for k, v in c['roles'].items() if (k, v) in roles]
            hits += [(c['predicate'],) for c in out['clauses'] if c['predicate'] in predicates]
            say(hits, 'entry', text, hits or ('unread: ' + str(out['abstain']['reasons']) if not out['readable'] else 'read'))
        for text in ENTRY_UNREADABLE:
            out = SR.read(text)
            say(out['readable'], 'entry', text, out['clauses'] if out['readable'] else '')
        for text, predicate in ENTRY_KEPT:
            out = SR.read(text)
            ok = out['readable'] and out['clauses'][0]['predicate'] == predicate
            say(not ok, 'entry-ok', text, '' if ok else out)
        for text in ENTRY_NOT_UNREADABLE_INPUT:
            out = SR.read(text)
            kind = (out['abstain'] or {}).get('kind')
            say(kind == 'unreadable_input', 'entry', text, kind)
    print(f'checks={checks} violations={violations}')
    sys.exit(1 if violations else 0)


if __name__ == '__main__':
    main()
