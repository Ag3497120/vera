# W3-a6 実装報告（R1）

## 概要

`RELATIVE_POSITION` 型と `gen_relpos` の絞り込み判定、名詞型・述語役割枠の生成形式、builder の任意入力と集計、役割枠を持つ配置だけで返す query の3鍵を実装した。述語枠の旧17型、既存名詞プロンプト、既存判定腕は保っている。受入基準は一部のみ確認できたため `done: false`。

## 差分に含まれるファイル

- 変更: `verantyx/coarse_types.py`、`verantyx/coarse_place.py`、`tools/gen_coarse_evidence.py`、`tools/build_coarse_placement.py`、`docs/COARSE_PLACEMENT.md`。
- 追加: `tests/coarse_place/test_coarse_place_w3a6_{build,decide,gen,query,role_check,types}.py`、`tests/coarse_place/data/w3a6_expect.json`、`artifacts/w3-a6/` の事前登録記録・期待hash・実行出力・監査スクリプト・判断記録。
- `w3a6_expect.json` は作業開始時に既にあった凍結ファイルで、hash `bea8c8a1dd97dbb6b1f5c4bd7d44c44ac7b322036cc2366027e714b37814af33` を維持した。試験の削除・変更・skip/xfail化・期待の弱体化はしていない。

## 受入基準

実行環境は `$W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S`、`$E=/Users/motonisihikoudai/vera-wiring/env/bin/python`、`$S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W3-a6-impl`。pytestコマンドは `artifacts/w3-a6/scripts/py.sh` を使い、`PYTHONPATH=$W`、`PYTHONDONTWRITEBYTECODE=1`、`-p no:cacheprovider` で実行した。

### N1 — 合格

- 実行: `$E` で `artifacts/w3-a6/scripts/n1_query_bytes.py` を使い、r7・r8全見出し語、配置なし固定200語、読解入口の配置なし・r8の前後出力を生成し、`$E artifacts/w3-a6/scripts/compare_n1.py` で比較。
- 結果: 5比較すべて `same`。r7 1,758,845行・sha256 `3feb7651ac8dcccac12e430e68fc32233e6792a3a7bc88823a0cd6cf6de79764`、r8 1,766,903行・`5db28ae6e323bfe10e107bd47550c657958818b15f962705a2567952eb6d941a`、配置なし200語・`a506a76cf8a262dbc4047444d4363b7486d56032eff77fa57b458cfa38ee2c27`、読解入口なし4,149行・`84b2c118d271153e92eb5c189b16867bc5da01992d2745673a9b3866e16e99c7`、読解入口r8 4,149行・`ce351ef41bd9cb3ee67867025911720d0214924f2ec662a56a4e7347801c7924`。
- テスト: `artifacts/w3-a6/scripts/py.sh -m pytest -q -p no:cacheprovider --basetemp=$S/bt_core tests/coarse_place/test_coarse_place_w3a6_*.py tests/coarse_place/test_coarse_place_w3a3_query.py` — 48 passed。出力 `tests_core.txt`。全数比較 `n1/n1_cmp.txt`。

### N2 — 未確認

生成後のr9がなく、`n2_table.tsv`、述語ごとの確認状態・根拠・分布割合を測っていない。事前の対象選別では8,311語、期待データ中の役割行はすべて対象に含まれた（`needs_check.txt`）。これは生成・受入の証拠ではない。

### N3 — 未確認

r9がなく、PLACEから変わった語、15語の判定、目視誤り率を測っていない。事前の名詞型対象一覧は2,721語で、凍結期待中の語はすべて一覧に含まれた（`needs_check.txt`）。

### N4 — 未確認

実生成枠のCONFIRMED標本60語がなく、目視評価、標本hash、誤り率は未測定。したがって `role_frame_min_sources` をN4に基づいて決めておらず、W3-a6設定ファイルも作っていない。

### N5 — 未確認

r9を構築していないため、281語の `SEEDS_PRED` と375語の参考集合をr8と比較していない。

### N6 — 未確認

監査役の測定対象となるr9/run1とその `content_sha256` は存在しない。隠しバンクは開いていない。

### N7 — 未達

