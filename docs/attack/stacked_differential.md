# Stacked differential attack

## Findings

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| — | — | No disagreement found in the cases exercised | Staged intersections follow the documented hand-off and abstention rules | The acceptance run passed all 10 tests; 32 generated stage graphs agreed with the independent reference |

## What held

- A final-stage candidate with a strict link-count lead is returned as `ANSWER_BY_STAGES`; equal top link counts return `UNKNOWN_UNDERDETERMINED` with the tied candidates.
- A missing condition set returns the stage-specific `UNKNOWN_STAGE*_EMPTY` verdict. Candidates with no link to the prior survivors return `UNKNOWN_STAGES_DISCONNECTED`.
- The first and intermediate stages stop when more than 40 candidates would be handed forward. The width boundary case used 41 candidates.
- In the three-stage fixture, the intermediate linked set was handed forward without electing a winner there.
- The independent exact-membership reference agreed with `staged` on 32 deterministic generated graphs with 2–4 stages.

The acceptance command completed with **10 passed, 0 failed, 0 xfailed** in **0.08 seconds**.

## What I did not cover

- Real corpus stores, large-store timing, or generated terms whose matching depends on substring/coarsening behavior.
- The full `ask` route, `stage_split`, direct consensus, judging, or interactions with the other stacked helpers.
- A wrong-answer or fabrication claim. This run found no disagreement, and it does not establish that such failures are absent outside these synthetic cases.
