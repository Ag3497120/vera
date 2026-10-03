"""W3-c: observe(viewpoint, structure) — anchors, moves, occupancy, re-observation, the turn record and replay.

The reading entry is called for anchor sentences that it reads; EDGE needs `relations`, which the entry does not produce, so those tests
use READINGS WRITTEN BY HAND (`reading_source: injected`) through the public API. Placements are fakes (tests/observe/fakes.py).
"""
import copy
import importlib.util
import itertools
import json
from pathlib import Path

import pytest

from verantyx import observe as O
from verantyx import salience as SAL

_spec = importlib.util.spec_from_file_location('w3c_observe_fakes', Path(__file__).resolve().parent / 'observe' / 'fakes.py')
fakes = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fakes)

GIVE = fakes.GIVE
SRC = 'llm_authored:codex:pro-b00001'


def vp(text=GIVE, direction='', range_=None, kind='seed', **kw):
    return O.Viewpoint(O.AnchorText(kind, text, **kw), O.parse_direction(direction), range_)


def struct(placement=None, items=(), index=None):
    p = placement
    return O.Structure.from_injected(items, p, p, index) if p is not None else O.Structure.from_injected(items, None, None, index)


def elements(obs):
    return [e for g in obs.ranks for e in g]


def surfaces_of(element, role):
    return [f['surface'] for f in element.to_dict()['cross']['arms'][role]['fillers']]


def make_index(tmp_path, rows):
    from tools import build_p4_corpus_index as bi
    root = tmp_path / 'corpus'
    (root / 'out').mkdir(parents=True)
    lines = [json.dumps({'text': t, 'source': SRC, 'scene': 's', 'sha': 'h%d' % i}, ensure_ascii=False) for i, t in enumerate(rows)]
    (root / 'out' / 'sentences.jsonl').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    assert bi.main(['--root', str(root), '--out', str(tmp_path / 'idx'), '--manifest', str(tmp_path / 'm.json'), '--family', 'pro']) == 0
    return tmp_path / 'idx'


# ------------------------------------------------------------------ the types
def test_viewpoint_is_closed():
    with pytest.raises(ValueError, match='BAD_ARGUMENTS'):
        O.Viewpoint(O.AnchorText('story', 'x'))
    with pytest.raises(ValueError, match='BAD_ARGUMENTS'):
        O.Viewpoint(O.AnchorText('seed', 'x'), (O.FaceSwap('colour'),))
    with pytest.raises(ValueError, match='BAD_ARGUMENTS'):
        O.Viewpoint(O.AnchorText('seed', 'x'), (O.Edge('because'),))
    with pytest.raises(ValueError, match='BAD_ARGUMENTS'):
        O.Viewpoint(O.AnchorText('seed', 'x'), (O.FaceSwap('agent'),), 2)
    with pytest.raises(ValueError, match='BAD_ARGUMENTS'):
        O.Viewpoint(O.AnchorText('seed', 'x'), (O.FaceSwap('agent'),), -1)
    with pytest.raises(ValueError, match='BAD_ARGUMENTS'):
        O.Viewpoint('anchor')
    assert O.Viewpoint(O.AnchorText('seed', 'x'), (O.FaceSwap('agent'), O.Edge('cause'))).effective_range == 2
    assert O.Viewpoint(O.AnchorText('seed', 'x'), (O.FaceSwap('agent'), O.Edge('cause')), 1).effective_range == 1


@pytest.mark.parametrize('spec', ['FACE_SWAP', 'FACE_SWAP:', 'FACE_SWAP:colour', 'EDGE:because', 'SWAP:agent', 'FACE_SWAP:agent,', ' FACE_SWAP:agent',
                                  'FACE_SWAP: agent', 'FACE_SWAP:agent EDGE:cause'])
def test_direction_syntax_is_closed(spec):
    with pytest.raises(ValueError, match='BAD_ARGUMENTS'):
        O.parse_direction(spec)


def test_direction_parses_in_order():
    assert O.parse_direction('') == ()
    assert O.parse_direction('FACE_SWAP:agent,EDGE:relative') == (O.FaceSwap('agent'), O.Edge('relative'))


# ------------------------------------------------------------------ anchors (D13)
def test_anchor_text_is_read_and_is_the_only_cell_when_no_move():
    obs = O.observe(vp(), struct())
    assert obs.outcome == 'FOCUS' and obs.focus.cell_key == obs.anchor.cell.key
    d = obs.to_dict()
    assert d['anchor']['cross_origin'] == 'read:semantic_read' and d['anchor']['cross']['center']['predicate'] == 'あげる'
    assert d['anchor']['coords'] == [{'origin': {'kind': 'anchor', 'id': 'anchor', 'cross_index': 0}, 'moves': []}]


def test_no_anchor_when_the_reader_abstains():
    obs = O.observe(vp('こんにちは。'), struct())
    d = obs.to_dict()
    assert obs.outcome == 'NO_ANCHOR' and d['abstain']['reason'] == 'READER_ABSTAINED' and d['anchor'] is None
    assert d['abstain']['detail']['kind'] in ('unreadable_input', 'not_supported')


def test_no_anchor_for_a_read_error_is_typed_not_swallowed():
    obs = O.observe(vp(''), struct())
    assert obs.outcome == 'NO_ANCHOR' and obs.focus.reason == 'READ_ERROR:EMPTY_TEXT'


def test_no_anchor_record_not_in_structure():
    obs = O.observe(O.Viewpoint(O.AnchorRecord('nope')), struct())
    assert obs.focus.reason == 'RECORD_NOT_IN_STRUCTURE'


def test_no_anchor_when_the_anchor_has_several_crosses_and_no_index():
    two = fakes.read_out([fakes.clause('行く', {'agent': '太郎'}), fakes.clause('買う', {'agent': '花子', 'patient': '本'})])
    v = O.Viewpoint(O.AnchorText('seed', 'x', None, None, two))
    obs = O.observe(v, struct())
    assert obs.outcome == 'NO_ANCHOR' and obs.focus.reason == 'ANCHOR_CROSS_AMBIGUOUS'
    assert len(obs.focus.detail['candidates']) == 2 and all(k.startswith('cell:') for k in obs.focus.detail['candidates'])    # nothing chosen
    ok = O.observe(O.Viewpoint(O.AnchorText('seed', 'x', None, 1, two)), struct())
    assert ok.outcome == 'FOCUS' and ok.anchor.cell.cross.center['predicate'] == '買う'
    out_of_range = O.observe(O.Viewpoint(O.AnchorText('seed', 'x', None, 5, two)), struct())
    assert out_of_range.focus.reason == 'ANCHOR_CROSS_INDEX_OUT_OF_RANGE'


