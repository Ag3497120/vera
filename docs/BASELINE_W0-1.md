# W0-1 統合基線（BASELINE_W0-1）

この文書は、統合チケット W0-1 の測定結果を記録する。**数値はすべて括弧内の出力ファイル（`artifacts/w0-1/`）から辿れる**。
出力ファイルが無い数値は書かない。前任者の途中出力は条件の記録が無いため破棄し、測り直した（10 節）。

## 1. 測定条件

- 基点: `dev` = `origin/dev` = `origin/src/wave3` = `65f43da`（`versions.txt`）。統合後ツリー = `dev` ＋ 取り込んだ wave4 の 11 unit ＋ wave5 の 2 unit ＋ 環境マーカー／依存除去／測定ツール（作業ツリーは未コミット）。
- 実行環境: Python 3.11.14、pytest 9.1.1、fugashi 1.5.2、unidic-lite 1.0.8、macOS arm64（`versions.txt`）。この venv には外部の別物 `verantyx` が editable で入っており、PYTHONPATH 無しで `import verantyx` すると `.../simureal/reference-verantyx-bdcd218/engine/verantyx/__init__.py` に解決される（`versions.txt` 末尾）。以後の全実行は `env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<対象ツリー>`。
- node: 既定の測定（`PATH=/usr/bin:/bin`）では node は PATH に無い。`*_with_node` の測定だけ `PATH=/usr/bin:/bin:/usr/local/bin`（node v22.17.0）。この node は `--jitless --no-warnings` でも stderr に `Warning: disabling flag --expose_wasm due to conflicting flags`（63 バイト）を出す（`versions.txt`）。`/opt/homebrew/bin/node` はこの機械に無い。警告 1 行だけを取り除く node ラッパー（`quiet_node_shim.sh`。実 node をそのまま実行し、その 1 行だけを stderr から落とす）を PATH の先頭に置いた測定も 1 回行った（`after_pytest_with_quiet_node.txt`。テストは 1 行も変えていない）。
- pytest のフラグ: before・after とも `-q -p no:cacheprovider -rfEs --continue-on-collection-errors --junitxml=...`（dev には収集エラーが 1 件あり、フラグ無しでは全体が中断する）。
- 全コマンドと出力ファイルの対応: `artifacts/w0-1/COMMANDS.md`。
- before は `git archive dev` で別ディレクトリに展開した `dev` の純粋な状態で測った。`before_pytest.txt` に「environment classification of skips」節が無いこと（= 作業ツリーの `tests/conftest.py` を拾っていない）を確認済み（`grep -c` で 0）。
- 決定性: before・after を各 2 回走らせ、失敗/エラー ID 集合は完全一致（before 165 行、after 124 行。`determinism.txt`）。

## 2. 総数

pytest の要約行（出典のファイルの最終行付近）:

| 測定 | 収集 | passed | failed | error | xfailed | xpassed | skipped | 出典 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| before（dev） | 3956 + 収集エラー1モジュール | 3631 | 164 | 1（収集エラー） | 82 | 68 | 11 | `before_pytest.txt` |
| after（node なし） | 3974 | 3672 | 124 | 0 | 82 | 68 | 28 | `after_pytest.txt`、収集件数は `g2_collect.txt` |
| after（node あり） | 3974 | 3680 | 124 | 0 | 82 | 68 | 20 | `after_pytest_with_node.txt` |
| after（警告を除いた node あり） | 3974 | 3689 | 124 | 0 | 82 | 68 | 11 | `after_pytest_with_quiet_node.txt` |
| （参考）after + w_question_forms2 | 3974 | 3641 | 155 | 0 | 83 | 67 | 28 | `qf2_trial_pytest.txt` |

- 収集は、各行の passed+failed+xfailed+xpassed+skipped の合計と一致する（before: 3631+164+82+68+11=3956、after: 3672+124+82+68+28=3974、node あり: 3680+124+82+68+20=3974、警告を除いた node あり: 3689+124+82+68+11=3974、参考: 3641+155+83+67+28=3974）。`g3_compare*.txt` の junit 集計（testcases=3956 / 3974 / 3974）とも一致。
- before の `1 error` は `tests/attack/test_semantic_unknown_choice_paraphrase.py` の収集エラー（`NameError: name 'pytest' is not defined`。`import pytest` の欠落）。after では収集エラー 0（`g2_collect.txt`: `collection errors: 0`）。
- 要約行の `37 subtests passed` は before・after とも同じ。
- ENV_MISSING の内訳（after、node なし。`after_pytest.txt` の「environment classification of skips」節。`UNCLASSIFIED_SKIP` は 0 行）: sandbox_integration 8、node_jitless_quiet 9、node 8、eval_fixtures 1、ja_sealed1_dev_fixtures 1、round5_dev_fixtures 1（合計 28）。node あり: node は 0、他は同数（合計 20、`after_pytest_with_node.txt`）。
- before の 11 skip は、同じ 11 テスト（sandbox 8、eval_fixtures 1、ja_sealed1 1、round5 1）。理由が資源名無しの自由文だった（`before_pytest.txt` の SKIPPED 行）。

## 3. 取り込み表（G5）

ledger は `/Users/motonisihikoudai/vera-wiring/phase2/runs/wave4/ledger.jsonl`（19 unit）と `.../wave5/ledger.jsonl`（5 unit）。読み取り専用で、`tools/w0_1_unit_table.py` が読み、出力が `unit_table.txt`。
規則（この順で適用）: R1 台帳に merged が無い → 取り込まない／R2 merged だが commit が無い → 取り込む変更が存在しない／R4 merged で commit があるが、載せると前に通っていたテストが落ちると測定された → 取り込まない／R3 merged で commit が枝にある → 取り込む。

| wave | unit | 台帳のイベント列 | merged の commit | 規則 | 判定 | ツリーの該当ファイルが枝の版と一致 | 理由 |
|---|---|---|---|---|---|---|---|
| wave4 | `w_case_lexicon` | launch→finished→retry→launch→finished→merged | ff71279 | R3 | IMPORTED | 4/4 | merged with a commit that is on the branch |
| wave4 | `w_question_forms` | launch→finished→retry→launch→finished→hold→merged | - | R2 | NOT_IMPORTED | - | merged without a commit; no change exists to import: DEPENDENCY WAIVED by the conductor owner: held unit superseded by w_question_forms2; phenomenon units do not touch semantic_wh.py |
| wave4 | `w_question_forms2` | add_unit→launch→finished→merged | 9c89f1e | R4 | NOT_IMPORTED | 0/2 | merged with a commit, but adding it makes previously-passing tests fail; see artifacts/w0-1/qf2_trial_compare.txt |
| wave4 | `p_parallel` | launch→finished→merged | da21edc | R3 | IMPORTED | 2/2 | merged with a commit that is on the branch |
| wave4 | `p_double_neg` | launch→finished→merged | ffe079e | R3 | IMPORTED | 2/2 | merged with a commit that is on the branch |
| wave4 | `p_causative` | launch→finished→retry→launch | - | R1 | NOT_IMPORTED | - | no merged event in the ledger (no terminal event) |
| wave4 | `p_caus_pass` | launch→finished→merged | 17e6d4f | R3 | IMPORTED | 2/2 | merged with a commit that is on the branch |
| wave4 | `p_passive` | launch→finished→merged | 498f3c3 | R3 | IMPORTED | 2/2 | merged with a commit that is on the branch |
| wave4 | `p_potential` | launch→finished→retry→launch→finished→hold | - | R1 | NOT_IMPORTED | - | no merged event in the ledger (hold) |
| wave4 | `p_negation` | launch→finished→retry→launch→finished→hold | - | R1 | NOT_IMPORTED | - | no merged event in the ledger (hold) |
| wave4 | `p_giving` | launch→finished→merged | 57079df | R3 | IMPORTED | 2/2 | merged with a commit that is on the branch |
| wave4 | `p_quantity` | launch→finished→merged | e6b2952 | R3 | IMPORTED | 2/2 | merged with a commit that is on the branch |
| wave4 | `p_temporal` | launch→finished→merged | 0ff2328 | R3 | IMPORTED | 2/2 | merged with a commit that is on the branch |
| wave4 | `p_conditional` | launch→finished→retry→launch | - | R1 | NOT_IMPORTED | - | no merged event in the ledger (no terminal event) |
| wave4 | `p_comparison` | launch→finished→merged | 77d5699 | R3 | IMPORTED | 2/2 | merged with a commit that is on the branch |
| wave4 | `p_reason` | launch→finished→merged | b8b9a50 | R3 | IMPORTED | 2/2 | merged with a commit that is on the branch |
| wave4 | `p_scramble` | launch→finished→merged | 6546002 | R3 | IMPORTED | 2/2 | merged with a commit that is on the branch |
| wave4 | `p_adnominal` | launch→finished→retry→launch→finished→hold | - | R1 | NOT_IMPORTED | - | no merged event in the ledger (hold) |
| wave4 | `p_synonym` | launch→finished→retry→launch→finished→hold | - | R1 | NOT_IMPORTED | - | no merged event in the ledger (hold) |
| wave5 | `r_reader_regress` | launch→finished→retry→launch→adopt→finished→retry→launch→finished→retry→launch→finished→hold | - | R1 | NOT_IMPORTED | - | no merged event in the ledger (hold) |
| wave5 | `r_verifier` | launch→finished→retry→launch→finished→hold→retry→launch→finished→merged | d25a73a | R3 | IMPORTED | 2/2 | merged with a commit that is on the branch |
| wave5 | `r_memory` | launch→finished→retry→launch→finished→hold→retry→launch→finished→merged | 6febe16 | R3 | IMPORTED | 2/2 | merged with a commit that is on the branch |
| wave5 | `r_demos` | launch→finished→retry→launch→finished→retry→launch→finished→retry→launch | - | R1 | NOT_IMPORTED | - | no merged event in the ledger (no terminal event) |
| wave5 | `r_reader_regress2` | add_unit→launch | - | R1 | NOT_IMPORTED | - | no merged event in the ledger (no terminal event) |

