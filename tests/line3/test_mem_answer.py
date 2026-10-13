"""MEM-d tests: the ANSWER RUN over a memory snapshot (docs/LINE3_LOOM_MEMORY_DESIGN.md 4.1 (2), 6, 9.4 T-MEM-26..30; L-MEM-21).

A question asked after the sessions is answered through recall / weave_span / emit with the evidence gate (evidence.v2, scope clause, unchanged) over the snapshot; the superseded
sentences are history, not quotes; a contested memory is a typed abstention; the run is a loom-format ledger that replays from the snapshot file."""
import hashlib
import json
import os

import pytest

from verantyx.loom import ledger as lg
from verantyx.loom import memanswer as ma
from verantyx.loom import memguard as mg
from verantyx.loom import memory as mem
from verantyx.loom.mcp import LoomServer
from verantyx.loom.state import Refuse
from mem_common import new_store, refusal_of, write_all

pytestmark = pytest.mark.usefixtures("gate_v2")                # PUB-M6c (L-PUB-76): written against the original gate (evidence.v2); the default gate is asserted in test_pub_m6c.py


SENT = ["田中の担当は認証", "認証の期限は金曜", "田中の担当は決済", "サーバーのポートは8080", "サーバーのポートは9090", "決済の期限は月曜"]       # sid 0..5


def make_store(tmp_path, name="mem", supersede=True):
    st = new_store(tmp_path, name)
    s = st.begin("m", profile=mem.PROFILE_V2)
    for k, t in enumerate(SENT):
        s.call("write", {"text": t, "turn": "1-%d" % (k + 1)})
    if supersede:
        assert s.call("supersede", {"new_sid": 2, "old_sid": 0, "reason": "変更"})["ok"]
    s.commit()
    return str(tmp_path / name)


def open_run(store, question, **kw):
    return ma.AnswerSession(store, question, "test-model", **kw)


def weave_emit(a, sid, unit):
    w = a.call("weave_span", {"sid": sid, "tier": "WORD", "first": unit, "last": unit})
    assert w["ok"], w
    return a.call("emit", {})


# -- the snapshot -------------------------------------------------------------------------------------------------------------------------
def test_snapshot_is_named_by_its_sha_and_carries_the_supersede_marks_and_turns(tmp_path):
    store = make_store(tmp_path)
    snap = ma.write_snapshot(store)
    data = open(snap["path"], "rb").read()
    assert snap["name"] == "memory_%s.jsonl" % hashlib.sha256(data).hexdigest()[:12] and snap["sha256"] == hashlib.sha256(data).hexdigest()
    assert (snap["sentences"], snap["superseded"], snap["store_id"]) == (6, 1, "t")
    rows = [json.loads(ln) for ln in data.decode().splitlines()]
    assert rows[0]["superseded_by"] == {"by": 2, "reason": "変更", "session": 1} and "superseded_by" not in rows[2]
    assert [r["turn"] for r in rows] == ["1-%d" % k for k in range(1, 7)] and all(r["source"].startswith("mem:t/1#") for r in rows)
    assert ma.write_snapshot(store) == snap                                  # idempotent: the same bytes, the same name
    ma.read_snapshot(snap["path"])
    mg.check_memory_rows(rows)


def test_snapshot_refusals(tmp_path):
    empty = str(tmp_path / "empty")
    mem.MemStore(empty, "t")
    with pytest.raises(Refuse) as e:
        ma.write_snapshot(empty)
    assert e.value.type == "empty_store"
    store = make_store(tmp_path)
    snap = ma.write_snapshot(store)
    with open(snap["path"], "ab") as f:
        f.write(b" ")
    with pytest.raises(Refuse) as e2:                                         # the name is no longer the sha of the bytes
        ma.read_snapshot(snap["path"])
    assert e2.value.type == "snapshot_unverified"
    store2 = make_store(tmp_path, "bad")
    with open(os.path.join(store2, "memory.jsonl"), "ab") as f:
        f.write(b"\n")
    with pytest.raises(Refuse) as e3:                                         # a store that does not verify has no snapshot
        ma.write_snapshot(store2)
    assert e3.value.type == "store_unverified"


def test_the_snapshot_does_not_move_when_the_store_grows(tmp_path):
    """L-MEM-21: an answer run never reads a growing memory."""
    store = make_store(tmp_path)
    snap = ma.write_snapshot(store)
    a = open_run(store, "田中の担当は何ですか", snapshot=snap)
    s = mem.MemStore(store).begin("m", profile=mem.PROFILE_V2)
    s.write("認証の担当は佐藤")
    s.commit()
    r = a.call("recall", {"question": "認証の担当は何ですか"})
    assert r["verdict"] == "NONE" and r["sentences"] == 6
    assert ma.write_snapshot(store)["name"] != snap["name"]


