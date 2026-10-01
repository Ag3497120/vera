# Round 5 設計監査 — 意味を保持して合成・検証する経路へ

監査日: 2026-09-30。独立設計監査。**この文書は方式の提案であり、実装・性能改善の報告ではない。**

## 監査境界と判断

`CLAUDE.md` を読み、指定された `python3.11 -m verantyx.cli index search` を実行した。検索語は複合語句のほか `question`、`compose`、`frame`、`plan`、`constraint`、`proof`。複合語句の UNKNOWN だけで不存在とは判断せず、個別検索と実コードを確認した。索引は 639 エントリーを検索したと報告した。

閲覧対象は Round 4 の仕様・結果、integration map/master plan、関連 runtime のソース。新規評価・テスト・ビルド・索引更新を実行していない。sealed5 と Pro heldout の本文・参照・個別出力は読んでいない。現在の runtime と外部 corpus/index は変更していない。この新規文書以外のファイル変更、git commit は行わない。

親から受け取った最新独立封印集計は、一般 QA 正1/誤1/棄権13（15）、コード 正0/誤1/棄権14（15）、文書 正63/誤20/棄権37（120）、6能力 正5/誤7/棄権78（90）、injection 0、median 18.748 ms。本監査では独立再照合していないため、これは**受領した集計**である。各失敗を特定のコード箇所へ帰属させることはできない。Round 3 も正答率未達であり、4群とも同じ方式の微調整と再試験を止めるという決定を前提にする。

監査終盤の更新: 親から、独立評価は参考106件まで終了し最終ハッシュ一致、runtime固定解除と連絡を受けた。同方式調整・再試験の停止は継続する。本監査自体は引き続き文書作成のみとし、本実装を開始しない。

結論は、**「自然言語を型へ変換する」「出典を付ける」「部品を連結して実行する」は既にある。次方式の差は、節・変数・作用域・要求全体を失わず保持し、その意味計画から導出した応答だけを解放すること**に置く。一般 QA、コード生成、即時文書複雑 QA を主軸のまま、自由文・常識・比喩・冗談・俳句/物語へ同じ接続契約を育てる。生成を LLM へ委譲する提案ではない。

## 実コードで確認した構造

以下の「確認」はソース上の制御・データ構造を意味する。新規実験での発現や失敗頻度を意味しない。

