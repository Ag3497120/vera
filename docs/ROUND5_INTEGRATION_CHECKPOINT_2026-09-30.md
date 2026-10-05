# Round5 partial integration — implementation and evaluation handoff

This record is an engineering handoff, not acceptance of the full project.
The original implementation CLI completed normally at approximately 11:48 UTC.
No corpus generator, pull or Wikipedia job was stopped. No commit, push, publish,
deployment, or external document transfer was performed by this integration task.

## Goal and current architectural gap

The user's latest priority is **general meaning understanding and free-text
generation as the shared foundation**, followed by construction beyond stored
complete examples. QA, code construction and complex document QA are applications.
The three experimental A/B/C routes do not by themselves demonstrate that shared
foundation. Broader conversation, metaphor, commonsense, humour, haiku and stories
remain goals, including where the current readers refuse them.

At 12:12 UTC the user defined "weights" as Vera's own **non-learning structural
parameters**, retaining a compressed and placed corpus. This does not authorize
neural training or runtime LLM calls. Compression must preserve provenance,
polarity, conditions, corrections and uncertainty. Compression ratio alone is
not a capability or correctness result. Existing generators and representations
must remain intact while alternative representations are tested independently.

A has typed source spans, clauses, role bindings and proof replay. B has its own
program contract/plan; C has its own constraint ledger/content plan. A common
source-to-meaning contract and demonstrated cross-domain semantic transfer are
still missing. Adding a common response envelope or router does not fill that gap.
The next shared layer should preserve unchanged source/hash/character spans,
entity identity, typed roles, world/scope, polarity, modality, time, conditions,
obligations and unread requirements. Each application must independently verify
its lowering; semantic equivalence must not be inferred from similar field names.

## Identity and preservation

- Source repository: `/Users/motonishikoudai/Projects/Verantyx-Vera-alpha`
- Branch: `integrate/one-vera`
- Base HEAD: `8b2732089a133300c365ce332eaf74de2a82fd29`
- Original session: `01a0f143-0a76-7280-b0b1-efdd49ac8d20`
- Original implementation task: `01a0f19c-f8ee-7110-85b1-21db1917facd`
- Integration workspace: `/Users/motonishikoudai/Documents/Codex/2026-09-30/task`
- Current integration candidate: workspace `semantic-scope-fix/`
- Final original snapshot before integration: workspace
  `validation/20260930T115502Z/checkout/`
- The twelve guarded source-file writes and hashes are in workspace
  `coordination/integration_applied.json`. Existing unrelated dirty work remains.
- Ongoing status: workspace `coordination/status.json`; B/C exchange contract:
  `coordination/bc_integration_contract.json`.

The source repository contains the validated A safety/material/scene fixes.
The separate `coordination/integration_round5_applied.json` receipt identifies
the later guarded B/C/router integration. If that receipt is absent, use the
frozen runtime rather than assuming the live repository has received it.
Do not overwrite the source from an older snapshot.

## Changes and evidence

A now retains unsupported content instead of dropping quantities, origins or
manner; preserves compound-verb tense; refuses interrogatives/volition as factual
assertions; and independently validates full antecedent position and content.
The proof checker rejects both borrowing a condition from a later sentence and
clipping an argument from the actual condition. Supported simple conditions and
sahen predicates retain their positive/negative controls.

The final A gate run passed 68 kernel, 10 reader, 22 public-entry, 4 retrieval
adapter and 55 compatibility tests. A separate run passed 67 safety/material/
scene/Round3 regressions: **226 passing tests** in total. The independent safety
audit reran 42 probes with no inappropriate answer or invalid guard acceptance,
and verified both new span attacks are rejected. These are regression tests,
not a measurement of general meaning understanding or held-out accuracy.

`doctor` returned OK. The original CLI's earlier health run was 89/89 forks,
47/50 measurements; missing frozen-binary and pruning-speed checks remained.
The integration checkpoint's own broad health run was cancelled for parent
load coordination after 977.13 seconds (exit -15); it did not pass. Only this
task's known three-process health tree was stopped. Other user jobs were kept.
Do not substitute the original run for this incomplete result.

`FamilyLibrary` now infers a single question slot for `who_did_what`, holding
unsupported or missing-context rows. Answering a synthetic scene requires
`ask(original_question, context=original_sentence)` with both unchanged. A
context-free question cannot promote that scene's answer to a general fact.
Existing indexes with inconsistent slots request rebuilding into a new version.

`MaterialSource.candidates` is a separate read-only composition-material reader.
It returns original payload, family, row, source, sha and `verified=False`, never
an answer. It uses existing separate-family indexes, bounded candidates and no
legacy `FamilyLibrary.ask` result. The actual approved small intake version was
copied with stable hashes into workspace `intake-smoke/candidate_20260930T1133`.
All 14 narrative/relation records were reachable with identity and provenance
retained. This is training-data connectivity, not independent evaluation.

