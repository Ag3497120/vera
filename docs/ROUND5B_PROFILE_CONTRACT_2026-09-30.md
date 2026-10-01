# Round5-B 初回profile契約案 — 独立素材生成へ渡す意味仕様

> 後続ユーザー指示による設定変更: 実装は gpt-6.1-sol / max / fast有効（priority）。本文の旧fastなし記述より [Fast設定の改訂](AMENDMENT_2026-09-30_fast_mode.md) を優先する。意味契約・予算・採点基準は変更しない。

2026-09-30。`PREREGISTERED_2026-09-30_round5b_contract_plan.md`の付属契約。**19:10 JSTの親レビューでv1として採用した。以下のMは「実装すべき契約」を示し、実装済み・検証済みを意味しない。** 初稿作成時にはB実装、fixture生成、評価実行を開始していない。sealed/heldout本文・参照・個別出力は読んでいない。runtime/test変更、commitは初稿担当が行っていない。採用の履歴と実際の開始条件は事前登録§14を参照する。

目的は、実装者の内部schemaやAの未検証schemaを素材作者へ読ませず、四profileのraw要件・独立gold契約・gold plan・oracleを作れる粒度で意味を固定すること。初回範囲外の能力を削除/永久拒否する仕様ではない。10演算familyと既存subkindを登録に残し、初回対応、保留、将来拡張を区別する。

## 1. 既存primitive/subkindの静的確認

次表は`code_spec.py`と`code_compose.py`を読んで確認した分岐の一覧。分岐の存在は、任意のchain、要求API、空/null、全入力での意味保存を保証しない。後述のM表と混同しない。

| 既存family | subkind/指定 | reference/Python/JSの分岐 | SQLの分岐 | POSIX shellの分岐 |
| --- | --- | --- | --- | --- |
| filter | `== != < <= > >= even odd`。正/負は`>0/<0`、除外は`!=`、null除外は`!=None`へ読む。 | あり。null/比較の意味差に注意。 | field必須。通常比較、NULL、偶奇の分岐あり。 | 数値比較/偶奇。文字列と通常のnull比較は拒否。 |
| map | `square abs multiply upper lower strip length pluck` | 全8subkindの分岐あり。recordでは通常field更新、pluckは値への投影。 | pluckのみ。 | square/abs/multiplyのみ。 |
| aggregate | `sum mean count min max`、`all_ties` | 全5subkind、min/maxの全同順位record返却分岐あり。 | SUM/AVG/COUNT/MIN/MAX。groupなしmin/maxの全同順位分岐あり。 | sum/mean/countのみ。 |
| group | 1field | keyを文字列化し、group後のaggregateまたはgroupを返す分岐。 | GROUP BYの単一指定。 | なし。 |
| sort | 1key、ascending/descending、stable | Python stable sort、JS indexによるtie順保持。 | ORDER BY、stable指定時にrowidを足す分岐。 | `sort -n/-nr`。 |
| diff | 隣接するcurrent−previous | あり。 | なし。 | awkの前行との差。 |
| dedupe | scalar全値または1field、先頭保持 | Python構造比較、JS JSON.stringifyを使う分岐。 | DISTINCT指定。record先頭保持とは同じでない。 | 元行文字列をkeyとしたawk。 |
| join | inner、同名の1key | 左×右の一致、右recordで同名keyを上書き。 | 同名keyのJOIN。通常projectionはbase側。 | なし。 |
| not_exists | left anti、同名の1key | 右に一致しない左record。 | NOT EXISTS。 | なし。 |
| ratio | 分子field/分母field、zero_division | 除算とzero fallback。reference/Pythonはtruthiness、JSは`===0`。 | CASE WHEN denominator=0、REAL除算。 | なし。 |

参照位置は`code_spec.py:16–40,118–248`、`code_compose.py:20–21,24–104,146–213,220–286,301–393`。read_specはgroup/aggregateを末尾へ移し、複数aggregateとaggregate後の操作を拒否する。scalar parameterを一般symbolとして束縛するinterface、AND/OR/NOTのpredicate tree、中間型、別名join key、任意projectionの一般契約は現Specificationにない。これらを「既存対応」と記載して素材の正例を正当化しない。

