"""W3-b5: the generated frame of a predicate as a REFERENCE for what an adjunct (or a に phrase) may be read as. The query gains the key `frame_generated`; the second table (K62 v2)
gains a kind of row, `frame_required`: a row that the plan reads only when the generated frame of the predicate holds the particle with a type that the row expects and the
filler (a DECIDED direct answer, or every candidate of a split one) is of that type. The table of kinds (`license`), the 16 rows (none is left after table change record 2), the control flow, the contract of `frame_generated`,
the reasons, the data (tests/reading_soundness/ja_r11.jsonl) and these tests were registered in docs/READING_SOUNDNESS.md section 10F (K200-K206) in this order: registration,
data (frozen), tests (frozen), code. The placements the tests open are fakes made from the `placement` of each row of the data (a contract-conforming answer; `answer_of`); the only real
placements are r7 and r8, read only, for the tests of the query (skipped with ENV_MISSING when they are not there).
Run under a clean environment (env -i): a VERA_PLACEMENT left in the shell would change the default path of the entry.
"""
import ast
import collections
import copy
import difflib
import importlib.util
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent
RS = TREE / 'tests' / 'reading_soundness'
A = TREE / 'artifacts' / 'w3-b5'
BASE_COMMIT = '7494ba2'
R7 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1'
R8 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'
SIX = ('が', 'を', 'に', 'へ', 'から', 'で')


def _load_by_path(name, path):
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


F = _load_by_path('w3b2_fakes_in_test_w3b5', RS / 'w3b2_fakes.py')

from tools.bank_score.v2 import b1    # noqa: E402
from verantyx import coarse_place as CP    # noqa: E402
from verantyx import coarse_types as CT    # noqa: E402
from verantyx import event_cross as EC    # noqa: E402
from verantyx import semantic_read as SR    # noqa: E402
from verantyx import semantic_reader as R    # noqa: E402

DOCS = (TREE / 'docs' / 'READING_SOUNDNESS.md').read_text(encoding='utf-8')
DATA_FILE = RS / 'ja_r11.jsonl'
DATA = [json.loads(l) for l in DATA_FILE.read_text(encoding='utf-8').splitlines() if l.strip()]
NARROWED_FILE = A / 'narrowed_rows.json'            # K206: rows taken out of the table after a misread (written only if that happened)
NARROWED = json.loads(NARROWED_FILE.read_text(encoding='utf-8')) if NARROWED_FILE.exists() else {'rows': {}}
NARROWED_ROWS = NARROWED['rows']
EXC_FILE = A / 'expect_exceptions.json'              # a frozen expectation that a fact of the reader (not a misread) made wrong: declared with the observation
EXCEPTIONS = {e['id']: e for e in json.loads(EXC_FILE.read_text(encoding='utf-8'))['exceptions']} if EXC_FILE.exists() else {}
READ_TYPES = ('P_MOVE', 'P_COMMUNICATE', 'P_ACT', 'P_CREATE', 'P_EMOTION')
ROLE_GROUPS = ('de_place', 'de_instrument', 'de_cause', 'ni_recipient', 'ni_goal', 'ni_time', 'ni_purpose', 'ni_other', 'mechanism')


@pytest.fixture(autouse=True)
def _no_placement_in_the_environment(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)


def git(*args):
    return subprocess.run(['git', '-C', str(TREE)] + list(args), capture_output=True, check=True).stdout.decode('utf-8')


def block_lines(name):
    m = re.search(r'<!-- BEGIN table:%s -->\n(.*?)<!-- END table:%s -->' % (name, name), DOCS, re.S)
    assert m, name
    return [line for line in m.group(1).splitlines() if line.startswith('|') and not set(line) <= set('|- ')][1:]


def block(name, docs=None):
    return [[c.strip().strip('`') for c in line.strip().strip('|').split('|')] for line in block_lines(name)]


KIND = {'arg': '項', 'adjunct': '付加'}


# ===================================================================================================================================
# K201 / L2: the table of kinds
# ===================================================================================================================================
def test_the_table_of_the_docs_is_the_rows_of_the_code_with_their_kind_in_the_same_order():
    got = [tuple(r) for r in block('w3b5_frames')]
    want = [(t, role, '/'.join(parts), ' '.join(exp), KIND[kind], lic) for (t, role, parts, exp, kind, lic) in R.typed_frames_w3b5_rows()]
    assert got == want and len(got) == 17 + 0          # 17 rows of the kind table and, after table change records 1 and 2 (K206), none of the 16 registered rows of the kind frame_required


def test_the_first_seventeen_rows_are_the_rows_of_the_second_table_character_for_character_and_have_the_kind_table():
    old = block_lines('w3b4_frames')
    new = block_lines('w3b5_frames')
    assert len(old) == 17
    for o, n in zip(old, new[:17]):
        assert n.rstrip().endswith(' | table |') and n.rstrip()[:-len(' table |')].rstrip() == o.rstrip()
    assert [r[5] for r in block('w3b5_frames')] == ['table'] * 17 + ['frame_required'] * 0
    v2 = R.typed_frames_v2()
    code = [(t, role, parts, exp, kind) for t, rows in v2.items() for (role, parts, exp, kind) in rows]
    rows = [(t, role, parts, exp, kind) for (t, role, parts, exp, kind, lic) in R.typed_frames_w3b5_rows() if lic == 'table']
    assert rows == code


def test_the_rows_of_the_kind_frame_required_are_the_registered_table_in_the_same_order():
    reg = [(t, role, '/'.join(parts), ' '.join(exp), KIND[kind]) for t, rows in R.TYPED_FRAMES_FRAME_REQUIRED_W3B5.items() for (role, parts, exp, kind) in rows]
    assert reg == [tuple(r[:5]) for r in block('w3b5_frames')[17:]]
    assert [t for t, rows in R.TYPED_FRAMES_FRAME_REQUIRED_W3B5.items()] == ['P_MOVE', 'P_COMMUNICATE', 'P_ACT', 'P_CREATE', 'P_EMOTION']
    assert R.W3B5_LICENSES == ('table', 'frame_required')
    for r in block('w3b5_frames'): assert r[5] in R.W3B5_LICENSES


def test_the_rows_of_both_kinds_have_the_roles_the_types_and_the_particles_of_the_convention_and_no_word():
    noun_types, roles = set(CT.NOUN_TYPES), set(b1.ROLES)
    for (t, role, parts, exp, kind, lic) in R.typed_frames_w3b5_rows():
        assert t in CT.PRED_TYPES and role in roles and kind in ('arg', 'adjunct') and lic in R.W3B5_LICENSES
        assert len(parts) == 1 and parts[0] in SIX
        assert exp and set(exp) <= noun_types and list(exp) == list(dict.fromkeys(exp))
        assert (kind == 'adjunct') == (role in ('time', 'place'))
        if role in EC.EXPECTED_TYPES: assert frozenset(exp) == EC.EXPECTED_TYPES[role], (t, role)
    for row in block('w3b5_frames'):
        assert re.fullmatch(r'P_[A-Z]+', row[0]) and row[1] in roles and row[2] in SIX and set(row[3].split()) <= noun_types and row[4] in ('項', '付加')


def test_two_rows_of_one_type_and_one_particle_in_both_kinds_have_disjoint_expected_types():
    seen = collections.defaultdict(list)
    for (t, role, parts, exp, kind, lic) in R.typed_frames_w3b5_rows():
        for other in seen[(t, parts[0])]: assert not set(other) & set(exp), (t, parts, exp, other)
        seen[(t, parts[0])].append(exp)
    seen = collections.defaultdict(list)
    for t, role, part, exp, kind, lic in block('w3b5_frames'):
        for other in seen[(t, part)]: assert not set(other.split()) & set(exp.split()), (t, part)
        seen[(t, part)].append(exp)


