"""Independent limit and determinism attacks against the agent adapter."""

from __future__ import annotations

import json
import threading
from typing import Any

import pytest

from verantyx.agent_adapter import (
    MAX_BRIEF_CHARS,
    MAX_BRIEF_RECORDS,
    MAX_LINE_CHARS,
    CodexExecAdapter,
    compile_frame_brief,
    parse_agent_output,
)


class Frame:
    def __init__(self, records: list[Any]):
        self.records = records

    def _active(self) -> list[Any]:
        return self.records


class ScriptRunner:
    def __init__(self, chunks: list[Any]):
        self.chunks = list(chunks)
        self.poll_count = 0
        self.stop_count = 0
        self.commands: list[list[str]] = []
        self.sent: list[str] = []

    def start(self, command: list[str]) -> dict[str, int]:
        self.commands.append(command)
        return {"cursor": 0}

    def poll(self, handle: dict[str, int]) -> Any:
        self.poll_count += 1
        if handle["cursor"] >= len(self.chunks):
            return None
        chunk = self.chunks[handle["cursor"]]
        handle["cursor"] += 1
        return chunk

    def send(self, handle: Any, text: str) -> None:
        self.sent.append(text)

    def stop(self, handle: Any) -> None:
        self.stop_count += 1


def _brief_records(brief: str) -> Any:
    return json.loads(brief.split("RECORDS_JSON:\n", 1)[1])


def test_parser_accepts_closed_question_and_keeps_prose_as_other() -> None:
    output = (
        '{"type":"QUESTION","id":"q-1","text":"Choose","options":["a","b"]}\n'
        "plain words\n"
    )

    assert parse_agent_output(output) == [
        {"type": "QUESTION", "id": "q-1", "text": "Choose", "options": ["a", "b"]},
        {"type": "OTHER", "text": "plain words"},
    ]
    assert parse_agent_output(output.encode()) == parse_agent_output(output)


def test_parser_rejects_duplicate_keys_extra_fields_and_nonstandard_constants() -> None:
    output = (
        '{"type":"DONE","type":"DONE"}\n'
        '{"type":"DONE","extra":true}\n'
        '{"type":"DONE","extra":NaN}\n'
    )

    events = parse_agent_output(output)
    assert len(events) == 3
    assert all(event["type"] == "ERROR" for event in events)


def test_parser_enforces_line_and_total_output_budgets() -> None:
    line_limited = parse_agent_output("abcde\nz", max_line_chars=4, max_output_chars=8)
    assert line_limited == [
        {"type": "ERROR", "message": "agent output line exceeded the size limit"},
        {"type": "OTHER", "text": "z"},
    ]

    output_limited = parse_agent_output("a\nb\nc", max_output_chars=3)
    assert output_limited == [
        {"type": "OTHER", "text": "a"},
        {"type": "OTHER", "text": "b"},
        {"type": "ERROR", "message": "agent output exceeded the total size limit"},
    ]


def test_parser_returns_typed_errors_for_bad_input_and_bad_limits() -> None:
    assert parse_agent_output(None) == [{"type": "ERROR", "message": "agent output must be text"}]
    assert parse_agent_output(b"ok\xff") == [{"type": "OTHER", "text": "ok\ufffd"}]
    with pytest.raises(ValueError, match="limits must be positive integers"):
        parse_agent_output("", max_events=0)


def test_brief_is_idempotent_and_independent_of_slot_insertion_order() -> None:
    slots_a = {"zeta": "last", "alpha": "first"}
    slots_b = {"alpha": "first", "zeta": "last"}
    frame_a = Frame([{"id": "r1", "kind": "fact", "slots": slots_a}])
    frame_b = Frame([{"id": "r1", "kind": "fact", "slots": slots_b}])

    brief_a = compile_frame_brief(frame_a, project_root="/workspace/project")
    brief_b = compile_frame_brief(frame_b, project_root="/workspace/project")
    assert brief_a == brief_b
    assert compile_frame_brief(frame_a, project_root="/workspace/project") == brief_a
    assert _brief_records(brief_a) == [
        {"id": "r1", "kind": "fact", "slots": {"alpha": "first", "zeta": "last"}}
    ]


def test_brief_redacts_secrets_and_paths_but_keeps_project_relative_paths() -> None:
    frame = Frame(
        [
            {
                "id": "r2",
                "kind": "note",
                "slots": {
                    "api_token": "visible-secret-value",
                    "external_path": "/etc/passwd",
                    "filename": "src/agent.py",
                    "message": "visit https://example.test/path",
                },
            }
        ]
    )

    records = _brief_records(compile_frame_brief(frame, project_root="/workspace/project"))
    assert records[0]["slots"] == {
        "api_token": "[REDACTED]",
        "external_path": "[PATH_REDACTED]",
        "filename": "src/agent.py",
        "message": "[URL_REDACTED]",
    }


