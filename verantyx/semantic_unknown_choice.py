"""Closed-choice wiring from constructed unknown candidates to frame terms.

The Resolver may select only terms already present in a candidate or the
question frame. Candidate provenance is returned separately and never enters
the ask. An adopted mapping is stored as testimony, not as semantic evidence.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any, Callable, Literal, Optional

from .memory_frame import Resolver
from .semantic_unknown import UnknownReport


Decision = Literal["ADOPT", "NONE", "UNRESOLVED"]


def _get(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, Mapping):
        return value.get(name, default)
    return getattr(value, name, default)


def _plain(value: Any) -> Any:
    """Convert the typed provenance records to ordinary JSON-shaped values."""
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {name: _plain(getattr(value, name))
                for name in value.__dataclass_fields__}
    return value


def _as_terms(values: Iterable[Any]) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise TypeError("frame_vocabulary must be an iterable of terms")
    terms: list[str] = []
    for value in values:
        if not isinstance(value, str):
            raise TypeError("frame vocabulary terms must be strings")
        if value and value.strip() and value not in terms:
            terms.append(value)
    return terms


def _candidate_terms(candidate: Any, unknown: str) -> list[str]:
    terms: list[str] = []

    def add(value: Any) -> None:
        if isinstance(value, str) and value and value.strip() and value != unknown and value not in terms:
            terms.append(value)

    # A distinct candidate term is useful for alternate candidate types. The
    # current UnknownCandidate.term repeats the queried unknown and is omitted.
    add(_get(candidate, "term"))
    for unit in (_get(candidate, "units", ()) or ()):
        add(unit)
    for family in (_get(candidate, "families", ()) or ()):
        for member in (_get(family, "members", ()) or ()):
            add(member)
    for option in (_get(candidate, "options", ()) or ()):
        add(option)
    return terms


def _evidence(report: Any) -> list[dict[str, Any]]:
    result = []
    for index, candidate in enumerate(_get(report, "candidates", ()) or ()):
        result.append({
            "candidate_index": index,
            "kind": _get(candidate, "kind"),
            "constructed": bool(_get(candidate, "constructed", True)),
            "counts_as_evidence": False,
            "provenance": _plain(_get(candidate, "provenance", ()) or ()),
        })
    return result


class SemanticUnknownChoice:
    """Resolve an unknown against constructed terms and a question frame.

    ``supersede_alias`` is the explicit correction path when a user or caller
    rejects an earlier adopted alias. All asks still go through Resolver.
    """

    def __init__(self, asker: Callable[[str], str], seed: int = 7):
        self.resolver = Resolver(asker, seed=seed)
        self.aliases: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}
        self.alias_history: list[dict[str, Any]] = []
        self._next_id = 1

    @staticmethod
    def _options(report: Any, frame_vocabulary: Iterable[Any]) -> tuple[list[str], dict[str, list[str]]]:
        unknown = _get(report, "term", "")
        if not isinstance(unknown, str):
            raise TypeError("UnknownReport.term must be a string")
        candidates = _get(report, "candidates", ()) or ()
        origins: dict[str, list[str]] = {}
        for candidate in candidates:
            for term in _candidate_terms(candidate, unknown):
                origins.setdefault(term, [])
                if "candidate" not in origins[term]:
                    origins[term].append("candidate")
        for term in _as_terms(frame_vocabulary):
            origins.setdefault(term, [])
            if "frame" not in origins[term]:
                origins[term].append("frame")
        return list(origins), origins

    @staticmethod
    def _key(report: Any, options: list[str]) -> tuple[str, tuple[str, ...]]:
        return str(_get(report, "term", "")), tuple(sorted(options))

    def choose(self, report: UnknownReport, frame_vocabulary: Iterable[str]) -> dict[str, Any]:
        """Return a typed decision, an adopted option if any, and provenance."""
        return self._choose(report, frame_vocabulary, supersedes=None, force=False)

    __call__ = choose

    def supersede_alias(self, report: UnknownReport,
                        frame_vocabulary: Iterable[str]) -> dict[str, Any]:
        """Re-ask after an adopted alias was judged wrong, linking its replacement."""
        frame_terms = _as_terms(frame_vocabulary)
        options, _ = self._options(report, frame_terms)
        old = self.aliases.pop(self._key(report, options), None)
        return self._choose(report, frame_terms, supersedes=old, force=True)

    def _choose(self, report: UnknownReport, frame_vocabulary: Iterable[str], *,
                supersedes: Optional[dict[str, Any]], force: bool) -> dict[str, Any]:
        options, origins = self._options(report, frame_vocabulary)
        evidence = _evidence(report)
        key = self._key(report, options)

        if not force and key in self.aliases:
            record = self.aliases[key]
            return {"decision": "ADOPT", "option": record["choice"],
                    "alias_record": record, "evidence": evidence}

        if _get(report, "status") != "CANDIDATES":
            return {"decision": "NONE", "option": None,
                    "alias_record": None, "evidence": evidence}
        if not options:
            return {"decision": "NONE", "option": None,
                    "alias_record": None, "evidence": evidence}

        # JSON strings keep untrusted line breaks and delimiters inside one
        # displayed list item. Source spans and candidate reasons are omitted.
        shown = [json.dumps({"term": term, "from": origins[term]}, ensure_ascii=False,
                            sort_keys=True) for term in options]
        query = json.dumps(_get(report, "term", ""), ensure_ascii=False)
        result = self.resolver.resolve(
            query, shown,
            "Choose only among these constructed terms and question-frame terms.",
        )
        shown_choice = result.get("choice")
        reverse = dict(zip(shown, options))
        option = reverse.get(shown_choice) if result.get("status") == "ADOPT" else None
        decision: Decision
        if result.get("status") == "ADOPT" and option is not None:
            decision = "ADOPT"
        else:
            # A null choice is not evidence that no relation exists; abstain.
            decision = "UNRESOLVED"
            option = None

        record = {
            "id": f"semantic-unknown-alias-{self._next_id}",
            "op": "alias",
            "scope": "semantic_unknown",
            "word": _get(report, "term", ""),
            "choice": option,
            "status": decision,
            "asks": _plain(result.get("asks", [])),
            "by": "llm-closed-choice",
            "support": "testimony",
            "supersedes": supersedes.get("id") if supersedes else None,
        }
        self._next_id += 1
        self.alias_history.append(record)
        if decision == "ADOPT":
            self.aliases[key] = record

        return {"decision": decision, "option": option,
                "alias_record": record, "evidence": evidence}


def choose_unknown(report: UnknownReport, frame_vocabulary: Iterable[str],
                   asker: Callable[[str], str], *, seed: int = 7) -> dict[str, Any]:
    """One-shot convenience wrapper; use SemanticUnknownChoice to reuse aliases."""
    return SemanticUnknownChoice(asker, seed=seed).choose(report, frame_vocabulary)
