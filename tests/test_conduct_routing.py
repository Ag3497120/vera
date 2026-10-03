"""W2-h: the conduct entry chooses the implementer and the verifier by the router when the frame has an
[agents] table, and keeps the [agent_settings] path when it has none.  Agents here are shell scripts."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_conduct_routing_support import *  # noqa: F401,F403  (autouse guards + helpers)
from test_conduct_routing_support import (BARE, COMBINED, HONEST, IMPL_ARGS, PASS_GOOD, Spec, agent, conduct_spec, default,
                                          dsl_tail, new_repo, routed_execute, routed_frame, routing_rows, rule, sum_frame)
from test_agent_routing_support import fake_chooser
from test_conduct_entry_support import (EXAMPLE_FRAMES, ROOT, conduct_argv, read_ledger, rows_of, run_cli)

from verantyx import agent_routing as ar
from verantyx.conductor_run import conduct_entry

STARTED = ("AGENT_START_CALLED", "LAUNCH_PLANNED", "VERIFIER_START_CALLED", "VERIFIER_LAUNCH_PLANNED")


def nothing_started(run) -> bool:
    return not any(row["type"] in STARTED for row in run.rows) and not run.of("AGENT_START_CALLED")


# ------------------------------------------------------------------ the whole routed run
@pytest.fixture(scope="module")
def routed(tmp_path_factory):
    return routed_execute(tmp_path_factory.mktemp("routed") / "r", routed_frame(conduct_spec()))


def test_a_routed_run_starts_the_codex_implementer_and_the_claude_verifier_by_the_routers_decisions(routed):
    run = routed
    assert run.out["verdict"] == "RUN_COMPLETE" and run.out["outcome"] == "COMPLETE"
    decisions = run.of("ROUTING_DECISION")
    assert [(d["role"], d["agent_id"], d["decided_by"], d["stage"]) for d in decisions] == [
        ("implement", "CodexImpl", "rule:IMPL_FEATURE", "rule"), ("verify", "ClaudeVerify", "rule:VERIFY_RULE", "rule")]
    assert all(d["values"] == "declared" and d["job_id"] == run.out["run_id"] and d["task_kind"] in ar.TASK_KINDS
               for d in decisions)
    assert run.one("FRAME_COMPILED")["routing"] == "routed"
    codex = run.one("LAUNCH_PLANNED")
    claude = run.one("VERIFIER_LAUNCH_PLANNED")
    assert Path(codex["argv"][0]).name == "codex.sh" and codex["adapter"] == "codex"
    assert Path(claude["argv"][0]).name == "claude.sh" and claude["adapter"] == "claude"
    assert codex["model"]["source"] == "routing" and codex["model"]["agent_id"] == "CodexImpl"
    limits = run.one("RUN_LIMITS")["verification"]
    assert limits["adapter"]["source"] == "routing" and limits["adapter"]["value"] == "claude"
    assert limits["model"]["agent_id"] == "ClaudeVerify" and limits["same_adapter_as_implementer"] is False
    assert limits["same_lineage_as_implementer"] is False and limits["mode"] == "configured"
    assert [r["type"] for r in run.rows[:5]] == ["CONDUCT_INVOKED", "FRAME_READ", "FRAME_COMPILED", "ROUTING_DECISION",
                                                  "ROUTING_DECISION"]                    # both before anything starts
    assert run.rows.index(decisions[1]) < run.rows.index(run.one("AGENT_START_CALLED"))


def test_R6_one_decision_is_one_row_and_a_decision_row_holds_declared_keys_only(routed):
    run = routed
    decisions = run.of("ROUTING_DECISION")
    assert len(decisions) == 2
    envelope = {"schema", "seq", "run_id", "type", "time"}
    for row in decisions:
        assert set(row) - envelope == set(ar.DECLARED_KEYS) | set(ar.JOIN_KEYS)
        assert not set(row) & set(ar.MEASURED_KEYS)
        assert row["agent_basis"]["kind"] == "declared_dsl" and row["agent_basis"]["line"] >= 1
        assert row["size"] == "small" and row["size_basis"]["thresholds"] == "design values, not measured"
        assert row["size_basis"]["task_kind_source"] == "frame"
    measured = run.of("ROUTING_MEASURED")
    assert len(measured) == 1 and measured[0]["values"] == "measured"
    assert set(measured[0]) - envelope == set(ar.MEASURED_KEYS) | set(ar.JOIN_KEYS)
    assert not set(measured[0]) & set(ar.DECLARED_KEYS)
    assert measured[0]["outcome"] == "COMPLETE" and measured[0]["rounds"] == 1 and measured[0]["elapsed_seconds"] > 0
    assert measured[0]["job_id"] == run.out["run_id"] and run.rows[-1]["type"] == "ROUTING_MEASURED"


def test_R6_the_ledger_only_grows_and_the_second_runs_rows_follow_the_first_runs_bytes(tmp_path):
    state = tmp_path / "state"
    first = routed_execute(tmp_path / "a", routed_frame(conduct_spec()), state=state)
    ledger = Path(first.out["ledger"])
    before = ledger.read_bytes()
    second = routed_execute(tmp_path / "b", routed_frame(conduct_spec()), state=state)
    after = ledger.read_bytes()
    assert after.startswith(before) and len(after) > len(before)
    rows = read_ledger(ledger)
    assert [r["seq"] for r in rows] == list(range(len(rows)))
    for run_id in (first.out["run_id"], second.out["run_id"]):
        mine = [r for r in rows if r["run_id"] == run_id]
        assert sum(r["type"] == "ROUTING_DECISION" for r in mine) == 2 and sum(r["type"] == "ROUTING_MEASURED" for r in mine) == 1
    assert first.out["run_id"] != second.out["run_id"]


# ------------------------------------------------------------------ R3 in a run
def test_R3_when_every_verifier_is_of_the_implementers_lineage_the_run_stops_before_anything_starts(tmp_path):
    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec(verify_prefer=("CodexVerify", "SameLineageClaude"))))
    assert run.out["verdict"] == "REFUSED" and run.out["refusal"]["reason"] == "ROUTING_UNDECIDED"
    assert run.out["refusal"]["code"] == "NO_VIABLE_CANDIDATE" and run.outcome.exit_code == 2
    assert nothing_started(run) and run.of("RUN_LIMITS") == [] and run.of("ROUTING_MEASURED") == []
    implement, verify = run.of("ROUTING_DECISION")
    assert implement["agent_id"] == "CodexImpl"
    assert verify["agent_id"] is None and verify["decided_by"] == "NONE" and verify["stage"] == "NONE"
    assert verify["undecided_reason"] == "NO_VIABLE_CANDIDATE"
    assert {(e["agent_id"], e["reason"]) for e in verify["excluded"]} == {("CodexVerify", "SAME_LINEAGE"), ("SameLineageClaude", "SAME_LINEAGE")}
    assert run.rows[-1]["type"] == "REFUSED" and run.rows[-1]["code"] == "NO_VIABLE_CANDIDATE"
    assert not list((run.state / "runs" / run.out["run_id"]).glob("runtime*"))      # no worktree, no session


def test_R3_a_verifier_of_another_lineage_is_taken_over_one_of_the_same_lineage_and_the_exclusion_is_in_the_ledger(tmp_path):
    spec = conduct_spec(verify_prefer=("SameLineageClaude", "ClaudeVerify"))
    run = routed_execute(tmp_path / "r", routed_frame(spec))
    assert run.out["outcome"] == "COMPLETE"
    verify = run.of("ROUTING_DECISION")[1]
    assert verify["agent_id"] == "ClaudeVerify"
    assert {(e["agent_id"], e["reason"]) for e in verify["excluded"]} == {("SameLineageClaude", "SAME_LINEAGE")}
    assert verify["independence"] == {"implement": "distinct_lineage"}


def test_R3_an_explicit_independent_of_none_lets_the_same_lineage_verify_and_the_ledger_says_so(tmp_path):
    spec = conduct_spec(verify_prefer=("CodexVerify",), verify_when={"role": "verify", "independent_of": "none"})
    run = routed_execute(tmp_path / "r", routed_frame(spec), codex_script=COMBINED)
    assert run.out["outcome"] == "COMPLETE", run.one("RUN_FINISHED")
    verify = run.of("ROUTING_DECISION")[1]
    assert verify["agent_id"] == "CodexVerify" and verify["decided_by"] == "rule:VERIFY_RULE"
    assert verify["independence"] == {"implement": "waived_by:rule:VERIFY_RULE"}
    limits = run.one("RUN_LIMITS")["verification"]
    assert limits["same_adapter_as_implementer"] is True and limits["same_lineage_as_implementer"] is True
    assert run.one("VERIFIER_LAUNCH_PLANNED")["same_adapter_as_implementer"] is True


# ------------------------------------------------------------------ refusals before a start
def test_a_frame_with_an_invalid_routing_table_is_ROUTING_INVALID_and_nothing_is_started(tmp_path):
    spec = conduct_spec()
    spec.agents[0]["kinds"].append("interpretive_dance")
    run = routed_execute(tmp_path / "r", routed_frame(spec))
    refusal = run.out["refusal"]
    assert (refusal["reason"], refusal["code"], run.outcome.exit_code) == ("ROUTING_INVALID", "UNKNOWN_KIND", 2)
    assert refusal["line"] is not None and nothing_started(run) and routing_rows(run) == []
    assert run.of("FRAME_COMPILED") == []


@pytest.mark.parametrize("kwargs,names", [
    ({"adapter": "codex"}, "adapter"), ({"model": "gpt-6-luna"}, "model"), ({"effort": "low"}, "effort"),
    ({"verifier_adapter": "claude"}, "verifier_adapter"), ({"verifier_model": "x"}, "verifier_model"),
    ({"verifier_effort": "low"}, "verifier_effort")])
def test_J2_an_agent_argument_with_an_agents_table_is_refused_and_not_silently_ignored(tmp_path, kwargs, names):
    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec()), **kwargs)
    assert run.out["refusal"]["reason"] == "AGENT_SETTING_INVALID" and run.outcome.exit_code == 2
    assert names in run.out["refusal"]["detail"]
    assert nothing_started(run) and routing_rows(run) == []


def test_J2_a_python_adapter_object_with_an_agents_table_is_refused_too(tmp_path):
    from verantyx.agent_adapter import FakeAdapter

    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec()), adapter=FakeAdapter())
    assert run.out["refusal"]["reason"] == "AGENT_SETTING_INVALID" and nothing_started(run)


def test_J2_without_an_agents_table_the_adapter_is_still_required(tmp_path):
    run = routed_execute(tmp_path / "r", sum_frame(settings=(), quick=True))
    assert run.out["refusal"]["reason"] == "AGENT_SETTING_MISSING" and "--adapter" in run.out["refusal"]["missing"]
    assert nothing_started(run) and run.of("FRAME_COMPILED") == []


def test_J1_a_routed_frame_needs_a_task_kind_and_the_argument_beats_the_frame(tmp_path):
    run = routed_execute(tmp_path / "a", routed_frame(conduct_spec(), settings=("verification_retries: 0",)))
    assert run.out["refusal"]["reason"] == "AGENT_SETTING_MISSING" and "task_kind" in run.out["refusal"]["missing"]
    assert nothing_started(run) and routing_rows(run) == []
    run = routed_execute(tmp_path / "b", routed_frame(conduct_spec(), settings=("verification_retries: 0",)), task_kind="small_fix")
    first = run.of("ROUTING_DECISION")[0]
    assert (first["task_kind"], first["decided_by"], first["size_basis"]["task_kind_source"]) == ("small_fix", "rule:DEFAULT", "cli")
    run = routed_execute(tmp_path / "c", routed_frame(conduct_spec()), task_kind="small_fix")     # the frame says feature
    assert run.of("ROUTING_DECISION")[0]["task_kind"] == "small_fix"
    run = routed_execute(tmp_path / "d", routed_frame(conduct_spec()), task_kind="wizardry")
    assert run.out["refusal"]["reason"] == "AGENT_SETTING_INVALID" and nothing_started(run)


def test_a_task_kind_no_agent_declares_is_a_typed_undecided_and_nothing_starts(tmp_path):
    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec()), task_kind="attack")
    assert run.out["refusal"]["reason"] == "ROUTING_UNDECIDED" and run.out["refusal"]["code"] == "NO_VIABLE_CANDIDATE"
    assert nothing_started(run) and len(run.of("ROUTING_DECISION")) == 1


def test_a_dry_run_records_both_decisions_and_starts_nothing(tmp_path):
    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec()), dry_run=True)
    assert run.out["verdict"] == "DRY_RUN_PLANNED" and run.outcome.exit_code == 0
    assert [d["role"] for d in run.of("ROUTING_DECISION")] == ["implement", "verify"]
    assert run.of("ROUTING_MEASURED") == [] and run.of("VERIFIER_LAUNCH_PLANNED") == []     # nothing ran, so nothing to measure
    assert run.one("LAUNCH_PLANNED")["dry_run"] is True and run.of("PROCESS_STARTED") == []


# ------------------------------------------------------------------ the testimony stage in a run
def tie_conduct_spec() -> Spec:
    spec = conduct_spec(with_answer=True)
    spec.agents.append(agent("CodexImplB", roles=("implement",), kinds=("feature", "small_fix")))
    spec.rules.append(rule("IMPL_SMALL", {"role": "implement", "size": "small"}, ["CodexImplB"]))
    return spec


def test_J11_a_tie_the_records_cannot_settle_puts_the_closed_question_to_the_chooser_and_records_the_testimony(tmp_path):
    chooser, prompts = fake_chooser(["CodexImplB"])
    run = routed_execute(tmp_path / "r", routed_frame(tie_conduct_spec()), routing_chooser=chooser)
    assert run.out["outcome"] == "COMPLETE" and len(prompts) == 2
    impl = run.of("ROUTING_DECISION")[0]
    assert impl["stage"] == "llm_testimony" and impl["agent_id"] == "CodexImplB"
    assert impl["decided_by"] == "llm_testimony:" + impl["testimony"]["decision_id"] and impl["testimony"]["status"] == "ADOPTED"
    assert set(impl["candidates"]) == {"CodexImpl", "CodexImplB"} and impl["matched_rules"] == ["IMPL_FEATURE", "IMPL_SMALL"]


def test_J11_a_chooser_whose_two_asks_disagree_leaves_the_run_unstarted(tmp_path):
    chooser, prompts = fake_chooser(["CodexImpl", "CodexImplB"])
    run = routed_execute(tmp_path / "r", routed_frame(tie_conduct_spec()), routing_chooser=chooser)
    assert len(prompts) == 2 and run.out["refusal"]["code"] == "TESTIMONY_ABSTAINED" and nothing_started(run)
    assert run.of("ROUTING_DECISION")[0]["agent_id"] is None


def test_J11_on_the_command_line_the_asker_is_the_frames_answer_agent_and_a_fake_one_is_unavailable(tmp_path):
    run = routed_execute(tmp_path / "r", routed_frame(tie_conduct_spec()))
    assert run.out["refusal"]["reason"] == "ROUTING_UNDECIDED" and run.out["refusal"]["code"] == "TESTIMONY_UNAVAILABLE"
    asker, implement = run.of("ROUTING_DECISION")
    assert (asker["role"], asker["agent_id"], asker["stage"], asker["task_kind"]) == ("answer", "AskerFake", "rule", "closed_choice")
    assert implement["role"] == "implement" and implement["undecided_reason"] == "TESTIMONY_UNAVAILABLE"
    assert nothing_started(run) and not (run.state / "routing_choice.jsonl").exists()      # no question was ever put


def test_J11_without_an_answer_role_the_tie_is_unavailable_as_well(tmp_path):
    spec = tie_conduct_spec()
    spec.agents = [a for a in spec.agents if a["id"] != "AskerFake"]
    spec.rules = [r for r in spec.rules if not (r["id"] == "DEFAULT" and r["when"]["role"] == "answer")]
    run = routed_execute(tmp_path / "r", routed_frame(spec))
    assert run.out["refusal"]["code"] == "TESTIMONY_UNAVAILABLE"
    assert [d["role"] for d in run.of("ROUTING_DECISION")] == ["answer", "implement"]
    assert run.of("ROUTING_DECISION")[0]["undecided_reason"] == "ROLE_NOT_ROUTABLE"


# ------------------------------------------------------------------ the other agents the table may name
def test_J14_an_implementer_routed_to_a_fake_adapter_runs_the_fake_path_without_a_verifier(tmp_path):
    spec = conduct_spec()
    spec.agents[0].update(adapter="fake", lineage="none")
    run = routed_execute(tmp_path / "r", routed_frame(spec))
    assert [d["role"] for d in run.of("ROUTING_DECISION")] == ["implement"]
    assert run.one("AGENT_START_CALLED")["adapter"] == "fake" and run.of("LAUNCH_PLANNED") == []
    measured = run.one("ROUTING_MEASURED")
    assert measured["outcome"] in ("RUN_COMPLETE", "RUN_INCOMPLETE") and measured["rounds"] == 1


def test_a_verifier_routed_to_a_fake_adapter_is_refused_before_anything_starts(tmp_path):
    spec = conduct_spec()
    spec.agents[1].update(adapter="fake", lineage="none")
    run = routed_execute(tmp_path / "r", routed_frame(spec))
    assert run.out["refusal"]["reason"] == "AGENT_SETTING_INVALID" and nothing_started(run)
    assert len(run.of("ROUTING_DECISION")) == 2


def test_a_table_without_a_verify_role_keeps_the_verification_required_default(tmp_path):
    spec = conduct_spec()
    spec.agents = [a for a in spec.agents if "verify" not in a["roles"]]
    spec.rules = [r for r in spec.rules if r["when"]["role"] != "verify"]
    run = routed_execute(tmp_path / "r", routed_frame(spec))
    assert [d["role"] for d in run.of("ROUTING_DECISION")] == ["implement"]
    assert run.out["outcome"] == "VERIFIER_NOT_CONFIGURED" and run.one("RUN_LIMITS")["verification"] == {"mode": "required_unconfigured"}


# ------------------------------------------------------------------ R5: the old path is untouched
def test_R5_a_frame_without_an_agents_table_runs_as_before_and_says_so(tmp_path):
    repo = new_repo(tmp_path / "repo")
    frame = tmp_path / "frame.md"
    frame.write_text(BARE, encoding="utf-8")
    outcome = conduct_entry(frame, repo, "fake", state_dir=tmp_path / "s", poll_interval=0.02)
    rows = read_ledger(outcome.ledger)
    assert rows_of(rows, "FRAME_COMPILED")[0]["routing"] == "legacy_agent_settings"
    assert not [r for r in rows if r["type"].startswith("ROUTING_")]
    assert [r["type"] for r in rows][:4] == ["CONDUCT_INVOKED", "FRAME_READ", "FRAME_COMPILED", "AGENT_START_CALLED"]


def test_R5_every_example_frame_without_agents_is_legacy_and_the_sample_with_agents_is_routed(tmp_path):
    for path in EXAMPLE_FRAMES:
        repo = new_repo(tmp_path / path.stem / "repo")
        outcome = conduct_entry(path, repo, None if path.stem == "routing_two_lineages" else "fake",
                                state_dir=tmp_path / path.stem / "s", dry_run=path.stem == "routing_two_lineages",
                                codex_bin=sys.executable, claude_bin=sys.executable, poll_interval=0.02)
        rows = read_ledger(outcome.ledger)
        compiled = rows_of(rows, "FRAME_COMPILED")[0]["routing"]
        assert compiled == ("routed" if path.stem == "routing_two_lineages" else "legacy_agent_settings"), path.name


def test_R5_the_old_json_frame_format_is_always_the_old_path(tmp_path, git_repo, capsys):
    from test_conduct_entry import _jsonl_from

    jsonl = _jsonl_from(next(p for p in EXAMPLE_FRAMES if p.stem == "library_catalog_search"), tmp_path)
    code, out, _ = run_cli(conduct_argv(jsonl, git_repo, "fake"), capsys)
    rows = read_ledger(out["ledger"])
    assert rows_of(rows, "FRAME_COMPILED")[0]["routing"] == "legacy_agent_settings" and code in (0, 1)


# ------------------------------------------------------------------ through the real command line
def sample_frame_text() -> str:
    return (ROOT / "docs" / "frames" / "examples" / "routing_two_lineages.md").read_text(encoding="utf-8")


def test_the_cli_routes_the_sample_frame_without_an_adapter_and_dry_runs_to_two_decisions(tmp_path, git_repo, capsys, no_agent_process):
    frame = tmp_path / "sample.md"
    frame.write_text(sample_frame_text(), encoding="utf-8")
    code, out, _ = run_cli(["conduct", "--frame", str(frame), "--repo", str(git_repo), "--dry-run",
                            "--codex-bin", sys.executable, "--claude-bin", sys.executable], capsys)
    assert code == 0 and out["verdict"] == "DRY_RUN_PLANNED"
    rows = read_ledger(out["ledger"])
    decisions = rows_of(rows, "ROUTING_DECISION")
    assert [(d["role"], d["agent_id"]) for d in decisions] == [("implement", "CodexImpl"), ("verify", "ClaudeVerify")]
    assert all(d["decided_by"].startswith("rule:") for d in decisions)


def test_the_cli_task_kind_option_and_the_adapter_rules(tmp_path, git_repo, capsys, no_agent_process):
    frame = tmp_path / "sample.md"
    frame.write_text(sample_frame_text(), encoding="utf-8")
    base = ["conduct", "--frame", str(frame), "--repo", str(git_repo), "--dry-run", "--codex-bin", sys.executable,
            "--claude-bin", sys.executable]
    code, out, _ = run_cli([*base, "--task-kind", "small_fix"], capsys)
    assert code == 0
    assert rows_of(read_ledger(out["ledger"]), "ROUTING_DECISION")[0]["decided_by"] == "rule:IMPL_SMALL_FIX"
    code, out, _ = run_cli([*base, "--adapter", "codex"], capsys)
    assert code == 2 and out["refusal"]["reason"] == "AGENT_SETTING_INVALID"
    legacy = tmp_path / "legacy.md"
    legacy.write_text(BARE, encoding="utf-8")
    code, out, _ = run_cli(["conduct", "--frame", str(legacy), "--repo", str(git_repo), "--dry-run"], capsys)
    assert code == 2 and out["refusal"]["reason"] == "AGENT_SETTING_MISSING"


def test_the_cli_parser_takes_no_adapter_and_knows_the_task_kinds():
    parser_help = subprocess.run([sys.executable, "-m", "verantyx.cli", "conduct", "--help"], capture_output=True, text=True,
                                 env={"PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1", "PATH": "/usr/bin:/bin"})
    assert parser_help.returncode == 0 and "--task-kind" in parser_help.stdout and "[agents]" in parser_help.stdout
    assert all(kind in parser_help.stdout for kind in ar.TASK_KINDS)


# ------------------------------------------------------------------ round 2: a table from another producer, with values unsaid
def _sparse_conduct_table(*, impl_model=None, impl_effort=None, verify_model="claude-sonnet-5-5", verify_effort="low"):
    """A table made by the dictionary producer: the human said which agent does what, not (all of) how to start it."""
    impl = agent("CodexImpl", roles=("implement",), kinds=("feature",))
    verify = agent("ClaudeVerify", adapter="claude", lineage="anthropic", roles=("verify",), kinds=("verification",),
                   model=verify_model, effort=verify_effort)
    for item, model, effort in ((impl, impl_model, impl_effort),):
        for key, value in (("model", model), ("effort", effort)):
            if value is None:
                item.pop(key)
            else:
                item[key] = value
    for item in (impl, verify):
        item.pop("concurrency")
        item.pop("note")
    for key, value in (("model", verify_model), ("effort", verify_effort)):
        if value is None:
            verify.pop(key)
    return ar.table_from_dicts([impl, verify], [
        {**default("implement", ["CodexImpl"]), "reason": None}, {**default("verify", ["ClaudeVerify"]), "reason": None},
        {"id": "IMPL_FEATURE", "when": {"role": "implement", "kind": "feature"}, "prefer": ["CodexImpl"],
         "witnesses": ["Features go to Codex.", "Codex is the implementer."]}])


def _routed_with(monkeypatch, table):
    """Make the conduct entry read this table instead of the frame's own (the frame is only a vehicle)."""
    import dataclasses

    from verantyx import project_frame

    original = project_frame.load_conduct_frame

    def load(path, **kwargs):
        return dataclasses.replace(original(path, **kwargs), routing=table)

    monkeypatch.setattr(project_frame, "load_conduct_frame", load)


