# 公民館の貸室予約（日本語・一本道・書き込み許可あり）
[goal]
project: 貸室予約
statement: 住民が公民館の部屋の空きを調べて申し込め、職員が予定を確かめられるようにする

[philosophy_invariants]
I1: 利用者の連絡先は職員以外に見せない

[completion_criteria]
C1: 同じ部屋の同じ時間が二重に押さえられないことを確認する | {"kind":"command_exit","command":["make","check-rooms"],"expected_exit":0}
C2: 初めての利用者でも申し込みの手順で迷わない | human-judged

[phases]
P1: 部屋の一覧を登録する
P2: 空き状況の画面を作る
P3: 申し込みの入力欄を実装する
P4: 職員用の予定表を作る
P5: 公民館で試しに使う

[phase_order]
P1 -> P2: 空き状況は登録した部屋ごとに出す
P2 -> P3: 申し込みは空きを確かめた枠にだけできる
P3 -> P4: 予定表は受け付けた申し込みを並べる
P4 -> P5: 試しに使うのは職員用の予定表が見られてから

[decisions]
D1: 一回に借りられる単位 => 二時間
D2: SCOPE | 会議用の机の貸し出し | out of scope
D3: SCOPE | 利用後のアンケート | in scope
D4: CONFIRM | 空き枠の自動確保 | not permitted
D5: CHOICE | 申し込みの確定連絡 | 電話
D6: CHOICE | 予定表の見せ方 | 週ごとの一覧

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
利用者の申込記録を消す => 申込記録の削除には館長の承認が必要 => 人間

[write_allowlist]
W1: app
W2: docs

[forbidden_actions]
利用者の連絡先を掲示に出す => 連絡先は職員だけが見る
