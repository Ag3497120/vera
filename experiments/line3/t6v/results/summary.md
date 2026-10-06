## T6v results (S300, placement level mid, search budget 64/8, same 90 fixed questions)

### Tier RUN

(1) strict grading (T0 grader 7.2: adopted read-out candidate; list = abstention; unanswerable answered = wrong)

| system | questions | correct/wrong/abstain (answerable) | unanswerable answered (fict+attr) | of which wrong | read-out verdicts | cycle unit answer: correct/wrong/abstain, unanswerable answered |
|---|---|---|---|---|---|---|
| T0 legacy a1 | 90 | 45/7/8 | 3+8 | 11 | - | - |
| T0 legacy a2 | 90 | 44/9/7 | 0+10 | 10 | - | - |
| baseline (T5/T6 stored) | 90 | 0/0/60 | 0+0 | 0 | {'CHOICE': 75, 'None': 15} | 0/48/12, 8 |
| baseline re-run (check) | 90 | 0/0/60 | 0+0 | 0 | {'CHOICE': 75, 'None': 15} | 0/48/12, 8 |
| V1 | 90 | 0/0/60 | 0+0 | 0 | {'CHOICE': 30, 'None': 60} | 0/14/46, 15 |
| V2 | 33 | 0/0/24 | 0+0 | 0 | {'CHOICE': 28, 'None': 5} | 0/0/24, 0 |
| V3 | 90 | 0/0/60 | 0+0 | 0 | {'CHOICE': 75, 'None': 15} | 0/0/60, 0 |
| V123 | 90 | 0/0/60 | 0+0 | 0 | {'CHOICE': 42, 'None': 48} | 3/24/33, 5 |

(2) diagnostic: gold string in the read-out, answerable questions only (a01..a60 for RUN)

| system | answerable | with an adopted state | gold in some candidate sentence | gold in some single section path | gold in union of path words | gold in the cycle's unit answer | gold held in subject's sentences |
|---|---|---|---|---|---|---|---|
| baseline (T5/T6 stored) | 60 | 60 | 1 | 1 | 1 | 0 | 58 |
| baseline re-run (check) | 60 | 60 | 1 | 1 | 1 | 0 | 58 |
| V1 | 60 | 15 | 4 | 4 | 4 | 1 | 58 |
| V2 | 24 | 24 | 3 | 3 | 3 | 1 | 24 |
| V3 | 60 | 60 | 23 | 23 | 23 | 6 | 58 |
| V123 | 60 | 33 | 28 | 28 | 28 | 6 | 58 |

(3) question-dependence and (4) function-word-only paths, plus size of the read-out

| system | questions with a read-out | distinct content-word sets across them | distinct adopted-state sets (union of path words incl. function words) | function-only paths, first 3 states (T6 metric) | function-only paths, all states | adopted states per question min/median/max | listed sentences min/median/max |
|---|---|---|---|---|---|---|---|
| baseline (T5/T6 stored) | 75 | 2 | 2 | 1008 / 1350 (74.7%) | n/a (only first 3 states stored) | 6/13/13 | 40/9360/9360 |
| baseline re-run (check) | 75 | 2 | 2 | 1008 / 1350 (74.7%) | 2912 / 5052 (57.6%) | 6/13/13 | 40/9360/9360 |
| V1 | 30 | 11 | 12 | 379 / 498 (76.1%) | 779 / 1476 (52.8%) | 1/5/36 | 40/3600/9360 |
| V2 | 28 | 3 | 2 | 0 / 504 (0.0%) | 0 / 7572 (0.0%) | 21/49/49 | 160/8640/8640 |
| V3 | 75 | 23 | 7 | 9 / 1106 (0.8%) | 17500 / 1877119 (0.9%) | 156/5310/5342 | 76972/1855318/1856219 |
| V123 | 42 | 34 | 33 | 0 / 445 (0.0%) | 0 / 83315 (0.0%) | 1/1/3546 | 6/720/64960 |

#### Same table restricted to the 33 questions on which V2 finished (V2 is ~4x costlier than the others: see wall times)

