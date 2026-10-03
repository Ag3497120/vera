<!-- w1a5-prereg:begin -->
登録日時: 2026-10-04 05:15:13 +0900（`date '+%F %T %z'` の出力）。直前のコミット: `df4f001e1f3027192b0006e8c9a54b4a164088c3`（作業木 `ticket/W1-a5`、未コミットの変更なし）。
この時点で **無い** ファイル: `tests/reading_soundness/ja_r12.jsonl`、`tests/test_semantic_read_w1a5.py`、`artifacts/w1-a5/` の測定物（`prereg_time.txt`・`isolation_check.txt`・`index_search.txt` を除く）、`semantic_reader.py` の W1-a5 の区画。
出典: チケット `W1-a5_convention_slots.prompt.md` と中間職の指示書 `W1-a5/plan.md`（Claude Opus 5.5）。規約 `docs/READING_CONVENTIONS.md` §3（述語）・§4.3・§5（極性・時制）・§6（量化）・§9.1（未決）。

### 位置づけ

B1（r8）の日本語の棄権のうち「表せない部分（unrepresented source content）」が理由の文の中身は (a) 相の助動詞 (b) 数量の副詞（遊離した数量）(c) 副詞 (d) 「X の Y」の修飾の重なり、だった。W1-a4 の教訓（表層の規則で読む範囲を広げると未公開の文で誤読が出る）に従い、ここでは **規約が名指しする閉じた文法の類** だけを規約の欄に写す。相の助動詞の一覧は読解器の語の一覧ではなく **規約 §3 の列挙の写し**。副詞は意味を決めず **印** として残す（黙って落とさない）。(d) は W3-b2 に欄があり、このチケットでは扱わない。英語は触らない。

### K210 制御の流れ（登録）

1. 入口 `semantic_read._read_ja` を、モジュールの末尾で `w1a5_wrap` が包む（`semantic_read.py` に 2 行。`_read_ja` の本文は 1 字も変えない）。包みは `(text, placement=None)` を受け、`W1A5_DEPTH[0] > 0`（基点の `_read_ja` を呼んでいる間と、W3-b3 の節ごとの読みの間）なら基点をそのまま呼ぶ。深さ 0 のとき、深さを 1 にして基点の出力 `out` を得て（`try/finally` で戻す）、次の 3 つのどれかだけを行う。それ以外は `out` と **同じオブジェクト** を返す。
   - (a) `out['readable']` が真 → K211 の相の規則だけを掛ける。基点と同じ極性・時制なら何もしない。違えば節の `polarity`・`tense` だけを替えた写しを返す（`aspect_corrected`）。門に当たれば棄権（`aspect_refused`）。
   - (b) 偽で、再読の引き金（下）に当たる → K211〜K213 の門を順に掛け、読めれば K214 の読み（`reread`）、門に当たれば基点の棄権の理由の **後ろに** W1-a5 の理由を 1 つ足して棄権（`reread_refused`）。
   - (c) それ以外は何もしない（`not_triggered`）。
2. 配置の有無で W1-a5 の判断は変わらない（配置に問い合わせない）。
3. 最後の判断を診断用に `W1A5_LAST` に記録し、`w1a5_explain_ja(text, placement=None)` は `semantic_read.read(text, 'ja', placement=placement)` を自分で走らせてその記録の写しを返す（第二の判断を書かない）。形: `{'path': 'not_triggered'|'aspect_kept'|'aspect_corrected'|'aspect_refused'|'reread'|'reread_refused', 'reason': None|str, 'aspect': None|{'aux','polarity','tense'}, 'adverbs': [表層…], 'quantity': None|{'surface','value','counter','key'}}`。
4. 最初にトークンの値の写し（表層・pos1〜4・cForm・原形・lemma・lForm・文字位置）を取り、以後はその写しだけで判断する（タガーのノードは次の解析で壊れうる）。`_map_ja` に渡すトークン列は呼ぶ直前に取り直す。

