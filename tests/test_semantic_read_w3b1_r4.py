"""W3-b1 round 4 (review round 3, M8): a clause that a typed path (U, S4) read must not have a head that may be a derived verb (a potential, a spontaneous or a short
causative looks like a verb of its own in the output of the tagger). Docs/READING_SOUNDNESS.md section 10, K63 "派生の疑いの門", table change record 3, registered
2026-10-03 17:09:34 +0900.

Order of events (honest, `artifacts/w3-b1/r4_gate_prereg_time.txt` < `r10_placement_answers_time.txt` < `bank_freeze_r10_time.txt` < `r10_before_gate_time.txt` <
`r4_impl_time.txt` < `w3b1_tests_freeze_r4_time.txt`): the gate was registered in the docs, the placement of the words of ja_r10 was asked, the data ja_r10.jsonl was
written and frozen from its generator, the data was run on the code without the gate (`r10_before_gate_live.txt`: 11 rows misread), THEN the gate was written, THEN this file.
The frozen tests of rounds 1 and 2 (test_semantic_read_w3b1.py, test_semantic_read_w3b1_events.py) are not changed by this round.

Placement answers here come from fakes (tests/reading_soundness/w3b1_fakes.py); no real placement is opened. Run under a clean environment (env -i).
"""
import hashlib
import importlib.util
import inspect
import json
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

TREE = Path(__file__).resolve().parent.parent
RS = TREE / 'tests' / 'reading_soundness'


def _load_by_path(name, path):
    """Load a helper module by its path under a unique name (sys.path is not changed; see test_semantic_read_w3b1.py)."""
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


F = _load_by_path('w3b1_fakes', RS / 'w3b1_fakes.py')

from tools.bank_score.v2 import b1    # noqa: E402
from verantyx import semantic_read as SR    # noqa: E402
from verantyx import semantic_reader as R    # noqa: E402

DOCS = (TREE / 'docs' / 'READING_SOUNDNESS.md').read_text(encoding='utf-8')
BASE_COMMIT = '0ff3f35'
TAIL = 'PLACEMENT_PREDICATE_TAIL_UNINTERPRETED'
DERIVED = 'PLACEMENT_PREDICATE_POSSIBLY_DERIVED'


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


