"""W1-a2 (round 5): the review's M1 / M2 / M3 / M5 (and a verb the tagger splits), each as a gate with sentences of the author's own.

M1  frames._LEARNED (katakana words the corpus put before a name: a list of frequent words, not of persons) is no evidence of a person;
M2  a に-phrase after the object of a verb of conversion is a `result` only on evidence of a result type: a person lexicon is no ground for it
    (a person that is in no list is not a result); a clause with no object (X は Y になる) and a verb of making a material into a product need none;
M3  the から-phrase of a passive is the agent, or the origin only when it names a spot / a named place: never `source` on no evidence;
M5  the end point of a verb of going is a goal / recipient only when it shows a place (or a gathering): a purpose / an activity is undecided;
M9  a verb the tagger splits (adjective stem + がる + られた) is not an identity sentence (a copula value with a verbal auxiliary and no copula).

The words are not those of the banks, the reviews, or the earlier gate tests. The checker (semantic_verify) re-derives each type with its own
tokenization and its own constants; the mutation tests clear the reader's `unsupported` mark and require the checker to refuse on its own.
"""
import inspect
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


def _refused_when_unsupported_is_cleared(text):
    v = document_view({'d': text})
    cleared = [replace(c, unsupported=()) for c in v.clauses if c.unsupported]
    assert cleared, text
    for c in cleared:
        with pytest.raises(Rejected):
            license_clause(c, View(v.sources, (c,), v.unread))


# ---- the lists the reader and the checker keep (two lists, one meaning) ------------------------------------------------------------------
def test_round5_class_lists_agree():
    assert set(R._LANGUAGE_NAMES) == set(V._VT_LANGUAGES)
    assert set(R._PRODUCT_PREDICATES) == set(V._VT_PRODUCT_VERBS) and set(R._PRODUCT_PREDICATES) <= set(R._CHANGE_PREDICATES)
    assert set(R._SPOT_NOUNS) == set(V._VT_SPOTS)
    assert set(R._GATHERING_NOUNS) == set(V._VT_GATHERINGS)
    assert set(R._GOAL_PREDICATES) == set(V._VT_GOAL_VERBS)
    from verantyx import frames
    assert set(R._ROLE_NOUNS) == set(V._VT_ROLE_NOUNS) == set(frames.ROLES) - {'農家'}      # the copy of frames.ROLES that leaves out the word that also names a building
    # the type-of-result rule: both lists of verbs are inside the verbs of change
    assert set(R._PROCESSING_PREDICATES) <= set(R._CHANGE_PREDICATES)


def test_no_person_rule_consults_the_learned_katakana_list():
    for fn in (R._is_person_phrase, V._vt_is_addressee):
        code = inspect.getsource(fn).split('"""', 2)[-1]          # the body, not the docstring that explains the removal
        assert '_LEARNED' not in code, fn.__name__


# ---- M1 -----------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('phrase', ['オルガン', 'ハープ', 'タブレット', 'スピーカー', 'シンセサイザー', 'ヴァイオリン', 'パリ', 'ロケット', '農家', 'お城のオルガン'])
def test_m1_a_katakana_word_is_not_shown_to_be_a_person(phrase):
    assert R._is_person_phrase(phrase) is False and V._vt_is_addressee(phrase) is False, phrase


@pytest.mark.parametrize('phrase', ['先生', '整備士', '運転手', '消防団', '子供達', '審査委員会', '看護師さん', '部長'])
def test_m1_real_persons_are_still_persons(phrase):
    assert R._is_person_phrase(phrase) is True and V._vt_is_addressee(phrase) is True, phrase


@pytest.mark.parametrize('text,word', [('オルガンに新しい鍵盤が付けられた。', 'オルガン'), ('ハープに弦が張られた。', 'ハープ'),
                                       ('タブレットに保護ガラスが貼られた。', 'タブレット'), ('スピーカーに布が掛けられた。', 'スピーカー'),
                                       ('ロケットに部品が取り付けられた。', 'ロケット')])
def test_m1_a_katakana_thing_is_never_the_agent_of_a_passive(text, word):
    assert not _any_role(text, 'agent', word)


