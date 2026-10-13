# Audit of bank 8 (bank8.tsv, held-out bank; NOT in any repo worktree)

Auditor: Claude (Sonnet 5.5), 2026-10-13. Inputs: `bank2-author/PROMPT8.md` and `PROMPT8b.md` (the briefs), the author's two files
`bank8-author/original/bank8.tsv` (round 1, 102 items, B8-A01..A42 / B8-U01..U60) and `bank8-author/original_b/bank8b.tsv` (round 2, 104 items,
B8b-A01..A42 / B8b-U01..U62), both by codex **gpt-6-luna**, the author's checkers, the corpus `S300_fulllead.jsonl` (sha256 d987fdee...) and the earlier banks
(`experiments/line3/bank2,3,4,6,7` and `questions.tsv`, read only). No Vera gate, reader, loom or other Vera system has read this bank;
`verantyx/loom/evidence.py` and the design documents were **not** opened; `vera-impl/hidden`, `face-design/vera1.txt` and `experiments/line3/bank_ls/` were not opened.

## Two rounds (deviation from the brief)

Round 1 (`PROMPT8.md`, fresh dir with only the corpus) came back clean by its own checker, but the author walked the corpus from the top and put **85 of 102 items on
articles that earlier banks already use** (only 17 on fresh ones); 18 of the 42 answerables repeated an earlier gold on the same article (mechanical check below) and
14 unanswerables repeated an earlier asked fact. Dropping those would have left too few items, so a **second round** (`PROMPT8b.md`, fresh dir `work8b/`: corpus
plus `EXCLUDED_ARTICLES.txt` = the 182 corpus titles that appear in banks 2/3/4/6/7 or `questions.tsv`, built from exact titles so the space bug of bank7 cannot recur)
asked for the same shapes again, plus 12 S9 items, on **articles no earlier bank uses** (tempting sentences of S8/S9 may come from an excluded article). Round 2
yielded 42 + 62 items with **no mechanical repeat at all**. The final bank is chosen from both rounds (round 2 by preference). Round 2's first launch died on a network error
(log kept in `bank2-author/failed_attempts8b/`); the identical prompt was relaunched; its last codex message and `README8b.md` were lost to a second network error, but the
bank and `check8b.py` were already written (check8b.txt was produced by running the author's script; its `PASS` is that script's).

## Rules applied to every item

- **Answerable**: gold verbatim in the cited sentence, shortest answering phrase (shorter verbatim alternatives added with `|`); the question names its subject;
  one clear answer; not answerable from the title alone; not a repeat of an earlier bank (same article and same gold, or same relation).
- **Unanswerable**: the asked fact is absent from the whole corpus (search terms recorded in `check8.py` `ABSENT`, 0 hits, scope corpus or subject article); the subject occurs
  in the corpus; tempting; no negation, no false premise (items asking a 区 of a city that has none, or a 市 of a 郡, were dropped), no single-qualifier trick, not inferable; not a
  repeat of an earlier bank; not a duplicate within bank8.
- **S8-chain**: the question is a chain 「XのYのZ」 and the corpus states the Z-type fact only for X, for Y or for another entity.
- **S9-name** (new): the subject is a rare proper name (katakana or unusual kanji; small town, village, station, shrine, bridge, embassy, minor person), and the asked fact is
  stated in the corpus only for a different entity that shares a kind word with it (県, 村, 駅, 神社, 橋, 大使館); the kind word is recorded per item in `check8.py` `KIND`
  and the checker requires it in both article titles. The tempting sentence is the second evidence id.
- **Per-article cap**: at most 2 items of a part (and at most 3 in all) per subject article.

## Mechanical reuse check (`check8.py`; run over the final bank and, ad hoc, over all 206 authored items)

- Question text identical (normalised) to a question of bank2/3/4/6/7 or `questions.tsv`: **0** in the final bank (0 in the authored 206 as well).
- Same article and same gold as an earlier answerable item: **0** in the final bank; in the authored 206, **18** answerables (all round 1) were caught
  (A01 A05 A07 A10 A12 A13 A14 A15 A16 A17 A18 A19 A25 A28 A29 A32 A36 A38) and dropped; the read of earlier questions added A20 (asks a fact that questions u27 holds as unanswerable) and A26 (gold 'topjohnwu' vs 'topjohnwu氏').
