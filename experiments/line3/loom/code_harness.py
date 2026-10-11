"""The `tests` step of a CODE run (docs/LINE3_LOOM_DESIGN.md 5.2 "Tests are not a gate of `emit` ... run by the harness after emit ... an attest
row (record: exit code)"; tickets LOOM-code, LOOM-d2; L-LOOM-73, 78, 82, 85..).

It lives HERE, not in verantyx/loom, because it runs a process and the loom package imports none (T-LOOM-32).  What it does:

  0. THE GATES OF THE LOOM ARE NOT A SAFETY WALL (L-LOOM-72/78): they prove where each token came from and the order of the definitions.
     A woven text that passed every gate still runs with the rights of whoever runs this step.  So (LOOM-d2, L-LOOM-85) EVERY run of this
     step, scripted or not, goes through the OS: verantyx/loom/isolate.py runs the tests under macOS `sandbox-exec` with
     tools/loom_isolation_profile.sb (no network, reads only the fixture copy and the python runtime, writes only a scratch folder, no fork,
     no exec), `python -s -S -P`, a cleared environment, stdin = /dev/null, 60 s, rlimits and a memory watchdog.  THE GATE IS THE PROBE:
     before the tests run, a script run INSIDE the same sandbox proves that a connect() fails, a write outside fails, a read of $HOME/.ssh
     fails and a read of the fixture works.  A probe that does not pass => `isolation_failed`, NOTHING is run, no attest row.  The old
     `--isolation-confirmed <token>` is no longer a gate: it is an OVERRIDE that is honoured only when the probe is `unavailable` (no sandbox-exec,
     a nested sandbox, ...; a probe that RAN and FAILED is never overridden, L-LOOM-115); it is printed to stderr and recorded in the attest row (`isolation.mechanism = "python_fallback"`, `isolation.override = true`).
  1. `emitted_output(run_dir)`: the text of a run is its verified `emit` row and nothing else.  What was tested is read from THE RUN: target and
     tests from row 0, the fixture from meta.json (never from a caller's task row).
  2. copy the fixture into a fresh temporary folder, check the COPY against the run's `code_index_sha` and take `tests_sha` (the bytes of every
     .py file the index does not hold: tests/, test_*.py, conftest.py), append the emitted text to the target file (after two blank lines),
  3. run `pytest -q -p no:cacheprovider --rootdir <copy> -- <the run's test files>` in the sandbox with cwd = the copy,
  4. append ONE `attest` row {kind: "tests", tests, target, code_index_sha, tests_sha, text_sha, driver, isolation_token, isolation:
     {mechanism, profile_sha, boot_sha, python_flags, limits, network, probe: {status, properties}}, exit_code, outcome, pytest_result:
     {collected, failed, exitstatus} | null, expected_min} to the run's ledger (`append_outside_row`: the run is replayed first, so a run that
     does not verify gets no row).  No path, no time, no pytest output and no probe EVIDENCE enters the row (the evidence is machine-dependent:
     it goes to the unhashed sidecar `isolation_evidence.jsonl` next to the ledger, L-LOOM-117).  `outcome` is "passed" only when pytest's own
     counts, written by the `rec` plugin of the launcher, agree with the process: the file exists, exitstatus == exit_code == 0, failed == 0 and
     collected >= N, the static count of `def test_*` in the named test files; an exit code 0 without that is "tests_incomplete" (L-LOOM-116).
     Running the step twice appends a second row (LOOM-i decides what that means).

The argv is built here from the run's relative file names; the task bank carries no command line.  The step runs on THIS machine (the Air is
not needed for isolation); the fixture tests are pure Python.

    python experiments/line3/loom/code_harness.py table <runs_dir>                                  # the K1..K5 scripted table
    python experiments/line3/loom/code_harness.py test <run_dir> [--isolation-confirmed <token>]     # the tests step of one existing run
    python experiments/line3/loom/code_harness.py probe                                             # print the isolation probe (exit 0 = passed)
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Optional

from verantyx.loom import fixture as fx
from verantyx.loom import isolate as iso
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


def _run_fallback(work: Path, tmp: str, scratch: str, test_files: List[str], timeout: int, limits: iso.Limits) -> iso.Outcome:
    """The OVERRIDE path only (the probe cannot pass and the operator named an isolation of their own): the same launcher, rlimits and watchdog
    but no sandbox-exec; the network is cut only by replacing socket.socket in the process (weak, recorded as such)."""
    argv = iso.fallback_argv("pytest", sys.executable, ["-q", "-p", "no:cacheprovider", "--rootdir", str(work), "--"] + list(test_files),
                             [str(work)] + iso.site_dirs(), limits, result_path=os.path.join(scratch, iso.RESULT_NAME))
    return iso.run_job(argv, iso.clean_env(scratch), cwd=str(work), timeout=timeout, limits=limits)


_TEST_DEF_RX = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+test_\w*", re.M)


def count_test_functions(work: Path, test_files: List[str]) -> int:
    """N of L-LOOM-116: the STATIC count of `def test_*` in the named test files of the copy - module-level functions and the methods of
    top-level `Test*` classes (what pytest would collect by default).  A lower bound: parametrisation makes pytest collect more, dynamic
    generation is not counted.  A file that does not parse is counted by regex; a file that does not exist counts 0 (pytest will fail it anyway)."""
    n = 0
    for tf in test_files:
        try:
            src = (work / tf).read_text(encoding="utf-8")
        except (OSError, ValueError):
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            n += len(_TEST_DEF_RX.findall(src))
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                n += 1
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                n += sum(1 for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and m.name.startswith("test_"))
    return n


def read_pytest_result(scratch: Path) -> Optional[dict]:
    """{collected, failed, exitstatus} written by the `rec` plugin of the launcher (isolate._BOOT) into the scratch folder, or None when the
    file is absent or not exactly three non-negative ints (the job can write there, so the shape is checked, not trusted)."""
    try:
        d = json.loads((scratch / iso.RESULT_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict) or set(d) != {"collected", "failed", "exitstatus"}:
        return None
    if not all(type(v) is int and v >= 0 for v in d.values()):
        return None
    return {k: d[k] for k in ("collected", "failed", "exitstatus")}


def judge(exit_code: int, rec: Optional[dict], expected_min: int) -> str:
    """L-LOOM-116: "passed" only when pytest's own summary agrees with the process: the file exists, exitstatus == exit_code == 0, failed == 0 and
    collected >= max(N, 1).  An exit code other than 0 is "failed" whatever the file says.  Exit code 0 with a missing / contradicting / short
    file is "tests_incomplete": the process said yes and pytest did not witness it (a text that ended the process before the tests ran).
    This raises the bar, it does not prove the verdict: a text in the same process can still write the file itself (L-LOOM-92)."""
    if exit_code != 0:
        return "failed"
    if rec is None or rec["exitstatus"] != 0 or rec["failed"] != 0 or rec["collected"] < max(expected_min, 1):
        return "tests_incomplete"
    return "passed"


def run_pytest(fixture_root, target_file: str, text: str, test_files: List[str], timeout: int = TIMEOUT_S,
               expect_index_sha: Optional[str] = None, isolation_token: Optional[str] = None, limits: Optional[iso.Limits] = None) -> dict:
    """Insert `text` at the end of `target_file` in a copy of the fixture and run the test files there, INSIDE the OS sandbox (LOOM-d2).
    Returns {exit_code, passed, outcome, pytest_result, expected_min, tail, code_index_sha, tests_sha, isolation, isolation_evidence}; `outcome` is
    "passed" | "failed" | "tests_incomplete" (see judge) and `passed` is outcome == "passed"; exit_code is pytest's (0 pass, 1 fail, 2 interrupted, 4 usage,
    5 none collected), -9 for the 60 s timeout, -10 for the memory watchdog.  The COPY is checked first: when `expect_index_sha` is given and the
    copy's CODE index differs (the fixture changed between the run and now), nothing runs and the result is {status: "fixture_changed",
    expected, found}; an unreadable fixture is {status: "fixture_unreadable"}.  THE GATE: the isolation probe (same profile, same parameters, same
    launcher) must pass, else {status: "isolation_failed", probe} and nothing runs - unless the probe is `unavailable` (could not be run at all) AND
    `isolation_token` (the operator's override, L-LOOM-86) is given (a probe that RAN AND FAILED is never overridden, L-LOOM-115), in which case the run is made WITHOUT the OS wall (the same launcher, rlimits and watchdog, socket.socket replaced), the override is
    printed to stderr and the result's `isolation` says `python_fallback` / `override: true`.  A passing probe is never lowered by a token."""
    limits = limits or iso.Limits()
    tmp = os.path.realpath(tempfile.mkdtemp(prefix="loom_code_"))
    try:
        work = Path(tmp) / "fx"
        scratch = Path(tmp) / "scratch"
        scratch.mkdir()
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
        expected_min = count_test_functions(work, test_files)
        policy = iso.tests_step_policy(tmp, str(scratch))
        probe_file = next(iter(sorted(index.file_sha)), None)
        result = iso.probe(policy, str(work / probe_file), str(scratch), limits, readonly_write_targets=[str(work)]) if probe_file else \
            iso.ProbeResult("unavailable", profile_sha=iso.profile_sha(), reason="no_probe_file")
        if result.ok:
            out = iso.pytest_job(policy, str(work), str(scratch), test_files, timeout, limits)
            rc, tail_src = out.exit_code, out.output
            isolation = iso.isolation_row(policy, result, limits)
        elif isolation_token is not None and result.status == "unavailable":
            print("code_harness: ISOLATION OVERRIDE %s: the probe did not pass (%s); running WITHOUT the OS wall (python_fallback)" % (
                isolation_token, result.reason or ",".join(k for k, v in result.properties.items() if not v)), file=sys.stderr)
            out = _run_fallback(work, tmp, str(scratch), test_files, timeout, limits)
            rc, tail_src = out.exit_code, out.output
            isolation = {"mechanism": "python_fallback", "override": True, "profile_sha": result.profile_sha, "boot_sha": iso.BOOT_SHA,
                         "python_flags": list(iso.PY_FLAGS), "limits": limits.describe(), "network": "monkeypatched", "probe": result.to_row()}
        else:
            hint = ("--isolation-confirmed <token> overrides an UNAVAILABLE probe, recorded" if result.status == "unavailable" else
                    "the probe ran and a property does not hold: no token overrides that")
            return {"status": "isolation_failed", "probe": result.report(),
                    "reason": "the OS sandbox could not be proven (probe %s); nothing was run. %s" % (result.status, hint)}
        rec = read_pytest_result(scratch)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    outcome = judge(rc, rec, expected_min)
    return {"exit_code": rc, "passed": outcome == "passed", "outcome": outcome, "pytest_result": rec, "expected_min": expected_min,
            "tail": tail_src[-TAIL_CHARS:], "code_index_sha": index.sha, "tests_sha": tests_sha, "isolation": isolation,
            "isolation_evidence": result.evidence}


def probe_fixture(fixture_root=None, limits: Optional[iso.Limits] = None) -> iso.ProbeResult:
    """The isolation probe on a throw-away copy of the fixture, with the same policy the tests step uses."""
    fixture_root = fixture_root or (ROOT / "experiments/line3/loom/fixture_repo")
    tmp = os.path.realpath(tempfile.mkdtemp(prefix="loom_probe_"))
    try:
        work, scratch = Path(tmp) / "fx", Path(tmp) / "scratch"
        scratch.mkdir()
        shutil.copytree(str(fixture_root), str(work), ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
        index = fx.build_index(work, _plain_reader)
        return iso.probe(iso.tests_step_policy(tmp, str(scratch)), str(work / sorted(index.file_sha)[0]), str(scratch), limits or iso.Limits(),
                         readonly_write_targets=[str(work)])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


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


EVIDENCE_SIDECAR = "isolation_evidence.jsonl"


def write_evidence_sidecar(run_dir, row: dict, text_sha: str, res: dict) -> None:
    """L-LOOM-117: the raw errno evidence of the probe (machine-dependent: ENOENT here, EPERM there for a file that is absent) goes NOT into the
    hashed attest row but next to the ledger, in an unhashed, append-only sidecar, one line per attest row (`row_i` names the row)."""
    line = {"row_i": row.get("i"), "text_sha": text_sha, "profile_sha": res["isolation"].get("profile_sha"), "evidence": res.get("isolation_evidence") or {}}
    with open(os.path.join(str(run_dir), EVIDENCE_SIDECAR), "a", encoding="utf-8") as f:
        f.write(json.dumps(line, sort_keys=True, ensure_ascii=False) + "\n")


def test_emitted_run(run_dir, driver: str = "model", isolation_token: Optional[str] = None, append_attest: bool = True) -> dict:
    """The `tests` step for one run.  Returns {status, ...}:
      {"status": "no_output"} (the run emitted nothing), {"status": "run_not_verified", ...},
      {"status": "not_a_code_run"} (row 0 / meta.json name no fixture, target and tests),
      {"status": "isolation_token_invalid"},
      {"status": "isolation_failed", probe} (the OS sandbox could not be proven: NOTHING is run, no attest row),
      {"status": "fixture_changed" | "fixture_unreadable"} (the copy is not the fixture the run was woven against),
      {"status": "tested", exit_code, passed, text_sha, code_index_sha, tests_sha, isolation, tail}.
    `driver` is the caller's statement of who wove the text (recorded, no longer a gate: every driver is sandboxed, L-LOOM-85); `isolation_token`
    is the operator's OVERRIDE for a machine where the probe cannot pass, never a gate (L-LOOM-86)."""
    out = lg.emitted_output(run_dir)
    if out["status"] != "emitted":
        return out
    named = what_the_run_names(run_dir)
    if named is None:
        return {"status": "not_a_code_run"}
    if isolation_token is not None and (not isinstance(isolation_token, str) or not ISOLATION_TOKEN_RX.match(isolation_token)):
        return {"status": "isolation_token_invalid", "reason": "3 to 64 characters of A-Z a-z 0-9 . _ : / @ = -, a label and not a secret"}
    res = run_pytest(named["fixture"], named["target"], out["text"], named["tests"], expect_index_sha=named["code_index_sha"],
                     isolation_token=isolation_token)
    if "status" in res:
        return res
    text_sha = hashlib.sha256(out["text"].encode("utf-8")).hexdigest()
    if append_attest:
        row = append_outside_row(run_dir, "harness", "attest",
                                 {"kind": "tests", "tests": named["tests"], "target": named["target"], "code_index_sha": res["code_index_sha"],
                                  "tests_sha": res["tests_sha"], "text_sha": text_sha, "driver": driver, "isolation_token": isolation_token,
                                  "isolation": res["isolation"], "exit_code": res["exit_code"], "outcome": res["outcome"],
                                  "pytest_result": res["pytest_result"], "expected_min": res["expected_min"]})
        write_evidence_sidecar(run_dir, row, text_sha, res)
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
    r = sub.add_parser("test", help="the tests step of one existing run, inside the OS sandbox (refused when the probe does not pass)")
    r.add_argument("run_dir")
    r.add_argument("--isolation-confirmed", dest="isolation", default=None, metavar="TOKEN",
                   help="OVERRIDE, not a gate: honoured only when the sandbox probe cannot pass; a label naming the isolation you run in instead; "
                        "printed to stderr and recorded in the attest row")
    sub.add_parser("probe", help="run the isolation probe on a copy of the fixture and print it (exit 0 = passed, 2 = failed / unavailable)")
    a = ap.parse_args(argv)
    if a.cmd == "probe":
        res = probe_fixture()
        print(json.dumps(dict(res.report(), profile_sha=res.profile_sha, mechanism=res.mechanism), sort_keys=True))
        return 0 if res.ok else 2
    if a.cmd == "test":
        res = test_emitted_run(a.run_dir, driver="model", isolation_token=a.isolation)
        print(json.dumps({k: v for k, v in res.items() if k not in ("tail", "isolation_evidence")}, sort_keys=True))
        return 0 if res["status"] == "tested" else 2
    for k, var in (("K1", "reference"), ("K2", "reference"), ("K3", "naive"), ("K3", "reference"), ("K3", "wrong_arity"),
                   ("K4", "naive"), ("K4", "reference"), ("K5", "reference")):
        res = run_k(k, var, a.runs_dir)
        e, tr = res["emit"], res["tests"]
        print(k, var, "emitted" if e.get("ok") else "refused:" + str(e.get("refusal")), repr(e.get("text")), "tests:", tr.get("exit_code", tr["status"]),
              tr.get("outcome", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
