# W3-b3 事前登録（docs の写し）

登録日時: 2026-10-03 23:17:09 +0900

## docs/READING_SOUNDNESS.md §10C

## 10C. W3-b3: 埋め込みの十字 — 述語が 2 つの文を、十字の中の十字と辺として読む（事前登録 K114〜）

<!-- w3b3-prereg:begin -->
登録日時: 2026-10-03 23:17:09 +0900（`date '+%F %T %z'` の出力。直前の同じ出力は 2026-10-03 23:17:08 +0900、直後は 2026-10-03 23:17:09 +0900 で、この節（と `docs/EVENT_CROSS.md`・`docs/READING_CONVENTIONS.md` の追記）はその間に書いた。記録は `artifacts/w3-b3/prereg_time.txt`）。
この時点で `tests/reading_soundness/w3b3_*.jsonl`・`tests/test_semantic_read_w3b3*.py` は存在しない（`artifacts/w3-b3/cut_tags.txt` は例文のタガーの出力の記録で、検査データではない）。`verantyx/` は基点 `c875ed3` のまま。
出典: 中間職の指示書 `.claude/vera-audit/review-impl/W3-b3/plan.md` §3 と、チケット `W3-b3_embedded_crosses.prompt.md`。W1-a4（保留。表層の接続語で節を分けて、レビュー 3 ラウンドで誤読が出続けた）の **一覧**（接続語の表の形・許可の 3 語・引用の動詞 8 語）だけを写した。規則は写していない。
目的: 述語がちょうど 2 つで切れ目がちょうど 1 つの文を、(1) 連体修飾節 → 主辞を充填物とする埋め込みの十字（主辞の腕を **型で** 決める）、(2) 閉じた接続語の節 → 別の十字と型付きの辺、として読む。各節の中の読みは **入口そのもの**（既存の規則と W3-b1/b2 の型による読解）を通し、新しい役割の規則・語の一覧・表層の規則は足さない。足してよいのは棄権を増やす門だけで、すべてここに登録する。誤読が出たらその構成を棄権に戻す（語を足して直さない）。

### K114 制御の流れ・引き金・チケットの文言の読み方
1. 配置を指定したときだけ動く。`semantic_read._read_ja` の「配置あり」の分岐の 1 行だけを変える（`_typed_reread_ja` が読めなければ `_w3b3_read_ja` を呼ぶ。読めなければ受け取った出力を **同じオブジェクトのまま** 返す）。配置なしの出力は基点と 1 バイトも変わらない（接続の文も、配置が無ければ読まない）。新しい経路が棄権した文の出力は 1 バイトも変えない（W3-b2 の K94 と同じ。棄権の型付きの理由は診断 `semantic_read.clause_scope_explain_ja` にだけ出す）。
2. 引き金は、配置に問い合わせる前に、全文のトークンだけで決める。和文・`R._sentences` が 1 区間・節の読みの中でない（深さ 0。節の読みは `_read_ja` を呼ぶので、印で二重に止める）・述語のまとまりがちょうど 2 つ・K115 の切れ目がちょうど 1 つ・一覧にない形（K115 の「一覧外の形」）がない・2 つのまとまりが切れ目の両側に 1 つずつ。
3. 引き金に当たった文に K116〜K120 を、K122 の順に掛ける。最初に当たった門の理由で止まる。問い合わせは、K116（トークンだけで決める門）と K117 の字面・トークン一致の検査をすべて通ってから初めて起きる。
4. チケットの文言の読み方（判断記録 H150〜に理由）:
   - (a) て形・連用中止の辺は **入口の出力には出さない**（入口では今の棄権のまま）。辺 `TE_UNDETERMINED`・`PARALLEL_UNDETERMINED` は診断の `edges` にだけ書く。規約 §1.2 の関係の型ではなく、`CrossReading` には入らない（採点器は規約に無い型を `readable: true` の `relations` に書くと必ず誤答にするため、受入基準 S2・S4（誤答 0）と入口の上では両立しない）。
   - (b) 主語の省略は **は の主題だけ** で埋める（W1-a4 の最終形。チケットの「同じ文の主語」より狭い。が の主語は埋めず棄権）。
   - (c) 主辞の腕はチケットの文言どおり（空いている腕がちょうど 1 つ ＋ 型の一致）。型の表 `TYPED_FRAMES` は広げない。
   - (d) 1 文の切れ目はちょうど 1 つ（節は 2 つ）。3 節以上は棄権。
   - (e) 切れ目の有無・一意性・形の門はトークンの品詞と活用形で決め、語の表層の一覧では決めない。

