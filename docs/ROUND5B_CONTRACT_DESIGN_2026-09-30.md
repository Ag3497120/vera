# Round5-B 候補設計 — 要求契約からの型付き依存合成と独立検査

日付: 2026-09-30。設計レビュー用。**未実装・未測定・未検証の候補契約**。

## 境界と結論

Round5-A は事前登録 commit `bdb454f` 後に実装中と親から連絡を受けている。本書は A の schema や成功を前提にせず、B 単独でも読解・合成・backend・検査の未達を区別する。実装担当と同じ runtime ファイルは編集しない。作業は既存 runtime の静的読解とこの新規文書の作成のみ。プログラムの試験実行、評価、測定、build、commit は行っていない。sealed/heldout の本文・参照・個別出力を一切読んでいない。

既存資産の探索には先の Round5 設計監査で読んだ `CLAUDE.md` と実行済み capability-index 検索（`question`/`compose`/`frame`/`plan`/`constraint`/`proof`）を用い、今回は runtime を読んで API を再確認した。新しい index search や runtime 実行はしていない。A の実装中コードへ依存する具体的フィールド名は確定しない。

**B の核心は、`Specification` を大きくすることではなく、(1) 原文から独立に保全した要求台帳、(2) 言語別インターフェースも含む契約、(3) 中間型と変数束縛を持つ依存 DAG、(4) 生成物から戻って要求を検査する経路を、別の責務として成立させること。** 既存 backend と実行器は条件付きで再利用できる。現在の `read_spec → backend → 同じ spec の reference` のまま span/trace を追加してもこの差は生まれない。

Python、JavaScript、SQL、POSIX shell の対象は維持する。現在の SQL 実行器は SQLite、shell は改行区切り数値入力という実装境界がある。その境界を明示しつつ、他の SQL dialect、入出力形、演算、言語への拡張を型付き lowering の追加として扱う。特定言語だけに製品目標を永久縮小しない。Vera runtime の読解・合成・検査に LLM や学習済み生成器を導入しない。

## 現行コードで確認した再利用資産と限界

以下はソース上で確認した事実。具体的な入力で失敗したという測定報告ではない。現在の実装作業で行番号や内容が変わり得るため、B 着手時に再確認する。

| 部品 | 再利用できる資産 | 現在の契約で不足するもの |
| --- | --- | --- |
| `code_spec.py:16–40` | `Operation(kind, field, comparator, value, descending)`、`Specification` の言語/shape/名前/fields/empty/unchanged/ties/stable/table | 入力パラメータの名前・個数・呼出方式、各fieldの型、複数入力の別schema、出力schema、演算対象の変数ID、中間型、作用域、原文span、要求別の充足証拠。 |
| `code_spec.py:46–61,76–117` | literal読解、明示された識別子/言語/関数名/空時動作などの候補 | 名前を引用しただけでfieldへ入れ得る。input/output/parameter/constantの識別子束縛がない。空入力と処理途中で空になる場合の作用域は別に表されない。 |
| `code_spec.py:64–73,181–226` | 認識済み演算候補 | fieldを60文字内の近さで結ぶ。演算は文字位置順、group/aggregateは末尾へ移す。これは型付き依存解決ではない。ratioはfieldsの先頭二つを使う。 |
| `code_spec.py:227–248` | 不足/unsupportedの拒否経路 | issue検出に触れなかった未読要求は、残存spanとして保持されない。multiple aggregates/aggregate後の操作等を一括拒否し、未知処理を表現する契約がない。 |
| `code_compose.py:20–21,24–104` | 10操作のID、現在のreference semantics | 各操作に入力型・出力型・pre/post-condition・効果・対応backendの宣言がない。`PARTS`のIDは実装出所であり原文要件の充足証拠ではない。 |
| `code_compose.py:146–213,220–286` | Python/JSの演算出力、stable sort、group、join等 | 関数の引数を `data` と場合によって `other` に固定する。要求されたAPIに従うインターフェース構成ではない。中間値名も `values/groups` を使う一列の処理である。 |
| `code_compose.py:301–357` | SQL literal/identifier quoting、WHERE/GROUP BY/ORDER BY/aggregate等 | `selection/grouping/ordering` は単一変数で、後続操作が前を上書きし得る。任意の演算DAGを意味保存する SQL lowering ではない。joinの出力列/衝突方針も契約化されない。 |
| `code_compose.py:360–393` | POSIX pipelineのfilter/map/sort/dedupe/diff/一部集計 | 数値1列/stdinに限定された実装。argv、ファイル名、出力format、exit status等の要求契約はない。 |
| `code_compose.py:107–139,406–494` | syntax check、境界候補、isolated Python、Node/SQLite/sh実行、timeout | fixtures/referenceは同じspecを使用。numeric fieldへ同じ値を入れる構築はfieldの取り違いを区別しにくい。runnerも生成側と同じ固定呼出をするため要求APIを独立に確認しない。 |
| `code_compose.py:396–403,423–432` | 結果比較/SQL結果decode | 数値に一律近似比較。SQL結果の解釈をexpectedのPython型へ合わせる。戻り型、列名、order、精度の契約を生成側から独立させる必要がある。 |
| `code_compose.py:504–539` | 一つのanswer入口、失敗時typed refusal、spec/parts/checksのtrace | 原文要求の完全性を検査する独立段はない。成功textの「仕様」が、ユーザー全要件かparsed specだけかを区別できる返却契約が必要。 |
| `round3.py:118–123` | 公開routerからcode answerへ進む既存接続 | Bもこの公開経路を通す。独立helperだけを評価して公開経路は旧経路という配線を作らない。 |

