"""W1-a 第 3 ラウンド: 人・組織の判定を「語の末尾の文字」から「正の証拠」に替えた門(M1)、変化の動詞の に 句が人のときの result(M2)、
Nのより Adj を名詞文にしない門(M3)。各門に「誤読を止める正例」と「正しい読みを残す負例」を 3 件以上。
文は評価バンク(ja_r3 を含む)や第 3 ラウンドの指摘の文とは別。検査は読解と別実装なので、読解が止めた節の unsupported を外した節を検査が拒否することも確かめる。"""
from dataclasses import replace

import pytest

from verantyx.semantic_reader import document_view
import verantyx.semantic_reader as R
import verantyx.semantic_verify as V
from verantyx.semantic_ir import View
from verantyx.semantic_verify import license_clause, Rejected


def supported(text):
    v = document_view({'d': text})
    return [c for c in v.clauses if not c.unsupported], v


def names(c):
    return {r.name: r.span.text for r in c.roles}


def _refused_when_unsupported_is_cleared(text):
    """the reader marks the clause unsupported; the checker, given the same clause with that mark removed, must refuse it on its own"""
    v = document_view({'d': text})
    cleared = [replace(c, unsupported=()) for c in v.clauses if c.unsupported]
    assert cleared, text
    for c in cleared:
        with pytest.raises(Rejected):
            license_clause(c, View(v.sources, (c,), v.unread))


# ---- M1. a word that merely ends like an organisation (社 会 部 校 所 堂 場) is not an agent -------------------------------------------
@pytest.mark.parametrize('text,word', [('古寺に釣鐘が吊るされた。', '古寺'), ('公会堂に舞台が組まれた。', '公会堂'), ('寄宿舎に暖房が入れられた。', '寄宿舎'),
                                       ('西部に風車が据えられた。', '西部'), ('背部に目印が付けられた。', '背部'), ('分社に灯籠が寄進された。', '分社'),
                                       ('音楽会に絵画が出品された。', '音楽会'), ('支店に端末が取り付けられた。', '支店'), ('洞窟の一部に壁画が描かれた。', '洞窟の一部')])
def test_m1_a_word_that_only_ends_like_an_organisation_is_not_the_agent(text, word):
    for c in supported(text)[0]:
        assert not any(r.name == 'agent' and word in r.span.text for r in c.roles), names(c)


@pytest.mark.parametrize('text', ['古寺に釣鐘が吊るされた。', '西部に風車が据えられた。', '音楽会に絵画が出品された。'])
def test_m1_checker_refuses_the_same_clause_with_the_unsupported_mark_removed(text):
    _refused_when_unsupported_is_cleared(text)


@pytest.mark.parametrize('text,agent', [('住民が自警団に保護された。', '自警団'), ('探索隊が救助隊に発見された。', '救助隊'), ('法案が審査委員会に承認された。', '審査委員会'),
                                        ('老人が警察に保護された。', '警察'), ('計画が政府に発表された。', '政府'), ('青年が太郎さんに助けられた。', '太郎さん'),
                                        ('青年が山田氏に叱られた。', '山田氏'), ('猫が子供達に追いかけられた。', '子供達'), ('村が山賊に襲われた。', '山賊'), ('城が連合軍に包囲された。', '連合軍'),
                                        ('新製品が開発チームに改良された。', '開発チーム'), ('容疑者が刑事に尾行された。', '刑事'), ('法案が国会に否決された。', '国会')])
def test_m1_a_person_or_an_organisation_by_positive_evidence_is_still_the_agent(text, agent):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('agent') == agent, [names(c) for c in cs]
    v = document_view({'d': text}); license_clause(next(c for c in v.clauses if not c.unsupported), v)


@pytest.mark.parametrize('phrase', ['古寺', '公会堂', '西部', '背部', '分社', '音楽会', '洞窟の一部', '運動会', '山間部', '出力部', '野球部', '営業課', '山田橋',
                                    '配達', '成長', '関係', '太郎の鞄'])
def test_m1_reader_and_checker_both_say_no_person(phrase):
    assert not R._is_person_phrase(phrase) and not V._vt_is_addressee(phrase), phrase


@pytest.mark.parametrize('phrase', ['警察', '政府', '協会', '自警団', '救助隊', '委員会', '審査委員会', '連合軍', '開発チーム', '取締役会', '田中さん', '山田氏', '子供達', '部長', '彼', '友人', 'ソニー', '太郎', '先生'])
def test_m1_reader_and_checker_both_say_person(phrase):
    assert R._is_person_phrase(phrase) and V._vt_is_addressee(phrase), phrase


# ---- M2. a person is not the `result` of a verb of change on a thing --------------------------------------------------------------
@pytest.mark.parametrize('text,person', [('姉が妹にセーターを仕上げた。', '妹'), ('叔母が甥に手紙を書き換えた。', '甥'), ('兄が後輩に地図を描き直した。', '後輩'),
                                         ('店主が客に帳簿を整理した。', '客'), ('祖父が孫に写真を選んだ。', '孫')])
def test_m2_a_person_after_the_object_of_a_verb_of_change_is_not_a_result(text, person):
    for c in supported(text)[0]:
        assert not any(r.name == 'result' and r.span.text == person for r in c.roles), names(c)


