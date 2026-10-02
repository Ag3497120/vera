# Evaluations (2026-09-28)
All sealed sets were written by Codex (gpt-6-sol) and not read before the run; lines were fixed before each run (preregistration). Judging by Claude.
- Verdict contract, 4 sealed rounds (200–220 claims each): harmful 0.5 / 0.5 / 8.0→0 after a fix / 0%; detection of contradictions and violations 62.5 / 47.5 / 40 / 8.3% (falls as wording varies — the rules do not reach free paraphrase).
- Two-stage (Vera first, a local LLM only for paraphrase-suspect claims, quotes checked in code, the model may not overturn a structural "roles differ"): accuracy 38.5 → 65.5%, harmful 0.5%.
- Flat vs stereo cross over 80–160 documents: stereo cross + fallback equals the right-document upper bound in all 4 rounds; judging time stays ~0.2–0.4 ms as documents grow (flat grows 0.6 → 8.7 ms).
- Sovereigns (rules / records): wrong routing 13 → 6–7.5%, same speed, no harmful verdicts.
- Corpus size (10/30/60/100% of sources): metaphor-answer coverage 14/19/24/28 of 30 words; size buys coverage, not correctness.
- Core six (2 sealed rounds each, 20 items): puns pass (70%, 80%); metaphor meaning, commonsense (effect, use) and haiku fail twice and are refused; stories only as labelled passages.
- Capability surveys: 48 basic abilities (dev) and 120 abilities from LLM benchmark taxonomies (sealed, 600 items): see the fit map in the model card.

## Update 2026-10-03 (prototype measurements; not sealed, not adopted)
All numbers are ours, on train/public data, for the working-copy snapshot `d25a73a`. They are progress measurements, not a held-out result.
- Public dev set (80 items, audited): 17 correct / 0 wrong (4/80 at the start of the phase); measured before the last waves.
- Reading coverage on 1,500 Wikipedia lead paragraphs (train split), 3,575 sentences, with at least one supported clause: 678 (19.0%) → 596 (16.7%, a precision fix that made the reader abstain more) → 1,339 (37.5%, construction registry plus eleven constructions).
- Gold probe on the Codex-generated corpus (train split only; 16 phenomena × 150 = 2,400 who-did-what items): correct 61 → 87 (3.6%), wrong 15 → 2 (+17 head/modifier mismatches), abstain 2,294. Of 1,500 diagnosed items, 73% of abstentions are on the reading side and 23% on the question side. Authors and gold are from the same model family: expect optimism.
- Leaf router (stereo cross as a reach index): 0 violations against a flat contract oracle (16,000 leads); two-hop chains through a rare entity 60/60 of the flat answers after the entity-walk fix (17–54% before); mid-frequency entities 0–23%.
- Realizer: realizable 65% (copula) / 24% (frame) on 10,000 leads; 300 meaning-changing mutations caught 300/300 jointly, 78/300 by the lineage check alone.
- Conductor: scripted agent, 103 questions, 0 wrong at fake-asker accuracy 100/80/50%; 130 real agent questions (72 with the human's answer): 0 answered, 72 escalated, 0 wrong.
- Tests in a clean clone: 1,666 passed, 18 failed, 9 skipped (see KNOWN_ISSUES.md).
- Planned, not done: a preregistered run on the sealed heldout split of the gold corpus, judged independently, with thresholds fixed before the run.
