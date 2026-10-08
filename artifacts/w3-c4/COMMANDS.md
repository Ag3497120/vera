# W3-c4 コマンドの一覧（どのファイルをどのコマンドで作ったか。数は書かない）

記号: `W` = 作業ツリー、`S` = スクラッチの `W3-c4-impl`、`D` = `W/tests/observe/question_ask`、`A` = `W/artifacts/w3-c4`、`R7` = `/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1`。
ラッパー: `S/py.sh`（新しいツリー）、`S/py_base.sh`（基点 `c334fe6` の `git archive` を `S/base` に展開したもの）。どちらも `env -i`、`PYTHONPATH=<ツリー>`、`PYTHONDONTWRITEBYTECODE=1`、`VP=<dir>` があれば `VERA_PLACEMENT`。
**子プロセスの cwd はそのツリー自身にする**（`python -m` は cwd を sys.path の先頭に置くので、cwd が別のツリーだとそちらの `verantyx` が読まれる。製品は出典の資産を cwd からの相対で探すので、別の cwd では `UNKNOWN_SOURCE_ASSET` になる）。runner は `cwd=<tree>` で子を起こし、`score.loaded_from` に実際に読んだ `verantyx/cli.py` の路を残す。

| ファイル | コマンド |
|---|---|
| `env_check.txt` | 4 つの節（新旧それぞれ、ツリーの cwd と中立の cwd）で `import verantyx, verantyx.cli, verantyx.observe, verantyx.one, verantyx.basis_policy` して読み込んだ `verantyx*` の `__file__` を並べた（全部そのツリーの下） |
| `index_search.txt` | `S/py.sh -m verantyx.cli index search "question cross ask document"` と `"質問の十字"` |
| `pytest_related_before.txt` / `pytest_related_after.txt` | `S/rel_tests.sh <out> <basetemp>`（関係テスト 18 ファイル。`-p no:cacheprovider -rf --tb=no`。before は何も変えない前、after は仕上げのあと） |
| `nondeterministic_keys.txt` | 基点で 5 文書 10 問を 2 回流し（`S/probe/run10.sh`）、2 回の JSON の葉を比べて値が違った鍵を取った |
| `prereg.txt` | `date` と、検査データの前に `ls D` が無いことの記録 |
| `D/*`（検査データ） | `python3 D/build_data.py`（文書・配置・問）、`python3 D/build_w3c2.py`（W3-c2 の再利用）。`S/py.sh D/check_lines.py > A/check_lines.txt`。凍結: `S/py.sh D/freeze_data.py --frozen-at "<date>"` → `D/FROZEN.json`、`shasum -a 256` → `A/freeze.txt`。追加分: `D/questions_nodoc.jsonl` と `D/FROZEN_EXTRA.json` |
| `parity.txt` | `S/py.sh D/parity.py --out A/parity.txt` |
| `a1_{base1,base2,new,base_r7,new_r7}.jsonl` と `*_score.json` | `S/run_a1.sh`（`D/run_ask.py --mode cli`。343 問 = AQ・W3-c2・B2 の形。docs は `S/a1_docs` に集めたコピー） |
| `a1_cmp_noplace.txt` / `a1_cmp_r7.txt` | `S/py.sh D/cmp_a1.py --base A/a1_base1.jsonl --base2 A/a1_base2.jsonl --new A/a1_new.jsonl --mask A/nondeterministic_keys.txt --questions S/a1_questions.jsonl`（r7 は `a1_base_r7`・`a1_new_r7` 対で、対照の base2 に `a1_base1` を使わず同じ r7 の基点 2 回目 `a1_base_r7_2` を使う） |
| `a1_cmp_other_modes.txt` | `D/run_ask.py --ask-mode legacy --no-docs` と `--no-docs`（round5 で `--document` なし）を base・new で 10 問ずつ流して `cmp_a1.py --outside-all` |
| `a2_{place,r7}*`・`w3c2_{place,r7}*`・`b2like_{place,r7}*` | `S/run_a2.sh`（`D/run_ask.py`。`place` は `--mode inproc --placement`、`r7` は `--mode cli --vp R7`。訂正を当てた版は `--rescore` で `questions_corrected.jsonl` に対して採点し直した `*_corr_score.json`） |
| `a2_nodoc*` | `D/run_ask.py --questions D/questions_nodoc.jsonl --mode inproc --placement D/placement_ask.json` |
| `determinism.txt` | `PYTHONHASHSEED=0` と `=1` で新データの先頭 20 問を `--mode cli --vp R7` で流し、`S/py.sh D/cmp_det.py --a … --b … --mask A/nondeterministic_keys.txt` |
| `summary.txt` | `S/py.sh D/make_summary.py`（全部ファイルから機械で作る。`--patch-docs` で `docs/OBSERVATION.md` の測定結果の区間に貼る） |
| `pytest_new_tests.txt` | `pytest tests/test_ask_question_cross.py tests/test_ask_question_cross_data.py` |
| `pytest_full.txt` / `pytest_new_failures.txt` | 全体テストを最後に 1 回。基線との差は `comm -13` |
| `paths_check.txt` | `git status --short` と許可パスの正規表現 |

## 第 2 ラウンド（M1: 書かれた述語の一致）

| ファイル | コマンド |
|---|---|
| `D/extra2/*`（検査データ） | `python3 D/extra2/build_extra2.py`（文書 4 本・質問 42 問・配置。手書きの内容を書き出すだけ。`verantyx` を import しない）。`S/py.sh D/extra2/check_extra2.py > A/r2_check_extra2.txt`。凍結: `D/FROZEN_EXTRA2.json`（sha256 と `date`）、`shasum -a 256 D/FROZEN_EXTRA2.json D/extra2/questions.jsonl > A/r2_freeze.txt` |
| `D/extra2/corrections.jsonl`・`questions_corrected.jsonl` | 凍結のあとに気づいた作者の誤り 2 問（X032・X037）の訂正。凍結したファイルは変えない |
| `r2_extra2_before_place*` | 規則を入れる前（第 1 ラウンドのコード）で `D/run_ask.py --questions D/extra2/questions.jsonl --docs-dir D/extra2/docs --tree new --mode inproc --placement D/extra2/placement_extra2.json`。`*_corr_score.json` は `--rescore` で `questions_corrected.jsonl` に対して採点し直したもの |
| `r2_extra2_place*`・`r2_extra2_r7*` | 同じ質問を規則を入れた後で（`place` は `--mode inproc --placement`、`r7` は `--mode cli --vp R7`） |
| `r1_scores/` | 第 1 ラウンドの score の JSON のコピー（再測定の前に `cp`。差を `make_summary.py` が出す）。`r1_summary.txt` は第 1 ラウンドの `summary.txt` |
| `a1_new*`・`a2_*`・`w3c2_*`・`b2like_*`・`determinism*` | 第 2 ラウンドで再測定: `S/r2/run_r2.sh`（`a1_new`・`a1_new_r7` を流し、`S/run_a2.sh` を流す）。基点の出力（`a1_base*`）は第 1 ラウンドのまま（基点のツリーは変わっていない） |
| `a1_cmp_*` | 第 1 ラウンドと同じコマンド（上の表）。基点の 2 回目との対照つき |
| `summary.txt` | `S/py.sh D/make_summary.py --patch-docs`（第 2 ラウンドの節 `round 2` と `extra2` を足した） |
| `r2_probe_*` | 中間職のプローブ（`W3-c4-rev/probe*.py`、読むだけ）を出力先だけ自分のスクラッチにして流した結果: 規則の前後 |
| `r2_pytest_*` | `pytest` の出力（新しいテスト・関係テスト・全体） |
