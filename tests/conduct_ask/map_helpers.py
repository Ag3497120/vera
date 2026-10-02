"""Helpers for tests/test_conduct_map_*.py (not collected: the name does not start with test_)."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ca_helpers as H  # noqa: E402,F401

from verantyx import conduct_ask as ca  # noqa: E402
from verantyx import conduct_map as cm  # noqa: E402
from verantyx.llm_choice import ChoiceLedger, ProviderReply  # noqa: E402
from verantyx.project_frame import load_conduct_frame  # noqa: E402

W2G = Path(__file__).resolve().parent / "w2g"
YN_JA, YN_EN = H.YN_JA, H.YN_EN


def w2g(name: str) -> str:
    return str(W2G / "frames" / f"{name}.md")


def fixed_order(n: int) -> list[int]:
    return list(range(n))


def view_of(frame_path: str) -> "ca.FrameView":
    return ca.build_view(load_conduct_frame(frame_path))


def mapper_for(frame_path: str, options: Optional[Sequence[str]], script: Optional[dict] = None, *,
               ledger: Optional[ChoiceLedger] = None, providers: Any = None, order_source: Any = None,
               max_asks: int = 8, max_candidates: int = 24, max_records: int = 3) -> "cm.RecordMapper":
    pair = providers if providers is not None else cm.fake_pair(script or {}, view_of(frame_path), options)
    return cm.RecordMapper(pair, ledger if ledger is not None else ChoiceLedger(None), order_source=order_source or fixed_order,
                           max_asks=max_asks, max_candidates=max_candidates, max_records=max_records)


def ask_map(frame_path: str, question: str, options: Optional[Sequence[str]], script: Optional[dict] = None,
            **kw: Any) -> tuple[dict, "cm.RecordMapper"]:
    """Ask with the record mapping on through an injected mapper whose providers are scripted (made-up answers)."""
    mapper = mapper_for(frame_path, options, script, **kw)
    res = ca.answer_question(frame_path, question, list(options) if options is not None else None, vocab_llm="fake", mapper=mapper)
    return res, mapper


def decided(res: dict) -> tuple:
    return (res["decision"], res["answer"], res["answer_option_index"], res["escalate_reason"], res["escalate_detail"])


def frame_line(frame_path: str, line: int) -> str:
    return Path(frame_path).read_text(encoding="utf-8").splitlines()[line - 1].strip()


class RaisingProvider:
    """A provider whose ask raises (as a test guard against a real process does)."""

    name = "raising"

    def __init__(self, exc: Exception):
        self.exc, self.calls = exc, 0

    def ask(self, prompt: str) -> ProviderReply:
        self.calls += 1
        raise self.exc


class TextProvider:
    """A provider that returns one fixed text for every ask and counts its asks."""

    name = "text"

    def __init__(self, text: str):
        self.text, self.calls, self.prompts = text, 0, []

    def ask(self, prompt: str) -> ProviderReply:
        self.calls += 1
        self.prompts.append(prompt)
        return ProviderReply.success(self.text, provider=self.name)
