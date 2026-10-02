# Conduct tree differential review

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| — | — | — | — | No discrepancies found in the covered cases; no defect is reported. |

## What held

- An independent, deliberately simple reference model matched `build`'s sorted fixed-width grouping and node names for the generated leaf counts in the test suite.
- The same comparison held for the tested configurable arities, and reversing mapping insertion order did not change the resulting grouping.
- Leaf values remained the original objects at the leaves, and a caller-supplied root name was retained.
- An out-of-corpus term and an out-of-corpus term sequence returned `UNKNOWN_NO_ROUTE` at the root with the prior trail preserved.
- Acceptance command: `VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_conduct_tree_differential.py` — **17 passed in 0.07s**.

## Coverage limits

- The reference model checks tree construction, not the exact face selection or conduction scores used by `surface.route`. Unknown-term abstention is checked from the conduct tree's stated contract; unique routed terms and tie outcomes are not differentially modeled.
- The hierarchy-backed/federated conversion path and its anchor surface-mass gate are not exercised.
- Very large trees, malformed leaf crosses, and arity values that cannot reduce a level are not covered; no performance claim is made from these small generated cases.
