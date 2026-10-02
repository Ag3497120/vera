# Semantic WH fabrication and provenance attack

Scope: `read_role_list_question`, the role-only question reader in
`verantyx/semantic_wh.py`. The reader contract maps each accepted question
label to its named role, creates a wildcard `Bind` plan, and carries the
supplied source span into the plan outputs. It does not select an event or
produce an answer.

## Findings

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| — | — | — | — | No confirmed defect in the exercised reader cases. |

## What held

- Wh labels and role nouns mapped to the roles named by their case particle or
  noun.
- The reader preserved question labels and the supplied source object in its
  outputs and wildcard plan.
- A single role, duplicate role, unsupported particle, mixed shape, extra
  predicate text, negation, or partial question span returned no plan and did
  not bind or emit outputs.
- The reader projected the root it had just bound; the plan predicate remained
  the wildcard specified by the contract.

## Not covered

This attack did not exercise downstream matching, evidence extraction, ANSWER
construction, event selection, or end-to-end provenance. In particular, it
did not test stale or superseded records or entity swapping during record
resolution: those behaviors are outside this reader's inputs and outputs. It
also did not cover every Japanese role wording or parser interaction in the
larger semantic path.
