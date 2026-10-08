# Round5-A phase 2 — measure sentences, role-only questions (2026-10-01)

**Status: development result on the public dev set only. Not adopted, not a sealed result, not general completion.**
Work copy: `~/Projects/vera-round5-run/phase2/workcopy` (base `9342f78`, phase2 commits on top). The original repo is untouched.
Implementation: Claude (design, code, checker); Codex gpt-6-luna max Standard was used as hands only (adversarial test authoring, full-suite regression run).

## Public dev80 (fixtures SHA a765402a…c1c693), `one.Vera(mode="semantic")`
| family | items | correct (base copy) | correct now | wrong now | abstain now |
|---|---:|---:|---:|---:|---:|
| role_binding | 4 | 2 | 3 | 0 | 1 |
| negation_scope | 4 | 0 | 0 | 0 | 4 |
| condition | 4 | 0 | 0 | 0 | 4 |
| exception | 4 | 0 | 0 | 0 | 4 |
| quote_reality | 4 | 0 | 0 | 0 | 4 |
| unit_calculation | 7 | 0 | 3 | 0 | 4 |
| comparison | 7 | 0 | 5 | 0 | 2 |
| two_hop_join | 6 | 0 | 0 | 0 | 6 |
| multiple_requirements | 6 | 0 | 0 | 0 | 6 |
| ambiguity | 4 | 0 | 0 | 0 | 4 |
| multi_argument | 4 | 0 | 4 | 0 | 0 |
| equivalent_paraphrase | 2 | 2 | 2 | 0 | 0 |
| insufficient_evidence | 6 | 0 | 0 | 0 | 6 |
| conflicting_evidence | 4 | 0 | 0 | 0 | 4 |
| injection | 4 | 0 | 0 | 0 | 4 |
| time_scope | 4 | 0 | 0 | 0 | 4 |
| negative_polarity | 2 | 0 | 0 | 0 | 2 |
| conditional_exception | 2 | 0 | 0 | 0 | 2 |
| counterfactual_scope | 2 | 0 | 0 | 0 | 2 |
| **total** | 80 | 4 | 17 | 0 | 63 |

**Baseline note:** the base copy measures 4/80, not the 5/80 of the earlier report: r47 (injection, `記録:…`) abstains in the base copy because the later colon-scope safety fix
(`uninterpreted colon scope`, added after the earlier run on review findings) turns a `記録:` heading into an unread source clause. That is a deliberate safety rule, not changed here; a typed heading-scope reading would be needed to recover r47.

Wrong ANSWER stayed 0; no item lost relative to the base copy. Median ask of the answered items 1.3 ms (p95 2.7 ms, max 10.3 ms). Runs kept: `results/phase2/baseline_public80`, `run_measure01..05` (run04 contained one wrong ANSWER, r74; root-caused and fixed in step 5, kept).
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

## Step 4-5: coordinated predicates, and what the first wrong answer taught
- `semantic_coord.py`: plain te/renyō chains inside one sentence become one clause per predicate. A topic-`は` subject of the first clause is shared only by later clauses that have no は/が phrase
  of their own (the typed rule for the sidecar's unpermitted `INTERCLAUSE_BORROW`). Adversative が, causal ので/から, conditional ば/たら/と, hedges and quotes stay refused. The checker re-derives the
  coordination and the borrow per clause (every predicate must be a clause of the view; the borrowed phrase must be the first clause's topic NP).
- `frame_evidence` (commit 1f9b7d8 of the original repo, already byte-identical in this copy) confirmed the structure (per-clause owner/arguments, the borrow marked unpermitted); the code path itself is not imported yet.
- **run04 produced a wrong ANSWER (r74)**: enabling coordination made the document readable and exposed a question-side bug: the cleft question `リンを呼んだのは？` was read as a yes/no question.
  Fixed: cleft questions ask for the open role; a particle-final fragment is never a yes/no question; the noun of a cleft is not turned into a head-noun restriction.
- **A pre-existing tense bug found on the way**: the past auxiliary だ after 撥音便 (呼んだ, 読んだ, 飲んだ) was not recognised as past (decided by orthBase), so past and nonpast of those verbs were conflated
  (`エンはリンを呼ぶ。` answered `呼んだ？` with はい). Now decided by lemma in reader and checker; the question normaliser no longer strips that だ. Tests for both directions added.
- Codex (hands) wrote 97 coordination cases from a spec: 90 passed at first; the findings were two spec errors of mine (open-world: an unstated combination is UNKNOWN, never いいえ; concessive のに keeps the topic subject on the main clause),
  one verb/name dependence of the old Frame reader (recipient of 送る or of the name ソウ is dropped, so those clauses abstain), and no implementation bug. Codex also ran the whole `tests/` directory on the base and on this copy: no regression (2 pre-existing failures in both).
- Full semantic/goal/frame suites: 469 pass.

## Step 6: stereo-cross routing of the document path (2026-10-02)
See `docs/ROUND5A_STEREO_ROUTE_2026-10-02.md`. The semantic path now narrows the documents to the reach of the question's anchors through a `conduct_tree` over the documents (a document = one leaf;
unread text indexed by character bigrams; per-pattern intersection for clauses, union for unread; rare-entity expansion for joins/guards). Synthetic scale: flat view 0/40 from 300 documents (budget), routed 88-92/100 with 0 wrong
at 300/1,000/4,000 documents and a constant 0.77 ms median. Public dev80 unchanged (17 correct / 0 wrong; single documents are below the routing threshold).
The scale run also found two real fragment-answer bugs (name split, tagger-cut names) — fixed in reader and checker. Whole `tests/` directory: see the final count in the run log of this step.

## Not done / next
- r36 (discourse difference), r35/r59/r60 (multiply/divide kernel ops), r37 (equal values answered as 同じ), r38 (clock-time ordering).
- Totals over more than two measures (needs an aggregate over all matching clauses, with the checker verifying completeness).
- Exceptions/conditions/two-hop (r05–r08, r15–r16, r25–r26, r29–r32, r55–r58) need habitual-rule and relative-clause readers; the から/name work does not touch them.
- Independent review of this diff and a new sealed run are still required before any adoption claim.
