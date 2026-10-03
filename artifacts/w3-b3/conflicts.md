# W3-b3: 既存テストとの衝突（手順 8。§3.12）

実測: 全体テストを実装の後の木で流した（`pytest_full.txt`）: 基線の一覧（`dev_c875ed3_failures.txt`）に無い失敗が 3 件（`pytest_new_failures.txt`）。関係するテストだけを先に流した `pytest_related.txt` では 2 件（`tests/test_question_cross.py` は関係するテストの範囲の外だった）。

| テスト | 分類 | 原因 | 処置 |
|---|---|---|---|
| `tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches` | 環境由来（共通指示: `test_s6_…` は未コミットの間だけ落ちる） | 作業ツリーが未コミットのため | `S/committed`（`W` の写しに `git init && git commit`）で流して通ることを確かめた（`s6_in_committed_copy.txt`）。 |
| `tests/test_semantic_read_w3b2.py::test_the_functions_of_the_entry_that_are_not_the_typed_reread_are_the_base_commits` | **(C) 構造の衝突（読みの正誤ではない）** | このテストは `semantic_read.py` の関数のうち W3-b2 の基点 `3b31258` から変わったものが `['_typed_reread_ja']` だけであると主張する。W3-b3 のチケット（指示書 §3.1・§2.1）は `_read_ja` の 2 行（`_typed_reread_ja` が読めなければ `_w3b3_read_ja` を呼ぶ）の変更を **求めている** ので、`_read_ja` も変わった関数に入る。 | **既存テストは変えていない。** 提案の差分は `proposed_test_changes.diff`（`W` に当てていない）。構成を棄権に戻して直すことはできない（`_read_ja` の差し込みを戻すと新しい経路の入口が無くなる）。中間職か監査役が改訂を認めたときだけ当てる。別の案（採らなかった）: 差し込みを `_typed_reread_ja` の中に移せばこのテストは通るが、指示書 §0 は `_typed_reread_ja` を変えてよい関数にしていない。 |
| `tests/test_question_cross.py::test_existing_functions_and_constants_are_byte_identical_to_the_base` | **(C) 構造の衝突（読みの正誤ではない）** | W3-c2 の「既存の関数・定数が基点とバイト一致」のテストは、`_read_ja` の本文の sha256 を固定の値で持つ。指示書が求める `_read_ja` の 2 行の変更で、その値が変わる（`caac7ccd…` → `6d9d64a8…`）。 | **既存テストは変えていない。** 提案の差分（その行の値の置き換え）は `proposed_test_changes.diff` の 2 つ目。同じ扱い。 |

提案の差分 2 つを、`W` の写し（`S/patched`。`.git` の指す先は同じで、コミットはしていない）に当てて、2 つのテストが通ることを確かめた（`proposed_changes_in_a_copy.txt`: 58 passed）。`W` には当てていない。

(A)（新しい読みが正しい）に当たる、配置ありの既存テストの棄権の期待との衝突は 0 件。(B)（新しい読みが誤り）は 0 件。W3-b1・W3-b2・W5-a・観測（283 件、dev と同じ結果）・十字（E1_SAME ほか）のテストはすべて通る。
