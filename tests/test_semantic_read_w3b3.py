"""W3-b3: a sentence of two predicates read as two crosses and an edge (a relative clause: the head is a filler of an arm of the main clause and the arm it fills in the relative
clause is decided by TYPE; a connective: a closed list of cuts and a typed relation). The tables and rules were registered in docs/READING_SOUNDNESS.md section 10C (K114-K122)
before the data (w3b3_*.jsonl) and this file were written.

Placement answers here come from fakes (tests/reading_soundness/w3b3_fakes.py: the fixture of the placement r6, and hand-made answers); no real placement is opened.
Run under a clean environment (env -i): a VERA_PLACEMENT left in the shell would change the default path of the entry.
"""
import ast
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

TREE = Path(__file__).resolve().parent.parent
RS = TREE / 'tests' / 'reading_soundness'
BASE_COMMIT = 'c875ed3'    # dev: the commit W3-b3 starts from


def _load_by_path(name, path):
    """Load a helper module by its path under a unique name (sys.path is NOT changed: see the note of tests/test_semantic_read_w3b1.py)."""
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


F = _load_by_path('w3b3_fakes_in_test', RS / 'w3b3_fakes.py')
COMMON = _load_by_path('w3b3_common_in_test', RS / 'w3b3_common.py')

from tools.bank_score.v2 import b1    # noqa: E402
from verantyx import semantic_read as SR    # noqa: E402
from verantyx import semantic_reader as R    # noqa: E402

DOCS = (TREE / 'docs' / 'READING_SOUNDNESS.md').read_text(encoding='utf-8')
ROWS = {name: COMMON.load_data(name) for name in COMMON.DATA_ALL}
ALL = [r for name in COMMON.DATA_ALL for r in ROWS[name]]
TEST_INPUTS = [l.strip() for l in (RS / 'w3b3_test_inputs.txt').read_text(encoding='utf-8').splitlines() if l.strip() and not l.startswith('#')]
JA = re.compile('[぀-ヿ㐀-䶿一-鿿]')
JA_TEST_INPUTS = [t for t in TEST_INPUTS if JA.search(t)]
EN_TEST_INPUTS = [t for t in TEST_INPUTS if not JA.search(t)]
NOT_CUTS = ['弟と兄が来た。', '駅から兄が来た。', '東京なら兄が来る。', '兄が本を読んでいる。', '兄が来てもいい。', 'だから兄が来た。']
NOT_LISTED = {'兄が来てから弟が帰った。': 'てから', '兄が来たのに、弟が帰った。': 'のに', '兄が来るために、弟が帰った。': 'ため', '兄が来るように、弟が帰った。': 'よう', '兄が来た後に弟が帰った。': '後'}


