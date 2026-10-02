# 直売所の在庫アプリ（日本語・方針が多い・別名あり・書き込み許可あり）
[goal]
project: 直売所在庫アプリ
statement: 直売所の在庫を数えて、売り切れそうな品を農家に知らせられるようにする

[philosophy_invariants]
I1: 在庫の数は端末の中だけで数える

[completion_criteria]
C1: 在庫の増減が合うことを確認する | {"kind":"command_exit","command":["make","check-stock"],"expected_exit":0}
C2: 通知の文面が農家に伝わる | human-judged
C3: 起動してすぐに一覧が出る | human-judged

[phases]
P1: 品目の一覧を作る
P2: 在庫の入力画面を作る
P3: 売り切れ通知を実装する

[phase_order]
P1 -> P2: 入力画面は品目の一覧から選ばせる
P2 -> P3: 通知は入力された在庫を見て出す

[decisions]
D1: SCOPE | 価格の自動計算 | out of scope
D2: SCOPE | 売り切れの通知 | in scope
D3: SCOPE | 農家ごとの集計 | in scope
D4: CONFIRM | 実機での通知の試験 | not permitted
D5: CHOICE | 通知の手段 | 端末内の通知
D6: 画面の言語 => 日本語

[vocabulary_aliases]
棚卸し画面 => 在庫の入力画面
在庫切れ通知 => 売り切れ通知

[escalation_conditions]
none: none

[protected_actions]
農家の電話番号を外部に渡す => 個人情報の提供には人間の承認が必要 => 人間

[write_allowlist]
W1: src
W2: docs/stall
