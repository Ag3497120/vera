#!/usr/bin/env python3
"""W3-c7: compares the entry outputs BEFORE and AFTER the stage (line by line, byte by byte).
  a changed line is `newly_read` only when BEFORE was unreadable, AFTER is readable and `w3c7_explain_ja(text, DIR)['read']` is true; any other change is `other_change` (a failure).
Prints same= changed= newly_read= other_change=; --tsv gets the changed lines; --jsonl gets the newly read lines (text, clauses, relations, path, edges).
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-c7/tools/entry_compare.py BEFORE AFTER --inputs F --explain-placement DIR [--tsv OUT] [--jsonl OUT]
"""
import argparse
import collections
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TREE))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('before'); ap.add_argument('after')
    ap.add_argument('--inputs', required=True); ap.add_argument('--explain-placement', required=True)
    ap.add_argument('--tsv'); ap.add_argument('--jsonl')
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    constructions.discover()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if k.startswith('verantyx') and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    texts = [l for l in Path(a.inputs).read_text(encoding='utf-8').splitlines() if l.strip()]
    b = Path(a.before).read_text(encoding='utf-8').splitlines()
    c = Path(a.after).read_text(encoding='utf-8').splitlines()
    if not (len(texts) == len(b) == len(c)):
        print('LENGTHS DIFFER', len(texts), len(b), len(c)); sys.exit(2)
    q = R.CoarseQuery(a.explain_placement)
    cnt = collections.Counter()
    tsv, new = [], []
    paths = collections.Counter()
    for t, x, y in zip(texts, b, c):
        if x == y:
            cnt['same'] += 1
            continue
        cnt['changed'] += 1
        bx, by = json.loads(x), json.loads(y)
        ex = R.w3c7_explain_ja(t, q)
        ok = (not bx.get('readable')) and by.get('readable') is True and ex['read'] is True
        cnt['newly_read' if ok else 'other_change'] += 1
        tsv.append('%s\t%s\t%s\t%s' % ('newly_read' if ok else 'other_change', t, ex['path'], ex['reason']))
        if ok:
            paths[(ex['path'], tuple(e['kind'] for e in ex['edges']))] += 1
            new.append({'text': t, 'path': ex['path'], 'edges': ex['edges'], 'clauses': by['clauses'], 'relations': by['relations']})
    print('same=%d changed=%d newly_read=%d other_change=%d' % (cnt['same'], cnt['changed'], cnt['newly_read'], cnt['other_change']))
    for k, v in sorted(paths.items(), key=lambda kv: str(kv[0])): print('newly_read_by_path %s %s = %d' % (k[0], '+'.join(k[1]), v))
    if a.tsv: Path(a.tsv).write_text('\n'.join(tsv) + '\n', encoding='utf-8')
    if a.jsonl: Path(a.jsonl).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in new), encoding='utf-8')


if __name__ == '__main__':
    main()
