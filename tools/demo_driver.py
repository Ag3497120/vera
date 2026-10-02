"""Small deterministic acceptance demo for the conductor run loop."""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile

from verantyx.conductor import ProjectFrame
from verantyx.conductor_run import ConductorRun, _task_done_record
from verantyx.memory_frame import Memory
from verantyx.memory_lessons import LessonIndex
from verantyx.memory_revalidate import RevalidatingMemory


class ScriptedAdapter:
    def __init__(self, scripts, intended_order=()):
        self.scripts = list(scripts)
        self.intended_order = tuple(intended_order)
        self.briefs = []
        self.sent = []
        self.stopped = []

    def start(self, brief):
        self.briefs.append(brief)
        events = self.scripts.pop(0) if self.scripts else []
        return {"events": events, "polled": False, "index": len(self.briefs) - 1}

    def poll(self, handle):
        if handle["polled"]:
            return []
        handle["polled"] = True
        return handle["events"]

    def send(self, handle, message):
        self.sent.append((handle["index"], message))

    def stop(self, handle):
        self.stopped.append(handle["index"])


def memory_events(memory):
    events = [{"op": "write", "record": record}
              for record in memory.records.values()]
    events.extend({"op": "supersede", "id": old, "by": new}
                  for old, new in memory.superseded.items())
    events.extend(dict(event) for event in memory.aliases.values())
    return events


def make_project(memory_path, command_runner):
    memory = Memory(str(memory_path))
    frame = ProjectFrame(memory, command_runner=command_runner)
    decision = memory.write(
        "DECISION", "human", witness={"kind": "testimony", "by": "human"},
        subject="作業順", choice="準備から納品",
    )
    for task, item, command in (
        ("準備", "準備確認", "prepare"),
        ("納品", "納品確認", "deliver"),
    ):
        frame.add_acceptance(
            task, item, witness_kind="command_exit",
            target={"command": ["demo", command], "expected_exit": 0},
        )
        frame.add_goal(task, item)
    frame.add_order("準備", "納品", decision["id"])
    return frame