- Asked-fact wording (subject removed) with char-bigram Jaccard >= 0.40 against a same-article earlier question: **0** in the final bank (max 0.06); it caught 5 authored items
  (B8-U03, U38, U44, U45, U46). The rest of the repeats in the table below were found by reading the earlier questions of every article-sharing item.
- Zero reuse of any (article, asked fact) pair of bank2, bank4, bank6, bank7 (and bank3, questions.tsv) is therefore guaranteed mechanically for questions and golds, and by the
  item-by-item read for the unanswerable relations. bank5 (`bank5.jsonl`, memory dialogues, other corpus) cannot overlap.

## Counts (over the 206 authored items)

| part / shape | authored | valid | fixed | dropped (invalid / repeat) | surplus (valid, not selected) | kept |
|---|---|---|---|---|---|---|
| answerable | 84 | 23 | 12 | 24 (4 / 20) | 25 | 35 |
| S1-alias | 12 | 5 | 0 | 2 (0 / 2) | 5 | 5 |
| S2-place | 12 | 5 | 0 | 5 (4 / 1) | 2 | 5 |
| S3-person | 12 | 5 | 0 | 3 (0 / 3) | 4 | 5 |
| S4-toshite | 12 | 5 | 0 | 3 (0 / 3) | 4 | 5 |
| S5-paren | 12 | 5 | 0 | 1 (0 / 1) | 6 | 5 |
| S6-naming | 12 | 5 | 0 | 0 (0 / 0) | 7 | 5 |
| S7-near | 12 | 5 | 0 | 4 (2 / 2) | 3 | 5 |
| S8-chain | 16 | 2 | 3 | 1 (0 / 1) | 10 | 5 |
| S9-name | 22 | 7 | 3 | 4 (3 / 1) | 8 | 10 |
| **total** | 206 | 67 | 18 | 47 (13 / 34) | 74 | 85 |

"valid" / "fixed" count kept items only (fixed = gold alternatives added, evidence or note corrected, or question re-worded). "surplus" items read as valid but were not
selected (their absence searches were **not** run, so they are not certified). Targets: 35 answerable and 50 unanswerable kept; S1..S8 at least 5 each (5 each), S9 at least 8 (10).
The kept bank contains **6 items from round 1** (B8-U09, U11, U39, U55, U58, U60) and 79 from round 2.

## Auditor-written text

