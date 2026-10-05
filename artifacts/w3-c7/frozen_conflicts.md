# W3-c7: 既存テストとの食い違い（統合時に監査役が扱う。実装役は既存テストを編集していない）

基線 `/Users/motonisihikoudai/Projects/vera-impl/baselines/dev_6bc410d_failures.txt`（116 件）との差は `new_failures.txt`（36 件）。全体テストは `pytest_full.txt`（151 failed、15663 passed）。36 件の内訳は次のとおりで、**これ以外の新しい失敗は 0**。

| 件数 | テスト | 理由の種類 | 段 C7 が読んだ文の判定 |
|---|---|---|---|
| 1 | `tests/test_question_cross.py::test_existing_functions_and_constants_are_byte_identical_to_the_base` | `_read_ja` の本文の sha256 を固定（基点 `6d9d64a8…` → 今 `18a84477…`）。チケットが `_read_ja` を 1 行変える（`return` → `out =` ＋ 1 行）ことを指示している | 該当なし（`frozen_conflicts_evidence.txt`） |
| 1 | `tests/test_w10f04_holes.py::test_semantic_read_existing_lines_are_not_changed` | `git diff -U0 6bc410d -- verantyx/semantic_read.py` の `-` 行が 0 であることを要求。同じ 1 行の変更で落ちる（`-            return out if out['readable'] else _w3b3_read_ja(text, R, placement, out, unsupported_report)`）。**指示書の食い違いの一覧に無かったもの** | 該当なし |
| 3 | `tests/test_semantic_read_w3b6.py::test_the_top_level_definitions_of_the_base_are_unchanged_and_the_new_constants_are_the_two_registered`・`::test_the_particles_stage_r_reads_are_the_seven_without_ga_and_wo`・`::test_the_end_of_the_reader_has_no_word_of_a_sentence_and_assigns_none_of_the_names_of_the_entry` | 最初の `# W3-b6:` から **ファイル末尾まで** を走査する（最上位の名前が W3-b6 のものだけ・全文 ASCII）。段 C7 の末尾追記が当たる | 該当なし。走査を `# W3-c7:` の手前で止めれば、同じ判定（ASCII のみ・基点の最上位の定義の不変）が通ることを `frozen_conflicts_evidence.txt` に出した（`ascii_only_before_c7: True`、`base_defs_unchanged: True`、段 C7 が足した名前は `_w3c7_*`・`w3c7_*`・`W3C7_*`・`_W3C7*` だけ）。`chr()` などで ASCII に見せかける回避はしていない |
| 15 | `tests/test_semantic_read_w3b3.py::test_te_and_the_continuative_are_not_in_the_output_and_the_edge_is_in_the_diagnosis[W3B3-PAR-001〜008・016〜022]` | W3-b3 の凍結データの て・連用中止 15 行は「入口では棄権、辺は診断にだけ」と固定していた。チケット (2) が、両節に主語のあるこの形を `sequence` として読むと決めた（棄権 → 正読） | 15 行すべて `correct`（`w3b3_par_evidence.txt`: 前 `readable=False`（`RELATION_NOT_MAPPED:frame`）→ 後 `readable=True`、関係は `sequence`。正解は `["sequence","manner","cause"]`（て）・`["sequence"]`（連用中止）） |
| 15 | `tests/test_semantic_read_w3b3.py::test_when_the_path_does_not_read_the_output_is_the_bases_and_the_questions_are_the_bases_until_the_gates_that_need_none[<上の 15 文>]` | 同じ 15 文。「W3-b3 が読まない文は出力が基点と同じ」と固定していた | 同じ 15 行が `correct` |
| 1 | `tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches` | チケットが「未コミットの間だけ」と書く環境由来（2 回の走行の比較の `<WORK>/home` の一致が `False`）。段 C7 とは無関係 | 該当なし |

## 前後の出力の全文
`w3b3_par_evidence.txt`（W3B3-PAR-001 と 016 の前後の出力の全文と正解、15 行の前後の `readable`・判定・関係）。
`w3b3_fixture_delta.txt`（W3-b3 の凍結データ 203 行の入口の判定の差。変わったのは上の 15 行だけで、すべて棄権 → `correct`）。

## 全体テストの実行中に既存テストが書き換えたファイル
`tests/attack/w3a3/r6_48_queries.jsonl`（実行後に `git status` に `M` で出た）を `git checkout -- tests/attack/w3a3/r6_48_queries.jsonl` で戻した。
基線にあって今は通った 1 件: `tests/test_one_trace.py::test_every_default_integration_part_has_a_trace`（基線は環境由来。今回の変更とは無関係）。
