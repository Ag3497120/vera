"""W3-c7: compound sentences v1 (3-4 clauses of finite cuts, te / continuative with a subject on both sides, quotation, no sharing of a case across clauses, anaphora refused).
The rules and the closed tables were registered in docs/READING_SOUNDNESS.md section 10K (K300-K307, H300-H308) before the data (w3c7_*.jsonl, first frozen: artifacts/w3-c7/data_freeze.sha256,
copy in artifacts/w3-c7/frozen_r1/; refrozen in round 4: data_freeze.r4.sha256) and this file were written. Placement answers come from a recorded fake (w3c7_placement_r9.jsonl: the answers of the real r9, recorded as they came) and from the fixture of W3-b3;
no real placement is opened. Run under a clean environment (env -i): a VERA_PLACEMENT left in the shell would change the default path of the entry.
"""
import ast
import copy
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent
RS = TREE / 'tests' / 'reading_soundness'
FROZEN_R1 = TREE / 'artifacts' / 'w3-c7' / 'frozen_r1'
DERIVED_REASON = 'CLAUSE_FORM_NOT_READ:PLACEMENT_PREDICATE_POSSIBLY_DERIVED'
REVISED_KEYS = {'behavior', 'entry_expect', 'w3c7_expect', 'structure_expect', 'expect', 'abstain_why'}
RULING_1 = '2026-10-05 09:03:42 +0900'
BASE_COMMIT = '6bc410d'    # dev: the commit W3-c7 starts from
FROZEN = ('multi', 'te', 'quote', 'sharing', 'anaphora')
# Round 4 (auditor ruling 1, 2026-10-05 09:03:42 +0900): 41 rows of the data had expected something that the gate of section 10C K117 5 forbids (a data error, not an error of the stage).
# Their expectations were revised to the refusal of that gate; the previous full text is in artifacts/w3-c7/frozen_r1/, the new freeze is data_freeze.r4.sha256.
# The list of the 41 ids is unchanged; the revised rows now go through the general check like every other row.
DERIVED_GATE_ROWS = set("""W3C7-MULTI-002 W3C7-MULTI-004 W3C7-MULTI-006 W3C7-MULTI-007 W3C7-MULTI-008 W3C7-MULTI-009 W3C7-MULTI-011 W3C7-MULTI-012 W3C7-MULTI-013 W3C7-TE-001 W3C7-TE-008 W3C7-TE-011 W3C7-TE-016 W3C7-TE-024 W3C7-QUOTE-003 W3C7-QUOTE-004 W3C7-QUOTE-005 W3C7-QUOTE-006 W3C7-QUOTE-011 W3C7-QUOTE-012 W3C7-QUOTE-013 W3C7-SHARE-001 W3C7-SHARE-002 W3C7-SHARE-003 W3C7-SHARE-004 W3C7-SHARE-005 W3C7-SHARE-006 W3C7-SHARE-007 W3C7-SHARE-010 W3C7-SHARE-011 W3C7-SHARE-014 W3C7-SHARE-015 W3C7-SHARE-016 W3C7-SHARE-017 W3C7-SHARE-018 W3C7-SHARE-019 W3C7-SHARE-025 W3C7-ANA-003 W3C7-ANA-009 W3C7-ANA-015 W3C7-ANA-025""".split())


def _load_by_path(name, path):
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


F3 = _load_by_path('w3b3_fakes_in_w3c7', RS / 'w3b3_fakes.py')
COMMON = _load_by_path('w3b3_common_in_w3c7', RS / 'w3b3_common.py')

from tools.bank_score.v2 import b1    # noqa: E402
from verantyx import event_cross as EC    # noqa: E402
from verantyx import semantic_read as SR    # noqa: E402
from verantyx import semantic_reader as R    # noqa: E402

DOCS = (TREE / 'docs' / 'READING_SOUNDNESS.md').read_text(encoding='utf-8')


def load(name):
    return [json.loads(l) for l in (RS / ('w3c7_%s.jsonl' % name)).read_text(encoding='utf-8').splitlines() if l.strip()]


