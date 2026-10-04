"""W3-b6: the reader uses the ROLE FRAME of a predicate (stage R). The contract of the answer (docs/READING_SOUNDNESS.md section 10I, K270-K277): when the answer of a predicate has
`role_frame_status` CONFIRMED, `role_frame` = {particle: [{"role", "types"}]}; the reader reads a filler through a particle the table of K62 has no opinion about when exactly one role of the
frame declared for that particle holds the (direct) type of the filler. The registration, the data (`tests/reading_soundness/ja_r13.jsonl`, frozen) and these tests were written in this
order: registration (10I), data, tests (frozen), code. The placements the tests open are fakes made from the `placement` of each row (`tests/reading_soundness/w3b6_fakes.py`); the only real
placement is r8, read only, for the check that the fakes do not contradict it (skipped with ENV_MISSING when it is not there).
Run under a clean environment (env -i): a VERA_PLACEMENT left in the shell would change the default path of the entry.
"""
import ast
import collections
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent
RS = TREE / 'tests' / 'reading_soundness'
A = TREE / 'artifacts' / 'w3-b6'
BASE_COMMIT = '51c9693'
R8 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'


def _load_by_path(name, path):
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


W = _load_by_path('w3b6_fakes_in_test_w3b6', RS / 'w3b6_fakes.py')
RUN = _load_by_path('w3b6_run_rows_in_test_w3b6', A / 'tools' / 'run_rows.py')

from verantyx import coarse_types as CT    # noqa: E402
from verantyx import event_cross as EC    # noqa: E402
from verantyx import semantic_read as SR    # noqa: E402
from verantyx import semantic_reader as R    # noqa: E402

DOCS = (TREE / 'docs' / 'READING_SOUNDNESS.md').read_text(encoding='utf-8')
DATA_FILE = RS / 'ja_r13.jsonl'
DATA = [json.loads(l) for l in DATA_FILE.read_text(encoding='utf-8').splitlines() if l.strip()]
BY_ID = {r['id']: r for r in DATA}
EXC_FILE = A / 'expect_exceptions.json'              # a frozen expectation that a fact of the reader (not a misread) made wrong: declared with the observation
EXCEPTIONS = {e['id']: e for e in json.loads(EXC_FILE.read_text(encoding='utf-8'))['exceptions']} if EXC_FILE.exists() else {}
RULES = ('K270', 'K271', 'K272', 'K273', 'K274', 'K275', 'K276')


@pytest.fixture(autouse=True)
def _no_placement_in_the_environment(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)


def git(*args):
    return subprocess.run(['git', '-C', str(TREE)] + list(args), capture_output=True, check=True).stdout.decode('utf-8')


def block(name):
    m = re.search(r'<!-- BEGIN table:%s -->\n(.*?)<!-- END table:%s -->' % (name, name), DOCS, re.S)
    assert m, name
    lines = [line for line in m.group(1).splitlines() if line.startswith('|') and not set(line) <= set('|- ')][1:]
    return [[c.strip().strip('`') for c in line.strip().strip('|').split('|')] for line in lines]


_RECORDS = {}


def records():
    """The records of the tool for every row of the data (run once)."""
    if not _RECORDS:
        recs, problems = RUN.run_rows(DATA, EXCEPTIONS)
        _RECORDS['recs'] = {x['id']: x for x in recs}
        _RECORDS['problems'] = problems
    return _RECORDS['recs'], _RECORDS['problems']


def explain(row):
    return SR.typed_explain_ja(row['input'], W.query_of(row))


def read(row):
    return SR.read(row['input'], placement=W.query_of(row))


# ===================================================================================================================================
# the data
# ===================================================================================================================================
def test_the_data_has_the_registered_keys_ids_and_counts():
    keys = ['id', 'lang', 'input', 'text', 'behavior', 'expect', 'pred_type', 'path', 'particle', 'rule', 'construction', 'placement', 'placement_source', 'synthetic_words', 'frame_source',
            'entry_expect', 'w3b6_expect', 'plan_expect', 'role_basis', 'keyless_same', 'note', 'base_trigger']
    assert len({r['id'] for r in DATA}) == len(DATA)
    for r in DATA:
        assert list(r) == keys, r['id']
        assert r['input'] == r['text'] and r['lang'] == 'ja' and r['behavior'] in ('read', 'abstain') and r['entry_expect'] == r['behavior']
        assert re.fullmatch(r'W3B6-[A-Z0-9]+-[RAX]-\w+', r['id']), r['id']
        assert r['frame_source'] == 'synthetic_contract' and r['placement_source'] in ('r8', 'synthetic')
        assert (r['placement_source'] == 'synthetic') == bool(r['synthetic_words']), r['id']
        assert r['behavior'] != 'read' or r['expect']['must_not'], r['id']
        assert r['rule'] in RULES, r['id']
    read_rows = [r for r in DATA if r['behavior'] == 'read']
    abstain_rows = [r for r in DATA if r['behavior'] == 'abstain']
    assert len(read_rows) >= 25 and len(abstain_rows) >= 25
    for rule in RULES:
        assert sum(1 for r in DATA if r['rule'] == rule) >= 3, rule
        assert sum(1 for r in DATA if r['rule'] == rule and r['behavior'] == 'abstain') >= 3 or rule in ('K270',), rule


