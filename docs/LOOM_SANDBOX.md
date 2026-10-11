# LOOM_SANDBOX — running a task through the loom (L1 subagent, L2 API driver, scripted)

Implements docs/LINE3_LOOM_DESIGN.md §7 (L1/L2/L3/L4), §9 (sandbox, harness), §10.1 (task bank, controls). Decisions: docs/LINE3_LOCAL_DECISIONS.md `## LOOM-e（砂場・駆動器・採点）`.
Nothing here runs a model by itself; the numbers of §10 exist only after the operator has run the tasks below.

## 1. What is in the repository

| file | what |
|---|---|
| `.mcp.json` | registers the stdio server `vera-loom`: `<project python> -m verantyx.cli loom mcp --tasks experiments/line3/loom/tasks_bank2.jsonl --runs-dir experiments/line3/loom/runs --isolated`, `env` = `PYTHONPATH=.`, `PYTHONHASHSEED=0`, `PYTHONDONTWRITEBYTECODE=1`. `--isolated` (LOOM-d2, L-LOOM-93) makes the server prove the macOS `sandbox-exec` profile `tools/loom_isolation_profile.sb` with a probe and only then re-execute itself inside it (no network, reads only the task bank / corpus / fixtures / the `verantyx/` source, writes only the runs dir); a probe that does not pass => the server does not start (exit 3, a typed JSON line on stderr). The relative paths need **cwd = the repository root** (Claude Code starts a project server in the project folder) |
| `.claude/agents/loom-weaver.md` | subagent for tasks whose mode is `constructed_allowed` (`model: haiku`) |
| `.claude/agents/loom-weaver-record-only.md` | the same for `record_only` tasks |
| `.claude/agents/loom-control.md` | the free-text CONTROL (tools: `begin`, `lookup`, `read_sentence` only; its final text is scored; labelled `control`) |
| `experiments/line3/loom/tasks_bank2.jsonl` | 30 tasks: the ten tasks of design 10.1 × (`record_only`, `constructed_allowed`, `free_text`). **No gold.** The server serves it; the gold is read from `experiments/line3/bank2/bank2.tsv` by `score.py` only |
| `experiments/line3/loom/harness.py`, `score.py` | the harness (CLI) and the scorer |
| `verantyx/loom/driver.py` | the L2 API driver (no SDK import; the real client is made in `harness.py`) |
| `experiments/line3/loom/runs/`, `results/` | the OPERATOR folders: what the MCP server writes (run folders = the ledgers) and `results/<base>.<mode>.<driver>.json`. No scripted run is ever written here; `find` and `score` default to them |
| `experiments/line3/loom/baseline_scripted/{runs,results}/` | the 30 scripted baseline runs: gold-informed scripts, a harness check and not a measurement (its README says so); the default folders of `--driver scripted` only |

Task ids: `bank2/I2-041.record_only`, `bank2/I2-041.constructed_allowed`, `bank2/I2-041.free_text` (the control; server-side its `mode` is `record_only`, the harness reads its `control` flag; the control agent is told to ignore the mode).

Differences from the design text, on purpose: the agent files are named `loom-weaver*` / `loom-control` (the ticket), not `vera-loom-weaver` / `vera-loom-control`; the server's flags are `--tasks` and `--runs-dir` (the CLI of the core), the corpus is named by each task; the L2 driver is in `verantyx/loom/driver.py` as designed but takes the client as an argument so that the confined package imports no SDK.

## 2. One restart is needed (the owner does this once)

`.mcp.json` and `.claude/agents/*.md` are read when a Claude Code session **starts**. A session that was open before the files existed does not see them.

1. Make sure the session will run in the repository that holds these files (merge `line3-loom-e`, or start `claude` in that worktree). The folder must have `.mcp.json` at its root and the venv python named in it must exist (`/Users/motonisihikoudai/vera-wiring/env/bin/python`; edit `command` on another machine).
2. End the current session (`/exit`) and start a new one: `cd <repo root> && claude`.
3. Claude Code asks whether to trust the project MCP server `vera-loom` (it comes from `.mcp.json`): approve it.
4. Check: `/mcp` shows `vera-loom` connected with **18 tools** (the server now starts through `--isolated`: if it does NOT connect, run the command by hand, below, and read the one JSON line on stderr: `isolation_failed` names the probe property that does not hold, `isolation_unavailable` / `sandbox_exec_missing` says there is no `sandbox-exec` here; a run made through the sandboxed server says `isolated: true` in the `begin` result and in its `meta.json`); `/agents` lists `loom-weaver`, `loom-weaver-record-only`, `loom-control`. The tool names the subagents use are `mcp__vera-loom__begin`, `…__lookup`, `…__read_sentence`, `…__add`, `…__open_cross`, `…__seat`, `…__seat_run`, `…__unseat`, `…__swap`, `…__extend`, `…__topic`, `…__set_depth`, `…__link`, `…__unlink`, `…__read`, `…__emit`, `…__abstain`, `…__status` (verified by starting the server and listing its tools; `tests/line3/test_loom_harness.py`).

