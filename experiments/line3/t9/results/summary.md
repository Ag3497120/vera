# T9 -- bank2 (cross-sentence bank) measured on Vera line 3 systems, with keyword baselines

Grading: `scorer.py` (NFKC, casefold, no spaces / thousands commas / middle dots, 万 and kanji digits to ASCII; gold alternative a substring of ONE word of an entry; for B1/B2 a candidate is one sentence). 'Gold in a candidate' = any candidate holds the gold. Single right / wrong = exactly one candidate holds / does not hold the gold; list = >= 2 candidates; none = no candidate. List size = number of candidates (entries over the 3 tiers + upper-layer entries). Times are wall seconds per question inside a worker (several workers ran at once, so times include contention; tower build not included). B1/B2 = baselines.py with MeCab ('-mecab') and character bigrams ('-bigram').

Systems: `flat-P` = layers off (ask, 3 tiers, preset P); `layers-path-P` = layers on, default path candidates; `layers-ssp-P` = layers on, stable-seats-path; `carry-{close|defer}-{path|index}-P` = RUN low carry tower + carry_query, path descent (design) or index descent (fallback=index).

## intra2 (fulllead, n = 69)

| system | n run | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size median / max (lists) | first-gold pos median / max | s/question median (max) | trace ok |
|---|---|---|---|---|---|---|---|---|---|---|---|
| flat-fast | 69 | 7 (10%) | 0 | 16 | 7 | 36 | 10 | 5.0 / 21 | 1.0 / 2 | 6.11 (23.98) | n/a |
| flat-standard | 69 | 9 (13%) | 0 | 4 | 9 | 55 | 1 | 7.5 / 37 | 1.0 / 3 | 41.21 (279.29) | n/a |
| layers-path-fast | 69 | 7 (10%) | 0 | 6 | 7 | 46 | 10 | 6.0 / 21 | 1.0 / 2 | 15.80 (44.24) | 69/69 |
| layers-path-standard | 69 | 10 (14%) | 0 | 0 | 10 | 58 | 1 | 11.0 / 41 | 1.5 / 23 | 106.26 (371.39) | 69/69 |
| layers-ssp-fast | 69 | 9 (13%) | 0 | 11 | 9 | 48 | 1 | 6.0 / 24 | 2.0 / 3 | 18.53 (48.23) | 69/69 |
| layers-ssp-standard | 69 | 16 (23%) | 0 | 0 | 16 | 53 | 0 | 23.0 / 65 | 2.5 / 46 | 97.88 (362.85) | 69/69 |
| carry-close-index-fast | 69 | 0 (0%) | 0 | 1 | 0 | 0 | 68 | - / - | - / - | 2.24 (11.38) | 69/69 |
| carry-close-index-standard | 69 | 7 (10%) | 1 | 7 | 6 | 7 | 48 | 2.0 / 39 | 1.0 / 36 | 5.12 (13.34) | 69/69 |
| carry-close-path-fast | 69 | 0 (0%) | 0 | 0 | 0 | 0 | 69 | - / - | - / - | 0.43 (0.47) | 69/69 |
| carry-close-path-standard | 69 | 0 (0%) | 0 | 0 | 0 | 0 | 69 | - / - | - / - | 0.43 (0.46) | 69/69 |
| carry-defer-index-fast | 69 | 0 (0%) | 0 | 5 | 0 | 2 | 62 | 10.0 / 10 | - / - | 1.66 (6.39) | 69/69 |
| carry-defer-index-standard | 69 | 10 (14%) | 2 | 7 | 8 | 15 | 37 | 3.0 / 15 | 1.0 / 3 | 3.86 (7.18) | 69/69 |
| carry-defer-path-fast | 69 | 0 (0%) | 0 | 1 | 0 | 0 | 68 | - / - | - / - | 0.98 (4.89) | 69/69 |
| carry-defer-path-standard | 69 | 2 (3%) | 0 | 9 | 2 | 3 | 55 | 2.0 / 9 | 1.5 / 2 | 1.27 (6.70) | 69/69 |
| B1-mecab | 69 | 47 (68%) | 31 | 18 | 16 | 4 | 0 | 2.0 / 34 | 1.0 / 8 | - (-) | n/a |
| B2-mecab | 69 | 57 (83%) | 20 | 2 | 37 | 10 | 0 | 2.0 / 42 | 1.0 / 12 | - (-) | n/a |
| B1-bigram | 69 | 38 (55%) | 30 | 29 | 8 | 2 | 0 | 2.0 / 5 | 1.0 / 5 | - (-) | n/a |
| B2-bigram | 69 | 54 (78%) | 19 | 2 | 35 | 13 | 0 | 2.0 / 5 | 1.0 / 5 | - (-) | n/a |