def test_anchor_record_uses_the_structure_reading():
    s = struct(items=[{'id': 's1', 'text': GIVE, 'reading': fakes.read_out([fakes.clause('あげる', {'agent': '太郎', 'patient': '本', 'recipient': '花子'})])}])
    obs = O.observe(O.Viewpoint(O.AnchorRecord('s1')), s)
    d = obs.to_dict()
    assert obs.outcome == 'FOCUS' and d['anchor']['coords'][0]['origin'] == {'kind': 'structure', 'id': 's1', 'cross_index': 0}
    assert d['anchor']['cross_origin'] == 'read:injected'
    assert d['structure']['by_reading_source'] == {'semantic_read': 0, 'injected': 1}


def test_unreadable_record_is_no_anchor():
    s = O.Structure.from_injected([{'id': 'u', 'reading': {'schema': fakes.SCHEMA, 'lang': 'ja', 'readable': False, 'clauses': [], 'relations': [],
                                                           'abstain': {'kind': 'not_supported', 'reasons': ['X']}, 'unsupported': [], 'clause_meta': []}}])
    assert O.observe(O.Viewpoint(O.AnchorRecord('u')), s).focus.reason == 'READER_ABSTAINED'


# ------------------------------------------------------------------ FACE_SWAP (D5)
def test_default_stub_placement_licenses_no_face_swap():
    obs = O.observe(vp(direction='FACE_SWAP:agent'), struct())
    assert obs.outcome == 'NO_MOVE_LICENSED'
    assert obs.to_dict()['abstain']['reasons'] == {'FACE_SWAP:NO_PLACEMENT': 1}
    assert obs.to_dict()['counts']['moves']['FACE_SWAP']['cells_unlicensed']['NO_PLACEMENT'] == 1
    assert obs.anchor is not None and obs.ranks == ()


def test_face_swap_licenses_only_agree_and_counts_every_other_reason():
    p = fakes.people_placement()
    obs = O.observe(vp(direction='FACE_SWAP:agent'), struct(p))
    c = obs.to_dict()['counts']['moves']['FACE_SWAP']
    assert sorted(surfaces_of(e, 'agent')[0] for e in elements(obs)) == sorted(['犬', '次郎', '花子'])
    assert c['licensed'] == 3 and c['candidates_skipped_same_as_original'] == 1 and c['candidates_tried'] == 9
    assert c['candidates_unlicensed']['DISAGREE'] == 2
    assert c['candidates_unlicensed']['NOT_CHECKED:ESTIMATED_NEAR'] == 1
    assert c['candidates_unlicensed']['NOT_CHECKED:UNPLACED'] == 1
    assert c['candidates_unlicensed']['NOT_CHECKED:MULTIPLE'] == 1
    assert c['candidates_unlicensed']['NOT_CHECKED:UNKNOWN'] == 1
    assert sum(c['candidates_unlicensed'].values()) == 9 - 3
    for e in elements(obs):
        d = e.to_dict()
        assert d['type_agreement']['moved_arm']['agreement']['verdict'] == 'AGREE' and d['cross_origin'] == 'constructed:face_swap'
        assert d['coords'][0]['moves'][0]['move'] == 'FACE_SWAP' and d['coords'][0]['moves'][0]['neighbor_source'] == 'fake-placement/1'


def test_face_swap_changes_only_the_one_arm():
    obs = O.observe(vp(direction='FACE_SWAP:agent'), struct(fakes.people_placement()))
    for e in elements(obs):
        d = e.to_dict()['cross']
        assert surfaces_of(e, 'patient') == ['本'] and surfaces_of(e, 'recipient') == ['花子']
        assert d['center'] == obs.anchor.to_dict()['cross']['center']


def test_flat_field_with_several_candidates_is_a_tie_not_a_choice():
    obs = O.observe(vp(direction='FACE_SWAP:agent'), struct(fakes.people_placement()))
    assert obs.outcome == 'TIE' and len(obs.focus.candidates) == 3 and len(obs.ranks) == 1
    assert list(obs.focus.candidates) == sorted(obs.focus.candidates)    # string order, a display order
    assert obs.to_dict()['salience_trace']['rank1'] == {'kind': 'TIE', 'size': 3}
    assert [r['cell_key'] for r in obs.to_dict()['realization']] == list(obs.focus.candidates)    # every tied candidate is returned with its realization


def test_patient_is_never_licensed_even_with_a_placement_that_would_agree():
    p = fakes.FakePlacement({'本': fakes.direct('ARTIFACT'), 'ノート': fakes.direct('ARTIFACT')}, {'本': ('ノート',)})
    obs = O.observe(vp(direction='FACE_SWAP:patient'), struct(p))
    assert obs.outcome == 'NO_MOVE_LICENSED' and obs.to_dict()['abstain']['reasons'] == {'FACE_SWAP:ROLE_NOT_IN_TABLE': 1}
    assert p.neighbor_calls == []    # the table decides before any neighbour is asked


def test_face_swap_without_that_arm():
    obs = O.observe(vp(direction='FACE_SWAP:place'), struct(fakes.people_placement()))
    assert obs.to_dict()['abstain']['reasons'] == {'FACE_SWAP:NO_ARM': 1}


def test_face_swap_on_an_arm_tie_is_refused():
    tie = fakes.read_out([fakes.clause('あげる', {'agent': ['太郎', '次郎'], 'patient': '本'})])
    obs = O.observe(O.Viewpoint(O.AnchorText('seed', 'x', None, None, tie), (O.FaceSwap('agent'),)), struct(fakes.people_placement()))
    assert obs.to_dict()['abstain']['reasons'] == {'FACE_SWAP:ARM_TIE': 1}


def test_a_word_with_no_neighbours_is_named_no_neighbors():
    p = fakes.FakePlacement({'太郎': fakes.direct('PERSON')}, {'太郎': ()})
    obs = O.observe(vp(direction='FACE_SWAP:agent'), struct(p))
    assert obs.to_dict()['abstain']['reasons'] == {'FACE_SWAP:NO_NEIGHBORS': 1}


