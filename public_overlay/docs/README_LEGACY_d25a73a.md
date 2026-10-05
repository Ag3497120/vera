# Legacy README of the vera-ja package (snapshot d25a73a, 2026-10-03)

This is the former front page of `public_overlay/README.md`, moved here **without changes to its wording**, except for two things: (1) the link to the v0.1.0 release page is described in words ("the v0.1.0 release (the Releases page of this repository)"), and (2) where a sentence contains a claim word, a mark `[N-xx]` was added that points to a row of the numbers spec with its denominator and set (`artifacts/w16-t11/numbers.r1.json` in Verantyx-Vera-alpha). **None of the numbers below were recomputed for v0.9-preview.** They date from 2026-09-28 to 2026-10-03 (snapshot d25a73a). Their sources are not in the tree at ecde332; the marks only tie each sentence to the wording of the old README at that commit. The numbers measured for v0.9-preview are in `README.md` and `EVAL.md`.

---

# Vera base (ja) — a Japanese chat and checker with no weights

Vera is not a neural network. It reads Japanese into **predicate–argument structure** (who did what to whom, negation, rule kind, condition, exception, filled-in omissions), keeps the owner's records in that form, and reaches them through a **stereo-cross tree with a flat fallback**, split into **sovereigns** (one tree per kind of document, joined under one root). Answers are computed by rules, arithmetic, and counts of independent sources. Nothing is trained; adding a document is adding rows.

It runs on a CPU in Python, answers in about 0.1–5 ms, and every answer either shows where it came from or says it does not know.


## Update 2026-10-03: the semantic path, a stereo-cross router, a realizer and a conductor (prototypes)

This update adds about 120 modules and the test suite on top of the base above. **Everything in this section is a prototype: not adopted, not a sealed result, and development is paused at this snapshot (working-copy commit `d25a73a`).** The measurements are our own (train data, a public dev set, scripted agents) and each number says what it is.

| Part (`vera_base/verantyx/`) | What it does | Measured at this snapshot |
|---|---|---|
| `semantic_reader`, `semantic_ir`, `semantic_execute`, `semantic_verify` | Reads Japanese into typed clauses (frames with case roles, copula, measures, coordination, tense, guards); a producer answers and an **independent checker** licenses every clause; unread text stays typed and blocks the answer it could change | Public dev set (80 items, audited, not sealed): **17 correct, 0 wrong** [N-51][N-52] (measured before the last waves; 4/80 at the start of this phase). Real Wikipedia lead paragraphs (1,500 train leads, 3,575 sentences): **37.5%** of sentences yield at least one supported clause (19.0% → 16.7% after a precision fix that over-abstained → 37.5% after the construction wave) |
| `constructions/` | Registry of reading constructions (parentheticals, quotations, adnominal clauses, predicate chains, time expressions, quantifiers, voice, connectives, modality, omitted subjects, light verbs, noun-phrase internals, …); each construction brings an independently written licensor; two constructions disagreeing on a span give typed ambiguity | Reading coverage was used as a merge gate while this was built |
| `semantic_route` | The stereo cross as a **leaf router**: documents are leaves, a conduction tree finds every leaf that can matter for a question (never one "best" leaf); the routed view is only ever a subset of the flat view | 0 violations against a flat contract oracle on 16,000 leads; rare-entity two-hop chains 60/60 of the flat answers (17–54% before an entity-walk fix); mid-frequency entities 0–23% (open) |
| `semantic_realize`, `semantic_generate` | The inverse of the reader: typed clauses → Japanese text, accepted only if (a) the reader re-reads it to the same clause and (b) every content word is lineage-checked against the source; answers, summaries, refusals with quoted evidence | Realizable on real leads: 65% of copula clauses, 24% of frame clauses (limited by what the reader supports). Mutation audit (polarity, tense, role swap, term swap): 300/300 caught jointly; the lineage check alone catches 26% |
| `semantic_unknown`, `semantic_outside` | Words outside the closure: typed, constructed candidates from attested units (`EXPLAINED_BY_UNITS`, `KIN_NEIGHBOURHOOD`); never an answer; an optional LLM may only choose among listed candidates (two independent asks must agree) | Demo level; not measured on real unknown words |
| `memory_frame`, `memory_*`, `project_frame` | Typed append-only project memory (closed kinds, witnesses, supersession, testimony vs evidence) so human-decided design, completion criteria and decisions survive context loss | 23/23 askable questions answered with record ids on a worked example |
| `conductor`, `conductor_run`, `agent_adapter`, `agent_runtime`, `verifier_agents` | The idea: Vera holds the human-decided frame, answers an agent's questions from it (or escalates with a typed reason), checks done-claims against witnesses, and drives a project to completion without a human in the loop. A verifier agent is an evidence producer, never a judge; protected actions always escalate | Scripted agent, 103 questions: **0 wrong** [N-53] at fake-asker accuracy 100/80/50%. **Real questions (130 an agent really asked a human, 72 with the human's answer): 0 answered, 72 escalated, 0 wrong** [N-54][N-55] — safe and not yet useful; 50.8% of those exchanges can be turned into askable typed decisions |