## cross2 (s3000, n = 9)

| system | n run | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size median / max (lists) | first-gold pos median / max | s/question median (max) | trace ok |
|---|---|---|---|---|---|---|---|---|---|---|---|
| flat-fast | 9 | 0 (0%) | 0 | 3 | 0 | 5 | 1 | 4.0 / 6 | - / - | 24.18 (56.28) | n/a |
| flat-standard | 9 | 0 (0%) | 0 | 2 | 0 | 7 | 0 | 7.0 / 11 | - / - | 93.16 (138.31) | n/a |
| layers-path-fast | 9 | 0 (0%) | 0 | 2 | 0 | 6 | 1 | 4.0 / 7 | - / - | 53.97 (70.39) | 9/9 |
| layers-path-standard | 9 | 0 (0%) | 0 | 1 | 0 | 8 | 0 | 9.0 / 11 | - / - | 210.04 (332.59) | 9/9 |
| layers-ssp-fast | 9 | 0 (0%) | 0 | 3 | 0 | 6 | 0 | 5.5 / 8 | - / - | 56.41 (100.34) | 9/9 |
| layers-ssp-standard | 9 | 0 (0%) | 0 | 0 | 0 | 9 | 0 | 22.0 / 46 | - / - | 221.26 (266.15) | 9/9 |
| carry-close-index-fast | 9 | 0 (0%) | 0 | 0 | 0 | 0 | 9 | - / - | - / - | 1.89 (4.22) | 9/9 |
| carry-close-index-standard | 9 | 0 (0%) | 0 | 0 | 0 | 0 | 9 | - / - | - / - | 6.06 (14.97) | 9/9 |
| carry-close-path-fast | 9 | 0 (0%) | 0 | 0 | 0 | 0 | 9 | - / - | - / - | 0.13 (1.22) | 9/9 |
| carry-close-path-standard | 9 | 0 (0%) | 0 | 0 | 0 | 0 | 9 | - / - | - / - | 0.03 (11.90) | 9/9 |
| carry-defer-index-fast | 9 | 0 (0%) | 0 | 0 | 0 | 0 | 9 | - / - | - / - | 2.54 (5.08) | 9/9 |
| carry-defer-index-standard | 9 | 1 (11%) | 0 | 0 | 1 | 1 | 7 | 2.5 / 3 | 1.0 / 1 | 10.59 (29.71) | 9/9 |
| carry-defer-path-fast | 9 | 0 (0%) | 0 | 0 | 0 | 0 | 9 | - / - | - / - | 1.92 (25.88) | 9/9 |
| carry-defer-path-standard | 9 | 0 (0%) | 0 | 0 | 0 | 1 | 8 | 2.0 / 2 | - / - | 15.99 (29.19) | 9/9 |
| B1-mecab | 9 | 2 (22%) | 0 | 5 | 2 | 2 | 0 | 16.0 / 32 | 16.0 / 17 | - (-) | n/a |
| B2-mecab | 9 | 8 (89%) | 0 | 0 | 8 | 1 | 0 | 3.0 / 35 | 2.5 / 18 | - (-) | n/a |
| B1-bigram | 9 | 1 (11%) | 0 | 6 | 1 | 2 | 0 | 4.0 / 7 | 2.0 / 2 | - (-) | n/a |
| B2-bigram | 9 | 9 (100%) | 0 | 0 | 9 | 0 | 0 | 2.0 / 8 | 2.0 / 5 | - (-) | n/a |

## unans (n = 50: fulllead 25, s3000 25): can a user reject what is shown?

Correct behaviour = abstain. B1/B2 never abstain (candidates for every question). 'list only' = rejectable by a user; 'single answer' = confident wrong.

