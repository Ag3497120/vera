# bank3 — Japanese question bank of kinds absent from bank2 (final)

`bank3.tsv`: 91 questions over the two frozen corpora in `../data/` (the same files as bank2). Purpose: measure abilities
beyond verbatim one-sentence lookup ("unknown abilities"), e.g. with the minimal initial placement on vs off. Graded by the owner,
so items were audited for one clear answer and natural Japanese.

Columns (tab-separated, header starts with `#`): `id kind corpus subject question gold evidence notes audit`.
Gold alternatives are separated by `|` and each occurs verbatim in a cited evidence sentence; unans gold is empty;
summary-choice gold is `LETTER|option text`. `evidence` follows bank2: fulllead `title#i` (**0-based** sentence index, lead split
on 「。」), s3000 = bare article title; two ids are separated by `;`. `notes`: paraphrase word mapping, unknown-word
`question surface／corpus surface`, unans what is missing.

## Provenance

- Authored by codex **gpt-6-luna** from `PROMPT3.md` (in `vera-impl/bank2-author/`, not part of this repo), with access only to the
  two corpus files — it never saw Vera code or results. One round, 100 items.
- Audited by **Claude Opus 5.5**: every item valid / fixed / dropped with a reason — [AUDIT3.md](AUDIT3.md) (100 → 91).
  The author's original file and its sha256 are recorded in `MANIFEST.json`.
- `MANIFEST.json` = the G1 intake record: sha256 of `bank3.tsv` and of both corpora, written before any Vera system read the bank.
  Corpora sha256 equal the author's copies and bank2's.

## Kinds and counts

| kind | what it asks | corpus | n | valid / fixed | dropped |
|---|---|---|---|---|---|
| two-facts | answer needs two sentences of one article (one identifies the subject or holds half of the answer) | fulllead | 14 | 3 / 11 | 6 |
| paraphrase | no character bigram shared with the gold sentence (subject removed) | fulllead | 20 | 5 / 15 | 0 |
| unknown-word | subject written in a form absent from both corpora (space split, suffix added, ボイス/ヴォイス, ・, case) | fulllead | 18 | 7 / 11 | 2 |
| compare | 「XとYのうち、〜が早いのはどちらですか」; X, Y described, not named; gold = title | s3000 | 14 | 7 / 7 | 1 |
| summary-choice | 「Xについて正しいのはどれですか」 with A/B/C in the question | fulllead | 10 | 0 / 10 | 0 |
| unans-kind | forms of the kinds above whose answer is in neither corpus file; correct behaviour = abstain | fulllead 14, s3000 1 | 15 | 7 / 8 | 0 |
| total | | | 91 | 29 / 62 | 9 |

## Checks

`check_bank3.py` (run: `python3 check_bank3.py`) → `check.txt`: **0 errors**. It verifies counts, unique ids, evidence resolution,
every gold alternative verbatim in cited evidence and absent from the question, two-facts = two sentences of one article, the
author's strict paraphrase bigram rule, unknown-word surface absent from both corpus files, compare titles absent from the question
and the gold's stated year earlier, summary-choice letter/option/length (<= 25), no duplicated (sentence, gold) pair; INFO lines give
letter balance (A3/B4/C3), compare answer position (7 first / 7 second), reuse and bank2 overlap.

## Baselines (`baselines.py` → `baselines.txt`; run with `/Users/motonisihikoudai/vera-wiring/env/bin/python`)

Same B1 (keyword, ties kept) and B2 (B1 + next sentence / followed title) as bank2; MeCab / character bigrams.

| kind | n | B1 | B2 | other |
|---|---|---|---|---|
| two-facts | 14 | 3 (21%) / 1 (7%) | 8 (57%) / 6 (43%) | both evidence sentences in B2: 5/14 |
| paraphrase | 20 | 8 (40%) / 6 (30%) | 12 (60%) / 10 (50%) | |
| unknown-word | 18 | 16 (89%) / 14 (78%) | 16 (89%) / 15 (83%) | B1 after kana normalisation 17 (94%) / 14 (78%); B1 with the subject deleted 16 (89%) / 15 (83%) |
| compare | 14 | | | lookup + compare stated years: 13 (93%) / 12 (86%); answer-the-first 7/14; chance 50% |
| summary-choice | 10 | | | pick the option with most term overlap in the subject's article: 9.0 (90%) / 9.5 (95%); always-one-letter <= 4/10; chance 33% |
| unans-kind | 15 | candidates 15/15 | | keyword lookup never abstains |

## Known limits (read before reporting numbers)

1. **Only paraphrase and two-facts can separate the foundation from lookup.** Trivial lookup already reaches 86-95% on
   unknown-word, compare and summary-choice; on/off differences there can only reveal a loss relative to lookup, not a gain.
2. **unknown-word does not test surface mapping.** With the altered subject deleted from the question, B1 still finds the gold in
   16/18: the remaining words locate the sentence in a 592-sentence corpus. Kana normalisation (NFKC + MeCab reading) adds one
   item and is unnecessary. There are no kana-spelling items: almost every kanji title's reading is in its lead's gloss, so the kana
   form occurs in the corpus; and MeCab readings are wrong for exactly such cases (古浄瑠璃 → フルジョウルリ).
3. **compare is one comparison type** (earlier year) over unrelated entity pairs that are described, not named; the description
   step is an extra identify-by-description hop. Descriptions are unique in S3000 (searched).
4. **two-facts is mostly "identify the subject from one sentence, answer from another"** (riddle-style descriptions), not
   entity-to-entity bridging; descriptions are unique in the corpus.
5. **Small n**: one item = 5-10 points. Report per item, or per kind with counts.
6. **Concentration and reuse**: 91 rows use 68 articles (CUBE JUICE ×6, ハッシュテーブル ×5, フェミニズム ×5 …); all unans subjects
   are subjects of answerable items; 16 answerable items re-ask a bank2 fact in a new form (useful as a literal-vs-new-form contrast:
   ids in `check.txt`).
7. **Grading**: numeric golds keep corpus formatting (3万2,500キロワット, 120 m, 約27.3日); accept the listed alternatives and
   obvious short forms (能登町, 丈夫, 一丁目から三丁目). For summary-choice grade the letter; for compare the entity (title or an
   unambiguous reference to it).
