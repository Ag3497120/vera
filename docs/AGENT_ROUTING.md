# エージェントの分業と経路づけ (W2-h)

人間が最初に一度だけ書く「どのエージェントがどういう性質か」「どの仕事をどこへ振るか」の表から、Vera の指揮者が
仕事ごとに使うエージェントを決める。決定は 1 件ずつ、規則の id か LLM 証言の id つきで追記専用の台帳に残る。

- 実装: `verantyx/agent_routing.py`（記録の型・意味の検査・経路づけ器）、`verantyx/project_frame.py`（枠の読み込み器）、
  `verantyx/conductor_run.py`（`conduct_entry` への接続）、`verantyx/cli.py`（`conduct`）
- 見本の枠: `docs/frames/examples/routing_two_lineages.md`
- 試験: `tests/test_agent_routing.py` `tests/test_agent_routing_dsl.py` `tests/test_agent_routing_role.py`
  `tests/test_agent_routing_relation.py` `tests/test_conduct_routing.py`

## 0. 三層の設計（層の向きを逆にしない）

```
producer（枠の DSL: project_frame.py ／ 将来: 自由文の読解器 ／ テスト: 辞書）
   └─ 記録を作るだけ。見るのは行の「形」だけ
        ↓ AgentRecord / RoutingRule / RoutingPrecedence（それぞれ basis つき）
記録層 verantyx/agent_routing.py: build_routing_table(...)
   └─ 意味の検査（語彙外・重複・既定行の欠落・循環・参照切れ）は、ここだけで行う
        ↓ RoutingTable
経路づけ器 verantyx/agent_routing.py: route(table, request, chooser_factory=...)
   └─ DSL を知らない。記録だけを受け取り、型付きの RoutingDecision を返す
```

人間の説明を枠の閉じた文法で書かせるのは **初期版の producer** にすぎない。必須なのは、人間がその話題について
書いた説明を汎用意味理解で読み、同じ記録に落とせること（次のチケット W2-h2）。そのために

- 記録の型は DSL から独立している（`agent_routing.py` は `project_frame` / `conductor_run` / `cli` を import しない。
  `tests/test_agent_routing.py::test_R0_*` が固定している）。
- 意味の検査は記録層に 1 か所だけある。自由文の producer も同じ検査を通るので、拒否の型は書き方によらない。DSL 側に
  同じ検査を二重に書かない（`test_the_dsl_does_not_repeat_the_record_layers_checks`）。
- 決定は宣言の並び順に依存しない。優先順の一覧の中の順は人間が宣言した優先順位なので使うが、エージェント表の行の順・
  規則の行の順は使わない。
- 記録は DSL の書き方を持ち込まない。「役割の受け皿（人間の "それ以外は…"）」は規則 ID `DEFAULT` という名前ではなく
  `RoutingRule.fallback` の欄で表す（DSL の producer が `DEFAULT:` の行をこの欄にする）。理由・並行数・effort・model は、
  人間が書かなかったなら `None`（未申告）で持てる。書かれていない値を producer が作って `declared` を名乗ることはしない。
  出所は 1 文に限らず、複数の文を持てる（下の表）。
- 種類（`kinds`）と系統（`lineage`）も、人間が書かなかったなら `None`（未申告）で持てる。「実装は Sonnet 5.5」は役割だけを言い、
  種類を言っていない。producer が全部の種類を埋めると、人間が言っていない「この種類も宣言した」を `declared` として作ることになるので、
  埋めない。経路づけ器は、`kinds` が未申告の候補を **種類では除外しない**（種類の限定を付けずに名指された、と読む。限定に反するとは読まない）。
  ただし見えない解決にしないため、決定の `kind_fit`（候補ごとに `declared` ＝宣言した種類に合う / `undeclared` ＝未申告）に残す。
  `lineage` が未申告のエージェントは、独立の判定に関わらない役割（生成・読解など）ならそのまま使える。独立の判定に関わるとき
  （検証役の `independent_of`）に限り、`LINEAGE_UNDECLARED` で除外する（`PRIOR_ROLE_UNUSED` とも `SAME_LINEAGE` とも混ぜない。
  比べる側の実装役の系統が未申告のときも同じ）。
- **系統の名札は producer が宣言した分割である（記録層の約束）**。1 つの表の中で、同じ `lineage` の名札は同系統、違う名札は
  別系統として扱う。記録層は 2 つの呼び名（`Claude系` と `Anthropic系` など）が同じ系統かどうかを知らない。だから、呼び名を
  揃えられない producer は **名札を付けない**（`None`）。そして人間が言った関係だけを `LineageRelation(a, b, relation, basis)`
  （`a` `b` はエージェント ID、`relation` は `same` か `distinct`、向きは持たない、出所つき）として `build_routing_table(...,
  lineage_relations=...)` に渡す。言われていない関係（3 体で「A と B、A と C は別系統」とだけ言われたときの B と C）は、名札でも関係でも
  作らない。同じ系統の閉包は「同じ名札」と `same` の関係の推移閉包で、入力の順に依存しない。矛盾する記録（閉包の中に違う名札が 2 つ、
  閉包の中に `distinct`、同じ組に `same` と `distinct`）は表を作らず `LINEAGE_CONFLICT`、同じ組・同じ関係の 2 件目は
  `DUPLICATE_LINEAGE_RELATION`、参照切れは `UNKNOWN_AGENT_REF`、自分自身との関係・語彙外の関係・出所の無い関係は `BAD_VALUE`。
