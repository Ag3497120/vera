"""W3-b1: the reader reads with the DIRECT type of a word (coarse placement) only; the table of types and the gate were registered in
docs/READING_SOUNDNESS.md section 10 (K62-K65) before the data (ja_r8.jsonl, en_r4.jsonl) and this file were written.

Placement answers here come from fakes (tests/reading_soundness/w3b1_fakes.py); no real placement is opened. Run under a clean environment (env -i):
a VERA_PLACEMENT left in the shell would change the default path of the entry.
"""
import ast
import importlib.util
import inspect
import io
import json
import os
import re
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent
RS = TREE / 'tests' / 'reading_soundness'


def _load_by_path(name, path):
    """Load a helper module by its path under a unique name. sys.path is NOT changed: a directory put at the front of sys.path for the rest of the session
    would shadow same-named modules of other test directories (tests/observe/measure.py against tests/event_cross/measure.py)."""
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


F = _load_by_path('w3b1_fakes', RS / 'w3b1_fakes.py')

from tools.bank_score.v2 import b1    # noqa: E402
from verantyx import coarse_types as CT    # noqa: E402
from verantyx import semantic_read as SR    # noqa: E402
from verantyx import semantic_reader as R    # noqa: E402
W1A5 = _load_by_path('w1a5_common_in_w3b1', RS / 'w1a5_common.py')    # W1-a5 (docs/READING_SOUNDNESS.md 10G)

DOCS = (TREE / 'docs' / 'READING_SOUNDNESS.md').read_text(encoding='utf-8')
BASE_COMMIT = '2732274'  # integration: dev before the W3-b1 merge (W5-a changed the base reading)


@pytest.fixture(autouse=True)
def _no_placement_in_the_environment(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)


def block(name):
    m = re.search(r'<!-- BEGIN table:%s -->\n(.*?)<!-- END table:%s -->' % (name, name), DOCS, re.S)
    assert m, name
    rows = [[c.strip().strip('`') for c in line.strip().strip('|').split('|')] for line in m.group(1).splitlines()
            if line.startswith('|') and not set(line) <= set('|- ')]
    return rows[1:]


def rows_of(*names):
    out = []
    for name in names:
        for line in (RS / name).read_text(encoding='utf-8').splitlines():
            if line.strip(): out.append(json.loads(line))
    return out