def main():
    with tempfile.TemporaryDirectory(prefix="vera-driver-demo-") as directory:
        root = Path(directory)
        command_state = {"prepare": 1, "deliver": 0}

        def command_runner(target):
            return command_state[target["command"][1]]

        frame = make_project(root / "frame.jsonl", command_runner)

        # Revalidation marks a changed file witness STALE, so it cannot be relied on.
        stale_path = root / "stale-witness.txt"
        stale_path.write_text("old witness", encoding="utf-8")
        stale_record = frame.memory.write(
            "DECISION", "demo stale witness",
            witness={"kind": "file_sha256", "path": str(stale_path),
                     "sha256": hashlib.sha256(stale_path.read_bytes()).hexdigest()},
            subject="一時判断", choice="旧案",
        )
        stale_path.write_text("changed witness", encoding="utf-8")
        revalidated = RevalidatingMemory(
            frame.memory, cache_ttl=0, cache_size=0,
        ).ask("stale witness status probe", require_fresh=False)
        assert revalidated["witness_status"][stale_record["id"]] == "STALE"
        stale_done = frame.memory.write(
            "TASK", "stale prior driver record",
            witness={"kind": "file_sha256", "path": str(stale_path),
                     "sha256": hashlib.sha256("old witness".encode("utf-8")).hexdigest(),
                     "by": "conductor_run", "task_id": "納品",
                     "acceptance_record_ids": ["old-acceptance"]},
            subject="納品", state="完了",
        )
        revalidated = RevalidatingMemory(
            frame.memory, cache_ttl=0, cache_size=0,
        ).ask("stale DONE witness status probe", require_fresh=False)
        assert revalidated["witness_status"][stale_done["id"]] == "STALE"
        assert not _task_done_record(frame, "納品")

        # Two writer logs disagree. The driver merges them and returns typed CONFLICTs.
        left = Memory(str(root / "agent-left.jsonl"))
        right = Memory(str(root / "agent-right.jsonl"))
        left_record = left.write(
            "DECISION", "agent-left", witness={"kind": "testimony", "by": "agent-left"},
            subject="共有順序", choice="案左",
        )
        right_record = right.write(
            "DECISION", "agent-right", witness={"kind": "testimony", "by": "agent-right"},
            subject="共有順序", choice="案右",
        )
        conflict_adapter = ScriptedAdapter([])
        conflict_run = ConductorRun(
            frame, conflict_adapter, log_path=root / "driver.jsonl",
            task_ids=("納品", "準備"),
            agent_memory_logs=(memory_events(left), memory_events(right)),
        ).run()
        assert not conflict_run.complete
        assert conflict_run.blocking_item["kind"] == "memory_conflict"
        assert conflict_run.blocking_item["conflicts"][0]["kind"] == "CONFLICT"
        assert not conflict_adapter.briefs

        # Each writer supersedes its own value with the explicitly agreed value.
        left.write(
            "DECISION", "human resolution for left",
            witness={"kind": "testimony", "by": "human"},
            supersedes=left_record["id"], subject="共有順序", choice="合意案",
        )
        right.write(
            "DECISION", "human resolution for right",
            witness={"kind": "testimony", "by": "human"},
            supersedes=right_record["id"], subject="共有順序", choice="合意案",
        )
        resolved_logs = (memory_events(left), memory_events(right))

        # The caller and fake agent prefer the later phase first. The ORDER graph
        # still dispatches the predecessor, where two failed DONE attempts create
        # a repeatable typed lesson.
        first_adapter = ScriptedAdapter([
            [{"type": "DONE"}, {"type": "DONE"}],
        ], intended_order=("納品", "準備"))
        first_run = ConductorRun(
            frame, first_adapter, log_path=root / "driver.jsonl",
            task_ids=("納品", "準備"), agent_memory_logs=resolved_logs,
        ).run()
        assert not first_run.complete
        assert len(first_adapter.briefs) == 1
        assert first_adapter.intended_order[0] == "納品"
        assert "Current frame task: 準備" in first_adapter.briefs[0]
        lessons = LessonIndex(frame.memory).lessons_for("準備検証失敗")
        assert len(lessons) >= 2

        # The retry brief includes the matched lessons. PREPARE completes, but
        # DELIVER cannot be completed from acceptance alone without its DONE event.
        command_state["prepare"] = 0
        second_adapter = ScriptedAdapter([[{"type": "DONE"}], []])
        second_run = ConductorRun(
            frame, second_adapter, log_path=root / "driver.jsonl",
            task_ids=("納品", "準備"), agent_memory_logs=resolved_logs,
        ).run()
        assert not second_run.complete
        assert second_run.blocking_item["kind"] == "agent_terminal_event"
        assert second_run.blocking_item["missing"] == "agent DONE event"
        assert "Prior typed lessons (context only):" in second_adapter.briefs[0]
        assert "DONE結果確認" in second_adapter.briefs[0]
        assert ["Current frame task: 準備" in second_adapter.briefs[0],
                "Current frame task: 納品" in second_adapter.briefs[1]] == [True, True]

        # A later, witnessed DONE completes the final phase and re-verifies both
        # deterministic acceptance checks before the project is called complete.
        final_adapter = ScriptedAdapter([[{"type": "DONE"}]])
        final_run = ConductorRun(
            frame, final_adapter, log_path=root / "driver.jsonl",
            task_ids=("納品", "準備"), agent_memory_logs=resolved_logs,
        ).run()
        assert final_run.complete
        assert final_run.pending == ()
        assert set(final_run.completed) == {"準備", "納品"}
        assert len(final_adapter.briefs) == 1
        assert "Current frame task: 納品" in final_adapter.briefs[0]

        # ORDER cycles are refused when a driver is constructed from the frame.
        cycle_memory = Memory(str(root / "cycle.jsonl"))
        cycle_frame = ProjectFrame(cycle_memory, command_runner=lambda target: 0)
        cycle_decision = cycle_memory.write(
            "DECISION", "human", witness={"kind": "testimony", "by": "human"},
            subject="循環順", choice="甲乙",
        )
        for task, item in (("甲", "甲確認"), ("乙", "乙確認")):
            cycle_frame.add_acceptance(
                task, item, witness_kind="command_exit",
                target={"command": ["demo", task], "expected_exit": 0},
            )
            cycle_frame.add_goal(task, item)
        cycle_frame.add_order("甲", "乙", cycle_decision["id"])
        cycle_frame.add_order("乙", "甲", cycle_decision["id"])
        try:
            ConductorRun(cycle_frame, ScriptedAdapter([]), log_path=root / "cycle-driver.jsonl")
        except ValueError as exc:
            assert "cycle" in str(exc)
        else:
            raise AssertionError("ORDER cycle was accepted")

    print("DEMO OK")


if __name__ == "__main__":
    main()
