# Meter v2 report (long stories, equal per-turn budget)

Stories: LS-D01. Repeats: [1]. Arms: A0 (context only), A1 (log + grep), A3 (structure (crosses)), A3f (flat table (no geometry)). Runs: 4.

Fewer than 3 repeats: a range is a single value, 'beats' is indicative only (OP-PUB-8 asks for ranges that do not overlap).

Every cell is `mean (min-max)` over repeats of the SUM over the stories of the set.

## Plants noticed at intake (structure notes and model reports, separately)

| metric | A0 | A1 | A3 | A3f |
|---|---|---|---|---|
| contradictions planted | 12 | 12 | 12 | 12 |
| contradictions: structure notes | 0 | 0 | 5 | 5 |
| contradictions: model reports | 1 | 12 | 4 | 6 |
| contradictions: either | 1 | 12 | 6 | 6 |
| reversals planted | 4 | 4 | 4 | 4 |
| reversals: structure notes | 0 | 0 | 3 | 2 |
| reversals: model reports | 0 | 0 | 3 | 2 |
| reversals: either | 0 | 0 | 3 | 2 |
| updates planted | 8 | 8 | 8 | 8 |
| updates: structure notes (UPDATE) | 0 | 0 | 8 | 8 |
| updates: model (supersede) | n/a | n/a | 0 | 0 |
| updates: either | 0 | 0 | 8 | 8 |
| false alarm: structure, list-trap pairs | 0 | 0 | 0 | 0 |
| false alarm: structure, unmatched (an unplanted conflict is possible) | 0 | 0 | 0 | 2 |
| false alarm: model report pairs matching no plant | 3 | 1 | 0 | 0 |

## Answers at the checkpoints

| metric | A0 | A1 | A3 | A3f |
|---|---|---|---|---|
| questions asked | 40 | 40 | 40 | 40 |
| right | 0 | 20 | 7 | 9 |
| over-broad | 0 | 0 | 0 | 0 |
| abstain | 32 | 2 | 16 | 17 |
| confident wrong | 0 | 10 | 9 | 6 |
| absent admitted (right) | 8 | 8 | 8 | 8 |
| false conflict claimed (inside confident wrong) | 0 | 0 | 5 | 2 |
| right per mille | 0 | 500 | 175 | 225 |
| present: asked | 12 | 12 | 12 | 12 |
| present: right | 0 | 11 | 3 | 3 |
| present: confident wrong | 0 | 1 | 2 | 0 |
| contested: asked | 12 | 12 | 12 | 12 |
| contested: right | 0 | 2 | 4 | 6 |
| contested: confident wrong | 0 | 8 | 4 | 4 |
| updated: asked | 8 | 8 | 8 | 8 |
| updated: right | 0 | 7 | 0 | 0 |
| updated: confident wrong | 0 | 1 | 3 | 2 |
| absent: asked | 8 | 8 | 8 | 8 |
| absent: admitted (right) | 8 | 8 | 8 | 8 |
| absent: confident wrong | 0 | 0 | 0 | 0 |

## Cost (tokens are estimates when the client is the stub)

| metric | A0 | A1 | A3 | A3f |
|---|---|---|---|---|
| input tokens | 450140 | 3968429 | 5760534 | 6228687 |
| output tokens | 12554 | 64288 | 53282 | 60397 |
| API calls (assistant turns) | 201 | 680 | 710 | 723 |
| tool calls | 201 | 854 | 925 | 1053 |
| story turns | 160 | 160 | 160 | 160 |
| turns / episodes capped by the runaway cap | 0 | 0 | 0 | 0 |
| results cut by the budget | 0 | 169 | 104 | 117 |
| characters omitted by the budget | 0 | 67958 | 58018 | 58195 |

## P2 and P3 (OP-PUB-8, changed: revise until BOTH hold)

- **P2, the structure beats the log + search** (A3 vs A1): contradictions found (either) with ranges that do not overlap, right answers at least equal, confident wrong at most equal. Verdict: **not met**.
- **P3, the geometry beats the flat table** (A3 vs A3f): ranges that do not overlap on at least one of contradictions / reversals / updates / right answers, and not worse on the others. Verdict: **not met**.

## Pre-registered predictions P-PUB-1..4 (design 6.4; thresholds are this harness's operationalisation, frozen with the code)

| id | prediction | outcome |
|---|---|---|
| P-PUB-1 | Under the budget, A1's right answers fall well below the meter v1's 55/60 (916 per mille). Operationalised: A1 right_per_mille < 750. | confirmed |
| P-PUB-2 | A3 notices more contradictions than A1 (structure or model, 'any'). Confirmed iff min over repeats of A3 > max over repeats of A1 (ranges do not overlap). | not confirmed |
| P-PUB-3 | A3 and A3f differ little on same-seat contradictions (|mean A3 - mean A3f| <= 1 plant per story-set) and A3 is higher on reversals + updates ('any'). | confirmed |
| P-PUB-4 | A3's input tokens are about those of A1 or lower. Operationalised: mean A3 <= 1.25 x mean A1. | not confirmed |

Asymmetry of A1 (see the module doc): its answer is a closed value scored by exact match, not a gate-passed quote.