| system | corpus | n run | no candidate (abstained) | list only (rejectable) | single answer (confident wrong) | list size median / max |
|---|---|---|---|---|---|---|
| flat-fast | fulllead | 25 | 5 | 16 | 4 | 3.0 / 18 |
| flat-fast | s3000 | 25 | 9 | 9 | 7 | 6.0 / 35 |
| flat-standard | fulllead | 25 | 0 | 25 | 0 | 7.0 / 35 |
| flat-standard | s3000 | 25 | 3 | 16 | 6 | 4.5 / 25 |
| layers-path-fast | fulllead | 25 | 5 | 17 | 3 | 4.0 / 19 |
| layers-path-fast | s3000 | 25 | 9 | 12 | 4 | 3.0 / 35 |
| layers-path-standard | fulllead | 25 | 0 | 25 | 0 | 12.0 / 46 |
| layers-path-standard | s3000 | 25 | 3 | 21 | 1 | 5.0 / 30 |
| layers-ssp-fast | fulllead | 25 | 2 | 20 | 3 | 4.5 / 21 |
| layers-ssp-fast | s3000 | 25 | 3 | 16 | 6 | 3.0 / 36 |
| layers-ssp-standard | fulllead | 25 | 0 | 25 | 0 | 21.0 / 66 |
| layers-ssp-standard | s3000 | 25 | 0 | 25 | 0 | 14.0 / 42 |
| carry-close-index-fast | fulllead | 25 | 25 | 0 | 0 | - / - |
| carry-close-index-fast | s3000 | 25 | 25 | 0 | 0 | - / - |
| carry-close-index-standard | fulllead | 25 | 9 | 6 | 10 | 3.0 / 12 |
| carry-close-index-standard | s3000 | 25 | 22 | 0 | 3 | - / - |
| carry-close-path-fast | fulllead | 25 | 25 | 0 | 0 | - / - |
| carry-close-path-fast | s3000 | 25 | 25 | 0 | 0 | - / - |
| carry-close-path-standard | fulllead | 25 | 25 | 0 | 0 | - / - |
| carry-close-path-standard | s3000 | 25 | 25 | 0 | 0 | - / - |
| carry-defer-index-fast | fulllead | 25 | 18 | 0 | 7 | - / - |
| carry-defer-index-fast | s3000 | 25 | 22 | 0 | 3 | - / - |
| carry-defer-index-standard | fulllead | 25 | 7 | 10 | 8 | 3.0 / 4 |
| carry-defer-index-standard | s3000 | 25 | 15 | 7 | 3 | 2.0 / 3 |
| carry-defer-path-fast | fulllead | 25 | 25 | 0 | 0 | - / - |
| carry-defer-path-fast | s3000 | 25 | 25 | 0 | 0 | - / - |
| carry-defer-path-standard | fulllead | 25 | 23 | 0 | 2 | - / - |
| carry-defer-path-standard | s3000 | 25 | 22 | 0 | 3 | - / - |
| B1-mecab | fulllead | 25 | 0 | 13 | 12 | 3.0 / 52 |
| B1-mecab | s3000 | 25 | 0 | 11 | 14 | 5.0 / 129 |
| B2-mecab | fulllead | 25 | 0 | 24 | 1 | 2.5 / 68 |
| B2-mecab | s3000 | 25 | 0 | 18 | 7 | 3.5 / 139 |
| B1-bigram | fulllead | 25 | 0 | 6 | 19 | 2.5 / 54 |
| B1-bigram | s3000 | 25 | 0 | 5 | 20 | 2.0 / 4 |
| B2-bigram | fulllead | 25 | 0 | 23 | 2 | 2.0 / 78 |
| B2-bigram | s3000 | 25 | 0 | 17 | 8 | 2.0 / 5 |

## cross2, per item (n = 9, s3000; report per item, not a rate)

Cell: S = single answer holds gold; Ln = list of n holds gold; w = single answer without gold; xn = list of n without gold; - = no candidate; . = not run. B1/B2 cells: S/Ln as for a sentence list (n = number of sentences).

| item | gold | flat-fast | flat-standard | layers-path-fast | layers-path-standard | layers-ssp-fast | layers-ssp-standard | carry-close-index-fast | carry-close-index-standard | carry-close-path-fast | carry-close-path-standard | carry-defer-index-fast | carry-defer-index-standard | carry-defer-path-fast | carry-defer-path-standard | B1-mecab | B2-mecab | B1-bigram | B2-bigram |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C2-006 | 省都 | x2 | x9 | x2 | x11 | x2 | x46 | - | - | - | - | - | - | - | - | x2 | L3 | w | L2 |
| C2-018 | 139日目 | x6 | x6 | x7 | x7 | x8 | x15 | - | - | - | - | - | L2 | - | - | w | L2 | w | L2 |
| C2-020 | 市轄区 | - | x11 | - | x11 | w | x22 | - | - | - | - | - | x3 | - | x2 | x3 | x4 | x4 | L6 |
| C2-021 | 玩具シリーズ|玩具 | x6 | x8 | x7 | x11 | x7 | x34 | - | - | - | - | - | - | - | - | w | L2 | w | L2 |
| C2-022 | 二人または二組|二人 | x4 | x7 | x4 | x10 | x6 | x17 | - | - | - | - | - | - | - | - | w | L3 | w | L3 |
| C2-024 | ウクライナ | w | w | w | w | w | x24 | - | - | - | - | - | - | - | - | w | L2 | w | L2 |
| C2-026 | 東三河 | w | w | w | x8 | w | x22 | - | - | - | - | - | - | - | - | w | L2 | w | L2 |
| C2-029 | 関東地方|関東 | w | x2 | x4 | x4 | x5 | x15 | - | - | - | - | - | - | - | - | L29 | L30 | L2 | L2 |
| R2-C006 | 最後の晩餐 | x2 | x2 | x2 | x3 | x4 | x16 | - | - | - | - | - | - | - | - | L32 | L35 | x7 | L8 |

