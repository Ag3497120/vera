# G3-g -- the combined labelled candidate list (flat cross + layers + windows), bank2 fulllead

Code state: line3 HEAD 1fbc76f231aa566513b16e7e2199ff240b19017c plus the uncommitted G3-g work (verantyx/line3/combined.py, ask.py / cli.py hooks, slide_flat.py `word_sources`). The combiner is `verantyx.line3.combined.combine`, the one `ask(structure="combined")` calls.

## What is replayed and what is live

* **Flat cross (3 tiers) and layers (stable-seats-path) are REPLAYED records**, not re-run: T10's raw per-question records (`experiments/line3/t10/results/ask_fulllead_{fast,standard}_ordered-stop.jsonl`), same 94 questions, same ordered placement cache (`/Users/motonisihikoudai/Projects/vera-impl/cache/f1b`, group_insert ordered, order forward, on_collapse stop), layers variant A / compress / no feedback. T10's code sha: `be923510340a26a073e6cfda4211404fe361e03b` (fast) and `be923510340a26a073e6cfda4211404fe361e03b` (standard) (T10 `head` = line3 be92351 + the F1c work in progress of that moment, run from `t10_snapshot`; the flat / layers code path has not changed since: tests/line3/test_ask*.py and test_matryoshka.py are the goldens, and `equiv_check.py` re-ran the live `ask_combined` flat + layers parts on cheap questions and compared them with the records, results below). Their raw times (load 20-40, 10 workers) are T10's. A replayed candidate holds the words, centres, stability and counts T10 recorded: **no source sentences and no per-word provenance, no P-4 trace flag for the flat part** (the layers' run trace flag is recorded and used).
* **Windows are LIVE**: `measure_windows.py`, slide_flat.ask_flat, members representative, evidence plain and window, z_deep slide (the G3-c3 default placements, window cache `slidewin_725d5ac1a8d2_RUN_3df141b12327_07db87511ff1.pkl` in the scratch caches), the windows' own search budget (512 / 64), `effort` fast = 4 windows, standard = 10 windows; 6 workers; the 1-min load at the questions' end was 2.9-8.6 (median 6.1), the goldens ran on the same machine at the same time. Window records carry the per-word sentences (`word_sources`).
* The combined row is the combiner's output on those sources, so everything that is not 'gold in a candidate' (single / list / none) follows the **combined verdict** (windows alone never a single answer); all other rows keep t9's count rule (exactly one candidate = single), so they equal the published tables (T10 flat / ssp rows are checked against `t10/results/summary.md` and the window rows against `g3/s1flat/results/summary_flat.md` below).
* Order of the list: flat (RUN, WORD, CHAR), layers (tier, layer), window/plain, window/window-evidence; equal word sets are one entry placed at its first candidate. T10's own tables list the layers' tiers alphabetically (the records were written with sorted keys); the replay uses the live order RUN, WORD, CHAR.

## intra2 (fulllead, n = 69), fast

Single / list columns: rows named COMBINED, 'flat + layers, merged' and 'windows alone, both variants merged' follow the combined VERDICT (a list of one entry that only windows give is a LIST); the other rows are t9's count rule. List size = entries of the shown lists (>= 2 entries; COMBINED rows: also the number of entries before the merge). 'words' = words in the list.