### Tier RUN (V2 subset)

(1) strict grading (T0 grader 7.2: adopted read-out candidate; list = abstention; unanswerable answered = wrong)

| system | questions | correct/wrong/abstain (answerable) | unanswerable answered (fict+attr) | of which wrong | read-out verdicts | cycle unit answer: correct/wrong/abstain, unanswerable answered |
|---|---|---|---|---|---|---|
| baseline (T5/T6 stored) | 33 | 0/0/24 | 0+0 | 0 | {'CHOICE': 28, 'None': 5} | 0/18/6, 2 |
| baseline re-run (check) | 33 | 0/0/24 | 0+0 | 0 | {'CHOICE': 28, 'None': 5} | 0/18/6, 2 |
| V1 | 33 | 0/0/24 | 0+0 | 0 | {'CHOICE': 9, 'None': 24} | 0/5/19, 4 |
| V2 | 33 | 0/0/24 | 0+0 | 0 | {'CHOICE': 28, 'None': 5} | 0/0/24, 0 |
| V3 | 33 | 0/0/24 | 0+0 | 0 | {'CHOICE': 28, 'None': 5} | 0/0/24, 0 |
| V123 | 33 | 0/0/24 | 0+0 | 0 | {'CHOICE': 16, 'None': 17} | 2/9/13, 2 |

(2) diagnostic: gold string in the read-out, answerable questions only (a01..a60 for RUN)

| system | answerable | with an adopted state | gold in some candidate sentence | gold in some single section path | gold in union of path words | gold in the cycle's unit answer | gold held in subject's sentences |
|---|---|---|---|---|---|---|---|
| baseline (T5/T6 stored) | 24 | 24 | 0 | 0 | 0 | 0 | 24 |
| baseline re-run (check) | 24 | 24 | 0 | 0 | 0 | 0 | 24 |
| V1 | 24 | 5 | 0 | 0 | 0 | 0 | 24 |
| V2 | 24 | 24 | 3 | 3 | 3 | 1 | 24 |
| V3 | 24 | 24 | 9 | 9 | 9 | 2 | 24 |
| V123 | 24 | 14 | 12 | 12 | 12 | 3 | 24 |

(3) question-dependence and (4) function-word-only paths, plus size of the read-out

| system | questions with a read-out | distinct content-word sets across them | distinct adopted-state sets (union of path words incl. function words) | function-only paths, first 3 states (T6 metric) | function-only paths, all states | adopted states per question min/median/max | listed sentences min/median/max |
|---|---|---|---|---|---|---|---|
| baseline (T5/T6 stored) | 28 | 2 | 2 | 360 / 504 (71.4%) | n/a (only first 3 states stored) | 6/13/13 | 40/9360/9360 |
| baseline re-run (check) | 28 | 2 | 2 | 360 / 504 (71.4%) | 1040 / 1848 (56.3%) | 6/13/13 | 40/9360/9360 |
| V1 | 9 | 5 | 5 | 123 / 150 (82.0%) | 237 / 354 (66.9%) | 2/5/13 | 180/3600/9360 |
| V2 | 28 | 3 | 2 | 0 / 504 (0.0%) | 0 / 7572 (0.0%) | 21/49/49 | 160/8640/8640 |
| V3 | 28 | 14 | 5 | 0 / 404 (0.0%) | 6486 / 684395 (0.9%) | 162/5197/5342 | 77600/1846036/1856218 |
| V123 | 16 | 15 | 14 | 0 / 168 (0.0%) | 0 / 6702 (0.0%) | 1/1/282 | 20/720/34380 |

Baseline re-run equals the stored T5 answer (verdict, units, adopted-state trace) on 90 / 90 questions.

### Tier WORD

(1) strict grading (T0 grader 7.2: adopted read-out candidate; list = abstention; unanswerable answered = wrong)

