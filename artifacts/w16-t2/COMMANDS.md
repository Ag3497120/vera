# W16-t2 の測定の再現コマンド（`artifacts/w16-t2/` の出力を作ったコマンドそのもの）

2026-10-06 01:34、第 3 ラウンドの実装役が書き直した（レビュー `review.r1.md` の必須 1）。前の版は、配置なしの分と第 1 ラウンドの分が雛形と言葉の説明で、コマンドそのものではなかった。

## 0. 約束・変数・記録の状況

約束:
- `run_paths.py`・`tools.bank_score`・関係テストの行は、`$S/` のスクリプトに書かれた引数のまま 1 行ずつ書いた。ループ（`run_r2.sh` の `pair` と `for P`）は、原本のコピーの `$PY run_paths.py …` の行を `echo` に替えて機械的に展開し、その出力と原本の行を機械的にこのファイルへ差し込んだ（打ち直していない）。原本は「8. 原本」に全文を写した（`$S` は一時のスクラッチで、消えうるため）。
- `compare.py` と漏れ検出の行はスクリプトに無い。出所は各節の冒頭に書いた。
- スクリプトにも出力ファイル自身にも記録が無いものは「記録なし」と書き、推測で埋めていない（1・6.2・6.3・6.4・7）。
- 「第 3 ラウンドで確認」と書いたものは、第 3 ラウンドで実際に流して確かめたこと。出力はスクラッチ（`$S` と同じ親の `w16t2-r3/`）に出し、`artifacts/w16-t2/` の既存のファイルは書き換えていない。

変数（以下のコマンドで使う）:
```
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t2-S
A=$W/artifacts/w16-t2
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
R9=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t2-impl
QA=$W/tests/observe/question_ask
P2=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t2-plan2
PL=/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W16-t2
```
- `$PL` は指示書・レビューの置き場所（`plan.md` = 第 2 ラウンドの指示書、`round1/plan.md` = 第 1 ラウンドの指示書、`review.r1.md` = 第 2 ラウンドのレビュー）。コマンドには使わず、出所の参照だけに使う。
- `$P2/plug/leakplug.py` は中間職（レビュー役）が作った pytest プラグイン。原本は 8 に写した。
- `$S/base` は基点 3a1677c の `verantyx`・`tools`・`pyproject.toml`。`$PL/round1/plan.md` の 17 行目は `git archive` で展開したと書く。展開した実際のコマンドは記録なし。第 3 ラウンドで `git archive 3a1677c verantyx tools pyproject.toml` の展開と `diff -rq` で比べ、576 ファイルすべて一致した。
- `run_paths.py` は 1 つの集合（`--set` の `questions.jsonl` と `docs/`）を ask・serve（`decode_grammar.read_turn`）・chat の 3 入口に通して 1 問 1 行の jsonl にする。子プロセスは、`--tree` の値を cwd と PYTHONPATH にし、環境変数を HOME・PATH（`/usr/bin:/bin`）・PYTHONPATH・PYTHONDONTWRITEBYTECODE=1 だけ（`--vp` があれば VERA_PLACEMENT も）にして起こし、読み込まれた `verantyx*` が `--tree` の下にあることを検査する。
- 現在の `run_paths.py` は第 2 ラウンドの版（旧 chat も流す。一時ディレクトリは `TemporaryDirectory`）。第 1 ラウンドの jsonl（`_r2` なし）は第 1 ラウンドの版（旧 chat なし、一時ディレクトリは `mkdtemp`）で流したもので、その版のファイルは `$A` にも `$S` にも残っていない。第 1 ラウンドの jsonl は書き換えていない。

`run_paths.py` の出力は 32 本（`ls $A/*.jsonl | wc -l` が 32）。記録の状況:

| 出力 | 本数 | 状況 | 節 |
|---|---|---|---|
| 第 2 ラウンド 配置あり（`old_*_r2.jsonl`・`new_*_r2.jsonl`） | 10 | スクリプトの引数どおり | 2 |
| 第 2 ラウンド 配置なし（`old_*_noplace_r2.jsonl`・`new_*_noplace_r2.jsonl`） | 10 | スクリプトの引数どおり | 3 |
| 第 1 ラウンドの new（`new_u4.jsonl`・`new_own60.jsonl`・`new_w3c4.jsonl`・`new_w3c4_b2like.jsonl`） | 4 | スクリプトの引数どおり | 6.1 |
| 第 1 ラウンドの old（`old_u4.jsonl`・`old_own60.jsonl`・`old_w3c4.jsonl`・`old_w3c4_b2like.jsonl`） | 4 | **記録なし** | 6.2 |
| 実験（`exp_trigger_u4.jsonl`・`exp_trigger_own60.jsonl`・`exp_trigger_w3c4.jsonl`・`exp_trigger_w3c4_b2like.jsonl`） | 4 | **一部だけ記録**（引数の全体は記録なし） | 6.3 |

