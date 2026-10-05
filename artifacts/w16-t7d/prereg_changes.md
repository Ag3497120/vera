# 事前登録（凍結したテスト）の変更記録

## 変更 1: test_a6_unknown_tags_stay_owner の入力の 1 件、test_a6b の追加（実装の後、2026-10-06）
- 前: `'<task-notification attr="1">x</task-notification>'` を owner_utterance と期待（指示書 A6 の例）。
- 後: `'<task-notification attr="1">x'`（閉じ無し）を owner_utterance と期待。元の入力は新テスト `test_a6b` で `user_turn_unattributed`（reason UNOPENED_CLOSE_TAG）と期待。
- 理由: 指示書の規則 4（塊の外に既知の閉じタグが 1 つでもあれば MALFORMED）・J6（閉じタグだけは作者を断定しない）と、A6 の例（属性つきの開き + 完全一致の閉じ → owner）が矛盾した。実装は規則 4/J6 に従った（安全側。作者を owner と断定しない）。失敗の実出力は実装後の初回の pytest（34 passed / 1 failed）。
- 期待値の弱体化ではなく、規則との矛盾の解消。中間職の判断を仰ぐ点として報告に書く。

## 変更 2（第 2 ラウンド、2026-10-06）: skip の抜け道を塞ぐ（レビュー必須 4）
- 前: `tests/test_w16t7d_attribution.py` の `test_a10_other_events_unchanged_vs_baseline` と `tests/test_w16t7d_correction.py` の fixture `base_root` が、`git archive d1942e2` の失敗時に `pytest.skip("git archive d1942e2 unavailable")`。
- 後: どちらも `pytest.fail("git archive d1942e2 failed: " + stderr)`。期待値（比較の中身）は変えていない。理由: 証拠のテストを条件つき skip で「成功扱い」にしない。

## 変更 3（第 2 ラウンド）: 新しいテストファイル `tests/test_w16t7d_review1.py` の追加（凍結は 3 本に更新）
- 追加のみ（既存テストの期待は変えていない）。A11（T7 の kind は新しい actor type を events add で拒否し、基点と出力が byte 一致）、A11b（kind と actor type の組が不正な行は verify が BAD_SHAPE。T7 の語彙だけの台帳は基点と verify の出力が一致）、A11c（新しい kind の正しい組は verify OK）、A12・A12b（秘密の形が塊の境界をまたぐ混在は、分けずに全体を伏せた 1 行 user_turn_unattributed）、A13（split_system_blocks が線形）。
- 実装前（第 1 ラウンドの実装を再現した変種）の赤は `red_before_r2.log`（16 失敗・2 成功）。再現の方法は impl.r2.md に記す。