| 確認した構造 | 実装箇所 | 次方式に必要な変更 |
| --- | --- | --- |
| 型付き `Query` は既に kind/slot/stages/polarity/intent/出所を持つ。ただし多くの種類は正規表現の優先順で1つに決まり、最終 `SlotFrame` は全節の predicate と argument を集合化し、否定は `any(...)` の1 bit、subject は1つ。 | `question.py:96–108,159–221,329–352`; `answer_slots.py:38–47,85–103` | 複数の出来事、引数の役割、否定の作用先、数量の対象、条件と結論の関係を別の節ノードとして残す必要がある。型の名前を増やすだけでは解消しない。 |
| `Frame` は agent/patient/recipient/negated を持ち、active/passive/converse の正規化資産がある。一方 `Frame.key()` は時制を含まない。 | `frames.py:32–36,151–166` | このフレームを再実装せず、時点・作用域・節間関係を外側で保持する。キーが同じことを、全要求に対する意味同一性とみなさない。 |
| QA の検索は原則 subject の完全一致と predicate key。文書化時に subject を得られない文は除外。候補は1 leaf と capped framesから来る。 | `evidence_library.py:100–115,180–216` | 主語が未知変数になる問い、関係を辿って同定する問いは、entity/role を変数とした段階検索契約が必要。コーパス量や cap の増量だけで読解契約は変わらない。 |
| 資格判定は predicate 集合の包含、arguments が本文/context にあること、文に値型らしい表現があること。値の位置が特定の出来事と結ばれた証明項ではない。 | `answer_slots.py:147–175,178–221` | 「値がある」と「求めた関係の値である」を分離し、回答変数を特定の証拠節へ束縛する。 |
| QA の独立出典数は `norm(candidate["text"])` 単位に集約する。意味が同じ別表現でも別候補になる。検索 sovereign は分離され、その後候補を集めて選択する。 | `answer_slots.py:224–247`; `round3.py:288–314` | データの異なる証人の照合は維持するが、照合対象を表面文でなく型付き answer proposition とし、文体差を答えの相違と混同しない。証拠なしの同義化はしない。 |
| 文書回答は `_compose_existing` を先に実行し、結果が `NOT_IN_DOCS` のときだけ Round 4 の `answer_slots` 回復へ進む。旧経路の ANSWER は新 gate で再検査されない。 | `answer.py:1468–1509` | すべての answer producer を提案にし、同一の完全性/根拠検査へ通す契約変更が必要。fallback の追加だけでは旧誤答を覆えない。 |
| 旧文書経路は重み付き語一致と語形条件で順位を決め、`_rank` は同点を doc/index で並べ、通常経路は `ranked[0]` を選ぶ。一般的な厳密同点棄権はこの箇所にない。 | `answer.py:368–426,429–450,1346–1367` | routing score と答えの正当性を分ける。同点候補が意味的に異なるなら棄権する。配置順は意味を増やさない。これは現行の固定原則との整合上の問題だが、単独修正を「新方式」とは呼ばない。 |
| 比較・集計・多段回答に個別の数量操作や隣接文選択があるが、共通の変数束縛された query operator tree にはなっていない。 | `answer.py:520–596,599–710,713–924,1375–1431` | 選択・結合・集計・差・条件適用を型付き演算とし、演算ごとの証明責務を持たせる。 |
| コードは既に `Specification`/`Operation`、複数 backend、実行照合を持つ。field の推定に60文字内距離を使い、演算は文字位置で順序化し、group/aggregate は後へ並べ替える。中間値/型/変数束縛/出力構造を表す木ではない。 | `code_spec.py:16–40,64–73,118–226,235–248` | 表面語順から離れ、依存関係・入力出力型・束縛を持つ program contract と型付き構文木を中心にする。 |
| コードの samples、reference、backend は同じ parsed spec を共有する。実行照合は code→spec の検査には有効だが、自然文→spec の取り落としを独立には検出しない。 | `code_compose.py:107–139,406–408,504–539` | 仕様の各要求を原文spanと結び、独立の要求充足検査を設ける。共有 spec を増やすだけでは oracle の共通誤りを防げない。 |
| 生成には出典 Frame→realize→同じ frame reader の再読がある。再読一致自体で入力の読み違いを修復できない点をコードも明記する。物語は隣接 corpus 文の列を選ぶ。 | `abilities.py:181–202,1613–1754` | 局所文の往復に加え、複数文の参加者/状態/時間/要求を一貫した計画で検査する。 |
| `_scene_graph` は選ばれた行の語共起 graph を trace に記録する。`_writer_candidate` は候補と再読結果を trace に書くが、採用文を書き換えない。 | `abilities.py:1580–1611,1747–1753,1756–1783,1806–1813` | trace に部品が現れることと、答えの内容がその部品の計算に依存することを分けて測る。 |
| 俳句には既に mora/切れ字/scene の制約探索があるが、4 moraの季語＋「や」を先頭にし、7/5の断片を貪欲に選ぶ。 | `abilities.py:1441–1520` | 「制約探索を入れる」だけでは新規でない。全文計画を探索対象にし、テーマ・視点・時点等の共同制約を扱う差が必要。 |

以上から想定される一般化の壁は、語彙不足だけでは説明できない。異なる構造の文が同じ flat slot へ落ちるなら、後段の証拠が十分でも失われた関係を復元できない。一方、封印問題でこの原因が何件を占めるかは未確認である。

親から本文なしで受け取った方式別所見は、コードの要求インターフェース欠落、文書の別slotの近傍事実/複数条件欠落/計算結合不足/肯否と根拠矛盾、創作の内容条件欠落、現在情報に対する保存叙述の返答である。前三者は flat specification、slot判定、旧経路の成功時バイパス、局所再読と整合する**原因候補**だが、個別入力/traceを見ていないので直接因果の確認とはしない。現在情報の所見も、live分類と主張の有効時点を別々に扱う必要を示す仮説として採用する。単なるlive語の追加は新方式に含めず、計画に query time、assertion valid time、freshness requirementを持たせる方向とする。

