# 人間の自由文の説明から分業の記録を作る (W2-h2)

人間が **自分の言葉で** 書いた「どのエージェントがどういう性質か」「どう振り分けたいか」の説明（日本語・英語、散文・箇条書き・表・追記つき）から、
W2-h（`docs/AGENT_ROUTING.md`）と **同じ記録** を作り、W2-h の経路づけ器で仕事 1 件の振り先を決める。
入口は `python -m verantyx.cli route --explanation <file> --task <json>`、実装は `verantyx/routing_from_text.py`。実行時に LLM は使わない。

- 試験: `tests/test_routing_from_text.py`（手で作った読解出力での単体試験）、`tests/test_routing_from_text_entry.py`（入口）、
  `tests/test_routing_from_text_data.py`（凍結した自作データ）、`tests/test_routing_from_text_regress.py`（本物の読解器を通す回帰試験。第 1 ラウンドのレビューの探りの文）
- 道具: `tests/routing_from_text/run_bank.py`（バンクを入口で流して採点）、`check_no_text_words.py`（T4 の機械の部分）、`reader_gaps.py`（読めなかった単位の集計）、
  `constants_in_data.py`（定数の表の項目のうち検査データの説明文に現れるものの全件。7 章）、
  `recompute.py`（この文書の「測定結果」の区間を `artifacts/w2-h2/` から作り直して照合）
- 凍結した検査データ: `tests/routing_from_text/data/`（`FROZEN.json` に sha256・日時・書き手。説明文と中間職の task は中間職、実装役の task は実装役）

## 0. 先に読む（到達状況）

**読解器の被覆は、普通に書かれた説明文にはほぼ届かない。** 読解器は「X が Y を V する」「Y は X がやる」「X は Y より A」「X と Y は同じ会社だ」「X reviews/writes/checks/reads/attacks Z」
の単文とその否定しか読めない。そこで、この版の芯は **「読めなかった単位が 1 つでもある説明文からは、どの仕事も振らない（型付きで棄権する）」**（判断 J1）である。
読めない文には「ただし」「追記」「人がやる」が書かれているかもしれず、それを読まずに振れば誤って振る。承認の条件は「誤って振った数 0」で、正答率は条件ではない。
その結果、普通の文の説明では、ほぼ全部が棄権になる。数は「測定結果」の区間にある（推測で書かない）。

読解器が読める形の説明文（`reader_shaped`）では、読解器 → 十字 → 関係 → 記録 → 経路づけ器の全経路が通って route になる。手で作った読解出力では、関係の取り出し・記録への写像・
門・経路づけ・後段の制約を単体試験で全部固定している。

## 1. 目的と三層の中での位置

```
producer（枠の DSL / 自由文の読解 = この文書 / 辞書）── 記録を作るだけ
   ↓ AgentRecord / RoutingRule / RoutingPrecedence / LineageRelation（basis つき）
記録層 agent_routing.build_routing_table ── 意味の検査はここだけ
   ↓ RoutingTable
経路づけ器 agent_routing.route ── DSL も自由文も知らない
```

この文書の producer は、記録層・経路づけ器・十字・読解器を **呼ぶだけ** で変更しない（`git diff --stat` が空であることを `artifacts/w2-h2/untouched.txt` に残した）。
十字は話題に依存しない意味の層で（`docs/EVENT_CROSS.md`）、この producer はその述語の中心・腕の役割・充填物・量化・比較・極性・モダリティから関係を取り出す。

## 2. 流れ

```
説明文の全文
  └ (1) 分節: 行と文末記号で「単位」に切る（形だけ。話題の語を見ない）
       └ (2) 読解: 単位ごとに semantic_read.read ＋ event_cross.attach_events（試験では手で作った読解出力を差し込める）
            └ (3) 関係の取り出し: 十字の中心（述語の類・極性・モダリティ・比較）と腕（役割・充填物）と量化から、閉じた関係の集合へ
                 └ (4) 記録への写像: 関係 → AgentRecord / RoutingRule / RoutingPrecedence / LineageRelation（basis = Basis.text(説明文のパス, 原文の文...)）
                      │      ＋ 記録の型に入らない関係（禁止・人がやる・待つ・検証以外の独立）は「後段の制約」
                      └ (5) 門: MAPPED / COMPARISON_ONLY 以外の単位が 1 つでもあれば、どの仕事も振らない（INCOMPLETE_READING）
                           └ (6) build_routing_table（記録層の拒否は RECORD_REFUSED）
                                └ (7) route(table, RoutingRequest(...))（chooser_factory なし）
                                     └ (8) 後段の制約: 決定を「振らない」に変えることだけができる
                                          └ (9) 出力（決定的な JSON 1 行）
```

## 3. 単位の切り方（`segment`）

形だけを見る。話題の語は見ない。文字の集合の定数でループし、正規表現は使わない。

- 切る場所: 改行、文末記号（`SENTENCE_ENDS`。`.` は直後が空白か行末のときだけ。`5.5` は切れない）。文末記号の直後の閉じ括弧・引用符（`CLOSERS`）は同じ文に残す。
- 行頭の記号（`LIST_MARKERS`、`1.` `1)` のような番号、見出しの `#`）は外して読解器に渡し、外した記号は単位の `marker` に残す。
- 記号だけの行（空行・`---`・表の区切り行 `|---|---|`。`MARKUP_CHARS` と空白だけの行）は単位にせず、`reading.skipped_markup` に数える（末尾の改行の後の空行も 1 行と数える）。
- 表の行（`|` で始まる行）は 1 行を 1 単位として渡す（表の解釈はしない。読めなければ門が止める）。
- 単位の `witness` は説明文の原文の部分文字列（その行を、前後の空白だけ落としたもの。文末記号を含む）。1 行に複数の文があるとき、最初の文の witness は行頭の記号・ラベルを含む行の先頭からその文の終わりまで、
  2 つ目以降は文だけ。
- 追記の印（`OVERRIDE_MARKERS`）が行頭のラベル（`追記（翌日）：` `P.S. ` `Update:`）として現れたときに限り、ラベルを外した残りを読解器に渡し、その行の全部の文に `override: true` を付ける。
  印は NFKC・小文字化した **語全体** との一致で、語の一部とは照合しない（`追記は誰かが書く。` や `Updated:` は追記ではない）。
- （W5-b で追記）印のうち「足す」を言うもの（`ADDITION_LABELS`: `追記` `追伸` `p.s.` `ps` `addendum`）の行は、**文ごとに**、その文に置き換えの標識（`REPLACEMENT_MARKERS`: `やっぱり` `ではなく` `instead` `replace`）があるときだけ上書き（`UnitResult.override` と関係の `override`）として扱う。
  標識が無い文は上書きでない普通の単位（足す）になる。`Unit.override`（行が印で始まった）と `Unit.label`（その印の比較用の形）は文の切り方の結果として今までどおり付け、上書きかどうかの判定は `extract` が行う。足すのに使われた単位の数は出力の `reading.addition_labels_kept_as_addition`。

## 4. 関係の集合と写す先（`RELATION_KINDS`）

読解器の十字の 1 節（中心＋腕）が、次の閉じた集合のどれかに落ちる。落ちなければ単位は `UNIT_STATUSES` の止まる状態になる（10 章）。

| 関係 | 取り方（汎用の材料だけ） | 写す先 |
|---|---|---|
| `SUITABILITY`（適性・割り当て） | 述語の類が `ASSIGN`（recipient が agent、patient が仕事）/ `PERFORM`（agent と patient）/ `SUIT`（agent か entity と、goal・patient・attribute のどれか）/ `ROLE_VERB`（動詞が仕事を言う）/ `CREATE_VERB`（動詞＋目的語）。極性 `+`、モダリティ `null` か `obligation` | `RoutingRule`。仕事の語から `role=` / `kind=` / `size=`。条件が `role=` だけなら `fallback=True`。選好は `(呼び名,)` |
| `PROHIBITION`（禁止） | 上と同じ述語で極性 `-`、またはモダリティ `prohibition` | 記録にしない。後段の制約 `prohibit` |
| 例外（`EXCEPTION`） | 独立の種類にしない。範囲の狭い `SUITABILITY` / `PROHIBITION` として読む（経路づけ器は受け皿より条件つきの規則を先に見る） | 同上 |
| `COMPARISON`（比較） | `SUIT` 類で `comparison: comparative`、standard が呼び名。「A は B より検証に向く」 | `RoutingRule` 選好 `(A,)` だけ。B を 2 番手にしない（言われていない「B でもよい」を作らない） |
| `COMPARISON_ONLY` | 述語が類の表に無く、腕が entity と standard だけでどちらも呼び名。「A は B より速い」 | 記録にしない。**門を止めない唯一の「読んだが記録にしない」類**（J8） |
| 条件（`CONDITION`） | 独立の種類にしない。仕事の語の `SIZE_TERMS` の修飾が `size=`、仕事の語が `kind=` / `role=` | 規則の条件。読解器の `relations`（節の間の条件・理由など）は写さない（`UNREPRESENTABLE`、判断 D2） |
| `INDEPENDENCE`（独立・系統） | コピュラ（`だ` / `be`）で entity が並列の 2 名（`と` / `and`）、value が（`IDENTITY_TERMS` の語, `LINEAGE_HEADS` の語）の 2 語 | 同一 → `LineageRelation(a, b, same)`。否定の同一（not the same family）→ `distinct`。**肯定の差異（別の会社だ）は割れる** ので `AMBIGUOUS_RELATION`（両方の読みを `relations` に `held` で残し記録は作らない）。entity が役割の名詞 2 つ（`ROLE_NOUNS`）で 実装・検証 の組 → 経路づけ器の既定 R3 そのものなので記録を作らず `represented_by: ROUTER_DEFAULT_R3`。それ以外の役割の組 → 後段の制約 `independent` |
| `QUANTITY`（数量） | `RUN` 類（動かす・run）で agent を言い、量化が `at_most:N` / `exactly:N`（キーは `event` かその腕）| `AgentRecord.concurrency = N`。1 日の回数・全体の上限など記録の欄に無いものは `UNREPRESENTABLE` |
| `PRECEDENCE`（優先） | `PREFER` 類で優先する側と される側が呼び名 | `RoutingPrecedence`。**同じ条件の非受け皿の規則が、優先する側に 1 本・される側に 1 本** と一意に写せるときだけ。そうでなければ `AMBIGUOUS_RELATION` |
| 追記による上書き（`OVERRIDE`） | `override: true` の単位の関係 | 範囲（`role` / `kind` / `size` の集合）が **まったく同じ** 先の関係のうち、**同じ種類の言明**（割り当て→割り当て）か **同じ呼び名** の関係を置き換える。置き換えた先は `relations[].superseded_by` に残し `reading.auto_resolved` に数える。範囲が同じで、種類も呼び名も違う先（「A がやる」→「B はやらない」）があれば足すのか置き換えるのか分からないので `AMBIGUOUS_RELATION`（判断 D13）。範囲が一部だけ重なる（共通の欄が一致し、同じではない）なら `AMBIGUOUS_RELATION`。重ならなければ足すだけ |
| `ALIAS`（別名） | `CALL` 類（呼ぶ・call）だけ。コピュラ（「X は Y だ」）で両方が呼び名のときは別名とは取らない: 別名（「L はルナだ」）とも所属・述定（「ハルは東社だ」）とも読める割れる読みなので `AMBIGUOUS_RELATION`（両方の読み `COPULA_IS_ANOTHER_NAME` / `COPULA_IS_A_PREDICATE_OF_THE_FIRST` を `held` に残し、別名の表も記録も作らない。判断 D14）。value が仕事の語なら別名でなく割り当て | 別名の表。記録の ID は最初に名指しされた呼び名（8 章） |
| `HUMAN` | 述語の類の agent（`ASSIGN` では recipient）が `HUMAN_TERMS` | 後段の制約 `human`。範囲が `RESIDUAL_TERMS` なら経路づけ器の `NOT_COVERED` だけを置き換える |
| `WAIT` | `WAIT` 類（待つ・hold）で仕事の腕が引ける | 後段の制約 `wait`（同上） |

腕のうち使わなかったもの（時・場所・手段など）が 1 つでもあれば `UNREPRESENTABLE`（`UNUSED_ARM`）。量化・モダリティ・態・スコープ・節の間の関係も、使わなかったものがあれば止まる。
中心の `tense`（時制）も同じで、読解器の非過去の値 `nonpast` 以外（`past`・`null` など）は `UNREPRESENTABLE`（`TENSE:<値>`）。過去の出来事（「ハルが実装をやった」「Rook reviewed the code」）は「前回だれがやったか」の報告で、
振り分けの宣言ではないから（判断 D15）。`tense` の欠けた読解出力は十字が入力として拒否する（`INPUT_REJECTED`）ので `UNREAD` になる。
腕が `ARM_TIE`（候補が割れた）なら `AMBIGUOUS_RELATION`（どれも選ばない）。

## 5. 述語の類の引き方

粗い配置（W3-a2）は未統合で、既定の `PlacementLookup` は全部 `NO_PLACEMENT`（`stub-no-placement/1`）を返すスタブである。したがって **述語の類も充填物の型も配置からは何も引けず、型一致は全部 `NOT_CHECKED`** で、
この producer は配置を使わない。述語の類は次の手の表（6 章に全項目と理由）から、読解器が返した辞書形との完全一致（NFKC・小文字化）だけで引く。
表に無い述語は `PREDICATE_CLASS_UNKNOWN`、仕事の語が表に引けなければ `WORK_TERM_UNKNOWN`。どちらも門を止める。
粗い配置が統合されたら、呼び名の腕の型（`PERSON` / `GROUP_ORG` 以外は棄権）などに使える（申し送り）。

照合は、読解器が返した辞書形・充填物の文字列との完全一致、または fugashi で切った形態素の並びとの完全一致だけで、説明文の生の文字列に対する部分文字列の探索・正規表現はしない。
充填物の形は「修飾語（`SIZE_TERMS` に引ける）＋主辞」までで、主辞は修飾語を除いた残りを連結した文字列で `WORK_TERMS` に完全一致で引く（`リファクタリング` は fugashi で 2 語に切れる）。
それ以外の形（`設計の大きな変更` のような の 句）は `WORK_TERM_UNKNOWN`。

## 6. 定数の表（全項目と理由）

すべて `verantyx/routing_from_text.py` の先頭にある。**task（期待）を書く前、かつ入口を検査データに通す前に凍結した**（凍結の日時とハッシュは「測定結果」の区間。ハッシュは正準 JSON の sha256 で、
`artifacts/w2-h2/freeze_constants.py` が作る）。**説明文 e1〜e6 の本文は、凍結の前に読んでいる**（7 章。実装役は定数を書く前に本文を一度読んだ）ので、定数が「データを見ずに書かれた」とは言えない。
定数の項目のうち e1〜e6 の語・句そのものであるものは 7 章に全件載せた。項目は閉じた語彙（`docs/AGENT_ROUTING.md` 2 章の `ROLES` / `TASK_KINDS` / `SIZES`）の意味と 1 対 1 に言えるものか、構文の語（コピュラ・照応・敬称）だけで、
1 対 1 でない語は **入れていない**（入れなければ棄権になるだけで、誤って振らない）。表の「reason」は、その項目の語の意味（英語の言い換え）で、値の欄が写す先の類・役割・種類・大きさである。


#### `PREDICATE_CLASSES`

| lang | entry | value | reason |
|---|---|---|---|
| ja | `任せる` | ASSIGN | delegate |
| ja | `頼む` | ASSIGN | ask someone to do |
| ja | `回す` | ASSIGN | pass a job on to |
| ja | `割り当てる` | ASSIGN | assign |
| en | `assign` | ASSIGN | assign |
| en | `delegate` | ASSIGN | delegate |
| ja | `やる` | PERFORM | do |
| ja | `行う` | PERFORM | carry out |
| ja | `受け持つ` | PERFORM | take charge of |
| en | `do` | PERFORM | do |
| en | `handle` | PERFORM | handle |
| ja | `向く` | SUIT | be suited to |
| ja | `適する` | SUIT | be suitable for |
| en | `suit` | SUIT | suit |
| ja | `確かめる` | ROLE_VERB | check -> verify |
| ja | `読む` | ROLE_VERB | read -> read |
| ja | `答える` | ROLE_VERB | answer -> answer |
| en | `check` | ROLE_VERB | check -> verify |
| en | `verify` | ROLE_VERB | verify -> verify |
| en | `review` | ROLE_VERB | review -> review |
| en | `read` | ROLE_VERB | read -> read |
| en | `answer` | ROLE_VERB | answer -> answer |
| en | `attack` | ROLE_VERB | attack -> the kind attack |
| ja | `書く` | CREATE_VERB | write |
| ja | `作る` | CREATE_VERB | make |
| en | `write` | CREATE_VERB | write |
| en | `implement` | CREATE_VERB | implement |
| en | `build` | CREATE_VERB | build |
| ja | `優先する` | PREFER | give priority to |
| en | `prefer` | PREFER | prefer |
| ja | `待つ` | WAIT | wait |
| en | `hold` | WAIT | hold |
| en | `wait` | WAIT | wait |
| ja | `呼ぶ` | CALL | call |
| en | `call` | CALL | call |
| ja | `だ` | COPULA | be |
| en | `be` | COPULA | be |
| ja | `動かす` | RUN | run (transitive) |
| ja | `走らせる` | RUN | make run |
| en | `run` | RUN | run |

#### `VERB_WORK`

| lang | entry | value | reason |
|---|---|---|---|
| ja | `確かめる` | ("role", "verify") | to check is to verify |
| ja | `読む` | ("role", "read") | to read is the role read |
| ja | `答える` | ("role", "answer") | to answer is the role answer |
| en | `check` | ("role", "verify") | check |
| en | `verify` | ("role", "verify") | verify |
| en | `review` | ("role", "review") | review |
| en | `read` | ("role", "read") | read |
| en | `answer` | ("role", "answer") | answer |
| en | `attack` | ("kind", "attack") | attack is a kind of job, not a role |
| ja | `書く` | ("role", "implement") | to write (with no object that says more) is to implement |
| ja | `作る` | ("role", "implement") | to make (the same) |
| en | `write` | ("role", "implement") | write (the same) |
| en | `implement` | ("role", "implement") | implement |
| en | `build` | ("role", "implement") | build (the same) |

#### `WORK_TERMS`

| lang | entry | value | reason |
|---|---|---|---|
| ja | `実装` | ("role", "implement") | implementation |
| ja | `検証` | ("role", "verify") | verification |
| ja | `レビュー` | ("role", "review") | review |
| ja | `生成` | ("role", "generate") | generation |
| ja | `読解` | ("role", "read") | reading |
| ja | `読み込み` | ("role", "read") | reading in |
| ja | `回答` | ("role", "answer") | answering |
| ja | `攻撃` | ("kind", "attack") | attack |
| ja | `テスト` | ("kind", "test_authoring") | tests (the work of writing them) |
| ja | `新機能` | ("kind", "feature") | a new feature |
| ja | `修正` | ("kind", "small_fix") | a fix |
| ja | `リファクタリング` | ("kind", "large_refactor") | refactoring (concatenated: fugashi cuts it in two) |
| ja | `リファクタ` | ("kind", "large_refactor") | refactoring (short form) |
| en | `implementation` | ("role", "implement") | implementation |
| en | `verification` | ("role", "verify") | verification |
| en | `review` | ("role", "review") | review |
| en | `reviews` | ("role", "review") | reviews |
| en | `generation` | ("role", "generate") | generation |
| en | `reading` | ("role", "read") | reading |
| en | `attack` | ("kind", "attack") | attack |
| en | `attacks` | ("kind", "attack") | attacks |
| en | `test` | ("kind", "test_authoring") | a test |
| en | `tests` | ("kind", "test_authoring") | tests |
| en | `feature` | ("kind", "feature") | a feature |
| en | `features` | ("kind", "feature") | features |
| en | `new feature` | ("kind", "feature") | a new feature |
| en | `new features` | ("kind", "feature") | new features |
| en | `fix` | ("kind", "small_fix") | a fix |
| en | `fixes` | ("kind", "small_fix") | fixes |
| en | `refactor` | ("kind", "large_refactor") | a refactor |
| en | `refactors` | ("kind", "large_refactor") | refactors |
| en | `refactoring` | ("kind", "large_refactor") | refactoring |
| en | `bulk generation` | ("kind", "bulk_generation") | bulk generation |

#### `SIZE_TERMS`

| lang | entry | value | reason |
|---|---|---|---|
| ja | `大きな` | large | big |
| ja | `大きい` | large | big |
| ja | `大規模な` | large | big |
| ja | `小さな` | small | small |
| ja | `小さい` | small | small |
| ja | `小規模な` | small | small |
| ja | `中規模な` | medium | middle-sized |
| en | `large` | large | big |
| en | `big` | large | big |
| en | `small` | small | small |
| en | `tiny` | small | small |
| en | `minor` | small | small |
| en | `medium` | medium | middle-sized |

#### `IDENTITY_TERMS`

| lang | entry | value | reason |
|---|---|---|---|
| ja | `同じ` | same | the same |
| ja | `同一` | same | the same |
| ja | `別` | different | another / different |
| ja | `異なる` | different | another / different |
| en | `same` | same | the same |
| en | `different` | different | different |
| en | `separate` | different | different |

#### `LINEAGE_HEADS`

| lang | entry | value | reason |
|---|---|---|---|
| ja | `会社` | organisation | company / series / lineage |
| ja | `系列` | lineage | company / series / lineage |
| ja | `系統` | lineage | company / series / lineage |
| ja | `ベンダー` | organisation | vendor / lab |
| ja | `ラボ` | organisation | vendor / lab |
| en | `company` | organisation | company / family |
| en | `family` | lineage | company / family |
| en | `lineage` | lineage | company / family |
| en | `lab` | organisation | lab / vendor |
| en | `vendor` | organisation | lab / vendor |
| en | `provider` | organisation | lab / vendor |

#### `ROLE_NOUNS`

| lang | entry | value | reason |
|---|---|---|---|
| ja | `作った者` | implement |  |
| ja | `実装した者` | implement |  |
| ja | `確かめる者` | verify |  |
| ja | `検証する者` | verify |  |
| en | `implementer` | implement |  |
| en | `verifier` | verify |  |
| en | `reviewer` | review |  |

#### 集合の定数（項目は全部ここにある）

| 定数 | 項目 | 理由 |
|---|---|---|
| `HUMAN_TERMS` | ja: `人` `人間` `私` `自分` `人手`／en: `human` `a human` `i` `me` `a person` `people` | 文の主体が人間（エージェントではない）であることを言う語。仕事の割り当て先が人間なら `HUMAN` |
| `RESIDUAL_TERMS` | ja: `それ以外` `それ以外の仕事` `それ以外のもの` `上記以外` `どれにも当てはまらない仕事`／en: `anything else` `everything else` `otherwise` `any other job` `any other work` `the rest` | 「残り全部」を範囲にする語。経路づけ器の `NOT_COVERED` だけを置き換える |
| `OVERRIDE_MARKERS` | `追記` `追伸` `訂正` `更新` `p.s.` `ps` `update` `edit` `correction` `addendum` | 行頭のラベルとして「これは前に言ったことを変える」を言う語（語全体の一致だけ） |
| `ADDITION_LABELS` | `追記` `追伸` `p.s.` `ps` `addendum`（`OVERRIDE_MARKERS` の部分集合。W5-b で足した） | 行頭のラベルのうち「前の言明に **足す**」を言う語。この印の行は、その文に `REPLACEMENT_MARKERS` の語があるときだけ前の関係を置き換える。印が無ければ両方を残し、同じ仕事に 2 人が候補になれば経路づけ器の同点の処理に任せる（A02）。`訂正` `更新` `update` `edit` `correction` は置き換えのまま |
| `REPLACEMENT_MARKERS` | ja: `やっぱり` `ではなく`／en: `instead` `replace`（W5-b で足した） | 文が「前の言明の代わり」を言う語。日本語は NFKC の文の部分文字列、英語は小文字化した語全体との一致。`ADDITION_LABELS` の行でだけ使う |
| `ANAPHORS` | ja: `前者` `後者` `それ` `これ` `あれ` `彼` `彼女` `同上` `上記` `そちら` `こちら`／en: `the former` `the latter` `it` `they` `them` `he` `she` `this` `that` `former` `latter` `the same one` | 先行詞を指す語。先行詞は読まないので呼び名として受けない（`NAME_UNRESOLVED`） |
| `GENERIC_OBJECTS` | ja: `コード` `作業` `仕事` `もの` `ファイル` `変更`／en: `code` `work` `job` `task` `file` `files` `change` `changes` | 仕事を言う動詞（確かめる・review など）の目的語として何も足さない語 |
| `HONORIFICS` | `さん` `氏` `君` `様` | 呼びかけの敬称。敬称つきの語は呼び名として受けない |
| `EN_DETERMINERS` | `the` `a` `an` `this` `that` `these` `those` `my` `our` | 英語で限定詞から始まる句は説明であって呼び名でない |
| `NON_NAME_POS` | `形容詞` `連体詞` `動詞` `助詞` `助動詞` `副詞` `接続詞` `代名詞` `感動詞` | 形態素の品詞がこれのどれかを含む句は素の名前でない（`重い方` `東社のモデル`）。架空の呼び名の品詞は当てにならないので、呼び名かどうかの判定には使わず、説明的な句を止めるためだけに使う |
| `SENTENCE_ENDS` | `。` `．` `！` `？` `!` `?`（と、直後が空白か行末の `.`） | 文末記号 |
| `CLOSERS` | `」` `』` `）` `)` `"` `'` | 文末記号の直後にあって文に残る閉じ記号 |
| `LIST_MARKERS` | `-` `*` `・` `•` `●` `○` | 箇条書きの記号 |
| `MARKUP_CHARS` | `-` `=` `_` `|` `:` `*` `#` `─` `—` `―` `~` `+` | これと空白だけの行は記号だけの行 |

`CONSTANT_NAMES` の 19 個（上の表と集合）が凍結の対象。（W5-b: `ADDITION_LABELS` と `REPLACEMENT_MARKERS` を足して 21 個。7 章に全件と理由を書いた。）

## 7. 定数の変更記録

凍結（ハッシュと日時は「測定結果」の区間）のあとに足した・変えた項目は、日時・項目・理由をここに全件書く。

**2026-10-03 の時点で凍結のあとに足した項目: なし**（最終のハッシュが凍結のハッシュと一致することを `artifacts/w2-h2/constants_final.txt` に残した）。

**凍結の順序についての正直な申告**（実装役の報告 `impl.r1.md` にも書いた）:
(1) 中間職の指示書は 7 章で説明文 e1〜e6 の内容を述べており、実装役は定数を書く前に e1〜e6 の本文を一度読んでいる。定数は閉じた語彙（`ROLES` / `TASK_KINDS` / `SIZES`）から選び、説明文の語に合わせて足してはいないが、
`リファクタリング` `新機能` `大量の生成` などの語は語彙の名前と説明文の両方に出る。中間職の指示書 2.3 がこれらの句を例に出していたことも、実装役だけの責ではない形で記しておく。
(2) 定数の凍結（12:46:15）のあと、検査データの task と期待を書く前に、実装役は e1〜e6 に 1 つの汎用の task を流して全部が棄権することを見た（棄権の型と理由は見たが、task の期待はそのあとで書き、出力に合わせていない）。
したがって凍結が保証するのは「task（期待）を書く前、かつ入口をデータに通す前に定数が決まっていた」ことだけで、「説明文を読む前に定数が決まっていた」ことではない。

**e1〜e6 の語・句そのものである定数の項目（全件。`tests/routing_from_text/constants_in_data.py` の出力 `artifacts/w2-h2/constants_in_data.json`。`test_M4_*` が docs のこの一覧と機械で突き合わせる）**
照合は、日本語の項目は NFKC の本文の部分文字列か語の辞書形（`動かさない` に `動かす`）、英語の項目は語・句全体（`-s -es -ed -ing -ies` の活用を許す）。形の表（`SENTENCE_ENDS` `CLOSERS` `LIST_MARKERS` `MARKUP_CHARS`）と品詞名（`NON_NAME_POS`）は話題の語でないので除く。
項目は閉じた語彙の意味と 1 対 1 に言えるものだけを選んだ結果、語彙の名前として自然な語が説明文にも出ている。次の項目が該当する（`lang:項目`）。
- `PREDICATE_CLASSES`: `en:answer`、`en:be`、`en:call`、`en:check`、`en:do`、`en:hold`、`en:implement`、`en:read`、`en:review`、`en:run`、`en:verify`、`en:write`、`ja:だ`、`ja:やる`、`ja:任せる`、`ja:作る`、`ja:優先する`、`ja:動かす`、`ja:呼ぶ`、`ja:回す`、`ja:待つ`、`ja:書く`、`ja:確かめる`、`ja:答える`、`ja:読む`、`ja:頼む`
- `VERB_WORK`: `en:answer`、`en:check`、`en:implement`、`en:read`、`en:review`、`en:verify`、`en:write`、`ja:作る`、`ja:書く`、`ja:確かめる`、`ja:答える`、`ja:読む`
- `WORK_TERMS`: `en:bulk generation`、`en:feature`、`en:features`、`en:fix`、`en:fixes`、`en:generation`、`en:implementation`、`en:reading`、`en:refactor`、`en:refactors`、`en:review`、`en:reviews`、`en:test`、`en:tests`、`en:verification`、`ja:テスト`、`ja:リファクタ`、`ja:リファクタリング`、`ja:レビュー`、`ja:修正`、`ja:実装`、`ja:攻撃`、`ja:新機能`、`ja:検証`、`ja:生成`、`ja:読み込み`
- `SIZE_TERMS`: `en:big`、`en:large`、`en:small`、`ja:大きな`、`ja:小さい`、`ja:小さな`
- `IDENTITY_TERMS`: `en:different`、`en:same`、`ja:別`、`ja:同じ`
- `LINEAGE_HEADS`: `en:family`、`en:lab`、`ja:会社`、`ja:系列`
- `ROLE_NOUNS`: `ja:作った者`、`ja:確かめる者`
- `HUMAN_TERMS`: `en:i`、`ja:人`、`ja:人間`
- `RESIDUAL_TERMS`: `ja:どれにも当てはまらない仕事`
- `OVERRIDE_MARKERS`: `en:p.s.`、`en:update`、`ja:追記`
- `ADDITION_LABELS`: `en:p.s.`、`ja:追記`
- `REPLACEMENT_MARKERS`: `en:instead`、`ja:ではなく`、`ja:やっぱり`
- `ANAPHORS`: `en:it`、`en:that`
- `GENERIC_OBJECTS`: `en:change`、`en:code`、`en:file`、`en:files`、`en:job`、`en:work`、`ja:もの`、`ja:コード`、`ja:ファイル`、`ja:仕事`、`ja:変更`
- `EN_DETERMINERS`: `en:a`、`en:our`、`en:that`、`en:the`

中間職がレビューで挙げた 6 つ（`作った者` `確かめる者` `どれにも当てはまらない仕事` `系列` `動かす` `hold`）はすべてこの一覧に含まれる。r1・r2（読解器が読める形の説明文）に現れる項目は `constants_in_data.json` の `r1-r2` にある。

**第 2 ラウンド（レビュー第 1 ラウンドへの対応）で足した・変えた定数の項目: なし**（ハッシュは凍結と同じ `095335d5…870a`。`artifacts/w2-h2/constants_final.txt`）。
第 2 ラウンドで足したのは定数でない処理だけである（コピュラの割れる読み・複数語の呼び名・時制・上書きの範囲。判断 D13〜D16）。

