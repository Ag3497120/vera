# `semantic_wh.py` tense and time attack

## Findings

No reportable defect was reproduced. The test run had no wrong answers or fabrications to repeat.

| ID | Severity (`wrong-ANSWER`, `ungrounded`, `crash`, `hang`, `robustness`) | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |

## What held

- Role-only wh questions and supported role-noun lists produced one wildcard pattern with the requested roles, labels, and variable order. Accepted examples included `誰が何を`, `誰が何をどこで誰にですか。`, and `渡した人、物、受取人は`.
- Questions containing past or nonpast predicate forms, relative time words, a date, a quantity, or event-order wording returned `None` and did not bind or project a role plan. Examples included `昨日誰が何を渡した？`, `今年、誰が何をした？`, `2026年に誰が何を渡した？`, and `誰が何をした後、誰に渡した？`.
- A time word alone and a single role did not produce a plan.

These expectations follow the module's role-only question contract: it returns `None` for another question shape and does not guess a predicate. Recognized cases were checked against the IR `Pattern("*", roles)` shape.

## Run

The required acceptance command completed with **15 passed** in **0.08s** on 2026-10-02; there were no xfails:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_wh_tense_time.py
15 passed in 0.08s
```

## What was not covered

- End-to-end question reading, retrieval, and answer generation; the reader was called directly with a small recording builder.
- Temporal interpretation or grounding by other modules, and behavior on corpus documents.
- Exhaustive Japanese tense/aspect, date, quantity, and event-order phrasing.
