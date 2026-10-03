# W5-a 実行したコマンドと出力ファイル

記号: `W=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-a-S`、`A=$W/artifacts/w5-a`、`S=<scratchpad>/W5a`（木の外）、`py.sh <木> 引数...` は `$A/scripts/py.sh`（`env -i`、wiring の venv、`PYTHONPATH=<木>`、`PYTHONDONTWRITEBYTECODE=1`）。
pytest は常に `-p no:cacheprovider`。

| 目的 | コマンド（要約） | 出力 |
|---|---|---|
| 索引 | `py.sh $W -m verantyx.cli index search "<4 つの問い>"` | `index_search.txt` |
| 隔離（開始時・終了時） | `py.sh $W -c "...verantyx* のファイルがすべて木の配下か..."`（指示書 C-ISO） | `isolation.txt`（`[]`） |
| 変更前の全体テスト | `py.sh $W -m pytest -q -rfEs --continue-on-collection-errors --basetemp=$S/bt_before --junitxml=$A/before_junit.xml tests` | `before_pytest.txt`・`before_failures.txt`・`before_junit.xml`（115 失敗・8429 成功。1 台で一括） |
| 変更前の入口の出力 | `cd $S/dev0e4 && py.sh $S/dev0e4 $A/scripts/entry_dump.py $S/dev0e4 $W/artifacts/w1-a/x3_after.jsonl $A/entry_before.jsonl`（2344 入力、`foreign []`） | `entry_before.jsonl` |
| 攻撃テスト（直す前、dev の写しに置いて） | `cd $S/dev0e4 && py.sh $S/dev0e4 -m pytest -q tests/attack/test_attack_w1a3_reading_entry.py tests/attack/test_attack_w3b_placement_type_order.py tests/attack/test_attack_w2h_routing_testimony_context_cache.py` | `attack_before.txt`（8 failed） |
| 攻撃テスト（直した後） | `py.sh $W -m pytest -q <同じ 3 本>` | `attack_after.txt`（8 passed） |
| 新しい試験 3 本 | `py.sh $W -m pytest -q tests/attack/test_w5a_cross_key_order.py tests/attack/test_w5a_testimony_reuse_key.py tests/attack/test_w5a_reading_entry_rules.py` | `new_tests_after.txt`（45 passed） |
| K3（鍵順の全順列。件数と秒数） | `py.sh $W -m pytest -q -s tests/attack/test_w5a_cross_key_order.py` | `k3_permutations.txt` |
| K4（照会の回数） | `py.sh $W $A/scripts/k4_counts.py $W $S/k4tmp` | `k4_reask_counts.txt` |
| K4 の関連テスト（指示書 §2 手順 3 の一覧） | `py.sh $W -m pytest -q <一覧>` | 端末の出力（606 passed, 2 skipped。ファイルには保存していない。全体テストに含まれる） |
| 変更後の入口の出力 | `py.sh $W $A/scripts/entry_dump.py $S/dev0e4 $W/artifacts/w1-a/x3_after.jsonl $A/entry_after.jsonl`（2344 入力、`foreign []`） | `entry_after.jsonl` |
| 入口の変化 | `/Users/motonisihikoudai/vera-wiring/env/bin/python $A/scripts/cmp.py $A/entry_before.jsonl $A/entry_after.jsonl v` | `entry_changes.txt`（`readable→false` 15、`reason_changed` 82、`changed`・`false→readable` なし） |
| 攻撃役の 140 文 | `py.sh $W $A/scripts/probe_cmp.py $W/attacks/W1-a3/probe_outputs.jsonl`（`run_probes.py` は実行していない） | `probe_cmp.txt` |
| 採点器（自作の見本 3 本、before = dev の写し、after = `$W`） | `cd <木> && py.sh <木> -m tools.bank_score --profile v2 --bank B1 --items tests/bank_score/fixtures/<fx>/items.jsonl --entry mod-semantic-read --tree <木> --out $S/bs_<before\|after>_<fx> --python <venv の python>` | `bank_score/<before\|after>_<fx>/{summary,run_meta}.json`、`bank_class_changes.tsv`（118 問すべて分類の変化なし） |
| 変更後の全体テスト | `py.sh $W -m pytest -q -rfEs --continue-on-collection-errors --basetemp=$S/bt_after --junitxml=$A/after_junit.xml tests` | `after_pytest.txt`・`after_failures.txt`・`after_junit.xml`（121 失敗・8476 成功） |
| 失敗集合の比較 | `comm -13 before_failures after_failures` ほか | `new_failures.txt`（6 行）・`fixed_failures.txt`（0 行）・`new_vs_official.txt`（7 行） |
| 新しい失敗 1 件（S6）の原因確認 | 変更を commit した木の写しで `tests/bank_score/test_bs_end_to_end.py` | `s6_on_committed_snapshot.txt`（9 passed。原因は未コミットの変更で `git status -- verantyx` が空でないこと） |
| C-HARD | `py.sh $W tests/reading_soundness/check_hardcode.py --base 0e40954` | `hardcode.txt`（失敗欄 2 つとも `[]`） |
| C-WORDS | `git diff 0e40954 -- verantyx/ \| grep '^+' \| grep -E '<攻撃文の語>'` | `attack_words_in_diff.txt`（0 行） |
| C-LISTS | 指示書のコマンド（dev の写しと `$W` の閉じた類の JSON を比べて `uniq \| wc -l`） | `c_lists.txt`（1） |
| C-SCOPE | `git status --short`、`git diff --stat 0e40954 -- verantyx/semantic_reader.py verantyx/agent_routing.py verantyx/en_frames.py tests/test_semantic_read_r4.py` | `scope.txt`、後者は空 |

