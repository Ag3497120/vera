<!-- w3b4-prereg:begin -->
登録日時: 2026-10-04 01:09:51 +0900（`date '+%F %T %z'` の出力。記録は `artifacts/w3-b4/prereg_time.txt`。直前のコミットは `c875ed32444b1a2a12dccf38a7a7a79a03418eeb`（Merge W3-b2））
この時点で `tests/reading_soundness/ja_r10_w3b4.jsonl`・`tests/test_semantic_read_w3b4.py`・`tests/coarse_place/test_k62_v1_subset_v2.py` は存在しない（型の成員の一覧 `artifacts/w3-b4/r7members/type_members.txt` は、この登録より前に作った。根拠の一覧であって、検査データではない）。
出典: 中間職の指示書 `.claude/vera-audit/review-impl/W3-b4/plan.md` §2〜§4 と、チケット `W3-b4_frames_stage2.prompt.md`。目的: 型による読解（W3-b1 経路 U・W3-b2 の規則）が読む述語の型を、K62 の 2 型（P_MOVE・P_COMMUNICATE）から、**充填物の型で役割がちょうど 1 つに決まる範囲だけ** 広げる。規則・門・語の一覧は足さない。足すのは第 2 表（v2）だけ。誤読が 1 件でも出た型は、その型を表から外して読まない型に戻す（語や表層の規則で直さない）。登録後の変更は狭める方向だけで、「表の変更記録（W3-b4）」に全件書く。
番号について: チケットは K110〜 を指すが、§10B が K94〜K113 を、並行の W3-b3 が §10C（K100〜）を使うので、衝突を避けて **この節は K160〜（事前登録・既知の穴）、判断記録は H160〜** を使う。検査データの名前も、チケットの `tests/reading_soundness/ja_r10.jsonl` は W3-b1 第 4 ラウンドの凍結データとして既にあるので、**`tests/reading_soundness/ja_r10_w3b4.jsonl`** を使う（受入基準 F3 の `ja_r10` はこのファイルを指すと読む）。

### K160 制御の流れ

- 配置を指定したときだけ動く。配置なしの出力は基点（c875ed3）と 1 バイトも変わらない（型の段は配置があるときだけ呼ばれる）。
- 読解器は **`verantyx/semantic_reader.py` の末尾への追記だけ** で変える（既存の行は 1 行も変えない。凍結テスト `test_the_reader_file_only_gains_lines` が `-` 行 0 を求める）。`semantic_read.py` は触らない。
- v1 の `TYPED_FRAMES`・`TYPED_FRAMES_NOT_READ` は **値を変えない**（凍結テスト 4 本が固定している）。v2 は新しい名前で持つ: `TYPED_FRAMES_W3B4`（新しく読む 5 型の行）、`typed_frames_v2()`（呼ばれた時点の `{**TYPED_FRAMES, **TYPED_FRAMES_W3B4}`。定数の写しにしない。凍結テストが v1 の辞書をその場で書き換えるため）、`TYPED_FRAMES_NOT_READ_W3B4`（読まないまま残る 6 型）。チケットの「`TYPED_FRAMES` を v2 の表と同じ並びで持ち」からの逸脱で、理由はこの 2 点（判断記録に書く）。
- W3-b2 の計画 `typed_plan_u_w3b2_ja` の本文を **1 字ずつ写した** `typed_plan_u_w3b4_ja` を足す。違うのは表の参照の 2 行だけ（`TYPED_FRAMES_NOT_READ` → `TYPED_FRAMES_NOT_READ_W3B4`、`TYPED_FRAMES.get(ptype)` → `typed_frames_v2().get(ptype)`）。旧は `typed_plan_u_w3b2_v1_ja` の名で残し、`typed_plan_u_w3b2_ja` の名を新しい関数に差し替える（入口は呼ぶたびに `R.typed_plan_u_w3b2_ja` を引くので、経路 U・U3 が v2 で読む）。W3-b1 の計画 `typed_plan_u_ja` は v1 のまま。**（第 4 ラウンドの注記: 表は v1 のまま。ただし名前 typed_plan_u_ja は K186 の門で包んだ関数に差し替えた。本体の関数定義は基点のまま）**
- 役割の決定は W3-b2 の規則そのまま: 充填物の主辞の配置が `DECIDED direct`（門 1〜6）または全候補が行の型に入る `MULTIPLE direct` で、その型に合う役割が表の中でちょうど 1 つ。2 つ以上なら棄権。配置に `frame` がある述語は frame と表の両方に一致する役割だけ。
- 配置側は変えない: `coarse_types.K62_FRAMES`（v1 の 9 行の写し）はそのまま。v1 ⊂ v2（行単位）をテストで確かめる。
- 基点との出力の差は「新しく読めた文」だけのはず。新しい型の文が v2 でも棄権したとき、出力の 2 番目の理由は W3-b1 の `PLACEMENT_FRAME_NOT_READ:<型>` のまま残り、v2 の本当の理由は診断 `typed_explain_ja` の `w3b2` に出る（`semantic_read.py` を変えないので直せない。既知の穴に書く）。