@pytest.fixture(autouse=True)
def _no_placement_in_the_environment(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_COARSE_PLACEMENT', raising=False)


def git(*args):
    return subprocess.run(['git', '-C', str(TREE)] + list(args), capture_output=True, check=True).stdout.decode('utf-8')


def _base_module():
    """The reading entry of the base commit (its own control flow), on top of the reader of this tree (the base functions that it calls are unchanged)."""
    src = git('show', '%s:verantyx/semantic_read.py' % BASE_COMMIT)
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_base_w3b3', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src, 'verantyx/semantic_read.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    return mod


BASE = _base_module()


def block(name):
    m = re.search(r'<!-- BEGIN table:%s -->\n(.*?)<!-- END table:%s -->' % (name, name), DOCS, re.S)
    assert m, name
    return [line for line in m.group(1).splitlines() if line.startswith('|') and not set(line) <= set('|- ')][1:]


def first_cells(name):
    return [re.split(r' \| ', line.strip()[1:-1].strip())[0].strip().strip('`') for line in block(name)]


def snap_of(text):
    return SR._w3b3_snapshot(text, R)


def new(text, query=None):
    q = query or F.FixtureQuery()
    return SR.read(text, placement=q), q


def base(text, query=None):
    q = query or F.FixtureQuery()
    return BASE.read(text, placement=q), q


def explain(text, query=None):
    return SR.clause_scope_explain_ja(text, query or F.FixtureQuery())


def verdict(row, out):
    return b1.judge(row['expect'], row['lang'], {'readable': out['readable'], 'clauses': out['clauses'], 'relations': out['relations']})['verdict']


def row_of(text):
    return next(r for r in ALL if r['input'] == text)


def validate_out(out):
    """The convention's shape of an output of the new path: a relation may hold `head` (checked apart); the other keys are the closed ones of section 1.2."""
    bad = []
    if set(out) != {'schema', 'lang', 'readable', 'clauses', 'relations', 'abstain', 'unsupported', 'clause_meta'}: bad.append('keys')
    if not out['readable']: return bad
    n = len(out['clauses'])
    if len(out['clause_meta']) != n: bad.append('meta length')
    for r in out['relations']:
        rr = {k: v for k, v in r.items() if k != 'head'}
        if set(rr) != {'type', 'from', 'to'} or rr['type'] not in b1.REL_TYPES or not all(isinstance(rr[k], int) and 0 <= rr[k] < n for k in ('from', 'to')): bad.append(('relation', r))
        if 'head' in r:
            if rr['type'] != 'relative' or set(r['head']) != {'from_role', 'to_role'}: bad.append(('head', r))
    for c in out['clauses']:
        if set(c) - {'predicate', 'roles', 'polarity', 'tense', 'modality', 'voice', 'predicate_basis', 'role_basis'}: bad.append(('clause keys', sorted(c)))
        if c['tense'] not in ('past', 'nonpast', None) or c['polarity'] not in ('+', '-') or c['voice'] != 'active': bad.append(('clause', c))
    return bad


# ---- 1. the tables of the docs are the constants of the reader -------------------------------------------------------------------------
def test_the_cut_table_of_the_docs_is_the_constant_of_the_reader():
    rows = block('w3b3_cuts')
    assert [r[0] for r in R.W3B3_CUTS] == first_cells('w3b3_cuts')
    for const, line in zip(R.W3B3_CUTS, rows):
        cells = [c.strip().strip('`') for c in line.strip()[1:-1].split('|')]
        kind, connectives, clause_kind, relation, tense_kept = const
        assert ('定形' if clause_kind == 'finite' else '非定形') == cells[2], (const, cells)
        assert (('`null`' if not tense_kept else '入口の値')) in line, (const, line)
        if relation in ('TE_UNDETERMINED', 'PARALLEL_UNDETERMINED'): assert relation in line, (const, line)
        elif kind != 'と': assert '`%s`' % relation in line.split('|')[4], (const, line)
    assert len(R.W3B3_CUTS) == 13


def test_the_relation_table_of_the_docs_is_the_constant_of_the_reader():
    lines = block('w3b3_relations')
    text = '\n'.join(lines)
    for kind, connectives, clause_kind, relation, tense_kept in R.W3B3_CUTS:
        mine = [l for l in lines if '`%s`' % kind in l.split('|')[1]]
        assert mine, kind
        assert any(('`%s`' % relation) in l or relation in l for l in mine), (kind, relation)
    assert 'TE_UNDETERMINED' in text and 'PARALLEL_UNDETERMINED' in text and 'condition_past_main' in text and 'quote_possible' in text
    for verb in R.W3B3_QUOTE_VERBS: assert verb in text, verb
    assert len(R.W3B3_QUOTE_VERBS) == 8 and R.W3B3_PERMISSION_WORDS == ('いい', 'よい', 'かまう')


def test_the_reasons_and_the_produced_table_of_the_docs_are_the_constants_of_the_reader():
    assert list(R.W3B3_REASON_NAMES) == first_cells('w3b3_reasons')
    assert list(R.W3B3_PRODUCED_WITH_PLACEMENT) == first_cells('w3b3_produced')
    assert 'role:beneficiary' in SR.NOT_PRODUCED and 'relation:relative' not in SR.NOT_PRODUCED and 'W3B3' not in json.dumps(SR.NOT_PRODUCED, ensure_ascii=False)


# ---- 2. the cuts (by part of speech and form, not by surface) -----------------------------------------------------------------------------
FORMS = [r for r in ALL if r['cut'] not in ('w1a4',) and not r['w3b3_expect'].startswith(('CLAUSE_SCOPE_NOT_LISTED', 'W3B3_NOT_TRIGGERED'))]


@pytest.mark.parametrize('row', FORMS, ids=[r['id'] for r in FORMS])
def test_every_row_has_exactly_the_cut_of_its_form(row):
    kinds = [c['kind'] for c in R.w3b3_cuts(snap_of(row['input']))]
    assert kinds == [row['cut']], (row['input'], kinds)


@pytest.mark.parametrize('text', NOT_CUTS)
def test_a_case_particle_a_noun_plus_nara_dakara_teiru_and_temo_ii_are_not_cuts(text):
    assert R.w3b3_cuts(snap_of(text)) == [], text
    cut, why = R.w3b3_scope(snap_of(text))
    assert cut is None and why.startswith(('W3B3_NOT_TRIGGERED:groups=1', 'CLAUSE_SCOPE_AMBIGUOUS:cuts=0')), (text, why)    # (東京なら: なら is a copula, a second group)


@pytest.mark.parametrize('text', sorted(NOT_LISTED))
def test_a_form_outside_the_list_is_not_a_cut_and_is_named(text):
    snap = snap_of(text)
    assert 'relative' not in [c['kind'] for c in R.w3b3_cuts(snap)], text
    cut, why = R.w3b3_scope(snap)
    assert cut is None and why.startswith('CLAUSE_SCOPE_NOT_LISTED:'), (text, why)


def test_a_sentence_with_two_cuts_or_three_predicates_is_not_triggered():
    cut, why = R.w3b3_scope(snap_of('兄が来て、弟が帰って、母が座った。'))
    assert cut is None and why == 'W3B3_NOT_TRIGGERED:groups=3'
    cut, why = R.w3b3_scope(snap_of('兄が来たので、弟が帰ったが、母が座った。'))
    assert cut is None and why == 'W3B3_NOT_TRIGGERED:groups=3'


def test_the_predicate_group_is_a_compound_verb_and_teiru_is_not_a_second_one():
    assert len(R.w3b3_groups(snap_of('兄が本を読んでいる。'))) == 1
    assert len(R.w3b3_groups(snap_of('兄が走り回った。'))) == 1
    assert len(R.w3b3_groups(snap_of('兄が来たので、弟が帰った。'))) == 2


def test_the_snapshot_is_not_the_nodes_of_the_tagger():
    """The features are copied at once: a later parse does not change what the pure functions read (K113 of W3-b2, trap 4)."""
    text = '兄が本を読んだので、弟が歌を歌った。'
    snap = snap_of(text)
    before = (R.w3b3_cuts(snap), R.w3b3_groups(snap), R.w3b3_scope(snap))
    R._tokens('母が絵を描いて、姉が手紙を書いた。'); R.document_view({'d': '先生が来たら、生徒が帰る。'})
    assert (R.w3b3_cuts(snap), R.w3b3_groups(snap), R.w3b3_scope(snap)) == before
    assert all(isinstance(t.surface, str) and isinstance(t.start, int) for t in snap)


# ---- 3. the cut is unique, or the sentence is not read (no question to the placement before) ---------------------------------------------------
def test_the_three_sentences_of_k116_and_a_topic_in_the_relative_clause():
    for text, want in (('兄が買った本を弟が読んだ。', None), ('兄が駅で買った本を読んだ。', 'CLAUSE_SCOPE_AMBIGUOUS:alternative_cut=1'),
                       ('駅で兄が本を買ったので、弟が喜んだ。', 'CLAUSE_SCOPE_AMBIGUOUS:alternative_cut=1'), ('兄は母が作った料理を食べた。', 'CLAUSE_SCOPE_AMBIGUOUS:topic_in_relative')):
        snap = snap_of(text)
        cut, why = R.w3b3_scope(snap)
        assert cut is not None and why is None, (text, why)
        assert R.w3b3_unique(snap, cut) == want, text


def test_only_ga_and_wo_repeated_break_a_cut_other_particles_do_not():
    snap = snap_of('三時に駅に兄が来たので、弟が帰った。')    # に twice does not break: moving 三時に to the main side is possible
    cut, _ = R.w3b3_scope(snap)
    assert R.w3b3_unique(snap, cut) == 'CLAUSE_SCOPE_AMBIGUOUS:alternative_cut=1'
    snap = snap_of('兄が来たので、弟が帰った。')
    cut, _ = R.w3b3_scope(snap)
    assert R.w3b3_unique(snap, cut) is None


def test_a_topic_after_the_first_phrase_of_a_connective_sentence_is_not_decided():
    for text in ('兄が来たから、弟は帰った。', '兄が来たので、母は弟が帰った。'):
        snap = snap_of(text)
        cut, _ = R.w3b3_scope(snap)
        assert R.w3b3_unique(snap, cut) == 'CLAUSE_SCOPE_AMBIGUOUS:topic_position', text
    snap = snap_of('兄は本を読んだので、歌を歌った。')    # the topic first is the one form that is kept
    cut, _ = R.w3b3_scope(snap)
    assert R.w3b3_unique(snap, cut) is None


@pytest.mark.parametrize('row', [r for r in ALL if r['cut'] != 'w1a4' and r['w3b3_expect'].startswith('CLAUSE_SCOPE_AMBIGUOUS')], ids=lambda r: r['id'])
def test_the_ambiguous_rows_stop_before_any_question(row):
    q = F.FixtureQuery()
    out = SR.read(row['input'], placement=q)
    bq = F.FixtureQuery()
    bout = BASE.read(row['input'], placement=bq)
    assert out == bout and q.calls == bq.calls, row['input']
    ex = explain(row['input'])
    assert ex['read'] is False and ex['reason'].startswith('CLAUSE_SCOPE_AMBIGUOUS'), (row['input'], ex['reason'])


# ---- 4. the gates of the whole sentence (by structure) ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize('row', [r for r in ALL if r['w3b3_expect'].startswith('CLAUSE_FORM_NOT_READ:') and r['w3b3_expect'].split(':')[1] in ('imperative', 'question', 'connective_outside_cut')],
                         ids=lambda r: r['id'])