## 2. profileの状態と実環境

以下では **M＝初回の実装・正例契約、C＝明記した条件内だけM、X＝初回はtyped unsupportedを返す範囲** とする。Xは削除を許可せず、既存の対応がある場合は回帰/拡張台帳に残す。条件を守ったM正例に対する不成功は未達であり、後からXへ付け替えない。

| profile ID | 初回runnerの採用候補 |
| --- | --- |
| `python_pure_v1` | `/opt/homebrew/bin/python3.11` 3.11.15。PATH上python3 3.9.6を使わない。 |
| `node_commonjs_sync_v1` | `/opt/homebrew/bin/node` v26.0.0。 |
| `sqlite_select_v1` | Python 3.11.15の標準sqlite3、SQLite 3.53.2。CLI 3.51.0とは別。 |
| `posix_numeric_stream_v1` | `/bin/sh`、GNU bash 3.2.57のPOSIX実行。locale=C、絶対pathを固定したawk/sort/uniq。 |

これらは親の確認結果を受領したもので、本担当が実行して確認したものではない。環境manifestは`/Users/motonishikoudai/Projects/vera-round5b-run/profile_environment_initial.json`。binary SHA/size/解決path、macOS 26.5 arm64を含むとの連絡を受領した。環境の存在は意味契約への対応証明ではない。

## 3. 素材で明示する入力domainと上限

初回80件のうちM正例64件には、以下のdomainをraw依頼の通常の言葉でも明示する。profile IDを一語書くだけで要件を全省略しない。goldだけへpreconditionを追加してはならない。この小さなdomainは反証可能な初回試作の素材条件であり、Vera全体の上限ではない。

| 項目 | 初回M正例の契約 |
| --- | --- |
| 入力数 | SequenceまたはRelation入力は最大2、scalar parameterは最大2。位置/名前/供給方法をrawで指定。 |
| 行/要素数 | 各入力collectionは0〜32。join後の中間行は最大1,024を許す。witnessもこの範囲を守る。 |
| 基本整数 | boolを除く整数。入力numeric field/要素は−1,000〜1,000。閾値parameterも同範囲、multiplyの係数は整数−10〜10。 |
| 中間整数 | 各整数演算・集計の数学的結果の絶対値が2,147,483,647以下である構成を正例にする。作者/監査者が全許容入力について上界を別途確認する。 |
| record/relation schema | 平坦、1〜6field/column。名前/型は全列挙し、出力は最大8field/column。nested object、可変schemaは初回X。 |
| 識別子 | 初回素材の名前は`[A-Za-z_][A-Za-z0-9_]{0,31}`。関数/parameter名は対象言語の予約語を避ける。field/table/columnは別symbolとして扱い、同名でもscopeを区別する。 |
| key/text | 明示的なASCII text。keyは長さ1〜12、文字集合は英数字とunderscore。文字列mapの対象は長さ0〜32、U+0020〜U+007E。 |
| nullable | 指定されたnumeric fieldだけ`Int or null`を許す。nullと欠損は別。全fieldは存在する。欠損、undefined、NaN、Infinityは初回正例のdomain外。 |
| 入力の順序 | Python/JS配列とshell行は順序付き。SQLの順序が必要ならschemaに一意な整数ordinal列を明記する（1〜32でよい）。物理行順/rowidは根拠にしない。 |
| 依存規模 | 正例は1〜5の演算family nodeを基本とし、各profile少なくとも8正例に3以上のnodeを含める。runtime探索上限8nodeとは別。 |
| predicate | depth最大3、atomic predicate最大4。AND/OR/NOTを型付きtreeにする。深さはatomic=0、論理接続で1増。任意code文字列は禁止。 |

