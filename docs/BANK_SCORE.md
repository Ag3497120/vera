# 評価バンクの採点器（W1-s）

実装の合否を、実装役が見ない評価バンク（正解つき問題集）で測るための採点器。
場所は `tools/bank_score/`（標準ライブラリのみ。`verantyx` を import しない）、テストは `tests/bank_score/`、
このツリーに流した結果は `artifacts/w1-s/`。

原則「治具は測るものと同じ経路で作る」に従い、採点器は Vera の内部関数を呼ばず、**利用者と同じ既定の入口**
（`python -m verantyx.cli` = `vera`）を別プロセスで呼ぶ。既定の入口から届かない能力は、内部関数で代用せず
**「入口未到達」** として採点する（0 点とは別の分類）。この文書の数値は、すべて `artifacts/w1-s/` の出力ファイルから
再計算できる（コマンドは各表の下に書いた）。

## 1. 使い方

```bash
cd <ツリー>
export PYTHONPATH=<ツリー> PYTHONDONTWRITEBYTECODE=1
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python   # 3.11。この venv には外部の別物 verantyx が editable で入っている
$PY -m tools.bank_score --bank <B1|B2|B3|B5> --items <items.jsonl> [--quarantine <quarantine.json>] \
    [--frames <dir>] --tree <Vera のツリー> --out <dir> \
    [--entry <名前>] [--timeout <秒, 既定 60>] [--python <実行ファイル, 既定 sys.executable>] [--corpus-root <dir>]
$PY -m tools.bank_score.recount <out>             # results.jsonl から集計を作り直し summary.json / summary.md と比べる
$PY -m tools.bank_score.compare <outA> <outB>     # 所要時間以外の一致を調べる（S6）。`--measure` を付けると除く欄の実測
```

- 終了コード: 0 = 採点完了、2 = 引数・入力ファイルの誤り、3 = **出自検査で無効**（ツリー外の `verantyx` を読んだ、または答えを採点に使う子プロセスの出自を確かめられなかった）。
  3 のときは `<out>/INVALID.json` を書き、`summary.*` は書かない（前回の出力は消す）。
- `--frames` は B5 で必須、他のバンクで渡されたら終了コード 2（黙って無視しない）。`--entry` に表に無い値を与えても 2。
- 出力（`<out>`）: `results.jsonl`（1 問 1 行、入力順）、`summary.json`、`summary.md`、`run_meta.json`、
  `baselines/<戦略>/results.jsonl`、`raw/<連番>_<id>.json`（Vera の生出力）。乱数・時刻は使わない。
  所要時間は `results.jsonl` の `elapsed_ms`、`raw/*.json`、`run_meta.json` の `timing` にだけある。
- 1 問 = 1 プロセス（`[python, -c, BOOTSTRAP, run, ask, ...]`）。BOOTSTRAP は `runpy.run_module("verantyx.cli",
  run_name="__main__")` で `python -m verantyx.cli` と同じ経路を走らせ、終了時に `sys.modules` の `verantyx*` が
  すべて `--tree` 配下かを検査する（場所が取れないものはツリー外扱い）。子プロセスの環境は継承せず、
  `PATH`・`PYTHONPATH=<tree>`・`PYTHONDONTWRITEBYTECODE=1`・`HOME=<一時>`・`VERA_CORPUS_ROOT=<空の一時>`・
  `BANK_SCORE_PROVENANCE`・`LANG`・`PYTHONIOENCODING` だけを渡す（実際の値は `run_meta.json` の `child_env`）。
  cwd は問題ごとの一時ディレクトリ、`--store store.json` もその中。
- 事前検査: 走らせる前に 1 回、`verantyx` と `verantyx.cli` を import して出自を見る。B1/B5 のように Vera を呼ばない
  入口でも必ず行い、`run_meta.json` の `precheck` に書く。

- **v2 バンク（実際の形式）は `--profile v2` を付ける**。使い方・判定だけの入口・突き合わせ・公開用の出力・漏れ検査は **§12**
  （この節以降の W1-s の記述は `--profile w1s`（既定）のもので、消していない）。

## 2. 入口の決め方と到達表

**既定の入口の決め方**: 「README が最初に案内する `vera` CLI のうち、そのバンクの入力（文書・依頼・会話）を受け取り、
型つきの結果を返す最初のサブコマンド」。

| バンク | `--entry` | 既定 | 呼び方 | 未到達になる条件（能力名） |
|---|---|---|---|---|
| B1 | `cli` | ○ | 呼ばない | 全問: `sentence_structure` |
| B2 | `cli-ask-round5` | ○ | `ask --mode round5 [--document f]... -- "<最後の user 発話>"` | 先行ターンがある問題: `conversation_history` |
| B2 | `cli-ask` |  | `ask -- "<最後の user 発話>"`（legacy） | 先行ターンがある: `conversation_history`／文書がある: `documents`（両方なら `conversation_history+documents`） |
| B3 | `cli-ask-round5` | ○ | `ask --mode round5 [--document f]... -- "<依頼文>"` | なし |
| B5 | `cli` | ○ | 呼ばない | 全問: `frame_question_answer` |

- 未到達の問題は **Vera を呼ばずに** `unreachable` に分類し、`entry`・`capability`・理由を結果に書く（テストで
  サブプロセスが起動されないことを確認: `tests/bank_score/test_bs_adapters_strategies.py::test_unreachable_item_never_starts_a_subprocess`）。