@pytest.mark.parametrize("unsaid,expected", [
    (dict(impl_model=None, impl_effort="low"), "model"), (dict(impl_model="gpt-6-luna", impl_effort=None), "effort"),
    (dict(impl_model=None, impl_effort=None), "model and no effort")])
def test_R0_a_chosen_agent_whose_model_or_effort_the_human_did_not_say_stops_before_a_start(tmp_path, monkeypatch, unsaid, expected):
    _routed_with(monkeypatch, _sparse_conduct_table(**unsaid))
    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec()))
    refusal = run.out["refusal"]
    assert (run.out["verdict"], refusal["reason"]) == ("REFUSED", "AGENT_SETTING_MISSING") and run.outcome.exit_code == 2
    assert "CodexImpl" in refusal["missing"] and expected in refusal["missing"] and "CodexImpl" in refusal["detail"]
    assert nothing_started(run) and run.of("RUN_LIMITS") == [] and run.of("ROUTING_MEASURED") == []
    decisions = run.of("ROUTING_DECISION")
    assert [(d["role"], d["agent_id"]) for d in decisions] == [("implement", "CodexImpl")]   # decided, then refused
    assert decisions[0]["agent_basis"]["kind"] == "declared_text" and len(decisions[0]["agent_basis"]["witnesses"]) >= 1