- 取り込み: 13 unit（wave4 の 11 + wave5 の 2）、取り込まない: 11 unit（wave4 の 8 + wave5 の 3）。`unit_table.txt` の `verdict=` 行の集計と一致。
- 衝突: **テキスト衝突は無い**。`overlap.txt` の 3 つの交わり（dev の分岐後変更∩wave4、dev の分岐後変更∩wave5、wave4変更∩wave5変更）はすべて空。よって解決方針は「枝の版をそのまま取り込む」。取り込んだファイルは枝の版とバイト一致（`import_identity.txt`: SAME 28、DIFF 2。DIFF の 2 つは下の w_question_forms2 の 2 ファイル）。
- hold／未完了（p_adnominal, p_synonym, p_negation, p_potential, p_causative, p_conditional, r_reader_regress, r_demos, r_reader_regress2）の変更は枝に入っていないので、ツリーにも入っていない（`git log dev..origin/src/wave4` の 12 コミットと `dev..origin/src/wave5` の 2 コミットは、台帳の merged 行の commit と一致。`unit_table.txt` の `on_branch=yes`）。
- **w_question_forms（hold → merged、commit なし）**: 台帳の merged 行の理由は「DEPENDENCY WAIVED ... superseded by w_question_forms2」。コミットが存在せず、取り込む変更が無い（規則 R2）。
- **w_question_forms2（台帳上 merged、commit 9c89f1e。取り込まない）**: 意味上の衝突（規則 R4）。`verantyx/semantic_wh.py` と `tools/demo_question_forms.py` の 2 ファイルを統合ツリーに載せて同じ pytest を走らせたところ（`qf2_trial_pytest.txt`）、before で通っていたのに after で **34 件が新たに失敗**した（`qf2_trial_compare.txt` の `G3 NEW_FAIL=34`）。この 2 ファイルを載せない統合ツリーでは新規失敗は 0（`g3_compare.txt`）。製品の挙動を直して通すことはこのチケットでは禁止なので、取り込まず、34 件の一覧を残す。「hold だから」ではない。
  - 新規失敗の内訳（`qf2_trial_compare.txt`）: test_semantic_wh_* 計 28 件（differential 6, fabrication 3, injection 2, limits 1, long_documents 4, negation_modality 2, paraphrase 2, realtext 4, tense_time 2, unicode_noise 2）、test_semantic_verify_fabrication 3 件、test_semantic_reader_paraphrase 1 件、test_semantic_measure 2 件（計 34）。全 34 件の ID:

- `tests.attack.test_semantic_reader_paraphrase::test_direct_who_question_binds_the_missing_agent_role`（before=passed）
- `tests.attack.test_semantic_verify_fabrication::test_gate_accepts_a_complete_replayed_answer_proposal`（before=passed）
- `tests.attack.test_semantic_verify_fabrication::test_replayed_proof_returns_the_source_supported_actor`（before=passed）
- `tests.attack.test_semantic_verify_fabrication::test_unresolved_opposing_claims_raise_conflict_instead_of_answering`（before=passed）
- `tests.attack.test_semantic_wh_differential::test_all_surface_words_and_case_particles_map_to_their_contract_roles`（before=passed）
- `tests.attack.test_semantic_wh_differential::test_generated_wh_case_sequences_match_independent_reference`（before=passed）
- `tests.attack.test_semantic_wh_differential::test_role_noun_lists_match_reference_and_preserve_label_order`（before=passed）
- `tests.attack.test_semantic_wh_differential::test_three_distinct_roles_are_supported_and_keep_source_order[\u3060\u308c\u304b\u3089\u4f55\u3078\u3069\u3053\u3067]`（before=passed）
- `tests.attack.test_semantic_wh_differential::test_three_distinct_roles_are_supported_and_keep_source_order[\u8d77\u70b9\u3001\u7269\u3001\u7d42\u70b9\u306f]`（before=passed）
- `tests.attack.test_semantic_wh_differential::test_valid_question_emits_one_wildcard_bind_and_one_output_per_requested_role`（before=passed）
- `tests.attack.test_semantic_wh_fabrication::test_roles_and_labels_are_taken_from_the_question[\u3069\u3053\u304b\u3089\u8ab0\u3078\uff1f-expected_roles1]`（before=passed）
- `tests.attack.test_semantic_wh_fabrication::test_roles_and_labels_are_taken_from_the_question[\u306a\u306b\u3067\u8ab0\u306b\u3002-expected_roles2]`（before=passed）
- `tests.attack.test_semantic_wh_fabrication::test_roles_and_labels_are_taken_from_the_question[\u8d77\u70b9\u3001\u53d7\u53d6\u4eba\u306f\uff1f-expected_roles4]`（before=passed）
- `tests.attack.test_semantic_wh_injection::test_role_noun_list_emits_the_role_mapping_from_the_contract`（before=passed）
- `tests.attack.test_semantic_wh_injection::test_wh_role_question_emits_only_the_requested_roles`（before=passed）
- `tests.attack.test_semantic_wh_limits::test_role_nouns_build_their_declared_roles`（before=passed）
- `tests.attack.test_semantic_wh_long_documents::test_case_particle_aliases_keep_their_declared_roles[\u3069\u3053\u3067\u4f55\u304b\u3089-expected2]`（before=passed）
- `tests.attack.test_semantic_wh_long_documents::test_case_particle_aliases_keep_their_declared_roles[\u306a\u306b\u3078\u8ab0\u3067-expected3]`（before=passed）
- `tests.attack.test_semantic_wh_long_documents::test_case_question_accepts_optional_question_ending`（before=passed）
- `tests.attack.test_semantic_wh_long_documents::test_role_noun_list_builds_roles_in_question_order`（before=passed）
- `tests.attack.test_semantic_wh_negation_modality::test_role_noun_question_accepts_other_distinct_roles`（before=passed）
- `tests.attack.test_semantic_wh_negation_modality::test_wh_origin_and_recipient_question_keeps_role_order`（before=passed）
- `tests.attack.test_semantic_wh_paraphrase::test_patient_to_recipient_particle_changes_the_plan`（before=passed）
- `tests.attack.test_semantic_wh_paraphrase::test_recipient_role_noun_variants_preserve_the_role_plan`（before=passed）
- `tests.attack.test_semantic_wh_realtext::test_origin_and_recipient_particles_are_preserved_in_order`（before=passed）
- `tests.attack.test_semantic_wh_realtext::test_role_noun_synonyms_map_to_agent_and_recipient`（before=passed）
- `tests.attack.test_semantic_wh_realtext::test_role_nouns_map_patient_and_origin`（before=passed）
- `tests.attack.test_semantic_wh_realtext::test_wh_aliases_and_particle_map_to_agent_and_location`（before=passed）
- `tests.attack.test_semantic_wh_tense_time::test_role_only_questions_make_one_wildcard_plan[\u8ab0\u304c\u4f55\u3092\u3069\u3053\u3067\u8ab0\u306b\u3067\u3059\u304b\u3002-asked2]`（before=passed）
- `tests.attack.test_semantic_wh_tense_time::test_role_only_questions_make_one_wildcard_plan[\u8d77\u70b9\u3001\u7269\u3001\u7d42\u70b9\u306f\uff1f-asked4]`（before=passed）
- `tests.attack.test_semantic_wh_unicode_noise::test_hiragana_wh_forms_and_location_particle_are_read_faithfully`（before=passed）
- `tests.attack.test_semantic_wh_unicode_noise::test_role_noun_list_builds_wildcard_roles_and_keeps_surface_labels`（before=passed）
- `tests.test_semantic_measure::test_tense_mismatch_does_not_answer[\u30df\u30aa\u306f\u672c\u3092\u8aad\u3080\u3002-\u8ab0\u304c\u672c\u3092\u8aad\u3093\u3060\uff1f]`（before=passed）
- `tests.test_semantic_measure::test_tense_mismatch_does_not_answer[\u30df\u30aa\u306f\u672c\u3092\u8aad\u3093\u3060\u3002-\u8ab0\u304c\u672c\u3092\u8aad\u3080\uff1f]`（before=passed）

  - 参考: w_question_forms2 の受入デモ `tools/demo_question_forms.py` は、自分のコミット 9c89f1e では `DEMO OK`、その 2 ファイルを統合ツリーに載せると AssertionError（`qf2_demo_check.txt`）。constructions パッケージは全モジュールを自動発見するため、後から入った p_* の読みが semantic_wh の挙動に影響する。これは既知の穴であり、直さない。

## 4. 回帰なし（G3）

`g3_compare.txt`（before_junit.xml と after_junit.xml の比較。`tools/w0_1_compare_runs.py`）:

