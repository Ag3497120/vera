<!-- w3b1-prereg:begin -->
登録日時: 2026-10-03 14:32:17 +0900(`date '+%Y-%m-%d %H:%M:%S %z'` の出力。直前の同じ出力は 2026-10-03 14:31:13 +0900、直後は 2026-10-03 14:32:17 +0900 で、この節はその間に書いた)
この時点で `tests/reading_soundness/ja_r8.jsonl`・`en_r4.jsonl`・`tests/test_semantic_read_w3b1*.py` は存在しない(型の成員の一覧 `artifacts/w3-b1/type_members.txt` と、表の各行の確認 `artifacts/w3-b1/frame_review.md` は、この登録より前に作った)。
出典: 中間職の指示書 `.claude/vera-audit/review-impl/W3-b1/plan.md` §3。目的: 読解器が語の型が分からないために棄権している所を、粗い配置(`coarse_place.query`)の **`origin=direct` かつ `DECIDED` の型だけ** を正の証拠として読めるようにする。表層の規則は足さない。足すのは型の表と証拠の門だけ。誤読が出たら、その構成(表の行)を **棄権に戻す**(語や表層の規則を足して直さない)。表を広げる変更は、このチケットでは禁止(狭める変更だけ。変更は下の「表の変更記録」に日時つきで全件書く)。

### K62 型の表と証拠の門

配置の述語は 13 型。次の 2 型だけを読み、残りの 11 型は読まない。助詞は格助詞だけ(は・も・の は行に無い)。「期待する型」は名詞 17 型の id。種類の「付加」は、役割が time・place のとき(証拠の門 5 を掛ける)。役割 → 期待する型は、`docs/EVENT_CROSS.md` の事前登録の表にある役割(agent・recipient・place・time)では **それと同じ**(テストが `event_cross.EXPECTED_TYPES` と機械照合する)。表に無い役割(goal・source・patient)の集合だけ、この表で決める。表の行の中身は型 id・役割名・助詞だけで、語は書かない。

<!-- BEGIN table:w3b1_frames -->
| 述語の型 | 役割 | 助詞 | 期待する型 | 種類 |
|---|---|---|---|---|
| `P_MOVE` | agent | が | PERSON GROUP_ORG ANIMAL | 項 |
| `P_MOVE` | goal | へ | PLACE | 項 |
| `P_MOVE` | source | から | PLACE | 項 |
| `P_MOVE` | place | で | PLACE | 付加 |
| `P_MOVE` | time | に | TIME | 付加 |
| `P_COMMUNICATE` | agent | が | PERSON GROUP_ORG ANIMAL | 項 |
| `P_COMMUNICATE` | recipient | に | PERSON GROUP_ORG | 項 |
| `P_COMMUNICATE` | patient | を | PERSON GROUP_ORG ANIMAL PLANT ARTIFACT SUBSTANCE_FOOD EVENT_ACT STATE_PROPERTY ABSTRACT INFO_LANGUAGE BODY_PART NATURAL_PHENOMENON WORK IDENTIFIER | 項 |
| `P_COMMUNICATE` | place | で | PLACE | 付加 |
| `P_COMMUNICATE` | time | に | TIME | 付加 |
<!-- END table:w3b1_frames -->

`P_MOVE` の に+PLACE・を・まで、`P_COMMUNICATE` の と(引用)・に+人以外は、表に行が無い(助詞が枠に無いか、型が合わないので棄権する)。

読まない型(13 型のうち 11。名前は理由の短い名):

