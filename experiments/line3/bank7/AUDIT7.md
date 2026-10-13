# Audit of bank 7 (bank7.tsv, held-out bank for the output gate v4)

Auditor: Claude (Sonnet 5.5), 2026-10-13. Inputs: `bank2-author/PROMPT7.md` (the brief), `bank7-author/work7/out/bank7.tsv` (86 items, B7-A01..A36
answerable, B7-U01..U50 unanswerable, by codex **gpt-6-luna**, which saw only the corpus, `EXCLUDED_ARTICLES.txt` and PROMPT7), the author's
`check7.py` / `check7.txt` (PASS on the original) / `README7.md`, and the corpus. No Vera gate (v2, v3 or v4), reader, loom, model or other Vera system has
read this bank; `verantyx/loom/evidence.py` and the REACH / EVIDENCE design documents were **not** opened; `vera-impl/hidden` and `face-design/vera1.txt`
were not opened; no network except codex itself. The auditor read only the shape descriptions the task brief gave (the S8-chain definition).

**Author's reach.** The author's log (`bank2-author/fleet-out7/bank7.log`) shows it opened `S300_fulllead.jsonl` and `EXCLUDED_ARTICLES.txt` and wrote its own four
files; it ran in a fresh directory (`bank7-author/work7/`) that holds nothing else, so it could not see bank6 or any earlier bank.

**Corpus identity.** `work7/S300_fulllead.jsonl` is byte-identical to `experiments/line3/data/S300_fulllead.jsonl` (sha256 `d987fdee...`). Evidence
ids are `title#i`, 0-based over the lead's 「。」 split (bank6 convention).

**Deviation from bank6's production, and the defect it exposed.** To keep the bank off bank6's items the author was handed a list of articles to avoid
(110 titles of banks 2, 3, 4 and 6). The list was built by a regex that broke on titles containing a space (`IEEE 488`, `CUBE JUICE`,
`NGC 36`, `2017 FIFA U-17ワールドカップ`, `2025 UEFAスーパーカップ`), so those five articles were not excluded and the author used them. The mechanical check
against the earlier banks (below) caught every consequence: four answerable and three unanswerable items repeated earlier questions, and were dropped.

## Rules applied to every item

- **Answerable**: gold verbatim in the cited sentence, the shortest answering phrase (shorter verbatim alternatives added with `|`); the question names its
  subject; one clear answer; not answerable from the title alone; **not a repeat** of an earlier bank (`bank2/3/4/6`, `questions.tsv`): same article and
  same relation / gold = repeat; a repeat was re-asked on another fact of the same article or dropped.
- **Unanswerable**: the asked fact is absent from the WHOLE corpus (all 592 sentences; the search terms are recorded in `check7.py` `ABSENT` and must have
  0 hits, scoped to the whole corpus or, where the relation word occurs in other articles, to the subject article); the subject occurs in the corpus and
  in the cited sentence; tempting; no negation, no false premise, no single-qualifier trick, not inferable; not a repeat of an earlier bank; not a
  duplicate within bank7.
- **S8-chain**: the question's subject is a chain 「XのYのZ」 and the corpus holds the Z-type fact only for X, for Y or for another entity, never for
  the entity the chain points to. The author's eight are of four kinds: the property of the parent entity (U43 ネノ県の人口, U44 阿波市の人口, U45
  ブレシア県の人口, U46 ハノーファー広域連合の人口: the sentence holds the population of the child), the postal code of a place (U47, U48: the corpus gives
  postal codes of other places only), the birth year of the person an album is named after (U49) and the founding year of the label of a debut (U50).
  The neighbouring-station / parent-company shapes of the brief do not occur: the 300-article corpus has no article pair with that structure.

## Counts