- `G3 NEW_FAIL=0`、終了コード 0。after で failed/error のテストはすべて before でも failed/error（または before で収集エラーだったモジュールのテスト）。
- before の失敗 164 件（ID）の行き先（`g3_compare.txt` の RECONCILIATION）: after でも失敗 123、after で passed 23、after で skipped 17、ID が改名で消えたもの 1（= 164）。after の失敗 124 件 = 123 + 1（before で収集エラーだったモジュールの `test_query_delimiters_and_line_breaks_stay_inside_the_json_string`）。
- `PASS_TO_SKIP` = 0（before で通っていたテストが skip になったものは無い）、`PASS_TO_XFAIL` = 0、`MISSING_IN_AFTER` = 0（改名 2 件を解決した後）。この 3 つは第 3 ラウンドから門番の終了コードにも反映される（下の「門番の規則」）。
- `FAIL_TO_SKIP` = 17（before で失敗 → after で ENV_MISSING の skip。内訳 node_jitless_quiet 9、node 8）。**これは「失敗を環境不足へ移した」件数であり、7 節で個別に根拠を示す。** node が PATH にあれば node の 8 件は走って通る（`g3_compare_with_node.txt`: skipped が 28 → 20、passed が 3672 → 3680、`G3 NEW_FAIL=0`）。
- `FIXED` = 24（before で失敗 → after で通る）。テストファイル別: test_verifier_agents 14、test_memory_revalidate 3、test_semantic_unknown_choice 1、tests/attack/test_semantic_unknown_choice_* 6（`g3_compare.txt` の FIXED 節）。before で `NameError: name 'pytest' is not defined` だったもの（`before_pytest.txt`。limits と realtext の分）は `import pytest` の追加で通る。それ以外は wave5 の r_verifier／r_memory が持ち込んだ製品・テストの変更に由来しうる。どちらによるかの切り分けはしていない。
  - **訂正（第 2 ラウンド）**: 第 1 ラウンドの文書は 25 件・test_memory_revalidate 4 件と書いていた。比較ツールが改名テストを「旧名の全ケースのうち最悪の状態」と比べており、旧 `test_missing_or_unknown_witness_is_unverifiable_and_answerable[None]`（before で passed）に対応する新 `..._with_safe_answerability[None-True]` まで「before で失敗」扱いにしていたため。ツールをケース単位の対応づけに直した（下の「改名の扱い」）。旧出力は `g3_compare.txt` に残っていない（上書きした）が、差分は `[None-True]` の 1 行（FIXED 25 → 24、RENAMED 節にケース対応が追加）だけで、`G3 NEW_FAIL=0` は変わらない。
- `ONLY_IN_AFTER` = 3（wave5 が追加したテスト 2 件分: `test_passing_verdict_without_rerunnable_evidence_is_unverified` 1、`test_reported_verdict_never_decides_completion` 2 ケース。いずれも passed）。
- **改名の扱い（ケース単位）**: `tools/w0_1_compare_runs.py` は、改名された 2 テスト（r_verifier `d25a73a`／r_memory `6febe16` が持ち込んだもの）の各ケースを、対応する before のケース 1 件とだけ比べる。対応は、param id が同じならそれ、無ければ「新 param id が旧 param id ＋ `-` で始まる」唯一の旧ケース（r_memory は `parametrize('witness')` を `parametrize('witness, answerable')` に変えたので `None-True` ← `None`、`witness1-False` ← `witness1`）。対応が 0 件または複数のケースは「before に無い」として扱い、after で失敗なら NEW_FAIL にする。対応表は `g3_compare.txt` の RENAMED 節に 8 ケース分（6 + 2）が出る。
- **門番の規則（第 3 ラウンドで追加。`tools/w0_1_compare_runs.py` の先頭の説明にも同じ文）**: NEW_FAIL に加え、次を終了コード 1 にする。(1) **after で収集エラーになったモジュール**: before で収集エラーでなかったものは 1 件ずつ `COLLECTION_ERROR <module> [error; before=collected|ABSENT]` として NEW_FAIL に数える。before でも収集エラーだったモジュールは before の失敗側として別見出しに載せる（before 側の規則と対称）。第 2 ラウンドのレビューは、after で 1 モジュールが収集エラーになってテストが丸ごと消えても `G3 NEW_FAIL=0`・exit 0 になる欠陥を合成入力で示した。(2) `MISSING_IN_AFTER`（改名を解決した後に before にあって after に無いケース。G4 は関数を数えるだけで parametrize のケースは展開しないため、この消え方は G4 では捕まらない）。(3) `PASS_TO_XFAIL`。(4) 資源名の無い（`ENV_MISSING[...]` でない）`PASS_TO_SKIP`。(2)〜(4) は末尾の直前の行 `G3 GATES MISSING_IN_AFTER=<n> PASS_TO_XFAIL=<n> PASS_TO_SKIP_UNCLASSIFIED=<n>` に出る。最終行は従来どおり `G3 NEW_FAIL=<n>`。この実データでは、4 本の比較出力（`g3_compare.txt`、`g3_compare_with_node.txt`、`g3_compare_with_quiet_node.txt`、`qf2_trial_compare.txt`）のうち統合ツリー側の 3 本は `AFTER_COLLECTION_ERROR_BUT_BEFORE_COLLECTION_ERROR (0)`、`G3 GATES` の 3 つとも 0、`G3 NEW_FAIL=0`、exit 0 で、第 2 ラウンドまでの出力との差は「見出し 1 つと GATES 行 1 つが増えた」だけ（`diff` で確かめた）。参考の `qf2_trial_compare.txt`（取り込まなかった w_question_forms2 を載せた試行）は `PASS_TO_XFAIL=1`（`tests.attack.test_semantic_verify_fabrication::test_correction_does_not_leave_the_superseded_actor_as_an_answer`）と `G3 NEW_FAIL=34`・exit 1 で、NEW_FAIL の 34 件は変わらない。
- **門番の自己試験**（`tools/w0_1_compare_selftest.py`、出力 `g3_rename_selftest.txt`、13 ケース、`SELFTEST PASS`）: after の junit のコピーを 1 か所ずつ変えて比較ツールを走らせ、`G3 NEW_FAIL=`・`G3 GATES`・終了コードを期待と突き合わせる。(E) 変更なし → NEW_FAIL=0、exit 0。(A) before で passed だった改名ケース `[None-True]` が失敗 → NEW_FAIL=1、exit 1（第 1 ラウンドの見逃しの再現）。(B) before で failed だった改名ケース `[witness1-False]` → NEW_FAIL=0。(C) 旧ケースに対応しない param id の改名ケース → NEW_FAIL=1（before=ABSENT）。(D) もう一方の改名テストの 1 ケース → NEW_FAIL=1。(F) 改名でないテスト → NEW_FAIL=1。**第 3 ラウンドで追加**: (G) before で収集できていたモジュール `tests.test_verifier_agents` の全ケースを 1 件の収集エラーに置き換え → `COLLECTION_ERROR ... before=collected`、NEW_FAIL=1、exit 1（第 2 ラウンドのレビューの再現）。(H) before でも収集エラーだったモジュール → NEW_FAIL=0、exit 0（before の失敗側）。(I) before に無いモジュールの収集エラー → NEW_FAIL=1（before=ABSENT）。(J) passed のケースを 1 件消す → MISSING_IN_AFTER=1、exit 1。(K) passed のケースが xfailed → PASS_TO_XFAIL=1、exit 1。(L) passed のケースが資源名の無い skip → PASS_TO_SKIP_UNCLASSIFIED=1、exit 1。(M) passed のケースが `ENV_MISSING[...]` の skip → すべて 0、exit 0（許可・一覧に載る）。(E)〜(F) の NEW_FAIL と exit は第 2 ラウンドの出力と同じ。C だけ、改名したケースが旧ケースに対応しなくなるため `MISSING_IN_AFTER=1` が加わる（NEW_FAIL=1、exit 1 は不変）。合成 junit は `artifacts/w0-1/tmp/selftest/` に作り、終了時に消す。
- **before で収集エラーだった paraphrase テストの扱いの測定**: `tests/attack/test_semantic_unknown_choice_paraphrase.py` は before では収集エラーで、15 ケースが before の ID に無い。そのうち after で失敗するのは `test_query_delimiters_and_line_breaks_stay_inside_the_json_string` 1 件で、これを「before 失敗側」に数えている。これが統合による回帰ではないことの測定: `git archive dev` の複製で、**変更を `import pytest` の 1 行だけ**にして（製品コードは dev そのまま）このファイルを走らせると `1 failed, 14 passed`、失敗は同じテスト（`paraphrase_dev_import_only.txt`）。after の失敗 124 件にも同じテストが入っている（`g3_compare.txt` の AFTER_FAILED_BUT_BEFORE_COLLECTION_ERROR 節）。

## 5. テストの保全（G4）と wave5 の期待値変更

`test_inventory.txt`（`tools/w0_1_count_tests.py`: AST で `tests/**/test_*.py` のテスト関数・メソッドを数える。parametrize は展開しない）:

- テスト関数 dev 2704 → after 2706。dev にあって after に無い名前は 2 件（改名のみ）、after にだけある名前は 4 件（改名先 2 + 新規 2）。`G4 before=2704 after=2706 delta=2 unexplained_missing=0 reduced=0`。
- 改名（台帳 unit r_verifier／r_memory が持ち込んだもの）:
  - `tests/test_verifier_agents.py::test_parse_accepts_recheckable_evidence_reference` → `..._test_parse_accepts_legacy_evidence_reference_as_testimony`（6 ケース → 6 ケース）
  - `tests/test_memory_revalidate.py::test_missing_or_unknown_witness_is_unverifiable_and_answerable` → `..._unverifiable_with_safe_answerability`（2 ケース → 2 ケース。パラメータが `witness` から `witness, answerable` へ）
- テスト以外のファイルの変更（環境マーカー等）は `git diff dev -- tests` で assert・期待値・パラメータが 1 つも変わっていないことを確認（wave5 の 2 ファイルを除く）。
- **wave5 が書き換えた期待値（`git diff dev -- tests/test_verifier_agents.py tests/test_memory_revalidate.py` の hunk ごと）。判定欄が「弱化の疑い」のものは中間職の判断を仰ぐ。**

