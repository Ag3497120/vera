"""LOOM-d tests: the per-run ledger, verify, replay (docs/LINE3_LOOM_DESIGN.md 6; T-LOOM-12, 17..20).

The rows hold no wall-clock time, so a replay reproduces the file byte for byte; a forged result is REPLAY_DIFFERS, an edited byte is TAMPERED.
"""


import json


import os


import platform


import subprocess


import sys


import pytest


from verantyx.ledger_events import LedgerError, canonical


from verantyx.loom import ledger as lg


from verantyx.loom.mcp import LoomServer, append_outside_row


from verantyx.loom.scripted import ScriptedWeaver, weave_tokyo


from loom_common import CORPUS, PY, ROOT, TASKS, rows, server, task, weaver


def tokyo(tmp_path, task_id="demo/tokyo_ca", run_id="r1", model="claude-haiku-4-5"):
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, task_id, model, run_id)
    r = weave_tokyo(w)
    assert r["ok"]
    return srv, w, tmp_path / "runs" / run_id


def rehash(run_dir, mutate):
    """Edit the rows and re-hash the whole chain and HEAD (what a forger who can write the folder would do)."""
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


def test_rows_have_the_designed_shape_and_a_valid_chain(tmp_path):
    srv, w, d = tokyo(tmp_path)
    rs = rows(d)
    assert [r["i"] for r in rs] == list(range(17))
    assert [r["op"] for r in rs] == ["begin"] + ["add"] * 4 + ["open_cross", "seat", "topic", "open_cross", "seat", "seat", "open_cross", "seat", "link", "link", "link", "emit"]
    for r in rs:
        assert set(r) == {"v", "i", "actor", "op", "args", "result", "state_sha", "prev", "sha"} and r["v"] == 1 and r["actor"] == "model"
        assert r["sha"] == lg.row_sha(r) and len(r["state_sha"]) == 64
    assert rs[0]["prev"] == lg.GENESIS and all(rs[i]["prev"] == rs[i - 1]["sha"] for i in range(1, 17))
    assert (d / "HEAD").read_text().strip() == rs[-1]["sha"]
    v = lg.verify_chain(d)
    assert v["status"] == "OK" and v["n"] == 17 and v["head"] == rs[-1]["sha"]
    # the row is canonical JSON: sorted keys, compact, UTF-8 (not \u-escaped)
    raw = (d / "ops.jsonl").read_text(encoding="utf-8").splitlines()[0]
    assert raw == canonical(json.loads(raw)) and "東京" in (d / "ops.jsonl").read_text(encoding="utf-8")


def test_the_state_sha_of_every_row_is_the_sha_of_the_state_after_it(tmp_path):
    srv, w, d = tokyo(tmp_path)
    rs = rows(d)
    assert rs[-1]["state_sha"] == srv.runs["r1"].run.state.sha()
    assert len({r["state_sha"] for r in rs}) > 10
    assert rs[3]["state_sha"] != rs[4]["state_sha"]


def test_there_is_no_wall_clock_in_a_row_and_two_runs_at_different_times_are_byte_identical(tmp_path):
    a = tokyo(tmp_path / "a")[2]
    import time
    time.sleep(0.05)
    b = tokyo(tmp_path / "b")[2]
    assert (a / "ops.jsonl").read_bytes() == (b / "ops.jsonl").read_bytes()
    for r in rows(a):
        flat = json.dumps(r)
        assert "ts" not in r and "time" not in r and "t_ns" not in flat
    t = [json.loads(ln) for ln in (a / "timing.jsonl").read_text().splitlines()]
    assert [x["i"] for x in t] == list(range(17)) and all(set(x) == {"i", "t_ns"} for x in t)
    assert t[-1]["t_ns"] >= t[1]["t_ns"] >= 0


def test_timing_is_outside_the_chain(tmp_path):
    srv, w, d = tokyo(tmp_path)
    (d / "timing.jsonl").write_text("garbage\n")
    assert lg.verify(d, corpus_path=CORPUS)["status"] == "OK"


def test_empty_folder_is_EMPTY(tmp_path):
    (tmp_path / "x").mkdir()
    assert lg.verify_chain(tmp_path / "x")["status"] == "EMPTY"
    assert lg.verify_chain(tmp_path / "nonexistent")["status"] == "EMPTY"


