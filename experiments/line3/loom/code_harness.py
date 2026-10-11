"""The `tests` step of a CODE run (docs/LINE3_LOOM_DESIGN.md 5.2 "Tests are not a gate of `emit` ... run by the harness after emit ... an attest
row (record: exit code)"; ticket LOOM-code, L-LOOM-73, 78, 82).

It lives HERE, not in verantyx/loom, because it runs a process and the loom package imports none (T-LOOM-32).  What it does:

  0. THE GATES OF THE LOOM ARE NOT A SAFETY WALL (L-LOOM-72/78): they prove where each token came from and the order of the definitions.
     A woven text that passed every gate still runs with the rights of the user who runs this step.  So a weave from a real model
     (driver != "scripted") is REFUSED (`isolation_required`) unless `--isolation-confirmed <token>` names the isolation the operator has
     put around this process (a VM, a container, the Air); the token is recorded in the attest row, and it is the operator's statement, which
     this module does not check.  Scripted runs (fixed texts of scripted_code.py) are allowed.
  1. `emitted_output(run_dir)`: the text of a run is its verified `emit` row and nothing else.  What was tested is read from THE RUN: target and
     tests from row 0, the fixture from meta.json (never from a caller's task row).
  2. copy the fixture into a fresh temporary folder, check the COPY against the run's `code_index_sha` and take `tests_sha` (the bytes of every
     .py file the index does not hold: tests/, test_*.py, conftest.py), append the emitted text to the target file (after two blank lines),
  3. run `python -m pytest -q -p no:cacheprovider --rootdir <copy> -- <the run's test files>` with cwd = the copy, a cleaned environment
     (PYTHONPATH = the copy, HOME = the temporary folder, PYTHONHASHSEED=0, no bytecode), stdin = /dev/null and a 60 s timeout (design 9.4);
     the real fixture is never written,
  4. append ONE `attest` row {kind: "tests", tests, target, code_index_sha, tests_sha, text_sha, driver, isolation_token, exit_code} to the
     run's ledger (`append_outside_row`: the run is replayed first, so a run that does not verify gets no row).  No path, no time, no pytest
     output enters the row.  Running the step twice appends a second row (LOOM-i decides what that means).

The argv is built here from the run's relative file names; the task bank carries no command line.  Network is not cut at the OS level and the
step runs on THIS machine, not the Air (open points: LOOM-d2); the fixture tests are pure Python.

    python experiments/line3/loom/code_harness.py table <runs_dir>                                  # the K1..K5 scripted table
    python experiments/line3/loom/code_harness.py test <run_dir> [--isolation-confirmed <token>]     # the tests step of one existing run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

from verantyx.loom import fixture as fx
from verantyx.loom import ledger as lg
from verantyx.loom.mcp import LoomServer, append_outside_row
from verantyx.loom.scripted import ScriptedWeaver

ROOT = Path(__file__).resolve().parents[3]
TIMEOUT_S = 60                                            # design 9.4
SCRIPTED = "scripted"                                     # the driver of run_k; anything else is a model (or a person) and needs isolation
ISOLATION_TOKEN_RX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@=-]{2,63}$")     # a LABEL the operator chooses ("vm-air-2026-10-11"), not a credential
TAIL_CHARS = 600


def load_tasks(path=None, root=ROOT) -> List[dict]:
    """The task bank with its corpus / fixture paths made absolute against the repo root."""
    path = Path(path) if path else Path(__file__).with_name("tasks_code.jsonl")
    rows = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for r in rows:
        for k in ("corpus", "fixture"):
            if k in r and not os.path.isabs(r[k]):
                r[k] = str(Path(root) / r[k])
    return rows


def _plain_reader(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def held_out_sha(work: Path, index) -> str:
    """`tests_sha` (L-LOOM-82): sha256 of the canonical {v, files: {relpath: sha256(bytes)}} of every .py file of the fixture copy that the
    CODE index does NOT hold (tests/, test_*.py, conftest.py anywhere) - the bytes the exit code depends on besides the indexed package, which
    `code_index_sha` covers.  __pycache__ and dot-folders are left out, as in the index."""
    held = {}
    for p in sorted(work.rglob("*.py")):
        rel = p.relative_to(work).as_posix()
        parts = rel.split("/")
        if p.is_file() and rel not in index.file_sha and "__pycache__" not in parts and not any(x.startswith(".") for x in parts):
            held[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return hashlib.sha256(json.dumps({"v": "tests_sha.v1", "files": held}, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def run_pytest(fixture_root, target_file: str, text: str, test_files: List[str], timeout: int = TIMEOUT_S,
               expect_index_sha: Optional[str] = None) -> dict:
    """Insert `text` at the end of `target_file` in a copy of the fixture and run the test files there.  Returns
    {exit_code, passed, tail, code_index_sha, tests_sha}; exit_code is pytest's (0 pass, 1 fail, 2 interrupted, 4 usage, 5 none collected) or
    "timeout" as -9.  The COPY is checked first: when `expect_index_sha` is given and the copy's CODE index differs (the fixture changed
    between the run and now), nothing runs and the result is {status: "fixture_changed", expected, found}; an unreadable fixture is
    {status: "fixture_unreadable"}."""
    with tempfile.TemporaryDirectory(prefix="loom_code_") as tmp:
        work = Path(tmp) / "fx"
        shutil.copytree(str(fixture_root), str(work), ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
        try:
            index = fx.build_index(work, _plain_reader)
        except (OSError, ValueError):
            return {"status": "fixture_unreadable"}
        if expect_index_sha is not None and index.sha != expect_index_sha:
            return {"status": "fixture_changed", "expected": expect_index_sha, "found": index.sha}
        tests_sha = held_out_sha(work, index)
        target = work / target_file
        body = target.read_text(encoding="utf-8").rstrip("\n")
        target.write_text(body + ("\n\n\n" if body else "") + text, encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", os.defpath), "PYTHONPATH": str(work), "PYTHONHASHSEED": "0", "PYTHONDONTWRITEBYTECODE": "1",
               "HOME": tmp, "LC_ALL": "C.UTF-8", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
        argv = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(work), "--"] + list(test_files)
        try:
            p = subprocess.run(argv, cwd=str(work), env=env, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
            rc, out = p.returncode, (p.stdout + p.stderr)
        except subprocess.TimeoutExpired:
            rc, out = -9, "timeout"
    return {"exit_code": rc, "passed": rc == 0, "tail": out[-TAIL_CHARS:], "code_index_sha": index.sha, "tests_sha": tests_sha}


def what_the_run_names(run_dir) -> Optional[dict]:
    """{fixture, target, tests, code_index_sha} as the RUN recorded them (row 0 and meta.json), or None when the run is not a code run that
    names a target and tests.  The caller's task bank is not consulted: what is tested is what the run was woven for."""
    lines, _ = lg.read_lines(run_dir)
    try:
        res = json.loads(lines[0])["result"]
        task, header = res["task"], res["header"]
        fixture = lg.Ledger(run_dir).read_meta().get("fixture")
        target = (task.get("target") or {}).get("file")
        tests = task.get("tests")
        sha = header.get("code_index_sha")
    except (IndexError, KeyError, TypeError, ValueError):
        return None
    if not (fixture and target and tests and sha):
        return None
    return {"fixture": fixture, "target": target, "tests": list(tests), "code_index_sha": sha}


