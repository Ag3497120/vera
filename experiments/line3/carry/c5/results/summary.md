# C5 -- question answering over the carry tower (S300 RUN tower, 90 questions)

Oracle rule: a gold string occurs in a word of an entry of the list (T6ab / T7b / T8). The tower's entries hold own words only; an inherited pack is named, never expanded. Time = wall seconds of one question (one process, other jobs on the machine).

## Candidate quality: answerable questions (60)

| system | a candidate holds the gold | ... single ANSWER | ... inside a list >= 2 | no candidate | candidates, none holds the gold | list size median (max) of lists >= 2 |
|---|---|---|---|---|---|---|
| close fast, path | 4 | 4 | 0 | 56 | 0 | - (-) |
| close standard, path | 4 | 4 | 0 | 54 | 2 | 2.0 (2) |
| close full, path | 4 | 4 | 0 | 52 | 4 | 2.5 (60) |
| close fast, index | 37 | 37 | 0 | 19 | 4 | - (-) |
| close standard, index | 42 | 38 | 4 | 14 | 4 | 2.0 (3) |
| close full, index | 46 | 37 | 9 | 9 | 5 | 4.5 (67) |
| defer fast, path | 3 | 2 | 1 | 56 | 1 | 5.0 (5) |
| defer standard, path | 3 | 2 | 1 | 53 | 4 | 5.0 (5) |
| defer fast, index | 43 | 41 | 2 | 14 | 3 | 4.0 (5) |
| defer standard, index | 51 | 44 | 7 | 6 | 3 | 2.0 (5) |
| flat T7b fast, RUN only | 27 | 18 | 9 | 31 | 2 | 18.0 (42) |
| flat T7b fast, 3 tiers pooled (as shown) | 28 | 4 | 24 | 5 | 27 | 6.0 (51) |

## Unanswerable questions (30): can a user reject what is shown?

| system | no candidate | only a list (rejectable) | a single answer (looks confident: wrong) |
|---|---|---|---|
| close fast, path | 30 | 0 | 0 |
| close standard, path | 28 | 1 | 1 |
| close full, path | 26 | 3 | 1 |
| close fast, index | 25 | 0 | 5 |
| close standard, index | 22 | 2 | 6 |
| close full, index | 19 | 5 | 6 |
| defer fast, path | 30 | 0 | 0 |
| defer standard, path | 28 | 0 | 2 |
| defer fast, index | 24 | 0 | 6 |
| defer standard, index | 21 | 1 | 8 |
| flat T7b fast, RUN only | 23 | 2 | 5 |
| flat T7b fast, 3 tiers pooled (as shown) | 4 | 22 | 4 |

## List sizes (entries per question, all 90)

| system | median | p90 | max | questions with >= 1 entry |
|---|---|---|---|---|
| close fast, path | 0.0 | 0.0 | 1 | 4 |
| close standard, path | 0.0 | 0.0 | 2 | 8 |
| close full, path | 0.0 | 1.0 | 60 | 12 |
| close fast, index | 1.0 | 1.0 | 1 | 46 |
| close standard, index | 1.0 | 1.0 | 3 | 54 |
| close full, index | 1.0 | 4.0 | 67 | 62 |
| defer fast, path | 0.0 | 0.0 | 5 | 4 |
| defer standard, path | 0.0 | 1.0 | 5 | 9 |
| defer fast, index | 1.0 | 1.0 | 5 | 52 |
| defer standard, index | 1.0 | 1.0 | 5 | 63 |
| flat T7b fast, RUN only | 0.0 | 6.0 | 42 | 36 |
| flat T7b fast, 3 tiers pooled (as shown) | 4.0 | 28.0 | 51 | 81 |

## Time, units read, trace (tower systems)

