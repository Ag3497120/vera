# Semantic coordination limits

This attack checks the tuple-based helpers in `verantyx/semantic_coord.py` against that module's coordination, chunk, and phrase-boundary contract. Expected values below come from those rules: a role span must respect token boundaries, and invalid coordination candidates are refusals.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| SC-LIM-01 | robustness | `phrase_bounded([("ククル", "名詞", "一般", "", 0, 3)], 1, 2)` | Reject a span whose start and end cut through the token. | Returns `True`; the xfailed reproducer remains visible in the suite. |
| SC-LIM-02 | crash | `coordination_ok([("歩き", "動詞", "自立", "連用形", 0, 2)], [99, 100])` | Refuse the invalid candidate with `False`, without throwing. | Raises `IndexError`; the xfailed reproducer remains visible in the suite. |

Neither finding is classified as a wrong answer: this unit does not exercise downstream answer generation or evidence handling.

## What held

- Te-plus-comma chains and renyō-plus-comma chains were accepted, while an adversative particle and a non-renyō first predicate were refused.
- Topic extraction and second-clause subject checks stayed within their respective token chunks.
- A phrase at chunk start was accepted, and a phrase beginning after an unseparated noun was refused.
- `tag` preserved the supplied token features and character offsets for paired inputs.
- Empty and single-predicate coordination inputs returned `False`.
- A 2,000-predicate chain returned the expected positive result. Repeated calls over two alternating inputs, scheduled across two worker threads, produced stable results.

## Not covered

- Parser or reader integration, including two independent reader instances and their tokenization behavior.
- Sustained memory-growth or timing benchmarks. The large-chain case is a bounded functional check, not a resource-budget measurement; these helpers expose no budget argument.
- Downstream answer generation, evidence attribution, corpus behavior, or very large unbounded inputs.

## Acceptance run

The required command completed with **11 passed, 2 xfailed** in **0.09s**. The xfails are the two reproductions above.
