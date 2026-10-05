# W16-t2 第 2 ラウンドの追記（実装役。第 1 ラウンドの記述の訂正を含む。第 1 ラウンドの本文は消さずその下に残す）

第 2 ラウンドの内容と数は `docs/OBSERVATION.md` 末尾の「W16-t2 第 2 ラウンドの実測結果」と、上位の報告 `impl.r1.md` にある。第 1 ラウンドの本文のうち **次は第 2 ラウンドで変わった（以下が正）**:
- D6（配置が無いときの 2 本目の経路）は **消した**（裁定 5）。配置なしでも serve は ask・chat と同じ関数で答える。既知の穴 5 は成り立たない。
- D7（`_open(None)` を据え置き）は **やめた**（裁定 6）。`_open(None)` も `VERA_PLACEMENT`・互換名・`PLACEMENT_ENV_CONFLICT` を解決する。
- D1 は **適用した**（裁定 4）。`ask --document` の既定は round5。
- T2-1 の「各入口が 1 回ずつ呼んだ」は、文書なしの行（W3-c4 の AQ020・AQ030）を含むと不正確（serve は文書なしのとき関数を呼ばない）。第 2 ラウンドは「文書のある 551 行で 3 入口が 1 回ずつ」「文書なしの 2 行は serve が 0 回」に分けた。
- T2-2 は入口ごとの「自分の旧 → 新」の遷移で書く: serve の誤答は 0 → 2（O38・BQ002。旧 ask の誤答の行と同じ。どちらも読解器の既知の誤りで W16-t1b）。ask・chat の誤答は旧と同じ 2 行。「serve の誤答が増えていない」とは読めない。AQ021・AQ022 は serve の正答→棄権（裁定 2 により列挙）。
- T2-4: 総行数 152,897（+185）。

---

# W16-t2 実装報告 第 1 ラウンド（実装役）

作業ツリー: `/Users/motonisihikoudai/Projects/vera-impl/wt/W16-t2-S`（コミットしていない）。基点 `3a1677c`。成果物はすべて `artifacts/w16-t2/`（以下 `A/`）。
結論: **受入基準のうち満たせなかったものがある（T2-2 の正答→棄権 2 行、T2-4 の行数が増えた）。`done=false`。** 原因と、監査役が決められる提案を末尾に置いた。

## 何をしたか
1. 指示書どおりの順で実装した（手順 1 環境・索引 → 2 関係テストの「前」→ 3 事前登録と凍結 → 4 旧経路の測定 → 5〜9 製品 → 10 テスト → 11 測定 → 12 docs）。ツリーは最初きれい（途中の作業なし）。
2. 新しい `verantyx/doc_answer.py`（242 行）: 旧 `cli._qc_*`・`_round5_question_cross` の本体を**そのまま移した**（`QC_TRIGGER`・`QC_SPLIT`・`QC_PAIRS`・`QC_END`・`records`・`_sources`・`_quotes_open`・`predicate_form`・`_wrap`・`_info`・`_run`・`later_stage`）。足したのは `placement_scope`・`Prepared`/`prepare`/`Prepared.of`・`answer(question, documents|Prepared, *, placement, read_mode, stage)` だけ。`cli` を import しない。
3. `cli.py`: 旧関数を消し、テストが import・差し替える名前（`_QC_TRIGGER`・`_qc_records`（def）・`_qc_predicate_form`・`_round5_question_cross`（閉じた一覧の docstring つき））を薄い層で残した。`cmd_ask` と `cmd_chat` の round5 の問いは 1 つの helper `_round5_answer`（`doc_answer.answer(..., stage=_round5_question_cross)` → `apply_to_ask`）を通る（P1: cli の大域名を `stage=` で渡す）。`cmd_chat` の到達不能な round5 分岐を消した（根拠 `A/chat_dead_branch.txt`）。`serve` は `_resolve_placement_env`、`ask`・`chat` は `_placement_env_error` で `PLACEMENT_ENV_CONFLICT`（rc 2）。`cmd_read`（ledger promote）と growth の `os.environ.get("VERA_PLACEMENT")` も `placement_from_env()` にした。chat の起動表示の 1 行を `doc_answer.answer` に直した（固定するテストなし）。
4. `decode_grammar.py`: `cli` の import をやめ、`Records` は `doc_answer.prepare` を持つ。`read_turn` は `doc_answer.answer` を通し、指示書の写し方 1〜3 を実装（`_mapped_answer`: 値 1 組・`values==[value]`・出所の文が `by_text` でちょうど 1 つ・同じ文書。それ以外は `STRUCTURE_UNDETERMINED` / `ROUND5_ANSWER_NOT_MAPPED:<型つきの理由>`）。serve 側の表層の規則は元から `_qc_predicate_form` の中だけで、serve は独自の表層一致を持たない。
5. `coarse_place.py`: `PLACEMENT_ENV`・`PlacementEnvConflict`・`placement_from_env()`（D4）。`vera_server._layer_summary` は `placement_from_env()` を通す。
6. テスト 3 本（`tests/test_w16t2_{one_path,layers,placement_env}.py`、37 件）、docs（FUSION §1.2・§1.3、CHAT、OBSERVATION の事前登録＋実測）。