**W5-b（2026-10-03）で凍結のあとに足した定数の項目（全件）**: `ADDITION_LABELS` = `追記` `追伸` `p.s.` `ps` `addendum`（`OVERRIDE_MARKERS` の部分集合なので、新しい語は 0）、`REPLACEMENT_MARKERS` = ja `やっぱり` `ではなく`、en `instead` `replace`。
理由: 攻撃役の反例 `Addendum:`（追記は足すのが既定で、置き換えは明示の標識があるときだけのはず）を直すため。`CONSTANT_NAMES` は 19 個から 21 個になり、凍結のハッシュの対象も 21 個になった（19 個のハッシュ `095335d5…870a` は凍結の記録として残す）。
e1〜e6 の語である項目は上の一覧に足した（`ADDITION_LABELS` `REPLACEMENT_MARKERS`）。**この 2 つの表の語は、チケットの文言（「やっぱり」「〜ではなく」「instead」「replace」の 4 語。チケットが挙げている）から決めた。** 実装役は説明文 e4 の本文を直接は読んでおらず、指示書に引かれた 1 文（`追記（翌日）：やっぱり…コマではなくホムラにする。`）だけを見た。e1〜e6 に出る語であることは、上の一覧のとおり `constants_in_data.py` の出力で後から確かめた。

## 8. 呼び名と別名

- 呼び名は、経路の類の十字の agent の腕（`ASSIGN` では recipient）と、`INDEPENDENCE` / `ALIAS` / `COMPARISON` / `COMPARISON_ONLY` の腕の充填物から集める。照合は NFKC＋大小文字無視。
- 出力の呼び名は **説明文に最初に現れた表記**（単位の番号、同じ単位の中では腕を集めた順）。別名の表は、`ALIAS`（`呼ぶ`・`call` の文だけ。コピュラは別名と取らない）の推移閉包で、各クラスの最初の呼び名が記録の ID になる。
  別名の対応は出力の `records.aliases` に残る。task の `already_used` / `running` の名前も同じ表で最初の呼び名に直す。表（エージェントの記録）に無い名前なら `ABSTAINED`（`TASK_NAME_UNKNOWN`）。
- 次のものは呼び名として受けず、その単位を止める（`NAME_UNRESOLVED`）: `ANAPHORS` の語、形態素の先頭が形容詞・連体詞の句（`重い方` `小さい子`）、助詞などを含む句（`東社のモデル`）、英語で限定詞から始まる句（`the quiet one`）、敬称つきの語、仕事の語・人の語そのもの。
  別名を読めないまま別のエージェントを作ると呼び名が違って誤って振るため（J10）。**「大きい方」「the slow one」のように、それ自体が最初の呼び名である場合も棄権になる**（既知の制限）。
- **英語の呼び名は 1 語**。読解器は副詞を充填物に混ぜることがある（`Rook usually reviews the code.` の agent が `Rook usually`）。品詞が分からないので、2 語以上で `and` で割れないものは `NAME_UNRESOLVED`（`MULTI_WORD_NAME:<句>`）で止める。複数語の固有名も止まる（既知の制限）。
- **コピュラ「X は Y だ」で X も Y も呼び名のとき**は別名にしない（`COPULA_ALIAS_OR_PREDICATION`、`AMBIGUOUS_RELATION`）。「ハルは東社だ」「セキは東社だ」を別名と取ると、推移閉包でハルとセキが 1 体に併合され、別のエージェントに振る。別名は「ルナをクイルと呼ぶ」のような `呼ぶ` の文だけから作る。
- 並列（`AとB`）は形態素の助詞 `と` / 英語の `and` で切る。`AとB` が 2 名として意味を持つのは `INDEPENDENCE` の entity だけで、ほかの腕に並列があれば `UNREPRESENTABLE`（`PARALLEL_NAMES`）。

## 9. 記録の作り方と `constructed`

- `AgentRecord`: `id` = 最初の呼び名、`adapter = "fake"`、`roles` / `kinds` は「だけ・only」の量化（`quantifiers` の `only` が仕事の腕にかかる）で言われたときだけ、`lineage` は **常に `None`**（名札は producer が宣言した分割で、
  自由文の producer は宣言できない。同じ会社だと言われた 2 体は `same` の関係にし、違う文字列の会社名からは何も作らない）、`model` / `effort` / `note` は `None`、`concurrency` は `QUANTITY` からだけ、
  `basis = Basis.text(説明文のパス, [そのエージェントについて言った文...])`。
- `RoutingRule`: `id` は producer が付ける ASCII（`T<単位番号3桁>_<連番>`）、`reason = None`、`independent_of` は **一切作らない**（検証と実装の独立は経路づけ器の既定 R3、それ以外は後段の制約）、`basis` は根拠の文。
  同じ範囲・同じ呼び名・同じ受け皿かどうかの規則は 1 本にまとめ、根拠の文を足す。条件が `role=` だけの規則だけが `fallback=True`（人間の無条件の割り当て）。
- `RoutingPrecedence` / `LineageRelation` も `Basis.text`。同じ組・同じ関係の複数の文は 1 つの記録に根拠の文を足す。
- **作った値の申告**: `adapter = "fake"` は人間が言った値ではない（記録層が必須にしている）。出力の `records.constructed` に `{"agent", "field": "adapter", "value": "fake", "reason": "ADAPTER_NOT_STATED_ROUTE_ONLY"}` を全エージェント分書く。
  `fake` は起動されない（この入口は起動しない。指揮者は fake の検証役を起動前に拒否する）。
- 受け皿は作り足さない。無条件の割り当てが同じ役割に 2 つ → 記録層の `DUPLICATE_FALLBACK` でそのまま棄権（順序を作って 1 つにまとめない）。条件つきの割り当てしかない役割 → `MISSING_ROLE_DEFAULT` でそのまま棄権。
  役割なしの規則 2 本なら受け皿は要らず、同点は経路づけ器の `TIE` になる。
- 表は **必ず `build_routing_table`** で作る（`RoutingTable(` の直接生成は無い）。記録層の拒否は `RECORD_REFUSED`（`detail` に記録層の `code`）。

## 10. 門と棄権の型

単位の状態（`UNIT_STATUSES`。閉じた一覧）:

| 状態 | 意味 | 門 |
|---|---|---|
| `MAPPED` | 関係に写した | 通す |
| `COMPARISON_ONLY` | 経路の類でない比較（記録にしない） | 通す |
| `UNREAD` | 読解器が棄権・拒否・例外（`READER_ERROR:<type>`）。読解器の理由をそのまま写す | 止める |
| `PREDICATE_CLASS_UNKNOWN` | 述語が類の表に無い | 止める |
| `WORK_TERM_UNKNOWN` | 仕事の語が表に引けない | 止める |
| `NAME_UNRESOLVED` | 呼び名として受けない句 | 止める |
| `AMBIGUOUS_RELATION` | 割れる読み（別の・コピュラの別名か述定か・優先の写し方・上書きの一部の重なり・種類も呼び名も違う上書き・`ARM_TIE`）。両方の読みを保持し記録は作らない | 止める |
| `CONTRADICTION` | 同じ範囲で同じ呼び名が「やる」と「やらない」、同じ者の並行数・「だけ」が食い違う | 止める |
| `UNREPRESENTABLE` | 記録の欄に無い（触るファイル・ファイル数・1 日の回数・時・場所・態・時制（過去など）・節の関係・使わなかった腕・量化・モダリティ） | 止める |

`MAPPED` と `COMPARISON_ONLY` 以外の単位が 1 つでもあれば、**どの仕事も** `decision: undecided`・`undecided_reason: ABSTAINED`・`abstention.type: INCOMPLETE_READING`
（止めた単位の一覧と状態別の件数つき）。単位が 0 個（空・記号だけ）なら `NO_CONTENT`。この場合も、読めた単位から作った関係と記録（記録層を通るなら表も）は出力に載せる。
**経路づけ器は呼ばない**（`router: null`）。呼んだ結果を出すと、それが答えに見えるから。`undecided_reason` の `ABSTAINED` はチケットの 5 値に足した 6 つ目で、
「説明が扱っていない（`NOT_COVERED`）」と「読めなかったので分からない」を混ぜないため（J2）。

棄権の型（`ABSTENTION_TYPES`。閉じた一覧）: `INCOMPLETE_READING` `NO_CONTENT` `RECORD_REFUSED` `TASK_NAME_UNKNOWN` `PROHIBITION_VETO` `INDEPENDENCE_VETO` `CONSTRAINT_CONFLICT` `ROUTER_UNEXPECTED`。

## 11. 経路づけの理由の写し

| 経路づけ器 | 出力 `undecided_reason` |
|---|---|
| `ROLE_NOT_ROUTABLE`（規則が無い） | `NOT_COVERED` |
| `NO_VIABLE_CANDIDATE`（全員除外） | `ALL_EXCLUDED` |
| `TESTIMONY_UNAVAILABLE`（頭が 2 体以上残り、優先順位でも決まらない。証言者を渡さない） | `TIE` |
| それ以外の `TESTIMONY_*` | 起きないはず。起きたら `ABSTAINED`（`ROUTER_UNEXPECTED`） |
| （経路づけ器の外）人がやる・待つ | `HUMAN` / `WAIT`（12 章の後段の制約） |

要求は `RoutingRequest(job_id="route-from-text", role, kind, size, used_agents={役割: (最初の呼び名, ...)}, in_use={最初の呼び名: 数})`。`used_lineages` は渡さない。`route(table, request)` を `chooser_factory` なしで呼ぶ。

## 12. 後段の制約（`CONSTRAINT_KINDS`）

記録の型に否定・人・待ちの記録が無く、経路づけ器は変えないので、次の 4 種を経路づけの後で適用する。**決定を「振らない」に変えることしかできない**（振り先を変えない・新しく振らない。振り直しは第二の経路づけ器になるので作らない）。

- `prohibit(A, 範囲)`: 決まった呼び名が A で仕事が範囲に入る → `ABSTAINED`（`PROHIBITION_VETO`）。経路づけ器が A を外したら誰に行ったかは分からないので次の候補に振り直さない。
- `human(範囲)` / `wait(範囲)`: 仕事が範囲に入る → `HUMAN` / `WAIT`（経路づけ器の結果より優先。人間がそう書いているため）。両方当たれば `ABSTAINED`（`CONSTRAINT_CONFLICT`）。範囲が `RESIDUAL` なら、経路づけ器が `NOT_COVERED` のときだけ当たる。
- `independent(役割 X, 役割 Y)`（実装と検証の組以外）: X（か Y）の仕事に決まった呼び名と、もう片方の役割の `already_used` の各呼び名の `lineage_relation` が `distinct` でなければ `ABSTAINED`（`INDEPENDENCE_VETO`）。
- 範囲の照合は `role` / `kind` / `size` の閉じた値の一致だけ（範囲の欄が無いものは「どれでも」）。
- `tests/test_routing_from_text.py::test_constraint_brute_force_*` が、7 つの制約の全部分集合（128 通り）× 7 種の仕事で「undecided が route にならない」「route の呼び名が別の呼び名にならない」を固定している。

## 13. 出力の形

標準出力 1 行（キーの並びは固定、`ensure_ascii=False`、`sort_keys` は使わない）。

```
{"schema": "verantyx.routing_from_text/1", "decision": "route"|"undecided", "agent": "<最初の呼び名>"|null,
 "undecided_reason": "NOT_COVERED"|"TIE"|"ALL_EXCLUDED"|"WAIT"|"HUMAN"|"ABSTAINED"|null,
 "abstention": null|{"type", "detail", "units": [{"index","status","text","reasons"}], "by_status": {...}},
 "basis_kind": "explicit"|"comparison"|"negation"|"condition"|"independence"|"precedence"|"quantity"|"combination"|"silence"|null,
 "evidence": ["<原文の文>", ...], "decided_by": "rule:..."|"precedence"|"router:<UNDECIDED_REASON>"|"constraint:<種類>"|"gate:<ABSTENTION_TYPE>",
 "records": {"agents", "rules", "precedence", "lineage_relations", "aliases", "constraints", "constructed", "table": "BUILT"|"REFUSED:<code>"},
 "relations": [...], "reading": {"units", "skipped_markup", "by_status", "auto_resolved", "lookup", "addition_labels_kept_as_addition", "common_noun_check": {"lookup", "checked", "not_checked", "flagged", "introduced_by_naming"}},
 "router": <RoutingDecision.ledger_fields()>|null, "ignored_fields": [...], "task": {...}}
```

- `evidence`: route のときは、決めた規則（と使った優先順位）の根拠の文。`TIE` のときは当てはまった規則の根拠の文。`HUMAN` / `WAIT` / 棄権の型のときは、その制約の根拠の文。門で止めたときは止めた単位の原文。
- `relations`: すべての関係（`held` = 割れた読み、`superseded_by` = 上書きされた先、`represented_by` = 経路づけ器の既定が持つ関係）。
- `reading.lookup`: `stub-no-placement/1`（粗い配置が未統合なので常にスタブ）。
- **`basis_kind`**（報告用。B6 の採点は `decision` と `agent` だけ）の決め方、上から順に最初に当たったもの:
  route: 優先順位の段 → `precedence`／根拠の文が 2 つ以上 → `combination`／除外に `SAME_LINEAGE` `LINEAGE_UNDECLARED` `PRIOR_ROLE_UNUSED` があるか独立が判定された → `independence`／除外に `CONCURRENCY_*` → `quantity`／比較から読んだ規則 → `comparison`／`kind=` か `size=` の条件の規則 → `condition`／それ以外 → `explicit`。
  undecided: `NOT_COVERED` → `silence`／`TIE` → `precedence`／`ALL_EXCLUDED` → 除外の理由で `independence` か `quantity`、なければ `silence`／`WAIT` `HUMAN` → `explicit`／`ABSTAINED` → `null`。
  （`negation` は route にも undecided にも当てはまる順序を置かなかったため、この版では出力されない。値としては閉じた一覧に残してある。）
- 集合は並べてから出す。時刻・乱数・`id()`・辞書の挿入順に頼る並びを出さない。`PYTHONHASHSEED` を変えても同じバイト列（`tests/test_routing_from_text_entry.py`）。

## 14. task と未使用の欄

- `role` `kind` `size` は必須（語彙外・欠けは終了コード 2 と `{"error": "BAD_TASK", ...}`。決定ではない）。`already_used` は `{役割: 呼び名 | [呼び名...]}`、`running` は `{呼び名: 数}`（呼び名の配列・呼び名 1 つも受ける）。省略可。
- `touches` と将来の欄 `used_today` `files` `date`（`IGNORED_FIELDS`）は、受け取って **使わず**、出力の `ignored_fields` に値つきで `NOT_USED_BY_ROUTER` として残す。知らない欄は `UNKNOWN_TASK_FIELD`。
  説明文が `touches` や日付・ファイル数で分岐していれば、その単位は `UNREPRESENTABLE` で門が止めるので、無視して誤って振ることは無い（J14）。
- `--task` は JSON の文字列。JSON として読めず、既存のファイルのパスなら、そのファイルを JSON として読む。説明文のファイルが無い・UTF-8 でない → 終了コード 2 と `{"error": "BAD_EXPLANATION", ...}`。
- 決定でも棄権でも終了コードは 0。


## 15. 測定結果

数値はすべて下の区間にある（`tests/routing_from_text/recompute.py --check` が `artifacts/w2-h2/` から同じ文字列を作れることを確かめる）。区間の外には数値を書かない。

基線との差（「基線にない失敗」）は、全体試験の失敗の一覧と基線（`/Users/motonisihikoudai/Projects/vera-impl/baselines/dev_e96a0cb_failures.txt`）を **両方とも `LC_ALL=C sort` してから `comm -13`** で取った集合の差
（`artifacts/w2-h2/after_failures.txt` `baseline_sorted.txt` `new_failures.txt`）。第 1 ラウンドは並べ方（ロケール）の違う 2 ファイルを `comm` に渡したため、基線にある 1 件が見かけの差として混ざっていた。
差の 2 件は基点 `e96a0cb` を `git archive` で別の場所に書き出した状態でも落ちる（`artifacts/w2-h2/known_two_failures_on_clean_base_export.txt`）。

<!-- recompute:begin -->
### 定数の表の凍結（出典: artifacts/w2-h2/constants_frozen.txt）

凍結の日時: 2026-10-03 12:46:15 +0900
sha256: `095335d57a02a0ee7d3c3db5df9d889fa7fc2fcd4a2f4f63c732c5b4056f870a`
表の項目数: sizes: {'PREDICATE_CLASSES': 40, 'VERB_WORK': 14, 'WORK_TERMS': 33, 'SIZE_TERMS': 13, 'IDENTITY_TERMS': 7, 'LINEAGE_HEADS': 11, 'ROLE_NOUNS': 7, 'HUMAN_TERMS': 2, 'RESIDUAL_TERMS': 2, 'OVERRIDE_MARKERS': 10, 'ANAPHORS': 2, 'GENERIC_OBJECTS': 2, 'HONORIFICS': 4, 'EN_DETERMINERS': 9, 'NON_NAME_POS': 9, 'SENTENCE_ENDS': 6, 'CLOSERS': 6, 'LIST_MARKERS': 6, 'MARKUP_CHARS': 12}

検査データの最初の実行の日時（出典: artifacts/w2-h2/first_run_at.txt）: 2026-10-03 12:53:17 +0900

### 自作の検査データ（本体: e1〜e6）（出典: artifacts/w2-h2/data_run/summary.json）

問い 62（実行の失敗 0）。

|  | 問い | 正しく振った | 棄権した | 別の呼び名に振った | undecided と答えた | 呼び名を返した |
|---|---|---|---|---|---|---|
| route が正解 | 43 | 0 | 43 | 0 | - | - |
| undecided が正解 | 19 | - | - | - | 19 | 0 |

誤って振った数（undecided が正解で呼び名を返した数 ＋ route が正解で別の呼び名を返した数）: **0**
正答の合計: 19 / 62（常に棄権すれば 19）
`undecided_reason` の分布: {"ABSTAINED": 62}
`abstention.type` の分布: {"INCOMPLETE_READING": 62}
`basis_kind` の分布: {"None": 62}

| 説明文 | 単位 | 読めて写せた単位 | 状態の内訳 | 問い |
|---|---|---|---|---|
| e1 | 9 | 0 | UNREAD 9 | 10 |
| e2 | 13 | 0 | UNREAD 13 | 11 |
| e3 | 10 | 0 | UNREAD 10 | 10 |
| e4 | 13 | 0 | UNREAD 13 | 10 |
| e5 | 10 | 1 | MAPPED 1, UNREAD 9 | 10 |
| e6 | 10 | 0 | UNREAD 10 | 11 |

### 読解器が読める形の説明文（reader_shaped: r1・r2。本体の数とは別）（出典: artifacts/w2-h2/data_run_reader_shaped/summary.json）

問い 16（実行の失敗 0）。

|  | 問い | 正しく振った | 棄権した | 別の呼び名に振った | undecided と答えた | 呼び名を返した |
|---|---|---|---|---|---|---|
| route が正解 | 11 | 6 | 5 | 0 | - | - |
| undecided が正解 | 5 | - | - | - | 5 | 0 |

誤って振った数（undecided が正解で呼び名を返した数 ＋ route が正解で別の呼び名を返した数）: **0**
正答の合計: 11 / 16（常に棄権すれば 5）
`undecided_reason` の分布: {"ALL_EXCLUDED": 5, "NOT_COVERED": 5, "None": 6}
`abstention.type` の分布: {"None": 16}
`basis_kind` の分布: {"condition": 2, "explicit": 4, "independence": 5, "silence": 5}

| 説明文 | 単位 | 読めて写せた単位 | 状態の内訳 | 問い |
|---|---|---|---|---|
| r1 | 8 | 8 | MAPPED 7, COMPARISON_ONLY 1 | 8 |
| r2 | 6 | 6 | MAPPED 6 | 8 |

### 中間職の task（本体 e1〜e6。レビュー第 1 ラウンドで中間職が書いて凍結）（出典: artifacts/w2-h2/data_run_mid/summary.json）

問い 56（実行の失敗 0）。

|  | 問い | 正しく振った | 棄権した | 別の呼び名に振った | undecided と答えた | 呼び名を返した |
|---|---|---|---|---|---|---|
| route が正解 | 40 | 0 | 40 | 0 | - | - |
| undecided が正解 | 16 | - | - | - | 16 | 0 |

誤って振った数（undecided が正解で呼び名を返した数 ＋ route が正解で別の呼び名を返した数）: **0**
正答の合計: 16 / 56（常に棄権すれば 16）
`undecided_reason` の分布: {"ABSTAINED": 56}
`abstention.type` の分布: {"INCOMPLETE_READING": 56}
`basis_kind` の分布: {"None": 56}

| 説明文 | 単位 | 読めて写せた単位 | 状態の内訳 | 問い |
|---|---|---|---|---|
| e1 | 9 | 0 | UNREAD 9 | 9 |
| e2 | 13 | 0 | UNREAD 13 | 9 |
| e3 | 10 | 0 | UNREAD 10 | 10 |
| e4 | 13 | 0 | UNREAD 13 | 9 |
| e5 | 10 | 1 | MAPPED 1, UNREAD 9 | 9 |
| e6 | 10 | 0 | UNREAD 10 | 10 |

### 中間職の task（reader_shaped: r1・r2）（出典: artifacts/w2-h2/data_run_mid_reader_shaped/summary.json）

問い 17（実行の失敗 0）。

|  | 問い | 正しく振った | 棄権した | 別の呼び名に振った | undecided と答えた | 呼び名を返した |
|---|---|---|---|---|---|---|
| route が正解 | 11 | 6 | 5 | 0 | - | - |
| undecided が正解 | 6 | - | - | - | 6 | 0 |

誤って振った数（undecided が正解で呼び名を返した数 ＋ route が正解で別の呼び名を返した数）: **0**
正答の合計: 12 / 17（常に棄権すれば 6）
`undecided_reason` の分布: {"ALL_EXCLUDED": 5, "NOT_COVERED": 6, "None": 6}
`abstention.type` の分布: {"None": 17}
`basis_kind` の分布: {"condition": 2, "explicit": 4, "independence": 4, "quantity": 1, "silence": 6}

| 説明文 | 単位 | 読めて写せた単位 | 状態の内訳 | 問い |
|---|---|---|---|---|
| r1 | 8 | 8 | MAPPED 7, COMPARISON_ONLY 1 | 9 |
| r2 | 6 | 6 | MAPPED 6 | 8 |

### 読めなかった単位（出典: artifacts/w2-h2/reader_gaps.json。説明 8 本の全単位）

単位 79。状態: MAPPED 14, COMPARISON_ONLY 1, UNREAD 64。
読解器の理由別（`UNREAD` の最初の理由）: UNREAD/NO_SUPPORTED_CLAUSE 25, UNREAD/EN_UNREAD 17, UNREAD/NO_PREDICATE_TOKEN 12, UNREAD/UNREAD_SPAN 5, UNREAD/UNKNOWN_PREDICATE 2, UNREAD/PREDICATE_VALUE_NOT_MAPPED 1, UNREAD/QUANTIFIER_NOT_MAPPED 1, UNREAD/UNSUPPORTED_CLAUSE 1。

### 話題専用の規則が無いことの機械の確認（出典: artifacts/w2-h2/t4_text_words.txt, t4_grep.txt）

検査データの呼び名（`check_no_text_words.py`）: 28 個、そのうち `routing_from_text.py` に現れたもの（失敗）: 0 個。説明文の語のうちモジュールに現れたもの: 112 語（うち定数の表の項目: 61 語）。

- re の使用（空であること）: 0 行
- RoutingTable の直接生成（空）: 0 行
- used_lineages（空）: 0 行

### 読み込み先（出典: artifacts/w2-h2/c0.txt）

`outside: []`

### 試験（出典: artifacts/w2-h2/pytest_unit.txt, pytest_full.txt, new_failures.txt, check_hardcode.txt）

- 新しい試験: `104 passed in 7.86s`
- 全体試験の最終行: `116 failed, 7854 passed, 37 skipped, 75 xfailed, 75 xpassed, 37 subtests passed in 220.92s (0:03:40)`
- 基線にない失敗: 2 件（FAILED tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches; FAILED tests/test_p4_abilities.py::test_speech_act_drafts_fill_new_roles_and_reread）
- 決め打ち検査（新規ファイルの全行を足して流した出力）: added lines: 1509 / PROPER/NUMERIC (must be empty): [] / ENGLISH NAMES (must be empty): []
<!-- recompute:end -->

## 16. 話題専用の規則を置かなかったことの確かめ方（T4）

次のコマンドの出力を `artifacts/w2-h2/t4_grep.txt` と `t4_text_words.txt` に残してある。

```bash
grep -nE "^import re|^from re |\bre\.(compile|search|match|fullmatch|findall|finditer|sub|split)\(" verantyx/routing_from_text.py   # 空
grep -n "RoutingTable(" verantyx/routing_from_text.py                                                                            # 空
grep -n "used_lineages" verantyx/routing_from_text.py                                                                            # 空
grep -nE "\.find\(|\.index\(|\.startswith\(|\.endswith\(|\.split\(|\.count\(|\bin (text|line|raw|sentence)\b" verantyx/routing_from_text.py   # 1 行ずつ下で説明する
python tests/routing_from_text/check_no_text_words.py        # failures が空
```

文字列の探索・分割は次の 1 か所ずつだけで、どれも説明文の語を引くものではなく、形（行・文末・ラベルの括弧・並列の語）か、読解器が返した値に対するものである。

- `text.split("\n")`・`body.startswith("#")`・`stripped.startswith("|")`（`segment_with_counts` と `_marker`）: 行に切り、見出しの `#`・表の `|` の記号を見る（形だけ）。
- `all(ch in SENTENCE_ENDS or ch in CLOSERS or ch.isspace() for ch in sentence)`（`segment_with_counts`）: 句読点だけの断片を単位にしない（文字の集合の定数との照合）。
- `body.find("）" / ")", j)`（`_override_label`）: 追記のラベルの括弧の閉じを探す（ラベルの語そのものは `OVERRIDE_MARKERS` との完全一致）。
- `word.casefold() == "and"` の並列の切り分けと `surface.split()`（`_split_parallel` と `_identity_of`）: 英語の充填物を語に切る（読解器が返した充填物に対する処理）。
- `value.partition(":")`（`RUN` 類の量化 `at_most:N`）: 読解器が返した量化の値 `at_most:2` を割る。
- `head.startswith("rule:")` と `.split(",")`（`_router_outcome`）: 経路づけ器が返した `decided_by` の文字列を割る。
- `key.split()`（`_parse_work` の英語）: 読解器が返した充填物（小文字化後）を語に切って先頭の大きさの語を見る。
- 第 2 ラウンドの追加（上の grep に新しい行は出ない）: 時制は読解器が返した `center["tense"]` を、読解器の規約の値 `"nonpast"` と比べるだけ（`docs/READING_CONVENTIONS.md` §5。説明文の語ではない）。英語の呼び名が 1 語かどうかは、`_split_parallel` が切った語の個数（`len(tokens) > 1`）で、語の中身は見ない。

`check_no_text_words.py` は、検査データの全ての呼び名（`items.jsonl` の `agent` / `wrong_agents` と task の `already_used` / `running` の名前、別名を含む）が `routing_from_text.py` に 1 つも現れないこと（`failures` が空）と、
説明文の語（fugashi の名詞・動詞の基本形、英語の 3 字以上の語）のうちモジュールに現れるものの一覧を出す。一覧の語は、定数の表の項目なら 6 章に理由があり、そうでなければモジュールの説明文（docstring・コメント）に偶然現れた語である。
中間職は T4 のためにモジュールの全行を読む。

## 17. 隠しバンク B6 を流すとき（監査役向け。T5）

実装役は隠しバンクを指して流していない。同じ道具で次のように流せる（`--out` は `--bank` の下を指せない。指すと終了コード 2）。

```bash
cd <作業ツリー> && PYTHONPATH=<作業ツリー> PYTHONDONTWRITEBYTECODE=1 python tests/routing_from_text/run_bank.py \
  --bank <hidden>/banks/B6_routing/v2 --items <hidden>/banks/B6_routing/v2/items.jsonl --out <監査役の出力先>
```

各問いを入口のサブプロセスで流し、`<out>/runs.jsonl`（1 問 1 行）・`summary.json`・`summary.txt` を書く。誤って振った数は「undecided が正解なのに呼び名を返した数 ＋ route が正解なのに別の呼び名を返した数」。
説明文は `<bank>/explanations/<explanation_id>.md`、問いは `items.jsonl` の行（`task` に `role kind size touches already_used running` と将来の欄）。

## 18. 判断記録

### 中間職の指示書で決まっていたもの

| # | 論点 | 決定 | 理由 |
|---|---|---|---|
| J1 | 一部しか読めない説明文 | 読み切れない単位が 1 つでもあれば全部の仕事を棄権（`INCOMPLETE_READING`） | 読めない文が何を言っているかは読めない以上わからない（「ただし大きい物は人がやる」「追記: やっぱり…」）。「誤って振った数 0」を守れるのはこの門だけ。呼び名を含む文だけを見るなどの緩い門は、「検証は人がやる」（呼び名なし）で破れる |
| J2 | 読めなかったときの理由 | `undecided_reason: ABSTAINED` を足し、`abstention.type` で型を分ける | `NOT_COVERED`（説明が扱っていない）は説明文についての主張で、読めなかったときに言うと偽。不在と否定を混ぜない |
| J3 | `adapter` | `"fake"` を入れ、`records.constructed` に全件申告 | 記録層が必須にしている（変えられない）。架空の呼び名から codex / claude を引くのは作り話 |
| J4 | 系統の名札 | 付けない（`lineage=None`）。同じ会社と言われた 2 体には `same`、違う文字列からは何も作らない | 同じ説明文の中で別の言い方をした同じ会社（「北社」「北の会社」）を「別系統」にしないため |
| J5 | 受け皿 | 無条件の割り当て 1 体だけを `fallback=True` に。無い・2 つある場合は作らず記録層の拒否で棄権 | 作り話をしない |
| J6 | 記録に入らない関係 | 禁止・人がやる・待つ・検証以外の独立は、経路づけの後で「振らない」にだけ変える制約 | 記録の型に否定・人・待ちが無く、経路づけ器は変えない。振り先を変える後段は第二の経路づけ器になる |
| J7 | 検証と実装の独立 | 経路づけ器の既定 R3 が持つので記録を作らない（`represented_by: ROUTER_DEFAULT_R3`）。`independent_of` を作らない | 役割なしの規則と `independent_of` の同居による `INDEPENDENCE_CYCLE` を作らない。R3 は実装が未使用の検証を決めない（B6 で「検証は X」と書かれ実装が未使用の問いは、正解が route でも棄権になる。誤って振ることにはならない） |
| J8 | 読んだが記録にしない文 | `COMPARISON_ONLY` だけを門を止めない類にする | 状態を言う文は振り先に効くことがあるので、類の表に無い述語は止める |
| J9 | 並列と「別の」 | 並列は `と` / `and` で割る。「A と B は別の会社だ」は割れる読みとして `AMBIGUOUS_RELATION` | 「互いに別」と「2 体とも他社」の両方に読める |
| J10 | 説明的な呼び名・代名詞 | 呼び名として受けず止める | 別名を読めないまま別のエージェントを作ると呼び名違いで誤って振る |
| J11 | 定数の表 | 検査データを開く前に凍結、後で足したものは全件記録 | T4 |
| J12 | 検査データの書き手 | 説明文は中間職が書いて凍結済み、task と期待は実装役 | 書き手を分ける（オーケストレーターの注意書きは逆の分担を例示したが、説明文がすでに中間職の手で存在したので、書き手が分かれている点を満たす形で指示書に従った） |
| J13 | 数のしきい値（10 ファイルを超える） | `UNREPRESENTABLE` | 経路づけ器の `size` は許可パス数・受入条件数からの帯で、ファイル数とは別の量 |
| J14 | `touches` と将来の欄 | `ignored_fields` に型で残す | 経路づけ器に欄が無い。説明文が分岐していればその単位が止まる |
| J15 | 証言 | 使わない（`chooser_factory=None`） | 実行時 LLM は使わない |
| J16 | 上書き | 範囲が同じ関係だけを置き換え、数える。一部の重なりは割れる読み | 自動で解決したものも数えて記録する |
| J17 | 「だけ・only」 | そのときだけ `roles` / `kinds` を申告する | 言われた限定だけを記録にする |

### 実装役が決めたもの

