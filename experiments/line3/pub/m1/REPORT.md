# PUB-M1 measurement: the shape exchanger over the meter v1 sentences and bank5

shapes shape.v1, SHAPES_SHA 1908323f8690db16ebc7ea90ff46e00cb175ba6fd61021b6f31468c72dff7497.  Script: measure.py; numbers: results.json.  bank5 is a dev set (the rules were not tuned to it).

## (a) sentences stored by meter v1 (deduplicated)

inputs 638 (from 1610 rows); clauses 638; labels skipped 0; inputs with no clause 0

| shape | clauses | share |
|---|---|---|
| F1 属性 | 603 | 94.5 % |
| F2 主題値 | 0 | 0.0 % |
| F3 出来事 | 8 | 1.3 % |
| F4 主語なし | 3 | 0.5 % |
| F0 形なし | 24 | 3.8 % |

inputs whose clauses are all F1-F4: 614 of 638 (96.2 %); with an F0 clause: 24 (3.8 %); with some F1-F4 clause: 614 (96.2 %)
change clauses 0, F3 with the topic as subject 8, leading adverbials attached 0, events with a verb lemma (surface kept) 0

F0 reasons:

| reason | clauses | share of F0 | share of all clauses |
|---|---|---|---|
| no_relation | 15 | 62.5 % | 2.4 % |
| no_predicate | 9 | 37.5 % | 1.4 % |

F0 `no_predicate` (first 9):

- 「認証の担当はトークン更新が平井」 [平井]
- 「認証の担当は監査ログが松本」 [松本]
- 「認証の担当はトークン更新が松本」 [松本]
- 「認証の担当は出荷照合が平井」 [平井]
- 「ホストの担当はステージングがstg-a.internal」 [internal]
- 「ホストの担当は負荷試験用がstg-b.internal」 [internal]
- 「ポートの管理は検証用が8081」 [8081]
- 「河合が責任者」 [者]
- 「点検期限の机はスキャン机で月曜」 [月曜]

F0 `no_relation` (first 10):

- 「申請者の安藤」
- 「基盤のステージング用ホスト名」
- 「見本形式のPNG」
- 「チェックサム4MB」
- 「プレビュー転送ブロック8MB」
- 「プレビュー画像幅800px」
- 「チェックサム8MB」
- 「変換バッチ4MB単位」
- 「冊子索引見出し1,250件」
- 「スキャン保管用ディスク8TB」

## (a2) raw texts of the ok writes of meter v1 (deduplicated)

inputs 633 (from 1610 rows); clauses 633; labels skipped 0; inputs with no clause 0

| shape | clauses | share |
|---|---|---|
| F1 属性 | 515 | 81.4 % |
| F2 主題値 | 83 | 13.1 % |
| F3 出来事 | 8 | 1.3 % |
| F4 主語なし | 3 | 0.5 % |
| F0 形なし | 24 | 3.8 % |

inputs whose clauses are all F1-F4: 609 of 633 (96.2 %); with an F0 clause: 24 (3.8 %); with some F1-F4 clause: 609 (96.2 %)
change clauses 0, F3 with the topic as subject 8, leading adverbials attached 0, events with a verb lemma (surface kept) 0

F0 reasons:

| reason | clauses | share of F0 | share of all clauses |
|---|---|---|---|
| no_relation | 15 | 62.5 % | 2.4 % |
| no_predicate | 9 | 37.5 % | 1.4 % |

F0 `no_predicate` (first 9):

- 「認証の担当はトークン更新が平井」 [平井]
- 「認証の担当は監査ログが松本」 [松本]
- 「認証の担当はトークン更新が松本」 [松本]
- 「認証の担当は出荷照合が平井」 [平井]
- 「ホストの担当はステージングがstg-a.internal」 [internal]
- 「ホストの担当は負荷試験用がstg-b.internal」 [internal]
- 「ポートの管理は検証用が8081」 [8081]
- 「河合が責任者」 [者]
- 「点検期限の机はスキャン机で月曜」 [月曜]

F0 `no_relation` (first 10):

- 「申請者の安藤」
- 「基盤のステージング用ホスト名」
- 「見本形式のPNG」
- 「チェックサム4MB」
- 「プレビュー転送ブロック8MB」
- 「プレビュー画像幅800px」
- 「チェックサム8MB」
- 「変換バッチ4MB単位」
- 「冊子索引見出し1,250件」
- 「スキャン保管用ディスク8TB」

