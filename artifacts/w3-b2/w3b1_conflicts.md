# 凍結した W3-b1 のテストとの衝突(W3-b2。指示書 §3.9 の (A)(B)(C))

実測の出所: `existing_tests_after.txt`(`W` で既存の 14 ファイル + `tests/reading_soundness`: 4 失敗・2548 成功)、`existing_tests_dev.txt`(`DEV` = 基点の展開。`.git` が無いので `git show` を使うテストと `test_semantic_read_w3b1_i5.py` は環境の差で落ちる。`W` と `DEV` の失敗集合の差は下の 4 件だけが `W` にだけある)。凍結したテスト・データは **1 バイトも変えていない**。変えれば直る提案の差分は `proposed_w3b1_test_changes.diff`(`W` には当てていない。提案を当てた木 `S/prop2` で 4 件がすべて通ることを確かめた。`prop2` に `.git` が無いので `git show` のテスト 7 件は落ちるが、それは `DEV` と同じ環境の差)。

| # | 落ちたテスト | 種類 | 新しい出力 | `b1.judge` | どの規則か |
|---|---|---|---|---|---|
| 1 | `test_semantic_read_w3b1.py::test_path_u_abstains_with_the_typed_reason_of_the_first_decision_that_fails[over13-PLACEMENT_MULTIPLE:が:猫]` | (A) 仕様の帰結で新しく読めた | `猫が庭へ歩いた。` → agent 猫（`placement_all_candidates:ANIMAL+PERSON`）、goal 庭（`placement_direct:PLACE`）。出所の欄つき | `correct`(手で書いた正解 `{agent: 猫, goal: 庭}` に対して `b1.judge`。この文は凍結データに無い) | §3.4・K95: 全候補が agent の期待(PERSON・GROUP_ORG・ANIMAL)に入る MULTIPLE |
| 2 | `test_semantic_read_w3b1.py::test_path_s4_registered_unread_constructions[母がこの夜、手紙を書いた。-PLACEMENT_PART_NOT_ISOLATED]` | (A) | agent 母・patient 手紙・time 夜（`role_basis: {time: placement_direct:TIME}`、`role_flags: {time: {determiner: この}}`） | `correct`(手で書いた正解 `{agent: 母, patient: 手紙, time: 夜}`(規約どおり指示詞は値から外す)に対して `b1.judge`。この文は凍結データに無い) | §3.7・K97 (D1) |
| 3 | `test_semantic_read_w3b1.py::test_every_row_of_the_new_data_with_the_fixture[W3B1-S4-084]` | (A) | `弟がその冬、本を読んだ。` → agent 弟・patient 本・time 冬（`role_flags: {time: {determiner: その}}`） | `correct`（`b1.judge(row['expect'], …)`。`delta.jsonl` の `newly_read` の `ja_r8.jsonl` 1 件がこの行） | §3.7・K97 (D1) |
| 4 | `test_semantic_read_w3b1.py::test_only_the_gate_and_the_query_adapter_read_the_fields_of_an_answer` | (A2) 仕様の帰結(源の走査) | 出力は変わらない。`semantic_reader` の中で答えの欄(`state`・`origin`・`top`・`decided_by`・`estimate_basis`)を読む関数が `placement_type` のほかに `placement_fit`・`predicate_frame` に増えた(`_placement_answer_problems` は元から) | — | 指示書 §3.4・§3.3 と R5 の `placement_field_uses_explained.txt` が、この 2 関数の中での読みを前提にしている(`placement_type` を変えずに「全候補が合う」を決めるには、答えの `top`・`decided_by` を読む関数がもう 1 つ要る) |

(B)(出力は W3-b1 と同じだが、W3-b2 の計画が固定の答えに無い語を問い合わせた)は **0 件**: `test_semantic_read_w3b1*.py` の固定の答え(`w3b1_fakes.FixtureQuery`)で `misses` を数えるテストはすべて通っている。

(C)(それ以外。実装の誤り)は **0 件**。

## 提案の差分の中身(名前は変えない。変えた行ごとに前後)

1. `test_only_the_gate_…`: `allowed = {'placement_type'}` → `{'placement_type', 'placement_fit', 'predicate_frame'}`(`_placement_answer_problems` の許可は元の式のまま)。理由: 上の #4。
2. `…[over13-…]`: `({'猫': F.answer(['ANIMAL', 'PERSON'])}, 'PLACEMENT_MULTIPLE:が:猫')` → `({'猫': F.answer(['ANIMAL', 'ABSTRACT'])}, 'PLACEMENT_MULTIPLE:が:猫')`。理由: `[ANIMAL, PERSON]` は全候補が合うので読む。候補に外れがある割れ(`ABSTRACT` を含む)は棄権のまま。テストの意図(割れは棄権)は保たれる。全候補一致の読みは `tests/test_semantic_read_w3b2.py` が確かめる。
3. `…registered_unread_constructions`: `('母がこの夜、手紙を書いた。', 'PLACEMENT_PART_NOT_ISOLATED')` → `('母がどの夜、手紙を書いた。', 'PLACEMENT_PART_NOT_ISOLATED')`。理由: この・その は指示詞の印として読む。読まないままの連体詞は `どの`(疑問)。
4. `ja_r8.jsonl` の `W3B1-S4-084`: `entry_expect: "abstain"`・`expect_reason_prefix: "PLACEMENT_PART_NOT_ISOLATED"` → `entry_expect: "read"`・`expect_reason_prefix: null`。理由: 上の #3。`W3B1-S4-083`(この夜 + 開けた)は述語が下一段で派生の疑いの門に当たるので棄権のまま、`W3B1-S4-085`(あの夜)は あの がタガーに感動詞と切られるので棄権のまま。

## 環境由来(W3-b2 と無関係)

- `DEV` で落ちる `test_event_cross_entry.py` の 12 件・`test_semantic_read_w3b1*.py` の `…base_commit_did`・`…byte_for_byte` は `DEV` に `.git` が無いための差(`git show` を使う)。`W` では通る。
- `DEV` で落ちて `W` で通る `test_semantic_read_w3b1_r3.py::test_every_row_of_ja_r9_with_the_fixture[W3B1-R9-S4-030]` は、全体テストの基線(`dev_3b31258_failures.txt`)に無く、`W` の全体テストでも通る(`pytest_fixed_vs_baseline.txt` は 0 件)。`DEV` に `.git` が無い環境の差と考える(原因の追究はしていない)。
- 全体テストで基線に無い失敗は 5 件(`pytest_new_failures.txt`): 上の 4 件と、`tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches`。s6 は共通指示のとおり環境由来(未コミットの間だけ失敗する)で、`W` をコミットした複製(`S/committed`)で `tests/bank_score`・`tests/test_semantic_read.py`・`r2`〜`r4` を流すと全部通る(`s6_in_committed_copy.txt`)。