| # | ファイル::テスト | 変更前 | 変更後 | 判定 | 根拠（製品コード） |
|---|---|---|---|---|---|
| M1 | test_memory_revalidate::test_text_witness_is_checked_against_current_file | `(id in records) == (expected == 'FRESH')` | `id not in records` かつ `verdict != 'ANSWER'` | 製品仕様への追随（FRESH 時の期待が反転。安全側への変更だが、FRESH のとき answerable を確認する assert は無くなった。**反転なので中間職が確認**） | 追加コメント「needle の存在だけでは無関係なファイル本文が事実の証拠にならない」。製品側の差分は `semantic_unknown_choice.py` と `verifier_agents.py` 1 行のみで、memory_revalidate の製品コードは dev のまま（= dev のテストが dev の製品に対して古かった。before で 3 件が失敗していた `before_pytest.txt`） |
| M2 | test_memory_revalidate::test_missing_or_unknown_witness_… | 2 ケースとも `'legacy' in records` | `witness=None` は True、`{'kind':'unknown'}` は False | 製品仕様への追随（改名＋パラメータ追加。未対応の witness 種別は答えの根拠にならない） | 同上。コメント「An unsupported witness kind cannot support an answer」 |
| V1 | test_verifier_agents::_verdict（補助関数） | 常に `evidence_ref` 文字列を持つ旧形式の verdict | 既定は構造化 `evidence`（command, expected）＋`opinion`。`evidence_ref` 指定時のみ旧形式 | 製品仕様への追随 | `verantyx/verifier_agents.py` `parse_verdict`（`{"type","result","evidence","opinion"}` を受理、旧形式は testimony） |
| V2 | `_file_evidence_runner`（新規補助関数） | — | root 配下の file/needle を検査する runner | 強化（テスト基盤の追加） | `run_verifiers(..., evidence_runner=...)` |
| V3 | test_passing_independent_verifier_completes_after_conductor_recheck | `len(calls) == 2` | `len(calls) == 3` ＋ `sum(kind == command) == 1` | 製品仕様への追随＋強化（証拠の再実行が 1 呼び出し増えた。追加 assert で内訳を固定） | コメント「The evidence re-run adds one call」 |
| V4 | test_verification_output_is_stored_as_testimony_not_fact | `evidence_ref.find(GOOD_EVIDENCE) >= 0` | audit JSON を読み `items[0].evidence.command == ["check-acceptance"]` ＋ `deterministic_result == "PASS"` | 製品仕様への追随（旧: 文字列を含む → 新: 構造化された再実行証拠を検査）。同等以上 | 同上 |
| V5 | test_passing_verdict_without_rerunnable_evidence_is_unverified | — | 新規テスト | 強化（新規） | 規則「再実行可能な証拠の無い PASS は UNVERIFIED」 |
| V6 | test_contradicting_verifiers_abstain_without_vote_pooling | `"abstains" in reason`、VERIFICATION レコードは**無い** | `"disagrees" in reason and "abstains" in reason`、VERIFICATION レコードが**ある**（`evidence_disagrees is True`、`deterministic_result == "UNVERIFIED"`） | 製品仕様への追随（`reply.kind == "ESCALATE"` は不変。レコードの有無の期待が反転） | `verifier_agents.py` `evidence_disagrees` |
| V7 | test_unanimous_fail_is_recorded_and_escalated | FAIL の verdict | FAIL の verdict に構造化 evidence（expected 1）を付与 | 製品仕様への追随（入力形式） | V1 と同じ |
| V8 | test_reported_verdict_never_decides_completion | — | 新規（2 ケース: 報告 FAIL でも再実行が 0 なら完了、報告 PASS でも再実行が 1 なら完了しない） | 強化（新規） | 「verifier は裁判官ではない」規則 |
| V9 | test_unsafe_or_missing_artifact_cannot_complete_task | 2 ケースとも VERIFICATION レコードは**無い** | `../outside.json` は従来どおり無し、`missing.json` は FAIL レコードが**ある**（`deterministic_result == "UNVERIFIED"`） | 製品仕様への追随（`ESCALATE` と `UNVERIFIED in reason` は不変。**一方のケースで「無い」→「ある」に反転**したので確認を仰ぐ） | コメント「Legacy references remain testimony, so an unreplayable claim is recorded as FAIL」 |
| V10 | test_missing_plain_file_evidence_cannot_complete_task | 旧形式 evidence_ref、VERIFICATION レコード**無し** | 構造化 file evidence ＋ runner、FAIL レコードが**ある** | 製品仕様への追随（V9 と同型） | コメント「A failed deterministic re-run is retained as a typed FAIL testimony record」 |
| V11 | test_artifact_evidence_must_be_readable_under_allowed_root | `artifact_root=tmp_path`（旧形式 `artifact:checked.json`） | 構造化 file evidence ＋ `evidence_runner=_file_evidence_runner(tmp_path)` | 製品仕様への追随（入力形式） | V2 |
| V12 | test_plain_file_evidence_must_be_readable_under_allowed_root | 同上 | 同上 | 製品仕様への追随（入力形式） | V2 |
| V13 | test_brief_quotes_injection_text_as_untrusted_record_data | `index("UNTRUSTED_DATA_JSON") < index("Never return PASS without")` | `... < index("Supply one or more deterministic evidence")` | 製品仕様への追随（順序検査は同じ、基準の文言が製品の brief の文言に追随）。`verantyx/verifier_agents.py:184` に新しい文言がある。**基準の文言が変わっただけで順序の検査自体は同等** | `verifier_agents.py:184` |
| V14 | test_parse_accepts_legacy_evidence_reference_as_testimony（旧 …recheckable…） | 改名前: 旧形式 ref を受理 | 改名 ＋ `assert not verdict.evidence` を追加 | 強化 | コメント「Reference strings are backward-compatible testimony, not re-runnable evidence」 |
| V15 | test_deterministic_witness_is_rechecked_after_verdict | `len(calls) == 2`、`all(call["command"] == [...] for call in calls)` | `len(calls) == 3`、`sum(kind==command)==1`、`all(... for call in calls if "expected_exit" in call)` | **弱化の疑い**（`all(...)` の対象を「`expected_exit` を持つ呼び出し」に絞った。証拠再実行の呼び出しは `sum(...)==1` で個数だけ担保し、その command の中身は検査していない。一方 `len` と `sum` が追加されている）。中間職の判断を仰ぐ | V3 と同じ |
| V16 | test_new_verifier_result_supersedes_previous_record | FAIL の verdict | FAIL の verdict に構造化 evidence（expected 1）を付与 | 製品仕様への追随（入力形式） | V1 |
| V17 | test_post_verification_witness_failure_prevents_done | 呼び出し記録 `calls` を witness の判定に共用 | 専用リスト `witness_calls` に分離 | 同等（証拠の再実行が `calls` に入るようになった分を切り離した） | V3 |

- 判定の根拠は上の hunk と製品コードの該当行から私が読んだもの。**テスト関数の assert を弱めたと断定できるもの（弱化）は無いが、「弱化の疑い」が 1 件（V15）、期待の反転が 3 件（M1, V6, V9/V10）ある。** wave5 の 2 unit を取り込む判断は、この 4 点が「製品仕様への追随」として許容されることに依存する。自分では黙って入れも外しもせず、中間職のレビューに回した。

- **中間職の判断（第 1 ラウンドのレビュー `review.r1.md` より）: wave5 の 2 unit（r_memory `6febe16`、r_verifier `d25a73a`）は取り込んだままとする。** 期待が反転した M1・M2・V6・V9・V10 のテストは、dev の製品に対してすでに失敗していた（`before_junit.xml` で該当の 3 + 1 + 3 + 1 + 1 件が failed）。製品側の変更は `verifier_agents.py` の 1 行（`checks.sort(...)`）と `semantic_unknown_choice.py` だけで、反転に関わる memory_revalidate と verifier の振る舞いは dev 時点の製品のまま。台帳で merged と記録された unit が、古くなっていたテストを製品に合わせたものと判断し、このチケットの禁止事項「実装役が期待値を弱める」には当たらない。V15（`all(...)` を `if "expected_exit" in call` で絞った件）は、実際の呼び出し列（`[{'command': ['check-acceptance'], 'expected_exit': 0}, {'kind': 'command', 'command': ['check-acceptance']}, {'command': [...], 'expected_exit': 0}]`）を出力して確かめた結果、証拠を再実行する呼び出しの command も `check-acceptance` で、絞り込みが外すのは同じ値を持つ 1 件だけ、代わりに `len(calls) == 3` と `sum(kind == command) == 1` が加わっているため、弱化に当たらず実質は同等とされた。

## 6. after の失敗 124 件の原因分類

分類は 5 種: 製品の不具合／テストの配置依存／環境不足／期待値の古さ／分類保留(UNKNOWN_CAUSE)。`tools/w0_1_failure_table.py` が `after_junit.xml` と `probe_stale.txt` から作る（出力 `failure_table.md`）。
**期待値の古さ**は「テスト側だけを機械的に変えた（製品を触らない）コピーで通る」と probe が示したものだけ。製品側のコピーも変えた probe は含めない。**製品の不具合**と**環境不足**は、失敗しているテストについては根拠が成り立たないので 0 件（ここにあるのは「分からない」と「古い期待値」だけ）。迷ったものは分類保留。

集計（`failure_table.md` 冒頭）:

failed testcases: 124
- group=memory_brief category=分類保留(UNKNOWN_CAUSE): 44
- group=names category=分類保留(UNKNOWN_CAUSE): 3
- group=names category=期待値の古さ: 19
- group=other category=分類保留(UNKNOWN_CAUSE): 32
- group=predicate_span category=期待値の古さ: 11
- group=reader category=分類保留(UNKNOWN_CAUSE): 15
- totals: 分類保留(UNKNOWN_CAUSE)=94, 期待値の古さ=30

before 比: before の失敗 164 件のうち 123 件が after でも失敗し（同じ ID）、1 件が収集エラーだったモジュールのテストとして加わる（4 節）。

#### 群 `other` ／ 分類保留(UNKNOWN_CAUSE) ／ 32件

根拠: no probe and no ledger decision; cause not investigated beyond the failure message in after_junit.xml

