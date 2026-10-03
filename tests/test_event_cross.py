"""W3-b: the event cross (verantyx/event_cross.py), on reader outputs WRITTEN BY HAND in the shape of docs/READING_CONVENTIONS.md section 1
(the reading entry itself is not called here), with fake placements (tests/event_cross/fakes.py).
"""
import copy
import json
import re
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent / 'event_cross'))

import fakes    # noqa: E402
from verantyx import event_cross as E    # noqa: E402

SCHEMA = 'verantyx.semantic_read/1'


def clause(predicate='渡す', roles=None, polarity='+', tense='past', modality=None, voice='active', **extra):
    c = {'predicate': predicate, 'roles': {} if roles is None else roles, 'polarity': polarity, 'tense': tense, 'modality': modality, 'voice': voice}
    c.update(extra)
    return c


def reading(clauses, relations=(), metas=None):
    metas = metas if metas is not None else [{'rule': 'hand', 'span': [i, i + 1]} for i in range(len(clauses))]
    return {'schema': SCHEMA, 'lang': 'ja', 'readable': True, 'clauses': clauses, 'relations': list(relations),
            'abstain': None, 'unsupported': [], 'clause_meta': metas}


def refusal(kind, reasons):
    return {'schema': SCHEMA, 'lang': 'ja', 'readable': False, 'clauses': [], 'relations': [],
            'abstain': {'kind': kind, 'reasons': reasons}, 'unsupported': [], 'clause_meta': []}


GIVE = reading([clause('渡す', {'patient': '地図', 'recipient': '生徒', 'agent': '先生'})])


# ---------------------------------------------------------------------------------------------------------------------------------
# structure
# ---------------------------------------------------------------------------------------------------------------------------------
def test_single_clause_one_cross_center_and_arms_in_convention_order():
    r = E.build_crosses(GIVE)
    assert r.status == 'CROSSED' and len(r.crosses) == 1
    x = r.crosses[0]
    assert x.index == 0
    assert dict(x.center) == {'predicate': '渡す', 'polarity': '+', 'tense': 'past', 'modality': None, 'voice': 'active'}
    assert {k: a.fillers[0].surface for k, a in x.arms.items()} == {'agent': '先生', 'patient': '地図', 'recipient': '生徒'}
    assert list(x.arms) == ['agent', 'patient', 'recipient']    # the order of ROLE_NAMES, not the order of the input (patient first)
    assert all(a.kind == 'FILLER' and len(a.fillers) == 1 for a in x.arms.values())
    assert all(f.head == f.surface and f.head_basis == 'surface' for a in x.arms.values() for f in a.fillers)
    assert x.provenance == {'source_schema': SCHEMA, 'clause_index': 0, 'rule': 'hand', 'span': [0, 1]}


def test_three_clauses_relations_are_copied_exactly():
    rels = [{'type': 'relative', 'from': 0, 'to': 1}, {'type': 'sequence', 'from': 1, 'to': 2}, {'type': 'quote', 'from': 2, 'to': 0}]
    src = reading([clause('食べる', {'agent': '子ども', 'patient': 'りんご'}), clause('洗う', {'agent': '母'}), clause('言う', {'agent': '父'})], rels,
                  [{'rule': 'a', 'span': [0, 3]}, {'rule': 'b', 'span': [3, 5]}, {'rule': 'c', 'span': [5, 9]}])
    r = E.build_crosses(src)
    assert len(r.crosses) == 3
    assert [c.index for c in r.crosses] == [0, 1, 2]
    assert [c.center['predicate'] for c in r.crosses] == ['食べる', '洗う', '言う']
    assert [dict(x) for x in r.relations] == rels                       # same count, same order, same from / to
    assert [c.provenance['rule'] for c in r.crosses] == ['a', 'b', 'c']
    assert [c.provenance['span'] for c in r.crosses] == [[0, 3], [3, 5], [5, 9]]
    d = r.to_dict()
    assert d['relations'] == rels and len(d['relations']) == len(src['relations'])


