# 読み聞かせ会の当番表（日本語・取り置き枠・禁止と優先順位あり・別名あり）
[goal]
project: 読み聞かせ当番表
statement: 読み聞かせ会の当番を決めて、前日に担当者へ知らせる仕組みを作る

[philosophy_invariants]
I1: 当番は本人の同意なしに確定しない
I2: 担当者の予定は他の担当者に見せない

[completion_criteria]
C1: 同じ日に二人が重ならない | {"kind":"command_exit","command":["make","check-duty"],"expected_exit":0}
C2: 世話人が一人で当番表を直せる | human-judged

[phases]
P1: 担当者の名簿を整える
P2: 当番の割り振りを作る
P3: 前日の連絡を実装する
P4: 世話人向けの手引きを書く

[phase_order]
P1 -> P2: 割り振りは名簿の人から選ぶ
P2 -> P3: 連絡は割り振りの結果を使う
P2 -> P4: 手引きは割り振りの操作を説明する

[decisions]
D1: 当番の周期 => 月に一度
D2: SCOPE | 欠席時の代役の手配 | in scope
D3: SCOPE | 図書の貸出管理 | out of scope
D4: CONFIRM | 担当者への試験の連絡 | permitted
D5: CHOICE | 連絡の手段 | 電子メール

[vocabulary_aliases]
割り振り表 => 当番の割り振り
お知らせ => 前日の連絡

[escalation_conditions]
none: none

[protected_actions]
担当者の予定を共有する => 予定の共有には本人の承認が必要 => 人間

[write_allowlist]
W1: duty
W2: manual

[forbidden_actions]
名簿を別の団体に渡す => 名簿の目的外の利用は認めていない

[conflict_precedence]
R1: forbidden_actions > protected_actions: 禁止は承認でも覆らない
