# W3-c4 攻撃報告

## 1. 対象

- `docs/OBSERVATION.md:1337-1360` の D3〜D6（round5・文書あり・既存 verdict が `UNKNOWN_UNREAD` / `UNKNOWN_NO_EVIDENCE` の場合だけ後段、D4 の文書読込と文分割、D5 の出典出力、D6 の方針接続）。
- `docs/BASIS_POLICY.md:1277-1279` の W3-c4 接続注記（文書由来の `sources[].text` は文書本文の行から切り出され、W5-d の本文照合を満たす）。
- 実装は指定の読み取り専用 `VERA_PLACEMENT` r8 を使い、CLI `vera ask` 相当の `cli.main` を通した。実データの期待表や隠しバンクは使っていない。

## 2. 命中した攻撃

### A1 — 元ファイルに無い出典文を `ANSWER_HUMAN_BASIS` として返す

- 観点: (c) 出典 `text` の本文照合。
- 再現コマンド:

  ```bash
  PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -s attacks/W3-c4/test_attack_w3c4.py::test_markdown_link_evidence_text_is_a_literal_source_substring
  ```

- 入力文書（`linked.md` の1行目）: `先生は[本](https://example.org/book)を読んだ。`
- 質問: `先生は何を読んだ？`
- 実際の出力（テストが標準出力に出した JSON）:

  ```json
  {"basis_outcome": "ANSWER_HUMAN_BASIS", "raw_document_line": "先生は[本](https://example.org/book)を読んだ。", "source": {"family": "document", "line": 1, "sentence_id": "linked.md#1:1", "source": "linked.md", "text": "先生は本を読んだ。"}, "text": "本", "verdict": "ANSWER"}
  ```

- 期待との差: 返された `sources[0].text` の `先生は本を読んだ。` は入力ファイルの行に連続した文字列として存在しない。読み込み時にリンク先を落とし、リンク表示語を残して周囲と連結した後の文が出典になっている。方針も `ANSWER_HUMAN_BASIS` を返す。
- 該当箇所: [`verantyx/document_loaders.py:185-225`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-c4/verantyx/document_loaders.py:185) が Markdown リンクをラベルだけにし、空隙を畳む。後段は [`verantyx/cli.py:278-288`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-c4/verantyx/cli.py:278) で変換済みの `doc.text` から文を作り、[`verantyx/cli.py:292-301`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-c4/verantyx/cli.py:292) でその文を出典にし、[`verantyx/cli.py:390-395`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-c4/verantyx/cli.py:390) で回答に載せる。方針の照合も [`verantyx/basis_policy.py:158-168`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-c4/verantyx/basis_policy.py:158) でロード後の文書テキストを使う。
- 範囲の限定: D4 は文書を `Document.text` として扱い、`_document_texts` と同じ読み方を明記している。その定義では返却文はロード後本文に存在する。命中は「オーナーが渡した元ファイルの逐字的な出典を返す」という読みでの本文追跡性に限り、回答内容が誤り、または W5-d のロード後照合をすり抜けた、という主張ではない。

## 3. 外れた攻撃

新規攻撃テストの残り23件は、指定配置で実行しても誤答・条件外の差分を再現しなかった（`1 failed, 23 passed`）。主な出力と理由:

- 英語 `The clerk reads the newspaper.` に `What did the clerk read?`、報告引用 `先生は「本を読んだ」と言った。`、否定文への肯定質問、受身・使役・時の副詞 → いずれも `UNKNOWN_UNREAD`・`NO_ATTESTED_CELL` で棄権。
- 同じ述語で主語と目的語を入れ替えた2文と「は」主題 → `先生は誰を見た？` に `生徒` を返し、出典は `先生は生徒を見た。`。
- 質問末尾の「の」「か」 → `PREDICATE_FORM_DIFFERS` で元の棄権。「のですか」は `QUESTION_NOT_READ`。丁寧形 `読みました` と普通形の質問も `PREDICATE_FORM_DIFFERS`。
- 文末句点なし・全角空白 → `本` を返し、出典文は入力の部分文字列。文中改行では `NO_ATTESTED_CELL`。`Mr. Smith` は `NO_TYPED_CANDIDATE` で誤答なし（r8 配置に英語名の型がないため、略語境界保護自体の検証にはならない）。同一文を2文書に置くと `本` と2件の出典を返した。
- `.txt` の文中 URL を除くと文が成立する候補 → `NO_ATTESTED_CELL`。該当文を出典にする経路には到達しなかった。
- 条件外: round5 の既存回答は後段を no-op にした出力と時間鍵だけを伏せて一致。文書なしの `UNKNOWN_UNREAD` と、文書ありの `UNKNOWN_UNSUPPORTED_EVIDENCE` も同じ比較で一致。legacy+文書は `UNKNOWN_ROUTE_CONFIGURATION`、engine は `UNKNOWN_NOT_LOADED` で、どちらも `question_cross` なし。
- 方針接続: factual は `ANSWER_HUMAN_BASIS`、creative は `CONSTRUCTED`、`--show-generated-reference` は `ANSWER_HUMAN_BASIS`。不正な `--confirm` id は `UNKNOWN_CONFIRM_ID`・`wrote:0`。初回は confirm を付けても回答が維持されると誤って想定したが、有効でない id を拒む既存方針の出力であり攻撃ではないため、最終テストではこの出力を期待値にした。
- 比較用の関係テスト `tests/test_ask_question_cross.py` は `64 passed`。新規攻撃テストは上記の1件を意図的に失敗として確認した。

## 4. 数と制限

- 命中: **1**（A1、元ファイルの逐字的な出典文字列が出ない経路）。
- 外れ: **23**（上記の意味誤答・棄権形・方針・条件外の攻撃）。
- 製品コードは変更していない。新規ファイルは `attacks/W3-c4/` のテストとこの報告だけ。ネットワーク、隠し評価バンク、別クローン、commit/push は使っていない。
- 測れていない範囲: `vera chat`、隠しデータ、人手が意味付けしたMarkdown表示本文と元ファイル表現のどちらを「文書本文」とするかの裁定。r8 で英語の述語照合の誤答は再現せず、これは英語全般の正しさの証明ではない。