<!-- BEGIN table:w3b1_not_read -->
| 述語の型 | 名前 | 理由(型と助詞) |
|---|---|---|
| `P_GIVE` | NI_ROLE_SPLIT | に の役割が成員で割れる(agent・recipient か beneficiary・goal) |
| `P_CHANGE` | NI_RESULT_OR_TIME | に が result か time か |
| `P_CREATE` | NI_RECIPIENT_OR_BENEFICIARY | に+人 が recipient か beneficiary か |
| `P_PERCEIVE` | NI_SOURCE_OR_RECIPIENT | に が source か recipient か |
| `P_EXIST` | GA_ENTITY_OR_AGENT | が が entity(存在)か agent(居住)か |
| `P_POSSESS` | PARTICLE_ROLE_UNDECIDED | 助詞と役割の対応が型で決まらない |
| `P_ACT` | PARTICLE_ROLE_UNDECIDED | 助詞と役割の対応が型で決まらない |
| `P_STATE` | ADJECTIVAL_PREDICATE | 形容詞・形状詞の述語(入口は形容詞の節を写さない) |
| `P_COGNITION` | TO_QUOTATION_NI_UNDECIDED | と の引用(関係を写さない)、に が決まらない |
| `P_EMOTION` | NI_DE_CAUSE_OR_PLACE | に・で が名詞句の cause か place か |
| `P_CONSUME` | NI_ROLE_UNDECIDED | に の役割が決まらない(授受・手助けの動詞が同居) |
<!-- END table:w3b1_not_read -->

英語は読まない(前置詞の列。配置に英語の述語が 0 件、日常語の名詞に direct が無い)。根拠は `artifacts/w3-b1/frame_review.md`(行ごとの確認)。

**証拠の門(配置の答えを決定に使う唯一の関数 `semantic_reader.placement_type(answer, *, adjunct=False)`)**。上から順に最初に当たったもの:

1. 契約の不変条件(`docs/COARSE_PLACEMENT.md` §11.6: `DECIDED` ⇔ `len(top)==1`、`MULTIPLE` ⇔ 2 以上、ほかの state ⇔ 空、`estimated` ⇔ `constructed` ⇔ `estimate_basis ∈ {proximity, generated}`、`direct` ⇒ `estimate_basis is None`、`direct` の答えに `decided_by` がある)を破る → `PLACEMENT_INVALID`
2. `NO_PLACEMENT` → `PLACEMENT_NO_PLACEMENT:<placement.reason>`、`UNKNOWN` → `PLACEMENT_UNKNOWN`、`UNPLACED` → `PLACEMENT_UNPLACED`、`MULTIPLE` → `PLACEMENT_MULTIPLE`
3. `origin == estimated` → `proximity` なら `PLACEMENT_ESTIMATED_NEAR`、`generated` なら `PLACEMENT_ESTIMATED_GENERATED`
4. `decided_by` に `gen_definition` を含む → `PLACEMENT_DIRECT_VIA_GENERATED`(§11.6 の提案: 格上げした直接は分けて扱う余地。保守的な側を採る)
5. `adjunct=True`(役割が time・place)で、`decided_by` の腕が **すべて** `role@` で始まる → `PLACEMENT_SLOT_EVIDENCE_ONLY`(役割の分布の腕は「その位置に出た」ことしか数えず、副詞的な名詞が同じ位置に出る)
6. それ以外(`DECIDED`・`direct`)→ その型

問い合わせは **語だけ**(`context_role`・`context_predicate` を渡さない。役割の位置で推定した型で役割を決める循環を避ける)。語は出力に書く値の表記そのもの(先頭の指示の連体詞を外した後)で、主辞を取り出す規則は作らない(複合語・の 句は全体で問い合わせ、未配置・推定なら棄権)。述語は書かれた動詞の辞書形。`coarse_place.query` は必ず実在のパス付きで呼ぶ(`None` を渡さない。`VERA_COARSE_PLACEMENT` は読まない)。

### K63 読む条件

和文だけ。配置が指定されているとき、入口はまず今の経路を走らせ、今の経路が `readable: true` なら出力を 1 バイトも変えずに返す。今の経路が棄権し、次の 2 つの引き金のどちらかに当たる節があるときだけ、型で決めさせ、その結果を **今の写しの規則(`_map_ja`・`_clause_ja`)にもう一度通して** 返す。読めなければ、今の棄権の理由を先頭に残したまま `PLACEMENT_*` の理由を 1 つ足す。引き金に当たらない棄権は出力を変えない。

