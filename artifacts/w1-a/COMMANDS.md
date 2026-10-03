# W1-a / W1-a2 コマンドと出力

W1-a3 の記録を先に、その下に W1-a2 **第 3 ラウンド**の記録、第 2 ラウンド(「W1-a2 第 2 ラウンドの記録」)、第 1 ラウンドの記録(「W1-a2 の記録」)、W1-a の第 3 ラウンドまでの記録(「第 3 ラウンドの記録」)をそのまま下に残した。

## W1-a3 の記録(チケット W1-a2 の最終の継続。review.r3.md の必須 1・2。2026-10-03)

すべて `scripts_w1a3/py.sh` と同じ形(`env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<木>` ＋ `/Users/motonisihikoudai/vera-wiring/env/bin/python`、pytest には `-p no:cacheprovider`)。`W` = 作業ツリー、`A` = `W/artifacts/w1-a`、`S` = scratchpad の `W1-a3-impl`(`r3end` = 変更前の W の写し、`dev191` = `191db17` の展開、`A_r3end` = 変更前の `A` の写し、`committed` = s6 確認用のコミットした複製)。読み込まれた `verantyx*` が木配下であることは、検査スクリプトとテストの中で確かめる(`test_semantic_read_r4.py` の隔離テスト、`w1a3_review_r3_check.py` の隔離検査)。

