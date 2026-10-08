# R4 目視の表（W10-f05, 本物の後段 qwen3.5:4b, 自転車の整備の文書）

**これは目視であり正解データではない。** 実装役が 1 語ずつ見て付けた印で、基準は「この文書の中での普通の読み」。

| 行き先 | 語 | 申告の型 | decided_by | 目視 | 理由 |
|---|---|---|---|---|---|
| layer_estimated | 作業 | EVENT_ACT | gen_definition | 正 |  |
| layer_estimated | 作業台 | ARTIFACT | gen_definition | 正 |  |
| layer_confirmed | ディレイラー | ARTIFACT | hearst@doc:c2d800d37937 | 正 | 自転車部品。ARTIFACT で妥当 |
| layer_estimated | 午前 | TIME | gen_definition | 正 |  |
| layer_confirmed | スプロケット | ARTIFACT | hearst@doc:c2d800d37937 | 正 | 自転車部品。ARTIFACT で妥当 |
| layer_estimated | トルク | STATE_PROPERTY | gen_definition | 正 |  |
| layer_estimated | ボルト | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | 客 | PERSON | gen_definition | 正 |  |
| layer_confirmed | チェーンリング | ARTIFACT | hearst@doc:c2d800d37937 | 正 | 自転車部品。ARTIFACT で妥当 |
| layer_estimated | リング | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | ブラケット | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | 朝 | TIME | gen_definition | 正 |  |
| layer_estimated | 振れ取り | STATE_PROPERTY | gen_definition | 誤 | 作業（EVENT_ACT）。STATE_PROPERTY は誤り |
| layer_estimated | グリス | SUBSTANCE_FOOD | gen_definition | 正 |  |
| layer_estimated | ブレーキ | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | ブレーキキャリパー | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | キャリパー | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | アウターケーシング | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | ケーシング | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | チューブ | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | 空気 | STATE_PROPERTY | gen_definition | 割れる | SUBSTANCE_FOOD か STATE_PROPERTY か。割れる |
| layer_estimated | 修理 | EVENT_ACT | gen_definition | 正 |  |
| layer_estimated | ペダル | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | ステム | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | ハンドル | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | バー | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | シート | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | シートポスト | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | ポスト | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | フォーク | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | フレーム | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | フリー | STATE_PROPERTY | gen_definition | 誤 | 断片（フリーホイール）。null が正しい |
| layer_estimated | フリーホイール | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | ホイール | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | ディスクローター | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | パッド | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | 棚 | PLACE | gen_definition | 正 |  |
| layer_estimated | チェーンチェッカー | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | 整理 | EVENT_ACT | gen_definition | 正 |  |
| layer_estimated | 消耗品 | SUBSTANCE_FOOD | gen_definition | 誤 | 自転車の消耗部品で ARTIFACT が妥当。SUBSTANCE_FOOD は誤り |
| layer_estimated | 午後 | TIME | gen_definition | 正 |  |
| layer_estimated | バーテープ | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | テープ | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | クイック | STATE_PROPERTY | gen_definition | 誤 | 断片（クイックリリース）。null が正しい |
| layer_estimated | スルーアクスル | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | ダウンチューブ | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | 傷 | STATE_PROPERTY | gen_definition | 正 |  |
| layer_estimated | 歪み | STATE_PROPERTY | gen_definition | 正 |  |
| layer_estimated | トップチューブ | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | シートチューブ | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | シール | SUBSTANCE_FOOD | gen_definition | 割れる | 貼るシール（ARTIFACT）か物質か。判定が割れる |
| layer_estimated | リアディレイラー | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | 位置 | RELATIVE_POSITION | gen_definition | 正 |  |
| layer_estimated | フロントディレイラー | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | カセットスプロケット | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | リムテープ | SUBSTANCE_FOOD | gen_definition | 誤 | リムに貼る帯で ARTIFACT。SUBSTANCE_FOOD は誤り |
| layer_estimated | レス | STATE_PROPERTY | gen_definition | 誤 | 断片（チューブレス）。null が正しい |
| layer_estimated | 圧 | STATE_PROPERTY | gen_definition | 正 |  |
| layer_estimated | シー | INFO_LANGUAGE | gen_definition | 誤 | トークナイザの断片（シーラント）。語でないので null が正しい |
| layer_estimated | シーラント | SUBSTANCE_FOOD | gen_definition | 正 |  |
| layer_estimated | ラント | ARTIFACT | gen_definition | 誤 | 断片（シーラント）。null が正しい |
| layer_estimated | エアロスポーク | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | 油圧 | STATE_PROPERTY | gen_definition | 正 |  |
| layer_estimated | 油圧ブレーキ | ARTIFACT | gen_definition | 正 |  |
| layer_estimated | エア抜き | EVENT_ACT | gen_definition | 正 |  |
| layer_estimated | フルード | SUBSTANCE_FOOD | gen_definition | 正 |  |
| layer_estimated | 完成 | STATE_PROPERTY | gen_definition | 割れる | EVENT_ACT とも読める。割れる |
| layer_estimated | 店頭 | PLACE | gen_definition | 正 |  |

## 集計（目視）
- direct（layer_confirmed）: 3 語、目視の誤り 0 語（誤りの率 0/3。基準の 1 割以下を満たす）。
- estimated: 65 語、明らかな誤り 8 語、割れる 3 語。estimated は読解器に読まれず答えを変えないので、この誤りは配置の答えに出ない（表示と台帳にだけ出る）。
- 閾値は取り直していない（direct の誤りが 1 割以下のため、上げる必要が出なかった）。
