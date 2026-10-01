# Round5-A 公開意味経路の実装・開発測定

2026-09-30。**この試作は未採用。Aの自然文対応は未完成であり、Round5全体・6能力の完成ではない。** 初回は正答ANSWER 6/80、誤答ANSWER 0、棄権74。意味経路内の一般的な要求読解不具合を修正した後は5/80、0、75だった。60%以上という正式採用条件に届いていない。B/Cは実装していない。新封印・既存封印再試験・heldout評価は行っていない。

正式事前登録 `bdb454f` の予算、採否、広い目標を維持した。最新の人間指示によりgpt-6.1-sol / max / FAST（priority）で同じ実装セッションを継続し、実装を別モデルやサブエージェントへ委譲しなかった。Python実行経路に学習・LLM runtimeはない。モデル起動の記録は `vera-round5-run/preflight/resume_fast.json`。実行環境は専用envのPython3.11.15。

## 実装した方式差と再利用

公開 `one.Vera` に明示的な `mode="semantic"` を接続した。この分岐は旧question.read、slot選択、Bot.find、skills、一般ANSWERの前に入り、拒否後もそれらへ戻らない。既存モードとAPIの既定値は維持している。

意味経路は原文を保管した文書viewを初期化時に作り、質問を節・役割・型付き変数・polarity/modality/time・全要求obligationの計画へ読む。Sourceから `Bind / Join / ApplyCondition / Except / Filter / Sum / Difference / Compare / Project` を経たproof DAGを生成し、別実装のcheckerが原文licensing、束縛、全祖先の条件/例外、演算、出力、obligationを再生する。提出proof外の適用可能な反対証拠と省かれた回答候補もauditする。異なる検証済み回答は棄権し、順序やIDや票数で選ばない。

- Frameの役割・predicate正規化、typed_edgesの節/case/modalityとMeCabを再利用した。原文助動詞の時制を追加で保持する。旧Frame自体は変更しない。
- Stageの読み候補をRequestへ保持し、verdictのItem読解/規範種別判定を利用する。Stage候補が自然文の意味を完全に確定するとは主張しない。
- Variableは既存rewrite_core.Varを拡張し、producerの照合・Joinに既存match/substituteを使う。汎用書換え器を再新設していない。
- checkerはproducerのmatcher、算術helper、成功flagを使わない。照合・有理数算術・proof再生を別実装した。原文Frame等とshape/type契約は共有するため、共通原因の読解誤りを排除した証明ではない。
- Decimalは有限128桁・指数絶対値256の契約。Compareは厳密な有理数、変換/加減算は厳密な有限Decimalのみ。非終端変換や範囲外は拒否する。表示もambient precisionで丸めない。

現行QA adapterは既存EvidenceLibraryのconduct_treeとterm/predicate postingsを読み取り、原文rowから同じ意味経路へ渡す。familyとrowのindependent属性は別sovereignにする。context質問を根拠へ昇格せず、他sovereignから欠けた束縛を補わない。DBはmode=ro/query_only、索引再構築・全量Wiki切替・大きい資産の変更をしていない。

## 固定予算と独立レビューの修正

parse32 / plan・proof depth8 / candidates256 / bindings64 / shared steps4096を維持する。ask全体でproducer/checkerのMeterを共有する。論理操作の計量定義、取得との分離、キャッシュ条件、数量の契約、採点方法は [実装契約の追記](ROUND5A_IMPLEMENTATION_CONTRACT_2026-09-30.md) に保存した。4096 CPU命令という意味ではなく、既存形態素ライブラリ内部の全操作数を計数した証明でもない。

独立原本を上書きせず、修正後probeを別名で保存した。レビュー時点の不具合と最終公開ANSWERの誤答を混同しない。

