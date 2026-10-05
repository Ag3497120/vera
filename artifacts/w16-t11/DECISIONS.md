# W16-t11 判断記録（実装役、第 1 ラウンド）

1. **数値の仕様の凍結**: `numbers.json`（43 行）と `claim_words.json`（言い切りの語の一覧）を、README・KNOWN_ISSUES・EVAL・CHANGELOG を書く前に凍結（sha256 と時刻: `numbers.sha256`・`numbers_time.txt`・`claim_words.sha256`）。後で旧い README・EVAL の言い切りの文（「0 wrong」「100%」）を `docs/README_LEGACY_d25a73a.md` と `EVAL.md` の履歴に移したところ、その文を R-2 に通すために **履歴の行 N-51〜N-56 が要る** と分かったので、`numbers.r1.json`（最初の 43 行は `numbers.json` と同一。`numbers.r1.sha256`・`numbers.r1_time.txt`）を足した。前の版は消していない。r1 の凍結（03:43:01）は、`docs/README_LEGACY_d25a73a.md` を作った（03:42:44）後だが、KNOWN_ISSUES・EVAL・README・CHANGELOG を書く前（`mtime_order.txt`）。言い切りの語の一覧は r1 で変えていない。
2. **T3 の出所の選択**（指示書の「どちらか 1 つ」）: W14 の C 系の数は `artifacts/w16-t3/r3/t32_result.txt`（第 3 ラウンドの保存結果。新旧の物差し・要素 0 個の anchored・quote_check のある行が 1 つのファイルでそろう）を主にした。`r5/t32_recheck.txt` は「保存結果を最終の照合器で再評価すると anchored が 140」という 1 行だけを別の行（N-39）にした。`artifacts/w16-t3/t32_result.txt`（T3 第 1 ラウンドの結果。anchored 145）は版が違うので使わない。理由: r3 の保存結果と r5 の再評価は同じ保存ファイルを指す（再評価の 1 行目）ので混ぜずに 2 行に分けられ、第 1 ラウンドの 145 とは版が違うから。144 と 140 を同じ行に混ぜていない。
3. **旧の物差しと新の物差し**: 「Vera が確かめた出典」の旧（0/256 行、N-34）と新（153/256 行、N-36）は 2 行に分け、README に「定義が違う。比べない」と書いた。「0 → 153 に増えた」とは書いていない。
4. **分母の無い行**: N-19（全体テストの既知の失敗 115）は、総数が出所（`docs/AUDIT_2026-10-06.md`）に無いので分母を `n/a` とし、集合の欄にその旨を書いた。総数を別の基点の出力（`artifacts/w5-*/before_pytest.txt` の passed 数）から借りなかった（基点が違う）。N-05〜N-08（T2）は出所が「答えあり 20・答えなし 20」の内訳ごとの分母を書いていないので、全体の 40 を分母にした（ask の正しい棄権 19 を答えなし 20 で割る、などは出所に無いので書かない）。
5. **N-54（実際の質問での誤答 0）は空虚**: 答えた件数が 0（N-55）なので、誤答 0 は当然。履歴の行として分母 72 と併記し、EVAL の履歴に「答えた件数が 0 なので 0 は当然」と書き足した（元の文面は変えていない）。
6. **README の構成**: YAML は変えていない。英語の本文の後に `## 日本語` の節（`README.ja.md` は作らない）。古い節は README から外し、**README の本文全体を** `public_overlay/docs/README_LEGACY_d25a73a.md`（新しい docs の節）に文面を変えずに移した（変えたのは GitHub の URL の語への置き換えと、言い切りの文への `[N-xx]` の印の追加だけ。どちらも冒頭に書いた）。旧の EVAL.md は `public_overlay/EVAL.md` の「History」にそのまま移し、印を足したのは 3 文（N-51〜N-56）。分母を想像で補った文は無い（旧の文面にある 80・103・72・30 の分母だけを使った）。
7. **検査器の除外の語彙を足した**（README を書いた後。凍結した言い切りの語は触っていない）: 数値の字句の除外の型に (i) 英字＋数字の識別子（`run1`・`v1`・`sha256`・`r9`・`T3` など。指示書の「ID」の一般化）と (ii) 層の名前（`layer 0`・`層 0`）を足した。指示書の閉じた除外の一覧（日付・時刻・版・16 進・ID・パス・節番号）を、層の名前の分だけ広げたことになる。理由: 「layer 0」は serve の層の名前で、数値ではない。仕様の値と衝突する例（`N-01` 以外の数字が識別子の中にだけある場合）は 1 件も無いことを確かめた（README の照合は 0 件）。
8. **正規化は 2 規則だけ**（`normalize.py`）: (a) attest の `tree=<出力先の絶対パス>/` → `tree=./`、(b) `events verify` の `"head"` の 64 桁 → `<sha256>`。README の本文の中の言い方で表示名（`vera ...`）を実際のコマンド（`python -m verantyx.cli ...`）に対応づけた。
9. **hook の例**: 全文（1827 バイト）は長いので先頭の 18 行を貼り、「先頭が一致」の規則で検査（`tests/test_w16t11_readme.py::test_examples_hook_block_is_a_prefix_of_the_full_output`）。`hooks print` の最初の `_vera` の行は標準エラーに出る（`b_hooks.stderr`）。
10. **attest の例で `変更` の申告は `NO_BASE`（証言）になる**: `--base` を渡していないため。そのまま見せ（隠さず）、README で理由を書いた。「記録・証言・食い違い」が 1 つ以上ずつ出る例として使える（記録: `tests/test_calc.py`、証言: `NO_BASE`・`COMMAND_NOT_ALLOWED`、食い違い: `COUNT_DIFFERS`）。sha の申告は固定値で、`replay.sh` の中で一致を確かめる（`calc.py` の sha が違えば終了 3）。
11. **serve の例は枠**: `AUDITOR_RUNS: serve-layer0` の印は英語の節に 1 つだけ（日本語の節は「英語の節の枠に貼り、ここにも写す」と書いた）。出力は想像で書いていない。`replay_serve.sh` を書いたが **流していない**（Ollama とソケットが要る）。要求の形は `benchmarks/public_v1/run.py` の `run_vera_row` と `docs/FUSION.md` K652 に合わせた。**`replay_serve.sh` は未実行のため、動くことは確かめていない**。
12. **煙試験**: 1 回目はバックグラウンドで流し、serve の段が終了 1（`serve process did not stop after SIGINT`、HTTP 200、プロセスの終了コード -9）。失敗を成功と書き換えていない。前景で流し直した 2 回目は全段 0（serve は `--no-llm` の探針）。1 回目の原因は未確認（バックグラウンドのジョブが SIGINT を無視する疑い）。両方の記録を `smoke_run1_bg_failed/`・`smoke/` に残し、`release_assets.md`・KNOWN_ISSUES に書いた。`smoke/` の `.command` ファイル 6 本に scratchpad の絶対パスが残っている（`redact_smoke_output.py` の対象外。artifacts は公開の木ではないので失敗にはしない）。
13. **配布物が 2 つ**（`verantyx_vera 0.1.0a1` と `vera-ja 0.2.0a1`）: 決めていない。版も pyproject も変えていない。README の入れ方の節に「監査役・オーナーが決める」と書いた。
14. **見つからなかった既知の穴**: 無し。指示書の列挙（T1b の 2 件・T3 の要素の無い誤答・T7 の過剰な伏せと 2 乗・T6 の再生のラベル未付与・W14 の人の採点未了・T10・T8・全体テスト 115）はすべて出所つきで KNOWN_ISSUES にある。ただし T1b の「2 件」は `artifacts/w16-t1b/CHANGES.md` の差分の分類（(a) 読める→棄権で能力を失った 3 行、(b) 名前＋肩書き）から **実装役が 2 件にまとめた**（出所に「既知の穴 2 件」と書いた節は見つからなかった）。
15. **指示書からの逸脱**: (a) 検査器の単体テストを README を書く前に「赤を確かめた」わけではない（検査器とテストを同時に書き、突然変異の確認 `mutations.txt` で赤を確かめた）。(b) 煙試験の 1 回目の失敗（上の 12）。(c) `numbers.r1.json` の追加（上の 1）。(d) `public_overlay/docs/README_LEGACY_d25a73a.md` を足した（許可パスの「`public_overlay/docs/**` の新しい節」の範囲）。(e) 指示書は R-2 の対象を README・KNOWN_ISSUES・EVAL・CHANGELOG としたが、legacy 文書も同じ検査に加えた。

