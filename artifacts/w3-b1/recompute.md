| item | value | source (artifacts/w3-b1/) |
|---|---|---|
| new data: rows (ja_r8 / en_r4) | 213 (197 / 16) | tests/reading_soundness/ja_r8.jsonl, en_r4.jsonl |
| new data: path U, read-expected / abstain-expected | 45 / 65 | ja_r8.jsonl, en_r4.jsonl (r8_counts.txt) |
| new data: path S4, read-expected / abstain-expected | 36 / 51 | ja_r8.jsonl, en_r4.jsonl (r8_counts.txt) |
| new data: path EN, read-expected / abstain-expected | 0 / 16 | ja_r8.jsonl, en_r4.jsonl (r8_counts.txt) |
| new data: path U, rows per predicate type (read-expected + abstain-expected) | P_ACT 0+4, P_CHANGE 0+4, P_COGNITION 0+4, P_COMMUNICATE 21+12, P_CONSUME 0+4, P_CREATE 0+4, P_EMOTION 0+4, P_EXIST 0+4, P_GIVE 0+4, P_MOVE 24+8, P_PERCEIVE 0+4, P_POSSESS 0+4, P_STATE 0+5 | ja_r8.jsonl |
| round 3 data ja_r9: rows (path U / path S4) | 60 (30 / 30) | tests/reading_soundness/ja_r9.jsonl, r9_counts.txt |
| round 3 data ja_r9: read-expected / abstain-expected, path U and path S4 | 6 / 24, 6 / 24 | ja_r9.jsonl, r9_counts.txt |
| ja_r9 through the entry with the placement, without the gate on the ending (written before the gate): verdicts | abstain 15, correct 28, incomplete 1, misread 16 | r9_before_gate_live.json |
| ja_r9 without the gate: abstain-expected rows the entry reads | 33 | r9_before_gate_live.json |
| ja_r9 through the entry with the placement, with the gate on the ending: verdicts | abstain 50, correct 10 | r9_entry_check.json |
| ja_r9 with the gate: misread / incomplete / UNJUDGED | 0 / 0 / 0 | r9_entry_check.json |
| ja_r9 with the gate: bad verdicts identical to the output with no placement | 0 of 0 | r9_entry_check.json |
| ja_r9 with the gate: read-expected rows the entry abstains on / abstain-expected rows the entry reads | 2 / 0 | r9_entry_check.json |
| ja_r9 with the gate: second reasons by prefix | PLACEMENT_PART_NOT_NP 1, PLACEMENT_PREDICATE_POSSIBLY_DERIVED 2, PLACEMENT_PREDICATE_TAIL_UNINTERPRETED 32, PLACEMENT_REREAD_ABSTAINS 8 | r9_entry_check.json |
| round 4 data ja_r10: rows (path U / path S4) | 78 (37 / 41) | tests/reading_soundness/ja_r10.jsonl, r10_counts.txt |
| round 4 data ja_r10: read-expected / abstain-expected, path U and path S4 | 10 / 27, 9 / 32 | ja_r10.jsonl, r10_counts.txt |
| round 4 data ja_r10: rows by kind | dekiru 2, godan_plain 11, ichidan_plain 11, ichidan_upper 2, potential 31, ranuki 2, sa_not_a 6, short_causative 11, spontaneous 2 | ja_r10.jsonl, r10_counts.txt |
| ja_r10 through the entry with the placement, without the gate on a head that may be a derived verb (written before the gate): verdicts | abstain 43, correct 24, misread 11 | r10_before_gate_live.json |
| ja_r10 without the gate: misread / incomplete / UNJUDGED | 11 / 0 / 0 | r10_before_gate_live.json |
| ja_r10 through the entry with the placement, with the gate: verdicts | abstain 54, correct 24 | r10_entry_check.json |
| ja_r10 with the gate: misread / incomplete / UNJUDGED | 0 / 0 / 0 | r10_entry_check.json |
| ja_r10 with the gate: read-expected rows the entry abstains on / abstain-expected rows the entry reads | 4 / 5 | r10_entry_check.json |
| ja_r10 with the gate: second reasons by prefix | PLACEMENT_DIRECT_VIA_GENERATED 1, PLACEMENT_PART_NO_ROLE 1, PLACEMENT_PREDICATE_POSSIBLY_DERIVED 11, PLACEMENT_REREAD_ABSTAINS 20, PLACEMENT_SLOT_EVIDENCE_ONLY 20, PLACEMENT_UNPLACED 1 | r10_entry_check.json |
| ja_r10 rows that the gate on a head that may be a derived verb stopped, by path and kind | S4 short_causative 4, U potential 3, U short_causative 4 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 rows read by the entry with the gate, by path and kind | S4 godan_plain 1, S4 ichidan_upper 2, S4 sa_not_a 2, U godan_plain 7, U ichidan_plain 5, U sa_not_a 3 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, S4 dekiru: read / second reasons by prefix | PLACEMENT_PART_NO_ROLE 1, PLACEMENT_UNPLACED 1 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, S4 godan_plain: read / second reasons by prefix | PLACEMENT_SLOT_EVIDENCE_ONLY 3, read 1 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, S4 ichidan_plain: read / second reasons by prefix | PLACEMENT_SLOT_EVIDENCE_ONLY 5 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, S4 ichidan_upper: read / second reasons by prefix | read 2 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, S4 potential: read / second reasons by prefix | PLACEMENT_DIRECT_VIA_GENERATED 1, PLACEMENT_REREAD_ABSTAINS 2, PLACEMENT_SLOT_EVIDENCE_ONLY 8, one reason only 3 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, S4 ranuki: read / second reasons by prefix | PLACEMENT_REREAD_ABSTAINS 2 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, S4 sa_not_a: read / second reasons by prefix | PLACEMENT_SLOT_EVIDENCE_ONLY 1, read 2 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, S4 short_causative: read / second reasons by prefix | PLACEMENT_PREDICATE_POSSIBLY_DERIVED 4, PLACEMENT_SLOT_EVIDENCE_ONLY 3 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, S4 spontaneous: read / second reasons by prefix | PLACEMENT_REREAD_ABSTAINS 2 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, U godan_plain: read / second reasons by prefix | read 7 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, U ichidan_plain: read / second reasons by prefix | one reason only 1, read 5 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, U potential: read / second reasons by prefix | PLACEMENT_PREDICATE_POSSIBLY_DERIVED 3, PLACEMENT_REREAD_ABSTAINS 14 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, U sa_not_a: read / second reasons by prefix | read 3 | r10_entry_check.json, ja_r10.jsonl |
| ja_r10 with the gate, U short_causative: read / second reasons by prefix | PLACEMENT_PREDICATE_POSSIBLY_DERIVED 4 | r10_entry_check.json, ja_r10.jsonl |
| round 3 -> round 4 (same inputs): read with the placement in round 3 and abstained in round 4, by the file the input comes from | ja_r8.jsonl 4, ja_r9.jsonl 2 | r3_entry_live.jsonl, r4_entry_live.jsonl |
| round 3 -> round 4 (same inputs): read in both with a different output / abstained in round 3 and read in round 4 / abstained in both with a different output | 0 / 0 / 0 | r3_entry_live.jsonl, r4_entry_live.jsonl |
| ja_r8 rows read with the placement before the gate that the gate returned to abstention | 4 of 53 | r2_entry_live.jsonl, r4_entry_live.jsonl |
| inputs read with the placement before the gate and after it with a different output | 0 | r2_entry_live.jsonl, r4_entry_live.jsonl |
| entry with the placement on the new data: verdicts | abstain 120, correct 92, incomplete 1 | r8_entry_check.json |
| entry with the placement on the new data: misread / incomplete / UNJUDGED | 0 / 1 / 0 | r8_entry_check.json |
| entry with the placement on the new data: bad verdicts identical to the output with no placement | 1 of 1 | r8_entry_check.json |
| new data: read-expected rows the entry abstains on / abstain-expected rows the entry reads | 34 / 1 | r8_entry_check.json |
| new data: abstained rows whose second reason is not the registered prefix | 18 | r8_entry_check.json |
| declared exceptions (w3b1_expect_exceptions.json) by kind | baseline_reads 1, reason_differs 18, row_returned_to_abstain 25, trigger_not_reached 9 | tests/reading_soundness/w3b1_expect_exceptions.json |
| base-commit comparison: inputs (x3 + English + B1 samples + event cross sentences + new data) | 2899 | entry_dev.jsonl, entry_live.jsonl |
| base-commit comparison: same / reason_changed | 2469 / 364 | entry_dev.jsonl, entry_live.jsonl, base_diff_summary.txt |
| base-commit comparison: false->readable / readable->false | 66 / 0 | entry_dev.jsonl, entry_live.jsonl, base_diff_summary.txt |
| base-commit comparison: changed (source fields taken out) / changed (as they are) / error_changed | 0 / 0 / 0 | entry_dev.jsonl, entry_live.jsonl |
| false->readable by the file the input comes from | ja_r10.jsonl 9, ja_r8.jsonl 47, ja_r9.jsonl 10 | base_diff.jsonl |
| false->readable verdicts | CORRECT 66 | base_diff.jsonl |
| reason_changed: reasons added, by prefix | PLACEMENT_DIRECT_VIA_GENERATED 3, PLACEMENT_ESTIMATED_GENERATED 5, PLACEMENT_ESTIMATED_NEAR 2, PLACEMENT_FRAME_NOT_READ 79, PLACEMENT_MULTIPLE 11, PLACEMENT_NOT_PREDICATE_TYPE 1, PLACEMENT_PART_MARKER 7, PLACEMENT_PART_NONE 2, PLACEMENT_PART_NOT_FOLLOWED 3, PLACEMENT_PART_NOT_ISOLATED 3, PLACEMENT_PART_NOT_NP 17, PLACEMENT_PART_NO_ROLE 3, PLACEMENT_PART_PARTICLE 2, PLACEMENT_PREDICATE_POSSIBLY_DERIVED 17, PLACEMENT_PREDICATE_TAIL_UNINTERPRETED 32, PLACEMENT_PREDICATE_UNIDENTIFIED 32, PLACEMENT_REREAD_ABSTAINS 28, PLACEMENT_SLOT_EVIDENCE_ONLY 34, PLACEMENT_TYPE_MISMATCH 30, PLACEMENT_UNKNOWN 25, PLACEMENT_UNPLACED 24, PLACEMENT_VOICE_NOT_ACTIVE 4 | entry_dev.jsonl, entry_live.jsonl |
| x3 sentences in the comparison: count / newly readable with the placement | 2217 / 0 | entry_dev.jsonl, entry_live.jsonl |
| reader (document_view) on the x3 sentences: byte-for-byte as the base commit | yes (2217 lines) | x3_after.jsonl, x3_dev.jsonl |
| frozen banks (harness): sentences / changed / misread | 500 / 0 / 0 | soundness_compare.txt |
| a3_check output same as the base commit | yes | a3_dev.txt, a3_after.txt |
| entry with no placement: output equal to the base commit on all inputs | yes | entry_none.jsonl, entry_dev.jsonl |
| answers rewritten to estimated only: newly readable / readable and changed | 0 / 0 | a3_direct_only.txt |
| answers rewritten to multiple only: newly readable / readable and changed | 0 / 0 | a3_direct_only.txt |
| B1 sample B1_v2 through the scorer (no placement reaches the child process): correct / correct_abstain / over_abstain / misread / wrong | 32 / 13 / 20 / 0 / 0 | bs_B1_v2/summary.json |
| B1 sample B1_v2_r2 through the scorer (no placement reaches the child process): correct / correct_abstain / over_abstain / misread / wrong | 11 / 8 / 17 / 0 / 0 | bs_B1_v2_r2/summary.json |
| B1 sample B1_v2_r3 through the scorer (no placement reaches the child process): correct / correct_abstain / over_abstain / misread / wrong | 4 / 0 / 13 / 0 / 0 | bs_B1_v2_r3/summary.json |
| B1 samples in-process with the placement: verdicts | abstain 50, correct 68; misread 0, incomplete 0 | b1_fixtures_live.json |
| placement questions over all inputs: total / most for one input / inputs with a question | 610 / 4 / 361 | queries_live.json |
| placement answers by state/origin/basis | DECIDED/direct/None 543, DECIDED/estimated/generated 5, DECIDED/estimated/proximity 2, MULTIPLE/direct/None 11, UNKNOWN/None/None 25, UNPLACED/None/None 24 | queries_live.json |
| time per input with the placement (median / mean / max, ms) at 1-min load 1.96 | 0.687 / 0.924 / 84.389 | timing_live.json |
| time per input with no placement (median / mean / max, ms) at 1-min load 1.96 | 0.596 / 0.871 / 59.609 | timing_none.json |
| members of the two read types: members / frames tried / newly readable | 111 / 222 / 102 | probe_members.txt |
| placement predicates (ns=P headwords): all / written with ASCII only | 10971 / 0 | probe_members.txt |
| event cross with the placement, event_cross_sentences: sentences read / arms / AGREE / DISAGREE / NOT_CHECKED | 69 / 171 / 35 / 0 / 136 | events_live.json |
| event cross with the placement, new_data: sentences read / arms / AGREE / DISAGREE / NOT_CHECKED | 78 / 198 / 113 / 0 / 85 | events_live.json |
| event cross with the placement, rest: sentences read / arms / AGREE / DISAGREE / NOT_CHECKED | 198 / 479 / 155 / 4 / 320 | events_live.json |
| event cross DISAGREE arms in all (and how many of them were typed by the entry) | 4 (0) | events_live.json |
| integration (W3-b1 + W5-a, base 2732274): inputs / the merged entry with no placement equals the base commit byte for byte (rows) | 2899 / 2899 | integ_combination.txt |
| integration (W3-b1 + W5-a, base 2732274): inputs the commit before W5-a read and the base commit abstains on (W5-a): all / read by the merged entry with the placement / with a second reason (the typed path ran) | 48 / 0 / 0 | integ_combination.txt |
| integration (W3-b1 + W5-a, base 2732274): those inputs by the type of the first reason | {"AGENT_EVIDENCE_MISSING": 6, "PATH_ROLE_NOT_MAPPED": 1, "SUBJECT_TYPE_UNDETERMINED": 1, "UNDETERMINED_VOICE": 8, "UNSUPPORTED_CLAUSE": 32} | integ_combination.txt |
| integration (W3-b1 + W5-a, base 2732274): inputs abstained on both before and after W5-a with a different output (reason changed by W5-a) | 118 | integ_combination.txt |
| integration (W3-b1 + W5-a, base 2732274): read by the typed path (read with the placement, abstained with none): merged entry / W3-b1 tree alone | 66 / 66 | integ_combination.txt |
| integration (W3-b1 + W5-a, base 2732274): of those: identical output in both / different output / only the merged entry / only the W3-b1 tree alone (W5-a stopped it) | 66 / 0 / 0 / 0 | integ_combination.txt |
| integration (W3-b1 + W5-a, base 2732274): inputs read by the W3-b1 tree alone and stopped by W5-a (listed in full) | none | integ_combination.txt |
| integration (W3-b1 + W5-a, base 2732274): declared exceptions whose why names section 10A, by K (all declared) | section 10A K63 6 (of 53) | tests/reading_soundness/w3b1_expect_exceptions.json |
| integration (W3-b1 + W5-a, base 2732274): declared exceptions: unchanged / rewritten compared with round 4 | 47 / 6 | w3b1_expect_exceptions.json, r4_w3b1_expect_exceptions.json |
| integration (W3-b1 + W5-a, base 2732274): ja_r9 rows the commit before W5-a reads and the base commit abstains on | 1 | r4_entry_dev.jsonl, entry_dev.jsonl |
| integration (W3-b1 + W5-a, base 2732274): W5-a measurement inputs (2344): merged entry with no placement equals W5-a round 3 byte for byte | yes | w5a_entry_none.jsonl, artifacts/w5-a/r3/entry_after.jsonl |
| integration (W3-b1 + W5-a, base 2732274): W5-a measurement inputs, merged entry with the placement against W5-a entry_before: readable->false / false->readable / changed / reason_changed | 43 / 0 / 0 / 215 | w5a_entry_live.jsonl, artifacts/w5-a/entry_before.jsonl |
| integration (W3-b1 + W5-a, base 2732274): W5-a measurement inputs, with no placement (same comparison): readable->false / false->readable / changed / reason_changed | 43 / 0 / 0 / 103 | w5a_entry_none.jsonl, artifacts/w5-a/entry_before.jsonl |
| integration (W3-b1 + W5-a, base 2732274): W5-a measurement inputs: the readable->false set and its first reasons with the placement are the same as W5-a round 3 | yes (43 inputs) | w5a_entry_live.jsonl, w5a_entry_none.jsonl, artifacts/w5-a/r3/entry_after.jsonl |
| integration (W3-b1 + W5-a, base 2732274): E1 (events parity) lines | E1_SAME, E1_EQUALS_BASE_2732274, E1_SAME_WITH_PLACEMENT | e1.txt |
