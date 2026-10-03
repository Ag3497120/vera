"""W3-b2: the event cross gets `AGREE_ALL_CANDIDATES` (a split placement whose every type the role expects), its counts get a last key only when such an arm exists, and the
entry's new clause key `role_flags` is accepted and written to the `flags` of the filler (`flags.determiner`). The three changes were registered in docs/EVENT_CROSS.md (the
change record) before this file was written. The expectations of tests/test_event_cross*.py are not changed.
"""
import copy
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent


def _load_by_path(name, path):
    """Load a helper module by its path under a unique name (sys.path is NOT changed: see the note of tests/test_semantic_read_w3b1_events.py)."""
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fakes = _load_by_path('w3b2_event_cross_fakes', TREE / 'tests' / 'event_cross' / 'fakes.py')
W2F = _load_by_path('w3b2_fakes_in_events_test', TREE / 'tests' / 'reading_soundness' / 'w3b2_fakes.py')

from verantyx import event_cross as EC    # noqa: E402
from verantyx import semantic_read as SR    # noqa: E402

BASE_COMMIT = '3b31258'


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)


def clause(**extra):
    c = {'predicate': '歩く', 'roles': {'agent': '家族', 'goal': '庭'}, 'polarity': '+', 'tense': 'past', 'modality': None, 'voice': 'active'}
    c.update(extra)
    return c


def reading(c):
    return {'schema': EC.SOURCE_SCHEMA, 'lang': 'ja', 'readable': True, 'clauses': [c], 'relations': [], 'abstain': None, 'unsupported': [],
            'clause_meta': [{'rule': 'frame', 'span': [3, 5]}]}


def cross(c, mapping):
    return EC.build_crosses(reading(c), fakes.MappingLookup(mapping))


# ---------------------------------------------------------------------------------------------------------------------------------
# AGREE_ALL_CANDIDATES
# ---------------------------------------------------------------------------------------------------------------------------------
def test_a_split_placement_whose_every_type_the_role_expects_is_agree_all_candidates():
    r = cross(clause(), {'家族': fakes.direct('PERSON', 'GROUP_ORG')})
    ag = r.crosses[0].arms['agent'].agreement
    assert (ag.verdict, ag.reason) == ('AGREE_ALL_CANDIDATES', None)
    assert ag.expected == ('ANIMAL', 'GROUP_ORG', 'PERSON') and ag.observed == ('GROUP_ORG', 'PERSON')


def test_a_split_placement_with_one_type_the_role_does_not_expect_is_still_not_checked_multiple():
    for types in (('PERSON', 'ABSTRACT'), ('PLACE', 'GROUP_ORG'), ('TIME', 'PERSON', 'ANIMAL')):
        ag = cross(clause(), {'家族': fakes.direct(*types)}).crosses[0].arms['agent'].agreement
        assert (ag.verdict, ag.reason) == ('NOT_CHECKED', 'MULTIPLE'), types


def test_an_estimated_split_is_not_agree_all_candidates_even_when_every_type_fits():
    ag = cross(clause(), {'家族': fakes.estimated('proximity', 'PERSON', 'GROUP_ORG')}).crosses[0].arms['agent'].agreement
    assert (ag.verdict, ag.reason) == ('NOT_CHECKED', 'ESTIMATED_NEAR')
    ag = cross(clause(), {'家族': fakes.estimated('generated', 'PERSON', 'GROUP_ORG')}).crosses[0].arms['agent'].agreement
    assert (ag.verdict, ag.reason) == ('NOT_CHECKED', 'ESTIMATED_GENERATED')


def test_the_rules_before_the_split_rule_still_come_first():
    # a role that is not in the table, an arm that is a tie, a broken lookup answer: none of them is an agree_all_candidates
    r = cross(clause(roles={'agent': '家族', 'patient': '手紙'}), {'家族': fakes.direct('PERSON', 'GROUP_ORG'), '手紙': fakes.direct('PERSON', 'GROUP_ORG')})
    assert r.crosses[0].arms['patient'].agreement.reason == 'ROLE_NOT_IN_TABLE'
    r = cross(clause(roles={'agent': ['家族', '一家']}), {'家族': fakes.direct('PERSON', 'GROUP_ORG'), '一家': fakes.direct('PERSON', 'GROUP_ORG')})
    assert r.crosses[0].arms['agent'].agreement.reason == 'ARM_TIE'
    assert EC._agreement('agent', 'FILLER', 'not a place result').reason == 'LOOKUP_RESULT_INVALID'