| 目的 | コマンド | 出力 |
|---|---|---|
| 索引(CLAUDE.md の手順) | `python -m verantyx.cli index search "受身 尊敬 態 れる られる"` | `A/w1a3_index_search.txt`(`UNKNOWN_NOT_FOUND`。似たものは無かった) |
| テストの先書き・凍結(入口に通す前) | `tests/test_semantic_read_r4.py` を書く → `shasum -a 256 … > A/w1a3_tests_freeze.sha256`、`date > A/w1a3_tests_freeze_time.txt`(2 回目の凍結は H65) | `A/w1a3_tests_freeze.sha256`、`A/w1a3_tests_freeze_time.txt` |
| 変更前の写しで流す | `cp tests/test_semantic_read_r4.py S/r3end/tests/` → `cd S/r3end && py.sh S/r3end -m pytest -q -p no:cacheprovider -rf tests/test_semantic_read_r4.py` | `A/w1a3_r4_on_r3end.txt`(`57 failed, 18 passed`) |
| 入口の変更 | `verantyx/semantic_read.py`(`_NI_KARA_FREE_PREDICATES`・`_SPONTANEOUS_PREDICATES`・`_not_person_evidence` と `_voice_ja`、`NOT_PRODUCED` の voice の行) | — |
| Y1 入口のテスト・回帰確認 | `pytest -q -p no:cacheprovider -rf tests/test_semantic_read.py tests/test_semantic_read_r2.py tests/test_semantic_read_r3.py tests/test_semantic_read_r4.py tests/bank_score/test_bs_entry_semantic_read.py`、`shasum -a 256 -c A/w1a3_tests_freeze.sha256`(最後の行が OK)、`w1a2_review_r2_check.py`(W と dev)、`w1a3_review_r3_check.py`(W と `r3end`) | `A/w1a3_pytest_semantic_read.txt`、`A/r3_review_check_{after,dev}.txt`、`A/w1a3_review_r3_check_{after,r3end}.txt` |
| 入口の変化の表(第 3 ラウンドの終わりとの比較) | `py.sh S/r3end scripts_w1a3/entry_dump.py S/A_r3end/x3_after.jsonl S/entry_r3end.jsonl` と W で同じ → `python3 scripts_w1a3/entry_changes.py S/entry_r3end.jsonl S/entry_now.jsonl A/w1a3_entry_changes_vs_r3end.tsv` | `A/w1a3_entry_changes_vs_r3end.tsv`、`A/w1a3_entry_changes_summary.txt` |
| Y2 読解器が変わらないことの確認 | `harness.py --out S/soundness_after.json` → `cmp` ×、`a3_check.py` → `cmp`、`shasum -c` ×9(W で実行)、`check_hardcode.py --base 191db17`、`pytest tests/reading_soundness`、`r3_review_check.py`・`w1a2_review_r1_check.py`(`S/y3.sh`) | `A/freeze_check.txt`、`A/a6_hardcode.txt`、`A/pytest_reading_soundness.txt`(`soundness`・`a3`・`y3` は `S/` に出して `A_r3end` と `cmp`。すべて同一) |
| Y4 X3 | `bash scripts_w1a3/run_x3.sh`(`--extra` に `w1a3_review_r3_examples_ja.txt`・`w1a3_r4_inputs_ja.txt` を足した) | `A/x3_{dev,after}.jsonl`、`A/x3_table.tsv`、`A/x3_summary.txt`(`unclassified=0 regressed=0 wrong=0 misread=0`) |
| Y5 X4・X5 | `python3 scripts_w1a3/gen_examples.py`、`bash scripts_w1a3/run_x5.sh`、壊れた入力 7 型は 1 件ずつ `python -m verantyx.semantic_read …`、分類の比較は `A_r3end` の `results.jsonl` との突き合わせ | `A/semantic_read_examples.txt`、`A/w1a3_broken_inputs.txt`、`A/bank_score_b1_selfmade{,_r2,_r3}/`、`A/bank_score_b1_w1s_run.txt`、`A/w1a3_bank_class_changes.tsv`、`A/pytest_bank_score.txt` |
| Y6 全テスト(約 2.5 分) | `S/run_full.sh`(`pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --junitxml=A/w1a3_after_junit.xml tests`。`uptime` の 1 分平均が 8 以下で開始)、基線との `comm`、`tools/w0_1_compare_runs.py A/w1a2_start_junit.xml A/w1a3_after_junit.xml …` | `A/w1a3_after_pytest.txt`、`A/w1a3_after_junit.xml`、`A/w1a3_new_failures.txt`(s6 の 1 行)、`A/w1a3_compare.txt` |
| Y6 s6(コミットした複製) | W から `.git`・`artifacts`・`corpora` を除いて `S/committed` に写し、`git init && git add -A && git commit` した複製で `pytest tests/bank_score tests/test_semantic_read.py tests/test_semantic_read_r2.py tests/test_semantic_read_r3.py tests/test_semantic_read_r4.py` | `A/w1a3_s6_in_committed_copy.txt`(`590 passed`) |
| Y6 カバレッジ | `tools/read_coverage.py --n 1500 --stride 200 --json S/coverage_after.json`(`VERA_LEADS` を `env -i` の後ろに付ける)→ `cmp` で `A_r3end/coverage_after.json` と一致 | `A/w1a3_coverage_cmp.txt` |
| K の例の実測 | `scripts_w1a3/k_examples.py A/w1a3_k_sentences.txt`(DEV と W で) | `A/w1a3_k_examples.txt` |
| Y7 語の grep | 指示書 §6 Y7 の `WORDS` を `semantic_read.py` と docs の追加行に grep | `A/w1a3_review_words.txt`(0 行)、`A/w1a3_review_words_docs.txt`(0 行) |
| Y9 X7 | `recompute.py > A/recompute.md`、空行以外の全行が docs にあるかの確認 | `A/recompute.md`、`A/recompute_in_docs_check.txt`(0 行) |

## W1-a2 第 3 ラウンドの記録

すべて `env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<木>`(`scripts_r3/py.sh <木> <引数>` がこの形)の下で実行した。pytest には `-p no:cacheprovider`。`S` = `<scratchpad>/W1-a2-impl3`(自分用の作業場所。`DEV` = `S/dev191` は `git -C W archive 191db17 | tar -x -C S/dev191`。`rm -rf` は使わず、消さずに残した)。`A` = `W/artifacts/w1-a`。作業用スクリプトは `artifacts/w1-a/scripts_r3/` に写した(パスは scratchpad の絶対パスのまま)。
同じコマンドの形で再実行できるのは X1〜X7 の第 2 ラウンドの表(下)と同じ。ここに足したもの・変えたものだけを書く。

