"""W1-a2 (round 6): the entry's 必須 2 (れる/られる of a person subject: passive or honorific) and 必須 3 (a capital letter is no evidence of a person),
and the third self-made B1 v2 sample.

必須 2  With a person as the subject, れる/られる is a passive and an honorific alike (先生が説明された: "the teacher explained"): the surface does not
        choose, so the voice is undecided. With a に/から phrase it is a passive only when the verb is of the closed class that takes no に/から
        phrase actively (W1-a3: _NI_KARA_FREE_PREDICATES); a によって phrase is a passive for any subject. (Round 6 also kept the passive for a subject
        that is not a person-phrase; W1-a3 withdrew that: a person owed respect may be missing from the person table, so only a subject headed by a
        noun that is never a person keeps it, see tests/test_semantic_read_r4.py.)
必須 3  A capital letter says "a name", not "a person" (Paris, London are written like Ann): the recipient after `to` and the subject of an
        intransitive verb need a pronoun or an animate noun; only the double-object form (V NP NP) makes the first object the recipient.

The third sample (tests/bank_score/fixtures/B1_v2_r3/items.jsonl, frozen in artifacts/w1-a/b1v2_r3_fixture_freeze.sha256) is written from the
convention before the entry was run on it, and carries `must_not` rows; every item must be valid and judged not a misreading.
"""
import json
from pathlib import Path

import pytest

from test_semantic_read import validate
from tools.bank_score.v2 import b1
from verantyx import semantic_read as SR

TREE = Path(__file__).resolve().parent.parent
FIXTURE3 = TREE / 'tests' / 'bank_score' / 'fixtures' / 'B1_v2_r3' / 'items.jsonl'
ITEMS3 = [json.loads(l) for l in FIXTURE3.read_text(encoding='utf-8').splitlines() if l.strip()]


def only_clause(text):
    out = SR.read(text)
    assert out['readable'] is True, out
    assert len(out['clauses']) == 1, out
    return out['clauses'][0]


def refusal(text):
    out = SR.read(text)
    assert out['readable'] is False and out['clauses'] == [] and out['relations'] == [], out
    return out['abstain']


# ---- the third sample ---------------------------------------------------------------------------------------------------------------------
def test_the_third_sample_has_the_planned_shape():
    assert len([i for i in ITEMS3 if i['lang'] == 'ja']) >= 10 and len([i for i in ITEMS3 if i['lang'] == 'en']) >= 6
    assert all(i['expect']['must_not'] for i in ITEMS3)


@pytest.mark.parametrize('item', ITEMS3, ids=[i['id'] for i in ITEMS3])
def test_every_third_sample_input_gets_a_valid_output_and_no_misreading(item):
    out = SR.read(item['input'])
    assert validate(out) == [], out
    verdict = b1.judge(item['expect'], item['lang'], {'readable': out['readable'], 'clauses': out['clauses'], 'relations': out['relations']})
    assert verdict['verdict'] not in ('misread', 'UNJUDGED'), (verdict, out)


# ---- 必須 2 -------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text', ['校長が紹介された。', '会長が挨拶された。', '教授が発表された。', '部長が連絡された。', '監督が指示された。'])
def test_a_person_subject_with_no_agent_phrase_is_a_passive_or_an_honorific_and_abstains(text):
    ab = refusal(text)
    assert ab['kind'] == 'not_supported' and any(r.startswith('UNDETERMINED_VOICE') for r in ab['reasons']), ab


@pytest.mark.parametrize('text', ['社長が部下に報告された。', '会長が秘書に相談された。', '教授が助手に説明された。', '校長が保護者に連絡された。'])
def test_a_person_subject_with_a_phrase_the_active_verb_takes_is_a_passive_or_an_honorific_and_abstains(text):
    ab = refusal(text)      # the voice rule or the reader itself (NO_SUPPORTED_CLAUSE) may be what stops it; a passive reading is never returned
    assert ab['kind'] == 'not_supported' and ab['reasons'], ab


@pytest.mark.parametrize('text,agent,patient', [('子どもが先生に叱られた。', '先生', '子ども'), ('選手が監督に褒められた。', '監督', '選手'),
                                                ('少年は兄に追いかけられた。', '兄', '少年')])
def test_a_phrase_the_active_verb_cannot_take_keeps_the_passive(text, agent, patient):
    c = only_clause(text)
    assert c['voice'] == 'passive' and c['roles'] == {'patient': patient, 'agent': agent}, c


@pytest.mark.parametrize('text', ['塀が壊された。', '窓が開けられた。', '荷物が運ばれた。', '木が倒された。'])
def test_a_subject_without_evidence_of_a_thing_abstains(text):
    # W1-a3 (H63): replaces test_a_subject_that_is_not_a_person_keeps_the_passive (the same four sentences, the opposite claim): "not known to be a person"
    # is no evidence of a thing. The passive that stays is the one of a subject headed by a noun that is never a person (test_semantic_read_r4, T6).
    ab = refusal(text)
    assert ab['kind'] == 'not_supported' and ab['reasons'] and all(r.startswith('UNDETERMINED_VOICE') for r in ab['reasons']), ab


