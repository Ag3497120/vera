# G3-h window caches: arm_cap x z_deep x seat_empty_axis (fulllead, RUN, level mid, padding one, centre both, strict, z_reserved, unit_sid; the 292 pair windows)

- budget / slide / allow: `slidewin_725d5ac1a8d2_RUN_3df141b12327_07db87511ff1.pkl`; slide spec 3df141b12327, place spec 07db87511ff1; 592 windows (292 pairs); build wall 80 s, cpu 477 s
- budget / slide / deny: `slidewin_725d5ac1a8d2_RUN_3df141b12327_45402f30e7e3.pkl`; slide spec 3df141b12327, place spec 45402f30e7e3; 592 windows (292 pairs); build wall 85 s, cpu 503 s
- budget / order / allow: `slidewin_725d5ac1a8d2_RUN_6b36bcb7306d_9280bce0035a.pkl`; slide spec 6b36bcb7306d, place spec 9280bce0035a; 592 windows (292 pairs); build wall 75 s, cpu 436 s
- budget / order / deny: `slidewin_725d5ac1a8d2_RUN_6b36bcb7306d_cf35f420cea6.pkl`; slide spec 6b36bcb7306d, place spec cf35f420cea6; 592 windows (292 pairs); build wall 70 s, cpu 410 s
- budget / order_window / allow: `slidewin_725d5ac1a8d2_RUN_3a9ef919a0bb_bf765f4da473.pkl`; slide spec 3a9ef919a0bb, place spec bf765f4da473; 592 windows (292 pairs); build wall 74 s, cpu 435 s
- budget / order_window / deny: `slidewin_725d5ac1a8d2_RUN_3a9ef919a0bb_33590d7cdefc.pkl`; slide spec 3a9ef919a0bb, place spec 33590d7cdefc; 592 windows (292 pairs); build wall 76 s, cpu 444 s
- x / slide / allow: `slidewin_725d5ac1a8d2_RUN_3df141b12327_f9af37611eb0.pkl`; slide spec 3df141b12327, place spec f9af37611eb0; 592 windows (292 pairs); build wall 86 s, cpu 509 s
- x / slide / deny: `slidewin_725d5ac1a8d2_RUN_3df141b12327_8728c32d3fb6.pkl`; slide spec 3df141b12327, place spec 8728c32d3fb6; 592 windows (292 pairs); build wall 80 s, cpu 473 s
- x / order / allow: `slidewin_725d5ac1a8d2_RUN_6b36bcb7306d_2da39eb4fba5.pkl`; slide spec 6b36bcb7306d, place spec 2da39eb4fba5; 592 windows (292 pairs); build wall 54 s, cpu 306 s
- x / order / deny: `slidewin_725d5ac1a8d2_RUN_6b36bcb7306d_95a3b9853130.pkl`; slide spec 6b36bcb7306d, place spec 95a3b9853130; 592 windows (292 pairs); build wall 53 s, cpu 296 s
- x / order_window / allow: `slidewin_725d5ac1a8d2_RUN_3a9ef919a0bb_a44cc22d6ed5.pkl`; slide spec 3a9ef919a0bb, place spec a44cc22d6ed5; 592 windows (292 pairs); build wall 52 s, cpu 293 s
- x / order_window / deny: `slidewin_725d5ac1a8d2_RUN_3a9ef919a0bb_a935be6c6c01.pkl`; slide spec 3a9ef919a0bb, place spec a935be6c6c01; 592 windows (292 pairs); build wall 52 s, cpu 294 s

### seat_empty_axis allow

