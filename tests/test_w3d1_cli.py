"""W3-d1 (5): `python -m verantyx.cli realize` (a subprocess, the way a user runs it). r9 is read only; without it the placement tests skip."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "w3-d1"
R9 = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2"


def _plain_tokens():
    """A canonical token line of a cross read WITHOUT a placement (so the tests that do not need r9 can run without it)."""
    from verantyx import cross_tokens, event_cross, semantic_read

    got = event_cross.build_crosses(semantic_read.read("太郎が花子に本を渡した。", "ja", placement=None), event_cross.StubLookup())
    assert got.status == "CROSSED" and len(got.crosses) == 1
    return cross_tokens.cross_to_tokens(got.crosses[0])


TOKENS = _plain_tokens()


def run(*args, env_extra=None, stdin=None):
    env = {k: v for k, v in os.environ.items() if k not in ("VERA_PLACEMENT", "VERA_REALIZE_FORMS")}
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(env_extra or {})
    done = subprocess.run([sys.executable, "-m", "verantyx.cli", "realize", *args], input=stdin, capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120)
    return done


def pool_line(index=0):
    path = ART / "t2_pool.jsonl"
    if not path.exists():
        pytest.skip("ENV_MISSING[artifacts/w3-d1/t2_pool.jsonl]")
    return json.loads(path.read_text(encoding="utf-8").splitlines()[index])


def test_help_lists_the_forms_option():
    done = run("--help")
    assert done.returncode == 0 and "--forms" in done.stdout and "--placement" in done.stdout


def test_a_token_line_without_a_placement_is_a_typed_answer_not_a_crash():
    done = run(TOKENS)
    body = json.loads(done.stdout)
    assert done.returncode == 0 and body["schema"] == "verantyx.cross_tokens/1" and body["status"] in ("REALIZED", "REFUSED", "ABSTAINED")


def test_a_bad_token_line_is_rejected_with_its_type():
    body = json.loads(run("not a cross").stdout)
    assert body["status"] == "TOKEN_REJECTED"


@pytest.mark.skipif(not Path(R9).exists(), reason="ENV_MISSING[coarse placement r9/run2]")
def test_a_typed_cross_is_realized_with_the_placement():
    row = pool_line(0)
    done = run(row["tokens"], "--placement", R9)
    body = json.loads(done.stdout)
    assert done.returncode == 0 and body["status"] == "REALIZED" and body["cell_key"] == row["cell_key"]
    assert body["checks"]["reread"]["passed"] and body["checks"]["topic_attempts"][-1]["passed"] is True
    again = run("-", "--placement", R9, stdin=row["tokens"] + "\n")                 # stdin is the default input
    assert json.loads(again.stdout)["text"] == body["text"]


@pytest.mark.skipif(not Path(R9).exists(), reason="ENV_MISSING[coarse placement r9/run2]")
@pytest.mark.parametrize("name", ["t3_layer_override_particle.json", "t3_layer_override_style.json"])
def test_an_overriding_table_is_refused_with_exit_code_2_by_the_option_and_by_the_variable(name):
    row = pool_line(0)
    by_option = run(row["tokens"], "--placement", R9, "--forms", str(ART / name))
    by_variable = run(row["tokens"], "--placement", R9, env_extra={"VERA_REALIZE_FORMS": str(ART / name)})
    for done in (by_option, by_variable):
        body = json.loads(done.stdout)
        assert done.returncode == 2 and body["status"] == "REFUSED" and body["reason"] == "FORMS_OVERRIDE_REFUSED"


def test_a_missing_table_is_forms_not_found_with_exit_code_2(tmp_path):
    done = run(TOKENS, "--forms", str(tmp_path / "missing.json"))
    assert done.returncode == 2 and json.loads(done.stdout)["reason"] == "FORMS_NOT_FOUND"


@pytest.mark.skipif(not Path(R9).exists(), reason="ENV_MISSING[coarse placement r9/run2]")
def test_a_table_that_only_adds_is_accepted():
    row = pool_line(0)
    done = run(row["tokens"], "--placement", R9, "--forms", str(ART / "t3_layer_add_style.json"))
    assert done.returncode == 0 and json.loads(done.stdout)["status"] == "REALIZED"