### backend間で保存すべき意味は操作名だけでは足りない

| 操作/観点 | 静的に確認できる現在の実装差 | Bで明示する契約 |
| --- | --- | --- |
| dictionary入力 | reference/Python/JSはvaluesへ投影する（44–45,148–149,222–223）。 | mapのkeyを保つのか、valuesだけなのか。勝手にschemaを弱めない。 |
| group key | reference/Pythonは`str(...)`、JSは`String(...)`（76–79,180–183,255–258）。 | key型、key同一性、出力のmap/rows形式。異型keyを文字列化してよいか。 |
| record dedupe | Python/referenceは構造比較、JSはJSON.stringify key（68–75,176–179,251–254）。 | 比較対象field、等値規則、最初/最後の保持、順序。 |
| join | Python/JSは右recordで重なるkeyを上書き、SQLの無指定projectionはbase側（80–86,184–189,259–265,354–355）。 | left/rightの別schema、key対応、join種別、列名衝突、projection、行多重性。 |
| text length | Pythonは`len`、JSは`.length`（57–60,166–168,237–239）。 | byte/code point/UTF-16 unit/graphemeのどれか。異なる意味を同じmap labelで隠さない。 |
| arithmetic/precision | referenceのsumは`math.fsum`、Pythonは`sum`、JSはreduce（97–100,200–203,275–278）。 | 数値domain、精度、許容誤差、overflow、丸め。整数と浮動小数を一律closeにしない。 |
| null/zero/empty | null比較、分母0、入力空、aggregate対象空は別箇所で処理（44–47,87–102,150–151,191–208,266–283）。 | `input_empty`/`filtered_empty`/`group_empty`/`denominator_zero`のtriggerとscope。値Noneが「明示null」か「未指定」かも区別。 |
| SQL順序 | sortは`base`列を指定、stable時rowidを足す（333–336）。 | row順序の有無とtieの処理、要求dialect/schemaでrowidが有効か、group後sortの対象。 |

これらは全backendを捨てる理由ではなく、**意味が保存される既存部分を判定して再利用する条件**である。互換でない計画をflat `Specification`に潰して検査を通すことはしない。

## 既存の意味・手続き部品を再発明しない