**経路 U(未知の述語。述語の型で項を読む)**
- 引き金(すべて満たす): 入力が 1 文、`view.unread` が空、節がちょうど 1 つで `rule == 'frame'`、`conditions` が空、`clause.predicate` が読解器の 4 つの一覧(`_TRANSFER_PREDICATES`・`_GOAL_PREDICATES`・`_PLACEMENT_PREDICATES`・`_LOCATION_PREDICATES`)のどれにも無い。さらに (U1) `unsupported == ()` で `recipient` という名の役割がある、または (U2) `set(unsupported) == {'ambiguous case role: に'}` で `ambiguous` という名の役割の `rule` がすべて `case:に:location|goal|time`。読解器が自分で割れると言った他の理由(`ambiguous frame role`・`unrepresented source content` ほか)が 1 つでもあれば引き金に当たらない(型で上書きしない)。
- 手順(最初に失敗した所の理由を 1 つ足して棄権): (1) 態が能動でなければ棄権。(2) 述語の配置(書かれた述語を問い合わせ)が門を通り、型が `P_` で始まり、読む型である。(3) 節のすべての役割について、助詞が枠のどれかの行にあり、値の配置が門を通り、期待する型に入る。候補の行がちょうど 1 つ(0 は不一致、2 以上は `PLACEMENT_ROLE_TIE`)。候補が付加の行なら門 5 を掛ける。読解器が役割名を決めているのに表の役割と違えば `PLACEMENT_READER_DISAGREES`(読解器の名が `recipient`・`ambiguous` のときだけ表が決める)。同じ役割が 2 つなら棄権。(4) 通れば、述語・態・経路の動詞とサ変の門・極性・時制・モダリティ・文全体の検査(量化の語・数詞・授受の補助動詞・文頭の接続詞・述語の覆い)は今のコードのまま走り、役割の写しのループだけが表で決めた役割に置き換わる。
- 出力の節に、`predicate_basis: "placement_direct:<P_型>"` と `role_basis: {"<役割>": "placement_direct:<型>"}`(節のすべての役割)を **最後の鍵として** 足す。

**経路 S4(表せない部分を時・場所として読む。述語の型は使わない)**
- 引き金: 入力が 1 文、`unread` が空、frame の節がちょうど 1 つ、`conditions` が空、`set(unsupported) == {'unrepresented source content'}`。U の引き金と同時には当たらない。
- 部分の取り出し(全文のトークンで行う。区間だけを解析し直さない): 覆い = 節のすべての役割の区間 + 述語の区間 + サ変の名詞。部分 = 覆われていない連続したトークンで、品詞が `_CONTENT_WORDS` に入るもの。部分が 0 なら `PLACEMENT_PART_NONE`。
- 部分ごと(1 つでも通らなければ棄権): (1) 部分のトークンがすべて名詞・接頭辞・接尾辞で、数詞を含まない(副詞・形容詞・形状詞は `PLACEMENT_PART_NOT_NP:<品詞>`、数詞は `PLACEMENT_PART_MARKER:quant`)。(2) 部分の前のトークンが、文頭・補助記号・覆われたトークン・覆われた区間の格助詞のどれかである(連体詞・動詞・助動詞などが直前にあれば `PLACEMENT_PART_NOT_ISOLATED`。名詞句の修飾を落とさないため)。(3) 部分の直後が、補助記号の `、`(助詞 ∅)か助詞(その表層)で、そのさらに次が助詞(には・では・にも・は)でない(`PLACEMENT_PART_NOT_FOLLOWED`・`PLACEMENT_PART_PARTICLE:<連なり>`)。(4) 標識(K64)が、部分のトークン・直後の助詞のどれかにあれば `PLACEMENT_PART_MARKER:<型>`。文のどこかに接続詞のトークンがあれば(覆われていても)`PLACEMENT_PART_MARKER:conn`。(5) 構成(下の表)。(6) 通れば、`time`・`place`(規約 §2 の既にある役割名だけ)の役割として節に足し、`role_basis`(足した役割だけ)を出し、今の写しにもう一度通す。既に同じ役割があれば `DUPLICATE_ROLE` で棄権。

