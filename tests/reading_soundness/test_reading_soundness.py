"""W1-a: 意味読解の健全性。評価文はファイル(ja/en/table7/a3.jsonl)から読む。ここに文を重複して書かない
(型の門の単体テストだけは、正例・負例を明示するため文をここに持つ。評価バンクの文とは別)。"""
import importlib.util
import json
import re
import sys
from dataclasses import replace
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location('w1a_harness', HERE / 'harness.py')
harness = importlib.util.module_from_spec(_spec); sys.modules['w1a_harness'] = harness; _spec.loader.exec_module(harness)

from verantyx import en_frames as en                                    # noqa: E402
from verantyx.semantic_ir import View                                    # noqa: E402
from verantyx.semantic_reader import document_view                       # noqa: E402
from verantyx.semantic_verify import license_clause, Rejected            # noqa: E402


def _items(name):
    return harness.load(name)


def _classify_all():
    rows = []
    for f in harness.JA_BANKS:
        rows += [harness.classify_ja(i, document_view, license_clause) for i in _items(f)]
    for f in harness.EN_BANKS:
        rows += [harness.classify_en(i, en) for i in _items(f)]
    return rows


ROWS = _classify_all()
SUMMARY = harness.summarize(ROWS)


def test_isolation_modules_are_under_the_tree():
    root, bad = harness.isolation_check()
    assert not bad, bad


def test_bank_is_large_enough():
    need = {'J1': 15, 'J2': 15, 'J3': 15, 'J4': 15, 'J5': 15, 'J6': 15, 'J7': 15, 'J8': 15, 'J9': 15,
            'E1': 8, 'E2': 8, 'E3': 8, 'E4': 8, 'E5': 8, 'E6': 8,
            # round 2 (ja_r2 / en_r2): sub-forms the first bank did not measure
            'K1': 6, 'K2': 5, 'K3': 6, 'K4': 5, 'K5': 3, 'K6': 4, 'F1': 4, 'F2': 4, 'F3': 4, 'F4': 4, 'F5': 4, 'F6': 4,
            # round 3 (ja_r3): the type of a に-phrase decides whether it can be an agent / a result
            'L1': 12, 'L2': 10, 'L3': 5}
    for t, n in need.items():
        assert SUMMARY[t]['n'] >= n, (t, SUMMARY[t])


def test_frozen_banks_are_unchanged():
    """The gold of every bank is frozen before it is first run (artifacts/w1-a/bank_freeze*.sha256). ja_r2/en_r2/a3_r2 are frozen as
    written; ja.jsonl is back to its frozen text (J1-17 was amended once and the amendment was reverted)."""
    import hashlib
    art = HERE.parent.parent / 'artifacts' / 'w1-a'
    expected = {}
    for name in ('bank_freeze.sha256', 'bank_freeze_r2.sha256', 'bank_freeze_r3.sha256'):
        f = art / name
        if not f.exists():
            pytest.skip('artifacts/w1-a not present')
        for line in f.read_text(encoding='utf-8').splitlines():
            if line.strip():
                digest, path = line.split()
                expected[Path(path).name] = digest
    for fname, digest in expected.items():
        assert hashlib.sha256((HERE / fname).read_bytes()).hexdigest() == digest, fname


_CHECKED = [r for r in ROWS if r['id'] not in harness.ESCALATED]


@pytest.mark.parametrize('row', _CHECKED, ids=[r['id'] for r in _CHECKED])
def test_no_misread_is_returned_as_supported(row):
    assert row['result'] != 'misread', (row['text'], row.get('clauses') or row.get('frame'))


def test_the_only_misread_is_the_escalated_exception():
    misread = {r['id'] for r in ROWS if r['result'] == 'misread'}
    assert misread <= set(harness.ESCALATED), misread - set(harness.ESCALATED)
    assert set(harness.ESCALATED) == {'J1-17'}


def test_no_clause_outside_the_gold_passes_the_checker():
    assert sum(r['false_pass'] for r in ROWS if r['id'] not in harness.ESCALATED) == 0


@pytest.mark.parametrize('t', [f'J{i}' for i in range(1, 10)] + ['K1', 'K4', 'K6'])
def test_japanese_types_are_mostly_read_not_just_refused(t):
    s = SUMMARY[t]
    assert 2 * s['correct'] >= s['n'], s


def test_english_controls_are_still_read():
    """F0: plain active/passive/ditransitive/negated sentences must still be read (the soundness layer abstains, it does not
    refuse everything)."""
    assert SUMMARY['F0']['correct'] == SUMMARY['F0']['n']


def test_english_regression_still_passes():
    assert en.regression()['all_pass'] is True


def test_english_simple_negation_and_active_sentences_are_still_read():
    assert SUMMARY['E0']['correct'] == SUMMARY['E0']['n']
    assert SUMMARY['E1']['correct'] >= 3


