# 防災訓練の参加受付（日本語・一本道・範囲の食い違いあり・保留）
[goal]
project: 防災訓練の受付
statement: 自治会が訓練の参加者を世帯ごとに受け付け、地区ごとの人数を表にまとめられるようにする

[philosophy_invariants]
I1: 参加の申し込みは本人の同意なしに他の世帯へ見せない

[completion_criteria]
C1: 地区ごとの人数が受付の件数と合うことを確認する | {"kind":"command_exit","command":["make","check-drill"],"expected_exit":0}
C2: 受付の担当者が迷わず入力できる | human-judged

[phases]
P1: 受付項目を決める
P2: 受付画面を作る
P3: 集計表を作る
P4: 当日の運用を試す

[phase_order]
P1 -> P2: 画面は受付項目に沿って作る
P2 -> P3: 集計は受け付けた内容から作る
P3 -> P4: 当日の運用の試しは集計表ができてから行う

[decisions]
D1: 受付番号の付け方 => 世帯ごと
D2: SCOPE | 備蓄品の管理 | out of scope
D3: SCOPE | 避難経路の案内 | in scope
D4: SCOPE | 要配慮者名簿の扱い | in scope
D5: SCOPE | 要配慮者名簿の扱い | out of scope
D6: CONFIRM | 住民への一斉の自動電話 | not permitted
D7: CHOICE | 集計の単位 | 地区ごと

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
住民の名簿を外部の団体に渡す => 名簿の提供には自治会長の承認が必要 => 人間

[write_allowlist]
W1: src
W2: docs/drill

[forbidden_actions]
要配慮者の住所を掲示する => 住所の掲示は行わない
