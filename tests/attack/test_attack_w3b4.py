"""Executable W3-b4 attacks. Case formulas and abstention expectations are frozen in PREREG.md."""
from dataclasses import dataclass
import importlib.util
from pathlib import Path
import sys
import subprocess
from types import SimpleNamespace
import json
import os

import pytest

from verantyx import semantic_read as SR
from verantyx import semantic_reader as R

_FAKE_PATH = Path(__file__).resolve().parents[2] / 'tests' / 'reading_soundness' / 'w3b1_fakes.py'
_FAKE_SPEC = importlib.util.spec_from_file_location('w3b1_fakes_for_attack_w3b4', _FAKE_PATH)
_FAKES = importlib.util.module_from_spec(_FAKE_SPEC)
sys.modules[_FAKE_SPEC.name] = _FAKES
_FAKE_SPEC.loader.exec_module(_FAKES)
MapQuery, answer = _FAKES.MapQuery, _FAKES.answer


FOCUS = ('さえ', 'すら', 'こそ', 'まで', 'など', 'なんか', 'くらい', 'ほど', 'ばかり', 'でも', 'も', 'は', 'だけ', 'しか', 'ずつ')
SEPARATORS = ('{q}', '、{q}', '　{q}', '「{q}」', ' {q} ')
CROSS_FOCUS = ('も', 'さえ', 'すら', 'まで', 'こそ', 'なんか', 'だけ', 'ほど', 'ばかり', 'でも')
R8 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'
TREE = Path(__file__).resolve().parents[2]
PROMPT_CASES = (
    ('P01', '兄が店へ注文した。', 'へ-recipient'),
    ('P02', '兄が上司から叱られた。', 'passive-agent'),
    ('P03', '兄が右から打った。', 'from-direction'),
    ('P04', '兄が朝から働いた。', 'from-time'),
    ('P05', '兄が廊下を走った。', 'path-wo'),
    ('P06', '兄が三日を過ごした。', 'duration-wo'),
    ('P07', '水が飲みたい。', 'non-agent-ga'),
    ('P08', '本が読める。', 'potential-ga'),
    ('P09', '兄が来たので弟が笑った。', 'subordinate'),
    ('P10', '兄が失敗を悔やんだ。', 'cause-or-patient'),
    ('P11', '兄が穴を掘った。', 'result-wo'),
    ('P12', '音が驚いた。', 'non-agent-ga'),
)


def _base_entry():
    src = subprocess.run(['git', '-C', str(TREE), 'show', 'c875ed3:verantyx/semantic_read.py'],
                         capture_output=True, check=True).stdout.decode('utf-8')
    name = 'verantyx._semantic_read_base_attack_w3b4'
    spec = importlib.util.spec_from_loader(name, loader=None)
    module = importlib.util.module_from_spec(spec)
    module.__package__ = 'verantyx'
    sys.modules[name] = module
    exec(compile(src, 'semantic_read.py@c875ed3', 'exec'), module.__dict__)
    return module


@dataclass(frozen=True)
class Probe:
    case_id: str
    text: str
    category: str
    roles: tuple
    pred_type: str
    focus_surface: str | None = None
    case_surface: str | None = None


def _probe(case_id, text, category, roles, pred_type='P_ACT', focus=None, case=None):
    return Probe(case_id, text, category, tuple(roles), pred_type, focus, case)


