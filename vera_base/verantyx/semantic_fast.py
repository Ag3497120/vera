"""Shared stereo-cross index for semantic-view selection.

The index is a read-only projection of a View.  Its conductive tree selects
source leaves; immutable postings then select clauses or source documents
inside those leaves.  The three adapters below share this one projection and
never build a second view-wide index.

Views are normally replaced when ingestion changes them.  Container identity,
container size, and an optional ``version``/``revision`` stamp are checked on
each query.  Call ``invalidate`` after an in-place edit that leaves those
values unchanged.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from . import conduct_tree


_GRAM_PREFIX = "\x00semantic-fast-gram:"


def _field_stamp(value: Any) -> tuple[int, int]:
    try:
        size = len(value)
    except (TypeError, AttributeError):
        size = -1
    return id(value), size


def _view_stamp(view: Any) -> tuple[Any, ...]:
    """A constant-time change token for the ordinary immutable View shape."""
    version = next((getattr(view, name) for name in
                    ("version", "revision", "generation", "updated_at")
                    if hasattr(view, name)), None)
    return (id(view), _field_stamp(getattr(view, "sources", None)),
            _field_stamp(getattr(view, "clauses", None)),
            _field_stamp(getattr(view, "unread", None)), version)


def _surface_terms(clause: Any) -> tuple[str, ...]:
    terms: set[str] = set()

    def add(term: Any) -> None:
        if isinstance(term, str) and term:
            terms.add(term)
        elif isinstance(getattr(term, "head", None), str) and term.head:
            terms.add(term.head)

    for role in getattr(clause, "roles", ()):
        add(getattr(role, "term", None))
    for pattern in (*getattr(clause, "conditions", ()),
                    *getattr(clause, "exceptions", ())):
        for name, term in getattr(pattern, "roles", ()):
            if name != "attribute":
                add(term)
    predicate = getattr(clause, "predicate", None)
    if isinstance(predicate, str) and predicate:
        terms.add(predicate)
    return tuple(sorted(terms))


def _role_terms(clause: Any) -> tuple[str, ...]:
    out = set()
    for role in getattr(clause, "roles", ()):
        term = getattr(role, "term", None)
        if isinstance(term, str) and term:
            out.add(term)
    return tuple(sorted(out))


def _query_values(values: Iterable[str] | str) -> tuple[str, ...]:
    if isinstance(values, str):
        values = (values,)
    return tuple(dict.fromkeys(value for value in values
                               if isinstance(value, str) and value))


def _grams(text: str) -> frozenset[str]:
    if not text:
        return frozenset()
    if len(text) == 1:
        return frozenset((_GRAM_PREFIX + "1:" + text,))
    return frozenset(_GRAM_PREFIX + "2:" + text[i:i + 2]
                     for i in range(len(text) - 1))


def _occurs_in_span(view: Any, span: Any, unit: str) -> tuple[tuple[str, int, int], ...]:
    sources = getattr(view, "sources", {})
    source = getattr(span, "source", None)
    if source not in sources:
        return ()
    raw = sources[source]
    start = getattr(span, "start", -1)
    end = getattr(span, "end", -1)
    if type(start) is not int or type(end) is not int or start < 0 or end < start or end > len(raw):
        return ()
    found = []
    pos = start
    while True:
        at = raw.find(unit, pos, end)
        if at < 0:
            break
        found.append((source, at, at + len(unit)))
        pos = at + 1
    return tuple(found)


@dataclass(frozen=True)
class _IndexState:
    view: Any
    stamp: tuple[Any, ...]
    clauses: tuple[Any, ...]
    sources: Mapping[str, str]
    by_term: Mapping[str, tuple[int, ...]]
    by_role_term: Mapping[str, tuple[int, ...]]
    by_source: Mapping[str, tuple[int, ...]]
    by_gram: Mapping[str, tuple[int, ...]]
    role_by_gram: Mapping[str, tuple[str, ...]]
    source_by_term: Mapping[str, frozenset[str]]
    tree: Any
    built_ms: float


class SharedIndex:
    """A single source-leaf index shared by unknown, summary, and realize.

    Build once with ``SharedIndex(view)`` and retain the object for all three
    adapters.  Query methods only read immutable state, so concurrent reads
    need no query lock.  A rebuild is serialized and published as one state.
    """

    def __init__(self, view: Any):
        self.view = view
        self._lock = threading.RLock()
        self._invalid = False
        self._state = self._build(view)
        self._build_count = 1
        self.unknown = UnknownIndexAdapter(self)
        self.summary = SummaryIndexAdapter(self)
        self.realize = RealizeIndexAdapter(self)

    @staticmethod
    def _build(view: Any) -> _IndexState:
        started = time.perf_counter()
        clauses = tuple(getattr(view, "clauses", ()))
        sources = dict(getattr(view, "sources", {}) or {})
        by_term: dict[str, list[int]] = defaultdict(list)
        by_role: dict[str, list[int]] = defaultdict(list)
        by_source: dict[str, list[int]] = defaultdict(list)
        by_gram: dict[str, set[int]] = defaultdict(set)
        role_by_gram: dict[str, set[str]] = defaultdict(set)
        source_by_term: dict[str, set[str]] = defaultdict(set)
        leaves: dict[str, dict[str, dict[str, int]]] = {}

        for pos, clause in enumerate(clauses):
            span = getattr(clause, "span", None)
            source = getattr(span, "source", None)
            if isinstance(source, str) and source:
                by_source[source].append(pos)
                leaf = leaves.setdefault(source, {})
            else:
                leaf = None

            terms = _surface_terms(clause)
            role_terms = _role_terms(clause)
            for term in terms:
                by_term[term].append(pos)
                if isinstance(source, str) and source:
                    source_by_term[term].add(source)
                    if leaf is not None:
                        facet = getattr(clause, "predicate", None)
                        if not isinstance(facet, str) or not facet:
                            facet = term
                        cross = leaf.setdefault(term, {})
                        cross[facet] = cross.get(facet, 0) + 1
            for term in role_terms:
                by_role[term].append(pos)
                for gram in _grams(term):
                    role_by_gram[gram].add(term)

            spans = [span] if span is not None else []
            spans.extend(getattr(role, "span", None)
                         for role in getattr(clause, "roles", ()))
            for item in spans:
                text = getattr(item, "text", "")
                if isinstance(text, str):
                    for gram in _grams(text):
                        by_gram[gram].add(pos)

        # Unread spans have no clause posting, but their source leaf remains
        # visible to document selection, matching the routed view's boundary.
        for unread in getattr(view, "unread", ()):
            span = getattr(unread, "span", None)
            source = getattr(span, "source", None)
            text = getattr(span, "text", "")
            if isinstance(source, str) and source:
                leaves.setdefault(source, {})
                if isinstance(text, str):
                    for gram in _grams(text):
                        leaf = leaves[source]
                        cross = leaf.setdefault(gram, {})
                        cross["<unread>"] = cross.get("<unread>", 0) + 1

        tree = conduct_tree.build(leaves) if leaves else None
        built_ms = (time.perf_counter() - started) * 1000
        return _IndexState(
            view, _view_stamp(view), clauses, MappingProxyType(sources),
            MappingProxyType({k: tuple(v) for k, v in by_term.items()}),
            MappingProxyType({k: tuple(v) for k, v in by_role.items()}),
            MappingProxyType({k: tuple(v) for k, v in by_source.items()}),
            MappingProxyType({k: tuple(sorted(v)) for k, v in by_gram.items()}),
            MappingProxyType({k: tuple(sorted(v)) for k, v in role_by_gram.items()}),
            MappingProxyType({k: frozenset(v) for k, v in source_by_term.items()}),
            tree, built_ms,
        )

    def invalidate(self) -> None:
        """Mark the current projection stale after a caller's in-place edit."""
        with self._lock:
            self._invalid = True

    def is_current(self, view: Any | None = None) -> bool:
        target = self.view if view is None else view
        return (target is self.view and not self._invalid
                and self._state.stamp == _view_stamp(target))

    def refresh(self, view: Any | None = None) -> "SharedIndex":
        """Rebuild after a detected change, or bind this index to a new View."""
        target = self.view if view is None else view
        with self._lock:
            if target is not self.view:
                self.view = target
                self._invalid = True
            if self._invalid or self._state.stamp != _view_stamp(target):
                self._state = self._build(target)
                self._build_count += 1
                self._invalid = False
        return self

    def _read(self) -> _IndexState:
        if not self.is_current():
            self.refresh()
        return self._state

    @property
    def build_ms(self) -> float:
        return self._read().built_ms

    @property
    def build_count(self) -> int:
        self._read()
        return self._build_count

    @staticmethod
    def _ordered(state: _IndexState, positions: Iterable[int]) -> tuple[Any, ...]:
        return tuple(state.clauses[i] for i in sorted(set(positions)))

    def clauses_for_terms(self, terms: Iterable[str], *, match: str = "any",
                          roles_only: bool = False) -> tuple[Any, ...]:
        state = self._read()
        index = state.by_role_term if roles_only else state.by_term
        queries = _query_values(terms)
        if not queries:
            return ()
        if match not in ("any", "all"):
            raise ValueError("match must be 'any' or 'all'")
        groups = [set(index.get(term, ())) for term in queries]
        positions = set.union(*groups) if match == "any" else set.intersection(*groups)
        return self._ordered(state, positions)

    candidate_clauses = clauses_for_terms

    def documents_for_terms(self, terms: Iterable[str], *, match: str = "any") -> tuple[str, ...]:
        state = self._read()
        return self._document_names(state, terms, match=match)

    candidate_documents = documents_for_terms

    @staticmethod
    def _document_names(state: _IndexState, terms: Iterable[str], *,
                        match: str = "any") -> tuple[str, ...]:
        queries = _query_values(terms)
        if not queries:
            return ()
        if match not in ("any", "all"):
            raise ValueError("match must be 'any' or 'all'")
        sets: list[set[str]] = []
        for term in queries:
            # The conductive tree is the document lookup path for the same
            # exact surfaces used by LeafTree. Predicate-only postings remain
            # available through the companion source posting.
            found = None
            if state.tree is not None:
                found, _visited = _tree_reach(state.tree, term)
            if found is None:
                found = set(state.source_by_term.get(term, ()))
            sets.append(set(found))
        if match == "any":
            found_sources = set.union(*sets)
        elif match == "all":
            found_sources = set.intersection(*sets)
        else:
            raise ValueError("match must be 'any' or 'all'")
        return tuple(sorted(source for source in found_sources if source in state.sources))

    def document_texts_for_terms(self, terms: Iterable[str], *,
                                 match: str = "any") -> Mapping[str, str]:
        state = self._read()
        names = self._document_names(state, terms, match=match)
        return MappingProxyType({name: state.sources[name] for name in names})

    def clauses_for_units(self, units: Iterable[str]) -> tuple[Any, ...]:
        """Candidate clauses whose source spans may contain every requested unit."""
        state = self._read()
        queries = _query_values(units)
        if not queries:
            return ()
        positions: set[int] | None = None
        for unit in queries:
            grams = _grams(unit)
            if not grams:
                return ()
            candidates: set[int] | None = None
            for gram in grams:
                posting = set(state.by_gram.get(gram, ()))
                candidates = posting if candidates is None else candidates & posting
                if not candidates:
                    break
            if candidates is None:
                candidates = set()
            positions = candidates if positions is None else positions & candidates
            if not positions:
                return ()
        # Gram overlap only narrows. Exact substring validation keeps the
        # adapter's candidate set equal to the flat span search.
        return self._ordered(state, (i for i in (positions or ())
                                   if all(_clause_has_unit(state.view, state.clauses[i], u)
                                          for u in queries)))

    def clauses_for_unit(self, unit: str) -> tuple[Any, ...]:
        return self.clauses_for_units((unit,))

    def role_terms_containing(self, unit: str) -> tuple[str, ...]:
        """Indexed substring lookup over semantic role terms."""
        state = self._read()
        grams = _grams(unit)
        if not grams:
            return ()
        terms: set[str] | None = None
        for gram in grams:
            posting = set(state.role_by_gram.get(gram, ()))
            terms = posting if terms is None else terms & posting
            if not terms:
                return ()
        return tuple(sorted(term for term in (terms or ()) if unit in term))

    def documents_for_clauses(self, clauses: Iterable[Any]) -> Mapping[str, str]:
        """Return source documents referenced by clauses, preserving source order."""
        state = self._read()
        names = set()
        if hasattr(clauses, "span"):
            clauses = (clauses,)
        for clause in clauses:
            source = getattr(getattr(clause, "span", None), "source", None)
            if isinstance(source, str) and source in state.sources:
                names.add(source)
        return MappingProxyType({name: state.sources[name] for name in sorted(names)})

    def clauses_for_document(self, source: str) -> tuple[Any, ...]:
        state = self._read()
        return self._ordered(state, state.by_source.get(source, ()))

    def clause_ids_for_units(self, units: Iterable[str]) -> frozenset[str]:
        return frozenset(getattr(clause, "id", "")
                         for clause in self.clauses_for_units(units)
                         if isinstance(getattr(clause, "id", None), str))

    def stats(self) -> dict[str, Any]:
        state = self._read()
        return {"documents": len(state.sources), "clauses": len(state.clauses),
                "terms": len(state.by_term), "unit_grams": len(state.by_gram),
                "builds": self._build_count, "build_ms": state.built_ms}


