# Vera Harness

**The model does not lie: it stays silent instead.** Vera Harness runs a model (Claude, DeepSeek, a local model through Ollama, ...) inside Vera so that its **only output is a verbatim quote from the record, or an honest 「分かりません」 ("I don't know")**. When the record does not say it, says two things, or says an old value, the harness does not answer. Every operation goes on a hash-chained ledger that can be replayed and verified later.

日本語: [README.md](README.md)

```
vera ask --docs ./manuals "保守契約の窓口は何ですか"          # "who is the contact for the maintenance contract?"
答え: 「総務部」
根拠: 保守契約の窓口は総務部である。（保守契約#1）
run: runs/ask-20261014-…

vera ask --docs ./manuals "保守契約の解約手数料は何ですか"     # "what is the cancellation fee?"
分かりません（理由: no_record、文書にその答えが書かれていません）
```

## What it is, and what it is not

**It is** a harness that forces the output channel. The model is given only Vera's tools; its free text is dropped (only a length and a hash are kept); the answer you are shown is a verbatim stretch of one sentence of your documents (or of the memory) that Vera's gate let through. The gate refuses by default. The core needs only the standard library and a morphological analyzer (fugashi + unidic-lite): no training, no network.

**It is not**:

* a general agent framework ("everything is a plugin"). It is a verification harness.
* a truth checker. It guarantees "the document says so", not "the document is right".
* a way to make a model smarter. It answers *less*, on purpose.
* multilingual. **Japanese only**; an English question is refused by the gate.
* a claim that the cross geometry helps. The memory is built on "crosses" and "nests" that find contradictions and updates deterministically, but there is **no evidence** that this beats a plain log plus search (in the research measurements it did not). That is research, not a product claim. The research history lives in the `research` branch of this repository (created at publish time).

## Measured numbers (the claims table)

Every number is either re-measured by `vera eval` and CI in this repository, or comes from a report in the research branch. Read the conditions.