Japanese parsing dependencies are declared in the `[ja]` extra. A clean isolated
wheel installation used Fugashi 1.5.2 and UniDic-lite 1.0.8, correctly answered a
simple sourced question and refused an unrepresented quantity while sockets and
subprocesses were blocked. Evidence is in workspace
`checkpoints/20260930T120433Z/wheel-smoke.json`.

## Observed development performance — below acceptance

The same immutable public 80-case development set was reused for diagnosis:

| Runtime | Correct | Wrong | Abstain |
| --- | ---: | ---: | ---: |
| Original A initial | 6 | 0 | 74 |
| Original A tense correction | 5 | 0 | 75 |
| Integration safety revision | 4 | 0 | 76 |

The latest decrease is a conservative refusal when a document contains a
nonassertive quoted instruction; the global unread-source policy prevents using
an otherwise answerable fact. This remains a capability gap. Keep every run.
No source fixture was modified and no sealed/heldout content was read.

For the integration run, uninstrumented `ask` wall time was median **1.214 ms**,
p95 **72.583 ms**, max **578.483 ms**. Initialization median was 2.722 ms and max
239.050 ms. These measurements are for the small public document fixtures under
concurrent development/generation load. They do not establish whole-corpus speed,
sublinear scaling, or historical microsecond claims. The earlier real-index A
smoke took approximately 138 seconds to initialize and broad queries exceeded
the 256-candidate limit. No budget or acceptance threshold was relaxed.

## B/C and the normal public route

Authoritative source documents:

- `docs/PREREGISTERED_2026-09-30_round5b_contract_plan.md`
- `docs/ROUND5B_PROFILE_CONTRACT_2026-09-30.md`
- `docs/PREREGISTERED_2026-09-30_round5c_content_plan.md`
- `docs/ROUND5C_GENERATION_DESIGN_2026-09-30.md`

The candidate's normal entry is `Vera(mode="round5").ask(raw)`. It obtains no
correct family/profile from the caller. It calls B's `is_code_request(raw)` and
C's `is_content_request(raw)`; a unique intent selects the component, overlap
is held, and neither selects A with the normally loaded document/QA sources.
Component refusal never falls back to a legacy answer. Explicit modes are
`semantic`, `contract` and `content`; the package default remains `legacy`.

B: `contract_codegen.generate_code(raw, cancel=None)`; the public adapter does
not pass a gold contract or profile. C: `content_api.ContentEngine(
material_source=MaterialSource(index_root)).ask(raw, materials=ordinary_sources)`.
Retrieved record payloads enter through the material reader; direct ordinary
materials are source/text mappings. C's `CREATED` means verified finite fictional
construction, not a factual `ANSWER` or assessed literary quality.

B's eight modules/four tests and C's seven modules/four tests were imported
without modifications from their owner manifests at 12:31 UTC. The public
router transport tests passed 13/13. Four light probes through the actual
engines reached A document ANSWER, B REQUIREMENT_UNREAD with no code, C CREATED
and C sourced ANSWER. They used one process, no children and blocked network.
These authored checks validate wiring, not accuracy or the 50 ms criterion.

The final all-module static pass also found an unchanged legacy truncated stub,
`verantyx/dialogue_context.py` (unterminated docstring, 18 lines). It is not
imported by the A/B/C paths exercised here and has no references in the package
source. Its identical original bytes are preserved and listed in the freeze
manifest. This prevents claiming that the entire package passes compilation;
all other selected Python sources compile. Repairing a stub's syntax alone
would not demonstrate its missing conversational capability.

A further training-material probe reached seven actual paraphrase records
through the C public route with original identity and verified=False retained.
The narrative query tested through that route returned no matching records;
the separate exact-variant reader test reached all seven narrative records.
Retrieval therefore remains query-dependent, and neither connectivity result
establishes that material improved generation quality.

B's initial real OS tests failed 6/6; its four raw requests produced zero
execution witnesses and zero ANSWERs. A later allocated minimal isolation
probe passed (parent 1/children 2, no retries, 71.07 ms excluding Python startup
and imports). This is not a full raw code-generation result or a 50 ms pass.
The 200 ms child and 1000 ms call limits were not relaxed.
Core 17, review 6 and sandbox-unit 22 tests passed in the owner's environment.
The lowering history includes 23 passes, then a 22-pass/1-error run and a
single repaired SQL-case pass; no latest whole-suite pass is claimed. Complete public-path isolation, whole-request latency, raw B80 and arbitrary code construction are
unmet. See `ROUND5B_INTEGRATION_HANDOFF_2026-09-30.md`.

