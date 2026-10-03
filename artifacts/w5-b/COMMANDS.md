# W5-b 流したコマンド（実装役 第 1 ラウンド。順に）

記号: `W=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-b-S`、`A=$W/artifacts/w5-b`、`PY=$A/scripts/py.sh`（`env -i`・wiring の venv・`PYTHONPATH=<木>`・`PYTHONDONTWRITEBYTECODE=1`）、`S=<scratchpad>/impl-r1`、`PLC=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r5/run1`。`cd $W &&`（または `cd $S/dev &&`）を各コマンドの先頭に付けた。`uptime` の 1 分平均は全体テストの前に 4.1〜4.6（8 未満）。

## 手順 0（製品コードに触れる前）
1. `py.sh` を書く（`A/scripts/py.sh`）。
2. 索引: `cd $W && for q in <指示書の 7 つ>; do $PY $W -m verantyx.cli index search "$q" >> $A/index_search.txt; done`
3. 隔離: `$PY $W -c "import sys, verantyx.conduct_map, …, verantyx.cli; print(sorted(… 木の外の verantyx*))" > $A/isolation.txt`（`[]`）
4. dev の写し: `git -C $W archive a92a926 | tar -x -C $S/dev && (cd $S/dev && git init -q && git add -A && git commit -qm base)`
5. 変更前の全体テスト: `cd $W && $PY $W -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --basetemp=$S/bt_before tests > $A/before_pytest.txt`（115 失敗。`before_failures.txt`）
6. 変更前の測定（`$S/dev` のコード）:
   - `sed -e … $W/artifacts/w3-a/measure_w3a.py > $A/scripts/measure_coarse_w5b.py`、`cd $S/dev && $PY $S/dev $A/scripts/measure_coarse_w5b.py $S/dev $A/coarse_before {l1,l2,l3} --placement $PLC`
   - `cd $W && $PY $W tests/conduct_ask/w2c2/run_w2c2.py run --code-tree $S/dev --label before --out $A/w2c2_before`
   - `cd $S/dev && $PY $S/dev tests/observe/measure.py --reobserve --workdir $S/wm_before --out $A/o2_before.json`
   - `cd $S/dev && $PY $S/dev tests/routing_from_text/run_bank.py --bank <data> --items <data>/<items> --explanations-dir <dir> --out $A/routing_before/<名前>`（items・items_mid・items_reader_shaped・items_mid_reader_shaped の 4 通り）
7. 攻撃テスト 6 本（＋データ）を `tests/attack/` と `$S/dev/tests/attack/` に写す（先頭に出典の 1 行だけ足す）。dev の写しで `$PY $S/dev -m pytest -q -p no:cacheprovider --basetemp=$S/bt_atk_dev <6 本> > $A/attack_before.txt`（17 failed, 18 passed）。

## 手順 2〜7（モジュールごと）
- W4-m: `$PY $W -m pytest … tests/test_sovereign_{store,ledger,units,promote,cli,w5b}.py tests/attack/test_attack_w4m_sovereign.py > $A/w4m_tests.txt`。負荷: `cp <PROTO>/stress_w4m.py $A/scripts/`、`$PY $S/dev $A/scripts/stress_w4m.py 30 $S/stress_before > $A/l3_stress_before.txt`、`$PY $W $A/scripts/stress_w4m.py 30 $S/stress > $A/l3_stress_after.txt`。
- W3-c: `$PY $W -m pytest … tests/test_observe_data.py`（単独）と `tests/test_observe.py tests/test_observe_entry.py tests/test_observe_realize.py tests/test_salience.py tests/test_event_cross.py tests/attack/test_attack_w3c_observe.py tests/attack/test_w5b_observe_paths.py` → `$A/w3c_tests.txt`。`$PY $W tests/observe/measure.py --reobserve --workdir $S/wm_L4 --out $A/o2_after.json`。`$PY $W $A/scripts/l4_merge_reobserve.py > $A/l4_merge_reobserve.txt`。
- W3-a2: `$PY $W -m pytest … tests/coarse_place tests/test_gen_coarse_evidence.py tests/attack/test_attack_w3a2_contract.py > $A/w3a_tests.txt`。`$PY $W $A/scripts/measure_coarse_w5b.py $W $A/coarse_after {l1,l2,l3} --placement $PLC`、`cmp $A/coarse_before/eval_runs/$k/items.jsonl $A/coarse_after/eval_runs/$k/items.jsonl`（`coarse_items_cmp.txt`）。`cp <PROTO>/q.py $A/scripts/coarse_probe_queries.py`、前後の出力（`coarse_probe_{before,after}.txt`）。`$PY $W $A/scripts/count_time_head_counters.py $PLC > $A/time_head_counters.txt`。
- W2-g2: `$PY $W -m pytest … <指示書の 19 ファイル>（tests/test_conduct_map_w5b.py と tests/attack/test_attack_w2g2_mapping.py を含む）> $A/w2g_tests.txt`。
- W2-c3: `$PY $W -m pytest … <指示書の 20 ファイル> > $A/w2c_tests.txt`。`$PY $W tests/conduct_ask/w2c2/run_w2c2.py run --code-tree $W --label after --out $A/w2c2_after`、`… diff $A/w2c2_before $A/w2c2_after --out $A/w2c2_diff`。
- W2-h2: `$PY $W -m pytest … tests/test_routing_from_text{,_data,_entry,_regress,_w5b}.py tests/attack/test_attack_w2h2_routing_from_text.py > $A/w2h_tests.txt`。`$PY $W tests/routing_from_text/run_bank.py …（前と同じ 4 通り。--out $A/routing_after/<名前>）`、`python3 $A/scripts/routing_diff.py $A > $A/routing_diff.txt`。`$PY $W $A/scripts/routing_with_placement.py $PLC > $A/routing_with_placement.txt`。

