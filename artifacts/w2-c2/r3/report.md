# W2-c3（W2-c2 の第 3 ラウンド）実装報告 r1

実装役: Claude Sonnet 5.5。作業ツリー: `/Users/motonisihikoudai/Projects/vera-impl/wt/W2-c2-S`（ブランチ `ticket/W2-c2`、基点 `5cae978`、未コミット）。
指示書: `review-impl/W2-c3/plan.md`。チケット末尾の「監査役の判断（2026-10-03 14:05）」に従った。出力はすべて `artifacts/w2-c2/r3/`（この報告の写しも `artifacts/w2-c2/r3/report.md`）。
**注意**: このディレクトリにあった別チケット（W2-c の第 4 ラウンド）の `impl.r1.md` は、この報告で上書きした。指示書のとおり、事前に `review-impl/W2-c3.W2-c-r4.bak/` に全体の写しがあることを確かめた（`impl.r1〜r3.md` `review.r1〜r3.md` `plan.md` の 7 ファイル）。それらの中身は読んでいない。

## 1. 何をしたか

1. **戻した（D9）**: `NEGATED_QUESTION` `INVERTED_QUESTION` `NO_ALLOWLIST` の 3 つの罠を基点 `5cae978` の字句に戻した。否定・反転の検出器一式（`_question_form_trap` ほか）、書き込み先の検出一式（`_path_is_write_target` ほか）、`_JA_OK_TAIL` `_NEG_JA_ASKED_OK` を消し、`layer_negation` の本体・`mapping_gate` の最初の 2 つの `if`・語彙外の経路の 2 行・`_layer_permission` の並びを基点にした。`_option_spans` と `_masked_question` は BUILTIN が使うので残し、BUILTIN の節に移した。
2. **残した**: 広い語句の証拠（`wider_evidence`、`_wider_sides` ほか）、`_narrow_reading`、BUILTIN（`_BI_*`、`_builtin_protected_asked`、3 か所の呼び出し）は無変更。
3. **証拠の無い広い語句（D10、監査役の判断 B1）**: `_decide` の広い語句のブロックの「証拠が無いとき」を作り直し（狭い読みが答え、または `conduct_map.retry_allowed` の型なら内部の型 `VOCAB_UNMAPPED/TERM_IN_WIDER_PHRASE` で対応づけに回す。試してはいけない型で上げるときは回さず基点の型）、`finish` に置き換えを足した（対応づけが無効、または決めなかったとき、`exit_check` が無く reason が `FRAME_SILENT` か `MAPPING_UNSETTLED`（`LEDGER_INTEGRITY` を除く）なら基点の `FRAME_SILENT/TERM_IN_WIDER_PHRASE` に置き換える。`mapping` の記録は書き換えない）。
4. **jsonl の枠の読み（D11、監査役の判断 B1）**: `_view_from_jsonl` で、POLICY（`question_kind` が CHOICE / CONFIRM / SCOPE）の `witness.authority_record_id` で対になる DECISION を特定し、`decisions` にも `skipped_records` にも入れないようにした。語や値の一致では探さない。
5. **測定の道具**（`tests/conduct_ask/w2c2/run_w2c2.py`。既存のサブコマンドは無変更）: `sentences`、`c2r3`、`table3` を足した。
6. **試験**: `tests/test_conduct_ask_w2c2.py` を書き換え（対応表は §4）、`tests/test_conduct_ask_w2c2_view.py` を新設。データ `tests/conduct_ask/w2c2/r3_sentences.jsonl`（旧試験の表から機械的に移した 78 文）と `r3_scripts/good_d3.json`、基点の出力の記録 `artifacts/w2-c2/r3/sentences_base.jsonl` を足して凍結（`freeze_r3.txt`）。
7. **docs**: `docs/CONDUCT_ASK.md` を手順 8 のとおり直した（§3 §4 §5 の広い語句と VOCAB_UNMAPPED の行、§4 の 2・§7 の 4・§11 の 1 行・§13 の門の 1 文は基点の文言に戻し、§10 の 104〜118 は消さず状態を追記、119〜124 を追加、§11 の W2-c2 の項と §15 を書き直した）。§9 は無変更（基点とハッシュ一致を確認）。

