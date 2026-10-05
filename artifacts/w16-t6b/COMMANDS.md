# 実行したコマンド（前置き: cd <作業ツリー>; PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python）
- 隔離: `$PY -P -c "import sys,os,verantyx.cli,verantyx.attest,verantyx.ledger_events; print([...ツリー外の verantyx*...])"` → isolation.txt / isolation_after.txt（どちらも `[]`）
- 索引: `$PY -P -m verantyx.cli index search "attest ledger verify"` → index_search.txt（UNKNOWN_NOT_FOUND）
- 赤: `$PY -P -m pytest -q -p no:cacheprovider tests/test_w16t6b_ledger_verify.py` → red_before.txt（実装前）。`$PY -P artifacts/w16-t6b/probe_marks.py` → red_before_marks.tsv
- 基線: `$PY -P artifacts/w16-t6/synth/run_synth.py <scratch>/syn_work_before artifacts/w16-t6b/synth_before`、`$PY -P artifacts/w16-t6/replay/run_replay.py artifacts/w16-t6b/replay_before`（manifest.json を複製してから）、`artifacts/w16-t6b/k606_capture.sh artifacts/w16-t6b/k606_before`
- K606 の固定入力: `vera events --ledger-dir <scratch>/k606/led_add add test_run --data '{...}'`、`cd <scratch>/k606/tree && PATH=<venv>/bin:$PATH vera run --ledger-dir <scratch>/k606/led_run --keep-args -- python -m pytest -q tests/test_a.py -p no:cacheprovider`（複製を k606_fixture/ に）
- 実装後: 同じ 3 つを synth_after / replay_after / k606_after に。`$PY -P artifacts/w16-t6b/synth_diff.py synth_before/t6_1_synth.json synth_after/t6_1_synth.json` → synth_diff.txt。replay は 4 ファイルを `cmp` → replay_cmp.txt。k606 は k606_cmp.txt（比較の python は報告に書いた方法）。
- 緑: `$PY -P -m pytest -q -p no:cacheprovider tests/test_w16t6b_ledger_verify.py` → green_after.txt
- 既存: `$PY -P -m pytest -q -p no:cacheprovider tests/test_w16t6_*.py` → t6_existing_after.txt。移行案は scratchpad の複製 mig/new で同 3 ファイルを流した → proposed_migration_pytest.txt
- 関係: `$PY -P -m pytest -q -p no:cacheprovider tests/test_w16t6b_*.py tests/test_w16t6_*.py tests/test_w16t7_ledger.py tests/test_w16t7_run.py tests/test_w10f04_ledger.py tests/test_semantic_read_w3e2_ledger.py` → related_tests.txt
- a16 の CLI: `$PY -P -m verantyx.cli attest k606_fixture/rep.md --tree k606_fixture/tree --ledger a16_fixture/led/events.jsonl --json` → a16_cli.json / a16_cli.rc（exit=4）

## 第 2 ラウンド
- 手順は plan.md（第 2 ラウンド）どおり。出力は `*_r2*`: isolation_r2.txt・freeze_r2_start.sha256・t6_four_plus_new_r2.txt（59 passed）・red_r2_cli.txt・green_r2_cli.txt・tests_freeze_r2.sha256・synth_after_mig/・synth_diff_mig.txt・k606_after_r2/・k606_cmp_r2.txt（k606_rec_cmp.py を使用）・replay_after_r2/・replay_cmp_r2.txt・replay_norm_cmp_r2.txt（replay_norm_cmp_r2.py）・a16_cli_r2.json/.rc（相対パスで実行して byte 比較）・branches_r2.txt・related_tests_r2.txt（202 passed）。
- 合成の再測定は新しい作業ディレクトリ（scratchpad の syn_work_mig2）で行い、出力ディレクトリは先に mkdir が必要（run_synth.py は作らない）。最初の 2 回は出力先の欠如・作業ディレクトリの再利用で失敗した（結果は無効、上書きした）。
