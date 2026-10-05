# W3-f1 コマンド（`$S` は scratchpad の W3f1-impl。`py` は `PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 <venv python>` を付ける薄い包み）
| 目的 | コマンド | 出力 |
|---|---|---|
| 隔離の確認 | `import verantyx.cli, frames, semantic_reader, semantic_verify` の後 `W` 外のモジュールを列挙 | `isolation.txt` |
| 索引 | `python -m verantyx.cli index search "participant key canonical role suffix"`／`"親族 名詞 正規化"` | `index_search.txt` |
| 再現（前・後） | `python -m verantyx.cli ask <問い> --mode round5 --document <file>` | `repro_before_{1,2}.json`・`repro_after_{1,2}.json` |
| frames 回帰（前・後） | `frames.regression()`（`_got` を除く） | `frames_regression_{before,after}.txt` |
| K342 の流し（前・後・対照） | `tests/observe/question_ask/run_ask.py --tree new` を aq・extra2（`--mode inproc --placement`）・w3c2・b2like（`--mode cli`）で、出力先 `before/`・`after/`・対照 `before2/`（aq・extra2 のみ） | `before*/`・`after/` の `*.jsonl`・`*_score.json` |
| バンク（前・後） | `python -m tools.bank_score --bank B2 --items tests/bank_score/fixtures/B2/items.jsonl --tree $W --entry cli-ask-round5 --python <venv python> --out $S/bs_B2_<t>`、B1 は `--entry mod-semantic-read` | `bs_{B1,B2}_{before,after}.txt`、`bs_compare.txt`（問別の results.jsonl 比較） |
| 検査データ生成 | `python3 artifacts/w3-f1/mk_data.py tests/reading_soundness/w3f1_kinship.jsonl` | `tests/reading_soundness/w3f1_kinship.jsonl`、`freeze.sha256` |
| A1 | `pytest tests/test_w3f1_kinship_answer.py`（前・後） | `a1_before.txt`・`a1_before_failed.txt`・`a1_after.txt` |
| 誤答の範囲 | `python artifacts/w3-f1/measure_range.py OUT.tsv OUT_TRUNC.tsv` | `range_{before,after}.tsv`・`range_{before,after}_truncated.tsv` |
| frames 層の調査 | `python artifacts/w3-f1/census.py OUT.tsv` | `census_{before,after}.tsv` |
| 公開の写しの親族数 | `python3 artifacts/w3-f1/b2_kin_count.py` | `b2_public_kin_count.txt` |
| K342 比較 | `python3 artifacts/w3-f1/k342_compare.py k342_changed.tsv NAME:before:after[:ctrl] ...` | `k342_changed.tsv`・`k342_summary.txt` |
| 補助の観察（テストではない） | `frames.canonical` に語を渡して表示 | `canonical_probe.txt` |
| 関係テスト（前・後） | 指示書 S1-8 の pytest | `related_{before,after}.txt` |
| 全体テスト（負荷が低いとき 1 回） | `pytest tests -q -rfE --tb=no -p no:cacheprovider > pytest_full.txt`。`after_failures.txt` は同じファイルの `^(FAILED\|ERROR)` 行（`sed 's/ - .*//'`・`sort -u`）、`comm -13` で基線と比較 | `pytest_full.txt`・`after_failures.txt`・`new_failures.txt`・`fixed_failures.txt`・`pytest_full_load_before.txt` |
| 全体テスト（基点、git 付きの写し） | `git clone --shared` の写し（HEAD）で同じ全体テスト | `pytest_full_base.txt`・`after_failures_base.txt`・`new_failures_classified.txt` |
| census の文数 | `census.py OUT.tsv` の stdout（前は基点の frames.py＋凍結データの写し） | `census_before.log`・`census_after.log` |
| AQ025 の原因の切り分け | 単文を `ask --mode round5 --document` で基点の写しと W で流す | `k342_aq025_cause.txt` |
| ハードコード検査 | `git diff -- verantyx/ \| grep '^+' \| grep -nE '叔\|祖\|伯\|義\|曾\|肥料\|診察\|店員'` | `check_hardcode.txt` |

