# PUB-M5/M6 — bank_ls dev（2 本、モデルなし、offline）

各メッセージを 1 書き込み（64 字超は「。」で切る）、セッションごとに mem.v4 の store、題名を主題に宣言。F0 の拒否は数えるだけ（keep_unshaped なし）。

| 物語 | セッション | メッセージ | 書き込み | 受理 | F0 | 他の拒否 | 織りの拒否（受理のうち） | 記憶の文 | 秒 |
|---|---|---|---|---|---|---|---|---|---|
| LS-D01 | 16 | 160 | 640 | 237 (37.0 %) | 403 (63.0 %) | {} | 137 (57.8 %) | 237 | 59.3 |
| LS-D02 | 14 | 115 | 805 | 344 (42.7 %) | 461 (57.3 %) | {} | 115 (33.4 %) | 344 | 82.8 |

F0 の理由（節）: {'case_before_topic': 9, 'coordination': 12, 'gap_is_not_a_particle': 745, 'negated': 9, 'no_predicate': 111, 'no_relation': 89, 'repeated_case_particle': 12, 'value_not_noun': 2}

## 検知（十字の注記）と仕掛け

| 注記 | 発火 | hit | 他の仕掛け | 仕掛けなし | 対なし | 見つかった仕掛け |
|---|---|---|---|---|---|---|
| SAME_SEAT | 18 | 11 | {} | 7 | 0 | 11 / 24 |
| REVERSAL_X | 8 | 8 | {} | 0 | 0 | 8 / 8 |
| UPDATE | 16 | 15 | {} | 1 | 0 | 15 / 16 |
| ENUMERATION | 10 | 7 | {} | 3 | 0 | 7 / 16 |

仕掛けの数: {'contradiction': 24, 'update': 16, 'list_trap': 16, 'reversal': 8, 'repeat': 12}。内訳: {'enumeration_arm_owner': 10, 'reversal_x_key_agrees': 8, 'update_with_prior': 8, 'update_first': 8}

## 想起（チェックポイントの問い）

- absent: {'admitted': 0, 'n': 16, 'parsed': 8, 'route_None': 16, 'verdict_NONE': 16}
- contradiction: {'form_rephrased_n': 23, 'form_rephrased_reached': 0, 'form_same_n': 1, 'form_same_reached': 1, 'lenient_exact': 1, 'lenient_extra': 0, 'lenient_reached': 1, 'n': 24, 'parsed': 6, 'route_None': 23, 'route_exact': 1, 'strict_exact': 1, 'strict_extra': 0, 'strict_reached': 1, 'verdict_CHOICE': 1, 'verdict_NONE': 23}
- plain: {'form_rephrased_n': 20, 'form_rephrased_reached': 0, 'form_same_n': 4, 'form_same_reached': 4, 'lenient_exact': 4, 'lenient_extra': 0, 'lenient_reached': 4, 'n': 24, 'parsed': 11, 'route_None': 20, 'route_exact': 4, 'strict_exact': 4, 'strict_extra': 0, 'strict_reached': 4, 'verdict_ANSWER': 4, 'verdict_NONE': 20}
- update: {'form_rephrased_n': 15, 'form_rephrased_reached': 0, 'form_same_n': 1, 'form_same_reached': 1, 'lenient_exact': 1, 'lenient_extra': 0, 'lenient_reached': 1, 'n': 16, 'parsed': 7, 'route_None': 15, 'route_exact': 1, 'strict_exact': 1, 'strict_extra': 0, 'strict_reached': 1, 'verdict_NONE': 15, 'verdict_UPDATED': 1}
