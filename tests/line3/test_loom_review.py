"""LOOM-core review fixes (L-LOOM-43 .. L-LOOM-50): the ledger is judged by its BYTES, what a refused call may cost the ledger, unguessable
run ids, the boundary of "one call = one row", the full interpreter identity, typed replay inputs, `bad_pos`, the demo task ids.
(The OP-LOOM-4 tests, L-LOOM-51, are in test_loom_stability.py.)"""
import asyncio
import hashlib
import json
import os
import platform
import subprocess
import sys

import pytest

from verantyx.ledger_events import LedgerError, canonical
from verantyx.loom import ledger as lg
from verantyx.loom.mcp import LoomServer, MAX_BEGINS, Sandbox, SandboxError
from verantyx.loom.ops import MODEL_OPS
from verantyx.loom.scripted import ScriptedWeaver, weave_tokyo
from loom_common import CORPUS, PY, ROOT, TASKS, TOY, rows, server, task, weaver

TOKYO_CA_SHA = "70a569eba879736d1bf1b7a6e86ff8a281216d571a2ce4fc9c3d42e4d83470e2"
TOKYO_RO_SHA = "c74f3319b605745e07a008b876bae444d9cb0dc4ed59387af165176cde9816c8"


def tokyo(tmp_path, task_id="demo/tokyo_ca", run_id="r1"):
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, task_id, "claude-haiku-4-5", run_id)
    assert weave_tokyo(w)["ok"]
    return srv, w, tmp_path / "runs" / run_id


def rehash(run_dir, mutate):
    rs = rows(run_dir)
    mutate(rs)
    prev = lg.GENESIS
    out = []
    for i, r in enumerate(rs):
        r = dict(r)
        r["i"], r["prev"] = i, prev
        r["sha"] = lg.row_sha(r)
        prev = r["sha"]
        out.append(r)
    (run_dir / "ops.jsonl").write_bytes(b"".join(lg.line_of(r) for r in out))
    (run_dir / "HEAD").write_text(prev + "\n")


def edit_line(run_dir, idx, fn):
    """Rewrite line idx (0-based) of ops.jsonl as bytes; the chain, HEAD and every sha are NOT touched."""
    p = run_dir / "ops.jsonl"
    lines = p.read_bytes().split(b"\n")
    lines[idx] = fn(lines[idx])
    p.write_bytes(b"\n".join(lines))


def emit_idx(d):
    return [i for i, r in enumerate(rows(d)) if r["op"] == "emit"][0]


# ---------------------------------------------------------------------------------------------------------------
# L-LOOM-43: verify and replay judge the raw bytes
# ---------------------------------------------------------------------------------------------------------------
def test_a_whitespace_edit_that_leaves_the_parsed_row_unchanged_is_TAMPERED(tmp_path):
    srv, w, d = tokyo(tmp_path)
    assert lg.verify(d)["status"] == "OK"
    edit_line(d, 3, lambda b: b.replace(b'"actor":', b'"actor": ', 1))
    v = lg.verify(d)
    assert v["status"] == "TAMPERED" and {"line": 4, "type": "NONCANONICAL_LINE"} in v["problems"]
    assert not any(p["type"] == "SHA_MISMATCH" for p in v["problems"])        # the parsed row still hashes: only the bytes betray it
    o = lg.emitted_output(d)
    assert o["status"] == "run_not_verified" and o["verify"] == "TAMPERED" and "text" not in o


@pytest.mark.parametrize("how", ["trailing_space", "reordered_keys", "escaped_char", "indent"])
def test_every_other_non_canonical_spelling_of_a_row_is_TAMPERED(tmp_path, how):
    srv, w, d = tokyo(tmp_path)

    def fn(b):
        if how == "trailing_space":
            return b + b" "
        if how == "reordered_keys":
            return json.dumps(json.loads(b), ensure_ascii=False).encode("utf-8")           # insertion order, spaces after , and :
        if how == "escaped_char":
            return b.replace("東".encode("utf-8"), b"\\u6771", 1)
        return json.dumps(json.loads(b), ensure_ascii=False, sort_keys=True, indent=1).replace("\n", " ").encode("utf-8")
    edit_line(d, 1, fn)
    assert lg.verify(d)["status"] == "TAMPERED"
    assert lg.emitted_output(d)["status"] == "run_not_verified"


