## fulllead_sents (level mid)

| tier | mode | crosses | bare seed | size 2-3 | size 4-5 | size 6+ | median / p90 / max size | stop budget | exhausted | CPU s | wall s (4 workers) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| RUN | whole | 3653 | 1946 (53%) | 265 | 451 | 991 | 1 / 8 / 14 | 2169 | 1484 | 1590 | 398 |
| RUN | ordered | 3653 | 5 (0%) | 102 | 410 | 3136 | 9 / 13 / 27 | 1914 | 1739 | 3281 | 823 |
| RUN | reverse | 3653 | 5 (0%) | 102 | 410 | 3136 | 9 / 13 / 26 | 1772 | 1881 | 4830 | 1213 |
| WORD | whole | 3557 | 2187 (61%) | 318 | 235 | 817 | 1 / 9 / 37 | 2895 | 662 | 1519 | 381 |
| WORD | ordered | 3557 | 1 (0%) | 22 | 71 | 3463 | 12 / 19 / 67 | 2418 | 1139 | 4662 | 1169 |
| WORD | reverse | 3557 | 1 (0%) | 22 | 71 | 3463 | 13 / 19 / 64 | 2302 | 1255 | 5507 | 1383 |
| CHAR | whole | 1358 | 402 (30%) | 110 | 82 | 764 | 7.5 / 50 / 115 | 1287 | 71 | 953 | 238 |
| CHAR | ordered | 1358 | 0 (0%) | 0 | 4 | 1354 | 38 / 104 / 182 | 989 | 369 | 6582 | 1654 |
| CHAR | reverse | 1358 | 0 (0%) | 0 | 4 | 1354 | 37 / 104 / 176 | 994 | 364 | 6430 | 1611 |

Budget stops of the ordered build (members left): median members left in the breaking group / after it, and the reason

| tier | mode | stopped | reasons | left in group median / max | left after median / max | stopped with size 1 (first member alone broke) |
|---|---|---|---|---|---|---|
| RUN | ordered | 1914 | {'max_class': 1792, 'max_moves': 122} | 5 / 316 | 0 / 0 | 0 |
| RUN | reverse | 1772 | {'max_class': 905, 'max_moves': 867} | 5 / 314 | 0 / 0 | 0 |
| WORD | ordered | 2418 | {'max_class': 1953, 'max_moves': 465} | 9 / 381 | 0 / 715 | 0 |
| WORD | reverse | 2302 | {'max_moves': 950, 'max_class': 1352} | 10 / 237 | 0 / 715 | 0 |
| CHAR | ordered | 989 | {'max_moves': 841, 'max_class': 148} | 33 / 233 | 0 / 710 | 0 |
| CHAR | reverse | 994 | {'max_moves': 846, 'max_class': 148} | 34 / 237 | 0 / 710 | 0 |

Order sensitivity (forward vs reverse): crosses of the SAME size / same unit set / same size but different units

| tier | crosses | same unit set | same size, other units | different size | median |size diff| among differing |
|---|---|---|---|---|---|
| RUN | 3653 | 1702 (47%) | 536 | 1415 | 1 |
| WORD | 3557 | 1054 (30%) | 584 | 1919 | 3 |
| CHAR | 1358 | 311 (23%) | 46 | 1001 | 11 |

## S300 (level mid)

| tier | mode | crosses | bare seed | size 2-3 | size 4-5 | size 6+ | median / p90 / max size | stop budget | exhausted | CPU s | wall s (4 workers) |
|---|---|---|---|---|---|---|---|---|---|---|---|

Budget stops of the ordered build (members left): median members left in the breaking group / after it, and the reason

| tier | mode | stopped | reasons | left in group median / max | left after median / max | stopped with size 1 (first member alone broke) |
|---|---|---|---|---|---|---|

Order sensitivity (forward vs reverse): crosses of the SAME size / same unit set / same size but different units

| tier | crosses | same unit set | same size, other units | different size | median |size diff| among differing |
|---|---|---|---|---|---|