## 手順 9・確認
- L1: `$PY $W -m pytest -q -p no:cacheprovider -rf --basetemp=$S/bt_L1 <攻撃テスト 6 本> | tee $A/L1_attack_after.txt`（2 failed, 33 passed）。写しの比較（`diff`・`cmp`）→ `$A/L1_copies_same.txt`。
- L3: `$PY $W -m pytest … tests/test_sovereign_w5b.py tests/attack/test_attack_w4m_sovereign.py -k "not tampered_export"`（`L3_tests.txt`）、`stress_w4m.py 30`（`l3_stress_after.txt`）。
- 全体テスト: `cd $W && $PY $W -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --basetemp=$S/bt_after tests > $A/after_pytest.txt`、`grep -E '^(FAILED|ERROR) ' … | sed 's/ - .*//' | sort -u > $A/after_failures.txt`、`comm` で `new_failures.txt` `fixed_failures.txt` `new_vs_official_baseline.txt`。
- 隔離の取り直し（`isolation_after.txt`）、範囲（`git status --short | grep -v …`）、`git diff --stat a92a926 -- tests/`、`__pycache__` の有無、製品の差分の攻撃文の語の grep。
- 後始末: `git checkout -- artifacts/w3-c/index_small/pro.db artifacts/w3-c/index_small_manifest.json`（`measure.py --reobserve` が追跡下のこの 2 ファイルを作り直したため。基点の内容に戻した）。
- 一時の探索（`$S/play`・`$S/play2` の小さなスクリプト）は結果を `artifacts/` に残していない（探索のみ。数値は報告に使っていない）。
- CLI の通し（公開の入口 `python -m verantyx.conduct_ask --vocab-llm fake --map-fake … --vocab-ledger …`。manifest の作成・再生の型・書き換えの拒否）: `cd $W && $PY $W $A/scripts/cli_demo_manifest.py $S/cli/frame.md $S/cli/map_d3.json $S/cli_demo_work2 > $A/cli_demo_manifest.txt`（枠 `frame.md` は自作の小さな枠、台本 `map_d3.json` は作り物の対応づけ。どちらも scratchpad の下）。
- 全体テストの後の、コメントだけの変更（製品コードの差分の攻撃文の語の grep を 0 にするため）のあと、`tests/test_conduct_ask_w2c2.py tests/test_conduct_ask_w2c2_view.py tests/test_conduct_ask_w5b.py tests/test_conduct_map_w5b.py tests/test_routing_from_text.py` を流し直した（616 passed、4 failed = 宣言した C3×3・C4）。

