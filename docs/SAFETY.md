# Safety: claims, limits, threat model

(日本語の要点は README.md の「測った数字」「限界」。)

## 1. The guarantee, exactly

For `vera ask`, `vera mem` and `vera run`:

> If Vera shows an answer, then there is a successful `emit` row in a ledger that **verifies and replays identically**, and its text is a **verbatim stretch of one sentence** of the corpus (or of a remembered sentence) that the **evidence gate** passed for **this question**. In every other case Vera shows 「分かりません」 and a typed reason.

It is a statement about *what is shown*, not about the model. The model can be wrong, adversarial or prompt-injected; what it can do is limited to calling Vera's tools, and what comes out is limited to the above.

It is **not** a statement that the quote is the right answer (see 3.2), that the record is true, or that the transcript of an agent framework contains nothing else (E2, see 4).

## 2. Claims and where the numbers come from

All numbers are re-measurable offline with `vera eval` (the gate on the shipped banks; the memory red teams on two memories), compared with the frozen record `verantyx/harness/evals/expected.json`, or are reports in the `research` branch.

| claim | number | what it does *not* say |
|---|---|---|
| No answer to an unanswerable question: every stretch of 1 to 10 words of the sentences a question is asked over goes through gate v6; none passes | bank4 (the bank2+4 dev set) 0/60, bank6 0/34, bank7 0/47, bank8 0/50 | not a test on unseen data: bank6, 7 and 8 were used afterwards to examine the rules (bank8 was one unseen judgment, at gate v2) and are now regression sets. A new kind of question may be admitted. The corpus is 592 sentences of encyclopedic Japanese |
| A real model made no confident wrong answer on unanswerable questions | 0/126 | Claude Haiku 5.5, gate v2, one study. Not measured for other models, or for gate v6 with a model |
| The memory made no wrong answer under the research red teams | 0 | the red teams are the ones we thought of. `vera eval` re-runs four of them on two memories |
| Contradiction detection | precision 0.83, 137 of 216 planted | detection only (a note), measured on writes a Claude model made in the research meter |
| Replay | stored ledgers byte-identical | same CPython x.y.z and dictionary-derived hashes |

The research also measured that **the structure did not beat a plain log**: in the memory meter (meter v1, 6 tasks, 3 repeats) a plain log with a model found more planted contradictions (35.0 of 36 against 24.7 of 36) and answered more of the questions (55 of 60 against 17.7 of 60), at about a tenth of the cost. The memory's crosses and nests are kept because they are deterministic, replayable and refuse safely, **not because they are shown to be better**.

## 3. Limits

1. **Japanese only.** An English question is refused by the gate.
2. **The gate does not know the right answer.** On answerable questions it passes a stretch whose clause fits the question; some such stretches are not the gold answer (`vera eval`: in bank6, 3 of 26 answerable questions, and in bank8, 1 of 35, have a non-gold stretch admitted). A model that picks that stretch shows a quote that is verbatim, from the right sentence shape, and still not what you asked.
3. **Low reach.** Unseen questions reach a quote about one time in ten (dev 10/69, bank6 3/26, bank7 1/32, bank8 3/35). The harness is useful when silence is cheap and a wrong answer is expensive.
4. **The memory answers only from one-fact-per-write sentences** of the forms its shape table reads (「X の Y は A」 and a few more). Not read: a change expressed in words the table lacks, extension, 「X は Y が担当」, synonyms, a retraction in another write, the value of an event sentence (the question is read, the value is not quoted).
5. **Real-model evidence is Claude Haiku 5.5 only.** Other backends are tested with fake clients. A weaker model should produce more silence, not more lies; that is expected but not yet measured.
6. **Replay is exact-environment.** The header names the CPython x.y.z and the hashes of the tokenizer-derived tables; a different environment gets `INPUTS`.
7. **Quoted text is the record's.** If a document is wrong, outdated or hostile, a correct-looking quote of it passes.
8. **Privacy.** With a cloud backend, your questions and every sentence the model looks up or reads are sent to that provider. Use a local backend (Ollama, LM Studio, vLLM, MLX) to keep them on the machine.

## 4. Enforcement levels