## 再利用すべき既存部品と限界

| 既存部品 | 再利用できるもの | そのまま同等実装とはいえない理由 |
| --- | --- | --- |
| `frames.py:151–166`、`typed_edges.py:31–59` | event roles、predicate位置 `ev`、assert/quote/hedge/cond_if/cond_then、時制 | full query plan の変数・量化・作用域を保持した回答契約ではない。特に richer edge metadata を flat slot へ落とさないことが要点。 |
| `verdict.py:49–56,113–180,314–322` | Item、fact/permission/obligation/prohibition、condition、exception link、省略の由来 | condition は文字列、`_mentions` は内容語の包含。一般的な条件式・例外の適用証明を提供するわけではない。 |
| `stage_split.py:355–448`、`question.py:31–48` | 節候補、原文span、段階候補 | 段階を見つけることと、各段階の出力変数が次の役割へ結合されることは別。 |
| `conduct_tree`/`surface`/`sovereign`、`EvidenceLibrary` | 六腕・面の導通、独立 sovereign、bounded leaf/後退 | 証明探索への候補供給として残す。共起辺や近さを含意の証拠へ昇格しない。 |
| `puzzle.py:51–106` | 候補の積集合、複数残存時の `UNKNOWN_UNDERDETERMINED` | facet を持つ候補の絞り込みであり、節間の関係結合そのものではない。新たな証明では、各絞り込み条件も出典命題に結ぶ。 |
| `rewrite_core.py:50–64,108–166` | 項、変数、一度束縛した変数の一致、代入、typed budget/no-rule | 自然言語の文法/意味型/根拠 verifier はない。rewrite は先に適用できた規則を選ぶので、回答曖昧性の消去にはそのまま使わない。 |
| `rewrite_kernel.py:1–15,98–107,139–145` | 式木、規則データ、CrossStoreとの接続、数学の書換え | 既に「汎用書換え器を新設する」必要はない。ただし算術中心の parser と登録順戦略は自然文の読解候補を一意に正当化しない。 |
| `procedure_exec.py:23,54–96,131–150` | 前提・効果・予算・unsupported op の typed refusal | four-op digit addition interpreter。任意コード生成器ではない。前提/効果を明示する契約を再利用する。 |
| `intent_chain.py:73–109,157–181` | 次段が前段の finding に依存する受渡し | 外部 action workflow。document query execution と同じものに見立てない。 |
| `proof_ledger.py:35–108` | lemma/trial/未証明目標と出所の記録 | 台帳は証明器ではない。保存された status を QA の根拠検証と混同しない。 |
| `code_compose.py:146–494` | 言語 backend、構文検査、隔離実行、spec interpreter | read_spec の正しさとは別に再利用。入力要件が欠落した spec に対する成功を最終正解にしない。 |
| `realize`/`say`/`compose_frame`/`compose_ja`/`connective_render` | 文法、form/content出所、再読、接続詞の根拠 | 内容計画の代替ではない。style candidate と content proof を型で区別する。 |

`one.py`、`answer.py`、`answer_slots.py`、`code_spec.py`、`code_compose.py`、`abilities.py`、`round3.py` への参照検索では `rewrite_core`、`rewrite_kernel`、`procedure_exec`、`puzzle`、`proof_ledger`、`intent_chain` の直接利用は見つからなかった。この限られた探索から「repo全体に未使用」とは主張しない。

`rule_synthesis.py:1–35,87–125` も確認した。これは極性語の後続パターンを共通接頭辞から導く機構であり、下記の構造合成と同じものではない。規則/語彙の追加を新方式と呼ばないための区別である。

## 候補 A — 節・作用域を保持する意味計画と、根拠結合の実行器

**推奨する第一候補。** 一般 QA と即時文書複雑 QA を最初に対象とし、コードと生成も同じ「原文要求→計画→検証」の接続契約を利用する。これは shared learned model や mixed evidence store の導入ではない。