def test_a3_questions_do_not_answer_with_time_or_place():
    from verantyx.one import Vera
    for r in _items('a3.jsonl') + _items('a3_r2.jsonl') + _items('a3_r3.jsonl'):
        ans = Vera.from_texts({'d': r['text']}, mode='semantic').ask(r['question'])
        values = [str(v) for v in (ans.get('values') or [])]
        assert not any(f in v for f in r['forbidden'] for v in values), (r, ans.get('verdict'), values)


# ---------------------------------------------------------------------------------------------------------------------
# Gates: each has at least three sentences it must stop (not supported) and three correct readings it must keep.
# ---------------------------------------------------------------------------------------------------------------------
def supported(text):
    v = document_view({'d': text})
    return [c for c in v.clauses if not c.unsupported], v


def names(c):
    return {r.name: r.span.text for r in c.roles}


@pytest.mark.parametrize('text', ['1987年6月に議会で法案が可決された。', '1987年6月に工場で法案が可決された。', '午前3時に港で貨物が降ろされた。',
                                  '12時に作業員が倉庫で荷を積んだ。', '9時に授業が始まった。'])
def test_gate_time_phrase_is_never_an_event_participant(text):
    for c in supported(text)[0]:
        for r in c.roles:
            if r.name in ('agent', 'patient', 'recipient'):
                assert not re.search(r'[0-9０-９]', r.span.text), (r.name, r.span.text)


@pytest.mark.parametrize('text,agent', [('先生が校長に叱られた。', '校長'), ('犯人が警察に逮捕された。', '警察'),
                                        ('新しい法則が学者によって発見された。', '学者')])
def test_gate_time_phrase_keeps_real_passive_agents(text, agent):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('agent') == agent


@pytest.mark.parametrize('text', ['先月姉が書類を送った。', '昨年弟が学校で賞を取った。', '来週先生が教室で試験を行う。'])
def test_gate_time_word_fused_with_subject_is_not_read(text):
    assert not supported(text)[0]


@pytest.mark.parametrize('text,agent', [('先月、姉が書類を送った。', '姉'), ('昨年、弟が学校で賞を取った。', '弟'), ('来週、先生が試験を行う。', '先生')])
def test_gate_time_adverbial_before_a_comma_is_read_as_time(text, agent):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('agent') == agent and 'time' in names(cs[0])


@pytest.mark.parametrize('text', ['駅前に新しい売店が置かれた。', '市内に大きな塔が建てられた。', '広場に小さな像が造られた。'])
def test_gate_place_phrase_is_not_a_passive_agent(text):
    for c in supported(text)[0]:
        assert 'agent' not in names(c), names(c)


@pytest.mark.parametrize('text,agent', [('谷が山々に囲まれている。', '山々'), ('丘が川に囲まれている。', '川'), ('島が海に囲まれている。', '海')])
def test_gate_place_phrase_keeps_enclosing_agents(text, agent):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('agent') == agent


@pytest.mark.parametrize('text', ['課長が資料を図表に整理した。', '店員が箱を袋に分けた。', '職員が表を要点にまとめた。'])
def test_gate_conversion_target_is_a_result_not_a_recipient(text):
    cs, _ = supported(text)
    assert cs and 'recipient' not in names(cs[0]) and 'result' in names(cs[0])


@pytest.mark.parametrize('text,recipient', [('母が弟に切符を渡した。', '弟'), ('係員が客に鍵を見せた。', '客'), ('社長が部下に指示を伝えた。', '部下')])
def test_gate_real_recipients_are_kept(text, recipient):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('recipient') == recipient


@pytest.mark.parametrize('text', ['班長が隊員に壁を磨かせた。', '社長が部下に机を拭かせた。', '校長が生徒に庭を掃かせた。'])
def test_gate_causative_roles_are_causer_causee_patient(text):
    cs, _ = supported(text)
    assert cs and cs[0].rule == 'diathesis'
    assert {'causer', 'causee', 'patient'} <= set(names(cs[0]))


@pytest.mark.parametrize('text', ['先生が生徒を廊下に戻らせた。', '店主が店員を倉庫へ向かわせた。', '母が子供を庭に戻らせた。'])
def test_gate_intransitive_causative_is_not_read_as_causee_destination(text):
    assert not supported(text)[0]


@pytest.mark.parametrize('text', ['こんにちは。', 'おはようございます。', 'ありがとうございます。'])
def test_gate_greetings_are_not_propositions(text):
    assert not supported(text)[0]


@pytest.mark.parametrize('text,agent', [('雨が降った。', '雨'), ('犬が吠えた。', '犬'), ('鳥が鳴いた。', '鳥')])
def test_gate_short_clauses_with_a_participant_are_kept(text, agent):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('agent') == agent


@pytest.mark.parametrize('text', ['ありがとう。', 'こんにちは。', 'さようなら。'])
def test_gate_greeting_letters_are_not_a_copula_split(text):
    cs, v = supported(text)
    assert not cs and not any(c.rule == 'copula' for c in v.clauses)


