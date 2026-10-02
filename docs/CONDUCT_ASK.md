# conduct_ask: エージェントの聞き返しに、枠から答える

実装エージェントが「どの順で進めますか」「A と B のどちらにしますか」「これをやってよいですか」と聞き返してきたとき、
人間が最初に枠（`docs/frames/vera_project_frame.md` の書式）に書いた内容から答える。**枠から決まらないことは推測せず、
理由の型を付けて人間に上げる。** 第一の目標は「誤って答えない」こと、そのうえで答えられる範囲を広げること。

この文書の数値は、すべて `artifacts/w2-c/` の出力から再計算できる（各節に出典と再計算コマンドを置く）。
予想や未測定の値は書かない。

## 1. 使い方

```
python -m verantyx.conduct_ask --frame <枠.md|枠.jsonl> --question <文> [--option <肢> ...]
                               [--vocab-llm off|fake|codex|claude] [--vocab-fake <台本.json>] [--vocab-ledger <台帳>]
```

- 枠の形式（Markdown / JSONL）は内容で判定する（`project_frame.load_conduct_frame`）。
- 肢は 0 個、または 2 個以上（`--option` を繰り返す）。
- 公開 API: `verantyx.conduct_ask.answer_question(frame_path, question, options=None, *, vocab_llm="off", vocab_fake=None, vocab_ledger=None, chooser=None) -> dict`。
  `chooser` に `llm_choice.LLMChooser` を渡せば作り物のプロバイダで試せる。例外は投げず、想定外の失敗は `INTERNAL_ERROR` の JSON を返す。
- 副作用なし: 枠の隣にも作業ディレクトリにも何も書かない。`--vocab-ledger` を渡したときだけ、そのファイルに台帳を追記する（既定はメモリ上）。
- 既定の `--vocab-llm off` では LLM の部品を作らない。`codex` / `claude` は、語彙外の経路に入ったときに初めてプロバイダを作る。
  この変更では実プロバイダを一度も呼んでいない（試験はすべて作り物）。
- 標準出力には JSON を 1 個だけ（末尾に改行）。トレースバックは出さない（型名だけを標準エラーへ）。

終了コード: `0` = 決定を出した（answer / escalate）、`2` = 要求そのものの型付き拒否（質問が空・肢が 1 個・引数の誤り・枠が壊れている 等）、
`3` = `INTERNAL_ERROR`。

`python -m verantyx.cli` からはまだ呼べない（`verantyx/cli.py` と `conductor_run.py` は触らない約束。接続は別チケットの範囲）。

## 2. 出力（キーは常に全部出す）

```
{"schema": "conduct_ask/v1", "decision": "answer|escalate", "kind": "...", "answer": "...|null", "answer_option_index": 0|null,
 "derivation": "DIRECT|COMBINED|null", "resolver": null|["permission"|"order"|"scope"|"choice"|"acceptance", ...],
 "basis": [{"id","section","line","text"}], "escalate_reason": null|"...",
 "escalate_detail": null|"...", "vocab": null|{...}, "options": [{"index","text","ignored_marks","reading","maps_to"}],
 "trace": {"mentions_found","mentions_dropped_as_contained","resolvers_tried","resolver_outcomes"},
 "frame": {"path","sha256","format"}}
```

- `answer` が null でない ⇔ `decision == "answer"`。選択肢があるときは `answer_option_index` が int で、`answer` は `options[i]` の**原文そのまま**（推奨印も含む）。
  選択肢が無いときの `answer` は、枠に書かれた 1 個の語句（決定の値、方針の値、工程名、`command`）か、許可系の閉じた語句
  （日本語の質問では `許可` / `不可`、英語では `permitted` / `not permitted`）。複数要素になる答えや枠に無い言い回しが要る答えは `ANSWER_FORM_UNSUPPORTED` で上げる。
- `basis`: 根拠にした枠の記録（md の枠では ID・節・行・行の原文。jsonl では記録 ID・節・出現順・文）。LLM の証言は basis に入れない。
- `derivation`: 1 つの記録から決まったら `DIRECT`、2 つ以上を合わせたら `COMBINED`。
- `resolver`（第 7 ラウンドで足した。`derivation` の直後）: 答えを出した段の名前のリスト。名前は `permission`（許可の層）と `order` `scope` `choice` `acceptance`（解決器）の 5 つだけ。
  複数の解決器が同じ答えを出して `COMBINED` になったときは、答えた全部を解決器の並びの順に入れる。上げたとき・型付きの拒否・`INTERNAL_ERROR`・出口で答えが上げるに変わったとき（`MULTIPLE_QUESTIONS` など）は `null`。
  `derivation` の値（`DIRECT` / `COMBINED`）は記録の数の区別で、解決器の名前は持たない（既存の試験が値を固定しているので変えず、新しい欄にした）。
  答えについて「どの段が・どの記録から答えたか」は `resolver` と `basis[].id` の 2 欄だけで取り出せる（`trace` は経過の記録で、決まった欄ではない）。
- `kind`: 答えを出した経路の種別、無ければ `conductor.classify_question` の出力（参考値）。`classify_question` は経路の選択には使っていない
  （順序の質問を `OTHER` や `CHOICE` と分類するため。`trace` ではなく経路が `kind` を決める）。
- `vocab`: 語彙の対応づけを使った（または試みた）とき。枠の別名表で写したときは `provenance: "FRAME_ALIAS"`（枠の記録なので `counts_as_evidence: true`）。
  LLM の閉じた選択を使ったときは §6。使っていなければ null。
- `frame_refusal`（枠が使えないときだけ足したキー）: `project_frame.FrameRefusal.as_dict()` をそのまま入れる。
- `trace.view_skipped_records`（jsonl の枠で、この入口が読まなかった記録があるときだけ `resolver_outcomes` に入る）。

## 3. 理由の型

| `escalate_reason` | 意味 | チケットの型との対応 |
|---|---|---|
| `FRAME_SILENT` | 枠にその事柄を決める記録が無い（並列の工程・同点・許可リストの外・語は当たったが記録が決めない） | 枠が沈黙 |
| `FRAME_CONFLICT` | 枠の中で矛盾（同じ条件に違う値、優先順位が無い族どうしの衝突） | 枠内で矛盾 |
| `HUMAN_APPROVAL_REQUIRED` | `[protected_actions]`、`[escalation_conditions]`、枠が名指さない削除・公開・支出・認証情報に見える操作 | 人間の承認が必要 |
| `OUT_OF_RANGE` | 枠の決定を聞く質問ではない（進捗・状態、成果物の作成依頼） | 範囲外 |
| `VOCAB_UNMAPPED` | 質問の語が枠にも別名表にも無く、対応づけられない | 語彙が対応づけられない |
| `QUESTION_UNREADABLE` | 質問が空・肢の誤り、否定形・反転した質問、工程の節が読めない、「許可が必要か」と聞く質問、述語が読めない質問、1 つの質問に複数の問い | 質問が読めない |
| `NO_OPTION_ALLOWED` | どの肢も枠に反する（無理に肢を選ばない） | （足した型） |
| `ANSWER_FORM_UNSUPPORTED` | 答えは決まるが、肢が無く 1 語句で表せない | （足した型） |
| `FRAME_UNUSABLE` | 枠が読めない（`frame_refusal` に理由） | （足した型） |
| `INTERNAL_ERROR` | 想定外の失敗 | （足した型） |

足した 4 型の理由は §10 の判断記録。第 7 ラウンドの 3 つの detail の意味:
`RECORD_STANCE_UNREADABLE` = 操作を名指す別系列の記録（保護の操作なら不変条件、禁止の操作なら受入条件）の向き（要求か否定か）が閉じた形で読めない（§7）、
`INVARIANT_IS_CONDITIONAL` = 保護の操作と衝突する不変条件が、条件・時・主体を持つ否定で、一般の問いに「不可」とは言えない（§7）、
`PATH_CASE_DIFFERS` = 質問のパスが許可リストと大文字・小文字を畳んだときだけ一致する（§7）。いずれも型付きで上げる。`escalate_detail` は下位の理由（例 `TIE`、`UNORDERED`、`NO_STATE`、`NEGATED_QUESTION`、`INVERTED_QUESTION`、
`TERM_IN_WIDER_PHRASE`、`AMBIGUOUS_TERM`、`REQUIREMENT_OF_PERMISSION`、`PREDICATE_UNREADABLE`、`MULTIPLE_QUESTIONS`、`HUMAN_JUDGED_NOT_STATED`、`OUTSIDE_ALLOWLIST`、`PATH_NOT_PLAIN`（第 5 ラウンド）、`CONTEXT_SENTENCE_UNREAD`（第 5 ラウンド）、`RECORD_STANCE_UNREADABLE` `PATH_CASE_DIFFERS`（`FRAME_SILENT`）と `INVARIANT_IS_CONDITIONAL`（`HUMAN_APPROVAL_REQUIRED`）（第 7 ラウンド）、`NO_PRECEDENCE`、`BUILTIN_PROTECTED`、`VOCAB_LLM_OFF`、`LLM_ABSTAINED:DISAGREE`、`LLM_FAILED:TIMEOUT`）。

## 4. 層の順序（最初に決まった層の結果を出す。層どうしの結果は足し合わせない）

1. 入力の検査（空の質問・4000 文字超・肢が 1 個・空の肢・印を除いて同じになる肢）→ 型付き拒否、終了コード 2。
2. 否定形・反転した質問（否定語と同じ文に枠の語がある、または `avoid` / `以外` / `instead of` などがある）→ `QUESTION_UNREADABLE`。
3. `[escalation_conditions]` の条件語句（活用を許す）が質問に現れ、scope が ANY か質問の種別と同じ → `HUMAN_APPROVAL_REQUIRED`。
4. 語が長い語句の一部でないか（§5 の「より広い語句」。右側の付属語と、第 2 ラウンドで足した左側の修飾語）。
5. 許可の 3 段（§7）。
6. 解決器（順序・範囲・選択・受入条件）。複数が答えたら、全部同じ答えのときだけ答える（COMBINED）。違えば `FRAME_CONFLICT`。
   **答えを出す解決器はすべて**、述語が閉じた許可リストに当たるときだけ答える（§8。第 3 ラウンドで、順序の「X の前に Y を始めてよいか」と範囲の極性だけでなく、
   選択・「どちらが先か」・「次に着手できる作業」・複数の範囲の語を肢が名指す問いにも広げた）。
7. 進捗・状態の質問、成果物の作成依頼 → `OUT_OF_RANGE`。
8. 枠の語が 1 つも当たらない → 語彙外（§6）。当たったが決まらない → `FRAME_SILENT`。

出口（どの層で決まっても最後に通る 2 つの検査。答えを上げる側にだけ倒す）:
- 質問に「許可・承認・permission・approval が必要か／要るか／required／needed」の形があれば、答えになっていた結果は `QUESTION_UNREADABLE`（`REQUIREMENT_OF_PERMISSION`）に置き換える
  （「してよいか」と極性が逆なので、はい／いいえを返さない）。枠が沈黙・語彙外の結果も同じ型にする。承認が必要・矛盾の型で上がっていたものはそのまま。
- 答えようとしているのに、質問が 2 文以上の問いを含むなら `QUESTION_UNREADABLE`（`MULTIPLE_QUESTIONS`）。後の問いの述語が違うかもしれないため。
  第 3 ラウンドで、極性（はい／いいえ）の答えだけでなく、**すべての答え**に効かせた（肢の選択と枠の語句の答えを含む）。
- **読まれなかった文（第 5 ラウンド、`finish`）**: 答えようとしているのに、質問が 2 文以上あり、次のどれでもない文があれば `FRAME_SILENT`（`CONTEXT_SENTENCE_UNREAD`）。
  (a) 問いの文（`?` で終わる、または `か` で終わる文。問いの文が無いときは枠の語を含む文）、(b) 「次に着手できる作業」で解決器が「終わった」と読んだ前提の文（閉じた形 `<工程>と<工程>が終わりました` / `the <phase> and the <phase> are done` だけ。§8）、
  (c) 「誰かが承認した」を言う閉じた形の文（`Approved.` `承認済みです。` など。許可の層と同じ関数 `_sentences_unread` を使う）。
  `来年の話です。` `This is for the courier app.` のような条件・時・別の対象の文は、どの層も読んでいないので答えを上げる側に倒す（文を分けるだけで答えが出る穴だった）。
  すでに上げている結果の理由・detail は変えない。挨拶の文（`Thanks.` `よろしくお願いします。`）も読まれない文として上げる（閉じた挨拶の組は足していない。§10 の 42）。

同点は棄権する。「最初の 1 つ」「辞書順」で勝者を作る箇所は無い（候補から 1 つを取り出すのは、ちょうど 1 つに決まったことを確かめた後だけ）。

## 5. 語の照合（決定的・完全一致のみ）

- 正規化: NFKC、大小文字の畳み込み、引用符の除去、空白の連続を 1 つに。
- 日本語は部分文字列一致（2 文字未満の語は索引に入れない）、英語は単語境界のトークン列一致（冠詞は無視、先頭語だけ -s/-es/-ed/-d/-ing の規則活用を許す）。
- 操作名（禁止・保護・上げる条件）は活用を許す: `…する` は語幹で、それ以外のう段で終わる語は末尾 1 文字を落とした形で照合する。
- 工程の見出し語（日本語は最後の `を` より前、英語は先頭の動詞と冠詞を落とした残り）でも照合する。同じ見出し語が 2 つの工程にあれば使わない。
- 最長一致: 別の言及に厳密に含まれる言及は捨てて数える（`trace.mentions_dropped_as_contained`）。同じ位置に別々の役割の語が当たったら `AMBIGUOUS_TERM`。
- **より広い語句**: 当たった語が、質問の中でより長い名詞句の一部なら、別のものとして扱い `FRAME_SILENT`（`TERM_IN_WIDER_PHRASE`）。
  右側: 日本語では語の直後が `の…`、`以外`、`のコピー` など、または直前が助詞・句読点でない文字。英語では語の直後に機能語・問いの動詞（`start` `begin` など）以外の語が続く。
  **左側（第 2 ラウンド、第 3 ラウンドで改めた）**: 英語では語の直前の語が、閉じた機能語の表（冠詞・指示詞・助動詞・前置詞・接続詞・代名詞・wh 語）に無ければ修飾語とみなす（`secondary` `backup` `per-host` など）。
  `use` `include` `start` `pick` のように名詞・形容詞にもなる動詞・動名詞（`test` `build` `record` `support` `target` `document` `ship` `run` `plan` `count` `keep` など）は、
  **動詞の位置にあるときだけ**修飾語とみなさない。動詞の位置 = 文頭か節の頭、直前が主語の代名詞（`we` `I` `you` `they`）・`to`・`let's`・`please`（間に `also` `just` などの副詞があってもよい）。
  動名詞は前置詞や `be` の後ろも動詞の位置。`which` `what`・冠詞・所有代名詞の直後では名詞の修飾語（`Which test radio band …` は `TERM_IN_WIDER_PHRASE`）。
  日本語では `X の＋語` の X が、閉じた指示の語（`この` `その` `あの` `どの` `どちらの` `今回の` `今の` `本件の`）でも枠の語でもなければ修飾語とみなす（`予備の…` `バックアップの…`）。
  `リリースの` `プロジェクトの` `案件の` `版の` は、**直前が `この` `今回の` `本` `当` `今の` のときだけ**一般語（`このリリースの保存形式`）。`次回の` `次のリリースの` `前の版の` `別の案件の` `他のプロジェクトの` `現行の` `現在の` は
  別の時・別の対象を名指すので修飾語（許す側を列挙し、拒む語は列挙しない）。
  ただし語が、質問に添えられた肢の文字列の中にあるときは、その修飾は肢が提示する選択そのものなので「より広い語句」とみなさない。
  例: 条件 `価格の自動計算` に対して `価格の自動計算のコピー`、条件 `circuit breaker` に対して `circuit breaker library`。
  プロジェクトの条件より狭い言い回しも、LLM が条件へ写した結果が部分文字列の関係にあれば採用しない（§6）。
