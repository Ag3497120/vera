"""W10-f04 (7)(8), K283, K287: the candidate mouth in `vera serve`. Without `fill` nothing changes; with it `vera.holes`, `vera.ledger_ids` and a `testimony_fill` arm appear, the content and the outcome
do not change, and the record (documents) is never written. The placement is r8 (read only) through VERA_PLACEMENT; the LLMs are fakes."""
import contextlib
import io
import json
import re
import urllib.request
from pathlib import Path

import pytest

from verantyx import basis_policy as bp
from verantyx import cli
from verantyx import decode_grammar as G
from verantyx import fill_candidates as F
from verantyx import vera_server as VS
from verantyx.testimony_ledger import TestimonyLedger

R8 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'
DOC = '母が部屋で本を読んだ。\nウサギが図書館へ走った。\nエリートが銀行へ歩いた。\n'            # r3: two sentences of two holes each (a one-hole sentence is never adopted: J16)


def fresh_placement_connection():
    """`coarse_place` keeps ONE sqlite connection per placement in a module-level cache, and a connection is only usable in the thread that made it. A FusionConfig does all of Vera's work in its own
    thread (production has one config); the tests make several, so the cache is emptied (connections closed) before each config is built."""
    from verantyx import coarse_place
    for key in list(coarse_place._CACHE):
        try:
            coarse_place._CACHE.pop(key).con.close()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def r8(monkeypatch):
    fresh_placement_connection()
    assert Path(R8).exists(), 'the placement r8 is the reference of this ticket'
    monkeypatch.setenv('VERA_PLACEMENT', R8)
    monkeypatch.delenv('VERA_SOVEREIGN_ROOT', raising=False)
    monkeypatch.delenv('VERA_SOVEREIGN_STORE', raising=False)


class FakeLLM:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    def __call__(self, model, messages, fmt):
        self.calls.append(messages)
        return {'ok': True, 'content': self.reply, 'error': None, 'usage': {}}


def smart_fill_chat(calls):
    """The candidate backend: an open ask is answered by the hole's word (ウサギ -> 犬, エリート -> 兄, 図書館 -> 駅, 銀行 -> 港), a closed ask picks the first candidate shown."""
    nearest = {'図書館': ('PLACE', 'goal', '駅'), '窓口': ('PLACE', 'place', '公園'), '役所': ('PLACE', 'goal', '港'), 'ウサギ': ('ANIMAL', 'agent', '犬'), 'エリート': ('PERSON', 'agent', '兄'), 'カラス': ('ANIMAL', 'agent', '猫'),
               '銀行': ('PLACE', 'goal', '港')}

    def chat(model, messages, fmt):
        prompt = '\n'.join(m['content'] for m in messages)
        calls.append(prompt)
        if fmt and fmt.get('properties', {}).get('near_words') is not None:
            m = re.search(r'「([^」]+)」。\n述語', prompt)
            head = m.group(1) if m else None
            t, role, word = nearest.get(head, ('PLACE', None, None))
            return {'ok': True, 'content': json.dumps({'type': t, 'role': role, 'near_words': [word] if word else []}, ensure_ascii=False), 'error': None, 'usage': {}}
        first = re.search(r'^0: (\{.*\})$', prompt, re.M)
        return {'ok': True, 'content': json.dumps({'choice': 0 if first else None}), 'error': None, 'usage': {}}
    return chat


def docs(tmp_path, text=DOC):
    p = Path(tmp_path) / 'd.txt'
    p.write_text(text, encoding='utf-8')
    return [str(p)]


def cfg_of(tmp_path, llm, *, fill=None, text=DOC, **kw):
    fresh_placement_connection()
    return VS.FusionConfig.load(model='fake-model', documents=docs(tmp_path, text), llm_chat=llm, fill=fill, **kw)


def fill_of(tmp_path, calls, **kw):
    return F.FillConfig(ledger=TestimonyLedger(tmp_path / 'ledger.jsonl'), chat=smart_fill_chat(calls), model='fill-model', backend_name='fake', **kw)


def turn(cfg, q='誰が駅へ走った？', **vera):
    return VS.fusion_turn([{'role': 'user', 'content': q}], vera or None, cfg)