### K161 第 2 表（v2）

先頭の 9 行は `w3b1_frames`（K62）の行と 1 字も違わない。助詞は が を に へ から で の 6 つだけ（と・まで・より は書かない）。役割は `docs/READING_CONVENTIONS.md` §2 の閉じた一覧から。期待する型は `coarse_types.NOUN_TYPES` の 17 型の部分集合。**同じ型の中で同じ助詞を持つ 2 行の期待する型は互いに素**（テストで機械的に確かめる。現在の表は同じ型・同じ助詞の行が 1 つずつ）。新しい 20 行（**登録時。表の変更記録 1・2 で P_CHANGE の 4 行・P_CONSUME の 5 行を消したので 11 行。さらに第 3 ラウンドの表の変更記録 3 で P_ACT・P_CREATE・P_EMOTION の `place/で/PLACE` の 3 行を消したので、今は 8 行（表は 17 行）**）の（役割・助詞・型）は **v1 の 9 行にすでにある組だけ**（agent/が、patient/を、goal/へ、source/から、place/で、time/に）。recipient・instrument・result・goal(に)・cause の行は 1 行も足さない。

<!-- BEGIN table:w3b4_frames -->
| 述語の型 | 役割 | 助詞 | 期待する型 | 種類 |
|---|---|---|---|---|
| `P_MOVE` | agent | が | PERSON GROUP_ORG ANIMAL | 項 |
| `P_MOVE` | goal | へ | PLACE | 項 |
| `P_MOVE` | source | から | PLACE | 項 |
| `P_MOVE` | place | で | PLACE | 付加 |
| `P_MOVE` | time | に | TIME | 付加 |
| `P_COMMUNICATE` | agent | が | PERSON GROUP_ORG ANIMAL | 項 |
| `P_COMMUNICATE` | patient | を | PERSON GROUP_ORG ANIMAL PLANT ARTIFACT SUBSTANCE_FOOD EVENT_ACT STATE_PROPERTY ABSTRACT INFO_LANGUAGE BODY_PART NATURAL_PHENOMENON WORK IDENTIFIER | 項 |
| `P_COMMUNICATE` | place | で | PLACE | 付加 |
| `P_COMMUNICATE` | time | に | TIME | 付加 |
| `P_ACT` | agent | が | PERSON GROUP_ORG ANIMAL | 項 |
| `P_ACT` | patient | を | PERSON GROUP_ORG ANIMAL PLANT ARTIFACT SUBSTANCE_FOOD EVENT_ACT STATE_PROPERTY ABSTRACT INFO_LANGUAGE BODY_PART NATURAL_PHENOMENON WORK IDENTIFIER | 項 |
| `P_ACT` | goal | へ | PLACE | 項 |
| `P_ACT` | source | から | PLACE | 項 |
| `P_CREATE` | agent | が | PERSON GROUP_ORG ANIMAL | 項 |
| `P_CREATE` | patient | を | PERSON GROUP_ORG ANIMAL PLANT ARTIFACT SUBSTANCE_FOOD EVENT_ACT STATE_PROPERTY ABSTRACT INFO_LANGUAGE BODY_PART NATURAL_PHENOMENON WORK IDENTIFIER | 項 |
| `P_EMOTION` | agent | が | PERSON GROUP_ORG ANIMAL | 項 |
| `P_EMOTION` | patient | を | PERSON GROUP_ORG ANIMAL PLANT ARTIFACT SUBSTANCE_FOOD EVENT_ACT STATE_PROPERTY ABSTRACT INFO_LANGUAGE BODY_PART NATURAL_PHENOMENON WORK IDENTIFIER | 項 |
<!-- END table:w3b4_frames -->

