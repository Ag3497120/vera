# Audit of bank 3 (bank3.tsv)

Auditor: Claude (Opus 5.5), 2026-10-08. Inputs: `bank2-author/out/bank3.tsv` (100 items, codex gpt-6-luna from `PROMPT3.md`,
no access to Vera code), the two corpora, the author's `check3.py` / `README3.md`. Standards: bank2's (`AUDIT.md`, `AUDIT_r2.md`:
gold verbatim in evidence, gold not in the question and not guessable from question/title, one clear answer, natural question,
no generic/definitional golds, no duplicates) plus the kind rules of the request: two-facts must really need two sentences
(drop if one suffices; no arithmetic); paraphrase shares no content word with the gold sentence (author's strict character-bigram
check, subject removed) and stays natural; unknown-word: the question's surface is absent from the corpus, the gold present, and
the mapping is one a human would make; compare decidable from the two cited sentences alone; summary-choice exactly one true
option, two plausible false ones (contradicted or unsupported), each <= 25 chars, gold = letter|text; unans-kind answer absent
from the whole corpus file (searched), same forms as answerable items.

Outputs: `bank3_audited.tsv` (kept rows + column `audit`), `check3_audited.py` / `.txt` (0 errors), `baselines3.py` / `.txt`.
Final copy: `experiments/line3/bank3/` (sha256 recorded in `MANIFEST.json` before any Vera system read it).

**Format change (all rows, not counted as a fix):** evidence ids converted to the bank2 convention — fulllead `title#i` with i
**0-based** (the author used 1-based), s3000 evidence = bare article title. The `notes` column is kept (paraphrase mappings,
unknown-word surface vs corpus surface); for fixed rows it describes the new wording.

## Counts

| kind | authored | valid | fixed | dropped | kept |
|---|---|---|---|---|---|
| two-facts | 20 | 3 | 11 | 6 | 14 |
| paraphrase | 20 | 5 | 15 | 0 | 20 |
| unknown-word | 20 | 7 | 11 | 2 | 18 |
| compare (s3000) | 15 | 7 | 7 | 1 | 14 |
| summary-choice | 10 | 0 | 10 | 0 | 10 |
| unans-kind | 15 | 7 | 8 | 0 | 15 |
| total | 100 | 29 | 62 | 9 | 91 |

Corpus split after audit: fulllead 76, s3000 15 (14 compare + 1 unans compare).

## Main findings