def test_the_eleven_lines_of_w3a6_n2_each_have_a_row_and_the_unreached_ones_are_said_so():
    ids = [r['id'] for r in DATA if r['id'].startswith('W3B6-N2-')]
    assert len(ids) >= 10
    by_pred = {}
    for r in DATA:
        if r['id'].startswith('W3B6-N2-'): by_pred.setdefault(next(w for w, s in r['placement'].items() if s.get('namespace') == 'P'), []).append(r)
    assert set(by_pred) >= {'停泊する', '通報する', '連絡する', '打つ', '驚く', '確認する', '集める', '分ける', '待つ', '運ぶ'}
    assert by_pred['分ける'][0]['behavior'] == 'abstain' and 'NOT_REACHED:TRIGGER_NONE' in by_pred['分ける'][0]['note']
    assert by_pred['集める'][0]['path'] == 'R-blocked' and by_pred['集める'][0]['plan_expect'] == 'READ' and 'HEAD_DERIVED_GATE' in by_pred['集める'][0]['note']


def test_the_frames_of_the_data_are_fakes_and_the_fake_words_do_not_contradict_r8():
    if not os.path.isdir(R8): pytest.skip('ENV_MISSING: placement r8')
    from verantyx import coarse_place as CP
    for r in DATA:
        for word, spec in r['placement'].items():
            if word in r['synthetic_words']: continue
            q = CP.query(word, placement=R8)
            if spec.get('namespace') == 'P':
                assert q['state'] == 'DECIDED' and q['origin'] == 'direct' and q['top'] == spec['top'], (r['id'], word)
            elif 'top' in spec and 'origin' not in spec:
                assert q['state'] in ('DECIDED', 'MULTIPLE') and q['origin'] == 'direct' and q['top'] == sorted(spec['top']) and q['decided_by'] == spec['decided_by'], (r['id'], word)
            elif spec.get('origin') == 'estimated':
                assert q['origin'] == 'estimated' and q['top'] == spec['top'], (r['id'], word)
            else:
                assert q['state'] == spec['state'], (r['id'], word)


def test_every_answer_the_fakes_make_keeps_the_contract_of_the_placement_and_the_three_keys_are_last_in_order():
    from verantyx import semantic_reader as RD
    for r in DATA:
        q = W.query_of(r)
        for word in r['placement']:
            a = q.query(word)
            assert not RD._placement_answer_problems(a), (r['id'], word, RD._placement_answer_problems(a))
            keys = list(a)
            if 'role_frame_status' in keys:
                assert keys[-3:] == ['role_frame_status', 'role_frame', 'role_frame_unconfirmed'], (r['id'], keys[-4:])
            else:
                assert not {'role_frame', 'role_frame_unconfirmed'} & set(keys)


# ===================================================================================================================================
# O2: every row of the frozen data (no misread; the diagnosis, the plan, the path and the role_basis as registered)
# ===================================================================================================================================
def test_no_row_is_misread_and_every_row_does_what_the_registration_says():
    recs, problems = records()
    bad = [(i, [k for k, ok in x['checks'].items() if not ok], x['diag'], x['plan'], x['path']) for i, x in recs.items() if not all(x['checks'].values())]
    assert problems.get('misread', 0) == 0 and problems.get('incomplete', 0) == 0 and problems.get('UNJUDGED', 0) == 0, problems
    assert bad == [], bad


def test_the_rows_that_are_read_are_judged_correct_and_a_read_row_never_reads_less_or_more_than_expected():
    recs, _ = records()
    for r in DATA:
        x = recs[r['id']]
        if r['behavior'] == 'read': assert x['entry'] == 'read' and x['verdict'] == 'correct', (r['id'], x)
        else: assert x['entry'] == 'abstain' and x['verdict'] == 'correct', (r['id'], x)      # the judge calls a refusal of a row that must be refused `correct`


def test_a_row_the_frame_reads_is_read_by_stage_r_and_says_so_in_role_basis():
    recs, _ = records()
    stage_r = [r for r in DATA if r['path'] == 'R']
    assert len(stage_r) >= 20
    for r in stage_r:
        x = recs[r['id']]
        assert x['entry'] == 'read' and x['path'] == 'R' and x['diag'] == 'READ', r['id']
        assert any(v.startswith('role_frame:') for v in x['role_basis'].values()), r['id']
        for role, basis in x['role_basis'].items():
            if basis.startswith('role_frame:'):
                _, pred, particle, typ = basis.split(':')
                assert pred == next(w for w, s in r['placement'].items() if s.get('namespace') == 'P') and typ in CT.NOUN_TYPES and particle in R._CASE_PARTICLES_9


