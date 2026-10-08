# T8d stable-seats / stable-seated candidates -- effort standard (S300, 90 questions: 60 answerable, 30 unanswerable)

The list = every layer-0 entry of the three tiers + the upper-layer entries of the configuration, each labelled; nothing merged. 'Gold in a candidate' = a gold string occurs in a word of an entry (oracle rule of T6ab / T7b / T8). Upper-layer candidates of T8 were bags (N-19 expanded every bundle to all words of the lower state); T8b shows the path words of the full-question read; T8c the path words of the last stable state while the question is applied unit by unit.

## Candidate quality: answerable questions (60)

| configuration | gold in a candidate | ... single ANSWER | ... inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off | gold held only by an UPPER candidate: its words median |
|---|---|---|---|---|---|---|---|---|
| layers off (layer 0 = T7b) | 29 | 1 | 28 | 3 | 28 | 7.0 (69) | 0 | - |
| T8 bag, compress, A | 38 | 0 | 38 | 1 | 21 | 15.0 (76) | 9 | 7.0 |
| T8b PATH words (full-question read), compress, A  [current default] | 30 | 1 | 29 | 3 | 27 | 12.0 (72) | 1 | 10.0 |
| T8c STABLE-state path words, compress, A | 29 | 1 | 28 | 3 | 28 | 13.0 (73) | 0 | - |
| T8d STABLE-SEATS (restored state laid out by seats), compress, A | 38 | 0 | 38 | 1 | 21 | 35.0 (93) | 9 | 6.0 |
| T8d STABLE-SEATED (boundary only at seated units), path words, compress, A | 29 | 1 | 28 | 3 | 28 | 13.0 (73) | 0 | - |

## Unanswerable questions (30): can a user reject what is shown?

| configuration | no candidate | only a list (rejectable) | a single answer (looks confident: wrong) |
|---|---|---|---|
| layers off (layer 0 = T7b) | 3 | 25 | 2 |
| T8 bag, compress, A | 1 | 28 | 1 |
| T8b PATH words (full-question read), compress, A  [current default] | 3 | 26 | 1 |
| T8c STABLE-state path words, compress, A | 3 | 26 | 1 |
| T8d STABLE-SEATS (restored state laid out by seats), compress, A | 1 | 29 | 0 |
| T8d STABLE-SEATED (boundary only at seated units), path words, compress, A | 3 | 26 | 1 |

## Size of the UPPER-layer candidates (words per candidate), answerable questions

| configuration | upper candidates | words median | p90 | max | holding gold: count | words per gold-holding candidate: median / max | upper candidates per question (median / max) |
|---|---|---|---|---|---|---|---|
| layer 0 (for scale) | 799 | 5.0 | 10.0 | 21 | - | - | - |
| T8 bag, compress, A | 426 | 118.5 | 166.0 | 191 | 30 | 9.0 / 74 | 6.0 / 37 |
| T8b PATH words (full-question read), compress, A  [current default] | 210 | 24.0 | 38.0 | 58 | 20 | 7.0 / 36 | 4.0 / 9 |
| T8c STABLE-state path words, compress, A | 192 | 20.0 | 31.0 | 50 | 5 | 7.0 / 7 | 3.0 / 8 |
| T8d STABLE-SEATS (restored state laid out by seats), compress, A | 1450 | 15.0 | 76.0 | 104 | 42 | 7.0 / 12 | 24.5 / 43 |
| T8d STABLE-SEATED (boundary only at seated units), path words, compress, A | 192 | 20.0 | 31.0 | 50 | 5 | 7.0 / 7 | 3.0 / 8 |

## What the lower reads gave

- [pathA] upper runs: 345; upper entries: 321; upper entries dropped because the lower crosses gave no path words: 512; entries with every word sourced: 321 / 321
- [stableA] upper runs: 345; upper entries: 273; upper entries dropped because the lower crosses gave no path words: 748; entries with every word sourced: 273 / 273
- [seatedA] upper runs: 345; upper entries: 273; upper entries dropped because the lower crosses gave no path words: 748; entries with every word sourced: 273 / 273
- [seatsA] upper runs: 345; upper entries: 2155; upper entries dropped because the lower crosses gave no path words: 0; entries with every word sourced: 2155 / 2155

## Boundary records (per lower cross read down, over all questions; one record per (question, tier, layer, seed))

| config | lower reads | no restore (stable through the whole question) | restored | ... restored to STEP 0 (no unit applied) | ... restored at step >= 1 | state read has path words (listed > 0) / is shown (seats) | no break at a seated unit but the full-question state is unstable (energy-only break, not a boundary) |
|---|---|---|---|---|---|---|---|
| stableA | 3533 | 1143 | 2390 | 1838 | 552 | 889 | - |

  [stableA] restored: last stable step histogram {0: 1838, 1: 193, 2: 111, 3: 110, 4: 55, 5: 66, 6: 3, 7: 4, 8: 1, 9: 2, 10: 2, 12: 3, 13: 2}; first unstable step histogram {1: 1838, 2: 193, 3: 111, 4: 110, 5: 55, 6: 66, 7: 3, 8: 4, 9: 1, 10: 2, 11: 2, 13: 3, 14: 2}; units per read median 10.0; unstable unit attached (seated) in 2373 of 2390 restored; restored to step >= 7 (the boundary lies after the 6 seated units): 14
