# 初期搭載の層と階段（W12-c1）— 冷たい出発を初期コーパスで緩和し、Vera 単体で配れる「汎用の既定」を作る

状態: 設計と試作。本番の配布物は次のチケット。基点 `dev` = `5e7df09`。設計の前提: `ops/decisions/2026-10-04_VERA_BASE_V1.md` §5・§7、`docs/COARSE_PLACEMENT.md` §12.19（層）、`verantyx/granularity.py`・`hierarchy.py`・`stacked.py`・`placement.py` の docstring（vera1 の部品。呼ぶだけで直さない）。

第 3 ラウンドの裁定（2026-10-05 14:58:08 +0900、監査役）: 配布物としての初期層は採らない。語彙層・法令層は `build/initial-layers`（.gitignore）に残し、統合するのは builder と測定の道具と、この文書（負の結果）だけ。`--no-llm`／`--profile`／`--tier`（`confidence_tiers`）の配線は既定オフ（`--no-llm` を付けたときだけ働く）。

この文書の §1〜§7・§J は **検査データを作る前に** 書いた事前登録（日時は `artifacts/w12-c1/prereg_time.txt` の 1 行目）。数値は **約束** であって測定値ではない。測定値は §M にだけあり、出力ファイルからスクリプトで貼る。

## 1. 目的と構成

配る Vera 単体が初日から持つデータの構成。規則（読解・配置・層の優先）は変えない。データだけを足す。

| 層 | 中身 | 出所 | このチケットで |
|---|---|---|---|
| 基底 | 配置 r9（`content_sha256` が `e58908eb…`、読み取り専用） | jawiki 先頭文＋生成コーパスの分布 | 使うだけ |
| 語彙層 | 「文に使える語」の集合。独立出現 ≥3 の語だけ（K401） | jawiki（`human`）、生成コーパス heldout（`generated`） | 作る（`vocab`） |
| 分野層 | 分野ごとに分離した配置の層（W10-f05 の層の形）。法令・行政・一般の 3 つを設計 | 生成コーパス `general_qa` の scene 別の行 | **法令だけ作る**。行政＝`conversation` の scene `役所の窓口／*`（設計のみ・作らない）。一般＝**未定義**（どの scene を一般とするかをこのチケットでは決めない） |
| 利用者の層 | 利用者の文書から育てる層（W10-f05 の層そのもの） | 利用者の文書 | 既存の `r4_layer_real.sqlite`（自転車）を結合に使うだけ |

層の並べ方（`hierarchy` の容量則）: 1 ノードの識別語は `CAPACITY = MAX_ARMS × N_FACES = 6 × 4 = 24` 語、必要な深さは `hierarchy._layers_for(V) = ceil(log₆(V / 4))`。V は各層の direct 語数の **実測**（§M に貼る。ここでは値を書かない）。葉は分野で分離し、上位でだけ接続する。どの分野にも降りられない問いは `UNKNOWN_NO_EVIDENCE` で棄権（K402）。

読解器には触れない。`vera.layer`（融合の層 0/1、`decode_grammar.conclude`）は既存の意味のまま上書きしない。初期層の情報は新しい鍵 `vera.initial_layers` に置く。

## 2. 規則（事前登録、§13 K400〜）

チケットの文をそのまま。
- **K400**: 初期層は **データ** で、規則は変えない。層の形は W10-f05 の層（K290: 基底を上書きしない）。
- **K401**: 語彙層の語は独立出現 ≥3（出所の異なる文書）で確認した語だけ。LLM の申告は入れない。
- **K402**: 分野層は分野ごとに分離し、問いは上位で経路づけ（`hierarchy` の容量則）。どの分野にも降りられなければ `UNKNOWN_NO_EVIDENCE` で棄権。
- **K403**: `confidence_tiers` は「何段が同じ答えを出したか」の整数と段の名前。確率に見せない。同点の段は棄権（vera1 の教訓: 同点を決定論で崩すと一致を捏造する）。
- **K404**: 初期層なしの出力は基点と byte 一致。

具体化（K405 以降。中間職の指示書で決めた値。ここで固定する。変えるときは §J に理由を書く）:
- **K405 語彙層の候補**: 文書の中の **単一の字種の極大の連なり**。漢字 2〜8 字、カタカナ（長音 ー を含む）2〜20 字。混ざった字種の語は候補にしない（`OUT_OF_SCOPE_MIXED_SCRIPT` として数えるだけ）。
- **K406 単独出現**: 漢字の語は「前後が漢字でない」極大の連なり（踊り字「々」U+3005 は漢字の連なりに含める。先頭が「々」の連なりは候補にしない）。`granularity.standalone_count` は **import していない**（r1 レビュー M3 で docs と実装の食い違いを直した。逸脱は §J）: builder は極大の連なりを取るので、「々」を含まない文では `standalone_count(w, text) > 0` と同じ集合になる（`tests/test_w12c1_vocab.py::test_runs_of_kanji_equals_standalone_count_on_texts_without_the_mark` が合成の文で確かめる）。カタカナの語は「前後がカタカナ・長音でない」（`standalone_count` の穴を補う builder 側の追加条件。§7）。
- **K407 文書の単位と出所の別**: jawiki は記事（`title`）1 つ＝1 文書、出所の類 `human`。生成コーパスの heldout は `source`（生成の束）1 つ＝1 文書、出所の類 `generated`（`source` が無い行は族名＋行番号を文書にして、その数を報告）。**≥3 は同じ類の中で数える。類をまたいで足さない**（束ねず重ねる）。語の `origin_class` は `human`（jawiki ≥3）／`generated`（heldout ≥3 だけ）／`both`（両方）。jawiki は r9 の素材にも入っているので `in_base_material: true` を付ける。heldout は r9 の素材に入っていない。
- **K408 法令の分野層**: 素材は `$P4/general_qa.db` の `scene='法律と暮らし'` の行（id を保ったまま写す）。builder を r9 と同じ設定（manifest の `config`）・同じ holdout・同じ exclude-terms で、**jawiki 全量＋この行だけ** で回す。生成の定義・枠・名詞型・役割の枠（`--generated*`・`--role-frames`）は **渡さない**（LLM の申告を入れない）。層に入れる語: 分野の配置で `state=DECIDED` かつ `origin=direct`、かつ `coarse_place.query(word, placement=R9, layer=False)` の state が `UNPLACED`／`UNKNOWN`／`MULTIPLE`。`MULTIPLE` は分野の型が r9 の `top` の中にあるときだけ（外なら `TYPE_NOT_AMONG_BASE_CANDIDATES` として数える）。行は `placement_layer.write_entry`（origin `layer_confirmed`、`decided_by` は分野の配置の `by`、evidence に `{"decision":"builder_domain","model":null,"material_origin":"generated","domain":"law","scene":"法律と暮らし","domain_placement_content_sha256":…,"evidence_rows":[…]}`）。
  - `layer_confirmed` の本来の定義（LLM の申告と分布の一致）とは違う使い方。r9 自身が生成コーパスの分布から direct を出しているのと同じ扱い（素材が生成物であることを evidence の `material_origin: generated` に必ず残す）。判断は §J。