def test_a_clause_without_relations_adds_none():
    two = reading([clause('食べる', {'agent': '子ども'}), clause('洗う', {'agent': '母'})])
    assert E.build_crosses(two).relations == ()    # two clauses and no relation in the reader output: none is invented


def test_quantifier_goes_to_the_filler_flags_and_stays_in_the_center():
    q = {'agent': 'universal', 'event': 'exactly:3'}
    r = E.build_crosses(reading([clause('押す', {'agent': '係員', 'patient': 'ボタン'}, quantifiers=q, scope=['agent', 'event'], comparison=None)]))
    x = r.crosses[0]
    assert x.center['quantifiers'] == q and x.center['scope'] == ['agent', 'event']
    assert dict(x.arms['agent'].fillers[0].flags) == {'quantifier': 'universal'}
    assert dict(x.arms['patient'].fillers[0].flags) == {}
    assert list(x.center) == ['predicate', 'polarity', 'tense', 'modality', 'voice', 'quantifiers', 'scope', 'comparison']


def test_comparison_key_is_kept_in_the_center():
    r = E.build_crosses(reading([clause('高い', {'entity': '弟', 'standard': '兄'}, tense='nonpast', comparison='comparative')]))
    assert r.crosses[0].center['comparison'] == 'comparative'


# ---------------------------------------------------------------------------------------------------------------------------------
# ties and refusals
# ---------------------------------------------------------------------------------------------------------------------------------
def test_arm_tie_stays_split_and_is_not_checked():
    src = reading([clause('行く', {'agent': ['学生', '先生'], 'place': '駅'})])
    lk = fakes.MappingLookup({'学生': fakes.direct('PERSON'), '先生': fakes.direct('PERSON'), '駅': fakes.direct('PLACE')})
    r = E.build_crosses(src, lk)
    arm = r.crosses[0].arms['agent']
    assert arm.kind == 'ARM_TIE'
    assert [f.surface for f in arm.fillers] == ['学生', '先生']      # the order of the input, none chosen
    assert (arm.agreement.verdict, arm.agreement.reason) == ('NOT_CHECKED', 'ARM_TIE')
    assert r.crosses[0].arms['place'].agreement.verdict == 'AGREE'
    assert r.counts['arm_ties'] == 1


def test_singleton_array_and_empty_array_are_rejected():
    one = E.build_crosses(reading([clause('行く', {'agent': ['学生']})]))
    assert one.status == 'INPUT_REJECTED' and one.crosses == () and one.abstain['reasons'] == ['ROLE_VALUE_SINGLETON_ARRAY:agent']
    zero = E.build_crosses(reading([clause('行く', {'agent': []})]))
    assert zero.status == 'INPUT_REJECTED' and zero.abstain['reasons'] == ['EMPTY_ROLE_VALUE:agent']
    bad = E.build_crosses(reading([clause('行く', {'agent': ['学生', 3]})]))
    assert bad.abstain['reasons'] == ['ROLE_VALUE_NOT_STRING:agent']


@pytest.mark.parametrize('kind,reasons', [('unreadable_input', ['NO_PREDICATE']), ('not_supported', ['UNDETERMINED_VOICE:x'])])
def test_unreadable_is_abstained_with_the_abstain_copied(kind, reasons):
    src = refusal(kind, reasons)
    r = E.build_crosses(src)
    assert r.status == 'ABSTAINED' and r.crosses == () and r.relations == ()
    assert r.abstain == src['abstain'] and r.abstain['kind'] == kind
    assert r.to_dict()['abstain'] == src['abstain']