## 2. 変更ファイル

`git -C <ツリー> status --short`（最終）:
```
 M docs/CONDUCT_ASK.md
 M verantyx/conduct_ask.py
?? artifacts/w2-c2/
?? tests/conduct_ask/w2c2/
?? tests/test_conduct_ask_w2c2.py
?? tests/test_conduct_ask_w2c2_view.py
```
- `git diff 5cae978 -- verantyx/conduct_ask.py` のハンクは指示書 §7 の塊だけ（`_view_from_jsonl` の 2 か所、`Mention.wider`、`_wider_sides` 〜、`find_mentions` の 1 行、BUILTIN の節、`_layer_permission` の 1 語、`_narrow_reading`、`_decide` の広い語句のブロック、`finish` の `wider_base`、語彙外の経路の `_builtin_protected_asked` 2 か所）。`git diff 5cae978 -- verantyx/conduct_ask.py | grep -nE '^[-+].*(_negated|_INVERT_CUE|NEGATED_QUESTION|INVERTED_QUESTION|_path_status|NO_ALLOWLIST|_PATH_RX|form_trap)'` は何も出ない。
- `conduct_map.py` `llm_choice.py` `project_frame.py` `agent_*` `conductor_run.py` `semantic_*` `coarse_*` は無変更。`git diff 5cae978 --stat -- tests` は空（コミット済みの試験は無変更）。凍結データのハッシュは `freeze.txt` `freeze_supp.txt` `freeze_r3.txt` と一致。
- `__pycache__` `.pytest_cache` は無い（`find` で確認）。`conduct_ask.py` の sha256 = `8217a4b34b45be190f086a762f901535853340b8cbdc039972d805f27900b894`。
- 第 1・2 ラウンドの保存物（`artifacts/w2-c2/after/` `c1/` `c2_report*.txt` `r2_*` など）は書き換えていない。第 3 ラウンドの出力は `artifacts/w2-c2/r3/` だけ。
- 一時物は `/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/impl-r3/`（消していない。`rm -r` は使っていない。基点の書き出しは新しいディレクトリに作った）。

## 3. 受入基準ごとの結果

読み込まれた `verantyx*` はすべてツリーの下（`[]`、手順 0）。基点の結果の取り直しは `artifacts/w2-c2/base/results.jsonl` と `cmp` で一致（`BASE_RESULTS_SAME`）。

### 速い回帰
- 試験の書き換え前、`test_conduct_ask_w2c2.py` を除く 25 ファイル: **983 passed, 1 skipped**（指示書 §1.3 と同じ）。`test_a_value_that_matches_but_whose_subject_is_not_asked_is_not_an_answer` と `test_markdown_and_jsonl_frames_give_the_same_decisions` も通る（試験は変えていない）。
- 最後（27 ファイル、w2c2 の 2 ファイルを含む）: **1475 passed, 1 skipped**（w2c2 の 2 ファイルは 492 件）。skip・xfail は足していない（`grep` の唯一の一致は文中の単語 `skip`）。

### C1（凍結 349 問 × 2 モード。コマンド: `run` → `recount` → `diff`）
- 出力: `artifacts/w2-c2/r3/after/`、`c1/c1_summary.json`、`c1/c1_diff.tsv`。`recount` は `MATCH`。
- `S_lines_hold=True`、S1=0、S2=0、S3=0。**`off` で変わった問 0**、`fakemap` で変わった問 11（指示書 §1.3 と一致）。
- 変わった 11 問（全件）: `w2c-f02-11` `w2c-f05-13` `w2c-f10-07`（fixtures）、`w2g-w01-04` `w2g-w05-02` `w2g-w05-05` `w2g-w06-02`、`w2g2-x02-04` `w2g2-x05-04`、`w2g3-y06-03` `w2g3-y06-09`。全部 `mapping_outcome` が `NOT_ASKED:RULE_ESCALATION_NOT_RETRIED` → `ESCALATED:FRAME_SILENT/MAP_NONE` に変わっただけ（decision・answer・reason・detail は基点と同じ。全部が広い語句）。
- 字義の「1 問も変わらない」は `fakemap` のこの 11 問で満たさない。これは D10（広い語句を対応づけに回す）の直接の帰結で、決定は変わらない。

