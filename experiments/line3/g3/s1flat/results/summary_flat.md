# G3-f -- the sliding-window placements read as FLAT crosses (S1-flat), on bank2 fulllead RUN

fulllead RUN, windows placed with the G3-c3 defaults (centre both growths, arm_cap budget, strict judgement) under z_deep slide / order (the G3-c4 window caches), read order qcount_first, the cap in windows as T7b (fast 4 / standard 10), tier RUN, t9 scorer (the gold is a substring of ONE word of a candidate).  `FLAT` rows: every window that holds a question unit is read as T10 reads a cross (`rep` = the first member of each growth is the start, `all` = every strictly stable member; search budget 512/64 unless the row says; both seats of a shared unit); a candidate = one entry = the word set of the path words + the centre of the adopted states of one window (the per-axis answers of slide_ratios are only labels).  `S1 per-axis` rows are the G3-e2 runs with answer shape path (the best earlier shape).  Gold in a candidate = some candidate has the gold in one of its words; single right / wrong = exactly one candidate (does / does not); list = >= 2.

## intra2 (fulllead, n = 69)

| system | n | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size: entries median / max | words in the list median / max | words per entry median / max | first-gold pos median | windows read median / max | s/question median (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FLAT rep z=slide fast | 69 | 9 (13%) | 3 | 5 | 6 | 11 | 44 | 2.0 / 6 | 12.0 / 32 | 5.0 / 9 | 1.0 | 3.0 / 4 | 1.94 (16.33) |
| FLAT rep z=order fast | 69 | 7 (10%) | 2 | 7 | 5 | 14 | 41 | 3.0 / 8 | 13.0 / 39 | 5.0 / 11 | 1.0 | 3.0 / 4 | 3.18 (14.99) |
| FLAT rep z=slide standard | 69 | 10 (14%) | 0 | 10 | 10 | 18 | 31 | 3.0 / 10 | 15.5 / 50 | 5.0 / 9 | 1.0 | 6.0 / 10 | 4.58 (25.75) |
| FLAT rep z=order standard | 69 | 8 (12%) | 1 | 7 | 7 | 27 | 27 | 4.0 / 16 | 20.0 / 88 | 5.0 / 11 | 1.0 | 6.0 / 10 | 8.65 (28.55) |
| FLAT rep z=slide fast, budget 64/8 | 69 | 0 (0%) | 0 | 5 | 0 | 4 | 60 | 2.0 / 3 | 11.0 / 12 | 4.5 / 7 | - | 3.0 / 4 | 0.54 (2.26) |
| FLAT rep z=slide fast, budget 4096/512 | 69 | 9 (13%) | 3 | 5 | 6 | 17 | 38 | 2.0 / 12 | 12.0 / 96 | 5.0 / 9 | 1.0 | 3.0 / 4 | 2.72 (48.24) |
| FLAT rep z=slide fast, one seat per shared unit | 69 | 8 (12%) | 4 | 7 | 4 | 6 | 48 | 2.5 / 5 | 12.0 / 30 | 5.0 / 9 | 1.0 | 3.0 / 4 | 1.90 (16.45) |
| FLAT rep z=slide fast, evidence window | 69 | 19 (28%) | 5 | 17 | 14 | 15 | 18 | 3.0 / 6 | 16.0 / 36 | 5.0 / 9 | 1.0 | 3.0 / 4 | 1.27 (14.65) |
| FLAT rep z=order fast, evidence window | 69 | 20 (29%) | 1 | 14 | 19 | 17 | 18 | 4.0 / 15 | 19.5 / 102 | 6.0 / 11 | 1.0 | 3.0 / 4 | 2.55 (12.03) |
| FLAT rep z=slide standard, evidence window | 69 | 21 (30%) | 2 | 12 | 19 | 28 | 8 | 4.0 / 11 | 22.0 / 58 | 5.0 / 10 | 1.0 | 6.0 / 10 | 3.51 (20.36) |
| FLAT rep z=order standard, evidence window | 69 | 21 (30%) | 0 | 8 | 21 | 31 | 9 | 5.0 / 24 | 29.0 / 157 | 6.0 / 13 | 1.0 | 6.0 / 10 | 6.63 (36.02) |
| FLAT all z=slide fast (subset) | 40 | 8 (20%) | 0 | 3 | 8 | 6 | 23 | 9.5 / 54 | 48.0 / 261 | 5.0 / 8 | 1.5 | 3.0 / 4 | 97.05 (1209.63) |
| FLAT all z=slide fast, evidence window (subset) | 40 | 20 (50%) | 0 | 2 | 20 | 13 | 5 | 10.0 / 65 | 40.0 / 307 | 5.0 / 9 | 1.0 | 3.0 / 4 | 74.98 (719.27) |
| S1 per-axis z=slide three path | 69 | 1 (1%) | 1 | 3 | 0 | 0 | 65 | - / - | - / - | 3.0 / 3 | 1.0 | 3.0 / 4 | 0.62 (3.18) |
| S1 per-axis z=slide two_if_single_edge path | 69 | 2 (3%) | 2 | 11 | 0 | 20 | 36 | 3.0 / 8 | 3.0 / 8 | 1.0 / 3 | 1.0 | 3.0 / 4 | 0.62 (3.14) |
| S1 per-axis z=order three path | 69 | 1 (1%) | 0 | 4 | 1 | 0 | 64 | 2.0 / 2 | 6.0 / 6 | 3.0 / 3 | 1.0 | 3.0 / 4 | 0.36 (1.80) |
| S1 per-axis z=order two_if_single_edge path | 69 | 1 (1%) | 0 | 4 | 1 | 0 | 64 | 2.0 / 2 | 6.0 / 6 | 3.0 / 3 | 1.0 | 3.0 / 4 | 0.34 (1.72) |
| T10 flat-fast (3 tiers) | 69 | 16 (23%) | 0 | 2 | 16 | 49 | 2 | 26.0 / 141 | 178.0 / 1160 | 7.0 / 25 | 1.0 | - | 165.95 (413.56) |
| T10 flat-fast RUN tier only | 69 | 15 (22%) | 1 | 2 | 14 | 44 | 8 | 17.0 / 101 | 86.0 / 693 | 7.0 / 13 | 1.0 | - | 165.95 (413.56) |
| T10 layers-ssp-fast | 69 | 21 (30%) | 0 | 0 | 21 | 46 | 2 | 28.0 / 146 | 473.0 / 1774 | 7.0 / 298 | 2.0 | - | 294.72 (749.79) |
| T10 flat-standard (3 tiers) | 69 | 19 (28%) | 0 | 1 | 19 | 49 | 0 | 44.5 / 203 | 349.5 / 1497 | 7.0 / 25 | 1.0 | - | 485.69 (1087.67) |
| T10 flat-standard RUN tier only | 69 | 18 (26%) | 1 | 0 | 17 | 44 | 7 | 28.0 / 171 | 182.0 / 1043 | 7.0 / 13 | 1.0 | - | 485.69 (1087.67) |
| T10 layers-ssp-standard | 69 | 27 (39%) | 0 | 0 | 27 | 42 | 0 | 61.0 / 234 | 2070.0 / 5540 | 7.0 / 354 | 3.0 | - | 956.94 (1586.82) |
| B1-mecab | 69 | 47 (68%) | 31 | 18 | 16 | 4 | 0 | 2.0 / 34 | 2.0 / 34 | 1.0 / 1 | 1.0 | - | - (-) |
| B2-mecab | 69 | 57 (83%) | 20 | 2 | 37 | 10 | 0 | 2.0 / 42 | 2.0 / 42 | 1.0 / 1 | 1.0 | - | - (-) |
| B1-bigram | 69 | 38 (55%) | 30 | 29 | 8 | 2 | 0 | 2.0 / 5 | 2.0 / 5 | 1.0 / 1 | 1.0 | - | - (-) |
| B2-bigram | 69 | 54 (78%) | 19 | 2 | 35 | 13 | 0 | 2.0 / 5 | 2.0 / 5 | 1.0 / 1 | 1.0 | - | - (-) |

## unans (fulllead, n = 25): can a user reject what is shown?

| system | n | no candidate (abstained) | list only (rejectable) | single answer (confident wrong) | list size: entries median / max | words in the list median / max | verdicts |
|---|---|---|---|---|---|---|---|
| FLAT rep z=slide fast | 25 | 18 | 2 | 5 | 3.5 / 5 | 16.0 / 20 | AMBIGUOUS 3, ANSWER 5, CHOICE 2, U_NO_FIXED_POINT 8, U_RATIO_DISAGREEMENT 5, U_SECTION_DISAGREEMENT 1, U_UNSTABLE_AXIS_IMPROVABLE 1 |
| FLAT rep z=order fast | 25 | 16 | 3 | 6 | 3.0 / 5 | 12.0 / 55 | AMBIGUOUS 3, ANSWER 6, CHOICE 3, U_NO_FIXED_POINT 10, U_RATIO_DISAGREEMENT 3 |
| FLAT rep z=slide standard | 25 | 16 | 5 | 4 | 2.0 / 5 | 12.0 / 20 | AMBIGUOUS 3, ANSWER 4, CHOICE 5, U_NO_FIXED_POINT 7, U_RATIO_DISAGREEMENT 4, U_SECTION_DISAGREEMENT 1, U_UNSTABLE_AXIS_IMPROVABLE 1 |
| FLAT rep z=order standard | 25 | 13 | 7 | 5 | 4.0 / 5 | 18.0 / 55 | AMBIGUOUS 2, ANSWER 5, CHOICE 7, U_NO_FIXED_POINT 8, U_RATIO_DISAGREEMENT 3 |
| FLAT rep z=slide fast, budget 64/8 | 25 | 22 | 1 | 2 | 3.0 / 3 | 12.0 / 12 | ANSWER 2, CHOICE 1, U_NO_FIXED_POINT 20, U_RATIO_DISAGREEMENT 2 |
| FLAT rep z=slide fast, budget 4096/512 | 25 | 16 | 4 | 5 | 5.5 / 9 | 28.5 / 44 | AMBIGUOUS 6, ANSWER 5, CHOICE 4, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 7, U_SECTION_DISAGREEMENT 1, U_UNSTABLE_AXIS_IMPROVABLE 1 |
| FLAT rep z=slide fast, one seat per shared unit | 25 | 20 | 2 | 3 | 3.0 / 4 | 14.5 / 17 | AMBIGUOUS 3, ANSWER 3, CHOICE 2, U_NO_FIXED_POINT 11, U_RATIO_DISAGREEMENT 4, U_SECTION_DISAGREEMENT 1, U_UNSTABLE_AXIS_IMPROVABLE 1 |
| FLAT rep z=slide fast, evidence window | 25 | 6 | 9 | 10 | 3.0 / 6 | 21.0 / 34 | ANSWER 10, CHOICE 9, U_NO_FIXED_POINT 3, U_RATIO_DISAGREEMENT 2, U_UNSTABLE_AXIS_IMPROVABLE 1 |
| FLAT rep z=order fast, evidence window | 25 | 3 | 14 | 8 | 3.5 / 8 | 23.5 / 48 | AMBIGUOUS 1, ANSWER 8, CHOICE 14, U_NO_FIXED_POINT 2 |
| FLAT rep z=slide standard, evidence window | 25 | 4 | 12 | 9 | 3.0 / 11 | 21.0 / 61 | ANSWER 9, CHOICE 12, U_NO_FIXED_POINT 2, U_RATIO_DISAGREEMENT 1, U_UNSTABLE_AXIS_IMPROVABLE 1 |
| FLAT rep z=order standard, evidence window | 25 | 3 | 16 | 6 | 4.5 / 13 | 28.5 / 67 | AMBIGUOUS 1, ANSWER 6, CHOICE 16, U_NO_FIXED_POINT 2 |
| FLAT all z=slide fast (subset) | 17 | 8 | 5 | 4 | 5.0 / 6 | 20.0 / 40 | AMBIGUOUS 2, ANSWER 4, CHOICE 5, U_NO_FIXED_POINT 4, U_RATIO_DISAGREEMENT 2 |
| FLAT all z=slide fast, evidence window (subset) | 17 | 2 | 11 | 4 | 8.0 / 58 | 40.0 / 405 | ANSWER 4, CHOICE 11, U_NO_FIXED_POINT 1, U_UNSTABLE_AXIS_IMPROVABLE 1 |
| S1 per-axis z=slide three path | 25 | 25 | 0 | 0 | - / - | - / - | U_RATIO_DISAGREEMENT 22, U_SECTION_DISAGREEMENT 3 |
| S1 per-axis z=slide two_if_single_edge path | 25 | 8 | 9 | 8 | 5.0 / 9 | 5.0 / 9 | ANSWER 8, CHOICE 9, U_RATIO_DISAGREEMENT 7, U_SECTION_DISAGREEMENT 1 |
| S1 per-axis z=order three path | 25 | 25 | 0 | 0 | - / - | - / - | U_RATIO_DISAGREEMENT 19, U_SECTION_DISAGREEMENT 6 |
| S1 per-axis z=order two_if_single_edge path | 25 | 25 | 0 | 0 | - / - | - / - | U_RATIO_DISAGREEMENT 19, U_SECTION_DISAGREEMENT 6 |
| T10 flat-fast (3 tiers) | 25 | 1 | 23 | 1 | 37.0 / 258 | 235.0 / 2111 | - |
| T10 flat-fast RUN tier only | 25 | 5 | 20 | 0 | 29.0 / 198 | 171.5 / 990 | - |
| T10 layers-ssp-fast | 25 | 0 | 24 | 1 | 37.5 / 264 | 492.5 / 2319 | - |
| T10 flat-standard (3 tiers) | 25 | 0 | 25 | 0 | 52.0 / 330 | 343.0 / 2184 | - |
| T10 flat-standard RUN tier only | 25 | 4 | 21 | 0 | 38.0 / 198 | 198.0 / 1022 | - |
| T10 layers-ssp-standard | 25 | 0 | 25 | 0 | 63.0 / 340 | 2367.0 / 5560 | - |
| B1-mecab | 25 | 0 | 13 | 12 | 3.0 / 52 | 3.0 / 52 | - |
| B2-mecab | 25 | 0 | 24 | 1 | 2.5 / 68 | 2.5 / 68 | - |
| B1-bigram | 25 | 0 | 6 | 19 | 2.5 / 54 | 2.5 / 54 | - |
| B2-bigram | 25 | 0 | 23 | 2 | 2.0 / 78 | 2.0 / 78 | - |

## members=all against the representative, on the questions members=all was run for (z slide, fast; 57 of the 94 questions: the ones whose windows read at fast hold <= 700 starts together, results/all_subset_ids.txt; 57 of them finished)

| system | intra2 n | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | entries in the lists (sum) | unans n | abstained | list | single wrong |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FLAT rep z=slide fast | 40 | 5 (12%) | 1 | 3 | 4 | 2 | 30 | 18 | 17 | 14 | 1 | 2 |
| FLAT all z=slide fast (subset) | 40 | 8 (20%) | 0 | 3 | 8 | 6 | 23 | 243 | 17 | 8 | 5 | 4 |
| FLAT rep z=slide fast, evidence window | 40 | 13 (32%) | 4 | 7 | 9 | 5 | 15 | 42 | 17 | 5 | 4 | 8 |
| FLAT all z=slide fast, evidence window (subset) | 40 | 20 (50%) | 0 | 2 | 20 | 13 | 5 | 489 | 17 | 2 | 11 | 4 |
| S1 per-axis z=slide two_if_single_edge path | 40 | 2 (5%) | 2 | 5 | 0 | 7 | 26 | 31 | 17 | 8 | 4 | 5 |
| T10 flat-fast RUN tier only | 40 | 11 (28%) | 1 | 1 | 10 | 21 | 7 | 773 | 17 | 5 | 12 | 0 |
| T10 flat-fast (3 tiers) | 40 | 11 (28%) | 0 | 1 | 11 | 26 | 2 | 1334 | 17 | 1 | 15 | 1 |
| T10 layers-ssp-fast | 40 | 12 (30%) | 0 | 0 | 12 | 26 | 2 | 1436 | 17 | 0 | 16 | 1 |
| B1-mecab | 40 | 24 (60%) | 13 | 13 | 11 | 3 | 0 | 70 | 17 | 0 | 8 | 9 |
| B2-mecab | 40 | 32 (80%) | 11 | 2 | 21 | 6 | 0 | 96 | 17 | 0 | 17 | 0 |

## Where the flat questions end (FLAT rows; both kinds): the verdicts of the answerable questions, and the outcome of every start settled (summed over the windows read)

| system | verdicts (intra2) | questions with an entry | partial questions | questions that read nothing | windows read: 0 / 1-3 / 4+ | starts settled (windows read, summed) | candidate | none:ratio_disagreement | none:section_disagreement | none:points_nowhere | none:ungrounded | ambiguous | no_fixed_point | unstable_axis_improvable | no_question_unit |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| FLAT rep z=slide fast | AMBIGUOUS 7, ANSWER 8, CHOICE 17, U_NOT_READ 2, U_NO_EVIDENCE 2, U_NO_FIXED_POINT 24, U_RATIO_DISAGREEMENT 6, U_SECTION_DISAGREEMENT 2, U_UNSTABLE_AXIS_IMPROVABLE 1 | 25 | 44 | 2 | 2 / 39 / 28 | 310 | 50 | 56 | 17 | 12 | 33 | 23 | 109 | 2860 | 27 |
| FLAT rep z=order fast | AMBIGUOUS 8, ANSWER 9, CHOICE 19, U_NOT_READ 3, U_NO_FIXED_POINT 23, U_RATIO_DISAGREEMENT 7 | 28 | 44 | 3 | 3 / 38 / 28 | 380 | 63 | 80 | 14 | 17 | 11 | 25 | 159 | 516 | 20 |
| FLAT rep z=slide standard | AMBIGUOUS 11, ANSWER 10, CHOICE 28, U_NO_EVIDENCE 2, U_NO_FIXED_POINT 12, U_RATIO_DISAGREEMENT 4, U_SECTION_DISAGREEMENT 1, U_UNSTABLE_AXIS_IMPROVABLE 1 | 38 | 14 | 0 | 0 / 18 / 51 | 599 | 104 | 108 | 29 | 50 | 41 | 47 | 200 | 6188 | 68 |
| FLAT rep z=order standard | AMBIGUOUS 11, ANSWER 8, CHOICE 34, U_NO_FIXED_POINT 11, U_RATIO_DISAGREEMENT 5 | 42 | 16 | 0 | 0 / 16 / 53 | 764 | 138 | 146 | 27 | 62 | 16 | 48 | 309 | 2043 | 50 |
| FLAT rep z=slide fast, budget 64/8 | AMBIGUOUS 4, ANSWER 5, CHOICE 4, U_NOT_READ 2, U_NO_EVIDENCE 2, U_NO_FIXED_POINT 51, U_RATIO_DISAGREEMENT 1 | 9 | 44 | 2 | 2 / 39 / 28 | 310 | 13 | 28 | 9 | 7 | 5 | 4 | 244 | 2860 | 27 |
| FLAT rep z=slide fast, budget 4096/512 | AMBIGUOUS 14, ANSWER 8, CHOICE 23, U_NOT_READ 2, U_NO_EVIDENCE 2, U_NO_FIXED_POINT 6, U_RATIO_DISAGREEMENT 10, U_SECTION_DISAGREEMENT 3, U_UNSTABLE_AXIS_IMPROVABLE 1 | 31 | 44 | 2 | 2 / 39 / 28 | 310 | 66 | 75 | 18 | 12 | 37 | 56 | 28 | 2860 | 27 |
| FLAT rep z=slide fast, one seat per shared unit | AMBIGUOUS 8, ANSWER 11, CHOICE 10, U_NOT_READ 2, U_NO_EVIDENCE 2, U_NO_FIXED_POINT 27, U_RATIO_DISAGREEMENT 6, U_SECTION_DISAGREEMENT 2, U_UNSTABLE_AXIS_IMPROVABLE 1 | 21 | 44 | 2 | 2 / 39 / 28 | 309 | 38 | 59 | 18 | 22 | 31 | 21 | 111 | 2860 | 28 |
| FLAT rep z=slide fast, evidence window | AMBIGUOUS 4, ANSWER 22, CHOICE 29, U_NOT_READ 2, U_NO_EVIDENCE 3, U_NO_FIXED_POINT 6, U_RATIO_DISAGREEMENT 3 | 51 | 44 | 2 | 2 / 39 / 28 | 310 | 117 | 40 | 3 | 20 | 28 | 24 | 77 | 2860 | 27 |
| FLAT rep z=order fast, evidence window | AMBIGUOUS 2, ANSWER 15, CHOICE 36, U_NOT_READ 3, U_NO_EVIDENCE 2, U_NO_FIXED_POINT 9, U_RATIO_DISAGREEMENT 1, U_UNSTABLE_AXIS_IMPROVABLE 1 | 51 | 44 | 3 | 3 / 38 / 28 | 380 | 162 | 37 | 2 | 18 | 15 | 30 | 112 | 516 | 20 |
| FLAT rep z=slide standard, evidence window | AMBIGUOUS 2, ANSWER 14, CHOICE 47, U_NO_EVIDENCE 2, U_NO_FIXED_POINT 3, U_RATIO_DISAGREEMENT 1 | 61 | 14 | 0 | 0 / 18 / 51 | 599 | 214 | 72 | 7 | 49 | 32 | 56 | 153 | 6188 | 68 |
| FLAT rep z=order standard, evidence window | AMBIGUOUS 2, ANSWER 8, CHOICE 52, U_NO_EVIDENCE 2, U_NO_FIXED_POINT 4, U_UNSTABLE_AXIS_IMPROVABLE 1 | 60 | 16 | 0 | 0 / 16 / 53 | 764 | 288 | 78 | 5 | 46 | 23 | 64 | 245 | 2043 | 50 |
| FLAT all z=slide fast (subset) | AMBIGUOUS 7, ANSWER 3, CHOICE 14, U_NOT_READ 2, U_NO_EVIDENCE 2, U_NO_FIXED_POINT 11, U_RATIO_DISAGREEMENT 1 | 17 | 20 | 2 | 2 / 24 / 14 | 17808 | 2037 | 1487 | 1429 | 1080 | 968 | 1894 | 8109 | 1546 | 4342 |
| FLAT all z=slide fast, evidence window (subset) | ANSWER 2, CHOICE 33, U_NOT_READ 2, U_NO_EVIDENCE 2, U_NO_FIXED_POINT 1 | 35 | 20 | 2 | 2 / 24 / 14 | 17808 | 5277 | 1185 | 269 | 1798 | 1090 | 2812 | 5150 | 1546 | 4342 |

## The labels: per entry, how many axes of the placed members agree (slide_ratios, agreement three) -- labels only, nothing is decided by them

| system | entries (intra2 + unans) | entries with >= 1 axis agreed on some member | x agreed | y agreed | z agreed | entries holding the gold | ... of those with >= 1 axis agreed |
|---|---|---|---|---|---|---|---|
| FLAT rep z=slide fast | 69 | 0 | 0 | 0 | 0 | 14 | 0 |
| FLAT rep z=order fast | 88 | 2 | 0 | 0 | 2 | 10 | 1 |
| FLAT rep z=slide standard | 141 | 0 | 0 | 0 | 0 | 19 | 0 |
| FLAT rep z=order standard | 216 | 2 | 0 | 0 | 2 | 15 | 1 |
| FLAT rep z=slide fast, budget 64/8 | 19 | 0 | 0 | 0 | 0 | 0 | 0 |
| FLAT rep z=slide fast, budget 4096/512 | 110 | 0 | 0 | 0 | 0 | 14 | 0 |
| FLAT rep z=slide fast, one seat per shared unit | 48 | 2 | 0 | 0 | 2 | 12 | 1 |
| FLAT rep z=slide fast, evidence window | 147 | 1 | 1 | 0 | 0 | 30 | 0 |
| FLAT rep z=order fast, evidence window | 235 | 3 | 2 | 0 | 1 | 44 | 2 |
| FLAT rep z=slide standard, evidence window | 285 | 1 | 1 | 0 | 0 | 35 | 0 |
| FLAT rep z=order standard, evidence window | 438 | 3 | 2 | 0 | 1 | 48 | 2 |
| FLAT all z=slide fast (subset) | 270 | 30 | 0 | 0 | 30 | 108 | 20 |
| FLAT all z=slide fast, evidence window (subset) | 653 | 24 | 0 | 0 | 24 | 192 | 11 |

## Trace (FLAT rows, windows with an entry): the trace of every path word holds (trace_ok), and how many path words rest on an edge that only a CONSTRUCTED pair sentence evidences (evidence window)

| system | windows with an entry | trace ok | path words with an edge evidenced only by a constructed pair sentence (summed over windows) |
|---|---|---|---|
| FLAT rep z=slide fast | 49 | 49 | 0 |
| FLAT rep z=order fast | 57 | 57 | 0 |
| FLAT rep z=slide standard | 99 | 99 | 0 |
| FLAT rep z=order standard | 119 | 119 | 0 |
| FLAT rep z=slide fast, budget 64/8 | 13 | 13 | 0 |
| FLAT rep z=slide fast, budget 4096/512 | 63 | 63 | 0 |
| FLAT rep z=slide fast, one seat per shared unit | 38 | 38 | 0 |
| FLAT rep z=slide fast, evidence window | 107 | 107 | 3491 |
| FLAT rep z=order fast, evidence window | 127 | 127 | 4487 |
| FLAT rep z=slide standard, evidence window | 195 | 195 | 6803 |
| FLAT rep z=order standard, evidence window | 230 | 230 | 7648 |
| FLAT all z=slide fast (subset) | 42 | 42 | 0 |
| FLAT all z=slide fast, evidence window (subset) | 81 | 81 | 211209 |

## Time (FLAT rows): seconds per question, and the starts per window

| system | questions | s/question median / p90 / max | CPU s total | windows read | starts per window median / max |
|---|---|---|---|---|---|
| FLAT rep z=slide fast | 94 | 1.7 / 6.1 / 16.3 | 249 | 261 | 1.0 / 2 |
| FLAT rep z=order fast | 94 | 3.1 / 7.9 / 15.0 | 357 | 255 | 1.0 / 2 |
| FLAT rep z=slide standard | 94 | 4.2 / 11.9 / 25.8 | 508 | 518 | 1.0 / 2 |
| FLAT rep z=order standard | 94 | 8.1 / 18.5 / 28.6 | 794 | 528 | 1.0 / 2 |
| FLAT rep z=slide fast, budget 64/8 | 94 | 0.5 / 1.5 / 2.3 | 64 | 261 | 1.0 / 2 |
| FLAT rep z=slide fast, budget 4096/512 | 94 | 2.5 / 16.2 / 48.2 | 526 | 261 | 1.0 / 2 |
| FLAT rep z=slide fast, one seat per shared unit | 94 | 1.5 / 5.8 / 16.4 | 240 | 261 | 1.0 / 2 |
| FLAT rep z=slide fast, evidence window | 94 | 1.2 / 5.2 / 14.6 | 203 | 261 | 1.0 / 2 |
| FLAT rep z=order fast, evidence window | 94 | 2.4 / 6.8 / 14.4 | 299 | 255 | 1.0 / 2 |
| FLAT rep z=slide standard, evidence window | 94 | 3.2 / 10.3 / 20.4 | 414 | 518 | 1.0 / 2 |
| FLAT rep z=order standard, evidence window | 94 | 5.9 / 13.9 / 36.0 | 660 | 528 | 1.0 / 2 |
| FLAT all z=slide fast (subset) | 57 | 84.0 / 757.0 / 1488.2 | 12729 | 140 | 33.0 / 660 |
| FLAT all z=slide fast, evidence window (subset) | 57 | 76.8 / 445.1 / 847.6 | 8223 | 140 | 33.0 / 660 |

## Per-question overlap with T10 (review): which of the 69 intra2 golds each side finds (A = the window row, B = the T10 row)

| window row (A) | T10 row (B) | A | B | A only | both | B only | union |
|---|---|---|---|---|---|---|---|
| FLAT rep z=slide fast | T10 flat-fast RUN tier only | 9 | 15 | 5 | 4 | 11 | 20 |
| FLAT rep z=slide fast | T10 flat-fast (3 tiers) | 9 | 16 | 5 | 4 | 12 | 21 |
| FLAT rep z=slide fast | T10 layers-ssp-fast | 9 | 21 | 3 | 6 | 15 | 24 |
| FLAT rep z=slide fast | T10 flat-standard RUN tier only | 9 | 18 | 4 | 5 | 13 | 22 |
| FLAT rep z=slide fast | T10 flat-standard (3 tiers) | 9 | 19 | 4 | 5 | 14 | 23 |
| FLAT rep z=slide fast | T10 layers-ssp-standard | 9 | 27 | 3 | 6 | 21 | 30 |
| FLAT rep z=slide standard | T10 flat-fast RUN tier only | 10 | 15 | 6 | 4 | 11 | 21 |
| FLAT rep z=slide standard | T10 flat-fast (3 tiers) | 10 | 16 | 6 | 4 | 12 | 22 |
| FLAT rep z=slide standard | T10 layers-ssp-fast | 10 | 21 | 4 | 6 | 15 | 25 |
| FLAT rep z=slide standard | T10 flat-standard RUN tier only | 10 | 18 | 5 | 5 | 13 | 23 |
| FLAT rep z=slide standard | T10 flat-standard (3 tiers) | 10 | 19 | 5 | 5 | 14 | 24 |
| FLAT rep z=slide standard | T10 layers-ssp-standard | 10 | 27 | 3 | 7 | 20 | 30 |
| FLAT rep z=slide fast, evidence window | T10 flat-fast RUN tier only | 19 | 15 | 11 | 8 | 7 | 26 |
| FLAT rep z=slide fast, evidence window | T10 flat-fast (3 tiers) | 19 | 16 | 11 | 8 | 8 | 27 |
| FLAT rep z=slide fast, evidence window | T10 layers-ssp-fast | 19 | 21 | 8 | 11 | 10 | 29 |
| FLAT rep z=slide fast, evidence window | T10 flat-standard RUN tier only | 19 | 18 | 9 | 10 | 8 | 27 |
| FLAT rep z=slide fast, evidence window | T10 flat-standard (3 tiers) | 19 | 19 | 9 | 10 | 9 | 28 |
| FLAT rep z=slide fast, evidence window | T10 layers-ssp-standard | 19 | 27 | 6 | 13 | 14 | 33 |
| FLAT rep z=order fast, evidence window | T10 flat-fast RUN tier only | 20 | 15 | 9 | 11 | 4 | 24 |
| FLAT rep z=order fast, evidence window | T10 flat-fast (3 tiers) | 20 | 16 | 9 | 11 | 5 | 25 |
| FLAT rep z=order fast, evidence window | T10 layers-ssp-fast | 20 | 21 | 7 | 13 | 8 | 28 |
| FLAT rep z=order fast, evidence window | T10 flat-standard RUN tier only | 20 | 18 | 8 | 12 | 6 | 26 |
| FLAT rep z=order fast, evidence window | T10 flat-standard (3 tiers) | 20 | 19 | 8 | 12 | 7 | 27 |
| FLAT rep z=order fast, evidence window | T10 layers-ssp-standard | 20 | 27 | 5 | 15 | 12 | 32 |
| FLAT rep z=slide standard, evidence window | T10 flat-fast RUN tier only | 21 | 15 | 13 | 8 | 7 | 28 |
| FLAT rep z=slide standard, evidence window | T10 flat-fast (3 tiers) | 21 | 16 | 13 | 8 | 8 | 29 |
| FLAT rep z=slide standard, evidence window | T10 layers-ssp-fast | 21 | 21 | 10 | 11 | 10 | 31 |
| FLAT rep z=slide standard, evidence window | T10 flat-standard RUN tier only | 21 | 18 | 11 | 10 | 8 | 29 |
| FLAT rep z=slide standard, evidence window | T10 flat-standard (3 tiers) | 21 | 19 | 11 | 10 | 9 | 30 |
| FLAT rep z=slide standard, evidence window | T10 layers-ssp-standard | 21 | 27 | 7 | 14 | 13 | 34 |
| FLAT rep z=order standard, evidence window | T10 flat-fast RUN tier only | 21 | 15 | 10 | 11 | 4 | 25 |
| FLAT rep z=order standard, evidence window | T10 flat-fast (3 tiers) | 21 | 16 | 10 | 11 | 5 | 26 |
| FLAT rep z=order standard, evidence window | T10 layers-ssp-fast | 21 | 21 | 8 | 13 | 8 | 29 |
| FLAT rep z=order standard, evidence window | T10 flat-standard RUN tier only | 21 | 18 | 9 | 12 | 6 | 27 |
| FLAT rep z=order standard, evidence window | T10 flat-standard (3 tiers) | 21 | 19 | 9 | 12 | 7 | 28 |
| FLAT rep z=order standard, evidence window | T10 layers-ssp-standard | 21 | 27 | 5 | 16 | 11 | 32 |

All six window rows together: 28 golds; all six T10 rows together: 28; union 37; found by a window row and by no T10 row: 9 (I2-002 I2-004 I2-006 I2-024 I2-030 I2-042 I2-043 I2-045 R2-I018); found by a T10 row and by no window row: 9.


## Notes (G3-f)

- Code states. Every run's .meta.json records the sha256 of slide_flat.py, slide_query.py (committed G3-e2, 3b17519d...), cycle.py, readout.py, trace_check.py, slide_place.py, slide_ratios.py, slide.py and grammar.py. The runs were made by three states of slide_flat.py that differ in logging only (49790f1cf5fb: all rep runs and the plain members-all run; e4208e4756df: the evidence-window members-all run, which adds the trace field `edge_words`; 3282e2d0eb68: the final file, docstring). Closed by re-running fast z slide rep, evidence plain and window, with the final file (94 questions each): verdict, entries (window, words, centres, arrangements, citations, stability, constructed_edge_words, axis labels) and abstentions are equal for 94 of 94 and 94 of 94. results_pre/ against results/ (equiv_check.py): 1034 of 1034 questions equal.
- The caches are scratch files of the session (scratchpad/cache/slide, order: the G3-e2 sweep's window caches); a missing or mismatching cache is refused or rebuilt with --build (about 4 minutes of one core).
- members all was run on the 57 questions of results/all_subset_ids.txt only (L-715); the first attempt on all 94 questions was stopped after 6 (results_pre/flat_fast_zslide_all_partial6.jsonl).
- Edge evidence (edge_evidence_slide_representative.txt) and the share of the trace that rests on constructed pair sentences (trace_share_slide.txt) are diagnostics of z slide at fast with the representatives.
- Review (2026-10-09). The final slide_flat.py of the implementer (ae42251c3619) reproduced fast z slide rep plain and window for 94 of 94 questions (verdict, entries with labels and citations, abstentions, tallies). The review then fixed verdict_of (cycle's member status `mixed` is typed UNKNOWN_RATIO_DISAGREEMENT, as cycle._verdict_from types "none:mixed") and counts the starts `member_cap` leaves (not used here), giving slide_flat.py 779be502d101, and re-ran the eleven rep rows with it (sweep_flat.sh both, 5 workers; no --resume carry-over): every entry, abstention, tally and citation is unchanged; 13 verdict strings of no-entry questions changed (5 rows; e.g. I2-035 UNKNOWN_NO_EVIDENCE -> UNKNOWN_RATIO_DISAGREEMENT). The two members-all rows keep their earlier shas (49790f1cf5fb / e4208e4756df): none of their verdicts is affected by the fix. results_pre/ now compares against these re-runs.
