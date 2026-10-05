# Memory frame limits attack

Independent probes of write gates, witness handling, closed-choice resolution, persistence, repeated reads, and concurrent readers in `verantyx/memory_frame.py`. The tests treat writes as constructed memory, not testimony or evidence for any separate answer.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| MF-01 | crash | Write a FACT with `witness={"kind":"file_sha256"}`, then call `verify()`. | A malformed witness is rejected at write time or reported as `UNVERIFIABLE`; verification should not raise a raw exception. | The write is accepted. Verification indexes the absent `path` field and raises `KeyError('path')`. The xfailed test records this crash. |
| MF-02 | robustness | Write a valid FACT, then write another FACT with `supersedes="missing-record"`. | Reject the missing target without changing the log or active records. | `WriteRejected` is raised only after the new write event is appended. The attempted record remains in the log and active state. |
| MF-03 | robustness | With a constant `now`, write the same FACT twice with the same author and slots. | Idempotency probe: an identical retry should not add a duplicate event for the same derived record ID. | The second call appends another JSONL event. Both events use the same derived ID, so the in-memory record map still has one entry while the log grows. |

MF-03 is an idempotency and storage-growth probe; the interface does not otherwise promise deduplication of repeated writes.

## What held

- An empty log returned `UNKNOWN_NO_EVIDENCE` on repeated asks and remained uncreated.
- Missing required slots and a 100,000-character unknown kind produced `WriteRejected` without creating a log.
- A testimonial FACT survived reopening. Repeated reads and verification returned the same state without changing the JSONL bytes.
- A nonexistent file witness was reported as `STALE`; it remained visible with `require_fresh=False` and was filtered with `require_fresh=True`.
- Closed-choice resolution selected the same canonical term with reversed option order and repeated calls. Empty choices and invalid replies returned `NONE` or `UNRESOLVED`.
- A 750-option closed-choice list with `null` answers completed as `NONE`.
- Two independent readers returned matching snapshots concurrently, and a valid supersession left only the replacement record active.

## Not covered

No wrong-answer or ungrounded-answer finding was established: these probes did not validate semantic answers from populated memory. The suite did not exercise malformed JSONL at startup, concurrent writers or writer-reader races, very large persisted logs, resource caps over a long-running process, arbitrary asker hangs/exceptions, or every malformed witness shape. No sealed, heldout, or development data was used.

## Run

Acceptance command: `/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_memory_frame_limits.py`, with `VERA_CORPUS_ROOT=/tmp/vera-empty-materials`, `PYTHONDONTWRITEBYTECODE=1`, and `PYTHONPATH=.`.

Final result: `10 passed, 3 xfailed in 0.19s`.
