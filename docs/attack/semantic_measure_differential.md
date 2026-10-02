# Semantic measure differential attack

The attack uses an independent character scanner for a bounded set of source
sentences and an explicit reference table for the module's closed question
shapes. Expected dimensions, labels, relations, and output sorts are defined in
the test reference; they are not copied from module results.

## Findings

| ID | Severity (`wrong-ANSWER`, `ungrounded`, `crash`, `hang`, `robustness`) | Minimal repro | Expected | Observed |
|---|---|---|---|---|

No disagreements met the defect criteria in the exercised cases.

## What held

- The independent scanner agreed on 48 generated single-measure sentences
  using `kg`, `g`, `m`, and `cm`, including exact `Decimal` values, entity and
  answer labels, dimensions, and source spans.
- A two-measure sentence preserved decimal scale and propagated its shared
  head noun to both clauses.
- Malformed or incompletely consumed sentence examples returned `None`.
- All 9 exercised question shapes expanded to the reference `Sum` or
  `Compare` structure, including dimension-specific binds, a distinct-entity
  filter, relation, result sort, and output label.
- Unsupported question shapes returned `None` without changing the builder.
- Acceptance run: `23 passed`.

## Not covered

- The measure reader constructs typed operators; this attack did not execute a
  plan. It therefore did not verify computed sums, comparison answers, or
  cross-unit conversion at runtime.
- Source differential cases were limited to `kg`, `g`, `m`, and `cm`, simple
  labels and particles, and the sentence forms listed in the tests.
- The attack did not exercise the caller's full document-reading path,
  generated or external corpora, other unit spellings, or large-input timing.
