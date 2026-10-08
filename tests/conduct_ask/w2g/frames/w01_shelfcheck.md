# 地域図書館の蔵書点検（日本語・一本道・書き込み許可あり）
[goal]
project: 蔵書点検アプリ
statement: 司書が書架の本を順に確かめ、所在の分からない本の一覧を出せるようにする

[philosophy_invariants]
I1: 書架の並びは点検の途中で動かさない

[completion_criteria]
C1: 点検漏れの本が一覧に出ることを確認する | {"kind":"command_exit","command":["make","check-shelf"],"expected_exit":0}
C2: 司書が迷わず書架を進められる | human-judged

[phases]
P1: 書架の区分を決める
P2: 点検画面を作る
P3: 不明本の一覧を実装する
P4: 試験運用をする

[phase_order]
P1 -> P2: 画面は書架の区分に沿って作る
P2 -> P3: 一覧は点検の結果から作る
P3 -> P4: 試験運用は一覧が出てから行う

[decisions]
D1: 読み取り方式 => バーコード
D2: SCOPE | 雑誌の点検 | out of scope
D3: SCOPE | 郷土資料の点検 | in scope
D4: CONFIRM | 点検用端末の持ち帰り | not permitted
D5: CHOICE | 結果の出力形式 | 表計算ファイル
D6: CHOICE | 点検の担当 | 司書

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
蔵書データを削除する => 蔵書の削除には館長の承認が必要 => 人間

[write_allowlist]
W1: app
W2: tests

[forbidden_actions]
貸出履歴を点検画面に表示する => 利用者の貸出記録は点検に使わない
