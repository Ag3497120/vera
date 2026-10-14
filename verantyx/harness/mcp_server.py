"""`vera mcp`: Vera as the ONLY exit of an agent (Claude Code, Cursor, any MCP client).

  vera mcp --docs DIR|FILE --question Q [--question Q2 ...] --runs-dir runs      the loom over documents: one task per question; the client calls begin(task_id=q1, model=...),
                                                                              looks up and reads sentences, weaves a quote and `emit`s it (or `abstain`s)
  vera mcp --tasks tasks.jsonl --runs-dir runs                                the loom over a task bank you wrote
  vera mcp --mode memory --store DIR [--phase story]                          the memory: write / recall / report ... (a session; it is committed when the client closes stdin)
  vera mcp --mode memory --store DIR --phase question --question Q            an answer run over the committed memory

The server offers the loom's (or the memory's) tools and nothing else; there is no free-text channel and every call is one row of a hash-chained ledger.
Run it with the agent's own tools switched off (a subagent whose allow-list is `mcp__vera-loom__*`) to make Vera its only way to say something.
"""
from __future__ import annotations

import json
import os
from typing import Any, List, Optional, Sequence

from verantyx.harness import docs_corpus as dc
from verantyx.harness import runner as rn
from verantyx.loom import memanswer as ma
from verantyx.loom import memdoor as md
from verantyx.loom import memmcp
from verantyx.loom import memory as mem
from verantyx.loom import mcp as lm


def prepare_doc_tasks(docs: str, questions: Sequence[str], runs_dir: str) -> str:
    """Write the corpus of `docs` and a task bank (q1, q2, ...) under `runs_dir`; return the task bank path."""
    for q in questions:
        rn.refuse_secret_in_question(q)
    data, _ = dc.build_corpus(docs)
    runs_dir = os.path.abspath(runs_dir)
    corpus_path = os.path.join(runs_dir, "_corpora", dc.corpus_sha(data)[:16] + ".jsonl")
    rn._write_once(corpus_path, data)
    rows = [{"task_id": "q%d" % (i + 1), "text": q.strip(), "lang": "prose", "mode": "record_only", "corpus": corpus_path} for i, q in enumerate(questions) if q.strip()]
    if not rows:
        raise rn.HarnessError("give at least one --question (the loom's tasks are fixed before the client begins)", "no_question")
    tasks_path = os.path.join(runs_dir, "_tasks_%s.jsonl" % dc.corpus_sha(("\n".join(r["text"] for r in rows)).encode("utf-8"))[:12])
    rn._write_once(tasks_path, "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows).encode("utf-8"))
    return tasks_path


def serve_loom(tasks: str, runs_dir: str, evidence: str = rn.EVIDENCE_DEFAULT, subject_scope: str = "clause_or_title", allow_roots: Sequence[str] = ()) -> int:
    return lm.serve(tasks, runs_dir, list(allow_roots), evidence=evidence, subject_scope=subject_scope)


def open_memory_door(store: str, phase: str, model: str, question: Optional[str] = None) -> Any:
    """The door of one memory phase with the bundle `vera mem` uses (mem.v4 + shape.v4 / qwords.v2 / ask.v3, memanswer.v17)."""
    if phase == "story":
        return md.StructureDoor(store, "notes", model, profile=mem.PROFILE_V4, versions=dict(rn.MEM_BUNDLE))
    if not question:
        raise rn.HarnessError("--phase question needs --question", "no_question")
    snap = ma.write_snapshot(store, topics=False, crosses=True, versions=True)
    return md.AnswerDoor(store, "notes", question, model, snapshot=snap, answer_version=rn.MEM_ANSWER_VERSION)


def serve_memory(store: str, phase: str = "story", model: str = "mcp-client", question: Optional[str] = None) -> int:
    if question:
        rn.refuse_secret_in_question(question)
    if phase == "question" and os.path.isfile(os.path.join(store, "HEAD")):
        vs = rn.verify_path(store)
        if vs["status"] != "OK":
            raise rn.HarnessError("the store does not verify (%s): no answer is given from it" % vs["status"], "store_not_verified")
    door = open_memory_door(store, phase, model, question)
    server = memmcp.build(rn.UnsourcedGuard(door, store) if phase == "story" else rn.AnswerMarkGuard(rn.UnrecordedGate(door, store), store))
    if server is None:
        return 2
    try:
        server.run()
    finally:
        if phase == "story" and door.closed(None) is None:
            door.commit()                                   # the operator's commit: a story session is memory only once it is committed
        if hasattr(door, "close"):
            door.close()
    return 0
