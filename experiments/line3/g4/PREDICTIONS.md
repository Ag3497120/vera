# G4 predictions (registered BEFORE any real-data meter run)

Registered: 2026-10-11, by the G4-e/f implementer, before `experiments/line3/g4/meter.py` was run on any real stack or one-shot cache.
Source: `docs/LINE3_G4_GROWTH_METER.md` section 7.5 (P-1 .. P-7, copied verbatim; the brief called it "plan 3.4", it is 7.5). They are the designer's, written
2026-10-10. This file is not edited after the first real run: a prediction that fails is marked "failed" in the summary, never reworded here.

What already exists and is NOT a meter run: `experiments/line3/g4/read_smoke.py` (G4-c, 8 articles, 6 questions, no gold listed for any of the 3 intra2
questions) and the gate G-2 build report (`results/gate2_A.md`: structure only, no question asked). The smoke of this ticket (steps 1, 2, 3, 5, 8,
questions with entry <= 8 plus unans) is run AFTER this file; it is a plumbing check at 8 articles, not a measurement of the predictions.

## The designer's predictions (copied, section 7.5)

- P-1 (A): most 現れる are 直入. 後から <= 5 of 69.
- P-2 (A): at 300, A <= C@300 - 3 on gold in a candidate (document-order insertion plus closing seats fewer golds than the one-shot build).
- P-3 (A): among losses, U (read cap: more crosses hold question units as the prefix grows) > R > A. 単独誤答化 <= 2 over all steps.
- P-4 (A, C): the absent row is mostly "false presence" for both. The flat reader lists whenever a question unit's cross exists (C: T10 flat fast on
  unans = 23 CHOICE, 1 ANSWER, 1 UNKNOWN of 25). Absent-correct <= 5/25 on unans at 300 for both, and >= 1 confident wrong somewhere on the absent row.
- P-5 (B): <= 3/69 present-correct at 300 (T9 audit: CHAR contributed 1/69). Absent row like A.
- P-6 (A vs A0): |Delta present-correct| <= 3 at 300. The foundation acts through tie splitting and through which crosses close.
- P-7 (stack): the share of crosses closed at 300 is higher with the foundation on than off (arm-distinct ties grow classes; the risk in section 13).

## Added by the implementer (also before any run; meter-specific)

These are about quantities the meter introduces that the designer's list does not cover. Each is a number I commit to now.

- P-8 (A, 未着): at step 300, at least 5 and at most 25 of the 69 intra2 golds are 未着 (no RUN/WORD/CHAR unit of the prefix space holds the normalised gold).
  Reason: golds that are numbers with units, dates, or phrases across a tokeniser boundary; CHAR units are single characters and catch only one-character golds.
- P-9 (A, 現れる denominator): 未着 is stable once true (a gold unit that exists never disappears from a growing prefix); the number of 未着 questions never
  increases with the step among the entered questions. (A check of the definition more than a result; it fails only if the space is not monotone.)
- P-10 (A, 残る): of the questions that appear (H at some measured step), at least 75 % are 残る at every later measured step, because a seated unit never moves
  and a closed cross never grows; the losses that exist are mostly reading (U) and are not placement.
- P-11 (A, headline): at step 300 present-correct is at most 20 of 69 (T10 flat fast one-shot is 16 gold-in-candidate of 69, and present-correct needs the gold from the
  evidence article, which is stricter than gold in a candidate).
- P-12 (B vs A): gold in a candidate at step 300 for B is at most A's, and no question has B present-correct that A lacks, except one-character golds.

Judged in `results/summary.md` as held / failed, with the number beside each.