@pytest.mark.parametrize('mutate,reason', [
    (lambda o: o['clauses'][0]['roles'].update(location='駅'), 'ROLE_NOT_IN_CONVENTION:location'),
    (lambda o: o['relations'].append({'type': 'because', 'from': 0, 'to': 1}), 'RELATION_TYPE_NOT_IN_CONVENTION:because'),
    (lambda o: o['relations'].append({'type': 'cause', 'from': 0, 'to': 5}), 'RELATION_INDEX_OUT_OF_RANGE'),
    (lambda o: o.update(schema='other/1'), 'BAD_SCHEMA'),
    (lambda o: o.pop('clause_meta'), 'MISSING_FIELD:clause_meta'),
    (lambda o: o.update(readable='yes'), 'READABLE_NOT_BOOL'),
    (lambda o: o['clauses'][0].update(extra_key=1), 'UNKNOWN_CLAUSE_KEY:extra_key'),
    (lambda o: o['clause_meta'].pop(), 'CLAUSE_META_LENGTH_MISMATCH'),
    (lambda o: o.update(clauses=[], clause_meta=[]), 'READABLE_WITHOUT_CLAUSES'),
    (lambda o: o['clauses'][0]['roles'].update(agent='  '), 'EMPTY_ROLE_VALUE:agent'),
    (lambda o: o['clauses'][0].pop('voice'), 'MISSING_FIELD:voice'),
])
def test_rejected_input_has_a_typed_reason_and_no_cross(mutate, reason):
    src = copy.deepcopy(GIVE)
    src['relations'] = []
    mutate(src)
    r = E.build_crosses(src)
    assert r.status == 'INPUT_REJECTED' and r.crosses == () and r.relations == ()
    assert reason in r.abstain['reasons'] and r.abstain['kind'] == 'input_rejected'


def test_role_outside_the_convention_is_not_moved_to_a_near_name():
    r = E.build_crosses(reading([clause('行く', {'location': '駅'})]))
    assert r.status == 'INPUT_REJECTED' and r.abstain['reasons'] == ['ROLE_NOT_IN_CONVENTION:location']    # no `place` arm was made from it


def test_reader_error_object_is_rejected_with_its_type():
    r = E.build_crosses({'error': {'type': 'EMPTY_TEXT', 'detail': 'x'}})
    assert r.status == 'INPUT_REJECTED' and r.abstain['reasons'] == ['READER_ERROR:EMPTY_TEXT']
    assert E.build_crosses('not a dict').abstain['reasons'] == ['NOT_A_MAPPING']


# ---------------------------------------------------------------------------------------------------------------------------------
# E3: the closed lists are read from the convention document
# ---------------------------------------------------------------------------------------------------------------------------------
CONV = (TREE / 'docs' / 'READING_CONVENTIONS.md').read_text(encoding='utf-8')


def _first_column(text, start, end):
    i = text.index(start); j = text.index(end, i + 1)
    return re.findall(r'^\| `([^`]+)` \|', text[i:j], flags=re.M)


def test_convention_role_names_equal_the_table_of_section_2_in_set_and_order():
    names = _first_column(CONV, '\n## 2. ', '\n## 3. ')
    assert len(names) == 20
    assert tuple(names) == E.ROLE_NAMES


def test_convention_relation_types_equal_the_table_of_section_1_2():
    types = _first_column(CONV, '\n### 1.2 ', '\n## 2. ')
    assert len(types) == 11
    assert tuple(types) == E.RELATION_TYPES


def test_convention_clause_keys_equal_the_table_of_section_1_1():
    keys = _first_column(CONV, '\n### 1.1 ', '\n### 1.2 ')
    assert tuple(keys) == E.CLAUSE_KEYS


def test_the_arms_of_a_cross_never_leave_the_role_list_even_with_every_role():
    roles = {name: 'x%d' % i for i, name in enumerate(reversed(E.ROLE_NAMES))}
    x = E.build_crosses(reading([clause('なる', roles)])).crosses[0]
    assert tuple(x.arms) == E.ROLE_NAMES
    assert set(x.arms) <= set(E.ROLE_NAMES)


# ---------------------------------------------------------------------------------------------------------------------------------
# E4: type agreement with fake placements
# ---------------------------------------------------------------------------------------------------------------------------------
def _agreement_of(role, value, place):
    src = reading([clause('する', {role: value})])
    lk = fakes.MappingLookup({value: place})
    r = E.build_crosses(src, lk)
    return r, r.crosses[0].arms[role].agreement