## 拡張（誤答 2・3）のコマンド
| 目的 | コマンド | 出力 |
|---|---|---|
| 隔離・負荷 | 第 3 版指示書 E0（`import ...` の後に W 外のモジュールを列挙） | `ext_isolation.txt`・`ext_load_start.txt`・`ext_pytest_full_load_before.txt` |
| 索引 | `python -m verantyx.cli index search "<語>"`（2 回） | `ext_index_search.txt`（どちらも UNKNOWN_NOT_FOUND） |
| 事前登録 | `date` を `prereg_ext_time.txt` に、`docs/OBSERVATION.md` に追記 | `prereg_ext_time.txt` |
| 検査データ生成 | `python3 artifacts/w3-f1/mk_data_ext.py tests/reading_soundness` | `w3f1_prohibition.jsonl`・`w3f1_time_place.jsonl`・`w3f1_ext_range.jsonl`、`freeze_ext.sha256`（1 回目は `freeze_ext.v1_superseded.sha256`） |
| 再現（前・後） | `python -m verantyx.cli --store S ask "<問い>" --mode round5 --document <文書>`（3 件） | `repro_ext_before_{1,2,3}.json`・`repro_ext_after_{1,2,3}.json` |
| A1（前・後） | `pytest tests/test_w3f1_prohibition_answer.py tests/test_w3f1_time_place_answer.py [tests/test_w3f1_kinship_answer.py]` | `a1_ext_before.txt`・`a1_ext_before_failed.txt`・`a1_ext_after.txt` |
| 空振りの確認 | 時の語を取り除いた文を同じ入口で流す（`ext_vacuity_probe.txt`） | `ext_vacuity_probe.txt` |
| 範囲（前・後） | `python artifacts/w3-f1/measure_range_ext.py OUT.tsv`（W を測る。前は製品を変える前） | `ext_range_{before,after}.tsv`・`ext_range_changed.tsv`・`ext_reason_after.tsv` |
| K342（前・後・対照） | `tests/observe/question_ask/run_ask.py --tree new`（第 3 版指示書 E4-2。aq・extra2 は `--mode inproc --placement`、w3c2・b2like は `--mode cli`） | `before_ext/`・`before2_ext/`・`after_ext/`、`k342_ext_{summary.txt,changed.tsv}`・`k342_total_{summary.txt,changed.tsv}` |
| バンク（前・後） | `python -m tools.bank_score --bank B2 ... --entry cli-ask-round5 --python <venv>`・B1 `mod-semantic-read` | `bs_{B1,B2}_{before,after}_ext.txt`・`bs_ext_compare.txt` |
| 関係テスト・frames | 指示書 E4-4・E4-5（`frames.regression()` から `_got` を除く） | `ext_related_{before,after}.txt`・`ext_frames_regression_{before,after}.txt` |
| ハードコード | `git diff -- verantyx/ \| grep '^+' \| grep -nE '東京\|大阪\|明日\|今日\|来週\|エージェント\|評価バンク\|山田\|田中'` | `ext_check_hardcode.txt`（rc=1） |
| 全体テスト | `pytest tests -q -rfE --tb=no -p no:cacheprovider`（1 回） | `ext_pytest_full.txt`・`ext_after_failures.txt`・`ext_new_failures.txt`・`ext_new_failures_classified.txt`・`ext_fixed_failures.txt` |

## 第 3 版指示書・第 2 ラウンドのコマンド（追記。`_ext2` の名前。`$S` は scratchpad の r2）
| 目的 | コマンド | 出力 |
|---|---|---|
| 事前登録 | `date` を `prereg_ext2_time.txt` に、`docs/OBSERVATION.md` に追記 | `prereg_ext2_time.txt` |
| 検査データ生成 | `python3 artifacts/w3-f1/mk_data_ext2.py tests/reading_soundness` | `w3f1_time_place_suffix.jsonl`、`freeze_ext2.sha256`（1 回目は `*.v1_superseded.*`） |
| 接尾辞の確認 | `semantic_verify._vt_tokens` で時の語＋場所を表示 | `suffix_tokens_probe.txt` |
| 基点の空振り確認 | データを `ask --mode round5 --document` で流す（製品の直し前） | `ext2_base_probe.txt` |
| A1（前・後） | `pytest tests/test_w3f1_time_place_suffix_answer.py [他の test_w3f1_*]` | `a1_ext2_before.txt`・`a1_ext2_after.txt` |
| 再現（後） | 7 文（叔父・禁止・明日東京・来週港・毎朝店・港・てはなりません）を `python -m verantyx.cli --store S ask --mode round5 --document F -- Q` | `repro_ext2_after_{1..7}.json` |
| verdict 不変 | `verdict.read_records`＋`judge` の 6 件 | `ext2_verdict_probe.txt` |
| 過剰な棄権 | 92 語を `_vt_time_fused`／`_vt_time_suffix_fused` で比較 | `ext2_overabstain_probe.txt` |
| 範囲 | `python artifacts/w3-f1/measure_range_ext2.py OUT.tsv`（4 データ） | `ext2_range_after.tsv` |
| K342（前の流し `before_ext` 対 後 `after_ext2`、基点 dev の `before/` 対 後） | `run_ask.py --tree new`（`$S/k342.sh`）、`k342_compare.py` | `after_ext2/`、`k342_ext2_{summary.txt,changed.tsv}`、`k342_total2_{summary.txt,changed.tsv}` |
| バンク | `tools.bank_score --bank B2 … cli-ask-round5`／`B1 … mod-semantic-read` | `bs_{B1,B2}_after_ext2.txt`、`bs_ext2_compare.txt`（`W3f1-ext` の before との問ごとの比較） |
| 関係テスト・frames・隔離・ハードコード | 第 1 ラウンドの拡張と同じコマンド | `ext2_related_after.txt`・`ext2_frames_regression_after.txt`・`ext2_isolation.txt`・`ext2_check_hardcode.txt` |
| 全体テスト | `pytest tests -q -rfE --tb=no -p no:cacheprovider`（1 回） | `ext2_pytest_full.txt`・`ext2_after_failures.txt`・`ext2_new_failures.txt` |