## 1. 検査データの作成と凍結（製品を流す前）

作成と凍結の実行の行は **記録なし**（`$S/` のスクリプトにも出力にも無い）。次は、何がどのスクリプトから出るかだけ。
- `sets/make_sets.py`（引数なし。絶対パスで `sets/u4/`・`sets/own60/` に書く）→ u4 11 問・own60 60 問（第 1 ラウンド）
- `make_w3c4_sets.py`（引数なし。`__file__` を基準に `sets/w3c4/`・`sets/w3c4_b2like/` に書く。元は `tests/observe/question_ask/questions.jsonl` と `b2like/questions.jsonl`）→ w3c4 111 問・w3c4_b2like 47 問（第 1 ラウンド）
- `sets/make_w3f1_set.py`（引数なし。docstring の使い方は `python make_w3f1_set.py`。`tests/reading_soundness/w3f1_*.jsonl` から `sets/w3f1/` に書く。verantyx を import しない）→ 324 行（第 2 ラウンド）
- `freeze.sha256`（u4・own60 の 9 ファイルの sha256 と、最後に日付の行）と `freeze_r2.sha256`（w3f1 の 325 ファイル）。中のパスは `sets/...` の相対（`$A` を cwd にして `shasum -a 256` を流した形）。作ったコマンドの行は **記録なし**（`$PL/round1/plan.md` の手順 3-3 と `$PL/plan.md` の手順 8 の 2 にコマンドの形があるが、パスの書き方が実物と違うので、実行した行とは言えない）。

確認（第 3 ラウンドで実行。cwd は `$A`。結果: 前者は 325 行すべて OK、後者は 9 行 OK と、日付の行の形式が違うという警告 1 件）:
```
cd $A
shasum -a 256 -c freeze_r2.sha256
shasum -a 256 -c freeze.sha256
```

## 2. 第 2 ラウンド（`_r2`）: 配置あり

出所: `$S/run_r2.sh` の `for P in with none` の `with` の回（`$V` は `--vp $R9`、W3-c4 系の `$F` は `--fileplacement $QA/placement_ask.json`）を展開した。`$S/run_r2.log` に 20 行の `child done` と `ALLDONE`。`cd $A` で流し、old と new は集合ごとに並列（原本の `&` と `wait`）。
```
cd $A
$PY run_paths.py --tree $S/base --set sets/u4 --out old_u4_r2.jsonl --mode old --python $PY --vp $R9
$PY run_paths.py --tree $W --set sets/u4 --out new_u4_r2.jsonl --mode new --python $PY --vp $R9
$PY run_paths.py --tree $S/base --set sets/own60 --out old_own60_r2.jsonl --mode old --python $PY --vp $R9
$PY run_paths.py --tree $W --set sets/own60 --out new_own60_r2.jsonl --mode new --python $PY --vp $R9
$PY run_paths.py --tree $S/base --set sets/w3f1 --out old_w3f1_r2.jsonl --mode old --python $PY --vp $R9
$PY run_paths.py --tree $W --set sets/w3f1 --out new_w3f1_r2.jsonl --mode new --python $PY --vp $R9
$PY run_paths.py --tree $S/base --set sets/w3c4 --out old_w3c4_r2.jsonl --mode old --python $PY --docs-dir $QA/docs --fileplacement $QA/placement_ask.json
$PY run_paths.py --tree $W --set sets/w3c4 --out new_w3c4_r2.jsonl --mode new --python $PY --docs-dir $QA/docs --fileplacement $QA/placement_ask.json
$PY run_paths.py --tree $S/base --set sets/w3c4_b2like --out old_w3c4_b2like_r2.jsonl --mode old --python $PY --docs-dir $QA/b2like/docs --fileplacement $QA/placement_ask.json
$PY run_paths.py --tree $W --set sets/w3c4_b2like --out new_w3c4_b2like_r2.jsonl --mode new --python $PY --docs-dir $QA/b2like/docs --fileplacement $QA/placement_ask.json
```
比較（`compare.py`）。出所: スクリプトには無い。引数は出力 `t2_compare_r2.txt` の見出し行（`== u4 (old=old_u4_r2.jsonl new=new_u4_r2.jsonl, …)` の並び）から。`--out`・`--withheld` はこのコマンドが書いたファイルの名前。第 3 ラウンドで確認: 同じ引数を `--out`・`--withheld` だけスクラッチに替えて流し直し、`t2_compare_r2.txt`・`t2_1_serve_withheld_r2.tsv` と byte 一致した。
```
cd $A
$PY compare.py --out t2_compare_r2.txt --withheld t2_1_serve_withheld_r2.tsv u4=old_u4_r2.jsonl:new_u4_r2.jsonl own60=old_own60_r2.jsonl:new_own60_r2.jsonl w3c4=old_w3c4_r2.jsonl:new_w3c4_r2.jsonl w3c4_b2like=old_w3c4_b2like_r2.jsonl:new_w3c4_b2like_r2.jsonl w3f1=old_w3f1_r2.jsonl:new_w3f1_r2.jsonl
```