### K115 切れ目の閉じた一覧
全文のトークン（`R._tokens` の特徴を、最初に不変の値の列へ写したもの。タガーの節点は次の解析で別の値になる）の上で、品詞（pos1/pos2）・語彙素・活用形・隣のトークンで判定する。`cut_tags.txt` に各形のタガーの出力を残した。

<!-- BEGIN table:w3b3_cuts -->
| 切れ目 | 検出（全部満たす） | 節の種類 | 関係の型 | 時制 |
|---|---|---|---|---|
| `relative` | 動詞（連体形・終止形が同じ形。ている・てしまう の補助の動詞 = 直前が て/で の非自立可能は除く）、または動詞の連用形＋助動詞 た（連体形）の直後に 名詞・接頭辞 が来る。ない・れる・せる・形容詞・形状詞は対象外。直後の名詞の pos3 が 副詞可能・助数詞可能 のとき（後・前・ため・時 の型）は切れ目にせず一覧外（`CLAUSE_SCOPE_NOT_LISTED`） | 定形 | `relative` | 入口の値 |
| `ので` | 準体助詞 の ＋ 助動詞 で（語彙素 だ）。直前が動詞か助動詞 た | 定形 | `cause` | 入口の値 |
| `から` | pos2 が 接続助詞 の から。直前が動詞か助動詞 た | 定形 | `cause` | 入口の値 |
| `が` | pos2 が 接続助詞 の が（格助詞 が は除く） | 定形 | `contrast` | 入口の値 |
| `けれど` | pos2 が 接続助詞 で語彙素が けれど（けれど・けれども・けど。けれども の も 係助詞 も切れ目に入れる） | 定形 | `contrast` | 入口の値 |
| `と` | pos2 が 接続助詞 の と。直前が動詞の終止形か、助動詞 た・ない の終止形 | 定形 | `condition`（K119 の引用の門つき） | 入口の値 |
| `なら` | 助動詞 だ の仮定形 なら。直前が動詞の終止形（名詞＋なら は切れ目にしない） | 定形 | `condition` | `null` |
| `ば` | pos2 が 接続助詞 の ば。直前が動詞の仮定形 | 非定形 | `condition` | `null` |
| `たら` | 助動詞 た の仮定形 たら・だら。直前が動詞の連用形 | 非定形 | `condition` | `null` |
| `ても` | 接続助詞 て/で ＋ 係助詞 も。直前が動詞の連用形。直後が いい・よい・かまう（許可）なら切れ目にしない | 非定形 | `concession` | `null` |
| `ながら` | pos2 が 接続助詞 の ながら。直前が動詞の連用形 | 非定形 | `simultaneous` | `null` |
| `て` | 接続助詞 て/で。直前が動詞の連用形。直後が 読点、または 名詞・代名詞・副詞・連体詞・接頭辞（直後が 動詞の非自立可能・から・も・は なら切れ目にしない = ている・てから・ても・ては） | 非定形 | （書かない。診断の `TE_UNDETERMINED`） | `null` |
| `並列` | 動詞の連用形（連用形-一般）の直後が 読点 | 非定形 | （書かない。診断の `PARALLEL_UNDETERMINED`） | `null` |
<!-- END table:w3b3_cuts -->

