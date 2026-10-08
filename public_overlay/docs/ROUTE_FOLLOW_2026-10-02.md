# Semantic route entity following

The route walk now passes terms onward from a clause only when that clause contains a term on the current frontier and its predicate is one the request asks about. During join rounds, the matching clause can pass its terms to the next hop. During guard rounds, it can pass only its condition and exception terms. This keeps a document that mentions an anchor for another reason from injecting its unrelated vocabulary into the walk.

The regression suite builds its own parsed synthetic corpora. Each generated two-hop chain also has an anchor-mention document with a different predicate and an unread span about that document's unrelated term. The flat oracle gates unread spans that mention a question anchor. For each generated corpus, the test requires a routed `ANSWER` with the same values as the flat oracle, and confirms the irrelevant unread span is not routed. Additional cases cover a three-hop chain, condition lookup, and stopping expansion at common terms.

Run the acceptance suite from the worktree root:

```sh
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. \
  python -B -m pytest -q tests/test_semantic_route_follow.py
```

The run for this note passed **37 tests**.

## Reported tuning measurements

The following aggregate rows are transcribed from `join_tune_report_before_followfix.md` and `join_tune_report.md`. They pool the two-hop and guard rows across both corpus sizes and all frequency groups. Recall's denominator contains only flat-oracle-answerable cases; guard trials abstained in the oracle. Reach and latency are medians of the per-group medians. Each report records zero violations at every cap. These corpus-scale timings were not rerun for this unit.

| unread mode | cap | recall before | recall after | median reach before → after | median/p95 ms before → after | violations before → after |
|---|---:|---:|---:|---:|---:|---:|
| mention | 2 | 61/354 (17.2%) | 119/354 (33.6%) | 2 → 2 | 1.10/1.65 → 1.10/1.35 | 0 → 0 |
| mention | 4 | 63/354 (17.8%) | 139/354 (39.3%) | 5 → 4 | 0.74/1.77 → 0.71/1.41 | 0 → 0 |
| mention | 8 | 56/354 (15.8%) | 142/354 (40.1%) | 10 → 6 | 0.81/1.64 → 0.70/1.12 | 0 → 0 |
| mention | 32 | 52/354 (14.7%) | 142/354 (40.1%) | 16 → 6 | 0.85/1.86 → 0.69/1.18 | 0 → 0 |
| mention | 128 | 47/354 (13.3%) | 142/354 (40.1%) | 22 → 6 | 0.87/2.38 → 0.71/1.10 | 0 → 0 |
| all | 2 | 51/354 (14.4%) | 93/354 (26.3%) | 2 → 2 | 0.56/0.99 → 0.52/0.67 | 0 → 0 |
| all | 4 | 48/354 (13.6%) | 104/354 (29.4%) | 5 → 4 | 0.63/1.43 → 0.54/1.07 | 0 → 0 |
| all | 8 | 39/354 (11.0%) | 104/354 (29.4%) | 10 → 6 | 0.75/1.50 → 0.63/1.06 | 0 → 0 |
| all | 32 | 37/354 (10.5%) | 104/354 (29.4%) | 16 → 6 | 0.82/1.66 → 0.67/1.05 | 0 → 0 |
| all | 128 | 34/354 (9.6%) | 104/354 (29.4%) | 22 → 6 | 0.85/2.11 → 0.69/1.09 | 0 → 0 |

The report recommendation changes from expansion cap **4** before the fix to cap **8** after it, under `mention` mode. The reports attribute the better routed recall to retaining more of the relevant rare-entity joins while reducing unrelated leaf expansion. Zero violations means no routed answer contradicted or differed from the flat oracle in these trials; it does not establish coverage for common entities or for guard questions whose oracle abstained.