def test_a_form_gate_stops_the_sentence_before_any_question(row):
    q = F.FixtureQuery(); bq = F.FixtureQuery()
    assert SR.read(row['input'], placement=q) == BASE.read(row['input'], placement=bq) and q.calls == bq.calls
    ex = explain(row['input'])
    assert ex['reason'] == row['w3b3_expect'], (row['input'], ex['reason'])


def test_the_form_gate_looks_at_the_whole_sentence_not_at_one_clause():
    """An imperative, a quotation mark or a question mark in the FIRST clause stops the sentence too (the gate does not look at a position)."""
    for text, why in (('母が料理を作れ、弟が歌を歌った。', 'imperative'), ('兄が「来た」ので、弟が帰った。', 'quote'), ('兄が来ましたか、弟が帰った。', 'question')):
        snap = snap_of(text)
        assert R.w3b3_form_gate(snap, None) == 'CLAUSE_FORM_NOT_READ:' + why, text


def test_teiru_and_an_aspect_te_are_not_a_connective_outside_the_cut():
    snap = snap_of('兄が本を読んでいるので、弟が歌を歌った。')
    cut, why = R.w3b3_scope(snap)
    assert why is None and R.w3b3_form_gate(snap, cut) is None
    snap = snap_of('兄が来たので、弟が帰って、母が座った。')
    assert R.w3b3_scope(snap)[0] is None


# ---- 5. the text of a clause, the check of its tokens, the existing gates ---------------------------------------------------------------------------
def test_the_clause_texts_of_a_finite_cut_and_of_a_non_finite_cut():
    for text, a, b in (('兄が本を読んだので、弟が歌を歌った。', '兄が本を読んだ。', '弟が歌を歌った。'), ('兄が来れば、弟が帰る。', '兄が来る。', '弟が帰る。'),
                       ('兄が着いたら、弟が帰る。', '兄が着く。', '弟が帰る。'), ('兄が本を読みながら、弟が歌を歌った。', '兄が本を読む。', '弟が歌を歌った。'),
                       ('兄が本を読んで、弟が歌を歌った。', '兄が本を読む。', '弟が歌を歌った。'), ('兄が来ても、弟が帰る。', '兄が来る。', '弟が帰る。'),
                       ('兄が来るなら、弟が帰る。', '兄が来る。', '弟が帰る。'), ('兄が来ると、弟が帰る。', '兄が来る。', '弟が帰る。'),
                       ('兄が来たけれども、弟が帰った。', '兄が来た。', '弟が帰った。'), ('兄が買った本を弟が読んだ。', '兄が買った。', '本を弟が読んだ。')):
        snap = snap_of(text)
        cut, why = R.w3b3_scope(snap)
        assert why is None, (text, why)
        texts, why = R.w3b3_texts(snap, text, cut)
        assert why is None and (texts['a'], texts['b']) == (a, b), (text, texts, why)


def test_a_non_finite_clause_is_written_with_the_dictionary_form_as_written_not_the_lemma():
    """閉め has the lemma 締める and 帰ら 返る: the written base form is used (K117 2)."""
    for text, a in (('兄が戸を閉めれば、弟が来る。', '兄が戸を閉める。'), ('兄が家に帰れば、弟が来る。', '兄が家に帰る。')):
        snap = snap_of(text)
        cut, why = R.w3b3_scope(snap)
        texts, why = R.w3b3_texts(snap, text, cut)
        assert texts['a'] == a, (text, texts)