- 名詞化（`…を検出する` と `…の検出`）は当てない。語彙外か上げる。
- 推奨の印（`（推奨）`、`(recommended)`、`おすすめ`、`default` など閉じた表）は肢の照合の前に外し、`options[].ignored_marks` に記録する。印は根拠に使わない。

## 6. 語彙外（LLM の閉じた選択、既定はオフ）

質問に枠の語が 1 つも当たらず、質問の役割（範囲・選択・許可・順序の手がかり）が読めたとき、`--vocab-llm` が `off` 以外なら
`llm_choice.LLMChooser` に「枠の語のうち一番近いものはどれか」を聞く（独立 2 回の一致だけ採用、台帳、証言の型）。

- 質問の語: 手がかり句・肢の文字列・端の助詞を取り除いた残りの連続した 1 区間。0 個か 2 個以上なら `VOCAB_UNMAPPED`（`NO_SINGLE_TERM`）。役割が読めなければ `NO_ROLE`。
- 候補は役割で絞る: 範囲 → SCOPE 方針の条件、許可 → CONFIRM 方針の条件と禁止・保護の操作名、選択 → CHOICE 方針の条件と決定の主題、順序 → 工程名。17 個以上は `llm_choice` が `REFUSED:TOO_MANY_CANDIDATES` を返す。
- 採用されたら、その語を質問の語の代わりにして、その役割の規則だけで 1 回やり直す。決まらなければ、やり直しの結果の型で上げる。
  根拠（`basis`）は枠の行だけ。`vocab`: `{"question_term","candidates","frame_term","provenance":"LLM_TESTIMONY_MAPPING","counts_as_evidence":false,"outcome":"ADOPTED|ABSTAINED:<理由>|FAILED:<種別>|REFUSED:<理由>|OFF|…","ledger_decision_id","asks":[…]}`。
- 棄権 → `VOCAB_UNMAPPED`（`LLM_ABSTAINED:DISAGREE|NONE_SELECTED|INVALID_ANSWER`）、失敗 → `VOCAB_UNMAPPED`（`LLM_FAILED:<種別>`）、オフ → `VOCAB_UNMAPPED`（`VOCAB_LLM_OFF`）。
- 削除・公開・支出・認証情報に見える許可の質問は、最後まで対応づけられなければ `HUMAN_APPROVAL_REQUIRED`（`BUILTIN_PROTECTED`）で上げる（答えを出す方向には使わない）。

作り物のプロバイダ（`--vocab-llm fake --vocab-fake <台本.json>`）。台本は JSON の 1 個のオブジェクト:

```
{"pick": "<枠の語>|null", "pick2": "<2 回目だけ別の語>(任意)", "fail": "TIMEOUT|NONZERO_EXIT|…(任意)"}
```

作り物は prompt の候補行（`^\d+: {json}$`）を読み、`pick` が候補にあればその番号を `{"choice": n}` で返し、無ければ `{"choice": null}`。
`fail` があれば型付きの失敗を返す。`pick2` があれば 2 回目はそちらを選ぶ。台本は 1 プロセス（1 問）分。台本が無い・読めないときは終了コード 2 の型付き拒否。
これは「LLM が最も近い語を正しく選ぶ」という**仮定**であり、実際の LLM の測定ではない。

## 7. 許可の 3 段（と書き込み許可）

質問に操作が見つかったとき（許可の手がかり: `てよい`、`may I`、`can we` など。第 2 ラウンドで、名詞の `許可` と `permission` だけでは手がかりにしないことにした。
「許可が必要か」は「してよいか」と極性が逆なので、§4 の出口で上げる）:

1. `[forbidden_actions]` にある → **不可と答える**（承認が得られたと質問に書いてあっても同じ。人間に上げない）。
2. `[protected_actions]` にある → `HUMAN_APPROVAL_REQUIRED`。質問の「承認済み」という主張は記録ではないので数えない。
3. CONFIRM 方針の条件に当たる → 値の極性（`permitted` / `許可` / `可` ↔ `not permitted` / `不可` など閉じた表）で答える。条件が複数当たって値が違えば `FRAME_CONFLICT`。
   **答えの出口（答えが出た後に必ず通る。「許可」にも「不可」にも、値が肢と一致した答えにも、禁止・優先順位・保護と不変条件・書き込み許可の答えにも、同じ）**:
   (i) 許可の手がかりのある文が過去形（`was/were/did/had …`、`…でしたか` `…ていましたか` `…てもよかったですか`）なら `QUESTION_UNREADABLE`（`PAST_TENSE_PERMISSION`）。
   (ii) 「許可」と答えようとしていて、問いが「すべきか」（`should we` / `べき` / `した方がよい`）なら `FRAME_SILENT`（`ADVICE_NOT_PERMISSION`）。枠の「許可」は「してよい」であって「すべき」ではない。
   (iii) **閉じた形の門（第 4 ラウンド、`_perm_form_ok`）**: 枠の記録が決めているのは「この作業の担当（自分たち）がその操作を（今）してよいか」だけである。
   やめる・延期する・省略する・外注する・手順を書く、別の主体、別の時、別の目的は決めていない。そこで、許可の手がかりのある文の中で、曖昧でない言及のうち CONFIRM 方針・禁止・保護を持つもの全部
   （そういう言及が無く答えがパスから来たときは、その文の中のパスの字句。パスが 2 つ以上なら上げる）について、文の頭から対象の前まで（L）と、対象の後ろから文末まで（R）が、次の閉じた形に**全体一致**したときだけ答える。
   一致しなければ `FRAME_SILENT`（`PERMISSION_FOR_ANOTHER_OPERATION`: 操作の動詞が表に無い。`PERMISSION_FOR_ANOTHER_SUBJECT_OR_CONDITION`: 主体・時・対象・条件が形に無い。決めにくいときは後者）。
   禁止リスト（`中止` `stop` `remove` などを並べて拒む書き方）は無い。許す形だけを列挙している。
   - **英語の L**（対象は語幹で当たるので、`running X` の語に対し問いは `run X` の位置から始まり、間は空でよい）: `[so/and/then/also/ok/okay/well/now,] (can|could|may|might|should|shall) (I|we) <GAP>`、
     `(is|would) it [be] (ok|okay|fine|alright|allowed|permitted|acceptable) [for us/me] to <GAP>`、`(am I|are we) (allowed|permitted) to <GAP>`。
     `<GAP>` は 空、または `do|perform|carry out|try|start|begin|continue|keep|go ahead and`（CONFIRM・禁止・保護）。パスは `edit|modify|change|update|write to|write|create|add to|touch` が必須。
     `you` `they` は主語に入れない。**R**: 空、または `now|today|please|then|too|also|here` と `for|in this|the|our release|project|version|iteration|build` だけ。
   - **記録の言い直し（L4・R2、英語の禁止・保護だけ）**: 答えの根拠に、その操作と衝突した別の系列の記録（受入条件か不変条件）が入っているとき、その記録の本文から、操作の前の語列（末尾の助動詞を除く）を主語、
     後ろの語列を続きとして作る。問いが `(can|could|may…) <その主語> <操作>` で、続きがその続きに一致するとき（または R が通常の形のとき）だけ、名詞の主語と目的の句を許す。記録に無い主語・目的は上げる。
     規則は問いの固有の語を持たない（記録の本文から作る）。
   - **優先順位で「可」になった禁止の操作（第 5 ラウンド）**: 答えが「可」（`polarity == "YES"`）で、対象に禁止の操作を持つ言及があるとき、その「可」は別の系列の受入条件・不変条件が
     優先順位で禁止に勝ったからで、その記録が書いている主体と目的の場面にだけ当てはまる。この対象は L4（記録の言い直し）と（R1 か R2）だけを許し、`may we <操作>` `can I <操作>` `is it okay for us to <操作>` は一致しない。
     **第 6 ラウンド**: 言い直した記録が続き（操作の後ろの語列。条件・時・目的）を持つとき、問いはその続きをそのまま言う形（R2）でなければ答えない。
     記録の主語が `we` のときは L4 の形が一般の問い `may we <操作>?` と同じ文字列になるので、R1（空・`now`・`for this release` など）では答えない
     （`We will drain X after the yearly inspection` が禁止に勝つ枠で、`May we drain X?` `… now?` `Can we …?` は上げ、`May we drain X after the yearly inspection?` は「可」）。
     続きが空の記録だけ R1 で答える。禁止が勝つ「不可」と保護 × 不変条件の「不可」には、この制限をかけない。
     言い直せる記録が無いとき、日本語（言い直しを作らない）は常に上げる（`FRAME_SILENT`、`PERMISSION_FOR_ANOTHER_SUBJECT_OR_CONDITION`）。
     禁止が勝って「不可」になる答え、保護と不変条件で不変条件が勝つ「不可」は一般の問いでも「不可」で正しいので、この制限をかけない。
   - **日本語の L**: CONFIRM・パス・語彙外は `では|それでは|さて|ちなみに|今回は|まず|今は|では今` の談話語だけ。禁止・保護は、これに加えて「<誰か>の承認を得たので、」の承認の節を許す（禁止は承認があっても不可なので答えは変わらない）。`業者が` `来年は` は上げる。
   - **日本語の R**: CONFIRM の語（名詞）は `(を|は)?(し|行っ|おこなっ|実施し|実行し|やっ|始め|開始し|送っ)て[も](よい|いい|良い|構わない|かまわない|よろしい)[です](か|でしょうか)`（`問題ないですか` も）、
     `(する|行う|…)[こと](は|が)(でき|可能)(ます|る|です)か`、`(は|が)(許可|承認)され[てい](ます|る)か`。パスは `(を|に)?(書き換え|更新し|編集し|変更し|修正し|作成し|追加し|書い|書き込ん)て…` と辞書形の `…ことはできますか`。
     禁止・保護の操作は、その操作自身の動詞の残りだけ（操作の辞書形から `_ja_verb_forms` で作る。`削除する` なら `して…` / `する…`。名詞で書かれた操作は CONFIRM の語と同じ形）。
     `するのを中止して…` `する手順を書いて…` は一致しない。別名経由の操作は別名の語形から同じ規則で作る。語彙外（LLM の対応づけ）の言及は、語の後ろが CONFIRM の名詞の形か、動詞語幹の直後の `<1〜2 字>てもよいですか` のどちらか。
   - **他の文**（第 5 ラウンドから §4 の出口と同じ関数 `_sentences_unread`）: 許可の手がかりのある文のほかの文は、「誰かが承認した」を言う文（`Approved.` `The lead approved it.` `町内会長が許可しました。` `承認済みです。` `担当者の承認は得ています。` など、閉じた形）だけ許す。
     それ以外の文（`Only the vendor will do it.` `来年の話です。`）は主体・時・条件を持ちうるので上げる。
     **第 6 ラウンド**: 許可の層の外の答え（選択・値・範囲・順序。承認は答えを変えない）では、承認の文は前置きの無い形だけ許す
     （英語 `Approved.` `Approval was given.` `Approval is granted.` `Approval obtained.`、日本語 `承認済みです。` `許可をもらいました。` `承認を得ています。` など。`_PEN_APPROVED_BARE` `_PJA_APPROVED_BARE`）。
     `Next year approved.` `The old greenhouse team approved.` `来年度の承認済みです。` `中学校の承認をもらいました。` `旧システムの確認済みです。` のように、誰が・いつ・何についての承認かを前に置いた文は上げる
     （`CONTEXT_SENTENCE_UNREAD`）。許可の層の答えは従来の広い形のまま（`町内会長が許可しました。` `代表から承認をもらっています。` を答え続ける）。
4. `[write_allowlist]`: 質問のパスが許可リストの接頭辞（パスの区切り単位）の下なら可（上の門を通ったときだけ。`Can I edit <パス>?` の形で、`read` `copy` `業者が` `来月` `on another thing` は上げる）。**リストの外は不可と答えず `FRAME_SILENT`**。許可リストの節が無ければ `NO_ALLOWLIST`。
   **第 5 ラウンド**: パスの字句を `/` で分け、`.` や `..` だけから成る区切り（`a/../b` `a/./b`）があれば、許可リストの接頭辞に当たっていても照合せず `FRAME_SILENT`（`PATH_NOT_PLAIN`）で上げる
   （正規化して判定し直さない。答える範囲を広げないため）。先頭の `./` を 1 つ落とすのは従来どおり。リストの外の `..` 付きのパスの型は従来の `OUTSIDE_ALLOWLIST` のまま。
   **第 7 ラウンド（S-C、`PATH_CASE_DIFFERS`）**: 照合は大文字・小文字を畳んだ質問（`ctx.q`）で行うので、`KIOSK/x.py` が許可リストの `kiosk` に当たっていた。大文字・小文字は別のディレクトリになる
   ファイルシステムが多いので、**今の照合で許可リストに当たったパスだけ**、畳まない読み（`ctx.q_case`、NFKC・引用符・空白は同じ）から取り出した同じパスが、許可リストの記録の文字列と全体一致または `記録/` の接頭辞一致するかを確かめる。
   一致すればその記録を basis にして従来どおり「可」、しなければ `FRAME_SILENT`（`PATH_CASE_DIFFERS`）で上げる。2 つの読みから取り出したパスの並びが畳んで一致しないときは、どのパスも文字どおりには照合しない（上げる）。
   判定の順番は `OUTSIDE_ALLOWLIST` → `PATH_NOT_PLAIN` → `PATH_CASE_DIFFERS` → 可（すでに上げている問いの型を変えない）。許可リストや質問の側を正規化して比べ直さないので、
   リストの記録に大文字がある枠（`W1: App`）で答えが増えることはない（`artifacts/w2-c/r7/probe_path_widening.txt`: 4 通りのリスト × 10 通りの綴り × 5 通りの末尾の 200 問で、上げる → 答えが 0、答え → 上げるが 30）。接頭辞より後ろの大文字（`kiosk/Fare.py`）は記録の下なので「可」のまま。
