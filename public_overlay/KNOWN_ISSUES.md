# Known issues — snapshot 2026-10-03 (working-copy commit d25a73a, development paused)

Clean clone, `PYTHONPATH=vera_base python -m pytest tests`: 1,666 passed, 18 failed, 9 skipped.
Cause: several units were merged in a wave whose regression gate covered only a few test files; later merges changed behaviour that older tests encode. A repair pass fixed the verifier-agent and memory tests and was stopped before the rest. Each remaining failure is either a real regression (code to fix) or an outdated expectation (to update with a reason); safety tests are not to be loosened.

| Test file | Failing |
|---|---:|
| tests/test_semantic_measure.py (role-only questions, kanji-title splitting) | 8 |
| tests/test_semantic_realize.py (に/で/から case roles typed as ambiguous in some sentences; literal-overlap guard) | 3 |
| tests/test_semantic_coordination_codex.py | 2 |
| tests/test_semantic_scope_safety.py, test_semantic_public.py, test_request_goal_route.py, test_one_trace.py, test_conductor.py | 1 each |

Demos: `tools/demo_conduct.py` and `tools/demo_system.py` fail after the driver/verifier merges; `demo_generate`, `demo_outside`, `demo_vocab`, `demo_frame` print `DEMO OK`.

Behaviour versus the published 0.1.0 package: in pack-only mode the three example outputs listed in the README differ by design (source identity required; ties abstain). For 0.1.0 behaviour use the v0.1.0 tag.

Not in this repository: the independent attacker tests (they record about 150 defects as xfail and were not triaged), the Codex-generated corpus, and any sealed or heldout data.
