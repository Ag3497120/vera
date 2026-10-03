"""W1-a 第 2 ラウンド: 第 1 ラウンドの門が測っていなかった下位形の門。各門に「誤読を落とす正例」と「正しい読みを残す負例」を 3 件以上。
文は評価バンク(ja/ja_r2/en/en_r2/a3/a3_r2/table7)の文とは別。判定は役割の型(時間・動作主・受け手・結果)で、文字列の決め打ちではない。"""
import re

import pytest

from verantyx import en_frames as en
from verantyx.semantic_reader import document_view
import verantyx.semantic_reader as R
import verantyx.semantic_verify as V


def supported(text):
    v = document_view({'d': text})
    return [c for c in v.clauses if not c.unsupported], v


def names(c):
    return {r.name: r.span.text for r in c.roles}


def role_pairs(text):
    return [names(c) for c in supported(text)[0]]


# ---- 1. a counted time (半・過ぎ・時間後・頃・日後・上旬) is a time, never a participant, goal or result ---------------------------------
@pytest.mark.parametrize('text,when', [('4時半に社員が部屋を出た。', '4時半'), ('6時過ぎに母が駅に着いた。', '6時過ぎ'),
                                       ('1時間後に医師が病院へ戻った。', '1時間後'), ('20分後に電車が駅を出た。', '20分後'),
                                       ('3月下旬に新入生が寮に入った。', '3月下旬')])
def test_gate_counted_time_is_read_as_time(text, when):
    cs, _ = supported(text)
    for c in cs:
        n = names(c)
        assert not any(v == when for k, v in n.items() if k != 'time'), n
    assert not cs or any(names(c).get('time') == when for c in cs)


@pytest.mark.parametrize('text', ['4時半に社員が部屋を出た。', '6時過ぎに母が駅に着いた。', '1時間後に医師が病院へ戻った。'])
def test_gate_counted_time_is_not_dropped_to_nothing(text):
    """the clause itself must survive (an agent and a time), not be thrown away by the gate"""
    cs, _ = supported(text)
    assert cs and 'time' in names(cs[0]) and 'agent' in names(cs[0])


# ---- 2. a noun the tagger calls 副詞可能 is a time only if it names a time ----------------------------------------------------------
@pytest.mark.parametrize('text', ['結局、叔父が店で靴を買った。', '実際、姉が駅で地図を見せた。', '以上、課長が会場で閉会を告げた。', '全部、弟が部屋で荷物を運んだ。'])
def test_gate_non_time_adverbial_noun_is_not_a_time(text):
    for c in supported(text)[0]:
        assert 'time' not in names(c), names(c)
        assert not re.search('結局|実際|以上|全部', ' '.join(v for k, v in names(c).items())), names(c)


@pytest.mark.parametrize('text,when', [('先週、叔父が会社で会議に出た。', '先週'), ('去年の秋、家族が山で茸を採った。', '去年の秋'),
                                       ('その日、姉が学校で転んだ。', 'その日'), ('当時、祖母が村で店を営んだ。', '当時')])
def test_gate_time_adverbial_before_a_comma_is_kept_as_time(text, when):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('time') == when and 'agent' in names(cs[0])


# ---- 3. a passive's に-phrase is an agent only if it can act ------------------------------------------------------------------------
@pytest.mark.parametrize('text', ['軒下に風鈴が吊るされた。', '塀の脇に標識が立てられた。', '床の間に花が活けられた。', '書類が社長に渡された。',
                                  '荷物が部長に届けられた。', '学校に建物が建てられた。'])
def test_gate_non_agent_ni_phrase_is_not_the_agent_of_a_passive(text):
    for c in supported(text)[0]:
        assert 'agent' not in names(c), names(c)


@pytest.mark.parametrize('text,agent', [('弟が兄に叱られた。', '兄'), ('犯人が警察に捕まえられた。', '警察'), ('選手が観客に励まされた。', '観客'),
                                        ('生徒が先生に教えられた。', '先生'), ('母親に呼ばれた。', '母親')])
def test_gate_person_ni_phrase_keeps_the_agent_of_a_passive(text, agent):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('agent') == agent