## 3. 第 2 ラウンド（`_noplace_r2`）: 配置なし

出所: `$S/run_r2.sh` の `for P in with none` の `none` の回を展開した（`$V`・`$F` が空なので `--vp`・`--fileplacement` が無く、W3-c4 系の `--docs-dir` だけが残る）。子プロセスの環境は `run_paths.py` が最小に作るので、`VERA_PLACEMENT` は渡らない。ログは 2 と共通の `$S/run_r2.log`。
```
cd $A
$PY run_paths.py --tree $S/base --set sets/u4 --out old_u4_noplace_r2.jsonl --mode old --python $PY
$PY run_paths.py --tree $W --set sets/u4 --out new_u4_noplace_r2.jsonl --mode new --python $PY
$PY run_paths.py --tree $S/base --set sets/own60 --out old_own60_noplace_r2.jsonl --mode old --python $PY
$PY run_paths.py --tree $W --set sets/own60 --out new_own60_noplace_r2.jsonl --mode new --python $PY
$PY run_paths.py --tree $S/base --set sets/w3f1 --out old_w3f1_noplace_r2.jsonl --mode old --python $PY
$PY run_paths.py --tree $W --set sets/w3f1 --out new_w3f1_noplace_r2.jsonl --mode new --python $PY
$PY run_paths.py --tree $S/base --set sets/w3c4 --out old_w3c4_noplace_r2.jsonl --mode old --python $PY --docs-dir $QA/docs
$PY run_paths.py --tree $W --set sets/w3c4 --out new_w3c4_noplace_r2.jsonl --mode new --python $PY --docs-dir $QA/docs
$PY run_paths.py --tree $S/base --set sets/w3c4_b2like --out old_w3c4_b2like_noplace_r2.jsonl --mode old --python $PY --docs-dir $QA/b2like/docs
$PY run_paths.py --tree $W --set sets/w3c4_b2like --out new_w3c4_b2like_noplace_r2.jsonl --mode new --python $PY --docs-dir $QA/b2like/docs
```
比較（`compare.py`）。出所: 2 の比較と同じく、スクリプトには無く、出力 `t2_compare_noplace_r2.txt` の見出し行から。第 3 ラウンドで確認: `--out`・`--withheld` だけスクラッチに替えて流し直し、`t2_compare_noplace_r2.txt`・`t2_1_serve_withheld_noplace_r2.tsv` と byte 一致した。
```
cd $A
$PY compare.py --out t2_compare_noplace_r2.txt --withheld t2_1_serve_withheld_noplace_r2.tsv u4=old_u4_noplace_r2.jsonl:new_u4_noplace_r2.jsonl own60=old_own60_noplace_r2.jsonl:new_own60_noplace_r2.jsonl w3c4=old_w3c4_noplace_r2.jsonl:new_w3c4_noplace_r2.jsonl w3c4_b2like=old_w3c4_b2like_noplace_r2.jsonl:new_w3c4_b2like_noplace_r2.jsonl w3f1=old_w3f1_noplace_r2.jsonl:new_w3f1_noplace_r2.jsonl
```

## 4. 第 2 ラウンド: B2・B7 の公開の写し

出所: `$S/bank_r2.sh` の 3〜13 行。`$S/bank_r2.log` は `b2cmp 1`・`b7cmp 1`、ほかの行は 0、最後に `BANKDONE`。cd は `$W`。`A` はこのブロックでだけ相対の `artifacts/w16-t2`（原本の 3 行目のとおり。cwd が `$W` なので 0 の `A` と同じ場所）。
```
cd $W
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t2-impl; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python; A=artifacts/w16-t2
run() { env -u VERA_PLACEMENT -u VERA_COARSE_PLACEMENT PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD $PY "$@"; }
run -m tools.bank_score --bank B2 --items tests/bank_score/fixtures/B2/items.jsonl --tree $S/base --entry cli-ask-round5 --python $PY --out $S/bs_B2_before_r2 > $A/bs_B2_before_r2.txt 2>&1; echo b2before $?
run -m tools.bank_score --bank B2 --items tests/bank_score/fixtures/B2/items.jsonl --tree $PWD --entry cli-ask-round5 --python $PY --out $S/bs_B2_after_r2 > $A/bs_B2_after_r2.txt 2>&1; echo b2after $?
run -m tools.bank_score.compare $S/bs_B2_before_r2 $S/bs_B2_after_r2 > $A/bs_B2_compare_r2.txt 2>&1; echo b2cmp $?
run -m tools.bank_score --profile v2 --bank B7 --items tests/bank_score/fixtures/B7/items.jsonl --tree $S/base --python $PY --out $S/bs_B7_before_r2 > $A/bs_B7_before_r2.txt 2>&1; echo b7before $?
run -m tools.bank_score --profile v2 --bank B7 --items tests/bank_score/fixtures/B7/items.jsonl --tree $PWD --python $PY --out $S/bs_B7_after_r2 > $A/bs_B7_after_r2.txt 2>&1; echo b7after $?
run -m tools.bank_score.compare $S/bs_B7_before_r2 $S/bs_B7_after_r2 > $A/bs_B7_compare_r2.txt 2>&1; echo b7cmp $?
run artifacts/w16-t2/bank_compare.py $S/bs_B2_before_r2 $S/bs_B2_after_r2 > $A/bs_B2_semantic_compare_r2.txt 2>&1; echo b2sem $?
run artifacts/w16-t2/bank_compare.py $S/bs_B7_before_r2 $S/bs_B7_after_r2 > $A/bs_B7_semantic_compare_r2.txt 2>&1; echo b7sem $?
echo BANKDONE
```

