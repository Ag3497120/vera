# LINE3_LOOM_MEMORY_DESIGN — 空から始める構造: the loom as the model's memory, work log and context extension

作成: 設計役（Opus 5.5, 2026-10-12）。Ticket **MEM-0** (design only). Target: `wt/line3` (branch line3), base HEAD `cdb72525` (the commit that records the
owner's confirmation 「合っている。その設計を始めて」). No product code was written and nothing was committed. Every (O) number comes from scratch probes the designer
ran on Pro with `/Users/motonisihikoudai/vera-wiring/env/bin/python`, `PYTHONPATH=.`, on toy memory sentences written for this document (no corpus file read, no
stored ledger touched). The probes of the evidence gate ran in `wt/line3-loom-ev` **on its uncommitted working tree** (`evidence.v2`, L-LOOM-191..), because the gate is not
merged into line3 yet. The probes are not committed; MEM-a..c rebuild them as tests (§9.4). `vera-impl/hidden` was not opened. No network.
Implementation: Claude Sonnet. Review: Claude Opus. Held-out tests and the meter's gold lists: codex (the role split in the memory notes).

---

## 0. How to read this document

Marks as in `docs/LINE3_LOOM_DESIGN.md` §0: 【オーナー】 verbatim owner words; 【推奨】 the designer's proposal, not the owner's design; 【OP-MEM-n】 a point that
changes meaning and cannot be derived from the owner's words (until it is answered, the implementation uses the recommended default and every result is labelled
with it); 【L-MEM-nn】 an engineering choice that does not change meaning (the implementer copies it into `docs/LINE3_LOCAL_DECISIONS.md` under a new heading
`## MEM`); (O) counted by the designer for this document; (C) taken from another document and not re-counted. The usual rules hold: a tie abstains and order never
makes a winner; nothing is cut off silently; no float; byte-identical across `PYTHONHASHSEED` 0 / 1 / 12345.

### 0.1 The owner questions (three; the recommended option first)

| id | Question | Options (recommended first) | Blocks |
|---|---|---|---|
| **OP-MEM-1** | May the model's **own memory sentences** be the evidence from which the structure learns **which particle a word takes** (adhesion, the `a` of the key (n, p, a), UNANCHORED, the grammar records)? Today L-547 says "memory sentences are not corpus text": adhesion and the grammar records read only `kind = base` sentences | **(a) Yes, inside the memory space only 【推奨】.** The memory is its own space (N-16 「毎回、別の空間として読み」), holding nothing but the model's sentences; they are stored with `kind = base` **in that space**, and the provenance lives in `source = "mem:<store>/<session>#<i>"` and in the memory ledger. A guard refuses any row without the `mem:` prefix in a memory space, and any `mem:` row in a non-memory corpus (L-MEM-02), so the two never mix. Consequence (O): adhesion counts appear (`東京`+で = 2 after two sentences), the key's `a` and UNANCHORED work against the memory's own history, and the line-3 grammar layer can read the memory later. / (b) No: store them as `kind = memory_answer` (N-17 literally). Weave, the evidence gate and recall work unchanged (O: the same answers as (a)); adhesion stays empty, so `a` = 0 always and UNANCHORED never fires (O: `counts {}`). What is lost is only the NEW_RELATION / UNANCHORED information of §3.3, which is not counted as a detection anyway. / (c) As (a), but the adhesion of a session counts only the sentences of EARLIER sessions (a stricter 「継いだ情報を新しい証拠として数えない」) | MEM-a writes the `kind`; MEM-b reads adhesion. Both can be built under any option (one constant) |
| **OP-MEM-2** | **What is a contradiction in the memory?** The existing note CONFLICT (same centre, same arm, different units) keys on the HEAD of 「X の Y は A」: it compares the X's of two Y's | **(a) Two statements that answer the same question differently 【推奨】.** On every write of a clause 「[X の] Y は A」 the structure asks ITSELF 「[X の] Y は何ですか」 through the evidence gate over the memory (recall, §4.3); two or more distinct passing answers = **CONFLICT/same_question** (a note: it blocks nothing). The existing arm CONFLICT stays as a note but is **not counted** as a detection. Probe (O): finds 田中の担当 認証 vs 決済 and サーバーのポート 8080 vs 9090; does not flag 認証の期限 金曜 vs 決済の期限 月曜. / (b) Only the existing arm CONFLICT (no new reading). Probe (O): misses both planted contradictions above and flags 3 enumerations in 9 sentences (期限 ← 認証/決済, 前提 ← 認証/決済, 支店 ← 東京/大阪). / (c) Both, both counted | MEM-c (the self-question). MEM-a/b are independent |
| **OP-MEM-3** | **A sentence the structure cannot seat**, and when a changed placement counts as 「構造が検知した」 | **(a) The write is refused and nothing is stored; the model rephrases. A rephrase counts as a structural detection only when what made it rephrase was about CONTENT (a CONFLICT/same_question or REVERSAL note on its write) and the rephrased write changes content; a rephrase after a SHAPE refusal (`span_inexpressible`: two case particles before one head, a gap that is not a particle) is counted as cost, in its own column 【推奨】.** Reason (O): 8 of 25 ordinary work-log sentences are shape-refused although nothing in them is wrong (「東京で会議を開く」, 「佐藤が予算を決めた」); counting those would make the detection count measure the weave rule's grammar, not contradictions. / (b) Refused, and every refused-then-rephrased write counts as a detection (the owner's sentence read literally). / (c) Stored verbatim, only the expressible stretches seated; nothing is refused, so no placement ever changes (the memory keeps everything the model said, the structure sees less of it) | MEM-a (refuse or store), MEM-g (the headline column). The meter reports both counts under any option, so the answer changes only which column is the headline |

