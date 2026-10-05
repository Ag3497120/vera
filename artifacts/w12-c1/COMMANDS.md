# artifacts/w12-c1 — どのファイルをどのコマンドで作ったか（数は書かない。数は x*.json・x*.txt にある）

記号: `W`=`/Users/motonisihikoudai/Projects/vera-impl/wt/W12-c1-S`、`A=$W/artifacts/w12-c1`、`B=$W/build/initial-layers`（.gitignore の下: コミットされない）、`PY`=`/Users/motonisihikoudai/vera-wiring/env/bin/python`、
`R9`=`/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2`。どれも `PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1`、`VERA_PLACEMENT_LAYER*` は未設定。

| ファイル | 作り方 |
|---|---|
| `s0_*` | `scripts` なし（手順 S0 のコマンドそのまま） |
| `prereg_time.txt`・`data_freeze.sha256`・`data_freeze_time.txt`・`inputs/*` | 事前登録は `docs/INITIAL_LAYERS.md`（§1〜§7・§J）を書く前後の `date`。凍結は `find inputs -type f | sort | xargs shasum -a 256`。`inputs/x5_questions.jsonl` は `$PY scripts/x5_questions.py $W` |
| `x2_vocab.json`・`x2_sample60.tsv`・`x2_vocab_pass1.json`・`x2_sample60_pass1.tsv` | `scripts/build_vocab.sh`（pass1 は欄の一覧が足りない版。`FAMILY_FIELDS` を足して pass2。pass1 の出力は名前を変えて残した） |
| `x3_domain_db_{law,control}.json` | `$PY tools/build_initial_layers.py domain-db --codex-db $P4/general_qa.db --scene '法律と暮らし' --out $B/law/codex/general_qa.db --report …`（対照は `--control-of '法律と暮らし' --seed 20261005`） |
| 分野の配置（`$B/{law,control}/placement`） | `scripts/build_domain_placements.sh`（r9 の設定、`--generated*`・`--role-frames`・`--frozen`・`--compare-to` なし） |
| 直した版の配置（`$B/{law,control}_k2/placement`） | `scripts/build_domain_placements_k2.sh law`・`… control`（`def_min`=`alias_min`=`paren_alias_min`=2、`$B/r9_config_k2.json`） |
| `x3_{law,control}[_k2]_layer.json`・`$B/{law,control}[_k2]/*.sqlite`・`ledger.jsonl` | `scripts/make_domain_layer.sh <law|control|law_k2|control_k2> <scene> <report>` |
| `x3_law_k1.json`・`x3_law_k2.json`（=`x3_law.json`）・`x3_capacity_*.json`・`x3_sample60_*.tsv` | `$PY scripts/assemble_x3.py [_k2]`（目視の列は手で埋めた） |
| `x4_combine_law_bicycle.json`・`$B/combined/law+bicycle.sqlite` | `$PY tools/build_initial_layers.py combine --base $R9 --layer $B/law_k2/law_k2.sqlite --layer artifacts/w10-f05/r4_layer_real.sqlite --out $B/combined/law+bicycle.sqlite --ledger $B/combined/ledger.jsonl --report …` |
| `x4_bicycle/`・`x4_pottery/`・`x4_*.jsonl`・`x4_score.txt`・`x4_why_not_gained_*.txt` | `scripts/run_cold_start.sh <doc> <qa> <outdir> [<user layer>]`（陶芸は利用者の層なし: direct 0） |
| `x5_tiers.jsonl`・`x5_summary.json`・`x5_consistency.txt` | `VERA_PLACEMENT=$R9 $PY scripts/x5_run.py inproc --out … --tiers "vocab=$B/vocab/vocab.sqlite,law=$B/law_k2/law_k2.sqlite"`、`$PY scripts/score_tiers.py x5_tiers.jsonl x5_summary.json`、`… x5_run.py consistency --inproc x5_tiers.jsonl --out x5_consistency.txt --tiers …` |
| `x6_latency.json` | `VERA_PLACEMENT=$R9 $PY scripts/x6_latency.py --out x6_latency.json`（`--smoke` は 1 問） |
| `x6_http_*` | `$PY -m verantyx.cli --store <tmp> serve --no-llm --port 18931 --document inputs/docs_f01 --tier vocab=… --tier law=…` を立てて `curl` で 1 回 POST（127.0.0.1 のみ） |
| `x1_*.txt` | `scripts/x1_bytes.sh entry|serve|query`（基点の木は `git archive 5e7df09 | tar -x -C $SC/base`） |
| `pytest_*.txt`・`new_failures.txt` ほか | `$PY -m pytest tests -p no:cacheprovider -q -rfE --tb=no`、`$PY scripts/compare_failure_sets.py` |
| docs §M | `$PY scripts/paste_m.py`（出力ファイルから貼る） |