- 役割（`roles`）・種類（`kinds`）・系統（`lineage`）は **人間が言ったときだけ** 記録に入れる。役割も未申告（`None`）で持てる
  （空の一覧は `BAD_VALUE`。言わなかったことと、言ったが空、は別）。「攻撃と大きなファイルの読解は codex gpt-6-luna xhigh」は役割を
  言っていないので、役割を作らずに記録にできる（`roles=None`、`kinds=[attack, read_large_file]`）。経路づけ器は、`roles` が未申告の候補を
  **役割では除外しない**。見えない解決にしないため、決定の `role_fit`（候補ごとに `declared` ＝宣言した役割に合う / `undeclared` ＝未申告）に
  残す（`kind_fit` と同じ作り）。
- エージェント ID と `lineage` は人間の言葉そのもの（`Sonnet 5.5`、`ソネット`、`Claude系`）を記録層が受け付ける。検査するのは「空でない文字列で、
  前後に空白・制御文字が無い」ことだけ。ASCII のトークンの形は、行を空白・`:`・`,` で切る DSL の行の形の制約なので、DSL の producer が
  `MALFORMED_ROW` で見る（記録層の検査ではない）。規則 ID・優先順位 ID は producer が付ける名前なので従来どおり ASCII のトークン。
- 比較用の値 `RoutingDecision.essence()` は、規則を **付けられた名前でなく中身**（条件の集合・優先順・`fallback`）で、除外も同じ
  く中身で数える。自由文の producer は規則 ID を自分で作るので、ID が違っても同じ決定なら一致する。エージェント ID は人間が名指す
  もの（どの producer でも同じ名で呼ばれる前提）なのでそのまま比べる。この前提が崩れる producer（エージェントに別名を付ける）は、
  essence を使う前に名前を揃える必要がある。
- これらが固定していること（試験）: 行の順の入れ替え（`test_R0_the_order_of_the_rows_never_changes_the_decision`、
  `test_R0_essence_does_not_depend_on_the_names_or_the_order_the_producer_gave`）、DSL の producer と辞書の producer の同一性
  （`test_R0_the_dsl_producer_and_the_dictionary_producer_give_the_same_decision`）、規則の名前を全部付け替えた表と DSL の表の
  同一性（`test_R0_fallback_*`）、受け皿の名前に依らないこと、2 文の出所（`test_R0_basis_*`）、未申告の値を持つ表
  （`test_R0_unsaid_values_*`）、種類を言わない表（`test_R0_unsaid_kinds_*`）、人間の呼び名と系統名・系統を言わない表
  （`test_R0_names_*`、`test_R0_lineage_unsaid_*`、`tests/test_conduct_routing.py::test_R3_lineage_unsaid_*`）。**固定していないこと**: 実際の自由文からの読み取り（W2-h2 の仕事）と、エージェント ID の別名への
  耐性（`Sonnet 5.5` と `claude-sonnet-5-5` を同じエージェントとは数えない）。

記録には出所欄 `basis` がある。

| basis.kind | 意味 | 必須の欄 |
|---|---|---|
| `declared_dsl` | 枠の DSL の行から作った | `line`（行番号）。`witnesses` に元の行（1 つ） |
| `declared_text` | 人間の自由文から読んだ | `witnesses`（原文の文を **1 つ以上**。0 個・空の文は拒否）。1 つの記録の値が複数の文にまたがるとき（「Codex は実装に向く。」「Codex と Claude は別系統。」）は全部を残す。`Basis.text(source, "1 文")` の呼び方もそのまま使える |

台帳の `agent_basis` には `kind` / `source` / `line` / `witnesses`（文の一覧）が全部出る。

人間が書いた特性（速い・安い・得意、モデル名、系統）は **証言**（declared）であり、実測ではない。

## 1. 枠の文法（初期版の producer）

枠の Markdown に 3 つの節を足す（どれも省略できる。ただし `[agents]` と `[routing]` は両方要る）。

```
[agents]
ID: adapter=<codex|claude|fake> model=<m> effort=<e> roles=<役割,...> kinds=<種類,...> lineage=<系統名> concurrency=<n> [note=<識別子>]

[routing]
ID: <条件> [& <条件>...] => <エージェントID の優先順,...>: <理由>
DEFAULT: role=<役割> => <エージェントID の優先順,...>: <理由>

[routing_precedence]
ID: <高い規則ID> > <低い規則ID>: <理由>
```

- `[agents]`: 1 行 1 エージェント。値に空白は書けない。`roles` / `kinds` は `,` 区切り。`note` は省略可で、短い識別子だけ
  （自由文は不可）。エージェント ID は英字で始まる英数字・`_`・`-`、`lineage` は英字で始まる英数字・`_`・`.`・`-` に限る（行を切るための
  形の制約。外れると `MALFORMED_ROW`）。