**再読の引き金**（すべて満たすとき。満たさなければ何もしない）:
- T1 文が 1 つ（`R._sentences(text)` が 1 区間）で `view.unread` が空（`view = R.document_view({'d': text})`）。
- T2 `view.clauses` のうち rule が `frame` の節がちょうど 1 つ。ほかの節は、構文の節 `gold_quantity` で、その述語の区間が frame の節と同じ・`quantity` 以外の役割が frame の節と同じ・`quantity` の区間が W1-a5 の見つけた数量と同じものだけ（違えば `COMPETING_READINGS:gold_quantity`）。
- T3 その frame の節の `unsupported` が `{'unrepresented source content'}` だけ。
- T4 覆われない内容語が 1 つ以上あり、そのすべてが「品詞 副詞 のトークン」か「1 つの数量（K212 Q1 の形）のトークン」。覆い = 節の役割の区間 ∪ `R._predicate_coverage`。内容語 = `R._uncovered_nominals` と同じ品詞（名詞・代名詞・形容詞・形状詞・副詞・接頭辞・接尾辞）。ほかに覆われない内容語があれば当たらない。

**振る舞いの約束**（テストで確かめる）: (1) W1-a5 が何もしない入力の出力は基点の出力と同じオブジェクト。(2) 配置の有無で判断が変わらない。(3) W1-a5 が読んだ節には必ず `quantifiers` か `flags` か相の連鎖がある。(4) 読めた出力に W1-a5 が掛けて変えるのは `polarity`・`tense` だけ、または棄権。

### K211 相の補助動詞（規約 §3 の写し）

- **一覧**（規約 §3 の「〜ている／〜てしまう／〜ておく」の写し。テストが規約の文から機械で取り出して一致を確かめる）。語を足して直さない。

<!-- BEGIN table:w1a5_aspect_aux -->
| lemma | 表記 | 規約の出典 |
|---|---|---|
| 居る | いる | §3 述語「〜ている」 |
| 仕舞う | しまう | §3 述語「〜てしまう」 |
| 置く | おく | §3 述語「〜ておく」 |
<!-- END table:w1a5_aspect_aux -->

- **連鎖の形**: 節の述語の頭の動詞（サ変は する のトークン）か、その直後の態の助動詞（れる・られる・せる・させる）の直後に て／で（助詞-接続助詞）、その直後に 動詞-非自立可能 のトークン（補助動詞）。`ないで`・`ずに` の後の いる は連鎖に数えない（基点のまま）。
- **語尾の表**（補助動詞の活用形 cForm の頭と、その後ろ文末までの助動詞の原形の並び → 極性・時制。極性は §5 で決める。基点の節の極性は信じない）:

<!-- BEGIN table:w1a5_aspect_endings -->
| 補助動詞の cForm | 後ろの助動詞の原形 | polarity | tense |
|---|---|---|---|
| 終止形 | (なし) | + | nonpast |
| 連用形 | た | + | past |
| 連用形 | ます | + | nonpast |
| 連用形 | ます た | + | past |
| 未然形 | ない | - | nonpast |
| 未然形 | ない た | - | past |
| 連用形 | ます ぬ | - | nonpast |
| 連用形 | ます ぬ です た | - | past |
<!-- END table:w1a5_aspect_endings -->

- **門**（この順。最初に当たった理由を返す）:
  1. 補助動詞の lemma が一覧に無い（見る・有る・行く・来る・上げる・呉れる・貰う …）→ `ASPECT_NOT_IN_CONVENTION:<原形>`。てある はここ（H211）。授受は基点がすでに `BENEFACTIVE_NOT_PRODUCED` で棄権しているので、基点の出力が読めていなければ何もしない。
  2. 補助動詞の後ろにまた連鎖（てしまっている・ておいてある）→ `ASPECT_CHAIN_NOT_READ`。
  3. 語尾が表に無い（ば・たら・ても・ように・だろう・たい・なくはない・ないわけではない・命令形・意志形 …）→ `ASPECT_ENDING_NOT_READ`。
  4. 縮約形（てる・でる・ちゃう・じゃう。H212）: 読めた出力で、縮約の助動詞の後ろに ない・ぬ・ず・ます（未然形）がある → `ASPECT_CONTRACTED_NEGATION`。再読の中の縮約形 → `ASPECT_CONTRACTED`。それ以外の縮約形は何もしない。
  5. 出力の節が 2 つ以上: 連鎖のどれかが門 1〜3 に当たるか、補助動詞の直後が否定（ない・ぬ）なら `ASPECT_MULTI_CLAUSE`。当たらなければ何もしない。
  6. 出力の節が 1 つで連鎖の頭が節の述語でない → `ASPECT_NOT_ON_PREDICATE`。
