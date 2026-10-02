# Scout: semantic multi-clause summaries

## Finding

The current modules do not combine. There is no `verantyx/semantic_realize.py` in this worktree. `summarize.py` consumes the older lexical `CrossStore`; the semantic path represents source-bound clauses in a `View`; and the available realizers accept either a single frame or a separate content `Plan`. `Vera(mode='semantic')` answers typed requests, but it has no entity-summary route.

## What exists

### Legacy n-path summary

`verantyx/summarize.py` exposes these signatures (`:56-75`):

```python
def crossing_of(store: Any, subjects: Sequence[str]) -> Dict[str, List[str]]:
def summarize(
    store: Any,
    subjects: Sequence[str],
    *,
    vocab: Any,
    edges: Any,
    limit: int = 5,
) -> Dict[str, Any]:
```

The store is a `CrossStore`: `crosses` maps a core to facet counts and `source_labels` identifies source labels (`verantyx/cross_store.py:33-68`). The crossing keeps facets held by at least two listed subjects (`summarize.py:56-65`). For each speakable subject it asks `edges(subject, candidate_facets)` for licensed facet pairs; no callback or no returned pairs yields `UNKNOWN_NO_EDGE_LICENSE`, never a co-presence claim (`summarize.py:99-129`). The exported sidecar lookup returns pairs only (`verantyx/export_sqlite.py:243-254`), so the current summary result does not carry source sentence spans for each pair.

Candidates rank by crossing width and the subject's facet mass. The first rank group that would exceed `limit`, and every lower group, is dropped whole. Output contains kept claim dictionaries, a dropped count, ranking description, and fixed Japanese text (`summarize.py:131-164`). The policy is useful; its rank inputs and result are not semantic types.

### Available realization

The older realizer is single-frame:

```python
def surfaces(fr: Frame, *, past: bool = True) -> Dict[str, str]:
def realize(fr: Frame, *, past: bool = True) -> Dict[str, object]:
```

Both are in `verantyx/realize.py:73-103`. It builds active/polite/cleft/passive surfaces, reads each back as a `Frame`, and retains only exact frame round trips. It has no multi-clause input or source-provenance field.

`verantyx/content_realizer.py` is multi-clause, but it realizes the separate fiction/content IR (`content_realizer.py:1-9`, `content_ir.py:64-87, 155-206`):

```python
def atom_text(atom: Atom, narrator: str = "omniscient", budget: Budget | None = None) -> str:
def connector(plan: Plan, node_id: str) -> str:
def realize_plan(plan: Plan, *, expression_materials: tuple = (), budget: Budget | None = None) -> Realization:
```

`realize_plan` returns output-text clause offsets and expression-material spans (`content_realizer.py:81-142`, `content_ir.py:192-206`). Its relation shells can say `Cause` or `After` (`content_realizer.py:61-78`); those relations cannot be inferred merely from listing semantic source clauses.

### Semantic source and answer path

`semantic_ir.View` stores original source strings, parsed `Clause`s, unread spans, and indexes (`semantic_ir.py:100-123, 274-304`). A `Clause` carries predicate and role spans, polarity, modality, time, rule, family, sovereign, and unsupported reasons. `Span.valid(sources)` checks that its text equals the original source slice (`semantic_ir.py:21-32`). `document_view(documents, *, sovereigns=None, family='document')` creates that view (`semantic_reader.py:253-273`), one source sentence at a time (`semantic_reader.py:88-96`).

Semantic QA is request/plan/proof based:

```python
def answer(request, views, *, budget=Budget(), trace=()):
def license_clause(clause, view, ranges=None):
def gate(self, request, plan, proposals):
```

These are in `semantic.py:27-33`, `semantic_verify.py:264-280`, and `semantic_verify.py:753-766`. The checker independently licenses source spans and replays proofs. `answer` returns `kind='answer'`, `verdict='ANSWER'`, answer values, and per-source clause/span citations only after verification (`semantic.py:69-88`). Unsupported unread evidence currently refuses the semantic answer (`semantic.py:39-46`).

`Vera.__init__(..., mode='semantic', ...)` enables semantic mode, and `Vera.ask(self, question_text, *, query=None, mode=None, **engine_kwargs)` dispatches it to `_ask_semantic` (`one.py:66-99, 779-784`). `_ask_semantic(self, text, *, candidate_views=())` parses a semantic question and calls `answer` on a routed or retrieved `View` (`one.py:352-418`). The non-document path retrieves from a semantic `Request` (`semantic_retrieve.py:34-39, 78-90`); it does not accept an entity-summary request. Routing may narrow the view and is documented as able to lose derivations (`semantic_route.py:132-143`).

## What blocks the connection

- **Different data models.** `summarize` expects `store.crosses[subject][facet] -> count`, a vocabulary membership test, and `edges(subject, facets) -> pairs`. A semantic `View` has clauses and role terms, not those maps. Projecting clauses into lexical facet counts would silently invent a mapping and discard clause IDs, polarity, scope, and spans.
- **The crossing is an n-subject operation.** A single-entity profile is not an intersection across two or more paths. For a comparison of several entities, the intersection policy may fit; for one entity, the same operation would suppress facts unique to that entity.
- **An edge callback is not provenance.** The callback and output pair identify only two strings. Semantic provenance needs the exact supporting clause ID and original `Span`; same-sentence co-occurrence also must not be mistaken for a relation between separate clauses.
- **No compatible realizer input.** `realize` takes `Frame`; `realize_plan` takes content `Plan`/`Atom`, not semantic `Clause`/`View`. Content `ClauseSpan` offsets address generated text, while semantic `Span` offsets address original source. They must remain distinct.
- **The public semantic route is QA.** Its parser, `answer`, proof verifier, and result contract are for requests with answer obligations. Reusing it for generated summary text would incorrectly mark constructed prose as `ANSWER` or feed it back as evidence.
- **Retrieval is request-shaped.** With no loaded document bot, `Vera` calls `Retriever.retrieve(request)`. A summary request has no current retrieval contract, so the first safe slice is a caller-supplied or document-backed complete `View`.