| 目的 | コマンド | 出力 |
|---|---|---|
| 凍結(読解器に通す前) | `python3 scripts_r3/mkbank_r6.py`(データだけを書く。読解器・入口を import しない)→ `shasum -a 256 tests/reading_soundness/ja_r6.jsonl > A/bank_freeze_r6.sha256`、`shasum -a 256 tests/bank_score/fixtures/B1_v2_r3/items.jsonl > A/b1v2_r3_fixture_freeze.sha256`(2026-10-03 07:24:43 JST) | `tests/reading_soundness/ja_r6.jsonl`(38 文)、`tests/bank_score/fixtures/B1_v2_r3/items.jsonl`(17 問)、`A/bank_freeze_r6.sha256`、`A/b1v2_r3_fixture_freeze.sha256` |
| X1 A1/A2/A3・レビューの回帰確認・凍結・A6(W と dev。まとめて) | `scripts_r3/run_meas.sh`(harness、`a3_check.py`、`r3_review_check.py`、`w1a2_review_r1_check.py`、**`w1a2_review_r2_check.py`(新)**、`shasum -c` ×9、`check_hardcode.py --base 191db17`、レビューの語の grep) | `A/soundness_{after,dev}.{json,txt}`、`A/a3_{after,dev}.txt`、`A/r4_review_check_{after,dev}.txt`、`A/r2_review_check_{after,dev}.txt`、`A/r3_review_check_{after,dev}.txt`、`A/freeze_check.txt`、`A/a6_hardcode.txt`、`A/a6_review_words.txt` |
| X1 A0 | 指示書 §6 の 3 本(許可外のファイル、触らないファイルの差分、既存テストの差分)と、採点規則の差分 | `A/A0_w1a2.txt`(0 バイト)。採点規則の差分は 0 行 |
| X1 pytest 版・入口のテスト・採点器のテスト | `pytest tests/reading_soundness`、`pytest tests/test_semantic_read.py tests/test_semantic_read_r2.py tests/test_semantic_read_r3.py`、`pytest tests/bank_score` | `A/pytest_reading_soundness.txt`、`A/pytest_semantic_read.txt`、`A/pytest_bank_score.txt` |
| X2(必須 1〜4 の型。dev の読みも) | `A/r3_required1_dump.txt`(dev と修正後の読みの対。`x3_dev.jsonl`・`x3_after.jsonl` から作った) | `A/r3_required1_dump.txt` |
| X3 | `bash scripts_r3/run_x3.sh`(`dump_reads.py` を DEV と W で、`x3_compare.py`)。`--extra` に `review_r3_examples_ja.txt`・`b1v2_r3_inputs_ja.txt`・`w1a2r3_probe_ja.txt` を足した | `A/x3_{dev,after}.jsonl`、`A/x3_table.tsv`、`A/x3_summary.txt`、`A/x3_classified.tsv`(手分類に 12 行を足し、2 行を STILL_WRONG に直した) |
| X4 | `python3 scripts_r3/gen_examples.py`(5 本のコマンドと 3 つの見本の全入力を 1 件ずつ別プロセスで) | `A/semantic_read_examples.txt` |
| X5 | `bash scripts_r3/run_x5.sh`(B1_v2・B1_v2_r2・B1_v2_r3 を `--profile v2 --entry mod-semantic-read` で、w1s の見本を `--profile w1s` で) | `A/bank_score_b1_selfmade{,_r2,_r3}/`、`A/bank_score_b1_w1s_run.txt` |
| X6 全テスト(約 3 分) | `pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --junitxml=A/w1a2r3_after_junit.xml tests`(`scripts_r3/run_bg.sh` の中)、基線との `comm`、`tools/w0_1_compare_runs.py A/w1a2_start_junit.xml A/w1a2r3_after_junit.xml …` | `A/w1a2r3_after_{pytest.txt,junit.xml}`、`A/w1a2r3_new_failures.txt`、`A/w1a2r3_compare.txt` |
| X6 s6 の確認(コミットした複製) | W から `.git`・`artifacts`・`corpora` を除いて scratchpad に写し、`git init && git add -A && git commit` した複製で `pytest tests/bank_score tests/test_semantic_read.py tests/test_semantic_read_r2.py tests/test_semantic_read_r3.py` | `A/w1a2r3_s6_in_committed_copy.txt`(`515 passed`) |
| X6 カバレッジ | `scripts_r3/run_cov.sh`(before は DEV で測り直して `cmp`。`VERA_LEADS` を `env -i` の後ろに付けて渡す)、`coverage_diff.py` | `A/coverage_before_cmp.txt`、`A/coverage_{after.json,sentences_after.jsonl,clauses_after.jsonl}`、`A/coverage_diff_output.txt`、`A/{dropped,gained,changed}.tsv` |
| 第 2 ラウンドとの比較 | `python3 scripts_r3/make_round2_copy.py <複製>`(W のコピーの `verantyx/`・`tools/`・`tests/`・`docs/` に対して第 3 ラウンドの変更を戻す)→ 複製で `harness.py`・`dump_reads.py`・`entry_dump.py` を流す → `python3 scripts_r3/compare_with_round2.py …`(`scripts_r3/run_r2cmp.sh` が dump_reads の部分) | `A/soundness_round2code.{json,txt}`、`A/r3_lost_vs_round2.tsv`、`A/r3_entry_changes_vs_round2.tsv` |
| X7 | `python tests/reading_soundness/recompute.py > A/recompute.md`、空行以外の全行が docs にあるかの確認(§6 の X7 のコマンド)。docs の §6 は `recompute.md` を `##`→`####` に直して貼った | `A/recompute.md`、`A/recompute_in_docs_check.txt`(0 行) |
| 補助: 質問応答への影響 | `VERA_CORPUS_ROOT=<空のディレクトリ> qa_probe.py <seed> A/qa_probe_after_seed<seed>.json`(seed 7, 101)、`qa_summary.py > A/qa_probe_summary.txt`(`scripts_r3/run_bg.sh` の中) | `A/qa_probe_after_seed{7,101}.json`、`A/qa_probe_summary.txt` |
| 探索(受入基準ではない。凍結の後) | `scripts_r3/probe.py <文のファイル>`(読解 `document_view` と入口の出力を並べる) | (スクリプトのみ。出力は残していない) |