def test_R0_a_verifier_whose_effort_the_human_did_not_say_stops_before_a_start_too(tmp_path, monkeypatch):
    _routed_with(monkeypatch, _sparse_conduct_table(impl_model="gpt-6-luna", impl_effort="low", verify_effort=None))
    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec()))
    assert run.out["refusal"]["reason"] == "AGENT_SETTING_MISSING" and "ClaudeVerify" in run.out["refusal"]["missing"]
    assert "effort" in run.out["refusal"]["missing"] and nothing_started(run)
    assert [(d["role"], d["agent_id"]) for d in run.of("ROUTING_DECISION")] == [("implement", "CodexImpl"), ("verify", "ClaudeVerify")]


def test_R0_a_table_from_another_producer_that_says_everything_runs_like_the_dsls(tmp_path, monkeypatch):
    _routed_with(monkeypatch, _sparse_conduct_table(impl_model="gpt-6-luna", impl_effort="low"))
    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec()))
    assert run.out["outcome"] == "COMPLETE", run.out.get("refusal")
    decisions = run.of("ROUTING_DECISION")
    assert [(d["agent_id"], d["decided_by"], d["agent_basis"]["kind"]) for d in decisions] == [
        ("CodexImpl", "rule:IMPL_FEATURE", "declared_text"), ("ClaudeVerify", "rule:DEFAULT", "declared_text")]
    assert run.one("LAUNCH_PLANNED")["model"]["value"] == "gpt-6-luna"


