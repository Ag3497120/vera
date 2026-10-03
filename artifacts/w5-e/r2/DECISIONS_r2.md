# W5-e 第 2 ラウンド（W5-e2）: 指示書に無い判断と逸脱

作業ツリー: `/Users/motonisihikoudai/Projects/vera-impl/wt/W5-e-S`（基点 `ca66d3e` のまま。fetch・merge・checkout はしていない）。出力はすべて `artifacts/w5-e/r2/`（第 1 ラウンドの `artifacts/w5-e/*` は上書きしていない）。

## 逸脱（指示書と違うことをした）
1. **T1（`test_routing_from_text_entry.py::test_T1_…`）の `by_status` の 2 つの数を改めた**。指示書は index 6 の期待だけを改訂と書いたが、`by_status` は同じ 1 文の状態の集計なので、index 6 が `NAME_UNRESOLVED` から `UNREAD` になると `NAME_UNRESOLVED` 6→5・`UNREAD` 2→3 に動く（index 6 だけ直した直後の失敗出力で確認してから改めた）。同じ関数の中・同じ文の移動の帰結だけ。ほかの要素は不変。docs（`READING_SOUNDNESS.md` 10E.2）に書いてある。
2. **基線の失敗一覧の形式**: `dev_ca66d3e_failures.txt` は各行が `FAILED <id>` で始まるので、指示書の `sort $BL > bl_sorted.txt`・`comm` は形式が合わず全部が「基線に無い失敗」に見える。`sed 's/^FAILED //; s/ - .*//' $BL | sort` で作り直して比べた（`bl_sorted.txt`）。
3. **docs の K-A1 の「改訂後」の全文**に最初は注釈 1 行が入っておらず（その後 1 行足した）、docs 側も同じ内容に直した。最終の docs と関数は一致している。

## 判断（指示書の範囲の中の選択）
- **D2-5 の再凍結**: 第 1 ラウンドの `tests/test_routing_from_text_w5e.py` は `r2/test_routing_from_text_w5e.r1.py` に退避（sha256 は `w5e_test_r1_sha256.txt`）して書き直した。最低限の案に加えて、推定で型が述語型（`P_COMMUNICATE`）の引数と、`MULTIPLE` で `estimated` の引数、`MULTIPLE` で direct の全候補が非名詞型（`P_COMMUNICATE, P_MOVE`）で通る引数、`COMMON_NOUN_SUBJECT_UNTYPED` が決して出ない確かめ、1 つの推定の名前が文書全体を止める確かめを足した。r7 の `課`・`外注先` は「振られる」（訂正後の規則どおり）と注釈に書いた。
- **R1 のテストの `_direct` 経由の確かめ**は、`cp.ct.decide_word` ではなく `ct.decide_word`（同じモジュールの属性。`cp.ct` は `coarse_types` モジュールそのもの）を monkeypatch で包み、本物の判定に `cover` を足す形にした。期待は先に r7 の `generated_frames` の行（`申し込める` の枠は `に|PLACE` を持ち へ を持たない唯一の CONFIRMED 語。h5 の第 1 ラウンドの出力で `frame_unconfirmed` が `{を, に}`）から書いた。r7 が無い場合のフォールバックは不要（既存の A-4 のテストも r7 が無ければ落ちる作り。skip は足していない）。
- **K-A4 の攻撃の写し（r6）**: 期待の投影は `frame` だけでなく `frame_unconfirmed` も製品と独立に導出して比べる形にした（指示書は「外れた型は `frame_unconfirmed` に」。`cp.frame_backing` は呼ばない。`ct.rd_analyze` の腕ごとの有意な型の和集合で作る）。流したあと `r6_48_queries.jsonl` が変わったので基点の内容に戻した（改訂後の出力は `r6_48_queries.after_ka4.jsonl` に写した）。`r6_audit_summary.json` は変わらなかった。
- **K-A3**: 5 箇所（9 件）の入力に `"family": "memory_sovereign"` を足し、版 4 件の `3` を `4` に。各所に注釈 1 行。W5-c r3 の古い注釈（「CLASSIFY_VERSION は 3」）は履歴として残し、その直下の注釈で 4 だと明記した。
- **K-B の構造テスト**: `import difflib, hashlib` は関数の中に置いた（ファイルの最上位を変えないため。§6 の差分のスクリプトで `toplevel_changed` はどのファイルも `False`）。sha256 は `ast.get_source_segment`（その場の `_functions` と同じ本文）。
- **K-W3B3**: 11 の id がすべて `rows` にあることに加え、命中 6 行の期待が `abstain`・対照 5 行が `read` であることも assert した（id が期待の取り違えで差し替わるのを防ぐ）。
- **R1（`frame_cover_unconfirmed`）**: `_direct` の CONFIRMED の分岐で `unconfirmed.update(covered)` のあと `ROLE_PARTICLES` の順に並べ直す（指示書どおり）。`gen_map.get(に)` は `or ()` で None を避ける。
- A-2 の docstring: W5-d の (b) の文（「推定・UNPLACED・UNKNOWN は何も言わない」）が訂正と食い違うので、W5-e2 の段落に「(b) の推定の記述を上書きする」と明記した（(b) の文は直していない＝W5-d の履歴）。