- `[routing]` の条件は閉じた形だけ: `role=<役割>`（0 個か 1 個。チケットの文法どおり省略できる。省略した規則は、`kind` / `size` が合えば
  **どの役割の要求にも一致** する。例 `ATTACK: kind=attack => Luna: 攻撃は Luna`）、`kind=<種類>`、`size=<small|medium|large>`、
  `independent_of=<役割>`（`role=` の無い規則には書けない）、これらの `&` 結合。`DEFAULT` は役割ごとに 1 行ずつ書く（ID が `DEFAULT` の
  行だけ繰り返してよい）。`DEFAULT` 行の `role=` は必須（無ければ `MISSING_ROLE_CONDITION`）。
  `DEFAULT` という名前は **この行の形の約束** で、記録では `fallback=true` の欄になる（名前では判定しない）。
- この行の形では、エージェント行の `roles` `model` `effort` `kinds` `lineage` `concurrency` と、規則・優先順位の行の `: 理由` は **必須**（行の形の要求。
  無ければ `MISSING_FIELD`）。記録の型は、`kinds` `lineage` `model` `effort` `concurrency` と理由を人間が書かなかった場合に未申告（`None`）で
  持てる（自由文の producer 向け）。DSL の行の `roles=` は必須のまま（無ければ `MISSING_FIELD`）。
- 系統の **関係**（「A と B は別系統」）を書く DSL の文法は無い（チケットの文法は名札だけ）。DSL の producer は名札だけを作り、同じ名札は
  同系統・違う名札は別系統になる（0 章）。関係の記録は、自由文の producer と辞書の producer が渡す。
- `[routing_precedence]`: `[conflict_precedence]` と同じ形・同じ読み。推移的に読み、循環は拒否する。`DEFAULT` は名指せない。
- `[agent_settings]` の `task_kind: <種類>` が仕事の種類（`--task-kind` が優先）。

見出しの文法行は `docs/frames/vera_project_frame.md` にも足してある（ファイルの末尾の注釈。先頭に足すと、既存の試験が見る記録の行番号がずれるため）。

## 2. 閉じた語彙（`verantyx/agent_routing.py` の定数）

| 定数 | 値 |
|---|---|
| `ADAPTERS` | `codex`, `claude`, `fake` |
| `ROLES` | `implement`, `verify`, `review`, `generate`, `read`, `answer` |
| `TASK_KINDS` | `small_fix`, `feature`, `large_refactor`, `test_authoring`, `review`, `verification`, `attack`, `bulk_generation`, `read_large_file`, `closed_choice` |
| `SIZES` | `small`, `medium`, `large` |
| `BASIS_KINDS` | `declared_dsl`, `declared_text` |
| `RECORD_ERRORS`（記録層の拒否） | `UNKNOWN_ADAPTER` `UNKNOWN_ROLE` `UNKNOWN_KIND` `UNKNOWN_SIZE` `BAD_VALUE` `DUPLICATE_AGENT_ID` `DUPLICATE_RULE_ID` `UNKNOWN_AGENT_REF` `UNKNOWN_RULE_REF` `MISSING_ROLE_CONDITION` `BAD_CONDITION` `RULE_AGENT_MISMATCH` `MISSING_ROLE_DEFAULT` `DUPLICATE_FALLBACK` `INDEPENDENCE_CYCLE` `PRECEDENCE_CYCLE` `DUPLICATE_PRECEDENCE` `PRECEDENCE_ON_DEFAULT` `EMPTY_TABLE` `LINEAGE_CONFLICT` `DUPLICATE_LINEAGE_RELATION` |
| `LINEAGE_RELATIONS`（人間が言える関係） | `same`, `distinct` |
| `LINEAGE_VERDICTS`（2 体について記録層が言えること） | `same`, `distinct`, `undeclared` |
| `DSL_ERRORS`（行の形だけ） | `MALFORMED_ROW` `UNKNOWN_FIELD` `MISSING_FIELD` `DUPLICATE_FIELD` `MISSING_SECTION` `AGENT_SETTINGS_CONFLICT` |
| `EXCLUSION_REASONS`（候補の除外） | `ROLE_NOT_DECLARED` `KIND_NOT_DECLARED` `CONCURRENCY_FULL` `CONCURRENCY_UNDECLARED` `SAME_LINEAGE` `PRIOR_ROLE_UNUSED` `LINEAGE_UNDECLARED` |
| `KIND_FIT_VALUES`（決定の `kind_fit` と `role_fit` の値） | `declared`, `undeclared` |
| `UNDECIDED_REASONS`（決まらなかった型） | `ROLE_NOT_ROUTABLE` `NO_VIABLE_CANDIDATE` `TESTIMONY_UNAVAILABLE` `TESTIMONY_ABSTAINED` `TESTIMONY_FAILED` `TESTIMONY_REFUSED` `TESTIMONY_OUT_OF_SET` |
| `STAGES` | `rule`, `precedence`, `llm_testimony`, `NONE` |

R1 の 5 つの拒否（語彙外の種類・未知のアダプター・同じ ID の重複・役割の既定行の欠落・`independent_of` の循環）は、
それぞれ `UNKNOWN_KIND` `UNKNOWN_ADAPTER` `DUPLICATE_AGENT_ID` `MISSING_ROLE_DEFAULT` `INDEPENDENCE_CYCLE` という別の型で返る。
枠から読んだときは `RoutingParseError.code` に、`conduct` では `REFUSED` 行の `reason: ROUTING_INVALID` と `code` に出る。