# ------------------------------------------------------------------ round 3: a lineage the human did not say
def _lineage_unsaid_table(*, impl_lineage=None, waive: bool = False, verifier_lineage="anthropic"):
    """The human named who implements and who verifies; said nothing about kinds, and (for the implementer) no lineage."""
    impl = {"id": "Sonnet 5.5", "adapter": "codex", "model": "gpt-6-luna", "effort": "low", "roles": ["implement"],
            "witness": "実装は Sonnet 5.5。"}
    if impl_lineage is not None:
        impl["lineage"] = impl_lineage
    verify = {"id": "ClaudeVerify", "adapter": "claude", "model": "claude-sonnet-5-5", "effort": "low", "roles": ["verify"],
              "witness": "検証は ClaudeVerify。"}
    if verifier_lineage is not None:
        verify["lineage"] = verifier_lineage
    when = {"role": "verify", "independent_of": "none"} if waive else {"role": "verify"}
    return ar.table_from_dicts([impl, verify], [
        {"id": "r_impl", "when": {"role": "implement"}, "prefer": ["Sonnet 5.5"], "fallback": True, "witness": "実装は Sonnet 5.5。"},
        {"id": "r_verify", "when": when, "prefer": ["ClaudeVerify"], "witness": "検証は ClaudeVerify。"},
        {"id": "r_verify_otherwise", "when": {"role": "verify"}, "prefer": ["ClaudeVerify"], "fallback": True,
         "witness": "検証は ClaudeVerify。"}])