def test_unknown_word_and_broken_neighbor_answers_are_different_reasons():
    p = fakes.FakePlacement({}, {})    # the word is not in the placement: UNKNOWN
    assert O.observe(vp(direction='FACE_SWAP:agent'), struct(p)).to_dict()['abstain']['reasons'] == {'FACE_SWAP:UNKNOWN': 1}
    broken = fakes.FakePlacement({}, {}, {'太郎': O.NeighborResult('FOUND', (), {})})
    assert O.observe(vp(direction='FACE_SWAP:agent'), struct(broken)).to_dict()['abstain']['reasons'] == {'FACE_SWAP:NEIGHBORS_RESULT_INVALID': 1}
    not_a_result = fakes.FakePlacement({}, {}, {'太郎': 'FOUND'})
    assert O.observe(vp(direction='FACE_SWAP:agent'), struct(not_a_result)).to_dict()['abstain']['reasons'] == {'FACE_SWAP:NEIGHBORS_RESULT_INVALID': 1}


def test_all_candidates_refused_is_named_at_cell_level():
    p = fakes.FakePlacement({'机': fakes.direct('ARTIFACT')}, {'太郎': ('机',)})
    obs = O.observe(vp(direction='FACE_SWAP:agent'), struct(p))
    r = obs.to_dict()['abstain']['reasons']
    assert r == {'FACE_SWAP:NO_CANDIDATE_LICENSED': 1, 'FACE_SWAP:candidate:DISAGREE': 1}


def test_the_placement_is_asked_one_word_at_a_time_and_the_type_rule_is_not_rewritten():
    p = fakes.people_placement()
    O.observe(vp(direction='FACE_SWAP:agent'), struct(p))
    assert all(args == () and kwargs == {} for _w, args, kwargs in p.lookup_calls)


# ------------------------------------------------------------------ neighbour order (O3)
def test_the_order_of_neighbours_never_changes_the_output():
    outs = set()
    near = list(fakes.PEOPLE_NEAR['太郎'])
    for perm in itertools.islice(itertools.permutations(near), 0, 400, 37):
        p = fakes.FakePlacement(fakes.PEOPLE, {'太郎': perm})
        outs.add(O.to_json(O.observe(vp(direction='FACE_SWAP:agent'), struct(p))))
    assert len(outs) == 1
    assert json.loads(outs.pop())['focus']['kind'] == 'TIE'


# ------------------------------------------------------------------ EDGE (D6), on injected readings
def two_clause_reading(relation='cause', frm=0, to=1):
    return fakes.read_out(
        [fakes.clause('行く', {'agent': '太郎', 'place': '駅'}), fakes.clause('買う', {'agent': '花子', 'patient': '本'})],
        [{'type': relation, 'from': frm, 'to': to}])


def edge_view(direction, reading, cross_index=0, items=()):
    return O.Viewpoint(O.AnchorText('seed', 'x', None, cross_index, reading), O.parse_direction(direction)), struct(items=items)


def test_edge_forward_follows_the_relation_the_reading_holds():
    v, s = edge_view('EDGE:cause', two_clause_reading())
    obs = O.observe(v, s)
    assert obs.outcome == 'FOCUS'
    e = elements(obs)[0].to_dict()
    assert e['cross']['center']['predicate'] == '買う'
    assert e['coords'][0]['moves'] == [{'move': 'EDGE', 'relation': 'cause', 'reading': 'anchor', 'from': 0, 'to': 1, 'dir': 'forward'}]
    assert e['cross_origin'] == 'read:injected'
    c = obs.to_dict()['counts']['moves']['EDGE']
    assert c['licensed'] == 1 and c['licensed_by_reading_source'] == {'semantic_read': 0, 'injected': 1}


def test_edge_backward():
    v, s = edge_view('EDGE:cause', two_clause_reading(), cross_index=1)
    e = elements(O.observe(v, s))[0].to_dict()
    assert e['cross']['center']['predicate'] == '行く' and e['coords'][0]['moves'][0]['dir'] == 'backward'


def test_edge_with_another_relation_or_no_relation_is_no_move_licensed():
    v, s = edge_view('EDGE:contrast', two_clause_reading())
    obs = O.observe(v, s)
    assert obs.outcome == 'NO_MOVE_LICENSED' and obs.to_dict()['abstain']['reasons'] == {'EDGE:NO_RELATION_IN_STRUCTURE': 1}
    plain = fakes.read_out([fakes.clause('行く', {'agent': '太郎'})])
    obs2 = O.observe(*edge_view('EDGE:cause', plain))
    assert obs2.outcome == 'NO_MOVE_LICENSED'


def test_edge_is_not_made_from_adjacency():
    adjacent = fakes.read_out([fakes.clause('行く', {'agent': '太郎'}), fakes.clause('買う', {'agent': '花子'})])    # two clauses, no relation
    obs = O.observe(*edge_view('EDGE:sequence', adjacent))
    assert obs.outcome == 'NO_MOVE_LICENSED'


def test_edge_goes_through_a_structure_reading_that_holds_the_same_cross():
    # the anchor sentence is read by the entry (one cross); a structure sentence holds a cross with the same content AND a relation
    s_reading = fakes.read_out([fakes.clause('あげる', {'agent': '太郎', 'patient': '本', 'recipient': '花子'}), fakes.clause('喜ぶ', {'agent': '花子'}, tense='nonpast')],
                               [{'type': 'cause', 'from': 0, 'to': 1}])
    s = struct(items=[{'id': 's9', 'text': GIVE, 'reading': s_reading}])
    obs = O.observe(vp(direction='EDGE:cause'), s)
    e = elements(obs)[0].to_dict()
    assert e['cross']['center']['predicate'] == '喜ぶ'
    assert e['coords'][0]['moves'][0]['reading'] == 's9' and e['coords'][0]['origin']['kind'] == 'anchor'


def test_a_revisit_is_dropped_and_counted():
    v, s = edge_view('EDGE:cause,EDGE:cause', two_clause_reading(), cross_index=0)
    # level 1: cross 1; level 2: from cross 1 the relation points back to cross 0 = the anchor -> dropped
    obs = O.observe(v, s)
    assert [e.cell.distance for e in elements(obs)] == [1]
    assert obs.to_dict()['counts']['revisits_dropped'] == 1