- モダリティ・態は基点の判断のまま（`_MODAL_MARKS` などは入口が見ている）。

### K212 遊離した数量（規約 §6・§4.3 の写し）

- **Q1 形**: 連続する `名詞-数詞` のトークン（1 つ以上）＋その直後の助数詞のトークン 1 つ。助数詞のトークン = pos1 `接尾辞`・pos2 `名詞的` のもの、または pos1 `名詞`・pos3 `助数詞可能` のもの。種類: (i) 表層が 回・度 → event、(ii) 接尾辞（名詞的）→ 名詞句にかかる数、(iii) それ以外の 助数詞可能 の名詞（時間・円・キロ・リットル・台・杯 …）→ 単位（Q7 で棄権）。数詞の直後が助数詞のトークンでない形は数量ではない（引き金 T4 に当たらない）。1 文に 2 つ以上 → `QUANTIFIER_TARGET_UNDETERMINED:two`。
- **Q2 値**（数詞の品詞と字種で決める）: 数詞のトークンの表層を連結し NFKC。すべて ASCII の数字 → 整数。すべて下の表の漢数字 → 位取りの漢数字として変換（十・百・千 は前に数字が無ければ 1、万 は大きい位）。それ以外（`〇`・`数`・`何`・`幾`・`、`・小数点・数字と漢字の混在）・変換の失敗・値 0 → `QUANTIFIER_VALUE_UNDETERMINED:<表層>`。値は `exactly:N`（N は算用数字の文字列）。

<!-- BEGIN table:w1a5_numerals -->
| 種類 | 字 |
|---|---|
| digits | 一 二 三 四 五 六 七 八 九 |
| units | 十 百 千 万 |
<!-- END table:w1a5_numerals -->

- **Q3 位置**: 数量のトークンがどの役割の区間の中にも無い（中にあれば引き金に当たらない。H215）。助数詞の **直後のトークンが節の述語の区間の頭**（サ変は名詞のトークン）であること。違えば（三冊も・三冊ずつ・三人で・三人の・三回目・三冊ゆっくり …）→ `QUANTIFIER_TARGET_UNDETERMINED:position`。
- **Q4 時**: 数量の表層が `semantic_reader._TIME_NUMERIC_HEAD` に全体一致 → `QUANTIFIER_TARGET_UNDETERMINED:time`。
- **Q5 event**: 助数詞が下の 2 語 → キー `"event"`。ただし 度 で、数詞の直前のトークンが格助詞 が・を → `QUANTIFIER_TARGET_UNDETERMINED:unit`（H216）。

<!-- BEGIN table:w1a5_event_counters -->
| 助数詞 | キー | 規約の出典 |
|---|---|---|
| 回 | event | §6 回数（N 回押した の型） |
| 度 | event | §6 回数 |
<!-- END table:w1a5_event_counters -->

- **Q6 名詞句**（(ii) の助数詞）: **直前の名詞句 = 同じ節の中で数量の直前にある、格助詞つきの名詞句**。数詞の直前のトークンが格助詞 が か を（pos2 `格助詞`）で、その直前で終わる区間を持つ役割が節にあること。無ければ（文頭・は・も・に・で …）→ `QUANTIFIER_TARGET_UNDETERMINED:no_phrase` または `:particle`。が の場合に、節の を の句がその が の句より前にある → `…:scrambled`（H214）。**割れたら棄権**。
- **Q7 単位**: Q1 の (iii) → `QUANTIFIER_TARGET_UNDETERMINED:unit`（引き金には当てて理由を残す。三時間 は Q4 が先に `time` で止める）。
- **Q8 範囲**（再読の後、出力の節で）: 節の極性が −、モダリティが null 以外、態が active 以外 → `QUANTIFIER_SCOPE_UNDETERMINED:<neg|modality|voice>`。
- **Q9 役割**: キーにする役割は、が → `agent` か `entity`、を → `patient`（出力の節の `roles` で値が一致する役割名）。それ以外・見つからない → `QUANTIFIER_TARGET_UNDETERMINED:role`。
- 量化の語を含む複合語（一人・二人・一緒・一番・三日月 …）はタガーが数詞にしないので数量にならない（覆われない名詞・副詞として残り、引き金と副詞の門で決まる）。