Only the three S8 re-wordings (B8b-U45, B8b-U47, B8b-U48: the author's relative-clause chains rewritten as 「XのYのZ」, same fact) and the `|` gold alternatives of 13 answerables
(listed in the table) are the auditor's; every other question is the author's text, apart from the full-width 「？」 normalisation of round-1 questions. Report these separately
if a result hinges on them.

## Overlaps with earlier banks

Items whose **subject article** is also in an earlier bank (4; each asks another fact):

- B8-U09 重山: bank3 b3_uk11 (name origin), bank4 ADV-022 (trail length); asks the 市.
- B8-U39 2005年アジア野球選手権大会: bank4 ADV-006 (ballpark); asks the champion.
- B8-U55 犂神社: questions a50 (where); asks the 旧社格.
- B8-U60 要田駅: bank6 B6-A21 (reading of 字 寺向); asks the 駅番号.

Items whose **tempting sentence** comes from an earlier-used article (the asked fact is stated there for another entity, by design; the earlier questions asked other facts):
B8b-U44 (花園町駅), U47 / U48 (ネノ), U51 (在ハイチ日本国大使館), U52 (奥多摩橋: bank4 ADV-021 asks its 幅員), U54 and B8-U55 (千葉神社), U56 (テレゴ県),
U62 / B8-U58 (川原石駅), B8-U60 (海浦駅: bank2 I2-006 asks its 駅番号, here the 駅番号 of 要田駅 is asked).

**Within bank8**, articles with two items: 
下甘田村 (B8b-A11, B8b-U02); マハナイム (B8b-A13, B8b-U27); フルヴィッツのゼータ函数 (B8b-A18, B8b-U14); カン・エア (B8b-A20, B8b-U38); マッキルベイン緩衝液 (B8b-A21, B8b-U17); 方城駅 (B8b-A30, B8b-U37); 勝岩駅 (B8b-A33, B8b-U08); エネトピア (B8b-A34, B8b-U22, B8b-U49); 屋久島ラーメン (B8b-A35, B8b-U21); .yokohama (B8b-A40, B8b-U42); TEAM MAKEHEN (B8b-A41, B8b-U13); PDF-XChange (B8b-U01, B8b-U20); 在キューバ日本国大使館 (B8b-U04, B8b-U51); 東山県 (B8b-U10, B8b-U47); THREE1989 (B8b-U16, B8b-U41); シュタイアーベルク (B8b-U25, B8b-U45); 武寧県 (B8b-U26, B8b-U35); つちのこ神社 (B8b-U32, B8b-U54); 城站駅 (B8b-U44, B8b-U62); 上宇和村 (B8b-U48, B8b-U60).

## Per-item disposition (all 206 authored items)

| id | kind / shape | disposition | reason |
|---|---|---|---|
| B8-A01 | answerable | dropped (repeat) | repeats bank2 I2-001 (別名 ハッシュ表) |
| B8-A02 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A03 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A04 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A05 | answerable | dropped (repeat) | repeats questions a36 (囲碁) |
| B8-A06 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A07 | answerable | dropped (repeat) | repeats bank6 B6-A13 (制定日) |
| B8-A08 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A09 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A10 | answerable | dropped (repeat) | repeats bank6 B6-A18 (1972年からの編成) |
| B8-A11 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A12 | answerable | dropped (repeat) | repeats bank6 B6-A20 (番組名の由来) |
| B8-A13 | answerable | dropped (repeat) | repeats questions a48 (大川) |
| B8-A14 | answerable | dropped (repeat) | repeats questions a17 (JR東日本) |
| B8-A15 | answerable | dropped (repeat) | repeats bank2 I2-012 (通称 深川八幡宮) |
| B8-A16 | answerable | dropped (repeat) | repeats bank7 B7-A05 (6月第3週) |
| B8-A17 | answerable | dropped (repeat) | repeats bank6 B6-A25 (Kリーグ2) |
| B8-A18 | answerable | dropped (repeat) | repeats questions a25 (神崎郡) |
| B8-A19 | answerable | dropped (repeat) | repeats bank2 R2-I010 (波胡曽神) |
| B8-A20 | answerable | dropped (repeat) | asks the 標高 that questions u27 records as unanswerable (same fact) |
| B8-A21 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A22 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A23 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A24 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A25 | answerable | dropped (repeat) | repeats bank2 I2-032 (製鋼所) |
| B8-A26 | answerable | dropped (repeat) | repeats questions a49 (topjohnwu) |
| B8-A27 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A28 | answerable | dropped (repeat) | repeats bank2 I2-016 (地上から) |
| B8-A29 | answerable | dropped (repeat) | repeats bank6 B6-A14 (ヒューレット・パッカード) |
| B8-A30 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A31 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses; gold would need alternatives (list) |
| B8-A32 | answerable | dropped (repeat) | repeats bank2 R2-I012 (2188人) |
| B8-A33 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A34 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A35 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A36 | answerable | dropped (repeat) | repeats questions a32 (小野拓実) |
| B8-A37 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A38 | answerable | dropped (repeat) | repeats bank3 b3_pa19 (約27.3日) |
| B8-A39 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A40 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A41 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-A42 | answerable | surplus | valid on reading (gold verbatim, new fact, may share the article with an earlier bank); not selected because round 2 supplied enough items on articles no earlier bank uses |
| B8-U01 | S1-alias | dropped (repeat) | repeats bank6 B6-U26 (ATACS 何の略称 = 展開形) |
| B8-U02 | S1-alias | surplus | plausible; would need re-asking as 英語名 (the opposite concept carries the only English form); not selected |
| B8-U03 | S1-alias | dropped (repeat) | repeats bank6 B6-U01 (ハッシュ表の読み) |
| B8-U04 | S1-alias | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U05 | S1-alias | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U06 | S1-alias | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U07 | S2-place | dropped | 郡 asked for a 市: false premise (a district is not in one city) |
| B8-U08 | S2-place | dropped | 呉市 has no 区: false premise |
| B8-U09 | S2-place | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8-U10 | S2-place | dropped (repeat) | repeats bank6 B6-U07 (海浦駅 どの市) |
| B8-U11 | S2-place | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8-U12 | S2-place | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U13 | S3-person | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U14 | S3-person | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U15 | S3-person | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U16 | S3-person | dropped (repeat) | near-repeat of bank6 B6-U18 (who translated the same chronicle) |
| B8-U17 | S3-person | dropped (repeat) | repeats bank7 B7-U15 (最初の録音/初演者) |
| B8-U18 | S3-person | dropped (repeat) | near-repeat of bank7 B7-U13 (logo/icon designer) |
| B8-U19 | S4-toshite | dropped (repeat) | repeats bank3 b3_uk01 (平均計算量) |
| B8-U20 | S4-toshite | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U21 | S4-toshite | dropped (repeat) | repeats bank4 ADV-022 (登山道の長さ) |
| B8-U22 | S4-toshite | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U23 | S4-toshite | dropped (repeat) | repeats bank7 B7-U39 (参加チーム数) |
| B8-U24 | S4-toshite | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U25 | S5-paren | dropped (repeat) | repeats bank6 B6-U26 (ATACS 展開形) |
| B8-U26 | S5-paren | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U27 | S5-paren | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U28 | S5-paren | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U29 | S5-paren | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U30 | S5-paren | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U31 | S6-naming | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U32 | S6-naming | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U33 | S6-naming | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U34 | S6-naming | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U35 | S6-naming | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U36 | S6-naming | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U37 | S7-near | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U38 | S7-near | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U39 | S7-near | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8-U40 | S7-near | dropped (repeat) | repeats bank7 B7-U22 (優勝国) |
| B8-U41 | S7-near | dropped (repeat) | repeats bank7 B7-U23 (優勝ドライバー) |
| B8-U42 | S7-near | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U43 | S8-chain | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U44 | S8-chain | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U45 | S8-chain | dropped (repeat) | repeats bank6 B6-U35 (花園町駅の隣駅の駅番号) |
| B8-U46 | S8-chain | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U47 | S8-chain | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U48 | S8-chain | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U49 | S8-chain | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U50 | S8-chain | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U51 | S9-name | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U52 | S9-name | dropped (repeat) | same fact as bank2 R2-U002 (内浦町が廃止された時期) |
| B8-U53 | S9-name | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U54 | S9-name | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U55 | S9-name | fixed (kept) | tempting sentence re-cited: 千葉神社#1 (shares 神社) instead of 水戸東照宮#1 (shares only 宮) |
| B8-U56 | S9-name | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U57 | S9-name | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U58 | S9-name | fixed (kept) | note corrected: shared kind word is 駅 (the author wrote 橋) |
| B8-U59 | S9-name | surplus | plausible on reading; not selected: round 2 gave a better-spread item of the shape, or the relation/article is over-represented (all eight S8 items ask 隣駅の駅番号, six S9 items ask 駅番号, four ask 旧社格) |
| B8-U60 | S9-name | fixed (kept) | tempting sentence 海浦駅#1; note names the shared kind word 駅 |
| B8b-A01 | answerable | fixed (kept) | gold alternative (環状集落) |
| B8b-A02 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A03 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A04 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A05 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A06 | answerable | fixed (kept) | gold alternative |
| B8b-A07 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A08 | answerable | fixed (kept) | gold alternative |
| B8b-A09 | answerable | dropped | cap: PDF-XChange would carry three items (A09, U01, U20) |
| B8b-A10 | answerable | dropped | answer sentence is the fragment "中将" (no context); unfit as evidence |
| B8b-A11 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A12 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A13 | answerable | fixed (kept) | gold alternative without brackets |
| B8b-A14 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A15 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A16 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A17 | answerable | dropped | gold is a long paraphrase of a definition; no crisp answer |
| B8b-A18 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A19 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A20 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A21 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A22 | answerable | fixed (kept) | gold alternative |
| B8b-A23 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A24 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A25 | answerable | fixed (kept) | gold alternatives (each name) |
| B8b-A26 | answerable | fixed (kept) | gold alternative |
| B8b-A27 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A28 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A29 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A30 | answerable | fixed (kept) | gold alternative |
| B8b-A31 | answerable | surplus | gold is a long compound name; surplus |
| B8b-A32 | answerable | surplus | definition-type question; surplus |
| B8b-A33 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A34 | answerable | fixed (kept) | gold alternatives (each company) |
| B8b-A35 | answerable | valid (kept) | gold as the sentence phrase |
| B8b-A36 | answerable | dropped | cap: 城站駅 already carries U44 and U62 |
| B8b-A37 | answerable | fixed (kept) | gold alternative |
| B8b-A38 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A39 | answerable | surplus | omitted (coarse subject, nothing gained) |
| B8b-A40 | answerable | fixed (kept) | gold alternatives (each organisation) |
| B8b-A41 | answerable | valid (kept) | gold verbatim, new fact |
| B8b-A42 | answerable | fixed (kept) | gold alternative |
| B8b-U01 | S1-alias | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U02 | S1-alias | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U03 | S1-alias | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U04 | S1-alias | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U05 | S1-alias | surplus | surplus: 常山県 is used by U56 |
| B8b-U06 | S1-alias | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U07 | S2-place | surplus | same fact as U59 (旧村域の現在の市町村); U59 kept for S9 |
| B8b-U08 | S2-place | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U09 | S2-place | dropped | 大分市 has no 区: false premise |
| B8b-U10 | S2-place | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U11 | S2-place | dropped | 牙山市 has no 区: false premise |
| B8b-U12 | S2-place | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U13 | S3-person | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U14 | S3-person | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U15 | S3-person | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U16 | S3-person | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U17 | S3-person | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U18 | S3-person | surplus | surplus (trivially absent role) |
| B8b-U19 | S4-toshite | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U20 | S4-toshite | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U21 | S4-toshite | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U22 | S4-toshite | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U23 | S4-toshite | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U24 | S4-toshite | surplus | weak: asks for an item of the first dish, near-inferential |
| B8b-U25 | S5-paren | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U26 | S5-paren | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U27 | S5-paren | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U28 | S5-paren | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U29 | S5-paren | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U30 | S5-paren | surplus | cap: 勝岩駅 carries A33 and U08 |
| B8b-U31 | S6-naming | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U32 | S6-naming | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U33 | S6-naming | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U34 | S6-naming | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U35 | S6-naming | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U36 | S6-naming | surplus | cap: 屋久島ラーメン would carry three items |
| B8b-U37 | S7-near | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U38 | S7-near | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U39 | S7-near | dropped | the cited article states the early-mining period (明治末期から大正): the neighbouring fact is partly stated |
| B8b-U40 | S7-near | dropped | end year of a campaign "held in 2013" is inferable |
| B8b-U41 | S7-near | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U42 | S7-near | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U43 | S8-chain | surplus | cap: 方城駅 would carry three items (A30, U37, U43) |
| B8b-U44 | S8-chain | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U45 | S8-chain | fixed (kept) | re-worded by the auditor into the 「XのYのZ」 chain form (same fact asked) |
| B8b-U46 | S8-chain | surplus | same relation (本部所在地 of a 行政共同体) as U45; surplus |
| B8b-U47 | S8-chain | fixed (kept) | re-worded by the auditor into the 「XのYのZ」 chain form (same fact asked) |
| B8b-U48 | S8-chain | fixed (kept) | re-worded by the auditor into the 「XのYのZ」 chain form (same fact asked) |
| B8b-U49 | S8-chain | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U50 | S8-chain | surplus | cap: シュトルツェナウ would carry A12 and two more |
| B8b-U51 | S9-name | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U52 | S9-name | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U53 | S9-name | dropped | no kind word shared with the tempting article (和裁 vs カレッジ) |
| B8b-U54 | S9-name | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U55 | S9-name | surplus | relation cap (旧社格 already twice) |
| B8b-U56 | S9-name | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U57 | S9-name | dropped | no kind word shared with the tempting article |
| B8b-U58 | S9-name | dropped | no kind word shared with the tempting article |
| B8b-U59 | S9-name | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U60 | S9-name | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
| B8b-U61 | S9-name | surplus | 郡 asked for a 市 (S2 wording) and the tempting article shares only 駅; surplus |
| B8b-U62 | S9-name | valid (kept) | asked fact absent from the whole corpus (check8.py absence search); tempting; new relation for this article |
