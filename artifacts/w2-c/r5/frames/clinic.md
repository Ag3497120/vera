# 診療所の予約受付（日本語）
[goal]
project: 診療所の予約受付
statement: 診療所の予約を電話と画面で受け付け、受付の記録を残す

[philosophy_invariants]
I1: 患者の病歴を受付の画面に表示しない
I2: 病歴を外部に送ることはしない

[completion_criteria]
C1: 予約が二重にならないことを確認する | {"kind":"command_exit","command":["make","check"],"expected_exit":0}
C2: 夜間の点検で古い控えを破棄して容量を確かめる | human-judged

[phases]
P1: 予約の項目を決める
P2: 受付の画面を作る
P3: 確認の電話を自動化する
P4: 院内で試す

[phase_order]
P1 -> P2: 画面は項目が決まってから作る
P2 -> P3: 電話は画面の予約を読む
P2 -> P4: 院内の試験は画面がそろってから行う

[decisions]
D1: 予約の単位 => 15分
D2: 控えの保管場所 => 院内のサーバー
D3: SCOPE | オンライン診療の予約 | out of scope
D4: CONFIRM | 職員による操作の練習 | permitted
D5: CONFIRM | 患者への試験の電話 | not permitted
D6: CHOICE | 文字の色 | 黒

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
病歴を外部に送る => 病歴の送付には院長の承認が必要 => 人間

[write_allowlist]
W1: clinic
W2: tests

[forbidden_actions]
古い控えを破棄する => 控えは5年保管する

[conflict_precedence]
R1: completion_criteria > forbidden_actions: 点検のための破棄は認める
R2: philosophy_invariants > protected_actions: 承認があっても不変条件が先
