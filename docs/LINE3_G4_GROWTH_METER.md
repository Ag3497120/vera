# LINE3_G4_GROWTH_METER — 重ねて成長する計器（初期配置に文書を 1 本ずつ重ね、答えが「現れる・残る・壊れる」を測る）

Author: the designer (2026-10-10). Target: `wt/line3` (branch line3), base HEAD `c3cd793c` (the commit that records the decision after G3-k).
This document is design only. No product code was written and nothing was built or run. The numbers marked (O) come from light reads of
`experiments/line3/bank2/{bank2.tsv,data/fulllead_sents.jsonl}` (article order, entry steps, unit counts per prefix: a few seconds of tokenising).
The numbers marked (C) are copied from committed records and were not reproduced here. (E) marks an estimate derived from (C).

**This is a measuring instrument, not a new reader.** It feeds documents into structures that already exist and asks with readers that already exist.
It writes records and does not change `verantyx/`. The gaps it shows (§1.3) become later tickets, and only after the owner has answered.

---

## 0. 読み方

| 印 | 意味 |
|---|---|
| 【オーナー】 | The owner's words, quoted verbatim, and nothing else |
| 【決定 x】 | A decision in `ops/decisions/2026-10-06_line3_faithful_build.md` |
| 【条件 n】 | The three conditions for plan 2 (出所・引き継ぎの印・順番の台帳). The auditor stated them and the owner did not object |
| 【推奨】 | The designer's proposal. It is not the owner's design |
| 【OP-G4-n】 | A point that carries meaning and that the owner's words do not settle (§5). Nothing beyond the 【推奨】 default runs until the owner answers |
| 【L-G4-n】 | An engineering choice that does not change meaning (§6). The implementer records it in `docs/LINE3_LOCAL_DECISIONS.md` |
| (O)/(C)/(E) | Counted by the designer here / copied from a committed record / estimated from (C) |

The rules are the same as everywhere in line 3. A tie means abstain, and no order makes a winner. Nothing is cut off silently. No floats.
The default output is byte-identical. In addition, the order of the documents is a recorded input (【条件 3】). It is the only order allowed to
shape a structure.

---

## 1. 拘束条件と「初期配置」の今の姿

### 1.1 この計器を決める言葉（逐語）

| 出所 | 【オーナー】 |
|---|---|
| 最終目標の確認（2026-10-10） | 「初期の文法層などの配置、汎用意味理解などの構造体での実装によって初期配置に文書を重ねることによってモデルが進化するもの。自然文の生成は必ずしも必要なく判断するモデルとしても良いと感じています。」 |
| 同・追記 | 「初期配置からそこにデータを重ねることで成長するもの学習不要で初期の薄い文法層や語彙でも問題なく入れた質問に対して回答が生成できること」 |
| G3-k の測定後の決定（次の本命の方向） | 「重ねて成長する計器を作る (Recommended)」— G1 の最小初期配置（助詞 + フィボナッチの腕）に fulllead の文書を 1 本ずつ重ね、重ねるたびに bank2 の同じ問いを投げて「答えが現れる・残る・壊れる」を記録する |
| オーナーの原則（2026-10-08） | 「立体十字構造体において初期配置と規則が大切です。」 |
| 「黄金比率」とは何か | 「初期の基盤からデータを入れるだけでモデルの初期作成者が意図する方向にモデルをユーザーが使うことでその方向に制御しながら成長できるものを人為的に作り出す。」 |
| 「最小限の初期配置」の材料 | 「助詞などで組むのと、言葉の粒度のものから未知語への自然対応に向けるところの最小構成を探す形で組む」 |
| G1 の決定 OP-G1-1 / OP-G1-3 | 「全ての十字の最初の状態に写す (Recommended)」／「フィボナッチの梯子（233/377 … 1/377） (Recommended)」 |
| G2 の決定 OP-G2-8 | 「軸では腕のラベルとして、文法層では十字ごとの参照として (Recommended)」 |
| 作る順番の決定（案 2） | 「２つ目に統合した形になったので案２で設計に入って」（案 2 の中身: 「赤の十字でパックされた圧縮された情報が隣にできた黒の十字にコピーされます。そこから黒の十字内で情報を積んでいって不安定状態になるとその上に赤の十字が構築されて…」） |
| G2-f の監査後 | 「入力があると各ソブリンに投入してそこから両替機のように形でタンクに入れるような様々な状況に対応するためのソブリンを組んでおいて構造体を進化させる形」 |
| T6ab の後 | 「…この狭い問題セットで点数を取ることが最終目標ではありません。候補が出るのは実際の利用者に採点してもらって最適化するためです。」 |
| 【条件 1〜3】（案 2） | (1) compression keeps the provenance, (2) inherited information is not counted again as new evidence, (3) the input order is fixed, written to the ledger, and the change in the answers under another order is measured |

The decision file has no section titled 「モデルの命題」. The nearest owner text is 「オーナーのモデル像」 and 「モデル像の具体化」 (2026-10-08), quoted above.

What these words fix for the instrument:
1. **The unit of growth is "a document stacked on the initial placement".** No learning: no weight is fitted, and the only thing that changes is the
   structure that the documents build.
2. **The judgement matters, not the prose.** A typed abstention, a list a user can reject, provenance, and no confident wrong answer all count
   as "回答". Assembling natural sentences is not required (G3-j already made the assembled strings display-only).
3. **"Thin" grammar layer and vocabulary.** The initial placement should be small. Growth comes from the documents.

