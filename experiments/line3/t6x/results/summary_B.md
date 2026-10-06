## T6x B: capacity diagnosis of the 48 questions without an adopted state (default read rule, S300 RUN, level mid)

| category | n | detail |
|---|---|---|
| (i) no cross holds a query unit | 15 | {'all query units absent from the tier': 15} |
| (ii) only the unit's own seed cross, capacity 1 | 6 | {'': 6} |
| (iii) crosses with a query unit exist, no fixed point / ambiguous | 27 | {'UNKNOWN_NO_FIXED_POINT': 13, 'UNKNOWN_NO_EVIDENCE': 12, 'AMBIGUOUS': 2} |

(i) the 15 questions with no cross holding a query unit: query units and the own-seed cross

  query-unit totals: {'units': 18, 'absent': 18}

| id | query units (after filter) | in tier (n sentences) | own seed cross: capacity / stop / candidates |
|---|---|---|---|
| u01 | 翠壇 | 翠壇:absent | - |
| u02 | 霧鉄湾 | 霧鉄湾:absent | - |
| u05 | 蒼嶺大学 | 蒼嶺大学:absent | - |
| u06 | クワンタムフラックス 炉 | クワンタムフラックス:absent, 炉:absent | - |
| u07 | ぷにゃぷにゃ 理論 | ぷにゃぷにゃ:absent, 理論:absent | - |
| u08 | 銀鱗神社 | 銀鱗神社:absent | - |
| u10 | 黒曜電鉄 | 黒曜電鉄:absent | - |
| u11 | 星砂村 | 星砂村:absent | - |
| u12 | ザルヴェク 症候群 | ザルヴェク:absent, 症候群:absent | - |
| u13 | 朱雀橋駅 | 朱雀橋駅:absent | - |
| u14 | 鉄琴草 | 鉄琴草:absent | - |
| u16 | 白狐山 | 白狐山:absent | - |
| u17 | 月影亭事件 | 月影亭事件:absent | - |
| u18 | 雲海町議会 | 雲海町議会:absent | - |
| u20 | 青藍窯 | 青藍窯:absent | - |

(ii)/(iii): crosses holding a query unit, their capacity at mid, and how many stopped by budget

| id | cat | cycle verdict | query units | n crosses holding | capacity hist | stop hist |
|---|---|---|---|---|---|---|
| a01 | iii | UNKNOWN_NO_FIXED_POINT | 遊眠 | 3 | {'4': 2, '7': 1} | {'exhausted': 3} |
| a03 | iii | UNKNOWN_NO_EVIDENCE | 厚田聚富 | 4 | {'5': 4} | {'exhausted': 4} |
| a04 | iii | UNKNOWN_NO_EVIDENCE | BADGER HONEY | 3 | {'5': 3} | {'exhausted': 3} |
| a06 | ii | UNKNOWN_NO_EVIDENCE | ムーン 工房ハーヴェスト 経営 舞浜地ビール | 4 | {'1': 4} | {'budget': 4} |
| a08 | iii | UNKNOWN_NO_EVIDENCE | 世俗教育 | 4 | {'5': 4} | {'exhausted': 4} |
| a09 | iii | UNKNOWN_NO_EVIDENCE | 寅ヤス | 4 | {'5': 3, '7': 1} | {'exhausted': 4} |
| a10 | ii | UNKNOWN_NO_EVIDENCE | フェミニズム | 1 | {'1': 1} | {'budget': 1} |
| a14 | ii | UNKNOWN_NO_EVIDENCE | 伊勢原断層 | 1 | {'1': 1} | {'budget': 1} |
| a19 | ii | UNKNOWN_NO_EVIDENCE | ジェラーチェ 国 | 1 | {'1': 1} | {'budget': 1} |
| a21 | iii | UNKNOWN_NO_FIXED_POINT | 近江八幡郵便局 | 4 | {'4': 4} | {'exhausted': 4} |
| a23 | iii | UNKNOWN_NO_FIXED_POINT | 竜游県 | 4 | {'1': 1, '11': 1, '13': 2} | {'exhausted': 3, 'budget': 1} |
| a25 | iii | UNKNOWN_NO_EVIDENCE | 市川町 | 4 | {'6': 4} | {'exhausted': 4} |
| a26 | iii | UNKNOWN_NO_FIXED_POINT | 中之嶽神社 | 3 | {'4': 3} | {'exhausted': 3} |
| a29 | iii | UNKNOWN_NO_FIXED_POINT | 博文館 | 3 | {'4': 3} | {'exhausted': 3} |
| a30 | iii | AMBIGUOUS | 花園町駅 | 4 | {'1': 1, '9': 3} | {'exhausted': 3, 'budget': 1} |
| a31 | iii | UNKNOWN_NO_FIXED_POINT | 富岡八幡宮 | 4 | {'4': 4} | {'exhausted': 4} |
| a32 | iii | AMBIGUOUS | らない 作者 叱 母親 | 7 | {'1': 1, '8': 6} | {'exhausted': 6, 'budget': 1} |
| a34 | iii | UNKNOWN_NO_EVIDENCE | 奉天派 | 5 | {'6': 5} | {'exhausted': 5} |
| a35 | iii | UNKNOWN_NO_FIXED_POINT | 水戸東照宮 | 3 | {'4': 3} | {'exhausted': 3} |
| a36 | iii | UNKNOWN_NO_EVIDENCE | 互先 | 4 | {'5': 4} | {'exhausted': 4} |
| a38 | iii | UNKNOWN_NO_EVIDENCE | シリヤン 国 湖 | 4 | {'6': 4} | {'exhausted': 4} |
| a40 | iii | UNKNOWN_NO_FIXED_POINT | 千葉神社 | 3 | {'4': 3} | {'exhausted': 3} |
| a42 | ii | UNKNOWN_NO_EVIDENCE | 破局噴火 | 1 | {'1': 1} | {'budget': 1} |
| a44 | iii | UNKNOWN_NO_EVIDENCE | 善五郎 | 4 | {'5': 4} | {'exhausted': 4} |
| a50 | iii | UNKNOWN_NO_FIXED_POINT | 犂神社 | 3 | {'4': 3} | {'exhausted': 3} |
| a56 | iii | UNKNOWN_NO_FIXED_POINT | 蠑螺島 | 4 | {'4': 4} | {'exhausted': 4} |
| a57 | ii | UNKNOWN_NO_EVIDENCE | ハッシュテーブル | 1 | {'1': 1} | {'budget': 1} |
| u21 | iii | UNKNOWN_NO_FIXED_POINT | 代表作 遊眠 | 3 | {'4': 2, '7': 1} | {'exhausted': 3} |
| u23 | iii | UNKNOWN_NO_FIXED_POINT | 創業 博文館 | 3 | {'4': 3} | {'exhausted': 3} |
| u24 | iii | UNKNOWN_NO_FIXED_POINT | 千葉神社 祭神 | 3 | {'4': 3} | {'exhausted': 3} |
| u25 | iii | UNKNOWN_NO_EVIDENCE | 何色 奉天派 旗 | 5 | {'6': 5} | {'exhausted': 5} |
| u28 | iii | UNKNOWN_NO_EVIDENCE | LaMDA 公開 | 4 | {'6': 4} | {'exhausted': 4} |
| u29 | iii | UNKNOWN_NO_EVIDENCE | 互先 持つ 白 | 4 | {'5': 4} | {'exhausted': 4} |

