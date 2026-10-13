# PUB-M5 十字の検知 — meter v1 の仕掛けとの照合（offline, API なし）

36 store の保存文 2245。仕掛け: {'contradiction': 216, 'list_trap': 144, 'repeat': 72, 'reversal': 72, 'update': 108}。注記の引用（sid → turn）の組が、その注記の種類に合う仕掛けの2通に入れば hit。

| 注記 | 発火 | 発火した文 | hit | 他の仕掛け | 仕掛けなし | 対なし | 適合率 | 見つかった仕掛け |
|---|---|---|---|---|---|---|---|---|
| SAME_SEAT | 177 | 177 | 147 | 5 | 0 | 25 | 0.831 | 137 / 216 |
| REVERSAL_X | 4 | 4 | 1 | 1 | 0 | 2 | 0.250 | 1 / 72 |
| UPDATE | 15 | 15 | 14 | 1 | 0 | 0 | 0.933 | 14 / 108 |
| ENUMERATION | 472 | 472 | 0 | 141 | 140 | 191 | 0.000 | 0 / 144 |
| REVERSAL | 32 | 32 | 12 | 6 | 2 | 12 | 0.375 | 12 / 72 |
| SAME_QUESTION | 292 | 292 | 138 | 10 | 29 | 115 | 0.473 | 116 / 216 |

「他の仕掛け」の内訳（種類別）:
- SAME_SEAT: {'repeat': 3, 'reversal': 2}
- REVERSAL_X: {'contradiction': 1}
- UPDATE: {'contradiction': 1}
- ENUMERATION: {'contradiction': 129, 'reversal': 12}
- REVERSAL: {'contradiction': 6}
- SAME_QUESTION: {'repeat': 4, 'reversal': 6}

内訳: {'enumeration_arm_owner': 471, 'enumeration_nest': 1, 'reversal_x_key_agrees': 3, 'reversal_x_key_disagrees': 1, 'reversal_x_value': 1, 'reversal_x_の': 3, 'same_seat_F1': 129, 'same_seat_F2': 48, 'update_first': 11, 'update_with_prior': 4}

二つの証人の一致（注記の `witness`）: {'SAME_SEAT': {'agree': 115, 'unreadable': 56, 'cross_only': 3, 'unavailable': 3}, 'REVERSAL_X': {'cross_only': 2, 'agree': 2}, 'SAME_QUESTION': {'agree': 115, 'sq_only': 177}, 'REVERSAL': {'rev_only': 30, 'agree': 2}}

旧 REVERSAL（memfix 保存済み台帳, mem.v3）: 発火 311（仕掛けの反転に当たる 13、適合率 0.042）、仕掛けの反転が引用された 12 / 72。