- **K409 対照**: 法令と **同じ行数** の、`法律と暮らし` 以外の `general_qa` の行を `random.Random(20261005).sample(sorted(idの一覧), n)` で取り、同じ手順で「対照の層」を作る（層は作るが配らない）。法令の層の語数が対照と同程度なら「部分集合に絞ったこと自体の効果」と記録する（vera1 の `granularity.control` と同じ論法）。
- **K410 段（tier）**: 段は順に `base`（r9 だけ）→ `vocab`（語彙層）→ `law`（r9＋法令層）→ `law+user`（r9＋法令層と利用者の層の結合）。`vocab` は今の読解器が読まないので **常に `NOT_CONSULTED_BY_READER` で、一致に数えない**（数えると構成上の一致を捏造する）。`law`・`law+user` は、その段の層の direct 語のどれかが問いか文書の文字列に現れるときだけ `ROUTED`、現れなければ `NOT_ROUTED`（型 `UNKNOWN_NO_EVIDENCE`、K402）で一致に数えない。利用者の層が無い文書では `law+user` は `NOT_AVAILABLE`。
- **K411 署名と一致**: 段の答えの署名 = (結果の型〔outcome〕, 値の並び〔あれば sorted、無ければ本文〕)。`confidence_tiers = {"agree": 整数, "counted": 整数, "tiers": [{"name","status","signature"…}], "shown_tier": 名前}`。`agree` = 数えた段のうち、示す答え（数えた段のうち最後の段の答え）と署名が同じ段の数（base は常に数える）。**数えた段に ANSWER が 2 種類以上あれば `--profile strict` では `TIERS_CONFLICT` で棄権**（どちらかを選ばない。同点の崩しをしない）。UNKNOWN→ANSWER の違いは「層で読めるようになった」なので衝突にしない（ただし `agree` には数えない）。
  - **第 3 ラウンドの明確化（K403 の意図の明確化。規則の変更ではない。監査役の裁定）**: `agree` は答えた段（ANSWER）のうち示す答えと署名が同じ段の数。棄権どうしの一致は数えない。示す答えが棄権、または `TIERS_CONFLICT` なら `agree = 0`。`answered`（答えた段の数）を足し、`schema` を `verantyx.confidence_tiers/2` に上げた。上の文の「数えた段のうち…署名が同じ段の数」は r2 までの定義（`/1`）。
- **K412 `--profile assume`**: 仮定の読み（W3-e3）が未実装のあいだは、strict と同じ答えを返し、`vera.assumptions = []`、`vera.assumptions_status = "NOT_WIRED_UNTIL_W3-e3"` を必ず付ける（黙って strict と同じにしない）。
- **K413 `serve --no-llm`**: LLM を一度も呼ばない。記録で答えられる（`QUESTION_CROSS`）ときだけ記録の文を出し、それ以外は型つきの固定文で棄権。`--backend`・`--model`・`--strict`・`--free`・`--fill` との併用は型つきで拒否（`NO_LLM_WITH_BACKEND` など）。`--profile`・`--tier` は `--no-llm` なしでは拒否（既定の serve を変えないため）。`vera.layer` は上書きしない。初期層の情報は新しい鍵 `vera.initial_layers`（段ごとの名前・spec・sha256・base sha）に置き、`vera.confidence_tiers`・`vera.assumptions`・`vera.assumptions_status`・`vera.no_llm: true` を足す。
- **K414 X5 の 50 問**: 自転車 30＋陶芸 15＋W10-f01 の `questions.jsonl` の factual から `random.Random(20261005).sample(sorted(id), 5)`。正答の判定規則は下の K415 に書いてから凍結する。
- **K415 正答の判定（採点器 `artifacts/w12-c1/scripts/score_tiers.py`）**: 答えありの問いは「結果が ANSWER 系（`vera.outcome.outcome` が `ANSWER_HUMAN_BASIS`／`ANSWER_FORM_FROM_GENERATED`／`REFERENCE_GENERATED`）かつ 期待の値が構造化された値（`vera.reading.filler`。無ければ本文）に含まれ、期待にない値が無い」なら正答。答えなしの問い（`expect` が `ABSTAIN`）は「棄権（ANSWER 系でない）」が正答。それ以外の ANSWER 系は誤答。ANSWER 系でない出力は棄権。W10-f01 の `truth` は `{"kind":"ONE","filler":F}` → `expect={"verdict":"ANSWER","values":[F]}`、`{"kind":"NONE"}` → `expect="ABSTAIN"` に写す。
- **K416 `confidence_tiers` の単調性（X5）**: 段の一致数（`agree`）ごとの正答率が、`agree` が大きいほど下がらないこと。単調でなくても段の構成を変えない。ほとんどが `agree=1` なら、そのまま書く。
- **K417 整合の門**: 各問い・各段の答えを、同一プロセス（段の環境を切り替える）と、段ごとの別プロセスで出し、`vera.timing` を除いて byte 一致すること。1 件でも違えば、serve の `confidence_tiers` は `{"status":"UNAVAILABLE_IN_PROCESS"}` を返す形に倒し、X5 の数は別プロセスの方で出す。

## 3. 仮定の不変性ゲート（W3-e2 → W3-e3 への申し送り。規則の事前登録だけ、実装なし）

段 E2（仮定つきの読み）の採用条件に次を足す:
- 仮定つきの読みは、**同じ証拠で並ぶ別の仮定（同点の崩し方）のすべて** に替えても十字が変わらないときだけ採用する。変われば `ASSUMPTION_UNDETERMINED` で棄権する。
- 論法: vera1 の配置の不変性（`placement.py`・`metamorphic.py` の docstring）。「配置は情報を増やせない」: 同点の崩し方を変えると消える答えは根拠ではなく読み方の産物。`CLAUDE.md` の実測 73.3% → 23.7%（同点を辞書順で崩したとき、すべての段が最小の項目を選んで一致が 86 → 321 問に増え、正答率が落ちた）。決定論の同点崩しは一致を捏造する。
- 出典の別: 仮定の出所は `attested_human` を先に、`attested_generated` は別の型として申告して合算しない。
- 実装は W3-e3（W3-e2 の後）。このチケットは docs に規則を置くだけ。

## 4. 粒度の階段を未知語の出所に（W3-e3 への申し送り、実装なし）

