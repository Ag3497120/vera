"""O7 (self-made B3 here; the hidden bank is measured by the auditor with the same command and another --items).

An anchor is each material sentence of an item (kind seed); an item without materials is anchored by its brief (kind question). Two viewpoints per anchor:
no move (range 0) and `FACE_SWAP:agent`. Each viewpoint goes through `observe.run_entry` (the function behind the command-line entry; round 2) with the default
stub placement, so a swap is expected to be NO_MOVE_LICENSED here. Every element of every output is re-observed (`observe.reobserve`, from the JSON of the output);
a sentence that cannot be re-observed is a hallucination and is counted in `unreobservable_clauses` (expected 0).

    python tests/observe/run_bank.py --items tests/bank_score/fixtures/B3/items.jsonl --out artifacts/w3-c/b3_selfmade.jsonl --summary artifacts/w3-c/b3_selfmade_summary.json --no-index
    python tests/observe/run_bank.py --items ... --out ... --summary ... --index /Users/motonisihikoudai/Projects/vera-impl/build/p4-W1c
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import TREE    # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--items', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--summary', required=True)
    ap.add_argument('--no-index', action='store_true')
    ap.add_argument('--index')
    ap.add_argument('--index-family', action='append')
    args = ap.parse_args(argv)
    if args.no_index == (args.index is not None):
        raise SystemExit('give exactly one of --no-index and --index DIR')
    from verantyx import observe
    items = [json.loads(l) for l in Path(args.items).read_text(encoding='utf-8').splitlines() if l.strip()]
    structure = observe.build_structure(index_root=args.index, index_families=tuple(args.index_family or ('pro',)), no_index=args.no_index)
    rows = []
    summary = {'items': len(items), 'anchors': 0, 'viewpoints': 0, 'no_anchor': {}, 'realized': 0, 'refused': {}, 'unreobservable_clauses': 0, 'clauses': 0,
               'claim': {c: 0 for c in observe.CLAIMS}, 'outcome': {}, 'occupied': {s: 0 for s in observe.OCCUPANCY_STATES}, 'unreobservable_examples': []}
    for it in items:
        mats = it.get('materials') or []
        anchors = [(m, 'seed') for m in mats] if mats else [(it.get('brief', ''), 'question')]
        for text, kind in anchors:
            summary['anchors'] += 1
            for direction in ('', 'FACE_SWAP:agent'):
                range_ = 0 if direction == '' else None
                vp = observe.build_viewpoint(anchor_text=text, anchor_kind=kind, direction=direction, range_=range_)    # only to re-observe afterwards
                res = observe.run_entry(anchor_text=text, anchor_kind=kind, direction=direction, range_=range_, index_root=args.index,
                                        index_families=tuple(args.index_family or ('pro',)), no_index=args.no_index)    # the function behind `python -m verantyx.cli observe` (review r1, optional 1)
                if res.exit_code != 0: raise SystemExit('the entry refused %r: %s' % (text, res.error))
                out = json.loads(res.stdout)
                summary['viewpoints'] += 1
                summary['outcome'][out['focus']['kind']] = summary['outcome'].get(out['focus']['kind'], 0) + 1
                row = {'item': it['id'], 'anchor_kind': kind, 'anchor': text, 'direction': direction, 'outcome': out['focus']['kind']}
                if out['anchor'] is None:
                    reason = out['abstain']['reason']
                    summary['no_anchor'][reason] = summary['no_anchor'].get(reason, 0) + 1
                    row['reason'] = reason
                else:
                    els = [out['anchor']] + [e for g in out['ranks'] for e in g['elements'] if e['distance'] > 0]
                    row['elements'] = []
                    for el in els:
                        got = observe.reobserve(el, vp, structure)
                        summary['clauses'] += 1
                        summary['claim'][el['claim']] += 1
                        summary['occupied'][el['occupied']] += 1
                        if got['status'] != 'REOBSERVED':
                            summary['unreobservable_clauses'] += 1
                            summary['unreobservable_examples'].append({'item': it['id'], 'reason': got['reason']})
                        r = el['realization']
                        if r['status'] == 'REALIZED': summary['realized'] += 1
                        else: summary['refused'][r['reason']] = summary['refused'].get(r['reason'], 0) + 1
                        row['elements'].append({'cell_key': el['cell_key'], 'distance': el['distance'], 'claim': el['claim'], 'occupied': el['occupied'], 'reobserve': got['status'],
                                                'realization': r['text'] if r['status'] == 'REALIZED' else 'REFUSED:' + r['reason']})
                    if out['abstain']: row['abstain'] = out['abstain']
                rows.append(row)
    Path(args.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    Path(args.summary).write_text(json.dumps(summary, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'unreobservable_examples'}, ensure_ascii=False, sort_keys=True))
    return 0 if summary['unreobservable_clauses'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
