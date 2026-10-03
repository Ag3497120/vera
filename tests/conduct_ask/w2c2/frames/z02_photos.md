# 古い写真のデジタル化（日本語・一本道・書き込み許可あり・工程名に除去の語）
[goal]
project: 写真のデジタル化
statement: 家に残る古い写真を取り込み、傷を直し、日付順のアルバムにして家族が見られるようにする

[philosophy_invariants]
I1: 原本の写真は取り込みの後も捨てない

[completion_criteria]
C1: 取り込んだ写真の枚数が原本の枚数と一致することを確認する | {"kind":"command_exit","command":["make","check-count"],"expected_exit":0}
C2: 家族の誰が見ても日付順に並んでいると分かる | human-judged
C3: 撮影日の一覧表が家族に読める | human-judged

[phases]
P1: 取り込みの手順を決める
P2: 傷や汚れを取り除く
P3: 撮影日の一覧を作る
P4: 閲覧用のアルバムを組む
P5: 家族に見せて確かめる

[phase_order]
P1 -> P2: 取り込んだ写真だけを補正する
P2 -> P3: 補正した写真から日付を拾う
P3 -> P4: アルバムは日付順に組む
P4 -> P5: 見せるのはアルバムができてから

[decisions]
D1: 取り込みの解像度 => 六百dpi
D2: SCOPE | 動画の取り込み | out of scope
D3: SCOPE | 撮影場所の記録 | in scope
D4: CONFIRM | 原本の貸し出し | not permitted
D5: CHOICE | アルバムの形式 | 冊子
D6: CHOICE | 保存先 | 外付けディスク
D7: SCOPE | 削除ボタンの追加 | out of scope

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
原本を処分する => 原本の処分には家族会議の承認が必要 => 人間

[write_allowlist]
W1: scripts
W2: notes

[forbidden_actions]
家族の写真を外部のサービスに載せる => 写真は家族の外に出さない