5. どれにも無い → 次の層（最終的に `FRAME_SILENT` か語彙外）。不在を否定にしない。

族どうしの衝突（`[conflict_precedence]`）: 禁止された操作を要求する受入条件、保護された操作を否定する不変条件があるとき、
`higher > lower` が書いてあれば higher の族の結論に従い、その `R` 行と相手の記録を basis に入れる。書いていなければ `FRAME_CONFLICT`（`NO_PRECEDENCE`）。
方針どうし・決定どうしの矛盾（同じ条件・主題に違う値）は族ではないので、優先順位があっても常に `FRAME_CONFLICT`。

**記録の向き（第 7 ラウンド、S-A、`_record_stance`）**: 衝突の相手を探すとき、操作を名指す記録（保護の操作は不変条件、禁止の操作は受入条件）の向きを、
**操作そのものにかかる否定の閉じた形**だけで決める（否定語の表は広げない）。向きは次の 3 つ。
- **NEG（否定）**: 操作の語のすぐ前（英語）／すぐ後ろ（日本語）に閉じた否定の形があり、記録のほかの場所に否定語が無い。
  英語の閉じた形: `never` `not` `no longer` `cannot` `can't` `won't` `don't` `doesn't`、および `never` `not` `no longer` の直前に助動詞（`will|must|shall|should|do|does`）が 1 つ入った形。
  日本語の閉じた形: 操作が `…する` なら `しない` `しません` `することはしない` `することはしません`、う段の動詞なら 未然形＋`ない`・連用形＋`ません`・辞書形の末尾＋`ことはしない／しません`、名詞の操作なら `はしない` `をしない` `しない` `はしません` `をしません` `しません`。
  `ことはない` `ことはありません`（「その必要はない」とも読める）と、`禁止` `許さない` を使った言い方は閉じた形に入れない。
- **POS（要求・肯定）**: 記録のどこにも否定語が無い（`禁止` `許さ` も無い）。
- **UNREADABLE**: そのどちらでもない（否定語が操作の外にある、操作の位置が取れない、閉じた形でない否定が操作にかかっている）。どちらの向きにも倒さない。
`unreadable` が 1 つでもあれば、優先順位を見る前に `FRAME_SILENT`（`RECORD_STANCE_UNREADABLE`）で上げる（記録を basis に入れる）。保護の操作で NEG は不変条件の否定、禁止の操作で POS は受入条件の要求として、従来どおり衝突に数える。
NEG には「無条件」の区別がある。英語は主語が空か `we` だけで、操作の後ろ（続き）が空のとき。日本語は操作の前が空か `私たち|我々|われわれ` ＋ `は|が`（読点可）だけで、後ろが空（句点だけは可）のとき。
`<名詞>は` 一般は主語として許さない（`卒園前は…` は時の条件）。それ以外の NEG は条件つき。

**保護の操作 × 不変条件の「不可」（第 7 ラウンド、S-B）**: 優先順位で不変条件が勝つとき、衝突した不変条件が全部無条件なら従来どおり「不可」。
1 つでも条件つきなら、条件の外では保護（人間の承認が必要）なので `HUMAN_APPROVAL_REQUIRED`（`INVARIANT_IS_CONDITIONAL`）で上げる。**条件を言い直した問いにも答えない**（答える範囲を広げないため）。
優先順位の無い衝突（`NO_PRECEDENCE`）、保護が勝つ場合（`PROTECTED_ACTION`）、禁止が勝つ「不可」は変えない。

## 8. 質問の種類ごとの規則

- **順序**: 辺 `A -> B` から推移閉包。「どちらが先か」は一方からの道があれば先、無ければ `UNORDERED`（`FRAME_SILENT`）。
  「X の前に Y を始めてよいか」は、X が Y の祖先なら「いいえ」、Y が X の祖先なら「はい」、並列なら `UNORDERED`。
  **述語の許可リスト**: 答えるのは、Y への動作を聞く形だけ（日本語: `Y（を）<動詞>てもよいですか` `…できますか`。英語: `can/could/may/might/should we <動詞> Y`、`can Y start/begin/…`、`is it ok/allowed to …`、`are we allowed to …`）。
  **Y にかかる動詞は閉じた許可リスト（第 3 ラウンド）**: (a) 着手の動詞（英語 `start` `begin` `work on` `proceed with` `get started on` `tackle` `kick off`、日本語 `始め` `着手し` `取りかか` `開始し` `スタートし`）と
  (b) Y の工程名そのものの動詞（英語は工程名の先頭の語、日本語は最後の `を` の後ろの動詞。日本語は `作って` `作り始めて` `作ることはできますか` のように活用を許す）だけ。
  Y の直後から文末の許可の言い方までが、この形に**全体で一致**しなければならない（`作るのを中断して` `作り直して` `作るのを止めて` `stop` `postpone` `redesign` `freeze` `pause` `cancel` は一致しないので上げる。枠は工程を始める順しか決めていない）。
  `Y は、X 前に <動詞>てもよいですか` の形（Y が先頭の主題）は、動詞が `前に` の後ろに来る。
  `早すぎますか` `危険ですか` `would it be a mistake` `is it risky` のような評価の述語は、列挙しきれないので禁止リストにせず、許可リストに当たらなければ `QUESTION_UNREADABLE`（`PREDICATE_UNREADABLE`）で上げる。
  「X に着手する前に終わっているべき作業」は直前の工程の集合 D と祖先全体 A に対し、S が D を含み A に収まる肢が真。`だけ` / `only` は S = D = A のときだけ真。ちょうど 1 つが真なら答え、2 つ以上なら `TIE`、0 なら `NO_OPTION_ALLOWED`。
  「次に着手できる作業」は、質問で「終わった」とされた工程（jsonl の枠では TASK の完了）から決める。状態が無ければ `NO_STATE`（md の枠は工程の状態を持たない）。着手できる工程が複数なら、肢がそのすべてを名指す場合だけ答え、そうでなければ `TIE`。
  **前提の文（第 5 ラウンド）**: 「終わった」と読む文は閉じた形だけ: 英語 `[so/and/then/also/ok/okay/well/now,] [the|our|a|an] <工程>(, | and )… (is|are|has been|have been) [now|all|already] (done|finished|completed|complete)`、
  日本語 `[談話語]<工程>[を<その工程の動詞の て形>](と|、)…[は|が|も](終わり|完了し|済み)(ました|ています)`。`done in the old prototype` `旧版では…が終わりました` `…が来年終わります` のように時・場所の修飾が付く文は、
  工程の状態としては読んだとしても「読まれた文」に数えず、§4 の出口で `CONTEXT_SENTENCE_UNREAD` で上げる。
  **述語（第 3 ラウンド）**: 「次に」の文は `what can we start next` `what is next` `what comes next` `what can be started next`、`次に着手できる作業は何ですか` `次は何に着手できますか` などの閉じた形だけ（`what did the competitor start next` `次に着手したのはどれですか` は上げる）。
  **肢が読めないとき（第 4 ラウンド）**: 「どちらが先か」で肢が 1 つでも工程として読めなければ `VOCAB_UNMAPPED`（`OPTION_UNMAPPED`）。（確かめる位置は、候補を作る前。肢が読めず工程も順序づかない問いは `UNORDERED` ではなく `OPTION_UNMAPPED` になる。）「どの肢も不可」（`NO_OPTION_ALLOWED`）は、全部の肢が読めたうえで当てはまらないときだけ。
  「どちらが先か」の文も `which comes first` `which should we do first` `which is first`、`どちらを先に作りますか` `どちらが先ですか` などの閉じた形だけ（`which was built first last time` `which is easier to do first` `どちらが先に完成しましたか` `競合は…どちらを先に…` は上げる）。
- **範囲**: SCOPE 方針の条件が当たったとき、値の極性で答える（`範囲外ですか` のように外側を聞く質問は極性を反転）。
  **述語の許可リスト**: 語の前が `is/are/do/should… [we/it] [include…] the` の形、語の後が `in scope` / `out of scope` / `included` / `part of the …`（英語）、
  または `は範囲に含めますか` `を対象に入れてよいですか` `は範囲外ですか` の形（日本語。助詞の直後の読点を許す）のときだけ。`含めるのは誤りですか` `is it wrong to include …` は `PREDICATE_UNREADABLE`。条件が当たらなければ答えない（不在は範囲外ではない）。複数の条件を肢が名指すときは、真がちょうど 1 つで残りが全部偽のときだけ。
  **第 3 ラウンド**: 前の助動詞から過去形（`was` `were` `did`）を外した。後ろの修飾は、`for|in|of` ＋ `this|the|our` ＋ `release|project|version|iteration|build|scope` の閉じた形に全体一致のときだけ（`in scope for the old prototype` `included in the price` `in the previous release` は上げる）。
  日本語は条件の前に `今回の` `このリリースの` などの閉じた語以外（`前の版では` `来年は`）があれば上げる。
  複数の条件を肢が名指す問い（`which is in scope, A or B`、`which of A and B should we include`、`AとBのうち、範囲に含めるのはどちらですか`）も、この閉じた形だけ（`…for the old prototype` `…did we include last year` `…is cheaper to include` `競合は…` は上げる）。
- **選択**: CHOICE 方針の条件、または決定 `主題 => 値` の主題が質問に当たり、値と一致する肢がちょうど 1 つのとき。主題が当たらないのに肢が値と一致するだけでは答えない。肢が極性（はい/いいえ）なら値を極性に写さず `FRAME_SILENT`。
  **述語（第 3 ラウンド）**: 答えるのは「自分たちの今回の選択」を聞く閉じた形だけ。文全体を、主題を `¤`、提示された肢を `§` に置き換えて照合する。
  英語: `which|what ¤ (do|should|shall|will|would) (we|I) (use|pick|choose|adopt|select|target|take|go with|want [to …])` ［`, A or B`］、`which|what ¤`、`what is|are|'s the ¤`、`(should|do) we use [the] ¤ [of A or B]`、
  `(should|do) we use A or B for the ¤`、`what should the ¤ be`、`what should we use for the ¤`（語尾に `for|in|of (this|the|our) (release|project|…)` を 1 つ許す）。
  日本語（第 4 ラウンドで閉じた 5 つの組だけにした。`の扱い` `の場合` `について` などの付属語と、`は|って` と、肢の並び `AとBの` は許す）:
  P1 `(どれ|どちら|何|なに)にし(ます|ましょう)(か|でしょうか)`、P2 `(どれ|どちら|何|なに)を(使い|使用し|採用し|選び)(ます|ましょう)(か|でしょうか)`、P3 `どうし(ます|ましょう)(か|でしょうか)`（肢の並びを挟まない）、
  P4 `(どれ|どちら|何|なに)(です|でしょう)(か|かね)`、P5 `どこにし(ます|ましょう)(か|でしょうか)`（**答えの元の記録の主題が `場所|置き場|位置|保存先|置き先|宛先|送り先` のどれかで終わるときだけ**。別名なら正規形で見る）。
  `(どちらの|どの)¤` の後ろは `を(使い|使用し|採用し|選び)ます…` か `にします…` だけ。`いつ` `いくつ` `いくら`、`どこに使う`、`何に使う`、`どう使う` はどの組にも入らないので上げる
  （型は `QUESTION_UNREADABLE`/`PREDICATE_UNREADABLE`。肢が はい／いいえ なら `FRAME_SILENT`/`POLARITY_QUESTION_ON_A_VALUE`）。
  比較・評価（`cheaper` `速い` `読みやすい`）、過去・完了（`did … use` `でしたか` `使いましたか` `have we used`）、別の主体（`the competitor` `the vendor` `業者の`）、別の時（`来年` `前回` `next generation`）、`could we use`、`in the field` は上げる。
  肢が極性（はい／いいえ）の問いでこの形に当たらなければ、従来どおり `FRAME_SILENT`（`POLARITY_QUESTION_ON_A_VALUE`）。
  主題の値が肢に無いときは、全部の肢が枠の語として読めたときだけ `NO_OPTION_ALLOWED`（`VALUE_NOT_OFFERED`）。読めない肢が 1 つでもあれば `VOCAB_UNMAPPED`（`OPTION_UNMAPPED`）。
- **受入条件**: 受入条件の ID と「人が判定するか」の質問、または機械的な条件の `command` を聞く質問。
- **進捗・状態・作成依頼**: `OUT_OF_RANGE`。

## 9. 測定値

自作の検査データ: `tests/conduct_ask/fixtures/`（枠 11 個、質問 161 問。うち日本語 101 問・英語 60 問、取り置き枠 3 個 = 42 問、開発用 119 問）。
実装より先に書いて凍結した（`artifacts/w2-c/fixtures_freeze.txt` のハッシュと時刻。`artifacts/w2-c/fixtures_vs_code_times.txt` に作成時刻の比較。凍結後に正解は変えていない）。
**注意**: この検査データは、閉じた規則を知っている実装役が書いたものなので、監査役の評価バンクより易しい可能性がある。値は上限の目安として読むこと。

### 9.1 配分（出典 `artifacts/w2-c/fixtures_validate.txt`、再計算 `tests/conduct_ask/run_bank.py` の入力検査 / `tests/test_conduct_ask_bank.py::test_fixture_shape_matches_the_promise`）

| 区分 | 問数 |
|---|---:|
| そのまま（direct） | 41 |
| 組合せ（combined） | 40 |
| 語彙外（oov、うち「どれも近くない」13） | 40 |
| 上げるのが正解（escalate） | 40 |

上げるのが正解の内訳: `FRAME_SILENT` 16、`OUT_OF_RANGE` 10、`HUMAN_APPROVAL_REQUIRED` 8、`FRAME_CONFLICT` 6、罠 16 問（沈黙の中に含む）。
許可系の質問: 可 12・不可 12・上げる 14。

### 9.2 Q1 / Q2（出典 `artifacts/w2-c/bank/{fake,off}/summary.json`、1 問 1 プロセスで測定）

再計算: `cd <ツリー> && artifacts/w2-c/py.sh tests/conduct_ask/run_bank.py --items tests/conduct_ask/fixtures/items.jsonl --frames tests/conduct_ask/fixtures/frames --vocab-llm fake --split all --subprocess --out artifacts/w2-c/bank/fake`
（`off` も同様）。集計の再計算: `artifacts/w2-c/py.sh tests/conduct_ask/run_bank.py --recount artifacts/w2-c/bank/fake`（結果は `artifacts/w2-c/bank/recount.txt`、両方 MATCH）。

