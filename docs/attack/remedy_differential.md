# Remedy differential attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |

No mismatches were found in the covered contract cases, so there are no defect
repros or xfail tests.

## What held

- The independent reference agreed with `remedy` across the declared repair
  and routing verdicts, terminal verdicts, an unknown verdict, and generated
  combinations of verdict and context fields.
- `ANSWER*`, `SEEDED`, `AGREED`, `LEAD`, `ATTESTED`, and `COMPARISON` are
  returned as terminal outcomes with registration disabled.
- Typed routing refusals keep registration disabled; covered repair gaps
  request registration and retain their repair-specific guidance.
- Context fields are carried with a recorded repair when supplied with a
  truthy value. Terminal outcomes and unknown verdicts return early; for an
  unknown verdict, the documented fallback is “no remedy recorded” and does
  not create a contextual repair.

The acceptance command completed with **15 passed in 0.07s**:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. \
  /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q \
  tests/attack/test_remedy_differential.py
```

## What was not covered

- Inputs that are not mappings, exceptions from custom mapping implementations,
  or non-string values with unusual `__str__` behavior.
- Whether registering any proposed fact actually changes a downstream
  verdict, or whether factual claims and citations are grounded.
- Integration with the semantic path, memory, routing, or any external store.
- Performance or concurrent calls. This suite checks the pure remedy mapping
  only; it does not validate the empirical measurements written in the
  module's descriptions.
