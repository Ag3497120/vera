# T11 -- bank3 fulllead through ask(structure="combined"), fast

Records: 76 questions (two-facts 14/14, paraphrase 20/20, unknown-word 18/18, summary-choice 10/10, unans-kind 14/14); worker errors: 0. s3000 items (compare 14, unans-kind 1) are NOT run: they need an S3000 ordered cache that does not exist.
Code: snapshot of line3 HEAD 2ef8531f (see README for md5s).

## Per kind (gold = any gold alternative in a candidate word of ONE entry, t9 scorer; summary-choice: the option text after 'LETTER|')

| kind | n | gold in a candidate | single right / wrong | list with gold / without | no candidate | list size median / mean / max (lists >= 2) | first-gold position overall median / max | within its block median / max | B1 mecab / bigram | B2 mecab / bigram |
|---|---|---|---|---|---|---|---|---|---|---|
| two-facts | 14 | 4 (29%) | 0 / 0 | 4 / 10 | 0 | 13.5 / 24.4 / 116 | 7.5 / 43 | 1.5 / 2 | 3 (21%) / 1 (7%) | 8 (57%) / 6 (43%) |
| paraphrase | 20 | 3 (15%) | 0 / 0 | 3 / 17 | 0 | 40.5 / 51.4 / 184 | 11.0 / 34 | 1.0 / 1 | 8 (40%) / 6 (30%) | 12 (60%) / 10 (50%) |
| unknown-word | 18 | 6 (33%) | 0 / 0 | 6 / 12 | 0 | 46.5 / 51.5 / 142 | 3.5 / 73 | 1.0 / 68 | 16 (89%) / 14 (78%) | 16 (89%) / 15 (83%) |
| summary-choice | 10 | 1 (10%) | 0 / 0 | 1 / 9 | 0 | 62.0 / 107.7 / 243 | 1.0 / 1 | 1.0 / 1 | option-lookup 9.0/10 (mecab), 9.5/10 (bigram) | - |

**Comparability.** The grade above is the t9 rule: the gold must sit inside ONE WORD of an entry (entries are sets of short corpus words). The baselines B1/B2 are graded 'gold in a candidate SENTENCE' (a far easier unit for phrase golds such as 鳳珠郡能登町 or a whole option text), and return 1-3 sentences, whereas a combined list has tens of entries. So the table is NOT apples to apples; the nearer comparison is the looser sentence-citing table below (gold in a sentence cited by a flat or window entry), which is still a list of tens against B1/B2's 1-3 sentences.

**unans-kind (fulllead, n = 14)**: abstained (no candidate) 0 / list 14 / single (ANSWER, wrong by definition) 0; list size median 42.5 max 192. B1/B2 baseline: candidates returned for every one (keyword lookup never abstains, mecab 14/14).

unknown-word extra baseline: B1 after NFKC + MeCab-reading normalisation 17/18 (94%) mecab, 14/18 bigram (baselines.txt).

summary-choice: **the model cannot pick the letter** -- ask() returns candidate word sets from the corpus (no option is scored, no letter is produced), so 'letter correct' is not defined for any system here. The hit above only says the gold option's text is in a candidate. Discrimination (the user sees the options in the question and could compare): see the per-item rows below; a candidate that also holds a wrong option's text does not discriminate.

## Gold per origin (questions whose list holds the gold in an entry of that origin)

| kind | n | any | flat | layers | windows | flat/RUN | flat/WORD | flat/CHAR | layers | window/plain | window/window-evidence | only windows (no flat/layers entry holds it) | only flat (no layers/window) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| two-facts | 14 | 4 | 1 | 3 | 3 | 1 | 0 | 0 | 3 | 1 | 3 | 0 | 1 |
| paraphrase | 20 | 3 | 1 | 2 | 1 | 1 | 1 | 0 | 2 | 0 | 1 | 1 | 0 |
| unknown-word | 18 | 6 | 4 | 3 | 3 | 4 | 1 | 0 | 3 | 1 | 3 | 2 | 1 |
| summary-choice | 10 | 1 | 1 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |

