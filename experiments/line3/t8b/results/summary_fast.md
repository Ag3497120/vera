# T8b path-word candidates -- effort fast (S300, 90 questions: 60 answerable, 30 unanswerable)

The list = every layer-0 entry of the three tiers + the upper-layer entries of the configuration, each labelled; nothing merged. 'Gold in a candidate' = a gold string occurs in a word of an entry (oracle rule of T6ab / T7b / T8). Upper-layer candidates of T8 were bags (N-19 expanded every bundle to all words of the lower state); T8b shows only the path words read under the question from the lower crosses packed in the bundles.

## Candidate quality: answerable questions (60)

| configuration | gold in a candidate | ... single ANSWER | ... inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off | gold held only by an UPPER candidate: its words median |
|---|---|---|---|---|---|---|---|---|
| layers off (layer 0 = T7b) | 28 | 4 | 24 | 5 | 27 | 6.0 (51) | 0 | - |
| T8 bag, compress, A (previous default candidate) | 36 | 2 | 34 | 2 | 22 | 7.0 (53) | 8 | 4.0 |
| T8b PATH words, compress, A  [new default] | 28 | 4 | 24 | 5 | 27 | 7.0 (51) | 0 | - |
| T8b PATH words, compress, B | 28 | 4 | 24 | 5 | 27 | 6.0 (52) | 0 | - |
| T8b PATH words, compress, A, lower read = seed + question | 28 | 4 | 24 | 5 | 27 | 7.0 (51) | 0 | - |
| T8b PATH words, compress, B, lower read = seed + question | 28 | 4 | 24 | 5 | 27 | 6.0 (52) | 0 | - |
| T8b PATH words, same, A | 28 | 3 | 25 | 1 | 31 | 6.0 (51) | 0 | - |

## Unanswerable questions (30): can a user reject what is shown?

| configuration | no candidate | only a list (rejectable) | a single answer (looks confident: wrong) |
|---|---|---|---|
| layers off (layer 0 = T7b) | 4 | 22 | 4 |
| T8 bag, compress, A (previous default candidate) | 3 | 26 | 1 |
| T8b PATH words, compress, A  [new default] | 4 | 24 | 2 |
| T8b PATH words, compress, B | 4 | 23 | 3 |
| T8b PATH words, compress, A, lower read = seed + question | 4 | 24 | 2 |
| T8b PATH words, compress, B, lower read = seed + question | 4 | 23 | 3 |
| T8b PATH words, same, A | 3 | 25 | 2 |

## Size of the UPPER-layer candidates (words per candidate), answerable questions

| configuration | upper candidates | words median | p90 | max | holding gold: count | words per gold-holding candidate: median / max | upper candidates per question (median / max) |
|---|---|---|---|---|---|---|---|
| layer 0 (for scale) | 497 | 5.0 | 10.0 | 21 | - | - | - |
| T8 bag, compress, A (previous default candidate) | 106 | 93.5 | 143.0 | 165 | 18 | 8.5 / 18 | 1.0 / 7 |
| T8b PATH words, compress, A  [new default] | 43 | 18.0 | 33.0 | 35 | 6 | 7.0 / 14 | 1.0 / 3 |
| T8b PATH words, compress, B | 44 | 21.0 | 38.0 | 38 | 5 | 7.0 / 14 | 1.0 / 2 |
| T8b PATH words, compress, A, lower read = seed + question | 45 | 20.0 | 35.0 | 37 | 6 | 7.0 / 14 | 1.0 / 4 |
| T8b PATH words, compress, B, lower read = seed + question | 42 | 20.5 | 35.0 | 35 | 5 | 7.0 / 14 | 1.0 / 2 |
| T8b PATH words, same, A | 59 | 28.0 | 47.0 | 49 | 2 | 6.0 / 6 | 1.0 / 3 |

## Path-word upper candidates: what the read gave (compress, A)

- [cA] upper runs: 208; upper entries: 71; upper entries dropped because the lower crosses read no path under the question: 99
- [cA] every word of every entry has a source sentence: 71 / 71 entries; lower crosses read per entry median 5.0 max 13; source sentences per entry median 86.0
- [cAs] upper runs: 208; upper entries: 71; upper entries dropped because the lower crosses read no path under the question: 98
- [cAs] every word of every entry has a source sentence: 71 / 71 entries; lower crosses read per entry median 5.0 max 13; source sentences per entry median 92.0

## Time per question (seconds; other measurements ran at the same time: inflated by contention)

| | median | mean | p90 | max |
|---|---|---|---|---|
| layer 0 (layers off) | 6.5 | 14.6 | 30.1 | 131.9 |
| layers added, path cA | 10.3 | 13.7 | 33.0 | 54.9 |
| layers added, path cB | 5.8 | 11.0 | 32.3 | 59.2 |
| layers added, path sA | 27.0 | 33.4 | 62.5 | 111.6 |
| layers added, path cAs | 8.6 | 11.1 | 26.7 | 34.6 |
| layers added, path cBs | 4.0 | 8.3 | 22.0 | 43.6 |
| layers added, T8 bag compress (T8 run, A+B both variants; other load) | 0.1 | 0.2 | 0.4 | 1.9 |

## Trace through the layers

- path cA: 208 upper runs, every word traced (trace_ok): 208 / 208
- path cB: 208 upper runs, every word traced (trace_ok): 208 / 208
- path sA: 208 upper runs, every word traced (trace_ok): 208 / 208
- path cAs: 208 upper runs, every word traced (trace_ok): 208 / 208
- path cBs: 208 upper runs, every word traced (trace_ok): 208 / 208

## Reference only: rule-B scores (right = the list is ONE entry that holds gold; wrong = one entry without gold or an answer to an unanswerable question; abstain = otherwise)

| configuration | right | wrong | abstain |
|---|---|---|---|
| layers off (layer 0 = T7b) | 4 | 11 | 75 |
| T8 bag, compress, A (previous default candidate) | 2 | 5 | 83 |
| T8b PATH words, compress, A  [new default] | 4 | 6 | 80 |
| T8b PATH words, compress, B | 4 | 7 | 79 |
| T8b PATH words, compress, A, lower read = seed + question | 4 | 6 | 80 |
| T8b PATH words, compress, B, lower read = seed + question | 4 | 7 | 79 |
| T8b PATH words, same, A | 3 | 9 | 78 |

