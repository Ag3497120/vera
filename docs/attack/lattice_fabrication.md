# Lattice fabrication and provenance attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| LF-1 | ungrounded | `build({"甲乙丙丁", "甲乙戊己"})`; inspect `kin(lat, "甲乙丙丁")` | No `甲乙@L` family: `甲乙` is neither a standalone input word nor an atomic character. The documented node rule excludes unattested fragments. | `kin` includes `甲乙@L: ["甲乙戊己"]`. The same output also includes an allowed `甲@L` family. Reproduced in two separate invocations; captured by the xfailed test `test_kin_does_not_use_an_unattested_multi_character_fragment`. |

## What held

- `build` kept words of lengths 2 through 12 and discarded shorter or longer strings.
- The documented `電荷密度` split appeared when both children were input words, and `analyze` marked those children as words.
- A short compound with unattested halves produced no split.
- A long-window split required both sides as words; the long-window case did not use a single-character half.
- `kin` kept left and right slots separate, excluded the queried word, and returned the left-slot family in deterministic order.
- `predict_facets` aggregated neighbor counts, omitted source labels and the query term as a facet, and did not return the target's own cross when it had no kin.

## What was not covered

- Freshness and supersession of records, role attribution, and preservation of negation. The lattice interface here takes words and a cross store; it exposes no record chronology or sentence-level provenance to attack.
- Integrity or coverage of a real corpus. The tests use small constructed vocabularies and an in-memory cross store.
- Exhaustive long-window cuts for every length from 6 through 12, or behavior in downstream explanation and answer components.

## Run

Acceptance command result: **9 passed, 1 xfailed**. The xfail is the confirmed ungrounded-fragment finding above; it is not a module fix.
