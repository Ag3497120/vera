# Scout: polarity and the semantic path

This is a read-only scout of the current tree. The only run-based figures below come from a local probe over hand-written strings and the existing `polarity.regression()` entry point; they are not corpus coverage estimates. No development, sealed, heldout, fixture, or external corpus material was read.

## What exists

`verantyx/polarity.py` contains two related but distinct systems:

| Surface | Actual signature | What it returns / does |
|---|---|---|
| English aspect detector (`polarity.py:35-49, 439-461`) | `detect(sentence: str) -> List[Tuple[str, str, str]]` | Closed antonym vocabulary; returns `(aspect_key, value_word, polarity)`. English negators flip only a listed polar word. `on` and `off` require a preceding copula (`:125-141, 452-454`). |
| Japanese aspect detector (`:63-72, 98-188`) | `detect_ja(sentence: str) -> List[Tuple[str, str, str]]` | Uses the Japanese grammar data, aliases, and a term-local suffix check. It returns the same tuple shape. |
| Pole placement (`:191-205, 408-436, 620-721, 831-881`) | `_place_poles(store: CrossStore, sentence: str, core: str, hits: List[Tuple[str, str, str]], lang: str, claim: Optional[str] = None, context: Optional[str] = None) -> None`; `ingest_polar(store: CrossStore, sentence: str) -> Optional[str]`; `ingest_polar_ja(store: CrossStore, sentence: str, claim: Optional[str] = None, context: Optional[str] = None) -> Optional[str]` | Places aspect facets on a heuristic subject/core. `subject_of(sentence: str, word: str, lang: str = "en") -> Optional[str]` and `subject_is_core(sentence: str, core: str, word: str, lang: str = "en") -> bool` are approximations with conditional guards. `apply_polarity_gate(store: CrossStore, out: Dict[str, Any], query: str) -> None` changes the older route's answer to an unresolved-contradiction result when the asked aspect is contested. |
| Typed observed-negation reader (`:893-1002, 1185-1307, 1382-1484, 1540-1681`) | `observe_negation(text: str, *, lattice: Any = None, tokens: Optional[Iterable[Any]] = None) -> PolarityReading`; `fold_polarity(predicates: Iterable[str], text: str, *, lattice: Any = None, tokens: Optional[Iterable[Any]] = None) -> List[str]` | Extracts written Japanese negation, spans, and lemmas; handles lexicalized `ない`, double negation, embedded negation, and some prefixes. `fold_polarity` writes `¬`-prefixed predicate strings. |
| Absence boundary (`:957-1002`) | `inferred_from_absence(lemma: str) -> InferredNegation`; `polarity_key(observation: object, lemma: Optional[str] = None) -> str` | `ObservedNegation(kind, surface, lemma, span, context=None)` is distinct from `InferredNegation(lemma, reason="absence_is_not_negation")`. `polarity_key` rejects inferred or untyped input; absence cannot become a stored negative claim. |

`PolarityReading` has `verdict`, `observed`, `count`, and `category` fields (`:975-983`). Its sentence verdict is `positive`, `negative`, or `POLARITY_UNDECIDED`; observed items separately carry `kind`, source `surface`, normalized `lemma`, character `span`, and optional `context`. `_NAI_LEX` is a closed lexicalized-`ない` list (`:919-928`); `_UNDECIDED_PATS` catches modal/idiomatic mixes (`:900-913`). `_kunai_observations` folds `X-くない` to one observation of the `い`-adjective (`:1146-1162`); `_NU_BLOCK`/`_ZU_BLOCK`, `_lemma_is_real`, and `prefix_split_ok` guard homographs, fabricated lemmas, and prefix splits (`:929-932, 1100-1129, 1168-1182`). Noun-plus-`ない` can produce lemma `ある` with the noun in `context` (`:1245-1251`). `_raw_observations` and `_token_observations` merge raw and optional fugashi readings; `_counts_for_verdict` folds only the sentence-final cluster, while `observed` can retain embedded negation (`:1198-1307, 1382-1484, 1540-1567`). `regression() -> Dict[str, Any]` is at `:1684-1772`.

The semantic path uses a different representation and trust boundary:

