---
language: ja
license: mit
tags:
- japanese
- rule-based
- no-weights
- verification
- predicate-argument-structure
library_name: none
pipeline_tag: text-generation
---

# Vera base (ja) — a Japanese chat and checker with no weights

Vera is not a neural network. It reads Japanese into **predicate–argument structure** (who did what to whom, negation, rule kind, condition, exception, filled-in omissions), keeps the owner's records in that form, and reaches them through a **stereo-cross tree with a flat fallback**, split into **sovereigns** (one tree per kind of document, joined under one root). Answers are computed by rules, arithmetic, and counts of independent sources. Nothing is trained; adding a document is adding rows.

It runs on a CPU in Python, answers in about 0.1–5 ms, and every answer either shows where it came from or says it does not know.

## What it does well (measured on sealed data, judged by Claude)
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
The Codex sentence corpus (about 1.16M sentences, 33 MB) is on the [v0.1.0 release](https://github.com/Ag3497120/vera/releases/tag/v0.1.0) and is fetched on first use by `vera_base.corpus.fetch()`.
```python
import vera_base
chat = vera_base.Chat([{"title": "営業案内", "ja": "定休日は毎週水曜日です。"}], tree=True)
print(chat.reply("定休日はいつですか。")["text"])      # 定休日は毎週水曜日です。（「営業案内」より）
print(chat.reply("「猫」でダジャレを作って。")["text"])  # 猫が寝込んだ。…

base = vera_base.Base()
base.add("規程", "警備員は業者に鍵を貸さない。ただし、部長が承認した場合は貸してよい。", "rules")
base.build()
print(base.judge("警備員は業者に鍵を貸した。"))           # UNCONFIRMED (scope): the exception may apply
```

## Contents
- `vera_base/verantyx/` — the code (a subset of Verantyx-Vera-alpha, MIT)
- `vera_base/data/chat_pack.json` — 853 topics → short sentences composed from events that ≥2 independent sources wrote, with source counts. The source sentences themselves are not included.
- `vera_base/data/pun_lexicon.json` — 6,000 predicates and their readings
- `EVAL.md` — the measurements behind the tables above

## Limits
Pack-only mode (this package) answers general-knowledge questions only for the 853 topics in the pack; the full system reads a 3.57M-sentence store that is not distributed. Word paraphrases (私用端末 ↔ スマートフォン) are not bridged without a dictionary. The evaluations were made with generated sealed data and Claude's judgment; an external evaluation has not been done yet.