def test_a_by_phrase_is_a_passive_for_any_subject():
    out = SR.read('社長が株主によって解任された。')
    assert out['readable'] is False or out['clauses'][0]['voice'] == 'passive', out


# ---- 必須 3 -------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text,place', [('Ann sent the parcel to Oslo.', 'Oslo'), ('Tom shipped the crate to Cairo.', 'Cairo'),
                                        ('The package was sent to Vienna.', 'Vienna'), ('Kate mailed the card to Lima.', 'Lima')])
def test_a_place_name_after_to_is_never_a_recipient(text, place):
    out = SR.read(text)
    assert out['readable'] is False or all(place not in c['roles'].values() or c['roles'].get('recipient') != place for c in out['clauses']), out


@pytest.mark.parametrize('text', ['Ann sent the parcel to Oslo.', 'The package was sent to Vienna.'])
def test_a_name_after_to_with_no_evidence_of_a_person_abstains(text):
    ab = refusal(text)
    assert any(r.startswith('RECIPIENT_TYPE_UNDETERMINED') for r in ab['reasons']), ab


@pytest.mark.parametrize('text,recipient', [('Mia sent Noah a card.', 'Noah'), ('Ben gave Lena the keys.', 'Lena')])
def test_the_first_object_of_a_double_object_clause_is_the_recipient_by_the_construction(text, recipient):
    assert only_clause(text)['roles']['recipient'] == recipient


@pytest.mark.parametrize('text,recipient', [('Ann sent the card to the teacher.', 'teacher'), ('Mia gave the keys to the doctor.', 'doctor')])
def test_an_animate_noun_after_to_is_still_a_recipient(text, recipient):
    assert only_clause(text)['roles']['recipient'] == recipient


@pytest.mark.parametrize('text', ['Ann walked.', 'Noah waited.', 'Lena worked.'])
def test_a_capitalised_name_alone_is_no_evidence_of_the_subject_of_an_intransitive_verb(text):
    ab = refusal(text)
    assert any(r.startswith('SUBJECT_TYPE_UNDETERMINED') for r in ab['reasons']), ab


@pytest.mark.parametrize('text,agent', [('Ann opened the window.', 'Ann'), ('Noah closed the door.', 'Noah')])
def test_the_subject_of_a_transitive_verb_is_still_an_agent(text, agent):
    assert only_clause(text)['roles']['agent'] == agent


# ---- the review's optional 2 and 3 (a path with を; a サ変 noun apart from its する) ----------------------------------------------------------
@pytest.mark.parametrize('text', ['子どもが橋を渡った。', '鳥が空を飛んだ。', '兄が山道を歩いた。', '選手が競技場を走った。'])
def test_the_path_of_a_motion_verb_is_never_called_the_thing_acted_on(text):
    ab = refusal(text)
    assert any(r.startswith('PATH_ROLE_NOT_MAPPED') for r in ab['reasons']), ab


# W5-a round 2 (auditor's decision B2; docs/READING_SOUNDNESS.md K63): READING_CONVENTIONS §9.2 (1) sets aside one rejected alternative
# reading only (a comparison read, the copula unsupported). The reader leaves these inputs with an unsupported clause for another reason
# (causative frame: causer/causee unresolved), so the entry does not read them and abstains with UNSUPPORTED_CLAUSE. The old expectations
# are kept in K63 in full.
W5A_R2_REVISED = {'先生が生徒に練習をさせた。': ['UNSUPPORTED_CLAUSE'], '母が子どもに勉強をさせた。': ['UNSUPPORTED_CLAUSE'],
                  '母が弟に皿を洗わせた。': ['UNSUPPORTED_CLAUSE']}


@pytest.mark.parametrize('text', ['先生が生徒に練習をさせた。', '母が子どもに勉強をさせた。', '兄が洗濯をした。'])
def test_a_sahen_noun_apart_from_its_suru_is_not_read_as_suru_with_an_object(text):
    ab = refusal(text)
    if text in W5A_R2_REVISED:
        assert ab['reasons'] == W5A_R2_REVISED[text], ab
        return
    assert any(r.startswith('PREDICATE_NOT_MAPPED') for r in ab['reasons']), ab


@pytest.mark.parametrize('text,predicate', [('兄が窓を開けた。', '開ける'), ('弟が本を読んだ。', '読む'), ('母が弟に皿を洗わせた。', '洗う')])
def test_an_ordinary_object_and_a_causative_of_an_ordinary_verb_are_still_read(text, predicate):
    if text in W5A_R2_REVISED:
        assert refusal(text)['reasons'] == W5A_R2_REVISED[text]
        return
    out = SR.read(text)
    assert out['readable'] is True and out['clauses'][0]['predicate'] == predicate, out
