# T8d stable-seats / stable-seated candidates -- effort fast (S300, 90 questions: 60 answerable, 30 unanswerable)

The list = every layer-0 entry of the three tiers + the upper-layer entries of the configuration, each labelled; nothing merged. 'Gold in a candidate' = a gold string occurs in a word of an entry (oracle rule of T6ab / T7b / T8). Upper-layer candidates of T8 were bags (N-19 expanded every bundle to all words of the lower state); T8b shows the path words of the full-question read; T8c the path words of the last stable state while the question is applied unit by unit.

## Candidate quality: answerable questions (60)

| configuration | gold in a candidate | ... single ANSWER | ... inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off | gold held only by an UPPER candidate: its words median |
|---|---|---|---|---|---|---|---|---|
| layers off (layer 0 = T7b) | 28 | 4 | 24 | 5 | 27 | 6.0 (51) | 0 | - |
| T8 bag, compress, A | 36 | 2 | 34 | 2 | 22 | 7.0 (53) | 8 | 4.0 |
| T8b PATH words (full-question read), compress, A  [current default] | 28 | 4 | 24 | 5 | 27 | 7.0 (51) | 0 | - |
| T8c STABLE-state path words, compress, A | 28 | 3 | 25 | 5 | 27 | 6.5 (51) | 0 | - |
| T8d STABLE-SEATS (restored state laid out by seats), compress, A | 36 | 1 | 35 | 2 | 22 | 13.0 (62) | 8 | 4.0 |
| T8d STABLE-SEATED (boundary only at seated units), path words, compress, A | 28 | 3 | 25 | 5 | 27 | 6.5 (51) | 0 | - |

## Unanswerable questions (30): can a user reject what is shown?

| configuration | no candidate | only a list (rejectable) | a single answer (looks confident: wrong) |
|---|---|---|---|
| layers off (layer 0 = T7b) | 4 | 22 | 4 |
| T8 bag, compress, A | 3 | 26 | 1 |
| T8b PATH words (full-question read), compress, A  [current default] | 4 | 24 | 2 |
| T8c STABLE-state path words, compress, A | 4 | 23 | 3 |
| T8d STABLE-SEATS (restored state laid out by seats), compress, A | 3 | 27 | 0 |
| T8d STABLE-SEATED (boundary only at seated units), path words, compress, A | 4 | 23 | 3 |

## Size of the UPPER-layer candidates (words per candidate), answerable questions

| configuration | upper candidates | words median | p90 | max | holding gold: count | words per gold-holding candidate: median / max | upper candidates per question (median / max) |
|---|---|---|---|---|---|---|---|
| layer 0 (for scale) | 497 | 5.0 | 10.0 | 21 | - | - | - |
| T8 bag, compress, A | 106 | 93.5 | 143.0 | 165 | 18 | 8.5 / 18 | 1.0 / 7 |
| T8b PATH words (full-question read), compress, A  [current default] | 43 | 18.0 | 33.0 | 35 | 6 | 7.0 / 14 | 1.0 / 3 |
| T8c STABLE-state path words, compress, A | 37 | 16.0 | 20.0 | 25 | 4 | 7.0 / 7 | 0.5 / 3 |
| T8d STABLE-SEATS (restored state laid out by seats), compress, A | 411 | 34.0 | 81.0 | 104 | 26 | 4.5 / 10 | 6.5 / 18 |
| T8d STABLE-SEATED (boundary only at seated units), path words, compress, A | 37 | 16.0 | 20.0 | 25 | 4 | 7.0 / 7 | 0.5 / 3 |

## What the lower reads gave

- [pathA] upper runs: 208; upper entries: 71; upper entries dropped because the lower crosses gave no path words: 99; entries with every word sourced: 71 / 71
- [stableA] upper runs: 208; upper entries: 56; upper entries dropped because the lower crosses gave no path words: 117; entries with every word sourced: 56 / 56
- [seatedA] upper runs: 208; upper entries: 56; upper entries dropped because the lower crosses gave no path words: 117; entries with every word sourced: 56 / 56
- [seatsA] upper runs: 208; upper entries: 623; upper entries dropped because the lower crosses gave no path words: 0; entries with every word sourced: 623 / 623

## Boundary records (per lower cross read down, over all questions; one record per (question, tier, layer, seed))

| config | lower reads | no restore (stable through the whole question) | restored | ... restored to STEP 0 (no unit applied) | ... restored at step >= 1 | state read has path words (listed > 0) / is shown (seats) | no break at a seated unit but the full-question state is unstable (energy-only break, not a boundary) |
|---|---|---|---|---|---|---|---|
| stableA | 687 | 196 | 491 | 398 | 93 | 102 | - |

  [stableA] restored: last stable step histogram {0: 398, 1: 26, 2: 10, 3: 8, 4: 22, 5: 24, 6: 2, 7: 1}; first unstable step histogram {1: 398, 2: 26, 3: 10, 4: 8, 5: 22, 6: 24, 7: 2, 8: 1}; units per read median 8.0; unstable unit attached (seated) in 488 of 491 restored; restored to step >= 7 (the boundary lies after the 6 seated units): 1
