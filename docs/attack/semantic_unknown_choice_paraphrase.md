# Semantic unknown choice: paraphrase attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| PAR-01 | wrong-ANSWER | Adopt `widget` for `flarn` while the report is `CANDIDATES`; call again with the same term and options but status `NO_CANDIDATES`. | Return `NONE`, as required by the status gate. | Returns the cached `ADOPT widget` record without asking again. Reproduced in two direct runs; retained as an expected-failure test. |

## What held

- Five polite/plain and word-order surface forms produced the same selected candidate when both scripted Resolver asks selected it.
- The chooser adopted a frame-vocabulary term and mapped the selection to an option in the closed set.
- Disagreement and two null replies stayed `UNRESOLVED`; a report outside `CANDIDATES` returned `NONE` when no alias was cached.
- The stored record marked adoption as testimony, candidate provenance did not count as evidence, escaped line breaks stayed inside the query's JSON string, and reordering the frame vocabulary reused the alias.

The required acceptance command completed with **14 passed, 1 xfailed** in **0.16 seconds**. The expected failure is PAR-01.

## Not covered

- No live or stochastic model asker was used. The scripted asker selected a requested option from the closed-choice prompt, so these checks exercise prompt construction and response routing rather than independently judging paraphrase meaning.
- No production `UnknownReport` generation path, broader language coverage, or corpus-scale behavior was exercised.
- The changed-number/entity probe checks that a changed selected option is routed through; it does not establish that an asker will infer the intended number or entity meaning.
