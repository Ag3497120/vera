## T6x A (S300 RUN, default space V2, V3 adoption, official answer object; 90 fixed questions; search budget 64/8; level mid)

(1) strict grading, T0 grader (answerable a01..a60; unanswerable = fict + attr, answered = wrong)

| read rule | grading | correct/wrong/abstain (answerable) | unanswerable answered (fict+attr) | verdicts of the answer |
|---|---|---|---|---|
| query_crosses | B official (path words) | 17/3/40 | 2+2 = 4 | {'ANSWER': 24, 'CHOICE': 18, 'None': 48} |
| query_crosses | B without core-in-subject check | 17/3/40 | 2+2 = 4 | {'ANSWER': 24, 'CHOICE': 18, 'None': 48} |
| query_crosses | A reference (centre) | 2/18/40 | 2+2 = 4 | {'ANSWER': 24, 'CHOICE': 18, 'None': 48} |
| query_share_crosses | B official (path words) | 11/3/46 | 1+2 = 3 | {'ANSWER': 17, 'CHOICE': 45, 'None': 28} |
| query_share_crosses | B without core-in-subject check | 11/3/46 | 1+2 = 3 | {'ANSWER': 17, 'CHOICE': 45, 'None': 28} |
| query_share_crosses | A reference (centre) | 2/12/46 | 1+2 = 3 | {'ANSWER': 17, 'CHOICE': 45, 'None': 28} |

(2) gold in the path words (answerable, 60) and question dependence (gold of question i against the path words of j)

| read rule | with a read-out | gold in some path (any item) | gold in some centre | single-item answers | single-item with gold | matched hit | mismatched hit (mean fraction) | ratio |
|---|---|---|---|---|---|---|---|---|
| query_crosses | 33 | 28 | 6 | 20 | 17 | 28/33 (0.85) | 0.012 | 68.9 |
| query_share_crosses | 49 | 28 | 6 | 14 | 11 | 28/49 (0.57) | 0.019 | 29.9 |

(3) verdict mix over the 90 questions (cycle verdict -> answer verdict), crosses read, time

| read rule | cycle verdicts | answer verdicts | crosses read min/median/max | per-question secs median/max/sum (8 workers) | trace 100% |
|---|---|---|---|---|---|
| query_crosses | {'AMBIGUOUS': 2, 'ANSWER': 32, 'CHOICE': 10, 'UNKNOWN_NO_EVIDENCE': 33, 'UNKNOWN_NO_FIXED_POINT': 13} | {'ANSWER': 24, 'CHOICE': 18, 'None': 48} | 0/4.0/81 | 0.0/175.8/831 | 42/42 |
| query_share_crosses | {'ANSWER': 25, 'CHOICE': 37, 'UNKNOWN_NO_EVIDENCE': 17, 'UNKNOWN_NO_FIXED_POINT': 11} | {'ANSWER': 17, 'CHOICE': 45, 'None': 28} | 0/15.0/187 | 6.3/314.0/3292 | 62/62 |

(4) the 48 questions without an adopted state under the default: what the share rule does

| default cycle verdict | n | share rule: still no state | share rule: answer verdict mix | gold in path (answerable, with read-out) |
|---|---|---|---|---|
| AMBIGUOUS | 2 | 0 | {'CHOICE': 2} | 0/2 |
| UNKNOWN_NO_EVIDENCE | 33 | 18 | {'no state: UNKNOWN_NO_FIXED_POINT': 1, 'CHOICE': 14, 'no state: UNKNOWN_NO_EVIDENCE': 17, 'ANSWER': 1} | 0/12 |
| UNKNOWN_NO_FIXED_POINT | 13 | 10 | {'CHOICE': 3, 'no state: UNKNOWN_NO_FIXED_POINT': 10} | 0/2 |

Questions that HAD a state under the default and whose answer changed under the share rule: 14 / 42

(5) crosses read: extra crosses of group 2 per question (share rule), min/median/max: 0/10.0/124; questions with 0 extra: 26

(6) examples

