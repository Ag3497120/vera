# Gap graph differential attack

The test suite compares `GapGraph` operations with a small independent, list-based reference model. A fixed random seed generates 120 create requests, including repeated `(scope, subject)` pairs with conflicting metadata. Other checks cover status transitions, FIFO selection, timestamp filtering, persistence, and the refusal-ledger adapter.

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| D1 | robustness | Create one default `DETECTED` node, then call `graph.actionable(limit=0)`. | An explicit limit of zero selects no nodes. | Returns every actionable node because zero is treated like an omitted limit. |

D1 has a non-strict xfail reproduction in the test file. It does not produce an answer or testimony.

## What held

- All 120 generated create requests matched the independent `(scope, subject)` reuse model; duplicate calls retained the first node's fields.
- Invalid severity and status values were rejected without adding nodes.
- Valid status changes, optional resolution updates, verifier accumulation, and unknown-ID lookup matched the contract.
- Actionable filtering returned only the three forward-progress states, in oldest-first order; a positive limit matched the reference slice.
- `since(ts)` included nodes at the timestamp boundary and matched the generated reference projection.
- Save/load preserved all typed fields, and legacy rows received the documented defaults. A missing file loaded as an empty graph.
- Unresolved refusal recording was idempotent for a query; resolution changed the matching node to `RESOLVED`, and repeated or unmatched resolution was a no-op.
- The graph path helper returned a sibling `gap_graph.json` path.

The required acceptance command completed with **11 passed, 1 xfailed** in **0.12 seconds**.

## Not covered

- The classifier, router hooks, heartbeat resolution loop, quarantine gates, and end-to-end answer path were not exercised; this attack is limited to `gap_graph.py`'s data layer.
- Concurrent writers, malformed but syntactically valid JSON shapes, filesystem permission failures, and large stores were not tested.
- The work did not inspect or use development, sealed, heldout, or external data, and it did not change the module under test.
