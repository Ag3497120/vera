"""W1-a2 (round 5): the entry's M4 / M6 / M7 / M8 and the second self-made B1 v2 sample.

M4  a capital letter at the start of the input is no evidence of a name (Rain, Snow, Prices): an intransitive subject is `agent` only on a pronoun,
    an animate noun or a capitalised name that is not the first word;
M6  the place of existence / residence is `place`, never `goal` (convention 2, 4.2); an unshown place abstains;
M7  the predicate is the dictionary form of the verb WRITTEN (convention 3): the reader's converse (借りる -> 貸す ...) is never returned; もらう is
    the one restoration the convention states (4.6);
M8  `unreadable_input` needs positive evidence: a verb outside the closed list is `not_supported`, never "unreadable".

The second sample (tests/bank_score/fixtures/B1_v2_r2/items.jsonl, frozen in artifacts/w1-a/b1v2_r2_fixture_freeze.sha256) is written from the
convention, not from the entry's output, and carries `must_not` rows; every item must be valid and judged not a misreading.
"""
import json
from pathlib import Path

import pytest

from test_semantic_read import validate
from tools.bank_score.v2 import b1
from verantyx import semantic_read as SR

TREE = Path(__file__).resolve().parent.parent
FIXTURE2 = TREE / 'tests' / 'bank_score' / 'fixtures' / 'B1_v2_r2' / 'items.jsonl'
ITEMS2 = [json.loads(l) for l in FIXTURE2.read_text(encoding='utf-8').splitlines() if l.strip()]


def only_clause(text):
    out = SR.read(text)
    assert out['readable'] is True, out
    assert len(out['clauses']) == 1, out
    return out['clauses'][0]


def refusal(text):
    out = SR.read(text)
    assert out['readable'] is False and out['clauses'] == [] and out['relations'] == [], out
    return out['abstain']


# ---- the second sample --------------------------------------------------------------------------------------------------------------------
def test_the_second_sample_has_the_planned_shape():
    ja = [i for i in ITEMS2 if i['lang'] == 'ja' and i['expect']['readable']]
    en = [i for i in ITEMS2 if i['lang'] == 'en' and i['expect']['readable']]
    un = [i for i in ITEMS2 if not i['expect']['readable']]
    assert len(ja) >= 20 and len(en) >= 8 and len(un) >= 8, (len(ja), len(en), len(un))
    assert all(i['expect']['must_not'] for i in ITEMS2)


@pytest.mark.parametrize('item', ITEMS2, ids=[i['id'] for i in ITEMS2])
def test_every_second_sample_input_gets_a_valid_output_and_no_misreading(item):
    out = SR.read(item['input'])
    assert validate(out) == [], out
    if not item['expect']['readable']:
        assert out['readable'] is False, out
    verdict = b1.judge(item['expect'], item['lang'], {'readable': out['readable'], 'clauses': out['clauses'], 'relations': out['relations']})
    assert verdict['verdict'] not in ('misread', 'UNJUDGED'), (verdict, out)


# ---- M4 -----------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text', ['Fog lifted.', 'Wind howled.', 'Taxes increased.', 'Water dripped.'])
def test_m4_a_sentence_initial_capital_is_not_a_name(text):
    ab = refusal(text)
    assert ab['kind'] == 'not_supported'


@pytest.mark.parametrize('text,agent', [('Ann opened the window.', 'Ann'), ('The manager hired a clerk.', 'manager'), ('Dogs chased the cat.', 'Dogs')])
def test_m4_a_transitive_subject_is_still_an_agent(text, agent):
    assert only_clause(text)['roles']['agent'] == agent


@pytest.mark.parametrize('text', ['They worked.', 'She waited.', 'The dog walked.'])
def test_m4_a_pronoun_or_an_animate_noun_is_still_an_agent(text):
    assert 'agent' in only_clause(text)['roles']


def test_m4_the_first_object_of_a_double_object_clause_is_a_recipient_by_the_construction():
    # round 6: a capital letter says "a name", not "a person"; a name after `to` is no longer taken for a recipient (see test_semantic_read_r3.py),
    # but the double-object form itself says who receives
    assert only_clause('Cara sent Dev the report.')['roles']['recipient'] == 'Dev'