## 指示書の前提と実測の照合（合っていたこと・合わなかったこと）
- S0: 開始時の変更ファイルの sha256 は中間職の `r1_tree_snapshot.sha256` と一致（`start.sha256`）。読み込み先は 52 モジュールすべて `$W` 配下。第 1 ラウンドの `coarse_place.py` の sha256 は `0c6c0a7f…b4cc`（`coarse_place.r1.py`）。
- S1: A-2 の 8 ファイルは `1 failed, 220 passed, 1 skipped`（落ちたのは `test_T1_…` の 1 件＝指示書の予告どおり）。H3 は凍結 6 本 `misroutes: 0`・r7 の 60 文で振られる数 **4（全件 UNPLACED）**・配置なし 0。
- S2: r8 の重ねた複製の数・14 語・CONFIRMED で `frame == {}` の 12 → 14 語、r7 のバイト一致は、すべて中間職の試作（`plan_evidence/proto_r1_r8_delta.txt`）と一致。`cover["ignored"]` が空でない語は r8 で 0。
- 合わなかった前提は上の逸脱 1・2 だけ。止まって報告が必要な不一致（H3 の 4 件に UNPLACED・UNKNOWN 以外が混じる、など）は無かった。

## 既知の穴（隠さない）
1. **H3 の「8 → 0」は成り立たない**（訂正後の規則どおり 8 → 4。振られるのは r7 で UNPLACED の `課`・`部門`・`メンバー`・`外注先`）。これらの普通名詞を名前と区別するには、UNPLACED の語に別の証言が要る。今回の範囲外。
2. **R1 はこの基点では効かない**（`coarse_types.decide_word` が `cover` を書かない）。W3-a4（df4f001）の統合後に、r8 で `frame_unconfirmed["へ"] == ["PLACE"]` の 14 語を監査役が確かめる。確かめは重ねた複製（`$T` の scratchpad。`$W` には置いていない）。
3. **r8 の CONFIRMED で `frame == {}` の語は 12 → 14**（A-4 で `移す`・`通う` が増える）。`frame_status` は変えていないので `CONFIRMED` なのに `frame` が空の語が残る（R1 は `frame_unconfirmed` に出すだけ）。
4. **A-3 の既知の穴**: `family == "memory_sovereign"` の自己申告は `store_id`・`confirm_id` が無くても人になる（今回の範囲では変えない。条件にすると名指しの無い既存テスト `test_basis_policy_w5c_r3.py` の `HUMAN_CONFIRMED`〔`store_id` 無し〕などが落ちうる。監査役の判断に回す）。
5. K-A3 の入力に `family: memory_sovereign` を足した 9 件のテストは、「ソブリンの記録由来の人の出典」を手で作った入力で確かめている（本物のソブリンの記録の経路ではない。W6-a の D の格上げの本物の経路は `test_basis_policy_w5e.py` のソブリン由来のテストが見る）。
6. 中間職の未公開の文（`W5-e/holdout/`）は実装役は流していない（B は不変で、H6 の出力は第 1 ラウンドとバイト一致）。
7. 全体テストの環境由来の失敗（`test_s6_…`）は未コミットの間だけ落ちる。