### C2（D12 の読み。コマンド: `c2r3`）
- `c2r3 artifacts/w2-c2/r3/after --base artifacts/w2-c2/base` → exit 0、`C2R3_PASS`（`c2r3_report.txt`）。
  - `C2K_RAISE: 28/28`、`C2K_ROUTE: 26/26`、`ROUTE_STOPPED_BY_REVERTED_TRAP: ['w2c2-builtin-route-11']`
  - `C2R_SAME_AS_BASE: 278/278`（戻した罠の新データ・補いのデータの全行 × 両モード。違う行 0）
  - `B2_ITEMS (not judged as route)`: `w2c2-negated-route-06`、`w2c2-no_allowlist-route-01〜07, 10`（全部が戻した罠の側）
  - `TRANSFER_ROUTED: 9/30`（`WIDER` 3/6、`BUILTIN` 6/6、`NEGATED` `INVERTED` `NO_ALLOWLIST` 0/6。判定に入れない）
- 道具が判定していることの確認: `c2r3 artifacts/w2-c2/base --base artifacts/w2-c2/base` → exit 1（`C2K_ROUTE: 0/26`、`C2R_SAME_AS_BASE: 278/278`。`c2r3_on_base.txt`）。
- 旧定義 `c2`（参考）: exit 1（`c2_report_r3_olddef.txt`。戻した罠の route が基点どおり上がる）。
- 試験: `tests/test_conduct_ask_w2c2.py` `tests/test_conduct_ask_w2c2_view.py` が通る（492 件。C2-K と C2-R は試験の中で自分で判定している）。
- **D12 の字義との食い違い（監査役に申し送る）**: 監査役の「補いのデータで raise 全問・route 全問」は、補いのデータが戻した 2 つの罠（`NEGATED` 21 問・`NO_ALLOWLIST` 25 問）だけでできているので、戻した後は字義どおりには満たせない（戻せば基点どおり全部上がる）。指示書の D12 の読み（C2-K と C2-R）で判定した。

### md/jsonl（B1 の固定）
- `tests/test_conduct_ask_w2c2_view.py tests/test_conduct_ask_cli.py`: **26 passed**。
- 全データでコンパイルできる枠は 41 枠中 12 枠（29 枠は `FrameCompileError` で対象外。件数を試験で固定）。12 枠の `decisions` の (subject, value) の多重集合は一致、`TermIndex.exact` の語の group は（完了条件の id の語を除いて）一致。差は `experiment_data_pipeline.md` の `欠測の扱い` / `欠測扱い` の 1 組だけで、その差そのものを固定。
- 8 枠に属する問 118 問 × 2 モード = **236 回**の比較（decision, answer, index, reason, detail, `mapping.outcome`）で**差 0**（指示書 §1.3 と一致）。
- D11 の直しを外す（私の使い捨ての変異試験）と、view の試験 4 本が落ちる。直しを戻して 5 本とも通る（`conduct_ask.py` のハッシュも元と同じに戻したことを確認）。
- `authority_record_id` を消した写しでは、対だった DECISION 4 つが `decisions` に戻る（語の一致で消していないことの固定）。

### C3（監査役が測る。実装役は予行だけ）
- 予行（本物の codex は使っていない。`VERA_LLM_LIVE` は未設定）: `bank` → `b5_rule_probe.py`（`artifacts/w2-c2/r3/b5_probe_on_w2c2_after.txt`）。新データ（自作）の「答えるのが正解で規則層に上がる」: `NEGATED` 16、`NO_ALLOWLIST` 11、`INVERTED` 10 の計 37（`TERM_IN_WIDER_PHRASE` と `BUILTIN` は 0）。
- `probe`（`probe_base.txt` / `probe_after.txt`）: 答えるのが正解で規則層で上がる数 凍結 18 → 10、新 62 → 37、補い 25 → 25。上げるのが正解で誤って答えた数は 3 データとも 0。これは自作データの値で、隠しバンク B5 の値ではない。

