"""Typed, non-answer explanations for terms outside a semantic View.

The semantic proof path remains closed over source clauses.  This adapter
hands the existing View-local unknown/explain route to a separate generated
surface and keeps any closed-choice alias as testimony beside it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

from .explain import CONSTRUCTED_MARK
from .semantic_unknown import (
    Family,
    UnitProvenance,
    UnknownCandidate,
    UnknownReport,
    unknown_candidates,
)
from .semantic_unknown_choice import SemanticUnknownChoice


@dataclass(frozen=True)
class OutsideConstruction:
    """A structural candidate with its source-resolvable lineage."""

    kind: str
    term: str
    units: tuple[str, ...]
    provenance: tuple[UnitProvenance, ...]
    families: tuple[Family, ...]
    reason: str
    constructed: Literal[True] = True
    evidence: Literal[False] = False
    answer: Literal[False] = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "term": self.term,
            "units": list(self.units),
            "provenance": [_plain(item) for item in self.provenance],
            "families": [_plain(item) for item in self.families],
            "reason": self.reason,
            "constructed": self.constructed,
            "evidence": self.evidence,
            "answer": self.answer,
        }


@dataclass(frozen=True)
class GeneratedOutsideText:
    """A marked display surface, separate from the semantic answer path."""

    text: str
    constructed: Literal[True] = True
    evidence: Literal[False] = False
    answer: Literal[False] = False
    derivation: str = "semantic_generate:outside-structure"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "constructed": self.constructed,
            "evidence": self.evidence,
            "answer": self.answer,
            "derivation": self.derivation,
        }


@dataclass(frozen=True)
class OutsideResult:
    """Result of the out-of-frame hand-over; it is never an ANSWER."""

    term: str
    status: str
    reason: str
    generated: GeneratedOutsideText
    construction: Optional[OutsideConstruction]
    choice: Optional[dict[str, Any]] = None
    testimony: Optional[dict[str, Any]] = None
    adopted_term: Optional[str] = None
    constructed: Literal[True] = True
    evidence: Literal[False] = False
    answer: Literal[False] = False
    route: Literal["OUTSIDE_CONSTRUCTION"] = "OUTSIDE_CONSTRUCTION"

    @property
    def text(self) -> str:
        return self.generated.text

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route,
            "term": self.term,
            "status": self.status,
            "reason": self.reason,
            "generated": self.generated.to_dict(),
            "construction": (self.construction.to_dict()
                             if self.construction is not None else None),
            "choice": _plain(self.choice),
            "testimony": _plain(self.testimony),
            "adopted_term": self.adopted_term,
            "constructed": self.constructed,
            "evidence": self.evidence,
            "answer": self.answer,
        }


def _plain(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return _plain(value.to_dict())
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {name: _plain(getattr(value, name))
                for name in value.__dataclass_fields__}
    return value


def _spans_resolve(view: Any, candidate: UnknownCandidate) -> bool:
    sources = getattr(view, "sources", None)
    if not isinstance(sources, dict):
        return False
    for item in candidate.provenance:
        if not item.clauses:
            return False
        for clause_span in item.clauses:
            span = clause_span.span
            raw = sources.get(span.source)
            if (not isinstance(raw, str) or span.start < 0
                    or span.end <= span.start or span.end > len(raw)
                    or raw[span.start:span.end] != span.text):
                return False
    return True


def _construction(candidate: UnknownCandidate) -> OutsideConstruction:
    return OutsideConstruction(
        kind=candidate.kind,
        term=candidate.term,
        units=tuple(candidate.units),
        provenance=tuple(candidate.provenance),
        families=tuple(candidate.families),
        reason=candidate.reason,
    )


def _split_order(term: str, units: tuple[str, ...]) -> tuple[str, str] | None:
    if len(units) < 2:
        return None
    for left, right in ((units[0], units[1]), (units[1], units[0])):
        if left + right == term:
            return left, right
    return None


def _generated_text(term: str, status: str,
                    construction: OutsideConstruction | None,
                    choice: dict[str, Any] | None) -> GeneratedOutsideText:
    if construction is None:
        if status == "CANDIDATES":
            body = f"{term}について、このViewから構成的な経路を得られませんでした。"
        elif status == "KNOWN_TERM":
            body = "構成的説明の対象外です（KNOWN_TERM）。"
        else:
            body = f"{term}の構成的説明は保留です（{status}）。"
    elif construction.kind == "EXPLAINED_BY_UNITS":
        ordered = _split_order(term, construction.units)
        if ordered:
            body = f"{term}は、{ordered[0]}と{ordered[1]}に分解されます。"
        elif construction.units:
            body = f"{term}は、{construction.units[0]}を単位に含む構造候補です。"
        else:
            body = f"{term}の単位分解候補です。"
    elif construction.kind == "KIN_NEIGHBOURHOOD":
        groups = []
        for family in construction.families:
            slot = getattr(family, "slot", "")
            members = tuple(getattr(family, "members", ()))
            if slot and members:
                groups.append(f"{slot}の近傍（{'、'.join(members[:4])}）")
        if groups:
            body = f"{term}は、" + "；".join(groups) + "にある近傍候補です。"
        else:
            body = f"{term}の近傍候補です。"
    else:
        body = f"{term}について、このViewから説明経路を確認できませんでした。"

    if choice:
        if choice.get("decision") == "ADOPT" and isinstance(choice.get("option"), str):
            body += (f" 閉じた候補選択の証言: {choice['option']}。"
                     "この記録は構成候補を変更しません。")
        elif choice.get("decision") == "UNRESOLVED":
            body += " 閉じた候補選択は未解決のため採用していません。"
    return GeneratedOutsideText(body + CONSTRUCTED_MARK)


def _frame_terms(view: Any) -> tuple[str, ...]:
    terms: list[str] = []
    for clause in getattr(view, "clauses", ()):
        for role in getattr(clause, "roles", ()):
            value = getattr(role, "term", None)
            if isinstance(value, str) and value and value not in terms:
                terms.append(value)
        predicate = getattr(clause, "predicate", None)
        if isinstance(predicate, str) and predicate and predicate not in terms:
            terms.append(predicate)
    return tuple(terms)


def explain_outside(view: Any, term: str, asker: Any = None) -> OutsideResult:
    """Explain an unheld term as marked construction, never a source answer.

    ``asker`` is an injected closed-choice callback. Its two independently
    worded asks may select only candidate or View terms; an adopted result is
    returned as testimony and is not used to rewrite the construction.
    """
    if not isinstance(term, str):
        raise TypeError("term must be a string")

    report = unknown_candidates(view, term)
    raw = report.candidates[0] if report.candidates else None
    status = report.status
    reason = report.reason
    invalid_provenance = (raw is not None and raw.kind != "NO_REACH"
                          and not _spans_resolve(view, raw))
    if invalid_provenance:
        raw = None
        status = "ABSTAIN_INVALID_PROVENANCE"
        reason = "candidate source spans did not resolve against the View"
    candidate = _construction(raw) if raw is not None else None

    selected: dict[str, Any] | None = None
    if asker is not None and not invalid_provenance:
        choice_result = SemanticUnknownChoice(asker).choose(report, _frame_terms(view))
        selected = choice_result
    else:
        choice_result = None

    adopted = (selected.get("option")
               if selected and selected.get("decision") == "ADOPT" else None)
    record = selected.get("alias_record") if selected else None
    testimony = (record if isinstance(record, dict)
                 and record.get("status") == "ADOPT"
                 and record.get("support") == "testimony" else None)
    generated = _generated_text(term, status, candidate, selected)
    return OutsideResult(
        term=term,
        status=status,
        reason=reason,
        generated=generated,
        construction=candidate,
        choice=selected,
        testimony=testimony,
        adopted_term=adopted,
    )
