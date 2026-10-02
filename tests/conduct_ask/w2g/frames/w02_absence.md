# 学習塾の欠席連絡（日本語・ひし形の依存・禁止と受入条件）
[goal]
project: 欠席連絡システム
statement: 保護者が生徒の欠席を画面から伝え、講師が一覧で把握できるようにする

[philosophy_invariants]
I1: 生徒の氏名は通知の件名に入れない

[completion_criteria]
C1: 欠席の件数が一覧と集計で一致することを確認する | {"kind":"command_exit","command":["make","check-absence"],"expected_exit":0}
C2: 保護者が迷わず入力できる | human-judged
C3: 欠席の記録を上書きしないが、学期末に欠席の記録を上書きする | human-judged

[phases]
P1: 欠席連絡の項目を決める
P2: 保護者の入力画面を作る
P3: 講師の一覧画面を作る
P4: 通知の送信を実装する

[phase_order]
P1 -> P2: 入力画面は項目に沿って作る
P1 -> P3: 一覧画面は項目を並べる
P2 -> P4: 通知は入力された連絡を見て出す
P3 -> P4: 通知は一覧の状態を見て出す

[decisions]
D1: CHOICE | 通知の手段 | メール
D2: SCOPE | 振替授業の申し込み | in scope
D3: SCOPE | 月謝の請求 | out of scope
D4: CONFIRM | 保護者への一斉の試験送信 | not permitted
D5: CHOICE | 欠席理由の入力 | 選択式
D6: 締切の時刻 => 当日の正午

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
生徒の成績を保護者以外に見せる => 成績の開示には塾長の承認が必要 => 人間

[forbidden_actions]
欠席の記録を上書きする => 記録は残して履歴を保つ