| 指標 | fake（作り物の LLM） | off |
|---|---:|---:|
| 全体 | 161 | 161 |
| 誤って答えた（上げるのが正解なのに答えた） | 0 | 0 |
| 誤って答えた（答えが正解と違う） | 0 | 0 |
| Q1: 誤答率（誤答 / 全体） | 0.0 | 0.0 |
| 答えるのが正解の問 | 108 | 108 |
| Q2: 正しく答えた割合 | 0.9815（106/108） | 0.7315（79/108） |
| 　そのまま | 0.9756（40/41） | 0.9756（40/41） |
| 　組合せ | 0.975（39/40） | 0.975（39/40） |
| 　語彙外 | 1.0（27/27） | 0.0（0/27、オフでは常に上げる） |
| 上げるのが正解の問 | 53 | 53 |
| 　正しく上げた | 53（1.0） | 53（1.0） |
| 　理由の型が一致 | 53（1.0） | 53（1.0） |

開発用と取り置き（同じファイル）:

| 指標 | fake 開発 | fake 取り置き | off 開発 | off 取り置き |
|---|---:|---:|---:|---:|
| 問数 | 119 | 42 | 119 | 42 |
| 誤答 | 0 | 0 | 0 | 0 |
| 答えるのが正解の問の正答率 | 0.9868（75/76） | 0.9688（31/32） | 0.7368（56/76） | 0.7188（23/32） |
| 上げるのが正解の問を正しく上げた | 43/43 | 10/10 | 43/43 | 10/10 |

答えなかった 2 問のうち 1 問目（開発用 `w2c-f08-03`、off・fake とも）は第 4 ラウンドで答えなくなった: 問いは `Can we hand a handset to a visitor for the pilot?` で、枠は「来訪者に端末を渡す: 不可」。
`for the pilot` は閉じた後ろの修飾（`now` `for this release` など）に無いので `FRAME_SILENT`（`PERMISSION_FOR_ANOTHER_SUBJECT_OR_CONDITION`）で上げる（§7 の門。正しい向きの変化として受け入れ、`pilot` を許す規則は足していない。
凍結した正解は変えていない。この問は Q2 の分母に残る。出典 `artifacts/w2-c/r4/bank_changes.txt`）。2 問目（取り置き `w2c-f10-07`）は、質問が `欄の位置の検出` と名詞化して書いており、枠の工程 `欄の位置を検出する` の見出し語 `欄の位置` が
「より広い語句」の一部になるため `TERM_IN_WIDER_PHRASE` で上げた（§5 の「名詞化は当てない」の設計どおり。誤答ではない）。
取り置き枠を見てから規則を調整していない。

罠 16 問は 16 問とも正しく上げた。「どれも近くない」13 問は 13 問とも上げた（`artifacts/w2-c/bank/fake/summary.json` の `trap` / `oov_none`）。

### 9.3 Q3 語彙外（出典 `artifacts/w2-c/q3_vocab.txt`、再計算 `artifacts/w2-c/py.sh -m pytest -p no:cacheprovider -v tests/test_conduct_ask_vocab.py`）

13 本が通る。採用（2 回一致 → 対応づけで回答、`provenance == "LLM_TESTIMONY_MAPPING"`、`counts_as_evidence is False`、`ledger_decision_id` あり）、
不一致 → `LLM_ABSTAINED:DISAGREE`、どれも近くない → `LLM_ABSTAINED:NONE_SELECTED`、失敗 → `LLM_FAILED:TIMEOUT`、オフ → `VOCAB_LLM_OFF` を別々の試験で確かめる。
試験中は `subprocess.run` / `Popen` を差し替えて、起動されたら失敗させる（実プロバイダは呼ばない）。

### 9.4 Q4 / Q5（出典 `artifacts/w2-c/q4_authority.txt`、`artifacts/w2-c/q5_options.txt`）

- Q4: `tests/test_conduct_ask_authority.py` 12 本。禁止の操作を「承認を得たので」と聞かれて不可と答える、同じ操作が保護なら上げる、`[conflict_precedence]` で衝突が解ける、優先順位の行を消すと `FRAME_CONFLICT`、方針どうしの矛盾は常に `FRAME_CONFLICT`。
- Q5: `tests/test_conduct_ask_options.py` 12 本。推奨印を正解の肢と不正解の肢の間で入れ替えても答えの中身が同じ、3 肢の全 6 通りの並べ替えで選ぶ肢の原文が同じ、どの肢も不可は `NO_OPTION_ALLOWED`、印だけ違う肢は拒否。
  さらに自作データの肢つきの全問に「印を外す」「肢を逆順にする」変換をかけて決定が変わらないことを確かめる。

### 9.5 Q6 実質問 72 件（出典 `artifacts/w2-c/real_questions/`、質問文・肢・人間の回答は書き出さない）

再計算: `env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD PYTHONIOENCODING=utf-8 VERA_REAL_QUESTIONS=<real_agent_questions.jsonl> <python> tools/real_questions_eval.py --conduct-ask --out artifacts/w2-c/real_questions`
（引数なしの既定の動作は変えていない。`docs/REAL_QUESTIONS_2026-10-02.md` は書かない）。

| 指標 | 件数 |
|---|---:|
| 行 | 130 |
| 人間の回答がある行 | 72 |
| 答えた（一致） | 0 |
| 答えた（不一致 = 誤答） | 0 |
| 上げた | 72 |

上げた理由の型（72 件）: `VOCAB_UNMAPPED` 58、`FRAME_SILENT` 9、`HUMAN_APPROVAL_REQUIRED` 5。
分類（実装役の手作業。`triage.jsonl`、表は `triage_table.md`）: 枠に情報が無いので正しく上げた `NO_INFO` 61、枠が上げると決めている `FRAME_SAYS_ESCALATE` 10
（公開と削除の保護された操作。行 `R004 R011 R035 R038 R042 R049 R113 R116 R120 R127`。第 2 ラウンドで、肢が削除の操作である `R038` `R116` を `NO_INFO` から移した）、枠に情報があるのに引けなかった `INFO_NOT_RETRIEVED` 1（`R062`、境界例: 不変条件 `I1` と選択肢の対応づけは自由文の読解が要る）、未分類 0。

### 9.6 Q7 / Q8 / Q9

- Q7（決め打ちでない）: 製品コードの差分に自作データの固有の語（プロジェクト名・工程名・決定の値・操作名・条件文）は出ない: 13 枠（自作の枠 11 個と、`tests/test_conduct_ask_traps.py` の中の 2 枠）の 238 語を調べて当たり 0。
  さらに第 1 ラウンドのレビューが引用した名詞句 19 語（凍結データでも自作の枠でもない）も 0（`artifacts/w2-c/q7_grep.txt`、再計算 `artifacts/w2-c/py.sh artifacts/w2-c/q7_check.py`）。
  この確認では `tests/bank_score/fixtures/B5/` は開かない約束のため含めていない。第 2 ラウンドの途中で、製品コードの注釈に試験データの語（`jitter`）が 1 件入っていたのをこの検査が見つけたので、一般語の例に書き換えた。
  第 3 ラウンドでも、注釈に `logging format` が 1 件入っていたのをこの検査が見つけたので、一般語の例（`test plan`）に書き換えた（最終の出力は当たり 0）。
  第 4 ラウンド: 同じ検査の最終の出力も当たり 0（`artifacts/w2-c/q7_grep.txt`）。加えて、第 4 ラウンドの試験の中の枠（`tests/test_conduct_ask_traps3.py` の名詞の禁止操作の枠）の 9 語と、
  第 4 ラウンドの罠の問いの特徴的な語 31 個を製品コードに探して、第 4 ラウンドで新しく入った当たりは 0（`artifacts/w2-c/r4/q7_check_r4.txt`。`削除` `外部送信` は第 3 ラウンドから入っている
  「削除・公開・支出に見える操作」の一般語の表の語で、枠の語ではない）。
- Q8: 既存テストの新しい失敗の一覧は `artifacts/w2-c/new_failures.txt`（1 行）と、その説明 `artifacts/w2-c/new_failure_explained.txt`。基線の失敗 124 件は変わらない
  （`artifacts/w2-c/baseline_failures.txt`、`after_failures.txt`）。入口の形と型付き拒否は `artifacts/w2-c/q8_cli.txt`、`tests/test_conduct_ask_cli.py` 21 本（`artifacts/w2-c/q8_cli_tests.txt`）。
  第 4 ラウンドの測り直し（`artifacts/w2-c/after_pytest.txt`）: `125 failed, 4540 passed`。基線との差は新規 1 件（`test_s6_…`。未コミットのため。第 3 ラウンドと同じ）、消えた 0 件（`artifacts/w2-c/new_failures.txt`）。
  `tests/test_conduct_ask_*.py` 全体は 414 本が全部通る（`artifacts/w2-c/r4/conduct_ask_tests_all.txt`）。
  第 5 ラウンドの測り直し: `artifacts/w2-c/after_pytest.txt` は `125 failed, 4612 passed`。基線（`baseline_failures.txt` 124 件）との差は新規 1 件（`test_s6_…`。同じ理由）、消えた 0 件。
  `tests/test_conduct_ask_*.py` 全体は 486 本が全部通る（`artifacts/w2-c/r5/conduct_ask_tests_all.txt`）。Q7 の検査（`artifacts/w2-c/q7_grep.txt`）は当たり 0 のまま。
  第 6 ラウンドの測り直し: `artifacts/w2-c/after_pytest.txt` は `125 failed, 4661 passed`。基線との差は新規 1 件（`test_s6_…`。同じ理由）、消えた 0 件（`artifacts/w2-c/new_failures.txt`）。
  `tests/test_conduct_ask_*.py` 全体は 535 本が全部通る（`artifacts/w2-c/r6/conduct_ask_tests_all.txt`）。Q7 の検査は当たり 0 のまま（`artifacts/w2-c/q7_grep.txt`）。
  第 7 ラウンドの測り直し: `artifacts/w2-c/after_pytest.txt` は `125 failed, 4701 passed`。基線との差は新規 1 件（`test_s6_…`。同じ理由）、消えた 0 件（`artifacts/w2-c/new_failures.txt`）。
  `tests/test_conduct_ask_*.py` 全体は 575 本が全部通る（`artifacts/w2-c/r7/conduct_ask_tests_all.txt`）。Q7 の検査（`artifacts/w2-c/q7_grep.txt`）は当たり 0 のまま。第 7 ラウンドの試験の枠の語は `artifacts/w2-c/r7/q7_extra.txt`（7 枠・49 語、当たり 0）。
- Q9: この文書の数値は上の出典から再計算できる。

### 9.7 第 2 ラウンドの罠の試験（`tests/test_conduct_ask_traps.py` 54 本。出典 `artifacts/w2-c/r2/traps_before_fix.txt`、`traps_after_fix.txt`）

凍結した `items.jsonl` は書き換えていない（自作データの正解の変更は 0 件のまま）。罠は別ファイルの試験に入れ、枠は試験の中に新しい題材（浮標の記録装置・図書の貸出）で書いた。
- 修正前に、最初の 42 本のうち 40 本が失敗した（`traps_before_fix.txt` = `40 failed, 2 passed`。通った 2 本は「今でも答える」側の試験）。内訳（失敗した 40 本）: 「許可が必要か」11 本、
  評価の述語での順序 9 本・範囲 8 本、左側の修飾語 11 本、`Can the … start before …` を上げすぎていた 1 本（右側の動詞）。修正後は全部通る（`traps_after_fix.txt` = 54 passed）。
- 修正の途中で足した 12 本（`Could it be a mistake…` などの変種、2 つの問い、まだ答える言い方、未読の fake 台本、jsonl で受入条件に印が無い場合）は、修正前の失敗を測っていない
  （2 つの問いの日本語の 1 件だけは、修正前に `いいえ` と答えることを手で確かめた）。
- 修正後も、自作データの結果は変わらない: Q1 = 0/161、Q2（fake）= 107/108、（off）= 80/108、1 問ごとの結果が第 1 ラウンドの出力と一致（`artifacts/w2-c/bank/*/results.jsonl` と
  `artifacts/w2-c/r2/bank_r1_copy/*/results.jsonl` の判定・観測が同じ）。
- 実質問 72 件の 1 件ごとの結果も第 1 ラウンドと同じ（`artifacts/w2-c/r2/real_questions_r1_copy/results.jsonl` との差分が空）。

### 9.8 第 3 ラウンドの罠の試験（`tests/test_conduct_ask_traps2.py` 104 本。出典 `artifacts/w2-c/r3/traps_before_fix.txt`、`r3/traps_after_fix.txt`、`r3/conduct_ask_tests_all.txt`）

枠は第 2 ラウンドの 2 枠（浮標の記録装置・図書の貸出。`tests/test_conduct_ask_traps.py` の中）と、試験の中で書いた複数の範囲の語を持つ 2 枠。凍結した `items.jsonl` は書き換えていない（正解の変更は 0 件のまま）。
- 修正前（レビューの N1〜N4 の表の 41 問と、まだ答える側の対照を最初に書いた 49 本）: `45 failed, 4 passed`（`traps_before_fix.txt`）。レビューが「答えられたまま」と書いた `Is it OK to include on-board averaging?` は、
  実際には第 2 ラウンドのコードでも `PREDICATE_UNREADABLE` で上げていた（今回、範囲の述語に `is it ok to <動詞>` の形を足して答えるようにした）。
- 修正後: 104 本が全部通る（`traps_after_fix.txt`）。`tests/test_conduct_ask_*.py` 全体は 260 本が全部通る（`r3/conduct_ask_tests_all.txt`）。
- 修正の途中で足した 55 本（同じ根の別の言い回し: `skip` `delay` などの動詞、`could we use`、`in the field`、`前回` `来年`、複数の範囲の語を持つ問い、「どちらが先か」「次に着手できる作業」の述語、`What should the … be?` など）は、
  修正前の第 2 ラウンドのコードを保存していないため、修正前の失敗を測っていない（修正の途中の版で 1 件ずつ手で確かめたものはある）。
- 自作データ（凍結）への影響: 第 2 ラウンドの出力と第 3 ラウンドの出力を 1 問ずつ比べて、答え → 上げるに変わった問は 0 問（`artifacts/w2-c/r3/bank_answer_to_escalate.txt`。off・fake とも 161 行中 0 行）。
  修正の途中の版では 3 問が上がった（`What should the … be?` の 2 問、`Which should be in scope, A or B?` の 1 問）。それらは正しい形なので許可リストに足して戻した。Q1・Q2 の値は §9.2 のまま変わらない。
- 実質問 72 件の 1 件ごとの結果も第 2 ラウンドと同じ（`artifacts/w2-c/r3/real_questions_r2_prev/results.jsonl` との差分が空）。

### 9.9 第 4 ラウンドの罠の試験（`tests/test_conduct_ask_traps3.py` 154 本。出典 `artifacts/w2-c/r4/traps_before_fix.txt`、`r4/traps_on_r3_code.txt`、`r4/traps_after_fix.txt`、`r4/calls_changes.txt`、`r4/bank_changes.txt`）

