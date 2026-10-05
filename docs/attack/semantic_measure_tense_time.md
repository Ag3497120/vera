# Semantic measure tense and time attack

## Findings

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| T1 | ungrounded | `Aは3m、後日Bは4mです` | Decline the temporal sequence as outside the pure measure shape, or retain `後日` as a temporal qualifier. | Two `measure.length` clauses are returned. The second has entity `後日B`, kind `後日`, label `B`, and no time role. The xfail records this classification. |

No wrong answer or fabricated answer was demonstrated. The finding concerns the reader's typed interpretation; this attack did not exercise a downstream answer path.

## What held

- Past plain, past copular, polite past, and change-of-state aspect forms are declined instead of being read as timeless measures.
- Relative-time text before a measurement, a date embedded before a unit, and temporal prefixes on measure questions are declined by the closed shapes tested here.
- The decimal literal `0.10` is retained as a `Decimal` with its input scale.
- Acceptance run: 11 passed and 1 xfailed in 0.09 seconds.

## What was not covered

This attack did not test sentence segmentation before `read_measure_sentence`, routing, coordination, measure execution, or end-to-end answer generation. It did not establish how a later stage handles temporal evidence, dates attached through other constructions, or the observed `後日` kind role. No heldout, sealed, or development data was used.