整数上界はrawに指定した入力範囲と演算から導く証明である。実装が「大きな値では動かない」から原文にない上界を追加することは不可。導出できない構成は作者が正例として採用しない。もしrawが上記より広い整数/長さ/精度を要求すれば、勝手にこのdomainへ狭めず、そのprofileの契約不足としてtyped拒否する。Pythonの任意精度等を将来対応から消す意味ではない。

このdomain外の**値を生成済みコードへ実行時に渡した際のエラー処理**は、rawに別途要求されない限り初回の正当性判定範囲外である。domain外の**要件をVeraに依頼した場合**のunsupported拒否とは区別する。型検査を実行時validationの要求へ勝手に置き換えない。

## 4. 中立な型・式と計数の境界

gold素材では言語中立な`Int/Text/Nullable[T]/Float64/Seq[T]/Record{...}/Groups[K,T]/Relation{...}`を用いてよい。runtimeのclass名は使わない。symbolはsource、parameter、field、intermediate、outputを区別し、同じ型のfieldでも別IDを持つ。型のうちGroupsは内部中間型であり、初回に裸のgroup containerを外部返却する契約にはしない。

入力参照、field参照、parameter、literal、固定field名へのalias、返却record構成は構造ノードとして扱える。これらへ任意計算を埋め込んで10family制限や8node上限を回避しない。計算は下表の演算とsubkindだけで行う。predicateのatom/tree、構造ノード、lawの照合は事前登録のwork counterへ計数する。

Float64は有限のIEEE 754 binary64値を意味する。Mean/Ratioの出力だけに初回導入し、Float64を入力とする再集計・算術map・ratioの連鎖はX。型やshapeをfloat/int共通の「数値が近ければよい」へ潰さない。誤差許容の一律epsilonは使わない。

## 5. 全10familyと四profileの厳密な対応

| family/subkind | Python | JS | SQLite | POSIX | M/Cの内容 |
| --- | --- | --- | --- | --- | --- |
| Filter:整数`== != < <= > >= even odd` | M | M | M | M | 指定source/fieldに束縛。valueはliteralまたは指定scalar parameter。負の奇数も剰余≠0。 |
| Filter:Text `== !=` | M | M | M | X | ASCII完全一致。大小変換、数値への暗黙変換なし。 |
| Filter:IsNull/IsNotNull、AND/OR/NOT | M | M | M | C | 下記三値規則。shellにはnullを持たない整数atomの論理式だけ。 |
| Map:square/abs/multiply | M | M | M | M | Seq[Int]の変換、または指定record fieldだけの更新。SQL算術mapは今回必要な新loweringである。 |
| Map:pluck | M | M | M | X | 指定fieldのみの値列へ投影。SQLでは指定aliasの1列Relation。 |
| Map:upper/lower/strip/length | C | C | X | X | 上記ASCII domainに限定。stripは両端U+0020除去、lengthはcode point数。 |
| Aggregate:sum/count | M | M | M | M | countは行/要素数。nullableの非null数はIsNotNull Filterとの構成。 |
| Aggregate:mean | M | M | M | M | 整数合計と個数から一度だけFloat64へ丸める。空時はNullまたは指定0.0。 |
| Aggregate:min/max値 | M | M | M | X | 非null整数の極値。空時はNullまたは指定整数sentinel。 |
| Aggregate:min/max全同順位 | C | C | C | X | 全同順位の元要素/recordを返す。空は空列。group内の全同順位は初回X。 |
| Group | C | C | C | X | 1つの非nullInt/Text key。直後のgroup Aggregateが消費し、key/valueのtyped record列を作る。 |
| Sort | M | M | M | M | 1つの非nullInt/Text key（shellはIntのみ）、昇順/降順、同順位は入力順を保持。 |
| Diff | M | M | X | M | Seq[Int]の隣接差。SQLの新window loweringは初回採用範囲外。 |
| Dedupe | M | M | M | M | scalar値または1つの非nullInt/Text keyによる先頭保持。SQL DISTINCTへの短絡は不可。 |
| Join | C | C | C | X | 2入力のinner equijoin、左右それぞれの1key、別schema、明示projection/alias。 |
| NotExists | C | C | C | X | 同じkey契約によるleft anti join。左recordと順序/多重性を保存。 |
| Ratio | C | C | C | X | 同じrecordの非nullInt分子/分母。分母0は明示Null。非0はFloat64。初回では結果が終端。 |