DATA = {name: load(name) for name in FROZEN}
SUP = load('sup')
ROWS = [r for name in FROZEN for r in DATA[name]] + SUP
ANSWERS = {}
for _l in (RS / 'w3c7_placement_r9.jsonl').read_text(encoding='utf-8').splitlines():
    if _l.strip():
        _r = json.loads(_l)
        ANSWERS[_r['term']] = _r['answer']


class FixtureQuery:
    """query(term) -> a recorded answer of the real r9 (a word that was not recorded is UNKNOWN and listed in `misses`); every question is in `calls`."""
    id = 'w3c7-fixture'

    def __init__(self):
        self.misses, self.calls = [], []

    def query(self, term):
        self.calls.append(term)
        if term not in ANSWERS:
            self.misses.append(term)
            return {'state': 'UNKNOWN', 'term': term}
        return copy.deepcopy(ANSWERS[term])


@pytest.fixture(autouse=True)
def _no_placement_in_the_environment(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)


def git(*args):
    return subprocess.run(['git', '-C', str(TREE)] + list(args), capture_output=True, check=True).stdout.decode('utf-8')


def _base_module():
    """The reading entry of the base commit (its own control flow: W3-b3 and no stage C7), on top of the reader of this tree."""
    src = git('show', '%s:verantyx/semantic_read.py' % BASE_COMMIT)
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_base_w3c7', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src, 'verantyx/semantic_read.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    return mod


BASE = _base_module()


def verdict(row, out):
    return b1.judge(row['expect'], row['lang'], {'readable': out['readable'], 'clauses': out['clauses'], 'relations': out['relations']})['verdict']


def expect_ok(row, ex):
    want = row['w3c7_expect']
    if want == 'READ': return ex['read'] is True
    return ex['read'] is False and (ex['reason'] or '').startswith(want)


def structure_ok(row, ex):
    want = row.get('structure_expect')
    if not want: return True
    if ex['edges'] != want['edges'] or len(ex['clause_reads']) != len(want['clauses']): return False
    for got, w in zip(ex['clause_reads'], want['clauses']):
        c = got['clause']
        if not got['readable'] or c is None: return False
        if (c['predicate'], c['roles'], c['polarity'], c['tense'], c['voice']) != (w['predicate'], w['roles'], w['polarity'], w['tense'], w['voice']): return False
    return True


# ---- the data ---------------------------------------------------------------------------------------------------------------------------
def test_the_data_has_the_registered_size_and_is_the_frozen_one():
    assert sum(len(DATA[n]) for n in FROZEN) == 130 and all(len(DATA[n]) >= 25 for n in FROZEN)
    # the first freeze (round 1), kept as a copy: the same hashes, and half read / half refused in each file
    for line in (TREE / 'artifacts' / 'w3-c7' / 'data_freeze.sha256').read_text(encoding='utf-8').splitlines():
        digest, path = line.split(None, 1)
        copy = FROZEN_R1 / Path(path.strip()).name
        assert hashlib.sha256(copy.read_bytes()).hexdigest() == digest, path
        rows = [json.loads(l) for l in copy.read_text(encoding='utf-8').splitlines() if l.strip()]
        read = sum(1 for r in rows if r['entry_expect'] == 'read')
        assert read == len(rows) - read, path
    # the current files are the refrozen ones (round 4)
    for line in (TREE / 'artifacts' / 'w3-c7' / 'data_freeze.r4.sha256').read_text(encoding='utf-8').splitlines():
        digest, path = line.split(None, 1)
        assert hashlib.sha256((TREE / path.strip()).read_bytes()).hexdigest() == digest, path


def test_the_r4_revision_changes_only_the_41_rows_and_only_their_expectation():
    changed = set()
    n_read = n_abstain = 0
    for n in FROZEN:
        old = (FROZEN_R1 / ('w3c7_%s.jsonl' % n)).read_text(encoding='utf-8').splitlines()
        new = (RS / ('w3c7_%s.jsonl' % n)).read_text(encoding='utf-8').splitlines()
        assert len(old) == len(new)
        for a, b in zip(old, new):
            ra, rb = json.loads(a), json.loads(b)
            assert ra['id'] == rb['id']
            if rb['id'] not in DERIVED_GATE_ROWS:
                assert a == b, rb['id']
                continue
            changed.add(rb['id'])
            assert tuple(ra) == tuple(rb)
            assert {k for k in ra if ra[k] != rb[k]} <= REVISED_KEYS
            assert ra['input'] == rb['input'] and ra['text'] == rb['text']
            assert rb['w3c7_expect'] == DERIVED_REASON and rb['entry_expect'] == 'abstain' and rb['behavior'] == 'abstain'
            assert rb['expect']['readable'] is False and rb['structure_expect'] is None and rb['abstain_why'] == 'derived_gate_k117_5'
            if ra['entry_expect'] == 'read': n_read += 1
            else: n_abstain += 1
    assert changed == DERIVED_GATE_ROWS
    assert (n_read, n_abstain) == (32, 9)