def test_the_rows_that_are_read_only_when_the_frame_licenses_them_are_in_the_five_types_that_the_table_reads_and_not_in_the_second_table():
    v2 = R.typed_frames_v2()
    assert set(R.TYPED_FRAMES_FRAME_REQUIRED_W3B5) <= set(v2) and set(v2) == {'P_MOVE', 'P_COMMUNICATE', 'P_ACT', 'P_CREATE', 'P_EMOTION'}
    assert not set(R.TYPED_FRAMES_FRAME_REQUIRED_W3B5) & set(R.TYPED_FRAMES_NOT_READ_W3B4)
    rows_v2 = {(t, role, parts, exp) for t, rs in v2.items() for (role, parts, exp, kind) in rs}
    for t, rs in R.TYPED_FRAMES_FRAME_REQUIRED_W3B5.items():
        for (role, parts, exp, kind) in rs: assert (t, role, parts, exp) not in rows_v2      # the second table is not changed: no frame_required row is in it


def test_v1_is_inside_the_rows_of_the_kind_table_and_the_rows_of_the_gaps_of_the_second_table_are_only_the_rows_of_the_kind_frame_required():
    table_rows = {(t, role, parts[0], tuple(sorted(exp)), kind) for (t, role, parts, exp, kind, lic) in R.typed_frames_w3b5_rows() if lic == 'table'}
    for t, role, part, types, kind in CT.K62_FRAMES: assert (t, role, part, tuple(sorted(types)), kind) in table_rows, (t, role, part)
    req = {(t, role, parts[0]) for (t, role, parts, exp, kind, lic) in R.typed_frames_w3b5_rows() if lic == 'frame_required'}
    assert {r for r in req if r[1] in ('instrument', 'result', 'cause', 'beneficiary', 'companion', 'quotation')} == set()
    assert {r[2] for r in req} <= {'に', 'で'}                      # the rows of this ticket are the particles に and で only (after K206: に only)


def test_the_rows_of_the_kind_frame_required_are_inside_the_registered_sixteen():
    pre = (A / 'PREREG.md').read_text(encoding='utf-8')
    m = re.search(r'<!-- BEGIN table:w3b5_frames -->\n(.*?)<!-- END table:w3b5_frames -->', pre, re.S)
    reg = [[c.strip().strip('`') for c in l.strip().strip('|').split('|')] for l in m.group(1).splitlines() if l.startswith('|') and not set(l) <= set('|- ')][1:]
    reg_fr = {tuple(r[:5]) for r in reg if r[5] == 'frame_required'}
    assert len(reg_fr) == 16
    now = {(t, role, '/'.join(parts), ' '.join(exp), KIND[kind]) for t, rows in R.TYPED_FRAMES_FRAME_REQUIRED_W3B5.items() for (role, parts, exp, kind) in rows}
    for r in now:       # only narrowing: a row may go, or its types may be fewer, never a new row or a new type
        assert any(r[:3] == g[:3] and set(r[3].split()) <= set(g[3].split()) and r[4] == g[4] for g in reg_fr), r


def test_the_reasons_of_the_docs_are_the_names_of_the_code_in_the_same_order():
    names = [re.split(r'[:`]', r[0].strip('`'))[0] for r in block('w3b5_reasons')]
    assert names == list(R.W3B5_REASON_NAMES) == ['FRAME_GENERATED_DOES_NOT_LICENSE', 'PLACEMENT_FRAME_GENERATED_INVALID']


# ===================================================================================================================================
# K200: what is registered about the control flow: the base values, only insertions, the end of the file, the other files
# ===================================================================================================================================
def _frozen(name):
    for n in ast.parse(git('show', '%s:verantyx/semantic_reader.py' % BASE_COMMIT)).body:
        if isinstance(n, ast.Assign) and any(getattr(t, 'id', None) == name for t in n.targets): return ast.literal_eval(n.value)
    raise AssertionError(name)


def test_the_tables_and_the_reasons_of_the_base_commit_are_not_changed():
    for name in ('TYPED_FRAMES', 'TYPED_FRAMES_W3B4'):
        assert {k: tuple(tuple(r) for r in v) for k, v in getattr(R, name).items()} == {k: tuple(tuple(r) for r in v) for k, v in _frozen(name).items()}
    for name in ('TYPED_FRAMES_NOT_READ', 'TYPED_FRAMES_NOT_READ_W3B4'): assert getattr(R, name) == _frozen(name)
    assert tuple(R.W3B2_REASON_NAMES) == tuple(_frozen('W3B2_REASON_NAMES')) and len(R.W3B2_REASON_NAMES) == 8


def test_the_file_diff_against_the_base_commit_has_only_added_lines_in_the_two_files_of_the_ticket():
    d = git('diff', BASE_COMMIT, '--', 'verantyx/semantic_reader.py', 'verantyx/coarse_place.py')
    assert d.strip() and [l for l in d.splitlines() if l.startswith('-') and not l.startswith('---')] == []


def _top_level(src):
    out = {}
    for n in ast.parse(src).body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)): out[n.name] = ast.dump(n)
        elif isinstance(n, ast.Assign): out['='.join(ast.dump(t) for t in n.targets)] = ast.dump(n)
    return out


def test_in_the_reader_only_the_plan_of_w3b4_is_changed_and_in_the_query_file_only_the_query_function():
    for path, changed in (('verantyx/semantic_reader.py', {'typed_plan_u_w3b4_ja'}), ('verantyx/coarse_place.py', {'query'})):
        base = _top_level(git('show', '%s:%s' % (BASE_COMMIT, path)))
        now = _top_level((TREE / path).read_text(encoding='utf-8'))
        assert {k for k in base if now.get(k) != base[k]} == changed, path           # nothing of the base is gone or different but the one function
        assert set(now) - set(base), path                                             # something was added (the table, the readers, a private function of the query)


