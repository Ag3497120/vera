# W5-f 実装報告 r1

指定報告先 `/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W5-f/impl.r1.md` は、この実行環境の書込許可範囲外だった。報告本文はこの作業ツリー内の `artifacts/w5-f/impl.r1.md` に保存した。

## 実装

- `verantyx/semantic_reader.py` に F-1 の引用断片棄権、F-2 の `名詞/普通名詞/副詞可能` 門、F-3 の繋辞値・「とも」の並立検査を追加した。K186、`_coordination_marks`、`document_view`、型表、W3-b5 行、CLI の別名を変えていない。
- `verantyx/basis_policy.py` を分類規則 v5 にし、ソブリン出典を人と分類する条件に非空 `store_id` と小文字 16 進 24 字の `confirm_id` を加えた。
- `docs/READING_SOUNDNESS.md`・`docs/BASIS_POLICY.md`・`docs/OBSERVATION.md` に事前登録、既知の穴、S5 の変更前後全文、実測結果を記録した。
- 既存テストの改訂は指示書 D4 の 16 関数だけ。新規テスト、補助データ、攻撃写しと各実測出力は `tests/`・`artifacts/w5-f/` に置いた。`tests/test_basis_policy_*` の既存変更は指定された 6 ファイルだけ（`artifacts/w5-f/scope_check.txt`）。
- commit / push はしていない。

## 受入基準

| 基準 | 実行と結果 | 出力 |
|---|---|---|
| I1 攻撃写し | 5 組の写しを各報告元と照合し全て `SAME`。`pytest ... tests/attack/test_attack_w3b4.py tests/attack/test_attack_w3c4.py tests/attack/test_attack_w5e_*.py` は **6 failed, 32 passed**。W3-b4 の 5 テスト（K-F2・K-HE・K-W3B4-GATE・K-P）と W3-c4 の 1 テスト（K-C4）が失敗。W5-e 攻撃は通過。I1 未達。 | `i1_attack_copies.txt`, `i1_attack.txt` |
| I2 読解 | 凍結 K265 の 94 文は fake / none / r8 の全モードで誤読 0。既存凍結 500 文は変更 0・誤読 0。4,149 入力では none の readable 286→286、r8 は 458→458。各 9 件の変更すべてで `unsupported[].reasons` に `COORDINATION_UNDETERMINED` が加わり、最終 abstain reason は `NO_SUPPORTED_CLAUSE`。W3-b4 339 行と W3-b5 649 行は誤読・期待不一致 0。**ただし K-F2 の右・W3-b5 反例はこの門で止まらず、未公開 holdout は開いていないため I2 全体は未達。** | `i2_gates_{fake,none,r8}.txt`, `i2_soundness_compare.txt`, `i2_entry_*_compare.txt`, `i2_entry_reason_changes.txt`, `i2_w3b4_rows.txt`, `i2_w3b5_rows.txt`, `k_f2_right.txt`, `proposals/k_f2.md` |
| I3 根拠方針 | `b_check.py` の 31 件で `fails: []`。W5-f 形状検査を含む根拠ポリシー 6 モジュールの組合せは 1,612 passed。指定 I3 コマンドは 59 passed・1 skipped。skip は r7 に該当枠がない既存テストが自ら宣言したもの。版は `5 1 2`（CLASSIFY / TABLE / CONFIRM_ID）。 | `i3_b_check_r2.txt`, `basis_policy_related_acceptance.txt`, `i3_tests.txt`, `i3_versions.txt` |
| I4 後段 | 主検査 111 問と extra2 42 問の verdict・text・`sources[].{source,line,text}` は変更 0、`wrong=[]`・error 0。質問十字テスト群は 73 passed。W3-c4 の元 Markdown 部分文字列テストは定義の差で残るため I4 は追加テストの範囲で確認し、攻撃写しの期待は満たしていない。 | `i4_score_compare.txt`, `i4_changed.tsv`, `i4_tests.txt`, `i1_attack.txt` |
| I5 監査役測定 | B1 / B6 / B7 は実装役の測定対象外として未実施。 | 該当なし |
| I6 全体 | 最後の全体テストは **191 failed, 15,129 passed, 46 skipped, 75 xfailed, 75 xpassed, 37 subtests passed**。基線 115 件に対し増加 76、減少 0。事前宣言 7 件は全て発生したが、**宣言外の新規失敗が 69 件**（`test_conduct_*` 68 件、`test_gen_coarse_evidence.py` 1 件）。失敗原因は `--tb=no` 出力から確定できず、I6 未達。 | `pytest_full.txt`, `after_failures.txt`, `new_failures.txt`, `new_undeclared.txt`, `reduced_failures.txt`, `new_undeclared_by_module.txt` |