def test_the_rows_that_the_reader_already_read_are_read_the_same_with_a_confirmed_frame_and_are_not_credited_to_stage_r():
    recs, _ = records()
    for r in DATA:
        if r['path'] in ('base', 'W3-b4'):
            x = recs[r['id']]
            assert x['path'] == r['path'] and x['entry'] == 'read'
            assert not any(v.startswith('role_frame:') for v in (x['role_basis'] or {}).values())
            kl = W.strip_role_frame(r)
            assert json.dumps(read(r), sort_keys=True, ensure_ascii=False) == json.dumps(read(kl), sort_keys=True, ensure_ascii=False), r['id']


# ===================================================================================================================================
# K277 / O4: no key, ESTIMATED, NO_ROLE_FRAME: the output is the output of the base (no key)
# ===================================================================================================================================
def test_without_the_keys_or_with_a_status_that_is_not_confirmed_the_output_is_the_output_without_keys():
    rows = [r for r in DATA if r['keyless_same']]
    assert len(rows) >= 8
    seen = set()
    for r in rows:
        kl = W.strip_role_frame(r)
        assert json.dumps(read(r), sort_keys=True, ensure_ascii=False) == json.dumps(read(kl), sort_keys=True, ensure_ascii=False), r['id']
        seen.add(next(s.get('role_frame_status', 'ABSENT') for s in r['placement'].values() if s.get('namespace') == 'P'))
    assert {'ESTIMATED', 'NO_ROLE_FRAME', 'ABSENT', 'CONFIRMED'} <= seen


def test_the_diagnosis_of_a_status_that_is_not_confirmed_names_the_status_and_a_missing_key_gives_the_reason_of_the_base():
    for r in DATA:
        pred = next(s for s in r['placement'].values() if s.get('namespace') == 'P')
        st = pred.get('role_frame_status', 'ABSENT')
        if st in ('ESTIMATED', 'NO_ROLE_FRAME') and pred.get('role_frame') is None and r['path'] in ('U', 'U3'):
            assert explain(r)['w3b2'] == 'ROLE_FRAME_NOT_CONFIRMED:' + st, r['id']
        if st == 'ABSENT' and r['path'] in ('U', 'U3'):
            why = explain(r)['w3b2']
            assert why is not None and not why.startswith('ROLE_FRAME_'), (r['id'], why)


def test_role_frame_unconfirmed_is_not_read_a_broken_value_changes_nothing():
    for rid in ('W3B6-K270-R-008', 'W3B6-K270-R-009', 'W3B6-K270-A-010'):
        r = BY_ID[rid]
        pred_word = next(w for w, s in r['placement'].items() if s.get('namespace') == 'P')
        for junk in (None, 'junk', 42, [1, 2], {'に': 'x'}, {'': {'': ''}}, {'で': [{'role': 'tool', 'reason': 'MAYBE'}]}):
            r2 = json.loads(json.dumps(r))
            r2['placement'][pred_word]['role_frame_unconfirmed'] = junk
            assert json.dumps(read(r2), sort_keys=True, ensure_ascii=False) == json.dumps(read(r), sort_keys=True, ensure_ascii=False), (rid, junk)
            assert explain(r2) == explain(r), (rid, junk)
    # and the key may be missing from the answer altogether when the other two are there: the reader does not need it
    r = json.loads(json.dumps(BY_ID['W3B6-K270-R-009']))
    q = W.query_of(r)
    pred_word = next(w for w, s in r['placement'].items() if s.get('namespace') == 'P')
    answers = {w: q.query(w) for w in r['placement']}
    del answers[pred_word]['role_frame_unconfirmed']
    assert SR.read(r['input'], placement=W.F.MapQuery(answers)) == read(BY_ID['W3B6-K270-R-009'])