@pytest.mark.parametrize("where", ["prepended", "appended"])
def test_a_duplicate_key_forgery_of_the_emit_row_is_TAMPERED_and_output_refuses(tmp_path, where):
    srv, w, d = tokyo(tmp_path)
    ei = emit_idx(d)
    forged = '"result":{"ok":true,"output_sha":"%s","status":"emitted","text":"FORGED"}' % ("0" * 64)

    def fn(b):
        s = b.decode("utf-8")
        s = "{" + forged + "," + s[1:] if where == "prepended" else s[:-1] + "," + forged + "}"
        return s.encode("utf-8")
    edit_line(d, ei, fn)
    v = lg.verify(d)
    assert v["status"] == "TAMPERED" and any(p["type"] == "NONCANONICAL_LINE" and p["line"] == ei + 1 for p in v["problems"])
    o = lg.emitted_output(d)
    assert o["status"] == "run_not_verified" and "FORGED" not in json.dumps(o, ensure_ascii=False)
    # the CLI consumer agrees
    p = subprocess.run([PY, "-m", "verantyx.cli", "loom", "output", str(d)], env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"),
                       cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert p.returncode == 1 and "FORGED" not in p.stdout and "run_not_verified" in p.stdout


def test_replay_compares_bytes_not_parsed_rows(tmp_path):
    srv, w, d = tokyo(tmp_path)
    edit_line(d, 5, lambda b: b.replace(b'"op":', b'"op": ', 1))
    rep = lg.replay(d)
    assert rep.status == "DIFFERS" and rep.first_diff == {"i": 5, "field": "bytes"}


def test_a_canonical_ledger_still_verifies_and_replays_byte_for_byte(tmp_path):
    srv, w, d = tokyo(tmp_path)
    rep = lg.replay(d)
    assert rep.identical and b"".join(rep.lines) == (d / "ops.jsonl").read_bytes()
    assert lg.verify(d)["status"] == "OK"


# ---------------------------------------------------------------------------------------------------------------
# L-LOOM-44: what a refused call may cost the ledger
# ---------------------------------------------------------------------------------------------------------------
def size(srv, rid):
    return (srv.sandbox.runs_root / rid / "ops.jsonl").stat().st_size


def test_an_oversize_argument_is_stored_as_sha_and_length_and_refused(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca", run_id="o")
    big = "あ" * 65
    r = w.call("lookup", text=big, tier="any")
    assert r["ok"] is False and r["refusal"] == "args_too_large" and r["detail"]["limit"] == 512 and r["detail"]["string_limit"] == 64
    row = rows(tmp_path / "runs" / "o")[-1]
    args = {"text": big, "tier": "any"}
    assert row["truncated"] is True and row["args"] == {} and row["args_sha256"] == hashlib.sha256(canonical(args).encode("utf-8")).hexdigest()
    assert row["args_chars"] == len(canonical(args)) and "redacted" not in row
    assert big not in (tmp_path / "runs" / "o" / "ops.jsonl").read_text(encoding="utf-8")
    assert w.call("status")["counters"]["lookups"] == 1                       # counted in its class (L-LOOM-27)
    assert lg.verify(tmp_path / "runs" / "o")["status"] == "OK"               # and it replays


def test_the_string_cap_sits_above_every_legitimate_value_and_below_abuse(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    assert w.call("lookup", text="あ" * 33, tier="any")["refusal"] == "bad_args"          # 33 .. 64: the handler's own limit (32)
    assert w.call("lookup", text="あ" * 64, tier="any")["refusal"] == "bad_args"
    assert w.call("lookup", text="あ" * 65, tier="any")["refusal"] == "args_too_large"
    assert w.call("add", text="x", kind="constructed", **{"k" * 65: 1})["refusal"] == "args_too_large"       # a long KEY too
    assert w.call("seat_run", cid="c1", arm="+x", uids=["u%d" % i for i in range(200)])["refusal"] == "args_too_large"    # many short strings
    assert w.call("lookup", text="日本", tier="any")["ok"]


def test_200_refused_abstains_of_4000_chars_no_longer_cost_4_9_MB(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca", run_id="a")
    out = [w.call("abstain", type="x" * 4000) for _ in range(200)]
    assert [r["refusal"] for r in out[:5]] == ["args_too_large"] * 5
    assert all(r["refusal"] == "cap_exceeded" and r["detail"] == {"guard": "abstain_refused", "limit": 5} for r in out[5:])
    d = tmp_path / "runs" / "a"
    assert size(srv, "a") < 120_000, size(srv, "a")
    assert all(r["truncated"] and r["args"] == {} for r in rows(d)[1:])
    assert lg.verify(d)["status"] == "OK"
    assert w.call("status")["guards"] == {"abstain_refused": 5, "closed_calls": 0}
    # a VALID abstain is never blocked: the model can always close its run
    assert w.call("abstain", type="no_record") == {"ok": True, "status": "abstained", "type": "no_record"}
    assert srv.closed("a") == ["abstained", "no_record"]
    assert lg.verify(d)["status"] == "OK"


def test_a_short_wrong_abstain_type_is_echoed_at_most_32_chars_and_counts(tmp_path):
    w = weaver(server(tmp_path), "prose/ca")
    r = w.call("abstain", type="y" * 50)
    assert r["refusal"] == "bad_type" and r["detail"]["type"] == "y" * 32
    assert w.call("status")["guards"]["abstain_refused"] == 1


def test_calls_after_the_run_is_closed_are_capped(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca", run_id="c")
    assert w.call("abstain", type="unknown")["ok"]
    first = [w.call("lookup", text="日本", tier="any") for _ in range(20)]
    assert all(r["refusal"] == "run_closed" for r in first)
    rs = rows(tmp_path / "runs" / "c")
    assert not any("truncated" in r for r in rs[-20:]) and rs[-1]["args"] == {"text": "日本", "tier": "any"}      # still verbatim under the cap
    more = [w.call("lookup", text="x" * 4000, tier="any") for _ in range(300)]
    assert all(r["refusal"] == "cap_exceeded" and r["detail"] == {"guard": "closed_calls", "limit": 20} for r in more)
    assert size(srv, "c") < 250_000, size(srv, "c")
    assert w.call("status")["refusal"] == "cap_exceeded"
    d = tmp_path / "runs" / "c"
    assert lg.verify(d)["status"] == "OK"
    srv.harness("c", "free_text_dropped", {"sha256": "0" * 64, "chars": 3})               # the harness's rows are not capped
    assert lg.verify(d)["status"] == "OK"
    # a restarted server rebuilds the same state, guards included
    srv2 = LoomServer(TASKS, str(tmp_path / "runs"), evidence="off")
    assert srv2.closed("c") == ["abstained", "unknown"] and srv2.runs["c"].run.state.guards == {"abstain_refused": 0, "closed_calls": 20}


def test_the_guards_are_in_the_state_sha(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca")
    a = rows(tmp_path / "runs" / w.run_id)[-1]["state_sha"]
    w.call("abstain", type="nope")
    assert rows(tmp_path / "runs" / w.run_id)[-1]["state_sha"] != a


def test_begin_is_capped_per_server_and_a_refused_begin_leaves_no_folder(tmp_path):
    srv = LoomServer(TASKS, str(tmp_path / "runs"), max_begins=3, evidence="off")
    ids = [srv.call("begin", {"task_id": "prose/ca", "model": "m"})["run_id"] for _ in range(3)]
    assert len(set(ids)) == 3
    r = srv.call("begin", {"task_id": "prose/ca", "model": "m"})
    assert r == {"ok": False, "refusal": "cap_exceeded", "detail": {"guard": "begin", "limit": 3}}
    assert sorted(p.name for p in (tmp_path / "runs").iterdir()) == sorted(ids)
    assert MAX_BEGINS == 256 and LoomServer(TASKS, str(tmp_path / "r2")).max_begins == 256
    # a giant task id is not echoed
    srv2 = server(tmp_path / "x")
    d = srv2.call("begin", {"task_id": "T" * 5000, "model": "m"})["detail"]
    assert d["task_id"] == "T" * 64


def test_an_oversize_call_after_a_secret_is_not_double_stored(tmp_path):
    """Oversize wins over the secret scan: nothing of the arguments reaches the row, so there is nothing to redact."""
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca", run_id="s")
    r = w.call("lookup", text="sk-ant-" + "a" * 80, tier="any")
    assert r["refusal"] == "args_too_large"
    assert "sk-ant" not in (tmp_path / "runs" / "s" / "ops.jsonl").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------------------------------------
# L-LOOM-45: unguessable run ids on the MCP door; replay does not depend on them
# ---------------------------------------------------------------------------------------------------------------
def test_run_ids_are_reproducible_without_a_nonce_and_not_with_one(tmp_path):
    ident = {"task_id": "prose/ca", "model": "m", "corpus_sha": None, "seq": 0}
    a = LoomServer(TASKS, str(tmp_path / "a"), evidence="off")
    ra = a.call("begin", {"task_id": "prose/ca", "model": "m"})["run_id"]
    ident["corpus_sha"] = a.runs[ra].run.corpus.corpus_sha
    assert ra == hashlib.sha256(canonical(ident).encode("utf-8")).hexdigest()[:12]            # the old formula, byte for byte
    b = LoomServer(TASKS, str(tmp_path / "b"), nonce="n1", evidence="off")
    c = LoomServer(TASKS, str(tmp_path / "c"), nonce="n2", evidence="off")
    d = LoomServer(TASKS, str(tmp_path / "d"), nonce="n1", evidence="off")
    rb, rc, rd = (s.call("begin", {"task_id": "prose/ca", "model": "m"})["run_id"] for s in (b, c, d))
    assert len({ra, rb, rc}) == 3 and rb == rd                                                 # the nonce is the only difference


def test_the_mcp_server_mixes_in_a_per_process_nonce_and_a_guessed_id_reaches_nothing(tmp_path):
    pytest.importorskip("mcp.server.fastmcp")
    from verantyx.loom import mcp as lm
    bank = tmp_path / "tasks.jsonl"
    bank.write_text("\n".join(json.dumps(t, ensure_ascii=False) for t in TASKS) + "\n", encoding="utf-8")

    def call(m, tool, args):
        async def go():
            content, _ = await m.call_tool(tool, args)
            return json.loads(content[0].text)
        return asyncio.run(go())
    m1, m2 = lm.build(str(bank), str(tmp_path / "r1")), lm.build(str(bank), str(tmp_path / "r2"))
    n1, n2 = m1.loom_server.nonce, m2.loom_server.nonce
    assert len(n1) == 32 and n1 != n2
    r1 = call(m1, "begin", {"task_id": "prose/ca", "model": "m"})["run_id"]
    r2 = call(m2, "begin", {"task_id": "prose/ca", "model": "m"})["run_id"]
    assert r1 != r2
    # what an attacker who knows task, model and corpus can compute (the pre-fix formula, seq from 0) is not a run
    guess = hashlib.sha256(canonical({"task_id": "prose/ca", "model": "m", "corpus_sha": m1.loom_server.runs[r1].run.corpus.corpus_sha, "seq": 0}).encode("utf-8")).hexdigest()[:12]
    assert guess != r1
    for tool in ("status", "emit", "abstain"):
        a = {"run_id": guess} if tool != "abstain" else {"run_id": guess, "type": "unknown"}
        assert call(m1, tool, a)["refusal"] == "unknown_run"
    assert call(m1, "status", {"run_id": r2})["refusal"] == "unknown_run"                      # another server's run is not reachable either
    assert not (tmp_path / "r1" / guess).exists()


def test_a_run_with_a_nonce_id_replays_byte_for_byte_under_another_nonce(tmp_path):
    a = LoomServer(TASKS, str(tmp_path / "runs"), nonce="first", evidence="off")
    w = ScriptedWeaver(a, "demo/tokyo_ca", "claude-haiku-4-5")
    assert weave_tokyo(w)["ok"]
    rid = w.run_id
    d = tmp_path / "runs" / rid
    assert lg.verify(d)["status"] == "OK"
    rep = lg.replay(d)
    assert rep.identical and rep.run.run_id == rid and b"".join(rep.lines) == (d / "ops.jsonl").read_bytes()    # run_id is read from row 0
    b = LoomServer(TASKS, str(tmp_path / "runs"), nonce="second", evidence="off")
    assert b.closed(rid) == a.closed(rid)                                                       # a restarted server with another nonce reloads it
    assert b.call("status", {"run_id": rid})["refusal"] == "run_closed"                          # reachable by its id, and closed as recorded


# ---------------------------------------------------------------------------------------------------------------
# L-LOOM-46: the boundary of "one call = one row"
# ---------------------------------------------------------------------------------------------------------------
def test_every_call_that_reaches_the_server_with_an_existing_run_appends_one_row(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca", run_id="b")
    d = tmp_path / "runs" / "b"
    for tool in MODEL_OPS:
        if tool == "begin":
            continue
        n = len(rows(d))
        for args in ({}, {"zzz": 1}):
            w.call(tool, **args)
            n += 1
            assert len(rows(d)) == n, (tool, args)
    assert lg.verify(d)["status"] == "OK"


def test_a_call_with_no_run_to_write_to_leaves_no_row_and_no_folder(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca", run_id="b")
    before = sorted(p.name for p in (tmp_path / "runs").iterdir())
    n = len(rows(tmp_path / "runs" / "b"))
    assert srv.call("status", {"run_id": "nope"})["refusal"] == "unknown_run"
    assert srv.call("status", {})["refusal"] == "unknown_run"
    assert srv.call("begin", {"task_id": "nope", "model": "m"})["refusal"] == "unknown_task"
    assert srv.call("begin", {"task_id": "prose/ca"})["refusal"] == "bad_args"
    assert srv.call("rotate", {"run_id": "b"})["refusal"] == "unknown_tool"                  # not one of the 18: no op to name in a row
    assert srv.call("begin", {"task_id": "prose/ca", "model": "m", "run_id": "b"})["refusal"] == "bad_args"
    assert sorted(p.name for p in (tmp_path / "runs").iterdir()) == before and len(rows(tmp_path / "runs" / "b")) == n


# ---------------------------------------------------------------------------------------------------------------
# L-LOOM-47: the interpreter identity
# ---------------------------------------------------------------------------------------------------------------
def test_the_header_records_the_full_interpreter_identity_and_a_patch_release_is_a_mismatch(tmp_path):
    srv, w, d = tokyo(tmp_path)
    h = rows(d)[0]["result"]["header"]
    assert h["python_version"] == "%d.%d.%d" % tuple(sys.version_info[:3]) and h["python_implementation"] == platform.python_implementation()
    for field, val in (("python_version", "%d.%d.%d" % (sys.version_info[0], sys.version_info[1], sys.version_info[2] + 1)),
                       ("python_implementation", "PyPy"), ("python_version", "%d.%d" % tuple(sys.version_info[:2]))):
        dd = tmp_path / ("p_" + field + val.replace(".", "_"))
        import shutil
        shutil.copytree(str(d), str(dd))
        rehash(dd, lambda rs, f=field, v=val: rs[0]["result"]["header"].__setitem__(f, v))
        rep = lg.replay(dd)
        assert rep.status == "INPUTS" and rep.mismatch == "python_mismatch", (field, val)
        assert lg.verify(dd)["status"] == "REPLAY_INPUTS_MISMATCH"


# ---------------------------------------------------------------------------------------------------------------
# L-LOOM-48: a SandboxError in the loader is a typed status
# ---------------------------------------------------------------------------------------------------------------
def test_replay_with_a_loader_outside_the_sandbox_is_a_typed_input_mismatch_not_a_crash(tmp_path):
    srv, w, d = tokyo(tmp_path)

    def loader(path):
        raise SandboxError(path)
    rep = lg.replay(d, loader=loader)
    assert rep.status == "INPUTS" and rep.mismatch == "corpus_outside_sandbox" and rep.exit_code() == 2
    v = lg.verify(d, loader=loader)
    assert v["status"] == "REPLAY_INPUTS_MISMATCH" and v["replay"]["mismatch"] == "corpus_outside_sandbox"
    assert lg.SandboxError is SandboxError
    # through the real sandbox: a corpus the sandbox does not list
    sb = Sandbox(tmp_path / "runs", [], [])
    assert lg.replay(d, loader=sb.read_bytes).mismatch == "corpus_outside_sandbox"
    # and a live server whose run cannot reload says so with a LedgerError
    other = LoomServer([task("x", tiers=["WORD"])], str(tmp_path / "runs"), evidence="off")
    other.sandbox.read_files.clear()
    with pytest.raises(LedgerError):
        other.call("status", {"run_id": "r1"})


# ---------------------------------------------------------------------------------------------------------------
# L-LOOM-49: link pos
# ---------------------------------------------------------------------------------------------------------------
def test_link_with_a_negative_pos_other_than_minus_one_is_bad_pos_on_both_doors(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca", run_id="l")
    c = w.call("open_cross", tier="WORD", L=1)["cid"]
    assert w.call("link", cid=c, pos=-2) == {"ok": False, "refusal": "bad_pos", "detail": {"pos": -2, "thread_length": 0}}
    assert w.call("link", cid=c, pos=3)["refusal"] == "bad_pos"
    assert w.call("status")["thread"] == []
    pytest.importorskip("mcp.server.fastmcp")
    from verantyx.loom import mcp as lm
    bank = tmp_path / "tasks.jsonl"
    bank.write_text("\n".join(json.dumps(t, ensure_ascii=False) for t in TASKS) + "\n", encoding="utf-8")
    m = lm.build(str(bank), str(tmp_path / "mruns"))

    def call(tool, args):
        async def go():
            content, _ = await m.call_tool(tool, args)
            return json.loads(content[0].text)
        return asyncio.run(go())
    rid = call("begin", {"task_id": "prose/ca", "model": "m"})["run_id"]
    cid = call("open_cross", {"run_id": rid, "tier": "WORD", "L": 1})["cid"]
    r = call("link", {"run_id": rid, "cid": cid, "pos": -2})
    assert r["refusal"] == "bad_pos" and r["detail"]["pos"] == -2
    assert call("status", {"run_id": rid})["thread"] == []
    assert call("link", {"run_id": rid, "cid": cid, "pos": -1})["thread"] == [cid]                 # -1 is "the end"
    cid2 = call("open_cross", {"run_id": rid, "tier": "WORD", "L": 1})["cid"]
    assert call("link", {"run_id": rid, "cid": cid2})["thread"] == [cid, cid2]
    assert call("unlink", {"run_id": rid, "cid": cid2})["ok"]
    assert call("link", {"run_id": rid, "cid": cid2, "pos": 0})["thread"] == [cid2, cid]


# ---------------------------------------------------------------------------------------------------------------
# L-LOOM-50: the demo's task ids are the doc's; the output bytes are the same
# ---------------------------------------------------------------------------------------------------------------
def test_the_cli_demo_uses_the_task_ids_of_the_doc_and_its_output_bytes_are_unchanged(tmp_path):
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0")
    p = subprocess.run([PY, "-m", "verantyx.cli", "loom", "demo", "--corpus", CORPUS, "--runs-dir", str(tmp_path / "runs")],
                       env=env, cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert p.returncode == 0
    ca, ro = tmp_path / "runs" / "demo_ca", tmp_path / "runs" / "demo_ro"
    assert rows(ca)[0]["args"]["task_id"] == "demo/tokyo_ca" and rows(ro)[0]["args"]["task_id"] == "demo/tokyo_ro"
    assert rows(ca)[0]["result"]["task"]["mode"] == "constructed_allowed" and rows(ro)[0]["result"]["task"]["mode"] == "record_only"
    assert lg.emitted_output(ca) == {"status": "emitted", "text": "東京は日本の首都です", "output_sha": TOKYO_CA_SHA}
    assert lg.emitted_output(ro) == {"status": "emitted", "text": "東京は日本の首都", "output_sha": TOKYO_RO_SHA}
    assert (len(rows(ca)), len(rows(ro))) == (17, 14)
    bank = [json.loads(ln) for ln in open(os.path.join(ROOT, "experiments/line3/loom/tasks_demo.jsonl"), encoding="utf-8")]
    assert [t["task_id"] for t in bank] == ["demo/tokyo_ca", "demo/tokyo_ro"]
