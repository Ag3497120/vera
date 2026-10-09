# G3-c small run: fulllead_RUN_mid_none_pairs40

spec sha256 97efc4a9a7ec16291e2b27a23ec0eab522deb8ec07680291481a8e21238b8f22 (place), slide spec 3df141b123272f9c1ae9278a2e956d4ecd8a0e0eb6f1a8b2d95cd8251d66f7ff, scope corpus, tier RUN, padding none, level mid {"max_class": 1000, "max_states": 20000, "max_moves": 400000}

windows 40 (two-sentence 40, one-sentence 0); wall 25.3 s in total, 0.63 s per window (median 0.21 s, max 1.10 s)

## N+1 got a seat (two-sentence windows)
- strict (a seated unit that is in N+1 and not in N): 20/40 = 50.0%
- loose (a seated unit that is in N+1, shared units included): 28/40 = 70.0%
- windows that have at least one unit only in N+1: 39/40 = 97.5%
- of those, strict seat: 20/39 = 51.2%

## stop reasons
- 2-sentence budget (max_class, inside next): 10
- 2-sentence budget (max_class, inside this): 19
- 2-sentence exhausted: 11

## sizes (units seated / units in the window; class sizes)
- units in the window (median): 14; seated (median): 8; L (median): 2
- class size: median 165, max 960; windows with class size 1: 0
- windows that stopped inside sentence N: 19; inside N+1: 10; never stopped: 11
- seated fraction of the units: 339 of 644 units
- per-axis key split of the representative (sum over windows): x n=211, y n=0, z n=70
- windows whose class holds more than one per-axis split (same total key): 8
- classes larger than max_class (the terminals of the best key are not counted against max_class, as in placement._settle): 0 windows, 0 stable steps
- units on z arms (representative): 127, of which fillers with no z evidence on their inner edge: 72, on neither edge: 51

## verification (independent verifier)
- classes that are stable (one key, every member a fixed point, closed, no unit on a y arm): 40/40 = 100.0%
- diagnostic LINE (no search; x by sentence position, -z by next-sentence position): fixed point of single swaps: 14/40 = 35.0%; key below the search's: 14/40 = 35.0%; equal-key different arrangements one swap away (median): 73
- the line seats every unit, the search only those before its stop: compared on the windows where both seat the same units (search exhausted, 11): line key below the search's 9, equal 2, above 0
- z self-links on a seated unit (n_z(u,u) > 0; counted, a unit has one seat): 13 windows, 20 units
