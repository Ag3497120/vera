# W7-release r1 事前登録

登録時刻: 2026-10-04 09:31 JST  
同期元: 読み取り専用 `/Users/motonisihikoudai/Projects/vera-impl/vera-dev`、branch `dev`、HEAD `89e3d2e358c5fed67ba0c71be1b5f0325022a423`。  
同期先: `/Users/motonisihikoudai/Projects/vera-impl/wt/pub-release`。

## 対象と境界

- 同期対象は同期元の `verantyx/`、指定された設計文書、指定されたテスト候補とその必要データ、公開クローンのパッケージ設定・README・評価文書・既知の問題文書。
- `artifacts/`、`attacks/`、`results/`、隠しバンク、配置 SQLite、環境変数ファイル、鍵は同期しない。別の `wt` は開かない。
- `vera-dev` は計画書にある読み取り専用同期元として扱う。チケット本文にある別 `wt` の記述より、ユーザー共通指示と計画書の同期元指定を優先する。
- Python 検証は指定インタープリター、`PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/pub-release`、`PYTHONDONTWRITEBYTECODE=1` を使う。pytest には `-p no:cacheprovider` を付け、`verantyx*` の import 元がすべて同期先内であることを記録する。

## 凍結対象

実装前に同期元のコミット、対象文書、対象テストと必要データの相対パス・SHA-256 を記録する。テスト候補はチケット記載の `tests/test_semantic_read*.py`、`tests/event_cross/`、`tests/observe/`、`tests/test_basis_policy*.py`、`tests/test_routing_from_text*.py`、`tests/test_question_cross*.py`、`tests/test_chat_repl.py`、`tests/reading_soundness/**` とする。配置・隠しバンク・外部ファイル依存が判明したものは実装前の判定と理由を記録し、実装後に基準を緩めない。

事前のパス検査で、次の候補テストは `build/coarse-W3a/full/r7` または `r8` の外部配置に依存していることを確認したため、公開クローンへは写さない: `test_question_cross_w5d.py`、`test_routing_from_text_w5e.py`、`test_semantic_read_w3b4.py`、`test_semantic_read_w3b5.py`、`test_semantic_read_w5e.py`。これらの参照行は凍結マニフェストの対象で、出所とハッシュは `freeze.r1.json` にある。`tests/test_chat_repl.py` と `docs/CHAT.md` は同期元に存在しないため、チャット入口は P1 の固定入力で直接確かめ、CHAT 文書は公開側で作成する。

追加事前登録（import 依存の確認後）: 対象テストの import を追ったところ `tools/bank_score/**` と `tools/build_p4_corpus_index.py` が公開側に必要と分かった。これらはテストが使う公開の採点・合成 fixture 用支援コードとして、コピー前に source commit と SHA-256 を `freeze.r1.json` に追記する。`tests/reading_soundness/` はチケットの「データ」に限定し、JSON/JSONL/TXT のみ写す。同ディレクトリの pytest モジュールは artifacts のハッシュ記録に依存するため写さない。

追加事前登録（一時領域での最初の収集確認後）: 補助データの欠落を検出した。再試行には指定文書、`tests/bank_score/fixtures/B1_v2/items.jsonl`、`tests/reading_soundness/` のうち `test_*.py` 以外の fixture helper を加える。`test_basis_policy_w5e.py` は import 時に外部 `artifacts/w5-e/h4_inputs.json` を読むため除外する。`test_question_cross_w5e.py` は実配置依存の除外対象 `test_question_cross_w5d.py` から helper を import するため除外する。テスト本文・期待値は変更しない。

追加事前登録（2 回目の収集確認後）: `test_semantic_read_r2.py`、`test_semantic_read_r3.py`、`test_semantic_read_w3b1.py` が追加の `B1_v2_r2` / `B1_v2_r3` fixture を読むと判明したため、両 fixture もコピー前に SHA-256 を凍結する。`test_semantic_read_w1a5.py` は `artifacts/w1-a5/expect_exceptions.json` を読むため除外する。`test_semantic_read_w3b1_i5.py`、`test_semantic_read_w3b2.py`、`test_semantic_read_w3b3.py`、`test_semantic_read_w3b3_events.py`、`test_semantic_read_w3b3_m1r3.py`、`test_semantic_read_w3b3_r2.py` は開発 Git の過去コミットから `git show` でコードを取るため除外する（公開クローンにはその履歴が無い）。

実行前の静的依存確認で追加判明: `test_semantic_read_w3b1.py` と `test_semantic_read_w3b1_r3.py` は開発 Git の過去コミットを `git show` し、`test_semantic_read_w3b1_r4.py` はそれに加えて `artifacts/w3-b1/bank_freeze_r10.sha256` を読む。公開クローンにその履歴・artifacts はなく、混入禁止のため P2 実行対象から外す。これら 3 ファイルはコピー後に依存が分かったため、ユーザーの「テスト削除禁止」に従って凍結済みのまま残し、ソース本文や期待値は変更しない。これは、依存判定と実行対象の更新をコピー前に済ませるべき手順からの逸脱として記録する。

P2 初回実行で `test_routing_from_text*.py` が `tests/routing_from_text/` の公開 fixture・helper を読むこと、および `test_event_cross_entry.py` が開発 Git の過去コミットを読むことが判明した。`tests/routing_from_text/**` の全 17 ファイルを別紙ハッシュで凍結してから同期する。`test_event_cross_entry.py` は履歴なしでは実行できないため P2 対象から外す。これらの不足確認は実装後・テスト候補コピー後の P2 初回実行で判明したため、P2 完了前に追加した手順変更として報告する。テスト本文・期待値は編集せず、既存テストは削除しない。

## 受入判定手順

- **P1 固定入力**: UTF-8 文書 `花子が太郎に資料を渡した。`、入力 `資料の出来事を一文で言い換えてください。` を使う。文書・問い合わせは実装前に固定し、SHA-256 を記録する。
- **P1**: 同期先の `vera_base` を import し、round5 のチャットを文書付きで一往復、同じ文書への ask を実行する。同期元の CLI 出力との UTF-8 バイト一致を比較し、コマンド・終了状態・標準出力・標準エラーを保存する。実行時に解決された `verantyx*` のファイル位置も保存する。
- **P2**: 凍結した依存非該当テストを同期先内で実行する。収集数・成功数・失敗数・未収集数、実行コマンド、出力を記録する。
- **P3**: `find . -size +50M` と、禁止名（hidden、artifacts、build、環境変数ファイル、鍵）の作業ツリー検査を実行し、出力を保存する。
- **P4**: README・EVAL・KNOWN_ISSUES の数値をチケット記載値と照合する。`baselines/scores` は同期元に存在しないため、チケットにない評価値を追加しない。数値の照合表を報告に残す。

## 期待値と棄権条件

隠しバンク等の値はチケット記載値だけを正とする。未提供・未測定の評価数値は補わない。P1 のバイト一致、P2 のテスト、P3 の混入検査、P4 の数値照合のどれかを実行結果で確認できない場合、全受入完了とは報告しない。