| system | questions | correct/wrong/abstain (answerable) | unanswerable answered (fict+attr) | of which wrong | read-out verdicts | cycle unit answer: correct/wrong/abstain, unanswerable answered |
|---|---|---|---|---|---|---|
| baseline (T5/T6 stored) | 30 | 0/0/20 | 0+0 | 0 | {'CHOICE': 30} | 0/20/0, 10 |
| V123 | 30 | 0/0/20 | 0+0 | 0 | {'CHOICE': 20, 'None': 10} | 0/7/13, 5 |

(2) diagnostic: gold string in the read-out, answerable questions only (a01..a60 for RUN)

| system | answerable | with an adopted state | gold in some candidate sentence | gold in some single section path | gold in union of path words | gold in the cycle's unit answer | gold held in subject's sentences |
|---|---|---|---|---|---|---|---|
| baseline (T5/T6 stored) | 20 | 20 | 0 | 0 | 0 | 0 | 20 |
| V123 | 20 | 14 | 3 | 3 | 1 | 0 | 20 |

(3) question-dependence and (4) function-word-only paths, plus size of the read-out

| system | questions with a read-out | distinct content-word sets across them | distinct adopted-state sets (union of path words incl. function words) | function-only paths, first 3 states (T6 metric) | function-only paths, all states | adopted states per question min/median/max | listed sentences min/median/max |
|---|---|---|---|---|---|---|---|
| baseline (T5/T6 stored) | 30 | 3 | 3 | 4 / 354 (1.1%) | n/a (only first 3 states stored) | 1/2/3 | 720/1440/2160 |
| V123 | 20 | 12 | 12 | 0 / 356 (0.0%) | 0 / 14036 (0.0%) | 5/11/930 | 200/740/75400 |

Wall times:
- Q_F1_RUN_1.log: QUEUE_DONE worker 22010 questions 11 wall 5234.2 (questions logged: 6)
- Q_F1_RUN_2.log: QUEUE_DONE worker 22011 questions 11 wall 5280.5 (questions logged: 6)
- Q_F1_RUN_3.log: QUEUE_DONE worker 22012 questions 11 wall 5245.7 (questions logged: 6)
- Q_F1_RUN_4.log: QUEUE_DONE worker 22013 questions 11 wall 5078.1 (questions logged: 6)
- Q_F1_RUN_5.log: QUEUE_DONE worker 22014 questions 11 wall 5141.1 (questions logged: 6)
- Q_F1_RUN_6.log: QUEUE_DONE worker 22015 questions 11 wall 5255.8 (questions logged: 6)
- Q_V123_RUN.log: QUEUE_DONE worker 22016 questions 86 wall 1289.2 (questions logged: 56)
- Q_V2_RUN_1.log: stopped by the experimenter (questions logged: 4)
- Q_V2_RUN_10.log: stopped by the experimenter (questions logged: 0)
- Q_V2_RUN_2.log: stopped by the experimenter (questions logged: 4)
- Q_V2_RUN_3.log: stopped by the experimenter (questions logged: 4)
- Q_V2_RUN_4.log: stopped by the experimenter (questions logged: 3)
- Q_V2_RUN_5.log: stopped by the experimenter (questions logged: 0)
- Q_V2_RUN_6.log: stopped by the experimenter (questions logged: 2)
- Q_V2_RUN_7.log: stopped by the experimenter (questions logged: 1)
- Q_V2_RUN_8.log: stopped by the experimenter (questions logged: 1)
- Q_V2_RUN_9.log: stopped by the experimenter (questions logged: 1)
- Q_V123_WORD.log: QUEUE_DONE worker 22205 questions 30 wall 1385.7 (questions logged: 20)

### (5) Chance control: gold of question i against the read-out words of question j (answerable, RUN)

| system | matched pairs hit (i = j) | mismatched pairs hit (i != j), mean per question | ratio |
|---|---|---|---|
| baseline | 1 / 60 (0.02) | 0.01 | 1.3 |
| V1 | 4 / 15 (0.27) | 0.00 | inf |
| V2 | 3 / 24 (0.12) | 0.15 | 0.8 |
| V3 | 23 / 60 (0.38) | 0.36 | 1.1 |
| V123 | 28 / 33 (0.85) | 0.01 | 68.9 |

