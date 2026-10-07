# T8f stable-seats-qpath / qword -- effort standard (S300, 90 questions: 60 answerable, 30 unanswerable)

List = every layer-0 entry of the three tiers + the upper entries of the configuration (nothing merged). Gold in a candidate = a gold string occurs in a word of an entry (oracle rule).

## Answerable (60)

| configuration | gold in a candidate | single ANSWER | inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off |
|---|---|---|---|---|---|---|---|
| layers off | 29 | 1 | 28 | 3 | 28 | 7.0 (69) | 0 |
| T8 bag A | 38 | 0 | 38 | 1 | 21 | 15.0 (76) | 9 |
| T8e stable-seats-path A | 38 | 0 | 38 | 1 | 21 | 22.0 (77) | 9 |
| T8f Q1 stable-seats-qpath A | 38 | 0 | 38 | 1 | 21 | 22.0 (77) | 9 |
| T8f Q2 stable-seats-qword A | 38 | 0 | 38 | 1 | 21 | 22.0 (77) | 9 |

## Unanswerable (30)

| configuration | no candidate | only a list (rejectable) | a single answer (wrong) |
|---|---|---|---|
| layers off | 3 | 25 | 2 |
| T8 bag A | 1 | 28 | 1 |
| T8e stable-seats-path A | 1 | 28 | 1 |
| T8f Q1 stable-seats-qpath A | 1 | 28 | 1 |
| T8f Q2 stable-seats-qword A | 1 | 28 | 1 |

## Upper candidates (answerable questions)

| configuration | upper cand. total | per question median / max | words median / p90 / max | bundles per cand. median / p90 / max | seats median / p90 / max | gold-holding: count, words median / max, bundles median / max |
|---|---|---|---|---|---|---|
| T8 bag A | 426 | 6.0 / 37 | 118.5 / 166.0 / 191 | 8.0 / 11.0 / 17 | - / - / - | 30, 9.0 / 74, 7.0 / 11 |
| T8e stable-seats-path A | 810 | 12.5 / 44 | 14.0 / 148.0 / 186 | 7.0 / 10.0 / 17 | 63.0 / 498.0 / 1035 | 61, 9.0 / 74, 7.0 / 11 |
| T8f Q1 stable-seats-qpath A | 810 | 12.5 / 44 | 14.0 / 148.0 / 186 | 7.0 / 10.0 / 17 | 63.0 / 498.0 / 1035 | 61, 9.0 / 74, 7.0 / 11 |
| T8f Q2 stable-seats-qword A | 810 | 12.5 / 44 | 14.0 / 148.0 / 186 | 7.0 / 10.0 / 17 | 63.0 / 498.0 / 1035 | 61, 9.0 / 74, 7.0 / 11 |

By tier (all 90 questions): candidates / words median p90 max / bundles median p90 max / seats median p90 max

| configuration | tier | candidates | words | bundles | seats |
|---|---|---|---|---|---|
| seatsPathA | RUN | 82 | 9.5 / 13.0 / 20 | 6.0 / 9.0 / 11 | 24.0 / 38.0 / 50 |
| seatsPathA | WORD | 489 | 14.0 / 57.0 / 90 | 7.0 / 9.0 / 16 | 61.0 / 129.0 / 217 |
| seatsPathA | CHAR | 639 | 99.0 / 161.0 / 187 | 7.0 / 10.0 / 17 | 231.0 / 622.0 / 1035 |
| seatsPathA | all | 1210 | 15.0 / 150.0 / 187 | 7.0 / 10.0 / 17 | 64.0 / 491.0 / 1035 |
| qpathA | RUN | 82 | 9.5 / 13.0 / 20 | 6.0 / 9.0 / 11 | 24.0 / 38.0 / 50 |
| qpathA | WORD | 489 | 14.0 / 57.0 / 90 | 7.0 / 9.0 / 16 | 61.0 / 129.0 / 217 |
| qpathA | CHAR | 639 | 99.0 / 161.0 / 187 | 7.0 / 10.0 / 17 | 231.0 / 622.0 / 1035 |
| qpathA | all | 1210 | 15.0 / 150.0 / 187 | 7.0 / 10.0 / 17 | 64.0 / 489.0 / 1035 |
| qwordA | RUN | 82 | 9.5 / 13.0 / 20 | 6.0 / 9.0 / 11 | 24.0 / 38.0 / 50 |
| qwordA | WORD | 489 | 14.0 / 57.0 / 90 | 7.0 / 9.0 / 16 | 61.0 / 129.0 / 217 |
| qwordA | CHAR | 639 | 99.0 / 161.0 / 187 | 7.0 / 10.0 / 17 | 231.0 / 622.0 / 1035 |
| qwordA | all | 1210 | 15.0 / 150.0 / 187 | 7.0 / 10.0 / 17 | 64.0 / 491.0 / 1035 |

