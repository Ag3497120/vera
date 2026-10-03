# W3-a 作業ログ

作業ツリー: `/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S`（HEAD 3d8bae9、tracked ファイルの変更なし）。commit していない。
Python は `artifacts/w3-a/py.sh`（venv ＋ PYTHONPATH ＋ PYTHONDONTWRITEBYTECODE）。読み込まれた `verantyx*` はすべてツリー配下（確認済み）。

## 手順ごと
- **手順 0**: `py.sh`、`index_search.txt`（6 件の問い。すべて `UNKNOWN_NOT_FOUND`＝既存物なし）、`DECISIONS.md`。
- **手順 1**: `verantyx/coarse_types.py`（型 17＋13、境界規則、種、表記の規則、既定の閾値）、`tests/coarse_place/test_coarse_place_types.py`。
- **手順 2**: 検査データを `*_spec.txt` に手で書き、`make_test_data.py` で JSONL にした（**1 回だけ実行。再実行しない**）。取り分け `holdout_2000.jsonl`（種 20261003）は
  `tools/build_coarse_placement.py holdout` で作成。`PREREG.md` を書き、`freeze.py` で `FROZEN.json` を作った。
  **凍結時刻 `2026-10-02T20:48:07Z`**。凍結した 7 ファイルの sha256:
  - typed_vocab.jsonl `10546bbf0e8cc312330cd5e3b51e93f393ab244aae4f16d98e4338223605f28b`
  - unknown_words.jsonl `f0d0932a61fa7ab32c5c940d79fff5d43853ada1b2fb6cf4f0b4f0e74b8017f9`
  - dev_vocab.jsonl `5a286f49dc59a0cc0be78295e1516d7c660dd1d6106aac16a816c6a64efb1832`
  - dev_unknown.jsonl `3f3172d04fda65a1b82bbf9664979728bda29613ced0fa25c936caa26637c1c7`
  - predicate_check.jsonl `1fb8c36281269dbecc32d0a5895c01e909eb8aaa48b43334445e14972a6439db`
  - holdout_2000.jsonl `c9772c535ee284b2cf10adcea45be63704b7f8494fe00778655c4f4ff1c30323`
  - PREREG.md `8a798bfcad5d39ba403c5819b887d8adb4c91c86114dcb37143ff7d47965ab5a`
  - （参考）凍結時の `coarse_types.py` `0956f593d8ba72c05138233db2c99e6aa722efd5f7fbe8dbde0478a8930bac61`。以後に変えた（`DECISIONS.md` 2）。
  `freeze_stat.txt` に stat の出力。凍結の検算はすべて OK（最後の確認は下の「検算」）。
- **手順 3**: `tools/build_coarse_placement.py`（holdout / build / verify）、`verantyx/coarse_place.py`（問い合わせ・入口）、`tests/coarse_place/` の単体テスト。
  合成材料は `tests/coarse_place/fixtures/jawiki_mini.jsonl`、codex 風 DB はテストの中で `tmp_path` に作る。
- **手順 4**: 1% 標本（`--sample-stride 100`）を 2 回（`sample/run1`・`run2`）。`content_sha256` が一致、`verify` が OK。
  dev の設定選びは、標本ではなく **全量の材料** の dev 用の建築（`build/coarse-W3a/dev/*`、抽出段の cache 付き）で行った。理由は `DECISIONS.md` 2-8。dev の全測定は `dev_runs/`（001〜054）。
- **手順 5**: 全量を 2 回（`full/run1`・`full/run2`、cache なし）。`content_sha256` が一致、`verify` が OK、`build_started_at_utc` は凍結時刻より後。
  最初の全量（第 1 回）は `manifest_full_round1_run1.json`（`eval_runs/001`〜`004` の配置）。設定を 2 点変えて作り直した（第 2 回、`DECISIONS.md` 3）。最終は第 2 回。
  ログ: `build_full_run1.log`・`build_full_run2.log`。manifest の写し: `manifest_full_run1.json`・`manifest_full_run2.json`。
