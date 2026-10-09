# G3-e / S1 -- bank2 fulllead through the question path over sliding windows (`structure="slide"`, tier RUN), with the T10 rows and B1/B2

Systems: `slide P [tag]` = ask_slide, preset P (fast 4 / standard 10 / full unbounded WINDOWS), tag = configuration (`three` = agreement R1=R2=R3; `two_if_single_edge` = an axis with one evidenced edge judged on R2, R3 only; suffixes: `-wnone` grouping by kind only (no question-unit count inside a group), `-sent` windows hold = units of the sentences, `-rep` representative of each class only, `-standins` stand-in units make a window a candidate). A candidate = one entry (window, axis, agreed unit; `words` = [unit]). `T10 flat-P` = the T10 flat sweep (3 tiers; candidates = entries over the 3 tiers) and its RUN tier only; `T10 layers-ssp-P` = flat + stable-seats-path layers. B1/B2 = baselines.py (MeCab / bigram).

Grading = t9/scorer.py (gold alternative a substring of one WORD of an entry; NFKC, casefold, ...). 'Gold in a candidate' = any candidate holds the gold. Single right / wrong = exactly one candidate (holds / does not hold) the gold; list = >= 2 candidates; none = no candidate. List size = number of entries (duplicates across windows / axes are separate entries, never merged; `distinct` = distinct unit sets).

## intra2 (fulllead, n = 69)

