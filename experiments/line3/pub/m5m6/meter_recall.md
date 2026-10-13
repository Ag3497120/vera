# PUB-M6 想起（十字）の到達 — meter v1（offline, API なし）

meter v1 の構造 arm 36 run（360 問）の書き込みを mem.v4 の store に流し直し（モデルの raw write をそのまま、turn つき）、回答 run memanswer.v3 の `recall` を質問文のまま呼ぶ oracle。

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

verdict（種類/verdict）: {'contradicted/ANSWER': 36, 'contradicted/CHOICE': 75, 'contradicted/NONE': 32, 'contradicted/UPDATED': 1, 'plain/ANSWER': 75, 'plain/NONE': 33, 'updated/ANSWER': 54, 'updated/CHOICE': 12, 'updated/NONE': 41, 'updated/UPDATED': 1}

route: {'class': 58, 'exact': 147, 'flat': 23, 'nest': 26, 'none': 106}

issues（NONE の理由）: {'no_event_clause': 5, 'no_position': 100, 'no_slot_noun_matches': 95, 'question_unparsed:no_question_word': 6}

### 見つかった値は出せるか（到達した問いだけ。出口の門は変えていない: weave_span で引用 → emit）

{'contradicted/contested_available': 75, 'plain/emit_refused': 47, 'plain/emitted_right': 28, 'updated/emit_refused': 37, 'updated/emitted_right': 14, 'updated/emitted_wrong': 16}

出せなかった理由: {'no_evidence:no_slot_head': 8, 'no_evidence:no_subject': 6, 'no_evidence:question_has_no_subject': 54, 'no_evidence:question_has_no_subject,no_slot_head': 1, 'no_evidence:question_has_no_subject,not_copular': 5, 'no_evidence:wrong_arm,no_slot_head': 10}