def test_the_prereg_is_before_the_freeze():
    pre = (TREE / 'artifacts' / 'w3-c7' / 'prereg_time.txt').read_text(encoding='utf-8').strip()
    frz = (TREE / 'artifacts' / 'w3-c7' / 'data_freeze_time.txt').read_text(encoding='utf-8').strip()
    frz4 = (TREE / 'artifacts' / 'w3-c7' / 'data_freeze_time.r4.txt').read_text(encoding='utf-8').strip()
    assert pre < frz < RULING_1 < frz4 and '<!-- w3c7-prereg:begin -->' in DOCS and '<!-- w3c7-prereg:end -->' in DOCS


@pytest.mark.parametrize('row', ROWS, ids=[r['id'] for r in ROWS])
def test_no_row_is_misread_or_incomplete_and_the_fixture_holds_every_word(row):
    q = FixtureQuery()
    out = SR.read(row['input'], placement=q)
    assert verdict(row, out) in ('correct', 'abstain'), (row['input'], verdict(row, out), out)
    q2 = FixtureQuery()
    ex = R.w3c7_explain_ja(row['input'], q2)
    assert q.misses == [] and q2.misses == []
    assert (row['entry_expect'] == 'read') == bool(out['readable']), (row['input'], out['readable'])
    assert expect_ok(row, ex), (row['input'], row['w3c7_expect'], ex['reason'])
    assert structure_ok(row, ex), (row['input'], ex['edges'], [c['clause'] for c in ex['clause_reads']])
    if row['behavior'] == 'read': assert verdict(row, out) == 'correct'


def test_every_row_the_stage_reads_is_in_the_convention_and_goes_through_the_cross_builder():
    n = 0
    for row in ROWS:
        out = SR.read(row['input'], placement=FixtureQuery())
        ex = R.w3c7_explain_ja(row['input'], FixtureQuery())
        if not ex['read']: continue
        n += 1
        assert set(out) == {'schema', 'lang', 'readable', 'clauses', 'relations', 'abstain', 'unsupported', 'clause_meta'} and out['readable'] and len(out['clause_meta']) == len(out['clauses'])
        for r in out['relations']:
            assert set(r) - {'head'} == {'type', 'from', 'to'} and r['type'] in b1.REL_TYPES and r['type'] != 'parallel'
        for c in out['clauses']:
            assert set(c) <= {'predicate', 'roles', 'polarity', 'tense', 'modality', 'voice', 'predicate_basis', 'role_basis'}
        reading = EC.build_crosses(out)
        assert reading.status == 'CROSSED', (row['input'], reading.status)
    assert n >= 40


def test_a_continuative_is_written_as_sequence_and_parallel_is_only_in_the_diagnosis():
    ex = R.w3c7_explain_ja('兄が本を読み、弟が歌を歌った。', FixtureQuery())
    out = SR.read('兄が本を読み、弟が歌を歌った。', placement=FixtureQuery())
    assert ex['read'] and ex['edges'] == [{'kind': 'parallel', 'type': 'sequence', 'from': 0, 'to': 1}]
    assert out['relations'] == [{'type': 'sequence', 'from': 0, 'to': 1}] and out['clauses'][0]['tense'] is None
    assert 'parallel' not in EC.RELATION_TYPES and 'parallel' not in b1.REL_TYPES