| # | 論点 | 決定 | 理由 |
|---|---|---|---|
| D1 | `EXCEPTION` `CONDITION` `OVERRIDE` | 関係の種類にせず、前二者は範囲の狭い `SUITABILITY` / `PROHIBITION` と仕事の範囲の条件、後者は単位の旗と置き換えにした。`RELATION_KINDS` は 10 種 | 例外・条件は十字の 1 節から独立に取り出せず（「ただし」「なら」は節の間の関係）、範囲の違いで表せる |
| D2 | 読解器の `relations`（節の間の条件・理由など） | 1 つでもあれば単位は `UNREPRESENTABLE`（`READER_RELATION:<type>`）。条件節の中身を規則の条件に写すことはしない | 条件節の意味（大きさ・種類・ファイル数のどれ）を型付きで言える材料が無い。現在の読解器は複数節を実際にはほぼ作らない |
| D3 | 計画書の定数の一覧に足した表 | `VERB_WORK`（動詞が言う仕事）、`LINEAGE_HEADS`（系統の語）、`ROLE_NOUNS`（役割の名詞）、`HONORIFICS` `EN_DETERMINERS` `NON_NAME_POS`（呼び名でない句）、`CLOSERS` `MARKUP_CHARS`（形） | 計画書の `IDENTITY_TERMS` `GENERIC_OBJECTS` だけでは「同じ会社」「作った者」「確かめる→検証」「重い方」を一つの表の項目では言えない。足した表も全項目を 6 章に載せ、凍結のハッシュに含めた |
| D4 | `CREATE_VERB`（書く・write など） | 目的語が仕事の語ならその語（`テスト` → `kind=test_authoring`）、目的語が無いか汎用なら動詞の既定（`role=implement`）。動詞の役割と目的語の種類を重ねた規則（`role=implement & kind=test_authoring`）は作らない | 重ねると、実装の受け皿が無いときに `MISSING_ROLE_DEFAULT` を呼ぶ。言っていない役割を足さない |
| D5 | `basis_kind` の順序 | 優先順位の段を最初に見る（`combination` より先） | 優先順位の文は必ず 2 つ目の文になるので、`combination` が先だと `precedence` が出ない |
| D6 | 凍結のハッシュ | 正準 JSON の sha256（計画書の `repr` ではない） | `frozenset` の `repr` は `PYTHONHASHSEED` で変わる |
| D7 | 出力 `records.table` | `records` に `table`（`BUILT` か `REFUSED:<code>`）を足した | 門で止めたときも、記録層を通ったかどうかを言うため |
| D8 | `already_used` と `running` の形 | 前者は `{役割: 呼び名 | 呼び名の配列}`（それ以外は `BAD_TASK`）、後者は `{呼び名: 数}`・呼び名の配列・呼び名 1 つ | チケットが値の形だけを言っているので、書かれている形だけを受け、別の形を推測しない（隠しバンクの形が違えば `BAD_TASK` の終了コード 2 になり、誤って振ることはない） |
| D9 | `witness` | 1 行に複数の文があるとき、最初の文は行頭の記号・ラベルを含む | 計画書の「記号を外す前の行から」に従う |
| D10 | `exactly:N` | `at_most:N` と同じく並行数の上限 `N` として写す | 計画書が両方を `QUANTITY` に挙げている。「ちょうど N」は少なくとも上限が N であることを含む |
| D11 | 優先順位の写し | 優先する側・される側の呼び名が、同じ条件の非受け皿の規則を 1 本ずつ持つときだけ | 「規則どうしの組に一意に写せるとき」の実装。受け皿は優先順位に名指せない（記録層） |
| D12 | 並列の名前を持つ腕 | `INDEPENDENCE` の entity 以外では `UNREPRESENTABLE` | 「AとBがテストを書く」を 2 つの割り当てにするには、言われていない読みの選択が要る |

### 第 2 ラウンド（レビュー第 1 ラウンドへの対応）で決めたもの

| # | 論点 | 決定 | 理由 |
|---|---|---|---|
| D13 | 追記の上書きの範囲（レビューの任意の改善 1） | 範囲が同じ先のうち、種類（割り当て→割り当て、禁止→禁止）が同じか呼び名が同じものだけを置き換える。種類も呼び名も違う先が 1 つでもあれば `AMBIGUOUS_RELATION`（`OVERRIDE_OTHER_KIND_AND_NAME`） | 「追記: B もテストを書く」が足すだけの意味なら同点が正解で、「追記: B はテストを書かない」が A の割り当てを置き換えるのは明らかに意味が違う。同じ種類で呼び名の違う置き換え（「やっぱり B に」）は、置き換えの読みを残した。それは J16 の範囲の判断と同じで、足すだけの読みが正しいときは誤って振りうることを既知の制限に書いた |
| D14 | コピュラ「X は Y だ」の別名（レビュー M1） | 両方が呼び名なら `AMBIGUOUS_RELATION`（`COPULA_ALIAS_OR_PREDICATION`）。読み 2 つ（別名／述定）を `held` に残し、別名の表と記録は作らない。別名は `呼ぶ`・`call` の文だけから作る | 配置がスタブで、名前と普通名詞（会社名・チーム名）を区別できない。「ハルは東社だ」「セキは東社だ」を別名にすると推移閉包で別のエージェントが併合され、別の呼び名に振る（レビュー第 1 ラウンドで実測）。J9 と同じ扱い |
| D15 | 時制（レビュー M3） | `center["tense"]` が `nonpast` 以外なら `UNREPRESENTABLE`（`TENSE:<値>`） | 中心の欄を黙って捨てない。過去形は「前回だれがやったか」の報告で、振り分けの宣言ではない。`null`（テ形など）も宣言と言えないので止める |
| D16 | 英語の呼び名 | 1 語に限る。2 語以上で `and` で割れないものは `NAME_UNRESOLVED`（`MULTI_WORD_NAME`） | 読解器が副詞を充填物に混ぜる（`Rook usually`）と、存在しない呼び名に振る（レビュー第 1 ラウンドで実測）。品詞が分からないので語数で止める |

### W5-b（攻撃の第 2 波 A01・A02）で決めたもの

| # | 論点 | 決定 | 理由 |
|---|---|---|---|
| D17 | 普通名詞の主語（A01）の根拠 | 理由 `COMMON_NOUN_SUBJECT:<名前>:<根拠>`（単位の状態は既存の `NAME_UNRESOLVED`、単位は通らないので記録は作らず門が `INCOMPLETE_READING` で止める）。根拠は 2 つで、どちらか一方で足りる。(a) `DETERMINER:<限定詞>`: 英語の単位で、関係が使う呼び名が、単位の元の文（`Unit.text`）の中で `EN_DETERMINERS` の語の直後に出る（読解器は `The team` の `The` を落とすので元の文を見る。空白で切り前後の句読点を除き、限定詞は大小無視）。(b) `PLACEMENT_DIRECT:<型,…>`: 十字の `place`（`explain(..., lookup=…)` の配置）が `origin == direct` かつ `DECIDED` / `MULTIPLE` | 語の一覧ではなく、文の構造（限定詞）と配置の証言だけを使う。この木の既定の配置はスタブ（`NO_PLACEMENT`）なので (b) は配置がつながったときに効く（(a) がこの木の攻撃を止める）。正規表現は使わない（T4） |
| D18 | (b) で根拠にしないもの | `estimated`（構成物で証言でない）・`UNPLACED`・`UNKNOWN`・`NO_PLACEMENT`。命名の文（`呼ぶ`・`call`）の **2 つ目の名前**と、命名の文の名前は調べない | 推定は証言でない。命名の文で導入された名前は、その文によって名前になっている（`チーム` を人が `呼ぶ` と書けば、配置が `GROUP_ORG` と言っても名前） |
| D19 | 調べた数 | 出力の `reading.common_noun_check` = {`lookup`, `checked`（配置が答えた名前。重複は 1）, `not_checked`（配置が使えず調べられなかった名前）, `flagged`, `introduced_by_naming`} | 自動で棄却した件数も数える。配置が無いときに「調べて問題なかった」と見えないように、調べられなかった数を別に出す |
| D20 | 追記は足す（A02） | `ADDITION_LABELS`（`追記` `追伸` `p.s.` `ps` `addendum`）の行は、文ごとに `REPLACEMENT_MARKERS` の語があるときだけ上書き。無ければ足す（両方の関係が残り、同じ仕事に 2 人が候補になれば経路づけ器の既存の処理（同点・矛盾）に任せる）。`訂正` `更新` `update` `edit` `correction` は今までどおり置き換える | 「追記」は足すのが既定のはずで、置き換えは明示の標識があるときだけ。見えない置き換えをしない |
| D21 | 既存テスト 3 本 | `追記：` の行が標識なしで置き換わることを期待する 3 本（`test_relation_override_replaces_exactly_the_same_scope_and_counts_it` `test_relation_override_that_overlaps_only_partly_is_held_as_ambiguous` `test_D13_an_override_of_another_kind_about_another_name_is_held_not_a_replacement`）は **この変更と矛盾して落ちる**。テストには触れず、報告で宣言した（チケットの指示と既存の期待のどちらを取るかは監査役の判断） | テストの期待を弱めない |

### W5-b 第 4 ラウンド（監査役の裁定 C3、2026-10-03）

D20（追記は足す）の帰結として落ちていた既存の 3 本について、監査役は「3 本の **入力** に置き換えの標識（`やっぱり`）を足して『標識つきの置き換え』の試験として残し、同じ入力の標識なしの版を『足す（両方が記録に残る）』の新しい試験として追加する」と裁定した（名前と assert は変えない）。変えたのは入力の文字列と、読解器の表（文をそのまま鍵にした辞書）の鍵だけ。以下が **変更前と変更後の関数の全文**。

**test_relation_override_replaces_exactly_the_same_scope_and_counts_it**（変更前）

```python
def test_relation_override_replaces_exactly_the_same_scope_and_counts_it():
    text = "実装はハルに任せる。\n追記：実装はルナに任せる。\n"
    table = {"実装はハルに任せる。": OV[0][1], "実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    explained = rt.explain(text, "x.md", reader=lambda s: table[s])
    assert explained.extraction.auto_resolved == 1
    assert [r.superseded_by for r in explained.extraction.relations] == ["R002", None]
    assert [r.preference for r in explained.records.rules] == [("ルナ",)]
    result = rt.route_task(explained, task())
    assert result["agent"] == "ルナ" and result["reading"]["auto_resolved"] == 1
    assert [r["superseded_by"] for r in result["relations"]] == ["R002", None]      # the replaced relation is kept and says by what
```

**test_relation_override_replaces_exactly_the_same_scope_and_counts_it**（変更後）

```python
def test_relation_override_replaces_exactly_the_same_scope_and_counts_it():
    text = "実装はハルに任せる。\n追記：やっぱり実装はルナに任せる。\n"
    table = {"実装はハルに任せる。": OV[0][1], "やっぱり実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    explained = rt.explain(text, "x.md", reader=lambda s: table[s])
    assert explained.extraction.auto_resolved == 1
    assert [r.superseded_by for r in explained.extraction.relations] == ["R002", None]
    assert [r.preference for r in explained.records.rules] == [("ルナ",)]
    result = rt.route_task(explained, task())
    assert result["agent"] == "ルナ" and result["reading"]["auto_resolved"] == 1
    assert [r["superseded_by"] for r in result["relations"]] == ["R002", None]      # the replaced relation is kept and says by what
```

**test_relation_override_that_overlaps_only_partly_is_held_as_ambiguous**（変更前）

```python
def test_relation_override_that_overlaps_only_partly_is_held_as_ambiguous():
    table = {"大きな実装はハルに任せる。": rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな実装"})),
             "実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    # "大きな実装" is a size word before a head that is not a kind: the first sentence stops, so use a kind head instead
    table = {"大きなリファクタリングはハルに任せる。": rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きなリファクタリング"})),
             "実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    text = "大きなリファクタリングはハルに任せる。\n追記：実装はルナに任せる。\n"
    explained = rt.explain(text, "x.md", reader=lambda s: table[s])
    assert explained.extraction.units[1].status == "AMBIGUOUS_RELATION" and explained.extraction.auto_resolved == 0
    assert out_of(explained)["abstention"]["type"] == "INCOMPLETE_READING"
```

**test_relation_override_that_overlaps_only_partly_is_held_as_ambiguous**（変更後）

```python
def test_relation_override_that_overlaps_only_partly_is_held_as_ambiguous():
    table = {"大きな実装はハルに任せる。": rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな実装"})),
             "実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    # "大きな実装" is a size word before a head that is not a kind: the first sentence stops, so use a kind head instead
    table = {"大きなリファクタリングはハルに任せる。": rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きなリファクタリング"})),
             "やっぱり実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    text = "大きなリファクタリングはハルに任せる。\n追記：やっぱり実装はルナに任せる。\n"
    explained = rt.explain(text, "x.md", reader=lambda s: table[s])
    assert explained.extraction.units[1].status == "AMBIGUOUS_RELATION" and explained.extraction.auto_resolved == 0
    assert out_of(explained)["abstention"]["type"] == "INCOMPLETE_READING"
```

**test_D13_an_override_of_another_kind_about_another_name_is_held_not_a_replacement**（変更前）

```python
def test_D13_an_override_of_another_kind_about_another_name_is_held_not_a_replacement():
    ov, text = explain_lines(("ハルはテストを書く。", rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}))),
                             ("セキもテストを書く。", rd("ja", cl("書く", {"agent": "セキ", "patient": "テスト"}))))
    # the same kind (A does it -> B does it) replaces; a different kind and a different name (A does it -> B does not) is held
    table = {"ハルはテストを書く。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"})),
             "モモはテストを書かない。": rd("ja", cl("書く", {"agent": "モモ", "patient": "テスト"}, "-"))}
    explained = rt.explain("ハルはテストを書く。\n追記：モモはテストを書かない。\n", "x.md", reader=lambda sentence: table[sentence])
    unit = explained.extraction.units[1]
    assert unit.status == "AMBIGUOUS_RELATION" and unit.reasons[0].startswith("OVERRIDE_OTHER_KIND_AND_NAME:")
    assert explained.extraction.auto_resolved == 0 and out_of(explained, kind="test_authoring")["abstention"]["type"] == "INCOMPLETE_READING"
    same_name = {"ハルはテストを書く。": table["ハルはテストを書く。"],
                 "ハルはテストを書かない。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}, "-"))}
    explained = rt.explain("ハルはテストを書く。\n追記：ハルはテストを書かない。\n", "x.md", reader=lambda sentence: same_name[sentence])
    assert explained.extraction.units[1].status == "MAPPED" and explained.extraction.auto_resolved == 1
```

**test_D13_an_override_of_another_kind_about_another_name_is_held_not_a_replacement**（変更後）

```python
def test_D13_an_override_of_another_kind_about_another_name_is_held_not_a_replacement():
    ov, text = explain_lines(("ハルはテストを書く。", rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}))),
                             ("セキもテストを書く。", rd("ja", cl("書く", {"agent": "セキ", "patient": "テスト"}))))
    # the same kind (A does it -> B does it) replaces; a different kind and a different name (A does it -> B does not) is held
    table = {"ハルはテストを書く。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"})),
             "やっぱりモモはテストを書かない。": rd("ja", cl("書く", {"agent": "モモ", "patient": "テスト"}, "-"))}
    explained = rt.explain("ハルはテストを書く。\n追記：やっぱりモモはテストを書かない。\n", "x.md", reader=lambda sentence: table[sentence])
    unit = explained.extraction.units[1]
    assert unit.status == "AMBIGUOUS_RELATION" and unit.reasons[0].startswith("OVERRIDE_OTHER_KIND_AND_NAME:")
    assert explained.extraction.auto_resolved == 0 and out_of(explained, kind="test_authoring")["abstention"]["type"] == "INCOMPLETE_READING"
    same_name = {"ハルはテストを書く。": table["ハルはテストを書く。"],
                 "やっぱりハルはテストを書かない。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}, "-"))}
    explained = rt.explain("ハルはテストを書く。\n追記：やっぱりハルはテストを書かない。\n", "x.md", reader=lambda sentence: same_name[sentence])
    assert explained.extraction.units[1].status == "MAPPED" and explained.extraction.auto_resolved == 1
```

標識なしの版は `tests/test_routing_from_text_w5b.py` に新しい 3 本として足した（既存ファイルの差分を入力だけに保つため）: `test_C3_without_a_marker_relation_override_replaces_exactly_the_same_scope_and_counts_it_both_statements_stand`・`test_C3_without_a_marker_relation_override_that_overlaps_only_partly_is_held_as_ambiguous_both_declarations_stand`・`test_C3_without_a_marker_an_override_of_another_kind_about_another_name_is_held_not_a_replacement_both_statements_stand`。期待は今の木で測った挙動（出力は `artifacts/w5-b/w2h_tests.txt`）: 1 本目は単位が 2 つとも `MAPPED`・`auto_resolved == 0`・`superseded_by` が両方 `None`・規則の `preference` が `[('ハル',), ('ルナ',)]` で、`route_task` は同じ仕事に 2 体の候補なので既存の処理で `RECORD_REFUSED`／`DUPLICATE_FALLBACK` の棄権。2 本目は 2 つとも `MAPPED`（範囲の違う 2 つの宣言がどちらも残り、agent は `ルナ`）。3 本目の前半（別の名前・別の種類）は 2 つとも `MAPPED`、後半（同じ名前で否定）は 2 単位とも `CONTRADICTION`（`CONTRADICTS:R002`／`CONTRADICTS:R001`）で、置き換えではなく矛盾として残り `INCOMPLETE_READING` で棄権する。

## 19. 既知の制限

- **読解器の被覆が狭い**（0 章）。普通に書かれた説明文は、棄権の理由（`NO_SUPPORTED_CLAUSE` `EN_UNREAD` `NO_PREDICATE_TOKEN` など）の件数どおり、ほぼ全部が棄権になる。単位の数と理由は「測定結果」の区間と `artifacts/w2-h2/reader_gaps.md`。
- **受け皿の要求**: 条件つきの割り当てだけがある役割、無条件の割り当てが 2 つある役割は、記録層が拒否して棄権になる（作り足さない）。
- **R3 と未使用の実装**: 「検証は X」と書かれ、実装がまだ使われていない検証の仕事は、正解が route でも経路づけ器が決めない（`PRIOR_ROLE_UNUSED`）。誤って振ることにはならない。実装を使ったあとの検証でも、検証役と実装役の系統の関係が言われていなければ `LINEAGE_UNDECLARED`。
- **説明的な呼び名**（「重い方」「the slow one」）はそれ自体が最初の呼び名でも棄権。別名として後から出る場合も、別名の表に入らないので止まる。
- **複数語の英語の呼び名**（`Big Rook` のような固有名）は棄権（D16）。別名の取り出し元は `呼ぶ`・`call` の文だけで、コピュラ（「L は Luna だ」）の別名は読まない（D14）。
- **過去形の文**は棄権（D15）。「ハルが実装をやった」だけの説明文では、実装の仕事は決まらない（`UNREPRESENTABLE`）。未来（`Rook will review the code.`）は読解器が `nonpast` と返すので宣言として読む。
- **追記の上書き**は、同じ範囲・同じ種類の言明なら呼び名が違っても置き換える（D13）。「追記」が足すだけの意味で書かれていれば、本来は同点（undecided）が正解になる。
  （W5-b で直した: `追記` `追伸` `p.s.` `ps` `addendum` の行は、その文に `REPLACEMENT_MARKERS` の語が無ければ足す（D20）。残る穴: 標識の語は 4 つの閉じた表で、`replaced`・`rather than`・`今度は` のような言い方は標識として読まない（足す側に倒れ、2 人が候補なら同点で棄権する）。標識は文ごとに見るので、同じ行の別の文の標識は効かない。）
- **普通名詞の主語**（「チームがレビューをやる」）は、配置がスタブで名前と区別できず、`HUMAN_TERMS` の小さい閉じた表にも無ければ呼び名になる（申し送り。読解器の被覆が狭く、他の全文が読める説明文の中でしか効かない）。
  （W5-b で直した部分: 英語は単位の元の文で限定詞の直後にある名前を止める（`The team`、D17 (a)）。配置がつながれば `direct` の型を持つ語も止める（D17 (b)）。**残る穴**: 日本語には限定詞が無く、配置がスタブの間は `チーム` を止められない。配置がつながると、凍結の経路づけデータの呼び名のうち配置が `direct` と答える語（人名・地名と同じ形の呼び名）も止まりうる（`artifacts/w5-b/routing_with_placement.txt` に実測を出す。製品コードは変えずに測った）。限定詞が無い英語の普通名詞（`Reviewers review code.`）と、限定詞が名前から離れた文（`The big team ...` は複数語の名前として止まる）は D17 (a) の対象でない。）
- **名前の敬称以外の人**（「あの人」）は `HUMAN_TERMS` に無ければ呼び名として検査され、通れば呼び名になる（敬称つき・照応・説明的な句だけを止める）。
- **表と箇条書きのラベル**（`シロ：実装担当。`、表の行）は解釈しない。読解器が読めないので門が止める。
- **見出し・題名の行**（`## エージェントの分担`、`メモ（チャットから転記）`）も単位として読解器に渡るため、述語が無ければ `UNREAD` で門が止める。
- 英語は読解器が読める文の種類が少ない（`EN_UNREAD` が多い）。
- `adapter` は記録層が必須にするため `fake` を入れている（`constructed` に申告）。実行系がこの記録をそのまま起動するには、記録層で未申告を許す変更が要る。
- `negation` の `basis_kind` は出力されない（13 章）。

## 20. 申し送り

- **記録層（W2-h）へ**: `adapter` を未申告にできるようにする（`model` / `effort` と同じく起動前の `AGENT_SETTING_MISSING` に揃える）。受け皿の無い役割を言ったときの扱い、否定（禁止）・人がやる・待つの記録の型を足せば、後段の制約を記録に取り込める。
  `docs/frames/vera_project_frame.md` の注釈の追記（W2-h4 の任意の改善 4）は許可パス外なのでしていない。
- **読解器（W1-a4）へ**: 英語の充填物の境界（`Rook usually reviews the code.` の agent が副詞を含めて `Rook usually` になる。`usually` `always` `sometimes` `often` で実測。`rarely` は `EN_UNREAD`）、文の分割と部分読み、箇条書きのラベル（`名前：説明`）、コロンのスコープ、並列（`AとB` の共有）、`実装をやる` 以外の `する` 動詞（サ変の名詞＋する）、複数文の入力、比較の `dimension`。読めなかった単位の型と例は `artifacts/w2-h2/reader_gaps.md`。
- **粗い配置（W3-a2）へ**: 統合されたら、呼び名の腕の型（`PERSON` / `GROUP_ORG` 以外は棄権）に使える。今はスタブなので使わない。

## 21. 作業上の正直な記録

- 凍結の順序（7 章）、全体試験の前後の負荷、止めた実行は `impl.r1.md`（第 1 ラウンド）と `impl.r2.md`（第 2 ラウンド）に書いた。

## W5-d の事前登録: 普通名詞を呼び名にしない・置き換えの標識の後ろの「維持」
<!-- w5d-prereg:begin -->
事前登録の時刻: 2026-10-03 23:07:22 +0900（`date '+%F %T %z'` の出力）。

- **R-J1（R1）**: `_common_noun_stop` に 1 つ足す。日本語（`reading.lang == "ja"`）で、名前が命名の文で導入されていないとき: 配置の答えが使えて `origin == "direct"`・`state in ("DECIDED","MULTIPLE")` で、型のどれかが `event_cross.NOUN_TYPE_IDS`（17 型）にある → `COMMON_NOUN_SUBJECT:<名>:PLACEMENT_DIRECT:<型>`。配置の答えが使えない（答えが無い・`NO_PLACEMENT`）→ `NAME_UNVERIFIED:<名>:NO_PLACEMENT`（単位の状態は既存の `NAME_UNRESOLVED`。`UNIT_STATUSES` を増やさない）。配置が使えて UNPLACED・UNKNOWN・推定 → 今どおり名前として通す。17 型に無い型だけの direct は止めない。英語は変えない。`common_noun_check` の辞書に鍵を足さない。
- **R-J2（R2）**: 置き換えの標識の後ろの扱い（語の一覧を使わない）。標識の位置（日本語は NFKC の文で `REPLACEMENT_MARKERS["ja"]` の最初の出現、英語は語として最初の出現）の後ろを `rest` とする。(1) `rest` の先頭（空白を除く）が節の区切り、または `rest` が文末記号だけ → 置き換え（今どおり）。(2) `rest` に文末より前の節の区切りが無い → 標識が節を直接導く → 置き換え（今どおり）。(3) それ以外（標識と次の区切りの間に独立した断片 `head`）→ `head` を同じ reader で読む。読めて節がちょうど 1 つで極性が `-` → **維持**（置き換えにしない。`additions_kept` に数え、理由 `MAINTAINED_AFTER_MARKER`）。読めない・節が 0 か 2 以上・極性 `+` → `AMBIGUOUS_RELATION`（理由 `MARKER_SCOPE_UNDETERMINED:<head>`。置き換えも足しもしない）。`UnitResult.replaces` と `Extraction` の出力の鍵の並びは変えない。
- 本物の reader では `そのまま`・`変えない` などは読めないので AMBIGUOUS_RELATION に倒れる（「そのまま類」を見分ける語の一覧を作らないことの代価。既知の穴として書く）。

### 宣言する規則どうしの衝突（実装役は解かずに宣言する。判断は監査役）
チケットの規則を字面どおりに入れると、旧い振る舞いをそのまま固定した既存テストが落ちる。実装役はチケットの規則どおりに作り、テストの期待は変えず（改訂が許された 1 関数を除く）、落ちた id を全部宣言する。

| # | 衝突 | 落ちる見込みのもの |
|---|---|---|
| K1 | W3-c2「型を確かめられない充填物は候補から外す」 × 配置なしで FILLED/TIE を期待する既存テスト・攻撃の外れ | `tests/test_question_cross_observe.py` の一部、攻撃の写しの 2 件 |
| K2 | R1「配置が無い日本語の名前は命名の文で導入されたものだけ」 × 配置なし（スタブ）の名前で振る既存テスト・R2 の攻撃テスト | `tests/test_routing_from_text*.py` の多数、攻撃の写しの R2 の 1 件 |
| K3 | A1「出典の本文が渡した文書の中にある」 × 存在しない文書を渡して `family: document` を人とする既存テスト | `tests/test_basis_policy_form.py`・`tests/test_basis_policy_w5c_r3.py` の一部 |
| K4 | D1「文面が同じときだけ格上げ」 × 別の文の記録で格上げすることを固定した既存テスト（改訂許可の 2 件の外） | `tests/test_basis_policy_w5c_r3.py::test_r3_a_recorded_yes_still_lifts_a_generated_answer` |
| K5 | W3-a3 A1「枠の確認は助詞ごとの型の一致」 × 攻撃の写しの不変条件「gen_frame の格上げ語は全部 CONFIRMED」 | `tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades` |
| D1-改訂 | 許可された 2 件のうち設計上落ちる 1 件 | `tests/test_basis_policy_confirm.py::test_two_confirmed_records_with_the_same_claim_are_not_a_split`（名前不変で改訂。前後の全文は BASIS_POLICY の測定の節） |

### 受入基準の測り方（G1〜G7。測る前に固定）
- G1: 攻撃の写し 5 本（`tests/attack/w3c2`・`test_attack_w5b_wave2.py`・`test_attack_w5c_*.py` 2 本・`tests/attack/w3a3/test_attack_w3a3_r6.py`）。落ちてよいのは宣言した K1(2)・K2(1)・K5(1) の 4 id だけ。A02・R2・W3-a3 A1 は新しいテストで確かめる。
- G2: `artifacts/w5-d/scripts/run_questions_both.py`（実装役の 185 問、配置あり／なし）。誤答 0、型未確認の充填物を持つ FILLED/TIE 0。正答の減少は変更前（`artifacts/w5-d/before/q185_*.json`）との差を数で。
- G3: 経路づけの凍結 4 本（`run_bank.py`、配置なし・r7）の misroutes と、自作の合成（`artifacts/w5-d/g3_synth/`、入力と期待を先に書き sha256 を凍結）。
- G4: `artifacts/w5-d/scripts/g4_probe.py`（入力を先に凍結）。自己申告の文書・文面違いの確認記録から `ANSWER_*` が 0。対照（本当に渡した文書の文・完全一致の記録）では答えが出ること。
- G5: r7 を cache なしで 2 回作り `verify` が両方 OK、`content_sha256` が run1 = run2 = r6（`5c969d45…`）。L1〜L3・動詞 300 語を `measure_w5d.py` で r6 と r7 で測り同じ。
- G7: `pytest tests`（最後に 1 回）の失敗集合が基線 `dev_c875ed3_failures.txt` から増えない。増えた分は 1 件ずつ K1〜K5 または環境由来に当てる。当たらないものはコードを直す。
- 基線（変更前）の測定は `artifacts/w5-d/before/` に保存済み（この事前登録より前）。製品コードの差分はこの時点で空。

<!-- w5d-prereg:end -->

## W5-d の測定: 普通名詞を呼び名にしない・置き換えの標識の後ろ
<!-- w5d-measured:begin -->

測定の時刻: 2026-10-03 23:34:53 +0900。出典はすべて `artifacts/w5-d/` のファイル（下に名前を書く）。全体テスト: `pytest_full.txt` の最終行 `198 failed, 11889 passed, 45 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 341.39s (0:05:41)`。基線 `dev_c875ed3_failures.txt` に無い新しい失敗は 83 件（`new_failures.txt`）で、1 件ずつ `new_failures_explained.txt` に K1〜K5・改訂・環境由来のどれかを書いた。どれにも当たらないものは 0 件（`grep -v -E 'K[1-5]|D1-改訂|環境由来' new_failures_explained.txt` が空）。基線から直った失敗は 0 件（`fixed_failures.txt`）。

### 自由文→記録（G3）
- 経路づけの凍結 4 本（`run_bank.py`、配置なし）: `g3_noplace_*/summary.txt`。誤って振った数（misroutes）はすべて 0（変更前 `before/rb_*.summary.txt` も 0）。`items`・`items_mid` の要約は変更前と同一（説明文が reader に読めず全部 UNREAD のため）。`items_reader_shaped`・`items_mid_reader_shaped` は r1 の「読めて写せた単位」が 6 → 0（`NAME_UNRESOLVED` 6）に減った（配置なしで日本語の名前が `NAME_UNVERIFIED` で止まるため）。「正しく振れた問い」の数は 3 と 2 のまま。r7 の配置あり（`g3_r7_*/summary.txt`、`items`・`items_mid`）も misroutes 0。
- B6 の形の合成（`g3_synth/`、入力と期待は先に書いて `g3_synth_inputs.sha256` に凍結。`g3_synth_results/`）: 14 問。誤って振った数は 変更前 1（`委員会` に振った）→ 変更後・配置なし 0、普通名詞の主語に振った数 1 → 0。r7 の配置ありでは 1（変更前と同じ 1 件: r7 は `委員会` を「推定」としか答えず、推定は名前として通す規則のため）。
- 「追記」の標識の後ろ（R2）は、本物の reader では `やっぱり…` を含む文が読めない（UNREAD）ので、経路づけの凍結データでは動かない。断片を読む偽 reader のテスト（`tests/test_routing_from_text_w5d.py`）でだけ維持・未確定の経路に到達する。

