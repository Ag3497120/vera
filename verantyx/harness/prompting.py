"""The system prompts.  Frozen text, shipped as package data; the sha256 of each prompt is recorded in the run (`agent_definition_sha`).

  loom_record_only   the weaver of the loom for a question over documents (record_only mode: every unit is a unit of the documents).  The text of the
                     measured weaver (research tree .claude/agents/loom-weaver-record-only.md, body) plus the API driver note.
  mem_story          the project-memory assistant of a session (the A3 arm of the long-story meter).
  mem_question       the answerer of one question over the memory (the A3 arm).
"""
from __future__ import annotations

import hashlib
import os

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts")


def load(name: str) -> str:
    with open(os.path.join(_DIR, name + ".txt"), encoding="utf-8") as f:
        return f.read()


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def loom_prompt() -> str:
    return load("loom_record_only")


def mem_story_prompt() -> str:
    return load("mem_story")


def mem_question_prompt() -> str:
    return load("mem_question")