1. 形態素と既存 Frame/Edge/Stage を候補として受け、構成的な文法の適用で parse forest を作る。候補には原文span、規則出所、節ID、event/entity/value変数、role、polarity、modality、時間、条件、例外、量化、依存辺を保持する。未解釈の要求spanを消して成功扱いにしない。文法規則は文構造の項書換えとして記述し、話題語ごとの分岐へ戻さない。
2. 質問を `Select`、`Bind`、`Join`、`Filter`、`ApplyCondition`、`Except`、`Project`、`Aggregate`、`Compare` などの型付き計画へ変換する。演算の順序は述語・引数の束縛と作用域で決める。主語が未知の場合も typed variable にする。曖昧な計画を全部記録し、根拠で解消できなければ棄権する。
3. 各 sovereign の六腕・面・辺を候補供給に使う。述語と既知roleで capped 後退を引き、未知roleの候補を次段へ渡す。文書追加時はその文書だけの source-bound clause view を即時構築する。全文書を一つの意味票へ束ねない。粒度の異なる層は語彙/表現候補と band に限り、答えの票にしない。
4. 証拠を単なる文章 list でなく、`premise source spans → typed operator → bound answer proposition` の DAG として残す。隣接、共起、route scoreだけで Join/原因/含意を成立させない。条件不明は不明、証拠不在は否定と区別する。
5. 最終 gate は必須出力スロットのすべて、条件/例外、出典の存在、変数の一貫性を検査する。旧 assembler/summary/code/creative 経路を含め、ANSWER の抜け道を作らない。内容の同値類は役割・作用域・値と検証済み変換に基づき、表面文の違いで票を分断しない。異なる answer proposition が同点なら棄権する。

**新規性の境界:** 型付き dataclass、新しい slot、隣接文 join、common predicate lexicon は既存。新しい部分は、意味保存された operator tree、全要求の coverage、証明責務、全回答共通 gate。`rewrite_core` の項/束縛や `verdict.Item` を土台にし、別名の frame engine を新造しない。

**反証可能な計画（まだ実施しない）:** 独立作成の公開開発素材で、内容語を固定しつつ役割交換、条件作用域、否定対象、量化、数量対象、引用/現実、時系列、例外、離れた照応だけを変える対を事前登録する。同義の語順/受動変換では計画が不変、意味変更では計画または判定が変わることを採点する。自然文の正解計画は実装者/そのparserから生成しない。完成前に定めた組合せを丸ごと留め置き、見た grammar template の言い換えだけで合格しない。

計画exact match、意味区別率、全要求充足、cited proposition 正確性、正/誤/棄権を別々に記録する。oracle plan で成功し自然文入力で失敗すれば読解仮説は反証される。正しい計画でも証拠を誤結合するなら実行器仮説は反証される。意味の最小変更へ無反応なら単なる表面分類の延長と判断する。配置/行順の置換で答えが変わる場合も失格。閾値緩和で救済しない。

## 候補 B — 原文要件契約からの型付きプログラム合成

**A の read/constraint 契約に続く第二候補。** `code_spec` の flat list をプログラムの意味だとみなすのを止め、input/output schema、列/変数束縛、出力形、pre/post-condition、順序/副作用条件を持つ contract と、中間値にも型のある AST/DAG を作る。

既存 code parts を型付き演算として登録し、契約の出力型から候補項を構成し、前提充足で枝刈りする。単にテンプレートを文字位置順に連結しない。合成には決定的な予算を設け、予算切れ/未知演算/不明束縛をそれぞれ返す。複数候補の仕様上の同値が確かめられないなら、登録順や短さだけで一つへ決めず棄権する。検査可能な code を生成する責任は Vera 本体に残す。

候補→実行→反例→候補修正を bounded に回す。ただし反例は backend の同じ spec interpreter だけに依存させず、原文から独立に作られた contract例、必須制約、型/効果検査で候補を排除する。実行成功は code→contract を、要件spanの充足は contract→request を検査する。小規模構造から始めても、表/文字列/日付等をすべて永久拒否する狭い製品目標に変えない。追加する場合は新しい型付き演算とその普遍的契約として追加する。

