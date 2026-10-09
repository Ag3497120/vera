# G3-g2 -- the combined list without merging across sources, per-origin blocks, typed abstentions first (bank2 fulllead)

Code state: line3 HEAD 6b62f0fd13ba06f78d02aafdda475adc1b851e93 plus the uncommitted G3-g2 work (verantyx/line3/combined.py `merge`, `also_in`, `header`, `blocks`; cli.py `--merge`).

Inputs: flat cross (3 tiers) and layers (stable-seats-path) REPLAYED from T10's raw records (as G3-g, no re-run); windows LIVE (`measure_windows.py`, representative members, evidence plain and window, z_deep slide, 94 questions per preset read at the G3-g2 code state, records `results/g2_win_*`). Lists: `combine(...)` with `merge="none"` (the default; every candidate its own entry, blocks flat/RUN, flat/WORD, flat/CHAR, layers, window/plain, window/window-evidence, each block most stable first with the source's order breaking ties, L-749; a block whose candidates hold no stability stays in the source's order and is marked order=source: the layers replayed from T10), `merge="none" in the source's order` (the L-743 arrangement before L-749, stability stripped from the sources) and `merge="word_set"` (G3-g). Position = 1-based index in the whole list; within-block position = index among the entries of that block. List size = entries of the lists with >= 2 entries (intra2), as in G3-g.

## Headline (intra2 n = 69, unans n = 25)

| merge | preset | gold in a candidate | single right / wrong | list with gold / without | none | list size median / max | first-gold position median / max (overall) | first-gold position median / max (within its block) | unans: abstained / list / single wrong |
|---|---|---|---|---|---|---|---|---|---|
| none, blocks by stability (G3-g2 default, L-749) | fast | 29 | 0 / 0 | 29 / 39 | 1 | 28.5 / 151 | 2.0 / 80 | 1.0 / 39 | 0 / 25 / 0 |
| none, blocks by stability (G3-g2 default, L-749) | standard | 34 | 0 / 0 | 34 / 35 | 0 | 68.0 / 239 | 4.5 / 125 | 1.0 / 39 | 0 / 25 / 0 |
| none, blocks in the source's order (before L-749) | fast | 29 | 0 / 0 | 29 / 39 | 1 | 28.5 / 151 | 3.0 / 80 | 1.0 / 38 | 0 / 25 / 0 |
| none, blocks in the source's order (before L-749) | standard | 34 | 0 / 0 | 34 / 35 | 0 | 68.0 / 239 | 8.0 / 124 | 1.0 / 43 | 0 / 25 / 0 |
| word_set (G3-g, recomputed) | fast | 29 | 0 / 0 | 29 / 39 | 1 | 28.5 / 147 | 3.0 / 80 | 1.0 / 38 | 0 / 25 / 0 |
| word_set (G3-g, recomputed) | standard | 34 | 0 / 0 | 34 / 35 | 0 | 60.0 / 227 | 8.0 / 120 | 1.0 / 43 | 0 / 25 / 0 |

Unans: a list of ONE window-only entry counts as a list; ANSWER (one entry some non-window origin gives) counts as single. The verdict rule is L-724 applied to the entries as listed.

## What not merging changes (word_set -> none)

| preset | kind | questions | entries word_set median / max | entries none median / max | questions whose verdict changes | of which ANSWER -> CHOICE | gold in a candidate word_set / none |
|---|---|---|---|---|---|---|---|
| fast | intra2 | 69 | 28.5 / 147 | 28.5 / 151 | 0 (-) | 0 (-) | 29 / 29 |
| fast | unans | 25 | 38.0 / 268 | 38.0 / 270 | 0 (-) | 0 (-) | 0 / 0 |
| standard | intra2 | 69 | 60.0 / 227 | 68.0 / 239 | 0 (-) | 0 (-) | 34 / 34 |
| standard | unans | 25 | 63.0 / 342 | 65.0 / 346 | 0 (-) | 0 (-) | 0 / 0 |

## Blocks whose order changed (stability order against the source's order)

Per block and question that lists the block: the block's sequence under L-749 (stability, ties in the source's order) against the source's own sequence. `order=source` blocks (no stability recorded: the layers replayed from T10) are not sorted and cannot change. Counted over the 94 questions.

| preset | block | questions listing the block | block sorted by stability (order=stability) | order changed by the sort | block with a tie of equal stability | first entry changed |
|---|---|---|---|---|---|---|
| fast | flat/RUN | 81 | 81 | 61 | 73 | 45 |
| fast | flat/WORD | 72 | 72 | 50 | 47 | 40 |
| fast | flat/CHAR | 9 | 9 | 6 | 5 | 5 |
| fast | layers | 89 | 0 | 0 | 0 | 0 |
| fast | window/plain | 32 | 32 | 9 | 10 | 8 |
| fast | window/window-evidence | 70 | 70 | 23 | 18 | 19 |
| fast | all blocks | 353 | 264 | 149 | 153 | 117 |
| standard | flat/RUN | 83 | 83 | 71 | 78 | 55 |
| standard | flat/WORD | 83 | 83 | 55 | 50 | 46 |
| standard | flat/CHAR | 33 | 33 | 18 | 17 | 16 |
| standard | layers | 94 | 0 | 0 | 0 | 0 |
| standard | window/plain | 47 | 47 | 19 | 18 | 17 |
| standard | window/window-evidence | 82 | 82 | 44 | 35 | 36 |
| standard | all blocks | 422 | 328 | 207 | 198 | 170 |

## Where the first gold stands, per block (intra2, merge none)

'first gold in this block' = questions where some entry of the block holds the gold; position = index of the first such entry inside the block (the block's order: most stable first, ties in the source's order); block size = entries of the block in those questions. 'first gold of the whole list is in this block' = the block that holds the earliest gold entry of the list.

| preset | block | questions with the gold in the block | position in block median / max | block size median / max (those questions) | questions where the whole list's first gold is here | block lists something (of 69) | block lists something and holds no gold |
|---|---|---|---|---|---|---|---|
| fast | flat/RUN | 15 | 1.0 / 39 | 9.0 / 60 | 15 | 61 | 46 |
| fast | flat/WORD | 6 | 1.0 / 2 | 11.5 / 24 | 1 | 53 | 47 |
| fast | flat/CHAR | 0 | - / - | - / - | 0 | 6 | 6 |
| fast | layers | 11 | 1.0 / 2 | 3.0 / 5 | 5 | 65 | 54 |
| fast | window/plain | 9 | 1.0 / 2 | 2.0 / 4 | 3 | 25 | 16 |
| fast | window/window-evidence | 19 | 1.0 / 5 | 2.0 / 5 | 5 | 51 | 32 |
| standard | flat/RUN | 18 | 1.0 / 39 | 12.5 / 156 | 18 | 62 | 44 |
| standard | flat/WORD | 8 | 1.0 / 2 | 7.5 / 33 | 1 | 62 | 54 |
| standard | flat/CHAR | 0 | - / - | - / - | 0 | 22 | 22 |
| standard | layers | 24 | 1.0 / 2 | 13.5 / 36 | 8 | 69 | 45 |
| standard | window/plain | 10 | 2.0 / 5 | 4.0 / 9 | 3 | 38 | 28 |
| standard | window/window-evidence | 21 | 1.0 / 9 | 4.0 / 10 | 4 | 61 | 40 |

## The abstention header: how often each source lists and how often it abstains with which type (all 94 questions)

A cell is a number of questions (of 94 = 69 intra2 + 25 unans). `listed` = the source gave candidates; a type = the source gave none and the header says why (the tier's own verdict for flat/<tier>; the source's verdict for the layers and the windows). The last column counts questions where the source listed AND some part of it (a layer run, a window) abstained with the given types.

**fast** (n = 94)

| source | listed | AMBIGUOUS | UNKNOWN_NOT_READ | UNKNOWN_NO_EVIDENCE | UNKNOWN_NO_FIXED_POINT | UNKNOWN_RATIO_DISAGREEMENT | UNKNOWN_SECTION_DISAGREEMENT | UNKNOWN_UNSTABLE_AXIS_IMPROVABLE | listed with part-abstentions (types: questions) |
|---|---|---|---|---|---|---|---|---|---|
| flat/RUN | 81 | 5 | 0 | 3 | 5 | 0 | 0 | 0 | - |
| flat/WORD | 72 | 1 | 0 | 0 | 20 | 1 | 0 | 0 | - |
| flat/CHAR | 9 | 2 | 0 | 0 | 83 | 0 | 0 | 0 | - |
| layers | 89 | 0 | 0 | 1 | 4 | 0 | 0 | 0 | AMBIGUOUS: 5, UNKNOWN_NO_EVIDENCE: 11, UNKNOWN_NO_FIXED_POINT: 55, UNKNOWN_RATIO_DISAGREEMENT: 4, UNKNOWN_SECTION_DISAGREEMENT: 4 |
| window/plain | 32 | 10 | 2 | 2 | 32 | 11 | 3 | 2 | ambiguous: 4, mixed: 16, no_fixed_point: 10, not_grounded: 3, points_nowhere: 1, ratio_disagreement: 8, section_disagreement: 1 |
| window/window-evidence | 70 | 4 | 2 | 3 | 9 | 5 | 0 | 1 | ambiguous: 9, mixed: 28, no_fixed_point: 30, not_grounded: 4, points_nowhere: 6, ratio_disagreement: 14, section_disagreement: 1 |

unans only (n = 25): sources that list something: flat/RUN 20; flat/WORD 19; flat/CHAR 3; layers 24; window/plain 7; window/window-evidence 19

Questions where every source abstains: 1; where at least one source abstains: 93; where every source lists: 1.

**standard** (n = 94)

| source | listed | AMBIGUOUS | UNKNOWN_NO_EVIDENCE | UNKNOWN_NO_FIXED_POINT | UNKNOWN_RATIO_DISAGREEMENT | UNKNOWN_SECTION_DISAGREEMENT | UNKNOWN_UNSTABLE_AXIS_IMPROVABLE | listed with part-abstentions (types: questions) |
|---|---|---|---|---|---|---|---|---|
| flat/RUN | 83 | 5 | 3 | 3 | 0 | 0 | 0 | - |
| flat/WORD | 83 | 3 | 0 | 8 | 0 | 0 | 0 | - |
| flat/CHAR | 33 | 2 | 0 | 59 | 0 | 0 | 0 | - |
| layers | 94 | 0 | 0 | 0 | 0 | 0 | 0 | AMBIGUOUS: 1, UNKNOWN_NO_EVIDENCE: 12, UNKNOWN_NO_FIXED_POINT: 60, UNKNOWN_RATIO_DISAGREEMENT: 2, UNKNOWN_SECTION_DISAGREEMENT: 3 |
| window/plain | 47 | 14 | 2 | 19 | 8 | 2 | 2 | ambiguous: 13, mixed: 36, no_fixed_point: 33, not_grounded: 4, points_nowhere: 9, ratio_disagreement: 24, section_disagreement: 4 |
| window/window-evidence | 82 | 2 | 2 | 5 | 2 | 0 | 1 | ambiguous: 24, mixed: 49, no_fixed_point: 52, not_grounded: 5, points_nowhere: 18, ratio_disagreement: 36, section_disagreement: 4 |

unans only (n = 25): sources that list something: flat/RUN 21; flat/WORD 21; flat/CHAR 11; layers 25; window/plain 9; window/window-evidence 21

Questions where every source abstains: 0; where at least one source abstains: 82; where every source lists: 12.

## `also_in`: the agreement mark between origins (merge none)

An entry with `also_in` has other origins that give the same word set (the mark only: nothing is summed, ranked or chosen by it). Counted over entries of the 94 questions.

| preset | entries | entries with also_in | word sets given by >= 2 origins | pairs of origins that agree (unordered, by word set) |
|---|---|---|---|---|
| fast | 4045 | 57 | 27 | flat/RUN + layers/RUN/1A: 1; flat/RUN + window/plain: 1; window/plain + window/window-evidence: 25 |
| standard | 7037 | 139 | 60 | flat/RUN + layers/RUN/1A: 1; flat/RUN + layers/RUN/2A: 1; flat/RUN + window/plain: 1; layers/RUN/1A + layers/RUN/2A: 1; window/plain + window/window-evidence: 58 |

Word sets given by two or more windows of ONE origin (twin windows, no `also_in`, two entries each): fast 5; standard 22.

## Golds that only windows find (intra2): where they stand now

Found ONLY by windows = the gold is in no entry of the flat and layers blocks. Position in the whole list (list size), block of the first gold entry and position inside it; G3-g (word_set) position for comparison; and the position inside each window block.

| preset | item | first gold: overall (list size) | block, position inside | G3-g word_set position (list size) | window/plain: position inside / block size | window/window-evidence: position inside / block size |
|---|---|---|---|---|---|---|
| fast | I2-002 | 68 (71) | window/plain, 2 | 65 (68) | 2 / 2 | 1 / 3 |
| fast | I2-004 | 6 (6) | window/window-evidence, 2 | 5 (6) | - | 2 / 2 |
| fast | I2-006 | 1 (2) | window/window-evidence, 1 | 1 (2) | - | 1 / 2 |
| fast | I2-009 | 3 (6) | window/window-evidence, 1 | 3 (6) | - | 1 / 4 |
| fast | I2-030 | 64 (65) | window/window-evidence, 1 | 65 (65) | - | 1 / 2 |
| fast | I2-045 | 30 (32) | window/plain, 2 | 30 (31) | 2 / 2 | 2 / 2 |
| fast | R2-I016 | 6 (6) | window/window-evidence, 1 | 6 (6) | - | 1 / 1 |
| fast | R2-I018 | 6 (7) | window/plain, 1 | 6 (7) | 1 / 1 | 1 / 1 |
| standard | I2-002 | 74 (79) | window/plain, 2 | 69 (74) | 2 / 3 | 1 / 4 |
| standard | I2-004 | 10 (10) | window/window-evidence, 2 | 9 (10) | - | 2 / 2 |
| standard | I2-006 | 19 (20) | window/window-evidence, 1 | 12 (13) | - | 1 / 2 |
| standard | I2-030 | 87 (88) | window/window-evidence, 1 | 88 (88) | - | 1 / 2 |
| standard | I2-043 | 125 (126) | window/window-evidence, 3 | 120 (122) | - | 3 / 4 |
| standard | I2-045 | 90 (93) | window/plain, 2 | 90 (92) | 2 / 2 | 3 / 3 |
| standard | R2-I018 | 36 (46) | window/plain, 2 | 23 (34) | 2 / 3 | 9 / 9 |

## Gold per block (intra2)

A block 'finds' a question when one of its entries holds the gold (the blocks are the owner's origins; layers = all layers/... origins).

| preset | flat/RUN | flat/WORD | flat/CHAR | layers | window/plain | window/window-evidence | any block |
|---|---|---|---|---|---|---|---|
| fast | 15 | 6 | 0 | 11 | 9 | 19 | 29 |
| standard | 18 | 8 | 0 | 24 | 10 | 21 | 34 |

## Notes

* The candidates and their order are G3-g's; `merge="none"` only stops joining equal word sets and groups the flat tiers in the fixed block order, so 'gold in a candidate' is the same as G3-g (checked in the first table: none, none in the source's order and word_set agree). The list is longer by the entries the merge had joined (mostly the two window variants giving the same word set).
* Position is a property of the fixed block order, not a ranking: the user reads a block most stable first (ties in the source's order; the layers replayed from T10 carry no stability and stay in the source's order); nothing is ordered across blocks.
