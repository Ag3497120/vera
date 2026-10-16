# Pre-registration — memory meter v2 on held-out set heldout_1 (written BEFORE opening it)

Date 2026-10-16. Owner decisions: end of ops/decisions/2026-10-06_line3_faithful_build.md (structure research B+C, event-bounded; one dev revision cycle done: verbatim writes, arms.v2, memanswer.v18).
Code: branch line3-pilot at the commit that adds this file. heldout_1 has not been opened by the designer or any implementer.

## Run
- Stories: experiments/line3/bank_ls/heldout_1 (6 stories), all checkpoints; repeats 3; model claude-haiku-5-5; arms A0, A1 (model-written log), A1v (raw sentences appended automatically), A3 (crosses, arms.v2 verbatim writes), A3f (flat table, same writes and answer path); answer path memanswer.v18; per-turn budget as in meter2 defaults.
- Budget cap: USD 45 total (stop and report if exceeded). Runs on this Mac with the load pause (> 12).
- Results are reported in full whatever they show; the report states which predictions failed.

## Claims and predictions (from the dev diagnosis)
- P2 (structure vs log): A3 right answers > A1 and > A1v with non-overlapping ranges over the 3 repeats. PREDICTION: fails (dev: A3 7–8/40 vs A1 20, A1v 19).
- P3 (geometry vs flat table): A3 > A3f on contradictions found, reversals found or right answers, non-overlapping ranges. PREDICTION: fails (dev and offline ablations: no difference except nests).
- H-D (intake detection): structure notes in A3 and A3f notice more planted UPDATES and REVERSALS than A1/A1v notice (A1/A1v counted by the model's own reports), non-overlapping ranges. PREDICTION: holds (dev: updates 8/8 vs 0/8, reversals 4/4 vs 0–1/4).
- Safety: confident-wrong answers of A3/A3f ≤ those of A1/A1v (dev: 4–6 vs 10). PREDICTION: holds.
- Stop rule (owner): if the A3 vs A3f difference never exceeds the repeat range on heldout_1 and heldout_2, the geometry claim is dropped and reported as negative.