# ---- M6 -----------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text,place', [('叔母は京都に住んでいる。', '京都'), ('兄は大阪に滞在した。', '大阪')])
def test_m6_the_place_of_residence_is_place_not_goal(text, place):
    roles = only_clause(text)['roles']
    assert roles.get('place') == place and 'goal' not in roles, roles


@pytest.mark.parametrize('text', ['兄は夢に住んでいる。', '母は将来に滞在した。'])
def test_m6_a_residence_with_no_shown_place_abstains(text):
    out = SR.read(text)
    assert out['readable'] is False or 'goal' not in out['clauses'][0]['roles'], out


@pytest.mark.parametrize('text', ['妹が体育館へ行った。', '兄が病院に着いた。'])
def test_m6_the_end_point_of_motion_is_still_goal(text):
    assert 'goal' in only_clause(text)['roles']


# ---- M7 -----------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text', ['姉は妹から鞄を借りた。', '弟は兄から切符を受け取った。', '妹は先生に歌を習った。', '兄は店員から鍵を預かった。', '姉は友人から話を聞いた。'])
def test_m7_the_converse_of_the_written_verb_is_never_the_predicate(text):
    out = SR.read(text)
    assert out['readable'] is False or out['clauses'][0]['predicate'] not in ('貸す', '渡す', '教える', '預ける', '伝える'), out


def test_m7_the_refusal_names_the_normalization():
    ab = refusal('姉は妹から鞄を借りた。')
    assert any(r.startswith('PREDICATE_NORMALIZED') for r in ab['reasons']), ab


@pytest.mark.parametrize('text,predicate', [('姉は妹に鞄をもらった。', 'もらう'), ('弟は兄から時計を貰った。', '貰う')])
def test_m7_morau_keeps_its_own_name_with_the_roles_of_the_convention(text, predicate):
    c = only_clause(text)
    assert c['predicate'] == predicate and c['voice'] == 'active', c
    assert set(c['roles']) == {'agent', 'recipient', 'patient'}, c


def test_m7_morau_roles_are_the_giver_as_agent_and_the_subject_as_recipient():
    c = only_clause('姉は妹に鞄をもらった。')
    assert c['roles'] == {'agent': '妹', 'patient': '鞄', 'recipient': '姉'}, c


@pytest.mark.parametrize('text,predicate', [('叔母が妹に時計をくれた。', 'くれる'), ('兄が弟に本をあげた。', 'あげる'), ('先生が生徒に地図を渡した。', '渡す'),
                                            ('兄が窓を開けた。', '開ける'), ('犬が魚を食べた。', '食べる')])
def test_m7_a_verb_that_is_written_as_the_reader_names_it_is_unchanged(text, predicate):
    assert only_clause(text)['predicate'] == predicate


# ---- M8 -----------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text', ['Ann received a letter from Ben.', 'Cara learned a song.', 'Dev painted a fence.'])
def test_m8_a_verb_outside_the_closed_list_is_not_called_unreadable(text):
    out = SR.read(text)
    if out['readable'] is False:
        assert out['abstain']['kind'] == 'not_supported', out


@pytest.mark.parametrize('text', ['Thank you very much.', 'Oh!', 'Hello.', 'Wow, hey!'])
def test_m8_a_formula_or_an_interjection_is_still_unreadable_input(text):
    assert refusal(text)['kind'] == 'unreadable_input'


# ---- a proper name before a common noun ---------------------------------------------------------------------------------------------------
def test_two_names_in_a_row_are_not_one_noun_phrase():
    out = SR.read('Ann taught Ben French.')
    assert out['readable'] is False and any(r.startswith('NP_BOUNDARY_UNDETERMINED') for r in out['abstain']['reasons']), out


# ---- be + a participle that is also an adjective of a state ---------------------------------------------------------------------------
@pytest.mark.parametrize('text', ['The shop was closed.', 'The door was opened.', 'The work was finished.', 'The line was stopped.'])
def test_a_participle_that_is_also_a_state_adjective_has_no_decided_voice(text):
    ab = refusal(text)
    assert any(r.startswith('UNDETERMINED_VOICE') for r in ab['reasons']), ab


@pytest.mark.parametrize('text', ['The door was opened by Dev.', 'The report was approved.', 'Ben was hired by Ann.'])
def test_a_passive_with_a_by_phrase_or_a_plain_participle_is_still_a_passive(text):
    assert only_clause(text)['voice'] == 'passive'
