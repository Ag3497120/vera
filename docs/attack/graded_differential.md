# Graded judge differential attack

The suite uses a small independent exact-term scorer over synthetic stores. It checks whole-grain matching, name-only and facet-inclusive indexing, ties, coverage, source-label removal, and the outer agreement report. Generated inputs contain unique query terms so the reference model can count exact matches directly without reusing `Ladder` or the graded module's helpers.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| GD-01 | robustness | Store `{"今昔物語": []}`; reader returns `["今昔物語"]`; query `今昔物語とは` | Exact stored core is answerable as `ANSWER` | `UNKNOWN_TIME_DEPENDENT`, with deictic `今`; substring detection mistakes part of the stable name for a time reference |

GD-01 is retained as a non-strict xfail. Its minimal test was replayed twice and produced the same xfail both times. This is a false refusal, not a fabricated answer.

## What held

- All 80 generated name-only cases and 60 generated facet-inclusive cases agreed with the independent scorer.
- Unique exact matches were returned; exact ties abstained at the setting level.
- Different settings that read different items produced an ambiguous outer report.
- Facet-only readings remained typed `ANSWER_BY_COARSENING`; source labels were absent from candidates and coverage.
- No-content and time-dependent routes returned no band, while a no-reading result retained a zero-agreement band.

## Not covered

The oracle intentionally covers only exact whole-term matching. It does not model character windows, Japanese morphology modes, language detection, or the default Japanese reader. The tests use small synthetic stores and do not measure corpus calibration or runtime on a large store.

## Acceptance run

Command run from the worktree root with the unit environment:

```text
/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_graded_differential.py
```

Result: 11 passed, 1 xfailed.