def test_R3_lineage_unsaid_an_implementer_of_unknown_lineage_stops_the_run_before_a_start(tmp_path, monkeypatch):
    _routed_with(monkeypatch, _lineage_unsaid_table())
    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec()))
    refusal = run.out["refusal"]
    assert (run.out["verdict"], refusal["reason"], refusal["code"]) == ("REFUSED", "ROUTING_UNDECIDED", "NO_VIABLE_CANDIDATE")
    assert run.outcome.exit_code == 2 and nothing_started(run) and run.of("ROUTING_MEASURED") == []
    implement, verify = run.of("ROUTING_DECISION")
    assert implement["agent_id"] == "Sonnet 5.5" and implement["kind_fit"] == {"Sonnet 5.5": "undeclared"}
    assert verify["agent_id"] is None and verify["undecided_reason"] == "NO_VIABLE_CANDIDATE"
    assert {(e["agent_id"], e["reason"]) for e in verify["excluded"]} == {("ClaudeVerify", "LINEAGE_UNDECLARED")}


def test_R3_lineage_unsaid_an_explicit_independent_of_none_runs_and_does_not_make_up_whether_the_lineages_match(tmp_path, monkeypatch):
    _routed_with(monkeypatch, _lineage_unsaid_table(waive=True))
    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec()))
    assert run.out["outcome"] == "COMPLETE", run.out.get("refusal")
    verify = run.of("ROUTING_DECISION")[1]
    assert verify["agent_id"] == "ClaudeVerify" and verify["independence"] == {"implement": "waived_by:rule:r_verify"}
    limits = run.one("RUN_LIMITS")["verification"]
    assert limits["same_lineage_as_implementer"] is None and limits["same_adapter_as_implementer"] is False


