"""Compile a deterministic, character-budgeted context brief from typed memory."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from typing import Literal

from .memory_frame import check_witness


_PRIORITY = {"INVARIANT": 0, "DECISION": 1, "TASK": 2, "LESSON": 3, "FACT": 4}
_CLOSED_TASK_STATES = {"完了", "done", "complete", "completed", "finished"}


@dataclass(frozen=True)
class BriefRecord:
    """A memory citation carried as context, with its original witness status."""

    id: str
    kind: str
    sentence: str
    witness_status: str

    @property
    def use(self) -> Literal["CONTEXT_ONLY"]:
        return "CONTEXT_ONLY"

    @property
    def evidence_authority(self) -> Literal[False]:
        return False


@dataclass(frozen=True)
class ContextBrief:
    """Typed agent context; this object is neither an answer nor evidence."""

    text: str
    records: tuple[BriefRecord, ...]
    dropped_ids: tuple[str, ...]

    @property
    def result_type(self) -> Literal["CONTEXT_ONLY"]:
        return "CONTEXT_ONLY"

    @property
    def evidence_authority(self) -> Literal[False]:
        return False


def _key(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).casefold()


def _focus_terms(focus) -> tuple[str, ...]:
    if focus is None:
        return ()
    terms = (focus,) if isinstance(focus, str) else focus
    return tuple(dict.fromkeys(_key(term) for term in terms if _key(term)))


def _focused(record: dict, terms: tuple[str, ...]) -> bool:
    if not terms:
        return False
    slots = record.get("slots", {})
    haystack = _key(" ".join((str(record.get("sentence", "")), *(str(v) for v in slots.values()))))
    return any(term in haystack for term in terms)


def _priority(record: dict):
    kind = record.get("kind")
    if kind == "TASK":
        state = _key(record.get("slots", {}).get("state"))
        if not state or state in _CLOSED_TASK_STATES:
            return None
    return _PRIORITY.get(kind)


def _witness_statuses(memory, records: list[dict]) -> dict[str, str]:
    verify = getattr(memory, "verify", None)
    if callable(verify):
        statuses = verify()
    else:
        statuses = {str(record.get("id", "")): check_witness(record.get("witness"))
                    for record in records}
    return {str(record.get("id", "")): str(statuses.get(str(record.get("id", "")), "UNVERIFIABLE"))
            for record in records}


def _askable(memory, record: dict) -> bool:
    """Check semantic retrievability through the public memory question path."""
    kind = record.get("kind")
    slots = record.get("slots", {})
    rid = str(record.get("id", ""))
    if not rid or not isinstance(slots, dict):
        return False
    subject = slots.get("subject") if kind != "LESSON" else slots.get("situation")
    if not subject:
        return False
    if kind == "FACT":
        attribute = slots.get("attribute")
    elif kind == "LESSON":
        attribute = "対処"
    else:
        attribute = None
    try:
        answer = memory.ask_about(subject, attribute, kind=kind, require_fresh=True)
    except (KeyError, TypeError, ValueError):
        return False
    return answer.get("verdict") == "ANSWER" and rid in {str(source) for source in answer.get("records", [])}


def _line(record: BriefRecord) -> str:
    return f"[id:{record.id}; witness:{record.witness_status}; context-only] {record.sentence}"


def _render(records: list[dict], selected: list[BriefRecord]) -> tuple[str, tuple[str, ...]]:
    selected_ids = {record.id for record in selected}
    dropped = tuple(str(record["id"]) for record in records if str(record["id"]) not in selected_ids)
    lines = [_line(record) for record in selected]
    if dropped:
        lines.append("Dropped record ids: " + ", ".join(dropped))
    return "\n".join(lines), dropped


def compile_brief(memory, budget_chars: int, focus=None) -> ContextBrief:
    """Return a typed context-only brief ranked by kind and focus, plus omitted IDs.

    Focused records rank ahead of nonmatching records; the fixed INVARIANT >
    DECISION > open TASK > LESSON > FACT order breaks ties. Character counts
    use Python string length. Each included citation keeps its witness status
    and is explicitly marked context-only; the result carries no evidence or
    answer authority. If the budget cannot report omitted IDs, compilation
    raises ``ValueError`` instead of hiding them.
    """
    if isinstance(budget_chars, bool) or not isinstance(budget_chars, int) or budget_chars < 0:
        raise ValueError("budget_chars must be a non-negative integer")

    superseded = getattr(memory, "superseded", {})
    records = [record for record in memory.active() if str(record.get("id", "")) not in superseded]
    if not records:
        return ContextBrief("", (), ())

    statuses = _witness_statuses(memory, records)
    terms = _focus_terms(focus)
    records.sort(key=lambda record: (
        0 if _focused(record, terms) else 1,
        _PRIORITY.get(record.get("kind"), len(_PRIORITY))
        if _priority(record) is not None else len(_PRIORITY),
        str(record.get("ts", "")),
        str(record.get("id", "")),
    ))
    askable = {str(record["id"]): _askable(memory, record)
               for record in records if _priority(record) is not None and record.get("sentence")}

    selected: list[BriefRecord] = []
    for record in records:
        rid = str(record.get("id", ""))
        if _priority(record) is None or not record.get("sentence") or not askable.get(rid, False):
            continue
        candidate = BriefRecord(rid, str(record.get("kind", "")), str(record["sentence"]), statuses[rid])
        trial = selected + [candidate]
        trial_text, _ = _render(records, trial)
        if len(trial_text) <= budget_chars:
            selected = trial

    brief, dropped = _render(records, selected)
    if len(brief) > budget_chars:
        raise ValueError("budget_chars is too small to report all dropped record IDs")
    return ContextBrief(brief, tuple(selected), dropped)
