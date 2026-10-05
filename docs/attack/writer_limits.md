# Writer limits attack

Scope: limits and repeatability checks against the public `Writer` interface in
`verantyx/writer.py`. No production module was changed. All checks used empty
or no-form writers; this suite did not assess generated sentence content.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| WL-01 | robustness | `Writer.build([], [])` | Empty inputs produce no forms and report no corpora. | No forms; empty corpus report. |
| WL-02 | robustness | Call `sentence` for an unattested subject with a store whose fields raise if read. | Return an empty list without inspecting the store. | Returned an empty list; store fields were not read. |
| WL-03 | robustness | Same call with an unattested 2 MiB subject string. | Return an empty list without a crash. | Returned an empty list. |
| WL-04 | robustness | Attested subject, no forms, `limit=0`. | Return no sentences. | Returned an empty list. |
| WL-05 | robustness | Attested subject, no forms, `limit=10**12`. | Return no sentences; the budget cannot create a sentence without a form. | Returned an empty list. |
| WL-06 | robustness | Call `sentence` twice for the same attested subject with no forms. | Repeated calls return the same result without changing forms. | Both calls returned empty lists; forms stayed empty. |
| WL-07 | robustness | Run 80 reads across two `Writer` instances in an 8-worker thread pool. | Reads complete and each no-form request returns no sentence. | All 80 returned empty lists. |
| WL-08 | robustness | Make 2,000 reads for an unattested subject. | Repeated refusals do not grow the writer's built report, forms, or vocabulary. | Those three state snapshots remained unchanged. |
| WL-09 | robustness | Empty writer passage for a known seed with `steps=0`. | No sentences are written; all path entries are counted as skipped. | No sentences were written and `skipped` equaled path length. |
| WL-10 | robustness | Build from two empty labeled corpora in either order. | Empty corpora yield the same forms and corpus lengths regardless of order. | Both builds had no forms and the same corpus length map. |

No defect was reproduced, so the suite has no xfails. The severity labels above
identify the tested robustness boundaries; they do not indicate a failure.

## What held

- Empty input builds completed and reported no learned forms.
- Unknown subjects returned an empty result before touching the supplied store,
  including with the large subject input above.
- Zero and very large sentence budgets returned no output when no forms existed.
- Repeated and concurrent no-form reads completed without changing the checked
  writer state.
- The zero-step passage result kept its written and skipped counts consistent.
- Reversing the two empty corpus entries did not change the forms or corpus
  length map.

The acceptance command
`/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_writer_limits.py`
ran with the unit environment and reported **10 passed in 0.08s**.

## Not covered

- Non-empty learned forms, sentence quality, provenance, licensing, or incorrect
  generated claims.
- Save/load round trips, statute paths, large non-empty corpora, or malformed
  corpus and store objects.
- Memory profiling over long-running generation, or concurrent builds and
  reads while shared composition tables are being changed.
- Invalid passage modes, negative step counts, or walks over large stores.