def test_R3_lineage_unsaid_a_known_pair_of_lineages_still_runs_and_says_false(tmp_path, monkeypatch):
    _routed_with(monkeypatch, _lineage_unsaid_table(impl_lineage="OpenAI系"))
    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec()))
    assert run.out["outcome"] == "COMPLETE", run.out.get("refusal")
    assert run.one("RUN_LIMITS")["verification"]["same_lineage_as_implementer"] is False


# ------------------------------------------------------------------ round 4: no role in a rule (F9), lineage as a relation (F8)
def _plain_agent(agent_id, adapter, model, roles=None, lineage=None, witness=None):
    item = {"id": agent_id, "adapter": adapter, "model": model, "effort": "low", "witness": witness or f"{agent_id}。"}
    if roles is not None:
        item["roles"] = list(roles)
    if lineage is not None:
        item["lineage"] = lineage
    return item


def _role_less_verify_table():
    """The human said which kind of job goes to whom and did not name a role for the verifier."""
    return ar.table_from_dicts(
        [_plain_agent("CodexImpl", "codex", "gpt-6-luna", ["implement"], "openai"),
         _plain_agent("ClaudeVerify", "claude", "claude-sonnet-5-5", None, "anthropic")],
        [{"id": "r_impl", "when": {"role": "implement"}, "prefer": ["CodexImpl"], "fallback": True, "witness": "実装は Codex。"},
         {"id": "r_verification", "when": {"kind": "verification"}, "prefer": ["ClaudeVerify"],
          "witness": "検証の仕事は ClaudeVerify。"}])