## Looser view: the sentences an entry CITES (source_sids), not its words (flat and windows only)

The primary grade needs the gold inside ONE word of an entry; entries are sets of short corpus words (a phrase gold such as 鳳珠郡能登町 is rarely one word), so a list can point at the evidence sentence without holding the gold string. Here: 'gold in a cited sentence' = a gold alternative is a substring of a sentence cited by some entry of the family (t9 normalisation); 'evidence cited' = some entry cites a sentence of the bank's evidence column; 'all evidence' = every evidence sentence is cited (flat or windows union). NOT the t9 rule; for reading the headroom only. The layers are left out: each layers entry cites a corpus-wide union (median ~255 of 592 sentences), so citing says nothing there.

| kind | n | gold in a cited sentence: flat | windows | flat or windows | evidence cited: flat | windows | flat or windows | all evidence cited (flat+windows) | distinct sentences cited per question flat / windows: median, max |
|---|---|---|---|---|---|---|---|---|---|
| two-facts | 14 | 5 | 6 | 8 | 9 | 8 | 12 | 6 | 6.0, 183 / 2.5, 5 |
| paraphrase | 20 | 10 | 5 | 11 | 8 | 5 | 10 | 10 | 4.0, 210 / 1.5, 7 |
| unknown-word | 18 | 10 | 8 | 13 | 10 | 8 | 13 | 13 | 3.0, 14 / 2.5, 6 |
| summary-choice | 10 | 4 | 4 | 5 | 8 | 6 | 9 | 9 | 8.5, 191 / 2.0, 6 |

## Verdict and list shape per kind

| kind | n | ANSWER | CHOICE | UNKNOWN (no candidate) | entries total median / max | entries per block (median over questions that list it) |
|---|---|---|---|---|---|---|
| two-facts | 14 | 0 | 14 | 0 | 13.5 / 116 | flat/RUN 5.0 (11 q); flat/WORD 5.0 (9 q); flat/CHAR 7.0 (1 q); layers 3.0 (14 q); w/plain 1.5 (8 q); w/window-evidence 3.0 (12 q) |
| paraphrase | 20 | 0 | 20 | 0 | 40.5 / 184 | flat/RUN 39.0 (17 q); flat/WORD 16.5 (14 q); flat/CHAR 1.0 (2 q); layers 3.0 (19 q); w/plain 2.0 (8 q); w/window-evidence 2.0 (10 q) |
| unknown-word | 18 | 0 | 18 | 0 | 46.5 / 142 | flat/RUN 40.0 (15 q); flat/WORD 14.5 (12 q); flat/CHAR - (0 q); layers 2.5 (16 q); w/plain 2.0 (8 q); w/window-evidence 4.0 (13 q) |
| summary-choice | 10 | 0 | 10 | 0 | 62.0 / 243 | flat/RUN 63.5 (8 q); flat/WORD 28.0 (8 q); flat/CHAR 8.0 (2 q); layers 3.5 (10 q); w/plain 2.0 (5 q); w/window-evidence 7.0 (6 q) |
| unans-kind | 14 | 0 | 14 | 0 | 42.5 / 192 | flat/RUN 11.5 (14 q); flat/WORD 7.0 (9 q); flat/CHAR 29.0 (1 q); layers 4.0 (13 q); w/plain 2.0 (5 q); w/window-evidence 3.0 (9 q) |

## Per item: paraphrase (the kind with headroom: B1/B2 30-60%)