| part / shape | authored | valid | fixed | dropped | kept |
|---|---|---|---|---|---|
| answerable | 36 | 21 | 11 | 4 | 32 |
| S1-alias | 6 | 6 | 0 | 0 | 6 |
| S2-place | 6 | 4 | 1 | 1 | 5 |
| S3-person | 6 | 4 | 2 | 0 | 6 |
| S4-toshite | 6 | 6 | 0 | 0 | 6 |
| S5-paren | 6 | 6 | 0 | 0 | 6 |
| S6-naming | 6 | 4 | 1 | 1 | 5 |
| S7-near | 6 | 5 | 0 | 1 | 5 |
| S8-chain | 8 | 8 | 0 | 0 | 8 |
| unanswerable total | 50 | 43 | 4 | 3 | 47 |
| **total** | 86 | 64 | 15 | 7 | 79 |

Counts are over the 86 original rows; kept = valid + fixed. The 15 fixed rows are 11 answerable (A03, A04, A06, A07, A10, A12, A13, A21, A25, A29: gold
alternatives; A27: re-ask) and 4 unanswerable (U10, U13, U14, U33: re-asked on a clean absent fact).

Targets of the brief: 30 answerable (kept 32), 40 unanswerable (kept 47), S1..S7 about 5 each (5-6), S8 at least 6 (8). The surplus is kept, not trimmed.

## Overlaps with earlier banks (mechanical, `check7.py`)