- 非定形の切れ目（ば・たら・ても・ながら・て・並列）の直前が助動詞（来なければ・読まれても・食べたくて の型）でも切れ目に数え、節は読まない（K117 の `aux_in_nonfinite`）。
- 切れ目のトークン（と、その直後の読点）はどの節の文字列にも入れない。それ以外のトークンはすべてどちらかの節に入る（黙って捨てない）。
- **述語のまとまり**: `semantic_read._is_predicate_token` が真のトークンを、(a) 直前のトークンも述語のトークン（複合動詞）、(b) 直前が て/で で、その前が同じまとまり、のとき同じまとまりに入れる。
- **一覧外の形**（引き金に当たらない。`CLAUSE_SCOPE_NOT_LISTED:<形>`）: のに（準体助詞 の の直後が 格助詞 に）、てから（て の直後が 格助詞 から）、動詞の後ろの 形状詞 助動詞語幹（よう・そう の型）、relative の直後の名詞が 副詞可能・助数詞可能（後・前・ため・時 の型）。
- 語の一覧は使わない。表に出る語は、いい・よい・かまう（W1-a4 の K42 の表から写した許可の 3 語）と、K119 の引用の動詞 8 語だけ。

### K116 切れ目の一意性と、文全体の門（トークンだけで決める。問い合わせない。順に掛ける）
1. **形の門** `CLAUSE_FORM_NOT_READ:<理由>`: 全文に (a) 活用形が 命令形 のトークン → `imperative`、(b) 括弧・引用符（「」『』""）→ `quote`、(c) 疑問（？ ? ・終助詞 か）→ `question`、(d) 切れ目のトークン以外で `R._w3b1_marker(token) == 'conn'` のトークン（接続詞・ほかの接続助詞。ただし述語のまとまりの中の て/で、つまり直前が動詞で直後が動詞の非自立可能の て/で は除く）→ `connective_outside_cut`。
2. **句**: 全文を、助詞（pos1 が 助詞 で、pos2 が 接続助詞・準体助詞 でないもの。連体の の は句の切れ目にしない）の連なりの直後で区切った連なり。句の助詞は連なり全体の表層。主題の句 = 先頭の句で、助詞の連なりが は で終わるもの。
3. 主題: 関係節（`relative`）の区間（文頭から関係節の述語まで）に、は で終わる句があれば `CLAUSE_SCOPE_AMBIGUOUS:topic_in_relative`。接続の文で、は で終わる句が先頭以外にあれば `CLAUSE_SCOPE_AMBIGUOUS:topic_position`。接続の文の先頭の主題の句は従属節の文字列に入れる（読解器の chunk と同じ）。K120 の主語の埋めでだけ主節に使う。
4. **別の切り方の数え上げ**（W1-a4 の「表層で切った」誤りを閉じる門）: 主題の句を除いた、従属節の側の述語の前の句を p1..pn とする。k=1..n について「先頭の k 個を主節の側に移した切り方」を作る。どれか 1 つでも、2 つの節のどちらにも が の句が 2 つ以上・を の句が 2 つ以上 **無い**（格の重複で壊れていない）なら、その切り方は成り立ちうるので `CLAUSE_SCOPE_AMBIGUOUS:alternative_cut=<k>`。が・を 以外の助詞（に・で・へ・から・と ほか）は重なっても壊れない（三時に駅に）ので、重なりを壊れた証拠にしない。読み直しはしない。関係節の側の p が無ければ（切れ目の前が述語だけ）一意。
5. k=0（移さない切り方）がすでに壊れている（どちらかの節に が か を の句が 2 つ以上ある）なら、成り立つ切り方が無いので `CLAUSE_SCOPE_AMBIGUOUS:noncontiguous`。
- 例（構造で決まる）: `兄が買った本を弟が読んだ。` → k=1 で主節に が が 2 つ → 壊れる → 一意。`兄が駅で買った本を読んだ。` → k=1 で主節「兄が＋本を読んだ」は壊れない → 棄権。`駅で兄が本を買ったので、弟が喜んだ。` → k=1 で主節「駅で＋弟が喜んだ」は壊れない → 棄権（文頭の句の係り先が決まらない。規約 §9.2）。

