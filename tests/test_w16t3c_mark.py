"""W16-t3c (K655・K656, docs/FUSION.md §11): quote_check が anchored のときだけ、本文の頭の印を MARK_ANCHORED_TESTIMONY にする。
LLM は偽。fixture と FakeLLM は tests/test_w16t3_serve.py と同じ作りをここに写してある（import しない）。No test is skipped.
G.MARK_ANCHORED_TESTIMONY は試験関数の中でだけ参照する（直す前に収集エラーに潰れないように）。"""
import json
from pathlib import Path

import pytest

from verantyx import decode_grammar as G
from verantyx import event_cross as EC
from verantyx import observe as O
from verantyx import vera_server as VS

NEW = "［証言: LLM の答えです。引用した文は記録にあります（確かめたのは、引用の実在と、答えの数値・日付・固有名・内容語が引用に現れることだけで、答えの正しさではありません）］"
OLD = "［証言: LLM の答えです。記録の裏づけはありません］"
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


def cfg_for(tmp_path, llm, *, strict=False, docs=True, doc_text=DOC):
    p = Path(tmp_path) / "d.txt"
    p.write_text(doc_text, encoding="utf-8")
    return VS.FusionConfig.load(model="fake-model", documents=[str(p)] if docs else [], strict=strict, llm_chat=llm)


def turn(cfg, q=Q, **vera):
    return VS.fusion_turn([{"role": "user", "content": q}], vera or None, cfg)


def reply(answer, quotes):
    return json.dumps({"answer": answer, "quotes": quotes}, ensure_ascii=False)


GOOD = [{"source": "d.txt", "line": 2, "text": "参加費は3,000円である。"}]


def test_the_constant_is_the_ticket_wording_and_starts_with_the_testimony_prefix():
    assert G.MARK_ANCHORED_TESTIMONY == NEW
    assert G.MARK_ANCHORED_TESTIMONY.startswith("［証言")     # benchmarks/public_v1/score.py strips a first line that starts with this
    assert G.MARK_TESTIMONY == OLD


def test_anchored_reply_has_the_anchored_mark_on_the_first_line(place, tmp_path):
    out = turn(cfg_for(tmp_path, FakeLLM(reply("3,000円", GOOD))))
    assert out["content"] == NEW + "\n3,000円\n（引用の出典: d.txt:2）"
    assert out["content"].split("\n")[0] == NEW


def test_anchored_reply_keeps_the_vera_field_and_the_testimony_basis(place, tmp_path):
    out = turn(cfg_for(tmp_path, FakeLLM(reply("3,000円", GOOD))))
    v = out["vera"]
    keys = list(v)
    assert keys[keys.index("outcome") + 1] == "quote_check" and keys[keys.index("quote_check") + 1:] == ["timing"]
    assert v["quote_check"]["verdict"] == "anchored"
    assert v["outcome"]["outcome"] == "TESTIMONY"
    prov = [p for p in v["provenance"] if p["sentence_kind"] != "record"]
    assert prov and all(p["origin"] == "testimony" and p["anchored_testimony"] == {"quotes": ["d.txt:2"]} for p in prov)


def test_conflict_reply_keeps_the_old_mark(place, tmp_path):
    out = turn(cfg_for(tmp_path, FakeLLM(reply("5,000円", GOOD))))
    assert out["vera"]["quote_check"]["verdict"] == "conflict"
    assert out["content"] == G.MARK_TESTIMONY + "\n5,000円\n（記録と食い違います: d.txt:2「3000円」）"
    assert NEW not in out["content"]


def test_unanchored_reply_with_a_quote_that_does_not_exist_keeps_the_old_mark(place, tmp_path):
    bad = [{"source": "d.txt", "line": 2, "text": "参加費は4,000円である。"}]
    out = turn(cfg_for(tmp_path, FakeLLM(reply("3,000円", bad))))
    assert out["vera"]["quote_check"]["verdict"] == "unanchored"
    assert out["content"] == G.MARK_TESTIMONY + "\n3,000円\n（記録で確かめられません）"
    assert NEW not in out["content"]


def test_unanchored_reply_that_is_not_json_keeps_the_old_mark(place, tmp_path):
    out = turn(cfg_for(tmp_path, FakeLLM("3,000円です")))
    assert out["vera"]["quote_check"]["verdict"] == "unanchored"
    assert out["content"] == G.MARK_TESTIMONY + "\n3,000円です\n（記録で確かめられません）"


def test_strict_layer_is_unchanged(place, tmp_path):
    out = turn(cfg_for(tmp_path, FakeLLM(reply("3,000円", GOOD)), strict=True))
    assert NEW not in out["content"] and "quote_check" not in out["vera"]


def test_no_documents_is_unchanged(place, tmp_path):
    out = turn(cfg_for(tmp_path, FakeLLM("3,000円です"), docs=False))
    assert out["content"].startswith(G.MARK_TESTIMONY + "\n") and NEW not in out["content"]
    assert "（引用の出典" not in out["content"] and "quote_check" not in out["vera"]


def test_non_factual_request_is_unchanged(place, tmp_path):
    llm = FakeLLM("太郎は地図を持って旅に出ました。")
    out = turn(cfg_for(tmp_path, llm), "太郎の短い話を書いて。", request_kind="creative")
    assert out["content"].startswith(G.MARK_CONSTRUCTED + "\n") and NEW not in out["content"]
    assert "quote_check" not in out["vera"]


def test_only_the_prefix_is_replaced_when_the_answer_contains_the_old_mark(place, tmp_path):
    line = "注記: ［証言: LLM の答えです。記録の裏づけはありません］ 参加費は3,000円である。"
    doc = "会議は2026年4月1日に開く。\n" + line + "\n"
    quotes = [{"source": "d.txt", "line": 2, "text": line}]
    out = turn(cfg_for(tmp_path, FakeLLM(reply(line, quotes)), doc_text=doc))
    assert out["vera"]["quote_check"]["verdict"] == "anchored"
    lines = out["content"].split("\n")
    assert lines[0] == NEW
    assert OLD in lines[1] and lines[1] == line
    assert out["content"].count(OLD) == 1 and out["content"].count(NEW) == 1