# ===================================================================================================================================
# O4 (c): a word of relative position: the frame never declares it
# ===================================================================================================================================
def test_a_word_of_relative_position_is_refused_both_as_direct_and_as_split_with_a_frame_that_declares_place():
    rows = [r for r in DATA if r['id'].startswith('W3B6-K272-A-1') or r['id'].startswith('W3B6-K272-A-2')]
    assert len(rows) == 15
    recs, _ = records()
    for r in rows:
        x = recs[r['id']]
        assert x['entry'] == 'abstain' and x['diag'] == r['w3b6_expect'], r['id']
        spec = r['placement'].get('右') or r['placement'].get('左')
        assert 'RELATIVE_POSITION' in spec['top']
        if r['particle'] == 'で' and spec['top'] == ['RELATIVE_POSITION']: assert x['diag'] == 'ROLE_FRAME_FILLER_RELATIVE_POSITION:で', r['id']
        if r['particle'] == 'で' and len(spec['top']) == 2: assert x['diag'] == 'ROLE_FRAME_FILLER_NOT_DIRECT:で:PLACEMENT_MULTIPLE', r['id']
    # the five sentences of W3-b4 bundle d are there in both forms
    for src in ('W3B4-ACT-A-901', 'W3B4-ACT-A-902', 'W3B4-ACT-A-903', 'W3B4-CREATE-A-901', 'W3B4-CREATE-A-902'):
        assert sum(1 for r in rows if src in r['construction']) == 2, src
    # the four reasons of the two particles: stage R says it where the table has no opinion; where the table has a row of an adjunct (P_MOVE ni = time) its own gate stops first (H273)
    assert {r['w3b6_expect'] for r in rows} == {'ROLE_FRAME_FILLER_RELATIVE_POSITION:で', 'ROLE_FRAME_FILLER_NOT_DIRECT:で:PLACEMENT_MULTIPLE', 'ROLE_FRAME_FILLER_RELATIVE_POSITION:に',
                                                  'ROLE_FRAME_FILLER_NOT_DIRECT:に:PLACEMENT_MULTIPLE', 'PLACEMENT_SLOT_EVIDENCE_ONLY:に:左'}
    frame_places = [r for r in rows if r['particle'] == 'で']
    for r in frame_places:
        pred = next(s for s in r['placement'].values() if s.get('namespace') == 'P')
        assert any('PLACE' in e['types'] for e in pred['role_frame']['で']) and R.predicate_role_frame(W.answer_of('x', pred))[0] == 'confirmed'


def test_relative_position_is_not_a_type_a_frame_may_declare_and_a_frame_that_writes_it_is_invalid():
    assert 'RELATIVE_POSITION' not in CT.NOUN_TYPES
    r = BY_ID['W3B6-K273-A-905']
    assert 'RELATIVE_POSITION' in json.dumps(r['placement'], ensure_ascii=False)
    assert explain(r)['w3b2'] == 'ROLE_FRAME_INVALID:TYPE_NOT_NOUN:で:RELATIVE_POSITION'


# ===================================================================================================================================
# O4 (d): a frame that breaks the contract: 6 ways and more; the whole sentence is refused (also a sentence the table read)
# ===================================================================================================================================
def test_an_invalid_frame_refuses_the_whole_sentence_with_the_reason_of_the_problem():
    rows = [r for r in DATA if r['id'].startswith('W3B6-K273-A-9') and r['id'] != 'W3B6-K273-A-914']
    assert len(rows) >= 8
    recs, _ = records()
    for r in rows:
        x = recs[r['id']]
        assert x['entry'] == 'abstain' and x['diag'].startswith('ROLE_FRAME_INVALID:'), r['id']
    assert len({r['w3b6_expect'].split(':')[1] for r in rows}) >= 8


def test_an_invalid_frame_refuses_even_a_sentence_the_table_reads():
    r = json.loads(json.dumps(BY_ID['W3B6-K274-R-002']))        # the table reads it (W3-b4); a broken frame on the predicate stops it
    pred_word = next(w for w, s in r['placement'].items() if s.get('namespace') == 'P')
    r['placement'][pred_word]['role_frame'] = {'は': [{'role': 'agent', 'types': ['PERSON']}]}
    assert read(BY_ID['W3B6-K274-R-002'])['readable']
    out = read(r)
    assert not out['readable']
    assert explain(r)['w3b2'] == 'ROLE_FRAME_INVALID:PARTICLE_NOT_CASE:は'


# ===================================================================================================================================
# the reader of the contract: every problem, one by one
# ===================================================================================================================================
def _answer(status='CONFIRMED', frame=None, keys=True):
    a = W.answer_of('x', {'top': ['P_ACT'], 'namespace': 'P', 'decided_by': ['seed']})
    if keys:
        a['role_frame_status'] = status; a['role_frame'] = frame; a['role_frame_unconfirmed'] = None
    return a


GOOD = {'で': [{'role': 'instrument', 'types': ['ARTIFACT']}], 'が': [{'role': 'agent', 'types': ['PERSON', 'ANIMAL']}]}


def test_predicate_role_frame_reads_a_well_formed_frame():
    kind, info = R.predicate_role_frame(_answer('CONFIRMED', GOOD))
    assert kind == 'confirmed' and info == {'で': (('instrument', frozenset({'ARTIFACT'})),), 'が': (('agent', frozenset({'PERSON', 'ANIMAL'})),)}
    assert R.predicate_role_frame(_answer(keys=False)) == ('absent', None)
    assert R.predicate_role_frame(_answer('ESTIMATED', None)) == ('not_confirmed', 'ESTIMATED')
    assert R.predicate_role_frame(_answer('NO_ROLE_FRAME', None)) == ('not_confirmed', 'NO_ROLE_FRAME')


