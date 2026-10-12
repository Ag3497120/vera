"""MEM-a tests: the memory store, the session, the write path (docs/LINE3_LOOM_MEMORY_DESIGN.md 3-4, 9.4 T-MEM-01..12; L-MEM-01..05, 14, 15, 17, 18).

The memory is a NEW MODE of the loom: these tests pin the empty start (M0), the refusals of `write`, the frozen crosses, the guards that keep a memory corpus and
a base corpus apart, and the frozen-stack fold (sessions chained and replayed byte for byte).  Nothing here needs the evidence gate."""
import hashlib
import json
import os
import subprocess
import sys

import pytest

from verantyx.ledger_events import GENESIS
from verantyx.loom import ledger as lg
from verantyx.loom import memguard as mg
from verantyx.loom import memnotes as mn
from verantyx.loom import memory as mem
from verantyx.loom import read as rd
from verantyx.loom.corpus import Corpus
from verantyx.loom.mcp import LoomServer
from verantyx.loom.state import Refuse
from mem_common import PROBE_REVERSAL, ROOT, SEEDS, STUB, ledger_rows, new_store, notes_of, session, write_all


# -- T-MEM-01..03: M0, the empty start --------------------------------------------------------------------------------------------------------
def test_empty_corpus_has_no_unit_pr1():
    c = Corpus(b"")
    assert c.n_sentences == 0
    assert [len(c.tier(t).postings) for t in ("RUN", "WORD", "CHAR")] == [0, 0, 0]
    assert c.corpus_sha == hashlib.sha256(b"").hexdigest()


def test_first_session_starts_from_nothing(tmp_path):
    st = new_store(tmp_path)
    assert st.head() is None
    s = st.begin("test-model", self_question=None)                      # MEM-c: the default of a new store is the gate hook (test_mem_recall.py); None = no hook
    b = ledger_rows(s)[0]
    h = b["result"]["header"]
    assert (h["mem_version"], h["session_no"], h["sessions_before"], h["sentences_before"]) == ("mem.v1", 1, 0, 0)
    assert h["store_head_before"] == GENESIS and h["memory_sha_before"] == hashlib.sha256(b"").hexdigest() and h["corpus_sha"] == h["memory_sha_before"]
    assert (h["kind_policy"], h["contradiction_policy"], h["unseatable_policy"], h["evidence_version"], h["self_question"]) == ("a", "a", "a", None, "none")
    assert h["notes_profile"] == "mem.v1" and h["caps"] == "mem.v1" and h["stability_mode"] == "report"
    assert b["result"]["task"]["caps"] == {"writes": 60, "recalls": 60, "lookups": 60, "ops": 300, "reads": 0, "emit_attempts": 0, "constructed": 0,
                                           "unit_chars": 8, "max_L": 2, "crosses": mem.CROSS_UNCAPPED, "max_depth": 0}
    st2 = s.status()
    assert (st2["sentences"], st2["units"], st2["crosses"], st2["thread_length"]) == (0, 0, 0, 0)


def test_first_write_is_trivially_stable_and_nothing_counted_fires(tmp_path):
    s = session(tmp_path, self_question=STUB)
    r = s.write("認証の前提は決済")
    assert r["ok"] and r["sid"] == 0 and r["history"] == {"sentences": 0, "corpus_sha": hashlib.sha256(b"").hexdigest()}
    assert all(k["np"]["status"] == "trivially_stable" and k["np"]["key"] == [0, 0, 0] for k in r["keys"])
    assert all(k["npa"]["status"] == "trivially_stable" for k in r["keys"])
    assert "notes" not in r                                              # P-MEM-1: with H empty no counted event fires (SAME_QUESTION asked, one sentence = one answer)
    assert all(u["origin"] == "new" and u["history_n"] == 0 for u in r["units"])        # every word was supplied by the model
    assert r["marked"] == "【新:認証】の【新:前提】は【新:決済】" and r["readback"] == {"text": "認証の前提は決済", "same": True}
    ev = s.events()
    assert ev["detections"]["headline"] == 0 and ev["units"] == {"new": 3, "record": 0}


