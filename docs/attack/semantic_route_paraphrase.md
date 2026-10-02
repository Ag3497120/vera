# Semantic route paraphrase attack

Scope: `semantic_route.LeafTree.restrict` with constructed semantic IR views and requests. Expected behavior is based on the router's contract that anchored routing retains documents whose clauses can matter, unread mentions gate routing, and routed views remain subsets of the input view.

## Findings

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| SRP-1 | robustness | With 10 leaves, put `Role("destination", Nominal("Tokyo", "Tokyo"), ...)` in d0, and put a Tokyo unread mention in d9. Route a request anchored to the literal string `Tokyo`. | Keep d0 because its clause contains the anchored nominal head. | d0 is omitted; d9 is retained through its unread mention. Clause-role indexing includes string terms but skips `Nominal` values. |
| SRP-2 | robustness | With 10 leaves, put a clause anchored by `New York` in d0 and unread text `NewYork appears in an opaque span` in d9. Route an anchor for `New York`. | Retain d9's unread span because the router's unread matching normalizes whitespace, so these surface forms match. | d9 is in the routed sources, but its unread span is filtered out by the later exact substring check. |

Both defects are visible as non-strict xfails. Each reproducer was rerun independently twice and failed its expected-retention assertion in both runs. The severity is `robustness`: this unit tests routing only and does not establish a downstream answer flip.

## What held

The acceptance run completed with **8 passed and 2 xfailed**. The passing cases covered polite/plain and word-order paraphrases with equivalent IR, role-order changes, entity swaps, conjunctive anchors, union across bind patterns, common-anchor fallback, role-only fallback, inclusion of a clause with a different predicate and negative polarity, and following a condition entity to its fact document. A routed-clause subset check also held.

## Not covered

- Whether the upstream reader maps natural-language paraphrases to equivalent IR.
- Whether either dropped item changes a producer/checker verdict or causes a wrong final answer.
- Wikipedia or other corpus behavior, stress/performance limits, and concurrency.
- Broader semantic cases beyond the constructed views and requests in this unit.
