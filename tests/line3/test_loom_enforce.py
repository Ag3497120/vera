"""LOOM enforcement tests, the layers that exist in the core (docs/LINE3_LOOM_DESIGN.md 7): L3 process isolation in code and the L4 emit gate.
(T-LOOM-30, 32, 33; L1 = the subagent files and L2 = the API driver are later tickets, T-LOOM-31 / 34 / 35.)

The output of a run is the text of its successful `emit` row, read only from a ledger whose verify is OK.  Free text, lookups, reads, statuses
and refused emits are never output.
"""
import ast
import hashlib
import os
import shutil

import pytest

from verantyx.loom import ledger as lg
from verantyx.loom.mcp import LoomServer, Sandbox, SandboxError
from verantyx.loom.scripted import ScriptedWeaver, say_only, weave_tokyo
from loom_common import CORPUS, ROOT, TASKS, rows, server, task

LOOM = os.path.join(ROOT, "verantyx/loom")


def sha(b):
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------------------------------------------
# T-LOOM-30: a weaver that answers in free text gets nothing scored
# ---------------------------------------------------------------------------------------------------------------
def test_a_weaver_that_answers_in_free_text_has_no_output(tmp_path):
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "demo/tokyo_ro", "m", "free")
    say_only(w, "答えは東京です")
    d = tmp_path / "runs" / "free"
    ops = [(r["actor"], r["op"]) for r in rows(d)]
    assert ops == [("model", "begin"), ("harness", "free_text_dropped"), ("harness", "abandoned")]
    assert not any(r["op"] == "emit" for r in rows(d))
    assert lg.emitted_output(d) == {"status": "no_output"}
    fd_ = rows(d)[1]["args"]
    assert fd_ == {"sha256": sha("答えは東京です".encode()), "chars": 7}
    assert "答えは東京です" not in (d / "ops.jsonl").read_text(encoding="utf-8")                    # only the sha reaches the ledger


def test_saying_the_gold_and_then_emitting_something_else_scores_the_emitted_text_only(tmp_path):
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "demo/tokyo_ro", "m", "gold")
    w.begin()
    w.say("東京は日本の首都")                                  # the 'gold', in free text
    u = w.call("add", text="東京", kind="record", tier="WORD")["uid"]
    c = w.call("open_cross", tier="WORD", L=1)["cid"]
    w.call("seat", cid=c, seat="centre", uid=u)
    w.call("link", cid=c)
    assert w.call("emit")["text"] == "東京"
    w.say("やはり答えは東京は日本の首都です")
    w.done()
    out = lg.emitted_output(tmp_path / "runs" / "gold")
    assert out["status"] == "emitted" and out["text"] == "東京" and out["output_sha"] == sha("東京".encode())


def test_a_dry_run_read_is_not_an_output(tmp_path):
    srv, w = server(tmp_path), None
    w = ScriptedWeaver(srv, "demo/tokyo_ro", "m", "dry")
    w.begin()
    u = w.call("add", text="東京", kind="record", tier="WORD")["uid"]
    c = w.call("open_cross", tier="WORD", L=1)["cid"]
    w.call("seat", cid=c, seat="centre", uid=u)
    w.call("link", cid=c)
    assert w.call("read")["text"] == "東京"
    w.done()
    assert lg.emitted_output(tmp_path / "runs" / "dry") == {"status": "no_output"}


def test_a_refused_emit_and_an_abstention_are_not_outputs(tmp_path):
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "demo/tokyo_ro", "m", "ref")
    w.begin()
    assert w.call("emit")["ok"] is False
    w.call("abstain", type="cannot_weave")
    assert lg.emitted_output(tmp_path / "runs" / "ref") == {"status": "no_output"}


def test_the_output_of_a_run_is_only_its_emit_row(tmp_path):
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "demo/tokyo_ca", "m", "emit")
    weave_tokyo(w)
    d = tmp_path / "runs" / "emit"
    emits = [r for r in rows(d) if r["op"] == "emit"]
    assert len(emits) == 1 and lg.emitted_output(d)["text"] == emits[0]["result"]["text"]


