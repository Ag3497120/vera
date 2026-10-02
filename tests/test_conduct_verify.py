"""W2-b: after the acceptance commands pass, the conductor starts a read-only verifier agent and
re-runs what it claims; only re-run claims count.  Agents here are shell scripts; nothing real is started.

Prefixes name the acceptance criterion (B1..B6 of docs/CONDUCT_VERIFY.md's ticket)."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from test_conduct_verify_support import *  # noqa: F401,F403  (autouse guards + helpers)
from test_conduct_verify_support import (BARE, BY_ARGS, BY_ARGS_ONE, IMPL_ARGS, QUICK_ARGS, CHECK_4_5, CHECK_NO_ARGS, C1_ARGV, HARDCODED, HONEST, LIMIT_CLAUDE, PASS_GOOD,
                                         FAIL_HARDCODED, PY, IMPLEMENTER_SETTINGS, attempt_dependent, dead,
                                         finding, git, implementer_prompts, pool_fixture, register,
                                         same_original_repository, sum_frame, untrusted_data, verdict,
                                         verifier_prompts, verifier_supervisor_pids,
                                         verify_dir, vspec, worktree_lines)
from test_conduct_verify_support import Run, cli_spec, execute_with_failing_sandbox_check, light_execute
from test_conduct_entry_support import read_ledger

D11_PASS = [
    "CONDUCT_INVOKED", "FRAME_READ", "FRAME_COMPILED", "RUN_LIMITS", "REPO_GUARD",
    "AGENT_START_CALLED", "LAUNCH_PLANNED", "AGENT_START_RETURNED", "AGENT_WAITING", "AGENT_EXITED",
    "AGENT_PROCESS_CHECK", "REPO_GUARD", "SANDBOX_CHECK", "ACCEPTANCE_COMMAND", "ACCEPTANCE_COMMAND",
    "ACCEPTANCE_SIDE_EFFECTS", "CANDIDATE_COMMIT", "VERIFIER_BRIEF", "VERIFIER_START_CALLED",
    "VERIFIER_LAUNCH_PLANNED", "VERIFIER_START_RETURNED", "VERIFIER_WAITING", "VERIFIER_EXITED",
    "VERIFIER_PROCESS_CHECK", "VERIFIER_WORKTREE_GUARD", "VERDICT", "VERIFIER_SANDBOX_CHECK",
    "VERIFIER_EVIDENCE", "VERIFIER_EVIDENCE", "VERIFICATION_RESULT", "COMMIT", "RUN_FINISHED"]
VERIFIER_TYPES = ("VERIFIER", "VERIFICATION", "CANDIDATE_COMMIT")
VERIFIER_PREFIXES = ("VERIFIER_", "VERIFICATION_", "CANDIDATE_COMMIT")
CANARY = "SELF-REPORT-CANARY-" + uuid.uuid4().hex
RECORD_V = 'echo $$ > $PIDS/verifier\nsleep 300 &\necho $! > $PIDS/vgrandchild\n'
IMPL_WRITES_CANARY = (HONEST + f'echo "{CANARY}"\n'
                      'while [ $# -gt 0 ]; do [ "$1" = "-o" ] && out=$2; shift; done\n'
                      f'echo "{CANARY}" > "$out"\n')
FIND_IMPL_WT = "impl=$(git worktree list --porcelain | sed -n 's/^worktree //p' | grep '/runtime/sessions/' | head -1)\n"
FIND_MAIN = "main=$(git worktree list --porcelain | sed -n 's/^worktree //p' | head -1)\n"
PASS_JSON_LINE = verdict("PASS", checks=[CHECK_4_5])

NO_VERIFIER_FRAME = sum_frame(settings=IMPLEMENTER_SETTINGS)
NONE_FRAME = sum_frame(settings=("verifier_adapter: none",))     # the implementer's settings come as arguments
SAME_MODEL_FRAME = sum_frame(human=("A person finds the program tidy",), settings=())
SAME_MODEL_ARGS = {**IMPL_ARGS, "verifier_adapter": "codex", "verifier_model": "gpt-6-luna", "verifier_effort": "low"}
# one finding whose command line (63 words of 512 characters) and claim are together larger than the whole
# 32768-character brief limit: the implementer's own brief fits, the brief with this finding added cannot
ONE_FAILING = [finding("UNRELATED_CHANGE", "x" * 2000,
                       {"argv": [PY, "-c", "raise SystemExit(3)", *["y" * 512] * 61], "expect_exit": 0})]
BIG_FILE = HONEST + "yes 'padding line' | head -n 4000 | sed 's/^/# /' >> sum_args.py\n"
COMBINED_CODEX = (
    "#!/bin/sh\n" + 'while [ $# -gt 0 ]; do [ "$1" = "-o" ] && out=$2; shift; done\n'
    "prompt=$(cat)\n"
    "if printf '%s' \"$prompt\" | grep -qF 'VERIFIER BRIEF v2'; then\n"
    "  nonce=$(printf '%s\\n' \"$prompt\" | sed -n 's/^Verdict nonce: \\([0-9a-f]\\{32\\}\\)$/\\1/p' | head -1)\n"
    "  printf '%s\\n' \"$prompt\"\n"                      # codex repeats the prompt on its output
    f"  printf 'some prose\\nVERA_VERDICT %s %s\\n' \"$nonce\" '{json.dumps(PASS_GOOD)}' > \"$out\"\n"
    "else\n" + "  " + HONEST.replace("\n", "\n  ").rstrip(" ") + "fi\n")


def combined_codex(base: Path) -> Run:
    base.mkdir(parents=True, exist_ok=True)
    script = base / "both.sh"
    script.write_text(COMBINED_CODEX, encoding="utf-8")
    script.chmod(0o755)
    return light_execute(base, "", frame=SAME_MODEL_FRAME, adapter="codex", codex_bin=str(script), **SAME_MODEL_ARGS)


SNAP = {"snapshots": True}          # the runs whose test asserts that the original repository is unchanged
register("verify", {
    # B1 and B6 read the same run: the implementer's self-report carries a canary (B6) and the verifier quotes a
    # usage-limit sentence next to its valid verdict (that is not a limit); neither changes the ledger's row types (B1)
    "B1_honest_and_pass": vspec(IMPL_WRITES_CANARY, default=PASS_GOOD, pre=f'echo "{LIMIT_CLAUDE}"\n', **SNAP),
    "B2a_hardcoded_then_fixed": vspec(attempt_dependent(HARDCODED, HONEST), rules=[("print(6)", FAIL_HARDCODED)],
                                      default=PASS_JSON_LINE, **BY_ARGS_ONE, **SNAP),
    "B2b_always_hardcoded_default_retries": vspec(HARDCODED, default=FAIL_HARDCODED, **BY_ARGS_ONE, **SNAP),
    # two findings, one without a command and one whose command does not fail, plus a duplicate and a skipped list:
    # separate tests below read different rows of the same run
    "B3_findings_without_evidence_or_reproduction": vspec(HONEST, default=verdict(
        "FAIL", checks=[CHECK_NO_ARGS], findings=[finding("UNRELATED_CHANGE", "the change looks wrong to me"),
                                                  finding("HARDCODED_ACCEPTANCE", "it prints a constant", CHECK_4_5),
                                                  finding("HARDCODED_ACCEPTANCE", "it prints a constant, again",
                                                          CHECK_4_5)]), **QUICK_ARGS),
    # a hard-coded program: the first check is false, the second claims the exit status of an acceptance command
    # wrongly, the third cannot be run at all
    "B3iii_pass_that_the_re_run_contradicts": vspec(HARDCODED, default=verdict("PASS", checks=[
        CHECK_4_5, {"argv": C1_ARGV, "expect_exit": 1}, {"argv": ["curl", "example.invalid"], "expect_exit": 0}]),
        **BY_ARGS_ONE),
    "B3_sandbox_self_check_fails": lambda base: execute_with_failing_sandbox_check(base),
    # through the real command line: the default requires a verifier; the argument skips verification on purpose
    "B4b_cli_without_a_verifier": cli_spec(HONEST, frame=NO_VERIFIER_FRAME),
    "B4d_cli_skips_verification": cli_spec(HONEST, frame=sum_frame(), args=("--verifier-adapter", "none")),
    # B2 (c) through the real command line: the arguments configure the verifier (the frame has none) and give no retries
    "B4d_cli_configures_the_verifier_and_gives_no_retries": cli_spec(
        HARDCODED, frame=sum_frame(two=False, settings=IMPLEMENTER_SETTINGS), verifier_default=FAIL_HARDCODED,
        args=("--verifier-adapter", "claude", "--verifier-model", "claude-sonnet-5-5", "--verifier-effort", "low",
              "--verifier-timeout-seconds", "60", "--verification-retries", "0")),
    "B4c_frame_opts_out": vspec(HONEST, frame=NONE_FRAME, require_verification=True, **IMPL_ARGS),
    "B4e_python_default": vspec(HONEST, frame=BARE, **IMPL_ARGS),
    # the verifier edits a file that the implementer was allowed to write: only an empty allowlist rejects it
    "B5a_verifier_writes_its_copy": vspec(HONEST, default=PASS_GOOD, pre="echo '# tampered by the verifier' >> sum_args.py\n",
                                          **SNAP, **QUICK_ARGS),
    "B5b_verifier_writes_the_implementer_worktree": vspec(
        HONEST, default=PASS_GOOD, pre=FIND_IMPL_WT + 'echo x > "$impl/written_by_verifier.txt"\n', **SNAP, **QUICK_ARGS),
    "B5b_verifier_writes_the_original_repository": vspec(
        HONEST, default=PASS_GOOD, pre=FIND_MAIN + 'echo x > "$main/written_by_verifier.txt"\n', **SNAP, **QUICK_ARGS),
    "B5c_verifier_exits_abnormally": vspec(HONEST, default=PASS_GOOD, pre=RECORD_V, post="exit 3\n", **SNAP, **QUICK_ARGS),
    "B5d_verifier_exceeds_its_time": vspec(HONEST, first=RECORD_V, raw="sleep 60\n", verifier_timeout_seconds=6, **SNAP, **QUICK_ARGS),
    "B5e_verifier_hits_a_usage_limit": vspec(HONEST, raw=f'echo "{LIMIT_CLAUDE}"\nexit 1\n', **SNAP, **QUICK_ARGS),
    "B5f_verifier_gives_no_verdict": vspec(HONEST, raw='echo "it looks fine to me"\n', **SNAP, **QUICK_ARGS),
    "M_input_too_large": vspec(BIG_FILE, default=PASS_GOOD, **QUICK_ARGS),
    "M_retry_brief_too_large": vspec(HONEST, default=verdict("FAIL", findings=ONE_FAILING), **QUICK_ARGS),
    "M_verifier_program_missing": vspec(HONEST, default=PASS_GOOD, claude_bin="/nonexistent/claude-verifier", **QUICK_ARGS),
    "M_same_model_codex_pair": combined_codex,
})
runs = pool_fixture("verify")


def types_without(run, *skip):
    return [t for t in run.types if t not in skip]


# ------------------------------------------------------------------ B1
def test_b1_an_honest_implementation_and_a_confirmed_pass_complete_and_the_ledger_shows_every_stage(runs):
    run = runs["B1_honest_and_pass"]
    assert run.out["outcome"] == "COMPLETE" and run.out["verdict"] == "RUN_COMPLETE", run.one("RUN_FINISHED")
    assert run.types == D11_PASS
    assert [r["seq"] for r in read_ledger(run.out["ledger"])] == list(range(len(run.types)))
    evidence = run.of("VERIFIER_EVIDENCE")
    assert [e["conclusion"] for e in evidence] == ["MATCHED", "MATCHED"]
    assert [e["status"] for e in evidence] == ["PASS", "PASS"] and evidence[0]["stdout"] == "9\n"
    candidate, commit = run.one("CANDIDATE_COMMIT"), run.one("COMMIT")
    assert commit["sha"] == candidate["sha"] and commit["parent"] == candidate["parent"] != candidate["sha"]
    assert commit["parent"] == run.one("VERIFIER_BRIEF")["base_commit"]
    result = run.one("VERIFICATION_RESULT")
    assert result["decision"] == "PASS_CONFIRMED" and result["counts"]["matched"] == 2
    assert result["counts"]["contradicted"] == 0 and result["counts"]["ignored"] == 0
    assert run.one("VERDICT")["status"] == "PARSED" and run.one("VERDICT")["result"] == "PASS"
    assert run.one("VERIFIER_EXITED")["runtime_terminal"] == "SESSION_ACCEPTED"
    assert run.one("VERIFIER_WORKTREE_GUARD")["changed"] is False
    finished = run.one("RUN_FINISHED")
    assert finished["attempts"] == 1 and finished["verification"] == "configured"
    # the original repository is untouched; only the kept implementer worktree remains besides it
    assert same_original_repository(run)
    assert len(worktree_lines(run)) == 2


# ------------------------------------------------------------------ B2
def test_b2_a_hardcoded_first_attempt_is_sent_back_with_the_re_run_finding_and_the_fix_completes(runs):
    run = runs["B2a_hardcoded_then_fixed"]
    assert run.out["outcome"] == "COMPLETE", run.one("RUN_FINISHED")
    assert len(run.of("AGENT_START_CALLED")) == 2 and len(run.of("VERIFIER_START_CALLED")) == 2
    results = run.of("VERIFICATION_RESULT")
    assert [r["decision"] for r in results] == ["FINDINGS_CONFIRMED", "PASS_CONFIRMED"]
    assert [r["attempt"] for r in results] == [1, 2]
    confirmed = run.of("VERIFIER_EVIDENCE")[0]
    assert confirmed["conclusion"] == "CONFIRMED" and confirmed["status"] == "FAIL" and confirmed["stdout"] == "6\n"
    assert confirmed["perspective"] == "HARDCODED_ACCEPTANCE"
    retry = run.one("IMPLEMENTER_RETRY")
    assert retry["attempt"] == 2 and retry["findings"] == ["V1.1"]
    first, second = implementer_prompts(run)
    assert "VERIFIER FINDINGS" not in first
    assert "VERIFIER FINDINGS (attempt 1" in second
    assert json.dumps(CHECK_4_5["argv"], separators=(",", ":")) in second                      # the command to re-run
    assert '"observed_stdout":"6\\n"' in second                          # what the conductor saw
    assert "the program ignores its arguments" not in second            # the verifier's reason is not passed on
    assert [r["attempt"] for r in run.of("ACCEPTANCE_COMMAND")] == [1, 2]
    worktree = run.one("COMMIT")["worktree"]
    code, text = git(worktree, "show", "HEAD:sum_args.py")
    assert code == 0 and "sum(" in text and "print(6)" not in text      # the last commit holds the corrected program
    assert same_original_repository(run) and len(worktree_lines(run)) == 2


def test_b2_always_hardcoded_with_the_default_two_retries_ends_as_verification_failed(runs):
    run = runs["B2b_always_hardcoded_default_retries"]
    assert run.out["outcome"] == "VERIFICATION_FAILED" and run.out["verdict"] == "RUN_INCOMPLETE"
    assert run.out["blocking"]["kind"] == "VERIFICATION_FAILED"
    failed = run.out["blocking"]["failed_criteria"]
    assert len(failed) == 1 and "HARDCODED_ACCEPTANCE" in failed[0] and "sum_args.py" in failed[0]
    assert len(run.of("AGENT_START_CALLED")) == 3 and len(run.of("VERIFIER_START_CALLED")) == 3   # 1 + 2 retries
    assert [r["decision"] for r in run.of("VERIFICATION_RESULT")] == ["FINDINGS_CONFIRMED"] * 3
    assert [r["attempt"] for r in run.of("IMPLEMENTER_RETRY")] == [2, 3]
    first, second, third = implementer_prompts(run)
    assert "VERIFIER FINDINGS" not in first and "VERIFIER FINDINGS (attempt 1" in second
    # each retry is the first brief plus the latest findings only: the earlier findings do not pile up
    assert "VERIFIER FINDINGS (attempt 2" in third and "VERIFIER FINDINGS (attempt 1" not in third
    assert run.of("COMMIT") == [] and run.one("RUN_FINISHED")["attempts"] == 3
    assert run.one("RUN_LIMITS")["verification"]["retries"] == {"value": 2, "source": "default",
                                                                "overridden_frame_value": None}
    assert len(worktree_lines(run)) == 1 and same_original_repository(run)


def test_b2_zero_retries_stops_after_one_implementer_attempt(runs):
    run = runs["B4d_cli_configures_the_verifier_and_gives_no_retries"]      # started through the command line
    assert (run.code, run.out["outcome"]) == (1, "VERIFICATION_FAILED"), run.err
    assert len(run.of("AGENT_START_CALLED")) == 1 and run.of("IMPLEMENTER_RETRY") == []
    limits = run.one("RUN_LIMITS")["verification"]
    assert limits["mode"] == "configured" and limits["retries"] == {"value": 0, "source": "cli", "overridden_frame_value": None}
    assert limits["timeout_seconds"] == {"value": 60, "source": "cli", "overridden_frame_value": None}
    assert limits["adapter"]["source"] == "cli" and limits["model"]["value"] == "claude-sonnet-5-5"
    assert run.one("CONDUCT_INVOKED")["cli"]["require_verification"] is True
    assert run.of("COMMIT") == []


# ------------------------------------------------------------------ B3: the verifier's lies do not pass
def test_b3_i_a_failure_without_evidence_is_not_counted_and_nothing_is_sent_back(runs):
    run = runs["B3_findings_without_evidence_or_reproduction"]
    row = run.of("VERIFIER_EVIDENCE")[0]
    assert (row["source"], row["index"], row["status"], row["conclusion"]) == ("finding", 1, "NOT_RUN", "NO_EVIDENCE")
    assert row["argv"] is None and row["exit_code"] is None                  # nothing was run for it
    counts = run.one("VERIFICATION_RESULT")["counts"]
    assert counts["no_evidence"] == 1 and counts["confirmed"] == 0           # it is not a valid finding
    assert run.out["outcome"] == "VERIFICATION_UNCONFIRMED"                  # and so the run is not failed for it
    assert len(run.of("AGENT_START_CALLED")) == 1 and run.of("IMPLEMENTER_RETRY") == []
    assert run.of("COMMIT") == []


def test_b3_ii_a_finding_that_does_not_reproduce_is_not_valid(runs):
    run = runs["B3_findings_without_evidence_or_reproduction"]
    evidence = [e for e in run.of("VERIFIER_EVIDENCE") if e["argv"]]
    assert len(evidence) == 1                                                # the repeated command ran once
    assert evidence[0]["status"] == "PASS" and evidence[0]["stdout"] == "9\n"
    assert evidence[0]["conclusion"] == "NOT_REPRODUCED"
    counts = run.one("VERIFICATION_RESULT")["counts"]
    assert counts["not_reproduced"] == 1 and counts["confirmed"] == 0
    assert run.of("COMMIT") == [] and run.of("IMPLEMENTER_RETRY") == []
    assert run.one("VERIFICATION_RESULT")["decision"] == "UNCONFIRMED"
    # what was skipped or repeated is counted, not dropped silently
    assert counts["duplicates"] == 1 and counts["ignored"] == 1 and counts["ignored_detail"] == {"fail_checks": 1}


@pytest.mark.parametrize("index, status, conclusion", [
    (1, "FAIL", "CONTRADICTED"),      # the program prints 6 for 4 5, not 9
    (2, "FAIL", "CONTRADICTED"),      # the acceptance command exits 0, the verifier claimed 1
    (3, "REFUSED", "UNVERIFIED"),     # a command the conductor will not run is not "contradicted", it is "unknown"
])
def test_b3_iii_a_pass_that_the_conductors_run_contradicts_is_not_a_pass(index, status, conclusion, runs):
    run = runs["B3iii_pass_that_the_re_run_contradicts"]
    row = run.of("VERIFIER_EVIDENCE")[index - 1]
    assert (row["source"], row["status"], row["conclusion"]) == ("check", status, conclusion)
    assert run.one("VERIFICATION_RESULT")["decision"] == "PASS_CONTRADICTED"
    assert run.out["outcome"] == "VERIFIER_PASS_CONTRADICTED" and run.out["verdict"] == "RUN_INCOMPLETE"
    assert run.of("COMMIT") == [] and len(worktree_lines(run)) == 1
    assert len(run.of("AGENT_START_CALLED")) == 1                       # a lying pass is not sent back for rework
    counts = run.one("VERIFICATION_RESULT")["counts"]
    assert (counts["contradicted"], counts["unverified"], counts["matched"]) == (2, 1, 0)
    assert run.of("VERIFIER_EVIDENCE")[2]["refusal_reason"] == "NETWORK_PROGRAM"


def test_b3_the_sandbox_is_never_skipped_when_its_self_check_fails(runs):
    run = runs["B3_sandbox_self_check_fails"]
    rows = run.of("VERIFIER_EVIDENCE")
    assert [(r["status"], r["error"], r["conclusion"]) for r in rows] == [("ERROR", "SANDBOX_UNAVAILABLE", "UNVERIFIED")] * 2
    assert run.one("VERIFIER_SANDBOX_CHECK")["ok"] is False
    assert run.out["outcome"] == "VERIFICATION_UNCONFIRMED" and run.of("COMMIT") == []
    assert len(run.of("AGENT_START_CALLED")) == 1 and run.of("IMPLEMENTER_RETRY") == []   # not sent back for rework
    assert not list(verify_dir(run).glob("rerun-*/sum_args.py"))         # no command ever ran in a copy


# ------------------------------------------------------------------ B4: verification is required by default
def test_b4_a_without_a_verifier_the_run_stops_after_the_acceptance_and_nothing_is_completed(runs):
    run = runs["B4b_cli_without_a_verifier"]
    assert run.out["outcome"] == "VERIFIER_NOT_CONFIGURED" and run.out["verdict"] == "RUN_INCOMPLETE"
    assert run.out["blocking"]["kind"] == "VERIFIER_NOT_CONFIGURED"
    assert run.one("AGENT_EXITED")["runtime_terminal"] == "SESSION_ACCEPTED"   # the implementer did run
    assert [c["status"] for c in run.of("ACCEPTANCE_COMMAND")] == ["PASS", "PASS"]
    assert not [t for t in run.types if t.startswith(VERIFIER_PREFIXES)]
    assert run.of("COMMIT") == [] and len(worktree_lines(run)) == 1
    assert run.one("RUN_LIMITS")["verification"]["mode"] == "required_unconfigured"


def test_b4_b_the_cli_requires_a_verifier_by_default(runs):
    run = runs["B4b_cli_without_a_verifier"]
    assert (run.code, run.out["verdict"], run.out["outcome"]) == (1, "RUN_INCOMPLETE", "VERIFIER_NOT_CONFIGURED"), run.err
    assert run.one("RUN_LIMITS")["verification"]["mode"] == "required_unconfigured"
    assert run.of("COMMIT") == [] and not [t for t in run.types if t.startswith(VERIFIER_PREFIXES)]


def _resolved(settings=(), *, require, cli=None):
    from verantyx.conductor_run import _resolve_verification
    from verantyx.project_frame import load_conduct_frame

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "frame.md"
        path.write_text(sum_frame(settings=(*IMPLEMENTER_SETTINGS, *settings)), encoding="utf-8")
        return _resolve_verification(load_conduct_frame(path), "codex", "gpt-6-luna", cli=cli or {}, require=require,
                                     codex_bin="codex", claude_bin="claude")


def test_b4_the_mode_follows_the_frame_the_arguments_and_the_require_flag():
    # the Python flag of B4 (a): nothing configured is "required but unconfigured" only when a verifier is required
    assert _resolved(require=True)["mode"] == "required_unconfigured"
    assert _resolved(require=False)["mode"] == "not_requested"
    assert _resolved(("verifier_adapter: none",), require=True)["mode"] == "skipped"
    assert _resolved(("verifier_adapter: none",), require=True)["skip_source"] == "frame"
    assert _resolved(require=True, cli={"adapter": "none"})["skip_source"] == "cli"
    configured = _resolved(("verifier_adapter: claude", "verifier_model: claude-sonnet-5-5", "verifier_effort: low"),
                           require=False)
    assert configured["mode"] == "configured" and configured["retries"]["value"] == 2 and \
        configured["retries"]["source"] == "default" and configured["same_adapter_as_implementer"] is False


def test_b4_c_a_frame_that_opts_out_completes_and_the_ledger_says_nothing_was_verified(runs):
    run = runs["B4c_frame_opts_out"]
    assert run.out["outcome"] == "COMPLETE"
    skipped = run.one("VERIFICATION_SKIPPED")
    assert skipped["source"] == "frame"
    assert run.types.index("VERIFICATION_SKIPPED") > run.types.index("ACCEPTANCE_SIDE_EFFECTS")
    assert run.types.index("VERIFICATION_SKIPPED") < run.types.index("COMMIT")
    assert run.one("RUN_LIMITS")["verification"]["mode"] == "skipped"
    assert not [t for t in run.types if t.startswith(("VERIFIER_", "VERIFICATION_RESULT", "CANDIDATE_COMMIT"))]


def test_b4_d_the_command_line_can_skip_verification_on_purpose_even_over_a_configured_verifier(runs):
    run = runs["B4d_cli_skips_verification"]          # the frame configures a claude verifier; the argument says none
    assert (run.code, run.out["verdict"], run.out["outcome"]) == (0, "RUN_COMPLETE", "COMPLETE"), run.err
    assert run.one("VERIFICATION_SKIPPED")["source"] == "cli"
    limits = run.one("RUN_LIMITS")["verification"]
    assert limits["mode"] == "skipped" and limits["adapter"]["source"] == "cli"
    assert limits["model"]["overridden_frame_value"] == "claude-sonnet-5-5"   # the frame's value was overridden, and kept visible
    assert not [r for r in run.rows if r["type"].startswith(("VERIFIER_", "CANDIDATE"))]


def test_b4_e_the_python_default_keeps_the_w2a_ending_and_records_that_no_verifier_was_requested(runs):
    run = runs["B4e_python_default"]
    assert run.out["outcome"] == "COMPLETE"
    assert not [t for t in run.types if t.startswith(VERIFIER_PREFIXES)]
    assert run.one("RUN_LIMITS")["verification"]["mode"] == "not_requested"
    assert run.types[-2:] == ["COMMIT", "RUN_FINISHED"] and len(run.types) == 18   # W2-a's 18 rows, exactly


# ------------------------------------------------------------------ B5: the verifier cannot change the work
B5 = {
    "a": ("B5a_verifier_writes_its_copy", "VERIFIER_MODIFIED_WORKTREE"),
    "b": ("B5b_verifier_writes_the_implementer_worktree", "VERIFIER_MODIFIED_WORKTREE"),
    "c": ("B5c_verifier_exits_abnormally", "VERIFIER_FAILED"),
    "d": ("B5d_verifier_exceeds_its_time", "VERIFIER_TIMED_OUT"),
    "e": ("B5e_verifier_hits_a_usage_limit", "VERIFIER_LIMIT_REACHED"),
    "f": ("B5f_verifier_gives_no_verdict", "VERIFIER_OUTPUT_INVALID"),
}


@pytest.mark.parametrize("letter", list(B5))
def test_b5_each_verifier_failure_has_its_own_type_and_leaves_nothing_behind(letter, runs):
    name, expected = B5[letter]
    run = runs[name]
    assert run.out["outcome"] == expected, run.one("RUN_FINISHED")
    assert run.out["verdict"] == "RUN_INCOMPLETE" and run.of("COMMIT") == []
    assert len(worktree_lines(run)) == 1 and same_original_repository(run)
    # a verdict that could not be read is recorded under the extraction's own name (NO_VERDICT), the others under their type
    assert run.one("VERIFICATION_RESULT")["decision"] == ("NO_VERDICT" if letter == "f" else expected)
    assert run.one("VERIFIER_PROCESS_CHECK")["group_alive"] is False
    assert all(dead(pid) for pid in verifier_supervisor_pids(run))
    if letter in "cd":
        pids = [int((run.pids / n).read_text()) for n in ("verifier", "vgrandchild")]
        assert all(dead(pid) for pid in pids)


def test_b5_a_verifier_that_writes_its_own_copy_is_caught_by_the_runtime(runs):
    run = runs["B5a_verifier_writes_its_copy"]
    exited = run.one("VERIFIER_EXITED")
    assert exited["runtime_terminal"] == "SESSION_REJECTED" and "write allowlist violation" in exited["terminal_message"]
    assert "sum_args.py" in exited["terminal_message"]                     # an allowed path of the implementer, still refused
    assert run.one("VERIFIER_WORKTREE_GUARD")["changed"] is False       # the other worktrees were not touched


def test_b5_a_verifier_that_writes_the_implementers_worktree_or_the_repository_is_caught_by_the_conductor(runs):
    impl = runs["B5b_verifier_writes_the_implementer_worktree"]
    guard = impl.one("VERIFIER_WORKTREE_GUARD")
    assert guard["changed"] is True and guard["where"] == "implementer_worktree"
    assert "written_by_verifier.txt" in guard["status_after"] and "written_by_verifier.txt" not in guard["status_before"]
    assert impl.one("VERIFIER_EXITED")["runtime_terminal"] == "SESSION_ACCEPTED"   # its own copy was clean
    main = runs["B5b_verifier_writes_the_original_repository"]
    assert main.out["outcome"] == "VERIFIER_MODIFIED_WORKTREE"
    guard = main.one("VERIFIER_WORKTREE_GUARD")
    assert guard["where"] == "original_repository"
    assert "written_by_verifier.txt" in json.dumps(guard["repository_after"]) and \
        "written_by_verifier.txt" not in json.dumps(guard["repository_before"])
    for run in (impl, main):
        assert run.of("COMMIT") == [] and len(worktree_lines(run)) == 1


def test_b5_the_six_verifier_failures_are_six_different_types(runs):
    types = {runs[name].out["outcome"] for name, _ in B5.values()}
    assert types == {"VERIFIER_MODIFIED_WORKTREE", "VERIFIER_FAILED", "VERIFIER_TIMED_OUT", "VERIFIER_LIMIT_REACHED",
                     "VERIFIER_OUTPUT_INVALID"}
    assert len({runs[name].out["outcome"] for name, _ in B5.values()}) == 5   # (a) and (b) are one type, two places
    assert runs["B5a_verifier_writes_its_copy"].out["blocking"]["reason"] != \
        runs["B5b_verifier_writes_the_implementer_worktree"].out["blocking"]["reason"]


def test_b5_a_timed_out_verifier_is_stopped_by_its_own_deadline_not_by_a_guess(runs):
    exited = runs["B5d_verifier_exceeds_its_time"].one("VERIFIER_EXITED")
    assert exited["runtime_terminal"] == "SESSION_TIMED_OUT" and exited["guard_deadline_used"] is False


def test_b5_a_usage_limit_sentence_with_no_verdict_is_a_limit_and_not_an_invalid_output(runs):
    exited = runs["B5e_verifier_hits_a_usage_limit"].one("VERIFIER_EXITED")
    assert exited["limit_text_seen"] is True and exited["exit_code"] == 1


# ------------------------------------------------------------------ B6: the self-report is not handed over
def test_b6_the_implementers_self_report_never_reaches_the_verifier(runs):
    run = runs["B1_honest_and_pass"]
    assert run.out["outcome"] == "COMPLETE"
    assert run.one("VERIFIER_EXITED")["limit_text_seen"] is True         # control: a limit sentence beside a valid verdict
    exited = run.one("AGENT_EXITED")
    assert CANARY in exited["output_tail"] and CANARY in exited["last_message_tail"]     # the control: it was said
    brief_row = run.one("VERIFIER_BRIEF")
    assert CANARY not in brief_row["brief"]
    prompts = verifier_prompts(run)
    assert len(prompts) == 1 and CANARY not in prompts[0]
    assert prompts[0].startswith(brief_row["brief"])
    ledger_text = Path(run.out["ledger"]).read_text(encoding="utf-8")
    assert CANARY in ledger_text and CANARY not in json.dumps({k: v for k, v in brief_row.items()})
    assert brief_row["inputs"] == ["task", "goal", "invariants", "acceptance", "write_allowlist", "base_commit",
                                   "candidate_commit", "diff"]
    data = untrusted_data(brief_row["brief"])
    assert sorted(data) == sorted(brief_row["inputs"])
    assert data["write_allowlist"] == ["sum_args.py"] and data["task"] == "SumArgs"
    assert data["candidate_commit"] == run.one("CANDIDATE_COMMIT")["sha"]
    assert "print(sum(" in data["diff"] and data["invariants"] == ["Keep the program in one small file named sum_args.py"]
    assert [a["argv"] for a in data["acceptance"]] == [C1_ARGV, [PY, "-c", C2_ARGV[2]]]
    assert f"VERA_VERDICT {brief_row['nonce']}" not in brief_row["brief"]       # the example is a placeholder
    assert "VERA_VERDICT <nonce>" in brief_row["brief"] and len(brief_row["nonce"]) == 32
    assert brief_row["brief_chars"] == len(brief_row["brief"]) <= 32768


def test_b6_the_brief_builder_refuses_a_key_that_is_not_in_the_closed_set():
    from verantyx.verifier_agents import BRIEF_PAYLOAD_KEYS, build_conduct_verifier_brief

    payload = {key: "x" for key in BRIEF_PAYLOAD_KEYS}
    nonce = "0123456789abcdef0123456789abcdef"
    assert "Verdict nonce: " + nonce in build_conduct_verifier_brief(payload, nonce=nonce)
    for extra in ("implementer_output", "last_message", "agent_output"):
        with pytest.raises(ValueError, match="unknown verifier brief key"):
            build_conduct_verifier_brief({**payload, extra: "I did it"}, nonce=nonce)
    with pytest.raises(ValueError, match="missing verifier brief key"):
        build_conduct_verifier_brief({k: v for k, v in payload.items() if k != "diff"}, nonce=nonce)
    with pytest.raises(ValueError):
        build_conduct_verifier_brief(payload, nonce="short")


# ------------------------------------------------------------------ read-only launch and the other types
def test_the_verifier_is_launched_read_only_and_the_implementer_keeps_its_write_sandbox(runs):
    run = runs["B1_honest_and_pass"]
    planned = run.one("VERIFIER_LAUNCH_PLANNED")
    assert planned["read_only"] is True and planned["allowlist"] == []
    assert planned["argv"][-6:] == ["--permission-mode", "dontAsk", "--disallowedTools",
                                    "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch", "--allowedTools", "Read,Grep,Glob"]
    assert planned["argv"][:5] == [run.rows[0]["cli"].get("claude_bin", planned["argv"][0]), "-p", "--model",
                                   "claude-sonnet-5-5", "--effort"]
    assert planned["same_adapter_as_implementer"] is False and planned["same_model_as_implementer"] is False
    assert "-s" in run.one("LAUNCH_PLANNED")["argv"] and "workspace-write" in run.one("LAUNCH_PLANNED")["argv"]
    assert run.one("VERIFIER_BRIEF")["inputs"] and planned["stdin"]["sha256"] != run.one("LAUNCH_PLANNED")["stdin"]["sha256"]


def test_the_same_model_as_the_implementer_is_allowed_and_recorded(runs):
    run = runs["M_same_model_codex_pair"]
    # a passed verification with human judgment left: the run waits for the human, the worktree is kept
    assert run.out["outcome"] == "HUMAN_JUDGMENT_PENDING", run.one("RUN_FINISHED")
    assert run.one("VERIFICATION_RESULT")["decision"] == "PASS_CONFIRMED" and run.of("COMMIT") == []
    assert len(worktree_lines(run)) == 2
    planned = run.one("VERIFIER_LAUNCH_PLANNED")
    assert planned["same_adapter_as_implementer"] is True and planned["same_model_as_implementer"] is True
    argv = planned["argv"]
    assert argv[argv.index("-s") + 1] == "read-only"
    impl = run.one("LAUNCH_PLANNED")["argv"]
    assert impl[impl.index("-s") + 1] == "workspace-write"
    assert run.one("RUN_LIMITS")["verification"]["same_model_as_implementer"] is True
    assert run.one("VERDICT")["source"] == "last_message"                 # codex repeats the prompt on its output


def test_a_verifier_brief_over_the_limit_is_not_cut_and_not_sent(runs):
    run = runs["M_input_too_large"]
    assert run.out["outcome"] == "VERIFIER_INPUT_TOO_LARGE"
    brief = run.one("VERIFIER_BRIEF")
    assert brief["too_large"] is True and brief["brief"] is None and brief["brief_chars"] > 32768
    assert run.of("VERIFIER_START_CALLED") == [] and run.of("COMMIT") == []


def test_findings_that_do_not_fit_the_retry_brief_stop_the_run_instead_of_being_cut(runs):
    run = runs["M_retry_brief_too_large"]
    assert run.out["outcome"] == "RETRY_BRIEF_TOO_LARGE"
    assert run.one("VERIFICATION_RESULT")["counts"]["confirmed"] == 1
    first = run.one("AGENT_START_CALLED")["brief_chars"]
    assert first <= 32768                                    # the implementer's own brief fitted ...
    reason = run.out["blocking"]["reason"]
    size = int(reason.split("is ")[1].split(" characters")[0])
    assert size > 32768 > size - 32000 and "nothing is cut" in reason    # ... the brief with the finding did not, and was not cut
    assert run.of("IMPLEMENTER_RETRY") == [] and len(run.of("AGENT_START_CALLED")) == 1
    assert len(worktree_lines(run)) == 1


def test_a_missing_verifier_program_is_a_start_failure_and_the_candidate_is_discarded(runs):
    run = runs["M_verifier_program_missing"]
    assert run.out["outcome"] == "VERIFIER_START_FAILED"
    assert run.one("VERIFIER_START_FAILED")["error"] == "ExecutableNotFound"
    assert run.of("COMMIT") == [] and len(worktree_lines(run)) == 1


# ------------------------------------------------------------------ the decision table without processes
def _extraction(result: str, **kwargs):
    from verantyx.verifier_agents import ConductVerdict, VerdictExtraction
    return VerdictExtraction("PARSED", ConductVerdict(result, **kwargs))


def _row(source, conclusion):
    return {"source": source, "conclusion": conclusion}


DECISIONS = [
    (("PASS", {}), [], "UNCONFIRMED", "VERIFICATION_UNCONFIRMED"),                       # a pass resting on nothing
    (("PASS", {}), [_row("check", "MATCHED")], "PASS_CONFIRMED", None),
    (("PASS", {}), [_row("check", "MATCHED"), _row("check", "UNVERIFIED")], "UNCONFIRMED", "VERIFICATION_UNCONFIRMED"),
    (("PASS", {}), [_row("check", "MATCHED"), _row("check", "CONTRADICTED")], "PASS_CONTRADICTED",
     "VERIFIER_PASS_CONTRADICTED"),
    (("FAIL", {}), [_row("finding", "CONFIRMED")], "FINDINGS_CONFIRMED", "VERIFICATION_FAILED"),
    (("FAIL", {}), [_row("finding", "NOT_REPRODUCED"), _row("finding", "NO_EVIDENCE")], "UNCONFIRMED",
     "VERIFICATION_UNCONFIRMED"),
    (("UNDETERMINED", {"reason": "cannot tell"}), [], "UNDETERMINED", "VERIFICATION_UNDETERMINED"),
]


def test_the_decision_table_keeps_cannot_tell_and_false_apart():
    from verantyx.conductor_run import _verification_decision

    for (result, kwargs), rows, decision, outcome in DECISIONS:
        got = _verification_decision(_extraction(result, **kwargs), rows, duplicates=0, ignored=0, ignored_detail={})
        assert (got["decision"], got["outcome"]) == (decision, outcome), (result, rows)


def test_a_verdict_that_could_not_be_read_is_an_invalid_output_under_its_own_name():
    from verantyx.conductor_run import _verification_decision
    from verantyx.verifier_agents import VerdictExtraction

    for status in ("NO_VERDICT", "MULTIPLE_VERDICTS", "MALFORMED"):
        got = _verification_decision(VerdictExtraction(status), [], duplicates=0, ignored=0, ignored_detail={})
        assert (got["decision"], got["outcome"]) == (status, "VERIFIER_OUTPUT_INVALID")