# -- answering -----------------------------------------------------------------------------------------------------------------------------
def test_an_answer_is_a_recalled_quote_that_passes_the_gate(tmp_path):
    store = make_store(tmp_path)
    a = open_run(store, "田中の担当は何ですか")
    b = a.begin_result
    assert b["tools"] == list(ma.ANSWER_TOOLS) and b["mem_answer"]["superseded"] == [0] and b["rules"]["abstain"] == ["no_record", "cannot_weave", "unknown", "contested"]
    assert b["evidence_profile"] == {"version": "evidence.v2", "subject_scope": "clause"} and b["question"]["subject"] == ["田中"]
    r = a.call("recall", {"question": "田中の担当は何ですか"})
    assert r["verdict"] == "ANSWER" and r["answers"][0]["text"] == "決済" and r["answers"][0]["occurrences"][0]["turn"] == "1-3"
    assert r["history"][0]["occurrences"][0]["sid"] == 0
    out = weave_emit(a, 2, "決済")
    assert out["ok"] and out["text"] == "決済" and a.closed() == ["emitted", out["output_sha"]]
    o = ma.answer_output(a.ledger.dir)
    assert o["status"] == "emitted" and o["text"] == "決済" and o["recalls"][0]["answers"] == [["決済"]]
    v = ma.verify_answer(a.ledger.dir)
    assert v["status"] == "OK" and v["replay"]["status"] == "IDENTICAL"


def test_the_gate_passes_the_answer_only_as_the_quote_of_a_sentence_that_answers_this_question(tmp_path):
    store = make_store(tmp_path, supersede=False)
    a = open_run(store, "田中の担当は何ですか")
    assert a.call("emit", {})["refusal"] == "empty_thread"
    # a quote from a sentence about ANOTHER question: the gate reads its clause and refuses it
    assert a.call("weave_span", {"sid": 1, "tier": "WORD", "first": "金曜", "last": "金曜"})["ok"]
    r = a.call("emit", {})
    assert r["ok"] is False and r["refusal"] == "no_evidence"
    assert a.call("drop", {"cid": "c1"})["ok"]
    # a hand-built unit (not a quote) is refused too
    assert a.call("add", {"text": "認証", "kind": "record", "tier": "WORD"})["ok"]
    assert a.call("open_cross", {"tier": "WORD", "L": 1})["ok"]
    assert a.call("seat", {"cid": "c2", "seat": "centre", "uid": "u2"})["ok"] and a.call("link", {"cid": "c2"})["ok"]
    r2 = a.call("emit", {})
    assert r2["ok"] is False and r2["refusal"] in ("no_evidence", "not_quoted", "constructed_unit")
    assert a.call("drop", {"cid": "c2"})["ok"]
    # the quote of the right sentence passes
    assert weave_emit(a, 0, "認証")["text"] == "認証"


def test_a_superseded_sentence_is_never_a_quote(tmp_path):
    store = make_store(tmp_path)
    a = open_run(store, "田中の担当は何ですか")
    r = a.call("weave_span", {"sid": 0, "tier": "WORD", "first": "認証", "last": "認証"})
    assert r["ok"] is False and r["refusal"] == "superseded_sentence" and r["detail"]["by"] == 2 and r["detail"]["reason"] == "変更"
    assert a.run.state.crosses == {} and a.run._nweaves == 0
    assert a.call("read_sentence", {"sid": 0})["ok"] and a.call("lookup", {"text": "認証", "tier": "WORD"})["matches"]            # history is visible
    assert weave_emit(a, 2, "決済")["text"] == "決済"


def test_a_contested_memory_is_a_typed_abstention_holding_both_values(tmp_path):
    store = make_store(tmp_path)
    a = open_run(store, "サーバーのポートは何ですか")
    r = a.call("recall", {"question": "サーバーのポートは何ですか"})
    assert r["verdict"] == "CHOICE" and [g["answers"] for g in r["answers"]] == [["8080"], ["9090"]]
    assert refusal_of(a.call("abstain", {"type": "nope"})) == "bad_type"
    assert a.call("abstain", {"type": "contested"})["ok"] and a.closed() == ["abstained", "contested"]
    o = ma.answer_output(a.ledger.dir)
    assert o == {"status": "abstained", "type": "contested", "recalls": [{"question": "サーバーのポートは何ですか", "verdict": "CHOICE", "answers": [["8080"], ["9090"]]}]}
    assert a.call("recall", {"question": "x"})["refusal"] == "run_closed"


def test_nothing_in_memory_is_no_record(tmp_path):
    store = make_store(tmp_path)
    a = open_run(store, "鈴木の担当は何ですか")
    r = a.call("recall", {"question": "鈴木の担当は何ですか"})
    assert r["verdict"] == "NONE" and "codes" in r
    assert a.call("abstain", {"type": "no_record"})["ok"]
    assert ma.answer_output(a.ledger.dir)["type"] == "no_record"