R10 = [json.loads(l) for l in (RS / 'ja_r10.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]


def reasons(out):
    assert out['readable'] is False, out
    return out['abstain']['reasons']


def derived_of(text):
    view = R.document_view({'d': text})
    assert len(view.clauses) == 1, text
    return R.typed_head_derived_ja(R._tokens(text), view.clauses[0])


def no_gate(monkeypatch):
    monkeypatch.setattr(R, 'typed_head_derived_ja', lambda toks, clause: None)


# ---------------------------------------------------------------------------------------------------------------------------------
# 1. the table in the docs is the code, and holds no word
# ---------------------------------------------------------------------------------------------------------------------------------
def test_the_derived_gate_table_in_the_docs_is_the_constant_of_the_code_and_holds_no_word():
    rows = block('w3b1_derived_gate')
    assert tuple((r[0], None if r[1] == '問わない' else r[1]) for r in rows) == R.DERIVED_GATE
    assert [r[0] for r in rows] == ['下一段', '五段-サ行']
    for r in rows:
        assert r[2] == DERIVED + ':<活用型>'
        assert len(r) == 3 and r[1] in ('問わない', 'ア段+す')                  # a structure of the conjugation, not a list of words
    assert R.DERIVED_GATE == (('下一段', None), ('五段-サ行', 'ア段+す'))


def test_the_kana_of_the_a_column_in_the_docs_are_the_set_of_the_code_and_are_not_words():
    m = re.search(r'清音・濁音・半濁音: ([^)]*)\)', DOCS)
    assert m
    assert set(m.group(1).replace(' ', '')) == set(R._A_ROW_KANA) and all(len(k) == 1 for k in R._A_ROW_KANA)
    assert len(R._A_ROW_KANA) == 15


def test_the_reason_and_the_change_record_are_registered_in_the_docs_inside_the_preregistration_block():
    registered = {re.split(r'[:\[<]', r[0])[0] for r in block('w3b1_reasons')}
    assert DERIVED in registered
    begin, end = DOCS.index('<!-- w3b1-prereg:begin -->'), DOCS.index('<!-- w3b1-prereg:end -->')
    assert begin < DOCS.index('<!-- BEGIN table:w3b1_derived_gate -->') < end
    rec = DOCS.index('3. **2026-10-03 17:09:34 +0900')
    assert begin < rec < end and 'レビュー第 3 ラウンド' in DOCS[rec:end] and 'M8' in DOCS[rec:end]


def test_the_frozen_data_of_round_4_is_the_data_that_was_frozen():
    sums = dict(reversed(line.split()) for line in (TREE / 'artifacts' / 'w3-b1' / 'bank_freeze_r10.sha256').read_text(encoding='utf-8').splitlines() if line.strip())
    for name in ('ja_r10.jsonl', 'w3b1_mk_r10.py', 'w3b1_r10_excluded.txt'):
        key = [k for k in sums if k.endswith(name)]
        assert len(key) == 1 and hashlib.sha256((RS / name).read_bytes()).hexdigest() == sums[key[0]], name


# ---------------------------------------------------------------------------------------------------------------------------------
# 2. the function itself: a closed structure of the conjugation type and the end of the dictionary form
# ---------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text,want', [
    # a potential verb (a shimo-ichidan verb of its own in the tagger), any ending the tail gate lets through
    ('猫が庭へ歩けた。', DERIVED + ':下一段-カ行'), ('兄が駅へ歩けない。', DERIVED + ':下一段-カ行'), ('兄が駅へ歩けなかった。', DERIVED + ':下一段-カ行'),
    ('姉が冬、皿を洗えた。', DERIVED + ':下一段-ア行'), ('兄が夜、字を書けない。', DERIVED + ':下一段-カ行'),
    # a shimo-ichidan verb that is not a potential: the gate is wide (a cost, K83)
    ('猫が庭へ出た。', DERIVED + ':下一段-ダ行'), ('母が冬、窓を閉めた。', DERIVED + ':下一段-マ行'), ('母が昼、窓を開けた。', DERIVED + ':下一段-カ行'),
    # a ra-dropped potential, a spontaneous verb
    ('兄が夜、映画を見れた。', DERIVED + ':下一段-ラ行'), ('姉が夜、昔を思えた。', DERIVED + ':下一段-ア行'),
    # a short causative (a godan verb of the sa line whose dictionary form ends in a kana of the a-column and す)
    ('猫が庭へ歩かした。', DERIVED + ':五段-サ行'), ('兄が夜、弟を走らした。', DERIVED + ':五段-サ行'), ('姉が夜、本を読ました。', DERIVED + ':五段-サ行'),
    ('姉が冬、皿を洗わした。', DERIVED + ':五段-サ行'), ('兄が夜、手紙を書かさない。', DERIVED + ':五段-サ行'),
    # godan sa-line verbs whose dictionary form does not end in a kana of the a-column and す (the okurigana is taken by the kanji), the other godan verbs, kami-ichidan, できる
    ('兄が夜、手紙を渡した。', None), ('母が昼、本を返した。', None), ('母が病院へ引き返した。', None), ('先生が冬、本を貸さなかった。', None),
    ('猫が庭へ走った。', None), ('兄が駅へ歩いた。', None), ('姉が冬、皿を洗った。', None), ('母が昼、写真を見た。', None), ('弟が冬、服を着た。', None),
    ('姉が冬、掃除ができた。', None),
])
def test_the_function_gives_the_reason_or_none_by_the_conjugation_type_and_the_end_of_the_dictionary_form(text, want):
    assert derived_of(text) == want


def test_a_head_that_is_not_found_is_refused_and_the_signature_has_no_placement():
    toks = R._tokens('猫が庭へ走った。')
    assert R.typed_head_derived_ja(toks, SimpleNamespace(predicate_span=SimpleNamespace(end=10 ** 6))) == DERIVED + ':head'
    assert list(inspect.signature(R.typed_head_derived_ja).parameters) == ['toks', 'clause']


def test_the_function_does_not_read_the_answer_fields_of_the_placement_and_does_not_ask_it():
    src = inspect.getsource(R.typed_head_derived_ja)
    for needle in ("'state'", '"state"', "'origin'", '"origin"', "'top'", '"top"', 'decided_by', 'estimate_basis', 'query(', 'placement_type', '.lemma'):
        assert needle not in src, needle
    assert '_base(' in src                                                        # the dictionary form of the tagger (orthBase), not feature.lemma


# ---------------------------------------------------------------------------------------------------------------------------------
# 3. the entry: the sentences of the review (round 3, M8), the short causatives of the plan, and the sentences that the review did not list
# ---------------------------------------------------------------------------------------------------------------------------------
def u_map():
    m = {w: F.answer('P_MOVE') for w in ('走る', '歩く', '歩ける', '歩かす', '行ける', '戻れる')}
    m.update({w: F.answer('PERSON') for w in ('兄', '弟', '姉')})
    m.update({w: F.answer('ANIMAL') for w in ('猫',)})
    m.update({w: F.answer('PLACE') for w in ('庭', '駅', '港', '島')})
    return m


