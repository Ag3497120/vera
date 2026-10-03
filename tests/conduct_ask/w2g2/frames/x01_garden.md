# 市民農園の区画予約（日本語・一本道・書き込み許可あり）
[goal]
project: 農園予約アプリ
statement: 利用者が空いている区画を選んで予約し、管理人が利用の状況を確かめられるようにする

[philosophy_invariants]
I1: 利用者の住所は管理人以外に見せない

[completion_criteria]
C1: 同じ区画が二重に予約されないことを確認する | {"kind":"command_exit","command":["make","check-booking"],"expected_exit":0}
C2: 高齢の利用者でも迷わず予約できる | human-judged

[phases]
P1: 区画の一覧を整える
P2: 予約画面を作る
P3: 確認メールの送信を実装する
P4: 管理人用の利用表を作る
P5: 利用者に試してもらう

[phase_order]
P1 -> P2: 予約画面は区画の一覧から選ばせる
P2 -> P3: 確認メールは予約が入ってから送る
P3 -> P4: 利用表は確認が済んだ予約だけを載せる
P4 -> P5: 試してもらうのは利用表が見られるようになってから

[decisions]
D1: 区画の広さの表記 => 平方メートル
D2: SCOPE | 農具の貸し出し | out of scope
D3: SCOPE | 利用者どうしの掲示板 | in scope
D4: CONFIRM | 予約の自動キャンセル | not permitted
D5: CHOICE | 予約の単位 | 半年
D6: CHOICE | 利用表の形式 | 一覧表
D7: 使用料の支払い方法 => 現地での手渡し

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
予約の記録を消す => 予約記録の削除には管理人の承認が必要 => 人間

[write_allowlist]
W1: app
W2: tests

[forbidden_actions]
利用者の電話番号を掲示板に出す => 連絡先は管理人だけが見る
