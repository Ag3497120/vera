"""W1-a3 (review.r3 必須 1): the entry says `passive` for れる/られる only on a POSITIVE piece of evidence.

The old rule took "not in a closed class" as evidence (a subject that is not a person-phrase cannot be honoured: the passive stands). A word the
tagger-side table does not know as a person (a person who is owed respect) is then read as a thing. The evidence is turned round:

  1a  a によって phrase                                                    -> passive
  1b  a に/から phrase, a verb of the closed class _NI_KARA_FREE_PREDICATES (a transitive verb that takes no に/から argument of its own in any
      sense), a transitive verb                                           -> passive; any other verb, whatever the subject: UNDETERMINED_VOICE
  2   no agent phrase, a transitive verb: られる (also the potential of an ichidan verb) -> abstain; a verb of the closed class
      _SPONTANEOUS_PREDICATES (れる/られる of thought and feeling is also spontaneous) -> abstain; a subject whose head is a noun of a closed class
      that is never a person (_not_person_evidence) -> passive; otherwise -> abstain (a thing without that evidence may be a person who is owed respect).

Every sentence below is written (from this rule, with words the author chose) BEFORE the entry was run on it; the file is frozen by
artifacts/w1-a/w1a3_tests_freeze.sha256. T1-T5, T7, T8 ask for an abstention; T6, T9, T10 ask for a passive.
W5-a round 2 (K62): T6 now asks for an abstention (UNDETERMINED_VOICE:passive or spontaneous); rule 2c above is withdrawn.
"""
import sys
from pathlib import Path

import pytest

from verantyx import semantic_read as SR
from verantyx import semantic_reader as R
from verantyx import frames

TREE = Path(__file__).resolve().parent.parent


def test_every_verantyx_module_comes_from_this_tree():
    mods = {n: m for n, m in sys.modules.items() if (n == 'verantyx' or n.startswith('verantyx.')) and getattr(m, '__file__', None)}
    assert mods, 'no verantyx module loaded'
    outside = sorted(n for n, m in mods.items() if TREE not in Path(m.__file__).resolve().parents)
    assert outside == [], (str(TREE), outside)


def refusal(text):
    out = SR.read(text)
    assert out['readable'] is False and out['clauses'] == [] and out['relations'] == [], out
    return out['abstain']


def abstains_on_voice(text):
    ab = refusal(text)
    assert ab['kind'] == 'not_supported', ab
    assert ab['reasons'] and all(r.startswith('UNDETERMINED_VOICE') for r in ab['reasons']), ab
    return ab


def only_clause(text):
    out = SR.read(text)
    assert out['readable'] is True, out
    assert len(out['clauses']) == 1, out
    return out['clauses'][0]


# T1: a subject that names a person who is owed respect, but that the person table does not know; no agent phrase
T1 = ['牧師が励まされた。', '神父が救助された。', '将軍が採用された。', '長老が呼び止められた。', '師範が勧誘された。']
# T2: the same kind of subject, a に/から phrase of a person, a verb outside the closed class
T2 = ['牧師が友人に励まされた。', '神父が警察に救助された。', '将軍が兄に採用された。', '長老が弟に追跡された。', '師範が部下から勧誘された。']
# T3: a person subject (known to the person table), a に/から phrase of a person, a verb outside the closed class
T3 = ['弟が兄に助けられた。', '客が店員に呼び止められた。', '友人が警察に救助された。', '部下が上司に励まされた。', '先輩が後輩から確認された。']
# T4: a thing as the subject, a に/から phrase of a person, a verb outside the closed class (transfer, delegation, request included).
# (First freeze: 切符が友人に送られた。 資金が団体から提供された。 調査が友人に依頼された。 鍵が弟に届けられた。 賞が選手に授与された。 The unchanged
# reader answers NO_SUPPORTED_CLAUSE to all five (a に-phrase of a transfer verb is not read as an agent at all), so the voice rule never sees them: they
# are kept below as T4X with the claim that is true of them. They were replaced here, before the voice rule was touched; see the judgement record H65.)
T4 = ['写真が姉から送られた。', '報告が部下から提出された。', '苦情が客から寄せられた。', '申請が兄に却下された。', '資料が友人から提供された。']
# T4X: the same kind of sentence with a に-phrase of a transfer verb: the reader itself does not read it; whatever is returned, it is never a passive
T4X = ['切符が友人に送られた。', '資金が団体から提供された。', '調査が友人に依頼された。', '鍵が弟に届けられた。', '賞が選手に授与された。']
# T5: a thing with no evidence that it is a thing, no agent phrase, a godan / suru verb
T5 = ['橋が撤去された。', '条例が廃止された。', '傘が回収された。', '計画が撤回された。']
# T6: the head of the subject is a noun of a closed class that is never a person; no agent phrase; a godan / suru verb outside the spontaneous class
T6 = ['倉庫が解体された。', '教室が改装された。', '要約が削除された。', '目次が更新された。', '海岸が閉鎖された。']
# T7: the same kind of subject, an ichidan verb + られる (the potential has the same form)
T7 = ['表が書き換えられた。', '要点が見つけられた。', '目次が書き換えられた。']
# T8: the same kind of subject, a verb of thought / feeling (れる is also spontaneous)
T8 = ['海岸が偲ばれた。', '倉庫が思い出された。', '要点が期待された。', '湖が想像された。']
# T9: a verb of the closed class + a に/から phrase of a person (the first one has a subject of the T1 kind)
T9 = [('妹が母に叱られた。', '母', '妹'), ('牧師が友人に褒められた。', '友人', '牧師'), ('子猫が犬に噛まれた。', '犬', '子猫'),
      ('後輩が先輩から叱られた。', '先輩', '後輩'), ('弟が友人に殴られた。', '友人', '弟')]