def test_the_split_rule_is_decided_by_the_set_of_types_not_by_their_order_and_never_changes_the_arm():
    r = cross(clause(), {'家族': EC.PlaceResult(state='MULTIPLE', origin='direct', types=('PERSON', 'GROUP_ORG'))})
    assert r.crosses[0].arms['agent'].agreement.verdict == 'AGREE_ALL_CANDIDATES'
    assert r.crosses[0].arms['agent'].fillers[0].surface == '家族' and r.crosses[0].center['predicate'] == '歩く'


# ---------------------------------------------------------------------------------------------------------------------------------
# the counts: the form does not change unless the new value occurs
# ---------------------------------------------------------------------------------------------------------------------------------
def test_verdicts_and_the_entry_keys_are_what_they_were_and_the_extra_verdict_is_apart():
    assert EC.VERDICTS == ('AGREE', 'DISAGREE', 'NOT_CHECKED')
    assert EC.EXTRA_VERDICTS == ('AGREE_ALL_CANDIDATES',)
    assert EC.ENTRY_BASIS_KEYS == ('predicate_basis', 'role_basis')
    assert EC.ENTRY_FLAG_KEYS == ('role_flags',)


def test_counts_without_the_new_verdict_are_the_same_dict_as_before():
    r = cross(clause(roles={'agent': '兄', 'goal': '庭'}), {'兄': fakes.direct('PERSON'), '庭': fakes.direct('PLACE')})
    c = r.counts
    assert list(c) == ['crosses', 'arms', 'arm_ties', 'agreement', 'not_checked_by_reason']
    assert c['agreement'] == {'AGREE': 1, 'DISAGREE': 0, 'NOT_CHECKED': 1} and list(c['agreement']) == ['AGREE', 'DISAGREE', 'NOT_CHECKED']
    # the serialised cross of a reading without it has no such key anywhere
    assert 'AGREE_ALL_CANDIDATES' not in json.dumps(r.to_dict())


def test_counts_with_the_new_verdict_get_it_as_the_last_key_of_agreement_only():
    r = cross(clause(), {'家族': fakes.direct('PERSON', 'GROUP_ORG'), '庭': fakes.direct('PLACE')})
    c = r.counts
    assert list(c) == ['crosses', 'arms', 'arm_ties', 'agreement', 'not_checked_by_reason']
    assert list(c['agreement']) == ['AGREE', 'DISAGREE', 'NOT_CHECKED', 'AGREE_ALL_CANDIDATES']
    assert c['agreement'] == {'AGREE': 0, 'DISAGREE': 0, 'NOT_CHECKED': 1, 'AGREE_ALL_CANDIDATES': 1}
    assert c['arms'] == 2 and sum(c['not_checked_by_reason'].values()) == 1
    d = r.to_dict()
    assert d['counts'] == c and d['crosses'][0]['arms']['agent']['agreement']['verdict'] == 'AGREE_ALL_CANDIDATES'


def test_a_clause_set_that_mixes_the_verdicts_counts_each_once():
    r = cross(clause(roles={'agent': '家族', 'goal': '庭'}), {'家族': fakes.direct('PERSON', 'GROUP_ORG'), '庭': fakes.direct('TIME')})
    # goal is not in the table: NOT_CHECKED(ROLE_NOT_IN_TABLE); agent: AGREE_ALL_CANDIDATES
    assert r.counts['agreement'] == {'AGREE': 0, 'DISAGREE': 0, 'NOT_CHECKED': 1, 'AGREE_ALL_CANDIDATES': 1}


# ---------------------------------------------------------------------------------------------------------------------------------
# role_flags: accepted, checked, copied to the flags of the filler
# ---------------------------------------------------------------------------------------------------------------------------------
def test_role_flags_are_accepted_and_written_to_the_flags_of_the_filler_of_that_role_only():
    c = clause(roles={'agent': '母', 'place': '部屋'}, role_basis={'place': 'placement_direct:PLACE'}, role_flags={'place': {'determiner': 'この'}})
    r = cross(c, {'母': fakes.direct('PERSON'), '部屋': fakes.direct('PLACE')})
    assert r.status == 'CROSSED'
    arms = r.crosses[0].arms
    assert dict(arms['place'].fillers[0].flags) == {'determiner': 'この'} and dict(arms['agent'].fillers[0].flags) == {}
    assert 'role_flags' not in r.crosses[0].center and 'role_flags' not in json.dumps(r.crosses[0].center)


