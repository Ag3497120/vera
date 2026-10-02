# Semantic reader attack: tense and time

Scope: constructed Japanese examples for `verantyx.semantic_reader`. The checks cover past/nonpast event marking, relative time words, date-like values, and age questions. They do not evaluate downstream answer generation.

Acceptance run: `9 passed, 4 xfailed`. The ungrounded observations below were reproduced in two separate probe runs.

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| TT-01 | robustness | `ユンは今年の代表だ。` | Keep the relative-year scope explicit as unread or unsupported; do not emit a clean timeless clause. | Emitted an identity clause with empty time and unsupported fields, value `今年の代表`, and no unread span. |
| TT-02 | ungrounded | `ユンは技師だった。`; `ユンは技師ではなかった。` | Preserve past time and polarity, or keep the past copula unread. | Both became clean identity clauses with empty time. The negative example had positive polarity and kept `ではなかった` inside the value literal. |
| TT-03 | ungrounded | `ユンは2024年技師だ。` | Keep the date-like construction explicitly time-scoped or unread; do not invent a quantity unit from the following noun. | Emitted a clean identity clause whose value was `Quantity(2024, 年技師)`, with no unsupported marker or unread span. |

## What held

- `運ぶ` in nonpast and `運んだ` in past event clauses receive different time tags.
- A past auxiliary in the compound `受け取った` is retained; past event negation is represented separately from tense.
- Copulas containing `現在` or `以前` carry the reader's unsupported-time marker.
- Age questions scoped by `今年`, `以前`, or an explicit year become typed unread requests with no answer plan.

## What was not covered

- Other date formats, ambiguous calendar values, or all Japanese relative-time expressions.
- Ordering and simultaneity across clauses, or reference times carried across sentences.
- Aspect distinctions such as progressive versus habitual readings.
- Execution of request plans or whether downstream components refuse to answer these claims.
