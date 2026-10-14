# Architecture

(日本語の概要は README.md。This page says what happens where.)

## The one idea

The model never *writes* an answer. It *operates* Vera: it looks things up, reads sentences, weaves a quote of the record into a small structure, and asks Vera to `emit` it. Vera decides whether that quote answers the question. Everything the model does is one row of a hash-chained ledger; what a person sees is derived from the ledger, not from what the model said.

```
 you ── vera ask / mem / run / mcp ─────────────────────────────────────────────────────────────────────────────┐
                                                                                                                │
   backend (Anthropic | OpenAI-compatible | JSON ops | plugin)        one request in, one Anthropic-shaped turn out
        │  text blocks → dropped (sha256 + length)      tool_use blocks → only the tools the server offered
        ▼
   driver  (verantyx.loom.driver / memdriver, UNCHANGED)              loops turns, enforces caps (repeat, status spam, max turns)
        ▼
   loom server / memory door  ─►  evidence gate (evidence.v6)  ─►  ledger (ops.jsonl: chain, canonical JSON)
        ▲                                                              │
        └──────────────── runner.settle: verify + replay ──────────────┘
                                   │
                                   ▼
                    Answer: a quote + its source sentence(s), or 「分かりません」 + typed reason
                                   │   (gate-filter plugins may still refuse it; nothing can add)
                                   ▼
                    CLI text / JSON  ·  web UI (server.py + webui/index.html)  ·  MCP client
```

## Layers

| layer | where | what it does | changed in this repo? |
|---|---|---|---|
| grammar | `verantyx/line3/`, `lang.py`, `ja_grammar.py` | Japanese units (fugashi + unidic-lite), particles, the cross geometry used to read a clause | minimal subset of the research tree |
| loom | `verantyx/loom/` | the 20 operations, the state, the **evidence gate** (`evidence.py`, versions v1 to v6, v6 default), ledger (`ledger.py`, `ops.py`) | unchanged, except `harness_meta` may carry `plugins` |
| memory | `verantyx/loom/mem*.py` | a store of committed sentences, the shape exchanger (reads 「X の Y は A」 and friends), crosses and nests (the index), notes (SAME_SEAT, UPDATE, REVERSAL_X, ENUMERATION), the answer run (`memanswer.v17`) | unchanged |
| backends | `verantyx/harness/backends/` | one class per way to reach a model; each returns `Turn` objects the unchanged driver reads | new |
| runner | `verantyx/harness/runner.py` | `ask`, `mem_say`, `mem_ask`, `settle` (the Answer from a **verified** ledger), `verify_path`, `replay_path`; plugin resolution and the gate filters | new |
| CLI | `verantyx/harness/cli.py` (+ `loom_cli.py`, `mcp_server.py`) | `ask mem run mcp verify replay eval plugins loom` | new |
| web UI | `verantyx/harness/server.py`, `webui/index.html` | stdlib `http.server`, JSON endpoints, one static page | new |
| plugins | `verantyx/harness/plugins.py`, `builtin_plugins.py` | entry-point registry, the manifest a ledger carries | new |
| evals | `verantyx/harness/evalrun.py`, `evals/` | offline re-measurement of the safety numbers, frozen record | new |

The import name `verantyx` is kept so ledgers made by the research tree replay unchanged; the product and the command are `vera`.

## `vera ask`, step by step

1. **Corpus.** `docs_corpus` reads `.txt` / `.md` (recursively, sorted), splits sentences at 。！？ and line breaks (Markdown markers removed, nothing else rewritten) and writes deterministic bytes; their sha256 names the corpus. The corpus is also copied beside the ledger.
2. **Begin.** A `record_only` loom task (`TASK_ID ask/1`) with the evidence gate (v6) is begun. The first `harness_meta` row records the driver, the model, the sha of the system prompt and the plugins that run.
3. **Episode.** The backend is asked for turns until the model closes the run (`emit` or `abstain`) or a cap trips. The model can `lookup` a unit, `read_sentence`, and `weave_span(sid, tier, first, last)`: a quote of exactly that stretch, built from the sentence's own units. Then `emit`.
4. **The gate** reads the clause around the quoted stretch with Vera's own grammar and passes it only if that sentence answers *this* question: the subject, the asked slot, the particle after the answer, not a word of the question itself, not a negated or glued fragment (rules CH, SU, TW, NEG on top of v2). **It refuses by default**; every refusal has typed codes the model sees and a person can read.
5. **Settle.** `ledger.emitted_output` verifies the chain and the replay first; only then is the text of the successful `emit` read. The source sentences are looked up in the corpus (a lookup, not the model's claim).
6. **One gate for every document entry.** `runner.DocRedactGate` wraps the loom server in `vera ask`, the UI and `vera mcp` (via `loom.mcp.build(wrap=…)`): a sentence that received a redaction marker is never quotable (`redacted_sentence`). A test enumerates every answer entry point and checks each one.
7. **Filters.** Gate-filter plugins (if any) may still refuse the answer; they cannot add anything.

If the model writes prose instead of calling a tool, the prose is hashed and dropped. If it never closes the run, the run is `abandoned` and the person sees 「分かりません」 with the reason.

## `vera mem`

* `mem_say`: one *story session*: each message arrives as a turn (`1-3` = session 1, message 3); the model keeps what matters with `write` (one fact, one sentence), may `declare_topic`, and must end every turn with `report(contradictions)`. The session is committed to the store only if it completed.
* The store derives an **index** (a pure function of the sentences): crosses (a position per centre phrase, seats on arms), nests, the slide order of values, and the **notes**. A note never blocks a write and never decides an answer by itself.
* `mem_ask`: an answer run over a snapshot (`memanswer.v17`). `recall(question)` returns ANSWER / UPDATED (latest value + history) / CHOICE (two values nobody resolved) / candidates / NONE. A value can only come out as a quote of the remembered sentence, through the same gate; a value of a contested position, or a replaced value, is refused (`contested_value`, `replaced_value`). A question the memory cannot read gets 「分かりません」.
* The crosses and nests are used to find contradictions and updates deterministically. **That they are better than a plain log is not claimed** (see docs/SAFETY.md).

## The web UI

`vera run` serves one static HTML page (script and style inline, by-hash CSP, nothing loaded from outside) and a few JSON endpoints under `/api/`: state, settings, ask, say, runs, ledger/trace, verify, memory, position. See docs/SAFETY.md for the exposure rules. The page renders only what an `Answer` holds (a quote and its sources, or a refusal and its typed reason); the model's prose does not exist in an `Answer`.

## Determinism

A run is a pure function of its inputs: the ledger bytes do not depend on `PYTHONHASHSEED`, on wall-clock time (which is kept outside the chain) or on dict/set order (nothing in the structure iterates one). CI asserts it under three hash seeds. Anything that is *not* deterministic (the model) is recorded as rows; replay re-executes the *operations* against a fresh state and compares the *results*.

## Tests and CI

`tests/core` (the loom, the grammar, the memory; about 50 files ported from the research tree) and `tests/harness` (backends with fake clients, runner, CLI, plugins, the web server on an ephemeral port, the examples, `vera eval`) run in CI on Python 3.11.14 under three hash seeds, sharded. `tools/verify_fixtures.py` replays every stored ledger under `tests/fixtures/ledgers`. A job runs `vera eval --quick`. A clean-venv install job builds the wheel and checks that the package data (prompts, tool schemas, grammar data, evals, web page) is inside it. No job uses an API key or the network.

The English text was written with the help of AI.
