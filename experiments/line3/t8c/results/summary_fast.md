# T8c stable-state candidates -- effort fast (S300, 90 questions: 60 answerable, 30 unanswerable)

The list = every layer-0 entry of the three tiers + the upper-layer entries of the configuration, each labelled; nothing merged. 'Gold in a candidate' = a gold string occurs in a word of an entry (oracle rule of T6ab / T7b / T8). Upper-layer candidates of T8 were bags (N-19 expanded every bundle to all words of the lower state); T8b shows the path words of the full-question read; T8c the path words of the last stable state while the question is applied unit by unit.

## Candidate quality: answerable questions (60)

| configuration | gold in a candidate | ... single ANSWER | ... inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off | gold held only by an UPPER candidate: its words median |
|---|---|---|---|---|---|---|---|---|
| layers off (layer 0 = T7b) | 28 | 4 | 24 | 5 | 27 | 6.0 (51) | 0 | - |
| T8 bag, compress, A | 36 | 2 | 34 | 2 | 22 | 7.0 (53) | 8 | 4.0 |
| T8b PATH words (full-question read), compress, A  [current default] | 28 | 4 | 24 | 5 | 27 | 7.0 (51) | 0 | - |
| T8c STABLE-state path words, compress, A | 28 | 3 | 25 | 5 | 27 | 6.5 (51) | 0 | - |
| T8c STABLE-state path words, compress, B | 28 | 4 | 24 | 5 | 27 | 7.0 (52) | 0 | - |

## Unanswerable questions (30): can a user reject what is shown?

| configuration | no candidate | only a list (rejectable) | a single answer (looks confident: wrong) |
|---|---|---|---|
| layers off (layer 0 = T7b) | 4 | 22 | 4 |
| T8 bag, compress, A | 3 | 26 | 1 |
| T8b PATH words (full-question read), compress, A  [current default] | 4 | 24 | 2 |
| T8c STABLE-state path words, compress, A | 4 | 23 | 3 |
| T8c STABLE-state path words, compress, B | 4 | 23 | 3 |

## Size of the UPPER-layer candidates (words per candidate), answerable questions

| configuration | upper candidates | words median | p90 | max | holding gold: count | words per gold-holding candidate: median / max | upper candidates per question (median / max) |
|---|---|---|---|---|---|---|---|
| layer 0 (for scale) | 497 | 5.0 | 10.0 | 21 | - | - | - |
| T8 bag, compress, A | 106 | 93.5 | 143.0 | 165 | 18 | 8.5 / 18 | 1.0 / 7 |
| T8b PATH words (full-question read), compress, A  [current default] | 43 | 18.0 | 33.0 | 35 | 6 | 7.0 / 14 | 1.0 / 3 |
| T8c STABLE-state path words, compress, A | 37 | 16.0 | 20.0 | 25 | 4 | 7.0 / 7 | 0.5 / 3 |
| T8c STABLE-state path words, compress, B | 42 | 18.0 | 27.0 | 27 | 5 | 7.0 / 9 | 1.0 / 3 |

## What the lower reads gave

- [pathA] upper runs: 208; upper entries: 71; upper entries dropped because the lower crosses gave no path words: 99; entries with every word sourced: 71 / 71
- [stableA] upper runs: 208; upper entries: 56; upper entries dropped because the lower crosses gave no path words: 117; entries with every word sourced: 56 / 56
- [stableB] upper runs: 208; upper entries: 60; upper entries dropped because the lower crosses gave no path words: 75; entries with every word sourced: 60 / 60

## T8c boundary records (per lower cross read down, over all questions)

| config | lower reads | stable through the whole question (no restore) | restored | ... boundary at step 1 (backup = step 0, no unit applied: no path can be read) | ... restored at step >= 2 | restored states that gave path words | not restored, gave path words |
|---|---|---|---|---|---|---|---|
| stableA | 687 | 196 | 491 | 398 | 93 | 44 | 58 |

  [stableA] restored: last stable step histogram {0: 398, 1: 26, 2: 10, 3: 8, 4: 22, 5: 24, 6: 2, 7: 1}; units per read median 8.0
| stableB | 582 | 196 | 386 | 286 | 100 | 74 | 59 |

  [stableB] restored: last stable step histogram {0: 286, 1: 16, 2: 64, 3: 10, 4: 5, 5: 3, 6: 1, 7: 1}; units per read median 8.0

## Time per question (seconds; other measurements ran at the same time: inflated by contention)

| | median | mean | p90 | max |
|---|---|---|---|---|
| layer 0 (layers off) | 4.4 | 8.9 | 19.0 | 92.4 |
| layers added, bagA | 0.1 | 0.1 | 0.2 | 1.3 |
| layers added, pathA | 6.7 | 8.2 | 18.8 | 29.0 |
| layers added, stableA | 13.0 | 13.0 | 30.8 | 47.2 |
| layers added, stableB | 11.0 | 10.6 | 22.6 | 36.1 |

## Trace through the layers

- bagA: 208 upper runs, every word traced (trace_ok): 208 / 208
- pathA: 208 upper runs, every word traced (trace_ok): 208 / 208
- stableA: 208 upper runs, every word traced (trace_ok): 208 / 208
- stableB: 208 upper runs, every word traced (trace_ok): 208 / 208

## Reference only: rule-B scores (right = the list is ONE entry that holds gold; wrong = one entry without gold or an answer to an unanswerable question; abstain = otherwise)

| configuration | right | wrong | abstain |
|---|---|---|---|
| layers off (layer 0 = T7b) | 4 | 11 | 75 |
| T8 bag, compress, A | 2 | 5 | 83 |
| T8b PATH words (full-question read), compress, A  [current default] | 4 | 6 | 80 |
| T8c STABLE-state path words, compress, A | 3 | 7 | 80 |
| T8c STABLE-state path words, compress, B | 4 | 7 | 79 |