## 5. 第 2 ラウンド: 関係テスト・漏れの検出

### 5.1 関係テスト（`related_after_r2.txt`）
出所: `$S/related_r2.sh` の 3〜4 行目（3 行目は `cd` で、ここでは `$W`。`$S/related_r2.log` に `RELDONE`）。`$S/rel.txt` の中身（28 のテストファイル・ディレクトリ）は 8 に写した。
```
cd $W
env -u VERA_PLACEMENT -u VERA_COARSE_PLACEMENT PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -p no:cacheprovider -q -rf $(cat $S/rel.txt) tests/test_w16t2_one_path.py tests/test_w16t2_layers.py tests/test_w16t2_placement_env.py > artifacts/w16-t2/related_after_r2.txt 2>&1
```

### 5.2 漏れの検出（`leak_check_r2.txt`）
出所: 第 2 ラウンドの指示書 `$PL/plan.md` の 165 行目のコマンド。末尾の `> $A/leak_check_r2.txt` は前の版の COMMANDS.md の記述（スクリプトには無い）。出力は `LEAK_CHANGE` の 1 行と `100 passed`。
```
cd $W && env -u VERA_PLACEMENT -u VERA_COARSE_PLACEMENT PYTHONPATH=$W:$P2/plug PYTHONDONTWRITEBYTECODE=1 $PY -m pytest -p no:cacheprovider -p leakplug -s -q tests/test_serve_fusion.py tests/test_w16t2_placement_env.py tests/test_w16t2_one_path.py 2>&1 | grep -E "LEAK_CHANGE|passed|failed" > $A/leak_check_r2.txt
```

## 6. 第 1 ラウンド（`_r2` なし）

### 6.1 new 4 本と比較（`new_*.jsonl`・`t2_compare.txt`・`t2_1_serve_withheld.tsv`）
出所: `$S/runnew.sh` の 4〜9 行（4 行目が変数、5〜8 行目が `run_paths.py` の 4 本、9 行目が `compare.py`）。`cd $A` で流す。比較の引数の old 側は、記録なしの 6.2 の出力。
```
cd $A
R9=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python; W=/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t2-S; QA=$W/tests/observe/question_ask
$PY run_paths.py --tree $W --set sets/u4 --out new_u4.jsonl --mode new --vp $R9 --python $PY
$PY run_paths.py --tree $W --set sets/own60 --out new_own60.jsonl --mode new --vp $R9 --python $PY
$PY run_paths.py --tree $W --set sets/w3c4 --docs-dir $QA/docs --out new_w3c4.jsonl --mode new --fileplacement $QA/placement_ask.json --python $PY
$PY run_paths.py --tree $W --set sets/w3c4_b2like --docs-dir $QA/b2like/docs --out new_w3c4_b2like.jsonl --mode new --fileplacement $QA/placement_ask.json --python $PY
$PY compare.py --out t2_compare.txt --withheld t2_1_serve_withheld.tsv u4=old_u4.jsonl:new_u4.jsonl own60=old_own60.jsonl:new_own60.jsonl w3c4=old_w3c4.jsonl:new_w3c4.jsonl w3c4_b2like=old_w3c4_b2like.jsonl:new_w3c4_b2like.jsonl
```
第 3 ラウンドで確認: 現在の `compare.py`（第 2 ラウンドで拡張され、出力に第 2 ラウンドの節が付く）を、9 行目と同じ引数で `--out`・`--withheld` だけスクラッチに替えて流し直した。出力から第 2 ラウンドで足された部分（注の 1 行と、節「round 2」以降）を除くと `t2_compare.txt` と byte 一致し、`t2_1_serve_withheld.tsv` は byte 一致した。