# T10: a によって phrase
T10 = ['候補者が党によって指名された。', '作家が出版社によって採用された。']


@pytest.mark.parametrize('text', T1)
def test_t1_a_subject_without_evidence_and_no_agent_abstains(text):
    abstains_on_voice(text)


@pytest.mark.parametrize('text', T2)
def test_t2_a_subject_of_the_unknown_person_kind_with_a_ni_phrase_abstains(text):
    abstains_on_voice(text)


@pytest.mark.parametrize('text', T3)
def test_t3_a_person_subject_with_a_ni_phrase_and_a_verb_outside_the_class_abstains(text):
    abstains_on_voice(text)


@pytest.mark.parametrize('text', T4)
def test_t4_a_thing_with_a_ni_or_kara_phrase_and_a_verb_outside_the_class_abstains(text):
    abstains_on_voice(text)


@pytest.mark.parametrize('text', T4X)
def test_t4x_a_ni_phrase_of_a_transfer_verb_is_never_returned_as_a_passive(text):
    out = SR.read(text)
    assert out['readable'] is False or all(c.get('voice') != 'passive' for c in out['clauses']), out


@pytest.mark.parametrize('text', T5)
def test_t5_a_thing_without_evidence_of_a_thing_abstains(text):
    abstains_on_voice(text)


@pytest.mark.parametrize('text', T6)
def test_t6_a_subject_headed_by_a_noun_that_is_never_a_person_keeps_the_passive(text):
    # W5-a round 2 (auditor's decision B1; docs/READING_SOUNDNESS.md K62): rule 2c (a passive on a non-person subject alone) is withdrawn.
    # A non-person subject rules out the honorific, not the spontaneous: the entry abstains. The old expectation is kept in K62 in full.
    ab = abstains_on_voice(text)
    assert ab['reasons'] == ['UNDETERMINED_VOICE:passive or spontaneous'], ab


@pytest.mark.parametrize('text', T7)
def test_t7_an_ichidan_verb_with_rareru_is_a_passive_or_a_potential_and_abstains(text):
    ab = abstains_on_voice(text)
    assert any('potential' in r for r in ab['reasons']), ab


@pytest.mark.parametrize('text', T8)
def test_t8_a_verb_of_thought_or_feeling_is_a_passive_or_a_spontaneous_and_abstains(text):
    ab = abstains_on_voice(text)
    assert any('spontaneous' in r for r in ab['reasons']), ab


@pytest.mark.parametrize('text,agent,patient', T9)
def test_t9_a_verb_that_takes_no_ni_phrase_of_its_own_keeps_the_passive(text, agent, patient):
    c = only_clause(text)
    assert c['voice'] == 'passive' and c['roles'] == {'patient': patient, 'agent': agent}, c


@pytest.mark.parametrize('text', T10)
def test_t10_a_by_phrase_is_a_passive_for_any_subject(text):
    out = SR.read(text)
    assert out['readable'] is False or out['clauses'][0]['voice'] == 'passive', out


# T11: no sentence; the closed classes and the evidence function
def test_t11_the_ni_kara_class_is_the_five_verbs_and_meets_no_class_of_the_reader():
    cls = SR._NI_KARA_FREE_PREDICATES
    assert cls == frozenset(('叱る', '褒める', '追いかける', '殴る', '噛む'))
    for name in ('_TRANSFER_PREDICATES', '_GOAL_PREDICATES', '_PLACEMENT_PREDICATES', '_LOCATION_PREDICATES', '_CHANGE_PREDICATES'):
        assert not (cls & getattr(R, name)), (name, sorted(cls & getattr(R, name)))
    assert all(frames.transitivity(v) == 'trans' for v in cls), {v: frames.transitivity(v) for v in cls}


def test_t11_the_spontaneous_class_is_apart_from_the_ni_kara_class_and_every_verb_is_in_the_dictionary_form():
    assert not (SR._SPONTANEOUS_PREDICATES & SR._NI_KARA_FREE_PREDICATES)
    assert SR._SPONTANEOUS_PREDICATES and all(isinstance(v, str) and v for v in SR._SPONTANEOUS_PREDICATES)


@pytest.mark.parametrize('phrase', ['先生', '社長', '弟', '友人', '部下', '警察', '山田さん', '店員'])
def test_t11_a_phrase_that_is_a_person_is_never_evidence_of_a_thing(phrase):
    assert R._is_person_phrase(phrase) is True
    assert SR._not_person_evidence(phrase) is False


@pytest.mark.parametrize('phrase', ['牧師', '神父', '橋', '条例', '傘', '計画', '子猫', ''])
def test_t11_a_noun_outside_the_closed_classes_is_no_evidence(phrase):
    assert SR._not_person_evidence(phrase) is False


@pytest.mark.parametrize('phrase', ['倉庫', '要約', '目次', '海岸', '駅の倉庫', '英語', '赤色', '総会'])
def test_t11_a_head_in_a_closed_class_that_is_never_a_person_is_evidence(phrase):
    assert SR._not_person_evidence(phrase) is True