## 第 2 ラウンド
- 作業用の置き場: `$S2=<scratchpad>/impl-r2`（`probe2.py`・`p3.py`・`bt_*`。消さずに残す）。レビューの探り `W5b_rev1/probe_ca.py`・`probe_atk.py` と凍結反例 `W5b_rev1/l2/` は読むだけで流した（書いていない）。
- `cd $W && $PY $W $R/probe_ca.py $R/l2`、`$PY $W $R/probe_atk.py $W/tests/attack/w2c3`（M1・M2 の確認。修正前は誤答 / 上がらない、修正後は全部 `HUMAN_APPROVAL_REQUIRED` か `FRAME_SILENT/TERM_IN_WIDER_PHRASE`）。
- `cd $W && $PY $W tests/conduct_ask/w2c2/run_w2c2.py run --code-tree $W --label after --out $A/w2c2_after` と `… diff $A/w2c2_before $A/w2c2_after --out $A/w2c2_diff`（第 1 ラウンドの出力は `$S2/r1_artifacts/` に写してから上書き）。
- 関係テスト: 各モジュールの手順の「確かめ方」と同じ（下の最終の実行は `impl.r2.md`）。

## 第 3 ラウンド
- 作業用の置き場: `$S3=<scratchpad>/W5b_r3`（`dev/` は `git archive a92a926` の写し、`probe_*.py`、`bt_*`。消さずに残す）。レビューの探り `W5b_rev2/probe2.py`・`probe_atk2.py`・凍結反例 `W5b_rev2/l2r2/`・`W5b_rev1/l2/` は読むだけ。
- M-A・M-B の確認: `cd $W && $PY $W $A/scripts/probe_review_r2_atk2.py $W/tests/attack/w2c3 > $A/probe_review_r2_atk2_after.txt`、`$PY $W $A/scripts/probe_review_r2_probe2.py > $A/probe_review_r2_probe2_after.txt`（レビューの探りの写し）。自分の探り（別の言い回し）: `$PY $W $A/scripts/probe_r3_attribute_forms.py $W/tests/attack/w2c3 > $A/probe_r3_attribute_forms_after.txt`、dev の写しで `cd $S3/dev && $PY $S3/dev … > $A/probe_r3_attribute_forms_before.txt`。
- 広い語句の答えの前後: `cd $S3/dev && $PY $S3/dev $A/scripts/wider_answer_effect.py > $A/wider_answer_effect_before.txt`、`cd $W && $PY $W $A/scripts/wider_answer_effect.py > $A/wider_answer_effect_after.txt`。
- レビューの凍結反例: `cd $W && $PY $W -m pytest -q -p no:cacheprovider --basetemp=$S3/bt_l2a W5b_rev2/l2r2/test_l2r2.py`（1 failed: `消して`）、`… W5b_rev1/l2`（4 failed: 第 1 ラウンドで確定したレビューの試験の作りの誤り）。
- 関係テスト（W2-c 系 20 ファイル）→ `$A/w2c_tests.txt`、`run_w2c2.py run/diff` → `$A/w2c2_after/`・`$A/w2c2_diff/`（ログ `w2c2_after_run.log`・`w2c2_diff.log`）。
- 全体テスト（`uptime` の 1 分平均 4.95）: `cd $W && $PY $W -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --basetemp=$S3/bt_full tests > $A/after_pytest.txt`。その後の `grep`・`comm` は手順 9 と同じ。

