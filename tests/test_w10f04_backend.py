"""W10-f04 (O6, K285): `llm_backend.chat` -- ollama / openai / fake in one shape {ok, content, usage, error}; typed failures; the fake records what is sent at the boundary."""
import io
import json
import socket
import urllib.error
import urllib.request

import pytest

from verantyx import llm_backend as LB
from verantyx import vera_server as VS


class Resp:
    def __init__(self, body):
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def patch_urlopen(monkeypatch, fn):
    seen = []

    def urlopen(req, timeout=None):
        seen.append({'url': req.full_url, 'body': json.loads(req.data.decode()), 'headers': {k.lower(): v for k, v in req.header_items()}, 'timeout': timeout})
        return fn(req)
    monkeypatch.setattr(urllib.request, 'urlopen', urlopen)
    return seen


MSGS = [{'role': 'user', 'content': 'hi'}]


def test_ollama_name_is_still_in_vera_server_and_is_the_moved_function():
    assert VS._ollama_chat is LB._ollama_chat


def test_ollama_success_shape(monkeypatch):
    seen = patch_urlopen(monkeypatch, lambda r: Resp({'message': {'content': 'ok'}, 'prompt_eval_count': 3, 'eval_count': 4}))
    out = LB.chat('ollama', 'm', MSGS, {'type': 'object'}, url='http://127.0.0.1:11434')
    assert out == {'ok': True, 'content': 'ok', 'usage': {'prompt_tokens': 3, 'completion_tokens': 4, 'total_tokens': 7}, 'error': None}
    assert seen[0]['url'] == 'http://127.0.0.1:11434/api/chat' and seen[0]['body']['format'] == {'type': 'object'} and seen[0]['body']['options']['temperature'] == 0


def test_openai_request_body_and_shape(monkeypatch):
    seen = patch_urlopen(monkeypatch, lambda r: Resp({'choices': [{'message': {'content': '{"a":1}'}}], 'usage': {'prompt_tokens': 5, 'completion_tokens': 2}}))
    schema = {'type': 'object', 'properties': {'a': {'type': 'integer'}}}
    out = LB.chat('openai', 'gpt-x', MSGS, schema, api_base='https://api.example.test/v1/', api_key='KEY')
    assert out == {'ok': True, 'content': '{"a":1}', 'usage': {'prompt_tokens': 5, 'completion_tokens': 2, 'total_tokens': 7}, 'error': None}
    req = seen[0]
    assert req['url'] == 'https://api.example.test/v1/chat/completions' and req['headers']['authorization'] == 'Bearer KEY'
    assert req['body']['model'] == 'gpt-x' and req['body']['messages'] == MSGS and req['body']['temperature'] == 0
    assert req['body']['response_format'] == {'type': 'json_schema', 'json_schema': {'name': 'vera', 'schema': schema, 'strict': True}}
    LB.chat('openai', 'gpt-x', MSGS, None, api_base='https://api.example.test/v1', max_tokens=7)
    assert seen[1]['body']['max_tokens'] == 7 and 'response_format' not in seen[1]['body'] and 'authorization' not in seen[1]['headers']


def test_openai_reads_the_environment(monkeypatch):
    monkeypatch.setenv('VERA_LLM_API_BASE', 'https://env.example.test/v1')
    monkeypatch.setenv('VERA_LLM_API_KEY', 'ENVKEY')
    seen = patch_urlopen(monkeypatch, lambda r: Resp({'choices': [{'message': {'content': 'x'}}]}))
    assert LB.chat('openai', 'm', MSGS, None)['ok'] is True
    assert seen[0]['url'].startswith('https://env.example.test/v1/') and seen[0]['headers']['authorization'] == 'Bearer ENVKEY'
    monkeypatch.delenv('VERA_LLM_API_BASE')
    with pytest.raises(ValueError):
        LB.chat('openai', 'm', MSGS, None)          # a missing setting is not a backend failure


FAILS = {
    'TIMEOUT': lambda r: (_ for _ in ()).throw(socket.timeout('slow')),
    'CONNECT_FAILED': lambda r: (_ for _ in ()).throw(urllib.error.URLError(ConnectionRefusedError('no'))),
    'HTTP_ERROR': lambda r: (_ for _ in ()).throw(urllib.error.HTTPError('u', 500, 'boom', {}, io.BytesIO(b'bad'))),
    'BAD_RESPONSE': lambda r: Resp(b'not json'),
}


@pytest.mark.parametrize('backend', ['ollama', 'openai'])
@pytest.mark.parametrize('kind', list(FAILS))
def test_typed_failures(monkeypatch, backend, kind):
    patch_urlopen(monkeypatch, FAILS[kind])
    out = LB.chat(backend, 'm', MSGS, None, api_base='https://x.test/v1')
    assert out['ok'] is False and out['content'] is None and out['error']['type'] == kind and out['usage'] == {}


def test_fake_backend_records_what_was_sent_and_runs_the_script():
    fb = LB.FakeBackend([{'raw': '{"x": 1}'}, {'fail': 'TIMEOUT'}, {'pick': '駅'}, {'pick': None}, {'pick': '無い語'}])
    msgs = [{'role': 'user', 'content': '候補:\n0: {"term": "公園", "used_in": []}\n1: {"term": "駅", "used_in": []}'}]
    assert LB.chat('fake', 'm', MSGS, {'t': 1}, fake=fb) == {'ok': True, 'content': '{"x": 1}', 'usage': {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}, 'error': None}
    assert LB.chat('fake', 'm', MSGS, None, fake=fb)['error']['type'] == 'TIMEOUT'
    assert json.loads(LB.chat('fake', 'm', msgs, None, fake=fb)['content']) == {'choice': 1}
    assert json.loads(LB.chat('fake', 'm', msgs, None, fake=fb)['content']) == {'choice': None}
    assert json.loads(LB.chat('fake', 'm', msgs, None, fake=fb)['content']) == {'choice': None}      # a word that is not shown is null, never a guess
    out = LB.chat('fake', 'm', MSGS, None, fake=fb)
    assert out['ok'] is False and out['error']['type'] == 'SCRIPT_EXHAUSTED'                        # never a silent empty answer
    assert len(fb.sent) == 6 and fb.sent[0] == {'model': 'm', 'messages': MSGS, 'fmt': {'t': 1}}


def test_unknown_backend_and_make_chat():
    with pytest.raises(ValueError):
        LB.chat('nope', 'm', MSGS, None)
    fb = LB.FakeBackend([{'raw': 'a'}])
    assert LB.make_chat('fake', fake=fb)('m', MSGS, None)['content'] == 'a'


def test_same_script_same_content_whatever_the_name():
    outs = [LB.chat('fake', 'm', MSGS, None, fake=LB.FakeBackend([{'raw': 'z'}])) for _ in range(3)]
    assert outs[0] == outs[1] == outs[2]
