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

- `unscorable` の 2 種（`ITEM_INVALID` / `JUDGE_UNAVAILABLE`）は要約で分けて数える。
- 要約の最初の表に **正答率・誤答率・誤った応諾率・過剰棄権率・入口未到達率** を並べる。分母は 2 種を併記する:
  全問（隔離を除く）／到達した問題（`unreachable` と `unscorable:ITEM_INVALID` を除く）。
- V2_RULES と S2 は「escalate が正解なのに選択肢を返したら誤答」と言うが、9 分類の定義にちょうど当たるのは
  `false_compliance`（棄権すべきなのに答えた）。採点器は `false_compliance` に入れ、`correct` にならないことをテストで
  保証している（`test_b5_escalate_expected_but_option_returned_is_not_correct`）。要約は誤答率と誤った応諾率を並べるので、
  どちらの読み方でも失敗として見える。

## 5. 規則の定義（`normalize.py` / `lemma.py` / `checks.py`）

各規則は `PASS` / `FAIL` / `UNJUDGED`（判定できない）の 3 値。

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
