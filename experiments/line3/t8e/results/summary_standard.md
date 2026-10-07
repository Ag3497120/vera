# T8e stable-seats-path -- effort standard (S300, 90 questions: 60 answerable, 30 unanswerable)

List = every layer-0 entry of the three tiers + the upper entries of the configuration (nothing merged). Gold in a candidate = a gold string occurs in a word of an entry (oracle rule).

## Answerable (60)

| configuration | gold in a candidate | single ANSWER | inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off |
|---|---|---|---|---|---|---|---|
| layers off | 29 | 1 | 28 | 3 | 28 | 7.0 (69) | 0 |
| T8 bag A | 38 | 0 | 38 | 1 | 21 | 15.0 (76) | 9 |
| T8d stable-seats A (1 per bundle) | 38 | 0 | 38 | 1 | 21 | 35.0 (93) | 9 |
| T8e stable-seats-path A (1 per upper entry) | 38 | 0 | 38 | 1 | 21 | 22.0 (77) | 9 |

## Unanswerable (30)

| configuration | no candidate | only a list (rejectable) | a single answer (wrong) |
|---|---|---|---|
| layers off | 3 | 25 | 2 |
| T8 bag A | 1 | 28 | 1 |
| T8d stable-seats A (1 per bundle) | 1 | 29 | 0 |
| T8e stable-seats-path A (1 per upper entry) | 1 | 28 | 1 |

## Upper candidates (answerable questions)

| configuration | upper cand. total | per question median / max | words median / p90 / max | bundles per cand. median / p90 / max | seats median / p90 / max | gold-holding: count, words median / max, bundles median / max |
|---|---|---|---|---|---|---|
| T8 bag A | 426 | 6.0 / 37 | 118.5 / 166.0 / 191 | 8.0 / 11.0 / 17 | - / - / - | 30, 9.0 / 74, 7.0 / 11 |
| T8d stable-seats A (1 per bundle) | 1450 | 24.5 / 43 | 15.0 / 76.0 / 104 | 1.0 / 2.0 / 8 | 14.0 / 75.0 / 103 | 42, 7.0 / 12, 2.0 / 8 |
| T8e stable-seats-path A (1 per upper entry) | 810 | 12.5 / 44 | 14.0 / 148.0 / 186 | 7.0 / 10.0 / 17 | 63.0 / 498.0 / 1035 | 61, 9.0 / 74, 7.0 / 11 |

By tier (all 90 questions), stable-seats-path: candidates / words median p90 max / bundles median p90 max / seats median p90 max

| tier | candidates | words | bundles | seats |
|---|---|---|---|---|
| RUN | 82 | 9.5 / 13.0 / 20 | 6.0 / 9.0 / 11 | 24.0 / 38.0 / 50 |
| WORD | 489 | 14.0 / 57.0 / 90 | 7.0 / 9.0 / 16 | 61.0 / 129.0 / 217 |
| CHAR | 639 | 99.0 / 161.0 / 187 | 7.0 / 10.0 / 17 | 231.0 / 622.0 / 1035 |
| all | 1210 | 15.0 / 150.0 / 187 | 7.0 / 10.0 / 17 | 64.0 / 491.0 / 1035 |

## Position of the first gold-holding candidate (answerable questions with gold; 1 = first; layer-0 entries come first)

| configuration | questions with gold | position in whole list: median / p90 / max | list length of those: median / max | position among UPPER candidates (gold held by an upper one): n, median / p90 / max | upper candidates of those: median / max |
|---|---|---|---|---|---|
| layers off | 29 | 1.0 / 2.0 / 4 | 11.0 / 69 | 0, - / - / - | - / - |
| T8 bag A | 38 | 1.0 / 13.0 / 28 | 17.5 / 76 | 23, 4.0 / 10.0 / 34 | 6.0 / 37 |
| T8d stable-seats A (1 per bundle) | 38 | 1.0 / 25.0 / 38 | 40.5 / 93 | 23, 17.0 / 21.0 / 23 | 25.0 / 43 |
| T8e stable-seats-path A (1 per upper entry) | 38 | 1.0 / 19.0 / 44 | 28.0 / 77 | 23, 7.0 / 21.0 / 35 | 13.0 / 44 |

## Time per question (seconds; other agents' work ran at the same time: inflated)

| | median | mean | p90 | max |
|---|---|---|---|---|
| layer 0 | 21.2 | 26.7 | 67.3 | 148.2 |
| layers added, bagA | 5.9 | 7.4 | 16.7 | 37.7 |
| layers added, seatsA | 59.6 | 60.7 | 104.6 | 133.7 |
| layers added, seatsPathA | 47.9 | 46.6 | 74.5 | 100.0 |
(bagA, seatsA times are from the earlier sweeps, run under other loads)

## Trace

- bagA: 345 upper runs, trace_ok 345 / 345; entries with every word sourced 666 / 666; upper entries dropped for no layout/path words: 0
- seatsA: 345 upper runs, trace_ok 345 / 345; entries with every word sourced 2155 / 2155; upper entries dropped for no layout/path words: 0
- seatsPathA: 345 upper runs, trace_ok 345 / 345; entries with every word sourced 1210 / 1210; upper entries dropped for no layout/path words: 0

## Merging: stable-seats bundles vs stable-seats-path candidates (all questions)

upper candidates: stable-seats 2155, stable-seats-path 1210

