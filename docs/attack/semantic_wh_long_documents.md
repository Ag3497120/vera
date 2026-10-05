# Long and multi-document semantic WH attack

This attack exercises `read_role_list_question` with large context text and
long role-only questions. The expected plans follow the reader contract: the
question names event roles, producing one wildcard `Bind` for those roles;
the predicate is not inferred from the context.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| LD-01 | robustness | Ask `誰が何を?` with a context containing 40 copies each of a sentence, a near-duplicate, and a contradictory pair, plus one sentence extended by 8,000 repeated clauses. | Produce one wildcard bind for `agent` and `patient`, preserving the supplied context in the bind and outputs. | The plan had those two roles in question order; the exact context object was carried through. No context-derived predicate or answer was produced. |
| LD-02 | robustness | Ask `誰が` repeated 2,048 times followed by `何を`. | Abstain because the question repeats the `agent` role; do not leave partial bindings or outputs. | Returned `None` with no binding, output, or projection. |

No reader defect, crash, or hang was reproduced. The reader does not execute an
answer, so wrong-answer and evidence behavior were not assessed. The acceptance
run completed with **15 passed**.

## What held

- Case particles mapped to their declared roles, and the roles stayed in the
  order asked.
- Role noun lists produced one wildcard bind with the listed roles.
- Supported question endings were accepted.
- Single-role questions, duplicate roles, and unsupported question shapes
  returned `None` without partial builder state.
- A long, contradictory context was carried as opaque input; it did not alter
  the role plan.

## Not covered

The test uses a recording builder to inspect the plan made by this reader. It
does not exercise downstream document routing, evidence selection, or answer
generation, so it does not establish how a full multi-document query is
resolved. It also does not use a production semantic builder or real document
IR.
