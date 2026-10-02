# Memory revalidation attacker: real-text stress

## Findings

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| MR-1 | crash | Pass a self-referential dictionary to `_status` twice. | Return `UNVERIFIABLE` for an unsupported witness. | Both checks raise `ValueError` during `_key` JSON serialization (`Circular reference detected`), before witness classification. Reproduced twice in the xfailed test. |

No wrong-answer or ungrounded answer was observed in the wrapper checks: the ask-path test stubs the underlying `Memory.ask` result and verifies stale records are removed before that call. No hang was observed in the bounded checks. These are not real-text rates.

## What held

The acceptance run completed with **14 passed and 1 xfailed**. File hash and text-match witnesses returned `FRESH` when they matched; mismatches and a missing text file returned `STALE`. Empty, unsupported, testimony, and timed-out git witnesses returned `UNVERIFIABLE`. The git witness check used the expected local `git cat-file -e` invocation, reported a missing commit as stale, reused a cached status within its TTL, and rechecked after expiry. The public ask wrappers omitted stale active records and attached witness statuses, including `UNVERIFIABLE` for testimony.

## What was not covered

No Wikipedia lead paragraphs were loaded or measured, so lead-level crash, hang, wrong-output, and ungrounded-output rates are **N/A (0 leads checked)**. The unit's commander allowed opening only `verantyx/memory_revalidate.py`; the referenced `tools/round5a_route_tune.py` loader was outside that read boundary. The checks therefore use local witness examples and a stub for `Memory.ask` rather than real Wikipedia input or the full memory implementation. No network or external corpus data was used.
