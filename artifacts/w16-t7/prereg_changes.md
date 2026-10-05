# 凍結後の試験の変更（2 件。どちらも試験側の誤りで、期待は弱めていない）
凍結: artifacts/w16-t7/prereg_sha256.txt（2026-10-05 23:04）。変更後の sha は prereg_sha256_after.txt。

1. tests/test_w16t7_hooks.py::test_hook_unwritable_ledger_still_exits_zero
   - 前: `run_hook(t, "UserPromptSubmit", {"prompt": "x"}, blocker)`（cwd も blocker＝ファイル）→ subprocess が NotADirectoryError（試験の準備の誤り。hook を実行できていない）。
   - 後: `run_hook(..., blocker, cwd=tmp_path)`（CLAUDE_PROJECT_DIR だけをファイルにし、cwd は有効なディレクトリ）。期待（終了コード 0・標準出力が空）は同じ。
2. tests/test_w16t7_run.py::ours()
   - 前: lstart を確かめられない（もう居ない）pid の組 (pid, None) を集合に残し、all_gone が `None != None` で永遠に偽。
   - 後: pid か lstart が空の組を除く。期待（孤児が止まった後に sweep が process_exit を足す）は同じ。
3. docs/RECORDER.md: 先頭の事前登録の後に §9 実測・§10 既知の穴を追記（§1〜§8 は変更なし）。

## 第 2 ラウンド（レビュー r1 対応。既存テストの本文・期待は変更なし。追加のみ）
- tests/test_w16t7_redact.py: 末尾に 4 件追加（改行つき token 語の逐語保存、パスワード＋タブの伏せ、数値の秘密名キーの受理、安全網が秘密を拒否し続けること）。
- tests/test_w16t7_run.py: 末尾に追加（塞がれた台帳 2 種で子を起動しない、秘密の形のラベルで落ちない、起動後の追記失敗が型つき）。
- tests/test_w16t7_hooks.py: 末尾に 3 件追加（.claude へのシンボリックリンク、settings.json へのシンボリックリンク、実体の無い場合）。
- docs/RECORDER.md: §2 に status の閉じた一覧と優先順を追記、§11 を追加。それ以外は変更なし。
- 変更後の sha: prereg_sha256_after.r2.txt。変更前の本文は git に無いので、追加分だけを上に列挙した。

## 第 3 ラウンド（レビュー r2 必須 1 対応。既存テストの本文・期待は変更なし。追加のみ）
- tests/test_w16t7_redact.py: 末尾に 3 件追加（隣り合う鍵の redact 冪等性と残留なし、隣り合う鍵を含む発話が台帳に残ること、run --keep-args の子孫の隣り合う鍵が台帳の全ファイルに完成形で残らないこと）。
- docs/RECORDER.md: §12 を追加。それ以外は変更なし。
- 変更後の sha: prereg_sha256_after.r3.txt。

## 第 4 ラウンド（監査役の裁定: 秘匿の左境界を外す。既存の試験・docs §1〜§12 は変更なし。追加のみ）
- tests/test_w16t7_redact.py の末尾に 14 件（pytest の件数）: test_r4_redact_after_alnum_escape_urlenc_japanese（7 例）・test_r4_fuzz_single_all_combinations・test_r4_fuzz_pairs_all_combinations・test_r4_nonsecret_text_unchanged・test_r4_specific_name_wins_on_overlap・test_r4_ledger_run_keep_args_after_escape・test_r4_ledger_hook_posttooluse_after_escape・test_r4_ledger_owner_utterance_japanese_bearer_verbatim_rest。
- docs/RECORDER.md: §13 を追加。それ以外は変更なし。
- 変更後の sha: prereg_sha256_after.r4.txt。
- 第 4 ラウンド・レビュー r1 必須 1 対応: tests/test_w16t7_redact.py の末尾に 1 件追加（test_r4_password_password_value_redacted。pytest の件数で第 4 ラウンドは計 15 件）。docs/RECORDER.md §13 の「残る限界」から password: password: の項目を削除し、§13 に 5（解消の記述と実測）を追加。§12 以前は変更なし。変更後の sha: prereg_sha256_after.r4b.txt。
