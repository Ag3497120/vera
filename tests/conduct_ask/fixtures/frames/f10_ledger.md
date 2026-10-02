# 手書き帳票の読み取り（日本語・取り置き枠・任意の節なし・分岐と合流）
[goal]
project: 帳票読み取りツール
statement: 手書きの帳票を撮影した画像から、金額の欄を読み取って表にする

[philosophy_invariants]
I1: 読み取れなかった欄を推測で埋めない
I2: 元の画像は加工せずに残す

[completion_criteria]
C1: 見本の帳票で金額が全部一致する | {"kind":"command_exit","command":["make","check-samples"],"expected_exit":0}
C2: 読み取れない欄が一覧で分かる | human-judged

[phases]
P1: 見本の帳票を集める
P2: 欄の位置を検出する
P3: 数字の読み取りを実装する
P4: 結果の表を書き出す
P5: 誤読の確認をする

[phase_order]
P1 -> P2: 位置の検出は見本で調整する
P1 -> P3: 読み取りは見本で試す
P2 -> P4: 表は検出した欄の順に並べる
P3 -> P4: 表には読み取った数字が入る
P4 -> P5: 確認は書き出した表を見て行う

[decisions]
D1: 画像の形式 => PNG
D2: 位置の検出の方式 => 枠線の検出
D3: SCOPE | 縦書きの帳票 | out of scope
D4: SCOPE | 金額の欄の読み取り | in scope
D5: CONFIRM | 帳票の画像の外部への送信 | not permitted
D6: CHOICE | 表の形式 | CSV

[vocabulary_aliases]
none: none

[escalation_conditions]
E1: 読み取りの精度の基準を変える => 基準は人間が決める => 人間 => ANY

[protected_actions]
帳票の原本を廃棄する => 原本の廃棄には人間の承認が必要 => 人間
