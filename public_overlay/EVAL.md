# Evaluations — v0.9-preview (base: dev `ecde332`)

This file gives the detail behind the table in `README.md`. Every number has a row id `[N-xx]` there (value, denominator, set, source path at the commit) and can be recomputed with `python tools/readme_numbers_check.py numbers` in the development tree (`Verantyx-Vera-alpha`). Sources named below are paths in that tree at `ecde332`.

## How the sets differ

- **Held-out sets**: written by a different model family and kept from the implementers; run by the auditor outside the implementer's sandbox (`docs/AUDIT_2026-10-06.md`). Only counts and results are recorded; the items are not published. Some graders and some expectations of these sets were corrected by their author after the first run (the record says which); the numbers in the table are after those corrections.
- **Hidden banks**: counts only. B1 [N-15] [N-16], B2 [N-17] [N-18]. Their contents and paths are not published.
- **Self-made sets** (written by the implementers): a pass proves little. They are in the table only where the result is a negative one or where they show how a mechanism behaves: [N-20] [N-21] [N-22] [N-23] [N-40].
- **The W14 public benchmark v1, run1** (`docs/BENCHMARK_PUBLIC.md`): machine-judged drafts; human grading is not done [N-41]. The systems compared are the plain local LLM, Vera's default mode (the LLM's sentences are shown, marked as testimony) and Vera's strict mode.

## What each group measures

- **Completion-claim check** (`vera attest`): held-out T6 [N-01] [N-02] [N-03]. On the self-made comparison, Vera's reading of the report adds nothing to a plain regex/JSON extractor [N-20] [N-21] [N-22]; a plain local LLM judge answered "no" to some correct facts [N-23].
- **Ledger** (`vera run`, `events verify`): held-out T7 [N-04].
- **Answering path** (T2): held-out T2 [N-05] [N-06] [N-07] [N-08]. The three entrances (ask, chat, serve) call one function.
- **Human confirmation** (T8): held-out T8 [N-09] [N-10] [N-11]; the base reader reads only part of the set [N-12]. A human confirmation (word types and frames) did not unlock any independently written sentence [N-10].
- **Quote check** (T3, serve layer 0): held-out T3 [N-13] [N-14]. In the W14 C system [N-35] [N-37] [N-38] [N-39] and the self-made T3-1 set [N-40]. The "sources Vera verified" count was [N-34] under the old yardstick and is [N-36] under the new one; the definitions differ, so these two rows are not a before/after comparison.
- **W14 systems**: [N-24] to [N-33]. The strict mode and the always-abstain baseline coincide on the machine judgement.
- **Test suite**: [N-19].
- **Not measured**: [N-41] [N-42] [N-43].

## History (up to snapshot d25a73a). Not recomputed in this version.

The text below is the previous `EVAL.md`, moved without changes to its wording, except for the headings that mark its two parts and the `[N-xx]` marks (N-51 to N-56) added after sentences that contain a claim word, so that each points to a row with its denominator and set. One more addition: in the Conductor line of part 2, a short parenthetical about the 130 real agent questions [N-54] was written in by the editor (the old text did not have it); it only says that, with no answered question, no wrong answer is possible. These marks tie the sentence to the wording of the old README/EVAL at `ecde332`; the underlying measurements are **not** part of the tree and were **not** recomputed here.

### History part 1: evaluations of 2026-09-28
All sealed sets were written by Codex (gpt-6-sol) and not read before the run; lines were fixed before each run (preregistration). Judging by Claude.
- Verdict contract, 4 sealed rounds (200–220 claims each): harmful 0.5 / 0.5 / 8.0→0 after a fix / 0%; detection of contradictions and violations 62.5 / 47.5 / 40 / 8.3% (falls as wording varies — the rules do not reach free paraphrase).
- Two-stage (Vera first, a local LLM only for paraphrase-suspect claims, quotes checked in code, the model may not overturn a structural "roles differ"): accuracy 38.5 → 65.5%, harmful 0.5%.
- Flat vs stereo cross over 80–160 documents: stereo cross + fallback equals the right-document upper bound in all 4 rounds; judging time stays ~0.2–0.4 ms as documents grow (flat grows 0.6 → 8.7 ms).
- Sovereigns (rules / records): wrong routing 13 → 6–7.5%, same speed, no harmful verdicts.
- Corpus size (10/30/60/100% of sources): metaphor-answer coverage 14/19/24/28 of 30 words [N-56]; size buys coverage, not correctness.
- Core six (2 sealed rounds each, 20 items): puns pass (70%, 80%); metaphor meaning, commonsense (effect, use) and haiku fail twice and are refused; stories only as labelled passages.
- Capability surveys: 48 basic abilities (dev) and 120 abilities from LLM benchmark taxonomies (sealed, 600 items): see the fit map in the model card.

### History part 2: update 2026-10-03 (prototype measurements; not sealed, not adopted)
All numbers are ours, on train/public data, for the working-copy snapshot `d25a73a`. They are progress measurements, not a held-out result.
- Public dev set (80 items, audited): 17 correct / 0 wrong [N-51][N-52] (4/80 at the start of the phase); measured before the last waves.
- Reading coverage on 1,500 Wikipedia lead paragraphs (train split), 3,575 sentences, with at least one supported clause: 678 (19.0%) → 596 (16.7%, a precision fix that made the reader abstain more) → 1,339 (37.5%, construction registry plus eleven constructions).
- Gold probe on the Codex-generated corpus (train split only; 16 phenomena × 150 = 2,400 who-did-what items): correct 61 → 87 (3.6%), wrong 15 → 2 (+17 head/modifier mismatches), abstain 2,294. Of 1,500 diagnosed items, 73% of abstentions are on the reading side and 23% on the question side. Authors and gold are from the same model family: expect optimism.
- Leaf router (stereo cross as a reach index): 0 violations against a flat contract oracle (16,000 leads); two-hop chains through a rare entity 60/60 of the flat answers after the entity-walk fix (17–54% before); mid-frequency entities 0–23%.
- Realizer: realizable 65% (copula) / 24% (frame) on 10,000 leads; 300 meaning-changing mutations caught 300/300 jointly, 78/300 by the lineage check alone.
- Conductor: scripted agent, 103 questions, 0 wrong [N-53] at fake-asker accuracy 100/80/50%; 130 real agent questions (72 with the human's answer): 0 answered, 72 escalated, 0 wrong [N-54][N-55] (zero answered, so zero wrong is trivially so).
- Tests in a clean clone: 1,666 passed, 18 failed, 9 skipped (see KNOWN_ISSUES.md).
- Planned, not done: a preregistered run on the sealed heldout split of the gold corpus, judged independently, with thresholds fixed before the run.
