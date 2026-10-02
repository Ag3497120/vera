"""Compile the Vera frame and demonstrate cited conductor answers and refusals."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("VERA_CORPUS_ROOT", "/tmp/vera-empty-materials")

from verantyx.conductor import AgentQuestion
from verantyx.project_frame import FrameParseError, compile_frame, load_frame, parse_frame


FRAME_PATH = ROOT / "docs" / "frames" / "vera_project_frame.md"


def main() -> int:
    source_text = FRAME_PATH.read_text(encoding="utf-8")
    spec = load_frame(FRAME_PATH)

    malformed = "[goal]\nproject: Vera\nstatement: example\n[unknown]\nfield: value\n"
    try:
        parse_frame(malformed, source="malformed demo frame")
    except FrameParseError as exc:
        assert exc.line == 4
        assert "unknown section" in exc.message
    else:
        raise AssertionError("an undeclared section was accepted")

    with tempfile.TemporaryDirectory(prefix=".frame-demo-", dir=ROOT) as scratch:
        compiled = compile_frame(spec, Path(scratch) / "memory.jsonl")
        assert compiled.spec.project == "Vera"
        assert compiled.spec.goal.startswith("Vera is a general chatbot")
        assert len(compiled.spec.criteria) == 5
        assert all(record.get("witness", {}).get("kind") == "testimony" for record in compiled.records)
        assert all("source" in record["witness"] and isinstance(record["witness"].get("line"), int)
                   for record in compiled.records)

        questions = [
            ("phase-order", AgentQuestion("demo-order", "What order of work should come next?")),
            ("publish", AgentQuestion("demo-publish", "May I publish the project?")),
            ("delete", AgentQuestion("demo-delete", "May I delete project records?")),
            ("spend money", AgentQuestion("demo-spend", "May I spend money for this?")),
            ("enter credentials", AgentQuestion("demo-credentials", "May I enter credentials?")),
            ("access evaluation-only material", AgentQuestion("demo-evaluation", "May I access evaluation-only material?")),
            ("scope", AgentQuestion("demo-scope", "Is general QA and dialogue in scope?")),
            ("local demo", AgentQuestion("demo-confirm", "May I run the local demo?")),
            ("base choice", AgentQuestion("demo-choice", "基本構造はどちらを選択しますか？",
                                           options=["立体十字", "case-frame fallback"])),
            ("unsupported request", AgentQuestion("demo-unknown", "What is an unsupported request?")),
        ]
        assert len(questions) == 10
        active = {record["id"]: record for record in compiled.memory.active(require_fresh=True)}
        replies = {}
        for label, question in questions:
            reply = compiled.conductor.answer(question)
            assert reply.record_ids, f"{label} answer did not cite a record"
            assert all(record_id in active for record_id in reply.record_ids), f"{label} cited a missing record"
            replies[label] = reply

        order_reply = replies["phase-order"]
        assert order_reply.kind == "ESCALATE"
        assert any(active[rid]["kind"] == "ORDER" and active[rid]["slots"] == {"subject": "P1", "target": "P2"}
                   for rid in order_reply.record_ids)

        protected = ("publish", "delete", "spend money", "enter credentials", "access evaluation-only material")
        for action in protected:
            reply = replies[action]
            assert reply.kind == "ESCALATE", f"protected action {action!r} did not escalate"
            assert any(active[rid]["kind"] == "ESCALATE" and
                       active[rid].get("witness", {}).get("protected_action") is True and
                       active[rid].get("witness", {}).get("condition") == action
                       for rid in reply.record_ids), f"{action!r} escalation lacks its frame record"

        scope_reply = replies["scope"]
        assert scope_reply.kind == "ANSWER" and scope_reply.answer == "in scope"
        scope_policy = next(active[rid] for rid in scope_reply.record_ids
                           if active[rid]["kind"] == "POLICY" and
                           active[rid]["witness"].get("condition") == "general QA and dialogue")
        assert scope_policy["witness"]["authority_record_id"] in scope_reply.record_ids

        demo_reply = replies["local demo"]
        assert demo_reply.kind == "ANSWER" and demo_reply.answer == "permitted"
        assert any(active[rid]["kind"] == "POLICY" and active[rid]["witness"].get("condition") == "local demo"
                   for rid in demo_reply.record_ids)

        choice_reply = replies["base choice"]
        assert choice_reply.kind == "ANSWER" and choice_reply.answer == "立体十字"
        assert any(active[rid]["kind"] == "ALIAS" and active[rid]["slots"] ==
                   {"subject": "立体十字", "value": "stereo cross"} for rid in choice_reply.record_ids)

        unknown_reply = replies["unsupported request"]
        assert unknown_reply.kind == "ESCALATE"
        assert any(active[rid]["kind"] == "ESCALATE" and
                   active[rid]["witness"].get("condition") == "unsupported request"
                   for rid in unknown_reply.record_ids)

    assert source_text.endswith("\n")
    print("DEMO OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
