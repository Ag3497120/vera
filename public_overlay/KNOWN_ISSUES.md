# Known issues — v0.9-preview (base: dev `d1942e2`)

Everything here is a hole we know about and have **not** closed, except the notes marked "Fixed", which record what the first attack wave broke and which ticket closed it. Each item names its source as `Verantyx-Vera-alpha@d1942e2:<path>` (the development tree, which the public tree does not carry the artifacts of; the older rows of the README table cite `ecde332`, the commit they were measured at). Numbers carry a mark `[N-xx]` that points to a row of the table in `README.md` (value, denominator, set, source). Items marked "(日本語)" are repeated in Japanese in short form.

Attack results of the first attack wave are in the README ("Attack results"; source `docs/AUDIT_2026-10-06.md` at `d1942e2`): broke 1 of 16 in the attest group [N-60], 4 of 11 in the quote-check group [N-61], 4 of 17 in the ledger-and-records group [N-62], 0 of 4 in the answer-path group [N-63] and 0 of 2 in the human-confirmation group [N-64]. The kinds that were fixed (W16-t3b, W16-t6b, W16-t7c; integrated in dev) are noted below as "Fixed" next to the kinds that remain; none of them was on this list before the attack, so no row was retired. The kinds that remain are listed in sections 1 to 3. The next wave is not scheduled.

## 1. Quote check in serve layer 0 (T3)

The label `anchored` means: the cited quote exists verbatim, the answer's numbers, dates, names and content words appear in it, and negation agrees. It is a mark, not a confirmation that the answer is right (`docs/FUSION.md` §9.8, `docs/AUDIT_2026-10-06.md` "限界").

- **Wrong answers without checkable elements can pass as `anchored`.** In the self-made T3-1 set, 5 of 30 wrong answers stayed `anchored` [N-40]; in the saved W14 C run, 31 of 144 `anchored` rows had no checkable element [N-38]. (日本語: 要素の無い誤答は検出できない。)
- **An unrelated but existing line can anchor an answer** whose name also occurs in that line (type N1 in §9.8). The check does not read whether the quote answers the question.
- **Part-of-name matches** (`緑川工務店` vs `緑川建具店`): only the proper-noun part is compared.
- **Wording variants become false `unanchored`**: surface forms of nouns are compared (`打ち合わせ`/`打合せ`, `申込み`/`申し込み`). Negation is compared only as present/absent, so a correct answer next to a negated relative clause in the quote is marked `unanchored`.
- **Different documents with the same base name** collide in the records layer; the second one's quotes can come out `fabricated` (J-R3-4, §9.8).
- **One W14 row lost its quote check** because the LLM call timed out (255 of 256 rows carry `quote_check` [N-35]). Why layer 0 takes about twice as long as the plain call is not diagnosed.
- **Left open after the attack (W16-t3b fixed the other kinds).** A paraphrase that drops the key word; a surface match of a noun and a verb; an answer "that is right" when the quote contains the word for "right" (§9.8); a quote under a forged source path stays `anchored` when the sentence is in the record, and is shown as `relocated`. `anchored` is not a proof of correctness. The kinds fixed by W16-t3b (dev `1d37c57`): swapped subject and object, a different tense, a composite of two lines, an exact match for a forged path [N-61]. The counts on our own sets did not change after the fix [N-70] [N-71] [N-72].
- **Real-LLM error rate of layer 0 is not measured** [N-43]: the held-out T3 set used scripted ("fake") LLM items.
- The final checker re-scored the saved W14 C run: 140 rows `anchored` instead of the saved 144 [N-39] [N-37]; we report both and do not mix them.
- **The old and the new yardstick for "sources Vera verified" are different definitions.** The old one counted 0 rows [N-34]; the new one counts rows with an existing quote [N-36]. Do not read one as an increase over the other (`docs/FUSION.md` T3-2).

## 2. Completion-claim check (T6, `vera attest`)

- **Vera's reading adds nothing over a plain regex/JSON extractor** on the self-made set: both catch 22 of 22 false facts [N-20] [N-21], added detections 0 [N-22]. The value is the mechanism (sha, collected test count, exit code, ledger), not the reading (`docs/ATTEST.md` T6-2). The plain LLM judge said "no" to 17 of 53 correct facts [N-23].
- **No labels for the replay on real reports.** 173 real reports were replayed; the structured extractors found no claims in free-text reports, and the label column of `labels.tsv` is empty, so we cannot say how many reported mismatches are real (`docs/ATTEST.md` T6-3, `artifacts/w16-t6/replay/summary.txt`).
- **Left open after the attack**: unless `--ledger-head` is given, a forgery that recomputes every row and the HEAD of the ledger is not detected (a property of the T7 verification). (Fixed: W16-t6b, dev `995fa4b`: a tampered ledger that fails the T7 verification is no longer used; the claim stays `TESTIMONY` with `LEDGER_UNVERIFIED`; the CLI has `--ledger-head` [N-60].)
- A `--rerun` only runs commands from a closed allowed list; other acceptance commands stay `TESTIMONY` (`COMMAND_NOT_ALLOWED`).

