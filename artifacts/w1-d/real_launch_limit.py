"""Measure what a real (non dry-run) launch through the conduct entry does today.

The "agent" is a fake executable (not named codex or claude) that reads its stdin to EOF,
sleeps 2 seconds, then reports DONE.  Nothing named codex or claude is started.
Usage: PYTHONPATH=<tree> python real_launch_limit.py   (prints the measurement)
"""
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import verantyx
from verantyx.conductor_run import conduct_entry

ROOT = Path(verantyx.__file__).resolve().parents[1]
FRAME = ROOT / "docs" / "frames" / "examples" / "firmware_update_tool.md"

with tempfile.TemporaryDirectory(prefix="w1d-real-limit-") as tmp:
    tmp = Path(tmp)
    repo = tmp / "repo"
    repo.mkdir()
    for args in (["init", "-q"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    fake = tmp / "slow-agent.sh"
    fake.write_text('#!/bin/sh\ncat > /dev/null\nsleep 2\nprintf \'%s\\n\' \'{"type":"DONE"}\'\n')
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    print("verantyx from:", Path(verantyx.__file__).resolve())
    print("frame:", FRAME.relative_to(ROOT), "(model/effort from the frame's [agent_settings])")
    started = time.monotonic()
    outcome = conduct_entry(FRAME, repo, "codex", dry_run=False, codex_bin=str(fake))
    elapsed = time.monotonic() - started
    print(f"elapsed_seconds={elapsed:.2f}")
    print("verdict:", outcome.verdict, "exit_code:", outcome.exit_code)
    print("blocking:", json.dumps(outcome.blocking, ensure_ascii=False)[:400] if outcome.blocking else None)
    print("result:", outcome.result)
    ledger = [json.loads(line) for line in Path(outcome.ledger).read_text().splitlines()]
    print("ledger_row_types:", [row["type"] for row in ledger])
    planned = [row for row in ledger if row["type"] == "LAUNCH_PLANNED"]
    print("launch_row: dry_run=%s cwd_created=%s argv=%s" % (planned[0]["dry_run"], planned[0]["cwd_created"], planned[0]["argv"][:2] + ["..."] + planned[0]["argv"][-3:]))
    runtime_log = next((tmp / "repo" / ".verantyx-conduct" / "runs").glob("*/runtime/runtime.jsonl"))
    rows = [json.loads(line) for line in runtime_log.read_text().splitlines()]
    print("runtime_event_types:", [row["type"] for row in rows])
    print("ConductorRun MAX_RUN_SECONDS (upper bound of the whole run):", __import__("verantyx.conductor_run", fromlist=["x"]).MAX_RUN_SECONDS)
