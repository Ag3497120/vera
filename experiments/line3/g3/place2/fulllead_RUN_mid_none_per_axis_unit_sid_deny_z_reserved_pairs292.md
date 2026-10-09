# G3-c2 run: fulllead_RUN_mid_none_per_axis_unit_sid_deny_z_reserved_pairs292

switches {"growth": "z_reserved", "seat_empty_axis": "deny", "seat_key": "unit_sid", "stability": "per_axis"}; spec sha256 7615d5cc32a88029e5bb2d8e4206bbffe098c1a3b8233db5c77a730dfb7ff5a7 (place), slide spec 3df141b123272f9c1ae9278a2e956d4ecd8a0e0eb6f1a8b2d95cd8251d66f7ff, scope corpus, tier RUN, padding none, level mid {"max_class": 1000, "max_states": 20000, "max_moves": 400000}

windows 292 (two-sentence 292, one-sentence 0); wall 206.2 s in total, 0.71 s per window (median 0.38 s, max 3.73 s)

## N+1 got a seat (two-sentence windows; seats of sentence N+1)
- strict (a seated unit that is in N+1 and not in N): 236/292 = 80.8%
- loose (a seated seat of sentence N+1, shared units' N+1 seats included): 236/292 = 80.8%
- windows that have at least one unit only in N+1: 291/292 = 99.6%
- seated N+1 seats / N+1 seats in the windows: 953/2363 = 40.3%

## stop reasons
- 2-sentence budget (max_class, inside next): 131
- 2-sentence budget (max_class, inside this): 56
- 2-sentence budget (max_moves, inside next): 8
- 2-sentence exhausted: 97

## sizes
- windows that stopped inside sentence N: 56; inside N+1: 139; never stopped: 97
- of the two-sentence windows: stopped inside N 56, inside N+1 139
- stop reasons of the budget stops: max_class 187, max_states 0, max_moves 8, no_seat 0
- units(seats) in the window (median): 16; seated (median): 11; L (median): 3, max 8
- class size: median 240, max 960; windows with class size 1: 42
- classes larger than max_class: 0 windows
- seated fraction of the seats: 3150 of 4785
- windows whose final class holds more than one per-axis key: 0 (keys per window: median 1, max 1)
- per-axis key of the representative (sum over windows): x n=2277, y n=0, z n=321; summed key n=2598
- z-arm units (representative): 953, without z evidence on their inner edge: 656, on neither edge: 634
- windows with z evidence: 292; seatless arms (windows with at least one arm denied beyond y): 1
- units with two seats (windows 102, units 164): both seated 61, the two seats directly linked by a cross edge 10
- moves of the representative: tested 13830, improving one axis and worsening another (not taken) 22, Pareto-improving (must be 0) 0

## verification (independent verifier; swaps of 12 evenly spread members per class, keys / closure / legality of all)
- classes that are stable (every checked member a fixed point, closed, antichain of keys, centre non-empty, no seat on a seatless arm or against the reservation): 292/292 = 100.0%
