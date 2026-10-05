# Round5-C integration handoff — 2026-09-30

## Scope and source

Implementation is an independent `git archive` copy of
`/Users/motonishikoudai/Projects/Verantyx-Vera-alpha` branch `integrate/one-vera`,
observed HEAD `8b2732089a133300c365ce332eaf74de2a82fd29`. The original dirty tree,
one.py, semantic/contract modules, libraries, corpus jobs, Wikipedia jobs and
CLI processes were not modified or stopped. No push, deployment, merge or
external content transmission was performed. Workspace-only pytest dependency
installation fetched public packages; it sent no project files.

Patch ownership: seven new `verantyx/content_{ir,reader,planner,realizer,verify,api,codec}.py`
and four new `tests/test_content_{api,planner,verify,codec}.py`. Health-check
generated reports in the copy are excluded from the patch. The baseline copy
has its own history and preserves original uncommitted changes by isolation.

README, CLAUDE.md, VERA_GOAL_AND_RESUME, Round5-C design/preregistration and
existing Frame/Event/conjugation/library code were read. No project AGENTS.md
or relevant project SKILL.md was found. `index search writer` and `index search
realize` confirmed reusable components. Nothing sealed/heldout was opened.

## API contract

```python
from verantyx.content_api import ContentEngine, is_content_request

engine = ContentEngine(material_source=reader)  # reader optional
result = engine.ask(raw_brief, materials=[
    {"source": "doc:1", "text": "...", "family": "local", "purpose": "evidence"}
])
```