- `tests.attack.test_conductor_escalate_realtext::test_reask_citation_must_name_an_active_record_and_then_closes` — 失敗メッセージの先頭行: `AssertionError: assert False is True`
- `tests.attack.test_conductor_escalate_realtext::test_repeated_resolution_check_does_not_duplicate_resolved_ledger_entry` — 失敗メッセージの先頭行: `AssertionError: assert False is True`
- `tests.attack.test_memory_frame_limits::test_empty_memory_returns_unknown_without_mutating_log` — 失敗メッセージの先頭行: `AssertionError: assert {'verdict': '..._classes': {}} == {'verdict': '...'records': []}`
- `tests.attack.test_memory_merge_differential::test_canonical_order_and_exact_duplicate_removal` — 失敗メッセージの先頭行: `AssertionError: assert [{'op': 'writ...ote', 'z': 1}] == [{'op': 'writ...ote', 'z': 1}]`
- `tests.attack.test_memory_merge_fabrication::test_partial_supersession_link_stays_pending_until_target_record_arrives` — 失敗メッセージの先頭行: `AssertionError: assert ['new', 'old'] == ['new']`
- `tests.attack.test_memory_merge_injection::test_instruction_payload_cannot_hide_a_dangling_supersession` — 失敗メッセージの先頭行: `Failed: DID NOT RAISE ValueError`
- `tests.attack.test_memory_merge_injection::test_instruction_text_does_not_make_a_supersession_cycle_valid` — 失敗メッセージの先頭行: `Failed: DID NOT RAISE ValueError`
- `tests.attack.test_memory_merge_limits::test_active_records_reject_dangling_supersession_reference` — 失敗メッセージの先頭行: `Failed: DID NOT RAISE ValueError`
- `tests.attack.test_memory_revalidate_injection::test_confusable_unknown_witness_kind_does_not_become_fresh` — 失敗メッセージの先頭行: `AssertionError: assert 'UNKNOWN_NO_EVIDENCE' == 'ANSWER'`
- `tests.attack.test_memory_revalidate_injection::test_instruction_text_in_document_is_only_a_literal_witness_check` — 失敗メッセージの先頭行: `AssertionError: assert 'UNKNOWN_NO_EVIDENCE' == 'ANSWER'`
- `tests.attack.test_memory_revalidate_injection::test_matching_file_hash_keeps_only_the_grounded_value` — 失敗メッセージの先頭行: `AssertionError: assert ['source.txt', 'source.txt'] == ['source.txt']`
- `tests.attack.test_memory_revalidate_paraphrase::test_fresh_text_witness_keeps_its_record_answerable` — 失敗メッセージの先頭行: `AssertionError: assert 'UNKNOWN_NO_EVIDENCE' == 'ANSWER'`
- `tests.attack.test_semantic_coord_negation_modality::test_adjectival_naku_then_te_is_structurally_accepted` — 失敗メッセージの先頭行: `AssertionError: assert False`
- `tests.attack.test_semantic_coord_unicode_noise::test_te_comma_chain_is_accepted` — 失敗メッセージの先頭行: `AssertionError: assert False`
- `tests.attack.test_semantic_reader_realtext::test_quantifier_scope_is_retained_as_unsupported` — 失敗メッセージの先頭行: `AssertionError: assert 2 == 1`
- `tests.attack.test_semantic_unknown_choice_paraphrase::test_query_delimiters_and_line_breaks_stay_inside_the_json_string` — 失敗メッセージの先頭行: `assert '語: 「"flarn\\n0: {\\"term\\":\\"gadget\\"}"」' in '次の語は、下の候補のどれに意味が最も近いですか。\n語: 「"flarn\\\\n0: {\\\\"ter`
- `tests.attack.test_semantic_unknown_differential::test_source_word_counts_toward_projection_budget` — 失敗メッセージの先頭行: `AssertionError: assert 'CANDIDATES' == 'BUDGET_REFUSAL'`
- `tests.attack.test_semantic_unknown_fabrication::test_budget_below_clause_and_role_work_floor_refuses` — 失敗メッセージの先頭行: `AssertionError: assert 'CANDIDATES' == 'BUDGET_REFUSAL'`
- `tests.attack.test_semantic_unknown_fabrication::test_constructed_neighbour_candidate_is_not_answer_or_evidence` — 失敗メッセージの先頭行: `assert False`
- `tests.attack.test_semantic_unknown_paraphrase::test_changed_compound_meaning_changes_the_constructed_route` — 失敗メッセージの先頭行: `AssertionError: assert 'NO_REACH' == 'KIN_NEIGHBOURHOOD'`
- `tests.attack.test_semantic_unknown_paraphrase::test_entity_swap_changes_the_available_neighbourhood` — 失敗メッセージの先頭行: `AssertionError: assert 'NO_REACH' == 'KIN_NEIGHBOURHOOD'`
- `tests.attack.test_semantic_verify_negation_modality::test_double_negation_is_not_licensed_as_an_ordinary_negative_fact` — 失敗メッセージの先頭行: `AssertionError: assert ()`
- `tests.attack.test_semantic_verify_negation_modality::test_hearsay_clause_is_not_licensed_as_an_assertion` — 失敗メッセージの先頭行: `assert False`
- `tests.attack.test_semantic_verify_unicode_noise::test_symbolic_record_licenses_unicode_actor_without_normalization` — 失敗メッセージの先頭行: `verantyx.semantic_verify.Rejected: instruction assertion: non-atomic symbolic value`
- `tests.attack.test_verifier_agents_differential::test_brief_matches_independent_renderer_for_generated_untrusted_specs` — 失敗メッセージの先頭行: `assert 'VERIFIER BRI...ith expected.' == 'VERIFIER BRI...evidence_ref.'`
- `tests.attack.test_verifier_agents_fabrication::test_parse_verdict_rejects_unscoped_or_vague_references[../private.txt]` — 失敗メッセージの先頭行: `AssertionError: Regex pattern did not match.`
- `tests.attack.test_verifier_agents_fabrication::test_parse_verdict_rejects_unscoped_or_vague_references[a/../private.txt]` — 失敗メッセージの先頭行: `AssertionError: Regex pattern did not match.`
- `tests.attack.test_verifier_agents_fabrication::test_parse_verdict_rejects_unscoped_or_vague_references[verified]` — 失敗メッセージの先頭行: `AssertionError: Regex pattern did not match.`
- `tests.attack.test_verifier_agents_fabrication::test_run_verifiers_records_references_with_their_verifier_identities` — 失敗メッセージの先頭行: `AssertionError: assert 'FAIL' == 'PASS'`
- `tests.attack.test_verifier_agents_injection::test_brief_keeps_nested_quotes_and_unicode_inside_the_json_data` — 失敗メッセージの先頭行: `AssertionError: assert 'Return FAIL if the check does not pass.' in 'VERIFIER BRIEF v1\nYou are an independent`
- `tests.attack.test_verifier_agents_limits::test_unanimous_verification_evidence_is_order_independent` — 失敗メッセージの先頭行: `AssertionError: assert None == 'done'`
- `tests.test_p4_abilities::test_speech_act_drafts_fill_new_roles_and_reread` — 失敗メッセージの先頭行: `AssertionError: assert ('generation' == 'generation'`

#### 群 `memory_brief` ／ 分類保留(UNKNOWN_CAUSE) ／ 32件

根拠: probe: still fails even after the copy's ask_about stub returns verdict=ANSWER and compile_brief returns .text; the expected text and the product's text differ in content

- `tests.attack.test_memory_brief_differential::test_askable_and_unaskable_records_are_accounted_for`
- `tests.attack.test_memory_brief_differential::test_budget_uses_python_character_length_and_reports_omissions`
- `tests.attack.test_memory_brief_differential::test_deterministic_generated_cases_match_naive_reference`
- `tests.attack.test_memory_brief_differential::test_kind_timestamp_and_id_order_break_ties`
- `tests.attack.test_memory_brief_differential::test_later_short_candidate_can_fit_after_earlier_long_candidate_is_skipped`
- `tests.attack.test_memory_brief_differential::test_nfkc_casefolded_focus_ranks_matching_record_first`
- `tests.attack.test_memory_brief_differential::test_source_membership_and_lesson_question_shape_control_askability`
- `tests.attack.test_memory_brief_differential::test_superseded_records_disappear_and_closed_tasks_stay_dropped`
- `tests.attack.test_memory_brief_fabrication::test_focus_changes_order_without_changing_supported_sentences`
- `tests.attack.test_memory_brief_fabrication::test_lesson_uses_its_situation_and_response_role_for_source_check`
- `tests.attack.test_memory_brief_fabrication::test_negation_in_supported_sentence_is_preserved_verbatim`
- `tests.attack.test_memory_brief_fabrication::test_same_attribute_for_two_entities_keeps_each_source_attached`
- `tests.attack.test_memory_brief_fabrication::test_superseded_record_is_not_rendered_or_counted_as_active_input`
- `tests.attack.test_memory_brief_fabrication::test_supported_record_is_rendered_verbatim_with_its_id`
- `tests.attack.test_memory_brief_injection::test_embedded_instruction_stays_attributed_to_its_record`
- `tests.attack.test_memory_brief_injection::test_focus_ranks_matches_without_admitting_uncited_records`
- `tests.attack.test_memory_brief_injection::test_superseded_record_is_excluded_from_brief_and_accounting`
- `tests.attack.test_memory_brief_injection::test_typed_kind_priority_precedes_input_order`
- `tests.attack.test_memory_brief_limits::test_concurrent_readers_return_the_same_brief`
- `tests.attack.test_memory_brief_limits::test_dropped_ids_are_reported_when_selected_line_fits`
- `tests.attack.test_memory_brief_limits::test_exact_character_budget_includes_full_selected_line`
- `tests.attack.test_memory_brief_limits::test_focus_uses_nfkc_casefold_matching_to_rank_first`
- `tests.attack.test_memory_brief_limits::test_record_order_is_independent_of_active_order_and_kind_priority`
- `tests.attack.test_memory_brief_limits::test_repeated_calls_are_idempotent_and_do_not_mutate_records`
- `tests.attack.test_memory_brief_limits::test_superseded_ids_are_excluded_from_output_and_drop_accounting`
- `tests.attack.test_memory_brief_paraphrase::test_closed_task_is_omitted_and_accounted_for`
- `tests.attack.test_memory_brief_paraphrase::test_entity_swap_is_reflected_in_the_rendered_record`
- `tests.attack.test_memory_brief_paraphrase::test_focus_normalizes_width_and_case`
- `tests.attack.test_memory_brief_paraphrase::test_focus_precedes_kind_priority`
- `tests.attack.test_memory_brief_paraphrase::test_number_swap_is_reflected_in_the_rendered_record`
- `tests.attack.test_memory_brief_paraphrase::test_polite_and_plain_wording_keep_the_same_focused_record`
- `tests.attack.test_memory_brief_paraphrase::test_superseded_record_is_removed_before_dropped_accounting`