def test_two_paths_to_the_same_content_become_one_cell_with_both_coords():
    reading = fakes.read_out(
        [fakes.clause('行く', {'agent': '太郎'}), fakes.clause('買う', {'agent': '花子'})],
        [{'type': 'cause', 'from': 0, 'to': 1}])
    twin = fakes.read_out([fakes.clause('行く', {'agent': '太郎'}), fakes.clause('買う', {'agent': '花子'})], [{'type': 'cause', 'from': 0, 'to': 1}])
    obs = O.observe(O.Viewpoint(O.AnchorText('seed', 'x', None, 0, reading), (O.Edge('cause'),)), struct(items=[{'id': 't', 'reading': twin}]))
    es = elements(obs)
    assert len(es) == 1
    readings = [c['moves'][0]['reading'] for c in es[0].to_dict()['coords']]
    assert readings == ['anchor', 't']    # every path is listed, in the string order of its canonical JSON


def test_face_swap_then_face_swap_back_is_a_revisit():
    p = fakes.FakePlacement({'太郎': fakes.direct('PERSON'), '次郎': fakes.direct('PERSON')}, {'太郎': ('次郎',), '次郎': ('太郎',)})
    obs = O.observe(vp(direction='FACE_SWAP:agent,FACE_SWAP:agent'), struct(p))
    assert [e.cell.distance for e in elements(obs)] == [1]
    assert obs.to_dict()['counts']['revisits_dropped'] == 1


def test_range_limits_how_many_moves_are_applied():
    p = fakes.FakePlacement({'太郎': fakes.direct('PERSON'), '次郎': fakes.direct('PERSON'), '三郎': fakes.direct('PERSON')},
                            {'太郎': ('次郎',), '次郎': ('三郎',)})
    two = O.observe(vp(direction='FACE_SWAP:agent,FACE_SWAP:agent'), struct(p))
    assert sorted(e.cell.distance for e in elements(two)) == [1, 2]
    one = O.observe(vp(direction='FACE_SWAP:agent,FACE_SWAP:agent', range_=1), struct(p))
    assert [e.cell.distance for e in elements(one)] == [1]
    assert one.outcome == 'FOCUS' and one.focus.cell_key == elements(one)[0].cell.key
    zero = O.observe(vp(direction='FACE_SWAP:agent', range_=0), struct(p))
    assert zero.outcome == 'FOCUS' and zero.focus.cell_key == zero.anchor.cell.key
    # distance is the first stage of the field: the nearer cell is the focus
    assert two.outcome == 'FOCUS' and two.focus.cell_key == [e for e in elements(two) if e.cell.distance == 1][0].cell.key


# ------------------------------------------------------------------ occupancy (D7)
def test_structure_sentence_attests_by_cross_not_by_string():
    items = [{'id': 's1', 'text': GIVE, 'reading': fakes.read_out([fakes.clause('あげる', {'agent': '次郎', 'patient': '本', 'recipient': '花子'})])}]
    obs = O.observe(vp(direction='FACE_SWAP:agent'), struct(fakes.people_placement(), items))
    by = {surfaces_of(e, 'agent')[0]: e.to_dict() for e in elements(obs)}
    assert by['次郎']['occupied'] == 'ATTESTED' and by['次郎']['claim'] == 'OBSERVED_OCCUPIED'
    assert by['次郎']['occupancy'][0]['witness'] == [{'reading': 's1', 'cross_index': 0}]
    assert by['花子']['claim'] == 'UNKNOWN_OCCUPANCY' and by['花子']['provenance'] == 'observed:occupancy_unknown:UNKNOWN_NO_INDEX'    # no index asked


def test_no_index_is_unknown_not_unoccupied():
    obs = O.observe(vp(direction='FACE_SWAP:agent'), struct(fakes.people_placement()))
    for e in elements(obs):
        d = e.to_dict()
        assert d['occupied'] == 'UNKNOWN_NO_INDEX' and d['claim'] == 'UNKNOWN_OCCUPANCY'
        assert [s['state'] for s in d['occupancy']] == ['UNOCCUPIED', 'UNKNOWN_NO_INDEX']
    occ = obs.to_dict()['counts']['occupancy']
    assert occ['ATTESTED'] == 1 and occ['UNKNOWN_NO_INDEX'] == 3 and occ['UNOCCUPIED'] == 0    # the anchor is attested by its own reading; the swaps are unknown


def test_anchor_text_is_attested_by_its_own_reading():
    obs = O.observe(vp(), struct())
    d = obs.to_dict()['anchor']
    assert d['occupied'] == 'ATTESTED' and d['occupancy'][0]['witness'] == [{'reading': 'anchor', 'cross_index': 0}]


def test_index_attests_by_cross_and_a_substring_hit_with_another_cross_does_not(tmp_path):
    idx = make_index(tmp_path, ['次郎は花子に本をあげた。', '日本は花子に本をあげた。', '本を読むのは楽しい。', 'ただの文字列。'])
    spec = O.IndexSpec(idx, ('pro',))
    obs = O.observe(vp(direction='FACE_SWAP:agent'), struct(fakes.people_placement(), index=spec))
    by = {surfaces_of(e, 'agent')[0]: e.to_dict() for e in elements(obs)}
    jiro = by['次郎']
    assert jiro['occupied'] == 'ATTESTED' and jiro['claim'] == 'OBSERVED_OCCUPIED' and jiro['basis_origin'] == 'generated'
    w = jiro['occupancy'][1]
    assert w['source'] == 'index:pro' and w['witness'][0]['origin'] == 'generated' and w['witness'][0]['generator'] == 'codex'
    inu = by['犬']
    assert inu['occupied'] == 'UNOCCUPIED' and inu['claim'] == 'CONSTRUCTED_UNOCCUPIED' and inu['provenance'] == 'constructed:observed_unoccupied'
    assert inu['basis_origin'] is None
    assert inu['occupancy'][1]['detail']['rows_read'] >= 1     # 本 matched rows (incl. 日本 ...) were read and none was this cross


def test_sources_are_separate_and_not_summed():
    attested = O.Occupancy((O.OccupancySource('structure', 'UNOCCUPIED', None, {}), O.OccupancySource('index:pro', 'ATTESTED', [{'origin': 'generated'}], {})))
    assert attested.occupied == 'ATTESTED' and attested.basis_origin == 'generated'
    both = O.Occupancy((O.OccupancySource('structure', 'UNOCCUPIED', None, {}), O.OccupancySource('index:pro', 'UNOCCUPIED', None, {})))
    assert both.occupied == 'UNOCCUPIED'
    mixed = O.Occupancy((O.OccupancySource('structure', 'UNOCCUPIED', None, {}), O.OccupancySource('index:pro', 'UNKNOWN_WINDOW_SATURATED', None, {}),
                         O.OccupancySource('index:code', 'UNKNOWN_FAMILY_DB_MISSING', None, {})))
    assert mixed.occupied == 'UNKNOWN_WINDOW_SATURATED'    # the first UNKNOWN in the order asked
    assert O.Occupancy((O.OccupancySource('structure', 'UNOCCUPIED', None, {}), O.OccupancySource('index:pro', 'UNKNOWN_FAMILY_DB_MISSING', None, {}),
                        O.OccupancySource('index:code', 'UNKNOWN_WINDOW_SATURATED', None, {}))).occupied == 'UNKNOWN_FAMILY_DB_MISSING'