| per run (292 pair windows) | budget/slide/allow | budget/order/allow | budget/order_window/allow | x/slide/allow | x/order/allow | x/order_window/allow |
|---|---|---|---|---|---|---|
| centre of the representative in N / in N+1 | 218 / 74 | 275 / 17 | 269 / 23 | 218 / 74 | 226 / 66 | 223 / 69 |
| growths kept (single N / single N+1 / both) | 112 / 74 / 106 | 26 / 17 / 249 | 36 / 23 / 233 | 116 / 74 / 102 | 106 / 66 / 120 | 116 / 69 / 107 |
| other sentence seated, strict (N+1 seated for a centre in N) | 241/292 = 82.5% | 241/292 = 82.5% | 241/292 = 82.5% | 241/292 = 82.5% | 241/292 = 82.5% | 241/292 = 82.5% |
| units seated / units of the pairs | 3220/4785 = 67.2% | 3774/4785 = 78.8% | 3722/4785 = 77.7% | 3155/4785 = 65.9% | 3507/4785 = 73.2% | 3505/4785 = 73.2% |
| real N<->N+1 edges per window, median / max | 1 / 2 | 2 / 2 | 2 / 2 | 1 / 2 | 2 / 2 | 2 / 2 |
| windows with none / exactly one / two such edges | 51 / 103 / 138 | 51 / 60 / 181 | 51 / 62 / 179 | 51 / 103 / 138 | 51 / 75 / 166 | 51 / 79 / 162 |
| ... of those edges, with a count | 250/379 = 65.9% | 268/422 = 63.5% | 267/420 = 63.5% | 250/379 = 65.9% | 263/407 = 64.6% | 263/403 = 65.2% |
| deeper z edges with both ends seated: with a count (n > 0) | 55/496 = 11.0% | 1144/1144 = 100.0% | 1098/1098 = 100.0% | 53/431 = 12.2% | 763/763 = 100.0% | 755/755 = 100.0% |
| ... with the arm's direction (omega > 0) | 55/496 = 11.0% | 1122/1144 = 98.0% | 1086/1098 = 98.9% | 53/431 = 12.2% | 747/763 = 97.9% | 746/755 = 98.8% |
| z-arm seats with evidence on the inner edge, all | 305/875 = 34.8% | 1412/1566 = 90.1% | 1365/1518 = 89.9% | 303/810 = 37.4% | 1026/1170 = 87.6% | 1018/1158 = 87.9% |
| budget stops | 186 | 115 | 128 | 147 | 74 | 78 |
| cap stops (arm_cap x) / units unseated by the cap | 0 / 0 | 0 / 0 | 0 / 0 | 52 / 351 | 74 / 486 | 71 / 455 |
| stopped: inside the centre's / inside the other sentence / cap / never | 51 / 135 / 0 / 106 | 51 / 64 / 0 / 177 | 51 / 77 / 0 / 164 | 51 / 96 / 52 / 93 | 51 / 23 / 74 / 144 | 51 / 27 / 71 / 143 |
| representative strictly stable | 276/292 = 94.5% | 271/292 = 92.8% | 270/292 = 92.4% | 275/292 = 94.1% | 268/292 = 91.7% | 266/292 = 91.0% |
| members strictly stable (all members of all classes) | 128477/131852 = 97.4% | 53863/55561 = 96.9% | 62928/66197 = 95.0% | 95092/97695 = 97.3% | 26594/27547 = 96.5% | 27949/29301 = 95.3% |
| windows with at least one strictly stable member | 291/292 = 99.6% | 291/292 = 99.6% | 292/292 = 100.0% | 290/292 = 99.3% | 281/292 = 96.2% | 282/292 = 96.5% |
| class size median / max | 426 / 2079 | 101 / 1309 | 206 / 1224 | 216 / 2079 | 13.5 / 966 | 20 / 966 |
| arm length L median / max | 4 / 8 | 5 / 9 | 5 / 8 | 4 / 8 | 4 / 8 | 4 / 8 |

### seat_empty_axis deny

