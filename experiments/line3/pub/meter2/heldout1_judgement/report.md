# Meter v2 report (long stories, equal per-turn budget)

Stories: LS-H1-01, LS-H1-02, LS-H1-03, LS-H1-04, LS-H1-05, LS-H1-06. Repeats: [1, 2, 3]. Arms: A0 (context only), A1 (log + grep), A3 (structure (crosses)), A3f (flat table (no geometry)), A1v (log + grep, raw message appended by the harness (arms.v2 only)). Runs: 90.

Every cell is `mean (min-max)` over repeats of the SUM over the stories of the set.

## Plants noticed at intake (structure notes and model reports, separately)

| metric | A0 | A1 | A3 | A3f | A1v |
|---|---|---|---|---|---|
| contradictions planted | 72 | 72 | 72 | 72 | 72 |
| contradictions: structure notes | 0 | 0 | 29 (28-30) | 26 (25-28) | 0 |
| contradictions: model reports | 8.7 (8-9) | 62.7 (62-63) | 29 (25-32) | 27.3 (25-29) | 71 |
| contradictions: either | 8.7 (8-9) | 62.7 (62-63) | 33.3 (32-35) | 30.7 (30-32) | 71 |
| reversals planted | 24 | 24 | 24 | 24 | 24 |
| reversals: structure notes | 0 | 0 | 16 (15-17) | 17.3 (16-19) | 0 |
| reversals: model reports | 0 | 0.3 (0-1) | 14.7 (13-16) | 15.7 (14-18) | 10 (9-12) |
| reversals: either | 0 | 0.3 (0-1) | 16 (15-17) | 17.3 (16-19) | 10 (9-12) |
| updates planted | 48 | 48 | 48 | 48 | 48 |
| updates: structure notes (UPDATE) | 0 | 0 | 41 | 41 | 0 |
| updates: model (supersede) | n/a | n/a | 0 | 0 | n/a |
| updates: either | 0 | 0 | 41 | 41 | 0 |
| false alarm: structure, list-trap pairs | 0 | 0 | 0 | 0 | 0 |
| false alarm: structure, unmatched (an unplanted conflict is possible) | 0 | 0 | 33.3 (28-36) | 9.7 (8-11) | 0 |
| false alarm: model report pairs matching no plant | 14.7 (14-15) | 37.3 (33-41) | 21.7 (14-30) | 25.7 (14-36) | 53.7 (45-59) |

## Answers at the checkpoints

| metric | A0 | A1 | A3 | A3f | A1v |
|---|---|---|---|---|---|
| questions asked | 240 | 240 | 240 | 240 | 240 |
| right | 0 | 90 (87-94) | 25 (23-27) | 25 (22-28) | 106 (104-108) |
| over-broad | 0 | 2.3 (2-3) | 0 | 0 | 2.7 (1-4) |
| abstain | 192 | 15.7 (11-22) | 148 (145-150) | 148.3 (143-154) | 24 (23-25) |
| confident wrong | 0 | 94 (91-100) | 19 (17-20) | 18.7 (16-21) | 61.7 (59-64) |
| absent admitted (right) | 48 | 38 (37-39) | 48 | 48 | 45.7 (45-47) |
| false conflict claimed (inside confident wrong) | 0 | 0 | 11 (10-12) | 12.7 (11-15) | 0 |
| right per mille | 0 | 2250 (2175-2350) | 625 (575-675) | 625 (550-700) | 2650 (2600-2700) |
| present: asked | 72 | 72 | 72 | 72 | 72 |
| present: right | 0 | 46.7 (44-51) | 3 | 3 | 53.7 (53-54) |
| present: confident wrong | 0 | 16.3 (13-20) | 1.7 (1-2) | 2.3 (2-3) | 7.7 (7-8) |
| contested: asked | 72 | 72 | 72 | 72 | 72 |
| contested: right | 0 | 15.7 (13-19) | 22 (20-24) | 22 (19-25) | 11.7 (10-13) |
| contested: confident wrong | 0 | 49 (46-51) | 8 (6-10) | 6 (4-8) | 48 (47-50) |
| updated: asked | 48 | 48 | 48 | 48 | 48 |
| updated: right | 0 | 27.7 (26-29) | 0 | 0 | 40.7 (40-41) |
| updated: confident wrong | 0 | 18.7 (18-20) | 9.3 (8-11) | 10.3 (9-12) | 3.7 (3-5) |
| absent: asked | 48 | 48 | 48 | 48 | 48 |
| absent: admitted (right) | 48 | 38 (37-39) | 48 | 48 | 45.7 (45-47) |
| absent: confident wrong | 0 | 10 (9-11) | 0 | 0 | 2.3 (1-3) |

## Cost (tokens are estimates when the client is the stub)

| metric | A0 | A1 | A3 | A3f | A1v |
|---|---|---|---|---|---|
| input tokens | 2487154.3 (2479104-2494483) | 25476564 (24175204-27113968) | 33181029.3 (32556222-33675907) | 33126936.3 (30753172-35170279) | 30152319 (29752287-30730788) |
| output tokens | 59691 (59288-60093) | 374351.3 (366127-382423) | 344689 (341347-349403) | 345786.7 (321918-361755) | 391737 (388350-396438) |
| API calls (assistant turns) | 979.3 (977-981) | 3950.3 (3852-4045) | 3744.3 (3698-3805) | 3730.7 (3579-3890) | 4509.3 (4455-4583) |
| tool calls | 979.3 (977-981) | 4758 (4651-4860) | 5593.7 (5552-5663) | 5605 (5247-5881) | 4603.7 (4563-4681) |
| story turns | 732 | 732 | 732 | 732 | 732 |
| turns / episodes capped by the runaway cap | 0 | 0 | 0 | 1 (0-2) | 3.7 (3-5) |
| results cut by the budget | 0 | 946.7 (807-1101) | 345.7 (283-416) | 309.7 (243-387) | 1284.3 (1216-1367) |
| characters omitted by the budget | 0 | 301969.3 (257115-341221) | 179788 (140267-209798) | 159793.7 (126150-199731) | 448571.7 (425015-474361) |

