"""Small no-network demo for the conductor's closed question kinds."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Mapping, Optional

from verantyx.conductor import (
    AgentQuestion,
    ProjectFrame,
    QUESTION_ANSWERABILITY,
    QUESTION_KINDS,
    classify_question,
)
from verantyx.memory_frame import Memory
from verantyx.question import is_content_request


_BASE_ORDER = re.compile(
    r"\b(next|follow(?:s|ing)?|upcoming|sequence|priority|proceed|order of work)\b|"
    r"次|順番|先行|後続|優先順位|どこから進め|何から進め",
    re.I,
)
_BASE_CONFIRM = re.compile(
    r"\b(may i|can i|could i|should i|is it (?:okay|acceptable)|do i have permission)\b|"
    r"\bwould\b.{0,120}\b(?:okay|acceptable)\b|"
    r"してよい|してもよい|してもいい|して(?:も)?大丈夫|許可(?:され|が)|実行可能",
    re.I,
)
_BASE_SCOPE = re.compile(
    r"\b(scope|in scope|out of scope|within scope|included in)\b|"
    r"対象(?:内|外)?|範囲(?:内|外)?|含まれ(?:る|ます)?|スコープ",
    re.I,
)
_BASE_STATUS = re.compile(
    r"\b(done|complete|completed|finished|status|progress)\b|"
    r"完了|終わ(?:っ|り)|済ん|進捗|状態",
    re.I,
)
_BASE_CHOICE = re.compile(
    r"\b(choose|select|pick|which|decide between)\b|選んで|選択|どれを|どちらを|どの案",
    re.I,
)


def _baseline_kind(text: str, options: Optional[list[str]]) -> str:
    """Mirror the pre-wave3 classifier to calculate the fixed holdout baseline."""
    raw = (text or "").strip()
    if not raw or is_content_request(raw):
        return "OTHER"
    if _BASE_ORDER.search(raw):
        return "ORDER"
    if _BASE_SCOPE.search(raw):
        return "SCOPE"
    if _BASE_CHOICE.search(raw) and re.search(r"\bwhich\b|選んで|選択|どれ|どちら", raw, re.I):
        return "CHOICE"
    if _BASE_CONFIRM.search(raw):
        return "CONFIRM"
    if _BASE_STATUS.search(raw):
        return "STATUS"
    if _BASE_CHOICE.search(raw):
        return "CHOICE"
    if options is not None and re.search(r"[?？]$", raw) and re.search(r"\b(which|what)\b|どれ|どちら", raw, re.I):
        return "CHOICE"
    return "OTHER"


def _option_text(value: Any) -> Optional[str]:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        for key in ("text", "label", "value", "name"):
            if isinstance(value.get(key), str):
                return value[key]
    return None


def _extract_question(row: Mapping[str, Any], row_number: int) -> tuple[str, Optional[list[str]]]:
    text: Optional[str] = None
    for key in ("question", "question_text", "text", "prompt", "agent_question", "ask"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            text = value
            break
        if isinstance(value, Mapping):
            for nested_key in ("text", "question", "body", "prompt"):
                nested = value.get(nested_key)
                if isinstance(nested, str) and nested.strip():
                    text = nested
                    break
        if text:
            break
    assert text is not None, f"question text missing at row {row_number}"

    raw_options = row.get("options", row.get("choices"))
    if isinstance(raw_options, Mapping):
        raw_options = list(raw_options.values())
    options = None
    if isinstance(raw_options, list):
        options = [value for raw in raw_options if (value := _option_text(raw)) is not None]
    return text, options


def _load_questions(path: Path) -> list[tuple[str, Optional[list[str]]]]:
    raw = path.read_text(encoding="utf-8")
    if raw.lstrip().startswith("["):
        values = json.loads(raw)
    else:
        values = [json.loads(line) for line in raw.splitlines() if line.strip()]
    assert isinstance(values, list) and values, "real question input must contain rows"
    return [_extract_question(value, index + 1) for index, value in enumerate(values)]


def _assert_constructed_examples() -> None:
    examples = (
        ("Which design do you prefer?", ["minimal", "detailed"], "DESIGN_PREFERENCE"),
        ("Which feature should I enable?", ["search", "export"], "FEATURE_SELECTION"),
        ("Do I have permission to adjust logs?", None, "PERMISSION"),
        ("Could you clarify the retention requirement?", None, "REQUIREMENT_CLARIFICATION"),
        ("Is the deployment plan acceptable?", None, "PLAN_CONFIRMATION"),
        ("Which resource should we allocate?", None, "RESOURCE_CHOICE"),
        ("Which task should I prioritize?", None, "PRIORITY_CHOICE"),
        ("Where should the settings window open?", None, "DECISION_REQUEST"),
    )
    for text, options, expected in examples:
        assert classify_question(text, options) == expected, expected
        assert QUESTION_ANSWERABILITY[expected]

    assert set(QUESTION_ANSWERABILITY) == set(QUESTION_KINDS)
    always_escalate = {"REQUIREMENT_CLARIFICATION", "RESOURCE_CHOICE", "PRIORITY_CHOICE", "DECISION_REQUEST"}
    assert all(QUESTION_ANSWERABILITY[kind].startswith("ALWAYS_ESCALATE:") for kind in always_escalate)


def _assert_record_backed_answers(root: Path) -> None:
    frame = ProjectFrame(Memory(str(root / "records.jsonl")))

    design = frame.add_decision("design preference", "minimal")
    frame.add_decision("alternate layout", "detailed")
    design_policy = frame.add_policy("CHOICE", "design", "minimal", design["id"])

    feature = frame.add_decision("feature selection", "search feature")
    frame.add_decision("alternate feature", "export feature")
    feature_policy = frame.add_policy("CHOICE", "feature", "search feature", feature["id"])

    permission = frame.add_decision("logging permission", "allowed")
    permission_policy = frame.add_policy("CONFIRM", "adjust logs", "allowed", permission["id"])

    plan = frame.add_decision("deployment plan", "approved")
    plan_policy = frame.add_policy("CONFIRM", "deployment plan", "approved", plan["id"])

    cases = (
        (AgentQuestion("design", "Which design do you prefer?", ["minimal", "detailed"]), "minimal", design_policy),
        (AgentQuestion("feature", "Which feature should I enable?", ["search feature", "export feature"]), "search feature", feature_policy),
        (AgentQuestion("permission", "Do I have permission to adjust logs?"), "allowed", permission_policy),
        (AgentQuestion("plan", "Is the deployment plan acceptable?"), "approved", plan_policy),
    )
    for question, expected, record in cases:
        reply = frame.answer(question)
        assert reply.kind == "ANSWER" and reply.answer == expected
        assert record["id"] in reply.record_ids
        assert reply.question_kind == classify_question(question.text, question.options)

    for question in (
        AgentQuestion("requirements", "Could you clarify the retention requirement?"),
        AgentQuestion("resource", "Which resource should we allocate?"),
        AgentQuestion("priority", "Which task should I prioritize?"),
        AgentQuestion("decision", "Where should the settings window open?"),
    ):
        reply = frame.answer(question)
        assert reply.kind == "ESCALATE" and reply.answer is None

    escalation_frame = ProjectFrame(Memory(str(root / "escalation.jsonl")))
    escalation = escalation_frame.add_escalation(
        "adjust logs", "human decision required", "DECISION", question_kind="CONFIRM"
    )
    reply = escalation_frame.answer(AgentQuestion("permission-escalation", "Do I have permission to adjust logs?"))
    assert reply.kind == "ESCALATE" and reply.missing == "DECISION"
    assert escalation["id"] in reply.record_ids


def main() -> None:
    _assert_constructed_examples()
    with tempfile.TemporaryDirectory(prefix="question-kinds-") as temporary:
        root = Path(temporary)
        _assert_record_backed_answers(root)
        empty = ProjectFrame(Memory(str(root / "empty.jsonl")))
        no_record_cases = (
            AgentQuestion("order", "What comes next?"),
            AgentQuestion("choice", "Which route should I pick?", ["internal", "remote"]),
            AgentQuestion("confirm", "Is it acceptable to do this?"),
            AgentQuestion("scope", "Is this within scope?"),
            AgentQuestion("status", "Is the task complete?"),
            AgentQuestion("design", "Which design do you prefer?", ["minimal", "detailed"]),
            AgentQuestion("feature", "Which feature should I enable?", ["search", "export"]),
            AgentQuestion("permission", "Do I have permission to adjust logs?"),
            AgentQuestion("requirements", "Could you clarify the retention requirement?"),
            AgentQuestion("plan", "Is the deployment plan acceptable?"),
            AgentQuestion("resource", "Which resource should we allocate?"),
            AgentQuestion("priority", "Which task should I prioritize?"),
            AgentQuestion("decision", "Where should the settings window open?"),
            AgentQuestion("other", "Tell me a story."),
        )
        for question in no_record_cases:
            assert empty.answer(question).kind != "ANSWER", "no question kind answers without an active record"

        source = os.environ.get("VERA_REAL_QUESTIONS")
        assert source, "VERA_REAL_QUESTIONS is required for the fixed real-question holdout"
        rows = _load_questions(Path(source))
        assert len(rows) == 130, "the real question set must contain 130 rows"
        heldout = [(text, options) for index, (text, options) in enumerate(rows, start=1) if index % 3 == 0]
        assert len(heldout) == 43

        before_other = 0
        after_other = 0
        for index, (text, options) in enumerate(heldout, start=1):
            before_other += _baseline_kind(text, options) == "OTHER"
            after_other += classify_question(text, options) == "OTHER"
            reply = empty.answer(AgentQuestion(f"heldout-{index}", text, options))
            assert reply.kind != "ANSWER", "a kind answered without any active frame record"

        rate = after_other / len(heldout)
        print(f"Held-out OTHER rate before: {before_other}/{len(heldout)} ({before_other / len(heldout):.1%})")
        print(f"Held-out OTHER rate after:  {after_other}/{len(heldout)} ({rate:.1%})")
        assert rate < 0.35, f"held-out OTHER rate {after_other}/{len(heldout)} is not below 35%"
    print("DEMO OK")


if __name__ == "__main__":
    main()