読む型に残る「読まない助詞」（表の外の助詞・型は今までどおり `PLACEMENT_PARTICLE_NOT_IN_FRAME`・`PLACEMENT_TYPE_MISMATCH` で棄権する）: `P_ACT` の に（する の result）、`P_CHANGE` の に（result）・を（経路）（**P_CHANGE は表の変更記録 1 で型ごと読まない型に戻した**）、`P_CREATE` の に（recipient/beneficiary・goal/place・result）・へ・から（用例が乏しい）、`P_CONSUME` の に+TIME 以外・へ（**P_CONSUME は表の変更記録 2 で型ごと読まない型に戻した**）、`P_EMOTION` の に（cause）・へ・から。すべての型で で の instrument（規約が型を決めない）（**表の変更記録 3 で、新しく読む 3 型（P_ACT・P_CREATE・P_EMOTION）は で の place も読まない**。v1 の P_MOVE・P_COMMUNICATE の で の place の行は表に残る）、を+PLACE/TIME/QUANTITY（経路・幅・量）、と・まで・より（6 つの助詞の外）。

### K162 読まない型（v2）

<!-- BEGIN table:w3b4_not_read -->
| 述語の型 | 名前 | 理由(型と助詞) |
|---|---|---|
| `P_GIVE` | GA_NI_GIVER_OR_RECEIVER | が・に の人が与え手か受け手か(もらう・借りる と あげる・渡す で逆)。型は同じ PERSON。に は goal も取る |
| `P_PERCEIVE` | GA_PERCEIVER_OR_PERCEIVED | が の人が知覚する側か知覚される側か(見る と 見える・見つかる)。に も割れる |
| `P_EXIST` | GA_ENTITY_OR_AGENT | が が entity(存在: 規約 §4.2)か agent(居住・姿勢)か。型は同じ |
| `P_POSSESS` | GA_AGENT_OR_RECIPIENT | が が agent か recipient(受ける・受け取る・得る)か。に も recipient か与え手か |
| `P_STATE` | ADJECTIVAL_PREDICATE | 形容詞・形状詞の述語(入口は形容詞の節を写さない) |
| `P_COGNITION` | GA_OBJECT_OR_AGENT | が が対象(わかる・分かる)か agent か。に・と が規約で決まらない |
| `P_CHANGE` | HE_GOAL_OR_RESULT | へ が goal(落ちる・広がる)か result(変わる: 工場から店へ変わった)か。result の型は規約が決めず PLACE も取る(店・都会・体育館)。に も result と time が重なる。表の変更記録 1(レビュー第 1 ラウンド F4・M1)で読まない型に戻した |
| `P_CONSUME` | NI_TIME_OR_PURPOSE | に+TIME が time か使い道(金を休みに使う)か。使い道は規約に役割が無く、休み・老後・正月のような行事・期間の語は TIME も取る。表の変更記録 2(レビュー第 1 ラウンド F4・M2)で読まない型に戻した |
<!-- END table:w3b4_not_read -->

読む型は 13 のうち 7（P_MOVE・P_COMMUNICATE・P_ACT・P_CHANGE・P_CREATE・P_CONSUME・P_EMOTION）、読まない型は 6（**登録時。表の変更記録 1・2 で P_CHANGE・P_CONSUME を読まない型に戻したので、今は読む型 5（P_MOVE・P_COMMUNICATE・P_ACT・P_CREATE・P_EMOTION）・読まない型 8**）。が の行が書けない型は型ごと読まない（ほぼすべての文に が があり、が を外した型は読む文が無いので、理由の文字列だけが変わって紛らわしい）。

