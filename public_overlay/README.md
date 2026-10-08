---
language: ja
license: mit
tags:
- japanese
- rule-based
- no-weights
- verification
- predicate-argument-structure
library_name: none
pipeline_tag: text-generation
---

# Vera — a trustworthy record and verdict for the work AI agents do in Japanese

*Status: preview (`v0.9-preview`, not yet published). Base: the development tree `Verantyx-Vera-alpha` at commit `d1942e2`.*

Vera is **not** a language model and does not compete with one at reading, answering or writing. It sits next to an AI agent (or an LLM) and does three things with what the agent says and does:

1. **Judge.** It compares the agent's claims with recorded facts: file hashes, collected tests, exit codes, numbers in command output (`RECORD` / `TESTIMONY` / `MISMATCH`), and the verbatim quotes an LLM gives from your documents (`anchored` / `unanchored` / `conflict`).
2. **Record.** It keeps an append-only, hash-chained ledger of what the agent ran, so that a later check can tell whether the record was changed.
3. **Ruler.** It ships the measuring tools and a public benchmark, and reports negative results in the same table as positive ones.

## What Vera does not do

- It does **not** read Japanese better than an LLM and does not try to. The base reader is narrow: it reads 22 of 60 held-out sentences [N-12].
- It does **not** answer or write on its own. The answer is made by the LLM; Vera compares and records. Text that comes from an LLM is shown as testimony, never as a fact of Vera's.
- It does **not** do general Japanese reading comprehension. Sentences it cannot read stay marked as unread and block the answer they could change.

## What you can do today

All commands below were run in the tree at `ecde332`. `vera ...` stands for `python -m verantyx.cli ...` of that tree (or the `vera` command of an installed wheel). The output is pasted as printed, with exactly two normalizations: in the first line of `attest`, the absolute path of the working directory after `tree=` is replaced by `.`; in `events verify`, the hexadecimal `head` value is replaced by `<sha256>`. Counts, states, types and exit codes are never replaced. The replay script is `artifacts/w16-t11/examples/replay.sh` in the development tree (added after `ecde332`). The examples were run at `ecde332`; the replay was then run again in a tree that contains the product code of `d1942e2` (the integration commit `4c2a2e5`) and the normalized output is byte-identical to the pasted one (`artifacts/w16-t11/r3.r3.txt`).

### 1. Check a completion report: `vera attest <report> --tree <repo>`

An agent's report says what it did. `attest` checks each claim against the files and a re-run, and sorts it into **record** (matches), **testimony** (cannot be checked; neither true nor false) or **mismatch**. The report below claims a file hash (correct), two test files (one with a wrong count) and an acceptance command that is not on the list `--rerun` may run.

<!-- EXAMPLE a_attest -->
```text
$ vera attest report.md --tree demo --rerun
vera attest  report=report.md  tree=./demo
[V] 申告 4 件: 記録 1 / 証言 2 / 食い違い 1（読み飛ばした形外れの行 0）
  V-1 行6 証言 NO_BASE [changed] - 変更: calc.py(sha256 af626eb7a9c3d865bc4d7d84f96982d7349f4931c403286d23603d85e6552442)。
      記録 MATCH file_sha:calc.py  申告="af626eb7a9c3d865bc4d7d84f96982d7349f4931c403286d23603d85e6552442" 実際="af626eb7a9c3d865bc4d7d84f96982d7349f4931c403286d23603d85e6552442"
      証言 NO_BASE changed:calc.py  申告="changed" 実際=null
  V-2 行7 記録 MATCH [tests_added] - 追加したテスト: tests/test_calc.py の 2 件が通った。
      記録 MATCH test_exists:tests/test_calc.py  申告="exists" 実際="ある"
      記録 MATCH test_count:tests/test_calc.py  申告=2 実際=2
      記録 MATCH test_passed:tests/test_calc.py  申告="passed" 実際=0
  V-3 行8 食い違い COUNT_DIFFERS [tests_added] - 追加したテスト: tests/test_extra.py の 4 件が通った。
      記録 MATCH test_exists:tests/test_extra.py  申告="exists" 実際="ある"
      食い違い COUNT_DIFFERS test_count:tests/test_extra.py  申告=4 実際=1
      記録 MATCH test_passed:tests/test_extra.py  申告="passed" 実際=0
  V-4 行9 証言 COMMAND_NOT_ALLOWED [acceptance] - 受入 A-1: `make deploy` を実行し、終了コード 0。
      証言 COMMAND_NOT_ALLOWED exit:make deploy  申告=0 実際=null
[a] 申告 0 件: 記録 0 / 証言 0 / 食い違い 0（読み飛ばした形外れの行 0）
# exit code: 1
```

The mismatch is `COUNT_DIFFERS` (four claimed, one collected). The two testimonies are `NO_BASE` (no `--base` given, so "changed" cannot be checked) and `COMMAND_NOT_ALLOWED` (the command is not on the closed list, so it is not re-run). The exit code is `1` because there is a mismatch.

### 2. Keep the agent's work in a ledger: `vera run -- <cmd>` and the hook template

`vera run` runs a command and appends its start and exit to the ledger; `events verify` re-computes the hash chain.

<!-- EXAMPLE b_run -->
```text
$ vera run --ledger-dir .vera/ledger -- python3 -c "print(2+3)"
5
# exit code: 0
```
<!-- EXAMPLE b_verify -->
```text
$ vera events --ledger-dir .vera/ledger verify
{"head": "<sha256>", "n": 2, "problems": [], "status": "OK"}
# exit code: 0
```

If a line of the ledger is edited afterwards (here: the exit code in line two of a copy of the ledger), `verify` reports it and exits `1`:

<!-- EXAMPLE b_verify_tampered -->
```text
$ vera events --ledger-dir .vera/ledger_tampered verify
{"head": "<sha256>", "n": 2, "problems": [{"line": 2, "type": "SHA_MISMATCH"}], "status": "TAMPERED"}
# exit code: 1
```

`vera hooks print --claude-code --vera-cmd vera` prints a ready-made Claude Code hook configuration that appends the owner's utterances and the agent's shell tool calls to the same ledger (first lines shown; the real output is longer):

<!-- EXAMPLE b_hooks -->
```text
$ vera hooks print --claude-code --vera-cmd vera
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "vera events add owner_utterance --stdin --from claude-code --ledger-dir \"${CLAUDE_PROJECT_DIR:-.}/.vera/ledger\" || exit 1",
            "timeout": 10
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
```

### 3. Ask a question about documents: `vera serve` (layer 0)

`vera serve --backend ollama --model <model> --document <file>` passes your documents to a local LLM and then checks the **verbatim quotes** the LLM cites against those documents. The reply carries `vera.quote_check.verdict` = `anchored`, `unanchored` or `conflict`.

```text
vera serve --backend ollama --model qwen3.5:4b --document guide.txt --port 11500
```

<!-- AUDITOR_RUNS: serve-layer0 -->
Run by the auditor on the development tree with a local LLM (replay: `artifacts/w16-t11/examples/replay_serve.sh`, which also writes the two-line rental guide used as `guide.txt`). An LLM's wording can differ between runs, so this is one recorded run, not a byte-replayed example. The first line of the reply says what was checked: the quoted sentence exists in the record and the answer's number appears in it — not that the answer is correct.

