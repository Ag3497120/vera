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
