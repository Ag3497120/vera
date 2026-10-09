# G3-c4 window caches: z_deep slide vs order (fulllead, RUN, level mid, padding one, centre both + budget + strict; the pair windows)

- slide: `slidewin_725d5ac1a8d2_RUN_3df141b12327_07db87511ff1.pkl`; slide spec 3df141b12327, place spec 07db87511ff1; 592 windows in the cache (292 pairs); build wall 87 s, cpu 516 s
- order: `slidewin_725d5ac1a8d2_RUN_6b36bcb7306d_9280bce0035a.pkl`; slide spec 6b36bcb7306d, place spec 9280bce0035a; 592 windows in the cache (292 pairs); build wall 65 s, cpu 381 s

| per run (292 pair windows) | z_deep slide (G3-c3 run A) | z_deep order |
|---|---|---|
| centre of the representative in N / in N+1 | 218 / 74 | 275 / 17 |
| growths kept (single N / single N+1 / both) | 112 / 74 / 106 | 26 / 17 / 249 |
| other sentence seated, strict | 241/292 = 82.5% | 241/292 = 82.5% |
| units seated / units of the pairs | 3220/4785 = 67.2% | 3774/4785 = 78.8% |
| z-arm seats with evidence on the inner edge: +z depth 1 | 74/142 = 52.1% | 36/184 = 19.5% |
| z-arm seats with evidence on the inner edge: +z deeper | 12/126 = 9.5% | 446/446 = 100.0% |
| z-arm seats with evidence on the inner edge: -z depth 1 | 176/237 = 74.2% | 232/238 = 97.4% |
| z-arm seats with evidence on the inner edge: -z deeper | 43/370 = 11.6% | 698/698 = 100.0% |
| ... all z-arm seats | 305/875 = 34.8% | 1412/1566 = 90.1% |
| ... deeper seats (any arm) | 55/496 = 11.0% | 1144/1144 = 100.0% |
| deeper z edges with both ends seated: with a count | 55/496 = 11.0% | 1144/1144 = 100.0% |
| real N<->N+1 edges per window, median / max | 1 / 2 | 2 / 2 |
| windows with none / exactly one / two such edges | 51 / 103 / 138 | 51 / 60 / 181 |
| ... of those edges, with a count | 250/379 = 65.9% | 268/422 = 63.5% |
| stopped: inside the centre's / inside the other sentence / cap / never | 51 / 135 / 0 / 106 | 51 / 64 / 0 / 177 |
| budget stops | 186 | 115 |
| representative strictly stable | 276/292 = 94.5% | 271/292 = 92.8% |
| marked UNSTABLE_AXIS_IMPROVABLE | 16 | 21 |
| members strictly stable (all members of all classes) | 128477/131852 = 97.4% | 53863/55561 = 96.9% |
| windows with at least one strictly stable member | 291/292 = 99.6% | 291/292 = 99.6% |
| class size median / max | 426 / 2079 | 101 / 1309 |
| arm length L median / max | 4 / 8 | 5 / 9 |
| z-axis key n of the representative, median / max | 1 / 7 | 5 / 22 |
| x-axis key n of the representative, median / max | 8 / 39 | 7 / 39 |

("evidence" of a z-arm edge: n > 0 of the rule the edge used: n_z for the innermost edge (depth 1) and, under slide, for every edge; n_x of the pair under order for the deeper edges.  A real N<->N+1 edge = a cross edge whose two ends are seats of different sentences.  The z-axis key of the two runs is NOT comparable: under order it also sums word-order counts.)