def test_brief_refuses_excess_records_and_deep_nested_values() -> None:
    many_records = [
        {"id": f"r{index}", "kind": "note", "slots": {}}
        for index in range(MAX_BRIEF_RECORDS + 1)
    ]
    with pytest.raises(ValueError, match="too many active records"):
        compile_frame_brief(Frame(many_records))

    nested: Any = "leaf"
    for _ in range(9):
        nested = {"child": nested}
    frame = Frame([{"id": "r1", "kind": "note", "slots": {"nested": nested}}])
    with pytest.raises(ValueError, match="nesting exceeded"):
        compile_frame_brief(frame)


def test_command_builder_keeps_brief_as_one_bounded_argument() -> None:
    adapter = CodexExecAdapter(executable="codex-bin", project_dir="/workspace/a folder")
    brief = "text; $(still one argument)\n"
    command = adapter.build_command(brief)

    assert command[0:2] == ["codex-bin", "exec"]
    assert command[-2:] == ["--", brief]
    assert command[command.index("-C") + 1] == "/workspace/a folder"
    with pytest.raises(ValueError, match="brief must be bounded text"):
        adapter.build_command("x" * (MAX_BRIEF_CHARS + 1))


def test_codex_adapter_streams_split_lines_then_closes_idempotently() -> None:
    runner = ScriptRunner(['{"type":"DONE"}', "\n", None])
    adapter = CodexExecAdapter(runner=runner)
    handle = adapter.start("bounded brief")

    assert adapter.poll(handle) == []
    assert adapter.poll(handle) == [{"type": "DONE"}]
    assert adapter.poll(handle) == []
    assert adapter.poll(handle) == []
    assert runner.poll_count == 3


def test_codex_adapter_bounds_messages_before_sending() -> None:
    runner = ScriptRunner([])
    adapter = CodexExecAdapter(runner=runner)
    handle = adapter.start("brief")

    adapter.send(handle, "x" * MAX_LINE_CHARS)
    with pytest.raises(ValueError, match="message must be bounded text"):
        adapter.send(handle, "x" * (MAX_LINE_CHARS + 1))
    assert runner.sent == ["x" * MAX_LINE_CHARS]


def test_codex_adapter_timeout_closes_and_stops_runner_once() -> None:
    now = [10.0]
    runner = ScriptRunner(["should not be read"])
    adapter = CodexExecAdapter(runner=runner, timeout_seconds=2, clock=lambda: now[0])
    handle = adapter.start("brief")
    now[0] = 12.0

    assert adapter.poll(handle) == [{"type": "ERROR", "message": "agent execution timed out"}]
    assert adapter.poll(handle) == []
    adapter.stop(handle)
    assert runner.poll_count == 0
    assert runner.stop_count == 1


def test_two_concurrent_handles_keep_their_streams_separate() -> None:
    class PerHandleRunner:
        def start(self, command: list[str]) -> dict[str, Any]:
            tag = command[-1]
            return {"chunks": [f'{{"type":"OTHER","text":"{tag}"}}\n', None], "cursor": 0}

        def poll(self, handle: dict[str, Any]) -> Any:
            cursor = handle["cursor"]
            handle["cursor"] += 1
            return handle["chunks"][cursor]

        def send(self, handle: Any, text: str) -> None:
            pass

        def stop(self, handle: Any) -> None:
            pass

    adapter = CodexExecAdapter(runner=PerHandleRunner())
    handles = [adapter.start("reader-a"), adapter.start("reader-b")]
    observed: list[list[dict[str, Any]]] = [[], []]

    def read(index: int) -> None:
        for _ in range(3):
            observed[index].extend(adapter.poll(handles[index]))

    threads = [threading.Thread(target=read, args=(index,), daemon=True) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=2)

    assert all(not thread.is_alive() for thread in threads)
    assert observed == [
        [{"type": "OTHER", "text": "reader-a"}],
        [{"type": "OTHER", "text": "reader-b"}],
    ]


@pytest.mark.xfail(strict=False, reason="DEFECT: non-finite floats serialize as non-standard JSON tokens")
def test_brief_numeric_values_remain_strict_json() -> None:
    frame = Frame([{"id": "r1", "kind": "note", "slots": {"score": float("nan")}}])
    brief = compile_frame_brief(frame)

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-standard JSON constant: {value}")

    json.loads(brief.split("RECORDS_JSON:\n", 1)[1], parse_constant=reject_constant)


@pytest.mark.xfail(strict=False, reason="DEFECT: a brief-sized integer hits the JSON encoder digit guard")
def test_brief_safely_serializes_integers_within_the_brief_size_budget() -> None:
    frame = Frame([{"id": "r1", "kind": "note", "slots": {"count": 10**5000}}])
    brief = compile_frame_brief(frame)
    assert len(brief) <= MAX_BRIEF_CHARS
    assert _brief_records(brief)[0]["slots"]["count"] == 10**5000
