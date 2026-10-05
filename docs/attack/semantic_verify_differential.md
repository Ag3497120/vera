# Semantic verifier differential review

No differential disagreement was found in the exercised scope. The rows below record edge cases where the independent reference and verifier matched; `robustness` marks those checks as non-defects.

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| R-01 | robustness | `「外『内。』外！」次。` | Keep punctuation inside balanced quotes within the same source range; split after the quote. | Matched the character-scanner reference. |
| R-02 | robustness | `100 cm + 0.5 m`, requested in `m` | Exact result is `1.5 m`. | Sum replay matched the rational reference. |
| R-03 | robustness | Convert `1/3` to a finite decimal | Reject as non-terminating. | Raised the expected typed rejection. |

## What held

- Generated pairs of Japanese sentence terminators and newline boundaries matched a small character-by-character reference scanner. Balanced nested quote marks kept internal punctuation inside the sentence range, and malformed quotes were rejected by both implementations.
- Generated fractions with terminating decimal expansions matched an independent `Decimal` division reference. A non-terminating fraction and values beyond the verifier's precision contract were rejected.
- Length and mass unit conversions matched a separate rational scale table. Quantity comparisons across `m` and `cm` agreed with rational comparison; ordered string comparison was rejected.
- The `Sum`, absolute `Difference`, and equality `Filter` replay paths matched hand-calculated reference results.

## What was not covered

- Natural-language clause licensing, Japanese analyzer behavior, frame and measure parsing, guard/exception licensing, and source role-span assignment were not exercised.
- Plan validation, proof-node replay, evidence-universe enumeration, opponent detection, and the final gate were not exercised.
- The generated inputs were small. Large-source budget limits, adversarial runtime behavior, and hang behavior were not evaluated.

## Acceptance run

Ran the required command from the worktree root with `VERA_CORPUS_ROOT=/tmp/vera-empty-materials`, `PYTHONDONTWRITEBYTECODE=1`, and `PYTHONPATH=.`. Result: **121 passed in 0.11s**. No xfail was needed because no disagreement was reproduced.