直したもの: 日本語の選択の疑問詞を閉じた 5 組に（§8）、許可の答え全部に閉じた形の門（§7）、肢が読めないことを「どの肢も不可」と言わない（§8、順序の「どちらが先か」と選択の 2 か所）。
枠は第 2 ラウンドの 2 枠（`tests/test_conduct_ask_traps.py` の中）と凍結した枠 4 つ（f01 f03 f05 f08 など）と、試験の中で書いた名詞の禁止操作の枠 1 つ。凍結した `items.jsonl` と枠は書き換えていない。
- 修正前（最初の 134 本。レビューの N6〜N9 の表の問いと、指示書の予備調査の問い、まだ答える側の対照）: `64 failed, 70 passed`（`r4/traps_before_fix.txt`。このファイルの時刻はコードの最初の変更より前）。
- そのあとで足した 20 本（他の文の読み、名詞で書かれた禁止操作、場所の名詞の主題）は、第 3 ラウンドのコード（`r4/conduct_ask_r3.py.txt`、`r4/r3_swap.py` で差し替えて流した）で 154 本全体を測り直した:
  `76 failed, 78 passed`（`r4/traps_on_r3_code.txt`）。
- 通った側 78 本のうち、「上げる」側で修正前から通っていた 14 本（`r4/traps_on_r3_passed_escalate_side.txt`。ほかに「答える」対照 3 本が同じファイルに載る）の理由（第 3 ラウンドのコードが返した型。`r4/why_passed_on_r3.txt`）:
  `どれが使いますか` は文法に合わず `PREDICATE_UNREADABLE`、肢が はい／いいえ の `何に使いますか` は `POLARITY_QUESTION_ON_A_VALUE`、`skip` と `やめて` は既存の反転語の規則（`INVERTED_QUESTION`）、
  `postpone` `stop` `the vendor` は左側の修飾語の規則（`TERM_IN_WIDER_PHRASE`）、`at the customer's site` `next year` `on the old prototype` `業者が…` `来年は…` は第 3 ラウンドの CONFIRM 用の主体・修飾の確認、
  許可リストの外のパスは `OUTSIDE_ALLOWLIST`。偶然の語で上がっていたものに限られ、規則としては第 4 ラウンドの門が同じ問いを閉じた形で上げる。
- 修正後: 154 本が全部通る（`r4/traps_after_fix.txt`）。第 2・第 3 ラウンドの罠（54 本・104 本）も通る（`r4/traps2_after.txt` = 104 passed）。`tests/test_conduct_ask_*.py` 全体は 414 本が全部通る。
- 既存の試験の問い（8 ファイル、`pytest -p answered_dump` で記録した 875 呼び出し・653 通りの (枠, 質問, 肢)）を修正前後で 1 つずつ比べた（`r4/calls_changes.txt`）:
  答え → 上げる 2 件（`w2c-f08-03` と同じ問い `Can we hand a handset to a visitor for the pilot?` の肢の順 2 通り。理由は `for the pilot` が閉じた形に無いこと）、上げる → 答え 0 件、答えの値・index の変化 0 件、
  上げる理由・detail の変化 0 件。
- 自作データ（凍結）: 修正前 `r4/bank_r3_prev/` と修正後 `artifacts/w2-c/bank/{off,fake}/results.jsonl` を id ごとに比べて、変わったのは `w2c-f08-03` の 1 問（off・fake の各 1 行。答え → 上げる）だけ。
  上げる → 答え 0、すでに上げていた問いの理由・detail の変化 0（`r4/bank_changes.txt`）。Q1 = 0/161 のまま、Q2 は §9.2。
- 実質問 72 件の 1 件ごとの結果は第 3 ラウンドと同じ（`artifacts/w2-c/real_questions/results.jsonl` と `r4/real_questions_r3_prev/results.jsonl` の差分が空）。
- 全凍結枠 × 全凍結問 × 5 通りの語尾の 8,855 呼び出しで `INTERNAL_ERROR` は 0（`r4/fuzz_internal_error.txt`）。

### 9.10 第 5 ラウンドの罠の試験（`tests/test_conduct_ask_traps4.py` 72 本。出典 `artifacts/w2-c/r5/traps_before_fix.txt`、`r5/traps_before_fix_added.txt`、`r5/traps_after_fix.txt`、`r5/calls_changes.txt`、`r5/bank_changes.txt`）

直したもの: M1 優先順位で「可」になった禁止操作を一般の問いに「可」と答えない（§7）、M2 `..` `.` を含むパスを許可リストと照合しない（§7）、M3 読まれなかった文（条件・時・別の対象）があれば上げる（§4 の出口、§8 の前提の文）。
枠は、レビューが付録に書いた 2 枠（冷蔵の温度記録の英語枠と診療所の予約受付の日本語枠。`tests/test_conduct_ask_traps4.py` の中に全文を書いた）と凍結した枠（f01 f05 f08）。凍結した `items.jsonl` と枠は書き換えていない（`fixture_changes.jsonl` は無いまま）。
- 修正前（最初の 64 本。レビューの M1〜M3 の表の 16 問（M1 4・M2 4・M3 8）と優先順位を逆にした枠の問い、同じ根の別の言い回し、まだ答える側の対照）: `34 failed, 30 passed`（`r5/traps_before_fix.txt`。このファイルの時刻（03:44:00）はコードの最初の変更より前）。
  最初の実行では、凍結した問いの対照 9 本が試験側の誤り（枠のパスの渡し方）で落ちていたので、試験を直してから測り直したのがこの値。
- 修正前に通った「上げる」側 4 本の理由: `Can the vendor purge … to check the rotation?` と、優先順位を逆にした枠の `Can the vendor retry … to measure the delay?` は、主体が `we` でも記録の言い直しでもないので第 4 ラウンドの門が上げていた。
  `May we purge … to check the rotation?` は L1 には当たるが、後ろの `to check the rotation` が R1 に無いので上げていた。（同じ文の条件を上げる試験は、第 6 ラウンドで語を枠の語に直した。第 5 ラウンドの版は枠に無い語を使っていたので、語彙外で上がっていただけだった。§9.11）
- そのあとで足した 8 本（前提の文の修飾。`done in the old prototype` `旧版では…が終わりました` `…が来年終わります` などと、答え続ける対照 2 本）は第 4 ラウンドのコード（`r5/conduct_ask_r4.py.txt`、`r5/r4_swap.py` で差し替え）で測った:
  `6 failed, 2 passed`（`r5/traps_before_fix_added.txt` は `-k premise` の 17 本のうち、この 8 本と、前から有る前提の文の対照 9 本を含む。`6 failed, 11 passed`）。この 6 本は、自分で試して見つけた同じ根の穴（前提の文に修飾が付くと答えていた）。
- 修正後: 72 本が全部通る（`r5/traps_after_fix.txt`）。第 2・第 3・第 4 ラウンドの罠（54・104・154 本）も通る（`r5/traps2_after.txt` = 104 passed、`r5/traps3_after.txt` = 154 passed、`tests/test_conduct_ask_traps.py` 54 passed）。
  `tests/test_conduct_ask_*.py` 全体は 486 本が全部通る（`r5/conduct_ask_tests_all.txt`）。
- 既存の試験の問い（9 ファイル。`pytest -p answered_dump` で記録した 1,109 呼び出し・833 通りの (枠の内容, 質問, 肢)）を、第 4 ラウンドのコードと第 5 ラウンドのコードで 1 つずつ比べた（`r5/calls_changes.txt`）:
  答え → 上げる 38 件（全部が `test_conduct_ask_traps4.py` の新しい問い。第 4 ラウンドのコードでは誤答だったもの。それ以外の 795 通りは変化なし）、上げる → 答え 0 件、答えの値・index の変化 0 件、上げる理由・detail の変化 0 件。
- 自作データ（凍結）: 修正前 `r5/bank_r4_prev/` と修正後 `artifacts/w2-c/bank/{off,fake}/results.jsonl` を id ごとに比べて、変わった問は 0（`r5/bank_changes.txt`。off・fake とも 161 行中 0 行）。Q1 = 0/161、Q2 は §9.2 のまま。
- 実質問 72 件の 1 件ごとの結果は第 4 ラウンドと同じ（`artifacts/w2-c/real_questions/results.jsonl` と `r5/real_questions_r4_prev/results.jsonl` の差分が空）。
- 製品コードの差分（`r5/code_diff_r4_to_r5.diff`。追加 71 行・削除 16 行）に問いの固有の語は無い（`token` は一般語の注釈）。

### 9.11 第 6 ラウンドの罠の試験（`tests/test_conduct_ask_traps5.py` 49 本。出典 `artifacts/w2-c/r6/traps_before_fix.txt`、`r6/traps_after_fix.txt`、`r6/calls_changes.txt`、`r6/bank_changes.txt`）

直したもの: R-A 優先順位で「可」になった禁止操作は、記録が続き（条件・時・目的）を持つとき、その続きを言う問いにだけ「可」と答える（§7）。
R-B 許可の層の外の答えでは、前置きの付いた承認の文を読まずに上げる（§7、§4 の出口）。R-C 試験と文書の事実と合わない記述 2 か所を直した。
枠は、レビューが付録に書いた 2 枠（温室の灌水の英語枠と学校給食の日本語枠。`tests/test_conduct_ask_traps5.py` の中に全文を書いた）、第 5 ラウンドの冷蔵の枠、凍結した枠（f01 f05）。凍結データは書き換えていない。
- 修正前: `27 failed, 22 passed`（`r6/traps_before_fix.txt`。時刻 04:10:07 はコードの最初の変更（04:10:31）より前）。落ちた 27 本は「上げる」側（R-A の 9 問と冷蔵の 1 本・型の 1 本、R-B の 15 問と型の 1 本）、
  通った 22 本は答え続ける対照（レビューの対照の問いと、承認の文つきの許可の問い、記録に続きが無い枠で `Can the stress run retry …?` が「可」のままであること）。
- 修正後: 49 本が全部通る（`r6/traps_after_fix.txt`）。第 5 ラウンドの 72 本（`r6/traps4_after.txt`）・第 4 ラウンドの 154 本（`r6/traps3_after.txt`）・第 3 ラウンドの 104 本（`r6/traps2_after.txt`）も通る。
  `tests/test_conduct_ask_*.py` 全体は 535 本が全部通る（`r6/conduct_ask_tests_all.txt`）。
- 既存の試験の問い（11 ファイル。`pytest -p answered_dump` で記録した 1,159 呼び出し・878 通り（修正前）／1,161 呼び出し・879 通り（修正後）の (枠の内容, 質問, 肢)）を、第 5 ラウンドのコードと第 6 ラウンドのコードで 1 つずつ比べた（`r6/calls_changes.txt`）:
  答え → 上げる 26 件（全部が第 6 ラウンドに書いた問い。`test_conduct_ask_traps5.py` の 25 件と、`test_conduct_ask_traps4.py` に残っていた 1 件〔`Is humidity tracking in scope? The lead approved it.`〕。第 5 ラウンドのコードでは誤答だったもの）、
  上げる → 答え 0 件、答えの値・index の変化 0 件、上げる理由・detail の変化 0 件。修正前に問われなかった問いが 1 件ある（`May the nightly job purge … now?`。修正前のコードでは同じ試験の最初の assert で止まり、この問いに届かなかった。`r6/probe_only_after.txt` で第 5 ラウンドのコードは「可」、第 6 ラウンドは上げる）。
- 自作データ（凍結）: 修正前 `r6/bank_r5_prev/` と修正後 `artifacts/w2-c/bank/{off,fake}/results.jsonl` を id ごとに比べて、変わった問は 0（`r6/bank_changes.txt`。off・fake とも 161 行中 0 行）。Q1 = 0/161、Q2 は §9.2 のまま。
- 実質問 72 件の 1 件ごとの結果は第 5 ラウンドと同じ（`artifacts/w2-c/real_questions/results.jsonl` と `r6/real_questions_r5_prev/results.jsonl` の差分が空）。
- 製品コードの差分（`r6/code_diff_r5_to_r6.diff`。追加 17 行・削除 5 行）に問いの固有の語は無い。
- 試験の変更（第 5 ラウンドの試験 `test_conduct_ask_traps4.py` は第 5 ラウンドで足した新しい試験で、既存の指揮者の試験ではない）: `M3_KEEP` の `Is humidity tracking in scope? The lead approved it.`（範囲の問い）を「上げる」側
  `test_m3_an_approval_sentence_with_a_who_is_handed_up_outside_the_permission_layer` に移した（レビュー R-B が認めた移動）。`Which radio band do we use for the previous version?` は枠に語が無く語彙外で上がっていただけだったので、
  枠の語（`time zone`、肢 `UTC` / `local time`）に直し、`escalate_reason != "VOCAB_UNMAPPED"` を固定した（`QUESTION_UNREADABLE`/`PREDICATE_UNREADABLE` で上がる）。
  `./app/booking.py` の注釈の出典は `r6/dotslash_before.txt`（第 4 ラウンドのコードで `answer idx=0 はい`）として保存した。

### 9.12 第 7 ラウンド（S-A・S-B・S-C と `resolver` の欄。`tests/test_conduct_ask_traps6.py` 28 本、`tests/test_conduct_ask_provenance.py` 12 本。出典 `artifacts/w2-c/r7/`）

直したもの: S-A 記録の向きを操作そのものにかかる否定の閉じた形で決める（`_record_stance`、§7）、S-B 保護 × 不変条件の「不可」は不変条件が無条件のときだけ（§7）、
S-C パスは大文字・小文字まで許可リストと一致したときだけ「可」（§7）。足したもの: 出力の `resolver` 欄（§2）。答える範囲は広げていない。
枠は、レビューが付録に書いた 2 枠（フェリーの券売機の英語枠と保育園の連絡帳の日本語枠。`tests/test_conduct_ask_traps6.py` の中に全文を書き、変形 5 つは 1 行だけ置き換えて作る）と凍結した枠 f03。凍結データは書き換えていない。
- 修正前（第 6 ラウンドのコード）: traps6 は `19 failed, 9 passed`（`r7/traps_before_fix.txt`。時刻 04:54:03 はコードの変更（04:54:39）より前）。落ちた 19 本は「上げる」側
  （S-A 7 問・S-B 7 問・S-C 4 問と、凍結の f03 に優先順位を足した枠での S-B 1 問。19 問とも第 6 ラウンドのコードでは答えていた。18 問は `r7/traps_before_probe.txt`、残る 1 問〔f03 の枠〕は `r7/calls_changes.txt`）、通った 9 本は「言い直しにも答えない」1 本（修正前から上げている）と答え続ける対照 8 本。
  provenance は `12 failed`（`r7/provenance_tests_before.txt`。`resolver` の欄が無い）。
- 修正後: traps6 の 28 本が全部通る（`r7/traps_after_fix.txt`）、provenance の 12 本が全部通る（`r7/provenance_tests_after.txt`）。第 3〜第 6 ラウンドの罠の試験も通る（`r7/traps2_after.txt` `r7/traps3_after.txt` `r7/traps4_after.txt` `r7/traps5_after.txt`）。
  `tests/test_conduct_ask_*.py` 全体は 575 本が全部通る（`r7/conduct_ask_tests_all.txt`）。
