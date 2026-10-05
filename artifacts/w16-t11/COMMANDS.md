# W16-t11 流したコマンド（前置き: cd 作業ツリー; PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python）

- 隔離: `$PY -P -c "import ...; print([ツリー外の verantyx モジュール])"` → `isolation.txt`（`[]`）。`git rev-parse HEAD` → `base_commit.txt`。`$PY -P -m verantyx.cli index search "README の数値の検査"` → `index_search.txt`（UNKNOWN_NOT_FOUND）。
- 仕様の凍結: `numbers.json`・`claim_words.json` の sha256 → `numbers.sha256`・`claim_words.sha256`・`numbers_time.txt`。追記版 `numbers.r1.json`（`numbers.r1.sha256`・`numbers.r1_time.txt`）。
- 検査器の試験: `$PY -m pytest -q -p no:cacheprovider tests/test_w16t11_checker.py` → `checker_tests.txt`（18 件）。
- 仕様の再計算: `$PY tools/readme_numbers_check.py numbers --spec-only` → `spec_only.txt`、`... --spec artifacts/w16-t11/numbers.r1.json --spec-only` → `spec_only.r1.txt`。
- 実例の再生: `bash artifacts/w16-t11/examples/replay.sh <dir>`（3 回: ex1・ex2・ex-final。出力 `examples/replay_run1.txt`・`replay_run2.txt`・`r3_replay.txt`）、`normalize.py <dir> examples/out`、`normalize.py --print` の diff（IDENTICAL）、`examples/out.sha256`。
- 煙試験（1 回目、バックグラウンド・serve の段が失敗）: `VERA_PYTHON=$PY VERA_SMOKE_SCRATCH_ROOT=<scratch>/smoke-root bash tools/release/smoke_wheel.sh <scratch>/smoke-out > smoke.log` → `smoke.exit`（1）、`smoke_run1_bg_failed/`。
- 煙試験（2 回目、前景）: 同じコマンドで `<scratch>/smoke-out2` → `smoke2.log`・`smoke2.exit`（0）、`smoke/`。`uptime` → `uptime_smoke.txt`・`uptime_smoke2.txt`。
- 資産: `shasum -a 256 <wheel>` → `release_assets.sha256`・`release_assets.md`・`release_assets_check.txt`。
- 型の名前の確認: `grep -l ... docs/FUSION.md docs/ATTEST.md docs/RECORDER.md` → `type_names_check.txt`。
- R-1: `$PY tools/readme_numbers_check.py numbers --spec artifacts/w16-t11/numbers.r1.json --readme public_overlay/README.md` → `r1.txt`（exit=0 と sha の確認 3 件）。
- R-2: `... claims --files public_overlay/README.md public_overlay/KNOWN_ISSUES.md public_overlay/EVAL.md CHANGELOG.md public_overlay/docs/README_LEGACY_d25a73a.md` → `r2.txt`。
- R-3: `bash examples/replay.sh <dir>`、`normalize.py`、`$PY -m pytest -q -p no:cacheprovider tests/test_w16t11_readme.py -k examples` → `r3_replay.txt`・`r3.txt`（5 件）。
- R-4: `... prepublish --files <上と同じ 5 件>` → `r4.txt`、許可パス外 `public_overlay/pyproject.toml public_overlay/vera_base/corpus.py` → `r4_outside_scope.txt`（2 件・exit=1。直していない）。
- R-5: `git diff --stat ecde332 -- verantyx/ public_overlay/vera_base/ public_overlay/pyproject.toml` → `r5.txt`（空）、`git status --short` → `status_end.txt`、`find ... test_*.py` → `no_tests_in_artifacts.txt`（空）。
- 突然変異の確認: `mutations.txt`（仕様の値・README の値の変更で R-1 が赤、印の無い言い切りで R-2 が赤、絶対パスで R-4 が赤、存在しない commit で exit 2）。
- 自分の試験: `$PY -m pytest -q -p no:cacheprovider tests/test_w16t11_checker.py tests/test_w16t11_readme.py` → `tests_w16t11.txt`（30 件通過。`LC_ALL=C` でも通過を確認）。
- 全体テストは流していない（チケットの指示）。既存の `tests/test_conduct_ask_cli.py`（README.md のパスを使う）だけ流して 21 件通過。

## 第 3 ラウンドの実行コマンド（出力は `*.r3.txt`）
前置き: `export PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python`
- 隔離・基点: `isolation.r3.txt`（`[]`）、`base_commit.r3.txt`
- 仕様: `$PY tools/readme_numbers_check.py numbers --spec artifacts/w16-t11/numbers.r3.json --spec-only` → `spec_only.r3.txt`
- R-1: `... numbers`、`... numbers --spec numbers.r3.json --readme public_overlay/README.md`、`shasum -c` → `r1.r3.txt`
- R-2: `... claims`（引数なし）と 5 ファイル明示 → `r2.r3.txt`
- R-3: `pytest -q -p no:cacheprovider tests/test_w16t11_readme.py -k examples` → `r3.r3.txt`
- R-4: `... prepublish` → `r4.r3.txt`
- R-5: `git diff --stat 4c2a2e5 -- verantyx/ public_overlay/vera_base/ public_overlay/pyproject.toml`、`git status --short` → `r5.r3.txt`
- 全試験: `pytest -q -p no:cacheprovider tests/test_w16t11_checker.py tests/test_w16t11_readme.py` → `tests_w16t11.r3.txt`
- 突然変異（scratchpad の写し）: `mutations.r3.txt`
