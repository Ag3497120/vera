# Summarizer fabrication and provenance attack

Scope: `verantyx/summarize.py`, using constructed stores, vocabularies, and
edge lookups. The module treats the edge lookup as its sentence-edge source
and is responsible for emitting claims only among crossing facets.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| F1 | wrong-ANSWER | One stored subject `A` with facets `f,g`; pass `subjects=["A", "A"]`; edge lookup returns `(f,g)`. Repeated twice in the xfail test. | `UNKNOWN_TOO_FEW_PATHS`: the repeated identifier names one held path, so it cannot form a two-path crossing. | `SUMMARY`; duplicate holder entries make both facets appear shared, and the pair is emitted twice. |
| F2 | ungrounded | `A` has `f,g,private`, `B` has `f,g`; lookup receives the crossing facets and returns `(f,private)` for `A`. Repeated twice in the xfail test. | No claim; `private` is not a crossing facet, so no edge among the crossing facets is licensed. | `SUMMARY` includes `A: (f, private)` despite `private` being outside the crossing and lookup's requested facet set. |

Both defects are marked `xfail(strict=False)` so they remain visible without
failing the acceptance suite. The expected behavior follows the module's
documented two-or-more-subject crossing and edge-among-crossing-facets
contract, rather than copying its output.

## What held

The requested acceptance command completed with **9 passed and 2 xfailed**.
Passing checks covered typed refusals for too few paths, disjoint paths, and
missing/empty edge licences; a traceable licensed pair and its rendered line;
vocabulary silence; source-label and unheld-subject filtering; and whole-rank
group dropping at the limit.

## What I did not cover

The flat store interface exposes subject identifiers, facet counts, a vocab
gate, and an edge lookup. These tests cannot independently inspect sentence
text or establish semantic roles, entity identity, negation, supersession, or
partial-span correctness inside the source records. No corpus or external data
was used, and the summarizer implementation was not changed.