| 指摘 | 実装と検証 |
|---|---|
| K1/K3 | 同じ束縛でも異なる根拠/条件の導出をscope処理前に落とさず、Join全親のpending条件/例外を維持。順序置換と右親欠落を検査 |
| K4 | proof外の条件付き反対証拠も、その条件の明示根拠を含めて検査 |
| K2 | 内側のbind、predicate閉包、索引キー、条件支持、witness、重複検査、DAG抽出を計量。元probeの4160 bind呼出は修正版で64。最終同等goldの64回答は実行+検査2595 steps以内で通過 |
| R2-1/1b | dict縮約前の全Variable occurrence、全operator文脈、bound value type、event sortを検査 |
| R2-2 | trailを含む条件cache、非循環witnessの再構成と最小依存深さ。直接factつき全24順序を維持、純循環は拒否 |
| R2-3 | 高精度の同単位/異単位、比較・変換・加減算の厳密契約。ambient precision12/28/64で検査 |
| R4-1 | Sourceのcanonical全内容をcacheの外で常に照合。原文text、predicate_span999、family、time等7改変を実gateでも拒否。公開入口でも4改変を拒否 |
| R4-2〜5 | guard正負競合、未処理生Sourceのwitness流用、claim/proof回答の入替え、canonical IRのWhen/Unless消去・predicate/time捏造を拒否 |

原本 `kernel_probe_initial.*`、`kernel_shape_revision02_review.*`、`checker_revision04_review.*` 等は保存した。再実行は `review_probes/*final07.*`、`*final08.*` と `checker_final08_summary.json`。各JSONには実Pythonと実装hashのbefore/afterを記録する。親が報告した65件拡張境界レビューはproducerの別診断であり、この公開80件成績や最終独立採用判定の代替ではない。

## 検査の層

最終 `gates_final05/gates.json` はkernel68、reader10、公開入口22、adapter4を通過。旧互換55件は `gates_final03` の通過結果を、one/bot/questionのbyte一致を検査して再利用した。合計159件。kernelは自然文readerを使わないgold式・固定計画とmutation、readerは独立に手記述した小さい自然文oracle、公開入口は原文からの全経路・改変・順序・欠落要求・注入、adapterは隔離した小さい索引の正しいJoin/分離/上限/非書込を検査する。

Source、licensing、scope、例外、反対証拠、provenance、Bind、Join、算術、Project、obligation、Unread、DAG、上限+1、tie、不変性、公開fallback禁止を含む。checker helperを毒化せずproducer helperだけを例外化してもgold算術の独立検査が通る。自作producer由来の期待値だけで自然文理解を証明していない。

初期のテスト起動失敗、basetemp親欠落による4件のharness setup errorも残した。`gates_revision07` の91通過/4setup error、修正後のrevision08/09、final01〜05を保存し、時制修正中のfinal04公開テスト1失敗も削除していない。

## 公開80件の全問結果

独立監査済みAPPROVED/ready_for_evaluation=trueの素材のみを使用した。80行・12対24行、SHA-256:

`a765402a5fc88176dd17833730780c3b8c917f7c3d80a7748277c61845c1c693`

fixture/参照解答は生成・修正・削除していない。19行の独立訂正履歴は親の `fixture_corrections.json` / fixture_versionsにある。参照ANSWER63/UNKNOWN10/CONFLICT4/AMBIGUOUS3はVera成績ではない。

| run | 正答ANSWER /80 | 誤答ANSWER | 棄権 | 適切棄権（別集計） | 順序変更 | runtime error / budget棄権 |
|---|---:|---:|---:|---:|---:|---:|
| 初回 public80_run01 | 6（7.5%） | 0 | 74 | 10 | 0 | 0 / 0 |
| 修正後 public80_run02 | 5（6.25%） | 0 | 75 | 10 | 0 | 0 / 0 |

主集計の棄権には正しいUNKNOWN等も含む。ANSWERと適切棄権を合算した照合は初回16/80、修正後15/80。どの集計でも60%に届かない。修正後の全verdictはANSWER5、UNKNOWN_NO_EVIDENCE43、UNKNOWN_UNREAD20、UNKNOWN_UNSUPPORTED_EVIDENCE10、UNKNOWN_CONDITION1、CONFLICT1。