- `rewrite_core.py:50–64,108–166` の項/変数一致/代入/規則traceは、演算項と型の束縛を扱う土台の候補。現行matchは構造の一致であり、型推論・subtyping・捕獲回避・source spanの検査まで実装済みとは扱わない。登録順のrewrite戦略を曖昧な要求の同点崩しへ使わない。
- `rewrite_kernel` の規則データ、`RuleStore`/CrossStore接続は既存。Bのためだけに別の汎用書換えエンジンを作らない。型付きoperator lawを載せられるかをadapterで検討し、算術向けsurface parserを自然文readerと呼ばない。
- `procedure.py:24–70` のCondition/Step/Effect/Procedure、`procedure_exec`の予算/unsupported/precondition/effect照合は既存。これらのpayloadはgeneric dictであり、Bの型付きcode contractとそのまま同一ではない。共通概念を引き継ぎ、arithmetic four-op executorを任意コードの実行器として流用しない。
- `code_ingest.py:1–15` はPython ASTをcall/arg/file/classの十字へ置く既存資産。interfaceや依存の観測に使えるが、raw要求の正しさ、任意プログラムの効果、contract fulfillmentを証明しない。
- `module_verify.py:1–22` はdomain moduleの別契約（`ask(store, query)`）の検査器。Bの要求インターフェース検査と同じではない。LLM draft module用の成長経路をVera runtimeの合成経路へ導入しない。
- `frames`/`typed_edges`/`stage_split`とAの節/span/scope型は、raw requirement readerに再利用できる候補。Aにcode contractの成熟度や任意コード能力を暗黙に要求しない。

六腕/面/辺は、対象言語の演算・構文部品・規則の候補供給に残す。型判定と証明は後段で行う。異なる言語や語彙粒度を一つの票へ混ぜず、データの異なる証人と表現供給を区別する。候補配置や登録順を変えて意味が変わる場合は失格とする。

## 候補契約: 五つのimmutable成果物

以下はAへ要求するschemaではなく、Bの責務を固定するための候補。実装時の型名はAの確定版と整合させる。同じ情報を二重保持する場合はlossless adapterを定義する。

| 成果物 | 最低限保持するもの | 禁止する短絡 |
| --- | --- | --- |
| `RequestSource` | raw text、content hash、version、原文座標方式、正規化textと原文への対応表、code/quote/説明/要求の領域 | 正規化後のoffsetを原文offsetとして使う。原文全文を出典にして全要求を消化した扱いにする。 |
| `RequirementLedger` | requirement ID、discontiguous spans、clause/scope ID、kind、対象symbol、比較/順序/否定/数量/境界の式、origin、解析状態、未解釈region | 後で生成したcontract/planから逆算して「読み取った要求」を作る。未読句を任意の説明句へ落とす。 |
| `ProgramContract` | source/ledger hash、language/dialect/runtime profile、interface、入力schema/型、返却schema/型、pre/post/effect/order/error条件、各constraint→requirement IDs、未解決候補 | `operations`だけを契約とする。要求されない前提を加えて入力domainを勝手に狭める。 |
| `TypedProgramPlan` | node ID、operator/version、input node/symbol IDs、output型、field path、lexical scope、preconditions/known refinements/effects、requirement解放候補、lowering選択 | text上の近さだけでfield束縛。group/aggregate等の定位置化。型が合うだけで要求を満たしたとする。 |
| `VerificationCertificate` | generated artifact hash、source/ledger/contract/plan hash、独立検査別の結果、requirementごとのwitness/failure、適用law、test scope、backend/version、未検証領域 | producerの`passed=True`を信用。実行check成功を自然言語要求の完全な理解へ拡張。 |

`origin` は少なくとも `explicit_request`、`request_example`、`derived_from_requirements`、`documented_convention`、`gold_contract` を区別する。導出要件は元requirementと導出規則を必要とする。システムの便宜で付けた名前やdefaultを、原文で要求された事実として記録しない。

### インターフェースは言語別tagged contractにする

