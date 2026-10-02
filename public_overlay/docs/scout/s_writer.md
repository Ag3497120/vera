# Scout: writer forms and connective rendering for clause realization

## Existing surfaces

`verantyx/writer.py:9-14` describes the corpus-built Writer inventory and
`Writer.build()` records its actual form count in `w.built["forms"]`
(`verantyx/writer.py:103-141`). The header count is a build snapshot, not a
runtime guarantee. Forms are harvested from the supplied prose, so a different
corpus can produce a different inventory.

The relevant signatures are:

```python
Writer.build(cls, stores: Iterable[Any], prose: Sequence[Tuple[str, str]], *,
             statutes: Optional[Iterable[Path]] = None,
             norm_corpora: Optional[Iterable[str]] = None) -> "Writer"
Writer.sentence(self, store: Any, subject: str, *,
                limit: int = 1) -> List[Dict[str, Any]]
Writer.passage(self, store: Any, seed: str, *, steps: int = 6,
               mode: str = "path", trace: Optional[Trace] = None) -> Dict[str, Any]
harvest(texts: Iterable[Tuple[str, str]], *,
        head_only: bool = True) -> Dict[str, Form]
compose(forms: Dict[str, Form], subject: str, facets: Sequence[str], *,
        limit: int = 3, content_from: Optional[Sequence[str]] = None,
        vocab: Optional[Any] = None, licence: str = "unknown",
        roles: Optional[Dict[str, str]] = None,
        order: Optional[Dict[str, int]] = None, tail: str = "") -> List[Draft]
```

`Writer.build` learns the vocabulary, slot-selection counts, joins, and forms
from the same labelled corpora (`writer.py:118-140`). `Writer.sentence` takes
one store subject and its facets, then calls `compose` with the subject as
content provenance and `Writer.licence(subject)` (`writer.py:89-101,143-159`).
`Writer.passage` calls `trace.walk` before asking for a sentence at each path
item (`writer.py:161-185`). That passage path is the lexical walk to leave out.
Direct `sentence`/`compose` do not walk the store, but they still recombine a
subject and facets; they do not realize a semantic clause.

`Form` holds a template, per-hole cases, per-hole `(particle, predicate)` slot
keys, count, example, and source (`compose_ja.py:421-433`). Its `polarity`,
`modality`, and derived `register` properties inspect the shape itself
(`compose_ja.py:440-497`). The register labels are `norm`, `record`, or
`unknown`; `Form` has no separately stored register field. Modality detection
forces a form into `norm`; otherwise `fusion.register_of` classifies selected
sentence endings. That classifier explicitly describes itself as narrow and
may return `unknown` (`fusion.py:240-256`). This is a coarse document/register
filter, not a conversational-style selector.

`compose` has useful safety gates: `fits` checks basic term shape and typed
hole cases (`compose_ja.py:608-631`); optional vocabulary filtering removes
unattested words (`compose_ja.py:691-700`); a norm form is skipped unless the
content licence is `norm` (`compose_ja.py:722-726`). Where a slot key exists,
`selects(noun, particle, verb)` returns true, false, or unknown from learned
counts, and a well-observed rejection is not filled (`compose_ja.py:287-312,
361-383,767-785`). It also checks corpus-observed character joins at filled
template seams (`compose_ja.py:796-805`). These are useful filters, but the
subject-plus-facets input and first-compatible-fill loop do not bind a
semantic predicate and its named arguments (`compose_ja.py:657-669,691-795`).

`Writer.licence` selects `norm` or `record` from the corpus that most attests
the subject, falling back to `unknown` (`writer.py:89-101`). This is not the
semantic `Clause.modality`, and it must not decide what a verified clause
means.

`verantyx/connective_render.py` has two public entry points:

```python
render_diff(diff_result: Dict[str, Any]) -> Dict[str, Any]
render_summary(summary_result: Dict[str, Any]) -> Dict[str, Any]
```