def test_the_quotation_goes_from_the_quoting_clause_to_the_content_and_carries_the_quotation():
    out = SR.read('兄が弟が来たと言った。', placement=FixtureQuery())
    assert out['relations'] == [{'type': 'quote', 'from': 1, 'to': 0}]
    assert out['clauses'][0]['predicate'] == '来る' and out['clauses'][1]['predicate'] == '言う'
    assert out['clauses'][1]['roles'] == {'agent': '兄', 'quotation': '弟が来た'}
    assert out['clauses'][1]['role_basis']['quotation'] == 'w3c7_quote'


def test_the_four_clause_limit_and_the_nonfinite_cuts_are_refused_with_their_reason():
    ex = R.w3c7_explain_ja('兄が帰ったので、弟が来たが、母が座ったけれど、姉が立ったから、妹が寝た。', FixtureQuery())
    assert ex['reason'] == 'CLAUSES_OVER_LIMIT:5' and R.W3C7_MAX_CLAUSES == 4
    ex = R.w3c7_explain_ja('兄が帰れば、弟が来たので、母が座った。', FixtureQuery())
    assert ex['reason'] == 'CUT_KIND_NOT_READ:ば'


# ---- the entry: what stage C7 may and may not change ---------------------------------------------------------------------------------
def test_a_refusal_the_stage_gives_back_is_the_same_object(monkeypatch):
    seen = []
    real = R.w3c7_read_ja

    def spy(text_, placement, out, report):
        res = real(text_, placement, out, report); seen.append((out, res)); return res
    monkeypatch.setattr(R, 'w3c7_read_ja', spy)
    for text in ('兄が帰ったので、弟は来たが、母が座った。', '兄は本を読んで、歌を歌った。', '兄が本を読んだと言った。', '彼が本を読んで、弟が歌を歌った。'):
        SR.read(text, placement=FixtureQuery())
    assert len(seen) >= 4 and all(o is r for o, r in seen)


def test_the_stage_is_not_called_when_there_is_no_placement_or_w3b3_reads_or_the_input_is_english(monkeypatch):
    called = []
    real = R.w3c7_read_ja
    monkeypatch.setattr(R, 'w3c7_read_ja', lambda *a: called.append(a[0]) or real(*a))
    for row in ROWS:
        assert SR.read(row['input'], placement=None) == BASE.read(row['input'], placement=None)
    assert called == []
    for text in ('兄が本を読んだので、弟が歌を歌った。', '母が弟に話した人を兄が呼んだ。'):      # W3-b3 reads these
        out = SR.read(text, placement=F3.FixtureQuery())
        assert out['readable'] and out == BASE.read(text, placement=F3.FixtureQuery())
    assert called == []
    for text in ('John read a book and Mary sang.', 'He said that she came.'):
        assert SR.read(text, placement=FixtureQuery()) == BASE.read(text, placement=FixtureQuery()) and called == []


def test_a_sentence_that_the_stage_stops_before_any_question_asks_the_placement_what_the_base_asks():
    n = 0
    for row in ROWS:
        ex = R.w3c7_explain_ja(row['input'], FixtureQuery())
        if ex['read'] or ex['clause_reads']: continue
        q1, q2 = FixtureQuery(), FixtureQuery()
        a, b = SR.read(row['input'], placement=q1), BASE.read(row['input'], placement=q2)
        assert a == b and q1.calls == q2.calls, row['input']
        n += 1
    assert n >= 40


ATTACHMENT_SENTENCES = ('兄が帰ったので、母が弟に話した人を姉が呼んだ。', '兄が来たが、母が弟に話した人を姉が呼んだ。', '兄が帰ったので、母が弟に話した人を姉が呼んだが、妹が絵を描いた。')


def test_a_finite_cut_followed_by_a_relative_cut_is_refused_before_any_question_and_the_reverse_order_is_still_read():
    # H309 (round 2, review M1): the attachment of the finite clause (the relative clause or its head clause) is split
    for text in ATTACHMENT_SENTENCES:
        ex = R.w3c7_explain_ja(text, FixtureQuery())
        assert ex['read'] is False and ex['reason'] == 'RELATIVE_NESTED_NOT_READ:attachment' and ex['clause_reads'] == [], text
        q1, q2 = FixtureQuery(), FixtureQuery()
        a, b = SR.read(text, placement=q1), BASE.read(text, placement=q2)
        assert a == b and q1.calls == q2.calls, text
    for row in SUP:
        if row['input'] in ATTACHMENT_SENTENCES:
            assert row['behavior'] == 'abstain' and row['w3c7_expect'] == 'RELATIVE_NESTED_NOT_READ', row['id']
    ex = R.w3c7_explain_ja('母が弟に話した人を兄が呼んだので、姉が絵を描いた。', FixtureQuery())
    assert ex['read'] is True and ex['reason'] is None