1. **two-facts was mostly realised as "identify the subject by a description, then look up".** Instead of a bridge (X → founder →
   school), 16/20 questions replace the title by a paraphrase of sentence i and ask a fact of sentence j. That needs two sentences
   only when sentence j does not restate the question's key words. 6 dropped: one sentence suffices (tf03, tf05, tf06, tf17),
   gold = 非 + subject (tf02), gold decided by vocabulary not text (tf18). Of the fixes, 5 were "one sentence sufficed" repairs
   (tf08, tf09, tf10, tf13, tf15), 2 had no antecedent (「この競技」「この惑星」: tf15, tf16), 2 had wrong evidence ids (tf05 dropped,
   tf13), 1 asked list order (tf19). The kept items are of two clean types: (a) the answer sentence has no subject and the question
   identifies the article only through the other sentence (tf07, tf08, tf10, tf12, tf13, tf14, tf16, tf19, tf20); (b) each sentence
   holds half of the answer (tf09 full name ← #0, who left ← #1; tf15 first edition ← #0, its events ← #1). Riddle-style
   descriptions remain somewhat artificial but are unambiguous in the corpus (checked by search).
2. **paraphrase passes the strict bigram rule (20/20) but the author bought it with meaning errors.** 3 factual errors
   (pa09 Canada was the assumed battlefield, not a "focus"; pa12 古浄瑠璃 *is* the puppet play, the question said "before
   古浄瑠璃"; pa14 the dam sends water, not electricity), 1 artificial question (pa11 "which name comes first"), 9 stilted or
   vague wordings (退団/低音域, 個人活動名義, 後半の代, 中心天体周回, 底部までの距離, 一件, 両端…), 2 with a second correct answer
   (pa03, pa05). All rewrites were re-checked under the same strict bigram rule (`check3_audited.txt`). 7 paraphrase items ask a
   fact already asked literally in bank2 (pa05, pa08, pa11, pa13, pa14, pa17, pa18): a controlled literal-vs-paraphrase contrast.
3. **unknown-word contains no kana spelling, and the altered subject is not needed.** Alterations as authored: 13 suffix additions (町内, 地区,
   思想, 規格, 家, 案, コンビ, 地方 …) whose surface contains the corpus title verbatim — two of them not words anyone uses
   (唯物史観説, 態文法) —, 4 space splits, 1 split inside a word no human writes (「CUBE J UICE」), and 2 non-alterations whose
   "surface" is a phrase containing the verbatim title (「千葉神社の別称」「ヒルフィギュアの訳語」). Kana is almost impossible under the rule: nearly every kanji title has its reading in
   the lead's gloss (e.g. 唯物史観（ゆいぶつしかん）), so the kana surface *does* occur in the corpus. Fixes replaced the bad surfaces
   with variants a person really types: ボイス (corpus ヴォイス), ヒル・フィギュア, ビースティボーイズ, Cube Juice; two guessable golds
   (uw02 非連結グラフ, uw10 バダフシャーン州) were changed. **Diagnostic:** B1 with the subject surface *deleted* from the question still
   finds the gold in 16/18 (MeCab) — the rest of the question (マスコット, 結成, 通勤率, 機密解除 …) locates the sentence in this
   592-sentence corpus. So these items do not measure surface mapping; see the baseline section.
4. **compare: position bias and two ambiguities.** 13/15 golds were the first-described entity; 6 items were swapped (now 7/7).
   co07 dropped: 「サミーの遊技機」 also matches キングキャメル (2003, Sammy) in S3000, which would flip the answer; co13 fixed:
   S3000 also has 1974年アルペンスキー世界選手権 (now 「第43回…」). All other descriptions are unique in S3000 (searched). The author
   described the entities instead of naming them (to keep the gold title out of the question), so each item also requires
   identify-by-description. Every item is the same comparison type (earlier year); no count / 最大 / 最初 comparisons.
5. **summary-choice: all 10 golds were letter A** (always-A = 100%), every true option was a verbatim substring of the evidence,
   4 true options were bare noun fragments (妙見本宮, 熊の「BAN BAN」, 最大15台の機器, 1.54倍の光), sc03 had **two true options**
   (「県都に置かれている」 is true: 千葉市 is the prefectural capital), joke/implausible distractors (犬の「ワンワン」, 海水を貯める,
   木星より近い恒星, 高校生), and 5 true options duplicated facts asked elsewhere in the bank. All 10 rewritten: statements, letters
   now A3/B4/C3, distractors contradicted by the article (or false and unsupported).
6. **unans-kind answers are really absent** (searched both corpus files for 計算量/O(1), dropz, 衝突/チェイン/オープンアドレス,
   来日, 決勝/得点, 閉店, Bard, 由来, ケーブル, 県社 year, 観客, レバノン/アルバニア counts). 8 fixed: no antecedent (「このデータ構造」
   「この思想運動」「この大会」), ill-posed questions with no single answer even in the world (sunset time, device power consumption,
   "which of U-17/U-20 had more teams" — both 24), a presupposition (「採用されたハッシュ関数」), one option contradicted by inference.
   Tell: all 15 unans subjects are subjects of answerable bank-3 items (CUBE JUICE ×2, ハッシュテーブル ×2, FIFA U-17 ×3 …), and
   uk05 (レバノン選手団) is also a bank2 unans subject.
7. **Duplicates and concentration.** The same fact was asked in several kinds (妙見本宮 ×4, ヤウク ×2, 鳳珠郡能登町 ×2,
   非連結グラフ ×2, 大学図書館の近く ×2, 15台 ×2, イングランド ×2, BAN BAN ×2, 1.54倍 ×2); now every (gold sentence, gold) pair occurs
   once. The author worked through the first articles of the file: 91 rows use 68 articles, CUBE JUICE ×6, ハッシュテーブル ×5,
   フェミニズム ×5, 千葉神社/ビースティ・ボーイズ/FIFA U-17/IEEE 488 ×4. 29 bank-3 articles are bank2 subjects; 16 answerable
   bank-3 items ask a fact bank2 already asks (listed in `check3_audited.txt`).

## Re-check

`check3_audited.py` (author's checker adapted: 9 columns, 0-based evidence, new counts; adds: every gold alternative verbatim in
cited evidence and absent from the question; compare titles absent from the question and the gold's stated year is the earlier
one; summary letter/option/length; no duplicate (sentence, gold); INFO on letters, compare position, alteration type, reuse,
bank2 overlap). Result: **91 rows, 0 errors.**

## Baselines (`baselines3.txt`; MeCab / bigram; gold-in-candidate unless stated)

| kind | n | B1 | B2 | other |
|---|---|---|---|---|
| two-facts | 14 | 3 (21%) / 1 (7%) | 8 (57%) / 6 (43%) | both evidence sentences in B2: 5/14 / 5/14 |
| paraphrase | 20 | 8 (40%) / 6 (30%) | 12 (60%) / 10 (50%) | |
| unknown-word | 18 | 16 (89%) / 14 (78%) | 16 (89%) / 15 (83%) | B1-kana 17 (94%) / 14 (78%); B1 with subject deleted 16 (89%) / 15 (83%) |
| compare | 14 | gold sentence 6/14 / 5/14 | | lookup+year solver 13 (93%) / 12 (86%); first-described 7/14; chance 50% |
| summary-choice | 10 | | | option lookup in the subject article 9.0 (90%) / 9.5 (95%); always-A/B/C 3/4/3; chance 33% |
| unans-kind | 15 | candidates for 15/15 | | keyword lookup never abstains |

Kana normalisation (NFKC + MeCab reading of question and units): adds 1 item over plain B1 (uw06 青海町内) with MeCab and none with
bigrams; it is not needed because plain lookup already solves 16/18, and the subject is not needed either. MeCab readings are also
unreliable for the kana case that matters (古浄瑠璃 → フルジョウルリ, 六日町 → ムイカチョウ, unknown Latin words get no reading).

Reading: only **paraphrase** (B1 30-40%, B2 50-60%) and **two-facts** (B1 7-21%, B2 43-57%) leave headroom above trivial lookup.
**unknown-word, compare and summary-choice are at 86-95% for trivial lookup**, so an on/off difference there cannot be credited
to the foundation; they can only show a *loss* (a system that does worse than lookup). unans measures abstention, which lookup
never does: read a system's unans rate against its own answerable rate. Sample sizes are small (one item = 5-7 points).

## Per-item decisions

Format: id — decision — reason; for fixes the changed fields (old → new). Evidence ids in this list are the author's 1-based ids.
- **b3_tf01** (two-facts) — fixed — question unnatural (「どの二種類の抽象的な仕組み」; 抽象的 is not in the text); reworded
    - question: `キーと値の組をすばやく引ける構造は、どの二種類の抽象的な仕組みを効率よく実現する手段ですか？` → `キーと値の組をすばやく引けるデータ構造は、何と何の効率的な実装の一つとされていますか？`
    - gold: `連想配列や集合` → `連想配列や集合`
- **b3_tf02** (two-facts) — drop — one sentence suffices (#2 alone) and gold 非連結グラフ = 非 + subject, guessable from the question; subject already in bank2 (I2-002)
- **b3_tf03** (two-facts) — drop — one sentence suffices: #3 alone says the back shows ヨコ糸; the second link (ヨコ糸 = 緯糸) is dictionary knowledge, not a fact of sentence #1
- **b3_tf04** (two-facts) — fixed — question contained 「性のあり方」, part of the gold; reworded
    - question: `現代社会で男性の視点が優先され女性が不当な扱いを受けると主張する思想は、どのような性のあり方まで射程を広げていますか？` → `現代の社会では男性の視点が優先され女性が不当な扱いを受けている、と主張する思想は、現代ではどこまで射程を広げてきましたか？`
    - gold: `多様な性のあり方` → `多様な性のあり方|多様な性`
- **b3_tf05** (two-facts) — drop — evidence wrong (#2 is the commute rate; the answer is in #3) and #3 alone suffices (question restates 能生町 + 改めて発足 from #3)
- **b3_tf06** (two-facts) — drop — one sentence suffices (#4 alone: 中央区 + 地域名); gold contains the title 天満橋; awkward question
- **b3_tf07** (two-facts) — valid — ok: #3 has no subject, the question identifies the town only through #2 (珠洲郡); a grader should accept 能登町
- **b3_tf08** (two-facts) — fixed — one sentence sufficed: the question restated #4's definition of the gold (北辰妙見尊星王の本宮を意味する別称); gold 妙見本宮 also used by pa04/uw12/sc03. Now asks the 社紋 (#3, no subject) of the shrine identified by #1
    - question: `千葉市中央区にある神社について、北辰妙見尊星王の本宮を意味する別称は何ですか？` → `千葉市中央区にある神社の社紋は何ですか？`
    - gold: `妙見本宮` → `九曜紋`
    - evidence: `千葉神社#1;千葉神社#4` → `千葉神社#1;千葉神社#3`
- **b3_tf09** (two-facts) — fixed — one sentence sufficed (#2 contains both 脱退 and ベース, so the bassist link of #1 is not needed); gold ヤウク duplicated pa06. Now asks the full name of the member who left in 1981 (#2 gives only シャタン, #1 the full name)
    - question: `ヤング・アボリジニーズのメンバーから結成された初期編成のベーシストが脱退した後、ベースを引き継いだのは誰ですか？` → `ビースティ・ボーイズで1981年に脱退したメンバーのフルネームは何ですか？`
    - gold: `ヤウク` → `ジェレミー・シャタン`
- **b3_tf10** (two-facts) — fixed — one sentence sufficed: the question named 星野英彦's solo project, so #3 alone gives dropz whoever took part. Now asks whose project 長尾伸一's unit joined (#1 identifies the unit, #3 has no subject)
    - question: `長尾伸一のソロユニットが参加した、星野英彦のソロプロジェクト名は何ですか？` → `シンガーソングライター長尾伸一のソロユニットは、誰のソロプロジェクトにメンバーとして参加していますか？`
    - gold: `dropz` → `星野英彦`
- **b3_tf11** (two-facts) — fixed — second correct location (市内中心部の南西) in the same sentence; gold alternative added
    - gold: `大学図書館の近く` → `大学図書館の近く|中心部の南西`
- **b3_tf12** (two-facts) — valid — ok: #3 has no subject; 「2015年まで基礎自治体」 occurs only in #2 (98 articles mention 基礎自治体). Same fact as bank2 (73,921人) — cross-bank contrast
- **b3_tf13** (two-facts) — fixed — question named テレゴ (= title), so the article is found directly and #4 is decoration; evidence id #3 wrong (the 6副郡 fact is #4); now identifies the district only via #4
    - question: `旧テレゴ郡時代に6つの副郡があった県について、県都はどの副郡に置かれていますか？` → `郡だった時代に6つの副郡があった県では、県都はどの副郡に置かれていますか？`
    - gold: `アイーヴ副郡` → `アイーヴ副郡|アイーヴ`
    - evidence: `テレゴ県#2;テレゴ県#3` → `テレゴ県#2;テレゴ県#4`
- **b3_tf14** (two-facts) — valid — ok: #3 (イングランドが初優勝を果たした) has no subject; tournament identified only through #2
- **b3_tf15** (two-facts) — fixed — 「この競技」 had no antecedent, and #3 alone answered (追加 = added later). Now asks the events of the first edition: #2 gives 1983's events, #1 that 1983 was the first
    - question: `選択競技として複数回行われたこの競技で、後年の回に新しく加わった種目は何ですか？` → `ユニバーシアードで自転車競技が初めて選択競技として行われた年には、どんな種目が実施されましたか？`
    - gold: `マウンテンバイクとBMX` → `ロードレースとトラックレース|ロードレース|トラックレース`
    - evidence: `ユニバーシアード自転車競技#1;ユニバーシアード自転車競技#3` → `ユニバーシアード自転車競技#1;ユニバーシアード自転車競技#2`
- **b3_tf16** (two-facts) — fixed — 「この惑星」 had no antecedent, and #3 alone already implies 外側. Now: planet identified by #3, answer in #2 (no subject)
    - question: `豊富な水素大気の下に水層がありうるこの惑星は、居住可能域のどちら側を公転していますか？` → `豊富な水素の大気の下に水の層が存在しうるとされる太陽系外惑星は、地球が太陽から受け取る光の何倍の光を受けていますか？`
    - gold: `すぐ外側` → `1.54倍`
    - evidence: `TOI-2285 b#1;TOI-2285 b#3` → `TOI-2285 b#2;TOI-2285 b#3`
- **b3_tf17** (two-facts) — drop — one sentence suffices (#3 alone answers; the description from #1 is decoration); 「の地位」 of the gold is in the question
- **b3_tf18** (two-facts) — drop — gold decided by vocabulary (記事投稿 = ブログ), not by the text; コメント is an equally plausible 'posting' feature
- **b3_tf19** (two-facts) — fixed — question asked list order (「先頭に挙がるもの」), unnatural; now asks the head-office prefecture (#2, no subject) of the company identified by #1
    - question: `エジプトで貨物自動車やバスを製造する会社が登録しているブランド名のうち、先頭に挙がるものは何ですか？` → `エジプトで貨物自動車やバスの製造開発を行っている企業は、どの県に本社を置いていますか？`
    - gold: `ECHOLINE` → `カリュービーヤ県|カリュービーヤ`
    - evidence: `マニュファクチャリング・コマーシャル・ビークルズ#1;マニュファクチャリング・コマーシャル・ビークルズ#3` → `マニュファクチャリング・コマーシャル・ビークルズ#1;マニュファクチャリング・コマーシャル・ビークルズ#2`
- **b3_tf20** (two-facts) — fixed — wording unnatural (「芸能名が付けられた」「起点」); reworded, short alternative added
    - question: `1973年に芸能名が付けられた伝統芸能の起点とされる、祭礼での芝居の名前は何ですか？` → `1973年に発行された本で現在の名前を付けられた郷土芸能は、何という芝居が始まりとされていますか？`
    - gold: `篠路村烈々布素人芝居` → `篠路村烈々布素人芝居|烈々布素人芝居`
- **b3_pa01** (paraphrase) — fixed — question unnatural (「外側に現れる素材はどんな色調を帯びますか」); reworded
    - question: `デニムでは、外側に現れる素材はどんな色調を帯びますか？` → `デニムの外面は、たいてい何色をしていますか？`
    - gold: `インディゴ色` → `インディゴ色|インディゴ`
    - notes: `外側→表側、素材→タテ糸、色調→色` → `外面→表側、たいてい→通常、何色→インディゴ色`
- **b3_pa02** (paraphrase) — valid — ok (definition-type gold; a grader should accept 社会運動と思想)
- **b3_pa03** (paraphrase) — fixed — 「別の呼び方」 has two correct answers in the sentence (唯物論的歴史観 = full form, 史的唯物論 = synonym); alternative added
    - gold: `史的唯物論` → `史的唯物論|唯物論的歴史観`
- **b3_pa04** (paraphrase) — valid — ok (kept as the single item on 妙見本宮; tf08/uw12/sc03 changed or dropped)
- **b3_pa05** (paraphrase) — fixed — 「立ち位置はどこ」 is also answered by 向かいあった斜面や遠方 in the same sentence; alternatives added
    - gold: `地上から` → `地上から|地上|向かいあった斜面や遠方`
- **b3_pa06** (paraphrase) — fixed — 退団 / 低音域 unnatural for a band; reworded
    - question: `ビースティ・ボーイズでは、退団に伴い低音域を引き継いだ人物は誰ですか？` → `ビースティ・ボーイズで、メンバーが抜けたあと低音パートを引き継いだのは誰ですか？`
    - notes: `退団→脱退、低音域→ベース、引き継いだ→担当するようになった` → `抜けた→脱退、低音パート→ベース、引き継いだ→担当するようになった`
- **b3_pa07** (paraphrase) — fixed — stilted (「個人活動名義を持つ人物の氏名」); reworded
    - question: `CUBE JUICEの個人活動名義を持つ人物の氏名は何ですか？` → `CUBE JUICEは、どの歌手がひとりで活動するための名義ですか？`
    - gold: `長尾 伸一` → `長尾 伸一`
    - notes: `個人活動名義→ソロユニット` → `歌手→シンガーソングライター、ひとりで活動するための名義→ソロユニット`
- **b3_pa08** (paraphrase) — fixed — 「後半の代」 vague and 「家名で用いた苗字」 redundant; reworded. Same fact as bank2 I2-022 (cross-bank contrast)
    - question: `善五郎では、後半の代が家名で用いた苗字は何ですか？` → `善五郎の十代目から後の当主は、どんな名字を用いましたか？`
    - gold: `永樂` → `永樂`
    - notes: `後半の代→10代以降、家名で用いた苗字→永樂姓を名乗った` → `十代目から後→10代以降、名字→姓、用いました→名乗り`
- **b3_pa09** (paraphrase) — fixed — factually off: the plan did not 'focus on' a centre of Anglo-American conflict; Canada was the assumed main battlefield; reworded
    - question: `レッド計画が焦点を当てる英米対立の中心地はどの国ですか？` → `レッド計画で、アメリカとイギリスが戦うならば主な戦いの舞台になると見込んだ国はどこですか？`
    - notes: `焦点を当てる→主戦場、英米対立→米英間戦争、中心地→主戦場` → `アメリカとイギリスが戦う→米英間戦争、主な戦いの舞台→主戦場、見込んだ→想定されていた`
- **b3_pa10** (paraphrase) — valid — ok
- **b3_pa11** (paraphrase) — fixed — asked which name comes first in the text (artificial); now asks the name used by the Kansai-side operator (和歌山バス)
    - question: `サウスウェーブ号の二つの名称のうち、順序が先なのはどちらですか？` → `サウスウェーブ号のことを、関西側の運行会社は何という路線名で呼びますか？`
    - notes: `二つの名称→二つの案内名、順序が先→文中で最初の呼称` → `関西側の運行会社→和歌山バス（地理知識で対応）、路線名で呼びます→案内されている`
- **b3_pa12** (paraphrase) — fixed — factually wrong: the text says 古浄瑠璃 IS the puppet play popular before 近松, not a form popular before 古浄瑠璃 began; reworded
    - question: `古浄瑠璃が始まる前に大衆の支持を集めた舞台形式は何ですか？` → `古浄瑠璃は、当時の大衆に好まれたどんな舞台芸能でしたか？`
    - notes: `大衆→庶民、支持を集めた→人気だった、舞台形式→人形芝居` → `当時→江戸時代初期、大衆→庶民、好まれた→人気だった、舞台芸能→人形芝居`
- **b3_pa13** (paraphrase) — valid — ok
- **b3_pa14** (paraphrase) — fixed — factually wrong: the dam sends water to the power station, it does not send electricity; reworded. Same fact as bank2 R2-I009
    - question: `赤尾ダムから送られる電気の上限値はいくらですか？` → `赤尾ダムが供給した水で生み出される電気の出力は、上限でどれくらいですか？`
    - gold: `3万2,500キロワット` → `3万2,500キロワット|3万2,500`
    - notes: `電気→電力、上限値→最大` → `供給した水→送水し、生み出される→発生する、電気の出力→電力、上限→最大`
- **b3_pa15** (paraphrase) — fixed — 「一件」「結び付けて挙げられた」 vague; reworded
    - question: `LaMDAの一件に結び付けて挙げられた試験名は何ですか？` → `LaMDAをめぐる騒ぎは、どの試験の妥当性をめぐる論争を呼んだのですか？`
    - notes: `一件→主張をめぐる出来事、試験名→チューリング・テスト` → `騒ぎ→レモインの主張、試験→テスト、妥当性→有効性、論争→議論`
- **b3_pa16** (paraphrase) — fixed — 「関わる対象を二つ挙げると」 unnatural; reworded
    - question: `ニューツーリズムでは、訪問者が関わる対象を二つ挙げると何ですか？` → `ニューツーリズムでは、行った先の土地で何と何にふれあうことを大切にしますか？`
    - gold: `人や自然` → `人や自然`
    - notes: `訪問者→旅行者、関わる→触れ合い、対象→人や自然` → `行った先の土地→旅行先、ふれあう→触れ合い、大切にします→重要視された`
- **b3_pa17** (paraphrase) — valid — ok (same fact as bank2 I2-034, cross-bank contrast)
- **b3_pa18** (paraphrase) — fixed — 「底部までの距離」 is not 最大水深 (distance to the bottom from where?); reworded. Same fact as bank2 R2-I006
    - question: `シリヤン湖の底部までの距離として記された値は何ですか？` → `シリヤン湖は、もっとも深い所でどれくらいの深さですか？`
    - gold: `120 m` → `120 m|120`
    - notes: `底部までの距離→最大水深` → `もっとも深い所での深さ→最大水深`
- **b3_pa19** (paraphrase) — fixed — 「中心天体周回にかかる期間」 stilted; reworded
    - question: `TOI-2285 bの中心天体周回にかかる期間はどれほどですか？` → `TOI-2285 bは、主星の周りを一周に何日ほどかけますか？`
    - gold: `約27.3日` → `約27.3日|27.3日`
    - notes: `中心天体周回にかかる期間→公転周期` → `主星の周りを一周→公転、何日ほど→周期は約27.3日`
- **b3_pa20** (paraphrase) — fixed — 「連なる丁目の範囲の両端」 unnatural; reworded to ask the last 丁
    - question: `東雲西町に連なる丁目の範囲の両端はどこですか？` → `東雲西町は、何丁目まであるのですか？`
    - gold: `東雲西町一丁から東雲西町四丁` → `四丁|東雲西町四丁`
    - notes: `丁目の範囲の両端→行政地名の範囲` → `何丁目まである→行政地名は一丁から四丁`
- **b3_uw01** (unknown-word) — fixed — gold 「すばやく参照」 repeats the question's 高速化 and is not the operation; operation 参照 as gold
    - gold: `すばやく参照` → `参照`
- **b3_uw02** (unknown-word) — fixed — gold 非連結グラフ = 非 + subject (guessable) and question copied 連結でない; now asks 連結成分 (same fact as bank2 I2-002: cross-bank contrast literal vs split surface)
    - question: `連結 グラフでは、連結でないものを何と呼びますか？` → `連結 グラフで、極大で連結な部分グラフは何と呼ばれますか？`
    - gold: `非連結グラフ` → `連結成分`
    - evidence: `連結グラフ#2` → `連結グラフ#3`
- **b3_uw03** (unknown-word) — valid — ok (a grader should accept 丈夫)
- **b3_uw04** (unknown-word) — fixed — #2 states three claims (家父長制を基礎とし / 男性の視点を優先し / 女性が不当な扱い); any of them answers; alternatives added
    - gold: `女性が不当な扱いを受けている` → `女性が不当な扱いを受けている|男性の視点を優先し|家父長制を基礎とし`
- **b3_uw05** (unknown-word) — drop — 唯物史観説 is not a form a human would use; 移行先 ambiguous (#3 states both 無階級→階級 and 階級→無階級); the kana reading ゆいぶつしかん is in the corpus gloss, so no valid unknown surface exists
- **b3_uw06** (unknown-word) — valid — ok
- **b3_uw07** (unknown-word) — valid — ok (gold contains the title; a grader should accept 一丁目から三丁目)
- **b3_uw08** (unknown-word) — fixed — 態文法 is not a word, and gold 文法範疇 shared 文法 with the question; now uses ボイス, the common spelling of the corpus surface ヴォイス (absent from the corpus)
    - subject: `態文法` → `ボイス`
    - question: `態文法で動詞と主語や目的語の関係を示す分類枠は何ですか？` → `文法でいうボイスは、日本語では何と呼ばれますか？`
    - gold: `文法範疇` → `態`
    - evidence: `態#2` → `態#1`
    - notes: `態文法／態（「文法」を追加）` → `ボイス／ヴォイス（表記ゆれ: ボ↔ヴォ）`
- **b3_uw09** (unknown-word) — fixed — duplicate of tf07 (same evidence and gold 鳳珠郡能登町); now asks the region (#1)
    - question: `内浦町内が現在含まれる自治体はどこですか？` → `内浦町内は、石川県のどの地方にありましたか？`
    - gold: `鳳珠郡能登町` → `奥能登`
    - evidence: `内浦町#3` → `内浦町#1`
- **b3_uw10** (unknown-word) — fixed — gold バダフシャーン州 = subject + 州, guessable from the question; now asks the plateau (#2)
    - question: `バダフシャーン地方のアフガニスタン側にある州名は何ですか？` → `バダフシャーン地方は、どの高原の西部に位置していますか？`
    - gold: `バダフシャーン州` → `パミール高原`
    - evidence: `バダフシャーン#3` → `バダフシャーン#2`
- **b3_uw11** (unknown-word) — valid — ok
- **b3_uw12** (unknown-word) — drop — not an altered surface: the 'subject' 千葉神社の別称 is a phrase and the plain title 千葉神社 occurs verbatim in the question; gold duplicates pa04
- **b3_uw13** (unknown-word) — fixed — not an altered surface (ヒルフィギュアの訳語 is a phrase containing the verbatim title); now uses the dotted spelling ヒル・フィギュア (absent from corpus); all three renderings of #2 accepted
    - subject: `ヒルフィギュアの訳語` → `ヒル・フィギュア`
    - question: `ヒルフィギュアの訳語として挙げられる日本語を一つ答えてください。` → `ヒル・フィギュアは日本語でどのように訳されますか？`
    - gold: `丘絵` → `丘絵|丘陵像|ヒルフィガー`
    - notes: `ヒルフィギュアの訳語／ヒルフィギュア（「の訳語」を追加）` → `ヒル・フィギュア／ヒルフィギュア（中黒を挿入）`
- **b3_uw14** (unknown-word) — valid — ok
- **b3_uw15** (unknown-word) — fixed — ビースティ・ボーイズ史 unnatural as a subject and contains the title verbatim; now uses ビースティボーイズ (no middle dot, absent from corpus)
    - subject: `ビースティ・ボーイズ史` → `ビースティボーイズ`
    - question: `ビースティ・ボーイズ史でバンドが結成された年は何年ですか？` → `ビースティボーイズは何年に結成されましたか？`
    - notes: `ビースティ・ボーイズ史／ビースティ・ボーイズ（「史」を追加）` → `ビースティボーイズ／ビースティ・ボーイズ（中黒を省略）`
- **b3_uw16** (unknown-word) — fixed — gold 最大15台 contained the question word 最大
    - gold: `最大15台` → `15台`
- **b3_uw17** (unknown-word) — fixed — 「CUBE J UICE」 splits inside a word — no human writes it; now the mixed-case spelling Cube Juice (absent from corpus)
    - subject: `CUBE J UICE` → `Cube Juice`
    - question: `CUBE J UICEのマスコットの名前は何ですか？` → `Cube Juiceのマスコットは何という名前ですか？`
    - notes: `CUBE J UICE／CUBE JUICE（複合語を分割）` → `Cube Juice／CUBE JUICE（大文字小文字の違い）`
- **b3_uw18** (unknown-word) — fixed — #5 (土風炉に加えて茶陶を制作している) answers equally; alternative and evidence added
    - gold: `茶碗` → `茶碗|茶陶`
    - evidence: `善五郎#2` → `善五郎#2;善五郎#5`
- **b3_uw19** (unknown-word) — valid — ok
- **b3_uw20** (unknown-word) — valid — ok (same fact as bank2 I2-027: cross-bank contrast literal vs split surface)
- **b3_co01** (compare) — valid — ok: both descriptions unique in S3000, both years stated
- **b3_co02** (compare) — fixed — both descriptions unique in S3000, both years stated; order of the two entities swapped so the answer is not always the first-mentioned (position bias: 13/15 golds were first)
    - question: `韓国の女性小説家と日本の漫画家・漫画原作者のうち、生年が早いのはどちらですか？` → `日本の漫画家・漫画原作者と韓国の女性小説家のうち、生年が早いのはどちらですか？`
- **b3_co03** (compare) — valid — ok: both descriptions unique in S3000, both years stated
- **b3_co04** (compare) — fixed — both descriptions unique in S3000, both years stated; order of the two entities swapped so the answer is not always the first-mentioned (position bias: 13/15 golds were first)
    - question: `日本のキリスト教系新宗教とフランス・パリの経済学専門校のうち、設立年が早いのはどちらですか？` → `フランス・パリの経済学専門校と日本のキリスト教系新宗教のうち、設立年が早いのはどちらですか？`
- **b3_co05** (compare) — valid — ok: both descriptions unique in S3000, both years stated
- **b3_co06** (compare) — fixed — both descriptions unique in S3000, both years stated; order of the two entities swapped so the answer is not always the first-mentioned (position bias: 13/15 golds were first)
    - question: `ハンブルクの通信社とシカゴのソフトウェア会社のうち、設立年が早いのはどちらですか？` → `シカゴのソフトウェア会社とハンブルクの通信社のうち、設立年が早いのはどちらですか？`
- **b3_co07** (compare) — drop — ambiguous: S3000 also has キングキャメル (2003, a Sammy pachislot), so 「サミーの遊技機」 does not identify 獣王, and with キングキャメル the answer would flip
- **b3_co08** (compare) — valid — ok: both descriptions unique in S3000, both years stated
- **b3_co09** (compare) — fixed — both descriptions unique in S3000, both years stated; order of the two entities swapped so the answer is not always the first-mentioned (position bias: 13/15 golds were first)
    - question: `F値の小さい交換レンズとAndroid搭載スマートフォンのうち、発売年が早いのはどちらですか？` → `Android搭載スマートフォンとF値の小さい交換レンズのうち、発売年が早いのはどちらですか？`
- **b3_co10** (compare) — valid — ok: both descriptions unique in S3000, both years stated
- **b3_co11** (compare) — fixed — both descriptions unique in S3000, both years stated; order of the two entities swapped so the answer is not always the first-mentioned (position bias: 13/15 golds were first)
    - question: `新潟県の地震と佐賀県の空襲のうち、発生年が早いのはどちらですか？` → `佐賀県の空襲と新潟県の地震のうち、発生年が早いのはどちらですか？`
- **b3_co12** (compare) — fixed — both descriptions unique in S3000, both years stated; order of the two entities swapped so the answer is not always the first-mentioned (position bias: 13/15 golds were first)
    - question: `ソウルで行われた女子バスケットボール世界選手権とコペンハーゲン開催のバドミントン世界選手権のうち、開催年が早いのはどちらですか？` → `コペンハーゲン開催のバドミントン世界選手権とソウルで行われた女子バスケットボール世界選手権のうち、開催年が早いのはどちらですか？`
- **b3_co13** (compare) — fixed — ambiguous: S3000 also has 1974年アルペンスキー世界選手権; identified by 第43回 (from its sentence)
    - question: `アルペンスキー世界選手権とハンガリー開催の世界ジュニアフィギュアスケート選手権のうち、開催年が早いのはどちらですか？` → `第43回アルペンスキー世界選手権とハンガリー開催の世界ジュニアフィギュアスケート選手権のうち、開催年が早いのはどちらですか？`
- **b3_co14** (compare) — valid — ok: both descriptions unique in S3000, both years stated
- **b3_co15** (compare) — valid — ok: both descriptions unique in S3000, both years stated
- **b3_sc01** (summary-choice) — fixed — options were noun fragments, not statements; all 10 golds were letter A (always-A scores 100%); rewritten as statements, gold moved
    - question: `ハッシュテーブルについて正しいのはどれですか？ A. キーと値の組 B. 文字列だけの保存 C. 順序付きの要素列` → `ハッシュテーブルについて正しいのはどれですか？ A. 値を順番どおりに並べて保存する B. キーと値の組を格納する C. 木構造の一種である`
    - gold: `A|キーと値の組` → `B|キーと値の組を格納する`
- **b3_sc02** (summary-choice) — fixed — letter bias (all golds A); options reordered
    - question: `フェミニズムについて正しいのはどれですか？ A. 平等を確立することを目指す B. 家父長制を基礎にする C. 男女の二分法を当然とする` → `フェミニズムについて正しいのはどれですか？ A. 家父長制を基礎にする B. 男女の二分法を当然とする C. 平等を確立することを目指す`
    - gold: `A|平等を確立することを目指す` → `C|平等を確立することを目指す`
- **b3_sc03** (summary-choice) — fixed — two true options: C 「県都に置かれている」 is true by world knowledge (千葉市 is the prefectural capital); A was a bare noun; gold 妙見本宮 duplicated pa04. New true option from #2
    - question: `千葉神社について正しいのはどれですか？ A. 妙見本宮 B. 祭神は日本武尊 C. 県都に置かれている` → `千葉神社について正しいのはどれですか？ A. 旧社格は県社 B. 祭神は日本武尊 C. 千葉県佐倉市にある`
    - gold: `A|妙見本宮` → `A|旧社格は県社`
    - evidence: `千葉神社#4` → `千葉神社#2`
- **b3_sc04** (summary-choice) — fixed — options were bare noun phrases with joke distractors (犬の「ワンワン」); gold duplicated uw17; new true option from #1, C contradicted by #2
    - question: `CUBE JUICEについて正しいのはどれですか？ A. 熊の「BAN BAN」 B. 犬の「ワンワン」 C. 猫の「ミケ」` → `CUBE JUICEについて正しいのはどれですか？ A. 3人組のバンドである B. 2002年にメジャーデビューした C. 熊の「BAN BAN」がボーカル`
    - gold: `A|熊の「BAN BAN」` → `B|2002年にメジャーデビューした`
    - evidence: `CUBE JUICE#2` → `CUBE JUICE#1`
- **b3_sc05** (summary-choice) — fixed — true option duplicated tf11 (大学図書館の近く); distractor 高校生 implausible; new true option from #4, C contradicted by #1
    - question: `ウルフソン・カレッジについて正しいのはどれですか？ A. 大学図書館の近くにある B. 1965年に現在の名で設立 C. 学生の大半は高校生` → `ウルフソン・カレッジについて正しいのはどれですか？ A. 1965年に現在の名で設立 B. オックスフォード大学に属する C. 学生の大半は大学院生`
    - gold: `A|大学図書館の近くにある` → `C|学生の大半は大学院生`
    - evidence: `ウルフソン・カレッジ#3` → `ウルフソン・カレッジ#4`
- **b3_sc06** (summary-choice) — fixed — true option a fragment (最大15台の機器) duplicating uw16; new true option from #3
    - question: `IEEE 488について正しいのはどれですか？ A. 最大15台の機器 B. 通信に光ファイバーを必須とする C. 家庭用の動画圧縮規格` → `IEEE 488について正しいのはどれですか？ A. 家庭用の動画圧縮規格 B. 後継規格への移行が進んでいる C. 通信に光ファイバーを必須とする`
    - gold: `A|最大15台の機器` → `B|後継規格への移行が進んでいる`
    - evidence: `IEEE 488#2` → `IEEE 488#3`
- **b3_sc07** (summary-choice) — fixed — true option duplicated tf14 (winner); new true option from #2, distractors contradicted by #1/#3
    - question: `2017 FIFA U-17ワールドカップについて正しいのはどれですか？ A. イングランドが初優勝 B. 開催地はブラジル C. アルゼンチンが優勝` → `2017 FIFA U-17ワールドカップについて正しいのはどれですか？ A. 開催国はインド B. イングランドは準優勝だった C. 2015年に開催された`
    - gold: `A|イングランドが初優勝` → `A|開催国はインド`
    - evidence: `2017 FIFA U-17ワールドカップ#3` → `2017 FIFA U-17ワールドカップ#2`
- **b3_sc08** (summary-choice) — fixed — distractor 海水を貯める implausible for a river dam; replaced by 北陸電力 (contradicted by #2: 関西電力); letter moved
    - question: `赤尾ダムについて正しいのはどれですか？ A. 重力式コンクリートダム B. 高さは92メートル C. 海水を貯める` → `赤尾ダムについて正しいのはどれですか？ A. 北陸電力の発電用ダム B. 重力式コンクリートダム C. 高さは92メートル`
    - gold: `A|重力式コンクリートダム` → `B|重力式コンクリートダム`
- **b3_sc09** (summary-choice) — fixed — letter bias (all golds A); options reordered
    - question: `沐浴剤について正しいのはどれですか？ A. 洗い流す必要がない B. 肌の保湿が主目的 C. 石鹸より洗浄力が強い` → `沐浴剤について正しいのはどれですか？ A. 肌の保湿が主目的 B. 石鹸より洗浄力が強い C. 洗い流す必要がない`
    - gold: `A|洗い流す必要がない` → `C|洗い流す必要がない`
- **b3_sc10** (summary-choice) — fixed — true option a fragment (1.54倍の光, now the tf16 gold); B 「木星より近い恒星」 meaningless; new true option from #1, C contradicted by #2
    - question: `TOI-2285 bについて正しいのはどれですか？ A. 1.54倍の光 B. 木星より近い恒星 C. 公転周期は約270日` → `TOI-2285 bについて正しいのはどれですか？ A. ハビタブルゾーンのすぐ外側を回る B. 公転周期は約270日 C. 地球より少ない光を受ける`
    - gold: `A|1.54倍の光` → `A|ハビタブルゾーンのすぐ外側を回る`
    - evidence: `TOI-2285 b#2` → `TOI-2285 b#1`
- **b3_uk01** (unans-kind) — fixed — 「このデータ構造」 had no antecedent; subject named
    - question: `このデータ構造の平均探索計算量は何ですか？` → `ハッシュテーブルの平均的な探索の計算量はどれくらいですか？`
- **b3_uk02** (unans-kind) — valid — ok: dropz occurs only in CUBE JUICE#3; no founding year anywhere
- **b3_uk03** (unans-kind) — fixed — 「採用されたハッシュ関数」 presupposes one specific function (ill-posed for a data structure in general); now asks collision resolution (衝突/チェイン/オープンアドレス absent from both corpora)
    - question: `ハッシュ テーブルで採用されたハッシュ関数の名称は何ですか？` → `ハッシュ テーブルでキーが衝突したときの代表的な解決法は何ですか？`
- **b3_uk04** (unans-kind) — fixed — 「この思想運動」 had no antecedent and used 最初 (unans tell); reworded
    - question: `この思想運動を最初に組織化した国はどこですか？` → `フェミニズムの運動はどの国で始まりましたか？`
- **b3_uk05** (unans-kind) — valid — ok: both S3000 sentences are roster stubs with no athlete count; no other article gives one (レバノン選手団 is also a bank2 unans subject)
- **b3_uk06** (unans-kind) — fixed — option A (日本で初公演, 1984年) is odd for a Japanese artist who debuted in 2002 (contradicted by inference, so not 'undecidable'); replaced
    - question: `CUBE JUICEについて正しいのはどれですか？ A. 日本で初公演した年は1984年 B. 映画主題歌を担当した年は2010年 C. 公式アプリを公開した年は2012年` → `CUBE JUICEについて正しいのはどれですか？ A. 2010年に解散した B. 映画主題歌を担当した年は2010年 C. 公式アプリを公開した年は2012年`
- **b3_uk07** (unans-kind) — valid — ok: no 来日/日本 performance in either corpus (uses 初めて, a mild unans tell)
- **b3_uk08** (unans-kind) — fixed — 「開催国と優勝国が記されているこの大会」 refers to the text itself; reworded like tf14
    - question: `開催国と優勝国が記されているこの大会の決勝スコアは何対何でしたか？` → `インドでの開催が承認された大会で、決勝のスコアは何対何でしたか？`
- **b3_uk09** (unans-kind) — valid — ok: 閉店 absent; #1 says only かつて存在した
- **b3_uk10** (unans-kind) — valid — ok: #5 gives only 2023年2月 (announcement), no release date
- **b3_uk11** (unans-kind) — fixed — sunset time depends on the date (ill-posed); now asks the origin of the name (由来 absent from the 重山 article)
    - question: `重山の山頂から見える日の入り時刻は何時ですか？` → `重山という名前の由来は何ですか？`
- **b3_uk12** (unans-kind) — valid — ok: none of the three options is stated
- **b3_uk13** (unans-kind) — fixed — power consumption of 'IEEE 488 devices' is device-dependent (ill-posed); now asks the maximum cable length (absent)
    - question: `IEEE 488機器の消費電力は何ワットですか？` → `IEEE 488のケーブルは最長何メートルまで延ばせますか？`
- **b3_uk14** (unans-kind) — valid — ok: 県社 stated, year absent (水戸東照宮/御祖神社 are other 県社 without years)
- **b3_uk15** (unans-kind) — fixed — named no year/subject (「U-17大会とU-20大会」), and the asked count (24 teams) is equal for both in reality; now asks attendance, identified as in the answerable compares
    - question: `U-17大会とU-20大会のうち、参加国数が多かったのはどちらですか？` → `インドで開かれたU-17ワールドカップと韓国で開かれたU-20ワールドカップのうち、観客の総数が多かったのはどちらですか？`
    - evidence: `2017 FIFA U-17ワールドカップ#3;2017 FIFA U-17ワールドカップ#4` → `2017 FIFA U-17ワールドカップ#2;2017 FIFA U-17ワールドカップ#4`
