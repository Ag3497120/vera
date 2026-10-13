# PUB-M6 想起（十字）の到達 — meter v1（offline, API なし）

meter v1 の構造 arm 36 run（360 問）の書き込みを mem.v4 の store に流し直し（モデルの raw write をそのまま、turn つき）、回答 run memanswer.v4（PUB-M6c） の `recall` を質問文のまま呼ぶ oracle。

### 厳密一致の照合

| 質問の種類 | n | 到達 | 厳密一致 | 余計な値あり | memfix 到達 前 | memfix 到達 後 |
|---|---|---|---|---|---|---|
| 矛盾質問 | 144 | 69 | 69 | 6 | 7 | 32 |
| 更新質問 | 108 | 67 | 55 | 12 | 21 | 50 |
| 平文質問 | 108 | 75 | 75 | 0 | 33 | 62 |
| **全体** | 360 | 211 | 199 | 18 | 61 | 144 |

### 寛容な照合（数値の後ろの単位の差を許す）

| 質問の種類 | n | 到達 | 厳密一致 | 余計な値あり |
|---|---|---|---|---|
| 矛盾質問 | 144 | 75 | 75 | 0 |
| 更新質問 | 108 | 67 | 55 | 12 |
| 平文質問 | 108 | 75 | 75 | 0 |
| **全体** | 360 | 217 | 205 | 12 |

verdict（種類/verdict）: {'contradicted/ANSWER': 36, 'contradicted/CANDIDATES': 32, 'contradicted/CHOICE': 75, 'contradicted/UPDATED': 1, 'plain/ANSWER': 75, 'plain/CANDIDATES': 27, 'plain/NONE': 6, 'updated/ANSWER': 54, 'updated/CANDIDATES': 32, 'updated/CHOICE': 12, 'updated/NONE': 9, 'updated/UPDATED': 1}

route: {'class': 58, 'exact': 147, 'flat': 23, 'nest': 26, 'none': 106}

issues（NONE の理由）: {'no_event_clause': 5, 'no_position': 100, 'no_slot_noun_matches': 95, 'question_unparsed:no_question_word': 6}

### 見つかった値は出せるか（到達した問いだけ。出口の門は変えていない: weave_span で引用 → emit）

{'contradicted/contested_available': 5, 'contradicted/contested_refused': 70, 'plain/emit_refused': 43, 'plain/emitted_right': 32, 'updated/emit_refused': 33, 'updated/emitted_right': 34}

出せなかった理由: {'contested_value': 70, 'contested_value:': 12, 'no_evidence:no_slot_head': 8, 'no_evidence:no_subject': 6, 'no_evidence:question_has_no_subject': 34, 'no_evidence:question_has_no_subject,no_slot_head': 1, 'no_evidence:question_has_no_subject,not_copular': 5, 'no_evidence:wrong_arm,no_slot_head': 10}

完成した問い（via）で出せた: {'nest': 11, 'update': 2}。完成した問いでも門が断った理由: {'nest:no_subject': 34, 'nest:no_subject,not_copular': 2}

置き換えられた値の赤チーム（UPDATED の問いごとに、history の各値を引用して emit を試す。`EMITTED_OLD` が古い値の誤出力）: {'questions': 2, 'tried': 2, 'weave_refused:replaced_value': 2}

### PUB-M6c（shape.v3 / ask.v3 / qwords.v2、回答 run memanswer.v4、門 evidence.v6）

- 出せた（正）: 66、出せた（誤）: 0、そのうち句読点つきの値を元の文の範囲のまま出した: 22（正 22、誤 0）
- 食い違い質問（同じ席の CHOICE）: 片方を出そうとして `contested_value` で拒否 70、拒否されず片方が出た 0（0 でなければならない）
- CANDIDATES を示した問い: 91（候補の総数 168）、そのうち金が候補の中にある 91、金が 1 位 90、先頭が同点 25
- **ORACLE 上限（先頭の候補だけを確かめる「モデル」。モデルの結果ではない）**: 橋を張って答えた 86、金に到達 74（厳密 72）、金に届かず 12；橋で見つけた値を門に通した結果: {'contested_available': 20, 'emit_refused': 35, 'emitted_right': 19}

