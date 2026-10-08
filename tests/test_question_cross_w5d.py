"""W5-d (docs/OBSERVATION.md, W5-d): a filler whose type was not checked against a placement is not a candidate of a question's hole.

Part 1: the rule itself (A01: an English `Who did the girl write?` is no longer answered with the two things the girl wrote; A02: a time adverb that
the reader fused with its noun (`毎日本`) stays in `excluded`; the new reason TYPE_UNCHECKED and the new status NO_TYPED_CANDIDATE; the MULTIPLE rule).
Part 2: the intent of the tests of tests/test_question_cross_observe.py that rely on an answer without a placement, written again WITH a placement that
types the fillers (those old tests are unchanged and fail by declared conflict K1; here the same checks hold under the new rule).
"""
import json
from pathlib import Path

import pytest

from verantyx import observe as O
from verantyx import salience as SAL
from verantyx import semantic_read as SR

from test_question_cross_observe import Q_SHIP, S1, S2, _entry, ask, fills, write_doc, write_placement  # noqa: F401

HERE = Path(__file__).resolve().parent
ATTACK_DATA = HERE / 'attack' / 'w3c2' / 'data'


def write_pl(tmp, lemmas, name='pl.json'):
    """A placement file: `lemmas` = {word: (state, origin, [types], estimate_basis)} or {word: 'TYPE'} (DECIDED, direct)."""
    out = {}
    for w, v in lemmas.items():
        if isinstance(v, str): out[w] = {'state': 'DECIDED', 'origin': 'direct', 'types': [v]}
        else:
            state, origin, types, *basis = v
            out[w] = dict({'state': state, 'origin': origin, 'types': types}, **({'estimate_basis': basis[0]} if basis and basis[0] else {}))
    path = Path(tmp) / name
    path.write_text(json.dumps({'lemmas': out, 'neighbors': {}}, ensure_ascii=False), encoding='utf-8')
    return str(path)


def ask_en(question, doc, placement=None):
    res = O.run_entry(anchor_text=question, anchor_kind='question', lang='en', structure_path=str(ATTACK_DATA / 'docs' / (doc + '.jsonl')), no_index=True, placement_path=placement)
    assert res.stdout, res.error
    return json.loads(res.stdout)


def ask_ja_doc(question, doc, placement=None):
    res = O.run_entry(anchor_text=question, anchor_kind='question', lang='ja', structure_path=str(ATTACK_DATA / 'docs' / (doc + '.jsonl')), no_index=True, placement_path=placement)
    assert res.stdout, res.error
    return json.loads(res.stdout)


def excluded(out): return [(e['surface'], e['reason']) for e in out['answer']['excluded']]


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 1: the rule
# ---------------------------------------------------------------------------------------------------------------------------------
def test_a01_an_english_who_question_without_a_placement_is_not_answered_with_things():
    out = ask_en('Who did the girl write?', 'EN08')
    a = out['answer']
    assert a['status'] == 'NO_TYPED_CANDIDATE' and a['fillers'] == []
    assert sorted(excluded(out)) == [('letter', 'TYPE_UNCHECKED'), ('note', 'TYPE_UNCHECKED')]
    assert {e['reason'] for e in a['excluded']} == {'TYPE_UNCHECKED'} and a['reasons'][0] == 'NO_TYPED_CANDIDATE'
    assert out['abstain'] == {'type': 'NO_MOVE_LICENSED', 'reasons': {'FILL_HOLE:NO_TYPED_CANDIDATE': 1}} and out['focus'] == {'kind': 'NO_MOVE_LICENSED'} and out['ranks'] == []


