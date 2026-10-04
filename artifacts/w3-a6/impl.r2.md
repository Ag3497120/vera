# W3-a6 実装報告（第2ラウンド）

## 結果

**未完了（`done: false`）**。N1の旧配置との同一性と関連テストは再確認した。前回レビューの必須項目のうち生成・r9構築、生成後のN2〜N6測定は未実施であり、N7も基線より新規失敗が増えたため受入基準を満たしていない。

依頼先の報告先 `/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W3-a6/impl.r2.md` はこの実行環境の書込可能範囲外だった。ツリー内の本ファイルに報告を保存した。

## 作業と変更ファイル

第1ラウンドから残る製品差分・追加テスト・凍結期待を保持した。第2ラウンドでは製品コードとテストを変更していない。測定記録を `artifacts/w3-a6/r2/` に追加し、実測の追記を `docs/COARSE_PLACEMENT.md` の `w3a6-measured` 節に追加した。

- 第1ラウンドからの製品差分: `verantyx/coarse_types.py`、`verantyx/coarse_place.py`、`tools/gen_coarse_evidence.py`、`tools/build_coarse_placement.py`。
- 第1ラウンドからの追加: `tests/coarse_place/test_coarse_place_w3a6_{build,decide,gen,query,role_check,types}.py` と `tests/coarse_place/data/w3a6_expect.json`。
- 第2ラウンドの追記・測定記録: `docs/COARSE_PLACEMENT.md`、`artifacts/w3-a6/r2/`、本報告。

開始時に既存の未コミット差分があったため、捨てずに作業を継続した（`artifacts/w3-a6/initial_state.txt`、前回ラウンドの記録）。テストの削除、skip/xfail 化、期待値の変更はしていない。C1〜C9の設計判断は第1ラウンドの `artifacts/w3-a6/DECISIONS.md` に記録済みで、第2ラウンドで変更していない。

判断の要約: **C1** 型を追加し既存試験は変更しない。**C2** 述語枠の既存プロンプト/schemaを`FRAME_NOUN_TYPES`で維持する。**C3** `gen_relpos`を既存の腕一覧に足さず、判定段を追加する。**C4** 役割枠表の読込と表有無フラグを追加する。**C5** 役割枠表がある配置だけで3鍵を出す。**C6** 非生成腕が型を独立に決める場合に限りRELATIVE_POSITION単独のdirectを許す。**C7** 既存名詞形を保ち新しい`ntype`形式を加える。**C8** 事前登録した定義系腕除外の対象一覧を使う（第1ラウンド測定は名詞型2,721語・役割枠8,311語）。**C9** query axesと`generated_noun_types`表/manifestに生成情報を保持し、`_direct`は変更しない。詳細・制約は `DECISIONS.md`。

## 受入基準ごとの結果

### N1 — 既存配置と配置なしの回答同一性: 確認

基点 `0041606` の複製と現在のツリーで、`artifacts/w3-a6/scripts/n1_query_bytes.py <tree> <placement|none> <out.tsv> [words]` を実行し、全回答を `cmp` した。使用配置は r7/run1、r8/run2、配置なし。加えて読解入口の配置なしとr8を比較した。

- r7/run1: 双方1,758,845行、双方SHA-256 `3feb7651ac8dcccac12e430e68fc32233e6792a3a7bc88823a0cd6cf6de79764`。
- r8/run2: 双方1,766,903行、双方SHA-256 `5db28ae6e323bfe10e107bd47550c657958818b15f962705a2567952eb6d941a`。
- 配置なし: 双方200行、双方SHA-256 `a506a76cf8a262dbc4047444d4363b7486d56032eff77fa57b458cfa38ee2c27`。
- 読解入口: 配置なし・r8とも各4,149行。SHA-256はそれぞれ `84b2c118d271153e92eb5c189b16867bc5da01992d2745673a9b3866e16e99c7`、`ce351ef41bd9cb3ee67867025911720d0214924f2ec662a56a4e7347801c7924`。
- 5比較すべて `same`。出力: `artifacts/w3-a6/r2/n1/query_results.txt`、`cmp_all.txt`、`entry_hashes.txt`。

実行した関連テスト:

```sh
PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -p no:cacheprovider --basetemp=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/codex-w3-a6-r2/pytest-n1 tests/coarse_place/test_coarse_place_w3a6_query.py tests/coarse_place/test_coarse_place_w3a4_r7_unchanged.py tests/coarse_place/test_coarse_place_w5b.py tests/coarse_place/test_coarse_place_w3b5_frame_generated.py
```

結果 `40 passed in 1.62s`。出力: `artifacts/w3-a6/r2/tests_n1.txt`。

### N2 — 役割つきの枠: 未確認

生成出力とr9がないため、生成された述語枠、分布による確認、目視の正誤率を測っていない。期待データの凍結hashは `bea8c8a1dd97dbb6b1f5c4bd7d44c44ac7b322036cc2366027e714b37814af33`。実データは10述語・11役割行だが、期待の説明にある「9述語」と一致しない。差を勝手に直していない。内訳出力: `artifacts/w3-a6/r2/expect_inventory.txt`。

### N3 — 相対位置の生成後判定: 未確認

凍結期待には15語があることを確認したが、生成・r9がないため、PLACEから変わった語、PLACE単独のdirectのまま残った語、申告との対応は未測定。期待hashと件数は上記N2および `expect_inventory.txt` を参照。

### N4 — `role_frame_min_sources` と役割の目視: 未確認

生成後の分布・役割行がなく、閾値の選択も目視表も作成していない。`role_frame_min_sources` は未設定・未凍結。

### N5 — seed判定のr8との一致: 未確認