def test_a_saturated_window_with_no_match_is_unknown_not_unoccupied(tmp_path):
    rows = ['本%d は面白い。' % i for i in range(5)] + ['日本は広い。']
    idx = make_index(tmp_path, rows)
    spec = O.IndexSpec(idx, ('pro',), window=3)
    obs = O.observe(vp(direction='FACE_SWAP:agent'), struct(fakes.people_placement(), index=spec))
    for e in elements(obs):
        d = e.to_dict()
        assert d['occupied'] == 'UNKNOWN_WINDOW_SATURATED' and d['claim'] == 'UNKNOWN_OCCUPANCY'
        assert any(s['hits'] == 3 for s in d['occupancy'][1]['detail']['searches'])


def test_missing_family_db_and_missing_index_are_their_own_states(tmp_path):
    idx = make_index(tmp_path, ['次郎は花子に本をあげた。'])
    other = O.observe(vp(), struct(index=O.IndexSpec(idx, ('code',)))).to_dict()['anchor']
    assert other['occupancy'][1]['state'] == 'UNKNOWN_FAMILY_DB_MISSING'
    nothing = O.observe(vp(direction='FACE_SWAP:agent'), struct(fakes.people_placement(), index=O.IndexSpec(tmp_path / 'absent', ('pro',))))
    for e in elements(nothing):
        assert e.to_dict()['occupied'] == 'UNKNOWN_NO_INDEX'
    # an anchor that its own reading attests stays ATTESTED whatever the index says
    assert other['occupied'] == 'ATTESTED'


def test_two_families_are_two_sources_never_one_vote(tmp_path):
    idx = make_index(tmp_path, ['次郎は花子に本をあげた。'])
    spec = O.IndexSpec(idx, ('pro', 'code'))
    obs = O.observe(vp(direction='FACE_SWAP:agent'), struct(fakes.people_placement(), index=spec))
    by = {surfaces_of(e, 'agent')[0]: e.to_dict() for e in elements(obs)}
    assert [s['source'] for s in by['次郎']['occupancy']] == ['structure', 'index:pro', 'index:code']
    assert by['次郎']['occupied'] == 'ATTESTED'
    assert by['花子']['occupied'] == 'UNKNOWN_FAMILY_DB_MISSING'    # pro: UNOCCUPIED, code: no such database -> not UNOCCUPIED


def test_the_index_is_opened_read_only_and_not_changed(tmp_path):
    idx = make_index(tmp_path, ['次郎は花子に本をあげた。'])
    before = (idx / 'pro.db').read_bytes()
    O.observe(vp(direction='FACE_SWAP:agent'), struct(fakes.people_placement(), index=O.IndexSpec(idx, ('pro',))))
    assert (idx / 'pro.db').read_bytes() == before


# ------------------------------------------------------------------ realization and the claim (D11, D12)
def test_realization_and_claim_travel_together():
    obs = O.observe(vp(direction='FACE_SWAP:agent'), struct(fakes.people_placement()))
    for e in elements(obs):
        r = e.realization
        assert r['status'] == 'REALIZED' and r['claim'] == 'UNKNOWN_OCCUPANCY' and r['provenance'].startswith('observed:occupancy_unknown')
        assert r['text'].endswith('に本をあげた。') and r['derivation'] == 'observed-cross'
    assert 'ANSWER' not in O.to_json(obs)


def test_unoccupied_cells_have_a_constructed_provenance_and_never_an_answer(tmp_path):
    idx = make_index(tmp_path, ['ただの文字列。'])
    obs = O.observe(vp(direction='FACE_SWAP:agent'), struct(fakes.people_placement(), index=O.IndexSpec(idx, ('pro',))))
    es = elements(obs)
    assert es and all(e.claim == 'CONSTRUCTED_UNOCCUPIED' and e.realization['provenance'] == 'constructed:observed_unoccupied' for e in es)
    assert 'ANSWER' not in O.to_json(obs)


def test_english_cross_is_a_typed_refusal():
    obs = O.observe(vp('Taro gave Hanako a book.'), struct())
    r = obs.to_dict()['anchor']['realization']
    assert r['status'] == 'REFUSED' and r['reason'] == 'NOT_REALIZABLE'
    refused = obs.to_dict()['counts']['realization']['refused']    # round 2: the zero counts are listed too (review r1, required fix 4)
    assert refused['NOT_REALIZABLE'] == 1 and sum(refused.values()) == 1 and list(refused) == sorted(refused)


# ------------------------------------------------------------------ reobserve (O2)
def test_reobserve_agrees_for_every_element():
    p = fakes.people_placement()
    v = vp(direction='FACE_SWAP:agent')
    s = struct(p)
    obs = O.observe(v, s)
    assert elements(obs) and O.reobserve(obs.anchor, v, s)['status'] == 'REOBSERVED'
    for e in elements(obs):
        assert O.reobserve(e, v, s) == {'status': 'REOBSERVED', 'reason': None}
        assert O.reobserve(e.to_dict(), v, s)['status'] == 'REOBSERVED'    # also from the JSON form


def test_reobserve_agrees_across_an_edge_and_a_swap():
    p = fakes.FakePlacement({'花子': fakes.direct('PERSON'), '次郎': fakes.direct('PERSON')}, {'花子': ('次郎',)})
    reading = two_clause_reading()
    v = O.Viewpoint(O.AnchorText('seed', 'x', None, 0, reading), (O.Edge('cause'), O.FaceSwap('agent')))
    s = struct(p)
    obs = O.observe(v, s)
    assert sorted(e.cell.distance for e in elements(obs)) == [1, 2]
    for e in elements(obs):
        assert O.reobserve(e, v, s)['status'] == 'REOBSERVED'