### 6.2 old 4 本: **記録なし**
`$S/` にスクリプトが無く、出力にも引数が残っていない。次は出力から言えることだけ（引数は書かない）。4 本とも、全行の `loaded_from` が `$S/base/verantyx/cli.py`、全行に `chat` の鍵が無く（第 1 ラウンドの版は旧 chat を流さない）、`ar_ask` が null。
- `old_u4.jsonl`（11 行）: `run_paths.py --mode old`（第 1 ラウンドの版）の出力。引数は記録なし。
- `old_own60.jsonl`（60 行）: `run_paths.py --mode old`（第 1 ラウンドの版）の出力。引数は記録なし。
- `old_w3c4.jsonl`（111 行）: `run_paths.py --mode old`（第 1 ラウンドの版）の出力。引数は記録なし。
- `old_w3c4_b2like.jsonl`（47 行）: `run_paths.py --mode old`（第 1 ラウンドの版）の出力。引数は記録なし。

### 6.3 実験 `exp_trigger_*`（後段の引き金に `UNKNOWN_UNSUPPORTED_EVIDENCE` を足した測定。実験で、製品の結果ではない）
出所: `proposed_trigger_unsupported_evidence.md` の 11 行目に、`run_paths.py --extra-trigger UNKNOWN_UNSUPPORTED_EVIDENCE`（子プロセスの中で `doc_answer.QC_TRIGGER` に足すだけ）で U4・own60・W3-c4・b2like を流した、と書いてある。第 3 ラウンドで調べた範囲（`$S/`・`artifacts/w16-t2/`・`docs/OBSERVATION.md`・指示書）では、これと出力が記録のすべてで、**引数の全体は記録なし**（`--set`・`--vp`・`--fileplacement`・`--docs-dir`・`--python` の値と並び）。`--extra-trigger` は現在の `run_paths.py` にある引数。4 本とも、全行の `loaded_from` が `$W/verantyx/cli.py`、全行の `ar_ask` が list（`--mode new` の流し）。
- `exp_trigger_u4.jsonl`（11 行）: `run_paths.py --extra-trigger UNKNOWN_UNSUPPORTED_EVIDENCE` の new の流し。引数の全体は記録なし。
- `exp_trigger_own60.jsonl`（60 行）: `run_paths.py --extra-trigger UNKNOWN_UNSUPPORTED_EVIDENCE` の new の流し。引数の全体は記録なし。
- `exp_trigger_w3c4.jsonl`（111 行）: `run_paths.py --extra-trigger UNKNOWN_UNSUPPORTED_EVIDENCE` の new の流し。引数の全体は記録なし。
- `exp_trigger_w3c4_b2like.jsonl`（47 行）: `run_paths.py --extra-trigger UNKNOWN_UNSUPPORTED_EVIDENCE` の new の流し。引数の全体は記録なし。

比較（`exp_trigger_compare.txt`）: コマンドの行は記録なし。出力の見出し行から、引数のうち `--out exp_trigger_compare.txt` と、`u4=old_u4.jsonl:exp_trigger_u4.jsonl`・`own60=old_own60.jsonl:exp_trigger_own60.jsonl`・`w3c4=old_w3c4.jsonl:exp_trigger_w3c4.jsonl`・`w3c4_b2like=old_w3c4_b2like.jsonl:exp_trigger_w3c4_b2like.jsonl` の 4 組が分かる。`--withheld`（`compare.py` では必須）の書き出し先は記録なし。第 3 ラウンドで確認: この 4 組を `--out`・`--withheld` だけスクラッチに替えて現在の `compare.py` で流し直し、出力から第 2 ラウンドで足された部分（注の 1 行と、節「round 2」以降）を除くと `exp_trigger_compare.txt` と byte 一致した。

### 6.4 B2・B7 の公開の写し
出所: `$S/bank.sh` の 3〜9 行。B2 の before だけは `bank.sh` に無い（B2 の after から始まる）。cd は `$W`。`A` はこのブロックでだけ相対の `artifacts/w16-t2`。
```
cd $W
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t2-impl; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python; A=artifacts/w16-t2
run() { env -u VERA_PLACEMENT -u VERA_COARSE_PLACEMENT PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD $PY "$@"; }
run -m tools.bank_score --bank B2 --items tests/bank_score/fixtures/B2/items.jsonl --tree $PWD --entry cli-ask-round5 --python $PY --out $S/bs_B2_after > $A/bs_B2_after.txt 2>&1; echo after $?
run -m tools.bank_score.compare $S/bs_B2_before $S/bs_B2_after > $A/bs_B2_compare.txt 2>&1; echo cmp $?
run -m tools.bank_score --profile v2 --bank B7 --items tests/bank_score/fixtures/B7/items.jsonl --tree $S/base --python $PY --out $S/bs_B7_before > $A/bs_B7_before.txt 2>&1; echo b7before $?
run -m tools.bank_score --profile v2 --bank B7 --items tests/bank_score/fixtures/B7/items.jsonl --tree $PWD --python $PY --out $S/bs_B7_after > $A/bs_B7_after.txt 2>&1; echo b7after $?
run -m tools.bank_score.compare $S/bs_B7_before $S/bs_B7_after > $A/bs_B7_compare.txt 2>&1; echo b7cmp $?
```
- B2 の before（`bs_B2_before.txt`・`$S/bs_B2_before/`）: **コマンドは記録なし**。残っている記録は、`tools.bank_score` が書く `$S/bs_B2_before/run_meta.json`: `bank` が B2、`args.items` が `tests/bank_score/fixtures/B2/items.jsonl`、`entry` が `cli-ask-round5`、`profile` が `w1s`（既定）、`tree_realpath` が `$S/base`、`python` が `$PY`、`args.timeout_s` が 60.0。第 3 ラウンドで確認: 第 2 ラウンドの `$S/bs_B2_before_r2/run_meta.json` と `timing` 以外が一致する。`--out` が `$S/bs_B2_before` だったことは `bank.sh` の 6 行目（`$S/bs_B2_before` を読む）と出力ディレクトリの存在から、出力が `$A/bs_B2_before.txt` に書かれたことはそのファイルの存在から言える。第 1 ラウンドの指示書 `$PL/round1/plan.md` の手順 11 の 3 の 1 本目に、このコマンドの形が指示されている（`PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 …`。`bank.sh` の `run()` とは環境の書き方が違う）。実際にそう流したかの記録は無い。
- `bs_semantic_compare.txt`: **コマンドの行は記録なし**。第 3 ラウンドで確認: `bank_compare.py $S/bs_B2_before $S/bs_B2_after` の出力に先頭の行 `== B2` を、`bank_compare.py $S/bs_B7_before $S/bs_B7_after` の出力に先頭の行 `== B7` を付けて連ねると、`bs_semantic_compare.txt` と byte 一致した。見出しを付けた実際の方法は記録なし。

