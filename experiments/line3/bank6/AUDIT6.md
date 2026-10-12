# Audit of bank 6 (bank6.tsv, held-out bank for the loom evidence gate v3)

Auditor: Claude (Opus 5.5), 2026-10-13. Inputs: `bank2-author/PROMPT6.md` (the brief), `bank2-author/out/bank6.tsv` (70 items,
B6-A01..A30 answerable, B6-U01..U40 unanswerable, by codex **gpt-6-luna**, which saw only the corpus and PROMPT6, not the gate's rule
list), the author's `check6.py` / `check6.txt` (PASS, re-run unchanged on the original: PASS) / `README6.md`, and the corpus.
No Vera gate (v2 or v3), reader, loom, model or other Vera system has read this bank; `verantyx/loom/evidence.py` and the rule
section of `docs/LINE3_LOOM_REACH_DESIGN.md` were **not** opened; `vera-impl/hidden` was not opened; no network. Every judgment
below was fixed before the auditor looked up the v3 freeze state; that lookup showed the one-line subject of commit 65b26d57
(it names the v3 categories, which match PROMPT6's seven shapes) and nothing more of the rules.

**Author's reach.** The author's log (`bank2-author/fleet-out6/bank6.log`) shows it read `S300_fulllead.jsonl` and wrote its four
files; the earlier banks appear in it only as names in an `ls -l out` listing, never opened. The repeats found below are
therefore coincidences of article choice, not copying.

**Corpus identity.** The author's `S300_fulllead.jsonl` (sha256 `d987fdee…`) is byte-identical to `experiments/line3/data/S300_fulllead.jsonl`.
`bank2/data/fulllead_sents.jsonl` (sha256 `45efdaed…`) is not byte-identical: it is its sentence split. Verified (and re-verified by
`check6.py`): its 592 sentences concatenated per title equal the 300 leads exactly, and every `source` is `title#i` with i 0-based over
`text.split("。")`, the author's evidence convention. No evidence id needed a format change.

**Shapes.** The author's TSV has no shape column; `README6.md` gives the order (6 alias, 6 place, 6 person, 6 としては, 5 parenthetical,
5 naming-verb, 6 near-fact), i.e. U01-06 S1-alias, U07-12 S2-place, U13-18 S3-person, U19-24 S4-toshite, U25-29 S5-paren, U30-34
S6-naming, U35-40 S7-near. The audited file adds a `shape` column (`-` for answerable) and an `audit` column (valid / fixed).

Rules applied to every item (the request):
- **Answerable**: gold verbatim in a cited sentence; the shortest answering phrase (shorter verbatim alternatives added with `|`,
  because `grade.py` scores by gold-in-answer containment); natural question naming its subject; one clear answer; **not answerable
  from the title alone**. Added: **not a repeat** of a question a Vera system has read (`bank2.tsv`, `bank3.tsv`, `bank4.tsv`,
  `questions.tsv`). A held-out bank cannot hold items the gate was developed on. A repeat = same article, same relation, same
  gold. Repeats were re-asked on another fact of the same article where one existed (precedent: bank4 ADV-005/025), else dropped.
- **Unanswerable**: the asked fact is absent from the WHOLE corpus (all 592 sentences searched for the relation, paraphrases
  and units; the terms are recorded in `check6.py` `ABSENT_TERMS` and must have 0 hits); the subject occurs in the corpus and in a
  cited sentence; tempting; no negation trick; **no single-qualifier trick** (a word in the question that alone turns a stated
  fact into an unstated one, cf. bank4 ADV-003/024/032); not inferable from the corpus; not a repeat; not a duplicate of another
  bank6 item.
- Counts: ≥ 25 answerable, ≥ 32 unanswerable, every shape ≥ 4.

## Counts

| part / shape | authored | valid | fixed | dropped | moved | kept |
|---|---|---|---|---|---|---|
| answerable | 30 | 11 | 15 | 4 | 0 | 26 |
| S1-alias (別名/通称/読み) | 6 | 4 | 1 | 1 | 0 | 5 |
| S2-place (どの区/市/県) | 6 | 4 | 1 | 1 | 0 | 5 |
| S3-person (〜した人物) | 6 | 1 | 4 | 1 | 0 | 5 |
| S4-toshite (〜としては) | 6 | 5 | 1 | 0 | 0 | 6 |
| S5-paren (括弧・読みの欄) | 5 | 0 | 4 | 1 | 0 | 4 |
| S6-naming (呼ばれる/称される) | 5 | 5 | 0 | 0 | 0 | 5 |
| S7-near (隣の同種の事実) | 6 | 3 | 1 | 2 | 0 | 4 |
| unanswerable total | 40 | 22 | 12 | 6 | 0 | 34 |
| **total** | 70 | 33 | 27 | 10 | 0 | 60 |