- **a01** `遊眠とは何ですか` gold=漫画家 subject=遊眠 | default: UNKNOWN_NO_FIXED_POINT -> share: CHOICE / CHOICE, 853 item(s), 61 crosses read
    - reference centre: キューバ
        - section 0 (question unit 遊眠): ダムジ / 武装トローラー / キューバ
        - section 1 (question unit None): ダムジ / 武装トローラー / キューバ
        - section 2 (question unit None): ダムジ / 武装トローラー / 日本国大使館 / 大使館 / キューバ
        - section 3 (question unit None): 日本国大使館 / 大使館 / 海軍 / 艦級 / キューバ
        - section 4 (question unit None): 日本国大使館 / 大使館 / 海軍 / 艦級 / キューバ
        - section 5 (question unit None): 海軍 / 艦級 / キューバ
        - source sentences (sid: units): 133: 在ハイチ日本国大使館ハイチ首都ポルトープランス郊外ペシオンヴィル日本大使館; 139: 岡崎建設おかざきけんせつ広島県安芸高田市本拠く日本薪ストーブメーカー鉄工所建設会社; 232: 在キューバ日本国大使館キューバ首都ハバナ日本大使館
- **a04** `HONEY BADGERとは何ですか` gold=バンド subject=HONEY BADGER | default: UNKNOWN_NO_EVIDENCE -> share: CHOICE / CHOICE, 853 item(s), 62 crosses read
    - reference centre: キューバ
        - section 0 (question unit HONEY): ダムジ / 武装トローラー / キューバ
        - section 1 (question unit BADGER): ダムジ / 武装トローラー / キューバ
        - section 2 (question unit None): ダムジ / 武装トローラー / 日本国大使館 / 大使館 / キューバ
        - section 3 (question unit None): 日本国大使館 / 大使館 / 海軍 / 艦級 / キューバ
        - section 4 (question unit None): 日本国大使館 / 大使館 / 海軍 / 艦級 / キューバ
        - section 5 (question unit None): 海軍 / 艦級 / キューバ
        - source sentences (sid: units): 133: 在ハイチ日本国大使館ハイチ首都ポルトープランス郊外ペシオンヴィル日本大使館; 139: 岡崎建設おかざきけんせつ広島県安芸高田市本拠く日本薪ストーブメーカー鉄工所建設会社; 232: 在キューバ日本国大使館キューバ首都ハバナ日本大使館
- **a08** `世俗教育とは何ですか` gold=学校教育|非宗教 subject=世俗教育 | default: UNKNOWN_NO_EVIDENCE -> share: CHOICE / CHOICE, 498 item(s), 7 crosses read
    - reference centre: を指す
        - section 0 (question unit 世俗教育): そとだんねつ / 外側 / を指す
        - section 1 (question unit None): そとだんねつ / 外側 / を指す
        - section 2 (question unit None): そとだんねつ / 外側 / を指す
        - section 3 (question unit None): 外断熱 / 構造 / を指す
        - section 4 (question unit None): 外断熱 / 構造 / を指す
        - section 5 (question unit None): 外断熱 / 構造 / を指す
        - source sentences (sid: units): 75: 外断熱そとだんねつ断熱層建物外側設構造工法を指す
- **a02** `半田岩はどこにありますか` gold=徳島県|三好市 subject=半田岩 | default: ANSWER -> share: ANSWER / ANSWER, 1 item(s), 5 crosses read
    - reference centre: 景勝地
        - section 0 (question unit 半田岩): 黒川谷川 / 景勝地
        - section 1 (question unit None): はんだいわ / 景勝地
        - section 2 (question unit None): はんだいわ / 半田岩 / 景勝地
        - section 3 (question unit None): はんだいわ / 半田岩 / 徳島県三好市山城町頼広 / 景勝地
        - section 4 (question unit None): 半田岩 / 徳島県三好市山城町頼広 / 黒川谷川 / 景勝地
        - section 5 (question unit None): 徳島県三好市山城町頼広 / 黒川谷川 / 景勝地
        - source sentences (sid: units): 4: 半田岩はんだいわ徳島県三好市山城町頼広黒川谷川景勝地