M表の全行が80正例に単独で1件ずつ出る必要はないが、後述の必須coverageを満たす。初回正例がこの表を越える機能を要するなら、測定後にunsupportedへ振り替えず、素材監査で修正理由を保存する。M/C能力表自体の変更は親の採用契約変更を必要とする。

## 6. predicate、null、zero、空の意味

nullable atomは三値T/F/Uで扱う。通常の比較・偶奇でoperandがNullならU。`IsNull(null)=T`、`IsNull(non-null)=F`、IsNotNullはその否定。rawの「nullと等しい/等しくない」は通常Eqへのliteral挿入でなくIsNull/IsNotNullと読む。`NOT(U)=U`、ANDはFがあればF・全TならT・それ以外U、ORはTがあればT・全FならF・それ以外U。FilterはTだけを残す。

この意味はPython/JSのtruthinessに委譲しない。SQLのWHEREと整合するnullable論理を、Python/JSでも型付きpredicateとして実装する契約である。nullを0やFalseに変換せず、NOTでunknownをtrueにしない。非nullと確認された枝だけならBoolへlowerできるが、そのlawを証跡に残す。

Mapの算術、Sort、Group、Dedupe key、Join key、Ratioはnullable operandをそのまま受け取らない。前段でIsNotNullを満たす対象へrefinementするか、当初schemaで非nullとする。pluckはnullable値の保存を許す。Sum/Mean/Min/Maxも非null入力のみで、nullを除く要求なら明示Filterを構成する。Countはnullを含む行も1と数える。

Zeroは正規の整数0でありNullではない。偶奇/除外/emptyとの取り違えをwitnessで区別する。Ratioの非0分母では、数学的な分数をround-to-nearest ties-to-evenでbinary64へ変換した値を正解とする。入力整数/中間整数の範囲内では分子/分母のbinary64化はexact。分母0ではNullを返し、例外、Infinity、行削除に変更しない。非零分母の0の結果は+0.0を標準化する。

Meanは整数のexact sum / countを一回丸めたFloat64。途中で丸めた平均の平均ではない。Python返却はfloat、JSはNumber、SQLはREAL、shellはFloat64へround-tripできる数値token。Mean/Ratioの正答比較は型を確認した上でbinary64値一致とし、−0を+0へ標準化するprofile規則を双方へ適用する。

| 空の位置/処理 | 初回の意味 |
| --- | --- |
| Filter/Map/Sort/Dedupe、Join/NotExistsが空列を作る | 空列のまま後続へ渡す。入力空への早期returnを全段へ流用しない。 |
| Diffの入力長0または1 | 空列。 |
| Sum/Countの対象空 | 標準は整数0。rawが別の許可sentinelを指定すれば該当aggregate scopeだけに適用。 |
| Mean/Min/Max値の対象空 | 標準はNull。rawが指定すればMeanは0.0、Min/Maxは整数sentinel。 |
| 全同順位Min/Maxの対象空 | 空列。Nullやscalarにしない。 |
| Groupの入力空 | group結果は0個。存在しないkeyの空groupを作らない。 |
| rawの明示input-empty override | 最大1つの名指したcollection入力に対して、その入口だけで適用。後段空のpolicyと別requirement。返却のunion型を明示。 |

sentinelは明示Null、整数−1,000〜1,000、Mean用0.0、または要求された型の空列に限定する。UNSPECIFIEDは値でなく契約状態であり、明示Nullと分ける。標準動作はprofileの公開規則だが、空/zeroが焦点のfixtureではrawにも明記する。caseを見て返り値を選び直さない。

## 7. 順序、group、join、出力schema