### K163 理由の再検討（W3-b1 の理由 → W3-b2 の規則で解けるか）

判定の規則: 同じ助詞の 2 役割の期待する型の集合が **互いに素** なら解ける（W3-b2 の規則で役割が 1 つに決まる）。期待する型が重なる、または規約 §2 が型を決めない役割（result・cause・purpose・経路の を）が行の型と同じ型の充填物を自然に取るなら解けない。対象は配置 r7 の `headwords`（ns=P・DECIDED・direct・`gen_definition` なし・型 1 つ）の述語。成員は `artifacts/w3-b4/r7members/type_members.txt`（`tests/reading_soundness/w3b1_type_members.py --placement …/r7/run1` の出力）。

| 型（r7 の成員数） | W3-b1 の理由 | 再検討 | 結論 |
|---|---|---|---|
| `P_ACT`（25） | PARTICLE_ROLE_UNDECIDED | が: agent だけ。を: patient（経路の を を取る移動の動詞は成員に無い。PLACE は v1 と同じく除く）。へ+PLACE: goal。から+PLACE: source。で+PLACE: place。**に は解けない**: する が「〜を〜にする」で result を取り、型は PLACE・TIME・人に及ぶ。goal（置く・つける・入れる）・time と型が重なる | 読む: が・を・へ・から・で。に は読まない（**第 3 ラウンドの表の変更記録 3 で で を外した**: 今は が・を・へ・から。で は instrument・cause と型が重なる。反例: 兄が右で打った＝右手（instrument）を place 右と読んだ）|
| `P_CHANGE`（23） | NI_RESULT_OR_TIME | が: agent。へ+PLACE: goal。から+PLACE: source。で+PLACE: place。**に は解けない**（result が TIME を取る: 冬になる。time と重なる。result は PLACE も取る）。**を も解けない**（自動詞 落ちる の経路の を の充填物は ARTIFACT も取り、patient の 14 型と重なる） | 読む: が・へ・から・で。に・を は読まない（**登録時の結論。表の変更記録 1 で、へ も解けないと分かり型ごと読まない型に戻した**） |
| `P_CREATE`（24） | NI_RECIPIENT_OR_BENEFICIARY | が: agent。を: patient。で+PLACE: place。**に は解けない**（に+人 が recipient か beneficiary か、に+PLACE が goal か place か、に+TIME が result と重なる）。へ・から は成員の用例が乏しいので行を置かない | 読む: が・を・で（**第 3 ラウンドの表の変更記録 3 で で を外した**: 今は が・を。反例: 兄が右で絵を描いた＝右手を place 右と読んだ。兄が口で絵を描いた＝r7 の 口=PLACE は文の語義 くち でない（K173））|
| `P_CONSUME`（14） | NI_ROLE_UNDECIDED | r7 の成員に授受・手助けの動詞は無い。が: agent。を: patient。から+PLACE: source。で+PLACE: place。に+TIME: time（「〜に使う」の目的の充填物は TIME でない）。に+人・に+PLACE の行は置かない | 読む: が・を・から・で・に(TIME)（**登録時の結論。表の変更記録 2 で、に+TIME も使い道と重なると分かり型ごと読まない型に戻した**） |
| `P_EMOTION`（10） | NI_DE_CAUSE_OR_PLACE | が: agent。を: patient。で+PLACE: place（原因の で の充填物は PLACE でない）。**に は解けない**（に が原因・相手で、cause は型を決めない。TIME の語でも原因と時が割れる） | 読む: が・を・で（**第 3 ラウンドの表の変更記録 3 で で を外した**: 今は が・を。反例: 兄が段差で驚いた＝段差は原因（cause）で、place 段差と読んだ）|
| `P_GIVE`（22） | NI_ROLE_SPLIT | が・に の人が与え手か受け手かが成員で割れる（もらう・借りる と あげる・渡す）。型は同じ PERSON | 読まない。GA_NI_GIVER_OR_RECEIVER |
| `P_PERCEIVE`（23） | NI_SOURCE_OR_RECIPIENT | が の人が知覚する側か知覚される側か（見る と 見える・見つかる）。型は同じ | 読まない。GA_PERCEIVER_OR_PERCEIVED |
| `P_EXIST`（24） | GA_ENTITY_OR_AGENT | 変わらない: 存在文の主語は entity（規約 §4.2）、居住・姿勢の動詞の人の主語は agent。型は同じ | 読まない。GA_ENTITY_OR_AGENT |
| `P_POSSESS`（21） | PARTICLE_ROLE_UNDECIDED | が: 受ける・受け取る・得る の主語は recipient にも agent にも当たる（型は同じ）。に: recipient か与え手か | 読まない。GA_AGENT_OR_RECIPIENT |
| `P_STATE`（2,324） | ADJECTIVAL_PREDICATE | 変わらない | 読まない。ADJECTIVAL_PREDICATE |
| `P_COGNITION`（23） | TO_QUOTATION_NI_UNDECIDED | が: わかる・分かる は が で対象を取り、対象は人も取る → agent と重なる。に: 対象・与え手・原因で規約に役割が無いか型が決まらない。と の引用は 6 つの助詞の外 | 読まない。GA_OBJECT_OR_AGENT |

