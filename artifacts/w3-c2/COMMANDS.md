# W3-c2 コマンド記録

## 手順 0: 足場
- `mkdir -p artifacts/w3-c2 $S/base $S/q1`; `artifacts/w3-c2/py.sh` を作成（env -i、PYTHONPATH=$W）。
- `git archive 2478fc7 | tar -x -C $S/base`（基点の展開）。
- `py.sh -c "import verantyx, verantyx.semantic_read, verantyx.observe; print(...)"` → 3 つとも $W/verantyx/ 配下を確認。
- `index search "疑問文 穴 質問の十字"` → UNKNOWN_NOT_FOUND。`index search "質問に文書の証拠で答える"` → ANSWER だが hits は document 系の既存物（compile_documents・vera_ask_documents など。構造の文を証拠にする疑問文の十字ではない）。
  判断: 作り直しに当たる既存物は無い。出力は index_before.txt。

## 手順 1: 事前登録
- docs/EVENT_CROSS.md 末尾に「穴の型（W3-c2。事前登録）」、docs/OBSERVATION.md 末尾に「質問の観測（W3-c2）」の事前登録小節を追記。日時は実際の `date` の出力（初版で書き手が先に日時を書いた誤りは本文の変更記録に書いて直した）。
- prereg.txt に date・区間 sha256・`ls tests/observe/question`（そんなファイルは無い）・verantyx/ の diff が空であることを記録。

## 手順 2: 検査データ（凍結）
- `tests/observe/question/build_docs.py`・`build_questions.py`（stdlib のみ。読解器・観測器を呼ばない）で docs/QD01〜QD10.jsonl（10 本、和 7・英 3）、questions.jsonl（185 問）、placement_q.json を作成。
- 文書の読めるか確認だけ `read()` で実施 → artifacts/w3-c2/docs_readability.jsonl（各文書に読めない文が 1 文以上）。
- `FROZEN_Q.json` で sha256 凍結（freeze.txt）。凍結時点で verantyx/ の差分は空。

## 手順 3・4: semantic_read.read_question（和文・英文）
- `verantyx/semantic_read.py` に追加のみ（削除 0）: HOLE_MARK_JA/EN・WH_TABLE・QUESTION_REASONS・read_question・_question_ja・_question_en・_finish_question・_isolate_hole ほか。read()・main()・既存関数は 1 字も変えていない（tests/test_question_cross.py に基点の関数・定数の sha256 を固定）。
- `tests/test_question_cross.py`: py.sh -m pytest -q -p no:cacheprovider tests/test_question_cross.py → 通る（件数は最終の pytest_related.txt）。

## 手順 5: observe.py の質問の経路
- `verantyx/observe.py` に追加のみ（削除 0）: ANSWER_SCHEMA・ANSWER_STATUSES・QuestionObservation・_cross_matches_question・_cross_extends_question・_hole_type_check・_observe_question ほか、`observe()` の docstring の直後に 2 行、モジュール docstring に追記。
- 基線（W3-c のテスト）: `py.sh -m pytest -q -p no:cacheprovider tests/test_observe.py tests/test_observe_data.py tests/test_observe_entry.py tests/test_observe_realize.py tests/test_salience.py` → 285 passed（w3c_tests_before.txt。observe.py を変える前）。
- `tests/test_question_cross_observe.py`（34 件）: 通る。

## 手順 6: 検査データを流す（Q2）
- `py.sh tests/observe/question/run_questions.py --questions … --out artifacts/w3-c2/q2_outputs.jsonl --score q2_score.json --timing q2_timing.json`。
- 第 1 回（q2_score.r1.json）: WRONG 1（Q185。腕が多い十字が別の充填物を隠した FILLED）。検査データは直さず、規則を直した（INCOMPLETE_BY_EXTENSION。docs/OBSERVATION.md の事前登録の変更記録）。第 2 回（r2）・最終（q2_score.json）: WRONG 0。
- 凍結の確認: `shasum -a 256 docs/*.jsonl questions.jsonl placement_q.json | sort` と FROZEN_Q.json の sha を sort して diff → 一致（計画のコマンドは glob の順と鍵の順が違うので sort をかけた。内容は一致）。