### C4（既存試験の失敗集合）
- 負荷: `uptime` の 1 分平均 5.31（`c4_wait.txt`）。今回の監査役の指示（8 を超えたら待つ）に従って待たずに 1 回だけ流した（指示書は 4 としていたが、監査役の指示を優先した）。
- 結果: **116 failed, 7984 passed, 45 skipped, 75 xfailed, 75 xpassed**（`c4_after.txt`、失敗一覧 `c4_after_failures.txt`）。
- 基線（115 件）に無い失敗 = `c4_new_failures.txt` の **2 件**: `tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches` と `tests/test_p4_abilities.py::test_speech_act_drafts_fill_new_roles_and_reread`（どちらも既知の 2 件。第 2 ラウンドの `c4_before_failures.txt`、基点の書き出しでも落ちている）。
- 基線にあって今回通った失敗が 1 件: `tests/test_one_trace.py::test_every_default_integration_part_has_a_trace`（原因は調べていない。この変更との関係は未確認）。
- 全体試験は最後に 1 回だけ（その後に足したのは `test_conduct_ask_w2c2.py` の B2 の試験 1 本とドキュメントの語句のみ。速い回帰は最後にもう一度流して 1475 passed）。

### C5（docs の表が出力から再計算できる）
- `table3 artifacts/w2-c2/base artifacts/w2-c2/r3/after > artifacts/w2-c2/r3/table_15.md` が docs §15.2 にそのまま入っている → `TABLE_IN_DOCS`（`c5_check.txt`）。出力を取り直した後も表は同じ（`TABLE_SAME`）。
- `git diff 5cae978 -- docs/CONDUCT_ASK.md | grep -nE "^\+.*(_negation_evidence|_question_form_trap|_path_is_write_target)"` の行は、退役・戻したを含む行だけ（含まない行 0）。
- `grep -n "w2c2-f05-13\|経路が無い" docs/CONDUCT_ASK.md`: 2 行（§11 と §15.4）。どちらも「経路が無いとは言えない」と測定結果を書く文。`w2c2-f05-13` の誤記は直した（`w2c-f05-13`。§15.4 の旧文の書き直しで消えた）。

## 4. 試験の置き換え（D13。旧名 → 新名。同じ文・同じデータを使い、期待は弱めていない）

指示書は「11 本（154 件）が落ちた」としていたが、私の測定は **12 関数・133 件**だった（`test_form_trap_with_positive_evidence` 27、`..._without_...` 21、`test_a_path_is_a_write_target...` 23、`test_route_reaches...` 28、`test_supp_c2_route...` 25、`test_the_gate_lets...` 3、ほか各 1 件。指示書の表の関数は 12 個ある）。違いの理由は調べていない。