### 宣言した衝突 K2（自由文→記録）の実際の失敗 id（既存 51 件と攻撃の写しの R2 の 1 件。`k2_check.txt`）
- `tests/attack/test_attack_w5b_wave2.py::test_yappari_sonomama_does_not_turn_an_addendum_into_replacement`
- `tests/test_routing_from_text.py::test_D13_an_override_of_another_kind_about_another_name_is_held_not_a_replacement`
- `tests/test_routing_from_text.py::test_M1_a_copula_between_two_names_is_ambiguous_and_makes_no_alias_and_no_merge`
- `tests/test_routing_from_text.py::test_M3_a_nonpast_centre_is_read_and_a_reading_without_a_tense_is_rejected_by_the_cross_as_unread`
- `tests/test_routing_from_text.py::test_T3_a_conditional_role_rule_without_the_roles_fallback_is_refused`
- `tests/test_routing_from_text.py::test_T3_a_role_less_conditional_rule_needs_no_fallback_and_a_size_word_before_an_unknown_head_stops`
- `tests/test_routing_from_text.py::test_T3_an_unconditional_assignment_is_the_fallback_and_nothing_else_is_made_one`
- `tests/test_routing_from_text.py::test_T3_only_says_roles_or_kinds_and_otherwise_they_stay_unsaid`
- `tests/test_routing_from_text.py::test_T3_records_are_declared_text_with_witnesses_that_are_substrings_and_say_only_what_was_said`
- `tests/test_routing_from_text.py::test_T3_the_same_content_as_a_hand_written_table_gives_the_same_decisions`
- `tests/test_routing_from_text.py::test_T3_two_unconditional_assignments_of_one_role_are_refused_by_the_record_layer_and_not_made_one`
- `tests/test_routing_from_text.py::test_constraint_human_and_wait_scopes_and_residual_and_conflict`
- `tests/test_routing_from_text.py::test_constraint_independence_veto_for_two_other_roles`
- `tests/test_routing_from_text.py::test_constraint_prohibition_veto_does_not_try_the_next_agent`
- `tests/test_routing_from_text.py::test_gate_one_unread_unit_stops_every_job_and_the_router_is_not_called`
- `tests/test_routing_from_text.py::test_handoff2_a_role_less_attack_rule_and_a_verify_job_do_not_make_an_independence_cycle`
- `tests/test_routing_from_text.py::test_handoff3_a_role_less_closed_choice_rule_is_chosen_for_an_answer_job`
- `tests/test_routing_from_text.py::test_output_keys_order_and_basis_kinds`
- `tests/test_routing_from_text.py::test_relation_alias_first_called_is_by_the_order_of_the_explanation_not_by_the_alias_direction`
- `tests/test_routing_from_text.py::test_relation_alias_returns_the_first_name_and_task_names_are_mapped_to_it`
- `tests/test_routing_from_text.py::test_relation_comparison_keeps_one_agent_only_and_comparison_only_does_not_stop`
- `tests/test_routing_from_text.py::test_relation_condition_from_a_size_word_and_head_by_concatenation`
- `tests/test_routing_from_text.py::test_relation_human_and_wait_with_scope_and_residual`
- `tests/test_routing_from_text.py::test_relation_independence_same_negated_distinct_and_a_different_phrase_is_held_as_ambiguous`
- `tests/test_routing_from_text.py::test_relation_override_replaces_exactly_the_same_scope_and_counts_it`
- `tests/test_routing_from_text.py::test_relation_override_that_overlaps_only_partly_is_held_as_ambiguous`
- `tests/test_routing_from_text.py::test_relation_precedence_maps_to_one_pair_of_rules_and_resolves_the_tie`
- `tests/test_routing_from_text.py::test_relation_precedence_that_cannot_be_written_as_one_pair_is_held_as_ambiguous`
- `tests/test_routing_from_text.py::test_relation_prohibition_by_polarity_and_by_modality`
- `tests/test_routing_from_text.py::test_relation_quantity_sets_concurrency_and_other_quantifier_forms_stop`
- `tests/test_routing_from_text.py::test_relation_roles_independence_is_the_routers_default_r3_and_makes_no_record`
- `tests/test_routing_from_text.py::test_relation_suitability_assign_recipient_and_perform_agent_and_role_verb`
- `tests/test_routing_from_text.py::test_router_call_passes_used_agents_only_no_chooser_and_the_first_names`
- `tests/test_routing_from_text.py::test_router_reasons_are_written_through_from_the_routers_types`
- `tests/test_routing_from_text.py::test_router_unknown_task_names_abstain_with_their_own_type`
- `tests/test_routing_from_text.py::test_stop_contradiction_and_conflicting_values`
- `tests/test_routing_from_text.py::test_stops_have_their_own_typed_status[\u30cf\u30eb\u306f\u5b9f\u88c5\u3060\u3002-reading13-MAPPED]`
- `tests/test_routing_from_text_entry.py::test_T1_the_entry_returns_the_documented_shape_and_routes_through_the_real_reader`
- `tests/test_routing_from_text_regress.py::test_M1_two_agents_that_are_each_east_co_are_not_merged_and_nobody_is_routed`
- `tests/test_routing_from_text_regress.py::test_M3_the_non_past_sentence_of_the_same_form_is_still_routed`
- `tests/test_routing_from_text_w5b.py::test_C3_without_a_marker_an_override_of_another_kind_about_another_name_is_held_not_a_replacement_both_statements_stand`
- `tests/test_routing_from_text_w5b.py::test_C3_without_a_marker_relation_override_replaces_exactly_the_same_scope_and_counts_it_both_statements_stand`
- `tests/test_routing_from_text_w5b.py::test_C3_without_a_marker_relation_override_that_overlaps_only_partly_is_held_as_ambiguous_both_declarations_stand`
- `tests/test_routing_from_text_w5b.py::test_a_japanese_addendum_with_a_replacement_word_replaces[\u3084\u3063\u3071\u308a\u5b9f\u88c5\u306f\u30eb\u30ca\u306b\u4efb\u305b\u308b\u3002-\u30eb\u30ca]`
- `tests/test_routing_from_text_w5b.py::test_a_japanese_addendum_with_a_replacement_word_replaces[\u5b9f\u88c5\u306f\u30df\u30e9\u3067\u306f\u306a\u304f\u30eb\u30ca\u306b\u4efb\u305b\u308b\u3002-\u30eb\u30ca]`
- `tests/test_routing_from_text_w5b.py::test_a_japanese_addendum_without_a_marker_keeps_both_statements[\u8ffd\u4f38\uff1a]`
- `tests/test_routing_from_text_w5b.py::test_a_japanese_addendum_without_a_marker_keeps_both_statements[\u8ffd\u8a18\uff08\u7fcc\u65e5\uff09\uff1a]`
- `tests/test_routing_from_text_w5b.py::test_a_japanese_addendum_without_a_marker_keeps_both_statements[\u8ffd\u8a18\uff1a]`
- `tests/test_routing_from_text_w5b.py::test_the_determiner_test_is_for_english_only_and_not_for_a_naming_sentence`
- `tests/test_routing_from_text_w5b.py::test_the_other_labels_replace_as_before_without_any_marker[\u66f4\u65b0\uff1a-\u5b9f\u88c5\u306f\u30eb\u30ca\u306b\u4efb\u305b\u308b\u3002]`
- `tests/test_routing_from_text_w5b.py::test_the_other_labels_replace_as_before_without_any_marker[\u8a02\u6b63\uff1a-\u5b9f\u88c5\u306f\u30eb\u30ca\u306b\u4efb\u305b\u308b\u3002]`
- `tests/test_routing_from_text_w5b.py::test_without_a_placement_nothing_is_checked_and_that_is_counted_not_hidden`

配置を与えれば K2 の既存テストの意図が満たせることの証拠と、残る分の理由: `k2_probe.txt`。
```
K2 probe (scratchpad copy of c875ed3 + the changed verantyx files; the test files are NOT changed; only tests/conftest.py of the copy gets the mechanical rewrite in k2_probe_rewrite.diff:
the default lookup of routing_from_text.explain is a placement that answers UNPLACED for every word).

K2 failing existing tests in the real tree:       51
of those, still failing with the rewrite:       14  => pass with a placement that knows the names: 37
  still failing: tests/test_routing_from_text.py::test_T3_the_same_content_as_a_hand_written_table_gives_the_same_decisions
  still failing: tests/test_routing_from_text.py::test_constraint_human_and_wait_scopes_and_residual_and_conflict
  still failing: tests/test_routing_from_text.py::test_constraint_independence_veto_for_two_other_roles
  still failing: tests/test_routing_from_text.py::test_constraint_prohibition_veto_does_not_try_the_next_agent
  still failing: tests/test_routing_from_text.py::test_gate_one_unread_unit_stops_every_job_and_the_router_is_not_called
  still failing: tests/test_routing_from_text.py::test_output_keys_order_and_basis_kinds
  still failing: tests/test_routing_from_text.py::test_relation_comparison_keeps_one_agent_only_and_comparison_only_does_not_stop
  still failing: tests/test_routing_from_text.py::test_relation_independence_same_negated_distinct_and_a_different_phrase_is_held_as_ambiguous
  still failing: tests/test_routing_from_text.py::test_relation_roles_independence_is_the_routers_default_r3_and_makes_no_record
  still failing: tests/test_routing_from_text.py::test_router_call_passes_used_agents_only_no_chooser_and_the_first_names
  still failing: tests/test_routing_from_text.py::test_router_reasons_are_written_through_from_the_routers_types
  still failing: tests/test_routing_from_text.py::test_router_unknown_task_names_abstain_with_their_own_type
  still failing: tests/test_routing_from_text_entry.py::test_T1_the_entry_returns_the_documented_shape_and_routes_through_the_real_reader
  still failing: tests/test_routing_from_text_w5b.py::test_without_a_placement_nothing_is_checked_and_that_is_counted_not_hidden
tests that fail only because of the rewrite:        0

Reasons of the still-failing ones (from --tb=short): (a) assertions on the lookup id 'stub-no-placement/1' / the not_checked count / byte-exact output (tests that are ABOUT the no-placement stub: 4);
(b) a sentence whose names come from splitting a parallel filler ('ハルとセキは同じ会社だ。'): the parts 'ハル' and 'セキ' have no placement answer of their own (the placement is asked about the filler 'ハルとセキ'), so R-J1 stops them as NAME_UNVERIFIED even with a placement (the gate then reads 6 mapped units instead of 7, and every test built on that text changes). This is a KNOWN HOLE of R-J1 as specified (over-abstention: the safe side) and is written in the docs; it is the main reason that K2 is not purely an 'old test gives no placement' conflict.
```

### 既知の穴（隠さない）
1. **並列の名前は配置があっても止まる**: `ハルとセキは…` の名前 `ハル`・`セキ` は、配置の答えが充填物 `ハルとセキ` 全体にしか付かず部分ごとの答えが無いので、日本語では `NAME_UNVERIFIED` になる（棄権側の過剰）。直すには `extract` に lookup を渡して部分ごとに引く必要がある（許可範囲の外）。
2. **R2 の「維持」は本物の reader ではほぼ到達しない**: `そのまま。`・`変えない。`・`No change.` は reader が節に読めず `AMBIGUOUS_RELATION` に倒れる。「そのまま類」を見分ける語の一覧は作らなかった代価。到達するのは断片を読む偽 reader のテストだけ。
3. **断片の述語は解釈しない**: 断片が節 1 つで極性 `-` なら（述語が何であれ）維持になる。変化の述語かどうかは見ない。維持は足す扱いなので、両方が並んで未確定になる側（棄権側）。
4. **標識の後ろに読点がある文は未確定になりうる**: `やっぱり実装はルナに、レビューはミラに任せる。` のように標識の後ろに節の区切りがあると断片（`実装はルナに`）を読むことになり、読めなければ `AMBIGUOUS_RELATION`（以前は置き換え）。
5. **推定の普通名詞は通る**: 配置が「推定」としか答えない普通名詞（r7 の `委員会`）は名前として通る（指示書のとおり）。

<!-- w5d-measured:end -->

## W5-d 第 2 ラウンド（W5-d2）の事前登録
<!-- w5d2-prereg:begin -->
事前登録の時刻: 2026-10-04 00:31:06 +0900（`date '+%F %T %z'` の出力。第 2 ラウンドの製品コード・テストの変更より前）。ベースは `dev` = `c875ed3`。第 1 ラウンドの `w5d-prereg`・`w5d-measured` 区間は 1 文字も変えない（第 1 ラウンドの記録）。この節が置き換えるものは、後ろの `w5d2-measured` 区間の「置き換わった記述」に列挙する。

**監査役の裁定（2026-10-04 00:05）**: B1 規則の衝突で落ちる既存テスト 78 件＋攻撃の写し 4 件は改訂を許可（K1・K2 は偽の `PlacementLookup` の注入、K3・K4・K5 は期待の改訂。名前は変えず、前後の全文を docs に）。B2 D1 の比較は正規化しない完全一致を追認（チケットの文言「NFKC 正規化後」は撤回）。B3 `recompute_q.py --check` と `w3c2-entry` 区間の例は、配置を与えた例に取り直してよい（区間の規則の本文は変えない）。追加 9 質問の観測が `VERA_PLACEMENT` を読まないのは、この後では「本番では質問がほぼ全部棄権」を意味するので、`observe.py` の question の経路で、`--placement` が無く `VERA_PLACEMENT` があるときは `event_cross.default_lookup()` の lookup を使う（収まらなければ既知の穴として次のチケットへ）。

**第 2 ラウンドの判断（中間職の指示書 D2-1〜D2-8）**
- D2-1 K1（質問の十字 15 件）: 配置の JSON（穴の充填物だけに direct の型。穴の型と食い違う型は付けない）または `O.FilePlacement` を注入する。例外 1 件（`test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun`）は「配置なしで FILLED」が主題で新しい契約と正反対なので、期待を新しい契約（配置なし → `NO_TYPED_CANDIDATE`・`TYPE_UNCHECKED`・`hole_type_check` が `NOT_CHECKED/NO_PLACEMENT`）に改訂。配置あり／なしの対のテストを足す。
- D2-2 K2（自由文→記録 52 件）: テストの中だけの `FakePlacement`（固定の名前は `UNPLACED`、列挙した普通名詞は direct の型）を注入。配置なしが主題の 3 件は期待を新しい契約（配置なし → 棄権）に改訂。**裁定の申し送り（並列の名前の過剰棄権は直さず既知の穴）からの逸脱**: 偽の配置（全語 UNPLACED）を注入しても 11 件は `ハルとセキは同じ会社だ。` の部分名 `ハル`・`セキ` に配置の答えが無く `NAME_UNVERIFIED` → `INCOMPLETE_READING` で通らない。期待を書き換えれば「弱体化」になるので、`routing_from_text.py` だけで、日本語の並列の充填物の部分名それぞれを同じ lookup に問う（R-J1 の同じ規則を部分名の配置の答えに当てるだけ。新しい規則は足さない。英語は変えない）。配置が無ければ今どおり `NAME_UNVERIFIED`。
- D2-3 K3（10 件）: 期待の値は変えず、渡した文書を実在させる（`tmp_path` の `memo.txt` に出典の `text` を書く）。K4: `artifacts/w5-d/k4_proposal.diff` をそのまま当てる。K5: 48 語の導出・バイト一致・各条件は不変、`frame_status` は `CONFIRMED` か `NOT_CONFIRMED`（後者は `frame is None`・`frame_disagreement`・助詞ごとの型が交わらない）、数は assert せず出力に一覧。
- D2-4 攻撃の写し 3 本の先頭行を `revised in W5-d2` に。G1-b は「先頭行と改訂した関数を除いて同一」。`data/` は同一。
- D2-5 D1: コードは変えない（正規化しない完全一致）。BASIS_POLICY に追認の理由を書く。
- D2-6 B3: `recompute_q.py` の `EXAMPLES` を 4 つ組（期待, 文書, 問い, 配置ファイル名）にし、`QD02`『どの人が客に切符を渡した？』（FILLED）と `QD01`『誰が生徒に地図を渡した？』（TIE）を `placement_q.json` つきに、`NO_ATTESTED_CELL` の例は今のまま。`--write` は 1 回だけ。凍結データは変えない。
- D2-7 追加 9: 製品の変更は `observe.py` の `_observe_question` の中だけ。`--placement` が無い（`StubLookup`）ときだけ `EC.default_lookup()`。充填物の型の確かめは同じ lookup に `surface` を問い直した答え。出力の `structure.placement` は実際に使った lookup の id。新しい鍵は足さない。**門**（どれか 1 つでも破れたらこの変更だけを戻して既知の穴に書く）: (1) r7 で 185 問の誤答 0・型未確認の FILLED/TIE 0、攻撃 120 問でも型未確認 0 で A01 が FILLED/TIE にならない、(2) `VERA_PLACEMENT` なしの 185 問の出力が第 1 ラウンドと byte 一致、(3) 平叙文の観測（`o1_bytes.py --child`）が基点と byte 一致（配置なしと r7 の 2 通り）。FALSE_NONE の増分と TIE が FILLED に縮む件は数えて書くが門にしない。
- D2-8 置き場所: 本区間（事前登録）、`w5d2-measured`（測定）、`w5d2-amended`（改訂したテストの前後の全文。`artifacts/w5-d/r2/scripts/amended_texts.py` で生成）。K1・B3・D2-7 → OBSERVATION、K2・D2-2 → ROUTING_FROM_TEXT、K3・K4・D1 → BASIS_POLICY、K5 → COARSE_PLACEMENT、EVENT_CROSS には穴の型の節への 1 段落。

**測り方（測る前に固定。出力はすべて `artifacts/w5-d/r2/`）**
- G1: 攻撃の写し 36 本が全部通る（`tests/attack/w3c2`・`test_attack_w5b_wave2.py`・`test_attack_w5c_*.py` 2 本・`tests/attack/w3a3/test_attack_w3a3_r6.py`）、K の 82 id が全部通る、G1-b は上のとおり。
- G2: 実装役の 185 問を（配置なしの環境 × place/noplace）と（`VERA_PLACEMENT=r7` × place/noplace）、攻撃 120 問を r7 で。誤答 0、型未確認の充填物を持つ FILLED/TIE 0。
- G3: 経路づけの凍結 4 本（配置なし）と 2 本（r7）の misroutes 0、合成 `g3_synth` を同じ入力で流し直して配置なしで誤って振った数 0。r7 は第 1 ラウンドの 1 から増えない。D2-2 の影響として r7 の 2 本の単位ごとの状態を第 1 ラウンドと比べる。
- G4: `g4_probe` の写しを流し、入力の sha256 と `summary` が第 1 ラウンドと同じ（`basis_policy.py` は第 2 ラウンドで変えない）。
- G5: r7 は作り直さない。`verify` が `OK`、`content_sha256` が第 1 ラウンドと同じ。
- G7: `pytest tests`（最後に 1 回）の失敗集合が基線から増えない。基線に無い失敗は環境由来だけ。K の id が残れば改訂を見直す。

**この文書の担当**: K2・D2-2（並列の名前の部分の問い合わせ。製品の変更は `verantyx/routing_from_text.py` の `read_units`・`_read_one`・`UnitReading`・`_places_of` だけ）。
<!-- w5d2-prereg:end -->

<!-- w5d2-amended:begin -->
#### `tests/test_routing_from_text.py` (before = git show c875ed3:tests/test_routing_from_text.py)

Added (helpers / tests, not amendments): `FakePlacement`, `std_placed`

##### `explain_lines` — before

```python
def explain_lines(*pairs, source="x.md"):
    """pairs: (sentence, reading).  The text is the sentences, one per line."""
    table = {sentence: reading for sentence, reading in pairs}
    text = "\n".join(sentence for sentence, _ in pairs) + "\n"
    return rt.explain(text, source, reader=lambda s: table[s]), text
```

##### `explain_lines` — after

```python
def explain_lines(*pairs, source="x.md", lookup=None):
    """pairs: (sentence, reading).  The text is the sentences, one per line.  ``lookup`` (W5-d2, default None = as before) is the placement."""
    table = {sentence: reading for sentence, reading in pairs}
    text = "\n".join(sentence for sentence, _ in pairs) + "\n"
    return rt.explain(text, source, reader=lambda s: table[s], lookup=lookup), text
```

##### `test_relation_suitability_assign_recipient_and_perform_agent_and_role_verb` — before

```python
def test_relation_suitability_assign_recipient_and_perform_agent_and_role_verb(std):
    explained, _ = explain_lines(("実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))),
                                 ("モモがコードを読む。", rd("ja", cl("読む", {"agent": "モモ", "patient": "コード"}))))
    assert kinds_of(explained) == [("SUITABILITY", ("ハル",), {"role": "implement"}),
                                   ("SUITABILITY", ("モモ",), {"role": "read"})]
    assert [r.fallback for r in explained.records.rules] == [True, True]      # an unconditional assignment is the role's fallback
    assert out_of(explained)["agent"] == "ハル" and out_of(explained, role="read", kind="read_large_file")["agent"] == "モモ"
```

##### `test_relation_suitability_assign_recipient_and_perform_agent_and_role_verb` — after

```python
def test_relation_suitability_assign_recipient_and_perform_agent_and_role_verb(std_placed):
    explained, _ = explain_lines(("実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))),
                                 ("モモがコードを読む。", rd("ja", cl("読む", {"agent": "モモ", "patient": "コード"}))), lookup=FakePlacement())
    assert kinds_of(explained) == [("SUITABILITY", ("ハル",), {"role": "implement"}),
                                   ("SUITABILITY", ("モモ",), {"role": "read"})]
    assert [r.fallback for r in explained.records.rules] == [True, True]      # an unconditional assignment is the role's fallback
    assert out_of(explained)["agent"] == "ハル" and out_of(explained, role="read", kind="read_large_file")["agent"] == "モモ"
```

##### `test_relation_prohibition_by_polarity_and_by_modality` — before

```python
def test_relation_prohibition_by_polarity_and_by_modality(std):
    for kw in ({"pol": "-"}, {"pol": "+", "mod": "prohibition"}):
        explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                     ("モモは検証をやってはいけない。", do("モモ", "検証", **kw)))
        assert [(r.kind, r.names) for r in explained.extraction.relations] == [("SUITABILITY", ("ハル",)), ("PROHIBITION", ("モモ",))]
        assert explained.records.constraints[0]["kind"] == "prohibit"
        assert len(explained.records.rules) == 1       # a prohibition is not a record
```

##### `test_relation_prohibition_by_polarity_and_by_modality` — after

```python
def test_relation_prohibition_by_polarity_and_by_modality(std_placed):
    for kw in ({"pol": "-"}, {"pol": "+", "mod": "prohibition"}):
        explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                     ("モモは検証をやってはいけない。", do("モモ", "検証", **kw)), lookup=FakePlacement())
        assert [(r.kind, r.names) for r in explained.extraction.relations] == [("SUITABILITY", ("ハル",)), ("PROHIBITION", ("モモ",))]
        assert explained.records.constraints[0]["kind"] == "prohibit"
        assert len(explained.records.rules) == 1       # a prohibition is not a record
```

##### `test_relation_comparison_keeps_one_agent_only_and_comparison_only_does_not_stop` — before

```python
def test_relation_comparison_keeps_one_agent_only_and_comparison_only_does_not_stop(std):
    explained, _ = explain_lines(("モモはハルより検証に向く。",
                                  rd("ja", cl("向く", {"entity": "モモ", "goal": "検証", "standard": "ハル"}, comparison="comparative"))),
                                 ("ハルは実装をやる。", do("ハル", "実装")))
    (rule,) = [r for r in explained.records.rules if r.role == "verify"]
    assert rule.preference == ("モモ",)                # not (モモ, ハル): "ハルでもよい" was not said
    assert explained.extraction.units[0].status == "MAPPED"
    assert [u.status for u in std.extraction.units][-1] == "COMPARISON_ONLY"
    assert std.abstention is None                       # a comparison of two names that routes nothing does not stop the gate
```

##### `test_relation_comparison_keeps_one_agent_only_and_comparison_only_does_not_stop` — after

```python
def test_relation_comparison_keeps_one_agent_only_and_comparison_only_does_not_stop(std_placed):
    explained, _ = explain_lines(("モモはハルより検証に向く。",
                                  rd("ja", cl("向く", {"entity": "モモ", "goal": "検証", "standard": "ハル"}, comparison="comparative"))),
                                 ("ハルは実装をやる。", do("ハル", "実装")), lookup=FakePlacement())
    (rule,) = [r for r in explained.records.rules if r.role == "verify"]
    assert rule.preference == ("モモ",)                # not (モモ, ハル): "ハルでもよい" was not said
    assert explained.extraction.units[0].status == "MAPPED"
    assert [u.status for u in std_placed.extraction.units][-1] == "COMPARISON_ONLY"
    assert std_placed.abstention is None                       # a comparison of two names that routes nothing does not stop the gate
```

##### `test_relation_condition_from_a_size_word_and_head_by_concatenation` — before

```python
def test_relation_condition_from_a_size_word_and_head_by_concatenation():
    explained, _ = explain_lines(("大きなリファクタリングはクイルに任せる。",
                                  rd("ja", cl("任せる", {"recipient": "クイル", "patient": "大きなリファクタリング"}))),
                                 ("実装はルナに任せる。", rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))))
    rule = next(r for r in explained.records.rules if r.preference == ("クイル",))
    assert {(c.field, c.value) for c in rule.conditions} == {("kind", "large_refactor"), ("size", "large")} and not rule.fallback
    assert out_of(explained, kind="large_refactor", size="large")["agent"] == "クイル"
    assert out_of(explained, kind="feature", size="small")["agent"] == "ルナ"
```

##### `test_relation_condition_from_a_size_word_and_head_by_concatenation` — after

```python
def test_relation_condition_from_a_size_word_and_head_by_concatenation():
    explained, _ = explain_lines(("大きなリファクタリングはクイルに任せる。",
                                  rd("ja", cl("任せる", {"recipient": "クイル", "patient": "大きなリファクタリング"}))),
                                 ("実装はルナに任せる。", rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))), lookup=FakePlacement())
    rule = next(r for r in explained.records.rules if r.preference == ("クイル",))
    assert {(c.field, c.value) for c in rule.conditions} == {("kind", "large_refactor"), ("size", "large")} and not rule.fallback
    assert out_of(explained, kind="large_refactor", size="large")["agent"] == "クイル"
    assert out_of(explained, kind="feature", size="small")["agent"] == "ルナ"
```

##### `test_relation_independence_same_negated_distinct_and_a_different_phrase_is_held_as_ambiguous` — before

```python
def test_relation_independence_same_negated_distinct_and_a_different_phrase_is_held_as_ambiguous():
    same, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")), ("セキは検証をやる。", do("セキ", "検証")),
                            ("ハルとセキは同じ会社だ。", rd("ja", cl("だ", {"entity": "ハルとセキ", "value": "同じ会社"}))))
    assert [(r.a, r.b, r.relation) for r in same.records.lineage_relations] == [("ハル", "セキ", "same")]
    en, _ = explain_lines(("Rook does the review.", rd("en", cl("do", {"agent": "Rook", "patient": "review"}))),
                          ("Lark reviews the code.", rd("en", cl("review", {"agent": "Lark", "patient": "code"}))),
                          ("Rook and Lark are not the same family.",
                           rd("en", cl("be", {"entity": "Rook and Lark", "value": "same family"}, "-"))))
    assert [(r.a, r.b, r.relation) for r in en.records.lineage_relations] == [("Rook", "Lark", "distinct")]
    amb, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                           ("ハルとセキは別の会社だ。", rd("ja", cl("だ", {"entity": "ハルとセキ", "value": "別の会社"}))))
    assert amb.extraction.units[1].status == "AMBIGUOUS_RELATION" and amb.records.lineage_relations == ()
    held = [r for r in rt.route_task(amb, task())["relations"] if r["held"]]
    assert len(held) == 2 and {h["data"]["reading"] for h in held} == {"EACH_OTHER_DIFFERENT", "BOTH_DIFFERENT_FROM_A_THIRD"}
    assert out_of(amb)["abstention"]["type"] == "INCOMPLETE_READING"
```

##### `test_relation_independence_same_negated_distinct_and_a_different_phrase_is_held_as_ambiguous` — after

```python
def test_relation_independence_same_negated_distinct_and_a_different_phrase_is_held_as_ambiguous():
    same, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")), ("セキは検証をやる。", do("セキ", "検証")),
                            ("ハルとセキは同じ会社だ。", rd("ja", cl("だ", {"entity": "ハルとセキ", "value": "同じ会社"}))), lookup=FakePlacement())
    assert [(r.a, r.b, r.relation) for r in same.records.lineage_relations] == [("ハル", "セキ", "same")]
    en, _ = explain_lines(("Rook does the review.", rd("en", cl("do", {"agent": "Rook", "patient": "review"}))),
                          ("Lark reviews the code.", rd("en", cl("review", {"agent": "Lark", "patient": "code"}))),
                          ("Rook and Lark are not the same family.",
                           rd("en", cl("be", {"entity": "Rook and Lark", "value": "same family"}, "-"))), lookup=FakePlacement())
    assert [(r.a, r.b, r.relation) for r in en.records.lineage_relations] == [("Rook", "Lark", "distinct")]
    amb, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                           ("ハルとセキは別の会社だ。", rd("ja", cl("だ", {"entity": "ハルとセキ", "value": "別の会社"}))), lookup=FakePlacement())
    assert amb.extraction.units[1].status == "AMBIGUOUS_RELATION" and amb.records.lineage_relations == ()
    held = [r for r in rt.route_task(amb, task())["relations"] if r["held"]]
    assert len(held) == 2 and {h["data"]["reading"] for h in held} == {"EACH_OTHER_DIFFERENT", "BOTH_DIFFERENT_FROM_A_THIRD"}
    assert out_of(amb)["abstention"]["type"] == "INCOMPLETE_READING"
```

##### `test_relation_roles_independence_is_the_routers_default_r3_and_makes_no_record` — before

```python
def test_relation_roles_independence_is_the_routers_default_r3_and_makes_no_record():
    explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                 ("作った者と確かめる者は別の会社だ。",
                                  rd("ja", cl("だ", {"entity": "作った者と確かめる者", "value": "別の会社"}))))
    (rel,) = [r for r in explained.extraction.relations if r.kind == "INDEPENDENCE"]
    assert rel.represented_by == "ROUTER_DEFAULT_R3" and explained.records.lineage_relations == ()
    assert explained.records.constraints == () and explained.extraction.units[1].status == "MAPPED"
```

##### `test_relation_roles_independence_is_the_routers_default_r3_and_makes_no_record` — after

```python
def test_relation_roles_independence_is_the_routers_default_r3_and_makes_no_record():
    explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                 ("作った者と確かめる者は別の会社だ。",
                                  rd("ja", cl("だ", {"entity": "作った者と確かめる者", "value": "別の会社"}))), lookup=FakePlacement())
    (rel,) = [r for r in explained.extraction.relations if r.kind == "INDEPENDENCE"]
    assert rel.represented_by == "ROUTER_DEFAULT_R3" and explained.records.lineage_relations == ()
    assert explained.records.constraints == () and explained.extraction.units[1].status == "MAPPED"
```

##### `test_relation_quantity_sets_concurrency_and_other_quantifier_forms_stop` — before

```python
def test_relation_quantity_sets_concurrency_and_other_quantifier_forms_stop():
    explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                 ("ハルは同時に二つまで動かす。",
                                  rd("ja", cl("動かす", {"agent": "ハル"}, quantifiers={"event": "at_most:2"}))))
    assert explained.records.agents[0].concurrency == 2
    assert out_of(explained, running={"ハル": 2})["undecided_reason"] == "ALL_EXCLUDED"
    assert out_of(explained, running={"ハル": 1})["agent"] == "ハル"
    bad, _ = explain_lines(("ハルは全部動かす。", rd("ja", cl("動かす", {"agent": "ハル"}, quantifiers={"event": "universal"}))))
    assert bad.extraction.units[0].status == "UNREPRESENTABLE"
```

##### `test_relation_quantity_sets_concurrency_and_other_quantifier_forms_stop` — after

```python
def test_relation_quantity_sets_concurrency_and_other_quantifier_forms_stop():
    explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                 ("ハルは同時に二つまで動かす。",
                                  rd("ja", cl("動かす", {"agent": "ハル"}, quantifiers={"event": "at_most:2"}))), lookup=FakePlacement())
    assert explained.records.agents[0].concurrency == 2
    assert out_of(explained, running={"ハル": 2})["undecided_reason"] == "ALL_EXCLUDED"
    assert out_of(explained, running={"ハル": 1})["agent"] == "ハル"
    bad, _ = explain_lines(("ハルは全部動かす。", rd("ja", cl("動かす", {"agent": "ハル"}, quantifiers={"event": "universal"}))), lookup=FakePlacement())
    assert bad.extraction.units[0].status == "UNREPRESENTABLE"
```

