# Tense and time verifier attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| T1 | ungrounded | Source: `太郎は今年東京に行く。`; question: `太郎は東京に行くか` | Preserve `今年` as a time role or refuse the source clause before it supports a claim whose IR only records `nonpast`. | The source clause had no time role and no unsupported marker. `Checker._source` accepted it, and `Checker.audit` returned `可否=True` for the bare nonpast question. This shows the year qualifier can be dropped; it does not establish that every affirmative answer in this pattern is false. |

The T1 case is marked as a non-strict expected failure in the test suite so the missing qualifier remains visible without failing acceptance.

## What held

- A past event and a nonpast event were licensed with their corresponding IR tense values.
- Changing either source clause to the opposite tense was rejected by source licensing.
- Past and nonpast questions did not bind to sources with the opposite tense.
- A negated past event produced a negative value for a past `whether` question.
- The checker licensed `行っている` as nonpast and `行っていた` as past.
- A source with `昨日` that the reader marked unsupported was rejected.
- The order-specific `行ってから` question was unread rather than answered from an individual event clause.

## Run

Acceptance command completed with **11 passed, 1 xfailed**:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. PYTEST_ADDOPTS='-p no:cacheprovider' /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_verify_tense_time.py
```

## Not covered

- All Japanese relative date expressions, calendar systems, or explicit date formats.
- Duration and quantity expressions that contribute temporal scope.
- All aspect and auxiliary combinations, including interactions with quotation, modality, and conditions.
- Proof replay for every event-order construction; the order probe checked that the request was left unread.