「無い」「決まらない」「読めない」は別々の型で返す。`PRIOR_ROLE_UNUSED`（その役割はまだこの仕事で使われていない）は、独立の条件を
「満たす」とも「満たさない」とも決めない。`LINEAGE_UNDECLARED`（比べる系統のどちらかを人間が書かなかった）も同じく、同系統とも別系統とも決めない
（`RoutingRequest.used_lineages` の要素 `None` が「使われたが系統は不明」。空は「まだ使われていない」で別）。既知の系統が衝突しているなら、
他に不明な系統があっても `SAME_LINEAGE`。`used_agents`（使われたエージェントの ID）で渡したときは、候補と各エージェントの
`lineage_relation` の 3 値（`same` / `distinct` / `undeclared`）がそのまま `SAME_LINEAGE` / 通る / `LINEAGE_UNDECLARED` になる（4 章）。`NO_VIABLE_CANDIDATE`（候補がすべて除外された）と `ROLE_NOT_ROUTABLE`（表にその役割が無い）
と `TESTIMONY_*`（証言で決まらなかった）も別の型。

## 3. 大きさ（size）のしきい値

仕事の大きさは、枠の許可パス数と受入条件数（機械判定＋人間判定）から決め、2 つが違えば **大きいほう** にする。
決定には両方の値と帯を記録する（`size_basis`）。

| 見るもの | small | medium | large |
|---|---|---|---|
| 許可パス数 | 1〜2 | 3〜5 | 6 以上 |
| 受入条件数 | 1〜3 | 4〜7 | 8 以上 |

これは **設計値**（作者が決めた値）であり、実測から導いたものではない。小さく見積もって軽いエージェントに振る誤りのほうが
高くつく、という理由で大きいほうを採る。定数は `SIZE_THRESHOLDS`。

## 4. 解消の順（事前登録。`route` の 1 か所にだけ書いてある）

1. **規則**: `role` / `kind` / `size` が一致する規則を、それぞれ自分の優先順の先頭から見る。**一致しうる規則** は、`role=` が要求の役割に
   一致する規則と、`role=` の無い規則で `kind` / `size` が合うもの。その役割の規則も、要求に一致する `role=` の無い規則も無ければ
   `ROLE_NOT_ROUTABLE`（この判定は公開関数 `routable(table, request)` の 1 か所で、指揮者も同じものを呼ぶ）。規則は当てはまったのに誰も残らなかったとき
   （役割なしの規則に頭が無く、その役割の受け皿も無いときを含む）は `NO_VIABLE_CANDIDATE` で、`ROLE_NOT_ROUTABLE`（経路が無い）とは別の型。
   次のものは **除外**（理由つきで決定に残す）: エージェントが役割・種類を宣言していない（`ROLE_NOT_DECLARED` / `KIND_NOT_DECLARED`。
   役割・種類を **未申告** のエージェントは除外しない）、`concurrency` の上限に
   達している（`CONCURRENCY_FULL`。種類を **未申告** のエージェントは `KIND_NOT_DECLARED` では除外せず、決定の `kind_fit` に `undeclared` と残す）、`concurrency` を人間が書かなかったエージェントにすでに動いているものがある
   （`CONCURRENCY_UNDECLARED`。空きがあるかどうかを推測しない。動いているものが無いときは除外しない）、独立の条件を
   満たさない（`SAME_LINEAGE` / `PRIOR_ROLE_UNUSED` / `LINEAGE_UNDECLARED`。下の「検証役の独立」）。最初に除外されなかった 1 体がその規則の「頭」。頭の無い規則は落ちる。
   どの受け皿でない規則にも頭が無いときだけ、その役割の受け皿の規則（`fallback`。DSL では `DEFAULT` 行）を使う。
   頭が 1 種類なら `stage=rule`、`decided_by=rule:<規則ID>`（同じ頭の規則が複数なら ID を並べる）。
2. **優先順位**: 頭が割れたら、`[routing_precedence]` を推移的に読む。他の（頭の違う）一致規則に支配されていない規則の頭が
   1 つに決まれば `stage=precedence`、使った優先順位の ID を `precedence_used` に残す。
3. **LLM 証言**: それでも割れたら、既存の閉じた選択の LLM 照会（`verantyx/llm_choice.py` の公開 API をそのまま使う。変更しない）に
   「この仕事に最も合うエージェントはどれか」を、残った頭の ID の閉じた一覧で聞く。順序と文面を変えた 2 回の問い合わせが
   同じ候補を指したときだけ採用し（証言型。1 回目と 2 回目が食い違えば決定にならない）、`stage=llm_testimony`、
   `decided_by=llm_testimony:<llm_choice の decision_id>` と台帳（`<state>/routing_choice.jsonl`）の記録を残す。
   過去の決定の再利用は `testimony.cached` に出る。
4. **型付きで止まる**: 決まらなければ `stage=NONE`、`undecided_reason`（`UNDECIDED_REASONS`）つきで返し、`conduct` は
   `FrameRefusal("ROUTING_UNDECIDED")` で起動前に止まる（完了にしない）。

