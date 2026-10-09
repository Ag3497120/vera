# G3-c2 run: fulllead_RUN_mid_none_per_axis_unit_allow_n_then_n1_pairs292

switches {"growth": "n_then_n1", "seat_empty_axis": "allow", "seat_key": "unit", "stability": "per_axis"}; spec sha256 84c41f2104406271f45aadd805abd69a7b26c8a487a6db751de97b46e436cd37 (place), slide spec 3df141b123272f9c1ae9278a2e956d4ecd8a0e0eb6f1a8b2d95cd8251d66f7ff, scope corpus, tier RUN, padding none, level mid {"max_class": 1000, "max_states": 20000, "max_moves": 400000}

windows 292 (two-sentence 292, one-sentence 0); wall 145.6 s in total, 0.50 s per window (median 0.24 s, max 5.00 s)

## N+1 got a seat (two-sentence windows; seats of sentence N+1)
- strict (a seated unit that is in N+1 and not in N): 177/292 = 60.6%
- loose (a seated seat of sentence N+1, shared units' N+1 seats included): 209/292 = 71.5%
- windows that have at least one unit only in N+1: 291/292 = 99.6%
- seated N+1 seats / N+1 seats in the windows: 772/2363 = 32.6%

## stop reasons
- 2-sentence budget (max_class, inside both): 5
- 2-sentence budget (max_class, inside next): 101
- 2-sentence budget (max_class, inside this): 106
- 2-sentence budget (max_moves, inside next): 3
- 2-sentence budget (max_moves, inside this): 3
- 2-sentence exhausted: 74

## sizes
- windows that stopped inside sentence N: 114; inside N+1: 104; never stopped: 74
- of the two-sentence windows: stopped inside N 114, inside N+1 104
- stop reasons of the budget stops: max_class 212, max_states 0, max_moves 6, no_seat 0
- units(seats) in the window (median): 15; seated (median): 9; L (median): 2, max 4
- class size: median 240, max 2160; windows with class size 1: 2
- classes larger than max_class: 7 windows
- seated fraction of the seats: 2516 of 4621
- windows whose final class holds more than one per-axis key: 48 (keys per window: median 1, max 4)
- per-axis key of the representative (sum over windows): x n=1481, y n=0, z n=459; summed key n=1940
- z-arm units (representative): 986, without z evidence on their inner edge: 575, on neither edge: 404
- windows with z evidence: 292; seatless arms (windows with at least one arm denied beyond y): 0
- units with two seats (windows 0, units 0): both seated 0, the two seats directly linked by a cross edge 0
- moves of the representative: tested 12844, improving one axis and worsening another (not taken) 338, Pareto-improving (must be 0) 0

## verification (independent verifier; swaps of 12 evenly spread members per class, keys / closure / legality of all)
- classes that are stable (every checked member a fixed point, closed, antichain of keys, centre non-empty, no seat on a seatless arm or against the reservation): 292/292 = 100.0%