DATA = rows_of('ja_r8.jsonl', 'en_r4.jsonl')
SAMPLES = [r['input'] for fx in ('B1_v2', 'B1_v2_r2', 'B1_v2_r3')
           for r in (json.loads(l) for l in (TREE / 'tests' / 'bank_score' / 'fixtures' / fx / 'items.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())]
EXCEPTIONS = json.loads((RS / 'w3b1_expect_exceptions.json').read_text(encoding='utf-8'))['exceptions'] if (RS / 'w3b1_expect_exceptions.json').exists() else []


def read(text, q, lang=None):
    return SR.read(text, lang, placement=q)


def reasons(out):
    assert out['readable'] is False, out
    return out['abstain']['reasons']


# ---------------------------------------------------------------------------------------------------------------------------------
# K62: the table of types (docs == code), the gate's registered form
# ---------------------------------------------------------------------------------------------------------------------------------
def test_the_table_of_frames_in_the_docs_is_the_table_in_the_code_in_the_same_order():
    docs = block('w3b1_frames')
    code = [(t, role, '/'.join(parts), ' '.join(exp), '項' if kind == 'arg' else '付加')
            for t, rows in R.TYPED_FRAMES.items() for (role, parts, exp, kind) in rows]
    assert [(r[0], r[1], r[2], r[3], r[4]) for r in docs] == code


def test_every_predicate_type_is_read_or_not_read_exactly_once():
    types = list(CT.PRED_TYPES)
    assert len(types) == 13
    assert sorted(list(R.TYPED_FRAMES) + list(R.TYPED_FRAMES_NOT_READ)) == sorted(types)
    assert set(R.TYPED_FRAMES) == {'P_MOVE', 'P_COMMUNICATE'}
    docs = block('w3b1_not_read')
    assert [(r[0], r[1]) for r in docs] == list(R.TYPED_FRAMES_NOT_READ.items())


def test_the_table_holds_type_ids_role_names_and_particles_only_no_words():
    noun_types, roles = set(CT.NOUN_TYPES), set(b1.ROLES)
    for t, rows in R.TYPED_FRAMES.items():
        assert t in CT.PRED_TYPES
        for role, parts, exp, kind in rows:
            assert role in roles and kind in ('arg', 'adjunct')
            assert parts and all(p in ('が', 'を', 'に', 'へ', 'で', 'から') for p in parts)     # case particles only (not は も の)
            assert exp and set(exp) <= noun_types
    for row in block('w3b1_frames'):
        assert re.fullmatch(r'P_[A-Z]+', row[0]) and row[1] in roles and re.fullmatch(r'が|を|に|へ|で|から', row[2])
        assert all(x in noun_types for x in row[3].split()) and row[4] in ('項', '付加')
    for row in block('w3b1_not_read'):
        assert re.fullmatch(r'P_[A-Z]+', row[0]) and re.fullmatch(r'[A-Z_]+', row[1])


def test_the_expected_types_of_a_role_are_those_of_the_event_cross_table():
    from verantyx import event_cross as EC
    seen = set()
    for t, rows in R.TYPED_FRAMES.items():
        for role, parts, exp, kind in rows:
            if role in EC.EXPECTED_TYPES:
                seen.add(role)
                assert set(exp) == set(EC.EXPECTED_TYPES[role]), (t, role)
    # the roles of the table in the docs (the current K62 table) that the event cross also registers: nothing is skipped silently
    docs_roles = {row[1] for row in block('w3b1_frames')}
    assert seen == {role for role in docs_roles if role in EC.EXPECTED_TYPES}
    assert seen == {'agent', 'place', 'time'}      # `recipient` was in the registered table and was returned to "not read" (K62 table change record 1)
    patient = [exp for rows in R.TYPED_FRAMES.values() for role, parts, exp, kind in rows if role == 'patient'][0]
    # Integration of W3-a6 (auditor, 2026-10-05): NOUN_TYPES gained RELATIVE_POSITION (18); the frame types of the reader's rows stay the 17 of FRAME_NOUN_TYPES
    assert set(patient) == set(CT.FRAME_NOUN_TYPES) - {'TIME', 'QUANTITY', 'PLACE'} and len(patient) == 14
    assert set(EC.NOUN_TYPE_IDS) == set(CT.NOUN_TYPES)


def test_adjunct_rows_are_exactly_the_time_and_place_rows():
    for rows in R.TYPED_FRAMES.values():
        for role, parts, exp, kind in rows:
            assert (kind == 'adjunct') == (role in ('time', 'place'))


def test_part_constructions_in_the_docs_are_those_in_the_code():
    docs = {(r[0], r[1].replace('(、)', '')): r[2] for r in block('w3b1_part_constructions')}
    assert docs == {(t, '∅' if p == '' else p): role for (t, p), role in R.PLACEMENT_PART_CONSTRUCTIONS.items()}
    assert set(R.PLACEMENT_PART_CONSTRUCTIONS.values()) <= {'time', 'place'}


def test_markers_in_the_docs_are_those_in_the_code_in_the_same_order():
    docs = {}
    for kind, cell in block('w3b1_markers'):
        cell = re.sub(r'\([^)]*\)', ' ', cell).replace('入口の `_QUANT_SURFACES` の語', ' ')
        docs[kind] = tuple(cell.split())
    assert list(docs) == list(R.W3B1_MARKERS_JA) and docs == {k: tuple(v) for k, v in R.W3B1_MARKERS_JA.items()}


def test_the_reasons_registered_in_the_docs_are_closed_and_every_reason_the_data_produces_is_among_them():
    registered = {re.split(r'[:\[<]', r[0])[0] for r in block('w3b1_reasons')}
    assert registered and all(x.startswith('PLACEMENT_') for x in registered)
    seen = set()
    for row in DATA:
        out = read(row['input'], F.FixtureQuery())
        if not out['readable'] and len(out['abstain']['reasons']) > 1:
            seen.update(re.split(r':', x)[0] for x in out['abstain']['reasons'][1:] if x.startswith('PLACEMENT_'))
    assert seen and seen <= registered, sorted(seen - registered)


# ---------------------------------------------------------------------------------------------------------------------------------
# the gate: placement_type (the only function that reads the fields of an answer)
# ---------------------------------------------------------------------------------------------------------------------------------
def test_gate_passes_a_decided_direct_answer_and_returns_its_type():
    assert R.placement_type(F.answer('PERSON')) == ('PERSON', None)
    assert R.placement_type(F.answer('P_MOVE')) == ('P_MOVE', None)


@pytest.mark.parametrize('bad', [
    lambda a: a.update(top=['PERSON', 'PLACE']),                                   # DECIDED with two types
    lambda a: a.update(state='MULTIPLE'),                                         # MULTIPLE with one type
    lambda a: a.update(state='UNKNOWN'),                                          # UNKNOWN with a type
    lambda a: a.update(origin='estimated'),                                       # estimated without basis / constructed
    lambda a: a.update(estimate_basis='proximity'),                               # direct with a basis
    lambda a: a.update(decided_by=None),                                          # direct without decided_by
    lambda a: a.update(constructed=True),                                         # constructed but direct
    lambda a: a.update(state='SURPRISE'),
])
def test_gate_rejects_an_answer_that_breaks_the_contract(bad):
    a = F.answer('PERSON'); bad(a)
    t, why = R.placement_type(a)
    assert t is None and why.startswith('PLACEMENT_INVALID')


def test_gate_rejects_what_is_not_an_answer():
    for junk in (None, [], 'x', {'state': 'DECIDED'}):
        assert R.placement_type(junk)[1].startswith('PLACEMENT_INVALID')


def test_gate_names_every_state_apart():
    assert R.placement_type(F.bare('NO_PLACEMENT', 'MISSING')) == (None, 'PLACEMENT_NO_PLACEMENT:MISSING')
    assert R.placement_type(F.bare('UNKNOWN')) == (None, 'PLACEMENT_UNKNOWN')
    assert R.placement_type(F.bare('UNPLACED')) == (None, 'PLACEMENT_UNPLACED')
    assert R.placement_type(F.answer(['PERSON', 'PLACE'])) == (None, 'PLACEMENT_MULTIPLE')


def test_gate_names_the_two_kinds_of_estimate_apart_and_never_uses_them():
    assert R.placement_type(F.answer('PLACE', origin='estimated', basis='proximity', decided_by=None)) == (None, 'PLACEMENT_ESTIMATED_NEAR')
    assert R.placement_type(F.answer('PLACE', origin='estimated', basis='generated', decided_by=['gen_definition'])) == (None, 'PLACEMENT_ESTIMATED_GENERATED')
    assert R.placement_type(F.answer(['PLACE', 'TIME'], origin='estimated', basis='proximity', decided_by=None, state='MULTIPLE'))[0] is None


def test_gate_does_not_use_a_direct_type_that_a_generated_definition_promoted():
    a = F.answer('PERSON', decided_by=['gen_definition', 'role@codex:x'])
    assert R.placement_type(a) == (None, 'PLACEMENT_DIRECT_VIA_GENERATED')
    assert R.placement_type(a, adjunct=True) == (None, 'PLACEMENT_DIRECT_VIA_GENERATED')


def test_gate_five_an_adjunct_decided_by_slot_arms_only_is_not_used():
    only_slots = F.answer('TIME', decided_by=['role@codex:a', 'role@jawiki'])
    assert R.placement_type(only_slots, adjunct=True) == (None, 'PLACEMENT_SLOT_EVIDENCE_ONLY')
    assert R.placement_type(only_slots, adjunct=False) == ('TIME', None)           # an argument: the gate does not apply
    assert R.placement_type(F.answer('TIME', decided_by=['definition', 'role@codex:a']), adjunct=True) == ('TIME', None)
    assert R.placement_type(F.answer('TIME', decided_by=['notation']), adjunct=True) == ('TIME', None)


def test_the_order_of_the_gate_is_the_registered_order():
    # an invalid answer is INVALID before anything else; a MULTIPLE estimate is the estimate; a generated promotion beats slot evidence
    a = F.answer('TIME', decided_by=['gen_definition', 'role@x'])
    assert R.placement_type(a, adjunct=True)[1] == 'PLACEMENT_DIRECT_VIA_GENERATED'
    b = F.bare('UNKNOWN'); b['top'] = ['TIME']
    assert R.placement_type(b)[1].startswith('PLACEMENT_INVALID')


def test_only_the_gate_and_the_query_adapter_read_the_fields_of_an_answer():
    """A5 (read by the machine as well as by the reviewer): `state` / `origin` / `top` / `decided_by` / `estimate_basis` of a placement answer are
    read in `placement_type` alone (CoarseQuery only forwards the answer and keeps the content hash)."""
    pat = re.compile(r"""\[['"](?:state|origin|top|decided_by|estimate_basis|constructed)['"]\]|\.get\(['"](?:state|origin|top|decided_by|estimate_basis|constructed)['"]""")
    for module in (R, SR):
        src = Path(module.__file__).read_text(encoding='utf-8')
        tree = ast.parse(src)
        offenders = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and pat.search(ast.get_source_segment(src, node) or ''):
                offenders.add(node.name)
        # nested functions are inside their parents' segments, so only top-level and method names matter here
        # W3-b2 (proposal): the gate for a SET of allowed types and the reader of the frame are two more readers of the fields of an answer (docs 10B K95)
        allowed = {'placement_type', 'placement_fit', 'predicate_frame'}
        assert offenders <= allowed | {'_placement_answer_problems'}, (module.__name__, sorted(offenders))
    assert 'placement_type' in {n.name for n in ast.walk(ast.parse(Path(R.__file__).read_text(encoding='utf-8'))) if isinstance(n, ast.FunctionDef)}


def test_the_query_adapter_asks_for_the_word_only_with_a_real_path(monkeypatch):
    from verantyx import coarse_place
    seen = []

    def fake(term, **kw):
        seen.append((term, kw)); return F.unknown_answer(term)
    monkeypatch.setattr(coarse_place, 'query', fake)
    q = R.CoarseQuery('/some/dir')
    q.query('犬')
    assert seen == [('犬', {'placement': '/some/dir'})]                    # no context_role, no context_predicate, no None path
    assert q.id == 'coarse-placement:' + F.SHA
    q2 = R.CoarseQuery('/other')
    monkeypatch.setattr(coarse_place, 'query', lambda term, **kw: F.bare('NO_PLACEMENT', 'MISSING', term))
    q2.query('犬')
    assert q2.id == 'coarse-placement:unavailable:MISSING'


# ---------------------------------------------------------------------------------------------------------------------------------
# the paths with a hand-written placement (one decision at a time)
# ---------------------------------------------------------------------------------------------------------------------------------
SENT = '猫が庭へ歩いた。'


def base_map(**over):
    m = {'歩く': F.answer('P_MOVE'), '猫': F.answer('ANIMAL'), '庭': F.answer('PLACE')}
    m.update(over)
    return m


def test_path_u_reads_a_sentence_whose_every_word_has_a_direct_type_and_says_where_each_role_came_from():
    q = F.MapQuery(base_map())
    out = read(SENT, q)
    assert out['readable'] is True
    c = out['clauses'][0]
    assert c['predicate'] == '歩く' and c['roles'] == {'agent': '猫', 'goal': '庭'} and (c['polarity'], c['tense'], c['modality'], c['voice']) == ('+', 'past', None, 'active')
    assert list(c)[-2:] == ['predicate_basis', 'role_basis']
    assert c['predicate_basis'] == 'placement_direct:P_MOVE'
    assert c['role_basis'] == {'agent': 'placement_direct:ANIMAL', 'goal': 'placement_direct:PLACE'}
    assert b1.judge({'readable': True, 'clauses': [{'predicate': '歩く', 'roles': {'agent': '猫', 'goal': '庭'}, 'polarity': '+', 'tense': 'past', 'modality': None, 'voice': 'active'}],
                     'relations': [], 'must_not': []}, 'ja', out)['verdict'] == 'correct'
    assert sorted(set(q.calls)) == sorted(['歩く', '猫', '庭']) and all(isinstance(t, str) for t in q.calls)       # only the words of the sentence, nothing else
    assert out['unsupported'] == SR.read(SENT, placement=None)['unsupported']                                      # what the reader said stays on the output


def test_without_a_placement_the_same_sentence_is_the_same_refusal_as_before():
    out = SR.read(SENT, placement=None)
    assert out['readable'] is False and len(out['abstain']['reasons']) == 1 and not out['abstain']['reasons'][0].startswith('PLACEMENT_')


@pytest.mark.parametrize('over,prefix', [
    ({'歩く': F.answer('P_STATE')}, 'PLACEMENT_FRAME_NOT_READ:P_STATE'),
    ({'歩く': F.answer('P_GIVE')}, 'PLACEMENT_FRAME_NOT_READ:P_GIVE'),
    ({'歩く': F.answer('PLACE')}, 'PLACEMENT_NOT_PREDICATE_TYPE'),
    ({'歩く': F.bare('UNPLACED')}, 'PLACEMENT_UNPLACED:predicate:歩く'),
    ({'歩く': F.answer(['P_MOVE', 'P_ACT'])}, 'PLACEMENT_MULTIPLE:predicate:歩く'),
    ({'歩く': F.answer('P_MOVE', origin='estimated', basis='proximity', decided_by=None)}, 'PLACEMENT_ESTIMATED_NEAR:predicate:歩く'),
    ({'庭': F.answer('PERSON')}, 'PLACEMENT_TYPE_MISMATCH:P_MOVE:へ:PERSON'),
    ({'庭': F.answer(['PLACE', 'TIME'])}, 'PLACEMENT_MULTIPLE:へ:庭'),
    ({'庭': F.answer('PLACE', origin='estimated', basis='generated', decided_by=['gen_definition'])}, 'PLACEMENT_ESTIMATED_GENERATED:へ:庭'),
    ({'庭': F.answer('PLACE', decided_by=['gen_definition'])}, 'PLACEMENT_DIRECT_VIA_GENERATED:へ:庭'),
    ({'庭': F.bare('UNPLACED')}, 'PLACEMENT_UNPLACED:へ:庭'),
    ({'庭': F.bare('NO_PLACEMENT', 'MISSING')}, 'PLACEMENT_NO_PLACEMENT:MISSING:へ:庭'),
    ({'猫': F.answer('PLACE')}, 'PLACEMENT_TYPE_MISMATCH:P_MOVE:が:PLACE'),
    # W3-b2 (proposal): [ANIMAL, PERSON] is now READ (every candidate is in the agent's set: K95); a split with a candidate outside stays refused
    ({'猫': F.answer(['ANIMAL', 'ABSTRACT'])}, 'PLACEMENT_MULTIPLE:が:猫'),
    ({'猫': F.bare('UNKNOWN')}, 'PLACEMENT_UNKNOWN:が:猫'),
])
def test_path_u_abstains_with_the_typed_reason_of_the_first_decision_that_fails(over, prefix):
    out = read(SENT, F.MapQuery(base_map(**over)))
    rs = reasons(out)
    assert len(rs) == 2 and rs[0] == SR.read(SENT, placement=None)['abstain']['reasons'][0] and rs[1].startswith(prefix), rs
    assert out['abstain']['kind'] == 'not_supported'


def test_path_u_a_particle_that_is_not_in_the_frame_of_the_type_is_not_read():
    out = read('猫が庭に歩いた。', F.MapQuery(base_map()))
    assert reasons(out)[1].startswith('PLACEMENT_TYPE_MISMATCH:P_MOVE:に:PLACE')           # に is in the frame (time), but 庭 is not a time
    out = read('猫が庭を歩いた。', F.MapQuery(base_map()))
    assert out['readable'] is False                                                          # を of a verb of movement: never read here


def test_path_u_the_reader_name_that_is_decided_must_agree_with_the_table():
    # a で-phrase the reader calls `means` (a vehicle) is not turned into a place because a placement says PLACE
    out = read('猫が車で庭へ歩いた。', F.MapQuery(base_map(**{'車': F.answer('PLACE')})))
    assert reasons(out)[1].startswith('PLACEMENT_READER_DISAGREES:instrument:place')


def test_path_u_a_tie_between_two_rows_is_an_abstention(monkeypatch):
    rows = R.TYPED_FRAMES['P_MOVE'] + (('place', ('へ',), ('PLACE',), 'arg'),)
    monkeypatch.setitem(R.TYPED_FRAMES, 'P_MOVE', rows)
    out = read(SENT, F.MapQuery(base_map()))
    assert reasons(out)[1].startswith('PLACEMENT_ROLE_TIE')


def test_path_u_a_gate_five_adjunct_is_read_only_with_more_than_slot_evidence():
    s = '猫が夜に庭へ歩いた。'
    slots = F.MapQuery(base_map(**{'夜': F.answer('TIME', decided_by=['role@codex:a'])}))
    assert reasons(read(s, slots))[1].startswith('PLACEMENT_SLOT_EVIDENCE_ONLY:に:夜')
    ok = F.MapQuery(base_map(**{'夜': F.answer('TIME', decided_by=['definition', 'role@codex:a'])}))
    out = read(s, ok)
    assert out['readable'] and out['clauses'][0]['roles'] == {'agent': '猫', 'time': '夜', 'goal': '庭'}
    assert out['clauses'][0]['role_basis']['time'] == 'placement_direct:TIME'


def test_path_u_does_not_touch_voice_polarity_tense_or_modality():
    base = F.MapQuery(base_map())
    neg = read('猫が庭へ歩かなかった。', base)
    assert neg['readable'] and neg['clauses'][0]['polarity'] == '-'
    modal = read('猫が庭へ歩きたい。', F.MapQuery(base_map()))
    assert modal['readable'] is False and reasons(modal)[1].startswith('PLACEMENT_REREAD_ABSTAINS:')
    q = read('猫が庭へ歩いたか。', F.MapQuery(base_map()))
    assert q['readable'] is False


def test_path_u_leaves_a_sentence_the_reader_calls_ambiguous_alone():
    # は makes the reader say `ambiguous frame role`: a type does not override what the reader itself says it cannot split
    q = F.MapQuery(base_map())
    out = read('猫は庭へ歩いた。', q)
    assert out['readable'] is False and len(reasons(out)) == 1 and q.calls == []


def test_path_s4_reads_a_part_the_frame_left_over_as_a_time_and_says_so():
    q = F.MapQuery({'夜': F.answer('TIME', decided_by=['definition'])})
    out = read('母が夜、手紙を書いた。', q)
    assert out['readable'] is True
    c = out['clauses'][0]
    assert c['roles'] == {'agent': '母', 'patient': '手紙', 'time': '夜'} and 'predicate_basis' not in c and c['role_basis'] == {'time': 'placement_direct:TIME'}
    assert list(c)[-1] == 'role_basis' and q.calls == ['夜']


@pytest.mark.parametrize('answer_,prefix', [
    (F.answer('TIME', decided_by=['role@codex:a']), 'PLACEMENT_SLOT_EVIDENCE_ONLY:part:夜'),
    (F.answer(['TIME', 'PLACE']), 'PLACEMENT_MULTIPLE:part:夜'),
    (F.answer('TIME', origin='estimated', basis='generated', decided_by=['gen_definition']), 'PLACEMENT_ESTIMATED_GENERATED:part:夜'),
    (F.answer('TIME', decided_by=['gen_definition']), 'PLACEMENT_DIRECT_VIA_GENERATED:part:夜'),
    (F.answer('PLACE', decided_by=['definition']), 'PLACEMENT_PART_NO_ROLE:PLACE:∅'),
    (F.answer('PERSON', decided_by=['definition']), 'PLACEMENT_PART_NO_ROLE:PERSON:∅'),
    (F.bare('UNPLACED'), 'PLACEMENT_UNPLACED:part:夜'),
])
def test_path_s4_abstains_unless_the_part_is_a_direct_time(answer_, prefix):
    out = read('母が夜、手紙を書いた。', F.MapQuery({'夜': answer_}))
    assert reasons(out)[0] == 'NO_SUPPORTED_CLAUSE' and reasons(out)[1].startswith(prefix), reasons(out)


@pytest.mark.parametrize('text,prefix', [
    ('母がそっと手紙を書いた。', 'PLACEMENT_PART_NOT_NP:副詞'),
    # W3-b2 (proposal): この is now an expressed mark (K97 D1): the unread one of the question word is どの
    ('母がどの夜、手紙を書いた。', 'PLACEMENT_PART_NOT_ISOLATED'),
    ('そして母が夜、手紙を書いた。', 'PLACEMENT_PART_MARKER:conn'),
    ('母が夜だけ手紙を書いた。', None),
    ('母が三回、手紙を書いた。', None),
    ('母が夜の手紙を書いた。', None),
    ('母が夜、手紙を書いた。弟が夜、本を読んだ。', None),
])
def test_path_s4_registered_unread_constructions(text, prefix):
    q = F.MapQuery({w: F.answer('TIME', decided_by=['definition']) for w in ('夜', '三', '回', '三回', 'そっと', 'この夜')})
    out = read(text, q)
    plain = SR.read(text, placement=None)
    if prefix is None:
        # not a part this path reads: nothing is added (or only a marker says why)
        assert out['readable'] == plain['readable']
        if not plain['readable']:
            assert out['abstain']['reasons'][0] == plain['abstain']['reasons'][0]
            assert all(r.startswith('PLACEMENT_PART_MARKER') for r in out['abstain']['reasons'][1:])
    elif prefix == 'PLACEMENT_PART_NOT_NP:副詞' and out['readable'] and W1A5.touched(text):
        assert out['clauses'][0]['flags']['adverbs'] and 'そっと' not in out['clauses'][0]['roles'].values()     # W1-a5 (10G K213): the adverb is a mark, not a part
    else:
        assert out['readable'] is False and reasons(out)[1].startswith(prefix), reasons(out)


def _s4_plan(text, mapping):
    """The S4 plan on the reader's own clause of `text` (called directly: what the plan says whatever the trigger says)."""
    view = R.document_view({'d': text})
    frame = [c for c in view.clauses if c.rule == 'frame']
    assert len(frame) == 1
    return R.typed_plan_s4_ja(text, R._tokens(text), frame[0], F.MapQuery(mapping))


@pytest.mark.parametrize('text,expected', [
    ('母が三回、手紙を書いた。', 'PLACEMENT_PART_MARKER:quant'),
    ('弟が冬ばかり本を読んだ。', 'PLACEMENT_PART_MARKER:quant'),
    ('弟が冬しか本を読まなかった。', 'PLACEMENT_PART_MARKER:quant'),
    ('母が冬の夜、窓を閉めた。', 'PLACEMENT_PART_NO_ROLE:TIME:の'),
])
def test_path_s4_plan_registered_marks_and_constructions_called_directly(text, expected):
    mapping = {w: F.answer('TIME', decided_by=['definition']) for w in ('冬', '夜', '三', '回', '三回')}
    typed, why = _s4_plan(text, mapping)
    assert typed is None and why == expected, why


def test_a_sentence_the_reader_already_reads_is_returned_byte_for_byte_with_or_without_a_placement():
    q = F.FixtureQuery()
    for text in SAMPLES + [r['input'] for r in DATA]:
        plain = SR.read(text, placement=None)
        if plain['readable']:
            assert json.dumps(read(text, F.FixtureQuery()), ensure_ascii=False) == json.dumps(plain, ensure_ascii=False), text
    assert q.misses == []


# ---------------------------------------------------------------------------------------------------------------------------------
# the data (frozen before this file): every row, with the fixture
# ---------------------------------------------------------------------------------------------------------------------------------
def test_the_data_has_the_registered_shape():
    ja = [r for r in DATA if r['lang'] == 'ja']
    u = [r for r in ja if r['path'] == 'U']; s4 = [r for r in ja if r['path'] == 'S4']; en = [r for r in DATA if r['path'] == 'EN']
    assert len(u) >= 60 and len(s4) >= 60 and len(en) >= 16
    for t in CT.PRED_TYPES:
        assert sum(r['pred_type'] == t for r in u) >= 4, t
    for group in (u, s4):
        n_read = sum(r['entry_expect'] == 'read' for r in group)
        assert 0.4 * len(group) <= n_read <= 0.6 * len(group), (len(group), n_read)
    assert all(r['entry_expect'] == 'abstain' for r in en)
    assert sum(r['path'] == 'EN' and 'unknown predicate' in r['construction'] for r in DATA) >= 8
    assert sum(r['path'] == 'EN' and 'adjunct' in r['construction'] for r in DATA) >= 8


W3B4_NOW_READ = {'W3B1-U-090', 'W3B1-U-091', 'W3B1-U-092'}     # P_ACT rows (へ + PLACE) of ja_r8, registered as refused before the second table existed


def _exception(row):
    return next((e for e in EXCEPTIONS if e['id'] == row['id']), None)


@pytest.mark.parametrize('row', DATA, ids=[r['id'] for r in DATA])
def test_every_row_of_the_new_data_with_the_fixture(row):
    q = F.FixtureQuery()
    out = read(row['input'], q, row['lang'])
    assert q.misses == [], q.misses
    exc = _exception(row)
    if exc is not None:
        # a row whose registered expectation the entry does not meet is declared in w3b1_expect_exceptions.json with the exact output it gives
        # (checked in test_declared_exceptions_are_real...). A declared row that the entry READS must be the base commit's own reading (not this path).
        if exc['kind'] == 'baseline_reads':
            assert out == SR.read(row['input'], row['lang'], placement=None)
        return
    if out['readable'] and row['entry_expect'] == 'abstain' and W1A5.touched(row['input']):
        # W1-a5 (10G K210/K213): an adverb sentence is read now, the adverb as a mark (`flags.adverbs`). What the S4 row forbids still holds: the adverb is no role of the clause (`must_not`).
        c = out['clauses'][row['expect']['must_not'][0]['clause']]
        assert all(c['roles'].get(m['role']) != m['value'] for m in row['expect']['must_not']) and c['flags']['adverbs'], c
        return
    verdict = b1.judge(row['expect'], row['lang'], out)['verdict']
    assert verdict in ('correct', 'abstain'), (verdict, out['clauses'])           # never a wrong or half reading, whatever the row says
    if row['id'] in W3B4_NOW_READ:
        # W3-b4: P_ACT is a type the second table reads (goal/へ/PLACE): the row that W3-b1 registered as refused (FRAME_NOT_READ) is read, and read correctly
        assert out['readable'] is True and verdict == 'correct', (out['abstain'], out['clauses'])
        return
    if row['entry_expect'] == 'read':
        assert out['readable'] is True and verdict == 'correct', (out['abstain'], out['clauses'])
    else:
        assert out['readable'] is False, out['clauses']
        if row['expect_reason_prefix']:
            rs = out['abstain']['reasons']
            assert len(rs) >= 2 and rs[1].startswith(row['expect_reason_prefix']), rs


def test_declared_exceptions_are_real_and_each_has_a_reason():
    ids = {r['id']: r for r in DATA}
    assert len({e['id'] for e in EXCEPTIONS}) == len(EXCEPTIONS)
    for e in EXCEPTIONS:
        assert e['id'] in ids and e.get('why') and e['kind'] in ('trigger_not_reached', 'baseline_reads', 'reason_differs', 'row_returned_to_abstain')
        row = ids[e['id']]
        out = read(row['input'], F.FixtureQuery(), row['lang'])
        # the exact output is pinned: a change of behaviour (better or worse) shows here
        assert out['readable'] == e['observed']['readable']
        if not out['readable']:
            assert out['abstain']['reasons'] == e['observed']['reasons'], e['id']
        else:
            assert [c['roles'] for c in out['clauses']] == e['observed']['roles'], e['id']
        # and it is a real difference from the registered expectation (an exception that no longer differs is stale)
        mismatch = (row['entry_expect'] == 'read') != out['readable']
        if not mismatch and not out['readable'] and row['expect_reason_prefix']:
            rs = out['abstain']['reasons']
            mismatch = not (len(rs) >= 2 and rs[1].startswith(row['expect_reason_prefix']))
        if not mismatch and out['readable']:
            mismatch = b1.judge(row['expect'], row['lang'], out)['verdict'] != 'correct'
        assert mismatch, e['id']
        if e['kind'] == 'baseline_reads':
            assert out['readable'] and out == SR.read(row['input'], row['lang'], placement=None)
        else:
            assert not out['readable']        # a declared difference of the other two kinds is always an abstention, never a reading


# ---------------------------------------------------------------------------------------------------------------------------------
# A3: direct only
# ---------------------------------------------------------------------------------------------------------------------------------
def _nothing_new(mapper, label):
    baseline = {}
    for text in SAMPLES + [r['input'] for r in DATA]:
        plain = SR.read(text, placement=None)
        got = read(text, F.FixtureQuery(mapper=mapper))
        if plain['readable']:
            assert got == plain, (label, text)
        else:
            assert got['readable'] is False, (label, text, got['clauses'])
            assert got['abstain']['reasons'][0] == plain['abstain']['reasons'][0], (label, text)


def test_estimated_proximity_answers_alone_read_nothing_new():
    _nothing_new(lambda a: F.to_estimated(a, 'proximity'), 'estimated_proximity')


def test_estimated_generated_answers_alone_read_nothing_new():
    _nothing_new(lambda a: F.to_estimated(a, 'generated'), 'estimated_generated')


def test_multiple_answers_alone_read_nothing_new():
    _nothing_new(F.to_multiple, 'multiple')


def test_the_fakes_of_the_direct_only_test_satisfy_the_contract():
    from verantyx import event_cross as EC
    n = {'estimated': 0, 'multiple': 0}
    for term, a in F.FIXTURE['answers'].items():
        for fake, key in ((F.to_estimated(a, 'proximity'), 'estimated'), (F.to_estimated(a, 'generated'), 'estimated'), (F.to_multiple(a), 'multiple')):
            assert not EC.PlaceResult.from_coarse_query(fake).invariant_problems(), (term, fake)
            n[key] += fake != a
    assert n['estimated'] > 100 and n['multiple'] > 100
    # and with the real answers the data does get read (the fakes are not trivially empty)
    assert sum(read(r['input'], F.FixtureQuery(), r['lang'])['readable'] for r in DATA if r['entry_expect'] == 'read') > 0


# ---------------------------------------------------------------------------------------------------------------------------------
# no placement: the output is the base commit's, to the byte
# ---------------------------------------------------------------------------------------------------------------------------------
def _base_module():
    src = subprocess.run(['git', '-C', str(TREE), 'show', '%s:verantyx/semantic_read.py' % BASE_COMMIT], capture_output=True, check=True).stdout
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_base_w3b1', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src.decode('utf-8'), 'verantyx/semantic_read.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    return mod


def test_without_a_placement_every_output_is_the_base_commits_output_byte_for_byte():
    base = _base_module()
    texts = list(dict.fromkeys(SAMPLES + [r['input'] for r in DATA] + ['犬が猫を追いかけた。', 'おはようございます。', '弟は兄より背が高い。', 'The dog chased the cat.']))
    for text in texts:
        if W1A5.touched(text):      # W1-a5 (10G K210): a sentence W1-a5 changed is one of the four registered kinds; every other sentence is compared byte for byte as before
            assert W1A5.documented(base.read(text), SR.read(text, placement=None)), text
            continue
        expect = json.dumps(base.read(text), ensure_ascii=False)
        assert json.dumps(SR.read(text), ensure_ascii=False) == expect, text
        assert json.dumps(SR.read(text, placement=None), ensure_ascii=False) == expect, text
        out = SR.read(text)
        assert all('predicate_basis' not in c and 'role_basis' not in c for c in out['clauses']), text
    # an empty VERA_PLACEMENT is no placement
    os.environ['VERA_PLACEMENT'] = ''
    try:
        assert json.dumps(SR.read(SENT), ensure_ascii=False) == json.dumps(base.read(SENT), ensure_ascii=False)
    finally:
        del os.environ['VERA_PLACEMENT']


def test_the_environment_variable_and_its_order_against_the_argument(monkeypatch):
    plain = SR.read(SENT, placement=None)
    monkeypatch.setenv('VERA_PLACEMENT', '/no/such/placement/dir')
    from_env = SR.read(SENT)
    assert from_env['readable'] is False and any(r.startswith('PLACEMENT_NO_PLACEMENT:MISSING') for r in from_env['abstain']['reasons'])
    assert SR.read(SENT, placement=None) == plain                                     # None: no placement, whatever the variable says
    mapped = SR.read(SENT, placement=F.MapQuery(base_map()))
    assert mapped['readable'] is True                                                 # an argument beats the variable
    monkeypatch.delenv('VERA_PLACEMENT')
    monkeypatch.setenv('VERA_COARSE_PLACEMENT', '/no/such/placement/dir')
    assert SR.read(SENT) == plain                                                     # the placement module's own variable is not read here


def test_a_path_that_does_not_exist_is_no_placement_not_an_error():
    out = SR.read(SENT, placement='/no/such/placement/dir')
    assert out['readable'] is False
    assert out['abstain']['reasons'][1].startswith('PLACEMENT_NO_PLACEMENT:MISSING:')


# ---------------------------------------------------------------------------------------------------------------------------------
# main(): --placement
# ---------------------------------------------------------------------------------------------------------------------------------
def run_main(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = SR.main(argv)
    return buf.getvalue(), code


def _base_run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = _base_module().main(argv)
    return buf.getvalue(), code


@pytest.fixture
def fake_coarse(monkeypatch):
    return F.patch_coarse_place(monkeypatch)


@pytest.mark.parametrize('argv', [['--text=猫が庭へ歩いた。', '--placement=/fake/dir'], ['--text=猫が庭へ歩いた。', '--placement', '/fake/dir'],
                                  ['--placement=/fake/dir', '--text=猫が庭へ歩いた。'], ['--placement', '/fake/dir', '--text', '猫が庭へ歩いた。']])
def test_placement_argument_forms(argv, fake_coarse):
    calls, fq = fake_coarse
    out, code = run_main(argv)
    obj = json.loads(out)
    assert code == 0 and obj['readable'] is True and obj['clauses'][0]['predicate_basis'] == 'placement_direct:P_MOVE'
    assert {c['placement'] for c in calls} == {'/fake/dir'} and all(c['context_role'] is None and c['context_predicate'] is None for c in calls)
    assert fq.misses == []


def test_placement_argument_beats_the_variable(fake_coarse, monkeypatch):
    calls, _ = fake_coarse
    monkeypatch.setenv('VERA_PLACEMENT', '/from/env')
    run_main(['--text=猫が庭へ歩いた。', '--placement=/from/arg'])
    assert {c['placement'] for c in calls} == {'/from/arg'}


@pytest.mark.parametrize('argv', [['--text=猫が庭へ歩いた。', '--placement'], ['--text=猫が庭へ歩いた。', '--placement='], ['--text=猫が庭へ歩いた。', '--placement', ''],
                                  ['--text=猫が庭へ歩いた。', '--placement=/a', '--placement=/b'], ['--text=猫が庭へ歩いた。', '--placement=/a', '--placement', '/b']])
def test_placement_argument_without_a_value_or_given_twice_is_a_bad_argument(argv, fake_coarse):
    out, code = run_main(argv)
    assert code == 2 and json.loads(out)['error']['type'] == 'BAD_ARGUMENTS'
    assert fake_coarse[0] == []


@pytest.mark.parametrize('argv', [['--text=猫が庭へ歩いた。', '--pl=/p'], ['--text=猫が庭へ歩いた。', '--p=/p'], ['--text=猫が庭へ歩いた。', '--placemen=/p'],
                                  ['--text=猫が庭へ歩いた。', '--Placement=/p'], ['--text=猫が庭へ歩いた。', '--', '--placement=/p'],
                                  ['--text=猫が庭へ歩いた。', '--', '--placement', '/p']])
def test_abbreviations_and_what_follows_double_dash_answer_as_the_base_commit_did(argv, fake_coarse):
    out, code = run_main(argv)
    assert (out, code) == _base_run(argv) and code == 2
    assert fake_coarse[0] == []


def test_a_refused_input_answers_the_same_with_a_placement(fake_coarse):
    for argv in (['--text=', '--placement=/p'], ['--placement=/p'], ['--text=犬が走った。', '--lang=en', '--placement=/p']):
        plain = [a for a in argv if not a.startswith('--placement')]
        assert run_main(argv) == run_main(plain)


def test_the_default_output_loads_no_placement_module_and_every_module_is_in_the_tree():
    def child(code):
        env = {'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(TREE)}
        return subprocess.run([sys.executable, '-c', code], cwd=str(TREE), env=env, capture_output=True, text=True, timeout=120)
    plain = ("import sys, io, contextlib; from verantyx import semantic_read as s\n"
             "buf = io.StringIO()\n"
             "with contextlib.redirect_stdout(buf): s.main(['--text=猫が庭へ歩いた。'])\n"
             "print([m for m in ('verantyx.coarse_place', 'verantyx.coarse_types', 'verantyx.event_cross') if m in sys.modules])\n")
    r = child(plain)
    assert r.returncode == 0 and r.stdout.strip() == '[]', (r.stdout, r.stderr)
    with_p = ("import sys, io, contextlib; from verantyx import semantic_read as s\n"
              "buf = io.StringIO()\n"
              "with contextlib.redirect_stdout(buf): s.main(['--text=猫が庭へ歩いた。', '--placement=/no/such/dir'])\n"
              "print('verantyx.coarse_place' in sys.modules, 'verantyx.event_cross' in sys.modules)\n"
              "print([m.__file__ for n, m in sys.modules.items() if n.startswith('verantyx') and getattr(m, '__file__', None) and not m.__file__.startswith(%r)])" % (str(TREE) + '/'))
    r = child(with_p)
    assert r.returncode == 0 and r.stdout.split('\n')[0] == 'True False' and r.stdout.split('\n')[1] == '[]', (r.stdout, r.stderr)


# ---------------------------------------------------------------------------------------------------------------------------------
# English: not read, one reason added
# ---------------------------------------------------------------------------------------------------------------------------------
class _Everything(F.MapQuery):
    """Answers every word with one direct type (for the English tests: no word of the sentence is looked up by a fixed key)."""
    def __init__(self, top, **kw):
        super().__init__({}); self.top, self.kw = top, kw

    def query(self, term):
        self.calls.append(term); return F.answer(self.top, term=term, **self.kw)


def test_english_unknown_predicate_gets_one_typed_reason_and_is_never_read():
    text = 'Ken sprinted the paint.'                                    # a known verb elsewhere, the verb of the clause is not in the closed list
    plain = SR.read(text, placement=None)
    assert plain['abstain']['reasons'] == ['UNKNOWN_PREDICATE:sprint']
    out = read(text, F.MapQuery({'sprint': F.bare('UNPLACED')}))
    assert out['abstain']['reasons'] == ['UNKNOWN_PREDICATE:sprint', 'PLACEMENT_UNPLACED:predicate:sprint']
    # a placement that types the verb direct still does not read English
    q = _Everything('P_MOVE')
    out = read(text, q)
    assert out['readable'] is False and out['abstain']['reasons'] == ['UNKNOWN_PREDICATE:sprint', 'PLACEMENT_FRAME_NOT_READ:en']
    assert q.calls == ['sprint']                                           # the lemma of the verb only
    out = read(text, _Everything('PERSON'))
    assert out['abstain']['reasons'][1] == 'PLACEMENT_FRAME_NOT_READ:en'    # whatever the type, English is not read


def test_english_sentences_the_entry_reads_today_are_unchanged_by_a_placement():
    for text in ('The dog chased the cat.', 'The teacher gave the student a map.'):
        assert read(text, F.FixtureQuery(), 'en') == SR.read(text, 'en', placement=None)


def test_english_with_no_word_of_the_closed_list_gets_the_unidentified_reason_and_asks_nothing():
    q = F.FixtureQuery()
    out = read('The dog sprinted to the park.', q)
    assert out['abstain']['reasons'] == ['UNKNOWN_PREDICATE', 'PLACEMENT_PREDICATE_UNIDENTIFIED'] and q.calls == []


def test_english_adjunct_refusals_are_not_touched_by_a_placement():
    for text in ('The boy opened the window at night.', 'The girl cleaned the room quietly.'):
        assert read(text, _Everything('PLACE'), 'en') == SR.read(text, 'en', placement=None)
