# 判断記録
1. `vera run` の台帳（process_exit に argv/cmd が無い）を `run_id` で process_start と結ばない: 新しい RECORD を作る＝広げる方向なので。現行でも NO_EVENT、変更後も NO_EVENT（k606_cmp.txt）。
2. `EMPTY` は OK ではないので未検証（LEDGER_UNVERIFIED、evidence.status=EMPTY）。
3. `--ledger` の名前が events.jsonl（またはディレクトリ）以外は検証に掛けられないので未検証（LEDGER_PATH_NOT_T7）。別ファイルを検証して渡されたファイルを読む取り違えを作らない。
4. 検証前後で bytes を比べ、出来事は検証した bytes から作る（TOCTOU 対策）。
5. `ledger_head` は API のみ。CLI の旗は cli.py（許可パス外）なので proposed_cli_ledger_head.diff に置くだけ。None のとき flags にキーを足さない（K606）。
6. 既存の T6 テスト 11 件・合成 8（実測は 7）件は編集しない（許可パス外・凍結）。一覧と移行案は existing_test_impact.md。
7. 赤を書いたあとテストを 1 か所だけ直した: a16v の期待を「BAD_SHAPE」一律から変種別（prev_empty は PREV_MISMATCH、他は BAD_SHAPE）に。最初の期待が T7 の verify の実際の分類を読み違えていた。厳密化であり弱体化ではない（test_amend_note.txt、sha は tests_freeze.sha256 と tests_freeze_final.sha256）。
8. 例外は verifier の外へ漏らさない（OSError/UnicodeError は LEDGER_UNREADABLE、それ以外の例外は LEDGER_VERIFY_FAILED として未検証）。
9. 語の一覧・特定の値の特別扱いは無い。a16 の変種も同じ規則（verify が OK でない）で止まる。

## 第 2 ラウンド（2026-10-06）
- 訂正の印: 上の判断 5（CLI は提案だけ）→ 裁定 3 により第 2 ラウンドで `proposed_cli_ledger_head.diff` を適用した（cli.py は `+` 1 行・`-` 0 行）。判断 6（既存テストを編集しない）→ 裁定 1 により `proposed_t6_test_migration.diff` を適用した（fixture のみ、assert を含む変更行 0）。
10. **synth_lib.py を diff の一部として適用した**（裁定 1 の文言には名前が無い。diff は `artifacts/w16-t6/synth/synth_lib.py` を含み、裁定はその diff を名指しで承認している。これを移さないと test_w16t6_synth の `detected == false_facts` が 20≠22 で落ち続けるため）。凍結物 cases.jsonl・expected.jsonl は不変（sha 一致）、freeze.sha256 の対象外のファイル。
11. attest.py と tests/test_w16t6b_ledger_verify.py は第 1 ラウンドのまま（編集していない。sha 37efee81…）。
12. CLI の試験は新しいファイル tests/test_w16t6b_cli_head.py に書き、旗の追加前に凍結して赤（3 failed・2 passed）を取った。分岐の回帰試験 tests/test_w16t6b_branches.py（3 件）は最初から緑で、赤は取れなかった。
13. 移行後の合成 40 件は凍結物と byte 同一になった（台帳が T7 の形で検証を通るため）。指示書の見込み（7 件が下がる）は仮定の形の台帳でのもので、7b にその全件と移行後の事実の両方を書いた。
14. 再生 173 本は 2 行だけ byte 差（evidence の verantyx/cli.py の sha256 のみ）。cli.py を承認どおり変更した結果の自己参照で、印・理由は不変。実装を戻して同一にはしない。
