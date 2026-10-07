# bank2 — Japanese cross-sentence question bank (final)

`bank2.tsv`: 128 questions over two frozen corpora in `../data/`. Columns (tab-separated, header line starts with `#`):
`id kind corpus subject question gold evidence audit`. Gold alternatives are separated by `|`; unans gold is empty.
Round-1 rows (I2-, C2-, UF-, US-) come first, then round-2 rows (R2-), each in authoring order.

## Provenance

- Authored by codex **gpt-6-luna** from `PROMPT.md` / `PROMPT2.md` with access only to the two corpus files and its own
  outputs — it never saw Vera code or Vera results. Two rounds: round 1 = 120 items, round 2 = 44 new items written after
  reading the round-1 audit.
- Audited by **Claude Opus 5.5** after each round: every item valid / fixed / dropped with a reason —
  [AUDIT_r1.md](AUDIT_r1.md) (120 → 97) and [AUDIT_r2.md](AUDIT_r2.md) (44 → 31). Authoring workspace:
  `vera-impl/bank2-author/` (not part of this repo).
- Corpora: `../data/S300_fulllead.jsonl` (300 articles, full lead, 592 sentences when split on 「。」) and
  `../data/S3000.jsonl` (3000 articles, first sentence only). Their sha256 equal the copies the author used; see `MANIFEST.json`.

## Kinds and counts

| kind | meaning | corpus | n | round 1 | round 2 | audit valid / fixed |
|---|---|---|---|---|---|---|
| intra2 | answer is in a sentence of the subject's lead that does **not** contain the title | fulllead | 69 | 49 | 20 | 44 / 25 |
| cross2 | answer is in article B, reached only through A's sentence naming B; question names A, not B | s3000 | 9 | 8 | 1 | 1 / 8 |
| unans | subject exists, asked attribute is in no article of the corpus file; correct behaviour = abstain | fulllead 25, s3000 25 | 50 | 40 | 10 | 45 / 5 |
| total | | | 128 | 97 | 31 | 90 / 38 |

`evidence`: intra2 `title#i` (0-based sentence index, split on 「。」); cross2 `A;B`; unans `title#0` (fulllead) or `title` (s3000).

## Checks

`check_bank2.py` (run: `/Users/motonisihikoudai/vera-wiring/env/bin/python check_bank2.py`) validates the bank against `../data/`:
round-1 rules (gold verbatim in evidence, gold not in question, intra2 gold in no title sentence, cross2 gold in B and not in A,
unans gold empty) plus round-2 rules (R2 intra2 evidence index >= 2; R2 cross2: B not in question, A's title does not contain B,
no B reuse). Result in `check.txt`: **0 errors, 4 warnings** — C2-022 (round 1, kept by the round-1 audit) has A = タッチテニス
containing B = テニス; US-020 and R2-U010 (レバノン) are mentioned inside the title of another article, checked by hand (no answer there).

## Baselines (`baselines.py` → `baselines.txt`)

Gold-in-candidate rate (ties kept). **B1** keyword: all corpus units with the highest count of question terms.
**B2** keyword + hop: B1 candidates plus the next sentence of the same article (fulllead) / the sentence of every article whose
title occurs in a candidate (s3000). Tokenizers: MeCab (fugashi, content words) and character bigrams.

| kind | n | B1 MeCab | B2 MeCab | B1 bigram | B2 bigram |
|---|---|---|---|---|---|
| intra2 (all) | 69 | 47 (68%) | 57 (83%) | 38 (55%) | 54 (78%) |
| intra2 round 1 | 49 | 32 (65%) | 42 (86%) | 26 (53%) | 41 (84%) |
| intra2 round 2 | 20 | 15 (75%) | 15 (75%) | 12 (60%) | 13 (65%) |
| cross2 | 9 | 2 (22%) | 8 (89%) | 1 (11%) | 9 (100%) |
| unans | 50 | never abstains (candidates for 50/50) | 50/50 | 50/50 | 50/50 |

Missed by B2 with both tokenizers (hard core): I2-011, I2-014, I2-029, I2-031, I2-033, I2-039, R2-I003, R2-I006, R2-I013.

## Known limits (read before reporting numbers)

1. **cross2 is too small to report a rate (n = 9)**, and B2 ("follow every title in the best sentence") solves 8-9/9; in 8/9
   the A sentence contains exactly one other S3000 title, so title-following has no noise. Two authoring rounds showed that
   S3000 (first sentences only) offers few natural entity-to-entity bridges: round 2 produced 14 candidates, 13 dropped as
   dictionary definitions of generic concept articles or homonym links. Report cross2 per item, not as a percentage.
2. **B2 is strong.** For intra2, a system must beat 78-86% (B2) to show anything beyond "title sentence + next sentence";
   only the 9 hard-core items separate it. Round-2 intra2 removed the adjacency shortcut (B2 = B1) but B1 alone reaches 60-75%
   because questions share non-title keywords (years, names) with the evidence sentence.
3. **Adjacency in round 1:** 34/49 round-1 intra2 evidences are the sentence right after a title sentence (31 are sentence #1);
   4 items (I2-003..006) are one 駅番号 template. Round-2 intra2 all have index >= 2.
4. **unans:** keyword lookup always returns a candidate, so B1/B2 give no abstention baseline — a system's unans score must be
   read against its own answerable score. 10/50 use 最初/初めて phrasing (no answerable item does except I2-048). Subjects
   repeat: the 5 round-2 s3000 unans re-ask round-1 unans subjects, the 5 round-2 fulllead unans share subjects with round-2 intra2.
5. **Gold matching is verbatim-substring.** Numeric golds keep the corpus formatting (3万2,500キロワット, 73,921人, 2188人);
   a scorer should normalise digits, commas, units and spaces or accept the listed alternatives.
6. Some golds remain weakly guessable from world knowledge (e.g. R2-C006 最後の晩餐, R2-I007 日本海側気候, R2-I020 一方向),
   though none from the question or title string.