### K117 節の文字列・読み・既存の門の再使用
1. 定形の節（関係節・ので・から・が・けれど・と・なら の前、主節）の文字列 = 区間の表層 ＋ `。`。
2. 非定形の節（ば・たら・ても・ながら・て・並列 の前）の文字列 = 動詞の前のトークンの表層 ＋ その動詞の **書かれた辞書形**（`typed_edges._base` = orthBase。語彙素は使わない: 閉め の lemma は 締める、帰ら は 返る）＋ `。`。動詞と切れ目の間に助動詞があれば `CLAUSE_FORM_NOT_READ:aux_in_nonfinite`。
3. **トークン一致の検査**: 節の文字列を `R._tokens` で解析し直し、各トークンの（表層・pos1・pos2・語彙素・活用形）が全文の同じトークンと一致すること。違ってよいのは最後のトークンの活用形だけで、(a) 定形の節の 連体形 → 終止形、(b) 非定形の節の書き換えた動詞（表層も違ってよいが orthBase と pos1 は一致）。ほかは `CLAUSE_TOKENS_DIFFER:<位置>`。
4. 節の文字列を入口 `_read_ja(文字列, 包んだ配置)` に通す。包んだ配置は新しい `_CachedQuery`（`w3b2_trace` を持たない）。`readable: true` で節がちょうど 1 つ・関係が空でなければ `CLAUSE_UNREAD:<節の番号>:<入口の最初の理由>`。
5. **既存の門の再使用**（基点の入口の単独の節の誤読 — 命令形・禁止・依頼・ている+ない・可能形 — が節の読みにそのまま入るのを止める）: すべての節の読みに、節の文字列のトークンと入口の述語の範囲で `R.typed_tail_ja` と `R.typed_head_derived_ja` を掛ける。当たれば `CLAUSE_FORM_NOT_READ:<その理由>`。下一段の動詞は派生の疑いで全部止まる（広い棄権。門を狭めない。被覆の損失は測って K123〜に書く）。埋め戻しの再読（K118）・主題の埋めの再読（K120）にも同じ門を掛ける。
6. 時制: relative・ので・から・が・けれど・と の節は入口が読んだ値。なら・ば・たら・ても・ながら・て・並列 の節は `null`（規約 §4.9・§5）。と の節は入口の値（規約 §4.9 の `null` の一覧に と が無い。正解が `null` なら採点されない）。

