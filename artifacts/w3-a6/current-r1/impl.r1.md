# W3-a6 実装報告 r1

## 結果

**done: false。** 役割つきの枠と RELATIVE_POSITION を含む既存の作業途中差分を活かし、指摘された役割説明と N7 文書の修正、事前登録・凍結・関連測定を行った。生成器の Codex 起動はすべて app-server 初期化で失敗し、生成結果も r9/run1 も得られていない。したがって N2〜N5 は未確認、N7 は関連テストに失敗があり、全受入基準の確認に至っていない。

指示上の第1ラウンド報告として指定ファイルを更新した。監査用ディレクトリに同名で存在していた以前の報告は、上書き前に `impl.r1.previous_attempt.md` へ原文保存した。

## 変更と作業ツリー

開始時点ですでに未コミット差分があり、`artifacts/w3-a6/initial_state.txt` に記録されていた。許可範囲内の coarse placement 実装・テスト・文書・測定物を引き継いだ。今回の明確なコード修正は `verantyx/coarse_types.py` の `ROLE_DESCRIPTIONS`（agent に恩恵表現で実際に動作した人を追加、time/causer/beneficiary の説明を補足）と `ROLE_FRAME_STATUSES`（CONFIRMED/ESTIMATED/NO_ROLE_FRAME）である。`docs/COARSE_PLACEMENT.md` は誤った N7 例外を取り除き、変更前後の全文と裁定を追記した。既存テストの期待値は変更していない。

最終 `git status --short` の出力は `artifacts/w3-a6/current-r1/status_final.txt`。作業ツリーの差分は `docs/COARSE_PLACEMENT.md`、`tools/build_coarse_placement.py`、`tools/gen_coarse_evidence.py`、`verantyx/coarse_place.py`、`verantyx/coarse_types.py`、`artifacts/w3-a6/**`、`tests/coarse_place/data/w3a6_expect.json` と追加の `tests/coarse_place/test_coarse_place_w3a6_*.py`。既存の途中差分と今回の変更を含む。r9 生成台帳は `build/coarse-W3a/full/r9/gen_ntype/` および `gen_role/` にあるが、`run1` はない。`git diff --check` は終了コード 0（出力なし、`artifacts/w3-a6/current-r1/diff_check_final.txt`）。テスト後に読み込まれた `verantyx*` のツリー外パスは空（`check_modules_after_tests.txt`）。`__pycache__` と `.pytest_cache` は検出されなかった（`cache_check_final.txt`）。コミット・push はしていない。

## 事前登録・凍結

`docs/COARSE_PLACEMENT.md` §12.18 に日時つきで方式・確認規則・生成プロンプト・測定表を事前登録した。凍結期待データ `tests/coarse_place/data/w3a6_expect.json` の SHA-256 は `bea8c8a1dd97dbb6b1f5c4bd7d44c44ac7b322036cc2366027e714b37814af33`。最終生成計画（`gen_plan_final.txt`）では名詞型 2,721 語／最大 207 呼び出し、役割枠 8,311 語／最大 624 呼び出し、gpt-6-luna・effort low・40 語/束・retry 2 を凍結した。抽出一覧の SHA-256 は ntype `6a871edbad30eee41fc98e3a6e74db036feae237ec3e3366c45fffc1b6e28424`、role `bd059e8a1a1885577a5e03395163f901cdafa90146d2716cd9dd9bbb640af92d`。60 語サンプルは指定 seed で生成してから SHA-256 `a134ac9c47060072911630ee8de7f9fadaca3f1c480a3afe9c7710af983da198` を記録した（`role_sample_meta.json`）。生成が空だったため目視判定は実施していない。

## 受入基準ごとの結果

### N1 — query の再測定は一致、読解入口は今回未実行

実行コマンドは `sh artifacts/w3-a6/current-r1/measure_n1.sh`。r7/run1 は 1,758,845 行、293.9 秒、SHA-256 `3feb7651ac8dcccac12e430e68fc32233e6792a3a7bc88823a0cd6cf6de79764`。r8/run2 は 1,766,903 行、297.1 秒、SHA-256 `5db28ae6e323bfe10e107bd47550c657958818b15f962705a2567952eb6d941a`。配置なしの固定 200 語は 0.0 秒、SHA-256 `a506a76cf8a262dbc4047444d4363b7486d56032eff77fa57b458cfa38ee2c27`。値は前回レビューが基点との byte 比較 exit 0 を記録したハッシュと一致する（`n1_comparison.txt`）。今回は基点ファイルとの独立 byte 比較を再実行していない。読解入口の 4,149 文も今回再実行していないため、N1 全体を今回自己確認したとはしない。