Everything else is fixed below as 【L-MEM-nn】 or 【推奨】. One point that could have been a fourth question is fixed as a default, stated so the owner can overturn it:
**there is no retraction in v1 (L-MEM-13)**. A later statement never silently replaces an earlier one; both stay, recall lists both (a CHOICE), and the
contradiction stays visible. (The Vera session layer's rule 「append a superseding row instead」 is the natural v2; it is not built here.)

---

## 1. Constraints, verbatim

### 1.1 The decision this design implements

| Point | 【オーナー】 verbatim (ops/decisions/2026-10-06_line3_faithful_build.md, 「証拠の門の審査後の決定」) |
|---|---|
| 構想 (2026-10-12) | 「仕組みとしてこの構造は初め何も入っていない状態でスタートするレベルで良いと思っています。この構造に入れることで矛盾しているのが分かったりバグがわかったりするように構造の力でデータがなくてもわかるような形で。構造は記憶としてや作業ログとしても機能してモデル自身のコンテキストの拡張にもなるという形。成長するごとにveraも成長する形。構造に語がないときなどはモデルが補ってやることによって矛盾を発見したり構造に入れれないというので配置を変えたのなら構造が検知したとも言えると思う」 |
| 確認 | 「合っている。その設計を始めて (Recommended)」 — on the reading: the loom may start from an EMPTY structure; the detection power comes from the structure's rules (seating rules, the key, typed notes such as CONFLICT, "cannot be seated → the placement had to change"), not from corpus evidence; the structure is the model's memory, work log and context extension and grows with use; a missing word is supplied by the model; "could not be seated and changed the placement" counts as a structural detection |

### 1.2 Earlier decisions that bind this design

| Decision | Content | Effect here |
|---|---|---|
| 原則 | 「立体十字構造体において初期配置と規則が大切です。」 | The empty start is the initial placement + the rules, nothing else (§3.1) |
| 最終目標 | 「初期配置からそこにデータを重ねることで成長するもの学習不要で初期の薄い文法層や語彙でも問題なく入れた質問に対して回答が生成できること」 | The memory grows by stacking the model's sentences; no weight is fitted (§7) |
| D-1, OP-G1-4, OP-G1-9 | Data unit at the centre; の に で と を が fixed on ring 1; 腕＝関係の札; foundation seats fixed | Unchanged; every memory cross is a seated prose cross of the loom |
| G1-b key (n, p, a) | `placement.seated_key`, `foundation.a_num` | The key of a memory cross is computed against the memory's own history (§3.3 (b)) |
| D-5 (G4) / the fold | A seated unit never moves in the frozen stack; `build(1..k+1) == extend(build(1..k), k+1)` | A committed memory weave is never changed (L-MEM-05); a session is one stacked document (§4.5) |
| N-16 / N-17 / M-3 (a) | 「毎回、別の空間として読み」; memory holds 「問いと採用した答え」「利用者の文」「探索の状態」; the search state is stored and shown, not used to answer | The memory is a separate space; the ledger (the ops = 探索の状態) is the work log, shown, never an answer source; only the woven sentences are (§4.4) |
| L-547 | Records/adhesion read BASE sentences only | OP-MEM-1 |
| Loom §3, §4, L-LOOM-09, L-LOOM-14 | Ops, refusals, one chained ledger per run, no undo | A memory session is a loom run with a few more ops (§4.1) |
| LOOM-notes | Three layers never mixed: prevention (refusals) / notes (non-blocking) / noticing (ledger) | Memory notes never block (L-MEM-09); the self-question is a note (OP-MEM-2) |
| weave_span.v2 (L-LOOM-130..146) | A stretch of a sentence becomes a chain of crosses whose read-out is the stretch; one arm unit per cross | The write op (§4.2). Its expressive limit is OP-MEM-3's cause |
| Evidence gate (LOOM-evidence, wt/line3-loom-ev, evidence.v2 uncommitted) | `judge_quote(corpus, qu, scope, sid, tier, i0, i1, version)`, a pure function | Reused unchanged as recall (§4.3) and in the answer run (§6) |
| §11 three loops | audit / growth onto the frozen stack (PASS rule L-LOOM-20; constructed → 「、」 L-LOOM-21) / self-modification with frozen rules | Memory content never enters a base corpus except through loop 2's grading (§7) |

### 1.3 Tensions, raised rather than smoothed over

1. **「データがなくてもわかる」 vs what can be detected.** No rule can find a content contradiction in ONE statement. Every content detection below needs at least
   two statements of the model; what the empty start removes is the CORPUS, not the data. The data is the model's own history, and it starts at zero. With zero
   history only the shape rules fire (§3.4). This is a property of contradiction, not of the design.
2. **The existing CONFLICT points the wrong way for memory** (O, §2). 「X の Y は A」 weaves to [Y topic, X on の] + [A]; CONFLICT keys on the centre Y, so it
   compares X's (an enumeration: 認証の期限 / 決済の期限) and never compares A's (the actual claim). OP-MEM-2.
3. **The weave rule seats one arm unit per cross** (L-LOOM-131), although the cross has six arms. 「東京で会議を開く」 needs 開く with で:東京 and を:会議 in one cross;
   weave_span refuses it (`nested_particle_chain`). The memory therefore speaks a narrow dialect: 「X の Y は A」 and short chains. Not changed here (no new rules);
   measured as cost (OP-MEM-3, P-MEM-4).
4. **The key from the model's own history mostly says "new relation", not "contradiction"** (O, §2 Pr6). The `a` term flags a legitimate 東京の天気 after 東京で…
   twice. Only the (n, p) part (word order of a pair already written) points at a contradiction (REVERSAL). §3.3 (b) keeps the two apart.
5. **The foundation is Japanese.** English sentences have no particle gaps, so every word is a one-unit cross and no arm is ever filled. Prose memory is Japanese
   (L-MEM-20); code memory goes through the code loom.
6. **Identifiers lose `_` and `.` in a prose read-out** (O: fmt_num → fmtnum, ops.py → opspy; L-LOOM-144: the loom writes letters only). Two identifiers that
   differ only in punctuation are one memory word. Code facts belong in code memory (§4.6); prose memory warns (L-MEM-19).

---

## 2. Facts measured for this design (O)

| Probe | Result |
|---|---|
| Pr1 empty start | `Corpus(b"")` builds: N = 0, 0 units in RUN / WORD / CHAR. The first write's crosses are `trivially_stable` (key (0, 0, 0)) |
| Pr2 adhesion on memory text | 4 sentences with `kind = memory_answer`: adhesion `counts {}` in RUN and WORD (L-547: `foundation.base_items`). The same sentences with `kind = base`: `{(会議,は):1, (会議,を):1, (担当,は):1, (期限,は):1, (東京,で):2, (田中,の):1, (認証,の):1}` |
| Pr3 weave + notes (`weave_span.v2`, WORD, whole sentence) | 「田中の担当は認証」 → c1 = [担当 topic, 田中 on +x(の)], c2 = [認証]. 9 sentences: **CONFLICT never fires on 田中の担当 認証 vs 決済** nor on 認証の期限 金曜 vs 月曜; it fires 3 times, all enumerations: 期限 ← {認証, 決済}, 前提 ← {認証, 決済}, 支店 ← {東京, 大阪}. Repeating 田中の担当 → `stable` (1, 1, 377) against the history. **「認証の前提は決済」 then 「決済の前提は認証」 → `unstable`, key (1, 0, 233), the improving swap `centre ↔ +x:0`** (the history orders the pair the other way) |
| Pr4 recall = the gate over the memory (scope `clause`, evidence.v2, units i0..i1 with i1 − i0 ≤ 2, 8 sentences) | 田中の担当は何ですか → {認証 (s0), 決済 (s2)}; サーバーのポートは何ですか → {8080 (s5), 9090 (s7)}; 認証の期限は何ですか → {金曜} only; 決済の期限は何ですか → {月曜} only; 鈴木の担当は何ですか → none; 会議はどこで開きますか → none (`no_slot_head`: 開き vs 開く, plus `wrong_arm`/`no_subject` elsewhere). 6 questions in 0.01 s. Identical with `kind = memory_answer` |
| Pr5 weavability of 25 work-log sentences | 17 / 25 weave whole. 5 `nested_particle_chain` (「totalはaddでリストを合計する」「fmt.pyにaddのimportを追加した」「Airでテストを実行する」「東京で会議を開く」「佐藤が予算を決めた」), 3 `gap_is_not_a_particle` (つの, より, は副). Of the 17, 12 are 「X の Y は A」 |
| Pr6 the key's `a` from history | History 「会議は東京で行う」「研修は東京で行う」, new 「東京の天気は晴れ」: the 天気 cross is `unstable` under `strict_npa` (key (0, 0, 0), best (0, 0, 110) moving 東京 from +x(の) to +y(で)) and `stable` under `strict_np` |
| Pr7 can the gate read the model's own clause? (self-question 「[X の] Y は何ですか」 against the sentence it came from, 13 sentences) | 10 / 13 yield a passing answer. Unreadable: 「fmt_numの戻り値は文字列」 (the identifier is cut into fmt / num), 「次の手順は計測」, 「締め切りは金曜」 (no X: subject-less, refused by evidence.v2). **One sentence can pass several nested stretches**: 「今日の作業はK3の修正」 → {K3, K3の修正}; 「K3の原因はimportの欠落」 → {import, importの欠落}. An enumeration loses items: 「mulの引数はaとb」 → {a} only |

---

## 3. The empty start (item 1)

### 3.1 What M₀ is

```
M₀ = ( F,  R,  H = (),  ledger = () )
  F  the foundation: foundation.DEFAULT_SPEC (P7, LADDER, WEIGHTS, FIB_DEN; seats_sha), the tokenisers incl. UniDic (part of the initial
     placement by OP-G4-5), the code loom's gates (parse, definition-first, builtins list, stdlib list)
  R  the rules that already exist: the seating rules (loom §3.2), weave_span.v2, the read rule, the key (n, p, a) and stability_of,
     the notes (CONFLICT prose/code, UNANCHORED), the evidence gate judge_quote, the frozen-seat rule (D-5)
  H  the memory corpus: the model's sentences, in order; empty
```

Nothing else: no fulllead, no bank, no adhesion table, no stack. The only thing that grows is H (and the ledger that records how it grew). Every derived object
(the memory Space, its adhesion, its weights, the cumulative loom state) is a pure function of H and the ledger, rebuilt or replayed, never stored as truth.

### 3.2 The memory store (L-MEM-17)

```
<store>/                    the --store DIR (required; no default path: L-MEM-17)
  sessions/<run_id>/ops.jsonl, HEAD, timing.jsonl     one loom ledger per session (loom §6.1 rows, unchanged format)
  memory.jsonl              DERIVED: the ok `write` rows of all sessions, in order, as corpus rows {sent, source, kind}
  HEAD                      the last session's HEAD + sha256(memory.jsonl) + the session count
```

`memory.jsonl` is derived from the ledgers and re-derived by `mem verify`; the ledgers are the single source of truth. **The ledger is the work log.**

### 3.3 The rules that detect without a corpus — exact

Notation: the write of sentence t (sid t of H). `C_t` = `Corpus(bytes(H[0..t]))` (the sentence included: weave and recall read it). `C_<t` =
`Corpus(bytes(H[0..t−1]))` (the history before it: the key and UNANCHORED read it, so a sentence is never its own evidence; G4 【条件 2】). Built with
`Corpus(...)`, never `Corpus.load` (its process-wide cache would hold every prefix: L-MEM-15).

**(a) Seating rules — data-free, always on.** Unchanged loom rules: one unit per seat, foundation seats untouchable (`seat_is_foundation`), the arm is the
relation (the particle), the centre is never empty at read, legs contiguous, one tier per thread. In memory mode they fire through `weave_span`:
`span_inexpressible` with `gap_is_not_a_particle` or `nested_particle_chain` (§1.3 (3)). These are **SHAPE** events (OP-MEM-3): they say the sentence does not
fit the structure, not that it is wrong. Plus one memory rule: a committed cross is frozen (`memory_frozen`, L-MEM-05).

**(b) The key from the structure's own history.** For each cross c of the new weave, two calls of the existing `read.stability_of` with `run.corpus = C_<t`:
`e_np` (mode `strict_np`) and `e_npa` (mode `strict_npa`).
- **REVERSAL** iff `e_np.status == "unstable"`. For a weave cross (centre + at most one arm unit, L = 1 or 2) no swap can change n (the arm unit stays adjacent to
  the centre through the contraction); the only (n, p)-improving swap is centre ↔ arm unit, i.e. **the history holds this pair in the other order**. Needs the
  pair co-written at least once before (n ≥ 1). (O: Pr3.) Counted as a detection.
- **NEW_RELATION** iff `e_npa.status == "unstable"` and `e_np.status != "unstable"`: only `a` improves, i.e. a unit of the cross has adhesion in the history
  to another arm particle and none to this one. **Information, not a detection** (O: Pr6 is a legitimate sentence).
- History empty, or no unit of c in the history: `trivially_stable` — the honest "the structure has nothing to say yet".
- Under OP-MEM-1 (b), `a` = 0 and NEW_RELATION never occurs; REVERSAL is unchanged.
- Stability never blocks a write (L-MEM-09: the memory's stability mode is `report`).

"Adjacency/adhesion counts accumulate from the model's own woven sentences" is therefore exact: `C_<t`'s Space gives n and p (`placement.Weights`: sentence
co-occurrence and word order over H[0..t−1]); its `foundation.Adhesion` gives adj(v, p) (the particle that follows v, per sentence) — under OP-MEM-1 (a) only.

**(c) Typed notes.**
- **CONFLICT/arm** (existing `notes.conflicts_prose`, over the cumulative thread, reported only when a variant includes a cross of this write: L-MEM-08).
  Meaning in memory: "this head has had different modifiers on the same relation" — mostly enumerations (O: Pr3). **A note, not counted** (OP-MEM-2 (a)).
- **CONFLICT/same_question** (OP-MEM-2 (a), §4.3): "the memory now answers the same question in two ways". Counted.
- **CONFLICT/code** (existing `notes.conflicts_code`, over the cumulative code of the code memory, §4.6): one name, two different definitions in one scope.
  Counted (a bug candidate).
- NO_RECORD and QUESTION_ECHO do not apply in a memory session (no lookup-before-add, no task question): the memory notes profile `mem.v1` =
  {CONFLICT, UNANCHORED, REVERSAL, NEW_RELATION, SAME_QUESTION, SHAPE} (L-MEM-08). The loom's own `notes.v2` is unchanged for ordinary runs.

**(d) "Cannot be seated → the placement changed" — exact.** Two event kinds, both read from the session ledger only:
- **UNSEATABLE**: a `write` row refused with `span_inexpressible` (reason recorded). Nothing is stored (OP-MEM-3 (a)).
- **RESEAT**: a `write` that is refused (UNSEATABLE) or noted (any counted note on its result) and is followed, within the next 3 model ops of the same session
  (L-MEM-07), by an ok `write` whose WORD unit multiset overlaps the first in at least one unit of 2+ characters. A RESEAT is **content** iff the trigger was a
  counted note (SAME_QUESTION, REVERSAL, CONFLICT/code) and the second write changes the answer unit set of that question (or the pair order); otherwise
  **shape**. Under OP-MEM-3 (a) only content RESEATs are counted as structural detections; shape RESEATs are the cost column. The case "a seat already taken by a
  different unit under the same relation" does not exist as a refusal: every weave makes new crosses, so "taken" is exactly CONFLICT (a note, never a block:
  blocking would teach the model to rephrase around the contradiction and hide it — §8, rejected).