### (6) Three read-out examples of V123 (RUN)

- **a02** 半田岩はどこにありますか  gold = 徳島県|三好市  (cycle unit answer: ANSWER ['景勝地']; adopted states 1; listed sentences 720; gold in a path: True)
    - section 0 (query unit 半田岩): 黒川谷川 / 景勝地
    - section 1 (query unit None): はんだいわ / 景勝地
    - section 2 (query unit None): はんだいわ / 半田岩 / 景勝地
    - section 3 (query unit None): はんだいわ / 半田岩 / 徳島県三好市山城町頼広 / 景勝地
    - section 4 (query unit None): 半田岩 / 徳島県三好市山城町頼広 / 黒川谷川 / 景勝地
    - section 5 (query unit None): 徳島県三好市山城町頼広 / 黒川谷川 / 景勝地
    - first listed sentences: はんだいわ半田岩徳島県三好市山城町頼広景勝地はんだいわ半田岩景勝地はんだいわ景勝地半田岩徳島県三好市山城町頼広黒川谷川景 | はんだいわ半田岩徳島県三好市山城町頼広景勝地はんだいわ半田岩景勝地はんだいわ景勝地半田岩徳島県三好市山城町頼広黒川谷川景 | はんだいわ半田岩徳島県三好市山城町頼広景勝地はんだいわ半田岩景勝地はんだいわ景勝地徳島県三好市山城町頼広黒川谷川景勝地半
- **a39** ブリティッシュ・エアウェイズとは何ですか  gold = 航空会社  (cycle unit answer: ANSWER ['イギリス']; adopted states 1; listed sentences 720; gold in a path: True)
    - section 0 (query unit ブリティッシュ): 最大 / イギリス
    - section 1 (query unit エアウェイズ): 航空会社 / イギリス
    - section 2 (query unit None): 航空会社 / エアウェイズ / イギリス
    - section 3 (query unit None): 航空会社 / エアウェイズ / ブリティッシュ / イギリス
    - section 4 (query unit None): エアウェイズ / ブリティッシュ / 最大 / イギリス
    - section 5 (query unit None): ブリティッシュ / 最大 / イギリス
    - first listed sentences: エアウェイズブリティッシュ最大イギリスブリティッシュ最大イギリス最大イギリス航空会社イギリス航空会社エアウェイズイギリス | エアウェイズブリティッシュ最大イギリスブリティッシュ最大イギリス最大イギリス航空会社イギリス航空会社エアウェイズブリティ | エアウェイズブリティッシュ最大イギリスブリティッシュ最大イギリス最大イギリス航空会社エアウェイズイギリス航空会社イギリス
- **a11** テレゴ県はどこの国にありますか  gold = ウガンダ  (cycle unit answer: CHOICE ['イタリア', 'コマルカ', 'コルーニャ', '北部', '州ア', '県']; adopted states 2685; listed sentences 24927; gold in a path: False)
    - section 0 (query unit テレゴ): 共和国ロンバルディア / 州ブレシア / イタリア
    - section 1 (query unit 県): 400人 / 基礎自治体 / イタリア
    - section 2 (query unit 国): 400人 / 基礎自治体 / イタリア
    - section 3 (query unit None): 400人 / 基礎自治体 / イタリア
    - section 4 (query unit None): 共和国ロンバルディア / 州ブレシア / イタリア
    - section 5 (query unit None): 共和国ロンバルディア / 州ブレシア / イタリア
    - first listed sentences: 400人コムーネイタリア400人コムーネイタリア400人コムーネイタリアセニーガ人口約1イタリアセニーガ人口約1イタリア | 400人コムーネイタリア400人コムーネイタリア400人コムーネイタリアセニーガ共和国ロンバルディアイタリアセニーガ共和 | 400人コムーネイタリア400人コムーネイタリア400人コムーネイタリアセニーガ州ブレシアイタリアセニーガ州ブレシアイタ