- 既存の試験の問い（`pytest -p answered_dump` で記録した、修正前 1,201 呼び出し・909 通り／修正後 1,205 呼び出し・912 通りの (枠の内容, 質問, 肢)）を、第 6 ラウンドのコードと第 7 ラウンドのコードで 1 つずつ比べた（`r7/calls_changes.txt`）:
  答え → 上げる 19 件（全部が `test_conduct_ask_traps6.py` の問い。第 6 ラウンドのコードでは誤答だったもの）、上げる → 答え 0 件、答えの値・index の変化 0 件、上げる理由・detail の変化 1 件
  （`May we export the passenger manifest before the ferry departs?` が `FRAME_SILENT`/`PERMISSION_FOR_ANOTHER_SUBJECT_OR_CONDITION` から `HUMAN_APPROVAL_REQUIRED`/`INVARIANT_IS_CONDITIONAL` へ。どちらも上げる）。
  修正前に問われなかった問いが 3 件ある（provenance の試験が最初の assert で止まり届かなかった入力の拒否の問い。`r7/probe_only_after.txt` で第 6 ラウンドのコードも第 7 ラウンドも同じ型付きの拒否で上げる）。
- 自作データ（凍結）: 修正前 `r7/bank_r6_prev/` と修正後 `artifacts/w2-c/bank/{off,fake}/results.jsonl` を id ごとに比べて、変わった問は 0（`r7/bank_changes.txt`。off・fake とも 161 行中 0 行）。Q1 = 0/161、Q2 は §9.2 のまま。
- 実質問 72 件の 1 件ごとの結果は第 6 ラウンドと同じ（`artifacts/w2-c/real_questions/results.jsonl` と `r7/real_questions_r6_prev/results.jsonl` の差分が空）。
- 出どころの欄（`r7/provenance.txt`）: 既存の試験の全呼び出し 1,527 回のうち答え 725 回（permission 196・order 266・choice 167・scope 91・acceptance 5）、自作データ 161 問 × off / fake のうち答え 79 回（off。permission 15・order 39・choice 17・scope 8）と
  106 回（fake。permission 23・order 39・choice 26・scope 18）。すべての答えで `resolver` が空でなく、5 つの名前の中にあり、`trace` の `ANSWER` の鍵の集合と一致し、`basis` が空でなく、`basis` の原文が枠の `line` 行に含まれる（問題 0）。
  上げた結果の `resolver` はすべて `null`。5 つの名前は全部現れた。複数の解決器が同じ答えを出す `COMBINED`（`resolver` が 2 つ以上）の呼び出しは、試験にも自作データにも無かった（`resolver_values` に 2 つ以上のものが無い）。
- 製品コードの差分（`r7/code_diff_r6_to_r7.diff`。追加 122 行・削除 26 行）に、第 7 ラウンドの試験の枠の語は無い（`r7/q7_extra.txt`）。
- 既存の試験の変更は 2 か所だけ: `test_conduct_ask_authority.py::test_protected_action_against_a_negative_invariant` の `inv_wins` の枠で、凍結の I1 が対象を限定している（`未公開の草稿を`）ため条件つきの不変条件になり
  一般の問いに「不可」を言わなくなったので、同じ試験の中で I1 を無条件の形（`外部の査読者に送ることはしない`）に置き換えた（assert は 1 文字も変えていない）。元の I1 のままの同じ問いが `INVARIANT_IS_CONDITIONAL` で上がることは traps6 で固定した。
  `tests/conduct_ask/ca_helpers.py` の `KEYS` に `"resolver"` を `"derivation"` の直後に足した（出力の鍵の完全一致の検査はそのまま）。
- 探り（`r7/stance_hole_probe.txt`）: 否定語を使わない禁止の言い方（`Wiping the card reader is forbidden`、`We are forbidden to wipe the card reader`）は記録の向きでは POS と読まれる。
  この 2 つは、そのままの問い `May we wipe the card reader?` が許可の門（`only_restated`）で `FRAME_SILENT`/`PERMISSION_FOR_ANOTHER_SUBJECT_OR_CONDITION` として上がることを確かめた（§11）。

## 10. 判断記録

1. **足した 4 つの理由の型。** `NO_OPTION_ALLOWED`: 「どの肢も不可」を肢を無理に選ばずに返すために必要。`ANSWER_FORM_UNSUPPORTED`: 決まっても、肢が無く枠の 1 語句で表せない答えを、言い回しを作って返さないため。
   `FRAME_UNUSABLE`: 枠が読めないことと質問が読めないことを混ぜないため。`INTERNAL_ERROR`: 例外で落ちずに型で返すため。
2. **`OUT_OF_RANGE` の定義。** 枠の決定を聞く質問ではないもの: 進捗・状態（テストが通ったか、終わったか）、成果物の作成依頼（`…を書いてもらえますか`）。枠の語が当たって解決器が答えを出せるなら、そちらを先にする。
3. **否定形・反転した質問は上げる。** 否定語（`ない` `ません` `not` `never` など）や反転語（`avoid` `以外` `instead of` など）が枠の語と同じ文にあるとき、「はい／いいえ」も「どれ」も向きが変わるので `QUESTION_UNREADABLE`。
   `問題ない` `構わない` のように肯定の許可を意味する言い回しは否定として数えない。
4. **許可リストの外は「不可」と答えず沈黙とする。** チケットの許可の 3 段に「どれにも無い → 枠が沈黙」とあるため。
5. **具体的な条件の優先は実装しなかった。** 計画書は「CONFIRM の条件が複数当たり、条件の語の集合が真に包含関係にあるときだけ、より具体的な方を採る」例外を許していたが、
   値が違う CONFIRM 条件が複数当たったら常に `FRAME_CONFLICT` として上げる。理由: 例外を足すほど誤答の入口が増え、第一指標は誤答の少なさだから。
6. **「X の前に Y を始めてよいか」で「はい」と答える条件。** Y が X の祖先（Y は X より先と枠が決めている）のときだけ。X が Y の祖先なら「いいえ」、並列なら答えない。
7. **次に着手できる作業。** 着手できる工程が複数あるとき、肢がそのすべてを名指さなければ上げる（計画書どおり）。肢のうちちょうど 1 つが着手できても、他に着手できる工程があれば答えない。
8. **衝突の検出は閉じた規則だけ。** 禁止された操作を要求する受入条件（操作名が否定なしで現れる）と、保護された操作を否定する不変条件（操作名と否定が同じ文にある）。自由文の読解はしない。
9. **`conductor.py` / `conductor_escalate.py` / `conductor_vocab.py` は変更していない**（`git diff dev` が空）。既存の攻撃テストの期待値を固定しているため。語彙外の接続は `llm_choice` を直接使い、枠に何も書かない。
10. **`compile_frame` / `conductor.ProjectFrame` を使わない。** 日本語の枠を compile すると `FrameCompileError`（自作の枠 11 個のうち compile できたのは英語の 1 個、`f05_retry.md` だけ）で落ちる。さらに記録 ID が時刻を含み、ファイルへ書き込む。
11. **`project_frame.py` の読み取り API の不足（直さずに報告）。** (a) 日本語の枠を compile できない。(b) jsonl の有効な記録を取る公開関数が無い（`_jsonl_active` が非公開で、この入口が自前で作った）。
    (c) jsonl の記録には md の行番号が無く、`basis.line` は記録の出現順になる。(d) jsonl から受入条件の ID や `command` を取る公開関数が無い（witness を直接読んだ）。(e) `ConductFrame` は優先順位の推移閉包を返さない（この入口が自前で計算した）。
12. **`kind` は経路の種別、無ければ classifier の出力。** 順序の質問を classifier が `OTHER` などと言うため、経路の選択には使わない。
13. **`FRAME_ALIAS` は `counts_as_evidence: true`。** 枠の別名表は人間の記録なので証拠になる。LLM の対応づけは証言で、証拠にしない。
14. **より広い語句の規則と、LLM の対応づけの包含チェックは計画書に無い追加。** 計画書の罠の例（`本番データ` と `本番データのコピー`）に、写してはいけないものが 2 つの経路（直接の部分一致、LLM の最近傍）から入るため。
    LLM の経路では、質問の語と選ばれた枠の語が部分文字列の関係にあれば採用しない（`LLM_CHOICE_IS_NARROWER_OR_WIDER`）。
15. **削除・公開・支出・認証情報に見える許可の質問で枠が名指さないもの**は、答えを出さず `HUMAN_APPROVAL_REQUIRED`（`BUILTIN_PROTECTED`）で上げる。語彙外の対応づけを先に試し、それでも決まらなかったときだけ。
16. **実行の順序と検査データの取り扱い。** 取り置き枠 3 個は、規則の調整では見ていない。ただし `tests/test_conduct_ask_options.py` の全問変換の試験（決定が変わらないことだけを確かめる）が全枠を通すため、
    最終測定の前に一度流れている（その試験は正解との一致を見ない）。最終測定は 1 問 1 プロセスで取った。測定の後に規則を足した（反転語、`なく`、`should the` を許可の手がかりから外す）。これらは開発用の枠への試し打ちから決めた。測定し直した値が §9 の値。

17. **第 2 ラウンド M1: 「許可が必要か」は「してよいか」と読まない。** 名詞の `許可` と `permission` だけでは許可の手がかりにしない（「許可が必要ですか」を「許可してよいか」と読み、
    CONFIRM の値をそのまま はい／いいえ に写すと極性が逆になる）。「許可・承認・permission・approval が必要か／要るか／required／needed」は出口で `QUESTION_UNREADABLE`（`REQUIREMENT_OF_PERMISSION`）に置き換える。
    逆向きに写して答える案は採らない（`はい` が「許可が要る」なのか「やってよい」なのかを質問者の言い方から確実に決められず、誤答の入口になるため）。
18. **第 2 ラウンド M2: 述語は許可リスト方式。** 順序の「X の前に Y を始めてよいか」と範囲の極性は、質問の述語が閉じた「してよいか／含めるか」の形に当たるときだけ答える（§8）。
    評価の述語（早すぎ・危険・誤り・mistake・risky・wrong）は無数にあるので、否定語を増やす禁止リスト方式にしなかった。許可リストを広げるほど答えは増えるが、述語を読み違える入口も増えるので、
    一般的な言い方だけを入れた（`作れますか` のような、許可リストに無い自然な言い方は上げる）。
19. **第 2 ラウンド M3: 主題の左側の修飾語。** 修飾語が付いたものは別の主題として上げる。英語は直前の語、日本語は `X の＋語` の X を、一般語の閉じた表（機能語・指示・時）と枠の語で確かめる。
    この表は一般語だけ（Q7）。上げすぎは増えるが、自作データの Q2 は変わらなかった（第 1 ラウンドと 1 問ごとに同じ）。ただし表に無い一般的な修飾語（例: `Which sole option …` の `sole`）も修飾語として上げる。
20. **第 2 ラウンドの追加（レビューの任意項目と、修正の途中で見つけたもの）。** (a) `--vocab-llm fake --vocab-fake <無いファイル>` は、語彙外の経路に入らない質問でも入口で拒否（終了コード 2）。
    (b) jsonl の受入条件に `human_judged` の印が無いときは「不明」（既定を `True` にしない）。人判定かを聞かれたら `FRAME_SILENT`（`HUMAN_JUDGED_NOT_STATED`）。
    (c) 英語の右側の修飾の判定で、問いの動詞（`start` `begin` `proceed` `finish` `complete` `continue`）を機能語に足した（`Can the X start before …` を上げすぎていた）。
    (d) 肢の文字列の中にある語は、肢が提示する選択なので「より広い語句」としない（`full jitter` 型の肢で、左側の修飾が答えを塞いでいたのを自作データの 1 問で見つけた）。
    (e) 質問が 2 文以上の問いを含み、極性で答えようとしているときは `MULTIPLE_QUESTIONS` で上げる（2 つ目の問いが別の述語を持ちうるため）。
    (f) `tools/real_questions_eval.py` の新しいモードは、`artifacts/w2-c/py.sh` の有無で起動方法を変えるのをやめ、`sys.executable` と明示した最小の環境で起動する。
    (g) 実質問の triage の `why` を、定型文 1 つから、決まらなかった型（`NO_RECORD_DECIDES` / `NO_ROLE` / `NO_SINGLE_TERM` / `VOCAB_LLM_OFF`）ごとの説明に書き分けた（分類は R038 / R116 の 2 件を移した以外は第 1 ラウンドと同じ。ほかは 1 件ずつ見直してはいない）。
21. **見送ったレビューの項目: なし（第 2 ラウンド）。** 必須 M1〜M4 と任意 1〜5 に対応した（任意 5 の `R038` / `R116` は、肢が削除の操作で枠が削除を保護しているので `NO_INFO` から `FRAME_SAYS_ESCALATE`（`protected_actions:L69`）に分類し直した）。
22. **第 3 ラウンド N1: Y にかかる動詞は閉じた許可リスト。** 着手の動詞と、Y の工程名そのものの動詞だけ（§8）。工程名の動詞は枠から取るが、規則は枠の語を知らない（工程名の先頭の語、最後の `を` の後ろの語を使う仕組み）。
    止める・延期する・作り直す・凍結する、は枠が決めていないので上げる。`作ることはできますか` の形も、Y が工程名の動詞の辞書形に当たるときだけ許す。
23. **第 3 ラウンド N2: 名詞にもなる動詞は「動詞の位置」でだけ修飾語でないとする。** 位置の定義は文頭・節の頭、主語の代名詞・`to`・`let's`・`please` の直後（`also` などの副詞は透過）、動名詞は前置詞・`be` の後ろも。
    禁止リスト（`test` `build` を修飾語と決める）にはしなかった。機能語の表と動詞・動名詞の表を分けただけで、機能語の扱いは変えていない。
24. **第 3 ラウンド N3: 日本語の左側は「許す側を列挙」。** `次回の` を外し、`現行の` `現在の` も外した（現行の仕組みを聞いているのか、今回決める選択かが決められない）。`リリースの` `プロジェクトの` `案件の` `版の` は直前が `この` `今回の` `本` `当` `今の` のときだけ一般語。
    `どちらの` は問いの限定詞なので表に足した（`どちらの保存形式を使いますか` を上げすぎていたため。凍結データには無い言い方）。
25. **第 3 ラウンド N4: 答えを出す解決器すべてに「閉じた形だけ」を広げた。** レビューが挙げた選択・範囲・許可に加えて、同じ根から、私が見つけた「どちらが先か」「次に着手できる作業」「複数の範囲の語を肢が名指す問い」にも同じ規則をかけた
    （`which was built first last time` `what did the competitor start next` `which was in scope for the old prototype` が答えていた。レビューの表には無かったが、攻撃役が最初に試す形なので同じ修正に入れた）。
    選択の述語は、文全体を `¤`（主題）・`§`（肢）に置き換えて閉じた形に全体一致させる（§8）。語尾の限定は 1 つの閉じた形だけ。禁止リスト（比較語・過去語の列挙）は書いていない。