### K213 副詞の印（規約 §2「副詞は役割にしない」の欄の追加）

品詞 副詞 のトークンだけを対象にする（急に・静かに・簡単に は形状詞＋に で対象外。H217）。各副詞トークンに順に:

- **A1 標識**: K64（`W3B1_MARKERS_JA` の 7 類。参照し、写さない。表層・原形・lemma・lForm を平仮名にした読み のどれかが一致。多分・恐らく の漢字表記を捕まえるため。H218）→ `ADVERB_MARK_NOT_READ:<類>:<表層>`。入口の `_QUANT_SURFACES` → `…:quant:<表層>`。規約が別の欄の印として名指しする語 → `…:convention:<表層>`。登録した類 → `…:modal:<表層>` / `…:approx:<表層>`。
- **A2 比較**: 文に助詞 より・ほど・くらい・ぐらい（または表層 より の副詞）がある → `COMPARISON_NOT_READ`。
- **A3 連続・接続**: 副詞の直後が副詞・接続詞・読点＋接続詞 → `ADVERB_STACKED`。
- **A4 名詞句の修飾**: 副詞（とその直後の と／に の助詞）の直後から役割の区間が始まるとき、その区間の最初のトークンが 名詞-普通名詞（pos3 が 副詞可能・助数詞可能 でない）・名詞-固有名詞・代名詞 のどれかで、区間の中に の・連体詞・形容詞・形状詞・動詞・数詞・接頭辞 が無いときだけ境界として認める。それ以外 → `ADVERB_MAY_MODIFY_NP:<表層>`。
- **A5 数量と同居**: 同じ文に K212 の数量がある → `ADVERB_WITH_QUANTITY`。
- **A6 範囲**（再読の後）: 節の極性が −、モダリティが null 以外 → `ADVERB_SCOPE_UNDETERMINED:<neg|modality>`。
- 役割の区間の端: 読解器が `phrase_bounded` で落とした役割（副詞の直後で始まる句）は A4 を通れば境界として認め、それ以外の役割はすべて `R.phrase_bounded(R.tag(text), 始, 終)` が真であること（偽 → 引き金に当たらないのと同じ扱いで何もしない）。

登録する副詞の類（**棄権を増やす向きだけ**。規準を文で書き、語はこの表の語だけ。登録後に語を足して誤読を直さない。K218）:
- `convention`: 規約が別の欄の印として名指しする語。規約 §4.4 の最上級（一番・最も）と §6 の `ちょうど`（exactly）。
- `modal`: 規約 §5 のモダリティの印で K64 に無いもの。
- `approx`: 副詞を外すと出来事の成立が含意されない近似・未遂の副詞。

<!-- BEGIN table:w1a5_adverb_classes -->
| 類 | 語 | 規準 |
|---|---|---|
| convention | 一番 最も ちょうど | 規約 §4.4 の最上級・§6 の exactly を名指しする語 |
| modal | どうぞ ひょっとすると ひょっとしたら もしかしたら | 規約 §5 のモダリティの印（request・possibility）で K64 に無い語 |
| approx | ほぼ だいたい 大体 あやうく 危うく | 副詞を外すと出来事の成立が含意されない近似・未遂 |
<!-- END table:w1a5_adverb_classes -->

比較の助詞（A2）: `W1A5_COMPARISON_PARTICLES` = より・ほど・くらい・ぐらい。

### K214 再読と出力

