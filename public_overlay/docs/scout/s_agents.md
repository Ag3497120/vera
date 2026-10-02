# Conductor with real project agents: scout

## Scope and what exists

This report is based on the current worktree. It contains `verantyx/conductor.py`, the semantic path, and `tools/conductor_sim.py`. It does **not** contain `phase2/commander/commander.py`, a `tools/commander` package, or files named `agent_adapter` / verifier units. `docs/CONDUCTOR_2026-10-02.md:58-65` also records that real adapters, verifier launch, and long-horizon recovery are not built. I cannot verify what the named external commander already does because its source is outside this worktree and this unit permits no outside reads. The commander notes below are therefore proposed integration points, not claims about its present implementation.

The conductor already has typed project records and conservative question handling. `install_conductor_kinds() -> None` registers `GOAL`, `ACCEPTANCE`, `ORDER`, `POLICY`, `ESCALATE`, `ALIAS`, and `VERIFICATION` (`verantyx/conductor.py:29-47`). `AgentQuestion` carries `id`, `text`, optional closed `options`, and optional `claimed_state`; `Reply` carries an `ANSWER`, `ESCALATE`, or `ASK_VERIFIER` kind, cited `record_ids`, reason/missing fields, and an optional verifier `spec` (`:49-81`).

Relevant current signatures, as declared in source:

```python
Memory.__init__(self, path: str, asker: Optional[Asker] = None, now: Callable[[], str] = lambda: time.strftime('%Y-%m-%dT%H:%M:%S'))
Memory.write(self, kind, author, witness=None, supersedes=None, **slots)
Memory.active(self, require_fresh=False)
ProjectFrame.__init__(self, memory: Memory | str | Path, *, asker: Optional[Callable[[str], str]] = None, command_runner: Optional[Callable[[Mapping[str, Any]], Any]] = None)
ProjectFrame.add_acceptance(self, task_id: str, item: str, *, witness_kind: Optional[str] = None, target: Optional[Mapping[str, Any]] = None, human_judged: bool = False, independent: bool = False) -> dict
ProjectFrame.answer(self, question: AgentQuestion) -> Reply
ProjectFrame.verify_claim(self, task_id: str, evidence: Optional[Mapping[str, Any]]) -> Reply
ProjectFrame.record_verification(self, acceptance_id: str, result: str, *, verifier_id: str, claimant_id: str, evidence_ref: str = "", template_id: Optional[str] = None, supersedes: Optional[str] = None) -> dict
Vera.__init__(self, *, bot: Any = None, chat: Any = None, general: Any = None, library: Any = None, gap_path: str | Path | None = None, engine_compat: bool = False, round3_root: str | Path | None = None, mode: str = 'legacy', material_immutable: bool = False, material_root: str | Path | None = None)
Vera.ask(self, question_text: str, *, query: question.Query | None = None, mode: str | None = None, **engine_kwargs: Any) -> dict
question.read_semantic(text: str) -> Sourced
semantic.answer(request, views, *, budget=Budget(), trace=())
```

`Memory` is an append-only JSONL log loaded by its constructor; active records omit superseded rows. Writes round-trip the canonical sentence through `semantic_reader.document_view` before appending (`verantyx/memory_frame.py:144-166, 188-238, 241-247`). `ProjectFrame` writes task/goal/policy records and its `answer()` handles a closed question set; unsupported or uncovered questions escalate, ties abstain, and protected actions always escalate (`verantyx/conductor.py:114-137, 192-204, 322-330, 374-408`).

`verify_claim()` checks each active goal acceptance using a file hash, text-in-file, git-commit, or injected command-exit witness. For an `independent=True` item it returns `ASK_VERIFIER` with a prompt and result schema; it does not start an agent. `record_verification()` stores a separate `VERIFICATION` testimony record and requires a different verifier id plus the expected template for independent reviews (`verantyx/conductor.py:332-371, 541-655`). Those checks compare caller-supplied ids; they do not authenticate a CLI process, require a nonempty `evidence_ref`, or establish that the verifier inspected the cited artifact. The command runner is injected and has no timeout or working-directory policy here (`:541-547, 605-630`).

The existing `tools/conductor_sim.py` is a simulator, not an agent runner: `build_frame(root: Path, asker=None)` constructs a fictional frame with a stub command runner, while `run_one(accuracy: int, verbose: bool = False) -> dict` scores scripted questions against its locally constructed case records (`tools/conductor_sim.py:71-86, 119-167, 268-321`). It does not invoke Codex exec or Claude Code.

