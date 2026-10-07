# C5 -- question answering over the carry tower (S300 RUN tower, 90 questions)

Oracle rule: a gold string occurs in a word of an entry of the list (T6ab / T7b / T8). The tower's entries hold own words only; an inherited pack is named, never expanded. Time = wall seconds of one question (one process, other jobs on the machine).

## Candidate quality: answerable questions (60)

| system | a candidate holds the gold | ... single ANSWER | ... inside a list >= 2 | no candidate | candidates, none holds the gold | list size median (max) of lists >= 2 |
|---|---|---|---|---|---|---|
| C5 fast (selected path) | 4 | 4 | 0 | 56 | 0 | - (-) |
| C5 standard (selected path) | 4 | 4 | 0 | 54 | 2 | 2.0 (2) |
| C5 fast, index descent | 37 | 37 | 0 | 19 | 4 | - (-) |
| flat T7b fast, RUN only | 27 | 18 | 9 | 31 | 2 | 18.0 (42) |
| flat T7b fast, 3 tiers pooled (as shown) | 28 | 4 | 24 | 5 | 27 | 6.0 (51) |

## Unanswerable questions (30): can a user reject what is shown?

| system | no candidate | only a list (rejectable) | a single answer (looks confident: wrong) |
|---|---|---|---|
| C5 fast (selected path) | 30 | 0 | 0 |
| C5 standard (selected path) | 28 | 1 | 1 |
| C5 fast, index descent | 25 | 0 | 5 |
| flat T7b fast, RUN only | 23 | 2 | 5 |
| flat T7b fast, 3 tiers pooled (as shown) | 4 | 22 | 4 |

## List sizes (entries per question, all 90)

| system | median | p90 | max | questions with >= 1 entry |
|---|---|---|---|---|
| C5 fast (selected path) | 0.0 | 0.0 | 1 | 4 |
| C5 standard (selected path) | 0.0 | 0.0 | 2 | 8 |
| C5 fast, index descent | 1.0 | 1.0 | 1 | 46 |
| flat T7b fast, RUN only | 0.0 | 6.0 | 42 | 36 |
| flat T7b fast, 3 tiers pooled (as shown) | 4.0 | 28.0 | 51 | 81 |

## Time, units read, trace (tower systems)

| system | time median s | mean | p90 | max | questions > 10 s | units read per question (median / max) | partial | reads at level 0 / 1 / 2 / 3 (sum) | exact skips (sum) | trace ok / questions | words traced / checked |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C5 fast (selected path) | 1.6 | 3.8 | 9.6 | 16.0 | 7 | 2.0 / 4 | 9 | 6 / 11 / 78 / 73 | 1526 | 90 / 90 | 24 / 24 |
| C5 standard (selected path) | 1.8 | 4.6 | 12.6 | 17.3 | 13 | 2.0 / 10 | 4 | 13 / 28 / 94 / 73 | 1595 | 90 / 90 | 63 / 63 |
| C5 fast, index descent | 2.8 | 4.5 | 10.4 | 16.9 | 14 | 4.0 / 4 | 17 | 59 / 65 / 91 / 73 | 3911 | 90 / 90 | 257 / 257 |

## Verdicts (all 90)

- C5 fast (selected path): ANSWER 4, UNKNOWN_NO_EVIDENCE 15, UNKNOWN_NO_PATH 71
- C5 standard (selected path): ANSWER 5, CHOICE 3, UNKNOWN_NO_EVIDENCE 15, UNKNOWN_NO_PATH 67
- C5 fast, index descent: ANSWER 46, UNKNOWN_NO_EVIDENCE 15, UNKNOWN_NO_PATH 29

## Where does the gold come from? (answerable questions with a gold candidate)

- C5 fast (selected path): gold in a black that is itself an entrance unit (the newest black): 0; gold reached through a lateral link (inherited pack): 0
- C5 standard (selected path): gold in a black that is itself an entrance unit (the newest black): 0; gold reached through a lateral link (inherited pack): 0
- C5 fast, index descent: gold in a black that is itself an entrance unit (the newest black): 0; gold reached through a lateral link (inherited pack): 0