### 1.2 「G1 の最小初期配置」はコードの上で今何か (O: code read)

| Artefact | Where | What it is | Does data sit in it? |
|---|---|---|---|
| The foundation F (P7 + Fibonacci ladder) | `grammar.py:48-97` `LADDER = (は, の, に, で, と, を, が)`, `WEIGHTS` = F(14−k)/377 (233/377 … 13/377), `foundation_obj()`, `foundation_sha()` | A constant made by hand: centre は 233/377, arms の 144, に 89, で 55, と 34, を 21, が 13 (/377). Exact Fractions, with a sha | — |
| The foundation cross | `grammar.foundation_cross()` (`grammar.py:616`), `rotated` (`:709`) | A `geometry.Cross` with L=1: centre は and the six particles on the arms in ladder order. Used as the grammar layer's reference cross per window (`GrammarCross`, `:624-665`) | **No.** It holds only the 7 particles |
| Arm labels of the windows | `slide.py:156-195` `P7_LADDER`, `Foundation` (a validated spec: distinct labels, strictly decreasing Fractions) | The labels and weights of the window crosses' axes (OP-G2-8 「軸では腕のラベルとして」) | Labels only. Data units sit on the window arms; the particles do not |
| The grammar records (adj, kind) | `grammar.build_records(texts)` (`:279`), `Records` (`:177`) | Counted from the data, per sentence: which P7 particle follows each content unit. `kind(c)` = the most frequent follower | Data-derived. Each sentence contributes on its own, so the records can be built prefix by prefix |
| The read order of the grammar layer | `wiring.ReadHook`, `cycle.plan_read(grammar=)`, `--grammar on\|off` (default off) | The foundation decides only the READ ORDER inside ties (G3-k, 「E_Q が先、単位数は同点内」) | No |

**What was never built (O: no `foundation=` exists in `placement.py` or `carry.py`):** the tickets G1-b ("基盤つきの配置", `build_cross(..., foundation=)`,
fixed constructed seats, contracted key 「継ぎ目」, attachment key `a`) and G1-c. The owner chose OP-G1-1 (a) 「全ての十字の最初の状態に写す」, but
OP-G1-4/5 (fixed or moving seats, where the attachment enters the key) were redirected into G2 (axes plus grammar layer) and never answered as
seat questions. G2 then placed the foundation as **labels and reference** (OP-G2-8), not as seats.

So, concretely: **「G1 の最小初期配置」 exists today as a reference (a constant cross with a sha, used as labels and as a read order). It does not exist
as a buildable starting state into which data is placed.** No data cross and no tower starts from the foundation's seats.

A minimal placement with "only particles and Fibonacci arms" can be constructed, because it is the constant `foundation_cross()` (sha `foundation_sha()`).
At step 0 it holds no data, so every question must abstain. That is the meter's first test (§2.1, T-G4-2). Its weakness is that nothing makes the
documents seat on it.

Why the foundation cannot be bolted onto the tower cheaply (O: code read): the data stream fed to a tower is the V2 space (`funcwords.default_filter`).
Particles are **removed** from it (L-150, the decision after T6v). A carried element seats only when a new occurrence of a word in its vocab arrives
(OP-1 (a), L-307/L-372, `CarryTower._woken`). A constructed "particle pack" copied into every black would therefore **never wake**, because no
particle occurrence ever arrives. Seating the foundation needs the G1 machinery (constructed seats that are fixed and transparent, 「継ぎ目」 §3.1.4).
That is placement code, not a measurement → OP-G4-1.

The parts of the "initial placement" that every arm below shares, stated so that nobody mistakes them for data (→ OP-G4-5):
the tokenisers (RUN = `verantyx.lang.ja_content_runs` + the gap pieces, WORD = fugashi/UniDic-lite short units, CHAR), the V2 function-word rule
(`funcwords.is_function_unit`, which uses UniDic POS for RUN and WORD), the placement rules (I-04 key, F1 ordered insertion, stop on collapse,
budget levels), the three-ratio cycle, and the foundation constant. **The UniDic dictionary is a large external vocabulary.** It is fixed and
not learned, but it is not "thin". The meter reports per tier, so the dictionary-light tiers (RUN, CHAR) stay visible.

### 1.3 「1 本重ねる」を今ある仕組みで言うと — 3 つの仕組みの判定

| Mechanism | What "add article k" does | State carried from k−1 to k? | Can earlier placements change? | Verdict |
|---|---|---|---|---|
| **M-C carry tower (案 2)** `carry.build_tower(..., after_sentence=)`, `CarryTower` | The article's sentences are fed in ledger order into the open black. If the black collapses it is closed and packed, the pack carries up, and the frontier is **copied** to the next black (OP-1 a) | **Yes.** It is a fold: tower_k = feed(tower_{k−1}, article k). The ledger numbers every event (C1 決定 「全ての出来事に番号」) | Closed units: **never** (a closed unit is never rebuilt, design C3/L-315; its pack's vocab is fixed at copy time, C1 決定). The open unit of each level re-settles when its scope grows (L-353) | **The only mechanism that stacks.** Faithful to 案 2 and to 【条件 1〜3】 |
| M-L layers (matryoshka, T8) `matryoshka.ask_layered` | Nothing persists. Layers are built **at question time** from the crosses read (「the check happens WHEN A QUESTION IS ASKED」, matryoshka.py header) | No | — | Not a document stack. It is part of the reader |
| M-P placement on the prefix (flat crosses, windows, combined) `line3 build` + `ask(index, structure="combined")` | Every seed's cross is placed again from the prefix's counts. n(x,y) and p(x,y) are corpus-wide, so any cross whose pool gains a co-occurrence can change | **No.** placement_k is a deterministic function of the prefix only, with no memory of placement_{k−1} | **Everything** that the new counts touch | **Not stacking** in the thesis' sense. It equals "stacking where every document may rearrange every earlier placement it touches" (the result is identical, history adds nothing). Kept as the **reference curve** (data-size curve) |

