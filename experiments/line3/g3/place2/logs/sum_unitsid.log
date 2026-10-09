# G3-c2 run: fulllead_RUN_mid_none_sum_unit_sid_allow_n_then_n1_pairs292

switches {"growth": "n_then_n1", "seat_empty_axis": "allow", "seat_key": "unit_sid", "stability": "sum"}; spec sha256 f83ffc0edcfc32a9bcf30bf31959d23607ed6f5ea55b81429e6d958ccd9ffb22 (place), slide spec 3df141b123272f9c1ae9278a2e956d4ecd8a0e0eb6f1a8b2d95cd8251d66f7ff, scope corpus, tier RUN, padding none, level mid {"max_class": 1000, "max_states": 20000, "max_moves": 400000}

windows 292 (two-sentence 292, one-sentence 0); wall 109.7 s in total, 0.38 s per window (median 0.20 s, max 4.07 s)

## N+1 got a seat (two-sentence windows; seats of sentence N+1)
- strict (a seated unit that is in N+1 and not in N): 176/292 = 60.2%
- loose (a seated seat of sentence N+1, shared units' N+1 seats included): 177/292 = 60.6%
- windows that have at least one unit only in N+1: 291/292 = 99.6%
- seated N+1 seats / N+1 seats in the windows: 660/2363 = 27.9%

## stop reasons
- 2-sentence budget (max_class, inside next): 108
- 2-sentence budget (max_class, inside this): 111
- 2-sentence budget (max_moves, inside next): 1
- 2-sentence budget (max_moves, inside this): 2
- 2-sentence exhausted: 70

## sizes
- windows that stopped inside sentence N: 113; inside N+1: 109; never stopped: 70
- of the two-sentence windows: stopped inside N 113, inside N+1 109
- stop reasons of the budget stops: max_class 219, max_states 0, max_moves 3, no_seat 0
- units(seats) in the window (median): 16; seated (median): 9; L (median): 2, max 4
- class size: median 168, max 2160; windows with class size 1: 1
- classes larger than max_class: 2 windows
- seated fraction of the seats: 2531 of 4785
- windows whose final class holds more than one per-axis key: 53 (keys per window: median 1, max 3)
- per-axis key of the representative (sum over windows): x n=1504, y n=0, z n=546; summed key n=2050
- z-arm units (representative): 1010, without z evidence on their inner edge: 534, on neither edge: 332
- windows with z evidence: 292; seatless arms (windows with at least one arm denied beyond y): 0
- units with two seats (windows 102, units 164): both seated 45, the two seats directly linked by a cross edge 18
- moves of the representative: tested 13044, improving one axis and worsening another (not taken) 207, Pareto-improving (must be 0) 0

## verification (independent verifier; swaps of 12 evenly spread members per class, keys / closure / legality of all)
- classes that are stable (every checked member a fixed point, closed, antichain of keys, centre non-empty, no seat on a seatless arm or against the reservation): 292/292 = 100.0%