## 3. Ledger and `vera run` (T7, `docs/RECORDER.md` §10, §14.4)

- **Over-redaction accepted by ruling**: some harmless hyphenated words are cut and replaced by a redaction mark (`task-management-system-abcdef` becomes `ta[REDACTED:sk]`); the number of redactions is recorded in `data.redactions` (`docs/RECORDER.md` §13, point 2).
- **Left open after the attack** (redaction is a best effort that errs toward over-redacting, not a guarantee that nothing leaks): a key split across two fields; a superposition of variants (full-width mixed with URL encoding); `U+2010` and zero-width characters; hexadecimal; base64 wrapped over lines; certain sequences with many delimiters (`docs/RECORDER.md` §15.4, §15.5). Fixed (W16-t7c, dev `ccfc839`): full-width, URL-encoded and base64 forms of a token are checked and the whole original token is redacted; 3 of the 4 broken kinds [N-65], and the 41 variants of the attacker are redacted [N-66].
- **`vera run`**: a descendant that was born and detached between two samplings is not recorded.
- **Pathological inputs cost quadratic time** in the redaction pass (about 5 s for 99,000 characters of repeated `password=`; ordinary text is fast). No speed-up was made (`docs/RECORDER.md` §13, point 3). After the attack: when one token holds a large number of short base64-like runs, the time grows with the square of the length (§15.5).
- A tampered last line plus its sha and the head can only be detected if the head is pinned elsewhere (§2). A torn last line blocks appends instead of being repaired silently.
- The `PostToolUse` classification looks at the head word of each `&&`/`;`/`|` segment only; a nested `bash -c "git commit"` is recorded as a plain tool call. A Claude Code version may not call `PostToolUse` for failed commands; the reliable exit code is the one from `vera run`.
- `hooks print`/`install` pin the code root as an absolute path; moving or deleting that clone makes every hook fail with exit 1 (recorded as not recorded, the agent is not stopped) (§14.4). A read-only ledger can end with exit 0 although the HEAD update failed.

## 4. Reader and human confirmation (T1b, T8)

- **T1b (a), a lost ability**: sentences with a desire/ability form such as 「先生は何を読みたかった？」 used to be answered and now abstain: the later-stage answer disappears and the row becomes `UNKNOWN_UNREAD` (`ABSTAINED`) (3 rows of the frozen extra2 set: X011, X012, X014; `artifacts/w16-t1b/CHANGES.md`, rule K815).
- **T1b (b)**: names followed by a title are now answered whole (`森田` becomes `森田課長`); where the written forms differ, the answer becomes `AMBIGUOUS` or an abstention (rule K801).
- **The base reader reads few sentences**: 22 of the 60 held-out T8 sentences [N-12]. A human confirmation did not unlock any independently written sentence [N-10] (`docs/AUDIT_2026-10-06.md` "限界").

## 5. Placement and growth (T10, `docs/COARSE_PLACEMENT.md` §11.7)

- The accuracy of generated definitions is known only on the frozen test data; words outside it are not measured.
- The word list is picked by frequency and includes function-like nouns and predicates; a `null` answer from the model counts as an abstention.
- Several thresholds were chosen on one development placement, not on a held-out one.
- A particle can appear both in `frame` and in `frame_unconfirmed` for the same word; generation types outside the significant distribution appear only in `frame_unconfirmed` and are not read.

## 6. Benchmark (W14, `docs/BENCHMARK_PUBLIC.md`)

- **Human grading is not done** [N-41]; the numbers in the table are machine drafts (normalized exact match and a fixed abstention sentence). Paraphrases are left to a person.
- **The strict mode (D) equals "always abstain" (Z)** on the machine judgement [N-24] [N-25] [N-27] [N-28]: it asserts nothing, so it can never be wrong, and it answers nothing. Read it together with the correct-answer rates, never alone.
- **The default mode (C) equals the plain LLM it is built on (A, the same `qwen3.5:4b`)** on the machine judgement [N-30] [N-57] [N-58] [N-59]: Vera's default mode adds nothing to the plain LLM's machine-judged results. The larger A' is a different model and not comparable to C [N-32].
- The hosted strong-LLM baseline was not measured (no network) [N-42].

## 7. Tests, packaging, process

