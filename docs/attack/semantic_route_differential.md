# Semantic route differential attack

## Findings

| id | severity (wrong-ANSWER / ungrounded / crash / hang / robustness) | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| No finding | n/a | n/a | No discrepancy in the checked behavior | No discrepancy observed in the checked behavior |

No defect was found in this scope, so no xfail reproducer was added.

## What held

- The independent flat reference agreed with `LeafTree.restrict` on 48 deterministic generated cases. Each case used one bind pattern, between 8 and 17 synthetic document leaves, and one to three literal role values. The reference intersects the holders of a pattern's usable literals, then compares the resulting source set.
- Focused checks confirmed that literals within one pattern intersect, separate patterns union, `attribute` and `Nominal` terms do not become string anchors, and all-common anchors keep the flat view.
- The checks confirmed the small-view skip, the selective-anchor behavior when another anchor is common, unread-span inclusion for an evidence document and a separate anchor mention, instruction-unread handling, and one rare-entity join hop.
- In the checked cases, the routed clauses were drawn from the input view.

Acceptance command, run with the unit's configured environment:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_route_differential.py
12 passed in 0.08s
```

## What was not covered

All inputs were synthetic `semantic_ir` objects. The differential reference covers the flat single-bind reach behavior; it does not model multi-hop expansion, conditions, exceptions, unread-text bigram collisions, cap fallback at scale, parser output, producer/checker proofs, or corpus behavior. The focused join test exercises one constructed hop but is not a differential reference for general join plans. No Wikipedia or other corpus data was loaded.
