# W1-a コマンドと出力(第 3 ラウンド。第 2 ラウンドから変えた行に **第3** と付けた)

すべて `env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<木>` の下で実行した(`VERA_CONSTRUCTIONS_OFF` は持ち込まない)。

記号:
- `W` = `/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S`(作業ツリー)
- `DEV` = `/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/r3/dev`(第3: 第 3 ラウンドで作り直した。`git -C W archive 075d486 | tar -x -C DEV`。W の外。最後に消した)
- `PY` = `/Users/motonisihikoudai/vera-wiring/env/bin/python`
- `LEADS` = `/Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl`
- `A` = `W/artifacts/w1-a`

| 目的 | コマンド(cwd) | 出力 |
|---|---|---|
| 隔離・変更範囲(A0) | 指示書 §4 A0 の 3 本(`outside:` の検査、許可外の変更の列挙、`git diff --stat 075d486 -- tests/ ':!tests/reading_soundness'`) | `A/A0_final.txt` |
| 全テストの基線(第 1 ラウンドの作業前の W で測定。HEAD は `075d486` のまま) | `cd W && PY -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --junitxml=A/before_junit.xml tests > A/before_pytest.txt` | `A/before_pytest.txt`, `A/before_junit.xml`, `A/before_vs_w0-1.txt` |
| 第 1 ラウンドの評価バンクの凍結 | `shasum -a 256 tests/reading_soundness/{a3,en,ja,table7}.jsonl`(読解器に通す前) | `A/bank_freeze.sha256`。J1-17 の 1 行の凍結後の修正は第 2 ラウンドで取り消した(`ja.jsonl` は凍結時のハッシュに戻っている)。経緯の記録: `A/bank_gold_amendment.txt`, `A/bank_after_amendment.sha256`, `A/soundness_after_pre_gold_amendment.{json,txt}` |
| 第 2 ラウンドの評価バンクの凍結(読解器に通す前に書いた) | `cd W && shasum -a 256 tests/reading_soundness/{ja_r2,en_r2,a3_r2}.jsonl` | `A/bank_freeze_r2.sha256` |
| **第3** 第 3 ラウンドの評価バンクの凍結(harness に通す前に書いた。凍結前に似た形の文を probe した: docs §5) | `cd W && shasum -a 256 tests/reading_soundness/{ja_r3,a3_r3}.jsonl` | `A/bank_freeze_r3.sha256` |
| 第 2 ラウンドのバンクの最初の実行(規則を直す前の記録。誤読 2 件 K2-04, F5-06 を見つけた) | 当時のツリーで `harness.py --out …`(再現はできない。記録として残す) | `A/soundness_after_r2_first_run_before_np_en_fix.json` |
| A1/A2 修正前 | `cd DEV && PYTHONPATH=DEV PY W/tests/reading_soundness/harness.py --out A/soundness_dev.json \| tee A/soundness_dev.txt` | `A/soundness_dev.json`, `A/soundness_dev.txt` |
| A1/A2 修正後 | `cd W && PY tests/reading_soundness/harness.py --out A/soundness_after.json \| tee A/soundness_after.txt` | `A/soundness_after.json`, `A/soundness_after.txt` |
| **第3** M1〜M3 の probe(レビューの文と、同型の穴を探した 141 文。重複除去済み)を dev と修正後で表示 | `PY tests/reading_soundness/show_clauses.py A/r3_probe_ja.txt`(DEV と W で) | `A/r3_probe_ja.txt`(入力), `A/r3_probe_ja_dev.txt`, `A/r3_probe_ja_after.txt` |
| 評価と単体・変異テスト(A1 の pytest 版) | `cd W && PY -m pytest -q -p no:cacheprovider tests/reading_soundness \| tee A/pytest_reading_soundness.txt` | `A/pytest_reading_soundness.txt` |
| A3 修正前 / 後 | `cd DEV && PYTHONPATH=DEV PY W/tests/reading_soundness/a3_check.py > A/a3_dev.txt; echo "exit=$?" >> A/a3_dev.txt` / `cd W && PY tests/reading_soundness/a3_check.py > A/a3_after.txt; echo "exit=$?" >> A/a3_after.txt` | `A/a3_dev.txt`, `A/a3_after.txt` |
| 第 1 ラウンドのレビューの再現文(20 文＋英語 10 文)を dev と修正後で表示 | `PY tests/reading_soundness/show_clauses.py A/review_r1_examples_ja.txt`(英語は `--en A/review_r1_examples_en.txt`)を DEV と W で | `A/review_r1_examples_{ja,en}_{dev,after}.txt`(入力 `A/review_r1_examples_{ja,en}.txt`) |
| A4 全テスト(修正後)と比較 | `cd W && PY -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --junitxml=A/after_junit.xml tests > A/after_pytest.txt 2>&1`、`PY tools/w0_1_compare_runs.py A/before_junit.xml A/after_junit.xml --before-log A/before_pytest.txt --after-log A/after_pytest.txt > A/compare.txt 2>&1; echo "exit=$?" >> A/compare.txt` | `A/after_pytest.txt`, `A/after_junit.xml`, `A/compare.txt` |
| A5 カバレッジ修正前(`tools/read_coverage.py` 無改変) | `cd DEV && PYTHONPATH=DEV VERA_LEADS=LEADS PY tools/read_coverage.py --n 1500 --stride 200 --json A/coverage_before.json`、`PY W/tests/reading_soundness/coverage_sentences.py --n 1500 --stride 200 --out A/coverage_sentences_before.jsonl` | `A/coverage_before.json`, `A/coverage_sentences_before.jsonl`(`A/coverage_clauses_before.jsonl` は第 1 ラウンドの dev 測定) |
| A5 カバレッジ修正後 | `cd W && VERA_LEADS=LEADS PY tools/read_coverage.py --n 1500 --stride 200 --json A/coverage_after.json`、`PY tests/reading_soundness/coverage_sentences.py --n 1500 --stride 200 --out A/coverage_sentences_after.jsonl --all-clauses A/coverage_clauses_after.jsonl --expect A/coverage_after.json` | `A/coverage_after.json`, `A/coverage_sentences_after.jsonl`, `A/coverage_clauses_after.jsonl` |
| A5 差分と分類の検査 | `cd W && PY tests/reading_soundness/coverage_diff.py A/coverage_sentences_before.jsonl A/coverage_sentences_after.jsonl --out-dir A --after-all A/coverage_clauses_after.jsonl --classified A/coverage_dropped_classified.tsv --gained-classified A/coverage_gained_classified.tsv \| tee A/coverage_diff_output.txt`(`exit=0`) | `A/dropped.tsv`, `A/gained.tsv`, `A/changed.tsv`, `A/coverage_dropped_classified.tsv`(手で分類), `A/coverage_gained_classified.tsv`(手で分類), `A/coverage_diff_output.txt` |
| A6 決め打ちの検査 | `cd W && PY tests/reading_soundness/check_hardcode.py > A/a6_hardcode.txt; echo "exit=$?" >> A/a6_hardcode.txt`、`git -C W diff 075d486 -- verantyx/ \| grep '^+' \| grep -n -E '2025\|東京\|JSON\|API\|妹\|今朝\|先生\|生徒\|作文\|報告書\|モデル\|会議\|ありがとう'`(0 行)、`… \| grep -n -w -E 'crowded\|quickly\|red'`(0 行) | `A/a6_hardcode.txt`, `A/a6_grep.txt` |
| A7 数値の再計算 | `cd W && PY tests/reading_soundness/recompute.py > A/recompute.md` | `A/recompute.md`(`docs/READING_SOUNDNESS.md` の表と同一) |
| カバレッジ入力の署名 | `shasum -a 256 LEADS` | `A/leads.sha256` |
| 既存物の索引引き | `cd W && PY -m verantyx.cli index search "<語>"` | `A/index_search.txt`(第 1 ラウンド) |
| 補助: 単位受入デモ(dev / 修正後) | `cd <木> && PYTHONPATH=<木> VERA_CORPUS_ROOT=<空のディレクトリ> VERA_LEADS=LEADS PY -B tools/gold_{passive,caus_pass,double_neg,comparison,scramble}.py`(末尾 12 行) | `A/unit_demos.txt` |
| 補助: 質問応答への影響(修正後) | `cd W && PYTHONPATH=W VERA_CORPUS_ROOT=<空のディレクトリ> PY tests/reading_soundness/qa_probe.py <seed> A/qa_probe_after_seed<seed>.json`(seed 7, 101。dev は第 1 ラウンドの `A/qa_probe_dev_seed*.json`) | `A/qa_probe_after_seed{7,101}.json`, `A/qa_probe_summary.txt` |
