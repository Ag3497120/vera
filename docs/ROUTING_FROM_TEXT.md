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
| `ANAPHORS` | ja: `前者` `後者` `それ` `これ` `あれ` `彼` `彼女` `同上` `上記` `そちら` `こちら`／en: `the former` `the latter` `it` `they` `them` `he` `she` `this` `that` `former` `latter` `the same one` | 先行詞を指す語。先行詞は読まないので呼び名として受けない（`NAME_UNRESOLVED`） |
| `GENERIC_OBJECTS` | ja: `コード` `作業` `仕事` `もの` `ファイル` `変更`／en: `code` `work` `job` `task` `file` `files` `change` `changes` | 仕事を言う動詞（確かめる・review など）の目的語として何も足さない語 |
| `HONORIFICS` | `さん` `氏` `君` `様` | 呼びかけの敬称。敬称つきの語は呼び名として受けない |
| `EN_DETERMINERS` | `the` `a` `an` `this` `that` `these` `those` `my` `our` | 英語で限定詞から始まる句は説明であって呼び名でない |
| `NON_NAME_POS` | `形容詞` `連体詞` `動詞` `助詞` `助動詞` `副詞` `接続詞` `代名詞` `感動詞` | 形態素の品詞がこれのどれかを含む句は素の名前でない（`重い方` `東社のモデル`）。架空の呼び名の品詞は当てにならないので、呼び名かどうかの判定には使わず、説明的な句を止めるためだけに使う |
| `SENTENCE_ENDS` | `。` `．` `！` `？` `!` `?`（と、直後が空白か行末の `.`） | 文末記号 |
| `CLOSERS` | `」` `』` `）` `)` `"` `'` | 文末記号の直後にあって文に残る閉じ記号 |
| `LIST_MARKERS` | `-` `*` `・` `•` `●` `○` | 箇条書きの記号 |
| `MARKUP_CHARS` | `-` `=` `_` `|` `:` `*` `#` `─` `—` `―` `~` `+` | これと空白だけの行は記号だけの行 |

`CONSTANT_NAMES` の 19 個（上の表と集合）が凍結の対象。

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
- `ANAPHORS`: `en:it`、`en:that`
- `GENERIC_OBJECTS`: `en:change`、`en:code`、`en:file`、`en:files`、`en:job`、`en:work`、`ja:もの`、`ja:コード`、`ja:ファイル`、`ja:仕事`、`ja:変更`
- `EN_DETERMINERS`: `en:a`、`en:our`、`en:that`、`en:the`

中間職がレビューで挙げた 6 つ（`作った者` `確かめる者` `どれにも当てはまらない仕事` `系列` `動かす` `hold`）はすべてこの一覧に含まれる。r1・r2（読解器が読める形の説明文）に現れる項目は `constants_in_data.json` の `r1-r2` にある。

**第 2 ラウンド（レビュー第 1 ラウンドへの対応）で足した・変えた定数の項目: なし**（ハッシュは凍結と同じ `095335d5…870a`。`artifacts/w2-h2/constants_final.txt`）。
第 2 ラウンドで足したのは定数でない処理だけである（コピュラの割れる読み・複数語の呼び名・時制・上書きの範囲。判断 D13〜D16）。

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
 "relations": [...], "reading": {"units", "skipped_markup", "by_status", "auto_resolved", "lookup"},
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

## 19. 既知の制限

- **読解器の被覆が狭い**（0 章）。普通に書かれた説明文は、棄権の理由（`NO_SUPPORTED_CLAUSE` `EN_UNREAD` `NO_PREDICATE_TOKEN` など）の件数どおり、ほぼ全部が棄権になる。単位の数と理由は「測定結果」の区間と `artifacts/w2-h2/reader_gaps.md`。
- **受け皿の要求**: 条件つきの割り当てだけがある役割、無条件の割り当てが 2 つある役割は、記録層が拒否して棄権になる（作り足さない）。
- **R3 と未使用の実装**: 「検証は X」と書かれ、実装がまだ使われていない検証の仕事は、正解が route でも経路づけ器が決めない（`PRIOR_ROLE_UNUSED`）。誤って振ることにはならない。実装を使ったあとの検証でも、検証役と実装役の系統の関係が言われていなければ `LINEAGE_UNDECLARED`。
- **説明的な呼び名**（「重い方」「the slow one」）はそれ自体が最初の呼び名でも棄権。別名として後から出る場合も、別名の表に入らないので止まる。
- **複数語の英語の呼び名**（`Big Rook` のような固有名）は棄権（D16）。別名の取り出し元は `呼ぶ`・`call` の文だけで、コピュラ（「L は Luna だ」）の別名は読まない（D14）。
- **過去形の文**は棄権（D15）。「ハルが実装をやった」だけの説明文では、実装の仕事は決まらない（`UNREPRESENTABLE`）。未来（`Rook will review the code.`）は読解器が `nonpast` と返すので宣言として読む。
- **追記の上書き**は、同じ範囲・同じ種類の言明なら呼び名が違っても置き換える（D13）。「追記」が足すだけの意味で書かれていれば、本来は同点（undecided）が正解になる。
- **普通名詞の主語**（「チームがレビューをやる」）は、配置がスタブで名前と区別できず、`HUMAN_TERMS` の小さい閉じた表にも無ければ呼び名になる（申し送り。読解器の被覆が狭く、他の全文が読める説明文の中でしか効かない）。
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