- Python: function名、parameterの順序/名前/種類（positional/keyword/default等）、返却値の型/構造、例外、入力mutation。名称変更で既存callerが動かなくなるなら、結果の値だけが正しくても不合格。
- JavaScript: function名、引数順、sync/async、必要なexport/call形式、返却構造、missing/undefined/nullの区別、mutation。Pythonの名前付き引数概念を無理に共有しない。
- SQL: dialect、source tableとそれぞれのcolumn schema、join対応、output列名/順序/型、row multiplicity、ORDER BYの要求、NULL semantics。関数名contractに偽装しない。
- POSIX shell: argv/環境/stdin/fileのどこが入力か、区切り/encoding、stdout/stderr、exit status、副作用条件。現在のnumeric pipelineを使えるときも入力protocolを明記する。

既定値が許されるのは、要求がその点を制約しない場合に限る。利用者が明示したinterfaceを別名wrapperや検査runner側の引数変換で救済しない。contractが未指定と明示値を区別できることが前提である。

### operator registryの型契約

現在の10操作を出発点にし、各operatorへ入力型、出力型、precondition、効果、順序・多重性、解放可能なrequirement種別、loweringの対応profileを付ける。最低限の例は以下。

| operator契約の例 | 型/依存で決める点 |
| --- | --- |
| `Filter(Seq[T], Predicate[T]) → Seq[T]` | predicateのbound symbolがT、フィルタ対象/条件作用域、order/multiplicity保存。AND/OR/NOTはpredicate式として残す。 |
| `Map(Seq[T], Expr[T→U]) → Seq[U]` | row更新かprojectionかを分ける。出力Uで後段fieldの存在を検査する。 |
| `Group(Seq[Record], KeyExpr→K) → Groups[K, Record]` | key型/同一性、groupの内外scope。groupをscalar扱いしない。 |
| `Aggregate(Groups[K,T], Agg[T→V]) → Map[K,V]` | 集計対象/空時条件/数値型。全体集計と各group内集計を別型で扱う。 |
| `Join(Seq[L], Seq[R], Key[L]≈Key[R], Projection) → Seq[U]` | 左右schema、null/重複/列衝突、指定された出力U。片側のfield名を両側へ強制しない。 |
| `Sort(Seq[T], KeyExpr, Direction, TiePolicy) → Seq[T]` | 前段の出力型、安定性、多段key。group後の値を元rowのfieldと混同しない。 |
| `Ratio(Seq[T], Numerator[T], Denominator[T], ZeroPolicy) → Seq[V]` | 分子/分母を別symbolへ束縛。0とnullの動作、結果精度を保持する。 |

`NotExists/Dedupe/Diff`も同じ方式で契約化する。表現可能な演算が増えても、自然文からその意味を取り出せたことにはならない。追加operatorの一般的契約と、特定話題への文分岐は区別する。

## raw requirement → contract: span coverageの実装可能な意味

span coverageは「文字を何%使ったか」ではなく、**要求解釈の取り落としを局所化する会計と検査**と定義する。任意の自然文における意味理解の完全性を自動証明するものではない。

1. 原文は不変。座標はUnicode code pointの半開区間など一方式へ固定し、byte offsetとの混同を避ける。全角正規化/空白整理を行う場合は元区間へのmapを保存する。非連続な根拠区間も表現する。
2. code/quote/列挙/条件句/主節などの領域と節を先に記録する。code片中のsyntaxや例示をそのまま外部命令にしない。禁止・例外・限定・順序・空時条件をscope nodeへ結ぶ。
3. ledgerはcontract/synthesizerが候補を作る前に凍結する。各region/token群は「要件候補」「明示例」「構文接続」「説明/背景」「不明」のいずれかへ、分類規則とともに関連付ける。説明/背景の既定値を使って未知句を捨てない。requirementは複数span、同じspanは複数requirementへ対応してよい。
4. 識別子はinput/parameter/output/field/constant/type等のsymbol tableへ宣言し、各出現をscope内で束縛する。距離は候補探索の順序にだけ使えて、束縛を正当化しない。`だけ/以外/各/先に/その後/空なら`等もoperatorの語だけに吸収せず、どの対象を制約するかをledgerへ残す。
5. 原文からの別経路のloss sentinelが、署名・識別子・literal・条件/否定/順序/数量等の未説明出現を照合する。全てを独立に理解する第二の万能parserは仮定しない。sentinelの判定も `checked/unknown` を返し、検出しなかったことを完全性の証明にしない。
6. `span linked`、`requirement interpreted`、`contract constraint bound`、`plan obligation discharged`、`artifact verified` を別状態にする。「合計」の文字をsum nodeへ貼っただけでは、対象fieldやgroup scopeの要求は充足しない。必要条件の不明/競合が残るなら成功にしない。
7. 返却traceはrequest→ledger→contract→plan→artifactの対応を持つ。比率を表示する場合も、文字coverage、独立gold要件coverage、証明された要件coverageを別々にし、単一の理解率へまとめない。