The reader is injected without importing its module:
`candidates(family,text,limit=64) -> {verdict,records,reason,trace}` for
`narrative` / `paraphrase_entail`. This adapter requests **8 records per family**
by default (constructor range 1..64). Records retain family, row_id, source,
sha, payload, role and verified=False. Source text is projected from narrative
sentences/lines or paraphrase s1/s2/**sentence**. who_did_what.question/answer
are never treated as its premise. Independent sovereign traces are retained;
similarity/count/route scores never become fact votes.

`CREATED` / `kind=created` is licensed fictional construction. `ANSWER` is an
evidence-only explanation. `UNKNOWN_CONTENT_*`, `CONTENT_STATE_CONFLICT`,
`CONTENT_CONSTRAINT_CONFLICT` and `CONTENT_CONSTRAINT_VIOLATION` retain failure.
No failed C result should be replaced by a legacy stored-answer fallback.
Return data includes ledger/plan hashes, immutable contract projections,
surface spans, obligation checks, per-clause source roles, budget and ms.
Failed results do not expose a candidate surface as a successful realization.

Direct Source/mapping materials default to **expression**. Narrative and
paraphrase sources remain expression even if a caller marks them evidence.
Actual-world claims need full matching occurrence evidence from an explicitly
marked non-narrative source. Quote substrings cannot prove who said them.

`is_content_request` is a router hint, not a capability guarantee. `one.Vera`
integration and public mode naming belong to the integration owner and are
not implemented or evaluated by this patch.

## Implemented construction and limits

Raw brief → immutable constraint ledger → bounded plan → plan-only realization
→ independent gate. Existing Frame and conjugation rules are reused; the new
shells cover finite open/ownership/location states, quote and conditional
worlds, discourse and phase. Explicit case roles, polarity, tense, focal
viewpoint, Before/Cause, required/forbidden content, exact/max sentence count
and character limits are kept. Unknown mandatory text is retained and blocks
success. Conditional tense applies to antecedent and consequent. C1 refuses
Before/Cause across or inside conditional scopes until a richer relation
schema exists. It does not infer causality from adjacency.

The planner uses explicit work-local rules, checks all premises/exceptions and
replays exclusive state effects. Under explicit AUTHOR_CHOICE(events), missing
declared rule actions may be inserted to reach a requested end state; this is
more than returning a saved complete sentence. Rule interpretation/effect
ambiguity cannot be rescued by author-choice permission. A known different
state, a negative state, and an absent state stay distinct. A narrated state
must hold at its narration point. Initial/final phase positions are checked.

The finite clause reader covers explicit standalone Japanese clauses and
meta-instructions. It is **not general semantic understanding or general free
text generation**. Unrestricted briefs, long-distance anaphora, implicit
commonsense, rich viewpoint access, multiple discourse antecedents, metaphor,
humour, haiku joint search and literary quality remain incomplete. Quality is
unassessed. Novelty is `novelty_verified=False`; per-clause derivation can be
quotation/paraphrase/slot_substitution/provenance_unknown. No material or
new-composition producer flag is an independent novelty oracle.

The Atom/obligation/rule/source contract is a shared-meaning **candidate** for
future QA/prose/code adapters. It is not a collection of problem-name branches.
A/B adapters, native semantic operator equivalence and code realization are
not connected here. Fiction/actual/hypothetical/source boundaries are kept.

## Non-learning storage and structure

`content_codec.pack_ledger/unpack_ledger` is **reversible contract storage**:
bounded zlib, original sources, spans, roles, conditions, negation, rule and
obligation identities, permissions, unread spans and hashes round-trip.
Decompression bombs, trailing/truncated data, bad IDs/counts/base64 and wrong
input types are rejected. A ratio proves neither meaning compression nor
generation ability.

`structural_view` reuses Event role labels, carries world-scoped entity IDs,
tense, polarity, conditions, source/obligation identity and **obligation kind**
(required versus forbidden). Counts are non-learning **routing-only** structural
parameters, partitioned by world/kind; they add no facts and write no store.
The full ledger remains authoritative. No live corpus compression, cross
placement, conduct_tree retrieval optimization or structural weight pipeline
was replaced. Meaning compression and reconstruction from a compressed
sovereign remain unimplemented integration/research work.

## Verification and reproducibility

New tests are authored development checks, separate from independent C48 or
R/P/G/V/E adoption. The independent agent developed and froze counterexamples,
including false state assertions, conditional tense loss, rule-effect tie
rescue, attribution evidence loss, expression provenance mismatch, metadata
as extra-node permission, empty-payload/source bounds, recursive entity
counting, malformed auxiliaries, rule span binding and world-scope leakage.
The corrected normal cases also pass; universal refusal was not the oracle.
Evidence files and snapshot hashes are beside this report.

```sh
cd /path/to/integrated/repo
PYTHONPATH=/Users/motonishikoudai/Documents/Codex/2026-09-30/task-8/pytest-runtime python3.11 -m pytest -q tests/test_content_api.py tests/test_content_planner.py tests/test_content_verify.py tests/test_content_codec.py
python3.11 -m py_compile verantyx/content_*.py tests/test_content_*.py
```

Tests run as a single Python process, no workers and no subprocess execution.
See `round5c_pytest.log` and `round5c_manifest.json` for final results/hashes.
Python3.11 and the existing local fugashi/UniDic grammar runtime are used.
Runtime model/effort/service-tier cannot be independently observed by this
executor; the parent requested gpt-6.1-sol/max/priority. No LLM/API/learning
appears in the content runtime.

Baseline copy doctor: **OK**. Baseline guard: **89/89 forks, 47/50 measures**;
V5 frozen binary missing, V24 propagates earlier failures, V42 failed timing
under concurrent load. These are separate from content tests; no all-green
health claim is made. No second broad suite was launched after load steering.

Fixed character/size bounds follow the C draft (1200 brief, 12000 material,
800 output, 4 entity/world, 8 event/depth, 16 nodes, 32 parse/surface candidates,
256 candidate/plan, 64 frontier, 4096 C steps). **Accounting gap:** existing
Frame/morphology internals are character-bounded but not included in C step
counts, as declared in Budget. The preregistration's all-inner-loops definition
must be reconciled and independently audited before adoption; the patch does
not silently declare that condition satisfied.

Remaining gates: one.Vera/router integration, API/mode freeze, preregistered
inventory/selector/accounting fixation, independent C48/gold/quality evaluation,
relative novelty check and public latency/memory validation. No C adoption,
new sealed pass or publication success is claimed.