def test_an_edited_byte_is_TAMPERED(tmp_path):
    srv, w, d = tokyo(tmp_path)
    p = d / "ops.jsonl"
    raw = p.read_text(encoding="utf-8")
    assert "東京は日本の首都です" in raw
    p.write_text(raw.replace("東京は日本の首都です", "東京は日本の首都でした"), encoding="utf-8")
    v = lg.verify(d)
    assert v["status"] == "TAMPERED" and any(x["type"] == "SHA_MISMATCH" for x in v["problems"])
    assert "replay" not in v                                                        # a broken chain is not replayed
    out = lg.emitted_output(d)
    assert out["status"] == "run_not_verified" and out["verify"] == "TAMPERED"


def test_a_dropped_or_reordered_row_is_TAMPERED(tmp_path):
    srv, w, d = tokyo(tmp_path)
    lines = (d / "ops.jsonl").read_bytes().split(b"\n")
    del lines[5]
    (d / "ops.jsonl").write_bytes(b"\n".join(lines))
    assert lg.verify_chain(d)["status"] == "TAMPERED"
    srv, w, d2 = tokyo(tmp_path / "b")
    lines = (d2 / "ops.jsonl").read_bytes().split(b"\n")
    lines[3], lines[4] = lines[4], lines[3]
    (d2 / "ops.jsonl").write_bytes(b"\n".join(lines))
    v = lg.verify_chain(d2)
    assert v["status"] == "TAMPERED" and {x["type"] for x in v["problems"]} >= {"PREV_MISMATCH"}


def test_a_torn_tail_is_TORN_TAIL_and_blocks_an_append(tmp_path):
    srv, w, d = tokyo(tmp_path)
    p = d / "ops.jsonl"
    p.write_bytes(p.read_bytes()[:-1])                                               # the last line has no newline
    assert lg.verify_chain(d)["status"] == "TORN_TAIL"
    with pytest.raises(LedgerError) as e:
        with lg.Ledger(d).locked() as lk:
            lk.tail()
    assert e.value.code == "TORN_TAIL_BLOCKS_APPEND"
    p.write_bytes(p.read_bytes() + b'{"half": ')
    assert lg.verify_chain(d)["status"] in ("TORN_TAIL", "TAMPERED")


def test_a_wrong_head_is_HEAD_MISMATCH_and_an_external_head_is_checked(tmp_path):
    srv, w, d = tokyo(tmp_path)
    good = (d / "HEAD").read_text().strip()
    assert lg.verify_chain(d, good)["status"] == "OK"
    v = lg.verify_chain(d, "0" * 64)
    assert v["status"] == "HEAD_MISMATCH" and v["problems"][0]["type"] == "EXPECTED_HEAD_MISMATCH"
    (d / "HEAD").write_text("f" * 64 + "\n")
    v = lg.verify_chain(d)
    assert v["status"] == "HEAD_MISMATCH" and v["problems"][0].get("HEAD_NOT_IN_CHAIN") is True
    rs = rows(d)
    (d / "HEAD").write_text(rs[-3]["sha"] + "\n")
    assert lg.verify_chain(d)["problems"][0]["HEAD_POINTS_TO_LINE"] == 15
    (d / "HEAD").unlink()
    assert lg.verify_chain(d)["problems"][0]["type"] == "HEAD_MISSING"


def test_replay_is_byte_identical_in_both_modes(tmp_path):
    for task_id, text in (("demo/tokyo_ca", "東京は日本の首都です"), ("demo/tokyo_ro", "東京は日本の首都")):
        srv, w, d = tokyo(tmp_path / task_id.split("/")[1], task_id)
        rep = lg.replay(d)
        assert rep.status == "IDENTICAL" and rep.exit_code() == 0 and rep.text == text
        assert b"".join(rep.lines) == (d / "ops.jsonl").read_bytes()
        assert lg.verify(d)["status"] == "OK"
        assert lg.verify(d)["replay"]["text"] == text


