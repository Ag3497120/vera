# The ledger

(日本語の要点は README.md の「強制の段」「限界」。This page is the format reference.)

Every run of Vera Harness is a folder of append-only, hash-chained rows. `vera verify` checks the chain and then replays the run; `vera replay` re-executes it and compares every row byte for byte.

## A run folder

`vera ask` writes `<runs-dir>/<run_id>/`:

| file | what | in the chain? |
|---|---|---|
| `ops.jsonl` | one canonical-JSON row per call, append-only | yes (it *is* the chain) |
| `HEAD` | the sha of the last row (a pin; commit it, or pass `--head`, to catch a rewrite of the whole chain) | pin |
| `meta.json` | where the corpus lives (relative to the repository or to the runs folder; an absolute path only for a corpus outside both) and its sha256 (a pointer, never hashed) | no |
| `corpus.jsonl` | the exact corpus bytes the run began on, beside the ledger so that the folder can be moved | its sha256 is in the `begin` row |
| `harness.json` | what the harness recorded for you: backend (name, model, base URL; never a key), prompt sha, plugins, driver report, usage | no (informational) |
| `timing.jsonl` | `{i, t_ns}` per row | no. Wall-clock time is kept **out** of the chain so that a replay can reproduce the file byte for byte |

A memory store (`vera mem --store S`) is `S/{HEAD, memory.jsonl, sessions/s0001/…, answers/a0001/…, snapshots/…}`: one ledger per session and per answer run, `memory.jsonl` = the committed sentences, `snapshots/` = what an answer run was asked over. A session counts as memory only when it was **committed** (a session that failed is not memory).

## A row

```
{"v":1, "i":<0-based>, "actor":"model"|"harness"|"human", "op":<one of a closed list>, "args":{…}, "result":{…},
 "state_sha":<sha256 of the canonical state after the op>, "prev":<sha of row i-1 | 64 zeros>, "sha":sha256(canonical(row without sha))}
```

