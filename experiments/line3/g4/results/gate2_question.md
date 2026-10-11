# G4-d2: gate G-2, the per-question criterion L-G4-32 (arm A, saved snapshots, no rebuild)

69 intra2 questions; foundation on, level mid, order forward; tiers RUN / WORD / CHAR; each at its entry step e(q) and at step 300.
Script: `experiments/line3/g4/gate2_question.py`.  Snapshots: `/Users/motonisihikoudai/Projects/vera-impl/cache/g4_stack_A/found-a2083d453637__mid__forward` (every state identity recomputed from the raw bytes).

Verdicts: **reachable** = a gold unit (T9 scorer rule, a unit of the space) is seated in a cross that holds a question unit (seed or seat; the gold's own cross included).  **closed-before** = not reachable, and every cross of a question unit is closed at a step strictly before e(q).  **未着** = no unit of the space spells a gold alternative.  **other:closed_at_entry** = every question-unit cross is closed but one of them at e(q) or later (at the gold article's own step); **other:open_no_cooccurrence** = some question-unit cross is open and the gold is not in any holding cross; **other:no_question_unit** = no question unit is in the space.

## Summary per tier (verdict counts of 69 questions)

### at e(q)

| tier | reachable | closed-before | 未着 | other | other:closed_at_entry | other:open_no_cooccurrence | other:no_question_unit | closed-before share | closed-before with true later co-occurrence (left_after) |
|---|---|---|---|---|---|---|---|---|---|
| RUN | 40 | 0 | 19 | 10 | 3 | 7 | 0 | 0.0 % | 0 of 0 |
| WORD | 17 | 0 | 51 | 1 | 0 | 1 | 0 | 0.0 % | 0 of 0 |
| CHAR | 1 | 0 | 68 | 0 | 0 | 0 | 0 | 0.0 % | 0 of 0 |

### at step 300

| tier | reachable | closed-before | 未着 | other | other:closed_at_entry | other:open_no_cooccurrence | other:no_question_unit | closed-before share | closed-before with true later co-occurrence (left_after) |
|---|---|---|---|---|---|---|---|---|---|
| RUN | 40 | 0 | 19 | 10 | 3 | 7 | 0 | 0.0 % | 0 of 0 |
| WORD | 17 | 0 | 51 | 1 | 0 | 1 | 0 | 0.0 % | 0 of 0 |
| CHAR | 1 | 0 | 68 | 0 | 0 | 0 | 0 | 0.0 % | 0 of 0 |

## The stop condition (more than half of the questions closed-before)

| tier | at e(q): closed-before | share | stop (> 50 %) | closed-before + closed_at_entry | share | at 300: closed-before | share | stop (> 50 %) | closed-before + closed_at_entry | share |
|---|---|---|---|---|---|---|---|---|---|---|
| RUN | 0 | 0.0 % | no | 3 | 4.3 % | 0 | 0.0 % | no | 3 | 4.3 % |
| WORD | 0 | 0.0 % | no | 0 | 0.0 % | 0 | 0.0 % | no | 0 | 0.0 % |
| CHAR | 0 | 0.0 % | no | 0 | 0.0 % | 0 | 0.0 % | no | 0 | 0.0 % |

The share is of all 69 questions; the two extra columns widen "before" to "at or before the gold article's own step" (every question-unit cross closed, the gold in no holding cross).

Across tiers (a question counts once): reachable in at least one tier / no tier reachable and every tier that has a gold unit is closed-before / the rest.

| at | reachable in some tier | blocked (closed-before in every tier with a gold unit) | 未着 in every tier | other |
|---|---|---|---|---|
| e(q) | 41 | 0 | 18 | 10 |
| 300 | 41 | 0 | 18 | 10 |

## Question-unit crosses closed AT BIRTH

Distinct question-unit crosses (a unit asked by several questions counts once) against every cross of the tier at the same step.

| tier | step | question-unit crosses | closed | closed at birth | share closed | share at birth | all crosses of the tier | closed | at birth |
|---|---|---|---|---|---|---|---|---|---|
| RUN | e(q) | 181 | 86 | 79 | 47.5 % | 43.6 % | - | - | - |
| WORD | e(q) | 342 | 272 | 221 | 79.5 % | 64.6 % | - | - | - |
| CHAR | e(q) | 724 | 667 | 610 | 92.1 % | 84.3 % | - | - | - |
| RUN | 300 | 183 | 94 | 80 | 51.4 % | 43.7 % | 3653 | 58.0 % | 54.9 % |
| WORD | 300 | 287 | 231 | 190 | 80.5 % | 66.2 % | 3557 | 78.1 % | 73.7 % |
| CHAR | 300 | 365 | 338 | 300 | 92.6 % | 82.2 % | 1358 | 80.2 % | 72.7 % |

