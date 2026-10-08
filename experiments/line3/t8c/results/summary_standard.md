# T8c stable-state candidates -- effort standard (S300, 90 questions: 60 answerable, 30 unanswerable)

The list = every layer-0 entry of the three tiers + the upper-layer entries of the configuration, each labelled; nothing merged. 'Gold in a candidate' = a gold string occurs in a word of an entry (oracle rule of T6ab / T7b / T8). Upper-layer candidates of T8 were bags (N-19 expanded every bundle to all words of the lower state); T8b shows the path words of the full-question read; T8c the path words of the last stable state while the question is applied unit by unit.

## Candidate quality: answerable questions (60)

| configuration | gold in a candidate | ... single ANSWER | ... inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off | gold held only by an UPPER candidate: its words median |
|---|---|---|---|---|---|---|---|---|
| layers off (layer 0 = T7b) | 29 | 1 | 28 | 3 | 28 | 7.0 (69) | 0 | - |
| T8 bag, compress, A | 38 | 0 | 38 | 1 | 21 | 15.0 (76) | 9 | 7.0 |
| T8b PATH words (full-question read), compress, A  [current default] | 30 | 1 | 29 | 3 | 27 | 12.0 (72) | 1 | 10.0 |
| T8c STABLE-state path words, compress, A | 29 | 1 | 28 | 3 | 28 | 13.0 (73) | 0 | - |
| T8c STABLE-state path words, compress, B | 30 | 1 | 29 | 3 | 27 | 12.5 (73) | 1 | 11.0 |

## Unanswerable questions (30): can a user reject what is shown?

| configuration | no candidate | only a list (rejectable) | a single answer (looks confident: wrong) |
|---|---|---|---|
| layers off (layer 0 = T7b) | 3 | 25 | 2 |
| T8 bag, compress, A | 1 | 28 | 1 |
| T8b PATH words (full-question read), compress, A  [current default] | 3 | 26 | 1 |
| T8c STABLE-state path words, compress, A | 3 | 26 | 1 |
| T8c STABLE-state path words, compress, B | 3 | 26 | 1 |

## Size of the UPPER-layer candidates (words per candidate), answerable questions

| configuration | upper candidates | words median | p90 | max | holding gold: count | words per gold-holding candidate: median / max | upper candidates per question (median / max) |
|---|---|---|---|---|---|---|---|
| layer 0 (for scale) | 799 | 5.0 | 10.0 | 21 | - | - | - |
| T8 bag, compress, A | 426 | 118.5 | 166.0 | 191 | 30 | 9.0 / 74 | 6.0 / 37 |
| T8b PATH words (full-question read), compress, A  [current default] | 210 | 24.0 | 38.0 | 58 | 20 | 7.0 / 36 | 4.0 / 9 |
| T8c STABLE-state path words, compress, A | 192 | 20.0 | 31.0 | 50 | 5 | 7.0 / 7 | 3.0 / 8 |
| T8c STABLE-state path words, compress, B | 219 | 18.0 | 31.0 | 38 | 6 | 7.0 / 11 | 3.0 / 12 |

## What the lower reads gave

- [pathA] upper runs: 345; upper entries: 321; upper entries dropped because the lower crosses gave no path words: 512; entries with every word sourced: 321 / 321
- [stableA] upper runs: 345; upper entries: 273; upper entries dropped because the lower crosses gave no path words: 748; entries with every word sourced: 273 / 273
- [stableB] upper runs: 313; upper entries: 312; upper entries dropped because the lower crosses gave no path words: 593; entries with every word sourced: 312 / 312

## T8c boundary records (per lower cross read down, over all questions)

| config | lower reads | stable through the whole question (no restore) | restored | ... boundary at step 1 (backup = step 0, no unit applied: no path can be read) | ... restored at step >= 2 | restored states that gave path words | not restored, gave path words |
|---|---|---|---|---|---|---|---|
| stableA | 3533 | 1143 | 2390 | 1838 | 552 | 327 | 562 |

  [stableA] restored: last stable step histogram {0: 1838, 1: 193, 2: 111, 3: 110, 4: 55, 5: 66, 6: 3, 7: 4, 8: 1, 9: 2, 10: 2, 12: 3, 13: 2}; units per read median 10.0
| stableB | 3056 | 1021 | 2035 | 1495 | 540 | 339 | 488 |

  [stableB] restored: last stable step histogram {0: 1495, 1: 145, 2: 137, 3: 103, 4: 55, 5: 71, 6: 22, 7: 3, 8: 3, 9: 1}; units per read median 10.0

## Time per question (seconds; other measurements ran at the same time: inflated by contention)

| | median | mean | p90 | max |
|---|---|---|---|---|
| layer 0 (layers off) | 21.7 | 27.7 | 66.5 | 139.8 |
| layers added, bagA | 5.9 | 7.4 | 16.7 | 37.7 |
| layers added, pathA | 37.7 | 41.6 | 78.8 | 137.6 |
| layers added, stableA | 61.1 | 64.5 | 116.1 | 163.8 |
| layers added, stableB | 45.8 | 52.2 | 98.7 | 175.9 |

## Trace through the layers

- bagA: 345 upper runs, every word traced (trace_ok): 345 / 345
- pathA: 345 upper runs, every word traced (trace_ok): 345 / 345
- stableA: 345 upper runs, every word traced (trace_ok): 345 / 345
- stableB: 313 upper runs, every word traced (trace_ok): 313 / 313

## Reference only: rule-B scores (right = the list is ONE entry that holds gold; wrong = one entry without gold or an answer to an unanswerable question; abstain = otherwise)

| configuration | right | wrong | abstain |
|---|---|---|---|
| layers off (layer 0 = T7b) | 1 | 5 | 84 |
| T8 bag, compress, A | 0 | 1 | 89 |
| T8b PATH words (full-question read), compress, A  [current default] | 1 | 2 | 87 |
| T8c STABLE-state path words, compress, A | 1 | 2 | 87 |
| T8c STABLE-state path words, compress, B | 1 | 3 | 86 |

