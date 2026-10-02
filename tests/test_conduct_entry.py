"""Acceptance tests for the conduct entry: E1 (fake start), E2 (dry-run codex/claude),
E3 (typed refusals), the ledger, JSONL frames and the settings rules."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from test_conduct_entry_support import *  # noqa: F401,F403  (fixtures + helpers)
from test_conduct_entry_support import (EXAMPLE_FRAMES, MINIMAL_FRAME, ROOT, VERA_FRAME, compiled_records,
                                        conduct_argv, read_ledger, rows_of, run_cli)


def kinds_of(records):
    counts = {}
    for record in records:
        counts[record["kind"]] = counts.get(record["kind"], 0) + 1
    return dict(sorted(counts.items()))


# ----------------------------------------------------------------- E1
def test_e1_fake_adapter_reaches_start_and_the_ledger_shows_it(git_repo, tmp_path, capsys):
    code, out, err = run_cli(conduct_argv(VERA_FRAME, git_repo, "fake"), capsys)
    # The Vera frame keeps five human-judged criteria, so the run is honestly incomplete.
    assert (code, out["verdict"]) == (1, "RUN_INCOMPLETE")
    assert out["refusal"] is None and err == ""
    rows = read_ledger(out["ledger"])
    assert Path(out["ledger"]) == git_repo / ".verantyx-conduct" / "ledger.jsonl"
    assert [row["type"] for row in rows] == [
        "CONDUCT_INVOKED", "FRAME_READ", "FRAME_COMPILED", "AGENT_START_CALLED", "AGENT_START_RETURNED", "RUN_FINISHED"]
    assert [row["seq"] for row in rows] == list(range(len(rows)))
    assert {row["run_id"] for row in rows} == {out["run_id"]}
    called, returned = rows_of(rows, "AGENT_START_CALLED")[0], rows_of(rows, "AGENT_START_RETURNED")[0]
    assert returned["handle_type"] == "FakeHandle" and returned["adapter"] == "fake"
    assert called["brief_sha256"] == returned["brief_sha256"] and called["task_id"] == "Vera"
    # FRAME_COMPILED agrees with an independent compilation of the same file.
    expected = compiled_records(VERA_FRAME, tmp_path)
    compiled = rows_of(rows, "FRAME_COMPILED")[0]
    assert compiled["record_count"] == len(expected)
    assert compiled["kinds"] == kinds_of(expected)
    assert compiled["human_criteria"] == 5 and compiled["machine_criteria"] == 1
    # FRAME_READ describes the file that was read.
    read = rows_of(rows, "FRAME_READ")[0]
    raw = VERA_FRAME.read_bytes()
    assert read["sha256"] == hashlib.sha256(raw).hexdigest() and read["bytes"] == len(raw)
    assert read["format"] == "markdown"
    lines = raw.decode().splitlines()
    assert read["blank_lines"] == sum(1 for x in lines if not x.strip())
    assert read["comment_lines"] == sum(1 for x in lines if x.strip().startswith("#"))
    finished = rows_of(rows, "RUN_FINISHED")[0]
    assert finished["complete"] is False and finished["blocking_kind"] == "acceptance"


def test_e1_through_a_real_subprocess_with_an_explicit_pythonpath(git_repo):
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run([sys.executable, "-m", "verantyx.cli", "conduct", "--frame", str(VERA_FRAME),
                           "--repo", str(git_repo), "--adapter", "fake"],
                          capture_output=True, text=True, env=env, cwd=str(git_repo), timeout=120)
    assert proc.returncode == 1, proc.stderr
    out = json.loads(proc.stdout)
    assert out["verdict"] == "RUN_INCOMPLETE"
    assert len(rows_of(read_ledger(out["ledger"]), "AGENT_START_RETURNED")) == 1


def test_tools_run_project_is_a_thin_wrapper_that_does_not_depend_on_pythonpath(git_repo):
    # Without PYTHONPATH an unrelated installed verantyx would be imported and would fail
    # on the "conduct" sub-command; a JSON refusal proves this tree's CLI answered.
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, str(ROOT / "tools" / "run_project.py"), "--frame", str(git_repo / "nope.md"),
                           "--repo", str(git_repo), "--adapter", "fake"],
                          capture_output=True, text=True, env=env, cwd=str(git_repo), timeout=120)
    assert proc.returncode == 2, proc.stderr
    assert json.loads(proc.stdout)["refusal"]["reason"] == "FRAME_NOT_FOUND"


def test_a_scripted_agent_with_a_command_runner_can_complete_the_run(git_repo, tmp_path):
    from verantyx.agent_adapter import FakeAdapter
    from verantyx.conductor_run import conduct_entry

    frame = tmp_path / "small.md"
    frame.write_text(MINIMAL_FRAME + "[write_allowlist]\nW1: src\n", encoding="utf-8")
    seen = []

    def runner(target):
        seen.append(target)
        return 0

    outcome = conduct_entry(frame, git_repo, FakeAdapter([{"type": "DONE"}]), command_runner=runner)
    assert (outcome.verdict, outcome.exit_code) == ("RUN_COMPLETE", 0)
    assert seen and seen[0]["expected_exit"] == 0
    # Without a runner (what the CLI does) the same frame cannot be called complete.
    again = conduct_entry(frame, git_repo, FakeAdapter([{"type": "DONE"}]))
    assert (again.verdict, again.exit_code) == ("RUN_INCOMPLETE", 1)
    assert "no injected command runner" in again.blocking["reason"]


# ----------------------------------------------------------------- E2
def _plan_of(out):
    """The single LAUNCH_PLANNED row of the run that produced ``out`` (the ledger spans runs)."""
    plans = [row for row in rows_of(read_ledger(out["ledger"]), "LAUNCH_PLANNED") if row["run_id"] == out["run_id"]]
    assert len(plans) == 1
    return plans[0]


def test_e2_codex_dry_run_records_the_exact_argument_array(git_repo, capsys, no_agent_process):
    code, out, err = run_cli(conduct_argv(VERA_FRAME, git_repo, "codex", "--dry-run",
                                          "--model", "gpt-6-luna", "--effort", "high"), capsys)
    assert (code, out["verdict"]) == (0, "DRY_RUN_PLANNED")
    plan = _plan_of(out)
    argv = plan["argv"]
    assert isinstance(argv, list) and all(isinstance(item, str) for item in argv)
    last_message = argv[12]
    assert argv == ["codex", "exec", "--ignore-user-config", "-m", "gpt-6-luna",
                    "-c", 'model_reasoning_effort="high"', "-s", "workspace-write",
                    "-C", plan["cwd"], "-o", last_message, "-"]
    assert last_message.endswith("last_message.txt")
    # The prompt is not in the array; stdin is a file whose content is the prompt.
    assert not any(plan["prompt"][:40] in item for item in argv)
    assert plan["stdin"]["mode"] == "file"
    stdin_file = Path(plan["stdin"]["path"])
    assert stdin_file.read_text(encoding="utf-8") == plan["prompt"]
    assert hashlib.sha256(plan["prompt"].encode()).hexdigest() == plan["stdin"]["sha256"]
    assert plan["stdin"]["chars"] == len(plan["prompt"])
    # Allowlist, sources and effective concurrency are in the ledger.
    assert plan["allowlist"] == ["docs", "tests", "tools", "verantyx"]
    assert "Write allowlist (enforced after exit): docs, tests, tools, verantyx." in plan["prompt"]
    assert plan["model"] == {"value": "gpt-6-luna", "source": "cli", "overridden_frame_value": None}
    assert plan["effort"]["source"] == "cli"
    assert plan["effective_concurrency"] == 1 and plan["dry_run"] is True
    assert plan["task_id"] == "Vera" and plan["output_path"] == last_message
    # A dry run creates no worktree and no process.
    assert not Path(plan["cwd"]).exists() and plan["cwd_created"] is False
    worktrees = subprocess.run(["git", "-C", str(git_repo), "worktree", "list"], capture_output=True, text=True).stdout
    assert len(worktrees.strip().splitlines()) == 1


def test_e2_claude_dry_run_records_the_exact_argument_array(git_repo, capsys, no_agent_process):
    code, out, err = run_cli(conduct_argv(VERA_FRAME, git_repo, "claude", "--dry-run",
                                          "--model", "claude-sonnet-5-5", "--effort", "high"), capsys)
    assert (code, out["verdict"]) == (0, "DRY_RUN_PLANNED")
    plan = _plan_of(out)
    assert plan["argv"] == ["claude", "-p", "--model", "claude-sonnet-5-5", "--effort", "high"]
    assert plan["stdin"]["mode"] == "file" and plan["output_path"] is None
    assert Path(plan["stdin"]["path"]).read_text(encoding="utf-8") == plan["prompt"]
    assert plan["cwd"].endswith("/worktree") and not Path(plan["cwd"]).exists()
    assert plan["backend"] == "claude-print"


def test_e2_executables_come_from_arguments_not_from_a_fixed_name(git_repo, capsys, no_agent_process):
    code, out, _ = run_cli(conduct_argv(VERA_FRAME, git_repo, "codex", "--dry-run", "--model", "m1", "--effort", "low",
                                        "--codex-bin", "/opt/x/codex-7"), capsys)
    assert code == 0 and _plan_of(out)["argv"][0] == "/opt/x/codex-7"
    code, out, _ = run_cli(conduct_argv(VERA_FRAME, git_repo, "claude", "--dry-run", "--model", "m2", "--effort", "low",
                                        "--claude-bin", "/opt/x/claude-9"), capsys)
    assert code == 0 and _plan_of(out)["argv"][0] == "/opt/x/claude-9"


def test_e2_without_model_or_effort_the_entry_refuses_and_names_both_ways_to_set_them(git_repo, capsys, no_agent_process):
    code, out, err = run_cli(conduct_argv(VERA_FRAME, git_repo, "codex", "--dry-run"), capsys)
    assert (code, out["verdict"], out["refusal"]["reason"]) == (2, "REFUSED", "AGENT_SETTING_MISSING")
    missing = out["refusal"]["missing"]
    assert "--model" in missing and "codex_model" in missing and "--effort" in missing and "codex_effort" in missing
    assert not rows_of(read_ledger(out["ledger"]), "LAUNCH_PLANNED")


def test_settings_come_from_the_frame_when_the_command_line_is_silent_and_the_cli_wins_otherwise(git_repo, capsys, no_agent_process):
    frame = EXAMPLE_FRAMES[0].parent / "library_catalog_search.md"
    code, out, _ = run_cli(conduct_argv(frame, git_repo, "codex", "--dry-run"), capsys)
    assert code == 0
    plan = _plan_of(out)
    assert plan["model"] == {"value": "gpt-6-luna", "source": "frame", "overridden_frame_value": None}
    assert plan["effort"]["value"] == "high" and plan["effort"]["source"] == "frame"
    assert plan["max_concurrency"]["value"] == "2" and plan["max_concurrency"]["source"] == "frame"
    assert plan["effective_concurrency"] == 1
    code, out, _ = run_cli(conduct_argv(frame, git_repo, "claude", "--dry-run", "--model", "other-model", "--max-concurrency", "60"), capsys)
    plan = _plan_of(out)
    assert code == 0
    assert plan["model"] == {"value": "other-model", "source": "cli", "overridden_frame_value": "claude-sonnet-5-5"}
    assert plan["effort"]["source"] == "frame"
    # 60 is accepted as an upper bound; the run is still one agent at a time.
    assert plan["max_concurrency"] == {"value": "60", "source": "cli", "overridden_frame_value": "2"}
    assert plan["effective_concurrency"] == 1


@pytest.mark.parametrize("flags", [
    ["--model", "gpt 6", "--effort", "high"],
    ["--model=-x", "--effort", "high"],
    ["--model", "gpt-6-luna", "--effort", 'high"; touch pwned; "'],
    ["--model", "gpt-6-luna", "--effort", "HIGH"],
    ["--model", "gpt-6-luna", "--effort", "high", "--max-concurrency", "0"],
    ["--model", "m" * 129, "--effort", "high"],
])
def test_unsafe_or_malformed_settings_are_refused_before_anything_is_planned(git_repo, capsys, no_agent_process, flags):
    code, out, _ = run_cli(conduct_argv(VERA_FRAME, git_repo, "codex", "--dry-run", *flags), capsys)
    assert (code, out["refusal"]["reason"]) == (2, "AGENT_SETTING_INVALID")
    assert out["refusal"]["missing"] and not rows_of(read_ledger(out["ledger"]), "LAUNCH_PLANNED")
    assert not (git_repo / "pwned").exists()


def test_dry_run_with_fake_is_an_ordinary_fake_run(git_repo, capsys):
    code, out, _ = run_cli(conduct_argv(VERA_FRAME, git_repo, "fake", "--dry-run"), capsys)
    assert (code, out["verdict"]) == (1, "RUN_INCOMPLETE")


# ----------------------------------------------------------------- E3
def _refusal_cases(tmp_path):
    broken = tmp_path / "broken.md"
    broken.write_text("[goal]\nproject: X\n", encoding="utf-8")
    plain = tmp_path / "plain.txt"
    plain.write_text("hello\nworld\n", encoding="utf-8")
    text = VERA_FRAME.read_text(encoding="utf-8")
    no_allow = tmp_path / "no_allow.md"
    no_allow.write_text(text.rsplit("\n[write_allowlist]", 1)[0], encoding="utf-8")
    human_only = tmp_path / "human_only.md"
    human_only.write_text("\n".join(x for x in text.splitlines() if not x.startswith("C6:")) + "\n", encoding="utf-8")
    empty_allow = tmp_path / "empty_allow.md"
    empty_allow.write_text(MINIMAL_FRAME + "[write_allowlist]\nnone: none\n", encoding="utf-8")
    empty = tmp_path / "empty.md"
    empty.write_text("", encoding="utf-8")
    binary = tmp_path / "binary.md"
    binary.write_bytes(b"[goal]\n\xff\xfe\n")
    bad_jsonl = tmp_path / "bad.jsonl"
    bad_jsonl.write_text('{"op":"write","record":{"id":"a","kind":"DECISION","slots":{"subject":"x","choice":"y"}}}\n{oops\n', encoding="utf-8")
    return {
        "WRITE_ALLOWLIST_MISSING": no_allow, "MACHINE_ACCEPTANCE_MISSING": human_only,
        "FRAME_PARSE_ERROR": broken, "FRAME_FORMAT_UNKNOWN": plain, "FRAME_NOT_FOUND": tmp_path / "missing.md",
        "WRITE_ALLOWLIST_EMPTY": empty_allow, "FRAME_FORMAT_UNKNOWN#empty": empty,
        "FRAME_UNREADABLE": binary, "FRAME_UNREADABLE#dir": tmp_path, "FRAME_JSONL_INVALID": bad_jsonl,
    }


def test_e3_each_kind_of_bad_frame_gets_its_own_typed_refusal_with_what_to_add(git_repo, tmp_path, capsys):
    cases = _refusal_cases(tmp_path)
    seen = {}
    for label, frame in cases.items():
        expected = label.split("#")[0]
        code, out, err = run_cli(conduct_argv(frame, git_repo, "fake"), capsys)
        assert (code, out["verdict"]) == (2, "REFUSED"), label
        refusal = out["refusal"]
        assert refusal["reason"] == expected, (label, refusal)
        assert refusal["missing"].strip() and len(refusal["missing"]) > 30, (label, refusal)
        assert "Traceback" not in err and err == ""
        # the refusal is also in the ledger, with the same reason
        assert rows_of(read_ledger(out["ledger"]), "REFUSED")[-1]["reason"] == expected
        assert not rows_of(read_ledger(out["ledger"]), "AGENT_START_CALLED")
        seen[label] = refusal["reason"]
    assert len(set(seen.values())) == 8  # eight distinct types; none collapses into another


def test_e3_refusals_say_where_and_what(git_repo, tmp_path, capsys):
    cases = _refusal_cases(tmp_path)
    _, out, _ = run_cli(conduct_argv(cases["WRITE_ALLOWLIST_MISSING"], git_repo, "fake"), capsys)
    assert "[write_allowlist]" in out["refusal"]["missing"]
    _, out, _ = run_cli(conduct_argv(cases["MACHINE_ACCEPTANCE_MISSING"], git_repo, "fake"), capsys)
    assert "command_exit" in out["refusal"]["missing"] and "all 5" in out["refusal"]["missing"]
    _, out, _ = run_cli(conduct_argv(cases["FRAME_PARSE_ERROR"], git_repo, "fake"), capsys)
    assert out["refusal"]["line"] == 3 and "[phases]" in out["refusal"]["missing"]
    _, out, _ = run_cli(conduct_argv(cases["FRAME_JSONL_INVALID"], git_repo, "fake"), capsys)
    assert out["refusal"]["line"] == 2
    _, out, _ = run_cli(conduct_argv(cases["WRITE_ALLOWLIST_EMPTY"], git_repo, "fake"), capsys)
    assert "none: none" in out["refusal"]["missing"]


def test_when_both_the_allowlist_and_machine_criteria_are_missing_both_are_named(git_repo, tmp_path, capsys):
    text = VERA_FRAME.read_text(encoding="utf-8").rsplit("\n[write_allowlist]", 1)[0]
    frame = tmp_path / "neither.md"
    frame.write_text("\n".join(x for x in text.splitlines() if not x.startswith("C6:")) + "\n", encoding="utf-8")
    _, out, _ = run_cli(conduct_argv(frame, git_repo, "fake"), capsys)
    assert out["refusal"]["reason"] == "WRITE_ALLOWLIST_MISSING"
    assert "[write_allowlist]" in out["refusal"]["missing"] and "command_exit" in out["refusal"]["missing"]
    assert "MACHINE_ACCEPTANCE_MISSING" in out["refusal"]["detail"]


def test_a_frame_with_no_completion_criterion_at_all_is_a_distinct_wording(git_repo, tmp_path, capsys):
    frame = tmp_path / "nocrit.md"
    frame.write_text(MINIMAL_FRAME.replace('C1: The check passes | {"kind":"command_exit","command":["true"],"expected_exit":0}',
                                           "none: none") + "[write_allowlist]\nW1: src\n", encoding="utf-8")
    _, out, _ = run_cli(conduct_argv(frame, git_repo, "fake"), capsys)
    assert out["refusal"]["reason"] == "MACHINE_ACCEPTANCE_MISSING"
    assert "no completion criterion" in out["refusal"]["missing"]


def test_frame_that_parses_but_cannot_become_typed_records_is_a_compile_refusal_with_its_line(git_repo, tmp_path, capsys):
    frame = tmp_path / "verb.md"
    frame.write_text((MINIMAL_FRAME + "[write_allowlist]\nW1: src\n").replace(
        "D1: goal authority => The human decides", "D1: goal authority => 人が決める。確認する"), encoding="utf-8")
    code, out, err = run_cli(conduct_argv(frame, git_repo, "fake"), capsys)
    assert (code, out["refusal"]["reason"]) == (2, "FRAME_COMPILE_ERROR")
    assert out["refusal"]["line"] and err == ""


def test_repo_problems_are_typed_and_not_confused_with_frame_problems(tmp_path, git_repo, capsys, no_agent_process):
    code, out, _ = run_cli(conduct_argv(VERA_FRAME, tmp_path / "no-such-dir", "fake"), capsys)
    assert (code, out["refusal"]["reason"], out["ledger"]) == (2, "REPO_NOT_FOUND", None)
    # naming a state dir still lets the refusal be written down
    state = tmp_path / "state"
    code, out, _ = run_cli(conduct_argv(VERA_FRAME, tmp_path / "no-such-dir", "fake", "--state-dir", str(state)), capsys)
    assert out["refusal"]["reason"] == "REPO_NOT_FOUND" and rows_of(read_ledger(out["ledger"]), "REFUSED")
    plain_dir = tmp_path / "not-git"
    plain_dir.mkdir()
    code, out, _ = run_cli(conduct_argv(VERA_FRAME, plain_dir, "codex", "--dry-run", "--model", "m", "--effort", "low"), capsys)
    assert (code, out["refusal"]["reason"]) == (2, "REPO_NOT_GIT")
    assert "git init" in out["refusal"]["missing"]
    # a fake run does not need git at all
    code, out, _ = run_cli(conduct_argv(VERA_FRAME, plain_dir, "fake"), capsys)
    assert code == 1


def test_a_repository_without_a_commit_is_refused_for_a_real_agent(tmp_path, capsys, no_agent_process):
    repo = tmp_path / "fresh"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    code, out, _ = run_cli(conduct_argv(VERA_FRAME, repo, "claude", "--dry-run", "--model", "m", "--effort", "low"), capsys)
    assert (code, out["refusal"]["reason"]) == (2, "REPO_NOT_GIT") and "commit" in out["refusal"]["missing"]


def test_an_unexpected_exception_is_an_internal_error_with_only_its_type(git_repo, capsys, monkeypatch):
    from verantyx import project_frame

    def boom(*a, **k):
        raise RuntimeError("secret details /home/x")

    monkeypatch.setattr(project_frame, "compile_frame", boom)
    code, out, err = run_cli(conduct_argv(VERA_FRAME, git_repo, "fake"), capsys)
    assert (code, out["verdict"], out["refusal"]["reason"]) == (3, "REFUSED", "INTERNAL_ERROR")
    assert out["refusal"]["detail"] == "RuntimeError" and "secret" not in json.dumps(out) and err == ""
    assert rows_of(read_ledger(out["ledger"]), "REFUSED")[-1]["reason"] == "INTERNAL_ERROR"


def test_a_corrupt_ledger_is_never_overwritten(git_repo, capsys):
    state = git_repo / ".verantyx-conduct"
    state.mkdir()
    ledger = state / "ledger.jsonl"
    ledger.write_text('{"schema":"conduct-ledger-v1","seq":5,"run_id":"x","type":"CONDUCT_INVOKED"}\n', encoding="utf-8")
    before = ledger.read_bytes()
    code, out, _ = run_cli(conduct_argv(VERA_FRAME, git_repo, "fake"), capsys)
    assert (code, out["refusal"]["reason"]) == (2, "LEDGER_UNUSABLE")
    assert ledger.read_bytes() == before


def test_a_state_directory_that_cannot_hold_a_ledger_is_a_typed_refusal_not_an_exception(git_repo, tmp_path, capsys):
    blocker = tmp_path / "a-file"
    blocker.write_text("x")
    code, out, err = run_cli(conduct_argv(VERA_FRAME, git_repo, "fake", "--state-dir", str(blocker / "sub")), capsys)
    assert (code, out["refusal"]["reason"]) == (2, "LEDGER_UNUSABLE") and err == ""
    assert out["refusal"]["missing"] and "Traceback" not in json.dumps(out)


def test_an_unknown_adapter_name_from_python_is_a_caller_error_not_a_silent_fake(git_repo):
    from verantyx.conductor_run import conduct_entry

    with pytest.raises(ValueError):
        conduct_entry(VERA_FRAME, git_repo, "gemini")


def test_no_launch_planned_is_its_own_refusal_when_the_order_gate_stops_the_run(git_repo, tmp_path, capsys, no_agent_process):
    # The cause of tools/demo_conduct.py stopping: an ORDER predecessor that is not a GOAL task.
    from verantyx.conductor import ProjectFrame
    from verantyx.memory_frame import Memory
    from verantyx.project_frame import compile_frame, parse_frame

    spec = parse_frame(VERA_FRAME.read_text(encoding="utf-8"), source="vera")
    memory_path = tmp_path / "ordered.jsonl"
    compilation = compile_frame(spec, memory_path)
    authority = next(r for r in compilation.records if r["slots"].get("subject") == "goal authority")
    ProjectFrame(compilation.memory).add_order("foundation", "Vera", authority["id"])
    code, out, _ = run_cli(conduct_argv(memory_path, git_repo, "codex", "--dry-run", "--model", "m", "--effort", "low"), capsys)
    assert (code, out["verdict"], out["refusal"]["reason"]) == (2, "REFUSED", "NO_LAUNCH_PLANNED")
    assert "order_predecessor" in out["refusal"]["detail"]
    code, out, _ = run_cli(conduct_argv(memory_path, git_repo, "fake"), capsys)
    assert (code, out["verdict"], out["blocking"]["kind"]) == (1, "RUN_INCOMPLETE", "order_predecessor")
    assert not rows_of(read_ledger(out["ledger"]), "AGENT_START_CALLED")


# ----------------------------------------------------------------- format detection and JSONL
def test_format_is_decided_by_content_not_by_extension(git_repo, tmp_path, capsys):
    text = VERA_FRAME.read_text(encoding="utf-8")
    for name in ("frame.jsonl", "frame.txt", "frame"):
        path = tmp_path / name
        path.write_text(text, encoding="utf-8")
        code, out, _ = run_cli(conduct_argv(path, git_repo, "fake"), capsys)
        assert code == 1, name
        assert rows_of(read_ledger(out["ledger"]), "FRAME_READ")[-1]["format"] == "markdown"
    # a BOM does not hide the header
    bom = tmp_path / "bom.md"
    bom.write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    assert run_cli(conduct_argv(bom, git_repo, "fake"), capsys)[0] == 1


def _jsonl_from(frame_path, tmp_path, name="frame.jsonl"):
    from verantyx.project_frame import compile_frame, parse_frame

    path = tmp_path / name
    compile_frame(parse_frame(Path(frame_path).read_text(encoding="utf-8"), source="s"), path)
    return path


def test_a_jsonl_frame_is_copied_not_written_to_and_reads_its_allowlist_from_witnesses(git_repo, tmp_path, capsys, no_agent_process):
    jsonl = _jsonl_from(VERA_FRAME, tmp_path)
    digest = hashlib.sha256(jsonl.read_bytes()).hexdigest()
    code, out, _ = run_cli(conduct_argv(jsonl, git_repo, "fake"), capsys)
    assert code == 1
    assert hashlib.sha256(jsonl.read_bytes()).hexdigest() == digest  # the input file is untouched
    rows = read_ledger(out["ledger"])
    read = rows_of(rows, "FRAME_READ")[0]
    assert read["format"] == "jsonl" and read["sha256"] == digest
    compiled = rows_of(rows, "FRAME_COMPILED")[0]
    expected = compiled_records(VERA_FRAME, tmp_path)
    assert compiled["record_count"] == len(expected) and compiled["kinds"] == kinds_of(expected)
    assert compiled["write_allowlist"] == ["docs", "tests", "tools", "verantyx"]
    copy = Path(compiled["memory_path"])
    assert copy != jsonl and copy.read_bytes() != b"" and copy.parent.parent.name == "runs"
    code, out, _ = run_cli(conduct_argv(jsonl, git_repo, "codex", "--dry-run", "--model", "m", "--effort", "low"), capsys)
    assert code == 0 and _plan_of(out)["allowlist"] == ["docs", "tests", "tools", "verantyx"]


def test_a_jsonl_frame_without_allowlist_or_machine_criteria_is_refused_like_markdown(git_repo, tmp_path, capsys):
    text = VERA_FRAME.read_text(encoding="utf-8")
    no_allow = tmp_path / "na.md"
    no_allow.write_text(text.rsplit("\n[write_allowlist]", 1)[0], encoding="utf-8")
    code, out, _ = run_cli(conduct_argv(_jsonl_from(no_allow, tmp_path, "na.jsonl"), git_repo, "fake"), capsys)
    assert out["refusal"]["reason"] == "WRITE_ALLOWLIST_MISSING"
    human = tmp_path / "ho.md"
    human.write_text("\n".join(x for x in text.splitlines() if not x.startswith("C6:")) + "\n", encoding="utf-8")
    code, out, _ = run_cli(conduct_argv(_jsonl_from(human, tmp_path, "ho.jsonl"), git_repo, "fake"), capsys)
    assert out["refusal"]["reason"] == "MACHINE_ACCEPTANCE_MISSING"


@pytest.mark.parametrize("mutate,expected_line", [
    (lambda rows: rows[:3] + ["{not json"] + rows[3:], 4),
    (lambda rows: rows[:1] + ['{"op":"explode"}'] + rows[1:], 2),
    (lambda rows: rows[:1] + [rows[0]] + rows[1:], 2),  # duplicate record id
    (lambda rows: ['{"op":"write","record":{"id":"z","kind":"NOPE","slots":{}}}'] + rows, 1),
])
def test_jsonl_defects_are_reported_with_their_line_and_never_as_a_raw_exception(git_repo, tmp_path, capsys, mutate, expected_line):
    rows = _jsonl_from(VERA_FRAME, tmp_path).read_text(encoding="utf-8").splitlines()
    bad = tmp_path / "defect.jsonl"
    bad.write_text("\n".join(mutate(rows)) + "\n", encoding="utf-8")
    code, out, err = run_cli(conduct_argv(bad, git_repo, "fake"), capsys)
    assert (code, out["refusal"]["reason"], out["refusal"]["line"]) == (2, "FRAME_JSONL_INVALID", expected_line)
    assert err == ""


def test_jsonl_agent_settings_that_disagree_are_refused_not_resolved_by_order(git_repo, tmp_path, capsys, no_agent_process):
    rows = _jsonl_from(EXAMPLE_FRAMES[0].parent / "library_catalog_search.md", tmp_path).read_text(encoding="utf-8").splitlines()
    first = next(json.loads(r) for r in rows if '"agent setting codex_model"' in r)
    clone = json.loads(json.dumps(first))
    clone["record"]["id"] = "dupmodel0001"
    clone["record"]["slots"]["choice"] = "another-model"
    clone["record"]["witness"]["value"] = "another-model"
    path = tmp_path / "tie.jsonl"
    path.write_text("\n".join(rows + [json.dumps(clone)]) + "\n", encoding="utf-8")
    code, out, _ = run_cli(conduct_argv(path, git_repo, "codex", "--dry-run", "--effort", "low"), capsys)
    assert (code, out["refusal"]["reason"]) == (2, "AGENT_SETTING_INVALID")
    assert "gpt-6-luna" in out["refusal"]["detail"] and "another-model" in out["refusal"]["detail"]


# ----------------------------------------------------------------- the ledger itself
def test_the_ledger_only_grows_and_continues_its_sequence_across_runs(git_repo, capsys):
    _, first, _ = run_cli(conduct_argv(VERA_FRAME, git_repo, "fake"), capsys)
    ledger = Path(first["ledger"])
    before = ledger.read_bytes()
    _, second, _ = run_cli(conduct_argv(VERA_FRAME, git_repo, "fake"), capsys)
    after = ledger.read_bytes()
    assert after.startswith(before) and len(after) > len(before)
    rows = read_ledger(ledger)
    assert [row["seq"] for row in rows] == list(range(len(rows)))
    assert {row["run_id"] for row in rows} == {first["run_id"], second["run_id"]} and first["run_id"] != second["run_id"]


def test_ledger_refuses_a_cut_off_last_row_and_a_sequence_gap(tmp_path):
    from verantyx.conductor_run import ConductLedger, LedgerError

    path = tmp_path / "l.jsonl"
    ledger = ConductLedger(path)
    ledger.append("r", "A")
    ledger.append("r", "B")
    good = path.read_bytes()
    path.write_bytes(good[:-5])
    with pytest.raises(LedgerError):
        ConductLedger(path)
    lines = good.splitlines(keepends=True)
    path.write_bytes(lines[1])  # seq 1 first: a gap
    with pytest.raises(LedgerError):
        ConductLedger(path)
    path.write_bytes(good)
    assert [row["type"] for row in ConductLedger(path).rows] == ["A", "B"]


def test_concurrent_writers_never_duplicate_or_skip_a_sequence_number(tmp_path):
    from verantyx.conductor_run import ConductLedger

    path = tmp_path / "l.jsonl"
    ledgers = [ConductLedger(path) for _ in range(4)]

    def work(ledger, name):
        for index in range(15):
            ledger.append(name, "TICK", n=index)

    threads = [threading.Thread(target=work, args=(ledger, f"w{i}")) for i, ledger in enumerate(ledgers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    rows = read_ledger(path)
    assert [row["seq"] for row in rows] == list(range(60))
    for i in range(4):
        assert [row["n"] for row in rows if row["run_id"] == f"w{i}"] == list(range(15))


# ----------------------------------------------------------------- the frame file we ship
def test_the_added_vera_criterion_is_not_mistaken_for_a_protected_action(tmp_path):
    from verantyx import project_frame
    from verantyx.conductor import ProjectFrame
    from verantyx.memory_frame import Memory

    spec = project_frame.parse_frame(VERA_FRAME.read_text(encoding="utf-8"), source="vera")
    c6 = next(item for item in spec.criteria if item.id == "C6")
    frame = ProjectFrame(Memory(str(tmp_path / "m.jsonl")))
    command = " ".join(c6.witness["command"])
    for text in (c6.text, command, f"{c6.text} {command}"):
        assert frame._protected_action(text) is None
    for text in ("delete the branch", "publish the release"):
        assert frame._protected_action(text) is not None  # the probe does fire on real protected wording
