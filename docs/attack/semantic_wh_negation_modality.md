# Attack: semantic WH negation and modality

## Findings

No defect was reproduced in this run, so there are no finding rows. The severity scale for a reproduced finding is `wrong-ANSWER`, `ungrounded`, `crash`, `hang`, or `robustness`.

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|

## What held

- WH case-role questions and role-noun lists produced one wildcard plan with the requested distinct roles, in input order, and retained their output labels.
- A single role, repeated semantic roles, and the tested predicate-bearing negation, double negation, adjective-like `いらない`, obligation, permission, prohibition, hearsay, and assertion forms returned `None` without allocating variables or binding a plan.
- The acceptance run completed with **15 passed** in **0.08 seconds**. No xfail cases were needed.

`None` means this reader did not recognize a role-only question shape; these tests do not treat it as a semantic `No`. The reader's plan/decline result alone does not establish an answer, and this run did not test downstream Unknown/No handling.

## What I did not cover

- Downstream pattern matching, semantic answer generation, and any conversion between Unknown and No.
- Integration with the real IR builder or documents; the tests use a recording builder to inspect the reader's requested wildcard and roles.
- Other negation and modality spellings, quoted or embedded clauses, and role-only fragments ending in a full stop.