## 7. ファイルごとの出所（2〜6 に載せなかったもの。記録の無いものは「記録なし」）

（`bs_*` は 4 と 6.4、`related_after_r2.txt` は 5.1、`leak_check_r2.txt` は 5.2、`t2_compare*.txt`・`t2_1_serve_withheld*.tsv` は 2・3・6.1 に載せた。）
- `related_before.txt`・`related_after.txt`（第 1 ラウンド）: **記録なし**。第 1 ラウンドの指示書 `$PL/round1/plan.md` の 83 行目（前）と 158 行目（後）にコマンドの形がある（`$S/rel.txt` の一覧を引数に渡す `pytest`）。
- `t2_6_check.txt`: **記録なし**。`$PL/round1/plan.md` の 219〜221 行目に、`related_*.txt` から失敗の一覧を作って比べる形がある（`$S/before_failed.txt`・`$S/after_failed.txt` は 0 バイトで残っている）。
- `t2_3_grep.txt`: **記録なし**。`$PL/round1/plan.md` の 131 行目に `grep -nE` の形がある。
- `loc.txt`（第 1 ラウンド）: **記録なし**。中身にコマンドの要約があり、`$PL/round1/plan.md` の 213〜214 行目にコマンドの形がある。
- `loc_r2.txt`: 先頭の 1 行にコマンドが書いてある（`find verantyx -name '*.py' | xargs cat | wc -l ; git diff --numstat 3a1677c -- verantyx ; wc -l verantyx/doc_answer.py`）。cd は `$W`（`$PL/plan.md` の 222 行目）。
- `paths_check.txt`（第 1 ラウンド。中身は `exit=1` の 1 行だけ）: **記録なし**。`$PL/round1/plan.md` の 230 行目に許可パスの正規表現つきのコマンドがある。
- `paths_check_r2.txt`: 見出し行はコマンドの要約で、許可パスの正規表現などの実体は書かれていない。コマンドそのものは **記録なし**（`$PL/plan.md` の 269 行目に正規表現つきのコマンドがある）。
- `chat_dead_branch.txt`: 先頭の 2 行に、基点 3a1677c の `cmd_chat`（1092〜1402 行）について `awk 'NR>=1092 && NR<=1402' | grep -n 'return\|break'` を使ったことと、基点の行番号は `git show 3a1677c:verantyx/cli.py` で確かめられることが書いてある。`awk` に渡したファイルの指定は書かれていないので、コマンドそのものは **記録なし**。
- `index_search.txt`・`index_search_r2.txt`: 出力の `query`（第 1 ラウンド: `document answer path`・`文書に答える`、第 2 ラウンド: `配置の環境変数`・`文書に答える経路`）が検索語。実行の行は **記録なし**（第 1 ラウンドは `$PL/round1/plan.md` の 77 行目に形がある。第 2 ラウンドの `## 配置の環境変数` などの見出し行は書き手の注記）。
- `rerun_check_r2.txt`: **実行の行は記録なし**。材料は残っている: `$S/rerun_new_w3c4_r2.jsonl`（W3-c4 配置ありの new の流し直し）と `rerun_check.py`（使い方は `rerun_check.py A.jsonl B.jsonl`）。第 3 ラウンドで確認: `cd $A` で `$PY rerun_check.py new_w3c4_r2.jsonl $S/rerun_new_w3c4_r2.jsonl` を流すと、出力は `rerun_check_r2.txt` と byte 一致した（実行したときの引数の並びは記録なし）。
- `proposed_default_round5.diff`・`proposed_default_round5.md`・`proposed_test_change_closed_lists.diff`・`proposed_trigger_unsupported_evidence.md`: 第 1 ラウンドの提案の文書と差分。作ったコマンドは **記録なし**。
- `COMMANDS.md`・`REPORT.md`: 手で書いた文書。
- `run_paths.py`・`compare.py`・`bank_compare.py`・`rerun_check.py`・`make_w3c4_sets.py`・`sets/make_sets.py`・`sets/make_w3f1_set.py`: スクリプトの本体（上のコマンドが呼ぶもの）。
- `sets/`: 1。

