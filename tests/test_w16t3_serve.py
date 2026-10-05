"""W16-t3 (K650-K653, docs/FUSION.md §9): 層 0 の事実の問いに文書を渡し、{answer, quotes} の返答を照合して `vera.quote_check` に載せる結線。
LLM は偽。fixture と FakeLLM は tests/test_serve_fusion.py と同じ作りをここに写してある（import しない）。No test is skipped."""
import json
import urllib.request
from pathlib import Path

import pytest

from verantyx import decode_grammar as G
from verantyx import event_cross as EC
from verantyx import llm_backend as LB
from verantyx import observe as O
from verantyx import vera_server as VS

DOC = "会議は2026年4月1日に開く。\n参加費は3,000円である。\n担当は久保田澄江さんである。\n太郎が地図を渡した。\n"
PLACE = {"太郎": "PERSON", "花子": "PERSON", "次郎": "PERSON", "地図": "ARTIFACT"}
Q = "参加費はいくらですか？"


class FakeLLM:
    def __init__(self, reply="", ok=True):
        self.reply, self.ok, self.calls = reply, ok, []

    def __call__(self, model, messages, fmt):
        self.calls.append({"model": model, "messages": messages, "fmt": fmt})
        if not self.ok:
            return {"ok": False, "content": None, "error": {"type": "CONNECT_FAILED", "detail": "fake"}}
        return {"ok": True, "content": self.reply, "error": None, "usage": {}}


@pytest.fixture
def place(tmp_path, monkeypatch):
    monkeypatch.delenv("VERA_PLACEMENT", raising=False)
    monkeypatch.delenv("VERA_SOVEREIGN_ROOT", raising=False)
    monkeypatch.delenv("VERA_SOVEREIGN_STORE", raising=False)
    path = Path(tmp_path) / "pl.json"
    path.write_text(json.dumps({"lemmas": {w: {"state": "DECIDED", "origin": "direct", "types": [t]} for w, t in PLACE.items()}, "neighbors": {}}, ensure_ascii=False), encoding="utf-8")
    fp = O.FilePlacement.from_path(str(path))
    monkeypatch.setattr(EC, "default_lookup", lambda *a, **k: fp)
    return fp


def cfg_for(tmp_path, llm, *, strict=False, docs=True):
    p = Path(tmp_path) / "d.txt"
    p.write_text(DOC, encoding="utf-8")
    return VS.FusionConfig.load(model="fake-model", documents=[str(p)] if docs else [], strict=strict, llm_chat=llm)


def turn(cfg, q=Q, **vera):
    return VS.fusion_turn([{"role": "user", "content": q}], vera or None, cfg)


def reply(answer, quotes):
    return json.dumps({"answer": answer, "quotes": quotes}, ensure_ascii=False)


GOOD = [{"source": "d.txt", "line": 2, "text": "参加費は3,000円である。"}]


def test_documents_reach_the_llm_with_the_quote_schema_and_the_reply_is_checked(place, tmp_path):
    llm = FakeLLM(reply("3,000円", GOOD))
    out = turn(cfg_for(tmp_path, llm))
    call = llm.calls[0]
    assert call["fmt"] == G.QUOTE_SCHEMA
    assert call["messages"][0]["role"] == "system" and "[d.txt:2] 参加費は3,000円である。" in call["messages"][0]["content"]
    assert call["messages"][1:] == [{"role": "user", "content": Q}]
    v = out["vera"]
    keys = list(v)
    assert keys[keys.index("outcome") + 1] == "quote_check" and keys[keys.index("quote_check") + 1:] == ["timing"]     # conclude の最後の鍵（timing は serve が後から足す）
    qc = v["quote_check"]
    assert qc["verdict"] == "anchored" and qc["quotes"][0]["found"] == "exact"
    assert qc["elements"] == [{"kind": "number", "value": "3000円", "found_in": ["d.txt:2"]}]
    assert out["content"] == G.MARK_TESTIMONY + "\n3,000円\n（引用の出典: d.txt:2）"
    assert v["outcome"]["outcome"] == "TESTIMONY"
    prov = [p for p in v["provenance"] if p["sentence_kind"] != "record"]
    assert prov and all(p["origin"] == "testimony" and p["anchored_testimony"] == {"quotes": ["d.txt:2"]} for p in prov)