def _tree_reach(tree: Any, term: str) -> tuple[set[str] | None, int]:
    """Apply LeafTree's conductive reach rule to the SharedIndex tree."""
    found: set[str] = set()
    visited = 0

    def walk(node: Any) -> None:
        nonlocal visited
        visited += 1
        for arm, child in node.children.items():
            if term not in node.profile[arm]:
                continue
            if isinstance(child, conduct_tree.Node):
                walk(child)
            else:
                found.add(getattr(node, "leaf_names", {}).get(arm, arm))

    walk(tree)
    return found, visited


def _clause_has_unit(view: Any, clause: Any, unit: str) -> bool:
    span = getattr(clause, "span", None)
    if _occurs_in_span(view, span, unit):
        return True
    return any(_occurs_in_span(view, getattr(role, "span", None), unit)
               for role in getattr(clause, "roles", ()))


class UnknownIndexAdapter:
    """Indexed source lookup for semantic_unknown unit and kin exploration."""

    def __init__(self, index: SharedIndex):
        self.index = index

    def unit_clauses(self, units: str | Iterable[str], *,
                     match: str = "any") -> tuple[Any, ...]:
        if isinstance(units, str):
            return self.index.clauses_for_unit(units)
        values = _query_values(units)
        if match == "all":
            return self.index.clauses_for_units(values)
        if match != "any":
            raise ValueError("match must be 'any' or 'all'")
        positions = {}
        for unit in values:
            for clause in self.index.clauses_for_unit(unit):
                positions.setdefault(id(clause), clause)
        return tuple(positions.values())

    def clauses_by_unit(self, units: Iterable[str]) -> Mapping[str, tuple[Any, ...]]:
        return MappingProxyType({unit: self.index.clauses_for_unit(unit)
                                 for unit in _query_values(units)})

    def unit_documents(self, units: Iterable[str]) -> Mapping[str, str]:
        clauses = self.unit_clauses(units)
        return self.index.documents_for_clauses(clauses)

    def kin_clauses(self, term: str, units: Iterable[tuple[str, str]], *,
                    min_unit: int = 1) -> Mapping[str, tuple[Any, ...]]:
        """Find clauses holding positional neighbours for ``(unit, L|R)`` slots."""
        result = {}
        for unit, position in units:
            if len(unit) < min_unit or position not in ("L", "R"):
                continue
            matching_terms = tuple(candidate for candidate in
                                   self.index.role_terms_containing(unit)
                                   if candidate != term and
                                   ((position == "L" and candidate.startswith(unit))
                                    or (position == "R" and candidate.endswith(unit))))
            kept = self.index.clauses_for_terms(matching_terms, roles_only=True)
            if kept:
                result[f"{unit}@{position}"] = tuple(kept)
        return MappingProxyType(result)


class SummaryIndexAdapter:
    """Candidate clause and document selection for summary/generate paths."""

    def __init__(self, index: SharedIndex):
        self.index = index

    def clauses(self, subjects: Iterable[str]) -> tuple[Any, ...]:
        return self.index.clauses_for_terms(subjects, roles_only=True)

    def documents(self, subjects: Iterable[str]) -> tuple[str, ...]:
        return self.index.documents_for_terms(subjects)


class RealizeIndexAdapter:
    """Document selection for realization from selected clauses or anchors."""

    def __init__(self, index: SharedIndex):
        self.index = index

    def documents_for_clauses(self, clauses: Iterable[Any]) -> Mapping[str, str]:
        return self.index.documents_for_clauses(clauses)

    def documents_for_terms(self, terms: Iterable[str], *, match: str = "any") -> Mapping[str, str]:
        return self.index.document_texts_for_terms(terms, match=match)


def shared_index(view: Any) -> SharedIndex:
    """Construct a per-view index; callers pass the result among their adapters."""
    return SharedIndex(view)


__all__ = ["SharedIndex", "UnknownIndexAdapter", "SummaryIndexAdapter",
           "RealizeIndexAdapter", "shared_index"]