# ---- 4. a recipient is checked on every rule's clause, not only on the frame's ---------------------------------------------------------
@pytest.mark.parametrize('text', ['彼が部屋を青に塗った。', '弟が壁を灰色に塗った。', '祖母が襖を白に張り替えた。', '姉が爪を桃色に塗り直した。'])
def test_gate_result_colour_is_never_a_recipient_whichever_rule_reads_it(text):
    for c in supported(text)[0]:
        assert 'recipient' not in names(c), (c.rule, names(c))


@pytest.mark.parametrize('text,recipient', [('母が弟に切符を渡した。', '弟'), ('係員が客に鍵を見せた。', '客'), ('社長が部下に指示を伝えた。', '部下'),
                                            ('祖父が孫に小遣いをあげた。', '孫')])
def test_gate_real_recipients_are_kept_after_the_gate_moved(text, recipient):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('recipient') == recipient


# ---- 5. a verb of change / rescheduling with a time に-phrase: the time is the new value (result), not when it happened -------------
@pytest.mark.parametrize('text,value', [('部長が会議を3時に変更した。', '3時'), ('母が予定を月曜日に変えた。', '月曜日'),
                                        ('課長が会議を来週に延期した。', '来週'), ('先生が試験を翌日に繰り上げた。', '翌日')])
def test_gate_rescheduling_time_is_the_result(text, value):
    cs, _ = supported(text)
    for c in cs:
        assert 'time' not in names(c), names(c)
    assert not cs or names(cs[0]).get('result') == value


@pytest.mark.parametrize('text,when', [('10時に会議が始まった。', '10時'), ('3時に兄が駅に着いた。', '3時'), ('月曜日に試験が行われた。', '月曜日')])
def test_gate_ordinary_verb_keeps_its_time(text, when):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('time') == when


# ---- 6. a participant that is the predicate's own stem is not a participant ------------------------------------------------------------
@pytest.mark.parametrize('text', ['お世話になっております。', 'お世話になりました。', 'いつもお世話になっております。'])
def test_gate_participant_repeating_the_predicate_is_not_read(text):
    assert not supported(text)[0]


@pytest.mark.parametrize('text,patient', [('祖父が昔の歌を歌った。', '昔の歌'), ('友人が踊りを踊った。', '踊り'), ('母が夢を見た。', '夢')])
def test_gate_cognate_object_is_kept(text, patient):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('patient') == patient


# ---- 7. a bare two-item comma pair is not an enumeration ----------------------------------------------------------------------------------
@pytest.mark.parametrize('text', ['普通、叔母が台所で朝食を作る。', '基本、店員が店で商品を並べる。', '通常、職員が窓口で書類を受け取る。'])
def test_gate_bare_comma_pair_is_not_a_fused_agent(text):
    for c in supported(text)[0]:
        assert '、' not in names(c).get('agent', ''), names(c)


@pytest.mark.parametrize('text,agent', [('犬と猫が庭で遊んだ。', '犬と猫'), ('兄や弟が店で本を買った。', '兄や弟')])
def test_gate_conjoined_agents_are_kept(text, agent):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('agent') == agent


# ---- 8. the comparison dimension is a noun, never a degree adverb ------------------------------------------------------------------
@pytest.mark.parametrize('text', ['この道は川沿いの道よりずっと長い。', 'この車は前の車よりはるかに速い。', '兄は弟よりもっと重い。'])
def test_gate_degree_adverb_is_not_the_comparison_dimension(text):
    for c in supported(text)[0]:
        if c.rule == 'comparison':
            assert not any(r.name == 'dimension' and r.span.text in ('ずっと', 'はるかに', 'もっと') for r in c.roles)


@pytest.mark.parametrize('text,dim', [('東京は大阪より人口が多い。', '人口'), ('弟は兄より背が低い。', '背'), ('この橋は古い橋より幅が広い。', '幅')])
def test_gate_noun_dimension_is_kept(text, dim):
    cs, _ = supported(text)
    assert cs and cs[0].rule == 'comparison' and any(r.name == 'dimension' and str(r.term) == dim for r in cs[0].roles)


# ---- 9. an equative is not an identity sentence -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text', ['この部屋はあの部屋と同じくらい広い。', 'この川はあの川と同じぐらい長い。', 'この棚はその棚と同じほど高い。'])
def test_gate_equative_is_not_a_copula_identity(text):
    assert not any(c.rule == 'copula' for c in supported(text)[0])


