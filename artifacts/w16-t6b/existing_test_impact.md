# 既存の T6 テストへの影響（K605 を入れたことで赤くなるもの。実装役は編集していない）

実測: `PYTHONPATH=<ツリー> $PY -P -m pytest -q -p no:cacheprovider tests/test_w16t6_*.py` → **11 failed, 100 passed**（`t6_existing_after.txt`。中間職の見込みの 11 件と同数・同じテスト）。
原因はすべて同じ: これらの台帳は T7 の形ではない（`actor` が文字列 `"x"`、1 行目の `prev` が `None`、ファイル名が `ev.jsonl`、HEAD 無し）。a16 と同じ形なので、a16 を止める規則はこれも止める。
期待値は 1 つも変えていない。移行案（`proposed_t6_test_migration.diff`）は台帳の作り方だけを T7 の配置に変え、assert 行を 1 行も変えない（diff 内の assert 行の増減 0 件）。
その案を複製 `scratchpad/W16-t6b/mig/new` で流した結果が `proposed_migration_pytest.txt`（3 ファイル 23 件すべて通る）。ツリーには適用していない。

| # | テスト | 行 | assert の全文 | 変更前 | 変更後 | 理由 |
|---|---|---|---|---|---|---|
| 1 | test_w16t6_basis.py::test_collect_only_event_is_not_a_basis_for_passed | 42 | `assert passed(Verifier(t, ledger=led), "tests/f.py")["reason"] == "NO_EVENT"` | NO_EVENT | LEDGER_UNVERIFIED | 台帳が `ev.jsonl`（T7 の名前でない）・actor 文字列 |
| 2 | test_node_only_and_k_only_events_are_not_a_basis | 50 | `assert r["mark"] != RECORD and r["reason"] == "NO_EVENT", argv` | NO_EVENT | LEDGER_UNVERIFIED（mark は TESTIMONY のまま） | 同上 |
| 3 | test_two_file_event_failing_cannot_be_pinned_on_one_file | 57 | `assert r["mark"] == TESTIMONY and r["reason"] == "NO_EVENT"` | NO_EVENT | LEDGER_UNVERIFIED | 同上 |
| 4 | test_two_file_event_passing_backs_each_file | 65 | `assert (r["mark"], r["reason"]) == (RECORD, "MATCH")` | RECORD/MATCH | TESTIMONY/LEDGER_UNVERIFIED | 同上 |
| 5 | test_single_file_event_failing_is_a_mismatch | 73 | `assert (r["mark"], r["reason"], r["actual"]) == (MISMATCH, "EXIT_CODE_DIFFERS", 1)` | MISMATCH/EXIT_CODE_DIFFERS/1 | TESTIMONY/LEDGER_UNVERIFIED/None | 同上 |
| 6 | test_unknown_flag_makes_event_unusable | 80 | `assert passed(Verifier(t, ledger=led), "tests/g.py")["reason"] == "NO_EVENT"` | NO_EVENT | LEDGER_UNVERIFIED | 同上 |
| 7 | test_exit_evidence_for_ledger_and_rerun | 109 | `assert f["mark"] == MISMATCH and f["evidence"]["path"] == led and f["evidence"]["sha256"] and f["evidence"]["event_sha"]` | MISMATCH | TESTIMONY | 同上 |
| 8 | test_w16t6_ledger.py::test_events_ledger_valid_tampered_and_split | 75 | `assert (f["mark"], f["reason"], f["actual"]) == (RECORD, "MATCH", 3)` | RECORD/MATCH/3 | TESTIMONY/LEDGER_UNVERIFIED/None | 台帳に `kind: "note"`（T7 の種類にない）・actor 文字列・prev None・HEAD 無し |
| 9 | test_ledger_event_beats_rerun_and_unverified_falls_back_to_rerun | 106 | `assert f["mark"] == RECORD and calls == []` | RECORD（台帳の出来事が再実行に勝つ） | MISMATCH（台帳は未検証になり、再実行の結果 0 と申告 1 が食い違う） | 同上（`ev.jsonl`・actor 文字列） |
| 10 | test_w16t6_synth.py::test_no_false_claim_is_recorded_and_no_true_claim_is_flagged[V] | 47 | `assert x["detected"] == x["false_facts"]` | 22 == 22 | 20 == 22 | 合成 S26・S27 の偽の終了コードが MISMATCH から TESTIMONY に下がる（偽の RECORD は 0 のまま。`missed`・`false_positive` は 0） |
| 11 | 同 [a] | 47 | 同上 | 22 == 22 | 20 == 22 | 同上 |

合成 40 件の指標（`synth_before/t6_1_synth.json`・`synth_after/t6_1_synth.json`）:
- V: detected 22→20、abstain_false 0→2、insufficient 0→5、exact 85→78（facts 85）。false_positive 0、missed 0。
- a: detected 22→20、abstain_false 0→2、insufficient 0→4、exact 84→78（facts 84）。false_positive 0、missed 0。
- b: detected 22→20、abstain_false 0→2、insufficient 0→5、exact 75→68（facts 85）。

## 意図を保った移行案（`proposed_t6_test_migration.diff`）
- basis.py の `ledger()`: `ledger_events.append` で `<tmp>/led<N>/events.jsonl`（T7 の行・HEAD）を作る（呼ぶごとに別ディレクトリ）。
- ledger.py の `_row`/`chain`/`write`: T7 の行（actor は dict、1 行目の prev は GENESIS、sha は `ledger_events.sha_of`）、`write` は HEAD も書く。台帳の置き場所は `<tmp>/led/events.jsonl`。`kind: "note"` は T7 の種類にないので `owner_utterance` に置き換える（assert は変えない）。
- 合成 40 件（凍結物）: `cases.jsonl`・`expected.jsonl` は触らず（freeze.sha256 のまま）、`synth_lib.materialize` が台帳を `ledger_events.append` で `<root>/<id>.ledger/events.jsonl` に作る（`note` は `owner_utterance`）。この案で `test_w16t6_synth.py` の 5 件が通る（`detected == false_facts` を含む）。
- 適用するかは監査役が決める。