@pytest.mark.parametrize('text', ['オルガンに新しい鍵盤が付けられた。', 'ハープに弦が張られた。', 'ロケットに部品が取り付けられた。'])
def test_m1_the_checker_refuses_the_thing_as_agent_on_its_own(text):
    v = document_view({'d': text})
    for c in v.clauses:
        agent_less = [r for r in c.roles if r.name != 'agent']
        # name the に-phrase `agent` (what the frame reader did before the type gate) and clear the reader's mark: the checker must refuse
        thing = next((r for r in c.roles if r.span.text in ('オルガン', 'ハープ', 'ロケット')), None)
        if thing is None: continue
        renamed = replace(c, unsupported=(), roles=tuple(replace(r, name='agent') if r is thing else r for r in c.roles))
        with pytest.raises(Rejected):
            license_clause(renamed, View(v.sources, (renamed,), v.unread))
        return
    pytest.fail('no clause names the thing: ' + text)


# ---- M2 -----------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text,word', [('店主が説明を幼なじみに言い換えた。', '幼なじみ'), ('祖父が話を曾孫に書き換えた。', '曾孫'),
                                       ('叔母が案内を甥っ子に訳した。', '甥っ子'), ('先輩が文面を教え子に読み替えた。', '教え子'),
                                       ('主任が通知を取引先に切り替えた。', '取引先'), ('母が献立を同居人に変えた。', '同居人')])
def test_m2_a_conversion_verb_with_a_phrase_that_shows_no_result_type_is_not_a_result(text, word):
    assert not _any_role(text, 'result', word)


@pytest.mark.parametrize('text', ['店主が説明を幼なじみに言い換えた。', '祖父が話を曾孫に書き換えた。', '先輩が文面を教え子に読み替えた。'])
def test_m2_the_checker_refuses_the_result_on_its_own(text):
    v = document_view({'d': text})
    for c in v.clauses:
        undecided = [r for r in c.roles if r.name == 'ambiguous']
        if not undecided: continue
        renamed = replace(c, unsupported=(), roles=tuple(replace(r, name='result') if r.name == 'ambiguous' else r for r in c.roles))
        with pytest.raises(Rejected):
            license_clause(renamed, View(v.sources, (renamed,), v.unread))
        return
    pytest.fail('no undecided phrase: ' + text)


@pytest.mark.parametrize('text,result', [('兄が議事録を仏語に訳した。', '仏語'), ('班長が名簿を四つの班に分類した。', '四つの班'),
                                         ('係員が書類を束に分けた。', '束'), ('職人が丸太を板に加工した。', '板'),
                                         ('先生が答案を平仮名に書き換えた。', '平仮名')])
def test_m2_a_conversion_into_a_shown_result_type_is_still_read(text, result):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('result') == result, [names(c) for c in cs]


@pytest.mark.parametrize('text,result', [('弟は研究者になった。', '研究者'), ('彼女は看護師になった。', '看護師'), ('兄は記者に変わった。', '記者')])
def test_m2_a_clause_with_no_object_has_only_one_thing_the_phrase_can_be(text, result):
    cs, _ = supported(text)
    assert any(names(c).get('result') == result for c in cs), [names(c) for c in cs]


def test_m2_the_language_names_have_a_criterion():
    # every entry of the class names a language / variety / script only (the docstring's criterion); none is a person or a place word
    for w in R._LANGUAGE_NAMES:
        assert not R._is_person_phrase(w) and not R._is_place_phrase(w), w


# ---- M3 -----------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text,word', [('製造元から部品が届けられた。', '製造元'), ('販売会社から案内が出された。', '販売会社'), ('現地事務所から報告が送られた。', '現地事務所'),
                                       ('支部から資料が配られた。', '支部'), ('開発部から仕様が示された。', '開発部'), ('運営委員から連絡が伝えられた。', '運営委員')])
def test_m3_a_from_phrase_of_a_passive_with_no_spot_evidence_is_never_the_source(text, word):
    assert not _any_role(text, 'source', word)


