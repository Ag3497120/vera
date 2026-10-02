# Semantic WH limits attack

Scope: `read_role_list_question` in `verantyx/semantic_wh.py`, exercised directly with a recording builder. The reader recognizes wh-plus-case role questions and role-noun lists, and returns `None` for another shape or repeated semantic roles.

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| WH-LIM-01 | robustness | `""` or a single role such as `"誰が?"` | Return `None` without adding a bind or outputs. | Held. |
| WH-LIM-02 | robustness | `"誰が何は？"` | Return `None` because both labels map to `agent`. | Held. |
| WH-LIM-03 | robustness | 256 KiB of unrecognized `x` characters | Return `None` without mutating the builder. | Held. |
| WH-LIM-04 | robustness | `"誰が"` repeated 4,096 times | Reject duplicate roles without building a plan. | Held. |
| WH-LIM-05 | robustness | Two threads repeatedly reading `"誰が何を？"` and `"何を誰が？"` with separate builders | Each plan keeps its own role bindings and source text. | Held. |
| WH-LIM-06 | robustness | 1,200 fresh reads of `"誰が何を？"` after warmup | Calls do not retain unbounded per-call allocations. | Held; traced live-memory growth stayed below the test's 128 KiB bound. |

No wrong-answer, ungrounded-output, crash, or hang defect was reproduced, so no xfail cases were needed.

## What held

- Accepted wh and role-noun questions produce one wildcard `Pattern` with the requested role bindings.
- Reversing role order changes the pattern layout while preserving the label-to-role assignments.
- Repeated fresh calls are deterministic and keep each call's supplied source text in its own outputs.
- Empty, malformed, singleton, and duplicate-role questions return `None` without building partial output.
- Large malformed and duplicate-role inputs returned without exceptions; concurrent readers with separate builders kept their results independent.
- The acceptance run completed with **16 passed, 0 failed, and 0 xfailed**.

## Not covered

- Integration through the production semantic reader or downstream routing and verification.
- Builder implementations other than the recording builder, including their own resource budgets.
- Inputs that are not strings; the reader's contract is a raw question string.
- Operating-system level memory use or runtime behavior beyond the acceptance test process.
