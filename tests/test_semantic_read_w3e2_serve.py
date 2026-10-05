"""W3-e2 (V5, D15): the assumed arm in `vera serve`: kind `assumed` in `vera.provenance`; never a record; never a basis of an ANSWER."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verantyx import vera_server as VS, basis_policy as bp, decode_grammar as G


def chat_for(text):
    return lambda model, msgs, fmt: {'ok': True, 'content': text, 'error': None, 'usage': {}}


@pytest.fixture
def doc(tmp_path):
    p = tmp_path / 'd.txt'
    p.write_text('母が部屋で手紙を読んだ。\nミナが走った。\n', encoding='utf-8')
    return str(p)


def turn(doc, reply, mode, strict=False, kind='factual'):
    cfg = VS.FusionConfig.load(model='fake', documents=[doc], llm_chat=chat_for(reply), read_mode=mode, strict=strict)
    r = VS.fusion_turn([{'role': 'user', 'content': '誰が来ましたか。'}], {'request_kind': kind, 'human_present': False}, cfg)
    r['vera'].pop('timing', None)
    return r


def test_the_assumed_arm_is_marked_in_the_provenance_and_strict_read_has_none(doc):
    a = turn(doc, 'ナナが来た。', 'assume')['vera']['provenance'][0]
    assert a['read'] is True and a['arms']['agent']['kind'] == 'assumed' and a['arms']['agent']['evidence'] == []
    assert a['assumptions'][0]['word'] == 'ナナ' and a['sentence_kind'] != 'record'
    s = turn(doc, 'ナナが来た。', 'strict')['vera']['provenance'][0]
    assert s['read'] is False and 'assumptions' not in s


def test_the_arm_keys_do_not_grow(doc):
    a = turn(doc, 'ナナが来た。', 'assume')['vera']['provenance'][0]
    assert set(a['arms']['agent']) == {'surface', 'kind', 'evidence'}


def test_an_assumed_sentence_is_never_a_record_even_when_the_record_holds_the_same_cross(doc):
    # the document says `ミナが走った。` : the record's sentences are read strictly (the cross of the record is none: ミナ is not typed), and the assumed reply is not matched by cross
    items = G.verify('ミナが走った。', G.load_records([doc]), 'factual', 'fake', read_mode='assume', assume=VS.FusionConfig(model='x', documents=[doc], records=None).assume_config())
    assert items[0]['sentence_kind'] != 'record' or items[0]['via'] == 'verbatim'
    assert items[0]['arms']['agent']['kind'] == 'assumed'


def test_a_factual_question_is_not_answered_from_an_assumed_arm(doc):
    for strict in (False, True):
        r = turn(doc, 'ナナが来た。', 'assume', strict=strict)
        assert r['vera']['outcome']['outcome'] != 'ANSWER_HUMAN_BASIS'
        assert all(p['sentence_kind'] != 'record' for p in r['vera']['provenance'])


def test_the_origin_assumed_is_not_human_in_the_basis_policy():
    src = [{'family': 'document', 'origin': 'assumed', 'source': 'x', 'line': 1, 'text': 'ナナが来た。'}]
    c = bp.classify_sources(src, user_documents=True, document_texts=['ナナが来た。'])
    assert c.counts['human'] == 0 and c.policy_basis != 'HUMAN'


def test_the_record_is_read_strictly_whatever_the_mode(doc):
    cfg = VS.FusionConfig.load(model='fake', documents=[doc], llm_chat=chat_for('x'), read_mode='assume')
    rec = cfg.records
    ids = [i for i, c in rec.crosses.items() if c is not None]
    assert all('assumptions' not in rec.crosses[i] for i in ids)
    assert any(w and w.startswith('UNREAD:SUBJECT_TYPE_UNDETERMINED:ミナ') for w in rec.cross_reason.values())


def test_a_bad_mode_is_refused():
    with pytest.raises(VS.FusionBadRequest):
        VS.FusionConfig(model='x', documents=[], records=None, read_mode='loose')
