"""View-local, constructed routes for terms no semantic clause holds.

The older reach, lattice, and explain helpers consume a small ``crosses`` /
``source_labels`` interface. A semantic View is not a CrossStore, so this
module builds that interface from the View's clause roles and builds its
lexicon from the View's own role terms and source text. A source that produced
a clause term cannot attest that same term; another source must contain the
normal three standalone occurrences. If the View has no such attestation,
the older explain path abstains. The lattice uses only vocabulary-approved
terms. It needs no external corpus or prebuilt CrossStore. Results are typed
hand-over candidates: they are always marked constructed, never testimony,
and never evidence.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from typing import Literal, Tuple

from . import explain as _explain
from . import lattice as _lattice
from .granularity import decompose_units
from .semantic_ir import Span, View
from .vocabulary import Vocabulary, attest, runs


CandidateKind = Literal[
    "EXPLAINED_BY_UNITS", "KIN_NEIGHBOURHOOD", "NO_REACH",
]
ReportStatus = Literal[
    "KNOWN_TERM", "CANDIDATES", "ABSTAIN_BARE_SUFFIX_SPLIT",
    "ABSTAIN_SPLIT_TIED", "ABSTAIN_UNIT_NOT_A_WORD", "BUDGET_REFUSAL",
]


@dataclass(frozen=True)
class ClauseSpan:
    clause_id: str
    span: Span

    def to_dict(self) -> dict:
        return {
            "clause_id": self.clause_id,
            "span": {
                "source": self.span.source,
                "start": self.span.start,
                "end": self.span.end,
                "text": self.span.text,
            },
        }


@dataclass(frozen=True)
class UnitProvenance:
    unit: str
    clauses: Tuple[ClauseSpan, ...]

    def to_dict(self) -> dict:
        return {"unit": self.unit,
                "clauses": [clause.to_dict() for clause in self.clauses]}


@dataclass(frozen=True)
class Family:
    slot: str
    members: Tuple[str, ...]

    def to_dict(self) -> dict:
        return {"slot": self.slot, "members": list(self.members)}


@dataclass(frozen=True)
class UnknownCandidate:
    kind: CandidateKind
    term: str
    units: Tuple[str, ...]
    provenance: Tuple[UnitProvenance, ...]
    reason: str
    constructed: Literal[True] = True
    evidence: Literal[False] = False
    families: Tuple[Family, ...] = ()

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "term": self.term,
            "units": list(self.units),
            "provenance": [item.to_dict() for item in self.provenance],
            "reason": self.reason,
            "constructed": self.constructed,
            "evidence": self.evidence,
            "families": [family.to_dict() for family in self.families],
        }


@dataclass(frozen=True)
class UnknownReport:
    status: ReportStatus
    term: str
    candidates: Tuple[UnknownCandidate, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "term": self.term,
            "candidates": [candidate.to_dict()
                           for candidate in self.candidates],
            "reason": self.reason,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True)


@dataclass
class _ViewCrosses:
    crosses: dict[str, Counter]
    source_labels: set[str]


def _view_store(view: View, role_terms: set[str]) -> _ViewCrosses:
    """Project co-occurring role terms into the old helpers' read interface."""
    crosses = {term: Counter() for term in role_terms}
    for clause in view.clauses:
        terms = sorted({role.term for role in clause.roles
                        if isinstance(role.term, str) and role.term})
        for term in terms:
            for other in terms:
                if other != term:
                    crosses[term][other] += 1
    return _ViewCrosses(crosses, set())


def _independent_vocabulary(
    view: View,
    candidates: set[str],
    corpora: list[tuple[str, str]],
) -> Vocabulary:
    """Attest each term only from sources that did not produce that facet."""
    producers: dict[str, set[str]] = {}
    for clause in view.clauses:
        clause_source = (clause.span.source
                         if clause.span.source in view.sources else "")
        for role in clause.roles:
            if not isinstance(role.term, str) or not role.term:
                continue
            source = (role.span.source if role.span.source in view.sources
                      else clause_source)
            if source:
                producers.setdefault(role.term, set()).add(source)
        if isinstance(clause.predicate, str) and clause.predicate:
            source = (clause.predicate_span.source
                      if clause.predicate_span.source in view.sources
                      else clause_source)
            if source:
                producers.setdefault(clause.predicate, set()).add(source)

    grouped: dict[frozenset[str], set[str]] = {}
    for term in candidates:
        excluded = frozenset(producers.get(term, ()))
        grouped.setdefault(excluded, set()).add(term)

    vocab = Vocabulary()
    for excluded, terms in sorted(
            grouped.items(), key=lambda item: tuple(sorted(item[0]))):
        independent = [corpus for corpus in corpora
                       if corpus[0] not in excluded]
        checked = attest(terms, independent)
        for term, by_source in checked.attested.items():
            for source, count in by_source.items():
                vocab.add(term, source, count)
    return vocab


def _unit_provenance(view: View, unit: str) -> UnitProvenance:
    found: dict[tuple[str, str, int, int], ClauseSpan] = {}
    for clause in view.clauses:
        locations: set[tuple[str, int, int]] = set()
        base = clause.span
        if base.valid(view.sources):
            raw = view.sources[base.source]
            pos = base.start
            while True:
                start = raw.find(unit, pos, base.end)
                if start < 0:
                    break
                end = start + len(unit)
                locations.add((base.source, start, end))
                pos = start + 1
        for role in clause.roles:
            span = role.span
            if span.valid(view.sources) and unit in span.text:
                raw = view.sources[span.source]
                pos = span.start
                while True:
                    start = raw.find(unit, pos, span.end)
                    if start < 0:
                        break
                    end = start + len(unit)
                    locations.add((span.source, start, end))
                    pos = start + 1
        for source, start, end in locations:
            span = Span(source, start, end, view.sources[source][start:end])
            found[(clause.id, source, start, end)] = ClauseSpan(clause.id, span)
    ordered = tuple(found[key] for key in sorted(found))
    return UnitProvenance(unit, ordered)