| | scope | guaranteed | not guaranteed |
|---|---|---|---|
| **E1** `vera ask/mem/run` | the harness drives the model through an API | only Vera's tools are offered; free text is dropped (hash + length); an unknown tool name is rejected with no state change; the person sees only a verified `emit` | the model's host (a provider, a local server) is outside the harness |
| **E2** `vera mcp` + Claude Code subagent allow-list | the agent's tools | the agent can call Vera's tools only; `vera loom output` prints only a verified `emit` | the **transcript still contains what the agent wrote**, and Vera cannot stop a parent agent or a person from reading it as the answer. Take the answer from the ledger. The allow-list is Claude Code's, not Vera's |
| **E3** `vera loom mcp --isolated` (macOS) | the MCP server process | OS sandbox (`sandbox-exec`): no network, no fork/exec, reads and writes only in listed places; a probe under the same profile must pass first, or exit 3 | the client is not confined; Apple has deprecated `sandbox-exec`; Linux bubblewrap is not implemented |

## 5. Threat model

Assets: the reader's trust in a shown answer; the documents and the memory; API keys; the local machine; the ledgers.

| threat | what Vera does | residual |
|---|---|---|
| The model hallucinates or is adversarial | forced tools; free text dropped; quote-only output; the gate refuses by default; caps stop loops; refusals are typed rows | limits 2 and 3 |
| Prompt injection in a document or a remembered sentence | the document reaches the model only as tool results; whatever the model is told to do, it can only call Vera's tools, and the output stays a gate-passed quote of the record | an injected sentence that *has the shape of an answer* can be quoted as one (limit 7). The harness cannot tell a planted fact from a true one |
| A ledger is edited afterwards | row hashes and links (`TAMPERED`), canonical form, torn tail, the `HEAD` pin, replay (`REPLAY_DIFFERS` catches a forged result) | someone who can rewrite the *whole* folder can rewrite the whole chain: pin `HEAD` elsewhere. `harness.json`, `timing.jsonl` and `runs/_corpora` are outside the chain (the corpus is bound by its sha256 in the `begin` row) |
| A website attacks the local web UI (`vera run`) | binds 127.0.0.1 / ::1 only (any other address is refused unless `--allow-remote`); every `/api/` call needs a per-process token that only the served page holds; POST must be `application/json`; an `Origin` must be this origin; the `Host` header must be the server's own (DNS rebinding); **no CORS headers**; CSP `default-src 'none'` with the page's own inline script and style allowed by hash and `connect-src 'self'`; `X-Frame-Options: DENY`; no external loads; one run at a time; 64 KB request bodies; answers and sentences are rendered as text, never as HTML | **another process on the same machine can connect to 127.0.0.1, read the page and therefore the token, and use your configured backend** (and spend its credits). There is no per-user authentication: treat the UI as trusted-local. On a shared machine do not run it; use the CLI. `--allow-remote` makes it reachable by anyone on the network: do not |
| Keys leak | keys come only from the environment or the macOS Keychain, are resolved at call time and handed to the SDK client only; every error text is passed through `redact`; `--base-url` with credentials is refused (the run folder records the URL); the UI shows presence and source, never a value, and has no field that accepts a key (the "key environment variable" field takes a *name* and rejects anything else) | keys in the environment are visible to your other processes; a Keychain read may prompt; a provider's own logging is out of scope |
| A malicious plugin | it can only refuse (gates), pick Vera-implemented versions (memory profiles), show notes (note kinds) or supply a backend; its name and version are in the ledger; a missing or changed plugin makes verify say `INPUTS` | **a plugin is arbitrary Python running with your privileges** (an entry point is code). Install only code you trust |
| Dependency or data tampering | the tokenizer and its dictionary are pinned in CI (`.github/constraints.txt`); the shipped eval files are checked against `MANIFEST.json` before every `vera eval` | a compromised release of a dependency |
| Resource exhaustion | caps on repeated operations, status calls and turns; one run at a time in the UI; a request-size limit | a very large corpus is read into memory |

## 6. Out of scope

The truth of your documents; the confidentiality of what you send to a cloud provider (3.8); a model host you do not control; side channels of the machine; the transcript of agent frameworks other than as described for E2.

## 7. Reporting

Open an issue, or write to the maintainer privately, for anything that lets an answer out that the gate should have refused, or lets a web page reach the local server.

The English text was written with the help of AI.