def test_the_plan_of_w3b4_only_gains_lines_and_the_end_of_the_reader_file_is_the_one_of_the_base_commit():
    def body(src):
        for n in ast.parse(src).body:
            if isinstance(n, ast.FunctionDef) and n.name == 'typed_plan_u_w3b4_ja': return ast.get_source_segment(src, n).splitlines()
    now = body((TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8'))
    base = body(git('show', '%s:verantyx/semantic_reader.py' % BASE_COMMIT))
    nd = list(difflib.ndiff(base, now))
    assert [l for l in nd if l.startswith('- ')] == [] and [l for l in nd if l.startswith('+ ')]
    last = lambda src: [ast.get_source_segment(src, n) for n in ast.parse(src).body[-3:]]
    assert last((TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')) == last(git('show', '%s:verantyx/semantic_reader.py' % BASE_COMMIT))
    assert R.typed_plan_u_w3b2_ja.ungated is R.typed_plan_u_w3b4_ja and R.typed_plan_u_w3b2_ja.__name__ == 'typed_plan_u_w3b4_ja_focus_gated'


def test_the_entry_the_convention_the_builder_and_the_other_files_that_the_ticket_does_not_name_are_not_changed():
    for path in ('verantyx/semantic_read.py', 'verantyx/coarse_types.py', 'verantyx/event_cross.py', 'verantyx/observe.py', 'tools/build_coarse_placement.py'):
        assert git('diff', BASE_COMMIT, '--', path) == '', path


def test_the_added_lines_of_the_two_files_hold_no_word_a_non_ascii_string_is_a_particle_or_a_docstring():
    allowed = {'で', 'に'}

    def literals(src):
        tree = ast.parse(src); doc = set()
        for n in ast.walk(tree):
            if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Module)) and n.body and isinstance(n.body[0], ast.Expr) and isinstance(getattr(n.body[0], 'value', None), ast.Constant):
                doc.add(id(n.body[0].value))
        c = collections.Counter()
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc and any(ord(ch) > 127 for ch in n.value): c[n.value] += 1
        return c
    for path in ('verantyx/semantic_reader.py', 'verantyx/coarse_place.py'):
        new = literals((TREE / path).read_text(encoding='utf-8')) - literals(git('show', '%s:%s' % (BASE_COMMIT, path)))
        assert set(new) <= allowed, (path, set(new) - allowed)


def test_the_only_readers_of_a_placement_answer_are_still_the_gate_the_adapter_and_the_one_reader_of_frame_generated():
    """W3-b4 K95: a field of the answer is read by the gate and the adapters only. The new reader of `frame_generated` reads that one key and no other field."""
    src = (TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'predicate_frame_generated')
    keys = {n.slice.value for n in ast.walk(fn) if isinstance(n, ast.Subscript) and isinstance(getattr(n.slice, 'value', None), str)}
    keys |= {n.args[0].value for n in ast.walk(fn) if isinstance(n, ast.Call) and getattr(n.func, 'attr', '') == 'get' and n.args and isinstance(n.args[0], ast.Constant)}
    assert keys <= {'frame_generated', 'origin', 'frame'}, keys
    plan = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == 'typed_plan_u_w3b4_ja')
    used = {n.slice.value for n in ast.walk(plan) if isinstance(n, ast.Subscript) and isinstance(getattr(n.slice, 'value', None), str)}
    assert not used & {'state', 'origin', 'top', 'decided_by', 'estimate_basis', 'frame_generated'}, used


# ===================================================================================================================================
# the fakes: a placement answer made from the `placement` of a row
# ===================================================================================================================================
def answer_of(word, spec):
    if 'state' in spec: return F.bare(spec['state'], term=word)
    if spec.get('namespace') == 'P':
        a = F.answer(spec['top'], decided_by=spec.get('decided_by', ['seed']), term=word)
        a['namespace'] = 'P'
        if spec.get('origin') == 'estimated': a = F.to_estimated(a, spec['basis'])
        if 'frame_status' in spec:
            a['frame_status'] = spec['frame_status']
            a['frame'] = spec.get('frame')
        if 'frame_generated' in spec: a['frame_generated'] = copy.deepcopy(spec['frame_generated'])
        return a
    if spec.get('origin') == 'estimated': return F.to_estimated(F.answer(spec['top'], decided_by=['seed'], term=word), spec['basis'])
    return F.answer(spec['top'], decided_by=spec.get('decided_by', ['seed']), term=word)


def query_of(row, mapper=None, strip=False):
    answers = {w: answer_of(w, spec) for w, spec in row['placement'].items()}
    if strip:
        for a in answers.values(): a.pop('frame_generated', None)
    if mapper: answers = {w: mapper(a) for w, a in answers.items()}
    return F.MapQuery(answers)


def explain(row, mapper=None):
    return SR.typed_explain_ja(row['input'], query_of(row, mapper))


def pred_answer(ptype, frame_generated, *, status='NOT_CONFIRMED', frame=None, key=True, **kw):
    a = answer_of('x', dict({'top': [ptype], 'namespace': 'P', 'decided_by': ['gen_frame', 'role_distribution@jawiki'], 'frame_status': status, 'frame': frame}, **kw))
    if key: a['frame_generated'] = frame_generated
    return a


def gf(ptype, frame, **over):
    g = {'origin': 'generated', 'constructed': True, 'ptype': ptype, 'frame': frame, 'provenance': {'model': 'm', 'effort': 'e', 'batch_id': 'b', 'attempt': 1}}
    g.update(over)
    return g


def noun(top, by=('seed',)):
    return F.answer(top, decided_by=list(by))


def explain_of(text, answers):
    return SR.typed_explain_ja(text, F.MapQuery(answers))


# ===================================================================================================================================
# K202: the reader of `frame_generated`
# ===================================================================================================================================
def test_the_reader_of_frame_generated_says_absent_generated_or_the_closed_list_of_problems():
    read = R.predicate_frame_generated
    assert read({}) == ('absent', None) and read({'frame_generated': None}) == ('absent', None)
    assert read({'frame_generated': gf('P_ACT', {'で': ['PLACE']})}) == ('generated', {'で': frozenset({'PLACE'})})
    assert read({'frame_generated': gf('P_ACT', {})}) == ('generated', {})                    # an empty frame is well formed: it licenses nothing
    bad = {
        'NOT_A_MAPPING': 'x', 'ORIGIN_NOT_GENERATED': gf('P_ACT', {}, origin='estimated'), 'FRAME_NOT_A_MAPPING': gf('P_ACT', []),
        'PARTICLE_NOT_CASE:の': gf('P_ACT', {'の': ['PLACE']}), 'TYPES_NOT_A_LIST:で': gf('P_ACT', {'で': 'PLACE'}), 'TYPE_NOT_NOUN:で:SPACE': gf('P_ACT', {'で': ['SPACE']})}
    for problem, value in bad.items():
        assert read({'frame_generated': value}) == (None, 'PLACEMENT_FRAME_GENERATED_INVALID:' + problem), problem
    assert read({'frame_generated': gf('P_ACT', {'で': []})}) == (None, 'PLACEMENT_FRAME_GENERATED_INVALID:TYPES_NOT_A_LIST:で')
    assert read({'frame_generated': gf('P_ACT', {'で': ['PLACE', '']})}) == (None, 'PLACEMENT_FRAME_GENERATED_INVALID:TYPES_NOT_A_LIST:で')


def test_the_reader_of_frame_generated_does_not_need_the_other_fields_of_the_answer():
    assert R.predicate_frame_generated({'frame_generated': gf('P_ACT', {'に': ['PERSON', 'PLACE']})}) == ('generated', {'に': frozenset({'PERSON', 'PLACE'})})



def registered_rows():
    """The 16 rows of the registration (artifacts/w3-b5/PREREG.md), as the dictionary the plan reads: for the tests of the MECHANISM (what a row of the kind frame_required does),
    which does not depend on how many rows the table has been narrowed to (table change record 1)."""
    pre = (A / 'PREREG.md').read_text(encoding='utf-8')
    m = re.search(r'<!-- BEGIN table:w3b5_frames -->\n(.*?)<!-- END table:w3b5_frames -->', pre, re.S)
    out = {}
    for l in m.group(1).splitlines():
        if not (l.startswith('|') and l.rstrip().endswith('| frame_required |')): continue
        c = [x.strip().strip('`') for x in l.strip().strip('|').split('|')]
        out.setdefault(c[0], []).append((c[1], (c[2],), tuple(c[3].split()), 'arg' if c[4] == '項' else 'adjunct'))
    return {t: tuple(v) for t, v in out.items()}


@pytest.fixture
def registered(monkeypatch):
    monkeypatch.setattr(R, 'TYPED_FRAMES_FRAME_REQUIRED_W3B5', registered_rows())


GOAL_ROWS = {'P_MOVE': (('goal', ('に',), ('PLACE',), 'arg'),), 'P_COMMUNICATE': (('goal', ('に',), ('PLACE',), 'arg'),), 'P_ACT': (), 'P_CREATE': (), 'P_EMOTION': ()}


@pytest.fixture
def goal_rows(monkeypatch):
    """The table as it was after table change record 1 (round 1): the two rows P_MOVE and P_COMMUNICATE `goal/に/PLACE` that record 2 (round 2, review.r1.md) took out. The tests that put it back show WHY
    they went (the rows that the review named are read with it) and that the mechanism still works with one row."""
    monkeypatch.setattr(R, 'TYPED_FRAMES_FRAME_REQUIRED_W3B5', dict(GOAL_ROWS))


# ===================================================================================================================================
# K200: the plan, on sentences (the plan's return is taken through a spy: the entry looks the name up each time it runs)
# ===================================================================================================================================
@pytest.fixture
def spy(monkeypatch):
    got = []
    orig = R.typed_plan_u_w3b2_ja

    def wrapped(*a, **k):
        r = orig(*a, **k); got.append(r); return r
    monkeypatch.setattr(R, 'typed_plan_u_w3b2_ja', wrapped)
    return got


TEXT_DE = '兄が校庭で活躍した。'
PLACE_OK = {'兄': noun('PERSON'), '校庭': noun('PLACE', ('definition',))}


def de_answers(frame_generated_value, **kw):
    a = dict(PLACE_OK)
    a['活躍する'] = pred_answer('P_ACT', frame_generated_value, **kw)
    return a


def test_a_frame_that_holds_the_particle_and_the_type_licenses_the_row_and_the_license_is_told_to_the_caller_only(registered, spy):
    ex = explain_of(TEXT_DE, de_answers(gf('P_ACT', {'で': ['PLACE'], 'を': ['ARTIFACT']})))
    assert ex['w3b2'] == 'READ'
    typed, why = spy[-1]
    assert why is None and typed['role_license'] == {'place': 'frame_generated'} and typed['role_basis'] == {'agent': 'placement_direct:PERSON', 'place': 'placement_direct:PLACE'}
    assert re.fullmatch(R.W3B2_ROLE_BASIS_RE, typed['role_basis']['place'])
    out = SR.read(TEXT_DE, placement=F.MapQuery(de_answers(gf('P_ACT', {'で': ['PLACE']}))))
    assert out['readable'] is True
    clause = out['clauses'][0]
    assert clause['roles'] == {'agent': '兄', 'place': '校庭'} and 'role_flags' not in clause and 'role_license' not in clause       # H204: the output has no new key (event_cross closes `role_flags`)
    assert EC._check(out) == []                                                                              # and the output is a valid input of the cross


def test_a_frame_without_the_particle_or_without_the_type_does_not_license_the_row(registered):
    for frame in ({}, {'を': ['ARTIFACT']}, {'に': ['PLACE']}, {'で': ['ABSTRACT']}, {'で': ['ARTIFACT', 'ABSTRACT']}):
        ex = explain_of(TEXT_DE, de_answers(gf('P_ACT', frame)))
        assert ex['w3b2'] == 'FRAME_GENERATED_DOES_NOT_LICENSE:で', frame


def test_a_predicate_with_no_frame_is_read_as_before_and_the_reason_is_the_one_of_the_base_commit(registered):
    for a in (de_answers(None), {**PLACE_OK, '活躍する': pred_answer('P_ACT', None, key=False)}):
        assert explain_of(TEXT_DE, a)['w3b2'] == 'PLACEMENT_PARTICLE_NOT_IN_FRAME:P_ACT:で'
    # absence and a frame that says no are two reasons
    assert explain_of(TEXT_DE, de_answers(gf('P_ACT', {})))['w3b2'] != explain_of(TEXT_DE, de_answers(None))['w3b2']


def test_the_frame_is_looked_at_only_when_a_row_of_the_kind_frame_required_is_needed_so_a_broken_frame_does_not_change_the_other_sentences(registered):
    # P_MOVE has the row place/で in the second table (kind table): a broken frame_generated changes nothing
    text = '兄が校庭で走った。'
    base = {**PLACE_OK, '走る': pred_answer('P_MOVE', None, key=False)}
    ok = explain_of(text, base)
    for broken in ('x', gf('P_MOVE', {'で': 'PLACE'}), gf('P_MOVE', {'の': ['PLACE']}), gf('P_MOVE', {}, origin='estimated')):
        a = {**PLACE_OK, '走る': pred_answer('P_MOVE', broken)}
        assert explain_of(text, a) == ok
        assert SR.read(text, placement=F.MapQuery(a)) == SR.read(text, placement=F.MapQuery(base))
    # a sentence that needs the row: the same broken frame is a reason of its own
    a = de_answers(gf('P_ACT', {'で': 'PLACE'}))
    assert explain_of(TEXT_DE, a)['w3b2'] == 'PLACEMENT_FRAME_GENERATED_INVALID:TYPES_NOT_A_LIST:で'


def test_a_confirmed_predicate_still_narrows_what_the_frame_of_the_table_reads_and_the_frame_generated_does_not_widen_it(registered):
    g = gf('P_ACT', {'で': ['PLACE']})
    ex = explain_of(TEXT_DE, de_answers(g, status='CONFIRMED', frame={'が': ['PERSON'], 'を': ['ARTIFACT']}))
    assert ex['w3b2'] == 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_ACT:で'
    assert explain_of(TEXT_DE, de_answers(g, status='CONFIRMED', frame={'が': ['PERSON'], 'で': ['PLACE']}))['w3b2'] == 'READ'
    assert explain_of(TEXT_DE, de_answers(g, status='CONFIRMED', frame={'が': ['PERSON'], 'で': ['ARTIFACT']}))['w3b2'].startswith('PLACEMENT_FRAME_TYPE_NOT_CONFIRMED:P_ACT:で')
    # the first role that the confirmed frame does not hold is the reason (the agent is asked first): a frame with no が says が
    assert explain_of(TEXT_DE, de_answers(g, status='CONFIRMED', frame={'を': ['ARTIFACT']}))['w3b2'] == 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_ACT:が'


def test_an_estimated_predicate_is_still_refused_at_the_predicate_and_the_gates_of_the_filler_stay(registered):
    g = gf('P_ACT', {'で': ['PLACE']})
    est = {**PLACE_OK, '活躍する': answer_of('活躍する', {'top': ['P_ACT'], 'namespace': 'P', 'origin': 'estimated', 'basis': 'generated', 'frame_status': 'ESTIMATED', 'frame_generated': g})}
    assert explain_of(TEXT_DE, est)['w3b2'] == 'PLACEMENT_ESTIMATED_GENERATED:predicate:活躍する'
    pred = pred_answer('P_ACT', g)
    for filler, why in ((noun('PLACE', ('role@jawiki', 'role@codex:narrative')), 'PLACEMENT_SLOT_EVIDENCE_ONLY:で:校庭'), (F.bare('UNPLACED'), 'PLACEMENT_UNPLACED:で:校庭'),
                        (F.bare('UNKNOWN'), 'PLACEMENT_UNKNOWN:で:校庭'), (F.to_estimated(noun('PLACE'), 'generated'), 'PLACEMENT_ESTIMATED_GENERATED:で:校庭'),
                        (noun('WORK', ('definition',)), 'PLACEMENT_TYPE_MISMATCH:P_ACT:で:WORK'), (noun('PLACE', ('gen_definition',)), 'PLACEMENT_DIRECT_VIA_GENERATED:で:校庭')):
        assert explain_of(TEXT_DE, {'兄': noun('PERSON'), '校庭': filler, '活躍する': pred})['w3b2'] == why, why


def test_a_split_filler_is_read_only_when_every_candidate_is_inside_the_licensed_types_and_the_license_is_row_intersect_frame(registered):
    text = '兄が家族に催促した。'
    g = gf('P_COMMUNICATE', {'に': ['GROUP_ORG', 'PERSON']})
    both = {'兄': noun('PERSON'), '家族': noun(['GROUP_ORG', 'PERSON'], ('definition',)), '催促する': pred_answer('P_COMMUNICATE', g)}
    assert explain_of(text, both)['w3b2'] == 'READ'
    only_person = {**both, '催促する': pred_answer('P_COMMUNICATE', gf('P_COMMUNICATE', {'に': ['PERSON']}))}
    assert explain_of(text, only_person)['w3b2'] == 'PLACEMENT_MULTIPLE:に:家族'              # the row is row ∩ frame = {PERSON}: GROUP_ORG is outside
    outside = {**both, '家族': noun(['PERSON', 'PLACE'], ('definition',))}
    assert explain_of(text, outside)['w3b2'] == 'PLACEMENT_MULTIPLE:に:家族'


def test_a_particle_that_two_licensed_rows_could_take_is_decided_by_the_type_of_the_filler_and_a_type_no_row_has_is_a_mismatch(registered):
    text = '兄が先生に旅行した。'
    frame = gf('P_MOVE', {'に': ['PERSON', 'PLACE']})
    a = {'兄': noun('PERSON'), '先生': noun('PERSON'), '旅行する': pred_answer('P_MOVE', frame)}
    assert explain_of(text, a)['w3b2'] == 'READ'                                            # PERSON: the row recipient (licensed) fits, the row goal (PLACE) does not
    a['先生'] = noun('EVENT_ACT')
    assert explain_of(text, a)['w3b2'] == 'PLACEMENT_TYPE_MISMATCH:P_MOVE:に:EVENT_ACT'
    # the frame lets the other type but not the one of the filler: the frame does not license (a reason of its own)
    a = {'兄': noun('PERSON'), '先生': noun('PERSON'), '旅行する': pred_answer('P_MOVE', gf('P_MOVE', {'に': ['PLACE']}))}
    assert explain_of(text, a)['w3b2'] == 'FRAME_GENERATED_DOES_NOT_LICENSE:に'


def test_the_gate_of_a_focus_particle_after_a_case_particle_is_still_on_the_plan_and_the_role_basis_keeps_its_form(registered):
    a = de_answers(gf('P_ACT', {'で': ['PLACE']}))
    assert explain_of('兄が校庭でも活躍した。', a)['w3b2'].startswith('PLACEMENT_FOCUS_PARTICLE_AFTER_CASE:で:も')
    out = SR.read(TEXT_DE, placement=F.MapQuery(a))
    for c in out['clauses']:
        for v in c['role_basis'].values(): assert re.fullmatch(R.W3B2_ROLE_BASIS_RE, v)


# ===================================================================================================================================
# L1: a subprocess on the tree of the base commit, for the properties "with the key taken out / with no placement, the same as the base commit"
# ===================================================================================================================================
CHILD = r'''
import json, sys, copy
from verantyx import semantic_read as SR
req = json.load(sys.stdin)
class Q:
    id = 'map-query'
    def __init__(self, m): self.m = m
    def query(self, term):
        a = self.m.get(term)
        if a is None:
            a = {'term': term, 'namespace': None, 'state': 'UNKNOWN', 'origin': None, 'estimate_basis': None, 'constructed': False, 'top': [], 'decided_by': None, 'generated': None,
                 'generated_definition': None, 'placement': {'content_sha256': req['sha'], 'reason': None}}
        return copy.deepcopy(a)
out = []
for item in req['items']:
    q = Q(item['answers']) if item['answers'] is not None else None
    r = SR.read(item['text'], placement=q)
    e = SR.typed_explain_ja(item['text'], q) if q is not None else None
    out.append({'read': r, 'explain': e})
print(json.dumps(out, ensure_ascii=False, sort_keys=True))
'''


@pytest.fixture(scope='module')
def base_tree(tmp_path_factory):
    d = tmp_path_factory.mktemp('base_w3b5')
    tar = subprocess.run(['git', '-C', str(TREE), 'archive', BASE_COMMIT, 'verantyx'], capture_output=True, check=True).stdout
    subprocess.run(['tar', '-x', '-C', str(d)], input=tar, check=True)
    return d


def _child(tree, items):
    env = {k: v for k, v in os.environ.items() if k not in ('VERA_PLACEMENT', 'VERA_COARSE_PLACEMENT')}
    env.update(PYTHONPATH=str(tree), PYTHONDONTWRITEBYTECODE='1')
    p = subprocess.run([sys.executable, '-c', CHILD], input=json.dumps({'items': items, 'sha': F.SHA}, ensure_ascii=False).encode('utf-8'), capture_output=True, env=env, cwd=str(tree))
    assert p.returncode == 0, p.stderr.decode('utf-8')[-2000:]
    return json.loads(p.stdout.decode('utf-8'))


def _mine(items):
    out = []
    for item in items:
        q = F.MapQuery(item['answers']) if item['answers'] is not None else None
        r = SR.read(item['text'], placement=q)
        e = SR.typed_explain_ja(item['text'], q) if q is not None else None
        out.append(json.loads(json.dumps({'read': r, 'explain': e}, ensure_ascii=False, sort_keys=True)))
    return out


def test_with_the_key_frame_generated_taken_out_every_row_of_the_data_is_read_and_explained_as_the_base_commit_does(base_tree):
    items = [{'text': r['input'], 'answers': {w: a for w, a in query_of(r, strip=True).mapping.items()}} for r in DATA]
    base = _child(base_tree, items)
    now = _mine(items)
    assert [i for i, (b, n) in enumerate(zip(base, now)) if b != n] == []
    assert base[0]['explain'] is not None and len(now) == len(DATA)


def test_with_no_placement_every_row_of_the_data_is_what_the_entry_of_the_base_commit_says(base_tree):
    items = [{'text': r['input'], 'answers': None} for r in DATA]
    assert _child(base_tree, items) == _mine(items)


# ===================================================================================================================================
# the data
# ===================================================================================================================================
def test_the_data_has_the_registered_keys_ids_counts_and_the_rule_of_the_source_of_the_frames():
    keys = ['id', 'lang', 'input', 'text', 'behavior', 'expect', 'pred_type', 'path', 'particle', 'role_group', 'construction', 'placement', 'frame_source', 'entry_expect', 'w3b5_expect', 'note']
    assert len({r['input'] for r in DATA}) == len(DATA) == len({r['id'] for r in DATA})
    for r in DATA:
        assert list(r) == keys, r['id']
        assert r['input'] == r['text'] and r['lang'] == 'ja' and r['path'] in ('U', 'U3', 'S4', 'none') and r['entry_expect'] in ('read', 'abstain')
        assert re.fullmatch(r'W3B5-(DEPLACE|DEINSTR|DECAUSE|NIRECIP|NIGOAL|NITIME|NIPURP|NIOTHER|MECH)-[RA]-\d{3}', r['id']) and r['behavior'] == ('read' if r['expect']['readable'] else 'abstain')
        assert r['entry_expect'] == ('read' if r['id'].split('-')[2] == 'R' else 'abstain') or r['id'] in NARROWED_ROWS
        assert r['role_group'] in ROLE_GROUPS and r['particle'] in ('で', 'に') and r['frame_source'] in ('r8', 'absent', 'synthetic') and r['pred_type'].startswith('P_')
        assert (r['role_group'] == 'mechanism') == (r['id'].split('-')[1] == 'MECH')
        if r['frame_source'] == 'synthetic': assert r['role_group'] == 'mechanism'          # a made-up frame is only for the mechanism
        if r['behavior'] == 'read': assert r['frame_source'] == 'r8' and r['id'].split('-')[2] == 'R'   # a made-up or missing frame never makes a row read
        errs = []
        b1.validate_item(r, errs)
        assert errs == [], (r['id'], errs)
        preds = [w for w, s in r['placement'].items() if s.get('namespace') == 'P']
        assert len(preds) == 1
        gfv = r['placement'][preds[0]].get('frame_generated', 'MISSING')
        if r['frame_source'] == 'absent': assert gfv is None
        elif r['frame_source'] == 'r8': assert isinstance(gfv, dict) and gfv['origin'] == 'generated' and gfv['constructed'] is True and gfv['ptype'] == r['pred_type']
    def n(g, b): return sum(1 for r in DATA if r['role_group'] == g and r['behavior'] == b)
    for g in ('de_place', 'ni_recipient', 'ni_goal', 'ni_time'): assert n(g, 'read') >= 20, g
    for g in ('de_place', 'de_instrument', 'de_cause', 'ni_recipient', 'ni_goal', 'ni_time', 'ni_purpose', 'ni_other'): assert n(g, 'abstain') >= 20, g
    assert sum(1 for r in DATA if r['role_group'] == 'mechanism') >= 15


def test_the_frame_of_every_row_of_the_frame_source_r8_is_the_row_of_the_table_of_r8():
    if not os.path.isdir(R8): pytest.skip('ENV_MISSING[coarse placement r8/run2]')
    con = sqlite3.connect('file:%s/placement.sqlite?mode=ro' % R8, uri=True)
    for r in DATA:
        w = next(w for w, s in r['placement'].items() if s.get('namespace') == 'P')
        s = r['placement'][w]
        row = con.execute('SELECT model, effort, batch_id, attempt, ptype, frame FROM generated_frames WHERE word=?', (w,)).fetchone()
        if r['frame_source'] == 'r8':
            assert row is not None and s['frame_generated'] == {'origin': 'generated', 'constructed': True, 'ptype': row[4], 'frame': json.loads(row[5]),
                                                              'provenance': {'model': row[0], 'effort': row[1], 'batch_id': row[2], 'attempt': row[3]}}, r['id']
            assert s['top'] == [row[4]] == [r['pred_type']]
        elif r['frame_source'] == 'absent': assert row is None and s['frame_generated'] is None, r['id']


def test_the_data_is_the_frozen_file_or_the_frozen_file_with_rows_appended_at_the_end():
    import hashlib
    lines = DATA_FILE.read_text(encoding='utf-8').splitlines(keepends=True)
    prefixes = {hashlib.sha256(''.join(lines[:k]).encode('utf-8')).hexdigest(): k for k in range(len(lines), 0, -1)}
    # the three freezes, in order: 604 rows (first freeze), 617 (13 rows appended in round 1, H206), 649 (32 rows appended in round 2, K206 change 2): each one is the start of the file as it is now
    sizes = [prefixes[(A / name).read_text(encoding='utf-8').split()[0]] for name in ('bank_freeze.sha256', 'bank_freeze_after.sha256', 'bank_freeze_r2.sha256')]
    assert sizes == [604, 617, 649]


def test_the_rows_appended_in_round_2_are_the_four_types_of_the_review_with_five_or_more_each_abstain_rows_with_the_real_frame_of_r8():
    appended = DATA[617:]
    assert len(appended) == 32 and all(r['id'].split('-')[2] == 'A' and r['behavior'] == 'abstain' and r['entry_expect'] == 'abstain' and r['w3b5_expect'] == 'REFUSED' for r in appended)
    assert all(r['frame_source'] == 'r8' and r['pred_type'] in ('P_MOVE', 'P_COMMUNICATE') and r['particle'] == 'に' for r in appended)
    assert all(r['expect'] == {'readable': False, 'clauses': [], 'relations': [], 'must_not': []} for r in appended)
    assert collections.Counter(TYPE_OF(r) for r in appended) == {'stay': 8, 'purpose': 8, 'org_receives': 8, 'undecided': 8}
    # the words are not the words of the older rows: the sentences and the (predicate, filler) pairs are new
    old_inputs = {r['input'] for r in DATA[:617]}
    assert not {r['input'] for r in appended} & old_inputs


def TYPE_OF(row):
    """The type of a round 2 row (review.r1.md required fix 2): by the id the generator gave (mk_round2_rows.py)."""
    g, n = row['id'].split('-')[1], int(row['id'].split('-')[3])
    return {'NIPURP': 'purpose', 'NIRECIP': 'org_receives'}.get(g) or ('stay' if n < 960 else 'undecided')


def _expected_reason_ok(row, got):
    e = row['w3b5_expect']
    if e == 'READ': return got == 'READ'
    if e == 'REFUSED': return got != 'READ'
    return (got or '').startswith(e)


def _row_ids():
    return [r['id'] for r in DATA]


@pytest.mark.parametrize('row', DATA, ids=_row_ids())
def test_every_row_of_the_data_is_read_or_refused_as_registered_and_judged_correct_when_read(row):
    q = query_of(row)
    out = SR.read(row['input'], placement=q)
    verdict = b1.judge(row['expect'], 'ja', out)['verdict']
    assert verdict not in ('misread', 'incomplete', 'UNJUDGED'), (verdict, out)           # L3: a misread is never allowed (K206: the row of the table that made it goes)
    ex = SR.typed_explain_ja(row['input'], query_of(row))
    entry = 'read' if out['readable'] else 'abstain'
    if row['id'] in NARROWED_ROWS:
        nr = NARROWED_ROWS[row['id']]
        assert entry == 'abstain' and ex['w3b2'] == nr['observed_w3b2'] and nr['frozen_entry_expect'] == row['entry_expect'] and nr['frozen_w3b5_expect'] == row['w3b5_expect']
        return
    if row['id'] in EXCEPTIONS:
        assert ex == EXCEPTIONS[row['id']]['observed_explain'] and verdict == EXCEPTIONS[row['id']]['observed_verdict']
        return
    assert entry == row['entry_expect'], (entry, ex)
    if entry == 'read':
        assert verdict == 'correct', verdict
        assert row['frame_source'] == 'r8' and ex['w3b2'] in ((None, 'PLACEMENT_W3B2_NOT_TRIGGERED') if row['path'] == 'none' else ('READ',))
    assert _expected_reason_ok(row, ex['w3b2'] if ex['w3b2'] is not None else 'PLACEMENT_W3B2_NOT_TRIGGERED'), (row['w3b5_expect'], ex)


def test_no_row_of_the_data_is_misread_or_incomplete_and_after_the_last_narrowing_the_entry_reads_only_what_the_reader_alone_reads():
    bad = collections.Counter(); read = []
    for row in DATA:
        out = SR.read(row['input'], placement=query_of(row))
        v = b1.judge(row['expect'], 'ja', out)['verdict']
        bad[v] += 1
        if out['readable']: read.append(row)
    assert bad['misread'] == 0 and bad['incomplete'] == 0 and bad['UNJUDGED'] == 0, bad
    # after table change record 2 (K206) there is no row of the kind frame_required: no sentence is read through a generated frame, so what is read is what the reader alone reads
    # (the rows of the path `none`: the typed step is not asked) and the key frame_generated licenses nothing
    assert read and all(r['path'] == 'none' for r in read) and {r['role_group'] for r in read} == {'de_place'}, collections.Counter(r['role_group'] for r in read)


def test_the_sentences_of_the_ticket_a_right_handed_hit_a_surprise_at_a_step_and_a_mouth_are_refused_and_the_boarding_gate_type_is_read_only_while_its_row_is_in_the_table():
    refused = ['兄が右で打った。', '兄が右で皿を洗った。', '兄が右で皿を拭いた。', '兄が右で絵を描いた。', '弟が右で記事を書いた。', '兄が段差で驚いた。', '兄が口で戦った。', '兄が口で絵を描いた。', '兄が口で手紙を書いた。', '兄が口で笑った。']
    by = {r['input']: r for r in DATA}
    for t in refused:
        assert t in by and by[t]['entry_expect'] == 'abstain' and by[t]['frame_source'] == 'absent'
        assert not SR.read(t, placement=query_of(by[t]))['readable'], t
    gate = [r for r in DATA if r['id'].startswith('W3B5-DEPLACE-R') and r['path'] == 'U3' and re.match(r'.+で.+が.+の.+を.+た。', r['input'])]
    assert len(gate) >= 5 and not any(r['input'] in refused for r in gate)
    # table change record 1 (K206): the row place/で of P_ACT and P_CREATE read the worst cases of the data as misreads and was taken out: these frozen rows are refused now, with the recorded diagnosis
    has_row = any(role == 'place' and t in ('P_ACT', 'P_CREATE') for (t, role, parts, exp, kind, lic) in R.typed_frames_w3b5_rows() if lic == 'frame_required')
    for r in gate:
        out = SR.read(r['input'], placement=query_of(r))
        assert out['readable'] is has_row, r['input']
        if not has_row:
            assert r['id'] in NARROWED_ROWS and SR.typed_explain_ja(r['input'], query_of(r))['w3b2'] == NARROWED_ROWS[r['id']]['observed_w3b2']


def test_the_rows_taken_out_by_the_table_change_records_are_the_sixteen_of_the_registration_fourteen_by_record_1_and_the_two_goal_rows_by_record_2_and_none_is_left():
    reg = {(t, role, parts[0]) for t, rows in registered_rows().items() for (role, parts, exp, kind) in rows}
    now = {(t, role, parts[0]) for (t, role, parts, exp, kind, lic) in R.typed_frames_w3b5_rows() if lic == 'frame_required'}
    assert len(reg) == 16 and now <= reg and len(reg - now) == 16 and now == set()
    two = {(t, role, parts[0]) for t, rows in GOAL_ROWS.items() for (role, parts, exp, kind) in rows}
    assert two == {('P_MOVE', 'goal', 'に'), ('P_COMMUNICATE', 'goal', 'に')} and two <= reg and len(reg - two) == 14        # record 1 left these two, record 2 took them out
    assert set(R.TYPED_FRAMES_FRAME_REQUIRED_W3B5) == set(registered_rows()) | {'P_ACT', 'P_CREATE', 'P_EMOTION'} and all(v == () for v in R.TYPED_FRAMES_FRAME_REQUIRED_W3B5.values())


def test_with_the_table_as_registered_the_worst_cases_of_the_data_are_read_which_is_why_the_sixteen_rows_were_taken_out(registered):
    """K206: the same data with the 16 registered rows put back. The rows that the change record names are the ones that misread (the count is the one in the record); with the table as it is
    now (no `registered` fixture) there is none (test_no_row_of_the_data_is_misread_or_incomplete)."""
    n = 0
    for r in DATA:
        out = SR.read(r['input'], placement=query_of(r))
        if b1.judge(r['expect'], 'ja', out)['verdict'] == 'misread': n += 1
    assert n >= 100


def test_with_the_two_goal_rows_put_back_the_rows_appended_in_round_2_are_read_and_misread_which_is_why_the_two_rows_were_taken_out_too(goal_rows):
    """K206, table change record 2 (review.r1.md): the table of record 1 (the two `goal/に/PLACE` rows). Each of the four types of the review has five or more rows that the entry reads, and each of them
    is a misread (the frozen expectation is `readable: false`; the license told by the plan is the goal row). The count is the measurement of `data_check_before_round2.txt`: 31 of the 32 rows (the 32nd stops
    at `PLACEMENT_UNPLACED:を:資料`)."""
    per, wrong = collections.Counter(), 0
    for r in DATA[617:]:
        out = SR.read(r['input'], placement=query_of(r))
        if not out['readable']: continue
        per[TYPE_OF(r)] += 1
        wrong += b1.judge(r['expect'], 'ja', out)['verdict'] == 'misread'
    assert all(per[t] >= 5 for t in ('stay', 'purpose', 'org_receives', 'undecided')) and sum(per.values()) == wrong == 31, (per, wrong)


def test_with_the_table_as_it_is_every_row_appended_in_round_2_is_refused_and_the_misreads_of_the_review_are_gone():
    for r in DATA[617:]:
        out = SR.read(r['input'], placement=query_of(r))
        assert not out['readable'] and b1.judge(r['expect'], 'ja', out)['verdict'] != 'misread', r['input']
        ex = SR.typed_explain_ja(r['input'], query_of(r))['w3b2']
        assert ex != 'READ' and not ex.startswith('FRAME_GENERATED_DOES_NOT_LICENSE'), (r['input'], ex)          # no row asks for the frame: the reason is one of the base commit's gates


def test_the_frozen_rows_whose_answer_was_written_wrongly_are_declared_with_the_observations_and_every_read_row_of_ni_goal_was_reviewed():
    wrong = {i: e for i, e in EXCEPTIONS.items() if e['kind'] in ('frozen_expectation_is_a_wrong_answer', 'goal_or_place_not_decided')}
    by = {r['id']: r for r in DATA}
    assert {i for i, e in wrong.items() if e['kind'] == 'frozen_expectation_is_a_wrong_answer'} == {'W3B5-NIGOAL-R-011', 'W3B5-NIGOAL-R-031'}       # 停泊: review.r1.md required fix 3
    assert set(wrong) == {'W3B5-NIGOAL-R-010', 'W3B5-NIGOAL-R-011', 'W3B5-NIGOAL-R-031', 'W3B5-NIGOAL-R-036'}
    for i, e in wrong.items():
        r = by[i]
        assert r['behavior'] == 'read' and r['entry_expect'] == 'read' and 'goal' in r['expect']['clauses'][0]['roles'] and i in NARROWED_ROWS     # the frozen expectation is not rewritten
        assert e['frozen_entry_expect'] == 'read' and e['frozen_w3b5_expect'] == r['w3b5_expect'] and e['observed_entry'] == 'abstain' and e['correct_by_convention'] and e['reason']
        assert e['observed_with_the_table_as_registered']['entry'] == 'read' and e['observed_with_the_table_as_registered']['verdict'] == 'correct'      # it was counted correct: that was the error
        assert not SR.read(r['input'], placement=query_of(r))['readable']
    review = [l.split('\t') for l in (A / 'round2' / 'ni_goal_read_rows_review.tsv').read_text(encoding='utf-8').splitlines()[1:]]
    assert [x[0] for x in review] == [r['id'] for r in DATA if r['role_group'] == 'ni_goal' and r['behavior'] == 'read'] and len(review) == 43
    assert {x[0] for x in review if x[4].startswith('DECLARED:')} == set(wrong)


def test_with_the_table_as_it_is_no_goal_row_reads_a_place_through_the_frame_and_the_reason_is_the_one_of_the_base_commit():
    text = '兄が駅に旅行した。'
    ok = {'兄': noun('PERSON'), '駅': noun('PLACE', ('definition',)), '旅行する': pred_answer('P_MOVE', gf('P_MOVE', {'に': ['PLACE']}))}
    assert explain_of(text, ok)['w3b2'] == 'PLACEMENT_TYPE_MISMATCH:P_MOVE:に:PLACE'          # the same sentence, the same frame: no row, no license, the reason of the base commit
    assert SR.read(text, placement=F.MapQuery(ok))['readable'] is False
    for frame in ({}, {'に': ['PLACE']}, {'で': ['PLACE']}):
        a = {**ok, '旅行する': pred_answer('P_MOVE', gf('P_MOVE', frame))}
        assert explain_of(text, a)['w3b2'] == 'PLACEMENT_TYPE_MISMATCH:P_MOVE:に:PLACE'      # whatever the frame says: it licenses nothing now
    a = {**ok, '旅行する': pred_answer('P_MOVE', gf('P_MOVE', {'に': 'PLACE'}))}               # and a broken frame is not even looked at (nothing needs it)
    assert explain_of(text, a)['w3b2'] == 'PLACEMENT_TYPE_MISMATCH:P_MOVE:に:PLACE'


def test_with_the_two_goal_rows_put_back_the_mechanism_reads_a_place_that_the_frame_lets_and_everything_else_is_a_reason(goal_rows):
    text = '兄が駅に旅行した。'
    ok = {'兄': noun('PERSON'), '駅': noun('PLACE', ('definition',)), '旅行する': pred_answer('P_MOVE', gf('P_MOVE', {'に': ['PLACE']}))}
    assert explain_of(text, ok)['w3b2'] == 'READ'
    assert explain_of(text, {**ok, '駅': noun('PLACE', ('role@jawiki',))})['w3b2'] == 'READ'            # an argument (goal) is not asked for evidence beyond role@: the gate is for adjuncts
    out = SR.read(text, placement=F.MapQuery(ok))
    assert out['readable'] and out['clauses'][0]['roles'] == {'agent': '兄', 'goal': '駅'} and 'role_flags' not in out['clauses'][0] and EC._check(out) == []
    for frame in ({}, {'を': ['ARTIFACT']}, {'で': ['PLACE']}, {'に': ['PERSON']}, {'に': ['ABSTRACT']}):
        a = {**ok, '旅行する': pred_answer('P_MOVE', gf('P_MOVE', frame))}
        assert explain_of(text, a)['w3b2'] == 'FRAME_GENERATED_DOES_NOT_LICENSE:に', frame
    # a filler with evidence of role@ only: the time row of the table (an adjunct) is asked first and the gate for an adjunct says why (the base commit's reason; the frame is not the cause)
    a = {**ok, '駅': noun('PLACE', ('role@jawiki',)), '旅行する': pred_answer('P_MOVE', gf('P_MOVE', {}))}
    assert explain_of(text, a)['w3b2'] == 'PLACEMENT_SLOT_EVIDENCE_ONLY:に:駅'
    a = {**ok, '旅行する': pred_answer('P_MOVE', None)}
    assert explain_of(text, a)['w3b2'] == 'PLACEMENT_TYPE_MISMATCH:P_MOVE:に:PLACE'                 # no frame: the reason of the base commit
    a = {**ok, '旅行する': pred_answer('P_MOVE', gf('P_MOVE', {'に': 'PLACE'}))}
    assert explain_of(text, a)['w3b2'] == 'PLACEMENT_FRAME_GENERATED_INVALID:TYPES_NOT_A_LIST:に'
    a = {**ok, '駅': noun(['PLACE', 'TIME'], ('definition',))}
    assert explain_of(text, a)['w3b2'] == 'PLACEMENT_MULTIPLE:に:駅'
    est = {**ok, '旅行する': answer_of('旅行する', {'top': ['P_MOVE'], 'namespace': 'P', 'origin': 'estimated', 'basis': 'generated', 'frame_status': 'ESTIMATED', 'frame_generated': gf('P_MOVE', {'に': ['PLACE']})})}
    assert explain_of(text, est)['w3b2'] == 'PLACEMENT_ESTIMATED_GENERATED:predicate:旅行する'
    for wrong in (noun('PERSON'), noun('EVENT_ACT', ('definition',)), F.bare('UNPLACED')):
        assert explain_of(text, {**ok, '駅': wrong})['w3b2'] != 'READ'
    conf = {**ok, '旅行する': pred_answer('P_MOVE', gf('P_MOVE', {'に': ['PLACE']}), status='CONFIRMED', frame={'が': ['PERSON'], 'に': ['PLACE']})}
    assert explain_of(text, conf)['w3b2'] == 'READ'
    conf = {**ok, '旅行する': pred_answer('P_MOVE', gf('P_MOVE', {'に': ['PLACE']}), status='CONFIRMED', frame={'が': ['PERSON'], 'を': ['ARTIFACT']})}
    assert explain_of(text, conf)['w3b2'] == 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_MOVE:に'


def _estimated(a): return F.to_estimated(a, 'generated')


@pytest.mark.parametrize('mapper', [_estimated, F.to_multiple], ids=['estimated', 'multiple'])
def test_with_a_placement_that_only_estimates_or_splits_no_row_that_reaches_a_typed_trigger_is_read(mapper):
    for row in DATA:
        if row['path'] == 'none': continue
        out = SR.read(row['input'], placement=query_of(row, mapper))
        assert not out['readable'], (row['id'], row['input'])


def test_the_frame_is_never_a_vote_for_a_type_the_entry_with_a_frame_licensing_nothing_reads_what_the_entry_with_no_frame_reads():
    """H201: the generated frame only allows or does not allow a row. A row of the table (kind table) is read exactly as before whatever the frame says."""
    for row in DATA:
        if row['pred_type'] not in ('P_MOVE', 'P_COMMUNICATE') or row['particle'] != 'で' or row['behavior'] != 'read': continue
        assert SR.read(row['input'], placement=query_of(row)) == SR.read(row['input'], placement=query_of(row, strip=True))


# ===================================================================================================================================
# L1: the query. The key is added, nothing else changes (r7 and r8 in full, the base commit's function as the reference)
# ===================================================================================================================================
def _base_coarse_place():
    src = git('show', '%s:verantyx/coarse_place.py' % BASE_COMMIT)
    spec = importlib.util.spec_from_loader('verantyx._coarse_place_base_w3b5', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src, 'verantyx/coarse_place.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    return mod


def _words(path, n_est=20):
    con = sqlite3.connect('file:%s/placement.sqlite?mode=ro' % path, uri=True)
    rows = con.execute('SELECT g.word, h.origin, g.ptype FROM generated_frames g LEFT JOIN headwords h ON h.word = g.word ORDER BY g.word').fetchall()
    direct = [w for w, o, p in rows if o == 'direct']
    est = collections.defaultdict(list)
    for w, o, p in rows:
        if o != 'direct' and len(est[p]) < n_est: est[p].append(w)
    nouns = [r[0] for r in con.execute("SELECT word FROM headwords WHERE ns='N' AND state='DECIDED' ORDER BY word LIMIT 20")]
    seeds = [r[0] for r in con.execute("SELECT word FROM headwords WHERE ns='P' AND origin='direct' AND word NOT IN (SELECT word FROM generated_frames) ORDER BY word LIMIT 20")]
    extra = ['ほげほげ', 'ホゲホゲ', 'ロケット', 'ＡＢＣ', 'abc']
    return direct + [w for ws in est.values() for w in ws] + nouns + seeds + extra, con


@pytest.mark.parametrize('path', [R7, R8], ids=['r7', 'r8'])
def test_the_answer_of_the_query_without_frame_generated_is_the_answer_of_the_base_commit_byte_for_byte_and_the_value_is_the_row_of_the_table(path):
    if not os.path.isdir(path): pytest.skip('ENV_MISSING[coarse placement %s]' % path)
    base = _base_coarse_place()
    words, con = _words(path)
    for w in words:
        a = CP.query(w, placement=path)
        b = base.query(w, placement=path)
        assert 'frame_generated' in a and 'frame_generated' not in b
        rest = {k: v for k, v in a.items() if k != 'frame_generated'}
        assert json.dumps(rest, ensure_ascii=False) == json.dumps(b, ensure_ascii=False), w
        keys = list(a)
        tail = [k for k in ('generated_frame', 'frame_status', 'frame', 'frame_unconfirmed', 'frame_disagreement') if k in a]
        assert keys[keys.index('frame_generated') + 1] == tail[0] and keys[keys.index('frame_generated') - 1] == 'spelling', w
        row = con.execute('SELECT model, effort, batch_id, attempt, ptype, frame FROM generated_frames WHERE word=?', (a['spelling']['normalized'],)).fetchone()
        if row is None: assert a['frame_generated'] is None, w
        else:
            assert a['frame_generated'] == {'origin': 'generated', 'constructed': True, 'ptype': row[4], 'frame': json.loads(row[5]),
                                           'provenance': {'model': row[0], 'effort': row[1], 'batch_id': row[2], 'attempt': row[3]}}, w
            fg = a['frame_generated']
            assert all(p in CT.CASE_PARTICLES_9 for p in fg['frame']) and all(t in CT.NOUN_TYPES for ts in fg['frame'].values() for t in ts)


def test_without_a_placement_the_query_has_the_key_with_null_and_the_other_keys_are_the_ones_of_the_base_commit(monkeypatch):
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)
    base = _base_coarse_place()
    a, b = CP.query('駅'), base.query('駅')
    assert a['state'] == 'NO_PLACEMENT' and a['frame_generated'] is None
    assert json.dumps({k: v for k, v in a.items() if k != 'frame_generated'}, ensure_ascii=False) == json.dumps(b, ensure_ascii=False)
    assert list(a)[list(a).index('frame_generated') + 1] == 'frame_status'
