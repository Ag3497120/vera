"""W3-c: the frozen test data (tests/observe/data) through the entry function, against the expectations written before the first observation,
and the properties O1-O5 on every case. Disagreements between the expectations and the observer were frozen in disagreements.json, not corrected."""
import copy
import hashlib
import itertools
import json
import shutil
import sys
from pathlib import Path

import pytest

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS / 'observe'))
import common    # noqa: E402
import view      # noqa: E402

from verantyx import event_cross as EC    # noqa: E402
from verantyx import observe as O         # noqa: E402
from verantyx import salience as SAL      # noqa: E402
from verantyx import semantic_read, semantic_realize    # noqa: E402

DATA = common.DATA


def jl(path):
    return [json.loads(l) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]


CASES = jl(DATA / 'viewpoints.jsonl') + jl(DATA / 'viewpoints_add1.jsonl') + jl(DATA / 'viewpoints_r2.jsonl')
# expected_r2.jsonl (round 2, docs change record 3) replaces the six two-turn rows of expected.jsonl and adds three cases; the first file is never rewritten
EXPECTED = {r['case']: r for f in ('expected.jsonl', 'expected_add1.jsonl', 'expected_r2.jsonl') for r in jl(DATA / f)}
DISAGREEMENTS = json.loads((DATA / 'disagreements.json').read_text(encoding='utf-8'))['rows']


@pytest.fixture(scope='module')
def world(tmp_path_factory):
    root = tmp_path_factory.mktemp('w3c_data')
    index = common.build_small_index(root / 'index_small')
    out = {}
    for case in CASES:
        kw = common.entry_kwargs(case, root / 'work', index)
        turns = []
        for _t in range(case.get('turns', 1)):
            res = O.run_entry(**kw)
            assert res.exit_code == 0, (case['case'], res.error)
            turns.append(res.stdout)
        out[case['case']] = (turns, kw)
    return out


def parsed(world, name):
    return [json.loads(t) for t in world[name][0]]


# ------------------------------------------------------------------ the data itself
def test_the_data_has_the_registered_shape():
    ja, en = jl(DATA / 'seeds_ja.jsonl'), jl(DATA / 'seeds_en.jsonl')
    assert len(ja) + len(en) >= 40 and len(ja) >= 15 and len(en) >= 15
    assert all(set(r) >= {'id', 'text', 'tags', 'topic', 'note'} for r in ja + en)
    assert len({r['id'] for r in ja + en}) == len(ja) + len(en)
    assert sorted(p.name for p in (DATA / 'ledgers').glob('L*.jsonl')) == ['L%02d.jsonl' % i for i in range(1, 13)]
    assert len({c['case'] for c in CASES}) == len(CASES) and set(EXPECTED) == {c['case'] for c in CASES}


def test_frozen_files_are_unchanged():
    frozen = json.loads((DATA / 'FROZEN.json').read_text(encoding='utf-8'))['stages']
    assert list(frozen) == ['inputs', 'inputs_add1', 'expected', 'first_observation', 'disagreements', 'disagreements_o4',
                            'inputs_r2', 'expected_r2', 'first_observation_r2']
    for stage in frozen.values():
        for rel, sha in stage['files'].items():
            assert hashlib.sha256((DATA / rel).read_bytes()).hexdigest() == sha, rel