## P2 and P3 (OP-PUB-8, changed: revise until BOTH hold)

- **P2, the structure beats the log + search** (A3 vs A1): contradictions found (either) with ranges that do not overlap, right answers at least equal, confident wrong at most equal. Verdict: **not met**.
- **P3, the geometry beats the flat table** (A3 vs A3f): ranges that do not overlap on at least one of contradictions / reversals / updates / right answers, and not worse on the others. Verdict: **not met**.

## Pre-registered predictions P-PUB-1..4 (design 6.4; thresholds are this harness's operationalisation, frozen with the code)

| id | prediction | outcome |
|---|---|---|
| P-PUB-1 | Under the budget, A1's right answers fall well below the meter v1's 55/60 (916 per mille). Operationalised: A1 right_per_mille < 750. | not confirmed |
| P-PUB-2 | A3 notices more contradictions than A1 (structure or model, 'any'). Confirmed iff min over repeats of A3 > max over repeats of A1 (ranges do not overlap). | not confirmed |
| P-PUB-3 | A3 and A3f differ little on same-seat contradictions (|mean A3 - mean A3f| <= 1 plant per story-set) and A3 is higher on reversals + updates ('any'). | not confirmed |
| P-PUB-4 | A3's input tokens are about those of A1 or lower. Operationalised: mean A3 <= 1.25 x mean A1. | not confirmed |

Asymmetry of A1 (see the module doc): its answer is a closed value scored by exact match, not a gate-passed quote.

## Arm version and who writes the memory

Arm version(s) in these runs: arms.v2. arms.v1 = the pilot's arms (the model writes its own words). arms.v2 = A3 / A3f writes must be VERBATIM WHOLE SENTENCES of the delivered message (a refused write stores nothing), declared topics must be pieces of the story's own words, A3 and A3f identically; A0 / A1 unchanged; A1v = A1 with the raw message appended to the log by the harness.

**A1's log is MODEL-WRITTEN** (the model chooses and words every line, at most 64 characters): its recall is bounded by what the model chose to write. A1v's log is the raw story (every sentence, appended automatically), so A1 vs A1v measures the cost of the model's own log writing.

Verbatim gate (writes accepted by the gate / refused as not verbatim / topics refused): A3 r01 207 / 90 / 3; A3 r02 220 / 96 / 3; A3 r03 262 / 92 / 3; A3f r01 245 / 100 / 4; A3f r02 195 / 112 / 3; A3f r03 220 / 114 / 6; A3 r01 209 / 12 / 0; A3 r02 194 / 19 / 0; A3 r03 219 / 12 / 0; A3f r01 177 / 18 / 0; A3f r02 165 / 20 / 0; A3f r03 206 / 25 / 0; A3 r01 606 / 86 / 0; A3 r02 534 / 54 / 0; A3 r03 554 / 75 / 0; A3f r01 674 / 59 / 0; A3f r02 535 / 52 / 0; A3f r03 578 / 53 / 0; A3 r01 450 / 20 / 1; A3 r02 524 / 29 / 0; A3 r03 360 / 23 / 0; A3f r01 533 / 22 / 0; A3f r02 410 / 23 / 0; A3f r03 620 / 27 / 0; A3 r01 192 / 54 / 0; A3 r02 204 / 46 / 0; A3 r03 275 / 48 / 0; A3f r01 240 / 48 / 0; A3f r02 181 / 47 / 0; A3f r03 212 / 68 / 0; A3 r01 112 / 14 / 0; A3 r02 109 / 15 / 0; A3 r03 114 / 18 / 0; A3f r01 109 / 9 / 0; A3f r02 111 / 8 / 0; A3f r03 111 / 10 / 0.

## Updated questions, one by one (class; abstain type)