SequenceのFilter/Mapは相対順序を保存する。Dedupeは指定keyで最初に出た要素/recordを保持する。Sortはkey順、同順位は入力順、descendingでも同順位を逆転しない。Min/Max全同順位は元の相対順序を保存する。keyのText比較はASCIIのbinary順。field名の並びやrecordの挿入順をkey等値へ混ぜない。

Groupは型付きkeyのまま区別し、IntをTextへ文字列化しない。各group内の相対順序を保存する。初回は1つのkeyと1つのaggregateで`Record{key_alias:K,value_alias:V}`の列を作り、ここへFilter/Sort/Map-pluckを適用できる。group後のpredicateは元rowでなく集計recordへ束縛する。group結果を返す順序はrawが指定する（key順または最初の出現順）。SQLでは必要なordinalを明記する。

Group集計はSum/Count/Min/Max値を基本にし、Meanも返却可能だがFloat64を使う後段算術/predicateは初回X。group後Filterは整数のaggregate結果で行う。複数のaggregateを同じplanへ置くことは初回Xとし、10familyを増やさず将来拡張する課題として残す。裸のGroups返却、group内全同順位、nested groupはX。

Joinはinner equijoinだけで、左右keyは同じ型の非nullInt/Text、名前は異なってよい。同一keyの重複を左右とも保存し、m×n個の一致pairを作る。出力はrawが指定した左右fieldからalias付きで構成する。衝突fieldの右上書きをdefaultにしない。Python/JSでは左の入力順、各左に対する右の入力順。SQLで同じ順序が要求される場合は左右ordinalから明示ORDER BYする。

NotExistsは右に一致keyが一つもない左recordを返す。右の重複で左の個数を変えない。Join/NotExistsとも片側空、左右で似た名前/異なる値、重複keyをwitnessに含める。異型keyの強制変換、自然join、outer join、任意条件joinは初回X。

SQLの結果は常にRelationとして採点する。global aggregateは指定列を持つ1row（Nullも1row）、通常projection/group/joinは0〜複数row。出力列名・順をcursor metadataで検査し、expectedがscalar/dictかを見てdecode方式を変えない。順序指定のないRelationはbag比較で多重性を保持し、順序指定があればordered rowsで比較する。

## 8. profile別のinterfaceとprotocol

**Python:** 関数名、parameter名・順・positional-or-keyword/keyword-only区別をrawで指定できる。初回はdefault/可変長args/async/classをXとし、入力引数は必須のみ。関数をその署名のまま呼び、返却型/構造、stdout/stderrが空、入力の値が変わらないことを検査する。record field更新は新しい出力recordへ行う。object identityやdeep-copyの必須条件は初回要求に含めない。PythonのboolをIntとして合格させない。

**JavaScript:** `module.exports.<requestedName>`から呼べる同期関数。引数順と数を要求どおりに保ち、PromiseやJSON文字列へ変更しない。module load時/呼出時のstdout/stderrは空、入力不変。返却Object/Arrayは要求schemaどおり、undefined/missingをNullとして補完しない。ES module/default export/async/BigInt/Date等は初回X。関数本体のparameter名がrawで指定されればそれもinterface requirementへ残す。

**SQLite:** Python runner内のSQLite 3.53.2に対する読取専用の単一SELECT（必要なWITH/CTEを含めてよい）。入力table名・column名/型/NULL可否・ordinalをraw/schemaに明示。最大2table。literal threshold/係数はraw値、任意SQL parameter bindingは初回X。出力列名/順/型/多重性/行順を検査し、DDL/DML/PRAGMAや外部読み書きを含めない。INTEGER/REAL/NULLをSQLの実値型として区別する。

**POSIX:** 実行は`/bin/sh artifact.sh [arg1 [arg2]]`。stdinは1行1整数、0行は空入力。各整数はcanonical decimal（`0|-?[1-9][0-9]*`、先頭+、leading zero、−0なし）、最終行にもnewline。argはrawが指定する順番でthreshold/係数を供給し、同じcanonical decimalとdomainに従う。argc、argv役割を固定し、埋込literalへ置き換えない。