この仕組みは未知要件を必ず発見できるという主張ではない。readerとsentinelが同じ自然言語構造を見落とす共通誤りは残る。それを測る境界が、独立に作成されたgold ledger/contractである。意味を全部「その他」に分類してcoverage100%とする実装、原文全文spanを全nodeへ貼る実装、template語に反応した箇所だけを分母にする実装は無効。

## typed dependency synthesis

合成はoutput contractから型に合うoperator候補を探し、入力の既知symbol/refinementと要求依存で枝刈りする。topological orderは依存から決める。原文語順、登録順、operator固定順へ戻さない。特に `Map→Filter` と `Filter→Map`、`Filter→Group→Aggregate` と集計後Filter、projection前後のsortなど、非可換な構成を別項として保持する。

各候補には、どのrequirementをどのlawで解放したか、どのpreconditionが未証明かを残す。型が合うだけでは同じ型のfield取り違いを検出できないため、field/symbol identityと原文roleの束縛が必須。書換えlawは意味が確認できる範囲に限定し、`rewrite_core.match/substitute`等を利用する。cap/budgetを超えたときは検査未完了であり、最初の動く候補を正解にしない。

候補の探索順は再現性と速度のために固定できるが、正しさの証拠ではない。異なる意味解釈が同点なら棄権する。コードの変数名や文法上の表記だけが違い、同じ契約の観測可能な意味をlawで保つ候補は一つの同値類として扱える。有限個のtestで同じ値になっただけでは同値と断定しない。

既存backendをそのまま使う経路は、`TypedProgramPlan → checked linear fragment → legacy Specification → backend` のlossless条件を証明できる場合だけ。任意DAG、分岐、複数集計、group後処理、左右異なるschema等は、対象backendに必要な局所loweringを足すか明示拒否する。SQLなら演算順序をsubquery/CTEに残すなど、実装差分が必要な場合がある。直線化時に捨てた要求を実行checkで取り戻そうとしない。

## independent requirement verifier: 独立性の範囲

完全独立な理解器を追加すれば万能になるとは考えない。**共有してよい低水準形式と、共有してはいけない正答判断を分ける。** immutable source/型/座標/シリアライズは共有できる。生成したoperationsをoracleの正解へそのまま変換する経路、同じfield選択関数、同じ順序推定、同じdefaultの補完で生成側と検査側を閉じない。

検査器は少なくとも三層に分ける。

1. **要求→契約の照合:** 凍結ledgerと原文から、各contract constraintの対象・scope・境界を照合する。独立goldがある開発時にはledgerの漏れも採点する。runtimeでは未理解/曖昧性を返し、自然文の真意を完全に証明したという出力にしない。
2. **契約→typed plan/生成artifactの検査:** 小さなkernelがsymbol binding、型、pre/post/effect、requirement IDs、operator lawの証跡を検査する。さらに最終artifactのAST/公開interfaceを読み、要求されたcallで呼べるかを確認する。planが正しくてもloweringが別物なら拒否する。
3. **独立実行witness:** 生成側から独立に保った期待値/性質、要求interfaceから作ったrunner、異なるfieldを区別する入力で最終artifactを実行する。成功は試したdomain/性質に限る。任意入力で正しいという証明へ拡張しない。

検査を通すartifactは返却するartifactとhash一致させる。検査専用wrapperで関数名・引数・返却形を直してから実行することはしない。SQL結果decodeをexpectedの型から決めず、要求output schemaから決める。stdout等の余分な出力も要求protocolとの一致として扱う。