# 第 2 ラウンド（W5-a2）

記号: `A2=$A/r2`、`S=<scratchpad>/W5a2`（木の外）。`$S/dev0e4` は `git archive 0e40954` の写し、`$S/r1snap` は第 1 ラウンド終了時の状態の写し（コミット済み）、`$S/snap` は最終状態の写し。dev の写しで流すときは必ず `cd` してから流した（`sys.path[0]` の落とし穴）。

| 目的 | コマンド（要約） | 出力 |
|---|---|---|
| 開始時の状態 | `git status --short`・`git diff --stat` | `r2/status_start.txt`（15 行）・`r2/diffstat_start.txt`（7 files） |
| 隔離（開始時・終了時） | 指示書 C-ISO | `r2/isolation_start.txt`・`r2/isolation.txt`（どちらも `[]`） |
| 索引 | `py.sh $W -m verantyx.cli index search "<2 つの問い>"` | `r2/index_search.txt`（2 件とも `UNKNOWN_NOT_FOUND`） |
| T6 の改訂前後 | `shasum -a 256`・`sed -n` | `r2/t6_before.{sha256,txt}`・`r2/t6_after.{sha256,txt}` |
| r3 の改訂前後 | 同上 | `r2/r3_before.{sha256,txt}`・`r2/r3_after.{sha256,txt}` |
| test_observe の原因 | `py.sh <木> $S/obs3.py`・`$S/obs_probe.py`（`cd` した上で、`$S/r1snap` と `$W`） | `r2/observe_cause.txt` |
| test_observe の改訂前後 | 同上 | `r2/observe_before.{sha256,txt}`・`r2/observe_after.{sha256,txt}` |
| 攻撃テスト 3 本 | `py.sh $W -m pytest -q <3 本>` | `r2/attack_after.txt`（8 passed） |
| 入口の出力 | `py.sh $W $A/scripts/entry_dump.py $W $W/artifacts/w1-a/x3_after.jsonl $A2/entry_after.jsonl` | `r2/entry_after.jsonl`（2344 入力、`foreign []`） |
| 入口の変化（dev） | `$PY $A/scripts/cmp.py $A/entry_before.jsonl $A2/entry_after.jsonl v` | `r2/entry_changes_vs_dev.txt`（`readable→false` 38・`reason_changed` 103。`CHG`・`F→R` 0） |
| 入口の変化（第 1 ラウンド） | `$PY $A/scripts/cmp.py $A/entry_after.jsonl $A2/entry_after.jsonl v` | `r2/entry_changes_vs_r1.txt`（`readable→false` 23・`reason_changed` 21。理由はすべて `UNSUPPORTED_CLAUSE`。`AGENT_EVIDENCE_MISSING` 0） |
| 攻撃役の 140 文 | `py.sh $W $A/scripts/probe_cmp.py $W/attacks/W1-a3/probe_outputs.jsonl` | `r2/probe_cmp.txt`（第 1 ラウンドの `probe_cmp.txt` と `diff` で同一） |
| H2 の不変条件 | `$PY $A2/h2_invariant.py $A2/entry_after.jsonl` | `r2/h2_invariant.txt`（25 行、理由の組は 1 種だけ） |
| B3 の 7 件の分類 | `py.sh $W $A2/classify7.py` | `r2/classify7.py`・`r2/classify7.txt` |
| B3 の 7 件のテスト | `py.sh $W -m pytest -q <ノード ID 2 つ> tests/test_observe_data.py` | `r2/b3_seven.txt`（115 passed） |
| 採点器（自作の見本 3 本、after = `$W`） | 第 1 ラウンドと同じコマンド（`--out $S/bs_r2_<fx>`）。スクリプトは `$S/bs_run.sh` | `r2/bank_score/after_<fx>/{summary,run_meta}.json` |
| 採点器の分類の突き合わせ | `$PY $A2/bank_cmp.py $S $S`（before は第 1 ラウンドの dev の結果の `results.jsonl`） | `r2/bank_class_changes.tsv`（118 問中 2 問が変化） |
| 全体テスト | `py.sh $W -m pytest -q -rfEs --continue-on-collection-errors --basetemp=$S/bt_after_r2 --junitxml=$A2/after_junit.xml tests`（スクリプト `$S/full.sh`、1 台で一括） | `r2/after_pytest.txt`・`r2/after_failures.txt`・`r2/after_junit.xml`・`r2/after_uptime.txt`（`116 failed, 8496 passed, 45 skipped, 75 xfailed, 75 xpassed`、279.76 s） |
| 失敗集合の比較 | `comm -13/-23` | `r2/new_failures.txt`（s6 の 1 行）・`r2/fixed_failures.txt`（0 行）・`r2/new_vs_official.txt`（2 行: s6 と `test_p4_abilities`。後者は第 1 ラウンドの `before_failures.txt` にある） |
| s6（コミット済みの写しで） | `cd $S/snap && py.sh $S/snap -m pytest -q tests/bank_score/test_bs_end_to_end.py` | `r2/s6_on_committed_snapshot.txt`（9 passed） |
| K3 | `py.sh $W -m pytest -q tests/attack/test_w5a_cross_key_order.py` | `r2/k3.txt`（7 passed） |
| K4 | `py.sh $W -m pytest -q <指示書 §5 の一覧>` | `r2/k4.txt`（383 passed） |
| 改訂したテストと読解のテスト | `py.sh $W -m pytest -q tests/test_semantic_read{,_r2,_r3,_r4}.py tests/test_observe.py tests/attack/test_w5a_reading_entry_rules.py` | `r2/reading_tests.txt`（456 passed） |
| C-HARD | `py.sh $W tests/reading_soundness/check_hardcode.py --base 0e40954` | `r2/hardcode.txt`（2 欄とも `[]`） |
| C-WORDS | 指示書のコマンド | `r2/attack_words_in_diff.txt`（1 行。`PLACE` が `_PLACEMENT_PREDICATES` に当たった偽陽性。DECISIONS E12） |
| C-LISTS | 閉じた類（指示書の一覧）の JSON を dev の写し（`cd` 済み）と `$W` で比べて `uniq \| wc -l` | `r2/c_lists.txt`（1） |
| C-SCOPE・C-TESTDIFF | `git status --short`・`git diff 0e40954 -- tests/` ほか | `r2/scope.txt`・`r2/tests_diff.txt`（skip／xfail の語 0） |

