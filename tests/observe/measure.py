"""W3-c measurement tool. Modes: --reader-only, --reobserve, --o4, --o5, --summary (see each function). All use the frozen cases.

    python tests/observe/measure.py --reader-only --out artifacts/w3-c/reader_seed_obs.jsonl
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ARTIFACTS, DATA, TREE, build_small_index, entry_kwargs, load_cases    # noqa: E402


def reader_only(args):
    """The reader (and the event cross of the reading entry) on every seed sentence. The observer is not called."""
    from verantyx import event_cross as EC
    from verantyx import semantic_read
    rows = []
    seeds = []
    for name in sorted(DATA.glob('seeds_*.jsonl')):
        seeds += [json.loads(l) for l in name.read_text(encoding='utf-8').splitlines() if l.strip()]
    for s in seeds:
        try:
            out = semantic_read.read(s['text'], None)
        except semantic_read.ReadError as exc:
            rows.append({'id': s['id'], 'readable': False, 'read_error': exc.type})
            continue
        crossed = EC.build_crosses(out)
        row = {'id': s['id'], 'lang': out['lang'], 'readable': out['readable'], 'abstain': out['abstain'], 'unsupported': out['unsupported'],
               'clauses': out['clauses'], 'relations': out['relations'], 'rules': [m['rule'] for m in out['clause_meta']], 'cross_status': crossed.status}
        rows.append(row)
    Path(args.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    readable = [r for r in rows if r['readable']]
    by_lang = {}
    for r in rows:
        k = r.get('lang') or 'none'
        by_lang.setdefault(k, [0, 0])
        by_lang[k][0] += 1
        by_lang[k][1] += 1 if r['readable'] else 0
    reasons = {}
    for r in rows:
        if not r['readable']:
            key = r.get('read_error') or json.dumps(r['abstain'], ensure_ascii=False, sort_keys=True)
            reasons[key] = reasons.get(key, 0) + 1
    print('seeds %d, readable %d, not readable %d' % (len(rows), len(readable), len(rows) - len(readable)))
    print('by language (seeds, readable):', json.dumps(by_lang, sort_keys=True))
    for k, n in sorted(reasons.items()):
        print('  not readable x%d: %s' % (n, k))
    multi = sum(1 for r in readable if len(r['clauses']) > 1)
    print('readable with more than one clause: %d; relations produced: %d' % (multi, sum(len(r['relations']) for r in readable)))
    return 0



def all_cases(path):
    from common import load_cases as lc
    cases = lc(path)
    if Path(path).resolve() == (DATA / 'viewpoints.jsonl').resolve():
        for extra in ('viewpoints_add1.jsonl', 'viewpoints_r2.jsonl'):    # the second file is round 2 (docs change record 3)
            if (DATA / extra).exists(): cases += lc(DATA / extra)
    return cases


def collect(cases, workdir):
    """case name -> list of (output dict, entry kwargs) for every turn (the entry function behind the command line)."""
    import view
    from verantyx import observe
    index = build_small_index()
    result = {}
    for case in cases:
        kw = entry_kwargs(case, workdir, index)
        turns = []
        for _t in range(case.get('turns', 1)):
            res = observe.run_entry(**kw)
            if res.exit_code != 0: raise SystemExit('case %s: exit %s %s' % (case['case'], res.exit_code, res.error))
            turns.append(json.loads(res.stdout))
        result[case['case']] = (turns, kw)
    return result


def structure_and_viewpoint(out, kw):
    from verantyx import observe
    structure = observe.build_structure(structure_path=kw.get('structure_path'), index_root=kw.get('index_root'), index_families=kw.get('index_families', ('pro',)),
                                        no_index=kw.get('no_index', False), placement_path=kw.get('placement_path'))
    return structure, observe.viewpoint_from_dict(out['viewpoint'])


def reobserve_mode(args):
    """O2: walk every coordinate of every element again (from the JSON of the output, not the in-memory objects) and check the sentence."""
    import view
    from verantyx import event_cross as EC
    from verantyx import observe, semantic_read, semantic_realize
    stats = {'cases': 0, 'outputs': 0, 'elements': 0, 'reobserved': 0, 'mismatch': 0, 'mismatch_by_reason': {}, 'mismatch_examples': [],
             'realized': 0, 'realized_reread_equal': 0, 'extra_content_words': 0, 'alternatives_checked': 0, 'alternatives_extra_content_words': 0,
             'alternatives_reread_equal': 0, 'refused_by_reason': {}}
    for name, (turns, kw) in collect(all_cases(args.cases), args.workdir).items():
        stats['cases'] += 1
        for out in turns:
            stats['outputs'] += 1
            if out['anchor'] is None: continue
            structure, vp = structure_and_viewpoint(out, kw)
            for el in [out['anchor']] + view.elements_of(out):
                stats['elements'] += 1
                got = observe.reobserve(el, vp, structure)
                if got['status'] == 'REOBSERVED':
                    stats['reobserved'] += 1
                else:
                    stats['mismatch'] += 1
                    stats['mismatch_by_reason'][got['reason']] = stats['mismatch_by_reason'].get(got['reason'], 0) + 1
                    stats['mismatch_examples'].append({'case': name, 'cell': el['cell_key'], 'reason': got['reason']})
                r = el['realization']
                if r['status'] == 'REFUSED':
                    stats['refused_by_reason'][r['reason']] = stats['refused_by_reason'].get(r['reason'], 0) + 1
                    continue
                stats['realized'] += 1
                surfaces = [f['surface'] for a in el['cross']['arms'].values() for f in a['fillers']]
                pred = el['cross']['center']['predicate']
                if not semantic_realize.check_observed_lineage(r['text'], pred, surfaces)['passed']: stats['extra_content_words'] += 1
                reread = EC.build_crosses(semantic_read.read(r['text'], 'ja'))
                if reread.status == 'CROSSED' and len(reread.crosses) == 1 and observe.cell_key_of(reread.crosses[0]) == el['cell_key']: stats['realized_reread_equal'] += 1
                for alt in r['alternatives']:
                    stats['alternatives_checked'] += 1
                    if not semantic_realize.check_observed_lineage(alt['text'], pred, surfaces)['passed']: stats['alternatives_extra_content_words'] += 1
                    rr = EC.build_crosses(semantic_read.read(alt['text'], 'ja'))
                    if rr.status == 'CROSSED' and len(rr.crosses) == 1 and observe.cell_key_of(rr.crosses[0]) == el['cell_key']: stats['alternatives_reread_equal'] += 1
    Path(args.out).write_text(json.dumps(stats, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in stats.items() if k != 'mismatch_examples'}, ensure_ascii=False, sort_keys=True))
    return 0


STAGE_ORDER = ('distance', 'utter_verbatim', 'utter_neighbor', 'recency', 'decided')


def first_differing_stage(a, b):
    """The first stage (in the order of the field) at which two cells of a salience trace have different values: the stage that separates them."""
    for st in STAGE_ORDER:
        if a['values'][st] != b['values'][st]: return st
    return None


def attribution(t1, t2, key1):
    """Which ledger line made turn 2 differ from turn 1. X = the turn-1 focus. For every cell of rank 1 at turn 2 (a TIE has several) take the stage that separates
    it from X; that stage's `ledger_seqs` of X or of the cell must hold a seq that turn 1 appended to the ledger (the utterance or the observation). Returns
    {'ok', 'appended_seqs', 'separations'}."""
    n0 = t1['salience_trace']['ledger']['last_seq'] or 0
    n1 = t2['salience_trace']['ledger']['last_seq'] or 0
    appended = list(range(n0 + 1, n1 + 1))
    cells2 = {x['cell_key']: x for x in t2['salience_trace']['cells']}
    x = cells2.get(key1)
    seps = []
    for c in (cells2[k] for k in (t2['focus']['candidates'] if t2['focus']['kind'] == 'TIE' else [t2['focus'].get('cell_key')]) if k in cells2):
        stage = first_differing_stage(x, c) if x is not None and c is not x else None
        seqs = sorted(set((x['ledger_seqs'][stage] if stage else []) + (c['ledger_seqs'][stage] if stage else [])))
        seps.append({'stage': stage, 'ledger_seqs': seqs, 'turn1_appended_among_them': sorted(set(seqs) & set(appended))})
    ok = bool(seps) and all(sp['stage'] is not None and sp['turn1_appended_among_them'] for sp in seps)
    return {'ok': ok, 'appended_seqs': appended, 'separations': seps}


def o4_verdict(t1, t2, alts):
    """P10 read strictly. Turn 1 a TIE -> turn 2 has the same `focus` and `realization` (the same candidates). Turn 1 a FOCUS with an alternative -> turn 2 differs and the
    stage that separates the new focus from the old one cites a line that turn 1 appended. Turn 1 a FOCUS without an alternative -> the same `focus` and `realization`."""
    same = json.dumps([t1['focus'], t1['realization']], ensure_ascii=False, sort_keys=True) == json.dumps([t2['focus'], t2['realization']], ensure_ascii=False, sort_keys=True)
    key1 = t1['focus'].get('cell_key')
    attr = None
    if t1['focus']['kind'] == 'TIE': ok = same
    elif alts:
        attr = attribution(t1, t2, key1)
        ok = (not same) and attr['ok']
    else: ok = same
    return ok, same, attr


def differing_ledger_seqs(name_a, name_b):
    """The line numbers (= seq) at which two ledger files differ (they have the same number of lines)."""
    la = (DATA / 'ledgers' / (name_a + '.jsonl')).read_text(encoding='utf-8').splitlines()
    lb = (DATA / 'ledgers' / (name_b + '.jsonl')).read_text(encoding='utf-8').splitlines()
    assert len(la) == len(lb), 'the pair must have the same length'
    return [i for i, (x, y) in enumerate(zip(la, lb), 1) if x != y]


def pair_check(pair_outputs):
    """L09 and L10 differ in one line. Their outputs must differ, and every stage value that differs between the two traces must be made by that line (its seq is in
    the `ledger_seqs` of one of the two outputs for that cell and stage)."""
    import view
    diff = differing_ledger_seqs('L09', 'L10')
    o9, o10 = pair_outputs['LG09'], pair_outputs['LG10']
    c9 = {x['cell_key']: x for x in o9['salience_trace']['cells']}
    c10 = {x['cell_key']: x for x in o10['salience_trace']['cells']}
    differences = []
    for key in sorted(set(c9) | set(c10)):
        for st in STAGE_ORDER:
            if c9[key]['values'][st] != c10[key]['values'][st]:
                seqs = sorted(set(c9[key]['ledger_seqs'][st]) | set(c10[key]['ledger_seqs'][st]))
                differences.append({'cell': key, 'stage': st, 'ledger_seqs': seqs, 'is_the_differing_line': bool(set(seqs) & set(diff))})
    s9, s10 = view.summarize(o9), view.summarize(o10)
    outputs_differ = (s9['focus'], s9['tie'], s9['ranks']) != (s10['focus'], s10['tie'], s10['ranks'])
    return {'differing_ledger_seqs': diff, 'outputs_differ': outputs_differ, 'stage_differences': differences,
            'every_difference_is_made_by_the_differing_line': bool(differences) and all(d['is_the_differing_line'] for d in differences),
            'ok': outputs_differ and bool(differences) and all(d['is_the_differing_line'] for d in differences),
            'focus': {'LG09': s9['focus'] or s9['tie'], 'LG10': s10['focus'] or s10['tie']}}


def o4_compute(two_turn, pair_outputs):
    """The O4 rows. `two_turn`: case name -> (ledger name, [output of turn 1, output of turn 2]); `pair_outputs`: {'LG09': output, 'LG10': output}.
    Both readings of "alternative" (docs change record 2) are judged with the same strict rule (round 2): at the state of turn 2 (the registered one) and at the state of turn 1."""
    import view
    rows = []
    for name, (ledger, (t1, t2)) in two_turn.items():
        key1 = t1['focus'].get('cell_key')
        same_stage = lambda a, b: all(a['values'][st] == b['values'][st] for st in ('distance', 'utter_verbatim', 'utter_neighbor'))

        def alternatives(trace):
            cells = {x['cell_key']: x for x in trace['cells']}
            return sorted(k for k, v in cells.items() if key1 is not None and k != key1 and key1 in cells and same_stage(v, cells[key1]))

        alts2, alts1 = alternatives(t2['salience_trace']), alternatives(t1['salience_trace'])
        ok2, same_output, attr2 = o4_verdict(t1, t2, alts2)
        ok1, _same, attr1 = o4_verdict(t1, t2, alts1)
        s1, s2 = view.summarize(t1), view.summarize(t2)
        cells2 = {x['cell_key']: x for x in t2['salience_trace']['cells']}
        rows.append({'case': name, 'ledger': ledger, 'turn1_focus': s1.get('focus') or s1.get('tie'), 'turn2_focus': s2.get('focus') or s2.get('tie'),
                     'turn1_kind': t1['focus']['kind'], 'turn2_kind': t2['focus']['kind'],
                     'alternatives': len(alts2), 'alternatives_at_turn1_state': len(alts1), 'alternative_exists': bool(alts2),
                     'same_focus_and_realization': same_output, 'attribution_registered_reading': attr2, 'attribution_turn1_reading': attr1,
                     'turn2_utterance': t2['salience_trace']['utterance'], 'turn2_boundaries': t2['salience_trace']['boundaries'],
                     'turn2_cells_ledger_seqs': {k: v['ledger_seqs'] for k, v in sorted(cells2.items())},
                     'rule_ok': ok2, 'rule_ok_if_alternative_is_read_at_turn1_state': ok1})
    pair = pair_check(pair_outputs)
    return {'rows': rows, 'pair_L09_L10': pair, 'all_rules_ok': all(r['rule_ok'] for r in rows) and all(r['rule_ok_if_alternative_is_read_at_turn1_state'] for r in rows) and pair['ok'],
            'rows_ok': sum(1 for r in rows if r['rule_ok']), 'rows_total': len(rows),
            'violations': sorted(r['case'] for r in rows if not r['rule_ok']),
            'rows_ok_if_alternative_is_read_at_turn1_state': sum(1 for r in rows if r['rule_ok_if_alternative_is_read_at_turn1_state']),
            'violations_if_alternative_is_read_at_turn1_state': sorted(r['case'] for r in rows if not r['rule_ok_if_alternative_is_read_at_turn1_state']),
            'pair_outputs_differ': pair['outputs_differ']}


def o4_mode(args):
    """O4: the same question twice on the same ledger. P10 read strictly (round 2; the rule of each case is in `o4_verdict`): a TIE at turn 1 stays the same output; a FOCUS
    without an alternative stays the same output; a FOCUS with an alternative changes, and the stage that separates the new focus from the old one cites a ledger line that
    turn 1 appended. Alternative = another observable cell equal to the turn-1 focus on the stages distance, utter_verbatim and utter_neighbor, at the state of turn 2
    (registered) or of turn 1 (the other reading); both readings are judged. L09 and L10: every stage value that differs is made by the one differing ledger line."""
    cases = [c for c in all_cases(args.cases) if c.get('turns', 1) == 2 or c['case'] in ('LG09', 'LG10')]
    data = collect(cases, args.workdir)
    two = {c['case']: (c['ledger'], data[c['case']][0]) for c in cases if c.get('turns', 1) == 2}
    pair = {n: data[n][0][0] for n in ('LG09', 'LG10')}
    result = o4_compute(two, pair)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    for r in result['rows']:
        print('%-10s %s->%s alt(turn2 state)=%s alt(turn1 state)=%s same=%s ok=%s ok_other_reading=%s' % (r['case'], r['turn1_kind'], r['turn2_kind'], r['alternatives'], r['alternatives_at_turn1_state'],
                                                                                             r['same_focus_and_realization'], r['rule_ok'], r['rule_ok_if_alternative_is_read_at_turn1_state']))
    print('registered reading (alternative at the state of turn 2): rows ok %d of %d, violations %s' % (result['rows_ok'], result['rows_total'], result['violations']))
    print('other reading (alternative at the state of turn 1): rows ok %d of %d, violations %s' % (result['rows_ok_if_alternative_is_read_at_turn1_state'], result['rows_total'], result['violations_if_alternative_is_read_at_turn1_state']))
    p = result['pair_L09_L10']
    print('L09 vs L10: differing ledger lines %s, outputs differ %s, every stage difference made by that line %s' % (p['differing_ledger_seqs'], p['outputs_differ'], p['every_difference_is_made_by_the_differing_line']))
    return 0 if result['all_rules_ok'] else 1


def o5_mode(args):
    """O5: every cell the entry reports as UNOCCUPIED has the constructed provenance and a claim that is not an answer; the word ANSWER never appears."""
    import view
    unocc = constructed = realized_constructed = answer = 0
    texts = 0
    for name, (turns, kw) in collect(all_cases(args.cases), args.workdir).items():
        for out in turns:
            raw = json.dumps(out, ensure_ascii=False)
            if 'ANSWER' in raw: answer += 1
            texts += 1
            if out['anchor'] is None: continue
            for el in [out['anchor']] + view.elements_of(out):
                if el['occupied'] != 'UNOCCUPIED': continue
                unocc += 1
                if el['provenance'] == 'constructed:observed_unoccupied' and el['claim'] == 'CONSTRUCTED_UNOCCUPIED': constructed += 1
                if el['realization']['status'] == 'REALIZED' and el['realization']['provenance'] == 'constructed:observed_unoccupied': realized_constructed += 1
    line = 'unoccupied %d, provenance_constructed %d, claim_answer %d' % (unocc, constructed, answer)
    extra = 'outputs_scanned %d, realized_sentences_carrying_the_constructed_provenance %d' % (texts, realized_constructed)
    Path(args.out).write_text(line + '\n' + extra + '\n', encoding='utf-8')
    print(line + '\n' + extra)
    return 0 if unocc > 0 and unocc == constructed and answer == 0 else 1


def summary_mode(args):
    """Counts over the frozen cases (the first turn of each): the numbers that docs/OBSERVATION.md quotes (tests/observe/recompute.py)."""
    import view
    cases = all_cases(args.cases)
    sm = {'cases': len(cases), 'outputs': 0, 'outcome': {}, 'no_anchor_reason': {}, 'elements': 0, 'moved_elements': 0, 'realized': 0, 'refused': {},
          'claims': {}, 'occupied': {}, 'type_agreement_moved': {}, 'swap_cases_with_a_placement_file': 0, 'edge_cases': 0, 'edge_cases_with_a_move': 0}
    data = collect(cases, args.workdir)
    for case in cases:
        turns, kw = data[case['case']]
        out = turns[0]
        sm['outputs'] += 1
        sm['outcome'][out['focus']['kind']] = sm['outcome'].get(out['focus']['kind'], 0) + 1
        if 'FACE_SWAP' in case['direction'] and case.get('placement'): sm['swap_cases_with_a_placement_file'] += 1
        if 'EDGE' in case['direction']:
            sm['edge_cases'] += 1
            if len(view.elements_of(out)) and any(e['distance'] > 0 for e in view.elements_of(out)): sm['edge_cases_with_a_move'] += 1
        if out['anchor'] is None:
            sm['no_anchor_reason'][out['abstain']['reason']] = sm['no_anchor_reason'].get(out['abstain']['reason'], 0) + 1
            continue
        for el in [out['anchor']] + [e for e in view.elements_of(out) if e['distance'] > 0]:
            sm['elements'] += 1
            if el['distance'] > 0:
                sm['moved_elements'] += 1
                v = el['type_agreement']['moved_arm']['agreement']['verdict'] if el['type_agreement']['moved_arm'] else 'NONE'
                sm['type_agreement_moved'][v] = sm['type_agreement_moved'].get(v, 0) + 1
            sm['claims'][el['claim']] = sm['claims'].get(el['claim'], 0) + 1
            sm['occupied'][el['occupied']] = sm['occupied'].get(el['occupied'], 0) + 1
            r = el['realization']
            if r['status'] == 'REALIZED': sm['realized'] += 1
            else: sm['refused'][r['reason']] = sm['refused'].get(r['reason'], 0) + 1
    Path(args.out).write_text(json.dumps(sm, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(sm, ensure_ascii=False, sort_keys=True))
    return 0


def compare_mode(args):
    """The frozen expectations against the observer: raw (no disagreement applied) and with the frozen disagreements applied."""
    import copy
    import view
    cases = all_cases(args.cases)
    exp = {}
    superseded = []
    for f in ('expected.jsonl', 'expected_add1.jsonl', 'expected_r2.jsonl'):    # the last file is round 2: its rows replace the two-turn rows of the first and add new cases
        for l in (DATA / f).read_text(encoding='utf-8').splitlines():
            if l.strip():
                r = json.loads(l)
                if f == 'expected_r2.jsonl' and r['case'] in exp: superseded.append(r['case'])
                exp[r['case']] = r
    dis = json.loads((DATA / 'disagreements.json').read_text(encoding='utf-8'))['rows']
    if (DATA / 'disagreements_r2.json').exists(): dis = dis + json.loads((DATA / 'disagreements_r2.json').read_text(encoding='utf-8'))['rows']    # round 2 (none if the r2 expectations all held)
    data = collect(cases, args.workdir)
    compared = raw_equal = after_equal = 0
    raw_bad = {}
    after_bad = []
    for case in cases:
        e = exp[case['case']]
        if e['outcome'] == 'TURNS':
            continue
        compared += 1
        got = view.summarize(data[case['case']][0][0])
        raw = view.compare(e, got)
        if not raw: raw_equal += 1
        else: raw_bad[case['case']] = sorted({d[0] for d in raw})
        e2 = copy.deepcopy(e)
        for d in dis:
            if d['case'] != case['case']: continue
            if 'cell' in d: e2[d['key']][d['cell']] = d['observed']
            else: e2[d['key']] = d['observed']
        if view.compare(e2, got): after_bad.append(case['case'])
        else: after_equal += 1
    turns_ok = 0
    turns_total = 0
    for case in cases:
        e = exp[case['case']]
        if e['outcome'] != 'TURNS': continue
        turns_total += 1
        o4 = e['o4']
        t1, t2 = [view.summarize(o) for o in data[case['case']][0]]
        if ((t1['focus'], t1['tie']) == (o4['turn1'].get('focus'), o4['turn1'].get('tie')) and (t2['focus'], t2['tie']) == (o4['turn2'].get('focus'), o4['turn2'].get('tie'))
                and t2['ranks'] == [sorted(g) for g in o4['turn2']['ranks']]): turns_ok += 1
    result = {'cases_with_one_turn_expectation': compared, 'equal_raw': raw_equal, 'different_raw': compared - raw_equal, 'different_raw_cases': raw_bad,
              'equal_with_frozen_disagreements': after_equal, 'different_after_frozen_disagreements': len(after_bad),
              'frozen_disagreement_rows': len(dis), 'frozen_disagreement_cases': sorted({d['case'] for d in dis}),
              'two_turn_cases': turns_total, 'two_turn_focus_and_ranks_equal': turns_ok,
              'expectations_superseded_by_expected_r2': sorted(superseded)}
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if not after_bad else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--reader-only', action='store_true')
    ap.add_argument('--reobserve', action='store_true')
    ap.add_argument('--o4', action='store_true')
    ap.add_argument('--o5', action='store_true')
    ap.add_argument('--summary', action='store_true')
    ap.add_argument('--compare', action='store_true')
    ap.add_argument('--cases', default=str(DATA / 'viewpoints.jsonl'))
    ap.add_argument('--workdir', default=str(ARTIFACTS / 'work_measure'))
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    for flag, fn in (('reader_only', reader_only), ('reobserve', reobserve_mode), ('o4', o4_mode), ('o5', o5_mode), ('summary', summary_mode), ('compare', compare_mode)):
        if getattr(args, flag): return fn(args)
    raise SystemExit('no mode given')


if __name__ == '__main__':
    raise SystemExit(main())