同点は棄権する。行の順・辞書順・`min` / `max` で勝者を作らない。`decided_by` や `candidates` の並びを整列するのは表示のためだけで、
選択には使わない。

### 検証役の独立（R3）

`role=verify` の **要求** には、どの規則が一致しても（`role=` の無い規則でも、`DEFAULT` でも）`independent_of=implement` が **暗黙に付く**
（独立の役割は規則の `role=` ではなく要求の役割で決める。`independent_roles_for(request.role)`）。つまり、その仕事の実装役に使った
エージェントと同じ系統の検証役は `SAME_LINEAGE` で除外される。候補が全部除外されたら `ROUTING_UNDECIDED`（`NO_VIABLE_CANDIDATE`）。
外せるのは、規則に `role=verify & independent_of=none` と書いたときだけで、そのとき同系統が許され、決定に
`independence: {"implement": "waived_by:rule:<ID>"}` が残る。`independent_of=none` は verify 以外の規則では `BAD_CONDITION`。
`role=` の無い規則に `independent_of` は書けない（どの役割の要求にも一致するので自己ループになる。`BAD_CONDITION`）。

2 体の系統の関係は `lineage_relation(table, a, b)`（経路づけ器も指揮者も同じ関数を使う）が 3 値で返す。
- **同じ閉包**（同じ名札、または `same` の関係の鎖で結ばれる。`a == b` を含む）→ `same` → 候補は `SAME_LINEAGE` で除外（detail に、同じ名札か
  `same` の関係か、同じエージェントか、を残す）。
- 違う閉包で、両方に名札があって違う、**または** 2 つの閉包の間に `distinct` の関係がある → `distinct` → 通る。両方の根拠があれば両方を残す
  （どちらかを選ばない）。
- どちらでもない → `undeclared` → `LINEAGE_UNDECLARED` で除外（`PRIOR_ROLE_UNUSED` ・`SAME_LINEAGE` とは混ぜない）。

要求は、使われたエージェントを `used_agents`（役割 → エージェント ID の並び）か、使われた系統の名札を `used_lineages` で渡す。**同じ役割を両方で渡すと
`ValueError`**（どちらを信じるかを黙って決めない）。表に無い ID を `used_agents` に渡したときも `ValueError`（呼び出し側の誤り）。`used_lineages` の判定と
文言は変えていない。指揮者は `used_agents`（実装役の ID）を渡す。`same_lineage_as_implementer` は同じ関数の 3 値（`same` → `True`、`distinct` → `False`、
`undeclared` → `null`）。通った候補の根拠は決定の `independence_basis`（役割 → 根拠の一覧）に残る。`used_agents` 経由は使われたエージェントごとに
`verdict` / `labels` / `relations`（間の `distinct` の関係。`basis.witnesses` まで辿れる）/ `joined_by`（閉包の中の `same` の関係）、`used_lineages` 経由は
使われた名札と候補の名札。`independence` の値（`distinct_lineage`・`waived_by:rule:<ID>`）は変えていない。

## 5. 指揮者との接続と後方互換

- 枠に `[agents]` があるとき（経路づけあり）: `conduct` は `--adapter` を **省く**。実装役・検証役は経路づけ器が選び、
  選ばれたエージェントの adapter / model / effort が従来の `settings` / `verification` の形に入る（`source: "routing"`、
  `agent_id` つき）。`_run_agent_process` と旧 `ConductorRun` は変更していない。`--adapter` `--model` `--effort`
  `--verifier-adapter` `--verifier-model` `--verifier-effort` を渡すと `AGENT_SETTING_INVALID`（片方を黙って勝たせない）。
  `[agent_settings]` に `codex_model` `codex_effort` `claude_model` `claude_effort` `verifier_adapter` `verifier_model`
  `verifier_effort` があれば、読み込み時に `ROUTING_INVALID`（code `AGENT_SETTINGS_CONFLICT`）。時間・回数・権限・`max_concurrency`・
  `task_kind` は従来どおり使う。
- 枠に `[agents]` が無いとき: 従来の `[agent_settings]` と `--adapter` のまま動く。台帳の行の型の列は変わらず、`ROUTING_*` 行は
  1 行も出ない。印は `FRAME_COMPILED.routing`（`"legacy_agent_settings"`、経路づけありなら `"routed"`）。`--adapter` が無ければ
  `AGENT_SETTING_MISSING`。JSONL 形式の枠は常にこの旧経路。
- 起動前に止まるもの: `ROUTING_INVALID`、`ROUTING_UNDECIDED`、`AGENT_SETTING_INVALID` / `AGENT_SETTING_MISSING`（矛盾・`task_kind` 欠け）。
  いずれも `AGENT_START_CALLED` の行が 0 件（試験で固定）。

## 6. 台帳の行

### `ROUTING_DECISION`（決定 1 件につき 1 行。`values: "declared"`）

