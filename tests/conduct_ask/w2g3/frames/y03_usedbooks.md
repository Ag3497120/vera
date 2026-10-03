# 古書店の買い取り査定（日本語・枝分かれと合流・書き込み許可あり）
[goal]
project: 買い取り査定
statement: 店員がお客さんの持ち込んだ本を調べ、買い取りの値段の目安をその場で伝えられるようにする

[philosophy_invariants]
I1: お客さんの身分証の写しは保存しない

[completion_criteria]
C1: 同じ本が二重に登録されないことを確認する | {"kind":"command_exit","command":["make","check-dup"],"expected_exit":0}
C2: 新人の店員でも査定の手順が分かる | human-judged

[phases]
P1: 本の情報を調べる仕組みをつなぐ
P2: 状態の評価画面を作る
P3: 値段の目安の計算を実装する
P4: お客さんへの提示画面を作る
P5: 店頭で一週間試す

[phase_order]
P1 -> P2: 評価画面は調べた本の情報を表示する
P2 -> P3: 計算は評価で付けた状態を使う
P2 -> P4: 提示画面は評価の結果を並べる
P3 -> P5: 試験では値段の目安も使う
P4 -> P5: 試験ではお客さんへの提示も行う

[decisions]
D1: 目安の表示単位 => 十円
D2: SCOPE | 雑誌の買い取り | out of scope
D3: SCOPE | 値段の履歴の保存 | in scope
D4: CONFIRM | お客さんへの値引きの提案 | not permitted
D5: CHOICE | 本の情報の調べ方 | コードの読み取り
D6: CHOICE | 提示画面の向き | 横向き

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
査定の履歴を全部消す => 査定履歴の消去には店長の承認が必要 => 人間

[write_allowlist]
W1: app
W2: tests

[forbidden_actions]
お客さんの身分証を撮影して保存する => 身分証の写しは残さない