## 変更ファイル
`verantyx/doc_answer.py`（新規）・`cli.py`・`decode_grammar.py`・`coarse_place.py`・`vera_server.py`、`docs/{CHAT,FUSION,OBSERVATION}.md`、`tests/test_w16t2_*.py`（3 本新規）、`artifacts/w16-t2/**`。`git status --short` はこれだけ（許可パスの検査 `A/paths_check.txt` は何も出ない）。`semantic_*`・`confidence_tiers`・`placement_grow`・既存の `tests/` に差分なし（`git diff --stat 3a1677c -- <それら>` が空）。
一時物: スクラッチ `/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t2-impl/`（`__pycache__` は作っていない）。

## 受入基準ごと（自分で実行した結果）
| 基準 | 結果 | コマンド・ファイル |
|---|---|---|
| T2-1 同じ答え | **満たした**。U4 11・own60 60・W3-c4 111・b2like 47 の 229 行で、3 入口（ask・serve の `read_turn`・chat round5）の AnswerResult（verdict・values・evidence）の不一致 **0**。各入口が `doc_answer.answer` を 1 回ずつ呼んだことも検査。テスト 19 件通過（偽の配置と実配置 r9 の両方）。serve が答えを見せずに棄権した行は 4 行（W3-c4 の諾否・複数値 3、b2like の諾否 1。型 `ROUND5_ANSWER_NOT_MAPPED:semantic_document:NOT_ONE_ROLE_VALUE`） | `pytest tests/test_w16t2_one_path.py`、`A/t2_compare.txt`（"AnswerResult mismatch count: 0"）、`A/t2_1_serve_withheld.tsv` |
| T2-2 誤答 0・正答は旧の最大以上 | **満たせなかった（2 点）**。(a) 正答→棄権 **2 行**（W3-c4 の AQ021・AQ022。旧 serve だけが後段で正答。新は ask・serve・chat とも棄権）。(b) 誤答は 0 でない: 新 ask の誤答 2 行は旧 ask と同じ行（own60 O38、b2like BQ002。読解器の答え）。**新 serve もこの 2 行を ask と同じく答える（旧 serve は棄権）**。凍結データの既存テスト（`test_ask_question_cross*`・`test_w3f1_*`・`test_basis_policy_w5c*`）は「前」と同じ全通過 | `A/t2_compare.txt`（変わった行を全件）、`A/proposed_trigger_unsupported_evidence.md`、`A/exp_trigger_compare.txt` |
| T2-3 層 | **満たした**。`decode_grammar` と `doc_answer` に cli の import なし（遅延・文字列も）。grep は docstring の 1 件だけ | `pytest tests/test_w16t2_layers.py`、`A/t2_3_grep.txt` |
| T2-4 行数 | **満たせなかった**。総 152,914 行（基点 152,712）、差 **+202**（追加 174＋新規 242、削除 214）。理由は下 | `A/loc.txt` |
| T2-6 関係テスト | 関係テスト 28 件の「前」2753 passed・1 xfailed（失敗 0）、「後」2790 passed・1 xfailed（新テスト 37 件を足した。失敗 0）。`comm -13` 空 | `A/related_before.txt`・`A/related_after.txt`・`A/t2_6_check.txt` |
| 環境変数 (3) | **満たした（ただし `_open(None)` は D7 のとおり据え置き）**。`tests/test_w16t2_placement_env.py` 13 件 + `tests/coarse_place` + `test_semantic_read_w3b1` 通過 | `A/related_after.txt` |
| B2・B7（公開の写し） | 前後で時計・一時ディレクトリ名・読込モジュール数（80→83）を除いて差 0。ただし公開の写しは 前後とも correct=0（B2 over_abstain=17・B7 over_abstain=25 で、基点と同じ）で、弱い証拠 | `A/bs_B2_{before,after}.txt`・`A/bs_B7_{before,after}.txt`・`A/bs_semantic_compare.txt`（`bank_compare.py`） |
| 許可パス | 満たした | `A/paths_check.txt` |
| T2-5 | 監査役（伏せた集合）。実装役は見ていない |  |