`job_id`（= `run_id`）, `role`, `task_kind`, `size`, `size_basis`, `agent_id`（決まらなければ `null`）, `stage`, `decided_by`,
`matched_rules`, `candidates`, `excluded`（`agent_id` / `rule_id` / `reason` / `detail`）, `kind_fit` と `role_fit`（候補ごとの `declared` / `undeclared`）,
`precedence_used`, `testimony`,
`independence`, `independence_basis`（独立の根拠。4 章）, `undecided_reason`, `agent_basis`（選ばれたエージェントの記録の出所）。実装役の行、検証役の行の順に、
エージェントを起動する前に書く。LLM 証言の問い合わせ先（`answer` 役）の決定も 1 件として同じ形で書く。
（行の型名と衝突するので、仕事の種類のキーは `kind` でなく `task_kind`。）

`role_fit` と `independence_basis` は第 4 ラウンドで足したキー。R7 の本物の台帳（`artifacts/w2-h/live/`）は第 2 ラウンドの記録なので、この 2 つのキーを持たない
（取り直していない。理由: 名札だけの DSL の見本の枠で決定が変わらないことを dry-run で確かめた。`artifacts/w2-h/r4/dry_run_decisions.txt`）。

### `ROUTING_MEASURED`（実行が終わった後に 1 行。`values: "measured"`）

`job_id`, `outcome`（終了の型）, `rounds`（この run の `AGENT_START_CALLED` の数）, `elapsed_seconds`。起動前の拒否と dry-run では書かない。
**貯めるだけで、経路づけ器は読まない。**

### 2 つの行は混ぜない

`DECLARED_KEYS` と `MEASURED_KEYS` は交わらず（`job_id` と `values` だけが両方に付く）、決定の行に実測のキー、実測の行に宣言のキーは入らない。
理由: 人間の「速い」「安い」「得意」は申告（証言）で、合格率・ラウンド数・所要時間は観測だから。混ぜると、申告が実測のような顔をして
後の経路づけに使われ、外れても気づけなくなる。今回は経路づけに実測を使わない（使うのは別チケット）。

## 7. 本物での確認（R7）

`docs/frames/examples/routing_two_lineages.md`（実装 = codex 系、検証 = claude 系、レビュー = claude 系の別モデル、生成 = codex low）で
`conduct` を `--adapter` なしに 1 回通した。出力は `artifacts/w2-h/live/` にある。

- 起動回数: codex 1 回・claude 1 回（`artifacts/w2-h/live/launches.txt`。上限は各 3 回）。
- 台帳（`artifacts/w2-h/live/a_tally_routed/ledger.jsonl`、要約は `artifacts/w2-h/live/live_checks.txt`）で、実装役が
  `CodexImpl`（`rule:IMPL_FEATURE`）、検証役が `ClaudeVerify`（`rule:VERIFY_ANY`、`independence: distinct_lineage`）に、経路づけ器の
  決定で振られ、`LAUNCH_PLANNED.argv[0]` が codex、`VERIFIER_LAUNCH_PLANNED.argv[0]` が claude だったこと、終了の型が `COMPLETE`
  だったことが追える。
- 秘密らしき文字列の走査: `artifacts/w2-h/live/a_tally_routed/secret_scan.txt`。

## 8. 判断記録（チケットに書かれていない点を保守的な側で決めたもの）