| 旧（落ちた 12 関数と、置き換えのために外した 1 本） | 新 |
|---|---|
| `test_form_trap_with_positive_evidence`（27）、`test_form_trap_without_positive_evidence_is_none`（21） | `test_a_negation_or_inversion_sentence_gives_the_output_the_base_code_recorded`（48 文。off・空の対応づけが `sentences_base.jsonl` と 7 欄で完全一致） |
| `test_a_path_is_a_write_target_only_right_after_or_before_a_write_verb`（23） | `test_a_path_sentence_gives_the_output_the_base_code_recorded`（23 文。同上） |
| `test_the_gate_lets_a_mapped_answer_through_when_there_is_no_positive_evidence`（3） | `test_the_gate_is_the_base_gate_again_a_negation_word_hands_a_mapped_answer_up`（同じ 3 文と `GOOD_D3`。`QUESTION_UNREADABLE/NEGATED_QUESTION` と `exit_check` と gate の trace を固定）、`test_the_gate_gives_the_output_the_base_code_recorded_with_a_correct_script`（7 文を記録と完全一致。`mapping.exit_check` まで） |
| `test_route_reaches_the_mapping_and_the_rules_never_answer_wrongly_except_the_recorded_failures`（28） | `test_c2k_route_of_a_kept_trap_reaches_the_mapping_or_is_stopped_by_a_reverted_trap`（残した罠の route 26）、`test_c2r_a_reverted_trap_gives_the_base_answer_in_both_modes`（戻した罠の新データ全行） |
| `test_recorded_c2_failures_are_exactly_the_route_sentences_that_the_definition_rejects`（1） | `test_route_stopped_by_reverted_trap_is_exactly_the_recorded_set`（生きている集合が `{w2c2-builtin-route-11}` と完全一致、`NO_ALLOWLIST` で止まる）、`test_b2_items_are_all_route_sentences_of_a_reverted_trap` |
| `test_a_recorded_c2_failure_is_never_answered_wrongly_either`（9。これは通っていたが、定数 `RECORDED_C2_FAILURES` を消したので置き換え） | `test_a_b2_item_is_never_answered_wrongly_either`（B2 の 9 問） |
| `test_c2_transfer_routing_count_is_the_measured_one`（1） | 同名（値を測定の値に: 9/30。回らない 3 問は `w2c2-wider-transfer-01〜03`、`BUILTIN` 6/6 が回る、戻した罠は 0） |
| `test_the_five_traps_still_hand_up_every_raise_sentence_and_no_route_sentence_in_the_rule_layer`（1） | `test_the_two_kept_traps_hand_up_every_raise_sentence_and_no_route_sentence_in_the_rule_layer`（残した罠の raise は全部規則層で上がり、どの罠の route も残した罠の detail で止まらない）＋ `test_c2r_…`。raise の `test_c2_raise_is_handed_up_…` は無変更で残した |
| `test_supp_c2_route_reaches_the_mapping_and_the_rules_never_answer_wrongly`（25） | `test_supp_route_rows_give_the_base_answer_in_both_modes`（25）、`test_supp_raise_rows_give_the_base_answer_in_both_modes`（21。足した） |
| `test_wider_phrase_without_evidence_is_vocab_unmapped_with_the_same_detail_and_says_what_was_not_checked`（1） | `test_a_wider_phrase_with_evidence_is_handed_up_as_frame_silent_and_says_what_was_not_checked`、`test_a_wider_route_sentence_is_off_the_base_hand_up_and_with_the_mapping_goes_to_it_and_comes_back_the_same`（15 問）、`test_vocab_unmapped_wider_phrase_is_never_the_final_output` |
| `test_a_wider_phrase_without_evidence_whose_narrow_reading_is_also_silent_stays_frame_silent`（1） | `test_a_wider_phrase_without_evidence_whose_narrow_reading_is_also_silent_goes_to_the_mapping_and_comes_back_frame_silent` |
| `test_a_wider_phrase_without_evidence_is_not_answered_from_the_narrow_reading`（1） | `test_a_wider_phrase_without_evidence_is_not_answered_from_the_narrow_reading_by_the_rules`（同じ 2 文） |

足した試験（D13 の 4〜6 と D11）: `test_a_wider_phrase_with_evidence_is_never_asked_of_the_mapping`（D10 b）、`test_a_wider_phrase_that_hands_up_a_type_the_mapping_may_not_retry_is_not_routed`（c。`NARROW_READING_HANDS_UP` の行は全部、1 件以上あることも確認）、`test_vocab_unmapped_wider_phrase_is_never_the_final_output`（d）、`test_a_wider_route_sentence_is_answered_by_the_mapping_when_the_script_names_the_right_record`（5a。値の記録を持つ 5 問が正しい答え）、`test_a_conflict_or_no_allowed_option_of_the_mapping_stays_as_its_own_type`（5b。`NO_OPTION_ALLOWED` と `FRAME_CONFLICT` が潰されない）、`test_the_gate_still_stands_after_a_wider_phrase_was_routed_and_its_exit_check_is_not_replaced`（5c の測定可能な形。下の判断 J2）、`test_the_r3_sentences_are_the_frozen_data`、view の 5 本（view・答え・対・同じ主語の通常の決定）。

## 5. 判断記録

指示書の D9〜D14 は docs §10 119〜124 に書いた。以下は、それに加えて私が決めたこと。