# ---------------------------------------------------------------------------------------------------------------
# T-LOOM-33: L4, a run that does not verify is not scored
# ---------------------------------------------------------------------------------------------------------------
def test_an_edited_ledger_is_not_scored(tmp_path):
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "demo/tokyo_ca", "m", "t1")
    weave_tokyo(w)
    d = tmp_path / "runs" / "t1"
    p = d / "ops.jsonl"
    p.write_text(p.read_text(encoding="utf-8").replace("東京は日本の首都です", "東京は日本の首都でした"), encoding="utf-8")
    assert lg.verify(d)["status"] == "TAMPERED"
    assert lg.emitted_output(d)["status"] == "run_not_verified"


def test_a_re_hashed_forgery_is_not_scored(tmp_path):
    from test_loom_ledger import rehash
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "demo/tokyo_ro", "m", "t2")
    weave_tokyo(w)
    d = tmp_path / "runs" / "t2"
    rehash(d, lambda rs: rs[-1]["result"].__setitem__("text", "日本は東京の首都"))
    assert lg.verify_chain(d)["status"] == "OK"
    assert lg.verify(d)["status"] == "REPLAY_DIFFERS"
    assert lg.emitted_output(d)["status"] == "run_not_verified"


def test_a_forged_emit_row_in_a_run_that_never_emitted_is_not_scored(tmp_path):
    from test_loom_ledger import rehash
    srv = server(tmp_path)
    w = ScriptedWeaver(srv, "demo/tokyo_ro", "m", "t3")
    say_only(w)
    d = tmp_path / "runs" / "t3"
    forged = {"v": 1, "i": 0, "actor": "model", "op": "emit", "args": {}, "result": {"ok": True, "status": "emitted", "text": "答え", "output_sha": sha("答え".encode())},
              "state_sha": rows(d)[0]["state_sha"], "prev": ""}
    rehash(d, lambda rs: rs.insert(1, forged))
    assert lg.verify_chain(d)["status"] == "OK"
    assert lg.emitted_output(d)["status"] == "run_not_verified"


# ---------------------------------------------------------------------------------------------------------------
# T-LOOM-32: L3 in code
# ---------------------------------------------------------------------------------------------------------------
def test_the_sandbox_reads_only_the_corpus_and_writes_only_the_run_folder(tmp_path):
    runs = tmp_path / "runs"
    sb = Sandbox(runs, [CORPUS])
    assert sb.read_bytes(CORPUS) == open(CORPUS, "rb").read()
    for bad in (os.path.join(os.path.dirname(CORPUS), "..", "..", "..", "..", "pytest.ini"), "/etc/passwd", str(tmp_path / "other.txt"),
                os.path.join(ROOT, "verantyx/cli.py"), os.path.dirname(CORPUS)):
        with pytest.raises(SandboxError):
            sb.read_bytes(bad)
    for bad in ("..", ".", "../x", "a/b", "/abs", "", "x\x00y", ".hidden", "a" * 65, None, 3):
        with pytest.raises(SandboxError):
            sb.run_dir(bad)
    assert sb.run_dir("ok-1.2_x") == runs.resolve() / "ok-1.2_x"


def test_a_symlink_cannot_lead_the_sandbox_out(tmp_path):
    runs = tmp_path / "runs"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    sb = Sandbox(runs, [CORPUS], [tmp_path / "root"])
    (tmp_path / "root").mkdir()
    os.symlink(str(outside / "secret.txt"), str(tmp_path / "root" / "link.txt"))
    with pytest.raises(SandboxError):
        sb.read_bytes(str(tmp_path / "root" / "link.txt"))                              # inside an allowed root, but it resolves outside
    (tmp_path / "root" / "ok.txt").write_text("fine")
    assert sb.read_bytes(str(tmp_path / "root" / "ok.txt")) == b"fine"
    os.symlink(str(outside), str(runs / "escape"))                                      # a run folder that is a link to elsewhere
    with pytest.raises(SandboxError):
        sb.run_dir("escape")
    os.symlink(CORPUS, str(tmp_path / "corpus_link.jsonl"))
    assert sb.read_bytes(str(tmp_path / "corpus_link.jsonl")) == open(CORPUS, "rb").read()       # a link to an allowed file is the allowed file