`render_diff` consumes a structural-diff record with verdict, sides, coverage,
and `only_a` / `only_b` / `shared` buckets. It returns text plus the items,
tails, and per-connective license records (`connective_render.py:417-530`).
`render_summary` accepts the older kept-claim bundle (`connective_render.py:533-580`).
The closed table licenses `そして` within a bucket, `また` for shared-bucket
lead-in, and `一方` for a bucket transition (`connective_render.py:129-145`).
`しかし` is absent from that table: its sole constructor refuses an empty
observed-negation pair list and validates each marked/unmarked pair
(`connective_render.py:308-329`). These are licenses for those structural
relations, not freely swappable words for any two clauses.

## What blocks the semantic connection

The semantic source object is richer and different. `semantic_ir.Clause`
contains a predicate, named `Role` values and source spans, polarity,
modality, time, conditions, exceptions, sovereign/family, and unsupported
reasons; `Clause.pattern()` makes a predicate/role/polarity/modality/time
`Pattern` (`semantic_ir.py:78-124`). `Clause` has no surface-register field.
Writer holes instead contain case labels and optional learned noun-slot keys.
There is no checked mapping from a semantic predicate and each named role to a
particular harvested `Form`, or from a connective-render bucket to a semantic
relation.

The semantic path currently has no realization hook. `Vera.__init__` accepts
`mode="semantic"`, and `Vera.ask(question_text, *, query=None, mode=None,
**engine_kwargs)` dispatches that mode to `_ask_semantic` (`one.py:66-99,779-784`).
`_ask_semantic` parses a question, obtains views, calls `semantic.answer`, and
returns its result (`one.py:352-418`). `semantic.answer(request, views, *,
budget=Budget(), trace=())` runs the producer and `Checker.gate`, then returns
an `ANSWER` only for checked proofs (`semantic.py:27-88`; gate:
`semantic_verify.py:753-765`). It does not call Writer or a surface renderer.
The semantic request reader also refuses generation/action speech acts rather
than treating them as semantic QA (`semantic_reader.py:413-423`).

The two paths therefore cannot be joined by handing a generated sentence back
as another semantic source. `document_view(documents, *, sovereigns=None,
family='document')` parses strings into source-bearing `Clause`s in a `View`
(`semantic_reader.py:253-273`); a generated string passed there would acquire
source spans and could look like testimony. `semantic.answer` counts clauses
in its supplied views when building proofs (`semantic.py:39-59,69-88`). A
round-trip parse must stay isolated and must never enter the evidence views.

There is also a shape mismatch on the connective side: `render_diff` expects
the older diff schema and coverage counts, not a list of semantic clauses or
proof edges. The `Join` operator is a proof operation, not by itself a
linguistic connective license (`semantic_ir.py:157-180`). The existing
`connective_render` license records cannot be inferred from mere clause
adjacency.

## Minimal typed, non-voting wiring

Add a small adapter after proof verification, not inside retrieval, parsing,
or the checker. Its input should be a `RealizationRequest` carrying:

- the already checked `Clause` or `Pattern` values, including predicate,
  role names and terms, polarity, modality, time, conditions, and exceptions;
- source clause IDs, exact source spans, and the verified proof reference that
  supports those clauses;
- an explicit `SurfacePolicy` with permitted Writer register labels. Do not
  infer a user's requested style from `Writer.licence` or from the truth of a
  clause;
- for linked clauses only, an explicit typed connective license and the two
  clause IDs it relates. Do not turn adjacency or `Join` into a license.

