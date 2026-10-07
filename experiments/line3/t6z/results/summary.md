## T6z results (S300 RUN; new defaults merge_sections + similar=word_set + on-demand budget raise; 90 fixed questions; search budget 64/8; level mid)

(1) strict grading, T0 grader (answerable a01..a60; unanswerable = fict + attr, answered = wrong)

| system | correct/wrong/abstain (answerable) | unanswerable answered (fict+attr) | answer verdicts |
|---|---|---|---|
| T0 legacy a1 | 45/7/8 | 3+8 = 11 | - |
| T0 legacy a2 | 44/9/7 | 0+10 = 10 | - |
| T6w rule B (path words; no merge) | 17/3/40 | 2+2 = 4 | ANSWER 24, CHOICE 18, none 48 |
| T6w rule A (centre) | 2/18/40 | 2+2 = 4 | same |
| T6y rule B (merge_sections, option) | 18/3/39 | 2+2 = 4 | ANSWER 25, CHOICE 17, none 48 |
| T6z rule B official (word set of the entry) | 18/3/39 | 2+2 = 4 | {'ANSWER': 25, 'CHOICE': 20, 'None': 45} |
| T6z rule B' (arrangements' path texts) | 18/3/39 | 2+2 = 4 | {'ANSWER': 25, 'CHOICE': 20, 'None': 45} |
| T6z rule A reference (centre) | 2/19/39 | 2+2 = 4 | {'ANSWER': 25, 'CHOICE': 20, 'None': 45} |

T6z rule B per-question outcome changes vs T6y/T6x-default are listed in (6).

(2) gold in the answer, answerable (60)

| answerable | with a read-out | gold in some arrangement's path text | gold in the word sets (joined) | gold as a part of some word | single-entry answers | single-entry with gold (word set) | single-entry with gold (arrangement path text) |
|---|---|---|---|---|---|---|---|
| 60 | 36 | 30 | 30 | 29 | 21 | 18 | 18 |

Question dependence (gold of question i against the answers of question j, answerable with a read-out): arrangement path texts: matched 30/36 (0.83), mismatched mean fraction 0.010, ratio 80.8; word sets: matched 30/36 (0.83), mismatched 0.011, ratio 75.0

(3) list sizes (entries), collapse

- questions with a read-out: 45 of 90 (ANSWER 25, list 20, UNKNOWN_NO_PATH 0); no adopted state: 45
- arrangements (items after merge_sections) per question min/median/max: 1/1/7560
- entries per question min/median/max: 1/1/89
- lists (CHOICE) entries min/median/max: 2/25.5/89; too_many flagged (>20): 12
- lists before the word-set collapse (arrangements > 1): 20; collapse to ONE entry (an ANSWER): 0 (); lists that stay: 20
- reduction arrangements -> entries over the lists that stay (sum): 13246 -> 680
- stay-lists with gold in some arrangement path: 12 of 20 (answerable only: 12 of 15)
- arrangements per entry: max 534, entries with >1 arrangement: 580 of 705; entries whose arrangements have different centres: 45

(4) on-demand budget raise, trace check, time

- questions where a raise was needed: 9 (a06, a10, a14, a19, a23, a30, a32, a42, a57); of those with a state afterwards: a06(CHOICE), a19(CHOICE), a32(CHOICE)
- trace check: 45 / 45 read-outs 100% (words traced 350256 / 350256); failures: 0
- per-question time (s; ask incl. raise + read-out + trace; 9 workers in parallel) median/max/sum: 0.01/191.7/1372; read-out+trace of the largest: 2.1

(5) cycle verdict mix: {'AMBIGUOUS': 1, 'ANSWER': 34, 'CHOICE': 11, 'UNKNOWN_NO_EVIDENCE': 31, 'UNKNOWN_NO_FIXED_POINT': 13}

(6) answerable questions whose rule B grade differs from T6x default (the T6w/T6x 17/3/40 run)

- a52: abstain -> correct

(7) every list (arrangements -> entries; gold in some path: Y/N)

- a05 149->19Y, a06 7560->45Y, a11 343->89N, a16 125->34Y, a19 1026->22Y, a24 215->65Y, a27 130->42Y, a32 1890->26N, a33 64->11Y, a37 148->18N, a43 123->18Y, a47 84->7Y, a48 78->25Y, a55 132->30Y, a59 6->6Y, u03 476->85, u04 2->2, u19 340->88, u26 12->6, u30 343->42