## The 9 B2-hard items (missed by B2 with both tokenizers), per system

Cell: S = single answer holds gold; Ln = list of n holds gold; w = single answer without gold; xn = list of n without gold; - = no candidate; . = not run. B1/B2 cells: S/Ln as for a sentence list (n = number of sentences).

| item | gold | flat-fast | flat-standard | layers-path-fast | layers-path-standard | layers-ssp-fast | layers-ssp-standard | carry-close-index-fast | carry-close-index-standard | carry-close-path-fast | carry-close-path-standard | carry-defer-index-fast | carry-defer-index-standard | carry-defer-path-fast | carry-defer-path-standard | B1-mecab | B2-mecab | B1-bigram | B2-bigram |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| I2-011 | 改称 | x7 | x3 | x9 | x6 | x10 | x8 | - | - | - | - | - | - | - | - | x3 | x5 | w | w |
| I2-014 | 九曜紋 | L5 | L5 | L6 | L11 | L6 | L22 | - | - | - | - | - | - | - | - | w | x2 | w | x2 |
| I2-029 | 和歌山千葉線 | L9 | L12 | L9 | L16 | L10 | L23 | - | L39 | - | - | - | L15 | - | - | w | x2 | w | x2 |
| I2-031 | USB|イーサネット|LXI | - | x37 | - | x41 | w | x53 | - | - | - | - | - | - | - | w | w | x2 | w | x2 |
| I2-033 | リュカーオーン | - | - | - | - | w | x11 | - | - | - | - | - | - | - | - | w | w | w | x2 |
| I2-039 | 愛知県 | w | x3 | x2 | x11 | x3 | x32 | - | w | - | - | x10 | x10 | - | - | w | x2 | w | x2 |
| R2-I003 | 中播磨県民センター | x8 | x12 | x9 | x15 | x9 | x28 | - | w | - | - | w | w | - | - | w | x2 | w | x2 |
| R2-I006 | 120 m|120 | - | w | - | x9 | w | x16 | - | x4 | - | - | w | x4 | - | - | w | x2 | w | x2 |
| R2-I013 | ネパール | w | x2 | w | x6 | x2 | x8 | - | - | - | - | - | - | - | - | w | x2 | w | x2 |

## System vs B2 (MeCab), answerable questions: overlap of 'gold in a candidate'

both = system and B2 hit; system only; B2 only; neither. Per kind. (B2-bigram in the last column: system hits that B2-bigram also misses = gold neither B2 holds.)