F-1〜F-3 の関連固定テストと W5-f ゲートテストは 2,746 passed（`reader_related_acceptance.txt`）。F-5 の補助質問テストは上表 I4 の 73 passed。S5 の個別モジュールもすべて通過: entry 1,086、form 29、table 35、W5-c 295、W5-c r3 138、W5-e 25 passed（`entry_revision_tests.txt` 等）。変更前の凍結失敗記録は 21 failed・33 passed（`pytest_before_fix_final.txt`）。

## S5 改訂・レビュー

第 1 ラウンドのため、前回レビュー指摘はない。D4 の変更対象を各群ごとに「変更前の全文を docs へ記録→編集→変更後の全文を記録→対象を実行」した。名前は維持し、自己申告出典の識別子を形状要件へ更新し、H4-C2 だけを退役対照にした。全文は `docs/BASIS_POLICY.md` の `W5-f S5` 記録、個別結果は `entry_revision_tests.txt`・`form_revision_tests.txt`・`table_revision_tests.txt`・`w5c_revision_tests.txt`・`w5c_r3_revision_tests.txt`・`w5e_revision_tests.txt` にある。

## 判断・逸脱・既知の穴

- K-F2: `右` は実測品詞が `名詞/普通名詞/一般` で、F-2 の品詞規則だけでは棄権しない。語の一覧は作らず、W3-b4 D10 と I2 の「右」条件は未達として申し送る。scratch clone で `P_ACT source/から` 行を外すと D10 は棄権したが、D06 は引き続き読解、4,149 件の readable は 458 のまま。W3-b5 登録行は base / 実装後とも誤読 171/649（差分 0）。
- K-HE: W3-b4 D01/D03 には指示書内の規則がない。scratch clone で `P_ACT goal/へ` 行を外すと該当型の読解は 4→0 となるため、製品表は維持した。
- K-W3B4-GATE / K-P: 攻撃写しは K186 本体だけを呼ぶ。また残る P02/P03/P10/P11 は型段の外。宣言どおり写し・登録期待を変えていない。
- K-C4: W3-c4 写しは元 Markdown の部分文字列を要求し、W5-f の「読込後本文」定義と相容れない。`cli.py` は無変更。新しい Markdown 入力の `sources[].text`・line は読込後本文に一致する。
- 未公開 holdout と評価バンクは指示に従って開いていない。I5 も指示に従い未測定。自己申告可能な正しい形式の ID と実在台帳との照合、形態素分割により係助詞が存在しない 15 文、型段に届かない読解経路は既知の穴として残る。
- 開始時のツリーには指示書の「clean」と異なる未コミット事前作業があり、破棄せず引き継いだ。K267 の凍結参照名の不一致は `docs/READING_SOUNDNESS.md` の K267-1 で訂正した。scratch の再利用による `b_check.py` 初回 assertion 失敗と攻撃比較の誤った元パスは別ログに記録し、正しい新規 scratch / パスで再測定した。
- 全体テストが追跡下の `tests/attack/w3a3/r6_48_queries.jsonl` を変更した。`git checkout --` は `.git/index.lock` 作成権限で失敗したため、HEAD の同ファイルを `git show` から scratch に出し、対象へ戻して `cmp` と HEAD 差分検査で一致を確認した（`restored_generated_check.txt`）。

最終状態は `artifacts/w5-f/status_after.txt` に保存する。