### oracleの共有誤りを減らす具体策

| 誤りが共有される経路 | 具体策 | 限界/採点 |
| --- | --- | --- |
| read_specが捨てた要求をreferenceも知らない | gold ledger/contractを読解器・合成器と別担当がrawから作り凍結。runtime ledgerもsynthesisより前に作る。 | runtimeの未知の自然文要件はなお見落とせる。goldで欠落率を別採点。 |
| runnerが生成側と同じ名前/引数へ合わせる | raw署名/独立contractからexpected callerを構成。PythonはASTで署名、JSは適切な構文readerとexport/call、SQLはschema/列、shellは入出力protocolを確認。 | JSの署名を単純regexだけで万能に扱わない。対応構文外はunknown。 |
| numeric fieldが同じ値でfield交換を見逃す | 入力各fieldに独立な値を割当て、片方だけ変える対・左右schema非対称・重複key・順序差を作る。 | 生成用samplesを増やすだけでなく、独立required field bindingを参照する。 |
| 同じ操作順をreferenceとbackendが使う | gold contractのdenotational meaningを基に、非可換なoperator対を区別するwitnessを独立作成。 | 普遍的正しさではなく、当該order区別ができるという証拠。 |
| 空/欠損/defaultを両者が同じに推定する | 入力空、filter後空、groupごとの空、zero/null/missingを別triggerで要求へ結ぶ。test期待値をcontractとは別途レビューする。 | 未指定の振舞いをユーザー要求と偽装しない。 |
| 同じ型/値だが要求output shapeを落とす | 名前、列順、row順、多重性、key保持、scalar/list/map、追加fieldをschemaで検査。数値のみ比較しない。 | schemaの読み違いはgold照合でしか判明しない場合がある。 |
| 生成物とreferenceが同じbackend semanticsを誤解する | 共通subsetに限るdifferential check、operatorごとの意味law、独立入力/期待値、精度profileを併用。 | Python/JS/SQL一致は多数決による正しさではない。同じ誤りはあり得る。 |
| 検査器がproducerの証明ラベルを信用する | 要求ID削除、field/比較境界/order/interface/output形を一つだけ変えるmutationを事前登録し、検査器が拒否することを確認。 | mutation成績を自然文正答率と混同しない。 |
| 同じ実装者が問題/契約/検査まで決める | raw資料・gold ledger・gold contract・期待値・採点基準の出所と担当を区別し、実装者の自己生成fixturesは別欄へ置く。 | 独立担当の人間的誤りもreviewする。無謬oracleとは呼ばない。 |

既存 `reference/spec samples` はbackend局所回帰として残す。自然文理解のoracleにはしない。metamorphic検査（識別子renaming、独立field変化、入力順変更、等価表現等）も、その変換が契約を保存する/変えることを独立に確認した場合だけ利用する。変換lawを誤ればoracleも誤る。

## Aとの接続、自然文とgold contractの境界

Aとの共通項は source span、scope、typed variable、requirement/proofの由来、typed refusalの受渡し。BのFunction/SQL/Shell interface、container type、effect、program loweringはB側の責務とする。A schemaは実装完了後にadapterを確定し、B設計から先回りして固定しない。

公開 `one.Vera` のcode routeから以下を同じ入口で追跡できるようにする候補を示す。API名は仮称で、ここで追加実装していない。

- `read_requirements(raw) → Ledger + ReadingAlternatives + UnknownRegions`
- `bind_contract(ledger, candidate_readings) → Contract | typed refusal`
- `synthesize(contract) → TypedPlanCandidates | typed refusal`
- `lower(plan, backend_profile) → Artifact + LoweringCertificate`
- `verify_requirements(raw, frozen_ledger, contract, plan, artifact) → VerificationCertificate`

gold contract入力は開発用に別のentryを持ち、`origin=gold_contract`を保持する。これを自然文の`read_requirements`経路へ通したことにしない。公開仕様へgold contractを付け足して正解する測定と、raw textだけで正解する測定は分ける。