### Gold probe (the corpus used as a ruler)
`tools/gold_probe.py` measures the reader on a Codex-generated Japanese corpus with gold answers (who-did-what questions over 16 grammatical phenomena, paraphrase/entailment pairs, question paraphrases). **TRAIN split only; the heldout split is sealed and was never opened.** On 2,400 items (150 per phenomenon): correct 87 (3.6%), wrong 2 (+17 head/modifier mismatches), abstain 2,294 — the reader is precise and very incomplete. Where the answers are lost (1,500 items): 73% reading side (unrepresented content, multiple predicates, ambiguous に/で/と roles), 23% question side. The corpus (about 8.9 M generated items) is private and is not distributed; authors and gold come from the same model family, so expect optimism.

### Behaviour changes from 0.1.0 (the base modules were updated)
`base`, `bot`, `chat`, `frames`, `surface`, `verdict` now come from the integration branch of Verantyx-Vera-alpha: answers must carry the identity and text of their sources, and ties abstain. In pack-only mode this changes three of the old example outputs: `猫とは何ですか` is refused ("the source sentence cannot be confirmed": the pack keeps counts and one witness, not every source text), the pun for 「猫」 abstains because its candidates tie, and the haiku request is refused with a different message. The other example answers are unchanged. The 0.1.0 behaviour is at the v0.1.0 tag.

### Status you should know before using this
- **Prototype, paused.** No claim of adoption; no sealed evaluation of this update (a preregistered, independently judged run is planned and will be reported in `EVAL.md`).
- **Tests.** `PYTHONPATH=vera_base python -m pytest tests` in a clean clone: **1,666 passed, 18 failed, 9 skipped.** The failures are listed in `KNOWN_ISSUES.md`. `tools/demo_generate.py`, `demo_outside.py`, `demo_vocab.py`, `demo_frame.py` print `DEMO OK`; `demo_conduct.py` and `demo_system.py` currently fail.
- **The LLM rule.** Nothing in Vera uses an LLM or a learned model to produce an answer, a sentence, a fact or a decision. Allowed: external agents driven by the conductor as hands, outside the answering path, and an LLM as a *closed-choice asker* (an option index or null; two independently worded asks must agree; stored as testimony). Older modules that call a model (`agent.py`, the optional two-stage check) are outside this rule and off by default.
- **Design rules kept throughout:** stack stages, never pool votes; ties abstain; typed refusals with evidence; Unknown is not No; generated text is typed and never evidence.

## What it does well (the base, measured 2026-09-28 on sealed data, judged by Claude)
| Capability | Result |
|---|---|
| Checking a claim against records (7 verdicts: supported / differs / contradicts / violates a rule / unconfirmed / not in the records / not a factual claim) | harmful errors 0–0.5% over 4 sealed rounds (820 claims); 0.08 ms per claim |
| Base routing over 160 mixed documents (stereo cross + fallback + sovereigns) | same accuracy as judging against the right document alone, 0 harmful verdicts, 0.37 ms median (flat search: 8.7 ms) |
| Kana conversion, readings, plain⇔polite, active⇔passive, arithmetic, units, dates, comparison, ordering, counting, question intent, syllogism, elimination | 7–8 of 8 on the development survey |
| Puns (sound play from readings) | 70% and 80% on two sealed rounds |
| Answers from a site's documents, with the source sentence | errors 9 → 5 of 200 after the stereo cross |