## W1-a2 第 2 ラウンドの記録

すべて `env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<木>`(`scripts_r2/py.sh <木> <引数>` がこの形)の下で実行した。`VERA_CONSTRUCTIONS_OFF` は持ち込まない。pytest には `-p no:cacheprovider`。
記号: `W`・`A` は第 1 ラウンドと同じ。`S` = `<scratchpad>/W1-a2-impl2`(自分用の作業場所。`DEV` = `S/dev191` は `git -C W archive 191db17 | tar -x -C S/dev191`。**`rm -rf` は使わず、消さずに残した**)。
作業用スクリプトは `artifacts/w1-a/scripts_r2/` に写した(パスは scratchpad の絶対パスのまま。記録であって、W の外の作業場所に依存する)。

| 目的 | コマンド | 出力 |
|---|---|---|
| 新しい評価バンクの作成(読解器に通す前) | `python3 scripts_r2/mkbank_r5.py`(`ja_r5.jsonl` 68 文・`a3_r5.jsonl` 5 行を書くだけ。読解器は import しない) | `tests/reading_soundness/{ja_r5,a3_r5}.jsonl` |
| 凍結(2026-10-03 06:11:06 JST) | `cd W && shasum -a 256 tests/reading_soundness/ja_r5.jsonl tests/reading_soundness/a3_r5.jsonl > A/bank_freeze_r5.sha256` | `A/bank_freeze_r5.sha256` |
| B1 v2 の第 2 の自作の見本(36 問)の作成と凍結(06:11:48 JST) | `python3 scripts_r2/mkfix_r2.py`、`shasum -a 256 tests/bank_score/fixtures/B1_v2_r2/items.jsonl > A/b1v2_r2_fixture_freeze.sha256`、v2 の検証 `E PYTHONPATH=W PY -c "from tools.bank_score import schema; r=schema.read_items('tests/bank_score/fixtures/B1_v2_r2/items.jsonl','B1',None,'v2'); print(len(r),[x['id'] for x in r if x['errors']])"` | `A/b1v2_r2_fixture_freeze.sha256`(検証は `36 []`) |
| X1/X2/A3/A6/凍結/カバレッジの測定一式 | `scripts_r2/run_meas.sh`(中身: harness を W と DEV で、a3_check を W と DEV で、`r3_review_check.py` と `w1a2_review_r1_check.py` を W と DEV で、`shasum -c` 7 本、`check_hardcode.py --base 191db17`、DEV で `tools/read_coverage.py --n 1500 --stride 200` と `coverage_sentences.py` を測り直して `cmp`、W で同じ 2 本) | `A/soundness_{after,dev}.{json,txt}`、`A/a3_{after,dev}.txt`、`A/r4_review_check_{after,dev}.txt`、`A/r2_review_check_{after,dev}.txt`、`A/freeze_check.txt`、`A/a6_hardcode.txt`、`A/coverage_before_cmp.txt`、`A/coverage_after.json`、`A/coverage_sentences_after.jsonl`、`A/coverage_clauses_after.jsonl` |
| カバレッジの差 | `cd W && E PYTHONPATH=W PY tests/reading_soundness/coverage_diff.py A/coverage_sentences_before.jsonl A/coverage_sentences_after.jsonl --out-dir A --after-all A/coverage_clauses_after.jsonl --classified A/coverage_dropped_classified.tsv --gained-classified A/coverage_gained_classified.tsv` | `A/coverage_diff_output.txt`、`A/{dropped,gained,changed}.tsv` |
| X3 基点との比較(文の集合にカバレッジの標本を足した) | `scripts_r2/run_x3.sh`(dump_reads を DEV と W で、`x3_compare.py`)、未分類の行は `scripts_r2/classify_x3.py`(各行の理由を書いて `x3_classified.tsv` に追記)、第 1 ラウンドの手分類は `scripts_r2/refresh_classified.py` で今も新しい行だけを残した | `A/x3_{dev,after}.jsonl`、`A/x3_table.tsv`、`A/x3_classified.tsv`、`A/x3_summary.txt` |
| X4 読解の入口(5 本のコマンドと、2 つの見本の全入力) | `python3 scripts_r2/gen_examples.py`(`cwd=S` で `semantic_read` を 1 件ずつ別プロセスで) | `A/semantic_read_examples.txt` |
| X5 採点器(2 つの自作の見本。入口 `mod-semantic-read`) | `cd W && E PYTHONPATH=W PY -m tools.bank_score --profile v2 --bank B1 --items tests/bank_score/fixtures/B1_v2/items.jsonl --entry mod-semantic-read --tree W --out S/bs_b1 --python PY`、同じく `B1_v2_r2` → `S/bs_b1_r2`。出力を `A/bank_score_b1_selfmade/`・`A/bank_score_b1_selfmade_r2/` に写した。w1s の見本は `--profile w1s --items tests/bank_score/fixtures/B1/items.jsonl` | `A/bank_score_b1_selfmade{,_r2}/`、`A/bank_score_b1_w1s_run.txt` |
| X5 既存の採点器のテスト | `cd W && E PYTHONPATH=W PY -m pytest -q -p no:cacheprovider tests/bank_score \| tail -1` | `A/pytest_bank_score.txt` |
| X6 全テスト | `scripts_r2/run_full.sh`(`pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --junitxml=A/w1a2r2_after_junit.xml tests`)、基線との `comm -23`、開始時点の junit との `tools/w0_1_compare_runs.py` | `A/w1a2r2_after_{pytest.txt,junit.xml}`、`A/w1a2r2_new_failures.txt`、`A/w1a2r2_compare.txt` |
| 補助: 質問応答への影響 | `cd W && E PYTHONPATH=W VERA_CORPUS_ROOT=<空のディレクトリ> PY tests/reading_soundness/qa_probe.py <seed> A/qa_probe_after_seed<seed>.json`(seed 7, 101)、`qa_summary.py > A/qa_probe_summary.txt` | `A/qa_probe_after_seed{7,101}.json`、`A/qa_probe_summary.txt` |
| X7 数値の再計算 | `cd W && E PYTHONPATH=W PY tests/reading_soundness/recompute.py > A/recompute.md` | `A/recompute.md`(`docs/READING_SOUNDNESS.md` に貼ってある。`A/recompute_in_docs_check.txt` が全行の有無) |
| review.r1 の反例の回帰確認 | `cd W && E PYTHONPATH=W PY tests/reading_soundness/w1a2_review_r1_check.py`(DEV でも同じファイルを流す) | `A/r2_review_check_{after,dev}.txt` |
| A0 変更範囲・A6 レビューの語 | 指示書 §6 X1 の A0 の 3 本、`{ git -C W diff HEAD -- verantyx/ tools/; cat W/verantyx/semantic_read.py; } \| grep -n -E '<語の一覧>'` | `A/A0_w1a2.txt`、`A/a6_review_words.txt` |
| 凍結後の自作の probe(読解器・入口) | `python3 scripts_r2/probe_show.py A/w1a2r2_probe_ja.txt`(読解)、`scripts_r2/probe_entry.py`(入口) | `A/w1a2r2_probe_ja.txt`(88 文。出力は x3 の表に入る) |

