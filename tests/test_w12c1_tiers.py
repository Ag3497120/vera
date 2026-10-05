"""W12-c1 T3 (confidence_tiers) and T5 (the stage's environment). Pure inputs; the answers of the stages are hand-made signatures."""
import json
import os

import pytest

from verantyx import confidence_tiers as CT
from verantyx import placement_layer as PL

ANS_A = {'outcome': 'ANSWER_HUMAN_BASIS', 'values': ['地図'], 'text': None}
ANS_B = {'outcome': 'ANSWER_HUMAN_BASIS', 'values': ['本'], 'text': None}
UNK = {'outcome': 'STRUCTURE_UNDETERMINED', 'values': None, 'text': '構造が決まらないので言えません（STRUCTURE_UNDETERMINED）。'}
NOREC = {'outcome': 'NO_RECORD', 'values': None, 'text': '記録に根拠が無いので答えられません（NO_RECORD）。'}


def tier(name, status, sig=None):
    return {'name': name, 'status': status, 'signature': sig}


def keys_and_values(x):
    if isinstance(x, dict):
        for k, v in x.items():
            yield k, v
            yield from keys_and_values(v)
    elif isinstance(x, list):
        for v in x:
            yield from keys_and_values(v)


def test_signature_of_an_answer_is_its_type_and_sorted_values():
    sig = CT.signature_of('太郎が地図を渡した。', {'outcome': {'outcome': 'ANSWER_HUMAN_BASIS'}, 'reading': {'filler': '地図'}})
    assert sig == {'outcome': 'ANSWER_HUMAN_BASIS', 'values': ['地図'], 'text': None}
    assert CT.signature_of('x', {'outcome': {'outcome': 'ANSWER_HUMAN_BASIS'}, 'reading': {'filler': '地図'}}) == sig        # the text of the sentence is not part of an answer's signature
    other = CT.signature_of('x', {'outcome': {'outcome': 'NO_RECORD'}, 'reading': {'filler': None}})
    assert other == {'outcome': 'NO_RECORD', 'values': None, 'text': 'x'} and other != sig


def test_agree_counts_the_counted_stages_with_the_shown_signature():
    ct = CT.combine([tier('base', CT.COUNTED, ANS_A), tier('vocab', CT.NOT_CONSULTED_BY_READER), tier('law', CT.COUNTED, ANS_A), tier('law+user', CT.COUNTED, ANS_A)])
    assert (ct['agree'], ct['counted'], ct['shown_tier'], ct['conflict']) == (3, 3, 'law+user', False)
    assert ct['answered'] == 3


def test_stages_that_were_not_consulted_do_not_count():
    ct = CT.combine([tier('base', CT.COUNTED, ANS_A), tier('vocab', CT.NOT_CONSULTED_BY_READER), tier('law', CT.NOT_ROUTED), tier('law+user', CT.NOT_AVAILABLE)])
    assert (ct['agree'], ct['counted'], ct['shown_tier']) == (1, 1, 'base')
    assert ct['answered'] == 1
    assert [t['status'] for t in ct['tiers']] == ['COUNTED', 'NOT_CONSULTED_BY_READER', 'NOT_ROUTED', 'NOT_AVAILABLE']


def test_unknown_to_answer_is_not_a_conflict_and_not_an_agreement():
    ct = CT.combine([tier('base', CT.COUNTED, UNK), tier('law', CT.COUNTED, ANS_A)])
    assert ct['conflict'] is False and (ct['agree'], ct['counted'], ct['shown_tier']) == (1, 2, 'law')
    assert ct['answered'] == 1


def test_two_different_answers_are_a_conflict_and_nothing_is_chosen():
    ct = CT.combine([tier('base', CT.COUNTED, ANS_A), tier('law', CT.COUNTED, ANS_B)], 'strict')
    assert ct['conflict'] is True and ct['agree'] == 0 and ct['answered'] == 2
    ct2 = CT.combine([tier('base', CT.COUNTED, ANS_B), tier('law', CT.COUNTED, ANS_A)], 'strict')     # the order does not decide
    assert ct2['conflict'] is True and ct2['agree'] == 0 and ct2['answered'] == 2


