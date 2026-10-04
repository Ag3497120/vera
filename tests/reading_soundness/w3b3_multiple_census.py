#!/usr/bin/env python3
"""W3-b3 (S4 preparation): the Japanese inputs on which the reader (`document_view`, not changed) puts `multiple predicates need explicit clause scope`, by group (the public inputs, the
three self-made B1 samples, the new data, the W1-a4 misreads), with: how many the base (dev, placement r6) reads, how many the new tree reads, how many are newly read, and for those the
new tree still does not read, the reason of the path (by name). --before / --after are the dumps of w3b1_entry_dump.py --mode live (dev / now); the reasons come from `clause_scope_explain_ja`.
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b3_multiple_census.py --inputs FILE --before DEV_R6.jsonl --after NOW_R6.jsonl --placement DIR --out FILE.json
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w3b3_common as C

MULTIPLE = 'multiple predicates need explicit clause scope'


def group_of(source):
    if source in ('B1_v2', 'B1_v2_r2', 'B1_v2_r3'): return 'b1_samples'
    if source == 'w3b3_w1a4.jsonl': return 'w1a4'
    if source.startswith('w3b3_'): return 'new_data'
    return 'public'


def main():
    ap = argparse.ArgumentParser()
    for k in ('inputs', 'before', 'after', 'placement', 'out'): ap.add_argument('--' + k, required=True)
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    constructions.discover()
    C.isolation()
    inputs = C.load_jsonl(a.inputs)
    before, after = C.load_jsonl(a.before), C.load_jsonl(a.after)
    assert [r['text'] for r in inputs] == [r['text'] for r in before] == [r['text'] for r in after]
    stat = collections.defaultdict(lambda: {'multiple_inputs': 0, 'base_read': 0, 'now_read': 0, 'newly_read': 0, 'still_abstains': 0, 'still_abstains_by_reason': collections.Counter(),
                                            'newly_read_by_cut': collections.Counter()})
    for item, b, n in zip(inputs, before, after):
        text = item['text']
        if SR.detect_lang(text) != 'ja': continue
        view = R.document_view({'d': text})
        if not any(MULTIPLE in c.unsupported for c in view.clauses): continue
        s = stat[group_of(item['source'])]
        s['multiple_inputs'] += 1
        br, nr = bool(b['out'].get('readable')), bool(n['out'].get('readable'))
        s['base_read'] += br; s['now_read'] += nr
        if nr and not br:
            s['newly_read'] += 1
            s['newly_read_by_cut'][SR.clause_scope_explain_ja(text, R.CoarseQuery(a.placement))['cut']['kind']] += 1
        if not nr:
            s['still_abstains'] += 1
            ex = SR.clause_scope_explain_ja(text, R.CoarseQuery(a.placement))
            s['still_abstains_by_reason'][(ex['reason'] or '').split(':')[0] + ('' if not (ex['reason'] or '').startswith('W3B3_NOT_TRIGGERED') else ':' + ex['reason'].split(':')[1].split('=')[0])] += 1
    out = {g: dict(s, still_abstains_by_reason=dict(sorted(s['still_abstains_by_reason'].items())), newly_read_by_cut=dict(sorted(s['newly_read_by_cut'].items()))) for g, s in sorted(stat.items())}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    for g, s in out.items(): print('%s multiple_inputs=%d base_read=%d now_read=%d newly_read=%d still_abstains=%d reasons=%s newly_read_by_cut=%s' % (
        g, s['multiple_inputs'], s['base_read'], s['now_read'], s['newly_read'], s['still_abstains'], json.dumps(s['still_abstains_by_reason'], ensure_ascii=False), json.dumps(s['newly_read_by_cut'], ensure_ascii=False)))


if __name__ == '__main__':
    main()