### K118 主辞の腕（`relative` だけ。型だけで決める）
1. 主辞の名詞句 = 関係節の述語の直後から、最初の助詞の直前まで。すべて 名詞（数詞でない）・接頭辞・接尾辞 で、の・連体詞を含まず、最後のトークンの pos3 が 副詞可能・助数詞可能（`W3B2_HEAD_RELATIONAL_POS3`）でない。満たさなければ `HEAD_ROLE_UNDETERMINED:head_not_simple` / `head_relational`。
2. 関係節の節（単独の読み）が `voice: active` でなければ `HEAD_ROLE_UNDETERMINED:voice`。
3. 関係節の述語（入口の述語。書かれた辞書形）の型 = `R.placement_type(問い合わせ)` が direct の `P_MOVE`・`P_COMMUNICATE`（`TYPED_FRAMES` にあるもの）。それ以外・答えが無いものは `HEAD_ROLE_UNDETERMINED:frame_not_read:<型か理由>`。節の役割名が、その型の表の役割名と `recipient` の外にあれば `HEAD_ROLE_UNDETERMINED:role_outside_frame`（棄権を増やす門）。
4. **枠が要求する腕** = その型の `TYPED_FRAMES` の行のうち 4 列目が `arg` の行（P_MOVE: agent・goal・source、P_COMMUNICATE: agent・patient）＋ 決まっていない腕（K62 の表の変更記録 1 で「読まない」に戻した `P_COMMUNICATE` の に の腕。名前は役割にしない = `NI_UNDECIDED`）。腕が埋まっているとは、単独の読みの役割に同じ役割名があること（`NI_UNDECIDED` は、関係節に に の句（格助詞 に）があれば埋まっているとする）。
5. 空いている腕がちょうど 1 つでなければ `HEAD_ROLE_UNDETERMINED:empty_arms=<n>`。その 1 つが `NI_UNDECIDED` なら `HEAD_ROLE_UNDETERMINED:undecided_arm`。
6. 主辞の配置の答えを `R.placement_fit(answer, その行の型)` に通し、`direct` か `all_candidates` でなければ `HEAD_ROLE_UNDETERMINED:type:<理由>`。述語の枠が CONFIRMED なら（`R.predicate_frame`）、決まった腕の助詞が枠にあり、主辞の型がすべて枠の型に入ることを確かめる（狭めるだけ。反すれば `HEAD_ROLE_UNDETERMINED:type:PLACEMENT_FRAME_*`）。
7. **付加の腕の同点**: 空いている `adjunct` の行（place・time）のどれかも `placement_fit(answer, 行の型, adjunct=True)` で `direct`／`all_candidates` なら `HEAD_ROLE_UNDETERMINED:adjunct_tie`。
8. **外の関係の型**: 主辞の型（direct の 1 つ、または全候補）が `ABSTRACT`・`EVENT_ACT`・`STATE_PROPERTY` のどれかを含めば `HEAD_ROLE_UNDETERMINED:outer_relation_type`（内容節・外の関係の区別がつかない。型の閉じた一覧。狭める側の門）。
9. **埋め戻しの再読**: 決まった腕の助詞（その行の 2 列目の 1 つ目）を使い、「主辞＋助詞＋関係節の文字列」を入口に通す。読みの述語・極性・時制・態・ほかの役割が単独の読みと同じで、決まった腕に主辞がちょうど入っていなければ `HEAD_ROLE_UNDETERMINED:refill_reread`。既存の門（K117 5）も掛ける。読めた節を関係節の節として使う。
10. 主節（主節の文字列）の読みの役割のうち、値が主辞と同じものがちょうど 1 つでなければ `HEAD_NOT_IN_HOST`。
11. 関係節の節の `predicate_basis` は `placement_direct:<型>`、`role_basis[腕]` は W3-b2 の文法（`placement_direct:<型>` か `placement_all_candidates:<A+B>`）。入口がすでに欄を書いていれば、その欄に腕の 1 行を足す（ほかの行は変えない）。

### K119 関係の表（規約 §1.2 の型と向き。節 0 = 従属節、節 1 = 主節）
<!-- BEGIN table:w3b3_relations -->
| 切れ目 | type | from → to | 棄権する場合（理由） |
|---|---|---|---|
| `relative` | `relative` | 0 → 1（＋`head`） | K118 |
| `ので`・`から` | `cause` | 0 → 1 | なし |
| `が`・`けれど` | `contrast` | 0 → 1 | なし |
| `ても` | `concession` | 0 → 1 | なし |
| `ば`・`たら`・`なら`・`と` | `condition` | 0 → 1 | 主節の tense が past → `RELATION_TYPE_UNDETERMINED:condition_past_main` |
| `と`（追加の門） | `condition` | 0 → 1 | 主節の述語が引用の動詞 8 語（言う 思う 話す 伝える 聞く 尋ねる 答える 考える。W1-a4 から写した）にある、または主節の述語の型が direct の `P_COMMUNICATE`・`P_COGNITION`・`P_CREATE`・`P_PERCEIVE`、または型が direct でない → `RELATION_TYPE_UNDETERMINED:quote_possible` |
| `ながら` | `simultaneous` | 0 → 1 | なし |
| `て` | （書かない） | — | 常に `RELATION_TYPE_UNDETERMINED:TE_UNDETERMINED`（診断の `edges` に `{"type":"TE_UNDETERMINED","from":0,"to":1}`） |
| `並列` | （書かない） | — | 常に `RELATION_TYPE_UNDETERMINED:PARALLEL_UNDETERMINED`（同上） |
<!-- END table:w3b3_relations -->
- て・並列の辺は、2 つの節が K117 で読めたときだけ診断の `edges` に書く。

