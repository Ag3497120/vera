### flat-fast: furthest stage of the gold (n = 69)

| stage | count | ids |
|---|---|---|
| 0 tok | 18 | I2-001, I2-007, I2-008, I2-015, I2-016, I2-018, I2-019, I2-026, I2-038, I2-040, I2-041, I2-046, I2-047, I2-050, R2-I008, R2-I009, R2-I011, R2-I014 |
| 1 noquery | 20 | I2-010, I2-011, I2-017, I2-020, I2-023, I2-032, I2-035, I2-039, I2-043, I2-044, R2-I002, R2-I003, R2-I004, R2-I006, R2-I007, R2-I010, R2-I012, R2-I015, R2-I017, R2-I019 |
| 2 budget | 11 | I2-012, I2-022, I2-025, I2-028, I2-033, I2-034, I2-036, I2-045, I2-048, R2-I013, R2-I020 |
| 3 nofix | 2 | I2-009, R2-I016 |
| 4 noagree | 10 | I2-002, I2-003, I2-004, I2-005, I2-006, I2-013, I2-021, I2-024, I2-030, I2-031 |
| 5 select | 1 | R2-I018 |
| 6 path | 0 |  |
| 7 hit | 7 | I2-014, I2-027, I2-029, I2-037, I2-042, R2-I001, R2-I005 |

### layers-ssp-fast: furthest stage of the gold (n = 69)

| stage | count | ids |
|---|---|---|
| 0 tok | 18 | I2-001, I2-007, I2-008, I2-015, I2-016, I2-018, I2-019, I2-026, I2-038, I2-040, I2-041, I2-046, I2-047, I2-050, R2-I008, R2-I009, R2-I011, R2-I014 |
| 1 noquery | 20 | I2-010, I2-011, I2-017, I2-020, I2-023, I2-032, I2-035, I2-039, I2-043, I2-044, R2-I002, R2-I003, R2-I004, R2-I006, R2-I007, R2-I010, R2-I012, R2-I015, R2-I017, R2-I019 |
| 2 budget | 10 | I2-012, I2-022, I2-025, I2-028, I2-033, I2-034, I2-036, I2-045, R2-I013, R2-I020 |
| 3 nofix | 1 | R2-I016 |
| 4 noagree | 10 | I2-002, I2-003, I2-004, I2-005, I2-006, I2-013, I2-021, I2-024, I2-030, I2-031 |
| 5 select | 1 | R2-I018 |
| 6 path | 0 |  |
| 7 hit | 9 | I2-009, I2-014, I2-027, I2-029, I2-037, I2-042, I2-048, R2-I001, R2-I005 |

### per tier (flat-fast): stage counts

| tier | tok | noquery | budget | nofix | noagree | select | path | hit |
|---|---|---|---|---|---|---|---|---|
| RUN | 19 | 21 | 11 | 1 | 10 | 1 | 0 | 6 |
| WORD | 51 | 9 | 7 | 1 | 0 | 0 | 0 | 1 |
| CHAR | 68 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |

### layers-ssp misses whose upper layer read a bundle holding a gold unit (k = 1): I2-002, I2-003, I2-004, I2-005, I2-013, I2-021, I2-024, I2-030, I2-031, R2-I016

### verdict of each tier for the misses (flat-fast)