Of the 15 answerable fixes, 10 are **re-asks** (new question + gold on another fact of the same article: A01, A09, A12, A14, A19, A22,
A24, A25, A27, A28) and 5 are minor (gold alternative or wording: A03, A05, A15, A16, A18). Of the 12 unanswerable fixes, 2 are re-targets
(U13, U29: qualifier tricks re-asked as a clean absent fact of the same shape), the rest wording.

## Main findings

1. **Absence holds; nothing moved.** For every one of the 40 asked facts no sentence of any article answers it. No unanswerable
   item had to move to answerable.
2. **Ten answerable items repeated questions that Vera systems have read** (the author never saw those banks). Verbatim or same
   relation + same gold: A01 = bank2 I2-001 (ハッシュ表), A09 ≈ I2-008 (カール・マルクス), A14 ≈ I2-017 (GPIB), A19 = I2-010 verbatim
   (3位), A22 ≈ questions a17 (東日本旅客鉄道), A23 ≈ I2-012 (深川八幡宮), A24 ≈ R2-I002 / b3_tf07 (能登町), A25 ≈ questions a16
   (大邱広域市), A27 ≈ b3_uw13 (丘絵…), A04 ≈ questions a36 (互先 → 手合割). Eight were re-asked on another fact of the same article,
   keeping the author's shape mix (読み, 〜を提案した企業, どの郡, どの国, 呼ばれる). A04 and A23 were dropped: their articles' only
   other fact is a reading, and the bank already has six. Two weaker overlaps are **kept** and flagged: A05 (何の平等 → ジェンダー;
   questions a10 「フェミニズムとは何ですか」 lists ジェンダー among its keywords) and A08 (大阪市の何区 → 西成区; questions a30
   「どこにありますか」 lists 西成区). In both the question asks a narrower slot than the earlier one.
3. **Four answerable items were answerable from the title** (definition questions whose gold restates the title): A02 デニム →
   デニム生地 (title + 生地; the sentence also gives *denim*, so there is no single answer), A10 海外ドラマ → 日本以外で制作…, A12
   温熱療法 → 温熱による医療行為…, A28 外断熱 → 断熱層を建物の外側に… . A02 and A10 were dropped. A12 and A28 (also questions
   a24 / a27 repeats) were re-asked on their second sentence (ハイパーサーミア; 熱容量の大きい建物).
4. **Two qualifier tricks, re-targeted.** U13 「Bardを開発した**人物**」: the developer is stated (Google, LaMDA#0/#4), and only 「人物」
   makes it absent (cf. ADV-003). Re-asked as 「Bardの開発を**率いた**人物」, a different relation with the same trap (レモイン). U29
   「カロリーヌの**括弧内に示された**英語名」: the English counterpart キャロライン is in #1, and only the location phrase made it absent.
   Re-asked as the original spelling (綴り), which the empty （） normally holds.
5. **Six unanswerable drops.** U17 (唯物史観を文章にまとめた人物): one-verb qualifier against the stated 唱えた, and the trap
   カール・マルクス is the real answer (cf. ADV-032). U12 (ハバナの大使館はどの州): ハバナ州 (La Habana) is built from the evidence's
   own word and is the real answer. U25 (連結グラフの英語表記): inferable from the corpus, since 連結成分 (connected component) and
   非連結グラフ (disconnected graph) compose to *connected graph* (cf. ADV-002). U37 (金曜日の放送時間): the corpus refutes the
   premise (毎週月曜日から木曜日), so the right reply 「金曜は放送なし」 is a corpus answer, not an abstention. U38 (男子競技の選手数):
   repeats bank4 ADV-028, same sentence, relation and trap. U04 (S-37の別名): duplicates U32 (S-37の別の愛称) on a one-sentence stub.
6. **Meta phrasing removed** (as in bank4): U01 「記事にどう示されていますか」, U25-U28 「読みの後、括弧内にある/記されている」. Questions
   now ask the fact plainly (「何と読みますか」, 「英語で何といいますか」, 「何の略称ですか」). Questions with no subject were completed:
   U11, U14, U15, U18, U20, U40, and A09 (「この歴史観」).
7. **Premise-false items (kept, by design of S2).** U07 / U10 ask which 市 a station in a 郡・町 is in, and U09 asks which 区 of 水戸市
   (no wards). The corpus names a different kind of place, which is what the brief asks for. Grading: any reply that names no
   市 / 区 (for example 「市ではなく芦北町」) counts as an abstention. U07 and U10 share one pattern on two articles, like bank4
   ADV-018/019.
8. **Sequential-number extrapolation (kept, flagged).** U35 (花園町駅 Y17) and U36 (海浦駅 OR08) ask for the neighbour's station
   number. Y16/Y18 and OR07/OR09 follow from the usual numbering, and are in fact correct, but the corpus states neither. The correct
   behaviour is still to abstain; a system that extrapolates shows exactly the failure the gate is meant to stop.
9. **Outside knowledge.** Corpus-unanswerable is not world-unanswerable. 11 of the 34 kept unanswerables are answerable from memory
   (U01 はっしゅひょう, U08 松本市・高山市, U11 Oxfordshire, U20 1974年, U26, U28 feminism, U29 Caroline, U32 ベルクト, U35, U36, U39), and 12
   more partly. Three c) values are the real-world answer (U08 松本市, one of two; U20 1974年; U32 ベルクト). They are kept as traps
   from memory. This matters only for `no_tools` / `free_text` controls.