名前・造語を 2 字／1 字の段で見て、既知の形態素と繋がるかを、仮定の出所 **(d')** として扱う。
- 手続き: `granularity.decompose(words, length=2)`／`granularity.propose` の位置の統計（`CharModel`）で、未知語の連続する 2 字・1 字が、既知語の中の同じ位置に現れるか。独立の確認は `granularity.verify` と同じ基準（保留コーパスの独立出現 `MIN_STANDALONE`=3）。
- 型（事前登録）: 繋がったとき `ASSUMPTION_SOURCE_D_PRIME`（仮定の出所の型。確定ではない）、繋がらないとき `UNKNOWN_NO_EVIDENCE`。形の例: カタカナ列の人名の形、カタカナ＋活用語尾（ザクる ← ザク？）。
- 対照: 同じ字の無作為な組み合わせ（`granularity.control`）を必ず並べる。対照と同程度なら「形の効果」と書き、出所と呼ばない。
- 採用は §3 の不変性ゲートを通ったときだけ。実装は W3-e3。

## 5. 知識量の階段 `confidence_tiers`（K403・K410・K411）

- 段: `base` → `vocab` → `law` → `law+user`（K410）。各段は `{"name", "status", "signature"}` を持つ。`status` は `COUNTED`／`NOT_CONSULTED_BY_READER`（vocab）／`NOT_ROUTED`／`NOT_AVAILABLE`。
- 数える段: `COUNTED` の段だけ。`NOT_CONSULTED_BY_READER`・`NOT_ROUTED`・`NOT_AVAILABLE` は一致に数えない。
- 第 3 ラウンドの定義: `agree` = 答えた段のうち示す答えと署名が同じ段の数（棄権どうしの一致は数えない。示すのが棄権、または衝突なら 0）、`answered` = 答えた段の数、`counted` = 数えた段の数。`agree`・`answered`・`counted` はすべて整数。
- `agree`・`counted` は整数。**確率・割合の形の欄（`prob`・`confidence`・`score`・小数）を作らない。**
- 同点: 数えた段に ANSWER が 2 種類以上あるときは選ばず `TIERS_CONFLICT`（strict）。辞書順・順序・ハッシュで答えを選ばない。
- 逆向き（base が ANSWER で後の段が棄権）のときは、示すのは最後の段の棄権になる（保守側。r1 O4）。UNKNOWN→ANSWER（K411）と対称には扱っていない。
- `in_base_material`（語彙層）は **jawiki で 3 文書以上** のときだけ true。jawiki に 1〜2 文書だけ出る語も r9 の素材には入っているが、語彙層はそれを「素材にある」とは数えない（r1 O5。名前は紛らわしいが、データの欄名なので変えていない）。
- 段の経路づけ（`ROUTED`）は、その段の層の direct 語が問いか文書の文字列に現れるかで決める（`hierarchy` の「降りられない＝棄権」の最小の形）。

## 6. `serve --no-llm` の契約

- 起動: `vera serve --no-llm [--profile strict|assume] [--tier NAME=SPEC ...] [--document f ...] [--layer L] [--placement P]`。LLM を一度も呼ばない（`vera.llm.called` は常に false）。
- 応答（OpenAI 互換・Ollama 互換の本文は既存のまま）の `vera` 欄: `no_llm: true`、`confidence_tiers`、`assumptions`（`[]`）、`assumptions_status`（`assume` のとき `NOT_WIRED_UNTIL_W3-e3`）、`initial_layers`（段ごとの名前・spec・sha256・base sha）。`vera.layer`（融合の層 0/1）は既存の意味のまま。
- 型つきの棄権: `decode_grammar.conclude` は `FIXED_TEXT[reading["type"]]` を引くので、`RECORDS` など表に無い型を渡すと KeyError になる。`decode_grammar` は触れないので vera_server の側で型を写す:

| plan_turn の読みの型 | no-llm の固定文の型 | 備考 |
|---|---|---|
| `QUESTION_CROSS` | （記録の文を出す。固定文なし） | 記録の出所を方針に通す（既存） |
| `NO_RECORD` | `NO_RECORD` | そのまま |
| `STRUCTURE_UNDETERMINED` | `STRUCTURE_UNDETERMINED` | そのまま |
| `RECORDS`（非 factual） | `ABSTAIN` | `vera.reading.type` は元の `RECORDS` のまま、`vera.no_llm_fixed_as` に写した型を残す |

- 拒否: `--no-llm` と `--backend`・`--model`・`--strict`・`--free`・`--fill` の併用は `NO_LLM_WITH_BACKEND` など型つき。`--profile`・`--tier` は `--no-llm` なしでは `PROFILE_NEEDS_NO_LLM`／`TIER_NEEDS_NO_LLM`。

## 7. 部品の既知の穴（直さない。ここに書くだけ）

- `granularity.verify` は `top` に **40 語しか返さない**。語彙層の全数には使わない。数えるのは builder の極大の連なり（`々` を含まない文では `standalone_count(w, text) > 0` と同じ集合。K406）で、`standalone_count` は呼んでいない。
- `granularity._KANJI` と `standalone_count` の漢字の範囲に **踊り字「々」（U+3005）が無い**: `代々木公園` が `々` で切れて `木公園` が単独出現と数えられる（r1 レビュー M2。旧版の語彙層に `木公園`・`木上原`・`木駅`・`意気揚`・`筋骨隆` などの断片が入り、`佐々木`・`代々木`・`人々`・`様々` が無かった）。builder は踊り字を漢字の連なりに含める（部品は直さない）。
- 「の」「ノ」「ツ」「ヶ」で区切られる地名（`鵜の木駅`・`柿ノ木駅`・`四ツ木駅`・`霞ヶ関`・`御茶ノ水`）は、区切りの前後が別の連なりになり、断片（`木駅`・`丘駅`・`千代田区霞` など）が候補になる。K405 の設計の限界で、直していない（r1 O6。`木駅` は新版にも human 12 文書で残る: 原因は `の`／`ノ`／`ツ` の前に切れた連なり、`々` ではない）。
- `granularity.standalone_count` の挟みの判定は **漢字だけ**。カタカナ語は前後がカタカナでも「単独」と数える（`リング` は `チェーンリング` の中でも数えられる）。K406 で builder 側に追加条件を置く。
- 層（`placement_layer`）は 1 つの SQLite で、`VERA_PLACEMENT_LAYER` で **1 つだけ** 指定できる。複数の層は `combine` で新しい層に写す（`write_entry` 経由。台帳の鎖が切れるので sqlite に直接 INSERT しない）。
- `FusionConfig(layer=…)` は環境変数を書き、別値があると `LAYER_ENV_CONFLICT`。段ごとの config は layer=None で、環境変数を段の値にした状態で作る。
- 語彙層の語は今の読解器が読まない（`NOT_CONSULTED_BY_READER`）。読解器が使う線は W3-e2/W3-e3。
- **台帳の追記は O(n²)**（`TestimonyLedger` / `ChoiceLedger`）: 追記のたびに台帳全体を読み直して検証し、manifest を書き直し、`store_id` の参照（`write_entry` が行ごとに 2 回）も全体検証になる。層に 1 万行以上を書くと現実的でない（途中で止めた最初の実行の観測: 約 100 秒で 1,229 行、その時点の速度は行数が増えるほど落ちていた。残してある `build/initial-layers/law/ledger_partial_aborted_o_n2.jsonl` の行数と、`build/initial-layers/law/domain_layer.log` の時刻にあたる）。`placement_layer.growth` も `ledger.store_id` を **層の行ごとに** 引くので同じ。直せない（`llm_choice.py`・`testimony_ledger.py`・`placement_layer.py` は許可パス外）ので、builder に `bulk_ledger`（鎖・manifest を同じ関数 `_chain_hash`・`_canonical`・`row_content_sha256` で作り、抜けるときに標準の `verify()` で全体を検証する。標準の追記と byte 一致することを `tests/test_w12c1_domain.py` で確認）と `CachedLedgerView`（growth 用の 1 回検証の読み取り窓）を置いた。本体の直しは別チケット。
- `placement_layer.write_entry` は行ごとに SQLite 接続を開いて commit する。macOS では commit が全 fsync で行あたり約 50 ms。builder の `fast_layer_writes` が書き込み中だけ `synchronous=OFF` にする（作り直すだけの成果物。行の中身は同じ）。
- 層に書く語は `write_entry` が NFKC に正規化するが、builder の見出し語は全角記号（`＝` など）を含むものが NFKC でない。`plan_domain_layer` が NFKC に直して重複を `DUPLICATE_AFTER_NFKC` として数える。
- SQLite 接続は作ったスレッドでしか使えず、配置と層の接続はプロセス全体のキャッシュにある。複数の `TierRunner` を 1 つのプロセスで作るとき（測定スクリプト）は同じ単一スレッドの pool を渡す（`TierRunner(pool=...)`）。製品の serve は runner 1 つ。
- 生成コーパスの `figurative_commonsense`（pun／simile_metaphor／haiku／cause_effect）と `paraphrase_entail`（pair／who_did_what）は種類ごとに欄が違う。最初の版は欄の一覧が足りず 49,203 行が読めなかった（`artifacts/w12-c1/x2_vocab_pass1.json`）。欄の一覧を足して作り直した（§J）。

## M. 測定（出力ファイルから `artifacts/w12-c1/scripts/paste_m.py` が貼った。手で写していない）

読み方の注意: 目視の表は正解データではない（実装役が見た判断）。数値の出所はそれぞれの出力ファイル（括弧内、`artifacts/w12-c1/` の下）。

### X1 初期層なしの出力は基点（`5e7df09`）と byte 一致（K404）
```
# x1_entry.txt
rows 4149
rows 4149
entry none SAME (    4149 lines, sha256 ee11a83425a3b890)
rows 4149
rows 4149
entry r9 SAME (    4149 lines, sha256 2a28316f96fb64d6)
# x1_serve.txt
310 /private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W12-c1-impl/x1/serve_base.jsonl
     310 /private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W12-c1-impl/x1/serve_new.jsonl
     620 total
SERVE SAME
# x1_query.txt
rows 1766903 overall_sha256 4ab15ee846e5db5d906d12f973cda6100567d8065009f13787c4550156a4e3f1 sec 288.5
rows 1766903 overall_sha256 4ab15ee846e5db5d906d12f973cda6100567d8065009f13787c4550156a4e3f1 sec 291.5
r9 SAME
```

### X2 語彙層（`x2_vocab.json`、`x2_sample60.tsv`）
- 候補（極大の単一字種の連なり、文書内の集合）: jawiki 異なり 1905843、生成 heldout 異なり 107202、合併 1962138。
- 語彙層の語数（独立出現 ≥3、類をまたいで足さない）: 合計 **372054**、`origin_class` 別 {"both": 20075, "generated": 14905, "human": 337074}、字種別 {"both/kanji": 16746, "both/katakana": 3329, "generated/kanji": 14212, "generated/katakana": 693, "human/kanji": 226681, "human/katakana": 110393}。
- `OUT_OF_SCOPE_MIXED_SCRIPT`（混ざった字種。数えるだけ）: 異なり jawiki 631823、生成 35203、合併 660861。
- r9 の UNPLACED 750572・MULTIPLE 5964 のうち語彙層で確認できた語: **216217**（状態×類別 {"MULTIPLE/both": 1511, "MULTIPLE/generated": 93, "MULTIPLE/human": 524, "UNPLACED/both": 7166, "UNPLACED/generated": 8761, "UNPLACED/human": 198162}）。語彙層は「文に使える語である」ことの確認で、型は付けない。
- 文書: jawiki 1501518 記事、生成 heldout {"code": {"documents": 469, "rows": 73642, "rows_unreadable": 0, "rows_without_source": 0}, "code_qa": {"documents": 1636, "rows": 34523, "rows_unreadable": 0, "rows_without_source": 0}, "conversation": {"documents": 1662, "rows": 159676, "rows_unreadable": 0, "rows_without_source": 0}, "figurative_commonsense": {"documents": 473, "rows": 25074, "rows_unreadable": 0, "rows_without_source": 0}, "general_qa": {"documents": 526, "rows": 34171, "rows_unreadable": 0, "rows_without_source": 0}, "narrative": {"documents": 786, "rows": 18193, "rows_unreadable": 0, "rows_without_source": 0}, "paraphrase_entail": {"documents": 880, "rows": 43544, "rows_unreadable": 0, "rows_without_source": 0}}。読めなかった行: {"generated": {}, "jawiki": {"REDIRECT_NO_TEXT": 953955}}。
- 処理: {"generated": 7.1, "jawiki": 23.6, "total": 34.2} 秒（`/usr/bin/time -l` の出力は `build/initial-layers/vocab/build.log`）。出力 14925824 bytes、sha256 `f808465b3cd451c3ac872a2d3710cce81dd5fd1f2c526403bbbce43237c59048`。
- 目視 60 語（r9 の UNPLACED／MULTIPLE ∩ 語彙層から `random.Random(20261005)`）: {"疑わしい": 18, "語": 42}（語＝語・名、断片＝長い語の途中、疑わしい＝句・不明）。**正解データではない。**
- 最初の版（pass1、欄の一覧が足りなかった）: 語数 370666、読めなかった行 {"generated": {"NO_READABLE_FIELD:figurative_commonsense": 19418, "NO_READABLE_FIELD:paraphrase_entail": 29785}, "jawiki": {"NO_TITLE_OR_TEXT": 953955}}（`x2_vocab_pass1.json`。§J）。
- **r2（レビュー M2 の直し）**: 旧版（踊り「々」が漢字の連なりに入っていない。`x2_vocab_v1_iter_unfixed.json`・`x2_sample60_v1_iter_unfixed.tsv`・`build/initial-layers/vocab/vocab_v1_iter_unfixed.sqlite`）は語数 371917、r9 の未決定のうち確認できた語 216079。直した版（上の数値）は語数 372054、確認できた語 216217。内訳・確認語は `x2_m2_counts.txt` と `x2_m2_check_words.txt`（`sqlite3 -readonly` の出力）:
```
v1_iter_unfixed words 371917 with_iteration_mark 0 confirmed_r9_undecided 216079 confirmed_r9_undecided_with_mark 0
v2_iter_fixed words 372054 with_iteration_mark 460 confirmed_r9_undecided 216217 confirmed_r9_undecided_with_mark 177
check words v1: ['意気揚', '木上原', '木公園', '木駅', '筋骨隆']
check words v2: ['人々', '代々木', '佐々木', '木駅', '様々']
# x2_m2_check_words.txt（直した版。word|docs_human|origin_class。レビューの確認の SQL の出力）
人々|3316|both
代々木|144|human
佐々木|1069|both
木駅|12|human
様々|5461|human
```
  `木駅`（human 12 文書）は直した版にも残る: 原因は `鵜の木駅`・`柿ノ木駅`・`四ツ木駅` など「の・ノ・ツ」で切れた連なり（`grep -a` で jawiki の文脈を確認）で、踊り字ではない（§7、O6。直していない）。
  目視 60 語は直した版から引き直した（語 42・疑わしい 18・断片 0。判定基準を旧版より厳しくした: 複合の句・語の一部かもしれないものは疑わしいにした。旧版の表と数は比べられない）。

### X3 法令の分野層（builder の経路。LLM なし、`x3_law_k1.json`・`x3_law_k2.json`、`x3_sample60_k1.tsv`・`x3_sample60_k2.tsv`）
| | 最初の版（r9 の設定、`def_min`=`alias_min`=`paren_alias_min`=1） | 直した版（閾値 2。**以後の測定はこちら**） |
|---|---|---|
| 素材（`法律と暮らし` の行） | 9694 行（sha256 `3578135955d9…`） | 9694 行（sha256 `3578135955d9…`） |
| 分野の配置の DECIDED/direct 語 | 995838 | 23487 |
| **層の direct 語数（法令）** | 16748 | 495 |
| 対照（同じ行数のランダム）の層の direct 語数 | 16805 | 498 |
| 層に書かなかった理由別（法令） | {"BASE_DECIDED": 979070, "DUPLICATE_AFTER_NFKC": 8, "TYPE_NOT_AMONG_BASE_CANDIDATES": 12} | {"BASE_DECIDED": 22984, "TYPE_NOT_AMONG_BASE_CANDIDATES": 8} |
| 台帳の鎖（chain_ok）・`promoted_to_layer` 行 | True・16748 | True・495 |
| `hierarchy._layers_for(V)`（V＝direct 語数、CAPACITY=24） | 5 | 3 |
| builder の秒・最大 RSS | 311.05 秒・11.2 GB | 84.17 秒・6.5 GB |
| 目視 60 語（正しい／疑わしい／誤り） | {"正しい": 33, "疑わしい": 12, "誤り": 15} | {"正しい": 45, "疑わしい": 11, "誤り": 4} |

- 誤りの割合: 最初の版 15/60、直した版 4/60。基準（1 割以下）に対し、最初の版は超え、直した版は届いた。**目視は正解データではない。**
- O10 目視の誤り: 実装役 4/60、r1 の中間職の独立判定 6/60（10.0%、境界上。出所: 中間職のレビュー r1）。
- 層の direct 語はすべて `layer_confirmed`（`material_origin: generated`、`model: null`）。基底（r9）が DECIDED の語は書いていない（K290）。層の `base_content_sha256` は r9 の `e58908eb4eba8820fed9eafcd1ff42a5a70cdfdf4c35a9646b5dd49aaa002a21`。
- 法令と対照の層の大きさがほぼ同じ（直した版 495 対 498）: 素材を部分集合に絞ったこと自体の効果で、法令の知識が増えたとは言えない（K409、§J）。
- 結合の層（法令の層＋自転車の利用者の層、`x4_combine_law_bicycle.json`）: {"sources": {"law_k2": 495, "r4_layer_real": 68}, "words": {"conflict": 0, "direct": 498, "estimated": 61, "human": 0}, "conflict_words": []}
- 法令の層と対照の層の重なり（r1 O1。`x3_overlap_law_control.txt`、直した版）: 法令の層 495 行のうち **469 行** が対照の層と (語, 型) で一致する。大きさが同じことより強い事実で、分野の内容を捉えた層ではない。


### X4 冷たい出発（`x4_score.txt`、`x4_qa_*.jsonl`、`x4_why_not_gained_*.txt`）
`ask --mode round5`（W10-f05 と同じ経路）。`--layer none` と `--layer <直した版の法令の層>`（自転車は結合の層も）。**誤答は全ての走行で 0**。
| 文書 | 層 | 正答 | 誤答 | 棄権（答えあり／答えなし） |
|---|---|---|---|---|
| 自転車（30 問） | none | 8 | 0 | 12／10 |
| 自転車（30 問） | law（直した版） | 8 | 0 | 12／10 |
| 自転車（30 問） | law＋自転車の利用者の層（結合） | 8 | 0 | 12／10 |
| 陶芸（15 問） | none | 10 | 0 | 0／5 |
| 陶芸（15 問） | law（直した版） | 10 | 0 | 0／5 |

陶芸は答えありの 10 問がすべて基底（r9）だけで既に正答（`ALREADY_CORRECT`）で、増える余地が無かった。自転車の増分は 0（法令の層も結合の層も）。

`why_not_gained.py` の型（r2: 誤答の型を足した）: GAINED／ALREADY_CORRECT／LAYER_WORD_NOT_IN_QUESTION／LAYER_NO_DIRECT／READER_NOT_REACHED と、誤答は **最優先で** WRONG_WITHOUT_LAYER／WRONG_WITH_LAYER／WRONG_BOTH（答えなしの問いに答えた場合も。判定は `score_qa.py` と同じ）。合成の入力での確認は `m4_synthetic/output.txt`（WRONG_BOTH 1・WRONG_WITHOUT_LAYER 1・GAINED 1）。足した後の自転車（法令層）の再実行の 1 行目は `m4_rerun_x4_bicycle_law.txt`（`wrong` 0、型の数は前と同じ）。

増えなかった理由の型（`why_not_gained.py`。法令の層、`routed` ＝法令層の direct 語が問いか該当文に現れた、答えありの問いの数）:
- `x4_why_not_gained_bicycle.txt`: {"counts": {"READER_NOT_REACHED": 2, "LAYER_WORD_NOT_IN_QUESTION": 10, "ALREADY_CORRECT": 8}, "answerable": 20, "routed": 2}
- `x4_why_not_gained_bicycle_combined.txt`: {"counts": {"READER_NOT_REACHED": 5, "ALREADY_CORRECT": 8, "LAYER_WORD_NOT_IN_QUESTION": 1, "LAYER_NO_DIRECT": 6}, "answerable": 20, "routed": 8}
- `x4_why_not_gained_pottery.txt`: {"counts": {"ALREADY_CORRECT": 10}, "answerable": 10, "routed": 0}

### X5 `confidence_tiers`（`x5_tiers.jsonl`、`x5_summary.json`、`x5_consistency.txt`）
50 問（自転車 30＋陶芸 15＋W10-f01 の 5 問）を製品の経路（`serve --no-llm` の `fusion_turn`、段つき）で。正答 6・正しい棄権 17・答えありの棄権 27・**誤答 0**。`vera.llm.called` は全件 false（`llm_called_any` = False）。
| `agree` | 問い | 正答 | 正しい棄権 | 答えありの棄権 | 誤答 | 正しかった割合 |
|---|---|---|---|---|---|---|
| 0 | 44 | 0 | 17 | 27 | 0 | 17/44 |
| 2 | 5 | 5 | 0 | 0 | 0 | 5/5 |
| 3 | 1 | 1 | 0 | 0 | 0 | 1/1 |

- 単調（`agree` が大きいほど下がらない）か: **はい**。段の構成は変えていない（K403・X5）。
- ANSWER を示した問いだけで見ると（`shown_answers_by_agree`）: [{"agree": 2, "answers": 5, "correct": 5, "wrong": 0}, {"agree": 3, "answers": 1, "correct": 1, "wrong": 0}]
- `counted` 別: [{"counted": 2, "questions": 20, "correct": 5, "correct_abstain": 7, "abstained_on_answerable": 8, "wrong": 0}, {"counted": 3, "questions": 30, "correct": 1, "correct_abstain": 10, "abstained_on_answerable": 19, "wrong": 0}]
- 整合の門（同じ段を別プロセスで答えさせて byte 一致、timing 除く）: `CONSISTENCY same=130 different=0 (every question x every base/layer stage; timing removed; a stage answered in a new process with its own variable alone)`
- `TIERS_CONFLICT`: 0 件。
- `answered` 別（`by_answered`）: [{"answered": 0, "questions": 44, "correct": 0, "correct_abstain": 17, "abstained_on_answerable": 27, "wrong": 0}, {"answered": 2, "questions": 5, "correct": 5, "correct_abstain": 0, "abstained_on_answerable": 0, "wrong": 0}, {"answered": 3, "questions": 1, "correct": 1, "correct_abstain": 0, "abstained_on_answerable": 0, "wrong": 0}]
- 第 3 ラウンドの定義（`agree` = 答えた段のうち示す答えと署名が同じ段の数。棄権どうしの一致は数えない。示すのが棄権、または衝突なら 0）での (agree, answered, counted) の組の数え上げ: {"0,0,3": 29, "3,3,3": 1, "0,0,2": 15, "2,2,2": 5}。示す答えが ANSWER の問いは 6 問（outcome から数えた。M7）、`agree == 0` の問いは 44 問。
- 示す答えが ANSWER の問い 6 問のうち `agree == answered == counted` の問い 6 問。示すのが棄権の問い 44 問のうち `agree == 0` は 44 問（outcome から数えた。M7）。
- 旧定義（`/1`、棄権の一致も数える）の出力は `x5_tiers_r2_agree_counts_abstain.jsonl`・`x5_summary_r2_agree_counts_abstain.json`。`x5_r2_vs_r3_agree.txt`: `rows old 50 new 50 same_except_agree_answered_schema_timing 50`（`agree`・`answered`・`schema`・timing を除いて旧出力と同じ）。`x5_consistency.txt` は段ごとの答えの比較で `combine` を通らないため、流し直していない。
- r2: 語彙層を作り直したので X5・X6 を作り直した版の vocab で流し直した。旧版（旧 vocab）の出力は `x5_tiers_v1_vocab.jsonl`・`x5_summary_v1_vocab.json`・`x5_consistency_v1_vocab.txt`・`x6_latency_v1_vocab.json`。X5 の 50 行は vocab の sha256 と timing を除いて旧版と同じ（比較は `x5_v1_vs_v2_vocab.txt`: 50 行すべて一致）。

### X6 `serve --no-llm` の遅延と最小構成（`x6_latency.json`、`x6_http_answer.json`）
in-process（`fusion_turn`、HTTP なし）、50 問×3 回（1 回目は温めで除く）、`vera.timing.vera_ms`。
| 構成 | p50 ms | p95 ms | max ms | 起動〜最初の答え ms（段の読み込み込み） | 最大 RSS（MB） |
|---|---|---|---|---|---|
| base だけ（段なし） | 106.113 | 111.368 | 141.664 | 677.4 | 102.9 |
| base＋法令層＋利用者の層 | 327.909 | 337.286 | 354.411 | 1097.8 | 107.0 |
- 配る物の大きさ（bytes）: {"combined_law_bicycle_sqlite": 430080, "law_layer_sqlite": 278528, "r9_placement_sqlite": 305909760, "vocab_sqlite": 14925824}。
- 「数十 ms 目標」: base だけで p50 が 106.113 ms で **届いていない**（読解器の時間。読解器は触れない約束なので直しに行っていない）。
- 計測時の負荷: `14:16  up 4 days, 13:29, 2 users, load averages: 2.99 3.30 4.28`。
- r2: 語彙層の作り直しの後に X6 も流し直した（旧版 `x6_latency_v1_vocab.json`。負荷 `x6_uptime_before_r2.txt`）。`x6_http_answer.json` は旧版の語彙層（sha256 `31a913dc…`）で立てた 1 回の応答のままで、流し直していない（正式な数ではない）。`x6_http_answer.json` は r2 以前の応答で、`confidence_tiers` も旧定義（`/1`）。
- 実際に 127.0.0.1 で `vera serve --no-llm --tier vocab=… --tier law=…` を立てて POST した 1 回の応答は `x6_http_answer.json`（遅延の正式な数ではない）。

### X8 基線から増えない（`pytest_full.txt`、`pytest_new_failures.txt`）
- 全体（`pytest tests -p no:cacheprovider -q -rfE --tb=no`）: `116 failed, 15946 passed, 38 skipped, 81 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 632.06s (0:10:32)`
- 基線（`dev_bfb17b8_failures.txt`、115 件）との差（`compare_failure_sets.py`）: 基線に無い失敗 **2 件**（`new_failures.txt`）['tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches', 'tests/test_p4_abilities.py::test_speech_act_drafts_fill_new_roles_and_reread']、基線にあって今回は通った 1 件（`fixed_failures.txt`）['tests/test_one_trace.py::test_every_default_integration_part_has_a_trace']。
- 基線に無い失敗の 2 件は、基点の木（`5e7df09` を `git archive` したもの）で単独で流しても **同じく失敗する**（`pytest_new_failures_check_base.txt` と `pytest_new_failures_check_new.txt`）。チケットが環境由来と書いた失敗（`test_s6_…`・`test_p4_abilities::test_speech_act_drafts…`）に当たる。このチケットの差分が原因ではない。
- 最初に `pytest`（引数なし）で流したら `artifacts/` の `test_*.py` の収集エラー 68 件で止まった（`pytest_full_rootcollect_errors.txt`）。W10-f05 と同じく `pytest tests` で流した。
- 新しいテスト（`tests/test_w12c1_*.py`）: `54 passed in 3.16s`。既存の層・融合のテスト（`test_w10f05_*`・`test_serve_fusion`・`test_w10f04_serve`）: `139 passed in 22.36s`。

### X7 中間職の未公開（別分野の文書 1 本と問い 15）
- **読み替え**（監査役の裁定、2026-10-05 14:58:08 +0900）: X7 は「初期層が原因の誤答 0（層なしと層ありで同じ答え）」で判定する。実装役は X7 の入力を見ていない。以下の数の出所は中間職のレビュー r1／r2 の報告（実装役の測定ではない）。
- r1（料理の文書 25 文・問い 15）: 層なしも法令の層ありも `correct 8 wrong 2 abstained 5`。誤答 2 件は期待 `祖母` に対して答え `["祖"]`。
- r2（園芸の文書 19 文・問い 15）: 層なしも法令の層ありも `correct 9 wrong 1 abstained 5`。誤答は期待 `叔父` に対して答え `["叔"]`。
- どちらの誤答も基点 `5e7df09` の木で同じ答えが出る（`ask --mode round5` の経路の切り出しの不具合。r9 の配置は `叔父 DECIDED PERSON`）。層の有無で答えは変わらない → **初期層が原因の誤答 0 で、読み替えた X7 は合格**。基点の誤答は **W3-f1**（監査役が起票）で直す。
- 配る経路（`serve --no-llm`、base＋law）では r1 の 15 問で正答 1・誤答 0、r2 の 15 問で正答 4（`叔父` を含む）・誤答 0、`llm_calls 0`（中間職の参考の測定）。
中間職がレビューで `artifacts/w12-c1/scripts/run_cold_start.sh <doc> <qa> <outdir> [<user layer>]` を新しい文書で走らせる（実装役は見ていない）。

## J. 判断記録

- 2026-10-05 起票。W3-e2 が読解器を並行で変更しているため、このチケットは読解器に触れず、規則の事前登録だけを申し送る。
- 法令のコーパス（e-Gov）は手元に本文が無く、ネットワーク禁止のため、法令の分野層の素材は生成コーパス `general_qa` の scene `法律と暮らし` を使う。生成物なので `material_origin: generated` を evidence に残し、法令の事実の根拠とは呼ばない（K408）。
- `layer_confirmed` を builder の分野の配置の direct 語に使うのは本来の定義の外。r9 自身が生成コーパスの分布から direct を出しているのと同じ扱いで、r9 の上に重ねる範囲に限る（基底が DECIDED の語には効かない、K290）。
- 初期搭載の索引照会（`index search`）は `語彙層 初期搭載` で `UNKNOWN_NOT_FOUND`。`粒度の階段` は既存の `verantyx/resolution.py`（解像度の階）と `granularity.py` が出た。resolution.py は法令条文の見出しの問いでの階の一致の実測で、今回の段（基底・語彙・分野・利用者）は「知識量の階段」で別の構成なので新しく作る。ただし「同点の段は棄権」の論法は再利用（K403）。
- 2026-10-05 語彙層の最初の版（pass1）は、生成コーパスの 2 族で欄の一覧が足りず `NO_READABLE_FIELD` が `figurative_commonsense` 19,418 行・`paraphrase_entail` 29,785 行、jawiki の redirect 行（本文なし）953,955 行が `NO_TITLE_OR_TEXT` に混ざっていた。欄の一覧（`FAMILY_FIELDS`）を足し、redirect を別の理由 `REDIRECT_NO_TEXT` にして作り直した（pass2）。pass1 の出力は `x2_vocab_pass1.json`・`x2_sample60_pass1.tsv`・`build/initial-layers/vocab/vocab_pass1.sqlite` に残す。pass1 と pass2 は **規則（K401・K405〜K407）が同じで入力の読み取り漏れだけが違う**。目視 60 語は pass2 の分布から取った（pass1 の表は目視していない）。
- 2026-10-05 **X3 の直し（閾値を上げる方向だけ）**: 法令の分野層の最初の版（`def_min`=`alias_min`=`paren_alias_min`=1、r9 の設定のまま）は direct 16,748 語（対照 16,805 語）で、目視 60 語（`random.Random(20261004)`）のうち **誤り 15 語（25%）**、疑わしい 12、正しい 33（`x3_sample60_k1.tsv`）。人名が定義文の地名で PLACE になる（ユハ・カンクネン、桑原晴民）、品種・手法・事件が QUANTITY／PERSON になる、など。1 割以下の基準に届かないので、閾値を上げる方向だけで builder の設定を `def_min`=`alias_min`=`paren_alias_min`=2 に上げて作り直した（`build/initial-layers/r9_config_k2.json`。それ以外の設定・入力・holdout・exclude-terms は同じ。抽出段のキャッシュは再利用: 閾値は抽出の後に効く）。直した版は direct 495 語（対照 498 語）、目視 60 語で **誤り 4 語（6.7%）**、疑わしい 11、正しい 45（`x3_sample60_k2.tsv`）。以後の測定（X4〜X6）は直した版（`law_k2`）の層で行う。最初の版の層・台帳・目視表は残してある。
- 2026-10-05 **法令の層と対照の層がほぼ同じ大きさ**（最初の版 16,748 対 16,805、直した版 495 対 498）。K409 の約束どおり、これは「法令の場面だから」ではなく「素材を general_qa の部分集合に絞ったこと自体（と、r9 とは別の抽出）」の効果と読む。法令の分野の知識が増えた、とは書かない。付随する観測: 分野の配置（jawiki 全量＋9,694 行）の見出し語は title 918,444（r9 は 900,943）で、r9 に無い title が 1.7 万語ある。r9 の抽出段のキャッシュ（`extract_r9.pkl`）が今の builder の抽出と同じかどうかは **未確認**（manifest の `builder_sha256` は一致、キャッシュの内容の照合はしていない）。
- 2026-10-05 `confidence_tiers` の `agree` は **棄権どうしの一致も数える**（K411 の文言どおり。署名は結果の型と固定文）。自転車の問い（製品の経路で全問が `STRUCTURE_UNDETERMINED`）は 3 段が棄権で一致して `agree=3` になる。したがって `agree` の高さは「答えの確からしさ」ではなく「構造が同じ結果を出した段の数」で、答えが ANSWER のものだけで見る集計も `x5_summary.json` の `shown_answers_by_agree` に別に出した。段の構成は変えていない（K403・X5）。
- 2026-10-05 `--layer` を `--no-llm` と一緒に渡したときは、base の次に `layer` という名前の段として扱う（`--tier` が無いときは base＋layer の 2 段。base 段は利用者の層を見ない: テスト `test_cli_layer_does_not_leak_into_the_base_stage`）。
- 2026-10-05 `vocab` 段は `--tier vocab=<vocab.sqlite>` で名前と sha256 だけを `vera.initial_layers` に出し、常に `NOT_CONSULTED_BY_READER`。読解器が語彙層を引く線は W3-e2/W3-e3（読解器に触れない約束）。
- 2026-10-05 手順の逸脱: (1) 実装役が `ls` で他のチケットのクローン（`wt/W10-f05-S`）の存在を 1 回確かめた（中のファイルは開いていない。W10-f05 の `run_domain.sh` の `W=` を直す前に、そのパスの有無を見ただけ）。(2) 陶芸の写しは inputs に無かったので W10-f05 のレビューが公開した写し（sha256 が `2b5709af…`・`63d66cb5…` と一致）を使った。(3) 台帳の追記の O(n²) のため、builder に `bulk_ledger` 等を足した（§7）。途中で止めた 3 回分の層・台帳は `build/initial-layers/{law,control}/*partial_aborted*` に残してある（行の中身は同じ規則）。

### 第 2 ラウンド（r1 レビューへの対応。2026-10-05 14:xx）
- **M1** `tests/test_w12c1_nollm.py` の fixture が `VERA_PLACEMENT_LAYER` を漏らしていた（`cli.main` の `--layer` が `os.environ` を直接書くため、`delenv(raising=False)` では teardown で戻らない）。各変数を `setenv`→`delenv` にして元の状態（無い）を monkeypatch に記録させ、`VERA_PLACEMENT_LAYER_ROOT` も対象に足した。後ろに環境が空かを見る probe を付けて `pytest` を流すと `passed`（`pytest_m1_probe.txt`: nollm 単独＋probe は 12 passed、`tests/test_w12c1_*.py`＋probe は 50 passed）。全体テストも流し直した（X8）。
- **M2** 語彙層の漢字の連なりに踊り字「々」を含めた（builder 側の追加条件。先頭が「々」の連なりは候補にしない）。部品 `granularity` の穴は §7 に書き、部品は直していない。語彙層を作り直し（旧版は `*_v1_iter_unfixed` に名前を変えて残した）、X2 の数・目視 60 語（引き直し）・X5・X6 を新しい版で出し直した。数: 語数 371,917 → 372,054（`々` を含む語 0 → 460）、r9 の未決定のうち確認できた語 216,079 → 216,217（`々` を含む語 0 → 177）。レビューの確認の SQL（`x2_m2_check_words.txt`）は `佐々木`・`代々木`・`人々`・`様々` と `木駅` を返す。**`木駅`（human 12 文書）が残る** のは `鵜の木駅`・`柿ノ木駅`・`四ツ木駅` の「の・ノ・ツ」で切れた連なりで、`々` とは別の原因（O6。直していない）。テストを 3 本足した（`代々木公園`／`人々`・`様々`・`佐々木`／先頭が `々`）。
- **M3** 実装に合わせて文を直した（docs の K406・§7、builder の docstring）。`granularity.standalone_count` は呼んでいない: builder は極大の連なりを取るので、`々` を含まない文では `standalone_count(w, text) > 0` と同じ集合になる。これを合成の文 9 本で確かめるテスト（`test_runs_of_kanji_equals_standalone_count_on_texts_without_the_mark`）と、`々` を含む文で意図して違うことを確かめるテスト（`test_iteration_mark_words_are_kept_whole_and_their_fragments_are_not_words`）を足した。指示書 S3 の「最終の判定は `standalone_count` を呼ぶ」からの **逸脱**（(b) を選んだ理由: jawiki 150 万記事 × 候補 190 万語の語ごとの正規表現は現実的でなく、極大の連なりは同値）。
- **M4** `why_not_gained.py` に誤答の型 `WRONG_WITHOUT_LAYER`／`WRONG_WITH_LAYER`／`WRONG_BOTH` を足した（最優先で判定。答えなしの問いに答えた場合も。判定は `score_qa.py` と同じ）。合成の入力での確認は `artifacts/w12-c1/m4_synthetic/`（`output.txt` に WRONG_BOTH 1・WRONG_WITHOUT_LAYER 1・GAINED 1）。足した後の自転車の再実行は型の数が前と同じ（`m4_rerun_x4_bicycle_law.txt`）。
- 任意の改善: **O1**（法令層 495 行のうち 469 行が対照と一致: X3）、**O2**（`--tier vocab=<無いファイル>` は `TIER_FILE_NOT_FOUND`。テスト 1 本）、**O3**（`new_failures_explained.txt` をこのチケットの根拠に書き換え）、**O4・O5**（§5）、**O6**（§7）、**O7**（X5 に `agree == counted` が 50/50 と書いた）は対応した。
- 変えていないもの: 読解器・`coarse_*`・部品。法令の層・対照の層（`law_k2` ほか）は作り直していない。X1 の r9 query 全数は流し直していない（`cli.py`・`vera_server.py` は r1 から編集しておらず、r2 の製品コードの変更は `confidence_tiers.py` の O2 だけ。既定の入口はそれを import しない）。入口 4,149 文と serve 310 行は流し直して SAME（`x1_entry.txt`・`x1_serve.txt`。r1 の出力は `*_r1.txt`）。

### 第 3 ラウンド（監査役の裁定への対応。2026-10-05 15:05）
- **裁定の要旨**（2026-10-05 14:58:08 +0900）: (1) X7 は「初期層が原因の誤答 0（層なしと層ありで同じ答え）」と読み替える。基点の誤答（叔父→「叔」、祖母→「祖」）は W3-f1 で直す。(2) M5 を直す。(3) 配布物としての初期層は採らない（語彙層・法令層は `build/initial-layers` に残し、builder・測定の道具・この文書だけを統合。`--profile`／`confidence_tiers`／`--no-llm` の配線は既定オフ）。`confidence_tiers` の `agree` は「答えた段のうち一致した数」に改め、棄権は数えない。
- **`agree` の定義の変更**: `confidence_tiers.combine` を改めた（`agree` = 示すのが ANSWER で衝突が無いとき、ANSWER の段のうち示す答えと署名が同じ段の数、それ以外は 0。`answered` を足し、`schema` を `/2` に）。r2 の §J の「`agree` は棄権どうしの一致も数える」は r2 までの定義で、r3 で改めた。`test_abstentions_of_different_types_are_different_signatures` の期待を `(agree, counted, conflict) == (1, 2, False)` から `(agree, answered, counted, conflict) == (0, 0, 2, False)` に書き換えたのは定義の変更によるもの（監査役の裁定）で、期待を弱めたのではない。ほかの既存の assert は変えず `answered` などを足しただけ。足したテスト: `test_agreeing_abstentions_are_not_counted`、`test_an_answer_followed_by_an_abstention_shows_the_abstention_with_agree_zero`、`test_schema_is_v2`、`test_runner_abstention_has_agree_zero`。S1 だけ（旧 `combine`）の状態で `test_w12c1_tiers.py` を流すと 9 件落ちる（`$SC/r3_red.txt`。テストが定義を見ている証拠）。
- **M5**: §7 の `granularity.verify` の行を事実どおりに直した（`standalone_count` は呼んでいない）。事前登録の約束ではなく事実の記述の誤りなので置き換えにした。
- **O9**: r2 の M1 の行の「12 passed／50 passed」は O2 のテストを足す前の実行の数（r2 のレビューで 13／51 を確認）。今回の `pytest_w12c1.txt` が今の数。
- **設計への負の結果**: 冷たい出発は「生成コーパス由来の層」では緩和できなかった（X4 の増分 0、法令層は対照と 469/495 一致で分野を捉えていない、語彙層は読解器が引かない）。効く見込みのある線は (a) 読解器が語彙層を仮定の出所として引く（W3-e3）、(b) 分野固有の文書（法令なら条文そのもの）から作る分野層（r11 と同じ線）、(c) 人の知の層（W13-h1）。ベース v1 §5 への追記は監査役がする（このチケットでは `ops/` を触らない）。配布物としての初期層は採らず、配線は既定オフ。
- **X1 の query**: r9 全数（約 5 分×2）は流し直していない。r2 のレビューで今の `cli.py`・`vera_server.py` のまま基点と SAME（`4ab15ee8…`）を確かめてあり、`coarse_place.query` は `confidence_tiers` を通らず、このラウンドで変えた製品コードは `confidence_tiers.py` の `combine` だけ。入口 4,149 文と serve 310 行は流し直した（r2 の出力は `x1_entry_r2.txt`・`x1_serve_r2.txt`）。
- **気づいた点（直していない）**: `cli.py` の `--help` の「how many stages agreed」は新しい定義（答えた段のうち一致した数）より広い言い方のまま。X1 の byte 一致と「製品の他の部分は変えない」の裁定のため触っていない。`x6_http_answer.json` は撮り直していない。
- **M6（第 3 ラウンドのレビュー）**: 全体テストの後に `compare_failure_sets.py` が `new_failures_explained.txt` を別チケットの固定文で上書きしていた。r2 の中身（O3: このチケットの根拠）に戻し、`compare_failure_sets.py` がこのファイルを書かないようにした（選択 (b)。`new_failures.txt`・`fixed_failures.txt`・`after_failures.txt` の書き出しは不変）。
- **O14・O15**: §M の X5 に「`agree > 0` の問いはすべて `agree == answered == counted` か」を数から機械的に出す 1 行を足した（結論の文は書いていない）。冒頭の裁定の段落の後に空行を入れた。
- **変えていないもの**: `cli.py`・`vera_server.py`・`READING_SOUNDNESS.md`・builder・層・X1〜X4・X6 の出力。
