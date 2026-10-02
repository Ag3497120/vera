# Reach fabrication attack

Scope: `verantyx.reach` with controlled stores, unit models, and judge stubs.
The acceptance run used the required empty-materials environment on 2026-10-02.

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| RF-1 | ungrounded | Empty `crosses`; ask for `AB`; judge returns `{"verdict": "ANSWER", "item": "UNRELATED", "agreeing": ["unsupported-record"]}`. Repeated twice in the xfailed test. | `UNKNOWN_NO_REACH`, with no item: there is no held core containing `AB`. | Both calls returned `CONTAINMENT` with item `UNRELATED` and the judge's `agreeing` value. `reach` accepts the judge verdict without checking that the item is held or contains the term. |

## What held

The 10 passing tests show that exact cores take precedence, source labels do not
count as held cores or unit evidence, unit splits respect left/right slots, the
richest attested unit is chosen, units precede containment, and a non-answer
judge result leaves the term unknown. The tests also check forwarding of a
containing held item from the judge and exclusion of labeled entries when
building the unit model.

## What was not covered

The unit and judge interfaces were controlled test doubles; this did not assess
the real graded judge's records, chronology, or agreement logic. The split map
was stubbed for the unit-role cases, so this run does not measure corpus-derived
decompositions. No hang or crash behavior was exercised.

Acceptance command result:

```text
10 passed, 1 xfailed in 0.08s
```
