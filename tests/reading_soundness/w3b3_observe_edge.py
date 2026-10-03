#!/usr/bin/env python3
"""W3-b3 (S5): the observer's EDGE move on readings of the new path, in this process. For each case (tests/observe/data/viewpoints.jsonl form; the anchor may hold `cross`: the number of
the cross of the sentence to stand on) `observe.run_entry` is called with the arguments of tests/observe/common.entry_kwargs (no index) and `anchor_cross`; the cells reached by an EDGE
are counted. Then every element of every output (the anchor and the ranked cells: tests/observe/view.elements_of) is walked again by `observe.reobserve` (the structure and the viewpoint
as tests/observe/measure.structure_and_viewpoint makes them) and the result is written: {elements, reobserved, mismatch, mismatch_by_reason}.
tests/observe/measure.py is NOT run and build_small_index is not called (they write under artifacts/w3-c/): only the two helpers are imported.
The reading entry reads the placement from the variable VERA_PLACEMENT (the anchor text goes through `semantic_read.read`).
Usage: cd <tree> && VERA_PLACEMENT=DIR PYTHONPATH=<tree> python tests/reading_soundness/w3b3_observe_edge.py --cases FILE --out FILE.json --reobserve-out FILE.json
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(TREE / 'tests' / 'observe'))
import w3b3_common as C


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--cases', required=True); ap.add_argument('--out', required=True); ap.add_argument('--reobserve-out', required=True)
    a = ap.parse_args()
    from verantyx import observe, constructions
    import common, view
    import measure as M    # only structure_and_viewpoint is used; importing it runs nothing
    constructions.discover()
    C.isolation()
    results, elements, reobserved, mismatch, by_reason = [], 0, 0, 0, {}
    with tempfile.TemporaryDirectory() as work:
        for case in C.load_jsonl(a.cases):
            kw = common.entry_kwargs(case, work)
            kw['anchor_cross'] = case['anchor'].get('cross')
            res = observe.run_entry(**kw)
            if res.exit_code != 0:
                results.append({'case': case['case'], 'exit_code': res.exit_code, 'error': res.error}); continue
            out = json.loads(res.stdout)
            els = view.elements_of(out)
            edge = [e for e in els if e['distance'] > 0 and e['coords'][0]['moves'] and e['coords'][0]['moves'][-1]['move'] == 'EDGE']
            row = {'case': case['case'], 'text': case['anchor']['text'], 'anchor_cross': kw['anchor_cross'], 'direction': case['direction'], 'outcome': out['focus']['kind'],
                   'abstain': out['abstain'], 'cells_by_edge': len(edge), 'cells_by_edge_detail': [{'dir': e['coords'][0]['moves'][-1]['dir'], 'predicate': e['cross']['center']['predicate'],
                                                                                                       'tense': e['cross']['center']['tense']} for e in edge]}
            if out['anchor'] is not None:
                structure, vp = M.structure_and_viewpoint(out, kw)
                for el in [out['anchor']] + els:
                    elements += 1
                    got = observe.reobserve(el, vp, structure)
                    if got['status'] == 'REOBSERVED': reobserved += 1
                    else:
                        mismatch += 1; by_reason[got['reason']] = by_reason.get(got['reason'], 0) + 1
            results.append(row)
    Path(a.out).write_text(json.dumps({'cases': results, 'cells_by_edge_total': sum(r.get('cells_by_edge', 0) for r in results)}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    Path(a.reobserve_out).write_text(json.dumps({'elements': elements, 'reobserved': reobserved, 'mismatch': mismatch, 'mismatch_by_reason': by_reason}, indent=1) + '\n', encoding='utf-8')
    for r in results: print('%s %s anchor_cross=%s %s outcome=%s cells_by_edge=%s' % (r['case'], r.get('text'), r.get('anchor_cross'), r.get('direction'), r.get('outcome'), r.get('cells_by_edge')))
    print('cases=%d cases_with_an_edge_cell=%d cells_by_edge_total=%d elements=%d reobserved=%d mismatch=%d' % (len(results), sum(1 for r in results if r.get('cells_by_edge')), sum(r.get('cells_by_edge', 0) for r in results),
                                                                                                          elements, reobserved, mismatch))


if __name__ == '__main__':
    main()