#### 群 `memory_brief` ／ 分類保留(UNKNOWN_CAUSE) ／ 12件

根拠: probe: passes only in a copy where the PRODUCT's compile_brief is also wrapped to return .text, so a test-side-only fix is not shown (the product returns a ContextBrief object, the test expects str); which side is intended is undecided

- `tests.attack.test_memory_brief_differential::test_empty_memory_and_budget_validation`
- `tests.attack.test_memory_brief_differential::test_nonaskable_records_are_never_rendered_as_answers`
- `tests.attack.test_memory_brief_fabrication::test_budget_can_fit_drop_accounting_without_partial_record_text`
- `tests.attack.test_memory_brief_fabrication::test_closed_task_is_not_emitted_and_its_id_is_reported`
- `tests.attack.test_memory_brief_fabrication::test_record_without_ask_path_source_is_dropped_and_accounted_for`
- `tests.attack.test_memory_brief_injection::test_closed_task_is_dropped_and_reported`
- `tests.attack.test_memory_brief_injection::test_compatibility_unicode_closed_state_is_normalized`
- `tests.attack.test_memory_brief_injection::test_question_path_failure_does_not_promote_record`
- `tests.attack.test_memory_brief_injection::test_record_is_omitted_when_question_path_does_not_cite_it`
- `tests.attack.test_memory_brief_limits::test_empty_memory_returns_empty_brief_at_zero_budget`
- `tests.attack.test_memory_brief_paraphrase::test_empty_memory_returns_empty_string`
- `tests.attack.test_memory_brief_paraphrase::test_unaskable_record_is_accounted_for_as_dropped`

#### 群 `names` ／ 期待値の古さ ／ 19件

根拠: probe: passes in a copy when the test stubs' pos2 `一般` is changed to `普通名詞`; verantyx/semantic_names.py:40 requires `普通名詞` (also what the installed unidic-lite emits)

- `tests.attack.test_semantic_names_differential::test_generated_name_splits_match_independent_reference`
- `tests.attack.test_semantic_names_fabrication::test_name_split_accepts_kanji_descriptor_and_one_proper_name`
- `tests.attack.test_semantic_names_limits::test_concurrent_independent_readers_do_not_share_results`
- `tests.attack.test_semantic_names_limits::test_large_cover_and_pathological_long_nonkanji_prefix_are_bounded`
- `tests.attack.test_semantic_names_limits::test_repeated_calls_are_idempotent_and_do_not_mutate_inputs`
- `tests.attack.test_semantic_names_long_documents::test_covering_selects_exact_span_from_a_long_sentence`
- `tests.attack.test_semantic_names_long_documents::test_name_split_accepts_multiple_kanji_title_tokens`
- `tests.attack.test_semantic_names_long_documents::test_repeated_entities_and_conflicting_titles_stay_document_local`
- `tests.attack.test_semantic_names_negation_modality::test_name_split_can_extract_exact_title_name_pair_in_negative_context`
- `tests.attack.test_semantic_names_paraphrase::test_entity_swap_keeps_split_shape_and_returns_the_swapped_name`
- `tests.attack.test_semantic_names_paraphrase::test_kanji_title_and_proper_name_split`
- `tests.attack.test_semantic_names_paraphrase::test_particle_and_clause_surface_changes_leave_the_name_split_unchanged`
- `tests.attack.test_semantic_names_realtext::test_name_split_accepts_kanji_title_and_one_proper_name`
- `tests.attack.test_semantic_names_tense_time::test_name_split_accepts_a_kanji_title_before_a_proper_name`
- `tests.attack.test_semantic_names_unicode_noise::test_name_split_accepts_kanji_title_plus_one_proper_name`
- `tests.attack.test_semantic_names_unicode_noise::test_name_split_preserves_decomposed_combining_sequence`
- `tests.attack.test_semantic_names_unicode_noise::test_name_split_preserves_fullwidth_name_surface`
- `tests.attack.test_semantic_names_unicode_noise::test_name_split_preserves_markup_and_emoji_in_tagged_name`
- `tests.attack.test_semantic_names_unicode_noise::test_tokens_covering_uses_python_codepoint_offsets_around_astral_noise`

#### 群 `names` ／ 分類保留(UNKNOWN_CAUSE) ／ 3件

根拠: probe: still fails after 一般->普通名詞 in the test stubs. The test treats a suffix token (接尾辞) as part of the title; verantyx/semantic_names.py:39 says prefixes and suffixes are deliberately not descriptors. Which side is intended is undecided

- `tests.attack.test_semantic_names_differential::test_name_split_accepts_kanji_title_appositive`
- `tests.attack.test_semantic_names_limits::test_name_split_accepts_kanji_title_and_one_proper_name`
- `tests.attack.test_semantic_names_paraphrase::test_split_accepts_a_common_noun_followed_by_a_noun_suffix`

#### 群 `predicate_span` ／ 期待値の古さ ／ 11件

根拠: probe: all 30 tests of the two files pass in a copy when the test stubs gain a `predicate_span` attribute (AttributeError today)

- `tests.attack.test_semantic_unknown_injection::test_any_provenance_returned_for_hostile_source_is_a_valid_source_slice`
- `tests.attack.test_semantic_unknown_injection::test_document_instruction_cannot_expand_candidate_authority`
- `tests.attack.test_semantic_unknown_injection::test_question_instruction_does_not_count_as_a_held_ir_term`
- `tests.attack.test_semantic_unknown_injection::test_quoted_nested_agent_message_remains_typed_data`
- `tests.attack.test_semantic_unknown_injection::test_repeated_attacks_are_deterministic_and_do_not_mutate_input`
- `tests.attack.test_semantic_unknown_injection::test_unicode_instruction_variants_do_not_add_result_types`
- `tests.attack.test_semantic_unknown_limits::test_clause_and_role_order_do_not_change_report_json`
- `tests.attack.test_semantic_unknown_limits::test_constructed_outputs_are_typed_and_never_evidence`
- `tests.attack.test_semantic_unknown_limits::test_exact_projection_budget_is_not_refused`
- `tests.attack.test_semantic_unknown_limits::test_repeated_calls_are_idempotent`
- `tests.attack.test_semantic_unknown_limits::test_two_concurrent_readers_return_the_same_report`

#### 群 `reader` ／ 分類保留(UNKNOWN_CAUSE) ／ 15件

根拠: wave5 units r_reader_regress (hold) / r_reader_regress2 (unfinished) were created to decide regression-vs-outdated for exactly these files and never finished; no decision exists