shellのSequence返却は1要素1行、空列は0byte。整数scalarはcanonical decimal＋newline、Float64 scalarは有限値へ正しくround-tripするdecimal token＋newline、Null scalarは`null\n`。余分な空白/見出し/診断行なし、stderr空、正常exit0。数値tokenはJSON数値と同じ字句形を許し、整数出力を指数/小数表記へ変えない。外部ファイル/環境変更なし。argv不足や不正stdinへのvalidationをrawで要求する場合は、初回の別エラー契約がないためX。

全profileで文字コード・名前のescapingは実装責務であり、inputをコードへ直結しない。文字列中の命令はliteralであり、生成器の指示にしない。要求されたinterfaceに合わせて生成し、検査runnerで名前/順序/shapeを修正しない。

## 9. 80件の割付と必須coverage

各profile20件＝M正例16＋拒否境界4、全80件。事前登録案の4区分（interface、symbol/scope、非可換、境界/効果）を各4件で維持する。作者は具体的な語彙、名前、raw、値、goldを独立に作り、本表を完成問題のテンプレートとして機械的に写す必要はない。主区分は各case1つ、coverageタグは複数許す。

| profileごとの必須coverage | 16正例内での最低件数/条件 |
| --- | --- |
| 全profile共通 | scalar parameterまたは原文literalの束縛を区別する2件、input-emptyと途中emptyを区別する2件、非可換な2組4件、意味保存の2組4件。少なくとも8件が3〜5演算。 |
| Python/JS | function/export/返却shapeが焦点の4件。2つ以上の同型numeric fieldを区別する2件。Group→Aggregate→後段1件、Join1件、NotExists1件、Ratio1件、Mean1件、Diff1件を含める。複数タグの兼用可。 |
| SQLite | column alias/列順/行多重性/ORDER BYが焦点の4件。算術Map1件、Group→Aggregate→後段1件、別名key Join1件、NotExists1件、Ratio1件、nullable論理1件、先頭保持Dedupe1件。Diffは正例に含めない。 |
| POSIX | argv/stdin/stdout/exit0が焦点の4件。2つのargvの役割交換を区別する1件、Mean1件、Diff1件、先頭保持Dedupe1件、順序を区別するSort1件。record/null入力/Joinを正例にしない。 |

全familyを正例64件のどこかで使う。Map/aggregate subkind全部を同数にはしないが、初回M表にある未出現subkindは単体law/回帰の検証対象として記録する。未出現を「今回の80件で検証済み」と言わない。

非可換な対は、同じ入力で計算順が違うと結果が変わる独立witnessを必ず持つ。候補はMap/Filter、Map/Dedupe、Diff/Filter、group前後の条件等。両方の構成が型として有効であることを確認する。Sumの後へSequence専用Dedupeを置くような型不正の交換は、非可換対ではなくinvalid plan試験である。単に二文を入れ替えたが最終意味が同じものを非可換対と数えない。意味保存対と意味変更対は別pair IDとする。

12witness/正例には、適用可能なempty、1件、ゼロ/負値、比較境界の直下/一致/直上、fieldを片方だけ変える例、重複key、同順位と逆順、片側empty/非一致、Null、返却shapeを区別する例を割り当てる。全部の契約に全部の種類を無理に入れず、非適用理由と代替witnessを記録する。12個のうち同じ結果になる簡単な例だけで埋めない。全witnessでinterface/型/出力/入力不変/protocolも検査する。

拒否境界は各profileで(1)異なる意味解釈が同じ根拠、(2)両立しない明示要件、(3)本表Xの明示機能、(4)必須情報を明確に欠く要求を各1件とする。(4)は作者がruntimeの苦手表現を推測して選ばず、たとえば演算の対象や比較基準が欠けて一意の契約を作れない構造にする。読み方が複数具体化できる(1)と、必須slot自体が与えられない(4)を区別する。typed reasonはcanonical診断へ対応させる。