| family | 全問 | 初回正答 | 修正後正答 | 修正後棄権 |
|---|---:|---:|---:|---:|
| role_binding | 4 | 2 | 2 | 2 |
| equivalent_paraphrase | 2 | 2 | 2 | 0 |
| injection | 4 | 1 | 1 | 3 |
| negative_polarity | 2 | 1 | 0 | 2 |
| multi_argument | 4 | 0 | 0 | 4 |
| two_hop_join | 6 | 0 | 0 | 6 |
| condition | 4 | 0 | 0 | 4 |
| exception | 4 | 0 | 0 | 4 |
| conditional_exception | 2 | 0 | 0 | 2 |
| negation_scope | 4 | 0 | 0 | 4 |
| unit_calculation | 7 | 0 | 0 | 7 |
| comparison | 7 | 0 | 0 | 7 |
| quote_reality | 4 | 0 | 0 | 4 |
| multiple_requirements | 6 | 0 | 0 | 6 |
| insufficient_evidence | 6 | 0 | 0 | 6 |
| conflicting_evidence | 4 | 0 | 0 | 4 |
| ambiguity | 4 | 0 | 0 | 4 |
| time_scope | 4 | 0 | 0 | 4 |
| counterfactual_scope | 2 | 0 | 0 | 2 |

12対のうち両行とも正答ANSWERはp01/p12の2対。全80の文書順反転でverdict区分/値の変更0を別JSONへ保存した。複数資料がない行は同一の置換となる。行/候補順、複製、相反根拠、必須条件除去は独立のkernel/public変形テストでも検査した。これを全80の行順置換がすべて意味同値で検査できたという主張にはしない。注入4件は1正答/3棄権、命令追従0。資料の命令をSource assertionとして採用していない。

### 初回後の修正記録

初回を残してから、fixtureに依存しない二つの読解不具合を手動probeで再現した。

1. `関数を書いてください。` を既存の「関数を書いた」事実からboolean ANSWERへ縮めた。既存のspeech-act/generation判定を使ってtyped unreadへ直した。B/Cを実装したものではない。
2. 過去の質問/guardを非過去の記述で充足した。質問とguardの時制をPattern/obligationへ保持し、checkerも原文助動詞を独立照合する。既存Frameのconverse変換時のpast消失は意味経路の原文読解で補い、旧Frameを変更しない。

before/afterは `speech_act_correction01_*.json` と `tense_correction01_*.json`。理由と全80前後差分は `corrections_run02.json`。r09/r28の棄権種別変更、r54のANSWER→棄権を保存した。r54の「〜ていない」というaspectの解釈は未対応で、正答を取り戻すために時制条件を消していない。

## 初期化と遅延

| run / phase | 中央値ms | p95 ms | 最大ms |
|---|---:|---:|---:|
| 初回・文書初期化 | 4.439 | 17.908 | 306.404 |
| 初回・ask | 1.577 | 36.648 | 415.691 |
| 修正後・文書初期化 | 14.099 | 105.626 | 406.649 |
| 修正後・ask | 2.843 | 151.003 | 1027.059 |

peak RSSは初回71,499,776 bytes、修正後71,680,000 bytes。候補/steps/peak bindingsは各回答に保存した。80件の中央値50msは下回ったが、ほとんどが棄権であり、広い能力での50msを達成した意味ではない。並行コーパス処理と隔離verify_allの負荷を環境JSONへ記録し、無負荷測定とは呼ばない。

実在索引への `qa_current_index_run01` は4family接続を確認した。初期化137,641.734ms、ask診断は1,439.274msと58.622ms、双方UNKNOWN_BUDGET（retrieval candidates）。索引のDB/pickleサイズ・mtimeは前後一致。取得の未達をkernelの失敗と混ぜない。最終時制修正前の接続診断で、一般QAの独立accuracy oracleを持つ成績ではなく、QAの50ms達成とも呼べない。

## 未実装・未解決

全要求のDAG契約が自然文の全要求を正しく読む保証にはなっていない。公開fixtureの大半を導出できず、必須能力を満たした完成実装とは呼べない。

