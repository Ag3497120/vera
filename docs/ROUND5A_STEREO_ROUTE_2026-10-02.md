# Round5-A — stereo-cross leaf routing for the document path (2026-10-02)

Development result in an isolated copy. Not adopted, not a sealed result.

## What was unconnected
`one.Vera(mode="semantic")` built ONE flat view over all documents and every question scanned every clause with the plan's predicate; any Unread sentence in ANY document refused every answer.
The stereo cross (`conduct_tree` / `surface.route`) was used only by the large-index retriever. Measured with synthetic documents (own data, one fact per document plus a shared entity `係員` in every document):
flat view = 39/40 correct at 200 documents and **0/40 at 300 and above** (the 256-candidate budget: `UNKNOWN_BUDGET`).

## Design (`verantyx/semantic_route.py`, called from `one.Vera._routed_semantic_view`)
- Leaf = one document. Each leaf's cross: core = the exact string of every clause role value (and of the entities in condition/exception patterns), facet = predicate; unread spans are indexed by character bigrams
  (substring containment is complete, so a document that mentions an anchor in a sentence the reader could not read is never missed, whatever the tagger did). `conduct_tree.build(arity=6)` builds the tree.
- A question reads its anchors per Bind pattern (literal string role values; Nominal heads are not anchors). **The reach set**, not a single "best" leaf: every arm whose merged surface holds the anchor is descended, because a
  one-leaf narrowing would hide a contradicting or excepting document. For CLAUSES, per pattern the leaves must hold ALL its anchors (a clause that binds or contradicts the pattern contains every literal value of it); patterns are unioned.
  For UNREAD text the rule is the opposite: it is opaque, so a leaf is reached when its unread text can mention ANY anchor (a fragment about the object alone may be the sentence that contradicts the clause).
  Codex's differential attack found exactly this hole (10 cases); fixed, tests kept.
- Joins need one more hop per extra Bind pattern; a guard (condition/exception) needs its own fact for up to three more hops. Only rare entities (held by <= 8 leaves) are followed; common ones (係員) are not, which can lose a derivation
  (abstention) but never create one. An anchor held by > 64 leaves is "common"; if every anchor of a pattern is common, or the request has no anchor (role-only, measure questions), the whole view is kept (flat).
- The routed `View` is a SUBSET of the original (same clauses and spans); producer and independent checker both run on it. Below 7 documents nothing changes.
- Trace: `semantic_route.LeafTree` with leaves, nodes, reached leaves, nodes visited, common/followed terms, route ms.

## Measured (synthetic, 100 questions per size, 0 wrong everywhere after the fixes below)
| documents | flat view | routed view | routed median ms | reached leaves | tree nodes visited |
|---:|---|---|---:|---:|---:|
| 50 / 200 | 39/40 | 39/40 | 0.77 | 1 | 8 |
| 300 | 0/40 (budget) | 92/100 | 0.77 | 1 | 10 |
| 1,000 | 0/40 (budget) | 88/100 | 0.76 | 1 | 10 |
| 4,000 | 0/40 (budget) | 92/100 | 0.77 | 1 | 12 |
The routed answer time stays at 0.77 ms from 50 to 4,000 documents (the flat view grows with the corpus and then abstains). Abstentions are questions about documents whose own text carries an Unread sentence.
Public dev80 is unchanged (17 correct, 0 wrong, 63 abstain): those items have a single document, below the routing threshold.

## Safety evidence
`tests/test_semantic_route.py`: contradictions in other documents, negations, Unread sentences that mention the anchors (still gate) or not (no longer block), two-hop across documents, a guard fact in another document,
out-of-corpus anchors, a common entity; plus randomized corpora differential against the flat view (6 seeds in the suite; 40 extra seeds x 12 questions run by hand: 0 violations,
routed reached 2.4 of 60 leaves on average). Invariant: routing may only save budget; if both answer, the values are equal; conflicts/negations/anchor-mentioning Unread text never become an answer.
A Codex (hands) adversarial differential file (`tests/test_semantic_route_codex.py`, 46 named cases + 32 seeded corpus/question pairs + 3 injection variants) attacks the same invariant: first run 10 failures (unread text mentioning only a subset of the anchors), all fixed; now all pass. Routing suites: 96 tests.

## Bugs the scale run found (kept as tests)
1. The appositive name split cut unknown katakana names (`コカカル` -> `コカ` + `カル`) and answered the fragment. Now split only for a kanji title before a proper name.
2. The reader/checker coverage ignored tokens such as interjections (`クク`) and the tagger's ascii-art label (`ノシ` tagged as symbol), so a name cut by the tagger answered a fragment (`クル`, `カル`).
   A role phrase must now be bounded by a particle or real punctuation on both sides, in the reader and (independently) in the checker.

## Not connected / limits
- Anchor-less questions (measures, role-only) and the multigrain candidate path still use the whole view. The large-index retriever already used `conduct_tree`.
- Common entities are not followed (derivations that join only through them abstain). The caps (64 / 8) are tunable and unmeasured on real text.
- Several documents in one sovereign share bindings as before; the routing narrows candidates, it does not change sovereign independence.
- The default `legacy` router and the B/C parts are untouched; the unconnected parts listed by `tests/test_one_trace.py` (writer, hub_edges, compose_*) are not part of this change.