Question-unit crosses at e(q), with multiplicity (one per question and unit): RUN 85 of 199 at birth; WORD 243 of 380 at birth; CHAR 676 of 802 at birth

The baseline at e(q) (all crosses of the tier at that step) is in `gate2_A.md` per measured step; at step 300 it is in the columns on the right.

## Diagnostics

**未着 split.**  `spans` = the gold alternative is spelled by ADJACENT kept units of the evidence sentence in this tier (the tier cut the gold into several units, e.g. ハッシュ + 表, so no one unit spells it); `absent` = not even the concatenation of the kept units of the evidence sentence spells it (it holds a dropped function unit or a character the tier does not keep).

| tier | 未着 | spans (cut into adjacent units) | absent |
|---|---|---|---|
| RUN | 19 | 15 | 4 |
| WORD | 51 | 42 | 9 |
| CHAR | 68 | 60 | 8 |

**reachable, by route and by the evidence sentence** (at e(q); the route is not exclusive).  `evidence unit` = a gold unit that sits in the evidence sentence itself is seated in a holding cross (otherwise the reach is through another occurrence of a gold-spelling unit).

| tier | reachable | via the gold's own cross holding a question unit | gold seated in a question-unit cross | gold seated in another holding cross | reachable through an evidence-sentence gold unit | not through one |
|---|---|---|---|---|---|---|
| RUN | 40 | 37 | 31 | 29 | 40 | 0 |
| WORD | 17 | 17 | 10 | 12 | 17 | 0 |
| CHAR | 1 | 0 | 0 | 1 | 1 | 0 |