If the server does not connect: run the command of `.mcp.json` by hand from the repository root (`PYTHONPATH=. <python> -m verantyx.cli loom mcp --tasks experiments/line3/loom/tasks_bank2.jsonl --runs-dir /tmp/x --isolated`; drop `--isolated` only to tell a sandbox problem from a server problem); it waits on stdin when it works.
When the repository is merged forward from a tree whose `.mcp.json` has no `--isolated`, the one change is `"--isolated"` appended to the `args` of `vera-loom` after the `--runs-dir` value; Claude Code reads `.mcp.json` at session start, so restart it again (steps 2-4).

## 3. Running a task through the L1 subagent (the operator's session)

The Python harness cannot call the Agent tool, so the operator's session does, around the harness steps. For each task and mode:

```
python experiments/line3/loom/harness.py prepare --task I2-041 --mode record_only      # prints the Agent call and the steps; writes nothing
```
1. In the session call the Agent tool: `subagent_type: loom-weaver-record-only` (`loom-weaver` for `constructed_allowed`, `loom-control` for `free_text`), `model: haiku`, `prompt: "task_id: bank2/I2-041.record_only"`. The prompt carries the task id only; the question comes back from `begin`.
2. **The parent session still receives the subagent's final message** (Claude Code returns it as the Agent tool's result; nothing in this build removes it, only the L2 driver does, design 7.2). Do not read it back to the user, do not quote it, do not act on it. The agent's id is in that result (`agentId`).
3. **The mechanical path (recommended).** Claude Code writes the subagent's transcript to `~/.claude/projects/<slug>/<session>/subagents/agent-<agentId>.jsonl` (`<slug>` = the session's working directory with `/` replaced by `-`; `<session>` = the session id; an `agent-<agentId>.meta.json` sits next to it; it names the parent's Agent `tool_use` id (`toolUseId`), which is how to pick the right file among several). Then:
   `python experiments/line3/loom/harness.py note --subagent-transcript PATH --requested-model haiku`
   It (a) takes the run id from the result of the subagent's one `mcp__vera-loom__begin` call and opens `runs/<run_id>` (no search, no heuristic; it prints `RUN_DIR=...`), (b) takes the control flag and the expected agent from row 0 of that ledger and the bank (a `--control` on a run that is not a control, or an `--agent` that is not the bank's agent for the mode, is refused: `control_mismatch` / `agent_mismatch`, nothing is written; both flags are optional), (c) hashes the final assistant text from the transcript (`free_text_dropped`: sha256 + length; for the control `free_text_control` with the text), writes `harness_meta` (driver `L1-subagent`, the requested model, the sha256 of the agent file, and the provider's `model` from the transcript as `response_model`, all testimony), and (d) **checks T-LOOM-34 automatically**: every `tool_use` name in the transcript must start with `mcp__vera-loom__`, and the ledger may not hold more model rows than the transcript holds loom calls (a surplus means someone else called the loom on this run). The verdict is written to `runs/<run_id>/transcript_check.json` (outside the chain, like `meta.json`) and into the results file as `t_loom_34` (`pass` / `violations` / `unchecked`) and `transcript_check`; violations are printed and make `note` exit 1 (the rows are still written; a run with `violations` is not a clean L1 run and is reported as such).
   The transcript format is Claude Code's, not documented; what the parser reads is pinned in `harness.TRANSCRIPT_PIN` and any other shape is a typed refusal (`transcript_shape`, `transcript_unfinished`, `transcript_no_final_text`, `transcript_no_begin`, `transcript_multiple_begins`, `run_folder_not_found`, ...). If it fails on a new Claude Code version, use the by-hand path.
4. `python experiments/line3/loom/harness.py close RUN_DIR` (appends `abandoned` if the subagent left the run open; for a control add `--reason control_free_text`).
5. `python experiments/line3/loom/harness.py score RUN_DIR --driver subagent` → verify (chain + replay) → output → score → `results/I2-041.record_only.subagent.json`. A run that does not verify is `run_not_verified` and has no output. The score is computed from the folder alone. A control is scored on its **answer line** (the first non-empty line, NFKC) only.
6. T-LOOM-34 is step 3(d). The older route, the recorder ledger's `tool_call` rows for that subagent, exists only in a session whose project has the recorder hooks installed (`.claude/settings.json` of Verantyx-Vera-alpha; the line3 worktree has none): use it only where those hooks are installed, as a second witness.

By hand, without a transcript (fallback): save the final message to a file F unread, `python experiments/line3/loom/harness.py find --task I2-041 --mode record_only` (candidates in the operator folder; it **refuses scripted folders** and, if more than one unscored candidate matches, prints `AMBIGUOUS` and exits 3 instead of picking the newest), then `note RUN_DIR --free-text-file F`. This path has no T-LOOM-34 check.

## 3b. Permissions, and what is not closed

**Allow the loom server once, or every subagent run asks 10-25 times.** Each `mcp__vera-loom__*` call of the subagent is a permission prompt in the parent session unless it is allowed. A suggestion for the owner to apply (this build edits no settings file) in the project's `.claude/settings.json` or `.claude/settings.local.json`:
```json
{
  "permissions": { "allow": ["mcp__vera-loom"] },
  "enabledMcpjsonServers": ["vera-loom"]
}
```
`mcp__vera-loom` allows every tool of that server (and only that server); `enabledMcpjsonServers` pre-approves the `.mcp.json` server so that the trust question of section 2 step 3 is not asked. The allow rule also lets the parent session call the loom (below), so it is a choice about convenience, not a mechanism.

Residuals, stated so that nobody reads more into a run than it holds:
- **The parent session can call `mcp__vera-loom__*`** (the tools are in its tool list too). It can `begin` a run of its own, or call an existing run if it learns the id (the run id is random, but it is in the tool results the parent may be shown). Rows written that way read `actor: model`, exactly like the subagent's: the ledger cannot tell the callers apart. The transcript check catches a surplus (more model rows than loom calls in the subagent's transcript), not a parent call that happens to equal one the subagent made. Operator discipline: the parent session does not call the loom.
- The parent still receives the subagent's final message (step 2); only L2 removes it.
- `model: haiku` is a request and `begin.model` is testimony of the subagent; `response_model` from the transcript is testimony of the provider's log, not an attestation.
- The transcript is a file the operator points at; nothing proves it is the transcript of that subagent except that its begin result names a run whose row 0 matches its `task_id` input.

