"""W5-a (H1-H4): rules of the reading entry that are checked with sentences that are NOT the attacker's and NOT in the frozen banks.

H1  れる/られる with no agent phrase is never `passive` (it is passive, spontaneous or honorific alike): a subject that is not a person rules
    out the honorific, not the spontaneous.
H2  a clause the reader left unsupported is set aside only by the one exception READING_CONVENTIONS §9.2 (1) writes down (a copula reading
    whose only reason is a predicate-phrase value, beside the comparison read from inside it); any other reason is a refusal. (Round 2,
    decision B2: round 1 had set aside two more reasons, a causative and 'unrepresented source content'; both are withdrawn.)
H3  a compound verb made of the closed class of verbs of going through a space, and an active clause with an を-phrase whose subject is shown not
    to be a person (or has no person evidence while the を-phrase has place evidence), are not given an agent / patient.
B3  (rounds 2-3) an active clause with an を-phrase whose subject has no person evidence is not read when the predicate is in none of the
    reader's closed classes with an を-object (the corpus transitivity table is not a source; auditor's decision B3 (β)): AGENT_EVIDENCE_MISSING.
H4  the English predicate is the dictionary form of the verb as written; no unique form -> abstain.
"""
from types import SimpleNamespace

import pytest

from verantyx import en_frames
from verantyx import semantic_read as SR


def read(text):
    return SR.read(text)


def reasons(text):
    out = read(text)
    assert out['readable'] is False and out['clauses'] == [] and out['relations'] == [], out
    return out['abstain']['reasons']


def only_clause(text):
    out = read(text)
    assert out['readable'] is True and len(out['clauses']) == 1, out
    return out['clauses'][0]


# ---- H1: no passive without the agent phrase's evidence -------------------------------------------------------------------------
@pytest.mark.parametrize('text', ['古い校舎が懐かしまれた。', '故郷の祭りが偲ばれた。', '亡き師の声が思い慕われた。',
                                  '若い日の夕焼けが回想された。', '遠い夏の浜辺が追想された。'])
def test_h1_a_recollection_with_no_agent_phrase_is_not_a_passive(text):
    out = read(text)
    assert not (out['readable'] and any(c['voice'] == 'passive' for c in out['clauses'])), out
    assert out['readable'] is False
    assert all(r.startswith(('UNDETERMINED_VOICE', 'UNKNOWN_PREDICATE_WORD', 'NO_SUPPORTED_CLAUSE', 'UNCOVERED_PREDICATE')) for r in out['abstain']['reasons']), out


@pytest.mark.parametrize('text', ['廊下が掃除された。', '地図が配布された。', '看板が撤去された。', '屋上が封鎖された。', '台所が改築された。'])
def test_h1_a_non_person_subject_alone_is_no_passive_evidence(text):
    r = reasons(text)
    assert r and all(x.startswith('UNDETERMINED_VOICE') for x in r), r


def test_h1_the_evidence_that_remains_still_gives_a_passive():
    # 1a: a によって phrase: a passive, or no reading at all (the reader leaves によって unread in many sentences; it is never another voice)
    out = read('橋が地震によって壊された。')
    assert out['readable'] is False or out['clauses'][0]['voice'] == 'passive', out
    # 1b: a に phrase and a verb of the closed class (_NI_KARA_FREE_PREDICATES)
    c = only_clause('弟が兄に叱られた。')
    assert c['voice'] == 'passive'


# ---- H2: an unsupported clause is set aside only by the one exception READING_CONVENTIONS §9.2 (1) writes down ---------------------
# (round 2, auditor's decision B2: the exemptions for a causative and for 'unrepresented source content' of round 1 are withdrawn; docs K63)
def test_h2_a_comparison_is_still_read_when_its_predicate_phrase_reason_is_answered_by_the_comparison():
    out = read('この公園は隣の公園より広い。')
    assert out['readable'] is True and out['clauses'][0].get('comparison') == 'comparative'
    assert [u['reasons'] for u in out['unsupported']] == [['copula value is a predicate phrase']]