10. **Overlap with the gate's development banks at the article level is unavoidable.** 29 of the 43 articles are also cited by bank2,
    bank3, bank4 or questions.tsv. After the fixes no question repeats one of them (`check6.py` checks surface and gold overlap).

## Re-check

`check6.py` → `check6.txt`: **PASS, 60 rows, 0 errors** (40 INFO: c) values and their corpus occurrence, golds that also occur in other
articles, the two known overlaps). It checks: corpus split identity; header; ids; ≥ 25 / ≥ 32 / every shape ≥ 4; questions end in ？,
have no negation and contain the subject; evidence resolves (1-2 ids of one article); answerable golds verbatim in a cited sentence and
not in the title or question; unanswerable gold empty, notes 文/欠落/誤答例; every `ABSENT_TERMS` search has 0 hits in all 592
sentences; no question equals one in bank2/bank3/bank4/questions.tsv; no answerable gold overlaps an earlier gold on the same article
(except the two kept and listed). The author's own `check6.py`/`check6.txt` are not copied (they validate the original 70 rows; shas in
MANIFEST.json).

## Per-item decisions

"outside" = could a strong LLM answer from memory (auditor's estimate; relevant to no_tools / free_text only).

| id | shape | decision | reason | outside |
|---|---|---|---|---|
| B6-A01 | - | fixed (re-ask) | repeat of bank2 I2-001 (ハッシュテーブルの別名 → ハッシュ表): re-asked as the term #0 defines in its parenthesis (エントリ) | - |
| B6-A02 | - | dropped | answerable from the title (デニム生地 = title + 生地); #0 also gives *denim*, so 「別の名称」 has two answers | - |
| B6-A03 | - | fixed | gold: shorter verbatim alternative 準則 added | - |
| B6-A04 | - | dropped | same fact as questions a36 (互先とは何ですか → 囲碁/手合割); the one-sentence article has only its reading left | - |
| B6-A05 | - | fixed | gold: the question already says 何の平等, so the shortest answer ジェンダー is added; flagged overlap with questions a10 (a definition question listing ジェンダー); narrower slot, kept | - |
| B6-A06 | - | valid | 南魚沼市, not in the title; one clear answer | - |
| B6-A07 | - | valid | 広島県 (also in 岡崎建設#0, unrelated) | - |
| B6-A08 | - | valid | 西成区; flagged overlap with questions a30 (「どこ」 listing 西成区); narrower slot, kept | - |
| B6-A09 | - | fixed (re-ask) | repeat of bank2 I2-008 (唯物史観を唱えた人物 → カール・マルクス) and 「この歴史観」 had no antecedent: re-asked as the reading of 史的唯物論 (#0) | - |
| B6-A10 | - | dropped | answerable from the title (海外ドラマ → 日本以外で制作・製作された…ドラマ); 25-character definition gold | - |
| B6-A11 | - | valid | PG; 略称 stated in the parenthesis | - |
| B6-A12 | - | fixed (re-ask) | the gold restated the title (温熱による医療行為…) and repeats questions a24: re-asked on #1 (ハイパーサーミア) | - |
| B6-A13 | - | valid | 1991年11月18日 | - |
| B6-A14 | - | fixed (re-ask) | repeat of bank2 I2-017 (IEEE 488の通称 → GPIB): re-asked as 〜を提案した企業 (ヒューレット・パッカード / Hewlett-Packard, #0) | - |
| B6-A15 | - | fixed | 「短絡する」 copied the sentence's technical verb: reworded; alternative 長野・岐阜 added | - |
| B6-A16 | - | fixed | gold: the romanised form dāna, given in the same parenthesis, added | - |
| B6-A17 | - | valid | 糸魚川市 | - |
| B6-A18 | - | fixed | gold: shorter alternative トリオ編成 added | - |
| B6-A19 | - | fixed (re-ask) | verbatim repeat of bank2 I2-010 (ヨーロッパで何位 → 3位): re-asked as its twin in the same sentence (世界では → 9位) | - |
| B6-A20 | - | valid | 山崎弘士と森谷威夫 | - |
| B6-A21 | - | valid | てらむかい (reading in parentheses) | - |
| B6-A22 | - | fixed (re-ask) | repeat of questions a17 (ATACSを開発したのは誰 → 東日本旅客鉄道): re-asked as the reading (アタックス) | - |
| B6-A23 | - | dropped | repeat of bank2 I2-012 (富岡八幡宮の通称 → 深川八幡宮); only readings / the ward (questions a31) left | - |
| B6-A24 | - | fixed (re-ask) | repeat of bank2 R2-I002 / bank3 b3_tf07 (→ 能登町): re-asked as the former 郡 (珠洲郡, #1; trap 鳳珠郡 in #2) | - |
| B6-A25 | - | fixed (re-ask) | repeat of questions a16 and answerable from the title (大邱FC → 大邱): re-asked as the league (Kリーグ2, #1) | - |
| B6-A26 | - | valid | 北辰妙見尊星王の本宮 (bank3 b3_pa04 asked the 別称 itself, not its meaning) | - |
| B6-A27 | - | fixed (re-ask) | repeat of bank3 b3_uw13 (日本語訳 → 丘絵/丘陵像/ヒルフィガー): re-asked as 〜が描かれた国 (イギリス, #0) | - |
| B6-A28 | - | fixed (re-ask) | gold restated the title (断熱層を建物の外側に…) and repeats questions a27: re-asked on #1 (熱容量の大きい建物 / コンクリート構造物) | - |
| B6-A29 | - | valid | 1945年5月24日 | - |
| B6-A30 | - | valid | 1965年 (としては; 1973 is the trap). bank3 b3_sc05 used 「1965年に現在の名で設立」 as a false option, a different statement | - |
| B6-U01 | S1-alias | fixed | meta phrasing (「記事にどう示されていますか」) → 「何と読みますか」; no reading after ハッシュ表 anywhere | yes (はっしゅひょう) |
| B6-U02 | S1-alias | valid | reading and place only; 通称 occurs only for 富岡八幡宮, IEEE 488, パリ経済学校 | no |
| B6-U03 | S1-alias | valid | no English name; 「ドラマ」 occurs in this sentence only | partial |
| B6-U04 | S1-alias | dropped | duplicate of U32 (S-37 別名 / 別の愛称: same article, same relation, one-sentence stub) | - |
| B6-U05 | S1-alias | valid | definition only, empty （）; no 別名/呼ばれ for it anywhere | partial |
| B6-U06 | S1-alias | valid | only the English Ferguson; no ゲール/Gaelic form anywhere | partial |
| B6-U07 | S2-place | valid | 葦北郡芦北町 (a town): premise-false by design; any reply naming no 市 = abstention | no (none) |
| B6-U08 | S2-place | valid | only the prefectural border; 松本市 occurs in 梓橋#0 (cross-article trap) | yes (松本市・高山市) |
| B6-U09 | S2-place | valid | 茨城県水戸市 only; 中央区 occurs for 千葉市 (千葉神社#0), 天満橋#3 | no (水戸市 has no wards) |
| B6-U10 | S2-place | valid | 遠賀郡岡垣町: same premise-false pattern as U07 on another article | no (none) |
| B6-U11 | S2-place | fixed | subject added (ヒルフィギュア); no county anywhere | yes (Oxfordshire) |
| B6-U12 | S2-place | dropped | 「ハバナ州」 is formed from the evidence's own word and is the real answer (La Habana province) | - |
| B6-U13 | S3-person | fixed | qualifier trick: 「Bardを開発した人物」 — the developer (Google) is stated; only 人物 excluded it → 「開発を率いた人物」 | partial |
| B6-U14 | S3-person | fixed | subject added (CUBE JUICE); no 考案/designer anywhere | no |
| B6-U15 | S3-person | fixed | subject added (「番組」 → YAMAMORIラジオ!!) | no |
| B6-U16 | S3-person | valid | 藤井健太郎 hosted the debut event; no producer of the band anywhere (TEAM MAKEHEN#0 has another producer) | no |
| B6-U17 | S3-person | dropped | one-verb qualifier (文章にまとめた vs stated 唱えた) and the trap カール・マルクス is the real answer | - |
| B6-U18 | S3-person | fixed | subject added (ケーザイ・シモン); no 翻訳/訳者 anywhere | no |
| B6-U19 | S4-toshite | valid | 思想として始まった, no year anywhere (b3_uk04 asked the country, a different slot) | partial |
| B6-U20 | S4-toshite | fixed | subject added (ブリティッシュ・エアウェイズ); no 設立 for BA | yes (1974) |
| B6-U21 | S4-toshite | valid | no 開業 anywhere in the corpus | partial (1958 / 2018) |
| B6-U22 | S4-toshite | valid | stub 「航空機の機体名称」 only | partial |
| B6-U23 | S4-toshite | valid | 2002年 is the debut, not the formation; no 結成 for CUBE JUICE | no |
| B6-U24 | S4-toshite | valid | uses only; no country of production anywhere | partial |
| B6-U25 | S5-paren | dropped | inferable: 連結成分 (connected component) + 非連結グラフ (disconnected graph) give *connected graph* | - |
| B6-U26 | S5-paren | fixed | meta phrasing and 「正式な英語名」 (ATACS itself is the English acronym) → 「何の略称ですか」 | yes |
| B6-U27 | S5-paren | fixed | meta phrasing → 「英語で何といいますか」 | partial |
| B6-U28 | S5-paren | fixed | meta phrasing and a false premise (「読みの後」: the （） is empty) → 「英語でどう綴りますか」 | yes (trivial) |
| B6-U29 | S5-paren | fixed | qualifier trick: the English counterpart キャロライン is in #1, only 「括弧内に示された」 excluded it → 原綴り; #1 added | yes (Caroline) |
| B6-U30 | S6-naming | valid | reading and province only; 志摩国 is the trap | no |
| B6-U31 | S6-naming | valid | adoption date only (bank4 ADV-015 asked its colours) | partial |
| B6-U32 | S6-naming | valid | stub; no 愛称 anywhere for it | yes (ベルクト) |
| B6-U33 | S6-naming | valid | place only; 「呼ばれている」 in 水戸東照宮#2 is a cross-article pattern | no |
| B6-U34 | S6-naming | valid | year and host only; no 通称/クラブワールドカップ | partial |
| B6-U35 | S7-near | valid | own number Y17 only; neighbours follow by extrapolation, not from the corpus (flagged) | yes (Y16/Y18) |
| B6-U36 | S7-near | valid | own number OR08 only; same pattern as U35 on another line (flagged) | yes (OR07/OR09) |
| B6-U37 | S7-near | dropped | premise refuted by the corpus (毎週月曜日から木曜日): 「金曜は放送なし」 is a corpus answer, not an abstention | - |
| B6-U38 | S7-near | dropped | repeats bank4 ADV-028 (same sentence, relation and trap) | - |
| B6-U39 | S7-near | valid | date and venue only; no score anywhere | yes (2-2, PK) |
| B6-U40 | S7-near | fixed | subject completed (which Games); no athlete count anywhere | partial |

## Fixes (old → new)

- **B6-A01**
    - question: `ハッシュテーブルは別名で何ともいいますか？` → `ハッシュテーブルでは、格納するキーと値の組を何と呼びますか？`
    - gold: `ハッシュ表` → `エントリ`
    - evidence: `ハッシュテーブル#1` → `ハッシュテーブル#0`
- **B6-A03**
    - gold: `人の従うべき準則` → `人の従うべき準則|準則`
- **B6-A05**
    - gold: `ジェンダーの平等` → `ジェンダーの平等|ジェンダー`
- **B6-A09**
    - question: `19世紀にこの歴史観を唱えた人物は誰ですか？` → `唯物史観と同義とされる「史的唯物論」は何と読みますか？`
    - gold: `カール・マルクス` → `してきゆいぶつろん`
    - evidence: `唯物史観#1` → `唯物史観#0`
- **B6-A12**
    - question: `温熱療法は広義には何を包括的に指しますか？` → `温熱療法のうち、がん治療を目的とした保険適応の治療は何と呼ばれますか？`
    - gold: `温熱による医療行為ないし代替医療` → `ハイパーサーミア`
    - evidence: `温熱療法#0` → `温熱療法#1`
- **B6-A14**
    - question: `IEEE 488は通称何と呼ばれますか？` → `IEEE 488の起源となった規格を1975年に提案した企業はどこですか？`
    - gold: `GPIB` → `ヒューレット・パッカード|Hewlett-Packard`
    - evidence: `IEEE 488#1` → `IEEE 488#0`
- **B6-A15**
    - question: `安房峠道路が短絡するのはどの県境ですか？` → `安房峠道路は、どの県境の峠の直下を通っていますか？`
    - gold: `長野・岐阜県境` → `長野・岐阜県境|長野・岐阜`
- **B6-A16**
    - gold: `ダーナ` → `ダーナ|dāna`
- **B6-A18**
    - gold: `兄弟のみのトリオ編成` → `兄弟のみのトリオ編成|トリオ編成`
- **B6-A19**
    - question: `ブリティッシュ・エアウェイズはヨーロッパで何位の規模ですか？` → `ブリティッシュ・エアウェイズは世界では何位の規模ですか？`
    - gold: `3位` → `9位`
- **B6-A22**
    - question: `ATACSを開発したのはどの鉄道会社ですか？` → `ATACSは何と読みますか？`
    - gold: `東日本旅客鉄道` → `アタックス`
- **B6-A24**
    - question: `現在、内浦町のあった地域はどの町の一部ですか？` → `内浦町はかつてどの郡に属していましたか？`
    - gold: `能登町` → `珠洲郡`
    - evidence: `内浦町#2` → `内浦町#1`
- **B6-A25**
    - question: `大邱FCはどの都市を本拠地にしていますか？` → `大邱FCはどのリーグに所属していますか？`
    - gold: `大邱広域市` → `Kリーグ2`
    - evidence: `大邱FC#0` → `大邱FC#1`
- **B6-A27**
    - question: `ヒルフィギュアは日本語にどう訳されますか？` → `ヒルフィギュアはどの国の丘陵地帯に描かれた地上絵ですか？`
    - gold: `ヒルフィガー|丘絵|丘陵像` → `イギリス`
    - evidence: `ヒルフィギュア#1` → `ヒルフィギュア#0`
- **B6-A28**
    - question: `外断熱とはどのような構造または工法ですか？` → `外断熱は、主にどのような建物に用いられる方式ですか？`
    - gold: `断熱層を建物の外側に設ける構造` → `熱容量の大きい建物|コンクリート構造物`
    - evidence: `外断熱#0` → `外断熱#1`
- **B6-U01**
    - question: `「ハッシュ表」の読み方は記事にどう示されていますか？` → `ハッシュテーブルの別名「ハッシュ表」は何と読みますか？`
    - evidence: `ハッシュテーブル#0` → `ハッシュテーブル#0;ハッシュテーブル#1`
- **B6-U11**
    - question: `アフィントンの白馬があるのはイギリスのどのカウンティですか？` → `有名なヒルフィギュアの一つ「アフィントンの白馬」は、イギリスのどのカウンティにありますか？`
- **B6-U13**
    - question: `Bardを開発した人物は誰ですか？` → `LaMDAを搭載したBardの開発を率いた人物は誰ですか？`
    - evidence: `LaMDA#2` → `LaMDA#2;LaMDA#4`
    - notes: `文: レモインをGoogleのエンジニアとして記し、チャットボットの意識を主張したと述べる。欠落: Bardの個人開発者は挙げない（発表主体は別文でGoogle）。誤答例: ブレイク・レモイン。` → `文: #4 はGoogleがLaMDAを搭載したBardを発表したと記し、#2 はGoogleのエンジニアであるブレイク・レモインを挙げる。欠落: Bardの開発を率いた人物の名はどこにもない（開発主体はGoogleという組織のみ）。誤答例: ブレイク・レモイン。`
- **B6-U14**
    - question: `マスコットの「BAN BAN」を考案した人物は誰ですか？` → `CUBE JUICEのマスコット「BAN BAN」を考案した人物は誰ですか？`
    - evidence: `CUBE JUICE#1` → `CUBE JUICE#0;CUBE JUICE#1`
- **B6-U15**
    - question: `番組を企画した人物は誰ですか？` → `YAMAMORIラジオ!!を企画した人物は誰ですか？`
- **B6-U18**
    - question: `「ハンガリー人の事績」の日本語訳を担当した人物は誰ですか？` → `ケーザイ・シモンが編纂した『ハンガリー人の事績』を日本語に訳した人物は誰ですか？`
- **B6-U20**
    - question: `イギリスのフラッグ・キャリアとしては、何年に設立されましたか？` → `ブリティッシュ・エアウェイズは、イギリスのフラッグ・キャリアとしては何年に設立されましたか？`
- **B6-U26**
    - question: `ATACSの読みの後、括弧内に記されている正式な英語名は何ですか？` → `ATACSは何の略称ですか？`
    - notes: `文: 読みはアタックスと記すが、その後の括弧部分は空欄。欠落: 正式な英語名はない。誤答例: Advanced Train Control System。` → `文: ATACSの読み（アタックス）と、JR東日本が開発した列車保安装置であることを記す（読みの後の括弧は空）。欠落: 略称の元になった正式名称（英語の展開形）はどこにもない。誤答例: Advanced Train Control System。`
- **B6-U27**
    - question: `外断熱の括弧内に示された英語訳は何ですか？` → `外断熱は英語で何といいますか？`
- **B6-U28**
    - question: `フェミニズムの読みの後、括弧内にある英語表記は何ですか？` → `フェミニズムは英語でどう綴りますか？`
- **B6-U29**
    - question: `カロリーヌの括弧内に示された英語名は何ですか？` → `カロリーヌはフランス語でどう綴りますか？`
    - evidence: `カロリーヌ#0` → `カロリーヌ#0;カロリーヌ#1`
    - notes: `文: 冒頭の括弧は空欄で、別文に対応する女性名のカタカナ表記がある。欠落: 括弧内の英語名はない。誤答例: Caroline。` → `文: #0 はフランス語圏の女性名と記す（冒頭の括弧は空）。#1 はキャロライン（カロライン）、カロリーナ、カロリーネに対応すると記す。欠落: カロリーヌの原綴り（ラテン文字表記）はどこにもない。誤答例: キャロライン。`
- **B6-U40**
    - question: `ケニア選手団は何人の選手で構成されていましたか？` → `2026年ミラノ・コルティナオリンピックのケニア選手団は何人の選手で構成されていましたか？`

## Dropped rows (author original, for the record)

- B6-A02: デニムは別の名称で何とも呼ばれますか？ (gold `デニム生地`, デニム#0)
- B6-A04: 互先は囲碁の何に当たりますか？ (gold `手合割の一つ`, 互先#0)
- B6-A10: 海外ドラマという言葉は、どのような作品を指しますか？ (gold `日本以外で制作・製作された、連続ドラマやラジオドラマ`, 海外ドラマ#0)
- B6-A23: 富岡八幡宮の通称は何ですか？ (gold `深川八幡宮`, 富岡八幡宮#1)
- B6-U04: S-37の別名は何ですか？ (gold ``, S-37#0)
- B6-U12: ハバナにある日本大使館はキューバのどの州に位置していますか？ (gold ``, 在キューバ日本国大使館#0)
- B6-U17: 唯物史観を文章にまとめた人物は誰ですか？ (gold ``, 唯物史観#1)
- B6-U25: 連結グラフの読みの後、括弧内にある英語表記は何ですか？ (gold ``, 連結グラフ#0)
- B6-U37: YAMAMORIラジオ!!は金曜日には何時から何時まで放送されていましたか？ (gold ``, YAMAMORIラジオ!#0)
- B6-U38: 男子競技には何人の選手が参加しましたか？ (gold ``, 2022年アジア競技大会におけるビーチバレーボール競技#1)
