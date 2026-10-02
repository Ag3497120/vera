# Scout: agreement bands beside semantic answers

## Finding

`graded.band_annotation` can be stored beside a semantic result as a Python mapping, but the existing judge does not produce an honest band for a semantic answer: it ranks legacy CrossStore core names, while the semantic path returns typed answer values backed by cited source clauses. There is no adapter or common answer key between them.

The smallest honest semantic band is absent (`None`) until a distinct, lineage-checked structure can be queried independently. Once one such structure returns the same verified typed answer, the smallest nonempty band is `agree=1, of=1`. That is an agreement count only. It must not alter or promote the semantic verdict.

## 1. What exists

### Graded annotation

`verantyx/graded.py:81-88` defines six default settings. `staircase` crosses the requested grain, grammar, and depth choices (`graded.py:119-141`). `GradedJudge.build` takes a store with `crosses` and `source_labels`, then builds a `resolution.Ladder` per setting (`graded.py:237-251`). Each ladder abstains on tied leaders (`resolution.py:103-131`).

The source signatures are:

```python
staircase(grains: Sequence[Tuple[str, int]] = GRAIN_AXIS,
          grammars: Sequence[str] = GRAMMAR_AXIS,
          depths: Sequence[Optional[int]] = (1,)) -> Tuple[Tuple[str, Dict[str, Any]], ...]
GradedJudge.__init__(self, settings: Sequence[Tuple[str, Dict[str, Any]]] = DEFAULT_SETTINGS,
                     *, read: Optional[Any] = None)
GradedJudge.build(self, store: Any) -> "GradedJudge"
GradedJudge.ask(self, query: str) -> Dict[str, Any]
band_annotation(judge: "GradedJudge", query: str) -> Optional[Dict[str, Any]]
Ladder.build(self, items: Dict[str, Iterable[str]]) -> "Ladder"
Ladder.vote(self, query_terms: Sequence[str]) -> Dict[str, Optional[str]]
ask(ladder: Ladder, query_terms: Sequence[str]) -> Dict[str, Any]
```

`GradedJudge.ask` runs the same query over its configured ladders and reports the leading item count, coverage, and per-setting readings (`graded.py:253-333`). `band_annotation` returns `None` when no reading is countable; otherwise it returns `agree` and `of`, with optional `item` and `concord` (`graded.py:336-361`). Its docstring explicitly defines this as an annotation beside a verdict, not evidence for the verdict.

Measured here with the configured interpreter, an in-memory store containing only `alpha`, and `read=lambda q: [q]`: the settings lengths were default `6`, wide `12`, full `48`; `band_annotation(judge, "alpha")` returned `{'agree': 6, 'of': 6, 'item': 'alpha', 'concord': 1.0}`. This is an API-shape smoke measurement on a synthetic store, not an accuracy result or semantic-path run.

### Semantic path

`semantic_ir.py:20-32,78-123,195-203,245-283` defines source spans, typed values, roles, clauses, requests, plans, proof nodes, proofs, and a `View` of original source strings and parsed clauses. `document_view` creates that view from source documents (`semantic_reader.py:253-273`); `read_request` produces a typed request or a request carrying unread spans (`semantic_reader.py:413-474`).

The relevant signatures are:

```python
document_view(documents, *, sovereigns=None, family='document')
read_request(text, budget=Budget())
answer(request, views, *, budget=Budget(), trace=())
Producer.run(self, plan: Plan) -> tuple[list[tuple[tuple, Proof]], dict]
Checker.gate(self, request, plan, proposals)
Retriever.retrieve(self, request, budget=Budget())
LeafTree.restrict(self, request, *, anchor_cap: int | None = None,
                  expand_cap: int | None = None, unread_cap: int | None = None,
                  max_rounds: int = 8)
Vera.__init__(self, *, bot: Any = None, chat: Any = None, general: Any = None,
              library: Any = None, gap_path: str | Path | None = None,
              engine_compat: bool = False, round3_root: str | Path | None = None,
              mode: str = 'legacy', material_immutable: bool = False,
              material_root: str | Path | None = None)
Vera._ask_semantic(self, text: str, *, candidate_views=()) -> dict
Vera.ask(self, question_text: str, *, query: question.Query | None = None,
         mode: str | None = None, **engine_kwargs: Any) -> dict
```

