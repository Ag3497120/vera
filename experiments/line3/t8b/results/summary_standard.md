# T8b path-word candidates -- effort standard (S300, 90 questions: 60 answerable, 30 unanswerable)

The list = every layer-0 entry of the three tiers + the upper-layer entries of the configuration, each labelled; nothing merged. 'Gold in a candidate' = a gold string occurs in a word of an entry (oracle rule of T6ab / T7b / T8). Upper-layer candidates of T8 were bags (N-19 expanded every bundle to all words of the lower state); T8b shows only the path words read under the question from the lower crosses packed in the bundles.

## Candidate quality: answerable questions (60)

| configuration | gold in a candidate | ... single ANSWER | ... inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off | gold held only by an UPPER candidate: its words median |
|---|---|---|---|---|---|---|---|---|
| layers off (layer 0 = T7b) | 29 | 1 | 28 | 3 | 28 | 7.0 (69) | 0 | - |
| T8 bag, compress, A (previous default candidate) | 38 | 0 | 38 | 1 | 21 | 15.0 (76) | 9 | 7.0 |
| T8b PATH words, compress, A  [new default] | 30 | 1 | 29 | 3 | 27 | 12.0 (72) | 1 | 10.0 |
| T8b PATH words, compress, B | 30 | 1 | 29 | 3 | 27 | 13.0 (72) | 1 | 6.0 |

## Unanswerable questions (30): can a user reject what is shown?

| configuration | no candidate | only a list (rejectable) | a single answer (looks confident: wrong) |
|---|---|---|---|
| layers off (layer 0 = T7b) | 3 | 25 | 2 |
| T8 bag, compress, A (previous default candidate) | 1 | 28 | 1 |
| T8b PATH words, compress, A  [new default] | 3 | 26 | 1 |
| T8b PATH words, compress, B | 3 | 26 | 1 |

## Size of the UPPER-layer candidates (words per candidate), answerable questions

| configuration | upper candidates | words median | p90 | max | holding gold: count | words per gold-holding candidate: median / max | upper candidates per question (median / max) |
|---|---|---|---|---|---|---|---|
| layer 0 (for scale) | 799 | 5.0 | 10.0 | 21 | - | - | - |
| T8 bag, compress, A (previous default candidate) | 426 | 118.5 | 166.0 | 191 | 30 | 9.0 / 74 | 6.0 / 37 |
| T8b PATH words, compress, A  [new default] | 210 | 24.0 | 38.0 | 58 | 20 | 7.0 / 36 | 4.0 / 9 |
| T8b PATH words, compress, B | 239 | 24.0 | 38.0 | 47 | 15 | 7.0 / 45 | 3.0 / 13 |

## Path-word upper candidates: what the read gave (compress, A)

- [cA] upper runs: 345; upper entries: 321; upper entries dropped because the lower crosses read no path under the question: 512
- [cA] every word of every entry has a source sentence: 321 / 321 entries; lower crosses read per entry median 10.0 max 30; source sentences per entry median 96.0

## Time per question (seconds; other measurements ran at the same time: inflated by contention)

| | median | mean | p90 | max |
|---|---|---|---|---|
| layer 0 (layers off) | 29.4 | 37.1 | 90.4 | 202.6 |
| layers added, path cA | 50.3 | 55.2 | 99.4 | 176.5 |
| layers added, path cB | 43.6 | 44.8 | 97.2 | 145.0 |
| layers added, T8 bag compress (T8 run, A+B both variants; other load) | 21.1 | 27.2 | 65.0 | 154.6 |

## Trace through the layers

- path cA: 345 upper runs, every word traced (trace_ok): 345 / 345
- path cB: 313 upper runs, every word traced (trace_ok): 313 / 313

## Reference only: rule-B scores (right = the list is ONE entry that holds gold; wrong = one entry without gold or an answer to an unanswerable question; abstain = otherwise)

| configuration | right | wrong | abstain |
|---|---|---|---|
| layers off (layer 0 = T7b) | 1 | 5 | 84 |
| T8 bag, compress, A (previous default candidate) | 0 | 1 | 89 |
| T8b PATH words, compress, A  [new default] | 1 | 2 | 87 |
| T8b PATH words, compress, B | 1 | 2 | 87 |

