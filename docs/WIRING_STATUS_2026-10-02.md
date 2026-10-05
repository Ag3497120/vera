# Vera wiring status — 2026-10-02

## Scope and run record

This is an implementation audit of the semantic, construction, memory, vocabulary,
and conductor wiring present in this worktree. I read the permitted scout report
`docs/scout/s_agents.md`, then checked the in-worktree modules and the applicable
demos directly. The scout report predates this snapshot on one point: it says that
adapter and verifier units are absent, while `verantyx/agent_adapter.py` and
`verantyx/verifier_agents.py` are present here. Its warnings about absent process
supervision still match the current runner boundary.

I did not read restricted evaluation material or reuse previously reported metrics.
The demos below used constructed inputs and no live model call. The separately
named frame and memory demos were not run because they read files outside the
permitted reference list. No unit-test suite was run.

Observed demo output:

| Demo | Result from this run |
| --- | --- |
| `tools/demo_generate.py` | `DEMO OK` (0.108 s) |
| `tools/demo_outside.py` | `assertions: 270` then `DEMO OK` (0.067 s) |
| `tools/demo_conduct.py` | `DEMO OK` (0.372 s) |
| `tools/demo_vocab.py` | `DEMO OK` (0.069 s) |
| `tools/demo_system.py` | `DEMO OK` (0.180 s) |
| `tools/demo_band.py` | Failed at its first expected-answer assertion (0.077 s) |

The failed demo ended with:

```text
assert result["verdict"] == "ANSWER"
AssertionError
```

I reproduced that first query using the demo's constructed source and got:

```text
clauses 32 unread 0
{'verdict': 'UNKNOWN_NO_EVIDENCE', 'reason': 'no complete supported derivation', 'values': []}
trace_parts ['semantic_execute.Producer', 'semantic_verify.Checker.gate']
```

The required file-length acceptance command passed after writing this report;
the report is longer than the required minimum.

The failure matters: `demo_band.py` does not reach its later checks of the band
annotation, and `semantic_band.band()` currently always returns `None`.

## Capability matrix

| Capability | Observed status | Main limit |
| --- | --- | --- |
| General semantic understanding | Narrow source-backed queries work; one broader constructed query fails | Finite supported grammar, not general conversation |
| Free-text generation | Verified source clauses can be rendered and grouped | No open-ended prose generator |
| Generation outside closure | Typed structural candidates and marked template text work on a synthetic view | Candidate structure is not a definition or answer |
| Stereo-cross use for speed | `LeafTree` is connected to the semantic route | No speed benchmark was run in the allowed demo set |
| Frame → agents → verification → project run | A scripted fake adapter can run and resume deterministic tasks | No live agent, real verifier, worktree confinement, or code patch run was demonstrated |
| Typed memory | Append-only typed memory underpins frame and conductor code | Several `memory_*` helpers are standalone; testimony handling needs care |
| Vocabulary resolution | Exact, alias, and closed-choice paths pass a fake-asker demo | Lexical assets and model disambiguation were not exercised |

### General semantic understanding

- **What ran:** `tools/demo_generate.py` returned `DEMO OK`. Its source-backed
  Japanese query is passed through the semantic producer and checker, and the
  demo asserts a verified `ANSWER` before asking the realizer to speak it.
  `verantyx/one.py::_ask_semantic` parses a typed request, builds a semantic view,
  and calls `semantic.answer`; the producer and checker are deterministic stages.
- **What is wired:** `verantyx/one.py::_routed_semantic_view` supplies a routed
  view when routing can narrow it. Unsupported or unread input remains represented
  as typed refusal material rather than being treated as a negative fact.
- **What is stubbed or not demonstrated:** the agreement-band implementation is
  a stub returning `None`. `demo_band.py` fails before testing its later non-voting
  assertions. Its source and expected subject/value pairs are generated from the
  same `pairs` input, so even a passing loop would be a narrow constructed smoke
  check, not an independent general-understanding evaluation.
- **Limit and weak claim:** the semantic reader supports a bounded grammar. The
  passing query demonstrates one narrow pattern, not general semantic coverage.
  The failed `対象00` query shows that a hand-constructed set of readable-looking
  location sentences is not enough to establish a supported derivation.

### Free-text generation

- **What ran:** `tools/demo_generate.py` returned `DEMO OK`. It exercises answer
  realization, summaries, a two-entity comparison, plain/polite variants, source
  spans, connective licenses, and a polarity conflict refusal.
- **What is wired:** `semantic_realize.realize_clause`, `realize_answer`, and
  `summarize_entity` only select forms that pass round-trip and term-lineage
  checks. `semantic_generate.generate` assembles those checked sentences into a
  typed `GeneratedText`; its supported request kinds are answer, summary, and
  compare. Generated output remains `CONSTRUCTED`, not an `ANSWER` or evidence.
- **What is not wired:** this is not open-ended free-text composition. The older
  writer templates are not connected to the semantic answer path. The facade's
  `say` route realizes an already verified answer; it does not ask a model to
  invent a sentence.
