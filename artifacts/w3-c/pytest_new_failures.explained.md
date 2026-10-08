# 基線にない失敗の説明（W3-c、全体テストの結果 `pytest_full.txt`）

基線 `/Users/motonisihikoudai/Projects/vera-impl/baselines/dev_5cae978_failures.txt` に無い失敗は 2 件（`pytest_new_failures.txt`）。どちらも W3-c の差分が原因ではない。

## 1. `tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches`（指示書の F9）

- 原因: このテストは `git status --porcelain -- verantyx` が空でないと落ちる。作業ツリーに `verantyx/` の未コミットの変更があるあいだは必ず落ちる（実装役はコミットしない）。W3-b でも同じ理由で新しい失敗として出た（`docs/EVENT_CROSS.md` の「基線にない失敗の説明」）。
- 確かめ方: 基点 5cae978 の作業ツリーに W3-c の差分（`verantyx/observe.py` `salience.py` `cli.py` `semantic_realize.py`、docs、tests）をコピーして **スクラッチのクローンの中でコミット**（作業ツリーではコミットしていない。コミットは `1258c64`、ネットワーク不使用）し、同じテストを流すと通る。
  - 作業ツリー: 落ちる（`recount ... summary.json 一致 / summary.md 一致` を出したあとの `git status` の検査で落ちる）。
  - スクラッチのコミット済みクローン: 通る（`artifacts/w3-c/pytest_two_in_scratch_committed_clone.txt`）。
  - 基点だけのクリーンなクローン: 通る（`artifacts/w3-c/pytest_two_in_clean_clone_5cae978.txt`）。

## 2. `tests/test_p4_abilities.py::test_speech_act_drafts_fill_new_roles_and_reread`

- 基点 5cae978 だけのクリーンなクローン（差分なし）でも同じ検査で落ちる（`artifacts/w3-c/pytest_two_in_clean_clone_5cae978.txt`、`out["kind"] == "answer"` が `unknown`）。W3-c をコミットしたクローンでも同じ（`pytest_two_in_scratch_committed_clone.txt`）。したがって W3-c の差分が原因ではなく、基点でこの環境（この実行の `env -i` の環境、索引や設定のある場所）では落ちる。基線の一覧を作った実行では落ちていなかったので、基線の実行と今の実行の環境の違い（時間・索引の置き場所・設定のいずれか）による。環境のどの値かは特定していない。
- このテストの対象（発話行為の下書き）は W3-c が触るファイル（`observe.py` `salience.py` `cli.py` の `observe` の追加 `semantic_realize.py` の末尾の追加）の外。

## 基線にあって今回通ったもの

- `tests/test_one_trace.py::test_every_default_integration_part_has_a_trace`: 基線の注記どおり Air 固有のテストで、この実行では通った（基線から減った 1 件。W3-c の変更とは関係がない）。

## 失敗の合計

`pytest_full.txt` の最終行と、基線との差（基線にない 2 件、基線にあって通った 1 件）は `artifacts/w3-c/pytest_failures.txt` と `pytest_new_failures.txt` から `comm` で出した。
