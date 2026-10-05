"""W3-b1 round 3 (review round 2, M7): a clause that a typed path (U, S4) read must end in one of the four endings that the present rules turn into a polarity and a
tense (docs/READING_SOUNDNESS.md section 10, K63 "述語の語尾の門", table change record 2, registered 2026-10-03 16:12:52 +0900).

Order of events (honest): the gate was registered in the docs (16:12:52), the data ja_r9.jsonl was written and frozen from its generator (`bank_freeze_r9_time.txt`,
16:14:40; its first run on the code without the gate gave 16 misreads and 1 incomplete: `r9_before_gate_live.txt`), THEN the gate was written, THEN this file.
The frozen tests of round 1 and 2 (test_semantic_read_w3b1.py, test_semantic_read_w3b1_events.py) are not changed by this round.

Placement answers here come from fakes (tests/reading_soundness/w3b1_fakes.py); no real placement is opened. Run under a clean environment (env -i).
"""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

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
BASE_COMMIT = '2732274'  # integration: dev before the W3-b1 merge (W5-a changed the base reading)
TAIL = 'PLACEMENT_PREDICATE_TAIL_UNINTERPRETED'


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


R9 = [json.loads(l) for l in (RS / 'ja_r9.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]


def reasons(out):
    assert out['readable'] is False, out
    return out['abstain']['reasons']


def tail_of(text):
    view = R.document_view({'d': text})
    assert len(view.clauses) == 1, text
    return R.typed_tail_ja(R._tokens(text), view.clauses[0])


# ---------------------------------------------------------------------------------------------------------------------------------
# K63: the four shapes (docs == code), and what is not one of them
# ---------------------------------------------------------------------------------------------------------------------------------
SHAPES = [
    ('終止形', '空', '猫が庭へ走る。'),
    ('連用形', '助動詞(原形 た・終止形)1 つ', '猫が庭へ走った。'),
    ('未然形', '助動詞(原形 ない・終止形)1 つ', '猫が庭へ走らない。'),
    ('未然形', '助動詞(原形 ない・連用形)1 つと、助動詞(原形 た・終止形)1 つ', '猫が庭へ走らなかった。'),
]


def test_the_tail_gate_table_in_the_docs_is_the_four_registered_shapes_and_holds_no_word_of_a_sentence():
    docs = block('w3b1_tail_gate')
    assert [(r[0], r[1]) for r in docs] == [(a, b) for a, b, _ in SHAPES]
    for r in docs:    # only a form of a verb and an auxiliary (原形 た・ない); not a list of endings
        assert not re.search(r'(ている|ません|たい|まい|ください|らしい|そうだ|べき|かもしれ)', ' '.join(r))


@pytest.mark.parametrize('form,tail,text', SHAPES, ids=[s[2] for s in SHAPES])
def test_each_of_the_four_shapes_passes_and_nothing_else_does_not(form, tail, text):
    assert tail_of(text) is None


@pytest.mark.parametrize('text,want', [
    # the sentences of the review (round 2, M7 table): each was read as polarity "+" / modality null by the typed paths
    ('姉が昼、本を読んでいない。', TAIL + ':連用形-撥音便:助詞'),
    ('姉が昼、本を読んでいなかった。', TAIL + ':連用形-撥音便:助詞'),
    ('姉が昼、本を読んでいません。', TAIL + ':連用形-撥音便:助詞'),
    ('姉が昼、本を読むな。', TAIL + ':終止形-一般:助詞'),
    ('姉が昼、本を読むまい。', TAIL + ':終止形-一般:助動詞'),
    ('姉が昼、本を読みたかった。', TAIL + ':連用形-一般:助動詞'),
    ('姉が昼、本を読め。', TAIL + ':命令形:なし'),
    ('猫が庭へ走るな。', TAIL + ':終止形-一般:助詞'),
    ('兄が駅へ歩け。', TAIL + ':命令形:なし'),
    ('弟が港へ走りたかった。', TAIL + ':連用形-一般:助動詞'),
    ('姉が島へ飛ぶまい。', TAIL + ':終止形-一般:助動詞'),
    # endings named in the review's list that ja_r9 does not hold (ず / ぬ, てしまう in the non-past, てください after a verb in て)
    ('姉が昼、本を読まず。', TAIL + ':未然形-一般:助動詞'),
    ('姉が昼、本を読まぬ。', TAIL + ':未然形-一般:助動詞'),
    ('姉が昼、本を読んでしまう。', TAIL + ':連用形-撥音便:助詞'),
    ('姉が昼、本を読んでください。', TAIL + ':連用形-撥音便:助詞'),
    # endings the present rules may or may not interpret: not told apart (a wide abstention)
    ('姉が昼、本を読みました。', TAIL + ':連用形-一般:助動詞'),
    ('姉が昼、本を読まれた。', TAIL + ':未然形-一般:助動詞'),
    ('姉が昼、本を読ませた。', TAIL + ':未然形-一般:助動詞'),
    ('姉が昼、本を読んだよ。', TAIL + ':連用形-撥音便:助動詞'),
    ('姉が昼、本を読んだ！', TAIL + ':連用形-撥音便:助動詞'),        # ！ stays in the tail (only a full stop is dropped)
])
def test_an_ending_that_is_not_one_of_the_four_is_refused_with_its_form_and_the_part_of_speech_after_the_head(text, want):
    assert tail_of(text) == want


def test_the_closing_full_stop_is_optional_and_nothing_follows_it():
    assert tail_of('猫が庭へ走った') is None and tail_of('猫が庭へ走った。') is None


# ---------------------------------------------------------------------------------------------------------------------------------
# the entry: the gate runs after the reread, so every earlier refusal keeps its reason; a refusal by the gate keeps the reader's reason first
# ---------------------------------------------------------------------------------------------------------------------------------
def u_map(**over):
    m = {w: F.answer('P_MOVE') for w in ('走る', '歩く', '飛ぶ')}
    m.update({w: F.answer('PERSON') for w in ('兄', '弟', '姉')})
    m.update({w: F.answer('ANIMAL') for w in ('猫',)})
    m.update({w: F.answer('PLACE') for w in ('庭', '駅', '港', '島')})
    m.update(over)
    return m


def s4_map():
    return {w: F.answer('TIME', decided_by=['definition']) for w in ('昼', '冬', '休日', '夜')}


def test_a_typed_reading_with_a_plain_ending_is_still_read_and_the_polarity_and_tense_are_the_reader_s():
    for text, pol, tense in [('猫が庭へ走る。', '+', 'nonpast'), ('猫が庭へ走った。', '+', 'past'), ('猫が庭へ走らない。', '-', 'nonpast'), ('猫が庭へ走らなかった。', '-', 'past')]:
        out = SR.read(text, placement=F.MapQuery(u_map()))
        assert out['readable'] is True, (text, out['abstain'])
        c = out['clauses'][0]
        assert (c['polarity'], c['tense'], c['modality']) == (pol, tense, None) and c['predicate_basis'] == 'placement_direct:P_MOVE'
    for text, pol, tense in [('姉が昼、本を読んだ。', '+', 'past'), ('姉が昼、本を読む。', '+', 'nonpast'), ('姉が昼、本を読まなかった。', '-', 'past'), ('姉が昼、本を読まない。', '-', 'nonpast')]:
        out = SR.read(text, placement=F.MapQuery(s4_map()))
        assert out['readable'] is True, (text, out['abstain'])
        c = out['clauses'][0]
        assert (c['polarity'], c['tense'], c['modality']) == (pol, tense, None) and c['role_basis'] == {'time': 'placement_direct:TIME'}


K800_KIND = {'弟が港へ走りたかった。': 'desire'}     # Integration (auditor ruling 2026-10-06, W16-t1b K800): the rows of the list below that the modality gate stops first


@pytest.mark.parametrize('text,mapping', [
    ('姉が昼、本を読んでいない。', s4_map()), ('姉が昼、本を読んでいなかった。', s4_map()), ('姉が昼、本を読んでいません。', s4_map()),
    ('姉が昼、本を読むな。', s4_map()), ('姉が昼、本を読むまい。', s4_map()), ('姉が昼、本を読みたかった。', s4_map()), ('姉が昼、本を読め。', s4_map()),
    ('母が冬、窓を閉めるな。', s4_map()), ('弟が休日、皿を洗いたかった。', s4_map()),
    ('猫が庭へ走るな。', u_map()), ('兄が駅へ歩け。', u_map()), ('弟が港へ走りたかった。', u_map()), ('姉が島へ飛ぶまい。', u_map()),
])
def test_the_thirteen_misreads_of_the_review_are_abstentions_now_with_the_readers_reason_first(text, mapping):
    """Integration (auditor ruling 2026-10-06, W16-t1b K800): for 弟が港へ走りたかった。 (a desire sentence) the modality gate stops the clause before the placement is asked, so the reasons are
    ['NO_SUPPORTED_CLAUSE'] with MODALITY_NOT_READ:desire in the unsupported list (abstention -> abstention, only the reason changes); old expectation: len(rs) == 2 and rs[1].startswith(TAIL + ':').
    The other twelve rows are unchanged."""
    out = SR.read(text, placement=F.MapQuery(mapping))
    rs = reasons(out)
    plain = SR.read(text, placement=None)
    assert plain['readable'] is False                          # the base commit refuses them
    if text in K800_KIND:
        assert rs == ['NO_SUPPORTED_CLAUSE'] and 'MODALITY_NOT_READ:' + K800_KIND[text] in [r for u in out['unsupported'] for r in u['reasons']], rs
        assert out['clauses'] == []
        return
    assert rs[0] == plain['abstain']['reasons'][0] and len(rs) == 2 and rs[1].startswith(TAIL + ':'), rs
    assert out['clauses'] == []


def test_the_gate_is_after_the_reread_so_an_earlier_refusal_keeps_its_reason():
    """Integration (auditor ruling 2026-10-06, W16-t1b K800): 猫が庭へ歩きたい。 (a desire sentence) is stopped by the modality gate first: ['NO_SUPPORTED_CLAUSE'] with MODALITY_NOT_READ:desire in the
    unsupported list; old expectation: reasons(out)[1].startswith('PLACEMENT_REREAD_ABSTAINS:'). The second row (a sentence without a modal auxiliary) is unchanged."""
    out = SR.read('猫が庭へ歩きたい。', placement=F.MapQuery(u_map()))
    assert reasons(out) == ['NO_SUPPORTED_CLAUSE'] and 'MODALITY_NOT_READ:desire' in [r for u in out['unsupported'] for r in u['reasons']]
    out = SR.read('猫は庭へ歩いた。', placement=F.MapQuery(u_map()))
    assert len(reasons(out)) == 1                                              # a trigger the typed paths do not answer: no placement reason at all


# ---------------------------------------------------------------------------------------------------------------------------------
# the data ja_r9 (frozen 16:14:40, before the gate)
# ---------------------------------------------------------------------------------------------------------------------------------
def test_the_data_has_the_registered_shape():
    assert len(R9) >= 40
    for path in ('U', 'S4'):
        rows = [r for r in R9 if r['path'] == path]
        assert len(rows) >= 20
        n_read = sum(r['entry_expect'] == 'read' for r in rows)
        assert 0 < n_read < len(rows)                                           # plain endings are in it (the gate must not be wider than it has to be) and the others too
    assert {r['tail'] for r in R9} >= {'past', 'nonpast', 'neg', 'negpast', 'prog', 'progneg', 'polneg', 'proh', 'imp', 'nomore', 'desire', 'please', 'shimau', 'oku',
                                       'youda', 'rashii', 'souda', 'kamo', 'beki'}
    assert all(r['expect']['clauses'][0]['voice'] == 'active' for r in R9)


# the one row the base commit reads itself (the same output with no placement; a hole of its rules, not of a typed path: docs K68 / K77)
BASELINE_READS = {'W3B1-R9-S4-030'}

# the two rows that were read before the gate on a head that may be a derived verb (docs K63, table change record 3, review.r3.md M8) and are returned to abstain by it
# (the head is a shimo-ichidan verb); the output is fixed as it is (declared, not hidden), and without the gate the row is read correctly
RETURNED_BY_DERIVED_GATE = {
    'W3B1-R9-S4-001': ['NO_SUPPORTED_CLAUSE', 'PLACEMENT_PREDICATE_POSSIBLY_DERIVED:下一段-カ行'],
    'W3B1-R9-S4-006': ['NO_SUPPORTED_CLAUSE', 'PLACEMENT_PREDICATE_POSSIBLY_DERIVED:下一段-マ行'],
}


# W3-b1-5 (integration with W5-a): the row that BASELINE_READS says the base commit reads wrongly was read by the base commit 0ff3f35; after W5-a (docs section 10A K63) the base
# commit abstains on it (UNSUPPORTED_CLAUSE). BASELINE_READS is kept as it was (not deleted); this is asked before it. The W3-b1 tree before the merge (f410469) still reads it.
READ_BY_THE_BASE_ONLY_BEFORE_W5A = {'W3B1-R9-S4-030': ['UNSUPPORTED_CLAUSE']}
W3B1_COMMIT = 'f410469'


def _module_at(commit):
    src = subprocess.run(['git', '-C', str(TREE), 'show', '%s:verantyx/semantic_read.py' % commit], capture_output=True, check=True).stdout
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_at_%s_w3b1_i5' % commit, loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src.decode('utf-8'), 'verantyx/semantic_read.py@%s' % commit, 'exec'), mod.__dict__)
    return mod


@pytest.mark.parametrize('row', R9, ids=[r['id'] for r in R9])
def test_every_row_of_ja_r9_with_the_fixture(row):
    q = F.FixtureQuery()
    out = SR.read(row['input'], 'ja', placement=q)
    assert q.misses == [], q.misses
    plain = SR.read(row['input'], 'ja', placement=None)
    verdict = b1.judge(row['expect'], 'ja', out)['verdict']
    if row['id'] in READ_BY_THE_BASE_ONLY_BEFORE_W5A:
        assert row['entry_expect'] == 'abstain' and out == plain and out['readable'] is False
        assert out['abstain']['reasons'] == READ_BY_THE_BASE_ONLY_BEFORE_W5A[row['id']] and verdict == 'abstain'
        before = _module_at(W3B1_COMMIT).read(row['input'], 'ja', placement=F.FixtureQuery())
        assert before['readable'] is True and b1.judge(row['expect'], 'ja', before)['verdict'] == 'incomplete'
        return
    if row['id'] in BASELINE_READS:
        assert out == plain and out['readable'] is True and verdict == 'incomplete'
        return
    if row['id'] in RETURNED_BY_DERIVED_GATE:
        assert row['entry_expect'] == 'read'
        assert out['readable'] is False and out['abstain']['reasons'] == RETURNED_BY_DERIVED_GATE[row['id']], out
        saved = R.typed_head_derived_ja
        R.typed_head_derived_ja = lambda toks, clause: None
        try: without_gate = SR.read(row['input'], 'ja', placement=F.FixtureQuery())
        finally: R.typed_head_derived_ja = saved
        assert without_gate['readable'] is True and b1.judge(row['expect'], 'ja', without_gate)['verdict'] == 'correct'
        return
    assert verdict in ('correct', 'abstain'), (verdict, out['clauses'])         # never a wrong or half reading
    if row['entry_expect'] == 'read':
        assert out['readable'] is True and verdict == 'correct' and 'role_basis' in out['clauses'][0], (out['abstain'], out['clauses'])
    else:
        assert out['readable'] is False, out['clauses']


def test_every_second_reason_the_data_produces_is_registered_in_the_docs():
    registered = {re.split(r'[:\[<]', r[0])[0] for r in block('w3b1_reasons')}
    assert TAIL in registered
    seen = set()
    for row in R9:
        out = SR.read(row['input'], 'ja', placement=F.FixtureQuery())
        if not out['readable']: seen.update(x.split(':')[0] for x in out['abstain']['reasons'][1:] if x.startswith('PLACEMENT_'))
    assert TAIL in seen and seen <= registered, sorted(seen - registered)


def _nothing_new(mapper, label):
    for row in R9:
        plain = SR.read(row['input'], 'ja', placement=None)
        got = SR.read(row['input'], 'ja', placement=F.FixtureQuery(mapper=mapper))
        if plain['readable']: assert got == plain, (label, row['input'])
        else:
            assert got['readable'] is False and got['abstain']['reasons'][0] == plain['abstain']['reasons'][0], (label, row['input'], got['clauses'])


def test_estimated_and_multiple_answers_alone_read_nothing_new_in_ja_r9():
    _nothing_new(lambda a: F.to_estimated(a, 'proximity'), 'estimated_proximity')
    _nothing_new(lambda a: F.to_estimated(a, 'generated'), 'estimated_generated')
    _nothing_new(F.to_multiple, 'multiple')


def _base_module():
    src = subprocess.run(['git', '-C', str(TREE), 'show', '%s:verantyx/semantic_read.py' % BASE_COMMIT], capture_output=True, check=True).stdout
    spec = importlib.util.spec_from_loader('verantyx._semantic_read_base_w3b1_r3', loader=None)
    mod = importlib.util.module_from_spec(spec)
    mod.__package__ = 'verantyx'
    sys.modules[spec.name] = mod
    exec(compile(src.decode('utf-8'), 'verantyx/semantic_read.py@%s' % BASE_COMMIT, 'exec'), mod.__dict__)
    return mod


def test_without_a_placement_every_ja_r9_output_is_the_base_commits_output_byte_for_byte():
    base = _base_module()
    for row in R9:
        expect = json.dumps(base.read(row['input']), ensure_ascii=False)
        assert json.dumps(SR.read(row['input']), ensure_ascii=False) == expect, row['input']
        assert json.dumps(SR.read(row['input'], placement=None), ensure_ascii=False) == expect, row['input']
