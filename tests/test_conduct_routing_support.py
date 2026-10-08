"""Helpers for the W2-h conduct tests (no tests of its own).  Real agents are never started: the codex and
claude "agents" are shell scripts the test writes.  Existing helpers are imported, not changed."""
from __future__ import annotations

import json
from pathlib import Path

from test_agent_routing_support import Spec, agent, default, dsl_tail, rule  # noqa: F401
from test_conduct_verify_support import *  # noqa: F401,F403  (autouse guards + helpers)
from test_conduct_verify_support import (HONEST, PASS_GOOD, Run, new_repo, read_ledger, sum_frame, verifier_script,
                                         write_script)

# One script that is both the implementer and (when its prompt is a verifier brief) the verifier: for a table
# whose implementer and verifier are the same adapter and so share one executable.
COMBINED = (
    "#!/bin/sh\n" + 'while [ $# -gt 0 ]; do [ "$1" = "-o" ] && out=$2; shift; done\n'
    "prompt=$(cat)\n"
    "if printf '%s' \"$prompt\" | grep -qF 'VERIFIER BRIEF v2'; then\n"
    "  nonce=$(printf '%s\\n' \"$prompt\" | sed -n 's/^Verdict nonce: \\([0-9a-f]\\{32\\}\\)$/\\1/p' | head -1)\n"
    "  printf '%s\\n' \"$prompt\"\n"
    f"  printf 'some prose\\nVERA_VERDICT %s %s\\n' \"$nonce\" '{json.dumps(PASS_GOOD)}' > \"$out\"\n"
    "else\n" + "  " + HONEST.replace("\n", "\n  ").rstrip(" ") + "fi\n")


def conduct_spec(*, verify_prefer=("ClaudeVerify",), verify_when=None, with_answer: bool = False) -> Spec:
    """CodexImpl (openai) implements; the verifier is named by ``verify_prefer``."""
    agents = [agent("CodexImpl", roles=("implement",), kinds=("feature", "small_fix")),
              agent("ClaudeVerify", adapter="claude", lineage="anthropic", model="claude-sonnet-5-5",
                    roles=("verify",), kinds=("verification",)),
              agent("CodexVerify", roles=("verify",), kinds=("verification",)),
              agent("SameLineageClaude", adapter="claude", lineage="openai", model="claude-sonnet-5-5",
                    roles=("verify",), kinds=("verification",))]
    rules = [rule("IMPL_FEATURE", {"role": "implement", "kind": "feature"}, ["CodexImpl"]),
             rule("VERIFY_RULE", verify_when or {"role": "verify", "kind": "verification"}, list(verify_prefer)),
             default("implement", ["CodexImpl"]), default("verify", list(verify_prefer))]
    if with_answer:
        agents.append(agent("AskerFake", adapter="fake", lineage="none", roles=("answer",), kinds=("closed_choice",)))
        rules.append(default("answer", ["AskerFake"]))
    return Spec(agents, rules)


def routed_frame(spec: Spec, *, settings=("task_kind: feature", "verification_retries: 0"), human=()) -> str:
    """The SumArgs frame with one cheap acceptance command, plus the routing sections of ``spec``."""
    return sum_frame(settings=settings, quick=True, human=human) + dsl_tail(spec)


def routed_execute(base: Path, frame: str, *, impl_body: str = HONEST, verifier_default=PASS_GOOD, codex_script: str | None = None,
                   repo: Path | None = None, state: Path | None = None, **kwargs) -> Run:
    """Run ``conduct_entry`` with ``adapter=None`` on a routed frame with scripted executables."""
    from verantyx.conductor_run import conduct_entry

    base.mkdir(parents=True, exist_ok=True)
    pids = base / "pids"
    pids.mkdir(exist_ok=True)
    repo = repo if repo is not None else new_repo(base / "repo")
    if codex_script is None:
        codex = write_script(base / "codex.sh", impl_body.replace("$PIDS", str(pids)))
    else:
        codex = base / "codex.sh"
        codex.write_text(codex_script, encoding="utf-8")
        codex.chmod(0o755)
    claude = verifier_script(base / "claude.sh", default=verifier_default, flavour="claude")
    frame_path = base / "frame.md"
    frame_path.write_text(frame, encoding="utf-8")
    state = state if state is not None else base / "state"
    kwargs.setdefault("codex_bin", str(codex))
    kwargs.setdefault("claude_bin", str(claude))
    kwargs.setdefault("poll_interval", 0.02)
    kwargs.setdefault("require_verification", True)
    adapter = kwargs.pop("adapter", None)
    outcome = conduct_entry(frame_path, repo, adapter, state_dir=state, **kwargs)
    out = outcome.as_dict()
    rows = [r for r in read_ledger(out["ledger"]) if r["run_id"] == out["run_id"]] if out["ledger"] else []
    return Run(outcome, out, rows, repo, Path(out["ledger"]).parent if out["ledger"] else state, pids)


def routing_rows(run: Run) -> list[dict]:
    return [r for r in run.rows if r["type"].startswith("ROUTING_")]
