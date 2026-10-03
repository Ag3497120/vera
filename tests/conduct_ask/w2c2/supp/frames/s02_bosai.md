# 町内会の防災訓練（日本語・一本道・書き込み許可なし；W2-c2 第 2 ラウンドの補い）
[goal]
project: 防災訓練の運営
statement: 町内会の防災訓練の参加者を数え、集合場所と当日の役割を決めて、終わった後に振り返りを残す

[philosophy_invariants]
I1: 参加者の名簿は訓練が終わっても町内会の外に出さない

[completion_criteria]
C1: 集合場所の一覧と地図の番号が一致していることを確認する | {"kind":"command_exit","command":["make","check-map"],"expected_exit":0}
C2: 初めての参加者にも当日の役割が分かる | human-judged

[phases]
P1: 集合場所の一覧を決める
P2: 当日の役割表を作る
P3: 参加者の受付名簿を作る
P4: 振り返りの記録欄を作る
P5: 小さな訓練で試す

[phase_order]
P1 -> P2: 役割は集合場所ごとに割り振る
P2 -> P3: 受付名簿には役割を書く欄を付ける
P3 -> P4: 振り返りは受付の人数を使う
P4 -> P5: 試すのは記録欄ができてから

[decisions]
D1: 集合場所の数 => 四か所
D2: SCOPE | 炊き出しの手配 | out of scope
D3: SCOPE | 当日の安否の確認 | in scope
D4: CONFIRM | 名簿の持ち出し | not permitted
D5: CHOICE | 役割表の形式 | 紙
D6: CHOICE | 連絡の手段 | 回覧板
D7: SCOPE | 備蓄品の購入 | out of scope

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
名簿を作り直す => 名簿の再作成には自治会長の承認が必要 => 人間

[forbidden_actions]
参加者の住所を掲示する => 住所は担当者だけが見る