C's owner ran 87/87 development tests in 3.49 seconds, one process, no children.
Its finite reader/plan/realizer is not general meaning/free-text capability.
The 4096-operation preregistration includes inner semantic operations that the
delivered counter does not cover. The one.Vera C adapter therefore explicitly
reports experimental=True, adoption_eligible=False, accounting_complete=False,
steps_known as a partial observed count and steps_total=null. This is an
experimental API, not a budget-compliant adoption result. Character limits do
not replace semantic-operation counts. Official C48/R/P/G/V/E remain unrun.
See `ROUND5C_INTEGRATION_HANDOFF_2026-09-30.md` and the accounting proposal.

The C codec is bounded reversible ledger storage. It is not live semantic
corpus compression or completion of Vera's non-learning structural weights.
The older edge compression loses event/time and complete source resolution;
the independent adapter work remains outside this frozen implementation.
See `STRUCTURAL_COMPRESSION_AUDIT_2026-09-30.md`.

## Independent evaluation scope fixed by the parent

Only **A document QA**, 120 unseen questions over ten newly authored documents,
is eligible for the requested independent preliminary evaluation. General QA,
B/code, C/free text, closure-outside construction, non-learning compression and
the four-group adoption are excluded. No sealed question content has been
provided to this implementation task. The full 120 denominator must preserve
correct, wrong, abstained, unrun and appropriate-refusal counts separately.
The existing 60% correct, <=15% wrong, zero instruction-following and median
uninstrumented ask <=50 ms remain comparison criteria; this preliminary run
does not replace the failed public-development adoption gate.

Construct once per evaluator document with
`Vera.from_texts({source_id: unchanged_raw_document}, mode="semantic")`, call
`vera.ask(unchanged_raw_question)` and then `vera.close()`. Do not pass a gold
plan, family, profile, prepared query or semantic labels. Ingest includes Bot
creation and semantic View creation; measure it separately from ask. Set
VERA_CORPUS_ROOT to the snapshot's empty-corpus directory so no live generated
or Wikipedia assets are consulted. The external input documents are owned by
the independent evaluator and hashed there after creation.

The sealed snapshot is
`/Users/motonishikoudai/Documents/Codex/2026-09-30/task/checkpoints/round5_partial_20260930_v1/runtime`.
Its sibling `manifest.json`, `environment.json`, `assets_manifest.json`,
`source_delta.json` and `source.patch` identify the exact version. Only their
actual presence and hashes constitute the freeze declaration. Later fixes
must go to a separate development copy and never change this snapshot.

## Reproduction and immediate next work

Use Python `/Users/motonishikoudai/Projects/vera-round5-run/env/bin/python` and run
from the chosen runtime directory. This environment has an editable installation
pointing at the original repository, so confirm `verantyx.__file__` resolves under
the intended runtime. Set `PYTHONDONTWRITEBYTECODE=1` and, for isolated checks,
`VERA_CORPUS_ROOT=/Users/motonishikoudai/Documents/Codex/2026-09-30/task/isolated-assets`.

```sh
python -m pytest -q tests/test_semantic_scope_safety.py tests/test_material_source.py tests/test_family_scene_scope.py tests/test_round3.py
python tools/round5a_verify.py --output validation/<new-gate-run>
python tools/round5a_evaluate.py --fixtures /Users/motonishikoudai/Projects/vera-round5-dev/fixtures.jsonl --manifest /Users/motonishikoudai/Projects/vera-round5-dev/manifest.json --gates validation/<new-gate-run> --output validation/<new-public-run>
```

Do not start broad suites or large subprocess groups without the parent's
execution slot. At 12:23 UTC the parent observed load 325/10 logical CPUs; later
Activity Monitor showed CPU 29.5% used/70.5% idle. Load alone does not establish
CPU saturation, and the reason for B child timeouts is not established.

Immediate next development: (1) reconcile raw source/meaning/plan contracts
across A/B/C, including correction, time, condition and uncertainty; (2) replace
global source-unread blocking with a proven independent scope rule, without
adding question-specific branches; (3) inspect B's OS probe under an allocated
single-probe slot; (4) implement and audit C's shared pre-operation meter before
adoption; (5) preserve all semantic/provenance fields in the separate non-learning
compression adapter and test placement invariance before connecting live data.

The reviewed intake29 and dedicated indexes are development material only.
Cloud180 (173 candidates/7 HOLD) and code100 (39/11 and 34/16 candidates/HOLD)
have not cleared the full-corpus duplicate gate and are not included in this
evaluation. Partial scans with zero matches are not completed duplicate checks.
No live producer output or production root was switched.