| seatedA | 687 | 199 | 488 | 398 | 90 | 102 | 2 |

  [seatedA] restored: last stable step histogram {0: 398, 1: 26, 2: 10, 3: 8, 4: 22, 5: 24}; first unstable step histogram {1: 398, 2: 26, 3: 10, 4: 8, 5: 22, 6: 24}; units per read median 8.0; unstable unit attached (seated) in 488 of 488 restored; restored to step >= 7 (the boundary lies after the 6 seated units): 0
| seatsA | 687 | 196 | 491 | 398 | 93 | 687 | - |

  [seatsA] restored: last stable step histogram {0: 398, 1: 26, 2: 10, 3: 8, 4: 22, 5: 24, 6: 2, 7: 1}; first unstable step histogram {1: 398, 2: 26, 3: 10, 4: 8, 5: 22, 6: 24, 7: 2, 8: 1}; units per read median 8.0; unstable unit attached (seated) in 488 of 491 restored; restored to step >= 7 (the boundary lies after the 6 seated units): 1

## T8d stable-seats: what a candidate is (all upper candidates, all 90 questions; answerable in brackets)

| tier | candidates | words median | p90 | max | seats median | p90 | max | arrangements in the state: median / max | sources per word (median) |
|---|---|---|---|---|---|---|---|---|---|
| RUN | 56 | 4.0 | 9.0 | 9 | 3.0 | 8.0 | 8 | 2.0 / 48 | - |
| WORD | 192 | 14.0 | 28.0 | 35 | 13.0 | 27.0 | 34 | 4.0 / 192 | - |
| CHAR | 375 | 62.0 | 94.0 | 104 | 61.0 | 93.0 | 103 | 2.0 / 48 | - |
| all | 623 | 37.0 | 86.0 | 104 | 36.0 | 85.0 | 103 | 2.0 / 192 | - |

Position of the first gold-holding candidate (answerable questions where some candidate holds gold; 1 = first). 'in the whole list' = layer-0 entries of the three tiers, then the upper entries; 'among upper' = counted over the upper candidates only; the list length is the number of candidates shown.

| configuration | questions with gold | position in the whole list: median / p90 / max | list length of those: median / max | position among upper candidates (gold held by an upper one): median / p90 / max | upper candidates of those: median / max | gold only in an upper candidate (not in off): count |
|---|---|---|---|---|---|---|
| layers off (layer 0 = T7b) | 28 | 1.0 / 2.0 / 4 | 7.0 / 51 | - / - / - | - / - | 0 |
| T8 bag, compress, A | 36 | 1.0 / 5.0 / 11 | 8.0 / 53 | 2.0 / 4.0 / 6 | 3.0 / 7 | 8 |
| T8b PATH words (full-question read), compress, A  [current default] | 28 | 1.0 / 2.0 / 4 | 8.0 / 51 | 1.0 / 2.0 / 2 | 1.0 / 3 | 0 |
| T8c STABLE-state path words, compress, A | 28 | 1.0 / 2.0 / 4 | 8.0 / 51 | 1.0 / 2.0 / 2 | 1.0 / 3 | 0 |
| T8d STABLE-SEATS (restored state laid out by seats), compress, A | 36 | 1.0 / 9.0 / 14 | 16.0 / 62 | 6.0 / 12.0 / 14 | 10.0 / 18 | 8 |
| T8d STABLE-SEATED (boundary only at seated units), path words, compress, A | 28 | 1.0 / 2.0 / 4 | 8.0 / 51 | 1.0 / 2.0 / 2 | 1.0 / 3 | 0 |

Gold-holding upper candidates of stable-seats: words median / max, seats median / max: 4.5 / 10, 3.5 / 9

## Time per question (seconds; other measurements ran at the same time: inflated by contention)

| | median | mean | p90 | max |
|---|---|---|---|---|
| layer 0 (layers off) | 3.5 | 7.9 | 18.6 | 86.2 |
| layers added, seatedA | 10.9 | 11.1 | 25.5 | 36.2 |
| layers added, seatsA | 12.6 | 11.8 | 27.8 | 44.2 |
| layers added, bagA | 0.1 | 0.1 | 0.2 | 1.3 |
| layers added, pathA | 6.7 | 8.2 | 18.8 | 29.0 |
| layers added, stableA | 13.0 | 13.0 | 30.8 | 47.2 |

## Trace through the layers

- seatedA: 208 upper runs, every word traced (trace_ok): 208 / 208
- seatsA: 208 upper runs, every word traced (trace_ok): 208 / 208
- bagA: 208 upper runs, every word traced (trace_ok): 208 / 208
- pathA: 208 upper runs, every word traced (trace_ok): 208 / 208
- stableA: 208 upper runs, every word traced (trace_ok): 208 / 208

## Reference only: rule-B scores (right = the list is ONE entry that holds gold; wrong = one entry without gold or an answer to an unanswerable question; abstain = otherwise)

| configuration | right | wrong | abstain |
|---|---|---|---|
| layers off (layer 0 = T7b) | 4 | 11 | 75 |
| T8 bag, compress, A | 2 | 5 | 83 |
| T8b PATH words (full-question read), compress, A  [current default] | 4 | 6 | 80 |
| T8c STABLE-state path words, compress, A | 3 | 7 | 80 |
| T8d STABLE-SEATS (restored state laid out by seats), compress, A | 1 | 2 | 87 |
| T8d STABLE-SEATED (boundary only at seated units), path words, compress, A | 3 | 7 | 80 |

