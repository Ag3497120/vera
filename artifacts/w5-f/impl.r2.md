# W5-f 実装報告 r2

## 結果

`done: false`。r1 レビューの F1 指摘は公開 reader で再検査し、指定理由での棄権を確認した。F2 は、方向語と実在の場所語が同じ品詞・構文になる対を選択的に扱えず未達。I6 全体テストでは基線にない失敗が76件あり、そのうち69件は未宣言のまま残った。実行した内容と未達を以下に記録する。

指定先 `/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W5-f/impl.r2.md` は作業ツリー外で書込許可がないため、本文はこのファイルに保存した。外部の報告先には書き込んでいない。

## r1 レビュー必須項目への対応

1. **F1 公開経路での引用・括弧断片**: `_quoted_focus_after_case_reason` を共有し、`w1a5_wrap` が読解結果を得た後、引用・括弧断片があり、かつ出力が readable の場合に `PLACEMENT_QUOTED_PARTICLE_AFTER_CASE:<格>` で棄権させる。レビュー freeze の11ケースを `none`・`fake`・`r8` で再生し、33試行で不一致0、全ケースが棄権し指定理由を返した（`r2_f1_holdout_results_final.txt`）。再生コマンドは `$PY artifacts/w5-f/scripts/verify_r1_f1.py > artifacts/w5-f/r2_f1_holdout_results_final.txt`。`tests/test_semantic_read_w5f.py` は11 passed（`r2_f1_w5f_tests_final.txt`）。初回の `document_view` 内実装は4 failとなり（`r2_f1_w5f_tests.txt`）、wrapper 後段へ移した。広い public gate の試行は配置なし150文のバイト一致を崩したので、引用・括弧形かつ readable の場合だけに狭め、その後の攻撃テストでは追加のバイト一致失敗がない（`r2_i1_attack.txt`, `r2_i1_attack_final.txt`）。

2. **F2 品詞だけの方向語 gate**: 語彙リストや表層判定を加えず、未達として残した。freeze の32対で、一般名詞方向語24件と場所語 controls 24件があり、filler を伏せた構文が24対一致した。POS triplet も20対一致し、現 gate が方向例を捕捉したのは8件（`r2_f2_invariance.txt`）。公開 replay の方向例32件はすべて棄権したが、目標理由 `RELATIONAL_NOUN_FILLER` は0件で、他理由による棄権だった（`r2_f2_public_results.txt`）。これらの replay コマンドは `$PY artifacts/w5-f/scripts/probe_r1_f2_invariance.py > artifacts/w5-f/r2_f2_invariance.txt` と `$PY artifacts/w5-f/scripts/verify_r1_f2_public.py > artifacts/w5-f/r2_f2_public_results.txt`。別の public probe では `兄が右で打った。` と `弟が右から倉庫へ打った。` が readable となり、具体的な場所語の読み取りも確認した（`r2_i2_f2probe.txt`、実行は `$PY artifacts/w5-f/scripts/f2probe.py "$W" rows > artifacts/w5-f/r2_i2_f2probe.txt`）。これを修正成功とは数えない。場所語 controls を保ち、同じ POS・構文の方向語だけを棄権させる非語彙規則を作れなかった。

3. **I6 の conductor 失敗と全体再実行**: conductor の対象群は68 failed（`r2_i6_conduct_failures_detail.txt`）。再現コマンドは `$PY -m pytest -p no:cacheprovider tests/test_conduct_routing.py -k J11_a_tie --tb=short` と `$PY artifacts/w5-f/scripts/debug_conduct_r1_sample.py`。1件の ledger replay は `SANDBOX_SELFCHECK_FAILED`, exit 71, `sandbox-exec: sandbox_apply: Operation not permitted` を記録し、acceptance は `SANDBOX_UNAVAILABLE` / `ACCEPTANCE_UNVERIFIED` になった（`r2_i6_conduct_sample_replay.txt`）。この1件の証拠だけでは68件すべての原因を断定しない。全体テストも最後に再実行し、宣言外に conductor 68件と `test_gen_coarse_evidence.py` 1件が残った（`r2_new_undeclared_by_module.txt`）。

## 受入基準と実行結果

