"""W3-b4: the third step of reading by the type of a word: the table of K62 is widened to a second table (v2) for the types whose particles are decided by the types of the
fillers, and the plan of the typed re-read (W3-b2's rule, unchanged) reads with it. The table, the 6 types that stay unread and their reasons were registered in
docs/READING_SOUNDNESS.md section 10D (K160-K165) before the data (tests/reading_soundness/ja_r10_w3b4.jsonl) and this file were written.

Placement answers here come from fakes built out of the `placement` of each row of the data (a contract-conforming answer made from the real answer of the placement r7 for the
word; the minimal fake is `MapQuery` of tests/reading_soundness/w3b1_fakes.py, which fits the `query(term)` protocol of the entry). The only real placement a test opens is r7, read only,
for the one smoke test of the default entry (skipped when it is not there).
Run under a clean environment (env -i): a VERA_PLACEMENT left in the shell would change the default path of the entry.
"""
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TREE = Path(__file__).resolve().parent.parent
RS = TREE / 'tests' / 'reading_soundness'
BASE_COMMIT = 'bed39eb'    # Integration (auditor, 2026-10-04): dev just before W3-b4 was merged (W3-b3's two lines in semantic_read.py are not W3-b4's); W3-b4 itself started from c875ed3
R7 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1'
SIX = ('が', 'を', 'に', 'へ', 'から', 'で')


def _load_by_path(name, path):
    """Load a helper module by its path under a unique name (sys.path is NOT changed: see the note of tests/test_semantic_read_w3b1.py)."""
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


F = _load_by_path('w3b2_fakes_in_test_w3b4', RS / 'w3b2_fakes.py')

from tools.bank_score.v2 import b1    # noqa: E402
from verantyx import coarse_types as CT    # noqa: E402
from verantyx import event_cross as EC    # noqa: E402
from verantyx import semantic_read as SR    # noqa: E402
from verantyx import semantic_reader as R    # noqa: E402

DOCS = (TREE / 'docs' / 'READING_SOUNDNESS.md').read_text(encoding='utf-8')
DATA_FILE = RS / 'ja_r10_w3b4.jsonl'
EXC_FILE = TREE / 'artifacts' / 'w3-b4' / 'expect_exceptions.json'
DATA = [json.loads(l) for l in DATA_FILE.read_text(encoding='utf-8').splitlines() if l.strip()]
EXCEPTIONS = {e['id']: e for e in json.loads(EXC_FILE.read_text(encoding='utf-8'))['exceptions']}
EXCEPTION_KINDS = json.loads(EXC_FILE.read_text(encoding='utf-8'))['kinds']
NARROWED_FILE = TREE / 'artifacts' / 'w3-b4' / 'narrowed_types.json'
NARROWED = json.loads(NARROWED_FILE.read_text(encoding='utf-8'))['types']
# round 2 (docs K165, table change records 1 and 2): a misread was found for P_CHANGE and P_CONSUME, so they went back to the unread types. The frozen rows of these two types keep their
# frozen expectations (`entry_expect: read` for 27 and 29 rows): the tests below read a row of a narrowed type as "the entry refuses it" (see `narrowed_types.json`).
# round 3 (docs K165, table change record 3, the auditor's way (b)): the rows place/で/PLACE of P_ACT, P_CREATE and P_EMOTION were taken out of the table (the types stay, with their other rows).
# The frozen rows whose diagnosis that changed are NOT rewritten: `narrowed_rows.json` (made by tools/mk_narrowed_rows.py) records them, with the diagnosis that is observed now, and the tests read
# such a row as "the entry refuses it, with that diagnosis". Ten sentences of the review of round 2 were appended to the data as refused rows (`DATA[323:333]`).
NARROWED_ROWS_FILE = TREE / 'artifacts' / 'w3-b4' / 'narrowed_rows.json'
NARROWED_ROWS_RECORD = json.loads(NARROWED_ROWS_FILE.read_text(encoding='utf-8'))
NARROWED_ROWS = NARROWED_ROWS_RECORD['data_rows_refused_by_the_narrowing']
DE_ROW = ('place', ('で',), ('PLACE',), 'adjunct')
READ_TYPES = ('P_ACT', 'P_CREATE', 'P_EMOTION')
UNREAD_TYPES = ('P_GIVE', 'P_PERCEIVE', 'P_EXIST', 'P_POSSESS', 'P_STATE', 'P_COGNITION', 'P_CHANGE', 'P_CONSUME')
# the refusals that happen BEFORE the type of the predicate is asked (the registered reasons of the rows of a narrowed type that stay as they were registered)
BEFORE_THE_TYPE = ('PLACEMENT_W3B2_NOT_TRIGGERED', 'PLACEMENT_VOICE_NOT_ACTIVE')


@pytest.fixture(autouse=True)
def _no_placement_in_the_environment(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)


def git(*args):
    return subprocess.run(['git', '-C', str(TREE)] + list(args), capture_output=True, check=True).stdout.decode('utf-8')


def _base_module():
    """The reading entry of the base commit (its own control flow), on top of the reader of this tree (the base functions that it calls are unchanged)."""
    src = git('show', '%s:verantyx/semantic_read.py' % BASE_COMMIT)
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_base_w3b4', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src, 'verantyx/semantic_read.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    return mod


BASE = _base_module()


def block_lines(name):
    m = re.search(r'<!-- BEGIN table:%s -->\n(.*?)<!-- END table:%s -->' % (name, name), DOCS, re.S)
    assert m, name
    return [line for line in m.group(1).splitlines() if line.startswith('|') and not set(line) <= set('|- ')][1:]


def block(name):
    return [[c.strip().strip('`') for c in line.strip().strip('|').split('|')] for line in block_lines(name)]


def code_rows(frames):
    return [(t, role, '/'.join(parts), ' '.join(exp), '項' if kind == 'arg' else '付加') for t, rows in frames.items() for (role, parts, exp, kind) in rows]


# ===================================================================================================================================
# K161 / K162: the tables of the docs are the constants of the code; v1 is not changed; v1 is the first 9 rows of v2
# ===================================================================================================================================
def test_the_second_table_in_the_docs_is_the_table_of_the_code_in_the_same_order():
    assert [tuple(r) for r in block('w3b4_frames')] == code_rows(R.typed_frames_v2())


def test_the_first_nine_rows_are_the_rows_of_the_first_table_character_for_character_and_the_two_types_are_v1s():
    assert block_lines('w3b4_frames')[:9] == block_lines('w3b1_frames')
    v2 = R.typed_frames_v2()
    assert list(v2)[:2] == ['P_MOVE', 'P_COMMUNICATE'] and list(v2)[2:] == list(R.TYPED_FRAMES_W3B4)
    for t in ('P_MOVE', 'P_COMMUNICATE'): assert v2[t] == R.TYPED_FRAMES[t]


def test_the_table_holds_type_ids_role_names_and_the_six_particles_only_no_words():
    noun_types, roles = set(CT.NOUN_TYPES), set(b1.ROLES)
    for t, rows in R.typed_frames_v2().items():
        assert t in CT.PRED_TYPES
        for role, parts, exp, kind in rows:
            assert role in roles and kind in ('arg', 'adjunct')
            assert len(parts) == 1 and parts[0] in SIX              # と・まで・より are not particles of the table
            assert exp and set(exp) <= noun_types and list(exp) == list(dict.fromkeys(exp))
            assert (kind == 'adjunct') == (role in ('time', 'place'))
    for row in block('w3b4_frames'):
        assert re.fullmatch(r'P_[A-Z]+', row[0]) and row[1] in roles and row[2] in SIX and set(row[3].split()) <= noun_types and row[4] in ('項', '付加')