def test_a01_with_a_direct_type_the_same_question_is_excluded_by_the_type():
    out = ask_en('Who did the girl write?', 'EN08', str(ATTACK_DATA / 'direct-types.json'))
    a = out['answer']
    assert a['status'] == 'TYPE_EXCLUDED_ALL' and a['fillers'] == []
    assert {e['reason'] for e in a['excluded']} == {'HOLE_TYPE_DISAGREE'}      # "checked and wrong" is not "could not be checked"
    assert out['abstain']['reasons'] == {'FILL_HOLE:candidate:HOLE_TYPE_DISAGREE': 2}


def test_the_rule_does_not_depend_on_the_language_an_english_filler_typed_as_a_person_is_a_candidate(tmp_path):
    pl = write_pl(tmp_path, {'letter': 'PERSON', 'note': 'PERSON'})            # an invented placement: it only shows that the language is not the rule
    out = ask_en('Who did the girl write?', 'EN08', pl)
    assert out['answer']['status'] == 'TIE' and sorted(f['surface'] for f in out['answer']['fillers']) == ['letter', 'note']
    assert {f['hole_type_check']['verdict'] for f in out['answer']['fillers']} == {'AGREE'}


def test_a02_a_time_adverb_fused_with_its_noun_is_not_a_candidate_without_a_checked_type(tmp_path):
    out = ask_ja_doc('花子は何を読んだ？', 'JA02')
    a = out['answer']
    assert a['status'] == 'NO_TYPED_CANDIDATE' and a['fillers'] == []
    assert sorted(excluded(out)) == [('新聞', 'TYPE_UNCHECKED'), ('本', 'TYPE_UNCHECKED'), ('毎日本', 'TYPE_UNCHECKED')]
    pl = write_pl(tmp_path, {'本': 'ARTIFACT', '新聞': 'ARTIFACT'})            # only the two real nouns are typed (direct)
    out = ask_ja_doc('花子は何を読んだ？', 'JA02', pl)
    a = out['answer']
    # W5-e（チケット W5-e の名指しの改訂）: 本・新聞（AGREE）と毎日本（TYPE_UNCHECKED）が並ぶ構成は TIE ではなく INCOMPLETE_TYPING（A-1）。
    assert a['status'] == 'INCOMPLETE_TYPING' and {f['surface'] for f in a['fillers']} == {'本', '新聞'}
    assert excluded(out) == [('毎日本', 'TYPE_UNCHECKED')]                      # not hidden: it stays in `excluded`
    assert {f['hole_type_check']['verdict'] for f in a['fillers']} == {'AGREE'}


def test_the_new_names_are_at_the_end_of_the_closed_lists():
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A1）: A-1 が INCOMPLETE_TYPING を末尾に足したので、末尾の 2 つを固定する
    assert O.ANSWER_STATUSES[-2:] == ('NO_TYPED_CANDIDATE', 'INCOMPLETE_TYPING') and O.ANSWER_STATUSES[:10] == (
        'FILLED', 'TIE', 'NO_ATTESTED_CELL', 'TYPE_EXCLUDED_ALL', 'HOLE_TYPE_UNDETERMINED', 'POLAR_QUESTION',
        'DIRECTION_NOT_APPLIED', 'QUESTION_NOT_READ', 'ANCHOR_CROSS_INDEX_OUT_OF_RANGE', 'INCOMPLETE_BY_EXTENSION')
    assert O.HOLE_EXCLUSION_REASONS == ('HOLE_TYPE_DISAGREE', 'HOLE_TYPE_NOT_CHECKED', 'SAME_AS_RESTRICTOR', 'TYPE_UNCHECKED')


