# Gap graph fabrication and provenance attack

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| A1 | robustness | Create one actionable node, then call `graph.actionable(limit=0)`. | An explicit zero limit returns an empty list. | The call returns the one actionable node. `test_actionable_zero_limit_returns_no_nodes` records this as a non-strict xfail. |

No wrong-ANSWER or unsupported-answer finding was observed in the inspected module: its API stores gap records and does not produce answers.

## What held

- Unresolved refusal records retained the exact query text, including negation and a partial-span example, along with verdict, branch, and allowed-source labels.
- Scope and subject matching kept different query/file scopes distinct, and resolving one query left a second query's refusal untouched.
- Resolution metadata named the supplied branch; attempting to resolve a missing query did not create a record.
- `GapNode.as_dict()` / `from_dict()` preserved the tested provenance, typed fields, and transition fields.
- Actionable selection excluded a blocked node and returned eligible nodes oldest first. Unknown severity and status values were rejected.

## Not covered

- Disk persistence and malformed persisted records were not exercised.
- The audit did not inspect callers, verify that allowed-source labels point to genuine source records, or test any larger semantic IR integration.
- No answer-producing behavior exists in the inspected API, so this run cannot establish end-to-end answer traceability.

## Run

Acceptance command completed with **10 passed, 1 xfailed** in **0.09s**:

```text
/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_gap_graph_fabrication.py
```

The run used the unit environment (`VERA_CORPUS_ROOT=/tmp/vera-empty-materials`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONPATH=.`) and disabled pytest's cache provider to keep generated files out of the worktree.
