# 決定 A の生産側（`verantyx/verifier_agents.py` の記録値）が既存テストと衝突する一覧

測定: `artifacts/w1-g/decision_a/measure.sh`（ツリーの外の一時複写に `verifier_agents_record_result.diff` と
`test_n106_expectation.diff` を当て、同じコマンドを前後で流した）。出力: `before.txt` / `after.txt` /
`new_failures.txt` / `fixed_failures.txt` / `n106_after_diffs.txt` / `n106_tree.txt`。

ツリーには入れていない（`verifier_agents.py` は W2-b が変更中。チケットの指示）。

## 新しく落ちるテスト（`new_failures.txt` の 2 件）

| テスト id | 固定している行 | 固定している値 | 決定 A の下での値 |
|---|---|---|---|
| `tests/test_verifier_agents.py::test_passing_verdict_without_rerunnable_evidence_is_unverified` | 127 行 `assert verification["slots"]["result"] == "FAIL"` | `FAIL`（再実行できる証拠が無い PASS の報告） | `UNVERIFIED`（`after.txt`: `assert 'UNVERIFIED' == 'FAIL'`） |
| `tests/test_verifier_agents.py::test_unsafe_or_missing_artifact_cannot_complete_task[artifact:missing.json]` | 263 行 `assert verification["slots"]["result"] == "FAIL"`（直前のコメントが「再実行できない主張は FAIL として記録」と書いている） | `FAIL`（旧い形の参照で再実行できない） | `UNVERIFIED`（同上） |

どちらも、テストの意図（`ESCALATE` で完了しない・`deterministic_result == "UNVERIFIED"`）は決定 A の下でも保たれる。
食い違うのは「記録の型」だけで、テスト自身が決定 A と逆の型（FAIL）を固定している。

## 対象テスト n=106（`tests/attack/test_verifier_agents_fabrication.py::test_run_verifiers_records_references_with_their_verifier_identities`）

- ツリーでの失敗（`n106_tree.txt`）: 188 行 `assert result == "PASS"` が `'FAIL'` で落ちる。
- 決定 A の生産側の差分と 188 行の期待を `UNVERIFIED` に変えた差分（`test_n106_expectation.diff`）を当てた複写（`n106_after_diffs.txt`）:
  188 行は通り、**190 行**の `assert stored["verifiers"] == [{"verifier_id": ..., "result": "PASS", "evidence_ref": ...}]` で落ちる。
  現行の記録は `stored["verifiers"][i]` が `reported_result`・`opinion`・`items`・`session_id`・`verifier_id` のキーを持ち、
  テストが期待する旧い形（`result`・`evidence_ref`）ではない（`n106_after_diffs.txt` の `At index 0 diff:` 行）。
  190 行以降は決定 A ではなく、期待値が古い側（切り分けの順位 11）の問題なので、このチケットでは通せない。

## 決定 A の生産側を入れても減らない失敗

`fixed_failures.txt` は 0 行（差分を当てても、前に落ちていたテストが通るようにはならない）。