- `E = semantic_read`。`toks2 = R._tokens(text)` を取り直し、数量のトークン（数詞と助数詞）**だけ** を除いた列 `masked` を作る（副詞は除かない）。`E._map_ja(text, masked, SimpleNamespace(clauses=(replace(frame, unsupported=()),), unread=()), R)` を呼ぶ。`_Abstain` → `REREAD_ABSTAINS:<その理由>`（入口の門 `_QUANT_SURFACES`・命令形・可能形の疑い・受身の門などはすべて今のまま働く。迂回しない）。
- 再読の節に K211 の相の規則を掛け（棄権なら理由）、Q8・Q9・A6 を掛ける。
- 出力の節の鍵の順: `predicate, roles, polarity, tense, modality, voice`（`_clause_ja` の出力そのまま）の後ろに、数量があれば `quantifiers`、副詞があれば最後に `flags`（`{"adverbs": [表層, …]}`。文中の出現順。副詞のトークンの表層だけ）。
- 出力全体は `E._answer('ja', [節], [], meta, out['unsupported'])`（`unsupported` は基点の棄権の出力が持っていたもの。W3-b1 の S4 と同じ扱い）。
- `flags` は規約 §1.1 の鍵ではなく、照合（§8）に使わない（W3-b2 の `role_flags.determiner` と同じ形で `docs/READING_CONVENTIONS.md` §3 に追記する）。採点アダプタは読まない欄。

### K215 理由の型（閉じた一覧）

出力に出る W1-a5 の理由は、基点の棄権の理由の **後ろ** に 1 つ足す（基点の理由の並びは今のまま。`kind` は基点のまま。読めた出力に相の門が当たったときは `kind: not_supported`、理由は 1 つ）。

<!-- BEGIN table:w1a5_reasons -->
| 理由 | 意味 |
|---|---|
| ASPECT_NOT_IN_CONVENTION:<原形> | 補助動詞が規約 §3 の列挙に無い（てみる・てある・ていく・てくる …） |
| ASPECT_CHAIN_NOT_READ | 補助動詞の後ろにまた連鎖がある |
| ASPECT_ENDING_NOT_READ | 補助動詞の語尾が表に無い |
| ASPECT_CONTRACTED_NEGATION | 縮約形の後ろに否定がある（読めた出力の極性が決まらない） |
| ASPECT_CONTRACTED | 再読の中の縮約形 |
| ASPECT_MULTI_CLAUSE | 2 節以上の出力で、補助動詞の連鎖が決まらない |
| ASPECT_NOT_ON_PREDICATE | 連鎖の頭が節の述語でない |
| QUANTIFIER_TARGET_UNDETERMINED:<two\|unit\|time\|position\|particle\|no_phrase\|scrambled\|role> | 数量のかかり先・種類が決まらない |
| QUANTIFIER_VALUE_UNDETERMINED:<表層> | 数詞の値が決まらない |
| QUANTIFIER_SCOPE_UNDETERMINED:<neg\|modality\|voice> | 否定・モダリティ・態の中の数量 |
| COMPETING_READINGS:gold_quantity | 構文の節 `gold_quantity` が W1-a5 の読みと整合しない |
| ADVERB_MARK_NOT_READ:<類>:<表層> | K64・入口の量化の語・規約の名指し・登録した類の副詞 |
| COMPARISON_NOT_READ | 比較の助詞のある文 |
| ADVERB_STACKED | 副詞が連続する・接続詞を挟む |
| ADVERB_MAY_MODIFY_NP:<表層> | 副詞の直後の句が名詞句の内側を修飾しうる形 |
| ADVERB_WITH_QUANTITY | 数量と副詞の同居 |
| ADVERB_SCOPE_UNDETERMINED:<neg\|modality> | 否定・モダリティの中の副詞 |
| REREAD_ABSTAINS:<理由> | 入口の既存の門が再読を棄権した |
<!-- END table:w1a5_reasons -->

### K216 出力の欄

- `quantifiers`: 規約 §6 の形。回数 `{"event": "exactly:N"}`、名詞句 `{"patient": "exactly:N"}`（キーは役割名）。節の鍵の順では `voice` の後ろ。
- `flags`: `{"adverbs": [表層, …]}`。節の鍵の順では最後。`role_flags`・`predicate_basis`・`role_basis` は W1-a5 の読みには付かない。
- 十字（`event_cross.validate`）は節の鍵 `flags` を `UNKNOWN_CLAUSE_KEY:flags` で拒む（H220）。`quantifiers` は受け取る。

