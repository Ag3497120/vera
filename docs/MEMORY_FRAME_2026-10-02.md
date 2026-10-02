# Typed project memory (prototype, 2026-10-02)

Isolated work copy only (`verantyx/memory_frame.py`, `tests/test_memory_frame.py`, `tools/memory_frame_demo.py`); not applied to the original repo.

## Why
Measured on the real session notes (181 prose entries in vera-1): only 25% of the clauses the semantic reader found were supported (573 clauses, 297 unread spans) and 6/6 questions asked back were refused.
A note can be perfectly clear to a person and still not be something Vera can answer from. The memory therefore has to be typed WHEN IT IS WRITTEN.

## Write-time gates (`Memory.write`)
1. Kind and slots are closed: FACT(subject, attribute, value), DECISION, INVARIANT, TASK(state in 未着手/進行中/完了/停止/保留), LESSON, QUESTION. Missing/extra slots are rejected.
2. FACT and INVARIANT need a witness that can be re-checked later (`file_sha256`, `text_in_file`, `git_commit`) or an explicit `testimony`. Stale witnesses drop a record from answers (it stays in the log).
3. The entity and attribute slots are bare compound nouns: particles and の are dropped (`未読の上限` -> `未読上限`), the original is kept in `normalized`.
4. Askability round trip: the record's canonical sentence must be read back by the semantic reader into one supported property clause with the same value. Values must be noun phrases; a verb-phrase value is rejected with a hint.
5. Append-only: a record is superseded by a newer one, never deleted; two active records that disagree are a typed non-answer, not a pick.

## Out-of-frame words (`Resolver`)
A word that is not in the frame (a state, a kind) is shown to a model with the CLOSED list of canonical expressions and asked which one it is closest to (or none). The reply must be an index in range (anything else is invalid).
Two independent asks (different wording, shuffled order) must name the same expression; only then an alias is stored, as TESTIMONY with both asks. The model cannot add a canonical term. Live check (gpt-6-luna, low, Standard):
`ブロック中 -> 保留` and `もうすぐ終わる -> 進行中`, both asks agreeing. The mapping is a model's judgment, kept as testimony and reusable without asking again.

## Measured (demo, 27 typed records written from this session's real facts, with witnesses where a file or text could be pointed to)
- 27 written, 0 rejected after normalization and noun-phrase values; 23/23 questions answered correctly with the record id cited; 3 questions with no record all refused; 12 FRESH witnesses, 4 testimonies.
- Caveat: the questions use the canonical slot forms (`ask_about`), so this measures that typed records are askable, not free-form question understanding. Each ask rebuilds the view (about 5 ms); the leaf router applies from 7 records.

## Not done
Witness re-validation on every read, a budgeted brief compiler (the text actually given to a model), a lesson index keyed by tool/situation, multi-writer reconciliation (author/time precedence), a resume-fidelity benchmark
(drop the context, rebuild from the store, redo a task), and the writer that turns a model's work into typed records automatically. The model still decides WHAT to write; the gate only guarantees that what is written can be asked.