##### `two_rules_and_a_precedence` — before

```python
def two_rules_and_a_precedence(prefer_arms):
    return explain_lines(
        ("実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))),
        ("大きな修正はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな修正"}))),
        ("大きな修正はルナに任せる。", rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "大きな修正"}))),
        ("ルナをハルより優先する。", rd("ja", cl("優先する", prefer_arms))),
    )[0]
```

##### `two_rules_and_a_precedence` — after

```python
def two_rules_and_a_precedence(prefer_arms, lookup=None):      # W5-d2: ``lookup`` (default None = as before) is the placement
    return explain_lines(
        ("実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))),
        ("大きな修正はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな修正"}))),
        ("大きな修正はルナに任せる。", rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "大きな修正"}))),
        ("ルナをハルより優先する。", rd("ja", cl("優先する", prefer_arms))),
        lookup=lookup,
    )[0]
```

##### `test_relation_precedence_maps_to_one_pair_of_rules_and_resolves_the_tie` — before

```python
def test_relation_precedence_maps_to_one_pair_of_rules_and_resolves_the_tie():
    # two non-fallback rules with the same conditions and different agents tie; the human's precedence decides between them
    explained = two_rules_and_a_precedence({"patient": "ルナ", "standard": "ハル"})
    assert explained.extraction.units[3].status == "MAPPED" and len(explained.records.precedence) == 1
    got = out_of(explained, kind="small_fix", size="large")
    assert got["decision"] == "route" and got["agent"] == "ルナ" and got["decided_by"] == "precedence"
    assert got["basis_kind"] == "precedence"
```

##### `test_relation_precedence_maps_to_one_pair_of_rules_and_resolves_the_tie` — after

```python
def test_relation_precedence_maps_to_one_pair_of_rules_and_resolves_the_tie():
    # two non-fallback rules with the same conditions and different agents tie; the human's precedence decides between them
    explained = two_rules_and_a_precedence({"patient": "ルナ", "standard": "ハル"}, lookup=FakePlacement())
    assert explained.extraction.units[3].status == "MAPPED" and len(explained.records.precedence) == 1
    got = out_of(explained, kind="small_fix", size="large")
    assert got["decision"] == "route" and got["agent"] == "ルナ" and got["decided_by"] == "precedence"
    assert got["basis_kind"] == "precedence"
```

##### `test_relation_precedence_that_cannot_be_written_as_one_pair_is_held_as_ambiguous` — before

```python
def test_relation_precedence_that_cannot_be_written_as_one_pair_is_held_as_ambiguous():
    assert two_rules_and_a_precedence({"patient": "ルナ"}).extraction.units[3].status == "AMBIGUOUS_RELATION"
    lone, _ = explain_lines(("大きな修正はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな修正"}))),
                            ("実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))),
                            ("ルナをハルより優先する。", rd("ja", cl("優先する", {"patient": "ルナ", "standard": "ハル"}))))
    assert lone.extraction.units[2].status == "AMBIGUOUS_RELATION" and lone.records.precedence == ()
```

##### `test_relation_precedence_that_cannot_be_written_as_one_pair_is_held_as_ambiguous` — after

```python
def test_relation_precedence_that_cannot_be_written_as_one_pair_is_held_as_ambiguous():
    assert two_rules_and_a_precedence({"patient": "ルナ"}, lookup=FakePlacement()).extraction.units[3].status == "AMBIGUOUS_RELATION"
    lone, _ = explain_lines(("大きな修正はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな修正"}))),
                            ("実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))),
                            ("ルナをハルより優先する。", rd("ja", cl("優先する", {"patient": "ルナ", "standard": "ハル"}))), lookup=FakePlacement())
    assert lone.extraction.units[2].status == "AMBIGUOUS_RELATION" and lone.records.precedence == ()
```

##### `test_relation_override_replaces_exactly_the_same_scope_and_counts_it` — before

```python
def test_relation_override_replaces_exactly_the_same_scope_and_counts_it():
    text = "実装はハルに任せる。\n追記：やっぱり実装はルナに任せる。\n"
    table = {"実装はハルに任せる。": OV[0][1], "やっぱり実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    explained = rt.explain(text, "x.md", reader=lambda s: table[s])
    assert explained.extraction.auto_resolved == 1
    assert [r.superseded_by for r in explained.extraction.relations] == ["R002", None]
    assert [r.preference for r in explained.records.rules] == [("ルナ",)]
    result = rt.route_task(explained, task())
    assert result["agent"] == "ルナ" and result["reading"]["auto_resolved"] == 1
    assert [r["superseded_by"] for r in result["relations"]] == ["R002", None]      # the replaced relation is kept and says by what
```

##### `test_relation_override_replaces_exactly_the_same_scope_and_counts_it` — after

```python
def test_relation_override_replaces_exactly_the_same_scope_and_counts_it():
    text = "実装はハルに任せる。\n追記：やっぱり実装はルナに任せる。\n"
    table = {"実装はハルに任せる。": OV[0][1], "やっぱり実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    explained = rt.explain(text, "x.md", reader=lambda s: table[s], lookup=FakePlacement())
    assert explained.extraction.auto_resolved == 1
    assert [r.superseded_by for r in explained.extraction.relations] == ["R002", None]
    assert [r.preference for r in explained.records.rules] == [("ルナ",)]
    result = rt.route_task(explained, task())
    assert result["agent"] == "ルナ" and result["reading"]["auto_resolved"] == 1
    assert [r["superseded_by"] for r in result["relations"]] == ["R002", None]      # the replaced relation is kept and says by what
```

##### `test_relation_override_that_overlaps_only_partly_is_held_as_ambiguous` — before

```python
def test_relation_override_that_overlaps_only_partly_is_held_as_ambiguous():
    table = {"大きな実装はハルに任せる。": rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな実装"})),
             "実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    # "大きな実装" is a size word before a head that is not a kind: the first sentence stops, so use a kind head instead
    table = {"大きなリファクタリングはハルに任せる。": rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きなリファクタリング"})),
             "やっぱり実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    text = "大きなリファクタリングはハルに任せる。\n追記：やっぱり実装はルナに任せる。\n"
    explained = rt.explain(text, "x.md", reader=lambda s: table[s])
    assert explained.extraction.units[1].status == "AMBIGUOUS_RELATION" and explained.extraction.auto_resolved == 0
    assert out_of(explained)["abstention"]["type"] == "INCOMPLETE_READING"
```

##### `test_relation_override_that_overlaps_only_partly_is_held_as_ambiguous` — after

```python
def test_relation_override_that_overlaps_only_partly_is_held_as_ambiguous():
    table = {"大きな実装はハルに任せる。": rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな実装"})),
             "実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    # "大きな実装" is a size word before a head that is not a kind: the first sentence stops, so use a kind head instead
    table = {"大きなリファクタリングはハルに任せる。": rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きなリファクタリング"})),
             "やっぱり実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    text = "大きなリファクタリングはハルに任せる。\n追記：やっぱり実装はルナに任せる。\n"
    explained = rt.explain(text, "x.md", reader=lambda s: table[s], lookup=FakePlacement())
    assert explained.extraction.units[1].status == "AMBIGUOUS_RELATION" and explained.extraction.auto_resolved == 0
    assert out_of(explained)["abstention"]["type"] == "INCOMPLETE_READING"
```

##### `test_relation_alias_returns_the_first_name_and_task_names_are_mapped_to_it` — before

```python
def test_relation_alias_returns_the_first_name_and_task_names_are_mapped_to_it():
    # another name comes from a CALL sentence only (a copula "X is Y" with two names is held as ambiguous: see the M1 tests below)
    explained, _ = explain_lines(("ルナは実装をやる。", do("ルナ", "実装")),
                                 ("ルナをクイルと呼ぶ。", rd("ja", cl("呼ぶ", {"patient": "ルナ", "result": "クイル"}))),
                                 ("ソラがコードを確かめる。", rd("ja", cl("確かめる", {"agent": "ソラ", "patient": "コード"}))))
    assert [{"canonical": g["canonical"], "aliases": g["aliases"]} for g in explained.records.aliases] == [{"canonical": "ルナ", "aliases": ["クイル"]}]
    got = rt.route_task(explained, task(role="implement", running={"クイル": 1}))
    # the alias in the task is read as the first name (ルナ, who declares no concurrency and is busy): not TASK_NAME_UNKNOWN
    assert got["agent"] is None and got["undecided_reason"] == "ALL_EXCLUDED" and got["abstention"] is None
    assert out_of(explained)["agent"] == "ルナ"
```

##### `test_relation_alias_returns_the_first_name_and_task_names_are_mapped_to_it` — after

```python
def test_relation_alias_returns_the_first_name_and_task_names_are_mapped_to_it():
    # another name comes from a CALL sentence only (a copula "X is Y" with two names is held as ambiguous: see the M1 tests below)
    explained, _ = explain_lines(("ルナは実装をやる。", do("ルナ", "実装")),
                                 ("ルナをクイルと呼ぶ。", rd("ja", cl("呼ぶ", {"patient": "ルナ", "result": "クイル"}))),
                                 ("ソラがコードを確かめる。", rd("ja", cl("確かめる", {"agent": "ソラ", "patient": "コード"}))), lookup=FakePlacement())
    assert [{"canonical": g["canonical"], "aliases": g["aliases"]} for g in explained.records.aliases] == [{"canonical": "ルナ", "aliases": ["クイル"]}]
    got = rt.route_task(explained, task(role="implement", running={"クイル": 1}))
    # the alias in the task is read as the first name (ルナ, who declares no concurrency and is busy): not TASK_NAME_UNKNOWN
    assert got["agent"] is None and got["undecided_reason"] == "ALL_EXCLUDED" and got["abstention"] is None
    assert out_of(explained)["agent"] == "ルナ"
```

##### `test_relation_alias_first_called_is_by_the_order_of_the_explanation_not_by_the_alias_direction` — before

```python
def test_relation_alias_first_called_is_by_the_order_of_the_explanation_not_by_the_alias_direction():
    explained, _ = explain_lines(("クイルは実装をやる。", do("クイル", "実装")),
                                 ("クイルをルナと呼ぶ。", rd("ja", cl("呼ぶ", {"patient": "クイル", "result": "ルナ"}))))
    assert out_of(explained)["agent"] == "クイル" and agent_ids(explained) == ["クイル"]
    explained, _ = explain_lines(("クイルは実装をやる。", do("クイル", "実装")),
                                 ("ルナをクイルと呼ぶ。", rd("ja", cl("呼ぶ", {"patient": "ルナ", "result": "クイル"}))))
    assert out_of(explained)["agent"] == "クイル" and agent_ids(explained) == ["クイル"]
```

##### `test_relation_alias_first_called_is_by_the_order_of_the_explanation_not_by_the_alias_direction` — after

```python
def test_relation_alias_first_called_is_by_the_order_of_the_explanation_not_by_the_alias_direction():
    explained, _ = explain_lines(("クイルは実装をやる。", do("クイル", "実装")),
                                 ("クイルをルナと呼ぶ。", rd("ja", cl("呼ぶ", {"patient": "クイル", "result": "ルナ"}))), lookup=FakePlacement())
    assert out_of(explained)["agent"] == "クイル" and agent_ids(explained) == ["クイル"]
    explained, _ = explain_lines(("クイルは実装をやる。", do("クイル", "実装")),
                                 ("ルナをクイルと呼ぶ。", rd("ja", cl("呼ぶ", {"patient": "ルナ", "result": "クイル"}))), lookup=FakePlacement())
    assert out_of(explained)["agent"] == "クイル" and agent_ids(explained) == ["クイル"]
```

##### `test_M1_a_copula_between_two_names_is_ambiguous_and_makes_no_alias_and_no_merge` — before

```python
def test_M1_a_copula_between_two_names_is_ambiguous_and_makes_no_alias_and_no_merge():
    for left, right in (("ハル", "東社"), ("クイル", "ルナ")):
        explained, _ = explain_lines((f"{left}は実装をやる。", do(left, "実装")),
                                     (f"{left}は{right}だ。", rd("ja", cl("だ", {"entity": left, "value": right}))))
        unit = explained.extraction.units[1]
        assert unit.status == "AMBIGUOUS_RELATION" and unit.reasons == ["COPULA_ALIAS_OR_PREDICATION"]
        assert explained.records.aliases == ()
        got = out_of(explained)
        assert got["decision"] == "undecided" and got["abstention"]["type"] == "INCOMPLETE_READING" and got["router"] is None
        held = [r for r in got["relations"] if r["held"]]
        assert {h["data"]["reading"] for h in held} == {"COPULA_IS_ANOTHER_NAME", "COPULA_IS_A_PREDICATE_OF_THE_FIRST"}
    # two agents that "are" the same third name stay two agents: nobody is routed on the strength of a merge
    explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                 ("セキはレビューをやる。", do("セキ", "レビュー")),
                                 ("ハルは東社だ。", rd("ja", cl("だ", {"entity": "ハル", "value": "東社"}))),
                                 ("セキは東社だ。", rd("ja", cl("だ", {"entity": "セキ", "value": "東社"}))))
    assert agent_ids(explained) == ["セキ", "ハル"] and explained.records.aliases == ()
    for job in (task(), task(role="review", kind="review")):
        assert rt.route_task(explained, job)["decision"] == "undecided"
```

##### `test_M1_a_copula_between_two_names_is_ambiguous_and_makes_no_alias_and_no_merge` — after

```python
def test_M1_a_copula_between_two_names_is_ambiguous_and_makes_no_alias_and_no_merge():
    for left, right in (("ハル", "東社"), ("クイル", "ルナ")):
        explained, _ = explain_lines((f"{left}は実装をやる。", do(left, "実装")),
                                     (f"{left}は{right}だ。", rd("ja", cl("だ", {"entity": left, "value": right}))), lookup=FakePlacement())
        unit = explained.extraction.units[1]
        assert unit.status == "AMBIGUOUS_RELATION" and unit.reasons == ["COPULA_ALIAS_OR_PREDICATION"]
        assert explained.records.aliases == ()
        got = out_of(explained)
        assert got["decision"] == "undecided" and got["abstention"]["type"] == "INCOMPLETE_READING" and got["router"] is None
        held = [r for r in got["relations"] if r["held"]]
        assert {h["data"]["reading"] for h in held} == {"COPULA_IS_ANOTHER_NAME", "COPULA_IS_A_PREDICATE_OF_THE_FIRST"}
    # two agents that "are" the same third name stay two agents: nobody is routed on the strength of a merge
    explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                 ("セキはレビューをやる。", do("セキ", "レビュー")),
                                 ("ハルは東社だ。", rd("ja", cl("だ", {"entity": "ハル", "value": "東社"}))),
                                 ("セキは東社だ。", rd("ja", cl("だ", {"entity": "セキ", "value": "東社"}))), lookup=FakePlacement())
    assert agent_ids(explained) == ["セキ", "ハル"] and explained.records.aliases == ()
    for job in (task(), task(role="review", kind="review")):
        assert rt.route_task(explained, job)["decision"] == "undecided"
```

##### `test_M3_a_nonpast_centre_is_read_and_a_reading_without_a_tense_is_rejected_by_the_cross_as_unread` — before

```python
def test_M3_a_nonpast_centre_is_read_and_a_reading_without_a_tense_is_rejected_by_the_cross_as_unread():
    explained, _ = explain_lines(("ハルが実装をやる。", do("ハル", "実装")))
    assert explained.extraction.units[0].status == "MAPPED"
    clause = cl("やる", {"agent": "ハル", "patient": "実装"})
    del clause["tense"]
    explained, _ = explain_lines(("ハルが実装をやる。", rd("ja", clause)))
    assert explained.extraction.units[0].status == "UNREAD"       # the cross requires the key (INPUT_REJECTED): never a silent default
```

##### `test_M3_a_nonpast_centre_is_read_and_a_reading_without_a_tense_is_rejected_by_the_cross_as_unread` — after

```python
def test_M3_a_nonpast_centre_is_read_and_a_reading_without_a_tense_is_rejected_by_the_cross_as_unread():
    explained, _ = explain_lines(("ハルが実装をやる。", do("ハル", "実装")), lookup=FakePlacement())
    assert explained.extraction.units[0].status == "MAPPED"
    clause = cl("やる", {"agent": "ハル", "patient": "実装"})
    del clause["tense"]
    explained, _ = explain_lines(("ハルが実装をやる。", rd("ja", clause)), lookup=FakePlacement())
    assert explained.extraction.units[0].status == "UNREAD"       # the cross requires the key (INPUT_REJECTED): never a silent default
```

##### `test_D13_an_override_of_another_kind_about_another_name_is_held_not_a_replacement` — before

```python
def test_D13_an_override_of_another_kind_about_another_name_is_held_not_a_replacement():
    ov, text = explain_lines(("ハルはテストを書く。", rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}))),
                             ("セキもテストを書く。", rd("ja", cl("書く", {"agent": "セキ", "patient": "テスト"}))))
    # the same kind (A does it -> B does it) replaces; a different kind and a different name (A does it -> B does not) is held
    table = {"ハルはテストを書く。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"})),
             "やっぱりモモはテストを書かない。": rd("ja", cl("書く", {"agent": "モモ", "patient": "テスト"}, "-"))}
    explained = rt.explain("ハルはテストを書く。\n追記：やっぱりモモはテストを書かない。\n", "x.md", reader=lambda sentence: table[sentence])
    unit = explained.extraction.units[1]
    assert unit.status == "AMBIGUOUS_RELATION" and unit.reasons[0].startswith("OVERRIDE_OTHER_KIND_AND_NAME:")
    assert explained.extraction.auto_resolved == 0 and out_of(explained, kind="test_authoring")["abstention"]["type"] == "INCOMPLETE_READING"
    same_name = {"ハルはテストを書く。": table["ハルはテストを書く。"],
                 "やっぱりハルはテストを書かない。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}, "-"))}
    explained = rt.explain("ハルはテストを書く。\n追記：やっぱりハルはテストを書かない。\n", "x.md", reader=lambda sentence: same_name[sentence])
    assert explained.extraction.units[1].status == "MAPPED" and explained.extraction.auto_resolved == 1
```

##### `test_D13_an_override_of_another_kind_about_another_name_is_held_not_a_replacement` — after

```python
def test_D13_an_override_of_another_kind_about_another_name_is_held_not_a_replacement():
    ov, text = explain_lines(("ハルはテストを書く。", rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}))),
                             ("セキもテストを書く。", rd("ja", cl("書く", {"agent": "セキ", "patient": "テスト"}))), lookup=FakePlacement())
    # the same kind (A does it -> B does it) replaces; a different kind and a different name (A does it -> B does not) is held
    table = {"ハルはテストを書く。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"})),
             "やっぱりモモはテストを書かない。": rd("ja", cl("書く", {"agent": "モモ", "patient": "テスト"}, "-"))}
    explained = rt.explain("ハルはテストを書く。\n追記：やっぱりモモはテストを書かない。\n", "x.md", reader=lambda sentence: table[sentence], lookup=FakePlacement())
    unit = explained.extraction.units[1]
    assert unit.status == "AMBIGUOUS_RELATION" and unit.reasons[0].startswith("OVERRIDE_OTHER_KIND_AND_NAME:")
    assert explained.extraction.auto_resolved == 0 and out_of(explained, kind="test_authoring")["abstention"]["type"] == "INCOMPLETE_READING"
    same_name = {"ハルはテストを書く。": table["ハルはテストを書く。"],
                 "やっぱりハルはテストを書かない。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}, "-"))}
    explained = rt.explain("ハルはテストを書く。\n追記：やっぱりハルはテストを書かない。\n", "x.md", reader=lambda sentence: same_name[sentence], lookup=FakePlacement())
    assert explained.extraction.units[1].status == "MAPPED" and explained.extraction.auto_resolved == 1
```

##### `test_relation_human_and_wait_with_scope_and_residual` — before

```python
def test_relation_human_and_wait_with_scope_and_residual():
    base = (("ハルは実装をやる。", do("ハル", "実装")), ("ソラがコードを確かめる。", rd("ja", cl("確かめる", {"agent": "ソラ", "patient": "コード"}))))
    human, _ = explain_lines(*base, ("生成は人がやる。", do("人", "生成")))
    assert out_of(human, role="generate", kind="bulk_generation")["undecided_reason"] == "HUMAN"
    assert out_of(human)["agent"] == "ハル"                                  # a human-does-it statement is scoped
    wait, _ = explain_lines(*base, ("生成を待つ。", rd("ja", cl("待つ", {"patient": "生成"}))))
    assert out_of(wait, role="generate", kind="bulk_generation")["undecided_reason"] == "WAIT"
    rest, _ = explain_lines(*base, ("それ以外の仕事を待つ。", rd("ja", cl("待つ", {"patient": "それ以外の仕事"}))))
    assert out_of(rest, role="generate", kind="bulk_generation")["undecided_reason"] == "WAIT"   # where the router said NOT_COVERED
    assert out_of(rest)["agent"] == "ハル"                                    # a residual scope never turns a route into a wait
    assert out_of(rest, role="verify", kind="verification")["undecided_reason"] == "ALL_EXCLUDED"   # and not ALL_EXCLUDED either
```

##### `test_relation_human_and_wait_with_scope_and_residual` — after

```python
def test_relation_human_and_wait_with_scope_and_residual():
    base = (("ハルは実装をやる。", do("ハル", "実装")), ("ソラがコードを確かめる。", rd("ja", cl("確かめる", {"agent": "ソラ", "patient": "コード"}))))
    human, _ = explain_lines(*base, ("生成は人がやる。", do("人", "生成")), lookup=FakePlacement())
    assert out_of(human, role="generate", kind="bulk_generation")["undecided_reason"] == "HUMAN"
    assert out_of(human)["agent"] == "ハル"                                  # a human-does-it statement is scoped
    wait, _ = explain_lines(*base, ("生成を待つ。", rd("ja", cl("待つ", {"patient": "生成"}))), lookup=FakePlacement())
    assert out_of(wait, role="generate", kind="bulk_generation")["undecided_reason"] == "WAIT"
    rest, _ = explain_lines(*base, ("それ以外の仕事を待つ。", rd("ja", cl("待つ", {"patient": "それ以外の仕事"}))), lookup=FakePlacement())
    assert out_of(rest, role="generate", kind="bulk_generation")["undecided_reason"] == "WAIT"   # where the router said NOT_COVERED
    assert out_of(rest)["agent"] == "ハル"                                    # a residual scope never turns a route into a wait
    assert out_of(rest, role="verify", kind="verification")["undecided_reason"] == "ALL_EXCLUDED"   # and not ALL_EXCLUDED either
```

##### `one_unit_status` — before

```python
def one_unit_status(sentence, reading):
    explained, _ = explain_lines((sentence, reading))
    return explained.extraction.units[0].status, explained.extraction.units[0].reasons
```

##### `one_unit_status` — after

```python
def one_unit_status(sentence, reading, lookup=None):      # W5-d2: ``lookup`` (default None = as before) is the placement
    explained, _ = explain_lines((sentence, reading), lookup=lookup)
    return explained.extraction.units[0].status, explained.extraction.units[0].reasons
```

##### `test_stops_have_their_own_typed_status` — before

```python
@pytest.mark.parametrize("sentence,reading,status", [
    ("ハルは速い。", rd("ja", cl("速い", {"entity": "ハル"})), "PREDICATE_CLASS_UNKNOWN"),
    ("ハルは占いをやる。", do("ハル", "占い"), "WORK_TERM_UNKNOWN"),
    ("前者は実装をやる。", do("前者", "実装"), "NAME_UNRESOLVED"),
    ("重い方は実装をやる。", do("重い方", "実装"), "NAME_UNRESOLVED"),
    ("ハルさんは実装をやる。", do("ハルさん", "実装"), "NAME_UNRESOLVED"),
    ("The quiet one does the review.", rd("en", cl("do", {"agent": "the quiet one", "patient": "review"})), "NAME_UNRESOLVED"),
    ("ハルは10ファイルを超える実装をやる。", do("ハル", "10ファイルを超える実装"), "WORK_TERM_UNKNOWN"),
    ("ハルは実装をやる。", rd("ja", cl("やる", {"agent": "ハル", "patient": "実装", "time": "明日"})), "UNREPRESENTABLE"),
    ("ハルは1日3回まで実装をやる。", rd("ja", cl("やる", {"agent": "ハル", "patient": "実装"}, quantifiers={"event": "at_most:3"})), "UNREPRESENTABLE"),
    ("ハルは実装をやりたい。", rd("ja", cl("やる", {"agent": "ハル", "patient": "実装"}, mod="desire")), "UNREPRESENTABLE"),
    ("ハルは実装をやる。", rd("ja", cl("やる", {"agent": "ハル", "patient": "実装"}, voice="passive")), "UNREPRESENTABLE"),
    ("ハルは実装をやる。", rd("ja", cl("やる", {"agent": ["ハル", "モモ"], "patient": "実装"})), "AMBIGUOUS_RELATION"),
    ("ハルは東社のモデルだ。", rd("ja", cl("だ", {"entity": "ハル", "value": "東社のモデル"})), "NAME_UNRESOLVED"),
    ("ハルは実装だ。", rd("ja", cl("だ", {"entity": "ハル", "value": "実装"})), "MAPPED"),
])
def test_stops_have_their_own_typed_status(sentence, reading, status):
    got, reasons = one_unit_status(sentence, reading)
    assert got == status, reasons
```

##### `test_stops_have_their_own_typed_status` — after

```python
@pytest.mark.parametrize("sentence,reading,status", [
    ("ハルは速い。", rd("ja", cl("速い", {"entity": "ハル"})), "PREDICATE_CLASS_UNKNOWN"),
    ("ハルは占いをやる。", do("ハル", "占い"), "WORK_TERM_UNKNOWN"),
    ("前者は実装をやる。", do("前者", "実装"), "NAME_UNRESOLVED"),
    ("重い方は実装をやる。", do("重い方", "実装"), "NAME_UNRESOLVED"),
    ("ハルさんは実装をやる。", do("ハルさん", "実装"), "NAME_UNRESOLVED"),
    ("The quiet one does the review.", rd("en", cl("do", {"agent": "the quiet one", "patient": "review"})), "NAME_UNRESOLVED"),
    ("ハルは10ファイルを超える実装をやる。", do("ハル", "10ファイルを超える実装"), "WORK_TERM_UNKNOWN"),
    ("ハルは実装をやる。", rd("ja", cl("やる", {"agent": "ハル", "patient": "実装", "time": "明日"})), "UNREPRESENTABLE"),
    ("ハルは1日3回まで実装をやる。", rd("ja", cl("やる", {"agent": "ハル", "patient": "実装"}, quantifiers={"event": "at_most:3"})), "UNREPRESENTABLE"),
    ("ハルは実装をやりたい。", rd("ja", cl("やる", {"agent": "ハル", "patient": "実装"}, mod="desire")), "UNREPRESENTABLE"),
    ("ハルは実装をやる。", rd("ja", cl("やる", {"agent": "ハル", "patient": "実装"}, voice="passive")), "UNREPRESENTABLE"),
    ("ハルは実装をやる。", rd("ja", cl("やる", {"agent": ["ハル", "モモ"], "patient": "実装"})), "AMBIGUOUS_RELATION"),
    ("ハルは東社のモデルだ。", rd("ja", cl("だ", {"entity": "ハル", "value": "東社のモデル"})), "NAME_UNRESOLVED"),
    ("ハルは実装だ。", rd("ja", cl("だ", {"entity": "ハル", "value": "実装"})), "MAPPED"),
])
def test_stops_have_their_own_typed_status(sentence, reading, status):
    got, reasons = one_unit_status(sentence, reading, lookup=FakePlacement())
    assert got == status, reasons
```

##### `test_stop_contradiction_and_conflicting_values` — before

```python
def test_stop_contradiction_and_conflicting_values():
    both, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")), ("ハルは実装をやらない。", do("ハル", "実装", "-")))
    assert [u.status for u in both.extraction.units] == ["CONTRADICTION", "CONTRADICTION"]
    quant, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                             ("ハルは二つまで動かす。", rd("ja", cl("動かす", {"agent": "ハル"}, quantifiers={"event": "at_most:2"}))),
                             ("ハルは三つまで動かす。", rd("ja", cl("動かす", {"agent": "ハル"}, quantifiers={"event": "at_most:3"}))))
    assert [u.status for u in quant.extraction.units][1:] == ["CONTRADICTION", "CONTRADICTION"]
```

##### `test_stop_contradiction_and_conflicting_values` — after

```python
def test_stop_contradiction_and_conflicting_values():
    both, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")), ("ハルは実装をやらない。", do("ハル", "実装", "-")), lookup=FakePlacement())
    assert [u.status for u in both.extraction.units] == ["CONTRADICTION", "CONTRADICTION"]
    quant, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                             ("ハルは二つまで動かす。", rd("ja", cl("動かす", {"agent": "ハル"}, quantifiers={"event": "at_most:2"}))),
                             ("ハルは三つまで動かす。", rd("ja", cl("動かす", {"agent": "ハル"}, quantifiers={"event": "at_most:3"}))), lookup=FakePlacement())
    assert [u.status for u in quant.extraction.units][1:] == ["CONTRADICTION", "CONTRADICTION"]
```

##### `test_gate_one_unread_unit_stops_every_job_and_the_router_is_not_called` — before

```python
def test_gate_one_unread_unit_stops_every_job_and_the_router_is_not_called(monkeypatch):
    calls = []
    real = ar.route
    monkeypatch.setattr(ar, "route", lambda *a, **k: calls.append(1) or real(*a, **k))
    explained, _ = explain_lines(*STD, ("ただし大きい物は人がやる。", no("ja")))
    for job in (task(), task(role="verify", kind="verification", already_used={"implement": ["ハル"]}), task(role="review", kind="review")):
        got = rt.route_task(explained, job)
        assert got["decision"] == "undecided" and got["undecided_reason"] == "ABSTAINED" and got["agent"] is None
        assert got["abstention"]["type"] == "INCOMPLETE_READING" and got["router"] is None
        assert got["decided_by"] == "gate:INCOMPLETE_READING" and got["basis_kind"] is None
        assert got["abstention"]["by_status"]["UNREAD"] == 1 and got["abstention"]["by_status"]["MAPPED"] == 7
        assert [u["status"] for u in got["abstention"]["units"]] == ["UNREAD"]
    assert calls == []
    # the records of the units that were read are still reported
    assert got["records"]["agents"] and got["records"]["rules"]
    clean, _ = explain_lines(*STD)
    assert rt.route_task(clean, task())["decision"] == "route" and calls == [1]
```

##### `test_gate_one_unread_unit_stops_every_job_and_the_router_is_not_called` — after

```python
def test_gate_one_unread_unit_stops_every_job_and_the_router_is_not_called(monkeypatch):
    calls = []
    real = ar.route
    monkeypatch.setattr(ar, "route", lambda *a, **k: calls.append(1) or real(*a, **k))
    explained, _ = explain_lines(*STD, ("ただし大きい物は人がやる。", no("ja")), lookup=FakePlacement())
    for job in (task(), task(role="verify", kind="verification", already_used={"implement": ["ハル"]}), task(role="review", kind="review")):
        got = rt.route_task(explained, job)
        assert got["decision"] == "undecided" and got["undecided_reason"] == "ABSTAINED" and got["agent"] is None
        assert got["abstention"]["type"] == "INCOMPLETE_READING" and got["router"] is None
        assert got["decided_by"] == "gate:INCOMPLETE_READING" and got["basis_kind"] is None
        assert got["abstention"]["by_status"]["UNREAD"] == 1 and got["abstention"]["by_status"]["MAPPED"] == 7
        assert [u["status"] for u in got["abstention"]["units"]] == ["UNREAD"]
    assert calls == []
    # the records of the units that were read are still reported
    assert got["records"]["agents"] and got["records"]["rules"]
    clean, _ = explain_lines(*STD, lookup=FakePlacement())
    assert rt.route_task(clean, task())["decision"] == "route" and calls == [1]
```