- `tests.test_request_goal_route::test_unsupported_or_unverified_request_or_source_is_held[\u8cc7\u6599\u306e\u51fa\u6765\u4e8b\u3092\u96f6\u6587\u4ee5\u5185\u3067\u8a00\u3044\u63db\u3048\u3066\u304f\u3060\u3055\u3044\u3002-\u82b1\u5b50\u304c\u592a\u90ce\u306b\u8cc7\u6599\u3092\u6e21\u3057\u305f\u3002-licensed one-event surface does not satisfy the requested sentence count]` — 失敗メッセージの先頭行: `AssertionError: assert 'licensed one-event surface does not satisfy the requested sentence count' in 'producer`
- `tests.test_semantic_coordination_codex::test_concessive_main_clause_keeps_the_topic_subject` — 失敗メッセージの先頭行: `AssertionError: assert ('UNKNOWN_UNSUPPORTED_EVIDENCE' == 'ANSWER'`
- `tests.test_semantic_coordination_codex::test_plain_predicate_coordination_answers_clause_local_roles[te_location_first]` — 失敗メッセージの先頭行: `AssertionError: assert ('UNKNOWN_NO_EVIDENCE', []) == ('ANSWER', ['工房F'])`
- `tests.test_semantic_measure::test_kanji_title_before_a_name_is_split[\u30df\u30ca\u306f\u9752\u3044\u9375\u3092\u5009\u5eabC\u304b\u3089\u6280\u5e2b\u30e6\u30f3\u3078\u904b\u3093\u3060\u3002-\u8ab0\u3078\u904b\u3093\u3060\uff1f-expected0]` — 失敗メッセージの先頭行: `AssertionError: assert ('UNKNOWN_INVALID_PROOF', []) == ('ANSWER', ['ユン'])`
- `tests.test_semantic_measure::test_role_only_questions_generalize[\u30d2\u30ed\u306f\u8377\u7269\u3092\u99c5B\u304b\u3089\u30b5\u30ad\u3078\u5c4a\u3051\u305f\u3002-\u7269\u3001\u8d77\u70b9\u3001\u7d42\u70b9\u306f\uff1f-expected5]` — 失敗メッセージの先頭行: `AssertionError: assert ('UNKNOWN_NO_EVIDENCE', []) == ('ANSWER', ['荷物', '駅B', 'サキ'])`
- `tests.test_semantic_measure::test_role_only_questions_generalize[\u30d2\u30ed\u306f\u8377\u7269\u3092\u99c5B\u304b\u3089\u5e97\u9577\u30b5\u30ad\u3078\u5c4a\u3051\u305f\u3002-\u4f55\u3092\u3069\u3053\u304b\u3089\u8ab0\u3078\uff1f-expected3]` — 失敗メッセージの先頭行: `AssertionError: assert ('UNKNOWN_NO_EVIDENCE', []) == ('ANSWER', ['荷物', '駅B', 'サキ'])`
- `tests.test_semantic_measure::test_role_only_questions_generalize[\u30d2\u30ed\u306f\u8377\u7269\u3092\u99c5B\u304b\u3089\u5e97\u9577\u30b5\u30ad\u3078\u5c4a\u3051\u305f\u3002-\u7269\u3001\u8d77\u70b9\u3001\u7d42\u70b9\u306f\uff1f-expected6]` — 失敗メッセージの先頭行: `AssertionError: assert ('UNKNOWN_NO_EVIDENCE', []) == ('ANSWER', ['荷物', '駅B', 'サキ'])`
- `tests.test_semantic_measure::test_role_only_questions_generalize[\u30d2\u30ed\u306f\u8377\u7269\u3092\u99c5B\u304b\u3089\u5e97\u9577\u30b5\u30ad\u3078\u5c4a\u3051\u305f\u3002-\u8ab0\u304c\u4f55\u3092\u8ab0\u3078\uff1f-expected4]` — 失敗メッセージの先頭行: `AssertionError: assert ('UNKNOWN_INVALID_PROOF', []) == ('ANSWER', ['ヒロ', '荷物', 'サキ'])`
- `tests.test_semantic_measure::test_role_only_questions_generalize[\u30df\u30ca\u306f\u9752\u3044\u9375\u3092\u5009\u5eabC\u304b\u3089\u6574\u5099\u58eb\u30b3\u30a6\u3078\u904b\u3093\u3060\u3002-\u4f55\u3092\u3069\u3053\u304b\u3089\u8ab0\u3078\uff1f-expected1]` — 失敗メッセージの先頭行: `AssertionError: assert ('UNKNOWN_NO_EVIDENCE', []) == ('ANSWER', ['...庫C', '整備士コウ'])`
- `tests.test_semantic_measure::test_role_only_questions_generalize[\u30df\u30ca\u306f\u9752\u3044\u9375\u3092\u5009\u5eabC\u304b\u3089\u90e8\u9577\u7530\u4e2d\u3078\u904b\u3093\u3060\u3002-\u4f55\u3092\u3069\u3053\u304b\u3089\u8ab0\u3078\uff1f-expected0]` — 失敗メッセージの先頭行: `AssertionError: assert ('UNKNOWN_NO_EVIDENCE', []) == ('ANSWER', ['...倉庫C', '部長田中'])`
- `tests.test_semantic_measure::test_role_only_questions_generalize[\u30df\u30ca\u306f\u9752\u3044\u9375\u3092\u5009\u5eabC\u304b\u3089\u90e8\u9577\u7530\u4e2d\u3078\u904b\u3093\u3060\u3002-\u8ab0\u304c\u4f55\u3092\u3069\u3053\u304b\u3089\uff1f-expected2]` — 失敗メッセージの先頭行: `AssertionError: assert ('UNKNOWN_NO_EVIDENCE', []) == ('ANSWER', ['...'青い鍵', '倉庫C'])`
- `tests.test_semantic_public::test_unhandled_wh_is_not_yes_no_and_location_is_required` — 失敗メッセージの先頭行: `AssertionError: assert 'UNKNOWN_UNREAD' == 'UNKNOWN_NO_EVIDENCE'`
- `tests.test_semantic_realize::test_reader_case_roles_are_preserved[\u30de\u30ad\u306f\u5b66\u6821\u304b\u3089\u672c\u3092\u904b\u3093\u3060\u3002-origin]` — 失敗メッセージの先頭行: `AssertionError: assert 'origin' in {'agent', 'patient', 'source'}`
- `tests.test_semantic_realize::test_reader_case_roles_are_preserved[\u30de\u30ad\u306f\u5b66\u6821\u3067\u672c\u3092\u8aad\u3093\u3060\u3002-location]` — 失敗メッセージの先頭行: `AssertionError: assert 'location' in {'agent', 'patient', 'place'}`
- `tests.test_semantic_scope_safety::test_unrepresented_request_content_never_becomes_a_yes[\u30ca\u30aa\u306f\u5b66\u6821\u304b\u3089\u30ea\u30af\u306b\u9752\u9375\u3092\u6e21\u3057\u305f\u304b\uff1f]` — 失敗メッセージの先頭行: `AssertionError: assert 'UNKNOWN_NO_EVIDENCE' == 'UNKNOWN_UNREAD'`


- 読み手の群 D について: 台帳のとおり wave5 の unit r_reader_regress は hold、r_reader_regress2 は launch のまま終了しており、これらのテストが「回帰」か「古い期待値」かを決める作業は完了していない。決定が無いので分類保留。
- 群 A の 3 件（分類保留）: probe でもテスト側の `一般` → `普通名詞` の機械置換では通らない。テストは接尾辞（接尾辞トークン）を肩書の一部として受理することを期待し、`verantyx/semantic_names.py:39` のコメントは「接頭辞・接尾辞は束縛形態素であり記述語ではない」としている。どちらが意図かは決められない。
- 群 C について: probe（`probe_stale.txt`）は製品のコピーの `compile_brief` を `.text` を返すよう包み、スタブに `verdict=ANSWER` を返させた状態で 44 件中 12 件を通すが、製品側を変えているので「テスト側だけの古さ」とは言えない。残り 32 件は期待テキストと製品のテキストが内容として違う（例: 製品が `Dropped record ids: r1` を返す箇所でテストは `[id:r1...` を期待）。分類保留。
- 群 E（32 件）は probe も台帳の決定も無く、失敗メッセージの先頭行だけを付けた。原因は調べていない。

## 7. 環境不足（ENV_MISSING）一覧

after（node なし）で skip 28 件。skip の理由はすべて `ENV_MISSING[資源名]: 必要物` で始まる（`tests/_vera_env.py` の `RESOURCES` に資源名・必要物を書いてある）。skip の根拠（資源があれば実行されるか）:

| 資源 | 必要物 | 件数 | 資源があるとき走る証拠 |
|---|---|---:|---|
| `node` | PATH 上の `node` | 8 | `after_pytest_with_node.txt`: この 8 件が通る（skipped 28 → 20、passed 3672 → 3680。`g3_compare_with_node.txt`）。node の 8 件は before では `UNKNOWN_CODE_SPEC ... node is unavailable` の AssertionError で失敗していた（`before_junit.xml`） |
| `node_jitless_quiet` | PATH 上の node で、`--jitless --no-warnings` が stderr に何も出さないもの | 9 | **この機械の既定の node では走らない**。before ではこの 9 件は `/opt/homebrew/bin/node` 固定のため `FileNotFoundError` で失敗していた（`before_pytest.txt`）。この機械の node v22.17.0 は同コマンドで stderr に警告 1 行を出し（`versions.txt`）、テストは stderr を失敗扱いするため、資源が「欠けている」と分類した。stderr 判定は緩めていない。**警告の無い node があれば通ることの実測（第 2 ラウンドで追加）**: 実 node を実行しつつ警告 1 行だけを stderr から落とすラッパー（`quiet_node_shim.sh`。他の stderr 行・終了コード・stdout は素通し）を PATH の先頭に置き、**テストを 1 行も変えずに**全体を走らせた: `124 failed, 3689 passed, 11 skipped, 82 xfailed, 68 xpassed`（`after_pytest_with_quiet_node.txt`）。`tests/test_contract_lower.py` と `tests/test_round4.py` だけの実行は `51 passed`、skip 0（`contract_lower_round4_with_quiet_node.txt`）。この 9 件を含む ENV_MISSING[node]／[node_jitless_quiet] の 17 件はすべて passed になり、失敗集合は node 無しの after と同じ 124 件（`g3_compare_with_quiet_node.txt`: `G3 NEW_FAIL=0`、`PASS_TO_SKIP` 0、`FAIL_TO_SKIP` 0）。したがって製品の不具合を環境不足へ逃がしたものではない。これは「警告 1 行を除く」ラッパー越しの実測であり、警告を出さない別バージョンの node での実測ではない。 |
| `sandbox_integration` | `VERA_SANDBOX_INTEGRATION=1`、macOS の root 所有 sandbox ワーカー | 8 | before でも同じ 8 件が skip（理由は自由文）。opt-in の条件は従来どおりで、理由文字列だけ統一。この機械では実行していない |
| `eval_fixtures` | `tools/eval_dirs.txt` に列挙された評価ディレクトリのどれかが `~/Projects` 配下に存在 | 1 | 実行していない（この機械に無い） |
| `ja_sealed1_dev_fixtures` | `$VERA_JA_SEALED1_DIR` または `~/Projects/vera-ja-sealed1`（doc_* 10 件と ab_* 6 件） | 1 | 実行していない |
| `round5_dev_fixtures` | `$VERA_ROUND5_DEV_FIXTURES` または `~/Projects/vera-round5-dev/fixtures.jsonl` | 1 | 環境変数を合成した 1 行ファイルに向けると skip が消えて通る（`env_resource_override_demo.txt`。実物の fixtures ではない） |

- 実行していない資源（sandbox_integration, eval_fixtures, ja_sealed1）は「資源があれば走る」ことを、この機械では実証できていない。コード上は条件式を `_vera_env.available(...)` に置き換えただけで、期待値と assert は不変（`git diff dev -- tests`）。
- 全 skip の ID（after、node なし）:

##### `ENV_MISSING[eval_fixtures]` — 1件

- `tests.test_no_dev_literal_overlap::test_answerers_have_no_eight_character_dev_literal`

##### `ENV_MISSING[ja_sealed1_dev_fixtures]` — 1件

- `tests.test_one_trace::test_every_default_integration_part_has_a_trace`

##### `ENV_MISSING[node]` — 8件