def test_emitted_run(run_dir, driver: str = "model", isolation_token: Optional[str] = None, append_attest: bool = True) -> dict:
    """The `tests` step for one run.  Returns {status, ...}:
      {"status": "no_output"} (the run emitted nothing), {"status": "run_not_verified", ...},
      {"status": "not_a_code_run"} (row 0 / meta.json name no fixture, target and tests),
      {"status": "isolation_required"} (driver is not "scripted" and no isolation token: NOTHING is run),
      {"status": "isolation_token_invalid"},
      {"status": "fixture_changed" | "fixture_unreadable"} (the copy is not the fixture the run was woven against),
      {"status": "tested", exit_code, passed, text_sha, code_index_sha, tests_sha, tail}.
    `driver` is the caller's statement of who wove the text: only `run_k` says "scripted"; the CLI and every other caller are "model"."""
    out = lg.emitted_output(run_dir)
    if out["status"] != "emitted":
        return out
    named = what_the_run_names(run_dir)
    if named is None:
        return {"status": "not_a_code_run"}
    if driver != SCRIPTED:
        if isolation_token is None:
            return {"status": "isolation_required", "driver": driver,
                    "reason": "the gates of the loom do not make a woven text safe to run; pass --isolation-confirmed <token> once the step runs inside an isolated environment"}
        if not isinstance(isolation_token, str) or not ISOLATION_TOKEN_RX.match(isolation_token):
            return {"status": "isolation_token_invalid", "reason": "3 to 64 characters of A-Z a-z 0-9 . _ : / @ = -, a label and not a secret"}
    res = run_pytest(named["fixture"], named["target"], out["text"], named["tests"], expect_index_sha=named["code_index_sha"])
    if "status" in res:
        return res
    text_sha = hashlib.sha256(out["text"].encode("utf-8")).hexdigest()
    if append_attest:
        append_outside_row(run_dir, "harness", "attest",
                           {"kind": "tests", "tests": named["tests"], "target": named["target"], "code_index_sha": res["code_index_sha"],
                            "tests_sha": res["tests_sha"], "text_sha": text_sha, "driver": driver,
                            "isolation_token": isolation_token if driver != SCRIPTED else None, "exit_code": res["exit_code"]})
    return dict(res, status="tested", text_sha=text_sha)