## 8. 原本（`$S/` のスクリプト・一覧と、`$P2/plug/` のプラグインの全文。第 3 ラウンドで機械的に写した）

### `$S/runnew.sh`（第 1 ラウンドの new 4 本と比較）
```
#!/bin/sh
# usage: runnew.sh  -> runs new on all four sets
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W16-t2-S/artifacts/w16-t2
R9=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python; W=/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t2-S; QA=$W/tests/observe/question_ask
$PY run_paths.py --tree $W --set sets/u4 --out new_u4.jsonl --mode new --vp $R9 --python $PY
$PY run_paths.py --tree $W --set sets/own60 --out new_own60.jsonl --mode new --vp $R9 --python $PY
$PY run_paths.py --tree $W --set sets/w3c4 --docs-dir $QA/docs --out new_w3c4.jsonl --mode new --fileplacement $QA/placement_ask.json --python $PY
$PY run_paths.py --tree $W --set sets/w3c4_b2like --docs-dir $QA/b2like/docs --out new_w3c4_b2like.jsonl --mode new --fileplacement $QA/placement_ask.json --python $PY
$PY compare.py --out t2_compare.txt --withheld t2_1_serve_withheld.tsv u4=old_u4.jsonl:new_u4.jsonl own60=old_own60.jsonl:new_own60.jsonl w3c4=old_w3c4.jsonl:new_w3c4.jsonl w3c4_b2like=old_w3c4_b2like.jsonl:new_w3c4_b2like.jsonl
```

### `$S/bank.sh`（第 1 ラウンドの B2 の after・B7）
```
#!/bin/sh
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W16-t2-S
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t2-impl; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python; A=artifacts/w16-t2
run() { env -u VERA_PLACEMENT -u VERA_COARSE_PLACEMENT PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD $PY "$@"; }
run -m tools.bank_score --bank B2 --items tests/bank_score/fixtures/B2/items.jsonl --tree $PWD --entry cli-ask-round5 --python $PY --out $S/bs_B2_after > $A/bs_B2_after.txt 2>&1; echo after $?
run -m tools.bank_score.compare $S/bs_B2_before $S/bs_B2_after > $A/bs_B2_compare.txt 2>&1; echo cmp $?
run -m tools.bank_score --profile v2 --bank B7 --items tests/bank_score/fixtures/B7/items.jsonl --tree $S/base --python $PY --out $S/bs_B7_before > $A/bs_B7_before.txt 2>&1; echo b7before $?
run -m tools.bank_score --profile v2 --bank B7 --items tests/bank_score/fixtures/B7/items.jsonl --tree $PWD --python $PY --out $S/bs_B7_after > $A/bs_B7_after.txt 2>&1; echo b7after $?
run -m tools.bank_score.compare $S/bs_B7_before $S/bs_B7_after > $A/bs_B7_compare.txt 2>&1; echo b7cmp $?
```

### `$S/run_r2.sh`（第 2 ラウンドの run_paths.py 20 本）
```
#!/bin/bash
# W16-t2 round 2 measurement: old (S/base) and new (W) for 5 sets x {with placement, without}. Run from artifacts/w16-t2.
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W16-t2-S/artifacts/w16-t2
R9=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t2-S
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t2-impl
QA=$W/tests/observe/question_ask
pair() { # name setdir suffix extra...
  n=$1; set=$2; suf=$3; shift 3
  for m in old new; do
    tree=$W; [ $m = old ] && tree=$S/base
    $PY run_paths.py --tree $tree --set $set --out ${m}_${n}${suf}_r2.jsonl --mode $m --python $PY "$@" &
  done
  wait
}
for P in with none; do
  if [ $P = with ]; then suf=""; V="--vp $R9"; else suf="_noplace"; V=""; fi
  pair u4 sets/u4 "$suf" $V
  pair own60 sets/own60 "$suf" $V
  pair w3f1 sets/w3f1 "$suf" $V
  if [ $P = with ]; then F="--fileplacement $QA/placement_ask.json"; else F=""; fi
  pair w3c4 sets/w3c4 "$suf" --docs-dir $QA/docs $F
  pair w3c4_b2like sets/w3c4_b2like "$suf" --docs-dir $QA/b2like/docs $F
done
echo ALLDONE
```

