"""W3-c4 A1: compare the outputs of `vera ask` of the base (c334fe6) and of this tree, byte for byte after masking.

    cmp_a1.py --base O1.jsonl --base2 O2.jsonl --new O3.jsonl --mask KEYS.txt [--outside-all]

Each O is the .jsonl of run_ask.py (one object per question with `exit_code` and `stdout`). The mask (docs/OBSERVATION.md, A1 の比べ方): the VALUE of every key listed in KEYS.txt (at any depth)
is replaced by 0, the key stays. Then:
  (iii) base vs base2 (the control: two runs of the same base): masked bytes must be equal for every question;
  (i)   a question the later stage cannot touch (the base verdict is not in the closed set, or no document was handed over, or --outside-all) must have masked bytes equal to the base's;
  (ii)  a question inside the closed set whose later stage mapped to ORIGINAL must equal the base after the `question_cross` key and the step `part == question_cross` of the trace are removed;
  inside the closed set and mapped to ANSWER / AMBIGUOUS_QUESTION_CROSS_TIE: changed by design, counted, not compared.
Prints one line per differing question and the counts. Exit 1 when any `differ` count is not 0."""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

TRIGGER = ('UNKNOWN_UNREAD', 'UNKNOWN_NO_EVIDENCE')


def load(path):
    out = {}
    for l in Path(path).read_text(encoding='utf-8').splitlines():
        if l.strip():
            r = json.loads(l); out[r['id']] = r
    return out


def mask(obj, keys):
    if isinstance(obj, dict): return {k: (0 if k in keys else mask(v, keys)) for k, v in obj.items()}
    if isinstance(obj, list): return [mask(v, keys) for v in obj]
    return obj


def dump(obj): return json.dumps(obj, indent=2, ensure_ascii=False)


def masked_bytes(row, keys):
    try: return (row['exit_code'], dump(mask(json.loads(row['stdout']), keys)))
    except ValueError: return (row['exit_code'], row['stdout'])


def strip_qc(row):
    o = json.loads(row['stdout'])
    o.pop('question_cross', None)
    if isinstance(o.get('trace'), list): o['trace'] = [t for t in o['trace'] if not (isinstance(t, dict) and t.get('part') == 'question_cross')]
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True); ap.add_argument('--base2', required=True); ap.add_argument('--new', required=True)
    ap.add_argument('--mask', required=True); ap.add_argument('--outside-all', action='store_true')
    ap.add_argument('--questions', help='question file: a question with docs [] is outside (no document handed over)')
    args = ap.parse_args()
    keys = {l.strip() for l in Path(args.mask).read_text(encoding='utf-8').splitlines() if l.strip()}
    b1, b2, nw = load(args.base), load(args.base2), load(args.new)
    docs_of = {}
    if args.questions:
        for l in Path(args.questions).read_text(encoding='utf-8').splitlines():
            if l.strip():
                q = json.loads(l); docs_of[q['id']] = q.get('docs') or []
    ids = sorted(set(b1) & set(b2) & set(nw))
    print('mask keys (values set to 0, keys kept): %s' % ', '.join(sorted(keys)))
    print('questions compared: %d (base %d, base2 %d, new %d)' % (len(ids), len(b1), len(b2), len(nw)))
    c = Counter(); lines = []
    for i in ids:
        if masked_bytes(b1[i], keys) == masked_bytes(b2[i], keys): c['base_vs_base2_same'] += 1
        else: c['base_vs_base2_differ'] += 1; lines.append('DIFFER base-vs-base2 %s' % i)
        try: bo = json.loads(b1[i]['stdout'])
        except ValueError: bo = {}
        inside = (not args.outside_all) and bool(docs_of.get(i, [None])) and isinstance(bo, dict) and bo.get('verdict') in TRIGGER
        if not inside:
            if masked_bytes(b1[i], keys) == masked_bytes(nw[i], keys): c['outside_same'] += 1
            else: c['outside_differ'] += 1; lines.append('DIFFER outside %s' % i)
            continue
        try: no = json.loads(nw[i]['stdout'])
        except ValueError: no = {}
        mapped = (no.get('question_cross') or {}).get('mapped_to')
        ran = any(isinstance(t, dict) and t.get('part') == 'question_cross' for t in (no.get('trace') or []))
        if no.get('door') == 'question_cross' and no.get('verdict') == 'ANSWER' or no.get('verdict') == 'AMBIGUOUS_QUESTION_CROSS_TIE':
            c['inside_changed_by_design'] += 1
        elif ran or mapped == 'ORIGINAL':
            same = (b1[i]['exit_code'] == nw[i]['exit_code'] and dump(mask(strip_qc(nw[i]), keys)) == dump(mask(bo, keys)))
            if same: c['original_same'] += 1
            else: c['original_differ'] += 1; lines.append('DIFFER original %s' % i)
        else:
            # inside the closed set but nothing of the later stage in the output: either the policy withdrew the answer (not possible for an abstention) or a bug
            c['inside_unexplained'] += 1; lines.append('UNEXPLAINED inside-set %s' % i)
    for l in lines: print(l)
    print('base1 vs base2: same %d, differ %d' % (c['base_vs_base2_same'], c['base_vs_base2_differ']))
    print('base vs new (outside the later stage): same %d, differ %d' % (c['outside_same'], c['outside_differ']))
    print('base vs new (ORIGINAL, question_cross removed): same %d, differ %d' % (c['original_same'], c['original_differ']))
    print('inside the closed set and mapped to ANSWER or TIE (changed by design, not compared): %d' % c['inside_changed_by_design'])
    print('inside the closed set, unexplained: %d' % c['inside_unexplained'])
    bad = c['base_vs_base2_differ'] + c['outside_differ'] + c['original_differ'] + c['inside_unexplained']
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
