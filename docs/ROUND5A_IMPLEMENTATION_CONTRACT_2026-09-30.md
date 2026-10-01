# Round5-A 実装契約の補足（初回測定前）

2026-09-30。`bdb454f` の正式事前登録を変更しない。以下は縦断試作の実装上の定義を明示する追記であり、採用条件・固定目標・予算の緩和ではない。

- 公開入口は `one.Vera(..., mode="semantic")` および `ask(..., mode="semantic")`。このモードは原文から専用の意味計画を読み、旧 slot/assembler/skills/一般回答へ fallback しない。旧モードは従来の API として保持する。
- 文書 view は追加した原文を保持する。source span は Python 文字列の半開区間であり、注入文を除いた連結文字列の offset ではない。Frame の時制・Edge の節/modality・Stage の区切り候補・verdict.Item の規範種別を外側の節構造に残す。
- parse32 は一つの原文 scope の意味読み候補数、depth8 は計画および提出 proof の依存深さ、candidates256 は一回の質問で各 sovereign が検査する節の総上限、bindings64 は中間演算で保持する異なる束縛状態の上限、steps4096 は実行と独立検査に割り当てる操作数の合計。取得は上限+1を検出し、超過時に切り捨てた候補から ANSWER を作らない。ingest/索引初期化は ask と別計測する。
- 文書間の Join は同じ文書 sovereign 内だけ。一般 QA は既存 EvidenceLibrary の六腕/面 routing と predicate postings を読み取り adapter から使う。各 family の計画実行・proof 検査を分け、family 間の部分束縛・根拠数・票を混合しない。異なる検証済み回答が残れば棄権する。
- 条件と例外は開世界で扱う。条件の根拠不在は偽ではない。例外の不適用には明示的な反対根拠が必要。未対応の必須要求・作用域は原文 span とともに typed refusal に残す。
- verifier は producer の成功 flag と束縛を信用しない。出典原文に対する節の licensing、演算前提、束縛、単位、条件/例外、全 obligation、最終出力を別実装で検査する。ただし proof の健全性は自然文 reader の完全性を証明しない。kernel、独立素材の reader、公開入口の正誤棄権を分離する。
- B/C、任意の日本語文法、談話照応、全量索引への変更はこの実装の完成対象に含めない。未実装の構造を結果文書へ明記する。開発80件は採用判断の素材であり封印成績・一般化証明ではない。

測定素材 manifest に HOLD が記載されている間は評価しない。fixture/参照解答には実装担当から変更を加えない。

初回測定前の追加定義（独立kernel/checkerレビュー後）:

- 最新の人間指示を優先し、gpt-6.1-sol / max / FAST（priority）で同じセッションを継続する。意味・採否・予算は変更しない。
- Decimal は128桁以内、指数の絶対値256以内の有限量を扱う。比較は有理数で厳密に行い、変換・加減算は厳密な有限Decimalへ戻せる場合だけ通す。表示にも ambient Decimal context を適用しない。非終端変換や表現範囲外はtyped refusal。
- steps は候補/索引キー訪問、照合するrole、条件の閉包、代替witness探索、演算、行の重複検査、shapeのnode/依存/term/obligation、提出DAGのnode/edge/binding/coverage/answer、出典照合を計上する。日本語の原文節境界の独立走査は初回のみ文字数を計上する。固定した不変Request/Planのshapeは再検査の同一オブジェクト照合後に再利用できるが、proofの検査やSourceのcanonical内容照合は省かない。原文Frame等の既存形態素ライブラリ内部処理は一つのlicensing操作として扱い、4096 CPU命令や4096文字の一般的上限とは主張しない。
- obligationの原文位置をoperator/outputにも保持する。要求の有効な別substringへobligationだけを移しても拒否する。symbolic recordはkernel専用の一出典一式の閉じた文法として full-source / body / predicate / role / When・Unless / time を照合する。自然文の切り詰めによるguard消去は、元原文の節境界検査でも拒否する。
- ask全体で実行・検査のstep Meterを共有する。現行QAの取得は別traceで候補行256、各posting257件目の検出、最大depth8の名詞依存展開を記録する。familyおよび既存rowのindependent属性を別sovereignとし、Joinしない。context質問をassertionへ昇格させない。
- 公開80件の主集計は正答ANSWER / 誤答ANSWER / 棄権の3区分を全80分母で保存する。正しいUNKNOWN/CONFLICT/AMBIGUOUSは「適切棄権」として別集計する。値は空白・句読点表記のみ正規化し、数量はDecimalと単位を厳密比較する。boolean出力は、参照polarityがあるboolean質問（whや末尾「は？」を除く）で参照polarityを比較する。entity/quantity出力をbooleanだけで正解にしない。必要なsource IDsをすべて含むことをANSWERの採点条件にする。自然文required_factsは原本と出力を保存して検討できるようにし、実装readerから期待値を作らない。
