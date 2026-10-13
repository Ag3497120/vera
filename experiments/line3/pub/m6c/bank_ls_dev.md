# PUB-M5/M6 — bank_ls dev（2 本、モデルなし、offline）

各メッセージを 1 書き込み（64 字超は「。」で切る）、セッションごとに mem.v4 の store、題名を主題に宣言。F0 の拒否は数えるだけ（keep_unshaped なし）。

| 物語 | セッション | メッセージ | 書き込み | 受理 | F0 | 他の拒否 | 織りの拒否（受理のうち） | 記憶の文 | 秒 |
|---|---|---|---|---|---|---|---|---|---|
| LS-D01 | 16 | 160 | 640 | 274 (42.8 %) | 366 (57.2 %) | {} | 172 (62.8 %) | 274 | 78.3 |
| LS-D02 | 14 | 115 | 805 | 386 (48.0 %) | 419 (52.0 %) | {} | 132 (34.2 %) | 386 | 105.4 |

F0 の理由（節）: {'case_before_topic': 9, 'coordination': 12, 'gap_is_not_a_particle': 719, 'negated': 9, 'no_predicate': 65, 'no_relation': 30, 'repeated_case_particle': 12, 'value_not_noun': 1}

## 検知（十字の注記）と仕掛け

| 注記 | 発火 | hit | 他の仕掛け | 仕掛けなし | 対なし | 見つかった仕掛け |
|---|---|---|---|---|---|---|
| SAME_SEAT | 25 | 12 | {} | 13 | 0 | 12 / 24 |
| REVERSAL_X | 8 | 8 | {} | 0 | 0 | 8 / 8 |
| UPDATE | 16 | 15 | {} | 1 | 0 | 15 / 16 |
| ENUMERATION | 10 | 7 | {} | 3 | 0 | 7 / 16 |

仕掛けの数: {'contradiction': 24, 'update': 16, 'list_trap': 16, 'reversal': 8, 'repeat': 12}。内訳: {'enumeration_arm_owner': 10, 'reversal_x_key_agrees': 8, 'update_with_prior': 8, 'update_first': 8}

## 想起（チェックポイントの問い）

PUB-M6c（shape.v3 / ask.v3 / qwords.v2）。`candidates_*` = CANDIDATES を示した問い、`oracle_top_*` = **ORACLE の上限（先頭の候補だけを確かめる「モデル」。モデルの結果ではない）**、存在しない問いの `admitted` = 橋なしで答えた数、`oracle_admitted` = 先頭の候補を確かめたら答えが出た数（どちらも 0 でなければならない）。

- absent: {'admitted': 0, 'candidates_offered': 0, 'n': 16, 'oracle_admitted': 0, 'parsed': 12, 'route_None': 16, 'verdict_NONE': 16}
- contradiction: {'candidates_gold_among': 10, 'candidates_gold_rank1': 10, 'candidates_offered': 10, 'candidates_tied_top': 0, 'form_rephrased_n': 23, 'form_rephrased_reached': 0, 'form_same_n': 1, 'form_same_reached': 1, 'lenient_exact': 1, 'lenient_extra': 0, 'lenient_reached': 1, 'n': 24, 'oracle_top_answered': 10, 'oracle_top_exact': 9, 'oracle_top_reached': 9, 'oracle_top_wrong': 1, 'parsed': 16, 'route_None': 23, 'route_exact': 1, 'strict_exact': 1, 'strict_extra': 0, 'strict_reached': 1, 'verdict_CANDIDATES': 10, 'verdict_CHOICE': 1, 'verdict_NONE': 13}
- plain: {'candidates_gold_among': 8, 'candidates_gold_rank1': 8, 'candidates_offered': 8, 'candidates_tied_top': 0, 'form_rephrased_n': 20, 'form_rephrased_reached': 0, 'form_same_n': 4, 'form_same_reached': 4, 'lenient_exact': 4, 'lenient_extra': 0, 'lenient_reached': 4, 'n': 24, 'oracle_top_answered': 8, 'oracle_top_exact': 8, 'oracle_top_reached': 8, 'oracle_top_wrong': 0, 'parsed': 18, 'route_None': 20, 'route_exact': 4, 'strict_exact': 4, 'strict_extra': 0, 'strict_reached': 4, 'verdict_ANSWER': 4, 'verdict_CANDIDATES': 8, 'verdict_NONE': 12}
- update: {'candidates_gold_among': 6, 'candidates_gold_rank1': 5, 'candidates_offered': 7, 'candidates_tied_top': 1, 'form_rephrased_n': 15, 'form_rephrased_reached': 0, 'form_same_n': 1, 'form_same_reached': 1, 'lenient_exact': 1, 'lenient_extra': 0, 'lenient_reached': 1, 'n': 16, 'oracle_top_answered': 7, 'oracle_top_exact': 5, 'oracle_top_reached': 5, 'oracle_top_wrong': 2, 'parsed': 12, 'route_None': 15, 'route_exact': 1, 'strict_exact': 1, 'strict_extra': 0, 'strict_reached': 1, 'verdict_CANDIDATES': 7, 'verdict_NONE': 8, 'verdict_UPDATED': 1}