26. **第 3 ラウンド N4: 許可の出口 3 つ。** 過去形の許可の問い・「すべきか」に「許可」・条件より狭い／別の主体の許可、は答えない。禁止（不可）の答えには効かせない（枠が「常に禁止」と言っているので、時制が違っても向きは同じ。ただし過去形は上げる）。
    「すべきか」の `FRAME_SILENT`（`ADVICE_NOT_PERMISSION`）は、枠の「許可」を助言に写さないため。日本語は条件の後ろの修飾（時など）を見ていない（既知の穴）。
    禁止と受入条件の衝突を優先順位で「許可」にした答え（`f05` の型）は、主体・修飾を見る対象にしない（その文は受入条件の文そのもので、後ろに目的が付くため）。
27. **第 3 ラウンド: `MULTIPLE_QUESTIONS` を答え全部に。** 極性の答えだけでなく、肢の選択・語句の答えにも効かせた。文末が `。` で終わる問い（`…ですか。`）も数える。
28. **レビューとの食い違い 2 点。** (a) `Is it OK to include on-board averaging?` は第 2 ラウンドのコードでも上げていた（上の §9.8）。(b) 私が書いた `Please include on-board averaging?` の対照は、レビューの要求に無く答えない方が安全なので、試験から外した。
29. **第 3 ラウンドの任意項目。** O1（日本語の範囲の述語で助詞の直後の読点を許す）は直した。O2 は一部（`Can we run … on a field unit?` と `業者は…してもよいですか` は上げる。`Can the vendor run …` は元から上げていた。`Which logging format should the vendor use?` は上げる）。
    `現行の保存形式はどれですか` は上げる（24）。O3（実質問の triage の見直し）は今回も 1 件ずつの見直しをしていない。変更は無い。

30. **第 4 ラウンドの方針: 答える形を閉じて列挙し、全体一致したときだけ答える。** 日本語の選択の疑問詞（N6）、許可の操作・主体・時（N7）、パス（N8）に、第 3 ラウンドまでの「述語を閉じた形で確かめる」を広げた。
    禁止リストは書いていない（`_INVERT_CUE` は変えていない）。答える範囲を広げる規則は足していない。迷った点は上げる側に倒した。
31. **同じ根で塞いだ穴（指示書 §2 の予備調査）。** 許可の穴は CONFIRM の「許可」だけでなく、禁止の「不可」にもあった（`<禁止の操作>をやめてもよいですか` `…の手順を書いてもよいですか` `May we stop <禁止の操作>?` に「不可」と答えていた）。
    門を答え全部（可・不可・値が肢と一致した答え・禁止・優先順位・保護と不変条件・パス）にかけた。`_perm_plain_subject_and_tail` は門に吸収して消した。
32. **`w2c-f08-03` は上がるようになった。** `Can we hand a handset to a visitor for the pilot?`（凍結データの正解は「No」）は、`for the pilot` が閉じた後ろの修飾に無いので `FRAME_SILENT` で上げる。
    `pilot` を許す規則は足さず、正解も変えない（指示書 §3 のとおり正しい向きの変化として受け入れた）。Q2（fake）は 107/108 から 106/108 に下がった。
33. **記録の言い直し（L4・R2）は禁止・保護の英語の操作だけで、記録の本文から作る。** 禁止の操作と衝突した受入条件・不変条件（答えの根拠に入っている）の中で、操作の前の語列（末尾の助動詞を除く）を主語、後ろの語列を続きとする。
    第 3 ラウンドから答えている `Can the stress run retry … to measure the delay?`（優先順位で決まる答え。Q4 の試験が要求する）を答え続けるための最小の形で、問いが記録をそのまま言い直したときだけ名詞の主語と目的を許す。
    R2（続き）は L4 のときだけ。`Can we retry … to measure the delay?` のように主語が `we` で目的だけ記録と同じ問いは、上げる側に倒した（R1 の通常の修飾だけを許す）。
34. **他の文の読み（指示書に無い追加。誤答を減らす方向のみ）。** 許可の手がかりの無い文が `Only the vendor will do it.` のように主体・時を言う問い（`Can we run X? Only the vendor will do it.`）に「Yes」と答えていた
    （門が手がかりのある文だけを見ていたため）。承認を言う閉じた形（`Approved.` `The lead approved it.` `町内会長が許可しました。` `承認済みです。` `担当者の承認は得ています。` など）以外の文があれば上げる。
    これは答える範囲を狭める変更で、凍結データの答えは変えない（`r4/calls_changes.txt`、`r4/bank_changes.txt`）。承認を言う別の言い回し（`上長の OK をもらいました` など）は上げすぎる側に倒れる。
35. **名詞で書かれた禁止操作（`…の外部送信` など）は CONFIRM の語と同じ形で読む（指示書に無い追加）。** 指示書の「操作自身の動詞の残り」は、辞書形から語幹を作れる操作（`…を削除する`）を想定しており、
    名詞の操作では語幹が無く、そのままだと今まで答えていた `<名詞>をしてよいですか` まで上げてしまう。名詞の操作は `<名詞>(を|は)(し|行っ|…)て…` の形だけ読む（`を中止して` `を業者がして` は上げる）。
36. **語彙外の言及の後ろ（指示書 §4 のとおり）。** 語の後ろが CONFIRM の名詞の形か、動詞語幹の直後の `<1〜2 字>てもよいですか` のとき。語彙外の語そのものの中に操作（`…を中止`）が入っている場合は見分けられない（§11）。
37. **P5（`どこにしますか`）は答えの元の記録の主題で決める。** 問いの語（別名かもしれない）ではなく、決定の主題・CHOICE の条件の末尾が閉じた場所の名詞のとき。それ以外は上げる。`いつ` `いくつ` `いくら` はどの組にも入れていない（型の対応を確かめる手段が無いため）。
38. **N9 の 2 か所は指示書どおり。** 順序の「どちらが先か」は肢を探す前に、肢が 1 つでも工程として読めなければ `OPTION_UNMAPPED`。選択は `any` を `all` にした。肢が工程名の全文（`Write the sensor driver`）だと `TERM` と読まれる件（O4）は答える範囲を広げるので直していない。
39. **試験の追加の扱い。** 修正前の測定（`r4/traps_before_fix.txt`）の後に 20 本を足した。足した分は第 3 ラウンドのコードに差し替えて測った（§9.9）。

40. **第 5 ラウンドの方針（M1〜M3）。** 前の 4 ラウンドと同じく、答えてよい形を閉じて列挙し、一致しないものは上げる側に倒す。禁止リストは書いていない。答える範囲を広げる規則は足していない
    （`r5/calls_changes.txt` で、上げる → 答えは 0 件）。
41. **M1: 優先順位で「可」になった禁止操作は、記録の言い直し（L4・R1/R2）でしか答えない。** 禁止と受入条件の衝突で受入条件が勝つと「可」になるが、それは受入条件が書く主体と目的の場面に限る。第 4 ラウンドの門は L1（`may we`）を「可」にも「不可」にも同じに通していた。
    答えの極性が「可」で対象に禁止の操作があるときだけ L4 に絞る（`_perm_en_target(..., only_restated=True)`、日本語は言い直しを作らないので常に上げる）。禁止が勝つ「不可」と保護 × 不変条件の「不可」は一般の問いでも正しいので変えない。
    `Can the stress run retry … to measure the delay?` のように記録を言い直した問いは第 4 ラウンドどおり「可」（Q4 の試験が要求する）。第 4 ラウンドの指示書が L4・R2 を「追加で許す形」としか書いていなかった穴で、レビューが指摘した。
42. **M3: 読まれなかった文は上げる。挨拶の組は足さない。** 答えの出口（`finish`）に、問いの文・前提の文・承認の文のどれでもない文があれば `CONTEXT_SENTENCE_UNREAD` で上げる出口を足した。許可の層の同種の関数と共通にした（`_sentences_unread`）。
    挨拶（`Thanks.` `よろしくお願いします。`）は、今答えている問いに挨拶の文を持つものが既存の試験にも自作データにも無かった（`r5/calls_changes.txt`、`r5/bank_changes.txt` で変化 0）ので、閉じた挨拶の組は足さず上げる側に倒した。
43. **M3 と同じ根: 前提の文の修飾。** 「次に着手できる作業」の前提の文は、解決器が「終わった」と読んでいたが、`done in the old prototype` `旧版では…が終わりました` のような修飾は読まずに答えていた（自分で試して見つけた）。
    前提の文を閉じた形（§8）に一致するときだけ「読まれた文」に数え、それ以外は §4 の出口で上げる。凍結データの前提の文 9 問は全部この形に一致する（`tests/test_conduct_ask_traps4.py::test_m3_premise_sentences_of_what_can_we_start_next_are_still_read`）。
44. **M2: `..` と `.` を含むパスは正規化せず上げる。** 正規化すれば `tracker/../tracker/x.py` は答えられるが、答える範囲が広がり、パスの解釈（シンボリックリンクなど）を誤る入口も増えるので、レビューの指示どおり照合せずに上げる。
    新しい detail `PATH_NOT_PLAIN` は許可リストの接頭辞に当たったときだけ。リストの外のパスは従来の `OUTSIDE_ALLOWLIST` のまま（すでに上げていた問いの detail を変えない）。絶対パス（`/tracker/…`）と `~/…` は、門の L が `edit` の直前で終わらない形なので従来から上がっている（`r5/probe_a.py` の出力で確認）。
45. **レビューの任意項目 O-a〜O-d。** O-a（`resolve_order` の (d) の位置が指示書より前）は docs §8 に一言書いた通り（候補を作る前に肢が読めないことを確かめる）で、理由の変化 0。O-b（`_PJA_APPROVED` の前置きの狭め）、O-c（`_perm_ja_target` の `assert`）、
    O-d（`here` を R1 から外す）は、第 5 ラウンドの必須の修正の範囲外で、変更で新しい誤りを入れないため今回は直していない（§11）。
46. **試験を先に書いた順。** `tests/test_conduct_ask_traps4.py` と `r5/traps_before_fix.txt` はコードの変更より前（03:44:00）。前提の文の修飾の 8 本は、自分で試して見つけたあとに足したので、修正前は第 4 ラウンドのコードに差し替えて測った（§9.10）。

47. **第 6 ラウンド（R-A・R-B・R-C）の方針。** 閉じた形で答え、一致しないものは上げる側に倒す方針は変えない。禁止リストは書かない。答える範囲は広げていない
    （`r6/calls_changes.txt` と `r6/bank_changes.txt` で、上げる → 答えは 0 件、値の変化 0 件）。
48. **R-A: 続きを持つ記録は、続きを言う問いにだけ「可」と答える。** 変更は `_perm_en_target` の 1 行（`if r2 or (r1 and not (only_restated and cont))`）。記録の主語が `we` のとき L4 は L1 と同じ文字列なので、
    第 5 ラウンドの `r1 or r2` では、記録の条件を言わない一般の問いにも「可」だった。続きが空の記録は従来どおり R1 でも答える（`test_ra_a_criterion_with_no_continuation_still_answers_the_plain_question` が固定）。
    禁止が勝つ「不可」と保護 × 不変条件の「不可」は `only_restated` でないので変えない。
49. **R-B: 許可の層の外では、承認の文は前置きの無い形だけ。** 承認は選択・値・範囲・順序の答えを変えないので、前置きを読む理由が無い。`finish` の `_sentences_unread(..., bare=out.layer != "permission")`。
    `確認済みです` は承認ではないので、前置きの無い形（`_PJA_APPROVED_BARE`）には入れない（許可の層の広い形には従来どおり残る）。許可の層の答えは、答えたままにする一覧（`町内会長が許可しました。` など）を守るため従来のまま。
    その結果、第 5 ラウンドの試験の対照 `Is humidity tracking in scope? The lead approved it.` は上がるようになった。第 5 ラウンドで足した新しい試験の対照で、レビューが移動を認めたので上げる側に移した（既存の指揮者の試験の期待値は変えていない）。
50. **R-C: 試験の assert を意味のあるものに。** `Which radio band …` は枠に語が無く、語彙外で上がっていただけで「同じ文の条件が上がる」ことを確かめていなかった。枠の語に直し、理由が `VOCAB_UNMAPPED` でないことを固定した。
    無い出力ファイルの引用は、第 4 ラウンドのコードで流して出力を保存した（`r6/dotslash_before.txt`）。
51. **試験を先に書いた順。** `tests/test_conduct_ask_traps5.py` と `r6/traps_before_fix.txt` はコードの変更より前（04:10:07、コードの最初の変更は 04:10:31）。

52. **第 7 ラウンド（S-A・S-B・S-C と `resolver`）の方針。** 閉じた形で答え、一致しないものは上げる側に倒す方針は変えない。否定語の表（`_NEG_EN` `_NEG_JA` `_INVERT_CUE`）は広げず、禁止語を足さない。
    答える範囲は広げていない（`r7/calls_changes.txt` と `r7/bank_changes.txt` で、上げる → 答えは 0 件、値・index の変化 0 件）。レビューの任意の改善（O-1・O-2・O-b〜O-e）はやっていない。
53. **`resolver` の欄を足した理由。** 答えを出した段の名前が、出力の決まった欄から取り出せなかった（`derivation` は `DIRECT`/`COMBINED` だけ、`Outcome.layer` は 4 つの解決器を全部 `"resolver"` と書く）。
    `derivation` の値は既存の試験 6 か所が固定しているので、値を変えずに新しい欄 `resolver` を `derivation` の直後に足した。このため既存の試験の `KEYS`（出力の鍵の完全一致）に `"resolver"` を 1 つ足した（検査は弱めていない）。
    次のチケットで、LLM を使う設定のときに規則の答えを LLM の対応づけで裏づける設計にするための準備。
54. **`inv_wins` の入力の差し替え。** 凍結の f03 の I1 は `未公開の草稿を外部の査読者に送ることはしない` と対象を限定していて、S-B の規則では条件つきの不変条件になる。そのため「優先順位で不変条件が勝つ」の試験の入力を、
    同じ試験の中で I1 を無条件の形に置き換えた（レビュー r3 S-B が認めた差し替え）。元の I1 のままで上がる型は traps6 で固定した。凍結データ（`tests/conduct_ask/fixtures/`）は変えていない。