The semantic answer route is separately typed. `Vera(mode='semantic')` dispatches through `Vera.ask()` to `_ask_semantic()` (`verantyx/one.py:66-100, 352-418, 779-784`). `question.read_semantic()` calls `semantic_reader.read_request`; the reader returns a `Request` containing plans, obligations, source spans, and typed unread spans (`verantyx/question.py:97-115`, `verantyx/semantic_reader.py:413-474`, `verantyx/semantic_ir.py:195-203`). `semantic.answer()` runs a producer then an independent checker over source `View`s and returns an evidence-bearing `ANSWER` only for one verified result; ambiguity, missing evidence, unread inputs, conflicts, or budget limits remain typed refusals (`verantyx/semantic.py:10-19, 27-97`). `Vera` routes original document text or reads the existing read-only semantic index; it does not schedule project work (`verantyx/one.py:216-235, 346-418`; `verantyx/semantic_retrieve.py:17-35, 87-102`).

## What blocks connecting the conductor to the semantic path

- There is no dispatch boundary: `ProjectFrame.command_runner` only checks an acceptance command supplied by its caller. No code here starts, polls, cancels, or reaps an agent process, and no adapter maps CLI events into `AgentQuestion` or `Reply`.
- Current `TASK` records store only a task name and state; the recognized states are `未着手`, `進行中`, `完了`, `停止`, and `保留` (`memory_frame.py:27-39, 207-238`; `conductor.py:322-330`). They do not record a run id, lease, pinned base revision, path allowlist, agent identity, deadline, diff, logs, or restart point. The append-only log is a useful persistence base, but it is not a crash-safe process supervisor or a complete run journal.
- The conductor’s control frame and the semantic IR are different contracts. The former answers order/policy/status questions from active frame records; the latter needs a parsed `Request`, source `View`, plan, and replayable `Proof`. There is no typed conversion from a project task or agent result into a semantic proof.
- `Memory.write()` uses the semantic reader as a round-trip check on record sentences, and `Memory.ask()` can ask those sentences through `Vera(mode='semantic')` (`memory_frame.py:196-205, 257-265`). That narrow bridge does not mean `ProjectFrame.answer()` uses the semantic proof gate. It is an askability check for the record language.
- Agent-produced patches, logs, and text are constructed outputs. They may advance orchestration state after separate checks, but they must not be converted into testimony, semantic `Clause`s, proof sources, or a Vera `ANSWER`. A command passing only establishes its declared process result; it does not establish the truth of generated claims. Keep runtime agent execution outside `Vera.ask()` so the no-LLM/no-runtime-learning goal remains intact.
- The semantic reader has a bounded supported grammar and explicitly returns typed unread inputs for unsupported requests. It is not a general task planner or a way to interpret arbitrary agent conversation (`semantic_reader.py:413-474`).

## Minimal typed, non-voting wiring

Keep the commander as a process service and the conductor as the deterministic project controller. If a commander API exists, the smallest useful boundary is a durable `launch / poll / cancel / recover` interface. The conductor decides which authorized task is ready, forms a typed request, and consumes a typed terminal event; it should not combine multiple agent opinions as votes. An inconclusive review abstains or escalates.

Proposed messages (new contracts, not existing source types):

```text
RunRequest = {task_id, attempt_id, backend_id, base_commit, private_worktree,
              allowed_paths, instruction_ref, acceptance_record_id, deadline,
              protocol_version}
RunResult  = {task_id, attempt_id, backend_run_id, status, exit_code,
              changed_paths, diff_digest, transcript_ref, question?, timestamps}
VerifyRequest = {acceptance_record_id, claimant_id, artifact_commit, diff_digest,
                 witness_spec, template_id}
VerifyResult  = {result: PASS|FAIL, verifier_run_id, template_id,
                 artifact_commit, evidence_ref}
```

Only these fields cross the boundary. `RunRequest` is derived from human-authored frame records plus a pinned repository snapshot; do not send the whole memory log or hidden credentials. `RunResult` is an untrusted report: the orchestrator independently reads the worktree diff and checks the path allowlist and process exit before changing task state. Transcript and evidence values are references to retained bytes/digests, not the content promoted into semantic evidence.

Use a strict, versioned event schema for agent questions. A valid request contains only the fields needed for `AgentQuestion(id, text, options, claimed_state)` and goes to `ProjectFrame.answer()`. A typed `Reply` may unblock a safe task; `ESCALATE` pauses it for a human. Malformed JSON, unrecognized fields, free-form follow-up instructions, or attempts to change scope are protocol failures that stop the run and escalate. Never infer a policy answer from ordinary agent prose.

