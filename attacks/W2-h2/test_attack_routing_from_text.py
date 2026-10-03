"""Executable attacks against W2-h2's public ``vera route`` entry."""
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
TASK = {"role": "review", "kind": "review", "size": "medium"}


def route(explanation):
    env = dict(os.environ)
    env.update({"PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"})
    proc = subprocess.run(
        [sys.executable, "-m", "verantyx.cli", "route", "--explanation", str(HERE / explanation),
         "--task", json.dumps(TASK)],
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_attack_01_common_noun_is_not_a_declared_agent_name():
    out = route("attack_01_common_noun.md")
    assert (out["decision"], out["agent"]) != ("route", "team"), out


def test_attack_02_addendum_does_not_silently_replace_an_existing_assignment():
    out = route("attack_02_addendum.md")
    assert (out["decision"], out["agent"]) != ("route", "Luna"), out
