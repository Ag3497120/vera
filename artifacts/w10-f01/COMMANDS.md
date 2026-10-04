# artifacts/w10-f01 — どのファイルをどのコマンドで作ったか（数は書かない。数は score_*.txt・score_*.json にある）

記号: `W` = `/Users/motonisihikoudai/Projects/vera-impl/wt/W10-f01-S`、`A` = `$W/artifacts/w10-f01`、
`PY` = `env PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python`、
`R8` = `/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2`（粗い配置。読むだけ）。

| ファイル | 作り方 |
|---|---|
| `env_check.txt` | `cd $W && $PY -c "import verantyx, verantyx.cli, verantyx.vera_server, verantyx.observe, verantyx.basis_policy, sys; print('\n'.join(sorted(m.__file__ for n,m in sys.modules.items() if n.startswith('verantyx') and getattr(m,'__file__',None))))"` |
| `index_search.txt` | `cd $W && $PY -m verantyx.cli index search "OpenAI 互換 serve 文法 復号"`（`UNKNOWN_NOT_FOUND`: 既存の同じものは無い） |
| `prereg.txt` | 検査データを書く前の `ls -R $A/data` と `date`（`docs/FUSION.md` §1 の登録のあと） |
| `data/docs/F01.txt`〜`F05.txt` | 手で書いた（Vera にも LLM にも通さずに） |
| `data/questions.jsonl` | `$PY $A/scripts/make_questions.py $A/data/questions.jsonl`（手で書いた表から。期待を含む） |
| `freeze.txt`・`data/FROZEN.json` | `cd $A && shasum -a 256 data/docs/*.txt data/questions.jsonl > freeze.txt`、FROZEN.json は同じ sha256 と `date` |
| `eval_layer0.jsonl`・`eval_layer0.log` | `$PY $A/scripts/run_eval.py --docs-dir $A/data/docs --questions $A/data/questions.jsonl --port 18765 --model qwen3.8:27b-mlx --placement $R8 --max-tokens 200 --out $A/eval_layer0.jsonl --tree $W`（層 0 = 既定） |
| `eval_layer1.jsonl`・`eval_layer1.log` | 同上に `--strict`（`--port 18766`、`--max-tokens` なし） |
| `score_layer0.json/.txt`・`score_layer1.json/.txt` | `$PY $A/scripts/score.py --questions $A/data/questions.jsonl --run $A/eval_layerN.jsonl --out $A/score_layerN.json > $A/score_layerN.txt` |
| 上 4 本の続け実行 | `bash $A/scripts/run_both.sh` |
| `z1_cmp.txt`・`z1_nondeterministic.txt` | `bash $A/scripts/z1.sh`（基点 `00f1bcc` を `git archive` した木と今の木で、`ask`・`chat`・`observe`・`route` の 8 通りを 2 回ずつ流して cmp） |
| `pytest_related_after.txt` | 実装後に（実装前には取り損ねた。判断記録 D15）`cd $W && $PY -m pytest -p no:cacheprovider -q -rf --tb=no tests/test_ask_question_cross.py tests/test_ask_question_cross_data.py tests/test_basis_policy_entry.py tests/test_basis_policy_table.py tests/test_basis_policy_w5d.py tests/test_question_cross_observe.py` |
| `pytest_fusion.txt` | `cd $W && $PY -m pytest -p no:cacheprovider -q -rs tests/test_serve_fusion.py tests/test_serve_fusion_ollama.py` |
| `pytest_full.txt`・`pytest_full_failures.txt`・`pytest_new_failures.txt` | `cd $W && $PY -m pytest tests -p no:cacheprovider -q -rf --tb=no`（最後に 1 回）、`grep '^FAILED' … \| sed 's/ - .*//' \| sort`、基線 `dev_00f1bcc_failures.txt` との `comm -13` |
| `paths_check.txt` | `git -C $W status --short` と許可パス外の検査 |

## 第 2 ラウンド（r2）で足したもの
| ファイル | 作り方 |
|---|---|
| `r2_old_behaviour_fails.txt` | 第 1 ラウンドの振る舞い（Vera の処理がスレッド任せ・`quantifiers` を無視）を 2 行の差し替えで再現して、新しいテストが落ちることを確かめた出力: `cd $W && $PY - <<'EOF'`（`VS.FusionConfig.run_vera` を直接呼びに、`G._NON_CENTER_KEYS = ("roles","quantifiers")` にして `pytest.main(['-p','no:cacheprovider','-q','tests/test_serve_fusion.py','-k','concurrent_http or extra_count or candidate_check','--tb=line'])`）`EOF` |
| `real_placement_thread_check.jsonl` | 本物の配置（R8）で。`$S/thr/d.txt`（`父が川で魚を釣った。`・`太郎が地図を渡した。`）と 3 問で `$PY $A/scripts/run_eval.py --docs-dir $S/thr --questions $S/thr/q.jsonl --port 18770 --model qwen3.8:27b-mlx --placement $R8 --strict --out $A/real_placement_thread_check.jsonl --tree $W`。`grep -c '"state": "ERROR"'` が 0 |
| `eval_q35_layer{0,1}.jsonl`・`score_q35_layer{0,1}.txt/.json`・`run_q35.done` | `bash $A/scripts/run_q35.sh`（`qwen3.5:4b`。`paste_results.py` が docs §4.1 に貼る） |
| `z1_cmp.txt` | `scripts/z1.sh` を直した（case 9 = 有効な role の route を足し、標準エラーも cmp する） |
