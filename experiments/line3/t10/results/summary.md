# T10 -- bank2 under the new initial placement (ordered group insertion), measured on Vera line 3, with the t9 rows and keyword baselines

Systems: `flat-P [tag]` = layers off (ask, 3 tiers, preset P); `layers-path-P [tag]` = layers on, default path candidates; `layers-ssp-P [tag]` = layers on, stable-seats-path; tag `ordered-stop` = the T10 placement (group_insert-on_collapse; `ordered-stop` = tied share-groups inserted one member at a time in sentence word order, growth stops just before the member that breaks the budget, L-460..L-463); tag `t9 whole` = the T9 sweep with the whole-group insertion (L-72), copied from t9/results/summary.md's configs (same questions, same scorer; recomputed here from t9's raw per-question records, so the numbers equal t9/results/summary.md). Placement cache = the complete ordered cache of fulllead_sents (level mid); presets fast / standard; layers variant A, compress, no feedback.

Grading (as t9): `scorer.py` (NFKC, casefold, no spaces / thousands commas / middle dots, 万 and kanji digits to ASCII; gold alternative a substring of ONE word of an entry; for B1/B2 a candidate is one sentence). 'Gold in a candidate' = any candidate holds the gold. Single right / wrong = exactly one candidate holds / does not hold the gold; list = >= 2 candidates; none = no candidate. List size = number of candidates (entries over the 3 tiers + upper-layer entries). B1/B2 = baselines.py with MeCab ('-mecab') and character bigrams ('-bigram').

