## T6w results (S300 RUN, new defaults V1+V2+V3, new answer form; 90 fixed questions; search budget 64/8; level mid)

(1) strict grading, T0 grader (answerable a01..a60; unanswerable = fict + attr, answered = wrong)

| system | correct/wrong/abstain (answerable) | unanswerable answered (fict+attr) | of which wrong | answer verdicts |
|---|---|---|---|---|
| T0 legacy a1 | 45/7/8 | 3+8 | 11 | - |
| T0 legacy a2 | 44/9/7 | 0+10 | 10 | - |
| T6w rule A (answer = agreed centre unit) | 2/18/40 | 2+2 | 4 | {'ANSWER': 24, 'CHOICE': 18, 'None': 48} |
| T6w rule B (answer counts if gold in the path words) | 17/3/40 | 2+2 | 4 | {'ANSWER': 24, 'CHOICE': 18, 'None': 48} |
| T6w rule B without the core-in-subject check | 17/3/40 | 2+2 | 4 | {'ANSWER': 24, 'CHOICE': 18, 'None': 48} |

(2) diagnostic: gold in the answer, answerable questions (60)

| answerable | with an adopted state / read-out | gold in some path (any item) | gold in some centre (any item) | single-item answers | single-item with gold in its paths | gold held in the subject's sentences |
|---|---|---|---|---|---|---|
| 60 | 33 | 28 | 6 | 20 | 17 | 58 |

(3) question dependence: gold of question i against the path words of question j (answerable questions with a read-out)

| matched hit (i = j) | mismatched hit, mean fraction per read-out (i != j) | ratio |
|---|---|---|
| 28 / 33 (0.85) | 0.012 | 68.9 |

Distinct answers (centre + path words, whole answer) across the 33 read-outs of answerable questions: 30. Distinct centres: 44.

(4) list sizes, time

- questions: 90; with a read-out: 42 (ANSWER 24, list/CHOICE 18, UNKNOWN_NO_PATH 0); no adopted state: 48 (cycle verdicts of those: {'UNKNOWN_NO_FIXED_POINT': 13, 'UNKNOWN_NO_EVIDENCE': 33, 'AMBIGUOUS': 2})
- items per answer (distinct (centre, paths)) min/median/max: 1/1.0/1056; adopted states per question min/median/max: 1/1.0/3546
- list sizes (CHOICE answers only) min/median/max: 2/159.5/1056; too_many flagged: 15
- trace check: 42 / 42 read-outs 100% (words traced 92334 / 92334); failures: 0
- per-question time (s, ask + read-out + trace, one process, 9 questions running in parallel on 10 cores) min/median/max/sum: 0.00 / 0.01 / 173.49 / 834.5
- crosses read per question min/median/max: 0/4.0/81

(5) answer examples (S300 RUN)

- **a02** `半田岩はどこにありますか`  gold = 徳島県|三好市  subject = 半田岩  | cycle: ANSWER ['景勝地'] | answer: ANSWER, 1 item(s)
    - centre **景勝地**
        - section 0 (question unit 半田岩): 黒川谷川 / 景勝地
        - section 1 (question unit None): はんだいわ / 景勝地
        - section 2 (question unit None): はんだいわ / 半田岩 / 景勝地
        - section 3 (question unit None): はんだいわ / 半田岩 / 徳島県三好市山城町頼広 / 景勝地
        - section 4 (question unit None): 半田岩 / 徳島県三好市山城町頼広 / 黒川谷川 / 景勝地
        - section 5 (question unit None): 徳島県三好市山城町頼広 / 黒川谷川 / 景勝地
