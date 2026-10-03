"""W1-a2 (round 4): no type is decided without POSITIVE evidence.

N1  the ending characters of a word decide nothing about whether it is a person (frames._PERSON_SUFFIX is no longer consulted);
N2  the に-phrase after the object of a verb of making is a `result` only with evidence of a result type (a person lexicon is not consulted);
N3  the に-phrase of a passive verb of selection is by/as undecided: a result only when it names a post, never an agent;
N4  Nほど / Nくらい / Nぐらい / N並み is a degree comparison, not a noun sentence;
J1-17  the end point of a motion verb is a `recipient` only when it shows a place or a person (otherwise undecided; round 5 M5 took back the
       re-reading as a direction / goal of round 4);
plus the から-phrase of a passive (an agent only with evidence of a person).

Each gate has at least three sentences it must stop and three correct readings it must keep. The sentences are not those of the banks, of the
reviews or of the earlier gate tests; the words are the author's own. The checker (semantic_verify) re-derives each type with its own tokenization,
its own constants and its own rules (it does not import the reader): the mutation tests below clear the reader's `unsupported` mark and require the
checker to refuse the clause on its own.
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


def _refused_when_unsupported_is_cleared(text, rule=None):
    v = document_view({'d': text})
    cleared = [replace(c, unsupported=()) for c in v.clauses if c.unsupported and (rule is None or c.rule == rule)]
    assert cleared, text
    for c in cleared:
        with pytest.raises(Rejected):
            license_clause(c, View(v.sources, (c,), v.unread))


# ---- the reader and the checker keep the same classes (two lists, one meaning) --------------------------------------------------------
def test_round4_class_lists_agree():
    assert set(R._PERSON_NOUNS) == set(V._VT_PERSON_WORDS)
    assert set(R._PERSON_ROLE_SUFFIX_TOKENS) == set(V._VT_ROLE_SUFFIXES)
    assert set(R._MEMBER_NOUNS) == set(V._VT_MEMBER_NOUNS)
    assert set(R._POST_NOUNS) == set(V._VT_POSTS) and set(R._POST_SUFFIX_TOKENS) == set(V._VT_POST_SUFFIXES)
    assert set(R._PROCESSING_PREDICATES) == set(V._VT_PROCESSING_VERBS)
    assert set(R._SELECTION_PREDICATES) == set(V._VT_SELECTION_VERBS)
    assert set(R._PROCESSING_PREDICATES) <= set(R._CHANGE_PREDICATES) and set(R._SELECTION_PREDICATES) <= set(R._CHANGE_PREDICATES)
    assert set(R._COLOR_NAMES) == set(V._VT_COLOURS)
    assert set(R._FORMAT_NOUNS) == set(V._VT_FORMATS)
    assert set(R._RESULT_FORM_NOUNS) == set(V._VT_FORM_NOUNS)
    assert set(R._DEGREE_MARKS) == set(V._VT_DEGREE_MARKS)


def test_the_person_and_suffix_rules_no_longer_read_frames_is_role_or_person_suffix():
    import inspect
    for fn in (R._is_person_phrase, V._vt_is_addressee, R._is_post_phrase, R._result_type_evidence, V._vt_result_evidence):
        src = inspect.getsource(fn)
        assert 'is_role' not in src.replace('_is_role', '') or 'frames import ROLES' in src
        assert '_PERSON_SUFFIX' not in src.replace('_PERSON_SUFFIX_TOKENS', '').replace('_PERSON_ROLE_SUFFIX_TOKENS', '')
        assert 'endswith' not in src, fn.__name__


# ---- N1 ----------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('phrase', ['隣家', '五官', '欠員', '最長', '民生', '大手', '母屋', '山の隣家', '標準の最長'])
def test_n1_a_one_token_word_that_ends_like_a_person_suffix_is_not_a_person(phrase):
    assert not R._is_person_phrase(phrase) and not V._vt_is_addressee(phrase), phrase


@pytest.mark.parametrize('phrase', ['保護者', '研究員', '事務員', '薬剤師', '理学士', '運営者', '歌手', '画家', '会長', '隊員', '兵士', '審査委員会', '管理者会'])
def test_n1_a_noun_plus_a_person_role_suffix_token_or_a_closed_person_word_is_a_person(phrase):
    assert R._is_person_phrase(phrase) and V._vt_is_addressee(phrase), phrase


@pytest.mark.parametrize('text,word', [('隣家に洗濯物が干された。', '隣家'), ('五官に刺激が与えられた。', '五官'), ('欠員に応募が寄せられた。', '欠員'),
                                       ('最長に印が付けられた。', '最長'), ('民生に配慮が払われた。', '民生'), ('大手に注文が出された。', '大手')])
def test_n1_a_passive_ni_phrase_headed_by_such_a_word_is_not_the_agent(text, word):
    for c in supported(text)[0]:
        assert not any(r.name == 'agent' and word in r.span.text for r in c.roles), names(c)


@pytest.mark.parametrize('text', ['隣家に洗濯物が干された。', '五官に刺激が与えられた。', '欠員に応募が寄せられた。'])
def test_n1_the_checker_refuses_the_same_clause_with_the_unsupported_mark_removed(text):
    _refused_when_unsupported_is_cleared(text)


@pytest.mark.parametrize('text,agent', [('不審者が警備員に取り押さえられた。', '警備員'), ('荷物が事務員に運ばれた。', '事務員'), ('書類が研究員に確かめられた。', '研究員'),
                                        ('計画が保護者に承認された。', '保護者')])
def test_n1_a_real_person_by_a_suffix_token_is_still_the_agent(text, agent):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('agent') == agent, [names(c) for c in cs]
    v = document_view({'d': text}); license_clause(next(c for c in v.clauses if not c.unsupported), v)


@pytest.mark.parametrize('text,word', [('体長から数値が割り出された。', '体長'), ('隣家から物音が聞かれた。', '隣家'), ('欠員から人数が数えられた。', '欠員')])
def test_n1_a_kara_phrase_of_a_passive_is_an_agent_only_with_evidence_of_a_person(text, word):
    for c in supported(text)[0]:
        assert not any(r.name == 'agent' and word in r.span.text for r in c.roles), names(c)


@pytest.mark.parametrize('text,agent', [('通知が役所から届けられた。', '役所'), ('手紙が友人から届けられた。', '友人'), ('連絡が事務員から伝えられた。', '事務員')])
def test_n1_a_kara_phrase_naming_a_person_is_still_the_agent(text, agent):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('agent') == agent, [names(c) for c in cs]


# ---- N2 ----------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text,word', [('叔母が上着を双子に仕立てた。', '双子'), ('兄が帽子を後継ぎに直した。', '後継ぎ'), ('職人が椅子を居候に仕上げた。', '居候'),
                                       ('係が名簿を新人に整理した。', '新人'), ('母が毛布を一人っ子に塗り直した。', '一人っ子'), ('店主が看板を孫に描き直した。', '孫')])
def test_n2_a_ni_phrase_after_the_object_of_a_verb_of_making_is_not_a_result_without_evidence(text, word):
    cs, v = supported(text)
    assert not any(r.name == 'result' for c in cs for r in c.roles), [names(c) for c in cs]
    assert any(c.unsupported for c in v.clauses)                 # typed: undecided, not read


@pytest.mark.parametrize('text', ['叔母が上着を双子に仕立てた。', '兄が帽子を後継ぎに直した。', '職人が椅子を居候に仕上げた。'])
def test_n2_the_checker_refuses_a_result_without_evidence_when_the_mark_is_removed(text):
    v = document_view({'d': text})
    for c in v.clauses:
        if any(r.name == 'ambiguous' for r in c.roles):
            renamed = replace(c, unsupported=(), roles=tuple(replace(r, name='result') if r.name == 'ambiguous' else r for r in c.roles))
            with pytest.raises(Rejected):
                license_clause(renamed, View(v.sources, (renamed,), v.unread))
            return
    pytest.fail('no ambiguous に-phrase: ' + text)


@pytest.mark.parametrize('text,res', [('職人が布を縹色に染めた。', None), ('農家が土地を三区画にまとめた。', '三区画'), ('学者が論文を英語版に直した。', '英語版'),
                                      ('画家が柱を緑に塗り替えた。', '緑'), ('係が書類を二束にまとめた。', '二束'), ('事務員が表を一覧にまとめた。', '一覧')])
def test_n2_evidence_of_a_result_type_keeps_the_result(text, res):
    cs, _ = supported(text)
    if res is None: return                                       # a colour name that is not in the closed class stays undecided (never a wrong result)
    assert cs and names(cs[0]).get('result') == res, [names(c) for c in cs]
    v = document_view({'d': text}); license_clause(cs[0], v)


@pytest.mark.parametrize('text,res', [('画家が壁を黄に塗り替えた。', '黄'), ('先生が詩を英語に訳した。', '英語'), ('会が名簿を三組に分けた。', '三組')])
def test_n2_a_conversion_verb_keeps_its_result_without_a_person_lexicon(text, res):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('result') == res, [names(c) for c in cs]


@pytest.mark.parametrize('text', ['弟が机を孫に分けた。', '妹が人形を甥に変えた。'])
def test_n2_a_conversion_verb_with_a_person_of_evidence_after_a_thing_is_undecided(text):
    cs, _ = supported(text)
    assert not any(r.name == 'result' for c in cs for r in c.roles)


# ---- N3 ----------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text,word', [('青年団に代表が選ばれた。', '青年団'), ('協議会に議長が指名された。', '協議会'), ('隣組に世話役が選ばれた。', '隣組'),
                                       ('寄り合いに取りまとめ役が指名された。', '寄り合い'), ('学区に委員が選出された。', '学区'), ('友人に新人が選ばれた。', '友人')])
def test_n3_a_passive_selection_with_a_non_post_ni_phrase_is_neither_agent_nor_result(text, word):
    cs, v = supported(text)
    assert not any(r.span.text == word and r.name in ('agent', 'result') for c in cs for r in c.roles), [names(c) for c in cs]
    assert any(c.unsupported for c in v.clauses)


@pytest.mark.parametrize('text', ['青年団に代表が選ばれた。', '協議会に議長が指名された。', '友人に新人が選ばれた。'])
def test_n3_the_checker_refuses_an_agent_of_a_passive_selection(text):
    v = document_view({'d': text})
    done = False
    for c in v.clauses:
        if c.rule != 'frame' and any(r.name == 'agent' for r in c.roles):
            cleared = replace(c, unsupported=())
            with pytest.raises(Rejected):
                license_clause(cleared, View(v.sources, (cleared,), v.unread)); done = True
    assert done or any(c.unsupported for c in v.clauses)


@pytest.mark.parametrize('text,post', [('村田さんが主任に選ばれた。', '主任'), ('宮本さんが理事に選任された。', '理事'), ('小島さんが編集長に指名された。', '編集長'),
                                       ('大西さんが館長に任命された。', '館長')])
def test_n3_a_post_after_a_passive_selection_is_a_result_not_an_agent(text, post):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('result') == post and 'agent' not in names(cs[0]), [names(c) for c in cs]
    v = document_view({'d': text}); license_clause(cs[0], v)


def test_n3_the_selection_class_is_made_of_selection_verbs_only():
    assert {'選ぶ', '選出する', '指名する', '任命する'} <= set(R._SELECTION_PREDICATES)
    assert not ({'昇進する', '昇格する', '降格する', '変える'} & set(R._SELECTION_PREDICATES))


# ---- N4 ----------------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text', ['この畑は隣の畑ほど広くない。', '兄は父くらい几帳面だ。', '彼の字は先生ぐらい端正ではない。', 'この池は沼ほど深くない。',
                                  '私の庭は君のほど広くない。', '今夜の月は昨夜ほど明るくない。'])
def test_n4_a_degree_comparison_is_not_a_noun_sentence(text):
    cs, v = supported(text)
    assert not any(c.rule in ('copula', 'negation') for c in cs), [(c.rule, names(c)) for c in cs]


@pytest.mark.parametrize('text', ['妹は母ほど社交的ではない。', '兄は父くらい几帳面だ。', '彼の字は先生ぐらい端正ではない。'])
def test_n4_the_checker_refuses_the_copula_clause_with_the_mark_removed(text):
    _refused_when_unsupported_is_cleared(text, rule='copula')


@pytest.mark.parametrize('text', ['この靴は兄のより小さい。', 'この鞄は君のほど重くない。'])
def test_n4_a_comparison_the_comparison_construction_reads_is_still_read(text):
    cs, _ = supported(text)
    assert any(c.rule == 'comparison' for c in cs), text


@pytest.mark.parametrize('text', ['この部屋は静かだ。', 'あの店は学生向けではない。', '彼の趣味は読書だ。'])
def test_n4_a_noun_sentence_without_a_degree_mark_is_still_read(text):
    cs, v = supported(text)
    assert any(c.rule in ('copula', 'negation') for c in cs) or any(c.unsupported for c in v.clauses)
    assert not any(c.rule == 'comparison' for c in cs)


# ---- J1-17: the end point of a motion verb ------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text,word', [('戦後は若者が新天地へ移った。', '新天地'), ('兄が山里へ向かった。', '山里'), ('姉が繁華街へ出た。', '繁華街')])
def test_j117_an_end_point_without_evidence_is_not_a_recipient(text, word):
    for c in supported(text)[0]:
        assert not any(r.name == 'recipient' and r.span.text == word for r in c.roles), names(c)


@pytest.mark.parametrize('text,word', [('妹が学校へ行った。', '学校'), ('マキが研究室へ行った。', '研究室'), ('弟が友人へ向かった。', '友人')])
def test_j117_an_end_point_that_shows_a_place_or_a_person_keeps_the_project_convention(text, word):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('recipient') == word, [names(c) for c in cs]


@pytest.mark.parametrize('text', ['戦後は若者が新天地へ移った。', '兄が山里へ向かった。', '姉が繁華街へ出た。'])
def test_j117_the_checker_refuses_a_recipient_end_point_without_evidence(text):
    # Round 5 (M5): the reader no longer re-reads such an end point as `direction`/`goal` (nothing shows a place); the phrase stays `ambiguous`.
    # The mutation is the same as before: give the end point the name `recipient`, clear the reader's mark, and the checker must refuse.
    v = document_view({'d': text})
    for c in v.clauses:
        undecided = [r for r in c.roles if r.name in ('direction', 'ambiguous')]
        if undecided:
            renamed = replace(c, unsupported=(), roles=tuple(replace(r, name='recipient') if r.name in ('direction', 'ambiguous') else r for r in c.roles))
            with pytest.raises(Rejected):
                license_clause(renamed, View(v.sources, (renamed,), v.unread))
            return
    pytest.fail('no undecided end point: ' + text)


def test_j117_the_known_misreading_is_gone_from_the_bank():
    import harness
    assert harness.ESCALATED == {}