| Claim | Number | Condition / source |
|---|---|---|
| No answer is given to an unanswerable question (output gate v6) | bank4 **0/60**, bank6 **0/34**, bank7 **0/47**, bank8 **0/50** | For each question, **every stretch of 1 to 10 words** of the sentences it is asked over is put through the gate; for an unanswerable question none passes. Re-measured by `vera eval`. bank8's 0/50 was an unseen judgment at gate v2 (v6 also gives 0/50). bank6 to bank8 were used afterwards to examine the rules, so they are now **frozen regression sets, not unseen tests** |
| Confident wrong answers by a real model on unanswerable questions | **0/126** | Claude Haiku 5.5, gate v2, research branch `experiments/line3/loom/results_h55f` |
| Wrong answers from the memory | **0** | **[research figure]** Red teams of the research tree (no recall, paraphrase, misleading writes, bridge attacks, ...), `experiments/line3/pub/m6c`. `vera eval` re-runs four of them (emit one side of a contested position, emit a replaced value, emit without recalling, emit through a bridge) on two memories |
| Contradiction detection | **[research figure]** precision 0.83, 137 of 216 planted. **What `vera eval` shows in this repository (the two shipped memories MEM-T01 and T03, 20 questions): SAME_SEAT fired 11 times, 7 on a planted fact and 4 false alarms, 7 of 12 plants found; UPDATE 0 of 6 and REVERSAL_X 0 of 4 (not read); of the 20 questions 4 were answered correctly by quote (12 reached; contested ones correctly left silent)** | The research meter (the model's writes of meter v1 replayed, report `pub/m5m6`) and the shipped eval have different conditions, and the latter is smaller. Detection, not an answer |
| Replay | every stored ledger **byte-identical** | CI, under `PYTHONHASHSEED` 0, 1 and 12345 |

## Limits (read these first)

* **Japanese only.**
* **It reaches an answer about one time in ten.** This number comes from a **gate-only sweep, with no model**: every stretch of the documents a question is asked over is put through the gate and the questions for which the gold phrase passes are counted, on the dev and held-out-at-the-time question sets (dev, bank6 to bank8). It is not a reach with a model in the loop and not a measurement on unseen questions. The rest come back as 「分かりません」 (a quote is possible only when the shape of the question and of the sentence match). This is the price of never answering wrongly. Answerable questions that reached a quote (`vera eval`, "reach"): dev 10/69, bank6 3/26, bank7 1/32, bank8 3/35.
* **Even for answerable questions the gate can pass a quote that is not the right one.** It passes a phrase quoted from a sentence whose shape fits the question; it does not know the gold answer (`vera eval`, "wrong answer admitted": 3 questions in bank6, 1 in bank8; 0 on unanswerable questions).
* **Memory writes are verbatim quotes of what the user said, and nothing else.** In `vera mem` and the UI each user message is recorded, with its text, as a row of the hash chain (`user_turn`); a model `write` is executed only if its text equals one whole sentence of the message of the turn being delivered (split only at 。！？ or the end of the message; NFC; a final 。 optional), never a piece of one; otherwise it is refused `not_from_user` (a `write_refused` row) and never stored. `vera verify` checks every stored write against the user turn it was written in (`WRITE_NOT_FROM_USER`); the model cannot name the turn, so an old message cannot be re-quoted to look newer. Writes made through MCP (`vera mcp --mode memory`) are the agent's own claims and outside this rule (verify reports them as `unsourced_sessions`). **An answer quoted from such a sentence is marked 「出所: 利用者の発言ではない（エージェントの記録）」** (the quoting guarantee above is about answers from the user's own words), **One rule: an agent's (unsourced) write never takes part in ordering or retirement.** Its rows carry no turn (a `turn` argument is stripped); a `supersede` runs only if its new side is a user's sentence and every retired sentence is the user's and from a strictly earlier turn, else `unsourced_order` (whichever session issues it); a write that reads as a change (「…に変更」) is refused; `verify` re-checks everything in every session (`UNSOURCED_ORDER`). An agent's value may *contest* a user's value (the position becomes ambiguous and the memory abstains) but never answers over it, so a later user correction of an agent's record is contested too. The MCP question-phase `emit` result also carries `sourced` and the mark. The research entry `python -m verantyx.loom.memmcp` has none of these guards and will not start without `--research-unguarded`. Sentences end only at 。！？ or the end of the message, never at a line break (end line-separated facts with 。). **Self-corrections inside one message** make a position `ambiguous_in_turn` (every write for that place from that message is refused) in exactly two cases: two sentences the memory reads at the same place, or a sentence it cannot read right after a readable fact. Other ways of correcting oneself (「山本。広報担当は鈴木です。」, 「…訂正します、広報の担当者は鈴木です。」, 「…今は鈴木です。」: read as a different form or place) are a **reader-coverage limit, not a guarantee**. A 「？」 also splits a condition from its consequence (「もし予算が通れば？広報の担当は鈴木。」 stores the second half as a fact). Say each fact once, in one sentence. **The recorded user turns are the source of truth**: before any memory answer every sentence of every recorded user turn is read with the memory's own reader, and if one says something else at the answered position and is not stored (the model left it out, or the memory refused it), the answer is withheld as `unrecorded_user_statement` (with the turn). A store whose ledger does not verify answers nothing (`store_not_verified`). Secret-shaped spans in a user message, a question or a document sentence (labelled password/token/key…, `sk-`/`Bearer`/`ghp_`/`AKIA` tokens, URL user:pass, full-width forms; the exact list is in docs/SAFETY.md) are replaced by `[redacted:sha256-8]` before recording or reading. **A secret with no label and no known prefix (a bare password in a sentence, a card number…) is not detected: do not type it into Vera.** A question with a secret is refused (`secret_in_question`) before anything is written or sent (normally only the span is lost; if a sentence boundary was removed, a whole sentence erased or the whole message dropped, the turn is recorded `redaction_lossy` and asks about anything said in a turn not later than it are refused `redacted_turn_unreadable`; the say result, CLI and UI tell the user). A contested list never shows a value that a later user sentence replaced as current. In a contested list each value carries its own sourced flag and mark.
* `declare_topic` and `bridge` are labels chosen by the model, never quoted, and cannot retire or reorder a fact. `supersede` runs only when the replacing statement was said in a strictly later user turn than every sentence it retires (the reverse is a `supersede_refused` row; `vera verify` re-checks: `SUPERSEDE_ORDER`).
* **The memory answers only from sentences written one fact per write, one sentence each.** It does not read "it changed", "extended", "X is handled by Y", synonyms (place / venue), or a retraction in another write. For an event sentence ("the meeting is held in Tokyo") it can read the question but does not give the value as a quote.
* **Real-model measurements exist only for Claude Haiku 5.5 (during the research).** The DeepSeek / OpenAI-compatible / Ollama / JSON backends have been tested with fake clients only. The guarantee lives in Vera (gate, ledger) and does not depend on the model's behaviour, but **a weak model produces more 「分かりません」**.
* The stored fixture ledgers (`tests/fixtures/ledgers`) replay **only on CPython 3.11.14** (CI is pinned to it); ledgers you make replay on your own Python. **Replaying** a ledger needs the same CPython x.y.z and the same dictionary-derived hashes (the morphological dictionary version) as the one that made it; otherwise the replay says `INPUTS` (not reproducible). Verifying the hash chain works anywhere.
* The guarantee depends on the enforcement level (E1 to E3 below).

