# G3-c small run: fulllead_RUN_mid_one_first40

spec sha256 e56f5c730ba2b2e6640ee0b7ba0b53c5623a0d62422441bc9a5e7ad51ec7c635 (place), slide spec 3df141b123272f9c1ae9278a2e956d4ecd8a0e0eb6f1a8b2d95cd8251d66f7ff, scope corpus, tier RUN, padding one, level mid {"max_class": 1000, "max_states": 20000, "max_moves": 400000}

windows 40 (two-sentence 20, one-sentence 20); wall 21.9 s in total, 0.55 s per window (median 0.18 s, max 1.09 s)

## N+1 got a seat (two-sentence windows)
- strict (a seated unit that is in N+1 and not in N): 8/20 = 40.0%
- loose (a seated unit that is in N+1, shared units included): 12/20 = 60.0%
- windows that have at least one unit only in N+1: 20/20 = 100.0%
- of those, strict seat: 8/20 = 40.0%

## stop reasons
- 1-sentence budget (max_class, inside this): 9
- 1-sentence exhausted: 11
- 2-sentence budget (max_class, inside next): 6
- 2-sentence budget (max_class, inside this): 11
- 2-sentence exhausted: 3

## sizes (units seated / units in the window; class sizes)
- units in the window (median): 13; seated (median): 7; L (median): 2
- class size: median 216, max 960; windows with class size 1: 5
- windows that stopped inside sentence N: 20; inside N+1: 6; never stopped: 14
- seated fraction of the units: 286 of 572 units
- per-axis key split of the representative (sum over windows): x n=189, y n=0, z n=40
- windows whose class holds more than one per-axis split (same total key): 2
- classes larger than max_class (the terminals of the best key are not counted against max_class, as in placement._settle): 0 windows, 0 stable steps
- units on z arms (representative): 96, of which fillers with no z evidence on their inner edge: 69, on neither edge: 58

## verification (independent verifier)
- classes that are stable (one key, every member a fixed point, closed, no unit on a y arm): 40/40 = 100.0%
- diagnostic LINE (no search; x by sentence position, -z by next-sentence position): fixed point of single swaps: 18/40 = 45.0%; key below the search's: 4/40 = 10.0%; equal-key different arrangements one swap away (median): 2.5
- the line seats every unit, the search only those before its stop: compared on the windows where both seat the same units (search exhausted, 14): line key below the search's 3, equal 5, above 6
- z self-links on a seated unit (n_z(u,u) > 0; counted, a unit has one seat): 6 windows, 12 units
