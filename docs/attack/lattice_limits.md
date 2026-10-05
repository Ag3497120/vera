# Lattice limits and determinism attack

Scope: black-box checks of `verantyx.lattice` using small constructed inputs. No production corpus or external data was loaded.

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| D-01 | crash | `build([None])` | Return a typed refusal for a malformed word. | Raises `TypeError: object of type 'NoneType' has no len()`. Captured as a non-strict xfail. |
| P-01 | robustness | `build([])` | Empty words, slots, and atoms. | Held: all three are empty and reported as zero. |
| P-02 | robustness | Build the same words as a list, reversed iterator, generator, and duplicated list. | Input iteration order and duplicates do not change the lattice. | Held: snapshots match. |
| P-03 | robustness | Build `テレビドラマ` with both `テレビ` and `ドラマ`, then with only `テレビ`. | A long split is present only when both halves are words. | Held: the licensed split appears; the incomplete vocabulary yields no split. |
| P-04 | robustness | Build `電荷密度`, empty and one-character strings, and strings of length 13 and 100,000. | Only supported word lengths become nodes; oversized inputs are skipped. | Held: only `電荷密度` is retained. |
| P-05 | robustness | Analyze `電荷密度` at depths 0 and 1 with attested components. | Depth zero has no branches; depth one has valid children without recursive branches. | Held. |
| P-06 | robustness | Query kin with `limit=1`. | Results are sorted, exclude the term, and each family stays within the limit. | Held. |
| P-07 | robustness | Predict tied facets with `top=1`, then `top=0`. | Ties use lexical order; source labels and the term itself are omitted; zero returns no facets. | Held: `facet-a` is selected and zero returns an empty list. |
| P-08 | robustness | Repeat `analyze` and `kin` 20 times on one lattice. | Results stay identical and reads do not mutate the lattice. | Held. |
| P-09 | robustness | Two thread-pool readers make 40 calls each to `analyze`, `kin`, and `predict_facets` on shared inputs. | Concurrent reads match the sequential result. | Held. |
| P-10 | robustness | Build three words once and as a list repeated 5,000 times. | Duplicate-heavy input produces the same unique lattice state. | Held. |

## What held

The required acceptance run completed with **11 passed, 1 xfailed** in **0.10 seconds**. A second run with xfail reporting completed with **11 passed, 1 xfailed** in **0.11 seconds**. The one xfail is D-01; the other checks passed. The direct malformed-input reproduction confirmed the raw `TypeError`.

Order changes, duplicate entries, and generator input produced the same lattice snapshot. The tested long split required both component words. Repeated queries and two concurrent readers left the shared lattice unchanged. Positive result limits and the zero prediction budget behaved as expected.

## What I did not cover

- Infinite or very slow iterators, because exercising them could hang the test process.
- Process-wide memory consumption or scaling with a large vocabulary. The duplicate-heavy check covers only 5,000 repetitions of three short words.
- Malformed values other than `None`, or non-iterable `words` inputs.
- Corpus-backed behavior, other lattice consumers, or broader answer quality.

No wrong-answer or ungrounded defect was observed in these constructed cases. No fix was made to the lattice module.