## 手順 7: 測定物・文書・全体
- Q1: `py.sh tests/reading_soundness/w3b1_entry_dump.py --mode none --inputs … --out …` を基点（$BASE）で 1 回・今で 3 回（entry_inputs.txt 2,899 行と q1_doc_inputs.jsonl 86 行）→ q1_read_cmp.txt（6 行とも same）。`tests/observe/o1_bytes.py --child`（viewpoints.jsonl の凍結ケース全部。M15-question-J01 を含む）を基点 1 回・今 3 種のハッシュ種 → q1_observe_cmp.txt（3 行とも same）。
- Q4: q4_observe_grep.txt（3 行: 呼び出しの 1 行・関数の引数 neighbors の 1 行・SAL.rank([], state).trace の 1 行。前 2 行は D19 が定めた呼び出しの形で neighbors を受け取って使わない）、q4_nfkc.txt（NFKC は `_nfkc` の 1 関数だけで、一致の関数 2 つと型の判定が呼ぶ）、q4_mark.txt（置き換え先は印の定数だけ）、q4_no_data_words.txt（hits 0）、check_hardcode.txt（失敗欄は空）。
- 測定結果の区間: `py.sh tests/observe/question/recompute_q.py --write`（docs/OBSERVATION.md の 2 つの区間を artifacts から作る）。
- 関連テストは 2 つに分けて流した（pytest_related.txt）: `tests/test_observe_data.py` と `tests/test_event_cross_data.py` を同じ pytest プロセスで流すと、モジュール名 `measure` の衝突で test_observe_data の 2 件（test_o4_alternative_rule_and_the_pair_l09_l10・test_o4_the_strict_judge_flags_the_old_rule_it_replaced）が落ちる。この 2 ファイルだけで再現し（私の変更と無関係）、基線の全体テストでは落ちていない。結合の出力は pytest_related_combined.txt。
- 全体テスト: run_in_background で 1 回（負荷が 8 を超えれば待つ。pytest_full.wait.txt）。pytest_full.txt・pytest_failures.txt・pytest_new_failures.txt・pytest_fixed.txt。

## 第 2 ラウンド（review.r1.md の M1 と任意 1〜3）
- 修正: `verantyx/semantic_read.py` の `_question_en`（E2）で、取り残しの末尾 `to` の判定を「`to` で始まる」より先にした（残りが `to` 1 語なら印は `to` の後）。
- 回帰テスト: `tests/test_question_cross.py`（2 件）・`tests/test_question_cross_observe.py`（1 件）。修正前のコードに戻すと 3 件とも落ち、修正後は通ることを確認。
- 入口の確認: `py.sh -m verantyx.cli observe --anchor-text "Who did the girl write to?" --anchor-kind question --structure <E-S01..S03> --no-index`（3 問とも `QUESTION_NOT_READ`）。
- Q2 の流し直し: 第 1 ラウンドと同じコマンドで `run_questions.py` → `q2_outputs.jsonl` は修正前と byte 一致（`m1_q2_cmp.txt`）。q2_timing.json は新しい実測、前回のものは `q2_timing.round1.json`。
- Q1: 基点の展開（`git archive 2478fc7`）を scratchpad に作り、読解（entry_inputs 2,899 行・q1_doc_inputs 86 行）を基点 1 回・今 3 回、観測（`o1_bytes.py --child`、索引は scratchpad に作成）を基点 1 回・今 3 種のハッシュ種で `cmp` → `q1_read_cmp.txt`・`q1_observe_cmp.txt`（すべて same）。sha256 は `q1_read_sha.txt`・`q1_observe_sha.txt`。
- Q4: `q4_no_data_words.txt`（hits 0）・`check_hardcode.txt`（失敗欄は空）を再生成。`q4_mark.txt` は行番号がずれたので、置き換えの行（和文の `text[:a] + mark + text[end:stop]` を含む）まで拾う grep に直して再生成。
- 関連テスト: `pytest_related.txt`（2 グループ）。全体テスト: `pytest_full.txt`・`pytest_failures.txt`・`pytest_new_failures.txt`・`pytest_fixed.txt`・`pytest_two_at_base.txt`。
- 測定区間: `recompute_q.py --write` を `common_numstat.txt` と交互に 2 回、`--check` が 0 を返す（`docs/OBSERVATION.md` 377 行追加で安定）。
