# どのファイルをどのコマンドで作ったか
（`W`・`PY`・`A`・`S` は指示書の定義。python は `env PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 $PY`）
- `load_start.txt`・`status_start.txt`・`isolation.txt`・`isolation_end.txt`: uptime、git status/log、隔離の確認（verantyx* が W 配下だけ）。
- `index_search.txt`: `python -m verantyx.cli index search` 2 問。
- `repro_before_*.json`・`repro_after_*.json`: `python -m verantyx.cli --store $S/st ask --mode round5 --document <F> -- <問い>`。`repro_*_read.json`: `semantic_read.read('次郎は小説を読みたかった。', placement=None)`。`repro_after_read_r9.txt`: 同 `placement=$R9`。
- `prereg_time.txt`・`freeze.sha256`: `date`、`shasum -a 256`。
- `mk_data.py`: `python $A/mk_data.py $W/tests/reading_soundness` → `w16t1b_modality.jsonl`・`w16t1b_title.jsonl`。
- `a1_before.txt`・`a1_before_failed.txt`・`a1_after.txt`: `pytest tests/test_w16t1b_*.py [tests/test_w3f1_*.py] -q -rfE --tb=no -p no:cacheprovider`。
- `measure_range.py` → `range_before.tsv`・`range_after.tsv`。`range_changed.tsv`: 前後の `diff`。`reason_after.tsv`: `range_after.tsv` の理由の集計。
- `$S/measure.sh before|before2|after`（run_ask.py ×4）→ `before/`・`before2/`・`after/`。`k342_control*`・`k342_summary.txt`・`k342_changed.tsv`: `artifacts/w3-f1/k342_compare.py`。`k342_classified.tsv`: マスク後の分類（インライン python）。
- `$S/measure_entry.sh before|after` → `entry_{none,r9}.{before,after}.{jsonl,log}`。`entry_diff.py` → `entry_*_diff.{txt,tsv}`。
- `$S/measure_bank.sh before|after` → `bs_B{1,2,3}_{before,after}.txt`。`bs_*_compare.txt`: `python -m tools.bank_score.compare`。`bs_semantic_compare.txt`: run_meta の diff。
- `$S/measure_rel.sh before|after` → `related_files.txt`・`related_{before,after}.txt`。`related_diff.txt`: FAILED/ERROR 行の `diff`。
- `wrap_reach.txt`: document_view の包みの到達（6 つとも True）。`check_hardcode.txt`: 製品の差分の `grep`（rc=1）。
- `CHANGES.md`・`EXISTING_TEST_CONFLICTS.md`・`DECISIONS.md`・`COMMANDS.md`: 手書き（数値は上のファイルから）。

# 第 2 ラウンドの追加（`S` は scratchpad の `W16t1b-impl`）
- `prereg_r2_time.txt`・`docs_r2_time.txt`: `date`。`freeze_r2.sha256`（最初の版 `freeze_r2.first.sha256`）: `shasum -a 256` 6 ファイル＋時刻。
- `base_gate.py`・`mk_data.py <out> <基点の木> <python>`・`mk_data_r2.py <out> <基点の木> <python> <tmp>`: gate の規則で `w16t1b_modality.jsonl`・`w16t1b_converse.jsonl` を生成（基点の木は `git archive HEAD` の展開先 `$S/base`）。
- `modality_r1_frozen.jsonl`・`m4_gate_diff.txt`・`m4_nongate_diff.txt`・`m4_base_reasons.txt`: K819（M4）の前後の写し・差・基点の理由。
- `scan_ichidan_criteria.py`/`.txt`・`scan_ichidan_potential.py`/`.txt`: K818 の式の選択の根拠（入口 4,149 文の下一段）。
- `a2_before.txt`（基点の木＋新しいテスト、`pytest tests/test_w16t1b_modality_answer.py tests/test_w16t1b_converse.py tests/test_w16t1b_title_answer.py`）・`a2_after.txt`（`pytest tests/test_w16t1b_*.py tests/test_w3f1_*.py`）。
- `repro_r2_m2.txt`・`repro_r2_m3.txt`: レビューの確かめのコマンド。
- `$S/measure.sh after_r2` → `after_r2/`、`$S/measure_entry.sh after_r2`、`$S/measure_bank.sh after_r2`、`k342_summary_r2.txt`（`artifacts/w3-f1/k342_compare.py`）、`entry_*_diff_r2.*`（`entry_diff.py`）、`bs_B*_compare_r2.txt`（`tools.bank_score.compare`）。
- `measure_range_r2.py` → `range_before_r2.tsv`（基点の木）・`range_after_r2.tsv`・`range_changed_r2.tsv`。
- `related_after_r1.txt`（第 1 ラウンドの写し）・`related_after_r2_pre.txt`（製品を直したが旧テストのまま）・`related_after_r2.txt`（最終）・`related_diff_r2.txt`・`revised_tests_table.tsv`・`tests_revision.diff`。
