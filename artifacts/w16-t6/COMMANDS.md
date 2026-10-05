# W16-t6 実行したコマンド（作業ツリー W=/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t6-S）

前置き（毎回）: `cd $W && export PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1`、`PY=/Users/motonisihikoudai/vera-wiring/env/bin/python`、`A=$W/artifacts/w16-t6`、`SP=<scratchpad>/W16-t6`。

1. 隔離: `$PY -c "import verantyx.cli, verantyx.attest, verantyx.testimony_ledger, sys, os; print([m.__file__ for n,m in list(sys.modules.items()) if n.startswith('verantyx') and getattr(m,'__file__',None) and not m.__file__.startswith(os.getcwd())])" | tee $A/isolation.txt`（手順 0 で attest 無しの版を取り、最後に attest ありで取り直した）
2. 事前登録: `docs/ATTEST.md` を書き `shasum -a 256 docs/ATTEST.md | tee $A/prereg.sha256`
3. 合成データ: `python3 $A/synth/mk_synth.py`、`shasum -a 256 cases.jsonl expected.jsonl | tee freeze.sha256`、`shasum -a 256 -c freeze.sha256`
4. テスト（単体）: `$PY -m pytest -q -p no:cacheprovider tests/test_w16t6_parse.py tests/test_w16t6_verify.py`、続いて rerun・ledger・cli・compare・synth
5. T6-1: `$PY -m pytest -q -p no:cacheprovider tests/test_w16t6_synth.py | tee $A/t6_1_pytest.txt`、`$PY $A/synth/run_synth.py $SP/synth_run1 $A`（→ t6_1_synth.json / .txt）
6. T6-2: `$PY $A/compare/run_compare.py $SP/cmp_run2 $A/compare`（Ollama qwen3.5:4b、3 回。v1 は `compare/v1_signature_prompt/`）、`$PY $A/compare/recompute.py | tee $A/compare/recompute.txt`
7. T6-3: `$PY $A/replay/run_replay.py $A/replay --freeze`（初回: manifest 固定。b2 の改訂の後に `... $A/replay` で再実行。改訂前の要約・食い違い表を `*_before_b2_amendment.*` に退避）
8. T6-4: `$PY -m pytest -q -p no:cacheprovider tests/test_w16t6_rerun.py | tee $A/t6_4_rerun.txt`、`grep -n "subprocess\.\|os\.system\|os\.popen\|shell=True" verantyx/attest.py`
9. CLI の到達: `$PY -m verantyx.cli attest --help | head -20`、`$PY -m verantyx.cli attest $SP/S28.md --tree $SP/cmp_run2/S28 --rerun --extractor V`（手で 1 件）
10. 関係テスト: `$PY -m pytest -q -p no:cacheprovider tests/test_w16t6_*.py tests/test_semantic_read_w3e2_ledger.py tests/test_w10f04_ledger.py tests/test_w10f05_promote.py tests/test_w10f05_cli.py | tail -5 | tee $A/related_tests.txt`
11. 許可パス・追記のみ: `git status --short | tee $A/status_final.txt`、`git diff verantyx/cli.py verantyx/testimony_ledger.py | grep -c '^-[^-]'`、`find artifacts/w16-t6 \( -name 'test_*.py' -o -name '*_test.py' -o -name conftest.py \) | wc -l`
12. 自己照合（中間職の確認 10）: `$PY -m verantyx.cli attest <impl.r1.md> --tree $W --extractor b --partial-tree --search-dir artifacts/w16-t6 ... | tee $A/report_self_attest.txt`
