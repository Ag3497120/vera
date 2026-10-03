# 給食の確認表（日本語・ひし形の依存・書き込み許可あり）
[goal]
project: 給食の確認表
statement: 保護者がアレルギーの情報を届け、調理室が前日に献立と照らし合わせて確かめられるようにする

[philosophy_invariants]
I1: アレルギーの情報は調理室と担任だけが見る

[completion_criteria]
C1: 届いた情報が確認画面に漏れなく出ることを確認する | {"kind":"command_exit","command":["make","check-allergy"],"expected_exit":0}
C2: 調理室の職員が確認画面を迷わず読める | human-judged

[phases]
P1: 食材の一覧を取り込む
P2: 保護者の届け出画面を作る
P3: 献立との照合を実装する
P4: 調理室用の確認画面を作る
P5: 一つの学年で試す

[phase_order]
P1 -> P2: 届け出画面は取り込んだ食材から選ばせる
P1 -> P3: 照合は食材の一覧を使う
P2 -> P4: 確認画面は届け出の内容を並べる
P3 -> P4: 確認画面は照合の結果も示す
P4 -> P5: 試すのは確認画面ができてから

[decisions]
D1: 確認を行う時刻 => 前日の午後三時
D2: SCOPE | 献立表の作成 | out of scope
D3: SCOPE | 欠席した児童の連絡 | in scope
D4: CONFIRM | 保護者への催促の自動送信 | permitted
D5: CHOICE | 届け出の方法 | 画面からの入力
D6: CHOICE | 確認画面の言語 | 日本語のみ

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
届け出の記録を消す => 届け出の削除には校長の承認が必要 => 人間

[write_allowlist]
W1: app
W2: docs

[forbidden_actions]
児童の氏名を献立表に載せる => 個人名は掲示しない