def test_multiple_with_every_type_inside_the_hole_is_checked_one_type_outside_is_not(tmp_path):
    inside = write_pl(tmp_path, {'船長': ('MULTIPLE', 'direct', ['GROUP_ORG', 'PERSON'])}, 'in.json')
    out, _ = ask(tmp_path, Q_SHIP, [S1], placement=inside)
    a = out['answer']
    assert a['status'] == 'FILLED' and fills(out) == [('船長', [('s1', 0)])]
    assert a['fillers'][0]['hole_type_check'] == {'verdict': 'AGREE', 'reason': 'MULTIPLE_ALL_IN_HOLE', 'expected': ['GROUP_ORG', 'PERSON'], 'observed': ['GROUP_ORG', 'PERSON']}
    outside = write_pl(tmp_path, {'船長': ('MULTIPLE', 'direct', ['ARTIFACT', 'PERSON'])}, 'out.json')
    out, _ = ask(tmp_path, Q_SHIP, [S1], placement=outside)
    a = out['answer']
    assert a['status'] == 'NO_TYPED_CANDIDATE' and a['fillers'] == [] and excluded(out) == [('船長', 'TYPE_UNCHECKED')]
    assert a['excluded'][0]['hole_type_check'] == {'verdict': 'NOT_CHECKED', 'reason': 'MULTIPLE', 'expected': ['GROUP_ORG', 'PERSON'], 'observed': ['ARTIFACT', 'PERSON']}


def test_an_estimated_unplaced_or_unknown_answer_is_not_a_checked_type(tmp_path):
    for name, spec in (('est', ('DECIDED', 'estimated', ['PERSON'], 'proximity')), ('gen', ('DECIDED', 'estimated', ['PERSON'], 'generated')),
                       ('unp', ('UNPLACED', None, [])), ('unk', ('UNKNOWN', None, []))):
        pl = write_pl(tmp_path, {'船長': spec}, name + '.json')
        out, _ = ask(tmp_path, Q_SHIP, [S1], placement=pl)
        assert out['answer']['status'] == 'NO_TYPED_CANDIDATE', name
        assert excluded(out) == [('船長', 'TYPE_UNCHECKED')], name
    pl = write_pl(tmp_path, {'船長': 'PERSON'}, 'direct.json')                   # the same word, direct: a candidate
    out, _ = ask(tmp_path, Q_SHIP, [S1], placement=pl)
    assert out['answer']['status'] == 'FILLED'


def test_all_disagree_is_type_excluded_all_and_any_unchecked_among_them_is_no_typed_candidate(tmp_path):
    only_wrong = write_pl(tmp_path, {'船長': 'ANIMAL', '提督': 'ANIMAL'}, 'a.json')
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=only_wrong)
    assert out['answer']['status'] == 'TYPE_EXCLUDED_ALL' and {e['reason'] for e in out['answer']['excluded']} == {'HOLE_TYPE_DISAGREE'}
    assert out['abstain']['reasons'] == {'FILL_HOLE:candidate:HOLE_TYPE_DISAGREE': 2}
    mixed = write_pl(tmp_path, {'船長': 'ANIMAL'}, 'b.json')                    # the admiral is not in the file: UNKNOWN: not checked
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=mixed)
    a = out['answer']
    assert a['status'] == 'NO_TYPED_CANDIDATE' and a['fillers'] == []
    assert sorted(excluded(out)) == [('提督', 'TYPE_UNCHECKED'), ('船長', 'HOLE_TYPE_DISAGREE')]
    assert out['abstain']['reasons'] == {'FILL_HOLE:NO_TYPED_CANDIDATE': 1}
    assert a['reasons'][0] == 'NO_TYPED_CANDIDATE'


def test_a_checked_candidate_among_unchecked_ones_answers_and_the_others_stay_excluded(tmp_path):
    pl = write_pl(tmp_path, {'船長': 'PERSON'})
    # W5-e（チケット W5-e の名指しの改訂）: AGREE の候補が TYPE_UNCHECKED の候補と並ぶ構成は FILLED ではなく INCOMPLETE_TYPING（A-1）。候補と除外は両方返る。
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=pl)
    a = out['answer']
    assert a['status'] == 'INCOMPLETE_TYPING' and fills(out) == [('船長', [('s1', 0)])] and excluded(out) == [('提督', 'TYPE_UNCHECKED')]