def test_R3_role_a_verifier_chosen_by_a_rule_with_no_role_runs_and_the_decision_says_its_role_was_not_declared(tmp_path, monkeypatch):
    _routed_with(monkeypatch, _role_less_verify_table())
    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec()))
    assert run.out["outcome"] == "COMPLETE", run.out.get("refusal")
    implement, verify = run.of("ROUTING_DECISION")
    assert (implement["role"], implement["agent_id"]) == ("implement", "CodexImpl")
    assert (verify["role"], verify["agent_id"], verify["decided_by"]) == ("verify", "ClaudeVerify", "rule:r_verification")
    assert verify["role_fit"] == {"ClaudeVerify": "undeclared"} and verify["independence"] == {"implement": "distinct_lineage"}
    assert run.one("RUN_LIMITS")["verification"]["same_lineage_as_implementer"] is False


def test_R3_role_a_table_whose_only_verify_rule_has_no_role_still_has_a_verifier_for_the_conductor(tmp_path, monkeypatch):
    table = _role_less_verify_table()
    request = ar.RoutingRequest(role="verify", kind="verification", job_id="j", size="small")
    assert not any(item.role == "verify" for item in table.rules) and ar.routable(table, request)


def _relation_table(kind):
    """No lineage name on either agent: the human only said how the two relate."""
    return ar.table_from_dicts(
        [_plain_agent("CodexImpl", "codex", "gpt-6-luna", ["implement"]),
         _plain_agent("ClaudeVerify", "claude", "claude-sonnet-5-5", ["verify"])],
        [{"id": "r_impl", "when": {"role": "implement"}, "prefer": ["CodexImpl"], "fallback": True, "witness": "実装は Codex。"},
         {"id": "r_verify", "when": {"role": "verify"}, "prefer": ["ClaudeVerify"], "fallback": True,
          "witness": "検証は ClaudeVerify。"}],
        lineage_relations=[{"a": "CodexImpl", "b": "ClaudeVerify", "relation": kind,
                            "witness": f"CodexImpl と ClaudeVerify は{'別' if kind == 'distinct' else '同じ'}系統。"}])