def _candidate(
    view: View,
    *,
    kind: CandidateKind,
    term: str,
    units: tuple[str, ...] = (),
    reason: str,
    families: tuple[Family, ...] = (),
) -> UnknownCandidate:
    provenance = tuple(_unit_provenance(view, unit) for unit in units)
    return UnknownCandidate(kind, term, units, provenance, reason,
                            families=families)


def _budget_refusal(term: str) -> UnknownReport:
    return UnknownReport(
        "BUDGET_REFUSAL", term, (),
        "the View projection exceeds the non-negative integer work budget",
    )


def unknown_candidates(
    view: View,
    term: str,
    budget: int = 256,
) -> UnknownReport:
    """Build constructed candidates for a term no clause holds.

    ``budget`` limits the number of source clauses, role terms, and distinct
    source words projected into the local vocabulary. An abstention carries
    the exact typed reason used by ``explain.py``; only the three candidate
    kinds above can be returned.
    """
    if not isinstance(term, str):
        raise TypeError("term must be a string")
    if type(budget) is not int or budget < 0:
        return _budget_refusal(term)
    if budget == 0:
        return _budget_refusal(term)

    role_terms = {
        role.term for clause in view.clauses for role in clause.roles
        if isinstance(role.term, str) and role.term
    }
    if (term in role_terms
            or any(clause.predicate == term for clause in view.clauses)):
        return UnknownReport(
            "KNOWN_TERM", term, (),
            "a semantic clause already holds this term",
        )

    source_counts: Counter = Counter()
    corpora = []
    for source in sorted(view.sources):
        counts = runs(view.sources[source])
        source_counts.update(counts)
        corpora.append((source, view.sources[source]))
    work = (len(view.clauses)
            + sum(len(clause.roles) for clause in view.clauses)
            + len(source_counts) + 1)
    if work > budget:
        return _budget_refusal(term)

    source_words = set(source_counts)
    terms = role_terms | source_words
    vocab = _independent_vocabulary(view, terms, corpora)

    store = _view_store(view, role_terms)
    model = decompose_units(terms)
    lat = _lattice.build(vocab.attested)
    result = _explain.explain(store, term, model=model, vocab=vocab, lat=lat)
    verdict = result.get("verdict")

    if verdict == "EXPLAINED_BY_UNITS":
        units = tuple(unit["part"] for unit in result.get("units", ()))
        candidate = _candidate(
            view, kind="EXPLAINED_BY_UNITS", term=term, units=units,
            reason="the View's positional unit structure licenses this split; "
                   "the result is constructed, not source testimony",
        )
        if any(not item.clauses for item in candidate.provenance):
            candidate = _candidate(
                view, kind="NO_REACH", term=term,
                reason="a valid source clause span was not available for every unit",
            )
            return UnknownReport("CANDIDATES", term, (candidate,),
                                 "constructed no-reach candidate")
        return UnknownReport("CANDIDATES", term, (candidate,),
                             "constructed explanation candidate")

    if verdict == "KIN_NEIGHBOURHOOD":
        raw_families = result.get("families", {})
        families = tuple(
            Family(slot, tuple(members))
            for slot, members in sorted(raw_families.items())
        )
        units = tuple(sorted({family.slot.rsplit("@", 1)[0]
                              for family in families}))
        candidate = _candidate(
            view, kind="KIN_NEIGHBOURHOOD", term=term, units=units,
            families=families,
            reason="the View has positional neighbours sharing these units; "
                   "this is a neighbourhood, not a meaning",
        )
        if any(not item.clauses for item in candidate.provenance):
            candidate = _candidate(
                view, kind="NO_REACH", term=term,
                reason="a valid source clause span was not available for every unit",
            )
            return UnknownReport("CANDIDATES", term, (candidate,),
                                 "constructed no-reach candidate")
        return UnknownReport("CANDIDATES", term, (candidate,),
                             "constructed neighbourhood candidate")

    if verdict == "UNKNOWN_NO_REACH":
        candidate = _candidate(
            view, kind="NO_REACH", term=term,
            reason="no licensed unit decomposition or kin neighbourhood "
                   "was found in this View",
        )
        return UnknownReport("CANDIDATES", term, (candidate,),
                             "constructed no-reach candidate")

    abstentions = {
        "ABSTAIN_BARE_SUFFIX_SPLIT": "ABSTAIN_BARE_SUFFIX_SPLIT",
        "ABSTAIN_SPLIT_TIED": "ABSTAIN_SPLIT_TIED",
        "ABSTAIN_UNIT_NOT_A_WORD": "ABSTAIN_UNIT_NOT_A_WORD",
    }
    if verdict in abstentions:
        return UnknownReport(abstentions[verdict], term, (),
                             result.get("note", "the older explain path abstained"))

    # HELD is ruled out by the clause-held check above; containment is not
    # enabled in this View-local projection and must not be promoted.
    candidate = _candidate(
        view, kind="NO_REACH", term=term,
        reason="the View did not yield a constructed route",
    )
    return UnknownReport("CANDIDATES", term, (candidate,),
                         "constructed no-reach candidate")
