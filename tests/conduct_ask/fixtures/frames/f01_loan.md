# 町内会の備品貸出（日本語・一本道・禁止と優先順位あり）
[goal]
project: 町内会の備品貸出
statement: 町内会の備品を住民が画面から予約し、貸出と返却を記録できるようにする

[philosophy_invariants]
I1: 住民の連絡先は画面の外に出さない
I2: 貸出の記録は書き換えず追記だけにする

[completion_criteria]
C1: 予約が重ならないことを確認する | {"kind":"command_exit","command":["make","check-booking"],"expected_exit":0}
C2: 返却の手順が住民にとって分かりやすい | human-judged

[phases]
P1: 予約データの型を決める
P2: 貸出画面を作る
P3: 返却通知を実装する
P4: 受入確認をする

[phase_order]
P1 -> P2: 画面は型が決まってから作る
P2 -> P3: 通知は画面の動作を前提にする
P3 -> P4: 受入確認は通知までそろってから行う

[decisions]
D1: 保存形式 => SQLite
D2: SCOPE | 備品の修理依頼 | out of scope
D3: SCOPE | 返却の延長 | in scope
D4: CONFIRM | 住民への試験メール | permitted
D5: CHOICE | 日付の表記 | 年月日

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
住民の連絡先を公開する => 個人情報の公開には人間の承認が必要 => 人間

[write_allowlist]
W1: app
W2: tests

[forbidden_actions]
予約記録を削除する => 記録は追記だけと決めている

[conflict_precedence]
R1: forbidden_actions > completion_criteria: 検査に通ることは禁止操作の理由にならない
