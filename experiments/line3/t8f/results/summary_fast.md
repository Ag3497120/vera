# T8f stable-seats-qpath / qword -- effort fast (S300, 90 questions: 60 answerable, 30 unanswerable)

List = every layer-0 entry of the three tiers + the upper entries of the configuration (nothing merged). Gold in a candidate = a gold string occurs in a word of an entry (oracle rule).

## Answerable (60)

| configuration | gold in a candidate | single ANSWER | inside a list >= 2 | no candidate | candidates, none holds gold | list size median (max), lists >= 2 | gold gained vs off |
|---|---|---|---|---|---|---|---|
| layers off | 28 | 4 | 24 | 5 | 27 | 6.0 (51) | 0 |
| T8 bag A | 36 | 2 | 34 | 2 | 22 | 7.0 (53) | 8 |
| T8e stable-seats-path A | 36 | 2 | 34 | 2 | 22 | 7.0 (55) | 8 |
| T8f Q1 stable-seats-qpath A | 36 | 2 | 34 | 2 | 22 | 7.0 (55) | 8 |
| T8f Q2 stable-seats-qword A | 36 | 2 | 34 | 2 | 22 | 7.0 (55) | 8 |

## Unanswerable (30)

| configuration | no candidate | only a list (rejectable) | a single answer (wrong) |
|---|---|---|---|
| layers off | 4 | 22 | 4 |
| T8 bag A | 3 | 26 | 1 |
| T8e stable-seats-path A | 3 | 26 | 1 |
| T8f Q1 stable-seats-qpath A | 3 | 26 | 1 |
| T8f Q2 stable-seats-qword A | 3 | 26 | 1 |

## Upper candidates (answerable questions)

| configuration | upper cand. total | per question median / max | words median / p90 / max | bundles per cand. median / p90 / max | seats median / p90 / max | gold-holding: count, words median / max, bundles median / max |
|---|---|---|---|---|---|---|
| T8 bag A | 106 | 1.0 / 7 | 93.5 / 143.0 / 165 | 5.0 / 7.0 / 13 | - / - / - | 18, 8.5 / 18, 6.0 / 7 |
| T8e stable-seats-path A | 120 | 1.0 / 15 | 84.0 / 142.0 / 165 | 5.0 / 7.0 / 13 | 173.0 / 400.0 / 861 | 27, 9.0 / 18, 5.0 / 7 |
| T8f Q1 stable-seats-qpath A | 120 | 1.0 / 15 | 84.0 / 142.0 / 165 | 5.0 / 7.0 / 13 | 173.0 / 400.0 / 861 | 27, 9.0 / 18, 5.0 / 7 |
| T8f Q2 stable-seats-qword A | 120 | 1.0 / 15 | 84.0 / 142.0 / 165 | 5.0 / 7.0 / 13 | 173.0 / 399.0 / 861 | 27, 9.0 / 18, 5.0 / 7 |

By tier (all 90 questions): candidates / words median p90 max / bundles median p90 max / seats median p90 max