- **Limit and weak claim:** the demo's documents and expected source buckets are
  hand-authored together. Equal projections across styles and different surface
  strings establish consistency checks, not an independent human judgment that
  arbitrary generated language preserves meaning.

### Generation outside the semantic closure

- **What ran:** `tools/demo_outside.py` printed `assertions: 270` and `DEMO OK`.
  It checks typed markers, source-resolving spans, candidate kinds, abstentions,
  and closed-choice disagreement behavior.
- **What is wired:** `semantic_unknown.unknown_candidates` adapts a semantic
  `View` into the older explain/lattice/vocabulary interfaces. `semantic_outside`
  turns a candidate into a marked, fixed-form explanation. Any optional chooser
  may select only a listed candidate or frame term; its choice is returned as
  testimony and does not rewrite the construction.
- **What is not established:** the demo hand-builds its clause roles and spans,
  and its `FakeAsker` follows a preset correctness schedule. It does not test the
  normal semantic reader on a real unknown word or measure an LLM's disambiguation.
- **Limit and weak claim:** a unit split or positional neighborhood is a
  structural candidate, not a lexical meaning. The generated Japanese strings
  are templates. The span checks prove that the demo's own spans resolve against
  its own constructed source text.

### Stereo-cross use for speed

- **What ran:** no in-scope demo measured `semantic_route.LeafTree` speed or
  compared routed answers against a flat baseline. `demo_system.py` returned
  `DEMO OK`, but its single-source question cannot exercise a useful multi-leaf
  narrowing route. Its checked `SharedIndex` build is navigation indexing, not a
  stereo-cross speed result.
- **What is wired:** `one.Vera._routed_semantic_view` caches a `LeafTree` for the
  current semantic view and passes its restricted view to the answer producer
  and checker. If routing cannot safely narrow, it returns the original view.
  `semantic_fast.SharedIndex` is used by `VeraSystem` for summary/unit navigation
  context, explicitly marked as non-evidence.
- **What is not demonstrated:** no permitted synthetic benchmark was supplied as
  a named demo here, and I did not run corpus benchmarks. No historical timing or
  recall figure is repeated in this status.
- **Limit and weak claim:** the presence of a tree and trace fields shows routing
  is connected, not that it is faster on a target corpus or equivalent on all
  queries. Common or unsupported anchors can fall back to the full view.

### Frame → agents → verification → project run

- **What ran:** `tools/demo_conduct.py` returned `DEMO OK`. It sends scripted
  questions through the frame, checks cited replies and escalations, uses a fake
  command-witness callback, simulates an interruption, and resumes the scripted
  run. `tools/demo_system.py` also returned `DEMO OK` using a `_DoneAdapter` that
  always emits a scripted `DONE` event.
- **What is wired:** `ProjectFrame` answers only from typed frame records and
  returns citations or escalation. `ConductorRun` parses closed agent events,
  verifies acceptance before writing task completion state, journals transitions,
  and refuses uncertain resume without an adapter recovery hook. Escalations can
  be recorded beside the frame through `conductor_escalate`.
- **What is only wired:** `CodexExecAdapter` accepts an injected runner and
  configures a read-only Codex session; it does not provide its own process
  supervisor. The verifier API accepts injected adapter sessions, but the demos
  supply no verifier. `VeraSystem.conduct` also requires a caller-supplied adapter.
- **What is missing:** the demo's agent and command runner are Python fakes, not
  Codex or a shell witness. There is no isolated writable worktree, OS-enforced
  path allowlist, pinned artifact snapshot, or real external verifier run in this
  unit. The driver takes GOAL tasks in frame order; it does not enforce the
  separate ORDER graph as a scheduler. Verifier identity strings are not process
  authentication, and file evidence references are not content review.
- **Weak demo claims:** the question events and their expected replies are built
  together in `_make_questions`; that is not a separately authored oracle. The
  completion witness is controlled by an in-memory readiness flag. These demos
  prove a fake-adapter protocol path, not a production agent project run.
- **Not run:** `tools/demo_frame.py` reads the separate canonical frame document,
  which is outside the allowed read-only references for this unit.

### Typed memory

- **What ran:** memory writes and reads are exercised within the passing
  conductor and vocabulary demos. The vocabulary demo uses `ScratchMemory` in
  memory; the conductor demo uses a temporary JSONL `Memory` store and cleans it
  up. Neither is the standalone real-fact memory demo.
- **What is wired:** `memory_frame.Memory` is an append-only typed JSONL log.
  Records have typed slots and optional witnesses, and memory questions go back
  through `Vera(mode="semantic")`. `memory_brief.compile_brief` is used by
  `ConductorRun` to send context-only records to an adapter.
- **What remains standalone:** `memory_lessons` is not imported by the run loop;
  `memory_merge` has no caller in the conductor path; `memory_revalidate` is a
  separate wrapper that patches `Memory` and `check_witness` at import time.
  There is no demo here exercising merge, revalidation, or lesson resolution.
