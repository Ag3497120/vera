# G3-e2 -- the answer shape (end unit | walked path), the read order (more question units first | grammar first) and z_deep, on S1 fast

fulllead RUN, windows placed with the G3-c3 defaults (centre both growths, arm_cap budget, strict judgement) under z_deep slide / order (the G3-c4 window caches), fast = 4 windows read per question, tier RUN, t9 scorer (the gold is a substring of ONE word of a candidate).  A candidate = one entry (window, axis, agreed unit [, path under shape path]); `words` of an entry = the end unit (unit) or the units of the walked path (path).  Gold in a candidate = some candidate has the gold in one of its words; single right / wrong = exactly one candidate (does / does not); list = >= 2.  `E2` rows are this ticket; `ref` rows are earlier runs (old read order, unit shape).

## intra2 (fulllead, n = 69)

| system | n | gold in a candidate | via x / z | gold in the END unit / only in path words | single right | single wrong | list with gold | list without gold | no candidate | list size: entries median / max | words in the list median / max | words per entry median / max | first-gold pos median | windows read median / max | s/question median (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E2 z=slide three unit | 69 | 0 (0%) | 0 / 0 | 0 / 0 | 0 | 4 | 0 | 0 | 65 | - / - | - / - | 1.0 / 1 | - | 3.0 / 4 | 0.66 (3.33) |
| E2 z=slide three path | 69 | 1 (1%) | 1 / 0 | 0 / 1 | 1 | 3 | 0 | 0 | 65 | - / - | - / - | 3.0 / 3 | 1.0 | 3.0 / 4 | 0.62 (3.18) |
| E2 z=slide two_if_single_edge unit | 69 | 1 (1%) | 0 / 1 | 1 / 0 | 1 | 12 | 0 | 20 | 36 | 3.0 / 8 | 3.0 / 8 | 1.0 / 1 | 1.0 | 3.0 / 4 | 0.62 (3.16) |
| E2 z=slide two_if_single_edge path | 69 | 2 (3%) | 1 / 1 | 1 / 1 | 2 | 11 | 0 | 20 | 36 | 3.0 / 8 | 3.0 / 8 | 1.0 / 3 | 1.0 | 3.0 / 4 | 0.62 (3.14) |
| E2 z=order three unit | 69 | 0 (0%) | 0 / 0 | 0 / 0 | 0 | 4 | 0 | 1 | 64 | 2.0 / 2 | 2.0 / 2 | 1.0 / 1 | - | 3.0 / 4 | 0.35 (1.72) |
| E2 z=order three path | 69 | 1 (1%) | 1 / 0 | 0 / 1 | 0 | 4 | 1 | 0 | 64 | 2.0 / 2 | 6.0 / 6 | 3.0 / 3 | 1.0 | 3.0 / 4 | 0.36 (1.80) |
| E2 z=order two_if_single_edge unit | 69 | 0 (0%) | 0 / 0 | 0 / 0 | 0 | 4 | 0 | 1 | 64 | 2.0 / 2 | 2.0 / 2 | 1.0 / 1 | - | 3.0 / 4 | 0.34 (1.69) |
| E2 z=order two_if_single_edge path | 69 | 1 (1%) | 1 / 0 | 0 / 1 | 0 | 4 | 1 | 0 | 64 | 2.0 / 2 | 6.0 / 6 | 3.0 / 3 | 1.0 | 3.0 / 4 | 0.34 (1.72) |
| E2 z=slide three path, OLD read order | 69 | 1 (1%) | 1 / 0 | 0 / 1 | 1 | 5 | 0 | 0 | 63 | - / - | - / - | 3.0 / 4 | 1.0 | 3.0 / 4 | 0.62 (3.15) |
| ref c2 (S1, G3-c2 placements, old order) three | 69 | 0 (0%) | 0 / 0 | 0 / 0 | 0 | 2 | 0 | 0 | 67 | - / - | - / - | 1.0 / 1 | - | 4.0 / 4 | 0.57 (1.93) |
| ref c2 (S1, G3-c2 placements, old order) two_if_single_edge | 69 | 0 (0%) | 0 / 0 | 0 / 0 | 0 | 16 | 0 | 25 | 28 | 4.0 / 10 | 4.0 / 10 | 1.0 / 1 | - | 4.0 / 4 | 0.54 (1.85) |
| ref c4 (G3-c3 placements, old order, unit) z=slide three | 69 | 0 (0%) | 0 / 0 | 0 / 0 | 0 | 6 | 0 | 0 | 63 | - / - | - / - | 1.0 / 1 | - | 3.0 / 4 | 0.61 (3.22) |
| ref c4 (G3-c3 placements, old order, unit) z=slide two_if_single_edge | 69 | 0 (0%) | 0 / 0 | 0 / 0 | 0 | 14 | 0 | 20 | 35 | 2.5 / 6 | 2.5 / 6 | 1.0 / 1 | - | 3.0 / 4 | 0.59 (3.15) |
| ref c4 (G3-c3 placements, old order, unit) z=order three | 69 | 0 (0%) | 0 / 0 | 0 / 0 | 0 | 3 | 0 | 1 | 65 | 2.0 / 2 | 2.0 / 2 | 1.0 / 1 | - | 3.0 / 4 | 0.29 (2.03) |
| ref c4 (G3-c3 placements, old order, unit) z=order two_if_single_edge | 69 | 0 (0%) | 0 / 0 | 0 / 0 | 0 | 3 | 0 | 1 | 65 | 2.0 / 2 | 2.0 / 2 | 1.0 / 1 | - | 3.0 / 4 | 0.32 (2.03) |
| T10 flat-fast (3 tiers) | 69 | 16 (23%) | - | - | 0 | 2 | 16 | 49 | 2 | 26.0 / 141 | 178.0 / 1160 | 7.0 / 25 | 1.0 | - | 165.95 (413.56) |
| T10 flat-fast RUN tier only | 69 | 15 (22%) | - | - | 1 | 2 | 14 | 44 | 8 | 17.0 / 101 | 86.0 / 693 | 7.0 / 13 | 1.0 | - | 165.95 (413.56) |
| T10 layers-ssp-fast | 69 | 21 (30%) | - | - | 0 | 0 | 21 | 46 | 2 | 28.0 / 146 | 473.0 / 1774 | 7.0 / 298 | 2.0 | - | 294.72 (749.79) |
| B1-mecab | 69 | 47 (68%) | - | - | 31 | 18 | 16 | 4 | 0 | 2.0 / 34 | 2.0 / 34 | 1.0 / 1 | 1.0 | - | - (-) |
| B2-mecab | 69 | 57 (83%) | - | - | 20 | 2 | 37 | 10 | 0 | 2.0 / 42 | 2.0 / 42 | 1.0 / 1 | 1.0 | - | - (-) |
| B1-bigram | 69 | 38 (55%) | - | - | 30 | 29 | 8 | 2 | 0 | 2.0 / 5 | 2.0 / 5 | 1.0 / 1 | 1.0 | - | - (-) |
| B2-bigram | 69 | 54 (78%) | - | - | 19 | 2 | 35 | 13 | 0 | 2.0 / 5 | 2.0 / 5 | 1.0 / 1 | 1.0 | - | - (-) |

## unans (fulllead, n = 25): can a user reject what is shown?

| system | n | no candidate (abstained) | list only (rejectable) | single answer (confident wrong) | list size: entries median / max | words in the list median / max | verdicts |
|---|---|---|---|---|---|---|---|
| E2 z=slide three unit | 25 | 25 | 0 | 0 | - / - | - / - | U_RATIO_DISAGREEMENT 22, U_SECTION_DISAGREEMENT 3 |
| E2 z=slide three path | 25 | 25 | 0 | 0 | - / - | - / - | U_RATIO_DISAGREEMENT 22, U_SECTION_DISAGREEMENT 3 |
| E2 z=slide two_if_single_edge unit | 25 | 8 | 9 | 8 | 5.0 / 9 | 5.0 / 9 | ANSWER 8, CHOICE 9, U_RATIO_DISAGREEMENT 7, U_SECTION_DISAGREEMENT 1 |
| E2 z=slide two_if_single_edge path | 25 | 8 | 9 | 8 | 5.0 / 9 | 5.0 / 9 | ANSWER 8, CHOICE 9, U_RATIO_DISAGREEMENT 7, U_SECTION_DISAGREEMENT 1 |
| E2 z=order three unit | 25 | 25 | 0 | 0 | - / - | - / - | U_RATIO_DISAGREEMENT 19, U_SECTION_DISAGREEMENT 6 |
| E2 z=order three path | 25 | 25 | 0 | 0 | - / - | - / - | U_RATIO_DISAGREEMENT 19, U_SECTION_DISAGREEMENT 6 |
| E2 z=order two_if_single_edge unit | 25 | 25 | 0 | 0 | - / - | - / - | U_RATIO_DISAGREEMENT 19, U_SECTION_DISAGREEMENT 6 |
| E2 z=order two_if_single_edge path | 25 | 25 | 0 | 0 | - / - | - / - | U_RATIO_DISAGREEMENT 19, U_SECTION_DISAGREEMENT 6 |
| E2 z=slide three path, OLD read order | 25 | 25 | 0 | 0 | - / - | - / - | U_NOT_READ 1, U_RATIO_DISAGREEMENT 21, U_SECTION_DISAGREEMENT 3 |
| ref c2 (S1, G3-c2 placements, old order) three | 25 | 25 | 0 | 0 | - / - | - / - | U_NOT_READ 1, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 21, U_SECTION_DISAGREEMENT 2 |
| ref c2 (S1, G3-c2 placements, old order) two_if_single_edge | 25 | 10 | 8 | 7 | 3.5 / 7 | 3.5 / 7 | ANSWER 7, CHOICE 8, U_NOT_READ 1, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 8 |
| ref c4 (G3-c3 placements, old order, unit) z=slide three | 25 | 25 | 0 | 0 | - / - | - / - | U_NOT_READ 1, U_RATIO_DISAGREEMENT 21, U_SECTION_DISAGREEMENT 3 |
| ref c4 (G3-c3 placements, old order, unit) z=slide two_if_single_edge | 25 | 10 | 6 | 9 | 5.5 / 9 | 5.5 / 9 | ANSWER 9, CHOICE 6, U_NOT_READ 1, U_RATIO_DISAGREEMENT 8, U_SECTION_DISAGREEMENT 1 |
| ref c4 (G3-c3 placements, old order, unit) z=order three | 25 | 25 | 0 | 0 | - / - | - / - | U_NOT_READ 2, U_RATIO_DISAGREEMENT 16, U_SECTION_DISAGREEMENT 7 |
| ref c4 (G3-c3 placements, old order, unit) z=order two_if_single_edge | 25 | 25 | 0 | 0 | - / - | - / - | U_NOT_READ 2, U_RATIO_DISAGREEMENT 16, U_SECTION_DISAGREEMENT 7 |
| T10 flat-fast (3 tiers) | 25 | 1 | 23 | 1 | 37.0 / 258 | 235.0 / 2111 | - |
| T10 flat-fast RUN tier only | 25 | 5 | 20 | 0 | 29.0 / 198 | 171.5 / 990 | - |
| T10 layers-ssp-fast | 25 | 0 | 24 | 1 | 37.5 / 264 | 492.5 / 2319 | - |
| B1-mecab | 25 | 0 | 13 | 12 | 3.0 / 52 | 3.0 / 52 | - |
| B2-mecab | 25 | 0 | 24 | 1 | 2.5 / 68 | 2.5 / 68 | - |
| B1-bigram | 25 | 0 | 6 | 19 | 2.5 / 54 | 2.5 / 54 | - |
| B2-bigram | 25 | 0 | 23 | 2 | 2.0 / 78 | 2.0 / 78 | - |

## Entries and where the questions end (slide systems; both kinds): entries x / z, words in them, typed abstentions summed over (window, axis)

| system | kind | n | entries x / z | words in entries (distinct) | entries with > 1 word | points_nowhere | section_disagreement | ratio_disagreement | no_edges | not_grounded | unstable_axis_improvable | no_question_unit | mixed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| E2 z=slide three unit | intra2 | 69 | 2 / 2 | 4 (4) | 0 | 45 | 67 | 25 | 215 | 0 | 0 | 0 | 244 |
| E2 z=slide three unit | unans | 25 | 0 / 0 | 0 (0) | 0 | 22 | 17 | 11 | 65 | 0 | 0 | 0 | 68 |
| E2 z=slide three path | intra2 | 69 | 2 / 2 | 12 (12) | 4 | 45 | 67 | 25 | 215 | 0 | 0 | 0 | 244 |
| E2 z=slide three path | unans | 25 | 0 / 0 | 0 (0) | 0 | 22 | 17 | 11 | 65 | 0 | 0 | 0 | 68 |
| E2 z=slide two_if_single_edge unit | intra2 | 69 | 2 / 86 | 88 (88) | 0 | 47 | 61 | 33 | 215 | 0 | 0 | 0 | 200 |
| E2 z=slide two_if_single_edge unit | unans | 25 | 0 / 52 | 52 (52) | 0 | 22 | 14 | 11 | 65 | 0 | 0 | 0 | 47 |
| E2 z=slide two_if_single_edge path | intra2 | 69 | 2 / 86 | 96 (96) | 4 | 47 | 61 | 33 | 215 | 0 | 0 | 0 | 200 |
| E2 z=slide two_if_single_edge path | unans | 25 | 0 / 52 | 52 (52) | 0 | 22 | 14 | 11 | 65 | 0 | 0 | 0 | 47 |
| E2 z=order three unit | intra2 | 69 | 3 / 3 | 6 (5) | 0 | 54 | 40 | 12 | 201 | 0 | 0 | 0 | 269 |
| E2 z=order three unit | unans | 25 | 0 / 0 | 0 (0) | 0 | 21 | 9 | 7 | 66 | 0 | 0 | 0 | 80 |
| E2 z=order three path | intra2 | 69 | 3 / 3 | 17 (14) | 6 | 54 | 40 | 12 | 201 | 0 | 0 | 0 | 269 |
| E2 z=order three path | unans | 25 | 0 / 0 | 0 (0) | 0 | 21 | 9 | 7 | 66 | 0 | 0 | 0 | 80 |
| E2 z=order two_if_single_edge unit | intra2 | 69 | 3 / 3 | 6 (5) | 0 | 54 | 40 | 12 | 201 | 0 | 0 | 0 | 269 |
| E2 z=order two_if_single_edge unit | unans | 25 | 0 / 0 | 0 (0) | 0 | 21 | 9 | 7 | 66 | 0 | 0 | 0 | 80 |
| E2 z=order two_if_single_edge path | intra2 | 69 | 3 / 3 | 17 (14) | 6 | 54 | 40 | 12 | 201 | 0 | 0 | 0 | 269 |
| E2 z=order two_if_single_edge path | unans | 25 | 0 / 0 | 0 (0) | 0 | 21 | 9 | 7 | 66 | 0 | 0 | 0 | 80 |
| E2 z=slide three path, OLD read order | intra2 | 69 | 2 / 4 | 20 (20) | 6 | 39 | 59 | 27 | 218 | 0 | 0 | 0 | 233 |
| E2 z=slide three path, OLD read order | unans | 25 | 0 / 0 | 0 (0) | 0 | 22 | 16 | 11 | 74 | 0 | 0 | 0 | 72 |
| ref c2 (S1, G3-c2 placements, old order) three | intra2 | 69 | 2 / 0 | 2 (2) | 0 | 91 | 134 | 28 | 294 | 0 | 0 | 0 | 102 |
| ref c2 (S1, G3-c2 placements, old order) three | unans | 25 | 0 / 0 | 0 (0) | 0 | 33 | 27 | 14 | 92 | 0 | 0 | 0 | 32 |
| ref c2 (S1, G3-c2 placements, old order) two_if_single_edge | intra2 | 69 | 2 / 128 | 130 (129) | 0 | 90 | 97 | 38 | 294 | 0 | 0 | 0 | 71 |
| ref c2 (S1, G3-c2 placements, old order) two_if_single_edge | unans | 25 | 0 / 36 | 36 (35) | 0 | 33 | 17 | 16 | 92 | 0 | 0 | 0 | 18 |
| ref c4 (G3-c3 placements, old order, unit) z=slide three | intra2 | 69 | 2 / 4 | 6 (6) | 0 | 39 | 59 | 27 | 218 | 0 | 0 | 0 | 233 |
| ref c4 (G3-c3 placements, old order, unit) z=slide three | unans | 25 | 0 / 0 | 0 (0) | 0 | 22 | 16 | 11 | 74 | 0 | 0 | 0 | 72 |
| ref c4 (G3-c3 placements, old order, unit) z=slide two_if_single_edge | intra2 | 69 | 2 / 69 | 71 (71) | 0 | 40 | 55 | 33 | 218 | 0 | 0 | 0 | 194 |
| ref c4 (G3-c3 placements, old order, unit) z=slide two_if_single_edge | unans | 25 | 0 / 42 | 42 (42) | 0 | 22 | 13 | 12 | 74 | 0 | 0 | 0 | 53 |
| ref c4 (G3-c3 placements, old order, unit) z=order three | intra2 | 69 | 3 / 2 | 5 (4) | 0 | 43 | 40 | 12 | 199 | 0 | 0 | 0 | 262 |
| ref c4 (G3-c3 placements, old order, unit) z=order three | unans | 25 | 0 / 0 | 0 (0) | 0 | 22 | 10 | 7 | 69 | 0 | 0 | 0 | 75 |
| ref c4 (G3-c3 placements, old order, unit) z=order two_if_single_edge | intra2 | 69 | 3 / 2 | 5 (4) | 0 | 43 | 40 | 12 | 199 | 0 | 0 | 0 | 262 |
| ref c4 (G3-c3 placements, old order, unit) z=order two_if_single_edge | unans | 25 | 0 / 0 | 0 (0) | 0 | 22 | 10 | 7 | 69 | 0 | 0 | 0 | 75 |

## Verdicts of the answerable questions and the reading cap (slide systems)

| system | verdicts (intra2) | partial questions | questions that read nothing (first block larger than the cap) | windows read: 0 / 1-3 / 4 |
|---|---|---|---|---|
| E2 z=slide three unit | ANSWER 4, U_NOT_READ 2, U_RATIO_DISAGREEMENT 48, U_SECTION_DISAGREEMENT 15 | 44 | 2 | 2 / 39 / 28 |
| E2 z=slide three path | ANSWER 4, U_NOT_READ 2, U_RATIO_DISAGREEMENT 48, U_SECTION_DISAGREEMENT 15 | 44 | 2 | 2 / 39 / 28 |
| E2 z=slide two_if_single_edge unit | ANSWER 13, CHOICE 20, U_NOT_READ 2, U_RATIO_DISAGREEMENT 31, U_SECTION_DISAGREEMENT 3 | 44 | 2 | 2 / 39 / 28 |
| E2 z=slide two_if_single_edge path | ANSWER 13, CHOICE 20, U_NOT_READ 2, U_RATIO_DISAGREEMENT 31, U_SECTION_DISAGREEMENT 3 | 44 | 2 | 2 / 39 / 28 |
| E2 z=order three unit | ANSWER 4, CHOICE 1, U_NOT_READ 3, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 49, U_SECTION_DISAGREEMENT 11 | 44 | 3 | 3 / 38 / 28 |
| E2 z=order three path | ANSWER 4, CHOICE 1, U_NOT_READ 3, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 49, U_SECTION_DISAGREEMENT 11 | 44 | 3 | 3 / 38 / 28 |
| E2 z=order two_if_single_edge unit | ANSWER 4, CHOICE 1, U_NOT_READ 3, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 49, U_SECTION_DISAGREEMENT 11 | 44 | 3 | 3 / 38 / 28 |
| E2 z=order two_if_single_edge path | ANSWER 4, CHOICE 1, U_NOT_READ 3, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 49, U_SECTION_DISAGREEMENT 11 | 44 | 3 | 3 / 38 / 28 |
| E2 z=slide three path, OLD read order | ANSWER 6, U_NOT_READ 8, U_RATIO_DISAGREEMENT 45, U_SECTION_DISAGREEMENT 10 | 44 | 8 | 8 / 30 / 31 |
| ref c2 (S1, G3-c2 placements, old order) three | ANSWER 2, U_NOT_READ 3, U_RATIO_DISAGREEMENT 56, U_SECTION_DISAGREEMENT 8 | 44 | 3 | 3 / 27 / 39 |
| ref c2 (S1, G3-c2 placements, old order) two_if_single_edge | ANSWER 16, CHOICE 25, U_NOT_READ 3, U_RATIO_DISAGREEMENT 24, U_SECTION_DISAGREEMENT 1 | 44 | 3 | 3 / 27 / 39 |
| ref c4 (G3-c3 placements, old order, unit) z=slide three | ANSWER 6, U_NOT_READ 8, U_RATIO_DISAGREEMENT 45, U_SECTION_DISAGREEMENT 10 | 44 | 8 | 8 / 30 / 31 |
| ref c4 (G3-c3 placements, old order, unit) z=slide two_if_single_edge | ANSWER 14, CHOICE 20, U_NOT_READ 8, U_RATIO_DISAGREEMENT 27 | 44 | 8 | 8 / 30 / 31 |
| ref c4 (G3-c3 placements, old order, unit) z=order three | ANSWER 3, CHOICE 1, U_NOT_READ 10, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 45, U_SECTION_DISAGREEMENT 9 | 44 | 10 | 10 / 28 / 31 |
| ref c4 (G3-c3 placements, old order, unit) z=order two_if_single_edge | ANSWER 3, CHOICE 1, U_NOT_READ 10, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 45, U_SECTION_DISAGREEMENT 9 | 44 | 10 | 10 / 28 / 31 |

## Reach (window level, intra2): the gold is a seated RUN unit of a window that holds a question unit

`all candidates` = no cap (40 / 69 on the G3-c2 placements); `read at fast` = of the windows the plan actually reads at fast (4 windows, whole blocks), per read order.

| placements | all candidates | read at fast, qcount_first | read at fast, grammar_first | windows read at fast median (qcount_first / grammar_first) | questions that read nothing (qcount_first / grammar_first) |
|---|---|---|---|---|---|
| z_deep slide | 40 / 69 | 37 / 69 | 27 / 69 | 3.0 / 3.0 | 2 / 8 |
| z_deep order | 41 / 69 | 38 / 69 | 27 / 69 | 3.0 / 3.0 | 3 / 10 |

## What the path shape could reach if the agreement did not decide (path_ceiling.py, intra2, windows read at fast, every readable member, agreement three's walks)

| placements | read order | questions | gold seated in a read window | gold = END unit of some walk | gold in the PATH of some walk | gold in the path of a WORKING section's walk | gold in an agreed entry (e2 run, path, three) |
|---|---|---|---|---|---|---|---|
| z_deep slide | qcount_first | 69 | 37 | 18 | 31 | 31 | 1 |
| z_deep slide | grammar_first | 69 | 27 | 14 | 24 | 24 | - |
| z_deep order | qcount_first | 69 | 38 | 20 | 34 | 34 | 1 |
| z_deep order | grammar_first | 69 | 27 | 11 | 24 | 24 | - |

## What the numbers say (facts; the reading is the owner's)

- Gold in a candidate stays 0-2 of 69 in all nine runs (ref: flat-fast 16, ssp 21, B1 47, B2 57).  Unit shape: 0 / 1 / 0 / 0 (slide three / slide two_if_single_edge / order three / order two_if); path shape: 1 / 2 / 1 / 1; in 4 of the 5 path hits the gold is a path word and not the end unit (the fifth, slide two_if, is also the unit shape's hit).  The old read order with the path shape and slide three: 1.
- The new read order does what it was meant to do, at the level of the windows read: the gold is a seated unit of a window READ at fast in 37 / 69 (slide) and 38 / 69 (order) questions against 27 / 69 under the grammar-first order (no cap: 40 / 41); the questions whose first block is larger than the cap and that read nothing fall from 8 to 2 (slide) and from 10 to 3 (order).  The reach moves; the candidates do not follow.
- The agreement is where the gold is lost, and the path shape does not change that by construction (the agreement decides whether an axis answers): of the 37 / 38 questions whose gold is seated in a read window, the gold is the END unit of some section walk in 18 / 20, and a word of the PATH of some walk in 31 / 34 (path_ceiling table); an agreed entry has it in 1.  The walks pass the gold or end on it; the three-way agreement (and, under the two-ratio rule, the one-edge z axis) does not let those walks answer.
- Entries are the same in both shapes (an entry is (window, axis, agreed unit)); only the words differ.  Words in the entries of the 69 answerable questions: slide three 4 -> 12 (4 entries, 3 words each), slide two_if_single_edge 88 -> 96 (88 entries; 4 of them have 3 words, the others one word: a one-edge axis has no walk, or the walk is one unit), order 6 -> 17 (6 entries, 2-3 words each).  Words per entry median / max: 3 / 3 (slide three), 1 / 3 (slide two_if), 3 / 3 (order).  The lists are short (<= 9 entries): the long lists of the flat path (17-141 entries) do not occur.
- Single wrong answers on the answerable questions: unit 4 / 12 / 4 / 4, path 3 / 11 / 4 / 4 (the path shape turns a wrong single answer into the right one once, and into a longer wrong answer otherwise).
- unans: three abstains 25 / 25 under both shapes, both orders and both z_deep rules; two_if_single_edge on z_deep slide gives 8 single confident answers (G3-c2 placements 7, G3-c3 placements with the old read order 9), 0 on z_deep order (where it again does not differ from three).
- z_deep order vs slide: the same picture (gold in a candidate 0-1); order gives 6 entries in the 94 questions (both agreement rules) against 4 (three) / 140 (two_if) on slide.
- Time: 94 questions in 12-20 s wall with 4 workers at load 3-6 (cache load about 1 s); 0.34-0.66 s per question at the median.