## What it refuses (measured, and by design)
Metaphor meanings, commonsense effects and uses, haiku and poems: two sealed rounds each failed (the most frequent thing in a corpus is the literal, not the intended meaning), so Vera says it does not know. Stories are only offered as a labelled passage from its corpus, never as new writing. Across 120 abilities taken from LLM benchmark taxonomies (JGLUE, llm-jp-eval, BIG-bench, HELM), about 45 fit this design (one right answer by rule, arithmetic or checking) and about 63 do not (open generation, dialogue, social and ethical judgment) — those belong to an LLM.

## A bot for your documents
Put `.txt` / `.md` files in a folder (sub-folders become sovereigns: separate trees under one root) and you have a bot that answers from them, in Japanese or English, with the sentence it answered from — or says the documents do not say.
```bash
vera-bot ./docs                        # ask in the terminal; "/judge <claim>" checks a claim
vera-server --docs ./docs --port 11435 # Ollama-compatible /api/chat and OpenAI-compatible /v1/chat/completions
```
```python
import vera_base
bot = vera_base.Bot.from_dir("docs")
bot.reply("何冊まで借りられますか。")      # 貸出は一人5冊までで、期間は2週間です。（「利用案内.txt」より）
bot.reply("How many books can I borrow?")  # Each person may borrow five books. (from guide_en.txt)
bot.judge("The library is not closed every Monday.")  # CONTRADICTED (negation)
```
Questions are matched to document sentences by content words, counters (何冊 ↔ 5冊), conditions (〜したら ↔ 場合は, if/when) and question type (いつ / when ↔ days and times), after the stereo cross narrows the documents. Paraphrases a dictionary would bridge (お弁当を食べた ↔ 飲食) are not bridged.

Also included: English claims checked against Japanese documents with a glossary (`vera_base.crossverify`), and a two-stage check that sends only undecided claims to a local LLM and verifies its quotes in code (`vera_base.two_stage`, off unless a local server is running).

## Use
```bash
pip install vera-ja
```
The Codex sentence corpus (about 1.16M sentences, 33 MB) is on the v0.1.0 release (the Releases page of this repository) and is fetched on first use by `vera_base.corpus.fetch()`.
```python
import vera_base
chat = vera_base.Chat([{"title": "営業案内", "ja": "定休日は毎週水曜日です。"}], tree=True)
print(chat.reply("定休日はいつですか。")["text"])      # 定休日は毎週水曜日です。（「営業案内」より）
print(chat.reply("「猫」でダジャレを作って。")["text"])  # 分かりません。候補が同点です。  (0.1.0 picked one; ties now abstain)

base = vera_base.Base()
base.add("規程", "警備員は業者に鍵を貸さない。ただし、部長が承認した場合は貸してよい。", "rules")
base.build()
print(base.judge("警備員は業者に鍵を貸した。"))           # UNCONFIRMED (scope): the exception may apply
```

## Contents
- `vera_base/verantyx/` — the code: the Vera base plus the semantic path, router, realizer, memory and conductor prototypes (from Verantyx-Vera-alpha, MIT)
- `tests/`, `tools/` — tests (`PYTHONPATH=vera_base python -m pytest tests`) and the measurement tools and demos named above
- `docs/` — design notes and results of each part (start with `docs/ROUND5A_STEREO_ROUTE_2026-10-02.md` and `docs/CONSTRUCTIONS_2026-10-02.md`), scout reports on connecting the older line
- `KNOWN_ISSUES.md` — the failing tests and demos of this snapshot
- `vera_base/data/chat_pack.json` — 853 topics → short sentences composed from events that ≥2 independent sources wrote, with source counts. The source sentences themselves are not included.
- `vera_base/data/pun_lexicon.json` — 6,000 predicates and their readings
- `EVAL.md` — the measurements behind the tables above

## Limits
Pack-only mode (this package) answers general-knowledge questions only for the 853 topics in the pack; the full system reads a 3.57M-sentence store that is not distributed. Word paraphrases (私用端末 ↔ スマートフォン) are not bridged without a dictionary. The base evaluations were made with generated sealed data and Claude's judgment (from 2026-09-30 sealed judging is done by an independent Codex run instead); no external evaluation has been done yet. The 2026-10-03 update has not been sealed-evaluated.
