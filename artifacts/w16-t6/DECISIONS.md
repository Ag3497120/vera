# W16-t6 判断の記録（指示書に無い判断・手順からの逸脱）

1. **事前登録の日時表記の誤り**: docs/ATTEST.md の冒頭に「事前登録: 2026-10-05 23:08 JST」と書いたが、書いた実時刻は 23:05:10（`prereg.sha256` の date 行と ATTEST.md の mtime）。合成データの凍結（cases.jsonl・expected.jsonl・freeze.sha256 の mtime と `prereg.sha256` 末尾の date 行）は 23:06:47、`verantyx/attest.py` の最初の書き込みはそれより後。
   事前登録の文書は書き換えず（sha256 を `prereg.sha256` に固定済み）、ここに訂正を残す。順序（事前登録 → 合成データの凍結 → 実装の最初の測定）自体は守った。
   なお、事前登録の sha256 を取った後に「shadow_marks.py を読んだ」という趣旨の誤記を直した（読んでいないので）。その版が `prereg.sha256` の値。
2. **`ROW_TYPES` を変えない**（指示書 §2.7 どおり）: 定数 `ATTESTATION_ROW_TYPES = ("attestation",)`・`ATTESTATION_MARKS`・`ATTESTATION_EXTRACTORS` と `record_attestation` を足しただけ。
   既存テスト `ROW_TYPES[-1] == 'assumption'` を落とさないため。
3. **`NOT_IN_TESTS_DIR`（TESTIMONY）を理由の型に足した**（事前登録の一覧に無い）: tests_added の申告が `tests/` の外のパスを指すとき。後述の「改訂」に書いた。`AMBIGUOUS_CLAIM` も同様（b2 の改訂）。
4. **変更ファイルの「変更された」は `--base` があるときだけ照合**（指示書どおり）。無いと `NO_BASE`（TESTIMONY）。合成データの正しい `変更` 申告はすべて git の基点つきで流す（S07・S08・S13・S16・S17・S34・S36）。基点無しの挙動は単体テストで確かめた。
5. **抽出器の既定は `structured`（V と a）**。b は明示したときだけ（再生では b が主役）。終了コードは選んだ抽出器すべての申告の最悪値。
6. **`changed` は 1 ファイル = 1 申告**（V の 1 行に 2 ファイルあれば 2 申告）。指示書の「申告ごとに印」を、検出の粒度を細かくする方向に取った。
7. **`file_sha` と `output_sha` を同じ事実の種類 `file_sha:<path>` にした**: 抽出器 b は受入の出力と変更ファイルを区別できないため、事実単位（sig）で比べられるようにするため。
8. **ledger 台帳の「通った」の照合**: tests_added の「通った」は、argv に pytest の呼び出しとそのパスを含む出来事の終了コードが 0 かで見る（`::node` 付きのパスは node を除いて比べる）。
9. **`--rerun` の収集（テストの件数）**: 件数の確認は `--collect-only` で常に行う（`--rerun` を要さない。コードの import を伴うので許可形と同じ規則をパスに掛ける）。ATTEST.md に明記済み。
10. **LLM 判定器 (c) のプロンプトを 1 回直した**（事前登録の §6 の「照合器が見るのと同じ生の観測」は変えず、問いの書き方だけ）: 最初の版（v1）は「確かめたい点」に内部の事実の署名（`test_exists:tests/a.py` など）と「申告の値: exists」を渡した。
   測ると誤検出が 31（正しい事実 53 件のうち。`compare/v1_signature_prompt/`）あり、署名が読めないせいと見て、平易な日本語の説明（`fact_phrase`）に直した（v2）。**直したのは c に有利な方向**で、c を弱く見せないため。v2 の誤検出は 17。
   v1 の生データと表は `compare/v1_signature_prompt/` に残してある。主の表は v2。v1 の結果を見てから直したので、「事前登録のとおり」ではない。
11. **b2（再生の食い違いの大半を占めた規則）を 1 回狭めた**: 1 行にテストのパスが 2 つ以上、または「N passed」が 2 つ以上あるとき、組を決めずに `AMBIGUOUS_CLAIM`（TESTIMONY）にした（「同点は棄権」）。
   最初の版の再生では食い違い 148 件（うち `COUNT_DIFFERS` 136 件）、直した後は 79 件（`COUNT_DIFFERS` 67）。直す前の要約・食い違い表は `replay/summary_before_b2_amendment.txt`・`replay/mismatches_before_b2_amendment.tsv`。
    **再生の結果を見てから規則を直した**ので事前登録ではない。合成 40 件の b の結果は変わらない（合成の行は 1 つのパスと 1 つの件数）。ラベルは無いので、直して誤検出が減ったとは言えない（減ったと言えるのは件数だけ）。
12. 合成データ `expected.jsonl`・`cases.jsonl` は凍結後に書き換えていない（`shasum -a 256 -c synth/freeze.sha256` が OK）。
13. fixture のファイルは JSON の中の文字列で持ち、テスト時に tmp に実体化する（`artifacts/` に `test_*.py` を置かない）。fixture の pytest は fixture ツリーの直下の空の `pytest.ini` で、`$W` の設定・conftest に登らない。
14. 他の `wt/*` は開いていない。`W8-shadow-2-S/tools/ops/shadow_marks.py` も読んでいない（参考に「してよい」だけで、規則は独自に事前登録した）。
15. `synth/freeze.sha256` のパス欄を、作業ツリー直下から `shasum -a 256 -c artifacts/w16-t6/synth/freeze.sha256` で検査できるように `cases.jsonl` → `artifacts/w16-t6/synth/cases.jsonl` に書き換えた（sha256 の値は凍結時のまま。cases.jsonl・expected.jsonl は書き換えていない）。
16. 第 2 ラウンド（レビュー r1 の必須 3 件）: 台帳の出来事を「通った」の根拠にする条件を絞り（収集だけ・選別・未知の旗・複数ファイルの失敗は根拠にしない。ATTEST.md 改訂 5）、0 件の収集は観測値 0 として COUNT_DIFFERS/MATCH にし、COUNT_DIFFERS・EXIT_CODE_DIFFERS に根拠を付けた。再測定で合成・再生の印と理由は不変。任意の改善のうち 1（連鎖切れの断定）・2（PYTEST_* を子の環境から落とす）を実施。3（--rev の意味）・4・5 は未実施。
17. 第 3 ラウンド（レビュー r2 の必須 1）: 終了 5 の収集は `-q` 無しの `pytest --collect-only <spec>` で再収集し、`collected 0 items` 単独のときだけ観測値 0。skip が付けば `COLLECT_SKIPPED`（TESTIMONY、`TESTIMONY_REASONS` に追加）。ATTEST.md 改訂 6。テスト 3 件を `tests/test_w16t6_basis.py` に追加。再測定で合成・再生は不変。任意の改善 1（0 件申告の `test_passed`）は未対応。