| arm | repeat | question index | class | answer status |
|---|---|---|---|---|
| A0 | 1 | 2 | abstain | none |
| A0 | 1 | 6 | abstain | none |
| A0 | 1 | 16 | abstain | none |
| A0 | 1 | 12 | abstain | none |
| A0 | 1 | 26 | abstain | none |
| A0 | 1 | 22 | abstain | none |
| A0 | 1 | 36 | abstain | none |
| A0 | 1 | 32 | abstain | none |
| A0 | 1 | 3 | abstain | none |
| A0 | 1 | 8 | abstain | none |
| A0 | 1 | 17 | abstain | none |
| A0 | 1 | 10 | abstain | none |
| A0 | 1 | 23 | abstain | none |
| A0 | 1 | 29 | abstain | none |
| A0 | 1 | 32 | abstain | none |
| A0 | 1 | 37 | abstain | none |
| A0 | 1 | 6 | abstain | none |
| A0 | 1 | 1 | abstain | none |
| A0 | 1 | 13 | abstain | none |
| A0 | 1 | 18 | abstain | none |
| A0 | 1 | 27 | abstain | none |
| A0 | 1 | 23 | abstain | none |
| A0 | 1 | 35 | abstain | none |
| A0 | 1 | 30 | abstain | none |
| A0 | 1 | 6 | abstain | none |
| A0 | 1 | 3 | abstain | none |
| A0 | 1 | 13 | abstain | none |
| A0 | 1 | 17 | abstain | none |
| A0 | 1 | 27 | abstain | none |
| A0 | 1 | 23 | abstain | none |
| A0 | 1 | 33 | abstain | none |
| A0 | 1 | 37 | abstain | none |
| A0 | 1 | 7 | abstain | none |
| A0 | 1 | 3 | abstain | none |
| A0 | 1 | 17 | abstain | none |
| A0 | 1 | 13 | abstain | none |
| A0 | 1 | 23 | abstain | none |
| A0 | 1 | 27 | abstain | none |
| A0 | 1 | 33 | abstain | none |
| A0 | 1 | 37 | abstain | none |
| A0 | 1 | 3 | abstain | none |
| A0 | 1 | 6 | abstain | none |
| A0 | 1 | 16 | abstain | none |
| A0 | 1 | 13 | abstain | none |
| A0 | 1 | 23 | abstain | none |
| A0 | 1 | 26 | abstain | none |
| A0 | 1 | 33 | abstain | none |
| A0 | 1 | 36 | abstain | none |
| A0 | 2 | 2 | abstain | none |
| A0 | 2 | 6 | abstain | none |
| A0 | 2 | 16 | abstain | none |
| A0 | 2 | 12 | abstain | none |
| A0 | 2 | 22 | abstain | none |
| A0 | 2 | 26 | abstain | none |
| A0 | 2 | 36 | abstain | none |
| A0 | 2 | 32 | abstain | none |
| A0 | 2 | 3 | abstain | none |
| A0 | 2 | 8 | abstain | none |
| A0 | 2 | 10 | abstain | none |
| A0 | 2 | 17 | abstain | none |
| A0 | 2 | 29 | abstain | none |
| A0 | 2 | 23 | abstain | none |
| A0 | 2 | 37 | abstain | none |
| A0 | 2 | 32 | abstain | none |
| A0 | 2 | 1 | abstain | none |
| A0 | 2 | 6 | abstain | none |
| A0 | 2 | 18 | abstain | none |
| A0 | 2 | 13 | abstain | none |
| A0 | 2 | 27 | abstain | none |
| A0 | 2 | 23 | abstain | none |
| A0 | 2 | 30 | abstain | none |
| A0 | 2 | 35 | abstain | none |
| A0 | 2 | 3 | abstain | none |
| A0 | 2 | 6 | abstain | none |
| A0 | 2 | 17 | abstain | none |
| A0 | 2 | 13 | abstain | none |
| A0 | 2 | 23 | abstain | none |
| A0 | 2 | 27 | abstain | none |
| A0 | 2 | 37 | abstain | none |
| A0 | 2 | 33 | abstain | none |
| A0 | 2 | 7 | abstain | none |
| A0 | 2 | 3 | abstain | none |
| A0 | 2 | 17 | abstain | none |
| A0 | 2 | 13 | abstain | none |
| A0 | 2 | 27 | abstain | none |
| A0 | 2 | 23 | abstain | none |
| A0 | 2 | 33 | abstain | none |
| A0 | 2 | 37 | abstain | none |
| A0 | 2 | 6 | abstain | none |
| A0 | 2 | 3 | abstain | none |
| A0 | 2 | 13 | abstain | none |
| A0 | 2 | 16 | abstain | none |
| A0 | 2 | 23 | abstain | none |
| A0 | 2 | 26 | abstain | none |
| A0 | 2 | 36 | abstain | none |
| A0 | 2 | 33 | abstain | none |
| A0 | 3 | 2 | abstain | none |
| A0 | 3 | 6 | abstain | none |
| A0 | 3 | 12 | abstain | none |
| A0 | 3 | 16 | abstain | none |
| A0 | 3 | 26 | abstain | none |
| A0 | 3 | 22 | abstain | none |
| A0 | 3 | 32 | abstain | none |
| A0 | 3 | 36 | abstain | none |
| A0 | 3 | 8 | abstain | none |
| A0 | 3 | 3 | abstain | none |
| A0 | 3 | 10 | abstain | none |
| A0 | 3 | 17 | abstain | none |
| A0 | 3 | 29 | abstain | none |
| A0 | 3 | 23 | abstain | none |
| A0 | 3 | 32 | abstain | none |
| A0 | 3 | 37 | abstain | none |
| A0 | 3 | 1 | abstain | none |
| A0 | 3 | 6 | abstain | none |
| A0 | 3 | 13 | abstain | none |
| A0 | 3 | 18 | abstain | none |
| A0 | 3 | 23 | abstain | none |
| A0 | 3 | 27 | abstain | none |
| A0 | 3 | 35 | abstain | none |
| A0 | 3 | 30 | abstain | none |
| A0 | 3 | 6 | abstain | none |
| A0 | 3 | 3 | abstain | none |
| A0 | 3 | 17 | abstain | none |
| A0 | 3 | 13 | abstain | none |
| A0 | 3 | 27 | abstain | none |
| A0 | 3 | 23 | abstain | none |
| A0 | 3 | 33 | abstain | none |
| A0 | 3 | 37 | abstain | none |
| A0 | 3 | 7 | abstain | none |
| A0 | 3 | 3 | abstain | none |
| A0 | 3 | 13 | abstain | none |
| A0 | 3 | 17 | abstain | none |
| A0 | 3 | 27 | abstain | none |
| A0 | 3 | 23 | abstain | none |
| A0 | 3 | 37 | abstain | none |
| A0 | 3 | 33 | abstain | none |
| A0 | 3 | 6 | abstain | none |
| A0 | 3 | 3 | abstain | none |
| A0 | 3 | 13 | abstain | none |
| A0 | 3 | 16 | abstain | none |
| A0 | 3 | 26 | abstain | none |
| A0 | 3 | 23 | abstain | none |
| A0 | 3 | 36 | abstain | none |
| A0 | 3 | 33 | abstain | none |
| A1 | 1 | 2 | right | value |
| A1 | 1 | 6 | right | value |
| A1 | 1 | 16 | right | value |
| A1 | 1 | 12 | right | value |
| A1 | 1 | 26 | right | value |
| A1 | 1 | 22 | confident_wrong | value |
| A1 | 1 | 36 | right | value |
| A1 | 1 | 32 | right | value |
| A1 | 1 | 3 | confident_wrong | value |
| A1 | 1 | 8 | confident_wrong | value |
| A1 | 1 | 17 | confident_wrong | value |
| A1 | 1 | 10 | confident_wrong | value |
| A1 | 1 | 23 | confident_wrong | value |
| A1 | 1 | 29 | confident_wrong | value |
| A1 | 1 | 32 | confident_wrong | value |
| A1 | 1 | 37 | confident_wrong | value |
| A1 | 1 | 6 | right | value |
| A1 | 1 | 1 | right | value |
| A1 | 1 | 13 | right | value |
| A1 | 1 | 18 | right | value |
| A1 | 1 | 27 | right | value |
| A1 | 1 | 23 | right | value |
| A1 | 1 | 35 | right | value |
| A1 | 1 | 30 | right | value |
| A1 | 1 | 6 | confident_wrong | value |
| A1 | 1 | 3 | confident_wrong | value |
| A1 | 1 | 13 | confident_wrong | value |
| A1 | 1 | 17 | confident_wrong | value |
| A1 | 1 | 27 | abstain | none |
| A1 | 1 | 23 | confident_wrong | value |
| A1 | 1 | 33 | confident_wrong | value |
| A1 | 1 | 37 | confident_wrong | value |
| A1 | 1 | 7 | right | value |
| A1 | 1 | 3 | right | value |
| A1 | 1 | 17 | confident_wrong | value |
| A1 | 1 | 13 | right | value |
| A1 | 1 | 23 | right | value |
| A1 | 1 | 27 | right | value |
| A1 | 1 | 33 | right | value |
| A1 | 1 | 37 | right | value |
| A1 | 1 | 3 | right | value |
| A1 | 1 | 6 | right | value |
| A1 | 1 | 16 | right | value |
| A1 | 1 | 13 | right | value |
| A1 | 1 | 23 | confident_wrong | value |
| A1 | 1 | 26 | right | value |
| A1 | 1 | 33 | right | value |
| A1 | 1 | 36 | right | value |
| A1 | 2 | 2 | right | value |
| A1 | 2 | 6 | right | value |
| A1 | 2 | 16 | right | value |
| A1 | 2 | 12 | right | value |
| A1 | 2 | 22 | over_broad | value |
| A1 | 2 | 26 | right | value |
| A1 | 2 | 36 | right | value |
| A1 | 2 | 32 | right | value |
| A1 | 2 | 3 | confident_wrong | value |
| A1 | 2 | 8 | confident_wrong | value |
| A1 | 2 | 10 | confident_wrong | value |
| A1 | 2 | 17 | confident_wrong | value |
| A1 | 2 | 29 | confident_wrong | value |
| A1 | 2 | 23 | confident_wrong | value |
| A1 | 2 | 37 | confident_wrong | value |
| A1 | 2 | 32 | confident_wrong | value |
| A1 | 2 | 1 | right | value |
| A1 | 2 | 6 | right | value |
| A1 | 2 | 18 | right | value |
| A1 | 2 | 13 | right | value |
| A1 | 2 | 27 | right | value |
| A1 | 2 | 23 | right | value |
| A1 | 2 | 30 | right | value |
| A1 | 2 | 35 | right | value |
| A1 | 2 | 3 | confident_wrong | value |
| A1 | 2 | 6 | confident_wrong | value |
| A1 | 2 | 17 | confident_wrong | value |
| A1 | 2 | 13 | confident_wrong | value |
| A1 | 2 | 23 | confident_wrong | value |
| A1 | 2 | 27 | abstain | none |
| A1 | 2 | 37 | confident_wrong | value |
| A1 | 2 | 33 | confident_wrong | value |
| A1 | 2 | 7 | right | value |
| A1 | 2 | 3 | confident_wrong | value |
| A1 | 2 | 17 | confident_wrong | value |
| A1 | 2 | 13 | right | value |
| A1 | 2 | 27 | right | value |
| A1 | 2 | 23 | right | value |
| A1 | 2 | 33 | right | value |
| A1 | 2 | 37 | right | value |
| A1 | 2 | 6 | right | value |
| A1 | 2 | 3 | right | value |
| A1 | 2 | 13 | right | value |
| A1 | 2 | 16 | right | value |
| A1 | 2 | 23 | confident_wrong | value |
| A1 | 2 | 26 | right | value |
| A1 | 2 | 36 | right | value |
| A1 | 2 | 33 | right | value |
| A1 | 3 | 2 | right | value |
| A1 | 3 | 6 | right | value |
| A1 | 3 | 12 | right | value |
| A1 | 3 | 16 | right | value |
| A1 | 3 | 26 | right | value |
| A1 | 3 | 22 | over_broad | value |
| A1 | 3 | 32 | right | value |
| A1 | 3 | 36 | right | value |
| A1 | 3 | 8 | confident_wrong | value |
| A1 | 3 | 3 | confident_wrong | value |
| A1 | 3 | 10 | confident_wrong | value |
| A1 | 3 | 17 | confident_wrong | value |
| A1 | 3 | 29 | confident_wrong | value |
| A1 | 3 | 23 | confident_wrong | value |
| A1 | 3 | 32 | confident_wrong | value |
| A1 | 3 | 37 | confident_wrong | value |
| A1 | 3 | 1 | right | value |
| A1 | 3 | 6 | right | value |
| A1 | 3 | 13 | right | value |
| A1 | 3 | 18 | right | value |
| A1 | 3 | 23 | right | value |
| A1 | 3 | 27 | right | value |
| A1 | 3 | 35 | right | value |
| A1 | 3 | 30 | right | value |
| A1 | 3 | 6 | confident_wrong | value |
| A1 | 3 | 3 | confident_wrong | value |
| A1 | 3 | 17 | confident_wrong | value |
| A1 | 3 | 13 | confident_wrong | value |
| A1 | 3 | 27 | abstain | none |
| A1 | 3 | 23 | confident_wrong | value |
| A1 | 3 | 33 | confident_wrong | value |
| A1 | 3 | 37 | confident_wrong | value |
| A1 | 3 | 7 | right | value |
| A1 | 3 | 3 | confident_wrong | value |
| A1 | 3 | 13 | right | value |
| A1 | 3 | 17 | right | value |
| A1 | 3 | 27 | right | value |
| A1 | 3 | 23 | right | value |
| A1 | 3 | 37 | right | value |
| A1 | 3 | 33 | right | value |
| A1 | 3 | 6 | right | value |
| A1 | 3 | 3 | confident_wrong | value |
| A1 | 3 | 13 | right | value |
| A1 | 3 | 16 | right | value |
| A1 | 3 | 26 | confident_wrong | value |
| A1 | 3 | 23 | confident_wrong | value |
| A1 | 3 | 36 | confident_wrong | value |
| A1 | 3 | 33 | right | value |
| A3 | 1 | 2 | abstain | no_record |
| A3 | 1 | 6 | confident_wrong | contested |
| A3 | 1 | 16 | confident_wrong | contested |
| A3 | 1 | 12 | confident_wrong | contested |
| A3 | 1 | 26 | confident_wrong | contested |
| A3 | 1 | 22 | abstain | no_record |
| A3 | 1 | 36 | abstain | no_record |
| A3 | 1 | 32 | abstain | cannot_weave |
| A3 | 1 | 3 | abstain | cannot_weave |
| A3 | 1 | 8 | abstain | cannot_weave |
| A3 | 1 | 17 | confident_wrong | contested |
| A3 | 1 | 10 | abstain | cannot_weave |
| A3 | 1 | 23 | abstain | cannot_weave |
| A3 | 1 | 29 | confident_wrong | contested |
| A3 | 1 | 32 | abstain | cannot_weave |
| A3 | 1 | 37 | abstain | no_record |
| A3 | 1 | 6 | abstain | no_record |
| A3 | 1 | 1 | abstain | no_record |
| A3 | 1 | 13 | abstain | no_record |
| A3 | 1 | 18 | abstain | no_record |
| A3 | 1 | 27 | abstain | cannot_weave |
| A3 | 1 | 23 | abstain | unknown |
| A3 | 1 | 35 | abstain | no_record |
| A3 | 1 | 30 | abstain | no_record |
| A3 | 1 | 6 | abstain | cannot_weave |
| A3 | 1 | 3 | abstain | cannot_weave |
| A3 | 1 | 13 | abstain | no_record |
| A3 | 1 | 17 | confident_wrong | contested |
| A3 | 1 | 27 | abstain | no_record |
| A3 | 1 | 23 | abstain | unknown |
| A3 | 1 | 33 | confident_wrong | contested |
| A3 | 1 | 37 | abstain | cannot_weave |
| A3 | 1 | 7 | abstain | no_record |
| A3 | 1 | 3 | abstain | no_record |
| A3 | 1 | 17 | abstain | no_record |
| A3 | 1 | 13 | abstain | no_record |
| A3 | 1 | 23 | abstain | no_record |
| A3 | 1 | 27 | confident_wrong | contested |
| A3 | 1 | 33 | abstain | no_record |
| A3 | 1 | 37 | abstain | cannot_weave |
| A3 | 1 | 3 | abstain | no_record |
| A3 | 1 | 6 | abstain | no_record |
| A3 | 1 | 16 | abstain | cannot_weave |
| A3 | 1 | 13 | abstain | no_record |
| A3 | 1 | 23 | abstain | no_record |
| A3 | 1 | 26 | abstain | cannot_weave |
| A3 | 1 | 33 | abstain | cannot_weave |
| A3 | 1 | 36 | abstain | cannot_weave |
| A3 | 2 | 2 | abstain | no_record |
| A3 | 2 | 6 | confident_wrong | contested |
| A3 | 2 | 16 | confident_wrong | contested |
| A3 | 2 | 12 | abstain | no_record |
| A3 | 2 | 22 | abstain | no_record |
| A3 | 2 | 26 | confident_wrong | contested |
| A3 | 2 | 36 | confident_wrong | contested |
| A3 | 2 | 32 | confident_wrong | contested |
| A3 | 2 | 3 | abstain | cannot_weave |
| A3 | 2 | 8 | abstain | cannot_weave |
| A3 | 2 | 10 | abstain | no_record |
| A3 | 2 | 17 | abstain | cannot_weave |
| A3 | 2 | 29 | confident_wrong | contested |
| A3 | 2 | 23 | abstain | cannot_weave |
| A3 | 2 | 37 | abstain | no_record |
| A3 | 2 | 32 | abstain | cannot_weave |
| A3 | 2 | 1 | abstain | no_record |
| A3 | 2 | 6 | abstain | no_record |
| A3 | 2 | 18 | abstain | no_record |
| A3 | 2 | 13 | abstain | cannot_weave |
| A3 | 2 | 27 | abstain | no_record |
| A3 | 2 | 23 | abstain | unknown |
| A3 | 2 | 30 | abstain | no_record |
| A3 | 2 | 35 | abstain | no_record |
| A3 | 2 | 3 | abstain | cannot_weave |
| A3 | 2 | 6 | abstain | cannot_weave |
| A3 | 2 | 17 | confident_wrong | contested |
| A3 | 2 | 13 | abstain | no_record |
| A3 | 2 | 23 | abstain | unknown |
| A3 | 2 | 27 | abstain | no_record |
| A3 | 2 | 37 | abstain | no_record |
| A3 | 2 | 33 | confident_wrong | contested |
| A3 | 2 | 7 | abstain | no_record |
| A3 | 2 | 3 | abstain | no_record |
| A3 | 2 | 17 | abstain | cannot_weave |
| A3 | 2 | 13 | abstain | no_record |
| A3 | 2 | 27 | confident_wrong | contested |
| A3 | 2 | 23 | abstain | no_record |
| A3 | 2 | 33 | confident_wrong | contested |
| A3 | 2 | 37 | abstain | no_record |
| A3 | 2 | 6 | abstain | no_record |
| A3 | 2 | 3 | confident_wrong | contested |
| A3 | 2 | 13 | abstain | no_record |
| A3 | 2 | 16 | abstain | unknown |
| A3 | 2 | 23 | abstain | no_record |
| A3 | 2 | 26 | abstain | cannot_weave |
| A3 | 2 | 36 | abstain | cannot_weave |
| A3 | 2 | 33 | abstain | no_record |
| A3 | 3 | 2 | abstain | no_record |
| A3 | 3 | 6 | abstain | no_record |
| A3 | 3 | 12 | confident_wrong | contested |
| A3 | 3 | 16 | confident_wrong | contested |
| A3 | 3 | 26 | confident_wrong | contested |
| A3 | 3 | 22 | abstain | no_record |
| A3 | 3 | 32 | abstain | cannot_weave |
| A3 | 3 | 36 | abstain | no_record |
| A3 | 3 | 8 | abstain | cannot_weave |
| A3 | 3 | 3 | abstain | cannot_weave |
| A3 | 3 | 10 | abstain | cannot_weave |
| A3 | 3 | 17 | abstain | cannot_weave |
| A3 | 3 | 29 | confident_wrong | contested |
| A3 | 3 | 23 | abstain | cannot_weave |
| A3 | 3 | 32 | abstain | cannot_weave |
| A3 | 3 | 37 | abstain | no_record |
| A3 | 3 | 1 | abstain | no_record |
| A3 | 3 | 6 | abstain | no_record |
| A3 | 3 | 13 | abstain | cannot_weave |
| A3 | 3 | 18 | abstain | no_record |
| A3 | 3 | 23 | abstain | no_record |
| A3 | 3 | 27 | abstain | no_record |
| A3 | 3 | 35 | abstain | no_record |
| A3 | 3 | 30 | abstain | no_record |
| A3 | 3 | 6 | confident_wrong | contested |
| A3 | 3 | 3 | abstain | no_record |
| A3 | 3 | 17 | abstain | cannot_weave |
| A3 | 3 | 13 | abstain | no_record |
| A3 | 3 | 27 | abstain | no_record |
| A3 | 3 | 23 | abstain | no_record |
| A3 | 3 | 33 | confident_wrong | contested |
| A3 | 3 | 37 | abstain | cannot_weave |
| A3 | 3 | 7 | abstain | no_record |
| A3 | 3 | 3 | abstain | no_record |
| A3 | 3 | 13 | abstain | no_record |
| A3 | 3 | 17 | abstain | cannot_weave |
| A3 | 3 | 27 | confident_wrong | contested |
| A3 | 3 | 23 | abstain | no_record |
| A3 | 3 | 37 | abstain | no_record |
| A3 | 3 | 33 | confident_wrong | contested |
| A3 | 3 | 6 | abstain | no_record |
| A3 | 3 | 3 | abstain | no_record |
| A3 | 3 | 13 | abstain | no_record |
| A3 | 3 | 16 | abstain | cannot_weave |
| A3 | 3 | 26 | abstain | cannot_weave |
| A3 | 3 | 23 | abstain | no_record |
| A3 | 3 | 36 | abstain | cannot_weave |
| A3 | 3 | 33 | abstain | no_record |
| A3f | 1 | 2 | abstain | no_record |
| A3f | 1 | 6 | confident_wrong | contested |
| A3f | 1 | 16 | confident_wrong | contested |
| A3f | 1 | 12 | abstain | no_record |
| A3f | 1 | 26 | confident_wrong | contested |
| A3f | 1 | 22 | abstain | no_record |
| A3f | 1 | 36 | abstain | no_record |
| A3f | 1 | 32 | confident_wrong | contested |
| A3f | 1 | 3 | abstain | cannot_weave |
| A3f | 1 | 8 | confident_wrong | contested |
| A3f | 1 | 17 | abstain | cannot_weave |
| A3f | 1 | 10 | abstain | cannot_weave |
| A3f | 1 | 23 | abstain | no_record |
| A3f | 1 | 29 | abstain | cannot_weave |
| A3f | 1 | 32 | abstain | cannot_weave |
| A3f | 1 | 37 | abstain | no_record |
| A3f | 1 | 6 | abstain | no_record |
| A3f | 1 | 1 | abstain | no_record |
| A3f | 1 | 13 | confident_wrong | contested |
| A3f | 1 | 18 | abstain | no_record |
| A3f | 1 | 27 | abstain | cannot_weave |
| A3f | 1 | 23 | abstain | cannot_weave |
| A3f | 1 | 35 | abstain | no_record |
| A3f | 1 | 30 | abstain | no_record |
| A3f | 1 | 6 | abstain | cannot_weave |
| A3f | 1 | 3 | abstain | cannot_weave |
| A3f | 1 | 13 | abstain | no_record |
| A3f | 1 | 17 | abstain | cannot_weave |
| A3f | 1 | 27 | abstain | no_record |
| A3f | 1 | 23 | abstain | unknown |
| A3f | 1 | 33 | confident_wrong | contested |
| A3f | 1 | 37 | abstain | unknown |
| A3f | 1 | 7 | abstain | no_record |
| A3f | 1 | 3 | abstain | cannot_weave |
| A3f | 1 | 17 | abstain | cannot_weave |
| A3f | 1 | 13 | abstain | no_record |
| A3f | 1 | 23 | confident_wrong | contested |
| A3f | 1 | 27 | confident_wrong | contested |
| A3f | 1 | 33 | confident_wrong | contested |
| A3f | 1 | 37 | abstain | no_record |
| A3f | 1 | 3 | abstain | no_record |
| A3f | 1 | 6 | abstain | no_record |
| A3f | 1 | 16 | abstain | unknown |
| A3f | 1 | 13 | abstain | no_record |
| A3f | 1 | 23 | abstain | no_record |
| A3f | 1 | 26 | abstain | cannot_weave |
| A3f | 1 | 33 | abstain | no_record |
| A3f | 1 | 36 | abstain | cannot_weave |
| A3f | 2 | 2 | abstain | no_record |
| A3f | 2 | 6 | confident_wrong | contested |
| A3f | 2 | 16 | confident_wrong | contested |
| A3f | 2 | 12 | abstain | no_record |
| A3f | 2 | 22 | abstain | no_record |
| A3f | 2 | 26 | confident_wrong | contested |
| A3f | 2 | 36 | abstain | no_record |
| A3f | 2 | 32 | abstain | cannot_weave |
| A3f | 2 | 3 | abstain | cannot_weave |
| A3f | 2 | 8 | abstain | no_record |
| A3f | 2 | 10 | abstain | cannot_weave |
| A3f | 2 | 17 | abstain | cannot_weave |
| A3f | 2 | 29 | confident_wrong | contested |
| A3f | 2 | 23 | abstain | no_record |
| A3f | 2 | 37 | abstain | no_record |
| A3f | 2 | 32 | abstain | cannot_weave |
| A3f | 2 | 1 | abstain | no_record |
| A3f | 2 | 6 | abstain | no_record |
| A3f | 2 | 18 | abstain | no_record |
| A3f | 2 | 13 | confident_wrong | contested |
| A3f | 2 | 27 | abstain | no_record |
| A3f | 2 | 23 | abstain | cannot_weave |
| A3f | 2 | 30 | abstain | no_record |
| A3f | 2 | 35 | abstain | no_record |
| A3f | 2 | 3 | abstain | cannot_weave |
| A3f | 2 | 6 | confident_wrong | contested |
| A3f | 2 | 17 | abstain | cannot_weave |
| A3f | 2 | 13 | abstain | no_record |
| A3f | 2 | 23 | abstain | unknown |
| A3f | 2 | 27 | abstain | no_record |
| A3f | 2 | 37 | abstain | no_record |
| A3f | 2 | 33 | confident_wrong | contested |
| A3f | 2 | 7 | abstain | no_record |
| A3f | 2 | 3 | abstain | no_record |
| A3f | 2 | 17 | abstain | cannot_weave |
| A3f | 2 | 13 | abstain | no_record |
| A3f | 2 | 27 | confident_wrong | contested |
| A3f | 2 | 23 | abstain | no_record |
| A3f | 2 | 33 | confident_wrong | contested |
| A3f | 2 | 37 | abstain | no_record |
| A3f | 2 | 6 | abstain | cannot_weave |
| A3f | 2 | 3 | abstain | no_record |
| A3f | 2 | 13 | abstain | no_record |
| A3f | 2 | 16 | abstain | unknown |
| A3f | 2 | 23 | abstain | no_record |
| A3f | 2 | 26 | abstain | cannot_weave |
| A3f | 2 | 36 | abstain | cannot_weave |
| A3f | 2 | 33 | abstain | no_record |
| A3f | 3 | 2 | abstain | no_record |
| A3f | 3 | 6 | confident_wrong | contested |
| A3f | 3 | 12 | confident_wrong | contested |
| A3f | 3 | 16 | confident_wrong | contested |
| A3f | 3 | 26 | confident_wrong | contested |
| A3f | 3 | 22 | abstain | no_record |
| A3f | 3 | 32 | confident_wrong | contested |
| A3f | 3 | 36 | abstain | no_record |
| A3f | 3 | 8 | abstain | cannot_weave |
| A3f | 3 | 3 | abstain | cannot_weave |
| A3f | 3 | 10 | abstain | cannot_weave |
| A3f | 3 | 17 | confident_wrong | contested |
| A3f | 3 | 29 | confident_wrong | contested |
| A3f | 3 | 23 | abstain | no_record |
| A3f | 3 | 32 | abstain | cannot_weave |
| A3f | 3 | 37 | abstain | no_record |
| A3f | 3 | 1 | abstain | no_record |
| A3f | 3 | 6 | abstain | no_record |
| A3f | 3 | 13 | confident_wrong | contested |
| A3f | 3 | 18 | abstain | no_record |
| A3f | 3 | 23 | abstain | cannot_weave |
| A3f | 3 | 27 | abstain | no_record |
| A3f | 3 | 35 | abstain | no_record |
| A3f | 3 | 30 | abstain | no_record |
| A3f | 3 | 6 | abstain | cannot_weave |
| A3f | 3 | 3 | abstain | cannot_weave |
| A3f | 3 | 17 | abstain | cannot_weave |
| A3f | 3 | 13 | abstain | no_record |
| A3f | 3 | 27 | abstain | no_record |
| A3f | 3 | 23 | abstain | no_record |
| A3f | 3 | 33 | confident_wrong | contested |
| A3f | 3 | 37 | abstain | unknown |
| A3f | 3 | 7 | abstain | cannot_weave |
| A3f | 3 | 3 | abstain | no_record |
| A3f | 3 | 13 | abstain | cannot_weave |
| A3f | 3 | 17 | abstain | no_record |
| A3f | 3 | 27 | confident_wrong | contested |
| A3f | 3 | 23 | confident_wrong | contested |
| A3f | 3 | 37 | abstain | no_record |
| A3f | 3 | 33 | abstain | no_record |
| A3f | 3 | 6 | abstain | no_record |
| A3f | 3 | 3 | abstain | no_record |
| A3f | 3 | 13 | abstain | no_record |
| A3f | 3 | 16 | abstain | unknown |
| A3f | 3 | 26 | abstain | cannot_weave |
| A3f | 3 | 23 | abstain | no_record |
| A3f | 3 | 36 | abstain | cannot_weave |
| A3f | 3 | 33 | confident_wrong | contested |
| A1v | 1 | 2 | abstain | none |
| A1v | 1 | 6 | right | value |
| A1v | 1 | 16 | right | value |
| A1v | 1 | 12 | right | value |
| A1v | 1 | 26 | right | value |
| A1v | 1 | 22 | over_broad | value |
| A1v | 1 | 36 | abstain | none |
| A1v | 1 | 32 | right | value |
| A1v | 1 | 3 | over_broad | value |
| A1v | 1 | 8 | right | value |
| A1v | 1 | 17 | right | value |
| A1v | 1 | 10 | right | value |
| A1v | 1 | 23 | confident_wrong | value |
| A1v | 1 | 29 | right | value |
| A1v | 1 | 32 | right | value |
| A1v | 1 | 37 | confident_wrong | value |
| A1v | 1 | 6 | right | value |
| A1v | 1 | 1 | abstain | none |
| A1v | 1 | 13 | right | value |
| A1v | 1 | 18 | right | value |
| A1v | 1 | 27 | right | value |
| A1v | 1 | 23 | right | value |
| A1v | 1 | 35 | right | value |
| A1v | 1 | 30 | right | value |
| A1v | 1 | 6 | right | value |
| A1v | 1 | 3 | right | value |
| A1v | 1 | 13 | right | value |
| A1v | 1 | 17 | right | value |
| A1v | 1 | 27 | right | value |
| A1v | 1 | 23 | right | value |
| A1v | 1 | 33 | right | value |
| A1v | 1 | 37 | right | value |
| A1v | 1 | 7 | right | value |
| A1v | 1 | 3 | confident_wrong | value |
| A1v | 1 | 17 | right | value |
| A1v | 1 | 13 | right | value |
| A1v | 1 | 23 | right | value |
| A1v | 1 | 27 | right | value |
| A1v | 1 | 33 | right | value |
| A1v | 1 | 37 | right | value |
| A1v | 1 | 3 | right | value |
| A1v | 1 | 6 | right | value |
| A1v | 1 | 16 | right | value |
| A1v | 1 | 13 | right | value |
| A1v | 1 | 23 | right | value |
| A1v | 1 | 26 | right | value |
| A1v | 1 | 33 | right | value |
| A1v | 1 | 36 | right | value |
| A1v | 2 | 2 | right | value |
| A1v | 2 | 6 | right | value |
| A1v | 2 | 16 | right | value |
| A1v | 2 | 12 | right | value |
| A1v | 2 | 22 | right | value |
| A1v | 2 | 26 | right | value |
| A1v | 2 | 36 | right | value |
| A1v | 2 | 32 | right | value |
| A1v | 2 | 3 | right | value |
| A1v | 2 | 8 | right | value |
| A1v | 2 | 10 | right | value |
| A1v | 2 | 17 | right | value |
| A1v | 2 | 29 | confident_wrong | value |
| A1v | 2 | 23 | confident_wrong | value |
| A1v | 2 | 37 | confident_wrong | value |
| A1v | 2 | 32 | right | value |
| A1v | 2 | 1 | right | value |
| A1v | 2 | 6 | right | value |
| A1v | 2 | 18 | right | value |
| A1v | 2 | 13 | right | value |
| A1v | 2 | 27 | right | value |
| A1v | 2 | 23 | right | value |
| A1v | 2 | 30 | right | value |
| A1v | 2 | 35 | right | value |
| A1v | 2 | 3 | right | value |
| A1v | 2 | 6 | right | value |
| A1v | 2 | 17 | confident_wrong | value |
| A1v | 2 | 13 | right | value |
| A1v | 2 | 23 | confident_wrong | value |
| A1v | 2 | 27 | abstain | none |
| A1v | 2 | 37 | right | value |
| A1v | 2 | 33 | right | value |
| A1v | 2 | 7 | right | value |
| A1v | 2 | 3 | right | value |
| A1v | 2 | 17 | right | value |
| A1v | 2 | 13 | abstain | none |
| A1v | 2 | 27 | right | value |
| A1v | 2 | 23 | right | value |
| A1v | 2 | 33 | right | value |
| A1v | 2 | 37 | right | value |
| A1v | 2 | 6 | right | value |
| A1v | 2 | 3 | right | value |
| A1v | 2 | 13 | right | value |
| A1v | 2 | 16 | right | value |
| A1v | 2 | 23 | right | value |
| A1v | 2 | 26 | right | value |
| A1v | 2 | 36 | right | value |
| A1v | 2 | 33 | right | value |
| A1v | 3 | 2 | right | value |
| A1v | 3 | 6 | right | value |
| A1v | 3 | 12 | right | value |
| A1v | 3 | 16 | right | value |
| A1v | 3 | 26 | right | value |
| A1v | 3 | 22 | right | value |
| A1v | 3 | 32 | right | value |
| A1v | 3 | 36 | right | value |
| A1v | 3 | 8 | right | value |
| A1v | 3 | 3 | right | value |
| A1v | 3 | 10 | right | value |
| A1v | 3 | 17 | right | value |
| A1v | 3 | 29 | over_broad | value |
| A1v | 3 | 23 | right | value |
| A1v | 3 | 32 | right | value |
| A1v | 3 | 37 | confident_wrong | value |
| A1v | 3 | 1 | right | value |
| A1v | 3 | 6 | right | value |
| A1v | 3 | 13 | right | value |
| A1v | 3 | 18 | right | value |
| A1v | 3 | 23 | right | value |
| A1v | 3 | 27 | right | value |
| A1v | 3 | 35 | right | value |
| A1v | 3 | 30 | right | value |
| A1v | 3 | 6 | right | value |
| A1v | 3 | 3 | right | value |
| A1v | 3 | 17 | confident_wrong | value |
| A1v | 3 | 13 | right | value |
| A1v | 3 | 27 | abstain | none |
| A1v | 3 | 23 | right | value |
| A1v | 3 | 33 | right | value |
| A1v | 3 | 37 | right | value |
| A1v | 3 | 7 | right | value |
| A1v | 3 | 3 | confident_wrong | value |
| A1v | 3 | 13 | abstain | none |
| A1v | 3 | 17 | right | value |
| A1v | 3 | 27 | right | value |
| A1v | 3 | 23 | right | value |
| A1v | 3 | 37 | right | value |
| A1v | 3 | 33 | right | value |
| A1v | 3 | 6 | right | value |
| A1v | 3 | 3 | right | value |
| A1v | 3 | 13 | right | value |
| A1v | 3 | 16 | right | value |
| A1v | 3 | 26 | right | value |
| A1v | 3 | 23 | abstain | none |
| A1v | 3 | 36 | right | value |
| A1v | 3 | 33 | right | value |
