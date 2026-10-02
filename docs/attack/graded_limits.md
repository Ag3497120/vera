# Graded judge limits and determinism

Independent limits probe for `verantyx.graded`. The synthetic stores and
readers below isolate `GradedJudge`; no corpus material was used. The required
acceptance command completed with **12 passed in 0.08s**. No defect reproduced,
so this file reports checked properties rather than known defects.

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| GL-01 | robustness | Empty settings and an empty store; ask with one content term. | Typed `UNKNOWN_NOT_PRESENT`, zero agreement, zero settings, and zero coverage without division failure. | Property held. |
| GL-02 | robustness | An injected reader returns 4,000 distinct unheld terms against a one-core store. | Typed `UNKNOWN_NOT_PRESENT`, no item, all terms missing, zero coverage. | Property held. |
| GL-03 | robustness | Build a whole-grain judge over 1,500 synthetic cores and ask for one exact core name. | The exact unique core remains `ANSWER` and is returned by name. | Property held. |
| GL-04 | robustness | Reverse the insertion order of two cores; repeat the same exact-core ask 40 times, rebuilding between asks. | Identical readings across order, asks, and rebuilds. | Property held. |
| GL-05 | robustness | Ask through two independently built judges in two threads, 30 asks per judge. | Each reader consistently returns its own exact core; no cross-talk. | Property held. |
| GL-06 | robustness | Two cores share the queried facet under a mentions setting. | Equal ladder scores abstain; the judge returns `UNKNOWN_NOT_PRESENT` with no item. | Property held. |
| GL-07 | robustness | Ask a time-deictic query with a matching subject, and separately ask blank/content-free queries. | Time-dependent, unparsed, and no-subject cases retain their distinct typed refusals. | Property held. |
| GL-08 | robustness | Annotate a unique whole-core reading, then annotate a query with no terms. | Annotation reports the one-setting band beside the reading; no-term input yields `None`. | Property held. |
| GL-09 | robustness | Run 200 distinct queries against one built judge. | Query traffic does not add ladders, held terms, or cores to judge state. | Property held. |

## What held

- Empty settings, empty/content-free queries, and time-dependent input returned
  typed refusals in the synthetic cases.
- A tie abstained, while a unique whole-grain core produced `ANSWER`.
- Core insertion order, repeated asks, repeated builds, and concurrent use of
  two separate readers did not change the checked readings.
- The judge handled the tested 4,000-term query and 1,500-core store. These are
  probe sizes, not asserted capacity limits.
- Repeated queries did not grow the judge's `ladders`, `held`, or `cores`
  collections. The annotation probe kept its band separate from the verdict.

## What was not covered

- No wall-clock or peak-memory benchmark was made; the state-size probe checks
  only the judge's retained collections.
- No malformed settings, malformed store objects, or non-string query values
  were tested.
- The concurrency check used two separate judges; concurrent calls on one
  judge were not exercised.
- No real corpus, semantic quality, or wrong-answer rate was evaluated.
- The checks do not establish capacity beyond the input sizes listed above.