| 独立診断段 | 入力 | 検査するもの | 失敗が示す境界 |
| --- | --- | --- | --- |
| R: reader | raw + 独立gold ledger/contract | 要件漏れ/誤解釈/束縛/作用域/曖昧性 | AまたはB code-specific読解。backendの責任にしない。 |
| S: synthesis | 独立gold contract | typed依存構成、requirements充足、budget | 自然文を除いた合成能力。A成功は不要。 |
| L: lowering | gold typed plan + backend profile | 実際の公開interface/意味/出力shape | 既存backendの互換条件/新lowering。 |
| V: verifier | 独立valid/invalid契約・証跡・生成物 | 欠落/改変を正しく採否するか | 検査自体の能力。誤答を実行済みとして通さないか。 |
| E: public end-to-end | rawだけ、固定runtime/corpus/profile | `one.Vera`の最終codeが要求を満たすか | R/S/L/Vとrouting/連携を含む実用結果。 |

Aの出力が不足/拒否でもS/L/Vはgold contractで検証できる。Eが失敗してRが失敗なら、Sの成功を一般的コード生成成功と呼ばない。goldでも失敗するSを、自然文読解だけ直せば解消すると見込まない。新封印評価にgold契約/正解callerをruntime入力として渡さない。

## 実装担当に渡す単位と停止点

新規ファイル名は候補であり、作成前に索引とA成果物を再確認する。

| 単位 | 予定対象 | 核心/レビュー証拠 |
| --- | --- | --- |
| B0 型/契約を固定 | Aとのadapter、仮称`code_contract.py` | source/ledger/contractとbackend profile、interface tagged union、unknownと明示nullの区別。既存Specificationのversion変換条件を文書化。 |
| B1 raw要求の保全 | `code_spec.py`を候補readerとして利用、仮称requirement adapter | ledgerをsynthesis前に固定。scope/span/識別子束縛とunknown regionが返る。現regexの追加だけにしない。 |
| B2 typed依存合成 | 仮称`code_plan.py`、既存rewrite/Procedureのadapter | 既存10操作を型契約化し、gold contractから未見order/field/interfaceの依存構成。最初は型付き直線fragmentでも、raw文字順連結と異なることを示す。 |
| B3 backend接続 | `code_compose.py`の既存emit/verifyをadapter化 | Python/JS/SQLite/POSIXのcapability table、lossless legacy lowering条件、要求interfaceと返却schema。unsupportedをlanguage profile付きで返す。 |
| B4独立検査 | 仮称`code_requirements_verify.py`、既存runnerの責務分離 | frozen要求からcaller/checks、artifactからinterface/効果、独立期待値/mutation採否。生成側のspecをそのままoracleへ流さない。 |
| B5公開入口 | `round3.py`/`one.py`との接続 | successful legacy codeが新gateを迂回しない。raw/contract/plan/artifact/certificateのhashとfailure stageが公開traceに残る。 |

最初の方式差の検証ではprimitive数を固定し、field/値/インターフェース/演算順の未見組合せで、gold contractからの合成とrawからの読解を別々に比べる。その後に新しい演算/型を増やす。四言語の最低限の縦断経路を保ち、特定言語だけの成功をB全体の成功としない。追加言語/既存言語の拡張は、backend profileと演算契約の差分として追跡する。

拒否の主因は少なくとも `REQUIREMENT_UNREAD`、`CONTRACT_AMBIGUOUS/CONFLICT`、`TYPE_OR_BINDING_FAILURE`、`SYNTHESIS_UNSUPPORTED/BUDGET`、`BACKEND_UNSUPPORTED`、`RUNTIME_UNAVAILABLE`、`VERIFICATION_FAILED` へ分ける。名前は既存typed refusal命名と整合させる。全失敗を「入力の形を明示してください」へまとめない。

コード説明/修正は既存 `explain_or_fix` の別経路を保持するが、構文名の列挙を生成タスクの成功へ数えない。Bで扱う際には要求された説明/修正のscopeと変更前後contractを別に固定する。今回のB設計は任意既存コードの意味解析や修復の完成を主張しない。

## 開発検証と新封印

