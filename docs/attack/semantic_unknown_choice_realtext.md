# Semantic unknown choice: real text stress

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| DATA-1 | robustness | Call `tools.round5a_route_tune.load(8, 1)` in the unit environment. | The permitted training-split loader returns leads for the real-text probe. | It raised `FileNotFoundError` for its configured `jawiki_leads.full.jsonl` path before returning any rows. This is a data-availability limitation, not a defect attributed to `semantic_unknown_choice.py`. |

No wrong answer, ungrounded choice, module crash, or hang was established by the constructed-report probes. No xfails were needed. The severity-1 wrong-answer/fabrication path was therefore not reported.

## What held

The attack suite ran **11 tests: 11 passed in 0.14 seconds**. The probes showed that:

- adoption is restricted to listed candidate or frame terms and requires matching results from two asks;
- disagreement returns `UNRESOLVED`, while a non-candidate report or an empty option set returns `NONE` without asking;
- frame terms can be selected, duplicate terms retain both origins, and a cached alias is reused when the same option set arrives in a different order;
- superseding an adopted alias links the replacement record to the prior record;
- candidate provenance is returned separately, is not sent in the asks, and is marked `counts_as_evidence: false`; the adopted record has `support: testimony`;
- an option containing a line break remains a single JSON-quoted list item in the prompts.

These are rates for the 11 constructed contract probes only. The real-text rate is **not measurable**: the loader returned zero paragraphs, so no Wikipedia lead was passed to the module. The acceptance run used the unit interpreter and environment, with pytest's cache provider disabled to keep generated files out of the worktree.

## Not covered

- Real Wikipedia lead paragraphs, including crash, hang, wrong-answer, and ungrounded-output rates on that corpus.
- Candidate reports produced by upstream semantic extraction on real paragraphs.
- Long-running or concurrent use, and malformed objects outside the typed report/candidate contract.