def test_which_noun_keeps_its_own_reason_for_an_unchecked_candidate(tmp_path):
    pl = write_pl(tmp_path, {'人': 'PERSON', '船長': 'PERSON', '商人': 'PERSON'})
    out, _ = ask(tmp_path, 'どの人が商人に小包を渡した？', [S1, S2], placement=pl)
    assert out['answer']['status'] == 'FILLED' and excluded(out) == [('提督', 'HOLE_TYPE_NOT_CHECKED')]    # unchanged: which+N is stricter and has its own name
    pl_none = write_pl(tmp_path, {'人': 'PERSON', '商人': 'PERSON'}, 'pn.json')
    out, _ = ask(tmp_path, 'どの人が商人に小包を渡した？', [S1, S2], placement=pl_none)
    assert out['answer']['status'] == 'TYPE_EXCLUDED_ALL' and {e['reason'] for e in out['answer']['excluded']} == {'HOLE_TYPE_NOT_CHECKED'}


def test_an_unchecked_filler_of_an_extending_cross_does_not_make_the_answer_incomplete(tmp_path):
    pl = write_pl(tmp_path, {'提督': 'PERSON'})                                  # the captain (extending cross) cannot be checked: it is not a candidate
    out, _ = ask(tmp_path, '誰が小包を渡さなかった？', ['提督は小包を渡さなかった。', '船長は港で小包を渡さなかった。'], placement=pl)
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('提督', [('s1', 0)])]
    both = write_pl(tmp_path, {'提督': 'PERSON', '船長': 'PERSON'}, 'both.json')
    out, _ = ask(tmp_path, '誰が小包を渡さなかった？', ['提督は小包を渡さなかった。', '船長は港で小包を渡さなかった。'], placement=both)
    assert out['answer']['status'] == 'INCOMPLETE_BY_EXTENSION'


def test_the_declarative_sentence_path_is_not_changed_by_the_question_rule(tmp_path):
    out, _ = ask(tmp_path, S1, [S1], kind='seed')
    assert 'answer' not in out and out['focus']['kind'] == 'FOCUS'


# ---------------------------------------------------------------------------------------------------------------------------------
# Part 2: the intent of the K1 tests of tests/test_question_cross_observe.py, WITH a placement that types the fillers
# ---------------------------------------------------------------------------------------------------------------------------------
PERSONS = {'船長': 'PERSON', '提督': 'PERSON'}


def test_k1_filled_has_the_filler_the_sentence_id_and_the_coordinate(tmp_path):
    out, text = ask(tmp_path, Q_SHIP, [S1, '鳥が空を飛んだ。'], placement=write_pl(tmp_path, PERSONS))
    a = out['answer']
    assert list(a) == ['schema', 'status', 'question', 'question_cross', 'fillers', 'excluded', 'structure', 'reasons']
    assert a['status'] == 'FILLED' and fills(out) == [('船長', [('s1', 0)])]
    assert out['focus']['kind'] == 'FOCUS' and out['anchor'] is None and out['abstain'] is None
    el = out['ranks'][0]['elements'][0]
    assert el['cell_key'] == out['focus']['cell_key'] and el['coords'] == [{'origin': {'kind': 'structure', 'id': 's1', 'cross_index': 0}, 'moves': []}]
    assert el['occupied'] == 'ATTESTED' and el['realization']['status'] == 'REALIZED' and el['realization']['text'].startswith('船長') and 'Ｘ' not in el['realization']['text']
    assert a['structure']['unread_ids'] == ['s2'] and a['structure']['crosses_matched'] == 1
    assert a['fillers'][0]['hole_type_check']['verdict'] == 'AGREE'


