# 運動会の当日案内（日本語・別名と上げる条件あり）
[goal]
project: 運動会の当日案内
statement: 運動会の当日に保護者が見る案内ページを用意する

[philosophy_invariants]
I1: 児童の名前は案内ページに載せない

[completion_criteria]
C1: 案内ページが携帯で崩れずに開ける | human-judged
C2: 時程表の時刻が先生の資料と一致する | {"kind":"command_exit","command":["python","tools/compare_times.py"],"expected_exit":0}

[phases]
P1: 競技の一覧を整える
P2: 時程表を作る
P3: 案内ページを組み立てる
P4: 保護者向けの確認をする

[phase_order]
P1 -> P2: 時程表は競技の一覧から作る
P2 -> P3: 案内ページは時程表を載せる
P3 -> P4: 確認は組み立てた案内ページで行う

[decisions]
D1: 雨天順延 => 翌日に延期
D2: SCOPE | 写真の掲載 | out of scope
D3: SCOPE | 駐車場の案内 | in scope
D4: CHOICE | 文字の大きさ | 大きめ
D5: CONFIRM | 先生向けの試験公開 | permitted

[vocabulary_aliases]
競技表 => 競技の一覧
タイムテーブル => 時程表
雨の日の扱い => 雨天順延

[escalation_conditions]
E1: 児童の学年別の人数を載せる => 個人が特定されうる => 人間 => ANY

[protected_actions]
案内ページを公開する => 公開には校長の承認が必要 => 人間