def test_an_auxiliary_between_the_verb_and_a_non_finite_cut_is_not_read():
    for text in ('兄が来なければ、弟が帰る。', '兄が褒められても、弟が帰る。', '兄が読みたくて、弟が歌った。'):
        snap = snap_of(text)
        cut, why = R.w3b3_scope(snap)
        assert why is None and cut['aux_before'] is True, (text, why, cut)
        texts, why = R.w3b3_texts(snap, text, cut)
        assert texts is None and why == 'CLAUSE_FORM_NOT_READ:aux_in_nonfinite', (text, why)
        q = F.FixtureQuery(); bq = F.FixtureQuery()
        assert SR.read(text, placement=q) == BASE.read(text, placement=bq) and q.calls == bq.calls


def test_the_token_check_compares_the_clause_with_the_sentence_and_names_the_position():
    text = '兄が本を読んだので、弟が歌を歌った。'
    snap = snap_of(text); cut, _ = R.w3b3_scope(snap)
    texts, _ = R.w3b3_texts(snap, text, cut)
    assert R.w3b3_tokens_match(snap, snap_of(texts['a']), cut, 'a') is None
    assert R.w3b3_tokens_match(snap, snap_of(texts['b']), cut, 'b') is None
    other = snap_of('兄が絵を読んだ。')                                   # a token of another word
    why = R.w3b3_tokens_match(snap, other, cut, 'a')
    assert why is not None and why.startswith('CLAUSE_TOKENS_DIFFER:'), why
    shorter = snap_of('兄が読んだ。')
    assert R.w3b3_tokens_match(snap, shorter, cut, 'a').startswith('CLAUSE_TOKENS_DIFFER:')


MISREADS = ['兄が本を読んでいないので、弟が歌を歌った。', '兄が来たので、弟が本を読んでいない。', '兄が手紙を書けたので、弟が歌を歌った。', '兄が来たので、弟が話せた。',
            '兄が来たので、弟が窓を開けるな。', '兄が来たから、弟が窓を開けて。']


@pytest.mark.parametrize('text', MISREADS)
def test_the_misreads_of_the_base_entry_do_not_enter_through_a_clause(text):
    """K117 5: a clause that the base entry misreads alone (imperative, prohibition, request, ている+ない, a potential form) is not read as a clause (positive control: the same structure reads)."""
    out, q = new(text)
    assert out['readable'] is False and out == base(text)[0], (text, out)
    ex = explain(text)
    assert ex['read'] is False and ex['reason'].split(':')[0] in ('CLAUSE_FORM_NOT_READ', 'CLAUSE_UNREAD', 'CLAUSE_SCOPE_AMBIGUOUS'), (text, ex['reason'])


def test_the_base_misreads_alone_are_still_the_base_output_and_the_clause_gates_see_them():
    """The five single-sentence misreads of the base (probe_w1a4_en.txt) are not this path's: unchanged. A clause that the base entry misreads alone has a reason in one of the two
    existing gates (the ending, the derived verb)."""
    from types import SimpleNamespace as NS
    for text in ('母が料理を作れ。', '料理を作れ。', '窓を開けるな。', '窓を開けて。', 'だから兄が歩いた。'):
        assert SR.read(text, placement=F.FixtureQuery()) == BASE.read(text, placement=F.FixtureQuery()), text
    for clause in ('兄が本を読んでいない。', '兄が手紙を書けた。', '兄が窓を開けた。'):
        out = SR.read(clause, placement=None)
        assert out['readable'] is True, clause
        sp = out['clause_meta'][0]['span']
        c = NS(predicate_span=NS(start=sp[0], end=sp[1]))
        toks = R._tokens(clause)
        assert R.typed_tail_ja(toks, c) or R.typed_head_derived_ja(toks, c), clause


@pytest.mark.parametrize('text', ['兄が本を読んだので、弟が歌を歌った。', '兄が来たから、弟が帰った。', '兄が弟を呼んだけれど、弟が来た。'])
def test_a_clause_that_the_entry_reads_is_read_and_no_gate_stops_it(text):
    ex = explain(text)
    assert ex['read'] is True and ex['reason'] is None and ex['triggered'] is True, ex
    assert [c['readable'] for c in ex['clause_reads']] == [True, True]
    assert len(ex['clause_texts']) == 2


# ---- 6. the relative clause: the arm of the head, by type ----------------------------------------------------------------------------------------------
HEAD_READS = ['母が弟に話した人を兄が呼んだ。', '姉が妹に頼んだ友達を先生が呼んだ。', '兄が先生に言った生徒を母が待った。', '母が姉に話した本を弟が読んだ。', '歌を弟に頼んだ人を兄が呼んだ。', '本を妹に話した先生を母が待った。']


@pytest.mark.parametrize('text', HEAD_READS)
def test_a_relative_clause_is_read_when_exactly_one_arm_is_empty_and_the_type_fits(text):
    out, q = new(text)
    assert out['readable'] is True, (text, explain(text))
    assert validate_out(out) == [] and verdict(row_of(text), out) == 'correct', out
    rel = out['relations'][0]
    assert rel['type'] == 'relative' and (rel['from'], rel['to']) == (0, 1) and set(rel['head']) == {'from_role', 'to_role'}
    c0, c1 = out['clauses']
    assert c0['roles'][rel['head']['from_role']] == c1['roles'][rel['head']['to_role']]
    assert c0['predicate_basis'].startswith('placement_direct:P_') and c0['role_basis'][rel['head']['from_role']].startswith('placement_')
    assert out['unsupported'] == SR.read(text, placement=None)['unsupported']          # the full sentence's report, as the typed paths of W3-b1 / W3-b2 carry it
    ex = explain(text)
    assert ex['read'] is True and ex['head']['arm'] == rel['head']['from_role'] and ex['head']['empty_arms'] == [rel['head']['from_role']]