# 第 3 ラウンド（W5-a3。出力は `artifacts/w5-a/r3/`。第 1・第 2 ラウンドの測定ファイルは、M1 の `r2/observe_after.txt` 1 ファイルを除いて消さず・上書きしていない）
`W`=作業木、`A`=`$W/artifacts/w5-a`、`A2`=`$A/r2`、`A3`=`$A/r3`、`S`=木の外の scratchpad の `W5a3`、`py.sh` は `$A/scripts/py.sh`。

| 何を | コマンド | 出力 |
|---|---|---|
| 開始時の記録 | `git status --short`・`git diff --stat` | `r3/status_start.txt`（18 行）・`r3/diffstat_start.txt`（10 files） |
| 隔離（開始時） | `py.sh $W -c "...モジュールの `__file__` が木の外のもの..."` | `r3/isolation_start.txt`（`[]`） |
| 索引 | `py.sh $W -m verantyx.cli index search "を の項 既知の枠 読解器の類 主語 人の証拠 棄権"` | `r3/index_search.txt`（`UNKNOWN_NOT_FOUND`） |
| 第 2 ラウンドの状態の写し | `git clone --no-hardlinks $W $S/r2snap` ＋ `rsync` ＋ 木の外でコミット | `$S/r2snap`（`git status --short` が空） |
| 改訂前の全文・sha256 | `shasum -a 256`・`sed -n '26,37p'`（test_T1）・`sed -n '101,107p'`（S-J21）・`grep '"S-J21"' tests/observe/data/expected.jsonl`。`git show 0e40954:...` と `cmp`（両方 dev と同一） | `r3/t1_before.{sha256,txt}`・`r3/sj21_before.{sha256,txt}`・`r3/sj21_frozen_expectation.txt` |
| M1: 抜けのある版の退避 | `cp $A2/observe_after.txt $A3/observe_after_r2_truncated.txt` | `r3/observe_after_r2_truncated.txt`（44 行） |
| M1: 関数の境界で取り直し | `awk '/^def test_realization_and_claim_travel_together/{f=1} /^def test_english_cross_is_a_typed_refusal/{f=0} f'` と `awk '/^def test_counts_list_every_.../{f=1} /^def test_a_cell_with_no_filler/{f=0} f'`（`tests/test_observe.py`） | `r2/observe_after.txt`（47 行。ここだけ上書き）。K63 のブロックの中身をスクリプト（`$S/m1_fix.py`）で置き換え |
| M1 の確かめ | `grep -c`・`wc -l`・Python で K63 のブロックを照合 | `r3/m1_check.txt`（2・3・47・`True`。`shasum -a 256 tests/test_observe.py` は `0990dc72…` のまま） |
| B3 (β) 変種 C | `semantic_read.py` の 3 か所（`_object_frame_known`・B3 のブロックの呼び出しとコメント・`NOT_PRODUCED` の値の末尾）。`$S/np_fix.py` | `r3/diff_r2snap_verantyx.txt`（`diff -ru $S/r2snap/verantyx $W/verantyx`。差は `semantic_read.py` の 3 ハンクだけ） |
| 新規ファイルのテスト | `py.sh $W -m pytest -q tests/attack/test_w5a_reading_entry_rules.py`（`$S/new_b3.py` で書き直し） | 47 passed（画面） |
| test_T1 の原因と測定 | `env -i ... PYTHONHASHSEED=0 python -m verantyx.cli route --explanation .../r1.md --task '{...}'`（今の木と `cd $S/r2snap` の写し） | `r3/t1_output.json`・`r3/t1_output_r2snap.json` |
| S-J21 の原因と測定 | `py.sh <木> $S/sj21_cause.py $S/sj21_tmp`（今の木と `cd $S/r2snap`） | `r3/sj21_cause.txt` |
| 改訂後の全文・sha256 | `shasum -a 256`・関数の境界の `awk`（指示書 手順 4.3・5.3） | `r3/t1_after.{sha256,txt}`・`r3/sj21_after.{sha256,txt}` |
| 入口の出力 | `py.sh $W $A/scripts/entry_dump.py $W $W/artifacts/w1-a/x3_after.jsonl $A3/entry_after.jsonl` | `r3/entry_after.jsonl`（2344 入力、`foreign []`） |
| 入口の変化（dev） | `$PY $A/scripts/cmp.py $A/entry_before.jsonl $A3/entry_after.jsonl v` | `r3/entry_changes_vs_dev.txt`（`readable→false` 43・`reason_changed` 103。`CHG`・`F→R` 0 行） |
| 入口の変化（第 2 ラウンド） | `$PY $A/scripts/cmp.py $A2/entry_after.jsonl $A3/entry_after.jsonl v` | `r3/entry_changes_vs_r2.txt`（`readable→false` 5。理由はすべて `AGENT_EVIDENCE_MISSING`） |
| 攻撃役の 140 文 | `py.sh $W $A/scripts/probe_cmp.py $W/attacks/W1-a3/probe_outputs.jsonl`、第 2 ラウンドとの `diff` | `r3/probe_cmp.txt`・`r3/probe_cmp_vs_r2.txt`（`JA020` 1 文と合計の行） |
| H2 の不変条件 | `$PY $A2/h2_invariant.py $A3/entry_after.jsonl` | `r3/h2_invariant.txt`（第 2 ラウンドと同じ 25 行） |
| 7 件の分類 | `py.sh $W $A3/classify7.py` | `r3/classify7.py`・`r3/classify7.txt` |
| 補助の測定 | `py.sh $W -c "...frames._TRANS..."`・`py.sh $W -c "...R._is_person_phrase..."` | `r3/transitivity_values.txt`・`r3/person_phrase_probe.txt` |
| 採点器（自作の見本 3 本） | 第 1・2 ラウンドと同じコマンド（`--out $S/bs_r3_<fx>`）。スクリプト `$S/bs_run.sh` | `r3/bank_score/after_<fx>/{summary,run_meta}.json` |
| 採点器の分類の突き合わせ | `$PY $A3/bank_cmp.py "<before>/bs_..._{fx}" "$S/bs_r3_{fx}"`（before: 第 2 ラウンドの実装役の `W5a2/bs_r2_<fx>`、dev は `W5a/bs_before_<fx>`） | `r3/bank_class_changes_vs_r2.tsv`（1 問: `FX-J30`）・`r3/bank_class_changes_vs_dev.tsv`（3 問） |
| K1（攻撃テスト 8 反例） | `py.sh $W -m pytest -q <3 本>` | `r3/attack_after.txt`（8 passed） |
| K3 | `py.sh $W -m pytest -q tests/attack/test_w5a_cross_key_order.py` | `r3/k3.txt`（7 passed） |
| K4 | `py.sh $W -m pytest -q <指示書 §5 の一覧>` | `r3/k4.txt`（383 passed。第 2 ラウンドの `r2/k4.txt` と同数） |
| B3 の 7 件のテスト | `py.sh $W -m pytest -q tests/test_routing_from_text_entry.py tests/test_routing_from_text_regress.py tests/test_observe_data.py` | `r3/b3_seven.txt`（132 passed） |
| 読解のテスト | `py.sh $W -m pytest -q tests/test_semantic_read{,_r2,_r3,_r4}.py tests/test_observe.py tests/attack/test_w5a_reading_entry_rules.py` | `r3/reading_tests.txt`（457 passed） |
| C-HARD | `py.sh $W tests/reading_soundness/check_hardcode.py --base 0e40954` | `r3/hardcode.txt`（2 欄とも `[]`） |
| C-WORDS | 指示書のコマンド | `r3/attack_words_in_diff.txt`（1 行。`PLACE` が `_PLACEMENT_PREDICATES` に当たった偽陽性。E12 と同じ） |
| C-LISTS | `py.sh <木> lists_dump.py`（semantic_read・semantic_reader の 99 個の閉じた集合を JSON にして sha256）を dev の写し（`W5a/dev0e4`）と `$W` で流し `uniq \| wc -l` | `r3/c_lists.txt`（1）・`r3/lists_dump.py` |
| C-SCOPE・C-TESTDIFF・C-ISO | `git status --short`・`git diff --stat 0e40954 -- <触らない所>`・`git diff 0e40954 -- tests/`・`git diff -- <第 3 ラウンドの 2 ファイル>`・隔離の確認 | `r3/scope.txt`・`r3/tests_diff.txt`・`r3/tests_diff_r3.txt`・`r3/isolation.txt`（`[]`） |
| 全体テスト | `py.sh $W -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --basetemp=$S/bt_after_r3 --junitxml=$A3/after_junit.xml tests`（スクリプト `$S/full.sh`、1 台で一括、開始前の負荷は `r3/after_uptime.txt`） | `r3/after_pytest.txt`（`116 failed, 8497 passed, 45 skipped, 75 xfailed, 75 xpassed`、283.38 s）・`r3/after_failures.txt`（116 行） |
| 失敗集合の比較 | `cmp $A2/after_failures.txt $A3/after_failures.txt`、`comm -13/-23` | `r3/failures_vs_r2.txt`（`same-failures-as-r2`）・`r3/new_failures.txt`（s6 の 1 行）・`r3/fixed_failures.txt`（0 行）・`r3/new_vs_official.txt`（2 行: s6 と `test_p4_abilities`。後者は第 1 ラウンドの `before_failures.txt` にある） |
| s6（コミット済みの写しで） | `git clone` ＋ `rsync` ＋ 木の外でコミットした `$S/snap` で `py.sh $S/snap -m pytest -q tests/bank_score/test_bs_end_to_end.py` | `r3/s6_on_committed_snapshot.txt`（9 passed） |
