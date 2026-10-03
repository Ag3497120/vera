"""W3-b1: the event cross gets the coarse placement as its default lookup (VERA_PLACEMENT / --placement) and copies the source fields of a clause that
the entry decided by a type (`predicate_basis`, `role_basis`) into its provenance. Existing expectations of tests/test_event_cross*.py are not changed.
"""
import copy
import importlib.util
import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent


def _load_by_path(name, path):
    """Load a helper module by its path under a unique name. sys.path is NOT changed: a directory put at the front of sys.path for the rest of the session
    would shadow same-named modules of other test directories (tests/observe/measure.py against tests/event_cross/measure.py: the two W3-c tests of o4)."""
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


F = _load_by_path('w3b1_fakes', TREE / 'tests' / 'reading_soundness' / 'w3b1_fakes.py')
fakes = _load_by_path('w3b1_event_cross_fakes', TREE / 'tests' / 'event_cross' / 'fakes.py')

from verantyx import event_cross as EC    # noqa: E402
from verantyx import semantic_read as SR    # noqa: E402

SENT = '猫が庭へ歩いた。'


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)


def run_main(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = SR.main(argv)
    return buf.getvalue(), code


def clause(**extra):
    c = {'predicate': '歩く', 'roles': {'agent': '猫', 'goal': '庭'}, 'polarity': '+', 'tense': 'past', 'modality': None, 'voice': 'active'}
    c.update(extra)
    return c


def reading(c):
    return {'schema': EC.SOURCE_SCHEMA, 'lang': 'ja', 'readable': True, 'clauses': [c], 'relations': [], 'abstain': None, 'unsupported': [],
            'clause_meta': [{'rule': 'frame', 'span': [3, 5]}]}


BASIS = {'predicate_basis': 'placement_direct:P_MOVE', 'role_basis': {'agent': 'placement_direct:ANIMAL', 'goal': 'placement_direct:PLACE'}}


# ---------------------------------------------------------------------------------------------------------------------------------
# the keys
# ---------------------------------------------------------------------------------------------------------------------------------
def test_the_clause_keys_of_the_convention_are_not_changed_and_the_basis_keys_are_a_separate_constant():
    assert EC.CLAUSE_KEYS == ('predicate', 'roles', 'polarity', 'tense', 'modality', 'voice', 'quantifiers', 'scope', 'comparison')
    assert EC.CLAUSE_OPTIONAL_KEYS == ('quantifiers', 'scope', 'comparison')
    assert EC.CENTER_KEYS == ('predicate', 'polarity', 'tense', 'modality', 'voice', 'quantifiers', 'scope', 'comparison')
    assert EC.ENTRY_BASIS_KEYS == ('predicate_basis', 'role_basis')
    assert not set(EC.ENTRY_BASIS_KEYS) & set(EC.CLAUSE_KEYS)


def test_a_clause_with_the_basis_keys_is_accepted_and_the_keys_go_to_provenance_not_to_the_center():
    out = reading(clause(**BASIS))
    before = copy.deepcopy(out)
    cr = EC.build_crosses(out, EC.StubLookup())
    assert out == before and cr.status == 'CROSSED'
    x = cr.crosses[0]
    assert x.provenance['predicate_basis'] == BASIS['predicate_basis'] and x.provenance['role_basis'] == BASIS['role_basis']
    assert not set(EC.ENTRY_BASIS_KEYS) & set(x.center)
    assert list(x.center) == list(EC.CENTER_KEYS[:5])


def test_a_clause_without_the_basis_keys_has_the_provenance_it_always_had():
    x = EC.build_crosses(reading(clause()), EC.StubLookup()).crosses[0]
    assert list(x.provenance) == ['source_schema', 'clause_index', 'rule', 'span']


def test_only_the_keys_that_are_present_are_copied():
    x = EC.build_crosses(reading(clause(role_basis={'time': 'placement_direct:TIME'})), EC.StubLookup()).crosses[0]
    assert x.provenance['role_basis'] == {'time': 'placement_direct:TIME'} and 'predicate_basis' not in x.provenance


def test_a_malformed_basis_is_refused_and_any_other_unknown_key_still_is():
    for bad in ({'predicate_basis': 3}, {'predicate_basis': ''}, {'role_basis': 'x'}, {'role_basis': {'agent': 3}}, {'role_basis': {}}):
        cr = EC.build_crosses(reading(clause(**bad)), EC.StubLookup())
        key = next(iter(bad))
        assert cr.status == 'INPUT_REJECTED' and 'ENTRY_BASIS_NOT_WELL_FORMED:%s' % key in cr.abstain['reasons'], bad
    cr = EC.build_crosses(reading(clause(basis_of_something='x')), EC.StubLookup())
    assert cr.status == 'INPUT_REJECTED' and 'UNKNOWN_CLAUSE_KEY:basis_of_something' in cr.abstain['reasons']


def test_the_basis_is_a_statement_it_is_not_checked_against_the_roles_here():
    # the cross copies what the entry says; it does not repair or judge it
    out = reading(clause(role_basis={'agent': 'placement_direct:PLACE'}))
    x = EC.build_crosses(out, fakes.MappingLookup({'猫': fakes.direct('ANIMAL')})).crosses[0]
    assert x.provenance['role_basis'] == {'agent': 'placement_direct:PLACE'} and x.arms['agent'].agreement.verdict == 'AGREE'


# ---------------------------------------------------------------------------------------------------------------------------------
# the default lookup
# ---------------------------------------------------------------------------------------------------------------------------------
def test_without_a_placement_the_default_lookup_is_the_stub(monkeypatch):
    lk = EC.default_lookup()
    assert isinstance(lk, EC.StubLookup) and lk.id == 'stub-no-placement/1'
    monkeypatch.setenv('VERA_PLACEMENT', '')
    assert isinstance(EC.default_lookup(), EC.StubLookup)
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/some/dir')
    assert isinstance(EC.default_lookup(), EC.StubLookup)                         # the placement module's own variable is not read here
    assert lk.lookup('犬').state == 'NO_PLACEMENT' and lk.lookup('犬').provenance == {'reason': 'STUB'}


def test_with_a_placement_the_default_lookup_asks_the_coarse_placement_with_the_word_only(monkeypatch):
    monkeypatch.setenv('VERA_PLACEMENT', '/env/dir')
    assert isinstance(EC.default_lookup(), EC.CoarseLookup) and EC.default_lookup().path == '/env/dir'
    assert EC.default_lookup('/arg/dir').path == '/arg/dir'                         # an argument beats the variable
    calls, fq = F.patch_coarse_place(monkeypatch)
    lk = EC.default_lookup('/arg/dir')
    got = lk.lookup('猫')
    assert isinstance(got, EC.PlaceResult) and got.state == 'DECIDED' and got.types == ('ANIMAL',) and got.source == 'direct'
    assert calls[-1] == {'term': '猫', 'context_role': None, 'context_predicate': None, 'placement': '/arg/dir'}
    assert not got.invariant_problems()
    assert lk.id == 'coarse-placement:' + F.SHA


def test_a_placement_that_cannot_be_opened_is_no_placement_with_its_own_reason_never_a_negative_answer():
    lk = EC.CoarseLookup('/no/such/placement/dir')
    got = lk.lookup('猫')
    assert got.state == 'NO_PLACEMENT' and got.provenance['placement']['reason'] == 'MISSING' and not got.invariant_problems()
    assert lk.id == 'coarse-placement:unavailable:MISSING'
    cr = EC.build_crosses(reading(clause()), lk)
    assert cr.counts['agreement']['NOT_CHECKED'] == 2 and cr.counts['not_checked_by_reason']['NO_PLACEMENT'] == 1


def test_build_crosses_and_attach_events_use_the_default_lookup_when_none_is_given(monkeypatch):
    out = reading(clause(**BASIS))
    assert EC.build_crosses(out).lookup_id == 'stub-no-placement/1'
    calls, _ = F.patch_coarse_place(monkeypatch)
    monkeypatch.setenv('VERA_PLACEMENT', '/env/dir')
    cr = EC.build_crosses(out)
    assert cr.lookup_id == 'coarse-placement:' + F.SHA
    assert cr.crosses[0].arms['agent'].agreement.verdict == 'AGREE' and cr.crosses[0].arms['agent'].agreement.observed == ('ANIMAL',)
    assert {c['placement'] for c in calls} == {'/env/dir'}
    assert EC.attach_events(out)['events']['lookup']['id'] == 'coarse-placement:' + F.SHA


def test_the_cross_says_agree_and_disagree_on_real_looking_data(monkeypatch):
    out = SR.read('先生が生徒に地図を渡した。', placement=None)
    assert out['readable']
    agree = EC.build_crosses(out, fakes.MappingLookup({'先生': fakes.direct('PERSON'), '生徒': fakes.direct('PERSON'), '地図': fakes.direct('ARTIFACT')}))
    assert agree.counts['agreement']['AGREE'] == 2 and agree.counts['agreement']['DISAGREE'] == 0
    disagree = EC.build_crosses(out, fakes.MappingLookup({'先生': fakes.direct('PLACE'), '生徒': fakes.direct('PERSON')}))
    assert disagree.crosses[0].arms['agent'].agreement.verdict == 'DISAGREE' and disagree.crosses[0].arms['agent'].agreement.observed == ('PLACE',)
    assert disagree.crosses[0].arms['agent'].fillers[0].surface == '先生'          # a statement, not a repair


# ---------------------------------------------------------------------------------------------------------------------------------
# the entry with --events and a placement
# ---------------------------------------------------------------------------------------------------------------------------------
def test_events_with_a_placement_carry_the_source_of_each_role_and_agree_with_the_types(monkeypatch):
    calls, fq = F.patch_coarse_place(monkeypatch)
    out, code = run_main(['--text=' + SENT, '--events', '--placement=/fake/dir'])
    obj = json.loads(out)
    assert code == 0 and obj['readable'] and list(obj)[-1] == 'events'
    assert obj['clauses'][0]['predicate_basis'] == 'placement_direct:P_MOVE'
    x = obj['events']['crosses'][0]
    assert x['provenance']['predicate_basis'] == obj['clauses'][0]['predicate_basis'] and x['provenance']['role_basis'] == obj['clauses'][0]['role_basis']
    assert 'predicate_basis' not in x['center'] and 'role_basis' not in x['center']
    assert x['arms']['agent']['agreement'] == {'verdict': 'AGREE', 'reason': None, 'expected': ['ANIMAL', 'GROUP_ORG', 'PERSON'], 'observed': ['ANIMAL']}
    assert x['arms']['goal']['agreement']['reason'] == 'ROLE_NOT_IN_TABLE'
    assert obj['events']['lookup']['id'] == 'coarse-placement:' + F.SHA and obj['events']['status'] == 'CROSSED'
    assert fq.misses == [] and all(c['context_role'] is None and c['context_predicate'] is None for c in calls)


def test_events_output_with_a_placement_is_the_output_without_events_plus_events_last(monkeypatch):
    F.patch_coarse_place(monkeypatch)
    for text in (SENT, '兄が弟に名乗った。', '母が夜、手紙を書いた。', '犬が猫を追いかけた。', 'おはようございます。'):
        plain, c0 = run_main(['--text=' + text, '--placement=/fake/dir'])
        with_events, c1 = run_main(['--text=' + text, '--placement=/fake/dir', '--events'])
        obj = json.loads(with_events); assert list(obj)[-1] == 'events' and c0 == c1
        obj.pop('events')
        assert json.dumps(obj, ensure_ascii=False) + '\n' == plain, text


def test_events_without_a_placement_are_the_stub_as_before():
    obj = json.loads(run_main(['--text=犬が猫を追いかけた。', '--events'])[0])
    assert obj['events']['lookup']['id'] == 'stub-no-placement/1'
    assert obj['events']['counts']['agreement'] == {'AGREE': 0, 'DISAGREE': 0, 'NOT_CHECKED': 2}
    assert 'predicate_basis' not in obj['clauses'][0] and 'role_basis' not in obj['clauses'][0]


def test_read_events_with_the_variable_uses_the_placement(monkeypatch):
    F.patch_coarse_place(monkeypatch)
    monkeypatch.setenv('VERA_PLACEMENT', '/env/dir')
    obj = EC.read_events(SENT)
    assert obj['readable'] and obj['events']['lookup']['id'] == 'coarse-placement:' + F.SHA
    assert obj['events']['crosses'][0]['arms']['agent']['agreement']['verdict'] == 'AGREE'


def test_a_source_field_in_the_reader_output_does_not_make_the_cross_refuse_it(monkeypatch):
    F.patch_coarse_place(monkeypatch)
    out = SR.read(SENT, placement='/fake/dir')
    assert out['readable'] and EC.build_crosses(out, EC.StubLookup()).status == 'CROSSED'