def test_the_arm_is_decided_by_the_type_not_by_the_particle_or_the_word():
    out, _ = new('母が弟に話した人を兄が呼んだ。')
    assert out['relations'][0]['head'] == {'from_role': 'patient', 'to_role': 'patient'}
    out, _ = new('歌を弟に頼んだ人を兄が呼んだ。')
    assert out['relations'][0]['head'] == {'from_role': 'agent', 'to_role': 'patient'}
    assert out['clauses'][0]['roles'] == {'agent': '人', 'patient': '歌', 'recipient': '弟'}


def test_a_split_answer_whose_every_candidate_fits_is_read_with_its_basis():
    out, _ = new('母が弟に話した客を兄が呼んだ。')
    assert out['readable'] is True
    assert out['clauses'][0]['role_basis']['patient'] == 'placement_all_candidates:NATURAL_PHENOMENON+PERSON'
    assert verdict(row_of('母が弟に話した客を兄が呼んだ。'), out) == 'correct'


@pytest.mark.parametrize('text,reason', [
    ('母が話した人を兄が呼んだ。', 'HEAD_ROLE_UNDETERMINED:empty_arms=2'),
    ('母が人を弟に話した部屋を兄が見た。', 'HEAD_ROLE_UNDETERMINED:empty_arms=0'),
    ('母が薬を頼んだ人を兄が呼んだ。', 'HEAD_ROLE_UNDETERMINED:undecided_arm'),
    ('兄が東京から歩いた町を弟が見た。', 'HEAD_ROLE_UNDETERMINED:adjunct_tie'),
    ('母が弟に話した問題を兄が見た。', 'HEAD_ROLE_UNDETERMINED:outer_relation_type'),
    ('父が兄に話した手紙を母が読んだ。', 'HEAD_ROLE_UNDETERMINED:outer_relation_type'),
    ('兄が書いた手紙を母が読んだ。', 'HEAD_ROLE_UNDETERMINED:frame_not_read'),
    ('母が弟に話した部屋を兄が見た。', 'HEAD_ROLE_UNDETERMINED:type'),
    ('兄が弟に頼んだ荷物を母が持った。', 'HEAD_ROLE_UNDETERMINED:type'),
    ('先生が生徒に教えた歌を弟が歌った。', 'CLAUSE_FORM_NOT_READ:PLACEMENT_PREDICATE_POSSIBLY_DERIVED'),
])
def test_each_head_rule_refuses_with_its_reason_and_the_output_is_the_bases(text, reason):
    ex = explain(text)
    assert ex['read'] is False and ex['reason'].startswith(reason), (text, ex['reason'])
    assert SR.read(text, placement=F.FixtureQuery()) == BASE.read(text, placement=F.FixtureQuery())


def test_the_head_noun_phrase_is_a_simple_noun_phrase_and_not_one_that_the_entry_may_read_otherwise():
    """K118 1, on the pure function: a の or a numeral in the phrase, or a head of a class that does not decide its type, is not a head (the entry may not read the main clause at all,
    so the order of the gates would give another reason first)."""
    for text, why in (('母が弟に話した兄の友達を先生が呼んだ。', 'HEAD_ROLE_UNDETERMINED:head_not_simple'), ('母が弟に話した三人の客を兄が呼んだ。', 'HEAD_ROLE_UNDETERMINED:head_not_simple')):
        snap = snap_of(text)
        cut, _ = R.w3b3_scope(snap)
        head, got = R.w3b3_head(snap, cut)
        assert head is None and got == why, (text, got)
    snap = snap_of('母が弟に話した人を兄が呼んだ。')
    cut, _ = R.w3b3_scope(snap)
    head, got = R.w3b3_head(snap, cut)
    assert got is None and head['surface'] == '人'


def test_a_head_that_is_an_estimate_or_unplaced_is_not_typed():
    for text, why in (('母が弟に話した知らせを兄が待った。', 'PLACEMENT_ESTIMATED_GENERATED'), ('兄が弟に頼んだ荷物を母が持った。', 'PLACEMENT_UNPLACED'), ('父が兄に話した医者を母が呼んだ。', 'PLACEMENT_MULTIPLE')):
        ex = explain(text)
        assert ex['reason'] == 'HEAD_ROLE_UNDETERMINED:type:' + why, (text, ex['reason'])


def test_an_estimated_or_split_placement_reads_no_relative_clause():
    """S1-5: the fakes that make every direct answer an estimate or a split one: no relative clause is read."""
    for text in HEAD_READS:
        for mapper in (lambda a: F.to_estimated(a, 'proximity'), lambda a: F.to_estimated(a, 'generated'), F.to_multiple):
            out, _ = new(text, F.FixtureQuery(mapper=mapper))
            assert out['readable'] is False, (text, out['relations'])


def test_the_head_must_be_in_the_main_clause_and_the_refill_must_read_the_same(monkeypatch):
    """HEAD_NOT_IN_HOST and the refill re-reading (K118 9, 10): the reading functions are replaced by a stub that changes one thing."""
    text = '母が弟に話した人を兄が呼んだ。'
    real = SR._w3b3_read_clause

    def no_head(string, query, R_):
        out = real(string, query, R_)
        if string.startswith('人を兄が'):
            out = json.loads(json.dumps(out)); out['clauses'][0]['roles'] = {'agent': '兄', 'patient': '犬'}
        return out
    monkeypatch.setattr(SR, '_w3b3_read_clause', no_head)
    assert explain(text)['reason'] == 'HEAD_NOT_IN_HOST'

    def other_tense(string, query, R_):
        out = real(string, query, R_)
        if string.startswith('人を母が'):
            out = json.loads(json.dumps(out)); out['clauses'][0]['tense'] = 'nonpast'
        return out
    monkeypatch.setattr(SR, '_w3b3_read_clause', other_tense)
    assert explain(text)['reason'] == 'HEAD_ROLE_UNDETERMINED:refill_reread'