**新規性の境界:** 閉じた parts、Specification、実行検査、reference interpreter は既存。差は明示的な中間型/束縛、依存による合成、要件の完全性、反例による候補除去。汎用 rewrite/Procedure を再発明しない。

**反証可能な計画（まだ実施しない）:** backend が既に扱う primitive の数を固定し、未観測の演算順序・nested condition・出力構造・field名・非可換 chainを独立に作成する。三つを分離する: (i) gold contract→synthesis、(ii)自然文→contract、(iii)自然文→最終code。外部oracleで境界値、異なる列の同時存在、列の値を独立に変える入力、重複・空・順序・不変性を確認する。現行 `samples` のように複数 numeric fieldへ同じvalueを入れるケースだけにしない（`code_compose.py:123–127`）。

同じ primitive set と同じ budget で未見構成が改善せず、語彙/テンプレート追加だけでしか進まないなら合成方式の仮説は棄却する。gold contractで成功して自然文で失敗すれば A の要件読解へ戻す。自生成check通過/外部oracle失敗率も正答率と別に出す。実行verifiedという名称だけで正答へ数えない。

## 候補 C — 状態と談話制約を持つ内容計画からの文章構成

**A/B の共通契約が成立してからの第三候補。** 既存 creative retrieval/再読器は残し、生成の単位を「次に使える文」から「要求を満たす出来事/談話計画」へ変更する。

計画は、参加者、対象の所有/位置/性質、出来事の前後、発話者/聞き手/意図、文数・視点・時制・語調・韻律の要求を含む。条件的な常識規則は前提が成立したときだけ適用する。比喩は source/target の対応roleと転移する属性を明示し、両者が似た語を含むだけで解釈を作らない。冗談は二つの読みと転換点を計画で残す。物語は各 event の前提/効果を更新し、全体の状態矛盾と要求未達を拒否する。俳句は既存 mora counterを利用して、三句を共同で探索する。

実世界の主張には出典命題を要求し、ユーザーの創作依頼から導入する架空の出来事には `fictional` と依頼spanを持たせる。表現用例の出典を「この架空の出来事が実際に起きた証拠」として扱わない。生成候補は独立 sovereign 内で根拠/構文を取得し、内容証明と表現供給を別の型付き段として渡す。現行の fixed prose・作品丸ごと・隣接文列のコピーへ頼らず、計画から realize/compose候補を作り、全文制約を検査する。

**新規性の境界:** scene graph、event transition、haiku constraint_search、reread、writer は既存。差は、新規の event sequenceを計画し、状態と談話制約で全文を検証し、その計画が実際に出力を制御すること。trace の項目追加は方式変更ではない。

**反証可能な計画（まだ実施しない）:** 独立に書いたbriefを、内容/視点/時制/人物/結末/韻律の組合せで留め置く。事実引用型・説明型・依頼文・創作を別採点し、6能力を合算して弱点を隠さない。要求充足、人物/状態整合、文章の理解可能性、比喩対応、冗談の解釈可能性、俳句の韻律/情景、作品の新規構成を独立評価者が判定する。コーパスの長い連続一致を報告し、作品全体の転記を新規構成へ数えない。

同じ素材の再配置に留まり、未見の制約組合せで内容計画を作れない場合はこの仮説を棄却する。mora/局所再読だけ成功して全文の意味が破綻する場合も失敗。sourceがあること、ANSWERを返したこと、創作タグがあることは品質合格にしない。

## 最初の実装単位 — 公開 one.Vera を通る A の縦断試作

本実装前のレビュー対象を、**文書/一般QAの「2つ以上の条件または段階を持つ問い→source-bound意味計画→全要求を満たす答え」**に固定する案を推奨する。単節も同じ経路を通す。任意の自然文を最初から読めるとは約束しない。一方で readerだけを変えて旧ランキングへ渡す試作では、今回の方式仮説を検証できない。