測定の要約（`A/t2_compare.txt`。行ごとに「旧 ask・旧 serve のどちらかが正答」→ 新の正答）: U4 7→7（旧 serve だけでは 2）、own60 24→24、W3-c4 53→51、b2like 25→25。ask・serve・chat は同数。

## 判断記録
- **D1**: 適用していない。`A/proposed_default_round5.diff`・`.md`（`--mode` 既定 None、テスト 2 本に `--mode legacy` を足すだけ。chat の 3 本目は変えない）。差分を一時的に当てて 1167 件通過を確かめ、元に戻した。
- **D2**: `predicate_form` は変えていない。serve に表層の規則を足していない。
- **D3**: 同じ答えの定義は事前登録（`docs/OBSERVATION.md` 末尾）と `compare.py`／テストが同じ式（verdict・values・evidence の `json.dumps(sort_keys)`）。
- **D4**: `placement_from_env`。`--placement` があれば引数が勝つ（serve では互換名も落とす）。空は未設定。
- **D5**: `answer()` は `read_mode` を `None|strict|assume` だけ受け、答えには影響させない（`ValueError('BAD_READ_MODE')`）。
- **指示書に無い判断（以下 D6〜D9。全部の根拠を書く）**:
  - **D6（配置が無いときの serve の読み）**: 既存テスト `test_serve_fusion.py::test_strict_no_placement_is_no_record_and_no_call`（配置なし → `NO_RECORD/NO_TYPED_CANDIDATE`）と `test_thread_bound_placement_really_fails_off_the_vera_thread`（配置を引く対照）、`test_semantic_read_w3e2_serve.py` 3 件が、本読みの答えを serve が見せると落ちた（本読みは配置なしでも答えるため）。そこで `read_turn` は、本読みの ANSWER（door が question_cross でない）のとき、配置が使えなければ（`_has_placement()`: `event_cross.default_lookup()` が `StubLookup` でなく、1 回引いて開けて、`unavailable` でない）旧と同じく `doc_answer.later_stage` の言うこと（`NO_TYPED_CANDIDATE` 等）を読みにする。配置があるときだけ本読みの答えを写す。T2-1 の「配置あり」の範囲と一致。**配置なしでは ask は答え serve は答えない**（旧と同じ）。
  - **D7（`coarse_place._open(None)` を変えなかった）**: 指示書は `_open(None)` が `placement_from_env()` を使うとしたが、`tests/coarse_place` の 3 件が `VERA_PLACEMENT` の漏れ（`test_serve_fusion` が `monkeypatch.delenv` の復元でパスを残す）で落ちた。`_open(None)` は従来どおり `VERA_COARSE_PLACEMENT` だけを読む（`vera placement`・coarse query の自前の変数）。「1 つの変数」は、文書に答える 3 入口（ask・chat・serve）の入口で `placement_from_env()` により解決する形で満たす。`NO_PLACEMENT_REASONS` に `PLACEMENT_ENV_CONFLICT` は足していない。
  - **D8（`Prepared` の records は遅延）**: 文書が読めないときの例外が、旧どおり後段の外枠（`ERROR` 型）で捕まるように。
  - **D9（`_mapped_answer` に極性の条件を入れない）**: 最初は `polarity != '+'` を棄権にしたが、否定の問い（AQ006 `誰が薬を渡さなかった？`）で旧 serve の正答を失ったので外した。指示書の写し方 2 の条件だけ。
- **手順からの逸脱**: OBSERVATION.md の事前登録は末尾に追記（W3-c4 の節の直後ではない。見出しの順を変えないため）。W3-c4・b2like の検査データは `make_w3c4_sets.py` で凍結済みの元データから写した（YESNO・ILLFORMED は gold `NOT_JUDGED`＝本読みが答える行は判定に入れない。W3-c4 の採点も「後段が答えないこと」だけを見た型）。この 2 つの写しは `freeze.sha256` の後に作った（元の `tests/observe/question_ask/` は変えていない）。