## 第 3 版指示書・第 3 ラウンドのコマンド（追記。`_ext3` の名前。`$S` は scratchpad の W3-f1-r3、`py` = `env PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 <venv python>`）
| 目的 | コマンド | 出力 |
|---|---|---|
| 隔離・負荷 | 第 1 ラウンドの拡張と同じ `import` 列挙、`uptime` | `ext3_isolation.txt`・`ext3_load_start.txt`・`ext3_pytest_full_load_before.txt` |
| 事前登録 | `date` を `prereg_ext3.txt` に、OBSERVATION に追記 | `prereg_ext3.txt` |
| 候補の生成と基点の空振り確認 | `python3 mk_data_ext3.py $S/cand`、`py probe_ext3.py $S/cand/w3f1_prohibition_nde.jsonl OUT.tsv`（第 2 ラウンドの W で流す） | `ext3_base_probe.txt` |
| 検査データ生成（空振りを除く） | `awk` で main_polar の非 ANSWER の id を `ext3_drop_ids.txt` に、`python3 mk_data_ext3.py tests/reading_soundness ext3_drop_ids.txt` | `w3f1_prohibition_nde.jsonl`、`freeze_ext3.sha256` |
| A1（前・後） | `py -m pytest tests/test_w3f1_prohibition_nde_answer.py`（前）、test_w3f1_* 5 本（後） | `a1_ext3_before.txt`・`a1_ext3_before_failed.txt`・`a1_ext3_after.txt` |
| 再現（後） | `py -m verantyx.cli --store S ask --mode round5 --document F -- "運転手は酒を飲む？"`（文書: 飲んではいけません／飲まない） | `repro_ext3_after_{1,2}.json` |
| 範囲 | `py measure_range_ext3.py OUT.tsv`（5 データ）、`ext2_range_after.tsv` との比較 | `ext3_range_after.tsv`・`ext3_range_changed.tsv` |
| 独自の追加検査 | 12 動詞 × 4 形の本動詞の問いを `probe_ext3.py` で | `ext3_extra_probe.tsv` |
| K342 | `run_ask.py --tree new`（`$S/k342.sh`、第 2 ラウンドと同じ 4 本）、`k342_compare.py`（`after_ext2` 対 `after_ext3`、基点 dev `before/` 対 `after_ext3`） | `after_ext3/`、`k342_ext3_{summary.txt,changed.tsv}`、`k342_total3_{summary.txt,changed.tsv}` |
| バンク | `tools.bank_score --bank B2 … cli-ask-round5`／`B1 … mod-semantic-read`、問ごとの比較（前 `W3f1-ext/bs_*_before_ext`・第 2 ラウンド `r2/bs_*_after_ext2`、いずれも scratchpad の `results.jsonl`、`elapsed_ms` を除く） | `bs_{B1,B2}_after_ext3.txt`、`bs_ext3_compare.txt` |
| 関係テスト・frames・ハードコード | 第 1 ラウンドの拡張と同じ | `ext3_related_after.txt`・`ext3_frames_regression_after.txt`・`ext3_check_hardcode.txt` |
| 時の語の語彙の穴 | `_vt_tokens`・`_vt_is_time` と ask（W と基点の写し） | `ext3_time_lexicon_gap.txt`・`ext3_tokens_probe.txt` |
| 全体テスト | `pytest tests -q -rfE --tb=no -p no:cacheprovider`（1 回） | `ext3_pytest_full.txt`・`ext3_after_failures.txt`・`ext3_new_failures.txt` |
