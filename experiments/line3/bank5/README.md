# Bank 5 — multi-session work memory (audited)

6 fictional work projects (MEM-T01..T06: inventory-app release, town film festival, joint culture experiment, warehouse app 3.2
release, disaster-prevention forum, city-archive photo migration), each told as **3 sessions** of Japanese messages (8 / 8 / 10)
that an assistant receives one by one, followed by **10 questions** about facts from sessions 1–2. Authored by codex gpt-6-luna
(brief `vera-impl/bank2-author/PROMPT5.md`; it never saw Vera code), audited by Claude Opus 5.5 on 2026-10-13 (`AUDIT5.md`).
**No Vera system has read this bank before intake** (sha256 in `MANIFEST.json`).

## Files

- `bank5.jsonl` — the audited bank, one task per line.
- `check5.py` / `check5.txt` — the audited mechanical checker and its output (PASS). `python check5.py [path]`.
- `AUDIT5.md` — rules, counts, findings, fact-form shares, per-item decisions, every fix old → new.
- `MANIFEST.json` — sha256 of the author's original and of the audited bank, author files, provenance.

## Schema

```
{id, title,
 sessions: [[{speaker, text}, ...] x 3],
 plants:    [{kind, fact, values, message_refs: [[s, i], ...], note}],   # kind: contradiction | update | list_trap | repeat | reversal
 questions: [{q, gold, kind, refs: [[s, i], ...]}]}                      # kind: contradiction | update | plain
```

Refs are `[session, message]`, both **0-based**. `plants` and `questions[].gold/kind/refs` are the key — never show them to the system
under test; feed only `sessions` (message by message, session by session) and then `questions[].q`.

Per task: 6 contradictions (3 within a session, 2 in adjacent sessions, 1 between sessions 1 and 3), 3 updates, 4 list traps, 2 repeats,
2 reversals (both in session 3); questions: 4 contradiction, 3 update, 3 plain, all about sessions 1–2 and none restated in session 3.

## Grading

- contradiction: gold `矛盾: X と Y` (X, Y in message order). Accept either order; the answer must give both values and mark the conflict.
  Answering one value alone is wrong.
- update: gold = the latest value. Answering the old value, or `矛盾: old と new`, is wrong (the change carries an explicit marker).
- plain: gold = the value.
- Plants that no question asks (the 2 contradictions involving session 3, reversals, list traps, repeats) are for intake-time
  metering: flag a contradiction/reversal, do NOT flag list traps or repeats.

## Caveats (see AUDIT5.md)

- Questions are neutral (they do not say that a fact was contradicted or changed); this is deliberate.
- Updates are self-contained: the old value appears only inside the 「AからBに変更」 sentence, never as an earlier stored fact.
- All tasks share one positional template and one question order: shuffle question order and run one task per context.
- Fact forms were NOT normalised: ~22 % of facts (18 % of questioned statements) are 「XのYはA」; ~60 % are fused slot statements
  (「認証モジュール担当は田中です」); every update is a change sentence. Splitting X and Y is the model's job.