## Position of the first gold-holding candidate (answerable questions with gold; 1 = first; layer-0 entries come first)

| configuration | questions with gold | position in whole list: median / p90 / max | list length of those: median / max | position among UPPER candidates (gold held by an upper one): n, median / p90 / max | upper candidates of those: median / max |
|---|---|---|---|---|---|
| layers off | 29 | 1.0 / 2.0 / 4 | 11.0 / 69 | 0, - / - / - | - / - |
| T8 bag A | 38 | 1.0 / 13.0 / 28 | 17.5 / 76 | 23, 4.0 / 10.0 / 34 | 6.0 / 37 |
| T8e stable-seats-path A | 38 | 1.0 / 19.0 / 44 | 28.0 / 77 | 23, 7.0 / 21.0 / 35 | 13.0 / 44 |
| T8f Q1 stable-seats-qpath A | 38 | 1.0 / 19.0 / 44 | 28.0 / 77 | 23, 7.0 / 21.0 / 35 | 13.0 / 44 |
| T8f Q2 stable-seats-qword A | 38 | 1.0 / 19.0 / 44 | 28.0 / 77 | 23, 7.0 / 21.0 / 35 | 13.0 / 44 |

## Time per question (seconds; other agents' work ran at the same time: inflated)

| | median | mean | p90 | max |
|---|---|---|---|---|
| layer 0 | 17.2 | 21.9 | 51.2 | 111.9 |
| layers added, bagA | 5.9 | 7.4 | 16.7 | 37.7 |
| layers added, seatsPathA | 47.9 | 46.6 | 74.5 | 100.0 |
| layers added, qpathA | 37.0 | 38.2 | 62.7 | 81.3 |
| layers added, qwordA | 36.9 | 38.1 | 62.8 | 81.3 |
(bagA, seatsPathA times are from the earlier sweeps, run under other loads; qpathA / qwordA from the T8f sweeps, each config in its own sweep)

## Trace

- bagA: 345 upper runs, trace_ok 345 / 345; entries with every word sourced 666 / 666; upper entries with no layout at all: 0; entries left with no kept bundle (no candidate): 0
- seatsPathA: 345 upper runs, trace_ok 345 / 345; entries with every word sourced 1210 / 1210; upper entries with no layout at all: 0; entries left with no kept bundle (no candidate): 0
- qpathA: 345 upper runs, trace_ok 345 / 345; entries with every word sourced 1210 / 1210; upper entries with no layout at all: 0; entries left with no kept bundle (no candidate): 0
- qwordA: 345 upper runs, trace_ok 345 / 345; entries with every word sourced 1210 / 1210; upper entries with no layout at all: 0; entries left with no kept bundle (no candidate): 0

## Subset check: bundles per candidate against stable-seats-path (all questions, upper candidates)

- seatsPathA: 1210 candidates, 8789 bundles in total
- qpathA: 1210 candidates, 8784 bundles in total
- qwordA: 1210 candidates, 8771 bundles in total

