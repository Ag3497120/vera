# W1-f 残っている失敗テストの原因切り分け（直さない。分類して次の仕事にする）

基点は `dev`（`075d486`）。この文書は調査と分類だけを書く。製品コード（`verantyx/`）もテスト（`tests/`）も変更していない。数値は、`<!-- w1f:begin:… -->` と `<!-- w1f:end:… -->` で囲んだ生成ブロックの中にあるか、地の文では出典ファイルを括弧で添えた。生成ブロックは `tools/w1_f_triage.py report` が `artifacts/w1-f/` から作り、`check` がバイト一致を検査する。

再生成の入口（すべて `tools/w1_f_triage.py` の下位コマンド）: `collect` → `baseline` → `isolate` → `history` → `probe revert／adapt／combo／env` → `fixcheck` → `qf2 ids own off err abl cap repro demo` → `report` → `check`。人が書く入力は `decisions.jsonl`・`bundles_input.jsonl`・`intent.jsonl`・`ticket_drafts.jsonl` と、`probes/*.diff`・`fixes/*.diff`（差分）だけで、それ以外は測定から再生成される。

## 1. 測定条件と、チケットの前提との食い違い

- 実行環境: Python は `/Users/motonisihikoudai/vera-wiring/env/bin/python`（3.11）、`env -i` に `HOME`・`PATH`・`PYTHONDONTWRITEBYTECODE=1`・`PYTHONHASHSEED=0` と `PYTHONPATH=<対象ツリー>` だけを渡す。pytest には `-p no:cacheprovider`。テストの選択は pytest の CLI 引数ではなく、実行時に書き出す選択プラグイン（`nodeid` の完全一致、非 ASCII の parametrize ID を CLI で選べないため）で行い、読み込まれた `verantyx*` がすべて対象ツリー配下であることを実行ごとに検査した（外れは `ISOLATION_VIOLATION`）。過去コミット・修正案の複写は `git archive` または `git clone --shared`（`$W/.git` に書かない）でツリーの外に作った。

<!-- w1f:begin:measure -->
- 収集（`collect.txt`）: 3986 tests collected
- 差分（`collect_delta.txt`）: tests/test_build_public.py: 12 tests collected / changed test files 6c0d71e..075d486: / tests/test_build_public.py
- 作業前の全体実行と基線の照合（`suite_before_compare.txt`）: SAME / failed_lines=124 matched_baseline=124 baseline_size=124
- 1 件ずつ別プロセスで実行（`runs_index.jsonl`）: {'failed': 124}、隔離違反 0 件
- 履歴（`history.jsonl`）: 追加時の状態 {'PASS': 120, 'XFAIL': 2, 'FAIL': 2}、境界の両端を実測で確かめた件数 122
<!-- w1f:end:measure -->

チケットの記述と実測が食い違った点（出典つき）:

1. **収集件数**: チケットは 3,974 件収集と書くが、実測は `artifacts/w1-f/collect.txt` の件数。差は W1-b の merge（`6c0d71e..075d486`）で足された `tests/test_build_public.py`（`collect_delta.txt`）。失敗集合は基線の 124 件と同一（`suite_before_compare.txt`）。
2. **「原因が未分類」の件数**: チケット・W0-1 の文書にある「未分類」「期待値が古い」の件数は測り直さず、写してもいない。失敗の全件に分類と根拠を付けた（下の集計、`triage.jsonl`）。W0-1 の「期待値が古い」は「テスト側を機械的に変えた複写で通る」という別の根拠で、この文書の定義（unit の意図したコミットを示す）とは違う。
3. **`w_question_forms2` の 34 件は「後から入った構文規則との衝突」ではない**: 34 件は qf2 自身のコミットで起きる（親で通り自身で落ちる。`qf2/own_commit.json`）。構文規則をすべて外しても落ちる（`qf2/constructions_off.json`）。`dev` の `semantic_wh.py` は親 `498f3c3` の版と同一なので、原因は `9c89f1e` の `semantic_wh.py` の差分そのもの。9 節に詳細。
4. **受入デモの失敗は 34 件とは別の現象**: デモは `9c89f1e`・`da21edc` で `DEMO OK`、`p_reason`（`b8b9a50`）以降で `AssertionError`（`qf2/demo_bisect.txt`）。`gold_reason` だけを外すと `DEMO OK`（`qf2/demo_leave_one_out.txt`）。
5. **役割の語彙が二通り並存している**: reader（`4af1231`）は で→place、から→source、まで→limit を出し、`semantic_wh.py`・`semantic_realize.py` は location・origin のまま。`semantic_verify.py` は両方を受理する。8 節の決定 1。
6. **`w_question_forms2` の受入はデモだけ**: 台帳の `acceptance` はデモ 1 本、wave4 の gates は route・memory_frame・conductor のテストと coverage（`manifest_wave4.json`）。攻撃テストが merge の門に入っていなかった、という事実だけを記録する。
7. **history の `first_bad` の読み方**: 追加時 XFAIL のテストは XFAIL を「良い」と数えるので、`first_bad` は xfail 印を外したコミットに寄る（`history.jsonl` の n=94 は、実際の原因 `b29097a` の stub が xfail の陰に隠れていた）。`decisions.jsonl` では原因のコミットを `changed_in` に書いた。n=82 は収集エラーの区間があり、テスト先頭に `import pytest` を 1 行足した複写で全コミットを測った（`history_patched.jsonl`。製品は変えていない）。非単調で、最後に落ち続け始めたコミットを根拠にした。

## 2. 分類の集計

分類の定義と順序は、チケットと実装指示書のとおり。「期待値が古い」は、(a) unit の指示文・最終報告がその挙動変更を明示し、(b) 新しい挙動が原則に反さず、(c) 可能なものは、テスト側だけを機械的に（期待値に触れず）合わせた複写で通ることを adapter probe で示した。形だけの adapter が作れないもの（件数・文言・verdict が期待の直接の対象）は、revert probe（その unit の製品差分を戻すと本人が通る）と意図の引用で裏づけ、`decisions.jsonl` の `adapt_note` に理由を書いた。

<!-- w1f:begin:counts -->
| 分類 | 件数 | 害 A | 害 B | 害 C | 害 D |
|---|---:|---:|---:|---:|---:|
| 製品の不具合 | 7 | 0 | 3 | 1 | 3 |
| 期待値が古い | 98 | 0 | 0 | 14 | 84 |
| テスト同士の矛盾 | 1 | 0 | 1 | 0 | 0 |
| テストの不備 | 1 | 0 | 0 | 0 | 1 |
| 判断が要る | 17 | 0 | 4 | 10 | 3 |
| 合計 | 124 | 0 | 8 | 25 | 91 |

| 落ち始めのコミット | unit（件名） | 件数 | 分類の内訳 |
|---|---|---:|---|
| a9cad0a | unit fix_w_brief_1 | 44 | 期待値が古い 44 |
| e481870 | unit g_names_fix | 22 | 判断が要る 3、期待値が古い 19 |
| 4af1231 | unit fix_semantic_reader | 16 | 判断が要る 8、期待値が古い 5、製品の不具合 3 |
| b29097a | unit fix_w_unknown_1 | 13 | 期待値が古い 13 |
| 3e36e08 | unit x_verifier_evidence | 7 | 判断が要る 1、期待値が古い 6 |
| 69b826b | unit fix_w_merge_1 | 4 | 判断が要る 3、期待値が古い 1 |
| 7b593d8 | unit fix_memory_frame | 4 | 期待値が古い 3、製品の不具合 1 |
| 38a9118 | unit finish_semantic_unknown | 3 | 期待値が古い 1、製品の不具合 2 |
| 1b2e7a4 | unit fix_semantic_coord | 2 | 期待値が古い 2 |
| born_red | 生まれたときから赤（追加コミットで既に FAIL） | 2 | テストの不備 1、判断が要る 1 |
| 068ce78 | unit fix_w_escalate_1 | 1 | 期待値が古い 1 |
| 075d486 | Merge W0-1 (integration baseline) | 1 | 製品の不具合 1 |
| 794ce88 | unit x_testimony | 1 | 期待値が古い 1 |
| 8e396b7 | unit fix_w_escalate_2 | 1 | 期待値が古い 1 |
| 9dbeea6 | unit fix_w_merge_2 | 1 | テスト同士の矛盾 1 |
| bd5dfba | unit fix_semantic_verify | 1 | 判断が要る 1 |
| d71e373 | unit k_quantifier | 1 | 期待値が古い 1 |
<!-- w1f:end:counts -->

## 3. 1 件ごとの分類表

根拠は `artifacts/w1-f/runs/NNN.txt`（NNN は基線 `dev_075d486_failures.txt` の行番号）と、`history/NNN_{good,bad}.txt`（`last_good` で通り `first_bad` で落ちる出力）。完全な根拠（引用・原則・相手・probe）は `triage.jsonl`。

