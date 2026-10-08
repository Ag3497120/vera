"""W5-e (docs/OBSERVATION.md, W5-e A-1): a candidate of AGREE next to a candidate that was not checked is not an answer.

When the fillers of the hole of the matched crosses hold at least one whose type AGREES with the hole and at least one that cannot be checked
(`TYPE_UNCHECKED`: UNPLACED, UNKNOWN, an estimate, a MULTIPLE with a type outside the hole, no placement for it), the answer is not FILLED / TIE but the
typed abstention `INCOMPLETE_TYPING` (the candidates and the exclusions are both returned; nothing is given as the answer). Agreeing candidates with only
disagreeing ones next to them, which+N, and the extending crosses are unchanged.
"""
import json

import pytest

from verantyx import observe as O

from test_question_cross_observe import Q_SHIP, S1, S2, ask, fills
from test_question_cross_w5d import ask_en, ask_ja_doc, excluded, write_pl

S3 = '将軍が商人に小包を渡した。'          # general ... (a third name for the same cross)


def _no_answer_given(out):
    """The abstention carries no element, no focus cell, no rank: nothing is given as an answer."""
    assert out['ranks'] == [] and out['focus'] == {'kind': 'NO_MOVE_LICENSED'}


# ---------------------------------------------------------------------------------------------------------------------------------
# the hit: one direct, one not placed
# ---------------------------------------------------------------------------------------------------------------------------------
def test_a1_one_direct_witness_and_one_unplaced_witness_is_incomplete_typing(tmp_path):
    pl = write_pl(tmp_path, {'船長': ('DECIDED', 'direct', ['PERSON']), '提督': ('UNPLACED', None, [])})
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=pl)
    a = out['answer']
    assert a['status'] == 'INCOMPLETE_TYPING'
    assert [f['surface'] for f in a['fillers']] == ['船長'] and excluded(out) == [('提督', 'TYPE_UNCHECKED')]       # both are returned
    assert a['reasons'][0] == 'INCOMPLETE_TYPING'
    assert out['abstain'] == {'type': 'NO_MOVE_LICENSED', 'reasons': {'FILL_HOLE:INCOMPLETE_TYPING': 1}}
    _no_answer_given(out)


@pytest.mark.parametrize('name,spec', [('est', ('DECIDED', 'estimated', ['PERSON'], 'proximity')), ('gen', ('DECIDED', 'estimated', ['PERSON'], 'generated')),
                                       ('unp', ('UNPLACED', None, [])), ('unk', ('UNKNOWN', None, [])),
                                       ('multi', ('MULTIPLE', 'direct', ['ARTIFACT', 'PERSON']))])
def test_a1_every_way_of_not_being_checked_makes_the_agreeing_one_incomplete(tmp_path, name, spec):
    pl = write_pl(tmp_path, {'船長': 'PERSON', '提督': spec}, name + '.json')
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=pl)
    assert out['answer']['status'] == 'INCOMPLETE_TYPING', name
    assert [f['surface'] for f in out['answer']['fillers']] == ['船長'] and excluded(out) == [('提督', 'TYPE_UNCHECKED')]
    _no_answer_given(out)


def test_a1_a_word_that_is_not_in_the_placement_at_all_is_unchecked_too(tmp_path):
    pl = write_pl(tmp_path, {'船長': 'PERSON'})                                    # 提督 is not in the file: UNKNOWN
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=pl)
    assert out['answer']['status'] == 'INCOMPLETE_TYPING'


def test_a1_two_agreeing_candidates_and_an_unchecked_one_are_incomplete_not_a_tie(tmp_path):
    pl = write_pl(tmp_path, {'船長': 'PERSON', '提督': 'PERSON', '将軍': ('UNPLACED', None, [])})
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2, S3], placement=pl)
    a = out['answer']
    assert a['status'] == 'INCOMPLETE_TYPING' and sorted(f['surface'] for f in a['fillers']) == ['提督', '船長']
    assert excluded(out) == [('将軍', 'TYPE_UNCHECKED')]
    _no_answer_given(out)


def test_a1_the_order_of_the_sentences_does_not_matter(tmp_path):
    pl = write_pl(tmp_path, {'船長': 'PERSON', '提督': ('UNPLACED', None, [])})
    a, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=pl)
    b, _ = ask(tmp_path, Q_SHIP, [S2, S1], placement=pl)
    assert a['answer']['status'] == b['answer']['status'] == 'INCOMPLETE_TYPING'
    assert [f['surface'] for f in a['answer']['fillers']] == [f['surface'] for f in b['answer']['fillers']]
    assert [(e['surface'], e['reason']) for e in a['answer']['excluded']] == [(e['surface'], e['reason']) for e in b['answer']['excluded']]


def test_a1_the_same_in_english_the_rule_does_not_depend_on_the_language(tmp_path):
    pl = write_pl(tmp_path, {'letter': 'PERSON'})                                # `note` is not placed: unchecked
    out = ask_en('Who did the girl write?', 'EN08', pl)
    assert out['answer']['status'] == 'INCOMPLETE_TYPING'
    assert [f['surface'] for f in out['answer']['fillers']] == ['letter'] and excluded(out) == [('note', 'TYPE_UNCHECKED')]


