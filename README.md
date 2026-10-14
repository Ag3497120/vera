# Vera Harness

Run a model inside Vera so that its only output is a **quote from the record** or an honest **「分かりません」**, with every operation on a hash-chained, replayable ledger.

> Status: tickets H0-H2 of `docs/HARNESS_DESIGN.md` (minimal tree, backends, runner and CLI). The full README, the eval set and the web UI follow (H3-H7).

```
pip install -e ".[anthropic,openai,mcp]"        # core: fugashi + unidic-lite, nothing else
export ANTHROPIC_API_KEY=...                     # or VERA_OPENAI_API_KEY / OPENAI_API_KEY, or the macOS Keychain (see verantyx/harness/keys.py); a key is never printed or recorded

vera ask --docs ./manuals "保守契約の更新期限はいつですか？"                  # quote + source sentence, or 分かりません + the typed reason
vera ask --docs ./manuals --backend openai --model llama3.1 --base-url http://127.0.0.1:11434/v1 "…"     # Ollama / LM Studio / vLLM / DeepSeek
vera ask --docs ./manuals --backend json --model tiny --base-url http://127.0.0.1:1234/v1 "…"          # a model without tool calling: it answers with a JSON array of ops
vera mem --store ./memory --say "広報の担当は山本" --ask "広報の担当は何ですか"                              # a memory: one fact per message; two told answers are "contested"
vera mcp --docs ./manuals --question "…" --runs-dir runs                                                 # Vera as the only exit of an agent (stdio MCP)
vera verify runs/ask-…   &&   vera replay runs/ask-…                                                   # chain, then byte-for-byte replay
```

How the output is forced (the guarantee does not depend on the model behaving):

* the model gets only the loom's tools (or the memory's); free text is **dropped**, only its sha256 and length are recorded (`free_text_dropped`);
* a quote is shown only if the evidence gate (`evidence.v6`) passes it, and only from a ledger that verifies and replays identically;
* all three backends (Anthropic, any OpenAI-compatible server, JSON ops) run through the same driver, the same server and the same ledger.

Limits, stated plainly: Japanese only; an answer is a verbatim stretch of one sentence, so most questions come back as 「分かりません」; the memory answers only from one-fact-per-message sentences. The effect of the cross-structure geometry is **not** claimed here.

MIT licensed. The import name stays `verantyx` so that ledgers made by the research tree replay unchanged.
