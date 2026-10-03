"""W3-c2: the observation of a question (docs/OBSERVATION.md 質問の観測): the cells of the structure that agree with the question's cross everywhere but the hole.

The documents here are written in each test (small, in a temporary directory) and do not use the sentences of the frozen test data (tests/observe/question/).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from verantyx import observe as O
from verantyx import event_cross as EC
from verantyx import salience as SAL
from verantyx import semantic_read as SR

TREE = Path(__file__).resolve().parent.parent
Q_SHIP = '誰が商人に小包を渡した？'
S1 = '船長が商人に小包を渡した。'          # captain gave the parcel to the merchant
S2 = '提督が商人に小包を渡した。'          # admiral ...


def write_doc(tmp, sentences, name='doc.jsonl'):
    path = Path(tmp) / name
    path.write_text(''.join(json.dumps({'id': 's%d' % i, 'text': t, 'lang': 'ja'}, ensure_ascii=False) + '\n' for i, t in enumerate(sentences, 1)), encoding='utf-8')
    return str(path)


def write_placement(tmp, lemmas, name='pl.json'):
    path = Path(tmp) / name
    path.write_text(json.dumps({'lemmas': {w: {'state': 'DECIDED', 'origin': 'direct', 'types': [t]} for w, t in lemmas.items()}, 'neighbors': {}}, ensure_ascii=False), encoding='utf-8')
    return str(path)


def ask(tmp, text, sentences, *, placement=None, direction='', kind='question', cross=None, lang=None):
    doc = write_doc(tmp, sentences)
    res = O.run_entry(anchor_text=text, anchor_kind=kind, lang=lang, direction=direction, anchor_cross=cross, structure_path=doc, no_index=True,
                      placement_path=placement)
    assert res.exit_code == 0, res.error
    return json.loads(res.stdout), res.stdout


def fills(out):
    return [(f['surface'], [(e['reading'], e['cross_index']) for e in f['evidence']]) for f in out['answer']['fillers']]


# ---------------------------------------------------------------------------------------------------------------------------------
def test_filled_has_the_filler_the_sentence_id_and_the_coordinate(tmp_path):
    out, text = ask(tmp_path, Q_SHIP, [S1, '鳥が空を飛んだ。'])
    a = out['answer']
    assert list(a) == ['schema', 'status', 'question', 'question_cross', 'fillers', 'excluded', 'structure', 'reasons']
    assert a['schema'] == 'verantyx.question_answer/1' and a['status'] == 'FILLED'
    assert fills(out) == [('船長', [('s1', 0)])]
    assert out['focus']['kind'] == 'FOCUS' and out['anchor'] is None and out['abstain'] is None
    el = out['ranks'][0]['elements'][0]
    assert el['cell_key'] == out['focus']['cell_key'] and el['coords'] == [{'origin': {'kind': 'structure', 'id': 's1', 'cross_index': 0}, 'moves': []}]
    assert el['occupied'] == 'ATTESTED' and el['realization']['status'] == 'REALIZED' and el['realization']['text'].startswith('船長') and 'Ｘ' not in el['realization']['text']
    assert a['structure']['sentences'] == 2 and a['structure']['unread'] == 1 and a['structure']['unread_ids'] == ['s2']
    assert a['structure']['crosses_compared'] == 1 and a['structure']['crosses_matched'] == 1
    assert a['question']['hole_role'] == 'agent' and 'declarative' not in a['question']
    assert out['counts']['question']['status'] == 'FILLED'


def test_a_tie_is_returned_with_both_and_never_broken(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2])
    assert out['answer']['status'] == 'TIE'
    assert [f['surface'] for f in out['answer']['fillers']] == sorted(['提督', '船長'])
    assert out['focus']['kind'] == 'TIE' and len(out['focus']['candidates']) == 2
    assert len(out['ranks']) == 1 and out['ranks'][0]['kind'] == 'TIE' and len(out['ranks'][0]['elements']) == 2
    assert sorted(r['reading'] for f in out['answer']['fillers'] for r in f['evidence']) == ['s1', 's2']


def test_a_tie_does_not_depend_on_the_order_of_the_sentences(tmp_path):
    def build(order):
        items = [{'id': 's%d' % i, 'text': t, 'reading': SR.read(t, 'ja', placement=None)} for i, t in order]
        return O.Structure.from_injected(items)
    vp = O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question')
    a = O.to_json(O.observe(vp, build([(1, S1), (2, S2)])))
    b = O.to_json(O.observe(vp, build([(2, S2), (1, S1)])))
    assert a == b and '"status":"TIE"' in a


def test_an_arm_tie_gives_each_filler_as_a_candidate_of_its_own():
    reading = SR.read(S1, 'ja', placement=None)
    reading['clauses'][0]['roles']['agent'] = ['船長', '提督']
    st = O.Structure.from_injected([{'id': 'x', 'text': 'hand written', 'reading': reading}])
    out = json.loads(O.to_json(O.observe(O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question'), st)))
    assert out['answer']['status'] == 'TIE'
    assert [f['surface'] for f in out['answer']['fillers']] == ['提督', '船長'] and all(f['from_arm_tie'] for f in out['answer']['fillers'])
    assert out['focus']['kind'] == 'FOCUS'    # one cell: the tie is inside its arm, which the answer shows


def test_no_attested_cell_says_how_many_sentences_were_not_read(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, ['鳥が空を飛んだ。', '商人が船長に小包を送った。', '誰が来たか。'])
    a = out['answer']
    assert a['status'] == 'NO_ATTESTED_CELL' and a['fillers'] == []
    assert out['focus'] == {'kind': 'NO_MOVE_LICENSED'} and out['abstain'] == {'type': 'NO_MOVE_LICENSED', 'reasons': {'FILL_HOLE:NO_ATTESTED_CELL': 1}}
    assert a['structure']['unread'] == 2 and a['structure']['unread_ids'] == ['s1', 's3'] and a['structure']['crosses_compared'] == 1
    assert 'UNREAD_SENTENCES:2' in a['reasons']


def test_type_excluded_all_is_not_the_same_as_no_attested_cell(tmp_path):
    pl = write_placement(tmp_path, {'船長': 'ANIMAL'})    # an invented placement: the captain is an animal, a person was asked for
    out, _ = ask(tmp_path, Q_SHIP, [S1], placement=pl)
    a = out['answer']
    assert a['status'] == 'TYPE_EXCLUDED_ALL' and a['fillers'] == []
    assert [(e['surface'], e['reason']) for e in a['excluded']] == [('船長', 'HOLE_TYPE_DISAGREE')]
    assert a['excluded'][0]['hole_type_check']['verdict'] == 'DISAGREE' and a['excluded'][0]['evidence'][0]['reading'] == 's1'
    assert out['abstain']['reasons'] == {'FILL_HOLE:candidate:HOLE_TYPE_DISAGREE': 1}


def test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [S1])    # no placement: NOT_CHECKED(NO_PLACEMENT), shown but not excluded
    assert out['answer']['status'] == 'FILLED'
    assert out['answer']['fillers'][0]['hole_type_check'] == {'verdict': 'NOT_CHECKED', 'reason': 'NO_PLACEMENT', 'expected': ['GROUP_ORG', 'PERSON'], 'observed': None}


def test_restrictor_whose_type_is_not_decided_says_so(tmp_path):
    out, _ = ask(tmp_path, 'どの人が商人に小包を渡した？', [S1])
    assert out['answer']['status'] == 'HOLE_TYPE_UNDETERMINED' and out['abstain']['reasons'] == {'FILL_HOLE:HOLE_TYPE_UNDETERMINED': 1}


def test_restrictor_keeps_only_candidates_whose_type_agrees(tmp_path):
    pl = write_placement(tmp_path, {'人': 'PERSON', '船長': 'PERSON', '提督': 'ANIMAL', '商人': 'PERSON'})
    out, _ = ask(tmp_path, 'どの人が商人に小包を渡した？', [S1, S2], placement=pl)
    a = out['answer']
    assert a['status'] == 'FILLED' and fills(out) == [('船長', [('s1', 0)])]
    assert [(e['surface'], e['reason']) for e in a['excluded']] == [('提督', 'HOLE_TYPE_DISAGREE')]
    pl2 = write_placement(tmp_path, {'人': 'PERSON', '船長': 'PERSON', '商人': 'PERSON'}, 'pl2.json')    # the admiral is not in the placement: not checkable
    out, _ = ask(tmp_path, 'どの人が商人に小包を渡した？', [S1, S2], placement=pl2)
    assert out['answer']['status'] == 'FILLED' and [(e['surface'], e['reason']) for e in out['answer']['excluded']] == [('提督', 'HOLE_TYPE_NOT_CHECKED')]
    assert out['answer']['excluded'][0]['hole_type_check']['reason'] == 'UNKNOWN'


def test_restrictor_itself_is_never_the_answer(tmp_path):
    pl = write_placement(tmp_path, {'船長': 'PERSON', '提督': 'PERSON', '商人': 'PERSON'})
    out, _ = ask(tmp_path, 'どの船長が商人に小包を渡した？', [S1, S2], placement=pl)
    a = out['answer']
    assert a['status'] == 'FILLED' and fills(out) == [('提督', [('s2', 0)])]
    assert [(e['surface'], e['reason']) for e in a['excluded']] == [('船長', 'SAME_AS_RESTRICTOR')]


def test_polar_question_makes_a_cross_but_is_not_observed(tmp_path):
    out, _ = ask(tmp_path, '船長が商人に小包を渡したか？', [S1])
    assert out['answer']['status'] == 'POLAR_QUESTION' and out['answer']['fillers'] == [] and out['answer']['question_cross'] is not None
    assert out['abstain']['reasons'] == {'FILL_HOLE:POLAR_QUESTION': 1}


def test_a_direction_on_a_question_is_not_applied(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [S1], direction='FACE_SWAP:agent')
    assert out['answer']['status'] == 'DIRECTION_NOT_APPLIED' and out['abstain']['reasons'] == {'FILL_HOLE:DIRECTION_NOT_APPLIED': 1} and out['ranks'] == []
    assert out['viewpoint']['direction'] == [{'move': 'FACE_SWAP', 'role': 'agent'}]


def test_en_a_stranded_to_question_never_returns_the_object_as_the_answer(tmp_path):
    # review r1 M1: `Who did the girl write to?` must not be answered with the object of `The girl wrote a letter.`
    path = Path(tmp_path) / 'en.jsonl'
    path.write_text(''.join(json.dumps({'id': i, 'text': t, 'lang': 'en'}) + '\n' for i, t in
                            [('E-S01', 'The girl wrote a letter.'), ('E-S02', 'The boy ran a race.'), ('E-S03', 'The farmer sold bread.')]), encoding='utf-8')
    for q in ['Who did the girl write to?', 'Who did the boy run to?', 'Who did the farmer sell to?']:
        res = O.run_entry(anchor_text=q, anchor_kind='question', structure_path=str(path), no_index=True)
        assert res.exit_code == 0, res.error
        out = json.loads(res.stdout)
        assert out['answer']['status'] not in ('FILLED', 'TIE'), (q, out['answer']['status'])
        assert out['answer']['fillers'] == [] if 'fillers' in out['answer'] else True


def test_a_question_the_reader_cannot_read_is_a_typed_no_anchor(tmp_path):
    out, _ = ask(tmp_path, '船長は誰に小包を渡した？', [S1])
    assert out['answer']['status'] == 'QUESTION_NOT_READ' and out['focus'] == {'kind': 'NO_ANCHOR', 'reason': 'READER_ABSTAINED'}
    detail = out['abstain']['detail']
    assert detail['reasons'] == ['RECIPIENT_TYPE_UNDETERMINED:Ｘ'] and detail['question']['wh'] == '誰' and 'declarative' not in detail['question']


def test_the_reading_of_the_anchor_is_not_evidence(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [])
    assert out['answer']['status'] == 'NO_ATTESTED_CELL' and out['answer']['structure']['sentences'] == 0
    st = O.Structure.from_jsonl(write_doc(tmp_path, [S1]))
    vp = O.build_viewpoint(anchor_text='誰が商人に小包を渡した？', anchor_kind='question')
    assert json.loads(O.to_json(O.observe(vp, O.Structure.empty())))['answer']['status'] == 'NO_ATTESTED_CELL'
    assert json.loads(O.to_json(O.observe(vp, st)))['answer']['status'] == 'FILLED'


def test_a_question_in_the_structure_is_not_evidence(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, ['誰が商人に小包を渡したか。', '船長が商人に小包を渡したのか？'])
    assert out['answer']['status'] == 'NO_ATTESTED_CELL' and out['answer']['structure']['unread'] == 2


def test_the_index_does_not_change_the_evidence(tmp_path):
    sys.path.insert(0, str(TREE / 'tests' / 'observe'))
    from common import build_small_index
    idx = build_small_index(out=tmp_path / 'index_small')
    doc = write_doc(tmp_path, [S1, '鳥が空を飛んだ。'])
    plain = O.run_entry(anchor_text=Q_SHIP, anchor_kind='question', structure_path=doc, no_index=True)
    with_index = O.run_entry(anchor_text=Q_SHIP, anchor_kind='question', structure_path=doc, index_root=str(idx), index_families=('pro',))
    assert plain.exit_code == with_index.exit_code == 0
    assert json.loads(plain.stdout)['answer'] == json.loads(with_index.stdout)['answer']


def test_nfkc_of_the_filler_and_of_the_other_arms(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, ['Ａ社が商人に小包を渡した。', 'A社が商人に小包を渡した。'])
    a = out['answer']
    assert a['status'] == 'FILLED' and sorted(f['surface'] for f in a['fillers']) == ['A社', 'Ａ社'] and {f['nfkc'] for f in a['fillers']} == {'A社'}
    assert out['focus']['kind'] == 'TIE' and len(out['focus']['candidates']) == 2    # two cells (the surface differs), one answer
    out, _ = ask(tmp_path, 'Ａ社は商人に何を渡した？', ['Ａ社が商人に小包を渡した。', 'A社が商人に小包を渡した。'])
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('小包', [('s1', 0), ('s2', 0)])]


def test_a_cross_with_more_arms_is_not_a_match_and_is_listed(tmp_path):
    out, _ = ask(tmp_path, '船長は何を渡さなかった？', ['船長は港で小包を渡さなかった。'])
    a = out['answer']
    assert a['status'] == 'NO_ATTESTED_CELL'
    assert a['structure']['extending'] == [{'reading': 's1', 'cross_index': 0, 'extra_roles': ['place'], 'fillers': ['小包']}]
    assert 'EXTENDING_CROSSES_NOT_MATCHED:1' in a['reasons']


def test_an_extending_cross_that_names_another_filler_makes_the_answer_incomplete(tmp_path):
    out, _ = ask(tmp_path, '誰が小包を渡さなかった？', ['提督は小包を渡さなかった。', '船長は港で小包を渡さなかった。'])
    # the admiral is a match; the captain is in a cross with one more arm: the set of fillers is not given as complete
    a = out['answer']
    assert a['status'] == 'INCOMPLETE_BY_EXTENSION' and [f['surface'] for f in a['fillers']] == ['提督'] and out['ranks'] == []
    assert out['abstain']['reasons'] == {'FILL_HOLE:INCOMPLETE_BY_EXTENSION': 1}
    # the same filler in the extending cross does not make it incomplete
    out, _ = ask(tmp_path, '誰が小包を渡さなかった？', ['船長は小包を渡さなかった。', '船長は港で小包を渡さなかった。'])
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('船長', [('s1', 0)])]


def test_polarity_tense_and_voice_must_be_the_same(tmp_path):
    for sentence in ('船長は商人に小包を渡さなかった。', '船長は商人に小包を渡す。'):
        out, _ = ask(tmp_path, Q_SHIP, [sentence])
        assert out['answer']['status'] == 'NO_ATTESTED_CELL', sentence
    out, _ = ask(tmp_path, '誰が商人に小包を渡さなかった？', ['船長は商人に小包を渡さなかった。'])
    assert out['answer']['status'] == 'FILLED'
    out, _ = ask(tmp_path, '誰が商人に小包を渡す？', ['船長は商人に小包を渡す。', S2])
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('船長', [('s1', 0)])]
    passive = SR.read(S1, 'ja', placement=None)
    passive['clauses'][0]['voice'] = 'passive'
    st = O.Structure.from_injected([{'id': 'p', 'text': 'hand written', 'reading': passive}])
    assert json.loads(O.to_json(O.observe(O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question'), st)))['answer']['status'] == 'NO_ATTESTED_CELL'


def test_the_predicate_is_compared_as_it_is_without_a_paraphrase(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, ['船長が商人に小包を送った。', '船長が商人に小包を運んだ。'])
    assert out['answer']['status'] == 'NO_ATTESTED_CELL'    # 送る / 運ぶ are not 渡す, whatever they are near


def test_a_filler_that_is_the_mark_character_is_a_correct_answer(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, ['Ｘが商人に小包を渡した。'])
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('Ｘ', [('s1', 0)])]


def test_no_sentence_with_the_mark_is_in_the_output_except_the_question_cross(tmp_path):
    out, text = ask(tmp_path, Q_SHIP, [S1])
    probe = json.loads(text)
    probe['answer']['question_cross'] = None
    probe['answer']['question'] = None
    assert 'Ｘ' not in json.dumps(probe, ensure_ascii=False)
    assert '"text":"Ｘ' not in text and 'Ｘが商人に' not in text.replace(json.dumps(out['answer']['question_cross'], ensure_ascii=False, separators=(',', ':')), '')


@pytest.mark.parametrize('case', [
    dict(text=Q_SHIP, sentences=[S1]), dict(text=Q_SHIP, sentences=[S1, S2]), dict(text=Q_SHIP, sentences=[]),
    dict(text='船長が商人に小包を渡したか？', sentences=[S1]), dict(text=Q_SHIP, sentences=[S1], direction='FACE_SWAP:agent'),
    dict(text='船長は誰に小包を渡した？', sentences=[S1]), dict(text='どの人が商人に小包を渡した？', sentences=[S1])])
def test_no_output_has_the_capital_word_answer(tmp_path, case):
    out, text = ask(tmp_path, case['text'], case['sentences'], direction=case.get('direction', ''))
    assert 'ANSWER' not in text and set(O.ANSWER_STATUSES) >= {out['answer']['status']}
    assert all('ANSWER' not in s for s in O.ANSWER_STATUSES)


def test_the_ledger_records_a_question_and_replays_to_the_same_output(tmp_path):
    st = O.Structure.from_jsonl(write_doc(tmp_path, [S1, S2]))
    for text in (Q_SHIP, '誰が商人に小包を渡さなかった？'):
        ledger = SAL.MemoryLedger()
        vp = O.build_viewpoint(anchor_text=text, anchor_kind='question')
        obs = O.observe(vp, st, ledger=ledger)
        assert isinstance(obs, O.QuestionObservation) and obs.outcome in ('TIE', 'NO_MOVE_LICENSED')
        O.record_turn(ledger, vp, obs)
        event = [e for e in ledger.events() if e['kind'] == 'observation'][0]
        assert event['payload']['outcome'] == obs.outcome and O.replay(list(ledger.events()), event, st) is True
    one = O.Structure.from_jsonl(write_doc(tmp_path, [S1], 'one.jsonl'))
    ledger = SAL.MemoryLedger(); vp = O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question')
    obs = O.observe(vp, one, ledger=ledger); O.record_turn(ledger, vp, obs)
    event = [e for e in ledger.events() if e['kind'] == 'observation'][0]
    assert event['payload']['observed_cell'] == obs.focus.cell_key and O.replay(list(ledger.events()), event, one) is True


def test_a_seed_and_a_statement_with_kind_question_take_the_old_path(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [S1], kind='seed')
    assert 'answer' not in out and out['focus']['kind'] == 'NO_ANCHOR'
    out, _ = ask(tmp_path, S1, [S1], kind='question')    # a statement with kind question (the frozen case M15-question-J01 is of this kind)
    assert 'answer' not in out and out['focus']['kind'] == 'FOCUS'
    out, _ = ask(tmp_path, 'Ｘ', [S1], kind='question')
    assert 'answer' not in out


def test_the_cross_index_of_a_question_is_zero_or_nothing(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [S1], cross=0)
    assert out['answer']['status'] == 'FILLED'
    out, _ = ask(tmp_path, Q_SHIP, [S1], cross=1)
    assert out['answer']['status'] == 'ANCHOR_CROSS_INDEX_OUT_OF_RANGE' and out['focus'] == {'kind': 'NO_ANCHOR', 'reason': 'ANCHOR_CROSS_INDEX_OUT_OF_RANGE'}


def _entry(args, seed, tmp):
    env = {'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(TREE), 'PYTHONHASHSEED': str(seed)}
    return subprocess.run([sys.executable, '-m', 'verantyx.cli', 'observe', *args], capture_output=True, text=True, env=env, cwd=str(tmp), timeout=180)


def test_the_command_line_entry_gives_the_same_bytes_for_two_hash_seeds(tmp_path):
    doc = write_doc(tmp_path, [S1, S2, '鳥が空を飛んだ。'])
    args = ['--anchor-text', Q_SHIP, '--anchor-kind', 'question', '--structure', doc, '--no-index']
    a, b = _entry(args, 0, tmp_path), _entry(args, 4242, tmp_path)
    assert a.returncode == b.returncode == 0, a.stderr + b.stderr
    assert a.stdout == b.stdout and json.loads(a.stdout)['answer']['status'] == 'TIE'
    assert 'ANSWER' not in a.stdout