| id | B1 m/b | B2 m/b | verdict | entries | per block (RUN/WORD/CHAR/lay/wP/wE) | gold | first gold: pos (block, in-block) | blocks holding gold | gold in a cited sentence / evidence cited (flat+windows) | s |
|---|---|---|---|---|---|---|---|---|---|---|
| b3_pa01 | 0/0 | 0/0 | CHOICE | 45 | 43/0/0/1/1/0 | list, no gold | - | - | yes / yes | 126 |
| b3_pa02 | 0/0 | 0/0 | CHOICE | 15 | 13/0/0/2/0/0 | list, no gold | - | - | yes / yes | 384 |
| b3_pa03 | 1/1 | 1/1 | CHOICE | 59 | 39/16/1/3/0/0 | list, no gold | - | - | no / no | 388 |
| b3_pa04 | 0/0 | 0/0 | CHOICE | 45 | 39/4/0/2/0/0 | list, no gold | - | - | no / no | 577 |
| b3_pa05 | 1/1 | 1/1 | CHOICE | 114 | 88/24/0/2/0/0 | list+gold | 1 (flat/RUN, 1) | flat/RUN, flat/WORD, layers | yes / no | 966 |
| b3_pa06 | 0/0 | 1/1 | CHOICE | 9 | 1/0/0/4/2/2 | list, no gold | - | - | yes / yes | 533 |
| b3_pa07 | 1/1 | 1/1 | CHOICE | 77 | 65/0/0/1/2/9 | list, no gold | - | - | yes / yes | 382 |
| b3_pa08 | 0/0 | 0/0 | CHOICE | 68 | 54/9/0/4/0/1 | list, no gold | - | - | no / no | 463 |
| b3_pa09 | 0/0 | 0/0 | CHOICE | 99 | 69/17/0/12/0/1 | list, no gold | - | - | yes / yes | 1165 |
| b3_pa10 | 1/1 | 1/1 | CHOICE | 66 | 63/0/0/3/0/0 | list, no gold | - | - | no / no | 901 |
| b3_pa11 | 0/0 | 0/0 | CHOICE | 51 | 30/18/0/3/0/0 | list, no gold | - | - | no / no | 719 |
| b3_pa12 | 0/0 | 1/1 | CHOICE | 16 | 6/3/0/0/3/4 | list, no gold | - | - | no / no | 77 |
| b3_pa13 | 0/0 | 0/0 | CHOICE | 17 | 8/2/0/4/1/2 | list, no gold | - | - | no / no | 275 |
| b3_pa14 | 1/0 | 1/0 | CHOICE | 12 | 1/6/1/4/0/0 | list, no gold | - | - | no / no | 583 |
| b3_pa15 | 0/0 | 1/0 | CHOICE | 36 | 0/28/0/6/1/1 | list, no gold | - | - | no / no | 736 |
| b3_pa16 | 1/1 | 1/1 | CHOICE | 36 | 0/34/0/2/0/0 | list, no gold | - | - | yes / yes | 950 |
| b3_pa17 | 0/0 | 1/1 | CHOICE | 20 | 10/0/0/2/6/2 | list+gold | 11 (layers, 1) | layers | yes / yes | 1017 |
| b3_pa18 | 0/0 | 0/0 | CHOICE | 24 | 8/2/0/5/4/5 | list, no gold | - | - | yes / yes | 782 |
| b3_pa19 | 1/1 | 1/1 | CHOICE | 184 | 62/117/0/5/0/0 | list, no gold | - | - | yes / yes | 1708 |
| b3_pa20 | 1/0 | 1/1 | CHOICE | 35 | 0/31/0/2/0/2 | list+gold | 34 (window/window-evidence, 1) | w/window-evidence | yes / yes | 627 |

## Per item: two-facts

