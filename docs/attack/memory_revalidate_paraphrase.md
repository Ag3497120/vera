# Memory revalidation paraphrase attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| MR-P01 | robustness | Store `ルーター / 未読の上限 = 24` as a FACT, then call `ask()` with `ルーターの未読の上限は何ですか？` and `ルーターの未読の上限はいくつ？`. | Equivalent questions keep the same verdict. | First is `UNKNOWN_NO_EVIDENCE`; second is `UNKNOWN_UNREAD`. The difference is captured by a non-strict xfail. |

## What held

- `ask_about()` kept the `ANSWER` and value `24` for the stored slot and tested normalized forms: surrounding whitespace, an attached Japanese subject particle, and omission of `の` in the attribute.
- A changed entity or attribute returned `UNKNOWN_NO_EVIDENCE` with no value.
- Testimony remained answerable and was labeled `UNVERIFIABLE`.
- A matching local text witness was labeled `FRESH`; a missing needle was labeled `STALE`, and its record did not support an answer.
- The tested free-form question variants did not produce an `ANSWER` without a complete supported request.

## Run

Acceptance command result: **8 passed, 1 xfailed in 0.23s**.

## What was not covered

- This was a small Japanese surface-variant sample, not an exhaustive paraphrase or particle matrix.
- Free-form number and entity substitutions, `git_commit` witnesses, cache expiry and eviction, and concurrent reads were not exercised.
- The probes used one constructed FACT and temporary local witness files; they do not establish general answer quality or full-module correctness.