def s4_map():
    return {w: F.answer('TIME', decided_by=['definition']) for w in ('昼', '冬', '休日', '夜', '年末')}


REVIEW = [   # the six misreads of the review (round 3) and the two the review's author found next to them; the short causatives of the plan (section 1.3)
    ('猫が庭へ歩けた。', u_map), ('兄が駅へ歩けなかった。', u_map), ('兄が駅へ歩けない。', u_map),
    ('姉が冬、皿を洗えた。', s4_map), ('姉が年末、皿を洗えなかった。', s4_map), ('姉が休日、絵を描けた。', s4_map),
    ('兄が夜、手紙を書けた。', s4_map), ('兄が夜、字を書けない。', s4_map),
    ('姉が夜、本を読ました。', s4_map), ('兄が夜、弟を走らした。', s4_map), ('姉が冬、皿を洗わした。', s4_map), ('兄が夜、手紙を書かした。', s4_map),
    ('猫が庭へ歩かした。', u_map),
]


@pytest.mark.parametrize('text,mapper', REVIEW, ids=[t for t, _ in REVIEW])
def test_the_sentences_of_the_review_and_the_short_causatives_are_abstentions_with_the_readers_reason_first(text, mapper):
    out = SR.read(text, placement=F.MapQuery(mapper()))
    rs = reasons(out)
    plain = SR.read(text, placement=None)
    assert plain['readable'] is False
    assert rs[0] == plain['abstain']['reasons'][0] and len(rs) == 2 and rs[1].startswith(DERIVED + ':'), rs
    assert out['clauses'] == []


@pytest.mark.parametrize('text,mapper', REVIEW, ids=[t for t, _ in REVIEW])
def test_without_the_gate_the_same_sentences_are_read_in_the_derived_form_which_is_what_the_gate_stops(text, mapper, monkeypatch):
    no_gate(monkeypatch)
    out = SR.read(text, placement=F.MapQuery(mapper()))
    assert out['readable'] is True
    c = out['clauses'][0]
    assert c['modality'] is None and c['voice'] == 'active'                       # the derived form returned with no modality / voice: the misreading


def test_the_gate_asks_the_placement_the_same_questions_with_and_without_it(monkeypatch):
    for text, mapper in REVIEW:
        q1 = F.MapQuery(mapper()); SR.read(text, placement=q1)
        q2 = F.MapQuery(mapper())
        monkeypatch.setattr(R, 'typed_head_derived_ja', lambda toks, clause: None)
        SR.read(text, placement=q2)
        monkeypatch.undo()
        assert q1.calls == q2.calls, text


# ---------------------------------------------------------------------------------------------------------------------------------
# 4. the gate is after the ending gate and the reread: the reasons of everything refused before are unchanged
# ---------------------------------------------------------------------------------------------------------------------------------
def test_the_derived_gate_is_after_the_tail_gate_and_the_reread():
    out = SR.read('母が冬、窓を閉めるな。', placement=F.MapQuery(s4_map()))
    assert reasons(out)[1].startswith(TAIL + ':') and len(reasons(out)) == 2          # 閉める is a shimo-ichidan verb, but the tail gate refuses it first
    out = SR.read('猫が庭へ歩きたい。', placement=F.MapQuery(u_map()))
    assert reasons(out)[1].startswith('PLACEMENT_REREAD_ABSTAINS:')
    out = SR.read('兄が駅へ歩け。', placement=F.MapQuery(u_map()))
    assert reasons(out)[1].startswith(TAIL + ':命令形')


def test_a_plain_godan_and_a_sa_line_verb_without_the_a_column_are_still_read():
    out = SR.read('猫が庭へ走った。', placement=F.MapQuery(u_map()))
    assert out['readable'] is True and out['clauses'][0]['predicate'] == '走る' and out['clauses'][0]['predicate_basis'] == 'placement_direct:P_MOVE'
    out = SR.read('兄が夜、手紙を渡した。', placement=F.MapQuery(s4_map()))
    assert out['readable'] is True and out['clauses'][0]['predicate'] == '渡す' and out['clauses'][0]['role_basis'] == {'time': 'placement_direct:TIME'}


