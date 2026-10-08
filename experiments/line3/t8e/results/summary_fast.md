# T8e stable-seats-path -- effort fast (S300, 90 questions: 60 answerable, 30 unanswerable)

List = every layer-0 entry of the three tiers + the upper entries of the configuration (nothing merged). Gold in a candidate = a gold string occurs in a word of an entry (oracle rule).

## Answerable (60)

| configuration | gold in a candidate | single ANSWER | inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off |
|---|---|---|---|---|---|---|---|
| layers off | 28 | 4 | 24 | 5 | 27 | 6.0 (51) | 0 |
| T8 bag A | 36 | 2 | 34 | 2 | 22 | 7.0 (53) | 8 |
| T8d stable-seats A (1 per bundle) | 36 | 1 | 35 | 2 | 22 | 13.0 (62) | 8 |
| T8e stable-seats-path A (1 per upper entry) | 36 | 2 | 34 | 2 | 22 | 7.0 (55) | 8 |

## Unanswerable (30)

| configuration | no candidate | only a list (rejectable) | a single answer (wrong) |
|---|---|---|---|
| layers off | 4 | 22 | 4 |
| T8 bag A | 3 | 26 | 1 |
| T8d stable-seats A (1 per bundle) | 3 | 27 | 0 |
| T8e stable-seats-path A (1 per upper entry) | 3 | 26 | 1 |

## Upper candidates (answerable questions)

| configuration | upper cand. total | per question median / max | words median / p90 / max | bundles per cand. median / p90 / max | seats median / p90 / max | gold-holding: count, words median / max, bundles median / max |
|---|---|---|---|---|---|---|
| T8 bag A | 106 | 1.0 / 7 | 93.5 / 143.0 / 165 | 5.0 / 7.0 / 13 | - / - / - | 18, 8.5 / 18, 6.0 / 7 |
| T8d stable-seats A (1 per bundle) | 411 | 6.5 / 18 | 34.0 / 81.0 / 104 | 1.0 / 1.0 / 5 | 33.0 / 80.0 / 103 | 26, 4.5 / 10, 2.0 / 5 |
| T8e stable-seats-path A (1 per upper entry) | 120 | 1.0 / 15 | 84.0 / 142.0 / 165 | 5.0 / 7.0 / 13 | 173.0 / 400.0 / 861 | 27, 9.0 / 18, 5.0 / 7 |

By tier (all 90 questions), stable-seats-path: candidates / words median p90 max / bundles median p90 max / seats median p90 max

| tier | candidates | words | bundles | seats |
|---|---|---|---|---|
| RUN | 22 | 8.0 / 14.0 / 18 | 4.0 / 7.0 / 7 | 18.0 / 29.0 / 31 |
| WORD | 60 | 30.0 / 49.0 / 58 | 5.0 / 6.0 / 7 | 52.0 / 90.0 / 153 |
| CHAR | 104 | 125.5 / 158.0 / 179 | 5.0 / 7.0 / 13 | 317.5 / 451.0 / 861 |
| all | 186 | 82.0 / 147.0 / 179 | 5.0 / 7.0 / 13 | 167.5 / 399.0 / 861 |

## Position of the first gold-holding candidate (answerable questions with gold; 1 = first; layer-0 entries come first)

| configuration | questions with gold | position in whole list: median / p90 / max | list length of those: median / max | position among UPPER candidates (gold held by an upper one): n, median / p90 / max | upper candidates of those: median / max |
|---|---|---|---|---|---|
| layers off | 28 | 1.0 / 2.0 / 4 | 7.0 / 51 | 0, - / - / - | - / - |
| T8 bag A | 36 | 1.0 / 5.0 / 11 | 8.0 / 53 | 17, 2.0 / 4.0 / 6 | 3.0 / 7 |
| T8d stable-seats A (1 per bundle) | 36 | 1.0 / 9.0 / 14 | 16.0 / 62 | 17, 6.0 / 12.0 / 14 | 10.0 / 18 |
| T8e stable-seats-path A (1 per upper entry) | 36 | 1.0 / 5.0 / 11 | 8.0 / 55 | 17, 2.0 / 4.0 / 6 | 3.0 / 15 |

## Time per question (seconds; other agents' work ran at the same time: inflated)

| | median | mean | p90 | max |
|---|---|---|---|---|
| layer 0 | 4.2 | 9.4 | 21.0 | 98.2 |
| layers added, bagA | 0.1 | 0.1 | 0.2 | 1.3 |
| layers added, seatsA | 12.6 | 11.8 | 27.8 | 44.2 |
| layers added, seatsPathA | 14.2 | 13.7 | 33.0 | 47.8 |
(bagA, seatsA times are from the earlier sweeps, run under other loads)

## Trace

- bagA: 208 upper runs, trace_ok 208 / 208; entries with every word sourced 166 / 166; upper entries dropped for no layout/path words: 0
- seatsA: 208 upper runs, trace_ok 208 / 208; entries with every word sourced 623 / 623; upper entries dropped for no layout/path words: 0
- seatsPathA: 208 upper runs, trace_ok 208 / 208; entries with every word sourced 186 / 186; upper entries dropped for no layout/path words: 0

## Merging: stable-seats bundles vs stable-seats-path candidates (all questions)

upper candidates: stable-seats 623, stable-seats-path 186