## 第 2 ラウンド（r1 レビュー対応）の出力
| 出力 | 作ったコマンド |
|---|---|
| `x2_vocab.json`・`x2_sample60.tsv`・`$B/vocab/vocab.sqlite`（踊り字を直した版。旧版は `*_v1_iter_unfixed.*`） | `scripts/build_vocab_v2.sh`（目視の列は手で埋めた） |
| `x2_m2_check_words.txt` | `sqlite3 -readonly $B/vocab/vocab.sqlite "select word,docs_human,origin_class from words where word in ('木公園','木上原','木駅','意気揚','筋骨隆','佐々木','代々木','人々','様々')"` |
| `x2_m2_counts.txt` | 旧新の vocab.sqlite と r9 の `headwords`（UNPLACED／MULTIPLE）を数える python（出力のみ保存） |
| `x3_overlap_law_control.txt` | `sqlite3 -readonly law_k2.sqlite "attach 'file:…/control_k2.sqlite?mode=ro' as c" "select count(*) from entries e where exists(select 1 from c.entries x where x.word=e.word and x.type=e.type)" "select count(*) from entries"` |
| `m4_synthetic/`・`m4_rerun_x4_bicycle_law.txt` | `scripts/why_not_gained.py <qa> <doc> <layer> <run none> <run layer>`（合成の入力は `m4_synthetic/` に置いた） |
| `x5_tiers.jsonl`・`x5_summary.json`・`x5_consistency.txt`・`x5_v1_vs_v2_vocab.txt`・`x6_latency.json`（旧版は `*_v1_vocab.*`） | 上の X5・X6 のコマンドを新しい vocab で流し直し |
| `pytest_m1_probe.txt` | `pytest tests/test_w12c1_nollm.py <probe> --rootdir=$W`（probe = 環境変数が空であることを見るだけのテスト。scratchpad に置いた） |
| `pytest_full.txt`・`new_failures.txt`・`fixed_failures.txt`・`pytest_new_failures*.txt`・`x1_entry.txt`・`x1_serve.txt` | r1 と同じコマンドで流し直し（r1 の出力は `*_r1.txt`） |

## 第 3 ラウンド（監査役の裁定への対応）の出力
| 出力 | 作ったコマンド |
|---|---|
| `s0_modules_r3.txt` | `$PY -c "import … ; print('foreign', bad, n)"`（`verantyx*` モジュールがすべて `$W` 配下か） |
| `x5_tiers.jsonl`・`x5_summary.json`・`x5_rerun_r3.log`・`x5_score_r3.txt`（`confidence_tiers/2` の定義。旧定義の出力は `x5_*_r2_agree_counts_abstain.*`） | `VERA_PLACEMENT=$R9 $PY scripts/x5_run.py inproc --out … --tiers "vocab=…,law=…"`、`$PY scripts/score_tiers.py x5_tiers.jsonl x5_summary.json`（`per_question`・`by_answered` を足しただけ。採点規則と単調性の判定は不変） |
| `x5_r2_vs_r3_agree.txt` | 旧新の 50 行を `agree`・`answered`・`schema`・timing を除いて比べる python（指示書 S4） |
| `x1_entry.txt`・`x1_serve.txt`（旧は `*_r2.txt`） | `zsh scripts/x1_bytes.sh entry`・`serve`（`query` は流し直していない: §J） |
| `pytest_w12c1.txt` | `$PY -m pytest -p no:cacheprovider -q tests/test_w12c1_{tiers,nollm,domain,vocab}.py` |
| `pytest_full.txt`・`new_failures.txt`・`fixed_failures.txt`（旧は `*_r2.txt`）・`pytest_related.txt` | `$PY -m pytest tests -p no:cacheprovider -q -rfE --tb=no`、`$PY scripts/compare_failure_sets.py`、関連テスト 7 本 |
| docs §M | `$PY scripts/paste_m.py`（O10・X5 の `answered` と組の数え上げ・X6 の注記・X7 の読み替えを足した） |

- r3 M6: `compare_failure_sets.py` は `new_failures_explained.txt` を書かない（手で保守するファイル。r2 の中身）。
