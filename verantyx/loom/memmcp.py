"""MEM-d: the MCP door of the memory meter — the FastMCP server `vera-mem` (docs/LINE3_LOOM_MEMORY_DESIGN.md 4.2, 9.1 MEM-d; owner 2026-10-13).

The memory tools of the loom, as an MCP server, one arm and one phase per process (`--arm context|log|blind|notes`, `--phase story|question`):

  story, structure arms (blind, notes)   write declare_topic supersede recall read_sentence report status        -> a `MemStore` session (profile mem.v2) of `--store`
  story, log                             log_append log_read report                                             -> a BaselineRun
  story, context                         report
  question, structure arms               recall lookup read_sentence weave_span drop read emit abstain status    -> an answer run over a snapshot of `--store` (`--question`)
  question, baselines                    log_read answer / answer

NO FREE-TEXT CHANNEL.  Every tool returns JSON, nothing the model writes outside a tool call is read, and the only products are rows of a hash-chained ledger (the session's, or the answer
run's `emit`).  The same enforcement as `vera-loom`: a tool outside the arm's list does not exist for the server (`unknown_tool`, no row), arguments are typed by the schema and
checked again by the run, a refusal is a typed row.  `commit` is the OPERATOR's: the server commits a story session when it shuts down (stdin closed), never on the model's word.
The tool schemas are the table `memdoor.TOOL_SPECS` (the L2 driver offers exactly those, `memdoor.api_tools`); the MCP signature adds only an optional `turn` to `report` (an L1 run has no
driver to tell the door which message it is on).  Run:  python -m verantyx.loom.memmcp --store DIR --arm notes [--phase story] [--model ID]
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional, Sequence

from verantyx.loom import memdoor as md
from verantyx.loom import memory as mem

SERVER_NAME = "vera-mem"
PREFIX = "mcp__vera-mem__"


def tool_names(arm: str, phase: str) -> Sequence[str]:
    return (md.STORY_TOOLS if phase == "story" else md.QUESTION_TOOLS)[arm]


def open_door(store, arm: str, phase: str, model: str, question: Optional[str] = None):
    """The door of one (arm, phase): StructureDoor / AnswerDoor / BaselineDoor."""
    if arm in md.STRUCTURE_ARMS:
        if phase == "story":
            return md.StructureDoor(store, arm, model)
        if question is None:
            raise ValueError("the question phase needs a question")
        return md.AnswerDoor(store, arm, question, model)
    return md.BaselineDoor(store, arm, phase, model, question)


def build(door: Any):
    """The FastMCP server for an open door, WITHOUT running it (None if the SDK is missing).  Exactly the door's tools are registered.  `mcp.mem_door` is the door behind it."""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        print('MCP SDK not installed. Run:  pip install "mcp[cli]"')
        return None
    server = FastMCP(SERVER_NAME)
    server.mem_door = door
    names = list(door.tool_names)

    def out(tool: str, args: dict) -> str:
        return json.dumps(door.call(tool, args), ensure_ascii=False, sort_keys=True)

    fns: Dict[str, Any] = {}

    def reg(fn):
        fns[fn.__name__] = fn
        return fn

    @reg
    def write(text: str) -> str:
        return out("write", {"text": text})

    @reg
    def declare_topic(text: str) -> str:
        return out("declare_topic", {"text": text})

    @reg
    def supersede(new_sid: int, reason: str, old_sid: int = -1, old_answer: str = "", question: str = "") -> str:
        a: Dict[str, Any] = {"new_sid": new_sid, "reason": reason}
        if old_sid != -1:                                       # -1 / "" = not given (the schema has defaults); any other value reaches the run and is judged there
            a["old_sid"] = old_sid
        if old_answer:
            a["old_answer"] = old_answer
        if question:
            a["question"] = question
        return out("supersede", a)

    @reg
    def recall(question: str) -> str:
        return out("recall", {"question": question})

    @reg
    def read_sentence(sid: int) -> str:
        return out("read_sentence", {"sid": sid})

    @reg
    def lookup(text: str, tier: str) -> str:
        return out("lookup", {"text": text, "tier": tier})

    @reg
    def status() -> str:
        return out("status", {})

    @reg
    def report(contradictions: List[List[str]], bugs: List[str] = [], turn: str = "") -> str:      # noqa: B006  (never mutated)
        if turn and door.turn is None:
            door.set_turn(turn)
        a: Dict[str, Any] = {"contradictions": contradictions}
        if bugs:
            a["bugs"] = bugs
        return out("report", a)

    @reg
    def log_append(text: str) -> str:
        return out("log_append", {"text": text})

    @reg
    def log_read(grep: str = "") -> str:
        return out("log_read", {"grep": grep} if grep else {})

    @reg
    def answer(kind: str, values: List[str]) -> str:
        return out("answer", {"kind": kind, "values": values})

    @reg
    def weave_span(sid: int, tier: str, first: str, last: str) -> str:
        return out("weave_span", {"sid": sid, "tier": tier, "first": first, "last": last})

    @reg
    def drop(cid: str) -> str:
        return out("drop", {"cid": cid})

    @reg
    def read() -> str:
        return out("read", {})

    @reg
    def emit() -> str:
        return out("emit", {})

    @reg
    def abstain(type: str) -> str:
        return out("abstain", {"type": type})

    for n in names:                                         # registered in the arm's order: exactly the door's tools, no other
        server.tool(name=n, description=md.TOOL_SPECS[n]["description"])(fns[n])
    return server


def serve(store, arm: str, phase: str = "story", model: str = "mcp-client", question: Optional[str] = None) -> int:
    door = open_door(store, arm, phase, model, question)
    server = build(door)
    if server is None:
        return 2
    try:
        server.run()
    finally:
        if phase == "story" and getattr(door, "commit", None) is not None and door.closed(None) is None:
            door.commit()                                     # the operator's commit: a story session is memory only once it is committed
        if hasattr(door, "close"):
            door.close()
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m verantyx.loom.memmcp", description="the vera-mem MCP server (one arm, one phase)")
    ap.add_argument("--store", required=True, help="the store / arm folder (required; there is no default path)")
    ap.add_argument("--arm", required=True, choices=md.ARMS)
    ap.add_argument("--phase", default="story", choices=("story", "question"))
    ap.add_argument("--model", default="mcp-client")
    ap.add_argument("--question", default=None)
    ns = ap.parse_args(list(sys.argv[1:] if argv is None else argv))
    return serve(ns.store, ns.arm, ns.phase, ns.model, ns.question)


if __name__ == "__main__":
    raise SystemExit(main())
