# Round5-C 4096 step — 静的分析と最小計測提案

2026-09-30。初回patchとは別の提案。実装・採用・C48評価の完了を意味しない。
対象は独立コピーの基点HEAD `8b2732089a133300c365ce332eaf74de2a82fd29` と
初回patch SHA256 `7fb0c1a4b100b1150fb30dc80025ebf4852ab42a53e8d03b45b7aab3e67d29be`。
初回11ファイル・API・manifest・patchを変更せず、他担当所有ファイルも変更していない。
今回の作業はソース/ASTの読み取りと文書化のみ。広域suite、subprocess群、索引再構築は起動していない。

## 結論と正本

初回 `Budget.steps` はCの外側で観測した部分計数であり、正本の全工程4096step適合を証明しない。
`content_ir.py:200–204` の「既存Frame/morphology内側をC step外とする」記述は、
正本を改訂したものではない。採用時にこの除外をそのまま許可することは提案しない。
文字数上限は文字走査を制限する別カウンタであり、意味操作の計上に置換できない。

正本 `docs/PREREGISTERED_2026-09-30_round5c_content_plan.md:65` は、
読解・候補処理・探索・実現・検査の合計4096stepを定め、読解規則適用、候補展開、
束縛照合、前提/例外/状態検査、遷移、文型適用、証明node検査、節対応照合、
候補間比較を各1stepとし、内側反復も含める。同:67は予算外の二重ループを許さず、
初期化/ingestとaskを別計測し、定義が実装不能と独立レビューで判明した場合だけ
測定前に旧案と理由を残す改訂を認める。この文書は数値・合格線・正本を改訂しない。

## 現在の未計上箇所

行番号はこの独立コピーのもの。実際の到達/反復数は未測定である。

| 箇所 | 未計上の操作 / 必要な最小hook |
| --- | --- |
| `content_reader.py:100–119` | `read_all`後にcandidate数、tagger後にtoken数を加算する。内部の読解、失敗比較、文型列挙を先払いで計測できない。下位hookとCの各意味照合へのhookが必要。 |
| `frames.py:218–257` `_predicates` | tokenごとの述語候補判定と補助/複合語規則。評価した規則/束縛操作を実行前に計上。 |
| `frames.py:169–209,287–428,431–438` | 各述語についての格走査、後方/前方名詞探索、連体/cleft/時制/否定/受動/授受/視点解釈。外側token1回でまとめず、呼出された各内側の意味判定・照合を計上。 |
| `frames.py:131–140` `canonical`、`66–103` | 役割候補との比較、役割分類、他動性の読解利用。固定辞書の読込みは初期化へ分離し、ask中の意味照合は計上。 |
| `typed_edges.py:78–94` `_negated`、`97–...` `_auxiliary` | 否定/補助の規則照合。短絡して失敗・終了した検査も、実際に評価した意味操作を計上。 `_predicates`からの呼出しも含む。 |
| `realize.py:26–70` `_class/conjugate`、`73–93` `surfaces` | 活用分類/態・時制・肯否・敬体の文型規則。最大3回のclass/tagger呼出しを表面候補1回へ隠さない。 |
| `content_verify.py:57,63,78–101,144–157` | prefix/状態/活用形照合、verb抽出、時制・否定検査、出典表現のFrame再読。既存のtoken一括加算では各内側検査を示せない。 |
| `content_planner.py:198–215,234–235` | 解候補の正準化/比較、transitionごとの`next`内側照合、optionalとremainingの`any`比較。禁止条件`any`はfalseの全走査で加算せず、true時にも事後一括加算。比較前のhookへ直す必要がある。 |
| `_tagger`利用全箇所 | `frames.read_all`, `realize._class`, C reader/verifierが同じ要求で複数回呼ぶ。token数は返却量であり、native内部の候補生成/比較を示す証明ではない。 |
| `frames.py:109–128` `attested` | `count(DISTINCT src)`/LIMIT50のSQL結果だけでは候補・出典の意味比較数を示せない。独立出典の取得と検査の境界、未計測SQL内部の扱いを固定する必要がある。 |