def test_two_rows_of_one_type_and_one_particle_have_disjoint_expected_types_so_the_role_is_decided_by_the_type_of_the_filler():
    for t, rows in R.typed_frames_v2().items():
        for i, a in enumerate(rows):
            for b in rows[i + 1:]:
                if set(a[1]) & set(b[1]): assert not set(a[2]) & set(b[2]), (t, a, b)
    # the docs table says the same (a check of the registered text, not of the code)
    seen = {}
    for t, role, part, exp, kind in block('w3b4_frames'):
        for other in seen.get((t, part), []): assert not set(other.split()) & set(exp.split()), (t, part)
        seen.setdefault((t, part), []).append(exp)


def test_the_roles_that_the_event_cross_types_have_the_same_types_and_patient_is_the_fourteen_types():
    fourteen = tuple(t for t in CT.NOUN_TYPES if t not in ('TIME', 'QUANTITY', 'PLACE'))
    assert len(fourteen) == 14
    for t, rows in R.typed_frames_v2().items():
        for role, parts, exp, kind in rows:
            if role in EC.EXPECTED_TYPES: assert frozenset(exp) == EC.EXPECTED_TYPES[role], (t, role)
            if role == 'patient': assert set(exp) == set(fourteen), t
            if role == 'goal' or role == 'source': assert exp == ('PLACE',)


def test_no_row_of_the_registered_gaps_is_in_the_table():
    """K161: the rows that are NOT written (a split that the types of the fillers do not decide)."""
    rows = {(t, role, parts[0]) for t, rs in R.typed_frames_v2().items() for (role, parts, exp, kind) in rs}
    for role in ('recipient', 'instrument', 'result', 'cause', 'beneficiary', 'companion', 'quotation'):
        assert not any(r[1] == role for r in rows), role
    assert not any(r[2] == 'に' and r[1] != 'time' for r in rows)            # no に row but time/に (P_MOVE, P_COMMUNICATE; P_CONSUME's was taken out in round 2)
    assert {t for t, role, p in rows if (role, p) == ('time', 'に')} == {'P_MOVE', 'P_COMMUNICATE'}
    assert not any(t in ('P_CHANGE', 'P_CONSUME') for t, role, p in rows)      # round 2: the two narrowed types have no row at all
    assert {t for t, role, p in rows if (role, p) == ('place', 'で')} == {'P_MOVE', 'P_COMMUNICATE'}      # round 3: no new type has a place/で row (instrument and cause take PLACE words too)
    assert ('P_CHANGE', 'patient', 'を') not in rows and ('P_ACT', 'goal', 'に') not in rows


def test_the_types_that_are_read_and_not_read_are_the_thirteen_without_overlap():
    assert set(R.TYPED_FRAMES) | set(R.TYPED_FRAMES_W3B4) == set(R.typed_frames_v2())
    assert set(R.TYPED_FRAMES) | set(R.TYPED_FRAMES_W3B4) | set(R.TYPED_FRAMES_NOT_READ_W3B4) == set(CT.PRED_TYPES) and len(CT.PRED_TYPES) == 13
    assert not set(R.TYPED_FRAMES) & set(R.TYPED_FRAMES_W3B4)
    assert not (set(R.TYPED_FRAMES) | set(R.TYPED_FRAMES_W3B4)) & set(R.TYPED_FRAMES_NOT_READ_W3B4)
    assert tuple(R.TYPED_FRAMES_W3B4) == READ_TYPES and tuple(R.TYPED_FRAMES_NOT_READ_W3B4) == UNREAD_TYPES
    assert [(r[0], r[1]) for r in block('w3b4_not_read')] == list(R.TYPED_FRAMES_NOT_READ_W3B4.items())
    for name in R.TYPED_FRAMES_NOT_READ_W3B4.values(): assert re.fullmatch(r'[A-Z_]+', name)


def _frozen(name):
    """The value of a module-level dict of the reader at the base commit, read from its source (not imported)."""
    for n in ast.parse(git('show', '%s:verantyx/semantic_reader.py' % BASE_COMMIT)).body:
        if isinstance(n, ast.Assign) and any(getattr(t, 'id', None) == name for t in n.targets): return ast.literal_eval(n.value)
    raise AssertionError(name)


def test_the_tables_of_the_base_commit_are_not_changed():
    assert {k: tuple(tuple(r) for r in v) for k, v in R.TYPED_FRAMES.items()} == {k: tuple(tuple(r) for r in v) for k, v in _frozen('TYPED_FRAMES').items()}
    assert R.TYPED_FRAMES_NOT_READ == _frozen('TYPED_FRAMES_NOT_READ')
    assert set(R.TYPED_FRAMES) == {'P_MOVE', 'P_COMMUNICATE'} and len(R.TYPED_FRAMES_NOT_READ) == 11


def test_the_second_table_is_composed_when_it_is_asked_not_copied_when_the_module_is_loaded(monkeypatch):
    patched = (('agent', ('が',), ('PERSON',), 'arg'),)
    monkeypatch.setitem(R.TYPED_FRAMES, 'P_MOVE', patched)
    assert R.typed_frames_v2()['P_MOVE'] == patched
    assert R.typed_frames_v2()['P_ACT'] == R.TYPED_FRAMES_W3B4['P_ACT']


# ===================================================================================================================================
# K160: the control flow. The reader file only gains lines; the plan of W3-b4 is the plan of W3-b2 with two names of the table; the entry is not changed
# ===================================================================================================================================
# Integration (auditor, 2026-10-04): the two scope tests below attest the discipline of the W3-b4 ticket itself (its commit against its own base);
# on dev other tickets merged after it (W5-e) legitimately touch coarse_place.py and insert lines into the reader, so they compare the ticket
# commit, not the working tree.
W3B4_BASE, W3B4_COMMIT = 'c875ed3', 'a8f1705'


def test_the_reader_file_only_gains_lines_and_the_other_files_of_the_ticket_are_not_touched():
    diff = git('diff', W3B4_BASE, W3B4_COMMIT, '--', 'verantyx/semantic_reader.py').splitlines()
    assert [l for l in diff if l.startswith('-') and not l.startswith('---')] == []
    for path in ('verantyx/semantic_read.py', 'verantyx/coarse_types.py', 'verantyx/coarse_place.py', 'verantyx/event_cross.py', 'verantyx/observe.py'):
        assert git('diff', W3B4_BASE, W3B4_COMMIT, '--', path) == '', path


def _plan_text(src, name, replacements=()):
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)
    body = node.body[1:] if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) else node.body      # without the docstring
    text = '\n'.join(ast.unparse(s) for s in body)
    for old, new in replacements: text = text.replace(old, new)
    return text, ast.dump(node.args)


