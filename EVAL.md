# Evaluations (2026-09-28)
All sealed sets were written by Codex (gpt-6-sol) and not read before the run; lines were fixed before each run (preregistration). Judging by Claude.
- Verdict contract, 4 sealed rounds (200–220 claims each): harmful 0.5 / 0.5 / 8.0→0 after a fix / 0%; detection of contradictions and violations 62.5 / 47.5 / 40 / 8.3% (falls as wording varies — the rules do not reach free paraphrase).
- Two-stage (Vera first, a local LLM only for paraphrase-suspect claims, quotes checked in code, the model may not overturn a structural "roles differ"): accuracy 38.5 → 65.5%, harmful 0.5%.
- Flat vs stereo cross over 80–160 documents: stereo cross + fallback equals the right-document upper bound in all 4 rounds; judging time stays ~0.2–0.4 ms as documents grow (flat grows 0.6 → 8.7 ms).
- Sovereigns (rules / records): wrong routing 13 → 6–7.5%, same speed, no harmful verdicts.
- Corpus size (10/30/60/100% of sources): metaphor-answer coverage 14/19/24/28 of 30 words; size buys coverage, not correctness.
- Core six (2 sealed rounds each, 20 items): puns pass (70%, 80%); metaphor meaning, commonsense (effect, use) and haiku fail twice and are refused; stories only as labelled passages.
- Capability surveys: 48 basic abilities (dev) and 120 abilities from LLM benchmark taxonomies (sealed, 600 items): see the fit map in the model card.