Persist a separate typed attempt journal (or add carefully constrained conductor record kinds) before launch and after each observed transition. Track an explicit state machine such as `AUTHORIZED → READY → RUNNING → SUBMITTED → CHECKED → ASK_VERIFIER → VERIFIED`; failure, timeout, interruption, conflict, or missing evidence leads to a blocked/escalated state, not a success state. The present `TASK` record alone cannot safely encode leases or replay identity. Make writes idempotent by `(task_id, attempt_id, event_id)` and retain the pinned base commit, allowlist digest, child process identity, backend run id, deadlines, exit code, changed-path list, diff digest, transcript ref, acceptance id, verifier id, and evidence ref.

Before launch, create an isolated worktree at the pinned commit and enforce write access to the allowlist at the OS/container boundary. After submission, independently enumerate tracked, untracked, and renamed paths; reject any scope escape. Bound wall time, idle time, output size, CPU/memory/disk, and child-process lifetime; on timeout cancel the process group, reap descendants, preserve logs, and record a typed timeout. Do not rely only on post-run `git diff`: a process with ambient filesystem access can write elsewhere.

For acceptance, let `verify_claim()` check the deterministic witness. If it returns `ASK_VERIFIER`, dispatch the returned acceptance template against a frozen artifact snapshot to a separately launched reviewer with a distinct orchestrator-issued identity. Hide the claimant’s completion assertion and rationale; provide the human-authored acceptance spec and artifact to inspect. Validate the reviewer’s structured result and evidence reference, then call `record_verification()`. Only after all active acceptance items pass may the conductor mark the task complete. A verifier id string alone is not proof of independence, so the driver must bind it to a different process/account and reject duplicate backend run ids.

For resumption, reload the append-only frame and attempt journal, reconcile each attempt against the commander’s durable run id, current child process, pinned commit, and saved event cursor. If the process is gone or its state is uncertain, record interruption and do not replay the same side effect blindly. Resume the same backend session only when the commander can prove the session and artifact snapshot match; otherwise create a new attempt linked to the interrupted one. Re-run acceptance from retained artifacts and require fresh independent verification when the artifact changes. Partial/corrupt journal entries, duplicate events, or an unverifiable process state pause for human recovery.

## Human boundary and main risks

The human must author the goal, task decomposition, ordering, allowed paths/tools, acceptance criteria, and any authority-bearing policy. The human must decide open-ended or off-protocol questions, changes to scope or acceptance, conflicting reviews, judgments without a machine witness, and any protected external action such as publishing, deletion, spending, or credential access. A human also controls whether to merge/adopt the resulting artifact. Agents can prepare diffs and evidence references; they cannot authorize their own expanded scope or declare a project fact true.

Measure scope containment first: use an inert fake backend that attempts an out-of-allowlist write (including an untracked file and a symlink escape), then check that the write is blocked and the task cannot become accepted. This is the first failure to measure because a successful-looking result is untrustworthy if filesystem scope is not enforced. Next measure hangs and descendant cleanup, malformed/off-protocol questions, and crash recovery at each persisted transition. For every case, compare the observed event log and final state with a separately authored expected trace; check no duplicate acceptance, no unapproved changed path, no leaked response as an answer, and no orphan child process. Use a fake executable with known behavior, not either production agent, to make failure injection repeatable.

The test gold must come from a human-reviewed manifest written independently of the adapter and conductor: authorized task ids, exact base commits, allowed paths, acceptance targets, expected state transitions, and expected escalation reason. Keep the oracle outside the run journal; the code under test must not generate its own expected results. For semantic integration, have a separate human-authored source document and question with explicit expected source spans and verdict, then verify that agent-generated artifacts do not appear as `View` sources or semantic evidence. Also test a genuine supported source claim and an unsupported request so that `UNKNOWN` is never interpreted as a negative claim.

## Reach and limits

With the missing process and journal contracts implemented, this design could drive a bounded project whose tasks, permissions, and acceptance checks were written down in advance. It could safely ask real coding agents to propose changes, contain their edits, rerun deterministic checks, request a distinct review, and recover from recorded interruptions. `ProjectFrame` already supplies a useful policy/status/escalation vocabulary and returns an independent-review request; `Memory` supplies append-only records; the semantic path supplies an independent source-proof path for the narrow questions its reader supports.

This wiring would not make Vera a general autonomous project planner, make arbitrary agent prose into evidence, prove a patch correct just because a command passed, or replace human judgment where acceptance is subjective or consequential. It cannot be claimed to reach end-to-end operation until the absent commander/adapter/verifier sources are inspected and the lifecycle, confinement, and recovery properties are independently tested. I ran no agent integration or semantic corpus evaluation for this scout; the only check run for this deliverable is the mandated file-length acceptance check.
