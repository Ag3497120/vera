# W3-a6 実装報告（第3ラウンド）

## 結果

**未完了（`done: false`）**。レビュー必須修正3を実装して試験した。N7を再実行した結果、新規失敗74件・解消0件で未達。ユーザー指示のネットワーク禁止により実生成を行えず、r9/run1 が無いため N2〜N6 と生成後の全数測定は実施できなかった。生成やr9を人工データで代替していない。

外部指定の報告先 `/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W3-a6/impl.r3.md` は作業ツリー外で、この実行環境の書き込み可能範囲に含まれない。報告は作業ツリー内の本ファイルに保存した。

## 作業と変更ファイル

第1・第2ラウンドの製品差分、凍結期待、試験を保持した。第3ラウンドでは製品コード、生成器、builder、期待データを変更せず、レビュー必須修正3として比較試験の基点読込を直し、測定記録と `docs/COARSE_PLACEMENT.md` §12.18 の実測区間を更新した。

- 既存の製品差分: `verantyx/coarse_types.py`、`verantyx/coarse_place.py`、`tools/gen_coarse_evidence.py`、`tools/build_coarse_placement.py`。
- 既存の追加試験と期待: `tests/coarse_place/test_coarse_place_w3a6_{build,decide,gen,query,role_check,types}.py`、`tests/coarse_place/data/w3a6_expect.json`。
- 第3ラウンドの変更: `tests/coarse_place/test_coarse_place_w3a6_decide.py`、`docs/COARSE_PLACEMENT.md`、`artifacts/w3-a6/r3/`。

期待データのsha256照合は成功（`r3/expect_freeze_check.txt`）。テスト・出力の削除、skip/xfail化、期待値の変更はしていない。

## 受入基準ごとの結果

### N1 — 既存出力の同一性

このラウンドでは製品コードを変えていないため、r7/r8全数・配置なし・読解入口の基点比較は第2ラウンドの測定を根拠として引き継ぎ、全数比較自体は再実行していない。第2ラウンドの5比較はすべて一致（詳細 `artifacts/w3-a6/r2/n1/cmp_all.txt`、`entry_hashes.txt`）。本ラウンドでは次のN1関連試験を再実行した。

```sh
PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -p no:cacheprovider --basetemp=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w3a6-review-r3/pytest-n1 tests/coarse_place/test_coarse_place_w3a6_query.py tests/coarse_place/test_coarse_place_w3a4_r7_unchanged.py tests/coarse_place/test_coarse_place_w5b.py tests/coarse_place/test_coarse_place_w3b5_frame_generated.py
```

結果 `40 passed in 1.52s`（`r3/tests_n1.txt`）。したがって全数N1の根拠は第2ラウンドの保存測定であり、このラウンドの再測定ではない。

### N2 — 役割つきの枠

未測定。実生成台帳・r9/run1 がなく、9シナリオ群の役割申告、期待10行、分布の `backed_by` を照合できない。`role_frame_min_sources` も未評価・未凍結。人工分布を使う役割確認試験の通過を生成回答の正しさの根拠にしていない。

### N3 — 相対位置の語

未測定。r9がないため15語のr9判定、r8からPLACEを含む判定が変わった名詞の全件、目視の誤り率は無い。

### N4 — 無作為60語の役割目視

未測定。実生成・r9の確認済み役割がなく、標本も目視表も作っていない。

### N5・(d)・全数不変条件

未測定。r9が無いため、seed比較、r8→r9差分、全見出し語の役割鍵・`gen_relpos`・直接RELATIVE_POSITIONの不変条件を実行していない。

### N6 — 監査用配置

未達。隠し評価バンクは開いていない。r9/run1とその`content_sha256`は無い。作業時の存在確認は `r3/r9_availability.txt` に `absent` と記録した。

### N7 — 全体テスト

実行コマンド:

```sh
PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -p no:cacheprovider --basetemp=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w3a6-review-r3/pytest-full -rf --tb=no tests
```