def run_k(k: str, variant: str, runs_dir, tasks: Optional[List[dict]] = None, run_id: Optional[str] = None, model: str = "scripted-weaver") -> dict:
    """Weave K<n> with the scripted weaver, emit, and test (driver "scripted").  Returns {task_id, run_dir, emit, tests}."""
    from verantyx.loom import scripted_code as sc
    tasks = tasks or load_tasks()
    task_id = "code/" + k.lower()
    srv = LoomServer(tasks, str(runs_dir))
    w = ScriptedWeaver(srv, task_id, model, run_id or ("%s-%s" % (k.lower(), variant)))
    w.begin()
    emit = sc.weave_k(w, k, variant)
    rd = srv.run_dir(w.run_id)
    tested = test_emitted_run(rd, driver=SCRIPTED) if emit.get("ok") else {"status": "no_output"}
    return {"task_id": task_id, "variant": variant, "run_dir": str(rd), "emit": emit, "tests": tested}


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="code_harness.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("table", help="the K1..K5 scripted runs and their tests")
    t.add_argument("runs_dir")
    r = sub.add_parser("test", help="the tests step of one existing run (a model's weave needs --isolation-confirmed)")
    r.add_argument("run_dir")
    r.add_argument("--isolation-confirmed", dest="isolation", default=None, metavar="TOKEN",
                   help="a label naming the isolation this process runs in (VM / container / Air); recorded in the attest row, not checked")
    a = ap.parse_args(argv)
    if a.cmd == "test":
        res = test_emitted_run(a.run_dir, driver="model", isolation_token=a.isolation)
        print(json.dumps({k: v for k, v in res.items() if k != "tail"}, sort_keys=True))
        return 0 if res["status"] == "tested" else 2
    for k, var in (("K1", "reference"), ("K2", "reference"), ("K3", "naive"), ("K3", "reference"), ("K3", "wrong_arity"),
                   ("K4", "naive"), ("K4", "reference"), ("K5", "reference")):
        res = run_k(k, var, a.runs_dir)
        e, tr = res["emit"], res["tests"]
        print(k, var, "emitted" if e.get("ok") else "refused:" + str(e.get("refusal")), repr(e.get("text")), "tests:", tr.get("exit_code", tr["status"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