Times: wall seconds per question inside a worker. T10: 4 workers on a shared MacBook Air (the 1-min load at each question's finish is in the time table); t9: 4 workers on another machine and load (5-15). Times of the two sweeps are therefore NOT comparable; they only show the order of magnitude. In T10 the layers configs run on top of ONE layer-0 read and the first config (`ssp`) builds the layer-1 reads that the second (`path`) finds cached on the index, so the `layers-path` seconds of T10 are layer 0 + the extra of a WARM second config; the `layers-ssp` seconds are the cold cost. Tower build time is not included.

## intra2 (fulllead, n = 69)

| system | n run | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size median / max (lists) | first-gold pos median / max | s/question median (max) | trace ok |
|---|---|---|---|---|---|---|---|---|---|---|---|
| flat-fast [ordered-stop] | 69 | 16 (23%) | 0 | 2 | 16 | 49 | 2 | 26.0 / 141 | 1.0 / 38 | 165.95 (413.56) | n/a |
| flat-fast [t9 whole] | 69 | 7 (10%) | 0 | 16 | 7 | 36 | 10 | 5.0 / 21 | 1.0 / 2 | 6.11 (23.98) | n/a |
| layers-path-fast [ordered-stop] | 69 | 18 (26%) | 0 | 2 | 18 | 47 | 2 | 27.0 / 143 | 1.0 / 38 | 271.41 (634.18) | 69/69 |
| layers-path-fast [t9 whole] | 69 | 7 (10%) | 0 | 6 | 7 | 46 | 10 | 6.0 / 21 | 1.0 / 2 | 15.80 (44.24) | 69/69 |
| layers-ssp-fast [ordered-stop] | 69 | 21 (30%) | 0 | 0 | 21 | 46 | 2 | 28.0 / 146 | 2.0 / 82 | 294.72 (749.79) | 69/69 |
| layers-ssp-fast [t9 whole] | 69 | 9 (13%) | 0 | 11 | 9 | 48 | 1 | 6.0 / 24 | 2.0 / 3 | 18.53 (48.23) | 69/69 |
| B1-mecab | 69 | 47 (68%) | 31 | 18 | 16 | 4 | 0 | 2.0 / 34 | 1.0 / 8 | - (-) | n/a |
| B2-mecab | 69 | 57 (83%) | 20 | 2 | 37 | 10 | 0 | 2.0 / 42 | 1.0 / 12 | - (-) | n/a |
| B1-bigram | 69 | 38 (55%) | 30 | 29 | 8 | 2 | 0 | 2.0 / 5 | 1.0 / 5 | - (-) | n/a |
| B2-bigram | 69 | 54 (78%) | 19 | 2 | 35 | 13 | 0 | 2.0 / 5 | 1.0 / 5 | - (-) | n/a |

## unans (fulllead): can a user reject what is shown?

Correct behaviour = abstain. B1/B2 never abstain (candidates for every question). 'list only' = rejectable by a user; 'single answer' = confident wrong.

| system | corpus | n run | no candidate (abstained) | list only (rejectable) | single answer (confident wrong) | list size median / max |
|---|---|---|---|---|---|---|
| flat-fast [ordered-stop] | fulllead | 25 | 1 | 23 | 1 | 37.0 / 258 |
| flat-fast [t9 whole] | fulllead | 25 | 5 | 16 | 4 | 3.0 / 18 |
| layers-path-fast [ordered-stop] | fulllead | 25 | 1 | 23 | 1 | 37.0 / 262 |
| layers-path-fast [t9 whole] | fulllead | 25 | 5 | 17 | 3 | 4.0 / 19 |
| layers-ssp-fast [ordered-stop] | fulllead | 25 | 0 | 24 | 1 | 37.5 / 264 |
| layers-ssp-fast [t9 whole] | fulllead | 25 | 2 | 20 | 3 | 4.5 / 21 |
| B1-mecab | fulllead | 25 | 0 | 13 | 12 | 3.0 / 52 |
| B2-mecab | fulllead | 25 | 0 | 24 | 1 | 2.5 / 68 |
| B1-bigram | fulllead | 25 | 0 | 6 | 19 | 2.5 / 54 |
| B2-bigram | fulllead | 25 | 0 | 23 | 2 | 2.0 / 78 |

## The 9 B2-hard items (missed by B2 with both tokenizers), per system

Cell: S = single answer holds gold; Ln = list of n holds gold; w = single answer without gold; xn = list of n without gold; - = no candidate; . = not run. B1/B2 cells: S/Ln as for a sentence list (n = number of sentences).

| item | gold | flat-fast [ordered-stop] | flat-fast [t9 whole] | layers-path-fast [ordered-stop] | layers-path-fast [t9 whole] | layers-ssp-fast [ordered-stop] | layers-ssp-fast [t9 whole] | B1-mecab | B2-mecab | B1-bigram | B2-bigram |
|---|---|---|---|---|---|---|---|---|---|---|---|
| I2-011 | 改称 | x9 | x7 | x10 | x9 | x10 | x10 | x3 | x5 | w | w |
| I2-014 | 九曜紋 | L4 | L5 | L4 | L6 | L4 | L6 | w | x2 | w | x2 |
| I2-029 | 和歌山千葉線 | L29 | L9 | L30 | L9 | L31 | L10 | w | x2 | w | x2 |
| I2-031 | USB|イーサネット|LXI | x78 | - | x79 | - | L82 | w | w | x2 | w | x2 |
| I2-033 | リュカーオーン | x21 | - | x23 | - | x25 | w | w | w | w | x2 |
| I2-039 | 愛知県 | - | w | - | x2 | - | x3 | w | x2 | w | x2 |
| R2-I003 | 中播磨県民センター | x16 | x8 | x17 | x9 | x18 | x9 | w | x2 | w | x2 |
| R2-I006 | 120 m|120 | x32 | - | x33 | - | x38 | w | w | x2 | w | x2 |
| R2-I013 | ネパール | L5 | w | L5 | w | L7 | x2 | w | x2 | w | x2 |

## System vs B2 (MeCab), answerable questions: overlap of 'gold in a candidate'

both = system and B2 hit; system only; B2 only; neither. Per kind. (Last column: system hits that B2-bigram also misses = gold neither B2 holds.)

| system | kind | n | both | system only | B2 only | neither | system-only ids | system hit, both B2 tokenizers miss |
|---|---|---|---|---|---|---|---|---|
| flat-fast [ordered-stop] | intra2 | 69 | 13 | 3 | 44 | 9 | I2-014,I2-029,R2-I013 | I2-014,I2-029,R2-I013 |
| flat-fast [t9 whole] | intra2 | 69 | 4 | 3 | 53 | 9 | I2-014,I2-029,I2-037 | I2-014,I2-029 |
| layers-path-fast [ordered-stop] | intra2 | 69 | 14 | 4 | 43 | 8 | I2-014,I2-029,R2-I013,R2-I020 | I2-014,I2-029,R2-I013 |
| layers-path-fast [t9 whole] | intra2 | 69 | 4 | 3 | 53 | 9 | I2-014,I2-029,I2-037 | I2-014,I2-029 |
| layers-ssp-fast [ordered-stop] | intra2 | 69 | 15 | 6 | 42 | 6 | I2-014,I2-029,I2-031,I2-037,R2-I013,R2-I020 | I2-014,I2-029,I2-031,R2-I013 |
| layers-ssp-fast [t9 whole] | intra2 | 69 | 6 | 3 | 51 | 9 | I2-014,I2-029,I2-037 | I2-014,I2-029 |
| B1-mecab | intra2 | 69 | 47 | 0 | 10 | 12 | - | - |

## T10 vs t9, same config: which answerable questions changed 'gold in a candidate'

gained = hit under T10, no hit in t9; lost = hit in t9, none under T10.

| config | kind | n | t9 hits | T10 hits | gained | lost | gained ids | lost ids |
|---|---|---|---|---|---|---|---|---|
| flat-fast [ordered-stop] | intra2 | 69 | 7 | 16 | 11 | 2 | I2-010,I2-012,I2-013,I2-017,I2-021,I2-032,I2-035,I2-048,R2-I010,R2-I013,R2-I015 | I2-037,I2-042 |
| layers-path-fast [ordered-stop] | intra2 | 69 | 7 | 18 | 13 | 2 | I2-010,I2-012,I2-013,I2-017,I2-021,I2-022,I2-032,I2-035,I2-048,R2-I010,R2-I013,R2-I015,R2-I020 | I2-037,I2-042 |
| layers-ssp-fast [ordered-stop] | intra2 | 69 | 9 | 21 | 14 | 2 | I2-010,I2-012,I2-013,I2-017,I2-021,I2-022,I2-031,I2-032,I2-034,I2-035,R2-I010,R2-I013,R2-I015,R2-I020 | I2-009,I2-042 |

## Time per question, T10 systems (wall seconds)

`layer 0` = A.ask (all 3 tiers); `layers extra` = ask_layered on top of that layer 0 (the first config of the run builds the layer-1 reads, the second finds them cached); `total` = layer 0 + extra. load = the 1-min load average of the Air when the question finished. All questions of the sweep (answerable and unans).

| system | n | layer 0 median / mean / max | layers extra median / mean / max | total median / mean / max | questions over 300 s total | load median / max |
|---|---|---|---|---|---|---|
| flat-fast [ordered-stop] | 94 | 167.4 / 186.4 / 413.6 | - | 167.4 / 186.4 / 413.6 | 7 | 28.6 / 70.1 |
| layers-path-fast [ordered-stop] | 94 | 167.4 / 186.4 / 413.6 | 79.8 / 82.4 / 281.8 | 266.7 / 268.8 / 634.2 | 35 | 28.6 / 70.1 |
| layers-ssp-fast [ordered-stop] | 94 | 167.4 / 186.4 / 413.6 | 94.8 / 109.6 / 449.4 | 289.2 / 296.0 / 749.8 | 45 | 28.6 / 70.1 |

## Layer-0 verdicts of the flat T10 systems

| system | kind | ANSWER | CHOICE | UNKNOWN_NO_STATE |
|---|---|---|---|---|
| flat-fast [ordered-stop] | intra2 | 2 | 65 | 2 |
| flat-fast [ordered-stop] | unans | 1 | 23 | 1 |

## Normalisation effect

Items where a system's gold hit exists only after normalisation (verbatim words do not hold the gold):

- flat-fast [ordered-stop]: none
- flat-fast [t9 whole]: none
- layers-path-fast [ordered-stop]: none
- layers-path-fast [t9 whole]: none
- layers-ssp-fast [ordered-stop]: none
- layers-ssp-fast [t9 whole]: none

## Diagnostic: looser rule (gold inside the concatenation of ALL words of one entry), answerable questions

Not the headline rule (the concatenation of a word set is not text of the corpus); shown to see whether the word-level rule hides hits for multi-word golds.

| system | intra2 word-level -> joined | cross2 word-level -> joined |
|---|---|---|
| flat-fast [ordered-stop] | 16 -> 17 (of 69) | - |
| flat-fast [t9 whole] | 7 -> 8 (of 69) | - |
| layers-path-fast [ordered-stop] | 18 -> 20 (of 69) | - |
| layers-path-fast [t9 whole] | 7 -> 8 (of 69) | - |
| layers-ssp-fast [ordered-stop] | 21 -> 24 (of 69) | - |
| layers-ssp-fast [t9 whole] | 9 -> 11 (of 69) | - |