### K164 検査データの設計と受入基準

検査データ `tests/reading_soundness/ja_r10_w3b4.jsonl`（1 行 1 文。鍵: `id`・`lang`・`input`・`text`・`behavior`・`expect`・`pred_type`・`path`・`construction`・`placement`・`entry_expect`・`w3b4_expect`・`note`）。読むようになった 5 型それぞれに読む 20 以上・棄権 20 以上、読まない 6 型それぞれに棄権 3 以上。棄権の行に必ず入れる群: (a) 同じ助詞で型が 2 役割に合う文（充填物が {PLACE, TIME} の MULTIPLE で に・で、{ARTIFACT, PLACE} で で・を など）、(b) 充填物が MULTIPLE で候補の 1 つが外れる文、(c) frame の無い述語で表に無い助詞の文、(d) W1-a4 の誤読の型（否定の中の副詞・引用の と・目的語の省略）。配置は偽物（普通名詞は direct の型、固有名は UNPLACED。型は r7 の答えと矛盾させない）。期待はデータを書く時点で凍結し、配置を通した読みは凍結まで呼ばない。

受入基準（チケットの写し）:
- F1: 配置なしの出力は基点と byte 一致。既存の凍結データ（ja_r1〜r9・en）と x3 で changed=0・misread=0。
- F2: v2 の表（既存 9 行が先頭にそのまま、同じ型・同じ助詞の 2 行の期待する型が互いに素、役割が規約の一覧の中、型が 17 型の中、助詞が 6 つの中、`TYPED_FRAMES` と docs の表が同一）。v1 ⊂ v2（テスト）。
- F3: 検査データで読むべき文が読め、棄権すべき文が棄権する。誤読 0。
- F4: 中間職の未公開の文（読むようになった型ごとに 15 文以上、読む／棄権半々）で誤読 0。誤読が出た型は表から外して読まない型に戻し、その文を棄権として足す（狭める方向だけ）。
- F5（監査役が測る）: 隠しバンク B1 を入口（`VERA_PLACEMENT`）で流し、誤読 0・誤答 0 のまま正読が 11 を上回る。
- F6: 既存テストの失敗集合が基線から増えない。`check_hardcode` の失敗欄が空。

### K165 表の変更の約束

登録後の変更は **狭める方向だけ**（型を「読まない」に戻す・行を消す）。変更は「表の変更記録（W3-b4）」に日時・前後・理由・出典を書く。誤読が 1 件でも出た型は、その型の行をすべて外して `w3b4_not_read` に戻す（行だけを外して型を残すのは、その行だけが原因と示せるときに限る。語・表層の規則は足さない）。
<!-- w3b4-prereg:end -->