def strip_timing(res):
    res = json.loads(json.dumps(res, ensure_ascii=False))
    res['vera'].pop('timing')
    return res


def test_without_fill_the_vera_field_has_the_keys_it_had(tmp_path):
    res = turn(cfg_of(tmp_path, FakeLLM('母が図書館へ歩いた。')))
    assert set(res['vera']) == {'schema', 'layer', 'request_kind', 'reading', 'grammar', 'grammar_id', 'llm', 'grammar_check', 'provenance', 'outcome', 'timing'}
    assert set(res['vera']['timing']) == {'vera_ms', 'llm_ms'}


def test_fill_adds_holes_ledger_ids_and_a_testimony_fill_arm_and_changes_nothing_else(tmp_path):
    reply = 'カラスが本部へ走った。'            # not a sentence of the documents (a verbatim record sentence is a record); two holes: が:カラス is adoptable, へ:本部 is not (r3)
    base = turn(cfg_of(tmp_path, FakeLLM(reply)))
    calls = []
    cfg = cfg_of(tmp_path, FakeLLM(reply), fill=fill_of(tmp_path, calls, max_doc_holes=0))
    res = turn(cfg)
    assert 'holes' in res['vera'] and 'ledger_ids' in res['vera'] and set(res['vera']) - set(base['vera']) == {'holes', 'ledger_ids'}
    assert res['content'] == base['content'] and res['vera']['outcome'] == base['vera']['outcome']          # K283: the candidate mouth only annotates
    item = res['vera']['provenance'][0]
    arm = item['arms']['agent']
    assert arm['kind'] == 'testimony_fill' and arm['surface'] == '猫' and arm['origin'] == 'testimony' and arm['basis'].startswith('LLM_TESTIMONY_FILL:fill-model:')
    assert item['sentence_kind'] != 'record' and item['read'] is False and res['vera']['ledger_ids'] and arm['ledger_id'] in res['vera']['ledger_ids']
    assert 'fill_llm_ms' in res['vera']['timing']
    assert res['vera']['outcome']['outcome'] == 'TESTIMONY'         # an answer from the model is never ANSWER_HUMAN_BASIS


def test_a_candidate_is_never_the_basis_of_an_answer(tmp_path):
    assert 'testimony' in bp.DECLARED_NON_EVIDENCE and 'constructed' in bp.DECLARED_NON_EVIDENCE
    src = {'family': 'llm', 'origin': 'testimony', 'model': 'm', 'text': '母が駅へ歩いた。'}
    assert bp.classify_sources([src]) != bp.classify_sources([{'family': 'document', 'source': 'd.txt', 'line': 1, 'text': 'x', 'sentence_id': 'd.txt#1:1'}])
    # the factual answer (a record) stays what it was whether the mouth is on or not, and a testimony arm is never in its sources
    calls = []
    for fill in (None, fill_of(tmp_path, calls, max_doc_holes=0)):
        cfg = cfg_of(tmp_path, FakeLLM('呼ばれない'), fill=fill)
        res = turn(cfg, '母は部屋で何を読んだ？')
        assert res['vera']['outcome']['outcome'] == 'ANSWER_HUMAN_BASIS' and res['content'] == '母が部屋で本を読んだ。' and cfg.llm_chat.calls == []
        assert all(p['sentence_kind'] == 'record' for p in res['vera']['provenance'])
        assert not any(a.get('kind') == 'testimony_fill' for p in res['vera']['provenance'] for a in (p.get('arms') or {}).values())


def test_the_documents_get_the_mouth_but_the_record_is_not_written(tmp_path):
    plain = cfg_of(tmp_path, FakeLLM(''))
    calls = []
    fill = fill_of(tmp_path, calls)
    cfg = cfg_of(tmp_path, FakeLLM(''), fill=fill)
    assert cfg.records.records == plain.records.records and cfg.records.crosses == plain.records.crosses and cfg.records.cross_reason == plain.records.cross_reason     # (8)
    assert cfg.fill_stats['holes_asked'] == 4 and cfg.fill_stats['adopted'] == 2 and cfg.fill_stats['skipped_holes'] == 0       # r3: 2 sentences x 2 holes; the が hole is adopted, the へ hole is refused by (a4)
    rows = fill.ledger.entries()
    assert [r['type'] for r in rows].count('testimony') == 2 and [r['type'] for r in rows].count('not_adopted') == 2         # the refused へ holes are on the ledger too (J14)
    assert all(r['context']['doc_id'] for r in rows if r['type'] == 'testimony')
    assert (Path(tmp_path) / 'd.txt').read_text(encoding='utf-8') == DOC