##### `test_T3_records_are_declared_text_with_witnesses_that_are_substrings_and_say_only_what_was_said` — before

```python
def test_T3_records_are_declared_text_with_witnesses_that_are_substrings_and_say_only_what_was_said(std):
    explained, text = explain_lines(*STD, source="/some/explanation.md")
    r = explained.records
    assert r.agents and r.rules
    for item in (*r.agents, *r.rules, *r.precedence, *r.lineage_relations):
        basis = item.basis
        assert basis.kind == "declared_text" and basis.source == "/some/explanation.md" and len(basis.witnesses) >= 1
        assert all(w in text and w.strip() for w in basis.witnesses)
    for agent in r.agents:
        assert agent.lineage is None and agent.adapter == "fake" and agent.model is None and agent.effort is None
        assert agent.note is None and agent.roles is None and agent.kinds is None and agent.concurrency is None
    for rule in r.rules:
        assert rule.reason is None and all(c.field != "independent_of" for c in rule.conditions)
    assert [c["agent"] for c in r.constructed] == [a.id for a in r.agents]
    assert all(c == {"agent": c["agent"], "field": "adapter", "value": "fake", "reason": "ADAPTER_NOT_STATED_ROUTE_ONLY"}
               for c in r.constructed)
    ar.build_routing_table(r.agents, r.rules, r.precedence, r.lineage_relations)   # the same record layer as any producer
```

##### `test_T3_records_are_declared_text_with_witnesses_that_are_substrings_and_say_only_what_was_said` — after

```python
def test_T3_records_are_declared_text_with_witnesses_that_are_substrings_and_say_only_what_was_said(std_placed):
    explained, text = explain_lines(*STD, source="/some/explanation.md", lookup=FakePlacement())
    r = explained.records
    assert r.agents and r.rules
    for item in (*r.agents, *r.rules, *r.precedence, *r.lineage_relations):
        basis = item.basis
        assert basis.kind == "declared_text" and basis.source == "/some/explanation.md" and len(basis.witnesses) >= 1
        assert all(w in text and w.strip() for w in basis.witnesses)
    for agent in r.agents:
        assert agent.lineage is None and agent.adapter == "fake" and agent.model is None and agent.effort is None
        assert agent.note is None and agent.roles is None and agent.kinds is None and agent.concurrency is None
    for rule in r.rules:
        assert rule.reason is None and all(c.field != "independent_of" for c in rule.conditions)
    assert [c["agent"] for c in r.constructed] == [a.id for a in r.agents]
    assert all(c == {"agent": c["agent"], "field": "adapter", "value": "fake", "reason": "ADAPTER_NOT_STATED_ROUTE_ONLY"}
               for c in r.constructed)
    ar.build_routing_table(r.agents, r.rules, r.precedence, r.lineage_relations)   # the same record layer as any producer
```

##### `test_T3_an_unconditional_assignment_is_the_fallback_and_nothing_else_is_made_one` — before

```python
def test_T3_an_unconditional_assignment_is_the_fallback_and_nothing_else_is_made_one(std):
    by_conditions = {tuple((c.field, c.value) for c in rule.conditions): rule for rule in std.records.rules}
    assert by_conditions[(("role", "implement"),)].fallback and by_conditions[(("role", "verify"),)].fallback
    assert by_conditions[(("role", "review"),)].fallback
    assert not by_conditions[(("kind", "test_authoring"),)].fallback and not by_conditions[(("kind", "attack"),)].fallback
    assert sorted(r.role for r in std.records.rules if r.fallback) == ["implement", "review", "verify"]
```

##### `test_T3_an_unconditional_assignment_is_the_fallback_and_nothing_else_is_made_one` — after

```python
def test_T3_an_unconditional_assignment_is_the_fallback_and_nothing_else_is_made_one(std_placed):
    by_conditions = {tuple((c.field, c.value) for c in rule.conditions): rule for rule in std_placed.records.rules}
    assert by_conditions[(("role", "implement"),)].fallback and by_conditions[(("role", "verify"),)].fallback
    assert by_conditions[(("role", "review"),)].fallback
    assert not by_conditions[(("kind", "test_authoring"),)].fallback and not by_conditions[(("kind", "attack"),)].fallback
    assert sorted(r.role for r in std_placed.records.rules if r.fallback) == ["implement", "review", "verify"]
```

##### `test_T3_two_unconditional_assignments_of_one_role_are_refused_by_the_record_layer_and_not_made_one` — before

```python
def test_T3_two_unconditional_assignments_of_one_role_are_refused_by_the_record_layer_and_not_made_one():
    explained, _ = explain_lines(("実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))),
                                 ("実装はルナに任せる。", rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))))
    got = out_of(explained)
    assert explained.table is None and explained.table_error[0] == "DUPLICATE_FALLBACK"
    assert got["abstention"]["type"] == "RECORD_REFUSED" and got["abstention"]["detail"] == "DUPLICATE_FALLBACK"
    assert got["records"]["table"] == "REFUSED:DUPLICATE_FALLBACK" and got["router"] is None and got["undecided_reason"] == "ABSTAINED"
```

##### `test_T3_two_unconditional_assignments_of_one_role_are_refused_by_the_record_layer_and_not_made_one` — after

```python
def test_T3_two_unconditional_assignments_of_one_role_are_refused_by_the_record_layer_and_not_made_one():
    explained, _ = explain_lines(("実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))),
                                 ("実装はルナに任せる。", rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))), lookup=FakePlacement())
    got = out_of(explained)
    assert explained.table is None and explained.table_error[0] == "DUPLICATE_FALLBACK"
    assert got["abstention"]["type"] == "RECORD_REFUSED" and got["abstention"]["detail"] == "DUPLICATE_FALLBACK"
    assert got["records"]["table"] == "REFUSED:DUPLICATE_FALLBACK" and got["router"] is None and got["undecided_reason"] == "ABSTAINED"
```

##### `test_T3_a_role_less_conditional_rule_needs_no_fallback_and_a_size_word_before_an_unknown_head_stops` — before

```python
def test_T3_a_role_less_conditional_rule_needs_no_fallback_and_a_size_word_before_an_unknown_head_stops():
    cond, _ = explain_lines(("大きなリファクタリングはハルに任せる。",
                             rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きなリファクタリング"}))),
                            ("ハルはレビューをやる。", do("ハル", "レビュー")))
    assert cond.table is not None and cond.abstention is None
    unknown, _ = explain_lines(("ハルは大きな占いをやる。", do("ハル", "大きな占い")))
    assert unknown.extraction.units[0].status == "WORK_TERM_UNKNOWN"
```

##### `test_T3_a_role_less_conditional_rule_needs_no_fallback_and_a_size_word_before_an_unknown_head_stops` — after

```python
def test_T3_a_role_less_conditional_rule_needs_no_fallback_and_a_size_word_before_an_unknown_head_stops():
    cond, _ = explain_lines(("大きなリファクタリングはハルに任せる。",
                             rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きなリファクタリング"}))),
                            ("ハルはレビューをやる。", do("ハル", "レビュー")), lookup=FakePlacement())
    assert cond.table is not None and cond.abstention is None
    unknown, _ = explain_lines(("ハルは大きな占いをやる。", do("ハル", "大きな占い")), lookup=FakePlacement())
    assert unknown.extraction.units[0].status == "WORK_TERM_UNKNOWN"
```

##### `test_T3_a_conditional_role_rule_without_the_roles_fallback_is_refused` — before

```python
def test_T3_a_conditional_role_rule_without_the_roles_fallback_is_refused():
    # "大きな" before the role word 実装 gives role=implement & size=large: a conditional rule of a role with no fallback
    explained, _ = explain_lines(("大きな実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな実装"}))))
    assert explained.extraction.units[0].status == "MAPPED"
    assert explained.table_error[0] == "MISSING_ROLE_DEFAULT"
    got = out_of(explained)
    assert got["abstention"]["type"] == "RECORD_REFUSED" and got["abstention"]["detail"] == "MISSING_ROLE_DEFAULT"
    assert explained.records.rules[0].fallback is False
```

##### `test_T3_a_conditional_role_rule_without_the_roles_fallback_is_refused` — after

```python
def test_T3_a_conditional_role_rule_without_the_roles_fallback_is_refused():
    # "大きな" before the role word 実装 gives role=implement & size=large: a conditional rule of a role with no fallback
    explained, _ = explain_lines(("大きな実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな実装"}))), lookup=FakePlacement())
    assert explained.extraction.units[0].status == "MAPPED"
    assert explained.table_error[0] == "MISSING_ROLE_DEFAULT"
    got = out_of(explained)
    assert got["abstention"]["type"] == "RECORD_REFUSED" and got["abstention"]["detail"] == "MISSING_ROLE_DEFAULT"
    assert explained.records.rules[0].fallback is False
```

##### `test_T3_only_says_roles_or_kinds_and_otherwise_they_stay_unsaid` — before

```python
def test_T3_only_says_roles_or_kinds_and_otherwise_they_stay_unsaid():
    explained, _ = explain_lines(("ウィックは検証だけをやる。", rd("ja", cl("やる", {"agent": "ウィック", "patient": "検証"}, quantifiers={"patient": "only"}))),
                                 ("ハルはテストだけを書く。", rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}, quantifiers={"patient": "only"}))),
                                 ("クイルは実装をやる。", do("クイル", "実装")))
    by_id = {a.id: a for a in explained.records.agents}
    assert by_id["ウィック"].roles == frozenset({"verify"}) and by_id["ウィック"].kinds is None
    assert by_id["ハル"].kinds == frozenset({"test_authoring"}) and by_id["ハル"].roles is None
    assert by_id["クイル"].roles is None and by_id["クイル"].kinds is None
```

##### `test_T3_only_says_roles_or_kinds_and_otherwise_they_stay_unsaid` — after

```python
def test_T3_only_says_roles_or_kinds_and_otherwise_they_stay_unsaid():
    explained, _ = explain_lines(("ウィックは検証だけをやる。", rd("ja", cl("やる", {"agent": "ウィック", "patient": "検証"}, quantifiers={"patient": "only"}))),
                                 ("ハルはテストだけを書く。", rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}, quantifiers={"patient": "only"}))),
                                 ("クイルは実装をやる。", do("クイル", "実装")), lookup=FakePlacement())
    by_id = {a.id: a for a in explained.records.agents}
    assert by_id["ウィック"].roles == frozenset({"verify"}) and by_id["ウィック"].kinds is None
    assert by_id["ハル"].kinds == frozenset({"test_authoring"}) and by_id["ハル"].roles is None
    assert by_id["クイル"].roles is None and by_id["クイル"].kinds is None
```

##### `test_T3_the_same_content_as_a_hand_written_table_gives_the_same_decisions` — before

```python
def test_T3_the_same_content_as_a_hand_written_table_gives_the_same_decisions(std):
    hand = ar.table_from_dicts(
        agents=[{"id": "ハル", "adapter": "fake", "witness": "w"}, {"id": "モモ", "adapter": "fake", "witness": "w"},
                {"id": "セキ", "adapter": "fake", "witness": "w"}],
        rules=[{"id": "A", "when": {"role": "implement"}, "prefer": ["ハル"], "fallback": True, "witness": "w"},
               {"id": "B", "when": {"kind": "test_authoring"}, "prefer": ["モモ"], "witness": "w"},
               {"id": "C", "when": {"role": "verify"}, "prefer": ["セキ"], "fallback": True, "witness": "w"},
               {"id": "D", "when": {"role": "review"}, "prefer": ["モモ"], "fallback": True, "witness": "w"},
               {"id": "E", "when": {"kind": "attack"}, "prefer": ["ハル"], "witness": "w"}],
        lineage_relations=[{"a": "ハル", "b": "セキ", "relation": "same", "witness": "w"}])
    requests = [dict(role="implement", kind="feature", size="medium"), dict(role="implement", kind="test_authoring", size="small"),
                dict(role="review", kind="review", size="medium"), dict(role="verify", kind="verification", size="medium"),
                dict(role="verify", kind="verification", size="medium", used_agents={"implement": ("ハル",)}),
                dict(role="verify", kind="verification", size="medium", used_agents={"implement": ("モモ",)}),
                dict(role="read", kind="read_large_file", size="large"), dict(role="verify", kind="attack", size="small",
                                                                             used_agents={"implement": ("モモ",)})]
    assert len(requests) >= 6
    for fields in requests:
        request = ar.RoutingRequest(job_id="j", **fields)
        assert ar.route(std.table, request).essence() == ar.route(hand, request).essence(), fields
```

##### `test_T3_the_same_content_as_a_hand_written_table_gives_the_same_decisions` — after

```python
def test_T3_the_same_content_as_a_hand_written_table_gives_the_same_decisions(std_placed):
    hand = ar.table_from_dicts(
        agents=[{"id": "ハル", "adapter": "fake", "witness": "w"}, {"id": "モモ", "adapter": "fake", "witness": "w"},
                {"id": "セキ", "adapter": "fake", "witness": "w"}],
        rules=[{"id": "A", "when": {"role": "implement"}, "prefer": ["ハル"], "fallback": True, "witness": "w"},
               {"id": "B", "when": {"kind": "test_authoring"}, "prefer": ["モモ"], "witness": "w"},
               {"id": "C", "when": {"role": "verify"}, "prefer": ["セキ"], "fallback": True, "witness": "w"},
               {"id": "D", "when": {"role": "review"}, "prefer": ["モモ"], "fallback": True, "witness": "w"},
               {"id": "E", "when": {"kind": "attack"}, "prefer": ["ハル"], "witness": "w"}],
        lineage_relations=[{"a": "ハル", "b": "セキ", "relation": "same", "witness": "w"}])
    requests = [dict(role="implement", kind="feature", size="medium"), dict(role="implement", kind="test_authoring", size="small"),
                dict(role="review", kind="review", size="medium"), dict(role="verify", kind="verification", size="medium"),
                dict(role="verify", kind="verification", size="medium", used_agents={"implement": ("ハル",)}),
                dict(role="verify", kind="verification", size="medium", used_agents={"implement": ("モモ",)}),
                dict(role="read", kind="read_large_file", size="large"), dict(role="verify", kind="attack", size="small",
                                                                             used_agents={"implement": ("モモ",)})]
    assert len(requests) >= 6
    for fields in requests:
        request = ar.RoutingRequest(job_id="j", **fields)
        assert ar.route(std_placed.table, request).essence() == ar.route(hand, request).essence(), fields
```

##### `test_router_call_passes_used_agents_only_no_chooser_and_the_first_names` — before

```python
def test_router_call_passes_used_agents_only_no_chooser_and_the_first_names(monkeypatch, std):
    seen = {}
    real = ar.route

    def spy(table, request, **kw):
        seen["request"], seen["kw"] = request, kw
        return real(table, request, **kw)

    monkeypatch.setattr(ar, "route", spy)
    got = rt.route_task(std, task(role="verify", kind="verification", already_used={"implement": "モモ"}, running={"ハル": 1}))
    request = seen["request"]
    assert request.used_agents == {"implement": ("モモ",)} and request.used_lineages == {} and request.in_use == {"ハル": 1}
    assert seen["kw"] == {} and request.job_id == "route-from-text"
    assert got["router"]["values"] == "declared"
```

##### `test_router_call_passes_used_agents_only_no_chooser_and_the_first_names` — after

```python
def test_router_call_passes_used_agents_only_no_chooser_and_the_first_names(monkeypatch, std_placed):
    seen = {}
    real = ar.route

    def spy(table, request, **kw):
        seen["request"], seen["kw"] = request, kw
        return real(table, request, **kw)

    monkeypatch.setattr(ar, "route", spy)
    got = rt.route_task(std_placed, task(role="verify", kind="verification", already_used={"implement": "モモ"}, running={"ハル": 1}))
    request = seen["request"]
    assert request.used_agents == {"implement": ("モモ",)} and request.used_lineages == {} and request.in_use == {"ハル": 1}
    assert seen["kw"] == {} and request.job_id == "route-from-text"
    assert got["router"]["values"] == "declared"
```

##### `test_router_reasons_are_written_through_from_the_routers_types` — before

```python
def test_router_reasons_are_written_through_from_the_routers_types(std):
    assert out_of(std, role="read", kind="read_large_file")["undecided_reason"] == "NOT_COVERED"
    assert out_of(std, role="verify", kind="verification", already_used={"implement": ["モモ"]})["undecided_reason"] == "ALL_EXCLUDED"
    tie, _ = explain_lines(("テストはハルがやる。", do("ハル", "テスト")), ("テストはルナがやる。", do("ルナ", "テスト")),
                           ("実装はクイルに任せる。", rd("ja", cl("任せる", {"recipient": "クイル", "patient": "実装"}))))
    got = out_of(tie, kind="test_authoring", size="small")
    assert got["undecided_reason"] == "TIE" and got["decided_by"] == "router:TESTIMONY_UNAVAILABLE" and got["basis_kind"] == "precedence"
    assert got["agent"] is None and got["abstention"] is None
    assert out_of(std, kind="test_authoring", size="small")["decided_by"] == "rule:T001_1"
```

##### `test_router_reasons_are_written_through_from_the_routers_types` — after

```python
def test_router_reasons_are_written_through_from_the_routers_types(std_placed):
    assert out_of(std_placed, role="read", kind="read_large_file")["undecided_reason"] == "NOT_COVERED"
    assert out_of(std_placed, role="verify", kind="verification", already_used={"implement": ["モモ"]})["undecided_reason"] == "ALL_EXCLUDED"
    tie, _ = explain_lines(("テストはハルがやる。", do("ハル", "テスト")), ("テストはルナがやる。", do("ルナ", "テスト")),
                           ("実装はクイルに任せる。", rd("ja", cl("任せる", {"recipient": "クイル", "patient": "実装"}))), lookup=FakePlacement())
    got = out_of(tie, kind="test_authoring", size="small")
    assert got["undecided_reason"] == "TIE" and got["decided_by"] == "router:TESTIMONY_UNAVAILABLE" and got["basis_kind"] == "precedence"
    assert got["agent"] is None and got["abstention"] is None
    assert out_of(std_placed, kind="test_authoring", size="small")["decided_by"] == "rule:T001_1"
```

##### `test_router_unknown_task_names_abstain_with_their_own_type` — before

```python
def test_router_unknown_task_names_abstain_with_their_own_type(std):
    for kw in ({"already_used": {"implement": ["ゲンバ"]}}, {"running": {"ゲンバ": 1}}):
        got = out_of(std, **kw)
        assert got["abstention"]["type"] == "TASK_NAME_UNKNOWN" and got["undecided_reason"] == "ABSTAINED" and got["agent"] is None
    named_only_in_a_comparison_only_sentence = explain_lines(*STD)[0]
    assert "ハル" in agent_ids(named_only_in_a_comparison_only_sentence)
```

##### `test_router_unknown_task_names_abstain_with_their_own_type` — after

```python
def test_router_unknown_task_names_abstain_with_their_own_type(std_placed):
    for kw in ({"already_used": {"implement": ["ゲンバ"]}}, {"running": {"ゲンバ": 1}}):
        got = out_of(std_placed, **kw)
        assert got["abstention"]["type"] == "TASK_NAME_UNKNOWN" and got["undecided_reason"] == "ABSTAINED" and got["agent"] is None
    named_only_in_a_comparison_only_sentence = explain_lines(*STD, lookup=FakePlacement())[0]
    assert "ハル" in agent_ids(named_only_in_a_comparison_only_sentence)
```

##### `test_constraint_prohibition_veto_does_not_try_the_next_agent` — before

```python
def test_constraint_prohibition_veto_does_not_try_the_next_agent(std):
    got = rt.route_task(with_constraints(std, [cons("prohibit", "ハル", role="implement")]), task())
    assert got["abstention"]["type"] == "PROHIBITION_VETO" and got["agent"] is None and got["undecided_reason"] == "ABSTAINED"
    assert got["router"]["agent_id"] == "ハル"        # what the router had decided is reported, and nobody else is chosen
```

##### `test_constraint_prohibition_veto_does_not_try_the_next_agent` — after

```python
def test_constraint_prohibition_veto_does_not_try_the_next_agent(std_placed):
    got = rt.route_task(with_constraints(std_placed, [cons("prohibit", "ハル", role="implement")]), task())
    assert got["abstention"]["type"] == "PROHIBITION_VETO" and got["agent"] is None and got["undecided_reason"] == "ABSTAINED"
    assert got["router"]["agent_id"] == "ハル"        # what the router had decided is reported, and nobody else is chosen
```

##### `test_constraint_human_and_wait_scopes_and_residual_and_conflict` — before

```python
def test_constraint_human_and_wait_scopes_and_residual_and_conflict(std):
    ok = rt.route_task(with_constraints(std, [cons("human", role="generate")]), task())
    assert ok["decision"] == "route"
    for kind, label in (("human", "HUMAN"), ("wait", "WAIT")):
        got = rt.route_task(with_constraints(std, [cons(kind, role="implement")]), task())
        assert got["undecided_reason"] == label and got["decided_by"] == f"constraint:{kind}" and got["agent"] is None
    residual = cons("wait", residual=True)
    assert rt.route_task(with_constraints(std, [residual]), task())["decision"] == "route"
    assert rt.route_task(with_constraints(std, [residual]), task(role="read", kind="read_large_file"))["undecided_reason"] == "WAIT"
    clash = rt.route_task(with_constraints(std, [cons("human", role="implement"), cons("wait", kind="feature")]), task())
    assert clash["abstention"]["type"] == "CONSTRAINT_CONFLICT" and clash["undecided_reason"] == "ABSTAINED"
```

##### `test_constraint_human_and_wait_scopes_and_residual_and_conflict` — after

```python
def test_constraint_human_and_wait_scopes_and_residual_and_conflict(std_placed):
    ok = rt.route_task(with_constraints(std_placed, [cons("human", role="generate")]), task())
    assert ok["decision"] == "route"
    for kind, label in (("human", "HUMAN"), ("wait", "WAIT")):
        got = rt.route_task(with_constraints(std_placed, [cons(kind, role="implement")]), task())
        assert got["undecided_reason"] == label and got["decided_by"] == f"constraint:{kind}" and got["agent"] is None
    residual = cons("wait", residual=True)
    assert rt.route_task(with_constraints(std_placed, [residual]), task())["decision"] == "route"
    assert rt.route_task(with_constraints(std_placed, [residual]), task(role="read", kind="read_large_file"))["undecided_reason"] == "WAIT"
    clash = rt.route_task(with_constraints(std_placed, [cons("human", role="implement"), cons("wait", kind="feature")]), task())
    assert clash["abstention"]["type"] == "CONSTRAINT_CONFLICT" and clash["undecided_reason"] == "ABSTAINED"
```

##### `test_constraint_independence_veto_for_two_other_roles` — before

```python
def test_constraint_independence_veto_for_two_other_roles():
    explained, _ = explain_lines(("ハルは検証をやる。", do("ハル", "検証")), ("モモはレビューをやる。", do("モモ", "レビュー")),
                                 ("ルナは実装をやる。", do("ルナ", "実装")),
                                 ("モモとルナは別の会社だ。", rd("ja", cl("だ", {"entity": "モモとルナ", "value": "同じ会社"}, "-"))))
    independent = cons("independent", roles=["implement", "review"])
    got = rt.route_task(with_constraints(explained, [independent]), task(role="review", kind="review", already_used={"implement": ["ハル"]}))
    assert got["abstention"]["type"] == "INDEPENDENCE_VETO" and got["agent"] is None      # モモ vs ハル: no relation is said
    got = rt.route_task(with_constraints(explained, [independent]), task(role="review", kind="review", already_used={"implement": ["ルナ"]}))
    assert got["decision"] == "route" and got["agent"] == "モモ"                            # モモ vs ルナ: said to be distinct
    got = rt.route_task(with_constraints(explained, [independent]), task(role="implement", kind="feature", already_used={"review": ["ハル"]}))
    assert got["abstention"]["type"] == "INDEPENDENCE_VETO"                                # the pair is read in both directions
    assert [(r.a, r.b, r.relation) for r in explained.records.lineage_relations] == [("モモ", "ルナ", "distinct")]
```

##### `test_constraint_independence_veto_for_two_other_roles` — after

```python
def test_constraint_independence_veto_for_two_other_roles():
    explained, _ = explain_lines(("ハルは検証をやる。", do("ハル", "検証")), ("モモはレビューをやる。", do("モモ", "レビュー")),
                                 ("ルナは実装をやる。", do("ルナ", "実装")),
                                 ("モモとルナは別の会社だ。", rd("ja", cl("だ", {"entity": "モモとルナ", "value": "同じ会社"}, "-"))), lookup=FakePlacement())
    independent = cons("independent", roles=["implement", "review"])
    got = rt.route_task(with_constraints(explained, [independent]), task(role="review", kind="review", already_used={"implement": ["ハル"]}))
    assert got["abstention"]["type"] == "INDEPENDENCE_VETO" and got["agent"] is None      # モモ vs ハル: no relation is said
    got = rt.route_task(with_constraints(explained, [independent]), task(role="review", kind="review", already_used={"implement": ["ルナ"]}))
    assert got["decision"] == "route" and got["agent"] == "モモ"                            # モモ vs ルナ: said to be distinct
    got = rt.route_task(with_constraints(explained, [independent]), task(role="implement", kind="feature", already_used={"review": ["ハル"]}))
    assert got["abstention"]["type"] == "INDEPENDENCE_VETO"                                # the pair is read in both directions
    assert [(r.a, r.b, r.relation) for r in explained.records.lineage_relations] == [("モモ", "ルナ", "distinct")]
```

##### `test_handoff2_a_role_less_attack_rule_and_a_verify_job_do_not_make_an_independence_cycle` — before

```python
def test_handoff2_a_role_less_attack_rule_and_a_verify_job_do_not_make_an_independence_cycle(std):
    assert std.table is not None
    got = out_of(std, role="verify", kind="attack", already_used={"implement": ["モモ"]})
    assert got["records"]["table"] == "BUILT"
    assert all(c.field != "independent_of" for rule in std.records.rules for c in rule.conditions)
```

##### `test_handoff2_a_role_less_attack_rule_and_a_verify_job_do_not_make_an_independence_cycle` — after

```python
def test_handoff2_a_role_less_attack_rule_and_a_verify_job_do_not_make_an_independence_cycle(std_placed):
    assert std_placed.table is not None
    got = out_of(std_placed, role="verify", kind="attack", already_used={"implement": ["モモ"]})
    assert got["records"]["table"] == "BUILT"
    assert all(c.field != "independent_of" for rule in std_placed.records.rules for c in rule.conditions)
```

##### `test_handoff3_a_role_less_closed_choice_rule_is_chosen_for_an_answer_job` — before

```python
def test_handoff3_a_role_less_closed_choice_rule_is_chosen_for_an_answer_job():
    explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                 ("ハルはレビューをやる。", do("ハル", "レビュー")),
                                 ("ルナは回答をやる。", do("ルナ", "回答")))
    # a role-less rule is made from a kind word; the closed choice has no word in the table, so build the same record by hand
    rule = ar.RoutingRule("T900_1", (ar.Condition("kind", "closed_choice"),), ("ルナ",), None, ar.Basis.text("x", "w"))
    records = dataclasses.replace(explained.records, rules=tuple(explained.records.rules) + (rule,))
    table = ar.build_routing_table(records.agents, records.rules, records.precedence, records.lineage_relations)
    decision = ar.route(table, ar.RoutingRequest(job_id="j", role="answer", kind="closed_choice", size="small"))
    assert decision.decided and decision.agent_id == "ルナ"
```

##### `test_handoff3_a_role_less_closed_choice_rule_is_chosen_for_an_answer_job` — after

```python
def test_handoff3_a_role_less_closed_choice_rule_is_chosen_for_an_answer_job():
    explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                 ("ハルはレビューをやる。", do("ハル", "レビュー")),
                                 ("ルナは回答をやる。", do("ルナ", "回答")), lookup=FakePlacement())
    # a role-less rule is made from a kind word; the closed choice has no word in the table, so build the same record by hand
    rule = ar.RoutingRule("T900_1", (ar.Condition("kind", "closed_choice"),), ("ルナ",), None, ar.Basis.text("x", "w"))
    records = dataclasses.replace(explained.records, rules=tuple(explained.records.rules) + (rule,))
    table = ar.build_routing_table(records.agents, records.rules, records.precedence, records.lineage_relations)
    decision = ar.route(table, ar.RoutingRequest(job_id="j", role="answer", kind="closed_choice", size="small"))
    assert decision.decided and decision.agent_id == "ルナ"
```

##### `test_output_keys_order_and_basis_kinds` — before

```python
def test_output_keys_order_and_basis_kinds(std):
    got = out_of(std)
    assert list(got) == ["schema", "decision", "agent", "undecided_reason", "abstention", "basis_kind", "evidence", "decided_by",
                         "records", "relations", "reading", "router", "ignored_fields", "task"]
    assert list(got["records"]) == ["agents", "rules", "precedence", "lineage_relations", "aliases", "constraints", "constructed", "table"]
    assert got["schema"] == rt.SCHEMA and got["reading"]["lookup"] == "stub-no-placement/1"
    assert got["basis_kind"] in rt.BASIS_KINDS_OUT and got["evidence"] == ["ハルは実装をやる。"]
    assert out_of(std, kind="test_authoring", size="small")["basis_kind"] == "condition"
    for undecided in (out_of(std, role="read", kind="read_large_file"), out_of(std, role="verify", kind="verification",
                                                                                   already_used={"implement": ["ハル"]})):
        assert undecided["undecided_reason"] in rt.UNDECIDED_OUT and undecided["basis_kind"] in rt.BASIS_KINDS_OUT + (None,)
    assert out_of(std, role="read", kind="read_large_file")["basis_kind"] == "silence"
    assert json.loads(rt.dumps(got)) == got
```

##### `test_output_keys_order_and_basis_kinds` — after

```python
def test_output_keys_order_and_basis_kinds(std_placed):
    got = out_of(std_placed)
    assert list(got) == ["schema", "decision", "agent", "undecided_reason", "abstention", "basis_kind", "evidence", "decided_by",
                         "records", "relations", "reading", "router", "ignored_fields", "task"]
    assert list(got["records"]) == ["agents", "rules", "precedence", "lineage_relations", "aliases", "constraints", "constructed", "table"]
    assert got["schema"] == rt.SCHEMA and got["reading"]["lookup"] == "test-fake-placement/1"      # W5-d2 (K2): the explanation was read under the made-up placement; the id of "no placement" is held by test_w5d2_k2_the_standard_explanation_with_and_without_a_placement
    assert got["basis_kind"] in rt.BASIS_KINDS_OUT and got["evidence"] == ["ハルは実装をやる。"]
    assert out_of(std_placed, kind="test_authoring", size="small")["basis_kind"] == "condition"
    for undecided in (out_of(std_placed, role="read", kind="read_large_file"), out_of(std_placed, role="verify", kind="verification",
                                                                                   already_used={"implement": ["ハル"]})):
        assert undecided["undecided_reason"] in rt.UNDECIDED_OUT and undecided["basis_kind"] in rt.BASIS_KINDS_OUT + (None,)
    assert out_of(std_placed, role="read", kind="read_large_file")["basis_kind"] == "silence"
    assert json.loads(rt.dumps(got)) == got
```

#### `tests/test_routing_from_text_entry.py` (before = git show c875ed3:tests/test_routing_from_text_entry.py)

Added (helpers / tests, not amendments): none

##### `entry` — before

```python
def entry(explanation, task, seed="0", module=("-m", "verantyx.cli", "route")):
    env = dict(os.environ)
    env.update({"PYTHONPATH": ROOT, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": seed})
    argument = task if isinstance(task, str) else json.dumps(task, ensure_ascii=False)
    return subprocess.run([sys.executable, *module, "--explanation", explanation, "--task", argument],
                          capture_output=True, text=True, env=env, cwd=ROOT)
```

##### `entry` — after

