# bank7: held-out bank for the output gate v4

`bank7.tsv`: 79 Japanese questions over the frozen fulllead corpus (`../data/S300_fulllead.jsonl`; sentence split = the lead split on 「。」, evidence ids
`title#i`, 0-based). **32 answerable** and **47 unanswerable** items. It is the one-shot held-out check of the output gate v4 (`docs/LINE3_PUBLIC_DESIGN.md`
section 5). The questions were written by an author that never saw the gate's rules, and the audit was done without reading them. Use it once,
after v4 is frozen, to measure reach (answerable answered correctly) and safety (unanswerable abstained); if the rules change afterwards, the next
revision needs a new bank (bank8).

Columns (tab-separated, header starts with `#`): `#id kind shape subject question gold evidence notes audit`, the bank6 columns.
- `kind` = ANSWERABLE / UNANSWERABLE. `shape` = `-` for answerable. For unanswerable it is one of `S1-alias`, `S2-place`, `S3-person`, `S4-toshite`,
  `S5-paren`, `S6-naming`, `S7-near` (the bank6 shapes, README there) and the new **`S8-chain`**: the subject is a chain 「XのYのZ」 and the corpus
  holds the Z-type fact only for X, for Y or for another entity, never for the entity the chain points to.
- `gold`: answerable = verbatim phrase(s) of the cited sentence, alternatives separated by `|` (containment scoring as `../grade.py`); empty for unanswerable.
- `evidence` = one or two `title#i` ids of one article (answerable: the answer sentence; unanswerable: the subject sentence plus, where different, the tempting
  sentence; U47 / U48 also cite the sentence of another article that holds a postal code, the tempting wrong answer).
- `notes` (unanswerable) = what the sentence says / why the asked fact is absent / the plausible wrong answer. `audit` = valid / fixed.

| part / shape | kept | valid / fixed | dropped |
|---|---|---|---|
| answerable | 32 | 21 / 11 | 4 |
| S1-alias | 6 | 6 / 0 | 0 |
| S2-place | 5 | 4 / 1 | 1 |
| S3-person | 6 | 4 / 2 | 0 |
| S4-toshite | 6 | 6 / 0 | 0 |
| S5-paren | 6 | 6 / 0 | 0 |
| S6-naming | 5 | 4 / 1 | 1 |
| S7-near | 5 | 5 / 0 | 1 |
| S8-chain | 8 | 8 / 0 | 0 |
| total | 79 | 64 / 15 | 7 |

The brief asked 30 + 40 kept; the author over-produced 86 (36 + 50) and 79 survived, so the surplus (2 answerable, 7 unanswerable) is kept, not trimmed.

## Provenance

- Authored by codex **gpt-6-luna** in `vera-impl/bank7-author/work7/` (not in this repo), a fresh directory holding only the corpus and
  `EXCLUDED_ARTICLES.txt`, from `vera-impl/bank2-author/PROMPT7.md`. Launched with the same launcher as bank6 (`.claude/vera-audit/fleet.sh`, `jobs7.tsv`,
  model L, effort max, workspace-write sandbox). One round, 86 items, with its own `check7.py` -> `check7.txt` (PASS on the original). Its log
  (`bank2-author/fleet-out7/bank7.log`) shows it opened only the corpus and the exclusion list. The brief and the launcher log are not copied here.
- **`PROMPT7.md` was written at 2026-10-13T10:11:43+09:00** (file mtime, sha256 `36a7a24e...`); the author's `bank7.tsv` was written at 10:50:46 (its checker at 10:50:14).
  For timing against the gate freeze: the git history of `line3` shows `evidence.v4 (frozen, not default)` merged at 10:48:24, so the author's output was
  written after that freeze and the brief before it. The author never had the rules; the auditor never opened `evidence.py` or the gate documents.
- The brief carried a list of 110 article titles to avoid (the evidence articles of banks 2, 3, 4 and 6). The list missed the titles that contain a space
  (see AUDIT7.md), so five articles were used that should have been excluded; the audit's mechanical comparison dropped every item that repeated an earlier question.
- Audited by **Claude Sonnet 5.5** on 2026-10-13, blind to the rules: [AUDIT7.md](AUDIT7.md). Every item is valid, fixed or dropped with a reason, 86 -> 79.
  The auditor wrote the replacement questions of A27, U10, U13, U14 and U33 (author's text otherwise); report these 5 separately if a result hinges on them.
- `MANIFEST.json` is the intake record: sha256 of the author's original, of `bank7.tsv`, of the corpus and of the checkers, written before any Vera system
  read the bank. **No Vera system has read this bank before intake.**

## How to use

- Run the gate (v4, and v3 as the comparison) once on all 79 items with the rules frozen. Report per part and per shape with counts: one unanswerable
  item is 20 points within a shape of 5. Answerable: correct = answered and a gold alternative is in the answer. Unanswerable: correct = abstained; any
  answer, including a hedged value, is `answered_unans`; note which wrong answer (notes) fired.
- **S8-chain**: U43..U46 (parent entity's population) are the clean kind; U47 / U48 (postal code of a place) and U49 / U50 (a person / company of a chain)
  are separate kinds; report S8 as a whole and, if the result hinges on it, by kind.
- **Extrapolation**: for U43..U46 and U49 the true answer is common knowledge; answering from memory is `answered_unans` too.

## Known limits

1. **Auditor-written items**: A27, U10, U13, U14, U33 (the replacement questions).
2. **Overlaps kept**: 15 items share an article with an earlier bank and ask another fact (AUDIT7.md); 19 % of the items (15 of 79) come from articles used before.
3. **Outside knowledge**: 10 kept unanswerables are answerable from memory and 14 partly. This matters for `no_tools` / `free_text` controls, not for the gate.
4. **Article concentration**: one article carries four items (私は息子を兵士に育てなかった: A35, A36, U15, U36) and five carry three (プリンツ・アーダルベルト級装甲巡洋艦, CUBE JUICE, 三水区, 2011年世界男子ハンドボール選手権, アルガルヴェ・カップ2017).
5. **No S8 of the brief's station / parent-company kind**: the corpus has no such article pair; the S8 items are population / postal code / birth year / founding year chains.

## Checks

`check7.py` (run `python3 check7.py > check7.txt` here) -> `check7.txt`: **PASS, 0 errors**. It verifies the corpus, header and ids, counts per part and shape
(>= 30 / 40, every shape >= 4, S8 >= 6), question form (ends in ？, no negation), evidence resolution, verbatim golds not equal to the title or in the question,
the recorded absence search of every unanswerable item (0 hits, 47 terms), and that no question text repeats bank2 / 3 / 4 / 6 or `questions.tsv` and no
answerable item repeats an earlier gold on the same article.
