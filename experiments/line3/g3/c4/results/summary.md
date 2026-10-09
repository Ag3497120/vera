# G3-c4 -- the deeper z-arm edges: evidence rule `slide` (n_z) vs `order` (the pair's word order, as x) on the question path over sliding windows

fulllead RUN, windows placed with the G3-c3 defaults (centre both growths, arm_cap budget, strict judgement), fast = 4 windows read per question, tier RUN, t9 scorer; `c2` rows = S1's committed run on the G3-c2 placements (before G3-c3); `c3 placements, z_deep slide` = the G3-c3 defaults unchanged. A candidate = one entry (window, axis, agreed unit).  Gold in a candidate = some candidate holds the gold (a WORD substring, NFKC); single right / wrong = exactly one candidate (does / does not); list = >= 2.

## intra2 (fulllead, n = 69)

| system | n | gold in a candidate | via x / via z | single right | single wrong | list with gold | list without gold | no candidate | list size median / max | first-gold pos median | windows read median / max | s/question median (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| c2 (S1, G3-c2 placements) three | 69 | 0 (0%) | 0 / 0 | 0 | 2 | 0 | 0 | 67 | - / - | - | 4.0 / 4 | 0.57 (1.93) |
| c2 (S1, G3-c2 placements) two_if_single_edge | 69 | 0 (0%) | 0 / 0 | 0 | 16 | 0 | 25 | 28 | 4.0 / 10 | - | 4.0 / 4 | 0.54 (1.85) |
| c3 placements, z_deep slide, three | 69 | 0 (0%) | 0 / 0 | 0 | 6 | 0 | 0 | 63 | - / - | - | 3.0 / 4 | 0.61 (3.22) |
| c3 placements, z_deep slide, two_if_single_edge | 69 | 0 (0%) | 0 / 0 | 0 | 14 | 0 | 20 | 35 | 2.5 / 6 | - | 3.0 / 4 | 0.59 (3.15) |
| c3 placements, z_deep order, three | 69 | 0 (0%) | 0 / 0 | 0 | 3 | 0 | 1 | 65 | 2.0 / 2 | - | 3.0 / 4 | 0.29 (2.03) |
| c3 placements, z_deep order, two_if_single_edge | 69 | 0 (0%) | 0 / 0 | 0 | 3 | 0 | 1 | 65 | 2.0 / 2 | - | 3.0 / 4 | 0.32 (2.03) |
| T10 flat-fast (3 tiers) | 69 | 16 (23%) | - | 0 | 2 | 16 | 49 | 2 | 26.0 / 141 | 1.0 | - | 165.95 (413.56) |
| T10 flat-fast RUN tier only | 69 | 15 (22%) | - | 1 | 2 | 14 | 44 | 8 | 17.0 / 101 | 1.0 | - | 165.95 (413.56) |
| T10 layers-ssp-fast | 69 | 21 (30%) | - | 0 | 0 | 21 | 46 | 2 | 28.0 / 146 | 2.0 | - | 294.72 (749.79) |
| B1-mecab | 69 | 47 (68%) | - | 31 | 18 | 16 | 4 | 0 | 2.0 / 34 | 1.0 | - | - (-) |
| B2-mecab | 69 | 57 (83%) | - | 20 | 2 | 37 | 10 | 0 | 2.0 / 42 | 1.0 | - | - (-) |
| B1-bigram | 69 | 38 (55%) | - | 30 | 29 | 8 | 2 | 0 | 2.0 / 5 | 1.0 | - | - (-) |
| B2-bigram | 69 | 54 (78%) | - | 19 | 2 | 35 | 13 | 0 | 2.0 / 5 | 1.0 | - | - (-) |

## unans (fulllead, n = 25): can a user reject what is shown?

| system | n | no candidate (abstained) | list only (rejectable) | single answer (confident wrong) | list size median / max | verdicts |
|---|---|---|---|---|---|---|
| c2 (S1, G3-c2 placements) three | 25 | 25 | 0 | 0 | - / - | U_NOT_READ 1, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 21, U_SECTION_DISAGREEMENT 2 |
| c2 (S1, G3-c2 placements) two_if_single_edge | 25 | 10 | 8 | 7 | 3.5 / 7 | ANSWER 7, CHOICE 8, U_NOT_READ 1, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 8 |
| c3 placements, z_deep slide, three | 25 | 25 | 0 | 0 | - / - | U_NOT_READ 1, U_RATIO_DISAGREEMENT 21, U_SECTION_DISAGREEMENT 3 |
| c3 placements, z_deep slide, two_if_single_edge | 25 | 10 | 6 | 9 | 5.5 / 9 | ANSWER 9, CHOICE 6, U_NOT_READ 1, U_RATIO_DISAGREEMENT 8, U_SECTION_DISAGREEMENT 1 |
| c3 placements, z_deep order, three | 25 | 25 | 0 | 0 | - / - | U_NOT_READ 2, U_RATIO_DISAGREEMENT 16, U_SECTION_DISAGREEMENT 7 |
| c3 placements, z_deep order, two_if_single_edge | 25 | 25 | 0 | 0 | - / - | U_NOT_READ 2, U_RATIO_DISAGREEMENT 16, U_SECTION_DISAGREEMENT 7 |
| T10 flat-fast (3 tiers) | 25 | 1 | 23 | 1 | 37.0 / 258 | - |
| T10 flat-fast RUN tier only | 25 | 5 | 20 | 0 | 29.0 / 198 | - |
| T10 layers-ssp-fast | 25 | 0 | 24 | 1 | 37.5 / 264 | - |
| B1-mecab | 25 | 0 | 13 | 12 | 3.0 / 52 | - |
| B2-mecab | 25 | 0 | 24 | 1 | 2.5 / 68 | - |
| B1-bigram | 25 | 0 | 6 | 19 | 2.5 / 54 | - |
| B2-bigram | 25 | 0 | 23 | 2 | 2.0 / 78 | - |

## Where the questions end (slide systems): typed abstentions summed over (window, axis) of the questions answered, and the entries

| system | kind | n | entries x / z | points_nowhere | section_disagreement | ratio_disagreement | no_edges | not_grounded | unstable_axis_improvable | no_question_unit | mixed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| c2 (S1, G3-c2 placements) three | intra2 | 69 | 2 / 0 | 91 | 134 | 28 | 294 | 0 | 0 | 0 | 102 |
| c2 (S1, G3-c2 placements) three | unans | 25 | 0 / 0 | 33 | 27 | 14 | 92 | 0 | 0 | 0 | 32 |
| c2 (S1, G3-c2 placements) two_if_single_edge | intra2 | 69 | 2 / 128 | 90 | 97 | 38 | 294 | 0 | 0 | 0 | 71 |
| c2 (S1, G3-c2 placements) two_if_single_edge | unans | 25 | 0 / 36 | 33 | 17 | 16 | 92 | 0 | 0 | 0 | 18 |
| c3 placements, z_deep slide, three | intra2 | 69 | 2 / 4 | 39 | 59 | 27 | 218 | 0 | 0 | 0 | 233 |
| c3 placements, z_deep slide, three | unans | 25 | 0 / 0 | 22 | 16 | 11 | 74 | 0 | 0 | 0 | 72 |
| c3 placements, z_deep slide, two_if_single_edge | intra2 | 69 | 2 / 69 | 40 | 55 | 33 | 218 | 0 | 0 | 0 | 194 |
| c3 placements, z_deep slide, two_if_single_edge | unans | 25 | 0 / 42 | 22 | 13 | 12 | 74 | 0 | 0 | 0 | 53 |
| c3 placements, z_deep order, three | intra2 | 69 | 3 / 2 | 43 | 40 | 12 | 199 | 0 | 0 | 0 | 262 |
| c3 placements, z_deep order, three | unans | 25 | 0 / 0 | 22 | 10 | 7 | 69 | 0 | 0 | 0 | 75 |
| c3 placements, z_deep order, two_if_single_edge | intra2 | 69 | 3 / 2 | 43 | 40 | 12 | 199 | 0 | 0 | 0 | 262 |
| c3 placements, z_deep order, two_if_single_edge | unans | 25 | 0 / 0 | 22 | 10 | 7 | 69 | 0 | 0 | 0 | 75 |

## Reach (window level, intra2): the gold is a seated RUN unit of a window that holds a question unit (every candidate window, no cap)

| placements | reach / 69 | candidate windows median / max | windows read without the cap (plan_windows cap=None), median |
|---|---|---|---|
| z_deep slide | 40 / 69 | 6.0 / 35 | 6.0 |
| z_deep order | 41 / 69 | 6.0 / 35 | 6.0 |

(S1 on the G3-c2 placements: reach 40 / 69.)

## The window caches (292 pair windows)

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

## The members of the windows that seat the gold (gold_diag.py)

Windows = those that hold a question unit and seat a unit that holds the gold (representative's seats). Members = every member of the class, read as the question path reads it; outcome per (member, axis): gold = the agreed unit holds the gold, other = another unit, else the typed abstention. `admitted gold` = gold AND the member holds a question unit, the answer is grounded and the axis is strictly stable for the member (what slide_query.read_window admits).

### agreement three

| z_deep | questions with a reach window | reach windows | members read | axis | gold | other unit | points_nowhere | section_disagreement | ratio_disagreement | no_edges | admitted gold (member-axes) | reach windows with an admitted gold on this axis | questions with an admitted gold on this axis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| slide | 40 | 73 | 16966 | x | 0 | 19 | 7237 | 7285 | 2425 | 0 | 0 | 0 | 0 |
| slide | 40 | 73 | 16966 | z | 0 | 72 | 7068 | 6816 | 1210 | 1800 | 0 | 0 | 0 |
| order | 41 | 78 | 7528 | x | 0 | 12 | 4637 | 1874 | 1005 | 0 | 0 | 0 | 0 |
| order | 41 | 78 | 7528 | z | 1 | 6 | 1527 | 3520 | 672 | 1802 | 0 | 0 | 0 |

### agreement two_if_single_edge

| z_deep | questions with a reach window | reach windows | members read | axis | gold | other unit | points_nowhere | section_disagreement | ratio_disagreement | no_edges | admitted gold (member-axes) | reach windows with an admitted gold on this axis | questions with an admitted gold on this axis |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| slide | 40 | 73 | 16966 | x | 0 | 19 | 7237 | 7285 | 2425 | 0 | 0 | 0 | 0 |
| slide | 40 | 73 | 16966 | z | 116 | 2028 | 8217 | 1590 | 3215 | 1800 | 116 | 2 | 2 |
| order | 41 | 78 | 7528 | x | 0 | 12 | 4637 | 1874 | 1005 | 0 | 0 | 0 | 0 |
| order | 41 | 78 | 7528 | z | 1 | 6 | 1527 | 3520 | 672 | 1802 | 0 | 0 | 0 |


## The independent verifier on real windows (verify_order.py)

- z_deep order: 292 windows; verifier-stable classes 292; record strict counts = verifier's 292; representative's axis key = verifier's key 292; z-arm edges read with their rule 1566 (of them deeper edges 1144); 328 s
- z_deep slide: 292 windows; verifier-stable classes 292; record strict counts = verifier's 292; representative's axis key = verifier's key 292; z-arm edges read with their rule 875 (of them deeper edges 496); 422 s

