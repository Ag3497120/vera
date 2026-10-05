# Gap graph limits and determinism attack

This attack exercised `verantyx/gap_graph.py` through its public `GapGraph`
and `refusal_to_gap` interfaces. The required acceptance run reported 17
passed and 2 xfailed.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| GGL-01 | robustness | Create an actionable node, then call `graph.actionable(limit=0)` (`test_actionable_zero_limit_returns_no_nodes`). | A zero-item limit returns an empty list. | The node is returned. The implementation treats zero as if no limit was supplied. |
| GGL-02 | crash | Write `[]` to a JSON file, then call `GapGraph.load(path)` (`test_load_parseable_non_mapping_payload_returns_empty_graph`). | Invalid stored graph data is handled as an empty graph, consistent with the loader's fallback for invalid JSON. | `AttributeError` escapes when the loader calls `.items()` on the parsed list. |

Both defect reproducers are marked `xfail(strict=False)` so the attack suite
remains green while the defects remain visible.

## What held

- Empty graphs return no actionable or recent nodes.
- Creating the same scope and subject reuses the original node; the same
  subject in different scopes gets distinct nodes.
- Unknown severities and statuses raise `ValueError`.
- Actionable nodes are returned oldest first, verified nodes are excluded,
  and a positive limit is honored. Repeated actionable reads do not mutate
  node fields.
- `since` includes a node whose update timestamp equals the boundary.
- Save/load preserves the node fields exercised, and saving an unchanged
  graph again produces the same text. Missing files and syntactically invalid
  JSON load as empty graphs.
- An unresolved refusal handoff reuses its node; resolving it is repeatable,
  and a subsequent unresolved handoff reuses the resolved node without
  reopening it.
- Two concurrent readers returned the same ordered result for a graph with
  80 nodes. Repeating a duplicate create 100 times left one node in the graph.

## Not covered

This attack did not profile heap usage or exercise very large graphs or large
JSON files. It did not test concurrent writers, multiple processes sharing a
file, equal `created_at` tie ordering, negative limits, or malformed
individual node records inside an otherwise valid JSON mapping. The reader
concurrency check establishes repeatable results for this case, not general
thread safety.