def test_agreement_direct_inside_the_table():
    r, ag = _agreement_of('agent', '先生', fakes.direct('PERSON'))
    assert (ag.verdict, ag.reason) == ('AGREE', None)
    assert ag.expected == ('ANIMAL', 'GROUP_ORG', 'PERSON') and ag.observed == ('PERSON',)


def test_agreement_direct_outside_the_table_is_disagree_and_the_role_does_not_change():
    r, ag = _agreement_of('agent', '機械', fakes.direct('ARTIFACT'))
    assert (ag.verdict, ag.reason) == ('DISAGREE', None)
    assert ag.expected == ('ANIMAL', 'GROUP_ORG', 'PERSON') and ag.observed == ('ARTIFACT',)
    assert list(r.crosses[0].arms) == ['agent'] and r.crosses[0].arms['agent'].fillers[0].surface == '機械'
    assert r.counts['agreement'] == {'AGREE': 0, 'DISAGREE': 1, 'NOT_CHECKED': 0}


@pytest.mark.parametrize('place,reason', [
    (fakes.estimated('proximity', 'PERSON'), 'ESTIMATED_NEAR'),
    (fakes.estimated('generated', 'PERSON'), 'ESTIMATED_GENERATED'),
    (fakes.bare('UNPLACED'), 'UNPLACED'),
    (fakes.bare('UNKNOWN'), 'UNKNOWN'),
    (fakes.bare('NO_PLACEMENT'), 'NO_PLACEMENT'),
    (fakes.direct('PERSON', 'PLACE'), 'MULTIPLE'),
    (fakes.estimated('proximity', 'PERSON', 'PLACE'), 'ESTIMATED_NEAR'),
])
def test_agreement_not_checked_with_its_own_reason(place, reason):
    r, ag = _agreement_of('agent', '先生', place)
    assert (ag.verdict, ag.reason, ag.expected, ag.observed) == ('NOT_CHECKED', reason, None, None)


def test_agreement_role_not_in_the_table():
    r, ag = _agreement_of('patient', '地図', fakes.direct('ARTIFACT'))
    assert (ag.verdict, ag.reason) == ('NOT_CHECKED', 'ROLE_NOT_IN_TABLE')


@pytest.mark.parametrize('bad', [
    fakes.PlaceResult(state='DECIDED', origin='direct', types=('PERSON', 'PLACE')),     # DECIDED with two types
    fakes.PlaceResult(state='MULTIPLE', origin='direct', types=('PERSON',)),            # MULTIPLE with one
    fakes.PlaceResult(state='UNKNOWN', origin=None, types=('PERSON',)),                 # a type on a state that has none
    fakes.PlaceResult(state='DECIDED', origin='estimated', estimate_basis=None, types=('PERSON',)),    # estimated without a basis
    fakes.PlaceResult(state='DECIDED', origin=None, types=('PERSON',)),                 # a type without an origin
    fakes.PlaceResult(state='SOMETHING', origin=None, types=()),
    {'state': 'DECIDED', 'top': ['PERSON']},                                            # not a PlaceResult at all
    None,
])
def test_agreement_invalid_lookup_result(bad):
    r = E.build_crosses(reading([clause('する', {'agent': '先生'})]), fakes.RawLookup(bad))
    arm = r.crosses[0].arms['agent']
    assert (arm.agreement.verdict, arm.agreement.reason) == ('NOT_CHECKED', 'LOOKUP_RESULT_INVALID')
    assert arm.fillers[0].place.source == 'INVALID' and arm.fillers[0].place.provenance['reason'] == 'LOOKUP_RESULT_INVALID'


def test_a_lookup_exception_is_not_swallowed():
    class Boom:
        id = 'boom'
        def lookup(self, lemma): raise RuntimeError('boom')
    with pytest.raises(RuntimeError):
        E.build_crosses(GIVE, Boom())