def test_recall_is_reserved_without_an_evidence_version(tmp_path):
    """MEM-a/b's behaviour, kept for a session whose begin row records no evidence version (no hook, or the stub): the real recall is in test_mem_recall.py."""
    s = session(tmp_path, self_question=None)
    r = s.call("recall", {"question": "田中の担当は何ですか"})
    assert r["ok"] is False and r["refusal"] == "recall_unavailable" and r["detail"]["ticket"] == "MEM-c"


# -- T-MEM-04..06: write and its refusals ----------------------------------------------------------------------------------------------
def test_write_refusals_each_fire(tmp_path):
    s = session(tmp_path)
    assert s.write("")["refusal"] == "bad_sentence"
    assert s.write("田中の\n担当は認証")["refusal"] == "bad_sentence"
    assert s.write("田中の\x00担当は認証")["refusal"] == "bad_sentence"
    assert s.write("田中の担当は認証" * 9)["refusal"] == "args_too_large"          # 72 characters: > ARG_STR_CAP, the row keeps sha + length only
    assert s.write("!?!?")["refusal"] == "no_unit"
    assert s.write("東京で会議を開く")["refusal"] == "span_inexpressible"
    r = s.write("日本より韓国")
    assert r["refusal"] == "span_inexpressible" and r["detail"]["reason"] == "gap_is_not_a_particle"
    assert s.call("write", {"text": "x", "role": "robot"})["refusal"] == "bad_args"
    assert s.call("write", {})["refusal"] == "bad_args"
    sec = s.write("AKIAIOSFODNN7EXAMPLE を使う")
    assert sec["refusal"] == "secret_shaped_sentence"
    rows = ledger_rows(s)
    assert "AKIAIOSFODNN7EXAMPLE" not in json.dumps(rows) and rows[-1]["redacted"] >= 1 and "args_sha256" in rows[-1]
    assert s.status()["sentences"] == 0                                  # nothing was stored by any of them


def test_write_caps_fire_at_the_limit(tmp_path):
    s = session(tmp_path)
    s.run.caps["writes"] = 2
    assert s.write("認証の前提は決済")["ok"] and s.write("田中の担当は認証")["ok"]
    assert s.write("会議は東京で行う")["refusal"] == "write_cap"
    s2 = session(tmp_path, "m2")
    s2.run.caps["ops"] = 2
    assert s2.write("認証の前提は決済")["ok"] and s2.call("swap", {"cid": "c1"})["refusal"] == "memory_frozen"
    assert s2.write("田中の担当は認証")["refusal"] == "ops_cap"
    s3 = session(tmp_path, "m3")
    s3.run.caps["lookups"] = 1
    assert s3.call("lookup", {"text": "認証", "tier": "WORD"})["ok"] and s3.call("lookup", {"text": "認証", "tier": "WORD"})["refusal"] == "lookup_cap"
    assert mem.CAPS_MEM_V1["writes"] == 60 and mem.CAPS_MEM_V1["ops"] == 300 and mem.CAPS_MEM_V1["lookups"] == 60 and mem.CAPS_MEM_V1["recalls"] == 60


def test_refused_write_changes_nothing(tmp_path):
    s = session(tmp_path)
    s.write("認証の前提は決済")
    before = (list(s.run.rows), s.run.state.sha(), mem.mem_sha(s.run.rows), s.run.corpus_cur.corpus_sha, len(s.run.state.units), list(s.run.state.thread))
    for bad in ("東京で会議を開く", "日本より韓国", "", "佐藤が予算を決めた"):
        assert s.write(bad)["ok"] is False
        after = (list(s.run.rows), s.run.state.sha(), mem.mem_sha(s.run.rows), s.run.corpus_cur.corpus_sha, len(s.run.state.units), list(s.run.state.thread))
        # the counters of the call classes move (a refused call is still a call); the units, crosses, thread and H do not
        assert after[0] == before[0] and after[2:] == before[2:]
        assert s.run.corpus is s.run.corpus_cur
    s.commit()
    assert [json.loads(l)["sent"] for l in open(s.store.memory_path, encoding="utf-8")] == ["認証の前提は決済"]