def test_tool_arguments_cannot_name_a_path(tmp_path):
    srv = server(tmp_path)
    for rid in ("../escape", "/tmp/x", "a/../b", "..", "runs/../..", "x\x00"):
        assert srv.call("status", {"run_id": rid})["refusal"] == "unknown_run"
        assert srv.begin("demo/tokyo_ca", "m", rid)["refusal"] == "bad_run_id"
    assert sorted(os.listdir(str(tmp_path))) == ["runs"] and os.listdir(str(tmp_path / "runs")) == []


def test_a_task_naming_a_corpus_outside_the_bank_cannot_be_read_through_a_tool(tmp_path):
    srv = server(tmp_path)
    srv.tasks["demo/tokyo_ca"]["corpus"] = "/etc/passwd"                                 # tampering with the in-memory bank after start
    assert srv.begin("demo/tokyo_ca", "m", "x")["refusal"] == "path_outside_sandbox"


def test_the_server_writes_nothing_outside_the_run_folder(tmp_path):
    before = sha(open(CORPUS, "rb").read())
    snap = {}
    for root, _, files in os.walk(os.path.dirname(CORPUS)):
        for f in files:
            snap[os.path.join(root, f)] = os.stat(os.path.join(root, f)).st_mtime_ns
    srv = server(tmp_path)
    weave_tokyo(ScriptedWeaver(srv, "demo/tokyo_ca", "m", "r"))
    created = set()
    for root, dirs, files in os.walk(str(tmp_path)):
        for f in files:
            created.add(os.path.relpath(os.path.join(root, f), str(tmp_path)))
    assert created == {os.path.join("runs", "r", n) for n in ("ops.jsonl", "HEAD", ".lock", "timing.jsonl", "meta.json")}
    assert sha(open(CORPUS, "rb").read()) == before
    for p, m in snap.items():
        assert os.stat(p).st_mtime_ns == m


FORBIDDEN_MODULES = {"socket", "ssl", "urllib", "http", "requests", "subprocess", "ftplib", "smtplib", "telnetlib", "xmlrpc", "multiprocessing",
                     "ctypes", "webbrowser"}


def test_the_loom_package_imports_no_network_and_no_process_module():
    files = sorted(f for f in os.listdir(LOOM) if f.endswith(".py"))
    assert {"state.py", "ops.py", "read.py", "code.py", "ledger.py", "mcp.py", "scripted.py", "corpus.py"} <= set(files)
    for fn in files:
        tree = ast.parse(open(os.path.join(LOOM, fn), encoding="utf-8").read())
        for n in ast.walk(tree):
            mods = []
            if isinstance(n, ast.Import):
                mods = [a.name for a in n.names]
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods = [n.module]
            for m in mods:
                assert m.split(".")[0] not in FORBIDDEN_MODULES, "%s imports %s" % (fn, m)
            if isinstance(n, ast.Call):
                f = n.func
                if isinstance(f, ast.Name) and f.id in ("eval", "exec", "__import__", "compile"):
                    raise AssertionError("%s calls %s" % (fn, f.id))
                if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "os" and f.attr in (
                        "system", "popen", "execv", "execve", "execl", "execvp", "spawnl", "spawnv", "fork", "kill", "remove", "unlink", "rmdir", "rename"):
                    raise AssertionError("%s calls os.%s" % (fn, f.attr))


def test_only_the_ledger_and_the_server_touch_files():
    for fn in ("state.py", "ops.py", "read.py", "code.py", "corpus.py", "scripted.py"):
        src = open(os.path.join(LOOM, fn), encoding="utf-8").read()
        tree = ast.parse(src)
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                f = n.func
                name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
                assert name not in ("open", "read_bytes", "read_text", "write_bytes", "write_text", "mkdir", "listdir", "walk"), "%s calls %s" % (fn, name)