def test_abstentions_of_different_types_are_different_signatures():
    ct = CT.combine([tier('base', CT.COUNTED, NOREC), tier('law', CT.COUNTED, UNK)])
    # round 3 (auditor's ruling, K403 clarified): agreeing/different abstentions are not counted, so agree is 0 (it was 1 under schema /1). A change of the definition, not a weakening.
    assert (ct['agree'], ct['answered'], ct['counted'], ct['conflict']) == (0, 0, 2, False)


def test_agreeing_abstentions_are_not_counted():
    ct = CT.combine([tier('base', CT.COUNTED, UNK), tier('law', CT.COUNTED, UNK), tier('law+user', CT.COUNTED, UNK)])
    assert (ct['agree'], ct['answered'], ct['counted']) == (0, 0, 3)


def test_an_answer_followed_by_an_abstention_shows_the_abstention_with_agree_zero():
    ct = CT.combine([tier('base', CT.COUNTED, ANS_A), tier('law', CT.COUNTED, UNK)])
    assert (ct['agree'], ct['answered'], ct['counted'], ct['shown_tier'], ct['conflict']) == (0, 1, 2, 'law', False)


def test_schema_is_v2():
    assert CT.combine([tier('base', CT.COUNTED, ANS_A)])['schema'] == 'verantyx.confidence_tiers/2'


def test_the_output_has_no_probability_shape():
    ct = CT.combine([tier('base', CT.COUNTED, ANS_A), tier('law', CT.COUNTED, ANS_A)])
    for k, v in keys_and_values(ct):
        assert k not in ('prob', 'probability', 'confidence', 'score', 'rate', 'percent')
        assert not isinstance(v, float)
    assert isinstance(ct['agree'], int) and isinstance(ct['counted'], int) and isinstance(ct['answered'], int)
    json.dumps(ct)


def test_base_is_required_and_the_profile_is_checked():
    with pytest.raises(CT.TierError):
        CT.combine([tier('base', CT.NOT_AVAILABLE)])
    with pytest.raises(CT.TierError):
        CT.combine([tier('base', CT.COUNTED, ANS_A)], 'lenient')


def test_routed_words_is_a_string_test_on_the_question_and_the_documents():
    assert CT.routed_words(['契約', '免許'], ['誰が契約した？', '太郎が本を読んだ。']) == ['契約']
    assert CT.routed_words(['契約'], ['誰が読んだ？']) == []


def test_parse_tier():
    assert CT.parse_tier('law=/x/y.sqlite') == ('law', '/x/y.sqlite')
    for bad in ('nolaw', '=x', 'law=', 'base=x'):
        with pytest.raises(CT.TierError):
            CT.parse_tier(bad)


def test_no_llm_plan_writes_a_type_conclude_knows():
    from verantyx import decode_grammar as G
    for orig in ('RECORDS', 'NO_RECORD', 'STRUCTURE_UNDETERMINED', 'SOMETHING_NEW'):
        t = CT.no_llm_plan({'call_llm': True, 'reading': {'type': orig, 'state': None, 'reason': None}, 'skip_reason': None})
        assert t['call_llm'] is False and t['reading']['type'] in G.FIXED_TEXT and t['no_llm_orig_type'] == orig
    same = {'call_llm': False, 'reading': {'type': 'QUESTION_CROSS'}}
    assert CT.no_llm_plan(same) is same


# ---- T5: the stage's environment ------------------------------------------------------------------------------------------------------------
def test_base_stage_has_no_layer_and_the_value_comes_back(monkeypatch):
    monkeypatch.setenv(PL.ENV_LAYER, '/user/layer.sqlite')
    with CT.stage_env(None):
        assert PL.ENV_LAYER not in os.environ
        with CT.stage_env('/domain/law.sqlite'):
            assert os.environ[PL.ENV_LAYER] == '/domain/law.sqlite'
        assert PL.ENV_LAYER not in os.environ
    assert os.environ[PL.ENV_LAYER] == '/user/layer.sqlite'


def test_an_exception_in_a_stage_restores_the_environment(monkeypatch):
    monkeypatch.setenv(PL.ENV_LAYER, '/user/layer.sqlite')
    with pytest.raises(RuntimeError):
        with CT.stage_env(None):
            raise RuntimeError('boom')
    assert os.environ[PL.ENV_LAYER] == '/user/layer.sqlite'
    monkeypatch.delenv(PL.ENV_LAYER)
    with pytest.raises(RuntimeError):
        with CT.stage_env('/domain/law.sqlite'):
            raise RuntimeError('boom')
    assert PL.ENV_LAYER not in os.environ