**What closure cost** (at e(q); questions that have a gold unit in the tier).  `gold left` = a question-unit cross closed and recorded a gold unit as left (the gold shares a sentence with its seed, but the cross was closed: `left_in_step` the same step, `left_after` later).  `still reachable` = such a question is nevertheless reachable (another holding cross seats the gold).  `no question-unit cross seats it` = reachable, yet no question-unit cross itself holds a gold unit.  `subject born at e(q)` = a question unit whose cross was opened at e(q) (the article's own words): its cross cannot have closed before e(q).

| tier | questions with a gold unit | gold left in a closed question-unit cross | of which still reachable | reachable, no question-unit cross seats it | with a question-unit cross born at e(q) |
|---|---|---|---|---|---|
| RUN | 50 | 11 | 11 | 9 | 50 |
| WORD | 18 | 16 | 16 | 7 | 18 |
| CHAR | 1 | 1 | 1 | 1 | 1 |

**The rows that are neither reachable nor 未着** (at e(q); the same at 300): the state of each question-unit cross and the best way a gold unit stands to any of them (`cooccur`: seated, left_in_step = recorded in the step the cross closed, left_after = recorded after it closed, none = never shares a sentence with the seed).

| id | tier | verdict | gold units | question-unit crosses | best cooccur |
|---|---|---|---|---|---|
| I2-011 | RUN | other:open_no_cooccurrence | 改称 | 改名:open/5 意味:C@21b/13 | none |
| I2-011 | WORD | other:open_no_cooccurrence | 改称 | 改名:open/6 意味:C@21b/13 語:C@29b/9 | none |
| I2-020 | RUN | other:closed_at_entry | 17代目 | 善五郎:C@60b/13 | none |
| I2-039 | RUN | other:open_no_cooccurrence | 愛知県出身/愛知県名古屋市中川区4丁目/愛知県名古屋市瑞穂区 | 寅ヤス:open/5 | none |
| I2-043 | RUN | other:open_no_cooccurrence | 大和町宮床 | 宮床村:open/7 町:C@103/18 | none |
| R2-I002 | RUN | other:open_no_cooccurrence | 鳳珠郡能登町 | 内浦町:open/5 | none |
| R2-I003 | RUN | other:open_no_cooccurrence | 中播磨県民センター | 市川町:open/6 | none |
| R2-I004 | RUN | other:open_no_cooccurrence | 落語協会所属 | 風藤松原:open/6 | none |
| R2-I007 | RUN | other:closed_at_entry | 日本海側気候 | 数河高原:C@121b/7 | none |
| R2-I012 | RUN | other:closed_at_entry | 人口2188人 | コィンスコヴォラ:C@82b/8 | none |
| R2-I019 | RUN | other:open_no_cooccurrence | 年間15台程度/最大15台 | 岡崎建設:open/9 薪ストーブ:open/9 | none |

## Gold units in the space

| tier | at | questions with a gold unit | with an exact gold unit (normalised text equals an alternative) | median gold units |
|---|---|---|---|---|
| RUN | e(q) | 50 | 39 | 1 |
| WORD | e(q) | 18 | 18 | 0 |
| CHAR | e(q) | 1 | 1 | 0 |
| RUN | 300 | 50 | 39 | 1 |
| WORD | 300 | 18 | 18 | 0 |
| CHAR | 300 | 1 | 1 | 0 |

## The 69 questions

`R` reachable, `CB` closed-before, `U` 未着, `O:entry` other:closed_at_entry, `O:open` other:open_no_cooccurrence, `O:noQ` other:no_question_unit.  Columns `e` / `300`.

| id | e(q) | gold | RUN e | RUN 300 | WORD e | WORD 300 | CHAR e | CHAR 300 |
|---|---|---|---|---|---|---|---|---|
| I2-001 | 1 | ハッシュ表 | U | U | U | U | U | U |
| I2-002 | 2 | 連結成分 | R | R | U | U | U | U |
| I2-003 | 8 | JR-Y13 | R | R | U | U | U | U |
| I2-004 | 9 | Y17 | R | R | U | U | U | U |
| I2-005 | 12 | JA16 | R | R | U | U | U | U |
| I2-006 | 19 | OR08 | R | R | U | U | U | U |
| I2-007 | 18 | 路線の廃止 | U | U | U | U | U | U |
| I2-008 | 10 | カール・マルクス | U | U | U | U | U | U |
| I2-009 | 23 | ボーカル | R | R | R | R | U | U |
| I2-010 | 24 | 3位 | R | R | U | U | U | U |
| I2-011 | 30 | 改称 | O:open | O:open | O:open | O:open | U | U |
| I2-012 | 33 | 深川八幡宮 | R | R | U | U | U | U |
| I2-013 | 44 | 県社 | R | R | U | U | U | U |
| I2-014 | 44 | 九曜紋 | R | R | U | U | U | U |
| I2-015 | 45 | さいたま市見沼区 | U | U | U | U | U | U |
| I2-016 | 48 | 地上から | U | U | U | U | U | U |
| I2-017 | 57 | GPIB | R | R | R | R | U | U |
| I2-018 | 58 | 権現さん | U | U | U | U | U | U |
| I2-019 | 59 | BAN BAN | U | U | U | U | U | U |
| I2-020 | 60 | 17代目 | O:entry | O:entry | U | U | U | U |
| I2-021 | 60 | 西村姓\|西村 | R | R | R | R | U | U |
| I2-022 | 60 | 永樂 | R | R | U | U | U | U |
| I2-023 | 61 | 富国強兵 | R | R | U | U | U | U |
| I2-024 | 65 | 集配普通郵便局 | R | R | U | U | U | U |
| I2-025 | 66 | 青 | R | R | R | R | R | R |
| I2-026 | 70 | アワド語 | U | U | U | U | U | U |
| I2-027 | 75 | ゴゴプラッタ | R | R | R | R | U | U |
| I2-028 | 79 | 大曲輪遺跡 | R | R | U | U | U | U |
| I2-029 | 88 | 和歌山千葉線 | R | R | U | U | U | U |
| I2-030 | 89 | 16柱 | R | R | U | U | U | U |
| I2-031 | 57 | USB\|イーサネット\|LXI | R | R | R | R | U | U |
| I2-032 | 105 | 製鋼所 | R | R | U | U | U | U |
| I2-033 | 107 | リュカーオーン | R | R | R | R | U | U |
| I2-034 | 142 | 1981年 | R | R | U | U | U | U |
| I2-035 | 145 | 黒パン\|ライパン | R | R | R | R | U | U |
| I2-036 | 148 | 1785年10月25日 | R | R | U | U | U | U |
| I2-037 | 106 | ムーラ | R | R | R | R | U | U |
| I2-038 | 106 | ソレローン島 | U | U | U | U | U | U |
| I2-039 | 169 | 愛知県 | O:open | O:open | U | U | U | U |
| I2-040 | 169 | トライデントデザイン専門学校 | U | U | U | U | U | U |
| I2-041 | 170 | キューバの太陽 | U | U | U | U | U | U |
| I2-042 | 173 | 新潟市西区 | R | R | U | U | U | U |
| I2-043 | 176 | 大和町 | O:open | O:open | U | U | U | U |
| I2-044 | 201 | 素朴な力強さ\|宗教色 | R | R | U | U | U | U |
| I2-045 | 261 | MtF | R | R | R | R | U | U |
| I2-046 | 294 | スタディオ・フリウーリ | U | U | U | U | U | U |
| I2-047 | 292 | 16の国 | U | U | U | U | U | U |
| I2-048 | 196 | イングランド | R | R | R | R | U | U |
| I2-050 | 273 | チューリング・テスト | U | U | U | U | U | U |
| R2-I001 | 53 | ホロヴィッツ | R | R | R | R | U | U |
| R2-I002 | 34 | 能登町 | O:open | O:open | U | U | U | U |
| R2-I003 | 43 | 中播磨県民センター | O:open | O:open | U | U | U | U |
| R2-I004 | 49 | 落語協会 | O:open | O:open | U | U | U | U |
| R2-I005 | 88 | 和歌山線 | R | R | U | U | U | U |
| R2-I006 | 106 | 120 m\|120 | R | R | R | R | U | U |
| R2-I007 | 121 | 日本海側気候\|日本海側 | O:entry | O:entry | U | U | U | U |
| R2-I008 | 157 | ウルトラプリニー式噴火 | U | U | U | U | U | U |
| R2-I009 | 158 | 3万2,500キロワット | U | U | U | U | U | U |
| R2-I010 | 89 | 波胡曽神 | R | R | U | U | U | U |
| R2-I011 | 77 | 丁斧掛け | U | U | U | U | U | U |
| R2-I012 | 82 | 2188人 | O:entry | O:entry | U | U | U | U |
| R2-I013 | 70 | ネパール | R | R | R | R | U | U |
| R2-I014 | 186 | 73,921人 | U | U | U | U | U | U |
| R2-I015 | 196 | イングランド | R | R | R | R | U | U |
| R2-I016 | 208 | BMX | R | R | R | R | U | U |
| R2-I017 | 99 | エタール・コホモロジー | U | U | R | R | U | U |
| R2-I018 | 250 | 20万人 | R | R | U | U | U | U |
| R2-I019 | 255 | 15台程度\|15台 | O:open | O:open | U | U | U | U |
| R2-I020 | 236 | 一方向のコンテンツ\|一方向 | R | R | U | U | U | U |

## Question-unit crosses at e(q) (RUN and WORD)

`unit:state/size`: state `open`, `C@s` closed at step s, `C@sb` closed at s = its birth; `+G` a gold unit is seated in it.

| id | gold units RUN / WORD | RUN question-unit crosses | WORD question-unit crosses |
|---|---|---|---|
| I2-001 | 0 / 0 | ハッシュテーブル:C@1b/11 | ハッシュ:C@1b/12 テーブル:C@1b/12 |
| I2-002 | 1 / 0 | 連結グラフ:open/9 極大:open/7+G 連結な:open/7+G 部分グラフ:open/7+G 呼:C@1b/11 | 連結:C@2b/13 グラフ:C@2b/13 極大:open/8 部分:open/8 |
| I2-003 | 1 / 0 | 川原石駅:C@8b/7 駅番号:open/2+G | 川原石:C@8b/7 駅:C@7b/7 番号:open/5 |
| I2-004 | 1 / 0 | 花園町駅:C@9b/7 駅番号:open/3+G | 花園町:C@9b/7 駅:C@7b/7 番号:open/6 |
| I2-005 | 1 / 0 | 海老津駅:C@12b/7 駅番号:open/4+G | 海老:C@12b/7 津:C@12b/7 駅:C@7b/7 番号:open/8 |
| I2-006 | 1 / 0 | 海浦駅:open/7 駅番号:open/5+G | 海:C@19b/11 浦:C@19b/11 駅:C@7b/7 番号:C@19/8 |
| I2-007 | 0 / 0 | 沢辺駅:C@18b/7 廃駅:open/6 | 沢辺:C@18b/8 駅:C@7b/7 廃:C@18b/7 もの:C@3b/10 |
| I2-008 | 0 / 0 | 唯物史観:open/8 唱:open/6 えた:open/6 | 唯物:C@10b/10 史観:C@10b/10 唱え:open/7 |
| I2-009 | 1 / 1 | ジーズ:open/11 担当:open/3+G | ビー・ジーズ:open/13 全員:open/4+G 共通:open/4+G 担当:open/4+G |
| I2-010 | 1 / 0 | ブリティッシュ:open/5 エアウェイズ:open/5 ヨーロッパ:open/11+G 規模:open/11+G | ブリティッシュ:open/6 エアウェイズ:open/6 ヨーロッパ:C@24b/8 規模:C@24b/8 |
| I2-011 | 1 / 1 | 改名:open/5 意味:C@21b/13 | 改名:open/6 意味:C@21b/13 語:C@29b/9 |
| I2-012 | 1 / 0 | 富岡八幡宮:open/4 通称:open/5+G 呼:C@1b/11 | 富岡:C@33b/7 八幡:C@33b/7 宮:C@33b/7 通称:C@33b/7 呼ば:C@15b/13 |
| I2-013 | 1 / 0 | 千葉神社:open/4 旧社格:open/2+G | 千葉:open/8 神社:C@33b/7 旧:open/4 社格:open/4 |
| I2-014 | 1 / 0 | 千葉神社:open/4 社紋:open/5+G | 千葉:open/8 神社:C@33b/7 社:C@44b/7 紋:open/6 |
| I2-015 | 0 / 0 | 七里村:open/4 地域:C@42b/8 | 村:C@45/10 地域:C@28b/7 現在:open/11 市:C@7b/7 区:C@9b/7 一部:open/20 |
| I2-016 | 0 / 0 | ヒルフィギュア:C@48b/13 ることを:C@48b/7 意識:C@48b/7 作:C@48b/7 | ヒル:C@48b/13 フィギュア:C@48b/16 こと:C@6/19 意識:C@48b/7 作ら:C@48b/7 い:C@7/19 |
| I2-017 | 1 / 1 | IEEE:C@57b/7 通称:C@57/17+G | IEEE:C@57b/11 488:C@57b/11 通称:C@33b/7 |
| I2-018 | 0 / 0 | 水戸東照宮:open/4 一般:open/7 呼:C@1b/11 | 水戸:open/9 東照:C@58b/9 宮:C@33b/7 一般:open/8 呼ば:C@15b/13 い:C@7/19 |
| I2-019 | 0 / 0 | CUBE:C@59b/7 JUICE:C@59b/7 マスコット:open/3 | CUBE:C@59b/7 JUICE:C@59b/7 マスコット:open/3 |
| I2-020 | 1 / 0 | 善五郎:C@60b/13 | 善五郎:C@60b/13 代:C@60b/10 目:open/4 |
| I2-021 | 1 / 1 | 善五郎:C@60b/13 初代:open/7+G 9代:open/7+G | 善五郎:C@60b/13 初代:C@60b/7+G 9:C@24b/8 代:C@60b/10 姓:C@55b/7 い:C@7/19 |
| I2-022 | 1 / 0 | 善五郎:C@60b/13 10代以降:C@60b/7+G | 善五郎:C@60b/13 10:C@3b/7 代:C@60b/10 以降:C@60b/7 姓:C@55b/7 い:C@7/19 |
| I2-023 | 1 / 0 | 博文館:open/4 時代風潮:C@61b/10+G 広:C@6b/11 | 博文:C@61b/7 館:C@61b/7 時代:C@61b/10 風潮:C@61b/10 広げ:C@6b/13 |
| I2-024 | 1 / 0 | 近江八幡郵便局:open/4 民営化前:open/3+G 分類:open/5+G 郵便局:open/4 | 近江八幡:open/10 郵便:C@65b/10 局:C@65b/10 民営:open/8 化:C@57b/9 前:C@12b/7 分類:C@65/8 |
| I2-025 | 2 / 2 | レッド:open/13 計画:C@66b/14 アメリカ:C@66b/14 | レッド:C@66b/13 計画:C@66b/9 アメリカ:C@38b/7 い:C@7/19 |
| I2-026 | 0 / 0 | アワディー:open/6 語:C@40b/7 | アワ:C@70b/7 ディー:C@70b/7 語:C@29b/9 |
| I2-027 | 1 / 1 | フットチョーク:open/6 ブラジリアン:open/9+G 柔術:open/9+G 呼:C@1b/11 | フット:C@75b/7 チョーク:C@48b/7 ブラジリアン:open/9+G 柔術:open/9+G 呼ば:C@15b/13 |
| I2-028 | 1 / 0 | 大曲輪貝塚:open/7 呼:C@1b/11 | 曲輪:C@79b/11 貝塚:C@79b/11 別名:C@75b/7 呼ば:C@15b/13 |
| I2-029 | 1 / 0 | 和歌山バス:open/8+G サウスウェーブ:open/9 号:open/9 案内:open/7+G | 和歌山:C@56b/7 バス:C@88b/13 サウス:open/15 ウェーブ:open/15 号:C@20b/7 案内:open/7 い:C@7/19 |
| I2-030 | 1 / 0 | 中之嶽神社:open/4 日本武尊:C@89b/8 祭神:open/2+G | 中:C@52/9 嶽:C@89b/7 神社:C@33b/7 日本:C@7b/7 武尊:C@89b/7 ほか:C@15b/14 祭神:open/6 柱:open/6 |
| I2-031 | 3 / 3 | IEEE:C@57b/7 後継規格:C@57b/7+G | IEEE:C@57b/11 488:C@57b/11 後継:open/12+G 規格:C@20b/7 通信:C@57b/9 方式:C@50b/8 使わ:C@3b/7 い:C@7/19 |
| I2-032 | 1 / 0 | 千里馬区域:open/6 千里馬運動:open/11+G 発祥:open/11+G 地:open/11+G | 千里:C@105b/8 馬:C@105b/8 区域:C@105/10 運動:C@6b/13 発祥:open/13 地:C@36b/7 施設:C@52b/7 |
| I2-033 | 1 / 1 | ニュクティーモス:C@107b/15 父:C@84b/7 | ニュクティーモス:C@107b/19 父:C@84b/7 王:C@44b/7 |
| I2-034 | 1 / 0 | サンゴーカメラ:C@142b/7 設立:open/5+G | サン:C@142b/13 ゴー:C@142b/13 カメラ:C@142b/13 年:C@17b/7 設立:open/11 |
| I2-035 | 2 / 1 | ライ:C@145b/7 麦パン:open/6 | ライ:C@145b/7 麦:open/7 パン:C@145b/7 別名:C@75b/7 |
| I2-036 | 1 / 0 | NGC:open/6 発見:C@21b/13 | NGC:open/7 36:open/7 発見:C@21b/13 |
| I2-037 | 1 / 1 | シリヤン:open/6 湖畔:open/4+G 街:open/4+G | シリ:open/7 ヤン:open/7 湖:C@106b/18 街:open/4+G |
| I2-038 | 0 / 0 | シリヤン:open/6 湖:C@106b/13 最大:open/18 島:open/12 | シリ:open/7 ヤン:open/7 湖:C@106b/18 最大:C@57/10 島:C@81b/7 |
| I2-039 | 4 / 0 | 寅ヤス:open/5 | 寅:open/6 ヤス:open/6 出身:C@49b/7 地:C@36b/7 |
| I2-040 | 0 / 0 | 寅ヤス:open/5 | 寅:open/6 ヤス:open/6 卒業:open/5 専門:open/5 学校:C@169/9 |
| I2-041 | 0 / 0 | ソル:open/10 クバーノ:open/10 という:C@6/15 カクテル:C@170b/16 名:C@53b/7 意味:C@21b/13 | ソル:open/10 クバーノ:open/10 いう:C@6/31 カクテル:C@170b/15 名:C@26b/8 意味:C@21b/13 |
| I2-042 | 1 / 0 | 五十嵐浜村:open/4 消滅:open/6+G 地域:C@42b/8 | 五十嵐:C@173b/7 浜村:C@173b/7 消滅:open/14 後:C@41b/7 地域:C@28b/7 現在:C@49/16 区:C@9b/7 一部:C@173/49 |
| I2-043 | 1 / 0 | 宮床村:open/7 町:C@103/18 | 宮:C@33b/7 床:C@176b/20 村:C@45/10 現在:C@49/16 町:C@7b/7 |
| I2-044 | 1 / 0 | 古浄瑠璃:open/10 人形芝居:C@201b/11 特徴:C@3b/9 | 古:C@201b/10 浄瑠璃:C@201b/10 人形:C@201b/13 芝居:C@201b/13 特徴:C@129/15 |
| I2-045 | 1 / 1 | トランス:C@261b/8 女性:C@6b/24 英語:C@63b/7 略称:C@14b/7 表現:C@21b/7 | トランス:C@261b/13 女性:C@6b/13 英語:C@32b/7 略称:C@14b/7 表現:C@21b/7 |
| I2-046 | 0 / 0 | 2025:open/10 UEFAスーパーカップ:open/7 スタジアム:open/6 | 2025:C@293/21 UEFA:C@294b/8 スーパー:C@202/11 カップ:C@196b/20 試合:open/12 スタジアム:open/7 |
| I2-047 | 0 / 0 | 2022年アジア:C@292b/8 競技大会:C@292b/8 ビーチバレーボール:C@292b/8 競技:C@292b/8 男子競技:open/7 国:C@196/17 選手:open/7 参加:open/17 | 2022:C@81b/7 年:C@17b/7 アジア:C@249/49 競技:C@183b/7 大会:C@147/7 ビーチ:C@292b/13 バレーボール:C@292b/13 男子:C@35b/7 選手:C@67b/7 参加:C@202/9 |
| I2-048 | 1 / 1 | 2017:open/7 FIFA:C@196b/14+G U-17ワールドカップ:open/7 初優勝:open/4+G 国:C@196/17+G | 2017:open/17 FIFA:C@67b/7 U:C@192b/7 17:C@22/9 ワールド:C@196b/20+G カップ:C@196b/20+G 初:open/3+G 優勝:open/22+G 国:C@16b/7 |
| I2-050 | 0 / 0 | LaMDA:C@273b/13 意識:C@48b/7 主張:C@6b/10 有効性:open/13 についての:C@6b/13 議論:C@162b/7 | LaMDA:C@273b/23 意識:C@48b/7 いう:C@6/31 主張:C@273/37 有効:C@273b/8 性:C@3b/7 議論:C@162b/7 |
| R2-I001 | 1 / 1 | ビースティ:C@53b/9 ボーイズ:C@53b/9 ベリー:open/5+G メンバー:C@53b/7 | ビースティ:C@53b/13 ボーイズ:C@53b/13 ベリー:open/5+G 後:C@41b/7 メンバー:C@53b/8 |
| R2-I002 | 1 / 0 | 内浦町:open/5 | 内浦:C@34b/7 町:C@7b/7 地域:C@28b/7 現在:open/6 一部:open/15 い:C@7/19 |
| R2-I003 | 1 / 0 | 市川町:open/6 | 市川:C@43b/13 町:C@7b/7 兵庫:C@43b/7 県:C@7b/7 |
| R2-I004 | 1 / 0 | 風藤松原:open/6 | 風:C@49b/7 藤松:C@49b/7 原:C@49b/7 2021:C@49b/7 年:C@17b/7 10:C@3b/7 月:C@17b/7 所属:C@49/8 い:C@7/19 |
| R2-I005 | 1 / 0 | サウスウェーブ:open/9 号:open/9 京成バス:open/8+G 千葉イースト:open/8+G 案内:open/7+G | サウス:open/15 ウェーブ:open/15 号:C@20b/7 京成:open/9 バス:C@88b/13 千葉:C@88/19 イースト:open/9 案内:open/7 い:C@7/19 |
| R2-I006 | 1 / 1 | シリヤン:open/6 湖:C@106b/13 | シリ:open/7 ヤン:open/7 湖:C@106b/18 部:C@25b/9 メートル:C@56b/7 |
| R2-I007 | 1 / 0 | 数河高原:C@121b/7 | 数:C@104/15 河:C@121b/8 高原:C@42b/7 気候:open/7 属し:C@51/13 |
| R2-I008 | 0 / 0 | 破局噴火:open/11 正式な:C@157/13 学術用語:C@157b/8 | 破局:open/13 噴火:C@157b/13 正式:open/27 学術:C@157b/13 用語:C@157b/14 |
| R2-I009 | 0 / 0 | 赤尾ダム:open/7 受:C@6b/10 最大:open/18 | 赤尾:C@158b/13 ダム:C@158b/13 発電:C@158b/8 所:C@49b/7 最大:C@57/10 |
| R2-I010 | 1 / 0 | 中之嶽神社:open/4 山:C@89/9 主:C@3b/9 祀:C@89b/7+G | 中:C@52/9 嶽:C@89b/7 神社:C@33b/7 山:C@56b/7 主:C@29b/9 祀ら:C@89b/7 い:C@7/19 神:C@89b/7 |
| R2-I011 | 0 / 0 | 表記:C@63b/7 | ちょん掛け:C@77b/9 1901:C@77b/9 年:C@17b/7 相撲:C@77b/9 表記:C@63b/7 技:C@75b/7 名:C@26b/8 い:C@7/19 |
| R2-I012 | 1 / 0 | コィンスコヴォラ:C@82b/8 | 2004:C@62b/7 年:C@17b/7 コィンスコヴォラ:C@82b/7 人:C@21/21 い:C@7/19 |
| R2-I013 | 1 / 1 | アワディー:open/6 語:C@40b/7 インド:C@70b/12 のほかに:C@15b/13 | アワ:C@70b/7 ディー:C@70b/7 語:C@29b/9 インド:C@70b/7 ほか:C@15b/14 国:C@16b/7 使わ:C@3b/7 い:C@7/19 |
| R2-I014 | 0 / 0 | スパイケニッセ:open/5 | 2007:C@18b/7 年:C@17b/7 スパイケニッセ:open/9 数:C@104/15 |
| R2-I015 | 1 / 1 | 2017:open/7 FIFA:C@196b/14+G U-17ワールドカップ:open/7 優勝:C@196b/15+G 国:C@196/17+G | 2017:open/17 FIFA:C@67b/7 U:C@192b/7 17:C@22/9 ワールド:C@196b/20+G カップ:C@196b/20+G 優勝:open/22+G 国:C@16b/7 |
| R2-I016 | 1 / 1 | ユニバーシアード:open/5 自転車競技:open/5 マウンテンバイク:open/4+G 追加:open/4+G | ユニバーシアード:C@208b/7 自転:C@208b/7 車:C@20/8 競技:C@183b/7 2011:C@208/25 年:C@17b/7 マウンテン:open/6+G バイク:open/6+G とも:C@107/9 追加:open/6+G |
| R2-I017 | 0 / 1 | グロタンディーク:C@99b/14 位相:C@99b/13 定義:C@99b/14 するために:C@99b/11 導入:C@99b/9 | グロタンディーク:C@99b/13 位相:C@99b/25 定義:C@99b/13 ため:C@1b/13 導入:open/15+G |
| R2-I018 | 1 / 0 | 2014年国勢調査:C@250b/7+G テレゴ:open/10 県:C@64b/7 | 2014:open/16 年:C@17b/7 国勢:C@22b/7 調査:C@22b/7 テレゴ:open/11 県:C@7b/7 数:C@104/15 人:C@21/21 |
| R2-I019 | 2 / 0 | 岡崎建設:open/9 薪ストーブ:open/9 | 岡崎:C@232b/10 建設:C@141b/13 薪:C@255b/7 ストーブ:C@255b/7 2013:C@255/25 年:C@17b/7 年間:C@255/7 台:C@57b/8 生産:C@10b/9 い:C@7/19 |
| R2-I020 | 1 / 0 | Porn:C@236b/13 2:C@137b/13 ポルノサイト:open/10+G コンテンツ:C@236b/8 提供:C@131b/10 | Porn:C@236b/22 2:C@40/25 0:C@236b/30 対照:open/13 的:C@1b/8 従来:open/13 ポルノ:C@236b/22 サイト:C@99b/7 コンテンツ:C@236b/22 提供:C@131b/17 い:C@7/19 |

## Checks

- seated units == data units of the members, every cross, step 55: 2462 crosses, 0 mismatches
- seated units == data units of the members, every cross, step 144: 5108 crosses, 0 mismatches
- every loaded snapshot (59 steps x 3 tiers) had its `state_sha256` recomputed from the raw canonical bytes and matched.