def test_dekiru_is_refused_by_the_existing_mark_of_the_entry_and_not_by_the_derived_gate():
    for text in ('姉が冬、掃除ができた。', '母が昼、洗濯ができなかった。', '兄が夜、勉強できた。'):
        out = SR.read(text, placement=F.MapQuery(dict(s4_map(), **{w: F.answer('EVENT_ACT') for w in ('掃除', '洗濯', '勉強')})))
        rs = reasons(out)
        assert not any(r.startswith(DERIVED) for r in rs), (text, rs)


# ---------------------------------------------------------------------------------------------------------------------------------
# 6. the data ja_r10 (frozen 17:11:28, before the gate)
# ---------------------------------------------------------------------------------------------------------------------------------
def test_the_data_has_the_registered_shape():
    paths = {r['path'] for r in R10}
    assert paths == {'U', 'S4'}
    derived = {(r['path'], r['derived']) for r in R10}
    for path in ('U', 'S4'):
        for d in ('potential', 'short_causative', 'ichidan_plain', 'godan_plain', 'sa_not_a'):
            assert (path, d) in derived, (path, d)
    assert len([r for r in R10 if r['derived'] == 'potential']) >= 24 and len([r for r in R10 if r['derived'] == 'short_causative']) >= 8
    assert len([r for r in R10 if r['derived'] in ('ichidan_plain', 'godan_plain', 'sa_not_a', 'dekiru')]) >= 16
    assert len([r for r in R10 if r['derived'] in ('ranuki', 'spontaneous')]) >= 2
    assert {r['tail'] for r in R10 if r['derived'] == 'potential'} == {'past', 'nonpast', 'neg', 'negpast'}


# declared (not hidden): rows registered `abstain` that the base commit reads itself, and reads correctly (the same output with no placement; no typed path was reached;
# not a hole of this change). The data is not changed.
BASELINE_READS = {'W3B1-R10-U-022', 'W3B1-R10-U-024', 'W3B1-R10-U-025', 'W3B1-R10-U-026', 'W3B1-R10-U-027'}
# declared (not hidden): rows registered `read` whose time word fails the evidence gate 5 (K62: a word of the time type decided only by the arm of the role
# distribution); I chose the words of these rows from the placement answers without asking which of them pass the gate (the choice of the data, not of the gate).
READ_EXPECTED_BUT_ABSTAINED = {
    'W3B1-R10-S4-027': ['NO_SUPPORTED_CLAUSE', 'PLACEMENT_SLOT_EVIDENCE_ONLY:part:週末'],
    'W3B1-R10-S4-029': ['NO_SUPPORTED_CLAUSE', 'PLACEMENT_SLOT_EVIDENCE_ONLY:part:夏'],
    'W3B1-R10-S4-030': ['NO_SUPPORTED_CLAUSE', 'PLACEMENT_SLOT_EVIDENCE_ONLY:part:秋'],
    'W3B1-R10-S4-033': ['NO_SUPPORTED_CLAUSE', 'PLACEMENT_SLOT_EVIDENCE_ONLY:part:夕方'],
}


@pytest.mark.parametrize('row', R10, ids=[r['id'] for r in R10])
def test_every_row_of_ja_r10_with_the_fixture(row, monkeypatch):
    q = F.FixtureQuery()
    out = SR.read(row['input'], 'ja', placement=q)
    assert q.misses == [], q.misses
    plain = SR.read(row['input'], 'ja', placement=None)
    verdict = b1.judge(row['expect'], 'ja', out)['verdict']
    assert verdict in ('correct', 'abstain'), (verdict, out['clauses'])             # never a wrong or half reading
    if row['id'] in BASELINE_READS:
        assert row['entry_expect'] == 'abstain' and out == plain and out['readable'] is True and verdict == 'correct'
        return
    if row['id'] in READ_EXPECTED_BUT_ABSTAINED:
        assert row['entry_expect'] == 'read' and out['readable'] is False and out['abstain']['reasons'] == READ_EXPECTED_BUT_ABSTAINED[row['id']]
        return
    if row['entry_expect'] == 'read':
        assert out['readable'] is True and verdict == 'correct', (out['abstain'], out['clauses'])
        assert out == plain or 'role_basis' in out['clauses'][0]                       # read by a typed path (it says where from), or by the base commit itself, the same
        assert row['derived'] in ('godan_plain', 'ichidan_upper', 'sa_not_a')
    else:
        assert out['readable'] is False, out['clauses']
        rs = out['abstain']['reasons']
        if len(rs) == 2 and rs[1].startswith(DERIVED + ':'):
            # the gate is what stopped it: without the gate the row is read (and, for the derived kinds, wrongly)
            monkeypatch.setattr(R, 'typed_head_derived_ja', lambda toks, clause: None)
            without = SR.read(row['input'], 'ja', placement=F.FixtureQuery())
            assert without['readable'] is True
            if row['derived'] in ('potential', 'short_causative'):
                assert b1.judge(row['expect'], 'ja', without)['verdict'] == 'misread', row['id']