- **J1（番号の衝突）**: 旧版の §15.4 は第 2 ラウンドの M1〜M4 を「D9〜D12」と呼んでいた。指示書の D9〜D14 と衝突するので、§10 の 114〜118 の見出しは「M1〜M4」のまま、§15.4 の書き直しで両方を並べ、「旧版の D9〜D12 とは別物」と書いた。
- **J2（指示書 D13 の 5 (c) は書いたとおりには再現できなかった）**: 「否定語を含む広い語句の問いに台本が答えると、基点の門で `QUESTION_UNREADABLE/NEGATED_QUESTION`（exit_check あり）になり置き換えられない」は、測定では `layer_negation` が広い語句の段より前にあるため、否定語のある文は門に届かず規則層で上がる（`mapping.outcome` は `NOT_ASKED`、`exit_check` なし。基点と同じ）。門が働くのは別の形（過去形の許可 `Could we have included …?`、`Should we include …?`、別の文の否定は `CONTEXT_SENTENCE_UNREAD`）で、その `exit_check` が置き換えられないことを試験にした。前者（規則層で上がる）も別の試験で固定した。
- **J3（§10 104〜118 の「退役」の追記）**: 指示書は「各項に『第 3 ラウンドで退役』を追記」と書いていたが、104・106・107・109・111・118 は第 3 ラウンドでも有効なので、「退役」とは書かず「有効」と書いた。退役を書いたのは 108（D5）・110（D7）・114（M1）・117（M4）。105（D2）・115（M2）は「D10 に置き換え」、112 は「B2 の判断」、113 は「値が変わった」、116 は「C2 の読みが D12 に置き換わった」と書いた。退役の項の見出しにも「（第 3 ラウンドで退役）」を入れた（`grep` の確認のため。項は消していない）。
- **J4（`table` と `table3`）**: 既存の `table`（第 1・2 ラウンドの表）は変えず、第 3 ラウンド用に `table3` を足し、docs の表と C5 は `table3` を使った。
- **J5（C2-K の route の数え方）**: `ROUTE_STOPPED_BY_REVERTED_TRAP` の 1 問も `C2K_ROUTE` の合格に数えた（D12 が「どちらかで合格」としているため）。件数だけの `26/26` では 1 問の理由が隠れるので、同じ行に id を出し、docs と試験にも書いた。
- **J6（`sentences` の対応づけの台本の経路）**: 台本つきの文は、`map_helpers.py` と同じ作り（`conduct_map.RecordMapper`、`fake_pair`、固定の順序）の `mapper` を渡して流す（対応づけの順序は既定では乱数のため）。空の台本は `map_fake` のファイルで流す。基点・変更後の両方を同じ道具で流し、読み込まれたモジュールの場所は子の中で確かめる。
- **J7（負荷の閾値）**: 指示書は C4 の前に 1 分平均 4 超で待つ、監査役の今回の指示は 8 超で待つ。5.31 で、後者に従った。
- **J8（基点の書き出しに `rm -rf` を使わない）**: 手順 0 の `rm -rf $TMPD/base && mkdir` は、新しいディレクトリ（`impl-r3/base`）を作るだけにした。
- **J9（M7 の自作の文）**: `artifacts/w2-c2/r3/r3_adv_path_e2e.py`。第 2 ラウンドの 35 文を写し、新しい 16 文（英 8・日 8。広い語句を含むもの 12 文）を足した。台本は記録 `D1 D3 D4 D5` のそれぞれを選び肢 0 に「一致」を返す素朴な台本。

## 6. 測定で分かったこと（M7 を含む。数値は出典つき）

