# 診療所の予約リマインド（日本語・一本道・取り置き枠・上げる条件あり）
[goal]
project: 予約リマインド
statement: 診療所の患者に予約の前日に連絡を送り、取り消しも受け付けられるようにする

[philosophy_invariants]
I1: 診療の内容は連絡の文面に書かない

[completion_criteria]
C1: 前日の連絡が対象の予約すべてに届くことを確認する | {"kind":"command_exit","command":["make","check-reminder"],"expected_exit":0}
C2: 受付の職員が操作を覚えられる | human-judged

[phases]
P1: 予約枠の種類を決める
P2: 受付画面を作る
P3: リマインドの送信を実装する
P4: 取り消しの受付を実装する
P5: 診療所の中で試用する

[phase_order]
P1 -> P2: 画面は枠の種類ごとに作る
P2 -> P3: 送信は受付済みの予約を対象にする
P3 -> P4: 取り消しは送った連絡に返信できるようにする
P4 -> P5: 試用は取り消しまでそろってから行う

[decisions]
D1: 連絡の送信時刻 => 前日の午後三時
D2: SCOPE | 診療費の精算 | out of scope
D3: SCOPE | 予約枠の空き状況の表示 | in scope
D4: CONFIRM | 患者への一斉の試験連絡 | not permitted
D5: CHOICE | 連絡の手段 | ショートメッセージ
D6: CHOICE | 予約枠の単位 | 二十分

[vocabulary_aliases]
none: none

[escalation_conditions]
E1: 診療科の追加 => 診療科が増えると運用が変わる => 人間 => ANY

[protected_actions]
患者の診察券の番号を消す => 患者番号の削除には院長の承認が必要 => 人間

[write_allowlist]
W1: app
W2: tests

[forbidden_actions]
患者の氏名を連絡の文面に入れる => 個人名は文面に載せない