| Surface | Actual signature | What it does |
|---|---|---|
| Source reader (`semantic_reader.py:99-249, 253-273`) | `_piece(source, raw, start, end, sovereign, family)`; `document_view(documents, *, sovereigns=None, family='document')` | Produces source-spanned `Clause` records and typed `Unread` spans. Japanese frame negation sets `Clause.polarity` to `'-'` only when `frame.negated` applies outside prohibition/obligation; copula parsing has its own explicit suffix rule (`:145-168, 234-247`). |
| Question reader (`semantic_reader.py:327-474`) | `_property_question(fragment, b, span)`; `_event_question(fragment, b, span)`; `read_request(text, budget=Budget())` | Builds typed `Request`/`Plan` objects. Event questions use `f.negated` for an explicit negative pattern or `whether-negative` relation (`:402-409`). Unsupported forms become a `Request` with `Unread`, not a guessed plan (`:471-474`). |
| IR (`semantic_ir.py:21-32, 86-123, 195-203`) | `Span(source, start, end, text)`; `Pattern(predicate, roles, polarity='+', modality='assert', time='', event=None)`; `Clause(..., polarity='+', modality='assert', ..., unsupported=())`; `Request(text, plans, obligations, covered, unread=(), stages=(), rules=())` | A source span must exactly match its original slice. Semantic polarity is a separate `+`/`-` field; patterns may additionally use `*`. There is no `ObservedNegation` field or antonym-as-negation field. |
| Producer and checker (`semantic_execute.py:29-40, 122-154, 198-207, 281-305`; `semantic_verify.py:264-280, 333-402, 523-601, 673-753`) | `bind(pattern: Pattern, clause: Clause, initial: dict | None = None, *, opposite: bool = False) -> dict | None`; `Producer.__init__(self, view: View, sovereign: str, meter: Meter)`; `Producer.run(self, plan: Plan) -> tuple[list[tuple[tuple, Proof]], dict]`; `Checker.__init__(self, view: View, sovereign: str, meter: Meter)`; `Checker.gate(self, request, plan, proposals)` | Matching checks predicate, roles, modality, time, and explicit polarity. The checker independently licenses clause text/spans and polarity, replays proofs, and detects applicable opposite evidence. |
| Public semantic answer (`semantic.py:10-19, 27-97`) | `refusal(verdict, reason, *, phase, request=None, trace=(), meter=None)`; `answer(request, views, *, budget=Budget(), trace=())` | Existing typed refusals include unread request, unsupported source, no evidence, contradiction, ambiguity, and budget outcomes. Only checked source clauses can yield `ANSWER`; distinct verified values abstain as `AMBIGUOUS`. |
| Semantic entry (`question.py:112-115`; `one.py:66-73, 352-418, 779-784`) | `read_semantic(text: str) -> Sourced`; `Vera.__init__(self, *, bot: Any = None, chat: Any = None, general: Any = None, library: Any = None, gap_path: str | Path | None = None, engine_compat: bool = False, round3_root: str | Path | None = None, mode: str = 'legacy', material_immutable: bool = False, material_root: str | Path | None = None)`; `_ask_semantic(self, text: str, *, candidate_views=()) -> dict`; `ask(self, question_text: str, *, query: question.Query | None = None, mode: str | None = None, **engine_kwargs: Any) -> dict` | `Vera(mode='semantic').ask(...)` calls `_ask_semantic`, which calls `question.read_semantic` and then `semantic.answer`. The ordinary `question.read()` path separately calls `polarity.observe_negation` (`question.py:347-359`); semantic reading bypasses that `Query` and its polarity field. |

## Local probe made for this scout

Run with the unit interpreter and the specified empty corpus-root setting. The direct probe used eight hand-written strings, three English `detect` calls, two Japanese `detect_ja` calls, and two semantic request parses. `polarity.regression()["pass"]` returned `True`.