**(e) UNANCHORED, re-read against the history.** The existing definition with `run.corpus = C_<t`: a unit on arm p with adj(anchor, p) = 0 and adj(anchor, q)
≥ 2 for some q ≠ p. In memory it is the note form of NEW_RELATION with a floor of two sentences: **information, not counted**. Never fires under OP-MEM-1 (b).

### 3.4 What fires at 0, 10, 100, 1000 seated units

A 「X の Y は A」 clause seats 3 WORD units (O: Pr3), so 10 / 100 / 1000 units ≈ 3 / 33 / 330 sentences. Cells without (O) are predictions (P-MEM-n, §5.4).

| Rule | 0 units (M₀) | 10 | 100 | 1000 |
|---|---|---|---|---|
| (a) shape: span_inexpressible | **fires** (no data needed) at the model's writing rate (O: 8/25) | same | same | same; falls as the model learns the dialect |
| (a) memory_frozen, seat rules | fire on misuse | same | same | same |
| (b) REVERSAL | never (empty history) | fires on a pair co-written once before in the other order (O: Pr3) | same | same; false alarms when one pair legitimately appears in two relations (predicted rare: the check is cross-local) |
| (b) NEW_RELATION | never | rare (needs adj ≥ 1 of the unit) | frequent (O: Pr6 after 2 sentences) | most writes of frequent words (prediction) — why it is not counted |
| (c) CONFLICT/arm | within one write only | fires on shared heads (O: 3 in 9 sentences) | many | dominated by enumerations (prediction) — why it is not counted |
| (c) CONFLICT/same_question | never | **fires on the second contradicting 「X の Y は」 clause** (O: 2/2 in Pr4) | same; also on legitimate updates (no retraction: L-MEM-13) | same; recall cost grows with H (linear; Pr4 0.01 s at 8 sentences) |
| (c) CONFLICT/code, definition-first, parse gate | **fire on the model's own code with an empty fixture** (data-free gates) | across sessions once code is carried (§4.6) | same | same |
| (e) UNANCHORED | never | never (needs adj ≥ 2 elsewhere) | occasional | frequent (prediction) |
| recall verdict | always NONE = the correct "not in memory" | ANSWER / CHOICE / NONE | same | same |

