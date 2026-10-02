# Semantic route fabrication and provenance review

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| SRF-1 | robustness | Route an eight-leaf view for anchor `MiraNo`; an unread-only leaf contains `Mira No: contradiction here`. | Keep the unread span: the unread lookup removes whitespace before matching its character grams, and the span is considered an anchor mention. | The unread-only source is reached, but the span is omitted because the final filter requires literal `MiraNo` in the original text. The reproducer is marked xfail. |

No answer is emitted by this router, so this finding is a dropped-record risk rather than an observed wrong answer or fabrication.

## What held

- Routed sources, clauses, and unread records came from the input view; retained clauses and spans stayed intact.
- Separate documents containing the same anchor were kept together, including positive and negative clauses and mentions in a different role.
- Unrelated documents were excluded for a selective anchor. A common anchor fell back to the flat view, while a selective anchor still routed when another anchor was common.
- Anchor mentions in unread text and instruction spans on reached sources were preserved in the exercised cases. A request without entity anchors also fell back to the flat view.

## Test run

The required acceptance command completed with exit code 0: **9 passed, 1 xfailed in 0.09s**. The xfail is SRF-1.

## Not covered

- Whether a downstream producer or independent checker turns a routed view into an answer, or whether any resulting answer is supported.
- Semantic adjudication of stale or superseded records; the router only selects document leaves and does not determine which record wins.
- Large corpora, non-default tree arities, exhaustive cap boundaries, or real corpus documents. The probes use small constructed views.