- 関連試験: `artifacts/w3-a6/scripts/py.sh -m pytest -q -p no:cacheprovider --basetemp=$S/bt_pre_gen tests/coarse_place tests/test_gen_coarse_evidence.py tests/test_gen_coarse_evidence_pred.py tests/attack/w3a3 tests/attack/test_attack_w3a2_contract.py tests/attack/test_attack_w3b_placement_type_order.py tests/test_semantic_read_w3b1.py tests/test_semantic_read_w3b4.py` — 1,055 passed、5 failed。5件は指示書のC1に列挙された既存期待との衝突（`tests_pre_gen.txt`、各試験と変更提案は `frozen_conflicts.md`）。
- 全体: `artifacts/w3-a6/scripts/py.sh -m pytest -q -p no:cacheprovider --basetemp=$S/bt_full -rf --tb=no tests` — 189 failed、15,115 passed、46 skipped、75 xfailed、75 xpassed、1 warning、37 subtests passed。出力 `pytest_full.txt`。基線115件に対して新規74件・解消0件（`failure_delta.txt`）。
- 新規失敗74件の内訳: C1 5件、conduct系68件、指示書が環境由来候補として挙げる `test_s6_two_runs_agree_except_timing_and_recount_matches` 1件（`new_failures_explained.txt`）。conduct系のrun台帳55件に `SANDBOX_SELFCHECK_FAILED`／`sandbox-exec: sandbox_apply: Operation not permitted` が記録された（`sandbox_full_evidence.txt`）が、全体テストは `--tb=no` のため、68件すべてと環境記録の因果対応は確認していない。残るconduct系失敗を合格扱いしていない。

## 追加確認

- 既存名詞・述語プロンプトとschemaのhashは `prompt_sha.txt` に記録。名詞・述語型生成の対象一覧は各2,721語・8,311語で、予定上限831回。出力 `gen_plan.txt`。
- `git diff --check` は終了コード0。`git diff 0041606 -- tests/` に削除行・変更行なし。`git status --short tests/attack/w3a3` は空。テストが書き換えたr6問い合わせJSONLは48行すべて `frame_generated` だけの差と記録後、HEADの内容に復元した（`attack_side_effect.txt`）。
- 最終モジュール確認では `verantyx.coarse_types`、`verantyx.coarse_place`、`tools.gen_coarse_evidence`、`tools.build_coarse_placement` はすべて作業ツリーから読み込まれ、外部の `verantyx*` / `tools*` は `[]`（`check_modules_final.txt`）。読み取り専用配置・生成物のhashはすべて `OK`（`readonly_after.txt`）。`cache_dirs.txt` は空。

## 判断記録・逸脱・既知の穴

- 開始時のツリーは指示書の「差分なし」と異なり、型・生成器・判定関数・期待データ・一部テスト・事前登録が途中まであった。既存作業を保持して不足したbuilder/queryを続けた（`initial_state.txt`）。第1ラウンドのため前回レビュー指摘はない。
- チケットが限定的に許す本物の生成より、ユーザー指示のネットワーク禁止を優先した。モデル・試しの束・本番生成は0回。r9構築、N2〜N6の多く、60語の目視を実施していない。
- 期待ファイルは11役割行・10種類の述語を持つが、チケットの「9述語」と指示書の「9述語・10行」と異なる。凍結期待は変更せず、全11行を対象にした（`needs_check.txt`）。
- N7の5件のC1衝突は型追加の指定を優先し、試験を変更しない。conduct系新規失敗は台帳上のsandbox拒否だけでは各失敗との対応を証明できず、未解決として扱う。
- 指示書指定の報告先 `/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W3-a6/impl.r1.md` は、管理された書込許可範囲（作業ツリー・一時領域）の外にあるため書き込んでいない。この報告は作業ツリー内 `artifacts/w3-a6/impl.r1.md` に置いた。
- 既知の穴: 実生成の正確さ、閾値選定、r9差分、PLACEからの実移動数、直接RELATIVE_POSITION数、生成・構築所要時間、r9 hashを実測していない。人工データと偽codexのテスト結果を実データの証拠とはみなさない。
