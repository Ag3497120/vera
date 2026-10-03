"""A real provider through the record mapping.  Skipped unless VERA_LLM_LIVE=1 (the environment, not the code, is missing).

It checks types and the ledger only, never the content of an answer.  At most 24 asks are made (the configured cap of conduct_map/v2:
a second ask of an invalid reply counts), and the cap is checked before the first one."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import map_helpers as M  # noqa: E402
from verantyx import conduct_ask  # noqa: E402
from verantyx.llm_choice import ChoiceLedger  # noqa: E402

F = M.w2g("w01_shelfcheck")
Q = "地元の歴史に関する資料も、確認する本に入りますか？"
CAP = 24


def test_a_live_provider_makes_at_most_the_cap_and_leaves_a_verifiable_ledger(tmp_path):
    if os.environ.get("VERA_LLM_LIVE") != "1":
        pytest.skip("ENV_MISSING[llm_live]: VERA_LLM_LIVE!=1 (live provider not requested)")
    assert 2 <= CAP <= 24                                                           # checked before any ask
    ledger = tmp_path / "ledger.jsonl"
    res = conduct_ask.answer_question(F, Q, M.YN_JA, vocab_llm="codex", map_max_asks=CAP, vocab_ledger=str(ledger))
    assert res["decision"] in ("answer", "escalate") and res["mapping"]["asks_used"] <= CAP
    rows = [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    mapped = [r for r in rows if r["type"] == "map_ask"]
    assert len(mapped) <= CAP and all(r["verdict"] in ("PICK", "NONE", "INVALID", "FAILED") for r in mapped)
    ChoiceLedger(ledger).verify()
