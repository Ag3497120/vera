# Round5-A phase 2 — measure sentences, role-only questions (2026-10-01)

**Status: development result on the public dev set only. Not adopted, not a sealed result, not general completion.**
Work copy: `~/Projects/vera-round5-run/phase2/workcopy` (base `9342f78`, phase2 commits on top). The original repo is untouched.
Implementation: Claude (design, code, checker); Codex gpt-6-luna max Standard was used as hands only (adversarial test authoring, full-suite regression run).

## Public dev80 (fixtures SHA a765402a…c1c693), `one.Vera(mode="semantic")`
| family | items | correct before | correct now | wrong now | abstain now |
|---|---:|---:|---:|---:|---:|
| role_binding | 4 | 2 | 2 | 0 | 2 |
| negation_scope | 4 | 0 | 0 | 0 | 4 |
| condition | 4 | 0 | 0 | 0 | 4 |
| exception | 4 | 0 | 0 | 0 | 4 |
| quote_reality | 4 | 0 | 0 | 0 | 4 |
| unit_calculation | 7 | 0 | 3 | 0 | 4 |
| comparison | 7 | 0 | 5 | 0 | 2 |
| two_hop_join | 6 | 0 | 0 | 0 | 6 |
| multiple_requirements | 6 | 0 | 0 | 0 | 6 |
| ambiguity | 4 | 0 | 0 | 0 | 4 |
| multi_argument | 4 | 0 | 3 | 0 | 1 |
| equivalent_paraphrase | 2 | 2 | 2 | 0 | 0 |
| insufficient_evidence | 6 | 0 | 0 | 0 | 6 |
| conflicting_evidence | 4 | 0 | 0 | 0 | 4 |
| injection | 4 | 0 | 0 | 0 | 4 |
| time_scope | 4 | 0 | 0 | 0 | 4 |
| negative_polarity | 2 | 0 | 0 | 0 | 2 |
| conditional_exception | 2 | 0 | 0 | 0 | 2 |
| counterfactual_scope | 2 | 0 | 0 | 0 | 2 |
| **total** | 80 | 4 | 15 | 0 | 65 |

**Baseline note:** the base copy measures 4/80, not the 5/80 of the earlier report: r47 (injection, `記録:…`) abstains in the base copy because the later colon-scope safety fix
(`uninterpreted colon scope`, added after the earlier run on review findings) turns a `記録:` heading into an unread source clause. That is a deliberate safety rule, not changed here; a typed heading-scope reading would be needed to recover r47.

Wrong ANSWER stayed 0; no item lost relative to the base copy. Median ask of the answered items 1.3 ms (p95 2.7 ms, max 10.3 ms). Runs kept: `results/phase2/baseline_public80`, `run_measure01..03`.
These numbers say nothing about unseen text: the rules were written over structure and checked with own paraphrase/swap tests, but the dev items are the only evaluation seen.

## What was added (structure, not words)
1. `semantic_measure.py` — a document sentence made only of `<label><は|が|に|も><number><unit>` segments (、-joined, optional list-level `の<noun>`) becomes one
   `measure.<dimension>` clause per segment; the dimension comes from the IR unit table. Requests handled over exactly two measures of one dimension: total (`合計は何<unit>？`),
   pick (`長い/短い/重い/軽い<kind>は？`, `長い方は？`, `どちらが…？`), same/different (`長さは違う？`). Plans use existing Bind/Join/Filter/Sum/Compare/Project.
   Alphabetic identifier labels answer with the identifier; numeral-ending labels answer with the whole label. Ties abstain (kernel `UNKNOWN_AMBIGUOUS`). Durations (1時間) are not clock-time scope.
2. `semantic_wh.py` — role-only questions (wh-word + case particle, or role nouns) become one wildcard Bind over the asked roles; several events carrying all roles stay ambiguous.
3. Reader: から (ablative) phrases are read as `origin` directly (typed_edges has no から edge); `<descriptor><proper name>` splits into descriptor + name from the sentence's own tokens (`semantic_names.py`),
   only when Unidic tags the head as a proper noun (e.g. 整備士コウ is NOT split because コウ is tagged as a common noun; the whole phrase is answered).
4. Checker (`semantic_verify.py`): independent split-based re-reading of measure sentences (every segment must be a clause, role set/label/kind/dimension/quantity checked), and
   independent validation of the name split and of origin roles. Shared-cause risk remains where the checker imports the same IR unit table and name-split helper.

## Existing test changed on purpose
`tests/test_semantic_scope_safety.py::test_checker_does_not_trust_reader_coverage_flags` used a から sentence as its "unsupported" example; から is now supported, so the example became an adverb (そっと). Reason recorded in the file.

## Tests
`tests/test_semantic_measure.py` (own generalization cases: paraphrase, unit conversion both ways, source-order swap, polite ending, entity/number swaps, must-not-answer cases, literal-overlap guard against dev strings)
and `tests/test_semantic_measure_codex.py` (78 cases written by Codex from a spec, expectations computed by hand; its first run found two real bugs — durations rejected by the clock-time pattern — which were fixed;
two of its cases encoded a wrong spec (injected instruction) and were corrected). Semantic/goal/frame suites: 347 pass.

## Not done / next
- r28 (coordinate predicates), r36 (discourse difference), r35/r59/r60 (multiply/divide kernel ops), r37 (equal values answered as 同じ), r38 (clock-time ordering).
- Totals over more than two measures (needs an aggregate over all matching clauses, with the checker verifying completeness).
- Exceptions/conditions/two-hop (r05–r08, r15–r16, r25–r26, r29–r32, r55–r58) need habitual-rule and relative-clause readers; the から/name work does not touch them.
- Independent review of this diff and a new sealed run are still required before any adoption claim.
