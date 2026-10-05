# Stacked limits and determinism attack

Independent probes of `verantyx/stacked.py`'s `staged` path. The acceptance
run reported **8 passed, 1 xfailed**.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| SL-1 | robustness | `殺人罪 → → 停止`, with the first and last stages each scripted to one candidate and the last candidate linked to the first | Refuse the malformed chain with `None` or a typed `UNKNOWN` verdict | Returns `ANSWER_BY_STAGES`; the empty stage is discarded and the remaining two stages are treated as a valid chain. Captured as a non-strict xfail. |

## What held

- The 40-candidate stage-one boundary proceeded; 41 candidates returned
  `UNKNOWN_STAGE1_TOO_WIDE` with empty text.
- Intermediate stages handed every linked candidate forward. In the scripted
  three-stage case, that allowed the final stage to select its unique strict
  leader.
- Reversing candidate iteration order preserved the same sorted tie refusal:
  `UNKNOWN_UNDERDETERMINED`, candidates `left` and `right`, and empty text.
- Repeated calls returned equal results without mutating the store.
- Two concurrent readers returned equal results.
- A 96-stage chain completed with `ANSWER_BY_STAGES`.
- An arrowless 250,000-character query returned `None`.
- The memory check passed: after warming the parser, 200 calls retained less
  than the test's 128 KiB bound.

## Not covered

- These staging probes used scripted candidate sets and a small synthetic
  store; they do not validate real `Puzzle` candidate generation or a corpus
  backed `ask` call.
- Memory retention was checked for the scripted repeated-call case, not under
  process-wide memory pressure.
- Chains longer than 96 stages, candidate sets wider than 41, and wide
  candidate sets at later stages were not exercised.