def test_a_passive_or_causative_relative_clause_is_not_read_for_its_head(monkeypatch):
    text = '母が弟に話した人を兄が呼んだ。'
    real = SR._w3b3_read_clause

    def passive(string, query, R_):
        out = real(string, query, R_)
        if string.startswith('母が弟に話した'):
            out = json.loads(json.dumps(out)); out['clauses'][0]['voice'] = 'passive'
        return out
    monkeypatch.setattr(SR, '_w3b3_read_clause', passive)
    assert explain(text)['reason'] == 'HEAD_ROLE_UNDETERMINED:voice'


# ---- 7. the relation of two clauses ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('row', [r for r in ROWS['connective'] if r['behavior'] == 'read' and r['entry_expect'] == 'read'], ids=lambda r: r['id'])
def test_a_connective_row_that_is_read_is_correct_and_has_the_relation_of_its_form(row):
    out, _ = new(row['input'])
    assert out['readable'] is True, (row['input'], explain(row['input'])['reason'])
    assert validate_out(out) == [] and verdict(row, out) == 'correct', (row['input'], out)
    assert 'head' not in out['relations'][0]
    rel = {'ので': 'cause', 'から': 'cause', 'が': 'contrast', 'けれど': 'contrast', 'と': 'condition', 'なら': 'condition', 'ば': 'condition', 'たら': 'condition', 'ても': 'concession',
           'ながら': 'simultaneous'}[row['cut']]
    assert out['relations'] == [{'type': rel, 'from': 0, 'to': 1}]
    null_tense = row['cut'] in ('なら', 'ば', 'たら', 'ても', 'ながら')
    assert (out['clauses'][0]['tense'] is None) == null_tense
    assert out['clauses'][1]['tense'] in ('past', 'nonpast')
    assert [c['predicate'] for c in out['clauses']] == [c['predicate'] for c in row['expect']['clauses']]


@pytest.mark.parametrize('text,reason', [
    ('兄が来ると、弟が帰った。', 'RELATION_TYPE_UNDETERMINED:condition_past_main'), ('兄が来れば、弟が帰った。', 'RELATION_TYPE_UNDETERMINED:condition_past_main'),
    ('兄が着いたら、弟が帰った。', 'RELATION_TYPE_UNDETERMINED:condition_past_main'), ('兄が来るなら、弟が帰った。', 'RELATION_TYPE_UNDETERMINED:condition_past_main'),
    ('弟が帰ると、先生が話す。', 'RELATION_TYPE_UNDETERMINED:quote_possible'), ('姉が戻ると、母が見る。', 'RELATION_TYPE_UNDETERMINED:quote_possible'),
])
def test_a_condition_is_not_decided_when_the_main_clause_is_past_or_a_quotation_is_possible(text, reason):
    ex = explain(text)
    assert ex['read'] is False and ex['reason'] == reason, (text, ex['reason'])
    assert SR.read(text, placement=F.FixtureQuery()) == BASE.read(text, placement=F.FixtureQuery())


def test_the_condition_of_to_needs_a_main_predicate_whose_type_is_known_and_not_a_quotation_type():
    out, _ = new('兄が来ると、弟が帰る。')
    assert out['readable'] and out['relations'][0]['type'] == 'condition'
    nothing = F.MapQuery({})                    # nothing is placed: the type of the main predicate is not direct, so a quotation is not excluded
    assert SR.read('兄が来ると、弟が帰る。', placement=nothing)['readable'] is False
    assert explain('兄が来ると、弟が帰る。', F.MapQuery({}))['reason'] == 'RELATION_TYPE_UNDETERMINED:quote_possible'
    # the other connectives do not ask the type of the main predicate
    assert SR.read('兄が来れば、弟が帰る。', placement=F.MapQuery({}))['readable'] is True


@pytest.mark.parametrize('row', ROWS['parallel'], ids=lambda r: r['id'])
def test_te_and_the_continuative_are_not_in_the_output_and_the_edge_is_in_the_diagnosis(row):
    q = F.FixtureQuery(); bq = F.FixtureQuery()
    out = SR.read(row['input'], placement=q)
    assert out == BASE.read(row['input'], placement=bq) and out['readable'] is False, row['input']
    ex = explain(row['input'])
    if row['behavior'] == 'read':
        edge = row['structure_expect']['edges'][0]
        assert ex['edges'] == [edge], (row['input'], ex)
        assert ex['reason'] == 'RELATION_TYPE_UNDETERMINED:' + edge['type']
        for got, want in zip(ex['clause_reads'], row['structure_expect']['clauses']):
            assert got['readable'] is True
            c = got['clause']
            assert (c['predicate'], c['roles'], c['polarity'], c['tense'], c['voice']) == (want['predicate'], want['roles'], want['polarity'], want['tense'], want['voice']), (row['input'], c)
    else:
        assert ex['edges'] == [] and ex['read'] is False


def test_te_and_the_continuative_edges_are_not_a_relation_of_the_convention():
    for t in ('TE_UNDETERMINED', 'PARALLEL_UNDETERMINED'): assert t not in b1.REL_TYPES
    from verantyx import event_cross as EC
    assert 'TE_UNDETERMINED' not in EC.RELATION_TYPES and 'PARALLEL_UNDETERMINED' not in EC.RELATION_TYPES


# ---- 8. ellipsis -------------------------------------------------------------------------------------------------------------------------------------
def test_the_subject_is_filled_by_the_topic_and_only_by_the_topic():
    out, _ = new('兄は本を読んだので、歌を歌った。')
    assert out['readable'] is True
    assert out['clauses'][1]['roles'] == {'agent': '兄', 'patient': '歌'} and out['clauses'][0]['roles'] == {'agent': '兄', 'patient': '本'}
    assert out['relations'] == [{'type': 'cause', 'from': 0, 'to': 1}]
    out, _ = new('兄は本を読みながら、歌を歌った。')
    assert out['readable'] and out['clauses'][1]['roles']['agent'] == '兄' and out['clauses'][0]['tense'] is None
    out, _ = new('兄が本を読んだので、歌を歌った。')            # a が subject is not filled (the cut is also not unique)
    assert out['readable'] is False
    assert explain('兄が本を読んだので、歌を歌った。')['reason'].startswith('CLAUSE_SCOPE_AMBIGUOUS')
    out, _ = new('兄は本を読んだが、母が歌を歌った。')         # the main clause has its own subject: nothing is filled
    assert out['readable'] and out['clauses'][1]['roles']['agent'] == '母'