### K120 省略（W1-a4 のレビュー第 1〜3 ラウンドで閉じた形。順に掛ける）
1. **主語の埋め**（唯一の形）: 先頭が主題の句 `X は`（K116 2）で、従属節（`relative` でない文の最初の節）の読みで X が agent、その節が能動。主節の側に が・は の句が無く、主節が能動で agent を持たない。このとき主節の文字列の前に `X は` を付けた文字列を入口に通し（既存の門も掛ける）、agent が X で、ほかが主節の単独の読みと同じなら、その読みを主節にする。違えば `ELLIPSIS_UNDETERMINED:subject`。
2. **埋めないときの棄権**: 主語（agent・受身の patient・entity）の無い節があり、ほかの節の側に が・は の句があるのに 1. で埋めなかったら `ELLIPSIS_UNDETERMINED:subject`。どの節の側にも が・は の句が無ければ書かない（入力に先行詞が無い。規約 §3）。
3. **目的語**: 能動の節で patient が無く、述語の `frames.transitivity` が `intrans` **でない**（`trans` も `unknown` も）、かつ、ほかの節に名詞の値の役割がこの節の agent と違う値で 1 つでもあれば `ELLIPSIS_UNDETERMINED:object`（W1-a4 第 3 ラウンド必須 2 を、`unknown` も含む側に広げた）。`relative` の関係節の節で、主辞を入れた腕が patient のときは対象外。
4. **斜格**: ほかの節にある goal・source・place・recipient・instrument・companion・time がこの節に無く、(a) 2 つの節の述語が同じ語、または (b) 欠けた役割が goal・source でこの節の述語が `R._GOAL_PREDICATES` か `semantic_read._PATH_VERBS`（dev にある一覧。新しい一覧は作らない）にある → `ELLIPSIS_UNDETERMINED:<役割>`。

### K121 出力
- `clauses` = [節 0, 節 1]（述語の出現順。関係節・従属節が先）。各節は入口の読み（K117 6 の時制・K118 の主辞の腕を反映）。`relations` = K119 の 1 要素。`relative` だけ `{"type": "relative", "from": 0, "to": 1, "head": {"from_role": <関係節での腕>, "to_role": <主節での役割>}}`（`head` は規約の鍵の外。採点器は読まない。十字が使う）。
- `clause_meta` = 各節 `{"rule": <入口の節の rule>, "span": [全文での述語の頭のトークンの始め, 切れ目（主節は文末の句点）の直前の最後のトークンの終わり]}`（全文のトークンの位置から作る）。`unsupported` = 全文の `unsupported_report`（W3-b1/b2 の型の経路と同じ）。
- `NOT_PRODUCED` は変えない（配置なしの入口の記述）。代わりに定数 `W3B3_PRODUCED_WITH_PLACEMENT`（配置があるときに新しく出る関係の型と欄）を足し、下の表と機械で照合する。

<!-- BEGIN table:w3b3_produced -->
| 名前 | 内容 |
|---|---|
| `relation:relative` | 配置あり・K118 が通ったときだけ。鍵 `head` を持つ |
| `relation:cause` | ので・から。配置ありのときだけ |
| `relation:contrast` | が・けれど。配置ありのときだけ |
| `relation:concession` | ても。配置ありのときだけ |
| `relation:condition` | ば・たら・なら・と。配置ありのときだけ |
| `relation:simultaneous` | ながら。配置ありのときだけ |
| `relation_key:head` | `relative` の関係だけが持つ鍵（`from_role`・`to_role`）。規約の鍵の外 |
| `tense:null` | なら・ば・たら・ても・ながら の従属節 |
<!-- END table:w3b3_produced -->

### K122 理由の型（閉じた一覧）と門の順
- 理由の名前（`:` の前）。診断 `clause_scope_explain_ja` の `reason`。入口の出力には出ない。