| per run (292 pair windows) | budget/slide/deny | budget/order/deny | budget/order_window/deny | x/slide/deny | x/order/deny | x/order_window/deny |
|---|---|---|---|---|---|---|
| centre of the representative in N / in N+1 | 218 / 74 | 275 / 17 | 269 / 23 | 218 / 74 | 226 / 66 | 223 / 69 |
| growths kept (single N / single N+1 / both) | 112 / 74 / 106 | 26 / 17 / 249 | 36 / 23 / 233 | 116 / 74 / 102 | 106 / 66 / 120 | 116 / 69 / 107 |
| other sentence seated, strict (N+1 seated for a centre in N) | 241/292 = 82.5% | 241/292 = 82.5% | 241/292 = 82.5% | 241/292 = 82.5% | 241/292 = 82.5% | 241/292 = 82.5% |
| units seated / units of the pairs | 3220/4785 = 67.2% | 3774/4785 = 78.8% | 3722/4785 = 77.7% | 3155/4785 = 65.9% | 3507/4785 = 73.2% | 3505/4785 = 73.2% |
| real N<->N+1 edges per window, median / max | 1 / 2 | 2 / 2 | 2 / 2 | 1 / 2 | 2 / 2 | 2 / 2 |
| windows with none / exactly one / two such edges | 51 / 103 / 138 | 51 / 60 / 181 | 51 / 62 / 179 | 51 / 103 / 138 | 51 / 75 / 166 | 51 / 79 / 162 |
| ... of those edges, with a count | 250/379 = 65.9% | 268/422 = 63.5% | 267/420 = 63.5% | 250/379 = 65.9% | 263/407 = 64.6% | 263/403 = 65.2% |
| deeper z edges with both ends seated: with a count (n > 0) | 55/496 = 11.0% | 1144/1144 = 100.0% | 1098/1098 = 100.0% | 53/431 = 12.2% | 763/763 = 100.0% | 755/755 = 100.0% |
| ... with the arm's direction (omega > 0) | 55/496 = 11.0% | 1122/1144 = 98.0% | 1086/1098 = 98.9% | 53/431 = 12.2% | 747/763 = 97.9% | 746/755 = 98.8% |
| z-arm seats with evidence on the inner edge, all | 305/875 = 34.8% | 1412/1566 = 90.1% | 1365/1518 = 89.9% | 303/810 = 37.4% | 1026/1170 = 87.6% | 1018/1158 = 87.9% |
| budget stops | 186 | 115 | 128 | 147 | 74 | 78 |
| cap stops (arm_cap x) / units unseated by the cap | 0 / 0 | 0 / 0 | 0 / 0 | 52 / 351 | 74 / 486 | 71 / 455 |
| stopped: inside the centre's / inside the other sentence / cap / never | 51 / 135 / 0 / 106 | 51 / 64 / 0 / 177 | 51 / 77 / 0 / 164 | 51 / 96 / 52 / 93 | 51 / 23 / 74 / 144 | 51 / 27 / 71 / 143 |
| representative strictly stable | 276/292 = 94.5% | 271/292 = 92.8% | 270/292 = 92.4% | 275/292 = 94.1% | 268/292 = 91.7% | 266/292 = 91.0% |
| members strictly stable (all members of all classes) | 128477/131852 = 97.4% | 53863/55561 = 96.9% | 62928/66197 = 95.0% | 95092/97695 = 97.3% | 26594/27547 = 96.5% | 27949/29301 = 95.3% |
| windows with at least one strictly stable member | 291/292 = 99.6% | 291/292 = 99.6% | 292/292 = 100.0% | 290/292 = 99.3% | 281/292 = 96.2% | 282/292 = 96.5% |
| class size median / max | 426 / 2079 | 101 / 1309 | 206 / 1224 | 216 / 2079 | 13.5 / 966 | 20 / 966 |
| arm length L median / max | 4 / 8 | 5 / 9 | 5 / 8 | 4 / 8 | 4 / 8 | 4 / 8 |

### allow against deny: windows whose record differs (the spec / switches fields aside, which differ in every window)

`record` = any other field differs; `seats` = the representative's seats, the members, the size or the class size differ (the placement itself); a window that differs only in `seatless_arms` (the arms denied for lack of evidence) has the same seats and members.

| arm_cap / z_deep | pair windows: record differs | pair windows: seats / members differ | one-sentence (padded) windows: record differs | ... seats / members differ |
|---|---|---|---|---|
| budget / slide | 1/292 = 0.3% | 0/292 = 0.0% | 300/300 = 100.0% | 0/300 = 0.0% |
| budget / order | 1/292 = 0.3% | 0/292 = 0.0% | 300/300 = 100.0% | 0/300 = 0.0% |
| budget / order_window | 1/292 = 0.3% | 0/292 = 0.0% | 300/300 = 100.0% | 0/300 = 0.0% |
| x / slide | 1/292 = 0.3% | 0/292 = 0.0% | 300/300 = 100.0% | 0/300 = 0.0% |
| x / order | 1/292 = 0.3% | 0/292 = 0.0% | 300/300 = 100.0% | 0/300 = 0.0% |
| x / order_window | 1/292 = 0.3% | 0/292 = 0.0% | 300/300 = 100.0% | 0/300 = 0.0% |

("evidence" of a z-arm edge: n > 0 of the rule the edge used: n_z for the innermost edge (depth 1) and, under slide, for every edge; n_x of the pair under order and the one window sentence's order under order_window (n is 0 or 1) for the deeper edges.  A real N<->N+1 edge = a cross edge whose two ends are seats of different sentences.  The z-axis keys of the three z_deep rules are not comparable with one another.)
