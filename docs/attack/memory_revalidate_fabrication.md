# Memory revalidation fabrication attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| None reproduced | — | Run `tests/attack/test_memory_revalidate_fabrication.py` | No stale record reaches the delegated ask; witness statuses follow the module's checker contract. | All 11 tests passed; no wrong answer or fabrication was established at the wrapper boundary. |

## What held

- A matching file digest and a contained `text_in_file` needle were labeled `FRESH` and kept available to the delegated ask.
- A digest mismatch, unreadable text file, or missing Git commit was labeled `STALE`; stale records were omitted before the ask and listed in `stale`.
- Testimony, unknown witness kinds, and malformed witnesses were labeled `UNVERIFIABLE`. As the module documents, these records remained answerable.
- The wrapper preserved the delegated answer payload and added witness labels. The tests included a negated claim to check that the wrapper did not rewrite that payload.
- The injected clock showed that a cached status was reused within its TTL and checked again after expiry. A zero TTL caused a check on each ask.
- The Git witness runner was called with a local `git cat-file -e <commit>^{commit}` check and a five-second timeout.

Acceptance command run from the worktree root:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_memory_revalidate_fabrication.py
```

Result: **11 passed in 0.13s**.

## What was not covered

The delegated `Memory.ask` and `Memory.ask_about` implementations were replaced with a boundary test double, so these tests do not establish how typed memory derives answers from records. Wrong-role attribution, entity swaps, whether negation is supported by the source, supersession behavior in the backing memory, and whether a partial text span supports a whole claim remain untested. The Git check used a stub runner rather than a real repository. No defect was reproduced, so there are no expected-failure tests.
