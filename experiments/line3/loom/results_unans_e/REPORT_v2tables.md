# LOOM-evidence, after the review (2026-10-12): the tables recomputed with the rule evidence.v2 and the third definition of route (1)

Route (1) = the run emitted NO text and the thread it ENDED with, replayed offline from its ledger (`score.final_thread_gate`: `ledger.replay`, then `evidence.gate`), fails the gate.  Sub-columns: **strict** = a refused `emit` carried `no_evidence`; **shown** = no refused emit, but a dry-run `read` listed `no_evidence`; **unseen** = the model never asked.  The 140 ledgers carry evidence.v1 and replay IDENTICAL under it; the same final threads are also judged under evidence.v2 (column `rule`).  Ledgers verified and replayed IDENTICAL: all 140.  (old) = the two earlier counts of REPORT_TABLES.txt: L_struct (a refused op ended the run) and told (a content code shown by a refused emit or a dry-run read).

## The 25 unanswerable bank2 items x 2 loom modes


**bank2 unans (25 items, 50 runs)**

| mode | rule | runs | wrong text | route (1) final-thread | = strict (refused emit) | + shown (dry-run read) | + unseen | content-level among route (1) | route (2) L_meta | no text, not route (1) or (2) | (old) L_struct | (old) told |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| record_only | evidence.v1 | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 24 | 1 | 0 | 0 |
| record_only | evidence.v2 | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 24 | 1 | 0 | 0 |
| constructed_allowed | evidence.v1 | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 24 | 1 | 0 | 0 |
| constructed_allowed | evidence.v2 | 25 | 0 | 0 | 0 | 0 | 0 | 0 | 24 | 1 | 0 | 0 |

| run | rule v1 (recorded): final thread | rule v2: final thread | how the model met it | outcome |
|---|---|---|---|---|

(the two sets together, 120 runs, are tabled in results_unans_adv_e/REPORT_v2tables.md)