最小の意味契約は、`Entity/Value/Event` 変数、役割つき `Assertion`、節別の polarity/modality、`Condition`/`Exception`、単位つき数量、source span と解釈規則、要求ごとの obligation ID。最小演算は `Bind/Join/Filter/Project/Compare` と、単位の整合する `Sum/Difference`。無制限な推論/再帰は入れず、深さ・候補・ステップの予算を公開する。条件/例外を読み取ったが扱えない場合も、消して単純問へ縮めず typed refusal にする。

新規モジュール名は以下の**提案**であり、作成前に索引を再確認する。すべて既存 runtime に対する将来の変更予定で、今回の監査では未変更。

| モジュール | 最初の責務/変更案 | 完了の証拠 |
| --- | --- | --- |
| 新規 `semantic_ir.py`（仮称） | immutableな節・変数・scope・requirement・proof node。構文型、出典型、answer型を分ける。 | 役割交換/否定移動/条件の掛かり先が型データに残る。原文spanと未解釈spanを直列化できる。 |
| 新規 `semantic_reader.py`（仮称） | 既存 `frames.read_all`、`typed_edges.extract`、`verdict.read_records`、`stage_split` の読みを候補として受け、構成文法による束縛候補と要求の集合へ変換する。 | 正解IRを独立作成した構造対で読解を採点。未解釈の必須条件を持ったままsuccessにしない。 |
| 新規 `semantic_execute.py`（仮称） | typed計画を各sovereignの候補と結合し、proof DAGを作る。`rewrite_core` のmatch/substituteを再利用候補にするが、登録順を答え選択に使わない。 | gold IRから条件/例外/多段結合/数量操作が正しく導出され、矛盾と不足が異なるtyped結果になる。 |
| 新規 `semantic_verify.py`（仮称） | operatorごとの前提、spanの存在、role/units/scope、全obligationの充足とfinal claimsを検査する小さなkernel。 | 役割/値/単位/根拠/条件/要求IDを1つだけ壊したproofをすべて拒否。producerの成功flagを信用しない。 |
| `question.py` | 新計画を `Sourced` な別フィールドとして公開。旧Queryと互換を保ち、旧slotへ平坦化した情報だけを新経路へ戻さない。 | `one.Vera`の返却traceから入力要求と最終束縛を追跡できる。 |
| `one.py`、`answer.py` | 試作を公開 `ask` の明示モードへ接続。既存assemblerは候補供給へ降格し、試作対象で成功バイパスさせない。最終gateの判定を`_finish`へ渡す。 | 個別モジュール直接呼び出しだけでなく、公開 `one.Vera` の文書/一般QA経路から同じgateが必ず走る。 |
| `evidence_library.py`/`base.py`のadapter | 現行候補取得をまず再利用し、取得文をsource-bound clausesへ変換する。必要時のみ既存role key/述語keyへ段階照会。初回は既存corpus/indexを再構築しない。 | query budget、候補上限、source/familyと経路が記録される。候補なしを理解不可能と混同しない。 |
| `realize.py`/`connective_render.py`へのadapter | verified claim/planだけを表面化。最初は必要な値と根拠を簡潔に返す。 | 返却textの全claimがproof nodeに結び、必要な複数答えを欠かさない。 |

即時文書QAでは新しい文書のsafeな部分をload時に節化し、文書ローカルのviewを作る。学習や既存世界知識の一括再構築を必要としない。parse/load時間も回答latencyと別に測る。一般QAは現行索引のrecall限界が残るため、oracle evidence供給と現行retrievalを分けて測定し、意味実行器の成功を検索recallの成功にすり替えない。

この縦断試作にB/Cを含めて完了したとは扱わない。Bでは次に `code_spec.py` をraw request→contract adapterへ、`code_compose.py`をtyped plan→backend/executionへ分けて接続する。関数名だけでなく引数名/個数/返却形/副作用という要求インターフェースをobligationとして検査する。Cでは `abilities.py` の選文をcontent planの提案にし、全文状態/談話制約を検査してから既存realizerへ渡す。4群すべての目的は維持し、Aの成功をRound5全能力の成功と呼ばない。

