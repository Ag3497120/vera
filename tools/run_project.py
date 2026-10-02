"""Run the active project frame through the isolated external-agent runtime."""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from verantyx.agent_runtime import AgentRuntime, normalize_allowlist
from verantyx.conductor import ProjectFrame
from verantyx.conductor_run import run_project


def _frame_allowlist(frame: ProjectFrame) -> tuple[str, ...]:
    declarations: list[tuple[str, ...]] = []
    active = getattr(frame, "_active", None)
    if not callable(active):
        raise ValueError("frame does not expose active typed records")
    for record in active():
        if not isinstance(record, dict) or record.get("kind") != "POLICY":
            continue
        slots = record.get("slots", {})
        if not isinstance(slots, dict):
            continue
        for key in ("write_allowlist", "allowed_paths"):
            if key not in slots:
                continue
            raw = slots[key]
            if isinstance(raw, str):
                raw = [raw]
            declarations.append(normalize_allowlist(raw))
            break
    if not declarations:
        raise ValueError("active POLICY records contain no write_allowlist or allowed_paths")
    permitted = set(declarations[0])
    for declared in declarations[1:]:
        permitted.intersection_update(declared)
    if not permitted:
        raise ValueError("active policy write allowlists have no shared path")
    return tuple(sorted(permitted))


def _adapter_spec(value: str) -> tuple[str, str]:
    if value == "codex":
        return "codex", "codex"
    if value.startswith("command:"):
        executable = value[len("command:"):].strip()
        if not executable:
            raise ValueError("command adapter requires an executable")
        return "command", executable
    raise ValueError("--adapter must be codex or command:<exe>")


def _result_dict(result: Any) -> dict[str, Any]:
    return {
        "complete": result.complete,
        "completed": list(result.completed),
        "pending": list(result.pending),
        "blocking_item": result.blocking_item,
        "outcomes": list(result.outcomes),
        "handoffs": list(result.handoffs),
        "interrupted": result.interrupted,
        "resumed": result.resumed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame", required=True, help="typed memory/frame JSONL file")
    parser.add_argument("--repo", required=True, help="Git repository for the private agent worktree")
    parser.add_argument("--adapter", required=True, help="codex or command:<exe>")
    args = parser.parse_args(argv)
    try:
        backend, executable = _adapter_spec(args.adapter)
        frame = ProjectFrame(args.frame)
        allowed_paths = _frame_allowlist(frame)
        runtime = AgentRuntime(args.repo, allowed_paths, backend=backend, executable=executable)
        result = run_project(frame, runtime)
        value = _result_dict(result)
        value["runtime_log"] = str(runtime.log_path)
        print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        return 0 if result.complete else 1
    except Exception as exc:
        print(f"run_project: {type(exc).__name__}: {str(exc)[:512]}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
