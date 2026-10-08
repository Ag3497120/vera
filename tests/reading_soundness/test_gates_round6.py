"""W1-a2 (round 6): the review's必須 1 (a transitive verb with its object left out) and 必須 4 (a family name + 家), each as a gate with sentences
of the author's own.

R1  a verb that can be transitive (言い換える, 訳す, 翻訳する, 変える, ...) whose object is left out is NOT a clause with "no thing acted on": the に-phrase
    may be whoever the work is done for, so it is a `result` only on evidence of a result type. Only a verb with no transitive use (なる, 変わる,
    成長する, ...) takes a result with no evidence and no object;
R4  <family name> + 家 is "the people of the family" and "the house of the family": no evidence of a person (a common noun + 家 is a person in every
    sense and stays). The checker (semantic_verify) re-derives both with its own tokenization and constants; the mutation tests clear the reader's
    `unsupported` mark and require the checker to refuse on its own.

The words are not those of the banks, the reviews, or the earlier gate tests.
"""
from dataclasses import replace

import pytest

import verantyx.semantic_reader as R
import verantyx.semantic_verify as V
from verantyx.semantic_ir import View
from verantyx.semantic_reader import document_view
from verantyx.semantic_verify import Rejected, license_clause


def supported(text):
    v = document_view({'d': text})
    return [c for c in v.clauses if not c.unsupported], v


def names(c):
    return {r.name: r.span.text for r in c.roles}


def _any_role(text, name, value):
    return any(r.name == name and r.span.text == value for c in supported(text)[0] for r in c.roles)


# ---- the two lists (one meaning) -------------------------------------------------------------------------------------------------------------
def test_round6_class_lists_agree():
    assert set(R._INTRANSITIVE_CHANGE_PREDICATES) == set(V._VT_INTRANSITIVE_CHANGE_VERBS)
    assert set(R._INTRANSITIVE_CHANGE_PREDICATES) <= set(R._CHANGE_PREDICATES)
    # a verb with a transitive use is never in the class (the object may merely be left out): the verbs that the conversion class names
    assert not set(R._INTRANSITIVE_CHANGE_PREDICATES) & set(R._PROCESSING_PREDICATES)
    for verb in ('言い換える', '訳す', '翻訳する', '変える', '書き換える', '読み替える', '置き換える', '分類する', '縮小する', '拡大する', '転換する'):
        assert verb not in R._INTRANSITIVE_CHANGE_PREDICATES and verb not in V._VT_INTRANSITIVE_CHANGE_VERBS, verb
    assert set(R._HOUSE_SUFFIX_TOKENS) == {'家'}


# ---- R1 -----------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('predicate', ['言い換える', '訳す', '翻訳する', '変える', '書き換える', '置き換える', '分類する'])
def test_r1_the_rule_itself_a_transitive_verb_with_no_object_needs_evidence_of_a_result(predicate):
    assert R._result_ill_typed(predicate, '外国人', None, False) is not None
    assert V._vt_result_excluded(predicate, '外国人', None, False) is not None


@pytest.mark.parametrize('predicate', ['なる', '変わる', '成長する', '変化する', '進化する'])
def test_r1_a_verb_with_no_transitive_use_still_takes_a_result_without_an_object(predicate):
    assert R._result_ill_typed(predicate, '外国人', None, False) is None
    assert V._vt_result_excluded(predicate, '外国人', None, False) is None


@pytest.mark.parametrize('text,word', [('ガイドが外国人に言い換えた。', '外国人'), ('通訳者が来客に訳した。', '来客'),
                                       ('店主が常連に書き換えた。', '常連'), ('司書が子どもたちに読み替えた。', '子どもたち'),
                                       ('教授が志望者に翻訳した。', '志望者'), ('操縦士が整備士に置き換えた。', '整備士'),
                                       ('通訳者が家主に言い換えた。', '家主'), ('兄が弟に変えた。', '弟')])
def test_r1_a_person_after_a_transitive_verb_with_its_object_left_out_is_never_a_result(text, word):
    assert not _any_role(text, 'result', word)


@pytest.mark.parametrize('text', ['ガイドが外国人に言い換えた。', '通訳者が来客に訳した。', '店主が常連に書き換えた。'])
def test_r1_the_checker_refuses_the_result_on_its_own(text):
    v = document_view({'d': text})
    for c in v.clauses:
        undecided = [r for r in c.roles if r.name == 'ambiguous']
        if not undecided: continue
        renamed = replace(c, unsupported=(), roles=tuple(replace(r, name='result') if r.name == 'ambiguous' else r for r in c.roles))
        with pytest.raises(Rejected):
            license_clause(renamed, View(v.sources, (renamed,), v.unread))
        return
    pytest.fail('no undecided phrase: ' + text)


@pytest.mark.parametrize('text,result', [('妹は薬剤師になった。', '薬剤師'), ('弟は職人に成長した。', '職人'), ('姪は歌手に変わった。', '歌手'),
                                         ('彼女は園長になった。', '園長')])
def test_r1_a_change_of_the_subject_with_no_object_is_still_read(text, result):
    cs, _ = supported(text)
    assert any(names(c).get('result') == result for c in cs), [names(c) for c in cs]


@pytest.mark.parametrize('text,result', [('兄が議事録を仏語に訳した。', '仏語'), ('班長が名簿を四つの班に分類した。', '四つの班'), ('先生が答案を平仮名に書き換えた。', '平仮名')])
def test_r1_an_object_and_a_shown_result_type_are_still_read(text, result):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('result') == result, [names(c) for c in cs]


# ---- R4 -----------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('phrase', ['堀内家', '西村家', '中島家', '三浦家', '福田家'])
def test_r4_a_family_name_plus_house_is_not_shown_to_be_a_person(phrase):
    assert R._is_person_phrase(phrase) is False and V._vt_is_addressee(phrase) is False, phrase


@pytest.mark.parametrize('phrase', ['落語家', '実業家', '教育家', '陶芸家'])
def test_r4_a_common_noun_plus_house_is_still_a_person(phrase):
    assert R._is_person_phrase(phrase) is True and V._vt_is_addressee(phrase) is True, phrase


@pytest.mark.parametrize('text,word', [('額が西村家に飾られた。', '西村家'), ('提灯が堀内家に吊るされた。', '堀内家'), ('のぼりが三浦家に立てられた。', '三浦家')])
def test_r4_a_family_house_is_never_the_agent_of_a_passive(text, word):
    assert not _any_role(text, 'agent', word)


@pytest.mark.parametrize('text,word', [('額が西村家に飾られた。', '西村家'), ('提灯が堀内家に吊るされた。', '堀内家')])
def test_r4_the_checker_refuses_the_family_as_agent_on_its_own(text, word):
    v = document_view({'d': text})
    for c in v.clauses:
        target = next((r for r in c.roles if r.span.text == word), None)
        if target is None: continue
        renamed = replace(c, unsupported=(), roles=tuple(replace(r, name='agent') if r is target else r for r in c.roles))
        with pytest.raises(Rejected):
            license_clause(renamed, View(v.sources, (renamed,), v.unread))
        return
    pytest.fail('no clause names the family: ' + text)


@pytest.mark.parametrize('text,word', [('原稿が落語家に依頼された。', '落語家'), ('感想が実業家に求められた。', '実業家')])
def test_r4_a_common_noun_plus_house_is_still_an_agent(text, word):
    assert _any_role(text, 'agent', word) or not supported(text)[0]      # unsupported is also right; a wrong role is not
