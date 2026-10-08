| item | value | source (artifacts/w3-b1/) |
|---|---|---|
| new data: rows (ja_r8 / en_r4) | 213 (197 / 16) | tests/reading_soundness/ja_r8.jsonl, en_r4.jsonl |
| new data: path U, read-expected / abstain-expected | 45 / 65 | ja_r8.jsonl, en_r4.jsonl (r8_counts.txt) |
| new data: path S4, read-expected / abstain-expected | 36 / 51 | ja_r8.jsonl, en_r4.jsonl (r8_counts.txt) |
| new data: path EN, read-expected / abstain-expected | 0 / 16 | ja_r8.jsonl, en_r4.jsonl (r8_counts.txt) |
| new data: path U, rows per predicate type (read-expected + abstain-expected) | P_ACT 0+4, P_CHANGE 0+4, P_COGNITION 0+4, P_COMMUNICATE 21+12, P_CONSUME 0+4, P_CREATE 0+4, P_EMOTION 0+4, P_EXIST 0+4, P_GIVE 0+4, P_MOVE 24+8, P_PERCEIVE 0+4, P_POSSESS 0+4, P_STATE 0+5 | ja_r8.jsonl |
| entry with the placement on the new data: verdicts | abstain 114, correct 96, incomplete 3 | r8_entry_check.json |
| entry with the placement on the new data: misread / incomplete / UNJUDGED | 0 / 3 / 0 | r8_entry_check.json |
| entry with the placement on the new data: bad verdicts identical to the output with no placement | 3 of 3 | r8_entry_check.json |
| new data: read-expected rows the entry abstains on / abstain-expected rows the entry reads | 30 / 3 | r8_entry_check.json |
| new data: abstained rows whose second reason is not the registered prefix | 16 | r8_entry_check.json |
| declared exceptions (w3b1_expect_exceptions.json) by kind | baseline_reads 3, reason_differs 16, row_returned_to_abstain 21, trigger_not_reached 9 | tests/reading_soundness/w3b1_expect_exceptions.json |
| base-commit comparison: inputs (x3 + English + B1 samples + event cross sentences + new data) | 2761 | entry_dev.jsonl, entry_live.jsonl |
| base-commit comparison: same / reason_changed | 2446 / 264 | entry_dev.jsonl, entry_live.jsonl, base_diff_summary.txt |
| base-commit comparison: false->readable / readable->false | 51 / 0 | entry_dev.jsonl, entry_live.jsonl, base_diff_summary.txt |
| base-commit comparison: changed (source fields taken out) / changed (as they are) / error_changed | 0 / 0 / 0 | entry_dev.jsonl, entry_live.jsonl |
| false->readable by the file the input comes from | ja_r8.jsonl 51 | base_diff.jsonl |
| false->readable verdicts | CORRECT 51 | base_diff.jsonl |
| reason_changed: reasons added, by prefix | PLACEMENT_DIRECT_VIA_GENERATED 2, PLACEMENT_ESTIMATED_GENERATED 5, PLACEMENT_ESTIMATED_NEAR 2, PLACEMENT_FRAME_NOT_READ 79, PLACEMENT_MULTIPLE 11, PLACEMENT_NOT_PREDICATE_TYPE 1, PLACEMENT_PART_MARKER 7, PLACEMENT_PART_NONE 2, PLACEMENT_PART_NOT_FOLLOWED 3, PLACEMENT_PART_NOT_ISOLATED 3, PLACEMENT_PART_NOT_NP 16, PLACEMENT_PART_NO_ROLE 2, PLACEMENT_PART_PARTICLE 2, PLACEMENT_PREDICATE_UNIDENTIFIED 32, PLACEMENT_SLOT_EVIDENCE_ONLY 14, PLACEMENT_TYPE_MISMATCH 30, PLACEMENT_UNKNOWN 26, PLACEMENT_UNPLACED 23, PLACEMENT_VOICE_NOT_ACTIVE 4 | entry_dev.jsonl, entry_live.jsonl |
| x3 sentences in the comparison: count / newly readable with the placement | 2217 / 0 | entry_dev.jsonl, entry_live.jsonl |
| reader (document_view) on the x3 sentences: byte-for-byte as the base commit | yes (2217 lines) | x3_after.jsonl, x3_dev.jsonl |
| frozen banks (harness): sentences / changed / misread | 500 / 0 / 0 | soundness_compare.txt |
| a3_check output same as the base commit | yes | a3_dev.txt, a3_after.txt |
| entry with no placement: output equal to the base commit on all inputs | yes | entry_none.jsonl, entry_dev.jsonl |
| answers rewritten to estimated only: newly readable / readable and changed | 0 / 0 | a3_direct_only.txt |
| answers rewritten to multiple only: newly readable / readable and changed | 0 / 0 | a3_direct_only.txt |
| B1 sample B1_v2 through the scorer (no placement reaches the child process): correct / correct_abstain / over_abstain / misread / wrong | 35 / 13 / 17 / 0 / 0 | bs_B1_v2/summary.json |
| B1 sample B1_v2_r2 through the scorer (no placement reaches the child process): correct / correct_abstain / over_abstain / misread / wrong | 11 / 8 / 17 / 0 / 0 | bs_B1_v2_r2/summary.json |
| B1 sample B1_v2_r3 through the scorer (no placement reaches the child process): correct / correct_abstain / over_abstain / misread / wrong | 4 / 0 / 13 / 0 / 0 | bs_B1_v2_r3/summary.json |
| B1 samples in-process with the placement: verdicts | abstain 47, correct 71; misread 0, incomplete 0 | b1_fixtures_live.json |
| placement questions over all inputs: total / most for one input / inputs with a question | 383 / 4 / 246 | queries_live.json |
| placement answers by state/origin/basis | DECIDED/direct/None 316, DECIDED/estimated/generated 5, DECIDED/estimated/proximity 2, MULTIPLE/direct/None 11, UNKNOWN/None/None 26, UNPLACED/None/None 23 | queries_live.json |
| time per input with the placement (median / mean / max, ms) at 1-min load 5.25 | 0.673 / 0.938 / 83.319 | timing_live.json |
| time per input with no placement (median / mean / max, ms) at 1-min load 5.20 | 0.635 / 0.932 / 64.88 | timing_none.json |
| members of the two read types: members / frames tried / newly readable | 111 / 222 / 124 | probe_members.txt |
| placement predicates (ns=P headwords): all / written with ASCII only | 10971 / 0 | probe_members.txt |
| event cross with the placement, event_cross_sentences: sentences read / arms / AGREE / DISAGREE / NOT_CHECKED | 70 / 174 / 36 / 1 / 137 | events_live.json |
| event cross with the placement, new_data: sentences read / arms / AGREE / DISAGREE / NOT_CHECKED | 54 / 143 / 83 / 0 / 60 | events_live.json |
| event cross with the placement, rest: sentences read / arms / AGREE / DISAGREE / NOT_CHECKED | 241 / 578 / 181 / 7 / 390 | events_live.json |
| event cross DISAGREE arms in all (and how many of them were typed by the entry) | 8 (0) | events_live.json |