`semantic.answer` runs a `Producer`, gates its proposals with `Checker`, and only returns `kind='answer'`, `verdict='ANSWER'`, and `semantic.verified=True` when a complete derivation was checked; it also returns typed `answer_values`, proof data, evidence text, and source spans (`semantic.py:27-88`). Refusals keep typed unknown/conflict verdicts (`semantic.py:10-19,89-97`). The public semantic route calls `_ask_semantic` directly (`one.py:779-784`); `_ask_semantic` reads the request, supplies one or more `View`s to `answer`, and finishes the result (`one.py:352-418`).

`Retriever` can return a `View` per available source family. It labels row sovereigns with the family's stored `independent` field (`semantic_retrieve.py:17-28,82-90`). A document-backed `Vera` builds a view from original texts and sovereign labels (`one.py:216-223`). `LeafTree` indexes terms from those same clauses and unread spans, then restricts the same `View` (`semantic_route.py:84-105,132-143`); it is a routing index, not another answer structure.

## 2. What blocks a direct connection

- **The answer keys differ.** The graded judge consumes a legacy store's `crosses` mapping and emits a core-name string. Semantic results are ordered `(label, typed value)` pairs such as strings, booleans, or quantities. Similar surface terms do not establish that a graded core is the semantic answer.
- **The query contracts differ.** Graded defaults to `ja_content_runs` and its own grammar/grain recutting (`graded.py:253-289`, `resolution.py:65-77`). Semantic mode reads a `Request` with explicit plans, obligations, and unread spans (`question.py:112-115`, `semantic_reader.py:413-474`). Feeding `request.text` to graded can count a term-index match unrelated to the requested predicate or output slot.
- **There is no call site.** `one.py` sends the semantic result to `_finish`; it does not construct a `GradedJudge` or call `band_annotation` (`one.py:352-418,779-784`). The existing `one.py:980-1006` graded trace entries belong to the legacy general route.
- **The checker is not an independent view.** Producer and checker receive the same `View`, sovereign, and plan in `semantic.answer` (`semantic.py:47-59`). The checker independently enumerates expected outputs and replays proofs, which is valuable verification, but it consumes the producer's parsed clause structure and request plan (`semantic_verify.py:523-531,626-671,753-766`). Reader and checker also share `semantic_coord` and `semantic_names` helpers (`semantic_reader.py:16-17`, `semantic_verify.py:14-18`). Counting producer and checker as two agreeing structures would count two stages of one evidence path.
- **Current view aggregation loses a band denominator.** Equal verified answer tuples are collapsed in `semantic.answer` with `verified.setdefault`; the result keeps one proof/view for a value and an attempts list by sovereign/plan, not a set of unique independent structure IDs (`semantic.py:33,57-59,69-88`). The current result cannot honestly say how many independent structures support that value.

## 3. Minimal typed, non-voting wiring

Keep the semantic answer path authoritative. Add a bridge that runs only after a verified semantic `ANSWER` and attaches a separate `annotations.agreement_band` object. It must leave `kind`, `verdict`, `text`, `answer_values`, `evidence`, `sources`, and `semantic.verified` unchanged. Do not run it on a refusal, and do not feed its result back into answer selection.

The bridge input should carry exactly:

- the canonical `Request` (`text`, `plans`, `obligations`, `covered`, and `unread`),
- the primary verified typed `answer_values` and primary proof source references,
- separately registered candidate structures, each with a stable `structure_id`, audited `lineage_id`, and either an original-source semantic `View` or a typed record view with source provenance.

For each candidate structure, reuse the existing semantic reader/checker contract where applicable and retain a typed outcome: `structure_id`, `lineage_id`, `verdict`, `verified`, `answer_values` when verified, and source references. Compare values with exact typed equality, not rendered text, term overlap, a sum of votes, or a partial match. Count at most one outcome per audited lineage. A verified different value is a non-match; an `UNKNOWN_*` result remains an abstention status and is never converted to `False` or negation.

