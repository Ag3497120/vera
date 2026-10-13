# Audit of the long-story banks (bank_ls)

Auditor: Claude (Sonnet 5.5), 2026-10-13. This file reports **counts and outcomes only** for `heldout_1` and `heldout_2` (design 6.6: the designer and implementer of a
revision do not read the judging stories or their questions); story-level detail is given for `dev/` only.

## What was checked, and how

1. **Mechanical** (`check_ls.py`, `check_dev.txt`, `check_heldout_1.txt`, `check_heldout_2.txt`: all **PASS, 0 errors**; `check_cross.txt`: PASS). Per story: sessions 10-20, messages
   per session 8-25, 600-1000 sentences (split after 「。」, every message ends in 「。」); plant counts exactly 12 contradictions / 8 updates / 8 list traps / 6 repeats / 4 reversals;
   contradiction value i in message i with no update/scope marker in its sentence; update = one message `old から new` + a change marker, old value stated earlier (`old_refs`),
   new value not stated before; reversal = the same pair both ways, one direction per message; repeat = one identical sentence in >= 2 sessions with every occurrence listed;
   completion of >= 3/6/9/12 contradictions and 2/4/6/8 updates by the four checkpoints; checkpoints at `ceil(n*f)-1`; 40 questions, exactly 3 plain / 3 contradiction /
   2 update / 2 absent per checkpoint; every question ends in ？, announces no kind, holds no gold value, has refs inside the sessions fed so far; contradiction and update questions
   tie to the plant on the same refs (gold form `矛盾: X と Y` / the new value) and every such plant is asked exactly once; plain golds are not contradicted/updated values and
   >= 4 per story concern list-trap facts; absent: gold `記録なし`, no refs, subject_refs resolve, `absent_terms` have 0 hits in the story; phrasing: `stored_slot` in the refs,
   `same` => in the question, `rephrased` => not in the question and `asked_slot` in the question but in no referenced message, >= 4 rephrased per checkpoint and >= half overall;
   ledger values in their messages, no ledger slot with two values unless it is a planted contradiction/update/reversal slot; author-flagged subject-less sentences >= 30 %.
   (`check_ls.py` is the auditor's checker, stricter than the authors' own; the authors' own checks passed first and are kept in the author directories.)
2. **Cross-split** (`check_ls.py --cross dev heldout_1 heldout_2`): no sentence of >= 8 characters shared between any two stories (0 of 9,371), no question shared (0 of 560), no
   title or speaker shared, largest shared-14-gram share between two stories 0.07 %. Topics were assigned distinct in the briefs.
3. **Independent reader** (`PROMPT_LSAUDIT.md`, codex gpt-6-luna, effort high, one run per story, sees the log without plants): its findings were compared with the plants by refs.
4. **Auditor's lint**: sentences of the form `X は Y` grouped by X, flagging X with different Y outside the plants (found one real case, below), and absent questions checked for
   a sentence that holds all their content words except the asked one (all flagged cases were the intended near-miss, subject present and asked fact missing).
5. **Loader**: `mem_run.py --validate --bank <split>/stories.jsonl` is ok for all 14 stories.

## Per story (counts only)

| split | story | sessions | messages | sentences | subject-less (author flag) | rephrased / non-absent | plain Qs on trap facts | reader found: contradictions / 12 | updates / 8 | reversals / 4 | reader: unplanted contradictions | extra updates | extra repeats |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dev | LS-D01 | 16 | 160 | 640 | 59 % | 26/32 | 8 | 11 | 8 | 4 | 0 | 0 | 0 |
| dev | LS-D02 | 14 | 115 | 805 | 43 % | 32/32 | 4 | 9 | 8 | 4 | 1 | 0 | 0 |
| heldout_1 | LS-H1-01 | 12 | 96 | 768 | 37 % | 20/32 | 8 | 12 | 8 | 4 | 0 | 0 | 0 |
| heldout_1 | LS-H1-02 | 12 | 120 | 840 | 43 % | 32/32 | 8 | 12 | 8 | 4 | 0 | 0 | 0 |
| heldout_1 | LS-H1-03 | 12 | 144 | 720 | 66 % | 32/32 | 8 | 11 | 8 | 4 | 0 | 0 | 0 |
| heldout_1 | LS-H1-04 | 16 | 128 | 736 | 33 % | 25/32 | 8 | 12 | 8 | 3 | 0 | 0 | 1 |
| heldout_1 | LS-H1-05 | 12 | 144 | 720 | 40 % | 32/32 | 4 | 12 | 8 | 4 | 0 | 0 | 0 |
| heldout_1 | LS-H1-06 | 10 | 100 | 600 | 73 % | 21/32 | 8 | 11 | 8 | 4 | 0 | 0 | 0 |
| heldout_2 | LS-H2-01 | 13 | 130 | 650 | 68 % | 29/32 | 6 | 11 | 8 | 4 | 0 | 0 | 0 |
| heldout_2 | LS-H2-02 | 12 | 120 | 600 | 37 % | 23/32 | 4 | 11 | 8 | 4 | 0 | 0 | 0 |
| heldout_2 | LS-H2-03 | 12 | 96 | 600 | 32 % | 23/32 | 10 | 12 | 8 | 4 | 0 | 2 | 0 |
| heldout_2 | LS-H2-04 | 12 | 120 | 600 | 60 % | 23/32 | 8 | 12 | 8 | 4 | 0 | 0 | 0 |
| heldout_2 | LS-H2-05 | 12 | 120 | 600 | 42 % | 32/32 | 4 | 9 | 8 | 4 | 0 | 0 | 0 |
| heldout_2 | LS-H2-06 | 12 | 97 | 679 | 41 % | 25/32 | 6 | 12 | 8 | 4 | 0 | 0 | 0 |

"reader found" = how many planted contradictions / updates / reversals the independent reader reported (by refs). Planted contradictions it missed are either misses of the reader
(dev: a venue stated two ways in sessions 8 and 11) or deliberately loose surface forms (dev: 「配布台数36台」 vs 「準備数40台」); the reader's recall of the planted contradictions is
9-12 of 12, so its "unplanted" count is a lower bound on what could exist, not a proof. "unplanted contradictions" = reader pairs not matching any planted contradiction: LS-D02 has 1
(a false positive: two different slots, 先行試作の工房出荷日 and 基板の試作受取日). "extra updates" in LS-H2-03 are two `moved` statements without an old value (not updates);
"extra repeat" in LS-H1-04 is one sentence stated twice verbatim without being a planted repeat (harmless, consistent). The reader found 3 of the 4 reversals in LS-H1-04.

## Defects found and what was done

| story | defect | action |
|---|---|---|
| LS-H2-04 (first attempt) | 404 of 735 sentences were repeats of a pool of generic filler sentences | rejected, regenerated with a no-repeat rule; the new story has 6 duplicate sentences = the 6 planted repeats |
| LS-H2-01 | 3 unplanted inconsistencies found by the auditor's lint and the reader: one slot stated two ways, one implicit change of a value without a marker, one unplanted repeat of a dependency sentence | repaired by the author (generator source), re-checked (PASS), re-read by the independent reader: 0 left |
| LS-H2-03 | 1 unplanted conflict (one slot stated two ways) | repaired by the author, re-checked, re-read: 0 left |
| LS-H1-01, H1-04, H2-02, H2-06 | author run died with an API stream disconnect | rerun from scratch (H1-04: resumed from the second dead attempt) |
| (all) | `refs` of absent questions: repeated `subject_refs` or missing | normalised to [] by `package_ls.py` (counted in the MANIFEST per story) |

No item was dropped from a kept story: the questions and plants of the stories as kept are the authors' (after the repairs above).

## Deviations from the specification

1. **Splits**: 2 dev + 6 + 6 stories (coordinator's change of 2026-10-13), instead of 6 stories in one bank.
2. **Sessions per story 10-16** (spec 10-20), **messages 96-160**, sentences 600-840 (spec 600-1000): within range.
3. **Style**: generator-built stories; near-constant sentences per message; filler sentences with odd concrete detail (it is a work-log style, not natural prose throughout). Reader-style
   naturalness was not scored.
4. **New keys**: `checkpoints`, `checkpoint`, `form`, `stored_slot`, `asked_slot`, `old_refs`, `subject_refs`, `absent_terms`, `ledger`, `subjectless_refs`; question kind `absent`.
5. **Ledger incomplete** (97-353 entries per story) and the **subject-less share is the author's flag**: a crude proxy (no は / が / も in the sentence) gives 25-77 % per story (the lowest, one story of heldout_1, 25 %).
6. **Answer forms of look-alike facts**: a list_trap's two facts may share one value (one plant in heldout_2); its plain questions are scored on the value asked about.
7. **Not measured**: whether any Vera system can answer the questions; whether the rephrased questions are answerable by a plain grep (the `stored_slot` / `asked_slot` rule only guarantees
   lexical difference from the stored slot phrase).
