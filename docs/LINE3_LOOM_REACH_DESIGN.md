# LINE3_LOOM_REACH_DESIGN — 到達を広げる: widening the evidence gate's reach without admitting an unanswerable question

作成: 設計役（Opus 5.5, 2026-10-13）。Ticket **LOOM-reach-0** (design only). Target: `wt/line3` (branch line3), base HEAD `cb6d5f65` (the commit that records the
owner's decision). No product code was written and nothing was committed. Every (O) number below comes from a scratch probe run on Pro with
`/Users/motonisihikoudai/vera-wiring/env/bin/python`, `PYTHONPATH=.`, over `experiments/line3/bank2/data/fulllead_sents.jsonl` (592 sentences), `bank2.tsv`,
`bank4.tsv` and the loom task files (read only). The probe lives in the session scratchpad (`scratchpad/reach/`: `common.py`, `judge.py`, `sweep.py`, `equiv.py`,
`exposure.py`); it is not committed. LOOM-reach-1 rebuilds the chosen rules in product code and pins the same numbers as tests (§8.3). `vera-impl/hidden` was not
opened. No network. Implementation: Claude Sonnet. Review: Claude Opus. Held-out items: codex.

---

## 0. How to read this document

Marks as in `docs/LINE3_LOOM_EVIDENCE_GATE.md` §0: 【オーナー】 verbatim owner words; 【推奨】 the designer's proposal; 【L-LOOM-nn】 an engineering choice the
implementer copies into `docs/LINE3_LOCAL_DECISIONS.md` under a new heading `## LOOM-reach`; (O) counted for this document; (C) taken from another document.
The usual rules hold: a tie abstains and order never makes a winner; nothing is cut off silently; no float; byte-identical across `PYTHONHASHSEED` 0 / 1 / 12345.

### 0.1 The decision this design implements

| Point | 【オーナー】 verbatim (ops/decisions/2026-10-06_line3_faithful_build.md, last section, 2026-10-13) |
|---|---|
| 織機の次（複数選択） | 「門 v2 でモデルの再計測 (Recommended)」「到達を広げる」「公開の準備」— 全部 |

This document is the second item only: 「到達を広げる」. The constraint it keeps is the one the gate exists for: **0 unanswerable admissions**, and no new wrong
answerable stretch unless the owner accepts it by name (§7).

### 0.2 Result in one table (O)

| set | reach (of 69 answerable) | answerable items admitting a wrong stretch | unanswerable admissions (of 60) | bank4 trap values admitted |
|---|---|---|---|---|
| evidence.v2 (today) | **10** | 0 | 0 | 0 |
| **recommended safe set = evidence.v3 (§5)** | **22** | **0** | **0** | **0** |
| safe set + inflected head (owner question OP-RE-1) | 24 | 1 (I2-007 「廃止」) | 0 | 0 |
| every candidate of §4 at once (not proposed) | 28 | 7 | 0 | 0 |

---

## 1. Method

### 1.1 The sweep (the T-EV-21 sweep, reproduced)

For each of the 129 items (69 answerable bank2 `intra2`/`fulllead` items; 60 unanswerable = bank2 `unans`/`fulllead` 25 + bank4 35, question texts from the loom
task files exactly as T-EV-21 takes them), for every sentence of the corpus and every stretch of 1..10 WORD units (53,733 stretches per item), the probe asks the
gate under the title scope (`clause_or_title`, the default; a stretch that passes under `clause` also passes under it).

* **reach** = answerable items with at least one passing stretch whose normalised text (NFKC, casefold, no spaces, no 「・」) is one of the gold alternatives;
* **wrong-admitting** = answerable items with at least one passing stretch that is not a gold;
* **unanswerable admissions** = unanswerable items with any passing stretch;
* **bank4 trap admissions** = bank4 items whose trap value (c) is among the passing stretches.

### 1.2 The probe judge equals the product gate

`judge.py` is a parametrised copy of `evidence.judge_quote` (v2 path, WORD tier, title scope): with no flag set it must be the product gate. `equiv.py` compares the
two on every stretch of every item: **0 mismatches over 129 × 53,733 = 6,931,557 judgements** (the product passes exactly 10 stretches, one per reached item). Every
candidate is a flag on this judge, so a difference in a row of §4 is caused by that candidate alone.

### 1.3 (a) The baseline, reproduced (O)

evidence.v2: reach **10 of 69** (I2-003, I2-004, I2-005, I2-006, I2-013, I2-014, I2-018, R2-I005, R2-I007, R2-I017 = `REACH_V2` of the tests); wrong-admitting
**0**; unanswerable admissions **0 of 60**; bank4 traps **0**. Identical to T-EV-21 and to `docs/LINE3_LOCAL_DECISIONS.md` L-LOOM-195/199.

The 59 unreachable items, per item on the occurrence of the gold with the fewest codes (product `judge_quote`, v2; an item can carry several): `no_slot_head` 39
(25 of them the predicate form's "Y not in the clause"), `no_subject` 21, `answer_glued` 14, `wrong_arm` 11, `answer_holds_question_unit` 8, `question_form_open` 8,
`question_has_no_subject` 4, `not_copular` 3; gold not WORD-aligned 5 (I2-010, I2-016, I2-028, I2-038, R2-I011).

---

## 2. The review's proposals, re-measured

The review notes gave four numbers. Under the exact rules of §4 the probe finds:

| review note | review's number | this probe | why it differs |
|---|---|---|---|
| (1) kind noun of the question word may be in the answer | +2 (I2-015, I2-042), 0 unans | **+1 (I2-042)**, 0 unans | I2-015 also needs the chained question word (どの市のどの区 → the slot is どの区), the particle after 「の + 一部」, AND the head あたり ↔ あたる (an all-kana verb; the inflection rule C3 deliberately skips all-kana words). With C1 + C2b + C2c + C3 it is still unreached |
| (2) slot particle after a parenthesis / reading gloss, or after 「の + slot noun」 | +4 (I2-027, I2-029, I2-045, R2-I002), 0 unans | **+2 (I2-027, I2-045)**; it also admits a wrong stretch (I2-028 「曲輪遺跡」) unless the prefix-glue fix T1 is added (then 0) | I2-029 is a coordination (「和歌山千葉線」、…「和歌山線」とも案内), not a gloss: rule C15, which admits a wrong stretch for R2-I005. R2-I002 「鳳珠郡能登町の一部」: 能登町 is glued to 鳳珠郡 and the question has no slot head (なっ is a function word): unreachable |
| head matching by kanji stem (unsafe) | +2, admits ADV-037 | +2 (I2-007, I2-021), **admits ADV-037** (「11月6日」: 開業 ~ 開催 by the stem 開) | reproduced |
| relaxing the copula (unsafe) | +3, admits UF-017 | 0 gain, 2 wrong (I2-044, R2-I008), 0 unans | a different relaxation (here: Y anywhere in the clause); the review's exact rule is not written down. Either way, not eligible |
| dropping the subject check | 19 unans | **15 unans** (10 of them bank4; the trap of ADV-030 admitted), +1 reach, 14 wrong-admitting items | not identified; the direction is the same |

---

## 3. What a candidate must satisfy

A candidate is **eligible** iff, alone (with only the tightenings T1 / T2 of §4.0, which change no v2 number), it gives **0 new wrong-admitting answerable items
and 0 unanswerable admissions**. The safe set (§5) is the union of the eligible candidates, measured together (interactions are measured, not assumed).

---

## 4. Candidates, one by one (O)

### 4.0 Two tightenings (companions; they change no evidence.v2 number)

| id | rule | effect |
|---|---|---|
| **T1 prefix glue** | the answer is `answer_glued` also when a **prefix** token (pos1 接頭辞, the tagger's reading of the whole sentence, the tagger `space._get_tagger` already used by `funcwords`) ends exactly at the answer's first character. Reason: a prefix is a function word, so it lies in the GAP of the filtered WORD cut (「ことから、大|曲輪|遺跡」: the gap is 「から、大」) and the v2 glue test does not see it | v2 alone: reach 10, wrong 0, unans 0 (no change). With the gloss rule it removes the only wrong stretch (I2-028 「曲輪遺跡」 for gold 大曲輪遺跡) |
| **T2 kind-only answer** | an answer whose text (IGNORE removed) equals a kind noun of the question (§4.1) or the slot noun is `answer_holds_question_unit` (「姓」 for 「何姓を」). The v2 echo set leaves units that contain an interrogative out (何姓), so the bare kind noun was never an echo | v2 alone: no change. With C3 it removes the wrong stretch 「姓」 (I2-021, sentence 130) |

### 4.1 The table

All rows are measured with T1 + T2 on unless marked "(no T)". "gain" = items newly reached over v2's 10. Exposure = how many of the 60 unanswerable items the rule
actually touches (question side: the rule applies to the question; sentence side: some stretch has strictly fewer failing codes with the rule than without);
it says how much the "0 unans" of that row is worth.

| id | rule (exact in §4.2) | gain (ids) | new wrong-admitting | unans adm. | bank4 traps | exposure on unans | eligible |
|---|---|---|---|---|---|---|---|
| C1 kind noun in the answer | the kind noun of the question word may end the answer | +1 (I2-042) | 0 | 0 | 0 | 34 questions have a kind noun; 1 item / 13 stretches moved | **yes** |
| C2a gloss before the particle | the arm particle may be read after one bracketed gloss right after the answer | +2 (I2-027, I2-045) | 0 (no T: 1, I2-028 「曲輪遺跡」) | 0 | 0 | 14 items / 160 stretches moved | **yes (with T1)** |
| C2b 「の + slot noun + p」 | with a slot noun N, the answer may be followed by 「の N p」 | 0 | 0 | 0 | 0 | — | no gain |
| C2c chained question word | 「どのA の どのB …」: the slot is the last question word | 0 | 0 | 0 | 0 | — | no gain (I2-015, see §2) |
| C2d kind noun after the answer | the answer may be followed by its kind noun, then p (「永樂（えいらく）姓を」); with C2a + C3 | +1 (I2-022) | **1** (I2-021 admits 「永樂」, the 10代以降 answer: the subject cut keeps only 善五郎, 「初代から9代まで」 is no subject) | 0 | 0 | — | no |
| C3 inflected head | slot head and a clause word with the same non-kana stem and both a kana ending (伴う ↔ 伴い, 名乗っ ↔ 名乗り) | +2 (I2-007, I2-021) | **1** (I2-007 「廃止」, the head of the gold 路線の廃止; without T2 also I2-021 「姓」) | 0 | 0 | 1 item / 10 stretches | **no — OP-RE-1** |
| C3x kanji stem (review's unsafe) | the head shares its first kanji with a clause word | +2 (I2-007, I2-021) | 2 | **1 (ADV-037)** | 0 | — | no |
| C4a naming verbs | a slot head in NAMING matches any NAMING word in the clause (呼ば ↔ 称さ ↔ いう); with C2a | +1 (I2-012) | 0 | 0 | 0 | 0 items moved | **yes** |
| C4b alias predicate | 「Xの別名/別称/異名は何」 also passes as 「A とも <naming verb>」 | +2 (I2-001, I2-035) | 0 | 0 | 0 | **0** (no unanswerable question asks 別名) | **yes** |
| C4c alias echo | for C4b only: a question unit that is a proper part of a subject run may be in the answer (アワド語 vs アワディー語's 語) | +1 (I2-026) | 0 | 0 | 0 | **0** | **yes** |
| C5 article aliases for the subject | a subject run may be read as an alias the same article declares (「A ともいう」, 「別名A」) | 0 | 0 | 0 | 0 | — | no gain |
| C6 relative clause with a kind-noun head | 「…V した Y は 誰/どこ/何」 with Y ∈ KIND_REL and no が before V: also judged as the slot question 「誰が … V」 (p = が, head = V) | +2 (I2-008, I2-032); with C11 +4 (also I2-048, R2-I015) | 0 | 0 | 0 | 1 question (UF-017, refused: no subject word) | **yes** |
| C6x relative clause, any Y, が or を arm | as C6 for every Y; arm を when the relative clause has a が | +2 (same) | 0 | 0 | 0 | — | not needed (no extra gain, wider exposure) |
| C8 location に ↔ で | p ∈ {に, で} accepts the other when the head is read | 0 | 0 | 0 | 0 | — | no gain |
| C9 head across て / し | the head may be read in the next clause when the clause ends in a te-form / 連用形 + 「、」 | +1 (I2-034) | **1** (R2-I017 「成り立つ性質」) | 0 | 0 | — | no (also reopens the owner's L-LOOM-195 decision on I2-034) |
| C10 subject in the previous sentence | a subject run may be read in sentence sid−1 of the same article | 0 | **1** (I2-029 「和歌山線」: 和歌山バス is in #1, the answer is 京成バス's name) | 0 | 0 | — | no |
| C10g same, guarded | only when the quoted sentence has no は-topic of its own | 0 | 1 (same) | 0 | 0 | — | no |
| C11 joiner punctuation inside a read word | a subject / head / Y reading (clause and title) crosses a gap of joiner punctuation (`- , . : / +`) and keeps it: 「U-17」 | 0 alone; +2 with C6 (I2-048, R2-I015) | 0 | 0 | 0 | 1 item / 59 stretches | **yes** (it is open point 2 of the v2 review, the title granularity, for joiners only) |
| C13 「Y としては A」 | the predicate copula also reads 「Y としては A」 | +1 (R2-I008) | 0 | 0 | 0 | **0** | **yes** |
| C14 「A が Y。」 and 名前 → the noun before it | Y 名前/名称 also read as the chain noun before it; 「A が Y」 at sentence end is a copula | +1 (I2-019) | **2** (I2-019 「熊の「BAN BAN」, I2-044 「強いこと」) | 0 | 0 | — | no |
| C15 coordination with も | 「A」、 … 「B」とも <head>: A takes the arm of the parallel 「p + も」 | +1 (I2-029) | **1** (R2-I005 「和歌山千葉線」: the same sentence, the other bus company) | 0 | 0 | — | no |
| X copula relaxed (contrast) | Y anywhere in the clause | 0 | 2 | 0 | 0 | — | no |
| X no subject check (contrast) | E-3 dropped | +1 (I2-050) | 14 | **15** | 1 (ADV-030) | — | no |

### 4.2 The rules, exact (the eligible ones; numbered for L-LOOM)

All offsets and readings are those of `docs/LINE3_LOOM_EVIDENCE_GATE.md` §3–§4 and §12 (evidence.v2) unless stated. "Read" = §4.3 of that document
(`_read_in`), extended by R6 below.

**R1 (C1) kind nouns.** `kinds(q)` = for every WORD of `words_of(question)` that is in `grammar.INTERROG`, the concatenation of the content WORD units glued to it
(no character between; 何|線 → 線, どの|区 → 区, 何|年 → 年); if that is empty and the word is どこ followed by 「の」 and a touching content WORD, that word
(どこの国 → 国). In E-6 a question unit u ∈ kinds(q) does not count as an echo when every reading of u inside the answer starts after the answer's first WORD unit,
and, if u is the last kind noun of the question, one reading ends at the answer's last unit (新潟市西区 for どの区: allowed; 区 alone, or 区役所: refused). T2 refuses
the bare kind noun. Every other question unit is still an echo.

**R2 (C2a) one gloss before the arm particle.** If, after the answer's end, skipping IGNORE characters, the next character is 「（」 or 「(」 and its matching closing
bracket (nesting counted) comes before any 「。」, let e = the offset after that closing bracket. Only when the answer's clause ends at the answer (hi = a1): E-4s reads
the follower at e (`grammar.follower(raw, e, "whole_word")`); the clause continues from the first WORD unit starting at or after e if the text between is connective
(`connective(…, stacked=True)`), and extends right as usual. The units INSIDE the brackets are not part of the clause: no subject, head or Y is read there. One gloss
only, right after the answer only. Requires T1.

**R3 (C4b, C4c) the alias predicate.** For a predicate question whose Y is exactly one of ALIAS_Y = {別名, 別称, 異名}, a stretch passes if it passes v2, or if: the gap
after the answer is exactly 「とも」 (IGNORE removed); a word of NAMING = {呼ば 呼ぶ 呼び 呼ん 称さ 称し 称する 称 いう 言う 云う} is a WORD unit of the clause outside
the answer; the subject is read (clause or title, unchanged); E-6 holds, except that a question unit that is a proper substring of a subject run and is not itself a
subject run may occur in the answer (R3b). 通称 / 愛称 / 略称 / 旧称 are NOT in ALIAS_Y (a nickname, an abbreviation, a former name are not "another name"; 「ともいう」
does not say which).

**R4 (C6) the relative clause with a kind-noun head.** For a predicate question whose Y is exactly one of KIND_REL = {人物 人 者 国 チーム 選手 団体 施設 会社 組織
都市 街 場所}: walk left from Y's first WORD over non-content words, counting auxiliaries (any non-P7 function word); one 「と」 may be passed after at least one
auxiliary (「地とされた」); stop at any other P7 particle. If at least one auxiliary was passed and the walk ends on a content word V, and no 「が」 occurs among
the question's words before V, the item may ALSO be judged as a slot question with particle p = が, head = V, no slot noun, the same subject and the same echo set
(V is an echo). 唯物史観を唱えた人物 → 「A が … 唱え」; 千里馬運動の発祥の地とされた施設 → 「A が … 地」; 初優勝した国 → 「A が 初優勝」.

**R5 (C13) 「Y としては A」.** For a predicate question: if the gap right before the answer is 「としては」 or 「としては、」 (IGNORE removed) and a Y form is read ending
at the unit right before that gap (within that unit's own clause), the copula holds; the subject is then read in the union of the answer's clause and Y's clause.
「として」 alone, 「では」, 「には」 are not included.

**R6 (C11) joiners inside a read word.** When a subject run, a Y form or a head is read (clause or title), a gap made only of `evidence.JOINERS` is crossed and its
characters are part of the spelled string (「U-17ワールドカップ」 is read in the title 「2017 FIFA U-17ワールドカップ」). A joiner gap is still not crossed by the
answer's extent rules (F2 unchanged).

**R7 (C4a) naming verbs.** A slot head that is in NAMING is read when ANY NAMING word is a WORD unit of the clause outside the answer (呼ば in the question,
称さ in 「深川八幡宮（ふかがわはちまんぐう）とも称さ」).

**T1, T2** as §4.0. Every other v2 check is unchanged (F1, F2, F3, S, C, E-3 subject, head required).

---

## 5. (c) The safe set and its reach (O)

**evidence.v3 【推奨】 = v2 + R1 + R2 + R3 (with R3b) + R4 + R5 + R6 + R7 + T1 + T2.** Measured together:

| measure | v2 | v3 |
|---|---|---|
| reach (of 69) | 10 | **22** |
| new ids | — | I2-001, I2-008, I2-012, I2-026, I2-027, I2-032, I2-035, I2-042, I2-045, I2-048, R2-I008, R2-I015 |
| answerable items admitting a wrong stretch | 0 | **0** |
| unanswerable admissions (of 60) | 0 | **0** |
| bank4 trap values admitted | 0 | **0** |
| the same set without T1 / T2 | — | reach 22, **1 wrong** (I2-028 「曲輪遺跡」): T1 is load-bearing |

Attribution (each gain needs exactly the rules named; measured by single-rule and pairwise runs): R1 I2-042; R2 I2-027, I2-045; R2 + R7 I2-012; R3 I2-001, I2-035;
R3b I2-026; R4 I2-008, I2-032; R4 + R6 I2-048, R2-I015; R5 R2-I008. No interaction gains or losses beyond these: the union of the single-rule gains is the set's
gain. The passing answers are each item's gold, e.g. カール・マルクス, 製鋼所, ハッシュ表, 黒パン / ライパン, アワド語, ゴゴプラッタ, MtF, 深川八幡宮, 新潟市西区,
イングランド, ウルトラプリニー式噴火.

What stays out (47 items): `no_slot_head` 18 (mostly paraphrase: 当代 / 現在, 住民数 / 人口, 出身地 / 出身), `answer_glued` 16, `no_subject` 9, `question_form_open`
8, `wrong_arm` 3, gold not WORD-aligned 5. The gate still refuses paraphrase that the article does not mark itself; that is its cost, unchanged.

---

## 6. (d) Held-out risk and the held-out check

### 6.1 The risk, stated with the exposure numbers

Every rule here was designed while looking at the 69 + 60 items; "0 unanswerable admissions" was measured on the banks that suggested the rules. Worse, most of the
new rules are barely exercised by the unanswerable banks (§4.1 exposure): **no unanswerable question asks 別名 (R3: 0), none has 「としては」 near a candidate (R5: 0),
none has a naming-verb head (R7: 0); R4 applies to exactly one (UF-017, refused only because its subject cut is empty)**. Only R2 (14 items, 160 stretches moved
closer to passing) and R1 (34 questions carry a kind noun) are really tested. So for R3, R4, R5, R7 the 0 is an absence of a test, not a pass.

### 6.2 The held-out check 【推奨】

1. **Freeze.** LOOM-reach-1 lands evidence.v3 with the pins of §8.3; the sha256 of `verantyx/loom/evidence.py` and of this document are written into the held-out
   ticket. No v3 rule changes after the freeze (a change is evidence.v4 and needs a new held-out set).
2. **Write (codex, gpt-6-luna, which has not read the gate code).** A new bank `experiments/line3/bank6/` over the SAME corpus (fulllead_sents.jsonl), TSV in the bank4
   format (#id, kind, corpus, subject, question, gold or empty, evidence sids, notes with a)/b)/c) trap, audit):
   * **~30 unanswerable**, at least 4 per rule R1–R7 plus 2 for T1, each built so the rule's surface pattern IS in the cited sentences but the asked fact is not:
     a 別名 question on an article whose 「ともいう」 names another thing or another level (R3); a 「…を唱えた人物」-type question where the sentence has
     「A が」 with a different object (R4); 「Y としては」 with a near-Y (R5); a gloss after a near-fact value (R2); a 「何と称され」 question whose sentence names
     something else with 「とも呼ばれ」 (R7); a どの区 question whose sentence has another ward (R1); a hyphenated title with a different event (R6).
     codex gets a plain-language description of the seven patterns (§4.2 in words), not the probe and not the code.
   * **~30 answerable**, natural questions with gold, written WITHOUT the rule list (so reach is not tuned to the rules): one question per article not used by bank2
     where possible.
3. **Audit (Opus, without running the gate).** Validity only (answerable from the cited sentence, unanswerable from the whole corpus, one gold, no ambiguity), as
   AUDIT4.md did. Fixed / dropped items are listed before any run.
4. **Run once.** `sweep` = the T-EV-21 sweep on bank6 under v2 and v3, title scope; report reach, wrong-admitting items, unanswerable admissions, trap admissions,
   per rule (which rule's variant passed: the probe's `tag`).
5. **Acceptance.** v3 becomes the server default only if bank6 unanswerable admissions = 0 and wrong-admitting answerable items ≤ v2's on bank6. If a rule admits an
   unanswerable item, that rule is removed (v3 minus that rule = v4, re-run on a fresh set) — never patched to fit bank6.

---

## 7. (e) Version, decisions, tests, owner questions

### 7.1 Version

`evidence.v3` (L-LOOM-170: any rule change is a new version). v1 and v2 stay byte-identical; the 140 v1 ledgers and any v2 ledgers replay under their recorded
version. `PROFILE_NAMES["v3"]`, `--evidence v3`. **The server / CLI / harness default stays v2 until §6.2 step 5 passes** (OP-RE-2). `EVIDENCE_RULE_V3` =
`EVIDENCE_RULE_V2` + one sentence: "The answer may end with the kind word of the question word (○○区 for どの区); a reading in brackets may stand between the answer
and its particle; 「A ともいう」 answers 別名; 「A が V」 answers 「V した人物/国/…」; 「Y としては A」 reads as 「Y は A」."

### 7.2 Local decisions (L-LOOM-201..)

| id | decision |
|---|---|
| L-LOOM-201 | EVIDENCE.V3 = v2 + R1..R7 + T1 + T2 (§4.2, §4.0); `EVIDENCE_VERSIONS += (evidence.v3,)`; default stays v2 (until OP-RE-2). |
| L-LOOM-202 | R1 kind nouns: `kind_nouns(question)` is part of the question cut (`QuestionUnits.kinds`, written into the begin `question` object under v3 only; under v1/v2 the begin object is byte-identical to today). |
| L-LOOM-203 | R2 gloss: one bracket group right after the answer, only when the clause ends at the answer; units inside the brackets are outside the clause. |
| L-LOOM-204 | R3 / R3b alias: ALIAS_Y = {別名, 別称, 異名}; NAMING as listed; the alternative reading is an OR with the v2 predicate reading; the evidence entry records `"via": "alias"`. |
| L-LOOM-205 | R4 relative clause: KIND_REL as listed (closed list; extending it is a new version); the evidence entry records `"via": "relative", "head": V`. |
| L-LOOM-206 | R5 「Y としては A」: `copula = "Y としては A"`. |
| L-LOOM-207 | R6 joiners inside readings (subject, Y, head; clause and title); not in the extent rules. |
| L-LOOM-208 | R7 naming-verb equivalence for slot heads. |
| L-LOOM-209 | T1 prefix glue: the whole sentence is tagged once (cached per corpus sha and sid, as `_VIEWS`); only pos1 接頭辞 counts. T2 kind-only answer. Both are tightenings and apply in v3 only (v2 is not edited). |
| L-LOOM-210 | Not adopted, with their numbers (§4.1): C2b, C2c, C2d, C3 (owner question), C3x, C5, C6x, C8, C9, C10, C10g, C14, C15. |
| L-LOOM-211 | Held-out protocol §6.2; bank6 is written after the freeze sha is recorded; the run is once. |

### 7.3 Tests (T-EV-24..; tests/line3/test_loom_evidence.py; v1/v2 pins untouched)

| id | test |
|---|---|
| 24 | the question cut under v3 for every bank question: `kinds`, the R4 variant (I2-008 head 唱え, I2-032 地, I2-048 優勝, R2-I015 優勝, UF-017 refused: no subject), the R3 alias form (I2-001, I2-026, I2-035) |
| 25 | per-rule unit probes on the real sentences, positive and negative: 新潟市西区 passes / 区 alone refused (T2) / 姓 refused (I2-021, sentence 130); ゴゴプラッタ, MtF pass / 曲輪遺跡 glued (T1); ハッシュ表, アワド語 pass / 「ハッシュ」 alone refused; カール・マルクス passes; ウルトラプリニー式噴火 passes; 深川八幡宮 passes; the non-adopted cases stay refused under v3: 廃止 (I2-007), 永樂 for I2-021, 和歌山線 for I2-029, 和歌山千葉線 for R2-I005, 成り立つ性質, 11月6日 (ADV-037) |
| 26 | the sweep (as T-EV-21, v3 added; about +1 min): reach v3 = the 22 ids of §5, wrong-admitting 0, unanswerable 0 of 60, bank4 traps 0; v2 still 10 / 0 / 0 |
| 27 | ablation pins: removing each rule loses exactly its ids of §5 (the attribution table), and removing T1 makes I2-028 wrong-admitting |
| 28 | versions: v1/v2 ledgers replay IDENTICAL; a v3 begin row carries `kinds` and EVIDENCE_RULE_V3; a forged v3 → v2 relabel is REPLAY_DIFFERS; default is v2 |
| 29 | `PYTHONHASHSEED` 0 / 1 / 12345 byte-identical for 24–28 |
| 30 | (after bank6 exists) the held-out sweep, pinned with the numbers of the single run |

### 7.4 Owner questions (≤ 3)

| id | question | options (recommended first) |
|---|---|---|
| **OP-RE-1** | The inflected head (C3: 伴う ↔ 伴い, 名乗っ ↔ 名乗り) adds 2 items (I2-007 路線の廃止, I2-021 西村姓; reach 22 → 24) and admits 0 unanswerable, but admits **one new wrong answerable stretch**: 「廃止」 for I2-007 (the head noun of the gold 「路線の廃止」, a cut-short answer). Accept it? | **(a) No: keep "0 new wrong" as the bar; C3 waits for an extent rule that refuses a cut-short の-phrase 【推奨】** (b) Yes: a partial answer is not a false fact; accept 24 with 1 wrong-admitting item |
| **OP-RE-2** | When does v3 become the default for new prose runs? | **(a) After the held-out bank6 passes (§6.2) 【推奨】** (b) Now, with bank6 as a later check (the model re-measure 「門 v2 でモデルの再計測」 would then run under v3, not v2) |
| **OP-RE-3** | R3 and R4 read the question's MEANING through the sentence's own markers: 「A ともいう」 is taken as an answer to 「別名は何」, and 「A が唱えた」 as an answer to 「唱えた人物は誰」. The v1 design said the gate "refuses paraphrase"; these two are marked paraphrase (the sentence's own 「ともいう」 / the relative clause of the question). Do they count as 「質問の slot の腕から読める」? | **(a) Yes, both 【推奨】** (+5: I2-001, I2-026, I2-035 via R3; I2-008, I2-032, I2-048, R2-I015 via R4 — reach 22) (b) R3 only (reach 18) (c) neither (reach 15: R1, R2, R5, R6, R7) |

---

## 8. Notes for the implementer

1. The probe's `judge.py` shows the shape of each rule as flags on a copy of `judge_quote`; the product version must keep v1 and v2 paths byte-identical (the probe's
   equality check over 6.9 M judgements is the model for the v2 regression pin).
2. R2's "only when the clause ends at the answer" matters: a gap 「 (」 is never connective, so this is always true when a bracket follows; state it anyway.
3. R4 is an OR of two judgements of the same stretch (predicate reading and slot reading); E-6 and E-3 are the same in both; report which one passed.
4. T1 needs the tagger on whole sentences (the line-3 tagger, already loaded by `funcwords`); cache by (corpus sha, sid) like `_VIEWS`.
5. I2-015 and R2-I002, named by the review as reachable, are not reached by any eligible rule (§2); do not tune for them.
