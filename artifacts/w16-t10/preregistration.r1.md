# W16-t10 受入期待（検査データ・実装前に凍結）

登録日時: 2026-10-05 23:05 Asia/Tokyo。ここに書くのはチケットの受入契約で、測定結果ではない。先の初稿は `preregistration.r0.md` とその SHA-256 に保存し、今回の訂正後の本書を有効な期待とする。訂正理由は作業報告にも記録する。

1. この作業ツリーから wheel を作り、新しい仮想環境へ入れ、ツリー外の空ディレクトリからコマンドを実行する。
2. `vera --help`: 終了コード 0、標準出力に `usage: vera` を含む。
3. 既存 CLI の構文に合わせて `vera read --text 'ハルはミナに本を渡した。'` を実行する。終了コード 0。標準出力は JSON object で、`schema=verantyx.semantic_read/1`、`lang=ja`、`readable` は bool、`clauses` は list。チケットの位置引数風表記は現行 parser に無いため、`--text` を使う。
4. `vera ask '誰が肥料を運んだ？' --mode round5 --document <一時文書>`: 終了コード 0。標準出力は JSON object で `verdict` が文字列。この確認は起動と出力形のみで、答えの正しさを測らない。
5. 隔離した store と loopback の空き port で `vera serve --no-llm` を起動する。GET `/v1/models` は HTTP 200 と JSON object を返し、`data` は list、先頭モデルの `id` は `vera-no-llm`。停止時の終了コードは 0。
6. wheel zip に `verantyx/constructions/` と `verantyx/data/` の member がある。
7. 成功した runtime 読み込みを `builtins.open`、`io.open`、read-only `os.open`、`sqlite3.connect` で記録する。導入先 `site-packages/verantyx/` 配下だけを wheel member と完全な相対 path で比較する。推測で未観測ファイルを足さない。対象の未収録数は 0。
8. 配置 pack/fetch は tar と SHA-256 sidecar を `file://` で往復する。digest 一致、展開成功、出力に `VERA_PLACEMENT` の設定先があること。P3 では配置ありの `vera read` も必要。合成データを使う場合は `constructed` と型づけ、r9 配置の動作証拠に数えない。
9. 全体テストは実行しない。P4 基線比較は監査役が行う。

一時文書、隔離 store、ログ、Python runtime module は別に記録し、package-data の照合対象から除く。Python 層から見えない native/OS 内部読み込みがあり得るため、その限界を報告する。