@pytest.mark.parametrize('text,word', [('製造元から部品が届けられた。', '製造元'), ('支部から資料が配られた。', '支部'), ('開発部から仕様が示された。', '開発部')])
def test_m3_the_checker_refuses_the_origin_on_its_own(text, word):
    v = document_view({'d': text})
    for c in v.clauses:
        undecided = [r for r in c.roles if r.name in ('ambiguous', 'source') and r.span.text == word]
        if not undecided: continue
        renamed = replace(c, unsupported=(), roles=tuple(replace(r, name='source') if r in undecided else r for r in c.roles))
        with pytest.raises(Rejected):
            license_clause(renamed, View(v.sources, (renamed,), v.unread))
        return
    pytest.fail('no from-phrase: ' + text)


@pytest.mark.parametrize('text,word', [('薪が森から運ばれた。', '森'), ('水が谷から引かれた。', '谷'), ('石が海岸から運び出された。', '海岸'), ('部品が神戸から送られた。', '神戸')])
def test_m3_an_origin_that_cannot_act_is_still_the_source(text, word):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('source') == word, [names(c) for c in cs]


@pytest.mark.parametrize('text,agent', [('友人から手紙が届けられた。', '友人'), ('先生から資料が配られた。', '先生'), ('兄から連絡が伝えられた。', '兄')])
def test_m3_a_person_is_still_the_agent_of_a_passive_from_phrase(text, agent):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('agent') == agent, [names(c) for c in cs]


# ---- M5 -----------------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text,word', [('兄は魚釣りに出かけた。', '魚釣り'), ('叔母は荷造りに戻った。', '荷造り'), ('祖父は昼食に向かった。', '昼食'),
                                       ('弟は日帰りに来た。', '日帰り'), ('先生は下見に出張した。', '下見'), ('姉は買い出しに通った。', '買い出し')])
def test_m5_a_purpose_is_neither_a_goal_nor_a_direction_nor_a_recipient(text, word):
    for c in supported(text)[0]:
        assert not any(r.span.text == word and r.name in ('goal', 'direction', 'recipient') for r in c.roles), names(c)


@pytest.mark.parametrize('text,word', [('姉が体育館へ行った。', '体育館'), ('父が病院に到着した。', '病院'), ('母が学校に通った。', '学校'),
                                       ('兄が授業に出かけた。', '授業'), ('弟が試合に向かった。', '試合')])
def test_m5_a_place_or_a_gathering_is_still_an_end_point(text, word):
    cs, _ = supported(text)
    assert cs and word in names(cs[0]).values(), [names(c) for c in cs]


@pytest.mark.parametrize('text,word', [('兄は魚釣りに出かけた。', '魚釣り'), ('叔母は荷造りに戻った。', '荷造り'), ('祖父は昼食に向かった。', '昼食')])
def test_m5_the_checker_refuses_the_purpose_as_a_recipient_or_goal_on_its_own(text, word):
    v = document_view({'d': text})
    for c in v.clauses:
        undecided = [r for r in c.roles if r.name == 'ambiguous' and r.span.text == word]
        if not undecided: continue
        for name in ('recipient', 'goal'):
            renamed = replace(c, unsupported=(), roles=tuple(replace(r, name=name) if r in undecided else r for r in c.roles))
            with pytest.raises(Rejected):
                license_clause(renamed, View(v.sources, (renamed,), v.unread))
        return
    pytest.fail('no undecided purpose: ' + text)


# ---- M9 (a verb the tagger splits) --------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text', ['同僚に子供が可愛がられた。', '上司に新人が恥ずかしがられた。', '隣人に子猫が欲しがられた。'])
def test_m9_a_split_verb_is_not_an_identity_of_two_nouns(text):
    for c in supported(text)[0]:
        assert c.rule != 'copula', (text, names(c))


@pytest.mark.parametrize('text', ['同僚に子供が可愛がられた。', '上司に新人が恥ずかしがられた。'])
def test_m9_the_checker_refuses_the_identity_on_its_own(text):
    v = document_view({'d': text})
    copulas = [replace(c, unsupported=()) for c in v.clauses if c.rule == 'copula']
    assert copulas
    for c in copulas:
        with pytest.raises(Rejected):
            license_clause(c, View(v.sources, (c,), v.unread))


@pytest.mark.parametrize('text', ['この部屋は静かだ。', '彼の趣味は読書だ。', '兄の仕事は医師です。'])
def test_m9_a_noun_sentence_with_its_copula_is_still_read(text):
    cs, v = supported(text)
    assert any(c.rule == 'copula' for c in cs) or any(c.unsupported for c in v.clauses)