| system | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size median / max | entries before merge median / max | words in list median / max | first-gold pos median / max | s/question median (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T10 flat-fast (3 tiers, T10 replayed) | 16 (23%) | 0 | 2 | 16 | 49 | 2 | 26.0 / 141 | 26.0 / 141 | 178.0 / 1160 | 1.0 / 38 | 165.95 (413.56) |
| T10 layers-ssp-fast (flat + layers, T10 replayed) | 21 (30%) | 0 | 0 | 21 | 46 | 2 | 28.0 / 146 | 28.0 / 146 | 473.0 / 1774 | 2.0 / 80 | 294.72 (749.79) |
| windows alone plain-fast (live) | 9 (13%) | 3 | 5 | 6 | 11 | 44 | 2.0 / 6 | 2.0 / 6 | 12.0 / 32 | 1.0 / 2 | 1.97 (15.88) |
| windows alone window-evidence-fast (live) | 19 (28%) | 5 | 17 | 14 | 15 | 18 | 3.0 / 6 | 3.0 / 6 | 16.0 / 36 | 1.0 / 4 | 1.36 (15.26) |
| flat + layers, merged by word set, verdict rule (fast) | 21 (30%) | 0 | 0 | 21 | 46 | 2 | 28.0 / 144 | 28.0 / 146 | 473.0 / 1774 | 2.0 / 80 | 294.72 (749.79) |
| windows alone, both variants merged, verdict rule (fast) | 19 (28%) | 0 | 0 | 19 | 32 | 18 | 3.0 / 10 | 3.0 / 10 | 16.0 / 52 | 1.0 / 2 | 3.24 (31.14) |
| COMBINED plain-fast (flat + layers + window/plain) | 24 (35%) | 0 | 0 | 24 | 43 | 2 | 28.0 / 146 | 28.0 / 146 | 481.0 / 1792 | 2.5 / 80 | 300.38 (754.08) |
| COMBINED window-evidence-fast (flat + layers + window/window-evidence) | 29 (42%) | 0 | 0 | 29 | 39 | 1 | 28.5 / 147 | 28.5 / 147 | 483.5 / 1801 | 3.0 / 80 | 298.17 (750.57) |
| COMBINED both-fast (flat + layers + both window variants) | 29 (42%) | 0 | 0 | 29 | 39 | 1 | 28.5 / 147 | 28.5 / 151 | 483.5 / 1801 | 3.0 / 80 | 303.84 (754.86) |
| B1-mecab | 47 (68%) | 31 | 18 | 16 | 4 | 0 | 2.0 / 34 | 2.0 / 34 | 2.0 / 34 | 1.0 / 8 | - (-) |
| B2-mecab | 57 (83%) | 20 | 2 | 37 | 10 | 0 | 2.0 / 42 | 2.0 / 42 | 2.0 / 42 | 1.0 / 12 | - (-) |
| B1-bigram | 38 (55%) | 30 | 29 | 8 | 2 | 0 | 2.0 / 5 | 2.0 / 5 | 2.0 / 5 | 1.0 / 5 | - (-) |
| B2-bigram | 54 (78%) | 19 | 2 | 35 | 13 | 0 | 2.0 / 5 | 2.0 / 5 | 2.0 / 5 | 1.0 / 5 | - (-) |

### unans (fulllead, n = 25), fast: can a user reject what is shown?

Correct behaviour = abstain. 'list' = rejectable by a user (for COMBINED rows a list of one window-only entry counts here); 'single answer' = confident wrong.

| system | no candidate (abstained) | list only (rejectable) | of which a list of ONE window-only entry | single answer (confident wrong) | list size median / max (lists) |
|---|---|---|---|---|---|
| T10 flat-fast (3 tiers, T10 replayed) | 1 | 23 | 0 | 1 | 37.0 / 258 |
| T10 layers-ssp-fast (flat + layers, T10 replayed) | 0 | 24 | 0 | 1 | 37.5 / 264 |
| windows alone plain-fast (live) | 18 | 2 | 0 | 5 | 3.5 / 5 |
| windows alone window-evidence-fast (live) | 6 | 9 | 0 | 10 | 3.0 / 6 |
| flat + layers, merged by word set, verdict rule (fast) | 0 | 24 | 0 | 1 | 37.5 / 263 |
| windows alone, both variants merged, verdict rule (fast) | 6 | 19 | 8 | 0 | 3.0 / 7 |
| COMBINED plain-fast (flat + layers + window/plain) | 0 | 24 | 0 | 1 | 37.5 / 264 |
| COMBINED window-evidence-fast (flat + layers + window/window-evidence) | 0 | 25 | 0 | 0 | 38.0 / 268 |
| COMBINED both-fast (flat + layers + both window variants) | 0 | 25 | 0 | 0 | 38.0 / 268 |
| B1-mecab | 0 | 13 | 0 | 12 | 3.0 / 52 |
| B2-mecab | 0 | 24 | 0 | 1 | 2.5 / 68 |
| B1-bigram | 0 | 6 | 0 | 19 | 2.5 / 54 |
| B2-bigram | 0 | 23 | 0 | 2 | 2.0 / 78 |

## intra2 (fulllead, n = 69), standard

Single / list columns: rows named COMBINED, 'flat + layers, merged' and 'windows alone, both variants merged' follow the combined VERDICT (a list of one entry that only windows give is a LIST); the other rows are t9's count rule. List size = entries of the shown lists (>= 2 entries; COMBINED rows: also the number of entries before the merge). 'words' = words in the list.

| system | gold in a candidate | single right | single wrong | list with gold | list without gold | no candidate | list size median / max | entries before merge median / max | words in list median / max | first-gold pos median / max | s/question median (max) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| T10 flat-standard (3 tiers, T10 replayed) | 19 (28%) | 0 | 1 | 19 | 49 | 0 | 44.5 / 203 | 44.5 / 203 | 349.5 / 1497 | 1.0 / 53 | 485.69 (1087.67) |
| T10 layers-ssp-standard (flat + layers, T10 replayed) | 27 (39%) | 0 | 0 | 27 | 42 | 0 | 61.0 / 234 | 61.0 / 234 | 2070.0 / 5540 | 3.0 / 92 | 956.94 (1586.82) |
| windows alone plain-standard (live) | 10 (14%) | 0 | 10 | 10 | 18 | 31 | 3.0 / 10 | 3.0 / 10 | 15.5 / 50 | 1.0 / 5 | 4.99 (28.00) |
| windows alone window-evidence-standard (live) | 21 (30%) | 2 | 12 | 19 | 28 | 8 | 4.0 / 11 | 4.0 / 11 | 22.0 / 58 | 1.0 / 6 | 3.93 (20.41) |
| flat + layers, merged by word set, verdict rule (standard) | 27 (39%) | 0 | 0 | 27 | 42 | 0 | 55.0 / 222 | 61.0 / 234 | 1956.0 / 5366 | 3.0 / 92 | 956.94 (1586.82) |
| windows alone, both variants merged, verdict rule (standard) | 21 (30%) | 0 | 0 | 21 | 40 | 8 | 5.0 / 17 | 5.0 / 21 | 24.0 / 84 | 1.0 / 5 | 9.63 (44.41) |
| COMBINED plain-standard (flat + layers + window/plain) | 30 (43%) | 0 | 0 | 30 | 39 | 0 | 59.0 / 226 | 64.0 / 238 | 1956.0 / 5374 | 4.5 / 92 | 962.98 (1593.09) |
| COMBINED window-evidence-standard (flat + layers + window/window-evidence) | 34 (49%) | 0 | 0 | 34 | 35 | 0 | 60.0 / 223 | 66.0 / 235 | 1956.0 / 5380 | 8.0 / 120 | 963.05 (1595.79) |
| COMBINED both-standard (flat + layers + both window variants) | 34 (49%) | 0 | 0 | 34 | 35 | 0 | 60.0 / 227 | 68.0 / 239 | 1956.0 / 5384 | 8.0 / 120 | 963.16 (1602.07) |

### unans (fulllead, n = 25), standard: can a user reject what is shown?

Correct behaviour = abstain. 'list' = rejectable by a user (for COMBINED rows a list of one window-only entry counts here); 'single answer' = confident wrong.

| system | no candidate (abstained) | list only (rejectable) | of which a list of ONE window-only entry | single answer (confident wrong) | list size median / max (lists) |
|---|---|---|---|---|---|
| T10 flat-standard (3 tiers, T10 replayed) | 0 | 25 | 0 | 0 | 52.0 / 330 |
| T10 layers-ssp-standard (flat + layers, T10 replayed) | 0 | 25 | 0 | 0 | 63.0 / 340 |
| windows alone plain-standard (live) | 16 | 5 | 0 | 4 | 2.0 / 5 |
| windows alone window-evidence-standard (live) | 4 | 12 | 0 | 9 | 3.0 / 11 |
| flat + layers, merged by word set, verdict rule (standard) | 0 | 25 | 0 | 0 | 62.0 / 337 |
| windows alone, both variants merged, verdict rule (standard) | 4 | 21 | 8 | 0 | 4.0 / 11 |
| COMBINED plain-standard (flat + layers + window/plain) | 0 | 25 | 0 | 0 | 62.0 / 338 |
| COMBINED window-evidence-standard (flat + layers + window/window-evidence) | 0 | 25 | 0 | 0 | 63.0 / 342 |
| COMBINED both-standard (flat + layers + both window variants) | 0 | 25 | 0 | 0 | 63.0 / 342 |

## Replay checks against the published tables

The replayed T10 rows and the live window rows, recomputed here, against the numbers printed in `t10/results/summary.md` and `g3/s1flat/results/summary_flat.md` (intra2 gold in a candidate / single wrong in unans).

| row | preset | gold in a candidate here | published | single wrong in unans here |
|---|---|---|---|---|
| T10 flat | fast | 16 | 16 | 1 |
| T10 layers-ssp | fast | 21 | 21 | 1 |
| windows plain | fast | 9 | 9 | 5 |
| windows window-evidence | fast | 19 | 19 | 10 |
| T10 flat | standard | 19 | 19 | 0 |
| T10 layers-ssp | standard | 27 | 27 | 0 |
| windows plain | standard | 10 | 10 | 4 |
| windows window-evidence | standard | 21 | 21 | 9 |

## Gold in a candidate, per origin (intra2, n = 69)

An origin 'finds' a question when some entry that holds the gold lists that origin (an entry with several origins counts for each). The combined-both list of the preset; flat/<tier> and layers/ are T10's replayed, window/ is live.

| preset | flat/RUN | flat/WORD | flat/CHAR | layers | window/plain | window/window-evidence | flat (any tier) | flat + layers | flat + layers + window/plain | all (combined both) | found ONLY by windows | found ONLY by flat + layers |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fast | 15 | 6 | 0 | 11 | 9 | 19 | 16 | 21 | 24 | 29 | 8 (I2-002, I2-004, I2-006, I2-009, I2-030, I2-045, R2-I016, R2-I018) | 10 (I2-012, I2-017, I2-021, I2-027, I2-029, I2-032, I2-034, I2-035, R2-I001, R2-I020) |
| standard | 18 | 8 | 0 | 24 | 10 | 21 | 19 | 27 | 30 | 34 | 7 (I2-002, I2-004, I2-006, I2-030, I2-043, I2-045, R2-I018) | 13 (I2-012, I2-017, I2-021, I2-023, I2-025, I2-027, I2-029, I2-032, I2-033, I2-034, I2-035, R2-I001, R2-I017) |

## The 9 B2-hard items, per origin (combined both)

Cell per origin: Y = some entry holding the gold lists that origin, . = no. Last columns: the combined verdict mark (S = single answer holds gold; Ln = list of n entries holds gold; w = single answer without gold; xn = list of n without gold; - = no candidate) and the position of the first entry holding the gold.

**fast**

| item | gold | flat/RUN | flat/WORD | flat/CHAR | layers | window/plain | window/window-evidence | combined | first-gold pos |
|---|---|---|---|---|---|---|---|---|---|
| I2-011 | 改称 | . | . | . | . | . | . | x13 | - |
| I2-014 | 九曜紋 | Y | . | . | . | . | Y | L6 | 1 |
| I2-029 | 和歌山千葉線 | Y | . | . | . | . | . | L33 | 1 |
| I2-031 | USB|イーサネット|LXI | . | . | . | Y | Y | Y | L84 | 80 |
| I2-033 | リュカーオーン | . | . | . | . | . | . | x25 | - |
| I2-039 | 愛知県 | . | . | . | . | . | . | - | - |
| R2-I003 | 中播磨県民センター | . | . | . | . | . | . | x17 | - |
| R2-I006 | 120 m|120 | . | . | . | . | . | . | x45 | - |
| R2-I013 | ネパール | Y | . | . | . | Y | Y | L8 | 1 |

B2-hard items with the gold in some candidate: 4 of 9 (I2-014, I2-029, I2-031, R2-I013); T10 layers-ssp fast: 4 of 9; windows alone (plain / evidence): 2 / 3.

**standard**

| item | gold | flat/RUN | flat/WORD | flat/CHAR | layers | window/plain | window/window-evidence | combined | first-gold pos |
|---|---|---|---|---|---|---|---|---|---|
| I2-011 | 改称 | . | . | . | . | . | . | x29 | - |
| I2-014 | 九曜紋 | Y | . | . | Y | . | Y | L13 | 1 |
| I2-029 | 和歌山千葉線 | Y | . | . | Y | . | . | L22 | 1 |
| I2-031 | USB|イーサネット|LXI | . | . | . | Y | Y | Y | L62 | 48 |
| I2-033 | リュカーオーン | Y | Y | . | Y | . | . | L87 | 1 |
| I2-039 | 愛知県 | . | . | . | . | . | . | x14 | - |
| R2-I003 | 中播磨県民センター | . | . | . | . | . | . | x22 | - |
| R2-I006 | 120 m|120 | . | . | . | Y | Y | Y | L110 | 92 |
| R2-I013 | ネパール | Y | . | . | Y | Y | Y | L21 | 1 |

B2-hard items with the gold in some candidate: 6 of 9 (I2-014, I2-029, I2-031, I2-033, R2-I006, R2-I013); T10 layers-ssp standard: 6 of 9; windows alone (plain / evidence): 3 / 4.

## The merge and the verdicts (combined both)

| preset | kind | n | UNKNOWN (no entry) | ANSWER (one entry, a non-window origin) | of which holds the gold | CHOICE | of which one entry only windows give | entries before merge median / max | entries after merge median / max | entries with several origins | with origins in several families | ANSWER only because of the merge (>= 2 candidates, 1 entry) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| fast | intra2 | 69 | 1 | 0 | 0 | 68 | 0 | 28.5 / 151 | 28.5 / 147 | 22 | 1 | 0 (-) |
| fast | unans | 25 | 0 | 0 | 0 | 25 | 0 | 38.0 / 270 | 38.0 / 268 | 5 | 1 | 0 (-) |
| standard | intra2 | 69 | 0 | 0 | 0 | 69 | 0 | 68.0 / 239 | 60.0 / 227 | 54 | 1 | 0 (-) |
| standard | unans | 25 | 0 | 0 | 0 | 25 | 0 | 65.0 / 346 | 63.0 / 342 | 6 | 1 | 0 (-) |

## What decision 3 changes (a candidate only windows give is never a single answer)

Under the count rule (t9 / G3-f: exactly one candidate = a single answer) every window read that ended with one entry was a single answer; under the verdict rule a window-only entry is a list. The windows-alone rows (one evidence variant, entries never merged across windows) counted both ways, and the same count on the combined lists:

| preset | row | kind | single answers under the count rule (right / wrong) | single answers under the verdict rule |
|---|---|---|---|---|
| fast | windows alone plain-fast | intra2 | 8 (3 / 5) | 0 |
| fast | windows alone plain-fast | unans | 5 (0 / 5) | 0 |
| fast | windows alone window-evidence-fast | intra2 | 22 (5 / 17) | 0 |
| fast | windows alone window-evidence-fast | unans | 10 (0 / 10) | 0 |
| fast | COMBINED both-fast | intra2 | 0 (0 / 0) | 0 |
| fast | COMBINED both-fast | unans | 0 (0 / 0) | 0 |
| standard | windows alone plain-standard | intra2 | 10 (0 / 10) | 0 |
| standard | windows alone plain-standard | unans | 4 (0 / 4) | 0 |
| standard | windows alone window-evidence-standard | intra2 | 14 (2 / 12) | 0 |
| standard | windows alone window-evidence-standard | unans | 9 (0 / 9) | 0 |
| standard | COMBINED both-standard | intra2 | 0 (0 / 0) | 0 |
| standard | COMBINED both-standard | unans | 0 (0 / 0) | 0 |

## Where the windows' candidates stand in the combined list (combined both)

The list is flat, then layers, then windows (L-720); a gold that only windows find stands after the flat and layers entries. Position = first entry holding the gold; list = size of the combined list.

| preset | gold found only by windows | first-gold position in the combined list (list size) | first-gold position inside the windows' own entries |
|---|---|---|---|
| fast | I2-002 | 65 (68) | 1 |
| fast | I2-004 | 5 (6) | 1 |
| fast | I2-006 | 1 (2) | 1 |
| fast | I2-009 | 3 (6) | 1 |
| fast | I2-030 | 65 (65) | 2 |
| fast | I2-045 | 30 (31) | 2 |
| fast | R2-I016 | 6 (6) | 1 |
| fast | R2-I018 | 6 (7) | 1 |
| standard | I2-002 | 69 (74) | 1 |
| standard | I2-004 | 9 (10) | 1 |
| standard | I2-006 | 12 (13) | 1 |
| standard | I2-030 | 88 (88) | 2 |
| standard | I2-043 | 120 (122) | 2 |
| standard | I2-045 | 90 (92) | 2 |
| standard | R2-I018 | 23 (34) | 1 |

## Time per question (wall seconds)

The flat + layers parts are T10's recorded times (10 workers, load 20-40, not comparable with a quiet machine); the window parts are this run's (6 workers, load 2.9-8.6, median 6.1). 'both variants' = the windows read twice (plain, then window evidence). The combined list is the union of all parts, so its cost is their sum.

| preset | flat layer 0 (T10) median / max | layers extra (T10) median / max | windows plain (live) median / max | windows window-evidence (live) median / max | windows both median / max | combined total median / max |
|---|---|---|---|---|---|---|
| fast | 167.4 / 413.6 | 94.8 / 449.4 | 1.91 / 15.88 | 1.35 / 15.26 | 3.00 / 31.14 | 292.0 / 754.9 |
| standard | 464.5 / 1087.7 | 441.2 / 861.3 | 4.59 / 28.00 | 3.72 / 20.41 | 8.94 / 44.41 | 922.2 / 1602.1 |

## P-4 (trace)

| preset | window/plain entries | traced ok | window/window-evidence entries | traced ok | with a word whose edge only a constructed pair sentence evidences | layers runs with entries (T10) | trace ok |
|---|---|---|---|---|---|---|---|
| fast | 69 | 69 | 147 | 147 | 106 | 166 | 166 |
| standard | 141 | 141 | 285 | 285 | 195 | 382 | 382 |

## Notes

* Same questions, same gold and the same scorer as T10 / G3-f; intra2 n = 69, unans n = 25; cross2 and s3000 were not run.
* A combined list is long: it holds the union of the flat cross's 3 tiers (median 26 / 44 entries at fast / standard in T10), the layers' and the windows' entries; the merge only joins equal word sets. The table above gives the sizes.
* The gold-in-a-candidate counts of the combined rows are unions of independently read sources and equal the union of what each origin finds; a larger union with a longer list is the trade the owner chose (candidates for users to grade).