def _missing_role_frame():
    a = _answer('CONFIRMED', GOOD)
    del a['role_frame']
    return a


PROBLEMS = [
    (lambda: _answer('MAYBE', GOOD), 'STATUS_UNKNOWN'),
    (lambda: _missing_role_frame(), 'MISSING_ROLE_FRAME'),
    (lambda: _answer('ESTIMATED', GOOD), 'FRAME_WITHOUT_CONFIRMED'),
    (lambda: _answer('NO_ROLE_FRAME', GOOD), 'FRAME_WITHOUT_CONFIRMED'),
    (lambda: _answer('CONFIRMED', None), 'NOT_A_MAPPING'),
    (lambda: _answer('CONFIRMED', []), 'NOT_A_MAPPING'),
    (lambda: _answer('CONFIRMED', 'x'), 'NOT_A_MAPPING'),
    (lambda: _answer('CONFIRMED', {'は': [{'role': 'agent', 'types': ['PERSON']}]}), 'PARTICLE_NOT_CASE:は'),
    (lambda: _answer('CONFIRMED', {'で': []}), 'ENTRIES_NOT_A_LIST:で'),
    (lambda: _answer('CONFIRMED', {'で': {'role': 'instrument', 'types': ['ARTIFACT']}}), 'ENTRIES_NOT_A_LIST:で'),
    (lambda: _answer('CONFIRMED', {'で': ['instrument']}), 'ENTRY_NOT_A_MAPPING:で'),
    (lambda: _answer('CONFIRMED', {'で': [{'role': 'instrument'}]}), 'ENTRY_KEYS:で'),
    (lambda: _answer('CONFIRMED', {'で': [{'role': 'instrument', 'types': ['ARTIFACT'], 'x': 1}]}), 'ENTRY_KEYS:で'),
    (lambda: _answer('CONFIRMED', {'で': [{'role': 'tool', 'types': ['ARTIFACT']}]}), 'ROLE_NOT_IN_CONVENTION:で:tool'),
    (lambda: _answer('CONFIRMED', {'で': [{'role': 'instrument', 'types': []}]}), 'TYPES_NOT_A_LIST:で'),
    (lambda: _answer('CONFIRMED', {'で': [{'role': 'instrument', 'types': 'ARTIFACT'}]}), 'TYPES_NOT_A_LIST:で'),
    (lambda: _answer('CONFIRMED', {'で': [{'role': 'instrument', 'types': ['ARTIFACT', '']}]}), 'TYPES_NOT_A_LIST:で'),
    (lambda: _answer('CONFIRMED', {'で': [{'role': 'instrument', 'types': ['RELATIVE_POSITION']}]}), 'TYPE_NOT_NOUN:で:RELATIVE_POSITION'),
    (lambda: _answer('CONFIRMED', {'で': [{'role': 'instrument', 'types': ['ARTIFACT']}, {'role': 'instrument', 'types': ['PLACE']}]}), 'ROLE_DUPLICATED:で:instrument'),
]


@pytest.mark.parametrize('make,problem', PROBLEMS)
def test_predicate_role_frame_names_each_problem(make, problem):
    assert R.predicate_role_frame(make()) == (None, 'ROLE_FRAME_INVALID:' + problem)


def test_the_problems_of_the_reader_are_the_registered_list():
    registered = set(re.findall(r'`([A-Z_]+)(?::<[^`]*)?[`（]', DOCS[DOCS.index('### 契約外の形の problem'):DOCS.index('### 理由名（`W3B6_REASON_NAMES`')]))
    used = {p.split(':')[0] for _, p in PROBLEMS}
    assert used <= registered and len(used) == 12 and {'STATUS_UNKNOWN', 'MISSING_ROLE_FRAME', 'FRAME_WITHOUT_CONFIRMED', 'NOT_A_MAPPING'} <= used


def test_the_reader_of_the_contract_reads_two_keys_and_the_code_never_names_role_frame_unconfirmed():
    src = (TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')
    i = src.index('# W3-b6:')
    tree = ast.parse(src[i:])
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'predicate_role_frame')
    keys = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith('role_frame'): keys.add(node.value)
    assert keys == {'role_frame_status', 'role_frame'}, keys
    # the code (docstrings and comments left out) of the whole file has no string constant that is the third key
    docstrings = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.Module)) and node.body and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], 'value', None), ast.Constant):
            docstrings.add(id(node.body[0].value))
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            assert 'role_frame_unconfirmed' not in node.value
        if isinstance(node, ast.Name): assert 'role_frame_unconfirmed' not in node.id
    # the other keys of the answer are read through the gates of the base, not here
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and isinstance(node.value, str): assert node.value not in ('state', 'origin', 'top', 'decided_by', 'estimate_basis'), node.value