| # | 論点 | 決定 |
|---|---|---|
| J1 | 仕事の種類はどこから来るか | `[agent_settings] task_kind` と `--task-kind`（CLI が勝つ）。経路づけのある枠で欠けていれば `AGENT_SETTING_MISSING`。自由文から推測しない。検証役の種類は `verification`、証言の問い合わせ先は `closed_choice` に固定 |
| J2 | `--adapter` と `[agents]` | `[agents]` のある枠では `--adapter` / `--model` / `--effort` / `--verifier-*` を拒否。無い枠では `--adapter` が要る。Python の `conduct_entry` は `adapter=None` を許す |
| J3 | `[agents]` のある枠の `[agent_settings]` | モデル・effort・検証役の adapter を書いたら読み込み時に拒否（同じことを 2 か所に書かせない） |
| J4 | 既定行（受け皿） | 記録の `fallback` 欄で表し、名前では判定しない。役割ごとに 1 つ（重複は `DUPLICATE_FALLBACK`）。条件は `role=` だけ（検証役は `independent_of=none` も可）。受け皿でない規則に頭が 1 つでもあればそちら、無ければ受け皿。DSL では ID `DEFAULT` の行が受け皿。受け皿は優先順位に名指せず（`PRECEDENCE_ON_DEFAULT`）、規則の名前と同じ名前は付けられない（`DUPLICATE_RULE_ID`） |
| J5 | 既定行の欠落の範囲 | `[agents]` の `roles=` に出る役割と規則の `role=` に出る役割は全部 DEFAULT を要する。表に出ない役割は `ROLE_NOT_ROUTABLE` |
| J6 | 検証役の独立の既定 | `role=verify` の **要求** には、一致した規則が `role=` を持たなくても `independent_of=implement` が暗黙に付く。外れるのは `role=verify & independent_of=none` と書いた規則だけで、決定に残る |
| J7 | 独立の対象の役割がまだ使われていない | `PRIOR_ROLE_UNUSED` で除外（満たすとも満たさないとも決めない） |
| J8 | 大きさのしきい値 | 3 章。設計値 |
| J9 | 規則の一致と候補の除外 | 一致は `role/kind/size` だけ。`independent_of`・concurrency・エージェントの宣言は候補の除外 |
| J10 | 優先順位 | 推移的に読む。頭の違う他の一致規則に支配されていない規則の頭だけが次の段へ進む |
| J11 | LLM 証言の問い合わせ先 | Python からは `routing_chooser`。CLI では枠の `answer` / `closed_choice` のエージェントを (a)(b) だけで経路づけ（再帰させない）して作る。fake・無しなら `TESTIMONY_UNAVAILABLE`。この判断は、この問い合わせ先の決定も `ROUTING_DECISION` 1 行として残す |
| J12 | 仕事 id | 1 回の実行（`run_id`）= 1 つの仕事。`job_id = run_id` |
| J13 | `ROUTING_UNDECIDED` | 実装役・検証役とも起動前に決め、決まらなければ決定の行（`agent_id: null`）を書いてから拒否 |
| J14 | 実装役が fake | 旧経路の fake と同じ道。検証役の経路づけはしない |
| J15 | やり直し（W2-b の retry） | 決定は 1 回の実行で 1 回。やり直しも同じエージェント |
| J16 | JSONL 形式の枠 | 常に旧経路 |
| J17 | `ROUTING_MEASURED` | 実行後に `conduct_entry` が 1 行。dry-run では書かない |
| J18 | 検証役が fake に振られた | `AGENT_SETTING_INVALID` で起動前に拒否（検証役は codex / claude のみ。記録の型では fake の検証役を許す） |
| J19 | `kind` の台帳キー | `task_kind`（台帳行の型名 `kind` と衝突するため） |
| J20 | 人間が書かなかった値（理由・並行数・effort・model） | 記録は `None` で持ち、作らない。`concurrency` が `None` で、そのエージェントにすでに動いているものが在るときだけ `CONCURRENCY_UNDECLARED` で除外（動いているものが無い最初の 1 回は除外しない）。選ばれた実装役・検証役を起動するのに `model` / `effort` が `None` なら、起動前に `AGENT_SETTING_MISSING`（`missing` にエージェント ID と欠けた欄）で止め、既定値を使わない。LLM 証言の問い合わせ先の `model` / `effort` が `None` なら証言は `TESTIMONY_UNAVAILABLE` |
| J21 | 枠の DSL が必須とするもの | 行の形の要求（`model` `effort` `concurrency` と `: 理由`）は DSL の producer が見る。記録層の検査ではない（W2-h2 の producer は書かれていない値を省ける） |
| J22 | 出所の文の数 | `declared_text` は 1 文以上（空の文・0 文は拒否）。`declared_dsl` は元の行 1 つ |
| J23 | 種類（`kinds`）を人間が書かなかったエージェント | 記録は `kinds=None` で持つ（空の一覧は `BAD_VALUE`。書かれたときの検査は従来どおり）。経路づけ器は種類で除外せず、決定の `kind_fit` に `undeclared` と残す。`kind=` 条件のある規則がそのエージェントを名指しても `RULE_AGENT_MISMATCH` にしない（宣言した種類に含まれないときだけ `RULE_AGENT_MISMATCH`）。DSL の producer は行の形として `kinds=` を必須にする（`MISSING_FIELD`）。全部の種類を埋めて `declared` を作ることはしない |
| J24 | エージェント ID・系統名の形、系統を人間が書かなかったエージェント | 記録層は ID と `lineage` を「空でない文字列・前後の空白と制御文字なし」だけ検査する（人間の呼び名をそのまま持てる）。ASCII のトークンの形は DSL の producer の検査（`MALFORMED_ROW`）。`lineage` は `None` で持て、独立の判定に関わる候補だけ `LINEAGE_UNDECLARED` で除外する。指揮者は検証役の要求に実装役の ID を `used_agents` で渡し、実装役との関係が分からなければ（`undeclared`）全候補が除外されて起動前に `ROUTING_UNDECIDED`（`NO_VIABLE_CANDIDATE`）。`independent_of=none` の規則は系統を見ない。`RUN_LIMITS.verification.same_lineage_as_implementer` は、関係が分からなければ `null`（真偽を作らない） |
| J25 | 系統の関係の記録（F8） | 名札は producer が宣言した分割（同じ名札＝同系統、違う名札＝別系統）。呼び名を揃えられない producer は名札を付けず、`LineageRelation`（`same` / `distinct`、向きなし、出所つき）で言われた関係だけを渡す。同系統の閉包は名札と `same` の推移閉包で、順序に依らない。矛盾は `LINEAGE_CONFLICT`（黙って片方を勝たせない）、重複は `DUPLICATE_LINEAGE_RELATION`。経路づけ器の独立の判定は候補と「使われたエージェント」の関係（`used_agents`）。言われていない関係は作らず `LINEAGE_UNDECLARED`。根拠は `independence_basis` に残し、`independence` の既存の値は変えない。`used_lineages` の経路は文言まで変えず、同じ役割を両方で渡すと `ValueError`。DSL に関係の文法は足さない |
| J26 | 役割を言わない割り当て（F9） | 規則の `role=` は 0 個か 1 個。無い規則は `kind` / `size` が合えばどの役割の要求にも一致し、受け皿の要求は生まない（`MISSING_ROLE_DEFAULT` の範囲は広げない）。受け皿の `role=` 欠けだけが `MISSING_ROLE_CONDITION`。`role=` の無い規則の `independent_of` は `BAD_CONDITION`（どの役割の要求にも効くので自己ループ。検証の独立は要求の役割で暗黙に効く）。`AgentRecord.roles` は未申告 `None` で持て（空は `BAD_VALUE`）、役割では除外せず `role_fit` に残す。`role=` の無い規則に頭が無くその役割の受け皿も無いときは `NO_VIABLE_CANDIDATE`（規則は当てはまったが誰も残らなかった。`ROLE_NOT_ROUTABLE` は「その役割の規則も、一致する役割なしの規則も無い」）。指揮者の「検証役を言ったか」は `routable` で決める |