def test_pr5_shapes_pinned(tmp_path):
    s = session(tmp_path)
    nested = ["totalはaddでリストを合計する", "fmt.pyにaddのimportを追加した", "Airでテストを実行する", "東京で会議を開く", "佐藤が予算を決めた"]
    for t in nested:
        r = s.write(t)
        assert r["refusal"] == "span_inexpressible" and r["detail"]["reason"] == "nested_particle_chain", t
    assert s.write("日本より韓国")["detail"]["reason"] == "gap_is_not_a_particle"
    ok = ["今日の作業はK3の修正", "認証の期限は金曜", "次の手順は計測", "田中の担当は認証"]
    assert all(r["ok"] for r in write_all(s, ok))
    ev = s.events()
    assert ev["unseatable"] == {"total": 6, "by_reason": {"gap_is_not_a_particle": 1, "nested_particle_chain": 5}}
    assert ev["cost"]["unseatable"] == 6 and ev["refused"] == {"span_inexpressible": 6}


def test_identifier_and_no_relation_informations(tmp_path):
    s = session(tmp_path)
    r = s.write("fmt_numの戻り値は文字列")
    assert [n["type"] for n in r["notes"]] == ["IDENTIFIER_FLATTENED"] and r["notes"][0]["identifiers"] == ["fmt_num"] and r["notes"][0]["read_as"] == ["fmtnum"]
    assert r["notes"][0]["counted"] is False
    r2 = s.write("赤色 青色 緑色")
    assert r2["ok"] and notes_of(r2) == ["NO_RELATION_SEATED"]


def test_user_role_source_and_lookup(tmp_path):
    s = session(tmp_path)
    a = s.write("認証の期限は金曜", "user")
    b = s.write("決済の期限は月曜")
    assert a["source"] == "mem:t/1#0:user" and b["source"] == "mem:t/1#1"
    lk = s.call("lookup", {"text": "認証", "tier": "WORD"})
    assert lk["ok"] and lk["matches"][0]["sids"] == [0]
    assert s.call("read_sentence", {"sid": 1})["source"] == "mem:t/1#1"


# -- T-MEM-07..09: frozen crosses, the tool set, the guards ----------------------------------------------------------------------------
def test_every_forbidden_op_on_a_committed_cross_is_memory_frozen(tmp_path):
    s = session(tmp_path)
    s.write("認証の前提は決済")
    args = {"unseat": {"cid": "c1", "seat": "+x:0"}, "swap": {"cid": "c1", "seat_a": "centre", "seat_b": "+x:0"}, "extend": {"cid": "c1", "L2": 3},
            "topic": {"cid": "c1", "on": False}, "set_depth": {"cid": "c1", "depth": 1}, "link": {"cid": "c1"}, "unlink": {"cid": "c1"}, "drop": {"cid": "c1"}}
    assert set(args) == set(mem.FROZEN_OPS)
    before = s.run.state.to_obj()
    for op, a in args.items():
        r = s.call(op, a)
        assert r["refusal"] == "memory_frozen" and r["detail"]["cid"] == "c1" and r["detail"]["op"] == op
    assert s.call("drop", {"cid": "c99"})["refusal"] == "unknown_cid"
    assert s.call("drop", {})["refusal"] == "bad_args"
    after = s.run.state.to_obj()
    assert after["crosses"] == before["crosses"] and after["units"] == before["units"] and after["thread"] == before["thread"]