def test_the_main_clause_that_takes_no_subject_from_the_topic_is_not_read_when_the_filled_reading_differs(monkeypatch):
    text = '兄は本を読んだので、歌を歌った。'
    real = SR._w3b3_read_clause

    def different(string, query, R_):
        out = real(string, query, R_)
        if string.startswith('兄は歌を'):
            out = json.loads(json.dumps(out)); out['clauses'][0]['roles']['agent'] = '母'
        return out
    monkeypatch.setattr(SR, '_w3b3_read_clause', different)
    assert explain(text)['reason'] == 'ELLIPSIS_UNDETERMINED:subject'


@pytest.mark.parametrize('row', [r for r in ALL if r['w3b3_expect'].startswith('ELLIPSIS_UNDETERMINED')], ids=lambda r: r['id'])
def test_an_omitted_object_or_oblique_that_has_an_antecedent_in_the_input_is_not_read(row):
    out, _ = new(row['input'])
    assert out['readable'] is False, row['input']
    ex = explain(row['input'])
    assert ex['reason'].startswith('ELLIPSIS_UNDETERMINED'), (row['input'], ex['reason'])


def test_an_object_that_is_not_omitted_and_an_intransitive_clause_are_read():
    for text in ('兄が本を読んだので、弟が歌を歌った。', '兄が来たから、弟が帰った。'):
        out, _ = new(text)
        assert out['readable'] is True, text


# ---- 9. S3: the misreads of W1-a4 --------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('row', ROWS['w1a4'], ids=lambda r: r['id'])
def test_w1a4_every_misread_is_an_abstention_and_the_output_is_the_bases(row):
    q = F.FixtureQuery(); bq = F.FixtureQuery()
    out = SR.read(row['input'], placement=q)
    bout = BASE.read(row['input'], placement=bq)
    assert out['readable'] is False and out == bout, (row['input'], out)
    assert verdict(row, out) == 'correct'
    assert explain(row['input'])['read'] is False


def test_w1a4_has_all_the_sentences_of_appendix_a_and_the_two_that_were_added():
    assert len(ROWS['w1a4']) == 53 and len({r['input'] for r in ROWS['w1a4']}) == 53
    assert sum(1 for r in ROWS['w1a4'] if '付録 A に無かった' in r['source']) == 2


@pytest.mark.parametrize('text', EN_TEST_INPUTS)
def test_the_english_output_is_not_changed(text):
    q = F.FixtureQuery(); bq = F.FixtureQuery()
    assert SR.read(text, placement=q) == BASE.read(text, placement=bq) and q.calls == bq.calls
    assert SR.read(text, placement=None) == BASE.read(text, placement=None)


# ---- 10. no placement: byte for byte; a sentence the path does not read: byte for byte; a clause read inside the path does not start the path again --------
@pytest.mark.parametrize('text', [r['input'] for r in ALL] + JA_TEST_INPUTS)
def test_without_a_placement_every_output_is_the_bases_and_has_no_head_and_no_basis(text):
    out = SR.read(text, placement=None)
    assert out == BASE.read(text, placement=None)
    assert json.dumps(out, ensure_ascii=False) == json.dumps(BASE.read(text, placement=None), ensure_ascii=False)
    assert 'head' not in json.dumps(out) and 'basis' not in json.dumps(out)


BEFORE_ANY_QUESTION = ('W3B3_NOT_TRIGGERED', 'CLAUSE_SCOPE_', 'CLAUSE_TOKENS_DIFFER', 'CLAUSE_FORM_NOT_READ:imperative', 'CLAUSE_FORM_NOT_READ:quote', 'CLAUSE_FORM_NOT_READ:question',
                       'CLAUSE_FORM_NOT_READ:connective_outside_cut', 'CLAUSE_FORM_NOT_READ:aux_in_nonfinite')


@pytest.mark.parametrize('text', [r['input'] for r in ALL] + JA_TEST_INPUTS)
def test_when_the_path_does_not_read_the_output_is_the_bases_and_the_questions_are_the_bases_until_the_gates_that_need_none(text):
    """K114 3: a sentence the path does not read gets the base's output byte for byte; it asks the placement nothing the base did not ask unless it passed every gate that needs no question
    (the base's questions always come first: the typed readings of W3-b1 / W3-b2 run before the path); a sentence the path reads is one the base did not read."""
    q = F.FixtureQuery(); bq = F.FixtureQuery()
    out = SR.read(text, placement=q)
    bout = BASE.read(text, placement=bq)
    ex = explain(text)
    assert q.calls[:len(bq.calls)] == bq.calls, text
    if ex['read']:
        assert out['readable'] is True and bout['readable'] is False, text
    else:
        assert out == bout, (text, ex['reason'])
        if ex['reason'].startswith(BEFORE_ANY_QUESTION): assert q.calls == bq.calls, (text, ex['reason'])


def test_the_path_is_not_started_from_inside_a_clause_reading():
    text = '兄が本を読んだので、弟が歌を歌った。'
    SR._W3B3_DEPTH[0] = 1
    try:
        out, q = new(text)
        assert out == base(text)[0]
    finally:
        SR._W3B3_DEPTH[0] = 0
    assert SR._W3B3_DEPTH == [0] and new(text)[0]['readable'] is True