def test_every_role_and_every_case_keeps_roles_and_values_unchanged():
    cases = [fakes.direct('PERSON'), fakes.direct('ARTIFACT'), fakes.estimated('proximity', 'PLACE'), fakes.estimated('generated', 'TIME'),
             fakes.bare('UNPLACED'), fakes.bare('UNKNOWN'), fakes.bare('NO_PLACEMENT'), fakes.direct('PERSON', 'PLACE')]
    roles = {name: 'w_' + name for name in E.ROLE_NAMES}
    for place in cases:
        lk = fakes.MappingLookup({v: place for v in roles.values()})
        r = E.build_crosses(reading([clause('する', dict(roles))]), lk)
        arms = r.crosses[0].arms
        assert {k: a.fillers[0].surface for k, a in arms.items()} == roles      # the same role -> value pairs, whatever the verdict
        c = r.counts
        assert c['arms'] == len(roles) and sum(c['agreement'].values()) == len(roles)
        assert sum(c['not_checked_by_reason'].values()) == c['agreement']['NOT_CHECKED']
        assert list(c['not_checked_by_reason']) == list(E.NOT_CHECKED_REASONS)     # every reason is written, also with 0


def test_the_lookup_receives_only_the_head_of_the_filler():
    lk = fakes.MappingLookup({})
    E.build_crosses(GIVE, lk)
    assert sorted(lk.calls) == sorted([(('先生',), {}), (('地図',), {}), (('生徒',), {})])    # no role, no predicate, no keyword


def test_stub_lookup_says_no_placement_everywhere():
    s = E.StubLookup()
    p = s.lookup('先生')
    assert (p.state, p.origin, p.types, p.source) == ('NO_PLACEMENT', None, (), 'NO_PLACEMENT') and p.provenance == {'reason': 'STUB'}
    r = E.build_crosses(GIVE)
    assert r.lookup_id == 'stub-no-placement/1'
    for arm in r.crosses[0].arms.values():
        assert arm.fillers[0].place.source == 'NO_PLACEMENT'
        assert arm.agreement.reason in ('NO_PLACEMENT', 'ROLE_NOT_IN_TABLE')
    assert isinstance(s, E.PlacementLookup)


def test_place_result_source_names():
    assert fakes.direct('PERSON').source == 'direct'
    assert fakes.estimated('proximity', 'PERSON').source == 'estimated_near'
    assert fakes.estimated('generated', 'PERSON').source == 'estimated_generated'
    assert [fakes.bare(s).source for s in ('UNPLACED', 'UNKNOWN', 'NO_PLACEMENT')] == ['UNPLACED', 'UNKNOWN', 'NO_PLACEMENT']
    assert fakes.direct('PERSON', 'PLACE').types == ('PERSON', 'PLACE')      # alphabetical, written as a set (not a ranking)


def test_from_coarse_query_copies_the_documented_shape():
    d = {'term': '先生', 'namespace': 'N', 'state': 'DECIDED', 'origin': 'direct', 'estimate_basis': None, 'constructed': False,
         'top': ['PERSON'], 'candidates': [{'type': 'PERSON', 'axes': {'seed': 1}}], 'axes': {}, 'neighbors': [], 'seen_in_material': [],
         'context': {'role': None, 'predicate': None}, 'placement': {'path': '/p', 'content_sha256': 'abc', 'reason': None}}
    p = E.PlaceResult.from_coarse_query(d)
    assert (p.state, p.origin, p.estimate_basis, p.types, p.source) == ('DECIDED', 'direct', None, ('PERSON',), 'direct')
    assert p.provenance['placement']['content_sha256'] == 'abc' and p.provenance['constructed'] is False and p.invariant_problems() == []
    est = dict(d, state='MULTIPLE', origin='estimated', estimate_basis='generated', constructed=True, top=['PLACE', 'PERSON'])
    q = E.PlaceResult.from_coarse_query(est)
    assert q.types == ('PERSON', 'PLACE') and q.source == 'estimated_generated' and q.invariant_problems() == []
    none = {'term': 'x', 'namespace': None, 'state': 'NO_PLACEMENT', 'origin': None, 'estimate_basis': None, 'constructed': False, 'top': [],
            'placement': {'path': None, 'content_sha256': None, 'reason': 'UNSET'}}
    n = E.PlaceResult.from_coarse_query(none)
    assert (n.state, n.source, n.types) == ('NO_PLACEMENT', 'NO_PLACEMENT', ()) and n.provenance['placement']['reason'] == 'UNSET'
    with pytest.raises(ValueError):
        E.PlaceResult.from_coarse_query({'state': 'DECIDED'})
    # a different order of `top` gives the same placement (it is a set, not a ranking)
    assert E.PlaceResult.from_coarse_query(dict(est, top=['PERSON', 'PLACE'])) == q