# ---------------------------------------------------------------------------------------------------------------------
# English: the Frame states only what a Frame can hold.
# ---------------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize('text', ['Mia might send the invoice.', 'Ken could sign the form.', 'The server should crash.', 'Lisa must update the file.'])
def test_en_modal_verbs_are_not_read_as_events(text):
    assert en.read_typed(text)[0] is None


@pytest.mark.parametrize('text', ['The letter Paul wrote arrived late.', 'Mia liked the tool the team built.', 'Ken fixed the bug the tester found.'])
def test_en_reduced_relative_is_not_read(text):
    assert en.read_typed(text)[0] is None


@pytest.mark.parametrize('text', ['Ken signed the contract drafted by Lisa.', 'Mia read the email sent by the client.', 'Paul opened the window broken by the storm.'])
def test_en_postnominal_participle_is_not_read(text):
    assert en.read_typed(text)[0] is None


@pytest.mark.parametrize('text', ['Ken painted the room blue.', 'They elected Ken president.', 'Ken found the task easy.', 'Mia heard the alarm ringing.'])
def test_en_small_clause_and_perception_complement_are_not_read(text):
    assert en.read_typed(text)[0] is None


@pytest.mark.parametrize('text', ['Ken converted the file to PDF.', 'Mia turned the report into a slide deck.', 'Paul translated the letter into French.'])
def test_en_result_of_a_verb_of_change_is_not_a_recipient(text):
    f, why = en.read_typed(text)
    assert f is None and why


@pytest.mark.parametrize('text', ['Ken thinks the report is late.', 'Mia says the server crashed.', 'The report was long.', 'Ken is an engineer.'])
def test_en_embedded_clause_and_copula_are_not_read(text):
    assert en.read_typed(text)[0] is None


@pytest.mark.parametrize('text,key', [('Mia returned the book to Paul.', ('return', 'mia', 'book', 'paul', False)),
                                      ('The plan was approved by the board.', ('approv', 'board', 'plan', '', False)),
                                      ('Lisa did not answer the phone.', ('answer', 'lisa', 'phone', '', True)),
                                      ('Ken wrote Lisa a letter.', ('writ', 'ken', 'letter', 'lisa', False))])
def test_en_plain_sentences_are_still_read(text, key):
    f, why = en.read_typed(text)
    assert f is not None and en.key(f) == key and not why


def test_en_adjective_list_has_no_test_sentence_word_and_a_stated_criterion():
    """R8: the comparative stems come from general English (criterion in the comment above _ADJ_STEMS), not from the evaluation
    sentences; the two-word special case is gone."""
    import inspect
    assert 'crowded' not in en._ADJ_STEMS and 'red' not in en._ADJ_STEMS
    src = inspect.getsource(en)
    assert '["more", "quickly"]' not in src and '["less", "crowded"]' not in src


# ---------------------------------------------------------------------------------------------------------------------
# The reader and the checker keep their time-type rules apart; they must still agree.
# ---------------------------------------------------------------------------------------------------------------------
TIME_PHRASES = ['6時半', '3時過ぎ', '2時間後', '午後3時', '夜9時半', '数日後', '10日間', '2020年代', '3月上旬', '昭和30年', '5月5日', '3年前', '昼過ぎ',
                '夕方', '今朝', '先月', '翌日', '毎朝', '戦後', '晩年', '退局後', '会議前', '正午', '未明', '深夜', '週末', '休日', '今後', '最近', '当時',
                '将来', '以降', '昨夜', '明日', '来週末', '先日', '上旬', '年末', '前日', '去年', '数年前', '先週の金曜日', '昨年の秋', '会議の翌日',
                '子供の頃', '月曜日', 'その日', 'その朝', 'ある日', 'その後', '2025年春', '平日', '毎年', '同年', '3日目', '来月の初め', '試合の後', '手術の前', '試合中', '食事中', '閉館間際', '元日', '誕生日', '夏休み', '年明け', '週明け', '期末', '学期末', '月末', '年度末', '今年度', '来年度']
NON_TIME = ['結局', '実際', '一部', '以上', '全部', '駅前', '校舎前', '正門前', '駅の前', '前', '後', '上', '中', '時', '日本', '日常', 'ニケフォロス朝', '東京',
            '先生', '会議', '花壇', '机の上', '近く', '付近', '以外', '他', 'ため', '場合', '本来', '従来', '以来', '少年', '青年', '満月', '学年', '王朝',
            '机の前', '校舎の前', '月面', '結末', '文末', '粉末', '終末', '本当', '基本', '通常', '原則', '事実', '結果', '多く', '多数', '全員', 'すべて', '同時', '全体', '世界', '勉強', '3人', '3つ', '100円', '2倍']