```text
run:      dev 0d4bc6f, 2026-10-06 06:41 +0900, ollama qwen3.5:4b (digest 2a654d98e6fb), one run
question: 一人で何冊まで借りられますか。
reply:
［証言: LLM の答えです。引用した文は記録にあります（確かめたのは、引用の実在と、答えの数値・日付・固有名・内容語が引用に現れることだけで、答えの正しさではありません）］
5冊
（引用の出典: guide.txt:1）
vera.quote_check: verdict anchored; quote guide.txt line 1 found exact; element number 5冊 found in guide.txt:1
```

## Held or marked, versus checked

Vera keeps two different things apart, and the type names in its output say which one you are looking at:

| What the output says | Meaning | Checked against a record? |
|---|---|---|
| `attest`: `RECORD` | the claimed value equals the actual value (hash, test count, exit code, number in output) | **yes** |
| `attest`: `MISMATCH` | the claimed value differs from the actual one; both are shown | **yes** (and found different) |
| `attest`: `TESTIMONY` | the claim could not be checked; the reason is a closed type such as `NO_EVENT` or `COMMAND_NOT_ALLOWED` | no: held as the agent's word |
| `events verify`: `status` `OK` / `TAMPERED` | the hash chain of the ledger is intact / was changed | **yes** (about the ledger itself) |
| serve layer 0: `provenance[*].sentence_kind` = `record` | a sentence filled from your documents | yes, it comes from the record |
| serve layer 0: `sentence_kind` = `testimony`, `constructed`, or `mark` = `UNREAD` | a sentence from the LLM or built by Vera | no: held and marked only |
| `quote_check.verdict` = `unanchored` | the cited quote is not found, or the answer's elements are not in it | the quote was looked for and not found |
| `quote_check.verdict` = `conflict` | the quotes disagree about an element | yes (a disagreement was found) |
| `quote_check.verdict` = `anchored` | the quote exists verbatim, the answer's numbers, dates, names and content words appear in it, and negation agrees | **only the quote was checked**; the sentence stays `testimony` (`anchored_testimony`) |

**`anchored` is a mark, not a confirmation that the answer is correct.** Known ways a wrong answer can still be `anchored` are listed in `KNOWN_ISSUES.md` (`docs/FUSION.md` §9.8 in the development tree).

## Measured numbers

One row, one number, always with its denominator and the set it was measured on. Negative and "not measured" results are in the same table. Held-out sets were written by a different model family and kept from the implementers; hidden-bank rows give counts only. Self-made sets are marked as such and are not evidence. Rows for the W14 run1 compare systems that are **not** Vera alone: the plain local LLM, Vera's default mode (the LLM's sentences included) and Vera's strict mode. Vera's default mode (C) and the plain LLM it is built on (A, the same `qwen3.5:4b`) have the same machine-judged results: Vera's default mode adds nothing to, and removes nothing from, the plain LLM's machine-judged correct answers or abstentions [N-30] [N-57] [N-58] [N-59]. A' is a different, larger model and is not what C is built on [N-32].

Two cautions that matter when reading the table. The W14 strict mode asserts nothing, so on the machine judgement it is indistinguishable from a system that always abstains [N-24] [N-25] [N-27] [N-28]. The old yardstick for "sources Vera verified" [N-34] and the new yardstick after T3 [N-36] are **different definitions**; they are listed in two rows and are not to be compared with each other.

The quote-check counts did not change when the checker was tightened in W16-t3b (the fix described under the attack results): on the self-made T3-1 set the checker detected 25 of 30 wrong answers and left 5 marked `anchored` [N-70], moved 0 of 20 correct answers off `anchored` [N-71], and on the saved W14 C run it still marks 140 of 255 rows `anchored` [N-72]. These are marks (held / marked only), not confirmations.

Every number can be recomputed from the cited file at the cited commit: `python tools/readme_numbers_check.py numbers` in the development tree does it and fails on any mismatch.