### K217 検査データの設計と受入基準（チケットの写し）

- `tests/reading_soundness/ja_r12.jsonl`（新規。期待を先に書いて凍結。実装に通さない）: **相 40**（読む 20・棄権 20）、**数量 40**（読む 20・棄権 20）、**副詞 40**（読む 20・棄権 20）。行の形は W3-b4 の `ja_r10_w3b4.jsonl` と同じ（`id`・`lang`・`category`・`behavior`・`input`・`text`・`expect`・`entry_expect`・`w1a5_expect`・`construction`・`note`）。読む行には必ず `must_not` を 1 つ以上。棄権が正解の群: 相（てみる・てある・ていく・てくる・てしまっている・ていなくはない・ていないわけではない・ていたら・ているだろう・ていたい・縮約形の否定・2 節の文の ていない・まだ／もう＋ていない）、数量（期間・名詞の助数詞・に の後・かき混ぜ・は／も の後・三冊も／ずつ／しか／だけ・三人の＋名詞・数詞が値に溶ける・が／を の後の 度・三回目・第三・二、三個・数個・何個・否定の数量・副詞と同居・量化の語を含む複合語）、副詞（K64 の各類・否定の焦点・モダリティ・名詞句の修飾・比較・副詞の連続・一番／ちょうど／ほぼ・数量と同居・接続詞を挟む）。
- **C1**: 既存の凍結データ（今ある ja・ja_r2〜r6・ja_r8〜r10・ja_r10_w3b4・table7・en・en_r2・en_r4・a3*・w3b2_*・w3b3_*）と x3 で `misread=0`。配置なしの出力が変わる文は **全件列挙** し「新しく読めた（正読）／棄権のまま理由が変わった／読みが変わった（読めた→別の読み）／読めた→棄権（相の門）」に分け、読みが変わった文は 0（H210 の基点の誤読の訂正は別欄に数え、凍結データでは 0 を示す）。
- **C2**: 検査データで誤読 0、相・数量・副詞の各 20 文が読める。
- **C3**: 中間職の未公開の文（各 30 文以上、期待を先に凍結）で誤読 0。誤読が出た構成は棄権に戻す。
- **C4**（監査役が測る）: B1（r8）で誤読 0・誤答 0 のまま、正読が 11 を上回る。実装役は測らず、見込みも書かない。
- **C5**: 既存テストの失敗集合が基線 `dev_df4f001_failures.txt` から増えない（byte 一致・ハッシュ固定の衝突は申告）。`check_hardcode` の失敗欄が空。

### K218 変更の約束

登録の後の変更は **狭める方向だけ**（門を足す・類を棄権に戻す）。変更は「変更記録」に日時（`date '+%F %T %z'`）・前後・理由・出典を書く。**語を足して誤読を直さない**: 誤読が出たら、その構成（相の 1 形・数量の 1 規則・副詞の印全体 のどれか）を棄権に戻す。副詞の印で誤読が出て構造の門（否定・位置・隣接）で説明できないときは、K213 を丸ごと棄権に戻す（引き金 T4 から副詞を外す）。

### 判断記録（登録の一部。H210〜H225。データより前に書く）