- **手順 6**: `measure_w3a.py`（l1 l2 l3 l5 pred）。凍結データの測定は `eval_runs/001`〜`009`（全部残す）。独立な再計算: `independent_recompute.py`（L2・L3）、
  `independent_recompute_l1.py`（L1。チケットの snippet）。出力は `*.txt`。測定スクリプトの値と一致した。
- **手順 7**: 全テストを走らせた（`pytest_full.txt`）。基線との差は新しい失敗が 1 件（`new_failures.txt`）。原因と切り分けは `new_failures_explained.txt`
  （`verantyx/` 配下に新規ファイルがあると `git status -- verantyx` が空でないため。挙動の変更ではない。commit 後は通る見込み。単独でも再現する）。
- **手順 8**: `docs/COARSE_PLACEMENT.md`。数値の表は `render_docs_numbers.py` が `artifacts/w3-a/` から作る。`--check` は OK（終了コード 0）。
  間違えた語の一覧は `errors_final.md`。
- **手順 9**: `git status` のすべての行が許可パスに入ることを確認した。`lattice.py`・`placement.py`・`vocabulary.py` は触っていない。

## 各 run の所要時間（manifest の実測）
- sample/run1、sample/run2: 6.7 秒、6.4 秒。full/run1: 422.4 秒、full/run2: 306.2 秒（差の原因は確かめていない。時間は管理した条件での測定ではない）。
- 配置の大きさ（full）: 260,935,680 バイト。

## 未解決・既知の穴（隠さない）
- 受入基準の未達: L1 の被覆（トークン）、L2 の正答率・誤決定率（わずかに超過）・語末の罠の誤決定率、L3 の正答率。数値は `docs/COARSE_PLACEMENT.md` の結果の表。
- 述語の frame 規則表の精度は低い（`predicate_check` は報告用）。
- 1 文字の接尾だけが残る語は推定しない（設計どおり）。長さ 13 文字以上の語は分解しない。
- 最初の凍結データの測定を見たあとで設定を変えた（`DECISIONS.md` 3 に理由。dev の測定と実装の誤りの修理に基づく。第 1 回の測定も `eval_runs` に残す）。

## 第 2 ラウンド（レビュー r1 への対応）
- 変更の中身と判断は `DECISIONS.md` の §4。作業の順: (1) 判定規則を `coarse_types.decide_word` に集約（M1・M2）、(2) 名詞/述語の別・助数詞・文脈の表示を出所ごとに（M3）、
  (3) 述語の種の見直しと頻度一覧（M4）、(4) `]]` の読み方と括弧別表記（M5・M6-1）、(5) 分類階級語・`一部`・再帰分解・`kin_left`（M6-2〜4）、(6) 単体テストを足す（`tests/coarse_place/test_coarse_place_review2.py` ほか）。
- 抽出段を作り直した（`build/coarse-W3a/dev/stage_full5.pkl`）。dev の建築: `dev/r2a`（種の見直し前）、`r2b`（種・停止語の見直し後。`kin_left` 有効）、`r2c`（`counter_min=50`）、`r2d`（`max_chain_depth=6`）、
  `r2e`（`paren_alias_min=999` = 括弧別表記の腕を決め手にしない A/B）、`r2f`（最終の既定: `kin_left` 無効）。dev の測定は `dev_runs/055`〜`072`（すべて残してある）。
- 全量の建築は 2 組。**中間**: `full/r2/run1`・`run2`（`kin_left` 有効。凍結データの測定 `eval_runs/010`〜`015`）。**最終**: `full/r2b/run1`・`run2`（既定。`kin_left` 無効。凍結データの測定 `eval_runs/016`〜`020`）。
  標本: `sample/r2/*`（中間）、`sample/r2b/*`（最終）。第 1 ラウンドの配置（`full/run1` `full/run2` `sample/run1` `sample/run2`）は消さずに残した。全量の 2 本は同時に走らせたので所要時間は 1 本ずつの時より長い。