これにより事前登録案の「未解釈境界」は**初回素材では必須情報不足の客観的な境界**として具体化する。初回文法の実装が苦手だった正例を後からこの拒否枠へ移さない。正しい拒否16件をEの40/80分子へ足さない。

gold診断は中立labelの`ambiguous / conflict / unsupported / incomplete`を用いる。実装のtyped reason名は対応表で写像できるが、4種類を単なるunknownへ潰した場合は診断全通過としない。不足する語が原文にない場合は、その必須slotを要求する節のspanと「何が与えられていないか」を記録し、架空のsource spanを作らない。

## 10. runtime型に依存しないgold受渡し

素材作者へ渡すのは本書§3〜§10の意味契約（環境指定が必要なら§2のprofile表）、事前登録案の対象/件数/品質/独立性、生成担当と保存先の指示だけ。§1の現行分岐一覧は実装側の再利用監査用であり、素材生成の根拠にしない。code_spec/compose、A内部schema、現在の出力、旧問題を読ませない。goldは次の中立情報を持てばよく、実装者が後でlossless adapterを作る。

| gold層 | 作者/監査者が持つ内容 |
| --- | --- |
| raw/meta | case ID、profile、主区分、coverage tags、pair ID/関係、raw、正例/拒否境界。 |
| ledger | 原文offsetと引用文字列、独立した要件ID、対象とscope、interface/型/肯否/順序/境界等の自然な説明と形式意味。 |
| contract | 入出力domain、symbol/field、署名/protocol、返却値の数学的関係/性質、order/effect/empty/zero、充足すべき全要件。 |
| gold plan | contractと別に作った型付き依存graph。任意のruntime node名やemit手順を要求しない。同値の有効planを許容する。 |
| caller/oracle | 要求interfaceそのものの呼出、12入力、期待値と型/schema/protocol、手計算/別方式確認、入力不変などの性質。 |
| provenance/review | 作者、監査者、原本hash、修正履歴、profile適合/上界/非可換性/null等の確認記録。 |

Sにはcontract層までを入力し、gold plan/callerの正解構成は採点側に保持する。contractを実装手順の同義語へ潰さず、入力と出力の関係、条件、scopeから正当なplanを作らせる。Lだけはgold planを明示入力できる。Eにはrawのみ。素材JSONのfield名は保存上の形式であってruntime schemaではなく、形式名の違いを誤答にしない。

作者のgold計画が唯一であることを仮定しない。独立contractを満たす別planはlawとwitnessで認め、型が合うだけ、有限witnessだけの一致では同値判定しない。署名/空/null/orderを落とした「同じ数値結果」を正解にしない。

## 11. 作成順序と採用後の責任

親が事前登録案と本profileの意味、件数/予算/採点を採用し、担当と出力先を指定すれば、素材生成を始められる。schemaやcounter hookの実装完成を待たない。素材の構文・profile・全goldを独立監査してhashを固定し、実装担当がrawを読む前の版と修正履歴を保存する。B実装の具体型、lowering、law/checker、counter配置、runnerは実装担当の仕事であり、対応が完了したかは実装後に検証する。

素材生成の指定モデルはgpt-6-luna low fast、実装はgpt-6.1-sol max fastなし。独立監査者はVeraを実行する前に意味・gold・caller・witnessを確認する。これは公開開発素材であって新封印ではない。新封印の本文/参照/個別採点の分離は継続する。

初回profileのM/C/X、上限、null/float/order仕様を素材や結果を見て変更しない。契約矛盾が見つかった場合は、測定前なら親が理由付きで版を変更して素材全体を監査し直す。測定後なら当該初回判定を無効/未確定として残し、訂正版を別runにする。実装都合のsilent subset化やwitnessだけの成功で意味の幅を偽らない。

本書では採用判断・環境hash保存・生成開始を行っていない。親が採用追記とmanifest/hashを固定する。通常routerへ統合したone.Veraと四群の最終新封印が必要であり、mode="contract"の初回profile通過だけで全体完成とは呼ばない。