def test_other_loom_ops_are_not_tools_of_a_memory_session(tmp_path):
    s = session(tmp_path)
    for op in ("add", "open_cross", "seat", "seat_run", "weave_span", "weave_sentence", "emit", "abstain", "read", "begin", "nonsense"):
        r = s.call(op, {})
        assert r["refusal"] == "unknown_tool", op
    assert s.run.state.closed is None                                    # no emit, no abstain: the session closes with `commit` only


def test_a_memory_row_guard_and_a_base_corpus_guard(tmp_path):
    with pytest.raises(Refuse) as e:
        mem.build_corpus([{"sent": "東京は晴れ", "source": "wiki/東京#1"}])
    assert e.value.type == "not_memory_row"
    with pytest.raises(Refuse):
        mg.check_memory_rows([{"sent": "x", "source": "mem:t/1#0", "kind": "memory_query"}])
    mg.check_memory_rows([{"sent": "x", "source": "mem:t/1#0:user", "kind": "memory_answer"}])
    s = session(tmp_path)
    s.write("認証の前提は決済")
    s.commit()
    data = (tmp_path / "mem" / "memory.jsonl").read_bytes()
    assert mg.holds_memory_rows(data) and not mg.holds_memory_rows("東京は晴れ".encode()) and not mg.holds_memory_rows(b'{"sent": "memo: x", "source": "w#1"}\n')
    with pytest.raises(Refuse) as e2:
        mg.assert_not_memory_corpus(data)
    assert e2.value.type == "memory_in_base"
    # the loom refuses it as a task corpus, and a stored run whose corpus holds a mem: row is INPUTS
    corpus = tmp_path / "corpus.jsonl"
    corpus.write_bytes(data)
    srv = LoomServer([{"task_id": "x", "text": "q", "lang": "prose", "mode": "record_only", "corpus": str(corpus), "tiers": ["WORD"]}], str(tmp_path / "runs"))
    r = srv.begin("x", "m")
    assert r["ok"] is False and r["refusal"] == "memory_in_base"
    # a plain corpus still opens a run (the guard is a no-op for every corpus without a mem: row)
    plain = tmp_path / "plain.jsonl"
    plain.write_text(json.dumps({"sent": "東京は日本の首都である", "source": "w#1"}, ensure_ascii=False) + "\n", encoding="utf-8")
    srv2 = LoomServer([{"task_id": "y", "text": "q", "lang": "prose", "mode": "record_only", "corpus": str(plain), "tiers": ["WORD"]}], str(tmp_path / "runs2"))
    assert srv2.begin("y", "m")["ok"] is True


def test_the_memory_never_reads_a_base_row(tmp_path):
    """The memory space refuses to be built from a corpus row (`not_memory_row`), also when it comes through `begin`: a tampered memory.jsonl is unverified first."""
    s = session(tmp_path)
    s.write("認証の前提は決済")
    s.commit()
    p = tmp_path / "mem" / "memory.jsonl"
    p.write_text(json.dumps({"kind": "base", "sent": "認証の前提は決済", "source": "wiki#1"}, ensure_ascii=False) + "\n", encoding="utf-8")
    with pytest.raises(Refuse) as e:
        mem.MemStore(str(tmp_path / "mem")).begin("m")
    assert e.value.type == "store_unverified"


# -- T-MEM-10..12: the fold, replay, tampering -------------------------------------------------------------------------------------------
STORY = [["認証の前提は決済", "田中の担当は認証", "東京で会議を開く", "会議は東京で行う", "決済の前提は認証"],
         ["田中の担当は決済", "サーバーのポートは8080", "研修は東京で行う", "東京の天気は晴れ"],
         ["サーバーのポートは9090", "認証の期限は金曜", "決済の期限は月曜", "鈴木の担当は決済", "田中の担当は認証と決済"]]


