# Semantic unknown fabrication attack

Scope: `verantyx/semantic_unknown.py`, exercised only with small in-memory
`View` instances and no external corpus. These checks target whether
constructed unknown-term candidates can be mistaken for supported answers or
carry provenance that does not point into the referenced source clause.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| SF-01 | robustness | Pass a non-string term; then try budgets `0`, `-1`, `True`, `1.5`, and a budget below the clause/role work floor. | Reject the term or return an empty typed budget refusal. | Held: non-string raises `TypeError`; each invalid or insufficient budget returns `BUDGET_REFUSAL` with no candidates. |
| SF-02 | robustness | Query an exact role term (`Alice`) or predicate (`likes`) in the view. | Return `KNOWN_TERM` without a constructed candidate. | Held for both terms. |
| SF-03 | robustness | Query `Alicecats` against `Alice likes cats`. | Any route remains one of the documented candidate kinds, explicitly constructed and never evidence or an answer. | Held: the returned route is `KIN_NEIGHBOURHOOD`; serialized candidates have `constructed: true`, `evidence: false`, and no answer field. |
| SF-04 | robustness | For every unit in that candidate, follow its provenance into the source and clause span. | Each span's text equals the unit and is bounded by the cited source clause. | Held for every reported unit and location. |
| SF-05 | robustness | Query the reversed entity string `catsAlice`. | Do not classify a non-exact role/predicate string as `KNOWN_TERM`. | Held; any candidate report remains explicitly constructed and non-evidence. |
| SF-06 | robustness | Query `Alicecats` in a negative clause, then in two conflicting-polarity clauses. | A constructed candidate must not become testimony, evidence, or an answer. | Held: returned candidates remain marked non-evidence; no answer record is emitted. |

No wrong-answer, ungrounded-answer, crash, or hang defect was reproduced, so no
`xfail` was added. The table records attack checks that held, rather than
confirmed defects.

## What held

- Exact role and predicate matches short-circuit to `KNOWN_TERM` with no
  candidates.
- Budget refusals are typed and contain no candidates.
- A candidate report is marked constructed and `evidence: false`; its kind is
  constrained to the three declared candidate kinds.
- Reported provenance spans point to the exact unit text inside the cited
  clause span in the test view.
- Reversed entity order and negative/conflicting polarity did not turn a
  constructed candidate into an answer or evidence.

## What was not covered

- Invalid or internally inconsistent `View` objects, including role terms
  whose text does not match their source span.
- Whether time, polarity, or supersession should filter candidate generation;
  the conflict check only verifies that candidates remain non-evidence.
- Large-input performance or hangs, and behavior with non-text source values.
- External corpora or any data beyond the in-memory test views.

## Run

Acceptance command run from the worktree root with the specified empty corpus
environment:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_unknown_fabrication.py
```

Result: **10 passed in 0.08s**.
