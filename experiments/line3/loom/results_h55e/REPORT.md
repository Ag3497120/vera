# LOOM-evidence — the reader's evidence gate at emit (claude-haiku-5-5, loom modes only, 140 runs, 2026-10-12)

Gate (docs/LINE3_LOOM_EVIDENCE_GATE.md, L-LOOM-170..190): a prose emit must be an unchanged weave_span quote; the loom derives the clause of the quoted sentence and reads it as Vera's grammar cross; the clause must hold every subject word (or the article title, OP-EV-1 a); the answer may not contain a question word; slot questions need the slot particle after the answer and the slot head in the sentence; predicate questions need 「Yは A」/「A は … Y」; else `no_evidence` with a code. Old ledgers replay under their recorded rule (no gate): 391/391 IDENTICAL; the 140 new ledgers verify/replay IDENTICAL. Prompts changed with the gate (recorded as a changed condition).

## Predictions vs outcome
| P | prediction | outcome |
|---|---|---|
| P-EV-1 | record_only exact 3/7 | 2/7 (I2-013, I2-034; I2-025 wove 青 four times and abstained without read/emit — model error, the gate passes 青) |
| P-EV-2 | constructed_allowed 3/7, no constructed unit emitted | 3/7 (I2-013, I2-025, I2-034); 0 constructed units added in 140 runs |
| P-EV-3 | 4 unreachable items: 0 exact, ≥ 6/8 told no_evidence | 0 exact; 6/8 told no_evidence; 0 texts |
| P-EV-4 | bank2 unans: 0 emitted | 0 emitted; L_meta 24 / 24 |
| P-EV-5 | bank4: 0 confident wrong per mode; ≥ 2 content-level refusals per mode | 0 / 0; trap emitted 0; content-level no_evidence shown 2 per mode (strict refused-emit 0) |
| P-EV-7 | input tokens ≥ 1.5× h55d | 1.88× (median 82,295 vs 43,795) |
| P-EV-8 | route (1) content-level ≥ 3/120; route (2) ≥ 85 % | shown 4, strict 0; route (2) 111/120 = 92.5 % |
| P-EV-9 | reach ≤ 12/69 | 12/69 |

Answerable exact hits, h55d → now: record_only 6/7 → 2/7; constructed_allowed 5/7 → 3/7.

## Two routes on 60 unanswerable items × 2 loom modes (120 runs)
| | wrong text | route (1) strict (refused emit) | route (1) shown (no_evidence via dry-run read or refused emit, then no text) | route (2) L_meta | other |
|---|---|---|---|---|---|
| before (h55-era), record_only | 2 | 0 | 0 | 57 | 1 |
| before, constructed_allowed | 2 | 2 (form only) | 0 | 55 | 1 |
| **now, record_only** | **0** | 1 (form) | 1 | 55 | 4 |
| **now, constructed_allowed** | **0** | 1 (form) | 1 | 56 | 3 |

Content-level refusals shown: ADV-001 (both modes), ADV-010 (record_only), ADV-013 (constructed_allowed). The 16 final threads left by the new runs: the 5 that pass the gate are exactly the 5 answerable hits; the other 11 would all be refused. Controls (stored): lookup control 1 wrong, pure LLM 22 wrong of 60.

## Reach cost (57/69 answerable bank2 items unreachable)
Best codes: no_slot_head 32, no_subject 21, wrong_arm 11, answer_holds_question_unit 8, question_form_open 8, gold not on word boundaries 5, not_copular 3, question_has_no_subject 2. The four lost loom items: I2-001 (paraphrase ともいう/別名), I2-008 (relative clause 人物 absent), I2-041 (head カクテル名 in the other clause), R2-I013 (に vs で; 使わ absent). I2-041 admits the wrong 「Sol」 through the gate (no run tried it).

Tokens: 23.86M in / 0.20M out over 2,061 calls. Tables: REPORT_TABLES.txt. Open points: route (1) definition (dry-run read vs refused emit); gate and prompt changed together (n = 1 per cell); record_only ≡ constructed_allowed in prose now.

## Notes after the review (2026-10-12; appended, nothing above is changed)
1. **Failure-code histogram.** The 57 unreachable answerable items are listed above by best occurrence with `no_subject` 21 and `answer_holds_question_unit` 8; the design (§2.4) says 15 and 7. Both count the "best" occurrence of an item, and the design does not state the tie-break; the product code takes the occurrence with the fewest codes. The reach (12 / 69) is the same in both. Not a defect.
2. **Two "told" numbers with two definitions.** P-EV-3 says "6/8 told no_evidence": of the 8 runs on the four unreachable items, 6 were SHOWN a `no_evidence` refusal, by a dry-run `read` or a refused `emit`. REPORT_TABLES.txt (P-EV-3 rows) says 1: only one of the 8 had a REFUSED OP carrying `no_evidence` (the `strict` count). They are different populations of events, not different measurements. The route table below the predictions counts 60 unanswerable items and has its own columns (strict 1 per mode, shown 1 per mode).
3. **Route (1) has a third definition, now THE definition** (review; owner 2026-10-12): the run emitted no text and the final thread, replayed offline, fails the gate. REPORT_v2tables.md (this folder and results_unans_e / results_unans_adv_e) gives it with `strict` (a refused emit) and `shown` (a dry-run read) as sub-columns, plus `unseen` (the model never asked). Over the 120 unanswerable runs: 4 runs (3.3 %): strict 0, shown 3, unseen 1 (ADV-001 x2, ADV-010 record_only shown; ADV-021 record_only unseen); route (2) 111 (92.5 %). ADV-013 constructed_allowed, counted "told" before, dropped its thread after the read: the final thread is empty, so it is not route (1) by this definition.
4. **record_only and constructed_allowed are the same condition for prose under the gate** (a constructed unit is `no_evidence/constructed_unit` in both). The modes were not changed and both stay measured; a difference between them in this table is run-to-run variation.
5. **The gate measured here is evidence.v1.** Its known holes (a predicate question with no subject, pieces of words, over-long stretches, several answers joined) and the fixes (evidence.v2) are in docs/LINE3_LOOM_EVIDENCE_GATE.md §8.6 and §12 and in L-LOOM-191..; the 140 ledgers replay IDENTICAL under v1. Under v2 the answerable hits would be 県社 (I2-013 x2) only: 青 and 1981年 are refused (REPORT_v2tables.md).