| id | B1 m/b | B2 m/b | verdict | entries | per block (RUN/WORD/CHAR/lay/wP/wE) | gold | first gold: pos (block, in-block) | blocks holding gold | gold in a cited sentence / evidence cited (flat+windows) | s |
|---|---|---|---|---|---|---|---|---|---|---|
| b3_tf01 | 0/0 | 0/0 | CHOICE | 15 | 5/0/7/3/0/0 | list, no gold | - | - | no / yes | 468 |
| b3_tf04 | 0/0 | 1/1 | CHOICE | 40 | 28/5/0/3/3/1 | list, no gold | - | - | yes / yes | 409 |
| b3_tf07 | 1/0 | 1/0 | CHOICE | 23 | 9/1/0/7/3/3 | list, no gold | - | - | no / yes | 321 |
| b3_tf08 | 0/0 | 0/0 | CHOICE | 11 | 1/7/0/1/0/2 | list+gold | 1 (flat/RUN, 1) | flat/RUN | yes / yes | 361 |
| b3_tf09 | 0/0 | 0/0 | CHOICE | 6 | 1/0/0/2/1/2 | list, no gold | - | - | yes / yes | 437 |
| b3_tf10 | 0/0 | 0/0 | CHOICE | 45 | 1/41/0/2/0/1 | list+gold | 43 (layers, 1) | layers, w/window-evidence | yes / yes | 339 |
| b3_tf11 | 0/0 | 1/1 | CHOICE | 116 | 98/0/0/3/1/14 | list, no gold | - | - | yes / yes | 354 |
| b3_tf12 | 1/0 | 1/1 | CHOICE | 22 | 11/2/0/5/0/4 | list, no gold | - | - | yes / yes | 884 |
| b3_tf13 | 1/0 | 1/0 | CHOICE | 14 | 1/5/0/3/0/5 | list+gold | 8 (layers, 2) | layers, w/window-evidence | yes / yes | 383 |
| b3_tf14 | 0/1 | 1/1 | CHOICE | 13 | 5/0/0/3/2/3 | list+gold | 7 (layers, 2) | layers, w/plain, w/window-evidence | yes / yes | 467 |
| b3_tf15 | 0/0 | 1/1 | CHOICE | 8 | 0/3/0/1/1/3 | list, no gold | - | - | no / no | 415 |
| b3_tf16 | 0/0 | 0/0 | CHOICE | 13 | 0/6/0/3/2/2 | list, no gold | - | - | no / yes | 557 |
| b3_tf19 | 0/0 | 1/1 | CHOICE | 4 | 0/3/0/1/0/0 | list, no gold | - | - | no / yes | 738 |
| b3_tf20 | 0/0 | 0/0 | CHOICE | 12 | 6/0/0/2/1/3 | list, no gold | - | - | no / no | 444 |

## Per item: unknown-word

