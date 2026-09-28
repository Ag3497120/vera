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

## Use
```bash
pip install fugashi unidic-lite
```
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