More in [docs/SAFETY.md](docs/SAFETY.md).

## Quickstart

Python 3.10 or newer.

```
git clone https://github.com/Ag3497120/vera && cd vera
python -m venv .venv && . .venv/bin/activate
pip install -e ".[anthropic,openai,mcp]"       # the core is fugashi and unidic-lite only; install just the SDKs you use
vera --version
```

It is not published on PyPI (no date). API keys are read **from the environment or the macOS Keychain** only; a key value never appears on screen or in a ledger.

### Claude

```
export ANTHROPIC_API_KEY=...                       # or: security add-generic-password -s vera-harness -a anthropic -w
vera ask --docs ./manuals "保守契約の窓口は何ですか"
```

The default backend is `anthropic`, the default model `claude-haiku-5-5` (`--model` to change).

### DeepSeek and other OpenAI-compatible APIs

```
export DEEPSEEK_API_KEY=...
vera ask --docs ./manuals --backend openai --model deepseek-chat --base-url https://api.deepseek.com --api-key-env DEEPSEEK_API_KEY "…"
```

Check your provider for model names. Tool calling is forced; for a server that rejects that use `--tool-choice auto` (the driver still accepts only tool calls).

### Ollama, LM Studio, vLLM (local, no key)

```
vera ask --docs ./manuals --backend openai --model llama3.1 --base-url http://127.0.0.1:11434/v1 "…"       # Ollama
vera ask --docs ./manuals --backend openai --model <id> --base-url http://127.0.0.1:1234/v1 "…"            # LM Studio
```

For a model without tool calling use the JSON backend: `--backend json` (the model answers with a JSON array of operations; anything else is dropped).

### The web UI (local only)

```
vera run --docs ./manuals            # http://127.0.0.1:3090/
```

The conversation (an answer is a quote with its source sentence, or 「分かりません」 with the typed reason), the operation trace, the ledger's hash chain with a **Verify** button, the memory's notes (SAME_SEAT / UPDATE / REVERSAL_X) and the crosses and nests of the asked position, and settings (backend; whether a key is present, never its value). Nothing is loaded from outside. It binds loopback only (127.0.0.0/8, ::1); `--allow-remote` does not exist in this version (it is refused). The base URL, the key environment-variable name, the documents and the storage folders can be set **only on the command line**; the page shows them read-only.

