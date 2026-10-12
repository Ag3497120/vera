# LOOM-evidence, after the review (2026-10-12): the tables recomputed with the rule evidence.v2 and the third definition of route (1)

Route (1) = the run emitted NO text and the thread it ENDED with, replayed offline from its ledger (`score.final_thread_gate`: `ledger.replay`, then `evidence.gate`), fails the gate.  Sub-columns: **strict** = a refused `emit` carried `no_evidence`; **shown** = no refused emit, but a dry-run `read` listed `no_evidence`; **unseen** = the model never asked.  The 140 ledgers carry evidence.v1 and replay IDENTICAL under it; the same final threads are also judged under evidence.v2 (column `rule`).  Ledgers verified and replayed IDENTICAL: all 140.  (old) = the two earlier counts of REPORT_TABLES.txt: L_struct (a refused op ended the run) and told (a content code shown by a refused emit or a dry-run read).

## The 10 bank2 tasks (7 answerable, 3 unanswerable)


| run | status | text | final thread under v1 (recorded) | final thread under v2 |
|---|---|---|---|---|
| I2-001.record_only | abstained_wrong | (none) | (no thread) | (no thread) |
| I2-001.constructed_allowed | abstained_wrong | (none) | FAILS no_evidence:no_slot_head | FAILS no_evidence:no_slot_head |
| I2-041.record_only | abstained_wrong | (none) | FAILS no_evidence:no_slot_head | FAILS no_evidence:no_slot_head,no_evidence:question_has_no_subject |
| I2-041.constructed_allowed | abstained_wrong | (none) | FAILS no_evidence:no_slot_head | FAILS no_evidence:no_slot_head,no_evidence:question_has_no_subject |
| I2-008.record_only | abstained_wrong | (none) | FAILS no_evidence:no_slot_head | FAILS no_evidence:no_slot_head |
| I2-008.constructed_allowed | abstained_wrong | (none) | FAILS no_evidence:no_slot_head | FAILS no_evidence:no_slot_head |
| I2-034.record_only | hit | 1981年 | passes | FAILS no_evidence:no_slot_head |
| I2-034.constructed_allowed | hit | 1981年 | passes | FAILS no_evidence:no_slot_head |
| I2-013.record_only | hit | 県社 | passes | passes |
| I2-013.constructed_allowed | hit | 県社 | passes | passes |
| R2-I013.record_only | abstained_wrong | (none) | FAILS no_evidence:no_slot_head,no_evidence:wrong_arm | FAILS no_evidence:answer_glued,no_evidence:no_slot_head,no_evidence:wrong_arm |
| R2-I013.constructed_allowed | abstained_wrong | (none) | (no thread) | (no thread) |
| I2-025.record_only | abstained_wrong | (none) | FAILS no_evidence:answer_holds_question_unit,no_evidence:no_subject | FAILS no_evidence:answer_crosses_break,no_evidence:answer_holds_question_unit,no_evidence:no_slot_head,no_evidence:no_subject |
| I2-025.constructed_allowed | hit | 青 | passes | FAILS no_evidence:no_slot_head |

Under v2 only 県社 (I2-013, both modes) would still be emitted: 青 (no slot head: 何色と ends the question) and 1981年 (設立 is outside the clause) are refused.

**the 3 unanswerable bank2 tasks (UF-001, UF-015, R2-U003), recorded rule v1 and v2**

| mode | rule | runs | wrong text | route (1) final-thread | = strict (refused emit) | + shown (dry-run read) | + unseen | content-level among route (1) | route (2) L_meta | no text, not route (1) or (2) | (old) L_struct | (old) told |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| record_only | evidence.v1 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| record_only | evidence.v2 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| constructed_allowed | evidence.v1 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |
| constructed_allowed | evidence.v2 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3 | 0 | 0 | 0 |

| run | rule v1 (recorded): final thread | rule v2: final thread | how the model met it | outcome |
|---|---|---|---|---|

## Offline: the corpus probe (every stretch of at most 10 WORD units of every sentence, title scope; 69 answerable bank2 items, 60 unanswerable)

| rule | answerable items reachable (some passing stretch is a gold alternative) | items admitting at least one WRONG stretch | of which admit ONLY wrong stretches |
|---|---|---|---|
| evidence.v1 | 12 / 69 | 21 / 69 | 9 |
| evidence.v2 | 10 / 69 | 0 / 69 | 0 |

reachable under v1: I2-003, I2-004, I2-005, I2-006, I2-013, I2-014, I2-018, I2-025, I2-034, R2-I005, R2-I007, R2-I017
reachable under v2: I2-003, I2-004, I2-005, I2-006, I2-013, I2-014, I2-018, R2-I005, R2-I007, R2-I017
wrong-admitting under v1: I2-003, I2-004, I2-005, I2-006, I2-013, I2-014, I2-015, I2-017, I2-018, I2-025, I2-027, I2-028, I2-029, I2-030, I2-034, I2-041, I2-042, R2-I002, R2-I005, R2-I007, R2-I017
wrong-admitting under v2: none
unanswerable items with any passing stretch under v2: 0 of 60