def test_ledgers_cover_the_registered_kinds():
    def kinds(name):
        return [json.loads(l)['kind'] for l in (DATA / 'ledgers' / (name + '.jsonl')).read_text(encoding='utf-8').splitlines()]
    assert kinds('L01') == [] and kinds('L02') == ['utterance', 'observation']
    assert 'decision' in kinds('L07') and kinds('L08') == ['decision', 'utterance', 'observation']
    l09, l10 = (DATA / 'ledgers' / 'L09.jsonl').read_text(encoding='utf-8').splitlines(), (DATA / 'ledgers' / 'L10.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(l09) == len(l10) == 2 and l09[0] == l10[0] and l09[1] != l10[1]    # one line differs
    assert kinds('L11') == ['utterance', 'utterance'] and kinds('L12') == ['utterance']
    texts = lambda name: [json.loads(l)['payload']['text'] for l in (DATA / 'ledgers' / (name + '.jsonl')).read_text(encoding='utf-8').splitlines()]
    assert texts('L11')[1] == texts('L12')[0] == jl(DATA / 'seeds_ja.jsonl')[0]['text']    # the latest utterance of L11 and the only one of L12 are the sentence of J01
    for name in ['L%02d' % i for i in range(1, 13)]:
        SAL.load_jsonl(DATA / 'ledgers' / (name + '.jsonl'))    # every ledger is a valid ledger


# ------------------------------------------------------------------ expectations written before the first observation
def _apply_disagreements(case, expected):
    expected = copy.deepcopy(expected)
    for d in DISAGREEMENTS:
        if d['case'] != case: continue
        if 'cell' in d:
            expected[d['key']][d['cell']] = d['observed']
        else:
            expected[d['key']] = d['observed']
    return expected


@pytest.mark.parametrize('case', [c['case'] for c in CASES if EXPECTED[c['case']]['outcome'] != 'TURNS'])
def test_output_matches_the_frozen_expectation(world, case):
    exp = _apply_disagreements(case, EXPECTED[case])
    got = view.summarize(parsed(world, case)[0])
    assert view.compare(exp, got) == []


def test_every_frozen_disagreement_is_still_a_disagreement_and_names_what_the_observer_did(world):
    # the expectation was NOT corrected: the frozen file still has the original value, which differs from what the observer gives
    for d in DISAGREEMENTS:
        want = EXPECTED[d['case']][d['key']]
        got = view.summarize(parsed(world, d['case'])[0])[d['key']]
        if 'cell' in d:
            assert want[d['cell']] != got[d['cell']] and got[d['cell']] == d['observed']
        else:
            assert want != got and got == d['observed']
        assert d['judgment'] and d['reason']


@pytest.mark.parametrize('case', [c['case'] for c in CASES if EXPECTED[c['case']]['outcome'] == 'TURNS'])
def test_two_turn_cases_o4_expectations(world, case):
    o4 = EXPECTED[case]['o4']
    t1, t2 = [view.summarize(o) for o in parsed(world, case)]
    assert (t1['focus'], t1['tie']) == (o4['turn1'].get('focus'), o4['turn1'].get('tie'))
    assert (t2['focus'], t2['tie']) == (o4['turn2'].get('focus'), o4['turn2'].get('tie'))
    assert t2['ranks'] == [sorted(g) for g in o4['turn2']['ranks']]


# ------------------------------------------------------------------ O1
def test_o1_every_case_is_byte_identical_on_a_second_run(world, tmp_path):
    index = common.build_small_index(tmp_path / 'index_small')    # the same directory name: the output carries the basename of the index root
    for case in CASES:
        kw = common.entry_kwargs(case, tmp_path / 'work2', index)
        again = []
        for _t in range(case.get('turns', 1)):
            res = O.run_entry(**kw)
            again.append(res.stdout)
        assert again == world[case['case']][0], case['case']


def test_o1_replay_from_the_ledger(world):
    from verantyx import observe
    done = 0
    for case in CASES:
        if not case.get('ledger'): continue
        turns, kw = world[case['case']]
        structure = observe.build_structure(structure_path=kw.get('structure_path'), index_root=kw.get('index_root'), index_families=kw.get('index_families', ('pro',)),
                                            no_index=kw.get('no_index', False), placement_path=kw.get('placement_path'))
        events = list(SAL.load_jsonl(kw['ledger_path']).events())
        before = len(SAL.load_jsonl(DATA / 'ledgers' / (case['ledger'] + '.jsonl')))
        new = [e for e in events[before:] if e['kind'] == 'observation']
        assert len(new) == case.get('turns', 1)
        for ev in new:
            assert observe.replay(events, ev, structure) is True, case['case']
            done += 1
    assert done >= 16


# ------------------------------------------------------------------ O2
def test_o2_reobserve_every_element_and_check_every_sentence(world):
    elements = reobserved = realized = extra = reread = 0
    for case in CASES:
        turns, kw = world[case['case']]
        for out in [json.loads(t) for t in turns]:
            if out['anchor'] is None: continue
            structure = O.build_structure(structure_path=kw.get('structure_path'), index_root=kw.get('index_root'), index_families=kw.get('index_families', ('pro',)),
                                          no_index=kw.get('no_index', False), placement_path=kw.get('placement_path'))
            vp = O.viewpoint_from_dict(out['viewpoint'])
            for el in [out['anchor']] + view.elements_of(out):
                elements += 1
                got = O.reobserve(el, vp, structure)
                assert got['status'] == 'REOBSERVED', (case['case'], el['cell_key'], got)
                reobserved += 1
                r = el['realization']
                if r['status'] == 'REALIZED':
                    realized += 1
                    surfaces = [f['surface'] for a in el['cross']['arms'].values() for f in a['fillers']]
                    assert semantic_realize.check_observed_lineage(r['text'], el['cross']['center']['predicate'], surfaces)['passed'], (case['case'], r['text'])
                    crossed = EC.build_crosses(semantic_read.read(r['text'], 'ja'))
                    assert crossed.status == 'CROSSED' and len(crossed.crosses) == 1 and O.cell_key_of(crossed.crosses[0]) == el['cell_key']
                    reread += 1
    assert elements == reobserved and realized == reread and realized > 50


def test_lineage_every_realized_sentence_and_variant_uses_only_the_words_of_its_cell(world):
    n = 0
    for case in CASES:
        for out in parsed(world, case['case']):
            if out['anchor'] is None: continue
            for el in [out['anchor']] + view.elements_of(out):
                r = el['realization']
                if r['status'] != 'REALIZED': continue
                surfaces = [f['surface'] for a in el['cross']['arms'].values() for f in a['fillers']]
                for text in [r['text']] + [a['text'] for a in r['alternatives']]:
                    lin = semantic_realize.check_observed_lineage(text, el['cross']['center']['predicate'], surfaces)
                    assert lin['passed'] and not lin['extra_lemmas'] and not lin['unexpected_tokens'], (text, lin)
                    n += 1
    assert n > 100


def test_reobserve_after_touching_a_coordinate_of_every_moved_element_is_a_mismatch(world):
    checked = 0
    for case in CASES:
        turns, kw = world[case['case']]
        out = json.loads(turns[0])
        if out['anchor'] is None: continue
        structure = O.build_structure(structure_path=kw.get('structure_path'), index_root=kw.get('index_root'), index_families=kw.get('index_families', ('pro',)),
                                      no_index=kw.get('no_index', False), placement_path=kw.get('placement_path'))
        vp = O.viewpoint_from_dict(out['viewpoint'])
        for el in [e for e in view.elements_of(out) if e['distance'] > 0]:
            bad = copy.deepcopy(el)
            bad['coords'][0]['moves'][0]['to'] = bad['coords'][0]['moves'][0]['to'] + 'X'
            assert O.reobserve(bad, vp, structure)['status'] == 'MISMATCH'
            checked += 1
    assert checked > 20


# ------------------------------------------------------------------ O3
def test_o3_a_tie_is_returned_with_its_candidates_and_in_any_order_stays_a_tie(world):
    ties = 0
    for case in CASES:
        for out in parsed(world, case['case']):
            if out['focus']['kind'] != 'TIE': continue
            ties += 1
            cands = out['focus']['candidates']
            assert len(cands) >= 2 and cands == sorted(cands)
            assert out['ranks'][0]['kind'] == 'TIE' and [e['cell_key'] for e in out['ranks'][0]['elements']] == cands
            rank1 = {c['cell_key']: c for c in out['salience_trace']['cells'] if c['rank'] == 1}
            specs = [SAL.Candidate(k, 1, ()) for k in cands]
            for perm in itertools.permutations(specs):
                r = SAL.rank(list(perm), SAL.FLAT)
                assert len(r.ranks) == 1 and sorted(r.ranks[0]) == cands
            assert set(rank1) == set(cands)
    assert ties >= 10


def test_o3_no_random_and_no_hash_order_in_the_new_files():
    import re
    pattern = re.compile(r'import random|from random|random\.|hash\(|__hash__|shuffle|uuid|secrets|urandom|\bid\(|time\.time|perf_counter|datetime\.now')
    hits = []
    for name in ('observe.py', 'salience.py'):
        for n, line in enumerate((common.TREE / 'verantyx' / name).read_text(encoding='utf-8').splitlines(), 1):
            if pattern.search(line): hits.append((name, n, line.strip()))
    assert len(hits) == 1 and hits[0][0] == 'salience.py' and 'datetime.datetime.now' in hits[0][2], hits


# ------------------------------------------------------------------ O4
def test_o4_alternative_rule_and_the_pair_l09_l10(world):
    import measure
    two = {c['case']: (c['ledger'], parsed(world, c['case'])) for c in CASES if c.get('turns', 1) == 2}
    pair = {n: parsed(world, n)[0] for n in ('LG09', 'LG10')}
    res = measure.o4_compute(two, pair)
    by = {r['case']: r for r in res['rows']}
    # P10 read strictly (review r1, required fix 2), with BOTH readings of "alternative" (the state of turn 2, the registered one; the state of turn 1): no violation in either
    assert res['violations'] == [] and res['rows_ok'] == res['rows_total'] == 6
    assert res['violations_if_alternative_is_read_at_turn1_state'] == [] and res['rows_ok_if_alternative_is_read_at_turn1_state'] == 6
    # a FOCUS with an alternative changes at turn 2, and the stage that separates the new focus from the old one cites a line that turn 1 appended
    for name in ('O4-a-L03', 'O4-e-L07'):
        r = by[name]
        assert r['turn1_kind'] == 'FOCUS' and r['alternatives'] >= 1 and not r['same_focus_and_realization']
        attr = r['attribution_registered_reading']
        assert attr['ok'] and all(sp['stage'] == 'recency' and sp['turn1_appended_among_them'] for sp in attr['separations'])
    # no alternative -> the same focus and realization; a TIE at turn 1 -> the same TIE (the same candidates)
    for name in ('O4-b-L04', 'O4-c-L05'):
        assert by[name]['turn1_kind'] == by[name]['turn2_kind'] == 'FOCUS' and by[name]['alternatives'] == 0 and by[name]['same_focus_and_realization']
    for name in ('O4-d-L01', 'O4-f-L08'):
        assert by[name]['turn1_kind'] == by[name]['turn2_kind'] == 'TIE' and by[name]['same_focus_and_realization']
        assert parsed(world, name)[0]['focus']['candidates'] == parsed(world, name)[1]['focus']['candidates']
    # the anchor sentence that turn 1 appended is skipped by stage ii at turn 2 and counted
    for name in ('O4-a-L03', 'O4-d-L01', 'O4-e-L07'):
        assert by[name]['turn2_utterance']['used_seq'] is None and len(by[name]['turn2_utterance']['skipped_same_as_anchor']) == 1
    # L09 and L10 differ in ONE line (line 2): every stage value that differs between the two traces is made by that line
    p = res['pair_L09_L10']
    assert p['differing_ledger_seqs'] == [2] and p['outputs_differ'] and p['ok'] and p['every_difference_is_made_by_the_differing_line']
    assert len(p['stage_differences']) >= 2 and all(d['stage'] == 'recency' and d['ledger_seqs'] == [2] for d in p['stage_differences'])


def test_o4_the_strict_judge_flags_the_old_rule_it_replaced(world, tmp_path):
    # sanity of the judge: the same two-turn data observed with the rule of round 1 (the anchor sentence is NOT skipped) is flagged under both readings
    import measure
    kept = SAL.build_context
    try:
        SAL.build_context = lambda ledger, neighbors=None, anchor_text=None: kept(ledger, neighbors, None)
        two = {}
        for c in CASES:
            if c.get('turns', 1) != 2: continue
            kw = dict(world[c['case']][1])
            dst = tmp_path / (c['case'] + '.jsonl')
            shutil.copyfile(DATA / 'ledgers' / (c['ledger'] + '.jsonl'), dst)
            kw['ledger_path'] = str(dst)
            two[c['case']] = (c['ledger'], [json.loads(O.run_entry(**kw).stdout) for _t in range(2)])
        pair = {n: parsed(world, n)[0] for n in ('LG09', 'LG10')}
        old = measure.o4_compute(two, pair)
    finally:
        SAL.build_context = kept
    assert old['violations'] == ['O4-d-L01', 'O4-e-L07', 'O4-f-L08']
    assert old['violations_if_alternative_is_read_at_turn1_state'] == ['O4-c-L05', 'O4-d-L01', 'O4-f-L08']


def test_o4_the_difference_is_in_the_ledger_and_not_in_chance(world):
    # the change between turns is a function of the ledger: O4-a changes at turn 2 (its own turn-1 observation lowers its focus, recency), O4-c does not (nothing in turn 1 changes stage ii)
    t1, t2 = parsed(world, 'O4-a-L03')
    assert t1['focus'] != t2['focus'] and t2['salience_trace']['ledger']['events'] > t1['salience_trace']['ledger']['events']
    c1, c2 = parsed(world, 'O4-c-L05')
    assert c1['focus'] == c2['focus'] and c2['salience_trace']['ledger']['events'] > c1['salience_trace']['ledger']['events']


def test_a_ledger_whose_latest_utterance_is_the_anchor_sentence_uses_the_one_before_it(world):
    for name in ('LG11', 'LG12'):    # LG12 gives the anchor as the record J01
        out = parsed(world, name)[0]
        assert out['salience_trace']['utterance'] == {'used_seq': 1, 'skipped_same_as_anchor': [2]}
        assert out['focus']['kind'] == 'FOCUS'
        by = {view.descriptor(c['cross']): c['cell_key'] for c in view.elements_of(out)}
        cells = {c['cell_key']: c for c in out['salience_trace']['cells']}
        assert cells[by[[d for d in by if 'agent=教授' in d][0]]]['ledger_seqs']['utter_verbatim'] == [1]    # 教授 occurs in the utterance of seq 1, not in the anchor sentence
    only = parsed(world, 'LG13')[0]
    assert only['focus']['kind'] == 'TIE' and only['salience_trace']['utterance'] == {'used_seq': None, 'skipped_same_as_anchor': [1]}
    empty = parsed(world, 'LG01')[0]
    assert [c['values'] for c in only['salience_trace']['cells']] == [c['values'] for c in empty['salience_trace']['cells']]    # as an empty ledger on every stage


# ------------------------------------------------------------------ O5
def test_o5_unoccupied_cells_carry_the_constructed_provenance_and_nothing_is_an_answer(world):
    unoccupied = 0
    for case in CASES:
        for text, out in zip(world[case['case']][0], parsed(world, case['case'])):
            assert 'ANSWER' not in text
            if out['anchor'] is None: continue
            for el in [out['anchor']] + view.elements_of(out):
                assert el['claim'] in ('OBSERVED_OCCUPIED', 'CONSTRUCTED_UNOCCUPIED', 'UNKNOWN_OCCUPANCY')
                if el['occupied'] == 'UNOCCUPIED':
                    unoccupied += 1
                    assert el['claim'] == 'CONSTRUCTED_UNOCCUPIED' and el['provenance'] == 'constructed:observed_unoccupied'
                    if el['realization']['status'] == 'REALIZED': assert el['realization']['provenance'] == 'constructed:observed_unoccupied'
                else:
                    assert el['provenance'] != 'constructed:observed_unoccupied'
    assert unoccupied >= 5