def probes():
    out = []
    # A: 15 focus forms x five registered separators after へ = 75.
    for q in FOCUS:
        for si, sep in enumerate(SEPARATORS):
            middle = sep.format(q=q)
            out.append(_probe(f'A{len(out)+1:03d}', f'兄が荷車を倉庫へ{middle}押した。', 'after-he',
                              (('兄', 'PERSON'), ('荷車', 'ARTIFACT'), ('倉庫', 'PLACE'), ('押す', 'P_ACT')), focus=q, case='へ'))
    # B: a focus/topic particle precedes a case-marked phrase = 15.
    for q in ('も', 'さえ', 'すら', 'は', 'だけ'):
        for subj in ('兄', '弟', '職人'):
            out.append(_probe(f'B{len(out)-75+1:03d}', f'{subj}{q}荷車を倉庫へ押した。', 'before-case',
                              ((subj, 'PERSON'), ('荷車', 'ARTIFACT'), ('倉庫', 'PLACE'), ('押す', 'P_ACT')), focus=q, case=''))
    # C: 10 focus forms after each of を/から/に/で = 40. P_MOVE rows make source/time/place valid table roles.
    templates = (
        ('兄が荷車を{q}倉庫へ押した。', 'を', (('兄', 'PERSON'), ('荷車', 'ARTIFACT'), ('倉庫', 'PLACE'), ('押す', 'P_ACT')), 'P_ACT'),
        ('兄が工場から{q}倉庫へ走った。', 'から', (('兄', 'PERSON'), ('工場', 'PLACE'), ('倉庫', 'PLACE'), ('走る', 'P_MOVE')), 'P_MOVE'),
        ('兄が去年に{q}倉庫へ走った。', 'に', (('兄', 'PERSON'), ('去年', 'TIME'), ('倉庫', 'PLACE'), ('走る', 'P_MOVE')), 'P_MOVE'),
        ('兄が国道で{q}倉庫へ走った。', 'で', (('兄', 'PERSON'), ('国道', 'PLACE'), ('倉庫', 'PLACE'), ('走る', 'P_MOVE')), 'P_MOVE'),
    )
    for template, particle, roles, ptype in templates:
        for q in CROSS_FOCUS:
            out.append(_probe(f'C{len(out)-90+1:03d}', template.format(q=q), 'after-other-case', roles, ptype, q, particle))
    # D: 20 independent role-overlap probes from PREREG.md.
    raw = (
        ('店員が店へ注文した。', 'へ-recipient', (('店員','PERSON'),('店','PLACE'),('注文する','P_ACT')), 'P_ACT'),
        ('客が窓口へ相談した。', 'へ-recipient', (('客','PERSON'),('窓口','PLACE'),('相談する','P_ACT')), 'P_ACT'),
        ('兄が店へ電話した。', 'へ-recipient', (('兄','PERSON'),('店','PLACE'),('電話する','P_ACT')), 'P_ACT'),
        ('記者が会社へ質問した。', 'へ-recipient', (('記者','PERSON'),('会社','GROUP_ORG'),('質問する','P_ACT')), 'P_ACT'),
        ('生徒が先生へ頼んだ。', 'へ-recipient', (('生徒','PERSON'),('先生','PERSON'),('頼む','P_ACT')), 'P_ACT'),
        ('兄が右から倉庫へ荷車を押した。', 'from-direction', (('兄','PERSON'),('右','PLACE'),('倉庫','PLACE'),('荷車','ARTIFACT'),('押す','P_ACT')), 'P_ACT'),
        ('兄が朝から倉庫へ荷物を運んだ。', 'from-time', (('兄','PERSON'),('朝','PLACE'),('倉庫','PLACE'),('荷物','ARTIFACT'),('運ぶ','P_ACT')), 'P_ACT'),
        ('姉が東から倉庫へ箱を運んだ。', 'from-direction', (('姉','PERSON'),('東','PLACE'),('倉庫','PLACE'),('箱','ARTIFACT'),('運ぶ','P_ACT')), 'P_ACT'),
        ('兄が上司から倉庫へ叱られた。', 'passive-agent', (('兄','PERSON'),('上司','PERSON'),('倉庫','PLACE'),('叱る','P_ACT')), 'P_ACT'),
        ('弟が右から倉庫へ打った。', 'from-direction', (('弟','PERSON'),('右','PLACE'),('倉庫','PLACE'),('打つ','P_ACT')), 'P_ACT'),
        ('兄が廊下を倉庫へ走った。', 'path-wo', (('兄','PERSON'),('廊下','ARTIFACT'),('倉庫','PLACE'),('走る','P_ACT')), 'P_ACT'),
        ('姉が公園を倉庫へ歩いた。', 'path-wo', (('姉','PERSON'),('公園','ARTIFACT'),('倉庫','PLACE'),('歩く','P_ACT')), 'P_ACT'),
        ('兄が川を倉庫へ渡った。', 'path-wo', (('兄','PERSON'),('川','ARTIFACT'),('倉庫','PLACE'),('渡る','P_ACT')), 'P_ACT'),
        ('兄が三日を倉庫へ過ごした。', 'duration-wo', (('兄','PERSON'),('三日','ARTIFACT'),('倉庫','PLACE'),('過ごす','P_ACT')), 'P_ACT'),
        ('姉が休暇の三日を倉庫へ過ごした。', 'duration-wo', (('姉','PERSON'),('休暇','TIME'),('三日','ARTIFACT'),('倉庫','PLACE'),('過ごす','P_ACT')), 'P_ACT'),
        ('兄が庭へ穴を掘った。', 'result-wo', (('兄','PERSON'),('庭','PLACE'),('穴','ARTIFACT'),('掘る','P_CREATE')), 'P_CREATE'),
        ('姉が壁へ穴を開けた。', 'result-wo', (('姉','PERSON'),('壁','PLACE'),('穴','ARTIFACT'),('開ける','P_CREATE')), 'P_CREATE'),
        ('兄が失敗を悔やんで倉庫へ戻った。', 'cause-or-patient', (('兄','PERSON'),('失敗','EVENT_ACT'),('倉庫','PLACE'),('悔やむ','P_EMOTION'),('戻る','P_MOVE')), 'P_EMOTION'),
        ('姉が音を恐れて倉庫へ逃げた。', 'cause-or-patient', (('姉','PERSON'),('音','ARTIFACT'),('倉庫','PLACE'),('恐れる','P_EMOTION'),('逃げる','P_MOVE')), 'P_EMOTION'),
        ('音が驚いた。', 'non-agent-ga', (('音','ANIMAL'),('驚く','P_EMOTION')), 'P_EMOTION'),
    )
    for i, (text, category, roles, ptype) in enumerate(raw, 1):
        out.append(_probe(f'D{i:02d}', text, category, roles, ptype))
    assert len(out) == 150, len(out)
    return tuple(out)