| system | n run | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size median / max (lists) | distinct units median | first-gold pos median / max | windows read median / max | candidate windows median | partial (0 read) | s/question median (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| slide fast [three] | 69 | 0 (0%) | 0 | 2 | 0 | 0 | 67 | - / - | 0.0 | - / - | 4.0 / 4 | 6.0 | 44 (3) | 0.57 (1.93) |
| slide fast [three] unanimous members only (derived) | 69 | 0 (0%) | 0 | 2 | 0 | 0 | 67 | - / - | 0.0 | - / - | 4.0 / 4 | 6.0 | 44 (3) | 0.57 (1.93) |
| slide fast [two_if_single_edge-rep] | 69 | 0 (0%) | 0 | 19 | 0 | 6 | 44 | 3.0 / 3 | 0.0 | - / - | 4.0 / 4 | 6.0 | 44 (3) | 0.11 (0.29) |
| slide fast [two_if_single_edge-sent] | 69 | 0 (0%) | 0 | 12 | 0 | 18 | 39 | 4.0 / 10 | 0.0 | - / - | 3.0 / 4 | 8.0 | 51 (12) | 0.61 (2.10) |
| slide fast [two_if_single_edge-standins] | 69 | 1 (1%) | 0 | 15 | 1 | 24 | 29 | 4.0 / 10 | 1.0 | 2.0 / 2 | 4.0 / 4 | 15.0 | 61 (3) | 0.68 (2.64) |
| slide fast [two_if_single_edge-wnone] | 69 | 0 (0%) | 0 | 17 | 0 | 23 | 29 | 5.0 / 10 | 1.0 | - / - | 4.0 / 4 | 6.0 | 44 (4) | 0.61 (2.26) |
| slide fast [two_if_single_edge] | 69 | 0 (0%) | 0 | 16 | 0 | 25 | 28 | 4.0 / 10 | 1.0 | - / - | 4.0 / 4 | 6.0 | 44 (3) | 0.54 (1.85) |
| slide fast [two_if_single_edge] unanimous members only (derived) | 69 | 0 (0%) | 0 | 2 | 0 | 0 | 67 | - / - | 0.0 | - / - | 4.0 / 4 | 6.0 | 44 (3) | 0.54 (1.85) |
| slide full [three] | 69 | 0 (0%) | 0 | 2 | 0 | 1 | 66 | 2.0 / 2 | 0.0 | - / - | 6.0 / 22 | 6.0 | 0 (0) | 1.39 (5.77) |
| slide full [three] unanimous members only (derived) | 69 | 0 (0%) | 0 | 2 | 0 | 0 | 67 | - / - | 0.0 | - / - | 6.0 / 22 | 6.0 | 0 (0) | 1.39 (5.77) |
| slide full [two_if_single_edge] | 69 | 2 (3%) | 0 | 8 | 2 | 38 | 21 | 5.0 / 26 | 2.0 | 13.5 / 26 | 6.0 / 22 | 6.0 | 0 (0) | 1.32 (5.33) |
| slide full [two_if_single_edge] unanimous members only (derived) | 69 | 0 (0%) | 0 | 5 | 0 | 0 | 64 | - / - | 0.0 | - / - | 6.0 / 22 | 6.0 | 0 (0) | 1.32 (5.33) |
| slide standard [three] | 69 | 0 (0%) | 0 | 2 | 0 | 1 | 66 | 2.0 / 2 | 0.0 | - / - | 6.0 / 10 | 6.0 | 14 (0) | 1.41 (3.99) |
| slide standard [three] unanimous members only (derived) | 69 | 0 (0%) | 0 | 2 | 0 | 0 | 67 | - / - | 0.0 | - / - | 6.0 / 10 | 6.0 | 14 (0) | 1.41 (3.99) |
| slide standard [two_if_single_edge] | 69 | 1 (1%) | 0 | 9 | 1 | 38 | 21 | 5.0 / 16 | 2.0 | 1.0 / 1 | 6.0 / 10 | 6.0 | 14 (0) | 1.38 (3.66) |
| slide standard [two_if_single_edge] unanimous members only (derived) | 69 | 0 (0%) | 0 | 5 | 0 | 0 | 64 | - / - | 0.0 | - / - | 6.0 / 10 | 6.0 | 14 (0) | 1.38 (3.66) |
| T10 flat-fast (3 tiers) [ordered-stop] | 69 | 16 (23%) | 0 | 2 | 16 | 49 | 2 | 26.0 / 141 | 25.0 | 1.0 / 38 | - | - | - | 165.95 (413.56) |
| T10 flat-fast RUN tier only [ordered-stop] | 69 | 15 (22%) | 1 | 2 | 14 | 44 | 8 | 17.0 / 101 | 11.0 | 1.0 / 38 | - | - | - | 165.95 (413.56) |
| T10 layers-ssp-fast [ordered-stop] | 69 | 21 (30%) | 0 | 0 | 21 | 46 | 2 | 28.0 / 146 | 26.0 | 2.0 / 82 | - | - | - | 294.72 (749.79) |
| T10 flat-standard (3 tiers) [ordered-stop] | 69 | 19 (28%) | 0 | 1 | 19 | 49 | 0 | 44.5 / 203 | 43.0 | 1.0 / 53 | - | - | - | 485.69 (1087.67) |
| T10 flat-standard RUN tier only [ordered-stop] | 69 | 18 (26%) | 1 | 0 | 17 | 44 | 7 | 28.0 / 171 | 20.0 | 1.0 / 43 | - | - | - | 485.69 (1087.67) |
| T10 layers-ssp-standard [ordered-stop] | 69 | 27 (39%) | 0 | 0 | 27 | 42 | 0 | 61.0 / 234 | 55.0 | 3.0 / 93 | - | - | - | 956.94 (1586.82) |
| B1-mecab | 69 | 47 (68%) | 31 | 18 | 16 | 4 | 0 | 2.0 / 34 | 1.0 | 1.0 / 8 | - | - | - | - (-) |
| B2-mecab | 69 | 57 (83%) | 20 | 2 | 37 | 10 | 0 | 2.0 / 42 | 2.0 | 1.0 / 12 | - | - | - | - (-) |
| B1-bigram | 69 | 38 (55%) | 30 | 29 | 8 | 2 | 0 | 2.0 / 5 | 1.0 | 1.0 / 5 | - | - | - | - (-) |
| B2-bigram | 69 | 54 (78%) | 19 | 2 | 35 | 13 | 0 | 2.0 / 5 | 2.0 | 1.0 / 5 | - | - | - | - (-) |

## unans (fulllead, n = 25): can a user reject what is shown?

Correct behaviour = abstain. 'no candidate' = typed abstention; 'list only' = rejectable by a user; 'single answer' = confident wrong.

| system | n run | no candidate (abstained) | list only (rejectable) | single answer (confident wrong) | list size median / max | verdicts |
|---|---|---|---|---|---|---|
| slide fast [three] | 25 | 25 | 0 | 0 | - / - | U_NOT_READ 1, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 21, U_SECTION_DISAGREEMENT 2 |
| slide fast [three] unanimous members only (derived) | 25 | 25 | 0 | 0 | - / - | - |
| slide fast [two_if_single_edge-rep] | 25 | 17 | 1 | 7 | 2.0 / 2 | ANSWER 7, CHOICE 1, U_NOT_READ 1, U_NO_EVIDENCE 3, U_RATIO_DISAGREEMENT 12, U_SECTION_DISAGREEMENT 1 |
| slide fast [two_if_single_edge-sent] | 25 | 12 | 7 | 6 | 3.0 / 7 | ANSWER 6, CHOICE 7, U_NOT_READ 2, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 8, U_SECTION_DISAGREEMENT 1 |
| slide fast [two_if_single_edge-standins] | 25 | 18 | 3 | 4 | 2.0 / 4 | ANSWER 4, CHOICE 3, U_NOT_READ 3, U_RATIO_DISAGREEMENT 10, U_SECTION_DISAGREEMENT 5 |
| slide fast [two_if_single_edge-wnone] | 25 | 11 | 8 | 6 | 3.5 / 7 | ANSWER 6, CHOICE 8, U_NOT_READ 1, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 8, U_SECTION_DISAGREEMENT 1 |
| slide fast [two_if_single_edge] | 25 | 10 | 8 | 7 | 3.5 / 7 | ANSWER 7, CHOICE 8, U_NOT_READ 1, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 8 |
| slide fast [two_if_single_edge] unanimous members only (derived) | 25 | 25 | 0 | 0 | - / - | - |
| slide full [three] | 25 | 24 | 0 | 1 | - / - | ANSWER 1, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 22, U_SECTION_DISAGREEMENT 1 |
| slide full [three] unanimous members only (derived) | 25 | 24 | 0 | 1 | - / - | - |
| slide full [two_if_single_edge] | 25 | 10 | 10 | 5 | 5.0 / 28 | ANSWER 5, CHOICE 10, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 9 |
| slide full [two_if_single_edge] unanimous members only (derived) | 25 | 24 | 0 | 1 | - / - | - |
| slide standard [three] | 25 | 24 | 0 | 1 | - / - | ANSWER 1, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 22, U_SECTION_DISAGREEMENT 1 |
| slide standard [three] unanimous members only (derived) | 25 | 24 | 0 | 1 | - / - | - |
| slide standard [two_if_single_edge] | 25 | 10 | 10 | 5 | 5.0 / 18 | ANSWER 5, CHOICE 10, U_NO_EVIDENCE 1, U_RATIO_DISAGREEMENT 9 |
| slide standard [two_if_single_edge] unanimous members only (derived) | 25 | 24 | 0 | 1 | - / - | - |
| T10 flat-fast (3 tiers) [ordered-stop] | 25 | 1 | 23 | 1 | 37.0 / 258 | - |
| T10 flat-fast RUN tier only [ordered-stop] | 25 | 5 | 20 | 0 | 29.0 / 198 | - |
| T10 layers-ssp-fast [ordered-stop] | 25 | 0 | 24 | 1 | 37.5 / 264 | - |
| T10 flat-standard (3 tiers) [ordered-stop] | 25 | 0 | 25 | 0 | 52.0 / 330 | - |
| T10 flat-standard RUN tier only [ordered-stop] | 25 | 4 | 21 | 0 | 38.0 / 198 | - |
| T10 layers-ssp-standard [ordered-stop] | 25 | 0 | 25 | 0 | 63.0 / 340 | - |
| B1-mecab | 25 | 0 | 13 | 12 | 3.0 / 52 | - |
| B2-mecab | 25 | 0 | 24 | 1 | 2.5 / 68 | - |
| B1-bigram | 25 | 0 | 6 | 19 | 2.5 / 54 | - |
| B2-bigram | 25 | 0 | 23 | 2 | 2.0 / 78 | - |

## Per axis (slide systems, intra2): where the gold is found

'x only' / 'z only' / 'both' = the gold is in an entry of that axis only / of both axes; `y` never answers in S1 (RUN-only windows have no y edge). `unit+path` = the same count with the entry's path words (the units of the walk steps and edge partners, diagnostic: wider than the headline `words = [unit]`). `distinct windows` = windows with an entry, median.

| system | gold in an entry | x only | z only | both | gold in unit+path | entries x / z (total) | windows with an entry median | questions with an entry |
|---|---|---|---|---|---|---|---|---|
| slide fast [three] | 0 | 0 | 0 | 0 | 1 | 2 / 0 (2) | 0.0 | 2 |
| slide fast [three] unanimous members only (derived) | 0 | 0 | 0 | 0 | 1 | 2 / 0 (2) | 0.0 | 2 |
| slide fast [two_if_single_edge-rep] | 0 | 0 | 0 | 0 | 1 | 2 / 33 (35) | 0.0 | 25 |
| slide fast [two_if_single_edge-sent] | 0 | 0 | 0 | 0 | 2 | 3 / 81 (84) | 0.0 | 30 |
| slide fast [two_if_single_edge-standins] | 1 | 0 | 1 | 0 | 2 | 1 / 119 (120) | 1.0 | 40 |
| slide fast [two_if_single_edge-wnone] | 0 | 0 | 0 | 0 | 2 | 1 / 125 (126) | 1.0 | 40 |
| slide fast [two_if_single_edge] | 0 | 0 | 0 | 0 | 2 | 2 / 128 (130) | 1.0 | 41 |
| slide fast [two_if_single_edge] unanimous members only (derived) | 0 | 0 | 0 | 0 | 1 | 2 / 0 (2) | 1.0 | 2 |
| slide full [three] | 0 | 0 | 0 | 0 | 1 | 2 / 2 (4) | 0.0 | 3 |
| slide full [three] unanimous members only (derived) | 0 | 0 | 0 | 0 | 1 | 2 / 0 (2) | 0.0 | 2 |
| slide full [two_if_single_edge] | 2 | 0 | 2 | 0 | 4 | 3 / 273 (276) | 1.0 | 48 |
| slide full [two_if_single_edge] unanimous members only (derived) | 0 | 0 | 0 | 0 | 1 | 3 / 2 (5) | 1.0 | 5 |
| slide standard [three] | 0 | 0 | 0 | 0 | 1 | 2 / 2 (4) | 0.0 | 3 |
| slide standard [three] unanimous members only (derived) | 0 | 0 | 0 | 0 | 1 | 2 / 0 (2) | 0.0 | 2 |
| slide standard [two_if_single_edge] | 1 | 0 | 1 | 0 | 3 | 3 / 217 (220) | 1.0 | 48 |
| slide standard [two_if_single_edge] unanimous members only (derived) | 0 | 0 | 0 | 0 | 1 | 3 / 2 (5) | 1.0 | 5 |

## Typed abstentions, summed over (window, axis) of the questions answered (slide systems)

| system | kind | n | points_nowhere | section_disagreement | ratio_disagreement | no_edges | not_grounded | unstable_axis_improvable | no_question_unit | mixed |
|---|---|---|---|---|---|---|---|---|---|---|
| slide fast [three] | intra2 | 69 | 91 | 134 | 28 | 294 | 0 | 0 | 0 | 102 |
| slide fast [three] | unans | 25 | 33 | 27 | 14 | 92 | 0 | 0 | 0 | 32 |
| slide fast [two_if_single_edge-rep] | intra2 | 69 | 142 | 103 | 77 | 294 | 0 | 0 | 0 | 0 |
| slide fast [two_if_single_edge-rep] | unans | 25 | 49 | 20 | 28 | 92 | 0 | 0 | 0 | 0 |
| slide fast [two_if_single_edge-sent] | intra2 | 69 | 75 | 65 | 39 | 239 | 0 | 0 | 0 | 60 |
| slide fast [two_if_single_edge-sent] | unans | 25 | 37 | 15 | 12 | 90 | 0 | 0 | 0 | 18 |
| slide fast [two_if_single_edge-standins] | intra2 | 69 | 106 | 92 | 37 | 289 | 0 | 0 | 0 | 60 |
| slide fast [two_if_single_edge-standins] | unans | 25 | 45 | 20 | 14 | 106 | 0 | 0 | 0 | 16 |
| slide fast [two_if_single_edge-wnone] | intra2 | 69 | 88 | 92 | 36 | 285 | 0 | 0 | 0 | 67 |
| slide fast [two_if_single_edge-wnone] | unans | 25 | 32 | 17 | 16 | 91 | 0 | 0 | 0 | 18 |
| slide fast [two_if_single_edge] | intra2 | 69 | 90 | 97 | 38 | 294 | 0 | 0 | 0 | 71 |
| slide fast [two_if_single_edge] | unans | 25 | 33 | 17 | 16 | 92 | 0 | 0 | 0 | 18 |
| slide full [three] | intra2 | 69 | 224 | 293 | 79 | 732 | 0 | 0 | 0 | 199 |
| slide full [three] | unans | 25 | 52 | 61 | 27 | 181 | 0 | 0 | 0 | 59 |
| slide full [two_if_single_edge] | intra2 | 69 | 226 | 210 | 93 | 732 | 0 | 0 | 0 | 138 |
| slide full [two_if_single_edge] | unans | 25 | 52 | 41 | 30 | 181 | 0 | 0 | 0 | 37 |
| slide standard [three] | intra2 | 69 | 189 | 230 | 55 | 572 | 0 | 0 | 0 | 160 |
| slide standard [three] | unans | 25 | 46 | 44 | 24 | 142 | 0 | 0 | 0 | 49 |
| slide standard [two_if_single_edge] | intra2 | 69 | 181 | 165 | 67 | 572 | 0 | 0 | 0 | 112 |
| slide standard [two_if_single_edge] | unans | 25 | 46 | 27 | 27 | 142 | 0 | 0 | 0 | 29 |

Verdicts (all 94):

- slide fast [three]: ANSWER 2, UNKNOWN_NOT_READ 4, UNKNOWN_NO_EVIDENCE 1, UNKNOWN_RATIO_DISAGREEMENT 77, UNKNOWN_SECTION_DISAGREEMENT 10
- slide fast [two_if_single_edge-rep]: ANSWER 26, CHOICE 7, UNKNOWN_NOT_READ 4, UNKNOWN_NO_EVIDENCE 6, UNKNOWN_RATIO_DISAGREEMENT 43, UNKNOWN_SECTION_DISAGREEMENT 8
- slide fast [two_if_single_edge-sent]: ANSWER 18, CHOICE 25, UNKNOWN_NOT_READ 14, UNKNOWN_NO_EVIDENCE 1, UNKNOWN_RATIO_DISAGREEMENT 33, UNKNOWN_SECTION_DISAGREEMENT 3
- slide fast [two_if_single_edge-standins]: ANSWER 19, CHOICE 28, UNKNOWN_NOT_READ 6, UNKNOWN_NO_EVIDENCE 2, UNKNOWN_RATIO_DISAGREEMENT 34, UNKNOWN_SECTION_DISAGREEMENT 5
- slide fast [two_if_single_edge-wnone]: ANSWER 23, CHOICE 31, UNKNOWN_NOT_READ 5, UNKNOWN_NO_EVIDENCE 1, UNKNOWN_RATIO_DISAGREEMENT 32, UNKNOWN_SECTION_DISAGREEMENT 2
- slide fast [two_if_single_edge]: ANSWER 23, CHOICE 33, UNKNOWN_NOT_READ 4, UNKNOWN_NO_EVIDENCE 1, UNKNOWN_RATIO_DISAGREEMENT 32, UNKNOWN_SECTION_DISAGREEMENT 1
- slide full [three]: ANSWER 3, CHOICE 1, UNKNOWN_NO_EVIDENCE 1, UNKNOWN_RATIO_DISAGREEMENT 82, UNKNOWN_SECTION_DISAGREEMENT 7
- slide full [two_if_single_edge]: ANSWER 13, CHOICE 50, UNKNOWN_NO_EVIDENCE 1, UNKNOWN_RATIO_DISAGREEMENT 29, UNKNOWN_SECTION_DISAGREEMENT 1
- slide standard [three]: ANSWER 3, CHOICE 1, UNKNOWN_NO_EVIDENCE 1, UNKNOWN_RATIO_DISAGREEMENT 82, UNKNOWN_SECTION_DISAGREEMENT 7
- slide standard [two_if_single_edge]: ANSWER 14, CHOICE 49, UNKNOWN_NO_EVIDENCE 1, UNKNOWN_RATIO_DISAGREEMENT 29, UNKNOWN_SECTION_DISAGREEMENT 1

Grammar forms of the 94 questions: plain 2, predicate 50, slot 25, standin 17

## Reach (window level, intra2)

The gold is a seated RUN unit of a window that holds a question unit (every candidate window, no cap): **40 / 69** (candidate windows per question: median 6.0, max 22). This is the upper bound of a unit-valued entry (`words = [unit]`) before the agreement, the cap or the tier of the gold (18 of the 69 golds are not one unit of any tier).

## Chance hits (diagnostic): how often the gold of ANOTHER question is held by an entry

| system | questions with entries | mean entries | other golds held per question (mean x 100 / 68) |
|---|---|---|---|
| slide fast [three] | 2 | 1.0 | 0.0 |
| slide fast [three] unanimous members only (derived) | 2 | 1.0 | 0.0 |
| slide fast [two_if_single_edge-rep] | 25 | 1.4 | 0.0 |
| slide fast [two_if_single_edge-sent] | 30 | 2.8 | 0.2 |
| slide fast [two_if_single_edge-standins] | 40 | 3.0 | 0.3 |
| slide fast [two_if_single_edge-wnone] | 40 | 3.1 | 0.3 |
| slide fast [two_if_single_edge] | 41 | 3.2 | 0.3 |
| slide fast [two_if_single_edge] unanimous members only (derived) | 2 | 1.0 | 0.0 |
| slide full [three] | 3 | 1.3 | 0.0 |
| slide full [three] unanimous members only (derived) | 2 | 1.0 | 0.0 |
| slide full [two_if_single_edge] | 48 | 5.8 | 0.4 |
| slide full [two_if_single_edge] unanimous members only (derived) | 5 | 1.0 | 0.0 |
| slide standard [three] | 3 | 1.3 | 0.0 |
| slide standard [three] unanimous members only (derived) | 2 | 1.0 | 0.0 |
| slide standard [two_if_single_edge] | 48 | 4.6 | 0.4 |
| slide standard [two_if_single_edge] unanimous members only (derived) | 5 | 1.0 | 0.0 |

## Time (wall seconds per question inside a worker; several workers at once on the shared machine)

| system | n | median / mean / max s | load median / max |
|---|---|---|---|
| slide fast [three] | 94 | 0.55 / 0.60 / 1.93 | 3.8 / 3.9 |
| slide fast [two_if_single_edge-rep] | 94 | 0.10 / 0.11 / 0.29 | 9.5 / 9.5 |
| slide fast [two_if_single_edge-sent] | 94 | 0.62 / 0.67 / 2.26 | 8.4 / 9.7 |
| slide fast [two_if_single_edge-standins] | 94 | 0.66 / 0.79 / 2.64 | 12.3 / 14.1 |
| slide fast [two_if_single_edge-wnone] | 94 | 0.60 / 0.68 / 2.26 | 5.9 / 7.0 |
| slide fast [two_if_single_edge] | 94 | 0.51 / 0.56 / 1.85 | 4.3 / 4.5 |
| slide full [three] | 94 | 1.29 / 1.80 / 5.84 | 16.6 / 16.7 |
| slide full [two_if_single_edge] | 94 | 1.21 / 1.70 / 5.54 | 16.6 / 17.5 |
| slide standard [three] | 94 | 1.23 / 1.44 / 3.99 | 15.1 / 16.0 |
| slide standard [two_if_single_edge] | 94 | 1.17 / 1.36 / 3.66 | 16.4 / 16.9 |