### Reuse boundary

When the input really is a legacy `CrossStore` and the task is the same n-subject lexical crossing, `crossing_of` and the current mandatory-edge refusal plus whole-rank-group selection are reusable as-is. They are valuable policies for a semantic adapter to preserve. They are not a direct `View` adapter: semantic clauses have typed role values and per-clause spans, whereas the legacy result has facet strings, counts, and no source-citation record. In particular, a single-entity summary cannot reuse the intersection operation without changing its meaning.

## Minimal wiring design

Add a separate typed summary API, initially over a complete `semantic_ir.View`:

```text
EntitySummaryRequest(entity: exact string, limit: positive integer)
SummaryCandidate(clause_id, predicate, typed roles, polarity, modality, time,
                 family, sovereign, source_span)
SummarySelection(kept candidates, dropped rank groups, ranking rule)
SummaryClause(text, output_start, output_end, source_clause_ids, source_spans)
ConstructedSummary(text, clauses, verdict, constructed=true)
```

These are proposed names, not existing classes. The data crossing each boundary should be:

1. **View to selector:** the exact entity string, each canonical candidate's `Clause.id`, predicate, ordered `(Role.name, Role.term)` values, polarity/modality/time, family/sovereign, and `Clause.span` (plus role spans if the renderer needs them). Validate each span against `View.sources`. Keep supported facts separate by clause; retain negation, modality, time, and scope rather than flattening them.
2. **Selector to realizer:** only selected typed candidates, their canonical clause IDs/source spans, and explicit rank/drop metadata. For multi-entity summaries, a same-sentence pair license must include the supporting clause ID and span. Never synthesize a pair from clauses merely because they mention the same entity.
3. **Realizer to caller:** generated text plus generated-text offsets, each mapped back to one or more source clause IDs and original spans. Keep source offsets and output offsets as differently named fields/types.

Use `license_clause` or a summary-specific independent checker over canonical clauses before selection. Start from the full original `View`; a routed subset is not sufficient to promise a complete entity summary. Mirror the current unread refusal until a narrower relevance gate has its own independent check. Keep each rendered item as an independent assertion; use no causal/temporal connector unless a separately licensed semantic relation supports it.

Reuse `crossing_of` and the whole-rank-group loop only where their meanings remain valid. For a multi-entity comparison, a typed adapter may project explicit per-entity facets and clause-backed pair licenses, but the projected terms must be specified and tested. For a single entity, define a separate deterministic fact-selection score; do not relabel legacy crossing width/mass as semantic support. Preserve dropped candidate IDs/groups, not just the old aggregate count.

The summary result must be a constructed summary type/verdict, never `kind='answer'` or `verdict='ANSWER'`. Its prose is a rendering, not testimony; do not ingest it into `View`, proof sources, retrieval indexes, or evidence counts. `Vera(mode='semantic')` can expose a distinct summary method that obtains the original document `View`; retrieval-backed summaries need a separate bounded retrieval design.

## Test plan with independent gold

Create a tiny hand-authored source set and a separately written expected-facts sheet before running the implementation. A human annotator should record each expected predicate, entity/role, polarity, scope, source ID, and source character offsets directly from the raw strings. Do not generate expected facts, licenses, offsets, rankings, or rendered answers with `document_view`, `summarize`, either realizer, `semantic.answer`, or their serializers.

- Include an entity mentioned in multiple parseable clauses and sources, a negative assertion, an unsupported/unread sentence, and two distinct facts that share a surface facet but occur in different sentences.
- Check exact selected fact set and polarity against the sheet; every rendered clause must map to its independently listed source clause and source slice. Independently slice the original strings to validate citations.
- Supply a hand-labeled same-sentence pair oracle. Assert that a pair from separate sentences is never licensed and that an unlicensed pair leads to a typed refusal or omission.
- Give the ranker a manually specified tied boundary group. Check the whole group is either kept or dropped as capacity permits, and that the dropped group IDs are reported. This expected result is written directly, not obtained from `summarize`.
- Check that the surface has no added predicate, participant, polarity change, cause, or temporal relation; output offsets address only generated text; and the result is constructed summary data, not an answer/evidence object.
- Permute source insertion order and verify the selected facts and citations remain stable apart from explicitly documented display ordering.

## Risks, first measurement, and reach

The first failure to measure is **surface-to-source entailment**: for every rendered clause, compare predicate, roles, polarity, modality, time, and any connector against the independent gold for its cited clause. This catches a fluent connector, dropped negation, or role swap that an output-text span map alone would miss. Next measure completeness against the gold selector input, including unread clauses and every whole rank group at the cut.

The reachable first slice is supported clauses in a complete semantic `View` with an exact entity mention and source-valid role spans. It can produce a list of separately cited clauses. It cannot safely resolve aliases/coreference, merge paraphrases, decide which conflicting or time-scoped value is current, summarize unsupported/unread text, or claim that selected clauses exhaust retrieved material. A semantic retriever would need a summary-specific candidate request and a full-view completeness check before such a result could be called exhaustive.

No corpus coverage, quality, or latency figure is claimed in this scout. The small measurements for the first implementation should be counts from the independent fixture: gold-matching clauses, licensed same-sentence pairs, kept/dropped groups, source-span matches, and unsupported-source refusals. This run measures only the requested document-size acceptance check.