Return only an annotation: `agree` is the number of independent verified outcomes exactly equal to the primary typed values; `of` is the number of independent verified outcomes compared; include matching/different structure IDs and abstention verdicts as metadata. If every candidate abstains or no candidate is independent, return no numeric band. With one eligible independent comparator the smallest numeric band is `0/1` or `1/1`. Neither result changes the primary verdict. If adapting the existing `band_annotation`, its `.item` must be renamed/nested as an annotation target, never copied into semantic `values`.

Potential independent structures are source-diverse, not parser-stage-diverse: separate independently maintained evidence families or registries; row groups with audited distinct `independent` provenance; or directly queried typed case-frame records authored and checked apart from the text reader. Family names or distinct files alone do not prove independence; deduplicate mirrors and shared upstream records by lineage. `memory_frame.Memory` is a possible typed record source: it stores slots and witness metadata (`memory_frame.py:144-165,207-238`), but `Memory.ask` renders records to sentences and calls `Vera(mode='semantic')` (`memory_frame.py:252-265`). That route is not an independent reading. A future bridge would need to query independently sourced typed slots directly. Testimony is explicitly classified as `TESTIMONY` by `check_witness` (`memory_frame.py:65-79`) and must not be treated as verified evidence.

The currently measured band settings (`6`, `12`, and `48`) are variants of one index and are not independent structures. They must not become `of=6/12/48` for semantic corroboration. Likewise, the route tree and producer/checker pair do not increment `of`.

## 4. Risks and first failure to measure

The first failure to measure is **false agreement from shared lineage or a shared reading error**. Mirrored source rows can agree because they copied the same sentence; separately executing the same parser can repeat the same predicate, negation, or scope error. Before reporting a band, test lineage de-duplication and compare band matches against an independently adjudicated answer set. Track exact-answer agreement, verified disagreement, abstention rate, and false agreement on the adjudicated cases separately; do not collapse `UNKNOWN` with a negative answer.

Other risks are treating a construction or generated sentence as evidence, comparing only rendered strings and losing value types, counting one independent source more than once, and hiding a real disagreement inside a single ratio. Keep per-structure typed outcomes and citations inspectable. Re-running producer/checker per structure also adds work; no runtime cost for this bridge has been measured.

## 5. Test plan with independent gold

Prepare a small, human-adjudicated ledger before running the implementation. The ledger should list original source spans, distinct lineage IDs, expected typed answer tuples, known counterexamples, and expected refusals. The gold must be authored from the source material and a written case-frame specification by reviewers who do not use `semantic_reader`, `semantic_verify`, `graded`, or outputs from the bridge to label it.

Exercise these cases:

- an independently maintained typed frame that supports exactly the primary answer;
- a lineage-distinct frame that supports a different typed value;
- an independent structure with no answer, preserving its exact `UNKNOWN_*` status;
- duplicate rows from one upstream source, which must not increase `of`;
- positive and negative source clauses, explicit conditions, and quantities whose types or units differ;
- a generated/constructed output and a testimony record, neither of which may count as evidence.

For every case, assert that only the annotation changes and that the primary verdict, answer values, proof, evidence, and citations remain byte-for-byte/equivalently unchanged. Check that ties still abstain in the semantic path and that an unknown outcome is not treated as negation. This scout adds no tests and ran no corpus accuracy evaluation.

## 6. Reach and limits

With the current code, an annotation can be displayed beside a legacy core-name judgment, but no numeric semantic band is supported by independent structures. With the proposed bridge and audited independent sources, it could report how often exact verified typed values recur across those structures. It would not estimate truth probability, repair an unread request, infer missing meaning, or authorize an answer that the semantic gate refused.

The only runtime measurements made for this scout are the setting counts and synthetic `alpha` band reported above. No semantic corpus, gold set, accuracy, independence audit, or wiring cost was measured, so no reach or quality percentage is claimed.
