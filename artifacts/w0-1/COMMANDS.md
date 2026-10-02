# W0-1 実行コマンドと出力ファイルの対応

記号: `W=/Users/motonisihikoudai/Projects/vera-impl/wt/W0-1-S`、`PY=/Users/motonisihikoudai/vera-wiring/env/bin/python`、
`ENV0` = `env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1`（node を PATH に足す版は `PATH=/usr/bin:/bin:/usr/local/bin`）。
すべての pytest に `-p no:cacheprovider`。測定の途中で製品コード・テストは変えていない（最後に変えたのは tests の import／子プロセス env 修正で、after の測定より前）。

| # | 目的 | コマンド（cwd） | 出力 |
|---|---|---|---|
| 1 | 取り込みファイルが枝の版と一致 | `cd $W; for b in wave4 wave5; do for f in $(git diff --name-only dev...origin/src/$b); do git show origin/src/$b:$f | cmp -s - $f && echo "SAME $b $f" \|\| echo "DIFF $b $f"; done; done` | `import_identity.txt` |
| 2 | 衝突（重なるファイル）なし | `cd $W; comm -12 <(git diff --name-only 73d3f72 dev \| sort) <(git diff --name-only 73d3f72 origin/src/wave4 \| sort)` ほか3通り + `git merge-base` | `overlap.txt` |
| 3 | 統合前 dev の全テスト（dev を `git archive dev \| tar -x -C artifacts/w0-1/tmp/dev_tree` で展開） | `cd $W/artifacts/w0-1/tmp/dev_tree; ENV0 PYTHONPATH=$PWD $PY -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --junitxml=$W/artifacts/w0-1/before_junit.xml tests` | `before_pytest.txt`, `before_junit.xml`（2回目: 使い捨ての `tmp/` に出し、比較結果のみ `determinism.txt`） |
| 4 | 統合後の全テスト（node なし） | `cd $W; ENV0 PYTHONPATH=$PWD $PY -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --junitxml=artifacts/w0-1/after_junit.xml tests` | `after_pytest.txt`, `after_junit.xml`（2回目の比較: `determinism.txt`） |
| 5 | 統合後の全テスト（node あり） | 4 と同じ、`PATH=/usr/bin:/bin:/usr/local/bin`、junit は `after_with_node_junit.xml` | `after_pytest_with_node.txt`, `after_with_node_junit.xml` |
| 6 | G3 比較 | `cd $W; ENV0 PYTHONPATH=$PWD $PY tools/w0_1_compare_runs.py artifacts/w0-1/before_junit.xml artifacts/w0-1/after_junit.xml --before-log artifacts/w0-1/before_pytest.txt --after-log artifacts/w0-1/after_pytest.txt` | `g3_compare.txt`（node 版: `g3_compare_with_node.txt`） |
| 7 | G1（チケット記載のコマンドそのまま） | `cd $W; ENV0 PYTHONPATH="$PWD" $PY -c "import verantyx, sys; bad=[...]; print(bad); sys.exit(1 if bad else 0)"` | `g1_ticket_cmd.txt` |
| 8 | G1（確認ツール） | `cd $W; ENV0 PYTHONPATH="$PWD" $PY tools/w0_1_check_isolation.py --import` | `g1_import.txt` |
| 9 | G2（確認ツール、収集後の verantyx* も検査） | `cd $W; ENV0 PYTHONPATH="$PWD" $PY tools/w0_1_check_isolation.py --collect` | `g2_collect.txt` |
| 10 | G2（チケット記載の収集コマンド、`-p no:cacheprovider` を付加） | `cd $W; ENV0 PYTHONPATH="$PWD" $PY -m pytest --collect-only -q -p no:cacheprovider tests`（末尾4行のみ保存） | `g2_ticket_cmd.txt` |
| 11 | テスト実行中の外部 verantyx 混入なし（全セッション） | `cd $W; ENV0 PYTHONPATH="$PWD:$PWD/tools" $PY -m pytest -q -p no:cacheprovider -p w0_1_isolation_plugin --continue-on-collection-errors tests` | `after_isolation_session_check.txt` |
| 12 | G4 テスト関数数 | `cd $W; ENV0 PYTHONPATH="$PWD" $PY tools/w0_1_count_tests.py --before-ref dev --after .` | `test_inventory.txt` |
| 13 | G5 取り込み表 | `cd $W; ENV0 PYTHONPATH="$PWD" $PY tools/w0_1_unit_table.py <wave4 ledger> origin/src/wave4 <wave5 ledger> origin/src/wave5`（台帳は `/Users/motonisihikoudai/vera-wiring/phase2/runs/waveN/ledger.jsonl`） | `unit_table.txt` |
| 14 | w_question_forms2 を載せた試行（`git ls-files -co --exclude-standard` でツリーを `tmp/qf2_tree` に複製し、`git show 9c89f1e:verantyx/semantic_wh.py` と `...:tools/demo_question_forms.py` を上書き） | 4 と同じ pytest を `tmp/qf2_tree` で | `qf2_trial_pytest.txt`, `qf2_trial_junit.xml`, `qf2_trial_compare.txt`（`tools/w0_1_compare_runs.py before_junit.xml qf2_trial_junit.xml`） |
| 15 | qf2 のデモ | `tmp/demo_one.sh <tree> tools/demo_question_forms.py`（env は台帳 manifest_wave4.json の env と同じ） | `qf2_demo_check.txt` |
| 16 | 失敗原因の probe | `cd $W; env -i HOME="$HOME" PATH=/usr/bin:/bin:/usr/local/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD" $PY tools/probe_w0_1_stale.py` | `probe_stale.txt` |
| 17 | 失敗1件ごとの分類表 | `cd $W; ENV0 $PY tools/w0_1_failure_table.py artifacts/w0-1/after_junit.xml artifacts/w0-1/probe_stale.txt` | `failure_table.md` |
| 18 | 依存の走査 | `cd $W; ENV0 $PY tools/w0_1_scan_deps.py $PWD`（末尾の分類注記は手書き） | `dependency_scan.txt` |
| 19 | REAL_QUESTIONS の再生成 | `cd $W; ENV0 PYTHONPATH="$PWD" VERA_CORPUS_ROOT=/tmp/vera-empty-materials VERA_REAL_QUESTIONS=/Users/motonisihikoudai/vera-wiring/data/real_agent_questions.jsonl $PY tools/real_questions_eval.py`（2回、`cmp`） | `real_questions_eval_stdout.txt`, `real_questions_report_generated.md`, `real_questions_determinism.txt`, `real_questions_old_vs_new.diff` |
| 20 | 種別の独立再計算 | `cd $W; ENV0 PYTHONPATH="$PWD" VERA_REAL_QUESTIONS=... VERA_CORPUS_ROOT=/tmp/vera-empty-materials $PY tools/w0_1_question_kinds.py` | `real_questions_kinds.txt` |
| 21 | unit 受入デモ（`tmp/demo_tree` にツリーを複製して実行。環境変数は manifest_wave4.json の env） | 各 `tools/demo_case_frames.py`, `tools/gold_{quantity,double_neg,caus_pass,scramble,passive,parallel,reason,temporal,comparison,giving}.py` を `env -i ... PYTHONPATH=. $PY -B <script> \| tail -1` | `unit_acceptance_final.txt` |
| 22 | 環境資源の上書きで ENV_MISSING テストが走ることの実証 | `VERA_ROUND5_DEV_FIXTURES=<合成1行ファイル> pytest tests/test_semantic_measure.py::test_no_dev_fixture_string_is_hardcoded` | `env_resource_override_demo.txt` |
| 23 | バージョン・条件の記録 | `$PY --version`, `pytest --version`, `pip list`, `node --version`, `git log` ほか | `versions.txt` |
| 24 | 索引の引き直し | `cd $W; ENV0 PYTHONPATH=$PWD $PY -m verantyx.cli index search "<語>"`（3語: 「テスト 失敗 比較 junit」「環境 skip 分類」「台帳 unit 取り込み」） | 出力は最終報告の判断記録に転記（3つとも `UNKNOWN_NOT_FOUND`、searched=749） |
| 25 | 第 2 ラウンド: 比較ツール修正後に G3 比較 3 本を再生成（junit・pytest 出力は第 1 ラウンドのまま。テストも製品も未変更） | `cd $W; ENV0 PYTHONPATH=$PWD $PY tools/w0_1_compare_runs.py artifacts/w0-1/before_junit.xml <after junit> --before-log artifacts/w0-1/before_pytest.txt --after-log <after pytest 出力>`（after = `after_junit.xml` / `after_with_node_junit.xml` / `qf2_trial_junit.xml`） | `g3_compare.txt`, `g3_compare_with_node.txt`, `qf2_trial_compare.txt`（末尾に `exit=`） |
| 26 | 門番の自己試験（第 3 ラウンドで 6 → 13 ケース。収集エラー・ケース消失・xfail 化・資源名の無い skip を追加） | `cd $W; ENV0 PYTHONPATH=$PWD $PY tools/w0_1_compare_selftest.py artifacts/w0-1/before_junit.xml artifacts/w0-1/after_junit.xml`（合成 junit は `artifacts/w0-1/tmp/selftest/`、終了時に消える） | `g3_rename_selftest.txt` |
| 27 | 警告 1 行だけを除く node ラッパーでテスト無改変の全体実行（`cp artifacts/w0-1/quiet_node_shim.sh artifacts/w0-1/tmp/nodeshim/node`、実行権限つき。**ラッパー内の node の実体パス `/usr/local/bin/node` は機械ごとに書き換える**） | `cd $W; env -i HOME="$HOME" PATH=$W/artifacts/w0-1/tmp/nodeshim:/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$W $PY -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --junitxml=artifacts/w0-1/after_with_quiet_node_junit.xml tests` | `after_pytest_with_quiet_node.txt`, `after_with_quiet_node_junit.xml` |
| 28 | 同ラッパーで `tests/test_contract_lower.py tests/test_round4.py` だけ | 27 と同じ env、`-rfEs tests/test_contract_lower.py tests/test_round4.py` | `contract_lower_round4_with_quiet_node.txt` |
| 29 | 27 の G3 比較 | `cd $W; ENV0 PYTHONPATH=$PWD $PY tools/w0_1_compare_runs.py artifacts/w0-1/before_junit.xml artifacts/w0-1/after_with_quiet_node_junit.xml --before-log artifacts/w0-1/before_pytest.txt --after-log artifacts/w0-1/after_pytest_with_quiet_node.txt` | `g3_compare_with_quiet_node.txt` |
| 30 | before で収集エラーだった paraphrase テストが、dev に `import pytest` を足しただけでも落ちることの測定（`git archive dev` を `artifacts/w0-1/tmp/dev_import_pytest` に展開し、`tests/attack/test_semantic_unknown_choice_paraphrase.py` に `import pytest` を 1 行足す） | その複製で `ENV0 PYTHONPATH=<複製> $PY -m pytest -q -p no:cacheprovider -rfEs tests/attack/test_semantic_unknown_choice_paraphrase.py` | `paraphrase_dev_import_only.txt` |
| 31 | 第 3 ラウンド: 門番（`tools/w0_1_compare_runs.py`）に after の収集エラー・MISSING_IN_AFTER・PASS_TO_XFAIL・資源名の無い PASS_TO_SKIP を加えたあと、比較 4 本を再生成（junit・pytest 出力は第 1・2 ラウンドのまま。テストも製品も未変更）。6・25・29 と同じコマンド（引数も同じ）。差分は「`AFTER_COLLECTION_ERROR_BUT_BEFORE_COLLECTION_ERROR (0)` の見出しと `G3 GATES ...` の行が増えた」だけ | 6・25・29 と同じ | `g3_compare.txt`, `g3_compare_with_node.txt`, `g3_compare_with_quiet_node.txt`, `qf2_trial_compare.txt`（末尾に `exit=`） |
| 32 | 第 3 ラウンド: 門番の自己試験の再実行（行 26 のコマンド） | `cd $W; ENV0 PYTHONPATH=$PWD $PY tools/w0_1_compare_selftest.py artifacts/w0-1/before_junit.xml artifacts/w0-1/after_junit.xml` | `g3_rename_selftest.txt`（末尾に `exit=0`） |

`tmp/`（dev の展開、qf2/demo の複製、2回目の実行）は最後に削除した。再現するには上の手順で作り直す。
