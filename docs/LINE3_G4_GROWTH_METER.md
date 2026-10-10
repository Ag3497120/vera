# LINE3_G4_GROWTH_METER — 重ねて成長する計器（基盤を座らせた平面の十字を凍結して文書ごとに積み、答えが「現れる・残る・壊れる」を測る）

Author: the designer (first version 2026-10-10; this revision 2026-10-10, after the owner's answers). Target: `wt/line3` (branch line3), base HEAD
`fa70eb16` (the commit recording OP-G4-5). The working tree also holds uncommitted G3-k2 changes (`flat_order`, in `ask.py`, `cycle.py`, `wiring.py`,
`combined.py`, `cli.py`). G4 code starts only after those are committed. This document is a design and implementation plan only. No product code was
written, and nothing was built or run. (O) = counted by the designer from light reads of `experiments/line3/bank2/{bank2.tsv,data/fulllead_sents.jsonl}`.
(C) = copied from committed records. (E) = an estimate derived from (C).

**What changed in this revision.** The owner answered every G4 question (§1.4), mostly NOT with the options I had recommended. The carry tower is no longer
an arm. The 「重ねる」 mechanism is a NEW frozen flat stack (§5). It is built on the G1 foundation, seated first in every cross (§4). §1–§3 keep the
facts. Everything from §4 on is the plan under the owner's choices. The options he declined are listed in §13.

---

## 0. 読み方

| 印 | 意味 |
|---|---|
| 【オーナー】 | The owner's words, quoted verbatim, and nothing else |
| 【決定 x】 | A decision in `ops/decisions/2026-10-06_line3_faithful_build.md` |
| 【条件 n】 | The three conditions for plan 2 (出所・引き継ぎの印・順番の台帳) |
| 【導出】 | A point the owner's words leave open, derived here from binding decisions (§12 shows each derivation). Not a guess |
| 【L-G4-n】 | An engineering choice that does not change meaning (§10). The implementer records it in `docs/LINE3_LOCAL_DECISIONS.md` |
| (O)/(C)/(E) | Counted here / copied from a committed record / estimated from (C) |

The rules are the same as everywhere in line 3. A tie means abstain, and no order makes a winner. Nothing is cut off silently. No floats. Every
default output stays byte-identical. The document order is a recorded input (【条件 3】), and it is the only order allowed to shape a structure.

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
| G1 の決定 OP-G1-1 / OP-G1-3 | 「全ての十字の最初の状態に写す (Recommended)」／「フィボナッチの梯子（233/377 … 1/377） (Recommended)」 |
| G3 の決定 OP-G3-6 | 「梯子の順に x、y、z へ。重みは辺の流れと配置の結合と読む順に (Recommended)」（L-529: は is the centre side, on no arm; の +x 144, に −x 89, で +y 55, と −y 34, を +z 21, が −z 13, over 377） |
| 【条件 1〜3】（案 2） | (1) compression keeps the provenance, (2) inherited information is not counted again as new evidence, (3) the input order is fixed, written to the ledger, and the change in the answers under another order is measured |

What these words fix: the unit of growth is "a document stacked on the initial placement". No weight is fitted. The judgement matters, not the prose:
a typed abstention, a list the user can reject, provenance, and no confident wrong answer all count as 「回答」.

### 1.2 「G1 の最小初期配置」はコードの上で今何か (O: code read)

| Artefact | Where | What it is | Does data sit in it? |
|---|---|---|---|
| The foundation F (P7 + Fibonacci ladder) | `grammar.py:48-97` `LADDER = (は, の, に, で, と, を, が)`, `WEIGHTS` = F(14−k)/377, `foundation_obj()`, `foundation_sha()` | A hand-made constant: は 233, の 144, に 89, で 55, と 34, を 21, が 13 (/377). Exact Fractions, with a sha | — |
| The foundation cross | `grammar.foundation_cross()` (`:616`) | A `geometry.Cross` with L=1: centre は, and the six others on +x −x +y −y +z −z. It is the grammar layer's reference per window | **No** |
| Arm labels of the windows | `slide.py` `P7_LADDER`, `Foundation` (L-529, L-560) | Labels and weights on the window crosses' axes | Labels only |
| The grammar records | `grammar.build_records`, `records_of_space`, `Records` | Per sentence and content unit (RUN, WORD; CHAR has none, L-541): which P7 particle follows it on the WORD cut | Data-derived, per sentence |
| The read order of the grammar layer | `wiring.ReadHook`, `--grammar on\|off` (default off) | The foundation sets only the read order inside E_Q ties (G3-k, G3-k2 `flat_order`) | No |

**Never built:** G1-b ("基盤つきの配置": `build_cross(..., foundation=)`, fixed constructed seats, the seam, the adhesion key a). No `foundation=` exists
in `placement.py`. The owner has now answered the seat questions (OP-G1-4/5/9, §1.4), so G1-b is buildable. It is the first prerequisite here (§4).

The apparatus that every arm shares: the tokenisers (RUN = `verantyx.lang.ja_content_runs` + the gap pieces; WORD = fugashi/UniDic-lite short units;
CHAR = single characters), the V2 function rule (`funcwords.is_function_unit`: UniDic POS for RUN and WORD, **the hiragana range for CHAR, no
dictionary**), the placement rules (I-04, F1 ordered insertion, stop on collapse, budget levels), and the three-ratio cycle. By OP-G4-5 the UniDic
dictionary now **counts as part of the initial placement** (it is not thin), and a dictionary-free arm is measured beside it (§7.1 arm B).

### 1.3 「1 本重ねる」の仕組み — 既存のものと、新設する第 3 の機構

The owner's 「第 3 の機構」 counts the stacking mechanisms: the carry tower, re-placement on the prefix, and now the frozen stack. M-L is listed only for
completeness: it is part of a reader, not a stacking mechanism.

| Mechanism | What "add article k" does | State carried from k−1 to k? | Can earlier placements change? | Role now |
|---|---|---|---|---|
| M-C carry tower (案 2) `carry.build_tower` | Sentences fed into the open black, which closes, packs and carries up | Yes (a fold) | Closed units never. The open unit re-settles | **Not an arm** (OP-G4-2). T9: 0–10/69 gold in a candidate (C) |
| M-L layers (T8) `matryoshka.ask_layered` | Nothing persists: the layers are built at question time | No | — | Part of a reader. Not used here |
| M-P one-shot placement on the prefix (`line3 build`) | Every seed's cross is placed again from the prefix counts | No (a function of the prefix only) | Everything that the new counts touch | **Arm C, the reference curve** (§7.1) |
| **M-F frozen flat stack (new, `verantyx/line3/stack.py`)** | The crosses of the seeds in article k are opened or grown. Earlier seated units never move | **Yes**: stack_k = step(stack_{k−1}, article k) | No seated unit moves. A held class can only narrow, and empty seats can only fill (§5.4) | **Arms A and B** |

Facts (C) that frame the comparison: the one-shot flat reader at step 300 scores 16/69 gold in a candidate (T10 flat fast, ordered-stop, grammar
off). The combined reader scores 33/69 (G3-k, combined fast, grammar on). B2 (keyword) scores 57/69. The stack is read by the **flat** reader
(§6), so its natural reference is the flat 16, not the combined 33.

---

## 2. 文書の順・段・問い（事実）

### 2.1 文書の順と段

- **Order** 【L-G4-1】: the line order of `experiments/line3/bank2/data/fulllead_sents.jsonl` (sha256 `45efdaed…6cefe`, (C) t9 README). An article
  is a maximal run of equal `title`: **300 articles and 300 distinct titles**, 592 sentences, at most 7 sentences per article (O). The order is recorded
  as the sha256 of the canonical title list.
- **Step k** = the first k articles. `prefix_k.jsonl` = the exact leading byte slice of the file, and its sha256 is the data sha of every step-k
  cache. Sids are global line numbers, so a sid means the same sentence at every step.
- **Step 0** = no sentence, so there is no cross (a cross needs a centre word, L-77). Every question must come back `UNKNOWN_NO_STATE` (T-G4-2).
- **Reverse order** (【条件 3】): articles reversed, with the sentence order inside each article kept. Arm A at step 300 only 【L-G4-17】.

### 2.2 問いと入る段 (O, recomputed from bank2.tsv)

All 94 fulllead questions of bank2: intra2 69 + unans 25. **e(q)** = the article position of the title in `evidence` (`title#i`). **s(q)** = the
article position of an unans subject (a label only).

intra2 e(q): 1, 2, 8, 9, 10, 12, 18, 19, 23, 24, 30, 33, 34, 43, 44, 44, 45, 48, 49, 53, 57, 57, 58, 59, 60, 60, 60, 61, 65, 66, 70, 70, 75, 77, 79,
82, 88, 88, 89, 89, 99, 105, 106, 106, 106, 107, 121, 142, 145, 148, 157, 158, 169, 169, 170, 173, 176, 186, 196, 196, 201, 208, 236, 250, 255,
261, 273, 292, 294 — **58 distinct articles** (the first version said 59: a miscount).
unans s(q): 1, 3, 8, 9, 12, 18, 19, 26, 28, 34, 36, 43, 44, 45, 59, 60, 66, 68, 89, 93, 121, 131, 158, 255, 261.

Before its article enters (k < e(q)), every intra2 question is unanswerable. So every intra2 question is its own unanswerable control at every step
before entry, and the 25 unans questions are that control at every step.

### 2.3 計器の段（OP-G4-6 の答え）

【決定 OP-G4-6】 「フィボナッチの階段 + 各問の記事が入った段」: **S = S-fib ∪ {e(q)}**, where S-fib = 1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 300.
That is **66 measured steps** (O): 1 2 3 5 8 9 10 12 13 18 19 21 23 24 30 33 34 43 44 45 48 49 53 55 57 58 59 60 61 65 66 70 75 77 79 82 88 89 99 105
106 107 121 142 144 145 148 157 158 169 170 173 176 186 196 201 208 233 236 250 255 261 273 292 294 300.
"入った直後の段" = step e(q): the first step whose prefix holds the article. The sum of prefix sizes over S = 14,202 sentences = **24.0 × the full
corpus** (O). This number drives the cost in §8. Over S-fib alone it is 1,856 = 3.14 × (O).

| S-fib step | 1 | 2 | 3 | 5 | 8 | 13 | 21 | 34 | 55 | 89 | 144 | 233 | 300 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| sentences | 3 | 6 | 12 | 14 | 20 | 29 | 41 | 68 | 114 | 192 | 296 | 469 | 592 |
| intra2 entered (of 69) | 1 | 2 | 2 | 2 | 3 | 6 | 8 | 13 | 20 | 40 | 48 | 62 | 69 |
| unans subjects entered (of 25) | 1 | 1 | 2 | 2 | 3 | 5 | 7 | 10 | 14 | 19 | 22 | 23 | 25 |
| RUN / WORD / CHAR content units | 24/27/42 | 44/46/76 | 110/112/151 | 124/126/164 | 185/199/248 | 241/272/315 | 354/408/426 | 501/576/534 | 815/937/710 | 1317/1474/914 | 1972/2074/1062 | 2906/2919/1242 | 3653/3557/1358 |

---

## 3. 既知の費用（事実）

| Fact | Value | Source |
|---|---|---|
| One-shot F1 ordered placement, full fulllead, CPU s | RUN 3281, WORD 4662, CHAR 6582 (sum 14,525) | (C) f1/summary.md |
| Same, RUN, the F1b cache build | 3653 crosses, 1762 s wall / 3524 s CPU at 2 workers | (C) `experiments/line3/f1b/build_cache.log` |
| Flat reader, fast, one fulllead question (3 tiers) | 115–130 s single process at Air load 6–9 (F1b probe); T10 sweep median 167 s / max 414 s wall under load 28 | (C) t10/README.md, t10/results/summary.md |
| Combined fast, 94 questions | 4,125–4,686 s wall with 10 workers on the Pro | (C) G3-k |
| GHA runners (public repo) | 4 vCPU / 16 GB per job, ≤ 20 jobs at once, 6 h per job; probe → cache → sweep → summarize in `line3-sweep.yml` | (C) the workflow header |

Note: the brief I was given quoted "flat build 22 min for 300 sentences at 2 workers". The primary record is RUN only, 592 sentences, 1762 s wall
(29 min) at 2 workers. I use the primary numbers.

---

## 4. 基盤を座らせる（G1-b、前提）

### 4.1 決まっていること

【決定】 OP-G1-1 「全ての十字の最初の状態に写す」, OP-G1-3 「フィボナッチの梯子」, OP-G1-4 「固定かつ継ぎ目」, OP-G1-5 「鍵の 3 番目 (n, p, a)」,
OP-G1-9 「腕＝関係の札」, OP-G3-6 (a) (the ladder on the axes; は on the centre side), OP-G4-1 「先に基盤を全ブラックに座らせる」.

【導出 D-1】 **The centre stays the data seed. The six arm particles take ring 1. は takes no seat and binds to the centre.** OP-G1-2 (whether the
centre is a data word or は) was never answered. The binding decisions settle it (§12):
(i) I-02 (the centre is found by search) and the decision 「中心には必ず語がある」 need a centre that can move among data words. A constructed は
centre is fixed (OP-G1-4), so no search would ever find a centre.
(ii) OP-G1-4 says 「両側のデータの語を隣とみなす」. That needs data on both sides of every foundation seat. In the `_Layout` edges, the only link between
arms is the centre. With a constructed centre removed, the cross falls apart into six separate chains, and the I-04 key no longer couples the arms.
(iii) L-529 / L-549 already place は 「centre side, on no arm」.
So the shape is the foundation cross of `grammar.foundation_cross()` with its centre given to the data. The six arm particles sit where its arms are,
and は is the relation of whatever data unit holds the centre.

### 4.2 基盤の席の仕様（`verantyx/line3/foundation.py`、新規）

- **Constructed tokens** 【L-G4-20】: the seat content is the string `"\u0000F:" + particle`. It never equals a data unit (no text unit contains NUL),
  and it never enters a space, a posting, n, p, N, r0 or E_Q (I-G1-2). `is_constructed(x)` = `x is not None and x.startswith("\u0000F:")`.
- **Position rule**: in every cross, on each of the six arms, the innermost seat (flat index `1 + a·L + (L−1)`, k = L−1) holds one arm particle:
  の, に, で, と, を, が (OP-G3-6 (a) order). L growth (L-65 `extend`) prepends empty OUTER seats, so the particles stay innermost forever. Under
  L-61 the arms are still a multiset of legs. The legs are now told apart by their particle, so arm identity = the particle (腕＝関係の札).
- **L** (L-G1-4): the smallest L with 6L+1 ≥ (data units) + 6. The seed alone is L=1 (centre + six particles). From the second data unit, L ≥ 2.
  The data seats at L are exactly the 6(L−1)+1 seats of a plain cross at L−1.
- **Moves** (OP-G1-4): a seat swap (i, j) is a move only if neither seat is constructed. L-77 stays (no empty centre). Rotations stay moves, but they
  are the identity under `canon`. The centre swaps with data seats as before (I-02).
- **The seam (contracted cross)**: the (n, p) edges are those of the cross with every constructed seat removed. On arm a, the data seats
  k = 0..L−2 are chained outer → inner, and seat k = L−2 links to the centre. The particle seat has no (n, p) edge. Because all six particles are
  innermost, **the contracted cross is exactly a plain flat at L−1**: drop seat k = L−1 of every leg. One function, `contract(flat, L) -> (flat', L')`,
  serves the key, the three ratios and the reader (§6). L' = max(1, L−1). The lone seed (L=1) contracts to `(seed, None×6)` at L=1.
- **Adhesion adj_T(v, p)** (L-G1-1 right-attached; per sentence): the number of **distinct sids** of the space's BASE sentences in which an occurrence
  of v ends where p begins.
  - RUN, WORD: from `grammar.records_of_space(space)` (default stem `straddle`; the WORD cut, punctuation skipped, L-542). adj = |{a.sid : a ∈
    Records.of(T, v), a.particle = p}|. This is L-G1-2 unchanged.
  - **CHAR (dictionary-free) 【L-G4-21】**: on the attribution-stripped text, the character at i is a CHAR unit v, and the character at i+1 is p ∈ P7
    (all seven are single characters). Nothing is skipped, and no tokeniser is used. This replaces L-G1-2 for the CHAR tier only, **in every arm**.
    So arm A's CHAR stack and arm B's stack are one and the same (§7.1).
  - Every count is reproducible with (sid, start, end, p_start) (I-G1-1). `adhesion_records(space, tier)` returns them, and the table is derived
    from them.
- **The key** (OP-G1-5 (a)): `(n, p, a_num)` lexicographic, larger is better. n and p = the I-04 sums over the contracted edges (the same `Weights`).
  a_num = Σ_arms Σ_{data v on the arm} F(p_arm)·adj_T(v, p_arm) + F(は)·adj_T(centre, は), with F = 144, 89, 55, 34, 21, 13 and 233. **Integers.**
  The denominator 377 is recorded and never divided 【L-G4-22】. (Under OP-G1-9 every data seat of an arm is bound to that arm's particle.)
- **Spec sha**: canonical JSON {format `line3.foundation_seats.v1`, `foundation_obj()`, arms → particle, centre relation は, position rule "ring1",
  seam "contract", attach {RUN: "records/straddle", WORD: "records/straddle", CHAR: "char_next"}, F numerators, 377}. Its sha256 → `seats_sha`.

### 4.3 `placement.py` の変更（foundation=None で既存のバイトは一切変わらない）

| Function | Change when `foundation` is given | When None |
|---|---|---|
| `build_cross(..., foundation=None)` | The start is the seed at the centre + the six particles (L=1) instead of the seed alone (L-63). `min_L` counts the 6. Placement gains `foundation` (the seats_sha) and `a_num` | Unchanged code path |
| `_layout` / `score_flat` / `_edge_sum` / `_swap_delta` | Use a `FoundationLayout(L)` whose `edges`/`inc` are those of the contracted cross, indexed over the full flat. Score = (n, p, a_num) | `_Layout`, (n, p) |
| `_scan` (moves, L-71) | Skip any pair (i, j) where a seat is constructed. Δa: a unit that changes arm (or moves to or from the centre) changes its F·adj term | Unchanged |
| `_insert_group` (L-64) | The empty seats are the candidates (a constructed seat is never empty). The gain is (Δn, Δp, Δa_num) over the incident contracted edges, plus F(p_arm)·adj(u, p_arm) for the target seat's arm (F(は)·adj(u, は) for the centre). All tied best gains are kept | Unchanged |
| `_settle` (L-71) | The triple key. Classes close under equal-triple-key moves | Unchanged |
| `find_twins` (L-90) | Also requires adj_T(u, p) = adj_T(v, p) for every p ∈ P7 (so a is invariant under the swap) | Unchanged |
| `group_order`, F1 ordered insertion (L-460/461), stop (L-463), budget (L-73/76) | **Unchanged** | — |
| `verify_class_foundation(tier, members, spec, adj)` (new, independent code) | Brute force: every non-constructed swap of every member, on the contracted cross with a recomputed from the adhesion records. No improving move, and the class is closed under equal-key moves | — |
| `contract_for_read(placement) -> Placement` (new) | The reader's view: every member contracted (L'), canonical, deduplicated, sorted. `cross` = the first. `twin_sets` carried. `arm_labels` kept aside (display only) | identity |

One consequence, recorded and measured (G1-b acceptance), not hidden: insertion compares the triple. A branch tied in (Δn, Δp) but worse in Δa is
dropped, so the (n, p) reached by greedy growth can differ from the foundation-off build. The decision's 「今の定義で区別できたものは変わらず」 holds
for each key comparison, not for every greedy path. G1-b reports the number of crosses whose contracted (n, p) differs from off.

Also changed: `ask.placement_key` adds `_found-<sha12>` only when on (L-G1-7). `Index(..., foundation=None)` and `load_placements` refuse a cache with
another seats_sha. `ask._Store.cross_for` returns `contract_for_read(p)` when `p.foundation` is set. CLI: `line3 build --foundation off|on` (default off).
With off, every committed byte is unchanged: `tests/line3/test_variants.py` GOLDEN, `tests/line3/test_matryoshka.py` GOLDEN_OLD, and the probe hashes
RUN `79b0a11f444ec220`, WORD `a44611defdd6bec4`, CHAR `51b97f502940dcc2` (`tools/determinism_probe.py`, the GHA gate).

---

## 5. 凍結した平面の積み（`verantyx/line3/stack.py`、新規）

### 5.1 状態

The stack is built per tier, independently (I-16: tiers never merge). For one tier, the state after step k is
`StackTier{tier, step k, prefix_sha256, title_order_sha256, seats_sha | None, level, crosses: {seed: StackCross}}`, where:

| StackCross field | Meaning |
|---|---|
| `seed` | The unit whose first appearance opened the cross |
| `L`, `members` | The held class: labelled flats (constructed tokens included), canonical sorted. **quotient off** (no twins, §5.5) |
| `seated` | `((unit, step), …)` in seating order. A unit is **seated** when the step that inserted it ends |
| `opened_at`, `closed_at` (None or a step), `closed_reason` | A cross closes at its first collapse (§5.3) and stays closed |
| `left` | `((step, unit, reason), …)`: the unit that collapsed, the rest of that step's candidates (`left_in_step`), and every later co-occurring unit (`left_after`) |
| `key`, `keyed_at` | (n, p, a_num) of the class at its last growth step, with that step's counts |

Every unit of prefix k owns exactly one cross at step k: `set(crosses) == set(tier_k.units())`. This is what `ask.load_placements` already requires.

### 5.2 1 段（文書 d = 記事 k+1）の操作 — これだけが状態を変える

1. Build `tier_{k+1}` from `prefix_{k+1}` rows (a full rebuild each step: tokenising ≤ 592 sentences takes seconds, 【L-G4-23】), plus the adhesion
   table of `tier_{k+1}` when the foundation is on.
2. D = the distinct units of the tier in d's sentences. Each u ∈ D is processed **independently** (crosses do not read each other). For the logs, D
   goes in code-point order.
3. **u is new (not in tier_k) → open its cross.** It is `build_cross(tier_{k+1}, u, quotient=False, group_insert="ordered", order="forward",
   on_collapse="stop", foundation=F, budget=level)`. Every co-occurring unit of a new u lies in d, so "the prefix" and "the document" give the same
   pool. All its units are seated at k+1. If it stopped by budget, `closed_at = k+1`.
4. **u has an open cross → grow it.** The candidates are V = {v : n_{k+1}(u, v) > 0, v not seated}. Because the cross is open, every earlier
   co-occurring unit was seated. So V = the units that first co-occur with u in d (asserted as an invariant). The order is M-1(b) on the current
   counts: groups by n_{k+1}(u, v) descending, and inside a group `group_order(tier_{k+1}, u, members)` (L-461: u's postings ascending, first
   occurrence). The document order therefore comes first, and the share order comes second, inside the document (【条件 3】). For each v in turn:
   `L2 = min_L(size + 1 [+ 6])`. `bases = extend(members)`. `_insert_group` and then `_settle` run with **`fixed_units` = the units seated before
   k+1** (plus the constructed seats). A seat is fixed iff its content is constructed or in `fixed_units`. Swaps only between non-fixed seats.
   The units inserted at k+1 may still move among themselves and the empty seats until the step ends.
5. **u has a closed cross →** nothing is inserted. `left_after` records V (N-05: the capacity was reached at the collapse).
6. **Every cross whose seed is not in D is byte-unchanged** (T-G4-5). It is not re-keyed, even though its pair counts may have changed.

The only change to `placement.py` for the stack: `_scan`, `_settle` and `_insert_group` take an optional `fixed_units: frozenset = frozenset()`.
The default keeps today's code path byte for byte.

**About the brief's "(b) open new crosses … when no seat accepts them":** in the flat plane every unit is a seed (L-63, I-08). The reader also
requires a cross for every unit (`load_placements`). So a new unit **always** opens its own cross (step 3). It is **also** seated in the open
crosses of every seed it co-occurs with (step 4). "No seat accepts" happens only for a closed cross, and then the unit is recorded in `left_after`. A
shared-cross reading (open a cross only when nobody accepts) is G1's R1, which the owner did not choose (OP-G1-1 → R2).

### 5.3 予算・閉じる

Level `mid` (the flat caches' level, L-210) 【L-G4-24】. A unit whose insertion or settle exceeds the budget is restored away (N-05). The rest of
that step's candidates are not inserted (L-463), and the cross **closes** (`closed_at`, `closed_reason` ∈ max_class / max_states / max_moves). N-05
makes the size at that moment the capacity, so a closed cross never grows again. This is what keeps the fold free of retry rules.

### 5.4 「並び替え」が凍結した積みで何になるか（OP-G4-3 の対象）

No seated unit ever moves. Between two steps j < k, a cross can change in exactly two ways, and only when its seed occurs in an article in (j, k]:

| Change | Definition (mechanical) |
|---|---|
| **充填** (fill) | units seated at a step in (j, k] (the fill can take the empty seat next to a gold path; L may grow, which adds an outer ring and moves nothing) |
| **絞り** (narrow) | some member of the class at j has no descendant at k. A descendant = a member whose seats hold, after `extend`, the same units on the same particle-labelled legs (foundation on) or on legs matched one-to-one (off) |

`arr_sha(X, k)` = the sha256 of the canonical `{L, members, seated}` of cross X at step k. **X was rearranged in (j, k]** ⇔ `arr_sha(X, j) ≠
arr_sha(X, k)` ⇔ 充填 or 絞り. Nothing else in the stack counts as rearrangement. A gold cross that is pushed out of the read cap is a READING change, and
a gold cross whose read changed only through the counts is an ADOPTION change (§7.4).

### 5.5 双子（L-90）を積みで使わない理由

Twin status depends on the pool's counts. Those grow every step, while the seats of a twin label would be frozen. A pair that is interchangeable
at step j can stop being interchangeable at k, and a held label class cannot express that. So the stack runs **quotient off** (the T4c search,
L-91), and every member holds actual units 【L-G4-25】. Consequence: on large crosses, classes grow faster than in the quotient flat build, so
crosses may close earlier. G4-d measures this before any question runs (gate G-2, §9).

### 5.6 台帳（1 段 1 行、追記のみ）

`ledger_<tier>.jsonl`, canonical JSON, one line per step: `{step, title, sids, prefix_sha256, opened: [seed…], grown: [{seed, seated: [unit…] (order of
insertion), L: [before, after], members: [before, after], narrowed: bool, key: [[n,p,a] before, after], a_gain}], closed: [{seed, reason,
left_in_step: [unit…]}], left_after: {seed: count}, adhesion: {attachments_added, by_particle: {p: count}}, state_sha256}`. `state_sha256` = the sha256 over
`(seed, canonical StackCross bytes)` sorted by seed: **the step identity**. With the foundation on, each seated unit's arm is recorded as the sorted
set of particles (or `centre`) it occupies across the members (`seats`). These are the "foundation attachments a".

### 5.7 決定論・写し・畳み込み

- **Determinism**: exact ints and Fractions, canonical sorted orders, PYTHONHASHSEED-free (as in placement.py). A step reads only `prefix_{k+1}` rows
  and the step-k state.
- **Snapshots** 【L-G4-26】: one pass from step 1 to 300. At every step the delta (the crosses changed at that step) goes to
  `stack/<tier>/<order>/<found>/delta_<k>.pkl`, and the manifest gets the step identity. The state at k = deltas 1..k composed (the last version of each
  seed). The loader recomputes `state_sha256` and refuses on a mismatch. Pickles are a local cache only. Only canonical bytes are compared.
- **The fold is true by construction**: `stack(1..k+1) = step(stack(1..k), article k+1)`. Nothing looks ahead (the prefix space of k+1 holds no row
  past article k+1), the step-k state holds everything the step reads, and no order comes from hashing. Test T-G4-4 checks it the hard way. In process 1,
  build 1..k and write the deltas. In process 2, load them and step k+1. Compare `state_sha256` with a single pass 1..k+1, for k ∈ {1, 2, 13, 34}
  and a 9-sentence toy. In addition, a stack built from `prefix_k.jsonl` alone must equal the step-k snapshot of the full pass (no lookahead).
- **Birth equals the one-shot build**: a cross opened at step k equals `contract_for_read(build_cross(tier_k, u, quotient=False, ordered, stop,
  foundation=F))`, member for member (T-G4-6). At step 1 every cross is a birth, so stack(1) = the one-shot quotient-off placement of prefix 1.

---

## 6. 積みを読む（ask の変更）

The reader (`cycle`, `readout`) **does not change**. The stack hands it standard `pl.Placement` objects.

1. **Read view** (`stack.read_view(StackCross, tier_k) -> pl.Placement`): `contract_for_read` of the class (§4.3). `size` = the data units seated.
   `stop` = "budget" if closed, else "exhausted". `candidates` = |{v : n_k(seed, v) > 0}|. `twin_sets` = (). `quotient` = False.
   `group_insert` = "ordered". `left_in_group`/`left_after` come from `left`. `score` = the contracted (n, p) recomputed on tier_k (display only;
   the reader does not select by it).
2. **`Index.from_stack(prefix_jsonl, stack_dir, step, tiers, foundation, order="forward")`** (ask.py): it builds the prefix space, composes and verifies
   each tier's state at `step`, and loads the read views. It records `{structure: "stack", step, state_sha256 per tier, seats_sha, order}` in the
   thought (placement records gain these fields only for a stack).
3. **`_Store(on_demand=False)` for a stack**: a seed without a cross raises an error. It never builds a one-shot cross silently.
4. **effort `full`** (which may rebuild a cross at a raised level, T6y) is refused on a stack index. `fast` (cap 4/tier) and `standard` (10) never rebuild.
5. **`space.build_space(rows, tiers=TIERS)`**: a new optional subset (the default bytes are unchanged), so arm B builds the CHAR tier only. The
   `Space` must accept a subset of tiers.
6. `grammar="on"` reads only `index.space` (the prefix): the records and stand-ins come from prefix k. T-G4-9 checks that no sid ≥ N_k appears in
   any grammar object.

Every tier (RUN, WORD, CHAR) is stacked and read for arm A. Arm B is the CHAR tier alone (§7.1).

---

## 7. 計器（`experiments/line3/g4/`）

### 7.1 腕と読み方（全ての腕で同じ読み手の設定。違いは表に書いたものだけ）

| Arm | Structure | Tiers | Reader `ask(…)` | Steps |
|---|---|---|---|---|
| **A** foundation + stack | M-F, foundation on | RUN, WORD, CHAR | `structure="flat", view="all", effort="fast", grammar="on"` (flat_order default eq_first) | all 66 |
| **B** dictionary-free | **the CHAR stack of A** (CHAR adhesion is char-level in every arm, §4.2) | CHAR | `tiers=("CHAR",), view="all", effort="fast", grammar="off"`, no stand-ins; run in a process where `fugashi`/`unidic_lite` cannot be imported | all 66 |
| **C** control, one-shot | M-P: `line3 build --group-insert ordered --on-collapse stop --level mid` on prefix k, foundation off (today's code), quotient on | RUN, WORD, CHAR | the reader of A | S-fib (13). Step 300 = the cache T10 used: `vera-impl/cache/f1b`, `placements_45efdaedb7ab_{RUN,WORD,CHAR}_mid_ordered-forward.pkl` (C: t10 `.meta.json`) |
| C_B | C's CHAR caches | CHAR | the reader of B | S-fib |
| A0 (diagnostic) | M-F, foundation **off** | RUN, WORD, CHAR | the reader of A | S-fib |
| C_F@300 (diagnostic) | one-shot, foundation on (the G1-b acceptance build) | RUN, WORD, CHAR | the reader of A | 300 |
| A_rev@300 (【条件 3】) | M-F, foundation on, reverse order | RUN, WORD, CHAR | the reader of A | 300 |

- **Why B runs on its own** 【L-G4-27】: B shares A's CHAR stack, but not A's reader. Grammar on is NOT inert for CHAR. CHAR has no records
  (kind none), but the read hook is given to every tier (`wiring.tier_kw`). Under `eq_first`, it splits an exact E_Q tie by the number of original
  question units a cross holds, which can change which CHAR crosses a cap of 4 reads. The question's grammar reading also uses the WORD cut
  (UniDic). So B runs directly at every measured step, with grammar off and with `fugashi`/`unidic_lite` imports blocked (`sys.modules[...] = None`).
  As a diagnostic, the summary reports how often B's answer equals A's CHAR-tier entries (no requirement).
- **Confounds, named**: A vs C differ in foundation, stacking (document-order insertion, frozen seats, closing) and quotient (off vs on). A0 vs C
  isolates stacking + quotient. A vs A0 isolates the foundation within the stack. C_F@300 vs C@300 isolates the foundation in a one-shot build.
- Step 300 of C must reproduce 8 sampled T10 records (`t10/results/ask_fulllead_fast_ordered-stop.jsonl`, grammar off) byte for byte when run with
  grammar off (the T10 settings). With grammar on, C@300 is new. A code drift since T10 is reported as a diff, never hidden 【L-G4-11】.

### 7.2 1 問 1 段の記録

One canonical-JSON line per (arm, step, qid). The hashed part has no floats and no time 【L-G4-7】.

| Field | Content |
|---|---|
| ids | `arm`, `step`, `article`, `prefix_sha256`, `structure_sha256` (stack: `state_sha256` per tier; one-shot: the cache file sha per tier), `seats_sha` or null, `code_sha256` per module read |
| question | `qid`, `kind`, `e` (or `s`), `entered` = step ≥ e, `evidence_sids` = the sids of article e(q) inside the prefix ([] before entry) |
| verdict | the typed verdict (`ANSWER` / `CHOICE` / `UNKNOWN_*`), `listed`, `partial`, `left_unread`, `tied_group_not_split`; per tier: verdict, entries, `read` seeds, `unread` count |
| gold | `gold_in_candidate` (`experiments/line3/t9/scorer.py`, unchanged 【L-G4-6】), `gold_entries`, `first_gold_pos`, `single_wrong` = (ANSWER and no entry holds gold) |
| provenance | per gold entry: `source_sids`, **`from_evidence`** = source_sids ∩ evidence_sids ≠ ∅, `origins` → (tier, seed) of the adopted states (`Candidate.seed`), and `pre_entry_hit` |
| structure of the gold crosses | per (tier, seed) of a gold origin: `arr_sha` (§5.4; one-shot: the sha of `Placement.to_bytes()`), `opened_at`, `closed_at`, seated count, whether read |
| answer bytes | `answer_sha256` (the reader's `to_bytes()`), `answer_obj_sha256` |
| question side | per tier: the question's content units and how many exist in the prefix space; A: `n_standins` |
| cost (not hashed) | CPU s, wall s, load1, host |

A `.meta.json` per run (argv, code shas, prefix and structure shas, seed, Python, host) 【L-G4-15】.

### 7.3 2×2（見出し）と併記

Each (arm, step, question) falls in exactly one cell. **The headline is the two "correct" cells.**

| | correct | miss / rejectable | confident wrong |
|---|---|---|---|
| **present** (intra2, k ≥ e(q)) | **some entry holds the gold AND `from_evidence`** | typed abstention (`UNKNOWN_*`); a list without gold; a list whose gold is not from the evidence article (`gold_not_from_evidence`, counted apart) | `ANSWER` single without gold |
| **absent** (intra2 k < e(q); unans at every step) | **typed abstention (`UNKNOWN_*`)** | a list (`CHOICE`, or `ANSWER` with gold = `pre_entry_hit`): false presence | `ANSWER` single without gold |

**Beside** (OP-G4-4 「候補に正解がある」も併記): `gold_in_candidate` per step (t9 scorer, any source). The flat reader assembles nothing, so G3-j does
not apply. An entry `from_evidence` before entry is impossible, and it is asserted.

Per step and arm, the curves are: present-correct / present, absent-correct / absent, confident wrong (both rows), gold in a candidate, median list
size, crosses read per tier, and (stacks) the crosses opened / grown / closed and the cumulative closed share.

### 7.4 現れる・残る・壊れる（OP-G4-3 の後の正確な定義）

For an intra2 q, M_q = the measured steps ≥ e(q) (e(q) is always measured). H_k = present-correct at k. G_k = gold in a candidate at k.

| Event | Definition |
|---|---|
| **現れる** | appear(q) = min{k ∈ M_q : H_k}. **直入** if appear = e(q). **後から** if appear > e(q): the delay in articles, and whether the gold entry's sources or its cross's seats include units seated after e(q) |
| never appears | a tag at 300: **未着** (no tier's prefix space holds the gold as a unit, and no path spells it), **未着席** (the gold unit exists but sits in no cross holding a question unit; `closed_before` if such a cross closed before the gold co-occurred), **未読** (such a cross exists but is unread), **未採択** (read, not adopted) |
| **残る** | H at every measured step from appear(q) to 300. Also reported with G |
| a **loss** at k | consecutive measured steps j < k with H_j and not H_k |
| **壊れる** | a loss that is (i) **単独誤答化**: the verdict at k is `ANSWER` with one entry without gold, whatever the cause; or (ii) any other loss in which **at least one** gold-holding cross X of step j (the (tier, seed) origins of its gold entries) is **U** or **A**, as defined below |
| **置き換え（成長）** | a loss that is not 単独誤答化 and in which **every** gold-holding cross X of step j is **R**. OP-G4-3: 「並び替えによる消失は「成長」— 壊れるには入れない」. It is counted in the growth columns, never in 壊れる |
| **戻る** | H again after a loss |

Cause per gold-holding cross X of step j, at the loss step k (mechanical, from the records):
**R** (rearranged) = `arr_sha(X, j) ≠ arr_sha(X, k)`: in the stack 充填/絞り (§5.4); in the one-shot arm a re-placement. **U** (unread) = equal
arr_sha, and X is not in the tier's `read` at k (the cap or the order changed: new crosses, other crosses' E_Q). **A** (not adopted) = equal arr_sha,
and X was read at k, but it gave no gold entry (the counts changed E_Q, the three ratios or the V3 pool). Every 壊れる and 置き換え stores the multiset
of tags, so a mixed loss is never hidden (it counts as 壊れる).

For unans questions and pre-entry steps: the verdict class at every measured step, and **単独誤答が現れる** (the first step with a single `ANSWER`).

### 7.5 事前登録の予測（測る前に書く。外れたら外れたと書く）

- P-1 (A): most 現れる are 直入. 後から ≤ 5 of 69.
- P-2 (A): at 300, A ≤ C@300 − 3 on gold in a candidate (document-order insertion plus closing seats fewer golds than the one-shot build).
- P-3 (A): among losses, U (read cap: more crosses hold question units as the prefix grows) > R > A. 単独誤答化 ≤ 2 over all steps.
- P-4 (A, C): the absent row is mostly "false presence" for both. The flat reader lists whenever a question unit's cross exists (C: T10 flat fast on
  unans = 23 CHOICE, 1 ANSWER, 1 UNKNOWN of 25). Absent-correct ≤ 5/25 on unans at 300 for both, and ≥ 1 confident wrong somewhere on the absent row.
- P-5 (B): ≤ 3/69 present-correct at 300 (T9 audit: CHAR contributed 1/69). Absent row like A.
- P-6 (A vs A0): |Δ present-correct| ≤ 3 at 300. The foundation acts through tie splitting and through which crosses close.
- P-7 (stack): the share of crosses closed at 300 is higher with the foundation on than off (arm-distinct ties grow classes; the risk in §13).

---

## 8. 費用と置き場所

**Model (E)**: one flat fast question at full size costs ≈ 120 s CPU (3 tiers; §3). It is taken as linear in the prefix size (sentences_k / 592).
This is an estimate: small prefixes have fewer and smaller crosses. Upper bound = full cost at every step. Builds are linear in the prefix (an upper
bound: smaller pools are cheaper).

| Item | Estimate (CPU h) | Upper (CPU h) | Notes |
|---|---|---|---|
| G1-b one-shot, foundation on, full (also C_F@300) | 4–12 | 12 | 14,525 s × a foundation factor of 1–3 (unknown until G1-b) |
| Stack passes A, A0, A_rev (3 tiers each; one pass gives all 300 steps) | 12–36 | 36 | each ≤ the one-shot full build × 1–3: a step settles only its own units, but classes are quotient-off |
| C prefix caches, 12 new S-fib steps | 8.6 | 8.6 | 2.14 corpus-equivalents × 14,525 s |
| Asks A (66 steps × 94) | 75 | 207 | 94 × 24.0 × 120 s |
| Asks B (66 steps, CHAR only, fugashi blocked) | 45 | 124 | 94 × 24.0 × 120 s × 0.6 (the CHAR share of a question, taken as ≤ 0.6) |
| Asks C, C_B, A0 (S-fib) | 10 + 6 + 10 | 30 + 20 + 30 | 94 × 3.14 × 120 s each |
| Asks C_F@300, A_rev@300 | 3 + 3 | 3 + 3 | 94 × 120 s each |
| **Total** | **≈ 180–220** | **≈ 500** | |

**Where** 【L-G4-28】: **GitHub Actions** on the public mirror. Unit tests and small probes (steps ≤ 34) run on the Air (`tools/air.sh`). The Pro runs
no G4 compute (compute-host arrangement; it also has a sweep running now). At 18 shards × 4 vCPU = 72 workers, the asks take ≈ 2.5–3.5 h wall (upper
≈ 7 h: split per arm, so that no job passes the 6 h limit). The stack passes need one job per tier per pass (sequential over steps; the touched crosses
of one step run in parallel over 4 workers), ≈ 1–3 h. The C caches: 12 steps × 3 tiers jobs, ≈ 1 h. **Wall total ≈ 9–13 h over four workflow runs**
(G1-b gate → stacks + gate G-2 → C caches → asks). On the Pro alone it would be ≥ 23–28 h at full use of 8 cores, which is not available.

Workflow 【L-G4-29】: a new `.github/workflows/line3-g4.yml` (not more inputs on `line3-sweep.yml`, whose stages assume one corpus file). Stages:
probe (the existing hashes + the stack identities at steps 1 and 34 RUN, T-G4-12) → `stack` (matrix tier × pass, artifact = deltas + manifest +
ledger) → `prefix-cache` (matrix step × tier, for C) → `ask` (matrix arm × shard; each shard composes the states it needs) → `summarize`.

---

## 9. チケット（実装: Sonnet、審査: Opus。順番どおり）

Common acceptance: change only the files listed. Number every judgement (L-G4-n / L-G1-n). With the foundation off and outside the stack, every
existing test and GOLDEN hash is unchanged. PYTHONHASHSEED 0/1/12345 give identical bytes. No float. Every cut is counted. Never open `vera-impl/hidden`.

| # | Ticket | Depends | Files | Acceptance (machine-checked) | Effort |
|---|---|---|---|---|---|
| 1 | **G1-a 基盤の席の仕様と付着** | — | `verantyx/line3/foundation.py` (new), `tests/line3/test_foundation.py` | spec sha stable; constructed tokens never in any space; adhesion for RUN/WORD equals the distinct-sid counts of `records_of_space`; CHAR char-level adjacency imports no fugashi (blocked-import test); every count re-derivable from (sid, span) and matching the text (I-G1-1); a float or a tied ratio raises | 0.5 d |
| 2 | **G1-b 基盤つきの配置** | 1 | `placement.py` (`foundation=`, `FoundationLayout`, `fixed_units`, `contract_for_read`, `verify_class_foundation`), `ask.py` (key `_found-`, `_Store` read view, `Index(foundation=)`), `cli.py` (`--foundation`), `tests/line3/test_placement_foundation.py` | T-G4-1; toy: two (n,p)-tied arrangements split by a; an (n,p)-decided toy unchanged by on/off in its contracted form; no generated move touches a constructed seat; every returned class passes `verify_class_foundation`; works with ordered/reverse/stop | 2 d |
| 3 | **G1-b 測定（関門 G-1）** | 2 | `experiments/line3/g4/gate1/` | full fulllead one-shot, foundation on vs off, 3 tiers: crosses by stop reason, size median, class size, contracted (n,p) differences, `f1/reach.py` reach (off = 41). Written as `gate1/summary.md`. **Stop and report to the owner if reach drops by > 5 or the max_class stops rise by > 25 %** (L-G4-31) | 0.5 d + GHA |
| 4 | **G4-a 段と問い** | — | `experiments/line3/g4/prefixes.py`, `schedule.py`, `tests/line3/test_g4_prefixes.py` | T-G4-3: 300 articles and titles; the prefixes are leading byte slices; e(q)/s(q) equal §2.2 (58 distinct); S equals §2.3 (66 steps, Σ sentences 14,202) | 0.5 d |
| 5 | **G4-b 凍結した積み** | 2, 4 | `verantyx/line3/stack.py`, `cli.py` (`line3 stack build --data --tiers --foundation --order --level --out`), `tests/line3/test_stack.py` | T-G4-4, -5, -6, -7, -8; ledger schema; deltas compose to the manifest identities | 2 d |
| 6 | **G4-c 積みを読む** | 5 | `ask.py` (`Index.from_stack`, `_Store(on_demand=False)`, refuse `full`), `space.py` (`build_space(tiers=)`), `tests/line3/test_ask_stack.py` | T-G4-2, -9, -10 (on a toy), -11; the read view passes the reader's existing checks; `build_space` default bytes unchanged | 1 d |
| 7 | **G4-d 積みの構築（関門 G-2）** | 5, 6, 3 | `experiments/line3/g4/build_stacks.py`, `.github/workflows/line3-g4.yml` (stack stage) | stacks A, A0, A_rev built; `gate2/summary.md`: per measured step and tier, crosses open/closed, the closed share, closures by reason, size and class medians; for each intra2 q, whether its gold unit sits in a cross holding a question unit at e(q). **Stop and report if > 50 % of those crosses closed before the gold co-occurred** (L-G4-32) | 0.5 d + GHA |
| 8 | **G4-e 計器の実行** | 6, 7 | `experiments/line3/g4/meter.py` (`--arm A\|B\|C\|C_B\|A0\|C_F\|A_rev --steps … --shard i/n --resume --check`), prefix caches for C | the §7.2 schema (T-G4-13); B runs in a process that cannot import fugashi/unidic_lite (T-G4-10); worker errors recorded as `{"id","error"}` and reported per step; resume per (arm, step, qid); C@300 grammar off reproduces 8 T10 records | 1.5 d |
| 9 | **G4-f 出来事と表** | 8 | `experiments/line3/g4/events.py`, `summarize.py`, `tests/line3/test_g4_events.py` | T-G4-14, -15; `results/summary.md`: the 2×2 per arm and step, gold in a candidate beside it, events with cause tags, never-appears tags, the step-300 A/C/A0/C_F/A_rev table per question, §7.5 predictions marked held or failed | 1 d |
| 10 | **G4-g ワークフロー仕上げ** | 8 | `line3-g4.yml` (prefix-cache, ask, summarize stages), `tools/determinism_probe.py` (stack identities) | T-G4-12; a dry run at steps {1, 2, 3} for all arms on GHA reproduces the Air bytes | 1 d |

Build order: 1 → 2 → 3 (gate G-1) → 4 (can run in parallel with 1–3) → 5 → 6 → 7 (gate G-2) → 8 → 9 → 10 → the measurement runs. **≈ 10.5
implementer-days plus ≈ 9–13 h of GHA wall.**

---

## 10. 局所の選択（L-G4-n）

| id | Choice |
|---|---|
| L-G4-1 | Order = the line order of `fulllead_sents.jsonl`. Article = a maximal run of one `title`. Recorded: the sha256 of the canonical title list |
| L-G4-6 | Grading = `t9/scorer.py` unchanged. `from_evidence` = a gold entry's source_sids meet the sids of the evidence article |
| L-G4-7 | Records = canonical JSON (sorted keys, compact, UTF-8, no floats). `answer_sha256` over `to_bytes()`. Time and load outside the hash |
| L-G4-11 | Step-300 checks: C (grammar off) against 8 T10 records; byte-equal or a reported diff |
| L-G4-15 | A `.meta.json` per run |
| L-G4-17 | Reverse order (articles reversed, inner order kept): arm A at step 300 only |
| L-G4-20 | Constructed token = `"\u0000F:" + particle` |
| L-G4-21 | CHAR adhesion = the next character is a P7 particle (no tokeniser, nothing skipped), in every arm. Supersedes L-G1-2 for CHAR only |
| L-G4-22 | a is held as an integer numerator over 377. The denominator is recorded, never divided |
| L-G4-23 | Each step rebuilds the prefix tier space from the prefix rows (no incremental space) |
| L-G4-24 | Stack budget level = mid (as the flat caches) |
| L-G4-25 | The stack runs quotient off (no twins) |
| L-G4-26 | Snapshots = per-step deltas + a manifest of `state_sha256`. The loader verifies the composed identity |
| L-G4-27 | B shares A's CHAR stack but runs its own reader (CHAR only, grammar off, no stand-ins) at all 66 steps in a process that cannot import fugashi/unidic_lite |
| L-G4-28 | Compute: GHA for builds and asks, the Air for tests and small probes, the Pro for none |
| L-G4-29 | A separate workflow `line3-g4.yml` |
| L-G4-30 | Events and cause tags are computed over measured steps only. A loss is 置き換え only if every gold-holding cross of the last holding step is R |
| L-G4-31 | Gate G-1 (after G1-b): stop and report if the foundation-on one-shot reach (`f1/reach.py`) is more than 5 below off (41), or the crosses stopped by max_class rise by more than 25 % in any tier. A designer's threshold: it stops work, it decides no meaning |
| L-G4-32 | Gate G-2 (after the stack build): stop and report if, for more than half of the intra2 questions, every cross holding a question unit had closed before the gold unit co-occurred with its seed. Same status as L-G4-31 |

---

## 11. 試験計画（T-G4-n）

| id | Test | Kind |
|---|---|---|
| T-G4-1 | foundation off: every existing test, `test_variants.py` GOLDEN, `test_matryoshka.py` GOLDEN_OLD and the three probe hashes are unchanged | unit + probe |
| T-G4-2 | step 0 (an empty stack index) answers all 94 questions `UNKNOWN_NO_STATE` | unit |
| T-G4-3 | prefixes, titles, e(q)/s(q), S (66 steps, Σ 14,202 sentences) | unit |
| T-G4-4 | **fold**: build 1..k, write, load in a new process, step k+1 → the same `state_sha256` as one pass 1..k+1 (k ∈ {1, 2, 13, 34} + a toy); a stack from `prefix_k.jsonl` alone = the step-k snapshot | unit + fulllead (Air) |
| T-G4-5 | **untouched**: every cross whose seed is not in article k+1 is byte-identical between k and k+1 | fulllead, all 300 steps |
| T-G4-6 | **birth**: a cross opened at step k = `build_cross(tier_k, seed, quotient=False, ordered, stop, foundation)`; stack(1) = the one-shot quotient-off placement of prefix 1 | unit + fulllead sample |
| T-G4-7 | **frozen**: every member at k+1 descends from a member at k (§5.4); every unit seated by step k sits on the same particle-labelled leg and ring in each descendant; constructed seats never move | fulllead, all steps |
| T-G4-8 | **restricted fixed point**: every class after a growth step passes `verify_class_foundation` restricted to the non-fixed seats (no improving move among this step's units and the empty seats; closed under equal-key moves) | unit + sample |
| T-G4-9 | no lookahead in reading: the space, the grammar records and the stand-ins of step k hold no sid ≥ N_k | unit |
| T-G4-10 | **dictionary-free B**: with `fugashi`/`unidic_lite` imports blocked, the CHAR-only stack build (`build_space(tiers=("CHAR",))`, CHAR adhesion) and the B read succeed, and the CHAR stack's `state_sha256` equals A's CHAR stack at the same step | unit (toy) + steps 1, 34 |
| T-G4-11 | a stack index refuses `effort="full"`; a missing seed raises (no on-demand build); a state for another prefix or order is refused | unit |
| T-G4-12 | cross-machine: the stack identities at steps 1 and 34 (RUN, foundation on) equal the Air values on GHA (Python 3.11) and in the cloud session (3.13) | probe |
| T-G4-13 | record schema: canonical bytes, no float in the hashed part, every §7.2 field present | unit |
| T-G4-14 | events on synthetic series: appear 直入/後から, stays, a loss with all-R (置き換え), mixed R+U (壊れる), A, 単独誤答化 with R (壊れる), 戻る, unmeasured steps skipped | unit |
| T-G4-15 | the 2×2 classification of every verdict shape, present and absent, including `gold_not_from_evidence` and the impossible pre-entry `from_evidence` (raises) | unit |

All tests run at PYTHONHASHSEED 0 / 1 / 12345. Tests on the full fulllead data run on the Air or GHA, never on the Pro while a sweep runs.

---

## 12. オーナーへの問い

**None.** Every meaning-level point is settled by the owner's G4 answers and earlier decisions. The points the words did not state explicitly were
derived as follows (reviewers: check these first):

| Point | Derivation |
|---|---|
| D-1 The centre of a seated cross (old OP-G1-2, unanswered) | The data seed, not は. I-02 (centre found by search), 「中心には必ず語がある」, and OP-G1-4's 「両側のデータの語を隣とみなす」 all need a data centre. A constructed centre would leave six disconnected chains after contraction. L-529/L-549 put は on the centre side, on no arm, so は binds to the centre's adhesion and has no seat (§4.1) |
| D-2 What 「並び替え」 is in a frozen stack | 充填 and 絞り of a gold-holding cross, i.e. `arr_sha` changed (§5.4). Read-order displacement and count drift are not placement rearrangements (the old OP-G4-3 asked about 「文書が前の配置を並べ替えること」) |
| D-3 単独誤答化 after a rearrangement | 壊れる. OP-G4-3 exempts the loss of the gold. A confident wrong answer is the confident-wrong cell of the 2×2 headline the owner chose (OP-G4-4) |
| D-4 A cross that collapses | It closes for good: N-05, 「その大きさが容量」 |
| D-5 New units | Always open their own cross (L-63/I-08 flat plane; OP-G1-1 chose R2, not the shared-cross R1) |

---

## 13. 却下された案（記録のために残す）

The options I recommended in the first version that the owner declined, and other parts of that version now dropped:

| Point | My recommendation (declined) | The owner's choice |
|---|---|---|
| OP-G4-1 | (a) Start from what exists: the foundation only as a sha/label/read order. G1-b later | 「先に基盤を全ブラックに座らせる」 (my option (b)) |
| OP-G4-2 | (a) Only the plan-2 carry tower counts as 「重ねる」; the prefix placement is the reference curve | 「凍結した平面の積みを新しく作る」 (my option (c)) |
| OP-G4-3 | (a) Every lost gold counts as 壊れる with a cause tag | 「並び替えによる消失は「成長」」 (my option (b)) |
| OP-G4-5 | (a) The initial placement = the foundation only; the tokenisers and UniDic are shared apparatus | 「辞書も初期配置に数え、辞書なしの腕を足す」 (my option (b)) |
| OP-G4-6 | (c) The tower at every article for two configs, plus S-anchor | 「フィボナッチの階段 + 各問の記事が入った段」 (a new shape: S-fib ∪ entry steps) |
| Accepted as recommended | OP-G4-4 (c) both, with the 2×2 headline; OP-G1-4 (a), OP-G1-5 (a), OP-G1-9 (a) | — |

Dropped with OP-G4-2: the tower arm and its 8 configs, S-all, S-anchor, `effort=None` on the tower, the tower snapshot and frozen-closed tests (old
T-G4-3/-4/-12), and the reverse order of the tower (now A_rev@300).

**The largest risk** (measured at gates G-1 and G-2 before any question runs): with the foundation seated, the arms become relation-labelled. In a
plain flat, the arm symmetry (L-61) merged arrangements that differed only by arm. With the foundation, those arrangements are distinct, and
wherever the adhesion does not separate them (units with no particle after them: about 35–50 % of content units, G1 §2.4 (3)), they stay tied.
The stack also runs quotient off. So classes can grow toward `max_class` within a few units, and crosses may close early. The meter would then
measure the budget instead of growth. The gates stop the plan and report, rather than spending ~200 CPU h on that.