def test_every_sentence_the_stage_reads_was_refused_by_the_base_and_nothing_the_base_read_changes():
    n = 0
    for row in ROWS:
        a, b = SR.read(row['input'], placement=FixtureQuery()), BASE.read(row['input'], placement=FixtureQuery())
        if a == b: continue
        assert not b['readable'] and a['readable'], row['input']
        assert R.w3c7_explain_ja(row['input'], FixtureQuery())['read'] is True
        n += 1
    assert n >= 40


def test_the_te_and_continuative_rows_of_w3b3_are_now_read_and_judged_correct():
    rows = [r for r in COMMON.load_data('parallel') if r['behavior'] == 'read']
    assert len(rows) == 15
    for r in rows:
        out = SR.read(r['input'], placement=F3.FixtureQuery())
        assert out['readable'] and verdict(r, out) == 'correct', r['input']
        assert R.w3c7_explain_ja(r['input'], F3.FixtureQuery())['read']


# ---- anaphora and W1-a4 ----------------------------------------------------------------------------------------------------------------
def test_anaphora_every_refusal_row_has_the_reason_before_any_question():
    rows = [r for r in DATA['anaphora'] if r['w3c7_expect'] == 'ANAPHORA_NOT_READ']
    assert len(rows) == 13
    for r in rows:
        ex = R.w3c7_explain_ja(r['input'], FixtureQuery())
        assert (ex['reason'] or '').startswith('ANAPHORA_NOT_READ:') and not SR.read(r['input'], placement=FixtureQuery())['readable']
        assert ex['clause_reads'] == []
    assert R.w3c7_explain_ja('兄が大きな本を読んだので、弟が帰ったが、母が座った。', FixtureQuery())['reason'] == 'ANAPHORA_NOT_READ:大きな'


def test_w1a4_the_misread_shapes_are_not_read_by_the_stage_and_the_output_is_what_it_was_without_it(monkeypatch):
    rows = COMMON.load_data('w1a4')
    assert len(rows) == 53
    outs = {r['input']: SR.read(r['input'], placement=F3.FixtureQuery()) for r in rows}
    for r in rows:
        assert R.w3c7_explain_ja(r['input'], F3.FixtureQuery())['read'] is False, r['input']
    monkeypatch.setattr(R, 'w3c7_read_ja', lambda text, placement, out, report: out)
    for r in rows:
        assert SR.read(r['input'], placement=F3.FixtureQuery()) == outs[r['input']], r['input']


# ---- the tables and the code --------------------------------------------------------------------------------------------------------------
def _table(name):
    m = re.search(r'<!-- BEGIN table:%s -->\n(.*?)<!-- END table:%s -->' % (name, name), DOCS, re.S)
    assert m, name
    rows = [l for l in m.group(1).splitlines() if l.startswith('| `')]
    return [re.match(r'\| `([^`]+)`', l).group(1) for l in rows], rows


def test_the_closed_tables_of_the_docs_are_the_constants_of_the_code():
    names, rows = _table('w3c7_edges')
    assert names == [e[0] for e in R.W3C7_EDGES]
    for e, row in zip(R.W3C7_EDGES, rows):
        cells = [c.strip() for c in row.strip().strip('|').split('|')]
        assert cells[5] == e[2], (e, cells)
    names, _ = _table('w3c7_reasons')
    assert tuple(names) == R.W3C7_REASON_NAMES