def test_k1_a_tie_is_returned_with_both_and_never_broken(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=write_pl(tmp_path, PERSONS))
    assert out['answer']['status'] == 'TIE' and [f['surface'] for f in out['answer']['fillers']] == sorted(['提督', '船長'])
    assert out['focus']['kind'] == 'TIE' and len(out['focus']['candidates']) == 2
    assert len(out['ranks']) == 1 and out['ranks'][0]['kind'] == 'TIE' and len(out['ranks'][0]['elements']) == 2
    assert sorted(r['reading'] for f in out['answer']['fillers'] for r in f['evidence']) == ['s1', 's2']


def _structure(items, placement_path):
    lookup = O.FilePlacement.from_path(placement_path)
    return O.Structure.from_injected(items, lookup=lookup, neighbors=lookup)


def test_k1_a_tie_does_not_depend_on_the_order_of_the_sentences(tmp_path):
    pl = write_pl(tmp_path, PERSONS)
    def build(order):
        return _structure([{'id': 's%d' % i, 'text': t, 'reading': SR.read(t, 'ja', placement=None)} for i, t in order], pl)
    vp = O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question')
    a = O.to_json(O.observe(vp, build([(1, S1), (2, S2)])))
    b = O.to_json(O.observe(vp, build([(2, S2), (1, S1)])))
    assert a == b and '"status":"TIE"' in a