---

## W1-a2 の記録

すべて `env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<木>` の下で実行した(`VERA_CONSTRUCTIONS_OFF` は持ち込まない)。
Python は `/Users/motonisihikoudai/vera-wiring/env/bin/python`、pytest には `-p no:cacheprovider`。どの Python 実行も、読み込んだ `verantyx*` が木の配下であることを自分で検査する(harness・a3_check・dump_reads・r3_review_check・test_semantic_read)か、採点器の出自の検査(`outside_count`)で見る。

記号:
- `W` = `/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S`(作業ツリー。HEAD `8d69747`、変更は未コミット)
- `DEV` = `<scratchpad>/W1-a2-impl/dev191`(基点 `dev`: `git -C W archive 191db17 | tar -x -C DEV`。W の外。**`rm -rf` は使わず、消さずに残した**)
- `START` = `<scratchpad>/W1-a2-impl/start8d`(開始時点: `git -C W archive HEAD | tar -x -C START`。W1-a2 の製品コード変更の前の読み。X3 の補助比較にだけ使った)
- `PY` = `/Users/motonisihikoudai/vera-wiring/env/bin/python`、`LEADS` = `/Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl`、`A` = `W/artifacts/w1-a`
- 以下 `E` は `env -i HOME=$HOME PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1`

| 目的 | コマンド(cwd) | 出力 |
|---|---|---|
| 開始時点の全テスト(手順 0。製品コード変更の前) | `cd W && E PYTHONPATH=W PY -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --junitxml=A/w1a2_start_junit.xml tests > A/w1a2_start_pytest.txt 2>&1` | `A/w1a2_start_junit.xml`, `A/w1a2_start_pytest.txt` |
| 新しい評価バンクの凍結(読解器に通す前。凍結の時刻は `impl.r1.md`) | `cd W && shasum -a 256 tests/reading_soundness/ja_r4.jsonl tests/reading_soundness/a3_r4.jsonl > A/bank_freeze_r4.sha256` | `A/bank_freeze_r4.sha256` |
| B1 v2 の自作の見本の凍結(入口に通す前) | `cd W && shasum -a 256 tests/bank_score/fixtures/B1_v2/items.jsonl > A/b1v2_fixture_freeze.sha256` | `A/b1v2_fixture_freeze.sha256` |
| 見本が v2 形式として正しい | `cd W && E PYTHONPATH=W PY -c "from tools.bank_score import schema; r=schema.read_items('tests/bank_score/fixtures/B1_v2/items.jsonl','B1',None,'v2'); bad=[x['id'] for x in r if x['errors']]; print(len(r), bad)"` | 標準出力(`65 []`) |
| X1/X2 評価バンク全部(修正前 dev) | `cd DEV && E PYTHONPATH=DEV PY W/tests/reading_soundness/harness.py --out A/soundness_dev.json > A/soundness_dev.txt` | `A/soundness_dev.{json,txt}` |
| X1/X2 評価バンク全部(開始時点。製品コード変更の前の W で流した。N1〜N4 の修正前の数) | `cd W && E PYTHONPATH=W PY tests/reading_soundness/harness.py --out A/soundness_start.json > A/soundness_start.txt` | `A/soundness_start.{json,txt}` |
| 同(r4 バンクを足す前の、開始時点の harness。`TOTAL misread=1`) | `cd START && E PYTHONPATH=START PY START/tests/reading_soundness/harness.py --out A/soundness_start_pre_r4.json > A/soundness_start_pre_r4.txt` | `A/soundness_start_pre_r4.{json,txt}` |
| X1/X2 評価バンク全部(修正後) | `cd W && E PYTHONPATH=W PY tests/reading_soundness/harness.py --out A/soundness_after.json > A/soundness_after.txt` | `A/soundness_after.{json,txt}` |
| A3 | `cd W && E PYTHONPATH=W PY tests/reading_soundness/a3_check.py > A/a3_after.txt; echo "exit=$?" >> A/a3_after.txt`(dev は `cd DEV && E PYTHONPATH=DEV PY W/tests/reading_soundness/a3_check.py > A/a3_dev.txt`) | `A/a3_after.txt`, `A/a3_dev.txt` |
| X2 第 3 ラウンドのレビューの反例(回帰確認。評価バンクではない) | `cd W && E PYTHONPATH=W PY tests/reading_soundness/r3_review_check.py > A/r4_review_check_after.txt; echo "exit=$?" >> …`(dev は DEV で同じファイルを流して `A/r4_review_check_dev.txt`) | `A/r4_review_check_{after,dev}.txt` |
| 凍結の検査 | `cd W && for f in bank_freeze bank_freeze_r2 bank_freeze_r3 bank_freeze_r4 b1v2_fixture_freeze; do shasum -a 256 -c A/$f.sha256; done` | `A/freeze_check.txt` |
| 評価と単体・変異テスト | `cd W && E PYTHONPATH=W PY -m pytest -q -p no:cacheprovider tests/reading_soundness \| tee A/pytest_reading_soundness.txt` | `A/pytest_reading_soundness.txt` |
| A6 決め打ちでない | `cd W && E PYTHONPATH=W PY tests/reading_soundness/check_hardcode.py --base 191db17 > A/a6_hardcode.txt; echo "exit=$?" >> A/a6_hardcode.txt`、レビューの語の grep(`{ git -C W diff HEAD -- verantyx/ tools/; cat W/verantyx/semantic_read.py; } \| grep -n -E '<語の一覧>'`) | `A/a6_hardcode.txt`, `A/a6_review_words.txt`(0 行) |
| A0 変更範囲 | 指示書 §6 X1 の A0 の 3 本 | `A/A0_w1a2.txt` |
| X3 文の集合の読みの書き出し(基点 / 修正後) | `cd DEV && E PYTHONPATH=DEV PY W/tests/reading_soundness/dump_reads.py --banks --extra A/r3_probe_ja.txt A/review_r1_examples_ja.txt A/r4_review_examples_ja.txt A/b1v2_inputs_ja.txt --out A/x3_dev.jsonl`、同じコマンドを `cd W && E PYTHONPATH=W PY tests/reading_soundness/dump_reads.py …`(`--out A/x3_after.jsonl`) | `A/x3_dev.jsonl`, `A/x3_after.jsonl`(入力: `A/r4_review_examples_ja.txt`, `A/b1v2_inputs_ja.txt` を新しく作った) |
| X3 比較と手分類 | `cd W && E PYTHONPATH=W PY tests/reading_soundness/x3_compare.py --dev A/x3_dev.jsonl --after A/x3_after.jsonl --gold-harness A/soundness_after.json --classified A/x3_classified.tsv --out A/x3_table.tsv \| tee A/x3_summary.txt` | `A/x3_table.tsv`, `A/x3_classified.tsv`, `A/x3_summary.txt` |
| X4 読解の入口(5 本のコマンドと、見本の全入力) | `$WD/gen_examples.sh`(中身: `cd $WD && E PYTHONPATH=W PY -m verantyx.semantic_read --text=…` を 5 本、続けて見本の入力 65 件を 1 件ずつ別プロセスで) | `A/semantic_read_examples.txt` |
| X4 入口のテスト | `cd W && E PYTHONPATH=W PY -m pytest -q -p no:cacheprovider tests/test_semantic_read.py` | `A/pytest_semantic_read.txt` |
| X5 採点器(自作の見本 65 問) | `cd W && E PYTHONPATH=W PY -m tools.bank_score --profile v2 --bank B1 --items tests/bank_score/fixtures/B1_v2/items.jsonl --entry mod-semantic-read --tree W --out $WD/bs_b1 --python PY`(出力を `A/bank_score_b1_selfmade/` に写した) | `A/bank_score_b1_selfmade/{summary.json,summary.md,results.jsonl,run_meta.json}` |
| X5 w1s の見本(採点の良し悪しは問わない。実行時エラー 0 の確認) | 同上で `--profile w1s --items tests/bank_score/fixtures/B1/items.jsonl`(`--out $WD/bs_b1_w1s`) | `A/bank_score_b1_w1s_run.txt`(終了コードと summary の分類) |
| X5 既存の採点器のテスト | `cd W && E PYTHONPATH=W PY -m pytest -q -p no:cacheprovider tests/bank_score \| tail -1` | `A/pytest_bank_score.txt` |
| X6 全テスト(修正後)と、基線・開始時点との比較 | `cd W && E PYTHONPATH=W PY -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --junitxml=A/w1a2_after_junit.xml tests > A/w1a2_after_pytest.txt 2>&1`、`comm -23`(基線 `/Users/motonisihikoudai/Projects/vera-impl/baselines/dev_191db17_failures.txt`)、`tools/w0_1_compare_runs.py` | `A/w1a2_after_{pytest.txt,junit.xml}`, `A/w1a2_new_failures.txt`, `A/w1a2_compare.txt` |
| X6 カバレッジ(before は DEV で測り直して `cmp`、after は W) | 指示書 §6 X6 のとおり(`tools/read_coverage.py` は無改変) | `A/coverage_{before,after}.json`, `A/coverage_sentences_*.jsonl`, `A/coverage_clauses_after.jsonl`, `A/{dropped,gained,changed}.tsv`, `A/coverage_diff_output.txt` |
| 補助: 質問応答への影響(修正後) | `cd W && E PYTHONPATH=W VERA_CORPUS_ROOT=<空のディレクトリ> PY tests/reading_soundness/qa_probe.py <seed> A/qa_probe_after_seed<seed>.json`(seed 7, 101)、`PY tests/reading_soundness/qa_summary.py > A/qa_probe_summary.txt` | `A/qa_probe_after_seed{7,101}.json`, `A/qa_probe_summary.txt` |
| X7 数値の再計算 | `cd W && E PYTHONPATH=W PY tests/reading_soundness/recompute.py > A/recompute.md` | `A/recompute.md`(`docs/READING_SOUNDNESS.md` §6 に貼ってある) |

## 第 3 ラウンドの記録(第 3 ラウンドまでの行はそのまま)

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
