# Memory lesson paraphrase attack

The attack tests `LessonIndex` and `lessons_for` with small in-memory typed records. The expected matches below follow the attack premise that the paraphrases express the stored situation; the changed-trigger controls expect a separate verdict or abstention.

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| P1 | robustness | Store `train delay`; query `  TRAIN   DELAY  ` | Return the `train delay` lesson | `[]` |
| P2 | robustness | Store `train delay`; query `Could you advise me about a train delay?` | Return the `train delay` lesson | `[]` |
| P3 | robustness | Store `train delay`; query `delay on a train` | Return the `train delay` lesson | `[]` |
| P4 | robustness | Store `lost key`; query `lost keys` | Return the `lost key` lesson | `[]` |
| P5 | robustness | Store `train delay`; query `bus delay` | Return the shared delay lesson | `[]` |
| P6 | robustness | Retrieve a lesson, mutate its nested `slots.lesson`, then retrieve again | The retained lesson stays unchanged | The second retrieval contains the caller's mutation |

P1–P5 are abstentions for same-situation surface variants, not wrong answers. P6 is an index-isolation issue. No severity-1 wrong answer or fabrication was observed, so none is reported.

## What held

- Exact trigger lookup returned the matching lesson.
- The Japanese particle variant `電車の遅延` / `電車が遅延` returned the same lesson.
- `train delay` and the changed-meaning trigger `train cancellation` returned their separate lessons.
- An unmatched `train schedule`, `missed connection`, or blank situation abstained without an asker.
- Non-LESSON records were ignored and an explicitly superseded lesson was not returned.

The acceptance command run from the worktree root completed with **8 passed, 6 xfailed** (0.16 seconds). The xfails retain the six reproductions above.

## What I did not cover

- Resolver-backed lookups with an injected asker, including disagreement, tie, and invalid-choice behavior.
- Other paraphrases, languages, entity types, or interaction with persisted `Memory` records.
- Any wrong-answer case; the changed-meaning controls did not return the neighboring lesson.