| system | kind | n | both | system only | B2 only | neither | system-only ids | system hit, both B2 tokenizers miss |
|---|---|---|---|---|---|---|---|---|
| flat-fast | intra2 | 69 | 4 | 3 | 53 | 9 | I2-014,I2-029,I2-037 | I2-014,I2-029 |
| flat-fast | cross2 | 9 | 0 | 0 | 8 | 1 | - | - |
| flat-standard | intra2 | 69 | 6 | 3 | 51 | 9 | I2-014,I2-029,I2-037 | I2-014,I2-029 |
| flat-standard | cross2 | 9 | 0 | 0 | 8 | 1 | - | - |
| layers-path-fast | intra2 | 69 | 4 | 3 | 53 | 9 | I2-014,I2-029,I2-037 | I2-014,I2-029 |
| layers-path-fast | cross2 | 9 | 0 | 0 | 8 | 1 | - | - |
| layers-path-standard | intra2 | 69 | 6 | 4 | 51 | 8 | I2-014,I2-029,I2-037,R2-I020 | I2-014,I2-029 |
| layers-path-standard | cross2 | 9 | 0 | 0 | 8 | 1 | - | - |
| layers-ssp-fast | intra2 | 69 | 6 | 3 | 51 | 9 | I2-014,I2-029,I2-037 | I2-014,I2-029 |
| layers-ssp-fast | cross2 | 9 | 0 | 0 | 8 | 1 | - | - |
| layers-ssp-standard | intra2 | 69 | 12 | 4 | 45 | 8 | I2-014,I2-029,I2-037,R2-I020 | I2-014,I2-029 |
| layers-ssp-standard | cross2 | 9 | 0 | 0 | 8 | 1 | - | - |
| carry-close-index-fast | intra2 | 69 | 0 | 0 | 57 | 12 | - | - |
| carry-close-index-fast | cross2 | 9 | 0 | 0 | 8 | 1 | - | - |
| carry-close-index-standard | intra2 | 69 | 6 | 1 | 51 | 11 | I2-029 | I2-029 |
| carry-close-index-standard | cross2 | 9 | 0 | 0 | 8 | 1 | - | - |
| carry-close-path-fast | intra2 | 69 | 0 | 0 | 57 | 12 | - | - |
| carry-close-path-fast | cross2 | 9 | 0 | 0 | 8 | 1 | - | - |
| carry-close-path-standard | intra2 | 69 | 0 | 0 | 57 | 12 | - | - |
| carry-close-path-standard | cross2 | 9 | 0 | 0 | 8 | 1 | - | - |
| carry-defer-index-fast | intra2 | 69 | 0 | 0 | 57 | 12 | - | - |
| carry-defer-index-fast | cross2 | 9 | 0 | 0 | 8 | 1 | - | - |
| carry-defer-index-standard | intra2 | 69 | 9 | 1 | 48 | 11 | I2-029 | I2-029 |
| carry-defer-index-standard | cross2 | 9 | 1 | 0 | 7 | 1 | - | - |
| carry-defer-path-fast | intra2 | 69 | 0 | 0 | 57 | 12 | - | - |
| carry-defer-path-fast | cross2 | 9 | 0 | 0 | 8 | 1 | - | - |
| carry-defer-path-standard | intra2 | 69 | 1 | 1 | 56 | 11 | R2-I020 | - |
| carry-defer-path-standard | cross2 | 9 | 0 | 0 | 8 | 1 | - | - |
| B1-mecab | intra2 | 69 | 47 | 0 | 10 | 12 | - | - |
| B1-mecab | cross2 | 9 | 2 | 0 | 6 | 1 | - | - |

## Normalisation effect

Items where a system's gold hit exists only after normalisation (verbatim words do not hold the gold):

- flat-fast: none
- flat-standard: none
- layers-path-fast: none
- layers-path-standard: none
- layers-ssp-fast: none
- layers-ssp-standard: none
- carry-close-index-fast: none
- carry-close-index-standard: none
- carry-close-path-fast: none
- carry-close-path-standard: none
- carry-defer-index-fast: none
- carry-defer-index-standard: none
- carry-defer-path-fast: none
- carry-defer-path-standard: none

## Diagnostic: looser rule (gold inside the concatenation of ALL words of one entry), answerable questions

Not the headline rule (the concatenation of a word set is not text of the corpus); shown to see whether the word-level rule hides hits for multi-word golds.

| system | intra2 word-level -> joined | cross2 word-level -> joined |
|---|---|---|
| flat-fast | 7 -> 8 (of 69) | 0 -> 0 (of 9) |
| flat-standard | 9 -> 10 (of 69) | 0 -> 0 (of 9) |
| layers-path-fast | 7 -> 8 (of 69) | 0 -> 0 (of 9) |
| layers-path-standard | 10 -> 11 (of 69) | 0 -> 0 (of 9) |
| layers-ssp-fast | 9 -> 11 (of 69) | 0 -> 1 (of 9) |
| layers-ssp-standard | 16 -> 18 (of 69) | 0 -> 1 (of 9) |
| carry-close-index-fast | 0 -> 0 (of 69) | 0 -> 0 (of 9) |
| carry-close-index-standard | 7 -> 7 (of 69) | 0 -> 0 (of 9) |
| carry-close-path-fast | 0 -> 0 (of 69) | 0 -> 0 (of 9) |
| carry-close-path-standard | 0 -> 0 (of 69) | 0 -> 0 (of 9) |
| carry-defer-index-fast | 0 -> 0 (of 69) | 0 -> 0 (of 9) |
| carry-defer-index-standard | 10 -> 10 (of 69) | 1 -> 1 (of 9) |
| carry-defer-path-fast | 0 -> 0 (of 69) | 0 -> 0 (of 9) |
| carry-defer-path-standard | 2 -> 2 (of 69) | 0 -> 0 (of 9) |