def test_h2_a_causative_is_not_set_aside_the_input_is_not_read():
    for text in ('監督が選手に水を飲ませた。', '隊長が隊員に地図を読ませた。'):
        out = read(text)
        assert out['readable'] is False and out['abstain']['reasons'] == ['UNSUPPORTED_CLAUSE'], out
        assert any('causative frame: causer/causee unresolved' in u['reasons'] for u in out['unsupported']), out


def test_h2_unrepresented_content_is_not_set_aside_the_input_is_not_read():
    out = read('その学生が教室で歌を歌った。')
    assert out['readable'] is False and out['abstain']['reasons'] == ['UNSUPPORTED_CLAUSE'], out
    assert any('unrepresented source content' in u['reasons'] for u in out['unsupported']), out
    for text in ('弟は野菜を食べなくもない。', '姉は手紙を書かなくもない。'):
        assert reasons(text) == ['UNSUPPORTED_CLAUSE']


def test_h2_a_reason_beside_the_predicate_phrase_reason_is_never_set_aside():
    # 'unresolved anaphora' beside 'copula value is a predicate phrase': the second is the written exception, the first is not
    assert reasons('彼の鞄は私のより小さい。') == ['UNSUPPORTED_CLAUSE']


H2_SENTENCES = ['この公園は隣の公園より広い。', 'この川はあの川より長い。', '兄は弟より背が高い。', 'この机はあの机より重い。', '猫は犬ほど大きくない。',
                '祖父は祖母より早く起きた。', '彼の鞄は私のより小さい。', '監督が選手に水を飲ませた。', '隊長が隊員に地図を読ませた。',
                '先生が生徒に作文を書かせた。', '母が子どもに薬を飲ませた。', '店長が店員に床を拭かせた。', '母がパンを焼いた。', '配達員が荷物を届けた。',
                '店長が棚を掃除した。', '祖母が庭の草を抜いた。', '姉が手紙を出した。', '弟は野菜を食べなくもない。', '姉は手紙を書かなくもない。',
                '兄は酒を飲まなくもない。', '母が焼いたパンを弟が食べた。', '弟が書いた手紙を姉が読んだ。', 'その学生が教室で歌を歌った。',
                '祖父が畑で芋を掘った。', '弟は兄よりよく食べる。', '妹は姉より速く走った。']


def test_h2_invariant_a_readable_input_holds_only_the_written_exception_beside_a_comparison():
    readable = []
    for text in H2_SENTENCES:
        out = read(text)
        if not out['readable']: continue            # `readable: false` is not asked here
        readable.append(text)
        for u in out['unsupported']:
            assert u['reasons'] == ['copula value is a predicate phrase'], (text, out)
        if out['unsupported']:
            assert any(c.get('comparison') for c in out['clauses']), (text, out)
    assert len(H2_SENTENCES) >= 20 and len(readable) >= 8, readable     # the invariant was not met by reading nothing


# ---- H3: a path with を is not an object, and its subject is not given as an agent when it is shown not to be a person -------------
@pytest.mark.parametrize('text', ['少年が坂道を駆け下りた。', '犬が広場を走り回った。', '兵士が国境を通り抜けた。', '子どもが川を飛び越えた。'])
def test_h3_a_compound_verb_of_going_through_a_space_does_not_take_a_patient(text):
    r = reasons(text)
    assert len(r) == 1 and r[0].startswith('PATH_ROLE_NOT_MAPPED:'), r


def test_h3_the_compound_test_is_the_structure_of_the_word_not_a_list():
    for lemma in ('駆け下りる', '飛び越える', '走り回る', '通り抜ける', '練り歩く', '突っ走る'):
        assert SR._is_compound_path_verb(lemma) is True, lemma
    for lemma in ('焼く', '持ち上げる', '引き渡す', '受け取る', '食べる', '読み解く'):
        assert SR._is_compound_path_verb(lemma) is False, lemma
    assert SR._is_compound_path_verb('走る') is False      # a verb of the class itself is the class's own test