構成の表(部分の主辞の配置が `DECIDED`・`direct` のとき。型は `placement_type(…, adjunct=True)` で決める):

<!-- BEGIN table:w3b1_part_constructions -->
| 型 | 助詞 | 役割 |
|---|---|---|
| TIME | ∅(、) | time |
| TIME | に | time |
| PLACE | で | place |
<!-- END table:w3b1_part_constructions -->

この表に無い組(は・も・の・と・や・から・まで・を・が、数量・様態の型 など)は `PLACEMENT_PART_NO_ROLE:<型>:<助詞>` で棄権する(規約 §2 に様態・数量の役割は無い。数量は `quantifiers` で、入口は出さない)。

**事前に「読まない」と登録する構成**(検査データは棄権すべき側で入れる): ∅+TIME のうち門 5 で落ちるもの(役割の腕だけの TIME)、は+TIME(主題)、様態(副詞・形状詞)、数量(数詞・助数詞)、の で名詞にかかる部分、述語が複数の文、サ変の述語(配置に無い)、は の主題の節(読解器が割れると言う)、受身・使役、英語。

### K64 標識の一覧(W1-a4 の指示書 §3.5 の一覧をそのまま写した。和文だけ。規則は写さない。照合はトークンの表層と原形)

<!-- BEGIN table:w3b1_markers -->
| 型 | 語 |
|---|---|
| neg | ない ず ぬ ません なかっ 全然 決して あまり 少しも ろくに めったに 必ずしも 全く |
| cond | もし もしも 万一 仮に たとえ ば たら なら 場合 |
| quant | (数詞 pos2) 入口の `_QUANT_SURFACES` の語 よく いつも 時々 たまに 少し たくさん ほとんど だけ しか ばかり のみ さえ |
| conn | (接続詞 pos1)(接続助詞 pos2) また さらに そして しかし だから でも |
| quote | 「 」 『 』 という そうだ らしい |
| modal | たぶん きっと おそらく ぜひ どうか どうやら もしかすると まるで |
| time_aspect | もう まだ すでに ずっと 急に 突然 やっと ついに 再び |
<!-- END table:w3b1_markers -->

### K65 理由の型(閉じた一覧)と出所の欄と配置の指定

理由は `abstain.reasons` の **2 番目** に足す(1 番目は今の理由のまま。`kind` は今のまま)。名前を変えるなら、ここに登録してからテストを書く。

