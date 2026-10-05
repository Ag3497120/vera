# 提案（適用していない）: `vera ask --document` の既定を round5 にする（指示書 D1）

理由: 既存テスト 2 本（ask）が「`--mode` なしの `--document` は `UNKNOWN_ROUTE_CONFIGURATION`（`--document requires --mode round5`）」を固定している。AGENTS.md は既存の試験の期待の変更を監査役の許可の範囲に限っているので、この回では適用せず、差分を `proposed_default_round5.diff` に置いた（製品 `verantyx/cli.py` とテスト 2 本。`cli.py` の差分は現在の作業ツリーに対するもの）。
chat の 3 本目（`tests/test_one_chat_round5.py:62-71`）は `chat --document`（既定 lab）の拒否で、ticket は ask の既定だけを言うので変えない。

確かめ（実装役が一時的に当てて流し、元に戻した。作業ツリーは `git status` で提案前と同じ）:
`pytest tests/test_basis_policy_entry.py tests/test_one_request_goal_route.py tests/test_one_chat_round5.py tests/test_ask_question_cross.py` → 1167 passed（差分を当てた状態）。

## 前後の全文（テストの該当行。名前は変えない）
1. `tests/test_basis_policy_entry.py::test_an_existing_configuration_error_keeps_its_place_before_the_new_ones`
   - 前: `_ask(tmp_path, capsys, "こんにちは", "--document", "x.txt", "--confirm", "abc", "maybe")`
   - 後: `_ask(tmp_path, capsys, "こんにちは", "--mode", "legacy", "--document", "x.txt", "--confirm", "abc", "maybe")`
   - 期待（rc 2・`UNKNOWN_ROUTE_CONFIGURATION`・`--document requires --mode round5`）は同じ。明示の legacy と文書の組合せの拒否になる。
2. `tests/test_one_request_goal_route.py::test_cli_rejects_source_documents_when_default_legacy_mode_was_selected`
   - 前: `"ask", RAW, "--document", str(source),`
   - 後: `"ask", RAW, "--mode", "legacy", "--document", str(source),`
   - 期待は同じ。
製品: `--mode` の既定を `None` にし、`mode = args.mode or ("round5" if documents else "legacy")`。明示の `--mode legacy` と `--document` は従来どおり拒否。