| Input | Observed result |
|---|---|
| `水が流れない。` | `observe_negation`: negative; observed lemma `流れる`. |
| `この映画はつまらない。` | positive; no observed negation. |
| `知らない人が来た。` | positive sentence verdict, but one observed item for lemma `知る`. |
| `彼が来ないとは言えない。` | `POLARITY_UNDECIDED`; no observed items. |
| `危なくない。` | negative; one item for lemma `危ない`. |
| `The gate is not safe.` | `observe_negation`: positive with no items; `detect`: `('safe', 'not_safe', '-')`. |
| `The gate is dangerous.` | `observe_negation`: positive with no items; `detect`: `('safe', 'dangerous', '-')`. |
| `The gate is safe.` | `observe_negation`: positive with no items; `detect`: `('safe', 'safe', '+')`. |

The Japanese aspect probe returned `('安全', 'not_安全', '-')` for `この道は安全ではありません。`, but no aspect hit for `この道は危なくない。`. The two semantic request probes, `この道は危なくないですか？` and `この道は安全ですか？`, each produced zero plans and one `Unread("unsupported request grammar")`. These are probe outcomes for these strings only, not rates or a coverage estimate.

## What blocks connecting the two

1. **The values are not interchangeable.** `PolarityReading.verdict` is a folded sentence result; semantic `Clause.polarity` is an explicit assertion attached to a predicate, roles, modality, time, and exact spans. `POLARITY_UNDECIDED` is not the semantic wildcard `'*'`. A sentence-level `negative` cannot safely set every clause to `'-'`.
2. **The observed span does not establish semantic attachment.** `知らない人が来た。` demonstrates the gap: the sentence verdict is positive while an embedded `知らない` remains observed. `fold_polarity` counts all `reading.observed` items (`polarity.py:1658-1681`), but the semantic reader needs clause and role scope. Reusing its output as a `Clause` would risk negating the wrong predicate or subject.
3. **Antonym polarity is lexical opposition, not grammatical negation.** The aspect detectors map `dangerous` to the `safe` aspect's negative pole and `not safe` to a different value string on that pole. Semantic predicates do not currently normalize these words to a shared aspect. Japanese aspect suffix detection and typed `ない` detection also differ, as the probe shows.
4. **No semantic call currently receives these readings.** `read_semantic` directly calls `semantic_reader.read_request`; `Vera._ask_semantic` passes its typed request and semantic views to the producer/checker. The `CrossStore` aspect facets written by `ingest_polar` are not semantic `Clause` evidence.
5. **The verifier intentionally rechecks the original grammar.** `license_clause` checks canonical clauses, exact source slices, role spans, and source polarity (`semantic_verify.py:264-280, 333-402`). A detector result without a source ID, unique occurrence span, predicate alignment, and independently licensed role assignment cannot pass this gate. The aspect detector's tuple has no character span; `ObservedNegation` has one but no semantic role or clause ID.
6. **Question support is limited before verification.** The two current Japanese property questions above were unread by `read_request`; no polarity adapter can turn that into an answer without a separately licensed question grammar. Existing negative event-question support applies only when `_event_question` already parses a frame.

## Minimal typed, non-voting wiring design

Keep the semantic reader and its independent checker authoritative. Add a reader-side diagnostic adapter, with a closed result type such as `PolarityProbe` (a design sketch; no such type exists yet):

```text
PolarityProbe(
  source_span: Span,                 # source ID, exact offsets, exact original text
  target_predicate: str | None,       # existing parsed predicate lemma
  target_span: Span | None,           # existing Clause.predicate_span
  observed: tuple[ObservedNegation],  # kind, surface, lemma, span, context
  aspect: str | None,                 # curated aspect key, if a listed pair matched
  candidate_polarity: Literal['+', '-'] | None,
  status: Literal['matched', 'ambiguous', 'unread']
)
```

The exact crossing is limited to: the original source/question span; its parsed predicate and role spans if present; the `PolarityReading` verdict/category and observed tuples; and, for a closed antonym hit, the detector's aspect/value/polarity tuple. Preserve source identity on each span. The adapter does not send counts, ranking, votes, generated text, or inferred absence as semantic evidence.

At source ingestion, call `observe_negation` on the exact sentence slice and retain its result as a diagnostic. Treat it as matched only when the observation is inside one parsed clause and its lemma and span align with that clause's predicate/scope under a separate exact rule. The aspect detector has no hit spans, so accept a pair proposal only when the term has a unique occurrence inside that same licensed clause; otherwise mark it ambiguous. A mismatch, mixed scope, missing lattice split, or `POLARITY_UNDECIDED` leaves the source unread/unsupported and leads to the existing typed refusal path.