def test_the_flags_of_a_filler_that_has_a_quantifier_hold_both():
    c = clause(roles={'agent': '母', 'place': '部屋'}, quantifiers={'place': 'all'}, role_flags={'place': {'determiner': 'その'}})
    r = cross(c, {})
    assert dict(r.crosses[0].arms['place'].fillers[0].flags) == {'quantifier': 'all', 'determiner': 'その'}


@pytest.mark.parametrize('bad', [
    {'place': {}}, {'place': {'determiner': ''}}, {'place': {'determiner': 3}}, {'place': {'determiner': 'この', 'other': 'x'}},
    {'time': {'determiner': 'この'}},          # a role the clause does not have
    {}, [], 'この', {'place': 'この'}, None,
])
def test_a_role_flags_of_a_bad_shape_is_refused_with_its_own_reason(bad):
    c = clause(roles={'agent': '母', 'place': '部屋'}, role_flags=bad)
    r = cross(c, {})
    assert r.status == 'INPUT_REJECTED' and 'ENTRY_FLAGS_NOT_WELL_FORMED' in r.abstain['reasons']


def test_a_key_that_is_not_registered_is_still_refused_and_the_registered_ones_are_not_widened():
    for key in ('role_flag', 'flags', 'determiner'):
        r = cross(clause(**{key: {'place': {'determiner': 'この'}}}), {})
        assert r.status == 'INPUT_REJECTED' and 'UNKNOWN_CLAUSE_KEY:%s' % key in r.abstain['reasons']
    assert EC.CLAUSE_KEYS == EC.CLAUSE_REQUIRED_KEYS + EC.CLAUSE_OPTIONAL_KEYS and 'role_flags' not in EC.CLAUSE_KEYS


def test_the_provenance_of_the_cross_still_copies_only_the_two_basis_keys():
    c = clause(role_basis={'agent': 'placement_all_candidates:GROUP_ORG+PERSON'}, role_flags={'goal': {'determiner': 'この'}})
    r = cross(c, {'家族': fakes.direct('PERSON', 'GROUP_ORG')})
    prov = r.crosses[0].provenance
    assert prov['role_basis'] == {'agent': 'placement_all_candidates:GROUP_ORG+PERSON'} and 'role_flags' not in prov


# ---------------------------------------------------------------------------------------------------------------------------------
# the entry's output goes through the cross (with the fixture of the placement r6 as the lookup)
# ---------------------------------------------------------------------------------------------------------------------------------
class FixtureLookup:
    id = 'fixture-lookup-w3b2'

    def __init__(self):
        self.q = W2F.FixtureQuery()

    def lookup(self, term):
        return EC.PlaceResult.from_coarse_query(self.q.query(term))


def test_the_entry_output_with_a_demonstrative_and_a_split_agent_is_crossed_and_counted():
    out = SR.read('家族が庭へ走った。', placement=W2F.FixtureQuery())
    assert out['readable'] is True and out['clauses'][0]['role_basis']['agent'].startswith('placement_all_candidates:')
    r = EC.build_crosses(out, FixtureLookup())
    assert r.status == 'CROSSED' and r.counts['agreement']['AGREE_ALL_CANDIDATES'] == 1
    out = SR.read('母がこの休日、本を読んだ。', placement=W2F.FixtureQuery())
    r = EC.build_crosses(out, FixtureLookup())
    assert r.status == 'CROSSED'
    assert dict(r.crosses[0].arms['time'].fillers[0].flags) == {'determiner': 'この'}
    assert r.counts['agreement']['AGREE'] == 2 and 'AGREE_ALL_CANDIDATES' not in r.counts['agreement']       # agent と time (the entry's reading did not flag the agent)


def test_the_events_of_an_output_without_the_new_keys_are_what_they_were():
    for text in ('猫が庭へ歩いた。', '母が夜、手紙を書いた。'):
        out = SR.read(text, placement=W2F.FixtureQuery())
        ev = EC.attach_events(out, FixtureLookup())['events']
        assert list(ev['counts']['agreement']) == ['AGREE', 'DISAGREE', 'NOT_CHECKED']