def test_R3_relation_a_distinct_relation_between_the_agents_lets_the_run_through_and_the_ledger_cites_it(tmp_path, monkeypatch):
    _routed_with(monkeypatch, _relation_table("distinct"))
    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec()))
    assert run.out["outcome"] == "COMPLETE", run.out.get("refusal")
    verify = run.of("ROUTING_DECISION")[1]
    assert verify["agent_id"] == "ClaudeVerify" and verify["independence"] == {"implement": "distinct_lineage"}
    entry = verify["independence_basis"]["implement"][0]
    assert entry["used_agent"] == "CodexImpl" and entry["verdict"] == "distinct"
    assert entry["relations"][0]["basis"]["witnesses"] == ["CodexImpl と ClaudeVerify は別系統。"]
    assert run.one("RUN_LIMITS")["verification"]["same_lineage_as_implementer"] is False


def test_R3_relation_a_same_relation_between_the_agents_stops_before_any_start(tmp_path, monkeypatch):
    _routed_with(monkeypatch, _relation_table("same"))
    run = routed_execute(tmp_path / "r", routed_frame(conduct_spec()))
    refusal = run.out["refusal"]
    assert (run.out["verdict"], refusal["reason"], refusal["code"]) == ("REFUSED", "ROUTING_UNDECIDED", "NO_VIABLE_CANDIDATE")
    assert nothing_started(run) and run.of("AGENT_START_CALLED") == []
    verify = run.of("ROUTING_DECISION")[1]
    assert verify["agent_id"] is None
    assert [(e["agent_id"], e["reason"]) for e in verify["excluded"]] == [("ClaudeVerify", "SAME_LINEAGE")]