- 最終の検算の出力は `*_r2b.txt`（`independent_recompute_r2b.txt`、`independent_recompute_l1_r2b.txt`、`l4_cli_r2b.txt`、`check_frozen_r2b.txt`、`check_modules_r2b.txt`、`l6_*_r2b.txt`、`pytest_full_r2b.txt` など）、
  中間のものは `*_interim.txt`。判定規則の全量の検算: `audit_met_arms_full.json`（最終）・`audit_met_arms_full_interim.json`（中間）。
- 報告用の what-if（設定は変えない）: `dev_whatif_kin_left.txt`、`dev_whatif_recursion.txt`、`frozen_whatif_report_only.txt`。

## W3-a2
- 指示書 `review-impl/W3-a2/plan.md` に従う。作業の順: 手順 0 準備（索引 `index_search_w3a2.txt`、モジュール確認 `check_modules_w3a2_start.txt`）→ 手順 1 F4・F6 → 手順 2・3 F3・F2・F1 の実装とテスト（`tests/coarse_place/test_coarse_place_review3.py`）→ 手順 4 dev（`build/coarse-W3a/dev/r3*`、cache は `stage_full6.pkl`）…。詳しい判断は `DECISIONS.md` §5。
- 手順 4〜5: dev（`dev/r3a`〜`r3c5`、`r3d`、`r4t`、`r4a`・`r4b`）で F1 の設定と生成の格上げを決めた（DECISIONS §5-2〜5-9）。全量は `full/r3`・`r3b`・`r3c`（F1〜F6 のみ。r3c が最終）、`full/r4/run1`・`run2`（最終・生成あり）。
- 手順 6〜7: `needs_evidence.jsonl`（r3c の見出し語から 60,382 語）→ 生成器 `tools/gen_coarse_evidence.py` → 生成の実行（呼び出し 1,510、全束成功）→ `generated/definitions.jsonl`・`ledger.jsonl`。
- 手順 10〜12: 最終の全量 2 本・測定（`eval_runs/036`〜`040`）・独立な再計算・docs（第 11 節、`render_docs_numbers.py --check`）・全体テスト（新しい失敗は test_s6 の 1 件だけ）。
- 一時物・途中の配置はツリーの外 `build/coarse-W3a/`（消していない）に残してある。

## W3-a2 第 2 ラウンド（レビュー r1 への対応）
- 必須の修正 M1（格上げした語が head の段・単位の族に入っていた）と M2（欧文の非単位が助数詞の表に入り `4xx`・`5xx` が数量になった）。詳しい判断は `DECISIONS.md` §6。
- 作業の順: M1 の修正（`coarse_place._estimate`・builder の `placed_single`）とテスト（修正を外すと落ちる: `m1_test_without_fix.txt`）→ M2 の規則を測る前に書く（§6-1）→ 抽出段に `counter_nums`・`learn_counters` の欧文の規則 → 合成のテスト → 抽出段の作り直し `dev/stage_full8.pkl` → 格子（`latin_units_grid.py`。9 候補の結果 `latin_units_grid_prereg9.*`、K=6 を足した最終 `latin_units_grid.*`）→ dev `r5a` → 全量 `full/r5/run1`・`run2`（cache なし）→ 凍結データの測定 `eval_runs/041`〜`045` → docs（第 11.8 節）→ 全体テスト。
- 最終の出力は `*_r5.*`（`independent_recompute_r5.txt`、`audit_met_arms_r5.json`、`hub_spread_full_r5.txt`、`upper_bound_r5.json`、`p4_check_r5.txt`、`p1_cli_r5.txt`、`m1_m2_check_r5.*`、`manifest_full_r5_run1.json`、`p5_compare.*`）。第 1 ラウンドの `full/r4` と `*_r4.*` は比較のために残した。
- 生成した定義文（`definitions.jsonl`・`ledger.jsonl`）の sha256 は第 1 ラウンドから変わっていない。codex は呼んでいない。