| id | B1 m/b | B2 m/b | verdict | entries | per block (RUN/WORD/CHAR/lay/wP/wE) | gold | first gold: pos (block, in-block) | blocks holding gold | gold in a cited sentence / evidence cited (flat+windows) | s |
|---|---|---|---|---|---|---|---|---|---|---|
| b3_uw01 | 1/1 | 1/1 | CHOICE | 49 | 40/0/0/1/2/6 | list, no gold | - | - | no / no | 833 |
| b3_uw02 | 1/1 | 1/1 | CHOICE | 77 | 37/27/0/5/4/4 | list+gold | 73 (window/plain, 4) | w/plain, w/window-evidence | yes / yes | 569 |
| b3_uw03 | 1/1 | 1/1 | CHOICE | 63 | 43/9/0/1/5/5 | list, no gold | - | - | yes / yes | 383 |
| b3_uw04 | 1/0 | 1/0 | CHOICE | 28 | 22/0/0/4/0/2 | list, no gold | - | - | yes / yes | 321 |
| b3_uw06 | 0/1 | 0/1 | CHOICE | 55 | 40/0/0/6/3/6 | list, no gold | - | - | yes / yes | 672 |
| b3_uw07 | 1/1 | 1/1 | CHOICE | 15 | 7/0/0/1/2/5 | list, no gold | - | - | no / no | 378 |
| b3_uw08 | 1/0 | 1/0 | CHOICE | 37 | 35/0/0/2/0/0 | list, no gold | - | - | no / no | 1390 |
| b3_uw09 | 1/1 | 1/1 | CHOICE | 90 | 69/19/0/0/1/1 | list, no gold | - | - | yes / yes | 311 |
| b3_uw10 | 1/1 | 1/1 | CHOICE | 103 | 91/9/0/3/0/0 | list, no gold | - | - | no / no | 1137 |
| b3_uw11 | 1/1 | 1/1 | CHOICE | 18 | 0/1/0/1/1/15 | list, no gold | - | - | yes / yes | 155 |
| b3_uw13 | 1/0 | 1/1 | CHOICE | 7 | 0/3/0/2/0/2 | list+gold | 6 (window/window-evidence, 1) | w/window-evidence | yes / yes | 793 |
| b3_uw14 | 0/0 | 0/0 | CHOICE | 53 | 31/15/0/5/0/2 | list, no gold | - | - | no / no | 670 |
| b3_uw15 | 1/1 | 1/1 | CHOICE | 44 | 43/0/0/1/0/0 | list+gold | 1 (flat/RUN, 1) | flat/RUN | yes / yes | 493 |
| b3_uw16 | 1/1 | 1/1 | CHOICE | 142 | 112/18/0/12/0/0 | list+gold | 68 (flat/RUN, 68) | flat/RUN, layers | yes / yes | 996 |
| b3_uw17 | 1/1 | 1/1 | CHOICE | 21 | 9/2/0/5/0/5 | list, no gold | - | - | yes / yes | 398 |
| b3_uw18 | 1/1 | 1/1 | CHOICE | 14 | 0/14/0/0/0/0 | list, no gold | - | - | yes / yes | 454 |
| b3_uw19 | 1/1 | 1/1 | CHOICE | 75 | 41/18/0/15/0/1 | list+gold | 1 (flat/RUN, 1) | flat/RUN, layers | yes / yes | 693 |
| b3_uw20 | 1/1 | 1/1 | CHOICE | 36 | 7/23/0/1/1/4 | list+gold | 1 (flat/RUN, 1) | flat/RUN, flat/WORD, layers, w/window-evidence | yes / yes | 650 |

## Per item: summary-choice

| id | gold | options whose text is in some candidate | B-option-lookup m/b | verdict | entries | gold option in a candidate (blocks) |
|---|---|---|---|---|---|---|
| b3_sc01 | B | - | 1.00/1.00 | CHOICE | 20 | - |
| b3_sc02 | C | - | 0.50/1.00 | CHOICE | 50 | - |
| b3_sc03 | A | - | 1.00/1.00 | CHOICE | 12 | - |
| b3_sc04 | B | - | 1.00/1.00 | CHOICE | 227 | - |
| b3_sc05 | C | - | 1.00/1.00 | CHOICE | 52 | - |
| b3_sc06 | B | - | 1.00/1.00 | CHOICE | 72 | - |
| b3_sc07 | A | - | 0.50/0.50 | CHOICE | 12 | - |
| b3_sc08 | B | B | 1.00/1.00 | CHOICE | 189 | flat/RUN, window/window-evidence |
| b3_sc09 | C | - | 1.00/1.00 | CHOICE | 200 | - |
| b3_sc10 | A | - | 1.00/1.00 | CHOICE | 243 | - |

Items where only the gold option's text is in a candidate: 1 / 10. The letter is never produced.

## Per item: unans-kind