* **canonical JSON**: sorted keys, no spaces, UTF-8; `verify` requires every line to *be* the canonical serialisation of its row.
* a row whose arguments held a secret-shaped string is stored redacted (`redacted`, `args_sha256`); one whose arguments were too large is stored as `truncated` + `args_sha256` + `args_chars`.
* `actor "model"`: an operation of the model, executed by the loom server (the 20 tools: `begin lookup read_sentence … weave_span … emit abstain status`; memory: `write recall report …`). A refused call is a row too (`result.ok = false`, a typed `refusal`). A call to a tool that does not exist is **not** a row: no state changes.
* `actor "harness"`: `free_text_dropped` (the model wrote prose: only its sha256 and character count are kept), `user_turn` (a memory session: what the **user** said, with its text, when it was delivered; every secret-shaped span (sk-ant-, sk-, AKIA…, ghp_…, xox…, private keys, Bearer, key=value) is first replaced by `[redacted:<sha256-8 of the span>]` and the list of those sha256-8 is the row's `redacted` field (what is detected is listed exactly in docs/SAFETY.md and `verantyx/harness/secretscan.py`: labels with `=`, `:` or は, CLI `--password X`, URL user:pass, `sk-`/`Bearer`/`ghp_`/`AKIA`/`xox` tokens of any length, full-width forms; the value token is replaced whole, up to white space, 。 or 、; other secret forms are NOT detected and must not be typed); if the redaction removed or changed a sentence boundary, erased a whole sentence, had to drop the whole message, or left a sentence the reader cannot read once the marker is out, the row also has `redaction_lossy: true`: the ledger, the whole-sentence rule and the reading only ever see the redacted text), `supersede_refused` (a model `supersede` whose new sentence is not later than what it would retire), `write_refused` (a model `write` that was not a whole user sentence, or was ambiguous in its message: sha256, length and a reason only), `statement_refused` (a memory answer run closed with an `abstain`; `reason` `unrecorded_user_statement`: a recorded user sentence at the answered position says something else and is not a stored write, or `redacted_turn_unreadable`: the answer's turn is not later than a `redaction_lossy` turn; `turn` names it), `plugin_refused` (a gate-filter plugin turned an emit into an abstain), `harness_meta` (driver, requested/response model, system-prompt sha, **`plugins`**: the canonical JSON of the plugins that ran, each with name, version and, for non-built-in plugins, a `digest` of its source), `abandoned` (the run was left open: a typed reason such as `api_error`, `max_turns`, `no_tool_call`, `cap_repeat`).
* the first row is `begin`; its result holds the **header**: loom version, Python implementation and exact version, `corpus_sha`, and the hashes of the space, the adhesion tables and the seats (derived from the tokenizer's dictionary), plus the evidence profile (`evidence.v6`, subject scope) the run was started under. A replay uses the profile the begin row recorded, so changing the default later never changes what an old run means.

## What is shown to a person

Only the text of a **successful `emit`** of a ledger that **verifies and replays identically** (`ledger.emitted_output` calls verify first). Lookups, reads, statuses and free text are never output. Otherwise the person sees 「分かりません」 and the typed reason: the abstention type the model chose, the reason the run was abandoned, the last refusal of the gate, or `run_not_verified`.

## Verification states

`vera verify RUN` prints `<STATUS> <kind>`; exit 0 only for `OK`.

| status | meaning |
|---|---|
| `OK` | chain intact, replay reproduced every row byte for byte, declared plugins installed |
| `EMPTY` | no rows |
| `TAMPERED` | a row's hash, its link to the previous row, or its canonical form is wrong |
| `TORN_TAIL` | the last line is incomplete (a crash while writing). Nothing after it can be trusted |
| `HEAD_MISMATCH` | the last row is not the sha pinned in `HEAD` / `--head` |
| `REPLAY_DIFFERS` | the chain is intact but the operations do not reproduce the recorded results (a server bug or a forged result) |
| `REPLAY_INPUTS_MISMATCH` | the run cannot be replayed under the conditions it names: `replay.status` is **`INPUTS`** and `replay.mismatch` says which: `python_mismatch` (another CPython x.y.z), `loom_version_mismatch`, `corpus_sha_mismatch`, `space_sha_mismatch` / `adhesion_sha_mismatch` / `seats_sha_mismatch` (another dictionary), `corpus_unreadable`, `unknown_plugin:<kind>/<name>`, `plugin_code:<kind>/<name>` (same version, other source), `plugin_version:<kind>/<name>:<declared>!=<installed>`, `plugins_malformed` |
| `WRITE_NOT_FROM_USER` | (a memory store) a stored write (or a write before the first user turn) is not equal to one whole sentence of the user turn it was written in |
| `SUPERSEDE_ORDER` | (a memory store) an executed `supersede` retires a sentence that is not earlier than its `new_sid` |
| `UNSOURCED_ORDER` | (a memory store) an executed `supersede` has an unsourced (agent) sentence as its new side or as a retired one, or an agent's write states a change |
| `AMBIGUOUS_WRITE` | (a memory store) a stored write belongs to a position its user message left ambiguous (a self-correction) |
| `USER_STATEMENT_NOT_RECORDED` | (a memory store) an answer run emitted a value for a position where a recorded user sentence (of the sessions its snapshot covered) says something else and is not a stored write |
| `REDACTED_TURN_UNREADABLE` | (a memory store) an answer run emitted although its source turn is not later than a `redaction_lossy` user turn |
| `NOT_A_RUN` | the path is not a run folder or a memory store |

The chain is always checked first: a tampered ledger says `TAMPERED` whatever else is missing. `INPUTS` is never reported as `OK`.

`vera replay RUN`: exit 0 `IDENTICAL`, 1 `DIFFERS`, 2 `INPUTS` / `NOT_A_RUN`.

## What a ledger proves, and what it does not

* It proves that **these operations, in this order, produced these results** (chain + replay), and that the answer shown is a quote the gate passed **on the recorded corpus**.
* A chain can be rewritten **as a whole** by someone who can write the folder; pin `HEAD` somewhere else (or pass `--head`) to detect that.
* It does not prove the corpus is true, nor that the model "understood" anything. It records what the model did.
* It does not make a run reproducible on another interpreter or another tokenizer dictionary: that is an explicit `INPUTS`.
* `harness.json`, `timing.jsonl` and `runs/_corpora/` are outside the chain; the corpus is bound by its sha256 in the `begin` row.

The English text was written with the help of AI.
