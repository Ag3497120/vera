"""W3-b3 round 4 (review r3, M1-r3): a focus or adverbial particle (係助詞・副助詞) stacked on a case particle makes the two-clause path abstain.

Registered in docs/READING_SOUNDNESS.md section 10C, "第 4 ラウンド" of the change record of the registration, BEFORE this file was written (artifacts/w3-b3/r4/docs_change_time.txt).
This file was frozen (sha256 and time in artifacts/w3-b3/r4/test_r4_freeze.*) before the change to the product code (artifacts/w3-b3/r4/fix_time.txt) and was run on the tree
without the change first: it fails there (artifacts/w3-b3/r4/test_r4_on_unfixed_tree.txt).
The three existing test files of W3-b3 are not changed. Placement answers come from the fixed answers (tests/reading_soundness/w3b3_fakes.py FixtureQuery); no real placement is opened.
Run under a clean environment (env -i).
"""
import importlib.util
import inspect
import json
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


F = _load_by_path('w3b3_fakes_in_test_m1r3', RS / 'w3b3_fakes.py')
COMMON = _load_by_path('w3b3_common_in_test_m1r3', RS / 'w3b3_common.py')

from verantyx import semantic_read as SR    # noqa: E402
from verantyx import semantic_reader as R    # noqa: E402

FOCUS = 'CLAUSE_FORM_NOT_READ:focus_particle'

# a relative clause whose に phrase carries a stacked focus/adverbial particle: the entry reads the single clause as recipient and drops the particle, which the output has no field for
M1R3 = [
    '兄が母にも話した人を弟が呼んだ。',
    '兄が母にまで話した人を弟が呼んだ。',
    '兄が母にさえ話した人を弟が呼んだ。',
    '兄が母にこそ話した人を弟が呼んだ。',
    '兄が母になど話した人を弟が呼んだ。',
    '兄が母にすら話した人を弟が呼んだ。',
]

# (predicate, roles, tense, polarity) per clause and the relations, read by the convention and equal to the output of the tree before the change
CONTROLS = {
    '兄が母に話した人を弟が呼んだ。': (
        [('話す', {'agent': '兄', 'recipient': '母', 'patient': '人'}, 'past', '+'), ('呼ぶ', {'agent': '弟', 'patient': '人'}, 'past', '+')],
        [{'type': 'relative', 'from': 0, 'to': 1, 'head': {'from_role': 'patient', 'to_role': 'patient'}}]),
    '兄は本を読んだので、歌を歌った。': (
        [('読む', {'agent': '兄', 'patient': '本'}, 'past', '+'), ('歌う', {'agent': '兄', 'patient': '歌'}, 'past', '+')],
        [{'type': 'cause', 'from': 0, 'to': 1}]),
    '兄が来ても、弟が帰る。': (
        [('来る', {'agent': '兄'}, None, '+'), ('帰る', {'agent': '弟'}, 'nonpast', '+')],
        [{'type': 'concession', 'from': 0, 'to': 1}]),
    '父が起きたけれども、祖父が座った。': (
        [('起きる', {'agent': '父'}, 'past', '+'), ('座る', {'agent': '祖父'}, 'past', '+')],
        [{'type': 'contrast', 'from': 0, 'to': 1}]),
}

# the cut is found (exactly one) and the gate stops it; these are checked as pure functions (the entry may stop them earlier for another reason)
GATE_HITS = M1R3 + [
    '兄が母には話した人を弟が呼んだ。',
    '兄が母にだけ話した人を弟が呼んだ。',
    '兄が母にばかり話した人を弟が呼んだ。',
    '兄も来たので、弟が帰った。',
]
GATE_PASSES = list(CONTROLS) + [
    '兄が泳いでも、弟が帰る。',
    '兄が来たけれども、弟が帰った。',
    '兄は本を読みながら、歌を歌った。',
]
ALL_SENTENCES = M1R3 + list(CONTROLS) + GATE_HITS + GATE_PASSES


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
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_base_w3b3_m1r3', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src, 'verantyx/semantic_read.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    return mod


BASE = _base_module()


def _dump(o):
    return json.dumps(o, ensure_ascii=False, sort_keys=True)


@pytest.mark.parametrize('text', M1R3)
def test_a_stacked_focus_particle_on_a_ni_phrase_is_not_read_and_the_output_is_the_bases(text):
    q, bq = F.FixtureQuery(), F.FixtureQuery()
    out = SR.read(text, placement=q)
    base = BASE.read(text, placement=bq)
    assert out['readable'] is False, (text, out)
    assert out == base, (text, out, base)
    assert _dump(out).encode('utf-8') == _dump(base).encode('utf-8')
    assert q.misses == [] and bq.misses == [], (q.misses, bq.misses)


@pytest.mark.parametrize('text', M1R3)
def test_the_diagnosis_of_a_stacked_focus_particle_names_the_gate(text):
    ex = SR.clause_scope_explain_ja(text, F.FixtureQuery())
    assert ex['triggered'] is True and ex['cut']['kind'] == 'relative', (text, ex)
    assert ex['read'] is False, (text, ex)
    assert ex['reason'] == FOCUS, (text, ex['reason'])


@pytest.mark.parametrize('text', list(CONTROLS))
def test_the_controls_are_still_read_as_the_convention_says(text):
    q = F.FixtureQuery()
    out = SR.read(text, placement=q)
    clauses, relations = CONTROLS[text]
    assert out['readable'] is True, (text, SR.clause_scope_explain_ja(text, F.FixtureQuery()))
    assert [(c['predicate'], c['roles'], c['tense'], c['polarity']) for c in out['clauses']] == clauses, out['clauses']
    assert out['relations'] == relations, out['relations']
    ex = SR.clause_scope_explain_ja(text, F.FixtureQuery())
    assert ex['read'] is True and ex['reason'] is None, ex
    assert q.misses == [], q.misses


@pytest.mark.parametrize('text', GATE_HITS)
def test_the_gate_stops_a_focus_or_adverbial_particle_that_is_not_the_connective_or_a_topic(text):
    snap = SR._w3b3_snapshot(text, R)
    cut, why = R.w3b3_scope(snap)
    assert cut is not None, (text, why)
    assert R.w3b3_focus_gate(snap, cut) == FOCUS


@pytest.mark.parametrize('text', GATE_PASSES)
def test_the_gate_lets_the_connective_も_and_the_topic_は_pass(text):
    snap = SR._w3b3_snapshot(text, R)
    cut, why = R.w3b3_scope(snap)
    assert cut is not None, (text, why)
    assert R.w3b3_focus_gate(snap, cut) is None


def test_the_gate_decides_by_the_part_of_speech_and_holds_no_list_of_particles():
    src = inspect.getsource(R.w3b3_focus_gate)
    body = src.split('"""', 2)[2]
    for w in ['も', 'まで', 'さえ', 'こそ', 'など', 'すら', 'だけ', 'しか', 'ばかり', 'でも']:
        assert "'%s'" % w not in body and '"%s"' % w not in body, w
    assert '係助詞' in body and '副助詞' in body


@pytest.mark.parametrize('text', ALL_SENTENCES)
def test_the_fixed_answers_hold_every_word_of_the_sentences_of_this_file(text):
    q, bq = F.FixtureQuery(), F.FixtureQuery()
    SR.read(text, placement=q)
    BASE.read(text, placement=bq)
    assert q.misses == [] and bq.misses == [], (text, q.misses, bq.misses)