def test_a_refusal_the_path_gives_back_is_the_same_object(monkeypatch):
    text = '駅で兄が本を読んだので、弟が歌を歌った。'
    seen = []
    real = SR._w3b3_read_ja

    def spy(text_, R_, placement, out, report):
        res = real(text_, R_, placement, out, report); seen.append((out, res)); return res
    monkeypatch.setattr(SR, '_w3b3_read_ja', spy)
    SR.read(text, placement=F.FixtureQuery())
    assert seen and all(o is r for o, r in seen)


@pytest.mark.parametrize('row', ALL, ids=[r['id'] for r in ALL])
def test_no_row_of_the_data_is_misread_or_incomplete_and_the_fixture_holds_every_word(row):
    q = F.FixtureQuery()
    out = SR.read(row['input'], placement=q)
    assert verdict(row, out) in ('correct', 'abstain'), (row['input'], verdict(row, out), out)
    bq = F.FixtureQuery(); BASE.read(row['input'], placement=bq)
    assert q.misses == [] and bq.misses == [], (q.misses, bq.misses)
    assert verdict(row, out) != 'correct' or row['behavior'] == 'abstain' or out['readable'] is True


# ---- 11. what the path does to the files (the scope of the ticket) -----------------------------------------------------------------------------
def _functions(src):
    t = ast.parse(src)
    out = {}
    for n in t.body:
        if isinstance(n, (ast.FunctionDef, ast.ClassDef)): out[n.name] = ast.get_source_segment(src, n)
        elif isinstance(n, ast.Assign): out[ast.unparse(n.targets[0])] = ast.get_source_segment(src, n)
    return out


def test_semantic_read_changes_only_read_ja_and_semantic_reader_only_adds():
    import difflib, hashlib      # W5-e2: function-local so that the file's top-level is unchanged
    b = _functions(git('show', '%s:verantyx/semantic_read.py' % BASE_COMMIT)); n = _functions((TREE / 'verantyx' / 'semantic_read.py').read_text(encoding='utf-8'))
    assert [k for k in b if k in n and b[k] != n[k]] == ['_read_ja'] and not [k for k in b if k not in n]
    br = _functions(git('show', '%s:verantyx/semantic_reader.py' % BASE_COMMIT)); nr = _functions((TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8'))
    # W5-e2（監査役の判断 2026-10-04 04:42、K-B）: 並立・選言の門（10E）を入れる差し込み口が無く、document_view に 1 行足した。変わった関数は document_view だけで、その差は追加 1 行だけ
    # （削除 0 行）。新しい本文の sha256 を固定する（W3-b2/b3 のハッシュ固定と同じ扱い。docs/READING_SOUNDNESS.md 10E.2）
    assert [k for k in br if k in nr and br[k] != nr[k]] == ['document_view'] and not [k for k in br if k not in nr]
    ndiff = [l for l in difflib.ndiff(br['document_view'].splitlines(), nr['document_view'].splitlines()) if l[:1] in '+-']
    assert [(l[0], l[1:].strip()) for l in ndiff] == [('+', 'cs = [_coordination_gate(c) for c in cs]')], ndiff
    assert hashlib.sha256(br['document_view'].encode('utf-8')).hexdigest() == '20b032d03e136b2b260c445d446e7de2ce642596844113f6f32d2678aeeb73fa'
    assert hashlib.sha256(nr['document_view'].encode('utf-8')).hexdigest() == 'b37c85231d62d4611d2ffa3df7f207e86f6c22b41c7e30f20e006d7ce15d62b8'
    diff = git('diff', BASE_COMMIT, '--', 'verantyx/semantic_reader.py').splitlines()
    assert not [l for l in diff if l.startswith('-') and not l.startswith('---')]
    rd = git('diff', BASE_COMMIT, '--', 'verantyx/semantic_read.py').splitlines()
    removed = [l for l in rd if l.startswith('-') and not l.startswith('---')]
    added = [l for l in rd if l.startswith('+') and not l.startswith('+++')]
    assert len(removed) == 1 and 'return _typed_reread_ja(' in removed[0], removed
    assert sum('_w3b3_read_ja(text, R, placement, out, unsupported_report)' in l for l in added) == 1, added


def test_the_w3b3_section_of_the_reader_holds_no_word_of_a_sentence():
    """No word list: every non-ASCII string literal of the new section is a tagger term (part of speech, form), a particle / auxiliary of the registered cuts, a kind of the
    cut table, or one of the 11 words of the registered lists (the permission words and the quotation verbs)."""
    src = (TREE / 'verantyx' / 'semantic_reader.py').read_text(encoding='utf-8')
    start = src.index('# W3-b3:')
    tree = ast.parse(src[start:])
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and re.search('[^\x00-\x7f]', n.value)}
    tagger = {'動詞', '名詞', '助詞', '助動詞', '接頭辞', '接尾辞', '接続助詞', '格助詞', '係助詞', '準体助詞', '連体詞', '副詞', '代名詞', '形容詞', '形状詞', '補助記号', '読点', '句点', '数詞',
              '終助詞', '副助詞', '副詞可能', '助数詞可能', '非自立可能', '連体形', '終止形', '連用形', '仮定形', '未然形', '命令形', '連用形-一般', '接続詞', '助動詞語幹'}
    particles = {'の', 'に', 'も', 'は', 'が', 'を', 'から', 'と', 'ば', 'ながら', 'けれど', 'けれども', 'けど', 'で', 'て', 'だ', 'た', 'たら', 'だら', 'なら', 'ても', 'でも', 'ので', 'ない', '、', '。', 'か',
                 '「', '」', '『', '』', '\u201c', '\u201d', '？', '?'}
    kinds = {k[0] for k in R.W3B3_CUTS} | {c for k in R.W3B3_CUTS for c in k[1]}
    words = set(R.W3B3_PERMISSION_WORDS) | set(R.W3B3_QUOTE_VERBS)
    extra = literals - tagger - particles - kinds - words
    assert extra == set(), extra