- No question text of bank7 equals a question of bank2 / bank3 / bank4 / bank6 / questions.tsv (after normalisation): **0**.
- No bank6 question and no bank6 (article, asked fact) pair is reused: the article-sharing items with bank6 are A18, U07, U17, U50 and each asks another fact
  (A18 the label of the major debut vs B6-U14 / B6-U23; U07 the 県 vs B6-U39 the score; U17 the unit name vs B6-U14 the mascot; U50 the label's founding year).
- No answerable item has the same article and gold as an earlier item (the checker errors on it).
- 15 kept items share an article with an earlier bank and ask another fact (kept deliberately, as bank6 did for A05 / A08):

  - B7-A02: article also in questions a36 (互先とは何ですか); asks the reading, not the definition
  - B7-A18: article also in bank2/3/4/6 (マスコット, 長尾伸一, dropz, デビュー月日, 考案者, 結成); asks the record label, which no earlier item asks
  - B7-A23: article also in questions a43 (二等分線とは何ですか; 線分 accepted); asks the narrower slot 何を二等分する (kept like bank6 A05 / A08)
  - B7-A26: article also in questions a47 (万太郎山はどこに; 三国山脈 accepted); asks the reading
  - B7-A27: re-ask (the original, 位置する山脈, was the same fact as a47): now asks the peak it belongs to
  - B7-U05: article also in questions a13 (国); asks the alias
  - B7-U07: article also in bank2 I2-046 (会場のスタジアム) and bank6 B6-U39 (試合結果); asks the 県
  - B7-U09: article also in questions a52 (どこに → 新潟県・佐渡島); asks the 市
  - B7-U13: article also in questions a49 (開発したのは誰); re-targeted to the logo
  - B7-U14: article also in bank2 I2-036 (発見の日); asks the cataloguer
  - B7-U17: article also in bank2/3/4/6 (see A18); bank6 B6-U14 asks who devised the mascot, this who named the unit
  - B7-U20: article also in questions a06 (経営しているのは誰); asks the production volume
  - B7-U34: article also in bank2 I2-048 / R2-I015, bank3 b3_tf14 / b3_sc07 / b3_uk08 / b3_uk15, bank4 ADV-007; asks the name of the double-winner record
  - B7-U39: same article as U34; asks the number of participating countries (bank3 b3_uk15 asks the crowd total, bank4 ADV-007 the final venue)
  - B7-U50: article also in bank2/3/4/6 (see A18); asks the founding year of the label, which no earlier item asks

## Main findings

1. **Absence holds**: for every kept unanswerable item no sentence of any article states the asked fact (47 recorded search terms, 0 hits; the subjects
   occur in exactly one article each, which makes the corpus-wide search short).
2. **Seven author items were repeats or flawed and were dropped** (A01, A15, A16, A17, U12, U31, U42; reasons in the table); **fifteen were fixed**: ten answerable golds got shorter verbatim alternatives (containment scoring), A27 and four unanswerable items were re-asked.
3. **False premises avoided**: U10 asked 「どの市」 of a 町 (大飯郡); U14 asked who gave a 固有名 to an object that has none; U33 presupposed a named internal
   algorithm. All three were re-asked on a clean absent fact.
4. **Single-qualifier trick**: U13 differed from the sentence's 開発 by the one word 設計 (cf. bank6 B6-U13); re-targeted to the logo designer.
5. **Outside knowledge**: 10 kept unanswerables are answerable from memory ('yes') and 14 more partly (column "outside"); this matters for `no_tools` /
   `free_text` controls, not for a gate.
6. **S8**: U43..U46 are the parent-entity-property kind; the postal-code pair (U47, U48) is the weakest S8 (the chain 「所在地の郵便番号」 is thin). Report
   S8 by sub-kind if the result hinges on it.
7. **Article reuse**: one article carries four items (私は息子を兵士に育てなかった: A35, A36, U15, U36), five carry three (プリンツ・アーダルベルト級装甲巡洋艦, CUBE JUICE, 三水区, 2011年世界男子ハンドボール選手権, アルガルヴェ・カップ2017).

## Per-item decisions

"outside" = could a strong LLM answer from memory (auditor's estimate; relevant to no_tools / free_text only).

| id | shape | decision | reason | outside |
|---|---|---|---|---|
| B7-A01 | - | dropped | repeats questions.tsv a36 (互先とは何ですか → 囲碁/手合割), same fact | - |
| B7-A02 | - | valid | article also in questions a36 (互先とは何ですか); asks the reading, not the definition | - |
| B7-A03 | - | fixed | gold: shorter verbatim alternative ウィレム added | - |
| B7-A04 | - | fixed | gold: trailing まで removed (the question asks the span, containment scoring) | - |
| B7-A05 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A06 | - | fixed | gold: the reading of the alias, in the same parenthesis, added | - |
| B7-A07 | - | fixed | gold: shorter verbatim alternative added | - |
| B7-A08 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A09 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A10 | - | fixed | gold: the question asks the country; shorter verbatim alternatives added | - |
| B7-A11 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A12 | - | fixed | gold: shorter verbatim alternative added | - |
| B7-A13 | - | fixed | gold: shorter verbatim alternative added | - |
| B7-A14 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A15 | - | dropped | verbatim repeat of bank2 I2-017 (IEEE 488の通称 → GPIB) | - |
| B7-A16 | - | dropped | verbatim repeat of bank6 B6-A14 (IEEE 488: 1975年に提案した企業 → ヒューレット・パッカード) | - |
| B7-A17 | - | dropped | verbatim repeat of bank2 I2-019 / bank3 b3_uw17 (CUBE JUICEのマスコット → BAN BAN) | - |
| B7-A18 | - | valid | article also in bank2/3/4/6 (マスコット, 長尾伸一, dropz, デビュー月日, BAN BANの考案者, 結成); asks the label, which no earlier item asks (bank4 ADV-001 asks the debut month/day, answerable by none) | - |
| B7-A19 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A20 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A21 | - | fixed | gold: the question asks the number; shorter verbatim alternatives added | - |
| B7-A22 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A23 | - | valid | article also in questions a43 (二等分線とは何ですか; 線分 accepted); asks the narrower slot 何を二等分する, kept like bank6 A05/A08 | - |
| B7-A24 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A25 | - | fixed | gold: shorter verbatim alternatives added | - |
| B7-A26 | - | valid | article also in questions a47 (万太郎山はどこに; 三国山脈 accepted); asks the reading | - |
| B7-A27 | - | fixed | re-ask (auditor-written): the original (位置する山脈 → 三国山脈) is the same fact as questions.tsv a47 (万太郎山はどこにありますか, 三国山脈 accepted) | - |
| B7-A28 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A29 | - | fixed | gold: shorter verbatim alternative added | - |
| B7-A30 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A31 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A32 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A33 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A34 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A35 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-A36 | - | valid | verbatim gold in the cited sentence, not answerable from the title | - |
| B7-U01 | S1 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U02 | S1 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U03 | S1 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | yes |
| B7-U04 | S1 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U05 | S1 | valid | article also in questions a13 (国); asks the alias | - |
| B7-U06 | S1 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U07 | S2 | valid | article also in bank2 I2-046 (会場のスタジアム) and bank6 B6-U39 (試合結果); asks the 県, another fact | yes |
| B7-U08 | S2 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | yes |
| B7-U09 | S2 | valid | article also in questions a52 (どこにありますか → 新潟県・佐渡島); asks the 市 | yes |
| B7-U10 | S2 | fixed | the original asked 「どの市」, but 大飯郡 holds no 市 (a false premise, cf. bank6 U07/U10): re-asked as the town of the county | yes |
| B7-U11 | S2 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | partly |
| B7-U12 | S2 | dropped | near-repeat of bank4 ADV-007 (2017 FIFA U-17 決勝会場のスタジアム): the city of the same final | yes |
| B7-U13 | S3 | fixed | the original (設計した人物) differs from 開発 by one word, a single-qualifier trick (cf. bank6 B6-U13): re-targeted to the logo | - |
| B7-U14 | S3 | fixed | the original asked who gave NGC 36 a 固有名, which it has none (false premise): re-asked as the cataloguer | partly |
| B7-U15 | S3 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U16 | S3 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U17 | S3 | valid | article also in bank2/3/4/6 (see A18); bank6 B6-U14 asks who devised the mascot, this item who named the unit: same shape, other fact | - |
| B7-U18 | S3 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U19 | S4 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | partly |
| B7-U20 | S4 | valid | article also in questions a06 (経営しているのは誰); asks production volume | - |
| B7-U21 | S4 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | partly |
| B7-U22 | S4 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | yes |
| B7-U23 | S4 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | yes |
| B7-U24 | S4 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U25 | S5 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U26 | S5 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | partly |
| B7-U27 | S5 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U28 | S5 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | partly |
| B7-U29 | S5 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U30 | S5 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U31 | S6 | dropped | ambiguous: 「ネパール文字表記は、どのように呼ばれていますか」 reads two ways and the Latin form in the sentence is a defensible answer | - |
| B7-U32 | S6 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | yes |
| B7-U33 | S6 | fixed | the original presupposed a ranking-adjustment algorithm named internally (a loaded premise): re-asked on the internal name only | - |
| B7-U34 | S6 | valid | article also in bank2 I2-048 / R2-I015, bank3 b3_tf14 / b3_sc07 / b3_uk08 / b3_uk15, bank4 ADV-007; asks the name of the double-winner record | - |
| B7-U35 | S6 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | partly |
| B7-U36 | S6 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U37 | S7 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | partly |
| B7-U38 | S7 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U39 | S7 | valid | same article; bank3 b3_uk15 asks the crowd total, bank4 ADV-007 the final venue; this asks the number of participating countries | partly |
| B7-U40 | S7 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U41 | S7 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | partly |
| B7-U42 | S7 | dropped | repeat in kind of bank6 B6-U39 (2025 UEFAスーパーカップ: 試合結果 asked, 通算ゴール数 here): same sentence, same missing result | yes |
| B7-U43 | S8 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | partly |
| B7-U44 | S8 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | partly |
| B7-U45 | S8 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | yes |
| B7-U46 | S8 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | partly |
| B7-U47 | S8 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U48 | S8 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | - |
| B7-U49 | S8 | valid | asked fact absent from all 592 sentences; subject in the corpus; tempting wrong answer in the notes | yes |
| B7-U50 | S8 | valid | article also in bank2/3/4/6 (see A18); asks the founding year of the label, which no earlier item asks | partly |

## Fixes (old -> new)

- **B7-A03**: gold: shorter verbatim alternative ウィレム added
    - question: `「オレンジ公ウィリアム」という呼び方のもとになったオラニエ公の名は何ですか？` -> `「オレンジ公ウィリアム」という呼び方のもとになったオラニエ公の名は何ですか？`
    - gold: `オラニエ公ウィレム` -> `オラニエ公ウィレム|ウィレム`
    - evidence: `オレンジ公ウィリアム#0` -> `オレンジ公ウィリアム#0`
- **B7-A04**: gold: trailing まで removed (the question asks the span, containment scoring)
    - question: `よみうりオープンゴルフトーナメントは何年から何年まで開催されていましたか？` -> `よみうりオープンゴルフトーナメントは何年から何年まで開催されていましたか？`
    - gold: `1979年から2006年まで` -> `1979年から2006年`
    - evidence: `よみうりオープンゴルフトーナメント#0` -> `よみうりオープンゴルフトーナメント#0`
- **B7-A06**: gold: the reading of the alias, in the same parenthesis, added
    - question: `熊送りには、どのような別名がありますか？` -> `熊送りには、どのような別名がありますか？`
    - gold: `熊祭り` -> `熊祭り|くままつり`
    - evidence: `熊送り#0` -> `熊送り#0`
- **B7-A07**: gold: shorter verbatim alternative added
    - question: `熊送りを執り行うのは、どのような人々ですか？` -> `熊送りを執り行うのは、どのような人々ですか？`
    - gold: `ユーラシア・タイガ・北アメリカ北部の内陸狩猟民族` -> `ユーラシア・タイガ・北アメリカ北部の内陸狩猟民族|内陸狩猟民族`
    - evidence: `熊送り#0` -> `熊送り#0`
- **B7-A10**: gold: the question asks the country; shorter verbatim alternatives added
    - question: `プリンツ・アーダルベルト級装甲巡洋艦は、どの国の海軍に属していましたか？` -> `プリンツ・アーダルベルト級装甲巡洋艦は、どの国の海軍に属していましたか？`
    - gold: `ドイツ帝国海軍` -> `ドイツ帝国海軍|ドイツ帝国|ドイツ`
    - evidence: `プリンツ・アーダルベルト級装甲巡洋艦#0` -> `プリンツ・アーダルベルト級装甲巡洋艦#0`
- **B7-A12**: gold: shorter verbatim alternative added
    - question: `日露協約は何の後に締結された協約ですか？` -> `日露協約は何の後に締結された協約ですか？`
    - gold: `日露戦争後` -> `日露戦争後|日露戦争`
    - evidence: `日露協約#0` -> `日露協約#0`
- **B7-A13**: gold: shorter verbatim alternative added
    - question: `リサ長尾はどのような歌手ですか？` -> `リサ長尾はどのような歌手ですか？`
    - gold: `日本の女性歌手` -> `日本の女性歌手|女性歌手`
    - evidence: `リサ長尾#0` -> `リサ長尾#0`
- **B7-A21**: gold: the question asks the number; shorter verbatim alternatives added
    - question: `梓橋が結んでいる長野県道は何号線ですか？` -> `梓橋が結んでいる長野県道は何号線ですか？`
    - gold: `長野県道48号松本環状高家線` -> `長野県道48号松本環状高家線|48号松本環状高家線|48号`
    - evidence: `梓橋#0` -> `梓橋#0`
- **B7-A25**: gold: shorter verbatim alternatives added
    - question: `余呉バスストップは転用後、どの会社の管理用施設として使われていますか？` -> `余呉バスストップは転用後、どの会社の管理用施設として使われていますか？`
    - gold: `中日本高速道路（NEXCO中日本）` -> `中日本高速道路（NEXCO中日本）|中日本高速道路|NEXCO中日本`
    - evidence: `余呉バスストップ#1` -> `余呉バスストップ#1`
- **B7-A29**: gold: shorter verbatim alternative added
    - question: `アルティメット・イヤーズはメーカーとしては、どのような機器を設計・製造していますか？` -> `アルティメット・イヤーズはメーカーとしては、どのような機器を設計・製造していますか？`
    - gold: `カスタムインイヤーモニター (IEMs)などの音響機器` -> `カスタムインイヤーモニター (IEMs)などの音響機器|カスタムインイヤーモニター`
    - evidence: `アルティメット・イヤーズ#0` -> `アルティメット・イヤーズ#0`
- **B7-A27**: re-ask (auditor-written): the original (位置する山脈 → 三国山脈) is the same fact as questions.tsv a47 (万太郎山はどこにありますか, 三国山脈 accepted)
    - question: `万太郎山が位置する山脈は何ですか？` -> `万太郎山は何の支峰に属していますか？`
    - gold: `三国山脈` -> `谷川岳`
    - evidence: `万太郎山#0` -> `万太郎山#1`
- **B7-U10**: the original asked 「どの市」, but 大飯郡 holds no 市 (a false premise, cf. bank6 U07/U10): re-asked as the town of the county
    - question: `大津呂ダムは福井県のどの市に建設されたダムですか？` -> `大津呂ダムが建設された大飯郡の町はどこですか？`
    - gold: `` -> ``
    - evidence: `大津呂ダム#0` -> `大津呂ダム#0`
- **B7-U13**: the original (設計した人物) differs from 開発 by one word, a single-qualifier trick (cf. bank6 B6-U13): re-targeted to the logo
    - question: `Magiskを設計した人物は誰ですか？` -> `Magiskのロゴを描いた人物は誰ですか？`
    - gold: `` -> ``
    - evidence: `Magisk#0` -> `Magisk#0`
- **B7-U14**: the original asked who gave NGC 36 a 固有名, which it has none (false premise): re-asked as the cataloguer
    - question: `NGC 36に固有名を付けた人物は誰ですか？` -> `NGC 36をNGCカタログに掲載した人物は誰ですか？`
    - gold: `` -> ``
    - evidence: `NGC 36#1` -> `NGC 36#1`
- **B7-U33**: the original presupposed a ranking-adjustment algorithm named internally (a loaded premise): re-asked on the internal name only
    - question: `グーグル八分の原因となるGoogleの検索順位調整アルゴリズムは、社内でどの名称と呼ばれていますか？` -> `グーグル八分の状態にすることを、Google社内では何と称していますか？`
    - gold: `` -> ``
    - evidence: `グーグル八分#0;グーグル八分#2` -> `グーグル八分#0;グーグル八分#2`

## Dropped rows (author original, for the record)
- B7-A01: 囲碁の互先とは、どのような手合割ですか？ (gold `手合割の一つ`, 互先#0)
- B7-A15: IEEE 488は、通称何と呼ばれていますか？ (gold `GPIB`, IEEE 488#1)
- B7-A16: IEEE 488の起源となったHP-IBを提案した会社はどこですか？ (gold `ヒューレット・パッカード`, IEEE 488#0)
- B7-A17: CUBE JUICEのマスコットになっている熊の名前は何ですか？ (gold `BAN BAN`, CUBE JUICE#1)
- B7-U12: 2017 FIFA U-17ワールドカップの決勝が行われた市はどこですか？ (gold ``, 2017 FIFA U-17ワールドカップ#0;2017 FIFA U-17ワールドカップ#1)
- B7-U31: ムルキー・アインの正式なネパール文字表記は、どのように呼ばれていますか？ (gold ``, ムルキー・アイン#0;ムルキー・アイン#1)
- B7-U42: 2025 UEFAスーパーカップの通算ゴール数はいくつでしたか？ (gold ``, 2025 UEFAスーパーカップ#0;2025 UEFAスーパーカップ#1)
