# LINE3_LOOM_DESIGN — 織機: the model can only output by operating Vera's structure

作成: 設計役（Opus 5.5, 2026-10-11）。Target: `wt/line3` (branch line3), base HEAD `4f38e72a` (the commit that records the owner's 「織機」 decision).
This document is design only. No product code was written. Every (O) number is from a short probe the designer ran on Pro with
`/Users/motonisihikoudai/vera-wiring/env/bin/python`, `PYTHONPATH=.`, over `experiments/line3/bank2/data/fulllead_sents.jsonl` (592 sentences).
The probe is not committed; LOOM-a re-runs it as a test (T-LOOM-03).
`vera-impl/hidden` was not opened. Implementation: Claude Sonnet. Review: Claude Opus. Held-out tests: codex (the role split in the memory notes).

---

## 0. How to read this document

| Mark | Meaning |
|---|---|
| 【オーナー】 | Only for the owner's own words, quoted verbatim |
| 【決定 x】 | A decision in `ops/decisions/2026-10-06_line3_faithful_build.md` (the numbering used there) |
| 【推奨】 | The designer's (AI) proposal. It is not the owner's design |
| 【OP-LOOM-n】 | A point that affects meaning and cannot be derived from the owner's words (§0.1). Until the owner answers, the implementation uses the recommended default and every result is labelled as made under that default |
| 【L-LOOM-nn】 | An engineering choice that does not change meaning. The designer fixed it here. The implementer records it in `docs/LINE3_LOCAL_DECISIONS.md` under a new heading `## LOOM` |
| (O) / (C) | Counted by the designer for this document / taken from another document and not re-counted here |

The usual rules apply (LINE3_DESIGN §0.2, G1, G2): a tie abstains and order never creates a winner; nothing is cut off silently; no float; the default is byte-identical across `PYTHONHASHSEED` 0 / 1 / 12345.

### 0.1 Owner questions (OP-LOOM). There are three, each with the recommended option first

| id | Question | Options (recommended first) | Blocks |
|---|---|---|---|
| **OP-LOOM-1** | Does a woven cross have to be a **stable** arrangement under Vera's own key before it can be emitted? | **(a) Strict on the full seated key (n, p, a) 【推奨】.** `emit` refuses any cross where a single swap of two data seats strictly raises `placement.seated_key`. The refusal includes every improving swap. Consequence (O): where the corpus has evidence, Vera decides both the word order and the particle. 日本 (WORD adhesion: の 2880, に 89, で 110, と 34, が 13) can only sit on the の arm next to a centre, so 「日本が勝った」 is refused while 「日本の首都」 is accepted. A unit with no evidence (any constructed unit; any record unit with no co-occurrence or adhesion in the cross) is never forced, and is marked `trivially_stable` / `no_evidence`. / (b) Strict on (n, p) only. Word order follows the corpus; the particle (arm) is the model's choice, and `a` is reported but not gated. / (c) Report only. Stability is an annotation and never a refusal. | LOOM-c (the emit gate). LOOM-a/b can be built under any option |
| **OP-LOOM-2** | What is a **unit of code**, and what is a code cross? | **(a) unit = one `tokenize` token (NAME / OP / NUMBER / STRING) 【推奨】.** A record token is looked up in a token index of a fixture repo and carries path:line:col. A cross is one logical line (statement). The loom adds the layout (indentation, newline, spacing) and marks it `layout`. No foundation and no stability gate. The gates are the parse gate, definition-first, and the tests. / (b) unit = one statement (an AST `stmt`). A record is a statement copied verbatim from the repo; a constructed unit is a new statement that parses alone. Coarser, so fewer operations, but the structure does much less (each cross holds one statement as a block). / (c) Like (a), plus a **code foundation**: six delimiter arms (`(`, `.`, `=`, `,`, `:`, `[`) on the innermost ring, read like the particles. This needs its own initial-placement design and is not designed here | LOOM-e (code). The prose loom is unaffected |
| **OP-LOOM-3** | Inside one cross, **in which order are the six arms read**? The grammar layer decides this (G2-f). The arms' particles and the ladder are fixed | **(a) Ascending ladder weight, so the heaviest particle is read last, next to the centre 【推奨】:** が(−z) → を(+z) → と(−y) → で(+y) → に(−x) → の(+x) → centre. This is G1 §3.1.3 condition 3 (「比率が大きいほど中心に近い」) applied to reading: reading ends at the centre, so the heavier the particle, the nearer the centre it is read. It keeps the の-modifier next to its head (「X が Y の Z」 instead of 「Y の X が Z」). / (b) Descending ladder (の first), the same order `grammar.read_order` uses for candidate crosses (G2 §4.2). / (c) (a), but when the task has a question slot (`grammar.read_question(...).slot`), the slot particle's arm is read first | LOOM-b (the read rule). Every other part is independent |

Each of the three addenda the coordinator relayed (強制 §7, 窓 §8, 循環 §11) is decided in this document without a new owner question.

---

## 1. Constraints, verbatim

### 1.1 The decision this design implements

| Point | 【オーナー】 verbatim |
|---|---|
| 織機 (2026-10-11) | 「ではなくaiモデルがveraの内部を操作して自分の出力したいものを出力するにはこの方法しかないというサンドボックスに入れて出力するためにveraの内部構造をいじり語を追加しながら言葉を紡ぐ、コードを紡ぐ機械にすると言うことですこれを実装して」 |
| 強制 (addendum, relayed by the coordinator) | 「サンドボックスのようなものでveraを通してveraをいじって言葉を出さないと出力できないということを強制するようなものが必要です」 |
| 循環 (addendum, relayed) | 「例えばモデルの出力でバグなどや自分の出力を監査することとvera自身をモデルが進化させてくれるような循環にすることができますか」 |
| IDE (owner's question, relayed with the coordinator's answer) | The owner asked whether a dedicated IDE is needed. The coordinator's answer, encoded here (§7.6, §8): no. The mandatory dedicated pieces are the driver (harness), the MCP server and process isolation |

The auditor's reading recorded with the decision (it is not the owner's words): the model cannot emit free text. It may only add words, seat them on crosses, rotate, read and emit. Only what is read from the structure is output. Added words are marked constructed; corpus words are records. Every operation goes to a chained ledger, and the output can be replayed from the operation sequence. Both Japanese and code (Python first) are woven.

### 1.2 Earlier decisions that bind the loom

