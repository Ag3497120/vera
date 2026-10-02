"""Shared helpers for tests/test_conduct_ask_*.py (not collected: the name does not start with test_)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verantyx import conduct_ask  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FRAMES = FIXTURES / "frames"
YN_JA = ["はい", "いいえ"]
YN_EN = ["Yes", "No"]


def frame(name: str) -> str:
    return str(FRAMES / f"{name}.md")


def ask(frame_name: str, question: str, options: Optional[list[str]] = None, **kw: Any) -> dict[str, Any]:
    path = frame_name if "/" in frame_name else frame(frame_name)
    return conduct_ask.answer_question(path, question, options, **kw)


def edit_frame(tmp_path: Path, name: str, *, drop: tuple[str, ...] = (), replace: tuple[tuple[str, str], ...] = (),
               append: Optional[dict[str, str]] = None, out_name: Optional[str] = None) -> str:
    """Write a modified copy of a fixture frame under tmp_path and return its path."""
    text = (FRAMES / f"{name}.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    out = []
    for ln in lines:
        if any(ln.startswith(d) for d in drop):
            continue
        for a, b in replace:
            ln = ln.replace(a, b)
        out.append(ln)
        for header, extra in (append or {}).items():
            if ln.strip() == header:
                out.append(extra)
    p = tmp_path / f"{out_name or name}.md"
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return str(p)


def mark_stripped(text: str) -> str:
    return conduct_ask._MARK_RX.sub("", text).strip()


KEYS = ("schema", "decision", "kind", "answer", "answer_option_index", "derivation", "resolver", "basis", "escalate_reason",
        "escalate_detail", "vocab", "options", "trace", "frame")


def jsonl_items() -> list[dict[str, Any]]:
    return [json.loads(ln) for ln in (FIXTURES / "items.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
