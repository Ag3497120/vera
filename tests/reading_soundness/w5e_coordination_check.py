#!/usr/bin/env python3
"""W5-e: every row of tests/reading_soundness/w5e_coordination.jsonl through the real entry `semantic_read.read(text, 'ja')`, judged by the expectation frozen with the row.

  expect "abstain"                                 -> readable is a MISREAD (an AとB / AやB / AかB filler must not be read: not split into companion, not folded into one value)
  expect {"read_or_abstain": {"roles": {...}}}    -> not readable is an ABSTAIN (allowed); readable with exactly one clause whose roles equal the expectation is CORRECT;
                                                      anything else that is readable (another number of clauses, other roles) is a MISREAD
The placement is whatever the process has (VERA_PLACEMENT unset: none; set: that placement), and the output says which.  Prints, per group, the counts and every MISREAD row;
--out gets the same as JSON.  Exit 1 when there is a MISREAD.  The loaded verantyx modules must be under the tree (else exit 2).
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w5e_coordination_check.py --out FILE
"""
import argparse
import collections
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent
sys.path.insert(0, str(TREE))


def judge(row, out):
    """('CORRECT' | 'ABSTAIN' | 'MISREAD', detail)"""
    expect = row['expect']
    if not out.get('readable'):
        return 'ABSTAIN', {'reasons': (out.get('abstain') or {}).get('reasons')}
    if expect == 'abstain':
        return 'MISREAD', {'why': 'expected an abstention, the sentence was read', 'clauses': out.get('clauses')}
    want = expect['read_or_abstain']['roles']
    clauses = out.get('clauses') or []
    if len(clauses) != 1:
        return 'MISREAD', {'why': 'expected one clause', 'clauses': clauses}
    got = clauses[0].get('roles')
    if got != want:
        return 'MISREAD', {'why': 'roles differ', 'want': want, 'got': got}
    return 'CORRECT', {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--data', default=str(HERE / 'w5e_coordination.jsonl'))
    a = ap.parse_args()
    from verantyx import semantic_read as SR
    bad_modules = [n for n, m in sys.modules.items() if n.startswith('verantyx') and getattr(m, '__file__', None) and not str(Path(m.__file__).resolve()).startswith(str(TREE))]
    if bad_modules:
        print('modules outside the tree:', bad_modules); sys.exit(2)
    rows = [json.loads(line) for line in Path(a.data).read_text(encoding='utf-8').splitlines() if line.strip()]
    counts = collections.defaultdict(lambda: collections.Counter())
    misread, details = [], []
    for row in rows:
        out = SR.read(row['text'], 'ja')
        verdict, detail = judge(row, out)
        counts[row['group']][verdict] += 1
        details.append({'id': row['id'], 'group': row['group'], 'text': row['text'], 'verdict': verdict, **detail})
        if verdict == 'MISREAD':
            misread.append(details[-1])
    summary = {'placement': os.environ.get('VERA_PLACEMENT') or None, 'rows': len(rows),
               'groups': {g: dict(sorted(c.items())) for g, c in sorted(counts.items())},
               'misread': len(misread), 'correct': sum(c['CORRECT'] for c in counts.values()), 'abstain': sum(c['ABSTAIN'] for c in counts.values())}
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    for m in misread:
        print('MISREAD', m['id'], m['text'], json.dumps({k: v for k, v in m.items() if k not in ('id', 'group', 'text', 'verdict')}, ensure_ascii=False))
    Path(a.out).write_text(json.dumps({'summary': summary, 'rows': details}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    sys.exit(1 if misread else 0)


if __name__ == '__main__':
    main()
