# Coverage fabrication attack report

The attack exercises `closing_domains` and `document_needed` with small in-memory shelf objects. It does not change `verantyx/coverage.py`.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| COV-FAB-01 | robustness | Put the subject in 5 or 6 shelves with the same score. | Since ties are displayed rather than broken, every tied shelf remains visible. | `closest` contains only the first 4 shelves; the other tied shelves are omitted. Reproduced with both shelf counts. |
| COV-FAB-02 | wrong-ANSWER | Map an alias to `Human Rights` or `Data Protection`, and put that exact title in a shelf's `crosses`. | The held canonical title gives that shelf score 2 with an `alias held` signal. | No shelf is returned and `coverage_hole` is true. The lookup case-folds the canonical title but does not normalize the stored set. Reproduced with both titles. |

Both findings are retained as non-strict xfails so the suite passes while keeping the defects visible.

## What held

- An exact subject core is reported with score 2 and a `held` signal.
- A subject unit is identified as a unit signal with score 1; two distinct matching units contribute 1 each.
- A source label alone is not counted as a core.
- A direct core ranks above a partial unit, and its signal stays attached to the shelf containing it.
- A one-hop Japanese alias is named in the signal; an alias chain is not followed.
- An empty atlas reports a coverage hole and names no shelf. A two-shelf tie is shown in the document line.

Required acceptance run: `10 passed, 4 xfailed in 0.09s` with `VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=.` and `/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_coverage_fabrication.py`.

## What was not covered

The API accepts prebuilt `crosses` and `source_labels`, not source records with roles, entity links, negation, revisions, or spans. These tests therefore cannot verify whether an underlying record swapped an entity, dropped a negation, was superseded, or matched only part of a source sentence. They check only the presence and shelf association of the strings exposed by the atlas.