@pytest.mark.parametrize('edit', [
    lambda c: c['moves'][0].__setitem__('to', '犬X'),
    lambda c: c['moves'][0].__setitem__('from', '次郎'),
    lambda c: c['moves'][0].__setitem__('neighbor_source', 'other/1'),
    lambda c: c['origin'].__setitem__('cross_index', 3),
    lambda c: c['moves'].append({'move': 'EDGE', 'relation': 'cause', 'reading': 'anchor', 'from': 0, 'to': 1, 'dir': 'forward'}),
    lambda c: c['moves'][0].__setitem__('move', 'JUMP'),
])
def test_reobserve_catches_a_coordinate_that_was_touched(edit):
    v = vp(direction='FACE_SWAP:agent')
    s = struct(fakes.people_placement())
    obs = O.observe(v, s)
    d = copy.deepcopy([e for e in elements(obs) if surfaces_of(e, 'agent') == ['犬']][0].to_dict())
    edit(d['coords'][0])
    got = O.reobserve(d, v, s)
    assert got['status'] == 'MISMATCH' and got['reason']


def test_reobserve_catches_a_changed_cross_and_a_changed_sentence():
    v = vp(direction='FACE_SWAP:agent')
    s = struct(fakes.people_placement())
    d = copy.deepcopy(elements(O.observe(v, s))[0].to_dict())
    bad = copy.deepcopy(d)
    bad['cross']['center']['tense'] = 'nonpast'
    assert O.reobserve(bad, v, s) == {'status': 'MISMATCH', 'reason': 'CROSS_BYTES_DIFFER'}
    other = copy.deepcopy(d)
    other['realization']['text'] = '犬は本を食べた。'
    assert O.reobserve(other, v, s)['status'] == 'MISMATCH'


def test_reobserve_needs_the_same_structure():
    v = O.Viewpoint(O.AnchorText('seed', 'x', None, 0, two_clause_reading()), (O.Edge('cause'),))
    s = struct()
    obs = O.observe(v, s)
    assert O.reobserve(elements(obs)[0], v, s)['status'] == 'REOBSERVED'
    cut = O.Viewpoint(O.AnchorText('seed', 'x', None, 0, fakes.read_out([fakes.clause('行く', {'agent': '太郎', 'place': '駅'})])), (O.Edge('cause'),))
    assert O.reobserve(elements(obs)[0], cut, s) == {'status': 'MISMATCH', 'reason': 'EDGE_NOT_IN_STRUCTURE'}


# ------------------------------------------------------------------ the field and the ledger (D8, D9)
def decided_ledger(*keys_and_kinds):
    led = SAL.MemoryLedger(clock=lambda: 'T')
    for kind, payload in keys_and_kinds:
        led.append({'kind': kind, 'payload': payload})
    return led


def first_run():
    return O.observe(vp(direction='FACE_SWAP:agent'), struct(fakes.people_placement()))


def keys_by_agent(obs):
    return {surfaces_of(e, 'agent')[0]: e.cell.key for e in elements(obs)}


def test_a_decision_makes_a_focus_and_a_later_observation_of_it_moves_it_on():
    k = keys_by_agent(first_run())
    s = struct(fakes.people_placement())
    v = vp(direction='FACE_SWAP:agent')
    led = SAL.MemoryLedger(clock=lambda: 'T')
    O.record_decision(led, k['次郎'])
    o1 = O.observe(v, s, ledger=led)
    assert o1.outcome == 'FOCUS' and o1.focus.cell_key == k['次郎']
    assert o1.to_dict()['salience_trace']['boundaries'][0]['decided_by'] == 'decided'
    O.record_turn(led, v, o1)
    o2 = O.observe(v, s, ledger=led)
    # 次郎 was observed: recency (iii) comes before the decision (iv). The two others (never observed) are tied -> TIE, not a pick
    assert o2.outcome == 'TIE' and k['次郎'] not in o2.focus.candidates and len(o2.focus.candidates) == 2
    d2 = o2.to_dict()['salience_trace']
    seqs = {c['cell_key']: c['ledger_seqs'] for c in d2['cells']}
    assert seqs[k['次郎']]['recency'] == [3]    # decision = ev:1, utterance = ev:2, observation = ev:3


def test_a_tie_turn_writes_no_observed_cell_and_the_second_turn_is_a_tie_again():
    s = struct(fakes.people_placement())
    v = vp(direction='FACE_SWAP:agent')
    led = SAL.MemoryLedger(clock=lambda: 'T')
    o1 = O.observe(v, s, ledger=led)
    ids = O.record_turn(led, v, o1)
    assert ids == ['ev:1', 'ev:2']
    evs = list(led.events())
    assert [e['kind'] for e in evs] == ['utterance', 'observation']
    assert evs[0]['payload'] == {'text': GIVE, 'anchor': 'seed'}
    p = evs[1]['payload']
    assert p['outcome'] == 'TIE' and 'observed_cell' not in p and len(p['tie_cells']) == 3 and p['state_seq'] == 0
    assert p['viewpoint']['direction'] == [{'move': 'FACE_SWAP', 'role': 'agent'}] and len(p['output_sha256']) == 64
    o2 = O.observe(v, s, ledger=led)
    assert o2.outcome == 'TIE' and o2.focus == o1.focus


def test_a_focus_turn_records_the_observed_cell():
    s = struct(fakes.people_placement())
    v = vp(direction='FACE_SWAP:agent', range_=0)
    led = SAL.MemoryLedger(clock=lambda: 'T')
    o = O.observe(v, s, ledger=led)
    O.record_turn(led, v, o)
    assert list(led.events())[1]['payload']['observed_cell'] == o.anchor.cell.key and list(led.events())[1]['payload']['outcome'] == 'FOCUS'


def test_a_record_anchor_writes_only_an_observation_and_no_utterance():
    s = struct(items=[{'id': 's1', 'reading': fakes.read_out([fakes.clause('行く', {'agent': '太郎'})])}])
    v = O.Viewpoint(O.AnchorRecord('s1'))
    led = SAL.MemoryLedger(clock=lambda: 'T')
    ids = O.record_turn(led, v, O.observe(v, s, ledger=led))
    assert ids == ['ev:1'] and list(led.events())[0]['kind'] == 'observation'


def test_no_anchor_and_no_move_licensed_are_recorded_as_outcomes():
    led = SAL.MemoryLedger(clock=lambda: 'T')
    v = vp('こんにちは。')
    O.record_turn(led, v, O.observe(v, struct(), ledger=led))
    v2 = vp(direction='FACE_SWAP:agent')
    O.record_turn(led, v2, O.observe(v2, struct(), ledger=led))
    outcomes = [e['payload']['outcome'] for e in led.events() if e['kind'] == 'observation']
    assert outcomes == ['NO_ANCHOR', 'NO_MOVE_LICENSED']
    assert all('observed_cell' not in e['payload'] for e in led.events())