| id | item | value | denominator | set | source (tree@commit:path) | what Vera did |
|---|---|---|---|---|---|---|
| N-01 | held-out T6: attest verdicts equal the expected ones | 72 | 72 | held-out T6: 72 reports (36 template, 36 JSON; 36 correct claims, 36 false claims) | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | checked against records |
| N-02 | held-out T6: false claims missed | 0 | 36 | the 36 false claims of held-out T6 | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | checked against records |
| N-03 | held-out T6: correct claims flagged by mistake | 0 | 36 | the 36 correct claims of held-out T6 | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | checked against records |
| N-04 | held-out T7: ledger checks equal the expected ones | 40 | 40 | held-out T7: 40 items | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | checked against records |
| N-05 | held-out T2: wrong answers on ask, chat and serve | 0 | 40 | held-out T2: 40 items (20 answerable, 20 unanswerable) | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-06 | held-out T2: ask correct answers | 5 | 40 | held-out T2: 40 items (20 answerable, 20 unanswerable) | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-07 | held-out T2: ask correct abstentions | 19 | 40 | held-out T2: 40 items (20 answerable, 20 unanswerable) | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-08 | held-out T2: serve displayed correct answers (base was 0) | 4 | 40 | held-out T2: 40 items (20 answerable, 20 unanswerable); the base value was 0 | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-09 | held-out T8: outputs for unconfirmed sentences equal the no-layer output | 36 | 36 | 36 unconfirmed sentences of held-out T8 (60 sentences in all) | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-10 | held-out T8: sentences newly read thanks to a human confirmation | 0 | 60 | held-out T8: 60 sentences with gold readings | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-11 | held-out T8: misreads | 0 | 60 | held-out T8: 60 sentences with gold readings | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-12 | held-out T8: sentences the base reader reads | 22 | 60 | held-out T8: 60 sentences | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-13 | held-out T3: marks equal the expected ones | 37 | 40 | held-out T3: 40 items (20 right answers, 20 wrong answers) | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | held / marked only |
| N-14 | held-out T3: wrong answers marked anchored | 0 | 20 | the 20 wrong answers of held-out T3 (40 items) | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | held / marked only |
| N-15 | hidden bank B1: correct answers | 11 | 296 | hidden bank B1: 296 items (reading, placement r9) | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-16 | hidden bank B1: wrong answers | 0 | 296 | hidden bank B1: 296 items (reading, placement r9) | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-17 | hidden bank B2: correct answers | 0 | 286 | hidden bank B2: 286 items (document questions, ask round5) | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-18 | hidden bank B2: wrong answers | 0 | 286 | hidden bank B2: 286 items (document questions, ask round5) | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-19 | full test suite: known failures (same set as the baseline) | 115 | n/a | full test suite; the known failures of the baseline (the total is not stated in the source) | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-20 | self-made 40 reports: false facts caught by Vera's reader (V) | 22 | 22 | the 22 false facts of 40 self-made reports (self-made set: not evidence) | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t6/compare/compare_table.md` | checked against records |
| N-21 | self-made 40 reports: false facts caught by the plain-regex extractor (a) | 22 | 22 | the 22 false facts of 40 self-made reports (self-made set: not evidence) | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t6/compare/compare_table.md` | checked against records |
| N-22 | self-made 40 reports: added detections from Vera's reader (V minus a) | 0 | 22 | the 22 false facts of 40 self-made reports (self-made set) | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t6/compare/compare_table.md` | measurement (not a Vera judgment) |
| N-23 | self-made 40 reports: correct facts the local LLM judge answered 'no' to | 17 | 53 | the 53 correct facts of 40 self-made reports (local LLM judge, self-made set) | `Verantyx-Vera-alpha@ecde332:docs/ATTEST.md` | measurement (not a Vera judgment) |
| N-24 | W14 run1: Vera strict (D) machine-judged correct answers | 0 | 64 | W14 public benchmark v1, run1: 64 answerable questions | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | measurement (not a Vera judgment) |
| N-25 | W14 run1: Vera strict (D) abstentions | 64 | 64 | W14 public benchmark v1, run1: 64 answerable questions | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | measurement (not a Vera judgment) |
| N-26 | W14 run1: Vera strict (D) held back on unanswerable questions | 48 | 48 | W14 public benchmark v1, run1: 48 unanswerable questions | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | measurement (not a Vera judgment) |
| N-27 | W14 run1: always-abstain baseline (Z) machine-judged correct answers | 0 | 64 | W14 public benchmark v1, run1: 64 answerable questions | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | measurement (not a Vera judgment) |
| N-28 | W14 run1: always-abstain baseline (Z) abstentions | 64 | 64 | W14 public benchmark v1, run1: 64 answerable questions | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | measurement (not a Vera judgment) |
| N-29 | W14 run1: always-abstain baseline (Z) held back on unanswerable questions | 48 | 48 | W14 public benchmark v1, run1: 48 unanswerable questions | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | measurement (not a Vera judgment) |
| N-30 | W14 run1: Vera default (C; its LLM is `qwen3.5:4b`) machine-judged correct answers (the LLM's sentences included) | 37 | 64 | W14 public benchmark v1, run1: 64 answerable questions | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | measurement (not a Vera judgment) |
| N-31 | W14 run1: Vera default (C) assertions made by Vera itself on unanswerable questions | 0 | 48 | W14 public benchmark v1, run1: 48 unanswerable questions | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | measurement (not a Vera judgment) |
| N-32 | W14 run1: a different, larger local model alone (A', `qwen3.8` 27B; not the model behind C) machine-judged correct answers | 49 | 64 | W14 public benchmark v1, run1: 64 answerable questions | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | measurement (not a Vera judgment) |
| N-33 | W14 run1: Vera default (C) unanswerable questions where the LLM's text carried the testimony mark | 48 | 48 | W14 public benchmark v1, run1: 48 unanswerable questions | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | held / marked only |
| N-57 | W14 run1: the plain `qwen3.5:4b` LLM alone (A) machine-judged correct answers | 37 | 64 | W14 public benchmark v1, run1: 64 answerable questions | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | measurement (not a Vera judgment) |
| N-58 | W14 run1: the plain `qwen3.5:4b` LLM alone (A) held back on unanswerable questions (machine-judged) | 31 | 48 | W14 public benchmark v1, run1: 48 unanswerable questions | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | measurement (not a Vera judgment) |
| N-59 | W14 run1: Vera default (C) held back on unanswerable questions (machine-judged) | 31 | 48 | W14 public benchmark v1, run1: 48 unanswerable questions | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | measurement (not a Vera judgment) |
| N-34 | W14 run1, old yardstick: rows with a source Vera verified | 0 | 256 | 256 rows of the W14 run1 C system (old yardstick) | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r3/t32_result.txt` | measurement (not a Vera judgment) |
| N-35 | after T3, W14 C rows carrying a quote_check | 255 | 256 | 256 rows of the W14 C system after T3 (saved run of the third round) | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r3/t32_result.txt` | held / marked only |
| N-36 | after T3, W14 C rows with at least one existing quote (new yardstick) | 153 | 256 | 256 rows of the W14 C system after T3 (new yardstick; its definition differs from the old one) | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r3/t32_result.txt` | held / marked only |
| N-37 | after T3, W14 C rows marked anchored (saved run) | 144 | 256 | 256 rows of the W14 C system after T3 (saved run of the third round) | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r3/t32_result.txt` | held / marked only |
| N-38 | after T3, anchored rows whose answer had no checkable element | 31 | 144 | the 144 anchored rows of the saved W14 C run | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r3/t32_result.txt` | held / marked only |
| N-39 | after T3, anchored rows when the saved run is re-checked with the final checker | 140 | 255 | the 255 rows with a quote_check, re-scored with the final checker | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r5/t32_recheck.txt` | held / marked only |
| N-40 | self-made T3-1: wrong answers left marked anchored | 5 | 30 | the 30 wrong answers of the self-made T3-1 set (self-made set: not evidence) | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r5/t31_result.txt` | held / marked only |
| N-41 | W14 human grading (A', A, B, C) | 未測定 (not measured) | n/a | W14 public benchmark v1 (human grading not done) | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | not measured |
| N-42 | strong hosted-LLM baseline | 未測定 (not measured) | n/a | W14 public benchmark v1 (no network) | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | not measured |
| N-43 | rate of wrong answers of serve layer 0 with a real LLM | 未測定 (not measured) | n/a | held-out T3 includes scripted-LLM items | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | not measured |
| N-60 | first attack wave, attest group: broken (tried is the denominator) | 1 | 16 | the 16 attacks tried on the attest group | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-61 | first attack wave, quote-check group: broken | 4 | 11 | the 11 attacks tried on the quote-check group | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-62 | first attack wave, ledger-and-records group: broken | 4 | 17 | the 17 attacks tried on the ledger-and-records group | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-63 | first attack wave, answer-path group: broken | 0 | 4 | the 4 attacks tried on the answer-path group | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-64 | first attack wave, human-confirmation group: broken | 0 | 2 | the 2 attacks tried on the human-confirmation group | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-65 | ledger-and-records group: broken kinds fixed in W16-t7c (denominator: broken) | 3 | 4 | the 4 broken kinds of the ledger-and-records group | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-66 | after the fixes: secret variants redacted | 41 | 41 | the 41 secret variants made by the attacker (rerun after the fixes) | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | measurement (not a Vera judgment) |
| N-67 | after the fixes: attack inputs for quote-check that became unanchored | 3 | 4 | the 4 attack inputs that had broken quote-check (rerun after the fixes) | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | held / marked only |
| N-68 | after the fixes: held-out T6, attest verdicts equal to the expected ones | 72 | 72 | held-out T6: 72 reports | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | checked against records |
| N-69 | after the fixes: held-out T3, marks equal to the expected ones | 37 | 40 | held-out T3: 40 items | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | held / marked only |
| N-70 | after W16-t3b, self-made T3-1: wrong answers left marked anchored | 5 | 30 | the 30 wrong answers of the self-made T3-1 set (self-made set: not evidence) | `Verantyx-Vera-alpha@d1942e2:artifacts/w16-t3b/t31/t31_result.txt` | held / marked only |
| N-71 | after W16-t3b, self-made T3-1: correct answers moved off anchored (false alarms) | 0 | 20 | the 20 correct answers of the self-made T3-1 set (self-made set: not evidence) | `Verantyx-Vera-alpha@d1942e2:artifacts/w16-t3b/t31/t31_result.txt` | held / marked only |
| N-72 | after W16-t3b, W14 C rows: anchored when the saved run is re-checked | 140 | 255 | the 255 rows with a quote_check, re-scored | `Verantyx-Vera-alpha@d1942e2:artifacts/w16-t3b/t32_recheck.txt` | held / marked only |

## Install

Install from a wheel built from the development tree (the release assets and their sha256 are listed in `CHANGELOG.md`; the download URL is filled in after the owner publishes):

```bash
python3.11 -m venv venv
venv/bin/python -m pip install '/path/to/verantyx_vera-0.1.0a1-py3-none-any.whl[ja]'
venv/bin/vera --help
```

The smoke test used before a release builds the wheel, installs it into a fresh virtual environment offline and runs `help`, `read`, `ask` and `serve` (the last one without an LLM). In the development tree:

```bash
VERA_PYTHON=python3.11 bash tools/release/smoke_wheel.sh <output-dir>
```

The coarse placement (a data file the reader uses) is fetched with `vera placement fetch`; the URL is filled in after the owner publishes, for now use a local file:

```bash
vera placement fetch --from file:///path/to/placement.tar --dest <dir>
```

An install that pulls the dependencies from a package index was not tested for this note. **Which of the two distributions ships under `v0.9-preview`** (this wheel, or the older `vera-ja` package in `public_overlay/`) **is decided by the auditor/owner and appended here.**

## Known holes and limits

The full list is in `KNOWN_ISSUES.md`. The main ones: `anchored` does not confirm correctness; Vera's reading adds no detections over a plain extractor in the completion-claim check [N-22]; the base reader reads few sentences [N-12]; the human grading of the W14 benchmark is not done [N-41]; the real-LLM error rate of layer 0 is not measured [N-43]; the full test suite has known environment-related failures [N-19]. The kinds that remain open after the attack are listed in `KNOWN_ISSUES.md` and under the attack results below.

**Attack results.** A model of a different family attacked a copy of the integrated development tree in a first attack wave, using the product only by reading and running it; the record is `docs/AUDIT_2026-10-06.md` in the development tree at `d1942e2`. For each group, the number tried is the denominator and the number that broke is the value. These are counts of the attacker's results, not a Vera judgment, and they are not totalled here.

- attest (a false claim must not become a record): 1 of 16 broke [N-60]. Broken: the exit code of a tampered ledger (`TAMPERED` under `events verify`) was taken as a record. **Fixed** in W16-t6b: attest uses only a ledger that passed the verification, and the CLI has `--ledger-head`.
- quote check (an unchecked answer must not be `anchored`): 4 of 11 broke [N-61]. Broken: a swap of subject and object, a difference of tense, and a composite of two lines were `anchored`; a forged source path matched exactly. **Fixed** in W16-t3b: role particles, tense, support by a single quote, and a source name that differs is shown as `relocated`. A quote under a forged path stays `anchored` when the sentence is in the record (shown as `relocated`); this is disclosed, not fixed.
- ledger and records (hide secrets, detect tampering, record child processes): 4 of 17 broke [N-62]. Broken: full-width characters, URL encoding, base64 and a key split across two fields were not redacted. Of the 4 broken kinds, 3 were **fixed** in W16-t7c, which also checks each variant of a token and redacts the original token whole [N-65]. The key split across two fields is not fixed and is disclosed.
- answer path (`ask`, `serve` and `chat` give the same answer): 0 of 4 broke [N-63]. Human confirmation (a row without a confirmation id has no effect): 0 of 2 broke [N-64].

Checks after the fixes: all 41 of 41 secret variants were redacted [N-66]. Of the 4 attack inputs that had broken the quote check, 3 became `unanchored` and 1 became `relocated`; the 6 control inputs did not change [N-67]. The held-out tests give the same result as before the fixes: attest 72 of 72, with missed false claims 0 and false alarms 0 [N-68]; quote check 37 of 40, with 0 wrong answers marked `anchored` [N-69].

**What the marks mean.** `anchored` is not a proof that an answer is correct. Redaction is not a guarantee that nothing leaks: it is a best effort that errs on the side of redacting too much.

**Kinds that remain open (disclosed, from the audit record).**
- Quote check: a paraphrase that drops the key word; a surface match of a noun and a verb; an answer such as "that is right" when the quote contains the word for "right" (`docs/FUSION.md` §9.8); a forged source path, when the quoted sentence is in the record (`found` is shown as `relocated`).
- Redaction: a key split across two fields; a superposition of variants (full-width characters mixed with URL encoding); `U+2010` and zero-width characters; hexadecimal; base64 wrapped over lines; certain sequences with many delimiters (`docs/RECORDER.md` §15.4, §15.5); and when one token holds a large number of short base64-like runs, the processing time grows with the square of the length (§15.5).
- attest: unless `--ledger-head` is given, a forgery that recomputes every row and the HEAD of the ledger is not detected (a property of the T7 verification).
- `vera run`: a descendant that was born and detached between two samplings is not recorded.

The next attack wave is not scheduled.

The measurement history of earlier snapshots (2026-09-28 to 2026-10-03) was moved, with its wording unchanged, to `EVAL.md` ("History") and `docs/README_LEGACY_d25a73a.md`. It was not recomputed.

## Contents

- `vera_base/` — the `vera-ja` package code of the earlier snapshot; `docs/` — design notes; `EVAL.md` — measurements; `KNOWN_ISSUES.md` — open holes; `docs/README_LEGACY_d25a73a.md` — the previous front page (bot for your documents, chat, usage of `vera-ja`).

## 日本語

# Vera — 日本語で行われる AI エージェントの仕事の、信頼できる記録と判定

*状態: プレビュー（`v0.9-preview`、未公開）。基点: 開発ツリー `Verantyx-Vera-alpha` のコミット `d1942e2`。*

Vera は言語モデルではなく、読む・答える・書くことで LLM と競いません。AI エージェント（や LLM）の隣に置いて、エージェントが言ったこと・したことについて、次の三つをします。

1. **判定する。** エージェントの申告を、記録された事実（ファイルの sha256・収集されたテスト・終了コード・出力の中の数値）と照合し（`RECORD` 記録 / `TESTIMONY` 証言 / `MISMATCH` 食い違い）、LLM が文書から挙げた逐語の引用を文書と照合します（`anchored` 錨あり / `unanchored` 錨なし / `conflict` 食い違い）。
2. **記録する。** エージェントが走らせたことを、追記専用・ハッシュ連鎖の台帳に残します。後から、記録が書き換えられたかどうかを検査できます。
3. **物差しになる。** 測定の道具と公開ベンチマークを出し、否定の結果も肯定の結果と同じ表に載せます。

## しないこと

- LLM より上手に日本語を読むことは **しません**（しようともしません）。基底の読解器は狭く、伏せた試験の文を全体のうち一部しか読みません [N-12]。
- 自分で答えたり書いたりは **しません**。答えを作るのは LLM で、Vera は照合と記録です。LLM 由来の文は証言として示し、Vera の事実としては示しません。
- 一般の日本語の読解は **しません**。読めない文は「未読」の印のまま残り、その文が変えうる答えを止めます。

## 今日できること

以下のコマンドはすべて `ecde332` の木で実際に流したものです。`vera ...` はその木の `python -m verantyx.cli ...`（またはインストールした wheel の `vera` コマンド）の略です。出力は印字されたまま貼ってあり、正規化は次の二つだけです。`attest` の最初の行で `tree=` の後の作業ディレクトリの絶対パスを `.` に置き換える。`events verify` の `head` の十六進の値を `<sha256>` に置き換える。件数・状態・型・終了コードは置き換えません。再生の手順は開発ツリーの `artifacts/w16-t11/examples/replay.sh`（`ecde332` より後に追加）です。例は `ecde332` で流しました。その後 `d1942e2` の製品コードを含む木（統合のコミット `4c2a2e5`）で再生し、正規化した出力が貼った出力と byte 一致することを確かめました（`artifacts/w16-t11/r3.r3.txt`）。

### 完了の申告を照合する: `vera attest <report> --tree <repo>`

エージェントの報告は、何をしたかを言います。`attest` は各申告をファイルと再実行に照らして、**記録**（一致）・**証言**（確かめられない。真とも偽とも言わない）・**食い違い** に分けます。下の報告は、ファイルの sha（正しい）、二つのテストファイル（片方は件数が偽）、`--rerun` が流してよい一覧に無い受入のコマンドを申告しています。

<!-- EXAMPLE a_attest -->
```text
$ vera attest report.md --tree demo --rerun
vera attest  report=report.md  tree=./demo
[V] 申告 4 件: 記録 1 / 証言 2 / 食い違い 1（読み飛ばした形外れの行 0）
  V-1 行6 証言 NO_BASE [changed] - 変更: calc.py(sha256 af626eb7a9c3d865bc4d7d84f96982d7349f4931c403286d23603d85e6552442)。
      記録 MATCH file_sha:calc.py  申告="af626eb7a9c3d865bc4d7d84f96982d7349f4931c403286d23603d85e6552442" 実際="af626eb7a9c3d865bc4d7d84f96982d7349f4931c403286d23603d85e6552442"
      証言 NO_BASE changed:calc.py  申告="changed" 実際=null
  V-2 行7 記録 MATCH [tests_added] - 追加したテスト: tests/test_calc.py の 2 件が通った。
      記録 MATCH test_exists:tests/test_calc.py  申告="exists" 実際="ある"
      記録 MATCH test_count:tests/test_calc.py  申告=2 実際=2
      記録 MATCH test_passed:tests/test_calc.py  申告="passed" 実際=0
  V-3 行8 食い違い COUNT_DIFFERS [tests_added] - 追加したテスト: tests/test_extra.py の 4 件が通った。
      記録 MATCH test_exists:tests/test_extra.py  申告="exists" 実際="ある"
      食い違い COUNT_DIFFERS test_count:tests/test_extra.py  申告=4 実際=1
      記録 MATCH test_passed:tests/test_extra.py  申告="passed" 実際=0
  V-4 行9 証言 COMMAND_NOT_ALLOWED [acceptance] - 受入 A-1: `make deploy` を実行し、終了コード 0。
      証言 COMMAND_NOT_ALLOWED exit:make deploy  申告=0 実際=null
[a] 申告 0 件: 記録 0 / 証言 0 / 食い違い 0（読み飛ばした形外れの行 0）
# exit code: 1
```

食い違いは `COUNT_DIFFERS`（申告は四件、収集は一件）です。二つの証言は `NO_BASE`（`--base` を渡していないので「変更した」は確かめられない）と `COMMAND_NOT_ALLOWED`（閉じた一覧に無いので再実行しない）です。食い違いがあるので終了コードは `1` です。

### エージェントの仕事を台帳に残す: `vera run -- <cmd>` と hook の雛形

`vera run` はコマンドを走らせ、開始と終了を台帳に追記します。`events verify` はハッシュ連鎖を計算し直します。

<!-- EXAMPLE b_run -->
```text
$ vera run --ledger-dir .vera/ledger -- python3 -c "print(2+3)"
5
# exit code: 0
```
<!-- EXAMPLE b_verify -->
```text
$ vera events --ledger-dir .vera/ledger verify
{"head": "<sha256>", "n": 2, "problems": [], "status": "OK"}
# exit code: 0
```

後から台帳の一行を書き換える（ここでは台帳のコピーの二行目の終了コード）と、`verify` が報告し、終了コード `1` で終わります。

<!-- EXAMPLE b_verify_tampered -->
```text
$ vera events --ledger-dir .vera/ledger_tampered verify
{"head": "<sha256>", "n": 2, "problems": [{"line": 2, "type": "SHA_MISMATCH"}], "status": "TAMPERED"}
# exit code: 1
```

`vera hooks print --claude-code --vera-cmd vera` は、持ち主の発言とエージェントのシェルのツール呼び出しを同じ台帳に追記する Claude Code の hook 設定を出します（先頭だけ示します。実際の出力はもっと長い）。

<!-- EXAMPLE b_hooks -->
```text
$ vera hooks print --claude-code --vera-cmd vera
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "vera events add owner_utterance --stdin --from claude-code --ledger-dir \"${CLAUDE_PROJECT_DIR:-.}/.vera/ledger\" || exit 1",
            "timeout": 10
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
```

### 文書への問い: `vera serve`（層 0）

`vera serve --backend ollama --model <model> --document <file>` は、文書をローカルの LLM に渡し、LLM が挙げた **逐語の引用** をその文書と照合します。応答の `vera.quote_check.verdict` は `anchored`・`unanchored`・`conflict` のどれかです。

```text
vera serve --backend ollama --model qwen3.5:4b --document guide.txt --port 11500
```

監査役が開発ツリーでローカルの LLM を使って一度だけ流した記録です（再生: `artifacts/w16-t11/examples/replay_serve.sh`。`guide.txt` の貸出の案内もこの台本が書きます）。LLM の言い回しは回ごとに変わりうるので、byte で再生する例ではありません。応答の最初の行が、確かめたことの範囲を言います（引用した文が記録にあり、答えの数値がその文に現れること。答えの正しさではありません）。

```text
run:      dev 0d4bc6f, 2026-10-06 06:41 +0900, ollama qwen3.5:4b (digest 2a654d98e6fb), one run
question: 一人で何冊まで借りられますか。
reply:
［証言: LLM の答えです。引用した文は記録にあります（確かめたのは、引用の実在と、答えの数値・日付・固有名・内容語が引用に現れることだけで、答えの正しさではありません）］
5冊
（引用の出典: guide.txt:1）
vera.quote_check: verdict anchored; quote guide.txt line 1 found exact; element number 5冊 found in guide.txt:1
```

## 「保持・印付け」と「確かめた」

Vera は次の二つを分けて扱い、出力の型の名前でどちらかが分かります。

| 出力の型 | 意味 | 記録と突き合わせたか |
|---|---|---|
| `attest`: `RECORD` | 申告の値が実際の値（ハッシュ・テストの件数・終了コード・出力の数値）と一致 | **はい** |
| `attest`: `MISMATCH` | 申告の値が実際の値と違う。両方を示す | **はい**（違いが見つかった） |
| `attest`: `TESTIMONY` | 確かめられなかった。理由は `NO_EVENT`・`COMMAND_NOT_ALLOWED` などの閉じた型 | いいえ（エージェントの言葉として保持） |
| `events verify`: `status` が `OK` / `TAMPERED` | 台帳のハッシュ連鎖が無傷 / 書き換えられた | **はい**（台帳そのものについて） |
| serve 層 0: `provenance[*].sentence_kind` が `record` | 文書から埋めた文 | はい（記録に由来） |
| serve 層 0: `sentence_kind` が `testimony`・`constructed`、または `mark` が `UNREAD` | LLM の文、または Vera が構成した文 | いいえ（保持・印付けだけ） |
| `quote_check.verdict` が `unanchored` | 引用が見つからない、または答えの要素が引用に無い | 引用を探して見つからなかった |
| `quote_check.verdict` が `conflict` | 引用どうしが要素について食い違う | はい（食い違いが見つかった） |
| `quote_check.verdict` が `anchored` | 引用が逐語で実在し、答えの数値・日付・固有名・内容語が引用に現れ、否定の有無が合う | **引用だけ確かめた**。文は `testimony` のまま（`anchored_testimony`） |

**`anchored` は印であって、答えが正しいことの確認ではありません。** 誤答が `anchored` になりうる既知の形は `KNOWN_ISSUES.md`（開発ツリーでは `docs/FUSION.md` §9.8）にあります。

## 測った数値

一行一数値で、必ず分母と測った集合を添えます。否定の結果と「未測定」も同じ表に入れます。伏せた試験は別系統のモデルが書いて実装役には見せなかった集合で、隠しバンクの行は件数だけです。自作の集合はその旨を書き、証拠にはなりません。W14 run1 の行は Vera 単独ではなく、ローカルの LLM 単体・Vera 既定（LLM の文を含む）・Vera の strict を比べたものです。Vera 既定（C）と、その土台と同じ `qwen3.5:4b` の LLM 単体（A）は、機械判定の結果が同じです。Vera 既定は、LLM 単体の機械判定の正答も棄権も増やさず、減らしもしません [N-30] [N-57] [N-58] [N-59]。A' は別の大きいモデルで、C の土台ではありません [N-32]。

表の読み方で大事な注意が二つあります。W14 の strict は何も断定しないので、機械判定では「常に棄権」と区別できません [N-24] [N-25] [N-27] [N-28]。「Vera が確かめた出典」の旧の物差し [N-34] と T3 の後の新の物差し [N-36] は **定義が違います**。二行に分けてあり、互いに比べてはいけません。

引用の照合の数は、W16-t3b で照合器を締めた後（直した内容は攻撃の結果の節）も変わりません。自作の集合 T3-1 では、誤答 30 件のうち 25 件を検出し、5 件が `anchored` のまま残りました [N-70]。正しい答え 20 件のうち、`anchored` 以外にしたものは 0 件でした [N-71]。W14 の C 系の保存結果では、255 行のうち 140 行が今も `anchored` です [N-72]。これらは印付けであって、確認ではありません（保持・印付けだけ）。

どの数値も、引用したコミットの引用したファイルから再計算できます。開発ツリーで `python tools/readme_numbers_check.py numbers` を流すと再計算し、一件でも合わなければ失敗します。

| id | 項目 | 値 | 分母 | 集合 | 出所（木@commit:パス） | Vera がしたこと |
|---|---|---|---|---|---|---|
| N-01 | 伏せた試験 T6: attest の判定が期待と一致 | 72 | 72 | 伏せた試験 T6（72 件: 定型文 36・JSON 36、正しい申告 36・偽の申告 36） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 記録と突き合わせて確かめた |
| N-02 | 伏せた試験 T6: 偽の申告の見逃し | 0 | 36 | 伏せた試験 T6 の偽の申告 36 件 | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 記録と突き合わせて確かめた |
| N-03 | 伏せた試験 T6: 正しい申告の誤検出 | 0 | 36 | 伏せた試験 T6 の正しい申告 36 件 | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 記録と突き合わせて確かめた |
| N-04 | 伏せた試験 T7: 記録の判定が期待と一致 | 40 | 40 | 伏せた試験 T7（40 件） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 記録と突き合わせて確かめた |
| N-05 | 伏せた試験 T2: ask・chat・serve の誤答 | 0 | 40 | 伏せた試験 T2（40 件: 答えあり 20・答えなし 20） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-06 | 伏せた試験 T2: ask の正答 | 5 | 40 | 伏せた試験 T2（40 件: 答えあり 20・答えなし 20） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-07 | 伏せた試験 T2: ask の正しい棄権 | 19 | 40 | 伏せた試験 T2（40 件: 答えあり 20・答えなし 20） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-08 | 伏せた試験 T2: serve が表示した正答（基点は 0） | 4 | 40 | 伏せた試験 T2（40 件: 答えあり 20・答えなし 20） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-09 | 伏せた試験 T8: 確認の無い文の出力が層なしと一致 | 36 | 36 | 伏せた試験 T8 の確認の無い文 36 文（全 60 文のうち） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-10 | 伏せた試験 T8: 人の確認で新しく読めた文 | 0 | 60 | 伏せた試験 T8（60 文、正解の読みつき） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-11 | 伏せた試験 T8: 誤読 | 0 | 60 | 伏せた試験 T8（60 文、正解の読みつき） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-12 | 伏せた試験 T8: 基底の読解器が読む文 | 22 | 60 | 伏せた試験 T8（60 文） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-13 | 伏せた試験 T3: 期待どおりの印 | 37 | 40 | 伏せた試験 T3（40 件: 正答 20・誤答 20） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 保持・印付けだけ |
| N-14 | 伏せた試験 T3: 誤答のうち錨ありと印が付いたもの | 0 | 20 | 伏せた試験 T3 の誤答 20 件 | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 保持・印付けだけ |
| N-15 | 隠しバンク B1: 正答 | 11 | 296 | 隠しバンク B1（読解、配置 r9、296 件） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-16 | 隠しバンク B1: 誤答 | 0 | 296 | 隠しバンク B1（読解、配置 r9、296 件） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-17 | 隠しバンク B2: 正答 | 0 | 286 | 隠しバンク B2（文書の問い、ask round5、286 件） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-18 | 隠しバンク B2: 誤答 | 0 | 286 | 隠しバンク B2（文書の問い、ask round5、286 件） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-19 | 全体テストの既知の失敗（基線と同じ集合） | 115 | n/a | 全体テスト（総数は出所に無い。環境に由来する既知の失敗の一覧） | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-20 | 自作 40 件の完了申告: Vera の読みが偽の事実を検出 | 22 | 22 | 自作 40 件の偽の事実 22 件（自作の集合。証拠にならない） | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t6/compare/compare_table.md` | 記録と突き合わせて確かめた |
| N-21 | 自作 40 件の完了申告: JSON・正規表現の抽出器 a が偽の事実を検出 | 22 | 22 | 自作 40 件の偽の事実 22 件（自作の集合。証拠にならない） | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t6/compare/compare_table.md` | 記録と突き合わせて確かめた |
| N-22 | 自作 40 件の完了申告: Vera の読みの上乗せ（V − a の件数） | 0 | 22 | 自作 40 件の偽の事実 22 件（自作の集合） | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t6/compare/compare_table.md` | 測定の結果（Vera の判定ではない） |
| N-23 | 自作 40 件の完了申告: LLM 判定器 c が正しい事実に「いいえ」を返した | 17 | 53 | 自作 40 件の正しい事実 53 件（qwen 系ローカルモデル。自作の集合） | `Verantyx-Vera-alpha@ecde332:docs/ATTEST.md` | 測定の結果（Vera の判定ではない） |
| N-24 | W14 run1: D（Vera strict）の機械判定の正答 | 0 | 64 | W14 公開ベンチマーク v1 run1、答えのある問い 64 問 | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 測定の結果（Vera の判定ではない） |
| N-25 | W14 run1: D（Vera strict）の棄権 | 64 | 64 | W14 公開ベンチマーク v1 run1、答えのある問い 64 問 | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 測定の結果（Vera の判定ではない） |
| N-26 | W14 run1: D の答えの無い問いで止めた数 | 48 | 48 | W14 公開ベンチマーク v1 run1、答えの無い問い 48 問 | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 測定の結果（Vera の判定ではない） |
| N-27 | W14 run1: Z（常に棄権）の機械判定の正答 | 0 | 64 | W14 公開ベンチマーク v1 run1、答えのある問い 64 問 | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 測定の結果（Vera の判定ではない） |
| N-28 | W14 run1: Z の棄権 | 64 | 64 | W14 公開ベンチマーク v1 run1、答えのある問い 64 問 | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 測定の結果（Vera の判定ではない） |
| N-29 | W14 run1: Z の答えの無い問いで止めた数 | 48 | 48 | W14 公開ベンチマーク v1 run1、答えの無い問い 48 問 | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 測定の結果（Vera の判定ではない） |
| N-30 | W14 run1: C（Vera 既定、LLM は `qwen3.5:4b`）の機械判定の正答（LLM の文を含む） | 37 | 64 | W14 公開ベンチマーク v1 run1、答えのある問い 64 問 | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 測定の結果（Vera の判定ではない） |
| N-31 | W14 run1: C の答えの無い問いで Vera 自身が断定した数 | 0 | 48 | W14 公開ベンチマーク v1 run1、答えの無い問い 48 問 | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 測定の結果（Vera の判定ではない） |
| N-32 | W14 run1: C とは別の大きいローカルモデル単体（A'、`qwen3.8` 27B）の機械判定の正答 | 49 | 64 | W14 公開ベンチマーク v1 run1、答えのある問い 64 問 | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 測定の結果（Vera の判定ではない） |
| N-33 | W14 run1: C の答えの無い問いで LLM の文に証言の印が付いた | 48 | 48 | W14 公開ベンチマーク v1 run1、答えの無い問い 48 問 | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 保持・印付けだけ |
| N-57 | W14 run1: A（`qwen3.5:4b` の LLM 単体）の機械判定の正答 | 37 | 64 | W14 公開ベンチマーク v1 run1、答えのある問い 64 問 | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 測定の結果（Vera の判定ではない） |
| N-58 | W14 run1: A の答えの無い問いで止めた数（機械判定） | 31 | 48 | W14 公開ベンチマーク v1 run1、答えの無い問い 48 問 | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 測定の結果（Vera の判定ではない） |
| N-59 | W14 run1: C（Vera 既定）の答えの無い問いで止めた数（機械判定） | 31 | 48 | W14 公開ベンチマーク v1 run1、答えの無い問い 48 問 | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 測定の結果（Vera の判定ではない） |
| N-34 | W14 run1 の旧の物差しで Vera が確かめた出典のある行 | 0 | 256 | W14 run1 の C 系 256 行（旧の物差し） | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r3/t32_result.txt` | 測定の結果（Vera の判定ではない） |
| N-35 | T3 の後の W14 C 系: quote_check のある行 | 255 | 256 | W14 の C 系 256 行（T3 の後、第三ラウンドの保存結果） | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r3/t32_result.txt` | 保持・印付けだけ |
| N-36 | T3 の後の W14 C 系: 新の物差しで実在の引用（exact・relocated）の位置のある行 | 153 | 256 | W14 の C 系 256 行（T3 の後。新の物差し。旧の物差しとは定義が違う） | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r3/t32_result.txt` | 保持・印付けだけ |
| N-37 | T3 の後の W14 C 系: 錨ありの印（保存結果） | 144 | 256 | W14 の C 系 256 行（T3 の後、第三ラウンドの保存結果） | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r3/t32_result.txt` | 保持・印付けだけ |
| N-38 | T3 の後の W14 C 系: 錨ありのうち答えの要素が無いの行 | 31 | 144 | W14 C 系の錨あり 144 行（保存結果） | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r3/t32_result.txt` | 保持・印付けだけ |
| N-39 | T3 の後の W14 C 系: 最終の照合器で保存結果を再評価した錨あり | 140 | 255 | quote_check のある 255 行（最終の照合器で再評価） | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r5/t32_recheck.txt` | 保持・印付けだけ |
| N-40 | 自作の集合 T3-1: 誤答のうち錨ありのまま見逃したもの | 5 | 30 | 自作の集合 T3-1 の誤答 30 件（自作。証拠にならない） | `Verantyx-Vera-alpha@ecde332:artifacts/w16-t3/r5/t31_result.txt` | 保持・印付けだけ |
| N-41 | W14 の人の採点（A'・A・B・C） | 未測定 | n/a | W14 公開ベンチマーク v1（人の採点は未了） | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 未測定 |
| N-42 | API の強い LLM（A'）の測定 | 未測定 | n/a | W14 公開ベンチマーク v1（ネットワーク不可） | `Verantyx-Vera-alpha@ecde332:docs/BENCHMARK_PUBLIC.md` | 未測定 |
| N-43 | serve 層 0 を本物の LLM で通した誤答率 | 未測定 | n/a | 伏せた試験 T3 は偽の LLM の項目を含む | `Verantyx-Vera-alpha@ecde332:docs/AUDIT_2026-10-06.md` | 未測定 |
| N-60 | 攻撃の最初の波: attest群で破れた数 | 1 | 16 | 攻撃の最初の波の「attest」群で試した 16 件 | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-61 | 攻撃の最初の波: 引用の照合群で破れた数 | 4 | 11 | 攻撃の最初の波の「引用の照合」群で試した 11 件 | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-62 | 攻撃の最初の波: 台帳と記録群で破れた数 | 4 | 17 | 攻撃の最初の波の「台帳と記録」群で試した 17 件 | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-63 | 攻撃の最初の波: 回答経路群で破れた数 | 0 | 4 | 攻撃の最初の波の「回答経路」群で試した 4 件 | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-64 | 攻撃の最初の波: 人の確認群で破れた数 | 0 | 2 | 攻撃の最初の波の「人の確認」群で試した 2 件 | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-65 | 台帳と記録群: 破れた型のうち直した数（W16-t7c） | 3 | 4 | 攻撃の最初の波の台帳と記録群で破れた 4 件の型 | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-66 | 修正の後: 伏せの変種のうち伏せた数 | 41 | 41 | 攻撃側が作った伏せの変種 41 件（修正の後に再実行） | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | 測定の結果（Vera の判定ではない） |
| N-67 | 修正の後: 引用の照合の攻撃入力のうち錨なしになった数 | 3 | 4 | 攻撃で破れた引用の照合の 4 件の入力（再実行） | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | 保持・印付けだけ |
| N-68 | 修正の後: 伏せた試験 T6 の attest の判定が期待と一致 | 72 | 72 | 伏せた試験 T6 の attest 72 件 | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | 記録と突き合わせて確かめた |
| N-69 | 修正の後: 伏せた試験 T3 の期待どおりの印 | 37 | 40 | 伏せた試験 T3 の引用の照合 40 件 | `Verantyx-Vera-alpha@d1942e2:docs/AUDIT_2026-10-06.md` | 保持・印付けだけ |
| N-70 | W16-t3b の後の自作 T3-1: 誤答のうち錨ありのまま見逃したもの | 5 | 30 | 自作の集合 T3-1 の誤答 30 件（自作。証拠にならない） | `Verantyx-Vera-alpha@d1942e2:artifacts/w16-t3b/t31/t31_result.txt` | 保持・印付けだけ |
| N-71 | W16-t3b の後の自作 T3-1: 正しい答えを錨あり以外にした数（誤検出） | 0 | 20 | 自作の集合 T3-1 の正しい答え 20 件（自作。証拠にならない） | `Verantyx-Vera-alpha@d1942e2:artifacts/w16-t3b/t31/t31_result.txt` | 保持・印付けだけ |
| N-72 | W16-t3b の後の W14 C 系: 保存結果を再評価した錨あり | 140 | 255 | quote_check のある 255 行（再評価） | `Verantyx-Vera-alpha@d1942e2:artifacts/w16-t3b/t32_recheck.txt` | 保持・印付けだけ |

## 入れ方

開発ツリーから作った wheel を入れます（リリース資産とその sha256 は `CHANGELOG.md` に一覧があります。ダウンロードの URL はオーナーの公開の後に埋めます）。

```bash
python3.11 -m venv venv
venv/bin/python -m pip install '/path/to/verantyx_vera-0.1.0a1-py3-none-any.whl[ja]'
venv/bin/vera --help
```

リリースの前に使う煙試験は、wheel を作り、新しい仮想環境にオフラインで入れて、`help`・`read`・`ask`・`serve`（最後だけ LLM なし）を流します。開発ツリーで:

```bash
VERA_PYTHON=python3.11 bash tools/release/smoke_wheel.sh <output-dir>
```

粗い配置（読解器が使うデータ）は `vera placement fetch` で取ります。URL はオーナーの公開の後に埋めます。いまはローカルのファイルを使います。

```bash
vera placement fetch --from file:///path/to/placement.tar --dest <dir>
```

パッケージの索引から依存を入れる入れ方は、この文書のためには試していません。**`v0.9-preview` でどちらの配布物を出すか**（この wheel か、`public_overlay/` の古い `vera-ja`）**は監査役・オーナーが決め、ここに追記します。**

## 既知の穴と限界

全体は `KNOWN_ISSUES.md` にあります。主なもの: `anchored` は正しさの確認ではない。完了申告の照合で Vera の読みは単純な抽出器に検出を足さない [N-22]。基底の読解器が読む文は少ない [N-12]。W14 ベンチマークの人の採点は未了 [N-41]。層 0 の本物の LLM での誤答率は未測定 [N-43]。全体テストには環境に由来する既知の失敗がある [N-19]。攻撃の後に残る型は `KNOWN_ISSUES.md` と下の「攻撃の結果」にあります。

**攻撃の結果。** 別系統のモデルが、統合済みの開発ツリーの写しを、製品の読み取りと実行だけで攻めました（最初の攻撃の波）。記録は開発ツリーの `docs/AUDIT_2026-10-06.md`（`d1942e2`）にあります。群ごとに、試した数が分母、破れた数が値です。これは攻撃側の結果の数えであって Vera の判定ではなく、ここでは合計しません。

- attest（偽の申告を記録にしない）: 16 件のうち 1 件が破れました [N-60]。破れた型: 改ざんされた台帳（`events verify` で `TAMPERED`）の終了コードが記録になりました。W16-t6b で**直しました**: attest は検証を通った台帳だけを使い、CLI に `--ledger-head` があります。
- 引用の照合（確かめていない答えを `anchored` にしない）: 11 件のうち 4 件が破れました [N-61]。破れた型: 主体と対象の逆転、時制の違い、二行の合成が `anchored` になり、出典のパスの偽装が完全一致になりました。W16-t3b で**直しました**: 役割の助詞・時制・一つの引用で支えること・出典の名前が違えば `relocated`。偽装したパスの引用は、文が記録にあれば `anchored` のまま残ります（`relocated` と表示）。これは直さず開示します。
- 台帳と記録（秘密を伏せる、改ざんを検出する、子プロセスを記録する）: 17 件のうち 4 件が破れました [N-62]。破れた型: 全角・URL エンコード・base64・二つの欄に分けた鍵が伏せられませんでした。破れた 4 つの型のうち 3 つを W16-t7c で**直しました**（各トークンの変形も照合し、元のトークンごと伏せる）[N-65]。二つの欄に分けた鍵は直さず開示します。
- 回答経路（`ask`・`serve`・`chat` が同じ答え）: 4 件のうち 0 件が破れました [N-63]。人の確認（確認 id の無い行は効かない）: 2 件のうち 0 件が破れました [N-64]。

修正の後の確かめ: 伏せの変種は 41/41 を伏せました [N-66]。引用の照合を破った攻撃の入力 4 件は、3 件が `unanchored`、1 件が `relocated` になり、対照の 6 件は変わりませんでした [N-67]。伏せた試験の結果は修正の前と同じです。attest は 72/72（偽の申告の見逃し 0・誤検出 0）[N-68]、引用の照合は 37/40（誤答で `anchored` になったもの 0）[N-69]。

**印の意味。** `anchored` は答えが正しいことの証明ではありません。伏せは、何も漏れない保証ではありません。過剰に伏せる側に倒す最善の努力です。

**残る型（開示。監査役の記録から）。**
- 引用の照合: 要の語を落とした言い直し。名詞と動詞の表層の一致。「その通り」で引用に「通り」がある場合（開発ツリーの `docs/FUSION.md` §9.8）。偽装したパスでも、引用の文が記録にあれば `anchored`（`found` は `relocated` と表示）。
- 伏せ: 二つの欄に分けた鍵。変形の重ね合わせ（全角と URL エンコードの混在など）。`U+2010` とゼロ幅の字。十六進。改行で折り返した base64。区切り字が多い特定の並び（`docs/RECORDER.md` §15.4・§15.5）。一つのトークンに短い base64 らしい列が大量にあると、処理の時間が長さの二乗に伸びます（§15.5）。
- attest: `--ledger-head` を渡さないと、台帳の全行と HEAD を計算し直した偽造は検出できません（T7 の検証の性質）。
- `vera run`: 標本化の間に生まれて切り離された子孫は記録しません。

次の攻撃の波は未定です。

以前の版（2026-09-28〜2026-10-03）の測定の履歴は、文面を変えずに `EVAL.md`（「History」）と `docs/README_LEGACY_d25a73a.md` に移しました。再計算はしていません。

## 内容

- `vera_base/` — 以前の版の `vera-ja` パッケージのコード。`docs/` — 設計メモ。`EVAL.md` — 測定。`KNOWN_ISSUES.md` — 未解決の穴。`docs/README_LEGACY_d25a73a.md` — 以前の表紙（文書のボット・チャット・`vera-ja` の使い方）。
