# T8 layers -- effort fast (S300, 90 questions: 60 answerable, 30 unanswerable)

The list = every layer-0 entry of the three tiers + the upper-layer entries of the variants named, each labelled (tier, layer, variant); nothing merged or summed. 'Gold in a candidate' = a gold string occurs in a word of an entry (oracle rule of T6ab / T7b). NOTE an upper-layer entry's words are the base words under the bundled lower states (N-19), so an upper entry is a larger bag of words than a layer-0 entry: see the size rows.

## Candidate quality: answerable questions (60)

| configuration | gold in a candidate | ... single ANSWER | ... inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off | gold in a candidate of <= 21 words |
|---|---|---|---|---|---|---|---|---|
| layers off (layer 0 = T7b) | 28 | 4 | 24 | 5 | 27 | 6.0 (51) | 0 () | 28 |
| layers on, same, query A | 30 | 0 | 30 | 0 | 30 | 6.5 (53) | 2 (a32,a37) | 30 |
| layers on, same, query B | 28 | 4 | 24 | 5 | 27 | 8.5 (52) | 0 () | 28 |
| layers on, same, query A+B | 30 | 0 | 30 | 0 | 30 | 10.0 (54) | 2 (a32,a37) | 30 |
| layers on, compress, query A | 36 | 2 | 34 | 2 | 22 | 7.0 (53) | 8 (a01,a11,a26,a29,a32,a35,a40,a50) | 36 |
| layers on, compress, query B | 29 | 4 | 25 | 5 | 26 | 7.0 (53) | 1 (a11) | 29 |
| layers on, compress, query A+B | 36 | 2 | 34 | 2 | 22 | 9.0 (55) | 8 (a01,a11,a26,a29,a32,a35,a40,a50) | 36 |

## Unanswerable questions (30): can a user reject what is shown?

| configuration | no candidate | only a list (rejectable) | a single answer (looks confident: wrong) |
|---|---|---|---|
| layers off (layer 0 = T7b) | 4 | 22 | 4 |
| layers on, same, query A | 1 | 26 | 3 |
| layers on, same, query B | 4 | 26 | 0 |
| layers on, same, query A+B | 1 | 27 | 2 |
| layers on, compress, query A | 3 | 26 | 1 |
| layers on, compress, query B | 4 | 26 | 0 |
| layers on, compress, query A+B | 3 | 26 | 1 |

## Size of the entries (words per entry)

| entries | count | words per entry median | p90 | max | holding gold: count | words per gold-holding entry median |
|---|---|---|---|---|---|---|
| layer 0 (all tiers) | 497 | 5.0 | 10.0 | 21 | 218 | 5.0 |
| layer 1+, same, A | 165 | 136.0 | 170.0 | 190 | 14 | 16.0 |
| layer 1+, same, B | 135 | 134.0 | 165.0 | 175 | 6 | 23.0 |
| layer 1+, compress, A | 106 | 93.5 | 143.0 | 165 | 18 | 8.5 |
| layer 1+, compress, B | 82 | 55.5 | 142.0 | 171 | 10 | 9.0 |

## How many questions stack, and why

| granularity | questions with a layer (any tier) | by tier RUN / WORD / CHAR | caused by a full cross (growth budget) | caused by a query-time collapse (no fixed point) | both | layer 2+ built | needed another layer but the effort bound stopped it | upper reads marked partial |
|---|---|---|---|---|---|---|---|---|
| same | 90 | 44 / 74 / 90 | 4 | 0 | 86 | 0 | 87 | 86 |
| compress | 90 | 44 / 74 / 90 | 4 | 0 | 86 | 0 | 85 | 86 |

## Time per question (seconds, 6 worker processes ran at once: inflated by contention)

| | median | mean | p90 | max |
|---|---|---|---|---|
| layer 0 (layers off) | 3.4 | 7.2 | 15.2 | 69.0 |
| layers added, same | 0.4 | 0.7 | 1.5 | 3.9 |
| total layer 0 + layers, same | 4.1 | 7.9 | 17.3 | 69.3 |
| layers added, compress | 0.1 | 0.2 | 0.4 | 1.9 |
| total layer 0 + layers, compress | 3.4 | 7.4 | 15.6 | 70.7 |

## Trace through the layers

- same: 416 upper-layer runs, every word traced (trace_ok): 416 / 416
- compress: 416 upper-layer runs, every word traced (trace_ok): 416 / 416

## Reference only: rule-B scores of the list (right = the list is ONE entry that holds gold; wrong = one entry without gold or an answer to an unanswerable question; abstain = otherwise)

| configuration | right | wrong | abstain |
|---|---|---|---|
| layers off (layer 0 = T7b) | 4 | 11 | 75 |
| layers on, same, query A | 0 | 7 | 83 |
| layers on, same, query B | 4 | 1 | 85 |
| layers on, same, query A+B | 0 | 4 | 86 |
| layers on, compress, query A | 2 | 5 | 83 |
| layers on, compress, query B | 4 | 1 | 85 |
| layers on, compress, query A+B | 2 | 4 | 84 |