- **a07** `湯野上バイパスはどこにありますか`  gold = 福島県|下郷町|南会津郡  subject = 湯野上バイパス  | cycle: ANSWER ['道路'] | answer: ANSWER, 1 item(s)
    - centre **道路**
        - section 0 (question unit 湯野上バイパス): 福島県南会津郡下郷町 / ゆのかみ / バイパス / 道路
        - section 1 (question unit None): ゆのかみ / バイパス / 事業中 / 道路
        - section 2 (question unit None): バイパス / 事業中 / 国道121号 / 道路
        - section 3 (question unit None): 事業中 / 国道121号 / 湯野上バイパス / 道路
        - section 4 (question unit None): 国道121号 / 湯野上バイパス / 福島県南会津郡下郷町 / 道路
        - section 5 (question unit None): 湯野上バイパス / 福島県南会津郡下郷町 / ゆのかみ / 道路
- **a12** `ベクトランは何から作られますか`  gold = 液晶ポリマー|合成繊維  subject = ベクトラン  | cycle: ANSWER ['作'] | answer: ANSWER, 1 item(s)
    - centre **作**
        - section 0 (question unit ベクトラン): 麦パン / むぎ / 作
        - section 1 (question unit 作): むぎ / パン / 作
        - section 2 (question unit None): むぎ / パン / ライ / 作
        - section 3 (question unit None): パン / ライ / ライムギ / 作
        - section 4 (question unit None): ライ / ライムギ / 麦パン / 作
        - section 5 (question unit None): ライムギ / 麦パン / 作
- **a05** `オナンはどの書物に登場しますか`  gold = 創世記|旧約聖書  subject = オナン  | cycle: CHOICE ['ギリシア', '登場'] | answer: CHOICE, 161 item(s)
    - centre **ギリシア**
        - section 0 (question unit オナン): おうさまのみみはろばのみみ / フリギア / ギリシア
        - section 1 (question unit 書物): 物語 / 神話 / ギリシア
        - section 2 (question unit 登場): 物語 / 神話 / ギリシア
        - section 3 (question unit None): 物語 / 神話 / 王様 / 耳 / ギリシア
        - section 4 (question unit None): 王様 / 耳 / おうさまのみみはろばのみみ / フリギア / ギリシア
        - section 5 (question unit None): 王様 / 耳 / おうさまのみみはろばのみみ / フリギア / ギリシア
    - centre **ギリシア**
        - section 0 (question unit オナン): おうさまのみみはろばのみみ / フリギア / ギリシア
        - section 1 (question unit 書物): 物語 / 神話 / ギリシア
        - section 2 (question unit 登場): 物語 / 神話 / ロバ / 王ミダス / ギリシア
        - section 3 (question unit None): 物語 / 神話 / ロバ / 王ミダス / ギリシア
        - section 4 (question unit None): ロバ / 王ミダス / おうさまのみみはろばのみみ / フリギア / ギリシア
        - section 5 (question unit None): おうさまのみみはろばのみみ / フリギア / ギリシア
    - ... 159 more items
- **a11** `テレゴ県はどこの国にありますか`  gold = ウガンダ  subject = テレゴ県  | cycle: CHOICE ['イタリア', 'コマルカ', 'コルーニャ', '北部', '州ア', '県'] | answer: CHOICE, 854 item(s)
    - centre **イタリア**
        - section 0 (question unit テレゴ): 400人 / コムーネ / イタリア
        - section 1 (question unit 県): 400人 / コムーネ / イタリア
        - section 2 (question unit 国): 400人 / コムーネ / イタリア
        - section 3 (question unit None): セニーガ / 人口約1 / イタリア
        - section 4 (question unit None): セニーガ / 人口約1 / イタリア
        - section 5 (question unit None): セニーガ / 人口約1 / イタリア
    - centre **イタリア**
        - section 0 (question unit テレゴ): 400人 / コムーネ / イタリア
        - section 1 (question unit 県): 400人 / コムーネ / イタリア
        - section 2 (question unit 国): 400人 / コムーネ / イタリア
        - section 3 (question unit None): セニーガ / 共和国ロンバルディア / イタリア
        - section 4 (question unit None): セニーガ / 共和国ロンバルディア / イタリア
        - section 5 (question unit None): セニーガ / 共和国ロンバルディア / イタリア
    - ... 852 more items
