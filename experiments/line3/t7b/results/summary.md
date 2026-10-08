# T7b -- amount of inference presets: time and candidate quality (S300, 90 questions: 60 answerable, 30 unanswerable)

The list shown to the user = every tier's entries, each labelled with its tier (nothing summed or merged). 'Gold in a candidate' = a gold string occurs in a word of an entry (the oracle rule of T6ab). Time = wall seconds of one question, all three tiers, one process.

## Time per question (seconds)

| preset | n | median | mean | p90 | max | sum RUN | sum WORD | sum CHAR | questions > 10 s | > 60 s |
|---|---|---|---|---|---|---|---|---|---|---|
| fast | 90 | 3.2 | 6.8 | 14.8 | 68.4 | 196 | 165 | 253 | 19 | 1 |
| standard | 90 | 16.6 | 20.9 | 50.3 | 110.1 | 377 | 548 | 956 | 60 | 6 |
| full | 90 | 108.6 | 169.4 | 404.0 | 617.2 | 1505 | 3756 | 9985 | 83 | 61 |

## How much was read (crosses per tier, per question)

| preset | questions marked partial | crosses read / would read in full (sum over the 90 questions) RUN | WORD | CHAR |
|---|---|---|---|---|
| fast | 86 | 208 / 564 | 271 / 2091 | 350 / 11316 |
| standard | 76 | 352 / 564 | 574 / 2091 | 838 / 11316 |
| full | 0 | 564 / 564 | 2091 / 2091 | 11316 / 11316 |

## Candidate quality: answerable questions (60)

| preset | a candidate holds the gold | ... as the single ANSWER | ... inside a list of >= 2 | no candidate at all | candidates, none holds the gold | list size median (max) of lists >= 2 | gold in RUN / WORD / CHAR |
|---|---|---|---|---|---|---|---|
| fast | 28 | 4 | 24 | 5 | 27 | 6.0 (51) | 27 / 4 / 0 |
| standard | 29 | 1 | 28 | 3 | 28 | 7.0 (69) | 28 / 5 / 0 |
| full | 30 | 0 | 30 | 2 | 28 | 22.0 (201) | 29 / 5 / 0 |

## Unanswerable questions (30): can a user reject what is shown?

| preset | no candidate (nothing to reject) | only a list (rejectable) | a single answer (looks confident: wrong) |
|---|---|---|---|
| fast | 4 | 22 | 4 |
| standard | 3 | 25 | 2 |
| full | 1 | 26 | 3 |

## Per question: does the gold survive the smaller budget? (answerable, against full)

- fast: gold present at full but lost at fast: 2 (a06,a24); gained: 0 ()
- standard: gold present at full but lost at standard: 1 (a06); gained: 0 ()
