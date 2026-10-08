# T7b -- amount of inference presets: time and candidate quality (S300, 90 questions: 60 answerable, 30 unanswerable)

The list shown to the user = every tier's entries, each labelled with its tier (nothing summed or merged). 'Gold in a candidate' = a gold string occurs in a word of an entry (the oracle rule of T6ab). Time = wall seconds of one question, all three tiers, one process.

## Time per question (seconds)

| preset | n | median | mean | p90 | max | sum RUN | sum WORD | sum CHAR | questions > 10 s | > 60 s |
|---|---|---|---|---|---|---|---|---|---|---|
| nodes3 | 90 | 2.1 | 4.6 | 13.2 | 32.0 | 107 | 77 | 225 | 13 | 0 |
| nodes4 | 90 | 3.4 | 7.3 | 14.8 | 71.5 | 217 | 172 | 270 | 23 | 2 |
| nodes6 | 90 | 7.2 | 13.4 | 37.8 | 120.8 | 308 | 494 | 403 | 35 | 3 |
| nodes8 | 90 | 12.0 | 17.3 | 49.6 | 114.4 | 386 | 500 | 668 | 49 | 5 |
| nodes12 | 90 | 26.3 | 30.9 | 70.9 | 139.2 | 489 | 762 | 1527 | 70 | 11 |
| nodes24 | 90 | 49.4 | 49.4 | 93.0 | 193.3 | 499 | 1487 | 2462 | 79 | 29 |
| full | 90 | 108.6 | 169.4 | 404.0 | 617.2 | 1505 | 3756 | 9985 | 83 | 61 |

## How much was read (crosses per tier, per question)

| preset | questions marked partial | crosses read / would read in full (sum over the 90 questions) RUN | WORD | CHAR |
|---|---|---|---|---|
| nodes3 | 89 | 132 / 564 | 210 / 2091 | 251 / 11316 |
| nodes4 | 86 | 208 / 564 | 271 / 2091 | 350 / 11316 |
| nodes6 | 84 | 277 / 564 | 413 / 2091 | 523 / 11316 |
| nodes8 | 82 | 336 / 564 | 489 / 2091 | 677 / 11316 |
| nodes12 | 71 | 372 / 564 | 656 / 2091 | 981 / 11316 |
| nodes24 | 63 | 387 / 564 | 968 / 2091 | 1754 / 11316 |
| full | 0 | 564 / 564 | 2091 / 2091 | 11316 / 11316 |

## Candidate quality: answerable questions (60)

| preset | a candidate holds the gold | ... as the single ANSWER | ... inside a list of >= 2 | no candidate at all | candidates, none holds the gold | list size median (max) of lists >= 2 | gold in RUN / WORD / CHAR |
|---|---|---|---|---|---|---|---|
| nodes3 | 25 | 4 | 21 | 8 | 27 | 4.0 (51) | 25 / 2 / 0 |
| nodes4 | 28 | 4 | 24 | 5 | 27 | 6.0 (51) | 27 / 4 / 0 |
| nodes6 | 29 | 1 | 28 | 3 | 28 | 7.0 (69) | 28 / 5 / 0 |
| nodes8 | 29 | 1 | 28 | 3 | 28 | 7.0 (69) | 28 / 5 / 0 |
| nodes12 | 29 | 1 | 28 | 3 | 28 | 7.0 (94) | 28 / 5 / 0 |
| nodes24 | 29 | 1 | 28 | 3 | 28 | 9.0 (94) | 28 / 5 / 0 |
| full | 30 | 0 | 30 | 2 | 28 | 22.0 (201) | 29 / 5 / 0 |

## Unanswerable questions (30): can a user reject what is shown?

| preset | no candidate (nothing to reject) | only a list (rejectable) | a single answer (looks confident: wrong) |
|---|---|---|---|
| nodes3 | 8 | 19 | 3 |
| nodes4 | 4 | 22 | 4 |
| nodes6 | 4 | 23 | 3 |
| nodes8 | 3 | 24 | 3 |
| nodes12 | 3 | 25 | 2 |
| nodes24 | 3 | 25 | 2 |
| full | 1 | 26 | 3 |

## Per question: does the gold survive the smaller budget? (answerable, against full)

- nodes3: gold present at full but lost at nodes3: 5 (a06,a24,a33,a41,a43); gained: 0 ()
- nodes4: gold present at full but lost at nodes4: 2 (a06,a24); gained: 0 ()
- nodes6: gold present at full but lost at nodes6: 1 (a06); gained: 0 ()
- nodes8: gold present at full but lost at nodes8: 1 (a06); gained: 0 ()
- nodes12: gold present at full but lost at nodes12: 1 (a06); gained: 0 ()
- nodes24: gold present at full but lost at nodes24: 1 (a06); gained: 0 ()