def test_a1_the_time_adverb_fused_with_its_noun_next_to_two_checked_nouns(tmp_path):
    pl = write_pl(tmp_path, {'本': 'ARTIFACT', '新聞': 'ARTIFACT'})
    out = ask_ja_doc('花子は何を読んだ？', 'JA02', pl)
    a = out['answer']
    assert a['status'] == 'INCOMPLETE_TYPING' and {f['surface'] for f in a['fillers']} == {'本', '新聞'}
    assert excluded(out) == [('毎日本', 'TYPE_UNCHECKED')]
    _no_answer_given(out)


def test_a1_incomplete_typing_comes_before_incomplete_by_extension(tmp_path):
    pl = write_pl(tmp_path, {'提督': 'PERSON', '船長': 'PERSON', '将軍': ('UNPLACED', None, [])})
    docs = ['提督は小包を渡さなかった。', '将軍は小包を渡さなかった。', '船長は港で小包を渡さなかった。']          # 船長: an extending cross (an extra arm), a candidate not seen in the matches
    out, _ = ask(tmp_path, '誰が小包を渡さなかった？', docs, placement=pl)
    a = out['answer']
    assert a['status'] == 'INCOMPLETE_TYPING' and a['reasons'][0] == 'INCOMPLETE_TYPING'
    assert any(r.startswith('EXTENDING_CROSSES_NOT_MATCHED:') for r in a['reasons'])
    assert out['abstain']['reasons'] == {'FILL_HOLE:INCOMPLETE_TYPING': 1}


# ---------------------------------------------------------------------------------------------------------------------------------
# the boundaries: what does not change
# ---------------------------------------------------------------------------------------------------------------------------------
def test_a1_agree_and_a_type_disagreement_is_still_filled(tmp_path):
    pl = write_pl(tmp_path, {'船長': 'PERSON', '提督': 'ANIMAL'})                # the admiral was CHECKED and is not a person: not "unchecked"
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=pl)
    a = out['answer']
    assert a['status'] == 'FILLED' and fills(out) == [('船長', [('s1', 0)])] and excluded(out) == [('提督', 'HOLE_TYPE_DISAGREE')]


def test_a1_agreeing_candidates_only_are_still_a_tie_and_a_single_one_is_filled(tmp_path):
    both = write_pl(tmp_path, {'船長': 'PERSON', '提督': 'PERSON'}, 'both.json')
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=both)
    assert out['answer']['status'] == 'TIE' and len(out['ranks'][0]['elements']) == 2
    one = write_pl(tmp_path, {'船長': 'PERSON'}, 'one.json')
    out, _ = ask(tmp_path, Q_SHIP, [S1], placement=one)
    assert out['answer']['status'] == 'FILLED' and out['answer']['excluded'] == []


def test_a1_nothing_checked_is_still_no_typed_candidate_and_without_a_placement_too(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2])
    assert out['answer']['status'] == 'NO_TYPED_CANDIDATE' and out['answer']['fillers'] == []
    pl = write_pl(tmp_path, {'船長': ('UNPLACED', None, []), '提督': ('UNPLACED', None, [])})
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=pl)
    assert out['answer']['status'] == 'NO_TYPED_CANDIDATE'


def test_a1_which_noun_keeps_its_own_reason_and_is_not_incomplete_typing(tmp_path):
    pl = write_pl(tmp_path, {'人': 'PERSON', '船長': 'PERSON', '商人': 'PERSON'})
    out, _ = ask(tmp_path, 'どの人が商人に小包を渡した？', [S1, S2], placement=pl)
    assert out['answer']['status'] == 'FILLED' and excluded(out) == [('提督', 'HOLE_TYPE_NOT_CHECKED')]


def test_a1_an_unchecked_filler_of_an_extending_cross_is_still_not_a_reason(tmp_path):
    pl = write_pl(tmp_path, {'提督': 'PERSON'})
    out, _ = ask(tmp_path, '誰が小包を渡さなかった？', ['提督は小包を渡さなかった。', '船長は港で小包を渡さなかった。'], placement=pl)
    assert out['answer']['status'] == 'FILLED'


def test_a1_the_closed_lists(tmp_path):
    assert O.ANSWER_STATUSES[-1] == 'INCOMPLETE_TYPING' and O.ANSWER_STATUSES[-2] == 'NO_TYPED_CANDIDATE'
    assert O.ANSWER_STATUSES[:10] == ('FILLED', 'TIE', 'NO_ATTESTED_CELL', 'TYPE_EXCLUDED_ALL', 'HOLE_TYPE_UNDETERMINED', 'POLAR_QUESTION',
                                      'DIRECTION_NOT_APPLIED', 'QUESTION_NOT_READ', 'ANCHOR_CROSS_INDEX_OUT_OF_RANGE', 'INCOMPLETE_BY_EXTENSION')
    assert O.HOLE_EXCLUSION_REASONS == ('HOLE_TYPE_DISAGREE', 'HOLE_TYPE_NOT_CHECKED', 'SAME_AS_RESTRICTOR', 'TYPE_UNCHECKED')
    assert all('ANSWER' not in s for s in O.ANSWER_STATUSES)


def test_a1_the_output_is_json_and_the_word_answer_is_not_in_the_abstention(tmp_path):
    pl = write_pl(tmp_path, {'船長': 'PERSON', '提督': ('UNPLACED', None, [])})
    out, text = ask(tmp_path, Q_SHIP, [S1, S2], placement=pl)
    assert json.loads(text) == out and out['answer']['status'] in O.ANSWER_STATUSES
    assert 'FILLED' not in json.dumps(out['abstain']) and out['ranks'] == []
