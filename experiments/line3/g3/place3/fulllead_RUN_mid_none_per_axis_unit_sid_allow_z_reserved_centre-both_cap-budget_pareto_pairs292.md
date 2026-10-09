# G3-c3 run: fulllead_RUN_mid_none_per_axis_unit_sid_allow_z_reserved_centre-both_cap-budget_pareto_pairs292

switches {"growth": "z_reserved", "seat_empty_axis": "allow", "seat_key": "unit_sid", "stability": "per_axis"} + {"arm_cap": "budget", "centre_scope": "both", "stability_judgement": "pareto"}; spec sha256 ffdf59572956f7d60ebb61aec92c47c99df5f4a11df2b9fc52dd7fb066b1e286 (place), slide spec 3df141b123272f9c1ae9278a2e956d4ecd8a0e0eb6f1a8b2d95cd8251d66f7ff, scope corpus, tier RUN, padding none, level mid {"max_class": 1000, "max_states": 20000, "max_moves": 400000}

windows 292 (two-sentence 292, one-sentence 0); wall 434.9 s in total, 1.49 s per window (median 1.19 s, max 5.99 s)

## the centre (representative; two-sentence windows 292)
- centre in N: 218, in N+1: 74 (of the one-sentence windows the centre is in N: 0)
- choice between the two growths (two-sentence windows): both_equal 15, both_incomparable 91, next 74, this 112
- class members with the centre in N / in N+1 (sum over windows): 70446 / 61406
## the other sentence (the one the z arms hold) got a seat (two-sentence windows)
- strict (a seated unit that is only in the other sentence): 241/292 = 82.5%
- loose (a seated seat of the other sentence, shared units' seats included): 241/292 = 82.5%
- seated seats of the other sentence / its seats in the windows: 875/2240 = 39.0%
- (N+1's own strict share, for comparison with G3-c2: 247/292 = 84.5%)

## stops (representative's growth; relative to the centre's sentence)
- stopped inside the centre's sentence: 51; inside the other sentence: 135; arm_cap x (units of the other sentence unseated, no budget stop): 0; never stopped: 106
- stop reasons of the budget stops: max_class 175, max_states 0, max_moves 11, no_seat 0
- unseated by arm_cap x: windows 0, units 0

## z-arm seats of the representative with z evidence on their inner edge (evidenced / seats)
- +z d1: 74/142 = 52.1%
- +z deeper: 12/126 = 9.5%
- -z d1: 176/237 = 74.2%
- -z deeper: 43/370 = 11.6%
- all z-arm seats: 305/875 = 34.8%
- real N<->N+1 edges per window (cross edges whose ends are seats of different sentences; two-sentence windows): median 1, max 2; of them with a count > 0: median 1, max 2
- windows with exactly one / none / more than one real N<->N+1 edge: 103 / 51 / 138

## stability
- representative strictly stable (no single legal move improves any axis): 276/292 = 94.5%; marked unstable (typed UNSTABLE_PARETO_IMPROVABLE): 0; by axis improvable: {}
- representative Pareto stable: 292/292 = 100.0%; the record's strict counts equal the independent verifier's (axis_improvable) on 292/292 = 100.0%
- members strictly stable (sum over windows): 128477/131852 = 97.4%; windows with at least one strictly stable member: 291/292 = 99.6%

## sizes
- class size: median 426, max 2079; windows with class size 1: 6; classes larger than max_class: 16 windows
- L: median 4, max 8
- seats in the window (median): 16; seated by the representative (median): 11; seated fraction: 3220 of 4785
- windows whose final class holds more than one per-axis key: 91 (keys per window: median 1, max 2)
- per-axis key of the representative (sum over windows): x n=2540, y n=0, z n=335

## verification (independent verifier; swaps of 12 evenly spread members per class, keys / closure / legality of all)
- classes that are stable (every checked member a Pareto fixed point under the member's own reservation, closed, antichain, centre non-empty, no seat against the reservation): 292/292 = 100.0%
