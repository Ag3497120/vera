# Semantic measure fabrication attack

Scope: independent checks of `verantyx/semantic_measure.py` for source provenance and request-plan construction. The parser and request builder were tested directly; the request tests use a small recording builder to inspect the emitted IR structure.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| M1 | ungrounded | `raw = "箱Aは3kg"`; call `read_measure_sentence("src", raw, 7, 0, 6, True, "facts")` twice | Reject the invalid source window (or otherwise avoid creating a clause with a span outside the source). | Both calls returned one clause with `span=(start=7, end=6, text="")`; its `body_span` still covered `箱Aは3kg`. The xfail test records the reproduction. |

The finding concerns malformed caller offsets. It does not demonstrate an unsupported amount or entity for a valid source window.

## What held

- A complete two-segment sentence kept each entity, label, exact `Decimal` quantity, particle, and shared head noun attached to source spans.
- Negation remainder, unconsumed text, and a dangling list separator were rejected instead of being read as a complete measure sentence.
- Sum plans referenced the two bound mass values and retained the requested unit. Comparison plans used the requested measure dimension and relation, with choice labels tied to the bindings; same/different plans used equality or inequality and distinct-entity filtering.
- Acceptance command run: `/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_measure_fabrication.py` with the specified environment; result was **10 passed, 1 xfailed**.

## Not covered

- Executing generated plans against a record store, including stale or superseded record selection, ambiguity handling, and final answer rendering.
- Runtime unit conversion or aggregation behavior after plan construction.
- Other malformed offset combinations beyond the reproduced `start > right` case.