<!-- BEGIN table:w3b1_reasons -->
| 理由 | 意味 |
|---|---|
| PLACEMENT_NO_PLACEMENT:<reason> | 配置が使えない(UNSET・MISSING・UNREADABLE・MANIFEST_MISMATCH) |
| PLACEMENT_INVALID[:<問題>] | 答えが契約を破る・空の語 |
| PLACEMENT_UNKNOWN | 材料に無く近さからも作れない |
| PLACEMENT_UNPLACED | 材料にあるが決める証拠が足りない |
| PLACEMENT_MULTIPLE | 型が割れた(同点は棄権) |
| PLACEMENT_ESTIMATED_NEAR | 推定(近さ)。構成であって証言でない |
| PLACEMENT_ESTIMATED_GENERATED | 推定(生成)。構成であって証言でない |
| PLACEMENT_DIRECT_VIA_GENERATED | 生成した定義の格上げで direct になった語 |
| PLACEMENT_SLOT_EVIDENCE_ONLY | 付加の語で、役割の分布の腕だけが決め手 |
| PLACEMENT_VOICE_NOT_ACTIVE | 態が能動でない(表は能動の枠だけ) |
| PLACEMENT_PREDICATE_NORMALIZED | 書かれた述語が読解器の述語と違う |
| PLACEMENT_NOT_PREDICATE_TYPE | 述語の型が P_ で始まらない |
| PLACEMENT_FRAME_NOT_READ:<型> | 読まない型 |
| PLACEMENT_PARTICLE_NOT_IN_FRAME:<型>:<助詞> | 助詞が枠のどの行にも無い |
| PLACEMENT_TYPE_MISMATCH:<型>:<助詞>:<名詞の型> | 名詞の型が期待する型に入らない |
| PLACEMENT_ROLE_TIE | 候補の行が 2 つ以上 |
| PLACEMENT_READER_DISAGREES:<読解器>:<表> | 読解器が決めた役割名と表が違う |
| PLACEMENT_DUPLICATE_ROLE:<役割> | 同じ役割が 2 つ |
| PLACEMENT_PART_NONE | 表せない部分が見つからない |
| PLACEMENT_PART_NOT_NP:<品詞> | 部分が名詞句でない |
| PLACEMENT_PART_NOT_ISOLATED | 部分の直前に覆われていない修飾などがある |
| PLACEMENT_PART_NOT_FOLLOWED | 部分の直後が助詞でも `、` でもない |
| PLACEMENT_PART_PARTICLE:<連なり> | 助詞が連なる(には・では・にも・は) |
| PLACEMENT_PART_MARKER:<型> | 否定・条件・量化・接続・引用などの標識(K64) |
| PLACEMENT_PART_NO_ROLE:<型>:<助詞> | 構成の表に無い組 |
| PLACEMENT_PREDICATE_UNIDENTIFIED | 英語: 動詞が特定できない |
| PLACEMENT_REREAD_ABSTAINS:<理由> | 型で決めた役割で今の写しにもう一度通したが、今の規則が棄権した |
<!-- END table:w3b1_reasons -->

門の理由(`PLACEMENT_NO_PLACEMENT`・`INVALID`・`UNKNOWN`・`UNPLACED`・`MULTIPLE`・`ESTIMATED_*`・`DIRECT_VIA_GENERATED`・`SLOT_EVIDENCE_ONLY`)には、語の位置を `:<位置>:<語>`(位置は `predicate`・助詞・`part`)で付ける。英語の `UNKNOWN_PREDICATE` には、配置が指定されているときだけ、先頭の動詞の `en.lemma` を問い合わせた門の理由(`...:predicate:<語>`)か、門が型を返しても `PLACEMENT_FRAME_NOT_READ:en` を足す(英語は読まない)。英語の付加語(`UNREPRESENTED_CONTENT:<語>`)は変えない。

**出所の欄**: 型で決めた節にだけ、節の鍵を最後に足す。U は `predicate_basis`(`placement_direct:<P_型>`)のあとに `role_basis`、S4 は `role_basis` だけ。既存の鍵の値と順は変えない。上位の鍵は足さない。十字は `ENTRY_BASIS_KEYS = ('predicate_basis', 'role_basis')` を受け入れ、節にあるときだけ `provenance` に同じ名前・同じ値で写す(`center` には入れない)。`CLAUSE_KEYS` は変えない(規約 §1.1 の表と一致するテストがある)。

**配置の指定**: `semantic_read.read(text, lang=None, *, placement=<番兵>)`(番兵は `VERA_PLACEMENT`。空・未設定は配置なし、`None` は配置なし、文字列はパス、`query(term)` を持つ物はそのまま)。`main()` は `--` より前の完全一致の `--placement=<dir>`・`--placement <dir>` だけを取り出す(パーサには登録しない。略記は今までどおり `BAD_ARGUMENTS`)。値なし・空・2 回は `BAD_ARGUMENTS`。順位は 引数 ＞ `VERA_PLACEMENT`。配置なしのとき出力は基点とバイト一致で、`coarse_place`・`coarse_types`・`event_cross` を import しない。

### 表の変更記録

(空。登録後の変更はすべてここに、日時・前後の差・理由・行を書く。)
<!-- w3b1-prereg:end -->
