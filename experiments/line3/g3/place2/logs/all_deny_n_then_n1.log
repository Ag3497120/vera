# G3-c2 run: fulllead_RUN_mid_none_per_axis_unit_sid_deny_n_then_n1_all

switches {"growth": "n_then_n1", "seat_empty_axis": "deny", "seat_key": "unit_sid", "stability": "per_axis"}; spec sha256 75f3e63b3c463dab8f8f5842d7a7f035305094d00d1d8d9a3cc96424026d4a31 (place), slide spec 3df141b123272f9c1ae9278a2e956d4ecd8a0e0eb6f1a8b2d95cd8251d66f7ff, scope corpus, tier RUN, padding none, level mid {"max_class": 1000, "max_states": 20000, "max_moves": 400000}

windows 592 (two-sentence 292, one-sentence 300); wall 186.6 s in total, 0.32 s per window (median 0.13 s, max 5.03 s)

## N+1 got a seat (two-sentence windows; seats of sentence N+1)
- strict (a seated unit that is in N+1 and not in N): 174/292 = 59.5%
- loose (a seated seat of sentence N+1, shared units' N+1 seats included): 174/292 = 59.5%
- windows that have at least one unit only in N+1: 291/292 = 99.6%
- seated N+1 seats / N+1 seats in the windows: 663/2363 = 28.0%

## stop reasons
- 1-sentence budget (max_class, inside this): 61
- 1-sentence exhausted: 239
- 2-sentence budget (max_class, inside next): 103
- 2-sentence budget (max_class, inside this): 111
- 2-sentence budget (max_moves, inside next): 3
- 2-sentence budget (max_moves, inside this): 3
- 2-sentence exhausted: 72

## sizes
- windows that stopped inside sentence N: 175; inside N+1: 106; never stopped: 311
- of the two-sentence windows: stopped inside N 114, inside N+1 106
- stop reasons of the budget stops: max_class 275, max_states 0, max_moves 6, no_seat 0
- units(seats) in the window (median): 10; seated (median): 8; L (median): 2, max 10
- class size: median 16, max 2160; windows with class size 1: 239
- classes larger than max_class: 7 windows
- seated fraction of the seats: 4637 of 7173
- windows whose final class holds more than one per-axis key: 57 (keys per window: median 1, max 4)
- per-axis key of the representative (sum over windows): x n=3640, y n=0, z n=482; summed key n=4122
- z-arm units (representative): 994, without z evidence on their inner edge: 570, on neither edge: 407
- windows with z evidence: 292; seatless arms (windows with at least one arm denied beyond y): 301
- units with two seats (windows 102, units 164): both seated 39, the two seats directly linked by a cross edge 13
- moves of the representative: tested 21850, improving one axis and worsening another (not taken) 374, Pareto-improving (must be 0) 0

## verification (independent verifier; swaps of 12 evenly spread members per class, keys / closure / legality of all)
- classes that are stable (every checked member a fixed point, closed, antichain of keys, centre non-empty, no seat on a seatless arm or against the reservation): 592/592 = 100.0%
