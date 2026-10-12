# LOOM-control — the two routes on bank2's 25 unanswerable fulllead items (claude-haiku-5-5, one run per cell, 2026-10-12)

Owner's condition (ops/decisions 2026-10-12): stable control needs BOTH (1) the structural refusal route (the model tries to weave/emit and the loom refuses) and (2) the model's own re-check route (lookups/reads find nothing → abstain before any weave attempt), counted separately.

| condition | n | answered / emitted (= confident wrong: not in the corpus) | abstained |
|---|---|---|---|
| record_only | 25 | 0 | 25 |
| constructed_allowed | 25 | 0 | 25 |
| free_text (lookup control) | 25 | 0 | 25 |
| no_tools (pure LLM) | 25 | **4** (UF-001, UF-009, UF-010, UF-011) | 21 |

| stop layer | L_meta | L_struct | L_none_marked | L_none | L_other | runs with any weave/seat/add/emit attempt |
|---|---|---|---|---|---|---|
| record_only | 25 | **0** | 0 | 0 | 0 | **0** |
| constructed_allowed | 25 | **0** | 0 | 0 | 0 | **0** |
| free_text | 25 | 0 | 0 | 0 | 0 | 0 |
| no_tools | 21 (no tool to check with — not a re-check) | 0 | 0 | 4 | 0 | 0 |

| condition | lookups median (range) | empty lookups | read_sentence | input tokens (25 runs) | input per run, median |
|---|---|---|---|---|---|
| record_only | 20 (4–45) | 413 / 594 | 236 | 6,150,161 | 175,271 |
| constructed_allowed | 19 (8–45) | 348 / 530 | 176 | 5,113,972 | 174,574 |
| free_text | 8 (4–19) | 106 / 219 | 92 | 604,547 | 22,568 |
| no_tools | 0 | 0 | 0 | 3,286 | 132 |

Reading (honest):
1. **Route (1) never fired on this bank.** The 50 loom runs made no add / open_cross / seat / weave_span / emit; zero not_a_record / constructed_forbidden / unstable_cross refusals. This bank proves route (2) only.
2. Every loom abstention is route (2): `abstain(no_record)` after 4–45 mostly empty lookups.
3. The pure LLM (no_tools) answered 4/25 where the lookup control abstained 25/25 (reverse: 0). So a lookup window alone makes Haiku 5.5 abstain on these; the loom's effect beyond that is not separable here.
4. The loom modes cost ≈ 8× the lookup control's input tokens and searched ≈ 2.4× longer to say 不明.
5. L-LOOM-157 (a test, not a model measurement): offering the four no_tools answers to the loom as `add` — record_only refuses 18/18; constructed_allowed refuses record units 9/9 but accepts short constructed units (6/9, marked). Where constructed units are allowed, the structure MARKS the answer rather than stopping it.

Next: bank4 (adversarial unanswerable, codex-authored, Opus-audited) is meant to tempt a weave so that route (1) can be observed. The raw tables are in REPORT_TABLES.txt; ledgers in runs_unans/, results in results_unans/.