def test_utterance_stages_move_the_focus_and_the_trace_names_the_ledger_line():
    k = keys_by_agent(first_run())
    s = struct(fakes.people_placement())
    v = vp(direction='FACE_SWAP:agent')
    led = decided_ledger(('utterance', {'text': '犬の話をしよう', 'anchor': 'question'}))
    o = O.observe(v, s, ledger=led)
    assert o.outcome == 'FOCUS' and o.focus.cell_key == k['犬']
    trace = o.to_dict()['salience_trace']
    assert trace['boundaries'][0]['decided_by'] == 'utter_verbatim'
    assert {c['cell_key']: c for c in trace['cells']}[k['犬']]['ledger_seqs']['utter_verbatim'] == [1]


# ------------------------------------------------------------------ replay (O1)
def test_replay_gives_the_same_output_from_the_ledger_before_the_turn():
    s = struct(fakes.people_placement())
    v = vp(direction='FACE_SWAP:agent')
    k = keys_by_agent(first_run())
    led = SAL.MemoryLedger(clock=lambda: 'T')
    O.record_decision(led, k['次郎'])
    for _ in range(3):
        o = O.observe(v, s, ledger=led)
        O.record_turn(led, v, o)
    evs = list(led.events())
    obs_events = [e for e in evs if e['kind'] == 'observation']
    assert len(obs_events) == 3
    for ev in obs_events:
        assert O.replay(evs, ev, s) is True
    # with a later line included the field changes: the replay of the first turn must NOT use it
    tampered = copy.deepcopy(obs_events[0])
    tampered['payload']['output_sha256'] = '0' * 64
    assert O.replay(evs, tampered, s) is False


def test_replay_from_a_flat_state():
    s = struct(fakes.people_placement())
    v = vp(direction='FACE_SWAP:agent')
    o = O.observe(v, s)
    led = SAL.MemoryLedger(clock=lambda: 'T')
    O.record_turn(led, v, o)
    ev = list(led.events())[-1]
    assert ev['payload']['viewpoint']['state'] == {'kind': 'FLAT'} and O.replay(list(led.events()), ev, s) is True


def test_output_is_byte_identical_for_the_same_inputs():
    s = struct(fakes.people_placement())
    v = vp(direction='FACE_SWAP:agent')
    assert O.to_json(O.observe(v, s)) == O.to_json(O.observe(v, struct(fakes.people_placement())))


def test_output_has_no_time_and_no_environment_value():
    text = O.to_json(first_run())
    assert '"ts"' not in text and '"seq"' not in text


def test_counts_name_zero_reasons_too():
    c = O.observe(vp(direction='FACE_SWAP:agent'), struct()).to_dict()['counts']
    assert set(c['moves']['FACE_SWAP']['cells_unlicensed']) == set(O.FACE_CELL_REASONS)
    assert set(c['moves']['FACE_SWAP']['candidates_unlicensed']) == set(O.FACE_CANDIDATE_REASONS)
    assert set(c['occupancy']) == set(O.OCCUPANCY_STATES) and set(c['claims']) == set(O.CLAIMS)


def test_counts_list_every_realization_refusal_reason_with_zeros_in_a_fixed_order():
    from verantyx import semantic_realize
    c = O.observe(vp(direction='FACE_SWAP:agent'), struct(fakes.people_placement())).to_dict()['counts']['realization']
    expect = sorted(semantic_realize.REFUSAL_REASONS - set(O.REFUSAL_NOT_ON_THIS_PATH))
    assert list(c['refused']) == expect and all(v == 0 for v in c['refused'].values()) and c['realized'] == 4
    # the two reasons that are left out belong to the answer / source-view realizers; if the realizer's list grows, this fails and a person decides
    assert set(O.REFUSAL_NOT_ON_THIS_PATH) <= semantic_realize.REFUSAL_REASONS and len(expect) + len(O.REFUSAL_NOT_ON_THIS_PATH) == len(semantic_realize.REFUSAL_REASONS)
    assert 'ANSWER' not in json.dumps(c)
    # an English cross cannot be said: that reason (and only that one) is counted
    en = O.observe(vp('Taro gave Hanako a book.'), struct()).to_dict()['counts']['realization']
    assert list(en['refused']) == expect
    assert en['refused']['NOT_REALIZABLE'] == 1 and sum(en['refused'].values()) == 1 and en['realized'] == 0


def test_a_cell_with_no_filler_is_not_searched_in_the_index_and_is_not_called_unoccupied(tmp_path):
    # decision E21: no surface to look up -> the index was never asked -> UNKNOWN_QUERY_NOT_SEARCHED, never UNOCCUPIED
    idx = make_index(tmp_path, ['次郎は花子に本をあげた。'])
    spec = O.IndexSpec(idx, ('pro',))
    empty = O.Viewpoint(O.AnchorText('seed', 'x', None, None, fakes.read_out([fakes.clause('あげる', {})])))
    el = O.observe(empty, struct(index=spec)).to_dict()['anchor']
    index_source = el['occupancy'][1]
    assert index_source['source'] == 'index:pro' and index_source['state'] == 'UNKNOWN_QUERY_NOT_SEARCHED'
    assert index_source['detail']['searches'] == [] and index_source['detail']['rows_read'] == 0
    # the reader called directly, as the structure side says UNOCCUPIED: the verdict is still not UNOCCUPIED
    got = struct(index=spec).index_reader().occupancy('cell:none', [], 'pro')
    assert got.state == 'UNKNOWN_QUERY_NOT_SEARCHED'
    occ = O.Occupancy((O.OccupancySource('structure', 'UNOCCUPIED', None, {}), got))
    assert occ.occupied == 'UNKNOWN_QUERY_NOT_SEARCHED'
    # a cell that has a filler and is searched keeps the old states
    searched = struct(index=spec).index_reader().occupancy('cell:none', ['次郎'], 'pro')
    assert searched.state == 'UNOCCUPIED' and searched.detail['searches'][0]['surface'] == '次郎'


