# F1c: ordered + stop (L-463) vs ordered + skip (L-501), fulllead_sents, level mid

Crosses that EXHAUSTED under stop are the same under skip (nothing collapses) and were copied; only the budget-stopped ones were rebuilt (build.py).

Tiers with a full run: RUN. Sample (every k-th seed, same seeds on both sides): WORD 150 seeds, CHAR 60 seeds.

## Sizes and stop reasons

| tier | mode | crosses | bare seed | size 2-3 | size 4-5 | size 6+ | median / p90 / max size | stop budget | exhausted |
|---|---|---|---|---|---|---|---|---|---|
| RUN | stop | 3653 | 5 (0%) | 102 | 410 | 3136 | 9 / 13 / 27 | 1914 | 1739 |
| RUN | skip | 3653 | 5 (0%) | 102 | 410 | 3136 | 9 / 13 / 37 | 0 | 3653 |
| WORD | stop | 150 | 0 (0%) | 1 | 3 | 146 | 11 / 19 / 37 | 88 | 62 |
| WORD | skip | 150 | 0 (0%) | 1 | 3 | 146 | 13 / 21 / 51 | 0 | 150 |
| CHAR | stop | 60 | 0 (0%) | 0 | 0 | 60 | 37 / 117 / 134 | 39 | 21 |
| CHAR | skip | 60 | 0 (0%) | 0 | 0 | 60 | 44 / 145 / 193 | 0 | 60 |

## Crosses that differ from stop

differ = the set of units seated differs from the stop cross (skip only adds units: stop's units are a subset, checked). Skipped members: among crosses with >= 1 skipped member.

| tier | stopped on budget (stop) | with >= 1 skipped member | differ from stop | of which gain >= 1 unit | gained units median / p90 / max | skipped per cross (with skips) median / p90 / max | skipped members total | candidates tried to seat after the first collapse (median / max) | reasons of skipped members |
|---|---|---|---|---|---|---|---|---|---|
| RUN | 1914 | 1914 | 477 (13%) | 477 | 2 / 5 / 18 | 5.0 / 17 / 315 | 16729 | 5.0 / 315 | {'max_class': 12696, 'max_moves': 4033} |
| WORD | 88 | 88 | 45 (30%) | 45 | 4 / 9 / 18 | 8.0 / 37 / 113 | 1397 | 8.0 / 113 | {'max_class': 712, 'max_moves': 685} |
| CHAR | 39 | 39 | 35 (58%) | 35 | 18 / 53 / 77 | 38 / 241 / 389 | 2958 | 38 / 389 | {'max_moves': 2947, 'max_class': 11} |

Among the differing crosses: the stop reason under stop was (left_after > 0 under stop = the stop also dropped later groups):

| tier | differ | stop had left_after > 0 | size gain 1 | gain 2-5 | gain 6+ | exhausted wholly after skipping with 0 skips (impossible) |
|---|---|---|---|---|---|---|
| RUN | 477 | 0 | 193 | 246 | 38 | 0 |
| WORD | 45 | 0 | 6 | 23 | 16 | 0 |
| CHAR | 35 | 5 | 2 | 4 | 29 | 0 |

## Cost (CPU seconds)

Pro column = f1 ordered+stop as measured on the Pro (4 workers). Air columns = the rebuilt (budget-stopped) crosses, stop and skip timed in the same worker on the Air (same machine, same load).

| tier | stop total (Pro) | skip total (reused Pro secs + rebuilt Air secs) | rebuilt crosses | stop on those (Air) | skip on those (Air) | ratio skip / stop on those |
|---|---|---|---|---|---|---|
| RUN | 3281 | 28143 | 1914 | 4890 | 27809 | 5.68 |
| WORD | 185 | 1786 | 88 | 177 | 1763 | 9.95 |
| CHAR | 273 | 5701 | 39 | 273 | 5688 | 20.80 |

Checks: RUN: Air stop build equals f1/raw units on 1914 of 1914 rebuilt, 40 reused crosses re-verified, mismatches []; WORD: Air stop build equals f1/raw units on 88 of 88 rebuilt, 10 reused crosses re-verified, mismatches []; CHAR: Air stop build equals f1/raw units on 39 of 39 rebuilt, 6 reused crosses re-verified, mismatches []

## The reach seeds (the budget-stopped crosses whose seed lies in N(question unit) and N(gold unit) of some of the 69 golds; all rebuilt)

| tier | seeds | with >= 1 skipped member | differ from stop | gained units median / max | skipped per cross median / max | CPU stop (Air) | CPU skip (Air) | ratio |
|---|---|---|---|---|---|---|---|---|
| RUN | 188 | 188 | 65 (35%) | 3 / 18 | 10.0 / 315 | 467 | 5650 | 12.1 |
| WORD | 171 | 171 | 104 (61%) | 5.0 / 76 | 17 / 672 | 413 | 16139 | 39.0 |
| CHAR | 85 | 85 | 81 (95%) | 37 / 114 | 161 / 652 | 890 | 33637 | 37.8 |
