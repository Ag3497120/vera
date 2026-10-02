"""Synthetic flat-versus-SharedIndex benchmark and equality demo."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from verantyx.semantic_fast import SharedIndex


@dataclass(frozen=True)
class Span:
    source: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class Role:
    term: str
    span: Span


@dataclass(frozen=True)
class Clause:
    id: str
    predicate: str
    span: Span
    roles: tuple[Role, ...]
    conditions: tuple = ()
    exceptions: tuple = ()


@dataclass(frozen=True)
class View:
    sources: dict[str, str]
    clauses: tuple[Clause, ...]
    unread: tuple = ()
    version: int = 1


def make_view(count: int) -> View:
    sources = {}
    clauses = []
    for number in range(count):
        source = f"doc-{number:05d}"
        topic = f"topic-{number % 97:02d}"
        marker = f"marker-{number % 11:02d}"
        entity = f"entity-{number:05d}"
        text = f"{entity} {topic} {marker} supports {topic}"
        sources[source] = text
        span = Span(source, 0, len(text), text)
        roles = (Role(entity, span), Role(topic, span), Role(marker, span))
        clauses.append(Clause(f"c-{number:05d}", "supports", span, roles))
    return View(sources, tuple(clauses))


def flat_documents(view: View, terms: tuple[str, ...]) -> set[str]:
    wanted = set(terms)
    out = set()
    for clause in view.clauses:
        held = {role.term for role in clause.roles}
        held.add(clause.predicate)
        if held & wanted:
            out.add(clause.span.source)
    return out


def flat_clauses(view: View, terms: tuple[str, ...], *, roles_only=False) -> set[str]:
    wanted = set(terms)
    out = set()
    for clause in view.clauses:
        held = {role.term for role in clause.roles}
        if not roles_only:
            held.add(clause.predicate)
        if held & wanted:
            out.add(clause.id)
    return out


def flat_unit_clauses(view: View, units: tuple[str, ...]) -> set[str]:
    out = set()
    for clause in view.clauses:
        spans = (clause.span, *(role.span for role in clause.roles))
        if all(any(unit in span.text for span in spans) for unit in units):
            out.add(clause.id)
    return out


def timed(call, repeats: int) -> float:
    started = time.perf_counter()
    for _ in range(repeats):
        call()
    return (time.perf_counter() - started) * 1000 / repeats


def run() -> None:
    print("docs  flat-ms/query  indexed-ms/query  speedup")
    for count in (300, 1000, 4000):
        view = make_view(count)
        index = SharedIndex(view)
        queries = tuple((f"topic-{n:02d}",) for n in (0, 7, 17, 31, 54, 96))
        queries += ((f"entity-{count // 2:05d}",), ("absent-term",), ("supports",))

        for query in queries:
            expected = flat_documents(view, query)
            actual = set(index.documents_for_terms(query))
            assert actual == expected, (count, "document candidates", query)
            flat_ids = flat_clauses(view, query)
            indexed_ids = {clause.id for clause in index.clauses_for_terms(query)}
            assert indexed_ids == flat_ids, (count, "clause candidates", query)

        summary_terms = ("topic-07", "marker-03")
        flat_summary = flat_clauses(view, summary_terms, roles_only=True)
        indexed_summary = {
            clause.id for clause in index.summary.clauses(summary_terms)
        }
        assert indexed_summary == flat_summary, (count, "summary clauses")

        unit_queries = (("entity-",), ("topic-07",), ("marker-03", "supports"))
        for units in unit_queries:
            expected = flat_unit_clauses(view, units)
            actual = {clause.id for clause in
                      index.unknown.unit_clauses(units, match="all")}
            assert actual == expected, (count, "unit clauses", units)
            expected_by_unit = {unit: flat_unit_clauses(view, (unit,))
                                for unit in units}
            actual_by_unit = {
                unit: {clause.id for clause in clauses}
                for unit, clauses in index.unknown.clauses_by_unit(units).items()
            }
            assert actual_by_unit == expected_by_unit, (count, "unit postings", units)

        selected = index.summary.clauses(summary_terms)
        flat_sources = {clause.span.source for clause in view.clauses
                        if clause.id in flat_summary}
        indexed_sources = set(index.realize.documents_for_clauses(selected))
        assert indexed_sources == flat_sources, (count, "realize documents")

        concurrent_queries = ("topic-17", "marker-03", "supports", "absent-term")
        with ThreadPoolExecutor(max_workers=4) as pool:
            concurrent = list(pool.map(index.documents_for_terms,
                                       concurrent_queries))
        expected_concurrent = [tuple(sorted(flat_documents(view, (term,))))
                               for term in concurrent_queries]
        assert concurrent == expected_concurrent, (count, "concurrent reads")
        assert index.build_count == 1, (count, "index rebuilt during reads")

        view.sources["extra-document"] = ""
        assert not index.is_current(), (count, "stale view was not detected")
        assert set(index.documents_for_terms("topic-17")) == flat_documents(
            view, ("topic-17",))
        assert index.is_current(), (count, "stale view was not rebuilt")
        assert index.build_count == 2, (count, "stale view rebuild count")

        repeats = 5 if count < 1000 else 3
        query = ("topic-17",)
        flat_ms = timed(lambda: flat_documents(view, query), repeats)
        indexed_ms = timed(lambda: index.documents_for_terms(query), repeats)
        speedup = flat_ms / indexed_ms if indexed_ms else float("inf")
        print(f"{count:4d}  {flat_ms:12.3f}  {indexed_ms:16.3f}  {speedup:7.2f}x")

    print("DEMO OK")


if __name__ == "__main__":
    run()