def test_the_ordinary_loom_still_refuses_a_memory_corpus(tmp_path):
    """L-MEM-02: the answer run is the one explicit door; `LoomServer.begin` still refuses a corpus with a mem: row."""
    store = make_store(tmp_path)
    snap = ma.write_snapshot(store)
    srv = LoomServer([{"task_id": "t", "text": "田中の担当は何ですか", "lang": "prose", "mode": "record_only", "corpus": snap["path"]}], str(tmp_path / "runs"))
    r = srv.begin("t", "m")
    assert r["ok"] is False and r["refusal"] == "memory_in_base"


def test_recall_cap_and_argument_checks(tmp_path):
    store = make_store(tmp_path)
    a = open_run(store, "田中の担当は何ですか")
    assert refusal_of(a.call("recall", {"question": ""})) == "bad_question"
    assert refusal_of(a.call("recall", {})) == "bad_args"
    a.run.recalls = ma.RECALL_CAP
    assert refusal_of(a.call("recall", {"question": "田中の担当は何ですか"})) == "recall_cap"
    assert refusal_of(a.call("weave_span", {"sid": 0, "tier": "WORD", "first": "認証", "last": "認証", "from": 0})) == "bad_args"
    with pytest.raises(Refuse):
        open_run(store, "")


# -- replay ------------------------------------------------------------------------------------------------------------------------------------
def test_replay_needs_the_snapshot_and_reproduces_every_byte(tmp_path):
    store = make_store(tmp_path)
    a = open_run(store, "田中の担当は何ですか")
    a.call("recall", {"question": "田中の担当は何ですか"})
    weave_emit(a, 2, "決済")
    rep = ma.replay_answer(a.ledger.dir)
    assert rep.identical and rep.text == "決済" and rep.n_rows == 4
    snap_path = os.path.join(store, "snapshots", a.run.snapshot)
    saved = open(snap_path, "rb").read()
    os.replace(snap_path, snap_path + ".moved")
    r1 = ma.replay_answer(a.ledger.dir)
    assert r1.status == "INPUTS" and r1.mismatch == "snapshot_missing" and ma.verify_answer(a.ledger.dir)["status"] == "REPLAY_INPUTS_MISMATCH"
    open(snap_path, "wb").write(saved + b"\n")                                  # same name, other bytes: the snapshot is no longer what its name says
    r2 = ma.replay_answer(a.ledger.dir)
    assert r2.status == "INPUTS" and r2.mismatch == "snapshot_unverified"
    open(snap_path, "wb").write(saved)
    os.remove(snap_path + ".moved")
    assert ma.replay_answer(a.ledger.dir).identical


def test_a_forged_recall_row_is_a_replay_difference(tmp_path):
    store = make_store(tmp_path)
    a = open_run(store, "サーバーのポートは何ですか")
    a.call("recall", {"question": "サーバーのポートは何ですか"})
    a.call("abstain", {"type": "contested"})
    p = a.ledger.dir / "ops.jsonl"
    rows = [json.loads(ln) for ln in open(p, encoding="utf-8")]
    rows[1]["result"]["verdict"] = "ANSWER"
    prev = rows[0]["sha"]
    out = []
    for r in rows[1:]:
        r["prev"] = prev
        r["sha"] = lg.row_sha(r)
        prev = r["sha"]
        out.append(lg.line_of(r))
    p.write_bytes(lg.line_of(rows[0]) + b"".join(out))
    (a.ledger.dir / "HEAD").write_text(prev + "\n")
    v = ma.verify_answer(a.ledger.dir)
    assert v["status"] == "REPLAY_DIFFERS" and v["replay"]["first_diff"]["i"] == 1


def test_two_identical_stores_give_identical_answer_ledgers(tmp_path):
    outs = []
    for name in ("one", "two"):
        store = make_store(tmp_path, name)
        a = open_run(store, "田中の担当は何ですか", run_id="a0001")
        a.call("recall", {"question": "田中の担当は何ですか"})
        weave_emit(a, 2, "決済")
        outs.append(open(a.ledger.dir / "ops.jsonl", "rb").read())
    assert outs[0] == outs[1] and hashlib.sha256(outs[0]).hexdigest()


def test_harness_rows_are_the_drivers_and_do_not_change_the_answer(tmp_path):
    store = make_store(tmp_path)
    a = open_run(store, "田中の担当は何ですか")
    a.harness("free_text_dropped", {"sha256": "0" * 64, "chars": 3})
    weave_emit(a, 2, "決済")
    assert ma.verify_answer(a.ledger.dir)["status"] == "OK" and ma.answer_output(a.ledger.dir)["text"] == "決済"
    a2 = open_run(store, "田中の担当は何ですか")
    a2.harness("abandoned", {"reason": "max_turns"})
    assert a2.closed() == ["abandoned", "max_turns"] and ma.answer_output(a2.ledger.dir)["status"] == "open"