| Decision | 【オーナー】 verbatim / content | Effect here |
|---|---|---|
| 原則 | 「立体十字構造体において初期配置と規則が大切です。」 | The loom's crosses keep the foundation (the initial placement) and Vera's key (the rule). OP-LOOM-1 asks how strictly the rule binds |
| D-1 | 「データの種を中心、助詞 6 語は最内環」 | Every prose cross: a data unit at the centre; の に で と を が fixed in the innermost ring (+x −x +y −y +z −z); は has no seat and attaches to the centre word (233/377) |
| OP-G1-4 | 「固定かつ継ぎ目」 | No loom operation touches a foundation seat. The key is computed on the contracted cross (`foundation.contract`) |
| OP-G1-9 | 「腕＝関係の札」 | Every data seat of an arm is bound to that arm's particle: the particle is read after the arm's units |
| G2-f / wiring | 「文法層の読む順」: the grammar layer decides the READ ORDER only, never the candidate set (L-552) | The grammar layer decides the arm order inside a cross (OP-LOOM-3). It never adds, removes or chooses a unit |
| T6v | 「助詞を空間から外す」 (function words are not units; `space.DEFAULT_FILTER`) | The record index is the data space with the default filter. A particle is never a record unit. It enters the output only from a foundation seat or as は |
| L-212 / I-16 | tiers are separate and never added together | One thread is one tier (§3.4). Mixing tiers is refused (`tier_mix`) |
| L-52 | a unit outside the space has weight 0 | A constructed unit contributes nothing to (n, p, a) |
| L-77 | the centre is never empty | `empty_centre` refusal |
| D-5 (G4) | a seated unit never moves in the frozen stack | Applies to the stack (§11 loop 2), not to the loom's working state. The loom freezes a thread at `emit` |
| F2 | assembled strings are display only (not selection, not scoring) | In the loom, adjacency **is** the output (it is the structure's read-out), not an extra display candidate. F2's span machinery is reused only to annotate whether a juxtaposition is attested (§3.6), and only for display |
| attest | record / testimony / mismatch (public_overlay/README.md §attest) | The declared model id is testimony. Op hashes and replay are records (§6.4). Loop 1 (§11.1) uses the same typing |

### 1.3 Tensions, raised rather than smoothed over

1. **「出力したいものを出力する」 vs 「規則が大切」.** If Vera's key binds strictly (OP-LOOM-1 (a)), the model cannot say everything it wants. If it does not bind, the loom is a template with provenance marks. OP-LOOM-1 is this tension.
2. **The owner listed rotation as a move, but a seated cross is rotation-invariant.** Its arms are told apart by their particle (`placement.verify_class_foundation`: "Rotations are the identity once the legs are told apart by their particle"), and the read rule reads by particle. A `rotate` operation would change nothing the model can see. 【L-LOOM-01】 There is no `rotate` tool. Swap, move (a swap with an empty seat) and unseat remain. This is recorded so the owner can see it.
3. **Prose has no sentence-final copula in the record index.** です has 0 postings in every tier, and である is not a unit in the filtered space (O). `record_only` prose therefore ends in nouns: 「東京は日本の首都」. This is a property of the faithful rule (T6v), not a bug (§3.5).

---

## 2. Facts measured for this design (O)

| Probe (fulllead, default filter unless stated) | Result |
|---|---|
| Distinct units | RUN 3653, WORD 3557, CHAR 1358 (with `unit_filter=None`: RUN 3935, WORD 3780) |
| 東京 / 日本 / 首都 postings | RUN 1 / 25 / **0**; WORD 7 / 49 / 4 |
| です, である, の, は | 0 in every filtered tier; は/の exist only with `unit_filter=None` (WORD 446 / 399) |
| WORD pair 日本→首都 | n = 2, p(日本 before 首都) = 2, p(首都 before 日本) = 0 |
| WORD adhesion rows (`foundation.adhesion_of_space`, numerator × adj, ladder は の に で と を が) | 日本 (0, 2880, 89, 110, 34, 0, 13); 東京 (0, 0, 0, 55, 0, 0, 0); キューバ (0, 288, 0, …); 首都 none |
| Meter units | ハッシュ RUN 1 / WORD 3, 表 RUN 2 / WORD 1; カール, マルクス 1 each in RUN and WORD; 1981年: no unit in any tier, but WORD has 1981 (2) and 年 (90); 県社 RUN 2, WORD 0 (WORD has 県 94 and 社 8); 青 RUN 1, WORD 1, CHAR 5; ネパール RUN 2, WORD 2; キューバ RUN/WORD 3, 太陽 RUN 2 / WORD 3 |
| Sentences holding 1981 | サンゴーカメラ#1 「1981年に…設立された。」 and ビースティ・ボーイズ#1 |
| MCP SDK | `import mcp` works under the env python (3.11.14; resolved from `/opt/homebrew/lib/python3.11/site-packages`) |
| `.mcp.json`, `.claude/agents/` in `wt/line3` | absent |
| API (claude-api reference, cached 2026-09-25) | Forced `tool_choice` `any`/`tool` returns **400** on Claude Opus 5.5, Sonnet 5.5 and Fable 5.1. It is accepted on Haiku 4.5. The current Haiku in the model table is `claude-haiku-4-5` (the task text's 「Haiku 5.5」 is not in the table; §6.4 records whatever the harness declares) |

---

## 3. The loom state

### 3.1 Objects

```
LoomState
  header      : run_id, task (id, text, lang prose|code, mode, caps), corpus_sha, space_sha, adhesion_sha per tier,
                seats_sha (foundation.DEFAULT_SPEC), code_index_sha (code only), loom_version, python_version, declared_model
  units       : {uid -> Unit}          uid = "u1", "u2", … in creation order (L-LOOM-02)
  crosses     : {cid -> LoomCross}     cid = "c1", "c2", … in creation order
  thread      : tuple of cid           the linked crosses, in reading order
  closed      : None | ("emitted", output_sha) | ("abstained", type) | ("abandoned", reason)
  counters    : ops, lookups, reads, emit_attempts, constructed
```

**Unit** (a side registry; cross cells hold the uid, never the surface; L-LOOM-03):

| field | record | constructed |
|---|---|---|
| `surface` | exactly a unit string of the tier's postings | the text the model gave (rules §5.1) |
| `kind` | `"record"` | `"constructed"` |
| `tier` | RUN / WORD / CHAR / CODE | `null` (it takes the tier of the cross it sits in) |
| `prov` | `{"tier", "n": len(postings), "sids": all postings}`; CODE: `{"occ": [[path, line, col], …], "files": {path: sha256}}` | `{"by": declared model id, "at": op index}` |
| `seated` | `null` or `[cid, seat]` | same |

The foundation is not a registry unit. It is the constructed token `foundation.token(p)` (`"\u0000F:" + p`) in a cell, which is exactly what `foundation.contract`, `placement.seated_key` and `placement.canon` expect. In the annotated output its provenance is `{"kind": "foundation", "seats_sha": …, "ratio": "144/377"}`. Three provenance kinds exist, and none of them can be passed off as another: **record**, **constructed** (by the model) and **foundation** (constructed by the initial author, G1 §3.1.1).

**LoomCross** = a `geometry.Cross` plus `{cid, tier, lang, topic: bool, depth: int (code), linked: bool}`. Prose crosses are always seated (D-1): at L, every arm's seat k = L−1 holds the foundation token of `DEFAULT_SPEC.arms[arm]`, and the data seats are k = 0 … L−2 (k = 0 is the outer end, `geometry.Seat`). Code crosses have no foundation (OP-LOOM-2 (a)), and their data seats are k = 0 … L−1.

| Limit | prose | code |
|---|---|---|
| L at open | 1 … 5 (L = 1 is the centre alone) | 1 … 8 |
| crosses per run | ≤ 24 | ≤ 60 |

### 3.2 Seating rules

1. **Data seats only.** A seat holding a foundation token is never a target or a source (`seat_is_foundation`). This is OP-G1-4.
2. **Empty seats only.** `seat` into an occupied seat is refused (`seat_occupied`). To replace a unit, `unseat` it first. This is deliberate: every replacement leaves two ledger rows.
3. **A unit instance sits at most once.** To use the same word twice, `add` it twice. Each instance is its own uid with the same provenance.
4. **Tier.** A record unit may only sit in a cross of its own tier (`tier_mismatch`). A constructed unit may sit in any cross. A constructed unit may sit on any **data** seat, including the centre. It is marked wherever it sits. It never sits on a foundation seat, because those are not data seats.
5. **Moves.** `swap(cid, a, b)` exchanges two data seats of one cross (`geometry.swap`); either may be empty, which makes it a move. A swap that would leave the centre empty while a leg is occupied is allowed as a working state. It is refused only at read/emit (`empty_centre`). Units move between crosses only by `unseat` + `seat`.
6. **Growth.** `extend(cid, L2)` prepends L2 − L empty outer seats to every arm (the meaning of L-65; L2 > L, within the limits). Nothing seated moves relative to the centre or to its arm. **It is loom-local code, not `placement.extend`** (L-LOOM-23): `placement.extend` ends with `placement.canon`, and on a flat without foundation tokens (every code cross) `canon` sorts the six legs by content (L-61). That would permute a code cross's arms by uid string and scramble the read-out. The loom never calls `placement.canon` on its own crosses. It hands `placement.seated_key` a flat in arm order (AXES), and the arm order of a seated prose cross is already the ladder order, so `_canon_seated` is the identity there.
7. **Contiguity (checked at read).** On every leg, the occupied data seats must be contiguous and must start at the innermost data seat (prose: k = L−2 down to some k₀; code: k = L−1 down to k₀). Otherwise the read gives `leg_gap`. Reason: the contracted edges chain outer → inner → centre (`placement._FLayout`), so a gap disconnects a unit from the centre, and its order in the read-out would rest on nothing.
8. **Frozen at emit.** After a successful `emit` or `abstain`, the run is closed. Every further model operation is `run_closed`. Harness rows (`free_text_dropped`, `grade`, `attest`) may still be appended (§6.1).

### 3.3 Linking crosses: a thread (L-LOOM-04)

- One run has **one thread**: an ordered list of crosses. `link(cid, pos)` inserts a cross at position `pos` (0 … len; omitted = end). `unlink(cid)` removes it from the thread; its units stay seated.
- A cross that holds any unit but is not linked makes `read`/`emit` refuse with **`unlinked_cross`**. An unlinked cross never disappears from the output silently. Empty unlinked crosses are listed in `status` and ignored.
- There is **no cross-of-crosses** (a seat holding a cross) in v1. Juxtaposition along the thread already covers compounds (ハッシュ + 表), relative clauses (「私が見た」 + 「映画」) and copulas. Nesting would need its own read rule and its own stability notion (the T8 bundles). The owner can ask for it later; it is out of scope here.

### 3.4 The read rule (exact)

```
read(thread) = concat(read(c) for c in thread)                      no separator for prose (Japanese)
read(c), prose = concat over the arms in ARM_ORDER (OP-LOOM-3 (a): が −z, を +z, と −y, で +y, に −x, の +x) of
                    [ the arm's data units, outer → inner (k ascending) ] + ( [particle of the arm] if the arm holds ≥ 1 unit )
                 + [ centre unit ]
                 + ( ["は"] if c.topic )
read(c), code  = "    " * c.depth
                 + spaced( [ centre unit ] + concat over the arms in AXES order (+x −x +y −y +z −z) of [ the arm's units, inner → outer ] )
                 + "\n"
```

- **Prose is head-final.** It reads toward the centre and ends on the head. The particle of an arm is read only if that arm holds a unit. は is read only if the cross is marked `topic` (op `topic`). は is the foundation's centre relation (D-1): it has no seat and is read immediately after the centre word. **Code is head-initial**: centre first, then away from it. For both languages, `seat_run(cid, arm, [uids])` fills an arm **in reading order** and always ends on the innermost data seat, so the run is contiguous (§3.2 rule 7). Prose, with n units on an arm of m = L−1 data seats: k = m−n, …, m−1 (outer → inner; the last unit lands next to the particle). Code: k = L−1, L−2, …, L−n (inner → outer). So the model writes units in the order they will be read. `seat` also accepts a bare arm (`"+x"`, no k), meaning the innermost **empty** data seat of that arm in the arm's growth direction. For prose that is the empty seat just outside the occupied block (`seat_out_of_range` when the arm is full). This saves a small model from computing k.
- **Code spacing** `spaced(tokens)` (L-LOOM-05). Tokens are joined by one space, except: no space before `)` `]` `}` `,` `:` `.`; no space after `(` `[` `{` `.`; no space between a NAME, `)` or `]` and a following `(` or `[`. Afterwards `tokenize` is run on the line, and the token strings must equal the seated surfaces in order. Otherwise the read gives `layout_changed_tokens`. This is a safety net, not expected to fire.
- Each emitted character belongs to exactly one segment of the annotation (§5.3): record, constructed, foundation or (code) layout. The loom adds no other character: no punctuation, no space in prose, no 「。」. Punctuation is not a unit in any tier (L-32). In `record_only` it therefore cannot appear. In `constructed_allowed` the model may add 「。」 as a constructed unit.

### 3.5 Worked example: 「東京は日本の首都です」

Tier: **WORD**. 首都 has no RUN posting (§2), so a RUN thread cannot hold it; one thread is one tier.

| op i | tool | args | result |
|---|---|---|---|
| 0 | begin | task `demo/tokyo`, model `claude-haiku-4-5`, mode `constructed_allowed` | run_id |
| 1–3 | add | 東京 / 日本 / 首都, kind `record`, tier WORD | u1 (n = 7), u2 (n = 49), u3 (n = 4) |
| 4 | add | です, kind `constructed` | u4 `{by: claude-haiku-4-5, at: 4}`. Under `record_only`: **refused `constructed_forbidden`** |
| 5 | open_cross | tier WORD, L 1 | c1 (centre only; the six foundation tokens sit at k = 0) |
| 6 | seat | c1, `centre`, u1 | — |
| 7 | topic | c1, true | — |
| 8 | open_cross | tier WORD, L 2 | c2 (data seats k = 0; foundation tokens at k = 1) |
| 9 | seat | c2, `+x:0`, u2 | 日本 on the の arm |
| 10 | seat | c2, `centre`, u3 | — |
| 11 | open_cross | tier WORD, L 1 | c3 |
| 12 | seat | c3, `centre`, u4 | — |
| 13–15 | link | c1 at 0, c2 at 1, c3 at 2 | thread (c1, c2, c3) |
| 16 | emit | — | `emitted` |

Read-out: c1 = 東京 + は (topic) → 「東京は」. c2 = the arms in ARM_ORDER; only +x (の) holds a unit → 日本 + の, then the centre 首都 → 「日本の首都」. c3 = 「です」. **text = 「東京は日本の首都です」**.
annotated = `東京[rec WORD n=7] は[fnd 233/377] 日本[rec WORD n=49] の[fnd +x 144/377] 首都[rec WORD n=4] です[con by claude-haiku-4-5 @4]`.

Stability (OP-LOOM-1 (a)), all values (O): c2's key is (n, p, a) = (2, 2, 2880). Swapping 日本 and 首都 gives (2, 0, ·) and is lower. Moving 日本 to an empty seat on another arm gives (2, 2, 110) at best (で) and is lower. So c2 is **stable**. c1 and c3 hold one unit each, so they are `trivially_stable`.
In `record_only`, op 4 is refused and the model can emit 「東京は日本の首都」 instead. The model could also try 日本 on the が arm: 「日本が首都」 is refused at emit under (a), with the witness `move u2 +x:0` (key a 13 → 2880).

### 3.6 Join annotations (display only, F2)

For every pair of adjacent record segments in the read-out with nothing between them (a juxtaposition, e.g. ハッシュ|表), the annotation says `join: attested [sid, start, end]` if some sentence holds the two units adjacent in that order. Adjacency is computed with `granularity.SpanIndex` spans of that tier: either touching, or separated only by characters that no tier keeps (F2 §2 step 2). Otherwise the annotation says `join: unattested`. The annotation is never a gate and never a score. A record segment followed by its arm's foundation particle gets `adhesion: k sentences` (the adhesion count of that unit and particle, from `foundation.Adhesion.adj`).

### 3.7 The emit rule

`emit` runs **every** check and returns every refusal it finds, not only the first (L-LOOM-06):

| refusal | condition |
|---|---|
| `empty_thread` | no linked cross |
| `unlinked_cross` | a cross holds a unit but is not linked (each one is listed) |
| `empty_centre` | a linked cross has a seated arm unit and no centre (L-77) |
| `leg_gap` | §3.2 rule 7 |
| `tier_mix` | the linked crosses' tiers differ |
| `constructed_forbidden` | a constructed unit is in the thread and mode is `record_only` (a second line of defence; `add` already refuses) |
| `unstable_cross` | OP-LOOM-1 (a) or (b): the cross's key strictly rises under a single data-seat swap. Swaps that touch a foundation seat, or that would empty the centre (L-77), are not moves and are skipped, exactly as in `placement.verify_class_foundation`. Payload: the key, every improving swap `[seat_a, seat_b, key_after]` in `geometry.moves_swap` order (a list, not a winner) |
| code: `parse_error` | `ast.parse` fails: payload `lineno`, `offset`, `msg` |
| code: `undefined_name` | definition-first fails (§5.2): payload `name`, `line` |
| code: `import_not_allowed`, `unsupported_construct`, `layout_changed_tokens` | §5.2, §3.4 |

If any refusal is returned, the thread is unchanged and the run continues (within the caps). If none, the output is fixed: `{status: "emitted", text, annotated, output_sha: sha256(text bytes), shares, stability}`. `shares` gives the number of characters per segment kind (record / constructed / foundation / layout), as integers.

**Abstention** is a separate closing operation: `abstain(type)` with type ∈ {`no_record` (the needed unit is not in the corpus), `cannot_weave` (records exist, but the structure refuses the arrangement), `unknown`}. A closed list; no free text.

---

## 4. The operation set (the MCP tools)

The server is named `vera-loom`. Claude Code exposes the tools as `mcp__vera-loom__<name>`. Every tool takes `run_id` (except `begin`). Several subagents may share one server process, so runs are keyed (L-LOOM-07). Every call, including refused and read-only calls, appends exactly one ledger row (§6). Results are JSON objects. A refusal is `{"ok": false, "refusal": <type>, "detail": {...}}` and never an exception.

| tool | arguments | result (ok) | refusals specific to it |
|---|---|---|---|
| `begin` | `task_id: str, model: str` (≤ 64 chars, testimony) | `{run_id, task: {text, lang, mode, tiers, caps}, rules}`. The task text comes from the task bank file the server was started with. **Gold is never in that file** | `unknown_task`, `bad_model_id` |
| `lookup` | `run_id, text: str (≤ 32 chars), tier: RUN\|WORD\|CHAR\|CODE\|any` | `{matches: [{tier, surface, n, sids (all), sentences: [{sid, source, text}] (the first 5 by sid)}]}`. Exact match on a unit surface; no substring search | `lookup_cap` |
| `read_sentence` | `run_id, sid: int` | `{sid, source, text, units: {RUN: [...], WORD: [...], CHAR: [...]}}` (the data-space units of that sentence; CODE: `path:line` → the line's tokens) | `lookup_cap` (shares the cap), `unknown_sid` |
| `add` | `run_id, text: str, kind: record\|constructed, tier: RUN\|WORD\|CHAR\|CODE` (tier is required for record and ignored for constructed) | `{uid, kind, surface, prov}` | `not_a_record` (no exact unit), `constructed_forbidden` (mode), `constructed_shadows_record` (the text is a record unit in some tier: use `kind: record`; payload: the tiers), `constructed_is_foundation` (one of P7), `bad_unit_text`, `secret_shaped_unit`, `constructed_cap` |
| `open_cross` | `run_id, tier, L: int, depth: int = 0 (code)` | `{cid, seats: [...], foundation: {arm: particle}}` | `bad_L`, `cross_cap` |
| `seat` | `run_id, cid, seat: "centre" \| "+x:0" …, uid` | `{cid, seat, uid}` | `seat_occupied`, `seat_is_foundation`, `seat_out_of_range`, `unit_already_seated`, `tier_mismatch` |
| `seat_run` | `run_id, cid, arm: "+x" …, uids: [str]` | the seats filled, in reading order | the same as `seat`, plus `arm_too_short` |
| `unseat` | `run_id, cid, seat` | `{uid}` (back in the pool) | `seat_empty`, `seat_is_foundation` |
| `swap` | `run_id, cid, seat_a, seat_b` | `{cid}` | `seat_is_foundation`, `seat_out_of_range`, `same_seat` |
| `extend` | `run_id, cid, L2` | `{cid, L}` | `bad_L` |
| `topic` | `run_id, cid, on: bool` | — | `not_prose` |
| `set_depth` | `run_id, cid, depth: 0..8` | — | `not_code` |
| `link` / `unlink` | `run_id, cid, pos?` | `{thread}` | `already_linked`, `not_linked` |
| `read` | `run_id` | `{text, annotated, refusals: [...], stability: [...]}`. This is the emit check as a dry run (nothing closes) | `read_cap` |
| `emit` | `run_id` | §3.7 | `emit_cap`, all §3.7 refusals |
| `abstain` | `run_id, type` | `{status: "abstained", type}` | `bad_type` |
| `status` | `run_id` | thread, crosses (cells as uids + surfaces), pool, counters, caps, ledger head | — |

**Caps** (L-LOOM-08). The ticket asked for a hard cap on ops per emit. It is met by a per-run cap: a run has at most one successful emit, so the per-run cap bounds the ops behind every emit attempt and behind the emitted output.

| cap | prose | code |
|---|---|---|
| state-changing ops (add … link/unlink) per run | 120 | 400 |
| lookup + read_sentence | 30 | 60 |
| read (dry run) | 20 | 40 |
| emit attempts | 5 | 8 |
| constructed units per run | 12 | 60 |
| chars per constructed unit | 8 | 40 (and exactly one token) |

When a cap is reached, further calls of that class are refused with the cap's type. `emit`, `abstain` and `status` are never capped, except `emit` by its own attempt cap. After the last emit attempt is refused, the only remaining closing operation is `abstain`. If the model stops without closing, the harness appends `abandoned` (§6.1).

There is **no undo** (L-LOOM-09). The ledger is append-only. A wrong seat is corrected by `unseat` / `swap`, a wrong unit by leaving it unseated (unseated units are never read), and a wrong cross by `unlink`. Each of these leaves its row. "Undo" would be a rewrite of state that the chain would have to explain anyway.

---

## 5. Modes, code, outputs

### 5.1 Modes (set per task, per run; the model cannot change them)

| mode | constructed units | foundation (P7 particles, は) |
|---|---|---|
| `record_only` | refused at `add` (`constructed_forbidden`) and again at emit | allowed (they are the structure, not the model's words) |
| `constructed_allowed` | allowed, marked `{by, at}`, counted in `shares.constructed` | allowed |

Prose `bad_unit_text` (L-LOOM-10): after NFC, a constructed unit is 1 … 8 characters, with no whitespace, no NUL and no control characters, and it is not empty. `constructed_shadows_record` compares the text with every tier's postings (RUN, WORD, CHAR): a word the corpus has must be added as a record, so its provenance cannot be hidden. `secret_shaped_unit`: `ledger_events.redact(text)` finds a REDACT_PATTERNS match. Then the ledger stores only the redacted text and `sha256` of the original, and the replay re-checks the stored result (the state is unchanged, so `state_sha` verifies it).

### 5.2 Code mode (OP-LOOM-2 (a))

- **Record index** (L-LOOM-11): every `*.py` file under the task's fixture root, sorted by path. Each file is tokenized with `tokenize`, keeping the token types NAME, OP, NUMBER and STRING. Each token gets an occurrence (path, line, col), and each file gets a sha256. A "sentence" of the CODE tier is one logical line (the tokens between NEWLINE tokens), so `read_sentence` and the provenance work as for prose.
- **Constructed code unit**: the text must tokenize to exactly one token of those types; otherwise `bad_unit_text`. It must not be a record surface (`constructed_shadows_record`). A new identifier the model invents is constructed: it is marked, and it must still pass definition-first.
- **Parse gate**: `ast.parse(text)` with the Python of the header (`python_version`; a replay under another version is refused with `python_mismatch`).
- **Definition-first** (L-LOOM-12): walk the AST in source order. Keep scopes: module, function (with its parameters), lambda and comprehension. A `Name` in `Load` context must be bound **earlier in the text**, in the same or an enclosing scope. Bindings come from `def` / `class` (bound at their line, so recursion works), assignment / augmented-assignment / annotated targets, `for` / `with … as` / `except … as` targets, parameters, comprehension variables, and `import` / `from … import` aliases. The other allowed sources are the pinned builtins list (`verantyx/loom/builtins_py311.txt`, generated once from `dir(builtins)` and committed) and the task's `context_names`, which are record names: the top-level names of the target file before the insertion point, from the code index. For `Attribute`, only the base name is checked. A forward reference that Python would allow (a function body naming a later module-level def) is **refused**: the rule is "definition seated earlier".
- **Imports**: `import m` / `from m import a` is allowed only if m is a module of the fixture repo (and, for `from`, a is a top-level def/class/assignment of m in the index, so it is a record) or m is on the pinned stdlib list (`math itertools functools collections re json fractions typing dataclasses operator string`). Anything else is `import_not_allowed`. `from m import *` is `unsupported_construct`.
- **`unsupported_construct`**: `global`, `nonlocal`, `del`, star-import, and calls whose function name is `eval`, `exec`, `compile`, `__import__`, `open`, `getattr`, `setattr` (L-LOOM-13).
- **Layout** is generated by the loom (`depth` per cross, spacing §3.4) and marked `layout`. The model chooses the depth through `set_depth`.
- **Tests** are not a gate of `emit`. They are run by the harness after emit (§9.4), and the result enters the ledger as an `attest` row (record: exit code).

### 5.3 Two outputs

- `text`: the raw bytes of the read-out. This is what the scorer, the tests and the user see as "the answer".
- `annotated`: a list of segments `{s, kind: record|constructed|foundation|layout, uid?, tier?, cid, seat, prov (short form), join?, adhesion?}`. Concatenating the `s` fields equals `text` (asserted, T-LOOM-10). The grading window (§8) renders `annotated`. Display marks: record plain; constructed 【構成:…】; foundation in grey. The text form for the CLI is `東京は日本の首都【構成:です】`.

---

## 6. The ledger

### 6.1 Rows (L-LOOM-14)

A separate ledger per run. `<runs_root>/<run_id>/ops.jsonl` + `HEAD` + `.lock`. The default `runs_root` is `experiments/line3/loom/runs` (the server's `--runs-dir`). The recorder's ledger (`.vera/ledger`, `ledger_events.ALL_KINDS` is closed and pinned by the installed hooks) is **not** touched. From `verantyx/ledger_events.py` the loom reuses only the pure functions: `canonical`, the GENESIS value, the TORN_TAIL rule (refuse to append to a ledger whose last line has no newline), and `redact` / `redact_obj`.

```
row = {"v": 1, "i": <int, 0-based>, "actor": "model"|"harness"|"human", "op": <closed list>,
       "args": {...}, "result": {...}, "state_sha": <sha256 of the canonical state after the op>,
       "prev": <sha of row i-1 | 64 zeros>, "sha": sha256(canonical(row without "sha"))}
```

- **There is no wall-clock time in a row** (L-LOOM-15). Time goes to `timing.jsonl` beside it, `{i, t_ns_since_begin}`, outside the chain, like the recorder's `runs/`. This is what makes "replay → identical bytes" possible. (The recorder's `sha_of` hashes `ts`, so its rows could never be reproduced.)
- Closed op list: model ops = the §4 tools. Harness ops = `abandoned`, `free_text_dropped`, `free_text_control`, `harness_meta`. Human ops = `grade`. Loop ops (§11) = `attest`, `audit_verdict`, `stacked`.
- `free_text_dropped` holds `{sha256, chars}` only, never the text (§7.2). `free_text_control` (control runs only, §9.3) holds the text, because the text is that run's output.
- `state_sha` = sha256 of canonical JSON of {units, crosses (cells as uids, topic, depth, linked), thread, closed, counters}. Dict keys are sorted. Lists keep their uid/cid order, which is a label order (L-LOOM-02).

### 6.2 Replay and verify

- `vera loom replay RUN_DIR [--out FILE]`: read row 0 (`begin`). Check that the corpus file, the space sha, the adhesion shas, the seats_sha and the code index sha are reproduced from the paths the header names; any difference is refused with the typed mismatch. Then re-execute every `actor: model` row's `(op, args)` against a fresh state and re-append the harness/human rows as recorded. Write a new `ops.jsonl`. **It must equal the original byte for byte.** The emitted `text` is printed. Exit codes: 0 identical, 1 differs (the first differing `i` and field are printed), 2 the inputs cannot be reproduced.
- `vera loom verify RUN_DIR [--head SHA]`: the chain (every `sha`, every `prev`, the HEAD file, the optional external head), then the replay. The status list follows `docs/RECORDER.md` §2: OK / EMPTY / TAMPERED / TORN_TAIL / HEAD_MISMATCH, plus **REPLAY_DIFFERS** (the chain is intact but the ops do not reproduce the results: a server bug or a forged result).
- **Determinism test** (T-LOOM-12): the scripted weaver's runs under `PYTHONHASHSEED` = 0, 1 and 12345 give byte-identical `ops.jsonl`.

### 6.3 What the ledger cannot prove (honest)

The same holes as RECORDER §2: a rewrite of the whole chain is undetected unless HEAD is pinned outside (commit `HEAD`, or pass `--head`). The ledger records that **some** client called these tools in this order. Which model it was is not proven (§6.4).

### 6.4 Model attribution

- `begin.args.model` is the model's own declaration: **testimony**.
- `harness_meta.args = {driver: "L1-subagent"|"L2-api"|"scripted", requested_model, agent_definition_sha}`, written by the harness: also **testimony** (the harness says what it asked for; in L1 the Agent tool's `model` parameter is not observable by the server).
- In L2, the API response's `model` field is stored in `harness_meta.args.response_model`. It is still testimony with respect to the ledger, but it comes from the provider.
- **Records**: the op hashes, `state_sha`, the replay, the emitted bytes. A sentence like "Haiku wove this" is always reported as testimony with these record fields beside it.

---

## 7. 強制 — enforcement: no output except through the loom

### 7.1 The four layers, and which can be built now

| layer | what it enforces | physical or procedural | buildable here now |
|---|---|---|---|
| **L1** Claude Code subagent | `.claude/agents/vera-loom-weaver.md` with `tools:` = only the `mcp__vera-loom__*` tools (no Read/Write/Edit/Bash/Grep/Glob/WebFetch/Agent). The system prompt says that the only output is `emit`/`abstain` and that free text is discarded. The parent session discards the subagent's final message | The tool allow-list is physical: the subagent cannot write a file or run a command. The discard of the final message is **procedural**: the parent model still sees the text in its own context, and only discipline (the operator writes the sha, never quotes it) keeps it from reaching the user | **Yes.** It needs `.mcp.json` + the agent files and a **session restart** (both load at session start) |
| **L2** API driver | `verantyx/loom/driver.py`: a manual tool-use loop. Its `tools` are only the loom tools plus `done`. Every `text` block in every assistant turn is dropped: its sha goes to `free_text_dropped`, and it is never appended back to the conversation as text the user sees. The episode ends on `done`, `emit`/`abstain` success, a cap, or `max_turns` (prose 60, code 200). One assistant turn may carry several `tool_use` blocks (parallel tool use); they are executed in block order, each is one ledger row, and all results go back in one user message | Physical: the driver's code is the only path from the model to anything, and it forwards only tool calls | **Designed and unit-tested with a fake client only.** No ANTHROPIC_API_KEY here (and no `ant auth` profile was checked, so the SDK is not run). See §7.3 for `tool_choice` |
| **L3** process isolation | The MCP server is a separate stdio process. Its file access is confined in code to: the corpus file(s) and the fixture root named in the task bank (read), and `runs_root/<run_id>/` (write). Every path is `resolve()`d and checked against these roots (`path_outside_sandbox`). No network module is imported (a test greps the loom package for `socket`, `urllib`, `http`, `requests`, `subprocess`). Optionally an OS profile (`sandbox-exec` on macOS: deny network, deny writes outside `runs_root`) | Code-level confinement is physical against the tools' own arguments. The OS profile adds a second wall | **Code-level: yes (LOOM-d).** OS profile: ticket LOOM-d2, tested on the Air; `sandbox-exec` is deprecated by Apple but still runs, so the ticket records whether it works there |
| **L4** emit gate | The scorer, the grading window and the growth loop read **only** the `emit` rows of a ledger whose `verify` is OK (chain + replay). Nothing else of a run (lookups, reads, statuses, free text) is ever scored or shown as output | Physical in the consumers' code: `experiments/line3/loom/score.py` calls `verify` first and refuses a run that is not OK (`run_not_verified`) | **Yes** |

**Do we need a dedicated IDE? No.** The mandatory dedicated pieces are the **driver** (L2: loom tools only, free text dropped, `tool_choice` forcing where the model allows it), the **MCP server** and the **process isolation** (L3). An existing IDE agent (Claude Code subagents) reaches **L1 only**. The human-facing windows needed are web pages (§8), not an IDE. A VS Code extension comes later, and only once code weaving is usable (§8).

### 7.2 Free text

- L1: whatever the subagent returns as its final message is recorded by the parent as `free_text_dropped {sha256, chars}` through `vera loom note RUN_DIR --free-text-file F` (the CLI hashes the file and stores no text). It is never scored or shown. The parent must not quote it to the user. This is the procedural part of L1.
- L2: every `text` block is dropped by the driver and recorded the same way. The conversation history sent back to the API keeps the model's own content blocks unchanged (the API requires the assistant turn as produced; L-LOOM-16), but no text block ever reaches the scorer or the user.
- Scripted weaver: its `say(text)` calls are recorded the same way (T-LOOM-30 checks that they score nothing).

### 7.3 `tool_choice` (from the API reference, §2)

- On **Haiku 4.5** and other models that accept it, L2 sends `tool_choice: {"type": "any"}`: every turn must be a tool call, and `done` ends the episode.
- On **Opus 5.5, Sonnet 5.5 and Fable 5.1**, forced `tool_choice` returns 400. L2 then sends `{"type": "auto"}` with `strict: true` on every tool. A turn that ends without a tool call (`stop_reason == "end_turn"`) is recorded as `free_text_dropped` and answered with a tool-less reminder. After 3 such turns the episode ends `abandoned: no_tool_call`.
- **The guarantee does not depend on `tool_choice`.** The driver forwards nothing but tool calls. `tool_choice` only removes wasted turns. The design says this explicitly so a later reader does not take `any` for the wall.

### 7.4 Residual channels (stated honestly)

| channel | bound | handling |
|---|---|---|
| constructed unit text | the **intended** channel: prose ≤ 12 units × 8 chars = 96 chars per run; code ≤ 60 tokens × 40 chars | marked in every output; counted in `shares` |
| choice and order of record units | unbounded in principle (that is the output) | it is the output, so it is visible |
| `lookup` query strings | ≤ 30 × 32 chars per run; free text the model chooses | in the ledger only; never in `text`; the windows show them as queries, never as output |
| declared model id | ≤ 64 chars | testimony; shown as such |
| op order, op timing, refused calls | a side channel to whoever reads the ledger | recorded anyway; never output |
| the subagent's final message (L1) | unbounded, and visible to the parent model | procedural discard (§7.2); L2 removes it physically |
| abstain type | closed list of 3 | — |

### 7.5 Enforcement tests

| id | test |
|---|---|
| T-LOOM-30 | A scripted weaver that only calls `say("答えは東京です")` and `done`: no `emit` row, the scorer returns `no_output`, and `free_text_dropped` holds the sha. A weaver that `say`s the gold and then emits something else: the score is that of the emitted text only |
| T-LOOM-31 | L2 driver with a fake client whose turns contain text blocks + tool calls: no text reaches the score; one `free_text_dropped` row per text block; with a fake `auto`-only model, 3 tool-less turns → `abandoned: no_tool_call` |
| T-LOOM-32 | L3: tool arguments that try `../`, absolute paths or symlinks out of the roots are refused `path_outside_sandbox`; a grep test over `verantyx/loom/` finds no network or subprocess import |
| T-LOOM-33 | L4: a run whose `ops.jsonl` is edited (one result byte) → verify `TAMPERED`, score `run_not_verified`; a run whose chain is re-hashed after editing a result → verify `REPLAY_DIFFERS` |
| T-LOOM-34 (when L1 is available) | after a subagent run, the recorder ledger's `tool_call` rows for that subagent and the loom ledger agree: zero non-loom tool calls by the subagent. Run by the operator; recorded in `experiments/line3/loom/results/` |
| T-LOOM-35 | the agent files: the `tools:` line of `vera-loom-weaver.md` parses to a set ⊆ {`mcp__vera-loom__*`}; `vera-loom-control.md` ⊆ {begin, lookup, read_sentence} |

---

## 8. 窓 — the human-facing windows (web pages, no IDE)

Built like the existing structure overview: an HTML template with a `/*__DATA__*/` slot, filled by a small Python builder from JSON (`tools/build_structure_overview.py`, `docs/LINE3_STRUCTURE_OVERVIEW.md`). Each is one self-contained file. They read verified ledgers only (L4).

| window | shows | writes |
|---|---|---|
| **(1) Grading window** `tools/loom_grade_template.html` + `tools/build_loom_grade.py --runs …` | per run: the task text; the emitted thread drawn as crosses (three.js, the same octahedron drawing as the overview: centre, six arms, seats, foundation particles in grey); `annotated` with record / constructed / foundation marks, join and adhesion annotations; every refusal the run met (type, op i); stability per cross | a grade per run: `pass` / `fail` / `unclear` + an optional note. The page cannot write files, so it **downloads `grades.jsonl`**. `vera loom grade-import grades.jsonl --grader NAME` appends `grade` rows (actor human) to each run's chain after `verify`. The grade feeds loop 2 (§11.2) |
| **(2) Observation window** `tools/loom_watch_template.html` + `tools/build_loom_watch.py RUN_DIR` | the op stream of a run replayed step by step (a slider over `i`): the state after each op from the replay, the thread's read-out at that step, lookups as queries, refusals in red | nothing. "Live" = rebuild the page from the growing ledger (`--watch` re-renders on change). Not a server |
| **(3) Code ledger viewer** (a mode of (2), `--code`) | for code runs: the lines as crosses, where the parse gate stopped (line, offset), which name failed definition-first, the import decisions, the test `attest` rows | nothing |

A VS Code extension comes later, only once code weaving is usable (the meter §9.4 passes) and only as another viewer of the same ledgers.

---

## 9. The sandbox and the harness

### 9.1 The MCP server

`vera loom mcp --tasks TASKS.jsonl --runs-dir DIR [--allow-root PATH …]`. A FastMCP stdio server, the same pattern as `verantyx/mcp_server.py` (`from mcp.server.fastmcp import FastMCP`; `@mcp.tool()` functions; `mcp.run()`), but a **separate module** `verantyx/loom/mcp.py` with its own `build()`/`serve()`. It does not import or touch the 126 tools of `vera mcp`. The task bank `experiments/line3/loom/tasks_bank2.jsonl` holds `{task_id, text, lang, mode, tiers, corpus, fixture?, context_names?}` and **no gold**. The scorer reads `bank2.tsv` separately.

Project files (created by LOOM-d, committed after review; a **Claude Code restart** is needed after adding them):

```json
// .mcp.json
{"mcpServers": {"vera-loom": {"command": "/Users/motonisihikoudai/vera-wiring/env/bin/python",
  "args": ["-m", "verantyx.cli", "loom", "mcp", "--tasks", "experiments/line3/loom/tasks_bank2.jsonl",
           "--runs-dir", "experiments/line3/loom/runs"], "env": {"PYTHONPATH": "."}}}}
```

### 9.2 The subagent definitions

`.claude/agents/vera-loom-weaver.md`:

```
---
name: vera-loom-weaver
description: Weaves an answer through the Vera loom. Use only for loom tasks.
tools: mcp__vera-loom__begin, mcp__vera-loom__lookup, mcp__vera-loom__read_sentence, mcp__vera-loom__add,
       mcp__vera-loom__open_cross, mcp__vera-loom__seat, mcp__vera-loom__seat_run, mcp__vera-loom__unseat,
       mcp__vera-loom__swap, mcp__vera-loom__extend, mcp__vera-loom__topic, mcp__vera-loom__set_depth,
       mcp__vera-loom__link, mcp__vera-loom__unlink, mcp__vera-loom__read, mcp__vera-loom__emit,
       mcp__vera-loom__abstain, mcp__vera-loom__status
---
```

The body (system prompt, fixed text and sha-pinned in `harness_meta`) says:

1. You can only answer by building Vera's structure. Anything you write as plain text is discarded unread, so do not write an answer.
2. Call `begin(task_id, model=<your model id>)` first. The task text comes back from it.
3. The rules: `lookup`/`read_sentence` to find corpus words; `add` (record, or constructed if the mode allows); crosses and seats; the read rule of §3.4 with the 東京 example of §3.5; `read` to check; `emit` or `abstain`.
4. Refusals are typed. Read them, change the structure, and try again within the caps.
5. If the corpus does not hold the answer, `abstain`.

The orchestrating session starts a run with `Agent(subagent_type="vera-loom-weaver", model="haiku", prompt="task_id: bank2/I2-041")`. The prompt carries the task id only; the text comes from `begin`.

`.claude/agents/vera-loom-control.md`: `tools:` = `begin`, `lookup`, `read_sentence` only. The prompt says: answer in plain text, one line, or say 「不明」. The control has the same window into the corpus and a free-text output (§9.3).

### 9.3 Drivers

| driver | where | runs |
|---|---|---|
| **scripted weaver** `verantyx/loom/scripted.py` | pure Python, deterministic: a script is a list of `(tool, args)`, or a function of the previous results (e.g. "lookup X; add the first match; …") | every test; the determinism test; the demo of §3.5 |
| **L1** subagent | the operator's Claude Code session (the Python harness **cannot** call the Agent tool) | the meter §10 now |
| **L2** API driver | `verantyx/loom/driver.py`; fake client in tests | not run here (no key); ready when a key or profile exists |

### 9.4 The harness

`experiments/line3/loom/harness.py` holds the non-model steps the operator runs around each L1 call. It is a CLI so the steps are uniform:

1. `prepare --task ID --mode M --model haiku` → prints the Agent call to make, writes nothing.
2. (the operator calls the Agent tool)
3. `note RUN_DIR --free-text-file F` → `free_text_dropped` (weaver) or `free_text_control` (control); `harness_meta`.
4. `close RUN_DIR` → `abandoned` if the run is not closed.
5. `verify` + `score` (§10). For code: `test RUN_DIR`. The fixture is copied to a temp dir; the emitted text is appended to the target file; `python -I -m pytest -q <task test>` runs with a 60 s timeout on the Air (`tools/air.sh`, the compute-host rule); the exit code goes to the chain as an `attest` row (record).

---

## 10. The meter (predictions are written here before anything is run)

### 10.1 bank2, prose: 10 questions × 2 modes through the loom (L1, Haiku) + 10 free-text controls

| id | kind | gold | what the loom needs (O) | prediction (record_only / constructed_allowed) |
|---|---|---|---|---|
| I2-001 | intra2 | ハッシュ表 | WORD or RUN ハッシュ + 表 juxtaposed (two crosses, or one leg). Gold is in #1, a sentence without ハッシュテーブル (L-G4-d2 point 3), so the model must `read_sentence` | hit / hit |
| I2-041 | intra2 | キューバの太陽 | centre 太陽, キューバ on the の arm. Stable under (a) (キューバ: の 288) | hit / hit (the showcase: の comes from the foundation) |
| I2-008 | intra2 | カール・マルクス | カール + マルクス; 「・」 is not a unit, so the text is カールマルクス, and the scorer's `norm` drops 「・」 | hit / hit |
| I2-034 | intra2 | 1981年 | WORD 1981 + 年 (no tier has 1981年) | hit if the model picks WORD; predicted 1 refusal `not_a_record` first / hit |
| I2-013 | intra2 | 県社 | RUN unit, or WORD 県 + 社 | hit / hit |
| R2-I013 | intra2 | ネパール | one unit | hit / hit |
| I2-025 | intra2 | 青 | one unit (RUN/WORD/CHAR) | hit / hit |
| UF-001 | unans | — | correct = `abstain` | abstain / weave (the model's own knowledge of 衝突処理, partly constructed) |
| UF-015 | unans | — | correct = `abstain` | abstain / abstain |
| R2-U003 | unans | — | correct = `abstain` | abstain / weave a number |

**Measures per run**: gold hit with the t9 scorer (`scorer.hits_text`) on `text`; **and** `hits_words` on the record surfaces only, plus the excess length (characters beyond the gold), because a long text can hit by substring (the OP-F2-5 caveat); the number of ops by class; the refusals by type; the record / constructed / foundation share of `text`; the time (from `timing.jsonl`); verify OK. Unans: correct = abstained.

**Control** (C1): Haiku via `vera-loom-control` with the same lookup tools and a free-text answer, scored with `hits_text` on the answer line; for unans, correct = 「不明」.

**Predictions** (P-LOOM-1 … 6):

1. Answerable, record_only: 7/7 hits, of which ≥ 5 on the first emit attempt.
2. Answerable, constructed_allowed: 7/7; constructed share of `text` ≤ 20 % in median.
3. Unans: record_only abstains 3/3; constructed_allowed abstains ≤ 2/3. **The loom's main measurable effect is on unans**: record_only removes the model's unsupported answers.
4. Control C1: answerable 7/7, unans 「不明」 ≥ 2/3.
5. Ops per answerable run: median 8–20; at least one typed refusal in ≥ 5/14 answerable runs (mostly `not_a_record`, `tier_mismatch`); `unstable_cross` in ≤ 2/14 (single-cross answers are trivially stable).
6. Wall time per run: 2–4 × the control's.

The decisions that would follow are named now: if (3) fails (record_only weaves unans answers out of records), record-only provenance is not enough to stop confident wrong answers, and the loom needs the reader's evidence gate (a record unit must be *read from a cross* that holds a question unit). That would be an owner question, not taken silently.

### 10.2 Code: 5 tasks on a fixture repo

Fixture `experiments/line3/loom/code_fixture/` (written in LOOM-e): `calc/__init__.py`, `calc/ops.py` (`add(a, b)`, `mul(a, b)`), `calc/fmt.py` (`fmt_num(x)` → str), and `tests/test_task_k.py` per task (held-out: written by codex, the role split).

| task | ask | gates it exercises |
|---|---|---|
| K1 | in ops.py, add `double(x)` returning `mul(x, 2)` | context_names (mul is a record) |
| K2 | in ops.py, add `total(xs)` summing with `add` in a loop | for/assign bindings, definition-first inside a body |
| K3 | in fmt.py, add `show_sum(a, b)` returning `fmt_num(add(a, b))` | needs `from calc.ops import add` first (definition-first via import) |
| K4 | in ops.py, add `square(x)` and `cube(x)` that uses `square` | definition order between new defs |
| K5 | in fmt.py, add `fmt_all(xs)` using a list comprehension and `fmt_num` | comprehension scope |

**Measures**: parse-gate pass on the final emit; `undefined_name` and `parse_error` refusals before it; the test pass (an `attest` row); ops; the constructed share (new identifiers such as `double` are constructed).
**Predictions**: final emit passes all gates 5/5; ≥ 1 `undefined_name` refusal in K3 (the import is forgotten first); tests pass 4/5; ops median 60–150.

---

## 11. 循環 — three loops

The order is fixed: **loom → loop 1 → loop 2 → loop 3**. Each loop consumes only verified ledgers (L4) and writes its own rows to the run's chain, or to its own chained ledger. Nothing in a loop edits a row.

### 11.1 Loop 1: audit (the model's output is checked)

- **Input**: an emitted, verified run.
- **Mechanical attest** (`vera loom attest RUN_DIR`), the same typing as `vera attest`:
  - record — every record unit re-found in the index with the same postings (code: same path:line:col and file sha); stability recomputed; parse + definition-first re-run on `text`; tests re-run (code); the files touched = only the task's target file (diff of the temp copy).
  - testimony — constructed units (the model's word); the declared model id.
  - mismatch — anything that differs.
  Each check is one `attest` row with `{claim, verdict, detail}`.
- **Optional auditor model**: another model, run through the loom itself as a `record_only` task whose corpus is the audited run's ledger (as sentences: one row's `op`/`result` per sentence). Its verdict is `audit_verdict` = testimony. It never overrides a mechanical record.
- **Feedback**: every mismatch becomes the next task's input. `vera loom followup RUN_DIR` writes a task `{task_id: <old>/f1, text: original task + the mismatch list}` into a follow-up bank. That bank is only used by a new run; the old run is never reopened.
- **Guarantee**: the attest rows are in the chain, so `verify` covers them; the replay re-derives the mechanical rows (they are pure functions of the run and the index) and must match. The auditor's testimony is replayed as recorded.

### 11.2 Loop 2: growth (passing outputs are stacked onto the frozen stack)

- **What counts as PASS** (decided here, as the coordinator asked; L-LOOM-20): prose — a human `grade: pass` from the grading window **and** no attest mismatch. Code — every gate passed **and** the tests passed (an `attest` record) **and** no mismatch. **A scorer hit alone never counts**: `hits_text` is a substring rule, and a long text can hit it (§10.1).
- **What is stacked**: a passing run becomes one document for `verantyx/line3/stack.py` (`extend(state, doc)`). The document's rows are `{"sent": <text>, "source": "loom:<run_id>#<output_sha12>"}`. **Constructed segments are replaced by 「、」 before stacking** (L-LOOM-21). 「、」 is a character no tier makes a unit (L-32), so constructed text can never become a posting. Without this, a constructed word stacked once would come back as a record (laundering). The replaced spans and their constructed provenance are stored in the stack ledger row (`stacked {run_id, constructed_spans}`). `space.KINDS` is closed (L-40) and is **not** extended. The provenance is in `source` and in the stack ledger; extending KINDS would change provenance typing, which only the owner may do (§11.3).
- **Which stack**: a separate stack directory, `fulllead` 300 articles as its prefix (the G4-b build), then the passing woven documents in the order of their grades. The fulllead-only stack is the **no-stacking control**.
- **Meter**: G4's own: 現れる / 残る / 壊れる (G4 §7.4) and the 2×2 headline (G4 §7.3), per step, on the bank2 questions and on the woven tasks' questions, against the control.
- **Why growth is exercised here and not with fulllead**: woven outputs of one task domain reuse the same vocabulary, while gate G-2 found that most RUN seeds of fulllead never recur (the coordinator's figure: 89 % of RUN seeds; (C), not re-counted). Prediction: a woven document grows existing open crosses (`fill`) far more often than it opens new ones (`birth`). Measured from the stack ledger as fill / (fill + birth) per step, against the fulllead steps.
- **Failure modes**: (i) a mechanically graded wrong output enters the stack (a code run whose tests are too weak). Control: code passes need the codex held-out tests, and every stacked document is listed in the stack ledger, so it can be removed by rebuilding the stack without it (the stack is a pure fold, `build(docs[:k+1]) == extend(build(docs[:k]), docs[k])`). (ii) Drift: the stack gradually reflects the model's habits. Measure: the share of postings whose sids are `loom:` sentences per tier per step, always reported beside the 2×2. (iii) Self-confirmation: a woven sentence makes the same answer easier next time. Control: the bank2 questions whose woven answer was stacked are reported apart from those that were not.
- **Guarantee**: a stacked step is reproducible from (prefix, the list of `run_id`s, each run's verified `text`); `stack.save` keys the step by the prefix sha, and the woven list sha is added to the key (L-LOOM-22).

### 11.3 Loop 3: self-modification (the model changes Vera's code)

- **Path**: a change to Vera's own code is woven through the **code loom** (parse gate, definition-first, the repo's tests as `attest`). Then an Opus review. Then the review verdict as an `audit_verdict` row. Then `git commit` by the owner's agent, recorded by the recorder hooks (`commit` kind). The loom run id goes in the commit message.
- **The boundary (checkable, not prose)**. Frozen except by the owner's verbatim decision:
  1. the three ratios and the energy (`verantyx/line3/energy.py`);
  2. the fixed-point / stability definition (`placement.score_flat`, `seated_key`, `verify_*`);
  3. provenance typing (`space.KINDS`, the record/constructed/foundation kinds of the loom, attest's record/testimony/mismatch);
  4. abstention (the typed refusals and abstain types);
  5. the initial placement: `foundation.DEFAULT_SPEC`, `P7`, `LADDER`, `WEIGHTS`, `FIB_DEN`, and `grammar.py`'s copies of them.
  A file list `ops/loom_frozen_paths.txt` plus a check `vera loom boundary DIFF` refuses a woven change that touches a frozen file (`frozen_path`), or a symbol on the frozen list inside an allowed file (via an AST diff of top-level names: `frozen_symbol`). The model may change data (units, crosses, stacks) and reviewed implementation elsewhere.
- **Guarantee**: every self-modification is (loom run ledger, verified) + (review row) + (recorder commit row). A commit without a loom run id is outside the loop and is reported as such.
- **Failure mode**: a change that keeps the tests green but shifts meaning (e.g. a default flips). Control: the existing golden files (`tests/line3/golden_*.json*`) are part of the test set every woven change must pass.

---

## 12. Tickets, decisions, tests, files

### 12.1 File layout

```
verantyx/loom/__init__.py
verantyx/loom/state.py      Unit, LoomCross, LoomState, state_sha, the seating rules
verantyx/loom/ops.py        every operation as a pure function (state, args) -> (state, result); caps; refusals
verantyx/loom/read.py       the read rule, annotated, joins/adhesion, stability (placement.seated_key), the emit gate
verantyx/loom/code.py       the code index, constructed-token check, spacing, parse gate, definition-first, imports
verantyx/loom/ledger.py     rows, chain, append (flock), verify, replay
verantyx/loom/mcp.py        FastMCP server (vera-loom), path confinement
verantyx/loom/scripted.py   the scripted weaver
verantyx/loom/driver.py     the L2 API driver (fake client in tests)
verantyx/loom/attest.py     loop 1;   verantyx/loom/grow.py  loop 2;   verantyx/loom/boundary.py  loop 3
verantyx/loom/builtins_py311.txt
verantyx/cli.py             top-level `loom` sub-commands: mcp, replay, verify, note, close, score, grade-import, attest, followup, boundary
.mcp.json, .claude/agents/vera-loom-weaver.md, .claude/agents/vera-loom-control.md
experiments/line3/loom/{tasks_bank2.jsonl, tasks_code.jsonl, code_fixture/, harness.py, score.py, runs/, results/}
tools/{loom_grade_template.html, build_loom_grade.py, loom_watch_template.html, build_loom_watch.py}
tests/line3/test_loom_{state,ops,read,stability,code,ledger,mcp,enforce,driver,windows,attest,grow,boundary}.py
ops/loom_frozen_paths.txt
```

The loom imports `geometry`, `foundation`, `placement` (only `seated_key`, `extend`, `canon`, `to_cross`, `from_cross`), `grammar` (only LADDER/WEIGHTS for the arm order), `granularity.SpanIndex`, `space`, `stack` (loop 2). It modifies none of them.

### 12.2 Tickets (build order; implementation Sonnet, review Opus, held-out tests codex)

| ticket | depends | content | acceptance | effort |
|---|---|---|---|---|
| **LOOM-a state + ops** | — | state.py, ops.py: every §4 operation except read/emit; caps; refusals; uids/cids | T-LOOM-01…09 | 1.5 d |
| **LOOM-b read** | a | read.py: the read rule (prose + the code skeleton), annotated, joins, adhesion, `read` | T-LOOM-10, -11, the §3.5 example byte-exact | 1 d |
| **LOOM-c emit + stability** | b | the emit gate with OP-LOOM-1 under the recommended default (a), plus the switch `--stability strict_npa\|strict_np\|report` so the owner's answer is a one-line change | T-LOOM-13…16 | 1 d |
| **LOOM-d ledger + CLI + MCP + L1 files + L3 code confinement** | c | ledger.py, replay/verify, mcp.py, cli `loom`, `.mcp.json`, the agent files, path confinement | T-LOOM-12, -17…20, -30, -32, -33, -35 | 2 d |
| LOOM-d2 OS sandbox profile | d | `sandbox-exec` profile for the server, tried on the Air; result recorded either way | the server runs under it, or the failure is recorded | 0.5 d |
| **LOOM-e code** | c | code.py, the fixture, `tasks_code.jsonl`; codex writes the held-out tests | T-LOOM-21…26 | 2 d |
| **LOOM-f L2 driver** | d | driver.py with a fake client; tool_choice by model (§7.3) | T-LOOM-31 | 1 d |
| **LOOM-g meter** | d (prose), e (code) | tasks_bank2.jsonl (no gold), harness.py, score.py; the operator runs §10 (restart first) | the §10 tables; predictions marked held/failed; T-LOOM-34 | 1 d + run |
| **LOOM-h windows** | d | grading window, observation window (+ code mode), grade-import | T-LOOM-40…42 | 1.5 d |
| **LOOM-i loop 1 audit** | g | attest.py, followup | T-LOOM-50…52 | 1 d |
| **LOOM-j loop 2 growth** | h, i | grow.py: pass rule, 「、」 replacement, stacking, the G4 meter vs control | T-LOOM-53…56 | 2 d |
| **LOOM-k loop 3 self-modification** | j | boundary.py, frozen list, commit linkage | T-LOOM-57…59 | 1 d |

Order: a → b → c → d → (e, f, h in parallel) → g → i → j → k. LOOM-c needs OP-LOOM-1; LOOM-e needs OP-LOOM-2; LOOM-b needs OP-LOOM-3. All three may be prototyped on the recommended default, labelled as such.

#### LOOM-notes (added 2026-10-11, owner question on 気づき)
Three layers, never mixed: (1) structural PREVENTION — typed refusals already in the core (definition-first, parse gate, unstable key, constructed in record_only); (2) structural NOTES that do not block — a thread-wide consistency pass at `read`/`emit` producing typed annotations in the `annotated` output and the ledger: `CONFLICT` (two crosses with the same centre whose arm contents contradict within the thread, e.g. 首都 ← 東京 vs 首都 ← 大阪), `UNANCHORED` (a constructed unit seated on an arm whose particle the corpus evidence contradicts), `NO_RECORD` (a lookup returned nothing and the model fell back to a constructed unit at that position); same type family as attest's record/testimony/conflict; (3) the model's own NOTICING — not guaranteed by the structure, only made observable: the ledger exposes self-corrections (unseat/swap before emit, a plan change after an empty lookup, recovery after a refusal). Meter columns for (3): self-correction count and kinds, recovery rate after refusals, against the free-text control. Effort: notes 1 d, meter columns 0.5 d.

### 12.3 Local decisions fixed by this design (L-LOOM-nn; the implementer copies them into LINE3_LOCAL_DECISIONS `## LOOM`)

| id | decision |
|---|---|
| L-LOOM-01 | No `rotate` tool: a seated cross is rotation-invariant (its arms are known by their particle) and the read rule reads by particle |
| L-LOOM-02 | uid/cid are creation-order counters; they are labels, never ranks |
| L-LOOM-03 | Cells hold uids; surfaces and provenance live in the registry; foundation cells hold `foundation.token(p)` |
| L-LOOM-04 | One thread per run, an ordered list; no nesting in v1 |
| L-LOOM-05 | The code spacing table + the re-tokenize check |
| L-LOOM-06 | `emit`/`read` return all refusals, in the fixed order of the §3.7 table, then by thread position |
| L-LOOM-07 | Every tool takes `run_id`; several runs per server process |
| L-LOOM-08 | The caps of §4 |
| L-LOOM-09 | No undo; corrections are new ops |
| L-LOOM-10 | The prose constructed-text rules (NFC, 1–8 chars, no whitespace / NUL / control) |
| L-LOOM-11 | The CODE index: token types, logical lines as sentences, sorted file order |
| L-LOOM-12 | Definition-first as specified in §5.2 (textual order; forward references refused) |
| L-LOOM-13 | The unsupported constructs and the pinned stdlib list |
| L-LOOM-14 | A per-run loom ledger, separate from `.vera/ledger`; the row shape of §6.1 |
| L-LOOM-15 | No wall time in a hashed row; `timing.jsonl` outside the chain |
| L-LOOM-16 | L2 keeps the model's content blocks in the API history unchanged; text is dropped only from the output path |
| L-LOOM-17 | The tier of a record unit is chosen by the model at `add`; `lookup(tier=any)` shows every tier's match |
| L-LOOM-18 | `lookup` is exact-match; `read_sentence` is the second read-only window (the gold of I2-001 is in a sentence without the subject, so exact lookup alone cannot reach it) |
| L-LOOM-19 | Stability is computed with `placement.seated_key` on a flat of surfaces in which a constructed unit is `"\u0000C:" + uid` (never in the postings, never equal to another cell); `trivially_stable` = the key and every swap's key are (0, 0, 0) |
| L-LOOM-20 | The loop-2 PASS rule (§11.2) |
| L-LOOM-21 | Constructed segments become 「、」 when stacked |
| L-LOOM-22 | The woven-list sha joins the stack step key |
| L-LOOM-23 | `extend` is loom-local (prepend empty outer seats, no `canon`); the loom never calls `placement.canon` on its crosses; `seat_run` ends on the innermost data seat; `seat` with a bare arm = the next empty data seat in the arm's growth direction |

### 12.4 Tests (T-LOOM-nn)

| id | test |
|---|---|
| 01–09 | each op: success and each refusal type; the foundation seats are never touched by any sequence of ops (a property test over random scripted sequences); caps fire exactly at the limit; `add` record = postings exactly; `constructed_shadows_record` over all three tiers |
| 03 | the §2 probe values as assertions (postings, adhesion rows, n/p of 日本→首都) |
| 10 | `"".join(seg.s) == text` for every read |
| 11 | the read rule on toys: arm order per OP-LOOM-3 (a); particles only on non-empty arms; は only with topic; code head-initial order; `seat_run` fills in reading order |
| 12 | determinism: scripted runs byte-identical under PYTHONHASHSEED 0/1/12345 |
| 13 | §3.5 end-to-end: the exact op list → `text` 「東京は日本の首都です」, the annotated kinds, c2 stable with key (2, 2, 2880); record_only → `constructed_forbidden` at op 4 and the emit of 「東京は日本の首都」 |
| 14 | 日本 on the が arm → `unstable_cross` with the witness containing the move to +x |
| 15 | the stability result equals `placement.verify_class_foundation([cross])`'s fixed-point verdict on the same flat (an independent check) |
| 16 | `empty_centre`, `leg_gap`, `unlinked_cross`, `tier_mix`, `empty_thread` each fire, and several at once are all reported |
| 17–20 | ledger: chain verify statuses; TORN_TAIL refuses append; replay byte-identical; REPLAY_DIFFERS on a forged result; secret-shaped text never in a row |
| 21–26 | code: one-token constructed check; spacing + re-tokenize; parse gate; definition-first (recursion allowed, forward reference refused, comprehension scope, import of a fixture name, `from m import *` refused); builtins list pinned; K1–K5 reference solutions pass all gates (written by the scripted weaver) |
| 30–35 | enforcement (§7.5) |
| 40–42 | windows: the builders embed only verified runs; grade-import appends `grade` rows after verify and refuses a run that does not verify; the page's segment text equals `annotated` |
| 50–52 | loop 1: attest rows for a correct run are all record/testimony; a tampered index entry → mismatch; followup writes a new task and never reopens the run |
| 53–56 | loop 2: the PASS rule (a scorer hit without a grade is not stacked); 「、」 replacement leaves no constructed surface in any posting; the stacked step equals a fresh build from the same list; the control stack is byte-equal to the G4-b fulllead build |
| 57–59 | loop 3: a diff touching `foundation.py` → `frozen_path`; a diff changing `WEIGHTS` inside `grammar.py` → `frozen_symbol`; an allowed diff passes |

### 12.5 The biggest risk

**The loom may be unusable by a small model under the faithful rule.** Strict stability (OP-LOOM-1 (a)) plus `record_only` plus exact-match units means that many things the model wants to say are refused. Haiku may spend its caps on refusals and abstain where the answer was weavable. The meter is built to show this rather than hide it: refusals by type, ops per answer, abstentions on answerable questions, and the control. The single-unit answers of bank2 (5 of the 7 answerable) are trivially stable and will not reveal the cost. Multi-cross prose such as §3.5 will. If the cost is too high, the choice between OP-LOOM-1 (a), (b) and (c) is the owner's, made with these numbers in hand.

**The second risk is code (OP-LOOM-2 (a))**: token-level weaving makes each line a puzzle of 5–20 seats. The cap (400 ops) may be too small for K2–K5. The ops count is measured; raising the cap is an L-LOOM change, while the unit choice is the owner's.

---

## 13. Scope and notes

- **Positioning (owner, 2026-10-11, recorded in ops/decisions):** the loom is not a replacement for the LLM. It is the LLM's organ of speech — the LLM holds the intent, Vera decides the form, the evidence and the record. Constructed units are the LLM's own words, passed through with their mark. The only cost the loom adds is latency and op count, which is an implementation matter (batch seating, batch linking); it is not a limit on expression. Demand is therefore every place an LLM is used where provenance and replay are required, not a separate niche.
- The owner's three questions (§0.1) are answered: OP-LOOM-1 (a) full key, OP-LOOM-2 (a) Python tokens, OP-LOOM-3 (a) が を と で に の then the centre.

- Not in scope: nesting crosses (L-LOOM-04), a code foundation (OP-LOOM-2 (c)), the reader's evidence gate (named in §10.1 as a possible follow-up), CHAR adhesion for prose crosses (`foundation.ATTACH_RULES` has `char_next`; a CHAR prose cross uses it as is), any change to G4's paused direction.
- Nothing here changes a committed byte of the line-3 reader. The loom is a new package and a new CLI sub-command.
- The owner's three questions are at the top (§0.1). Every result produced before they are answered is labelled with the default used.