55. **`INVARIANT_IS_CONDITIONAL` の理由の型は `HUMAN_APPROVAL_REQUIRED`。** 条件の外では操作は保護（人間の承認が必要）で、不変条件は条件の中の操作だけを否定している。「枠が沈黙」ではなく「承認が要る」が近いので。
56. **条件つきの不変条件の言い直しにも答えない。** レビューは「続きをそのまま言う問いには答えてよい」と書いたが、今それは上げていて、答えるようにすると答える範囲が広がる。範囲を広げない決定を優先し、常に上げる。
57. **`ことはない` `ことはありません` と `禁止` `許さない` を閉じた形に入れない。** 「その必要はない」とも読めるため、また否定語の表を広げないため。UNREADABLE として上がる。レビューの例示より狭くした。
58. **日本語の無条件の主語を代名詞 3 つ（`私たち` `我々` `われわれ`）に限った。** `<名詞>は` 一般を主語として許すと `卒園前は…` の時の条件が主語と読まれて S-B の誤答が残る。英語も主語は空か `we` だけ。上げすぎの側に倒した。
59. **`unreadable` は優先順位を見る前に上げる。** 向きが読めない記録は、優先順位が書いてあっても「どちらの側か」が決まらない。既存の試験と自作データには UNREADABLE になる記録が無く、既存の上げる理由は変わらなかった（`r7/calls_changes.txt`）。
60. **`PATH_CASE_DIFFERS` の順番は `OUTSIDE` → `NOT_PLAIN` → `CASE_DIFFERS` → 可。** すでに上げている問いの型を変えないため。許可リストや質問を正規化して比べ直さない（比べ直すと大文字の許可リストで上げる → 答えが起きる）。
61. **試験を先に書いた順。** `tests/test_conduct_ask_traps6.py`（04:53:46）、`tests/test_conduct_ask_provenance.py`（04:54:02）と `r7/traps_before_fix.txt` `r7/provenance_tests_before.txt`（04:54:03）はコードの変更（04:54:39）より前。
62. **コードは中間職の試作の差分をそのまま使った。** 指示書の仕様（§3）と読み比べて同じであることを確かめたうえで `patch` で当てた（`r7/code_diff_r6_to_r7.diff` が結果）。仕様との違いを見つけた箇所は無い。
    直接の探り（`r7/probe_stance_forms.txt`）で、仕様の一覧の記録の向きが変わらないことと、閉じた形の端の例を確かめた。

## 11. 既知の穴

- 自作データは実装役が書いたため、評価バンクより易しい可能性がある。Q1 の 0 は、この検査データでの値であり、評価バンクでの値ではない。
- 名詞化した言い方（`…を検出する` と `…の検出`）は当てない。取り置きの 1 問がこれで上げられた（§9.2）。
- 手がかりの表は日本語と英語だけ。後で・after 系の順序（`…した後で…`）は答えず上げる。
- 実質問 72 件は 0 件しか答えられない。枠（`docs/frames/vera_project_frame.md`）に書かれた決定は、公開・削除などの保護された操作と少数の方針だけで、人間の質問の大半はプロジェクト作業に関するもの。
  72 件のうち 58 件は `VOCAB_UNMAPPED`（質問の役割の手がかりが読めない、または語が 1 区間にならない）で、LLM の経路（`--vocab-llm codex|claude`）では測っていない（実プロバイダは呼ばない約束）。
- `codex` / `claude` のプロバイダは、構築の経路を試験していない（作り物と差し替えのみ）。
- jsonl の枠の同値確認は、compile できた英語の枠 1 つと例の枠 1 つだけ。日本語の jsonl の枠は作れていない（`compile_frame` の制約）。
- 許可の質問に含まれる `vera.db` のようなファイル名は、書き込み許可の判定でパスとして読まれる（許可リストに無ければ上げるだけ）。
- `conductor_run` からはまだ呼ばれていない（接続は別チケットの範囲）。`[agent_settings]` は読まない。
- 第 2 ラウンドの述語の許可リストと左側の修飾語の表は、一般的な言い方だけを読む。自然だが表に無い言い方（`作れますか`、`Is it fine that …`、`Which sole …`）は上げる。上げすぎは Q2 を下げうるが、誤答にはならない側に倒した。
  評価バンクでの上げすぎの量は未測定（`tests/bank_score/fixtures/B5/` は開かない約束）。
- 述語の読み違えは、許可リストの外の言い方では防げているが、許可リストの中の言い方で枠の記録が別の意味を持つ場合（例: `Should we start Y before X?` の `should` は「してよいか」と「すべきか」の両方に読める）は、極性の意味を区別していない。
- 実プロバイダ（codex / claude）で語彙外の経路を通した測定は無い。
- **第 3 ラウンドの既知の穴**（述語の閉じた形を広げたが、全部ではない）:
  - 受入条件の解決器（`人が判定するか` `command は何か`）は、時制・主体の述語を見ていない。前提の工程を聞く問い（`must be finished before`）は、必要性の手がかり（`must` `終わっているべき`）がある形にしか入らないので、
    `What was finished before … last time?` は上げる（`TERM_IN_WIDER_PHRASE`）が、これは述語の規則ではなく右側の語の規則で上げている。
  - 英語の許可の後ろの修飾は `now` `for this release` など少数だけを許し、それ以外は上げる（`Are we allowed to run X before the review?` も上げる）。上げすぎだが誤答にはならない側。
  - 選択の述語は、主題が 1 つの文にだけ当たる前提で文全体を照合する。文が複数の節（`…、そのうえで…`）を持つときは上げる。1 文目が閉じた形で 2 文目が問いでない文（`Which radio band should we use? Please decide.`）は答える。
  - 日本語の述語の許可リストは、よく使う活用（`て` 形・連用形・辞書形）だけ。可能形（`作れますか`）や丁寧な言い換えは上げる。
  - 評価バンク（B5）での第 3 ラウンド後の上げすぎの量は未測定（`tests/bank_score/fixtures/B5/` は開かない約束）。
- **第 4 ラウンドの既知の穴**:
  - **語彙外（`--vocab-llm` が off 以外）の語そのものの中に操作が入っている場合は、門で見分けられない。** 例: 語として切り出された `予約の記録を消去を中止` が LLM の閉じた選択で枠の禁止の操作に対応づけられたとき、
    後ろ（`してもよいですか`）は閉じた形に一致する。今回の評価（`--vocab-llm off`）では起きない。次のチケット（LLM に閉じた選択で「どの記録に当たるか」を聞く）の範囲。
  - **言い換えは読めない。** 評価バンクの問いは枠の記録を言い換えているため、語の一致では結び付かず、規則では 0 件しか答えられない（監査役の測定。この文書の自作データの Q2 とは別の値）。言い換えは次のチケットで扱う。
  - 日本語の選択の `いつ` `いくつ` `いくら`（日付・数の主題への問い）は、型の対応を確かめる手段が無いので答えない（上げすぎ）。`何がよいですか` `どうですか` も答えない。
  - 英語の許可は `Is X permitted?` `Is X allowed?`（`it` を使わない形）や `May we please …` も答えない（上げすぎ）。許可の手がかりのある文のほかの文は、承認を言う閉じた形だけ許す（上げすぎの側）。
  - 同じ文に CONFIRM・禁止・保護の言及が 2 つ以上あるときは、全部が閉じた形でなければ上げる。パスが 2 つ以上ある文は上げる。
  - 禁止・保護の英語の操作は、`<助動詞> <主語> <操作>` の記録の言い直し（L4）を、記録の本文に操作と主語がそろっているときしか許さない。操作の別名（英語）は、枠の語の語幹の一致で当たる範囲だけ。
  - O4（肢が工程名の全文 `Write the sensor driver` だと `TERM` と読まれ、「どちらが先か」を上げすぎる）と O5（`Is the packet layout judged by a human?` が `VOCAB_UNMAPPED`/`NO_ROLE` で上がる）は直していない（答える範囲を広げる変更のため）。
  - 実プロバイダ（codex / claude）で語彙外の経路を通した測定は無い（作り物のみ）。評価バンク（B5）での第 4 ラウンド後の値は未測定。
  - `_BUILTIN_PROTECTED` の語の表（`削除` `外部送信` など。第 3 ラウンド以前から）は一般語だが、枠の語と文字列が重なる場合がある。Q7 の検査（`artifacts/w2-c/q7_check.py`）は 3 文字未満の語を数えないので、この表との重なりは見ていない（第 4 ラウンドの補助の検査 `r4/q7_check_r4.py` は見ていて、第 4 ラウンドで新しく入った重なりは 0）。
- **第 5 ラウンドの既知の穴**:
  - 優先順位で「可」になった禁止の操作は、日本語では記録の言い直しを作らないので、記録をそのまま言い直した問いも上げる（`夜間の点検で古い控えを破棄してよいですか？` を上げる。上げすぎ）。英語は記録の本文から作る言い直しだけ答える。
  - 読まれなかった文は、閉じた 3 種（問いの文・前提の文・承認の文）以外は全部上げる。挨拶（`Thanks.` `よろしくお願いします。`）や `Please answer briefly.` も上げる（上げすぎ）。
    前提の文の閉じた形は `<工程>が終わりました` 型だけで、`We finished <工程>.` `<工程>は完了済みです` のような言い方は上げる（上げすぎ）。承認の文も閉じた形のみ（`Approved by the lead.` は上げる）。
  - `..` `.` を含むパスは、許可リストに当たるものだけを `PATH_NOT_PLAIN` で上げ、外のパスは従来の型。`~/…` `/…`（絶対パス）は第 4 ラウンドの門が上げているが、それはパスを見ての判断ではなく動詞の直前の形が合わないため（`/` の前に空白がある形などは未調査）。
  - 第 4 ラウンドの任意項目 O-b（`_PJA_APPROVED` の前置きが広い）・O-c（`_perm_ja_target` の `assert`）・O-d（R1 が `here` を許す）は直していない。O-b（許可の層の承認の文の前置きが広い）は、第 6 ラウンドで許可の層の外だけ閉じた。許可の層の答え（可・不可）は承認の文の前置き（`来年度の承認済みです` `中学校の承認をもらいました`）を今も読む。
    CONFIRM の可・不可・禁止の不可は承認で変わらないので誤答にはならないが、広い。
  - 語彙外の語に操作が入る穴（第 4 ラウンドから）、O4・O5、評価バンク（B5）での測定が無いこと、実プロバイダが未試験であることは変わらない。
- **第 6 ラウンドの既知の穴**:
  - 許可の層の承認の文の前置き（上の O-b）は広いまま。`The old greenhouse team approved.` のような場所の語も許可の層では通る（答えの値は変えない）。
  - R-A の制限は英語だけ（日本語は言い直しを作らないので、もともと常に上げている）。続きを持つ記録を言い直した問いは、続きが一語一句同じでないと上げる（上げすぎ）。
  - O-e（`only_restated` のとき、操作の動詞が表に無い問いの detail が `PERMISSION_FOR_ANOTHER_OPERATION` ではなく `…_SUBJECT_OR_CONDITION` になる）は直していない（答えは変わらない。型の精度だけ）。
  - O-c（`_perm_ja_target` の `assert`）・O-d（R1 が `here` を許す）は直していない。
  - 語彙外の語に操作が入る穴（第 4 ラウンドから）、O4・O5、評価バンク（B5）での測定が無いこと、実プロバイダが未試験であること、`test_s6` のコミット後の確認は変わらない。
- **第 7 ラウンドの既知の穴**:
  - 否定語を使わない禁止の言い方（`Wiping the card reader is forbidden`、`We are forbidden to wipe the card reader`）は、記録の向きでは POS（要求）と読まれる。
    今は許可の門で上がることを確かめた（`r7/stance_hole_probe.txt`）が、向きの読み取り自体はこの言い方を拒否の記録と見ていない。
  - `ことはない` `ことはありません` と、`禁止` `許さない` を使った不変条件は閉じた形に入れていないので、UNREADABLE として上がる（上げすぎ）。
  - 条件つきの不変条件の言い直し（`May we export the passenger manifest before the ferry departs?`）にも答えない（上げすぎ。範囲を広げない決定）。
  - 主語が `we` 以外の英語の不変条件（`The kiosk never exports …`）、`<名詞>は` で始まる日本語の不変条件、続きを持つ不変条件（`… unless asked`）は条件つき扱いで上がる（上げすぎ）。
  - 複数の解決器が同じ答えを出して `COMBINED`（`resolver` が 2 つ以上）になる呼び出しは、試験でも自作データでも起きていない（`r7/provenance.txt`）ので、この場合の `resolver` の値は試験で固定していない。
  - 規則だけで自然文の質問を読む方式の残りのリスクは §12。評価バンク（B5）での測定が無いこと、実プロバイダが未試験であること、`test_s6` のコミット後の確認は変わらない。

## 12. 既知の限界（規則だけで自然文の質問を読む方式）

- この入口は、自然文の質問を規則（閉じた形の列挙）で読み、列挙に無い形は上げる設計である。ただし列挙した形の中での読み違い（記録の向き・条件・主体・時・大文字小文字など）は、罠を書かれるたびに見つかってきた。
  規則だけの方式には、**まだ誰も書いていない言い回しで誤答する残りのリスク**があり、これまでの経過はそれを否定できていない。
- 中間職のレビューの罠の経過（数値は `artifacts/w2-c/r7/trap_history.txt` の各行から写した。出典の列はその行の位置）:

  | ラウンド | 罠の問い | 誤答 | 出典 |
  |---|---:|---:|---|
  | W2-c 第 1 | 約 85（出典の記載が概数） | 19 | `W2-c/review.r1.md:181` |
  | W2-c 第 2 | 73 | 41 | `W2-c/review.r2.md:98` |
  | W2-c 第 3 | 102 | 28 | `W2-c/review.r3.md:11` |
  | W2-c3 第 1（通算第 4） | 137 | 10 | `W2-c3/review.r1.md:10` |
  | W2-c3 第 2（通算第 5） | 74 | 24 | `W2-c3/review.r2.md:11` |
  | W2-c3 第 3（通算第 6） | 208 | 14 | `W2-c3/review.r3.md:11` |

  各ラウンドの罠は、前の回までの罠の誤答を 0 にしたあとに新しく書かれたもので、新しい罠ではそのたびに誤答が出た。罠の書き足しは第 6 で打ち切った（監査役の決定）。
  これらの数値は中間職の記録から写したもので、このツリーでは再計算できない（罠のスクリプトは実装役に渡されていない）。
- 第 7 ラウンドは、第 6 の罠の誤答 14 件の 3 つの根（S-A・S-B・S-C）を閉じた形で塞ぎ、その問いを `tests/test_conduct_ask_traps6.py` で固定した（§9.12）。未知の言い回しで誤答が無いことは示せていない。
- 予定（監査役の決定。次のチケット）: LLM を使う設定のときは、規則が出した答えも LLM の閉じた選択による対応づけ（独立 2 回の一致）で裏づけられた場合だけ採用し、食い違えば上げる。
  そのための欄として、答えに `resolver`（答えた段）と `basis`（根拠の記録の id）が必ず入ることを `artifacts/w2-c/r7/provenance.txt` で確かめた（答え 725 回・79 回・106 回すべてで問題 0。§9.12）。