def test_replay_of_a_run_with_refusals_caps_and_harness_rows(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca", run_id="busy")
    w.call("lookup", text="日本", tier="any")
    w.call("add", text="見つからない", kind="record", tier="WORD")
    w.call("seat", cid="c9", seat="centre", uid="u1")
    w.call("add", text="sk-ant-aaaaaaaaaaaa", kind="constructed")
    w.call("add", text="Ωa", kind="constructed")
    w.call("open_cross", tier="WORD", L=2)
    w.call("emit")
    w.say("答えは東京です")
    for _ in range(25):
        w.call("read")
    w.call("abstain", type="unknown")
    w.call("status")
    w.done()
    d = tmp_path / "runs" / "busy"
    assert lg.verify(d)["status"] == "OK"
    assert b"".join(lg.replay(d).lines) == (d / "ops.jsonl").read_bytes()
    ops = [r["op"] for r in rows(d)]
    assert "free_text_dropped" in ops and ops.count("read") == 25


def test_a_forged_result_with_a_rehashed_chain_is_REPLAY_DIFFERS(tmp_path):
    srv, w, d = tokyo(tmp_path)

    def forge(rs):
        rs[-1]["result"]["text"] = "東京は日本の首都でした"
    rehash(d, forge)
    assert lg.verify_chain(d)["status"] == "OK"                                       # the chain alone cannot tell
    v = lg.verify(d)
    assert v["status"] == "REPLAY_DIFFERS" and v["replay"]["first_diff"] == {"i": 16, "field": "result"}
    out = lg.emitted_output(d)
    assert out["status"] == "run_not_verified" and out["verify"] == "REPLAY_DIFFERS"
    assert lg.replay(d).exit_code() == 1


def test_a_forged_argument_or_state_sha_is_REPLAY_DIFFERS_at_that_row(tmp_path):
    srv, w, d = tokyo(tmp_path)
    rehash(d, lambda rs: rs[9]["args"].__setitem__("seat", "-z:0"))                   # 日本 seated on が instead of の, results untouched
    v = lg.verify(d)
    assert v["status"] == "REPLAY_DIFFERS" and v["replay"]["first_diff"]["i"] == 9
    srv, w, d2 = tokyo(tmp_path / "b")
    rehash(d2, lambda rs: rs[7].__setitem__("state_sha", "0" * 64))
    v = lg.verify(d2)
    assert v["status"] == "REPLAY_DIFFERS" and v["replay"]["first_diff"] == {"i": 7, "field": "state_sha"}


def test_an_inserted_row_is_REPLAY_DIFFERS(tmp_path):
    srv, w, d = tokyo(tmp_path)
    rehash(d, lambda rs: rs.insert(5, {"v": 1, "i": 0, "actor": "model", "op": "status", "args": {}, "result": {"ok": True}, "state_sha": rs[4]["state_sha"], "prev": ""}))
    v = lg.verify(d)
    assert v["status"] == "REPLAY_DIFFERS" and v["replay"]["first_diff"]["i"] == 5


def test_a_row_the_server_would_never_write_is_a_difference_not_a_crash(tmp_path):
    srv, w, d = tokyo(tmp_path)
    rehash(d, lambda rs: rs[3].__setitem__("op", "rotate"))
    assert lg.verify(d)["status"] == "REPLAY_DIFFERS"
    srv, w, d2 = tokyo(tmp_path / "b")
    rehash(d2, lambda rs: rs[3].__setitem__("actor", "root"))
    assert lg.verify(d2)["status"] == "REPLAY_DIFFERS"
    srv, w, d3 = tokyo(tmp_path / "c")
    rehash(d3, lambda rs: rs.__setitem__(0, dict(rs[0], op="status")))
    assert lg.verify(d3)["status"] == "REPLAY_DIFFERS"


def test_a_changed_corpus_is_REPLAY_INPUTS_MISMATCH_and_a_missing_one_is_unresolved(tmp_path):
    srv, w, d = tokyo(tmp_path)
    alt = tmp_path / "alt.jsonl"
    data = open(CORPUS, encoding="utf-8").read().splitlines()
    alt.write_text("\n".join(data[:-1]) + "\n", encoding="utf-8")
    rep = lg.replay(d, str(alt))
    assert rep.status == "INPUTS" and rep.mismatch == "corpus_sha_mismatch" and rep.exit_code() == 2
    assert lg.verify(d, corpus_path=str(alt))["status"] == "REPLAY_INPUTS_MISMATCH"
    (d / "meta.json").unlink()
    assert lg.replay(d).identical                                                      # LOOM-path: no meta.json at all, the recorded sha is found in the registry of shipped corpora
    toy = tmp_path / "toy.jsonl"
    toy.write_text(json.dumps({"sha": "0" * 64, "title": "t", "sent": "東京は日本の首都です。", "source": "t0#0"}, ensure_ascii=False) + "\n", encoding="utf-8")
    srv2 = LoomServer([dict(TASKS[0], corpus=str(toy))], str(tmp_path / "runs2"), (), "strict_npa", evidence="off")
    w2 = ScriptedWeaver(srv2, "demo/tokyo_ca", "m", "t1")
    w2.begin()
    (tmp_path / "runs2" / "t1" / "meta.json").unlink()
    r2 = lg.replay(tmp_path / "runs2" / "t1")                                          # a corpus no registry entry matches, and no pointer: unresolved
    assert r2.status == "INPUTS" and r2.mismatch == "corpus_unresolved"
    assert lg.replay(d, str(tmp_path / "gone.jsonl")).mismatch == "corpus_unreadable"
    assert lg.replay(d, CORPUS).status == "IDENTICAL"                                  # the path is only a pointer; the sha decides


def test_each_header_field_has_its_own_typed_mismatch(tmp_path):
    srv, w, d = tokyo(tmp_path)
    for field, name, newval in (("python_version", "python_mismatch", "2.7"), ("loom_version", "loom_version_mismatch", "loom.v0"),
                                ("space_sha", "space_sha_mismatch", "0" * 64), ("seats_sha", "seats_sha_mismatch", "1" * 64),
                                ("adhesion_sha", "adhesion_sha_mismatch", {"RUN": "0", "WORD": "0", "CHAR": "0"}),
                                ("corpus_sha", "corpus_sha_mismatch", "2" * 64)):
        dd = tmp_path / ("h_" + field)
        import shutil
        shutil.copytree(str(d), str(dd))
        rehash(dd, lambda rs, f=field, v=newval: rs[0]["result"]["header"].__setitem__(f, v))
        rep = lg.replay(dd)
        assert rep.status == "INPUTS" and rep.mismatch == name, (field, rep.status, rep.mismatch)


def test_the_header_holds_the_shas_and_no_path(tmp_path):
    srv, w, d = tokyo(tmp_path)
    h = rows(d)[0]["result"]["header"]
    assert set(h) == {"loom_version", "python_version", "python_implementation", "corpus_sha", "space_sha", "adhesion_sha", "seats_sha", "code_index_sha", "stability_mode", "declared_model"}
    assert h["python_version"] == "%d.%d.%d" % tuple(sys.version_info[:3]) and h["declared_model"] == "claude-haiku-4-5"
    assert h["python_implementation"] == platform.python_implementation()        # L-LOOM-47
    assert set(h["adhesion_sha"]) == {"RUN", "WORD", "CHAR"}
    assert ROOT not in (d / "ops.jsonl").read_text(encoding="utf-8") and "fulllead" not in (d / "ops.jsonl").read_text(encoding="utf-8")
    meta = json.loads((d / "meta.json").read_text())
    assert meta["corpus"].endswith("fulllead_sents.jsonl")                              # the path lives outside the chain


def test_a_restarted_server_continues_the_run_from_its_ledger(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca", run_id="resume")
    u = w.call("add", text="Ωa", kind="constructed")["uid"]
    c = w.call("open_cross", tier="WORD", L=1)["cid"]
    srv2 = server(tmp_path)                                                              # a new process, the same runs folder
    assert "resume" not in srv2.runs
    r = srv2.call("seat", {"run_id": "resume", "cid": c, "seat": "centre", "uid": u})
    assert r["ok"] is True
    srv2.call("link", {"run_id": "resume", "cid": c})
    e = srv2.call("emit", {"run_id": "resume"})
    assert e["ok"] and e["text"] == "Ωa"
    assert lg.verify(tmp_path / "runs" / "resume")["status"] == "OK"
    # the old server notices the rows it did not write and rebuilds from the file
    old = srv.call("status", {"run_id": "resume"})
    assert old["refusal"] == "run_closed" and old["detail"]["closed"][0] == "emitted"
    assert lg.verify(tmp_path / "runs" / "resume")["status"] == "OK"


def test_a_row_appended_by_the_harness_cli_is_picked_up_by_the_live_server(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca", run_id="live")
    w.call("add", text="Ωa", kind="constructed")
    d = tmp_path / "runs" / "live"
    row = append_outside_row(d, "harness", "free_text_dropped", {"sha256": "a" * 64, "chars": 5})
    assert row["i"] == 2 and row["actor"] == "harness"
    r = w.call("add", text="Ωb", kind="constructed")
    assert r["ok"] and r["uid"] == "u2" and r["prov"]["at"] == 3                       # `at` is the true row index, harness rows included
    append_outside_row(d, "harness", "abandoned", {"reason": "no_close"})
    assert w.call("status")["refusal"] == "run_closed"
    assert lg.verify(d)["status"] == "OK"
    assert srv.closed("live") == ["abandoned", "no_close"]


def test_append_outside_row_refuses_a_run_that_does_not_replay(tmp_path):
    srv, w, d = tokyo(tmp_path)
    rehash(d, lambda rs: rs[-1]["result"].__setitem__("text", "x"))
    with pytest.raises(LedgerError):
        append_outside_row(d, "harness", "free_text_dropped", {"sha256": "a" * 64, "chars": 1})


def test_the_free_text_row_holds_a_sha_and_a_length_never_the_text(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca", run_id="ft")
    w.say("答えは東京です")
    raw = (tmp_path / "runs" / "ft" / "ops.jsonl").read_text(encoding="utf-8")
    assert "答えは東京です" not in raw
    r = rows(tmp_path / "runs" / "ft")[-1]
    import hashlib
    assert r["op"] == "free_text_dropped" and r["args"] == {"sha256": hashlib.sha256("答えは東京です".encode()).hexdigest(), "chars": 7} and r["actor"] == "harness"


def test_a_control_run_keeps_its_text_because_the_text_is_its_output(tmp_path):
    srv = server(tmp_path)
    w = weaver(srv, "prose/ca", run_id="ctl")
    srv.harness("ctl", "free_text_control", {"sha256": "b" * 64, "chars": 3, "text": "不明"})
    assert "不明" in (tmp_path / "runs" / "ctl" / "ops.jsonl").read_text(encoding="utf-8")


def test_emitted_output_states(tmp_path):
    srv, w, d = tokyo(tmp_path)
    out = lg.emitted_output(d)
    assert out["status"] == "emitted" and out["text"] == "東京は日本の首都です" and len(out["output_sha"]) == 64
    srv2 = server(tmp_path / "x")
    w2 = weaver(srv2, "prose/ca", run_id="none")
    w2.call("abstain", type="no_record")
    assert lg.emitted_output(tmp_path / "x" / "runs" / "none") == {"status": "no_output"}


def test_ledgers_are_byte_identical_across_processes_and_hash_seeds(tmp_path):
    outs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=ROOT)
        runs = tmp_path / ("seed" + seed)
        p = subprocess.run([PY, "-m", "verantyx.harness.cli", "loom", "demo", "--corpus", CORPUS, "--runs-dir", str(runs)], env=env, cwd=ROOT,
                           capture_output=True, text=True, timeout=300)
        assert p.returncode == 0, p.stderr
        outs.append((runs, p.stdout))
    for name in ("demo_ca", "demo_ro"):
        blobs = {(r / name / "ops.jsonl").read_bytes() for r, _ in outs}
        assert len(blobs) == 1, name
        assert len({(r / name / "HEAD").read_text() for r, _ in outs}) == 1
    assert len({o for _, o in outs}) == 1


def test_the_cli_replay_verify_output_note_close(tmp_path):
    env = dict(os.environ, PYTHONHASHSEED="0", PYTHONPATH=ROOT)
    runs = tmp_path / "runs"

    def cli(*a):
        return subprocess.run([PY, "-m", "verantyx.harness.cli", "loom"] + list(a), env=env, cwd=ROOT, capture_output=True, text=True, timeout=300)
    assert cli("demo", "--corpus", CORPUS, "--runs-dir", str(runs)).returncode == 0
    d = str(runs / "demo_ca")
    p = cli("replay", d, "--out", str(tmp_path / "re.jsonl"))
    assert p.returncode == 0 and p.stdout.strip() == "東京は日本の首都です" and "REPLAY_IDENTICAL" in p.stderr
    assert (tmp_path / "re.jsonl").read_bytes() == (runs / "demo_ca" / "ops.jsonl").read_bytes()
    v = cli("verify", d)
    assert v.returncode == 0 and json.loads(v.stdout)["status"] == "OK"
    o = cli("output", d)
    assert o.returncode == 0 and json.loads(o.stdout)["text"] == "東京は日本の首都です"
    ft = tmp_path / "ft.txt"
    ft.write_text("自由な答え", encoding="utf-8")
    assert cli("note", d, "--free-text-file", str(ft), "--driver", "scripted", "--requested-model", "claude-haiku-4-5").returncode == 0
    assert "自由な答え" not in (runs / "demo_ca" / "ops.jsonl").read_text(encoding="utf-8")
    assert json.loads(cli("verify", d).stdout)["status"] == "OK"
    c = cli("close", d)
    assert c.returncode == 0 and "emitted" in c.stdout
    # tamper -> verify / output / replay say so
    p_ = runs / "demo_ro" / "ops.jsonl"
    p_.write_text(p_.read_text(encoding="utf-8").replace("東京は日本の首都", "東京は日本の首都X"), encoding="utf-8")
    assert cli("verify", str(runs / "demo_ro")).returncode == 1
    assert json.loads(cli("output", str(runs / "demo_ro")).stdout)["status"] == "run_not_verified"
    assert cli("replay", str(runs / "demo_ro")).returncode == 1
    assert cli("replay", str(runs / "nonexistent")).returncode in (1, 2)