すべての Python 実行では `/Users/motonisihikoudai/vera-wiring/env/bin/python`、`PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-f-S`、`PYTHONDONTWRITEBYTECODE=1` を用い、pytest には `-p no:cacheprovider` を指定した。読み込まれた `verantyx` は作業ツリー配下であることを harness の `foreign_modules=[]` と出力パスで確認した（`r2_i2_soundness.log`）。
以下の `$PY` は上記 Python 実行ファイル、`$W` は `/Users/motonisihikoudai/Projects/vera-impl/wt/W5-f-S`、`$R8` は `/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2`、`$FZ` と `$T` は指示書で固定された W5-d frozen evidence path と専用 scratch path を表す。コードブロック内のコマンドはこの環境で実行した。

### I1 攻撃の写し

コピーのバイト比較記録は5組とも SAME（`i1_attack_copies.txt`、r2 ではこのテストコピーを変更していない）。実行コマンド:

```sh
$PY -m pytest -p no:cacheprovider -q -rf --tb=line tests/attack/test_attack_w3b4.py tests/attack/test_attack_w3c4.py tests/attack/test_attack_w5e_*.py
```

結果は6 failed / 32 passed（`r2_i1_attack_final.txt`）で、計画に宣言された W3-b4 5件・W3-c4 1件と一致した。150文の読み取り安全テストの失敗行は D01・D03・D10。別の直接 gate テストは A/C 群を含む既知の K-W3B4-GATE misses を出し、抽出結果には A054・A059 もある（`r2_i1_grep_ids.txt`）。これは public frozen replay の結果とは別であり、直接 helper 側の既知の穴として隠さない。

### I2 読解

実行コマンド:

```sh
$PY tests/reading_soundness/w5f_gates_check.py --mode fake --out artifacts/w5-f/r2_i2_gates_fake.json
$PY tests/reading_soundness/w5f_gates_check.py --mode none --out artifacts/w5-f/r2_i2_gates_none.json
$PY tests/reading_soundness/w5f_gates_check.py --mode r8 --out artifacts/w5-f/r2_i2_gates_r8.json
$PY tests/reading_soundness/harness.py --out artifacts/w5-f/r2_i2_soundness.json --quiet
$PY tests/reading_soundness/w3b1_entry_dump.py --mode none --inputs artifacts/w3-b5/entry_inputs_r2.txt --out artifacts/w5-f/r2_i2_entry_none.jsonl
$PY tests/reading_soundness/w3b1_entry_dump.py --mode live --placement "$R8" --inputs artifacts/w3-b5/entry_inputs_r2.txt --out artifacts/w5-f/r2_i2_entry_r8.jsonl
$PY artifacts/w5-f/scripts/compare_entry_dumps.py none artifacts/w5-f/before/i2_entry_none.jsonl artifacts/w5-f/r2_i2_entry_none.jsonl artifacts/w5-f/r2_i2_entry_changed_none.tsv
$PY artifacts/w5-f/scripts/compare_entry_dumps.py r8 artifacts/w5-f/before/i2_entry_r8.jsonl artifacts/w5-f/r2_i2_entry_r8.jsonl artifacts/w5-f/r2_i2_entry_changed_r8.tsv
$PY artifacts/w3-b4/tools/run_rows.py --data tests/reading_soundness/ja_r10_w3b4.jsonl --out artifacts/w5-f/r2_i2_w3b4_rows.json --exceptions artifacts/w3-b4/expect_exceptions.json
$PY artifacts/w3-b5/tools/run_rows.py --data tests/reading_soundness/ja_r11.jsonl --out artifacts/w5-f/r2_i2_w3b5_rows.json --exceptions artifacts/w3-b5/expect_exceptions.json --narrowed artifacts/w3-b5/narrowed_rows.json
$PY artifacts/w5-f/scripts/f2probe.py "$W" rows
$PY artifacts/w5-f/scripts/w3b5_registered.py "$W" artifacts/w5-f/r2_i2_w3b5_registered.json
```

- `w5f_gates_check.py` の fake / none / r8 は各94行で misread 0（`r2_i2_gates_fake.txt`, `r2_i2_gates_none.txt`, `r2_i2_gates_r8.txt`）。
- 既存固定 harness は500文、changed 0、misread 0（基線も0）（`r2_i2_soundness_compare.txt`）。
- 4,149入力の none / r8 比較はそれぞれ9件だけ変更、readable 数は286 / 458で不変。全件が棄権理由だけの変更（`r2_i2_entry_none_compare.txt`, `r2_i2_entry_r8_compare.txt`）。
- W3-b4 は339行、misread / incomplete / unjudged / 入口期待不一致 / W3-b4期待不一致がすべて0、9例外（`r2_i2_w3b4_rows.txt`）。W3-b5 は649行で同5項目が0、23例外、narrowed 333行（`r2_i2_w3b5_rows.txt`）。
- 今回の W3-b5 登録行リプレイは misread 171（`r2_i2_w3b5_registered.txt`）。保存済み基線比較では misread 171→171、選択フィールド変更0（`proposals/k_f2_w3b5_registered_compare.txt`）。F2 の右の反例は上記のとおり残るため、I2 全体は未達。

