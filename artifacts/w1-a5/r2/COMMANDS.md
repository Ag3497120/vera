# W1-a5-2 (round 2, continuation): commands and outputs

Variables: `T=/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a5-S`, `PY=/Users/motonisihikoudai/vera-wiring/env/bin/python`, `RUN="env PYTHONPATH=$T PYTHONDONTWRITEBYTECODE=1 $PY"` (written as a shell function in zsh), `B` = the copy of the base `df4f001` (scratchpad `w1a5-impl/base_df4f001`, `cmp`-equal to `git show df4f001:` for the two reader files), `R8=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2`, `A=$T/artifacts/w1-a5`, `A2=$A/r2`, `S` = the scratchpad `w1a5-impl2`.
The first part of round 2 (the withdrawals, the data, the withdrawn list, the tests) is in the first table below (made by the previous run of this ticket; the files are unchanged). The second part (the continuation: the five gate functions put back, not called) is the second table.

## Part 1 (first run of round 2; files kept as they were)
| step | command | output |
|---|---|---|
| change record (K218) | text in docs 10G | `change_time.txt`, `CHANGE_K218.md` |
| data appended (14 rows), frozen | `$A/tools/append_k218_rows.py` | `bank_freeze_r2.txt`, `bank_freeze_r2.sha256`, `bank_append_time.txt` |
| withdrawn list (by rule), frozen before the implementation | `$A/tools/mk_withdrawn_k218.py` | `k218_withdrawn_rows.json`, `withdrawn_freeze.sha256`, `withdrawn_freeze_time.txt` |
| tests changed and frozen before the implementation | edit of `tests/test_semantic_read_w1a5.py` | `tests_freeze_r2.sha256`, `tests_freeze_r2_time.txt`, `tests_before_impl.txt` (138 failed, 319 passed, as expected before the implementation) |
| implementation (round-1 section minus the mark of an adverb and the quantity of a noun phrase) | edit of `verantyx/semantic_reader.py` | `impl_start_time.txt`, `semantic_reader.r1.py.txt` (the round-1 section) |

