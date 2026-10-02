# Conductor fabrication and provenance attack

Acceptance run: `10 passed, 2 xfailed in 0.20s` using the required interpreter and environment. Each xfail body builds two independent reproductions; the separate `--runxfail` run confirmed both cases in each body return the unsupported answer.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| CF-01 | wrong-ANSWER | Add a `CONFIRM` policy with condition `approve` and answer `yes`; ask “May I disapprove this proposal?” (also reproduced with “Should I disapprove this change?”). | Escalate for missing policy coverage. `disapprove` is a distinct predicate; an uncovered condition must not be treated as its negation or match. | `ANSWER yes` in both cases. `_matching_policy` uses substring containment, so `approve` matches inside `disapprove`. The answer cites the policy and authority records, but they cover `approve`, not `disapprove`. |
| CF-02 | ungrounded | Add an independent command-exit acceptance and a `PASS` verification with the correct distinct verifier and template, leaving `evidence_ref` empty. Repeated for two task frames. | Return `ASK_VERIFIER` until the verifier identifies inspected evidence, as required by the generated verifier prompt. | `ANSWER done` in both cases, citing the `VERIFICATION` record whose `evidence_ref` is empty. `record_verification` and `_valid_verification` accept the result without that requested provenance. |

## What held

- A unique ready successor was answered with its active `ORDER`, predecessor task, successor task, and cited authority record IDs.
- Competing ready successors caused abstention and cited both order edges and their authority.
- An order edge whose authority was superseded did not support an answer.
- Equally specific conflicting policies escalated with both policy and authority records.
- A unique choice answer cited its policy, authority, and vocabulary records; a protected policy answer escalated.
- A command witness and a valid distinct independent verifier produced a done answer with goal, acceptance, and verification IDs. Reusing the claimant as verifier was rejected.
- A malformed question escalated without an answer.

## Not covered

- File-hash, text-in-file, and git-commit witness freshness or path handling.
- Internals of `memory_frame` and storage-level forged records; the permitted source inspection was limited to `verantyx/conductor.py`.
- Broader language coverage, all protected-action variants, resolver alias flows, or concurrency and long-running behavior.
- Any development, held-out, sealed, or external corpus material.