Why M-C is a true prefix (O: code read; it becomes a test, L-G4-4 / T-G4-3):
`occurrences_of(tier, sid)` reads only `tier.sentence_units[sid]`, and the unit cut of a sentence depends only on that sentence (space.py L-30..L-32, the
V2 predicate is per unit). Every count of a unit is taken over its own scope only (`LocalSpace`, design 3.5, L-323/L-327). Nothing looks ahead in the
stream. So the tower after k articles must equal the tower built on the first k articles alone. The only difference is the ledger header (`order_sha256`
covers the whole sid list), so the ledger events must be a leading prefix.

**The uncomfortable number (C, T9 `results/summary.md`, intra2 n = 69, fulllead, RUN tower at level low):** the faithful mechanism scored
**0–10/69** gold in a candidate (close-index-standard 7, defer-index-standard 10, both path descents 0–2, every fast run 0).
The one-shot reader scores **33/69** (G3-k, combined fast, grammar on), and the keyword baseline B2 scores 57. So the owner's decision names G1 + 「重ねる」,
but the only mechanism that stacks is the weakest reader in line 3, and it has no foundation in it (§1.2). The meter shows this gap rather than
hiding it: it runs M-C as the 「重ねる」 arm and M-P as the control, on the same questions, at the same steps (→ OP-G4-2).