- **M7（`許可リストの無い枠には書き込みを許す答えを作る経路が無い` の書き直し）**: 自分で書いた書き込みの許可の問い 51 文（英 28・日 23、広い語句を含むもの 12 文）を、`off`・空の対応づけ・素朴な台本で流して、答えが出たのは `off` 0・空 0・素朴な台本 1 文（`docs/guide.md を修正しても大丈夫ですか？`。4 つの記録のどれでも）。**基点のコードでの同じ実行も同じ 1 文**（`r3_adv_path_e2e.txt` と `r3_adv_path_e2e_on_base.txt`）。許可の手がかり `_PERM_CUE` に無い問いで、パスの判定まで行かない基点からの穴。したがって「経路が無い」とは言えない、と docs §11・§15.4 に書いた。
- 基点のコードでの比較を最初に取ったとき、`tests/conduct_ask/ca_helpers.py` が `sys.path.insert(0, <ツリー>)` するので、`PYTHONPATH=<基点の書き出し>` だけでは基点のコードを読まず、ツリーのコードで流れた（出力の先頭の `conduct_ask loaded from:` の行で気づいた）。基点の書き出しを先に import してから実行する形に直し、スクリプトに読み込み元の出力を足した。**`run_w2c2.py` の測定の子プロセスはこの問題の影響を受けない**（子は `ca_helpers` を import せず、読み込んだモジュールの場所を assert する）。
- 対応づけに回る広い語句の問い: 554 問のうち、`off` で `MAPPING_OFF` に置き換わった問 29、`fakemap` で `MAPPING_DID_NOT_DECIDE:FRAME_SILENT/MAP_NONE` に戻った問 29、狭い読みが試してはいけない型で回さなかった問 3、状態・依頼の問い（`OUT_OF_RANGE`）の問 6（表 15-4）。最終の出力が `VOCAB_UNMAPPED/TERM_IN_WIDER_PHRASE` の行は 0（表 15-5）。

## 7. 既知の穴（隠さない）

- **D14 危険の移動**: 証拠の無い広い語句を対応づけに回すので、基点では偶然上がっていた問いが、対応づけが答えれば答えになりうる。第 2 ラウンドのレビュー §3 (c) の形（`excluded` のような活用形、`〜なしで`、`push … live`）は、戻した検出器でも門でも拾えない。語の表は足していない。新データの transfer: `WIDER` 3/6 が回る、`BUILTIN` 6/6 が回る（規則層の判定を狭めた帰結。空の台本では `MAP_NONE` で上がる。答える台本での挙動は測っていない）、戻した罠は 0。
- **戻した 3 つの罠は基点のまま**: 監査役のバンクでの誤発火は残る。基点の広い判定の穴（`drop-off`、`出せない`、`e.g.` をパスと読む）も同じ。
- `w2c2-builtin-route-11` は、戻した `NO_ALLOWLIST`（`e.g.` をパスと読む）で止まる（C2-K の route が 26/26 に数えられるのは D12 の読みのため。字義では 25/26）。
- md と jsonl の残る差: 完了条件の id（`c1` と hash id）、`experiment_data_pipeline.md` の `欠測の扱い` / `欠測扱い`。どちらも `project_frame` の側で、直していない。コンパイルできない枠 29 枠（日本語の枠など）は比較の対象外。jsonl の view の `skipped_records` には、markdown には無い種類の記録（GOAL など）が数えられる（基点から。D11 は対の DECISION を数えないだけ）。
- 証拠 (a)（主辞の型）は確かめていない（`wider_phrase_head_type = NOT_CHECKED:NO_PLACEMENT`）。`OUTSIDE_ALLOWLIST` の誤発火は未対応。E0 の `を除` が `を除外する場合` にも当たる（O1）。BUILTIN は依頼・代行の形を規則層では取りこぼす（対応づけの広い判定が出口で拾う設計だが、答える台本での確認は取っていない）。
- 指示書の「11 本（154 件）」と私の測定の「12 関数・133 件」が合わない理由は調べていない（§4）。
- 基線にあって今回通った 1 件（`test_one_trace.py::test_every_default_integration_part_has_a_trace`）の理由は調べていない。
- C3（隠しバンク B5 と本物の codex）は監査役が測る。私の予行（自作データ）の値は監査役の値の代わりにならない。
- D12 の読みが監査役の判断の字義と食い違うこと（§3 の C2）は、監査役の判断が必要。

## 8. 最後の確認

`git -C /Users/motonisihikoudai/Projects/vera-impl/wt/W2-c2-S status --short` の出力は §2 のとおり（許可パスだけ。一時ファイル・`__pycache__` なし）。