- 自然文の明示例外の一般的な適用/上書き/argument継承。IR/Except/kernelでは明示的な否定witnessを検査するが、日本語の「ただし」規則はunsupportedを保持して拒否する範囲が多い。
- 複数predicateの節作用域、列挙・共同主体・全称/数量限定、任意の複数要求、条件のmodal/nominal/time読解。
- 関係節を介する一般的な多段束縛、談話照応、省略、同一eventの再記述。event sort/identityのkernel照合はあるが自然文のevent同定は未完成。
- 明示日付/時刻、相対時点、version優先、進行・完了・「〜ていない」のaspect。時制のpast/nonpastのみ厳密に保つ対応は十分でない。
- fixtureにある閉じた在庫増減、空間配置、複合単位演算/比較の一般的な要求計画化。限定した名詞pathの計算だけを広い能力としない。
- 一般QAのcandidate recallと大きい索引の初期化/応答。現行索引の257件目で止めるため診断2問を解けず、上限を増やして救済していない。
- 最終版に対する新しい独立レビュー/採用判定。修正minimal probeや自作goldは一般化・読解完全性の証明ではない。

## 再現と保存

```python
from verantyx.one import Vera
v = Vera.from_texts({"d": "ユキの担当はソラ。ソラの居室は西棟。"}, mode="semantic")
result = v.ask("ユキの担当の居室はどこ？")
# result["semantic"]にrequest/plan/proof/budget、sourcesに原文spanを保存
# 既存instanceでも v.ask(question, mode="semantic") が明示入口
```

```sh
PY=/Users/motonishikoudai/Projects/vera-round5-run/env/bin/python
$PY tools/round5a_verify.py --output /Users/motonishikoudai/Projects/vera-round5-run/gates_reproduction
$PY tools/round5a_evaluate.py \
  --fixtures /Users/motonishikoudai/Projects/vera-round5-dev/fixtures.jsonl \
  --manifest /Users/motonishikoudai/Projects/vera-round5-dev/manifest.json \
  --gates /Users/motonishikoudai/Projects/vera-round5-run/gates_reproduction \
  --output /Users/motonishikoudai/Projects/vera-round5-run/public80_reproduction
$PY tools/round5a_qa_smoke.py --output /Users/motonishikoudai/Projects/vera-round5-run/qa_reproduction
```

実行器は既存runの上書きを拒否し、APPROVED/hash/80件/参照sourceと対応する全gateを測定前に確認する。環境、全80回答、参照値/required_facts/source IDs、正誤棄権、初期化/ask時間、source hash、文書順反転、各pairを保存する。QAは既存rootを既定で使用し、索引を作り直さない。

既存healthは隔離copyで実施した。baselineはpytest55通過、doctor exit0、verify_all forks89/89・47/50（frozen binary欠落V5、依存V24、timing V42未通過）。変更後もdoctor exit0、verify_all exit1・forks89/89・47/50、未通過IDは同じV5/V24/V42で、新規失敗0。隔離実行は1,875.775秒、baselineは269.721秒だった。QA初期化等も並行しており、速度比較の制御実験ではない。health snapshotは初回測定時のcodeで、後のsemantic reader/checker内だけのspeech-act/時制修正は最終semantic gateとrun02で検査した。既存one/bot/questionのhealth対象ファイルは最終版と一致する。全成果物は `health_final01/checkout` とstdout/stderrにあり、実repoの既存結果を上書きしていない。

`preservation_final01.json` ではbaselineの保護対象348ファイルの内容一致、変更はone/bot/questionの3件、消失0を確認した。封印/heldout関連のmetadataに列挙された2pathは内容を読まず除外した。.openclaw、paths.py、既存実験結果、記憶DBは保全した。記憶DB非変更というユーザー指示を優先し、vera-1への直接書込はしていない。commit/push、公開パッケージ同期もしていない。

変更ファイルは意味経路7module、既存one/bot/question、gold helperと4 test file、4 reproduction tool、実装契約と本結果文書。最終hashと全runは `/Users/motonishikoudai/Projects/vera-round5-run/` に残す。