```python
def entry(explanation, task, seed="0", module=("-m", "verantyx.cli", "route")):
    env = dict(os.environ)
    env.pop("VERA_PLACEMENT", None)      # W5-d2: the entry reads VERA_PLACEMENT, so a variable of the caller must not decide what these tests (written for "no placement") see
    env.update({"PYTHONPATH": ROOT, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": seed})
    argument = task if isinstance(task, str) else json.dumps(task, ensure_ascii=False)
    return subprocess.run([sys.executable, *module, "--explanation", explanation, "--task", argument],
                          capture_output=True, text=True, env=env, cwd=ROOT)
```

##### `test_T1_the_entry_returns_the_documented_shape_and_routes_through_the_real_reader` — before

```python
def test_T1_the_entry_returns_the_documented_shape_and_routes_through_the_real_reader():
    # W5-a round 3 (auditor's decision B3 (β); docs/READING_SOUNDNESS.md K64): the entry no longer reads an を-phrase as the thing acted on when
    # the subject has no person evidence and the predicate is in none of the reader's classes with an を-object (書く, 確かめる: the corpus
    # table alone calls them transitive). Two sentences of r1.md are not read, so the gate abstains and nobody is routed. The name is kept;
    # the old expectation is kept in K64 in full.
    proc = entry(r1(), TASK)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count("\n") == 1                      # one line
    out = json.loads(proc.stdout)
    assert list(out) == KEYS
    assert (out["decision"], out["agent"], out["undecided_reason"]) == ("undecided", None, "ABSTAINED")
    assert out["decided_by"] == "gate:INCOMPLETE_READING" and out["router"] is None
    assert out["abstention"]["type"] == "INCOMPLETE_READING"
    assert out["abstention"]["detail"] == "2 of 8 units were not read and mapped; no job is routed"
    assert out["abstention"]["units"] == [
        {"index": 1, "status": "UNREAD", "text": "モモがテストを書く。", "reasons": ["AGENT_EVIDENCE_MISSING:モモ"]},
        {"index": 2, "status": "UNREAD", "text": "セキがコードを確かめる。", "reasons": ["AGENT_EVIDENCE_MISSING:セキ"]}]
    assert out["evidence"] == ["モモがテストを書く。", "セキがコードを確かめる。"]
    assert out["reading"]["by_status"] == {"MAPPED": 5, "COMPARISON_ONLY": 1, "UNREAD": 2, "PREDICATE_CLASS_UNKNOWN": 0, "WORK_TERM_UNKNOWN": 0,
                                           "AMBIGUOUS_RELATION": 0, "NAME_UNRESOLVED": 0, "CONTRADICTION": 0, "UNREPRESENTABLE": 0}
    assert out["reading"]["lookup"] == "stub-no-placement/1"
    assert all(a["basis"]["kind"] == "declared_text" and a["lineage"] is None for a in out["records"]["agents"])
```

##### `test_T1_the_entry_returns_the_documented_shape_and_routes_through_the_real_reader` — after

```python
def test_T1_the_entry_returns_the_documented_shape_and_routes_through_the_real_reader():
    # W5-d2 (auditor's ruling B1, K2): the name is kept; the expectation is the contract of W5-d. This entry has no placement (the variable is taken off in entry()), and since
    # W5-d (R-J1) a Japanese name that no naming sentence introduced is not verified without a placement: the units that were MAPPED are NAME_UNRESOLVED
    # (NAME_UNVERIFIED:<name>:NO_PLACEMENT) and nobody is routed. The earlier text of this test (W5-a round 3: two sentences UNREAD, five MAPPED) is kept in the
    # docs (w5d2-amended) and in K64 of docs/READING_SOUNDNESS.md.
    proc = entry(r1(), TASK)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.count("\n") == 1                      # one line
    out = json.loads(proc.stdout)
    assert list(out) == KEYS
    assert (out["decision"], out["agent"], out["undecided_reason"]) == ("undecided", None, "ABSTAINED")
    assert out["decided_by"] == "gate:INCOMPLETE_READING" and out["router"] is None
    assert out["abstention"]["type"] == "INCOMPLETE_READING"
    assert out["abstention"]["detail"] == "8 of 8 units were not read and mapped; no job is routed"
    assert out["abstention"]["units"] == [
        {"index": 0, "status": "NAME_UNRESOLVED", "text": "ハルは実装をやる。", "reasons": ["NAME_UNVERIFIED:ハル:NO_PLACEMENT"]},
        {"index": 1, "status": "UNREAD", "text": "モモがテストを書く。", "reasons": ["AGENT_EVIDENCE_MISSING:モモ"]},
        {"index": 2, "status": "UNREAD", "text": "セキがコードを確かめる。", "reasons": ["AGENT_EVIDENCE_MISSING:セキ"]},
        {"index": 3, "status": "NAME_UNRESOLVED", "text": "モモは検証をやらない。", "reasons": ["NAME_UNVERIFIED:モモ:NO_PLACEMENT"]},
        {"index": 4, "status": "NAME_UNRESOLVED", "text": "レビューはモモがやる。", "reasons": ["NAME_UNVERIFIED:モモ:NO_PLACEMENT"]},
        {"index": 5, "status": "NAME_UNRESOLVED", "text": "ハルが攻撃をやる。", "reasons": ["NAME_UNVERIFIED:ハル:NO_PLACEMENT"]},
        {"index": 6, "status": "NAME_UNRESOLVED", "text": "ハルとセキは同じ会社だ。", "reasons": ["NAME_UNVERIFIED:ハル:NO_PLACEMENT"]},
        {"index": 7, "status": "NAME_UNRESOLVED", "text": "モモはハルより速い。", "reasons": ["NAME_UNVERIFIED:モモ:NO_PLACEMENT"]}]
    assert out["evidence"] == ["ハルは実装をやる。", "モモがテストを書く。", "セキがコードを確かめる。", "モモは検証をやらない。", "レビューはモモがやる。",
                               "ハルが攻撃をやる。", "ハルとセキは同じ会社だ。", "モモはハルより速い。"]
    assert out["reading"]["by_status"] == {"MAPPED": 0, "COMPARISON_ONLY": 0, "UNREAD": 2, "PREDICATE_CLASS_UNKNOWN": 0, "WORK_TERM_UNKNOWN": 0,
                                           "AMBIGUOUS_RELATION": 0, "NAME_UNRESOLVED": 6, "CONTRADICTION": 0, "UNREPRESENTABLE": 0}
    assert out["reading"]["lookup"] == "stub-no-placement/1"
    assert out["records"]["agents"] == []                      # nothing was mapped, so no agent record exists
    assert all(a["basis"]["kind"] == "declared_text" and a["lineage"] is None for a in out["records"]["agents"])
```

#### `tests/test_routing_from_text_regress.py` (before = git show c875ed3:tests/test_routing_from_text_regress.py)

Added (helpers / tests, not amendments): none

##### `run` — before

```python
def run(text, job):
    return rt.route_task(rt.explain(text, "probe.md"), dict(job))
```

##### `run` — after

```python
def run(text, job, lookup=None):      # W5-d2: ``lookup`` (default None = as before) is the placement
    return rt.route_task(rt.explain(text, "probe.md", lookup=lookup), dict(job))
```

##### `statuses` — before

```python
def statuses(text):
    return [(u.status, u.reasons) for u in rt.explain(text, "probe.md").extraction.units]
```

##### `statuses` — after

```python
def statuses(text, lookup=None):      # W5-d2: ``lookup`` (default None = as before) is the placement
    return [(u.status, u.reasons) for u in rt.explain(text, "probe.md", lookup=lookup).extraction.units]
```

##### `test_M1_two_agents_that_are_each_east_co_are_not_merged_and_nobody_is_routed` — before

```python
def test_M1_two_agents_that_are_each_east_co_are_not_merged_and_nobody_is_routed():
    assert [s for s, _ in statuses(M1_TEXT)] == ["MAPPED", "MAPPED", "AMBIGUOUS_RELATION", "AMBIGUOUS_RELATION"]
    for job in (REVIEW, IMPLEMENT):
        got = run(M1_TEXT, job)
        assert got["decision"] == "undecided" and got["agent"] is None and got["undecided_reason"] == "ABSTAINED"
        assert got["abstention"]["type"] == "INCOMPLETE_READING" and got["abstention"]["by_status"]["AMBIGUOUS_RELATION"] == 2
        assert got["records"]["aliases"] == [] and [a["id"] for a in got["records"]["agents"]] == ["ハル", "セキ"]
        assert sorted(item["data"]["reading"] for item in got["relations"] if item["held"]) == [
            "COPULA_IS_ANOTHER_NAME", "COPULA_IS_ANOTHER_NAME",
            "COPULA_IS_A_PREDICATE_OF_THE_FIRST", "COPULA_IS_A_PREDICATE_OF_THE_FIRST"]
```

##### `test_M1_two_agents_that_are_each_east_co_are_not_merged_and_nobody_is_routed` — after

```python
def test_M1_two_agents_that_are_each_east_co_are_not_merged_and_nobody_is_routed():
    assert [s for s, _ in statuses(M1_TEXT, lookup=FakePlacement())] == ["MAPPED", "MAPPED", "AMBIGUOUS_RELATION", "AMBIGUOUS_RELATION"]
    for job in (REVIEW, IMPLEMENT):
        got = run(M1_TEXT, job, lookup=FakePlacement())
        assert got["decision"] == "undecided" and got["agent"] is None and got["undecided_reason"] == "ABSTAINED"
        assert got["abstention"]["type"] == "INCOMPLETE_READING" and got["abstention"]["by_status"]["AMBIGUOUS_RELATION"] == 2
        assert got["records"]["aliases"] == [] and [a["id"] for a in got["records"]["agents"]] == ["ハル", "セキ"]
        assert sorted(item["data"]["reading"] for item in got["relations"] if item["held"]) == [
            "COPULA_IS_ANOTHER_NAME", "COPULA_IS_ANOTHER_NAME",
            "COPULA_IS_A_PREDICATE_OF_THE_FIRST", "COPULA_IS_A_PREDICATE_OF_THE_FIRST"]
```

##### `test_M3_the_non_past_sentence_of_the_same_form_is_still_routed` — before

```python
def test_M3_the_non_past_sentence_of_the_same_form_is_still_routed():
    got = run("ハルが実装をやる。\n", IMPLEMENT)
    assert (got["decision"], got["agent"]) == ("route", "ハル")
    got = run("Rook reviews the code.\n", REVIEW)
    assert (got["decision"], got["agent"]) == ("route", "Rook")
```

##### `test_M3_the_non_past_sentence_of_the_same_form_is_still_routed` — after

```python
def test_M3_the_non_past_sentence_of_the_same_form_is_still_routed():
    got = run("ハルが実装をやる。\n", IMPLEMENT, lookup=FakePlacement())
    assert (got["decision"], got["agent"]) == ("route", "ハル")
    got = run("Rook reviews the code.\n", REVIEW, lookup=FakePlacement())
    assert (got["decision"], got["agent"]) == ("route", "Rook")
```

#### `tests/test_routing_from_text_w5b.py` (before = git show c875ed3:tests/test_routing_from_text_w5b.py)

Added (helpers / tests, not amendments): none

##### `test_the_determiner_test_is_for_english_only_and_not_for_a_naming_sentence` — before

```python
def test_the_determiner_test_is_for_english_only_and_not_for_a_naming_sentence():
    explained = explain("ミラは実装をやる。\n", {"ミラは実装をやる。": ja_do("ミラ")})
    assert [u.status for u in explained.extraction.units] == ["MAPPED"]
    alias = rd("en", cl("call", {"patient": "Mira", "result": "Crew"}))
    sent = "Call Mira the Crew."
    ex = explain(f"Mira reviews code.\n{sent}\n", {"Mira reviews code.": en_review("Mira"), sent: alias})
    assert [u.status for u in ex.extraction.units] == ["MAPPED", "MAPPED"]
```

##### `test_the_determiner_test_is_for_english_only_and_not_for_a_naming_sentence` — after

```python
def test_the_determiner_test_is_for_english_only_and_not_for_a_naming_sentence():
    explained = explain("ミラは実装をやる。\n", {"ミラは実装をやる。": ja_do("ミラ")}, lookup=FakePlacement())
    assert [u.status for u in explained.extraction.units] == ["MAPPED"]
    alias = rd("en", cl("call", {"patient": "Mira", "result": "Crew"}))
    sent = "Call Mira the Crew."
    ex = explain(f"Mira reviews code.\n{sent}\n", {"Mira reviews code.": en_review("Mira"), sent: alias}, lookup=FakePlacement())
    assert [u.status for u in ex.extraction.units] == ["MAPPED", "MAPPED"]
```

##### `test_without_a_placement_nothing_is_checked_and_that_is_counted_not_hidden` — before

```python
def test_without_a_placement_nothing_is_checked_and_that_is_counted_not_hidden():
    explained = explain("ソラは実装をやる。\n", {"ソラは実装をやる。": ja_do("ソラ")})
    assert [u.status for u in explained.extraction.units] == ["MAPPED"]
    check = route(explained, role="implement", kind="feature")["reading"]["common_noun_check"]
    assert check == {"lookup": "stub-no-placement/1", "checked": 0, "not_checked": 1, "flagged": 0, "introduced_by_naming": 0}
```

##### `test_without_a_placement_nothing_is_checked_and_that_is_counted_not_hidden` — after

```python
def test_without_a_placement_nothing_is_checked_and_that_is_counted_not_hidden(monkeypatch):
    # W5-d2 (auditor's ruling B1, K2): the NAME IS FROM THE OLD CONTRACT (a Japanese name with no placement was routed and counted as "not checked"). The contract now
    # (W5-d, R-J1): with no placement a Japanese name that no naming sentence introduced is not verified -> the unit is NAME_UNRESOLVED (NAME_UNVERIFIED:<name>:NO_PLACEMENT)
    # and the text abstains; the check is still counted, not hidden.
    monkeypatch.delenv("VERA_PLACEMENT", raising=False)
    explained = explain("ソラは実装をやる。\n", {"ソラは実装をやる。": ja_do("ソラ")})
    (unit,) = explained.extraction.units
    assert unit.status == "NAME_UNRESOLVED" and unit.reasons == ["NAME_UNVERIFIED:ソラ:NO_PLACEMENT"]
    got = route(explained, role="implement", kind="feature")
    assert got["agent"] is None and got["abstention"]["type"] == "INCOMPLETE_READING"
    check = got["reading"]["common_noun_check"]
    assert check == {"lookup": "stub-no-placement/1", "checked": 0, "not_checked": 1, "flagged": 0, "introduced_by_naming": 0}
```

##### `test_a_japanese_addendum_without_a_marker_keeps_both_statements` — before

```python
@pytest.mark.parametrize("label", ["追記：", "追伸：", "追記（翌日）："])
def test_a_japanese_addendum_without_a_marker_keeps_both_statements(label):
    first, second = "実装はミラに任せる。", "実装はルナに任せる。"
    explained = explain(f"{first}\n{label}{second}\n", {first: ja_assign("ミラ"), second: ja_assign("ルナ")})
    assert explained.extraction.auto_resolved == 0 and [r.superseded_by for r in explained.extraction.relations] == [None, None]
    assert route(explained, role="implement", kind="feature")["agent"] is None
```

##### `test_a_japanese_addendum_without_a_marker_keeps_both_statements` — after

```python
@pytest.mark.parametrize("label", ["追記：", "追伸：", "追記（翌日）："])
def test_a_japanese_addendum_without_a_marker_keeps_both_statements(label):
    first, second = "実装はミラに任せる。", "実装はルナに任せる。"
    explained = explain(f"{first}\n{label}{second}\n", {first: ja_assign("ミラ"), second: ja_assign("ルナ")}, lookup=FakePlacement())
    assert explained.extraction.auto_resolved == 0 and [r.superseded_by for r in explained.extraction.relations] == [None, None]
    assert route(explained, role="implement", kind="feature")["agent"] is None
```

##### `test_a_japanese_addendum_with_a_replacement_word_replaces` — before

```python
@pytest.mark.parametrize("second,reading_name", [("やっぱり実装はルナに任せる。", "ルナ"), ("実装はミラではなくルナに任せる。", "ルナ")])
def test_a_japanese_addendum_with_a_replacement_word_replaces(second, reading_name):
    first = "実装はミラに任せる。"
    explained = explain(f"{first}\n追記：{second}\n", {first: ja_assign("ミラ"), second: ja_assign(reading_name)})
    assert explained.extraction.auto_resolved == 1
    assert route(explained, role="implement", kind="feature")["agent"] == "ルナ"
```

##### `test_a_japanese_addendum_with_a_replacement_word_replaces` — after

```python
@pytest.mark.parametrize("second,reading_name", [("やっぱり実装はルナに任せる。", "ルナ"), ("実装はミラではなくルナに任せる。", "ルナ")])
def test_a_japanese_addendum_with_a_replacement_word_replaces(second, reading_name):
    first = "実装はミラに任せる。"
    explained = explain(f"{first}\n追記：{second}\n", {first: ja_assign("ミラ"), second: ja_assign(reading_name)}, lookup=FakePlacement())
    assert explained.extraction.auto_resolved == 1
    assert route(explained, role="implement", kind="feature")["agent"] == "ルナ"
```

##### `test_the_other_labels_replace_as_before_without_any_marker` — before

```python
@pytest.mark.parametrize("label,sentence", [("訂正：", "実装はルナに任せる。"), ("更新：", "実装はルナに任せる。")])
def test_the_other_labels_replace_as_before_without_any_marker(label, sentence):
    first = "実装はミラに任せる。"
    explained = explain(f"{first}\n{label}{sentence}\n", {first: ja_assign("ミラ"), sentence: ja_assign("ルナ")})
    assert explained.extraction.auto_resolved == 1 and route(explained, role="implement", kind="feature")["agent"] == "ルナ"
    assert explained.extraction.additions_kept == 0
```

##### `test_the_other_labels_replace_as_before_without_any_marker` — after

```python
@pytest.mark.parametrize("label,sentence", [("訂正：", "実装はルナに任せる。"), ("更新：", "実装はルナに任せる。")])
def test_the_other_labels_replace_as_before_without_any_marker(label, sentence):
    first = "実装はミラに任せる。"
    explained = explain(f"{first}\n{label}{sentence}\n", {first: ja_assign("ミラ"), sentence: ja_assign("ルナ")}, lookup=FakePlacement())
    assert explained.extraction.auto_resolved == 1 and route(explained, role="implement", kind="feature")["agent"] == "ルナ"
    assert explained.extraction.additions_kept == 0
```

##### `test_C3_without_a_marker_relation_override_replaces_exactly_the_same_scope_and_counts_it_both_statements_stand` — before

```python
def test_C3_without_a_marker_relation_override_replaces_exactly_the_same_scope_and_counts_it_both_statements_stand():
    table = {"実装はハルに任せる。": ja_assign("ハル"), "実装はルナに任せる。": ja_assign("ルナ")}
    explained = explain("実装はハルに任せる。\n追記：実装はルナに任せる。\n", table)
    assert _units(explained) == ["MAPPED", "MAPPED"]
    assert explained.extraction.auto_resolved == 0
    assert [r.superseded_by for r in explained.extraction.relations] == [None, None]
    assert [r.preference for r in explained.records.rules] == [("ハル",), ("ルナ",)]
    result = route(explained, role="implement", kind="feature")
    assert result["agent"] is None
    assert result["abstention"]["type"] == "RECORD_REFUSED" and result["abstention"]["detail"] == "DUPLICATE_FALLBACK"
```

##### `test_C3_without_a_marker_relation_override_replaces_exactly_the_same_scope_and_counts_it_both_statements_stand` — after

```python
def test_C3_without_a_marker_relation_override_replaces_exactly_the_same_scope_and_counts_it_both_statements_stand():
    table = {"実装はハルに任せる。": ja_assign("ハル"), "実装はルナに任せる。": ja_assign("ルナ")}
    explained = explain("実装はハルに任せる。\n追記：実装はルナに任せる。\n", table, lookup=FakePlacement())
    assert _units(explained) == ["MAPPED", "MAPPED"]
    assert explained.extraction.auto_resolved == 0
    assert [r.superseded_by for r in explained.extraction.relations] == [None, None]
    assert [r.preference for r in explained.records.rules] == [("ハル",), ("ルナ",)]
    result = route(explained, role="implement", kind="feature")
    assert result["agent"] is None
    assert result["abstention"]["type"] == "RECORD_REFUSED" and result["abstention"]["detail"] == "DUPLICATE_FALLBACK"
```

##### `test_C3_without_a_marker_relation_override_that_overlaps_only_partly_is_held_as_ambiguous_both_declarations_stand` — before

```python
def test_C3_without_a_marker_relation_override_that_overlaps_only_partly_is_held_as_ambiguous_both_declarations_stand():
    table = {"大きなリファクタリングはハルに任せる。": ja_assign("ハル", "大きなリファクタリング"),
             "実装はルナに任せる。": ja_assign("ルナ")}
    explained = explain("大きなリファクタリングはハルに任せる。\n追記：実装はルナに任せる。\n", table)
    assert _units(explained) == ["MAPPED", "MAPPED"]
    assert explained.extraction.auto_resolved == 0
    assert route(explained, role="implement", kind="feature")["agent"] == "ルナ"        # the two declarations have different scopes: both stay
```

##### `test_C3_without_a_marker_relation_override_that_overlaps_only_partly_is_held_as_ambiguous_both_declarations_stand` — after

```python
def test_C3_without_a_marker_relation_override_that_overlaps_only_partly_is_held_as_ambiguous_both_declarations_stand():
    table = {"大きなリファクタリングはハルに任せる。": ja_assign("ハル", "大きなリファクタリング"),
             "実装はルナに任せる。": ja_assign("ルナ")}
    explained = explain("大きなリファクタリングはハルに任せる。\n追記：実装はルナに任せる。\n", table, lookup=FakePlacement())
    assert _units(explained) == ["MAPPED", "MAPPED"]
    assert explained.extraction.auto_resolved == 0
    assert route(explained, role="implement", kind="feature")["agent"] == "ルナ"        # the two declarations have different scopes: both stay
```

##### `test_C3_without_a_marker_an_override_of_another_kind_about_another_name_is_held_not_a_replacement_both_statements_stand` — before

```python
def test_C3_without_a_marker_an_override_of_another_kind_about_another_name_is_held_not_a_replacement_both_statements_stand():
    table = {"ハルはテストを書く。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"})),
             "モモはテストを書かない。": rd("ja", cl("書く", {"agent": "モモ", "patient": "テスト"}, "-")),
             "ハルはテストを書かない。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}, "-"))}
    # another name, another kind: with no marker the addendum is added next to the earlier statement
    explained = explain("ハルはテストを書く。\n追記：モモはテストを書かない。\n", table)
    assert _units(explained) == ["MAPPED", "MAPPED"] and explained.extraction.auto_resolved == 0
    assert route(explained, role="implement", kind="test_authoring")["agent"] == "ハル"
    # the same name, the opposite polarity: a contradiction that stays a contradiction (nothing is replaced, nothing is chosen)
    explained = explain("ハルはテストを書く。\n追記：ハルはテストを書かない。\n", table)
    units = explained.extraction.units
    assert [u.status for u in units] == ["CONTRADICTION", "CONTRADICTION"]
    assert [u.reasons[0] for u in units] == ["CONTRADICTS:R002", "CONTRADICTS:R001"]
    assert route(explained, role="implement", kind="test_authoring")["abstention"]["type"] == "INCOMPLETE_READING"
```

##### `test_C3_without_a_marker_an_override_of_another_kind_about_another_name_is_held_not_a_replacement_both_statements_stand` — after

```python
def test_C3_without_a_marker_an_override_of_another_kind_about_another_name_is_held_not_a_replacement_both_statements_stand():
    table = {"ハルはテストを書く。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"})),
             "モモはテストを書かない。": rd("ja", cl("書く", {"agent": "モモ", "patient": "テスト"}, "-")),
             "ハルはテストを書かない。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}, "-"))}
    # another name, another kind: with no marker the addendum is added next to the earlier statement
    explained = explain("ハルはテストを書く。\n追記：モモはテストを書かない。\n", table, lookup=FakePlacement())
    assert _units(explained) == ["MAPPED", "MAPPED"] and explained.extraction.auto_resolved == 0
    assert route(explained, role="implement", kind="test_authoring")["agent"] == "ハル"
    # the same name, the opposite polarity: a contradiction that stays a contradiction (nothing is replaced, nothing is chosen)
    explained = explain("ハルはテストを書く。\n追記：ハルはテストを書かない。\n", table, lookup=FakePlacement())
    units = explained.extraction.units
    assert [u.status for u in units] == ["CONTRADICTION", "CONTRADICTION"]
    assert [u.reasons[0] for u in units] == ["CONTRADICTS:R002", "CONTRADICTS:R001"]
    assert route(explained, role="implement", kind="test_authoring")["abstention"]["type"] == "INCOMPLETE_READING"
```

#### `tests/attack/test_attack_w5b_wave2.py` (before = the attack original attacks/W5-b/test_attack_w5b_wave2.py (first line dropped))

Added (helpers / tests, not amendments): `_AllUnplaced`

##### `test_yappari_sonomama_does_not_turn_an_addendum_into_replacement` — before

```python
def test_yappari_sonomama_does_not_turn_an_addendum_into_replacement():
    first = "実装はハルに任せる。"
    second = "やっぱりそのまま、実装はハルに任せる。"
    explained = rt.explain(f"{first}\n追記：{second}\n", "attack.md", reader=_reading_for_assignment)
    actual = {"statuses": [unit.status for unit in explained.extraction.units],
              "auto_resolved": explained.extraction.auto_resolved,
              "superseded_by": [relation.superseded_by for relation in explained.extraction.relations],
              "additions_kept": explained.extraction.additions_kept}
    print(f"OBS R2 {json.dumps(actual, ensure_ascii=False, sort_keys=True)}")
    assert actual == {"statuses": ["MAPPED", "MAPPED"], "auto_resolved": 0,
                      "superseded_by": [None, None], "additions_kept": 1}
```

##### `test_yappari_sonomama_does_not_turn_an_addendum_into_replacement` — after

```python
def test_yappari_sonomama_does_not_turn_an_addendum_into_replacement():
    # W5-d2 (K2): the expectation is the result of W5-d's R-J2. The marker `やっぱり` is followed by a fragment of its own (`そのまま`); the fragment is read by the same
    # reader, and this reader answers every sentence with the affirmative assignment, so the fragment is not a maintenance and the unit is AMBIGUOUS_RELATION:
    # nothing is replaced (superseded_by stays None, auto_resolved 0) and nothing is added. The point of the attack (it must not be a replacement) is kept.
    first = "実装はハルに任せる。"
    second = "やっぱりそのまま、実装はハルに任せる。"
    explained = rt.explain(f"{first}\n追記：{second}\n", "attack.md", reader=_reading_for_assignment, lookup=_AllUnplaced())
    actual = {"statuses": [unit.status for unit in explained.extraction.units],
              "auto_resolved": explained.extraction.auto_resolved,
              "superseded_by": [relation.superseded_by for relation in explained.extraction.relations],
              "additions_kept": explained.extraction.additions_kept}
    print(f"OBS R2 {json.dumps(actual, ensure_ascii=False, sort_keys=True)}")
    assert actual == {"statuses": ["MAPPED", "AMBIGUOUS_RELATION"], "auto_resolved": 0,
                      "superseded_by": [None], "additions_kept": 0}
```

<!-- w5d2-amended:end -->

## W5-d 第 2 ラウンド（W5-d2）の測定
<!-- w5d2-measured:begin -->
測定の時刻: 2026-10-04 01:22:30 +0900。出力はすべて `artifacts/w5-d/r2/`（ファイル名を添える）。中間職のレビュー r1（`review-impl/W5-d2/review.r1.md`）の M1〜M4（改訂したテストの前後の全文・測定の区間・失敗集合のファイル・報告）に応えてこの区間と `w5d2-amended` 区間を書いた。製品とテストのコードはレビューのあとに変えていない（`code_sha_r2b_start.txt` と `code_sha_r2b_end.txt` が同じ）。受入の測定はこのとき全部流し直した（`g1_rerun_r2b.txt`・`g2_rerun_r2b.txt`・`g3_rerun_r2b.txt`・`q1_observe_cmp_r2b.txt`・`g4_compare_r2b.txt`・`q5_r7_verify_r2b.txt`・`k5_check_r2b.txt`。出力は前の流しと byte 一致。違いが無かったことの確認なので前の流しのファイルも残す）。

**受入基準**（第 2 ラウンド）
- **G1**（`g1_rerun_r2b.txt`）: 攻撃の写し 36 本が `36 passed`、K の 72 関数（82 id）が全部通る（`102 passed`）、新しいテスト（第 1 ラウンドの 5 本＋第 2 ラウンドの追記）が `113 passed`。G1-b: 写しと原本の差は先頭行と改訂した関数・足したヘルパの中だけ（`g1b_hunks.txt`、`attack_copy_revisions.diff`。w5c の 2 本は原本と同一、`data/` も同一）。
- **G2**（`g2_185_*.json(l)`・`g2_attack120_r7.json(l)`・`g2_rerun_r2b.txt`）: `VERA_PLACEMENT` なしの 185 問は第 1 ラウンドの出力と byte 一致（place: 正答/誤答/FALSE_NONE/棄権 = 38 / 0 / 4 / 143、noplace: 26 / 0 / 4 / 155）。`VERA_PLACEMENT=r7`: place 73 / 0 / 6 / 106、noplace 66 / 0 / 8 / 111。誤答 0、型未確認の FILLED/TIE 0（4 通りとも `unchecked_fillers_in_FILLED_TIE` は 0・0・0・0）。正答は減っていない（第 1 ラウンドと同じか、r7 で増える）。攻撃の 120 問（r7、116 問は正解なしで採点されない）: FILLED 29・TIE 5、型未確認の FILLED/TIE 0、`wrong` 0 件。A01（`EN08-01`）は `NO_TYPED_CANDIDATE`（`letter`・`note` は `TYPE_UNCHECKED`）で FILLED/TIE にならない（`g2_r7_notes.txt`）。中間職の凍結 64 問・56 問は実装役が開かない約束なので測っていない（中間職が測る）。
- **G3**（`g3_rerun_r2b.txt`・`g3_*`）: 経路づけの凍結 4 本（配置なし）の misroutes は 0, 0, 0, 0、r7 の 2 本は 0, 0。合成 `g3_synth`（入力の sha256 は `g3_synth_inputs_check.txt` で第 1 ラウンドの凍結と一致）: 配置なし misroutes 0・普通名詞に振った数 0、r7 misroutes 1（第 1 ラウンドと同じ 1 件。`委員会` が推定の GROUP_ORG で通る既知の穴）、基点 1（`g3_synth_results/g3_synth_counts.json`）。D2-2 の影響: r7 の 2 本の 118 件を、D2-2 の呼び出しを外した写しと単位ごとに比べて変化した件数は 0（`g3_r7_diff.txt`）。
- **G4**（`g4_result.json`・`g4_compare_r2b.txt`）: 入力の sha256 と `summary` が第 1 ラウンドと同じ（自己申告の文書 16 件で `ANSWER` 0、文面違いの確認記録 15 件で `ANSWER` 0・旧文が返った 0、対照は 4/4 と 2/2 で答える）。`verantyx/basis_policy.py` は第 2 ラウンドで変えていない（sha256 が `files_start.sha256` と同じ）。
- **G5**（`q5_r7_verify_r2b.txt`・`k5_check_r2b.txt`）: r7 は作り直していない。`verify` が run1・run2 とも `OK`、`content_sha256` は第 1 ラウンドと同じ。`coarse_place.py`・`tools/build_coarse_placement.py` は第 2 ラウンドで変えていない。K5 の写しが通り、r6_audit_summary.json not_confirmed: 13 words; invariant_errors [] byte_differences []、第 1 ラウンドの 13 語と同じ集合（`命じる` を含む）。
- **平叙文の観測**（`q1_observe_cmp_r2b.txt`）: `o1_bytes.py --child` の出力が、配置なしと `VERA_PLACEMENT=r7` の 2 通りとも基点と byte 一致（`same: base vs now` が 2 行。この流しは前の流しとも byte 一致）。
- **G7**（`pytest_full.txt`・`after_failures.txt`・`new_failures.txt`・`fixed_failures.txt`・`new_failures_explained.txt`）: 全体テストの最終行 `117 failed, 11981 passed, 45 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 362.65s (0:06:02)`。失敗は一意に 117 件、基線に無い失敗は 2 件（`tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches`、`tests/test_gen_coarse_evidence.py::test_the_stop_signal_ends_the_run_with_an_interrupted_record`）、基線にあって今は通る失敗は 0 件。基線に無い失敗の理由は `new_failures_explained.txt`（環境由来だけ）。K の id は失敗集合に 0 件。