| system | time median s | mean | p90 | max | questions > 10 s | units read per question (median / max) | partial | reads at level 0 / 1 / 2 / 3 (sum) | exact skips (sum) | trace ok / questions | words traced / checked |
|---|---|---|---|---|---|---|---|---|---|---|---|
| close fast, path | 1.8 | 4.4 | 11.2 | 17.6 | 22 | 2.0 / 4 | 9 | 6 / 11 / 78 / 73 | 1526 | 90 / 90 | 24 / 24 |
| close standard, path | 1.8 | 4.6 | 12.8 | 17.4 | 16 | 2.0 / 10 | 4 | 13 / 28 / 94 / 73 | 1595 | 90 / 90 | 63 / 63 |
| close full, path | 1.7 | 4.6 | 12.4 | 20.0 | 16 | 2.0 / 28 | 0 | 40 / 55 / 94 / 73 | 1642 | 90 / 90 | 381 / 381 |
| close fast, index | 2.9 | 4.8 | 11.1 | 17.7 | 24 | 4.0 / 4 | 17 | 59 / 65 / 91 / 73 | 3911 | 90 / 90 | 257 / 257 |
| close standard, index | 3.4 | 5.3 | 12.7 | 17.8 | 24 | 4.0 / 10 | 9 | 77 / 101 / 116 / 73 | 4281 | 90 / 90 | 350 / 350 |
| close full, index | 3.2 | 5.1 | 12.3 | 21.0 | 18 | 4.0 / 40 | 0 | 153 / 151 / 116 / 73 | 4441 | 90 / 90 | 888 / 888 |
| defer fast, path | 1.5 | 1.4 | 2.8 | 4.6 | 0 | 2.0 / 4 | 11 | 7 / 33 / 92 / 68 | 1407 | 90 / 90 | 41 / 41 |
| defer standard, path | 1.3 | 1.4 | 3.0 | 5.3 | 0 | 2.0 / 8 | 3 | 13 / 54 / 97 / 68 | 1479 | 90 / 90 | 71 / 71 |
| defer fast, index | 1.7 | 1.5 | 2.9 | 4.6 | 0 | 4.0 / 4 | 17 | 60 / 69 / 92 / 68 | 2650 | 90 / 90 | 315 / 315 |
| defer standard, index | 1.6 | 1.5 | 2.9 | 5.4 | 0 | 4.0 / 10 | 8 | 83 / 104 / 97 / 68 | 2960 | 90 / 90 | 432 / 432 |

## Verdicts (all 90)

- close fast, path: ANSWER 4, UNKNOWN_NO_EVIDENCE 15, UNKNOWN_NO_PATH 71
- close standard, path: ANSWER 5, CHOICE 3, UNKNOWN_NO_EVIDENCE 15, UNKNOWN_NO_PATH 67
- close full, path: ANSWER 5, CHOICE 7, UNKNOWN_NO_EVIDENCE 15, UNKNOWN_NO_PATH 63
- close fast, index: ANSWER 46, UNKNOWN_NO_EVIDENCE 15, UNKNOWN_NO_PATH 29
- close standard, index: ANSWER 48, CHOICE 6, UNKNOWN_NO_EVIDENCE 15, UNKNOWN_NO_PATH 21
- close full, index: ANSWER 47, CHOICE 15, UNKNOWN_NO_EVIDENCE 15, UNKNOWN_NO_PATH 13
- defer fast, path: ANSWER 3, CHOICE 1, UNKNOWN_NO_EVIDENCE 15, UNKNOWN_NO_PATH 67, UNKNOWN_NO_STATE 4
- defer standard, path: ANSWER 8, CHOICE 1, UNKNOWN_NO_EVIDENCE 15, UNKNOWN_NO_PATH 62, UNKNOWN_NO_STATE 4
- defer fast, index: ANSWER 50, CHOICE 2, UNKNOWN_NO_EVIDENCE 15, UNKNOWN_NO_PATH 23
- defer standard, index: ANSWER 55, CHOICE 8, UNKNOWN_NO_EVIDENCE 15, UNKNOWN_NO_PATH 12

## Where does the gold come from? (answerable questions with a gold candidate)

- close fast, path: gold in a black that is itself an entrance unit (the newest black): 0; gold reached through a lateral link (inherited pack): 0
- close standard, path: gold in a black that is itself an entrance unit (the newest black): 0; gold reached through a lateral link (inherited pack): 0
- close full, path: gold in a black that is itself an entrance unit (the newest black): 0; gold reached through a lateral link (inherited pack): 0
- close fast, index: gold in a black that is itself an entrance unit (the newest black): 0; gold reached through a lateral link (inherited pack): 0
- close standard, index: gold in a black that is itself an entrance unit (the newest black): 0; gold reached through a lateral link (inherited pack): 3
- close full, index: gold in a black that is itself an entrance unit (the newest black): 0; gold reached through a lateral link (inherited pack): 7
- defer fast, path: gold in a black that is itself an entrance unit (the newest black): 0; gold reached through a lateral link (inherited pack): 0
- defer standard, path: gold in a black that is itself an entrance unit (the newest black): 0; gold reached through a lateral link (inherited pack): 0
- defer fast, index: gold in a black that is itself an entrance unit (the newest black): 0; gold reached through a lateral link (inherited pack): 0
- defer standard, index: gold in a black that is itself an entrance unit (the newest black): 0; gold reached through a lateral link (inherited pack): 5
