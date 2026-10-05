"""W10-f01 (docs/FUSION.md): `vera serve --backend ollama` -- layer 0 (the LLM answers, every sentence is typed) and layer 1 (`--strict`, a grammar built from the record).

The LLM is a fake everywhere in this file; the grammar and the verifier are tested by their rules. The real Ollama is in test_serve_fusion_ollama.py.
The placement is handed over by replacing `event_cross.default_lookup` (the path VERA_PLACEMENT takes). No test is skipped.
"""
import contextlib
import io
import json
import re
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from verantyx import cli
from verantyx import decode_grammar as G
from verantyx import event_cross as EC
from verantyx import observe as O
from verantyx import vera_server as VS
from verantyx.cross_store import CrossStore
from verantyx.cognitive_interventions import InterventionLog
from verantyx.gap_graph import GapGraph
from verantyx.tool_call_quarantine import ToolCallQuarantine

DOC = '太郎が地図を渡した。\n花子は本を読んだ。\n'
PLACE = {'太郎': 'PERSON', '花子': 'PERSON', '次郎': 'PERSON', '地図': 'ARTIFACT', '本': 'ARTIFACT'}


class FakeLLM:
    """差し込む LLM。呼ばれた回数と受け取った messages・format を残す。reply は文字列か (messages, fmt) -> 文字列。"""

    def __init__(self, reply='', ok=True):
        self.reply, self.ok, self.calls = reply, ok, []

    def __call__(self, model, messages, fmt):
        self.calls.append({'model': model, 'messages': messages, 'fmt': fmt})
        if not self.ok:
            return {'ok': False, 'content': None, 'error': {'type': 'CONNECT_FAILED', 'detail': 'fake'}}
        out = self.reply(messages, fmt) if callable(self.reply) else self.reply
        return {'ok': True, 'content': out, 'error': None, 'usage': {}}


def write_pl(tmp, lemmas):
    path = Path(tmp) / 'pl.json'
    path.write_text(json.dumps({'lemmas': {w: {'state': 'DECIDED', 'origin': 'direct', 'types': [t]} for w, t in lemmas.items()}, 'neighbors': {}}, ensure_ascii=False),
                    encoding='utf-8')
    return O.FilePlacement.from_path(str(path))


