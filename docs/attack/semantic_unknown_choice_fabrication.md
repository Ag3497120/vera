# Semantic unknown choice: fabrication and provenance attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| UCF-01 | ungrounded | Give a `CANDIDATES` report one candidate with `units=("unsupported",)` and `constructed=False`; both asks select that only option. | A term from an unconstructed candidate is ineligible. With no other eligible terms, return `NONE` and no option. | Returns `ADOPT` for `unsupported`; both asks record selection of it. Reproduced twice in separate chooser instances. Tracked by xfail `test_unconstructed_candidate_term_is_not_adopted`. |
| UCF-02 | robustness | Adopt `first`, then call `supersede_alias` for the same word with a report whose only option is `second`. | The replacement record links `supersedes` to the prior alias ID, as required by the explicit correction path. | Returns `ADOPT` for `second`, but `supersedes` is `None`. Reproduced twice in separate chooser instances. Tracked by xfail `test_supersede_links_prior_alias_after_option_set_changes`. |

## What held

- A valid candidate selected in both asks is stored as testimony. Its provenance is returned separately, marked `counts_as_evidence: false`, and is absent from the ask prompts.
- An out-of-range choice produces `UNRESOLVED`; a report outside `CANDIDATES` and a candidate equal to the queried unknown do not trigger an ask.
- A term containing a newline and option-like delimiter remains one JSON-encoded option. Duplicate terms are offered once, with both candidate and frame origins.
- Repeating the same request reuses the alias. A changed option set causes a new ordinary choice, and explicit superseding links the prior alias when the option set is unchanged.

## Run

Acceptance command completed from the worktree root:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_unknown_choice_fabrication.py
```

Result: **9 passed, 2 xfailed**. The two xfails are the defects in the findings table; both test reproducers exercise each issue twice.

## Not covered

The tests use deterministic callbacks and small structural report/candidate objects, so they do not exercise the production `UnknownReport` construction path or an external model. Wrong-role and swapped-entity cases, negation changes, candidate-family and option variants, malformed input types, and non-returning callbacks were not covered. The probes stayed within the permitted module boundary and used no external data or network.
