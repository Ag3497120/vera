# T8 layers -- effort standard (S300, 90 questions: 60 answerable, 30 unanswerable)

The list = every layer-0 entry of the three tiers + the upper-layer entries of the variants named, each labelled (tier, layer, variant); nothing merged or summed. 'Gold in a candidate' = a gold string occurs in a word of an entry (oracle rule of T6ab / T7b). NOTE an upper-layer entry's words are the base words under the bundled lower states (N-19), so an upper entry is a larger bag of words than a layer-0 entry: see the size rows.

## Candidate quality: answerable questions (60)

| configuration | gold in a candidate | ... single ANSWER | ... inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off | gold in a candidate of <= 21 words |
|---|---|---|---|---|---|---|---|---|
| layers off (layer 0 = T7b) | 29 | 1 | 28 | 3 | 28 | 7.0 (69) | 0 () | 29 |
| layers on, same, query A | 32 | 0 | 32 | 0 | 28 | 16.0 (76) | 3 (a32,a34,a37) | 31 |
| layers on, same, query B | 30 | 1 | 29 | 3 | 27 | 15.5 (78) | 1 (a37) | 30 |
| layers on, same, query A+B | 32 | 0 | 32 | 0 | 28 | 23.0 (85) | 3 (a32,a34,a37) | 31 |
| layers on, compress, query A | 38 | 0 | 38 | 1 | 21 | 15.0 (76) | 9 (a01,a26,a29,a32,a34,a35,a37,a40,a50) | 38 |
| layers on, compress, query B | 31 | 1 | 30 | 3 | 26 | 18.0 (76) | 2 (a11,a37) | 31 |
| layers on, compress, query A+B | 39 | 0 | 39 | 1 | 20 | 26.0 (83) | 10 (a01,a11,a26,a29,a32,a34,a35,a37,a40,a50) | 39 |

## Unanswerable questions (30): can a user reject what is shown?

| configuration | no candidate | only a list (rejectable) | a single answer (looks confident: wrong) |
|---|---|---|---|
| layers off (layer 0 = T7b) | 3 | 25 | 2 |
| layers on, same, query A | 0 | 29 | 1 |
| layers on, same, query B | 3 | 27 | 0 |
| layers on, same, query A+B | 0 | 29 | 1 |
| layers on, compress, query A | 1 | 28 | 1 |
| layers on, compress, query B | 3 | 27 | 0 |
| layers on, compress, query A+B | 1 | 28 | 1 |

## Size of the entries (words per entry)

| entries | count | words per entry median | p90 | max | holding gold: count | words per gold-holding entry median |
|---|---|---|---|---|---|---|
| layer 0 (all tiers) | 799 | 5.0 | 10.0 | 21 | 283 | 5.0 |
| layer 1+, same, A | 513 | 154.0 | 207.0 | 320 | 45 | 19.0 |
| layer 1+, same, B | 414 | 150.0 | 201.0 | 324 | 39 | 19.0 |
| layer 1+, compress, A | 426 | 118.5 | 166.0 | 191 | 30 | 9.0 |
| layer 1+, compress, B | 455 | 118.0 | 168.0 | 191 | 20 | 10.5 |

## How many questions stack, and why

| granularity | questions with a layer (any tier) | by tier RUN / WORD / CHAR | caused by a full cross (growth budget) | caused by a query-time collapse (no fixed point) | both | layer 2+ built | needed another layer but the effort bound stopped it | upper reads marked partial |
|---|---|---|---|---|---|---|---|---|
| same | 90 | 44 / 74 / 90 | 0 | 0 | 90 | 90 | 81 | 78 |
| compress | 90 | 44 / 74 / 90 | 0 | 0 | 90 | 81 | 48 | 82 |

## Time per question (seconds, 6 worker processes ran at once: inflated by contention)

| | median | mean | p90 | max |
|---|---|---|---|---|
| layer 0 (layers off) | 39.3 | 56.9 | 122.3 | 361.6 |
| layers added, same | 39.1 | 50.6 | 88.0 | 249.6 |
| total layer 0 + layers, same | 81.1 | 107.5 | 202.5 | 443.5 |
| layers added, compress | 21.1 | 27.2 | 65.0 | 154.6 |
| total layer 0 + layers, compress | 61.4 | 84.2 | 158.2 | 462.0 |

## Trace through the layers

- same: 761 upper-layer runs, every word traced (trace_ok): 761 / 761
- compress: 658 upper-layer runs, every word traced (trace_ok): 658 / 658

## Reference only: rule-B scores of the list (right = the list is ONE entry that holds gold; wrong = one entry without gold or an answer to an unanswerable question; abstain = otherwise)

| configuration | right | wrong | abstain |
|---|---|---|---|
| layers off (layer 0 = T7b) | 1 | 5 | 84 |
| layers on, same, query A | 0 | 2 | 88 |
| layers on, same, query B | 1 | 0 | 89 |
| layers on, same, query A+B | 0 | 2 | 88 |
| layers on, compress, query A | 0 | 1 | 89 |
| layers on, compress, query B | 1 | 0 | 89 |
| layers on, compress, query A+B | 0 | 1 | 89 |