| id | gold | stage per tier R/W/C | RUN verdict | WORD verdict | CHAR verdict | RUN entries (first 2) |
|---|---|---|---|---|---|---|
| I2-001 | ハッシュ表 | tok/tok/tok | UNKNOWN_NO_EVIDENCE | UNKNOWN_RATIO_DISAGREEMENT | UNKNOWN_NO_FIXED_POINT | - |
| I2-002 | 連結成分 | noagree/tok/tok | AMBIGUOUS | CHOICE | ANSWER | - |
| I2-003 | JR-Y13 | noagree/tok/tok | AMBIGUOUS | ANSWER | ANSWER | - |
| I2-004 | Y17 | noagree/tok/tok | UNKNOWN_NO_EVIDENCE | ANSWER | CHOICE | - |
| I2-005 | JA16 | noagree/tok/tok | AMBIGUOUS | UNKNOWN_NO_FIXED_POINT | ANSWER | - |
| I2-006 | OR08 | noagree/tok/tok | UNKNOWN_NO_EVIDENCE | UNKNOWN_NO_FIXED_POINT | UNKNOWN_NO_FIXED_POINT | - |
| I2-007 | 路線の廃止 | tok/tok/tok | AMBIGUOUS | CHOICE | UNKNOWN_RATIO_DISAGREEMENT | - |
| I2-008 | カール・マルクス | tok/tok/tok | ANSWER | ANSWER | ANSWER | 19世紀/えた/カール/マルクス/唱/歴史観 |
| I2-009 | ボーカル | budget/nofix/tok | UNKNOWN_NO_EVIDENCE | UNKNOWN_NO_FIXED_POINT | UNKNOWN_NO_FIXED_POINT | - |
| I2-010 | 3位 | noquery/tok/tok | UNKNOWN_SECTION_DISAGREEMENT | UNKNOWN_NO_EVIDENCE | UNKNOWN_NO_FIXED_POINT | - |
| I2-011 | 改称 | noquery/noquery/tok | ANSWER | CHOICE | ANSWER | という/意味/語 |
| I2-012 | 深川八幡宮 | budget/tok/tok | ANSWER | UNKNOWN_NO_FIXED_POINT | ANSWER | とも/言/訳 |
| I2-013 | 県社 | noagree/tok/tok | UNKNOWN_NO_FIXED_POINT | CHOICE | ANSWER | - |
| I2-015 | さいたま市見沼区 | tok/tok/tok | UNKNOWN_NO_FIXED_POINT | ANSWER | UNKNOWN_NO_FIXED_POINT | - |
| I2-016 | 地上から | tok/tok/tok | ANSWER | AMBIGUOUS | UNKNOWN_NO_FIXED_POINT | パン/ライ/作 |
| I2-017 | GPIB | noquery/noquery/tok | UNKNOWN_NO_FIXED_POINT | UNKNOWN_NO_EVIDENCE | UNKNOWN_NO_FIXED_POINT | - |
| I2-018 | 権現さん | tok/tok/tok | ANSWER | UNKNOWN_NO_FIXED_POINT | CHOICE | とも/言/訳 |
| I2-019 | BAN BAN | tok/tok/tok | ANSWER | UNKNOWN_NO_EVIDENCE | UNKNOWN_NO_FIXED_POINT | BAN/マスコット/熊 |
| I2-020 | 17代目 | noquery/tok/tok | UNKNOWN_NO_EVIDENCE | CHOICE | CHOICE | - |
| I2-021 | 西村姓|西村 | noagree/budget/tok | UNKNOWN_SECTION_DISAGREEMENT | CHOICE | CHOICE | - |
| I2-022 | 永樂 | budget/tok/tok | UNKNOWN_NO_EVIDENCE | ANSWER | UNKNOWN_NO_FIXED_POINT | - |
| I2-023 | 富国強兵 | noquery/tok/tok | UNKNOWN_NO_FIXED_POINT | UNKNOWN_NO_FIXED_POINT | UNKNOWN_NO_FIXED_POINT | - |
| I2-024 | 集配普通郵便局 | noagree/tok/tok | UNKNOWN_NO_FIXED_POINT | UNKNOWN_NO_FIXED_POINT | ANSWER | - |
| I2-025 | 青 | noquery/budget/budget | ANSWER | CHOICE | UNKNOWN_NO_FIXED_POINT | アメリカ/ニューヨーク/合衆国/市/戦争 |
| I2-026 | アワド語 | tok/tok/tok | UNKNOWN_SECTION_DISAGREEMENT | CHOICE | UNKNOWN_NO_FIXED_POINT | - |
| I2-028 | 大曲輪遺跡 | budget/tok/tok | ANSWER | UNKNOWN_NO_FIXED_POINT | ANSWER | とも/言/訳 |
| I2-030 | 16柱 | noagree/tok/tok | UNKNOWN_NO_FIXED_POINT | ANSWER | CHOICE | - |
| I2-031 | USB|イーサネット|LXI | noagree/noquery/tok | UNKNOWN_NO_FIXED_POINT | UNKNOWN_NO_EVIDENCE | UNKNOWN_NO_FIXED_POINT | - |
| I2-032 | 製鋼所 | noquery/tok/tok | UNKNOWN_NO_EVIDENCE | ANSWER | ANSWER | - |
| I2-033 | リュカーオーン | noquery/budget/tok | UNKNOWN_NO_EVIDENCE | UNKNOWN_RATIO_DISAGREEMENT | UNKNOWN_NO_FIXED_POINT | - |
| I2-034 | 1981年 | budget/tok/tok | CHOICE | ANSWER | UNKNOWN_NO_FIXED_POINT | 1にかつて/21/サンゴーカメラ/中心/家電量販店 ; 1にかつて/21/サンゴーカメラ/中心/東京都豊島区東池袋1 |
| I2-035 | 黒パン|ライパン | noquery/noquery/tok | CHOICE | CHOICE | UNKNOWN_NO_FIXED_POINT | むぎ/パン/ライ/ライムギ/作/麦パン ; パン/ライ/作 |
| I2-036 | 1785年10月25日 | budget/tok/tok | ANSWER | ANSWER | UNKNOWN_NO_FIXED_POINT | 36は/NGC/うお/座/方角/渦巻銀河 |
| I2-038 | ソレローン島 | tok/tok/tok | UNKNOWN_RATIO_DISAGREEMENT | ANSWER | UNKNOWN_NO_FIXED_POINT | - |
| I2-039 | 愛知県 | noquery/tok/tok | UNKNOWN_NO_EVIDENCE | ANSWER | UNKNOWN_NO_FIXED_POINT | - |
| I2-040 | トライデントデザイン専門学校 | tok/tok/tok | UNKNOWN_NO_EVIDENCE | ANSWER | UNKNOWN_NO_FIXED_POINT | - |
| I2-041 | キューバの太陽 | tok/tok/tok | UNKNOWN_RATIO_DISAGREEMENT | UNKNOWN_SECTION_DISAGREEMENT | UNKNOWN_NO_FIXED_POINT | - |
| I2-043 | 大和町 | noquery/tok/tok | CHOICE | ANSWER | UNKNOWN_NO_FIXED_POINT | に属す/ザムトゲマインデ/ヴェーザー/以下/本項/町/記述 ; に属す/ニーンブルク/町/町村/記述/連邦共和国ニーダーザクセン/郡 |
| I2-044 | 素朴な力強さ|宗教色 | noquery/tok/tok | CHOICE | UNKNOWN_RATIO_DISAGREEMENT | ANSWER | 初代竹本義太夫/前/古浄瑠璃/慶長/時代/浄瑠璃/義太夫節 ; 初代竹本義太夫/前/古浄瑠璃/慶長/浄瑠璃/義太夫節/貞享年間 |
| I2-045 | MtF | budget/budget/tok | ANSWER | ANSWER | UNKNOWN_NO_FIXED_POINT | トランスジェンダー/フェミニズム/女性/現代/男性 |
| I2-046 | スタディオ・フリウーリ | tok/tok/tok | CHOICE | CHOICE | UNKNOWN_NO_FIXED_POINT | 2025/2026シーズン/50回目/UEFA/UEFAスーパーカップ/アジアリーグアイスホッケー/欧州サッカー ; 2025/2026シーズン/50回目/UEFA/UEFAスーパーカップ/アジアリーグアイスホッケー/連盟 |
| I2-047 | 16の国 | tok/tok/tok | UNKNOWN_NO_EVIDENCE | CHOICE | UNKNOWN_NO_FIXED_POINT | - |
| I2-048 | イングランド | budget/noquery/tok | UNKNOWN_RATIO_DISAGREEMENT | ANSWER | UNKNOWN_NO_FIXED_POINT | - |
| I2-050 | チューリング・テスト | tok/tok/tok | UNKNOWN_NO_FIXED_POINT | ANSWER | UNKNOWN_NO_FIXED_POINT | - |
| R2-I002 | 能登町 | noquery/tok/tok | UNKNOWN_NO_EVIDENCE | CHOICE | UNKNOWN_NO_FIXED_POINT | - |
| R2-I003 | 中播磨県民センター | noquery/tok/tok | UNKNOWN_NO_EVIDENCE | CHOICE | UNKNOWN_NO_FIXED_POINT | - |
| R2-I004 | 落語協会 | noquery/tok/tok | CHOICE | ANSWER | ANSWER | 2025/2026シーズン/50回目/UEFA/UEFAスーパーカップ/アジアリーグアイスホッケー/欧州サッカー ; 2025/2026シーズン/50回目/UEFA/UEFAスーパーカップ/アジアリーグアイスホッケー/連盟 |
| R2-I006 | 120 m|120 | noquery/noquery/tok | UNKNOWN_RATIO_DISAGREEMENT | UNKNOWN_NO_FIXED_POINT | UNKNOWN_NO_FIXED_POINT | - |
| R2-I007 | 日本海側気候|日本海側 | noquery/tok/tok | UNKNOWN_NO_EVIDENCE | ANSWER | ANSWER | - |
| R2-I008 | ウルトラプリニー式噴火 | tok/tok/tok | UNKNOWN_NO_EVIDENCE | UNKNOWN_RATIO_DISAGREEMENT | CHOICE | - |
| R2-I009 | 3万2,500キロワット | tok/tok/tok | ANSWER | UNKNOWN_NO_FIXED_POINT | ANSWER | あかお/ダム/一級河川/富山県南砺市/庄川水系庄川/建設/赤尾ダム |
| R2-I010 | 波胡曽神 | noquery/tok/tok | UNKNOWN_NO_FIXED_POINT | CHOICE | CHOICE | - |
| R2-I011 | 丁斧掛け | tok/tok/tok | AMBIGUOUS | ANSWER | UNKNOWN_NO_FIXED_POINT | - |
| R2-I012 | 2188人 | noquery/tok/tok | ANSWER | AMBIGUOUS | UNKNOWN_NO_FIXED_POINT | EN/コィンスコヴォラ/ルブリン |
| R2-I013 | ネパール | budget/noquery/tok | UNKNOWN_RATIO_DISAGREEMENT | ANSWER | UNKNOWN_NO_FIXED_POINT | - |
| R2-I014 | 73,921人 | tok/tok/tok | CHOICE | ANSWER | UNKNOWN_NO_FIXED_POINT | オランダ/スパイケニッセ/南ホラント/政府/長 ; オランダ/スパイケニッセ/南ホラント/長/首相 |
| R2-I015 | イングランド | noquery/noquery/tok | UNKNOWN_RATIO_DISAGREEMENT | ANSWER | UNKNOWN_NO_FIXED_POINT | - |
| R2-I016 | BMX | nofix/budget/tok | UNKNOWN_NO_FIXED_POINT | CHOICE | UNKNOWN_NO_FIXED_POINT | - |
| R2-I017 | エタール・コホモロジー | tok/noquery/tok | ANSWER | AMBIGUOUS | UNKNOWN_NO_FIXED_POINT | 位相/位相空間上/圏 |
| R2-I018 | 20万人 | select/tok/tok | CHOICE | ANSWER | UNKNOWN_NO_FIXED_POINT | 6つ/ウガンダ/テレゴ/副郡/北部地域 ; 6つ/ウガンダ/テレゴ/副郡/西ナイル |
| R2-I019 | 15台程度|15台 | noquery/tok/tok | CHOICE | ANSWER | UNKNOWN_NO_FIXED_POINT | Maki/を行っており/フルオーダーメイド/式薪ストーブ/薪ストーブ ; Maki/を行っており/フルオーダーメイド/式薪ストーブ/鋼板製 |
| R2-I020 | 一方向のコンテンツ|一方向 | budget/tok/tok | UNKNOWN_RATIO_DISAGREEMENT | CHOICE | UNKNOWN_NO_FIXED_POINT | - |