---

## 4. The model's use: memory, work log, context extension (item 2)

### 4.1 Two kinds of run over one store

1. **Memory session** (`lang: prose`, `mode: memory`, new): the model writes and reads back. It never emits; it closes with `commit`. One session = one loom run =
   one ledger. Its `begin` row records `{store_head_before, memory_sha_before, sessions_before, evidence_version, notes_profile: "mem.v1", caps: "mem.v1",
   kind_policy: OP-MEM-1 answer}` (L-MEM-18).
2. **Answer run** = an ordinary loom run whose task `corpus` is a **memory snapshot** file `<store>/snapshots/memory_<sha12>.jsonl` (written by `mem snapshot`,
   named by its sha; the run's header already pins `corpus_sha`). Output only through `weave_span` + `emit` + the evidence gate (§6). This is how a later session
   answers "from memory" under the 織機 enforcement.

### 4.2 Memory-session operations (the MCP tools; every call one ledger row)

| tool | args | ok result | refusals |
|---|---|---|---|
| `mem_begin` | `store, model` | `{run_id, sessions_before, sentences_before, rules}` | `store_locked`, `store_unverified` (the store's HEAD does not verify) |
| `write` | `run_id, text (1..64 chars), role: model\|user` | `{sid, source, crosses (as weave_span returns them), units: [{uid, surface, origin: record\|new, history_n}], notes: [...]}` | `bad_sentence` (L-MEM-03), `secret_shaped_sentence`, `no_unit`, `span_inexpressible` (+ reason), `write_cap` |
| `recall` | `run_id, question (≤ 64 chars)` | `{verdict: ANSWER\|CHOICE\|NONE, answers: [{text, occurrences: [{sid, source, clause}]}], codes: {code: count} (NONE only), question: <evidence.question_units view>}` | `recall_cap` |
| `lookup` / `read_sentence` | as the loom, over `C_t` (memory sids) | as the loom | as the loom |
| `status` | `run_id` | session counters, store totals, the notes of this session so far | — |
| `commit` | `run_id` | `{memory_sha, store_head}`; the session is closed; memory.jsonl and the store HEAD are re-derived | `run_closed` |

`unseat`, `swap`, `drop`, `topic`, `extend`, `link`, `unlink` on a committed memory cross (any cross a `write` made, this session or earlier) →
**`memory_frozen`** (L-MEM-05). `add`/`open_cross`/`seat` are not tools of a memory session (the only way in is `write`).

**`write`, exact** (all checks before anything changes; a refused write stores nothing in H, only its ledger row — the row keeps the text, ≤ 64 chars, because
RESEAT is read from it; a secret-shaped text is stored redacted + sha as in loom §5.1):
1. NFC; 1..64 characters; no newline / NUL / control (`bad_sentence`); `ledger_events.redact` finds nothing (`secret_shaped_sentence`).
2. `row = {sent: text, source: "mem:<store_id>/<session_no>#<i>" + (":user" if role user), kind: base | memory_answer (OP-MEM-1)}`. `C_t` = C over H + row.
3. The WORD units of the row (`C_t.tier("WORD").sentence_units[t]`); none → `no_unit`.
4. `weave_span.v2(sid = t, tier = WORD, from = 0, to = last)` on the cumulative state (L-MEM-04: always the whole sentence, always WORD — the tier the gate reads,
   L-541/549). A refusal → the write is refused with the same reason; H is unchanged.
5. Commit: H gains the row; the crosses are linked at the end of the cumulative thread and frozen.
6. Provenance per unit: `history_n` = postings of the surface in `C_<t`; `origin = new` iff `history_n == 0` (the model supplied a word the structure lacked —
   the owner's 「語がないときなどはモデルが補って」), else `record` (earlier structure content). Unit `kind` stays `record` (it is a unit of the memory corpus);
   `origin` is an extra field of `prov` (L-MEM-16).
7. Notes (`mem.v1`, never blocking): REVERSAL / NEW_RELATION per new cross (§3.3 b), UNANCHORED (§3.3 e), CONFLICT/arm touching a new cross, SAME_QUESTION (§4.3),
   in the loom's note order. They go in the result and in a `loom_note` row after the write row (the existing note-row mechanism, `NOTE_AFTER_OPS` + `write`).

### 4.3 `recall(question)` — Vera's reader on the memory

1. `qu = evidence.question_units(question)` (the reader's question cut: `grammar.read_question`, subject runs, Y forms, slot).
2. Candidates: every WORD stretch (sid, i0, i1) of `C_t` with i1 − i0 ≤ 3 (L-MEM-11), in sentences that hold at least one WORD unit of a Y form or of the slot
   head (an exact prefilter: E-4p / E-5s fail on every other sentence), sid ascending.
3. `evidence.judge_quote(C_t, qu, scope = "clause", sid, "WORD", i0, i1, version = the session's evidence_version)`; pass = no code.
4. Per sentence, its **answer set** = the `norm`s of its MAXIMAL passing stretches (a passing stretch contained in another passing stretch of the same sentence
   is dropped; `norm` = NFKC + casefold + `evidence.strip_ignore`). One sentence often passes nested stretches (O: Pr7, {K3, K3の修正}): they are ONE statement,
   never a contradiction, and only K3の修正 is kept. (With all stretches kept, 「K3の修正」 and 「K3のテスト」 would agree through K3 and the contradiction
   would be hidden; with maximal ones, 「K3」 and 「K3の修正」 from two sentences are a CHOICE — a refinement is shown, never hidden.) Two sentences **agree** iff their answer sets intersect; the
   sentences with a non-empty set are grouped into the connected components of "agree" (union-find in sid order: deterministic). **NONE** (no sentence passes;
   the code histogram is returned, as `no_evidence` does), **ANSWER** (one component; every sentence listed with its answers, longest first), **CHOICE** (≥ 2
   components, all listed with sid and source, in sid order; never ranked: a tie abstains).
5. **SAME_QUESTION (OP-MEM-2 (a))**: after a write whose weave contains a topic cross T immediately followed (in the same weave) by a cross N, where T holds no arm
   unit other than on +x (の), the self-question is the sentence's own text from the start of T's の-arm unit (or of T's centre) to the end of T's は, plus
   「何ですか」 (L-MEM-10; the literal substring keeps punctuation). recall over `C_t`; if the verdict is CHOICE and sentence t is one of the occurrences →
   note `SAME_QUESTION {question, variants: [{answers, occurrences}]}` (one variant per component). If sentence t's own answer set is empty (the gate cannot read the model's own clause: Pr7, e.g.
   the subject-less 「締め切りは金曜」 under evidence.v2) → note `SELF_QUESTION_UNREADABLE` (a coverage count, never a detection).

The full line-3 ask cycle (three ratios over placed crosses) is not used in v1: on a space of a few dozen sentences its counts are degenerate, and the gate is
the reader's 「質問単位との一致」 itself (L-MEM-12). The memory stack (§4.5) keeps the door open for it.

### 4.4 What is stored, and what each thing is

| Thing | Stored | Kind |
|---|---|---|
| The foundation | constant + seats_sha | **foundation** (the initial author) |
| A memory sentence | verbatim in the write row and in memory.jsonl | **testimony** of the declared model (or of the user, relayed: `role user`); never "true", only "said at session s" |
| A unit with `history_n > 0` | as a corpus unit | **record** of earlier structure content (the record is that it was said, not that it holds) |
| A unit with `history_n == 0` | as a corpus unit, `origin: new` | **constructed** by the model at that write (the model supplied the word) |
| Op hashes, state_sha, the replay, notes rows | the ledger | **record** |
| The model's free text, transcripts | never; sha256 + length only (loom §7.2) | — |
| recall questions, lookup strings | verbatim in the ledger (≤ 64 chars) | queries; never output |
| Code (code memory, §4.6) | the emitted, verified text, appended to the carried fixture | as code loom; file shas in the index |

### 4.5 The frozen stack: one session = one document

- Seats never move: committed crosses are frozen (L-MEM-05), H is append-only, no undo (L-LOOM-09), no retraction (L-MEM-13).
- The fold: `state(1..k+1) = session_{k+1}(state(1..k))`. A session's `begin` names the store HEAD it started from; `mem replay` re-executes every session in
  order against an empty M₀ and must reproduce every row byte for byte (the loom replay, run in a chain). T-MEM-10 checks fold == one pass for k ∈ {1, 2, 3}.
- **The memory stack view** (MEM-f, optional): `stack.build` over H grouped by session as documents (foundation on), giving the per-seed crosses, `opened /
  grown / closed / left_after` per session, and the read view for the line-3 reader. A closed cross's `left_after` is the stack's own "cannot seat" (capacity),
  reported beside UNSEATABLE but not counted. It is derived and rebuildable; nothing reads it as truth.

### 4.6 Code memory

Code memory = the code loom with a **carried fixture**: session k's fixture = session k−1's fixture + every emitted, test-attested code text of session k−1,
appended to its target file (the harness already does this in a temp copy for the tests step, loom §9.4). The CODE record index is rebuilt from it, so earlier
sessions' definitions are records (`context_names`, the top names of the target file). The gates that need no data fire on the model's own code: parse,
definition-first (`undefined_name`), imports, and CONFLICT/code across sessions (a `def double` of session 2 against session 1's). Nothing new is defined.

### 4.7 Growth: 「成長するごとにveraも成長する」

After sessions 1..k, a fixed question set Q (written before the sessions, held-out). Per k and q, one cell:

| | correct | miss / rejectable | confident wrong |
|---|---|---|---|
| **present** (the answer was written in an earlier session, not in the current context) | ANSWER with the gold | NONE; CHOICE without the gold | ANSWER without the gold |
| **contested** (two values were written) | CHOICE holding both | NONE; ANSWER with one of them | ANSWER with a third value |
| **absent** (never written) | NONE | CHOICE (false presence) | ANSWER |

The headline is the three "correct" cells (present-correct, contested-correct, absent-correct). Beside: |H|, distinct units, events per session (REVERSAL,
SAME_QUESTION, UNSEATABLE, RESEAT content / shape, NEW_RELATION, CONFLICT/arm), recall time. The G4 events per q across k: **現れる** (first k with
present-correct), **残る**, **壊れる** = a later write turns present-correct into CHOICE (a contradiction or an update; reported with the writes that caused it).

---

## 5. The detection meter (item 3)

### 5.1 Tasks (gold lists by codex, held-out; the model never sees them)

| id | task | sessions | planted |
|---|---|---|---|
| **F** fact story | A project told turn by turn (owner messages): who owns what, deadlines, ports, decisions. 36 facts over 3 sessions | 3 (fresh context each) | 6 contradictions (3 within a session, 3 across), 2 reversals (「AのBはC」 then 「CのBはA」), 4 enumeration traps (same Y, different X: not contradictions), 3 explicit updates (「変更:」 — legitimate, scored as contested) |
| **C** code | fixture_repo `calc`: session 1 K1 + K4 (double, square, cube); session 2 (fresh context) four tasks that use session-1 names | 2 | 1 redefinition (`double` asked again with another body), 1 use-before-definition opportunity, 1 call with a wrong arity |
| **X** context extension | the F story's sessions 1–2, then session 3 = 18 questions only: 10 present, 3 contested, 5 absent | 3 | — |

### 5.2 Arms (the same model, the same turns, the same `report` tool)

| arm | what the model has |
|---|---|
| **A0** context only | the turns of the current session; no store |
| **A1** plain log | `log_append(text)` / `log_read(grep)` on an append-only text file (no structure, no notes) |
| **A2b** structure, blind | the memory tools; notes are logged but NOT returned to the model (measures the structure alone) |
| **A2** structure | the memory tools with notes; session 3 of X answers through answer runs (§4.1 (2)) |

Every arm ends every turn with `report(contradictions: [[turn_i, turn_j], …], bugs: [...])`: a closed format, so "noticed" is mechanical (no judge model).

### 5.3 Measures

- **(i) Contradictions the structure found that the model had not noticed**: gold pairs with a counted structural event in A2b (SAME_QUESTION, REVERSAL, content
  RESEAT) and absent from every A2b `report` up to and including that turn. Precision: counted events that match no gold pair (enumeration traps, updates are
  scored apart).
- **(ii) Bugs found** (C): definition-first refusals, parse errors, CONFLICT/code, per planted bug, before the tests; and the tests' attest.
- **(iii) Context extension** (X): the §4.7 table at session 3, per arm (A0 must answer from nothing: absent-correct is its only possible correct cell).
- Cost: UNSEATABLE / shape RESEAT per write, ops per fact, recall calls, wall time; SELF_QUESTION_UNREADABLE (coverage of OP-MEM-2).
- **Rule to count**: the structure counts as detecting only if A2's final `report` recall of planted contradictions **beats A1's** (strictly, on F, with
  false alarms reported beside), and A2b's structural recall beats A1's model-only recall.

### 5.4 Predictions (written now, before anything runs; a failed one is reported as failed)

- P-MEM-1: with H empty, no counted event fires on any write; recall returns NONE on every question (certain by construction; checked).
- P-MEM-2 (F, A2b): SAME_QUESTION finds ≥ 5 / 6 planted contradictions when both statements were written as 「X の Y は A」; ≤ 3 / 6 if the model writes them in
  other shapes. CONFLICT/arm (not counted) fires on ≥ 3 / 4 enumeration traps. REVERSAL finds 2 / 2 planted reversals with ≤ 1 false alarm over the story.
- P-MEM-3 (F): A1 finds ≤ 3 / 6 during the story (only when it greps), A0 ≤ 4 / 6 within a session and 0 / 3 across sessions; A2 ≥ 5 / 6.
- P-MEM-4: 25–40 % of the model's first-try writes are UNSEATABLE (Pr5: 8 / 25); after its first 10 refusals the rate halves (the model learns the dialect).
- P-MEM-5 (X): present-correct A2 ≥ 7 / 10, **A1 ≥ A2 − 1** (grep is a strong baseline; the structure's edge is elsewhere); contested-correct A2 ≥ 2 / 3, A1 ≤ 1 / 3;
  absent-correct A2 5 / 5, A1 ≥ 3 / 5, A0 ≥ 4 / 5 with 0 present-correct.
- P-MEM-6: NEW_RELATION fires on ≥ 30 % of the crosses whose arm unit has history by the end of F (why it is information only).
- P-MEM-7 (C): CONFLICT/code on the redefinition 1 / 1; `undefined_name` on the use-before-definition 1 / 1; the arity bug is caught by the tests only (no gate
  checks arity) in all arms.

The decisions that would follow are named now: if P-MEM-2 fails because the model avoids the 「X の Y は A」 shape, the weave rule's one-arm limit (§1.3 (3)) is
the bottleneck and the owner is asked whether a multi-arm weave (a new rule) may be designed; if P-MEM-5 shows A1 ≥ A2 on every cell, the structure is not a
better context extension than a log, only a better contradiction finder, and that is what is reported.

---

## 6. The evidence gate in memory mode (item 4)

**The same code, parameterised; no variant.** `judge_quote(corpus, qu, scope, sid, tier, i0, i1, version)` is already a pure function of its corpus:
- corpus = the memory snapshot (`C_t` in a memory session; the snapshot file in an answer run, pinned by `corpus_sha`);
- scope = `clause` always (L-MEM-12): a memory sentence has no article title (`source` minus `#i` would be `mem:<store>/<session>`, which no subject reads in);
- version = the evidence version recorded at `mem_begin` / `begin`.

"The answer must come from a clause the model itself wove earlier, with the subject and the slot" then holds by construction: under OP-MEM-3 (a) every memory
sentence was woven whole at its write, and the gate's quote rule (`not_quoted`: an unchanged weave_span cross) makes the answer run quote it. Under OP-MEM-3 (c)
(partially seated sentences) it would NOT hold, and the gate would need one more parameter (`woven_spans`: the answer stretch must lie inside a stretch that was
woven at write) — the only case in which a variant is needed.

Dependency: MEM-c and MEM-d need the evidence gate merged into line3 (it lives uncommitted in `wt/line3-loom-ev` at the time of writing).

---

## 7. What is NOT built (item 5)

- No learning, no fitted number, no weight; no new rule beyond those named in §3.1 R. The two new readings — the self-question (OP-MEM-2) and the event
  classification (REVERSAL / NEW_RELATION / RESEAT) — combine existing functions; they define no new seating or scoring.
- No change to `verantyx/line3/*`, `foundation.py`, `placement.py`, `space.KINDS` (L-40 closed), `notes.v2`, `weave_span.v2`, the evidence gate or the loop-3
  frozen list.
- No retraction / supersession (L-MEM-13), no blocking note, no multi-arm weave, no cross-of-crosses, no English prose memory, no RUN/CHAR memory weaves.
- Memory content never becomes a record of a base corpus. Loop 2 (loom §11.2) stays the only door: a memory sentence enters a stacked base corpus only through a
  PASS (human grade + no attest mismatch, L-LOOM-20), and `origin: new` units are replaced by 「、」 like constructed units (L-LOOM-21). Constructed units never
  become records any other way.
- No integration with the recorder (`.vera/ledger`, untouched) or with the Vera session layer (call-me-vera); the memory ledger is the loom ledger.
- No windows in v1 (the loom's observation window can replay a memory session as it is; a memory viewer is MEM-h, later).

---

## 8. Rejected options (kept for the record)

- **Blocking CONFLICT** ("the seat is taken"): the model would rephrase until the block is gone, and the contradiction would be stored in a shape the structure no
  longer compares. A note keeps it visible.
- **Latest wins**: order would make a winner (§0).
- **Stability against H including the new sentence**: every sentence would confirm itself (【条件 2】).
- **Counting CONFLICT/arm**: Pr3 shows its hits are enumerations.
- **The ask cycle as recall**: degenerate counts on a small space; the gate is the reader's own agreement (§4.3).

---

## 9. Tickets, decisions, tests

### 9.1 Tickets (implementation Sonnet, review Opus, held-out tests and gold codex)

| ticket | depends | content | acceptance | effort |
|---|---|---|---|---|
| **MEM-a store + session + write** | — | `verantyx/loom/memory.py`: store layout, `mem_begin` / `write` / `status` / `commit`, `memory_frozen`, caps profile `mem.v1`, the begin header, derived memory.jsonl + store HEAD, `mem replay` / `mem verify` (chained loom replay), the `mem:` guards; OP-MEM-1 and OP-MEM-3 as switches | T-MEM-01…12 | 2 d |
| **MEM-b history key + notes** | a | `C_<t`, REVERSAL / NEW_RELATION, UNANCHORED on history, CONFLICT/arm filtered to the write, unit `origin` / `history_n`, notes profile `mem.v1`, the RESEAT / UNSEATABLE counters (from the ledger, like `notes.self_corrections`) | T-MEM-13…19 | 1 d |
| **MEM-c recall + SAME_QUESTION** | b, evidence gate merged | `recall`, the prefilter, the verdicts, the self-question, SELF_QUESTION_UNREADABLE; OP-MEM-2 as a switch | T-MEM-20…25 | 1.5 d |
| **MEM-d answer run + MCP + agents** | c | `mem snapshot`; answer runs with scope clause; the `vera-loom` server gains the memory tools (`--store`); `.claude/agents/mem-writer.md` (A2/A2b), `mem-log.md` (A1, log tools only), `mem-plain.md` (A0); the A1 log tools (a tiny append-only file tool in the harness) | T-MEM-26…30 | 1.5 d |
| **MEM-e code memory** | d | the carried fixture per session; CONFLICT/code and definition-first across sessions | T-MEM-31…33 | 1.5 d |
| **MEM-g meter** | d, e | tasks F / C / X (codex: turns, gold pairs, questions), `experiments/line3/mem/harness.py`, `score.py`, the four arms, the §5.3 tables; the operator runs it; predictions marked held / failed | the §5 tables | 2 d + runs |
| MEM-f memory stack view | a | `stack.build` over sessions; the read view; left_after beside UNSEATABLE | T-MEM-34 | 1 d (optional) |
| MEM-h memory viewer | g | the observation window over a store | — | 1 d (later) |

Order: a → b → c → d → (e, f) → g → h. Total ≈ 9.5 d + runs (+ 2 d optional).

### 9.2 Local decisions (L-MEM-nn)

| id | decision |
|---|---|
| L-MEM-01 | The memory is its own corpus/space (N-16); a store holds one memory; two stores never merge |
| L-MEM-02 | Guards: a memory space refuses a row whose `source` does not start with `mem:`; the loom refuses a non-memory corpus that holds a `mem:` row (`memory_in_base`) |
| L-MEM-03 | A memory sentence: NFC, 1..64 chars (= `ARG_STR_CAP`), no newline / NUL / control; secret-shaped → refused, stored redacted + sha |
| L-MEM-04 | `write` weaves the whole sentence, WORD tier, `weave_span.v2`; a refused weave refuses the write and stores nothing in H |
| L-MEM-05 | Every cross a `write` made is frozen: `unseat / swap / drop / topic / extend / link / unlink` on it → `memory_frozen`; `add / open_cross / seat` are not memory tools |
| L-MEM-06 | Key and UNANCHORED of write t read `C_<t`; weave and recall read `C_t`; `stability_of` is called unchanged with the history corpus |
| L-MEM-07 | REVERSAL = `strict_np` unstable; NEW_RELATION = `strict_npa` unstable and `strict_np` not; RESEAT window = the next 3 model ops of the same session; overlap = one shared WORD unit of ≥ 2 chars |
| L-MEM-08 | A write's notes = those that involve a cross of that write; notes profile `mem.v1`; `NOTE_AFTER_OPS` gains `write` for memory runs only |
| L-MEM-09 | Nothing in a memory session blocks on a note or on stability (memory stability mode `report`) |
| L-MEM-10 | The self-question: topic cross T (arms other than +x empty) followed by N in the same weave; text = the sentence substring from T's first unit to T's は + 「何ですか」 |
| L-MEM-11 | recall stretches: i1 − i0 ≤ 3, the Y/slot-head prefilter, `norm` = NFKC + casefold + strip_ignore, a sentence's answer set = its maximal passing stretches, components of "answer sets intersect" (union-find in sid order), verdicts NONE / ANSWER / CHOICE, occurrences in sid order |
| L-MEM-12 | Gate scope `clause` in every memory use; the evidence version recorded at begin; no ask cycle in v1 |
| L-MEM-13 | No retraction in v1; contested facts stay CHOICE |
| L-MEM-14 | Caps `mem.v1` per session: writes 60, recalls 60, lookups + read_sentence 60, ops 300; no cross cap across sessions (a session ≤ 60 × 4 crosses) |
| L-MEM-15 | `Corpus(...)` per write (full rebuild), never `Corpus.load` for prefixes; at most the current `C_t` and `C_<t` are kept |
| L-MEM-16 | Unit `prov` gains `history_n` and `origin: new | record`; `kind` stays `record`; display 【新:…】 for `new` |
| L-MEM-17 | Store layout §3.2; `--store` required; meter stores under `experiments/line3/mem/stores/` |
| L-MEM-18 | The memory session's `begin` row carries the store HEAD before, memory sha before, the session count, the evidence version, the profiles |
| L-MEM-19 | A write whose units differ from the sentence's letters-only form (`_`, `.`) gets the note `IDENTIFIER_FLATTENED` (information) |
| L-MEM-20 | Prose memory is Japanese; a sentence with no particle gap and ≥ 3 units is accepted but reported (`NO_RELATION_SEATED`) |
| L-MEM-21 | An answer run's corpus is a snapshot file named by its sha; it never reads a growing memory |

### 9.3 The biggest risk

**At small N the structure detects almost nothing, and at large N its notes fire on almost everything — and only one rule sits in between.** Measured:
with empty history every key is trivially stable and only shape refusals fire, which are not contradictions (Pr1, Pr5); as history grows, CONFLICT/arm,
NEW_RELATION and UNANCHORED fire on enumerations and new relations (Pr3, Pr6). The counted detection rests on SAME_QUESTION and REVERSAL, and SAME_QUESTION
covers only 「X の Y は A」 clauses (12 of the 25 ordinary sentences of Pr5 have that shape) that the evidence gate can read back (10 of 13 such clauses in Pr7;
subject-less 「Y は A」 and cut identifiers are unreadable).
If the model writes its memory in other shapes, the structure becomes a log with refusals. The meter is built to show this: SELF_QUESTION_UNREADABLE and the
shape columns are reported beside every detection count, and A1 (a plain log) is the bar the structure must clear. Second risk: the model learns to evade
(rephrases until nothing fires); A2b (notes hidden) separates what the structure finds from what the model does with it.

### 9.4 Tests (T-MEM-nn)

| id | test |
|---|---|
| 01–03 | M₀: `Corpus(b"")` N = 0; the first write's crosses are trivially stable; recall on an empty store is NONE for every question; Pr1 pinned |
| 04–06 | write: the §4.2 refusals each fire; a refused write leaves H, memory.jsonl and the state sha unchanged; the Pr5 sentences pinned (17 ok, 5 nested, 3 gap) |
| 07–09 | `memory_frozen` for every forbidden op on a committed cross; `add / open_cross / seat` are unknown tools in a memory session; the `mem:` guards both ways |
| 10–12 | fold: three sessions replayed in a chain reproduce every row byte for byte under PYTHONHASHSEED 0 / 1 / 12345; fold == one pass; a tampered memory.jsonl → `store_unverified` |
| 13–16 | the key on history: Pr3 REVERSAL (1, 0, 233) with the swap centre ↔ +x:0; repeat → stable (1, 1, 377); Pr6 NEW_RELATION and `strict_np` stable; OP-MEM-1 (b) → a = 0 and no NEW_RELATION |
| 17–19 | CONFLICT/arm only on notes touching the write; Pr3's three enumerations; UNSEATABLE / RESEAT counters on a scripted ledger (content vs shape) |
| 20–25 | recall: Pr4 and Pr7 pinned (CHOICE {認証, 決済}, {8080, 9090}; ANSWER {金曜}; NONE for 鈴木; 「今日の作業はK3の修正」 alone is ANSWER {K3の修正}, never CHOICE; with 「今日の作業はK3のテスト」 CHOICE; written twice still ANSWER; with 「今日の作業はK4の修正」 CHOICE); SAME_QUESTION on 田中の担当; no SAME_QUESTION on 認証/決済の期限; SELF_QUESTION_UNREADABLE on 「締め切りは金曜」; occurrences in sid order; OP-MEM-2 (b) switch |
| 26–30 | answer run over a snapshot: the gate with scope clause passes 「認証」 for 田中の担当 only with the quote; a snapshot sha mismatch → INPUTS; agent files' tool lists |
| 31–33 | code memory: carried fixture; CONFLICT/code on a session-2 `double`; `undefined_name` across sessions |
| 34 | memory stack view equals `stack.build` over the same documents |

---

## 10. Scope and notes

- Nothing here changes a committed byte of the line-3 reader, the loom, the evidence gate or the foundation. Memory is a new module and a new run mode.
- The three owner questions are at the top (§0.1). Every result produced before they are answered is labelled with the defaults: OP-MEM-1 (a), OP-MEM-2 (a),
  OP-MEM-3 (a).