@pytest.mark.parametrize('text,entity', [('この鍵は古い。', 'この鍵'), ('あの建物は高い。', 'あの建物'), ('その箱は軽い。', 'その箱')])
def test_gate_demonstrative_is_one_entity(text, entity):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('entity') == entity


@pytest.mark.parametrize('text', ['この橋はあの橋より長い。', '北の池は南の池より広い。', '兄の車は弟の車より速い。'])
def test_gate_comparison_is_not_an_attribute_sentence(text):
    cs, v = supported(text)
    assert not any(c.rule == 'copula' for c in cs)
    assert all(c.rule == 'comparison' for c in cs)


@pytest.mark.parametrize('text', ['彼は荷物を運ばないわけではない。', '兄は饅頭を食べないわけじゃない。', '母は手紙を書かなかったわけではない。'])
def test_gate_double_negation_is_not_an_identity(text):
    cs, _ = supported(text)
    assert not any(c.predicate == 'identity' for c in cs)


# ---------------------------------------------------------------------------------------------------------------------
# The checker is independent of the reader: mutate a correct clause and the checker must refuse it.
# ---------------------------------------------------------------------------------------------------------------------
def _clause(text, rule=None):
    v = document_view({'d': text})
    c = next(c for c in v.clauses if not c.unsupported and (rule is None or c.rule == rule))
    license_clause(c, v)           # the unmutated clause passes
    return v, c


def _check(v, c):
    v2 = View(v.sources, (c,), v.unread)
    with pytest.raises(Rejected):
        license_clause(c, v2)


def test_checker_rejects_time_phrase_renamed_to_agent():
    v, c = _clause('1987年6月に工場で法案が可決された。')
    _check(v, replace(c, roles=tuple(replace(r, name='agent') if r.name == 'time' else r for r in c.roles)))


def test_checker_rejects_time_phrase_as_recipient_of_an_active_clause():
    v, c = _clause('9時に授業が始まった。')
    _check(v, replace(c, roles=tuple(replace(r, name='recipient') if r.name == 'time' else r for r in c.roles)))


def test_checker_rejects_swapped_agent_and_patient():
    v, c = _clause('先生が校長に叱られた。')
    swap = {'agent': 'patient', 'patient': 'agent'}
    _check(v, replace(c, roles=tuple(replace(r, name=swap.get(r.name, r.name)) for r in c.roles)))


def test_checker_rejects_result_renamed_to_recipient():
    v, c = _clause('課長が資料を図表に整理した。')
    _check(v, replace(c, roles=tuple(replace(r, name='recipient') if r.name == 'result' else r for r in c.roles)))


def test_checker_rejects_reversed_comparison_direction():
    v, c = _clause('この橋はあの橋より長い。', rule='comparison')
    flipped = tuple(replace(r, term='less') if r.name == 'direction' else r for r in c.roles)
    _check(v, replace(c, roles=flipped))


def test_checker_rejects_changed_comparison_dimension():
    v, c = _clause('この橋はあの橋より長い。', rule='comparison')
    other = tuple(replace(r, term='重い') if r.name == 'dimension' else r for r in c.roles)
    _check(v, replace(c, roles=other))


def test_checker_rejects_an_entity_cut_inside_a_word():
    v, c = _clause('この鍵は古い。')
    cut = tuple(replace(r, term='こ', span=replace(r.span, end=r.span.start + 1, text='こ')) if r.name == 'entity' else r for r in c.roles)
    _check(v, replace(c, roles=cut))


def test_checker_rejects_causee_and_patient_swapped():
    v, c = _clause('班長が隊員に壁を磨かせた。', rule='diathesis')
    swap = {'causee': 'patient', 'patient': 'causee'}
    _check(v, replace(c, roles=tuple(replace(r, name=swap.get(r.name, r.name)) for r in c.roles)))


# ---------------------------------------------------------------------------------------------------------------------
# The reader and the checker keep their class lists separately (independence), so a change to one must be mirrored: a
# reader that keeps a role the checker excludes (or the reverse) turns a supported answer into INVALID_PROOF.
# ---------------------------------------------------------------------------------------------------------------------
def test_reader_and_checker_class_lists_agree():
    import verantyx.semantic_reader as R
    import verantyx.semantic_verify as V
    assert set(R._TRANSFER_PREDICATES) == set(V._VT_ADDRESSEE_VERBS)
    assert set(R._CHANGE_PREDICATES) == set(V._VT_RESULT_VERBS)
    assert set(R._PLACEMENT_PREDICATES) == set(V._VT_PLACEMENT_VERBS)
    assert set(R._PERSON_NOUNS) == set(V._VT_PERSON_WORDS)
    assert set(R._CONTAINMENT_PREDICATES) == set(V._VT_ENCLOSING_VERBS)
    assert set(R._BENEFACTIVE_VERBS) == set(V._VT_BENEFACTIVE)
    assert set(R._GOAL_PREDICATES | R._LOCATION_PREDICATES) <= set(V._VT_MOTION_VERBS) | set(V._VT_ADDRESSEE_VERBS)