def test_a_wrong_value_with_a_real_quote_is_a_conflict_line(place, tmp_path):
    out = turn(cfg_for(tmp_path, FakeLLM(reply("5,000円", GOOD))))
    assert out["vera"]["quote_check"]["verdict"] == "conflict"
    assert out["content"] == G.MARK_TESTIMONY + "\n5,000円\n（記録と食い違います: d.txt:2「3000円」）"
    assert all("anchored_testimony" not in p for p in out["vera"]["provenance"])


def test_a_fabricated_quote_is_unanchored_and_says_so(place, tmp_path):
    out = turn(cfg_for(tmp_path, FakeLLM(reply("3,000円", [{"source": "d.txt", "line": 2, "text": "参加費は4,000円である。"}]))))
    assert out["vera"]["quote_check"]["verdict"] == "unanchored"
    assert out["vera"]["quote_check"]["quotes"][0]["found"] == "fabricated"
    assert out["content"].endswith("\n（記録で確かめられません）")
    assert all("anchored_testimony" not in p for p in out["vera"]["provenance"])


def test_a_reply_that_is_not_json_is_unanchored_with_a_typed_reason_and_the_raw_text(place, tmp_path):
    out = turn(cfg_for(tmp_path, FakeLLM("3,000円です")))
    qc = out["vera"]["quote_check"]
    assert qc["verdict"] == "unanchored" and qc["reason"] == "REPLY_NOT_JSON" and qc["quotes"] == []
    assert out["content"] == G.MARK_TESTIMONY + "\n3,000円です\n（記録で確かめられません）"
    out = turn(cfg_for(tmp_path, FakeLLM(json.dumps({"answer": ["x"], "quotes": []}))))
    assert out["vera"]["quote_check"]["reason"] == "ANSWER_NOT_A_STRING"


def test_the_basis_policy_is_not_changed_by_the_check(place, tmp_path):
    """方針の入力は JSON の answer の本文だけ。引用が実在しても事実の問いの ANSWER の根拠にならない（証言のまま）。"""
    out = turn(cfg_for(tmp_path, FakeLLM(reply("3,000円", GOOD))))
    assert out["vera"]["outcome"]["outcome"] == "TESTIMONY" and out["vera"]["outcome"]["content_shown"] is True
    assert "読んだ" not in out["content"] and "正しい" not in out["content"]


# --- K653: quote_mode が偽の経路は基点のまま ----------------------------------------------------------------------------------------------------

def test_layer1_strict_has_no_quote_check_and_no_quote_schema(place, tmp_path):
    llm = FakeLLM("{}")
    out = turn(cfg_for(tmp_path, llm, strict=True), "誰が地図を渡した？")
    assert "quote_check" not in out["vera"]
    assert all(c["fmt"] is not G.QUOTE_SCHEMA for c in llm.calls)


@pytest.mark.parametrize("kind", ["creative", "paraphrase", "style", "example"])
def test_non_factual_requests_are_unchanged(place, tmp_path, kind):
    llm = FakeLLM("昔々。")
    out = turn(cfg_for(tmp_path, llm), "短い話を書いて", request_kind=kind)
    assert "quote_check" not in out["vera"] and llm.calls[0]["fmt"] is None
    assert llm.calls[0]["messages"][0] == {"role": "system", "content": "利用者の文書は次のとおりです。依頼はこの文書の内容に基づいて答えてください。\n" + "\n".join(
        "[d.txt:%d] %s" % (i, t) for i, t in enumerate(DOC.strip().split("\n"), 1))}


def test_no_documents_is_unchanged(place, tmp_path):
    llm = FakeLLM("次郎が地図を渡した。")
    out = turn(cfg_for(tmp_path, llm, docs=False), "誰が地図を渡した？")
    assert "quote_check" not in out["vera"] and llm.calls[0]["fmt"] is None
    assert llm.calls[0]["messages"] == [{"role": "user", "content": "誰が地図を渡した？"}]
    assert out["content"] == G.MARK_TESTIMONY + "\n次郎が地図を渡した。"


def test_a_question_the_record_answers_does_not_call_the_llm(place, tmp_path):
    llm = FakeLLM("x")
    out = turn(cfg_for(tmp_path, llm), "誰が地図を渡した？")
    assert llm.calls == [] and "quote_check" not in out["vera"]
    assert out["content"] == "太郎が地図を渡した。"