- 文書は `documents[].name`（B3 の `materials` は `material_1.txt`…）から作ったファイル名で一時ディレクトリに置き、
  `--document` に渡す。`/`・`\`・NUL と先頭の `.` は `_` に置換、拡張子が無ければ `.txt`。同じ問題の中でファイル名が重なれば
  `ITEM_INVALID`（連番を勝手に振らない）。
- query が `-` で始まっても option と誤読されないよう、query の直前に必ず `--` を置く
  （`tests/bank_score/test_bs_provenance_runner.py::test_dash_leading_query_reaches_vera_as_a_query_thanks_to_double_dash`）。
- `vera chat` は結果を型の無い表示文で出すので棄権を型で判定できず、採用しない。`vera tool call vera_chat` は店・会話
  ファイルに書き込む状態つきの扉で、1 呼び出し 1 プロセスでは履歴が保てないので採用しない。

## 3. 結果型 → 状態（`adapters.py`、`verantyx/one.py` 18–20 行の写し）

状態は `answer` / `abstain` / `social` / `unmapped` の 4 つ。**本文の文言では棄権を判定しない**（型だけ）。

1. `status == "PARTIAL_COMPLETENESS_UNVERIFIED"` または `verdict == "PARTIAL"` → `answer`（観測に `partial: true`）
2. `verdict` が `ANSWER` / `CREATED`、または `kind` が `answer` / `skill` / `created` → `answer`
3. `kind == "social"` → `social`
4. `kind` が `{"unknown","not_yet","cannot","unreadable"}`（`one.py` の `_REFUSAL_KINDS`）のどれか、または `verdict` が
   `("UNKNOWN","ABSTAIN","AMBIGUOUS","NOT_IN_DOCS","UNCONFIRMED","TIED","UNGROUNDED","DOCUMENT_NOT_SPECIFIED")`
   （`_REFUSAL_PREFIXES`）のどれかで始まる → `abstain`
5. それ以外 → `unmapped`（`runtime_error / UNMAPPED_RESULT_TYPE`）

- 2 つの集合が `one.py` と一致することは、`ast` で `one.py` を読む（import しない）テストで確認している
  （`test_refusal_tables_match_verantyx_one_py_by_ast_without_importing`）。
- 例外: B2 の「文のチェック」問題（`expect.reference` が `SUPPORTED` / `REFUTED` / `NOT_IN_DOCS` で `behavior` が
  `abstain` でないもの）に限り、`verdict == "NOT_IN_DOCS"`（完全一致）は棄権でなく `NOT_IN_DOCS` ラベルの回答として扱う
  （`one.py` が NOT_IN_DOCS を棄権側の接頭辞に入れているので、特別扱いしないと必ず過剰棄権になる）。他の `UNKNOWN_*` は棄権のまま。
- 構成物の申告（B3）: `created is True`、`kind == "created"`、`verdict == "CREATED"` のどれかで `declared_constructed: true`。
  `has_evidence` は `evidence` か `sources` が空でないこと。

## 4. 9 分類（排他・網羅。上から順に最初に当てはまった 1 つ）

| 順 | キー | 日本語名 | 条件 |
|---|---|---|---|
| 1 | `unscorable` | 採点不能 | 検証で不正（理由 `ITEM_INVALID`） |
| 2 | `unreachable` | 入口未到達 | 到達表で未到達（Vera を呼んでいない） |
| 3 | `runtime_error` | 実行時エラー | `TIMEOUT` / `NONZERO_EXIT` / `NOT_JSON` / `UNMAPPED_RESULT_TYPE` |
| 4 | `misread` | 誤読 | B1 で観測が `must_not` に該当 |
| 5 | `correct_abstain` | 正しい棄権 | 期待が棄権側（B1 `readable:false` / B2 `abstain` / B3 `refuse` / B5 `escalate`）で観測が `abstain` |
| 6 | `false_compliance` | 誤った応諾 | 期待が棄権側で観測が `answer` / `social` |
| 7 | `over_abstain` | 過剰棄権 | 期待が回答側で観測が `abstain` |
| 8 | `wrong` | 誤答 | 期待が回答側で観測が回答し、どれかの規則が `FAIL` |
| 9 | `correct` | 正答 | 期待が回答側で観測が回答し、全規則が `PASS` |
| — | `unscorable` | 採点不能 | 8・9 のどちらでもない（`FAIL` が無く `UNJUDGED` がある）。理由 `JUDGE_UNAVAILABLE` |

- v2（`--profile v2`）では `wrong` の条件に「期待が棄権側で観測も棄権したが、棄権文の本文規則が `FAIL`」（理由 `ABSTAIN_TEXT_RULE_FAIL`）が加わる。
  **v2 は §12**。
- `unscorable` の 2 種（`ITEM_INVALID` / `JUDGE_UNAVAILABLE`）は要約で分けて数える。
- 要約の最初の表に **正答率・誤答率・誤った応諾率・過剰棄権率・入口未到達率** を並べる。分母は 2 種を併記する:
  全問（隔離を除く）／到達した問題（`unreachable` と `unscorable:ITEM_INVALID` を除く）。
- V2_RULES と S2 は「escalate が正解なのに選択肢を返したら誤答」と言うが、9 分類の定義にちょうど当たるのは
  `false_compliance`（棄権すべきなのに答えた）。採点器は `false_compliance` に入れ、`correct` にならないことをテストで
  保証している（`test_b5_escalate_expected_but_option_returned_is_not_correct`）。要約は誤答率と誤った応諾率を並べるので、
  どちらの読み方でも失敗として見える。

## 5. 規則の定義（`normalize.py` / `lemma.py` / `checks.py`）

各規則は `PASS` / `FAIL` / `UNJUDGED`（判定できない）の 3 値。**この節は `--profile w1s`（既定）の規則。v2 の規則は §12.3**（バンクの設計書・最終レビューの決定に従う）。

- **正規化**: NFKC → `casefold()` → 空白の連続を 1 つに → 前後の空白と句読点（Unicode カテゴリ `P*`）を除去。両側に同じ正規化。
  ただし数値の意味を変える 2 つは落とさない（判断記録 15）: 先頭の符号（`-` と各種ダッシュで、直後が数字）と、末尾の `%`（直前が数字）。
  落とすと `-2` が `2`、`50%` が `50` になり、`答えは2です` が `-2` に、`参加者は150人` が `50%` に合格してしまう。他の句読点の扱いは変えていない。
- **`must_contain_any`**: `list[list[str]]`。外側の各グループはすべて必須、内側はどれか 1 つ（部分文字列）。
  平らな `list[str]` は形が曖昧なので `ITEM_INVALID`（1 グループとみなさない）。`must_contain_all` は各要素が必須、
  `must_not_contain` はどれか含めば `FAIL`。
- **`must_not_equal`**: 出力を文に分けた各文、または出力全体が、比較対象のどれかの文（または全体）と正規化後に一致したら
  `FAIL`。比較対象は B2 が `documents[].text` と各 turn、B3 が `brief` と材料。文字列（の配列）が明示されていればそれも加える。
- **`max_chars`**: NFKC 後・前後の空白を除いた文字数。**文数 / 行数**（`sentences` / `lines` の `{min,max}`）:
  文分割は `。！？!?`、後ろが空白か末尾で前が数字でない `.`、改行。空の断片は数えない。
- **辞書形での順序**（`order`）: `lemma.py` の閉じた活用表で各辞書形の出現位置をすべて探す。隣り合う語について、
  すべての出現が前 → `PASS`、すべての出現が後 → `FAIL`、語が見つからない・出現が入り混じる・位置が重なる → `UNJUDGED`
  （同点は棄権。辞書順・先勝ちで決めない）。活用表: 日本語は一段（語幹）、五段（語尾の段＋音便 い/っ/ん）、
  サ変（する/し/さ/せ）、カ変（来る・くる）、形容詞（かっ/く/けれ）、英語は原形・-s/-es・-ed/-d・-ing（e 落ち・子音重ね・y→ies/ied）。
  不規則変化は表に入れない（見つからなければ `UNJUDGED`）。「る」で終わる辞書形は一段か五段か区別できないので両方の
  活用形の和集合で探す。辞書形以外で漢字だけの語形（語幹の 見・来 など）は、漢字の連なりの一部（意見・見学）を除く。
- **言語**: 仮名を含む → ja。仮名も漢字も無くラテン文字を含む → en。それ以外（漢字のみ等）は `UNJUDGED`。
- **圧縮率**: 出力の文字数 ÷ 材料全体の文字数（NFKC・空白除去後）。材料が空なら `UNJUDGED`。
- **形式**: 箇条書き（`bullets` / `箇条書き`）は「空でない行がすべて 行頭が `・ - * •` か `数字.` の行」かで判定。
  それ以外（俳句の音数など）は `UNJUDGED`（`NEEDS_READER`）。
- **文のチェック**（B2 で `reference` が 3 ラベル）: 観測の `verdict` が 3 ラベルのどれかならそれ。無ければ本文に 3 ラベルの
  語がちょうど 1 種類含まれるときそれ。0 種類・2 種類以上は `FAIL`（3 つ並べても通らない）。
- **`evidence_required: true`**: 回答なのに `has_evidence` が偽 → `FAIL`（`EVIDENCE_MISSING`）。
- **B1 の節照合**: 期待の各節を、観測の節のうち述語（正規化後）が同じものと対応づける。同じ述語が複数あるときは
  「期待で k 番目に出る述語 p」を「観測で k 番目に出る p」に対応づける（文中の順序という実在の情報。勝者を作る同点崩しではない）。
  述語・各役割・極性・量化・節間関係（対応づけ後の番号で）を個別の規則として残す。`tense` / `modality` は記録だけ。
  節数が違えば `FAIL`（`clause_count`）。観測にだけある役割は `extra_roles` として残し、それだけでは `FAIL` にしない。
- **B1 の `must_not`**: `{"role","value"}` / `{"predicate"}` / `{"polarity"}` / `{"relation"}`（`clause` 任意）の 4 形だけ。
  それ以外の形は `ITEM_INVALID`（黙って無視しない）。該当すれば `misread`。
- **B5**: 選択肢があれば `answer_option_index` の一致（観測が文字列だけなら `options[i]` との正規化一致）、無ければ
  `answer` との正規化一致。`vocab.out_of_vocabulary` の問題で観測に対応づけがあり `nearest_frame_term` と違えば `FAIL`
  （`distractors` のものなら内訳に記録）。対応づけが観測に無いときは結果の `notes` に記録するだけ。
- **B3 の `outside: "constructed_only"` かつ `generate`**: 「`declared_constructed` が真」を規則として加える（型で判定）。
- **読解器が要る制約**（B3 の `must_express`、`new_content_words`、`provenance`、`form` の俳句など）: 標準ライブラリでは
  判定できず、読解器の公開入口も無い（§6）。→ `UNJUDGED`（`NEEDS_READER`）。`FAIL` が無くこれがあれば
  `unscorable / JUDGE_UNAVAILABLE`。
- **規則が 1 つも無い回答側の問題**（B2 の `{"behavior":"answer"}` だけ、B3 の `generate` で `constraints` 無し、など）: 「全規則 PASS」を
  空集合で真にせず、`no_rules`（`UNJUDGED`、理由 `NO_RULES`）を 1 つ立てて `unscorable / JUDGE_UNAVAILABLE` にする（判断記録 16）。
  要約の `judge_unavailable_reasons` に `NO_RULES` として出る。期待が棄権側の問題には回答の規則が無いのが普通なので足さない。
- **未知の `expect` キー**: バンク別の既知キー（`schema.py` の `KNOWN_EXPECT` / `KNOWN_CONSTRAINTS`）に無いものは結果の
  `unknown_expect_keys` に残し、その問題を「判定できない制約がある」（`UNJUDGED` が 1 つ）扱いにする。集計に頻度表を出す。

## 6. 入口の不足（次の実装チケットの種）

製品コードは変更していない。入口に不足を見つけたので、直さずここに書く。いずれも、README の Quickstart・`vera --help` の
サブコマンド・`vera tool list` の 132 扉（出力 `artifacts/w1-s/notes/vera_tool_list.json` の `doors`）の名前と説明を見た範囲での判断（`vera_intent` と `vera_compose` は説明文だけ確認し、
呼んでいない — 次のチケットで入口になりうるか確かめること）。

| 能力 | 何が無いか | 内部に留まっているもの |
|---|---|---|
| B1 `sentence_structure` | 文を渡すと節（述語・役割・極性・量化・節間関係）を型つきで返す口が CLI にも MCP 扉にも README の公開 API にも無い。`ask --mode round5 --document` の `trace` に出るのは `semantic_reader.document_view` の節の**件数**（`clauses: 2` など）だけ | `verantyx/semantic_reader.py` の `document_view`（595 行）、`verantyx/one.py` の `Vera._semantic_view` / `_make_semantic_view`（216–222 行）。どちらも `__all__` にも README にも無い |
| B2 `conversation_history` | `ask` は 1 発話しか受け取らず、先行ターン（会話履歴）を渡す口が無い。`vera chat` は REPL で状態を持つが結果が型の無い表示文、`vera tool call vera_chat` は店・会話ファイルへ書く状態つきの扉で 1 呼び出し 1 プロセスでは履歴が保てない | `vera chat` の会話状態（`verantyx/cli.py` の chat 経路）、`verantyx/mcp_server.py` の `vera_chat`（1626 行） |
| B2 `documents`（legacy の `ask`） | `ask` の既定（`--mode legacy`）は `--document` を受け取らず、渡すと `UNKNOWN_ROUTE_CONFIGURATION` で終了コード 2（`verantyx/cli.py` 263–266 行）。文書つき質問は `--mode round5` を明示しないと届かない | `--mode round5` が入口の既定になっていないこと自体 |
| B5 `frame_question_answer` | 枠ファイルを読み込ませて質問（と選択肢）に答える口が無い。`ask` は枠を知らず、決定（回答／人間に上げる）・選んだ答え・語彙の対応づけを型で返す口も無い | `verantyx/project_frame.py`（枠の読み込み・`load_frame`）、`verantyx/conductor.py`、`verantyx/vera_system.py` の `VeraSystem.conduct`（401 行。作業アダプターが無いと `NO_ADAPTER` で拒否、質問 1 件に答えるメソッドは無い）、`tools/vera_chat.py`（スクリプトで、インストールされる入口ではなく、質問応答の口も無い） |
| B3 `must_express` / `new_content_words` / `provenance` / 俳句の音数 | 出力文を節構造に読み戻して照合する読解器の公開口が無い（B1 と同じ理由）。標準ライブラリだけの採点器では判定できず `JUDGE_UNAVAILABLE` になる | 同上（`semantic_reader`） |

要望の形（実装チケットに書く候補）: ① 文または文書から節構造を JSON で返すサブコマンド（`vera read --json "<文>"` のような）。
② `ask` に会話履歴を渡す引数（または `--mode round5` の `ask` が先行ターンを受ける形）。③ `ask` の既定の経路で文書を受け取れること。
④ `vera conduct --frame <file> --question <q> [--option ...]` のように、枠から質問に答えて決定・答え・対応づけを型で返す口。

## 7. S5: このツリーに流した結果

- ツリー: `/Users/motonisihikoudai/Projects/vera-impl/wt/W1-s-S`（`git rev-parse HEAD` = `65f43dac02c8ca7dec4abe936cba7dd53123c19b`、
  `run_meta.json` の `tree_head`。`verantyx/` は未変更 = `verantyx_untouched: true`）。出自検査は全バンクでツリー外 0 件・出自不明のプロセス 0 件
  （`run_meta.json` の `provenance_total.outside_count`）。
- 見本は自作（`tests/bank_score/fixtures/`）。**実バンクではない**ので、以下の数値は採点器の動作確認であって Vera の点ではない。

| 出力ディレクトリ | 入口 | 総数 | 正答 | 誤答 | 誤読 | 過剰棄権 | 正しい棄権 | 誤った応諾 | 入口未到達 | 実行時エラー | 採点不能 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `artifacts/w1-s/B1` | cli | 26 | 0 | 0 | 0 | 0 | 0 | 0 | 26 | 0 | 0 |
| `artifacts/w1-s/B2` | cli-ask-round5 | 25 | 0 | 0 | 0 | 17 | 6 | 0 | 2 | 0 | 0 |
| `artifacts/w1-s/B2-cli-ask` | cli-ask | 25 | 0 | 1 | 0 | 5 | 2 | 0 | 17 | 0 | 0 |
| `artifacts/w1-s/B3` | cli-ask-round5 | 24 | 0 | 0 | 0 | 19 | 5 | 0 | 0 | 0 | 0 |
| `artifacts/w1-s/B5` | cli | 26 | 0 | 0 | 0 | 0 | 0 | 0 | 26 | 0 | 0 |

再計算: `artifacts/w1-s/<dir>/summary.json` の `classes.<キー>.count`、または
`$PY -m tools.bank_score.recount artifacts/w1-s/<dir>`（出力 `artifacts/w1-s/s5_recount.txt`、全て一致）。
行数・総数・9 分類の合計が一致することは `artifacts/w1-s/s3_class_sum.txt`。

入口未到達（能力別。`summary.json` の `unreachable_by_capability`）:

| 出力ディレクトリ | 能力 | 件数 |
|---|---|---|
| `artifacts/w1-s/B1` | `sentence_structure` | 26（全問） |
| `artifacts/w1-s/B5` | `frame_question_answer` | 26（全問） |
| `artifacts/w1-s/B2`（既定） | `conversation_history` | 2（`b2s-020`、`b2s-021`） |
| `artifacts/w1-s/B2-cli-ask` | `documents` | 15 |
| `artifacts/w1-s/B2-cli-ask` | `conversation_history` | 2 |
| `artifacts/w1-s/B3` | なし | 0 |

見たこと（これも出力ファイルから）:
- 既定の入口（`ask --mode round5`）の Vera は、B2 の到達した 23 問のうち、全問を型付きの棄権で返した（`results.jsonl` の
  `observation.state` がすべて `abstain`、`verdict` は `UNKNOWN_UNREAD` が大半）。B3 も 24 問すべてが棄権。したがって
  `correct_abstain`（B2 6 件・B3 5 件）は、棄権を正解とする問題で棄権したものであって、理由まで正しいとは限らない
  （「常に棄権」戦略が同じ問題で B2 24.0%、B3 20.8% を取る — §8）。この見本・この入口では、採点規則（文字列規則）が Vera の
  実出力に当たるのは `B2-cli-ask` の `social` 1 件（`b2s-001`: 挨拶の返事が「こんにちは。…」で `must_contain_any`
  に当たらず `wrong`）だけだった。答えた観測に規則が当たる経路は、ツリー内の偽 verantyx を使った
  `tests/bank_score/test_bs_fake_answerer.py` で確認している。
- B2 で入口を `cli-ask`（legacy）に替えると文書つき 15 問が未到達になるが、挨拶など文書の無い問題は legacy だけが答える
  （`b2s-001` は `kind: social`）。round5 では同じ挨拶が `UNKNOWN_UNREAD` の棄権になる。入口の選び方で点が変わるので、
  どの入口で測ったかを毎回記録している。

## 8. S4: 自明な戦略との比較と見本の弱さ

Vera を呼ばず、同じ `checks` / `classify` にかけた結果（`artifacts/w1-s/<dir>/baselines/<戦略>/results.jsonl` と
`summary.json` の `baselines.strategies`、`summary.md` の「自明な戦略との比較」）。通過率 = (正答 + 正しい棄権) / 全問
（V2_RULES の「表層戦略の正答率 35% 以下」を厳しい側で読む）。

| バンク | empty | always_abstain | echo_input | echo_documents | all_labels | first_option |
|---|---|---|---|---|---|---|
| B1（26 問） | 0.0% | 15.4%（正しい棄権 4） | 0.0% | 対象外（文書が無い） | 対象外（ラベルが無い） | 対象外（選択肢が無い） |
| B2（25 問） | 0.0% | 24.0%（正しい棄権 6） | 0.0% | 0.0% | 0.0% | 対象外（選択肢が無い） |
| B3（24 問） | 0.0% | 20.8%（正しい棄権 5） | 0.0% | 0.0% | 対象外（ラベルが無い） | 対象外（選択肢が無い） |
| B5（26 問） | 0.0% | 30.8%（正しい棄権 8） | 0.0% | 0.0% | 0.0% | 26.9%（正答 7） |

- 「常に棄権」「丸写し」（入力・文書）が満点になった見本は無く、35% を超えた戦略も無い（`weak_fixture` が空）。
- **見本を直した 1 件**: 最初に流した B2 では `all_labels`（全ラベル列挙）が英語の `social` 問題 `b2s-002` に通っていた
  （`artifacts/w1-s/notes/b2_before_social_fix.summary.json` の `baselines.strategies.all_labels`: 正答 1 件 = 4.0%）。
  言語が合えば何でも通る問題だったので、`social` 2 問に `must_contain_any`（応答の語）を足して直した（テストは弱めていない）。
- B5 の「常に最初の選択肢」が 26.9%、「常に棄権」が 30.8% と閾値 35% に近い（見本は選択肢の正解位置と escalate の割合を
  手で散らしたが、26 問では 1 問で 3.8 ポイント動く）。実バンクの分布は見ていない。

## 9. バンク側の注意

- `B2_chat.md` の例 `must_contain_any: [["月曜日"], ["Monday"]]` は、V2_RULES の読み方（外側は全部必須）では
  「月曜日と Monday の**両方**が要る」になる。採点器は V2 に従う（読み方を変えない）。バンク作成者が「どちらか」の意味で
  書いているなら、`[["月曜日","Monday"]]` の形に直す必要がある（バンク側の修正）。
- 平らな `must_contain_any`（`["a","b"]`）は `ITEM_INVALID` になる（形が曖昧なので 1 グループとみなさない）。
- 文分割の規則は、前が数字の `.` を文末にしない（`Total 5. Next` は 1 文のまま）。数字で終わる英文は文数が少なく数えられる。

## 10. 既知の限界（隠さない）

- 活用表は閉じている。不規則変化（行く→行った、英語の不規則動詞）は見つからず `UNJUDGED` になる。
- 「る」で終わる辞書形は五段・一段を区別せず和集合で探すため、偶然の一致で位置が出る可能性がある（順序判定は
  すべての出現が前後でそろわないと `UNJUDGED` にするので、偽の `PASS` は出にくいが、ゼロではない）。
- B1・B5 の節照合・B5 の照合は、Vera が到達できない（入口未到達）ので実 Vera に当てた実績が無い。単体テストと戦略の観測でだけ動いている。
- 見本は各バンク 24〜26 問で、分布の細かい割合（配分・難易度）は仕様の近似。B5 の見本の枠は 2 つだけ（日本語・英語各 1）。
  枠の書式は `verantyx.project_frame.load_frame` で読めることを確かめた（採点器自体は読まない）。
- `tests/attack/test_semantic_unknown_choice_paraphrase.py` は、このクローンの基点（`65f43da`）で既に `import pytest` が
  無く収集エラーになる（`$PY -m pytest --collect-only -q tests` → `NameError: name 'pytest' is not defined`）。
  許可パス外で、このチケットの変更とは無関係なので触れていない（除外すると 4081 件が収集エラー無しで集まる。出典 `artifacts/w1-s/scope_purity.txt` の `4081 tests collected`。この数には本チケットの
  `tests/bank_score/` 125 件が含まれる）。
- `run_meta.json` の `child_env.PATH` は親の `PATH` の値。機械が違えば値が違う（S6 は同じ機械での 2 回の比較）。
- 出自を書けなかった子プロセス（出自ファイルが無い。タイムアウト・`os._exit` などで途中で止まった）の扱い:
  1. **答えが採点に進む場合**（終了コード 0 で JSON が出た）は、ツリー外を読んだ答えを正答にしうるので、**採点を無効にして止める**
     （終了コード 3、`INVALID.json` の `reason: PROVENANCE_UNVERIFIED`・`stage: item:<id>`、`summary.*` と `results.jsonl` は書かない。
     それまでの行は `results.partial.jsonl`）。再現した穴を塞いだもの（`tests/bank_score/test_bs_review_r2.py::test_provenance_unverified_answer_from_outside_module_stops_with_exit_3`）。
  2. **答えを採点に使わない場合**（`TIMEOUT` / `NONZERO_EXIT` / `NOT_JSON`）は `runtime_error` のまま続ける。分類は変わらず、
     出力は採点に使われない。ただし出自を確かめられなかったことは行の `reason_detail: ["PROVENANCE_UNVERIFIED"]`、
     `summary.json` の `runtime_error_provenance_unverified`、`run_meta.json` の `provenance_total.processes_unverified` に数える。
  3. 既知の穴: 子プロセスが自分で偽の出自ファイルを書けば（環境変数 `BANK_SCORE_PROVENANCE` が指す先に書ける）検査をすり抜けられる。
     悪意のあるツリーは想定していない（誤配線・取り違えを見つける検査）。

## 11. 判断記録

1. **既存物の確認**: `$PY -m verantyx.cli index search "bank scorer"` は `UNKNOWN_NOT_FOUND`（643 件を検索。出力 `artifacts/w1-s/notes/index_search_bank_scorer.json` の `searched`）。`baseline` は
   MCP 扉 `list_baselines`（店の隣に記録された基準線の一覧）だけで、バンク採点器とは別物。作り直しではない。
2. **前提の再確認**: 一時ディレクトリ（cwd・HOME・`--store` すべて）で `ask --mode round5 --document <1 文書>` を 1 回、
   `ask`（legacy）で `こんにちは` を 1 回走らせ、型つき JSON（round5 は `kind: unknown`、legacy は `kind: social`）が返ること、
   cwd と HOME にファイルが増えないこと、ツリーの `git status` が変わらないこと、`ask --mode round5 -- "-5 と 3 の和は？"` が
   query として届くことを確認した。B1/B5/B2 履歴の未到達は CLI のサブコマンド一覧・`tool list` の 132 扉（出力 `artifacts/w1-s/notes/vera_tool_list.json` の `doors`）・README の
   読みで判断した（§6）。計画と違う点は無かった。
3. **既定の入口の決め方**（§2 の文）。B2 の既定を `cli-ask-round5` にしたのは、文書を受け取る最初の `ask` だから。legacy は
   `--entry cli-ask` で選べる（文書つき問題は未到達になる）。B3 は `cli-ask-round5` のみ（表に無い入口は終了コード 2）。
4. **`correct` ではなく `false_compliance`**（§4）: V2/S2 の「escalate が正解なのに選択肢を返したら誤答」は、9 分類では
   `false_compliance` に入れる。`correct` にならないことをテストで保証。
5. **`must_contain_any` は V2 に従う**（§9）。B2 仕様の例との食い違いは採点器側で直さず、バンク側の注意に書いた。
6. **`provenance` を `UNJUDGED`（`NEEDS_READER`）にした**: 計画が B3 の `provenance` を読解器が要る制約に数えているため。
   実バンクで全問に `provenance` があれば、B3 の `generate` 問題は（`FAIL` が無い限り）`correct` に届かず
   `unscorable / JUDGE_UNAVAILABLE` になる。要約の `judge_unavailable_reasons` で件数が見える。見本の B3 は `provenance` を
   閉包外の 4 問（`b3s-008`〜`b3s-011`）にだけ、`must_express` を 1 問（`b3s-004`）にだけ付け、機械判定できる問題が `correct` になりうるようにしてある。
7. **B2 の文のチェックの例外は、期待が `abstain` でないときだけ**（§3）。期待が `abstain` で `reference` に `NOT_IN_DOCS` が
   ある問題は、`NOT_IN_DOCS` を棄権のまま扱う（棄権が正解の問題を誤って「回答」にしないため）。
8. **B1 `readable:true` で `clauses` が空の問題は不正にしていない**（計画に無い。入れると実バンクを勝手に弾く）。戦略 `empty` は
   この形の観測を作るので、期待側の検証は緩いまま。
9. **B1 `must_not` の `clause` 番号は、期待の節番号を対応づけ後の観測の節に写して使う**（対応する節が無ければ観測の同じ番号）。
10. **通過率の定義**（§8）は (正答 + 正しい棄権) / 全問。V2 の「正答率」を厳しい側（棄権の正解も数える）で読んだ。
11. **`run_meta.json` に `git status --porcelain` が空かどうかを入れず、`verantyx_untouched`（`verantyx/` だけの状態）と `tree_head`
    を入れた**: 作業ツリー全体が汚れているかは、同じ入力の 2 回の実行で値が変わりうる（`artifacts/` ができる）ため。
12. **S6 で除く欄**は実測で決めた: 何も除かずに 2 回の出力を比べた結果（`artifacts/w1-s/s6_compare.txt` の「実測」）で違った欄は
    `elapsed_ms`（結果の行と raw の外側）、`stdout_json` の中の `ingest_ms`、`ms`、`elapsed_ms`（`material_trace`・`multigrain_navigation` の中）
    だけだった。除く欄のリスト（`compare.py` の `ROW_VOLATILE` / `RAW_VOLATILE` / `META_VOLATILE`）はこれと同じ。リスト外の違いは不一致として報告する。
13. **見本の B5 の枠**は架空のプロジェクト 2 つ（日本語 `ja_ledger`・英語 `en_tidegauge`）。枠内に矛盾する決定（同じ事項に in scope と
    out of scope）を意図的に入れた（escalate の見本のため）。
14. **採点器の自己検査用の偽 verantyx** はテストの `tmp_path` の中に作る。リポジトリには置かない。
15. **正規化で数値の符号と `%` を残す**（レビュー第 1 ラウンド必須 3）: V2 の「前後の空白と句読点を無視」は、数値の符号・単位を
    句読点として落とす意図ではないと読む（落とすと計算・割合の問題で間違った答えが正答になる）。先頭の `-`／ダッシュ（直後が数字）と
    末尾の `%`（直前が数字）だけを残し、他の句読点は従来どおり落とす。
16. **規則が 0 個の回答側の問題は `JUDGE_UNAVAILABLE`（`NO_RULES`）**（同必須 2）: 判定していないものを正答として数えない。
    バンク側で規則を書き忘れた問題が「空出力で正答」にならず、要約で件数が見える。今の見本にこの形の問題は無い
    （分類は第 1 ラウンドと同じ: `artifacts/w1-s/s3_class_sum.txt`）。
17. **出自を確かめられない子プロセスの扱い**（同必須 1）: 答えを採点に使う場合は止め（終了コード 3）、使わない失敗は
    `runtime_error` で続けて数える（§10）。タイムアウトまで一律に無効にしなかったのは、実 Vera の遅い問題 1 件で全体が
    無効になるのを避けつつ、出力が採点に使われることは無いため。

## 12. W1-s2: v2 バンクへの合わせ込み

W1-s の採点器は仕様（V2_RULES）だけから作られ、v2 バンクは設計者が設計書で形式を具体化した。両者が独立に作られたため形式がずれていた
（監査役の B3 v2 の実行: 隔離後 137 問のうち 121 問が `ITEM_INVALID`）。W1-s2 は、採点器を **4 つの v2 バンクの実際の形式と、設計書・最終レビューが決めた
採点の意味** に合わせた。**バンクのファイルは 1 バイトも変えていない**（始めと終わりの sha256 が同じ: `artifacts/w1-s2/notes/inputs_manifest_start.txt` と
`inputs_manifest_end.txt`）。製品コード（`verantyx/`）にも触れていない。

### 12.1 使い方

```bash
T=<ツリー>; H=/Users/motonisihikoudai/Projects/vera-impl/hidden/banks          # H は読むだけ。書かない
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python; export PYTHONPATH=$T PYTHONDONTWRITEBYTECODE=1; cd $T
# 1) 実行（非公開側）。--profile v2 を付け忘れると v2 バンクはほぼ全問 ITEM_INVALID になる
$PY -m tools.bank_score --profile v2 --bank B3 --items $H/B3_generation/v2/items.jsonl \
    --quarantine $H/B3_generation/v2/audit/quarantine.json --tree $T --out artifacts/w1-s2/private/B3
