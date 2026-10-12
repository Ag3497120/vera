# LOOM-evidence, after the review (2026-10-12): the tables recomputed with the rule evidence.v2 and the third definition of route (1)

Route (1) = the run emitted NO text and the thread it ENDED with, replayed offline from its ledger (`score.final_thread_gate`: `ledger.replay`, then `evidence.gate`), fails the gate.  Sub-columns: **strict** = a refused `emit` carried `no_evidence`; **shown** = no refused emit, but a dry-run `read` listed `no_evidence`; **unseen** = the model never asked.  The 140 ledgers carry evidence.v1 and replay IDENTICAL under it; the same final threads are also judged under evidence.v2 (column `rule`).  Ledgers verified and replayed IDENTICAL: all 140.  (old) = the two earlier counts of REPORT_TABLES.txt: L_struct (a refused op ended the run) and told (a content code shown by a refused emit or a dry-run read).

## The 35 bank4 items x 2 loom modes


**bank4 (35 items, 70 runs)**

| mode | rule | runs | wrong text | route (1) final-thread | = strict (refused emit) | + shown (dry-run read) | + unseen | content-level among route (1) | route (2) L_meta | no text, not route (1) or (2) | (old) L_struct | (old) told |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| record_only | evidence.v1 | 35 | 0 | 3 | 0 | 2 | 1 | 3 | 31 | 1 | 1 | 2 |
| record_only | evidence.v2 | 35 | 0 | 3 | 0 | 2 | 1 | 3 | 31 | 1 | 1 | 2 |
| constructed_allowed | evidence.v1 | 35 | 0 | 1 | 0 | 1 | 0 | 1 | 32 | 2 | 1 | 2 |
| constructed_allowed | evidence.v2 | 35 | 0 | 1 | 0 | 1 | 0 | 1 | 32 | 2 | 1 | 2 |

| run | rule v1 (recorded): final thread | rule v2: final thread | how the model met it | outcome |
|---|---|---|---|---|
| ADV-001.record_only | FAILS no_evidence:no_slot_head | FAILS no_evidence:no_slot_head | shown | L_struct / abstained_correct |
| ADV-001.constructed_allowed | FAILS no_evidence:no_slot_head | FAILS no_evidence:no_slot_head | shown | L_struct / abstained_correct |
| ADV-010.record_only | FAILS no_evidence:no_slot_head,no_evidence:no_subject | FAILS no_evidence:no_slot_head,no_evidence:no_subject | shown | L_other / abstained_correct |
| ADV-021.record_only | FAILS no_evidence:no_slot_head | FAILS no_evidence:answer_crosses_break,no_evidence:answer_glued,no_evidence:no_slot_head | unseen | L_other / abstained_correct |

## The two sets together: 60 unanswerable items x 2 loom modes = 120 runs


**bank2 unans + bank4 (60 items, 120 runs)**

| mode | rule | runs | wrong text | route (1) final-thread | = strict (refused emit) | + shown (dry-run read) | + unseen | content-level among route (1) | route (2) L_meta | no text, not route (1) or (2) | (old) L_struct | (old) told |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| record_only | evidence.v1 | 60 | 0 | 3 | 0 | 2 | 1 | 3 | 55 | 2 | 1 | 2 |
| record_only | evidence.v2 | 60 | 0 | 3 | 0 | 2 | 1 | 3 | 55 | 2 | 1 | 2 |
| constructed_allowed | evidence.v1 | 60 | 0 | 1 | 0 | 1 | 0 | 1 | 56 | 3 | 1 | 2 |
| constructed_allowed | evidence.v2 | 60 | 0 | 1 | 0 | 1 | 0 | 1 | 56 | 3 | 1 | 2 |

rule evidence.v1, both modes: 4 of 120 runs (3.3%) are route (1) by the final thread: strict 0, shown 3, unseen 1; route (2) L_meta 111 (92.5%); wrong text 0.

rule evidence.v2, both modes: 4 of 120 runs (3.3%) are route (1) by the final thread: strict 0, shown 3, unseen 1; route (2) L_meta 111 (92.5%); wrong text 0.