| seatedA | 3533 | 1160 | 2373 | 1838 | 535 | 889 | 8 |

  [seatedA] restored: last stable step histogram {0: 1838, 1: 193, 2: 111, 3: 110, 4: 55, 5: 66}; first unstable step histogram {1: 1838, 2: 193, 3: 111, 4: 110, 5: 55, 6: 66}; units per read median 10.0; unstable unit attached (seated) in 2373 of 2373 restored; restored to step >= 7 (the boundary lies after the 6 seated units): 0
| seatsA | 2527 | 910 | 1617 | 1234 | 383 | 2527 | - |

  [seatsA] restored: last stable step histogram {0: 1234, 1: 125, 2: 88, 3: 64, 4: 45, 5: 45, 6: 3, 7: 3, 8: 1, 9: 2, 10: 2, 12: 3, 13: 2}; first unstable step histogram {1: 1234, 2: 125, 3: 88, 4: 64, 5: 45, 6: 45, 7: 3, 8: 3, 9: 1, 10: 2, 11: 2, 13: 3, 14: 2}; units per read median 10.0; unstable unit attached (seated) in 1601 of 1617 restored; restored to step >= 7 (the boundary lies after the 6 seated units): 13

## T8d stable-seats: what a candidate is (all upper candidates, all 90 questions; answerable in brackets)

| tier | candidates | words median | p90 | max | seats median | p90 | max | arrangements in the state: median / max |
|---|---|---|---|---|---|---|---|---|
| RUN | 108 | 4.0 | 9.0 | 13 | 3.0 | 8.0 | 12 | 8.0 / 2720 |
| WORD | 798 | 10.0 | 22.0 | 35 | 9.0 | 21.0 | 34 | 9.0 / 4368 |
| CHAR | 1249 | 47.0 | 91.0 | 104 | 46.0 | 90.0 | 103 | 4.0 / 273 |
| all | 2155 | 16.0 | 76.0 | 104 | 15.0 | 75.0 | 103 | 6.0 / 4368 |

Position of the first gold-holding candidate (answerable questions where some candidate holds gold; 1 = first). 'in the whole list' = layer-0 entries of the three tiers, then the upper entries; 'among upper' = counted over the upper candidates only; the list length is the number of candidates shown.

| configuration | questions with gold | position in the whole list: median / p90 / max | list length of those: median / max | position among upper candidates (gold held by an upper one): median / p90 / max | upper candidates of those: median / max | gold only in an upper candidate (not in off): count |
|---|---|---|---|---|---|---|
| layers off (layer 0 = T7b) | 29 | 1.0 / 2.0 / 4 | 11.0 / 69 | - / - / - | - / - | 0 |
| T8 bag, compress, A | 38 | 1.0 / 13.0 / 28 | 17.5 / 76 | 4.0 / 10.0 / 34 | 6.0 / 37 | 9 |
| T8b PATH words (full-question read), compress, A  [current default] | 30 | 1.0 / 3.0 / 21 | 14.0 / 72 | 2.0 / 4.0 / 4 | 4.0 / 9 | 1 |
| T8c STABLE-state path words, compress, A | 29 | 1.0 / 2.0 / 4 | 14.0 / 73 | 1.0 / 4.0 / 4 | 4.0 / 6 | 0 |
| T8d STABLE-SEATS (restored state laid out by seats), compress, A | 38 | 1.0 / 25.0 / 38 | 40.5 / 93 | 17.0 / 21.0 / 23 | 25.0 / 43 | 9 |
| T8d STABLE-SEATED (boundary only at seated units), path words, compress, A | 29 | 1.0 / 2.0 / 4 | 14.0 / 73 | 1.0 / 4.0 / 4 | 4.0 / 6 | 0 |

Gold-holding upper candidates of stable-seats: words median / max, seats median / max: 7.0 / 12, 6.0 / 11

## Time per question (seconds; other measurements ran at the same time: inflated by contention)

| | median | mean | p90 | max |
|---|---|---|---|---|
| layer 0 (layers off) | 27.5 | 33.8 | 82.6 | 158.8 |
| layers added, seatedA | 64.0 | 69.6 | 118.6 | 171.8 |
| layers added, seatsA | 59.6 | 60.7 | 104.6 | 133.7 |
| layers added, bagA | 5.9 | 7.4 | 16.7 | 37.7 |
| layers added, pathA | 37.7 | 41.6 | 78.8 | 137.6 |
| layers added, stableA | 61.1 | 64.5 | 116.1 | 163.8 |

## Trace through the layers

- seatedA: 345 upper runs, every word traced (trace_ok): 345 / 345
- seatsA: 345 upper runs, every word traced (trace_ok): 345 / 345
- bagA: 345 upper runs, every word traced (trace_ok): 345 / 345
- pathA: 345 upper runs, every word traced (trace_ok): 345 / 345
- stableA: 345 upper runs, every word traced (trace_ok): 345 / 345

## Reference only: rule-B scores (right = the list is ONE entry that holds gold; wrong = one entry without gold or an answer to an unanswerable question; abstain = otherwise)

| configuration | right | wrong | abstain |
|---|---|---|---|
| layers off (layer 0 = T7b) | 1 | 5 | 84 |
| T8 bag, compress, A | 0 | 1 | 89 |
| T8b PATH words (full-question read), compress, A  [current default] | 1 | 2 | 87 |
| T8c STABLE-state path words, compress, A | 1 | 2 | 87 |
| T8d STABLE-SEATS (restored state laid out by seats), compress, A | 0 | 0 | 90 |
| T8d STABLE-SEATED (boundary only at seated units), path words, compress, A | 1 | 2 | 87 |

