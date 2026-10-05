# Writer differential check

The check compares the writer's old-kana conversion and corpus licence choice
with small local reference functions. Other cases use narrow fakes to check
how `Writer` filters and forwards inputs to composition, aggregates a passage,
and records build metadata. The references do not call the implementation
helpers.

## Findings

These rows record covered behaviors; they are not defect reports. No defect
was reproduced, so the suite contains no xfails.

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| R01 | robustness | `modernize_form("前によつて後")` | `前によって後` | Matches; all 9 listed old-kana forms matched the independent reference. |
| R02 | robustness | `licence("対象")` with `{"対象": {"百科": 2, "法令": 4}}` and `norm_corpora={"法令"}` | `norm` | Matches the greatest-count corpus rule. |
| R03 | robustness | sentence for `対象`, facets `{z面, 出典語, a面}`, and source label `出典語` | Compose with sorted facets `[a面, z面]` and content source `対象` | Matches; source labels are filtered and the computed licence is forwarded. |
| R04 | robustness | passage walk sees 3 cores, while only one has a sentence | 1 written, 2 skipped, same trace returned | Matches. |

## What held

- The 9 specifically listed old-kana substitutions, combinations of those
  substitutions, preservation of unrelated text, and an unlisted spelling
  matched the independent reference.
- Licence selection returned `unknown` without counts, chose the corpus with
  the greatest count, and broke equal-count ties by label as documented in
  the implementation.
- An unattested subject did not reach composition. For an attested subject,
  `sentence` removed source labels from facets, sorted the remaining facets,
  and forwarded the subject as the content source.
- `passage` preserved the walk trace and reported its written and skipped
  counts. `build` retained the caller's prose sequence and recorded the
  mocked component reports and norm corpus labels.

Acceptance run from the worktree root:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_writer_differential.py
20 passed in 0.08s
```

## What was not covered

- Composition's real template and slot-selection behavior; composition was
  replaced with a recorder in the sentence-routing check.
- Building from real corpora or statute XML, and save/load behavior.
- Malformed inputs, filesystem failures, performance under large inputs, or
  whether generated drafts can reach any answer path elsewhere in the system.

The checks use synthetic data and support only the listed properties.