## 第 4 ラウンド
- 準備: `W=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-b-S; A=$W/artifacts/w5-b; PY=$A/scripts/py.sh; SCR=<scratchpad>; S=$SCR/W5b_r4; R1=$SCR/W5b_rev1; R2=$SCR/W5b_rev2; R3=$SCR/W5b_rev3; PLC=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r5/run1`（作業場 `$S` は木の外。一時の小さなスクリプト `$S/probe_md.py`・`$S/probe_kana.py`・`$S/copies.sh` も置いてある。`probe_*.py` は探索のみで、数値は報告に使っていない）。
- 手順 0: `shasum -a 256`（8 ファイル。指示書の起点と一致）、`git status --short --untracked-files=all > $S/status_start.txt`（168 行）、`index search` を 4 つの問いで `index_search.txt` に追記（4 つとも `UNKNOWN_NOT_FOUND`。似たものは無い）、隔離 `cd $W && $PY $W -c "import sys, verantyx.conduct_ask, …"`（`isolation_r4_start.txt` = `[]`）。
- M-D: `cd $W && $PY $W -m pytest -q -p no:cacheprovider --basetemp=$S/bt_md $R3/l2r3/test_l2r3.py -k n1_ja`（`6 passed`）、`… tests/test_conduct_ask_w2c2.py tests/test_conduct_ask_w5b.py`（`602 passed`）。
- M-E: `… $R3/l2r3/test_l2r3.py`（`38 passed`）、`$PY $W $R3/probe_ok.py …`（`probe_r4_probe_ok.txt`）、`$PY $W $R2/probe2.py`（`probe_r4_probe2_after.txt`。`sed 1d` した第 3 ラウンドの出力と差 0 行）、`$PY $W $R2/probe_atk2.py $W/tests/attack/w2c3`（`probe_r4_atk2_after.txt`。`$R3/atk2_r3.txt` と差 0 行）、`… tests/test_conduct_ask_w5b.py`（`147 passed`）。
- C4: `… tests/test_conduct_ask_w2c2_view.py`（`5 passed`）、`git diff a92a926 -- tests/test_conduct_ask_w2c2_view.py | grep -c '^[-+][^-+]'`（4）。
- C3: `cp tests/test_routing_from_text.py $S/test_routing_from_text.before.py`（編集前の保存。文書の「変更前」の全文の出所）→ 編集 → `… tests/test_routing_from_text.py`（`77 passed`）、`… tests/test_routing_from_text*.py tests/attack/test_attack_w2h2_routing_from_text.py > $A/w2h_tests.txt`（`141 passed`）、`git diff a92a926 -- tests/test_routing_from_text.py | grep '^[-+][^-+]'`（入力の文字列と表の鍵だけ）。
- C1: `… tests/coarse_place tests/test_gen_coarse_evidence.py tests/attack/test_attack_w3a2_contract.py > $A/w3a_tests.txt`（`171 passed`）、`for m in l1 l2 l3; do $PY $W $A/scripts/measure_coarse_w5b.py $W $A/coarse_after_r4 $m --placement $PLC > $A/coarse_after_r4_$m.txt; done`、`cmp`/`diff` で `coarse_items_r3_vs_r4.txt`、`$PY $W $A/scripts/routing_with_placement.py $PLC`（`routing_with_placement_r3_vs_r4.diff` は 0 行）、`event_cross` の接点（`kana_variant_event_cross.txt`）。
- C2: 関数を取り除いた後、`… tests/test_sovereign_w5b.py tests/attack/test_attack_w4m_sovereign.py`（`18 passed`）。
- L1: `… tests/attack/test_attack_w2g2_mapping.py tests/attack/test_attack_w2h2_routing_from_text.py tests/attack/test_attack_w3a2_contract.py tests/attack/test_attack_w3c_observe.py tests/attack/test_attack_w4m_sovereign.py tests/attack/w2c3/test_attack_w2c3_traps.py tests/attack/test_w5b_observe_paths.py > $A/L1_attack_after.txt`（`56 passed`）、写しと原本の差 `bash $S/copies.sh > $A/L1_copies_diff.txt`（W3-a2 の改訂した関数と W4-m の取り除いた関数の 2 か所だけ。出典の 1 行を除いて比較）。
- L2（実装役の自分の木での実行。合格の証明ではない）: `… -rf $R3/l2r3/test_l2r3.py $R1/l2 $R1/l2b $R2/l2r2 > $A/L2_frozen_on_impl_r4.txt`（`8 failed, 149 passed`）。
- L3: `… tests/test_sovereign_w5b.py tests/attack/test_attack_w4m_sovereign.py > $A/L3_tests.txt`（`18 passed`）、`mkdir -p $S/stress_L3; $PY $W $A/scripts/stress_w4m.py 30 $S/stress_L3 > $A/l3_stress_after.txt`。
- L4: `$PY $W $A/scripts/l4_merge_reobserve.py > $A/l4_merge_reobserve.txt`（`"rate": 1.0`）。
- W2-c 系 20 ファイル → `$A/w2c_tests.txt`（`1252 passed`）、`run_w2c2.py run/diff` → `$A/w2c2_after/`・`$A/w2c2_diff/`、`wider_answer_effect.py` → `$A/wider_answer_effect_after.txt`（第 3 ラウンドの出力と差 0 行）。
- 全体テスト（`uptime` の 1 分平均 5 前後、8 未満）: `cd $W && $PY $W -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --basetemp=$S/bt_after tests > $A/after_pytest.txt`、そこから `after_failures.txt`・`new_failures.txt`・`fixed_failures.txt`・`new_vs_official_baseline.txt`（指示書の `grep`・`sort`・`comm`）。
- 共通: 隔離の取り直し `isolation_after.txt`、範囲 `git status --short --untracked-files=all > $S/status_end.txt; diff $S/status_start.txt $S/status_end.txt`、`git diff --stat a92a926 -- verantyx/`・`-- tests/`、守った定数・攻撃文の語・`__pycache__`・文書の削除行数の確認。
