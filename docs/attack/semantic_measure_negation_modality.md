# Semantic measure negation and modality attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| SMNM-01 | ungrounded | `read_measure_sentence("attack", "Aは3m?", 0, 0, 5, "attack", "measure")` | Return `None` so the question is left unread rather than recorded as a measure assertion. | Repeated twice: each call returned a `measure.length` clause with `Quantity(Decimal('3'), 'm')`, `polarity='+'`, and `modality='assert'`. The regression test is marked xfail. |

## What held

- The asserted sentence `Aは3mです。` was read as one `measure.length` clause.
- Simple negation, double negation, and the negative adjective `重くない` were not read as measure facts.
- Obligation, permission, prohibition, and hearsay forms were not read as measure facts.
- The positive comparison question `どちらが長いですか？` was recognized.
- Negated sum, comparison, and same/different question forms were not expanded into requests.
- The declarative comparison `Aは長い方です。` was not expanded as a request.

## What was not covered

This attack did not cover other source labels, units, numeric boundaries, multi-measure sentences, same/different positive questions, or question forms outside the examples above. It did not exercise downstream routing, answering, or refusal behavior.

## Run

The required acceptance command completed with **16 passed, 1 xfailed** in **0.09 seconds**.