- **The full test suite has known failures**: [N-19] (the same set as the baseline; they come from the environment, not from the work of this release; the total is not stated in the source, so no denominator is given).
- **Two distributions exist** (`verantyx_vera 0.1.0a1` built from the root `pyproject.toml`, and `vera-ja 0.2.0a1` in `public_overlay/`). Which one v0.9-preview ships is not decided here (auditor/owner).
- The smoke test (`tools/release/smoke_wheel.sh`) passed when run in the foreground. A first run started from a background job failed at the `serve` stage ("serve process did not stop after SIGINT"); the cause was not confirmed (`artifacts/w16-t11/release_assets.md`).
- `public_overlay/pyproject.toml` and `public_overlay/vera_base/corpus.py` still name a release URL under the author's account; they are outside this change and are listed in `CHANGELOG.md` for the auditor.
- The serve layer 0 example in the README has no pasted output yet: the auditor runs it with a real LLM (marker `AUDITOR_RUNS: serve-layer0`).

## 日本語（要約）

- `anchored`（錨あり）は「引用が実在し、答えの要素が引用に現れ、否定の有無が合う」という印で、答えが正しいことの確認ではない。要素の無い誤答・無関係だが実在する行・名前の一部の一致・言い換えの偽の錨なしが残る（§1）。
- 完了申告の照合は、自作の集合では Vera の読みが単純な抽出器に何も足さない。実報告の再生には正解ラベルが無い（§2）。
- 台帳: 過剰な伏せを許容、病的な入力で 2 乗、hook は絶対パスを固定（§3）。
- 読解器は読める文が少なく、人の確認で新しく読めた文は 0 だった（§4）。T1b で願望・可能の文の一部が答えから棄権に変わった。
- 配置の精度は凍結データの外では未測定（§5）。W14 の人の採点は未了、strict は「常に棄権」と同じ、Vera 既定はその土台の LLM 単体と機械判定が同じ（§6）。
- 全体テストの既知の失敗、配布物が 2 つあること、煙試験の 1 回目の失敗（§7）。
- 最初の攻撃の波の結果は README の「攻撃の結果」にある。破れた数は attest 群 [N-60]、引用の照合群 [N-61]、台帳と記録群 [N-62]、回答経路群 [N-63]、人の確認群 [N-64]（分母は各群で試した数）。直した型（W16-t3b・t6b・t7c）は本文の各節に「直した」として併記した（攻撃の前の一覧には無かった型で、退役させた行は無い）。残る型: 引用の照合は要の語を落とした言い直し・名詞と動詞の表層の一致・「その通り」で引用に「通り」がある場合・偽装したパスでも文が記録にあれば錨あり。伏せは二つの欄に分けた鍵・変形の重ね合わせ・`U+2010` とゼロ幅の字・十六進・折り返した base64・区切り字の多い並び・短い base64 らしい列が大量にあると二乗。attest は `--ledger-head` が無いと全行と HEAD を計算し直した偽造を検出できない。`vera run` は標本化の間に生まれて切り離された子孫を記録しない。「錨あり」は正しさの証明ではなく、伏せは漏れない保証ではない。

## History: the list at snapshot 2026-10-03 (working-copy commit d25a73a, development paused)

Kept as it was (not recomputed for v0.9-preview). The test counts below describe that snapshot only.

Clean clone, `PYTHONPATH=vera_base python -m pytest tests`: 1,666 passed, 18 failed, 9 skipped.
Cause: several units were merged in a wave whose regression gate covered only a few test files; later merges changed behaviour that older tests encode. A repair pass fixed the verifier-agent and memory tests and was stopped before the rest. Each remaining failure is either a real regression (code to fix) or an outdated expectation (to update with a reason); safety tests are not to be loosened.

| Test file | Failing |
|---|---:|
| tests/test_semantic_measure.py (role-only questions, kanji-title splitting) | 8 |
| tests/test_semantic_realize.py (に/で/から case roles typed as ambiguous in some sentences; literal-overlap guard) | 3 |
| tests/test_semantic_coordination_codex.py | 2 |
| tests/test_semantic_scope_safety.py, test_semantic_public.py, test_request_goal_route.py, test_one_trace.py, test_conductor.py | 1 each |

Demos: `tools/demo_conduct.py` and `tools/demo_system.py` fail after the driver/verifier merges; `demo_generate`, `demo_outside`, `demo_vocab`, `demo_frame` print `DEMO OK`.

Behaviour versus the published 0.1.0 package: in pack-only mode the three example outputs listed in the README differ by design (source identity required; ties abstain). For 0.1.0 behaviour use the v0.1.0 tag.

Not in this repository: the independent attacker tests (they record about 150 defects as xfail and were not triaged), the Codex-generated corpus, and any sealed or heldout data.
