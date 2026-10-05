# Semantic reader differential check

## Method

The tests use small reference functions written independently of
`verantyx.semantic_reader`. They check exact quantity parsing, quote-aware
sentence boundaries, and a deliberately narrow nominal-copula grammar. The
copula cases compare the typed clause's predicate, polarity, and role terms
against values derived from the source string and the IR's quantity shape.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| — | — | — | — | No reproducible disagreement in the tested subset. |

The severity categories considered were `wrong-ANSWER`, `ungrounded`,
`crash`, `hang`, and `robustness`. No defect was reported, so there is no
minimal defect reproduction.

## What held

The required acceptance command completed with **54 passed**. The generated
cases agreed with the independent references for quantity parsing and
sentence splitting, and the fixed nominal-copula examples produced the
expected typed clauses.

## Not covered

The reference does not attempt general Japanese parsing. It does not check
frame and case-role extraction, coordination, tense, question plans, measure
sentences, conditions and exceptions, quotation or modality, or the reader's
handling of unsupported spans outside the tested sentence boundaries. The
results therefore describe only the bounded behaviors above; they do not
establish overall reader correctness.