### I3 根拠方針

実行コマンド:

```sh
$PY "$FZ/b_check.py" "$W" "$T/bcheck/run_fresh_20261004_0953"  # $FZ は指示書の W5-d frozen evidence path、$T は専用 scratchpad
$PY -m pytest -p no:cacheprovider -q tests/test_basis_policy_w5f.py tests/test_basis_policy_w5e.py tests/attack/test_attack_w5e_a3_sovereign_self_claim.py tests/attack/test_attack_w5d.py tests/attack/test_attack_w5c_classification_binding.py tests/attack/test_attack_w5c_confirmation_text_binding.py
$PY -c "import verantyx.basis_policy as b; print(b.CLASSIFY_VERSION, b.TABLE_VERSION, b.CONFIRM_ID_VERSION)"
```

W5-d B check は31件・fails 0（`r2_i3_b_check.txt`）。指定 pytest 群は59 passed / 1 skipped（`r2_i3_tests.txt`）。skip は既存の `test_frame_confirmed_partial_intersection_does_not_authorize_unbacked_type` で、分類ログに `UNCLASSIFIED_SKIP` と出ている。version 出力は `5 1 2`（`r2_i3_versions.txt`）。

### I4 質問後段

指定 `run_ask.py` を questions 111件と extra2 42件で再実行。両方とも WRONG 0・error_count 0。基線との verdict / text / sources source・line・text 比較は各 changed 0、変更 TSV は見出し1行のみ（`r2_i4_aq.log`, `r2_i4_extra2.log`, `r2_i4_aq_compare.txt`, `r2_i4_extra2_compare.txt`）。AQ では既存の FALSE_NONE 1件があるが比較対象でも変化なし。`pytest -p no:cacheprovider -q tests/test_ask_question_cross*.py` は73 passed（`r2_i4_tests.txt`）。比較コマンド:

```sh
$PY artifacts/w5-f/scripts/compare_ask_runs.py artifacts/w5-f/before/i4_aq_r1.jsonl artifacts/w5-f/r2_i4_aq.jsonl artifacts/w5-f/r2_i4_aq_changed.tsv
$PY artifacts/w5-f/scripts/compare_ask_runs.py artifacts/w5-f/before/i4_extra2_r1.jsonl artifacts/w5-f/r2_i4_extra2.jsonl artifacts/w5-f/r2_i4_extra2_changed.tsv
```

実行した質問コマンド:

```sh
$PY tests/observe/question_ask/run_ask.py --questions tests/observe/question_ask/questions.jsonl --docs-dir tests/observe/question_ask/docs --tree new --mode inproc --placement tests/observe/question_ask/placement_ask.json --out artifacts/w5-f/r2_i4_aq.jsonl --score artifacts/w5-f/r2_i4_aq_score.json
$PY tests/observe/question_ask/run_ask.py --questions tests/observe/question_ask/extra2/questions.jsonl --docs-dir tests/observe/question_ask/extra2/docs --tree new --mode inproc --placement tests/observe/question_ask/extra2/placement_extra2.json --out artifacts/w5-f/r2_i4_extra2.jsonl --score artifacts/w5-f/r2_i4_extra2_score.json
$PY -m pytest -p no:cacheprovider -q tests/test_ask_question_cross*.py
```

### I5 / I6

I5 は中間職の指示により実装役では測っていない。

最後に実行した全体テストコマンド:

```sh
date '+%F %T %z' > artifacts/w5-f/r2_pytest_full.started
env -i HOME=/Users/motonisihikoudai PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-f-S TMPDIR=/tmp /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -p no:cacheprovider -rf --tb=no tests > artifacts/w5-f/r2_pytest_full.txt 2>&1
date '+%F %T %z' > artifacts/w5-f/r2_pytest_full.finished
```

失敗差分は次のコマンドで生成・比較した。

