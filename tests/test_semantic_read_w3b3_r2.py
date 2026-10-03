"""W3-b3 round 2 (review r1, M1): the empty `に` arm of a relative clause of P_COMMUNICATE is filled only when the relative clause, read alone by the entry, has a `recipient`.

Registered in docs/READING_SOUNDNESS.md section 10C, "第 2 ラウンド" of the change record of the registration (2026-10-04 00:21), BEFORE this file was written.
This file was frozen (sha256 and time in artifacts/w3-b3/r2/) before the change to `_w3b3_head_arm` and was run on the tree without the change first (it fails there).
The two existing test files of W3-b3 are not changed. Placement answers come from fakes (tests/reading_soundness/w3b3_fakes.py); no real placement is opened.
Run under a clean environment (env -i).
"""
import importlib.util
import inspect
import re
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent
RS = TREE / 'tests' / 'reading_soundness'
BASE_COMMIT = 'c875ed3'


def _load_by_path(name, path):
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


F = _load_by_path('w3b3_fakes_in_test_r2', RS / 'w3b3_fakes.py')
COMMON = _load_by_path('w3b3_common_in_test_r2', RS / 'w3b3_common.py')

from verantyx import semantic_read as SR    # noqa: E402
from verantyx import semantic_reader as R    # noqa: E402

TEST_INPUTS = [l.strip() for l in (RS / 'w3b3_test_inputs.txt').read_text(encoding='utf-8').splitlines() if l.strip() and not l.startswith('#')]
JA = re.compile('[぀-ヿ㐀-䶿一-鿿]')
JA_TEST_INPUTS = [t for t in TEST_INPUTS if JA.search(t)]

# a relative clause of P_COMMUNICATE (話す・言う・頼む) whose に is a time (not the recipient): the arm of に is empty, so two arms are empty and the head is not placed
TIME_NI = [
    '母が昼に話した人を兄が呼んだ。',
    '母が三時に話した人を兄が呼んだ。',
    '母が夜に頼んだ友達を先生が呼んだ。',
    '母が朝に言った生徒を兄が呼んだ。',
    '姉が夜に話した先生を母が待った。',
    '父が三時に頼んだ友達を弟が呼んだ。',
]
# the thirteen sentences of the data that were read before the change: に is the recipient
RECIPIENT_NI = [
    '母が弟に話した人を兄が呼んだ。', '姉が妹に頼んだ友達を先生が呼んだ。', '兄が先生に言った生徒を母が待った。', '父が祖母に話した犬を兄が見た。',
    '母が姉に話した本を弟が読んだ。', '兄が弟に頼んだ花を母が買った。', '姉が母に頼んだ薬を弟が飲んだ。', '祖父が兄に話した絵を姉が描いた。',
    '先生が生徒に言った歌を弟が歌った。', '母が弟に話した客を兄が呼んだ。', '歌を弟に頼んだ人を兄が呼んだ。', '本を妹に話した先生を母が待った。',
    '絵を先生に言った生徒を弟が呼んだ。',
]
# a time に and a recipient に together: the recipient arm is filled, one arm (patient) is empty, the head is the patient
BOTH_NI = ['母が昼に弟に話した人を兄が呼んだ。', '母が弟に昼に話した人を兄が呼んだ。', '姉が夜に妹に頼んだ友達を先生が呼んだ。']


@pytest.fixture(autouse=True)
def _no_placement_in_the_environment(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)


def test_the_loaded_modules_are_of_this_tree():
    root = str(TREE.resolve())
    for name, mod in list(sys.modules.items()):
        if (name == 'verantyx' or name.startswith('verantyx.')) and getattr(mod, '__file__', None):
            assert str(Path(mod.__file__).resolve()).startswith(root), (name, mod.__file__)


def _base_module():
    import subprocess
    src = subprocess.run(['git', '-C', str(TREE), 'show', '%s:verantyx/semantic_read.py' % BASE_COMMIT], capture_output=True, check=True).stdout.decode('utf-8')
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_base_w3b3_r2', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src, 'verantyx/semantic_read.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    return mod


BASE = _base_module()


@pytest.mark.parametrize('text', TIME_NI)
def test_a_time_ni_does_not_fill_the_recipient_arm_so_the_relative_clause_is_not_read(text):
    q = F.FixtureQuery()
    ex = SR.clause_scope_explain_ja(text, q)
    assert ex['read'] is False, (text, ex)
    assert ex['reason'] == 'HEAD_ROLE_UNDETERMINED:empty_arms=2', (text, ex['reason'])
    assert ex['head']['empty_arms'] == ['patient', 'NI_UNDECIDED'], ex['head']
    out = SR.read(text, placement=F.FixtureQuery())
    assert out['readable'] is False and out == BASE.read(text, placement=F.FixtureQuery())    # the refusal is the base's, byte for byte
    assert q.misses == [], q.misses


@pytest.mark.parametrize('text', RECIPIENT_NI)
def test_a_recipient_ni_still_fills_the_arm_and_the_relative_clause_is_read_as_before(text):
    q = F.FixtureQuery()
    out = SR.read(text, placement=q)
    assert out['readable'] is True, (text, SR.clause_scope_explain_ja(text, F.FixtureQuery()))
    rel = out['relations'][0]
    assert rel['type'] == 'relative' and set(rel['head']) == {'from_role', 'to_role'}
    assert 'recipient' in out['clauses'][0]['roles']
    ex = SR.clause_scope_explain_ja(text, F.FixtureQuery())
    assert ex['read'] is True and len(ex['head']['empty_arms']) == 1 and 'NI_UNDECIDED' not in ex['head']['empty_arms'], ex['head']
    assert q.misses == []


@pytest.mark.parametrize('text', BOTH_NI)
def test_a_time_ni_and_a_recipient_ni_together_read_the_head_as_the_patient(text):
    out = SR.read(text, placement=F.FixtureQuery())
    assert out['readable'] is True, (text, SR.clause_scope_explain_ja(text, F.FixtureQuery()))
    c0 = out['clauses'][0]
    assert 'recipient' in c0['roles'] and 'time' in c0['roles'], c0
    assert out['relations'][0]['head']['from_role'] == 'patient' and c0['roles']['patient'] in ('人', '友達'), out


def test_the_arm_rule_adds_no_surface_string_of_a_particle():
    """The change narrows the count of the arms: the rule of `_w3b3_head_arm` is by the role names of the reading, not by the particle の surface (no `に` literal)."""
    src = inspect.getsource(SR._w3b3_head_arm)
    assert 'に' not in src.split('"""', 2)[2], 'the arm count must not look at the particle に'
    assert "ni_filled = 'recipient' in c0['roles']" in src


def test_the_diagnosis_of_a_time_ni_names_both_empty_arms_and_nothing_is_placed():
    ex = SR.clause_scope_explain_ja('母が昼に話した人を兄が呼んだ。', F.FixtureQuery())
    assert ex['read'] is False and ex['head']['arm'] is None and ex['head']['basis'] is None and ex['head']['candidates'] == []


@pytest.mark.parametrize('text', JA_TEST_INPUTS)
def test_the_fixture_holds_every_word_of_the_test_inputs(text):
    """Review r1, optional 1: no input of the test list asks the fixture for a word it does not have (the answer would be UNKNOWN, recorded in `misses`)."""
    q = F.FixtureQuery()
    SR.read(text, placement=q)
    bq = F.FixtureQuery()
    BASE.read(text, placement=bq)
    assert q.misses == [] and bq.misses == [], (text, q.misses, bq.misses)