def role_overlap_probes():
    return (
        _probe('X1', '兄が右で打った。', 'instrument-place', (('兄','PERSON'),('右','PLACE'),('打つ','P_ACT'))),
        _probe('X2', '妹が金を休みに使った。', 'purpose-time', (('妹','PERSON'),('金','ARTIFACT'),('休み','TIME'),('使う','P_CONSUME')), 'P_CONSUME'),
        _probe('X3', '兄が庭へ穴を掘った。', 'result-patient', (('兄','PERSON'),('庭','PLACE'),('穴','ARTIFACT'),('掘る','P_CREATE')), 'P_CREATE'),
        _probe('X4', '兄が段差で驚いた。', 'cause-place', (('兄','PERSON'),('段差','PLACE'),('驚く','P_EMOTION')), 'P_EMOTION'),
    )


def query_for(probe, force=None):
    mapping = {}
    for term, type_id in probe.roles:
        if force and term in force:
            type_id = force[term]
        if type_id is None:
            continue
        mapping[term] = answer(type_id, term=term)
    return MapQuery(mapping)


def entry_result(probe, force=None):
    return SR.read(probe.text, 'ja', placement=query_for(probe, force))


def focus_result(text):
    toks = R._tokens(text)
    clause = SimpleNamespace(span=SimpleNamespace(start=0, end=len(text)))
    return R.typed_focus_after_case_ja(toks, clause)


def is_lossy(probe, roles):
    if probe.category in ('after-he', 'before-case', 'after-other-case'):
        return True  # no output slot represents these contrastive particles
    if probe.category == 'へ-recipient':
        return 'goal' in roles and 'recipient' not in roles
    if probe.category == 'from-direction':
        return probe.case_id in ('D10', 'P03') and 'source' in roles
    if probe.category == 'from-time':
        return 'source' in roles
    if probe.category == 'passive-agent':
        return 'source' in roles or 'agent' in roles
    if probe.category in ('path-wo', 'duration-wo', 'result-wo', 'cause-or-patient'):
        return 'patient' in roles
    if probe.category == 'non-agent-ga':
        return 'agent' in roles
    if probe.category == 'potential-ga':
        return 'agent' in roles or bool(roles)
    if probe.category == 'subordinate':
        return bool(roles)
    return False


@pytest.mark.xfail(strict=True, reason='auditor ruling 2026-10-04 (W5-f F-2 withdrawn): relative-position nouns (右・左…) are typed PLACE in r8; the sound fix is the RELATIVE_POSITION type of W3-a6 / reader W3-b6. Strict xfail flips when that lands.')
def test_the_150_preregistered_safety_cases_are_not_returned_as_readings():
    violations = []
    for probe in probes():
        out = entry_result(probe)
        clauses = out.get('clauses') or [{}]
        roles = clauses[0].get('roles') or {}
        if out.get('readable') and is_lossy(probe, roles):
            violations.append({'id': probe.case_id, 'category': probe.category, 'input': probe.text,
                               'roles': roles, 'pred_type': probe.pred_type})
    assert not violations, json.dumps(violations, ensure_ascii=False, separators=(',', ':'))


@pytest.mark.xfail(strict=True, reason='auditor ruling 2026-10-04: this copy calls the K186 gate directly; W5-f F-1 fixed the quoted/bracketed particles at the public entry (tests/test_semantic_read_w5f.py covers it). Strict xfail until the gate itself is widened.')
def test_the_gate_catches_registered_adjacent_focus_particles_even_across_markers():
    misses = []
    for probe in probes():
        if probe.category not in ('after-he', 'after-other-case'):
            continue
        got = focus_result(probe.text)
        if got is None:
            misses.append({'id': probe.case_id, 'input': probe.text, 'expected_case': probe.case_surface,
                           'expected_focus': probe.focus_surface})
    assert not misses, json.dumps(misses, ensure_ascii=False, separators=(',', ':'))