# ===================================================================================================================================
# the registered reasons and tables
# ===================================================================================================================================
def test_the_reasons_and_the_kinds_of_the_docs_are_the_constants_of_the_code():
    assert [r[0] for r in block('w3b6_reasons')] == list(R.W3B6_REASON_NAMES)
    assert R.W3B6_REASON_NAMES == ('ROLE_FRAME_NOT_CONFIRMED', 'ROLE_FRAME_FILLER_NOT_DIRECT', 'ROLE_FRAME_FILLER_RELATIVE_POSITION', 'ROLE_FRAME_TYPE_NOT_DECLARED', 'ROLE_FRAME_SPLIT',
                                   'ROLE_FRAME_PARTICLE_NOT_DECLARED', 'ROLE_FRAME_INVALID', 'ROLE_FRAME_TABLE_CONFLICT', 'ROLE_FRAME_MULTIPLE_FILLERS')
    kinds = block('w3b6_role_kinds')
    assert [r[0] for r in kinds] == list(R.W3B6_ROLE_KINDS) and len(kinds) == 20 and sorted(R.W3B6_ROLE_KINDS) == sorted(EC.ROLE_NAMES)      # the docs list the six roles of the table first
    assert {r[0]: r[1] for r in kinds} == R.W3B6_ROLE_KINDS
    assert set(R.W3B6_ROLE_KINDS.values()) == {'arg', 'adjunct'}
    # the six roles the table has: the kind of the table
    table = {}
    for rows in R.typed_frames_v2().values():
        for role, parts, exp, kind in rows: table.setdefault(role, set()).add(kind)
    assert all(len(v) == 1 for v in table.values())
    for role, kinds_of in table.items(): assert R.W3B6_ROLE_KINDS[role] == next(iter(kinds_of)), role
    assert sorted(table) == ['agent', 'goal', 'patient', 'place', 'source', 'time']
    for row in kinds:
        assert (row[2] == '表') == (row[0] in table), row
    # every reason of the data is a registered name (or a reason of the plan of the base that the registration says is kept)
    for r in DATA:
        w = r['w3b6_expect']
        if w.startswith('ROLE_FRAME_'): assert w.split(':')[0] in R.W3B6_REASON_NAMES, r['id']