r9がないため、指示書所定のseed判定比較は行っていない。N1は既存配置での全回答比較であり、r9に対するN5の代替とは扱わない。

### (d) — r8からr9の述語変化: 未確認

r9がなく比較不能。変化が相対位置語の充填物型除外だけで説明できるか、差分腕、seed差は未測定。

### 不変条件 — 未確認

r9の全表・全見出し語がないため、指示書のr9全数不変条件は未実行。

### N6 — 監査用配置の識別: 未達

r9/run1と`content_sha256`がないため報告できない。禁止されたhidden評価バンクは開いていない。

### N7 — 全体テスト・失敗差分: 未達

全体テストの実行コマンド:

```sh
PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -p no:cacheprovider --basetemp=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/codex-w3-a6-r2/bt-full -rf --tb=no tests
```

最終行: `189 failed, 15123 passed, 38 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 572.56s (0:09:32)`。基線115失敗と比較して新規74、解消0。出力: `artifacts/w3-a6/r2/pytest_full_r2.txt`、差分: `failure_delta.txt`、一覧: `new_failures.txt`・`fixed_failures.txt`。

- 新規74件のうち5件は指示書のC1に列挙された型一覧の既存期待との衝突。試験は変更せず、詳細は `artifacts/w3-a6/frozen_conflicts.md`。
- 残るconduct系68件は、`pytest -q --rf --tb=short tests/test_conduct_routing.py tests/test_conduct_run.py tests/test_conduct_run_policy.py tests/test_conduct_run_settings.py tests/test_conduct_verify.py tests/test_conduct_verify_supervisor.py` でtraceback付き実行し、全体の失敗ID集合と一致した（`conduct_tracebacks.txt`、`conduct_full_compare.txt`）。`sandbox-exec -p '(version 1) (deny default)' /usr/bin/true` はexit 71、`sandbox_apply: Operation not permitted`（`sandbox_probe.txt`）。環境要因との対応を示す証拠は得たが、失敗自体は合格扱いにしていない。
- `test_s6_two_runs_agree_except_timing_and_recount_matches` は対象テストを単独再実行し、run metadataの `verantyx_untouched: false` を確認した。現在の作業差分を検出した結果であり、作業ツリーをクリーンにできない条件下で再現した（`triage_tests.txt`）。
- 停止signalの試験は単独実行で20秒timeoutしたが、同じ試験を基点の複製でも同じtimeoutで再現した。全体テストの失敗一覧には含まれていない（`base_stop_test.txt`、`triage_tests.txt`）。

W3-a6追加試験を含むコア確認は次の結果だった。

```sh
PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -p no:cacheprovider --basetemp=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/codex-w3-a6-r2/pytest-core tests/coarse_place/test_coarse_place_w3a6_*.py tests/coarse_place/test_coarse_place_w3a3_query.py
```

結果 `48 passed in 2.54s`。出力: `artifacts/w3-a6/r2/tests_core.txt`。

期待データの凍結hashも再確認した。`shasum -a 256 -c artifacts/w3-a6/expect_freeze.sha256` は `tests/coarse_place/data/w3a6_expect.json: OK`（`artifacts/w3-a6/r2/expect_freeze_check.txt`）。第2ラウンドではプロンプトを変更せず、生成も行っていない。

## 前回レビューの必須項目への対応

1. **実際の生成とr9**: 未実施。ユーザーのネットワーク禁止に従い、モデル呼び出しを行わなかった。r9/run1、r9のテスト・測定スクリプトも共有ビルドに存在しない（`r9_availability.txt`）。未解決。
2. **N2〜N5と非公開holdout**: r9/生成がないため未実施。非公開バンクにはアクセスしていない。期待データの10述語・11役割行と「9述語」記載の齟齬は記録した。
3. **N7の追加失敗**: 新規74件を再計測。C1の5件以外の69件をtraceback、sandbox probe、run metadata、基点比較で調査した。68件とsandbox拒否、1件と未コミット作業差分の直接的証拠を保存したが、全体の失敗数は基線より増えておりN7は未達。
4. **実測docs**: `docs/COARSE_PLACEMENT.md` のW3-a6測定節にN1ハッシュ、試験結果、N7の失敗差分、攻撃用JSONLの復元、r9未実施理由を追記した。生成・r9について架空の実測値は記載していない。

## 判断記録・逸脱・既知の穴

- `done: false`。N2〜N6とr9の不変条件を測れず、N7も基線より失敗が74件増えた。生成回数・effort・生成時間・構築時間・r9 content hashは存在しない。
- 実呼び出し数は第2ラウンドで0。明示的ネットワーク禁止を優先した。
- 期待データの述語数齟齬を補正しなかった。目視データ・判定を作らず、期待値も変更していない。
- 全体テストが追跡中の `tests/attack/w3a3/r6_48_queries.jsonl` を書き換えた。48行で `frame_generated` 鍵だけの差と確認し、HEADの内容に戻した。復元後SHA-256は `556436a80a9d521af1826722dc789b25773f01d0d6e41d6422530498b1bbb642`（`attack_side_effect.txt`、`attack_hashes_after_full.txt`）。
- 読み取り専用配置等11ファイルのSHA-256は全件OK（`readonly_check.txt`）。読み込まれた`verantyx` 23モジュールはすべて作業ツリー配下（`check_modules_final.txt`）。`__pycache__`・`.pytest_cache` は見つからなかった。
- N1で最初に誤って選んだr7/run2の結果は採用せず、指示書どおりのr7/run1で再計測した。
- `git diff --check` は空・exit 0（`diff_check.txt`）。作業ツリーの最終statusは `status_final.txt`。
