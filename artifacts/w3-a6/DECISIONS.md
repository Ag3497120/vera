# W3-a6 実装役の判断記録（第1ラウンド）

## 指示書・途中作業

- 作業開始時点の差分は指示書 §0.1 の「差分なし」と異なっていた。初期状態の一覧は `initial_state.txt`。既存の事前登録、凍結済み期待、基点出力、型・生成器・判定関数の途中実装とテストを保持し、不足していた builder と query の実装を続けた。
- 事前登録と期待の凍結が製品コード変更より前だったことは `prereg_timeline.txt` に記録した。期待データの sha256 は `expect_freeze.sha256`、基点比較用の読み取り専用物は `readonly_before.sha256`。
- 第1ラウンドのため前回レビュー指摘は無い。
- ユーザーの「ネットワークを使わない」を優先した。チケット本文が1箇所だけ許す本物の生成も行っていない。モデル生成、試しの束、本番の呼び出しは0回。実測の対象一覧と呼び出し上限は `needs_ntype.meta.json`、`needs_role.meta.json`、`gen_plan.txt`。
- チケットと指示書の数量記述は一致しない。凍結済み期待ファイルは助詞・役割の行が11行、述語見出しが10種類であり、本文の「9述語」、指示書の「9述語・10行」と異なる。期待ファイルは変更せず、そのまま一覧包含を検査した。確認出力は `needs_check.txt`。

## C1〜C9

- **C1**: 指示書どおり `NOUN_TYPES` に `RELATIVE_POSITION` を追加した。既存試験は変更していない。関連テストでは、指示書に列挙された5件だけが失敗し、1,055件が通過した（`tests_pre_gen.txt`）。全文の変更提案は `frozen_conflicts.md`。
- **C2**: 述語枠のプロンプト・schema・読取の名詞型を `FRAME_NOUN_TYPES` に限定した。旧プロンプト・schema の固定 sha256 は追加テストで確認した（`tests_core.txt`）。
- **C3**: `gen_relpos` を `GEN_ARMS`・`ARMS` に加えず、既存の判定行を残して新しい分岐を追加した。人工入力の判定・基点との比較は `test_coarse_place_w3a6_decide.py` が通過（`tests_core.txt`）。
- **C4**: `_TABLES` と配置の表有無フラグを追加し、役割枠を読む入口を実装した。`_direct` 等の既存回答生成は変更していない。
- **C5**: `role_frames` 表がある配置だけで3鍵を出す。表を持たない小規模配置で3鍵が無いこと、表のある配置で最終位置に出ることを確認した（`tests_core.txt`）。N1の全数比較は r7 1,758,845行・r8 1,766,903行、配置なし200語、読解入口none/r8各4,149行すべてsame（`n1/n1_cmp.txt`）。
- **C6**: RELATIVE_POSITION 単独の direct は非生成腕が型を独立に決めた場合に限る規則を実装した。実配置でその語数を数える r9 は未構築のため、実測はない。
- **C7**: 名詞の既存形式を保ち、型申告用の `ntype` 形式を追加した。旧名詞・述語形式の固定 hash と偽 codex による台帳・collect・summarize の動作を確認した（`tests_core.txt`）。
- **C8**: 事前登録どおり定義系の腕を除外する一覧を使った。対象は2,721語で境界頻度は2、役割枠は8,311語で境界頻度は16（`needs_ntype.meta.json`、`needs_role.meta.json`）。この選別のため定義系の腕で決まった語は生成対象外で、相対位置の誤分類を拾えない場合が残る。
- **C9**: `gen_relpos` は query の axes に腕名・型数・why を出し、生成の出所詳細は `generated_noun_types` 表と manifest に保持する設計とした。`_direct` は触っていない。query から batch/model の詳細を直接返さないことは既知の制約。

## 閾値・検査範囲・既知の未完了

- 生成が無いため60語の目視標本を作れず、`role_frame_min_sources` の N4 事前評価と凍結は行っていない。したがって `config_w3a6.json` は作成していない。
- r9/run1 は作成していない。N2〜N5、r8→r9全差分、不変条件、構築時間・生成時間・生成成功率、r9 content hash は未測定。
- 役割枠の確認テストは人工分布と偽 codex で通過したが、本物の生成枠・r9での確からしさは示さない。
- 関連テストが再生成した `tests/attack/w3a3/r6_48_queries.jsonl` は、HEADとの差が48行すべてで `frame_generated` 鍵だけだった（`attack_side_effect.txt`）。指示書の不変条件に反するため、HEADの内容に戻し、最終 status が空であることを確認した。
- 手順15の全体テストは1回実行した。結果は189 failed、15,115 passed、46 skipped、75 xfailed、75 xpassed、1 warning、37 subtests passed。基線115件に対し新規74件・解消0件だった（`pytest_full.txt`、`failure_delta.txt`）。新規74件はC1の5件、原因を個別確認できていないconduct系68件、既知の環境候補 `test_s6_two_runs_agree_except_timing_and_recount_matches` 1件。conduct系のrun台帳55件に `SANDBOX_SELFCHECK_FAILED` と `sandbox-exec: sandbox_apply: Operation not permitted` が記録されたが、`--tb=no` のため各失敗IDとの因果対応は未確認（`sandbox_full_evidence.txt`、`new_failures_explained.txt`）。全体テスト受入は未達として残す。
- 関連試験が書き換えた `tests/attack/w3a3/r6_48_queries.jsonl` は、差が48行すべて `frame_generated` 鍵だけと確認してから、`git show HEAD:<path>` で基点内容へ戻した（`attack_side_effect.txt`）。`git restore` は読み取り専用 `.git/index.lock` により失敗したため、ファイル内容を直接復元した。
- 最終報告は指示書指定の監査ディレクトリが書込可能範囲外のため、作業ツリー内の `artifacts/w3-a6/impl.r1.md` に作成する。指定先への書込みは行わない。
- 指示書に無いテスト修正・skip/xfail・期待弱体化はしていない。ユーザーのネットワーク禁止により、指示書の生成・r9構築・生成依存受入基準を実行できなかった。