未解決の研究課題は、自由な日本語の構成文法coverage、複雑な照応と省略、語義曖昧性、量化/反実仮想/談話意図、世界知識の不足、freshnessの根拠、任意プログラムの仕様読解と完全検証、比喩/冗談の人間的品質、新規物語の一貫性、bounded検索下のrecall/latencyである。小規模parser変更から全能力の獲得を約束しない。

## 開発検証と新封印の境界

- **今回:** コード読解とこの文書だけ。独立再照合完了後も、本実装の起動前に親が本案をレビューする。現在の評価成果物は修正しない。
- **開発検証:** 正式事前登録後、独立に作成した公開開発素材/構造対/契約を用いる。過去のspent資料を使う場合は回帰に限り、新方式の汎化証明に数えない。金標IRを渡したkernel試験、reader試験、現行索引のretrieval試験、公開 `one.Vera` end-to-endを別欄にする。自己生成の検査で自然文理解を証明しない。
- **方式差の固定:** 「同じparser＋厳しいgateだけ」「AのIR＋gold evidence」「A＋現行retrieval」の比較を事前登録し、情報保存と導出構造が実際に増えたかを確認する。基準runtimeは凍結snapshotとし、同じ4群の停止済み封印を繰り返し使わない。性能目標/合格基準は測定前に別途確定する。
- **新封印:** 設計・runtime・コーパス・索引・entrypoint・環境・採点方法・ハッシュを固定してから、独立担当者が作成/保持する新問題で4群を一度評価する。sealed5/Pro heldoutは引き続き実装者から隔離。最終出力の正しさは人間の独立採点を含め、ANSWER率/キーワード率/実行check成功率に置き換えない。
- **不合格時:** 単なる語彙/regex/閾値追加で直近封印を再試験しない。反証された層と残った仮説を文書化し、次の方式決定へ戻る。誤答をすべて棄権へ変えただけでも目標達成とはしない。

## 順序と判断の止め方

1. **独立再照合済みsnapshotを基準として確保する。** 親から最終ハッシュ一致と固定解除の連絡を受領済み。今回は引き続き調査/設計のみで、起動前に親が文書をレビューする。sealed5/Pro heldout の個別内容から設計を逆算しない。
2. **実装前の事前登録を固定する。** A/B/Cで何が既存と異なるか、期待する構造的能力、必要素材、operator grammar、budget、採点、棄却条件を記す。ここに記した検証は候補案であり、正式な事前登録の代わりではない。
3. **Aを縦に一本作る。** natural request→plan→独立文書/QA候補→proof→answer を通し、役割/作用域の情報が段間で失われないことを公開開発素材で確認する。全経路を一度に書き換えないが、評価対象の経路には最終gateを迂回させない。既存と同じ入力/データで構造差を比較する。
4. **Bを同じ契約に接続する。** gold contractと自然文を分けて測り、読解の誤りをbackend修正で隠さない。部品追加なしの未見組合せで、方式差があるかを先に確認する。
5. **Cを接続する。** 文単位の往復と全文計画の妥当性を別に確認し、6能力それぞれの品質を記録する。一般 QA/コード/文書の改善を理由に生成目標を消さない。
6. **新方式の固定後に、独立担当者が新しい封印評価を一度行う。** 4群の正/誤/棄権、出典完全性、injection、end-to-end median/p95、即時文書ingest時間、各sovereignの候補数/cap、予算棄権を分けて報告する。A/B/Cの失敗箇所をtraceで診断できる状態にする。原則/契約違反が出たら品質合格としない。fresh結果が未達なら語彙/閾値修正で同じ問題を再試験せず、仮説を改める。

実装担当モデルは今後 `gpt-6.1-sol`、reasoning `max`、fastなし。親の確認では、既定configにpriorityがあるため、既定設定を読み込まずfast指定なしのCLI起動が必要。コーパス担当は `luna`、`low`、fastというユーザー指定を保持する。ただし運用担当のモデル指定は、Vera runtimeでLLMを使う許可を意味しない。

この監査が確認したのは、新方式を必要とする表現・検証契約の不足と、再利用可能な既存資産である。上記三候補の正答率・速度・一般化はすべて未検証の設計仮説であり、達成を予告しない。