def test_quote_format_is_none_when_quote_mode_is_false(place, tmp_path):
    cfg = cfg_for(tmp_path, FakeLLM(""), docs=False)
    t = G.plan_turn(Q, "factual", cfg.records, cfg.documents, strict=False)
    assert G.quote_format(t, cfg.records) is None and G.quote_mode(t, cfg.records) is False


# --- OpenAI 互換: strict で通る形 -------------------------------------------------------------------------------------------------------------

def _objects(schema):
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            yield schema
        for v in schema.values():
            yield from _objects(v)
    elif isinstance(schema, list):
        for v in schema:
            yield from _objects(v)


class Resp:
    def __init__(self, body):
        self.body = json.dumps(body).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_openai_response_format_is_strict_and_the_schema_is_strict_clean(monkeypatch):
    seen = []

    def urlopen(req, timeout=None):
        seen.append(json.loads(req.data.decode()))
        return Resp({"choices": [{"message": {"content": "{}"}}]})
    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    LB._openai_chat("https://api.example.test/v1", "K", "m", [{"role": "user", "content": "x"}], G.QUOTE_SCHEMA)
    rf = seen[0]["response_format"]
    assert rf == {"type": "json_schema", "json_schema": {"name": "vera", "schema": G.QUOTE_SCHEMA, "strict": True}}
    objs = list(_objects(rf["json_schema"]["schema"]))
    assert len(objs) == 2
    for o in objs:
        assert o["additionalProperties"] is False and sorted(o["required"]) == sorted(o["properties"])


# ---- 第 3 ラウンド 裁定 3: quote_mode の format でも num_predict／max_tokens を送る -------------------------------------------------------------

class _R:
    def __init__(self, obj):
        self.obj = obj

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self.obj).encode()


def test_ollama_sends_num_predict_with_the_quote_schema_only(monkeypatch):
    sent = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: (sent.append(json.loads(req.data)), _R({"message": {"content": "x"}}))[1])
    m = [{"role": "user", "content": "q"}]
    LB._ollama_chat("http://x", "m", m, G.QUOTE_SCHEMA, 5, 33)
    LB._ollama_chat("http://x", "m", m, dict(G.QUOTE_SCHEMA), 5, 33)          # 同じ形の別の dict（文法の経路）は今のまま
    LB._ollama_chat("http://x", "m", m, G.QUOTE_SCHEMA, 5, None)
    assert sent[0]["options"] == {"temperature": 0, "num_predict": 33} and sent[0]["format"] == G.QUOTE_SCHEMA
    assert sent[1]["options"] == {"temperature": 0} and sent[1]["format"] == G.QUOTE_SCHEMA
    assert sent[2]["options"] == {"temperature": 0}


def test_openai_sends_max_tokens_with_the_quote_schema_only(monkeypatch):
    sent = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout=None: (sent.append(json.loads(req.data.decode())), _R({"choices": [{"message": {"content": "{}"}}]}))[1])
    m = [{"role": "user", "content": "q"}]
    LB._openai_chat("https://api.example.test/v1", "K", "m", m, G.QUOTE_SCHEMA, 5, 33)
    LB._openai_chat("https://api.example.test/v1", "K", "m", m, dict(G.QUOTE_SCHEMA), 5, 33)
    assert sent[0]["max_tokens"] == 33 and sent[0]["response_format"]["json_schema"]["schema"] == G.QUOTE_SCHEMA
    assert "max_tokens" not in sent[1] and "response_format" in sent[1]


def test_fusion_turn_quote_mode_passes_the_quote_schema_and_max_tokens_to_the_backend(place, tmp_path, monkeypatch):
    seen = []

    def fake(url, model, msgs, fmt, timeout=180.0, max_tokens=None):
        seen.append((fmt, max_tokens))
        return {"ok": True, "content": reply("3,000円", GOOD), "error": None, "usage": {}}
    monkeypatch.setattr(VS, "_ollama_chat", fake)
    p = Path(tmp_path) / "d.txt"
    p.write_text(DOC, encoding="utf-8")
    cfg = VS.FusionConfig.load(model="fake-model", documents=[str(p)], strict=False)
    VS.fusion_turn([{"role": "user", "content": Q}], None, cfg, 50)
    assert len(seen) == 1 and seen[0][0] is G.QUOTE_SCHEMA and seen[0][1] == 50
