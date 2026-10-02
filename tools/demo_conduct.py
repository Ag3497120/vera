"""Acceptance demo for the typed whole-project conductor run loop."""
from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

os.environ.setdefault("VERA_CORPUS_ROOT", "/tmp/vera-empty-materials")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

from verantyx.conductor import ProjectFrame
from verantyx.conductor_run import run_project
from verantyx.memory_frame import Memory


ROOT = Path(__file__).resolve().parents[1]


class ClosedChoiceAsker:
    """Test-only closed-list selector; it returns an index or null only."""

    def __init__(self):
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        block = prompt.split("候補:\n", 1)[-1].split("\n答えは", 1)[0]
        options = []
        for line in block.splitlines():
            match = re.fullmatch(r"\s*(\d+)\s*:\s*(.*?)\s*", line)
            if match:
                options.append((int(match.group(1)), match.group(2)))
        selected = next((index for index, value in options
                         if value.casefold() == "structured record"), None)
        return json.dumps({"choice": selected}, separators=(",", ":"))


class ScriptedAgent:
    """Inert fake agent with a crash after one witnessed task."""

    def __init__(self, ready: dict[str, bool], questions: list[dict[str, object]]):
        self.ready = ready
        self.questions = questions
        self.starts: dict[str, int] = {}
        self.responses: list[tuple[str, dict[str, object]]] = []
        self.crash_after_first_done = True

    def start(self, brief: str):
        match = re.search(r"^Current frame task: (.+)$", brief, re.M)
        if not match:
            raise AssertionError("driver brief did not name the active task")
        task_id = match.group(1).strip()
        self.starts[task_id] = self.starts.get(task_id, 0) + 1
        if task_id == "project-a":
            events = list(self.questions) + [
                {"type": "CLAIM", "task": task_id, "evidence": []},
                {"type": "DONE"},
            ]
        elif task_id == "project-b":
            events = [
                {"type": "DONE"},
                {"type": "DONE"},
            ]
        else:
            raise AssertionError(f"unexpected task {task_id}")
        return {"task_id": task_id, "events": events, "cursor": 0, "last_type": ""}

    def poll(self, handle):
        cursor = handle["cursor"]
        if cursor >= len(handle["events"]):
            return []
        event = handle["events"][cursor]
        handle["cursor"] = cursor + 1
        handle["last_type"] = event["type"]
        return [event]

    def send(self, handle, text: str):
        result = json.loads(text)
        self.responses.append((handle["task_id"], result))
        if handle["last_type"] in {"CLAIM", "DONE"} and result.get("kind") == "ESCALATE":
            self.ready[handle["task_id"]] = True

    def stop(self, handle):
        if handle["task_id"] == "project-a" and self.crash_after_first_done:
            self.crash_after_first_done = False
            raise RuntimeError("injected crash after durable witnessed DONE")


def _make_questions() -> tuple[list[dict[str, object]], dict[str, tuple[str, str | None]]]:
    events: list[dict[str, object]] = []
    gold: dict[str, tuple[str, str | None]] = {}

    def add(question_id: str, text: str, kind: str, answer: str | None,
            options: list[str] | None = None):
        event: dict[str, object] = {"type": "QUESTION", "id": question_id, "text": text}
        if options is not None:
            event["options"] = options
        events.append(event)
        gold[question_id] = (kind, answer)

    for index in range(16):
        suffix = f"{index:02d}"
        add(f"confirm-{suffix}", f"May I read outline section {suffix}?",
            "ANSWER", "yes")
    for index in range(10):
        suffix = f"{index:02d}"
        add(f"scope-{suffix}", f"Is temporary log {suffix} in scope?",
            "ANSWER", "in scope")
    for task_id in ("project-a", "project-b", "project-a", "project-b"):
        qid = f"status-{len(gold):02d}"
        add(qid, f"What is {task_id} status?", "ANSWER", "進行中")
    add("order-0", "What should be the next task?", "ANSWER", "project-a")
    add("order-1", "Which task is next in the sequence?", "ANSWER", "project-a")
    for index in range(2):
        add(f"choice-{index}", "Which artifact format should I choose?", "ANSWER",
            "compact record", ["plain note", "compact record"])
    add("unknown-0", "What is the favorite color of the moon?", "ESCALATE", None)
    add("protected-delete", "Should I just delete the branch?", "ESCALATE", None)
    return events, gold


def _build_frame(root: Path, ready: dict[str, bool], asker: ClosedChoiceAsker,
                 witness_checks: list[tuple[str, bool]]) -> ProjectFrame:
    memory = Memory(str(root / "memory.jsonl"), asker=asker)

    def command_runner(target):
        command = target.get("command", [])
        task_id = command[-1] if isinstance(command, list) and command else ""
        was_ready = ready.get(str(task_id), False)
        witness_checks.append((str(task_id), was_ready))
        return 0 if was_ready else 7

    frame = ProjectFrame(memory, command_runner=command_runner)
    authority = frame.add_decision("project rules", "use the typed project frame")
    sequence = frame.add_decision("project sequence", "foundation before project a")
    format_choice = frame.add_decision("artifact format", "structured record")
    frame.add_decision("alternative format", "plain note")
    frame.add_invariant("unknown answers", "do not guess and abstain on ties")
    frame.add_invariant("protected actions", "delete publish spending and credentials need human authority",
                        authority_boundary=True)

    for index in range(16):
        suffix = f"{index:02d}"
        condition = f"read outline section {suffix}"
        frame.add_policy("CONFIRM", condition, "yes", authority["id"])
    for index in range(10):
        suffix = f"{index:02d}"
        condition = f"temporary log {suffix}"
        frame.add_policy("SCOPE", condition, "in scope", authority["id"])
    frame.add_policy("CHOICE", "artifact format", "structured record", format_choice["id"])

    for task_id, item in (("project-a", "first completion witness"),
                          ("project-b", "second completion witness")):
        acceptance = frame.add_acceptance(
            task_id, item, witness_kind="command_exit",
            target={"command": ["demo-check", task_id], "expected_exit": 0},
        )
        frame.add_goal(task_id, item)

    frame.add_task("foundation", "完了")
    frame.add_task("project-a", "進行中")
    frame.add_task("project-b", "進行中")
    frame.add_order("foundation", "project-a", sequence["id"])
    return frame


