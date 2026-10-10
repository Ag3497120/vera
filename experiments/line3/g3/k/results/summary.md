# G3-k -- the unknown-word stand-ins and the grammar layer's read order in the combined list

Code: line3 HEAD `2ea0dbc2a07c` + the uncommitted G3-k work; code sha256 of the changed modules (on run): ask afca504bfb, combined 8ff90fdc07, cycle 5e8a62f066, grammar d6ddfd106d, matryoshka 15ffb6b066, slide_flat e55234e7af, slide_query c658f54648, wiring 9c90fe3a6f.
bank3 sweep: `measure_k.py fast ... --kinds unknown-word,paraphrase --workers 10`, started 2026-10-10 07:21:34 (on) / 2026-10-10 02:25:24 (off); python 3.11.14; PYTHONHASHSEED=0; cache /Users/motonisihikoudai/Projects/vera-impl/cache/t11.

## 0. The grammar-off run against the T11 records (same questions, same caches, fast)

The off run (this tree, HEAD + G3-k with `grammar="off"`) and the T11 records (HEAD 2ef8531f, which is G3-i; before G3-j, so the assembled strings of G3-j are not in them and are left out here) give the same list (origins and words of every non-assembled entry, in order) for **38 of 38** questions.

Superseded first on run (`bank3_uwpa_fast_on_layers_leak.jsonl`, kept): the layers still carried the stand-ins up as question bundles (found at review, L-807; the layers' down-reads then read them as full query units): gold in a candidate unknown-word 7, paraphrase 4 (gold lost against the off run: pa17).

Superseded second on run (`bank3_uwpa_fast_on_layer1_leak.jsonl`, kept; 測定時に層の漏れあり, found at the second review, L-810): layer 1 was built from plan.read + ctx.query + the answer units, and ctx.query holds every stand-in, so every stand-in's cross became a layer-1 bundle whether or not it was read under the cap (up to 431). Gold in a candidate on that run: unknown-word 7, paraphrase 6; layers origin: unknown-word 4, paraphrase 2; questions whose gold list differs from the fixed run: none.

## 1. Gold in a candidate, grammar on vs off (bank3 fulllead, combined, fast; the t9 rule; the assembled strings do not count)

| kind | n | off: gold in a candidate | on: gold in a candidate | gold only on | gold only off | off: list size median / max | on: list size median / max | verdicts off / on (ANSWER) | flat/RUN gold off / on | flat/WORD | layers | window/plain | window/evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| unknown-word | 18 | 6 | 7 | 1 (b3_uw18) | 0 () | 46.5 / 142 | 24.0 / 137 | 0 / 0 | 4 / 5 | 1 / 2 | 3 / 5 | 1 / 1 | 3 / 3 |
| paraphrase | 20 | 3 | 6 | 3 (b3_pa06 b3_pa09 b3_pa18) | 0 () | 40.5 / 184 | 40.0 / 191 | 0 / 0 | 1 / 0 | 1 / 1 | 2 / 2 | 0 / 2 | 1 / 3 |

(T11 published: unknown-word 6/18, paraphrase 3/20 for the off run at HEAD 2ef8531f.  B1 (keyword lookup, bank3/baselines.txt): unknown-word 16/18, paraphrase 8/20; B2 16/18, 12/20.)

All 38 questions: gold in a candidate off 9, on 13.

### 1b. What the new order does to the flat block under the fast cap (4 crosses per tier)

flat/RUN entries (all 38 questions): off 1226, on 935; questions where flat/RUN lists nothing: off 6, on 6; questions where flat/RUN falls to under a quarter (off >= 10 entries): **9** (pa04 39->5, pa05 88->8, pa10 63->13, pa19 62->9, uw02 37->0, uw08 35->0, uw09 69->0, uw10 91->4, uw15 43->1).
window entries (plain + evidence): off 126, on 185 (questions listing: plain off 16 / on 20, evidence off 23 / on 30).
Of those, questions with NO stand-in unit added (the change is the order alone): uw02 37->0.

**Who made flat/RUN fall (the 9 collapsed questions, read against the order-only run).** The fall is split in the part the ORDER ALONE makes (off -> order-only) and the part the stand-ins add on top (order-only -> on); a question is filed under the step that first took it under a quarter of its off entries.

| question | stand-in units added | flat/RUN off | order-only | on | fall by the order alone | fall by the stand-ins on top | under a quarter first at |
|---|---|---|---|---|---|---|---|
| pa04 | 6 | 39 | 5 | 5 | 34 | 0 | the order alone |
| pa05 | 14 | 88 | 8 | 8 | 80 | 0 | the order alone |
| pa10 | 6 | 63 | 35 | 13 | 28 | 22 | only once the stand-ins are added |
| pa19 | 77 | 62 | 63 | 9 | -1 | 54 | only once the stand-ins are added |
| uw02 | 0 | 37 | 0 | 0 | 37 | 0 | the order alone |
| uw08 | 284 | 35 | 28 | 0 | 7 | 28 | only once the stand-ins are added |
| uw09 | 46 | 69 | 69 | 0 | 0 | 69 | only once the stand-ins are added |
| uw10 | 4 | 91 | 4 | 4 | 87 | 0 | the order alone |
| uw15 | 121 | 43 | 42 | 1 | 1 | 41 | only once the stand-ins are added |

* Under a quarter by the ORDER ALONE: pa04, pa05, uw02, uw10.  Only once the stand-ins are added: pa10, pa19, uw08, uw09, uw15.  A question whose fall is split (the order takes part of it, the stand-ins the rest) shows in both columns of the fall.

**Attribution (the order alone vs the order plus the stand-ins; 38 questions with an order-only record).** `order-only` = grammar on with the stand-ins dropped from the intake (the read order of the crosses and of the windows, the form, the slot, the `grammar` row; no unit is added to any query).

| kind | n | gold off | gold order-only | gold on (order + stand-ins) | gained by the order alone | gained by the stand-ins on top | lost by the order alone | lost by the stand-ins on top | flat/RUN entries off / order-only / on | window entries off / order-only / on |
|---|---|---|---|---|---|---|---|---|---|---|
| unknown-word | 18 | 6 | 6 | 7 | b3_uw18 | b3_uw15 | b3_uw15 | - | 627 / 517 / 422 | 77 / 77 / 93 |
| paraphrase | 20 | 3 | 3 | 6 | - | b3_pa06 b3_pa09 b3_pa18 | - | - | 599 / 495 / 513 | 49 / 49 / 92 |

Questions whose list differs between order-only and on (i.e. the stand-ins changed something): 22 of 38 (pa03 pa04 pa06 pa07 pa09 pa10 pa11 pa12 pa13 pa14 pa16 pa18 pa19 pa20 uw04 uw08 uw09 uw10 uw15 uw16 uw19 uw20).

## 2. The stand-ins: how many, how many entries exist only through them, and whether the gold is in one

Questions with at least one stand-in unit added: **37 of 38** (forms over all 38: predicate 16, slot 12, standin 10).
Stand-in units added per question (those with any): median 36.0, max 431, p90 142.
Unknown content RUN words over the 38 questions: 104 (T2 50, T3 8, T4 33, T5 13); stand-in units added per word: T2 median 5.0 max 119; T3 median 9.5 max 36; T4 median 16.0 max 431.
Of them, words that CONTAIN an interrogative (何年, 何日, 何丁目, 最大何台, は何という ...: the thing asked, not an unknown subject; G1's 139 count them too): 19, with 424 of the 2428 added stand-in units (e.g. the part 年 stands in 119 units).

Entries marked `via_standin` (flat + windows; the layers' entries are not marked per entry): **19** of 1890 non-assembled entries over the 38 questions; the gold is in one of them for **0** questions.
Entries marked `read_via_standin` and NOT `via_standin` (they hold an original unit; their cross / window would not have been read under the cap by the same order without the stand-ins; L-810): **306** entries in 13 questions (flat/RUN 260, window 46); the gold is in one of them for **3** questions (pa09 pa18 uw15).  `via_standin` implies `read_via_standin` for crosses; 18 of 19 marked entries show both (a window entry can be `via_standin` through a member that holds only a stand-in in a window both orders read).

## 2b. Where the gained golds came from: the marks (L-810)

**bank3, on against the ORDER ALONE** (gold in a candidate on, none in the order-only run): 4 questions.

| question | gold entries on: origin (mark class) |
|---|---|
| pa06 | layers/RUN/1A (layers (unmarked by design)) |
| pa09 | window/plain (read_via_standin); window/plain (read_via_standin); window/window-evidence (read_via_standin); window/window-evidence (read_via_standin) |
| pa18 | window/plain (read_via_standin); window/plain (read_via_standin); window/plain (read_via_standin); window/plain (read_via_standin); window/window-evidence (read_via_standin); window/window-evidence (read_via_standin); window/window-evidence (read_via_standin) |
| uw15 | flat/RUN (read_via_standin); layers/RUN/1A (layers (unmarked by design)) |

By mark (a gold can sit in several entries; a question is counted once per class it has): with a `via_standin` gold entry 0; with a `read_via_standin` (not `via_standin`) gold entry 3; with a gold entry in the layers (unmarked by design) 2; with an unmarked flat / window gold entry (`neither`: reached through an order change among crosses / windows that the order alone also reads) 0.  Questions whose EVERY gold entry is of one class: via_standin 0, read_via_standin 2, layers 1, neither 0; questions with at least one marked gold entry 3 of 4.

**bank3, on against off** (gold in a candidate on, none in the off run): 4 questions.

| question | gold entries on: origin (mark class) |
|---|---|
| pa06 | layers/RUN/1A (layers (unmarked by design)) |
| pa09 | window/plain (read_via_standin); window/plain (read_via_standin); window/window-evidence (read_via_standin); window/window-evidence (read_via_standin) |
| pa18 | window/plain (read_via_standin); window/plain (read_via_standin); window/plain (read_via_standin); window/plain (read_via_standin); window/window-evidence (read_via_standin); window/window-evidence (read_via_standin); window/window-evidence (read_via_standin) |
| uw18 | flat/RUN (neither); layers/RUN/1A (layers (unmarked by design)) |

By mark (a gold can sit in several entries; a question is counted once per class it has): with a `via_standin` gold entry 0; with a `read_via_standin` (not `via_standin`) gold entry 2; with a gold entry in the layers (unmarked by design) 2; with an unmarked flat / window gold entry (`neither`: reached through an order change among crosses / windows that the order alone also reads) 1.  Questions whose EVERY gold entry is of one class: via_standin 0, read_via_standin 2, layers 1, neither 0; questions with at least one marked gold entry 2 of 4.

### 2c. The gained golds, diffed against the read sets of the order without the stand-ins (`gain_diff.py`, exact: the same ordering and cap with the stand-ins dropped from the intake)

| bank | question | against | gold entry (origin x count) -> path |
|---|---|---|---|
| bank3 | pa06 | order-only | layers/RUN/1A x1 -> layers entry: not marked per entry (union over bundles) |
| bank3 | pa06 | off | layers/RUN/1A x1 -> layers entry: not marked per entry (union over bundles) |
| bank3 | pa09 | order-only | window/plain x2 -> window read only through the stand-ins (not read by the same order without them); window/window-evidence x2 -> window read only through the stand-ins (not read by the same order without them) |
| bank3 | pa09 | off | window/plain x2 -> window read only through the stand-ins (not read by the same order without them); window/window-evidence x2 -> window read only through the stand-ins (not read by the same order without them) |
| bank3 | pa18 | order-only | window/plain x4 -> window read only through the stand-ins (not read by the same order without them); window/window-evidence x3 -> window read only through the stand-ins (not read by the same order without them) |
| bank3 | pa18 | off | window/plain x4 -> window read only through the stand-ins (not read by the same order without them); window/window-evidence x3 -> window read only through the stand-ins (not read by the same order without them) |
| bank3 | uw15 | order-only | flat/RUN x1 -> read only through the tie-break; layers/RUN/1A x1 -> layers entry: not marked per entry (union over bundles) |
| bank3 | uw18 | off | flat/RUN x1 -> the crosses are read by the order alone too: the SET read differs (V3 pool), not a stand-in cross; layers/RUN/1A x1 -> layers entry: not marked per entry (union over bundles) |
| bank2 | I2-023 | off | flat/RUN x3 -> the crosses are read by the order alone too: the SET read differs (V3 pool), not a stand-in cross; layers/RUN/1A x4 -> layers entry: not marked per entry (union over bundles) |
| bank2 | I2-025 | off | layers/WORD/1A x1 -> layers entry: not marked per entry (union over bundles) |
| bank2 | I2-033 | off | flat/RUN x1 -> read only through the tie-break; flat/RUN x31 -> the crosses are read by the order alone too: the SET read differs (V3 pool), not a stand-in cross; flat/WORD x15 -> the crosses are read by the order alone too: the SET read differs (V3 pool), not a stand-in cross; layers/RUN/1A x3 -> layers entry: not marked per entry (union over bundles); layers/WORD/1A x2 -> layers entry: not marked per entry (union over bundles) |
| bank2 | R2-I017 | off | layers/WORD/1A x1 -> layers entry: not marked per entry (union over bundles) |
| bank2 | R2-I018 | off | window/window-evidence x1 -> window read only through the stand-ins (not read by the same order without them) |
| bank2 | R2-I019 | off | window/plain x1 -> window read in both; the entry is new: a start that holds only a stand-in, or a different cycle over the window; window/window-evidence x1 -> window read in both; the entry is new: a start that holds only a stand-in, or a different cycle over the window |

Counts of (question, origin, path) groups: bank2 vs off: layers entry: not marked per entry (union over bundles) x5; bank2 vs off: read only through the tie-break x1; bank2 vs off: the crosses are read by the order alone too: the SET read differs (V3 pool), not a stand-in cross x3; bank2 vs off: window read in both; the entry is new: a start that holds only a stand-in, or a different cycle over the window x2; bank2 vs off: window read only through the stand-ins (not read by the same order without them) x1; bank3 vs off: layers entry: not marked per entry (union over bundles) x2; bank3 vs off: the crosses are read by the order alone too: the SET read differs (V3 pool), not a stand-in cross x1; bank3 vs off: window read only through the stand-ins (not read by the same order without them) x4; bank3 vs order-only: layers entry: not marked per entry (union over bundles) x2; bank3 vs order-only: read only through the tie-break x1; bank3 vs order-only: window read only through the stand-ins (not read by the same order without them) x4.

## 3. The chance control (G1 3.2 / F2 L-492 form: another question's gold against this question's stand-in-derived candidates)

Pool of other golds: the 52 fulllead bank3 items of kinds two-facts / paraphrase / unknown-word (gold alternatives as in the bank).

* Candidates = the words of the entries marked `via_standin` (they exist only through a stand-in): questions with at least one: 5.  Own gold in them: **0 / 5**.  Other items' golds in them: **1/255** of the pairs (5 questions x 51 other golds), i.e. 0.20 other golds per question on average.
* Where the gold is inside a stand-in unit: pa17: 何年 -> ['1981年に']; pa20: 何丁目 -> ['愛知県名古屋市中川区4丁目']; uw14: 現在所属 -> ['落語協会所属']; uw15: 何年 -> ['は1970年から1978年まで', 'は1978年に']; uw16: 最大何台 -> ['年間15台程度', '最大15台']; uw19: 年 -> ['が1974年に', 'は1974年に12の'].
* Candidates = the stand-in units themselves (G1: 'granularity-derived, not evidence of the unknown word'): questions with at least one: 37.  Own gold inside a stand-in unit: **6 / 37**.  Other items' golds inside a stand-in unit: **33/1887** of the pairs, i.e. 0.89 per question.
* The whole list (every non-assembled entry): other items' golds hit per question: off 23/38, on 22/38 (sum over 38 questions; the list is long, so this is the background rate that the gold of a question has to beat).

Chance counts per unknown word (G1: the chance that a random RUN unit is a stand-in = stand-in units / RUN units of the corpus) are in the per-item table and in every answer (`standins[*].chance`).

## 4. Per item: unknown-word

| id | form (slot) | unknown words (type: stand-ins added / RUN units) | off: entries / gold (first pos) | on: entries / gold (first pos) | marked entries (gold in one) | flat/RUN off -> on | gold origins off | gold origins on | s off / on |
|---|---|---|---|---|---|---|---|---|---|
| b3_uw01 | predicate (-) | テーブル(T2: 1/3653), 高速化(T2: 11/3653) | 49 / no | 71 / no | 0 (0) | 40 -> 61 | - | - | 504 / 521 |
| b3_uw02 | slot (と) | ばれますか(T5: 0/3653) | 77 / yes (73) | 38 / yes (34) | 0 (0) | 37 -> 0 | w/pl,w/ev | w/pl,w/ev | 380 / 281 |
| b3_uw03 | predicate (-) | に使われる(T2: 1/3653) | 63 / no | 101 / no | 0 (0) | 43 -> 43 | - | - | 260 / 310 |
| b3_uw04 | predicate (-) | 現代社会(T2: 7/3653), することは何ですか(T2: 36/3653) | 28 / no | 28 / no | 0 (0) | 22 -> 22 | - | - | 220 / 330 |
| b3_uw06 | predicate (-) | 青海町内(T2: 46/3653), 示(T4: 6/3653) | 55 / no | 137 / no | 0 (0) | 40 -> 20 | - | - | 430 / 648 |
| b3_uw07 | predicate (-) | 天満橋地区(T2: 14/3653), 示(T4: 6/3653), 丁目(T2: 8/3653) | 15 / no | 15 / no | 0 (0) | 7 -> 7 | - | - | 213 / 151 |
| b3_uw08 | slot (と) | 文法(T2: 2/3653), でいう(T2: 5/3653), ボイス(T4: 277/3653), ばれますか(T5: 0/3653) | 37 / no | 6 / no | 0 (0) | 35 -> 0 | - | - | 756 / 519 |
| b3_uw09 | slot (に) | 内浦町内(T2: 46/3653) | 90 / no | 15 / no | 0 (0) | 69 -> 0 | - | - | 168 / 79 |
| b3_uw10 | slot (の) | 高原(T2: 4/3653) | 103 / no | 13 / no | 0 (0) | 91 -> 4 | - | - | 673 / 364 |
| b3_uw11 | predicate (-) | 市川町内(T2: 47/3653), 割合(T4: 35/3653) | 18 / no | 20 / no | 0 (0) | 0 -> 2 | - | - | 89 / 376 |
| b3_uw13 | standin (-) | ヒル(T2: 1/3653), フィギュア(T2: 1/3653), でどのように(T5: 0/3653) | 7 / yes (6) | 6 / yes (1) | 0 (0) | 0 -> 0 | w/ev | WORD,w/ev | 516 / 541 |
| b3_uw14 | predicate (-) | 風藤松原コンビ(T3: 2/3653), 現在所属(T2: 14/3653) | 53 / no | 38 / no | 0 (0) | 31 -> 28 | - | - | 447 / 321 |
| b3_uw15 | slot (に) | ビースティボーイズ(T2: 2/3653), 何年(T2: 119/3653) | 44 / yes (1) | 4 / yes (1) | 0 (0) | 43 -> 1 | RUN | RUN,layers | 328 / 389 |
| b3_uw16 | standin (-) | 488規格(T2: 4/3653), 最大何台(T2: 6/3653) | 142 / yes (68) | 106 / yes (1) | 2 (0) | 112 -> 100 | RUN,layers | RUN,layers | 577 / 526 |
| b3_uw17 | slot (と) | Cube(T4: 104/3653), Juice(T4: 33/3653), は何という(T2: 5/3653) | 21 / no | 18 / no | 0 (0) | 9 -> 9 | - | - | 305 / 325 |
| b3_uw18 | predicate (-) | 善五郎家(T2: 8/3653), しているものは何ですか(T2: 14/3653) | 14 / no | 11 / yes (1) | 0 (0) | 0 -> 1 | - | RUN,layers | 350 / 122 |
| b3_uw19 | predicate (-) | 計画案(T3: 3/3653), 年(T2: 119/3653), 何年(T2: 0/3653) | 75 / yes (1) | 113 / yes (1) | 0 (0) | 41 -> 87 | RUN,layers | RUN,layers | 402 / 439 |
| b3_uw20 | slot (と) | フット(T2: 1/3653), チョーク(T2: 3/3653), ばれますか(T5: 0/3653) | 36 / yes (1) | 77 / yes (1) | 0 (0) | 7 -> 37 | RUN,WORD,layers,w/ev | RUN,WORD,layers,w/ev | 285 / 192 |

## 4. Per item: paraphrase

| id | form (slot) | unknown words (type: stand-ins added / RUN units) | off: entries / gold (first pos) | on: entries / gold (first pos) | marked entries (gold in one) | flat/RUN off -> on | gold origins off | gold origins on | s off / on |
|---|---|---|---|---|---|---|---|---|---|
| b3_pa01 | standin (-) | 外面(T4: 26/3653), 何色(T4: 10/3653) | 45 / no | 46 / no | 0 (0) | 43 -> 43 | - | - | 126 / 461 |
| b3_pa02 | standin (-) | どのような(T5: 0/3653), 理念(T4: 16/3653), のまとまりとして(T5: 0/3653) | 15 / no | 14 / no | 0 (0) | 13 -> 13 | - | - | 360 / 81 |
| b3_pa03 | predicate (-) | 別(T4: 6/3653), び方は何ですか(T2: 4/3653) | 59 / no | 55 / no | 0 (0) | 39 -> 41 | - | - | 356 / 286 |
| b3_pa04 | predicate (-) | 別(T4: 6/3653) | 45 / no | 28 / no | 0 (0) | 39 -> 5 | - | - | 518 / 285 |
| b3_pa05 | predicate (-) | 鑑賞者(T3: 14/3653), ち(T5: 0/3653) | 114 / yes (1) | 11 / yes (9) | 0 (0) | 88 -> 8 | RUN,WORD,layers | WORD | 788 / 341 |
| b3_pa06 | standin (-) | けたあと(T5: 0/3653), 低音パート(T4: 431/3653) | 9 / no | 16 / yes (9) | 0 (0) | 1 -> 8 | - | layers | 465 / 334 |
| b3_pa07 | slot (が) | 歌手(T2: 2/3653), がひとりで(T5: 0/3653), 名義(T4: 48/3653) | 77 / no | 191 / no | 0 (0) | 65 -> 169 | - | - | 329 / 643 |
| b3_pa08 | slot (を) | 十代目(T2: 12/3653), から後の(T2: 6/3653), 当主(T4: 27/3653), どんな(T5: 0/3653), 名字(T4: 40/3653) | 68 / no | 48 / no | 0 (0) | 54 -> 36 | - | - | 374 / 484 |
| b3_pa09 | predicate (-) | 戦い(T4: 16/3653), 舞台(T2: 1/3653), 見込(T4: 4/3653) | 99 / no | 172 / yes (168) | 0 (0) | 69 -> 73 | - | w/pl,w/ev | 793 / 617 |
| b3_pa10 | predicate (-) | 488の(T2: 1/3653), 元(T2: 2/3653), 省略表記(T2: 3/3653) | 66 / no | 16 / no | 0 (0) | 63 -> 13 | - | - | 609 / 435 |
| b3_pa11 | slot (と) | のことを(T2: 36/3653), 関西側(T2: 2/3653), 運行会社(T2: 15/3653), は何という(T2: 5/3653), 路線名(T2: 7/3653) | 51 / no | 36 / no | 4 (0) | 30 -> 30 | - | - | 499 / 505 |
| b3_pa12 | standin (-) | 当時の(T2: 1/3653), 大衆(T4: 81/3653), 好(T4: 1/3653), まれたどんな(T5: 0/3653), 舞台芸能(T3: 1/3653) | 16 / no | 16 / no | 5 (0) | 6 -> 0 | - | - | 69 / 34 |
| b3_pa13 | predicate (-) | 湖岸(T4: 10/3653), 一番大(T4: 113/3653), きいものはどこですか(T3: 14/3653) | 17 / no | 22 / no | 5 (0) | 8 -> 8 | - | - | 212 / 205 |
| b3_pa14 | standin (-) | 供給(T4: 4/3653), 出(T4: 10/3653), 電気(T2: 2/3653), 出力(T4: 13/3653), 上限(T4: 24/3653) | 12 / no | 58 / no | 0 (0) | 1 -> 25 | - | - | 365 / 613 |
| b3_pa15 | slot (の) | をめぐる(T5: 0/3653), 騒(T4: 1/3653), ぎは(T2: 2/3653), 試験(T2: 2/3653), 妥当性(T3: 8/3653), をめぐる(T5: 0/3653), 論争(T4: 12/3653) | 36 / no | 44 / no | 0 (0) | 0 -> 7 | - | - | 463 / 569 |
| b3_pa16 | slot (と) | った先の(T2: 1/3653), 土地(T4: 68/3653), で何と何にふれあうことを(T3: 36/3653), 大切(T4: 78/3653) | 36 / no | 45 / no | 0 (0) | 0 -> 7 | - | - | 597 / 647 |
| b3_pa17 | predicate (-) | 西暦(T2: 1/3653), 何年(T2: 118/3653) | 20 / yes (11) | 28 / yes (18) | 0 (0) | 10 -> 10 | layers | layers | 641 / 614 |
| b3_pa18 | standin (-) | 深い(T4: 2/3653), 所でどれくらいの(T2: 8/3653), 深(T4: 0/3653) | 24 / no | 30 / yes (17) | 0 (0) | 8 -> 8 | - | w/pl,w/ev | 473 / 437 |
| b3_pa19 | standin (-) | 主星(T4: 23/3653), 周り(T4: 3/3653), 一周(T3: 11/3653), 何日(T2: 40/3653) | 184 / no | 131 / no | 0 (0) | 62 -> 9 | - | - | 1084 / 873 |
| b3_pa20 | standin (-) | 何丁目(T2: 9/3653) | 35 / yes (34) | 66 / yes (62) | 3 (0) | 0 -> 0 | w/ev | w/ev | 369 / 318 |

## 5. Time and the read

Seconds per question (10 workers, the machine shared with the test suites and the other sweep steps; load 4-17): off median 391.0 max 1084.2; on median 382.8 max 872.6.
Questions whose flat tier lists something: RUN off 32 / on 32; WORD off 26 / on 25; CHAR off 2 / on 4 (of 38).

## 6. bank2 fulllead (intra2 69 + unans 25), combined fast, grammar on, against the off baselines

Baselines: (1) the recorded T10 flat + layers lists and the G3-g window lists (T10 flat 16, flat + layers 21, combined 29 of 69 at fast); their windows were read on the z_deep-slide placements while this tree reads the committed defaults (z_deep order, G3-i), so only the FLAT block (same ordered cache, equiv-checked: `equiv_off.txt` re-runs the off path on the cheapest questions against the T10 records) is strictly comparable with them; (2) the grammar-off run of THIS tree (same code, same window placements) when `bank2_fast_off.jsonl` is present, the clean comparison for the combined list.

| system (intra2, n = 69) | flat block | flat + layers | combined (all blocks) |
|---|---|---|---|
| T10 / G3-g records (flat + layers T10, windows G3-g on z_deep slide) | 16 | 21 | 29 |
| **grammar off, this tree, live** (n = 69) | 16 | 21 | 28 |
| **grammar on, live (layers fixed, L-810)** | 18 | 25 | 33 |
| grammar on, 測定時に層の漏れあり (superseded: layer 1 held every stand-in's cross; `bank2_fast_on_layer1_leak.jsonl`) (n = 69) | 18 | 24 | 33 |

Questions whose combined gold differs between the leaking run and the fixed run: none.

Per origin: flat/RUN off 15, on 16; flat/WORD off 6, on 7; flat/CHAR off 0, on 0; layers off 11, on 18; window/plain off 7, on 8; window/window-evidence off 20, on 22.
Against the grammar-off run of this tree: combined gold lost 1 (R2-I020), gained 6 (I2-023 I2-025 I2-033 R2-I017 R2-I018 R2-I019).
Flat block alone: lost 4 (I2-012 I2-013 I2-017 R2-I001), gained 6 (I2-009 I2-022 I2-023 I2-033 I2-037 I2-042).  Against the T10 flat records (same caches): lost 4 (I2-012 I2-013 I2-017 R2-I001), gained 6 (I2-009 I2-022 I2-023 I2-033 I2-037 I2-042).

* grammar off (this tree): unans (n = 25): abstained (no candidate) 0 / list 25 / single (ANSWER) 0, list size median 39.0 max 267; intra2: ANSWER 0 / CHOICE 68 / none 1, confident wrong (ANSWER without the gold) 0; entries per question (intra2) median 29.0 max 152; seconds per question median 431.6 max 1188.5.
* grammar on: unans (n = 25): abstained (no candidate) 0 / list 25 / single (ANSWER) 0, list size median 30.0 max 202; intra2: ANSWER 0 / CHOICE 69 / none 0, confident wrong (ANSWER without the gold) 0; entries per question (intra2) median 32.0 max 368; seconds per question median 404.0 max 1279.7.
* Forms over the 94 questions: plain 2, predicate 50, slot 25, standin 17; questions with stand-ins: 70; T10 flat + layers recorded seconds per question: median 289.2.
* Entries marked `via_standin` (flat + windows): **11 entries in 5 intra2 questions + 13 entries in 7 unans questions (the unans questions get stand-in-only entries too: 7 of 25 have one)**; entries marked `read_via_standin` and not `via_standin`: 347 in 15 intra2 questions + 80 in 6 unans questions.

* The gold is in a `via_standin` entry for 1 intra2 questions (R2-I019), in a `read_via_standin` (not `via_standin`) entry for 6 (I2-021 I2-022 I2-029 I2-033 I2-042 R2-I018).

### 6b. Where the gained golds came from (intra2, combined, on against the off run of this tree; there is no bank2 order-only run, so a `neither` gold also contains what the order alone brings)

**bank2 intra2, on against off** (gold in a candidate on, none in the off run): 6 questions.

| question | gold entries on: origin (mark class) |
|---|---|
| I2-023 | flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); layers/RUN/1A (layers (unmarked by design)); layers/RUN/1A (layers (unmarked by design)); layers/RUN/1A (layers (unmarked by design)); layers/RUN/1A (layers (unmarked by design)) |
| I2-025 | layers/WORD/1A (layers (unmarked by design)) |
| I2-033 | flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (read_via_standin); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/RUN (neither); flat/WORD (neither); flat/WORD (neither); flat/WORD (neither); flat/WORD (neither); flat/WORD (neither); flat/WORD (neither); flat/WORD (neither); flat/WORD (neither); flat/WORD (neither); flat/WORD (neither); flat/WORD (neither); flat/WORD (neither); flat/WORD (neither); flat/WORD (neither); flat/WORD (neither); layers/RUN/1A (layers (unmarked by design)); layers/RUN/1A (layers (unmarked by design)); layers/RUN/1A (layers (unmarked by design)); layers/WORD/1A (layers (unmarked by design)); layers/WORD/1A (layers (unmarked by design)) |
| R2-I017 | layers/WORD/1A (layers (unmarked by design)) |
| R2-I018 | window/window-evidence (read_via_standin) |
| R2-I019 | window/plain (via_standin); window/window-evidence (via_standin) |

By mark (a gold can sit in several entries; a question is counted once per class it has): with a `via_standin` gold entry 1; with a `read_via_standin` (not `via_standin`) gold entry 2; with a gold entry in the layers (unmarked by design) 4; with an unmarked flat / window gold entry (`neither`: reached through an order change among crosses / windows that the order alone also reads) 2.  Questions whose EVERY gold entry is of one class: via_standin 1, read_via_standin 1, layers 2, neither 0; questions with at least one marked gold entry 3 of 6.

Lost against off: R2-I020.

* Own gold inside a stand-in unit by the kind of the unknown word: through a word that contains an interrogative 8 questions, through another unknown word 6 (a question can be in both).
* Chance control (intra2 golds): intra2 questions with a `via_standin` entry: 5, own gold in one: 1; other intra2 golds in them: 0/340 of the pairs.  Questions with stand-in units: 45, own gold inside a stand-in unit: 14; other golds inside a stand-in unit: 29/3060 of the pairs.

| id | form (slot) | stand-ins added | baseline combined gold (the grammar-off run of this tree) | on gold (first pos) | flat baseline | flat on |
|---|---|---|---|---|---|---|
| I2-001 | predicate (-) | 1 | no | no | no | no |
| I2-002 | slot (と) | 0 | yes | yes (32) | no | no |
| I2-003 | predicate (-) | 0 | no | no | no | no |
| I2-004 | predicate (-) | 0 | no | no | no | no |
| I2-005 | predicate (-) | 0 | no | no | no | no |
| I2-006 | predicate (-) | 0 | no | no | no | no |
| I2-007 | slot (に) | 14 | no | no | no | no |
| I2-008 | predicate (-) | 0 | no | no | no | no |
| I2-009 | predicate (-) | 8 | yes | yes (1) | no | yes |
| I2-010 | plain (-) | 0 | yes | yes (4) | yes | yes |
| I2-011 | predicate (-) | 0 | no | no | no | no |
| I2-012 | slot (と) | 0 | yes | yes (357) | yes | no |
| I2-013 | predicate (-) | 0 | yes | yes (7) | yes | no |
| I2-014 | predicate (-) | 0 | yes | yes (1) | yes | yes |
| I2-015 | slot (の) | 41 | no | no | no | no |
| I2-016 | plain (-) | 0 | no | no | no | no |
| I2-017 | predicate (-) | 1 | yes | yes (135) | yes | no |
| I2-018 | slot (と) | 11 | no | no | no | no |
| I2-019 | predicate (-) | 0 | no | no | no | no |
| I2-020 | predicate (-) | 44 | no | no | no | no |
| I2-021 | slot (を) | 36 | yes | yes (4) | yes | yes |
| I2-022 | slot (を) | 36 | yes | yes (3) | no | yes |
| I2-023 | predicate (-) | 8 | no | yes (1) | no | yes |
| I2-024 | standin (-) | 0 | yes | yes (33) | no | no |
| I2-025 | standin (-) | 10 | no | yes (13) | no | no |
| I2-026 | predicate (-) | 1 | no | no | no | no |
| I2-027 | slot (と) | 0 | yes | yes (1) | yes | yes |
| I2-028 | slot (と) | 1 | no | no | no | no |
| I2-029 | standin (-) | 35 | yes | yes (1) | yes | yes |
| I2-030 | predicate (-) | 1 | yes | yes (24) | no | no |
| I2-031 | standin (-) | 15 | yes | yes (269) | no | no |
| I2-032 | predicate (-) | 0 | yes | yes (2) | yes | yes |
| I2-033 | predicate (-) | 5 | no | yes (15) | no | yes |
| I2-034 | slot (に) | 119 | yes | yes (19) | no | no |
| I2-035 | predicate (-) | 1 | yes | yes (2) | yes | yes |
| I2-036 | standin (-) | 1 | no | no | no | no |
| I2-037 | predicate (-) | 2 | yes | yes (1) | no | yes |
| I2-038 | predicate (-) | 0 | no | no | no | no |
| I2-039 | predicate (-) | 17 | no | no | no | no |
| I2-040 | predicate (-) | 7 | no | no | no | no |
| I2-041 | predicate (-) | 4 | no | no | no | no |
| I2-042 | slot (の) | 47 | yes | yes (1) | no | yes |
| I2-043 | slot (に) | 10 | no | no | no | no |
| I2-044 | predicate (-) | 0 | no | no | no | no |
| I2-045 | slot (と) | 0 | yes | yes (30) | no | no |
| I2-046 | predicate (-) | 1 | no | no | no | no |
| I2-047 | slot (の) | 0 | no | no | no | no |
| I2-048 | predicate (-) | 0 | yes | yes (4) | yes | yes |
| I2-050 | slot (の) | 5 | no | no | no | no |
| R2-I001 | standin (-) | 6 | yes | yes (44) | yes | no |
| R2-I002 | slot (の) | 28 | no | no | no | no |
| R2-I003 | predicate (-) | 91 | no | no | no | no |
| R2-I004 | slot (に) | 157 | no | no | no | no |
| R2-I005 | standin (-) | 35 | yes | yes (2) | yes | yes |
| R2-I006 | predicate (-) | 12 | no | no | no | no |
| R2-I007 | slot (に) | 5 | no | no | no | no |
| R2-I008 | predicate (-) | 0 | no | no | no | no |
| R2-I009 | standin (-) | 9 | no | no | no | no |
| R2-I010 | predicate (-) | 1 | yes | yes (2) | yes | yes |
| R2-I011 | standin (-) | 132 | no | no | no | no |
| R2-I012 | standin (-) | 151 | no | no | no | no |
| R2-I013 | slot (の) | 11 | yes | yes (1) | yes | yes |
| R2-I014 | predicate (-) | 126 | no | no | no | no |
| R2-I015 | predicate (-) | 0 | yes | yes (4) | yes | yes |
| R2-I016 | predicate (-) | 153 | yes | yes (4) | no | no |
| R2-I017 | slot (を) | 0 | no | yes (1) | no | no |
| R2-I018 | predicate (-) | 30 | no | yes (130) | no | no |
| R2-I019 | standin (-) | 126 | no | yes (25) | no | no |
| R2-I020 | standin (-) | 32 | yes | no | no | no |