- **H210 相は棄権した文だけの話ではない**: 基点は ている／ていない をすでに読んでいて、ていない・ていなかった・ています・ていません を `+` と誤読する（実測は指示書の証拠）。表せない部分の理由になっているのは相でなく、同じ文の副詞。だから相の規則は (a) 読めた出力の後処理（極性・時制の決め直し、規約に無い補助動詞の棄権）と (b) 再読の中、の両方に掛ける。基点の誤読の訂正は `readable→readable` の差として全件列挙し、1 件ずつ規約 §5 で正しいことを示す。凍結データでの件数は **実測で確かめて** 報告する（C1 は 0 件を求める）。
- **H211 てある は棄権**: チケットの目的 (1) は てある を含むが、規約 §3 の列挙に てある は無く、§9.1 は 〜てみる・〜てある・〜ていく・〜てくる の書き方を未決としている。てある は格の写し方も変える（窓が開けてある の 窓 は patient）。チケットの「やること 3」も「規約に無い形は棄権」と書く。規約 §3 の写しに忠実に棄権（チケットの文言との差）。
- **H212 縮約形は新しくは読まない**: てる・でる・ちゃう・じゃう は規約 §3 の字面に無い。基点が読めた出力は変えない。縮約形の直後に否定があれば棄権。再読の中の縮約形は棄権。
- **H213 助数詞は品詞で絞り、時間・単位は棄権**: チケットの「回・度 → event、それ以外 → 直前の名詞句の役割」だけでは、期間・単位を数として読む誤読が出る。助数詞のトークンの品詞が 接尾辞（名詞的）のものだけを数にし、名詞の助数詞（時間・円・キロ・台・杯 …）と `_TIME_NUMERIC_HEAD` に当たるものは棄権。
- **H214 直前の名詞句が割れる文は棄権**: 数詞の直前が格助詞 が か を のときだけ決める。が の場合、を の句が先にあれば棄権（かき混ぜ）。に・で・から・へ・と・まで・より・は・も の直後、直前に句が無い数量は棄権。チケットの「割れたら棄権」を狭める側に具体化した。
- **H215 数詞が役割の値に溶けている文は読まない**: 値から数量を剥がすのは表層の切り直しになる。
- **H216 度 は単位（温度・角度）と割れる**: 数詞の直前が が・を のときは棄権。回 にはこの門を掛けない。
- **H217 副詞の印は品詞 副詞 のトークンだけ**（チケットどおり）。形状詞＋に は対象外。
- **H218 K64 の照合は lemma と読みでも**: 多分・恐らく は表層・原形が K64 の たぶん・おそらく と一致しない。読みでの照合は棄権を増やす向きだけ。
- **H219 W1-a4 の誤読の型の門を使う**: 否定・モダリティのある節では副詞を印にしない、副詞の直後が名詞句の内側を修飾しうる形なら棄権、接続詞を挟む・副詞が連続するなら棄権、比較の文では読まない、数量と副詞の同居も読まない。W1-a4 のコードは持ち込まない。
- **H220 `flags` は十字が拒む（申告）**: 鍵の名前はチケットどおり `flags`。`event_cross.py` は触れないので、副詞の印つきの読みは十字で `INPUT_REJECTED:UNKNOWN_CLAUSE_KEY:flags`（基点ではその文は棄権 → ABSTAINED だった）。統合時に `event_cross.ENTRY_FLAG_KEYS` へ `flags` を足す 1 行が要る。
- **H221 差し込みは `_read_ja` の外（モジュールの末尾の包み）**: `test_question_cross` が `_read_ja` などの本文の sha256 を固定しているので、`_read_ja` の中に足さない。`semantic_read.py` の `if __name__ == '__main__':` の直前に 2 行。`tests/test_semantic_read_w3b4.py` の「`semantic_read.py` の差分が 0」の 1 件はチケットの許可（差し込み 2 行）と衝突する（申告）。
- **H222 `semantic_reader.py` の末尾に足す**: W3-b4 の構造テストの 1 件（ファイルの最後の 3 文が W3-b4 の名前の差し替えであること）が落ちる（申告）。チケットは「末尾に新しい区画」を指示している。W1-a5 の区画は `typed_plan_u_ja`・`typed_plan_u_w3b2_ja` を再代入しない。
- **H223 凍結データの名前**: チケットの「ja_r1〜r11」のうち、この木に `ja_r7.jsonl`・`ja_r11.jsonl` は無い。対象は今ある一覧（K217）。新しいデータは `ja_r12.jsonl`。
- **H224 番号**: §10G、K210〜、判断記録 H210〜、既知の穴 K230〜、測定結果 K225。
- **H225 `NOT_PRODUCED['quantifiers']` の文言は直せない（既知の穴）**: 「数量は全部読まない」と書いたまま。定数は `test_question_cross` がハッシュで固定し、`semantic_read.py` には 2 行しか足せない。統合時に監査役が文言を直す候補として申告する。
<!-- w1a5-prereg:end -->