@pytest.mark.parametrize('phrase', TIME_PHRASES + NON_TIME)
def test_reader_and_checker_agree_on_what_a_time_is(phrase):
    assert R._is_time_phrase(phrase) == V._vt_is_time(phrase), phrase


@pytest.mark.parametrize('phrase', TIME_PHRASES)
def test_time_phrases_are_time(phrase):
    assert R._is_time_phrase(phrase), phrase


@pytest.mark.parametrize('phrase', [p for p in NON_TIME if p != '日本の朝'])
def test_non_time_phrases_are_not_time(phrase):
    assert not R._is_time_phrase(phrase), phrase


@pytest.mark.parametrize('phrase', ['先月姉', '毎朝祖母', '2020年兄', '今朝、妹', '3時半先生'])
def test_reader_and_checker_agree_on_time_fused_phrases(phrase):
    assert R._time_fused(phrase) and V._vt_time_fused(phrase), phrase


def test_round2_class_lists_agree():
    assert set(R._TIME_WORDS) == set(V._VT_TIME_WORDS)
    assert set(R._TIME_FINAL_STEMS) == set(V._VT_FINAL_STEMS) and set(R._TIME_FINAL_WORDS) == set(V._VT_FINAL_WORDS)
    assert set(R._TIME_MORPHEMES) == set(V._VT_TIME_CHARS)
    assert set(R._SHARING_PREDICATES) == set(V._VT_SHARING_VERBS)
    assert set(R._CHANGE_PREDICATES) == set(V._VT_RESULT_VERBS)
    assert set(R._PERSON_NOUNS) == set(V._VT_PERSON_WORDS)


# ---------------------------------------------------------------------------------------------------------------------
# The checker re-derives these types itself: mutate a correct clause (round 2 sub-forms) and the checker must refuse it.
# ---------------------------------------------------------------------------------------------------------------------
from dataclasses import replace  # noqa: E402
from verantyx.semantic_ir import View  # noqa: E402
from verantyx.semantic_verify import license_clause, Rejected  # noqa: E402


def _correct(text, rule=None):
    v = document_view({'d': text})
    c = next(c for c in v.clauses if not c.unsupported and (rule is None or c.rule == rule))
    license_clause(c, v)
    return v, c


def _refused(v, c):
    with pytest.raises(Rejected):
        license_clause(c, View(v.sources, (c,), v.unread))


@pytest.mark.parametrize('new', ['goal', 'place', 'location', 'direction', 'agent', 'recipient', 'patient'])
def test_checker_rejects_a_counted_time_renamed_to_a_participant_or_adjunct(new):
    v, c = _correct('6時過ぎに母が駅に着いた。')
    _refused(v, replace(c, roles=tuple(replace(r, name=new) if r.name == 'time' else r for r in c.roles)))


def test_checker_rejects_the_new_value_of_a_change_renamed_to_time():
    v, c = _correct('部長が会議を3時に変更した。')
    _refused(v, replace(c, roles=tuple(replace(r, name='time') if r.name == 'result' else r for r in c.roles)))


def test_checker_rejects_a_new_value_that_is_a_time_for_a_verb_that_does_not_change_anything():
    v, c = _correct('母が予定を月曜日に変えた。')
    other = tuple(replace(r, name='goal') if r.name == 'result' else r for r in c.roles)
    _refused(v, replace(c, roles=other))


def test_checker_rejects_a_time_word_that_the_checker_does_not_know_as_time_when_it_is_renamed_to_agent():
    v, c = _correct('先週の金曜日に試験が行われた。')
    _refused(v, replace(c, roles=tuple(replace(r, name='agent') if r.name == 'time' else r for r in c.roles)))


def test_checker_rejects_a_passive_agent_that_is_a_person_swapped_into_the_patient_slot_of_a_thing():
    v, c = _correct('弟が兄に叱られた。')
    swap = {'agent': 'patient', 'patient': 'agent'}
    _refused(v, replace(c, roles=tuple(replace(r, name=swap.get(r.name, r.name)) for r in c.roles)))


