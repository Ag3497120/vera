# bank6: held-out bank for the loom evidence gate v3 (final)

`bank6.tsv`: 60 Japanese questions over the frozen fulllead corpus (`../data/S300_fulllead.jsonl`, sentence split
`../bank2/data/fulllead_sents.jsonl`). **26 answerable** and **34 unanswerable** items. It is the held-out check of the loom's evidence gate
v3 (`docs/LINE3_LOOM_REACH_DESIGN.md` §(d)). The questions were written by an author that never saw the gate's rule list, and the
audit was done without reading the rules. Use it once, after v3 is frozen, to measure reach (answerable answered correctly)
and safety (unanswerable abstained).

Columns (tab-separated, header starts with `#`): `#id kind shape subject question gold evidence notes audit`.
- `kind` = ANSWERABLE / UNANSWERABLE. `shape` = `-` for answerable. For unanswerable it is the trap shape of PROMPT6:
  `S1-alias` (別名/通称/読み of something with a different kind of name or none), `S2-place` (どの区/市/県 where the sentence names a
  different kind of place), `S3-person` (〜した人物 when the sentence names a person in another role), `S4-toshite` (a 〜としては fact
  not stated), `S5-paren` (a fact of the reading/gloss parenthesis that is not there), `S6-naming` (呼ばれる/称される for a name not
  given), `S7-near` (the sentence holds a neighbouring fact of the same type).
- `gold`: answerable = verbatim phrase(s) of a cited sentence, alternatives separated by `|` (scored by containment, as `../grade.py`).
  Empty for unanswerable.
- `evidence` = fulllead `title#i`, **0-based** over the lead's 「。」 split. One or two ids of one article: the answer sentence, or for
  unanswerable the subject sentence plus, where different, the sentence that tempts.
- `notes` (unanswerable) = `文: what the sentence says / 欠落: why the asked fact is absent / 誤答例: the plausible wrong answer`.
- `audit` = valid / fixed (dropped rows are listed in AUDIT6.md).

| part / shape | kept | valid / fixed | dropped |
|---|---|---|---|
| answerable | 26 | 11 / 15 | 4 |
| S1-alias | 5 | 4 / 1 | 1 |
| S2-place | 5 | 4 / 1 | 1 |
| S3-person | 5 | 1 / 4 | 1 |
| S4-toshite | 6 | 5 / 1 | 0 |
| S5-paren | 4 | 0 / 4 | 1 |
| S6-naming | 5 | 5 / 0 | 0 |
| S7-near | 4 | 3 / 1 | 2 |
| total | 60 | 33 / 27 | 10 |

## Provenance

- Authored by codex **gpt-6-luna** in `vera-impl/bank2-author/` (not in this repo) from `PROMPT6.md`. It had access only to the
  corpus file; its log shows it opened nothing else. One round, 70 items, with its own `check6.py` → `check6.txt` (PASS on the original).
  `PROMPT6.md` was written at 07:51:53 on 2026-10-13. That is after the v3 design commit **65b26d57** (07:48:19) and the owner's
  acceptance **bcf9c94c** (07:51:33), so the v3 rules were frozen before authoring. `docs/LINE3_LOCAL_DECISIONS.md` has no
  `evidence.v3` section with a sha, so the freeze of record is the design doc commit 65b26d57.
- Audited by **Claude Opus 5.5** on 2026-10-13, blind to the rules: [AUDIT6.md](AUDIT6.md). Every item is valid, fixed or dropped
  with a reason, 70 → 60. Every asked absent fact was searched in all 592 sentences. Ten answerable items repeated questions of
  bank2 / bank3 / questions.tsv; eight were re-asked on another fact of the same article and two were dropped.
- `MANIFEST.json` is the intake record: sha256 of the author's original, of `bank6.tsv`, of the corpus and of the checker, written
  before any Vera system read the bank. **No Vera system has read this bank before intake.**

## How to use

- Run the gate (v3, and v2 as the comparison) once on all 60 items, with the rules frozen. Report per part and per shape with
  counts: one unanswerable item is 20-25 points within a shape.
- Answerable: correct = answered and a gold alternative is in the answer. Unanswerable: correct = abstained; any answer, including
  a hedged value, is `answered_unans`. Note which `誤答例` fired.
- **Premise-false items** U07, U10 (a station in a 町 asked for its 市) and U09 (a 区 of 水戸市): a reply that names no 市 / 区
  (for example 「市ではなく芦北町」) counts as an abstention. Decide this before grading.
- **Extrapolation items** U35, U36 (the neighbouring station number): Y16/Y18 and OR07/OR09 are correct in the world but stated
  nowhere. An answer is `answered_unans`.

## Known limits

1. **Auditor-written items**: 10 answerable questions (A01, A09, A12, A14, A19, A22, A24, A25, A27, A28) and the re-targeted U13 / U29
   were written by the auditor, not the blind author. The auditor also did not read the rules, but was not blind to the earlier
   banks. Report these 12 items separately if the result hinges on them.
2. **Overlaps kept**: A05 (ジェンダー) and A08 (西成区) ask a narrower slot of a fact that questions.tsv a10 / a30 accept as a keyword.
   29 of the 43 articles also appear in earlier banks; no question repeats one.
3. **Outside knowledge**: 11 unanswerables are answerable from memory and 12 more partly (AUDIT6.md column "outside"). This matters
   for `no_tools` / `free_text` controls, not for the gate.
4. **Readings**: 3 of the 26 answerable items ask a reading (A09, A21, A22). If the reach gain sits in that slot type, report it
   separately.

## Checks

`check6.py` (run `python3 check6.py > check6.txt` here) → `check6.txt`: **PASS, 0 errors**. It verifies the corpus split identity, header
and ids, the minimum counts per part and shape, question form (ends in ？, no negation, contains the subject), evidence
resolution, verbatim golds not in the title or question, unanswerable notes, a recorded absence search per unanswerable item (0
hits in all 592 sentences), and that no question or answerable gold repeats bank2 / bank3 / bank4 / questions.tsv.
