"""Scripted, offline demonstration of the one-facade semantic system."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from verantyx.conductor_run import RunResult
from verantyx.semantic_generate import GeneratedText
from verantyx.semantic_outside import OutsideResult
from verantyx.vera_system import RouteRefusal, VeraSystem, VeraSystemResult


class _DoneAdapter:
    """A deterministic hands adapter that reports one terminal DONE event."""

    def start(self, brief: str) -> dict[str, Any]:
        return {"brief": brief, "events": [{"type": "DONE"}], "replies": []}

    def poll(self, handle: dict[str, Any]) -> list[dict[str, str]]:
        if not handle["events"]:
            return []
        return [handle["events"].pop(0)]

    def send(self, handle: dict[str, Any], reply: str) -> None:
        handle["replies"].append(reply)

    def stop(self, _handle: dict[str, Any]) -> None:
        return None


def _frame_text(witness_path: str) -> str:
    witness = json.dumps({
        "kind": "text_in_file",
        "path": witness_path,
        "needle": "demo acceptance source",
    }, ensure_ascii=False, separators=(",", ":"))
    return f'''[goal]
project: demo-project
statement: exercise the typed Vera facade
[philosophy_invariants]
none: none
[completion_criteria]
facade-ran: the constructed acceptance source is present | {witness}
[phases]
none: none
[phase_order]
none: none
[decisions]
none: none
[vocabulary_aliases]
none: none
[escalation_conditions]
none: none
[protected_actions]
none: none
'''


def main() -> None:
    checks = 0

    def check(condition: Any) -> None:
        nonlocal checks
        checks += 1
        assert condition, f"demo assertion {checks} failed"

    documents = {"manual.txt": "太郎は本を読む。"}
    tempdir = tempfile.TemporaryDirectory(prefix=".demo-system-", dir=os.getcwd())
    system = None
    try:
        witness = Path(tempdir.name) / "witness.txt"
        witness.write_text("demo acceptance source\n", encoding="utf-8")
        witness_path = str(witness.relative_to(Path.cwd()))
        system = VeraSystem(documents, frame=_frame_text(witness_path))
        answer = system.ask("太郎が何を読むか。")
        check(isinstance(answer, VeraSystemResult))
        check(answer.capability == "ask" and answer.verdict == "ANSWER")
        check(bool(answer.evidence))
        check(answer.band is not None and answer.band.status == "ABSTAINED")

        spoken = system.say("太郎が何を読むか。")
        check(isinstance(spoken, VeraSystemResult))
        check(isinstance(spoken.payload, GeneratedText))
        check(bool(spoken.provenance["source_spans"]))

        explanation = system.explain("未登録語")
        check(isinstance(explanation.payload, OutsideResult))
        check(explanation.payload.constructed is True)
        check(explanation.payload.answer is False and explanation.payload.evidence is False)
        check(bool(explanation.provenance["view_sources_consulted"]))

        summary = system.summarize("太郎", limit=2)
        check(isinstance(summary.payload, GeneratedText))
        check(bool(summary.provenance["source_spans"]))

        for constructed in (spoken, explanation, summary):
            check(constructed.generated is True)
            check(constructed.verdict != "ANSWER")
            check(constructed.answer is False)
            check(constructed.evidence is False)
            check(constructed.testimony is False)

        run = system.conduct(_DoneAdapter())
        check(isinstance(run.payload, RunResult))
        check(run.payload.complete is True)
        check(run.verdict == "COMPLETE")
        check(run.provenance["agent_output_is_evidence"] is False)

        routed = system.dispatch("ask: 太郎が何を読むか。")
        check(routed.capability == "ask" and routed.answer is True)
        refused = system.dispatch("hello")
        check(isinstance(refused.payload, RouteRefusal))
        check(refused.payload.verdict == "UNCLASSIFIABLE")
        check("ask:" in refused.payload.missing and "summarize:" in refused.payload.missing)

        check(system.shared_index is not None)
        check(system.shared_index.stats()["builds"] == 1)
        check(checks == 38)
    finally:
        if system is not None:
            system.close()
        tempdir.cleanup()

    print("DEMO OK")


if __name__ == "__main__":
    main()
