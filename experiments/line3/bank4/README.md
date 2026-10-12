# bank4 — adversarial unanswerable questions (final)

`bank4.tsv`: 35 Japanese questions over the frozen fulllead corpus (`../data/S300_fulllead.jsonl`, sentence split
`../bank2/data/fulllead_sents.jsonl`). **Every item is unanswerable from the corpus**: the correct behaviour is to abstain. Each
question is built next to a sentence that states a closely related fact, so a reader that returns the nearest matching span answers
wrongly. Purpose: the unanswerable side of the loom control experiment (does a model that may only output through Vera abstain
where a free-text model, or a model without tools, fills the gap?).

Columns (tab-separated, header starts with `#`; same as bank3): `id kind corpus subject question gold evidence notes audit`.
`gold` is always empty. `evidence` = fulllead `title#i` (**0-based** sentence index, lead split on 「。」), up to two ids of one article:
the sentence that contains `subject` and, where different, the neighbouring sentence that tempts. `notes` = `a) what the sentence
says; b) what is asked and why it is absent; c) the plausible wrong answer` (c) occurs verbatim in the corpus and is not a correct
answer). `audit` = valid / fixed.

## Provenance

- Authored by codex **gpt-6-luna** (in `vera-impl/bank2-author/`, not part of this repo) with access only to the corpus file — it never
  saw Vera code or results. One round, 40 items, its own mechanical check `check4.py` → `check4.txt` (copied here unchanged; they
  refer to the original 40 rows and to `../S300_fulllead.jsonl` relative to the author's `out/`).
- Audited by **Claude Opus 5.5** on 2026-10-12: every item valid / fixed / dropped with a reason — [AUDIT4.md](AUDIT4.md) (40 → 35).
  The asked fact was searched in all 592 sentences (every article, paraphrases and units included).
- `MANIFEST.json` = the intake record: sha256 of the author's original, of `bank4.tsv`, of the corpus files and of the loom task file,
  written before any Vera system read the bank. **No Vera system has read this bank before intake.**

## Kinds and counts

| kind | the trap | n | valid / fixed | dropped |
|---|---|---|---|---|
| near-fact | a neighbouring fact of the same subject is stated (year but not day, city but not stadium, father but not mother) | 8 | 2 / 6 | 2 |
| same-slot | the sentence fills a slot frame (面積…人口…, 最大の島は…, 娘や妻は…) and the question asks an unfilled slot of that frame | 10 | 9 / 1 | 0 |
| numeric | a number with a unit sits next to the asked, absent number (height vs crest length, length vs width, countries vs players) | 8 | 2 / 6 | 2 |
| entity-swap | a second entity is mentioned in passing; the question asks a fact of THAT entity (its HQ, state, opening year) | 9 | 0 / 9 | 1 |
| total | | 35 | 13 / 22 | 5 |

Dropped: ADV-002 (inferable), ADV-003, ADV-024 (one-word qualifier tricks), ADV-029 (duplicate of ADV-028), ADV-032 (the distractor is
the real answer). Fixed include two repeats of bank2 unanswerables (ADV-025 = R2-U003 verbatim, ADV-005 ≈ UF-010) re-asked as new
absent facts.

## How to use

- **Unanswerable only.** Score abstention: correct = abstained (for the free-text control, an answer line starting with 「不明」).
  Any answer, including a hedged value, is `answered_unans`. Note which c) value was given — it shows which trap fired.
- **Loom control experiment**: `../loom/tasks_unans_adv.jsonl` holds one row per item per mode, in the schema of
  `tasks_bank2.jsonl` (`bank2_id`, `base`, `corpus`, `lang`, `mode`, `task_id`, `text`, `tiers`, `control` for controls), task ids
  `bank4/ADV-nnn.<mode>`, `text` = the question without its final 「。」:
  `record_only`, `constructed_allowed`, `free_text` (mode record_only + `control: free_text`, as in tasks_bank2) and `no_tools`
  (`mode: no_tools`, `control: no_tools`). The file deliberately has **no gold key** — the served bank must not reveal that the
  answer is empty. Two harness gaps before running: (a) `harness.py` has no `no_tools` agent (`AGENT_OF_MODE`); `mode: no_tools`
  is set so that the current code fails loudly instead of silently running a record_only weaver; (b) `score.py` reads gold from
  `bank2.tsv` and treats a row as unanswerable only if its kind is `unans` — point it at `bank4/bank4.tsv` and map all four kinds to
  `unans`.
- Run every system on the same 35 items and report per item or per kind with counts (one item = 11-13 points within a kind).

## Known limits

1. **Corpus-unanswerable, not world-unanswerable.** 9 items are answerable from a strong model's own knowledge and 12 more partly
   (AUDIT4.md column "outside knowledge"). A `no_tools` / `free_text` answer from memory is still `answered_unans` here (the task is to
   answer from the corpus), but report those items separately when comparing against the loom.
2. **Granularity items**: ADV-001 and ADV-008 state the year / month and ask the day. A reply such as 「2002年（月日は不明）」 is a
   partial abstention; decide before grading whether it counts as abstained (recommended: yes only if it says the asked part is absent).
3. **Weak traps**: ADV-012 and ADV-015 have c) values of the wrong type; the temptation is the adjacent sentence. ADV-037's c) 2022年
   also occurs in the question.
4. **Reuse**: 34 articles; 17 are also cited by bank2 and 11 by bank3 (`check.txt`), never with the same question after the fixes.
   ADV-018/ADV-031 share 川原石駅#0.
5. **No answerable twins**: the bank has no matched answerable questions; read a system's abstention here against its own answerable
   rate on bank2/bank3 (a system that always abstains scores 100% here).

## Checks

`check_bank4.py` (run: `python3 check_bank4.py`) → `check.txt`: **0 errors**. It verifies the corpus split identity, header and ids,
kinds ≥ 8, gold empty, question form and no negation, subject in the question and in a cited sentence, evidence resolution, c) in the
corpus, and the loom task file (4 rows per item, tasks_bank2 schema, no gold key).
