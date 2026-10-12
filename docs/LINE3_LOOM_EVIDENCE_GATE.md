# LINE3_LOOM_EVIDENCE_GATE — 読み手の証拠の門: the emitted unit must be read from the question's cross

作成: 設計役（Opus 5.5, 2026-10-12）。Ticket **LOOM-evidence-0** (design only). Target: `wt/line3` (branch line3), base HEAD `5e72e296` (the commit that records the
owner's decision). No product code was written and nothing was committed. Every (O) number below comes from a scratch probe the designer ran on Pro with
`/Users/motonisihikoudai/vera-wiring/env/bin/python`, `PYTHONPATH=.`, over `experiments/line3/bank2/data/fulllead_sents.jsonl` (592 sentences) and the stored
ledgers `runs_h55c`, `runs_h55d`, `runs_unans`, `runs_unans_adv` (read and re-parsed, not modified). The probe is not committed; LOOM-evidence-1 rebuilds the gate in
product code and pins the same numbers as tests (§11.3). `vera-impl/hidden` was not opened. No network.
Implementation: Claude Sonnet. Review: Claude Opus. Held-out tests: codex.

> **Status after the review (2026-10-12).** The rules of this document are **evidence.v1**. The review's fixes and the owner's decision on the slot head form
> **evidence.v2** (§12; L-LOOM-191..): a predicate question with no subject is refused, the answer must be a whole word or phrase, exactly one answer, the slot head
> is read in the clause. New prose runs get v2; the 140 measurement ledgers carry v1 and replay under it. Notes marked **[after review]** below correct statements of this
> document in place; the original text is kept.

---

## 0. How to read this document

Marks as in `docs/LINE3_LOOM_DESIGN.md` §0: 【オーナー】 verbatim owner words; 【推奨】 the designer's proposal; 【L-LOOM-nn】 an engineering choice that does not change
meaning (the implementer copies it into `docs/LINE3_LOCAL_DECISIONS.md` under a new heading `## LOOM-evidence`); (O) counted for this document; (C) taken from another
document. The usual rules hold: a tie abstains and order never makes a winner; nothing is cut off silently; no float; byte-identical across `PYTHONHASHSEED` 0 / 1 / 12345.

### 0.1 The one owner question

| id | Question | Options (recommended first) | Blocks |
|---|---|---|---|
| **OP-EV-1** | A Wikipedia lead names its subject in sentence #0 and drops it afterwards (「旧社格は県社。」 is 千葉神社#1). May the **article title** of the quoted sentence stand in for a subject word that the clause itself does not hold? | **(a) Yes, for the subject only 【推奨】**: the title of the sentence's own article (its `source` minus `#i`) may hold a subject run; the annotation says `subject via title`. Reach (O): the gate admits a gold occurrence for **12 of 69** answerable bank2 items; it admits **no answer at all** for 60 of 60 unanswerable items (bank2 25 + bank4 35). / (b) No: the clause must hold every subject word. Reach (O): **0 of 69** answerable items (the loom could never answer a bank2 question); unanswerable 0 of 60, the same as (a). | Nothing in the build. The profile records the choice (`subject_scope`, L-LOOM-170); the implementation uses (a) until the owner answers, and every result is labelled with it |

Why it is the owner's: the title is a provenance field of the corpus row, not a unit seated anywhere. Counting it as "the subject is in the cross" is a reading of
「質問の単位と同じ十字に座っていて」 that the owner did not state. The numbers say that (b) closes the answering door completely on this corpus, and that (a) costs
nothing on the unanswerable banks in the probe; they do not decide the meaning.

---

## 1. Constraints, verbatim

### 1.1 The decision this design implements

| Point | 【オーナー】 verbatim (ops/decisions/2026-10-06_line3_faithful_build.md, last table) |
|---|---|
| 関連の門 (2026-10-12) | 「読み手の証拠の門を emit に入れる (Recommended)」— emit する単位は、質問の単位（主題と格の助詞）と同じ十字に座っていて、質問の slot の腕から読めるときだけ通す。Vera の読み手の「質問単位との一致」を織機に持ち込む。実装後に可答・不可答の両方を再計測 |
| 安定した制御 (2026-10-12) | 「でもやはり織機の構造に乗らないということと自分で再確認した経路の両方がないと安定した制御とは言えませんね」 |

The fact behind it (C, results_unans_adv/REPORT.md, L-LOOM-165..169): the loom's gate checks provenance, not relevance. On bank4 both loom modes emitted ADV-010
「シンガポール」 (the trap: the host city, for a question that asks the venue's name) and ADV-001 「2002年」 / 「2002年メジャーデビュー」 (the year, for a question that asks
the month and day). Route (1), the structure refusing, stopped no wrong answer: 0 content-level refusals in 70 loom runs. `docs/LINE3_LOOM_DESIGN.md` §10.1 had named
this outcome in advance: "the loom needs the reader's evidence gate (a record unit must be *read from a cross* that holds a question unit)".

### 1.2 Earlier decisions that bind this gate

| Decision | Effect here |
|---|---|
| OP-LOOM-1 (a) full key (n, p, a) | Unchanged. The evidence gate is an ADDITIONAL refusal; a cross that is stable but has no evidence is refused, a cross with evidence that is unstable is refused (§7.1) |
| record_only / constructed_allowed (§5.1 of the loom design) | Unchanged as modes. Under the gate a constructed unit can never reach a prose emit (§7.3) |
| weave_span faithful (owner, 「文に忠実な範囲織り」), L-LOOM-130..146 | The answer is a woven quote; the gate reads the quote's position in its sentence. A new rule version weave_span.v3 only adds an unhashed marker (§7.2) |
| L-LOOM-146 「助言だけ止める」 | Unchanged: an unstable quote cross offers no swap |
| T6v (particles are not units), L-541/L-549 (records are read on WORD) | The evidence is read on the WORD tier of the sentence with the default filter, as the grammar layer's records are |
| G2-f / L-552 「文法層の読む順」: the grammar layer decides the READ ORDER only, never the candidate set | **Tension, raised.** Here the grammar layer's reading of the question decides a REFUSAL at emit. The owner's decision explicitly brings 「質問単位との一致」 into emit; the line-3 reader's own question path is not touched (no file of `verantyx/line3` changes) |
| Owner 2026-10-12 「正規化後の完全一致を見出しに」 | The headline of the re-measurement stays `hit_exact` |

### 1.3 Two readings of 「同じ十字」, and why the literal one cannot be built

A cross made by `weave_span` holds at most one arm unit plus a centre (L-LOOM-131): in 「アメリカを青と色分け」 the stretch is not even weavable
(`nested_particle_chain`: 青 would be the centre of アメリカを青 and an arm unit of 青と色分け). In a weave chain the answer's OWN particle attaches it to the NEXT
cross, so "the answer on the slot arm" and "the subject in the same weave cross" exclude each other unless the subject is the very next unit. Read literally, the rule
would refuse every answer of every bank. 【推奨, fixed as L-LOOM-177】 The cross of the owner's sentence is **Vera's grammar cross of the clause** (G2
`grammar.grammar_cross` with the window = the clause of the quoted sentence, §4): its arms are the six particles, each clause unit sits on the arm of the particle that
follows it (an `Attachment` record), the topic は is the centre relation. "Seated in the same cross" = held by the clause; "readable from the slot arm" = the answer's
attachment record carries the slot particle. This is the reader's own notion (the grammar layer's records of a window), and the clause keeps the locality the
coordinator asked for: 「アメリカを青」 does not hold イギリス, because the clause of 青 stops at 「、」 (§8.5).

