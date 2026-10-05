# Semantic route limits and determinism

Independent probes for `verantyx.semantic_route.LeafTree`. These tests exercise the router with constructed IR views; they do not run a producer or a proof checker.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| SRL-1 | hang | Build a `LeafTree` from seven one-clause documents with `arity=1`. | Construction returns promptly or refuses the unsupported arity in a controlled way. | Construction did not return before the test's two-second subprocess timeout. The reproducer is retained as a non-strict xfail. |

## What held

- Empty and below-minimum views, plus a request with no literal string anchor, return a `skipped` trace rather than raising.
- Every document with the requested literal anchor remains in the routed view. An unread span that mentions the anchor also retains its document.
- Reversing synthetic document input order and repeating the same call preserve the routed view and stable trace fields. Two concurrent readers of one tree matched serial results for separate requests.
- Routing was idempotent on a nine-document routed view. With the default anchor cap, 128 matching documents routed, while 129 matching documents caused a `skipped` result so the caller can keep the flat view.
- A synthetic 256-document view retained both anchor-holding documents and dropped unrelated leaves.

Acceptance command run from the worktree root with the required environment:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_route_limits.py
11 passed, 1 xfailed in 1.58s
```

## What was not covered

- The largest synthetic view was 256 documents; this does not establish runtime or memory bounds for very large corpora.
- The tests did not mutate a `View` or `LeafTree` during concurrent calls, exercise malformed objects outside the IR types, or test real corpus content.
- The router only selects a corpus subset. These probes do not establish answer correctness, proof-checker behavior, or end-to-end abstention.
