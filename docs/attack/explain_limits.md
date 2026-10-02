# `explain.py` limits attack

This attack exercises the constructed-explanation boundary in
`verantyx/explain.py`. `reach` and split discovery are controlled test doubles,
so these results concern the post-route logic in `explain`, not the integration
with a populated corpus.

## Findings

No defect was reproduced in the bounded checks. Each row records a property
that held in the acceptance run.

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| L1 | robustness | Return a `CONTAINMENT` route object | Pass the route through unchanged | Same object returned |
| L2 | robustness | Return `UNKNOWN_NO_REACH` for an empty term and a one-million-character term | Preserve the typed route without processing a unit split | Same route object returned for both |
| L3 | robustness | Explain two held units with shared facets | Mark output constructed and sort crossing facets | `EXPLAINED_BY_UNITS`, marker present, crossing sorted |
| L4 | robustness | Put an unworded facet in the crossing | Keep raw crossing recountable but do not speak that facet | Facet remains in payload and is absent from draft text |
| L5 | robustness | Intersect ten thousand facets, including a source label | Exclude labels and cap the raw crossing at eight facets | Eight sorted facets returned; label absent |
| L6 | robustness | Make the optional edge lookup raise | Retain the typed explanation without optional edge pairs | `EXPLAINED_BY_UNITS`; no `edge_pairs` field |
| L7 | robustness | Repeat the same explanation call | Produce an equal result each time | Results equal |
| L8 | robustness | Rebuild equivalent stores with reversed insertion order | Produce the same explanation | Results equal |
| L9 | robustness | Run two explanations over separate stores at the same time | Keep each reader's result tied to its own store | Each result contains only its store's crossing |
| L10 | robustness | Repeat a fixed explanation one thousand times | Avoid unbounded retained Python allocations | Retained allocation stayed below the test's 256 KiB threshold |

## What held

The acceptance command completed with eleven passed tests and no xfails. The
bounded checks preserved non-unit route objects, kept constructed content
typed, applied the vocabulary gate to spoken facets, bounded the crossing
payload, and showed repeatable results for the tested calls. Concurrent calls
over independent stores did not cross-contaminate their outputs.

## Not covered

- A real `reach` implementation or populated corpus store; route and split
  enumeration were replaced with controlled doubles.
- The lattice neighbourhood path, a successful edge lookup, or malformed
  custom store/vocabulary objects.
- Process resident memory, long-duration concurrency, or arbitrary callbacks
  that block indefinitely. The allocation check measures retained traced
  Python allocations for its bounded repeated-call probe only.