@pytest.mark.xfail(strict=True, reason='auditor ruling 2026-10-04 (K-P): the cases are outside the typed stage with the real placement; kept as a strict xfail attestation for W3-b6.')
def test_a_false_direct_placement_can_turn_unregistered_roles_into_patient_or_agent_reads():
    cases = {p.case_id: p for p in probes()}
    attack = (
        ('D10', {'右': 'PLACE'}),
        ('D07', {'朝': 'PLACE'}),
        ('D11', {'廊下': 'ARTIFACT'}),
        ('D14', {'三日': 'ARTIFACT'}),
        ('D16', {'穴': 'ARTIFACT'}),
        ('D17', {'穴': 'ARTIFACT'}),
        ('D20', {'音': 'ANIMAL'}),
    )
    violations = []
    for case_id, force in attack:
        probe = cases[case_id]
        out = entry_result(probe, force)
        roles = (out.get('clauses') or [{}])[0].get('roles') or {}
        # Matched control: with the same sentence and no answer for the risky filler, the entry should abstain.
        control = entry_result(probe, {term: None for term in force})
        if out.get('readable') and is_lossy(probe, roles) and not control.get('readable'):
            violations.append({'id': case_id, 'input': probe.text, 'forced_direct_type': force,
                               'roles': roles, 'control_abstains': True})
    assert not violations, json.dumps(violations, ensure_ascii=False, separators=(',', ':'))


@pytest.mark.xfail(strict=True, reason='auditor ruling 2026-10-04 (W5-f F-2 withdrawn): 右から打った reads source=右 with r8 (PLACE); fixed on the placement side by W3-a6 (RELATIVE_POSITION). Strict xfail flips when r9 lands.')
def test_the_real_r8_run2_entry_has_no_preregistered_misread():
    if not os.path.isdir(R8):
        pytest.skip('the requested r8/run2 placement is absent')
    selected = {'A026', 'A054', 'A059', 'D01', 'D03', 'D06', 'D08', 'D10'}
    hits = []
    for probe in probes():
        if probe.case_id not in selected:
            continue
        out = SR.read(probe.text, 'ja', placement=R.CoarseQuery(R8))
        roles = (out.get('clauses') or [{}])[0].get('roles') or {}
        if out.get('readable') and is_lossy(probe, roles):
            hits.append({'id': probe.case_id, 'input': probe.text, 'roles': roles,
                         'abstain': out.get('abstain')})
    assert not hits, json.dumps(hits, ensure_ascii=False, separators=(',', ':'))


def test_no_placement_output_for_the_150_cases_is_byte_equal_to_c875ed3():
    base = _base_entry()
    encode = lambda value: json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    differences = []
    for probe in probes():
        before = encode(base.read(probe.text, 'ja', placement=None))
        after = encode(SR.read(probe.text, 'ja', placement=None))
        if before != after:
            differences.append({'id': probe.case_id, 'input': probe.text, 'base': before.decode('utf-8'),
                                'current': after.decode('utf-8')})
    assert not differences, json.dumps(differences, ensure_ascii=False, separators=(',', ':'))


def test_roles_outside_the_second_table_do_not_win_by_filler_type_alone():
    violations = []
    for probe in role_overlap_probes():
        out = entry_result(probe)
        if out.get('readable'):
            violations.append({'id': probe.case_id, 'input': probe.text,
                               'roles': (out.get('clauses') or [{}])[0].get('roles')})
    assert not violations, json.dumps(violations, ensure_ascii=False, separators=(',', ':'))


@pytest.mark.xfail(strict=True, reason='auditor ruling 2026-10-04 (K-HE/K-P): 店へ注文した / 右から打った need predicate role frames (W3-a6) and the RELATIVE_POSITION type; strict xfail until then.')
def test_the_twelve_examples_from_the_attack_instruction_do_not_produce_lossy_reads_on_r8():
    if not os.path.isdir(R8):
        pytest.skip('the requested r8/run2 placement is absent')
    query = R.CoarseQuery(R8)
    violations = []
    for case_id, text, category in PROMPT_CASES:
        out = SR.read(text, 'ja', placement=query)
        roles = (out.get('clauses') or [{}])[0].get('roles') or {}
        if out.get('readable') and is_lossy(_probe(case_id, text, category, ()), roles):
            violations.append({'id': case_id, 'input': text, 'roles': roles, 'abstain': out.get('abstain')})
    assert not violations, json.dumps(violations, ensure_ascii=False, separators=(',', ':'))