## Part 2 (this run: the continuation)
| step | command | output |
|---|---|---|
| isolation | `cd $T && RUN -c "import verantyx.semantic_read, verantyx.semantic_reader, verantyx.event_cross, sys; print([... not under $T])"` | printed `[]` (also in the old `isolation_check.txt`) |
| base copy | `git -C $T show df4f001:verantyx/semantic_read.py \| cmp - $B/verantyx/semantic_read.py` (and `semantic_reader.py`) | `BASE_OK` |
| addendum to the change record (before anything else) | docs 10G, change record, "追記" and the end of H235 | `change_time_addendum.txt` (07:02:58), `CHANGE_K218_addendum.md` |
| freeze check (data, list, tests unchanged) | `head -n 151 ja_r12.jsonl \| shasum -a 256`; `shasum -a 256 -c bank_freeze_r2.sha256 withdrawn_freeze.sha256 tests_freeze_r2.sha256` | `freeze_check_r2b.txt`, `freeze_check_time_r2b.txt` |
| record before the fix | copies of the outputs and the sha of the reader file | `pre_restore/` (`record_time.txt`, `shas.txt`, `semantic_reader.before_restore.py.txt`, the summaries and the entry outputs) |
| the five gate functions put back, not called | edit of `verantyx/semantic_reader.py` (python text replace from `semantic_reader.r1.py.txt`) | `restore_done_time.txt` |
| equivalence | `entry_dump.py --mode none --inputs entry_inputs.txt` in `$T` and in the minimal-change copy `$S/min`; `cmp` | `equivalence_min.txt` (`MIN_SAME`, `BEFORE_RESTORE_SAME`), `entry_none_after.jsonl` |
| entry r8 | `entry_dump.py --mode live --placement $R8 ...` | `entry_r8_after.jsonl`, `entry_r8_after.log` |
| C1 delta | `RUN $A/tools/delta_w1a5.py --before entry_*_base.jsonl --after entry_*_after.jsonl --out delta_*.jsonl --manual delta_manual.tsv --labels-out delta_*_labels.tsv` | `delta_none.jsonl`, `delta_r8.jsonl`, `delta_none_summary.txt`, `delta_r8_summary.txt`, `delta_*_labels.tsv` |
| C1 fake placements | `frozen_fixture_dump.py --tree $B` / `--tree $T`; `frozen_fixture_compare.py` | `frozen_fixture_{base,after}.jsonl`, `frozen_fixture_delta.txt` |
| C1 x3 | `dump_reads.py --banks --extra $S/new_sentences.txt` (the 165 sentences of ja_r12) in `$B` and `$T`; `cmp` | `x3_base.jsonl`, `x3_after.jsonl`, `x3_summary.txt` |
| C1 harness | `harness.py --out ... --quiet` in `$B` and `$T`; `$A/tools/cmp_soundness.py` | `soundness_{base,after}.json`, `soundness_compare.txt` |
| C2 | `RUN $A/tools/run_rows.py --data tests/reading_soundness/ja_r12.jsonl --placement none \| fixture \| $R8 --out ...` | `data_check_{none,fixture,r8}.{txt,json}` |
| cross | `RUN $A/tools/cross_new_reads_r2.py $T delta_none.jsonl` | `cross_on_new_reads.txt` |
| check_hardcode | `RUN $A/tools/check_hardcode_w1a5.py --base df4f001` | `check_hardcode.txt` |
| tests of the ticket | `RUN -m pytest -q -p no:cacheprovider tests/test_semantic_read_w1a5.py` | `pytest_w1a5.txt` |
| related tests | `RUN -m pytest -q -p no:cacheprovider -rf tests/test_semantic_read*.py tests/reading_soundness tests/test_question_cross*.py tests/test_ask_question_cross.py tests/test_event_cross*.py tests/test_observe*.py tests/event_cross tests/bank_score/test_bs_entry_semantic_read.py` | `pytest_related_after.txt`, `pytest_related_failures_after.txt` |
| full test (once, last) | `RUN -m pytest -q -p no:cacheprovider -rfE --continue-on-collection-errors tests` | `pytest_full.txt`, `pytest_full_start_time.txt`, `pytest_full_end_time.txt` |
| failure sets | `grep '^FAILED\|^ERROR' pytest_full.txt \| sed 's/ - .*//' \| sort -u`; `comm` against the baseline and against round 1 | `pytest_failures.txt`, `pytest_new_failures.txt`, `pytest_fixed_vs_baseline.txt`, `pytest_new_vs_r1.txt` |
| scope and docs checks | `git diff df4f001 -- verantyx/semantic_reader.py \| grep -c '^-[^-]'` (0), `git diff -U0 ... \| grep -c '^@@'` (1), `git diff --stat df4f001 -- verantyx`, the grep of the five functions and of `flags`, `git diff df4f001 -- docs \| grep -c '^-[^-]'` (0), the PREREG diff (empty) | `scope_check.txt` |
| a known error of the base | `SR.read('...うっかり鍵...')` in `$B` and in `$T` | `base_known_error.txt` |
| docs written after the full test (docs only), the tests that read the docs run again | `RUN -m pytest -q -p no:cacheprovider -rf <the 21 test files that mention READING_SOUNDNESS or READING_CONVENTIONS>` (`grep -rlE` over `tests` and `tools`) | `pytest_docs_readers_after_docs.txt` (3 failed, 3319 passed), `pytest_docs_readers_failures.txt` (3 lines, all in `pytest_failures.txt`: no failure that is not already counted), `pytest_docs_readers_start.txt`, `pytest_docs_readers_end.txt` |
| the one test that depends on load | `RUN -m pytest -q -p no:cacheprovider <node id>` run alone | `rerun_gen_coarse.txt` |
| conflicts and proposal | written by hand from the failures | `frozen_conflicts.md`, `proposed_test_changes.diff` (updated only; not applied; `git apply --check` dry run in `proposed_apply_check.txt`) |
| the five functions are the round-1 text | an `ast` comparison of every function of `semantic_reader.r1.py.txt` with the tree | `restore_verbatim_check.txt` (five `IDENTICAL`; only `_w1a5_reread` differs, as the change record says) |
| final check of the freezes, the order of the times and the isolation | `shasum -c` of the three freeze files, the times, the import check | `final_freeze_check.txt` |