Budget raise (only crosses involved that stopped by budget are rebuilt; 'exhausted' crosses cannot grow):

| id | cat | involved crosses | stopped by budget | capacity mid -> high -> max (budget-limited crosses) | new stop at max | verdict mid -> high -> max | states adopted mid/high/max |
|---|---|---|---|---|---|---|---|
| a06 | ii | 4 | 4 | ムーン: 1->1->1; 工房ハーヴェスト: 1->1->1; 経営: 1->1->11; 舞浜地ビール: 1->1->1 | {'budget': 3, 'exhausted': 1} | UNKNOWN_NO_EVIDENCE -> UNKNOWN_NO_EVIDENCE -> ANSWER | 0/0/8523 |
| a10 | ii | 1 | 1 | フェミニズム: 1->1->1 | {'budget': 1} | UNKNOWN_NO_EVIDENCE -> UNKNOWN_NO_EVIDENCE -> UNKNOWN_NO_EVIDENCE | 0/0/0 |
| a14 | ii | 1 | 1 | 伊勢原断層: 1->1->1 | {'budget': 1} | UNKNOWN_NO_EVIDENCE -> UNKNOWN_NO_EVIDENCE -> UNKNOWN_NO_EVIDENCE | 0/0/0 |
| a19 | ii | 1 | 1 | ジェラーチェ: 1->10->10 | {'exhausted': 1} | UNKNOWN_NO_EVIDENCE -> ANSWER -> ANSWER | 0/1366/1366 |
| a23 | iii | 4 | 1 | 竜游県: 1->1->11 | {'exhausted': 1} | UNKNOWN_NO_FIXED_POINT -> UNKNOWN_NO_FIXED_POINT -> UNKNOWN_NO_FIXED_POINT | 0/0/0 |
| a30 | iii | 4 | 1 | 花園町駅: 1->9->9 | {'exhausted': 1} | AMBIGUOUS -> AMBIGUOUS -> AMBIGUOUS | 0/0/0 |
| a32 | iii | 7 | 1 | 作者: 1->1->10 | {'exhausted': 1} | AMBIGUOUS -> AMBIGUOUS -> CHOICE | 0/0/1890 |
| a42 | ii | 1 | 1 | 破局噴火: 1->1->1 | {'budget': 1} | UNKNOWN_NO_EVIDENCE -> UNKNOWN_NO_EVIDENCE -> UNKNOWN_NO_EVIDENCE | 0/0/0 |
| a57 | ii | 1 | 1 | ハッシュテーブル: 1->1->1 | {'budget': 1} | UNKNOWN_NO_EVIDENCE -> UNKNOWN_NO_EVIDENCE -> UNKNOWN_NO_EVIDENCE | 0/0/0 |

questions with >= 1 involved cross stopped by budget: 9 / 48; questions whose involved crosses are all exhausted (budget cannot help): 39
  level high: questions with a bigger cross: 2; verdict changed: 1; now with an adopted state: 1  (a19:ANSWER)
  level max: questions with a bigger cross: 5; verdict changed: 3; now with an adopted state: 3  (a06:ANSWER, a19:ANSWER, a32:CHOICE)