この文書は検証方針であり、測定前の正式な事前登録に置き換わらない。各段の素材、採点、budget、言語profile、合否条件を本実装/測定前に固定する。

開発ではR/S/L/V/Eを分離し、正解・誤答・棄権、interface一致、要求全件充足、漏れた要求数、unsupportedとbudget、実行したcheckのscope、生成latencyを別に記録する。span coverage/実行成功/コードfenceの存在を正答率へ置き換えない。見た言い回しを少し変えるだけでなく、構造の組合せとcontract familyを丸ごと留め置く。データサイズやruntime環境の違いは方式差と混ぜない。

独立gold/期待値はruntime生成物と別ファイル/別出所で管理し、実装者のself fixturesと区別する。今後、現行のsample/referenceを通過して独立oracleを落とす率も記録し、自己検査の限界を隠さない。比較基準は凍結済みruntimeを用い、停止された同じ封印問題を微調整して繰り返し試さない。

新封印は設計・runtime・corpus/index・実行profile・公開entry・採点を固定後、独立担当者が保持する問題で一度行う。Bだけの単体試験が通っても、Round5全体では一般QA/コード/文書/6能力の4群の目標を維持する。問題本文・参照・個別出力を実装者が見ない境界を継続する。

## 誤って簡略化しやすい点

1. `Specification`へspan欄を増やしただけでtyped contractと呼ばない。要求台帳を生成planの後から作らない。
2. 契約の「入力はrecord list」を型検査の全てにしない。同じ数値型のfieldの取り違いはsymbolとscopeで検査する。
3. 原文の順番をprogram orderにしない。group/aggregateを必ず最後へ移さない。
4. 関数名だけをinterfaceとしない。検査runnerが生成物のAPIへ合わせてはいけない。
5. operatorの意味をPython参照値だけで決めない。SQL/JS/shellのprofileと要求protocolを保持する。
6. 未指定と明示None/0、入力空と途中空、比較対象の元値と変換後値を同じflagへ潰さない。
7. samplesを増やすだけでoracle独立性ができたとしない。expectedが同じ誤読spec由来なら共通誤りが残る。
8. 全数字列に同じ数を入れない。結果の値だけでなく列/行/キー/順序/多重性と副作用を検査する。
9. type-correct、syntax-valid、execution-checked、requirement-completeを同じ成功statusにしない。
10. token coverage100%、traceへの部品登場、`PARTS`のcitationを意味理解や正しさの証拠へ昇格しない。
11. テストで同じ値だった候補を意味同値とみなし、同点棄権を回避しない。探索順を証人の票へ変えない。
12. A成功をB読解成功とみなさない。gold contract入力のS/L成功をraw自然文のE成功へ混ぜない。
13. 既存部品を捨て新しい名前で再実装しない。ただし型/意味保存条件を確かめず既存backendへ丸投げもしない。
14. 初期subsetを永久的製品範囲へ変えない。未対応言語/演算の拒否は現実装の状態であり、汎用コード生成を諦める設計判断ではない。

## レビューの結論と未検証仮説

確認済みの結論は、現行実装が原文要求の完全性・要求API・中間束縛を十分に契約化しておらず、生成と検査が同一specを共有すること。backendの操作や実行器は資産として利用できるが、すべての操作chainを意味保存するとは確認できない。

提案仮説は、ledger/contract/typed DAG/独立検査を分ければ、要求の欠落・依存の誤り・loweringの誤りを診断し、未見構成を扱える範囲が広がること。正答率や速度が改善するとは未測定であり予告しない。一般自然文の完全読解、任意コードの全入力正当性、複雑な副作用や外部APIの仕様、全backendの同等能力は未解決である。

最初に反証すべき点は、**primitiveを増やさずgold contractから正しい依存構成を作れるか、raw要求からそのcontractを欠落なく読み取れるか、故意に壊したinterface/束縛/条件を独立検査が拒否できるか**の三つ。ここを別々に通せず、regexや語彙の追加だけで自己検査成功が増える場合は、Bの方式仮説を支持したとは扱わない。