At question reading, retain the current direct plan path for already parsed `+`/`-` questions. For an unsupported but recognized negation or listed antonym, attach the diagnostic to the question span and return typed unread until a grammar rule creates and validates a `Pattern` with exact target roles. Do not prefix semantic predicates with `¬`; do not synthesize a `Clause`; do not pass aspect triples to `Producer` as candidate evidence. To answer antonym questions, a later closed rule must normalize both terms to one curated aspect while preserving the same entity/attribute roles, and the existing verifier must license both source clauses. Otherwise return `UNKNOWN_UNREAD` or `UNKNOWN_UNSUPPORTED_EVIDENCE` with the polarity-scope reason.

Missing a negative row remains `UNKNOWN_NO_EVIDENCE`; it never creates `InferredNegation`. An explicit opposing row remains subject to the semantic checker's conflict refusal. The diagnostic can refine refusal reasons and prevent an unsafe answer, but it does not vote, pool source counts, or license an `ANSWER`.

## Risks and first failure to measure

The first risk is wrong attachment, not merely a wrong sentence-level polarity label. The local probe already found one relevant shape: an embedded negation is retained even though the whole sentence is positive. First measure false attachments and missed attachments separately, with counts grouped by predicate/role scope, lexicalized `ない`, copula, embedded clause, double negation, modality, and antonym pair. For each case compare the diagnostic target against independently annotated source spans and semantic roles. The highest-severity failure is an incorrect negative claim that passes source licensing; the adapter must refuse on any disagreement.

Other risks are language mismatch (the typed `observe_negation` rules center on Japanese while `detect` has English negators), lexicalized exceptions drifting from the tagger, prefix recognition depending on a lattice, and duplicate/overlapping observations being double-counted. Do not use the old `polarity.regression()` output as the gold set; it is useful as a smoke diagnostic only.

## Independent test plan

1. Write a small fresh suite of source sentences and questions. Before running either detector, have two annotators independently mark exact sentence/clause boundaries, negation-token offsets, predicate lemma, subject/roles, scope, lexicalized-vs-productive use, modality, and whether a word pair belongs to the approved antonym table. Adjudicate disagreements and freeze the annotations as gold.
2. Include minimal pairs for positive/negative predicates, bare lexicalized `ない` versus productive `くない`, embedded negation versus clause-final negation, double and modal forms, noun-plus-`ない`, copula negation, prefix negation with and without a valid lattice split, and direct antonyms versus unrelated near-misses. Keep English and Japanese scores separate.
3. Run the source reader and the adapter on those inputs. Compare observed spans and semantic `Clause`/`Pattern` polarity against the frozen annotations, not against detector output. Require exact source-slice, predicate, and role alignment for every accepted match; ambiguous/mismatched cases must produce typed unread/refusal.
4. Run `Vera(mode='semantic')` on only the hand-authored source texts. Check that supported explicit negative clauses cite their original spans, opposite licensed clauses refuse as conflict, missing clauses remain unknown rather than negative, unread questions refuse, and tied verified values abstain. Inspect the proof/source spans independently.
5. Report false-positive attachment, missed attachment, typed-refusal coverage, and answer precision separately. Set acceptance thresholds before the run; do not relax a threshold to turn an error into a pass. No development, heldout, sealed, or fixture data is needed for this plan.

## Reach estimate

The measured probe is intentionally tiny: the polarity regression returned `True`; the eight observation strings exposed embedded, lexicalized, productive, modal, and English-detector differences; and both semantic property-question examples were unread. Those outcomes establish useful local failure shapes only, not system coverage.

The immediate safe reach is narrow: preserve answers for negation forms already parsed and licensed as explicit semantic `+`/`-` clauses, and provide better typed refusals when a recognized negation cannot be attached. A curated, source-licensed aspect rule could later answer listed antonym questions when the query and source use the same normalized entity/attribute roles and the checker verifies each original clause. The polarity module alone cannot make arbitrary negation scope, English semantic negation, open-ended antonymy, or property questions answerable; it cannot turn missing evidence into a negative fact. No broader reach estimate is justified by the probe.