## (b) bank5 message texts

inputs 156; clauses 276; labels skipped 1; inputs with no clause 0

| shape | clauses | share |
|---|---|---|
| F1 属性 | 59 | 21.4 % |
| F2 主題値 | 164 | 59.4 % |
| F3 出来事 | 7 | 2.5 % |
| F4 主語なし | 1 | 0.4 % |
| F0 形なし | 45 | 16.3 % |

inputs whose clauses are all F1-F4: 114 of 156 (73.1 %); with an F0 clause: 42 (26.9 %); with some F1-F4 clause: 127 (81.4 %)
change clauses 3, F3 with the topic as subject 7, leading adverbials attached 0, events with a verb lemma (surface kept) 3

F0 reasons:

| reason | clauses | share of F0 | share of all clauses |
|---|---|---|---|
| gap_is_not_a_particle | 41 | 91.1 % | 14.9 % |
| no_relation | 3 | 6.7 % | 1.1 % |
| no_predicate | 1 | 2.2 % | 0.4 % |

F0 `gap_is_not_a_particle` (first 10):

- 「担当表では認証モジュール担当は田中です」 [では]
- 「今朝の一覧ではリリース窓口担当は小林」 [では]
- 「一覧ではCDNキャッシュTTLは30秒」 [では]
- 「会場費上限は8万円から9万円に引き上げる変更になりました」 [から]
- 「デモ用イメージはv2.3からv2.4へ更新となりました」 [へ]
- 「予算表では会場費9万円」 [では]
- 「工程メモではAPI凍結はフロント統合の前提です」 [では]
- 「契約確認表では契約テストは顧客受入テストの前提です」 [では]
- 「受付班の副担当は西村です」 [の副]
- 「当番表では安全統括は西村です」 [では]

F0 `no_predicate` (first 1):

- 「名古屋で利用者説明をします」 [説明]

F0 `no_relation` (first 3):

- 「田中です」
- 「バックエンド進捗です」
- 「配信費2万円です」

## (c) texts of the meter v1 `span_inexpressible` write refusals (deduplicated)

inputs 273 (from 727 rows); clauses 273; labels skipped 0; inputs with no clause 0

| shape | clauses | share |
|---|---|---|
| F1 属性 | 132 | 48.4 % |
| F2 主題値 | 113 | 41.4 % |
| F3 出来事 | 5 | 1.8 % |
| F4 主語なし | 0 | 0.0 % |
| F0 形なし | 23 | 8.4 % |

inputs whose clauses are all F1-F4: 250 of 273 (91.6 %); with an F0 clause: 23 (8.4 %); with some F1-F4 clause: 250 (91.6 %)
change clauses 3, F3 with the topic as subject 5, leading adverbials attached 0, events with a verb lemma (surface kept) 2

F0 reasons:

| reason | clauses | share of F0 | share of all clauses |
|---|---|---|---|
| gap_is_not_a_particle | 21 | 91.3 % | 7.7 % |
| case_before_topic | 1 | 4.3 % | 0.4 % |
| no_predicate | 1 | 4.3 % | 0.4 % |

meter v1 refusal rows 727 (reasons {"gap_is_not_a_particle": 71, "nested_particle_chain": 656}); the rows whose text is now a sentence of F1-F4 clauses only: 657 (90.4 %)
by the loom's refusal reason: {"gap_is_not_a_particle": {"now_F1_F4": 3, "rows": 71}, "nested_particle_chain": {"now_F1_F4": 654, "rows": 656}}

F0 `case_before_topic` (first 1):

- 「認証運用表でトークン更新担当は平井」 [で]

F0 `gap_is_not_a_particle` (first 10):

- 「デモ用イメージは v2.3 から v2.4 に更新」 [から]
- 「受付班の副担当は西村」 [の副]
- 「受付班の副担当者は西村」 [の副]
- 「受付班の副の担当は西村」 [の副の]
- 「受付班の副担当の名前は西村」 [の副]
- 「受付班の副担当者の名前は西村」 [の副]
- 「受付の副担当は西村」 [の副]
- 「入場券の受付開始は9:30へ変更」 [へ]
- 「承認会議の日程は11/09から11/10へ延期」 [へ]
- 「承認会議の日程は11/09から11/10に延期」 [から]

F0 `no_predicate` (first 1):

- 「ステージングホストは基盤担当でstg-b.internal」 [internal]