def test_an_utterance_equal_to_the_anchor_sentence_is_skipped_by_the_field_and_counted():
    k = keys_by_agent(first_run())
    s = struct(fakes.people_placement())
    v = vp(direction='FACE_SWAP:agent')
    led = decided_ledger(('utterance', {'text': '犬の話をしよう', 'anchor': 'question'}), ('utterance', {'text': GIVE, 'anchor': 'question'}))
    o = O.observe(v, s, ledger=led)
    trace = o.to_dict()['salience_trace']
    assert o.outcome == 'FOCUS' and o.focus.cell_key == k['犬']                       # U is the line before the anchor sentence
    assert trace['utterance'] == {'used_seq': 1, 'skipped_same_as_anchor': [2]}
    assert {c['cell_key']: c for c in trace['cells']}[k['犬']]['ledger_seqs']['utter_verbatim'] == [1]
    only = O.observe(v, s, ledger=decided_ledger(('utterance', {'text': GIVE, 'anchor': 'question'})))
    assert only.outcome == 'TIE' and only.to_dict()['salience_trace']['utterance'] == {'used_seq': None, 'skipped_same_as_anchor': [1]}


def test_for_a_record_anchor_the_structure_sentence_is_the_anchor_sentence():
    items = [{'id': 's1', 'text': GIVE, 'reading': fakes.read_out([fakes.clause('あげる', {'agent': '太郎', 'patient': '本', 'recipient': '花子'})])}]
    s = struct(fakes.people_placement(), items)
    v = O.Viewpoint(O.AnchorRecord('s1'), O.parse_direction('FACE_SWAP:agent'))
    led = decided_ledger(('utterance', {'text': '犬の話をしよう', 'anchor': 'question'}), ('utterance', {'text': GIVE, 'anchor': 'question'}))
    t = O.observe(v, s, ledger=led).to_dict()['salience_trace']
    assert t['utterance'] == {'used_seq': 1, 'skipped_same_as_anchor': [2]}
    # a structure sentence without a text has no anchor sentence to skip
    nt = struct(fakes.people_placement(), [{'id': 's1', 'reading': items[0]['reading']}])
    assert O.observe(v, nt, ledger=led).to_dict()['salience_trace']['utterance'] == {'used_seq': 2, 'skipped_same_as_anchor': []}


# ------------------------------------------------------------------ the placement file (D14)
def test_file_placement_answers_lookup_and_neighbors_and_names_unknown(tmp_path):
    f = tmp_path / 'p.json'
    f.write_text(json.dumps({'lemmas': {'太郎': {'state': 'DECIDED', 'origin': 'direct', 'types': ['PERSON']}},
                             'neighbors': {'太郎': ['次郎', '次郎', '花子'], '空': []}}, ensure_ascii=False), encoding='utf-8')
    fp = O.FilePlacement.from_path(f)
    assert fp.id.startswith('file:') and len(fp.id) == 5 + 64
    assert fp.lookup('太郎').types == ('PERSON',) and fp.lookup('誰').state == 'UNKNOWN'
    assert fp.neighbors('太郎') == O.NeighborResult('FOUND', ('次郎', '花子'), {'file': True})
    assert fp.neighbors('空').state == 'NO_NEIGHBORS' and fp.neighbors('誰').state == 'UNKNOWN'


@pytest.mark.parametrize('content', ['[]', '{', '{"lemmas": []}', '{"lemmas": {"a": {}}}', '{"zzz": 1}', '{"neighbors": {"a": "b"}}'])
def test_broken_placement_file_is_bad_arguments(tmp_path, content):
    f = tmp_path / 'p.json'
    f.write_text(content, encoding='utf-8')
    with pytest.raises(ValueError, match='BAD_ARGUMENTS'):
        O.FilePlacement.from_path(f)


def test_structure_file_rules(tmp_path):
    f = tmp_path / 's.jsonl'
    f.write_text(json.dumps({'id': 'a', 'text': GIVE}, ensure_ascii=False) + '\n\n' + json.dumps({'id': 'b', 'text': 'こんにちは。', 'tags': ['x']}, ensure_ascii=False) + '\n', encoding='utf-8')
    s = O.Structure.from_jsonl(f)
    info = s.info()
    assert info['sentences'] == 2 and info['blank_lines_skipped'] == 1 and info['by_status']['CROSSED'] == 1 and info['by_status']['ABSTAINED'] == 1
    assert len(info['file_sha256']) == 64
    for bad in ('{"id": "a"}\n', 'nope\n', '{"id": "anchor", "text": "x"}\n', '{"id":"a","text":"a"}\n{"id":"a","text":"b"}\n'):
        f.write_text(bad, encoding='utf-8')
        with pytest.raises(ValueError, match='BAD_ARGUMENTS'):
            O.Structure.from_jsonl(f)


# ------------------------------------------------------------------ the entry function
def test_run_entry_arguments(tmp_path):
    ok = O.run_entry(anchor_text=GIVE, no_index=True)
    assert ok.exit_code == 0 and json.loads(ok.stdout)['schema'] == 'verantyx.observe/1'
    for kw in ({}, {'anchor_text': 'x', 'anchor_record': 'y'}, {'anchor_text': 'x', 'direction': 'FACE_SWAP'},
               {'anchor_text': 'x', 'direction': 'EDGE:because'}, {'anchor_text': 'x', 'direction': 'FACE_SWAP:agent', 'range_': 5},
               {'anchor_text': 'x', 'anchor_kind': 'story'}, {'anchor_text': 'x', 'no_index': True, 'index_root': str(tmp_path)},
               {'anchor_text': 'x', 'index_families': ('nope',)}, {'anchor_text': 'x', 'structure_path': str(tmp_path / 'absent.jsonl')},
               {'anchor_text': 'x', 'placement_path': str(tmp_path / 'absent.json')}):
        got = O.run_entry(**kw)
        assert got.exit_code == 2 and got.stdout is None and got.error['error']['type'] == 'BAD_ARGUMENTS', kw


def test_run_entry_ledger_roundtrip(tmp_path):
    led = tmp_path / 'l.jsonl'
    a = O.run_entry(anchor_text=GIVE, no_index=True, ledger_path=str(led))
    assert a.exit_code == 0 and len(SAL.load_jsonl(led)) == 2
    b = O.run_entry(anchor_text=GIVE, no_index=True, ledger_path=str(led))
    assert len(SAL.load_jsonl(led)) == 4
    assert json.loads(b.stdout)['viewpoint']['state'] == {'kind': 'LEDGER', 'events': 2, 'last_seq': 2}
    led.write_bytes(b'{broken\n')
    bad = O.run_entry(anchor_text=GIVE, no_index=True, ledger_path=str(led))
    assert bad.exit_code == 3 and bad.error['error']['type'] == 'LEDGER_INVALID' and led.read_bytes() == b'{broken\n'