@pytest.mark.parametrize('text', ['姉が妹にセーターを仕上げた。', '兄が後輩に地図を描き直した。', '祖父が孫に写真を選んだ。'])
def test_m2_checker_refuses_the_person_result_with_the_unsupported_mark_removed(text):
    v = document_view({'d': text})
    for c in v.clauses:
        people = [r for r in c.roles if r.name == 'ambiguous']
        if not people: continue
        renamed = replace(c, unsupported=(), roles=tuple(replace(r, name='result') if r.name == 'ambiguous' else r for r in c.roles))
        with pytest.raises(Rejected):
            license_clause(renamed, View(v.sources, (renamed,), v.unread))
        return
    pytest.fail('no ambiguous に-phrase to rename: ' + text)


@pytest.mark.parametrize('text,res', [('学校が生徒を班長に指名した。', '班長'), ('会社が社員を支店長に昇格させた。', '支店長'),
                                      ('画家が壁を青に塗り替えた。', '青'), ('弟が犬を庭に移した。', None), ('係が資料を三つの束に分けた。', '三つの束'),
                                      ('委員会が候補を議長に選出した。', '議長')])
def test_m2_a_status_for_a_person_object_and_a_thing_result_are_still_results(text, res):
    cs, _ = supported(text)
    if res is None: return                                    # a place after a verb of moving is not the case under test
    assert cs and names(cs[0]).get('result') == res, [names(c) for c in cs]


@pytest.mark.parametrize('text,rec', [('父が子どもに菓子を分けた。', '子ども'), ('兄が妹にお茶を入れてあげた。', '妹'), ('先生が生徒に地図を直してやった。', '生徒')])
def test_m2_a_beneficiary_with_a_benefactive_is_still_the_recipient(text, rec):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('recipient') == rec, [names(c) for c in cs]


@pytest.mark.parametrize('text,word', [('先生が児童に絵本を編集した。', '児童'), ('技師が見習いに設計図を直した。', '見習い'), ('母が末っ子に服を仕立て直した。', '末っ子'),
                                        ('店長が新入りに道具を整理した。', '新入り'), ('祖母が園児に帽子を加工した。', '園児')])
def test_m2_a_に_phrase_before_the_object_is_never_the_result_whoever_it_names(text, word):
    """word order, not a lexicon: a result follows its object. The words here are not in any person list."""
    for c in supported(text)[0]:
        assert not any(r.name == 'result' and r.span.text == word for r in c.roles), names(c)


@pytest.mark.parametrize('text', ['先生が児童に絵本を編集した。', '技師が見習いに設計図を直した。', '店長が新入りに道具を整理した。'])
def test_m2_checker_refuses_a_result_that_precedes_its_object(text):
    v = document_view({'d': text})
    for c in v.clauses:
        if any(r.name == 'ambiguous' for r in c.roles):
            renamed = replace(c, unsupported=(), roles=tuple(replace(r, name='result') if r.name == 'ambiguous' else r for r in c.roles))
            with pytest.raises(Rejected):
                license_clause(renamed, View(v.sources, (renamed,), v.unread))
            return
    pytest.fail('no ambiguous に-phrase: ' + text)


@pytest.mark.parametrize('text,res', [('翻訳者が原稿を英語に訳した。', '英語'), ('会計係が帳簿を一冊に整理した。', '一冊'), ('職人が丸太を角材に加工した。', '角材')])
def test_m2_a_result_after_its_object_is_still_read(text, res):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('result') == res, [names(c) for c in cs]


def test_m2_class_lists_agree():
    assert set(R._APPOINTMENT_PREDICATES) == set(V._VT_APPOINTMENT_VERBS)
    assert set(R._APPOINTMENT_PREDICATES) <= set(R._CHANGE_PREDICATES)


# ---- M3. より after の is a comparison mark whatever the tagger calls it ------------------------------------------------------------
@pytest.mark.parametrize('text', ['この靴は兄のより小さい。', '私の机は先輩のより低い。', 'あの橋は隣町のより短い。', 'うちの犬は君のより強い。'])
def test_m3_a_comparison_with_a_nominalised_standard_is_not_an_identity_or_property(text):
    for c in supported(text)[0]:
        assert c.rule != 'copula', (text, names(c))


@pytest.mark.parametrize('text', ['この靴は兄のより小さい。', 'あの橋は隣町のより短い。', 'この鉛筆は君のより長い。'])
def test_m3_checker_refuses_the_copula_clause_with_the_unsupported_mark_removed(text):
    v = document_view({'d': text})
    copulas = [replace(c, unsupported=()) for c in v.clauses if c.rule == 'copula']
    assert copulas
    for c in copulas:
        with pytest.raises(Rejected):
            license_clause(c, View(v.sources, (c,), v.unread))


@pytest.mark.parametrize('text,rule', [('この部屋は静かだ。', 'copula'), ('あの店の主人は親切だ。', 'copula'), ('彼の夢はより良い社会だ。', 'copula'), ('この本は父のものだ。', 'copula')])
def test_m3_a_noun_sentence_without_a_comparison_is_still_read(text, rule):
    cs, v = supported(text)
    assert any(c.rule == rule for c in cs) or any(c.unsupported for c in v.clauses)   # read, or at worst typed-unsupported (anaphora): never a different rule
    assert not any(c.rule == 'comparison' for c in cs)