def _assert_questions(outcomes, gold, frame):
    by_id = {item["event"].get("id"): item for item in outcomes
             if item["event"].get("type") == "QUESTION"}
    assert len(gold) >= 30
    assert set(by_id) == set(gold)
    recorded_ids = set(frame.memory.records)
    for question_id, (expected_kind, expected_answer) in gold.items():
        outcome = by_id[question_id]["reply"]
        assert outcome["kind"] == expected_kind, (question_id, outcome)
        if expected_kind == "ANSWER":
            assert outcome["answer"] == expected_answer, (question_id, outcome)
            assert outcome["record_ids"], (question_id, outcome)
            assert set(outcome["record_ids"]) <= recorded_ids, (question_id, outcome)
        else:
            assert outcome["kind"] == "ESCALATE", (question_id, outcome)
            assert by_id[question_id].get("handoff"), question_id
    assert by_id["protected-delete"]["handoff"]["protected_action"] == "delete"
    assert len([event for event in frame.memory.aliases.values()
                if event.get("scope") == "agent-option"]) == 1


def main() -> None:
    questions, gold = _make_questions()
    ready = {"project-a": False, "project-b": False}
    witness_checks: list[tuple[str, bool]] = []
    asker = ClosedChoiceAsker()
    with tempfile.TemporaryDirectory(prefix=".demo-conduct-", dir=ROOT) as temp:
        root = Path(temp)
        frame = _build_frame(root, ready, asker, witness_checks)
        adapter = ScriptedAgent(ready, questions)
        log_path = root / "driver.jsonl"

        first = run_project(frame, adapter, log_path=log_path, claimant_id="scripted-worker")
        assert first.interrupted
        assert not first.complete
        assert first.completed == ("project-a",)
        assert "project-b" in first.pending
        assert adapter.starts.get("project-a") == 1
        assert not _task_state_done(frame, "project-b")
        assert not ready["project-b"]
        assert frame.verify_claim("project-b", {"claimant_id": "scripted-worker"}).kind == "ESCALATE"

        claim_results = [item for item in first.outcomes
                         if item["event"].get("type") == "CLAIM"]
        assert claim_results and claim_results[0]["reply"]["kind"] == "ESCALATE"
        assert witness_checks[0] == ("project-a", False)
        journal_rows = [json.loads(line) for line in log_path.read_text().splitlines()]
        failed_claim_seq = next(row["seq"] for row in journal_rows
                                if row.get("type") == "CLAIM_RESULT"
                                and row.get("claimed_task") == "project-a")
        done_seq = next(row["seq"] for row in journal_rows
                        if row.get("type") == "TASK_DONE"
                        and row.get("task_id") == "project-a")
        assert failed_claim_seq < done_seq
        assert any(record.get("kind") == "LESSON"
                   for record in frame.memory.active(require_fresh=True))

        _assert_questions(first.outcomes, gold, frame)
        assert len([item for item in first.outcomes
                    if item["event"].get("type") == "QUESTION"]) >= 30
        assert len(asker.prompts) == 2
        prompt_options = []
        for prompt in asker.prompts:
            block = prompt.split("候補:\n", 1)[-1].split("\n答えは", 1)[0]
            prompt_options.append(tuple(line.split(": ", 1)[1] for line in block.splitlines()
                                        if re.match(r"\s*\d+\s*:", line)))
        assert prompt_options[0] != prompt_options[1]

        second = run_project(frame, adapter, log_path=log_path, claimant_id="scripted-worker")
        assert second.resumed
        assert second.complete
        assert set(second.completed) == {"project-a", "project-b"}
        assert not second.pending
        assert adapter.starts.get("project-a") == 1
        assert adapter.starts.get("project-b") == 1
        all_outcomes = first.outcomes + second.outcomes
        assert sum(item["event"].get("type") == "CLAIM" for item in all_outcomes) == 1
        assert ("project-b", False) in witness_checks
        assert ("project-b", True) in witness_checks
        assert all(_task_state_done(frame, task_id) for task_id in ("project-a", "project-b"))
        assert all(frame.verify_claim(task_id, {"claimant_id": "scripted-worker"}).answer == "done"
                   for task_id in ("project-a", "project-b"))
    print("DEMO OK")


def _task_state_done(frame: ProjectFrame, task_id: str) -> bool:
    return any(record.get("kind") == "TASK" and
               record.get("slots", {}).get("subject", "").casefold() == task_id.casefold() and
               record.get("slots", {}).get("state") == "完了"
               for record in frame.memory.active(require_fresh=True))


if __name__ == "__main__":
    main()