| id | outcome | entries | per block (RUN/WORD/CHAR/lay/wP/wE) | what is missing (bank notes) | mecab B1 returned |
|---|---|---|---|---|---|
| b3_uk01 | list | 87 | 45/38/0/4/0/0 | 本文には計算量の記載がない | 2 |
| b3_uk02 | list | 51 | 1/41/0/4/1/4 | 複数文を結ぶ形だが結成年は本文にない | 3 |
| b3_uk03 | list | 36 | 13/17/0/5/0/1 | 未知語型の表面、関数名は本文にない | 1 |
| b3_uk04 | list | 17 | 7/0/0/10/0/0 | 起源国の記載がない | 2 |
| b3_uk06 | list | 192 | 181/8/0/1/0/2 | 選択肢の事実はいずれも本文から判定できない | 1 |
| b3_uk07 | list | 49 | 40/0/0/1/2/6 | 来日公演の記載がない | 6 |
| b3_uk08 | list | 7 | 3/0/0/3/0/1 | 二文を組み合わせる形式、得点は記載されない | 1 |
| b3_uk09 | list | 20 | 10/0/0/2/6/2 | 存続していた期間の終期は記載されない | 1 |
| b3_uk10 | list | 12 | 7/2/0/3/0/0 | 月までの記載にとどまり日付はない | 37 |
| b3_uk11 | list | 50 | 13/3/29/5/0/0 | 時刻の記載がない | 4 |
| b3_uk12 | list | 71 | 51/7/0/8/2/3 | 選択肢の情報は本文にない | 1 |
| b3_uk13 | list | 108 | 108/0/0/0/0/0 | 電力の記載がない | 1 |
| b3_uk14 | list | 11 | 1/3/0/3/0/4 | 旧社格はあるが指定年は記載されない | 1 |
| b3_uk15 | list | 21 | 5/5/0/5/2/4 | 比較型、参加国数はどちらの文にも記載されない | 1 |

## Per-source header: how many sources list something, answerable (62) against unans-kind (14)

| source | answerable: listed | unans-kind: listed | typed abstentions when not listed (answerable / unans) |
|---|---|---|---|
| flat/RUN | 51 / 62 | 14 / 14 | AMBIGUOUS 1, UNKNOWN_NO_FIXED_POINT 9, UNKNOWN_RATIO_DISAGREEMENT 1 / - |
| flat/WORD | 43 / 62 | 9 / 14 | AMBIGUOUS 4, UNKNOWN_NO_FIXED_POINT 13, UNKNOWN_SECTION_DISAGREEMENT 2 / AMBIGUOUS 1, UNKNOWN_NO_FIXED_POINT 1, UNKNOWN_RATIO_DISAGREEMENT 1, UNKNOWN_SECTION_DISAGREEMENT 2 |
| flat/CHAR | 5 / 62 | 1 / 14 | UNKNOWN_NO_FIXED_POINT 57 / UNKNOWN_NO_FIXED_POINT 13 |
| layers | 59 / 62 | 13 / 14 | UNKNOWN_NO_EVIDENCE 1, UNKNOWN_NO_FIXED_POINT 2 / UNKNOWN_NO_EVIDENCE 1 |
| window/plain | 29 / 62 | 5 / 14 | AMBIGUOUS 4, UNKNOWN_NOT_READ 6, UNKNOWN_NO_FIXED_POINT 19, UNKNOWN_NO_WINDOW 1, UNKNOWN_RATIO_DISAGREEMENT 3 / AMBIGUOUS 1, UNKNOWN_NOT_READ 1, UNKNOWN_NO_FIXED_POINT 4, UNKNOWN_NO_WINDOW 2, UNKNOWN_SECTION_DISAGREEMENT 1 |
| window/window-evidence | 41 / 62 | 9 / 14 | AMBIGUOUS 2, UNKNOWN_NOT_READ 6, UNKNOWN_NO_FIXED_POINT 11, UNKNOWN_NO_WINDOW 1, UNKNOWN_RATIO_DISAGREEMENT 1 / UNKNOWN_NOT_READ 1, UNKNOWN_NO_FIXED_POINT 2, UNKNOWN_NO_WINDOW 2 |

unans-kind questions where EVERY source lists nothing: 0 / 14; where at least one source abstains with a type: 14 / 14.

## Time (fast)

seconds per question (end to end ask(structure="combined"), several questions in parallel on a loaded machine): median 669, mean 696, max 1907, total CPU-ish sum 52883 s over 76 questions; 1-min load at the question ends: median 20.1, max 46.1.

