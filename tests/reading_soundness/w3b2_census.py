#!/usr/bin/env python3
"""W3-b2 step 2 / R4 preparation: the Japanese inputs whose single `frame` clause is unsupported ONLY for `ambiguous case role: で` / `: に`.

For every such input (one sentence, nothing unread, one clause with rule `frame`, no condition) the script writes the group key
  (the set of unsupported reasons, the rules of the `ambiguous` roles, whether the predicate is in one of the reader's four lists, the placement state and
   type of the predicate (written form of the reader's predicate))
with the count and the first inputs. With `--read-before FILE --read-after FILE` (two outputs of `w3b1_entry_dump.py` over the same inputs, the tree before and
the tree after) each group also gets how many of its inputs were readable before and after. The reader (`document_view`) is the tree's own; nothing is changed.
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b2_census.py --inputs FILE --placement DIR --out JSON [--read-before F --read-after F]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w3b2_common as C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inputs', required=True); ap.add_argument('--placement', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--read-before'); ap.add_argument('--read-after'); ap.add_argument('--exclude-source-prefix', default=None, help='leave out the inputs whose source begins with this (w3b2_: the new data)')
    a = ap.parse_args()
    from verantyx import semantic_reader as R, semantic_read as SR, coarse_place, constructions
    constructions.discover()
    C.isolation()
    before = {r['text']: r['out'].get('readable') for r in C.load_jsonl(a.read_before)} if a.read_before else None
    after = {r['text']: r['out'].get('readable') for r in C.load_jsonl(a.read_after)} if a.read_after else None
    four = (R._TRANSFER_PREDICATES, R._GOAL_PREDICATES, R._PLACEMENT_PREDICATES, R._LOCATION_PREDICATES)
    groups = collections.OrderedDict()
    total = 0
    for item in C.load_jsonl(a.inputs):
        t = item['text']
        if a.exclude_source_prefix and item['source'].startswith(a.exclude_source_prefix): continue
        if not SR._JA_CHAR.search(t): continue
        v = R.document_view({'d': t})
        if len(list(R._sentences(t))) != 1 or v.unread or len(v.clauses) != 1: continue
        c = v.clauses[0]
        if c.rule != 'frame' or c.conditions: continue
        u = set(c.unsupported)
        if not u or not u <= {'ambiguous case role: で', 'ambiguous case role: に'}: continue
        rules = sorted({x.rule for x in c.roles if x.name == 'ambiguous'})
        inlist = any(c.predicate in f for f in four)
        ans = coarse_place.query(c.predicate, placement=a.placement)
        ptype = ans['top'][0] if ans['state'] == 'DECIDED' else ('+'.join(ans['top']) or ans['state'])
        key = '%s | %s | in_reader_list=%s | predicate=%s/%s' % (','.join(sorted(u)), ','.join(rules), inlist, ans['state'], ptype)
        g = groups.setdefault(key, {'count': 0, 'readable_before': 0, 'readable_after': 0, 'first_inputs': []})
        g['count'] += 1; total += 1
        if before is not None and before.get(t): g['readable_before'] += 1
        if after is not None and after.get(t): g['readable_after'] += 1
        if len(g['first_inputs']) < 3: g['first_inputs'].append(t)
    ordered = sorted(groups.items(), key=lambda kv: (-kv[1]['count'], kv[0]))
    by_particle = collections.Counter()
    for k, g in groups.items():
        by_particle['de' if 'で' in k.split(' | ')[0] else 'ni'] += g['count']
    doc = {'inputs_in_group': total, 'by_particle_of_the_unsupported_reason': dict(by_particle), 'with_read_columns': before is not None and after is not None,
           'groups': [dict(g, key=k) for k, g in ordered]}
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    lines = ['inputs_in_group=%d by_particle=%s' % (total, json.dumps(dict(by_particle), sort_keys=True))]
    for k, g in ordered:
        extra = ' readable_before=%d readable_after=%d' % (g['readable_before'], g['readable_after']) if doc['with_read_columns'] else ''
        lines.append('%d%s\t%s\t%s' % (g['count'], extra, k, g['first_inputs']))
    Path(a.out).with_suffix('.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