### N2 — 未確認

最終プロンプトでの生成を試みたが応答はなく、`role_frame`・status・根拠腕を評価できない。10 述語 11 助詞役割行の実値表、実台帳の effort、r9/run1 はない。

### N3 — 未確認

RELATIVE_POSITION の定義と 15 語の期待は凍結したが、r9/run1 がない。15 語の r9 判定、r8→r9 で PLACE から変わった名詞の全件、誤り率は測っていない。

### N4 — 未確認

60 語の標本は凍結したが、role 生成出力がないため、全助詞の目視分類、CONFIRMED の明らかな誤り数、誤り率を測っていない。

### N5 — 未確認

生成・r9 がないため seed 281 語の名詞型・述語型を r8 と比較していない。差分と理由の一覧もない。

### N6 — 実装役の測定対象外

チケットどおり監査役が測る項目のため実施していない。

### N7 — 関連テストで 3 件失敗、基線集合の判定は未完

実行したコマンド:

```sh
PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -p no:cacheprovider --basetemp=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/codex-w3-a6-current-r1/pytest-related tests/coarse_place tests/test_gen_coarse_evidence.py tests/test_gen_coarse_evidence_pred.py
```

結果は **356 passed, 3 failed in 22.65s**（全文 `artifacts/w3-a6/current-r1/tests_related.txt`）。失敗は `test_inventory_only_grows`（既存期待 17 型に対し必須変更後 18 型）、`test_the_predicate_prompt_lists_the_closed_inventories_from_coarse_types_and_no_test_word`、`test_the_schema_is_closed_and_its_enums_are_the_inventories`（述語枠の既存テストが新しい名詞型まで要求する）である。既存テストを弱めず維持した。チケットの全体失敗基線との集合比較はしていないため N7 は未達判定を保留する。

### 生成・r9 の実測

`artifacts/w3-a6/current-r1/generate_and_collect.sh` を実行。ntype 207 回、role 624 回、計 831 回すべてが exit 1。各 stderr は `Error: failed to initialize in-process app-server client: Operation not permitted (os error 1)` で、両方とも出力 0 件。集計は `generation_failure_counts.txt`、詳細は `generation_failure_detail.txt` と `build/coarse-W3a/full/r9/gen_{ntype,role}/summary.json`。これはモデル応答の内容ではなく、Codex CLI 初期化失敗である。生成を必要とする N2〜N5、r9 の構築時間・実生成呼び出し manifest は未達。

## レビュー指摘・判断記録・既知の穴

- 既存の `review.r1.md` が指摘した agent の説明不足を一般的な説明に修正した。語の一覧や例文は足していない。
- N7 の「NOUN_TYPES 追加による衝突は別に宣言」という受入例外を削除し、§12.18 に変更前後と未解決の判断を記録した。18 型化と既存 17 型固定テストの衝突は残る。既存期待の変更は行わず、監査役の裁定が必要。
- 前回レビューの N1 基点比較は参照記録と今回のハッシュ照合にとどまり、読解入口 byte 比較は今回行っていない。N1 は部分確認として扱う。
- 生成の結果は「誤り」ではなく環境初期化失敗により「未生成」。出力がないものを正しい／誤りと推定していない。N2〜N5 の品質主張は行わない。
- 関連テスト以外の全体テストは実行していない（チケットの役割分担に従った）。`__pycache__` 等はなし。作業対象外の隠し評価バンク・他 worktree は開いていない。ネットワーク試行は指定された生成スクリプト経由の Codex 起動のみ。

## 未解決

Codex app-server 初期化が可能な実行環境で生成を完了し、r9/run1 と manifest を作成した後、N2〜N5 を実測すること。加えて監査役による N6 と N7 基線判定、18 型化と既存テスト期待の契約裁定が必要。