def _section():
    """Integration (auditor ruling 2026-10-06, W16-t1b K800): the section ends before the next ticket's mark `# W16-t1b:` (the modality gate appended at the end of the reader, attested by
    tests/test_w16t1b_*.py); old expectation: the section runs from `# W3-c7:` to the end of the file."""
    src = (TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')
    i = src.index('# W3-c7:')
    j = src.index('# W16-t1b:') if '# W16-t1b:' in src else len(src)
    return src[i:j]


def test_every_reason_the_stage_writes_is_in_the_closed_list():
    section = _section()
    used = set(re.findall(r"'([A-Z][A-Z_]{5,})[:']", section))
    allowed = set(R.W3C7_REASON_NAMES) | {'TE_UNDETERMINED', 'PARALLEL_UNDETERMINED'}
    assert {u for u in used if u not in allowed and not u.startswith(('W3B3_', 'W3C7_'))} == set(), used - allowed
    for text in ('兄が帰ったので、弟が来たが、母が座った。', '彼が本を読んで、弟が歌を歌った。', '兄が本を読んだと言った。', '兄が本を読んで、弟は歌を歌った。'):
        reason = R.w3c7_explain_ja(text, FixtureQuery())['reason']
        assert reason is None or reason.split(':')[0] in R.W3C7_REASON_NAMES, reason


def _grammar():
    src = (TREE / 'tests' / 'test_semantic_read_w1a5.py').read_text(encoding='utf-8')
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'GRAMMAR' for t in n.targets))
    return set(ast.literal_eval(node.value))


def test_the_section_holds_only_the_words_of_the_closed_grammar_and_assigns_no_name_of_w3b3_or_of_the_entry():
    section = _section()
    grammar = _grammar()
    tree = ast.parse(section)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            for token in set(re.findall(r'[^\x00-\x7f]+', node.value)):
                assert token in grammar, token
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                assert not (isinstance(t, ast.Name) and (t.id.startswith(('W3B3', 'w3b3', '_w3b3', '_W3B3')) or t.id in ('typed_plan_u_ja', '_CachedQuery', '_answer'))), t.id


def _defs(src):
    out = {}
    for n in ast.parse(src).body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name.lower().lstrip('_').startswith('w3b3'): out[n.name] = ast.dump(n)
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id.lower().lstrip('_').startswith('w3b3'): out[t.id] = ast.dump(n)
    return out


def test_the_tables_and_functions_of_w3b3_are_the_base_ones_and_the_base_lines_are_only_added_to():
    base = git('show', '%s:verantyx/semantic_reader.py' % BASE_COMMIT)
    now = (TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')
    a, b = _defs(base), _defs(now)
    assert a and set(a) <= set(b) and all(a[k] == b[k] for k in a)
    assert now.startswith(base)
    sr_base = git('show', '%s:verantyx/semantic_read.py' % BASE_COMMIT)
    sr_now = (TREE / 'verantyx' / 'semantic_read.py').read_text(encoding='utf-8')
    removed = [l for l in sr_base.splitlines() if l not in sr_now.splitlines()]
    assert removed == ["            return out if out['readable'] else _w3b3_read_ja(text, R, placement, out, unsupported_report)"]


def _snap(text):
    return SR._w3b3_snapshot(text, R)


def test_the_generalised_alternative_count_is_the_decision_of_w3b3_unique_on_two_clauses():
    texts = [r['input'] for r in ROWS] + [r['input'] for name in COMMON.DATA_ALL for r in COMMON.load_data(name)]
    n = 0
    for text in texts:
        snap = _snap(text)
        cut, why = R.w3b3_scope(snap)
        if cut is None or cut['kind'] == 'relative': continue
        a_phr, b_phr = R.w3b3_sides(snap, cut)
        if any(R._w3b3_topic(p) for p in b_phr) or any(R._w3b3_topic(p) for p in a_phr[1:]):
            mine = 'topic'
        else:
            topic_first = bool(a_phr) and R._w3b3_topic(a_phr[0])
            mine = R._w3c7_alternatives([a_phr, b_phr], topic_first)
        theirs = R.w3b3_unique(snap, cut)
        assert (mine is None) == (theirs is None), (text, mine, theirs)
        n += 1
    assert n >= 100


def test_a_scrambled_phrase_that_may_belong_to_a_later_clause_is_refused_and_a_fixed_order_is_read():
    assert R.w3c7_explain_ja('本を兄が読んだので、弟が帰ったが、母が座った。', FixtureQuery())['reason'] == 'CLAUSE_SCOPE_AMBIGUOUS:alternative_cut'
    assert R.w3c7_explain_ja('兄が本を読んだので、弟が帰ったが、母が座った。', FixtureQuery())['read'] is True
