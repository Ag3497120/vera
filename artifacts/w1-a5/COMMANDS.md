# W1-a5: commands and the files they wrote (all under `artifacts/w1-a5/`)

Variables: `T` = the tree (`/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a5-S`), `PY` = `/Users/motonisihikoudai/vera-wiring/env/bin/python`, `B` = the copy of the base commit `df4f001` (`git archive df4f001 | tar -x -C <scratchpad>/w1a5-impl/base_df4f001`),
`R8` = `/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2`, `RUN` = `env PYTHONPATH=$T PYTHONDONTWRITEBYTECODE=1 $PY` (in `$B` the same with `PYTHONPATH=$B`).

| step | command | output |
|---|---|---|
| isolation | `cd $T && $RUN -c "import verantyx.semantic_read, verantyx.semantic_reader, verantyx.event_cross, sys; print([m.__file__ for ...  not under $T])"` | `isolation_check.txt` (`[]`) |
| index | `$RUN -m verantyx.cli index search "相の助動詞 遊離数量 副詞 量化 quantifiers"` | `index_search.txt` (UNKNOWN_NOT_FOUND) |
| pre-registration | docs 10G (K210-K218, H210-H225) and conventions 3 | `PREREG.md`, `prereg_time.txt` |
| facts of the base entry | `cd $B && $RUN(B) tools/reader_facts.py --inputs FILE --out TSV --tokens` | `reader_facts_prefreeze.tsv` |
| data | `$RUN tools/mk_data_w1a5.py` (writes `tests/reading_soundness/ja_r12.jsonl`), `shasum -a 256` | `bank_freeze.sha256`, `bank_freeze_time.txt`, `data_counts.txt` |
| tests (frozen before the code) | `tests/test_semantic_read_w1a5.py` | `tests_freeze.sha256`, `tests_freeze_time.txt`, `tests_before_impl.txt` |
| tests (after the corrections of the test change record) | `$RUN -m pytest -q -p no:cacheprovider tests/test_semantic_read_w1a5.py` | `pytest_w1a5.txt`, `tests_freeze_after.sha256`, `tests_edited_time.txt`, `tests_frozen_copy/`, `expect_exceptions.json` |
| C2 | `$RUN tools/run_rows.py --data tests/reading_soundness/ja_r12.jsonl --placement none|R8|fixture --out JSON` | `data_check_none.*`, `data_check_r8.*`, `data_check_fixture.*` |
| C1 entry dumps | `w3b1_entry_dump.py --mode none|live [--placement R8] --inputs entry_inputs.txt --out FILE` in `$B` and `$T` | `entry_{none,r8}_{base,after}.jsonl` |
| C1 delta | `$RUN tools/delta_w1a5.py --before .. --after .. --out delta_X.jsonl --manual delta_manual.tsv --labels-out ..` | `delta_none.jsonl`, `delta_r8.jsonl`, `delta_*_summary.txt`, `delta_*_labels.tsv`, `delta_manual.tsv` |
| C1 fake placements | `tools/frozen_fixture_dump.py --tree TREE --out FILE` in `$B` and `$T`, `tools/frozen_fixture_compare.py` | `frozen_fixture_{base,after}.jsonl`, `frozen_fixture_delta.txt` |
| C1 x3 and harness | `dump_reads.py --banks --extra new_sentences.txt`, `cmp`; `harness.py --out`; `tools/cmp_soundness.py` | `x3_base.jsonl`, `x3_after.jsonl`, `x3_summary.txt`, `soundness_{base,after}.json`, `soundness_compare.txt` |
| cross | `build_crosses` on the newly read sentences (no placement) | `cross_on_new_reads.txt` |
| hardcode | `$RUN tools/check_hardcode_w1a5.py --base df4f001` | `check_hardcode.txt` |
| related tests | `$RUN -m pytest -q -p no:cacheprovider -rf --deselect tests/test_semantic_read_w1a5.py tests/test_semantic_read*.py tests/reading_soundness tests/test_question_cross*.py tests/test_ask_question_cross.py tests/test_event_cross*.py tests/test_observe*.py tests/event_cross tests/bank_score/test_bs_entry_semantic_read.py` | `pytest_related_after.txt`, `pytest_related_failures_after.txt`, `conflict_trace_*.txt` (the base copy is not a git repository: its tests that call `git show` cannot be collected, so the comparison with the base is made with the committed list of failures) |
| full tests | `$RUN -m pytest -q -p no:cacheprovider -rfE --continue-on-collection-errors tests` | `pytest_full.txt`, `pytest_failures.txt`, `pytest_new_failures.txt`, `pytest_fixed_vs_baseline.txt`, `pytest_full_start_time.txt` |
| conflicts | written by hand from the traces | `frozen_conflicts.md`, `proposed_test_changes.diff` (a proposal, not applied) |
| probe of unseen sentences | read the changed outputs of 3 lists | `probe_unseen_inputs_{1,2,3}.txt`, `probe_unseen.txt` |