The first adapter should accept source `Clause` values only. A bare
`Pattern` lacks clause spans, conditions, exceptions, and evidence
provenance; deriving a new proposition for realization needs a separate typed
request contract. The Writer adapter should return a `ClauseDraft`, not an
answer: text, the source clause ID, template and form-source ID, selected
register, role-to-hole mapping, and any connective license IDs. It should
enumerate only forms whose
hole cases and predicate/role mapping are explicitly compatible. It must
preserve polarity, modality, time, conditions, and exceptions; forms whose
shape adds or removes any of those properties are rejected. Unknown mappings
abstain. Do not pass arbitrary facets to `compose`, and do not call
`Writer.passage`, `compose_walk`, or `trace.walk`.

For connective rendering, pass a typed edge such as `WithinBucket`,
`SharedLeadIn`, `BucketTransition`, or `ObservedNegationPair` only when the
upstream structure actually supplies that relation and its source clause
IDs. Return the connective string with its license record. `しかし` requires
the checked observed-negation pair; it is not an alternative style choice.

The round-trip checker should take the `ClauseDraft` and return a separate
`RealizationCheck` with parsed-back typed clauses, compared fields, and a
typed refusal reason. It may call `semantic_reader.document_view` on a
temporary one-source mapping, then compare predicate, roles, polarity,
modality, time, conditions, exceptions, and clause count against the input.
It must reject unread/unsupported parse results, role loss or addition, and
any extra semantic content. Keep that temporary `View` out of Vera's real
views and discard it after comparison. Neither `ClauseDraft` nor
`RealizationCheck` carries `kind="answer"`, an answer verdict, or evidence;
the original verified result remains unchanged. The adapter is a renderer
and checker, not a voter in answer selection.

## First risk and measurement

The first failure to measure is semantic round-trip drift: a template may fit
the case labels yet alter the predicate, argument roles, negation, modality,
or time when the existing reader parses it. Track exact-structure successes
and typed abstentions separately from mere template fillability. The next
risk is reach: many harvested forms have no sound mapping to a semantic
predicate/role tuple, and the current semantic reader supports only a subset
of Japanese clauses.

I ran a small fresh-process probe using four authored sentences as input to
`harvest`. It returned three distinct forms: one `record`, two `unknown`; all
three had modality `none`, so this probe produced no norm-classified form.
This is only a toy check of extraction/classification, not a corpus coverage
estimate or a semantic gold set. It demonstrates why the source header's
corpus snapshot must not be treated as reachable semantic variation.

## Independent test plan

Create gold cases by hand from typed predicate/role/polarity/modality/time
records, reviewed independently of Writer and `semantic_reader`; include
explicit expected role terms and scope. Do not generate expected structures
by parsing Writer output or call `Clause.pattern()` to define the test gold.

For each gold clause, request each permitted register variant and round-trip
every resulting draft through an isolated `document_view`. Compare the
parsed-back fields to the hand-authored gold, require exact source spans,
reject extra clauses and unread spans, and check that each draft retains its
form-source provenance. Include negative, obligation, time, condition,
exception, quantity, and unsupported-scope cases. For a connective case,
hand-label the relation and supporting source clauses; assert the exact
connective/license pair, then parse the full linked text and compare its
clause set and relation to the gold. Include missing-license and empty
negation-pair controls that must abstain.

Finally assert that generated text is never added to the semantic source
`View`, never appears in answer evidence, never changes the original
`semantic.answer` verdict or proof, and is always returned as a typed draft
or typed refusal. Human reviewers should separately assess whether accepted
register variants sound natural; semantic equality alone does not establish
fluency.

## Reach estimate

The reachable slice is the intersection of templates with an explicit
predicate/role mapping, compatible case and selection gates, unchanged
modality/polarity/time/scope, and an exact isolated round trip. The connective
slice is limited to explicitly represented structural relations already
licensed by the closed table. This can provide conservative surface variants
for clauses covered by those mappings. It cannot supply arbitrary Japanese
paraphrases, infer missing facts, make an unsupported clause readable, turn a
proof operation into discourse meaning, or produce an `ANSWER` from generated
text. No corpus-wide reach estimate is justified by the toy probe; that needs
the independent gold set and a measured corpus build.