<!-- w1f:begin:table -->
| n | 分類 | 害 | テスト（nodeid） | 理由（1 文目） | 原因の箇所 | 束／落ち始め／相手 | 根拠 |
|---:|---|---|---|---|---|---|---|
| 1 | 期待値が古い | C | `tests/attack/test_conductor_escalate_realtext.py::test_reask_citation_must_name_an_active_…` | fix_w_escalate_2 が memory.active() の代替確認を外した（stale な記録で resolved にならないように）。 | verantyx/conductor_escalate.py:358 | changed_in 8e396b7 | history/001_bad.txt, history/001_good.txt, runs/001.txt |
| 2 | 期待値が古い | C | `tests/attack/test_conductor_escalate_realtext.py::test_repeated_resolution_check_does_not_…` | fix_w_escalate_1 が「引用だけで記録を検証できない conductor は閉じる」へ変えた（レビュー指摘: 捏造した record id で resolved になる）。 | verantyx/conductor_escalate.py:358 | changed_in 068ce78 | history/002_bad.txt, history/002_good.txt, runs/002.txt |
| 3 | 期待値が古い | D | `tests/attack/test_memory_brief_differential.py::test_askable_and_unaskable_records_are_acc…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/003_bad.txt, history/003_good.txt, runs/003.txt |
| 4 | 期待値が古い | D | `tests/attack/test_memory_brief_differential.py::test_budget_uses_python_character_length_a…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/004_bad.txt, history/004_good.txt, runs/004.txt |
| 5 | 期待値が古い | D | `tests/attack/test_memory_brief_differential.py::test_deterministic_generated_cases_match_n…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/005_bad.txt, history/005_good.txt, runs/005.txt |
| 6 | 期待値が古い | D | `tests/attack/test_memory_brief_differential.py::test_empty_memory_and_budget_validation` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/006_bad.txt, history/006_good.txt, runs/006.txt |
| 7 | 期待値が古い | D | `tests/attack/test_memory_brief_differential.py::test_kind_timestamp_and_id_order_break_tie…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/007_bad.txt, history/007_good.txt, runs/007.txt |
| 8 | 期待値が古い | D | `tests/attack/test_memory_brief_differential.py::test_later_short_candidate_can_fit_after_e…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/008_bad.txt, history/008_good.txt, runs/008.txt |
| 9 | 期待値が古い | D | `tests/attack/test_memory_brief_differential.py::test_nfkc_casefolded_focus_ranks_matching_…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/009_bad.txt, history/009_good.txt, runs/009.txt |
| 10 | 期待値が古い | D | `tests/attack/test_memory_brief_differential.py::test_nonaskable_records_are_never_rendered…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/010_bad.txt, history/010_good.txt, runs/010.txt |
| 11 | 期待値が古い | D | `tests/attack/test_memory_brief_differential.py::test_source_membership_and_lesson_question…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/011_bad.txt, history/011_good.txt, runs/011.txt |
| 12 | 期待値が古い | D | `tests/attack/test_memory_brief_differential.py::test_superseded_records_disappear_and_clos…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/012_bad.txt, history/012_good.txt, runs/012.txt |
| 13 | 期待値が古い | D | `tests/attack/test_memory_brief_fabrication.py::test_budget_can_fit_drop_accounting_without…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/013_bad.txt, history/013_good.txt, runs/013.txt |
| 14 | 期待値が古い | D | `tests/attack/test_memory_brief_fabrication.py::test_closed_task_is_not_emitted_and_its_id_…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/014_bad.txt, history/014_good.txt, runs/014.txt |
| 15 | 期待値が古い | D | `tests/attack/test_memory_brief_fabrication.py::test_focus_changes_order_without_changing_s…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/015_bad.txt, history/015_good.txt, runs/015.txt |
| 16 | 期待値が古い | D | `tests/attack/test_memory_brief_fabrication.py::test_lesson_uses_its_situation_and_response…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/016_bad.txt, history/016_good.txt, runs/016.txt |
| 17 | 期待値が古い | D | `tests/attack/test_memory_brief_fabrication.py::test_negation_in_supported_sentence_is_pres…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/017_bad.txt, history/017_good.txt, runs/017.txt |
| 18 | 期待値が古い | D | `tests/attack/test_memory_brief_fabrication.py::test_record_without_ask_path_source_is_drop…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/018_bad.txt, history/018_good.txt, runs/018.txt |
| 19 | 期待値が古い | D | `tests/attack/test_memory_brief_fabrication.py::test_same_attribute_for_two_entities_keeps_…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/019_bad.txt, history/019_good.txt, runs/019.txt |
| 20 | 期待値が古い | D | `tests/attack/test_memory_brief_fabrication.py::test_superseded_record_is_not_rendered_or_c…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/020_bad.txt, history/020_good.txt, runs/020.txt |
| 21 | 期待値が古い | D | `tests/attack/test_memory_brief_fabrication.py::test_supported_record_is_rendered_verbatim_…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/021_bad.txt, history/021_good.txt, runs/021.txt |
| 22 | 期待値が古い | D | `tests/attack/test_memory_brief_injection.py::test_closed_task_is_dropped_and_reported` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/022_bad.txt, history/022_good.txt, runs/022.txt |
| 23 | 期待値が古い | D | `tests/attack/test_memory_brief_injection.py::test_compatibility_unicode_closed_state_is_no…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/023_bad.txt, history/023_good.txt, runs/023.txt |
| 24 | 期待値が古い | D | `tests/attack/test_memory_brief_injection.py::test_embedded_instruction_stays_attributed_to…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/024_bad.txt, history/024_good.txt, runs/024.txt |
| 25 | 期待値が古い | D | `tests/attack/test_memory_brief_injection.py::test_focus_ranks_matches_without_admitting_un…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/025_bad.txt, history/025_good.txt, runs/025.txt |
| 26 | 期待値が古い | D | `tests/attack/test_memory_brief_injection.py::test_question_path_failure_does_not_promote_r…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/026_bad.txt, history/026_good.txt, runs/026.txt |
| 27 | 期待値が古い | D | `tests/attack/test_memory_brief_injection.py::test_record_is_omitted_when_question_path_doe…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/027_bad.txt, history/027_good.txt, runs/027.txt |
| 28 | 期待値が古い | D | `tests/attack/test_memory_brief_injection.py::test_superseded_record_is_excluded_from_brief…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/028_bad.txt, history/028_good.txt, runs/028.txt |
| 29 | 期待値が古い | D | `tests/attack/test_memory_brief_injection.py::test_typed_kind_priority_precedes_input_order` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/029_bad.txt, history/029_good.txt, runs/029.txt |
| 30 | 期待値が古い | D | `tests/attack/test_memory_brief_limits.py::test_concurrent_readers_return_the_same_brief` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/030_bad.txt, history/030_good.txt, runs/030.txt |
| 31 | 期待値が古い | D | `tests/attack/test_memory_brief_limits.py::test_dropped_ids_are_reported_when_selected_line…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/031_bad.txt, history/031_good.txt, runs/031.txt |
| 32 | 期待値が古い | D | `tests/attack/test_memory_brief_limits.py::test_empty_memory_returns_empty_brief_at_zero_bu…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/032_bad.txt, history/032_good.txt, runs/032.txt |
| 33 | 期待値が古い | D | `tests/attack/test_memory_brief_limits.py::test_exact_character_budget_includes_full_select…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/033_bad.txt, history/033_good.txt, runs/033.txt |
| 34 | 期待値が古い | D | `tests/attack/test_memory_brief_limits.py::test_focus_uses_nfkc_casefold_matching_to_rank_f…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/034_bad.txt, history/034_good.txt, runs/034.txt |
| 35 | 期待値が古い | D | `tests/attack/test_memory_brief_limits.py::test_record_order_is_independent_of_active_order…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/035_bad.txt, history/035_good.txt, runs/035.txt |
| 36 | 期待値が古い | D | `tests/attack/test_memory_brief_limits.py::test_repeated_calls_are_idempotent_and_do_not_mu…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/036_bad.txt, history/036_good.txt, runs/036.txt |
| 37 | 期待値が古い | D | `tests/attack/test_memory_brief_limits.py::test_superseded_ids_are_excluded_from_output_and…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/037_bad.txt, history/037_good.txt, runs/037.txt |
| 38 | 期待値が古い | D | `tests/attack/test_memory_brief_paraphrase.py::test_closed_task_is_omitted_and_accounted_fo…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/038_bad.txt, history/038_good.txt, runs/038.txt |
| 39 | 期待値が古い | D | `tests/attack/test_memory_brief_paraphrase.py::test_empty_memory_returns_empty_string` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/039_bad.txt, history/039_good.txt, runs/039.txt |
| 40 | 期待値が古い | D | `tests/attack/test_memory_brief_paraphrase.py::test_entity_swap_is_reflected_in_the_rendere…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/040_bad.txt, history/040_good.txt, runs/040.txt |
| 41 | 期待値が古い | D | `tests/attack/test_memory_brief_paraphrase.py::test_focus_normalizes_width_and_case` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/041_bad.txt, history/041_good.txt, runs/041.txt |
| 42 | 期待値が古い | D | `tests/attack/test_memory_brief_paraphrase.py::test_focus_precedes_kind_priority` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/042_bad.txt, history/042_good.txt, runs/042.txt |
| 43 | 期待値が古い | D | `tests/attack/test_memory_brief_paraphrase.py::test_number_swap_is_reflected_in_the_rendere…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/043_bad.txt, history/043_good.txt, runs/043.txt |
| 44 | 期待値が古い | D | `tests/attack/test_memory_brief_paraphrase.py::test_polite_and_plain_wording_keep_the_same_…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/044_bad.txt, history/044_good.txt, runs/044.txt |
| 45 | 期待値が古い | D | `tests/attack/test_memory_brief_paraphrase.py::test_superseded_record_is_removed_before_dro…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/045_bad.txt, history/045_good.txt, runs/045.txt |
| 46 | 期待値が古い | D | `tests/attack/test_memory_brief_paraphrase.py::test_unaskable_record_is_accounted_for_as_dr…` | fix_w_brief_1 が compile_brief の戻り値を型付きの ContextBrief にし、各行に witness 状態と context-only を付けた。 | verantyx/memory_brief.py:169, verantyx/memory_brief.py:112, verantyx/memory_brief.py:109 | changed_in a9cad0a | history/046_bad.txt, history/046_good.txt, runs/046.txt |
| 47 | 期待値が古い | D | `tests/attack/test_memory_frame_limits.py::test_empty_memory_returns_unknown_without_mutati…` | x_testimony が Memory.ask の答えに witness_classes を足した（空の記録でも {} を返す）。 | verantyx/memory_frame.py:396 | changed_in 794ce88 | history/047_bad.txt, history/047_good.txt, runs/047.txt |
| 48 | テスト同士の矛盾 | B | `tests/attack/test_memory_merge_differential.py::test_canonical_order_and_exact_duplicate_r…` | fix_w_merge_2 は、置換記録が対応するポインタを持たない supersede 事件を「非有効」として出力から落とす（再オープンで権限が復活しないように）。 | verantyx/memory_merge.py:108 | 相手: tests/test_memory_merge.py::test_mismatched_supersede_stays_… | history/048_bad.txt, history/048_good.txt, probes/revert_9dbeea6.json, runs/048.txt |
| 49 | 期待値が古い | C | `tests/attack/test_memory_merge_fabrication.py::test_partial_supersession_link_stays_pendin…` | fix_w_merge_1 は「置換記録のポインタが一致する supersede だけが有効」へ変えた。 | verantyx/memory_merge.py:97 | changed_in 69b826b | history/049_bad.txt, history/049_good.txt, runs/049.txt |
| 50 | 判断が要る | B | `tests/attack/test_memory_merge_injection.py::test_instruction_payload_cannot_hide_a_dangli…` | 指示文つきの dangling supersede が、置換記録（ポインタ無し）がある場合に ValueError にならず黙って落とされる。 | verantyx/memory_merge.py:91, verantyx/memory_merge.py:108 | 決定が要る | history/050_bad.txt, history/050_good.txt, runs/050.txt |
| 51 | 判断が要る | B | `tests/attack/test_memory_merge_injection.py::test_instruction_text_does_not_make_a_superse…` | 互いを置換する 2 つの supersede（ポインタ無し）が、循環として拒否されず黙って落とされる。 | verantyx/memory_merge.py:91, verantyx/memory_merge.py:108 | 決定が要る | history/051_bad.txt, history/051_good.txt, runs/051.txt |
| 52 | 判断が要る | B | `tests/attack/test_memory_merge_limits.py::test_active_records_reject_dangling_supersession…` | ポインタの無い置換記録に対する、存在しない old への supersede が dangling として拒否されず黙って落とされる。 | verantyx/memory_merge.py:91, verantyx/memory_merge.py:108 | 決定が要る | history/052_bad.txt, history/052_good.txt, runs/052.txt |
| 53 | 期待値が古い | C | `tests/attack/test_memory_revalidate_injection.py::test_confusable_unknown_witness_kind_doe…` | fix_memory_frame（witness scope and validation）が、未知の種類の witness（ZWSP 付きの file_sha256 など）を持つ記録を ANSWER の根拠にしないよう変えた。 | verantyx/memory_frame.py:368 | changed_in 7b593d8 | history/053_bad.txt, history/053_good.txt, runs/053.txt |
| 54 | 期待値が古い | C | `tests/attack/test_memory_revalidate_injection.py::test_instruction_text_in_document_is_onl…` | fix_memory_frame は text_in_file witness の needle が、その記録の（実体・属性・値）を読める文として述べていることを要求する。 | verantyx/memory_frame.py:359 | changed_in 7b593d8 | history/054_bad.txt, history/054_good.txt, runs/054.txt |
| 55 | 製品の不具合 | D | `tests/attack/test_memory_revalidate_injection.py::test_matching_file_hash_keeps_only_the_g…` | RevalidatingMemory は鮮度確認で file_sha256 witness のファイルを読み、Memory._witness_supports（7b593d8 で追加）が同じファイルをもう一度読む。 | verantyx/memory_frame.py:366 | B04 | history/055_bad.txt, history/055_good.txt, runs/055.txt |
| 56 | 期待値が古い | C | `tests/attack/test_memory_revalidate_paraphrase.py::test_fresh_text_witness_keeps_its_recor…` | n=54 と同じ（fresh な text witness の needle が記録の主張を読める文で述べていない）。 | verantyx/memory_frame.py:359 | changed_in 7b593d8 | history/056_bad.txt, history/056_good.txt, runs/056.txt |
| 57 | 期待値が古い | C | `tests/attack/test_semantic_coord_negation_modality.py::test_adjectival_naku_then_te_is_str…` | fix_semantic_coord は、共有する話題（は）が無い て／で の連鎖に、次の節の名詞句を要求する（話題の無い連鎖で主語を誤って共有しない）。 | verantyx/semantic_coord.py:49 | changed_in 1b2e7a4 | history/057_bad.txt, history/057_good.txt, runs/057.txt |
| 58 | 期待値が古い | C | `tests/attack/test_semantic_coord_unicode_noise.py::test_te_comma_chain_is_accepted` | fix_semantic_coord は、共有する話題（は）が無い て／で の連鎖に、次の節の名詞句を要求する（話題の無い連鎖で主語を誤って共有しない）。 | verantyx/semantic_coord.py:49 | changed_in 1b2e7a4 | history/058_bad.txt, history/058_good.txt, runs/058.txt |
| 59 | 期待値が古い | D | `tests/attack/test_semantic_names_differential.py::test_generated_name_splits_match_indepen…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/059_bad.txt, history/059_good.txt, runs/059.txt |
| 60 | 判断が要る | C | `tests/attack/test_semantic_names_differential.py::test_name_split_accepts_kanji_title_appo…` | g_names_fix は、肩書き（descriptor）の中の接尾辞トークン（技+師（接尾辞）+ユン）を束縛形態素として拒否し、title+name の分割をしない。 | verantyx/semantic_names.py:40 | 決定が要る | history/060_bad.txt, history/060_good.txt, probes/e2e_names_suffix.txt, runs/060.txt |
| 61 | 期待値が古い | D | `tests/attack/test_semantic_names_fabrication.py::test_name_split_accepts_kanji_descriptor_…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/061_bad.txt, history/061_good.txt, runs/061.txt |
| 62 | 期待値が古い | D | `tests/attack/test_semantic_names_limits.py::test_concurrent_independent_readers_do_not_sha…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/062_bad.txt, history/062_good.txt, runs/062.txt |
| 63 | 期待値が古い | D | `tests/attack/test_semantic_names_limits.py::test_large_cover_and_pathological_long_nonkanj…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/063_bad.txt, history/063_good.txt, runs/063.txt |
| 64 | 判断が要る | C | `tests/attack/test_semantic_names_limits.py::test_name_split_accepts_kanji_title_and_one_pr…` | g_names_fix は、肩書き（descriptor）の中の接尾辞トークン（研究+員（接尾辞）+玲）を束縛形態素として拒否し、title+name の分割をしない。 | verantyx/semantic_names.py:40 | 決定が要る | history/064_bad.txt, history/064_good.txt, probes/e2e_names_suffix.txt, runs/064.txt |
| 65 | 期待値が古い | D | `tests/attack/test_semantic_names_limits.py::test_repeated_calls_are_idempotent_and_do_not_…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/065_bad.txt, history/065_good.txt, runs/065.txt |
| 66 | 期待値が古い | D | `tests/attack/test_semantic_names_long_documents.py::test_covering_selects_exact_span_from_…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/066_bad.txt, history/066_good.txt, runs/066.txt |
| 67 | 期待値が古い | D | `tests/attack/test_semantic_names_long_documents.py::test_name_split_accepts_multiple_kanji…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/067_bad.txt, history/067_good.txt, runs/067.txt |
| 68 | 期待値が古い | D | `tests/attack/test_semantic_names_long_documents.py::test_repeated_entities_and_conflicting…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/068_bad.txt, history/068_good.txt, runs/068.txt |
| 69 | 期待値が古い | D | `tests/attack/test_semantic_names_negation_modality.py::test_name_split_can_extract_exact_t…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/069_bad.txt, history/069_good.txt, runs/069.txt |
| 70 | 期待値が古い | D | `tests/attack/test_semantic_names_paraphrase.py::test_entity_swap_keeps_split_shape_and_ret…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/070_bad.txt, history/070_good.txt, runs/070.txt |
| 71 | 期待値が古い | D | `tests/attack/test_semantic_names_paraphrase.py::test_kanji_title_and_proper_name_split` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/071_bad.txt, history/071_good.txt, runs/071.txt |
| 72 | 期待値が古い | D | `tests/attack/test_semantic_names_paraphrase.py::test_particle_and_clause_surface_changes_l…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/072_bad.txt, history/072_good.txt, runs/072.txt |
| 73 | 判断が要る | C | `tests/attack/test_semantic_names_paraphrase.py::test_split_accepts_a_common_noun_followed_…` | g_names_fix は、肩書き（descriptor）の中の接尾辞トークン（研究+員（接尾辞）+ユン）を束縛形態素として拒否し、title+name の分割をしない。 | verantyx/semantic_names.py:40 | 決定が要る | history/073_bad.txt, history/073_good.txt, probes/e2e_names_suffix.txt, runs/073.txt |
| 74 | 期待値が古い | D | `tests/attack/test_semantic_names_realtext.py::test_name_split_accepts_kanji_title_and_one_…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/074_bad.txt, history/074_good.txt, runs/074.txt |
| 75 | 期待値が古い | D | `tests/attack/test_semantic_names_tense_time.py::test_name_split_accepts_a_kanji_title_befo…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/075_bad.txt, history/075_good.txt, runs/075.txt |
| 76 | 期待値が古い | D | `tests/attack/test_semantic_names_unicode_noise.py::test_name_split_accepts_kanji_title_plu…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/076_bad.txt, history/076_good.txt, runs/076.txt |
| 77 | 期待値が古い | D | `tests/attack/test_semantic_names_unicode_noise.py::test_name_split_preserves_decomposed_co…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/077_bad.txt, history/077_good.txt, runs/077.txt |
| 78 | 期待値が古い | D | `tests/attack/test_semantic_names_unicode_noise.py::test_name_split_preserves_fullwidth_nam…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/078_bad.txt, history/078_good.txt, runs/078.txt |
| 79 | 期待値が古い | D | `tests/attack/test_semantic_names_unicode_noise.py::test_name_split_preserves_markup_and_em…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/079_bad.txt, history/079_good.txt, runs/079.txt |
| 80 | 期待値が古い | D | `tests/attack/test_semantic_names_unicode_noise.py::test_tokens_covering_uses_python_codepo…` | g_names_fix が descriptor トークンを品詞細分類「普通名詞」に限定した（UniDic の 普通名詞。 | verantyx/semantic_names.py:40 | changed_in e481870 | history/080_bad.txt, history/080_good.txt, runs/080.txt |
| 81 | 期待値が古い | D | `tests/attack/test_semantic_reader_realtext.py::test_quantifier_scope_is_retained_as_unsupp…` | k_quantifier（quantifier 構文規則）が 「すべての鳥は飛ぶ。 | verantyx/constructions/quantifier.py:26 | changed_in d71e373 | history/081_bad.txt, history/081_good.txt, runs/081.txt |
| 82 | 製品の不具合 | B | `tests/attack/test_semantic_unknown_choice_paraphrase.py::test_query_delimiters_and_line_br…` | SemanticUnknownChoice の _JSONOptionResolver._prompt が、すでに JSON 化された語（_prompt_json の出力）のバックスラッシュをもう一度エスケープし、プロンプトの語が直列化した文字列と別物（\\n）になる。 | verantyx/semantic_unknown_choice.py:160 | B03 | history_patched.jsonl, runs/082.txt |
| 83 | 製品の不具合 | D | `tests/attack/test_semantic_unknown_differential.py::test_source_word_counts_toward_project…` | work 予算が vocabulary.runs()（非 ASCII の連なり）だけを source word として数え、docstring の「distinct source words」の ASCII 語を数えない。 | verantyx/semantic_unknown.py:270 | B05 | history/083_bad.txt, history/083_good.txt, runs/083.txt |
| 84 | 製品の不具合 | D | `tests/attack/test_semantic_unknown_fabrication.py::test_budget_below_clause_and_role_work_…` | n=83 と同じ原因。 | verantyx/semantic_unknown.py:270 | B05 | history/084_bad.txt, history/084_good.txt, runs/084.txt |
| 85 | 期待値が古い | C | `tests/attack/test_semantic_unknown_fabrication.py::test_constructed_neighbour_candidate_is…` | fix_w_unknown_1 は、clause を作った出典が同じ項を attest できないとし、独立した別の出典の 3 回の単独出現が無ければ older explain を棄権させる。 | verantyx/semantic_unknown.py:276, verantyx/semantic_unknown.py:280 | changed_in b29097a | history/085_bad.txt, history/085_good.txt, runs/085.txt |
| 86 | 期待値が古い | D | `tests/attack/test_semantic_unknown_injection.py::test_any_provenance_returned_for_hostile_…` | fix_w_unknown_1 が producer の出典に predicate の出典（clause.predicate_span）を使うようになった。 | verantyx/semantic_unknown.py:154 | changed_in b29097a | history/086_bad.txt, history/086_good.txt, runs/086.txt |
| 87 | 期待値が古い | D | `tests/attack/test_semantic_unknown_injection.py::test_document_instruction_cannot_expand_c…` | fix_w_unknown_1 が producer の出典に predicate の出典（clause.predicate_span）を使うようになった。 | verantyx/semantic_unknown.py:154 | changed_in b29097a | history/087_bad.txt, history/087_good.txt, runs/087.txt |
| 88 | 期待値が古い | D | `tests/attack/test_semantic_unknown_injection.py::test_question_instruction_does_not_count_…` | fix_w_unknown_1 が producer の出典に predicate の出典（clause.predicate_span）を使うようになった。 | verantyx/semantic_unknown.py:154 | changed_in b29097a | history/088_bad.txt, history/088_good.txt, runs/088.txt |
| 89 | 期待値が古い | D | `tests/attack/test_semantic_unknown_injection.py::test_quoted_nested_agent_message_remains_…` | fix_w_unknown_1 が producer の出典に predicate の出典（clause.predicate_span）を使うようになった。 | verantyx/semantic_unknown.py:154 | changed_in b29097a | history/089_bad.txt, history/089_good.txt, runs/089.txt |
| 90 | 期待値が古い | D | `tests/attack/test_semantic_unknown_injection.py::test_repeated_attacks_are_deterministic_a…` | fix_w_unknown_1 が producer の出典に predicate の出典（clause.predicate_span）を使うようになった。 | verantyx/semantic_unknown.py:154 | changed_in b29097a | history/090_bad.txt, history/090_good.txt, runs/090.txt |
| 91 | 期待値が古い | D | `tests/attack/test_semantic_unknown_injection.py::test_unicode_instruction_variants_do_not_…` | fix_w_unknown_1 が producer の出典に predicate の出典（clause.predicate_span）を使うようになった。 | verantyx/semantic_unknown.py:154 | changed_in b29097a | history/091_bad.txt, history/091_good.txt, runs/091.txt |
| 92 | 期待値が古い | D | `tests/attack/test_semantic_unknown_limits.py::test_clause_and_role_order_do_not_change_rep…` | fix_w_unknown_1 が producer の出典に predicate の出典（clause.predicate_span）を使うようになった。 | verantyx/semantic_unknown.py:154 | changed_in b29097a | history/092_bad.txt, history/092_good.txt, runs/092.txt |
| 93 | 期待値が古い | D | `tests/attack/test_semantic_unknown_limits.py::test_constructed_outputs_are_typed_and_never…` | fix_w_unknown_1 が producer の出典に predicate の出典（clause.predicate_span）を使うようになった。 | verantyx/semantic_unknown.py:154 | changed_in b29097a | history/093_bad.txt, history/093_good.txt, runs/093.txt |
| 94 | 期待値が古い | D | `tests/attack/test_semantic_unknown_limits.py::test_exact_projection_budget_is_not_refused` | ClauseStub に predicate_span が無く、fix_w_unknown_1（predicate の出典も producer として数える）が clause.predicate_span を読んで AttributeError。 | verantyx/semantic_unknown.py:154 | changed_in b29097a | history/094_bad.txt, history/094_good.txt, runs/094.txt |
| 95 | 期待値が古い | D | `tests/attack/test_semantic_unknown_limits.py::test_repeated_calls_are_idempotent` | fix_w_unknown_1 が producer の出典に predicate の出典（clause.predicate_span）を使うようになった。 | verantyx/semantic_unknown.py:154 | changed_in b29097a | history/095_bad.txt, history/095_good.txt, runs/095.txt |
| 96 | 期待値が古い | D | `tests/attack/test_semantic_unknown_limits.py::test_two_concurrent_readers_return_the_same_…` | fix_w_unknown_1 が producer の出典に predicate の出典（clause.predicate_span）を使うようになった。 | verantyx/semantic_unknown.py:154 | changed_in b29097a | history/096_bad.txt, history/096_good.txt, runs/096.txt |
| 97 | 期待値が古い | C | `tests/attack/test_semantic_unknown_paraphrase.py::test_changed_compound_meaning_changes_th…` | n=85 と同じ（出典が 1 つの View は独立な attestation が無く、older explain が棄権して NO_REACH になる）。 | verantyx/semantic_unknown.py:276, verantyx/semantic_unknown.py:280 | changed_in b29097a | history/097_bad.txt, history/097_good.txt, runs/097.txt |
| 98 | 期待値が古い | C | `tests/attack/test_semantic_unknown_paraphrase.py::test_entity_swap_changes_the_available_n…` | n=85 と同じ（出典が 1 つの View は独立な attestation が無く、older explain が棄権して NO_REACH になる）。 | verantyx/semantic_unknown.py:276, verantyx/semantic_unknown.py:280 | changed_in b29097a | history/098_bad.txt, history/098_good.txt, runs/098.txt |
| 99 | 期待値が古い | C | `tests/attack/test_semantic_verify_negation_modality.py::test_double_negation_is_not_licens…` | fix_semantic_reader が二重否定を「unsupported double negation」の Unread として読む（節を作らない）。 | verantyx/semantic_reader.py:31 | changed_in 4af1231 | history/099_bad.txt, history/099_good.txt, runs/099.txt |
| 100 | 期待値が古い | D | `tests/attack/test_semantic_verify_negation_modality.py::test_hearsay_clause_is_not_license…` | fix_semantic_reader が伝聞（〜そうだ）を modality=hedge に型付けする。 | verantyx/semantic_reader.py:27 | changed_in 4af1231 | history/100_bad.txt, history/100_good.txt, runs/100.txt |
| 101 | 判断が要る | C | `tests/attack/test_semantic_verify_unicode_noise.py::test_symbolic_record_licenses_unicode_…` | fix_semantic_verify は symbolic 記録の実体・述語が「NFKC で不変な英数字と _ だけ」の原子であることを要求する（互換文字に隠した指示を許さない）。 | verantyx/semantic_verify.py:274, verantyx/semantic_verify.py:417 | 決定が要る | history/101_bad.txt, history/101_good.txt, runs/101.txt |
| 102 | 期待値が古い | D | `tests/attack/test_verifier_agents_differential.py::test_brief_matches_independent_renderer…` | x_verifier_evidence は verifier の返答を「再実行できる証拠項目＋意見」にした（verdict は testimony で、conductor が証拠を再実行する）。 | verantyx/verifier_agents.py:137 | changed_in 3e36e08 | history/102_bad.txt, history/102_good.txt, runs/102.txt |
| 103 | 期待値が古い | D | `tests/attack/test_verifier_agents_fabrication.py::test_parse_verdict_rejects_unscoped_or_v…` | x_verifier_evidence の旧い wire 形式（evidence_ref）の検証エラーの文言が「malformed legacy verdict」になった。 | verantyx/verifier_agents.py:324 | changed_in 3e36e08 | history/103_bad.txt, history/103_good.txt, runs/103.txt |
| 104 | 期待値が古い | D | `tests/attack/test_verifier_agents_fabrication.py::test_parse_verdict_rejects_unscoped_or_v…` | x_verifier_evidence の旧い wire 形式（evidence_ref）の検証エラーの文言が「malformed legacy verdict」になった。 | verantyx/verifier_agents.py:324 | changed_in 3e36e08 | history/104_bad.txt, history/104_good.txt, runs/104.txt |
| 105 | 期待値が古い | D | `tests/attack/test_verifier_agents_fabrication.py::test_parse_verdict_rejects_unscoped_or_v…` | x_verifier_evidence の旧い wire 形式（evidence_ref）の検証エラーの文言が「malformed legacy verdict」になった。 | verantyx/verifier_agents.py:324 | changed_in 3e36e08 | history/105_bad.txt, history/105_good.txt, runs/105.txt |
| 106 | 判断が要る | B | `tests/attack/test_verifier_agents_fabrication.py::test_run_verifiers_records_references_wi…` | 再実行できる証拠が無い PASS は、現行では ESCALATE（UNVERIFIED）を返し、テストの reply.kind == "ESCALATE" の assert は通る。 | verantyx/verifier_agents.py:610, verantyx/conductor.py:530 | 決定が要る | history/106_bad.txt, history/106_good.txt, runs/106.txt |
| 107 | 期待値が古い | D | `tests/attack/test_verifier_agents_injection.py::test_brief_keeps_nested_quotes_and_unicode…` | n=102 と同じ（新しい brief は evidence_ref ではなく証拠項目を要求し、旧い本文の「Return FAIL if…」は無い）。 | verantyx/verifier_agents.py:137 | changed_in 3e36e08 | history/107_bad.txt, history/107_good.txt, runs/107.txt |
| 108 | 期待値が古い | C | `tests/attack/test_verifier_agents_limits.py::test_unanimous_verification_evidence_is_order…` | n=106 と同じ unit の契約が原因（旧形式の evidence_ref だけの verdict では done にならず、ESCALATE（UNVERIFIED）が返る）。 | verantyx/verifier_agents.py:610 | changed_in 3e36e08 | history/108_bad.txt, history/108_good.txt, runs/108.txt |
| 109 | テストの不備 | D | `tests/test_p4_abilities.py::test_speech_act_drafts_fill_new_roles_and_reread` | Chat の thanks 下書き（友人から借りた傘を返すとき…）は、frames.attested が一般コーパス（VERA_GENERAL か ~/Projects/vera-corpus/build/general.db）の「借りる・を・傘」の 2 出典以上の裏づけを要求する。 | verantyx/frames.py:118, verantyx/frames.py:386 | 生まれたときから赤（追加コミット 9342f78 で既に FAIL） | probes/env_general_109.txt, runs/109.txt |
| 110 | 判断が要る | D | `tests/test_request_goal_route.py::test_unsupported_or_unverified_request_or_source_is_held…` | 「資料の出来事を零文以内で言い換えてください。 | verantyx/compositional_goal.py:1128 | 決定が要る | runs/110.txt |
| 111 | 製品の不具合 | C | `tests/test_semantic_coordination_codex.py::test_concessive_main_clause_keeps_the_topic_sub…` | 「ユラは疲れていたのに、箱をナオに預けた。 | verantyx/semantic_reader.py:99 | B01 | history/111_bad.txt, history/111_good.txt, runs/111.txt |
| 112 | 期待値が古い | C | `tests/test_semantic_coordination_codex.py::test_plain_predicate_coordination_answers_claus…` | fix_semantic_reader は、で の句が場所の語（閉じた名詞リスト・語尾）で決まらないと role=ambiguous（case:で:place\|means）にして推測しない。 | verantyx/semantic_reader.py:121 | changed_in 4af1231 | history/112_bad.txt, history/112_good.txt, runs/112.txt |
| 113 | 製品の不具合 | B | `tests/test_semantic_measure.py::test_kanji_title_before_a_name_is_split[\u30df\u30ca\u306f…` | 「倉庫Cから技師ユンへ運んだ」で、frame の recipient「ユン」（肩書き分割後）と case 読みの direction「技師ユン」が同じ語を二重に読み（_case_roles が重なる span を除外しない）、質問側は 誰へ を direction で問う。 | verantyx/semantic_reader.py:177, verantyx/semantic_reader.py:745 | B02 | history/113_bad.txt, history/113_good.txt, runs/113.txt |
| 114 | 判断が要る | C | `tests/test_semantic_measure.py::test_role_only_questions_generalize[\u30d2\u30ed\u306f\u83…` | fix_semantic_reader（で→place、から→source…と明示）は reader の出す役割名を変えたが、役割だけの問い（semantic_wh.py:15-16 の で→location・から→origin・起点→origin）と realize（semantic_realize.py:34）は旧い語彙のまま。 | verantyx/semantic_wh.py:15, verantyx/semantic_wh.py:16, verantyx/semantic_reader.py:128 | 決定が要る | history/114_bad.txt, history/114_good.txt, probes/combo_vocab_A_consumers_new.json, probes/combo_vocab_B_reader_old.json, runs/114.txt |
| 115 | 判断が要る | C | `tests/test_semantic_measure.py::test_role_only_questions_generalize[\u30d2\u30ed\u306f\u83…` | fix_semantic_reader（で→place、から→source…と明示）は reader の出す役割名を変えたが、役割だけの問い（semantic_wh.py:15-16 の で→location・から→origin・起点→origin）と realize（semantic_realize.py:34）は旧い語彙のまま。 | verantyx/semantic_wh.py:15, verantyx/semantic_wh.py:16, verantyx/semantic_reader.py:177 | 決定が要る | history/115_bad.txt, history/115_good.txt, probes/combo_vocab_B_reader_old.json, runs/115.txt |
| 116 | 判断が要る | C | `tests/test_semantic_measure.py::test_role_only_questions_generalize[\u30d2\u30ed\u306f\u83…` | fix_semantic_reader（で→place、から→source…と明示）は reader の出す役割名を変えたが、役割だけの問い（semantic_wh.py:15-16 の で→location・から→origin・起点→origin）と realize（semantic_realize.py:34）は旧い語彙のまま。 | verantyx/semantic_wh.py:15, verantyx/semantic_wh.py:16, verantyx/semantic_reader.py:177 | 決定が要る | history/116_bad.txt, history/116_good.txt, probes/combo_vocab_B_reader_old.json, runs/116.txt |
| 117 | 製品の不具合 | B | `tests/test_semantic_measure.py::test_role_only_questions_generalize[\u30d2\u30ed\u306f\u83…` | 「ヒロは荷物を駅Bから店長サキへ届けた。 | verantyx/semantic_reader.py:177, verantyx/semantic_reader.py:745 | B02 | history/117_bad.txt, history/117_good.txt, runs/117.txt |
| 118 | 判断が要る | C | `tests/test_semantic_measure.py::test_role_only_questions_generalize[\u30df\u30ca\u306f\u97…` | fix_semantic_reader（で→place、から→source…と明示）は reader の出す役割名を変えたが、役割だけの問い（semantic_wh.py:15-16 の で→location・から→origin・起点→origin）と realize（semantic_realize.py:34）は旧い語彙のまま。 | verantyx/semantic_wh.py:15, verantyx/semantic_wh.py:16, verantyx/semantic_reader.py:128 | 決定が要る | history/118_bad.txt, history/118_good.txt, probes/combo_vocab_A_consumers_new.json, probes/combo_vocab_B_reader_old.json, runs/118.txt |
| 119 | 判断が要る | C | `tests/test_semantic_measure.py::test_role_only_questions_generalize[\u30df\u30ca\u306f\u97…` | fix_semantic_reader（で→place、から→source…と明示）は reader の出す役割名を変えたが、役割だけの問い（semantic_wh.py:15-16 の で→location・から→origin・起点→origin）と realize（semantic_realize.py:34）は旧い語彙のまま。 | verantyx/semantic_wh.py:15, verantyx/semantic_wh.py:16, verantyx/semantic_reader.py:128 | 決定が要る | history/119_bad.txt, history/119_good.txt, probes/combo_vocab_A_consumers_new.json, probes/combo_vocab_B_reader_old.json, runs/119.txt |
| 120 | 判断が要る | C | `tests/test_semantic_measure.py::test_role_only_questions_generalize[\u30df\u30ca\u306f\u97…` | fix_semantic_reader（で→place、から→source…と明示）は reader の出す役割名を変えたが、役割だけの問い（semantic_wh.py:15-16 の で→location・から→origin・起点→origin）と realize（semantic_realize.py:34）は旧い語彙のまま。 | verantyx/semantic_wh.py:15, verantyx/semantic_wh.py:16, verantyx/semantic_reader.py:128 | 決定が要る | history/120_bad.txt, history/120_good.txt, probes/combo_vocab_A_consumers_new.json, probes/combo_vocab_B_reader_old.json, runs/120.txt |
| 121 | 期待値が古い | D | `tests/test_semantic_public.py::test_unhandled_wh_is_not_yes_no_and_location_is_required` | fix_semantic_reader は、で の句が場所の語で決まらないと ambiguous にする。 | verantyx/semantic_reader.py:121 | changed_in 4af1231 | history/121_bad.txt, history/121_good.txt, runs/121.txt |
| 122 | 判断が要る | D | `tests/test_semantic_realize.py::test_reader_case_roles_are_preserved[\u30de\u30ad\u306f\u5…` | fix_semantic_reader（で→place、から→source…と明示）は reader の出す役割名を変えたが、役割だけの問い（semantic_wh.py:15-16 の で→location・から→origin・起点→origin）と realize（semantic_realize.py:34）は旧い語彙のまま。 | verantyx/semantic_reader.py:128 | 決定が要る | history/122_bad.txt, history/122_good.txt, probes/combo_vocab_B_reader_old.json, runs/122.txt |
| 123 | 判断が要る | D | `tests/test_semantic_realize.py::test_reader_case_roles_are_preserved[\u30de\u30ad\u306f\u5…` | fix_semantic_reader（で→place、から→source…と明示）は reader の出す役割名を変えたが、役割だけの問い（semantic_wh.py:15-16 の で→location・から→origin・起点→origin）と realize（semantic_realize.py:34）は旧い語彙のまま。 | verantyx/semantic_reader.py:118 | 決定が要る | history/123_bad.txt, history/123_good.txt, probes/combo_vocab_B_reader_old.json, runs/123.txt |
| 124 | 期待値が古い | D | `tests/test_semantic_scope_safety.py::test_unrepresented_request_content_never_becomes_a_ye…` | fix_semantic_reader は から を source 役割として読む（意図に明示）。 | verantyx/semantic_reader.py:128 | changed_in 4af1231 | history/124_bad.txt, history/124_good.txt, runs/124.txt |
<!-- w1f:end:table -->

## 4. 製品の不具合の束

束は「原因の箇所（`075d486` の `path:行`）」ごと。束 B02 の 2 件（n=113・n=117）は、どちらも :177（文書側の二重読み）を直さないと通らないので 1 束にした。n=113 はさらに :745（質問側の 誰へ の役割）も要る（`cause_also`）。n=117 は :177 だけで通る。片側ずつの測定は下の表（`fixes/B02_only177.json`・`fixes/B02_only745.json`）。束の害は、含まれるテストの最も重い害（`triage.jsonl` の harm）から `report` が機械的に決める。F2 は、束の 1 件について、ツリーの外の複写に製品側だけの最小差分（`fixes/B0N.diff`）を当て、直す前 FAIL・直した後 PASS を示し、全体を走らせて新規失敗を単独で再確認した結果（`fixes/B0N.json`／`.txt`）。

<!-- w1f:begin:bundles -->
| 束 | 原因の箇所 | 束のテスト | 害 | 原則 | F2（直す前→後） | 全体での新規失敗（単独で確認） | 新規通過 |
|---|---|---:|---|---|---|---|---:|
| B01 | verantyx/semantic_reader.py:99 | 1 | C | 分からないことと偽であることを混ぜない（助詞だけの句を名詞句として読まない） | PASS（FAIL→PASS、`fixes/B01.diff`） | 0 件 | 1 |
| B02 | verantyx/semantic_reader.py:177 ＋ verantyx/semantic_reader.py:745 | 2 | B | 束ねず重ねる／分からないことと偽を混ぜない（同じ span を 2 つの役割で読まない。質問側と文書側が同じ語に同じ役割を使う） | PASS（FAIL→PASS、`fixes/B02.diff`） | 0 件 | 2 |
| B03 | verantyx/semantic_unknown_choice.py:160 | 1 | B | データと指示を分ける（untrusted な語は型付きデータとして逐語で渡し、二重加工して別の文字列に変えない） | PASS（FAIL→PASS、`fixes/B03.diff`） | 0 件 | 1 |
| B04 | verantyx/memory_frame.py:366 | 1 | D | 入力を変えない・繰り返しても同じ（1 回の問いで同じ witness を 2 回読み、状態と支持判定が別の読みに基づきうる） | PASS（FAIL→PASS、`fixes/B04.diff`） | 0 件 | 1 |
| B05 | verantyx/semantic_unknown.py:270 | 2 | D | 分からないことと偽を混ぜない／上限を超える入力は型付きの BUDGET_REFUSAL で返す（文書化された作業上限を守る） | PASS（FAIL→PASS、`fixes/B05.diff`） | 0 件 | 2 |
<!-- w1f:end:bundles -->

束 B02 の差分を hunk ごとに分けて測った結果（束の切り方の根拠。`fixes/B02_only177.json`・`fixes/B02_only745.json`）:

<!-- w1f:begin:bundle_parts -->
| 束 | 差分の一部 | 触る行 | 束のテストごとの結果（その一部だけを 075d486 に当てた複写） |
|---|---|---|---|
| B02 | only177（`fixes/B02_only177.diff`） | verantyx/semantic_reader.py | n=113 `test_kanji_title_before_a_name_is_split` = FAIL；n=117 `test_role_only_questions_generalize` = PASS |
| B02 | only745（`fixes/B02_only745.diff`） | verantyx/semantic_reader.py | n=113 `test_kanji_title_before_a_name_is_split` = FAIL；n=117 `test_role_only_questions_generalize` = FAIL |
| B02 | 両方（`fixes/B02.diff`） | 全部 | n=113 `test_kanji_title_before_a_name_is_split` = PASS；n=117 `test_role_only_questions_generalize` = PASS |
<!-- w1f:end:bundle_parts -->

各束の突いている原則（定義は 11 節）:

- B01: 分からないことと偽であることを混ぜない（助詞だけの句を名詞句として読み、節全体を unsupported にする）。
- B02: 束ねず重ねる／分からないことと偽を混ぜない（同じ語を 2 つの役割で読む。INVALID_PROOF という誤った型で返る）。
- B03: データと指示を分ける（untrusted な語をモデルに見せる形が、直列化した文字列と別物になる）。
- B04: 入力を変えない・繰り返しても同じ（1 回の問いで同じファイルを 2 回読み、状態と支持判定が別の読みに基づきうる）。
- B05: 文書化された作業上限を守る（上限を超える入力が BUDGET_REFUSAL にならない）。
- 攻撃テスト（`tests/attack/`）の突いている原則は、各行の `principle`（`triage.jsonl`）に書いた。

## 5. 期待値が古い

内訳は 10 節の「古くなったテストの更新」の下書きと同じ単位。証拠の強さを区別して書く。

- adapter で通ったもの（期待値に触れない入力・形の変更）: memory_brief、semantic_names のタグ、semantic_unknown の stub、conductor の二重化、memory_frame の追加鍵、memory_merge のポインタ、witness の文。差分は `probes/adapt_*.diff`、全 hunk が `tests/` 配下であること・通る件数・新規失敗が 0 であることは `probes/adapt_*.json`。
- memory_brief は adapter を 4 段（L1 型の取り出し、L2 ＋二重化に verdict、L3 ＋行の注記、L4 ＋旧い文字数勘定）に分け、テストごとに最小の段を `decisions.jsonl` の `adapt_probe` に書いた。**一括で同じ分類にしていない**: 型だけで通るものと、注記・予算勘定まで必要なものを分けた。ただし、`ask_about` の答えに `verdict` が無い二重化が落ちる原因は、unit の指示文には書かれていない（`fix_w_brief_1` の指示は型付きの context-only 結果）。unit 自身の `StubMemory`（`tests/test_memory_brief.py`）は最初から `verdict` を返すので、二重化が公開契約を満たしていないと判断したが、これは判断であり、既知の穴に書いた。
- revert probe と意図の引用で裏づけたもの（形だけの adapter が作れない）: `adapt_note` に理由を書いた。revert probe の「部分」は `git apply -R --reject`（当たる hunk だけ）で、unit の完全な取り消しではない。

<!-- w1f:begin:probes -->
| コミット | unit | 逆適用 | 本人が通った基線の失敗 | 新規失敗（単独で確認） |
|---|---|---|---:|---:|
| 068ce78 | unit fix_w_escalate_1 | PARTIAL_REJECT（1/3 hunk が当たらず） | 0 | 34 |
| 1b2e7a4 | unit fix_semantic_coord | OK | 2 | 0 |
| 38a9118 | unit finish_semantic_unknown | OK | 1 | 0 |
| 3e36e08 | unit x_verifier_evidence | PARTIAL_REJECT（1/11 hunk が当たらず） | 5 | 24 |
| 4af1231 | unit fix_semantic_reader | PARTIAL_REJECT（6/9 hunk が当たらず） | 2 | 0 |
| 69b826b | unit fix_w_merge_1 | PARTIAL_REJECT（2/4 hunk が当たらず） | 0 | 0 |
| 794ce88 | unit x_testimony | OK | 1 | 0 |
| 7b593d8 | unit fix_memory_frame | PARTIAL_REJECT（2/9 hunk が当たらず） | 0 | 63 |
| 8e396b7 | unit fix_w_escalate_2 | OK | 1 | 1 |
| 9dbeea6 | unit fix_w_merge_2 | OK | 1 | 1 |
| a9cad0a | unit fix_w_brief_1 | OK | 44 | 53 |
| b29097a | unit fix_w_unknown_1 | OK | 14 | 3 |
| bd5dfba | unit fix_semantic_verify | PARTIAL_REJECT（1/15 hunk が当たらず） | 1 | 0 |
| d71e373 | unit k_quantifier | OK | 1 | 0 |
| e481870 | unit g_names_fix | OK | 22 | 0 |

| adapter | tests/ 以外に触れない | 通る基線の失敗 | 残る | 新規失敗 |
|---|---|---:|---:|---:|
| brief_L1 | True | 12 | 112 | 0 |
| brief_L2 | True | 12 | 112 | 0 |
| brief_L3 | True | 32 | 92 | 0 |
| brief_L4 | True | 44 | 80 | 0 |
| cond | True | 2 | 122 | 0 |
| merge49 | True | 1 | 123 | 0 |
| names | True | 19 | 105 | 0 |
| revalidate | True | 2 | 122 | 0 |
| ustub | True | 11 | 113 | 0 |
| wc | True | 1 | 123 | 0 |

| 比較 | 通るようになった基線の失敗 | 新規失敗（単独で確認） |
|---|---:|---:|
| unknown_budget | 1 | 1 |
| vocab_A_consumers_new | 4 | 24 |
| vocab_B_reader_old | 6 | 0 |
<!-- w1f:end:probes -->

## 6. テスト同士の矛盾

該当は分類表の「テスト同士の矛盾」の行: `test_canonical_order_and_exact_duplicate_removal`（攻撃テスト）と `tests/test_memory_merge.py::test_mismatched_supersede_stays_nonoperative_after_serialize_and_reopen`（unit のテスト）。`9dbeea6` を戻すと前者が通り後者が落ちる（`probes/revert_9dbeea6.json`、本人が `newly_passing`、相手が `newly_failing_confirmed`）。`fix_w_merge_2` のレビュー指摘は「事件を除くか、非有効として符号化するか、`Memory._apply` でポインタを検証するか」の複数案を許しており、どれかを決めるのが 8 節の決定 3。

別の候補だった `test_budget_below_clause_and_role_work_floor_refuses`（`+1` の復活を要する）と `test_exact_projection_budget_is_not_refused` の矛盾は、`probes/combo_unknown_budget.json` で一度は確認した（`38a9118` を戻すと 2 つ目が落ちる）が、B05（語を数える）で両方が通る（`fixes/B05.json`）ので、矛盾ではなく製品の不具合として分類した。この比較は却下した仮説の記録として残した。

## 7. テストの不備

該当は `test_speech_act_drafts_fill_new_roles_and_reread`。Chat の thanks 下書きが、一般コーパス（`VERA_GENERAL` か `~/Projects/vera-corpus/build/general.db`）の「借りる・を・傘」に複数の出典があること（`frames.attested`）を要求し、このマシンにコーパスは無い。最小の sqlite を `VERA_GENERAL` で渡すと通る（`probes/env_general_109.txt`）。依存が `needs_resource` で宣言されていない。追加時（`9342f78`）から赤だった。

## 8. 判断が要る（何を決めればよいか）

1. **役割の語彙**（`location`/`origin` か `place`/`source`/`limit` か）。reader を旧い語彙へ戻す複写は新規失敗なしで一部が通り、consumer を新しい語彙へ寄せる複写は一部が通るが wh の攻撃テストが新たに落ちる（件数は `probes/combo_vocab_*.json` と上の probes の表）。どちらが契約かは原則から決まらない。reader の unit の指示（から→source など）は明示的、consumer と大半のテストは旧い語彙。qf2 を取り込む前提。
2. **非有効な supersede 事件の扱い**（構造検査をするか、型付きで保持して件数を報告するか、黙って落とすか）。 どの選択でも、落とした事件の件数の会計は必要（原則 P5）。黙って落としていること自体が、決定に関係なく原則に反する。
3. **supersede 事件を merge 出力に残すか**（6 節）。
4. **肩書きの中の接尾辞**（研究員＝研究＋員）で title+name を分割するか。実際のタガーは研究員ユンを 研究＋員（接尾辞）＋ユン に切る。現状は肩書きを分けず全体を 1 語として答える（`probes/e2e_names_suffix.txt`）。
5. **symbolic record の原子に許す文字**（NFKC 不変の英数字＋`_`か、Unicode を逐語で許すか）。
6. **零文以内の拘束**（零を数詞として読むか、未読の span として HOLD にするか）。
7. **再実行できる証拠が無いときの VERIFICATION 記録の値**（n=106）。`verifier_agents.py:610` は UNVERIFIED（ESCALATE）を返すが、記録の result を `FAIL` にする（`conductor.record_verification` は PASS／FAIL しか受けない: `conductor.py:530`）。UNVERIFIED を記録の型として足すか、記録しないか、FAIL のまま文書化するか。テストの期待（PASS）は新しい契約では正しくなく、現行の記録（FAIL）は UNVERIFIED と FAIL を混ぜるので、「期待値が古い」にはしなかった。同じ unit の n=108 は、assert が `result.answer == "done"` で止まり記録の値を見ていないので、この決定に依存しない（`期待値が古い` のまま）。

各件の理由と、決めた後に変えるファイルは 10 節の下書き。

## 9. `w_question_forms2`（F3）

### 9.1 衝突するテストの原因（件数は下の表と `qf2/ids.txt`）

`9c89f1e` の `semantic_wh.py` は 1 つの hunk（ほぼ全面書き換え。`git diff 075d486 9c89f1e -- verantyx/semantic_wh.py`）で、hunk 単位の切り分けが退化するため、機能を 1 つずつ親（`498f3c3`）の受理範囲に戻した版（`qf2/ablation.json`。3 つの因子の 2^3−1 通りの組合せ）で原因を分けた。因子は 3 つ:

1. **role_vocabulary（V）**: 役割名が変わる（で＋どこ→place、から→source、起点→source、終点→limit、へ＋どこ→direction）。攻撃テストは旧い名前（location・origin・recipient）を固定している。8 節の決定 1 に従属。
2. **clause_forms（C）**: 新しい節単位の wh 問い（`_clause_wh_question`）が role-only の問いより先に呼ばれ、同じ問いに別の計画を返す。**害は計画の形にとどまらない**: 時制が合わない問い（`ミオは本を読む。`／`誰が本を読んだ？`）に `Vera.ask` が `ANSWER ["ミオ"]` を返す（dev では `UNKNOWN_NO_EVIDENCE`）。対立する主張（`太郎は花子を見た。太郎は花子を見なかった。`／`何が花子を見た？`）では `Checker.audit` が Conflict を出さずに答えを返す。完全な答えの提案を `Checker.proof` が `Rejected` にする。いずれも下の表の「dev の出力」「dev+qf2 の出力」と失敗の 1 行目に出ている。
3. **wh_particle_pairs（P）**: role-only の問いで `_requested_role` が wh＋助詞の組（何に・何へ・誰で・何で・どこを…）を None にする、または後から拒否される役割（means・limit・companion）を返し、問いが読まれなくなる。旧い実装は助詞だけで役割を決め、任意の組を受理した。

<!-- w1f:begin:qf2 -->
- dev（`075d486`）に `9c89f1e` の `semantic_wh.py`・`tools/demo_question_forms.py` を重ねた複写の全体実行: 155 failed, 3653 passed, 28 skipped, 83 xfailed, 67 xpassed, 37 subtests passed
- 基線に無い新規失敗: **34 件**（`qf2/ids.txt`）、基線の失敗のうち通るようになるもの: **3 件**（`qf2/fixed_ids.txt`）
- 親 `498f3c3` で通り自身 `9c89f1e` で落ちる: **34 / 34 件**（`qf2/own_commit.json`）
- 構文規則 26 個をすべて外し（`VERA_CONSTRUCTIONS_OFF`）ても落ちる: **34 / 34 件**（`qf2/constructions_off.json`）
- 機能を親に戻した版（`qf2/ablation.json`。V = 役割の語彙、C = clause 形、P = wh＋助詞の組）で通る件数: all_three_restored［V＋C＋P］ = 34、no_clause_forms［C］ = 6、old_role_vocabulary［V］ = 20、old_role_vocabulary_no_clause_forms［V＋C］ = 26、parent_wh_particle_pairs［P］ = 4、parent_wh_particle_pairs_no_clause_forms［C＋P］ = 10、parent_wh_particle_pairs_old_role_vocabulary［V＋P］ = 28
- 失敗の 1 行目（`qf2/own_commit_errors.jsonl`。dev + 9c89f1e の複写で 1 件ずつ実行）から規則（`QF2_HARM_RULES`）で決めた害の段: A = 3、B = 0、C = 16、D = 15

| 機構（親に戻すと通る因子の組） | 主な原因の箇所（9c89f1e:verantyx/semantic_wh.py:行） | 件数 |
|---|---|---:|
| role_vocabulary | 9 | 12 |
| clause_forms | 170 | 6 |
| role_vocabulary | 89 | 6 |
| wh_particle_pairs | 83 | 2 |
| role_vocabulary＋wh_particle_pairs | 93 | 2 |
| role_vocabulary | 93 | 2 |
| wh_particle_pairs | 101 | 1 |
| role_vocabulary＋wh_particle_pairs | 71 | 1 |
| role_vocabulary＋wh_particle_pairs | 89 | 1 |
| wh_particle_pairs | 91 | 1 |

実行で確かめた原因の行（`qf2/repro.jsonl` の `cause_trace`。clause_forms = 親に無い呼び出しの行、wh_particle_pairs／role_vocabulary = `_requested_role` の実行行（`sys.settrace` で記録）または `_ROLE_NOUN` の差）:

| 因子 | 行 | そこに当たったテスト数 |
|---|---:|---:|
| clause_forms | 170 | 6 |
| role_vocabulary | 9 | 12 |
| role_vocabulary | 85 | 1 |
| role_vocabulary | 89 | 7 |
| role_vocabulary | 93 | 5 |
| wh_particle_pairs | 71 | 1 |
| wh_particle_pairs | 83 | 3 |
| wh_particle_pairs | 91 | 1 |
| wh_particle_pairs | 101 | 3 |

原因の行が未特定のテスト: 0 件

| テスト（nodeid） | 機構 | 原因の箇所（実行した行） | 問い | 文書 | dev の出力 | dev+qf2 の出力 | 失敗の 1 行目（dev+qf2）| 害 |
|---|---|---|---|---|---|---|---|---|
| `tests/attack/test_semantic_reader_paraphrase.py::test_direct_who_question_binds_…` | clause_forms | 170 | 誰が箱を運びましたか？ | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | read_request: [[('Bind', '運ぶ', ['patient', 'agent'])]] | read_request: [[('Bind', '*', ['patient', 'agent']), ('Bind', '運ぶ', [])]] | E   AssertionError: assert 2 == 1 | D |
| `tests/attack/test_semantic_verify_fabrication.py::test_gate_accepts_a_complete_r…` | clause_forms | 170 | 何が花子を見た？ | 太郎は花子を見た。 | Checker.audit: returns {(('agent', '太郎'),)} | Checker.audit: returns {(('何', '太郎'),)} | E   verantyx.semantic_verify.Rejected: producer binding/coverage/answer differs  | C |
| `tests/attack/test_semantic_verify_fabrication.py::test_replayed_proof_returns_th…` | clause_forms | 170 | 何が花子を見た？ | 太郎は花子を見た。 | Checker.proof: returns (('agent', '太郎'),) | Checker.proof: raises Rejected producer binding/coverage/answer differs from repl | E   verantyx.semantic_verify.Rejected: producer binding/coverage/answer differs  | C |
| `tests/attack/test_semantic_verify_fabrication.py::test_unresolved_opposing_claim…` | clause_forms | 170 | 何が花子を見た？ | 太郎は花子を見た。太郎は花子を見なかった。 | Checker.audit: raises Conflict applicable opponent outside proof | Checker.audit: returns {(('何', '太郎'),)} | E   Failed: DID NOT RAISE Conflict | A |
| `tests/attack/test_semantic_wh_differential.py::test_all_surface_words_and_case_p…` | role_vocabulary＋wh_particle_pairs | 83、89 | だれはどこで | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | projected ['agent', 'location'] | projected ['agent', 'place'] | E   AssertionError: assert (('agent', 'v0'), ('place', 'v1')) == (('agent', 'v0' | D |
| `tests/attack/test_semantic_wh_differential.py::test_generated_wh_case_sequences_…` | role_vocabulary＋wh_particle_pairs | 71、85 | 誰がどこを | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | projected ['agent', 'patient'] | None [] | E   AssertionError: assert None == ('projected', 0) | C |
| `tests/attack/test_semantic_wh_differential.py::test_role_noun_lists_match_refere…` | role_vocabulary | 9 | 物、起点は？ | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | projected ['patient', 'origin'] | projected ['patient', 'source'] | E   AssertionError: assert (('patient', 'v0'), ('source', 'v1')) == (('patient', | D |
| `tests/attack/test_semantic_wh_differential.py::test_three_distinct_roles_are_sup…` | role_vocabulary＋wh_particle_pairs | 93、101 | だれから何へどこで | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | projected ['origin', 'recipient', 'location'] | None [] | E   AssertionError: assert None == ('projected', 0) | C |
| `tests/attack/test_semantic_wh_differential.py::test_three_distinct_roles_are_sup…` | role_vocabulary | 9 | 起点、物、終点は | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | projected ['origin', 'patient', 'recipient'] | None [] | E   AssertionError: assert None == ('projected', 0) | C |
| `tests/attack/test_semantic_wh_differential.py::test_valid_question_emits_one_wil…` | role_vocabulary | 89 | 何が誰をどこでですか？ | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | projected ['agent', 'patient', 'location'] | projected ['agent', 'patient', 'place'] | E   AssertionError: assert (('agent', 'v0'), ('patient', 'v1'), ('place', 'v2')) | D |
| `tests/attack/test_semantic_wh_fabrication.py::test_roles_and_labels_are_taken_fr…` | role_vocabulary | 93 | どこから誰へ？ | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | builder の戻り値 ['origin', 'recipient'] | builder の戻り値 ['source', 'recipient'] | E   AssertionError: assert [(Pattern(predicate='*', roles=(('source', 'v0'), ('r | D |
| `tests/attack/test_semantic_wh_fabrication.py::test_roles_and_labels_are_taken_fr…` | wh_particle_pairs | 91 | なにで誰に。 | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | builder の戻り値 ['location', 'recipient'] | None [] | E   assert None is <object object at 0x<ADDR>> | C |
| `tests/attack/test_semantic_wh_fabrication.py::test_roles_and_labels_are_taken_fr…` | role_vocabulary | 9 | 起点、受取人は？ | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | builder の戻り値 ['origin', 'recipient'] | builder の戻り値 ['source', 'recipient'] | E   AssertionError: assert [(Pattern(predicate='*', roles=(('source', 'v0'), ('r | D |
| `tests/attack/test_semantic_wh_injection.py::test_role_noun_list_emits_the_role_m…` | role_vocabulary | 9 | 物、起点、受取人は | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | projected ['patient', 'origin', 'recipient'] | projected ['patient', 'source', 'recipient'] | E   AssertionError: assert [(Pattern(predicate='*', roles=(('patient', 'v0'), (' | D |
| `tests/attack/test_semantic_wh_injection.py::test_wh_role_question_emits_only_the…` | role_vocabulary | 89 | 誰が何をどこで? | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | projected ['agent', 'patient', 'location'] | projected ['agent', 'patient', 'place'] | E   AssertionError: assert [(Pattern(predicate='*', roles=(('agent', 'v0'), ('pa | D |
| `tests/attack/test_semantic_wh_limits.py::test_role_nouns_build_their_declared_ro…` | role_vocabulary | 9 | 物、起点、終点は？ | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | Pattern ['patient', 'origin', 'recipient'] | None [] | E   AssertionError: assert None == Pattern(predicate='*', roles=(('patient', 'v0 | C |
| `tests/attack/test_semantic_wh_long_documents.py::test_case_particle_aliases_keep…` | role_vocabulary | 89、93 | どこで何から | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | builder の戻り値 ['location', 'origin'] | builder の戻り値 ['place', 'source'] | E   AssertionError: assert ['place', 'source'] == ['location', 'origin'] | D |
| `tests/attack/test_semantic_wh_long_documents.py::test_case_particle_aliases_keep…` | wh_particle_pairs | 101 | なにへ誰で | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | builder の戻り値 ['recipient', 'location'] | None [] | E   assert None is <object object at 0x<ADDR>> | C |
| `tests/attack/test_semantic_wh_long_documents.py::test_case_question_accepts_opti…` | wh_particle_pairs | 83 | 誰が何にですか？。 | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | builder の戻り値 ['agent', 'recipient'] | None [] | E   assert None is <object object at 0x<ADDR>> | C |
| `tests/attack/test_semantic_wh_long_documents.py::test_role_noun_list_builds_role…` | role_vocabulary | 9 | 送り主、物、起点、終点は。 | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | builder の戻り値 ['agent', 'patient', 'origin', 'recipient'] | None [] | E   assert None is <object object at 0x<ADDR>> | C |
| `tests/attack/test_semantic_wh_negation_modality.py::test_role_noun_question_acce…` | role_vocabulary | 9 | 物、起点は？ | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | builder の戻り値 ['patient', 'origin'] | builder の戻り値 ['patient', 'source'] | E   AssertionError: assert (('patient', 'v0'), ('source', 'v1')) == (('patient', | D |
| `tests/attack/test_semantic_wh_negation_modality.py::test_wh_origin_and_recipient…` | role_vocabulary | 93 | 何から誰へですか？ | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | builder の戻り値 ['origin', 'recipient'] | builder の戻り値 ['source', 'recipient'] | E   AssertionError: assert (('source', 'v0'), ('recipient', 'v1')) == (('origin' | D |
| `tests/attack/test_semantic_wh_paraphrase.py::test_patient_to_recipient_particle_…` | wh_particle_pairs | 83 | 誰が何に | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | Pattern ['agent', 'recipient'] | None [] | E   AssertionError: assert None == Pattern(predicate='*', roles=(('agent', 'v1') | C |
| `tests/attack/test_semantic_wh_paraphrase.py::test_recipient_role_noun_variants_p…` | role_vocabulary | 9 | 物、終点は | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | Pattern ['patient', 'recipient'] | None [] | E   AssertionError: assert None == Pattern(predicate='*', roles=(('patient', 'v1 | C |
| `tests/attack/test_semantic_wh_realtext.py::test_origin_and_recipient_particles_a…` | role_vocabulary＋wh_particle_pairs | 93、101 | 何から何へ。 | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | Pattern ['origin', 'recipient'] | None [] | E   IndexError: list index out of range | C |
| `tests/attack/test_semantic_wh_realtext.py::test_role_noun_synonyms_map_to_agent_…` | role_vocabulary | 9 | 送り主、終点は | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | Pattern ['agent', 'recipient'] | None [] | E   IndexError: list index out of range | C |
| `tests/attack/test_semantic_wh_realtext.py::test_role_nouns_map_patient_and_origi…` | role_vocabulary | 9 | 物、起点は | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | Pattern ['patient', 'origin'] | Pattern ['patient', 'source'] | E   AssertionError: assert [Pattern(predicate='*', roles=(('patient', 1), ('sour | D |
| `tests/attack/test_semantic_wh_realtext.py::test_wh_aliases_and_particle_map_to_a…` | role_vocabulary | 89 | だれはどこでですか？ | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | Pattern ['agent', 'location'] | Pattern ['agent', 'place'] | E   AssertionError: assert [Pattern(predicate='*', roles=(('agent', 1), ('place' | D |
| `tests/attack/test_semantic_wh_tense_time.py::test_role_only_questions_make_one_w…` | role_vocabulary | 89 | 誰が何をどこで誰にですか。 | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | builder の戻り値 ['agent', 'patient', 'location', 'recipient'] | builder の戻り値 ['agent', 'patient', 'place', 'recipient'] | E   AssertionError: assert [(Pattern(predicate='*', roles=(('agent', 'v0'), ('pa | D |
| `tests/attack/test_semantic_wh_tense_time.py::test_role_only_questions_make_one_w…` | role_vocabulary | 9 | 起点、物、終点は？ | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | builder の戻り値 ['origin', 'patient', 'recipient'] | None [] | E   AssertionError: assert [] == [(Pattern(predicate='*', roles=(('origin', 'v0' | C |
| `tests/attack/test_semantic_wh_unicode_noise.py::test_hiragana_wh_forms_and_locat…` | role_vocabulary | 89 | だれがどこで? | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | builder の戻り値 ['agent', 'location'] | builder の戻り値 ['agent', 'place'] | E   AssertionError: assert CapturedPattern(predicate='*', roles=(('agent', 'v1') | D |
| `tests/attack/test_semantic_wh_unicode_noise.py::test_role_noun_list_builds_wildc…` | role_vocabulary | 9 | 起点、終点は？ | ミナは青い鍵を倉庫Cから技師ユンへ運んだ。 | builder の戻り値 ['origin', 'recipient'] | None [] | E   assert None is <object object at 0x<ADDR>> | C |
| `tests/test_semantic_measure.py::test_tense_mismatch_does_not_answer[\u30df\u30aa…` | clause_forms | 170 | 誰が本を読んだ？ | ミオは本を読む。 | ask: UNKNOWN_NO_EVIDENCE [] | ask: ANSWER ['ミオ'] | E   AssertionError: assert 'ANSWER' != 'ANSWER' | A |
| `tests/test_semantic_measure.py::test_tense_mismatch_does_not_answer[\u30df\u30aa…` | clause_forms | 170 | 誰が本を読む？ | ミオは本を読んだ。 | ask: UNKNOWN_NO_EVIDENCE [] | ask: ANSWER ['ミオ'] | E   AssertionError: assert 'ANSWER' != 'ANSWER' | A |
<!-- w1f:end:qf2 -->

各テストの最小再現（`qf2/repro.jsonl`）: 問いと文書（1〜3 文）、`dev` と `dev+qf2` の出力。テストが公開の入口（`Vera.ask`）を呼ぶ場合はその問いとテスト自身の文書、`semantic_verify.Checker` を直接呼ぶ場合はその文書と問いを使った（`document_source` に明記）。`semantic_reader.read_request` に問いだけを与えるテスト（1 件）と `semantic_wh.read_role_list_question` を直接呼ぶテスト（その他）は文書を持たないので、説明用の 1 文を使い、`document_source` にその理由を書いた。原因の行は、推測ではなく実行から取った: `_requested_role` を `sys.settrace` で包み、実行された行（None を返した return 行、または役割名を決めた代入行）を記録し（`capture_qf2*.jsonl`）、clause_forms は親に無い呼び出しの行、role-noun の問いの語彙は親と 9c89f1e の `_ROLE_NOUN` の差から取った。テストが最初の失敗で止まり後ろの問いに進まない場合は、他の因子を親に戻した複写（`capture_qf2_vc.jsonl`・`capture_qf2_pc.jsonl`）で最後まで走らせて残りの因子の行を取った。

### 9.2 受入デモの失敗（別の現象）

<!-- w1f:begin:demo -->
```
env: manifest_wave4.json の env（VERA_CORPUS_ROOT は空ディレクトリ）
498f3c3	unit p_passive	NO_DEMO_FILE
9c89f1e	unit w_question_forms2	DEMO OK
da21edc	unit p_parallel	DEMO OK
b8b9a50	unit p_reason	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2257, 'correct': 123, 'wrong_other': 3, 'wrong_overlap': 17})
0ff2328	unit p_temporal	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2258, 'correct': 124, 'wrong_other': 3, 'wrong_overlap': 15})
77d5699	unit p_comparison	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2257, 'correct': 125, 'wrong_other': 3, 'wrong_overlap': 15})
57079df	unit p_giving	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2251, 'correct': 131, 'wrong_other': 3, 'wrong_overlap': 15})
```

```
dev + qf2(9c89f1e) の複写。構文規則を 1 つずつ VERA_CONSTRUCTIONS_OFF で外してデモを走らせた結果
(none off)	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2246, 'correct': 135, 'wrong_other': 3, 'wrong_overlap': 16})
(all off)	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2304, 'correct': 78, 'wrong_other': 2, 'wrong_overlap': 16})
adnominal	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2248, 'correct': 133, 'wrong_other': 3, 'wrong_overlap': 16})
case_frames	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2246, 'correct': 135, 'wrong_other': 3, 'wrong_overlap': 16})
comparison	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2256, 'correct': 125, 'wrong_other': 3, 'wrong_overlap': 16})
connective_rel	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2246, 'correct': 135, 'wrong_other': 3, 'wrong_overlap': 16})
diathesis	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2247, 'correct': 134, 'wrong_other': 3, 'wrong_overlap': 16})
giving	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2247, 'correct': 134, 'wrong_other': 3, 'wrong_overlap': 16})
gold_caus_pass	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2247, 'correct': 134, 'wrong_other': 3, 'wrong_overlap': 16})
gold_comparison	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2247, 'correct': 134, 'wrong_other': 3, 'wrong_overlap': 16})
gold_double_neg	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2247, 'correct': 134, 'wrong_other': 3, 'wrong_overlap': 16})
gold_giving	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2252, 'correct': 129, 'wrong_other': 3, 'wrong_overlap': 16})
gold_parallel	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2254, 'correct': 127, 'wrong_other': 3, 'wrong_overlap': 16})
gold_passive	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2247, 'correct': 134, 'wrong_other': 3, 'wrong_overlap': 16})
gold_quantity	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2251, 'correct': 130, 'wrong_other': 3, 'wrong_overlap': 16})
gold_reason	DEMO OK
gold_scramble	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2249, 'correct': 132, 'wrong_other': 3, 'wrong_overlap': 16})
gold_temporal	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2245, 'correct': 134, 'wrong_other': 3, 'wrong_overlap': 18})
light_verb	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2246, 'correct': 135, 'wrong_other': 3, 'wrong_overlap': 16})
modality	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2246, 'correct': 135, 'wrong_other': 3, 'wrong_overlap': 16})
negation	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2246, 'correct': 135, 'wrong_other': 3, 'wrong_overlap': 16})
np_internal	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2251, 'correct': 131, 'wrong_other': 3, 'wrong_overlap': 15})
paren_gloss	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2246, 'correct': 135, 'wrong_other': 3, 'wrong_overlap': 16})
quantifier	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2246, 'correct': 135, 'wrong_other': 3, 'wrong_overlap': 16})
quote	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2246, 'correct': 135, 'wrong_other': 3, 'wrong_overlap': 16})
te_chain	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2246, 'correct': 135, 'wrong_other': 3, 'wrong_overlap': 16})
time_expr	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2246, 'correct': 135, 'wrong_other': 3, 'wrong_overlap': 16})
zero_subject	AssertionError: (7, {'correct': 83, 'wrong_other': 2, 'wrong_overlap': 17}, {'abstain': 2246, 'correct': 135, 'wrong_other': 3, 'wrong_overlap': 16})
```
<!-- w1f:end:demo -->

デモの `wrong_other` を増やすのは `gold_reason`（`p_reason`、`b8b9a50`）。9.1 の 34 件とは無関係に、`gold_reason` を直すか、デモの基準を見直す必要がある（10 節の「gold_reason」の下書き。順位は 10 節の表のとおりで、w_question_forms2 の取り込みの前提になる）。

### 9.3 この unit を取り込むには何を直す必要があるか

(a) 34 件を落とす条件: 8 節の決定 1（役割の語彙）が先。決定後、role_vocabulary は語彙の合わせ（`semantic_wh.py:9, 85, 89, 93`）、clause_forms（`:170`）は節単位の問いが role-only と同じ計画を返し、**時制の不一致で答えず、対立する主張で Conflict を出す**よう直す（テストの期待は変えない）、wh_particle_pairs は旧い実装が受理していた組のうち、安全に読めるものだけを再び読む（行は 9.1 の表）。期待の更新が許されるのは、決定後の役割名だけ。
(b) デモを落とす規則: `gold_reason`（9.2）。
(c) 取り込みで解消する基線の失敗: `qf2/fixed_ids.txt`（役割だけの問い。件数は上の表）。

## 10. 優先順位つきのチケット下書き

**優先順位の規則（この規則は件数を数える前に決めた。実装指示書の手順 8 のとおり）**:

1. 第 1 キー: 害の段（重い順）。A=偽の断定・権限の拡大（出典の無い ANSWER／PASS／done、同点で勝者を作って答える）、B=型・会計の偽り（UNKNOWN_* の型の取り違え、構成物を型で申告しない、落としたものを数えない）、C=安全側の取りこぼし（答えるべきところで棄権する）、D=書式・API の形・決定性のみ。害の段は各テストの失敗出力（期待値と実際の値）から決め、下書きの段は含まれるテストの最も重い段。
2. 第 2 キー: 下書きに含まれるテスト数（多い順）。
3. 両方が同じ下書きは同順位（名前順などで勝者を作らない。表の並びは表示のための順で、順位は同じ）。

害の段は手で書かない（`report` が機械的に決める）: 束の害 = 含まれるテストの最も重い害、`w_question_forms2` の 34 件 = dev + 9c89f1e の複写で 1 件ずつ実行した失敗の 1 行目（`qf2/own_commit_errors.jsonl`）に当てた規則（`QF2_HARM_RULES`。規則は 1 回目の失敗出力を見たあとで、上の害の段の定義に沿って書いた。どれにも当たらなければ `report` が落ちる）、デモ = 偽の誤答（wrong_other）が増えるなら A（`demo_harm`）。
順位は仕事の依存順ではない。順位 1（w_question_forms2 の取り込み）には、順位 2（gold_reason）と 8 節の決定 1（役割の語彙）が先に要る。

<!-- w1f:begin:tickets -->
| 順位 | 害 | テスト数 | 下書き | 束／決定 | 触るファイル |
|---:|---|---:|---|---|---|
| 1 | A | 34 | w_question_forms2 を取り込む（34 件の衝突の解消） | — | verantyx/semantic_wh.py, tests/attack/test_semantic_wh_*.py, tests/attack/test_semantic_verify_fabrication.py, tests/attack/test_semantic_reader_paraphrase.py, tests/test_semantic_measure.py |
| 2 | A | 0 | gold_reason を取り込むとデモの wrong_other が 2→3 に増える（w_question_forms2 取り込みの前提） | — | verantyx/constructions/gold_reason.py, tools/demo_question_forms.py（読むだけ） |
| 3 | B | 3 | 決定: 非有効な supersede 事件の扱い（構造検査・保持・会計） | — | docs/（決定を書く文書）, verantyx/memory_merge.py, tests/attack/test_memory_merge_*.py |
| 4 | B | 2 | B02: へ＋人の二重読み（文書側）と 誰へ の問い（質問側）の不一致 | B02 | verantyx/semantic_reader.py |
| 5 | B | 1 | B03: unknown_choice のプロンプトが JSON 化済みの語を二重にエスケープする | B03 | verantyx/semantic_unknown_choice.py |
| 5 | B | 1 | 決定: supersede 事件を merge 出力に残すか（9dbeea6 の矛盾） | — | verantyx/memory_merge.py, verantyx/memory_frame.py, tests/attack/test_memory_merge_differential.py |
| 5 | B | 1 | 決定: 再実行できる証拠が無いときの VERIFICATION 記録の値（UNVERIFIED と FAIL の混同） | — | docs/（決定を書く文書）, verantyx/verifier_agents.py, verantyx/conductor.py, tests/attack/test_verifier_agents_fabrication.py |
| 8 | C | 8 | 古くなったテストの更新: reader の typed ambiguity・coordination・quantifier（8 件） | — | tests/attack/test_semantic_coord_*.py, tests/attack/test_semantic_reader_realtext.py, tests/attack/test_semantic_verify_negation_modality.py, tests/test_semantic_coordination_codex.py, tests/test_semantic_public.py, tests/test_semantic_scope_safety.py |
| 8 | C | 8 | 決定: 役割の語彙（location/origin か place/source/limit か） | — | docs/（決定を書く文書）, verantyx/semantic_reader.py, verantyx/semantic_wh.py, verantyx/semantic_realize.py, tests/attack/test_semantic_wh_*.py（24 件）, tests/test_semantic_realize.py |
| 10 | C | 7 | 古くなったテストの更新: escalate／memory／merge の fixture（7 件） | — | tests/attack/test_conductor_escalate_realtext.py, tests/attack/test_memory_frame_limits.py, tests/attack/test_memory_merge_fabrication.py, tests/attack/test_memory_revalidate_*.py |
| 11 | C | 6 | 古くなった攻撃テストの更新: verifier_agents の新しい契約（6 件） | — | tests/attack/test_verifier_agents_*.py |
| 12 | C | 3 | 古くなった攻撃テストの更新: semantic_unknown の独立出典（3 件） | — | tests/attack/test_semantic_unknown_fabrication.py, tests/attack/test_semantic_unknown_paraphrase.py |
| 12 | C | 3 | 決定: 肩書きの中の接尾辞（研究員）で title+name を分割するか | — | verantyx/semantic_names.py, tests/attack/test_semantic_names_*.py（3 件） |
| 14 | C | 1 | B01: 助詞だけの句（のに の「の」）を格助詞の名詞句として読まない | B01 | verantyx/semantic_reader.py |
| 14 | C | 1 | 決定: symbolic record の原子に許す文字 | — | verantyx/semantic_verify.py, tests/attack/test_semantic_verify_unicode_noise.py |
| 16 | D | 44 | 古くなった攻撃テストの更新: memory_brief（44 件） | — | tests/attack/test_memory_brief_*.py |
| 17 | D | 19 | 古くなった攻撃テストの更新: semantic_names のタグ（19 件） | — | tests/attack/test_semantic_names_*.py |
| 18 | D | 11 | 古くなった攻撃テストの更新: semantic_unknown の stub（11 件） | — | tests/attack/test_semantic_unknown_limits.py, tests/attack/test_semantic_unknown_injection.py |
| 19 | D | 2 | B05: semantic_unknown の作業予算が ASCII の出典語を数えない | B05 | verantyx/semantic_unknown.py |
| 20 | D | 1 | B04: 1 回の問いで同じ witness ファイルを 2 回読む | B04 | verantyx/memory_frame.py |
| 20 | D | 1 | 決定: 零文以内の拘束の扱い | — | verantyx/compositional_goal.py, tests/test_request_goal_route.py |
| 20 | D | 1 | 環境依存のテスト宣言: 一般コーパスが要る下書きテスト | — | tests/_vera_env.py, tests/test_p4_abilities.py |
<!-- w1f:end:tickets -->

### 下書きの詳細（目的・触るファイル・受入基準の案）

<!-- w1f:begin:ticket_details -->
#### 順位 1（害 A・34 件）w_question_forms2 を取り込む（34 件の衝突の解消）
- 目的: 9c89f1e の semantic_wh.py は、役割の語彙の変更（role_vocabulary）・節単位の問い（clause_forms）・role-only の問いの wh＋助詞の組の制限（wh_particle_pairs）の 3 つの機構で既存テスト 34 件を落とす（機構ごとの件数は 9.1 の表）。clause_forms は、時制が合わない問いに偽の ANSWER を返し、対立する主張に Conflict を出さない（時制・Conflict のテストの失敗出力。9.1）。語彙の決定（8 節の決定 1）の後、3 つの機構を直して取り込む。前提: gold_reason の下書き（デモ）が先。取り込みで基線の失敗が通るようになる（件数は 9.1）。
- 触るファイル: verantyx/semantic_wh.py, tests/attack/test_semantic_wh_*.py, tests/attack/test_semantic_verify_fabrication.py, tests/attack/test_semantic_reader_paraphrase.py, tests/test_semantic_measure.py
- 受入基準の案（測り方）: dev + 9c89f1e の複写で、qf2/ids.txt の 34 件が、テストの期待を変えずに通る。特に時制が合わない問い（test_tense_mismatch_does_not_answer）が ANSWER にならず、対立する主張（test_unresolved_opposing_claims_raise_conflict_instead_of_answering）で Conflict が出ること。期待の更新が許されるのは、8 節の決定 1（役割の語彙）が文書になった後の「役割名」だけで、時制・Conflict・出典の性質を検査する assert は変えない。qf2/fixed_ids.txt の基線の失敗が通り、tools/demo_question_forms.py が DEMO OK（gold_reason の件を先に直す）、全体の新規失敗が 0。

#### 順位 2（害 A・0 件）gold_reason を取り込むとデモの wrong_other が 2→3 に増える（w_question_forms2 取り込みの前提）
- 目的: wave4 の p_reason（b8b9a50）が加えた構文規則 gold_reason が tools/demo_question_forms.py の seed 7 で wrong_other を 1 件増やす（偽の ANSWER が 1 件増える）。増えた項目を特定し、規則の条件を狭めて棄権（型付き）にする。
- 触るファイル: verantyx/constructions/gold_reason.py, tools/demo_question_forms.py（読むだけ）
- 受入基準の案（測り方）: dev + w_question_forms2(9c89f1e) の複写で、VERA_CONSTRUCTIONS_OFF 無しに tools/demo_question_forms.py が DEMO OK（qf2/demo_leave_one_out.txt の gold_reason 行と同じ結果）。gold の correct が下がらないこと（seed 7 と 101 の両方で測る）。全体の失敗集合は増えない。

#### 順位 3（害 B・3 件）決定: 非有効な supersede 事件の扱い（構造検査・保持・会計）
- 目的: memory_merge が、置換記録のポインタが一致しない supersede 事件を黙って出力から落とす。dangling／循環の検査を非有効な事件にも課すか、型付きで保持して件数を報告するかを決め、攻撃テスト 3 件を決定に合わせる。
- 触るファイル: docs/（決定を書く文書）, verantyx/memory_merge.py, tests/attack/test_memory_merge_*.py
- 受入基準の案（測り方）: 決定が文書になり、n=50〜52 の期待が決定に一致する。落とした事件の件数がどこかの出力に現れ、全体の失敗集合から該当 3 件が減る。

#### 順位 4（害 B・2 件）B02: へ＋人の二重読み（文書側）と 誰へ の問い（質問側）の不一致
- 目的: 肩書きつき名前（技師ユン／店長サキ）＋へ で、frame の recipient と case 読みの direction が同じ語を二重に読み、INVALID_PROOF になる。重なる span を case 読みから除き、誰へ は recipient で問う。
- 触るファイル: verantyx/semantic_reader.py
- 受入基準の案（測り方）: fixes/B02.diff 相当の修正で test_kanji_title_before_a_name_is_split と test_role_only_questions_generalize[誰が何を誰へ] が通り、全体の失敗集合の新規失敗が 0（fixes/B02.json）。

#### 順位 5（害 B・1 件）B03: unknown_choice のプロンプトが JSON 化済みの語を二重にエスケープする
- 目的: untrusted な語をモデルに見せる形が、直列化した文字列と別物になる。区切り（「」）だけを不活性にし、JSON のエスケープはそのまま見せる。
- 触るファイル: verantyx/semantic_unknown_choice.py
- 受入基準の案（測り方）: test_query_delimiters_and_line_breaks_stay_inside_the_json_string が通り、semantic_unknown_choice 系 81 件に新規失敗が出ない（fixes/B03.json）。

#### 順位 5（害 B・1 件）決定: supersede 事件を merge 出力に残すか（9dbeea6 の矛盾）
- 目的: 攻撃テストは事件を残す正準合併を、unit のテストは再オープンで権限が復活しないことを固定する。Memory._apply がポインタを検証すれば両立するかを決める。
- 触るファイル: verantyx/memory_merge.py, verantyx/memory_frame.py, tests/attack/test_memory_merge_differential.py
- 受入基準の案（測り方）: 決定が文書になり、test_canonical_order_and_exact_duplicate_removal と test_mismatched_supersede_stays_nonoperative_after_serialize_and_reopen が同時に通る（probes/revert_9dbeea6.json の矛盾が解ける）。

#### 順位 5（害 B・1 件）決定: 再実行できる証拠が無いときの VERIFICATION 記録の値（UNVERIFIED と FAIL の混同）
- 目的: verifier_agents.py:610 は再実行できる証拠が無い PASS を UNVERIFIED として ESCALATE するが、記録は FAIL で書く（conductor.record_verification は PASS／FAIL だけを受ける）。UNVERIFIED を記録の型として持つか、記録しないか、FAIL のまま文書化するかを決め、n=106 のテストを決定に合わせる。
- 触るファイル: docs/（決定を書く文書）, verantyx/verifier_agents.py, verantyx/conductor.py, tests/attack/test_verifier_agents_fabrication.py
- 受入基準の案（測り方）: 決定が文書になり、n=106 の期待が決定に一致する。再実行できる証拠が無い PASS の記録が FAIL と区別できる（記録の型として UNVERIFIED、または記録しないこと）か、FAIL のままなら型の混同を許す理由が決定に書かれている。UNVERIFIED を FAIL に固定する期待のテストを作らない。全体の失敗集合から該当 1 件が減り、新規失敗が 0。

#### 順位 8（害 C・8 件）古くなったテストの更新: reader の typed ambiguity・coordination・quantifier（8 件）
- 目的: fix_semantic_reader／fix_semantic_coord／k_quantifier の新しい挙動（二重否定の Unread、伝聞の hedge、で の ambiguous、から の source、話題の無い連鎖、量化節の追加）に合わせて期待を更新する。
- 触るファイル: tests/attack/test_semantic_coord_*.py, tests/attack/test_semantic_reader_realtext.py, tests/attack/test_semantic_verify_negation_modality.py, tests/test_semantic_coordination_codex.py, tests/test_semantic_public.py, tests/test_semantic_scope_safety.py
- 受入基準の案（測り方）: 8 件が期待を更新して通る。「はいに読み替えない」「推測しない」性質の assert は残る。

#### 順位 8（害 C・8 件）決定: 役割の語彙（location/origin か place/source/limit か）
- 目的: reader（place/source/limit…）と semantic_wh・semantic_realize（location/origin/recipient）の役割名が食い違い、役割だけの問い 6 件と realize 2 件が落ちる。正を 1 つ決め、全モジュールと攻撃テストを合わせる。qf2 取り込みの前提。
- 触るファイル: docs/（決定を書く文書）, verantyx/semantic_reader.py, verantyx/semantic_wh.py, verantyx/semantic_realize.py, tests/attack/test_semantic_wh_*.py（24 件）, tests/test_semantic_realize.py
- 受入基準の案（測り方）: 決定が文書になり、決めた語彙で n=114,115,116,118,119,120,122,123 が通る（115,116 は B02 も要る）。全体の失敗集合が増えない（probes/combo_vocab_*.json と同じ測り方）。

#### 順位 10（害 C・7 件）古くなったテストの更新: escalate／memory／merge の fixture（7 件）
- 目的: 信頼できる record lookup を持つ二重化、witness_classes の許容、置換記録のポインタ、読める witness 文へ更新する。
- 触るファイル: tests/attack/test_conductor_escalate_realtext.py, tests/attack/test_memory_frame_limits.py, tests/attack/test_memory_merge_fabrication.py, tests/attack/test_memory_revalidate_*.py
- 受入基準の案（測り方）: 7 件が通る（probes/adapt_cond・adapt_wc・adapt_merge49・adapt_revalidate の passes。n=53 は期待の更新が要る）。

#### 順位 11（害 C・6 件）古くなった攻撃テストの更新: verifier_agents の新しい契約（6 件）
- 目的: x_verifier_evidence の証拠項目・testimony の契約に合わせて brief の本文・エラー文言・done の条件の期待を更新する。記録の result（UNVERIFIED を FAIL として記録している点: verifier_agents.py:610）は別の決定の下書きで決めるので、このチケットの範囲に入れない。
- 触るファイル: tests/attack/test_verifier_agents_*.py
- 受入基準の案（測り方）: 6 件が通る。再実行できる証拠が無い PASS が done にならない性質（ESCALATE／UNVERIFIED）を検査する assert は期待を変えずに残す。更新後のテストが VERIFICATION 記録の result を FAIL に固定していない（grep で `"FAIL"` を要求する assert が増えていない）。

#### 順位 12（害 C・3 件）古くなった攻撃テストの更新: semantic_unknown の独立出典（3 件）
- 目的: 出典が 1 つの View では隣接候補を作らない（b29097a）。独立出典（3 回の単独出現）を持つ View を fixture にするか、期待を NO_REACH に変える。
- 触るファイル: tests/attack/test_semantic_unknown_fabrication.py, tests/attack/test_semantic_unknown_paraphrase.py
- 受入基準の案（測り方）: 3 件が通る。candidate が構成物・非証拠として型付きである性質のテストは残る。

#### 順位 12（害 C・3 件）決定: 肩書きの中の接尾辞（研究員）で title+name を分割するか
- 目的: g_names_fix が接尾辞を含む肩書きの分割を拒否する。実際のタガーは 研究員 を 研究+員 に切る。分割を許す条件を決める。
- 触るファイル: verantyx/semantic_names.py, tests/attack/test_semantic_names_*.py（3 件）
- 受入基準の案（測り方）: 決定が文書になり、n=60,64,73 の期待が決定に一致する。e2e（研究員ユンは… の答え）が決定どおり。全体の失敗集合が増えない。

#### 順位 14（害 C・1 件）B01: 助詞だけの句（のに の「の」）を格助詞の名詞句として読まない
- 目的: _case_phrase が名詞を含まない句を返し、節全体が unsupported になる。名詞を含まない句は読まない。
- 触るファイル: verantyx/semantic_reader.py
- 受入基準の案（測り方）: test_concessive_main_clause_keeps_the_topic_subject が通り、全体の失敗集合に新規失敗が 0（fixes/B01.json）。

#### 順位 14（害 C・1 件）決定: symbolic record の原子に許す文字
- 目的: NFKC で不変な英数字＋_ に限る現状と、Unicode を逐語で許すテストの食い違い。
- 触るファイル: verantyx/semantic_verify.py, tests/attack/test_semantic_verify_unicode_noise.py
- 受入基準の案（測り方）: 決定が文書になり、n=101 の期待が決定に一致する。互換文字に隠した指示の拒否テスト（semantic_verify 系）が落ちない。

#### 順位 16（害 D・44 件）古くなった攻撃テストの更新: memory_brief（44 件）
- 目的: a9cad0a の型付き ContextBrief・注記つきの行・verdict つきの ask_about に合わせて期待を更新する（adapter L1〜L4 が形だけの差であることを示している）。
- 触るファイル: tests/attack/test_memory_brief_*.py
- 受入基準の案（測り方）: 44 件が通る。更新はコントラクト（型・注記・二重化の verdict・旧い予算勘定）の変更だけで、検査する性質（順序・会計・落とした id・検索可能性）を弱めない。

#### 順位 17（害 D・19 件）古くなった攻撃テストの更新: semantic_names のタグ（19 件）
- 目的: 合成トークンの品詞細分類を IPAdic の「一般」から UniDic の「普通名詞」へ更新する。
- 触るファイル: tests/attack/test_semantic_names_*.py
- 受入基準の案（測り方）: 19 件が通る（probes/adapt_names.json の passes）。

#### 順位 18（害 D・11 件）古くなった攻撃テストの更新: semantic_unknown の stub（11 件）
- 目的: stub に semantic_ir.Clause が持つ predicate_span を足す。
- 触るファイル: tests/attack/test_semantic_unknown_limits.py, tests/attack/test_semantic_unknown_injection.py
- 受入基準の案（測り方）: 11 件が通る（probes/adapt_ustub.json の passes）。

#### 順位 19（害 D・2 件）B05: semantic_unknown の作業予算が ASCII の出典語を数えない
- 目的: docstring の distinct source words を ASCII 語も含めて数え、予算超過を型付きの BUDGET_REFUSAL にする。
- 触るファイル: verantyx/semantic_unknown.py
- 受入基準の案（測り方）: test_source_word_counts_toward_projection_budget と test_budget_below_clause_and_role_work_floor_refuses が通り、新規失敗が 0（fixes/B05.json）。

#### 順位 20（害 D・1 件）B04: 1 回の問いで同じ witness ファイルを 2 回読む
- 目的: RevalidatingMemory の鮮度確認と Memory._witness_supports が同じファイルを読む。支持判定は形だけを見て読みを 1 回にする。
- 触るファイル: verantyx/memory_frame.py
- 受入基準の案（測り方）: test_matching_file_hash_keeps_only_the_grounded_value が通り、memory_*／witness 系に新規失敗が 0（fixes/B04.json）。

#### 順位 20（害 D・1 件）決定: 零文以内の拘束の扱い
- 目的: 零を数詞として読むかで、HOLD の理由が変わる。
- 触るファイル: verantyx/compositional_goal.py, tests/test_request_goal_route.py
- 受入基準の案（測り方）: 決定が文書になり、n=110 の期待が決定に一致する。

#### 順位 20（害 D・1 件）環境依存のテスト宣言: 一般コーパスが要る下書きテスト
- 目的: test_speech_act_drafts_fill_new_roles_and_reread は frames.attested（一般コーパス）が無いと落ちる。needs_resource で宣言するか、最小の fixture を使う。
- 触るファイル: tests/_vera_env.py, tests/test_p4_abilities.py
- 受入基準の案（測り方）: コーパスの無い環境で ENV_MISSING[...] の skip として分類され（FAIL ではない）、コーパスのある環境で通る。probes/env_general_109.txt と同じ測り方で、最小 DB の指定で通る。
<!-- w1f:end:ticket_details -->

## 11. 判断記録

- 索引（`python -m verantyx.cli index search`）の結果は `index_search.txt`: 「失敗 テスト 分類」「bisect 回帰 コミット」「役割 語彙 origin source」の 3 問とも `UNKNOWN_NOT_FOUND`。既存の道具で代用できるものは無かった。
- 原則の語彙（攻撃テストの `principle` に使う）: P1 同点は棄権する／P2 分からないことと偽であることを混ぜない／P3 構成物・生成物は型で申告する／P4 出典の無い断定をしない／P5 自動で落としたもの・読み飛ばしたものを数えて報告する（会計）／P6 入力を変えない・繰り返しても同じ／P7 束ねず重ねる／P8 データと指示を分ける（untrusted な入力を逐語・型付きデータとして扱い、二重加工や指示としての解釈をしない。実装指示書の語彙に足した）。
- 保守的に決めたこと（件数は書かない）: 原則から決まらないものは「判断が要る」にした（同点は棄権）。「期待値が古い」は unit の指示文・最終報告に挙動変更の明示があり、新しい挙動が原則に反しない場合に限った。意図の明示が無い挙動の副作用（memory_brief の verdict ゲート）は、unit 自身の stub が同じ契約を持つことを根拠にしたが、既知の穴に残した。
- 出力の決定性: 実行ごとに変わるもの（一時パス、オブジェクトのアドレス、所要ミリ秒 `*_ms=`、gap の内容ハッシュ `gap_xxxxxxxx`）は `norm_out` で置換し、集合の表示順は `PYTHONHASHSEED=0` で固定した。1 件ずつ実行（`isolate`）を 2 回走らせて `runs/` が一致することを確かめてから採用した。
- 作業開始時に途中作業が残っていた（前回の実装役の続き）。残したもの: 選択プラグイン・`baseline`・`history` の測定。作り直したもの: `collect`・`isolate`（正規化の穴があった）・`probe revert`（衝突した 6 件を `--reject` で部分適用し、新規失敗を単独で再確認）。許可パス外の `tools/__pycache__/` は 1 ファイルずつ `rm`・`rmdir` で消した。
- デモの環境: `manifest_wave4.json` の env。`VERA_CORPUS_ROOT` は空のディレクトリ（キャッシュ内）。
- 第 2 ラウンドの変更: 「期待値が古い」だった n=106（`test_run_verifiers_records_references_with_their_verifier_identities`）を「判断が要る」に直した。新しい挙動（記録が FAIL）が原則 P2 に反し、テストの期待（PASS）も新しい契約では正しくない（8 節の決定 7）。n=108 は同じ unit の契約で落ちるが、記録の値を見ない assert で止まり、返信の型（ESCALATE／UNVERIFIED）は正しく申告されているので「期待値が古い」のままにした。
- qf2 の害の段は、第 1 ラウンドでは手で C と書いていた。失敗出力（時制が合わないのに ANSWER、Conflict が出ない）は偽の断定（A）に当たるので、`report` が失敗の 1 行目から機械的に決める形に直した。
- qf2 の機構の切り分けは、因子の全組合せ（V・C・P の 2^3−1 通り）で測った。P の因子は「`_requested_role` が None または後で拒否される役割を返す組だけを親の表（が・は→agent、を→patient、に・へ→recipient、で→location、から→origin）の役割に戻す」という変種で、受理される組の名前は 9c89f1e のまま（名前は V の因子）。3 つすべてを戻すと 34 件がすべて通る（`ablation.json` の `all_three_restored`）。
- 失敗の分類を「テストの削除・skip・xfail 化・期待値の弱体化」で解消していない。製品・テストは一切変えていない（`git status` の許可パス以外が 0）。

## 12. 既知の穴

- **adapter の限界**: 形だけの adapter が作れない「期待値が古い」は、意図の引用と revert probe に頼る。revert probe の「部分」は当たる hunk だけの逆適用で、unit の完全な取り消しではない（衝突した unit は `probes/revert_*.json` の `rejected_hunks`）。意図の引用は短い（15 語程度まで）ので、指示文全体の文脈は引用元ファイルを読む必要がある。
- **memory_brief の verdict ゲート**: `ask_about` の答えが `verdict == "ANSWER"` でないと record が引けないとする変更は、`fix_w_brief_1` の指示には書かれていない。二重化に verdict を足す adapter で通るが、「二重化が公開契約を満たしていなかった」のか「意図しない副作用」かは判断。
- **UNVERIFIED と FAIL**: `verifier_agents.py:610` は再実行できる証拠が無いとき VERIFICATION 記録を `FAIL` にする（返答は ESCALATE）。どの記録の型が正しいかは決められないので、n=106 を「判断が要る」にした（8 節の決定 7）。この決定は同じ unit の n=108 とは独立だが、n=108 のテストを更新するときに記録の result を FAIL に固定してはいけない。
- **閉じた名詞リスト**: reader の `で` の場所判定（`_PLACE_NOMINALS`・語尾）と、frames の関係節の判定（一般コーパスの裏づけ）は、語彙の外では typed ambiguity か未読になる。保証していないことの範囲との関係は決めていない。
- **害の段**: 製品の不具合・期待値が古い・判断が要る・テストの不備の各テストの害は、失敗出力から人が決めたもの。束・チケット下書き・qf2・デモの害は `report` が機械的に決める（10 節）。qf2 の害の規則は 1 回目の失敗出力を見たあとで書いた。規則は失敗の 1 行目の文字列だけで害の段を決めていて、C と D の境（計画が None・空で問いが読まれない＝C、計画の役割名・束縛数だけの違い＝D）を 1 件ずつ精査していない。第 3 ラウンドで、空の計画（`assert [] ==`）の 1 件を D から C に直した（`qf2/own_commit_errors.jsonl`）。D の 15 件は、`Vera.ask` の端から端までの実行で偽の答えが出ないかを 1 件ずつは測っていない。「期待値が古い」の害は、失敗が示す製品側の挙動の向き（安全側の取りこぼし＝C、形だけ＝D）で付けた。
- **qf2 の再現**: role-only の問いのテスト（read_role_list_question／read_request を直接呼ぶもの）は文書を持たないので、再現の文書は説明用の 1 文（`document_source` に明記）。この文書での `Vera.ask` の結果は、直接呼ぶテストの失敗を再現するものではなく、説明用の参考。原因の行は実行の記録（`sys.settrace` の実行行・`_ROLE_NOUN` の差）から取り、未特定は 0 件だが、ablation の変種は「親の受理範囲に戻す」編集であって、`semantic_wh.py` の 1 行だけを直した差分ではない。34 件それぞれを 1 行の修正で通したものではない。
- **束 B02**: 2 行にまたがる（n=117 は :177 だけで通り、n=113 は :177 と :745 の両方が要る。束の表の下の測定）。どちらの行がテスト意図に近いかは決めていない。
- **全体実行の揺れ**: `HOME` は実物を共有する。作業前の全体実行（`suite_before.txt`）は `PYTHONHASHSEED=0` を付ける前、作業後（`suite_after.txt`）は付けた後。失敗集合は同一（`suite_*_compare.txt`）。
- **チケット下書きの害**: 「古くなったテストの更新」の下書きは、含まれるテストの最も重い害で順位が決まる（実際には期待値の更新で、製品の害は無い）。順位は規則どおりだが、仕事の緊急度を表さない。