## 4. Scripted and API drivers

```
python experiments/line3/loom/harness.py run --task I2-041 --mode record_only --driver scripted     # -> baseline_scripted/{runs,results}/ by default
python experiments/line3/loom/harness.py run --task I2-041 --mode record_only --driver api --model claude-haiku-4-5   # needs `pip install anthropic` and credentials (ANTHROPIC_API_KEY or `ant auth login`)
```
`scripted` is the deterministic weaver (one script per bank2 task, written with the gold known; the demo tasks use the worked example); it is the harness baseline and the determinism check, **not** a model result: its "control" answers are the scripts' own words, written with the gold known, so the 7/7 of the scripted controls is not a measurement (the result says so in `control_note`, and `model_result: false`). `api` is the L2 driver: `tool_choice {"type":"any"}` for models that accept it (Haiku 4.5, ...), `auto` + `strict` tools for exactly `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-fable-5-1` (and `claude-mythos-5-1`); every text block is dropped (hash only), thinking blocks are counted apart (`thinking_dropped`: n, chars, sha256 only), and the tool calls of a turn after the one that closed the run are not executed (`calls_skipped_after_close`); it has not been run against the real API in this build. A run folder or results file that already exists is never overwritten; use `--tag`, another `--runs-dir`, or `--results-dir`.

## 5. What a result holds

`ledger` (path), `ledger_head`, `output_text`, `annotated`, `answer_view` (`hits_text`, then `hit_record_text` and `excess_chars` beside it), `score` (`status`, `correct`, `hits_text`, `hits_words`, `hit_record_text`, `excess_chars`, `answer_line` (controls), `chars`, `share_permille`, `replay_verified`, …), `op_counts`, `refusals`, `self_corrections`, `free_text_dropped`, `harness_meta`, `t_loom_34` and `transcript_check` (L1 runs noted from a transcript), `model_result` (false for the scripted driver), `wall` (driver and ledger nanoseconds; not hashed). `hits_text` is the primary column; `hit_record_text` (the gold inside the record + foundation text only, constructed words removed) and `excess_chars` (characters beyond the gold) say what the hit is made of. `harness.py summary` prints them as a table. Footnote: `hits_words` is the gold inside ONE record unit, so it is false by construction for every multi-unit answer (キューバの太陽, ハッシュ表, カールマルクス, 1981年); it is not a correctness column. A control result says `control: true`, is scored on its answer line, and is for comparison only.

Run folders are not portable: `meta.json` (not hashed) holds the absolute corpus path. After the repository moves, `verify` / `score` report `REPLAY_INPUTS_MISMATCH` until you pass it: `harness.py score RUN_DIR --corpus experiments/line3/bank2/data/fulllead_sents.jsonl` (or `python -m verantyx.cli loom verify RUN_DIR --corpus FILE`).
