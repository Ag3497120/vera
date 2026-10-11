# fixture_repo (LOOM-code)

A tiny package `calc/` (ops, fmt, counter) that the five code tasks K1-K5 of `docs/LINE3_LOOM_DESIGN.md` 10.2 are woven against
(`experiments/line3/loom/tasks_code.jsonl`).  The loom's CODE record index holds every `*.py` under `calc/`; it holds nothing under `tests/`.

## tests/

- `test_ops.py`, `test_fmt.py`, `test_counter.py`: regression tests of the existing package (green on the fixture as it stands).
- `test_k1.py` .. `test_k5.py`: **implementer-written PLACEHOLDERS** (written by the same agent that wrote the loom, so they are not held out).
  They exist so that the tests step has something to run (red on the fixture, green with the reference weave).  They are to be **replaced by
  codex held-out tests before any K result is cited**: until then a K1-K5 number (exit code, pass / fail, any rate) is a plumbing check, not
  evidence.  The attest row's `tests_sha` changes when they are replaced, which is how a result is tied to the tests that produced it.
