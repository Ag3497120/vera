# 夏祭りの屋台当番表（日本語・枝分かれ・書き込み許可なし）
[goal]
project: 屋台当番表
statement: 屋台ごとの当番を決め、当日の交代を実行委員が確かめられるようにする

[philosophy_invariants]
I1: 当番の個人の連絡先は実行委員以外に見せない

[completion_criteria]
C1: 同じ時間に同じ人が二つの屋台に入っていないことを確認する | {"kind":"command_exit","command":["make","check-shift"],"expected_exit":0}
C2: 当番表の見かたが初めての人にも分かる | human-judged
C3: 当番の登録画面の入力欄が小さい画面でも使える | human-judged

[phases]
P1: 当番の時間の区切りを決める
P2: 当番の登録画面を作る
P3: 売り上げの記録欄を作る
P4: 交代の連絡画面を実装する
P5: 実行委員で試しに使う

[phase_order]
P1 -> P2: 画面は決めた時間の区切りで作る
P2 -> P3: 記録欄は登録された屋台ごとに作る
P2 -> P4: 連絡は登録された当番に送る
P3 -> P5: 試用は記録欄が見られてから
P4 -> P5: 試用は交代の連絡が送れてから

[decisions]
D1: 一回の当番の長さ => 九十分
D2: SCOPE | 屋台の出店料の集金 | out of scope
D3: SCOPE | 当番の交代の連絡 | in scope
D4: CONFIRM | 当番表の印刷 | permitted
D5: CHOICE | 連絡の手段 | 掲示板
D6: CHOICE | 時間の区切り | 三十分
D7: SCOPE | 支払い状況の画面 | out of scope

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
当番の登録を全部消す => 全削除には実行委員長の承認が必要 => 人間

[forbidden_actions]
当番の個人の連絡先を掲示する => 連絡先は実行委員だけが見る