def test_checker_rejects_a_recipient_that_is_a_result():
    v, c = _correct('画家が壁を白に塗り替えた。')
    _refused(v, replace(c, roles=tuple(replace(r, name='recipient') if r.name == 'result' else r for r in c.roles)))


# ---- 10. a passive's から-phrase that is only a place or a time is the origin/start, not the agent -------------------------------------
@pytest.mark.parametrize('text,origin', [('米が九州から運ばれた。', '九州'), ('苗が北海道から送られた。', '北海道'), ('部品が倉庫から運び出された。', '倉庫'),
                                         ('祭りが大阪から伝えられた。', '大阪')])
def test_gate_place_with_kara_is_the_source_not_the_agent_of_a_passive(text, origin):
    cs, _ = supported(text)
    assert cs and 'agent' not in names(cs[0]) and names(cs[0]).get('source') == origin


@pytest.mark.parametrize('text,agent', [('手紙が友人から届けられた。', '友人'), ('報告が担当者から提出された。', '担当者'), ('荷物が配達員から手渡された。', '配達員'),
                                        ('知らせが役所から通知された。', '役所')])
def test_gate_person_or_organisation_with_kara_keeps_the_agent_of_a_passive(text, agent):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('agent') == agent


@pytest.mark.parametrize('text', ['来月から新制度が導入された。', '4月から新制度が導入された。', '9時から会議が開催された。'])
def test_gate_time_with_kara_is_never_an_agent(text):
    for c in supported(text)[0]:
        assert 'agent' not in names(c) or not re.search('月|時', names(c)['agent']), names(c)


# ---- 11. an event noun + の後/前/中/間際 is a time; an animal can be an agent; an indirect passive's に-phrase is its agent -----------------
@pytest.mark.parametrize('text,when', [('試合の後、選手が監督に帽子を返した。', '試合の後'), ('食事中に電話が鳴った。', '食事中'),
                                       ('閉館間際に、警備員が返却箱を確かめた。', '閉館間際'), ('手術の前に、医師が患者に説明した。', '手術の前')])
def test_gate_event_noun_with_before_after_during_is_a_time(text, when):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('time') == when and not any(when in v for k, v in names(cs[0]).items() if k != 'time')


@pytest.mark.parametrize('text', ['駅の前に新しい売店が置かれた。', '机の前に小さな椅子が置かれた。', '校舎の前に記念碑が建てられた。'])
def test_gate_place_with_no_mae_is_not_a_time(text):
    for c in supported(text)[0]:
        assert 'time' not in names(c), names(c)


@pytest.mark.parametrize('text,agent', [('野菜が猿に食べられた。', '猿'), ('庭の花が虫に食べられた。', '虫'), ('魚が猫に盗まれた。', '猫')])
def test_gate_an_animal_can_be_the_agent_of_a_passive(text, agent):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('agent') == agent


@pytest.mark.parametrize('text,agent', [('患者は医師に検査の結果を説明された。', '医師'), ('板前は常連客に寿司を頼まれた。', '常連客'),
                                        ('生徒は先生に宿題を出された。', '先生')])
def test_gate_indirect_passive_of_a_transfer_verb_keeps_its_agent(text, agent):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('agent') == agent


@pytest.mark.parametrize('text', ['書類が社長に渡された。', '警察に通報された。', '荷物が部長に届けられた。'])
def test_gate_direct_passive_of_a_transfer_verb_has_a_recipient_not_an_agent(text):
    for c in supported(text)[0]:
        assert 'agent' not in names(c), names(c)


# ---- 12. a は-topic is not the patient of an intransitive verb -----------------------------------------------------------------------------
@pytest.mark.parametrize('text', ['実は、叔父が駅で友人に会った。', '駅は、兄が友人に会った。', '友人は、弟が駅で会った。', '本当は、姉が港に着いた。'])
def test_gate_topic_is_not_the_patient_of_an_intransitive_verb(text):
    for c in supported(text)[0]:
        assert 'patient' not in names(c), names(c)


@pytest.mark.parametrize('text,patient', [('資料Aは、花子が渡した。', '資料A'), ('手紙は、母が書いた。', '手紙'), ('手紙は母に読まれた。', '手紙'),
                                          ('財布は、弟が拾った。', '財布')])
def test_gate_topic_patient_of_a_transitive_verb_is_kept(text, patient):
    cs, _ = supported(text)
    assert cs and names(cs[0]).get('patient') == patient
