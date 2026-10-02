# Differential attack: `verantyx.summarize`

The tests compare the implementation with a small, separate reference derived from the documented path, crossing, edge-license, vocabulary, ranking, and whole-rank-drop rules. Generated cases use unique subject IDs and synthetic stores; no corpus data is loaded.

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| SD-1 | wrong-ANSWER | One stored subject `A` holds `f1` and `f2`; call with subjects `["A", "A"]`, vocabulary `{A, f1, f2}`, and an edge license for `(f1, f2)`. Reproduced twice with `--runxfail`. | `UNKNOWN_TOO_FEW_PATHS`: the request contains only one distinct held path. | `SUMMARY`, with the repeated path counted twice as holders of both facets and one licensed `A: f1 と f2` claim. |

## What held

- Disjoint paths return `UNKNOWN_NO_CROSSING`; shared facets without a licensed edge return `UNKNOWN_NO_EDGE_LICENSE`.
- Subject and facet vocabulary gates prevent those terms from entering claims.
- Source labels and subject names are not counted as crossing facets.
- Rank ties sort by subject and pair, and a rank group that does not fit is dropped whole along with lower groups.
- Edge lookup exceptions produce a typed no-license refusal.
- The independent reference agreed with 50 generated unique-subject cases.

The required acceptance command completed with **9 passed and 1 xfailed**. The xfail is the reproduced SD-1 defect.

## Not covered

This attack uses synthetic in-memory inputs. It does not inspect corpus sidecars, validate the edge loader's data integrity, test malformed edge callback return values, or measure large-store performance and memory use. The module itself was not changed.