### `$S/bank_r2.sh`（第 2 ラウンドの B2・B7）
```
#!/bin/bash
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W16-t2-S
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t2-impl; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python; A=artifacts/w16-t2
run() { env -u VERA_PLACEMENT -u VERA_COARSE_PLACEMENT PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD $PY "$@"; }
run -m tools.bank_score --bank B2 --items tests/bank_score/fixtures/B2/items.jsonl --tree $S/base --entry cli-ask-round5 --python $PY --out $S/bs_B2_before_r2 > $A/bs_B2_before_r2.txt 2>&1; echo b2before $?
run -m tools.bank_score --bank B2 --items tests/bank_score/fixtures/B2/items.jsonl --tree $PWD --entry cli-ask-round5 --python $PY --out $S/bs_B2_after_r2 > $A/bs_B2_after_r2.txt 2>&1; echo b2after $?
run -m tools.bank_score.compare $S/bs_B2_before_r2 $S/bs_B2_after_r2 > $A/bs_B2_compare_r2.txt 2>&1; echo b2cmp $?
run -m tools.bank_score --profile v2 --bank B7 --items tests/bank_score/fixtures/B7/items.jsonl --tree $S/base --python $PY --out $S/bs_B7_before_r2 > $A/bs_B7_before_r2.txt 2>&1; echo b7before $?
run -m tools.bank_score --profile v2 --bank B7 --items tests/bank_score/fixtures/B7/items.jsonl --tree $PWD --python $PY --out $S/bs_B7_after_r2 > $A/bs_B7_after_r2.txt 2>&1; echo b7after $?
run -m tools.bank_score.compare $S/bs_B7_before_r2 $S/bs_B7_after_r2 > $A/bs_B7_compare_r2.txt 2>&1; echo b7cmp $?
run artifacts/w16-t2/bank_compare.py $S/bs_B2_before_r2 $S/bs_B2_after_r2 > $A/bs_B2_semantic_compare_r2.txt 2>&1; echo b2sem $?
run artifacts/w16-t2/bank_compare.py $S/bs_B7_before_r2 $S/bs_B7_after_r2 > $A/bs_B7_semantic_compare_r2.txt 2>&1; echo b7sem $?
echo BANKDONE
```

### `$S/related_r2.sh`（第 2 ラウンドの関係テスト）
```
#!/bin/bash
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t2-impl
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W16-t2-S
env -u VERA_PLACEMENT -u VERA_COARSE_PLACEMENT PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -p no:cacheprovider -q -rf $(cat $S/rel.txt) tests/test_w16t2_one_path.py tests/test_w16t2_layers.py tests/test_w16t2_placement_env.py > artifacts/w16-t2/related_after_r2.txt 2>&1
echo RELDONE >> $S/related_r2.log
```

### `$S/rel.txt`（関係テストの一覧。`$(cat $S/rel.txt)` で pytest の引数になる。1 行）
```
tests/test_ask_question_cross.py tests/test_ask_question_cross_data.py tests/test_ask_question_cross_w5f.py tests/attack/test_attack_w3c4.py tests/test_chat_repl.py tests/test_one_chat_round5.py tests/test_one_round5_router.py tests/test_basis_policy_entry.py tests/test_one_request_goal_route.py tests/test_serve_fusion.py tests/test_serve_fusion_ollama.py tests/test_w10f04_serve.py tests/test_w12c1_nollm.py tests/test_w12c1_tiers.py tests/test_w12c1_domain.py tests/test_w12c1_vocab.py tests/test_semantic_read_w3e2_serve.py tests/test_semantic_read_w3e2_cli.py tests/test_w10f05_cli.py tests/coarse_place tests/test_semantic_read_w3b1.py tests/test_w3f1_kinship_answer.py tests/test_w3f1_prohibition_answer.py tests/test_w3f1_time_place_answer.py tests/test_w3f1_time_place_suffix_answer.py tests/test_w3f1_prohibition_nde_answer.py tests/test_basis_policy_w5c.py tests/test_basis_policy_w5c_r3.py
```

### `$P2/plug/leakplug.py`（中間職の pytest プラグイン。漏れの検出に使う）
```
import os
_last = [None]
def pytest_runtest_teardown(item, nextitem):
    pass
def pytest_runtest_logfinish(nodeid, location):
    v = os.environ.get('VERA_PLACEMENT'), os.environ.get('VERA_COARSE_PLACEMENT')
    if v != _last[0]:
        print('\nLEAK_CHANGE after %s: %r' % (nodeid, v))
        _last[0] = v
```

### `$S/t.sh`（補助。pytest を `$W` で環境を整えて流す薄いラッパー。どの出力に使ったかは記録なし）
```
#!/bin/bash
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W16-t2-S
exec env -u VERA_PLACEMENT -u VERA_COARSE_PLACEMENT PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t2-S PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -p no:cacheprovider -q "$@"
```
