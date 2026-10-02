# Semantic unknown choice limits attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| UCL-1 | robustness | Call `choose` concurrently twice on the same `SemanticUnknownChoice`, with the same candidate-status report and one frame term. Synchronize both asker callbacks at each thread's first ask. | The sequential alias-cache behavior is preserved for identical concurrent reads: two asks total, one history record, and both results reference that record. | Both calls pass the cache lookup before either adopts. Each makes two asks and writes a separate `ADOPT` testimony record; the chooser has two history entries and the results reference different records. This was reproduced in three synchronized runs. The xfailed test is the minimal reproducer. |

## What held

- Empty choice sets and reports outside `CANDIDATES` return `NONE` without asking.
- Blank and duplicate frame terms are filtered; a single remaining term can be adopted.
- Candidate provenance is returned with `counts_as_evidence: false`; the alias record is marked as testimony.
- Sequential repeated adoption reuses the same record without additional asks. Reordering the same frame terms also hits the cache.
- Non-string frame terms raise `TypeError` before asking.
- A frame vocabulary of 3,000 terms with null replies returns `UNRESOLVED` after two asks.
- Newlines, quotes, and delimiters inside a one-term option remain part of the adopted term.
- Superseding an adopted alias asks again and links the replacement record to the prior ID.

Acceptance command run from the worktree with the configured empty corpus environment:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_unknown_choice_limits.py
10 passed, 1 xfailed in 0.21s
```

## What was not covered

- No semantic correctness or fabrication claim was tested; there was no wrong-answer finding to reproduce twice.
- The large-input check used a 3,000-term frame vocabulary; it does not establish a memory or input-size ceiling.
- Concurrency was checked only for two identical calls synchronized before their first ask. Other interleavings, distinct keys, and shared-asker behavior were not covered.
- Pathological candidate object iterators, exceptions raised by the asker, and long-running or blocked askers were not covered.
- No external data or network sources were used.