**K2（自由文→記録 52 件）の改訂**（裁定 B1。前後の全文は上の `w5d2-amended` 区間。`changed_functions_k1k2.txt`）: 既存 51 件と攻撃の写し R2 の 1 件（K の id の内訳は `k_ids.txt`: `test_routing_from_text.py` 36・`_w5b` 12・`_regress` 2・`_entry` 1・攻撃の写し 1）。名前は変えていない。直し方: テストの中だけの `FakePlacement`（固定の名前は `UNPLACED`、列挙した普通名詞は direct の型。製品には入っていない: `git diff c875ed3 -- verantyx/` に `fake` の語は無い）を `tests/test_routing_from_text.py` に 1 つ足し、`explain_lines(..., lookup=None)` と、それを経由する補助関数（`two_rules_and_a_precedence`・`one_unit_status`・`run`・`statuses`）に既定 None の `lookup` 引数を足し、module スコープの fixture `std` は変えずに `std_placed`（同じ STD を `FakePlacement()` で）を足して、K2 の関数だけを切り替えた。

**配置なしそのものが主題の改訂 3 件**（期待を新しい契約「配置なし → 棄権」に）: `test_routing_from_text_w5b.py::test_without_a_placement_nothing_is_checked_and_that_is_counted_not_hidden`（単位は `NAME_UNRESOLVED`・`NAME_UNVERIFIED:ソラ:NO_PLACEMENT`）、`test_routing_from_text_entry.py::test_T1_the_entry_returns_the_documented_shape_and_routes_through_the_real_reader`（本物の読解器・配置なしの子プロセスの今の出力に合わせた。`entry()` は子プロセスの env を `dict(os.environ)` から作るので `VERA_PLACEMENT` を外す 1 行を足した。期待の弱体化ではなく、漏れを防ぐため）、`test_routing_from_text.py::test_output_keys_order_and_basis_kinds`（主題は鍵の並びなので `std_placed` に切り替え、`reading.lookup == "test-fake-placement/1"`）。配置なしの棄権を表すテスト（足した）: `tests/test_routing_from_text_w5d.py::test_w5d2_k2_the_standard_explanation_with_and_without_a_placement`（STD を偽の配置ありで流すと第 1 ラウンド前と同じ判断、配置なしは `INCOMPLETE_READING`・単位に `NAME_UNVERIFIED:…:NO_PLACEMENT`）と `test_w5d2_without_a_placement_a_part_of_a_parallel_name_is_unverified_as_before`。攻撃の写し R2（`test_yappari_sonomama_does_not_turn_an_addendum_into_replacement`）は `lookup=` に全語 UNPLACED の偽の配置（`_AllUnplaced`）を渡し、期待を R-J2 の結果 `{"statuses": ["MAPPED", "AMBIGUOUS_RELATION"], "auto_resolved": 0, "superseded_by": [None], "additions_kept": 0}` に改訂した（攻撃の偽 reader は断片「そのまま」も肯定の「任せる」に読むので未確定。主旨＝置き換えにならない、は保たれる）。

**D2-2 並列の名前の部分（製品の変更。裁定の申し送り「並列の名前の過剰棄権は直さず既知の穴」からの逸脱）**: 理由と実測。(1) 裁定の K2 の形（偽の `PlacementLookup` の注入）・G7・「期待を弱めない」は、並列の部分に配置の答えが無いと同時には満たせない。偽の配置（全語 UNPLACED）を入れても、標準の説明文 STD の `ハルとセキは同じ会社だ。` で配置の答えが充填物 `ハルとセキ` 全体にしか付かず、部分 `ハル`・`セキ` に答えが無いので R-J1 が `NAME_UNVERIFIED:ハル:NO_PLACEMENT` で止め、関門が `INCOMPLETE_READING` で全部を棄権にする。中間職の試作の実測でこの 11 件が通らない（`test_relation_comparison_keeps_one_agent_only_and_comparison_only_does_not_stop`・`test_relation_independence_same_negated_distinct_and_a_different_phrase_is_held_as_ambiguous`・`test_relation_roles_independence_is_the_routers_default_r3_and_makes_no_record`・`test_gate_one_unread_unit_stops_every_job_and_the_router_is_not_called`・`test_T3_the_same_content_as_a_hand_written_table_gives_the_same_decisions`・`test_router_call_passes_used_agents_only_no_chooser_and_the_first_names`・`test_router_reasons_are_written_through_from_the_routers_types`・`test_router_unknown_task_names_abstain_with_their_own_type`・`test_constraint_prohibition_veto_does_not_try_the_next_agent`・`test_constraint_human_and_wait_scopes_and_residual_and_conflict`・`test_constraint_independence_veto_for_two_other_roles`。出典: `plan_evidence/proto_numbers.txt` §1）。実装役も同じ測定をした: D2-2 の呼び出し 1 行だけを外した写しで K2 のテスト一式を流すと 12 failed（上の 11 件と、`std_placed` に切り替えた `test_output_keys_order_and_basis_kinds`。`d22_without_the_call.txt`、`scripts/run_k2_without_d22.py`）、D2-2 を入れた木では 0 件。期待を書き換えれば「弱体化」、失敗のままなら G7 に反する。(2) 直し方は R-J1 の同じ規則を部分の名前それぞれの配置の答えに当てるだけ（新しい規則は足さない）: `read_units` で `lookup is None` なら最初に 1 回 `event_cross.default_lookup()` に解決し、`UnitReading.part_places`（既定値つきの新しい欄）に、日本語の `CROSSED` の単位の各充填物を `_split_parallel` で切った群を同じ lookup に問い、契約に合う答え（`invariant_problems()` が空）だけ `setdefault` で入れ、`_places_of` は充填物自身の答えを先にして `part_places` を後に足す。日本語だけ（英語の並列は問わない）。(3) 実測: 偽の配置なしで、routing の関係テスト一式＋攻撃の写し R2 の失敗集合は K2 の 52 id と完全に同じ（差 0。`k2_after_product_raw.txt`＝製品の変更だけを入れて、偽の配置を入れる前のテストを流した）＝この変更は新しい失敗を作らない。偽の配置ありで K2 の関数は全部通る（`g1_rerun_r2b.txt` の K の `102 passed`）。G3: 配置なし 4 本・r7 2 本とも misroutes 0、r7 の 2 本は D2-2 を外した写しと単位ごとに比べて 118 件中 0 件が変化（`g3_rerun_r2b.txt`・`g3_r7_diff.txt`）。足したテスト（`tests/test_routing_from_text_w5d.py`）: `test_w5d2_a_parallel_name_is_routed_when_the_placement_answers_for_each_part`（全語 UNPLACED で `ハルとセキは同じ会社だ。` が MAPPED・INDEPENDENCE(same)）、`test_w5d2_a_part_of_a_parallel_name_that_the_placement_types_as_a_common_noun_stops_the_unit`（部分の 1 つが direct の GROUP_ORG → `COMMON_NOUN_SUBJECT`）、`test_w5d2_without_a_placement_a_part_of_a_parallel_name_is_unverified_as_before`、`test_w5d2_an_english_parallel_name_is_not_asked_part_by_part`（spy の lookup で英語の部分が問われない）、`test_w5d2_the_parts_that_are_asked_are_exactly_the_groups_of_the_parallel_split`。

**第 2 ラウンドで置き換わった第 1 ラウンドの記述**（第 1 ラウンドの `w5d-*` 区間の中は 1 文字も変えていない。元の行は残し、この一覧が上書きする）
- 「既知の穴 1: 並列の名前は配置があっても止まる」→ 第 2 ラウンドで、配置があれば部分の名前も配置の答えで引く（上）。配置が部分を UNPLACED と答えれば名前として通る（単独の名前と同じ扱い。下の穴 3）。配置が無ければ今までどおり `NAME_UNVERIFIED`。
- 「K2 は宣言した衝突」→ 裁定 B1 で改訂が許可され、上のとおり改訂した。

**既知の穴**（直していない。次の攻撃と W3-b3 のあとで見る）:
1. r7 でも、推定・UNPLACED の普通名詞の主語が名前として通る（第 1 ラウンドの探りで 60 文中 8 文。合成 `g3_synth` の r7 で `委員会` が 1 件。`g3_synth_results/g3_synth_counts.json`）。
2. R2 の「維持」（`やっぱりそのまま`）は、本物の読解器ではほぼ到達しない（断片を節に読めず `AMBIGUOUS_RELATION` に倒れる。到達するのは断片を読む偽 reader のテストだけ。第 1 ラウンドのまま）。
3. D2-2 は「部分の名前それぞれの配置の答え」を見るだけで、配置が部分を UNPLACED と答えれば名前として通る。
4. 並列の部分を問う `lookup.lookup(名)` は `_read_one` の `try` の外にあり、部分を問われたときだけ例外を投げる lookup では `explain` 全体が例外で止まる（中間職のレビュー r1 の任意の改善 1。本番の `StubLookup`・`CoarseLookup` は例外を投げない作りなので実害は今のところ無い。レビューが製品・テストの変更を範囲外としたので直していない）。
5. r7 の説明文で `ハル` は MULTIPLE（ANIMAL・GROUP_ORG・PERSON）の direct なので `COMMON_NOUN_SUBJECT` で止まる（中間職のレビュー r1 の申し送り 2）。D2-2 は偽の配置では効くが、本番の r7 で `ハル` を名前として通さない（実装役も `r7_lookups.txt` で確かめた: `ハル` は MULTIPLE・direct・ANIMAL/GROUP_ORG/PERSON、`セキ` は UNPLACED、`チーム` は DECIDED・direct・GROUP_ORG、`委員会` は DECIDED・estimated・GROUP_ORG）。安全側の過剰棄権で、G3 の r7 で「正しく振った 0」はこれと読解器による。
**この文書の担当の測定は上のとおり。全体の受入と判断は `artifacts/w5-d/DECISIONS.md` の「第 2 ラウンド（W5-d2）」と `artifacts/w5-d/r2/`。**
<!-- w5d2-measured:end -->

## W5-e の事前登録: A-2 推定・未配置の普通名詞を担当者に振らない（`COMMON_NOUN_SUBJECT_UNTYPED`）
<!-- w5e-a2-prereg:begin -->
事前登録の時刻: 2026-10-04 03:53:18 +0900（`date '+%F %T %z'`）。この節は A-2 の新しいテスト（`tests/test_routing_from_text_w5e.py`）を書く前、製品コード（`verantyx/routing_from_text.py`）を直す前に確定した。上の節は 1 文字も変えない。

**命中（W5-d の攻撃 A-2、`tests/attack/test_attack_w5d.py::test_route_r7_estimated_common_noun_is_not_mapped_as_an_agent`）**: r7 で `委員会` は `DECIDED`・`estimated`（GROUP_ORG）。`_common_noun_stop` の (b) は direct のときだけ止めるので、`usable=True` だが `typed=False` の分岐で素通りし、`委員会はテストを書く。` の担当者が `委員会` になる。推定は構成物で、根拠にならない（W5-c 以来の原則）。

### 規則（`_common_noun_stop`。日本語・命名の文で導入されていない名前だけ。英語は変えない）
`place` はその名前に付いた配置の答え。上から最初に当たったもの:
1. 答えが使えない（無い・`state == NO_PLACEMENT`・`source == NO_PLACEMENT`）→ `NAME_UNVERIFIED:<名>:NO_PLACEMENT`（今どおり）。
2. `origin == direct` で `state == DECIDED`、型が名詞型（`event_cross.NOUN_TYPE_IDS`）→ `COMMON_NOUN_SUBJECT:<名>:PLACEMENT_DIRECT:<型>`（今どおり。止める。`flagged` に数える）。
3. `origin == direct` で `state == MULTIPLE`、**全候補が名詞型** → 2 と同じ（「全候補一致」。止める。`flagged`）。
4. `origin == direct` で `state == DECIDED`、型が名詞型でない（述語の型など）→ **通す**（今どおり。R-J1 の「17 型に無い型だけの direct は止めない」を保つ。W5-d の写しの `PredicateTypedName` もこれに頼る）。
5. それ以外（推定・`UNPLACED`・`UNKNOWN`・名詞型でない候補を含む `MULTIPLE`・その他の状態）→ **新しい理由** `COMMON_NOUN_SUBJECT_UNTYPED:<名>:<ESTIMATED|UNPLACED|UNKNOWN|MULTIPLE|状態>`（単位の状態は既存の `NAME_UNRESOLVED`。`UNIT_STATUSES` は増やさない）。

- 「DECIDED direct の名詞型のときだけ振る」を字面どおり（direct の人・組織を担当者にする）に読むと、r7 の 60 文で `先生`・`社員` などが振られて H3（8 → 0）が落ちる。だから「振る」は **型の付いた普通名詞の印 `COMMON_NOUN_SUBJECT:…:PLACEMENT_DIRECT` を付けて止める** と読む（今どおり）。担当者になるのは、命名の文で導入された名前か、4 の（名詞型でない direct の）名前だけ。
- `common_noun_check` の数え方は鍵を足さない: 5 は配置が答えたので `checked` に数える（`flagged` は 2・3 だけ、`not_checked` は 1 だけ）。
- 英語は変えない（決定木は日本語の分岐の中だけ）。

### 名指しの改訂（名前不変・前後の全文。標準の規則）
`tests/test_routing_from_text_w5b.py::test_an_estimated_unplaced_or_unknown_word_is_not_a_reason_to_stop` は「止めない」を固定している。W5-c 以来の原則「推定は構成物であり根拠にならない」に合わせ、3 つの引数とも `NAME_UNRESOLVED`・理由 `COMMON_NOUN_SUBJECT_UNTYPED:ソラ:…`・`checked == 1` に改訂する（名前は変えない）。後の全文は測定の節（`w5e-a2-amended`）。

**改訂の前の全文**
```python
@pytest.mark.parametrize("answer", [
    PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True}),      # a construction is not a testimony
    PlaceResult("UNPLACED", provenance={"fake": True}),
    PlaceResult("UNKNOWN", provenance={"fake": True}),
])
def test_an_estimated_unplaced_or_unknown_word_is_not_a_reason_to_stop(answer):
    lookup = Placement(ソラ=answer)
    explained = explain("ソラは実装をやる。\n", {"ソラは実装をやる。": ja_do("ソラ")}, lookup)
    assert [u.status for u in explained.extraction.units] == ["MAPPED"]
    assert route(explained, role="implement", kind="feature")["reading"]["common_noun_check"]["checked"] == 1
```
（デコレータ `@pytest.mark.parametrize("answer", [...])` の引数の 3 つは、上のとおり推定（`DECIDED estimated proximity GROUP_ORG`）・`UNPLACED`・`UNKNOWN`。1 行目 `PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True})`）

### 宣言する衝突 K-A2（実装役は解かずに宣言する。判断は監査役）
W5-d2 の裁定 K2 は、「UNPLACED と答える偽の配置 `FakePlacement`（`tests/test_routing_from_text.py`）の下で日本語の名前は担当者に振られる」ことを前提に既存のテストを書き直した。A-2 の規則（UNPLACED は止める）はその前提を退役させる。名指しの 3 引数を除く既存のテスト（`test_routing_from_text*.py`・`tests/attack/test_attack_w5b_wave2.py`・W5-d の写しの R2 など）が、同じ原因でまとめて落ちる。**実装役はテストを書き換えず**、落ちた id を全部宣言する（一覧は測定の節）。**H3（r7 の普通名詞 60 文で振られる数 8 → 0）を満たす規則と、K2 の裁定で作られた既存テストの前提は両立しない。H1・H7 はこの分だけ満たせない。**改訂の方向（K2 の偽の配置を述語の型を direct に答えるものに変える、または名前を命名の文で導入する）は `artifacts/w5-e/proposals/k_a2.md` に文章で書く。

### 受入（H3。測る前に固定）
- W5-d の凍結の経路づけ 6 本（配置なし 4 本・r7 2 本）で誤ルート 0。r7 の普通名詞 60 文（`r7_nouns.py`）で振られる数 8 → 0（変更前は `artifacts/w5-e/before/h3_r7_nouns.json`）。正しく振った数の before との差も数で書く。
<!-- w5e-a2-prereg:end -->

## W5-e A-2 の改訂後の全文と宣言
<!-- w5e-a2-amended:begin -->
記録の時刻: 2026-10-04 03:56:58 +0900。テストの改訂は製品コード（`routing_from_text.py`）の変更の後。名前不変。変えたのは関数の先頭のコメント 1 行・`explained.extraction.units` の期待・`state` の導出 1 行だけ（`git diff --stat tests/test_routing_from_text_w5b.py` で追加 3 行・削除 1 行）。前の全文は上の `w5e-a2-prereg` 区間。

**改訂の後の全文**
```python
@pytest.mark.parametrize("answer", [
    PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True}),      # a construction is not a testimony
    PlaceResult("UNPLACED", provenance={"fake": True}),
    PlaceResult("UNKNOWN", provenance={"fake": True}),
])
def test_an_estimated_unplaced_or_unknown_word_is_not_a_reason_to_stop(answer):
    # W5-e（チケット W5-e の名指しの改訂）: 推定・UNPLACED・UNKNOWN の名前は担当者に振らず COMMON_NOUN_SUBJECT_UNTYPED で止める（A-2。推定は構成物であり根拠にならない）。配置は答えたので checked に数える。
    lookup = Placement(ソラ=answer)
    explained = explain("ソラは実装をやる。\n", {"ソラは実装をやる。": ja_do("ソラ")}, lookup)
    state = "ESTIMATED" if answer.origin == "estimated" else answer.state
    assert [(u.status, u.reasons) for u in explained.extraction.units] == [("NAME_UNRESOLVED", [f"COMMON_NOUN_SUBJECT_UNTYPED:ソラ:{state}"])]
    assert route(explained, role="implement", kind="feature")["reading"]["common_noun_check"]["checked"] == 1
```

**宣言（K-A2。書き換えない）**: 名指しの 3 引数を除く既存のテストの失敗は 73 件（`artifacts/w5-e/a2_declared.txt`）。ファイル別: `tests/test_routing_from_text.py` 36・`tests/test_routing_from_text_w5d.py` 20・`tests/test_routing_from_text_w5b.py` 13・`tests/test_routing_from_text_regress.py` 2・`tests/attack/test_attack_w5b_wave2.py` 1・`tests/attack/test_attack_w5d.py`（W5-d の写しの R2）1。原因と改訂の方向は `artifacts/w5-e/proposals/k_a2.md`。チケットの試作の 72 件に対して 1 件多い（`test_routing_from_text_w5d.py::test_r1_a_direct_type_among_the_noun_types_is_a_common_noun[types4]`）理由は、MULTIPLE の扱いを A-2 の規則（全候補が名詞型のときだけ typed）どおりに作ったため（単位は止まるまま、理由の文字列だけが変わる）。

**製品の変更**: `verantyx/routing_from_text.py` の `_common_noun_stop` の中だけ（日本語の分岐。英語は変えない）。
<!-- w5e-a2-amended:end -->


## W5-e の測定: A-2 推定・未配置の普通名詞（H3）
<!-- w5e-a2-measured:begin -->
測定の時刻: 2026-10-04 04:10:06 +0900。コマンドは `artifacts/w5-e/scripts/measure.sh`（`run_bank.py` 6 本・`r7_nouns.py`）。凍結とテスト: `frozen_a2.sha256`・`frozen_a2_at.txt`、直す前に落ちる記録 `a2_before_fail.txt`（`14 failed, 8 passed`）。

- **誤ルート 0**: W5-d の凍結の 6 本（配置なし 4 本・r7 2 本）は変更の前後とも `misroutes: 0`（`after_measure.log`、`before_measure.log`）。正しく振った数（`route_correct`）は 6 本とも変更前と同じ: 0・0・3・2（配置なし 4 本）、0・0（r7 2 本）（`h3_bank_compare.txt`）。
- **r7 の普通名詞 60 文で振られる数**: 変更前 8（`before/h3_r7_nouns.json`）→ 変更後 0（`h3_r7_nouns.json`）。配置なしも 0（`h3_np_nouns.json`）。攻撃 A-2（`test_route_r7_estimated_common_noun_is_not_mapped_as_an_agent`）は通る。
- **テスト**: `tests/test_routing_from_text_w5e.py` は `20 passed`（`new_tests_run.txt`）。名指しの改訂（`test_an_estimated_unplaced_or_unknown_word_is_not_a_reason_to_stop`、3 引数）は通る。
- **宣言した衝突 K-A2**（書き換えていない。`a2_declared.txt`、73 件。理由と改訂の方向は `proposals/k_a2.md`）: ファイル別 `test_routing_from_text.py` 36・`test_routing_from_text_w5d.py` 20・`test_routing_from_text_w5b.py` 13・`test_routing_from_text_regress.py` 2・`attack/test_attack_w5b_wave2.py` 1・`attack/test_attack_w5d.py`（R2）1。**H1・H7 はこの分だけ満たせない。**
<!-- w5e-a2-measured:end -->

## W5-e 第 2 ラウンド: 監査役の訂正（2026-10-04 04:42:38 の判断）
<!-- w5e2-a2-prereg:begin -->
事前登録の時刻は `artifacts/w5-e/r2/a2_prereg_at.txt`。第 1 ラウンド（上の「W5-e の事前登録」以下）の記述は消さない。ここは訂正の追記。

### 訂正後の規則（`_common_noun_stop` の日本語の分岐だけ。英語は不変。命名の文で導入された名前は従来どおり調べない）
- **第 1 ラウンドの規則を捨てる**: 「推定・UNPLACED・UNKNOWN・名詞型でない候補を含む MULTIPLE を `COMMON_NOUN_SUBJECT_UNTYPED` で止める」は誤りだった（W5-d の R1 は「配置が名詞型を言う語＝普通名詞 → direct の名詞型なら止める／配置に無い語（UNPLACED）＝名前の候補 → 宣言された名前との照合に回す」という設計で、UNPLACED を止めると名前が全部止まる）。
- **基点（W5-d）の判定に戻す部分**: `typed = usable and origin == "direct" and state in ("DECIDED", "MULTIPLE")`、日本語では `typed = any(str(t) in event_cross.NOUN_TYPE_IDS for t in types)`（DECIDED も MULTIPLE も同じ `any`）。止めるときの理由は従来どおり `COMMON_NOUN_SUBJECT:<名>:PLACEMENT_DIRECT:<型,…>`。
- **足す分岐は 1 つだけ**: 日本語で配置の答えが使え（`usable`）かつ `origin == "estimated"`（state・型を問わない）なら止める。推定は構成物であり根拠にならない（W5-c 以来の原則）。理由は **既存の名前** に印を付けた `COMMON_NOUN_SUBJECT:<名>:PLACEMENT_ESTIMATED:<型,…>`（型は `place["types"]` をそのままの順で `,` 連結。空なら空文字）。
- **通す**: `UNPLACED`・`UNKNOWN`・その他の state で direct でない答えは W5-d のまま通す（名前の照合へ。`checked` に数える）。direct の名詞型でない型（`P_COMMUNICATE` など）も通す。配置なし（`None`・`NO_PLACEMENT`）は W5-d のまま `NAME_UNVERIFIED:<名>:NO_PLACEMENT`。
- **数え方**: 推定で止めた名前は `checked`（配置は答えたが証言ではない）。`flagged` は direct の名詞型だけ（従来どおり）。
- **`COMMON_NOUN_SUBJECT_UNTYPED` の退役**: 第 1 ラウンドで足した理由名 `COMMON_NOUN_SUBJECT_UNTYPED` は製品から出さない（退役。第 1 ラウンドの記述は履歴として残す）。

### H3 の読み方（第 2 ラウンド。測る前に固定）
訂正後の規則では「r7 の普通名詞 60 文で振られる数 8 → 0」は成り立たない（UNPLACED を止めないため）。第 2 ラウンドの H3 は次で判定する。
- W5-d の凍結の経路づけ 6 本で誤ルート 0（従来どおり）。
- r7 の普通名詞 60 文で、**主語が推定・名詞型を含む direct（DECIDED／MULTIPLE）の文で振られる数 0**（変更前は 8 のうち 4＝`委員会` 2・`開発者` 2）。
- 振られる数の合計と、その全件の語と配置の状態を報告する。全件が `UNPLACED` であること。`UNPLACED`・`UNKNOWN` 以外が 1 件でもあれば止まって報告する。
- 「第 2 ラウンド: 8 → 4（UNPLACED の文は訂正後の規則どおり）」を測定の節に追記する（第 1 ラウンドの 8 → 0 の記述は消さない）。
<!-- w5e2-a2-prereg:end -->

### 名指しの改訂（K-A2。名前不変・前後の全文。標準の規則）
<!-- w5e2-a2-amended:begin -->
監査役の判断（2026-10-04 04:42:38）の指名: 「推定を主題にしたテスト（`test_r1_a_placed_word_that_the_placement_cannot_type_still_passes` など）は、推定が根拠にならない原則（W5-c 以来）に合わせて期待を改訂」。チケット名指しの w5b のテストも同じ。**改訂前は基点（`ca66d3e`）の本文**（w5b は第 1 ラウンドの改訂を捨てて基点から作り直した。第 1 ラウンドの改訂後の全文は上の `w5e-a2-amended` 区間）。推定の引数だけ止め、UNPLACED・UNKNOWN は基点どおり `MAPPED`。デコレータ・引数の並び・関数名は不変。

#### `tests/test_routing_from_text_w5b.py::test_an_estimated_unplaced_or_unknown_word_is_not_a_reason_to_stop`

**改訂前（基点 ca66d3e の全文）**
```python
@pytest.mark.parametrize("answer", [
    PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True}),      # a construction is not a testimony
    PlaceResult("UNPLACED", provenance={"fake": True}),
    PlaceResult("UNKNOWN", provenance={"fake": True}),
])
def test_an_estimated_unplaced_or_unknown_word_is_not_a_reason_to_stop(answer):
    lookup = Placement(ソラ=answer)
    explained = explain("ソラは実装をやる。\n", {"ソラは実装をやる。": ja_do("ソラ")}, lookup)
    assert [u.status for u in explained.extraction.units] == ["MAPPED"]
    assert route(explained, role="implement", kind="feature")["reading"]["common_noun_check"]["checked"] == 1
```

**改訂後の全文**
```python
@pytest.mark.parametrize("answer", [
    PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True}),      # a construction is not a testimony
    PlaceResult("UNPLACED", provenance={"fake": True}),
    PlaceResult("UNKNOWN", provenance={"fake": True}),
])
def test_an_estimated_unplaced_or_unknown_word_is_not_a_reason_to_stop(answer):
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A2）: 推定は構成物であり根拠にならない（W5-c 以来）ので、推定の引数だけ COMMON_NOUN_SUBJECT:…:PLACEMENT_ESTIMATED:… で止める。UNPLACED・UNKNOWN は基点（W5-d）のまま通す。3 引数とも checked == 1
    lookup = Placement(ソラ=answer)
    explained = explain("ソラは実装をやる。\n", {"ソラは実装をやる。": ja_do("ソラ")}, lookup)
    if answer.origin == "estimated":
        assert [(u.status, u.reasons) for u in explained.extraction.units] == [("NAME_UNRESOLVED", ["COMMON_NOUN_SUBJECT:ソラ:PLACEMENT_ESTIMATED:GROUP_ORG"])]
    else:
        assert [u.status for u in explained.extraction.units] == ["MAPPED"]
    assert route(explained, role="implement", kind="feature")["reading"]["common_noun_check"]["checked"] == 1
```

#### `tests/test_routing_from_text_w5d.py::test_r1_a_placed_word_that_the_placement_cannot_type_still_passes`

**改訂前（基点 ca66d3e の全文）**
```python
@pytest.mark.parametrize("answer", [PlaceResult("UNPLACED", provenance={"fake": True}), PlaceResult("UNKNOWN", provenance={"fake": True}),
                                    PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True})])
def test_r1_a_placed_word_that_the_placement_cannot_type_still_passes(answer):
    explained = explain("ソラは実装をやる。\n", {"ソラは実装をやる。": ja_do("ソラ")}, Placement(ソラ=answer))
    assert [u.status for u in explained.extraction.units] == ["MAPPED"]
```

**改訂後の全文**
```python
@pytest.mark.parametrize("answer", [PlaceResult("UNPLACED", provenance={"fake": True}), PlaceResult("UNKNOWN", provenance={"fake": True}),
                                    PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True})])
def test_r1_a_placed_word_that_the_placement_cannot_type_still_passes(answer):
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A2）: 推定は構成物であり根拠にならない（W5-c 以来）ので、推定の引数（answer2）だけ止める。UNPLACED・UNKNOWN は W5-d のまま通す
    explained = explain("ソラは実装をやる。\n", {"ソラは実装をやる。": ja_do("ソラ")}, Placement(ソラ=answer))
    if answer.origin == "estimated":
        assert [(u.status, u.reasons) for u in explained.extraction.units] == [("NAME_UNRESOLVED", ["COMMON_NOUN_SUBJECT:ソラ:PLACEMENT_ESTIMATED:GROUP_ORG"])]
    else:
        assert [u.status for u in explained.extraction.units] == ["MAPPED"]
```
<!-- w5e2-a2-amended:end -->

## W5-e 第 2 ラウンドの測定: A-2 の訂正後（H3 の第 2 ラウンドの読み方）
<!-- w5e2-a2-measured:begin -->
測定の時刻は上の追記の直後（`artifacts/w5-e/r2/`）。第 1 ラウンドの「8 → 0」の記述（上の `w5e-a2-measured`）は消さない。

- 凍結とテスト: `frozen_a2_r2.sha256`・`frozen_a2_r2_at.txt`（事前登録 `a2_prereg_at.txt` の後）、直す前に落ちる記録 `a2_before_fail.txt`、直した後 `a2_after.txt`（A-2 に関わる 8 ファイル: 落ちるのは `test_routing_from_text_entry.py::test_T1_…` の 1 件だけ。K-B で改訂する。`1 skipped` は A-4 で攻撃のベクトルが消えた `test_frame_confirmed_partial_intersection…`）。
- **誤ルート 0**: W5-d の凍結の経路づけ 6 本（配置なし 4 本・r7 2 本）は `misroutes: 0`（`measure.log` と同じ出力。`h3_np_*`・`h3_r7_*`）。
- **r7 の普通名詞 60 文で振られる数: 第 2 ラウンドは 8 → 4**（`h3_r7_nouns.json`。変更前 8 は `artifacts/w5-e/before/h3_r7_nouns.json`）。振られる 4 文は `レビューは課がやる。`・`レビューは部門がやる。`・`レビューはメンバーがやる。`・`レビューは外注先がやる。` で、4 語とも r7 の配置の答えは `UNPLACED`（`h3_r7_routed_states.txt`、`all UNPLACED: True`）。訂正後の規則は UNPLACED を名前の候補として通す（W5-d のまま）ので、これは **規則どおり**。第 1 ラウンドの「8 → 0」は UNPLACED を止める誤った規則の値。推定の `委員会`・`開発者`（各 2 文、計 4 文）は止まる: **推定・名詞型を含む direct で振られる数 0**。配置なしは 0（`h3_np_nouns.json`）。
- 残る 4 文を止めるには UNPLACED の普通名詞を名前と区別する別の証言が要る。今回の範囲外（申し送り）。
<!-- w5e2-a2-measured:end -->