- `tests.test_round4::test_code_is_composed_and_executed[\u6574\u6570\u30ea\u30b9\u30c8\u304b\u3089\u5076\u6570\u3092\u53d6\u308a\u51fa\u3057\u3001\u4e8c\u4e57\u3057\u3066\u5408\u8a08\u3059\u308b\u95a2\u6570\u3002\u7a7a\u306a\u30890\u3002-JavaScript]`
- `tests.test_round4::test_code_is_composed_and_executed[\u6570\u5024\u30ea\u30b9\u30c8\u306e\u5e73\u5747\u3092\u8fd4\u3059\u95a2\u6570\u3002\u7a7a\u306a\u3089None\u3002\u5143\u306e\u5165\u529b\u306f\u5909\u66f4\u3057\u306a\u3044\u3002-JavaScript]`
- `tests.test_round4::test_code_is_composed_and_executed[\u6570\u5024\u30ea\u30b9\u30c8\u3092\u964d\u9806\u3067\u30bd\u30fc\u30c8\u3059\u308b\u95a2\u6570\u3002\u5143\u306e\u5165\u529b\u306f\u5909\u66f4\u3057\u306a\u3044\u3002-JavaScript]`
- `tests.test_round4::test_code_is_composed_and_executed[\u6570\u5024\u30ea\u30b9\u30c8\u306e\u91cd\u8907\u3092\u9664\u53bb\u3057\u3001\u96a3\u63a5\u3059\u308b\u5dee\u3092\u8fd4\u3059\u95a2\u6570\u3002-JavaScript]`
- `tests.test_round4::test_code_is_composed_and_executed[\u6570\u5024\u30ea\u30b9\u30c8\u304b\u3089None\u3092\u9664\u5916\u3059\u308b\u95a2\u6570\u30020\u306f\u6b8b\u3059\u3002-JavaScript]`
- `tests.test_round4::test_code_is_composed_and_executed[\u6587\u5b57\u5217\u30ea\u30b9\u30c8\u3092\u5927\u6587\u5b57\u306b\u5909\u63db\u3059\u308b\u95a2\u6570\u3002-JavaScript]`
- `tests.test_round4::test_code_new_fields_groups_sql_and_shell`
- `tests.test_round4::test_code_binds_the_requested_key_and_record_map[JavaScript]`

##### `ENV_MISSING[node_jitless_quiet]` — 9件

- `tests.test_contract_lower.ContractLowerTests::test_all_global_aggregate_subkinds_empty_and_float_type`
- `tests.test_contract_lower.ContractLowerTests::test_group_typed_key_aggregate_and_post_filter`
- `tests.test_contract_lower.ContractLowerTests::test_join_projection_multiplicity_and_antijoin`
- `tests.test_contract_lower.ContractLowerTests::test_js_text_diff_all_ties_and_group_mean_subkinds`
- `tests.test_contract_lower.ContractLowerTests::test_ratio_float_zero_and_extrema_ties`
- `tests.test_contract_lower.ContractLowerTests::test_record_map_stable_descending_and_first_dedupe`
- `tests.test_contract_lower.ContractLowerTests::test_requested_function_names_can_shadow_builtins`
- `tests.test_contract_lower.ContractLowerTests::test_text_subkinds_ascii_space_and_literal_escaping`
- `tests.test_contract_lower.ContractLowerTests::test_three_valued_not_and_or_keep_only_true`

##### `ENV_MISSING[round5_dev_fixtures]` — 1件

- `tests.test_semantic_measure::test_no_dev_fixture_string_is_hardcoded`

##### `ENV_MISSING[sandbox_integration]` — 8件

- `tests.test_contract_batch.ActualBatchTests::test_python_global_builtin_shadow_and_inputs_reset`
- `tests.test_contract_batch.ActualBatchTests::test_sql_database_and_relation_reset`
- `tests.test_contract_sandbox.ActualSeatbeltTests::test_child_timeout_and_output_limit_are_not_success`
- `tests.test_contract_sandbox.ActualSeatbeltTests::test_node_export_undefined_and_reset`
- `tests.test_contract_sandbox.ActualSeatbeltTests::test_python_empty_boundary_keyword_only_and_reset`
- `tests.test_contract_sandbox.ActualSeatbeltTests::test_python_signature_and_type_mutation_are_not_repaired`
- `tests.test_contract_sandbox.ActualSeatbeltTests::test_shell_protocol_exact_empty_and_argv`
- `tests.test_contract_sandbox.ActualSeatbeltTests::test_sql_column_alias_order_multiplicity_and_authorizer`


- `tests/conftest.py` の `pytest_sessionstart` は fugashi が使えないとセッションを終了コード 4 で止める。fugashi 非依存のテストもこのとき走らない（既知の穴）。

## 8. 自己完結の洗い出し

出典: `dependency_scan.txt`（`tools/w0_1_scan_deps.py` の機械走査＝先頭、手書きの分類＝末尾の「classification」節）。

- G1（`g1_ticket_cmd.txt`: `[]` と `exit=0`、`g1_import.txt`: 違反 `[]`、`exit=0`）。G2（`g2_collect.txt`: collected items 3974、collection errors 0、収集後の verantyx* モジュール 125 個すべてツリー配下、`exit=0`。`g2_ticket_cmd.txt`: `3974 tests collected`、`exit=0`）。テスト実行全体を通して（収集だけでなく実行後も）外部 verantyx が混入していないことも、pytest プラグインで確認した（`after_isolation_session_check.txt`: 169 モジュール、ツリー外 0）。
- 直したもの（tests、(a)）: 絶対パス `/opt/homebrew/bin/node` → PATH 上の node（`test_contract_lower.py`）、綴りの違うユーザの絶対パス `/Users/motonishikoudai/...`（`test_semantic_measure.py`）→ 環境変数＋既定値、`~/Projects/...` 直書き（`test_one_trace.py`, `test_no_dev_literal_overlap.py`）→ `_vera_env` 経由、`import pytest` の欠落 3 ファイル（`tests/attack/test_semantic_unknown_choice_{limits,paraphrase,realtext}.py`）、Python の子プロセスの PYTHONPATH/cwd 未指定（`tests/attack/test_conduct_tree_limits.py`, `tests/attack/test_semantic_route_limits.py`。この 2 つは xfail(strict=False) で、外部 verantyx に黙って解決されても気づけなかった）。
- 分類したもの（(b)）: 7 節の ENV_MISSING。
- 問題なしと判断したもの（(c)）: git／tmp 文字列がデータや mock の引数として渡されるだけのもの（`dependency_scan.txt` の分類節に 1 行ずつ）。
- 直していないもの（tools・製品。取り込んだ unit のファイルは枝とのバイト一致を保つため、製品は挙動を変えないため）: `verantyx/contract_sandbox.py:38-39,571,574` の `/opt/homebrew/...` 固定、`verantyx/build_failure_eval.py` の `/Users/...` 直書き、`tools/{cov_*,gold_*,realize_measure,round5a_*}.py` と `experiments/{reachability_audit/audit.py,search/run_ac.py}` の既定コーパスパス（綴りの違うユーザ `/Users/motonishikoudai/...`）、多くの `tools/gold_*.py` が `VERA_LEADS` 未設定で失敗すること、`experiments/guard/run_confirm4.py:69` の PATH 文字列、製品の home 相対の既定（`doctor.py`, `cli.py` ほか）。

## 9. unit 受入デモの結果

`unit_acceptance_final.txt`（統合ツリー（w_question_forms2 を除く）の複製で、台帳 manifest と同じ環境変数で実行。各ファイルの最終行）:

- `tools/demo_case_frames.py` と `tools/gold_{quantity, double_neg, caus_pass, scramble, passive, reason, temporal, comparison, giving}.py` は `DEMO OK`（計 10 本）。
- `tools/gold_parallel.py` は `AssertionError: correct did not rise on seed 101`（2 回追加実行しても同じ）。**そのユニット自身のコミット（da21edc）を `git archive` で展開した複製でも同じ環境で同じ失敗**（`unit_acceptance_final.txt` の注記）。統合が原因ではなく、この機械の環境では台帳の受入が再現しない。直さない。
- w_question_forms2 の受入デモ（取り込まない unit）は 3 節の `qf2_demo_check.txt`。

## 10. 前任の途中出力を破棄したこと

前任の作業ツリーには `artifacts/w0-1/` 一式（before_pytest.txt、try1-3.txt、93MB のツリー複製、`.pytest_cache` 入りの複製など）があったが、実行コマンドの記録が無く、cacheprovider を切らずに走らせた跡もあったため、**証拠に使わず全部捨てて測り直した**。この文書の数値はすべて、今回の `COMMANDS.md` のコマンドで作った出力から来ている。

## 11. 既知の穴（この基線の弱点）

- 失敗 124 件のうち 94 件は原因が決まっていない（分類保留）。製品の不具合と古い期待値が混ざっている可能性があり、基線はそれを区別していない。
- `node_jitless_quiet` の 9 件は、この機械の node が警告を出すという理由で skip にした。stderr 判定は緩めていない。警告 1 行だけを除く node ラッパーでテスト無改変のまま通ることは測った（7 節、`contract_lower_round4_with_quiet_node.txt`）が、警告を出さない別バージョンの node での実測は無い。
- `sandbox_integration`・`eval_fixtures`・`ja_sealed1_dev_fixtures` は、資源があれば走ることをこの機械では実証できていない。
- w_question_forms2 を取り込んでいないため、その unit の目的（wh 疑問のルーティング）は dev のまま。34 件の新規失敗の原因（テスト側の期待が dev の semantic_wh に合っているのか、wave4 の p_* と semantic_wh が噛み合わないのか）は調べていない。
- `tools/gold_parallel.py` は台帳では merged だがこの機械では自分のコミットでも落ちる。
- wave5 の期待値変更に「弱化の疑い」が 1 件（V15）、期待の反転が数件ある（5 節）。ただし V15 は 5 節に書き写した中間職の判断（実際の呼び出し列を出力して確かめた結果、実質同等で弱化に当たらない）で決着している。11 節だけを読む場合はその判断を参照のこと。
- fugashi が無い機械では、fugashi 非依存のテストを含むセッション全体が止まる。
- 実行時間・並列時の揺れは見ていない（同一環境で 2 回ずつ走らせて同一集合だったのみ）。