`MaterialSource.candidates`も現在のduck-typed契約に作業量の証明を含まない。
候補返却数の制限は、索引側の候補生成・意味比較回数を証明しない。
この境界はreader所有者の契約に委ね、全ask適合を主張する際の未接続として残す。
資料source/役割/verified=Falseや独立ソブリンの根拠境界は計測のために変えない。

添付 `ROUND5C_STEP_STATIC_INVENTORY.json` は10モジュールのAST上の258反復構文と
44依存呼出し箇所を列挙し、各source hashを記録する。モジュール内の到達しない
回帰関数、文字/保存処理の反復も含むため、258を必要hook数・実行step数・coverageと
して使わない。ヘルパー経由計測、短絡評価、native/SQL内部の包含は手作業監査が必要。

## 最小hook/予算契約（実装案、未適用）

1. 1askにつき共有meterを1個作り、read/material処理/plan/realize/verifyに渡す。
   既存関数のpublic引数を壊さないため、所有者が共通の`ContextVar`スコープを提供し、
   Frame/realize/typed_edgesの意味操作直前でhookを呼ぶ方式が最小候補である。
   グローバルtaggerのmonkeypatchやPython builtin置換は使わない。
   legacyのhookなし経路を保持する場合も、C strict経路はhookなしを拒否する。
2. hookは概念上 `charge(unit, site, phase, refs)` 。unitは正本の9種の意味操作。
   実際に評価する操作ごとに実行前に1stepを予約する。失敗した束縛/候補比較や
   短絡前に評価した候補も数え、短絡後の未実行候補を数えない。
   `while`の意味条件はbody前、`any/next`はpredicate評価前にhookを置く。
   `len(tokens)`・`len(forbidden)`の事後加算や、for外側1回だけの加算は代用にしない。
   `sorted`が意味候補間比較を行う箇所は比較器をhook化するか、同じ順序意味を保つ
   可視の比較手順へ置換する。単なる文字列エンコード/複製を意味比較へ過剰計数しない。
3. site表には「どの規則/束縛/比較を1操作とするか」を所有者と独立監査者が事前固定する。
   1関数呼出しを一律1stepにせず、同じ意味操作を外側wrapperと内側hookで二重計数しない。
   本文で定めた種類をCPU命令数、Python opcode数、walltimeへ置換しない。
4. 4096個の操作は実行でき、4097個目は実行前にtyped停止する。
   診断は`executed_steps=4096`と`stopped_attempt=4097`を区別し、site/phaseを残す。
   phaseとsiteごとの実行数合計がexecutedと一致する。各phaseに4096を別配分しない。
   候補数/文字数/world/node等の既存上限は独立に維持し、予算失敗後に増やさない。
5. hook登録、対象call graph、code/dictionary/index hash、unit表versionのcoverageを固定する。
   `accounting_complete`はproducerの成功flagではなく、登録済み経路の検査結果から作る。
   追加loop/新helper/未登録backendで完全性証明を無効にし、未知のstep数を0にしない。
   trace保持量も固定し、全logを無制限にためずsite合計と打切り位置を保存する。

必要な所有境界は、既存`frames.py/typed_edges.py/realize.py`の所有者によるhook追加、
reader所有者による候補取得の作業証明、C所有範囲の前払い化、統合所有者による
askスコープ/strict gateである。当担当は既存他担当ファイルを変更していない。
実装する場合は初回patchを親に適用した後の別commit/別patchとし、初回hashと区別する。

## native/索引の不透明境界と不明時扱い