## 第 2 ラウンド（review.r1.md への対応）
- 必須 1: 版番号の除外を「v で始まる／3 部分以上／-preview・aN が付く」だけにした。`claim_words.r1.json`（`100(?:\.0+)?\s*%`。厳しくする方向のみ。旧版は残す）、`claim_words.r1.sha256`。
- 必須 2: `numbers.r2.json`（r1 は残す。52 行）。N-57（A の機械判定の正答 37/64）・N-58（A の止めた数 31/48）・N-59（C の止めた数 31/48）を追加。N-30 に C の LLM（qwen3.5:4b）、N-32 に「C とは別の大きいモデル」を明記。README の表の前の注（英日）と KNOWN_ISSUES §6 に 1 文足した。DEFAULT_SPEC・DEFAULT_WORDS を r2・r1 に。
- 必須 3: 英語の表の "only" を外した。必須 4: EVAL の注に Conductor 行の括弧書きの例外を明記（案 a）。必須 5: KNOWN_ISSUES §4 を `UNKNOWN_UNREAD`（`ABSTAINED`）に。
- 任意: 2（N-34 の「何をしたか」を「測定の結果」に）・4（CHANGELOG の wheel の行）だけ対応。1・3・5・6・7 は見送り。

## 第 3 ラウンド（実装役 Sonnet 5.5）
- R-5 の試験 `test_r5_product_code_is_unchanged` の基点を `ecde332` から `4c2a2e5` に変更（チケットの指示 5。名前・期待の形は同じ。変更前: `git diff --stat ecde332 -- verantyx/ ...` が空。変更後: `4c2a2e5`）。merge で入った dev の製品コードを数えないため。期待の弱体化ではない。
- `DEFAULT_PUBLIC_FILES` に README_LEGACY を足して 5 件。CHANGELOG の「Before publishing」の文を「this file (`CHANGELOG.md`)」と明記し、5 件が一致する試験を足した。
- numbers.r3.json: r2 の 52 行を不変のまま先頭に置き、N-60〜N-72 の 13 行を足した（commit `d1942e2`）。N-70 の aux に `"25"` を足した（本文に「25 件を検出」と書くため）。合計（試した・破れた・直した）は仕様にも README にも入れていない。`vera run` と serve の件数は README に数字で書いていないので行を足していない。
- N-65 の正規表現は、台帳群の行の `**3 つを直した**` を同じ行の中で拾う（値 3、分母＝破れた数 4）。1 回一致を `--spec-only` で確認。
- KNOWN_ISSUES: 直った穴で「開いている」と書かれていた行は無かったので、退役の追記は無し（攻撃で見つかった型を追記し、直した型は括弧で併記）。EVAL.md は触っていない。dev の README.md も触っていない。
- 「25/30」は本文では「30 件のうち 25 件」と書き、[N-70] を付けた。
- release_assets.md に wheel が古い旨を追記（作り直していない）。
- serve 層 0 の枠は触っていない。

## 第 3 ラウンドのレビュー対応（実装役 Sonnet 5.5）
- 必須 1: KNOWN_ISSUES の 3 行（「閉じていない穴」に「直した」の注が混ざる旨を明記）・5 行（直した型は以前の一覧に無く、退役させた行は無いと事実どおりに）・日本語の要約（併記と書き、退役の文言を除去）を直した。任意 1（「その通り」§9.8 を日本語の要約に追加）・任意 2（3 行の括弧を 1 つに）も対応。任意 3・4 は見送り。数値・[N-xx] は不変。