<!-- BEGIN table:w3b3_reasons -->
| 理由の名前 | 細目 |
|---|---|
| `W3B3_NOT_TRIGGERED` | `not_reached`・`depth`・`sentences`・`groups=<n>`・`groups_not_split` |
| `CLAUSE_SCOPE_NOT_LISTED` | 一覧外の形（K115） |
| `CLAUSE_SCOPE_AMBIGUOUS` | `cuts=<n>`・`alternative_cut=<k>`・`topic_in_relative`・`topic_position`・`noncontiguous` |
| `CLAUSE_FORM_NOT_READ` | `imperative`・`quote`・`question`・`connective_outside_cut`・`aux_in_nonfinite`・既存の門の理由（`PLACEMENT_PREDICATE_TAIL_UNINTERPRETED:…`・`PLACEMENT_PREDICATE_POSSIBLY_DERIVED:…`） |
| `CLAUSE_TOKENS_DIFFER` | 位置 |
| `CLAUSE_UNREAD` | 節の番号と入口の最初の理由 |
| `HEAD_ROLE_UNDETERMINED` | `head_not_simple`・`head_relational`・`voice`・`frame_not_read`・`role_outside_frame`・`empty_arms=<n>`・`undecided_arm`・`type`・`adjunct_tie`・`outer_relation_type`・`refill_reread` |
| `HEAD_NOT_IN_HOST` | なし |
| `RELATION_TYPE_UNDETERMINED` | `TE_UNDETERMINED`・`PARALLEL_UNDETERMINED`・`condition_past_main`・`quote_possible` |
| `ELLIPSIS_UNDETERMINED` | `subject`・`object`・役割名 |
<!-- END table:w3b3_reasons -->

- 門の順: (1) 引き金 K114 2 → (2) 一覧外の形 → (3) 切れ目の数 → (4) 形の門 K116 1 → (5) 主題・別の切り方 K116 3〜5 → (6) 節の文字列（aux_in_nonfinite）・トークン一致 K117 1〜3 →【ここから問い合わせる】→ (7) 節の読み K117 4 → (8) 既存の門 K117 5 → (9) `relative` の主辞 K118 → (10) 関係の型 K119 → (11) 省略 K120 → 読めた。

### 検査データ（手順 3 で書く。この登録の後）
- `tests/reading_soundness/w3b3_relative.jsonl`（連体修飾 60 文）・`w3b3_connective.jsonl`（接続 60 文。K115 の接続の 11 形を各 3 文以上）・`w3b3_parallel.jsonl`（並列 30 文: て形 15・連用中止＋読点 15）、`w3b3_w1a4.jsonl`（W1-a4 のレビューの誤読の全件。棄権すべき文）。どれも日本語。`behavior: read` と `behavior: abstain` が半々（`w3b3_w1a4.jsonl` は全件 abstain）。
- `read` の行の `expect` は **規約どおりの正解**（実装が出せるかどうかで変えない）。`entry_expect`（`read` / `abstain`）は入口の出力の予想、`w3b3_expect`（`READ` か K122 の理由）は診断の予想、て形・並列の `read` の行は `structure_expect`（2 つの節と `edges` の辺）。`abstain` の行の `expect.readable: false` は「この経路では読みが一意に決まらない」の意味（規約 §7 の読めない入力ではない）で、`abstain_why` に棄権すべき理由の型を書く。
- 凍結の後に期待を変えない。直すべきと思ったら判断記録に書いて報告する。

### 受入基準の読み方
S1 配置なしの出力は基点とバイト一致（`w3b1_entry_dump.py --mode none` の比較）・既存の凍結データと x3 で `changed=0`・`misread=0`。S2 は中間職が未公開の文で測る。S3 W1-a4 の誤読の全件が棄権（テスト）。S4 は監査役が B1 で測る（下準備の数だけを出す）。S5 `vera observe` で EDGE の移動が動き、再観測可能率 100%。S6 既存テストの失敗集合が基線から増えない。目標の数値は書かない。測定結果は K123〜 に `w3b3_recompute.py` の出力をそのまま貼る。
<!-- w3b3-prereg:end -->


## docs/EVENT_CROSS.md

## W3-b3 の追記(埋め込みの十字。事前登録)

<!-- w3b3-ec-prereg:begin -->
登録日時: 2026-10-03 23:17:09 +0900（`docs/READING_SOUNDNESS.md` §10C と同じ。記録は `artifacts/w3-b3/prereg_time.txt`）。この時点で `verantyx/event_cross.py` は基点 `c875ed3` のまま。既存の節の文は変えていない（追記だけ）。

