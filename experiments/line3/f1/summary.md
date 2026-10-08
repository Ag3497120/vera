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
| RUN | whole | 2033 | 1053 (52%) | 63 | 269 | 648 | 1 / 8 / 13 | 1120 | 913 | 1009 | 253 |
| RUN | ordered | 2033 | 0 (0%) | 23 | 257 | 1753 | 9 / 10 / 20 | 1010 | 1023 | 1968 | 495 |
| RUN | reverse | 2033 | 0 (0%) | 23 | 257 | 1753 | 9 / 10 / 20 | 859 | 1174 | 2585 | 652 |
| WORD | whole | 2278 | 1590 (70%) | 141 | 92 | 455 | 1 / 8 / 35 | 1923 | 355 | 1131 | 284 |
| WORD | ordered | 2278 | 0 (0%) | 4 | 22 | 2252 | 10 / 16 / 59 | 1701 | 577 | 3620 | 910 |
| CHAR | whole | 1094 | 434 (40%) | 84 | 58 | 518 | 5 / 39 / 104 | 1036 | 58 | 640 | 160 |
| CHAR | ordered | 1094 | 0 (0%) | 2 | 2 | 1090 | 31 / 85 / 149 | 786 | 308 | 4436 | 1117 |

Budget stops of the ordered build (members left): median members left in the breaking group / after it, and the reason

| tier | mode | stopped | reasons | left in group median / max | left after median / max | stopped with size 1 (first member alone broke) |
|---|---|---|---|---|---|---|
| RUN | ordered | 1010 | {'max_class': 983, 'max_moves': 27} | 4 / 120 | 0 / 0 | 0 |
| RUN | reverse | 859 | {'max_class': 405, 'max_moves': 454} | 5 / 122 | 0 / 0 | 0 |
| WORD | ordered | 1701 | {'max_class': 1409, 'max_moves': 292} | 7 / 237 | 0 / 627 | 0 |
| CHAR | ordered | 786 | {'max_moves': 634, 'max_class': 152} | 27 / 197 | 0 / 514 | 0 |

Order sensitivity (forward vs reverse): crosses of the SAME size / same unit set / same size but different units

| tier | crosses | same unit set | same size, other units | different size | median |size diff| among differing |
|---|---|---|---|---|---|
| RUN | 2033 | 1019 (50%) | 321 | 693 | 1 |

