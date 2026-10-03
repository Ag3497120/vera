# 種の交換会の受付（日本語・一本道・書き込み許可なし）
[goal]
project: 種の交換会
statement: 参加者が持ち寄る種の品目を登録し、当日の交換の順番を案内できるようにする

[philosophy_invariants]
I1: 参加者の住所は運営以外に見せない

[completion_criteria]
C1: 登録した品目が一覧にそろって表示されることを確認する | {"kind":"command_exit","command":["make","check-list"],"expected_exit":0}
C2: 当日の順番表の見かたが初参加の人にも分かる | human-judged
C3: 登録フォームの入力例が初参加の人にも分かる | human-judged

[phases]
P1: 品目の登録項目を決める
P2: 登録フォームを作る
P3: 当日の順番表を作る
P4: 受付係向けの手引きを書く
P5: 交換会で試しに使う

[phase_order]
P1 -> P2: フォームは決めた登録項目どおりに作る
P2 -> P3: 順番表は登録された品目から作る
P3 -> P4: 手引きは順番表の見かたを含める
P4 -> P5: 試用は手引きがそろってから行う

[decisions]
D1: 一人あたりの出品数の上限 => 五品目
D2: SCOPE | 種の発送サービス | out of scope
D3: SCOPE | 当日の来場者の人数集計 | in scope
D4: CONFIRM | 登録内容の一括編集 | not permitted
D5: CHOICE | 品目の並べ方 | 五十音順
D6: CHOICE | 当日の連絡手段 | 掲示板
D7: SCOPE | 公開日の表示 | out of scope

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
参加者の住所録を作り直す => 住所録の再作成には代表の承認が必要 => 人間

[forbidden_actions]
参加者の住所を一覧に載せる => 住所は運営だけが見る