def test_k1_an_arm_tie_gives_each_filler_as_a_candidate_of_its_own(tmp_path):
    reading = SR.read(S1, 'ja', placement=None)
    reading['clauses'][0]['roles']['agent'] = ['船長', '提督']
    st = _structure([{'id': 'x', 'text': 'hand written', 'reading': reading}], write_pl(tmp_path, PERSONS))
    out = json.loads(O.to_json(O.observe(O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question'), st)))
    assert out['answer']['status'] == 'TIE'
    assert [f['surface'] for f in out['answer']['fillers']] == ['提督', '船長'] and all(f['from_arm_tie'] for f in out['answer']['fillers'])
    assert out['focus']['kind'] == 'FOCUS'
    # and without a placement the two are not candidates (the arm tie does not give a type)
    st0 = O.Structure.from_injected([{'id': 'x', 'text': 'hand written', 'reading': reading}])
    out0 = json.loads(O.to_json(O.observe(O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question'), st0)))
    assert out0['answer']['status'] == 'NO_TYPED_CANDIDATE' and out0['answer']['fillers'] == []


def test_k1_an_extending_cross_that_names_another_filler_makes_the_answer_incomplete(tmp_path):
    pl = write_pl(tmp_path, PERSONS)
    out, _ = ask(tmp_path, '誰が小包を渡さなかった？', ['提督は小包を渡さなかった。', '船長は港で小包を渡さなかった。'], placement=pl)
    a = out['answer']
    assert a['status'] == 'INCOMPLETE_BY_EXTENSION' and [f['surface'] for f in a['fillers']] == ['提督'] and out['ranks'] == []
    assert out['abstain']['reasons'] == {'FILL_HOLE:INCOMPLETE_BY_EXTENSION': 1}
    out, _ = ask(tmp_path, '誰が小包を渡さなかった？', ['船長は小包を渡さなかった。', '船長は港で小包を渡さなかった。'], placement=pl)
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('船長', [('s1', 0)])]


def test_k1_nothing_is_unchecked_by_accident_the_check_is_shown(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [S1])      # no placement: the check says why, and the filler is not a candidate
    a = out['answer']
    assert a['status'] == 'NO_TYPED_CANDIDATE'
    assert a['excluded'][0]['hole_type_check'] == {'verdict': 'NOT_CHECKED', 'reason': 'NO_PLACEMENT', 'expected': ['GROUP_ORG', 'PERSON'], 'observed': None}
    assert a['excluded'][0]['reason'] == 'TYPE_UNCHECKED'


def test_k1_nfkc_of_the_filler_and_of_the_other_arms(tmp_path):
    pl = write_pl(tmp_path, {'A社': 'GROUP_ORG', 'Ａ社': 'GROUP_ORG'})
    out, _ = ask(tmp_path, Q_SHIP, ['Ａ社が商人に小包を渡した。', 'A社が商人に小包を渡した。'], placement=pl)
    a = out['answer']
    assert a['status'] == 'FILLED' and sorted(f['surface'] for f in a['fillers']) == ['A社', 'Ａ社'] and {f['nfkc'] for f in a['fillers']} == {'A社'}
    assert out['focus']['kind'] == 'TIE' and len(out['focus']['candidates']) == 2
    pl2 = write_pl(tmp_path, {'小包': 'ARTIFACT'}, 'pl2.json')
    out, _ = ask(tmp_path, 'Ａ社は商人に何を渡した？', ['Ａ社が商人に小包を渡した。', 'A社が商人に小包を渡した。'], placement=pl2)
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('小包', [('s1', 0), ('s2', 0)])]


def test_k1_polarity_tense_and_voice_must_be_the_same(tmp_path):
    pl = write_pl(tmp_path, PERSONS)
    for sentence in ('船長は商人に小包を渡さなかった。', '船長は商人に小包を渡す。'):
        out, _ = ask(tmp_path, Q_SHIP, [sentence], placement=pl)
        assert out['answer']['status'] == 'NO_ATTESTED_CELL', sentence
    out, _ = ask(tmp_path, '誰が商人に小包を渡さなかった？', ['船長は商人に小包を渡さなかった。'], placement=pl)
    assert out['answer']['status'] == 'FILLED'
    out, _ = ask(tmp_path, '誰が商人に小包を渡す？', ['船長は商人に小包を渡す。', S2], placement=pl)
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('船長', [('s1', 0)])]
    passive = SR.read(S1, 'ja', placement=None)
    passive['clauses'][0]['voice'] = 'passive'
    st = _structure([{'id': 'p', 'text': 'hand written', 'reading': passive}], pl)
    assert json.loads(O.to_json(O.observe(O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question'), st)))['answer']['status'] == 'NO_ATTESTED_CELL'


def test_k1_a_filler_that_is_the_mark_character_is_a_correct_answer(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, ['Ｘが商人に小包を渡した。'], placement=write_pl(tmp_path, {'Ｘ': 'PERSON'}))
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('Ｘ', [('s1', 0)])]


def test_k1_the_ledger_records_a_question_and_replays_to_the_same_output(tmp_path):
    lookup = O.FilePlacement.from_path(write_pl(tmp_path, PERSONS))
    st = O.Structure.from_jsonl(write_doc(tmp_path, [S1, S2]), lookup, lookup)
    for text in (Q_SHIP, '誰が商人に小包を渡さなかった？'):
        ledger = SAL.MemoryLedger()
        vp = O.build_viewpoint(anchor_text=text, anchor_kind='question')
        obs = O.observe(vp, st, ledger=ledger)
        assert isinstance(obs, O.QuestionObservation) and obs.outcome in ('TIE', 'NO_MOVE_LICENSED')
        O.record_turn(ledger, vp, obs)
        event = [e for e in ledger.events() if e['kind'] == 'observation'][0]
        assert event['payload']['outcome'] == obs.outcome and O.replay(list(ledger.events()), event, st) is True
    one = O.Structure.from_jsonl(write_doc(tmp_path, [S1], 'one.jsonl'), lookup, lookup)
    ledger = SAL.MemoryLedger(); vp = O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question')
    obs = O.observe(vp, one, ledger=ledger); O.record_turn(ledger, vp, obs)
    event = [e for e in ledger.events() if e['kind'] == 'observation'][0]
    assert event['payload']['observed_cell'] == obs.focus.cell_key and O.replay(list(ledger.events()), event, one) is True
    # an abstention of the new kind is recorded and replays too
    none = O.Structure.from_jsonl(write_doc(tmp_path, [S1], 'none.jsonl'))
    ledger = SAL.MemoryLedger(); vp = O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question')
    obs = O.observe(vp, none, ledger=ledger); O.record_turn(ledger, vp, obs)
    event = [e for e in ledger.events() if e['kind'] == 'observation'][0]
    assert obs.outcome == 'NO_MOVE_LICENSED' and O.replay(list(ledger.events()), event, none) is True


def test_k1_the_cross_index_of_a_question_is_zero_or_nothing(tmp_path):
    pl = write_pl(tmp_path, PERSONS)
    out, _ = ask(tmp_path, Q_SHIP, [S1], cross=0, placement=pl)
    assert out['answer']['status'] == 'FILLED'
    out, _ = ask(tmp_path, Q_SHIP, [S1], cross=1, placement=pl)
    assert out['answer']['status'] == 'ANCHOR_CROSS_INDEX_OUT_OF_RANGE'


def test_k1_the_reading_of_the_anchor_is_not_evidence(tmp_path):
    lookup = O.FilePlacement.from_path(write_pl(tmp_path, PERSONS))
    st = O.Structure.from_jsonl(write_doc(tmp_path, [S1]), lookup, lookup)
    vp = O.build_viewpoint(anchor_text='誰が商人に小包を渡した？', anchor_kind='question')
    assert json.loads(O.to_json(O.observe(vp, O.Structure.empty(lookup, lookup))))['answer']['status'] == 'NO_ATTESTED_CELL'
    assert json.loads(O.to_json(O.observe(vp, st)))['answer']['status'] == 'FILLED'


def test_k1_the_command_line_entry_gives_the_same_bytes_for_two_hash_seeds(tmp_path):
    doc = write_doc(tmp_path, [S1, S2, '鳥が空を飛んだ。'])
    pl = write_pl(tmp_path, PERSONS)
    args = ['--anchor-text', Q_SHIP, '--anchor-kind', 'question', '--structure', doc, '--no-index', '--placement', pl]
    a, b = _entry(args, 0, tmp_path), _entry(args, 4242, tmp_path)
    assert a.returncode == b.returncode == 0, a.stderr + b.stderr
    assert a.stdout == b.stdout and json.loads(a.stdout)['answer']['status'] == 'TIE'
    assert 'ANSWER' not in a.stdout
    nopl = ['--anchor-text', Q_SHIP, '--anchor-kind', 'question', '--structure', doc, '--no-index']
    c, d = _entry(nopl, 0, tmp_path), _entry(nopl, 4242, tmp_path)
    assert c.stdout == d.stdout and json.loads(c.stdout)['answer']['status'] == 'NO_TYPED_CANDIDATE'


# ---------------------------------------------------------------------------------------------------------------------------------
# W5-d2 (D2-7, auditor's addition 9): without `--placement`, a question reads VERA_PLACEMENT (the coarse placement) through the same adapter the event
# cross uses.  The expectations come from what r7 says about the words (queried with CoarseLookup before the code was written):
#   先生, 校長, 生徒 = DECIDED direct PERSON;  花子 = MULTIPLE direct (ANIMAL, PERSON);  地図 = MULTIPLE direct (INFO_LANGUAGE, PLACE).
# These tests FAIL (they do not skip) when r7 is not there.
# ---------------------------------------------------------------------------------------------------------------------------------
R7 = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1"
# Integration (auditor, 2026-10-04): the two-machine gate runs this file on a machine without build/; the three tests that read r7 skip there with a
# visible reason (ENV_MISSING) instead of failing. Where r7 exists nothing changes.
_needs_r7 = pytest.mark.skipif(not __import__('os').path.isdir(R7), reason="ENV_MISSING[coarse placement r7/run1]")
Q_MAP = '誰が生徒に地図を渡した？'
T1 = '先生が生徒に地図を渡した。'
T2 = '校長が生徒に地図を渡した。'
T3 = '花子が生徒に地図を渡した。'


@_needs_r7
def test_w5d2_vera_placement_types_the_hole_filler_of_a_question(tmp_path, monkeypatch):
    monkeypatch.setenv('VERA_PLACEMENT', R7)
    out, _ = ask(tmp_path, Q_MAP, [T1])
    a = out['answer']
    assert a['status'] == 'FILLED' and fills(out) == [('先生', [('s1', 0)])]
    assert a['fillers'][0]['hole_type_check']['verdict'] == 'AGREE' and a['fillers'][0]['hole_type_check']['observed'] == ['PERSON']
    assert out['structure']['placement'].startswith('coarse-placement:')
    out, _ = ask(tmp_path, Q_MAP, [T1, T2])
    assert out['answer']['status'] == 'TIE' and sorted(f['surface'] for f in out['answer']['fillers']) == ['先生', '校長']
    out, _ = ask(tmp_path, Q_MAP, [T3])
    a = out['answer']
    assert a['status'] == 'NO_TYPED_CANDIDATE' and a['fillers'] == [] and excluded(out) == [('花子', 'TYPE_UNCHECKED')]
    assert a['excluded'][0]['hole_type_check']['reason'] == 'MULTIPLE' and a['excluded'][0]['hole_type_check']['observed'] == ['ANIMAL', 'PERSON']


@_needs_r7
def test_w5d2_the_placement_file_wins_over_vera_placement(tmp_path, monkeypatch):
    monkeypatch.setenv('VERA_PLACEMENT', R7)
    pl = write_pl(tmp_path, {'先生': 'ANIMAL'})
    out, _ = ask(tmp_path, Q_MAP, [T1], placement=pl)
    a = out['answer']
    assert a['status'] == 'TYPE_EXCLUDED_ALL' and {e['reason'] for e in a['excluded']} == {'HOLE_TYPE_DISAGREE'}
    assert not out['structure']['placement'].startswith('coarse-placement:')


def test_w5d2_an_empty_vera_placement_is_as_before_no_typed_candidate(tmp_path, monkeypatch):
    monkeypatch.setenv('VERA_PLACEMENT', '')
    out, _ = ask(tmp_path, Q_MAP, [T1])
    assert out['answer']['status'] == 'NO_TYPED_CANDIDATE' and out['structure']['placement'] == 'stub-no-placement/1'
    monkeypatch.delenv('VERA_PLACEMENT')
    out, _ = ask(tmp_path, Q_MAP, [T1])
    assert out['answer']['status'] == 'NO_TYPED_CANDIDATE' and out['structure']['placement'] == 'stub-no-placement/1'


@_needs_r7
def test_w5d2_the_command_line_with_vera_placement_gives_the_same_bytes_for_two_hash_seeds(tmp_path):
    import os, subprocess, sys
    doc = write_doc(tmp_path, [T1, T2])
    def run(seed):
        env = {'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(HERE.parent), 'PYTHONHASHSEED': str(seed), 'VERA_PLACEMENT': R7}
        return subprocess.run([sys.executable, '-m', 'verantyx.cli', 'observe', '--anchor-text', Q_MAP, '--anchor-kind', 'question', '--structure', doc, '--no-index'],
                              capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=180)
    a, b = run(0), run(4242)
    assert a.returncode == b.returncode == 0, a.stderr + b.stderr
    assert a.stdout == b.stdout and json.loads(a.stdout)['answer']['status'] == 'TIE'
    assert json.loads(a.stdout)['structure']['placement'].startswith('coarse-placement:')


def test_w5d2_k1_the_same_question_with_and_without_a_placement(tmp_path, monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=write_pl(tmp_path, {'船長': 'PERSON', '提督': 'PERSON'}))
    assert out['answer']['status'] == 'TIE'
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2])
    a = out['answer']
    assert a['status'] == 'NO_TYPED_CANDIDATE' and a['fillers'] == [] and [e['reason'] for e in a['excluded']] == ['TYPE_UNCHECKED', 'TYPE_UNCHECKED']
