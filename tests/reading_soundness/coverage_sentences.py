#!/usr/bin/env python3
"""tools/read_coverage.py と同じ条件(同じ文書の取り方・同じ supported の定義)で、supported 文ごとの内訳を JSONL に書く。

使い方: cd <木> && VERA_LEADS=<jsonl> PYTHONPATH=<木> python <このファイル> --n 1500 --stride 200 --out sentences.jsonl [--all-clauses all.jsonl]
supported 文の定義は read_coverage.py と同じ: (c.span.source, c.span.start) が、unsupported でない節を 1 つ以上持つ文。
出力の行数が read_coverage.py の supported_sentences と一致することを、--expect で渡された JSON と照合する(不一致なら終了コード 1)。
"""
import argparse, json, os, sys
sys.path.insert(0, '.'); sys.path.insert(0, 'tools')
import round5a_route_tune as T
if os.environ.get('VERA_LEADS'): T.PATH = os.environ['VERA_LEADS']
from verantyx.semantic_reader import document_view


def clause_row(c):
    return {'rule': c.rule, 'predicate': c.predicate, 'polarity': c.polarity,
            'roles': [[r.name, r.span.text] for r in c.roles], 'unsupported': list(c.unsupported)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=1500); ap.add_argument('--stride', type=int, default=200)
    ap.add_argument('--out', required=True); ap.add_argument('--all-clauses'); ap.add_argument('--expect')
    a = ap.parse_args()
    docs = T.load(a.n, a.stride); view = document_view(docs)
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign:
        print('ISOLATION FAILED', foreign, file=sys.stderr); sys.exit(2)
    by_key = {}
    for c in view.clauses:
        by_key.setdefault((c.span.source, c.span.start), []).append(c)
    supported = {k for k, cs in by_key.items() if any(not c.unsupported for c in cs)}
    with open(a.out, 'w', encoding='utf-8') as f:
        for k in sorted(supported):
            cs = by_key[k]
            f.write(json.dumps({'key': list(k), 'text': cs[0].span.text,
                                'clauses': [clause_row(c) for c in cs]}, ensure_ascii=False) + '\n')
    if a.all_clauses:
        with open(a.all_clauses, 'w', encoding='utf-8') as f:
            for k in sorted(by_key):
                cs = by_key[k]
                f.write(json.dumps({'key': list(k), 'text': cs[0].span.text, 'supported': k in supported,
                                    'clauses': [clause_row(c) for c in cs]}, ensure_ascii=False) + '\n')
    print(f'tree={root}\ndocuments={len(docs)} supported_sentences={len(supported)}')
    if a.expect:
        want = json.load(open(a.expect))['supported_sentences']
        if want != len(supported):
            print(f'MISMATCH with {a.expect}: {want} != {len(supported)}', file=sys.stderr); sys.exit(1)
        print(f'matches {a.expect}: {want}')


if __name__ == '__main__':
    main()
