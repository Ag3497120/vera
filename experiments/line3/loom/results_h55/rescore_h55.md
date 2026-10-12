# rescore_h55: the same runs under the exact-match headline

Ticket LOOM-span (owner, 2026-10-12): the headline `hit_exact` = the answer text equals a gold alternative after the T9 normalisation; a longer text counts as `hit_cited` only if it appears word for word in a sentence the ledger cites (an ok `read_sentence` / `lookup` result); `hits_text` (substring) and `excess_chars` are secondary columns. Made by `experiments/line3/loom/rescore.py --results experiments/line3/loom/results_h55` from the results files and the ledgers they name; nothing in `experiments/line3/loom/results_h55` was edited (the JSON files keep the score they were written with: `old status`, `old hits_text`).
All 30 ledgers were VERIFIED again before scoring (chain + replay): 30 of 30 are OK and replay IDENTICAL.

| task | mode | old status | old hits_text | new status | hit_exact | hit_cited | hits_text | excess | output (emitted text; a control: its answer line) |
|---|---|---|---|---|---|---|---|---|---|
| I2-001 | ro | hit | Y | miss | N | Y | Y | 4 | 「ハッシュ表ともいう」 |
| I2-001 | ca | miss | N | miss | N | N | N | - | 「ハッシュテーブルは連想配列」 |
| I2-001 | ctl | abstained_wrong | - | abstained_wrong | - | - | - | - | 「不明」 |
| I2-008 | ro | abstained_wrong | - | abstained_wrong | - | - | - | - | (none) |
| I2-008 | ca | abstained_wrong | - | abstained_wrong | - | - | - | - | (none) |
| I2-008 | ctl | hit | Y | hit | Y | N | Y | 0 | 「カール・マルクス」 |
| I2-013 | ro | hit | Y | miss | N | N | Y | 8 | 「千葉神社の旧社格県社」 |
| I2-013 | ca | hit | Y | miss | N | N | Y | 8 | 「千葉神社の旧社格県社」 |
| I2-013 | ctl | hit | Y | hit | Y | N | Y | 0 | 「県社」 |
| I2-025 | ro | abstained_wrong | - | abstained_wrong | - | - | - | - | (none) |
| I2-025 | ca | abstained_wrong | - | abstained_wrong | - | - | - | - | (none) |
| I2-025 | ctl | hit | Y | hit | Y | N | Y | 0 | 「青」 |
| I2-034 | ro | hit | Y | miss | N | N | Y | 11 | 「サンゴーカメラ1981年にに設立」 |
| I2-034 | ca | hit | Y | miss | N | N | Y | 10 | 「サンゴーカメラ1981年に設立」 |
| I2-034 | ctl | hit | Y | hit | Y | N | Y | 0 | 「1981年」 |
| I2-041 | ro | no_output | - | no_output | - | - | - | - | (none) |
| I2-041 | ca | abstained_wrong | - | abstained_wrong | - | - | - | - | (none) |
| I2-041 | ctl | hit | Y | miss | N | Y | Y | 7 | 「「キューバの太陽」という意味」 |
| R2-I013 | ro | hit | Y | hit | Y | N | Y | 0 | 「ネパール」 |
| R2-I013 | ca | abstained_wrong | - | abstained_wrong | - | - | - | - | (none) |
| R2-I013 | ctl | hit | Y | hit | Y | N | Y | 0 | 「ネパール」 |
| R2-U003 | ro | abstained_correct | - | abstained_correct | - | - | - | - | (none) |
| R2-U003 | ca | abstained_correct | - | abstained_correct | - | - | - | - | (none) |
| R2-U003 | ctl | abstained_correct | - | abstained_correct | - | - | - | - | 「不明」 |
| UF-001 | ro | abstained_correct | - | abstained_correct | - | - | - | - | (none) |
| UF-001 | ca | abstained_correct | - | abstained_correct | - | - | - | - | (none) |
| UF-001 | ctl | abstained_correct | - | abstained_correct | - | - | - | - | 「不明」 |
| UF-015 | ro | abstained_correct | - | abstained_correct | - | - | - | - | (none) |
| UF-015 | ca | abstained_correct | - | abstained_correct | - | - | - | - | (none) |
| UF-015 | ctl | abstained_correct | - | abstained_correct | - | - | - | - | 「不明」 |

| mode | answerable runs | hits_text (old headline) | **hit_exact (new headline)** | hit_cited (extra, longer quoted text) | emitted but not exact | unans abstained correct | unans answered | unans no output |
|---|---|---|---|---|---|---|---|---|
| record_only | 7 | 4 | **1** | 1 | 3 | 3/3 | 0 | 0 |
| constructed_allowed | 7 | 2 | **0** | 0 | 3 | 3/3 | 0 | 0 |
| free_text | 7 | 6 | **5** | 1 | 1 | 3/3 | 0 | 0 |