- **Boundary concern:** `Memory._witness_supports` accepts `testimony` records
  into the semantic memory view, and `Memory.ask` returns ordinary semantic
  answers over those record sentences without returning their witness class.
  This can make testimony look like ordinary semantic evidence. In addition,
  `conductor_run._lesson` and `_write_task_done` generate records labeled with
  testimony witnesses. Those paths need review against the rule that constructed
  outputs are never testimony or evidence; the current demos do not settle it.
- **Not run:** `tools/memory_frame_demo.py` reads additional project, source,
  and result files outside the approved references, so I did not run it or reuse
  its embedded metrics.

### Vocabulary resolution

- **What ran:** `tools/demo_vocab.py` returned `DEMO OK`; its final assertion
  confirms all of its local checks completed. It covers exact match, refusal on a
  lone lexical redirect, human alias testimony, reordered closed choices,
  and alias correction.
- **What is wired:** `ConductorVocabulary.resolve` checks exact frame terms and
  active aliases before asking a closed-choice resolver. Lexical candidates are
  filtered to terms already present in the frame. `ProjectFrame._resolve_option`
  has a separate internal closed-choice path for agent options.
- **What is only an opt-in helper:** `ConductorVocabulary` is not called by
  `ProjectFrame.answer` or `ConductorRun`; callers must use it directly to get
  its sidecar alias/sense behavior. The demo supplies tiny sidecar mappings and a
  fake asker, not the production lexical assets or a live model.
- **Limit and weak claim:** the fixed fake asker always chooses its configured
  target. The demo validates that no new vocabulary is added and that two asks
  agree; it does not establish real-world sense coverage or model accuracy.

## LLM reach audit

The semantic answer path (`question.read_semantic` → semantic producer/checker)
and the realization/summary surface builders contain no LLM call. The outside
route's structure and sentence template are deterministic, but it can optionally
call the closed-choice asker listed below. These paths do not use a learned model
to produce an answer sentence or fact.

| Reach point | What the model can produce | Rule status |
| --- | --- | --- |
| `memory_frame.CodexAsker` through `Resolver` | A JSON choice index or `null`; two differently worded asks must agree after order change | Allowed closed-choice use when kept behind `Resolver`; the raw `CodexAsker` callable itself does not enforce that boundary |
| `Memory._alias`, `ProjectFrame._resolve_option`, `ConductorVocabulary`, `SemanticUnknownChoice`, optional `memory_lessons.LessonIndex` asker | A selection among supplied terms; retained as testimony | Allowed only as closed choice; all demos used fakes, no live Codex ask was made |
| `CodexExecAdapter` supplied to `ConductorRun` / `VeraSystem.conduct` | External agent events and text, parsed into bounded protocol events | Can fit the external-hands allowance outside semantic answering when driven by a human frame; no live runner is configured or run here |
| `verifier_agents.run_verifiers` with an LLM-backed `VerifierAgent` adapter | A `PASS` / `FAIL` decision plus an evidence reference | Not a closed-choice asker. It is stored as verification testimony but can gate project completion, so compliance with the strict no-model-decisions rule is unresolved; this branch was not run |
| Legacy `verantyx.agent.Agent.run` | Arbitrary model-authored `final` text | Violates the stated rule if used as a Vera answer path; reachable from `verantyx/cli.py` agent mode and `verantyx/vera_server.py` `/agent/run` with Ollama or JGen callbacks |
| `verantyx.module_forge.draft_module` | Python source from local Ollama | Separate code-authoring path with later module verification/human approval, not the semantic answer route; it is not the closed-choice path or a conductor-run hand in this unit |
| `tools/codex_corpus*.py`, `tools/llm_plus_vera.py` | Codex-produced corpus/tool artifacts | Human-invoked authoring utilities, not runtime answer paths; none was run here |

The intended closed-choice routes obey the no-new-word rule in their resolver
protocol, but `CodexAsker` is a general callable if invoked outside that
protocol. The Codex hands adapter is read-only and depends on an injected runner;
it is not a code-writing project agent. The verifier route asks for a model
decision and should not be described as independently proven merely because the
result is typed. The legacy `Agent` path means this repository is not compliant
with the LLM rule as a whole, even though the audited semantic facade's answer
path itself is model-free.

## Older-line connections and remaining work

There are narrow adapters into older components: `semantic_unknown` uses the
older explain/lattice and view-local vocabulary path; `semantic_generate` uses a
licensed connective renderer; `conductor_escalate` records refusals through
`gap_graph`, `growth_signals`, and remedy/coverage helpers; and
`conductor_vocab` can read meaning-asset sidecars. These connections do not make
the older writer, graded, polarity, stacked, reach, or meaning-descent routes a
general semantic answer path. The matrix above records what was actually run;
other corpus benchmarks and live model integrations were not run in this unit.