def test_the_reason_names_of_stage_r_are_the_closed_list_and_the_gate_reasons_are_reused_by_name():
    src = (TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')
    section = src[src.index('# W3-b6:'):]
    used = set(re.findall(r"'(ROLE_FRAME_[A-Z_]+)", section))
    assert used <= set(R.W3B6_REASON_NAMES) and used >= set(R.W3B6_REASON_NAMES) - set()
    reused = set(re.findall(r"'(PLACEMENT_[A-Z_]+)", section))
    assert reused <= {'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED', 'PLACEMENT_FRAME_TYPE_NOT_CONFIRMED', 'PLACEMENT_DUPLICATE_ROLE', 'PLACEMENT_INVALID', 'PLACEMENT_FRAME_NOT_READ',
                      'PLACEMENT_PARTICLE_NOT_IN_FRAME', 'PLACEMENT_TYPE_MISMATCH', 'PLACEMENT_MULTIPLE'}, reused


# ===================================================================================================================================
# the particles, K276, K274: mechanism checks beyond the data
# ===================================================================================================================================
def test_the_particles_stage_r_reads_are_the_seven_without_ga_and_wo():
    src = (TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')
    section = src[src.index('# W3-b6:'):]
    assert '_CASE_PARTICLES_9' in section
    assert all(ord(ch) < 128 for ch in section)
    assert [p for p in R._CASE_PARTICLES_9 if p not in ('が', 'を')] == ['に', 'で', 'へ', 'と', 'から', 'まで', 'より']


def test_a_conflict_between_the_frame_and_what_the_table_decided_refuses_the_sentence_and_never_overwrites_the_table():
    rows = [r for r in DATA if r['id'].startswith('W3B6-K274-A-')] + [BY_ID['W3B6-K271-A-007']]
    assert len(rows) == 7                    # r2 (review r1 M1): +K274-A-007 (case B) and K274-A-008 (case A): the frame holds the type in 2 roles, none of them is the one of the table
    recs, _ = records()
    for r in rows:
        x = recs[r['id']]
        assert x['entry'] == 'abstain' and x['diag'].startswith('ROLE_FRAME_TABLE_CONFLICT:') and x['plan'] == x['diag'], r['id']
        _, particle, table_role, frame_role = x['diag'].split(':')
        assert table_role != frame_role and particle in R._CASE_PARTICLES_9
    # a sentence the table reads (case A): without the frame the base reads it; with the conflicting frame it is refused, never read with the role of the frame
    for rid in ('W3B6-K274-A-003', 'W3B6-K274-A-004', 'W3B6-K274-A-008'):
        r = BY_ID[rid]
        base_out = read(W.strip_role_frame(r))
        assert base_out['readable'] and not read(r)['readable']
        assert explain(r)['w3b2'].startswith('ROLE_FRAME_TABLE_CONFLICT:')


def test_when_the_frame_agrees_the_table_is_not_touched_the_output_of_a_sentence_the_table_reads_is_the_output_of_the_base():
    r = BY_ID['W3B6-K274-R-002']
    out = read(r)
    assert out['readable'] and out['clauses'][0]['roles'] == {'agent': '兄', 'patient': '箱', 'goal': '工場', 'source': '倉庫'}
    typed, why = R.typed_plan_u_w3b2_ja.ungated(*_plan_args(r), **_plan_kwargs(r))
    assert why is None and all(not v.startswith('role_frame:') for v in typed['role_basis'].values())
    body = R.typed_plan_u_w3b4_body_ja(*_plan_args(r)[:3], **_plan_kwargs(r))
    assert body[1] is None and body[0]['role_basis'] == typed['role_basis'] and list(body[0]) == list(typed)


def _plan_args(row):
    view = R.document_view({'d': row['input']})
    toks = R._tokens(row['input'])
    return view.clauses[0], toks, W.query_of(row)


def _plan_kwargs(row):
    return dict(voice='active', written=row['expect']['clauses'][0]['predicate'] if row['expect']['clauses'] else None, strip=lambda role: role.span.text, role_map=SR._ROLE_TABLE)


def test_a_sentence_the_stage_does_not_reach_is_returned_untouched_and_nothing_is_asked_that_the_base_does_not_ask():
    for rid in ('W3B6-K270-A-003', 'W3B6-K270-A-004', 'W3B6-K270-A-006', 'W3B6-K270-A-007'):
        r = BY_ID[rid]
        kl = W.strip_role_frame(r)
        q1, q2 = W.query_of(r), W.query_of(kl)
        o1, o2 = SR.read(r['input'], placement=q1), SR.read(kl['input'], placement=q2)
        assert json.dumps(o1, sort_keys=True, ensure_ascii=False) == json.dumps(o2, sort_keys=True, ensure_ascii=False), rid
        assert sorted(set(q1.calls)) == sorted(set(q2.calls)), (rid, q1.calls, q2.calls)


def test_with_keys_that_do_not_matter_the_words_asked_are_the_words_the_base_asks():
    for r in DATA:
        if r['path'] in ('base', 'W3-b4') or r['w3b6_expect'].startswith(('ROLE_FRAME_NOT_CONFIRMED', 'PLACEMENT_W3B2_NOT_TRIGGERED')):
            kl = W.strip_role_frame(r)
            q1, q2 = W.query_of(r), W.query_of(kl)
            SR.read(r['input'], placement=q1); SR.read(kl['input'], placement=q2)
            assert sorted(set(q1.calls)) == sorted(set(q2.calls)), (r['id'], q1.calls, q2.calls)


# ===================================================================================================================================
# the wiring (H270) and the scope of the change
# ===================================================================================================================================
def test_the_wiring_the_plan_of_w3b4_stays_under_a_name_and_the_entry_calls_it_then_stage_r():
    assert R.typed_plan_u_w3b4_ja.__wrapped__ is R.typed_plan_u_w3b4_body_ja
    assert R.typed_plan_u_w3b2_ja.ungated is R.typed_plan_u_w3b4_ja
    assert R.typed_plan_u_w3b2_ja.__name__ == 'typed_plan_u_w3b4_ja_focus_gated'
    assert R.typed_plan_u_w3b4_body_ja.__name__ == 'typed_plan_u_w3b4_ja'
    base_src = git('show', '%s:verantyx/semantic_reader.py' % BASE_COMMIT)
    base_fn = next(n for n in ast.parse(base_src).body if isinstance(n, ast.FunctionDef) and n.name == 'typed_plan_u_w3b4_ja')
    now_fn = next(n for n in ast.parse((TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')).body if isinstance(n, ast.FunctionDef) and n.name == 'typed_plan_u_w3b4_ja')
    assert ast.dump(base_fn) == ast.dump(now_fn)


def test_the_change_is_two_insertions_in_the_reader_and_nothing_else_outside_the_allowed_paths():
    diff = git('diff', '-U0', BASE_COMMIT, '--', 'verantyx/semantic_reader.py').splitlines()
    assert [l for l in diff if l.startswith('-') and not l.startswith('---')] == []
    hunks = [l for l in diff if l.startswith('@@')]
    assert len(hunks) == 2 and all(re.match(r'@@ -\d+(,0)? \+\d+(,\d+)? @@', h) for h in hunks)
    # `tests/attack/w3a3/r6_48_queries.jsonl` is rewritten by an existing test of the suite while it runs (a side effect, not a change of this ticket): it is not counted
    changed = (set(git('diff', '--name-only', BASE_COMMIT).split()) - {'tests/attack/w3a3/r6_48_queries.jsonl'}) | set(git('ls-files', '--others', '--exclude-standard').split())
    for p in changed:
        assert (p == 'verantyx/semantic_reader.py' or p == 'docs/READING_SOUNDNESS.md' or p.startswith('tests/test_semantic_read_w3b6') or p.startswith('tests/reading_soundness/')
                or p.startswith('artifacts/w3-b6/')), p
    assert git('diff', '--name-only', BASE_COMMIT, '--', 'verantyx').split() == ['verantyx/semantic_reader.py']
    docs_diff = git('diff', '-U0', BASE_COMMIT, '--', 'docs/READING_SOUNDNESS.md').splitlines()
    assert [l for l in docs_diff if l.startswith('-') and not l.startswith('---')] == []


def test_the_top_level_definitions_of_the_base_are_unchanged_and_the_new_constants_are_the_two_registered():
    base = ast.parse(git('show', '%s:verantyx/semantic_reader.py' % BASE_COMMIT))
    now = ast.parse((TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8'))

    def defs(tree):
        out = {}
        for n in tree.body:
            if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name not in out: out[n.name] = ast.dump(n)
        return out
    b, n = defs(base), defs(now)
    assert {k: v for k, v in n.items() if k in b} == b
    assert set(n) - set(b) == {'_typed_plan_u_w3b6_ja', 'predicate_role_frame', 'typed_plan_u_w3b6_stage_r_ja'} | {k for k in n if k.startswith('_w3b6_')}

    def assigned(tree):
        out = set()
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name): out.add(t.id)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name): out.add(node.target.id)
        return out
    new_names = assigned(now) - assigned(base)
    assert new_names == {'W3B6_REASON_NAMES', 'W3B6_ROLE_KINDS', 'typed_plan_u_w3b4_body_ja', 'typed_plan_u_w3b4_ja'}, new_names     # the last is the wrapped plan (H270): a def in the base, assigned again here
    consts = [name for name in new_names if not callable(getattr(R, name))]
    assert sorted(consts) == ['W3B6_REASON_NAMES', 'W3B6_ROLE_KINDS']


def test_the_end_of_the_reader_has_no_word_of_a_sentence_and_assigns_none_of_the_names_of_the_entry():
    src = (TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')
    i = src.index('# W3-b6:')
    tree = ast.parse(src[i:])
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert all(ord(ch) < 128 for ch in node.value), node.value
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                assert not (isinstance(t, ast.Name) and t.id in ('typed_plan_u_ja', 'typed_plan_u_w3b2_ja', 'typed_plan_u_w3b4_ja', 'typed_plan_u_w3b1_ungated_ja')), t.id


def test_the_data_and_the_tests_are_the_frozen_ones():
    freezes = [A / 'bank_freeze.sha256'] + sorted(A.glob('bank_freeze.r*.sha256'))       # the first is the freeze before the implementation; a later one (bank_freeze.r2.sha256 ...) records a change declared in docs 10I
    assert freezes[0].exists()
    freeze = freezes[-1]
    import hashlib
    for line in freeze.read_text(encoding='utf-8').splitlines():
        digest, path = line.split(None, 1)
        assert hashlib.sha256((TREE / path.strip()).read_bytes()).hexdigest() == digest, path


def test_the_prereg_is_before_the_freeze_and_the_freeze_before_the_implementation():
    pre = (A / 'prereg_time.txt').read_text(encoding='utf-8').split('\n')[0]
    frz = (A / 'bank_freeze_time.txt').read_text(encoding='utf-8').strip()
    impl = (A / 'impl_start_time.txt').read_text(encoding='utf-8').strip()
    assert pre < frz < impl, (pre, frz, impl)


def test_r2_a_frame_with_two_roles_for_the_type_none_of_them_the_one_of_the_table_is_a_conflict_but_one_that_includes_it_is_not():
    a7, a8, r9 = BY_ID['W3B6-K274-A-007'], BY_ID['W3B6-K274-A-008'], BY_ID['W3B6-K274-R-009']
    assert explain(a7)['w3b2'] == 'ROLE_FRAME_TABLE_CONFLICT:が:agent:experiencer+patient' and not read(a7)['readable']
    assert explain(a8)['w3b2'] == 'ROLE_FRAME_TABLE_CONFLICT:へ:goal:place+source' and not read(a8)['readable']
    assert len(explain(a7)['w3b2'].split(':')) == 4 and len(explain(a8)['w3b2'].split(':')) == 4
    out = read(r9)
    assert out['readable'] and out['clauses'][0]['roles'] == {'agent': '姉', 'patient': '肉', 'instrument': 'ナイフ'}