---

## 2. Facts measured for this design (O)

### 2.1 What the answerable h55d runs wove (the 14 loom runs that emitted; one weave_span each except I2-025 record_only)

| run | question | woven (sid, tier, stretch) | the stretch's sentence | subject in that sentence? |
|---|---|---|---|---|
| I2-001 ro (exact) | ハッシュテーブルの別名は何ですか | 1 RUN ハッシュ..表 → c1 ハッシュ, c2 表 | 「ハッシュ表ともいう。」 (ハッシュテーブル#1) | no (title) |
| I2-001 ca (miss) | same | 2 RUN 連想配列 | 「ハッシュテーブルは連想配列や集合の効率的な実装のうち1つである。」 | yes |
| I2-008 ro / ca (miss) | 唯物史観を唱えた人物は誰ですか | 23 WORD マルクス | 「19世紀にカール・マルクスが唱えた歴史観である。」 | no (title) |
| I2-013 ro / ca (exact) | 千葉神社の旧社格は何ですか | 86 RUN 県社 | 「旧社格は県社。」 | no (title) |
| I2-025 ro (exact) | レッド計画ではアメリカを何色としていましたか | 143 WORD アメリカ..青 (c1: 青 centre, アメリカ on を), then 143 WORD 青 (c2), `drop c1` | 「イギリスを「赤」、アメリカを「青」と色分けし、…」 | アメリカ yes, レッド計画 no (title) |
| I2-025 ca (exact) | same | 143 WORD 青 | same | same |
| I2-034 ro / ca (exact) | サンゴーカメラは何年に設立されましたか | 292 WORD 1981..年 → c1 1981, c2 年 | 「1981年に永豊企業株式会社のカメラ事業部門として設立された。」 | no (title) |
| I2-041 ro / ca (exact) | ソル・クバーノというカクテル名はどういう意味ですか | 348 WORD キューバ..太陽 → c1 太陽, キューバ on の | 「カクテル名は、Sol Cubanoと綴るが、これは「キューバの太陽」という意味。」 | no (title) |
| R2-I013 ro / ca (exact) | アワディー語はインドのほかに、どこの国で使われていますか | 152 WORD ネパール | 「インドのウッタル・プラデーシュ州アワド（旧称はアヨーディヤー）やネパールに話者がいる。」 | no (title) |

No emitted cross holds a question unit: every exact hit is the answer alone, woven from a sentence that (except I2-025's アメリカ) does not contain the question's
subject at all. The evidence must therefore be read from the quoted sentence around the woven answer, not from the emitted crosses.

### 2.2 The two wrong emissions of bank4 (runs_unans_adv)

| run | woven | sentence (CUBE JUICE#0 / 2025年世界水泳選手権マダガスカル選手団#0) |
|---|---|---|
| ADV-001 ro | 123 WORD 2002..年 and 123 WORD メジャー..デビュー (after two `span_inexpressible` on ビクター…デビュー) → 「2002年メジャーデビュー」 | 「CUBE JUICE（キューブ・ジュース）は、シンガーソングライター長尾 伸一（…1975年1月22日 - ）のソロユニットで2002年にビクターエンタテインメントよりメジャー・デビュー。」 |
| ADV-001 ca | 123 WORD 2002..年 → 「2002年」 | same |
| ADV-010 ro / ca | 579 WORD シンガポール | 「2025年世界水泳選手権マダガスカル選手団は、2025年7月11日から8月3日までシンガポールで開催された第22回世界水泳選手権のマダガスカル選手団、およびその競技結果。」 |

### 2.3 How the grammar layer cuts the questions (`grammar.read_question`, then the rules of §3)

Forms over the banks (O): bank2 answerable on fulllead (69): predicate 35, slot 23, open 11. bank4 (35): near-fact 8/8 predicate; same-slot 10/10 predicate;
numeric 7 predicate + 1 open (ADV-028); entity-swap 5 slot (031, 033, 034, 037, 038) + 1 predicate (039) + 3 open (035, 036, 040).
Two cut facts the rules must handle: `slot_of` needs the interrogative as its own WORD, so 「何色」 (one WORD) gives no slot (I2-025, ADV-015); `predicate_of` glues a
content verb into Y (「というカクテル名」 gives Y = いうカクテル名, I2-041).

### 2.4 What the gate of §5 does on the stored and the possible answers (probe)

| measure | (a) clause or title | (b) clause only |
|---|---|---|
| h55d record_only exact hits (6) that pass | **3** (I2-013, I2-025, I2-034) | 0 |
| h55d constructed_allowed exact hits (5) that pass | 3 (the same three) | 0 |
| bank2 answerable items (69) with at least one gold occurrence that passes | **12** (I2-003..006, I2-013, I2-014, I2-018, I2-025, I2-034, R2-I005, R2-I007, R2-I017) | 0 |
| unanswerable items (bank2 25 + bank4 35) for which ANY single unit of the corpus passes | **0 of 60** | 0 of 60 |
| bank4 trap values (c) that occur WORD-aligned (33 of 35) and pass | 0 of 33 | 0 of 33 |
| stored wrong emissions ADV-001 ×2, ADV-010 ×2 that pass | 0 of 4 | 0 of 4 |
| the 7 answerable loom tasks: single units that pass | I2-013 {県 → 県社}, I2-025 {青}, I2-034 {年 → 1981年}, I2-041 {Sol (wrong)}; the others none | I2-041 {Sol} only |

Where the 57 unreachable answerable golds fail under (a), counted per item on its best occurrence: `no_slot_head` 32, `no_subject` 15, `wrong_arm` 11,
`question_form_open` 8, `answer_holds_question_unit` 7, gold not WORD-aligned 5, `not_copular` 3, `question_has_no_subject` 2 (an item can carry several).
The gate is a unit-level relevance test: it passes when the sentence uses the question's own words for the asked relation (「駅番号はJR-Y13」 for 「駅番号は何ですか」)
and refuses paraphrase (「ハッシュ表ともいう」 for 「別名」, 「愛知県出身」 for 「出身地」). That is its cost, stated before measuring.

> **[after review]** The histogram above (`no_subject` 15, `answer_holds_question_unit` 7) is the design probe's. The product code counts `no_subject` 21 and
> `answer_holds_question_unit` 8 over the same 57 items (REPORT_TABLES.txt E8, REPORT.md): the design does not state which occurrence of an item counts when it has
> several, the implementation takes the occurrence with the fewest codes. Neither is a defect; the two lists are of different "best occurrences". The reach (12 / 69) is the same.

---

## 3. The question's units (QU)

### 3.1 The cut (exact; `verantyx/loom/evidence.py: question_units(text) -> QuestionUnits`, a pure function)

All offsets are in `r.text`, where `r = grammar.read_question(text)` (no space: the pattern is not used) and `words = grammar.words_of(r.text)`. IGNORE =
{「 」 『 』 “ ” " ' ・ · U+0020 U+3000 U+0009} (L-LOOM-177). "Touching" = the text between two spans is empty after removing IGNORE characters.

1. **Slot.** `slot = r.slot`. If it is None, the fallback slot (L-LOOM-171) is the FIRST frame of `r.frames` whose unit begins with a member of `grammar.INTERROG`
   (string prefix): `Slot(phrase = frame.unit, span = frame.span, particle = frame.particle, after = frame.after)`, `fallback = true`. (I2-025: 何色, particle と.)
2. **Effective particle p** (L-LOOM-172). `p = slot.particle`. If p is の, and the WORD right after that の is a content word touching it, and `grammar.follower`
   after that word is a P7 particle q ≠ の, then p = q and `slot_noun` = that word (「どこの国で」: p = で, noun 国). Otherwise p stays.
3. **Y** (the predicate head of 「XのYは何ですか」). `r.predicate` when the slot is not a fallback; for a fallback slot whose particle is None,
   `grammar.predicate_of(words, fallback_slot)`.
4. **Form** (L-LOOM-173): `slot` if p ∈ P7 (は の に で と を が); else `predicate` if Y exists; else `open`.
5. **Y forms** (L-LOOM-174): for every WORD w of `grammar.words_of(Y)` that is content (`grammar._content`), the suffix `Y[w.start:]` if it has ≥ 2 characters;
   longest first. (いうカクテル名 → いうカクテル名, カクテル名; 堤頂長 → 堤頂長, 頂長; 名称 → 名称.) Y is "held" when any form is read (§4.3).
6. **S-runs** (L-LOOM-175). Take `granularity._raw_spans(RUN, r.text)`; keep a unit u iff `not is_function_unit(u, RUN)` and some WORD of `words_of(u)` is content
   (= the reader's query units, the cut `wiring.intake(...).units` uses: T-EV-14 checks the equality on every bank question). Merge consecutive kept units that touch
   into one run (surface = the concatenation without IGNORE characters). Each run carries `after` = the P7 particle `grammar.follower(words, run_end)` gives, else None.
7. **Subject** (L-LOOM-175). Exclusion spans: the slot phrase, the slot noun, Y. Then the first rule that yields something:
   - (x_chain) form predicate: walk left from Y over 「R の」: the S-run R whose `after` is の and whose end is followed, up to the current start, by exactly 「の」
     (IGNORE removed); repeat from R. If at least one R was found, subject = [the OUTERMOST R] (「千葉神社の旧社格」 → 千葉神社; 「大邱FCのマスコットの名前」 → 大邱FC).
   - (topic) the non-excluded S-runs with `after` = は; (ga) with が; (case) with を, に, で, と or の. The subject is ALL runs of the first non-empty level.
   - none: subject = [] (§5, rule E-3).
8. **Slot head** (form slot only, L-LOOM-176): the WORD that `grammar.follower` gives right after the effective particle, if its label is `other` and it is content;
   else None. (何年に設立 → 設立; どこの国で使わ → 使わ; どの市町村に本社を → 本社.)
9. **Question units** (the echo set, L-LOOM-181): the kept RUN units of step 6 that contain no INTERROG member, plus the subject runs, plus the Y forms.

Values on the measured tasks (O; T-EV-01 pins the whole table for the 10 + 25 + 35 bank questions):

| item | form | p / Y | subject (level) | slot head |
|---|---|---|---|---|
| I2-001 | predicate | Y 別名 | ハッシュテーブル (x_chain) | — |
| I2-008 | predicate | Y 人物 | 唯物史観 (case) | — |
| I2-013 | predicate | Y 旧社格 | 千葉神社 (x_chain) | — |
| I2-025 | slot (fallback 何色) | p と | レッド計画, アメリカ (case: で, を) | — |
| I2-034 | slot | p に | サンゴーカメラ (topic) | 設立 |
| I2-041 | predicate | Y いうカクテル名 | [] | — |
| R2-I013 | slot (どこの国で) | p で, noun 国 | アワディー語 (topic) | 使わ |
| ADV-001 | predicate | Y 月日 | CUBEJUICE (ga) | — |
| ADV-010 | predicate | Y 名称 | 競技会場 (x_chain) | — |
| ADV-025 | predicate | Y 堤頂長 | 赤尾ダム (x_chain) | — |

### 3.2 Exposure to the model (read-only; it cannot be forged)

`begin` (prose runs under an evidence profile) returns one more key, `question` (L-LOOM-185):
`{"evidence": "evidence.v1", "subject_scope": "clause_or_title" | "clause", "form", "slot": {"phrase", "particle", "noun", "head", "fallback"}, "y", "y_forms",
"subject", "subject_level", "units"}`. No tool takes any of it as an argument. The gate never reads it back from a row: it recomputes `question_units(task.text)`
from the task bank file the server holds. It is part of the hashed `begin` result, so replay recomputes it and any drift of the cut is `REPLAY_DIFFERS`: a change of
the cut is a new evidence version (L-LOOM-170), never an edit of v1. The model sees what the gate will demand; it cannot change it.

---

## 4. The evidence: the clause of the quoted sentence

### 4.1 Which weave carries evidence

`weave_span.v3` (L-LOOM-183) = v2 plus one unhashed marker on each cross it makes: `quote = (w, sid, tier, i0, i1)`, w = the 1-based count of v3 weaves in the run.
Like `span`, it is cleared by any seat / unseat / swap / topic change of the cross (state.py lines 283/289/296 and ops.py 903 already clear `span`; they clear `quote`
too). Replay derives it from the row's result (`sid`, `tier`, `from`, `to`), exactly as `span`. A weave w is **intact** iff every cross carrying `quote[0] == w` still
carries it, all of them are linked, and they stand in the thread consecutively in creation order.

### 4.2 The clause (L-LOOM-177; on WORD, whatever the tier of the weave)

1. Answer span: `cs = spans(tier, sid)[i0].start`, `ce = spans(tier, sid)[i1].end` (`Corpus.spans()`, the attribution-stripped sentence).
2. Alignment: `a0` = the index of the WORD unit (`corpus.tier("WORD").sentence_units[sid]` with `spans("WORD", sid)`) that starts at cs; `a1` = the one that ends
   at ce. If either does not exist: `answer_not_word_aligned` (a RUN unit such as 「1981年に」 holds a particle and is never an answer).
3. `gap(k)` = the sentence text between WORD unit k's end and unit k+1's start. **Connective** iff, after removing IGNORE characters, it is empty; or it is exactly
   「は、」; or it has no 「、」 and `grammar.words_of(gap)` cuts it into tokens that rebuild it exactly, all in P7 ∪ {も}, the first in P7 (に, では, とも, には).
   Anything else breaks the clause: 、 (except after a bare は), 。, brackets, より, として, という, から, まで, a verb ending, a pronoun.
4. Clause `[lo, hi]`: from a0 step left while `gap(lo−1)` is connective; from a1 step right while `gap(hi)` is connective.
5. The evidence cross = `grammar_cross` of the window "this clause": every clause unit k seated on the arm of `follower(words_of(sentence), end_k, "whole_word")`
   when that is an arm particle, on は (the centre relation) when it is は, unseated otherwise. It is what the annotation shows (§7.6); the checks of §5 are stated on it.

### 4.3 Reading a word in the clause (L-LOOM-178)

A run string s (a subject run, a Y form, a question unit) is **read in the clause** iff there are lo ≤ i ≤ j ≤ hi, with [i, j] disjoint from [a0, a1], every
`gap(k)` for i ≤ k < j empty after removing IGNORE, and the concatenation of the WORD surfaces i..j equal to s without IGNORE characters. **Read in the title**
(OP-EV-1 (a) only): the same over `grammar.words_of(title)`, title = `source` with its final `#<digits>` removed.

---

## 5. The gate rule (exact)

For a prose run with an evidence profile, `read` and `emit` evaluate, after the §3.7 checks of the loom design and before stability (L-LOOM-184):

**T (thread).** Every linked cross that holds a unit must belong to an intact v3 weave, else `not_quoted` (that cid). Every unit of the thread must be a record unit,
else `constructed_unit` (that uid). Each intact weave is then judged on its own (a thread of two weaves needs two passing weaves).

**Per weave** (all checks run; every failing code is listed):

| step | code | condition (fails when …) | message (to the model; English, quoted words in 「」) |
|---|---|---|---|
| E-1 | `answer_not_word_aligned` | §4.2 step 2 | the stretch 「A」 does not begin and end on words of sentence N |
| E-2 | `question_form_open` | form = open | the question 「Q」 has no particle after its question word and no 「〜は何」 head, so no answer can be read from a sentence for it |
| E-3 | `question_has_no_subject` / `no_subject` | form slot and subject = []; or some subject run is read neither in the clause nor (scope clause_or_title) in the title. Form predicate with subject = [] skips E-3 (Y stands for it) **[after review: this skip was the defect; evidence.v1 only. evidence.v2 refuses `question_has_no_subject` for a predicate question too, L-LOOM-192]** | the subject 「S」 of the question is not in the clause 「C」 of sentence N (nor in its article title 「T」) |
| E-4s | `wrong_arm` | form slot and `follower(words_of(sentence), end of WORD a1, "whole_word")` is not ("particle", p) | the answer 「A」 is followed by 「g」 in sentence N; the question asks for the word before 「p」 (「slot phrase+p」) |
| E-5s | `no_slot_head` | form slot, the slot head h exists and no WORD unit of sentence N equals h **[after review: evidence.v2 reads h in the CLAUSE, outside the answer, and refuses when h is None, L-LOOM-195]** | sentence N does not contain 「h」, the question's predicate |
| E-4p | `no_slot_head` | form predicate and no Y form is read in the clause | the asked item 「Y」 is not in the clause 「C」: this sentence does not state what is asked |
| E-5p | `not_copular` | form predicate, Y is read at [y0, y1], but neither (P1) gap(y1) is は or は、 and a0 = y1 + 1 (「Y は A」) nor (P2) gap(a1) is は or は、, y0 > a1 and every gap between a1+1 and y1 is an arm particle or empty (「A は … Y」) | the answer 「A」 is not read as 「Y は A」 or 「A は … Y」 in the clause 「C」 |
| E-6 | `answer_holds_question_unit` | a question unit (§3.1 step 9) is read inside [a0, a1] (same reading as §4.3, restricted to the answer) | the answer contains 「u」, a word of the question; quote only what answers |

`T` and E-1..E-6 together form ONE refusal type **`no_evidence`** (L-LOOM-184), placed in `read.REFUSAL_ORDER` right after `constructed_forbidden` and before
`unstable_cross`. Payload: `{"weaves": [{"w", "cids", "sid", "source", "tier", "answer", "clause", "codes": [...], "messages": [...]}], "crosses": [{"cid", "code"}]}`.
The payload names only words of the question and of the sentence the model already quoted; it never reveals another sentence (no hint of where an answer is).

Summary of the rule in five lines:
1. A prose emit is a quotation: every cross is an unchanged `weave_span` cross; constructed and hand-seated units cannot be emitted.
2. The evidence of a woven answer is its clause: the stretch of the same sentence around it, joined only by particles (は の に で と を が, も) or nothing.
3. The clause must hold every subject word of the question (OP-EV-1 (a): or the sentence's article title holds it); the answer itself holds no question word.
4. Slot question: the answer's last word is followed by the question's slot particle, and the sentence holds the slot head; predicate question: the clause reads 「Y は A」 or 「A は … Y」.
5. Otherwise `no_evidence`, with one code and one message per missing piece; a question with no slot particle and no 「〜は何」 head can never be answered.

---

## 6. Where the evidence comes from: derived, not declared

The ticket offered (i) `emit(cid, evidence = cid2)` — the model weaves a second, wider span and names it — and (ii) `emit_from(cid, unit)` — the model emits one
unit out of a span cross. 【推奨, L-LOOM-182】 **(iii) neither: the loom derives the evidence from the quote the answer already is.** Every v3 answer cross knows its
(sid, tier, i0, i1); the clause is a function of that and of the corpus. Why this is the cleaner one:
- **Nothing to forge or to mis-declare.** Under (i) the model picks the evidence stretch; any declared stretch that passes is a sub-stretch of the clause (all checks
  are monotone in the stretch: a larger clause can only hold more subject words and the same attachments), so declaring adds failure modes, never evidence.
- **The output stays the read-out of whole crosses** (loom design §3.4). (ii) would emit part of a cross, a second output path the read rule does not have.
- **The evidence cross would not fit a weave anyway** (§1.3: 「アメリカを青と色分け」 is `nested_particle_chain`). (i) would need a weave rule for evidence that the
  output rule refuses.
- **No new tool and no new argument.** Prompts change by one paragraph; the h55d ops (one `weave_span`, one `emit`) are still the whole answer, so the re-measurement
  compares like with like.
- (i) also leaves unlinked evidence crosses in the state (`unlinked_cross`) or needs an exemption; (iii) leaves no extra state.
The model's part stays what the owner's route (2) asks for: it chooses which sentence and which stretch to quote; the loom checks that the quote answers the question.

---

## 7. Interactions

### 7.1 Order of checks; the key gate

`read`/`emit` return all refusals (L-LOOM-06). Order: empty_thread, unlinked_cross, empty_centre, leg_gap, tier_mix, constructed_forbidden, **no_evidence**,
unstable_cross, code types. The emit row's `refusal` is the first type, so a run that fails both is counted as a content refusal (route (1)). **A stable cross with
no evidence is refused; an evidenced cross that is unstable is refused** (both listed). The key gate and L-LOOM-146 (no swap offered for an unstable quote) are
unchanged; the advice string of `unstable_cross` is unchanged.

### 7.2 weave_span

v3 = v2 + the `quote` marker (L-LOOM-183). `WEAVE_SPAN_WV` becomes v3 for new runs; v1/v2 rows replay by their own rule forever. `weave_span` itself refuses nothing
new: the gate runs at read/emit, so a model can weave a stretch, `read` it, see `no_evidence`, and `drop` it.

### 7.3 record_only / constructed_allowed (recommended: refuse)

Under the gate a constructed unit in the thread is `no_evidence/constructed_unit` in both modes, and hand-seated record crosses (add + seat) are `not_quoted`.
Consequence, stated for the owner: **in prose, constructed_allowed can emit exactly what record_only can.** Constructed units may still be added and seated in
working crosses (they leave rows and notes), but never reach an emitted text. "Constructed words as non-answer connectors" (です, 。) is NOT opened: a connector
cross after an evidenced answer could carry content (「2002年」 + a constructed 「1月22日」 would pass), and a closed list of harmless connectors would be a meaning
choice. Code tasks are untouched (the gate is prose-only, L-LOOM-186).

> **[after review]** Said plainly: **under the gate record_only and constructed_allowed are the same condition for prose.** Both emit exactly the same texts; a constructed
> unit is `no_evidence/constructed_unit` in both. The two mode labels and the two task rows are kept (both stay measured, owner 2026-10-12) and neither the mode table
> nor the code was changed. A measured difference between the two modes on prose is run-to-run variation of the model, not the mode.

### 7.4 Notes (QUESTION_ECHO)

Unchanged (notes.v2, non-blocking: a thread unit of ≥ 2 characters that is a substring of the question). E-6 is its blocking counterpart, on exact question
units read inside the answer. They co-fire on echoes such as 「旧社格は県社」; QUESTION_ECHO's false positive of h55d (ハッシュ ⊂ ハッシュテーブル on the exact hit
ハッシュ表) does not fire E-6 (ハッシュ is not a question unit; ハッシュテーブル is not read inside ハッシュ表).

### 7.5 Versioning and replay (L-LOOM-170)

The `begin` result gains `evidence_profile = {"version": "evidence.v1", "subject_scope": ...}` (only when a profile is active, like `notes_profile`). A `begin` row
without it = no evidence gate: every stored ledger (h55..h55d, unans, unans_adv, code) replays byte-identical. Replay builds the Run with the recorded profile; an
unknown version or scope = `INPUTS evidence_profile_unknown`. Server / run_bank flags: `--evidence v1|off` (default v1 for new prose runs) and
`--subject-scope clause_or_title|clause` (default clause_or_title until OP-EV-1 is answered).

### 7.6 Output and scoring

`emit` (and `read`) add `evidence: [{"w", "sid", "source", "clause", "subject": [{"run", "via": "clause"|"title"}], "slot": {"particle", "arm"} | "copula": "Y は A"|"A は … Y", "y"}]`;
the annotated text is unchanged. `score.layer_report`: `no_evidence` is a structural refusal (route (1)), and `report_unans.OWNER_NAMED` gains it (L-LOOM-188).

### 7.7 Prompts (L-LOOM-189)

`.claude/agents/loom-weaver.md` and `loom-weaver-record-only.md` (the L2 driver reads them through `harness.system_prompt`) gain one paragraph describing §5 and
`begin.question`, and LOSE two things that the gate now contradicts: "build the answer by hand" / "Use add and seat by hand for a word that is in no sentence"
(not_quoted), and the invented example 「その会社の創業は何年ですか」 / 「その会社は1975年に創業した」 → 1975年 (predicate form, Y 創業 not read as 「創業は A」:
`not_copular`). New invented examples must pass the probe gate; `test_no_gold_in_the_agent_prompts` still applies. The prompt change is a confound of the
re-measurement (as in h55d), stated, not separated.

---

## 8. Walk-through

### 8.1 (a) The h55d exact hits

| run | clause (WORD, sentence text) | verdict (a) clause_or_title | verdict (b) clause |
|---|---|---|---|
| I2-001 ro 「ハッシュ表」 | 「ハッシュ表」 (ともいう breaks: も after と is allowed but いう is not a particle) | **no_evidence**: no_slot_head (別名) | no_subject (ハッシュテーブル), no_slot_head |
| I2-013 ro / ca 「県社」 | 「旧社格は県社」 | **pass**: P1 「旧社格 は 県社」, subject 千葉神社 via title | no_subject |
| I2-025 ro / ca 「青」 | 「アメリカを「青」と色分け」 | **pass**: 青 attached by と (slot と), アメリカ in the clause, レッド計画 via title | no_subject (レッド計画) |
| I2-034 ro / ca 「1981年」 | 「1981年に永豊企業株式会社のカメラ事業部門」 (として breaks) | **pass**: 年 attached by に (slot に), 設立 in sentence 292, サンゴーカメラ via title | no_subject |
| I2-041 ro / ca 「キューバの太陽」 | 「キューバの太陽」という意味」 (これは breaks on the left) | **no_evidence**: no_slot_head (カクテル名 is in the other clause 「カクテル名は、Sol Cubanoと綴る」, which is why 「Sol」 passes, §8.6) | same |
| R2-I013 ro / ca 「ネパール」 | 「やネパールに話者」 | **no_evidence**: wrong_arm (に, the question asks で), no_slot_head (使わ) | + no_subject |

So 3 of the 6 record_only exact hits and 3 of the 5 constructed_allowed exact hits survive under (a); none under (b). The misses I2-008 「マルクス」 and I2-001 ca
「連想配列」 are refused (no_slot_head: 人物 / 別名), and so would be the gold カール・マルクス: the gate cannot read 「X が唱えた」 as 「唱えた人物は X」.
The h55c over-extensions are all refused: 「旧社格は県社」 / 「ハッシュテーブルは連想配列」 (answer_holds_question_unit), 「アメリカの青」 (a swapped quote: `not_quoted`; woven as 「アメリカを青」 it is answer_holds_question_unit), 「1981年に設立」 (answer_not_word_aligned: RUN 1981年に),
「キューバの太陽という意味」 (no_slot_head, answer_holds_question_unit: 意味).

### 8.2 (b) ADV-010 and ADV-001: refused, with the exact strings

- **ADV-010** (both modes), weave 579 WORD 「シンガポール」. Clause 「シンガポールで開催」 (まで breaks on the left, された on the right). Codes `no_subject`, `no_slot_head`:
  "the subject 「競技会場」 of the question is not in the clause 「シンガポールで開催」 of sentence 579 (nor in its article title 「2025年世界水泳選手権マダガスカル選手団」)";
  "the asked item 「名称」 is not in the clause 「シンガポールで開催」: this sentence does not state what is asked". Same under (b).
- **ADV-001 ca**, weave 123 WORD 「2002年」. Clause 「ソロユニットで2002年にビクターエンタテインメント」 (より breaks). Code `no_slot_head`: "the asked item 「月日」 is not in
  the clause 「ソロユニットで2002年にビクターエンタテインメント」: this sentence does not state what is asked" (the subject CUBEJUICE is read in the title 「CUBE JUICE」;
  under (b) `no_subject` is added). **ADV-001 ro** adds a second weave 「メジャーデビュー」 (clause 「メジャー・デビュー」): `no_slot_head` and `answer_holds_question_unit`
  ("the answer contains 「メジャーデビュー」, a word of the question").

### 8.3 (c) A near fact of the same type: the head word decides

ADV-025 「赤尾ダムの堤頂長は何メートルですか」, trap 29.2メートル in 赤尾ダム#1 「高さ29.2メートルの重力式コンクリートダムで、…」: clause 「29.2メートルの重力式コンクリートダム」
(高さ is cut 高 + filtered さ, so it is not even joined; で、 breaks). `no_slot_head` (堤頂長). The slot particle cannot tell 堤頂長 from 高さ (both questions are
「〜は何メートル」, no particle after the interrogative): only the head can, so **the head of a predicate question must be a unit of the clause** (E-4p), and the answer
must be its copula complement (E-5p). The same rule refuses ADV-011 (「人口は73,921人」 for 世帯数), ADV-021 (橋長 for 幅員), ADV-022 (標高 for 全長), ADV-026 (排気量 for 最高出力).
ADV-030 is the converse case: 「人口は20万人」 (テレゴ県#2) has the right head and the right copula, and is refused only by `no_subject` (アイーヴ副郡; title テレゴ県).

### 8.4 (d) A same-slot item

ADV-018 「呉線の駅数は何駅ですか」, trap JR-Y13 in 川原石駅#1 「駅番号はJR-Y13。」: the sentence has the same slot shape 「〜は X」, but `no_slot_head` (駅数 ≠ 駅番号) and
`no_subject` (呉線; title 川原石駅). ADV-019 (OR08, 海浦駅#1) is the same. ADV-031 (entity-swap, slot に): 「広島県呉市海岸三丁目」 is attached by に as the slot asks, and is
refused only by `no_subject` (JR西日本 is not the station's article, nor in the clause).

### 8.5 The coordinator's example

Sentence 143 「イギリスを「赤」、アメリカを「青」と色分けし、…」. For 「レッド計画ではイギリスを何色としていましたか」 (slot と, subject {レッド計画, イギリス}): 青's clause
「アメリカを「青」と色分け」 does not hold イギリス → `no_subject`, although the title holds レッド計画 (all subject runs are required, L-LOOM-175; with "any one" the title
would have let 青 through: the probe showed it, and that is why the rule says ALL). 赤's clause 「イギリスを「赤」」 holds the subject but 赤 is followed by 「、」 (the sentence
elides と) → `wrong_arm`. The gate cannot give the right answer there, and it gives no wrong one. For 「イギリスをどう塗りましたか」: `question_form_open`.

### 8.6 What the gate can and cannot stop (bank4 kinds)

| kind | stopped by | cannot stop (in principle) |
|---|---|---|
| near-fact (8, predicate) | E-4p: the asked attribute (月日, 名称, 母親, 名前, 初回放送日) is not a unit of the clause; plus E-3 off-article (BAN BAN) | the asked head word occurs with the subject in the clause but the value is not the asked one (a qualifier: 「人口は（2005年）N人」 asked for 2020; AUDIT4 dropped such items, ADV-003/024) |
| same-slot (10, predicate) | E-4p (世帯数 ≠ 人口, 駅数 ≠ 駅番号, 厚さ, 呼称, 収容人数, 郵便番号, 色数) | the same: a literal Y with a wrong value |
| numeric (8: 7 predicate, 1 open) | E-4p (堤頂長, 幅員, 全長, 最大出力, 最高出力, 幅, 人口 with a wrong subject via E-3); ADV-028 by E-2 | as above; also a unit (km vs m) is not checked |
| entity-swap (9: 5 slot, 1 predicate, 3 open) | E-3 (the bridging entity is in the clause, the asked one is not: JR西日本, オレカ's subject runs, ムンバイ), E-4s/E-5s (wrong particle, head absent), E-2 (035, 036, 040) | a slot question whose subject, slot particle and head verb all co-occur for another event of the same subject (「Xは1990年に再設立」 for 「何年に設立」: 設立 is a unit) |

Trap values (O): 33 of 35 occur WORD-aligned (ソレローン島, 〒771-1505 do not); all 33 are refused, near-fact 8/8, same-slot 8/8, numeric 8/8, entity-swap 9/9.
Stronger (O): for all 60 unanswerable items of bank2 + bank4, NO single WORD unit of the corpus passes the gate, so any emit attempt on them is refused whatever
the model weaves. Precision on answerable questions is not guaranteed: I2-041 admits 「Sol」 (the predicate cut takes 「カクテル名は、Sol」 as 「Y は A」); a model that
emits it gets a wrong answer through the gate.

> **[after review, 2026-10-12] Correction.** The paragraph above is true of SINGLE units only, and "precision … is not guaranteed" understated it. Over all stretches of
> at most 10 WORD units (the corpus probe, title scope; T-EV-21), under **evidence.v1**: **20 of the 69 answerable bank2 items admit at least one wrong stretch**, 8 of
> them admit only wrong ones (the review's count; the product probe, which takes a stretch to be right iff its normalised text is a gold alternative, finds 21 and 9: one item more, whose
> cause is not identified; the review's stretch bound or its test of 'wrong' may differ) — pieces of a word (JR, 県, さん, 年, 日本 from 日本武尊), over-long stretches (気象条件は日本海側気候), stretches over a clause break
> (和歌山千葉線」、京成バス…), and answers to a question with no subject (「IEEE 488の通称」 → PSE of パリ経済学校; 「駅番号は何ですか」 → JR-Y13 of 川原石駅). The unanswerable
> side holds for stretches too: 0 of 60 items admit any stretch of at most 10 words under evidence.v2.
> Under **evidence.v2** the same probe finds: after the two fixes F1 + F2 alone, 6 of 69 items admit a wrong stretch (5 only wrong), reach 12 of 69; after the owner's slot-head
> decision (L-LOOM-195) **0 of 69** items admit a wrong stretch, reach **10 of 69** (I2-025: 何色と has no head; I2-034: 設立 is outside the clause 「1981年に…事業部門」). The
> reach is 9 of 69 if 「とも」-type particle stacks are not read as connective (R2-I005 would be lost with them): L-LOOM-196.

---

## 9. Predictions (written before any measurement; P-EV-n)

The re-measurement (LOOM-evidence-3): the 20 loom cells of h55d (7 answerable + 3 unans × record_only / constructed_allowed), bank2 unans 25 × 2 loom modes,
bank4 35 × 2 loom modes = **140 runs**, Haiku 5.5, L2 API driver, caps v2, one run per cell, evidence.v1, subject_scope as the owner answers OP-EV-1 (default (a)).
Controls are not re-run (they have no loom); the stored h55d / unans / unans_adv controls are the comparison. Under (b) the predictions in brackets.

1. **P-EV-1** bank2 answerable, record_only: exact hits **3/7** (I2-013 県社, I2-025 青, I2-034 1981年) [0/7]; the gate admits nothing better (§2.4).
2. **P-EV-2** constructed_allowed: **3/7** [0/7]; constructed share 0; no `constructed_unit` emitted.
3. **P-EV-3** The four unreachable answerable items (I2-001, I2-008, I2-041, R2-I013), 8 runs: no exact hit; ≥ 6 of 8 runs show ≥ 1 `no_evidence` (they weave the
   same sentences as in h55d); ≤ 1 of 8 emits a wrong text through the gate (the only admissible wrong answer is I2-041 「Sol」/「SolCubano」); the rest abstain.
4. **P-EV-4** bank2 unans 25 × 2: 0 emitted texts in both modes (no admissible answer exists); L_meta ≥ 23 per mode (route (2) as before: 25/25); every run that
   attempts an emit ends L_struct with `no_evidence`.
5. **P-EV-5** bank4 35 × 2: **confident wrong 0/35 in each mode** (was 2/35); the trap value emitted 0 times; ADV-001 and ADV-010, woven as before, are refused with
   the codes of §8.2; content-level route (1) refusals (`no_evidence` before an abstention): ≥ 2 runs per mode (was 0).
6. **P-EV-6** by kind, both modes: near-fact 0/8, same-slot 0/10, numeric 0/8, entity-swap 0/9 wrong. Any wrong emission on bank4 is a gate bug, not a model choice.
7. **P-EV-7** cost: answerable loom runs that pass keep 1–4 ops; the four refused items cost more (lookups after the refusal): median input tokens of the 14
   answerable loom runs ≥ 1.5 × h55d's.
8. **P-EV-8** the owner's two routes over 60 unans × 2 modes: route (1) content refusals in ≥ 3 runs in total; route (2) (L_meta) ≥ 85 % of runs, as before.
   Route (1) remains rare because the model rarely builds on an unanswerable item (8 of 70 loom runs on bank4); the gate makes each such build end in a refusal.
9. **P-EV-9** answerable reach over the whole bank2 (69 items, not run): at most 12 [0]; the loom becomes a narrow but (on these banks) silent-when-unsure speaker.

If P-EV-5/6 fail, the gate has a bug (the probe says no admissible answer exists). If P-EV-1 falls below 3/7 under (a), the cause is the model (refusal, then no
retry on the right stretch) or the prompt, and the ledger shows which.

---

## 10. Risks, stated

1. **The cost on answerable questions is large and certain**: 57 of 69 gold occurrences are unreachable under (a). It is the price of a unit-level relevance test
   (no paraphrase, no relative-clause reading, no cleft). The measurement shows it; relaxing it (paraphrase lists, a kind check instead of the head word) would be new
   owner decisions, not designed here.
2. **Inherited cut artifacts** decide some subjects: the RUN filter drops 「オレカ」 (ADV-033's subject falls to {レベリオンR13, 本社}); 「結ぶムンバイ」 is one run
   (never read in a sentence: always refused, the safe direction). The probe found no unanswerable item where an artifact opens a door under the all-runs rule.
3. **The title stand-in** (OP-EV-1 (a)) trusts the corpus's article structure: a sentence of article T is taken to be about T. The annotation marks every such use.
4. **Prompt confound** (§7.7).

---

## 11. Tickets, decisions, tests

### 11.1 Tickets (build order; implementation Sonnet, review Opus, held-out tests codex)

| ticket | content | files | effort |
|---|---|---|---|
| **LOOM-evidence-1** | `verantyx/loom/evidence.py` (question_units, clause, gate; imports grammar, granularity, funcwords, space only — not wiring/cycle); state.py (`quote` marker, cleared with `span`); ops.py (weave_span.v3, begin `question` + `evidence_profile`, RULES["evidence"]); read.py (`no_evidence` in REFUSAL_ORDER and evaluate, `evidence` in the result); ledger.py (replay by recorded profile, `evidence_profile_unknown`); mcp.py / run_bank.py flags; score.py / report_unans.py (route (1) type); the two agent prompts (§7.7); LINE3_LOCAL_DECISIONS `## LOOM-evidence` (L-LOOM-170..190) | as listed + tests/line3/test_loom_evidence.py | 1.5 d |
| **LOOM-evidence-2** | held-out tests by codex from §3–§5 only (not from the code): the pinned tables of §3.1, §8, the trap table, the 0-of-60 admission sweep | tests/line3/test_loom_evidence_heldout.py | 0.5 d |
| **LOOM-evidence-3** | the 140-run re-measurement of §9 and `results_evidence/REPORT.md` (P-EV-1..9 judged; the other OP-EV-1 option computed offline on the new final threads as a side column) | experiments/line3/loom/runs_evidence, results_evidence | 0.5 d + API |
| LOOM-evidence-4 | Opus audit of 1–3 | — | — |

### 11.2 Local decisions (L-LOOM-170..190)

| id | decision |
|---|---|
| 170 | Evidence profile `{"version": "evidence.v1", "subject_scope"}` in the `begin` result; absent = no gate (all stored ledgers); replay by the recorded profile; unknown = INPUTS `evidence_profile_unknown`; a change of any rule of §3–§5 is a new version |
| 171 | Fallback slot: the first frame whose unit begins with an INTERROG member, when `slot_of` finds none |
| 172 | の-slot: 「どこの N q」 / 「どの N q」 cut with の → effective particle q, slot noun N |
| 173 | Forms slot / predicate / open; open is always refused (`question_form_open`) |
| 174 | Y forms = WORD-boundary suffixes of Y starting at a content word, ≥ 2 characters |
| 175 | S-runs from the RUN cut with the default filter (= the reader's query units), merged when touching; subject = outermost の-chain element (predicate), else ALL runs of the first non-empty level topic / が / case; every subject run must be read **[after review: 「a predicate question skips the subject check」 is evidence.v1 only; v2 refuses it, L-LOOM-192]** |
| 176 | Slot head = the content WORD after the effective particle; checked as a unit anywhere in the quoted sentence (sentence level, not clause level) **[after review: evidence.v1 only. v2: read in the clause, none = refuse, L-LOOM-195]** |
| 177 | IGNORE set; connective gaps (empty, 「は、」, or a P7(+も) stack without 、); the clause on WORD; the evidence cross = `grammar_cross` of the clause window |
| 178 | Reading a run: touching WORD units disjoint from the answer; in the title by `words_of(title)` |
| 179 | Slot arm = `grammar.follower(words_of(sentence), end of the answer's last WORD, "whole_word")` is the effective particle |
| 180 | Copula for predicate questions: P1 「Y は A」 (A starts right after Y は / は、), P2 「A は … Y」 (only arm particles or nothing between A は and Y) |
| 181 | Echo: a question unit / subject run / Y form read inside the answer is refused |
| 182 | Evidence is derived from the woven quote; no evidence argument, no emit_from (§6) |
| 183 | weave_span.v3 = v2 + unhashed `quote` marker (w, sid, tier, i0, i1), cleared like `span` |
| 184 | One refusal type `no_evidence` (codes + messages per weave), between constructed_forbidden and unstable_cross; never names another sentence |
| 185 | `begin.question`: the cut, read-only, recomputed by the gate, hashed in the begin row |
| 186 | Prose only; code tasks unchanged; a CHAR or RUN weave is judged on WORD (must be WORD-aligned) |
| 187 | `evidence` list in `read` / `emit` results (clause, subject via clause/title, arm or copula) |
| 188 | `no_evidence` is a route-(1) structural refusal in `layer_report` and `OWNER_NAMED` |
| 189 | Prompt paragraph; removal of the hand-building advice and of the 1975年 example; examples must pass the gate |
| 190 | OP-EV-1 default `clause_or_title` until the owner answers; every result labelled with the scope |

### 11.3 Tests (T-EV-nn)

| id | test |
|---|---|
| 01 | `question_units` on the 10 + 25 + 35 bank questions: form, p, slot noun, Y, Y forms, subject + level, slot head (the table of §3.1 extended; values from the probe) |
| 02 | clauses on pinned sentences: 292 (1981年 → 「1981年に永豊企業株式会社のカメラ事業部門」), 143 (青 → 「アメリカを「青」と色分け」, 赤 → 「イギリスを「赤」」), 86, 579, 123, 324, 348, 152 |
| 03 | the 14 h55d answerable final threads replayed into a v3 run under both scopes → the verdicts of §8.1 (3 + 3 pass under (a), 0 under (b)) |
| 04 | ADV-001 ×2 / ADV-010 ×2 final threads → the codes and message strings of §8.2 |
| 05 | the bank4 trap table: 33 aligned traps refused, by kind 8/8/8/9 |
| 06 | the admission sweep (about 25 s, evidence.v1 pins): for the 60 unanswerable questions no single WORD unit of the corpus passes, under both scopes; for the 7 answerable loom tasks the admitted single units are exactly I2-013 {県}, I2-025 {青}, I2-034 {年}, I2-041 {Sol} under (a) and I2-041 {Sol} under (b). **[after review] + the multi-word sweep (T-EV-21, about 2.5 min): every stretch of at most 10 WORD units of every sentence, 60 unanswerable questions: 0 of 60 admit any under evidence.v2; 69 answerable: the wrong-admitting items under v1 (21; the review: 20) and under v2 (0), and the reach lists (12 -> 10).** |
| 07 | every stored ledger (h55..h55d, unans, unans_adv, code) still verifies and replays IDENTICAL (no profile = no gate) |
| 08 | a new scripted v1 run: `begin` has `question` and `evidence_profile`; replay IDENTICAL; a forged `question` in the row → REPLAY_DIFFERS; unknown profile → INPUTS |
| 09 | constructed unit in a thread → `no_evidence/constructed_unit` in both modes; hand-seated record cross → `not_quoted`; drop / unseat / swap of one cross of a weave → `not_quoted` for the weave |
| 10 | refusal order: a thread both unstable and evidence-less lists both, `no_evidence` first; the emit row's `refusal` is `no_evidence` |
| 11 | E-6: 「旧社格は県社」, 「アメリカを青」 refused; 「ハッシュ表」 not refused by E-6 |
| 12 | determinism under PYTHONHASHSEED 0 / 1 / 12345 (question cut, clause, payload bytes) |
| 13 | the gate's attachment equals an `Attachment` of `wiring.records_of(space)` for the pinned slot cases (年→に in 292, 青→と in 143) |
| 14 | the RUN cut of step 6 equals `wiring.intake(space, q).units` filtered by the same content predicate, on every bank question |
| 15 | code tasks K1–K5 unaffected; `test_no_gold_in_the_agent_prompts` passes; the new prompt examples pass the gate |

| 16 | **[after review]** F1: `IEEE 488の通称は何ですか` → PSE (パリ経済学校#1) and `駅番号は何ですか` → JR-Y13 (川原石駅): v1 admits, v2 `question_has_no_subject`; through the server v1 emits, v2 refuses; the same quote with its subject passes |
| 17 | F2: pieces of a word (JR, 県, さん, 年, 日本, 気候) → `answer_glued`; 気象条件は日本海側気候 and the stretch over 「、」 / 「（」 → `answer_crosses_break`; whole words / phrases (県社, 権現さん, 日本海側気候, JR-Y13, キューバの太陽) pass; 「とも」 is a particle stack in the v2 clause |
| 18 | slot head in the clause: 1981年 (設立 outside) and 青 (no head) → `no_slot_head` in v2, passing in v1; the messages |
| 19 | F3: two passing quotes → `multiple_answers` (v1 emitted 「県社県社」); dropping one lets the other go; 1981年 + 年 is now two refusals |
| 20 | versions: begin row v1 / v2 (rules text, `question.evidence`), a forged version → REPLAY_DIFFERS, the h55d final threads: v1 6 pass, v2 2 pass (I2-013) |
| 21 | the multi-word sweeps (see row 06) |
| 22 | gated smoke test (v1 and v2): QUESTION_ECHO notes, caps (lookup_cap at 30), stability entries, note rows replay |
| 23 | route (1) as the final thread re-judged offline (`score.final_thread_gate`, `layer_report(final=)`): ADV-001 shown, ADV-021 unseen, ADV-013 empty thread, I2-034 emitted; a no-gate run has none |

### 11.4 Residual owner question

**OP-EV-1** (§0.1) only. The cost of §2.4 / §10.1 is reported, not asked: it follows from the owner's rule and is what the re-measurement is for.

---

## 12. evidence.v2 (the review of 2026-10-12; L-LOOM-191..)

`evidence.v2` = v1 + the changes below, each a rule change and therefore a new version (L-LOOM-170); the 140 ledgers of the measurement carry v1 and replay under it,
new runs get v2 (`--evidence v2`, the default; `v1` and `off` remain).

| change | rule (v2 only) | code |
|---|---|---|
| F1 | a predicate question whose subject is empty is `question_has_no_subject` (v1 skipped E-3 for it) | `question_has_no_subject` |
| F2a | the answer is not glued: the gap before its first WORD unit and the gap after its last one must not be empty (after IGNORE) or only joiner punctuation (`- ‐ ‑ – — − , . : / +`). A WORD unit of this corpus is often a piece of a word (日本 / 武尊), so "whole word" = the maximal run of touching or joined units | `answer_glued` (the message names the whole word) |
| F2b | no gap INSIDE the answer other than empty, joiner punctuation or 「の」: a bracket, 「、」, a word, a particle は を に で が と も is a break. (Stricter than "a clause break" in the sense of 4.2, which let 「気象条件は日本海側気候」 through: は is connective.) | `answer_crosses_break` |
| F3 | at most one passing weave stands in the thread; the second and later passing weaves are listed in `crosses` | `multiple_answers` |
| S | the slot head is read in the CLAUSE of the answer (outside the answer); a slot question with no head is refused (owner 2026-10-12, defect 2) | `no_slot_head` |
| C | the clause reads a gap of only particle characters, the first one of は の に で と を が (「とも」 「でも」 「をも」), as connective; `words_of` reads 「とも」 as one function word, so the v1 clause stopped there | (clause bounds) |

Measured (T-EV-16..21, from the corpus): reach 12 -> 10 of 69; answerable items admitting a wrong stretch 20 (review; 21 by the product probe) -> 0; unanswerable 0 of 60;
of the stored emitted texts, 県社 x2 would still pass, 青 and 1981年 x2 would be refused. The agent prompts are NOT changed for v2: the refusals carry the codes and messages,
and the begin `rules.evidence` text names the extent and the single answer.
