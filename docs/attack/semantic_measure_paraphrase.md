# Semantic measure paraphrase attack

Independent surface-variant checks for `verantyx/semantic_measure.py`.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| None | — | — | — | No confirmed finding in the exercised cases. |

## What held

- Plain and polite measure sentences retained the same exact `Decimal` value and entity label.
- The supported particles `は`, `が`, `に`, and `も` retained the measure value and dimension.
- Reordering measure segments kept each entity attached to its own quantity. A shared head noun was attached to every measure clause.
- Sum-question plain and polite forms built a two-input `Sum` shape. Switching the requested unit from length to mass changed the bound dimension and output unit.
- The supported longer-question word orders built a greater-than comparison. Changing `長い` to `短い` changed the relation; `同じ` and `等しい` shared equality, while `違う` used inequality.
- Trailing unconsumed text in a measure sentence was left unread, and an unrecognized question produced no plan nodes.

The required acceptance command completed with **16 passed** and no xfails.

## What this did not cover

- The request tests use a recording builder to inspect the typed plan shape; they do not execute its operators or establish any final numerical or entity answer.
- Conversion and summation across different units, comparison ties, and integration with the rest of the semantic pipeline were not exercised.
- Paraphrases outside the module's closed structural patterns and non-measure question forms were not evaluated.
