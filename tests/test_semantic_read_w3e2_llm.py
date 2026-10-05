"""W3-e2 (K331 (e), D13): `fill_candidates.ask_assumption_type`: two asks, a closed schema, the sentence never sent under the mask."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from verantyx import fill_candidates as FC

CANDS = ['GROUP_ORG', 'PERSON']


def scripted(*contents):
    sent = []
    it = iter(contents)

    def chat(model, messages, fmt):
        sent.append((messages, fmt))
        c = next(it)
        if isinstance(c, Exception):
            raise c
        return c
    chat.sent = sent
    return chat


def ok(choice):
    return {'ok': True, 'content': json.dumps({'choice': choice}), 'error': None, 'usage': {}}


def test_two_equal_answers_agree():
    chat = scripted(ok(1), ok(1))
    r = FC.ask_assumption_type('ミナ', 'に', '渡す', CANDS, chat=chat, model='m')
    assert r == {'type': 'PERSON', 'status': 'AGREED', 'answers': ['PERSON', 'PERSON'], 'calls': 2, 'error': None}
    assert all(fmt['required'] == ['choice'] for _m, fmt in chat.sent)


def test_split_null_and_out_of_candidates_decide_nothing():
    assert FC.ask_assumption_type('ミナ', 'に', None, CANDS, chat=scripted(ok(0), ok(1)), model='m')['status'] == 'SPLIT'
    assert FC.ask_assumption_type('ミナ', 'に', None, CANDS, chat=scripted(ok(None), ok(None)), model='m')['status'] == 'NULL'
    assert FC.ask_assumption_type('ミナ', 'に', None, CANDS, chat=scripted(ok(None), ok(1)), model='m')['status'] == 'SPLIT'
    r = FC.ask_assumption_type('ミナ', 'に', None, CANDS, chat=scripted(ok(7), ok(1)), model='m')
    assert r['status'] == 'OUT_OF_CANDIDATES' and r['type'] is None and r['calls'] == 1
    r = FC.ask_assumption_type('ミナ', 'に', None, CANDS, chat=scripted({'ok': True, 'content': 'not json', 'error': None}, ok(1)), model='m')
    assert r['status'] == 'OUT_OF_CANDIDATES'


def test_a_failure_keeps_its_own_type_and_a_raise_does_not_crash():
    err = {'ok': False, 'content': None, 'error': {'type': 'TIMEOUT', 'detail': ''}}
    r = FC.ask_assumption_type('ミナ', 'に', None, CANDS, chat=scripted(err), model='m')
    assert r['status'] == 'BACKEND_FAILED' and r['error'] == 'TIMEOUT' and r['type'] is None
    r = FC.ask_assumption_type('ミナ', 'に', None, CANDS, chat=scripted(ok(1), RuntimeError('boom')), model='m')
    assert r['status'] == 'BACKEND_FAILED' and r['error'] == 'CONNECT_FAILED' and r['answers'] == ['PERSON']


def test_the_mask_keeps_the_sentence_out_and_the_flag_puts_it_in():
    text = 'ハルはミナに本を渡した。'
    chat = scripted(ok(1), ok(1))
    FC.ask_assumption_type('ミナ', 'に', '渡す', CANDS, chat=chat, model='m', text=text)
    blob = json.dumps(chat.sent[0][0], ensure_ascii=False)
    assert text not in blob and 'ハル' not in blob and '本' not in blob and 'ミナ' in blob
    chat = scripted(ok(1), ok(1))
    FC.ask_assumption_type('ミナ', 'に', '渡す', CANDS, chat=chat, model='m', text=text, mask_user_text=False)
    assert text in json.dumps(chat.sent[0][0], ensure_ascii=False)
