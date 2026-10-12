# Audit of bank 4 (bank4.tsv, adversarial unanswerable)

Auditor: Claude (Opus 5.5), 2026-10-12. Inputs: `bank2-author/out/bank4.tsv` (40 items ADV-001..040, codex gpt-6-luna, which saw only
the corpus and never Vera code), the author's `check4.py` / `check4.txt` / `README4.md`, and the corpus `S300_fulllead.jsonl`.
No Vera reader, loom or other Vera system has read the bank; `vera-impl/hidden` was not opened; no network.

Rules applied to every item (the request): (1) the asked fact is absent from the WHOLE corpus — all 592 sentences / 300 leads were
searched for the asked relation (keywords, units, paraphrases: 母, 球場/スタジアム/会場, 開業/開園/完成, 州都/の州, 容量/収容, 世帯, 郵便,
幅/幅員, 登山/全長, 馬力/PS/kW/キロワット, 公開/リリース, 始ま/開始, 色, マスコット, …) and any sentence that answers it, in any
article, makes the item answerable → drop; (2) the subject surface occurs verbatim in a cited evidence sentence; (3) the question
is natural Japanese and genuinely tempting (the evidence sentence sits next to the asked fact); (4) the c) distractor occurs in the
corpus and is NOT a correct answer (also not the real-world answer); (5) no negation tricks — one-word qualifiers that turn a
stated fact into an unstated one (「固有名」, 「実測」, 「番地まで」) are treated as the same trick; (6) ≥ 8 items per kind.
Also: no repeat of an unanswerable question of bank2 / bank3 (those banks have been read by Vera systems).

**Corpus identity.** The author's `S300_fulllead.jsonl` (sha256 `d987fdee…`) is byte-identical to `experiments/line3/data/S300_fulllead.jsonl`
(the bank3 corpus). It is **not** byte-identical to `bank2/data/fulllead_sents.jsonl` (sha256 `45efdaed…`) — that file is the
sentence-level split of the same corpus: verified that the 592 sentences, concatenated per title, equal the 300 lead texts exactly,
and that every `source` is `title#i` with i 0-based over the 「。」 split. The author's evidence convention (0-based index of
`text.split("。")`) is the same, so evidence ids needed no format change.

## Counts

| kind | authored | valid | fixed | dropped | kept |
|---|---|---|---|---|---|
| near-fact | 10 | 2 | 6 | 2 | 8 |
| same-slot | 10 | 9 | 1 | 0 | 10 |
| numeric | 10 | 2 | 6 | 2 | 8 |
| entity-swap | 10 | 0 | 9 | 1 | 9 |
| total | 40 | 13 | 22 | 5 | 35 |

## Main findings

1. **Absence holds.** For all 40 asked facts no sentence of the corpus answers them (searched per relation, all articles). The
   drops are for the other rules, not for an answer found elsewhere.
2. **Two items are answerable by inference / by the stated fact under a one-word qualifier (dropped).** ADV-002: the guitarist slot
   of #0 is an extraction blank, and #1-#2 leave ベリー as the only member without a role, succeeded by ホロヴィッツ — ベリー is
   inferable and is the real answer. ADV-003 (「母親の固有名」) and ADV-024 (「2020年の実測人口」) are answered by the corpus
   (カナン人シェアの娘; 23万人, 2020年投影人口) except for the qualifier — the qualifier trick that rule 5 excludes.
3. **One distractor is the real answer (dropped).** ADV-032: 北越急行's head office is in fact in 南魚沼市六日町, the c) value;
   only 「番地まで」 kept it unanswerable.
4. **Two items repeated bank2 unanswerables (fixed, not dropped).** ADV-025 「赤尾ダムの総貯水容量は何立方メートルですか」 is verbatim
   bank2 **R2-U003**, which is in `loom/tasks_bank2.jsonl` and has been run; ADV-005 (大邱FCの本拠地スタジアム名) repeats bank2
   **UF-010**. Both were re-asked as a different absent fact of the same sentence (堤頂長 with the stated height 29.2メートル as trap;
   マスコット with the corpus's only mascot, CUBE JUICE's 「BAN BAN」, as a cross-article trap).
5. **Evidence pointed at the subject sentence, not at the tempting one (5 fixes).** For ADV-004/007/025/026/027 the facts the notes
   describe (and the c) value) are in a neighbouring sentence that lacks the subject; that sentence was added as a second id.
6. **All entity-swap questions used meta phrasing** (「〜の説明に出る」「〜として出る」「〜として記された」) — reworded into natural
   questions that keep the bridging context (「川原石駅を運営するJR西日本は…」).
7. **Some c) distractors were not plausible answers** (a phrase for a postal code, 「15台程度」 for kW): replaced by corpus values of
   the right type from other articles (〒771-1505, 3万2,500キロワット). ADV-012 (液体の水) and ADV-015 (制定日) keep weak c) values;
   their temptation is the adjacent sentence itself.
