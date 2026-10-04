# K163 表外役割・型重複の追加攻撃登録

登録日時: 2026-10-04 06:47:49 +0900。対象は `docs/READING_SOUNDNESS.md` §10D K161・K163・K164 F3、表の変更記録 3。次の入力は実行前に登録し、すべての期待を入口の棄権とする。狙いは、result / instrument / cause / purpose の役割が PLACE・ARTIFACT・TIME など表の充填物型と重なる文で、表の patient/place/time 行から勝者を作らないこと。

| ID | 入力 | 配置する型 | 期待と根拠 |
|---|---|---|---|
| X1 | 兄が右で打った。 | 打つ=P_ACT、右=PLACE | `で` は instrument も取りうる。K163 の不採用行どおり、place に押し込まず棄権。 |
| X2 | 妹が金を休みに使った。 | 使う=P_CONSUME、金=ARTIFACT、休み=TIME | `に+TIME` は time/purpose のどちらもあり、P_CONSUME は読む型でない。棄権。 |
| X3 | 兄が庭へ穴を掘った。 | 掘る=P_CREATE、庭=PLACE、穴=ARTIFACT | `を` は結果物にも読める。patient と決めず棄権。 |
| X4 | 兄が段差で驚いた。 | 驚く=P_EMOTION、段差=PLACE | `で` は cause/place が割れる。place と決めず棄権。 |

