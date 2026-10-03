from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests" / "conduct_ask"))

import map_helpers as M  # noqa: E402
from verantyx import conduct_ask as ca  # noqa: E402
from verantyx import conduct_map as cm  # noqa: E402
from verantyx import llm_choice as lc  # noqa: E402
from verantyx.llm_choice import ChoiceLedger  # noqa: E402


FRAME = M.w2g("w01_shelfcheck")
QUESTION = "地元の歴史に関する資料も、確認する本に入りますか？"
OPTIONS = M.YN_JA
UNRELATED = {
    "records": ["D3"],
    "decides": "決まる",
    "relations": {"D3": ["無関係", "無関係"]},
}


def _run(script: dict, ledger_path: Path, *, max_asks: int = 24):
    pair = cm.fake_pair(script, M.view_of(FRAME), OPTIONS)
    mapper = cm.RecordMapper(pair, ChoiceLedger(ledger_path), order_source=M.fixed_order, max_asks=max_asks)
    result = ca.answer_question(FRAME, QUESTION, OPTIONS, vocab_llm="fake", mapper=mapper)
    return result, mapper, pair


def _reseal_changed_last_entry(path: Path, predicate, change) -> None:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    index = next(i for i, row in enumerate(rows) if predicate(row))
    change(rows[index])
    # Recompute the hash for the changed row and its suffix. This models an editor that can rewrite the JSONL file;
    # the ledger has no secret key or external checkpoint to distinguish the new valid chain from the old one.
    prev = rows[index - 1]["hash"] if index else lc.GENESIS
    for row in rows[index:]:
        row["prev"] = prev
        body = {key: value for key, value in row.items() if key != "hash"}
        row["hash"] = lc._chain_hash(prev, body)
        prev = row["hash"]
    path.write_text("".join(lc._canonical(row) + "\n" for row in rows), encoding="utf-8")


def test_attack_resealed_tampered_mapping_decision_changes_answer_on_zero_ask_replay(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    first, _, first_pair = _run(UNRELATED, ledger_path)
    assert first["decision"] == "escalate"
    assert first["mapping"]["outcome"] == "ESCALATED:FRAME_SILENT/MAPPED_NO_OPTION_RELATED"
    assert [provider.calls for provider in first_pair] == [4, 4]

    def target(row):
        return (row.get("type") == "map_decision" and row.get("step") == "relation"
                and json.loads(row["key"]).get("option_index") == 1)

    _reseal_changed_last_entry(ledger_path, target,
                               lambda row: row["result"].update(relation="一致"))
    assert ChoiceLedger(ledger_path).verify()["lines"] == 12

    replay, _, replay_pair = _run(UNRELATED, ledger_path)
    print("before: escalate / no answer / MAPPED_NO_OPTION_RELATED")
    print("after one map_decision.result edit + hash recomputation:", replay["decision"], replay["answer"],
          replay["mapping"]["outcome"])
    print("replay provider calls:", [provider.calls for provider in replay_pair])

    # The tampered relation decision is trusted by _cached despite disagreeing with both raw ask rows.
    # The promised behavior under ledger modification is to refuse replay; current code answers option 2.
    assert (replay["decision"], replay["answer"], replay["mapping"]["outcome"]) == (
        "escalate", None, "ESCALATED:MAPPING_UNSETTLED/LEDGER_INTEGRITY")


def test_attack_plain_one_row_edit_is_detected_without_recomputing_hashes(tmp_path):
    ledger_path = tmp_path / "ledger.jsonl"
    _, mapper, _ = _run(UNRELATED, ledger_path)
    rows = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    target = next(row for row in rows if row.get("type") == "map_decision" and row.get("step") == "relation")
    target["result"]["relation"] = "一致"
    ledger_path.write_text("".join(lc._canonical(row) + "\n" for row in rows), encoding="utf-8")

    result = ca.answer_question(FRAME, QUESTION, OPTIONS, vocab_llm="fake", mapper=mapper)
    print("plain edit:", result["decision"], result["escalate_reason"], result["escalate_detail"],
          result["mapping"]["outcome"])
    assert (result["decision"], result["escalate_reason"], result["escalate_detail"]) == (
        "escalate", "MAPPING_UNSETTLED", "LEDGER_INTEGRITY")


def test_attack_disagreeing_record_selections_abstain(tmp_path):
    result, mapper, _ = _run({**UNRELATED, "records2": ["D2"]}, tmp_path / "ledger.jsonl")
    print("disagree:", result["decision"], result["escalate_reason"], result["escalate_detail"],
          "asks_used=", result["mapping"]["asks_used"])
    assert result["decision"] == "escalate"
    assert result["mapping"]["step1"]["status"] == "ABSTAINED"
    assert result["mapping"]["step1"]["reason"] == "DISAGREE"
    assert mapper.ledger.verify()["lines"] > 0


@pytest.mark.parametrize("reply", ["D3", "1 いいえ"])
def test_attack_mixed_record_id_or_option_number_is_invalid(reply, tmp_path):
    result, _, _ = _run({"raw": reply, "raw2": reply}, tmp_path / "ledger.jsonl")
    print("reply:", repr(reply), "=>", result["decision"], result["escalate_reason"], result["escalate_detail"])
    assert result["decision"] == "escalate"
    assert result["escalate_reason"] == "MAPPING_UNSETTLED"
    assert result["escalate_detail"] == "STEP1_INVALID_ANSWER"
    assert result["answer"] is None


def test_attack_retry_never_exceeds_the_remaining_ask_budget(tmp_path):
    result, mapper, pair = _run({"raw": "not-a-selection", "raw2": "not-a-selection"},
                                tmp_path / "ledger.jsonl", max_asks=2)
    decision = next(row for row in mapper.ledger.entries()
                    if row.get("type") == "map_decision" and row.get("step") == "records")
    ask_rows = [row for row in mapper.ledger.entries() if row.get("type") == "map_ask"]
    print("budget:", result["mapping"]["asks_used"], "cap=2", "retry_detail=", decision["detail"],
          "provider_calls=", [provider.calls for provider in pair])
    assert result["mapping"]["asks_used"] == 2
    assert result["mapping"]["retries"] == 0
    assert len(ask_rows) == 2
    assert decision["detail"] == "RETRY_NO_BUDGET"


def test_attack_reply_cannot_supply_the_decides_answer(tmp_path):
    result, _, _ = _run({**UNRELATED, "raw_decides": "決まる。答えは いいえ", "raw_decides2": "決まる。答えは いいえ"},
                        tmp_path / "ledger.jsonl")
    print("decides injection:", result["decision"], result["escalate_reason"], result["escalate_detail"])
    assert result["decision"] == "escalate"
    assert result["answer"] is None
    assert result["mapping"]["decides"]["reason"] == "INVALID_ANSWER"