@pytest.mark.parametrize('text', ['庭が犬を見た。', '教室が机を持った。'])
def test_h3_a_subject_shown_not_to_be_a_person_is_not_called_an_agent(text):
    r = reasons(text)
    assert len(r) == 1 and r[0].startswith('SUBJECT_TYPE_UNDETERMINED:object or path:'), r


@pytest.mark.parametrize('text', ['機械が庭を掃いた。', '台風が畑を荒らした。'])
def test_h3_a_subject_with_no_person_evidence_and_a_place_with_を_is_not_called_an_agent(text):
    r = reasons(text)
    assert len(r) == 1 and r[0].startswith('SUBJECT_TYPE_UNDETERMINED:object or path:'), r


@pytest.mark.parametrize('text', ['母がパンを焼いた。', '配達員が荷物を届けた。', '店長が棚を掃除した。'])
def test_h3_a_person_with_an_ordinary_object_is_read_as_before(text):
    c = only_clause(text)
    assert set(c['roles']) == {'agent', 'patient'} and c['voice'] == 'active'


# ---- B3 (rounds 2-3): an を-phrase is the thing acted on only in a frame the reader's own closed classes know ----------------------------
from verantyx import frames
from verantyx import semantic_reader as R

B3_NO_FRAME = [('雨が屋根を降った。', '降る', '雨'), ('波が岸を上がった。', '上がる', '波'), ('煙が空を上がった。', '上がる', '煙'),
               ('雲が空をたなびいた。', 'たなびく', '雲'), ('気球が丘を下がった。', '下がる', '気球')]


@pytest.mark.parametrize('text,predicate,subject', B3_NO_FRAME)
def test_b3_a_subject_with_no_person_evidence_and_an_を_phrase_of_a_predicate_with_no_object_frame_is_not_read(text, predicate, subject):
    assert SR._object_frame_known(predicate, R) is False     # the premise: the predicate has no known frame with an を-object
    assert R._is_person_phrase(subject) is False
    assert reasons(text) == ['AGENT_EVIDENCE_MISSING:' + subject]


@pytest.mark.parametrize('text,predicate', [('少年が丘を上がった。', '上がる'), ('教師が階段を上がった。', '上がる'), ('患者が階段を降った。', '降る')])
def test_b3_the_same_predicates_with_a_person_subject_do_not_meet_this_rule(text, predicate):
    assert SR._object_frame_known(predicate, R) is False
    out = read(text)
    assert 'AGENT_EVIDENCE_MISSING' not in ' '.join((out['abstain'] or {}).get('reasons', [])), out


@pytest.mark.parametrize('text,predicate,subject', [('機械が部品を削った。', '削る', '機械'), ('嵐が小屋を壊した。', '壊す', '嵐')])
def test_b3_a_predicate_the_corpus_table_alone_calls_transitive_is_no_known_frame(text, predicate, subject):
    assert frames.transitivity(predicate) == 'trans'                        # the table says trans ...
    assert SR._object_frame_known(predicate, R) is False                    # ... and it is not a source: the reader's classes do not hold it
    assert R._is_person_phrase(subject) is False
    assert reasons(text) == ['AGENT_EVIDENCE_MISSING:' + subject]


def test_b3_the_same_predicates_with_a_person_subject_are_read_as_an_agent_and_a_patient():
    for text, predicate, subject in [('職人が部品を削った。', '削る', '職人'), ('職人が小屋を壊した。', '壊す', '職人')]:
        assert frames.transitivity(predicate) == 'trans' and SR._object_frame_known(predicate, R) is False
        assert R._is_person_phrase(subject) is True
        c = only_clause(text)
        assert c['predicate'] == predicate and set(c['roles']) == {'agent', 'patient'}


def test_b3_a_predicate_of_a_reader_class_is_read_with_a_subject_that_has_no_person_evidence():
    assert SR._object_frame_known('運ぶ', R) is True                        # 運ぶ is in a class of the reader
    assert R._is_person_phrase('機械') is False
    c = only_clause('機械が荷物を運んだ。')
    assert c['predicate'] == '運ぶ' and set(c['roles']) == {'agent', 'patient'}


