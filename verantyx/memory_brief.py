"""Compile a deterministic, character-budgeted brief from typed memory."""
from __future__ import annotations

import unicodedata


_PRIORITY = {"INVARIANT": 0, "DECISION": 1, "TASK": 2, "LESSON": 3, "FACT": 4}
_CLOSED_TASK_STATES = {"完了", "done", "complete", "completed", "finished"}


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


def _askable(memory, record: dict) -> bool:
    """Use the public memory question path and require this record as a source."""
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
    return rid in {str(source) for source in answer.get("records", [])}


def _line(record: dict) -> str:
    return f"[id:{record['id']}] {record['sentence']}"


def _render(records: list[dict], selected: list[dict]) -> str:
    selected_ids = {str(record["id"]) for record in selected}
    lines = [_line(record) for record in selected]
    dropped = [str(record["id"]) for record in records if str(record["id"]) not in selected_ids]
    if dropped:
        lines.append("Dropped record ids: " + ", ".join(dropped))
    return "\n".join(lines)


def compile_brief(memory, budget_chars: int, focus=None) -> str:
    """Return askable record lines, ranked by kind and focus, plus omitted record IDs.

    Focused records rank ahead of nonmatching records; the fixed INVARIANT >
    DECISION > open TASK > LESSON > FACT order breaks ties. Character counts
    use Python string length. If the budget cannot even report the omitted
    IDs, compilation raises ``ValueError`` instead of hiding them.
    """
    if isinstance(budget_chars, bool) or not isinstance(budget_chars, int) or budget_chars < 0:
        raise ValueError("budget_chars must be a non-negative integer")

    superseded = getattr(memory, "superseded", {})
    records = [record for record in memory.active() if str(record.get("id", "")) not in superseded]
    if not records:
        return ""

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

    selected = []
    for record in records:
        rid = str(record.get("id", ""))
        if _priority(record) is None or not record.get("sentence") or not askable.get(rid, False):
            continue
        trial = selected + [record]
        if len(_render(records, trial)) <= budget_chars:
            selected = trial

    brief = _render(records, selected)
    if len(brief) > budget_chars:
        raise ValueError("budget_chars is too small to report all dropped record IDs")
    return brief