def test_the_plan_of_w3b4_is_the_plan_of_w3b2_with_the_two_references_to_the_table_replaced():
    src = (TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')
    old, old_args = _plan_text(src, 'typed_plan_u_w3b2_ja', (('TYPED_FRAMES_NOT_READ', 'TYPED_FRAMES_NOT_READ_W3B4'), ('TYPED_FRAMES.get(ptype)', 'typed_frames_v2().get(ptype)')))
    new, new_args = _plan_text(src, 'typed_plan_u_w3b4_ja')
    assert old_args == new_args
    # Integration (auditor, 2026-10-04) per W3-b5 (docs 10F K200): the plan only GAINS lines (the frame_required kind of row); every statement of
    # the plan of W3-b2 is still there, in the same order
    import difflib
    assert [l for l in difflib.ndiff(old.splitlines(), new.splitlines()) if l.startswith('- ')] == []
    assert 'TYPED_FRAMES_NOT_READ_W3B4' in new and 'typed_frames_v2()' in new

def test_the_name_the_entry_calls_is_the_plan_of_w3b4_and_the_plan_of_w3b2_stays_under_a_name_of_its_own():
    # round 4 (K186): the two names the entry calls are the plans wrapped by the focus gate; the plan under the gate is the plan of rounds 1-3 (`ungated`)
    assert R.typed_plan_u_w3b2_ja.ungated is R.typed_plan_u_w3b4_ja
    assert R.typed_plan_u_ja.ungated is R.typed_plan_u_w3b1_ungated_ja
    assert R.typed_plan_u_w3b1_ungated_ja.__name__ == 'typed_plan_u_ja'                  # the function of the base commit, unchanged
    assert R.typed_plan_u_w3b2_v1_ja is not R.typed_plan_u_w3b4_ja and R.typed_plan_u_w3b2_v1_ja.__name__ == 'typed_plan_u_w3b2_ja'
    assert (R.typed_plan_u_w3b4_ja.__code__.co_names != R.typed_plan_u_w3b2_v1_ja.__code__.co_names)
    # the tail of the file (by ast, not by text): the last three statements are the round-4 replacement of the two names, and the one-line replacement of round 3 is still above them
    body = ast.parse((TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')).body
    def assign(n):
        return (n.targets[0].id, ast.unparse(n.value)) if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) else None
    # W1-a5 (docs 10G K210, H222): the section of W1-a5 is appended after these three statements; it does not assign these names again. The three statements are the last ones before it.
    start = next(i for i, n in enumerate(body) if isinstance(n, ast.Import) and ast.unparse(n) == 'import functools as _w1a5_functools')
    assert [assign(n) for n in body[start - 3:start]] == [('typed_plan_u_w3b1_ungated_ja', 'typed_plan_u_ja'), ('typed_plan_u_ja', '_typed_plan_focus_gated(typed_plan_u_w3b1_ungated_ja)'),
                                                         ('typed_plan_u_w3b2_ja', '_typed_plan_focus_gated(typed_plan_u_w3b4_ja)')]
    assert ('typed_plan_u_w3b2_ja', 'typed_plan_u_w3b4_ja') in [assign(n) for n in body[:start - 3]]
    assert not [n for n in body[start:] if (assign(n) or ('',))[0] in ('typed_plan_u_ja', 'typed_plan_u_w3b2_ja', 'typed_plan_u_w3b1_ungated_ja')]


def test_the_only_readers_of_a_placement_answer_are_still_the_gate_and_the_adapter():
    """W3-b4 adds no function that reads the fields of an answer (state, origin, top, decided_by, estimate_basis)."""
    src = git('show', '%s:verantyx/semantic_reader.py' % W3B4_COMMIT)       # the ticket's own file (see the note above)
    base = git('show', '%s:verantyx/semantic_reader.py' % W3B4_BASE)
    rx = re.compile(r"""\[\s*['"](state|origin|top|decided_by|estimate_basis)['"]\s*\]""")
    added = src[len(base):] if src.startswith(base) else None
    assert added is not None                                    # the file only gains lines, at its end
    assert rx.findall(added) == []


# ===================================================================================================================================
# the data
# ===================================================================================================================================
def answer_of(word, spec):
    if 'state' in spec: return F.bare(spec['state'], term=word)
    if spec.get('origin') == 'estimated': return F.to_estimated(F.answer(spec['top'], decided_by=['seed'], term=word), spec['basis'])
    return F.answer(spec['top'], decided_by=spec['decided_by'], term=word)


def query_of(row, mapper=None):
    answers = {w: answer_of(w, spec) for w, spec in row['placement'].items()}
    if mapper: answers = {w: mapper(a) for w, a in answers.items()}
    return F.MapQuery(answers)


def explain(row, mapper=None):
    return SR.typed_explain_ja(row['input'], query_of(row, mapper))


def test_the_data_has_the_registered_keys_ids_and_counts():
    keys = ['id', 'lang', 'input', 'text', 'behavior', 'expect', 'pred_type', 'path', 'construction', 'placement', 'entry_expect', 'w3b4_expect', 'note']
    assert len({r['input'] for r in DATA}) == len(DATA) == len({r['id'] for r in DATA})
    for r in DATA:
        assert list(r) == keys, r['id']
        assert r['input'] == r['text'] and r['lang'] == 'ja' and r['path'] in ('U', 'U3', 'S4', 'none') and r['entry_expect'] in ('read', 'abstain')
        assert re.fullmatch(r'W3B4-[A-Z]+-[RAX]-\d{3}', r['id']) and r['behavior'] == ('read' if r['expect']['readable'] else 'abstain')
        assert r['entry_expect'] == ('read' if r['id'].split('-')[2] == 'R' else 'abstain')
        errs = []
        b1.validate_item(r, errs)
        assert errs == [], (r['id'], errs)
    for t in READ_TYPES:
        read = [r for r in DATA if r['pred_type'] == t and r['entry_expect'] == 'read']
        abstain = [r for r in DATA if r['pred_type'] == t and r['entry_expect'] == 'abstain']
        assert len(read) >= 20 and len(abstain) >= 20, (t, len(read), len(abstain))
        assert any(r['path'] == 'U3' for r in read)
        # the groups of the ticket in the refused rows of every read type: split fillers, a particle not in the frame, the W1-a4 types
        text = ' '.join(r['construction'] for r in abstain)
        for marker in ('(a)', '(b)', '(c)', '(d)'): assert marker in text, (t, marker)
        assert any('あまり' in r['input'] or '全然' in r['input'] for r in abstain) and any(r['w3b4_expect'] == 'PLACEMENT_W3B2_NOT_TRIGGERED' for r in abstain), t
    for t in UNREAD_TYPES:
        assert len([r for r in DATA if r['pred_type'] == t and r['entry_expect'] == 'abstain']) >= 3, t


@pytest.mark.parametrize('row', DATA, ids=[r['id'] for r in DATA])
def test_every_row_of_the_data_is_read_or_refused_as_registered_and_judged_correct_when_read(row):
    q = query_of(row)
    out = SR.read(row['input'], placement=q)
    verdict = b1.judge(row['expect'], 'ja', out)['verdict']
    assert verdict not in ('misread', 'incomplete', 'UNJUDGED'), (verdict, out)
    ex = SR.typed_explain_ja(row['input'], query_of(row))
    e = row['w3b4_expect']
    if row['pred_type'] in NARROWED:
        # round 2: a narrowed type is not read. The entry refuses every row of it (whatever the frozen `entry_expect` said), and the diagnosis says why: the type of the predicate is not read,
        # unless the row is refused before the type is asked (a registered reason that stays: the trigger does not fire / the voice) -- then the registered reason is what is observed
        assert out['readable'] is False, out
        if ex['w3b2'] != 'PLACEMENT_FRAME_NOT_READ:' + row['pred_type']:
            assert row['entry_expect'] == 'abstain' and e in BEFORE_THE_TYPE, (row['id'], ex)
            if row['id'] in EXCEPTIONS: assert ex == EXCEPTIONS[row['id']]['observed_explain'], ex
            else: assert (ex['w3b2'] or '').startswith(e), (e, ex)
    elif row['id'] in NARROWED_ROWS:
        # round 3: a frozen row that the removal of the place/で rows changed. The entry refuses it (whatever the frozen `entry_expect` said), the diagnosis is the one recorded in `narrowed_rows.json`
        # (compared in full), and the record quotes the frozen row. It is checked BEFORE the declared rows: the three declared rows of these types are refused now with another reason
        rec = NARROWED_ROWS[row['id']]
        assert out['readable'] is False, out
        assert ex['w3b2'] == rec['observed_w3b2'] == 'PLACEMENT_PARTICLE_NOT_IN_FRAME:%s:で' % row['pred_type'], (ex, rec)
        assert rec['frozen_entry_expect'] == row['entry_expect'] and rec['frozen_w3b4_expect'] == row['w3b4_expect'] and rec['pred_type'] == row['pred_type']
        assert rec['declared_exception'] == (row['id'] in EXCEPTIONS)
    elif row['id'] in EXCEPTIONS:
        assert ('read' if out['readable'] else 'abstain') == row['entry_expect'], out
        # a declared row (artifacts/w3-b4/expect_exceptions.json): the entry does what the row registered; the REASON that was registered was a wrong prediction, so the observed one is pinned
        assert ex == EXCEPTIONS[row['id']]['observed_explain'] and verdict == EXCEPTIONS[row['id']]['observed_verdict'], (ex, verdict)
    else:
        assert ('read' if out['readable'] else 'abstain') == row['entry_expect'], out
        if e == 'READ': assert ex['w3b2'] == 'READ', ex
        else: assert (ex['w3b2'] or '').startswith(e), (e, ex)
    if out['readable']:
        assert verdict == 'correct', out
        rx = re.compile(R.W3B2_ROLE_BASIS_RE)
        clause = out['clauses'][0]
        assert clause['predicate_basis'] == 'placement_direct:' + row['pred_type'], clause
        assert set(clause['role_basis']) == set(clause['roles']), (clause['role_basis'], clause['roles'])
        for role, v in clause['role_basis'].items(): assert rx.fullmatch(v), (role, v)
    else:
        base = SR.read(row['input'], placement=None)
        assert out['abstain']['reasons'][0] == base['abstain']['reasons'][0], 'the first reason is the one of the reader alone'
    # a row the trigger fires for asks the placement (a row it does not fire for is refused by the reader alone). The only rows that fire the trigger and ask nothing are the rows refused
    # for the voice (a passive / causative is refused before the first question): round 1 had dropped this check altogether, round 2 restores it with that one exception
    if row['path'] != 'none' and ex['w3b2'] != 'PLACEMENT_VOICE_NOT_ACTIVE': assert q.calls
    assert set(q.calls) <= set(row['placement']), 'nothing is asked outside the words of the row'


def test_the_declared_exceptions_are_rows_of_the_frozen_data_each_explained_by_a_fact_and_none_is_a_wrong_reading():
    ids = {r['id']: r for r in DATA}
    assert set(EXCEPTIONS) <= set(ids) and 0 < len(EXCEPTIONS) <= 12
    for i, x in EXCEPTIONS.items():
        row = ids[i]
        assert x['kind'] in EXCEPTION_KINDS and x['input'] == row['input'] and x['frozen_w3b4_expect'] == row['w3b4_expect'] and x['frozen_entry_expect'] == row['entry_expect']
        assert x['observed_entry'] == row['entry_expect'] == 'abstain'                  # the entry does what the row registered
        assert x['observed_verdict'] not in ('misread', 'incomplete', 'UNJUDGED')
        assert x['observed_explain']['w3b2'] != 'READ' and not x['observed_explain']['w3b2'] == row['w3b4_expect']     # a real difference of the reason, never a row the new path read
        w3b2 = x['observed_explain']['w3b2']
        if x['kind'] == 'adjunct_arms_are_role_distributions_only':
            assert w3b2.startswith('PLACEMENT_SLOT_EVIDENCE_ONLY:')
            word = w3b2.split(':')[2]
            assert all(a.startswith('role@') for a in row['placement'][word]['decided_by']), i        # the fact is in the answer of the row, which is the answer of r7
        elif x['kind'] == 'entry_refuses_before_the_typed_step':
            assert w3b2 is None and SR.read(row['input'], placement=None)['abstain']['reasons'][0] == 'NO_PREDICATE_TOKEN'
        else:
            assert w3b2.startswith('PLACEMENT_REREAD_ABSTAINS:')


def test_no_row_of_the_data_is_misread_or_incomplete_and_every_read_type_is_read_in_at_least_twenty_rows():
    """Round 3: the NAME is kept (a test is not renamed) but the claim "every read type is read in at least twenty rows" is no longer true and is not made: after the place/で rows were taken out,
    the entry reads 4 rows of the data (P_ACT, へ/goal) and none of P_CREATE and P_EMOTION. What is checked instead: no row is misread or incomplete; of the frozen rows that registered `entry_expect: read`
    (at least twenty per read type, as registered) every row is either judged `correct` or is a recorded narrowed row that the entry refuses; and the number of rows judged `correct` is pinned to the measured
    one (artifacts/w3-b4/r3/per_type_counts.json): P_ACT 4, P_CREATE 0, P_EMOTION 0."""
    verdicts, entries = {}, {}
    for row in DATA:
        out = SR.read(row['input'], placement=query_of(row))
        verdicts[row['id']] = b1.judge(row['expect'], 'ja', out)['verdict']
        entries[row['id']] = out['readable']
    assert not [i for i, v in verdicts.items() if v in ('misread', 'incomplete', 'UNJUDGED')]
    for t in READ_TYPES:
        registered_read = [r for r in DATA if r['pred_type'] == t and r['entry_expect'] == 'read']
        assert len(registered_read) >= 20, t
        for r in registered_read:
            assert (entries[r['id']] and verdicts[r['id']] == 'correct') or (r['id'] in NARROWED_ROWS and not entries[r['id']]), r['id']
    assert {t: sum(1 for r in DATA if r['pred_type'] == t and verdicts[r['id']] == 'correct' and entries[r['id']]) for t in READ_TYPES} == {'P_ACT': 4, 'P_CREATE': 0, 'P_EMOTION': 0}
    assert sum(entries.values()) == 4


def test_with_no_placement_every_row_of_the_data_is_what_the_entry_of_the_base_commit_says():
    for row in DATA:
        assert SR.read(row['input'], placement=None) == BASE.read(row['input'], placement=None), row['id']
        assert SR.read(row['input'], placement='') == BASE.read(row['input'], placement=''), row['id']
        assert SR.typed_explain_ja(row['input'], None) == {'w3b1_trigger': None, 'w3b1': None, 'w3b2_trigger': None, 'w3b2': None, 'frame': None}


def test_the_six_types_that_stay_unread_are_refused_at_the_type_of_the_predicate_with_the_reason_of_the_type():
    row = next(r for r in DATA if r['id'] == 'W3B4-ACT-R-001')            # 兄が校庭で遊んだ。
    for t in UNREAD_TYPES:
        q = query_of(row)
        q.mapping['遊ぶ'] = F.answer(t, decided_by=['seed'], term='遊ぶ')
        ex = SR.typed_explain_ja(row['input'], q)
        assert ex['w3b2'] == 'PLACEMENT_FRAME_NOT_READ:' + t, (t, ex)
        assert SR.read(row['input'], placement=q)['readable'] is False
    # round 3: a type that is read has no place/で row, so 校庭で is refused for the particle (the type is read, the row is not in its table)
    for t in READ_TYPES:
        q = query_of(row)
        q.mapping['遊ぶ'] = F.answer(t, decided_by=['seed'], term='遊ぶ')
        assert SR.typed_explain_ja(row['input'], q)['w3b2'] == 'PLACEMENT_PARTICLE_NOT_IN_FRAME:%s:で' % t, t
        assert SR.read(row['input'], placement=q)['readable'] is False
    # and the sentence that a read type does read: へ/goal is a row of P_ACT only (兄が荷車を畑へ押した。 with the predicate 押す replaced)
    goal = next(r for r in DATA if r['id'] == 'W3B4-ACT-R-021')
    assert goal['input'] == '兄が荷車を畑へ押した。'
    for t in READ_TYPES:
        q = query_of(goal)
        q.mapping['押す'] = F.answer(t, decided_by=['seed'], term='押す')
        assert SR.typed_explain_ja(goal['input'], q)['w3b2'] == ('READ' if t == 'P_ACT' else 'PLACEMENT_PARTICLE_NOT_IN_FRAME:%s:へ' % t), t


@pytest.mark.parametrize('mapper', [lambda a: F.to_estimated(a, 'proximity'), lambda a: F.to_estimated(a, 'generated'), F.to_multiple], ids=['proximity', 'generated', 'split'])
def test_with_a_placement_that_only_estimates_or_splits_no_row_of_the_data_is_read(mapper):
    for row in DATA:
        out = SR.read(row['input'], placement=query_of(row, mapper))
        assert out['readable'] is False, row['id']
        assert out['abstain']['reasons'][0] == SR.read(row['input'], placement=None)['abstain']['reasons'][0], row['id']


def test_a_type_that_the_table_reads_is_read_with_the_frame_of_a_confirmed_predicate_only_when_the_frame_agrees():
    """K95 is unchanged: a CONFIRMED frame narrows what the table reads (the particle must be in it, every type of the role in its list). Round 3: the row is `W3B4-ACT-R-021` (へ/goal); a frame
    never adds a row to the table, so a frame that confirms で:PLACE does not make 兄が道路で荷車を押した。 readable (there is no place/で row for P_ACT)."""
    row = next(r for r in DATA if r['id'] == 'W3B4-ACT-R-021')            # 兄が荷車を畑へ押した。 (agent が, patient を, goal へ)
    q = query_of(row)
    frame_ok = {'が': ['ANIMAL', 'GROUP_ORG', 'PERSON'], 'を': ['ARTIFACT'], 'へ': ['PLACE']}
    q.mapping['押す'] = F.with_frame(dict(q.mapping['押す'], decided_by=['seed', 'gen_frame'], namespace='P'), 'CONFIRMED', frame_ok)
    assert SR.typed_explain_ja(row['input'], q)['w3b2'] == 'READ'
    q2 = query_of(row)
    q2.mapping['押す'] = F.with_frame(dict(q2.mapping['押す'], decided_by=['seed', 'gen_frame'], namespace='P'), 'CONFIRMED', {'が': ['ANIMAL', 'GROUP_ORG', 'PERSON'], 'を': ['ARTIFACT']})
    assert SR.typed_explain_ja(row['input'], q2)['w3b2'] == 'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:P_ACT:へ'
    road = next(r for r in DATA if r['id'] == 'W3B4-ACT-R-012')            # 兄が道路で荷車を押した。
    q3 = query_of(road)
    q3.mapping['押す'] = F.with_frame(dict(q3.mapping['押す'], decided_by=['seed', 'gen_frame'], namespace='P'), 'CONFIRMED', {'が': ['ANIMAL', 'GROUP_ORG', 'PERSON'], 'を': ['ARTIFACT'], 'で': ['PLACE']})
    assert SR.typed_explain_ja(road['input'], q3)['w3b2'] == 'PLACEMENT_PARTICLE_NOT_IN_FRAME:P_ACT:で'


def test_the_default_entry_reads_with_the_variable_and_with_the_option_the_same_as_with_a_placement_object():
    if not os.path.isdir(R7): pytest.skip('the placement r7 is not on this machine')
    text = '兄が荷車を畑へ押した。'
    env = dict(os.environ, PYTHONPATH=str(TREE), PYTHONDONTWRITEBYTECODE='1', VERA_PLACEMENT=R7)
    env.pop('VERA_COARSE_PLACEMENT', None)
    by_variable = subprocess.run([sys.executable, '-m', 'verantyx.semantic_read', '--text', text], capture_output=True, env=env, cwd=str(TREE)).stdout.decode('utf-8')
    env.pop('VERA_PLACEMENT')
    by_option = subprocess.run([sys.executable, '-m', 'verantyx.semantic_read', '--text', text, '--placement', R7], capture_output=True, env=env, cwd=str(TREE)).stdout.decode('utf-8')
    none = subprocess.run([sys.executable, '-m', 'verantyx.semantic_read', '--text', text], capture_output=True, env=env, cwd=str(TREE)).stdout.decode('utf-8')
    a, b, c = json.loads(by_variable), json.loads(by_option), json.loads(none)
    assert a == b and a['readable'] is True and a['clauses'][0]['roles'] == {'agent': '兄', 'patient': '荷車', 'goal': '畑'}
    assert c['readable'] is False
    # round 3: 兄が校庭で遊んだ。 (place/で of P_ACT is not in the table) is not read, with the variable and with the option alike
    text = '兄が校庭で遊んだ。'
    env['VERA_PLACEMENT'] = R7
    d = json.loads(subprocess.run([sys.executable, '-m', 'verantyx.semantic_read', '--text', text], capture_output=True, env=env, cwd=str(TREE)).stdout.decode('utf-8'))
    env.pop('VERA_PLACEMENT')
    e = json.loads(subprocess.run([sys.executable, '-m', 'verantyx.semantic_read', '--text', text, '--placement', R7], capture_output=True, env=env, cwd=str(TREE)).stdout.decode('utf-8'))
    assert d == e and d['readable'] is False


# ===================================================================================================================================
# round 2 (docs K165, table change records 1 and 2): the types that were taken out again after the review of round 1
# ===================================================================================================================================
def _registered_rows(type_id):
    """The rows the table REGISTERED for a type (artifacts/w3-b4/PREREG.md is the text of the registration and is not changed), in the form of the table of the code."""
    text = (TREE / 'artifacts' / 'w3-b4' / 'PREREG.md').read_text(encoding='utf-8')
    m = re.search(r'<!-- BEGIN table:w3b4_frames -->\n(.*?)<!-- END table:w3b4_frames -->', text, re.S)
    rows = []
    for line in m.group(1).splitlines():
        if not line.startswith('|') or set(line) <= set('|- '): continue
        c = [x.strip().strip('`') for x in line.strip().strip('|').split('|')]
        if c[0] == type_id: rows.append((c[1], (c[2],), tuple(c[3].split()), 'arg' if c[4] == '項' else 'adjunct'))
    return tuple(rows)


def test_the_narrowed_types_are_recorded_have_no_row_and_are_in_the_table_of_the_unread_types_with_their_reason():
    assert tuple(NARROWED) == ('P_CHANGE', 'P_CONSUME')
    assert tuple(R.TYPED_FRAMES_NOT_READ_W3B4)[-2:] == tuple(NARROWED)          # at the end, in the order of the docs
    for t, rec in NARROWED.items():
        assert R.TYPED_FRAMES_NOT_READ_W3B4[t] == rec['name'] and t not in R.typed_frames_v2() and t not in R.TYPED_FRAMES_W3B4
        assert [r for r in block('w3b4_not_read') if r[0] == t] == [[t, rec['name'], next(x[2] for x in block('w3b4_not_read') if x[0] == t)]]
        assert rec['narrowed_at'] and rec['reason'] and rec['source'] and rec['recorded_in']
        assert len(_registered_rows(t)) >= 4                                   # the registration did have rows for the type (PREREG.md is not changed)
    # only narrowing: the rows of the table are a subset of the registered ones
    registered = {(t, row) for t in ('P_ACT', 'P_CHANGE', 'P_CREATE', 'P_CONSUME', 'P_EMOTION') for row in _registered_rows(t)}
    for t, rows in R.TYPED_FRAMES_W3B4.items():
        for row in rows: assert (t, row) in registered, (t, row)
    assert len(code_rows(R.typed_frames_v2())) == 17 and len(block('w3b4_frames')) == 17      # round 3: 20 rows before the three place/で rows were taken out


def test_the_five_sentences_of_the_review_are_in_the_data_as_refused_rows_at_its_end_and_the_frozen_rows_stay():
    ids = [i for rec in NARROWED.values() for i in rec['rows_appended_to_the_data']]
    assert ids == ['W3B4-CHANGE-A-901', 'W3B4-CHANGE-A-902', 'W3B4-CHANGE-A-903', 'W3B4-CHANGE-A-904', 'W3B4-CONSUME-A-901']
    assert [r['id'] for r in DATA[318:323]] == ids and len(DATA) == 339      # round 3: ten more rows after them, round 4: six more
    for r in DATA[318:323]:
        assert r['entry_expect'] == 'abstain' and r['expect']['readable'] is False and r['behavior'] == 'abstain'
        assert r['w3b4_expect'] == 'PLACEMENT_FRAME_NOT_READ:' + r['pred_type'] and r['pred_type'] in NARROWED
    assert [r['input'] for r in DATA[318:323]] == ['会社が工場から店へ変わった。', 'チームが広場から体育館へ変わった。', '兄が田舎から都会へ変わった。', '学校が校舎から仮校舎へ変わった。', '兄が休みに金を使った。']
    # the first 318 rows are the frozen file (artifacts/w3-b4/bank_freeze.sha256): the file was only appended to
    import hashlib
    head = ''.join(l + '\n' for l in DATA_FILE.read_text(encoding='utf-8').splitlines()[:318]).encode('utf-8')
    frozen = (TREE / 'artifacts' / 'w3-b4' / 'bank_freeze.sha256').read_text(encoding='utf-8').split()[0]
    assert hashlib.sha256(head).hexdigest() == frozen


def test_the_five_sentences_were_misread_by_the_registered_rows_and_the_narrowed_table_refuses_them(monkeypatch):
    """The evidence for the narrowing, kept as a test: with the registered rows of the two types put back in memory (and the two types taken off the unread ones) the five sentences are READ and
    judged a misread; with the table as it is they are refused with the reason of the type. Nothing in the tree is changed by this test."""
    rows = DATA[318:323]
    for row in rows:
        out = SR.read(row['input'], placement=query_of(row))
        assert out['readable'] is False, row['input']
        assert SR.typed_explain_ja(row['input'], query_of(row))['w3b2'] == 'PLACEMENT_FRAME_NOT_READ:' + row['pred_type']
    for t in NARROWED:
        monkeypatch.setitem(R.TYPED_FRAMES_W3B4, t, _registered_rows(t))
        monkeypatch.delitem(R.TYPED_FRAMES_NOT_READ_W3B4, t)
    for row in rows:
        out = SR.read(row['input'], placement=query_of(row))
        assert out['readable'] is True, row['input']
        assert b1.judge(row['expect'], 'ja', out)['verdict'] == 'misread', (row['input'], out)
        assert SR.typed_explain_ja(row['input'], query_of(row))['w3b2'] == 'READ'


def test_every_row_of_a_narrowed_type_is_refused_by_the_entry_with_the_diagnosis_of_the_type_or_a_registered_reason_before_the_type():
    seen = {'type': 0, 'before_the_type': 0}
    for row in DATA:
        if row['pred_type'] not in NARROWED: continue
        assert SR.read(row['input'], placement=query_of(row))['readable'] is False, row['id']
        w3b2 = SR.typed_explain_ja(row['input'], query_of(row))['w3b2']
        seen['type' if w3b2 == 'PLACEMENT_FRAME_NOT_READ:' + row['pred_type'] else 'before_the_type'] += 1
    assert seen['type'] > 100 and 0 < seen['before_the_type'] <= 12, seen
    # the frozen read rows of the two types (27 and 29 rows) are the ones that the narrowing turned into refusals
    for t, n in (('P_CHANGE', 27), ('P_CONSUME', 29)):
        assert len([r for r in DATA if r['pred_type'] == t and r['entry_expect'] == 'read']) == n


# ===================================================================================================================================
# round 3 (docs K165, table change record 3): the rows place/で/PLACE of P_ACT, P_CREATE and P_EMOTION were taken out; the types stay
# ===================================================================================================================================
TEN = (('W3B4-ACT-A-901', 'P_ACT', '兄が右で打った。'), ('W3B4-ACT-A-902', 'P_ACT', '兄が右で皿を洗った。'), ('W3B4-ACT-A-903', 'P_ACT', '兄が右で皿を拭いた。'),
       ('W3B4-ACT-A-904', 'P_ACT', '兄が口で戦った。'), ('W3B4-CREATE-A-901', 'P_CREATE', '兄が右で絵を描いた。'), ('W3B4-CREATE-A-902', 'P_CREATE', '弟が右で記事を書いた。'),
       ('W3B4-CREATE-A-903', 'P_CREATE', '兄が口で絵を描いた。'), ('W3B4-CREATE-A-904', 'P_CREATE', '兄が口で手紙を書いた。'), ('W3B4-EMOTION-A-901', 'P_EMOTION', '兄が段差で驚いた。'),
       ('W3B4-EMOTION-A-902', 'P_EMOTION', '兄が口で笑った。'))


def test_the_narrowed_rows_are_recorded_and_the_three_rows_were_registered_and_are_gone():
    rec = NARROWED_ROWS_RECORD
    assert rec['rows_removed'] == [{'type': t, 'role': 'place', 'particle': 'で', 'types': ['PLACE'], 'kind': 'adjunct'} for t in READ_TYPES]
    assert rec['narrowed_at'] and rec['reason'] and rec['source'] and rec['recorded_in'] and rec['decided_by']
    assert rec['rows_appended_to_the_data'] == [i for i, t, text in TEN]
    for t in READ_TYPES:
        assert DE_ROW in _registered_rows(t)                                      # the registration (PREREG.md, not changed) did have the row
        assert DE_ROW not in R.typed_frames_v2()[t] and DE_ROW not in R.TYPED_FRAMES_W3B4[t]
        assert t not in R.TYPED_FRAMES_NOT_READ_W3B4                              # the type is not taken out: only the row
    # v1's rows place/で stay in the first table (P_MOVE, P_COMMUNICATE) and in the first nine rows of the docs
    for t in ('P_MOVE', 'P_COMMUNICATE'): assert DE_ROW in R.TYPED_FRAMES[t] and DE_ROW in R.typed_frames_v2()[t]
    # only narrowing: every row of the table is a registered row (the registered rows of the five types of the registration, and the two types of v1)
    registered = {(t, row) for t in ('P_ACT', 'P_CHANGE', 'P_CREATE', 'P_CONSUME', 'P_EMOTION') for row in _registered_rows(t)}
    for t, rows in R.TYPED_FRAMES_W3B4.items():
        for row in rows: assert (t, row) in registered, (t, row)
    assert len(NARROWED_ROWS) == 109 and {v['pred_type'] for v in NARROWED_ROWS.values()} == set(READ_TYPES)
    assert all(i in {r['id'] for r in DATA[:323]} for i in NARROWED_ROWS)         # only rows of the frozen part (the appended rows are refused as frozen)


def test_the_ten_sentences_of_review_r2_are_appended_as_refused_rows_and_the_frozen_rows_stay():
    import hashlib
    assert len(DATA) == 339     # round 4: six more rows after the ten (DATA[333:339])
    for r, (i, t, text) in zip(DATA[323:333], TEN):
        assert (r['id'], r['pred_type'], r['input']) == (i, t, text)
        assert r['entry_expect'] == 'abstain' and r['behavior'] == 'abstain' and r['expect'] == {'readable': False, 'clauses': [], 'relations': [], 'must_not': []}
        assert r['w3b4_expect'] == 'PLACEMENT_PARTICLE_NOT_IN_FRAME:%s:で' % t and r['path'] == 'U3'
        de = '右' if '右' in text else ('段差' if '段差' in text else '口')
        assert r['placement'][de] == {'top': ['PLACE'], 'decided_by': ['seed']}       # the filler of で is a seed answer (the optimistic fake): the misread appeared only that way
    lines = DATA_FILE.read_text(encoding='utf-8').splitlines()
    sha = lambda n: hashlib.sha256(''.join(l + '\n' for l in lines[:n]).encode('utf-8')).hexdigest()
    assert sha(318) == (TREE / 'artifacts' / 'w3-b4' / 'bank_freeze.sha256').read_text(encoding='utf-8').split()[0]
    assert sha(323) == (TREE / 'artifacts' / 'w3-b4' / 'r2' / 'bank_freeze_after_r2.sha256').read_text(encoding='utf-8').split()[0]


def test_the_ten_sentences_were_misread_with_the_place_de_rows_and_the_narrowed_table_refuses_them(monkeypatch):
    """The evidence for the narrowing, kept as a test: with the three rows put back in memory the ten sentences are READ and judged a misread (place 右 / 段差 / 口); with the table as it is they are
    refused for the particle. Nothing in the tree is changed (monkeypatch)."""
    rows = DATA[323:333]
    for r in rows:
        assert SR.read(r['input'], placement=query_of(r))['readable'] is False, r['input']
        assert SR.typed_explain_ja(r['input'], query_of(r))['w3b2'] == 'PLACEMENT_PARTICLE_NOT_IN_FRAME:%s:で' % r['pred_type']
    for t in READ_TYPES: monkeypatch.setitem(R.TYPED_FRAMES_W3B4, t, R.TYPED_FRAMES_W3B4[t] + (DE_ROW,))
    for r in rows:
        out = SR.read(r['input'], placement=query_of(r))
        assert out['readable'] is True, r['input']
        assert b1.judge(r['expect'], 'ja', out)['verdict'] == 'misread', (r['input'], out)
        assert SR.typed_explain_ja(r['input'], query_of(r))['w3b2'] == 'READ'
        assert 'place' in out['clauses'][0]['roles'], out


def test_the_rows_whose_diagnosis_the_narrowing_changed_are_exactly_the_recorded_rows(monkeypatch):
    frozen = DATA[:323]
    now = {r['id']: explain(r) for r in frozen}
    for t in READ_TYPES: monkeypatch.setitem(R.TYPED_FRAMES_W3B4, t, R.TYPED_FRAMES_W3B4[t] + (DE_ROW,))
    before = {r['id']: explain(r) for r in frozen}
    assert {i for i in now if now[i] != before[i]} == set(NARROWED_ROWS)             # 109 rows, no other row of the frozen data changes
    for r in frozen:
        if r['id'] not in NARROWED_ROWS: continue
        assert now[r['id']]['w3b2'] == NARROWED_ROWS[r['id']]['observed_w3b2'] and before[r['id']]['w3b2'] == NARROWED_ROWS[r['id']]['diagnosis_with_the_rows_put_back']
        # with the rows put back, the row is as it was registered: a declared row as pinned, the others as `entry_expect` and `w3b4_expect` say (and judged correct when read)
        out = SR.read(r['input'], placement=query_of(r))
        assert ('read' if out['readable'] else 'abstain') == r['entry_expect'], r['id']
        if r['id'] in EXCEPTIONS: assert before[r['id']] == EXCEPTIONS[r['id']]['observed_explain'], r['id']
        elif r['w3b4_expect'] == 'READ': assert before[r['id']]['w3b2'] == 'READ', r['id']
        else: assert (before[r['id']]['w3b2'] or '').startswith(r['w3b4_expect']), r['id']
        if out['readable']: assert b1.judge(r['expect'], 'ja', out)['verdict'] == 'correct', r['id']


# ===================================================================================================================================
# round 4 (docs K186, the auditor's decision 2): the gate of a focus particle right after a case particle, on the plans of paths U and U3
# ===================================================================================================================================
FOCUS_ROWS = DATA[333:339]
X_REFUSED = {'readable': False, 'clauses': [], 'relations': [], 'must_not': []}
GATE_PREFIX = 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE:'
SIX_SENTENCES = (('W3B4-ACT-A-911', '兄が台車を倉庫へさえ押した。', 'さえ'), ('W3B4-ACT-A-912', '兄が台車を倉庫へすら押した。', 'すら'), ('W3B4-ACT-A-913', '兄が台車を倉庫へこそ押した。', 'こそ'),
                 ('W3B4-ACT-A-914', '兄が台車を倉庫へまで押した。', 'まで'), ('W3B4-ACT-A-915', '兄が台車を倉庫へなど押した。', 'など'), ('W3B4-ACT-A-916', '兄が台車を倉庫へさえ押さなかった。', 'さえ'))


def ungate(monkeypatch):
    """Put the plans under the gate back (the plans of rounds 1-3), for the evidence. monkeypatch only: nothing leaks into another test."""
    monkeypatch.setattr(R, 'typed_plan_u_ja', R.typed_plan_u_ja.ungated)
    monkeypatch.setattr(R, 'typed_plan_u_w3b2_ja', R.typed_plan_u_w3b2_ja.ungated)


def _focus(text):
    return R.typed_focus_after_case_ja(R._tokens(text), SimpleNamespace(span=SimpleNamespace(start=0, end=len(text))))


def test_the_focus_gate_decides_by_parts_of_speech_and_adjacency_only():
    G = GATE_PREFIX
    cases = (('兄が台車を倉庫へさえ押した。', G + 'へ:さえ'), ('兄が荷車を畑へも押した。', G + 'へ:も'), ('兄が荷車を畑へは押した。', G + 'へ:は'),
             ('兄が台車をも倉庫へ押した。', G + 'を:も'), ('兄が台車を納屋からさえ倉庫へ押した。', G + 'から:さえ'), ('兄が国道でさえ走った。', G + 'で:さえ'),
             ('兄が荷車を畑へ、さえ押した。', G + 'へ:さえ'), ('兄が荷車を畑へ\u3000さえ押した。', G + 'へ:さえ'),
             ('兄が荷車を畑へと押した。', None), ('兄は荷車を畑へ押した。', None), ('兄が倉庫まで走った。', None), ('兄だけが倉庫へ走った。', None))
    for text, want in cases: assert _focus(text) == want, (text, _focus(text))
    # no list of words in the gate: the only string constants of its body are names of parts of speech and the format of the reason
    fn = next(n for n in ast.parse((TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef) and n.name == 'typed_focus_after_case_ja')
    body = fn.body[1:] if isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant) else fn.body
    consts = {c.value for st in body for c in ast.walk(st) if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    assert consts <= {'助詞', '格助詞', '係助詞', '副助詞', '補助記号', '空白', 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE:%s:%s'}, consts
    assert {'助詞', '格助詞', '係助詞', '副助詞'} <= consts


def test_the_six_sentences_of_review_w3b4_2_are_appended_as_refused_rows_and_the_frozen_rows_stay():
    import hashlib
    assert len(DATA) == 339 and len(FOCUS_ROWS) == 6
    for r, (i, text, part) in zip(FOCUS_ROWS, SIX_SENTENCES):
        assert (r['id'], r['input'], r['pred_type'], r['path']) == (i, text, 'P_ACT', 'U')
        assert r['entry_expect'] == 'abstain' and r['behavior'] == 'abstain' and r['expect'] == X_REFUSED
        assert r['w3b4_expect'] == GATE_PREFIX + 'へ:' + part
        # the placement is the answer of r7 as it is (nothing lifted to a seed): the misread appeared with the live r7
        for w in ('兄', '台車', '倉庫'): assert 'seed' not in r['placement'][w]['decided_by'], (i, w)
        assert r['placement']['押す'] == {'top': ['P_ACT'], 'decided_by': ['seed']}      # 押す is a word of the seed in r7 itself
    lines = DATA_FILE.read_text(encoding='utf-8').splitlines()
    sha = lambda n: hashlib.sha256(''.join(l + '\n' for l in lines[:n]).encode('utf-8')).hexdigest()
    assert sha(333) == (TREE / 'artifacts' / 'w3-b4' / 'r3' / 'bank_freeze_after_r3.sha256').read_text(encoding='utf-8').split()[0]
    assert sha(323) == (TREE / 'artifacts' / 'w3-b4' / 'r2' / 'bank_freeze_after_r2.sha256').read_text(encoding='utf-8').split()[0]
    assert sha(318) == (TREE / 'artifacts' / 'w3-b4' / 'bank_freeze.sha256').read_text(encoding='utf-8').split()[0]


def test_the_six_sentences_were_misread_without_the_focus_gate_and_the_gate_refuses_them(monkeypatch):
    """The evidence for the gate, kept as a test: with the gate the six sentences are refused (the diagnosis of the plan of W3-b4 is the reason of the gate; the output keeps the
    reason of the plan of W3-b1 that stops first); with the plans put back (monkeypatch) they are READ as goal 倉庫 and judged a misread."""
    for r in FOCUS_ROWS:
        out = SR.read(r['input'], placement=query_of(r))
        assert out['readable'] is False, r['input']
        assert SR.typed_explain_ja(r['input'], query_of(r))['w3b2'] == r['w3b4_expect']
        base = SR.read(r['input'], placement=None)
        assert out['abstain']['reasons'] == [base['abstain']['reasons'][0], 'PLACEMENT_FRAME_NOT_READ:P_ACT'], out['abstain']
    ungate(monkeypatch)
    for r in FOCUS_ROWS:
        out = SR.read(r['input'], placement=query_of(r))
        assert out['readable'] is True, r['input']
        assert out['clauses'][0]['roles'] == {'agent': '兄', 'patient': '台車', 'goal': '倉庫'}, out
        assert b1.judge(r['expect'], 'ja', out)['verdict'] == 'misread', (r['input'], out)
        assert SR.typed_explain_ja(r['input'], query_of(r))['w3b2'] == 'READ'


def test_the_focus_gate_closes_the_hole_of_v1_with_the_real_placement_r7(monkeypatch):
    if not os.path.isdir(R7): pytest.skip('the placement r7 is not on this machine')
    cases = (('兄が倉庫へさえ走った。', 'さえ'), ('兄が倉庫へすら走った。', 'すら'), ('兄が倉庫へまで走った。', 'まで'), ('兄が倉庫へ、さえ走った。', 'さえ'))
    for text, part in cases:
        out = SR.read(text, placement=R.CoarseQuery(R7))
        ex = SR.typed_explain_ja(text, R.CoarseQuery(R7))
        assert out['readable'] is False, text
        assert ex['w3b1'] == ex['w3b2'] == GATE_PREFIX + 'へ:' + part, (text, ex)
        assert out['abstain']['reasons'][1] == GATE_PREFIX + 'へ:' + part, out['abstain']
    ungate(monkeypatch)
    for text, part in cases:
        out = SR.read(text, placement=R.CoarseQuery(R7))
        assert out['readable'] is True and out['clauses'][0]['roles'] == {'agent': '兄', 'goal': '倉庫'}, (text, out)
        assert b1.judge(X_REFUSED, 'ja', out)['verdict'] == 'misread', (text, out)
        assert SR.typed_explain_ja(text, R.CoarseQuery(R7))['w3b1'] == 'READ'


def test_the_cost_of_the_focus_gate_correct_readings_with_mo_and_wa_after_a_case_particle_are_refused(monkeypatch):
    """A cost, recorded: the conventions (section 3) read a sentence with は or も after a case particle by dropping the particle, and that reading is correct. The gate decides by parts of speech
    and adjacency and keeps no list of words, so it does not tell は・も from さえ・すら. The two sentences below are refused now: a decrease of correct readings, not a misread."""
    if not os.path.isdir(R7): pytest.skip('the placement r7 is not on this machine')
    for text, part in (('兄が荷車を畑へも押した。', 'も'), ('兄が荷車を畑へは押した。', 'は')):
        out = SR.read(text, placement=R.CoarseQuery(R7))
        assert out['readable'] is False and SR.typed_explain_ja(text, R.CoarseQuery(R7))['w3b2'] == GATE_PREFIX + 'へ:' + part, (text, out)
    ungate(monkeypatch)
    for text in ('兄が荷車を畑へも押した。', '兄が荷車を畑へは押した。'):
        out = SR.read(text, placement=R.CoarseQuery(R7))
        assert out['readable'] is True and out['clauses'][0]['roles'] == {'agent': '兄', 'patient': '荷車', 'goal': '畑'}, (text, out)


def test_the_focus_gate_changes_no_diagnosis_and_no_output_of_the_frozen_rows(monkeypatch):
    frozen = DATA[:333]
    now = {r['id']: (SR.read(r['input'], placement=query_of(r)), explain(r)) for r in frozen}
    ungate(monkeypatch)
    before = {r['id']: (SR.read(r['input'], placement=query_of(r)), explain(r)) for r in frozen}
    assert now == before


def test_the_focus_gate_is_on_the_plans_of_paths_u_and_u3_only():
    for name in ('typed_plan_s4_ja', 'typed_plan_s4_w3b2_ja'): assert not hasattr(getattr(R, name), 'ungated'), name
    for name in ('typed_plan_u_ja', 'typed_plan_u_w3b2_ja'): assert callable(getattr(R, name).ungated), name
