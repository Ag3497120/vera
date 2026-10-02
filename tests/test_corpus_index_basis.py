"""W1-c2 / decision 1: an answer whose basis is a corpus sentence says so at its top level.

``basis_origin: "generated"`` is added (and only added) when a cited source carries
``origin == "generated"``. An answer that is not based on the corpus never has the key.
The index states of the commonsense path are now in its trace.
Synthetic data only. Helpers are copied here on purpose: tests/ is not a package.
"""
from __future__ import annotations

import json
from pathlib import Path

from tools.build_p4_corpus_index import build
from verantyx.abilities import Abilities
from verantyx.ability_corpus import Corpus, basis_origin
from verantyx.chat import Chat
from verantyx.question import read


def _index(tmp_path: Path, family: str, rows: list[dict]) -> Corpus:
    src = tmp_path / (family + ".jsonl")
    src.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    build(src, tmp_path / "idx" / (family + ".db"), family)
    return Corpus(tmp_path / "idx")


def _chat(tmp_path: Path, corpus: Corpus | None = None) -> Chat:
    chat = Chat([], general=tmp_path / "absent_general.db")
    chat._abilities = Abilities(corpus or Corpus(tmp_path / "idx"), general=chat.general)
    return chat


def _statuses(result: dict) -> dict:
    return {t["family"]: t["index"] for t in result["trace"] if t.get("part") == "ability_corpus.status"}


# ------------------------------------------------------------------- B1 commonsense
def test_b1_commonsense_answer_carries_basis_origin_and_status_trace(tmp_path):
    _index(tmp_path, "local", [
        {"text": "雨の日に傘を持たずに出たら、髪が濡れた。", "source": "a", "scene": "雨", "sha": "a"},
        {"text": "雨の日に傘を持たずに出たら、服が濡れた。", "source": "b", "scene": "雨", "sha": "b"},
    ])
    out = _chat(tmp_path).reply("雨の日に傘を持たずに外出すると、どうなりますか？")
    assert out["ability"] == "commonsense" and out["kind"] == "answer" and out["verdict"] == "ANSWER"
    assert "濡れた例" in out["text"]                     # same values as the existing test: nothing else changed
    assert out["basis_origin"] == "generated"
    assert any(s.get("origin") == "generated" for s in out["sources"])
    steps = [t for t in out["trace"] if t.get("part") == "ability_corpus.status"]
    assert [(t["family"], t["index"]) for t in steps] == [("local", "INDEX_AVAILABLE"),
                                                          ("pro", "UNKNOWN_FAMILY_DB_MISSING")]
    assert all("verdict" not in t for t in steps)


# ------------------------------------------------------------------ B2 generation
def test_b2_generation_marks_corpus_basis_but_not_general_knowledge(tmp_path, monkeypatch):
    corpus = _index(tmp_path, "local", [{"text": "窓が光った。", "source": "scene-a",
                                         "scene": "窓の朝", "sha": "w"}])
    made = _chat(tmp_path, corpus).reply("窓の様子を一文で描写してください。")
    assert made["kind"] == "compose" and made["basis_origin"] == "generated"

    (tmp_path / "absent_general.db").touch()
    chat = _chat(tmp_path, Corpus(tmp_path / "empty_index"))
    from verantyx import say

    def fake_say(topic, **_kwargs):
        return {"verdict": "GROUNDED", "lines": [{"sentence": "星が光る。",
                "witnesses": [{"source": "general-a", "text": "星が光った。"}]}]}
    monkeypatch.setattr(say, "say", fake_say)
    fallback = chat.reply("星の様子を一文で描写してください。")
    assert fallback["lines"][0]["sources"][0]["source"] == "general-a"
    assert "basis_origin" not in fallback


# --------------------------------------------------------------- B3 understanding
def test_b3_understanding_without_an_index_has_no_basis_origin(tmp_path):
    out = _chat(tmp_path).reply("次の2文は同じ意味を表していますか。『窓を閉めてください。』／『窓を閉じてもらえますか。』")
    assert out["ability"] == "understanding" and out["kind"] == "answer"
    assert "basis_origin" not in out


# ------------------------------------------------------------- B4 conversation supply
def test_b4_conversation_supply_marks_generated_basis(tmp_path, monkeypatch):
    from verantyx.round3 import GeneralRouter
    _index(tmp_path, "conversation", [{"text": "どういたしまして。", "source": "c", "scene": "職場",
                                       "sha": "c1", "dialogue_id": "d1"}])
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    result, trace = GeneralRouter(tmp_path / "r3").answer("ありがとう。", read("ありがとう。"))
    assert result["basis_origin"] == "generated"
    assert any(s.get("origin") == "generated" for s in result["sources"])
    conv = [t for t in trace if t.get("part") == "round3.family.conversation"]
    assert conv and conv[0]["index"] == "INDEX_AVAILABLE"


def test_b4b_conversation_without_an_index_is_the_social_frame_without_basis_origin(tmp_path, monkeypatch):
    from verantyx.round3 import GeneralRouter
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "nowhere"))
    result, trace = GeneralRouter(tmp_path / "r3").answer("ありがとう。", read("ありがとう。"))
    assert "basis_origin" not in result
    conv = [t for t in trace if t.get("part") == "round3.family.conversation"]
    assert conv and conv[0]["index"] == "UNKNOWN_NO_INDEX"


# ------------------------------------------------------------------ B5 code supply
def test_b5_code_supply_marks_generated_basis(tmp_path, monkeypatch):
    from verantyx.round3 import GeneralRouter
    # Chosen after looking at _terms(): the longest term (取り除く, used as the search string) appears
    # literally in the text, and the row identical to the question shares all 4 terms (score 1.0 >= .75).
    # (An earlier choice, 並べ替える, failed: _terms lists the variant 並べ代える first, which is not in the text.)
    text = "リストの重複を取り除く方法"
    _index(tmp_path, "code", [{"text": text, "source": "k", "scene": "配列", "sha": "k1"}])
    monkeypatch.setenv("VERA_P4_INDEX", str(tmp_path / "idx"))
    result = GeneralRouter._code_supply(text)
    assert result is not None and result["path"] == "code_supply"
    assert result["basis_origin"] == "generated"
    assert result["sources"][0]["origin"] == "generated"


# ---------------------------------------------------------- B6 commonsense, no index
def test_b6_commonsense_without_an_index_traces_no_index_and_has_no_basis_origin(tmp_path):
    chat = Chat([], general=tmp_path / "absent_general.db")
    chat._abilities = Abilities(Corpus(tmp_path / "nowhere"), general=chat.general)
    out = chat.reply("雨の日に傘を持たずに外出すると、どうなりますか？")
    assert out["ability"] == "commonsense"
    assert _statuses(out) == {"local": "UNKNOWN_NO_INDEX", "pro": "UNKNOWN_NO_INDEX"}
    assert "basis_origin" not in out
    assert all("verdict" not in t for t in out["trace"] if t.get("part") == "ability_corpus.status")


# --------------------------------------------------------------- B7 the rule itself
def test_b7_basis_origin_rule():
    assert basis_origin([]) is None
    assert basis_origin([{"family": "user"}]) is None
    assert basis_origin([{"origin": "generated"}]) == "generated"
    assert basis_origin([{"family": "general"}, {"origin": "generated"}]) == "generated"
    assert basis_origin(["x", None, 3, {"family": "document"}]) is None
    assert basis_origin(["x", {"origin": "generated"}]) == "generated"
    assert basis_origin([{"origin": "testimony"}]) is None