終了コード1。最終行は `189 failed, 15123 passed, 38 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 438.51s (0:07:18)`（`r3/pytest_full.txt`）。基線115件と失敗IDを正規化して比較した結果、新規74・解消0（`r3/after_failures.txt`、`new_failures.txt`、`fixed_failures.txt`）。内訳は既知のC1衝突5件、conduct系68件、S6 1件（`r3/new_failures_explained.txt`）。conduct系とS6は原因未確定の失敗として残し、環境要因として免責していない。N7は未達。

全体テストが `tests/attack/w3a3/r6_48_queries.jsonl` を変更した。48行のHEAD比較で変更キーが `frame_generated` のみと確認後、HEADの内容へ戻した。復元後sha256は実行前と同じ `556436a80a9d521af1826722dc789b25773f01d0d6e41d6422530498b1bbb642`（`r3/attack_side_effect.txt`）。他の2出力は前後でhash一致。

## 第2ラウンドレビューの必須修正

1. **本物の生成とr9、N2〜N6**: 未解決。チケットは生成手順を定めているが、今回の実行依頼はネットワーク禁止を明示している。禁止を優先し、LLM呼び出しをしていない。生成済みledger、`role_frame_min_sources` の事前評価、r9/run1は無く、N2〜N6を合格扱いにしていない。
2. **N7の追加失敗**: 未解決。全体pytestを再実行し、新規74・解消0を自分で比較した。conduct系68件をsandbox失敗と断定せず、差分から除外していない。S6 1件も未解決のまま記録した。
3. **`test_coarse_place_w3a6_decide.py` の一時ファイルとskip**: 修正済み。`git show 0041606:verantyx/coarse_types.py` の内容を `ModuleType` にメモリ上でexecし、基点履歴が無い場合はassertion failureにした。`tempfile`・`mkdtemp`・`pytest.skip`を削除した。レビュー指定のpytestコマンドは `6 passed in 0.15s`（`r3/tests_decide.txt`）。`rg -n 'pytest\.skip|pytest\.xfail|mkdtemp|tempfile' tests/coarse_place/test_coarse_place_w3a6_decide.py` は該当なし（`r3/test_hygiene.txt`）。

W3-a6追加試験とW3-a3 query試験は `48 passed in 2.29s`（`r3/tests_core.txt`）。初回はbasetempの親ディレクトリを作成していなかったためsetup errorになり、親を作成して再実行した。初回ログは成功ログで上書きされ、個別保存されていない。採用したのは再実行結果のみ。

## 判断記録・逸脱・既知の穴

- C1〜C9の設計判断は第1ラウンドの `artifacts/w3-a6/DECISIONS.md` と docs §12.18 の事前登録を維持した。今ラウンドで閾値を下げず、生成結果を作らず、既存試験を変更していない。
- 全数N1コマンドをこのラウンドで再実行せず、第2ラウンドの全数比較を参照した。今ラウンドの差分はテスト補助コードと測定記録に限り、製品コード差分は増えていない。全数N1を今ラウンドに実測したとは申告しない。
- W3-a6追加試験の初回は一時出力先の親ディレクトリ不足でsetup errorになった。出力先を作成した後の再実行は成功した。これは実行手順上の逸脱として記録する。
- 読み込まれた`verantyx`・`tools`モジュールの作業ツリー外一覧は空（`r3/check_modules_final.txt`）。凍結期待はhash一致（`r3/expect_freeze_check.txt`）。`__pycache__`・`.pytest_cache`は検索結果なし（`r3/cache_dirs.txt`）。`git diff --check` は空（`r3/diff_check.txt`）。
- 既知の穴: 実生成の正確さ、N2の期待10行と確認、N3の位置語誤分類率、N4の60語、N5/全差分/不変条件、r9の時間とhash、N6は未確認。conduct系68失敗の原因は未確定。N7も未達。
- 外部の指定報告先には書き込まず、作業ツリー内へ保存した。最終statusは `r3/status_final.txt`。