1. **`Filler.embedded`**: `Filler` に欄 `embedded: Optional[EventCross] = None`（最後の欄）を足す。`to_dict` は `embedded` が `None` でないときだけ、鍵 `embedded`（中身は `EventCross.to_dict()`）を **最後に** 足す（`None` のときは今とバイト一致）。意味: 連体修飾節（`relative`）の主辞 = 主節の腕の充填物の中に、関係節の十字が入る。
2. **関係の `head` 欄**: `relative` の関係は鍵 `head`（`{"from_role": <関係節での腕>, "to_role": <主節での役割>}`）を持ちうる。規約 §1.2 の鍵の外（採点器は読まない。`_relation_dict` が今も余分な鍵を残す）。`_check` は `head` があれば次を確かめ、反すれば `RELATION_HEAD_NOT_WELL_FORMED:<何が>`（入力の拒否 `INPUT_REJECTED`。`<何が>` は定数 `RELATION_HEAD_REASONS` の閉じた一覧）。`head` の無い関係は今と同じ。

<!-- BEGIN table:w3b3_head_reasons -->
| 何が | 検査 |
|---|---|
| `not_a_mapping` | `head` が写像でない |
| `keys` | `head` の鍵が `from_role`・`to_role` の 2 つだけでない |
| `type_not_relative` | 関係の `type` が `relative` でない |
| `role_not_in_convention` | `from_role`・`to_role` が `ROLE_NAMES` の文字列でない |
| `values_differ` | `clauses[from].roles[from_role]` と `clauses[to].roles[to_role]` が同じ空でない文字列でない |
| `duplicate_target` | 同じ `(to, to_role)` を指す `head` が 2 つ以上ある |
| `nested` | `from` の節自身がほかの `head` の `to` になっている（入れ子は 1 段まで） |
<!-- END table:w3b3_head_reasons -->

3. **`build_crosses`**: 十字を今と同じに作った後、`head` のある関係ごとに、`crosses[to]` の腕 `to_role`（`FILLER`）の充填物を `embedded=crosses[from]` にした十字に置き換える（`dataclasses.replace`）。腕の型一致・`counts` は変えない（`counts` に埋め込みを数え足さない）。`crosses` の並びと番号は今と同じ（関係節の十字は `crosses[from]` としても残る）。
4. **`TE_UNDETERMINED`・`PARALLEL_UNDETERMINED` は規約の関係の型ではなく、`CrossReading` には入らない**。て形・連用中止の文は入口（`semantic_read.read`）では棄権のままで、この 2 つの辺は診断 `semantic_read.clause_scope_explain_ja` の `edges` にだけ書く。`_check` の `RELATION_TYPE_NOT_IN_CONVENTION` は変えない。
5. 変えないもの: `ROLE_NAMES`・`RELATION_TYPES`・`EXPECTED_TYPES`・`VERDICTS`・`_agreement`・`counts` の形・`StubLookup`/`CoarseLookup`。観測 `observe.py` は変えない（`EDGE(relation)` は規約の 11 種だけ。升の鍵 `content_of_cross` は充填物の `embedded` を含めない）。
<!-- w3b3-ec-prereg:end -->


## docs/READING_CONVENTIONS.md の注記
§1.2 末尾:
- 追記(W3-b3): `relative` の関係は、W3-b3 の経路（配置あり。`docs/READING_SOUNDNESS.md` §10C）では鍵 `head`（`from_role`・`to_role`）を持つことがある。採点は読まない（`type`・`from`・`to` だけを見る）。規約の鍵の表は変えない。


§4.5 末尾:
- 追記(W3-b3): 配置ありの経路が読んだ `relative` の関係は、鍵 `head`（`{"from_role": <関係節での腕>, "to_role": <主節での役割>}`）を持つことがある。採点は読まない。主辞の腕は型で決まったときだけ（`docs/READING_SOUNDNESS.md` K118）で、決まらない文は読まない。


