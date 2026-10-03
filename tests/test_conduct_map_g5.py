"""G5: the ledger is append-only and complete, a second identical question is not asked, a failure is not reused."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import map_helpers as M  # noqa: E402
from map_helpers import ask_map, w2g  # noqa: E402
from verantyx import conduct_ask  # noqa: E402
from verantyx.llm_choice import ChoiceLedger  # noqa: E402

F = w2g("w01_shelfcheck")
Q = "地元の歴史に関する資料も、確認する本に入りますか？"
Q2 = "雑誌の点検は今回の範囲に含めますか？"
YN = M.YN_JA
GOOD = {"records": ["D3"], "decides": "決まる", "relations": {"D3": ["一致", "矛盾"]}}
ASK_KEYS = {"type", "id", "decision_id", "step", "ask_index", "attempt", "retry_of", "record_id", "option_index", "option", "frame_sha256",
            "question", "options", "candidates", "order", "shown", "labels_shown", "variant", "provider", "model", "effort", "prompt",
            "prompt_sha256", "raw_reply", "raw_truncated", "raw_len",
            "raw_sha256", "verdict", "parsed", "invalid_reason", "failure", "failure_detail", "returncode", "elapsed_ms", "ts",
            "seq", "prev", "hash"}
DECISION_KEYS = {"type", "decision_id", "key", "step", "record_id", "status", "reason", "detail", "result", "ask_ids", "question",
                 "candidates", "mapping_type", "counts_as_evidence", "ts", "seq", "prev", "hash"}
REUSE_KEYS = {"type", "decision_id", "reused_decision_id", "key", "step", "record_id", "ts", "seq", "prev", "hash"}


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError("a real provider process must never be started")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


def rows(mp, typ=None):
    return [e for e in mp.ledger.entries() if typ is None or e["type"] == typ]


def test_every_field_of_every_ask_is_recorded_and_only_three_row_types_exist():
    res, mp = ask_map(F, Q, YN, GOOD)
    assert res["decision"] == "answer"
    types = {e["type"] for e in rows(mp)}
    assert types == {"map_ask", "map_decision"} and "decision" not in types
    asks = rows(mp, "map_ask")
    assert len(asks) == 8 and all(set(a) == ASK_KEYS for a in asks)          # records 2 + decides 2 + 2 pairs x 2
    a = asks[0]
    assert a["step"] == "records" and a["question"] == Q and a["options"] == YN and a["prompt_sha256"] and a["raw_reply"]
    assert (a["attempt"], a["retry_of"], a["option_index"], a["labels_shown"]) == (0, None, None, None)
    assert a["verdict"] == "PICK" and a["provider"] == "scripted-map" and a["elapsed_ms"] >= 0 and a["raw_len"] == len(a["raw_reply"])
    assert [c["id"] for c in a["candidates"]][:2] == ["D1", "D2"] and a["shown"] and sorted(a["order"]) == list(range(len(a["candidates"])))
    decisions = rows(mp, "map_decision")
    assert len(decisions) == 4 and all(set(d) == DECISION_KEYS for d in decisions)          # records, decides, 2 pairs
    assert all(d["mapping_type"] == "LLM_TESTIMONY_RECORD_MAPPING" and d["counts_as_evidence"] is False for d in decisions)
    assert decisions[0]["status"] == "ADOPTED" and decisions[0]["result"] == {"records": ["D3"]}
    assert decisions[1]["step"] == "decides" and decisions[1]["result"] == {"decides": "決まる"}
    assert [(d["step"], d["record_id"], d["result"]) for d in decisions[2:]] == [("relation", "D3", {"relation": "一致"}),
                                                                                  ("relation", "D3", {"relation": "矛盾"})]
    assert decisions[0]["ask_ids"] == [asks[0]["id"], asks[1]["id"]]
    pair = [a for a in asks if a["step"] == "relation"]
    assert [(a["option_index"], a["option"]) for a in pair] == [(0, "はい"), (0, "はい"), (1, "いいえ"), (1, "いいえ")]
    assert all(sorted(a["labels_shown"]) == sorted(["一致", "矛盾", "無関係"]) for a in pair)


def test_a_failed_ask_is_recorded_with_its_type_and_no_raw_reply():
    res, mp = ask_map(F, Q, YN, {**GOOD, "fail": "TIMEOUT"})
    asks = rows(mp, "map_ask")
    assert all(a["verdict"] == "FAILED" and a["failure"] == "TIMEOUT" and a["raw_reply"] is None and a["parsed"] is None for a in asks)
    d = rows(mp, "map_decision")[0]
    assert (d["status"], d["reason"], d["result"]) == ("FAILED", "TIMEOUT", None)


def test_the_ledger_file_is_only_appended_to_and_verifies(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = ChoiceLedger(path)
    ask_map(F, Q, YN, GOOD, ledger=ledger)
    before = path.read_bytes()
    assert before.endswith(b"\n")
    ask_map(F, Q2, YN, {"records": ["D2"], "decides": "決まる", "relations": {"D2": ["矛盾", "一致"]}}, ledger=ledger)
    after = path.read_bytes()
    assert after.startswith(before) and len(after) > len(before)


def test_the_ledger_chain_is_verified_by_the_llm_choice_entry(tmp_path, monkeypatch):
    path = tmp_path / "ledger.jsonl"
    ask_map(F, Q, YN, GOOD, ledger=ChoiceLedger(path))
    import io
    from contextlib import redirect_stdout
    from verantyx import llm_choice
    out = io.StringIO()
    with redirect_stdout(out):
        code = llm_choice.main(["verify", str(path)])
    summary = json.loads(out.getvalue())
    assert code == 0 and summary["chain"] == "OK" and summary["by_type"] == {"map_ask": 8, "map_decision": 4}
    path.write_text(path.read_text(encoding="utf-8").replace('"verdict":"PICK"', '"verdict":"NONE"', 1), encoding="utf-8")
    out = io.StringIO()
    with redirect_stdout(out):
        code = llm_choice.main(["verify", str(path)])
    assert code == 2 and json.loads(out.getvalue())["chain"] == "BROKEN"


def test_the_second_identical_question_is_not_asked_again(tmp_path):
    ledger = ChoiceLedger(tmp_path / "l.jsonl")
    mp = M.mapper_for(F, YN, GOOD, ledger=ledger)
    p0 = mp.providers[0]
    first = conduct_ask.answer_question(F, Q, YN, vocab_llm="fake", mapper=mp)
    n_asks, calls = len(rows(mp, "map_ask")), (mp.providers[0].calls, mp.providers[1].calls)
    second = conduct_ask.answer_question(F, Q, YN, vocab_llm="fake", mapper=mp)
    assert len(rows(mp, "map_ask")) == n_asks and (mp.providers[0].calls, mp.providers[1].calls) == calls
    reuse = rows(mp, "map_reuse")
    assert len(reuse) == 4 and all(set(r) == REUSE_KEYS for r in reuse) and {r["step"] for r in reuse} == {"records", "decides", "relation"}
    for k in ("decision", "answer", "answer_option_index", "derivation", "resolver", "basis"):
        assert first[k] == second[k], k
    assert second["mapping"]["step1"]["cached"] is True and second["mapping"]["asks_used"] == 0 and first["mapping"]["asks_used"] == 8
    assert second["mapping"]["step1"]["decision_id"] == first["mapping"]["step1"]["decision_id"]
    assert p0 is mp.providers[0]


def test_another_option_order_or_question_is_a_different_ask():
    mp = M.mapper_for(F, YN, GOOD)
    conduct_ask.answer_question(F, Q, YN, vocab_llm="fake", mapper=mp)
    n = len(rows(mp, "map_ask"))
    mp2 = M.mapper_for(F, ["いいえ", "はい"], {**GOOD, "relations": {"D3": ["矛盾", "一致"]}}, ledger=mp.ledger)
    conduct_ask.answer_question(F, Q, ["いいえ", "はい"], vocab_llm="fake", mapper=mp2)
    assert len(rows(mp, "map_ask")) == n + 8                                  # another option order: its own ask
    mp3 = M.mapper_for(F, YN, GOOD, ledger=mp.ledger)
    conduct_ask.answer_question(F, Q.replace("？", ""), YN, vocab_llm="fake", mapper=mp3)
    assert len(rows(mp, "map_ask")) == n + 16                                 # another text of the question: its own ask
    conduct_ask.answer_question(F, "  " + Q + "  ", YN, vocab_llm="fake", mapper=mp3)
    assert len(rows(mp, "map_ask")) == n + 16                                 # only the whitespace differs: the same key


def test_an_abstention_is_reused_but_a_failure_is_not():
    mp = M.mapper_for(F, YN, {**GOOD, "records2": ["D2"]})
    r1 = conduct_ask.answer_question(F, Q, YN, vocab_llm="fake", mapper=mp)
    n = len(rows(mp, "map_ask"))
    r2 = conduct_ask.answer_question(F, Q, YN, vocab_llm="fake", mapper=mp)
    assert r1["escalate_detail"] == r2["escalate_detail"] == "STEP1_DISAGREE" and len(rows(mp, "map_ask")) == n
    # a failed first try is asked again, and the good second try is adopted
    bad = M.mapper_for(F, YN, {**GOOD, "fail": "LIMIT_REACHED"})
    r = conduct_ask.answer_question(F, Q, YN, vocab_llm="fake", mapper=bad)
    assert r["escalate_detail"] == "STEP1_FAILED:LIMIT_REACHED" and len(rows(bad, "map_ask")) == 2
    good = M.mapper_for(F, YN, GOOD, ledger=bad.ledger)
    r = conduct_ask.answer_question(F, Q, YN, vocab_llm="fake", mapper=good)
    assert r["decision"] == "answer" and len(rows(good, "map_ask")) == 10 and rows(good, "map_reuse") == []


def test_none_on_both_readings_is_reused():
    mp = M.mapper_for(F, YN, {"records": []})
    conduct_ask.answer_question(F, "館内の照明は交換しますか？", YN, vocab_llm="fake", mapper=mp)
    n = len(rows(mp, "map_ask"))
    r = conduct_ask.answer_question(F, "館内の照明は交換しますか？", YN, vocab_llm="fake", mapper=mp)
    assert r["escalate_detail"] == "MAP_NONE" and len(rows(mp, "map_ask")) == n and len(rows(mp, "map_reuse")) == 1


def test_a_broken_ledger_file_is_not_asked(tmp_path):
    path = tmp_path / "ledger.jsonl"
    script = tmp_path / "s.json"
    script.write_text(json.dumps(GOOD, ensure_ascii=False), encoding="utf-8")
    first = conduct_ask.answer_question(F, Q, YN, vocab_llm="fake", map_fake=str(script), vocab_ledger=str(path))
    assert first["decision"] == "answer" and path.is_file()
    text = path.read_text(encoding="utf-8")
    path.write_text(text[:-3] + "zz\n", encoding="utf-8")
    broken = conduct_ask.answer_question(F, Q, YN, vocab_llm="fake", map_fake=str(script), vocab_ledger=str(path))
    assert (broken["decision"], broken["escalate_reason"], broken["escalate_detail"]) == ("escalate", "MAPPING_UNSETTLED", "LEDGER_INTEGRITY")
    assert path.read_text(encoding="utf-8") == text[:-3] + "zz\n"          # nothing was appended to a broken ledger


def test_a_ledger_that_breaks_after_the_mapper_was_built_is_not_asked(tmp_path):
    path = tmp_path / "ledger.jsonl"
    mp = M.mapper_for(F, YN, GOOD, ledger=ChoiceLedger(path))
    conduct_ask.answer_question(F, Q2, YN, vocab_llm="fake", mapper=mp)
    calls = (mp.providers[0].calls, mp.providers[1].calls)
    path.write_text(path.read_text(encoding="utf-8")[:-3] + "zz\n", encoding="utf-8")
    r = conduct_ask.answer_question(F, Q, YN, vocab_llm="fake", mapper=mp)
    assert (r["escalate_reason"], r["escalate_detail"]) == ("MAPPING_UNSETTLED", "LEDGER_INTEGRITY")
    assert (mp.providers[0].calls, mp.providers[1].calls) == calls


def test_two_ledger_objects_on_one_file_keep_one_chain(tmp_path):
    """The word-choice ledger and the mapping ledger of a real run are two ChoiceLedger objects on the same file
    (review 1, optional 4).  Each append re-reads the file under a lock, so alternating appends stay one valid chain."""
    from verantyx.llm_choice import ChoiceLedger
    path = tmp_path / "ledger.jsonl"
    a, b = ChoiceLedger(str(path)), ChoiceLedger(str(path))
    for i in range(3):
        a.append({"type": "ask", "n": i})
        b.append({"type": "map_ask", "n": i})
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()]
    assert [r["seq"] for r in rows] == list(range(6)) and [r["type"] for r in rows] == ["ask", "map_ask"] * 3
    assert a.verify()["lines"] == 6 and b.verify()["lines"] == 6