def _run_story(tmp_path, name="story", hook=STUB, **kw):
    st = new_store(tmp_path, name)
    for sents in STORY:
        s = st.begin("test-model", self_question=hook, **kw)
        write_all(s, sents)
        assert s.commit()["ok"]
    return st


def test_three_sessions_replay_byte_for_byte(tmp_path):
    st = _run_story(tmp_path)
    v = st.verify(STUB)
    assert v["status"] == "OK" and v["sessions"] == 3 and v["sentences"] == 13 and v["replay"]["status"] == "IDENTICAL"
    rep = st.replay(STUB)
    assert rep.identical and rep.sessions == 3 and rep.rows_h == st.rows()
    h = st.head()
    assert [e["session_no"] for e in h["sessions"]] == [1, 2, 3] and h["sentences"] == len(st.rows())
    # the begin row of session k+1 names the HEAD session k left (the chain across sessions)
    r2 = ledger_rows(os.path.join(st.sessions_dir, "s0002"))[0]["result"]["header"]
    assert r2["sessions_before"] == 1 and r2["sentences_before"] == 4 and r2["memory_sha_before"] == mem.mem_sha(st.rows()[:4])
    r3 = ledger_rows(os.path.join(st.sessions_dir, "s0003"))[0]["result"]["header"]
    assert r3["store_head_before"] == mem.head_sha(mem.head_obj("t", "a", h["sessions"][:2], st.rows()[:8]))
    # a replay needs the hook the sessions were recorded with
    assert st.replay(None).status == "INPUTS" and st.replay(None).mismatch == "self_question_mismatch"


def test_replay_is_identical_with_a_pure_ledger_check(tmp_path):
    st = _run_story(tmp_path)
    for run_id in ("s0001", "s0002", "s0003"):
        d = os.path.join(st.sessions_dir, run_id)
        assert lg.verify_chain(d)["status"] == "OK"
        rows = ledger_rows(d)
        assert rows[0]["op"] == "begin" and rows[-1]["op"] == "commit"
        assert all("t_ns" not in r for r in rows)                        # no wall-clock time inside a row (timing.jsonl is outside the chain)


def test_fold_equals_one_pass(tmp_path):
    """T-MEM-10: state(1..k+1) = session_{k+1}(state(1..k)).  The cumulative structure after k sessions is the structure of the same sentences written in ONE session:
    the same units, crosses, thread and read-out (only the sources, and the counters of a session, differ)."""
    flat = [t for sents in STORY for t in sents]
    ok_sents = [s for s in flat if s not in ("東京で会議を開く",)]           # the refused one is refused in both
    st = _run_story(tmp_path, "fold")
    one_store = new_store(tmp_path, "one")
    one = one_store.begin("test-model", self_question=STUB)
    for t in flat[:60]:
        one.write(t)
    end3 = st.begin("test-model", self_question=STUB)                    # a 4th session: its carried state is the fold of sessions 1..3
    def shape(run):
        o = run.state.to_obj()
        return {"units": {u: (v["surface"], v["kind"], v["prov"]["n"], v["prov"].get("origin"), v["prov"].get("history_n")) for u, v in o["units"].items()},
                "crosses": o["crosses"], "thread": o["thread"]}
    assert shape(end3.run) == shape(one.run)
    assert [r["sent"] for r in end3.run.rows] == [r["sent"] for r in one.run.rows] == ok_sents
    assert "".join(sg["s"] for cid in end3.run.state.thread for sg in rd.read_prose(end3.run.state, end3.run.state.crosses[cid])) == \
        "".join(sg["s"] for cid in one.run.state.thread for sg in rd.read_prose(one.run.state, one.run.state.crosses[cid]))
    assert end3.run.state.counters["ops"] == 0 and end3.run.counts == {"writes": 0, "recalls": 0}      # the counters are the session's own
    for k in (1, 2, 3):                                                  # fold == one pass for k = 1, 2, 3: carry(H[:n]) equals the live state after the k-th session
        n = sum(len([x for x in sents if x != "東京で会議を開く"]) for sents in STORY[:k])
        run = mem.MemRun("t", k + 1, "sx", "m", store_head_before=GENESIS)
        run.carry(st.rows()[:n])
        live = new_store(tmp_path, "live%d" % k).begin("m")
        for sents in STORY[:k]:
            for t in sents:
                live.write(t)
        assert shape(run) == shape(live.run)