def test_the_gate_itself_stopped_rows_of_each_derived_kind_on_the_paths_where_the_data_reaches_it():
    gated = set()
    for row in R10:
        out = SR.read(row['input'], 'ja', placement=F.FixtureQuery())
        rs = out['abstain']['reasons'] if not out['readable'] else []
        if len(rs) == 2 and rs[1].startswith(DERIVED + ':'): gated.add((row['path'], row['derived']))
    # the data reaches the gate with a potential on path U (a verb the base commit's own suspicion does not catch), with a short causative on both paths; the rows of
    # the other kinds may be stopped earlier (K83, K84: the time words of some S4 rows fail the evidence gate 5 before the gate is reached)
    assert {('U', 'potential'), ('U', 'short_causative'), ('S4', 'short_causative')} <= gated, gated



def test_every_second_reason_the_data_produces_is_registered_in_the_docs():
    registered = {re.split(r'[:\[<]', r[0])[0] for r in block('w3b1_reasons')}
    assert DERIVED in registered
    seen = set()
    for row in R10:
        out = SR.read(row['input'], 'ja', placement=F.FixtureQuery())
        if not out['readable']: seen.update(x.split(':')[0] for x in out['abstain']['reasons'][1:] if x.startswith('PLACEMENT_'))
    assert DERIVED in seen and seen <= registered, sorted(seen - registered)


# ---------------------------------------------------------------------------------------------------------------------------------
# 7. direct only (nothing new is read from an estimated or a split answer) and no placement = the base commit
# ---------------------------------------------------------------------------------------------------------------------------------
def _nothing_new(mapper, label):
    for row in R10:
        plain = SR.read(row['input'], 'ja', placement=None)
        got = SR.read(row['input'], 'ja', placement=F.FixtureQuery(mapper=mapper))
        if plain['readable']: assert got == plain, (label, row['input'])
        else:
            assert got['readable'] is False and got['abstain']['reasons'][0] == plain['abstain']['reasons'][0], (label, row['input'], got['clauses'])


def test_estimated_and_multiple_answers_alone_read_nothing_new_in_ja_r10():
    _nothing_new(lambda a: F.to_estimated(a, 'proximity'), 'estimated_proximity')
    _nothing_new(lambda a: F.to_estimated(a, 'generated'), 'estimated_generated')
    _nothing_new(F.to_multiple, 'multiple')


def _base_module():
    src = subprocess.run(['git', '-C', str(TREE), 'show', '%s:verantyx/semantic_read.py' % BASE_COMMIT], capture_output=True, check=True).stdout
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_base_w3b1_r4', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src.decode('utf-8'), 'verantyx/semantic_read.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    return mod


def test_without_a_placement_every_ja_r10_output_is_the_base_commits_output_byte_for_byte():
    base = _base_module()
    for row in R10:
        expect = json.dumps(base.read(row['input']), ensure_ascii=False)
        assert json.dumps(SR.read(row['input']), ensure_ascii=False) == expect, row['input']
        assert json.dumps(SR.read(row['input'], placement=None), ensure_ascii=False) == expect, row['input']


def test_the_declared_rows_stopped_by_the_derived_gate_name_table_change_record_3_as_the_cause_and_not_record_1():
    """review.r1 of round 4, M1: a row returned to "not read" by the derived gate says so in its `why` (the cause is read off the output's second reason, not off the generator)."""
    declared = json.loads((RS / 'w3b1_expect_exceptions.json').read_text(encoding='utf-8'))['exceptions']
    by_gate = [e for e in declared if len(e['observed'].get('reasons') or []) >= 2 and e['observed']['reasons'][1].startswith(DERIVED)]
    assert by_gate, 'no declared row is stopped by the derived gate'
    for e in by_gate:
        assert e['kind'] == 'row_returned_to_abstain', e['id']
        assert 'table change record 3' in e['why'] and 'table change record 1' not in e['why'], e['id']
    for e in declared:
        if e not in by_gate and 'table change record 3' in e['why']: raise AssertionError('%s names record 3 but its second reason is not the derived gate' % e['id'])
