# Memory merge differential review

## Findings

The required acceptance run completed with **10 passed**. It found no disagreement between the module and the independent reference on the exercised inputs, so there is no defect severity to assign and no xfail was added.

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| — | — | None found in this run. | The documented canonical union and active conflict behavior. | No disagreement in 64 generated merge cases or 48 generated conflict cases. |

## What held

- A small reference implementation independently canonicalizes the union: writes by record id, exact duplicate removal, sorted alias/supersede/other events, inferred supersession links, and cycle rejection.
- The module matched that reference for 64 seeded generated event-log splits.
- Merge commutativity, idempotence, and associativity held for logs with a pending record-derived link.
- Exact duplicate event removal, canonical section ordering, collision rejection, pending links, inferred link materialization, and explicit and inferred cycle rejection held in focused cases.
- Active-record and conflict results matched a separate naive scan for 48 seeded generated record sets. The focused typed-conflict case included all active records supporting the conflicting values, in record-id order; superseded records did not remain active.
- JSONL file merging produced the same canonical result as the reference.

## Not covered

- The generated cases used small JSON-compatible mappings and did not cover arbitrary Python objects accepted through iterable inputs, extremely large logs, or performance limits.
- The file test covered a successful merge only; malformed JSONL, output-path aliasing, and filesystem failures were not exercised.
- This is a focused differential review of `memory_merge.py`; it does not establish behavior for the broader memory or semantic pipeline.