### Memory

```
vera mem --store ./memory --say "広報の担当は山本" --say "広報の担当は田中" --ask "広報の担当は何ですか"
分かりません（理由: contested、記録の中で答えが食い違っています： 「山本」 / 「田中」）
```

When two different values are told for the same seat, it does not pick one: it reports a contradiction and stays silent. The same folder is the same memory in the next conversation.

### Verify, replay, evaluate

```
vera verify runs/ask-…        # the hash chain, then the replay (byte for byte)
vera replay runs/ask-…
vera eval --quick             # re-measure the safety claims offline (no model, no network); exit 1 if a safety number is worse than the record
```

### MCP and Claude Code subagents

```
vera mcp --docs ./manuals --question "保守契約の窓口は何ですか" --runs-dir runs      # a stdio MCP server (vera-loom)
```

Give a subagent only the 20 tools `mcp__vera-loom__*` in its `tools:` list and Vera is that agent's only exit. A complete set of files is in [examples/claude_code](examples/claude_code/). The premise is that **you take the answer from `vera loom output runs/<run_id>`, not from Claude Code's transcript** (see E2 for what is and is not guaranteed).

## Enforcement levels (E1 to E3) and what each guarantees

| Level | What it does | Guarantees | Does not guarantee |
|---|---|---|---|
| **E1** (default, all OSes) `vera ask / mem / run` | The driver hands the model only Vera's tools, drops free text (`free_text_dropped`: length and hash), rejects any other tool name. Only the text of a successful `emit` of a verified ledger is shown | What you see is a quote the gate passed, or 「分かりません」. The ledger can be checked by chain and replay | No OS confinement of the model process (the model is behind an API, so the harness is its only exit) |
| **E2** (Claude Code) `vera mcp` + a subagent allow-list | The agent's tools are only Vera's MCP tools | The agent's tools are Vera's only. `vera loom output` prints nothing but the verified `emit` | Claude Code's transcript keeps whatever the agent wrote, and a parent agent or a person reading it as "the answer" cannot be stopped by Vera. Taking the answer from the ledger is part of the procedure |
| **E3** (macOS) `vera loom mcp --isolated` | The MCP server runs under `sandbox-exec`: no network, no exec, no reads or writes outside the listed places. Before starting it runs a probe under the same profile and refuses to start if the probe fails (exit 3) | The server (and its children) cannot send anything out or write elsewhere | The client (the agent) is not confined. Apple deprecates `sandbox-exec`. Linux (bubblewrap) is not supported yet |

## Plugins

Backends, gate filters, memory profiles and note kinds can be added through Python entry points (group `vera.plugins`); the built-ins are registered the same way. A ledger records which plugins ran and at which version, and `verify` says **INPUTS** (not reproducible) for a ledger whose plugin is not installed. See [docs/PLUGINS.md](docs/PLUGINS.md) and the minimal example in [examples/plugins](examples/plugins/vera_example_plugin/).

## Repository

```
verantyx/            the package (the import name is kept so that old ledgers replay)
  harness/           backends, runner, CLI, MCP, the web UI (webui/), plugins, evals (evals/)
  loom/              the loom, the gate, the memory (unchanged)
  line3/             the minimal grammar layer
examples/            docs_qa/ (ask documents), memory/ (a working-log memory), claude_code/, plugins/
docs/                ARCHITECTURE.md, SAFETY.md, LEDGER.md, PLUGINS.md
tests/               harness tests, replay of stored ledgers
```

* [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): what happens where
* [docs/SAFETY.md](docs/SAFETY.md): claims, limits, threat model
* [docs/LEDGER.md](docs/LEDGER.md): the ledger format and the verification states

The research history (experiments, design documents, meter reports) lives in the **`research` branch** of this repository (created at publish time). Whatever is claimed there about the structure (the cross geometry) is **research, not a claim of this harness**.

## License

MIT

The English text was written with the help of AI.
