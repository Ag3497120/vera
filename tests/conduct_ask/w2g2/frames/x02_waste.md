# ごみ出し日のお知らせ（日本語・ひし形の依存・書き込み許可あり）
[goal]
project: ごみ出しカレンダー
statement: 住民が自分の地区の収集日を確かめ、前日に知らせを受け取れるようにする

[philosophy_invariants]
I1: 収集日は役所の公表資料と一致させる

[completion_criteria]
C1: 画面の収集日が公表資料と一致することを確認する | {"kind":"command_exit","command":["make","check-calendar"],"expected_exit":0}
C2: 年配の住民が読める文字の大きさである | human-judged

[phases]
P1: 収集日の表を取り込む
P2: 地区の選択画面を作る
P3: 前日の通知を実装する
P4: 家族への共有機能を作る
P5: 町内で試験運用する

[phase_order]
P1 -> P2: 画面は取り込んだ表から地区を並べる
P1 -> P3: 通知は収集日の表を見て出す
P2 -> P4: 共有は選んだ地区ごとに行う
P3 -> P4: 共有は通知の内容をそのまま使う
P4 -> P5: 試験運用は共有機能がそろってから行う

[decisions]
D1: 通知の時刻 => 前日の午後六時
D2: SCOPE | 粗大ごみの申し込み | out of scope
D3: SCOPE | 収集日の変更のお知らせ | in scope
D4: CONFIRM | 住民の位置情報の取得 | not permitted
D5: CHOICE | 通知の方法 | アプリ内の通知
D6: CHOICE | 地区の分け方 | 町丁目ごと

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
住民の登録情報を消す => 住民データの削除には町内会長の承認が必要 => 人間

[write_allowlist]
W1: app
W2: docs

[forbidden_actions]
住民の氏名を共有画面に出す => 個人名は共有しない