## T2-4（行数）が増えた理由（数字は `A/loc.txt`）
+202 の内訳（実測）: doc_answer.py 242（移した後段 約 150 行は cli の削除と相殺で中立。足したのは scaffold: `placement_scope`・`Prepared`・`answer`・docstring 約 90 行）、cli.py 純減 109（旧関数 150＋chat の死んだ分岐を消し、薄い層・helper・conflict 処理 約 60 を足した）、decode_grammar.py 純増 43（写し方 `_mapped_answer`・`_has_placement`・`_BASE_UNKNOWN`）、coarse_place.py 純増 22（`placement_from_env`）、vera_server 純増 4。消せる大きな重複は許可パスの中に無かった（serve 側に独立した表層一致のコードは元からなく、旧 serve は `_qc_run` を呼んでいた）。減らすには、ticket の許可外の重複（`placement_grow` が `cli._qc_records` を使う、ほか）か、docstring の削減しかない。数字を作らず、増えたまま報告する。

## 既知の穴（隠さない）
1. **正答→棄権 2 行（AQ021・AQ022）**。原因は、旧 serve が後段を本読みの結果に関係なく直接呼んでいたのに対し、統合した経路が ask と同じ引き金（`UNKNOWN_UNREAD`／`UNKNOWN_NO_EVIDENCE` の閉じた 2 つ）だけで後段を走らせるため。引き金に `UNKNOWN_UNSUPPORTED_EVIDENCE` を足すと 0 になることを実測した（`A/exp_trigger_compare.txt`: 正答→棄権 0、誤答は同じ 2 行、不一致 0）が、既存テスト 5 箇所（`test_ask_question_cross.py:81,86,236`・`tests/attack/test_attack_w3c4.py:241,249-255`）が引き金の外であることを固定している。事前登録の「閉じた 2 つ」の変更なので **実装役は変えず、監査役の判断に回す**（`A/proposed_trigger_unsupported_evidence.md`）。
2. **serve が round5 の本読みの誤答を引き継ぐ**。own60 O38（`誰が小説を読んだ？` ← 文は `次郎は小説を読みたかった。`、本読みが 次郎 と答える）と b2like BQ002（`森田` と `森田課長`）。旧 ask の誤答でもあり、読解器（触れない）の問題。旧 serve は後段の `_qc_predicate_form` で棄権していた。**統合で serve の誤答が 0 → 2 になった**（チケットの T2-5「誤答 0」が隠し集合で破れる可能性）。本読みの答えに `predicate_form` をかけると「ましたか」の正答（U4 の正答）が過剰に棄権になるので、指示書の D2 に従って入れていない。
3. 「か」で終わる 何を／誰を の問いのうち `read_semantic` が読まないものは棄権のまま（例 U4 `太郎は花子に何を渡したか`: 本読みが読まず、後段は述語の形が違うので棄権。`太郎は花子に何を渡した？` は後段が答える。旧 ask と同じ）。
4. 諾否・複数値・出所が文に 1 つに当たらない本読みの答えは serve で `ROUND5_ANSWER_NOT_MAPPED`（保守側。4 行）。層 1 の文法で semantic_document 由来の役名が `cross_of` の役名と一致するかは、own60 と U4 では詰まらなかった（`test_serve_fusion` の strict 系は通過）が、広い集合では測っていない（P9）。
5. 配置が使えないとき serve は本読みの答えを見せない（D6）。ask は答える。差は「配置なし」の範囲。
6. `Prepared` を使い回す serve・chat と、毎回作る ask の答えは U4・own60 で一致（`test_a_reader_reused_over_questions_answers_as_a_fresh_one_does`）。他の文書では測っていない。
7. B2・B7 の公開の写しは前後とも correct=0 で、この変更の良し悪しを測る力が弱い。
8. `chat.py`・`one.py` は変えていない（必要がなかった）。`tools/`・`experiments/` の `cli._qc_*` の使用は見ていない（許可外）。`placement_grow.py` は `cli._qc_records`（残した薄い層）を使い続ける。
9. 実配置 r9 のテストは r9 がこのマシンにあるときだけ走る（無ければ skip。偽の配置の版は常に走る）。