8. **Outside knowledge.** Corpus-unanswerable is not world-unanswerable: 9 of the 35 kept items are answerable from a strong model's
   own knowledge (12 more partly) (ChatGPT's release date, Mumbai's state, Valladolid, JR West's head office, …). This only matters for the
   `no_tools` / `free_text` controls; the column below gives the auditor's estimate.
9. ADV-029 duplicated ADV-028 (same sentence, same relation, 男子/女子 swapped): dropped. ADV-018/019 keep the same pattern on two
   different articles/lines; ADV-018 and ADV-031 share the article 川原石駅 but ask different facts.

## Re-check

`check_bank4.py` → `check.txt`: **35 rows, 0 errors** (corpus split identity; header; ids; kinds ≥ 8; gold empty; question ends in 。
and has no negation; subject in the question and in a cited sentence; evidence resolves, ≤ 2 ids of one article; c) occurs in the
corpus; the loom task file has 4 rows per item with the tasks_bank2 schema and no gold key). INFO: ADV-037's c) 2022年 also occurs in
the question (kept: it is the only year next to the circuit). The author's own `check4.py` / `check4.txt` are copied unchanged (they
check the original 40 rows).

## Per-item decisions

"outside knowledge" = could a strong LLM answer from memory (auditor's estimate; relevant to no_tools / free_text only).

| id | kind | decision | reason | outside knowledge |
|---|---|---|---|---|
| ADV-001 | near-fact | valid | year 2002 stated, month/day nowhere (only 長尾伸一's birth date 1975年1月22日, the c) trap) | no |
| ADV-002 | near-fact | dropped | inferable: #0 leaves the guitarist slot empty, #1-#2 name ベリー as the one member with no stated role and ホロヴィッツ as his successor; ベリー is also the real answer (John Berry). The gap is an extraction artefact, not an absent fact | - |
| ADV-003 | near-fact | dropped | qualifier trick: 「オナンの母親は誰」 is answered by #1 (カナン人シェアの娘); only 「固有名」 makes it unanswerable, and Bath-shua literally means "daughter of Shua", so the corpus phrase is arguably the name | - |
| ADV-004 | near-fact | fixed | evidence pointed at #0 (「ギリシア神話の人物」); the father (#2) and ガイア (#3) that notes a) describe are in #2/#3; #3 holds the subject | no (usually unnamed) |
| ADV-005 | near-fact | fixed | the original question (本拠地スタジアムの正式名称) repeats bank2 UF-010 (「大邱FCのホームスタジアムの名称は何ですか」): replaced by another absent club fact; the only mascot in the corpus is CUBE JUICE's 「BAN BAN」 (cross-article distractor) | partial |
| ADV-006 | near-fact | fixed | question had no subject (「大会が行われた球場」); subject added | partial |
| ADV-007 | near-fact | fixed | notes a) cite インド (#1), evidence only #0; #1 added | yes (Salt Lake Stadium) |
| ADV-008 | near-fact | fixed | 「何日」 is ambiguous (day of month / how many days) and the title had lost 「!!」; asks the full date | no |
| ADV-009 | near-fact | valid | only the district ペシオンヴィル; no building name anywhere (the only other embassy, 在キューバ, has none either) | no |
| ADV-010 | near-fact | fixed | question lacked the championship (「マダガスカル選手団が出場した水泳競技の施設名」); full subject restored | partial |
| ADV-011 | same-slot | valid | area + population in the same slot sentence; 世帯 occurs only for 土成町郡 (78世帯), another place | no |
| ADV-012 | same-slot | valid | water layer mentioned conditionally, no thickness or any km figure for the planet; c) weak (not a number) but present and wrong | no |
| ADV-013 | same-slot | valid | #2 gives the daughter/wife form only; no son form anywhere | no |
| ADV-014 | same-slot | valid | largest island named (#4), #5 says it is inhabited but gives no population: strong temptation | partial |
| ADV-015 | same-slot | valid | only the adoption date; no colour or colour count anywhere; c) weak | yes |
| ADV-016 | same-slot | valid | 大学院生 is the status, not a field; no 専攻 anywhere for this college | no |
| ADV-017 | same-slot | valid | stadium named as the club's home; no 収容 (capacity) anywhere in the corpus | partial |
| ADV-018 | same-slot | valid | station of the line; no station count for 呉線; c) JR-Y13 may be misread as 13 | partial |
| ADV-019 | same-slot | valid | same pattern as ADV-018 on another line/article; c) OR08 may be misread as 8 | partial |
| ADV-020 | same-slot | fixed | question unnatural (「2024年現在の行政地名の郵便番号」), subject 行政地名 → 東雲西町; c) 東雲西町一丁… was not a postal code: replaced by 〒771-1505 (土成町郡#2, another place) | partial |
| ADV-021 | numeric | fixed | 「橋面幅」 is not the usual term; 幅員 | no |
| ADV-022 | numeric | valid | elevation stated; no trail / 登山道 / 全長 anywhere | no |
| ADV-023 | numeric | fixed | 「岡崎建設製ストーブ」 unnatural; subject 注文生産体制 → 岡崎建設 (+#0, which holds it); c) 15台程度 is not a kW value: replaced by 3万2,500キロワット (赤尾ダム#2, the only kW figure in the corpus) | no |
| ADV-024 | numeric | dropped | qualifier trick: the 2020 population IS stated (23万人, 2020年投影人口, #2); only 「実測」 vs 投影 separates it, a one-word modifier like a negation; grading 「23万人（投影）」 would be contested | - |
| ADV-025 | numeric | fixed | the original question (総貯水容量) is VERBATIM bank2 R2-U003, which is in loom/tasks_bank2.jsonl and has been run: replaced by another absent dam dimension (堤頂長, searched: no 堤頂/堤長 in the corpus) whose tempting wrong answer is the stated height; c) 29.2メートル is in #1: added | partial |
| ADV-026 | numeric | fixed | notes a) cite 3,799cc (#1), evidence only #0; #1 added | yes (version-dependent) |
| ADV-027 | numeric | fixed | 「数河高原地帯の東西幅」 smoothed; c) 13 is in #1: added | no |
| ADV-028 | numeric | fixed | question had no antecedent (「男子競技に出場した選手」 of which event?); event added | no |
| ADV-029 | numeric | dropped | duplicate of ADV-028: same sentence, same relation (players per event), same distractor type; only 男子/女子 differs | - |
| ADV-030 | numeric | valid | the sub-county is named as seat; only county populations (20万人 2014 / 23万人 2020 projection) exist: strong trap | no |
| ADV-031 | entity-swap | fixed | meta phrasing (「川原石駅の説明に出る」「番地まで」) → natural | yes (大阪市北区) |
| ADV-032 | entity-swap | dropped | distractor is the real answer: 北越急行 has its head office in 新潟県南魚沼市六日町; only 「番地まで」 keeps it unanswerable (qualifier trick), violating rule 4 | - |
| ADV-033 | entity-swap | fixed | meta phrasing (「〜の製造者として出る」) → natural | partial |
| ADV-034 | entity-swap | fixed | meta phrasing (「接続先として出る」) → natural | yes (マハーラーシュトラ州) |
| ADV-035 | entity-swap | fixed | meta phrasing (「LaMDAの記述に出る」) → natural | yes (2022-11-30) |
| ADV-036 | entity-swap | fixed | meta phrasing (「大会会場として記された」) → natural | partial |
| ADV-037 | entity-swap | fixed | meta phrasing (「会場として出る」) → natural | yes (1999) |
| ADV-038 | entity-swap | fixed | meta phrasing (「ニューヨーク市の文化に影響した」, not what #2 says) → plain question | partial (1920年代; no single year) |
| ADV-039 | entity-swap | fixed | meta phrasing (「キャンパス所在地として出る」) → natural | yes (バリャドリッド) |
| ADV-040 | entity-swap | fixed | meta phrasing (「運休理由として出る」) → natural | yes (2014; start date contested) |

## Fixes (old → new)

- **ADV-004**
    - evidence: `ニュクティーモス#0` → `ニュクティーモス#2;ニュクティーモス#3`
- **ADV-005**
    - question: `大邱FCが本拠地とするスタジアムの正式名称は何ですか。` → `大邱FCのマスコットの名前は何ですか。`
    - notes: `a) 文は本拠地を大邱広域市とする。; b) 問う競技場名は全300リード文にない。; c) 大邱広域市` → `a) 文は大邱FCが大邱広域市を本拠地とするサッカークラブであると記す。; b) 問うマスコット名は大邱FCの記事になく、コーパス中のマスコット名は別記事（CUBE JUICE#1）のものだけである。; c) BAN BAN`
- **ADV-006**
    - question: `大会が行われた球場の名称は何ですか。` → `2005年アジア野球選手権大会が行われた球場の名称は何ですか。`
- **ADV-007**
    - evidence: `2017 FIFA U-17ワールドカップ#0` → `2017 FIFA U-17ワールドカップ#0;2017 FIFA U-17ワールドカップ#1`
- **ADV-008**
    - question: `YAMAMORIラジオの初回放送日は何日ですか。` → `YAMAMORIラジオ!!の初回放送日は何年何月何日ですか。`
- **ADV-010**
    - question: `マダガスカル選手団が出場した水泳競技の施設名は何ですか。` → `2025年世界水泳選手権マダガスカル選手団が出場した競技会場の名称は何ですか。`
- **ADV-020**
    - subject: `行政地名` → `東雲西町`
    - question: `東雲西町の2024年現在の行政地名の郵便番号は何ですか。` → `東雲西町の郵便番号は何ですか。`
    - notes: `a) 文は2024年現在の行政地名が一丁から四丁であると示す。; b) 問う郵便番号は全300リード文に書かれていない。; c) 東雲西町一丁から東雲西町四丁` → `a) 文は2024年現在の行政地名が東雲西町一丁から東雲西町四丁であると示す。; b) 問う郵便番号は東雲西町の記事になく、他記事に別の地名の郵便番号がある。; c) 〒771-1505`
- **ADV-021**
    - question: `奥多摩橋の橋面幅は何メートルですか。` → `奥多摩橋の幅員は何メートルですか。`
- **ADV-023**
    - subject: `注文生産体制` → `岡崎建設`
    - question: `岡崎建設製ストーブ1台の最大出力は何キロワットですか。` → `岡崎建設が製作する薪ストーブ1台の最大出力は何キロワットですか。`
    - evidence: `岡崎建設#2` → `岡崎建設#0;岡崎建設#2`
    - notes: `a) 文は2013年当時に注文生産体制となり、年間15台程度を製作していたと記す。; b) 問うストーブ1台の出力は書かれていない。; c) 15台程度` → `a) 文は岡崎建設が薪ストーブメーカーであること、2013年当時に注文生産体制で年間15台程度を製作していたことを記す。; b) 問うストーブ1台の出力はどこにも書かれていない。; c) 3万2,500キロワット`
- **ADV-025**
    - question: `赤尾ダムの総貯水容量は何立方メートルですか。` → `赤尾ダムの堤頂長は何メートルですか。`
    - evidence: `赤尾ダム#0` → `赤尾ダム#0;赤尾ダム#1`
    - notes: `a) 文はダムの高さ29.2メートルと最大出力3万2,500キロワットを記す。; b) 問う貯水容量は載っていない。; c) 29.2メートル` → `a) 文は赤尾ダムが庄川に建設されたダムで、高さ29.2メートルの重力式コンクリートダムであると記す。; b) 問う堤頂長はどこにも書かれていない。; c) 29.2メートル`
- **ADV-026**
    - evidence: `日産・VR38DETT#0` → `日産・VR38DETT#0;日産・VR38DETT#1`
- **ADV-027**
    - question: `数河高原地帯の東西幅は何キロメートルですか。` → `数河高原の東西の幅は何キロメートルですか。`
    - evidence: `数河高原#0` → `数河高原#0;数河高原#1`
- **ADV-028**
    - question: `男子競技に出場した選手の総数は何人ですか。` → `2022年アジア競技大会のビーチバレーボール男子競技に出場した選手は全部で何人ですか。`
- **ADV-031**
    - question: `川原石駅の説明に出るJR西日本の本社住所は番地までどこですか。` → `川原石駅を運営するJR西日本は、本社をどこに置いていますか。`
- **ADV-033**
    - question: `レベリオン・R13の製造者として出るオレカの本社がある市区町村はどこですか。` → `レベリオン・R13を製造したオレカは、フランスのどの市町村に本社を置いていますか。`
- **ADV-034**
    - question: `プラガティ急行の接続先として出るムンバイが属する州はどこですか。` → `プラガティ急行が結ぶムンバイは、インドのどの州にありますか。`
- **ADV-035**
    - question: `LaMDAの記述に出るChatGPTが初めて一般公開された年月日はいつですか。` → `OpenAIのChatGPTが初めて一般公開されたのは何年何月何日ですか。`
- **ADV-036**
    - question: `大会会場として記された有明テニスの森公園の開園年月日はいつですか。` → `2011年楽天ジャパン・オープン・テニス選手権の会場となった有明テニスの森公園は、いつ開園しましたか。`
- **ADV-037**
    - question: `2022年のバレンシアグランプリの会場として出るリカルド・トルモ・サーキットは何年に開業しましたか。` → `2022年のバレンシアグランプリが開催されたリカルド・トルモ・サーキットは、何年に開業しましたか。`
- **ADV-038**
    - question: `ニューヨーク市の文化に影響したハーレム・ルネサンスは何年に始まりましたか。` → `ハーレム・ルネサンスは何年に始まりましたか。`
- **ADV-039**
    - question: `IE大学のキャンパス所在地として出るカスティーリャ・イ・レオン州の州都はどこですか。` → `IE大学のキャンパスがあるカスティーリャ・イ・レオン州の州都はどこですか。`
- **ADV-040**
    - question: `アウディーイウカ市電の運休理由として出るウクライナ東部紛争は何年何月何日に始まりましたか。` → `アウディーイウカ市電の運行停止の原因となったウクライナ東部紛争は、いつ始まりましたか。`