現行`_tagger()`はcached `fugashi.Tagger`を返すだけ。ローカルのfugashi1.5.2は
`__init__.py`からC拡張を公開しており、現在の呼出し契約にstep証明や途中cancelを含まない。
UniDic-lite1.0.8。Python外側hookは返却tokenを数えられるが、内部が正本の候補比較等を
含むか、それらを何回実行したかを現在のcontractから検証できない。
nativeの全CPU命令を数える要求ではない。正本の意味操作と文字走査の境界を、
backendソース/計測根拠を確認して分類する必要がある。

選択肢は、(a) native/索引側が必要な候補・規則・比較の先払い計測/停止を提供する、
または(b) 同じ凍結済み辞書と既存Frame/文法を使い、候補列挙が可視で計上可能な
非学習adapterを所有者が導入する、である。汎用文法/意味体系を新規に複製する案ではない。
上限見積りだけなら補助診断とし、実際反復数の証明と同一視しない。
SQL progress handlerもVM instruction数であり、意味操作counterへ自動置換しない。
文字上限・辞書固定・native version固定だけで完全性を認定しない。

最小のstrict gate案は `UNKNOWN_CONTENT_BUDGET_ACCOUNTING`（新規候補、未実装）。
`accounting_complete=False`, `steps_known=<観測済み下限>`, `steps_total=null`,
`uncovered_sites`, `stopped_at`を返し、CREATED/ANSWERを採用成功として公開しない。
既存の予算超過UNKNOWN、意味未解釈、制約違反とは理由を分ける。
出力草稿を表示するなら診断扱いに限り、旧QAへのfallbackや成功数への加算をしない。
全件UNKNOWNにして評価合格とすることも認めない。C採用は計測整備まで未達である。
初回v1 APIや出力を無断変更しないため、このgateは親が別revisionとして固定する必要がある。

cached辞書/役割/他動性の構築は初期化計測、ask中の検索・候補照合はask計測へ残す。
warm/cold方針を測定前に固定する。cache hitも当該lookup/照合操作を計上し、
過去に実行したnative処理を現在の実行回数へ再計上せず、skipを隠れたゼロ扱いにも使わない。
ソブリンの計算量集約は資源管理用であり、独立score/真偽票の合算を許可しない。

## 次の小検証（今回は未起動）

hook実装後、単一process・worker0・subprocess0で実施する最小対象:

- 合成tokenで格/否定/時制の内側走査と失敗照合を通し、siteと期待stepを照合する。
  これはhook診断であり、raw reader理解のR/E成績へ入れない。
- 4096成功、4097操作直前停止、失敗した`any`の全比較、短絡後未評価の非計数を確認する。
- Frame候補が複数のときの前後走査、複数活用候補、verifyの再読を同じ共有budgetに足す。
- candidate順序を変えても意味/許可を保ち、実際に比較した数を出す。
  既存の曖昧性/状態/否定/world/span回帰を併走し、計測追加で意味契約を弱めない。
- 未登録tagger/MaterialSource、新loop/codehash、欠けたcoverage証明をstrict UNKNOWNにする。
  計測済み制御ケースが成功することも確認し、全拒否をoracleにしない。
- site/phase合計、初期化とask分離、入力budget停止後の非実行を検査する。

予定コマンドは別revisionに新規`tests/test_content_budget_accounting.py`を置いた後、
`python3.11 -m pytest -q tests/test_content_budget_accounting.py`。
process1、subprocess0、目標数十case。現在はfixture/実装未作成のため実測時間なし。
既存content87caseの3.49秒は参考値で、native計測版の所要時間保証ではない。
広域guard/C48/索引再構築は親の実行枠調整まで起動しない。

この計測契約は意味表現→計画→自由文/コード等の将来共有基盤に載せられるが、
汎用意味理解・汎用自由文生成・閉包外生成、非学習の意味圧縮/立体十字重み配置を
達成した証拠にはならない。ledgerの可逆保存、構造view、計測済み意味操作の範囲を
それぞれ記録し、出典・条件・否定・訂正・不確実性の検査を引き続き独立に保つ。