| configuration | tier | candidates | words | bundles | seats |
|---|---|---|---|---|---|
| seatsPathA | RUN | 22 | 8.0 / 14.0 / 18 | 4.0 / 7.0 / 7 | 18.0 / 29.0 / 31 |
| seatsPathA | WORD | 60 | 30.0 / 49.0 / 58 | 5.0 / 6.0 / 7 | 52.0 / 90.0 / 153 |
| seatsPathA | CHAR | 104 | 125.5 / 158.0 / 179 | 5.0 / 7.0 / 13 | 317.5 / 451.0 / 861 |
| seatsPathA | all | 186 | 82.0 / 147.0 / 179 | 5.0 / 7.0 / 13 | 167.5 / 399.0 / 861 |
| qpathA | RUN | 22 | 8.0 / 14.0 / 18 | 4.0 / 7.0 / 7 | 18.0 / 29.0 / 31 |
| qpathA | WORD | 60 | 30.0 / 49.0 / 58 | 5.0 / 6.0 / 7 | 52.0 / 90.0 / 153 |
| qpathA | CHAR | 104 | 125.5 / 158.0 / 179 | 5.0 / 7.0 / 13 | 317.5 / 451.0 / 861 |
| qpathA | all | 186 | 82.0 / 147.0 / 179 | 5.0 / 7.0 / 13 | 167.5 / 399.0 / 861 |
| qwordA | RUN | 22 | 8.0 / 14.0 / 18 | 4.0 / 7.0 / 7 | 18.0 / 29.0 / 31 |
| qwordA | WORD | 60 | 30.0 / 49.0 / 58 | 5.0 / 6.0 / 7 | 52.0 / 90.0 / 153 |
| qwordA | CHAR | 104 | 125.5 / 158.0 / 179 | 5.0 / 7.0 / 13 | 313.0 / 451.0 / 861 |
| qwordA | all | 186 | 81.0 / 147.0 / 179 | 5.0 / 7.0 / 13 | 162.5 / 398.0 / 861 |

## Position of the first gold-holding candidate (answerable questions with gold; 1 = first; layer-0 entries come first)

| configuration | questions with gold | position in whole list: median / p90 / max | list length of those: median / max | position among UPPER candidates (gold held by an upper one): n, median / p90 / max | upper candidates of those: median / max |
|---|---|---|---|---|---|
| layers off | 28 | 1.0 / 2.0 / 4 | 7.0 / 51 | 0, - / - / - | - / - |
| T8 bag A | 36 | 1.0 / 5.0 / 11 | 8.0 / 53 | 17, 2.0 / 4.0 / 6 | 3.0 / 7 |
| T8e stable-seats-path A | 36 | 1.0 / 5.0 / 11 | 8.0 / 55 | 17, 2.0 / 4.0 / 6 | 3.0 / 15 |
| T8f Q1 stable-seats-qpath A | 36 | 1.0 / 5.0 / 11 | 8.0 / 55 | 17, 2.0 / 4.0 / 6 | 3.0 / 15 |
| T8f Q2 stable-seats-qword A | 36 | 1.0 / 5.0 / 11 | 8.0 / 55 | 17, 2.0 / 4.0 / 6 | 3.0 / 15 |

## Time per question (seconds; other agents' work ran at the same time: inflated)

| | median | mean | p90 | max |
|---|---|---|---|---|
| layer 0 | 3.3 | 7.2 | 15.1 | 71.3 |
| layers added, bagA | 0.1 | 0.1 | 0.2 | 1.3 |
| layers added, seatsPathA | 14.2 | 13.7 | 33.0 | 47.8 |
| layers added, qpathA | 10.7 | 10.6 | 25.0 | 34.1 |
| layers added, qwordA | 10.7 | 10.6 | 24.9 | 34.1 |
(bagA, seatsPathA times are from the earlier sweeps, run under other loads; qpathA / qwordA from the T8f sweeps, each config in its own sweep)

## Trace

- bagA: 208 upper runs, trace_ok 208 / 208; entries with every word sourced 166 / 166; upper entries with no layout at all: 0; entries left with no kept bundle (no candidate): 0
- seatsPathA: 208 upper runs, trace_ok 208 / 208; entries with every word sourced 186 / 186; upper entries with no layout at all: 0; entries left with no kept bundle (no candidate): 0
- qpathA: 208 upper runs, trace_ok 208 / 208; entries with every word sourced 186 / 186; upper entries with no layout at all: 0; entries left with no kept bundle (no candidate): 0
- qwordA: 208 upper runs, trace_ok 208 / 208; entries with every word sourced 186 / 186; upper entries with no layout at all: 0; entries left with no kept bundle (no candidate): 0

## Subset check: bundles per candidate against stable-seats-path (all questions, upper candidates)

- seatsPathA: 186 candidates, 958 bundles in total
- qpathA: 186 candidates, 957 bundles in total
- qwordA: 186 candidates, 939 bundles in total

