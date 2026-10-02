# Semantic unknown choice differential review

## Findings

| ID | Severity (wrong-ANSWER, ungrounded, crash, hang, robustness) | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| — | — | No discrepancy found in the covered cases. | Match the independent closed-choice reference. | The checked decisions and option inventories matched. |

## What held

- Candidate terms are drawn from candidate terms, units, family members, and options; frame vocabulary terms join the same closed list. Duplicate terms retain their candidate and frame origins. A queried term is omitted when it comes from the candidate but remains eligible when supplied as a frame term.
- The independent reference matched generated ordinary mapping reports. A selected option was adopted only when both asks agreed on a listed term. Empty inventories and reports outside `CANDIDATES` returned `NONE`; null, malformed, out-of-range, or disagreeing replies remained unresolved.
- Displayed options used JSON encoding, including for a term containing a line break and delimiters.
- An adopted choice was reused for the same term and option inventory. The tested correction path asked again and linked the replacement to the earlier record.
- Alias records were marked as testimony, while the returned candidate provenance remained explicitly outside evidence counts.

## Run

The required acceptance command completed with **9 passed**:

```sh
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. \
  /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q \
  tests/attack/test_semantic_unknown_choice_differential.py
```

## Not covered

The asker was a deterministic test double, so this review does not assess real model behavior, external data, or whether candidate-generation provenance is semantically correct. Inputs were ordinary mapping reports; alternate report objects and concurrent calls were not exercised. The review did not inspect or test neighboring semantic modules.
