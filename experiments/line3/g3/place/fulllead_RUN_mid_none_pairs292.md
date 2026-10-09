# G3-c small run: fulllead_RUN_mid_none_pairs292

spec sha256 97efc4a9a7ec16291e2b27a23ec0eab522deb8ec07680291481a8e21238b8f22 (place), slide spec 3df141b123272f9c1ae9278a2e956d4ecd8a0e0eb6f1a8b2d95cd8251d66f7ff, scope corpus, tier RUN, padding none, level mid {"max_class": 1000, "max_states": 20000, "max_moves": 400000}

windows 292 (two-sentence 292, one-sentence 0); wall 226.6 s in total, 0.78 s per window (median 0.19 s, max 4.00 s)

## N+1 got a seat (two-sentence windows)
- strict (a seated unit that is in N+1 and not in N): 178/292 = 60.9%
- loose (a seated unit that is in N+1, shared units included): 209/292 = 71.5%
- windows that have at least one unit only in N+1: 291/292 = 99.6%
- of those, strict seat: 178/291 = 61.1%

## stop reasons
- 2-sentence budget (max_class, inside both): 4
- 2-sentence budget (max_class, inside next): 104
- 2-sentence budget (max_class, inside this): 107
- 2-sentence budget (max_moves, inside next): 1
- 2-sentence budget (max_moves, inside this): 2
- 2-sentence exhausted: 74

## sizes (units seated / units in the window; class sizes)
- units in the window (median): 15; seated (median): 9; L (median): 2
- class size: median 174, max 2160; windows with class size 1: 2
- windows that stopped inside sentence N: 113; inside N+1: 105; never stopped: 74
- seated fraction of the units: 2512 of 4621 units
- per-axis key split of the representative (sum over windows): x n=1476, y n=0, z n=508
- windows whose class holds more than one per-axis split (same total key): 57
- classes larger than max_class (the terminals of the best key are not counted against max_class, as in placement._settle): 2 windows, 5 stable steps
- units on z arms (representative): 1000, of which fillers with no z evidence on their inner edge: 547, on neither edge: 338

## verification (independent verifier)
- classes that are stable (one key, every member a fixed point, closed, no unit on a y arm): 292/292 = 100.0%
- diagnostic LINE (no search; x by sentence position, -z by next-sentence position): fixed point of single swaps: 135/292 = 46.2%; key below the search's: 101/292 = 34.5%; equal-key different arrangements one swap away (median): 86.5
- the line seats every unit, the search only those before its stop: compared on the windows where both seat the same units (search exhausted, 74): line key below the search's 50, equal 17, above 7
- z self-links on a seated unit (n_z(u,u) > 0; counted, a unit has one seat): 81 windows, 124 units