## 9. W2-h2 への約束

- 自由文の説明を読む producer は、`Basis.text(source, <原文の文、または文の一覧>)` を付けた記録（`AgentRecord` / `RoutingRule` /
  `RoutingPrecedence`）を `build_routing_table` に渡す。経路づけ器は記録だけを受け取るので、`route` は変えなくてよい。
- 記録に入れるのは **人間が言ったことだけ**。書かれていない理由・並行数・effort・model は `None` のままにする（作らない）。
  最低限要るのは、エージェントの adapter と、規則の条件・優先順で、これらを読めなければ
  その記録は作らず、読めない理由を型付きで返す（棄権）。役割（`roles`）・種類（`kinds`）・系統（`lineage`）は人間が言ったときだけ入れる（言っていなければ
  `None`。「実装は Sonnet 5.5」だけでも、「攻撃は X」だけでも記録になる）。「攻撃は X」は **役割なしの規則**（`kind=attack`）と役割未申告のエージェントの記録にする
  （役割を作らない）。役割・種類の未申告は除外されず `role_fit` / `kind_fit: undeclared` に残り、系統の未申告は独立の判定に
  関わるときだけ `LINEAGE_UNDECLARED` で除外される（J23・J24・J26）。エージェント ID と系統名は人間の呼び名のままでよい。
  「A と B は別系統（同じ系統）」は `LineageRelation` で渡す。2 つの呼び名が同じ系統かどうか分からないときは、**名札を付けない**
  （付けると違う名札は別系統になる。J25）。
  分からないことと偽であることを混ぜない。
  `None` の model / effort のエージェントが実行に選ばれたら、指揮者が起動前に止める（J20）。
- 受け皿（「それ以外は…」）は、規則 ID の約束ではなく `fallback=True` の記録で作る。規則 ID は producer が自由に付けてよい
  （比較用の値は ID に依らない）。
- 評価は「言い回しの違う説明から同じ経路づけの決定が出るか」で測る。`RoutingDecision.essence()` が、basis・理由・時刻・証言 id・
  並び順・規則 ID を除いた比較用の値である（エージェント ID は人間の言葉なのでそのまま比べる）。
- 辞書 producer（`table_from_dicts`）は、DSL でない producer からも同じ決定が出ることのテスト用の見本。

## 10. 既知の制限

- 経路づけに実測を使わない（台帳に貯めるだけ）。実測の使い方は別チケット。
- 仕事の種類は人間が指定する（`task_kind`）。自由文から推測しない。
- 1 回の `conduct` は GOAL タスクを 1 つしか走らせないので、`concurrency` の `in_use` は常に空で渡す。上限の効果は経路づけ器の
  単体でだけ示される（`in_use` を渡したとき）。複数仕事の並行実行は未接続。
- 検証役のやり直しは同じエージェント（J15）。
- 系統を人間が書かなかった実装役と、検証役との関係も言われていないと、検証役の独立が判定できず、`role=verify & independent_of=none` で外さない限り検証役は決まらない
  （`LINEAGE_UNDECLARED`。系統を推測して入れない）。名札は producer の宣言した分割として扱うので、同じ系統の 2 つの呼び名の両方に名札を付けた
  入力は約束違反で、別系統として扱われる（記録層は検出できない）。種類を書かなかったエージェントは種類による絞り込みを受けない（`kind_fit` に残る）。
- `essence()` はエージェント ID を人間の言葉として比べる。別の producer が同じエージェントに別の ID を付けた場合の同一性は
  扱わない（ID の別名は producer が揃える。揃えられなければ別のエージェントとして扱う）。`adapter` は経路づけ器が使わない
  （指揮者の起動だけが使う）のに記録層では必須のまま（`model` / `effort` のように「未申告なら起動前に `AGENT_SETTING_MISSING`」に揃える余地がある）。
- `RoutingTable` は直接作れば検査を素通りできる（試験が 1 か所で使っている）。`build_routing_table` を通すのは producer の責務。
- `[routing_precedence]` は役割をまたぐ規則同士でも書ける（意味は無いが拒否しない）。
- 証言の問い合わせの実プロセス（codex / claude）は、このチケットの本物の実行では通していない（見本の枠は証言の段に入らない）。
  試験では偽の提供者で 2 回の問い合わせを通している。
- `[routing_precedence]` を使う見本の枠は無い（試験にだけある）。