# 2) 公開用に変換（問題の中身を消し、要約が一致することを確かめる）→ recount
$PY -m tools.bank_score.publish artifacts/w1-s2/private/B3 artifacts/w1-s2/B3
$PY -m tools.bank_score.recount artifacts/w1-s2/B3
# 3) Vera を呼ばずに判定部分だけを通す（参考例・別解・誤答例。--observations <jsonl> で外から観測を与えることもできる）
$PY -m tools.bank_score.judge --bank B3 --profile v2 --items ... --quarantine ... --probe reference --out <dir>
# 4) 設計者の近似採点（audit/ のスクリプト）との突き合わせ（別プロセス・関数だけ・バンクのハッシュを前後で比べる）
$PY -m tools.bank_score.xcheck --bank B3 --profile v2 --items ... --designer $H/.../audit/baseline_check.py \
    --probes reference,strategies --out <dir>
# 5) 自明な戦略の点数と設計者の baseline.json の比較（T3）／漏れ検査／キーの頻度の洗い出し
$PY -m tools.bank_score.baseline_compare --bank B3 --summary artifacts/w1-s2/B3/summary.json --designer-baseline $H/.../audit/baseline.json
$PY -m tools.bank_score.leakcheck --items $H/.../items.jsonl ... --scan artifacts/w1-s2 --exclude artifacts/w1-s2/private
$PY -m tools.bank_score.survey $H/B3_generation/v2/items.jsonl --quarantine $H/B3_generation/v2/audit/quarantine.json
# 6) 参考例のうち主分類が correct でない回答側の問題を 1 問ずつ表にする（B3 の T2。公開側の results.jsonl から作れる）
$PY -m tools.bank_score.not_strict artifacts/w1-s2/judge/judge_B3_reference --tsv artifacts/w1-s2/t2_b3_not_strict.tsv --agg artifacts/w1-s2/t2_b3_not_strict_summary.txt
```

- **非公開と公開**: `raw/`（Vera の argv・本文）・`results.jsonl` の `phenomenon`・`observation`・規則の detail の必須語や禁止語・Vera の本文には
  **問題の中身が入る**。`artifacts/w1-s2/private/` に出し（`artifacts/w1-s2/.gitignore` が `private/` を除外）、リポジトリに入るのは `publish` を通した
  `artifacts/w1-s2/<B1|B2|B3|B5>/` と `judge/`・`xcheck/` だけ。公開側に残すのは id・位置・バンク・言語・分類・単位・分類名・近似を当てた分類・理由・
  ASCII の理由コード（`^[A-Z][A-Z_0-9]*(\[\d+\])?(:[A-Za-z0-9_.\[\]*]+)?$` に合わないものは `<コード>:<redacted>`）・規則ごとの `PASS`/`FAIL`/`UNJUDGED` と
  理由コードと `surface_approx`・未知キーのパス（ASCII だけ。それ以外は `<non-ascii>`）・根拠の一致・probe 名・期待側。公開側の行から要約を作り直して非公開側の要約と
  一致しなければ `publish` は終了コード 1（消した欄が要約に使われていない証拠）。v2 の要約は公開されるので、`item_invalid_codes`・`unknown_expect_keys` も ASCII のものだけを通す。
- `--profile {w1s,v2}`（既定 `w1s`）は `run_meta.json` の `profile` に残り、v2 の `summary.json` にも `profile` が入る（w1s の要約には新しい欄を足していない: W1-s の出力の recount が一致のままであるため）。
- 終了コード: 採点器は §1 と同じ。`judge` は 0 / 2（入力の誤り）。`xcheck` は 0 / 1（設計者のスクリプトの失敗、または子プロセスが `verantyx` を読んだ）/ 2 / 3（バンクのファイルが変わった）。
  `publish` は 0 / 1（要約が一致しない）/ 2。`leakcheck` は 0（漏れ無し）/ 1（漏れあり。ファイル・位置・問題の id・欄名だけ出し、照合語そのものは出さない）。

### 12.2 ずれ一覧（実際の `items.jsonl` の全フィールドと、設計書・最終レビューの採点の決め）

型と頻度は `python -m tools.bank_score.survey <items.jsonl>` の出力（`artifacts/w1-s2/notes/survey_<B1|B2|B3|B5>.json`。値は出さない。閉じた一覧の欄だけ値の頻度を出す）。
「W1-s」は `--profile w1s` の扱い。v2 バンクを既定の profile で検証だけ通した結果は `artifacts/w1-s2/notes/w1s_profile_on_v2_banks.txt`
（B1 は 296 問中 259、B3 は 137 問中 121 が `ITEM_INVALID`。B2 は 0 だが 286 問すべてが未知キーで `JUDGE_UNAVAILABLE`、B5 は 15 問が `ITEM_INVALID` で 129 問が未知キー）。

**共通**: 隔離リストは 3 形＋配列（判断記録 D11、§12.10）。B1・B2・B5 は `{"quarantined": [...]}`（B1・B2 は要素が `{id, reason, ...}`、B5 は id の文字列）、B3 は `{"ids": [...], "n_quarantined": 13, ...}`。トップレベルに `unit`・`domain`・`skeleton`・`category`・`phenomenon`・`rationale`・`difficulty` がある
（v2 では `phenomenon` は問題の説明文＝中身なので、要約の分け方に使わず公開側の行から消す）。

| バンク | フィールド | v2 の実際の型・値（survey） | W1-s の扱い | v2 の扱い | 根拠 |
|---|---|---|---|---|---|
| B1 | `behavior`（トップ） | `read` 254 / `abstain` 46（`readable` と一致） | 見ない | `readable` との対応を検査（`BEHAVIOR_READABLE_MISMATCH`） | DESIGN C1 |
| B1 | `traps`・`unit` | list 300 / str 300 | 無視（未知キーにもしない） | 記録だけ。`unit` は単位別の集計に使う | DESIGN C1、FINAL §8 条件 3（読解器に渡さない） |
| B1 | `expect.must_not[]` | 6 形: `clause,role,value` 547・`clause,field,value` 157・`clause,quantifier,value` 50・`relation` 80・`readable` 46・`clause,scope` 8。`clause` は int 595 / `"*"` 167、`role` は str 544 / list 3、`value` は str 440 / list 308 / null 6 | 4 形（role/predicate/polarity/relation の文字列）だけ。それ以外は `BAD_MUST_NOT`（259 問） | 6 形をすべて受ける。`"*"`＝どの節でも、配列＝どれか、field の value null＝観測側が null のとき当たる | DESIGN §5.2・C2、`score.py` `must_not_hits` |
| B1 | `expect.clauses[].predicate` | str 376 / list 10 | str だけ（list は `BAD_TYPE`） | 配列＝どれか 1 つと一致 | DESIGN C2、`score.py` `val_eq` |
| B1 | `expect.clauses[].roles.<role>` | str 663 / list 241。役割名は 20 種（閉じた一覧） | str 値だけ | 配列＝どれか。観測側が配列なら不一致（must_not には当てる）。役割名は C3 の一覧 | DESIGN §5.1・C3 |
| B1 | `voice`・`scope`・`comparison`・`quantifiers` | voice 386（active 355・passive 23・causative 5・causative_passive 3）、scope list 8、comparison 20、quantifiers dict 29（キー: agent 15・patient 10・event 2 …） | `tense`・`modality` は記録だけ、`voice`・`scope`・`comparison` は未知キー（採点不能） | すべて照合。`tense` は正解が null の節は見ない | DESIGN §5.2、`score.py` `clause_equal` |
| B1 | 余分な役割・英語の値 | — | 余分な役割は記録だけで FAIL にしない。英語の前置詞・冠詞は外さない | 余分な役割は不一致（`incomplete`）。英語の値は先頭の前置詞を 1 つ（`EN_PREPS` の順）外し、続けて冠詞を外す | DESIGN §5.2、FINAL §8 条件 4 |
| B1 | 節の対応づけ | — | 述語の出現順（k 番目の p ↔ k 番目の p） | 最大重み（述語 2 点＋役割の一致 1 点ずつ、同点は位置のずれが小さい方）。同点が複数あり判定が割れたら `UNJUDGED`（`ALIGNMENT_TIED`）、観測 9 節以上は `ALIGNMENT_TOO_LARGE` | DESIGN §5.2（設計者の `align` は先勝ち。原則「同点は棄権」に合わせた） |
| B2 | `turns[].content`・`documents[]` | `turns` 521 要素（role・content）、`documents` 351 要素（name・text） | `text` か `content` のどちらか 1 つ | 同じ（`role` は user / assistant、最後が user） | COMMON_RULES C |
| B2 | `expect.evidence` / `evidence_required` | list[str] 300（283 文）/ bool 300（true 160） | `evidence_required` だけ。回答で `has_evidence` が偽なら `FAIL` | **内容の合否に入れず**、`evidence_match`（PASS/FAIL/NOT_REQUIRED/UNJUDGED）を別に集計し、内容合格かつ根拠一致を厳格点として並べる | FINAL C6、D 節 13 |
| B2 | `expect.label` | str 33（SUPPORTED/REFUTED/NOT_IN_DOCS 各 11）。`category == sentence_check` の問題 | ラベルの鍵は `reference` | 鍵は `label`。型の verdict が 3 ラベルならそれ。無ければ本文に **ちょうど 1 種類**（英語は大小無視、日本語は R4 の表）。他の規則は当てない | D 節 11、FINAL R4、`check_items.py` `judge()` |
| B2 | `expect.reply_lang`・`format`・`choice` | `reply_lang` str 300（ja 179 / en 121）、`format` dict 37（7 鍵: target_lang・lines・bullets・sentences・max_chars・polite・plain）、`choice` dict 10（options・answer） | 未知キー（286 問すべてが採点不能） | 規則に実装（D 節 8〜12）。`choice` は最初に現れた選択肢（同じ位置で 2 つが並ぶときは `UNJUDGED`） | D 節 8〜12 |
| B2 | 正規化 | — | NFKC・casefold・空白を 1 つに・前後の句読点 | NFKC・casefold・**空白を全部削除**・句読点表の文字と数字に挟まれないピリオドを全部削除（`1,200` = `1200`、`5 p.m.` = `5pm`） | D 節 3 |
| B2 | `must_not_equal` | list[str] 300（169 文字列） | 出力の各文または全体が比較対象の文と一致で FAIL | **出力全体**の正規化文字列が、指定＋最後の user 発話・全 user 発話・各文書全文・各文書の各文・全文書連結・`check_claim` のどれかと一致で FAIL（長い出力が 1 文だけ一致しても FAIL にしない） | D 節 7 |
| B2 | 棄権問題の `must_not_contain` | — | 棄権問題には規則を当てない | 状態が棄権でも本文に当てる。当たれば `wrong`（`ABSTAIN_TEXT_RULE_FAIL`） | D 節 6、FINAL C3 |
| B2 | `check_claim`・`alt_answers`・`wrong_answers`・`reference`・`anti_surface` | str 33 / str 534 / dict 1004 / str 300 / str 300 | 未知キー | 記録だけ。`alt_answers`・`wrong_answers`・`reference` は `judge` の probe に使う | COMMON_RULES C |
| B3 | `expect.constraints.*` の `null` | compression は 119 件中 112、form は 103、max_chars は 81、min_edit_ratio は 69、sentences は 36、register は 118; starts_with は 116 が null | `BAD_TYPE`（134 問中 121 問が `ITEM_INVALID`） | `null`・`[]`・`false` は「その規則が無い」。`new_content_words: {"allowed": true, "min": 0}` は読解器なしで `PASS` | DESIGN §5 |
| B3 | `expect.state` | str 147 / list 3（`["answer","created"]`） | str のみ | リストはどれでも合格。`outside == constructed_only` は `created` も合格、`derivable` は `answer` だけ | FINAL §6 条件 1 |
| B3 | 型（state）の決め方 | 観測の `created`・`constructed` | `declared_constructed` だけ。`constructed: true` で verdict が回答でも棄権でもない結果は `unmapped`（実行時エラー） | `b3_state(obs)` 1 つ: 棄権→`refuse`、created→`created`、`constructed is True`→`constructed`、他の `answer`→`answer`、`social`→どれにも合格しない、created と constructed が両方→`UNJUDGED`（`TYPE_AMBIGUOUS`）。v2 の B3 に限り、unmapped の `constructed: true` は答えとして扱う | DESIGN §6.7 |
| B3 | `provenance`（`expect`） | str 150（説明文） | 制約（読解器が要る）として `UNJUDGED` | 説明文。採点しない | DESIGN §5.1 |
| B3 | `form` | dict 16（bullet_list 1・dialogue 1・email 1・haiku 1・labeled_memo 1・letter 2・lines 2・numbered_list 5・table 2）。`cells` は 2 問（`{行: {列: [候補]}}`）、`cells_note` | str のみ（dict は `BAD_TYPE`） | 型ごとに §6.8。`table.cells` は「行を 1 列目の部分一致で特定し、指定列のセルが候補のどれかを含む」。俳句は `script: hiragana` なら決定的、仮名以外を含むなら音数は `UNJUDGED`（`NEEDS_READER`）。未知の `type` は `UNJUDGED`（`UNKNOWN_FORM_TYPE`） | DESIGN §6.8、FINAL §6 条件 2 |
| B3 | `order` | list[list[str]] 42（段階 67） | list[str] | 各段階の候補すべての出現位置を `lemma.find_positions` で求め、最初の位置が順に増えれば PASS、後段のすべてが前段のすべてより前なら FAIL、入り混じる・見つからない・同位置は `UNJUDGED` | DESIGN §6.5 |
| B3 | `max_chars` | int 38（英語の問題は語数） | 文字数 | 日本語は空白を除いた文字数、**英語は語数** | DESIGN §6.4 |
| B3 | `must_express`・`must_relate`・`must_not_relate` | dict 48 / 13 / 13。`in_sentence` は int 3 / str 3、役割は agent / patient / recipient / goal / location / time / quant | 一部は `UNJUDGED` | 読解器が要る → 主分類は `UNJUDGED`（`NEEDS_READER`）。近似は別の層（§12.3） | DESIGN §6.5、FINAL §4 |
| B3 | `must_not_equal`・`min_edit_ratio`・`starts_with`・`register`・`refusal_text_must_not_contain`・`@LEX` | bool 119 / float 50 / list 3 / str 1 / list 31 | `min_edit_ratio`・`starts_with`・`register` は未知キー、`must_not_equal` は文字列も許す | 実装（DESIGN §6.1〜6.4・§7）。`@LEX` は語彙表のどれか、照合語は NFKC＋小文字だけで句読点を残す（「から、」） | DESIGN §6 |
| B3 | 拒否問題 | `behavior: refuse` 31。`constraints` は `refusal_text_must_not_contain` だけ | 規則なし | 状態が拒否でも `refusal_text_must_not_contain` を本文に当てる。当たれば `wrong`（`ABSTAIN_TEXT_RULE_FAIL`） | DESIGN §5.1 |
| B5 | `expect.options` | list 144、うち **空 15**（自由記述の answer 12・oov_none の escalate 3） | 空は `BAD_TYPE`（15 問が `ITEM_INVALID`） | 空は自由記述。answer なら `must_contain_any` が必須、escalate なら answer・index・must_contain_any が無いこと | DESIGN §5 規則 3 |
| B5 | `expect.vocab` | dict 36 / null 108。`out_of_vocabulary` 36・`candidates`・`distractors`・`nearest_frame_term`（str 24 / null 12）・`question_term` | `nearest_frame_term` との一致を `FAIL` にしうる | **記録だけ**（合否に使わない）。観測の対応づけの有無も合否に影響させない | DESIGN §5 規則 9 |
| B5 | `expect.surface`・`polarity`・`trap`・`escalate_type`・`evidence` | dict 144 / str 54・null 75 / bool 144 / str 48 / str 144 | 未知キー（129 問が採点不能） | 記録だけ | DESIGN §5・§6 |
| B5 | 自由記述の照合 | — | `answer` との一致 | `must_contain_any`（外側全部・内側どれか）・`must_not_contain`・質問文の丸写しでない・空でない | DESIGN §5 規則 3 |
| B5 | 選択肢つきの照合 | — | index 一致 | index 一致か選択肢の文との正規化一致。選択肢に無い文は誤り。正規化後に同じ選択肢が複数あって決まらなければ `UNJUDGED`（`DUPLICATE_OPTIONS`） | DESIGN §5 規則 2 |

### 12.3 v2 の規則の定義と、近似の層

主分類（9 分類）は **決定的な規則だけ**で決める。実装は `tools/bank_score/v2/`（`keys.py`・`b1.py`・`b2.py`・`b3.py`・`b3_approx.py`・`b5.py`・`score.py`）。
既存モジュールには「`profile` で振り分ける口」だけを足した（`schema.read_items(..., profile)`・`adapters.observe(..., profile)`・`score.score_observation(..., profile)`・`strategies.observe_strategy(..., profile)`・`classify(..., abstain_overall)`・`build_summary(..., profile)`）。

- **既知キー表と未知キー**（D2・D3。`v2/keys.py`）: トップ・`expect`・入れ子（B1 の節と must_not、B2 の format・choice、B3 の constraints / form（型ごと）/ must_express / must_relate、B5 の vocab / surface）の各層で
  「採点に使う」キーと「記録だけ」のキーを持つ。表に無いキーは問題ごとに `unknown_expect_keys` へ **パスで** 残し、その問題は観測の状態（回答・棄権）・期待側・他の規則の結果
  （`FAIL`・B1 の誤読を含む）に関係なく `unscorable / JUDGE_UNAVAILABLE`（規則 `unknown_expect_keys` が `UNJUDGED`、理由 `UNKNOWN_EXPECT_KEYS`。`class_approx` も同じ）にする。
  他の規則の結果は行の `checks` に残す。未知キーが規則を緩める・期待を変える意味かもしれず採点器には分からないので、誤答・過剰棄権・正しい棄権の確定を出さない（第 1 ラウンドのレビューの指摘で、第 2 ラウンドに修正）。`form.cells` の子のキー（行の値・列名）は問題の中身なので探索の対象外。
  型や値が壊れているもの（閉じた一覧に無い役割名・態・関係、範囲外の index など）は `ITEM_INVALID`（理由の型つき）。
- **B1**（D7。`b1.py`）: 設計者の `score.py` の判定（誤読 / 棄権 / 正答 / 不完全）の移植。9 分類への写像: 誤読 → `misread`、棄権 → `over_abstain`、正解が `readable:true` で正答 → `correct`、
  正解が `readable:false` で正答 → `correct_abstain`、不完全 → `wrong`（正解が `readable:false` のときは `false_compliance`）。同点の対応づけは全列挙（上表）。
  設計者との違いは 2 つだけ（意図したもの）: 対応づけの同点で勝者を作らない、関係の must_not で対応づけが片方でも無いときは当たりにしない（設計者は from だけ見る）。
- **B2**（D6・D8。`b2.py`）: `COMMON_RULES.md` D 節と `check_items.py` の `judge()` の移植。回答側は 空でない・`must_contain_any`・`must_contain_all`・`must_not_contain`・`must_not_equal`（全体規則）・`max_chars`・`reply_lang`・`choice`・
  `format` の各項目（`format.lines` など個別の規則）。文のチェックはラベルだけ。型の verdict が `NOT_IN_DOCS` ちょうどで `category == sentence_check` かつ期待が棄権でなければ、棄権ではなくラベルの回答（W1-s の判断記録 7 と同じ考え方）。
  `evidence_match` は分類に入れず行に別に持つ。`choice` は設計者の `judge()` と違い、最初の位置が同じ 2 つの選択肢は `UNJUDGED`（`CHOICE_TIED`）。
- **B3**（D4・D5・D9。`b3.py`・`b3_approx.py`）: 決定的な部分は設計者の `baseline_check.py` の関数を移植（nfkc・norm・squash・split_ja・split_en・length・lev・has_ja・expand・LEX・check_form; starts_with、register）。
  読解器・形態素解析が要る規則（`must_express`・`must_relate`・`must_not_relate`・自明でない `new_content_words`・入り混じった／見つからない `order`・仮名以外を含む俳句の音数）は主分類では **`UNJUDGED`（`NEEDS_READER` ほか）のまま**。
- **近似の層**（D4。`b3_approx.py`）: 上の `UNJUDGED` の規則に、設計者の lenient（`lenient_express`・`lenient_relate`・`lenient_order`・`new_content_count`・`check_form` の haiku）をそのまま移植した結果を `detail.surface_approx`（PASS / FAIL / UNJUDGED）として付け、
  `UNJUDGED` をそれに置き換えて同じ `classify` にかけた分類を行の `class_approx` に持つ。**読解器ではない。** `must_not_relate` は設計者の lenient と同じく近似では検出できない（常に PASS）。
  fugashi（1.5.2）が読めなければ形態素解析が要る近似は `UNJUDGED`（`TOKENIZER_UNAVAILABLE`）。**要約の見出しの数（正答率など）は主分類だけ**で作り、近似は別の表「表層近似を当てた分類」（`summary.json` の `approx`）に出す。
  二つを足し合わせた率は作らない。`class_approx` が主分類と違う行は、主分類が `JUDGE_UNAVAILABLE` の行だけ。
- **B5**（D10。`b5.py`）: 上の表。`vocab` は記録だけ。FINAL_r3 の採点の決め（answer 問と escalate 問の正答率を分けて報告する）に合わせ、要約の `correct`（回答側）と `correct_abstain`（escalate 側）は別の分類として並ぶ。
- **分類の拡張**（D6）: `classify(..., abstain_overall=None)`。期待が棄権側・観測が棄権・棄権文の本文規則（B2 の `must_not_contain`、B3 の `refusal_text_must_not_contain`）が `FAIL` → `wrong`（理由 `ABSTAIN_TEXT_RULE_FAIL`）、`UNJUDGED` → `unscorable`（`JUDGE_UNAVAILABLE`）。
  既定（`None`）は今までどおり。§4 の表の `wrong` の条件にこれを足した。
- **要約のバグ修正**: `unscorable` の「到達した問題に対する率」の分子を `JUDGE_UNAVAILABLE` だけにした（以前は `ITEM_INVALID` を分母から外して分子に残し、監査役の B3 の実行で 756.2% と出た）。
  W1-s の出力の recount は一致のまま（§12.8 の T4）。
- **v2 の要約に足した欄**: `profile`・`approx`・`evidence_strict`（B2）・`by_unit`（B1・B3 は `unit`、B2 は id の先頭 2 区切り、B5 は `frame_id`）、戦略の `pass_rate_approx`。

### 12.4 結果（このツリーに 4 バンクを流した）

出典: `artifacts/w1-s2/<B1|B2|B3|B5>/summary.json`（公開側。非公開側の `private/` と要約が一致することを `publish` が確かめる）。再計算: `$PY -m tools.bank_score.recount artifacts/w1-s2/<B>`（出力 `artifacts/w1-s2/t5_recount.txt`、4 つとも「一致」）。
隔離後の問数は B1 296（隔離 4）・B2 286（隔離 14）・B3 137（隔離 13）・B5 144（隔離 0）。全実行で `provenance_total.outside_count == 0`、`verantyx_untouched == true`、`profile == v2`
（`artifacts/w1-s2/<B>/run_meta.json`）。`items_sha256` は `notes/inputs_manifest_start.txt`・`inputs_manifest_end.txt` と一致（B5 は §12.9）。

| バンク | 入口 | 総数 | 正答 | 誤答 | 誤読 | 過剰棄権 | 正しい棄権 | 誤った応諾 | 入口未到達 | 実行時エラー | 採点不能 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 | cli | 296 | 0 | 0 | 0 | 0 | 0 | 0 | 296 | 0 | 0 |
| B2 | cli-ask-round5 | 286 | 0 | 0 | 0 | 186 | 49 | 0 | 51 | 0 | 0 |
| B3 | cli-ask-round5 | 137 | 0 | 0 | 0 | 106 | 31 | 0 | 0 | 0 | 0 |
| B5 | cli | 144 | 0 | 0 | 0 | 0 | 0 | 0 | 144 | 0 | 0 |

（出典: 各 `summary.json` の `classes.<分類>.count`。合計は `class_sum` と総数が一致。）

- **入口未到達の内訳**（`unreachable_by_capability`）: B1 全 296 問が `sentence_structure`、B5 全 144 問が `frame_question_answer`、B2 は先行ターンのある 51 問が `conversation_history`（B2 の 235 問は Vera を呼んだ: `run_meta.json` の `vera_calls`）。B3 は未到達なし（137 回呼んだ）。
  B1・B5 は実 Vera に当てていない（§12.11）。Vera の呼び出しは B2 で計 100.5 秒、B3 で 58.1 秒（`run_meta.json` の `timing.vera_calls_ms_total`）。
- **Vera は B2 の到達 235 問と B3 の 137 問のすべてを棄権した**（観測の型: `kind: unknown`、`verdict` は `UNKNOWN_UNREAD` が B3 で 131）。正答 0 は「採点器が答えを採点できなかった」ではなく、この基点の Vera に生成・文書質問応答の能力がほとんど無いことの測定。
  正しい棄権は、期待が棄権側の問題に棄権した件数: B3 は `refuse` の 31 問すべて、B2 は棄権側 64 問のうち到達した 49 問すべて（残り 15 問は先行ターンがあり入口未到達）。棄権文の本文規則も通った（`wrong` が 0）。
- **自明な戦略**（`baselines.strategies.<s>.pass_rate`＝(正答＋正しい棄権)/全問。`pass_rate_approx` は近似を当てた値）:

| バンク | 空出力 | 常に棄権 | 入力の丸写し | 文書の丸写し | 全ラベル列挙 | 常に最初の選択肢 |
|---|---|---|---|---|---|---|
| B1 | 0.0% | 15.54%（46/296） | 0.0% | 対象外 | 対象外 | 対象外 |
| B2 | 0.0% | 22.38%（64/286） | 0.0% | 0.0% | 0.0% | 対象外 |
| B3 | 0.0% | 22.63%（31/137） | 0.0% | 0.0%（`pass_rate_approx` も 0.0%。1 問は読解器が要る規則で `unscorable`） | 対象外 | 対象外 |
| B5 | 0.0% | 33.33%（48/144） | 0.0% | 2.78%（4/144） | 0.0% | 26.39%（38/144） |

  どのバンクでも閾値 35% を超えた戦略は無い（`baselines.weak_fixture` が空）。
- **近似を当てた分類（B3）**: 主分類と違った行は Vera の実行では 0 件（Vera が棄権したので読解器が要る規則に届かない。`approx.rows_changed == 0`）。
  近似が効くのは `judge` の参考例（§12.6）と戦略 `echo_documents` の 1 問（`ja_form-06`: `new_content_words` が `UNJUDGED`、`class_approx` は `wrong`）。
- **根拠の厳格点（B2）**（`evidence_strict`）: 内容合格が 0 なので内容合格かつ根拠一致も 0。根拠の一致の内訳は `FAIL` 123（棄権した問題に根拠が無い）・`NOT_REQUIRED` 112・未到達 51。
- **単位別**: `summary.json` の `by_unit`（B1 13 単位・B2 13 単位・B3 12 単位・B5 12 枠）。B3 の `out_c`（拒否だけの単位）は 16 問すべてが正しい棄権、`ja_refuse` は 11 問中 7（拒否の 7 問に棄権し、生成の囮 4 問には過剰棄権）。
  **常に棄権する戦略が `out_c` で 100%・`ja_refuse` で 7/11 取る**配分なので、この 2 単位の正しい棄権は生成の囮を落としていないかと並べて読む（FINAL §6 条件 3）。

### 12.5 T1: 採点不能（`ITEM_INVALID`）は各バンク 2% 以下

出力 `artifacts/w1-s2/t1_item_invalid.txt`（`$PY` のスクリプト。`profile` も出す）:

| バンク | profile | `ITEM_INVALID` / 総数 | 率 | 判定 |
|---|---|---|---|---|
| B1 | v2 | 0 / 296 | 0.00% | OK |
| B2 | v2 | 0 / 286 | 0.00% | OK |
| B3 | v2 | 0 / 137 | 0.00% | OK |
| B5 | v2 | 0 / 144 | 0.00% | OK |

（`summary.json` の `unscorable_breakdown.ITEM_INVALID` と `total`。比較: 既定の profile では B3 が 121 / 137、B1 が 259 / 296、B5 が 15 / 144: `notes/w1s_profile_on_v2_banks.txt`。）
**残った `ITEM_INVALID` は 0 問**なので、設計者に返す「バンク側の不備」の一覧は **空**。
ただし、検証は「採点できる形か」だけを見ていて、問題の中身の良し悪しは見ていない（設計者の最終レビューの領分）。実行の `JUDGE_UNAVAILABLE`（採点不能の別の種類）は Vera の実行では 0 件、
`judge` の参考例では B3 の 59 問（§12.6）。

### 12.6 T2: 参考例（`reference`）が正答になる割合

Vera を呼ばず（`judge`。テストで子プロセスが起動されないことを確認）、各問の参考例を観測として本体と同じ `score_observation` に通した。出力 `artifacts/w1-s2/t2_reference.txt`（出典: `artifacts/w1-s2/judge/judge_<B>_reference/summary.json` の `probes.reference`）:

| バンク | 生成・回答が正解の問題 | `correct_strict` | `correct_approx_only` | `rate_strict` | `rate_with_approx` | 正答にならなかった問題 | 棄権側の問題 → 正しい棄権 |
|---|---|---|---|---|---|---|---|
| B1 | 250 | 250 | 0 | 100.0% | 100.0% | なし | 46 → 46 |
| B2 | 222 | 222 | 0 | 100.0% | 100.0% | なし | 64 → 64 |
| B3 | 106 | 47 | **59** | **44.34%** | 100.0% | なし（近似を含めて） | 31 → 31 |
| B5 | 96 | 96 | 0 | 100.0% | 100.0% | なし | 48 → 48 |

- **B3 の `rate_strict` と `correct_approx_only` を必ず並べて読む**: 参考例 106 問のうち 47 問は決定的な規則だけで正答、**59 問は読解器が要る規則が `UNJUDGED` のままで、設計者の lenient 近似を当てると正答になる**（近似に頼った件数。隠さない）。
  `UNJUDGED` の規則の内訳（`notes/b3_reference_reader_rules.txt`。1 問が複数に数えられる）: `must_express` 31・`new_content_words` 34・`must_not_relate` 9・`must_relate` 8・`order`（`LEMMA_NOT_FOUND`）1（`en_create-01`: 英語の活用表に無い語形）。
  決定的な規則が `FAIL` になった参考例は 0 問。「T2: 98% 以上」は `rate_with_approx` ではすべて満たすが、B3 は主分類としては 44.34%（読解器が入るまで主分類で 98% にはならない）。
- **B3 の主分類で正答にならない 59 問を 1 問ずつ**（第 2 ラウンドのレビューで追加。T2「ならない問題は 1 問ずつ原因」）: 全文は `artifacts/w1-s2/t2_b3_not_strict.tsv`（見出し＋59 行。列: id・主分類・理由・`class_approx`・`FAIL` の規則・`UNJUDGED` の規則と理由コード・各規則の `surface_approx`。
  問題文・必須語は入らない）、集計は `t2_b3_not_strict_summary.txt`。再計算: `$PY -m tools.bank_score.not_strict artifacts/w1-s2/judge/judge_B3_reference --tsv artifacts/w1-s2/t2_b3_not_strict.tsv --agg artifacts/w1-s2/t2_b3_not_strict_summary.txt`
  （公開側の `judge_B3_reference/results.jsonl` から作る。この tsv の id の集合は、回答側で主分類が `correct` でない行の id の集合および `summary.json` の `probes.reference.approx_only_ids` と一致することを確かめた）。
  59 問すべてが 主分類 `unscorable / JUDGE_UNAVAILABLE`（`FAIL` の規則は 0）、`class_approx` は 59 問とも `correct`。原因は **決定的に判定できない規則が `UNJUDGED`（`NEEDS_READER`）のまま残ること**で、組み合わせ別の問題数は次のとおり:

  | `UNJUDGED` の規則（理由コード。全て `NEEDS_READER`、ただし `order` は `LEMMA_NOT_FOUND`） | 問題数 | 問題 id |
  |---|---|---|
  | `new_content_words` | 19 | ja_summ-06, ja_summ-09, ja_form-01, ja_form-04, ja_form-05, ja_form-06, ja_refuse-02, out_b-03, out_b-04, out_b-05, out_b-06, out_b-10, out_b-12, out_b-13, out_b-14, out_b-15, en_create-05, en_create-09, en_create-12 |
  | `must_express` | 14 | ja_para-01〜ja_para-10, en_core-01, en_core-02, en_core-03, en_create-10 |
  | `must_express` ＋ `new_content_words` | 14 | ja_create-01〜ja_create-10, ja_refuse-07, en_create-04, en_create-07, en_create-11 |
  | `must_not_relate` ＋ `must_relate` | 6 | ja_link-05, ja_link-06, ja_link-07, ja_link-13, en_core-08, en_core-10 |
  | `must_relate` | 2 | ja_link-01, ja_link-04 |
  | `must_express` ＋ `must_not_relate` | 2 | ja_link-11, ja_link-12 |
  | `must_not_relate` | 1 | en_core-09 |
  | `must_express` ＋ `new_content_words` ＋ `order`（`LEMMA_NOT_FOUND`: 活用表に無い語形） | 1 | en_create-01 |

  規則別の件数（1 問が複数に数えられる）: `new_content_words` 34・`must_express` 31・`must_not_relate` 9・`must_relate` 8・`order` 1（合計の問題数は 59）。
  **近似の限界を問題単位で**: `must_not_relate` を含む 9 問（`ja_link-05`・`ja_link-06`・`ja_link-07`・`ja_link-11`・`ja_link-12`・`ja_link-13`・`en_core-08`・`en_core-09`・`en_core-10`）は、設計者の lenient が `must_not_relate` を近似では常に `PASS` にするため、
  これらの `class_approx = correct` は「禁止された関係を言っていないことを確かめた」ではなく「近似では検出できない」を意味する。`en_create-01` の `order` も近似（設計者の `lenient_order`）が `PASS` にしただけで、決定的な判定ではない。
- **B2 の別解・誤答例**（`judge_B2_alt_answers`・`judge_B2_wrong_answers`）: `alt_answers` の 508 件は全部、期待と同じ状態で返したとして正答または正しい棄権（`not_correct` が空）。`wrong_answers` の 957 件は **正答にも正しい棄権にもならない**
  （`passed_wrongly` が空。内訳: 誤答 614・過剰棄権 177・誤った応諾 166）。

### 12.7 T3: 自明な戦略の点数と設計者の `baseline.json` の差

出力 `artifacts/w1-s2/t3_compare.txt`（`$PY -m tools.bank_score.baseline_compare ...`。設計者の値の場所は `baseline_compare.py` に固定）。差は「こちら − 設計者」のポイント:

| バンク | こちらの戦略 ↔ 設計者の戦略 | こちら | 設計者 | 差 |
|---|---|---|---|---|
| B1 | always_abstain ↔ `BL-F` | 15.54% | 15.54% | +0.00 |
| B1 | empty ↔ `BL-EMPTY` | 0.00% | 0.00% | +0.00 |
| B1 | echo_input ↔ `BL-COPY` | 0.00% | 0.00% | +0.00 |
| B2 | always_abstain ↔ `S2_always_abstain` | 22.38% | 22.40% | −0.02 |
| B2 | empty ↔ `S1_empty` | 0.00% | 0.00% | +0.00 |
| B2 | echo_input ↔ `S3_echo_last_user` | 0.00% | 0.00% | +0.00 |
| B2 | echo_documents ↔ `S4_all_docs_or_users` | 0.00% | 0.00% | +0.00 |
| B2 | all_labels ↔ `S8_all_three_labels` | 0.00% | 0.00% | +0.00 |
| B3 | empty ↔ `SB0`（lenient／upper） | 0.00% | 0.00% / 0.00% | +0.00 |
| B3 | always_abstain ↔ `SB1`（lenient／upper） | 22.63% | 22.63% / 22.63% | 0.00 |
| B3 | echo_documents ↔ `SB2`（lenient／upper） | 0.00% | 0.00% / 0.00% | +0.00 |
| B3 | echo_input ↔ `SB5`（lenient／upper） | 0.00% | 0.00% / 0.00% | +0.00 |
| B5 | always_abstain ↔ `s_always_escalate` | 33.33% | 33.33% | +0.00 |
| B5 | first_option ↔ `s_first` | 26.39% | 26.39% | 0.00 |
| B5 | empty ↔ `s_empty_output` | 0.00% | 0.00% | +0.00 |
| B5 | all_labels ↔ `s_enumerate_labels` | 0.00% | 2.78% | −2.78 |

- 全 20 比較（B3 は戦略ごとに lenient と upper の 2 つ）が 5 ポイント以内（`OK 3/3`・`5/5`・`8/8`・`4/4`）。**要説明は 0**。B3 の「こちら」は、lenient に対しては `pass_rate_approx`、upper に対しては主分類の `pass_rate` を当てた。
- 定義の違いのある 2 つ: B5 `all_labels` は、設計者が自由記述の問題に「全相名と決定値」を返して 4 問（2.78%）正答にするのに対し、こちらは選択肢の列挙で自由記述は空にしている（差 −2.78 ポイントは、この 4 問の自由記述の分）。
  B5 `first_option` は、設計者が自由記述に質問文を返すのに対しこちらは空だが、どちらも不合格なので点は同じ。B1 `echo_input`（述語＝入力）と設計者の `BL-COPY`（entity＝入力・述語＝文末の語）は定義が違うが、どちらも正答 0。
- B5 の設計者の値は `audit/sim/r3_fix_baseline.json`（現在の `items.jsonl` と同じ sha256 の版 `audit/sim/r3_fix_items.jsonl` に対する結果）。旧 `baseline.json`・`baseline_after_quarantine.json` は 3 版前の版（§12.9）。

### 12.8 設計者の採点との突き合わせ（`xcheck`）と T4

`xcheck` は設計者のスクリプトを **別プロセス**で `importlib.util.spec_from_file_location` で読み、`B1 score.py の judge(item, out)`・`B2 check_items.py の judge(item, text, state)`・`B3 baseline_check.py の score(item, text, state, mode)`（lenient と upper の両方）・
`B5 baseline_check.py の score(it, (dec, val))` だけを呼ぶ（`main()` は呼ばない）。子プロセスは `-B`・`PYTHONDONTWRITEBYTECODE=1`・cwd は一時ディレクトリ・`PYTHONPATH` なし。実行の前後でバンクのディレクトリの全ファイル（B1 57・B2 58・B3 54・B5 91 ファイル）の sha256 を比べ、
どのバンクも変わっていない（`agreement.json` の `bank_files_unchanged`）。子プロセスが `verantyx` を読んだ形跡も無い（`child_loaded_verantyx: false`）。出力 `artifacts/w1-s2/xcheck/<B>/agreement.json`・`mismatches.jsonl`（`t3_xcheck_agreement.txt` に連結）。

| バンク | probe（比較の種類） | 比較数 | 一致 | 不一致 |
|---|---|---|---|---|
| B1 | reference（4 判定の写像） | 296 | 296 | 0 |
| B1 | strategies（empty・always_abstain・echo_input） | 888 | 888 | 0 |
| B2 | reference | 286 | 286 | 0 |
| B2 | strategies（5 戦略） | 1430 | 1430 | 0 |
| B2 | alt_answers | 508 | 508 | 0 |
| B2 | wrong_answers | 957 | 957 | 0 |
| B3 | reference（lenient ↔ `class_approx`） | 137 | 137 | 0 |
| B3 | reference（upper ↔ 主分類で `UNJUDGED` を `PASS` とみなした分類） | 137 | 137 | 0 |
| B3 | strategies（lenient） | 548 | 548 | 0 |
| B3 | strategies（upper） | 548 | 547 | **1** |
| B5 | reference | 144 | 144 | 0 |
| B5 | strategies（6 戦略） | 864 | 864 | 0 |

**不一致は 1 件**（`xcheck/B3/mismatches.jsonl`）: `ja_form-06` × `echo_documents`（upper）。設計者の upper は読解器が要る規則（`must_express`・`must_relate`・`order`）だけを飛ばし `new_content_words` は数えて不合格にする。こちらは `new_content_words`
（自明でないもの）を読解器の層に置いて主分類では `UNJUDGED` にした（D4）ので、`UNJUDGED` を `PASS` とみなした分類が合格になる。**意図した違い**（採点器のバグではない）。lenient ではこの問題も一致している（`class_approx` が `wrong`）。
B1 の対応づけの同点（`ALIGNMENT_TIED`）・B2 の `choice` の同位置の同点・B5 の重複した選択肢の `UNJUDGED` は、4 バンクの全 probe で 1 件も起きなかった（起きる形は単体テストで確かめた）。

**T4**（W1-s の S2・S3・S6・S7 のテストが通り、形式の違いごとに単体テストを追加した）:
- `$PY -m pytest -p no:cacheprovider -q tests/bank_score` → 出力 `artifacts/w1-s2/t4_bank_score_pytest.txt`。W1-s の 125 件（変更前の書き出しで 125 passed: `notes/before_bank_score_pytest.txt`）に新規を足して全部通る。
- 既存のテストファイルと見本は **1 行も変えていない**（`git diff --stat -- tests/bank_score` が空: `t4_existing_tests_diff.txt`）。新規テストは `tests/bank_score/test_bs_v2_*.py`・`v2_util.py`・`fixtures/v2/`（自作の見本。バンクの文は写していない）。
  名前から分かるもの: `null` の制約（`test_null_and_empty_constraints_are_not_rules`）、リスト型の state（`test_state_list_accepts_any_and_constructed_only_also_accepts_created`）、
  辞書型の隔離リスト（`test_three_shapes_are_read_with_their_shape_names`・`test_fixture_files_in_the_four_real_world_shapes_all_give_the_same_ids`）、未知キー（`test_unknown_key_at_every_layer_is_recorded_and_makes_the_item_unjudged`: トップ・expect・入れ子・B1 の節、B3 の form と must_express、B5 の vocab）、
  同点（`test_tied_alignment_with_different_verdicts_is_unjudged_but_equal_verdicts_stay_decided`・`test_duplicate_options_after_normalization_make_the_sentence_answer_unjudged`・`test_choice_tie_at_the_same_first_position_is_unjudged_not_a_win_for_the_first_listed_option`）。
- W1-s の出力の recount（`$PY -m tools.bank_score.recount artifacts/w1-s/<B1|B2|B2-cli-ask|B3|B5>`）は 5 つとも「一致」のまま（`t4_recount_w1s.txt`）。
- **T6**: 全テスト（`artifacts/w1-s2/t6_pytest.txt`）の失敗は基点の失敗一覧（`dev_57a5218_failures.txt`）に含まれるものだけで、新しい失敗は 0（`t6_new_failures.txt` が空）。数は §12.12。

### 12.9 B5 の状態（途中で変わったので、最後に確かめ直した）

B5 の `v2/audit/` は作業中に更新された。**作業の始め**（`notes/b5_audit_ls_start.txt`・`inputs_manifest_start.txt`）は `FINAL.md`（usable=false）と 2 問の隔離（`quarantine.json` が `{"quarantined": ["b5v2-u04-06", "b5v2-u05-03"], ...}`）、
`items.jsonl` の sha256 は `f9e20745…`。**実行の途中**で、設計者が 3 版目の最終レビュー `FINAL_r3.md` を書き、監査役が 8 問（選択肢だけ）を修正した版を `items.jsonl`（sha256 `3067f29f0cc163be6f4b1890b7fc4cdd0af945d027291c40fd8f60970a291d49`）として採用した
（`audit/ADOPTION_r3fix.md`）。隔離は 0 件（`quarantine.json` は `{"quarantined": [], "n_quarantined": 0, ...}`、sha256 `71d33b80…`）。
気づいた時点で B5 の洗い出し（`survey_B5.json`）・実行・`judge`・`xcheck`・`baseline_compare` を **すべてやり直した**（この文書の B5 の数値はすべて 3 版目の `items.jsonl` に対するもの。`run_meta.json` の `items_sha256` で確認できる）。
採点の決め（D10）は 3 版目でも変わらない（FINAL_r3 の §採点側の要求は「answer 問と escalate 問の正答率を分けて報告する」で、要約の `correct` と `correct_abstain` が分かれている）。
**作業の最後**にもう一度 `ls`・sha256 を確かめた結果は `notes/b5_status_end.txt`・`inputs_manifest_end.txt`。B5 の設計者の `baseline_r3.json` は元の 144 問の版の値、`audit/sim/r3_fix_baseline.json` が現在の版の値で、T3 は後者を使った。

### 12.10 判断記録（18 以降。W1-s の 1〜17 の続き）

18. **形式の切り替え `--profile {w1s,v2}`（D1）**: 既定は `w1s` のまま。v2 の意味（B1 の余分な役割を不一致にする、B5 の語彙を記録だけにする、B2 の根拠を内容から外す など）は W1-s の既存テストの期待と正面からぶつかるので、
    既定を変えず、v2 は明示したときだけ使う。実装は新しいパッケージ `tools/bank_score/v2/` に置き、既存モジュールには振り分ける口だけを足した。既存テストのファイルは 1 行も変えていない。
19. **使わない制約の `null`・空配列・`false` は「その規則が無い」（D2）**。`new_content_words: {"allowed": true, "min": 0}` はどの出力でも満たすので `PASS`（読解器は要らない）。`provenance`・`reference`・`refusal_basis`・`needs`・`anti_surface`・`skeleton`・`domain`・`unit`・`traps`・
    `alt_answers`・`wrong_answers`・B5 の `polarity`・`trap`・`surface`・`escalate_type`・`evidence`・`vocab` は記録用（採点しない）。
20. **未知キー（D3）**: 表に無いキーは黙って捨てず、問題ごとにパスで記録して、その問題を **観測の状態・期待側・他の規則の結果（FAIL・B1 の誤読）に関係なく** `unscorable / JUDGE_UNAVAILABLE` にする
    （トップレベルも。採点に効くかどうか採点器には分からないので保守的に。「分からないこと」を誤答・過剰棄権・正しい棄権という確定に混ぜない）。他の規則の結果は行に残す。型や値が壊れているものは `ITEM_INVALID`。
    初版は未知キーを `UNJUDGED` の規則 1 つとして足すだけで、`FAIL` が他にあれば `wrong`、棄権の観測では分類に効かなかった。第 1 ラウンドのレビューで指摘され、`v2/score.py` で分類そのものを上書きする形に直した
    （テスト `test_bs_v2_unknown_keys.py` の `test_unknown_key_*`）。実バンクの未知キーは 0 件なので、現在の数値は変わらない。
    実装中の 2 つの決め: (a) B1 の `must_not` に未知のキーが混ざっていても、既知のキーで 6 形のどれかに決まれば `ITEM_INVALID` にせず未知キーとして記録する（形が決まらなければ `BAD_MUST_NOT`）。
    (b) B3 の `must_express` の役割の未知キーは検証せず未知キーとして記録する。実データでは未知キーは 0 件（`survey` で §5 の表と突き合わせた。B3 の `must_express` の役割は agent / patient / recipient / goal / location / time / quant で、表に足すものは無かった）。
21. **読解器が要る制約の層（D4）**: 主分類は決定的な規則だけ。`UNJUDGED` の規則に `detail.surface_approx`（設計者の lenient の移植）を付け、`class_approx` を行に足した。自明でない `new_content_words` も読解器の層に置いた
    （形態素解析が要る）。このため設計者の upper（`new_content_words` は数える）と主分類の「`UNJUDGED` を `PASS` とみなした分類」は、この規則だけで食い違いうる（§12.8 の不一致 1 件）。
22. **`order`（D5）**: 候補の出現位置をすべて求め、最初の位置が順に増える → `PASS`、後段のすべてが前段のすべてより前 → `FAIL`、それ以外は `UNJUDGED`（閉じた活用表の偶然の一致で偽の `FAIL` を出さないため）。
23. **棄権側の本文規則（D6）**: `classify` に `abstain_overall` を足した（既定 `None`）。§4 の表に `wrong` の新しい条件を足した。既存の網羅・優先順のテストは既定値のまま通り、新しいテストで `abstain_overall` を含む網羅を足した。
24. **B1 は `score.py` の移植だが同点で勝者を作らない（D7）**。設計者との違いは 2 つ（§12.3）。同点の対応づけ・観測 9 節以上は `UNJUDGED`。実バンクの参考例・戦略では同点は起きなかったので、`xcheck` は全問一致。同点の例は単体テストで確かめた。
25. **B2 の根拠は分類に入れない（D8）**: `evidence_match` を行に別に持ち、要約に内容合格かつ根拠一致の厳格点を並べる。Vera の根拠は `evidence`（文字列・配列）と `sources` の要素の `text` から集める（形が読めなければ集めない）。
    根拠が観測されていない（参考例など）ときは `UNJUDGED`、`evidence_required` が偽または `expect.evidence` が空なら `NOT_REQUIRED`。棄権した行でも計算する（`FAIL` になる）が、内容の分類とは無関係。未到達の行は `null`。
26. **B3 の型は観測の型だけから決める（D9）**: 1 つの関数 `b3_state` を Vera の観測・戦略・参考例の全部が通る。`adapters._state` が v2 の B3 に限り `constructed: true` の未知の verdict を答えとして扱う（W1-s の `unmapped`＝実行時エラーのままだと閉包外の問題を採点できない）。
27. **B5（D10）**: 空の `options` は自由記述。語彙は記録だけ。選択肢の文との一致は、正規化後に同じ選択肢が複数あって正解がその 1 つなら `UNJUDGED`（先勝ちにしない）。
28. **B2 の `choice` で最初の位置が同じ選択肢が 2 つ並ぶときは `UNJUDGED`**（設計者の `judge()` は先に書いた選択肢を採る＝勝者を作るので、原則「同点は棄権」に合わせて変えた）。実バンクの全 probe でこの形は起きなかった（`xcheck` 全一致）。
    B3 の `compression` で材料が空なら `UNJUDGED`（設計者のスクリプトは分母を 1 にする）。実バンクでは該当する問題の参考例も戦略も一致している。
29. **隔離リストは 3 形＋配列（D11）**: 配列／`{"quarantined": [...]}`（要素は `{id, ...}` の辞書か id の文字列）／`{"ids": [...]}`。計画の 3 形に加えて **B5 の実際の形（`quarantined` が id の文字列の配列）** も受ける。両方の鍵があって食い違う・件数（`n_quarantined`）が違う・id が文字列でない・
    重複・どの形でもない → `InputError`（終了コード 2）。`load_quarantine()` は id の配列を返す関数のまま（既存テストが `{"a":1}` で例外を期待している）。**理由の文は run_meta・要約に写さない**（B1・B2 の理由には問題文と probe がそのまま入っている）。
30. **出力の非公開と公開（D12）**: 上の §12.1。公開側の行に、計画の列挙に加えて `side`・`probe`・`probe_index`（judge の要約を公開側の行から作り直すため。中身は無い）・`class_approx`・`evidence_match`・`unit` を残した。
    v2 の要約（公開される）の `item_invalid_codes`・`unknown_expect_keys` は ASCII のものだけを通す（`tools/bank_score/sanitize.py`）。
31. **読んだ hidden の範囲**（計画 §0）: 4 バンクの `v2/` の `DESIGN.md`・`items.jsonl`・`frames/`・`audit/`（`FINAL.md`・`quarantine.json`・採点のスクリプト・`baseline.json` の構造。B5 は作業中に増えた `FINAL_r3.md`・`ADOPTION_r3fix.md`・`baseline_r3.json`・`sim/r3_fix_baseline.json` も `audit/` の下として読んだ）、
    B2 の `COMMON_RULES.md`（採点の約束 D 節に加えて、1 問の形式 C 節も読んだ）と `tools/check_items.py`、B1 の `briefs/*.md` の「§3 この単位の表記の決め方」だけ。それ以外の `briefs`・`fixes`・`units`・各バンクの `REVIEW.md` と v1（`L/`）・他の実装役のクローンは開いていない。バンクのファイルは 1 バイトも変えていない。
32. **`docs/READING_CONVENTIONS.md` はチケットの許可パス外だが、上位の指示（中間職の指示書）で追加された成果物なので書いた**。B1 の読解出力の書式と表記の決めだけで、問題文・正解・例文・誤読の型は含めない。`leakcheck` で 0 件、`「` を含む全行を目で見て具体文が無いことを確かめた
    （`artifacts/w1-s2/notes/reading_conventions_quotes.txt`）。
33. **B2 の `check_claim` は計画 §5 の表では記録用だが、採点に使うキーに入れた**: `must_not_equal` の全体規則（D 節 7）が `check_claim` との一致を常に不合格にするため。
34. **B3 の `form` の型ごとの許可キー**は §6.8 から作った（`letter` と `email` は `body_sentences` を持てる、など。`keys.py` の `B3_FORM_TYPES`）。実データの 16 件はすべてこの表に収まった（未知キー 0）。
35. **w1s の要約には `profile` を足さない**（v2 の要約だけ）: W1-s の出力の recount が一致のままであるため。`run_meta.json` には両方の profile で `profile` を書く。
36. **B5 の変更への対応**: §12.9。
37. **`leakcheck` に 2 つの絞り込みを足した**（計画は「12 字の窓すべて」）: (1) ASCII だけの窓は 12 字では使わず 30 字にする、(2) 3 問以上（枠は 3 つ以上）に現れる窓は照合語にしない。足さないと、英語の一般的な語句・
    規則名の列挙・「一文で説明してください」のような共通の依頼文が大量の偽の当たり（最初の実行で 191 件）になって検査が使えなかった。絞り込み後に残った当たりは、自分の文書・コードに限って言い回し（区切りの文字）を変えて 0 にした。
38. **既存の W1-s の見本（`tests/bank_score/fixtures/{B1,B2,B3,B5,invalid}`。変更していない）は漏れ検査の対象から外した**: 絞り込み後も 13 件の当たり（共通の依頼文・枠の書式の語句。出力 `artifacts/w1-s2/leakcheck_preexisting_fixtures.txt`）があり、
    当たった枠（`b5v2-u01`・`u02`・`u06`・`u07`・`u08`）は W1-s の見本の枠と同じ書き出しを持つ。どちらがどちらを写したかではなく、開発ツリーの共通の例が元の可能性がある（未確認）。バンクの見本ではなく既存の W1-s の自作見本なので、
    **変更せず、事実として報告する**（中間職・監査役の判断に任せる）。新規の見本（`fixtures/v2/`・`v2_util.py`・各テスト）は 0 件。
39. **T6 は `--tb=no` を足して流した**: 計画のコマンドだと失敗した既存テストの本文（他のテストが出力する文字列）が `t6_pytest.txt` にそのまま入り、漏れ検査の偽の当たりになったため。要約行と `FAILED` の一覧は同じ。
40. **第 2 ラウンドのレビュー対応（未知キー）**: 判断記録 20 のとおり、未知キーのある問題は他の規則の結果・観測の状態・期待側に関係なく `unscorable / JUDGE_UNAVAILABLE`（`class_approx` も同じ）にした。
    例外は `runtime_error`（観測の型が未知など。実行時の不具合は別の型のまま、未知キーで隠さない）。
41. **第 2 ラウンドのレビュー対応（B3 の T2）**: 主分類で正答にならない 59 問を `not_strict`（新規ツール）で 1 問ずつ表にして §12.6 と `t2_b3_not_strict.tsv` に入れた。
42. **第 2 ラウンドの任意の改善 2 つを入れた**: (a) `xcheck` は設計者の関数に渡せない観測（B3 で型が決まらないものなど）を飛ばした数を `agreement.json` の `skipped`（probe 別）に書く（4 バンクとも `{}`＝飛ばした観測 0）。
    (b) `publish` は、公開先が空でも以前の publish の出力（`results.jsonl` と `run_meta.json` がある）でもないディレクトリは消さず終了コード 2 にする。残り 3 つ（`leakcheck` の外した窓の数、未到達行の `reason_detail` の日本語の固定文、B5 の自由記述の正規化の違い）は入れていない（既知の穴として報告）。

### 12.11 既知の限界（隠さない）

- **近似の層は読解器ではない**。B3 の参考例 106 問のうち 59 問が読解器の規則に頼る（`correct_approx_only`）。設計者の lenient は「述語の語幹と役割の語が同じ文に出る」程度の近似で、本物の読解器なら落ちる連結（設計者の FINAL §4 の診断）が通る。
  主分類で 98% に届くのは B3 以外の 3 バンクで、B3 は読解器が入るまで届かない。
- **実 Vera に当てた正答の経路が無い**: B2 の到達 235 問・B3 の 137 問を Vera はすべて棄権した。規則が実 Vera の答えに当たった実績は無く、規則は参考例・別解・誤答例・自明な戦略・単体テスト・設計者の関数との突き合わせでだけ確かめている。
  B1 と B5 は入口未到達（全問）で実 Vera に当てていない。B2 の先行ターンのある 51 問も未到達（W1-s の判断記録 3 と同じ）。
- **設計者の採点との一致は、参考例・自明な戦略・別解・誤答例（こちらが作った出力）に対するもの**。Vera の自由な出力に対して設計者の関数と一致するかは未検証（Vera の出力は `xcheck` に渡していない）。
- 活用表は閉じている（§10）。`en_create-01` の参考例の `order` は活用表に無い語形で `LEMMA_NOT_FOUND`（近似では `PASS`）。形態素解析は fugashi 1.5.2 に依存し、版は `run_meta.json` の `fugashi` に書く（辞書 unidic-lite の版は書いていない）。
  B3 を 2 回流した出力（`private/B3` と `private/B3-rerun`）は所要時間以外が一致した（`t4_s6_compare_B3.txt`: 145 ファイル）。
- `leakcheck` は **文字の窓の一致**（非 ASCII を含む 12 字の窓すべて・ASCII だけの文字列は 30 字の窓・8〜11 字の日本語の文字列は全体。3 問以上に現れる窓は共通の言い回しとして除く）しか見ない。
  言い換えられた中身・12 字未満の断片の散在・英語の短い語句は検出しない。公開物に残る中身の欄を減らすこと（`publish`）が主で、`leakcheck` は最後の網。
- B2 の `evidence`・`sources` の読み方は、W1-s で見た Vera の型つき結果の形（文字列・`text` を持つ辞書）からの推定。Vera が別の形で根拠を返すなら `evidence_match` は `UNJUDGED` や `FAIL` になりうる。
- 設計者に返す「バンク側の不備」の一覧は空（§12.5）だが、B3 の `must_express` などを決定的に判定できないことは **バンク側ではなく読解器側の欠け**（FINAL §6 条件 2 が読解器の受け入れ試験を求めている）。

### 12.12 T5・T6・漏れ検査・範囲の検査

- **T5**: 4 バンクの 9 分類・入口未到達の内訳・自明な戦略の点数・近似を当てた分類が `artifacts/w1-s2/<B>/summary.json`（と `summary.md`）にあり、§12.4 の数値はそこから再計算できる
  （`recount`: `t5_recount.txt` が 4 つとも「一致」）。非公開の `private/` 側は `.gitignore` で除外され、`git status --porcelain --ignored` で `!!`（無視）として出る（`scope_status.txt`）。
- **T6**（既存テストに新しい失敗が無い）: `env -i ... pytest -q -p no:cacheprovider -rfEs --tb=no --continue-on-collection-errors tests` の要約行は
  **124 failed, 4253 passed, 44 skipped, 82 xfailed, 68 xpassed**（`t6_pytest.txt`）。基点（`57a5218`）の失敗一覧 124 件（`dev_57a5218_failures.txt`）との差は、新しい失敗 **0 件**（`t6_new_failures.txt` が空。
  `t6_failed_now.txt`・`t6_failed_base.txt`）。成功は基点の 4,127 件に新規テスト 126 件（`tests/bank_score` は 125 件から 251 件へ）を足した数と一致する（4,127 + 126 = 4,253）。
- **漏れ検査**: `artifacts/w1-s2/leakcheck.txt` は `leakcheck: scanned_files=160 leaks=0`・`exit=0`（走査 160 ファイル、当たり 0。`grep -n scanned_files artifacts/w1-s2/leakcheck.txt` の数をそのまま書いた）。
  使った正確なコマンド（`$H` はバンクの親ディレクトリ、`F=tests/bank_score/fixtures`）:
  ```
  $PY -m tools.bank_score.leakcheck --items $H/B1_reading/v2/items.jsonl --items $H/B2_chat/v2/items.jsonl --items $H/B3_generation/v2/items.jsonl --items $H/B5_conductor/v2/items.jsonl \
      --frames $H/B5_conductor/v2/frames --scan artifacts/w1-s2 --scan docs/BANK_SCORE.md --scan docs/READING_CONVENTIONS.md --scan tests/bank_score --scan tools/bank_score \
      --exclude artifacts/w1-s2/private --exclude $F/B1 --exclude $F/B2 --exclude $F/B3 --exclude $F/B5 --exclude $F/invalid > artifacts/w1-s2/leakcheck.txt 2>&1; echo "exit=$?" >> artifacts/w1-s2/leakcheck.txt
  ```
  除外は非公開の `private/` と、既存の W1-s の見本 5 ディレクトリ（`tests/bank_score/fixtures/{B1,B2,B3,B5,invalid}`。変更不可・判断記録 38）だけ。`t2_b3_not_strict.tsv` も走査の対象に入っている。
  バンクの `items.jsonl` 4 つと B5 の枠（`frames/`）から作った照合語を使う。
- **範囲の検査**: 変更したのは許可パス（`tools/bank_score/**`・`tests/bank_score/**`・`docs/BANK_SCORE.md`・`artifacts/w1-s2/**`）と、上位の指示で追加された `docs/READING_CONVENTIONS.md` だけ。`verantyx/`・既存のテスト・既存の見本・`artifacts/w1-s/` は無変更
  （`git status --porcelain` と `git diff --stat`。`scope_status.txt`）。
