# 経費精算ツール（日本語・ひし形の依存・方針と決定の矛盾あり）
[goal]
project: 経費精算ツール
statement: 社員が経費を申請し、承認を経て月ごとに集計できるようにする

[philosophy_invariants]
I1: 承認の履歴は消さない
I2: 金額は端数を切り捨てない

[completion_criteria]
C1: 月次の合計が手計算と一致する | {"kind":"command_exit","command":["make","verify-monthly"],"expected_exit":0}
C2: 承認者が迷わず操作できる | human-judged

[phases]
P1: 申請書の様式を決める
P2: 入力画面を作る
P3: 承認の流れを作る
P4: 集計機能を作る
P5: 月次の出力を実装する

[phase_order]
P1 -> P2: 画面は様式に沿って作る
P1 -> P3: 承認の流れは様式の項目を使う
P2 -> P4: 集計は入力された申請を読む
P3 -> P4: 集計は承認済みだけを数える
P4 -> P5: 出力は集計結果を使う

[decisions]
D1: SCOPE | 交通費の精算 | in scope
D2: SCOPE | 立替金の精算 | in scope
D3: SCOPE | 立替金の精算 | out of scope
D4: 帳票の形式 => CSV
D5: 帳票の形式 => PDF
D6: CHOICE | 承認の段数 | 2段

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
経費を支払う => 支払いには経理の承認が必要 => 人間
