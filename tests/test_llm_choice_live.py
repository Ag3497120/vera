"""Live provider integration (V5).  Runs only with VERA_LLM_LIVE=1; otherwise it is skipped
and classified as ENVIRONMENT_MISSING.

It talks to a real model through ``codex exec``: at most 6 asks (3 words x 2 asks) in total
over the life of the ledger file, enforced in code before any ask.  It does not check what the
model answered, only that every outcome is typed, recorded, and chain-verified.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from verantyx.conductor import ProjectFrame
from verantyx.conductor_vocab import ConductorVocabulary
from verantyx.llm_choice import ChoiceLedger, CodexProvider, LLMChooser
from verantyx.memory_frame import Memory

WORDS = ("出版", "アーカイブ", "天気")
QUESTION = "次の工程ではどれを選びますか？"
HARD_CAP = 6
ROOT = Path(__file__).resolve().parents[1]
ASK_FIELDS = {"type", "id", "decision_id", "ask_index", "word", "question", "candidates", "contexts", "order",
              "shown", "variant", "provider", "model", "effort", "prompt", "raw_reply", "verdict", "picked_term",
              "invalid_reason", "failure", "returncode", "seq", "prev", "hash"}
STATUSES = {"ADOPTED", "ABSTAINED", "FAILED", "REFUSED"}


def test_live_codex_closed_choice(tmp_path):
    if os.environ.get("VERA_LLM_LIVE") != "1":
        pytest.skip("ENVIRONMENT_MISSING: VERA_LLM_LIVE!=1 (live provider not requested)")

    budget = min(int(os.environ.get("VERA_LLM_LIVE_MAX_ASKS", HARD_CAP)), HARD_CAP)
    ledger_path = Path(os.environ.get("VERA_LLM_LIVE_LEDGER", ROOT / "artifacts" / "w1-e" / "live_ledger.jsonl"))
    ledger = ChoiceLedger(ledger_path)
    existing = sum(1 for e in ledger.entries() if e.get("type") == "ask")
    planned = 2 * len(WORDS)
    if existing + planned > budget:
        pytest.fail(f"LIVE_BUDGET: {existing} ask rows already in {ledger_path} + {planned} planned > {budget}")

    provider = CodexProvider(
        model=os.environ.get("VERA_LLM_CODEX_MODEL", "gpt-6-luna"),
        effort=os.environ.get("VERA_LLM_CODEX_EFFORT", "low"),
        binary=os.environ.get("VERA_LLM_CODEX_BIN",
                              "/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex"))
    frame = ProjectFrame(Memory(str(tmp_path / "frame.jsonl")))
    frame.add_decision("公開工程", "公開")
    frame.add_decision("保管工程", "保管")
    frame.add_decision("確認工程", "点検")
    vocabulary = ConductorVocabulary(frame, aliases={}, senses={}, chooser=LLMChooser(provider, ledger))

    results = {word: vocabulary.resolve(word, QUESTION, question_kind="CHOICE") for word in WORDS}

    ledger = ChoiceLedger(ledger_path)                       # re-open: verifies the whole chain
    entries = ledger.entries()
    asks = [e for e in entries if e["type"] == "ask"]
    assert len(asks) <= budget
    for row in asks:
        assert ASK_FIELDS <= set(row)
        assert row["verdict"] in {"PICK", "NONE", "INVALID", "FAILED", "SKIPPED_DECIDED"}
    decisions = [e for e in entries if e["type"] == "decision"]
    assert {d["word"] for d in decisions} >= set(WORDS)
    by_id = {a["id"]: a for a in asks}
    for d in decisions:
        assert d["status"] in STATUSES
        if d["status"] == "ADOPTED":
            picks = [by_id[i] for i in d["ask_ids"]]
            assert [p["verdict"] for p in picks] == ["PICK", "PICK"]
            assert picks[0]["picked_term"] == picks[1]["picked_term"] == d["choice"]
        if d["status"] == "FAILED":
            assert d["failure"] in {"TIMEOUT", "NONZERO_EXIT", "EMPTY_OUTPUT", "LIMIT_REACHED", "NOT_FOUND",
                                    "OS_ERROR"}
    for word, res in results.items():
        assert res.status in {"ADOPTED", "ESCALATE"}
        if res.status == "ADOPTED":
            assert res.support == "testimony" and res.canonical in {"公開", "保管", "点検"}