What is missing for the literal thesis ("G1 foundation + stacking" in ONE structure):
- (gap 1) The foundation inside the tower: G1-b in the tower (constructed seats in every black's first state) → OP-G4-1.
- (gap 2) The grammar read order and the stand-ins in the tower reader: `carry_query.ask` has no `grammar=` and no `standins`. Its read order is
  (level desc, rq desc), L-314. Wiring them in, as G3-k did for the flat reader, is a reader change and lies outside G4.
- (gap 3) The tower exists for one tier at a time (T9 built RUN only). WORD and CHAR towers are possible (the code is tier-generic), but they have never
  been built on fulllead (C0 prototype: ~4.3 s / ~8 s per sentence, (C)).
- (gap 4) There is no window (slide) structure in the tower.

---

## 2. 手順（プロトコル）

### 2.1 文書の順と段

- **Order** 【L-G4-1】: the line order of `experiments/line3/bank2/data/fulllead_sents.jsonl` (sha256 `45efdaed…6cefe`, (C) t9 README).
  An article is a maximal run of equal `title`. There are **300 articles and 300 distinct titles**, 592 sentences, 125 one-sentence articles, and at most
  7 sentences per article (O). The order is fixed and recorded as the sha256 of the canonical list of titles, plus the tower's `order_sha256`
  of the sids (carry L-333).
- **Step k** 【L-G4-2】 = the first k articles. `prefix_k.jsonl` is the exact byte slice of the first lines of `fulllead_sents.jsonl`, and its sha256 is
  the data sha of every cache at step k.
- **Step 0** 【L-G4-3】 = no sentence. Tower: `build_tower` with no sids (one empty open black U0:0, empty carry). The foundation constant is recorded by
  its sha. Every question must come back `UNKNOWN_NO_EVIDENCE`, because rq = 0 everywhere (carry_query L-313/L-425). The control arm has no step 0
  (an index of 0 crosses is not something the reader takes), so it starts at step 1.
- **The reverse order** (【条件 3】 says the order change must be measured): the articles in reverse, with the sentence order inside each article
  kept. Tower arm only, at the staircase only 【L-G4-17】.

### 2.2 問い・入る段 (O)

All 94 fulllead questions of bank2 at every measured step: intra2 69 + unans 25 (cross2 and the s3000 unans belong to the other corpus and are not
asked). For each intra2 question, **e(q) = the article position of the title in `evidence`** (`title#i`) 【L-G4-5】. For each unans question,
**s(q) = the article position of its subject**. That is only a label, because unans questions have no evidence.

intra2 entry steps (O): 1, 2, 8, 9, 10, 12, 18, 19, 23, 24, 30, 33, 34, 43, 44, 44, 45, 48, 49, 53, 57, 57, 58, 59, 60, 60, 60, 61, 65, 66, 70, 70, 75,
77, 79, 82, 88, 88, 89, 89, 99, 105, 106, 106, 106, 107, 121, 142, 145, 148, 157, 158, 169, 169, 170, 173, 176, 186, 196, 196, 201, 208, 236, 250,
255, 261, 273, 292, 294 (59 distinct articles).
unans subject steps (O): 1, 3, 8, 9, 12, 18, 19, 26, 28, 34, 36, 43, 44, 45, 59, 60, 66, 68, 89, 93, 121, 131, 158, 255, 261.

**The implicit requirement:** before its article enters (k < e(q)), every intra2 question is unanswerable. At those steps the correct output is a typed
abstention, a list is a false presence, and a single answer is a confident wrong answer. So every intra2 question is its own unanswerable control at
every step before entry, and the 25 unans questions are that control at every step. The 2×2 judgement (§2.5) follows from this at every step, at no
extra cost.

### 2.3 階段（段の選び方）

| Schedule | Steps | Use |
|---|---|---|
| S-all | 1, 2, …, 300 (every article) | Tower arm, the two index-standard configs (§3.2): affordable |
| **S-fib** (the owner's Fibonacci numbers, plus 300) | **1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 300** | Every arm and every config |
| S-anchor(q) | e(q) + {0, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233}, clipped to ≤ 300 | Tower arm, per question: 現れる and 残る measured relative to entry |

What S-fib holds (O):

| step | 1 | 2 | 3 | 5 | 8 | 13 | 21 | 34 | 55 | 89 | 144 | 233 | 300 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sentences | 3 | 6 | 12 | 14 | 20 | 29 | 41 | 68 | 114 | 192 | 296 | 469 | 592 |
| intra2 entered (of 69) | 1 | 2 | 2 | 2 | 3 | 6 | 8 | 13 | 20 | 40 | 48 | 62 | 69 |
| unans subjects entered (of 25) | 1 | 1 | 2 | 2 | 3 | 5 | 7 | 10 | 14 | 19 | 22 | 23 | 25 |
| RUN / WORD / CHAR content units | 24/27/42 | 44/46/76 | 110/112/151 | 124/126/164 | 185/199/248 | 241/272/315 | 354/408/426 | 501/576/534 | 815/937/710 | 1317/1474/914 | 1972/2074/1062 | 2906/2919/1242 | 3653/3557/1358 |

Steps 2→3→5 add no new gold article. That is fine: those steps show whether stacking unrelated documents moves an answer that is already there.
The 7 questions whose article enters after 233 are seen on S-fib only at 300, so 残る cannot be measured for them there. S-anchor covers them
for the tower.

### 2.4 1 問 1 段の記録（per-question record）

One canonical-JSON line per (arm, config, step, question). The hashed part has no floats and no wall time 【L-G4-7】:

| Field | Content |
|---|---|
| ids | `arm` (tower / control), `config` (§3.2), `step`, `article` (title entered at this step), `prefix_sha256`, `structure_sha256` (tower: §3.1 snapshot identity; control: the sha of each tier's placement cache and of the window cache), `foundation_sha256`, `code_sha256` of every module read |
| question | `qid`, `kind` (intra2 / unans), `e` (or `s` for unans), `entered` = step ≥ e, `evidence_sid` (global sid of `title#i`; `null` if not yet in the prefix) |
| verdict | the reader's typed verdict (`ANSWER` / `CHOICE` / `UNKNOWN_*`), `listed`, per-source listed (control), `partial` / `left_unread` / `tied_group_not_split` |
| gold | `gold_in_candidate` (t9 `scorer.py`, unchanged 【L-G4-6】), `gold_entries` (indices), `first_gold_pos`, `single_wrong` = (verdict ANSWER and gold not in it) |
| provenance of the gold entry | `source_sids` of each gold entry; `gold_from_evidence` = some source sid is in the gold article (and separately `= evidence_sid`). Tower: the `chain` (unit, level, open/closed at this step, entrances, `lateral` = through an inherited pack). Control: `block`/`origins`, `via_standin`, `read_via_standin`. Pre-entry hits are kept and flagged (`pre_entry_hit`) |
| three ratios | for each gold entry: the reader's `stability` (Fraction "a/b") and the key. The meter runs the reader live, so it takes the end state from the live read object: flat cycle `TierResult.candidates[].end` (the source of `trace[].state`). Tower: `carry_query.read_unit` → `UnitRead.result.candidates[].end` on the unit's `ReadTier` (O: carry_query.py:166-204), even though `CarryAnswer.answer_obj()` does not serialise it. `energy.three_ratios` is recomputed independently on that state, and the three targets (section walk, edge flow, binding) are stored as Fractions with the unit they agree on. Store `"not_exposed"` (counted) only where even the live object has no end state (e.g. a layers or window entry whose member state the combiner does not keep); never reconstruct it by guess 【L-G4-14】 |
| answer bytes | `answer_sha256` = sha256 of the reader's `to_bytes()` (answer + thought, canonical), `answer_obj_sha256` = sha256 of the canonical `answer_obj()` alone |
| question-side growth | per tier, the question's content units and how many are in the prefix space; the G2-f pattern types T1..T5 of its RUN units; control with grammar on: the stand-in counts (`n_standins`, `chance`) 【L-G4-13】 |
| structure-side cause data | tower: the unit ids holding gold, whether each was read, `queue_left`. Control: the seeds of the gold crosses, whether they were read (`crosses_read`, `order_only_read`), and the cross bytes sha |
| cost (not hashed) | process CPU s, wall s, load1, host |

A `.meta.json` sits beside every run (argv, code sha256 per module, prefix and cache shas, PYTHONHASHSEED, Python version, host) 【L-G4-15】.

### 2.5 3 つの出来事と 2×2（summarizer の定義。測った段だけで数える）

For an intra2 question q, over its measured steps k_1 < k_2 < … at or after e(q):

| Event | Definition |
|---|---|
| **現れる** appear(q) | the first measured step ≥ e(q) with `gold_in_candidate`. Two delays are recorded: in articles (appear − e) and in measured steps. **直入** = appears at e(q). **成長** = appears only later (delay > 0): the gold needed documents stacked after its own article. Those cases get a provenance check: do the gold entry's sources include sentences of later articles? A question that never appears is recorded as such |
| **残る** stays(q) | gold held at every measured step from appear(q) to 300. The persistence ratio = measured steps holding gold / measured steps after appear. Byte-unchanged answers (`answer_obj_sha256` equal) are reported separately as **不変** |
| **壊れる** breaks(q) | the first measured step after appear(q) where either **消える** (no candidate holds the gold) or **単独誤答化** (verdict ANSWER with one entry that does not hold the gold). **戻る** = the gold is held again later. Every break gets a cause tag 【L-G4-9】: **配置** (the unit or cross that held the gold changed bytes), **読み** (that structure is unchanged but was not read: cap, order, exact skip), **採択** (read but not adopted, e.g. by the V3 pool) |
| pre-entry | at steps < e(q): the verdict class, plus `pre_entry_hit` (gold in a candidate before its article: the gold string occurs elsewhere, or chance) |

For an unans question: the verdict class at every step, and the event **単独誤答が現れる** (the first step with an ANSWER).

**2×2 at each step** (all 94 questions; rows from §2.2):

| | holds the gold, sourced from the evidence article | typed abstention (`UNKNOWN_*`, no entry) | list without gold | single answer without gold |
|---|---|---|---|---|
| evidence present (intra2, k ≥ e) | **correct** | miss | miss (rejectable) | confident wrong |
| evidence absent (intra2 k < e; unans at every step) | (impossible; flagged if it happens) | **correct** | false presence (rejectable) | confident wrong |

Curves per step and per config: entered, gold held, gold from evidence, 直入 / 成長, 残る, 壊れる by cause, single wrong, correct abstentions,
median list size, vocabulary known, and the rearrangement metric (§3.1 / §3.3).

### 2.6 「学習なし」の対照（one-shot）

- **Step 300 of the control equals the one-shot placement.** The existing records are the control, and nothing is rerun to get them:
  T10 (`experiments/line3/t10/results/ask_fulllead_{fast,standard}_ordered-stop.jsonl`: flat 16 / layers-ssp 21 fast, (C)) and the G3-k bank2 runs
  (combined fast: grammar off 28, on 33, (C); raw jsonl git-ignored on the Pro). Step 300 of the control arm, re-run from the step-300 cache, must
  reproduce a sample of 8 of these records byte for byte, the way G3-k checked 8 of 8 【L-G4-11】. If the code changed since, the report shows the diff.
- **Step 300 of the tower equals the T9 tower** (same data, same order, level low, same `pack_overflow`). The T9 carry records are its answers
  (`experiments/line3/t9/results/carry_fulllead_*`). The same byte check applies on a sample, or a diff is reported.
- The headline comparison is **tower at 300 vs one-shot at 300** (per question: both / tower only / one-shot only / neither), plus the whole curve of the
  tower against the control curve on S-fib.

---

## 3. 決定論・費用・置き場所

### 3.1 塔の腕（M-C）

- **One build per (tier, level, pack_overflow, order).** Use `build_tower(..., after_sentence=hook)`. The hook fires after each sentence, and at the last
  sentence of an article in the schedule it takes a snapshot 【L-G4-4】: a pickle of the tower (a local cache only, never compared) plus the
  **snapshot identity**: the sha256 of the canonical `{units, packs}` part of `CarryTower.to_bytes()` (without the `ledger` sha) and the sha256 of the
  ledger **events** so far. The ledger header is excluded because its `order_sha256` names the whole stream.
- The **prefix property** (test T-G4-3): for k ∈ {1, 2, 13, 89}, the tower built on the first k articles alone has the same snapshot identity, and its
  ledger events are exactly the leading events of the stream run.
- The **frozen-closed invariant** (T-G4-4): between consecutive snapshots, every closed unit's bytes (elements, scope, state, space sha) are unchanged.
  Only the open unit of each level, and new units, may differ. This is 案 2's structural promise. It is also the rearrangement metric of the tower
  (the number of units whose bytes changed per step) 【L-G4-12】.
- **Closed-black read invariant** (T-G4-12): a closed black read under the same question gives the same entries at every step (its read depends only on
  its own bytes and the question). Then in the tower a 壊れる can only be **配置** (the gold black was open) or **読み** (the descent or the cap did not
  reach it). To separate the two, the configs at S-fib include `effort=None` (unbounded descent) 【L-G4-8】.
- Configs 【L-G4-8】: RUN, level low (T9 parity), `pack_overflow` ∈ {close, defer} × descent `fallback` ∈ {None (path, the design), "index"} ×
  effort ∈ {fast, standard} at S-fib, plus `effort=None` at S-fib. The owner left both overflow rules (C3b) and both descents (C5 「新しい問いができてから両方測る」)
  as 測ってから決める, and in T9 only the index descent found anything. S-all and S-anchor: close-index-standard and defer-index-standard.
- **Cost (E, from the T9 records):** tower build 71 s CPU for all 592 sentences (close, (C)), done once per config family. Per question at step 300,
  median wall s in one worker (C, under load 5–15): close-index fast 2.2 / standard 5.1, defer-index 1.7 / 3.9, path 0.4–1.3. A question with
  rq = 0 everywhere returns at once (pre-entry questions whose words are absent).
  S-fib, all 8 configs: 13 × 94 × ~16 s ≈ 20,000 s. `effort=None` at S-fib: unknown (not run in T9); budget ≤ 30,000 s, with a stop at 3 h.
  S-all, two index-standard configs: 300 × 94 × (5.1 + 3.9) × ~0.6 (smaller towers early) ≈ 150,000 s. S-anchor: ~1,000 asks per config, ≈ 5,000 s.
  Reverse order at S-fib: ≈ 20,000 s. **Total ≈ 0.2–0.23 M CPU s ≈ 6 h on 10 cores.** Without S-all (S-fib + S-anchor only): **≈ 1.5–2 h**.
- **Where:** the Pro, 1 build process + 9 ask workers, after the running sweep ends (or the Air via `tools/air.sh`, as the compute-host memo says).
  The tower is a single sequential build, so sharding does not help it. The asks are embarrassingly parallel over (step, question).

### 3.2 対照の腕（M-P、作り直し）

- **Reader:** `ask(index, question, structure="combined", effort="fast")` with `--grammar on`, merge none, assembly on, every other option at the
  committed default. This is the current best reader, and its foundation is present as the read order. Grammar off is available at 300 from the
  records, and at other steps only if the owner asks 【L-G4-10】. The grammar records and the stand-ins are rebuilt from the prefix, so a word unknown
  at step k can be known at k+1. That is reported as vocabulary growth (§2.4).
- **Caches** 【L-G4-10】: one cache directory per step, keyed by the prefix sha, under `vera-impl/cache/g4/prefix_<k>_<sha12>/`: the three ordered
  placements (`line3 build --group-insert ordered --on-collapse stop`, level mid) plus the window cache. A cache is never reused across steps (the
  existing L-471 refusal of another corpus's cache stays). Step 300 = the existing `cache/t11` (= `cache/f1b` + windows): a free consistency check.
  An exact incremental re-placement (reuse a cross whose dependency key is unchanged) is NOT in v0. It is allowed later only after a byte-equality
  test against a from-scratch build on ≥ 3 steps.
- **Cost (E):** a full placement is RUN 3281 + WORD 4662 + CHAR 6582 = 14,525 CPU s (F1 ordered, (C)). Taking it as linear in the number of units
  (an upper bound: smaller prefixes have smaller pools), the 12 new S-fib prefixes need ≤ ~48,000 CPU s (≈ 1.3 h on 10 cores). Questions: the
  combined fast sweep of 94 questions took 4,125–4,686 s wall with 10 workers on the Pro (G3-k, (C)), so ≤ ~1.3 h wall per step at full size.
  8 of the 12 new steps have ≤ 68 sentences, which makes them cheap. The heavy ones are 89, 144 and 233. **Expected 5–8 h wall on the Pro;
  upper bound ~17 h.** `effort=None` is not run on the control (one question took ~16 min at `full` in T9).
- **Where (【推奨】): GitHub Actions**, extending `line3-sweep.yml` (it already has the probe → cache → sweep → summarize stages and byte-identity
  probes). Shard by (step × question shard). Per step, the cache jobs (3 tiers + windows) fit the 6 h job limit. With 18 shards × 4 vCPU this is
  ≈ 2–4 h. The workflow change is ticket G4-e, not this document.

### 3.3 バイト一致・マシンをまたぐ一致

- PYTHONHASHSEED=0 for every run. Exact Fractions only. The records hash canonical bytes, never pickles (F1c: "unchanged" is judged on placements,
  not pickle bytes).
- Seed independence (T-G4-8): 3 questions × steps {1, 34, 300} × both arms give identical `answer_sha256` under seeds 0 / 1 / 12345.
- Across machines 【L-G4-16】: extend `tools/determinism_probe.py` with the tower snapshot identity at steps {1, 34, 300} (RUN, low, close) and the
  RUN placement sha of prefix 34. The GHA probe stage then requires the Pro/Air values before any shard runs (as it does for RUN/WORD/CHAR today).
  Python 3.11 (Pro) vs 3.13 (cloud): only canonical bytes are compared, so pickles are rebuilt per host.
- Rearrangement metric of the control 【L-G4-12】: per tier and step, the number of crosses whose canonical bytes changed since the previous measured
  step, plus new crosses. Expected to be large for common seeds. This is what the tower forbids for closed units.

### 3.4 事前登録の予測（測る前に書く。外れたら外れたと書く）

- P-1 (tower): most 現れる are 直入 (the article's sentences sit in the open black, which is an entrance, C5 L-420). Many 壊れる are **読み** once that
  black closes, and the unbounded descent recovers part of them. Very few 成長 cases.
- P-2 (tower): no **配置** break comes from a closed unit (structurally impossible, T-G4-4). Any 配置 break is an open-unit re-settle.
- P-3 (control): at 300 it equals the one-shot records (33 combined). The curve rises roughly with entered questions, and 配置 breaks concentrate on
  questions whose subject is a common unit (large pools are re-placed often).
- P-4 (both): the pre-entry row of the 2×2 is "list without gold" for the control almost everywhere (combined abstained on 0/25 unans, (C)), and
  "typed abstention" for the tower almost everywhere (T9 carry abstained on 7–25/25, (C)). The two arms sit in opposite corners of the
  judgement table.

---

## 4. チケット（実装は計測だけ。`verantyx/` は変えない）

| Ticket | Depends on | Owner answers needed | Files | Acceptance |
|---|---|---|---|---|
| G4-a 段と問い | — | OP-G4-6 (default S-fib + S-anchor) | `experiments/line3/g4/prefixes.py`, `schedule.py`, `tests/line3/test_g4_prefixes.py` | 300 articles and distinct titles; the concatenation of the prefixes = the file byte for byte; the e(q)/s(q) table equals §2.2; the S-fib table equals §2.3 |
| G4-b 塔の写し | G4-a | OP-G4-1 (a), OP-G4-2 | `experiments/line3/g4/tower_snapshots.py`, `tests/line3/test_g4_tower.py` | T-G4-2, -3, -4, -9, -12; snapshot identities written to a manifest |
| G4-c 計器の実行 | G4-b (tower), G4-e caches (control) | OP-G4-4 (records both anyway) | `experiments/line3/g4/meter.py` (`--arm tower\|control --config … --steps … --workers N --resume --check`) | the record schema of §2.4 (T-G4-10); worker errors recorded as `{"id","error"}`, not fatal; resume per (config, step, qid). The combined reader has never run on a corpus as small as steps 1–8 (≤ 20 sentences, 24–185 RUN units, windows over 1–8 articles): an error there is a finding about the reader. It is reported per step in the summary and never filtered out as noise |
| G4-d 出来事と表 | G4-c | OP-G4-3, OP-G4-4 | `experiments/line3/g4/events.py`, `summarize.py`, `tests/line3/test_g4_events.py` | T-G4-5, -6; `results/summary.md` with the curves, events, 2×2, causes, step-300 comparisons |
| G4-e 対照の階段 | G4-a | OP-G4-2 (whether the control is shown as a curve at all) | `.github/workflows/line3-sweep.yml` (`prefix` input), `tools/determinism_probe.py` | per-step caches keyed by the prefix sha; T-G4-7, -8, -11; the probe gate |
| (later, owner-gated) G4-f 土台を塔に | the answer to OP-G4-1 (b) | OP-G1-4/5/9 as seat questions | `placement.py`/`carry.py` (G1-b) | outside G4: it is a placement rule, not a measurement |

---

## 5. オーナーへの問い（意味に関わる。推奨を先頭に）

| id | Question | Options | Recommended |
|---|---|---|---|
| **OP-G4-1** | 土台をどう入れて始めるか。The G1 foundation exists only as a reference (§1.2) and cannot seat in the tower without new placement rules (V2 drops particles, so a particle pack would never wake) | (a) **Start now from what exists**: step 0 = an empty tower + the foundation constant by sha (it acts as labels and the read order only where a reader uses it). The tower arm has no foundation, the control arm has it as the read order. Build G1-b later as G4-f. (b) Build G1-b first (constructed seats in every black's first state, 「継ぎ目」, the attachment key), which needs the old OP-G1-4/5/9 answered as seat questions, then measure. (c) Copy the foundation into the first black as a pack (G1 R3): it would never wake, so this is not recommended | **(a)** |
| **OP-G4-2** | 「重ねる」とみなす仕組みはどれか | (a) **Only the plan-2 tower is 「重ねる」. Placement on the prefix is shown beside it as the reference curve** (it equals stacking where a document may rearrange everything). (b) Count placement on the prefix as 「重ねる」 too (then history plays no role: the article order still shapes a prefix placement, but only as the sid order that F1 already takes (tied members inserted in the seed's posting order, L-461; 「文の語順が初期配置の一部」), not as a memory of earlier placements). (c) Build a new "frozen flat" stack (new seeds placed against the prefix, earlier crosses never re-placed, read by the current reader): new index code | **(a)**, accepting that the tower is today's weakest reader (0–10/69 vs 33/69). The meter shows the gap instead of choosing for you |
| **OP-G4-3** | 文書が前の配置を並べ替えることは「成長」か「壊れる」か | (a) **Every lost gold counts as 壊れる and carries a cause tag (配置 / 読み / 採択)**. The meaning can be decided later on the data. (b) A loss by rearrangement, where a more stable gold-free state replaced the old one, counts as growth (置き換え), not 壊れる. (c) Forbid rearrangement: freeze the open units too (changes carry L-353; new rule) | **(a)** |
| **OP-G4-4** | 「問題なく回答が生成できる」を何で測るか | (a) Gold in a candidate after its article entered (the t9 scorer). (b) The 2×2 judgement: evidence present → a candidate holding the gold, sourced from the evidence article; evidence absent (before entry, unans) → a typed abstention, where a list does not count as abstaining. (c) **Both. The headline is the pair (present → gold from evidence; absent → correct abstention)**, per step | **(c)**: you said 「判断するモデルとしても良い」 and also 「回答が生成できること」 |
| **OP-G4-5** | 「薄い文法層や語彙」の範囲 | (a) **The initial placement = the foundation (P7 + ladder) only. The tokenisers, the UniDic dictionary and the V2 rule are a fixed apparatus shared by every arm, named as such, with per-tier reports** (RUN and CHAR are dictionary-light). (b) Count the dictionary as part of the initial placement, report that it is not thin, and add a dictionary-free arm (CHAR only, with a non-UniDic function rule: new code). (c) Also count the grammar records from the whole corpus at every step (not thin: they would see the future); not recommended | **(a)** |
| **OP-G4-6** | 階段 | (a) Every article (300 steps) for everything: the control alone would be ~300 × 1 h. (b) The Fibonacci staircase 1, 2, 3, 5, …, 233, 300 for everything. (c) **The tower at every article for the two index-standard configs, plus S-anchor; S-fib for all other configs and for the control** | **(c)** (≈ 6 h tower + 5–8 h control; without S-all ≈ 2 h + 5–8 h) |

Not asked (already decided): the article order is the file order (fixed, recorded); the reverse order is run because 【条件 3】 requires it;
one article per step; bank2's 94 fulllead questions.

---

## 6. 局所の選択（L-G4-n）

| id | Choice |
|---|---|
| L-G4-1 | Order = the line order of `fulllead_sents.jsonl`. An article = a maximal run of one `title`. Recorded: the sha256 of the canonical title list and carry's `order_sha256` of the sids |
| L-G4-2 | `prefix_k.jsonl` = the first lines of the file up to the end of article k, byte for byte. Its sha256 is the data sha of every step-k cache |
| L-G4-3 | Step 0 is a tower step only (an empty tower, every answer must be `UNKNOWN_NO_EVIDENCE`). The control starts at step 1 |
| L-G4-4 | Tower snapshots are taken in one stream pass via `after_sentence` at article ends. Identity = sha256 of the canonical `{units, packs}` part of `to_bytes()` + sha256 of the ledger events (the header is excluded). Pickles are a local cache only |
| L-G4-5 | e(q) = the article position of the evidence title; s(q) = that of the unans subject (a label only) |
| L-G4-6 | Grading = `experiments/line3/t9/scorer.py` unchanged. `gold_from_evidence` = a gold entry cites a sentence of the gold article (`= evidence_sid` recorded separately) |
| L-G4-7 | Records are canonical JSON (sorted keys, compact, UTF-8, no floats). `answer_sha256` is taken over the reader's `to_bytes()`, `answer_obj_sha256` over `answer_obj()`. Time and load sit outside the hashed part |
| L-G4-8 | Tower configs: RUN, level low; close/defer × path/index × fast/standard at S-fib; `effort=None` at S-fib (a 3 h stop, recorded as `partial`); index-standard × {close, defer} at S-all and S-anchor |
| L-G4-9 | Events are computed over measured steps only. Cause tags come from byte comparison of the gold-holding structure between the appear step and the break step, plus the read logs |
| L-G4-10 | Control = combined fast with grammar on; per-step caches keyed by the prefix sha; no reuse across steps; no incremental re-placement in v0 |
| L-G4-11 | Step-300 checks: the tower against the T9 carry records, the control against the T10 and G3-k records, 8 sampled questions each, byte-equal or a reported diff |
| L-G4-12 | Rearrangement metric: tower = units whose bytes changed between measured steps; control = crosses per tier whose bytes changed, plus new crosses |
| L-G4-13 | Vocabulary growth per question and step: content units per tier present in the prefix space, and the G2-f pattern types T1..T5 |
| L-G4-14 | Three ratios: the reader's stability and key; `energy.three_ratios` recomputed from the end state of the LIVE read object for every arm (flat `TierResult.candidates[].end`; tower `UnitRead.result.candidates[].end` on its `ReadTier`); `"not_exposed"` (counted) only where even the live object lacks it |
| L-G4-15 | A `.meta.json` per run: argv, code sha256 per module, prefix and cache shas, seed, Python version, host |
| L-G4-16 | Cross-machine identity via `tools/determinism_probe.py` (the tower at steps 1, 34, 300; the RUN placement at prefix 34); the GHA probe gate |
| L-G4-17 | Reverse order (articles reversed, sentence order inside each article kept): tower only, S-fib only; e(q) recomputed for that order |

---

## 7. 試験計画

| id | Test | Kind |
|---|---|---|
| T-G4-1 | Prefix slicing: 300 articles, 300 distinct titles; prefixes concatenate to the file; the shas are stable; the e(q)/s(q) tables equal §2.2 | unit |
| T-G4-2 | Step 0: an empty tower answers every one of the 94 questions with `UNKNOWN_NO_EVIDENCE`; the foundation sha is recorded and equals `grammar.foundation_sha()` | unit |
| T-G4-3 | Prefix property: for k ∈ {1, 2, 13, 89} (and a 9-sentence toy), tower(prefix k) has the same snapshot identity as the stream snapshot at k, and its ledger events = the leading events | unit + fulllead |
| T-G4-4 | Frozen-closed: between all consecutive snapshots, closed units are byte-unchanged; only open units and new units differ | fulllead (all 300) |
| T-G4-5 | Events on synthetic series: appear / 直入 / 成長, stays, 消える, 単独誤答化, 戻る, unmeasured steps skipped, pre-entry hits kept apart | unit |
| T-G4-6 | 2×2 classification of every verdict shape (ANSWER with and without gold, CHOICE with and without gold, each `UNKNOWN_*`, assembled-only entries not counted per G3-j) | unit |
| T-G4-7 | Step-300 equality with the existing records (8 sampled questions per arm) | fulllead |
| T-G4-8 | Seed independence: 3 questions × steps {1, 34, 300} × both arms under seeds 0 / 1 / 12345 give identical `answer_sha256` | fulllead |
| T-G4-9 | A step-k snapshot or cache is refused for step k' ≠ k (prefix sha / order sha mismatch) | unit |
| T-G4-10 | Record schema: canonical bytes, no float anywhere in the hashed part, every field of §2.4 present | unit |
| T-G4-11 | A control cache built for the full corpus is refused for a prefix (the existing L-471 refusal holds under the meter) | unit |
| T-G4-12 | Closed-black read invariant: a closed black read under the same question gives byte-identical entries at every later step | fulllead (sampled) |

All tests run at PYTHONHASHSEED 0 / 1 / 12345. Tests on the full fulllead data run on the compute host, not on the Pro while it has a sweep running.
