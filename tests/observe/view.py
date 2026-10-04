"""Turn an entry output (the JSON of `observe`) into the comparable form that tests/observe/data/expected*.jsonl is written in, and compare."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import entry_kwargs    # noqa: E402


def descriptor(cross):
    c = cross['center']
    arms = ';'.join('%s=%s' % (r, '/'.join(f['surface'] for f in a['fillers'])) for r, a in cross['arms'].items())
    return '%s|%s|%s|%s' % (c['predicate'], c['polarity'], c['tense'], arms)


def realization_text(r):
    if r is None: return None
    return 'REALIZED:' + r['text'] if r['status'] == 'REALIZED' else 'REFUSED:' + r['reason']


def elements_of(out):
    return [e for g in out['ranks'] for e in g['elements']]


def summarize(out):
    """The comparable form of one output."""
    s = {'outcome': out['focus']['kind']}
    if out['abstain'] and out['abstain']['type'] == 'NO_ANCHOR':
        s['reason'] = out['abstain']['reason']
        return s
    anchor = out['anchor']
    s['anchor'] = descriptor(anchor['cross'])
    s['anchor_realization'] = realization_text(anchor['realization'])
    s['anchor_occupied'] = anchor['occupied']
    els = elements_of(out)
    by_key = {e['cell_key']: e for e in els}
    by_key[anchor['cell_key']] = anchor
    observed = [e for e in els if e['distance'] > 0]
    s['observed'] = sorted(descriptor(e['cross']) for e in observed)
    if out['abstain'] and out['abstain']['type'] == 'NO_MOVE_LICENSED':
        s['reasons'] = out['abstain']['reasons']
    focus = out['focus']
    s['focus'] = descriptor(by_key[focus['cell_key']]['cross']) if focus['kind'] == 'FOCUS' else None
    s['tie'] = sorted(descriptor(by_key[k]['cross']) for k in focus['candidates']) if focus['kind'] == 'TIE' else None
    shown = observed if observed else ([by_key[focus['cell_key']]] if focus['kind'] == 'FOCUS' else [])
    s['occupied'] = {descriptor(e['cross']): e['occupied'] for e in shown}
    s['realization'] = {descriptor(e['cross']): realization_text(e['realization']) for e in shown}
    s['claims'] = {descriptor(e['cross']): e['claim'] for e in shown}
    s['distances'] = {descriptor(e['cross']): e['distance'] for e in observed}
    s['unoccupied_marked'] = sorted(descriptor(e['cross']) for e in shown if e['claim'] == 'CONSTRUCTED_UNOCCUPIED')
    s['ranks'] = [sorted(descriptor(e['cross']) for e in g['elements']) for g in out['ranks']]
    s['basis_origin'] = {descriptor(e['cross']): e['basis_origin'] for e in shown if e['basis_origin']}
    trace = out['salience_trace']
    s['decided_by'] = [b['decided_by'] for b in trace['boundaries']]
    seqs = {}
    for c in trace['cells']:
        seqs[descriptor(by_key[c['cell_key']]['cross'])] = c['ledger_seqs']
    s['ledger_seqs'] = seqs
    c = out['counts']['moves']['FACE_SWAP']
    s['face_swap_counts'] = {'licensed': c['licensed'], 'candidates_tried': c['candidates_tried'],
                             'candidates_skipped_same_as_original': c['candidates_skipped_same_as_original'],
                             **{k: v for k, v in c['candidates_unlicensed'].items() if v}}
    return s


def compare(expected, got):
    """Diffs between an expected row and a summary (only the keys the expected row has; FOCUS rows with `observed: []` mean no moved cell)."""
    diffs = []
    for key, want in expected.items():
        if key in ('case', 'o4'): continue
        if key == 'recency_seq':
            for desc, seqs in want.items():
                have = got.get('ledger_seqs', {}).get(desc, {}).get('recency')
                if have != seqs: diffs.append((key, desc, seqs, have))
            continue
        have = got.get(key)
        if key in ('tie', 'observed', 'unoccupied_marked'):
            want = sorted(want) if want is not None else None
        if key == 'face_swap_counts':
            have = {k: v for k, v in (have or {}).items() if v or k in want}
            want = {k: v for k, v in want.items()}
        if have != want: diffs.append((key, want, have))
    return diffs


def run_case(case, workdir, index_dir=None, observe_module=None):
    """Run one case through `observe.run_entry` (the function behind the command line). Returns the outputs of every turn (parsed JSON)."""
    from verantyx import observe
    outs = []
    kw = entry_kwargs(case, workdir, index_dir)
    for _turn in range(case.get('turns', 1)):
        res = observe.run_entry(**kw)
        if res.exit_code != 0:
            raise RuntimeError('case %s exit %s %s' % (case['case'], res.exit_code, res.error))
        outs.append(json.loads(res.stdout))
    return outs
