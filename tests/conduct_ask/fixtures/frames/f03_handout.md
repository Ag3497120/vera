# 社内勉強会の資料整備（日本語・並列が多い・任意の節なし・矛盾あり）
[goal]
project: 勉強会の配布資料
statement: 社内勉強会の配布資料を章ごとに分担して書き、全体をそろえて配る

[philosophy_invariants]
I1: 未公開の草稿を外部の査読者に送ることはしない
I2: 図版の出典は必ず本文に書く

[completion_criteria]
C1: 全章の用語が用語集と一致する | {"kind":"command_exit","command":["python","tools/check_terms.py"],"expected_exit":0}
C2: 初めて読む人が最後まで読める | human-judged

[phases]
P1: 目次を決める
P2: 第1章を書く
P3: 第2章を書く
P4: 図版を用意する
P5: 全体を校正する

[phase_order]
P1 -> P2: 章の分担は目次から決まる
P1 -> P3: 章の分担は目次から決まる
P1 -> P4: 図版の数は目次から決まる
P2 -> P5: 校正は書き上がった章に対して行う
P3 -> P5: 校正は書き上がった章に対して行う
P4 -> P5: 校正は図版も含めて行う

[decisions]
D1: 配布形式 => PDF
D2: 文体 => です・ます調
D3: 用語集の置き場所 => 巻末

[vocabulary_aliases]
none: none

[escalation_conditions]
none: none

[protected_actions]
外部の査読者に送る => 外部への送付には人間の承認が必要 => 人間