@pytest.fixture
def place(tmp_path, monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_SOVEREIGN_ROOT', raising=False)
    monkeypatch.delenv('VERA_SOVEREIGN_STORE', raising=False)
    fp = write_pl(tmp_path, PLACE)
    monkeypatch.setattr(EC, 'default_lookup', lambda *a, **k: fp)
    return fp


@pytest.fixture
def noplace(monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_SOVEREIGN_ROOT', raising=False)
    monkeypatch.delenv('VERA_SOVEREIGN_STORE', raising=False)


def docfile(tmp_path, text=DOC, name='d.txt'):
    p = Path(tmp_path) / name
    p.write_text(text, encoding='utf-8')
    return str(p)


def make_cfg(tmp_path, llm, *, strict=False, docs=None, text=DOC):
    paths = [docfile(tmp_path, text)] if docs is None else docs
    return VS.FusionConfig.load(model='fake-model', documents=paths, strict=strict, llm_chat=llm)


def msg(q):
    return [{'role': 'user', 'content': q}]


def run(cfg, q, **vera):
    return VS.fusion_turn(msg(q), vera or None, cfg)


def gbnf_literals(gbnf):
    """GBNF の文字列リテラルを読み戻す（`altN ::= "…"` の行と `tok ::= "…" | "…"`）。"""
    out = []
    for line in gbnf.splitlines():
        if line.startswith('root ::='):
            continue
        body = line.split('::=', 1)[1].strip()
        for m in re.finditer(r'"((?:[^"\\]|\\.)*)"', body):
            out.append(re.sub(r'\\(.)', lambda k: {'n': '\n', 'r': '\r', 't': '\t'}.get(k.group(1), k.group(1)), m.group(1)))
    return out


# ---- 文法 ----------------------------------------------------------------------------------------------------------------------------------

def test_grammar_alternatives_gbnf_and_schema_come_from_the_same_list(place, tmp_path):
    cfg = make_cfg(tmp_path, FakeLLM(), strict=True)
    turn = G.plan_turn('太郎は何を渡した？', 'factual', cfg.records, cfg.documents, strict=True)
    g = turn['grammar']
    assert turn['reading']['type'] == 'QUESTION_CROSS' and turn['reading']['filler'] == '地図'
    assert g['alternatives'] == ['太郎が地図を渡した。', '太郎は地図を渡した。']            # A2 (the record sentence) then A3 (the question with the filler in the hole)
    assert g['json_schema']['properties']['answer']['enum'] == g['alternatives']
    assert gbnf_literals(g['gbnf']) == g['alternatives']
    assert g['json_schema']['additionalProperties'] is False and g['json_schema']['required'] == ['answer']
    again = G.plan_turn('太郎は何を渡した？', 'factual', cfg.records, cfg.documents, strict=True)['grammar']
    assert again['id'] == g['id'] and re.fullmatch(r'g-[0-9a-f]{16}', g['id'])
    assert g['summary']['sovereign'] == {'state': 'NOT_CONFIGURED', 'used_as_grammar_source': False, 'reason': 'SOVEREIGN_CLAIM_NOT_A_SENTENCE'}


def test_gbnf_escapes_quote_backslash_newline():
    nasty = ['彼は"はい"と言った。', 'a\\b。', '一行目\n二行目。']
    assert gbnf_literals(G.gbnf_alternatives(nasty)) == nasty
    assert gbnf_literals(G.gbnf_vocabulary(nasty)) == nasty


def test_every_alternative_passes_the_verifier_as_a_record(place, tmp_path):
    cfg = make_cfg(tmp_path, FakeLLM(), strict=True)
    g = G.plan_turn('太郎は何を渡した？', 'factual', cfg.records, cfg.documents, strict=True)['grammar']
    for alt in g['alternatives']:
        items = G.verify(alt, cfg.records, 'factual', 'm')
        assert len(items) == 1 and items[0]['sentence_kind'] == 'record' and items[0]['read'] and items[0]['evidence'] == ['d.txt#1:1']
        assert G.all_record_with_hole(items, 'patient', '地図')


def test_a3_only_when_the_question_word_occurs_once(place, tmp_path):
    cfg = make_cfg(tmp_path, FakeLLM(), strict=True)
    assert G._a3('誰が誰を渡した？', '誰', 'X') is None
    assert G._a3('地図を渡した？', '誰', 'X') is None
    assert G._a3('誰が地図を渡した？', '誰', '太郎') == '太郎が地図を渡した。'


# ---- 読めない・記録が無い入力では LLM を呼ばない（層 1）、型は層 0 でも同じ ------------------------------------------------------------------------

NOCALL = [
    ('太郎は何を買った？', 'NO_RECORD'),                       # no attested cell
    ('地図の話を書いて', 'STRUCTURE_UNDETERMINED'),            # not a question
    ('太郎は地図を渡しましたか？', 'STRUCTURE_UNDETERMINED'),   # polar
    ('Who handed over the map?', None),                        # English question: any non-answer type
]


@pytest.mark.parametrize('q,type_', NOCALL)
def test_strict_does_not_call_the_llm_when_nothing_is_readable_or_recorded(place, tmp_path, q, type_):
    llm = FakeLLM('{"answer": "太郎が地図を渡した。"}')
    res = run(make_cfg(tmp_path, llm, strict=True), q)
    v = res['vera']
    assert llm.calls == [] and v['llm']['called'] is False
    assert v['reading']['type'] in ('NO_RECORD', 'STRUCTURE_UNDETERMINED') and (type_ is None or v['reading']['type'] == type_)
    assert v['outcome']['outcome'] == v['reading']['type'] and v['outcome']['content_shown'] is False
    assert res['content'] == G.FIXED_TEXT[v['reading']['type']] and v['grammar'] is None


def test_strict_no_placement_is_no_record_and_no_call(noplace, tmp_path):
    llm = FakeLLM()
    v = run(make_cfg(tmp_path, llm, strict=True), '誰が地図を渡した？')['vera']
    assert llm.calls == [] and v['reading']['type'] == 'NO_RECORD' and v['reading']['state'] == 'NO_TYPED_CANDIDATE'


def test_strict_no_documents_is_no_record_and_no_call(place, tmp_path):
    llm = FakeLLM()
    cfg = make_cfg(tmp_path, llm, strict=True, docs=[])
    v = run(cfg, '誰が地図を渡した？')['vera']
    assert llm.calls == [] and v['reading']['type'] == 'NO_RECORD' and v['reading']['reason'] == 'NO_DOCUMENTS'
    assert run(cfg, '物語を書いて', request_kind='creative')['vera']['reading']['type'] == 'NO_RECORD' and llm.calls == []


def test_strict_tie_is_structure_undetermined_and_no_call(place, tmp_path):
    llm = FakeLLM()
    cfg = make_cfg(tmp_path, llm, strict=True, text='太郎が地図を渡した。\n次郎が地図を渡した。\n')
    v = run(cfg, '誰が地図を渡した？')['vera']
    assert llm.calls == [] and v['reading']['type'] == 'STRUCTURE_UNDETERMINED'


def test_default_layer_keeps_the_types_but_lets_the_llm_answer_as_testimony(place, tmp_path):
    llm = FakeLLM('分かりません。')
    res = run(make_cfg(tmp_path, llm), '太郎は何を買った？')
    v = res['vera']
    assert len(llm.calls) == 1 and v['reading']['type'] == 'NO_RECORD' and v['layer'] == 0
    assert v['outcome']['outcome'] == 'TESTIMONY' and v['outcome']['content_shown'] is True


# ---- Z3: 文法の外は出ない ------------------------------------------------------------------------------------------------------------------

OUTSIDE = [
    ('{"answer": "次郎が地図を渡した。"}', 'ANSWER_NOT_IN_ENUM'),            # a person who is not in the record
    ('{"answer": "太郎が地図を渡したよ。"}', 'ANSWER_NOT_IN_ENUM'),          # a record sentence with characters added
    ('太郎が地図を渡した。', 'NOT_JSON'),
    ('{"reply": "太郎が地図を渡した。"}', 'NO_ANSWER_KEY'),
    ('{"answer": "太郎が地図を渡した。", "extra": 1}', 'KEYS_NOT_ANSWER_ONLY'),
    ('{"answer": ["太郎が地図を渡した。"]}', 'ANSWER_NOT_A_STRING'),
    ('[1, 2]', 'NOT_AN_OBJECT'),
    ('', 'NOT_JSON'),
]


@pytest.mark.parametrize('raw,why', OUTSIDE)
def test_z3_outside_grammar_is_withheld(place, tmp_path, raw, why):
    res = run(make_cfg(tmp_path, FakeLLM(raw), strict=True), '誰が地図を渡した？')
    v = res['vera']
    assert v['outcome']['outcome'] == 'OUTSIDE_GRAMMAR' and v['outcome']['outcome'] not in G.ANSWER_OUTCOMES
    assert v['grammar_check'] == {'in_grammar': False, 'reason': why}
    assert res['content'] == G.FIXED_TEXT['OUTSIDE_GRAMMAR']
    assert v['llm']['raw'] == raw and v['llm']['withheld'] is True and v['outcome']['content_shown'] is False
    assert v['provenance'] == []


def test_z3_creative_token_outside_the_vocabulary_is_withheld(place, tmp_path):
    cfg = make_cfg(tmp_path, FakeLLM(json.dumps({'answer': ['太郎', 'が', '宇宙船', 'を', '作っ', 'た', '。']}, ensure_ascii=False)), strict=True)
    res = run(cfg, '短い話を書いて', request_kind='creative')
    assert res['vera']['grammar_check']['reason'] == 'TOKEN_NOT_IN_VOCABULARY' and res['vera']['outcome']['outcome'] == 'OUTSIDE_GRAMMAR'
    assert '宇宙船' not in res['content'] and res['vera']['llm']['withheld'] is True


def test_z3_verifier_is_independent_of_the_schema(place, tmp_path):
    """The grammar check is not trusted to be the only gate: a sentence that is not a record never becomes an answer even if it is handed to the verifier directly."""
    cfg = make_cfg(tmp_path, FakeLLM(), strict=True)
    items = G.verify('次郎が地図を渡した。', cfg.records, 'factual', 'm')
    assert items[0]['sentence_kind'] == 'testimony' and not G.all_record_with_hole(items, 'agent', '太郎')


# ---- 層 1: 文法の内なら答え ----------------------------------------------------------------------------------------------------------------

def test_strict_in_grammar_answer_is_human_basis_with_evidence(place, tmp_path):
    llm = FakeLLM('{"answer": "太郎が地図を渡した。"}')
    res = run(make_cfg(tmp_path, llm, strict=True), '誰が地図を渡した？')
    v = res['vera']
    assert v['layer'] == 1 and v['outcome']['outcome'] == 'ANSWER_HUMAN_BASIS' and res['content'] == '太郎が地図を渡した。'
    assert v['grammar_check']['in_grammar'] is True and v['grammar_id'].startswith('g-')
    assert [p['sentence_kind'] for p in v['provenance']] == ['record'] and v['provenance'][0]['evidence'] == ['d.txt#1:1']
    assert v['outcome']['basis_policy']['outcome'] == 'ANSWER_HUMAN_BASIS' and v['reading']['filler'] == '太郎'
    assert llm.calls[0]['fmt'] == v['grammar']['json_schema'] and v['timing']['llm_ms'] >= 0


# ---- 層 0（既定）--------------------------------------------------------------------------------------------------------------------------

def test_default_record_answers_and_the_llm_is_not_called(place, tmp_path):
    llm = FakeLLM('これは呼ばれないはず')
    res = run(make_cfg(tmp_path, llm), '誰が地図を渡した？')
    v = res['vera']
    assert llm.calls == [] and v['llm']['called'] is False and v['llm']['skipped_reason'] == 'RECORD_ANSWERED'
    assert v['outcome']['outcome'] == 'ANSWER_HUMAN_BASIS' and res['content'] == '太郎が地図を渡した。'
    assert v['provenance'][0]['sentence_kind'] == 'record' and v['provenance'][0]['evidence'] == ['d.txt#1:1']
    assert v['reading']['type'] == 'QUESTION_CROSS' and v['layer'] == 0 and v['grammar'] is None


def test_default_llm_answer_without_record_is_testimony_never_an_answer(place, tmp_path):
    res = run(make_cfg(tmp_path, FakeLLM('次郎が地図を渡した。'), strict=False), '太郎は何を買った？')
    v = res['vera']
    assert v['outcome']['outcome'] == 'TESTIMONY' and v['outcome']['outcome'] not in G.ANSWER_OUTCOMES
    assert res['content'] == G.MARK_TESTIMONY + '\n次郎が地図を渡した。\n（記録で確かめられません）'
    assert v['provenance'][0]['sentence_kind'] == 'testimony' and v['provenance'][0]['origin'] == 'testimony'
    assert v['provenance'][0]['source'] == {'family': 'llm', 'origin': 'testimony', 'model': 'fake-model'}
    assert v['outcome']['basis_policy']['outcome'] != 'ANSWER_HUMAN_BASIS' and v['llm']['raw'] == '次郎が地図を渡した。'


def test_mixing_trap_record_sentence_plus_invention_is_not_an_answer(place, tmp_path):
    """classify_sources would call document + testimony HUMAN. The two origins are never put in one result: the policy sees testimony only."""
    res = run(make_cfg(tmp_path, FakeLLM('太郎が地図を渡した。次郎が本を燃やした。')), '太郎は何を買った？')
    v = res['vera']
    assert v['outcome']['outcome'] == 'TESTIMONY' and v['outcome']['outcome'] not in G.ANSWER_OUTCOMES
    kinds = [p['sentence_kind'] for p in v['provenance']]
    assert kinds == ['record', 'testimony']
    counts = v['outcome']['basis_policy']['counts']
    assert counts['human'] == 0 and counts['non_evidence'] == 1                # the policy was handed the testimony sentence only
    assert v['outcome']['basis_policy']['basis'] == 'NONE'


def test_unreadable_sentence_is_marked_unread(place, tmp_path):
    res = run(make_cfg(tmp_path, FakeLLM('たぶんそうかもしれないけれど、よく分からない。')), '太郎は何を買った？')
    p = res['vera']['provenance']
    assert p and all(x['mark'] == 'UNREAD' and x['read'] is False and x['sentence_kind'] == 'testimony' for x in p)
    assert res['vera']['outcome']['outcome'] == 'TESTIMONY'


def test_negated_record_sentence_is_not_a_record(place, tmp_path):
    items = G.verify('太郎が地図を渡さなかった。', G.load_records([docfile(tmp_path)]), 'factual', 'm')
    assert items[0]['sentence_kind'] == 'testimony'


def test_default_arm_level_marks(place, tmp_path):
    items = G.verify('太郎が本を渡した。', G.load_records([docfile(tmp_path)]), 'factual', 'm')
    arms = items[0]['arms']
    assert items[0]['sentence_kind'] == 'testimony' and arms['agent']['kind'] == 'record' and arms['patient']['kind'] == 'testimony'
    assert arms['agent']['evidence'] == ['d.txt#1:1'] and items[0]['center_kind'] == 'record'


def test_llm_unavailable_is_a_type_and_not_an_exception(place, tmp_path):
    for strict, q in ((False, '太郎は何を買った？'), (True, '誰が地図を渡した？')):
        res = run(make_cfg(tmp_path, FakeLLM(ok=False), strict=strict), q)
        assert res['vera']['outcome']['outcome'] == 'LLM_UNAVAILABLE' and res['content'] == G.FIXED_TEXT['LLM_UNAVAILABLE']
        assert res['vera']['llm']['error']['type'] == 'CONNECT_FAILED'


def test_a_raising_llm_is_typed_too(place, tmp_path):
    def boom(model, messages, fmt):
        raise RuntimeError('x')
    res = run(make_cfg(tmp_path, boom), '太郎は何を買った？')
    assert res['vera']['outcome']['outcome'] == 'LLM_UNAVAILABLE'


def test_empty_llm_answer(place, tmp_path):
    assert run(make_cfg(tmp_path, FakeLLM('  ')), '太郎は何を買った？')['vera']['outcome']['outcome'] == 'LLM_EMPTY'


# ---- 創作・言い換え ------------------------------------------------------------------------------------------------------------------------

def test_creative_default_is_constructed_with_the_fixed_mark(place, tmp_path):
    llm = FakeLLM('太郎は地図を持って旅に出ました。')
    res = run(make_cfg(tmp_path, llm), '太郎の短い話を書いて。', request_kind='creative')
    v = res['vera']
    assert v['outcome']['outcome'] == 'CONSTRUCTED' and res['content'].startswith(G.MARK_CONSTRUCTED + '\n')
    assert v['outcome']['outcome'] not in G.ANSWER_OUTCOMES and v['outcome']['basis_policy']['outcome'] == 'CONSTRUCTED'
    assert v['reading']['type'] == 'RECORDS' and all(p['sentence_kind'] != 'testimony' for p in v['provenance'])
    sys_msg = llm.calls[0]['messages'][0]
    assert sys_msg['role'] == 'system' and '太郎が地図を渡した。' in sys_msg['content'] and llm.calls[0]['fmt'] is None


def test_creative_without_documents_is_still_constructed_in_the_default_layer(place, tmp_path):
    res = run(make_cfg(tmp_path, FakeLLM('昔々あるところに。'), docs=[]), '話を書いて', request_kind='paraphrase')
    assert res['vera']['outcome']['outcome'] == 'CONSTRUCTED' and res['content'].startswith(G.MARK_CONSTRUCTED)


def test_creative_strict_vocabulary_in_grammar_is_constructed(place, tmp_path):
    toks = ['太郎', 'が', '地図', 'を', '渡し', 'た', '。']
    cfg = make_cfg(tmp_path, FakeLLM(json.dumps({'answer': toks}, ensure_ascii=False)), strict=True)
    res = run(cfg, '言い換えて', request_kind='paraphrase')
    v = res['vera']
    assert v['grammar']['kind'] == 'vocabulary' and set(toks) <= set(v['grammar']['json_schema']['properties']['answer']['items']['enum'])
    assert gbnf_literals(v['grammar']['gbnf']) == v['grammar']['json_schema']['properties']['answer']['items']['enum']
    assert v['outcome']['outcome'] == 'CONSTRUCTED' and res['content'] == G.MARK_CONSTRUCTED + '\n太郎が地図を渡した。'


def test_creative_strict_english_only_documents_are_not_supported(place, tmp_path):
    llm = FakeLLM()
    cfg = make_cfg(tmp_path, llm, strict=True, text='Alice gave Bob a map.\n')
    v = run(cfg, 'write a story', request_kind='creative')['vera']
    assert llm.calls == [] and v['reading']['type'] == 'STRUCTURE_UNDETERMINED' and v['reading']['state'] == 'CREATIVE_LANG_NOT_SUPPORTED'


# ---- 入力の検査 ----------------------------------------------------------------------------------------------------------------------------

def test_bad_inputs_are_typed(place, tmp_path):
    cfg = make_cfg(tmp_path, FakeLLM())
    with pytest.raises(VS.FusionBadRequest) as e:
        VS.fusion_turn(msg('x'), {'request_kind': 'chatty'}, cfg)
    assert e.value.error == 'BAD_REQUEST_KIND'
    with pytest.raises(VS.FusionBadRequest) as e:
        VS.fusion_turn([{'role': 'assistant', 'content': 'x'}], None, cfg)
    assert e.value.error == 'NO_USER_MESSAGE'
    with pytest.raises(VS.FusionBadRequest) as e:
        VS.fusion_turn('x', None, cfg)
    assert e.value.error == 'BAD_MESSAGES'
    with pytest.raises(VS.FusionBadRequest) as e:
        VS.fusion_turn(msg('x'), {'human_present': 'yes'}, cfg)
    assert e.value.error == 'BAD_HUMAN_PRESENT'


def test_list_content_is_read_and_only_the_last_user_message_is_the_question(place, tmp_path):
    llm = FakeLLM('分かりません。')
    cfg = make_cfg(tmp_path, llm)
    msgs = [{'role': 'user', 'content': '誰が地図を渡した？'}, {'role': 'assistant', 'content': '太郎です'},
            {'role': 'user', 'content': [{'type': 'text', 'text': '太郎は何を'}, {'type': 'text', 'text': '買った？'}]}]
    res = VS.fusion_turn(msgs, None, cfg)
    assert res['vera']['reading']['type'] == 'NO_RECORD' and len(llm.calls) == 1
    assert [m['role'] for m in llm.calls[0]['messages']] == ['system', 'user', 'assistant', 'user']        # layer 0 hands the whole conversation to the LLM, behind the document system message (W16-t3 K650)
    assert llm.calls[0]['messages'][1:] == [{'role': 'user', 'content': '誰が地図を渡した？'}, {'role': 'assistant', 'content': '太郎です'}, {'role': 'user', 'content': '太郎は何を買った？'}]


# ---- HTTP ----------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def server(place, tmp_path):
    def start(cfg):
        store = CrossStore()
        handler = VS.make_handler(store, lambda: None, 'm', None, GapGraph.load(tmp_path / 'g.json'), lambda: None,
                                  InterventionLog.load(tmp_path / 'i.json'), lambda: None, ToolCallQuarantine.load(tmp_path / 't.json'), lambda: None,
                                  **({'fusion': cfg} if cfg is not None else {}))
        httpd = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        started.append(httpd)
        return 'http://127.0.0.1:%d' % httpd.server_address[1]
    started = []
    yield start
    for h in started:
        h.shutdown()
        h.server_close()


def post(url, path, body):
    req = urllib.request.Request(url + path, data=json.dumps(body, ensure_ascii=False).encode('utf-8'), headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode('utf-8'), r.headers
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode('utf-8'), exc.headers


def test_http_openai_shape(server, tmp_path):
    url = server(make_cfg(tmp_path, FakeLLM('分かりません。')))
    st, raw, _h = post(url, '/v1/chat/completions', {'model': 'x', 'messages': msg('誰が地図を渡した？')})
    body = json.loads(raw)
    assert st == 200 and body['object'] == 'chat.completion' and body['id'].startswith('chatcmpl-') and body['model'] == 'fake-model'
    assert body['choices'][0]['message'] == {'role': 'assistant', 'content': '太郎が地図を渡した。'} and body['choices'][0]['finish_reason'] == 'stop'
    assert body['vera']['outcome']['outcome'] == 'ANSWER_HUMAN_BASIS' and body['vera']['schema'] == 'verantyx.fusion/1'
    assert set(body['vera']['timing']) == {'vera_ms', 'llm_ms'}


def test_http_openai_stream_ends_with_done_and_carries_vera(server, tmp_path):
    url = server(make_cfg(tmp_path, FakeLLM('次郎が本を読んだ。')))
    st, raw, h = post(url, '/v1/chat/completions', {'messages': msg('太郎は何を買った？'), 'stream': True})
    events = [e for e in raw.split('\n\n') if e]
    assert st == 200 and h['Content-Type'] == 'text/event-stream' and events[-1] == 'data: [DONE]'
    chunks = [json.loads(e[len('data: '):]) for e in events[:-1]]
    assert all(c['object'] == 'chat.completion.chunk' for c in chunks)
    assert chunks[0]['choices'][0]['delta']['content'] == G.MARK_TESTIMONY + '\n次郎が本を読んだ。\n（記録で確かめられません）'
    assert chunks[-1]['choices'][0]['finish_reason'] == 'stop' and chunks[-1]['vera']['outcome']['outcome'] == 'TESTIMONY'


def test_http_ollama_default_is_ndjson(server, tmp_path):
    url = server(make_cfg(tmp_path, FakeLLM('次郎が本を読んだ。')))
    st, raw, _h = post(url, '/api/chat', {'model': 'x', 'messages': msg('太郎は何を買った？')})
    lines = [json.loads(x) for x in raw.splitlines()]
    assert st == 200 and lines[-1]['done'] is True and 'vera' in lines[-1] and lines[0]['done'] is False
    assert lines[0]['message']['content'].endswith('次郎が本を読んだ。\n（記録で確かめられません）') and lines[-1]['done_reason'] == 'stop'


def test_http_ollama_stream_false_is_one_object(server, tmp_path):
    url = server(make_cfg(tmp_path, FakeLLM('x')))
    st, raw, _h = post(url, '/api/chat', {'messages': msg('誰が地図を渡した？'), 'stream': False})
    body = json.loads(raw)
    assert st == 200 and body['done'] is True and body['message']['content'] == '太郎が地図を渡した。' and body['vera']['outcome']['outcome'] == 'ANSWER_HUMAN_BASIS'


def shown_texts(raw):
    """応答からクライアントに見える本文（message.content / delta.content）だけを集める。vera 欄は含めない。"""
    objs = []
    for part in raw.replace('data: ', '').split('\n'):
        part = part.strip()
        if part and part != '[DONE]':
            objs.append(json.loads(part))
    out = []
    for o in objs:
        for ch in o.get('choices', []):
            out.append((ch.get('message') or ch.get('delta') or {}).get('content') or '')
        out.append((o.get('message') or {}).get('content') or '')
    return out


def test_http_strict_never_leaks_the_llm_sentence_to_the_client(server, tmp_path):
    for path, body in (('/v1/chat/completions', {'stream': True}), ('/v1/chat/completions', {}), ('/api/chat', {}), ('/api/chat', {'stream': False})):
        url = server(make_cfg(tmp_path, FakeLLM('{"answer": "次郎が地図を渡した。"}'), strict=True))
        st, raw, _h = post(url, path, dict(body, messages=msg('誰が地図を渡した？')))
        texts = shown_texts(raw)
        assert st == 200 and any(texts) and not any('次郎' in t for t in texts), (path, body, texts)
        assert G.FIXED_TEXT['OUTSIDE_GRAMMAR'] in texts


def test_http_without_fusion_the_new_routes_are_404(server):
    url = server(None)
    for path in ('/v1/chat/completions', '/api/chat'):
        st, raw, _h = post(url, path, {'messages': msg('x')})
        assert st == 404 and json.loads(raw) == {'ok': False, 'error': 'not_found'}
    for path in ('/v1/models', '/api/tags'):
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(url + path, timeout=10)
        assert e.value.code == 404


def test_http_bad_request_kind_and_bad_json(server, tmp_path):
    url = server(make_cfg(tmp_path, FakeLLM()))
    st, raw, _h = post(url, '/v1/chat/completions', {'messages': msg('x'), 'vera': {'request_kind': 'nope'}})
    assert st == 400 and json.loads(raw)['error'] == 'BAD_REQUEST_KIND'
    req = urllib.request.Request(url + '/api/chat', data=b'{not json', headers={'Content-Type': 'application/json'})
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(req, timeout=10)
    assert e.value.code == 400


def test_http_models_and_tags(server, tmp_path):
    url = server(make_cfg(tmp_path, FakeLLM()))
    assert json.loads(urllib.request.urlopen(url + '/v1/models', timeout=10).read())['data'][0]['id'] == 'fake-model'
    assert json.loads(urllib.request.urlopen(url + '/api/tags', timeout=10).read())['models'][0]['name'] == 'fake-model'


def test_http_existing_routes_still_answer_as_before(server, tmp_path):
    url = server(make_cfg(tmp_path, FakeLLM()))
    st, raw, _h = post(url, '/agent/run', {})
    assert st == 400 and json.loads(raw) == {'ok': False, 'error': 'missing_task'}
    st, raw, _h = post(url, '/nope', {})
    assert st == 404 and json.loads(raw) == {'ok': False, 'error': 'not_found'}


# ---- Ollama の呼び出し（HTTP は標準ライブラリ。失敗は型つき）----------------------------------------------------------------------------------

def test_ollama_chat_failure_types():
    r = VS._ollama_chat('http://127.0.0.1:1', 'm', msg('x'), None, timeout=2)
    assert r['ok'] is False and r['error']['type'] == 'CONNECT_FAILED'

    class Slow(ThreadingHTTPServer):
        pass

    from http.server import BaseHTTPRequestHandler
    import time

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            n = int(self.headers.get('Content-Length', '0'))
            self.rfile.read(n)
            if self.path == '/api/chat' and getattr(self.server, 'mode') == 'slow':
                time.sleep(1.5)
            data = {'slow': b'{}', 'bad': b'not json', 'err': b'boom', 'ok': json.dumps({'message': {'content': 'hi'}, 'prompt_eval_count': 3, 'eval_count': 2}).encode()}[self.server.mode]
            self.send_response(500 if self.server.mode == 'err' else 200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except OSError:
                pass

    httpd = Slow(('127.0.0.1', 0), H)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = 'http://127.0.0.1:%d' % httpd.server_address[1]
    try:
        for mode, want in (('slow', 'TIMEOUT'), ('bad', 'BAD_RESPONSE'), ('err', 'HTTP_ERROR')):
            httpd.mode = mode
            r = VS._ollama_chat(url, 'm', msg('x'), None, timeout=0.5 if mode == 'slow' else 5)
            assert r['ok'] is False and r['error']['type'] == want, (mode, r)
        httpd.mode = 'ok'
        r = VS._ollama_chat(url, 'm', msg('x'), {'type': 'object'}, timeout=5)
        assert r == {'ok': True, 'content': 'hi', 'error': None, 'usage': {'prompt_tokens': 3, 'completion_tokens': 2, 'total_tokens': 5}}
    finally:
        httpd.shutdown()
        httpd.server_close()


# ---- CLI -----------------------------------------------------------------------------------------------------------------------------------

@pytest.fixture
def fake_serve(monkeypatch):
    calls = []

    def fake(st, save, **kw):
        calls.append(kw)
        return 0
    monkeypatch.setattr(VS, 'serve', fake)
    return calls


def cli_run(capsys, *argv):
    capsys.readouterr()
    rc = cli.main(list(argv))
    return rc, capsys.readouterr().out


def test_cli_top_level_store_survives_serve(tmp_path, fake_serve, capsys, monkeypatch):
    seen = {}
    real = cli.cmd_serve

    def spy(args):
        seen['store'] = args.store
        return real(args)
    monkeypatch.setattr(cli, 'cmd_serve', spy)
    st = str(tmp_path / 'X.json')
    rc, _ = cli_run(capsys, '--store', st, 'serve', '--backend', 'ollama', '--model', 'm', '--port', '1')
    assert rc == 0 and seen['store'] == st and fake_serve[0]['store_path'] == Path(st)
    assert fake_serve[0]['fusion'].model == 'm' and fake_serve[0]['fusion'].strict is False


def test_cli_without_backend_calls_serve_exactly_as_before(tmp_path, fake_serve, capsys):
    st = str(tmp_path / 'Y.json')
    rc, _ = cli_run(capsys, '--store', st, 'serve', '--port', '4321', '--llm', 'qq', '--jgen-endpoint', 'http://e')
    assert rc == 0 and fake_serve == [{'port': 4321, 'default_model': 'qq', 'jgen_endpoint': 'http://e', 'store_path': Path(st)}]


def test_cli_fusion_options_and_refusals(tmp_path, fake_serve, capsys, monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_SOVEREIGN_ROOT', raising=False)
    monkeypatch.delenv('VERA_SOVEREIGN_STORE', raising=False)
    st = str(tmp_path / 'Z.json')
    base = ['--store', st, 'serve', '--backend', 'ollama']
    rc, out = cli_run(capsys, *base)
    assert rc == 2 and json.loads(out)['verdict'] == 'MODEL_REQUIRED'
    rc, out = cli_run(capsys, *base, '--model', 'm', '--strict', '--free')
    assert rc == 2 and json.loads(out)['verdict'] == 'STRICT_AND_FREE'
    rc, out = cli_run(capsys, *base, '--model', 'm', '--document', str(tmp_path / 'nope.txt'))
    assert rc == 2 and json.loads(out)['verdict'] == 'DOCUMENT_NOT_FOUND'
    rc, out = cli_run(capsys, *base, '--model', 'm', '--sovereign-root', str(tmp_path))
    assert rc == 2 and json.loads(out)['verdict'] == 'SOVEREIGN_NEEDS_BOTH'
    assert fake_serve == []
    d = docfile(tmp_path)
    rc, _ = cli_run(capsys, *base, '--model', 'm', '--document', d, '--strict', '--placement', str(tmp_path), '--sovereign-root', str(tmp_path), '--sovereign-store', 'S1')
    import os
    assert rc == 0 and fake_serve[0]['fusion'].strict is True and fake_serve[0]['fusion'].documents == [d] and fake_serve[0]['fusion'].records.n_loaded == 1
    assert os.environ['VERA_PLACEMENT'] == str(tmp_path) and os.environ['VERA_SOVEREIGN_STORE'] == 'S1'
    monkeypatch.delenv('VERA_PLACEMENT'), monkeypatch.delenv('VERA_SOVEREIGN_ROOT'), monkeypatch.delenv('VERA_SOVEREIGN_STORE')


# ---- max_tokens（層 0 の自由な答えだけに効く。文法は自分で出力を縛る）---------------------------------------------------------------------------

def test_max_tokens_is_validated_and_reaches_the_llm_call(place, tmp_path, monkeypatch):
    seen = []

    def fake_ollama(url, model, messages, fmt, timeout=180.0, max_tokens=None):
        seen.append((fmt, max_tokens))
        return {'ok': True, 'content': 'はい。', 'error': None, 'usage': {}}
    monkeypatch.setattr(VS, '_ollama_chat', fake_ollama)
    plain = VS.FusionConfig.load(model='m', documents=[docfile(tmp_path)])
    VS.fusion_turn(msg('太郎は何を買った？'), None, plain, 50)
    assert seen == [(G.QUOTE_SCHEMA, 50)]
    for bad in (0, -1, '5', True, 1.5):
        with pytest.raises(VS.FusionBadRequest) as e:
            VS.fusion_turn(msg('x'), None, plain, bad)
        assert e.value.error == 'BAD_MAX_TOKENS'


def test_ollama_chat_sends_num_predict_only_without_a_format(monkeypatch):
    sent = []

    class R:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({'message': {'content': 'x'}}).encode()

    def fake_urlopen(req, timeout=None):
        sent.append(json.loads(req.data))
        return R()
    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)
    VS._ollama_chat('http://x', 'm', msg('q'), None, 5, 33)
    VS._ollama_chat('http://x', 'm', msg('q'), {'type': 'object'}, 5, 33)
    assert sent[0]['options'] == {'temperature': 0, 'num_predict': 33} and 'format' not in sent[0] and sent[0]['think'] is False and sent[0]['stream'] is False
    assert sent[1]['options'] == {'temperature': 0} and sent[1]['format'] == {'type': 'object'}


# ---- r2 必須 1: Vera の側の処理は専用の 1 本のスレッドだけ（配置の SQLite 接続はスレッドをまたげない）-----------------------------------------------

class ThreadBoundPlacement:
    """最初に引かれたスレッドを持ち主とし、別のスレッドから使われたら sqlite3 と同じ ProgrammingError を投げる偽の配置。"""

    def __init__(self, inner):
        object.__setattr__(self, '_inner', inner)
        object.__setattr__(self, '_owner', threading.get_ident())

    def __getattr__(self, name):
        if threading.get_ident() != self._owner:
            import sqlite3
            raise sqlite3.ProgrammingError('SQLite objects created in a thread can only be used in that same thread')
        return getattr(self._inner, name)


@pytest.fixture
def thread_bound_place(place, monkeypatch):
    """起動時の文書の読み込み（`G.load_records`）が、配置を引く（= 配置を開く）。持ち主はその読み込みを実行したスレッド。"""
    holder = {}

    def lookup(*a, **k):
        if 'p' not in holder:
            holder['p'] = ThreadBoundPlacement(place)
        return holder['p']
    monkeypatch.setattr(EC, 'default_lookup', lookup)
    real_load = G.load_records

    def load_and_open(documents):
        records = real_load(documents)
        EC.default_lookup()                                     # the placement is opened on the thread that loaded the documents
        return records
    monkeypatch.setattr(G, 'load_records', load_and_open)
    return holder


def test_concurrent_http_requests_read_on_the_one_vera_thread(thread_bound_place, server, tmp_path):
    release = threading.Event()
    entered = threading.Event()

    def slow(messages, fmt):
        if not entered.is_set():                               # only request 1 waits; a request 2 that wrongly reaches the LLM must not hang the test
            entered.set()
            assert release.wait(30)
        return '分かりません。'
    cfg = make_cfg(tmp_path, FakeLLM(slow))
    url = server(cfg)
    first = {}

    def call_first():
        first['r'] = post(url, '/v1/chat/completions', {'messages': msg('太郎は何を買った？')})
    t = threading.Thread(target=call_first)
    t.start()
    assert entered.wait(30)                                    # request 1 is alive (waiting inside the LLM) ...
    st2, raw2, _h = post(url, '/v1/chat/completions', {'messages': msg('誰が地図を渡した？')})        # ... while request 2 is read on another request thread
    release.set()
    t.join(30)
    v2 = json.loads(raw2)['vera']
    assert st2 == 200 and v2['reading']['type'] == 'QUESTION_CROSS' and v2['outcome']['outcome'] == 'ANSWER_HUMAN_BASIS'
    v1 = json.loads(first['r'][1])['vera']
    assert first['r'][0] == 200 and v1['reading']['type'] == 'NO_RECORD' and v1['reading']['state'] == 'NO_ATTESTED_CELL'
    assert thread_bound_place['p']._owner in {t.ident for t in cfg._vera_thread._threads}      # opened on the vera thread, never on a request thread
    for v in (v1, v2):
        assert v['reading']['state'] != 'ERROR'


def test_thread_bound_placement_really_fails_off_the_vera_thread(thread_bound_place, tmp_path):
    """対照: 偽の配置が本当に別スレッドで落とす（上のテストが空振りでないことの確認）。"""
    cfg = make_cfg(tmp_path, FakeLLM())
    reading, _qc = G.read_turn('誰が地図を渡した？', 'factual', cfg.records, cfg.documents)      # main thread, not the vera thread
    assert reading['type'] == 'STRUCTURE_UNDETERMINED' and reading['state'] == 'ERROR' and 'ProgrammingError' in reading['reason']


# ---- r2 必須 2: 回数などの修飾（quantifiers）も十字の一部。記録に無い回数の文に記録の印を付けない --------------------------------------------------

QDOC = '弟が犬を呼んだ。\n'


@pytest.mark.parametrize('kind', ['factual', 'creative'])
def test_verify_does_not_mark_a_sentence_with_an_extra_count_as_record(place, tmp_path, kind):
    cfg = make_cfg(tmp_path, FakeLLM(), text=QDOC)
    same = G.verify('弟が犬を呼んだ。', cfg.records, kind, 'm')[0]
    assert same['sentence_kind'] == 'record' and same['evidence'] == ['d.txt#1:1']                 # the record itself still is
    for text in ('弟が犬を三回呼んだ。', '弟が犬を十回呼んだ。', '弟が犬を5回呼んだ。'):
        item = G.verify(text, cfg.records, kind, 'm')[0]
        assert item['read'] and item['sentence_kind'] != 'record' and item['evidence'] == [], (text, item)
        assert item['arms']['agent']['kind'] == 'record' and item['arms']['patient']['kind'] == 'record'     # the arms are in the record; the sentence is not


def test_layer0_llm_sentence_with_an_extra_count_is_not_record_marked(place, tmp_path):
    for rk in ('factual', 'creative'):
        res = run(make_cfg(tmp_path, FakeLLM('弟が犬を三回呼んだ。'), text=QDOC), '弟は犬を何回呼んだ？' if rk == 'factual' else '犬の話を書いて', request_kind=rk)
        assert res['vera']['provenance'][0]['sentence_kind'] != 'record', (rk, res['vera']['provenance'])
        assert res['vera']['outcome']['outcome'] in ('TESTIMONY', 'CONSTRUCTED')


def test_the_candidate_check_of_layer1_also_sees_quantifiers(place, tmp_path):
    cfg = make_cfg(tmp_path, FakeLLM(), text=QDOC)
    src = cfg.records.crosses['d.txt#1:1']
    assert G._candidate_ok('弟が犬を呼んだ。', src, 'agent', '弟')
    assert not G._candidate_ok('弟が犬を三回呼んだ。', src, 'agent', '弟')


# ---- r2 必須 3: vera 欄の鍵の集合が docs/FUSION.md §1.6 の一覧と等しい ----------------------------------------------------------------------------

VERA_KEYS = {'schema', 'layer', 'request_kind', 'reading', 'grammar', 'grammar_id', 'llm', 'grammar_check', 'provenance', 'outcome', 'timing'}
READING_KEYS = {'type', 'state', 'reason', 'hole_role', 'hole_type', 'filler', 'sources'}
LLM_KEYS = {'called', 'model', 'ok', 'error', 'raw', 'withheld', 'skipped_reason'}
GCHECK_KEYS = {'in_grammar', 'reason'}
OUTCOME_KEYS = {'outcome', 'content_shown', 'reason', 'basis_policy'}
GRAMMAR_KEYS = {'id', 'kind', 'summary', 'json_schema', 'gbnf'}
PROV_COMMON = {'text', 'read', 'mark', 'unread_reason', 'sentence_kind', 'origin', 'evidence', 'arms', 'center_kind', 'via'}
PROV_READ = {'center'}                       # only for a sentence that could be read
PROV_TESTIMONY = {'source'}                  # only for a sentence that is not a record in a factual request
ARM_KEYS = {'surface', 'kind', 'evidence'}


def test_vera_field_keys_are_the_documented_ones_layer0_and_layer1(place, tmp_path):
    l0 = run(make_cfg(tmp_path, FakeLLM('太郎は本を買った。')), '太郎は何を買った？')['vera']
    assert set(l0) == VERA_KEYS | {'quote_check'} and set(l0['reading']) == READING_KEYS and set(l0['llm']) == LLM_KEYS
    assert set(l0['grammar_check']) == GCHECK_KEYS and set(l0['outcome']) == OUTCOME_KEYS and l0['grammar'] is None
    p = l0['provenance'][0]
    assert set(p) == PROV_COMMON | PROV_READ | PROV_TESTIMONY and set(p['source']) == {'family', 'origin', 'model'}
    assert all(set(a) == ARM_KEYS for a in p['arms'].values())
    assert set(l0['timing']) == {'vera_ms', 'llm_ms'}
    l1 = run(make_cfg(tmp_path, FakeLLM('{"answer": "太郎が地図を渡した。"}'), strict=True), '誰が地図を渡した？')['vera']
    assert set(l1) == VERA_KEYS and set(l1['grammar']) == GRAMMAR_KEYS and set(l1['reading']) == READING_KEYS
    q = l1['provenance'][0]
    assert set(q) == PROV_COMMON | PROV_READ and q['sentence_kind'] == 'record' and q['via'] == 'cross' and q['evidence'] == ['d.txt#1:1']
    assert set(l1['reading']['sources'][0]) == {'source', 'line', 'text', 'sentence_id'}
    unread = run(make_cfg(tmp_path, FakeLLM('ええと')), '太郎は何を買った？')['vera']['provenance'][0]
    assert unread['mark'] == 'UNREAD' and set(unread) == PROV_COMMON | PROV_TESTIMONY and unread['unread_reason']


def test_http_api_version_and_bad_content_length(server, tmp_path):
    url = server(make_cfg(tmp_path, FakeLLM()))
    assert json.loads(urllib.request.urlopen(url + '/api/version', timeout=10).read()) == {'version': 'vera-fusion'}
    import http.client
    conn = http.client.HTTPConnection(url.split('//')[1], timeout=10)
    conn.putrequest('POST', '/api/chat')
    conn.putheader('Content-Length', 'abc')
    conn.endheaders()
    resp = conn.getresponse()
    assert resp.status == 400 and json.loads(resp.read())['error'] == 'bad_json'
    conn.close()
    plain = server(None)
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(plain + '/api/version', timeout=10)
    assert e.value.code == 404