def test_a_tampered_memory_jsonl_is_store_unverified(tmp_path):
    st = _run_story(tmp_path)
    p = st.memory_path
    good = p.read_bytes()
    p.write_bytes(good.replace("金曜".encode(), "月曜".encode()))
    with pytest.raises(Refuse) as e:
        st.begin("m")
    assert e.value.type == "store_unverified"
    assert st.verify(STUB)["status"] == "STORE_UNVERIFIED"
    p.write_bytes(good)
    assert st.verify(STUB)["status"] == "OK"
    assert st.begin("m").run.session_no == 4


def test_a_tampered_ledger_row_is_caught(tmp_path):
    st = _run_story(tmp_path)
    p = os.path.join(st.sessions_dir, "s0002", "ops.jsonl")
    raw = open(p, "rb").read()
    open(p, "wb").write(raw.replace("サーバーのポートは8080".encode(), "サーバーのポートは8081".encode(), 1))
    assert st.verify(STUB)["status"] == "TAMPERED"
    with pytest.raises(Refuse):
        st.begin("m")


def test_a_rewritten_result_with_a_valid_chain_is_replay_differs(tmp_path):
    """A forged result (a sha-valid chain whose row says something the ops do not produce): the replay finds it."""
    st = _run_story(tmp_path)
    d = os.path.join(st.sessions_dir, "s0001")
    rows = ledger_rows(d)
    i = next(k for k, r in enumerate(rows) if r["op"] == "write" and r["result"].get("ok"))
    rows[i]["result"]["units"][0]["origin"] = "record"
    prev = GENESIS
    out = []
    for r in rows:
        r = {k: v for k, v in r.items() if k != "sha"}
        r["prev"] = prev
        r = lg.seal(r["i"], prev, {k: v for k, v in r.items() if k not in ("v", "i", "prev")})
        prev = r["sha"]
        out.append(lg.line_of(r))
    open(os.path.join(d, "ops.jsonl"), "wb").write(b"".join(out))
    open(os.path.join(d, "HEAD"), "w").write(prev + "\n")
    h = json.loads(st.head_path.read_text())
    h["sessions"][0]["head"] = prev
    st.head_path.write_text(json.dumps(h, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n")
    v = st.verify(STUB)
    assert v["status"] in ("REPLAY_DIFFERS", "STORE_UNVERIFIED")
    rep = st.replay(STUB)
    assert rep.status == "DIFFERS" and rep.first_diff["session"] == "s0001" and rep.first_diff["i"] == i


# -- sessions: locking, abandoning, crash repair ------------------------------------------------------------------------------------------
def test_one_open_session_per_store(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m")
    with pytest.raises(Refuse) as e:
        new_store(tmp_path).begin("m")
    assert e.value.type == "store_locked"
    s.close()
    assert new_store(tmp_path).begin("m")                                  # the lock is released


def test_an_uncommitted_session_is_not_memory(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m")
    s.write("認証の前提は決済")
    s.close()                                                            # abandoned: no commit
    assert st.head() is None and st.rows() == []
    s2 = st.begin("m")
    assert s2.run.session_no == 1 and s2.run_id == "s0002" and len(s2.run.rows) == 0         # the abandoned folder keeps its number
    s2.write("田中の担当は認証")
    s2.commit()
    assert [r["sent"] for r in st.rows()] == ["田中の担当は認証"]
    assert st.verify()["status"] == "OK"


def test_a_crash_between_the_commit_row_and_the_head_is_finished(tmp_path):
    st = new_store(tmp_path)
    s = st.begin("m")
    s.write("認証の前提は決済")
    st._finalize = lambda sess: (_ for _ in ()).throw(RuntimeError("crash"))          # the commit row is appended, then the process dies
    with pytest.raises(RuntimeError):
        s.commit()
    s.close()
    st2 = new_store(tmp_path)
    assert st2.head() is None
    s2 = st2.begin("m")                                                  # begin finishes the commit it finds
    assert s2.run.session_no == 2 and [r["sent"] for r in s2.run.rows] == ["認証の前提は決済"]
    assert st2.head()["sentences"] == 1
    s2.close()
    assert st2.verify()["status"] == "OK"


def test_store_requires_an_explicit_directory_and_policies_are_checked(tmp_path):
    with pytest.raises(ValueError):
        mem.MemStore(None)
    with pytest.raises(ValueError):
        mem.MemStore("")
    st = new_store(tmp_path)
    with pytest.raises(Refuse) as e:
        st.begin("m", unseatable_policy="c")
    assert e.value.type == "policy_not_built"
    with pytest.raises(Refuse):
        st.begin("m", kind_policy="z")
    with pytest.raises(Refuse):
        st.begin("m", contradiction_policy="z")
    with pytest.raises(Refuse):
        st.begin("bad\x00model")
    with pytest.raises(Refuse):
        st.begin("AKIAIOSFODNN7EXAMPLE")
    s = st.begin("m", kind_policy="b")
    s.write("認証の前提は決済")
    s.commit()
    with pytest.raises(Refuse) as e2:
        st.begin("m", kind_policy="a")                                   # one memory, one kind policy
    assert e2.value.type == "policy_mismatch"
    with pytest.raises(ValueError):
        mem.MemStore(str(tmp_path / "mem"), "other")


def test_the_cli_reports(tmp_path, capsys):
    st = _run_story(tmp_path)
    assert mem.main(["status", "--store", str(st.path)]) == 0
    assert json.loads(capsys.readouterr().out)["sessions"] == 3
    assert mem.main(["replay", "--store", str(st.path)]) == 2                # the story used the stub hook: INPUTS self_question_mismatch
    capsys.readouterr()
    assert mem.main(["events", "--store", str(st.path)]) == 0
    assert set(json.loads(capsys.readouterr().out)) == {"s0001", "s0002", "s0003"}


# -- determinism ----------------------------------------------------------------------------------------------------------------------
_SCRIPT = r"""
import sys, hashlib, os, json
sys.path.insert(0, os.path.join(%(root)r, "tests", "line3"))
from mem_common import STUB, new_store, write_all
from test_mem_store import STORY
import pathlib
st = new_store(pathlib.Path(sys.argv[1]), "det")
for sents in STORY:
    s = st.begin("test-model", self_question=STUB)
    write_all(s, sents)
    s.commit()
h = hashlib.sha256()
for rid in ("s0001", "s0002", "s0003"):
    h.update(open(os.path.join(st.sessions_dir, rid, "ops.jsonl"), "rb").read())
h.update(open(st.memory_path, "rb").read())
h.update(open(st.head_path, "rb").read())
print(h.hexdigest(), st.verify(STUB)["status"])
"""


def test_ledger_bytes_do_not_depend_on_the_hash_seed(tmp_path):
    py = os.environ.get("VERA_TEST_PYTHON") or sys.executable
    digests = set()
    for seed in ("0", "1", "12345"):                                     # one process at a time
        out = subprocess.run([py, "-c", _SCRIPT % {"root": ROOT}, str(tmp_path / seed)], env=dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT),
                             capture_output=True, text=True, timeout=300)
        assert out.returncode == 0, out.stderr
        digest, status = out.stdout.split()
        assert status == "OK"
        digests.add(digest)
    assert len(digests) == 1