def test_the_document_hole_budget_counts_what_it_skips(tmp_path):
    calls = []
    cfg = cfg_of(tmp_path, FakeLLM(''), fill=fill_of(tmp_path, calls, max_doc_holes=1))
    assert cfg.fill_stats['holes_asked'] == 1 and cfg.fill_stats['skipped_holes'] == 3


def test_fill_off_fusion_turn_is_byte_identical_to_a_config_without_the_arguments(tmp_path):
    a = strip_timing(turn(cfg_of(tmp_path, FakeLLM('母が図書館へ歩いた。'))))
    b = strip_timing(turn(VS.FusionConfig.load(model='fake-model', documents=docs(tmp_path), llm_chat=FakeLLM('母が図書館へ歩いた。'), fill=None, backend='ollama')))
    assert json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(b, ensure_ascii=False, sort_keys=True)


def test_a_backend_failure_of_the_mouth_does_not_break_the_turn(tmp_path):
    def down(model, messages, fmt):
        return {'ok': False, 'content': None, 'error': {'type': 'CONNECT_FAILED', 'detail': 'x'}}
    fill = F.FillConfig(ledger=TestimonyLedger(tmp_path / 'l.jsonl'), chat=down, model='m', max_doc_holes=0)
    base = turn(cfg_of(tmp_path, FakeLLM('弟が役所へ走った。')))
    res = turn(cfg_of(tmp_path, FakeLLM('弟が役所へ走った。'), fill=fill))
    assert res['content'] == base['content'] and res['vera']['holes'][0]['status'] == 'BACKEND_FAILED' and res['vera']['holes'][0]['reason'] == 'BACKEND_FAILED:CONNECT_FAILED'
    assert not any(a.get('kind') == 'testimony_fill' for p in res['vera']['provenance'] for a in (p.get('arms') or {}).values())


def test_openai_backend_route(tmp_path, monkeypatch):
    seen = []

    class Resp:
        def read(self):
            return json.dumps({'choices': [{'message': {'content': 'はい'}}], 'usage': {'prompt_tokens': 1, 'completion_tokens': 1}}).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    monkeypatch.setattr(urllib.request, 'urlopen', lambda req, timeout=None: (seen.append(req.full_url), Resp())[1])
    cfg = VS.FusionConfig.load(model='gpt-x', documents=docs(tmp_path), backend='openai', api_base='https://api.example.test/v1')
    res = turn(cfg, '誰が駅へ走った？')
    assert seen == ['https://api.example.test/v1/chat/completions'] and res['usage'] == {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2}


def test_serve_refusals(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv('VERA_LLM_API_BASE', raising=False)
    st = tmp_path / 'store.json'
    for argv, verdict in [(['serve', '--backend', 'openai', '--model', 'm'], 'API_BASE_REQUIRED'), (['serve', '--backend', 'ollama', '--model', 'm', '--fill'], 'LEDGER_REQUIRED'),
                          (['serve', '--backend', 'ollama'], 'MODEL_REQUIRED')]:
        code = cli.main(['--store', str(st)] + argv)
        assert code == 2 and json.loads(capsys.readouterr().out)['verdict'] == verdict
    capsys.readouterr()
    p = tmp_path / 'bad.jsonl'
    TestimonyLedger(p)
    p.write_text(p.read_text(encoding='utf-8').replace('header', 'headex'), encoding='utf-8')
    assert cli.main(['--store', str(st), 'serve', '--backend', 'ollama', '--model', 'm', '--fill', '--ledger-file', str(p)]) == 2
    assert json.loads(capsys.readouterr().out)['verdict'] == 'LEDGER_INTEGRITY'