@pytest.mark.parametrize('text,predicate', [('機械が荷物を保管した。', '保管する'), ('機械が装置を設置した。', '設置する')])
def test_b3_a_predicate_of_a_reader_class_with_an_を_object_is_a_known_frame_though_the_table_does_not_say_trans(text, predicate):
    assert frames.transitivity(predicate) != 'trans'
    assert SR._object_frame_known(predicate, R) is True
    c = only_clause(text)
    assert c['predicate'] == predicate and set(c['roles']) == {'agent', 'patient'}


def test_b3_object_frame_known_has_one_source_the_reader_classes():
    import inspect
    classes = (R._TRANSFER_PREDICATES, R._SHARING_PREDICATES, R._CHANGE_PREDICATES - R._INTRANSITIVE_CHANGE_PREDICATES, R._SELECTION_PREDICATES,
               R._PROCESSING_PREDICATES, R._PRODUCT_PREDICATES, R._CONTAINMENT_PREDICATES, R._PLACEMENT_PREDICATES)
    assert len(classes) == 8
    for cls in classes:                                                      # every word of the eight classes is a known frame
        assert cls and all(SR._object_frame_known(v, R) is True for v in sorted(cls))
    in_a_class = set().union(*classes)
    table_only = [v for v in ('削る', '壊す') if frames.transitivity(v) == 'trans' and v not in in_a_class]
    assert table_only == ['削る', '壊す']                                    # 'trans' in the corpus table, in no class: not a known frame
    assert all(SR._object_frame_known(v, R) is False for v in table_only)
    intrans = [v for v in sorted(R._INTRANSITIVE_CHANGE_PREDICATES) if v not in in_a_class]   # not narrowed by the table's value
    assert intrans and all(SR._object_frame_known(v, R) is False for v in intrans)
    assert SR._object_frame_known('あり得ない語', R) is False                # in no class
    assert list(inspect.signature(SR._object_frame_known).parameters) == ['predicate', 'R']   # the corpus table is not an argument


def test_b3_an_object_marked_with_は_is_not_an_を_phrase_and_does_not_meet_this_rule():
    text = '空は雲がたなびいた。'
    assert SR._object_frame_known('たなびく', R) is False
    out = read(text)
    assert 'AGENT_EVIDENCE_MISSING' not in ' '.join((out['abstain'] or {}).get('reasons', [])), out


# ---- H4: the English predicate is the dictionary form as written; a tie abstains ---------------------------------------------------
def test_h4_the_dictionary_form_comes_from_the_written_form():
    out = read('The door was painted by them.')
    assert out['readable'] is True and out['clauses'][0]['predicate'] == 'paint', out
    out = read('The fence was mended by them.')       # not in the closed list: not read, and not read as another word
    assert out['readable'] is False


def test_h4_two_known_verbs_with_the_same_written_form_are_a_tie():
    known = {'hire', 'hir'}
    frame = SimpleNamespace(predicate='hire', ambiguous=False, inferred=False, agent='them', patient='chair', recipient=None, negated=False)
    text = 'The chair was hired by them.'
    words = SR._en_words(text)
    low = [w.lower() for w in words]
    assert {v for v in known if 'hired' in SR._en_inflections(v, SR._en_irregular_table())} == {'hire', 'hir'}
    with pytest.raises(SR._Abstain) as stop:
        SR._clause_en(text, words, low, frame, known, set(en_frames.AUX), en_frames)
    assert stop.value.reason == 'PREDICATE_FORM_UNDETERMINED:hired:hir,hire'


def test_h4_with_one_candidate_the_form_is_taken():
    known = {'hire'}
    frame = SimpleNamespace(predicate='hire', ambiguous=False, inferred=False, agent='them', patient='chair', recipient=None, negated=False)
    text = 'The chair was hired by them.'
    words = SR._en_words(text)
    low = [w.lower() for w in words]
    clause, meta = SR._clause_en(text, words, low, frame, known, set(en_frames.AUX), en_frames)
    assert clause['predicate'] == 'hire' and clause['voice'] == 'passive'
