# N2 run1 / run2 申告・確認・根拠腕

期待は10述語・11役割行。run1 は旧gen_role、run2 はgen_role_v2。目視期待ではなく、凍結試験データに対する配置出力の比較。

- run1: 期待役割の申告 4/11、確認 1/11。
- run2: 期待役割の申告 10/11、確認 2/11。
- run2で確認された期待役割の腕検査: 全件通過。
- `confirmed` の型は確認済み型、`PARTLY_BACKED` は未確認型を表す。未確認行では分布根拠の一致を申告しない。

|述語|助詞 / 期待役割|run1申告|run1確認|run1根拠腕・有意型|run2申告|run2確認|run2根拠腕・有意型|
|---|---|---|---|---|---|---|---|
|停泊する|に / place|はい|未確認:NOT_BACKED|—|はい|未確認:NOT_BACKED|—|
|通報する|に / recipient|はい|未確認:NOT_BACKED|—|はい|未確認:NOT_BACKED|—|
|連絡する|に / recipient|はい|recipient[PERSON] + 一部未確認:PARTLY_BACKED|role_distribution@codex:narrative (PERSON)<br>role_distribution@codex:paraphrase_entail (PERSON)<br>role_distribution@codex:pro (PERSON)|はい|recipient[PERSON] + 一部未確認:PARTLY_BACKED|role_distribution@codex:narrative (PERSON)<br>role_distribution@codex:paraphrase_entail (PERSON)<br>role_distribution@codex:pro (PERSON)|
|打つ|で / instrument|いいえ|期待役割なし|—|はい|未確認:NOT_BACKED|—|
|驚く|で / cause|いいえ|期待役割なし|—|はい|未確認:NOT_BACKED|—|
|確認する|で / place|いいえ|期待役割なし|—|はい|未確認:NOT_BACKED|—|
|集める|に / goal|いいえ|期待役割なし|—|はい|未確認:NOT_BACKED|—|
|分ける|に / result|はい|未確認:NOT_BACKED|—|はい|未確認:NOT_BACKED|—|
|待つ|で / place|いいえ|期待役割なし|—|いいえ|期待役割なし|—|
|運ぶ|へ / goal|いいえ|期待役割なし|—|はい|goal[PLACE]|role_distribution@codex:narrative (PLACE)|
|運ぶ|から / source|いいえ|期待役割なし|—|はい|未確認:NOT_BACKED|—|

出典データ: `n2_run1_vs_run2.jsonl`。腕の有意型と票の対応は同ファイルの `backing_arms` に全文を保持。