# ---------------------------------------------------------------------------------------------------------------------------------
# determinism, no mutation, the registered table
# ---------------------------------------------------------------------------------------------------------------------------------
def test_to_dict_is_deterministic_and_the_input_is_not_changed():
    src = reading([clause('渡す', {'patient': '地図', 'agent': '先生'}, quantifiers={'agent': 'universal'}), clause('行く', {'agent': ['学生', '先生']})],
                  [{'type': 'sequence', 'from': 0, 'to': 1}])
    before = copy.deepcopy(src)
    lk = fakes.MappingLookup({'先生': fakes.direct('PERSON')})
    a = json.dumps(E.build_crosses(src, lk).to_dict(), ensure_ascii=False, sort_keys=False)
    b = json.dumps(E.build_crosses(src, lk).to_dict(), ensure_ascii=False, sort_keys=False)
    assert a == b and src == before
    out = E.attach_events(src, lk)
    assert src == before and list(out)[-1] == 'events' and {k: v for k, v in out.items() if k != 'events'} == before


def test_attach_events_keeps_the_order_of_the_reader_keys():
    out = E.attach_events(GIVE)
    assert list(out) == list(GIVE) + ['events']


def test_events_schema_and_count_keys():
    d = E.build_crosses(GIVE).to_dict()
    assert d['schema'] == 'verantyx.event_cross/1' and d['status'] == 'CROSSED' and d['abstain'] is None and d['lookup'] == {'id': 'stub-no-placement/1'}
    assert list(d['counts']) == ['crosses', 'arms', 'arm_ties', 'agreement', 'not_checked_by_reason']
    assert d['counts']['crosses'] == 1 and d['counts']['arms'] == 3
    ab = E.build_crosses(refusal('not_supported', ['X'])).to_dict()
    assert ab['status'] == 'ABSTAINED' and ab['crosses'] == [] and ab['counts']['crosses'] == 0


def test_registered_table_in_the_document_equals_expected_types():
    doc = (TREE / 'docs' / 'EVENT_CROSS.md').read_text(encoding='utf-8')
    i, j = doc.index('<!-- prereg:begin -->'), doc.index('<!-- prereg:end -->')
    rows = re.findall(r'^\| `([^`]+)` \| ((?:`[A-Z_]+` ?)+) \|', doc[i:j], flags=re.M)
    table = {role: frozenset(re.findall(r'`([A-Z_]+)`', types)) for role, types in rows}
    assert table == E.EXPECTED_TYPES
    assert re.search(r'EXPECTED_TYPES_VERSION = %s\b' % E.EXPECTED_TYPES_VERSION, doc[i:j])
    assert set(E.EXPECTED_TYPES) <= set(E.ROLE_NAMES)
    assert all(t in E.NOUN_TYPE_IDS for ts in E.EXPECTED_TYPES.values() for t in ts)


def test_module_level_imports_are_the_standard_library_only():
    import ast
    tree = ast.parse((TREE / 'verantyx' / 'event_cross.py').read_text(encoding='utf-8'))
    mods = set()
    for node in tree.body:
        if isinstance(node, ast.Import): mods |= {a.name.split('.')[0] for a in node.names}
        if isinstance(node, ast.ImportFrom): mods.add((node.module or '').split('.')[0] + ('<relative>' if node.level else ''))
    assert mods <= {'__future__', 'copy', 'dataclasses', 'typing'}, mods