```sh
grep -E '^(FAILED|ERROR) ' artifacts/w5-f/r2_pytest_full.txt | sed 's/^FAILED //; s/^ERROR //; s/ - .*//' | sort > artifacts/w5-f/r2_after_failures.txt
comm -23 artifacts/w5-f/r2_after_failures.txt artifacts/w5-f/basefail_ids.txt > artifacts/w5-f/r2_new_failures.txt
comm -23 artifacts/w5-f/r2_new_failures.txt artifacts/w5-f/declared_sorted.txt > artifacts/w5-f/r2_new_undeclared.txt
comm -23 artifacts/w5-f/declared_sorted.txt artifacts/w5-f/r2_new_failures.txt > artifacts/w5-f/r2_missing_declared.txt
comm -13 artifacts/w5-f/r2_after_failures.txt artifacts/w5-f/basefail_ids.txt > artifacts/w5-f/r2_reduced_failures.txt
```

全体テストの開始・終了記録は2026-10-04 12:03:32 +0900 / 12:11:41 +0900、pytest が報告した実行時間は487.04秒。結果は191 failed / 15,129 passed / 46 skipped / 75 xfailed / 75 xpassed（`r2_pytest_full.started`, `r2_pytest_full.finished`, `r2_pytest_full.txt`）。基線115件との差分は新規76件、宣言7件はすべて発生、宣言外69件、減少0（`r2_after_failures.txt`, `r2_new_failures.txt`, `r2_missing_declared.txt`, `r2_new_undeclared.txt`, `r2_reduced_failures.txt`）。宣言外の内訳は conductor 68件、generator 1件（`r2_new_undeclared_by_module.txt`）。I6 は未達。

## 変更ファイルと手順記録

- 製品コード: `verantyx/semantic_reader.py`（r2 の公開引用 gate を追加。`_coordination_gate` / K186 の r1 変更も保持）、`verantyx/basis_policy.py`（r1）。`cli.py` は変更していない。
- docs: `docs/READING_SOUNDNESS.md`, `docs/BASIS_POLICY.md`, `docs/OBSERVATION.md`。
- テスト・固定データ: W5-f の読解、根拠方針、ask テストと frozen data、W3-b4/W3-c4/W5-e 攻撃写し、および r1 から引き継いだ6本の既存 basis policy テスト改訂。R2 ではテストの削除、skip/xfail 化、期待値の弱体化はしていない。
- 作業開始時に未コミット差分が既にあったため破棄せず引き継いだ。`r2_review_holdout.sha256` はレビュー側 freeze `aea0fb3f6b8158dc8884851e019bd538ee7f2c0305f4e2808c40c26dc6732617` と一致する。未公開評価バンクと禁止された clone は開いていない。
- 実装後の全体テストが追跡下 `tests/attack/w3a3/r6_48_queries.jsonl` を変更したので、変更後版を artifact に保存し、HEAD 版を戻して `cmp` した（`r2_r6_48_queries_after_full.jsonl`, `r2_r6_48_queries_head.jsonl`）。
- `semantic_reader.py` の基点からの削除行数は0。静的区画確認では W5-e / K186 のほか wrapper の1行追加 hunk がある（`r2_semantic_deleted_line_count.txt`, `r2_semantic_hunks.txt`）。これは r1 レビューの F1 公開経路修正に必要な差分であり、計画の当初の区画想定からの逸脱として記録する。追跡下の既存 test 変更は計画記載の basis policy 6本のみ（`r2_tracked_test_changes.txt`）。
- 禁止された製品ファイルとの差分、許可外の追跡差分パス、許可外の untracked path は空（`r2_forbidden_product_diff.txt`, `r2_disallowed_paths.txt`, `r2_disallowed_untracked.txt`）。
- 最初の許可パス grep は `tests/` を完全一致扱いする式だったため、許可対象の既存テスト6本を出力した。その記録を `r2_disallowed_paths_bad_filter.txt` に残し、`tests/.*` に直して再確認した結果、許可外パス0件。
- 最後に実行した `git -C /Users/motonisihikoudai/Projects/vera-impl/wt/W5-f-S status --short` は `r2_status_after.txt` に記録した。テスト生成の tracked JSON は HEAD と `cmp` 済みで、終了時の `__pycache__` / `.pytest_cache` 検索と一時拡張子検索はいずれも空だった。

## 既知の穴

- `右` を含む方向読みが public reader で成立する。F2 を語彙・表層リストなしで直す方法は見つからず、棄権として残した。
- I1 の宣言済み6攻撃失敗、I6 の宣言外69失敗は解決していない。特に conductor 68件のうち、sandbox self-check を実測したのは再現用1件であり、全件の原因特定には至っていない。
- 指定外部報告先へ書けないため、報告のレビューは作業ツリー内の本ファイルを参照する必要がある。
