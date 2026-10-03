# W3-b2 事前登録（docs/READING_SOUNDNESS.md §10B の登録時の本文。変えない）

<!-- w3b2-prereg:begin -->
登録日時: 2026-10-03 21:07:46 +0900（`date '+%F %T %z'` の出力。直前の同じ出力は 2026-10-03 21:06:11 +0900、直後は 2026-10-03 21:07:46 +0900 で、この節はその間に書いた。記録は `artifacts/w3-b2/prereg_time.txt`）
この時点で `tests/reading_soundness/w3b2_*.jsonl`・`tests/test_semantic_read_w3b2*.py` は存在しない（`tests/reading_soundness/w3b2_common.py`・`w3b2_frames_list.py`・`w3b2_census.py` と、その出力 `artifacts/w3-b2/confirmed_frames.json`・`census_de_ni.json` は、この登録より前に作った。根拠の一覧であって、検査データではない）。
出典: 中間職の指示書 `.claude/vera-audit/review-impl/W3-b2/plan.md` §3 と、チケット `W3-b2_reader_frames.prompt.md`。目的: W3-b1 の「直接の型だけで読む」を、(1) 配置の述語の枠 `frame`（W3-a3）を狭める側に使い、(2) 候補がすべて役割の期待に合う `MULTIPLE` を認め、(3) 「X の Y」を主辞の型で問い、(4) 指示詞（この・その・あの）を充填物の印として表す、ところまで広げる。**表層の規則は足さない。足すのは、型の証拠の門の拡張と、閉じた構造の検査だけ**。誤読が出たら、その構成を **棄権に戻す**（語や表層の規則を足して直さない。変更は下の「表の変更記録（W3-b2）」に日時つきで全件書く）。K62 の型の表・K63 の構成の表・K64 の標識の一覧は **広げない**（狭める変更だけ）。

### K94 制御の流れと引き金

配置を指定したときだけ動く（配置なしの出力は基点と 1 バイトも変わらない。`semantic_read._typed_reread_ja` は配置があるときだけ呼ばれる）。原則: **W3-b2 は、W3-b1 が棄権した文を、読めるときだけ上書きする。読めなければ W3-b1 の出力を 1 バイトも変えずに返す。W3-b1 が読んだ文は、述語の枠（K95）に反するときだけ棄権に変える。** したがって「W3-b1（配置 r6）と W3-b2（配置 r6）の出力の差」は、(a) 新しく読めた文、(b) 枠で読めなくなった文、の 2 種類だけである（機械で確かめる）。

1. 配置への問い合わせは、1 文の間は同じ語に 1 回だけ（`_CachedQuery`。実の問い合わせの列は、W3-b1 だけのときと、W3-b1 の計画が通った文では同じ）。引き金は、問い合わせる前に決める（`ambiguous frame role` などで W3-b1 の引き金に当たらない文は、問い合わせの数が 0 のまま）。
2. W3-b1 の引き金 `typed_trigger_ja` が `U` か `S4` のとき:
   - W3-b1 の計画が通ったなら、今のコードの結果（読めた／再読で棄権／語尾の門／派生の疑いの門）をそのまま使い、W3-b2 の計画は走らせない。読めた `U` の節にだけ、述語の枠の検査（K95）を掛け、反すれば 2 番目の理由を `PLACEMENT_FRAME_*` にして棄権する（1 番目は今の理由）。
   - W3-b1 の計画が棄権したなら、W3-b2 の計画（`U` は `typed_plan_u_w3b2_ja`、`S4` は `typed_plan_s4_w3b2_ja`）を同じ経路で試す。通り、今の写しの再実行・語尾の門・派生の疑いの門・（`U` なら）枠の検査をすべて通れば、その読みを返す。それ以外は W3-b1 の棄権の出力をそのまま返す。**W3-b2 の計画が棄権した理由は出力に足さない**（診断の関数 `semantic_read.typed_explain_ja(text, placement)` で取り出し、テストと測定物に書く）。
3. W3-b1 の引き金が None のとき、新しい引き金 `U3`（格の曖昧 で）`semantic_reader.typed_trigger_w3b2_ja(text, view)` を調べる。すべて満たすとき `U3`、ほかは None（問い合わせる前に決める）:
   - 1 文、`view.unread` が空、節がちょうど 1 つで `rule == 'frame'`、`conditions` が空（W3-b1 と同じ）。
   - 述語が読解器の 4 つの一覧（`_TRANSFER_PREDICATES`・`_GOAL_PREDICATES`・`_PLACEMENT_PREDICATES`・`_LOCATION_PREDICATES`）のどれにも無い（W3-b1 の `U` と同じ）。
   - `set(clause.unsupported)` が `{'ambiguous case role: で'}` か `{'ambiguous case role: で', 'ambiguous case role: に'}`。
   - `name == 'ambiguous'` の役割の `rule` がすべて下の表（`W3B2_AMBIGUOUS_RULES`）の 2 つのどちらか。`case:に:result|beneficiary`・`case:に:goal|purpose|addressee`・`case:に:time|result`・`case:に:agent|result`・`case:と:…`・`case:から:…`・`case:へ:…` は **対象外**（読解器が別の割れを言っている。型で上書きしない）。
   - に だけの曖昧は W3-b1 の `U` がすでに受け持つので、`U3` は で を含むときだけ。
   `U3` の計画は `U` と同じ `typed_plan_u_w3b2_ja`。読解器が決めた役割名は表と一致しなければ `PLACEMENT_READER_DISAGREES`、`ambiguous` は表が決める。で の役割は K62 の `place / で / PLACE`（付加。門 5 を掛ける）でしか決まらない。

<!-- BEGIN table:w3b2_ambiguous_rules -->
| 読解器の規則名（`ambiguous` の役割の `rule`） |
|---|
| `case:で:place|means` |
| `case:に:location|goal|time` |
<!-- END table:w3b2_ambiguous_rules -->

### K95 証拠の門の拡張と述語の枠

`placement_type` は変えない（凍結テストが直接呼ぶ）。新しい関数 `semantic_reader.placement_fit(answer, allowed, *, adjunct=False)` が、許される型の集合 `allowed` に対して、答えを次の順に調べる:

1. `placement_type(answer, adjunct=adjunct)` が型 T を返す → `T ∈ allowed` なら `('direct', (T,))`、でなければ `('mismatch', (T,))`（呼び手が `PLACEMENT_TYPE_MISMATCH:<述語の型>:<助詞>:<T>` と書く）。
2. `placement_type` の理由が `PLACEMENT_MULTIPLE` のときだけ、次の順に調べる: 答えの契約（`_placement_answer_problems` が空・`state == MULTIPLE`）、`origin == estimated` → 推定の理由（`PLACEMENT_ESTIMATED_NEAR`・`PLACEMENT_ESTIMATED_GENERATED`。推定の MULTIPLE は全候補が合っても読まない）、`decided_by` に `gen_definition` → `PLACEMENT_DIRECT_VIA_GENERATED`、`adjunct` で腕がすべて `role@` → `PLACEMENT_SLOT_EVIDENCE_ONLY`、候補の型の全部が `allowed` に入る → `('all_candidates', 辞書順の型の並び)`、それ以外 → `(None, 'PLACEMENT_MULTIPLE')`（理由の文字列は W3-b1 と同じ）。
3. それ以外の理由は `placement_type` の理由そのまま。

**全候補一致の意味**: 候補がすべて役割の期待する型に入るなら、どの候補であっても読みは同じ（読んでも偽にならない）。同点の棄権（候補から 1 つを選ぶとき）とは別の話で、1 つでも外れる候補があれば `PLACEMENT_MULTIPLE` のまま棄権する。**述語の MULTIPLE は読まない**（述語の型が割れれば枠が割れる。述語は今までどおり `placement_type` だけ）。S4 の構成の表（K63）は 1 つの役割に型が 1 つなので、S4 の部分の MULTIPLE は全候補一致にならない（`placement_type` のまま。棄権）。

`U` と `U3` の計画（`typed_plan_u_w3b2_ja`）は W3-b1 の `typed_plan_u_ja` と同じ手順で、役割ごとに、助詞が枠の行（K62）にある行について `allowed = その行の期待する型` で `placement_fit` を呼び（付加の行は `adjunct=True`）、`direct` か `all_candidates` を返す行がちょうど 1 つなら読む（0 は不一致、2 以上は `PLACEMENT_ROLE_TIE`）。述語の型が `P_` でないなどの理由・読まない型の理由は W3-b1 と同じ文字列。

**述語の枠 `predicate_frame(answer)`**: 述語の答えの `frame_status` と `frame`（W3-a3、`docs/COARSE_PLACEMENT.md` §12.10）を、狭めるためだけに使う。
- `frame_status` の鍵が無い・`NOT_CONFIRMED`・`NO_FRAME_TABLE` → 表（K62）だけで読む（従来どおり）。
- `CONFIRMED` → `frame` が §12.10 の不変条件（`frame` が空でも可の辞書、鍵がすべて格助詞 9 種、値が空でない型 id の昇順で重複の無い並び、`namespace == P`・`state == DECIDED`・`origin == direct`・`gen_frame ∈ decided_by`）を満たすとき `{助詞: 型の集合}`。破れば `PLACEMENT_FRAME_INVALID:<問題>`（棄権）。
- 上の 3 つ以外の `frame_status`（述語の門を通った後に出るはずの無い値）は `PLACEMENT_FRAME_INVALID:FRAME_STATUS_UNEXPECTED`（棄権）。
枠があるとき、役割 1 つごとに、助詞が `frame` の鍵に無ければ `PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:<P型>:<助詞>`、充填物の型（direct なら 1 つ、全候補一致なら全部）が `frame[助詞]` に **すべては** 入らなければ `PLACEMENT_FRAME_TYPE_NOT_CONFIRMED:<P型>:<助詞>:<型を + でつないだもの>`。K62 の行の判定に **加えて** 掛ける（狭めるだけ。枠にあって K62 に無い助詞・型を、読む根拠にしない）。`gen_frame` で格上げされた述語は W3-b1 の門 4 を今すでに通っている（`gen_definition` が `decided_by` に無い）ので、この登録で **枠で狭めて使う** と決める（`frame_unconfirmed` は使わない）。`typed_frame_check_ja(toks, typed, predicate_answer)` は W3-b1 の計画が通って読めた `U` の節に同じ検査を掛ける（新しく問い合わせない）。

**出所の欄 `role_basis` の値**（閉じた文法。K99 の表）: `placement_direct:<T>`（今まで）、`placement_direct_head:<T>`（K96 の主辞で決めた）、`placement_all_candidates:<T1>+<T2>[+…]`（型は辞書順）、`placement_all_candidates_head:<T1>+<T2>[+…]`。`predicate_basis` は今までどおり `placement_direct:<P型>`。

### K96 「X の Y」（名詞句の中の の 修飾）

`docs/READING_CONVENTIONS.md` §3 は「の の修飾は残す」なので、値は **句全体のまま**（今のまま。規約に欄を足す必要は無く、この登録は規約に沿う）。型は主辞 Y で問う。`semantic_reader.no_phrase_head(toks, start, end)` は、区間（指示詞の連体詞を外した後）のトークンが **すべて**「名詞（`pos2` が数詞でない）・接頭辞・接尾辞」か「`の`（`pos1` が助詞、`pos2` が格助詞）」で、`の` が 1 つ以上あり、先頭・末尾・連続の `の` が無く、最後の `の` より後ろが空でないときだけ構造に当たる（語の一覧は使わない）。主辞 = 最後の `の` より後ろのトークンの連なり。主辞の最後のトークンの `pos3` が下の表の 2 つのどちらかなら `PLACEMENT_HEAD_RELATIONAL:<pos3>`（関係・時・回数を表す名詞。句の型を主辞が決めない。棄権）。構造に当たる値は **主辞だけを問い合わせる**（句全体は問い合わせない。出所は `_head` の付いた値）。当たらない値は今までどおり値全体（W3-b1 と同じ）。`U`・`U3` の役割の値と、`S4` の部分の両方に掛ける。`S4` では、覆われていない内容語の連なり 2 つ以上が `の` 1 つだけを挟んで続くとき、それを 1 つの部分（表層 = 全体、主辞 = 後ろの連なり）にまとめてから、W3-b1 の `S4` の検査（名詞句か・孤立・直後の助詞・標識・構成の表）を **まとめた部分に** 掛ける（標識の検査は部分のすべてのトークンに掛ける）。十字は今までどおり値の表層全体を問い合わせる（`head_basis: surface`）ので、読解器の `role_basis` と十字の一致の判定は食い違いうる（既知の穴）。

<!-- BEGIN table:w3b2_head_relational_pos3 -->
| 主辞の `pos3`（`PLACEMENT_HEAD_RELATIONAL` になる） |
|---|
| `副詞可能` |
| `助数詞可能` |
<!-- END table:w3b2_head_relational_pos3 -->

### K97 指示詞（この・その・あの）を充填物の印として表す

和文だけ。指示詞の連体詞 = `pos1 == 連体詞` かつ表層が下の表の 3 語（チケットが名指した語。`semantic_read._DEMONSTRATIVES` は `どの` を含むので使わない）。タガーが `感動詞` と切った あの は連体詞でないので対象外（棄権のまま）。`どの` は疑問なので対象外（W3-c2 の穴の型）: `どの` を区間の先頭に含む役割は W3-b2 の計画が `PLACEMENT_DETERMINER_NOT_READ:<表層>` で読まず、`どの` が部分の直前にあれば K63 の `PLACEMENT_PART_NOT_ISOLATED` のまま。規約 §3 は「指示詞の連体詞は外す」。**値は今までどおり外したもの**。外した指示詞を、型の経路で読んだ節の新しい鍵 `role_flags`（`{役割: {"determiner": "この"}}`。`role_basis` の後ろ、節の最後の鍵。指示詞が無い節には付けない）に書く。`_clause_ja` は変えず、`_typed_reread_ja` が `_map_ja` の結果の節に後から足す。十字は `role_flags` を受け入れ、充填物の `flags.determiner` に写す（`docs/EVENT_CROSS.md` の変更記録）。**S4 の経路の中だけ**で扱う（`U`・`U3` の節で指示詞が区間の外に残ると読解器が `unrepresented source content` を足すので、`U`・`U3` の引き金に当たらない）:
- **(D1)** 部分の直前のトークンが指示詞の連体詞で、その連体詞の直前が W3-b1 の孤立の条件（文頭・補助記号・覆われたトークン・覆われた区間の格助詞）を満たすなら、その部分は孤立している（連体詞は部分の表層に入れない。値 = 部分）。読めたら、その役割に `determiner` を付ける。
- **(D2)** 覆われていない内容語の連なりが 0 で（W3-b1 なら `PLACEMENT_PART_NONE`）、節の役割のうち区間の直前が指示詞の連体詞のものがあり、その連体詞を区間に含めると `semantic_coord.phrase_bounded` が通り、連体詞を覆いに足すと `_uncovered_nominals` が偽になり、ほかのすべての役割の区間も `phrase_bounded` を通るとき: 指示詞の前にある役割それぞれについて、役割名（規約の名）が `event_cross.EXPECTED_TYPES` の表にあり（無ければ `PLACEMENT_DETERMINER_ROLE_UNTYPED:<役割>`）、値（K96 の主辞の規則を含む）が `placement_fit(…, EXPECTED_TYPES[役割], adjunct=役割 in ('time','place'))` で `direct` か `all_candidates` なら、その役割に `role_basis` と `determiner` を付けて読む（新しい役割は足さない。`mode` は `extra`、足す役割は 0）。どれかが通らなければ棄権（連体詞を含めても区間が閉じない・ほかに覆われない内容語が残る場合は `PLACEMENT_DETERMINER_NOT_BOUNDED`）。これは「型の証拠のある役割だけ、指示詞を表せた部分にする」規則で、型の無い役割（patient・goal など）に付いた指示詞は読まない。
- 読解器が指示詞を区間の **中に** 含めた役割（`_strip_demonstrative` が外す）は今の経路のままで、`role_flags` は付かない（既知の穴）。英語の this・that・these・those は表さない（K98）。

<!-- BEGIN table:w3b2_demonstratives -->
| 指示詞の連体詞（`W3B2_DEMONSTRATIVES`） |
|---|
| `この` |
| `その` |
| `あの` |
<!-- END table:w3b2_demonstratives -->

### K98 読まないもの（この登録で決める）

- **K62 の型の表・K63 の構成の表・K64 の標識の一覧は広げない。** したがって で は K62 の `place / で / PLACE` だけ、に は `time / に / TIME` だけが型で決まる。で の instrument、に の recipient・goal（に+PLACE）は表に行が無いので **読まない**（チケットの例文の 胡麻油・参加者・倉庫 はこの規則では読まない。広げるなら成員の確認と事前登録が先で、別の決定）。
- **数量の副詞（三度・二回・3回）は読まない。** W3-b1 の `S4` は数量を「読まない」と登録している（K63・数詞は `PLACEMENT_PART_MARKER:quant`）。読むには規約 §6 の `quantifiers` を出す必要があるが、(a) 回数の助数詞（回・度）と人や物の助数詞（人・本）を分けるのは語の一覧で、型では決まらない（`3回`・`5人` はどちらも `QUANTITY`）、(b) 漢数字の数は配置が UNKNOWN で、数への変換は表層の規則、(c) 入口は `quantifiers` を出さない（`NOT_PRODUCED`）。型の証拠だけでは決まらないので棄権のまま。
- **英語は読まない**（このチケットは日本語だけ。英語の型の経路は無い（K67）。英語の this・that・these・those を出力に写すには配置なしの経路を変えることになり、配置なしの出力を変えない原則に反する）。
- **述語が複数（関係節・条件・並列）は別チケット W3-b3、比較の述語句は規約 §4.4 の別チケット。** このチケットでは触れない。
- 述語の MULTIPLE、推定（near・generated）の MULTIPLE、`gen_definition` の MULTIPLE は全候補が合っても読まない（K95）。

### K99 理由の型・出所の欄・`role_flags`（閉じた一覧）

出力に出る W3-b2 の理由は枠の 3 つだけ（`abstain.reasons` の **2 番目**。1 番目は今の理由のまま。`kind` は今のまま）。ほかは `typed_explain_ja` の診断だけに出る。W3-b1 の理由（K65）はそのまま使い、名前を変えない。

<!-- BEGIN table:w3b2_reasons -->
| 理由 | 出力に出るか | 意味 |
|---|---|---|
| PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED:<P型>:<助詞> | 出る | 述語の枠（CONFIRMED）に助詞が無い |
| PLACEMENT_FRAME_TYPE_NOT_CONFIRMED:<P型>:<助詞>:<型+…> | 出る | 充填物の型が枠の型にすべては入らない |
| PLACEMENT_FRAME_INVALID:<問題> | 出る | 枠が §12.10 の不変条件を破る |
| PLACEMENT_HEAD_RELATIONAL:<pos3> | 診断のみ | の 句の主辞が関係・時・回数を表す名詞 |
| PLACEMENT_DETERMINER_ROLE_UNTYPED:<役割> | 診断のみ | 指示詞の前の役割が十字の型の表に無い |
| PLACEMENT_DETERMINER_NOT_BOUNDED | 診断のみ | 指示詞を含めても区間が閉じない・覆われない内容語が残る |
| PLACEMENT_DETERMINER_NOT_READ:<表層> | 診断のみ | 区間の先頭の連体詞が疑問の指示詞（どの）など、3 語でない |
| PLACEMENT_W3B2_NOT_TRIGGERED | 診断のみ | U3 にも当たらない（W3-b1 の引き金も None） |
<!-- END table:w3b2_reasons -->

`PLACEMENT_FRAME_INVALID:<問題>` の問題の閉じた一覧: `NAMESPACE_NOT_P`・`NOT_DECIDED_DIRECT`・`GEN_FRAME_NOT_IN_DECIDED_BY`・`FRAME_NOT_A_MAPPING`・`PARTICLE_NOT_CASE:<助詞>`・`TYPES_NOT_A_SORTED_LIST:<助詞>`・`FRAME_STATUS_UNEXPECTED`。

`role_basis` の値の文法（正規表現。テストが出力のすべての値に掛ける）: `placement_(direct|all_candidates)(_head)?:[A-Z_]+(\+[A-Z_]+)*`。`direct` は型が 1 つ、`all_candidates` は 2 つ以上で辞書順。`role_flags` の形: `{役割名: {"determiner": 空でない文字列}}`（役割名は節の `roles` にあるもの、鍵は `determiner` だけ）。節の鍵の順は `…, predicate_basis, role_basis, role_flags`（`role_flags` は最後）。`role_flags` は `docs/READING_CONVENTIONS.md` §1.1 の鍵ではなく、照合に使わない。

診断の関数 `semantic_read.typed_explain_ja(text, placement)` は `{"w3b1_trigger", "w3b1", "w3b2_trigger", "w3b2", "frame"}` を返す（`read()` と同じ内部の関数を同じ順で呼ぶ。別の判定を書かない）。和文だけ。

### 表の変更記録（W3-b2）

登録後の変更はすべてここに、日時・前後の差・理由・出典を書く（狭める変更だけ）。登録したときの本文は `artifacts/w3-b2/PREREG.md`（変えない）。

（登録時点: 変更なし）
<!-- w3b2-prereg:end -->

# docs/EVENT_CROSS.md 事前登録の変更記録に追記した本文

1. **2026-10-03 21:07:46 +0900（`date '+%F %T %z'` の出力。W3-b2 の事前登録 `docs/READING_SOUNDNESS.md` §10B と同じ時刻で、この記録はその間に書いた）。W3-b2 の 3 つの変更。表の中身 `EXPECTED_TYPES` と `EXPECTED_TYPES_VERSION` は変えない（変えたのは表でなく、規則と欄）。**
   - (1) 型一致の規則 6 を分ける。前: `state == MULTIPLE`（直接でも）→ `NOT_CHECKED(MULTIPLE)`。後: `state == MULTIPLE`（直接。推定は規則 5 で先に外れる）で、型が **すべて** 表の集合に入る → `AGREE_ALL_CANDIDATES`（`expected` は表の集合の辞書順、`observed` は型の辞書順。どの候補であっても期待に合う）、1 つでも外れれば `NOT_CHECKED(MULTIPLE)`。ほかの規則・順は変えない（役割が表に無い・腕が ARM_TIE などは規則 1・2 で先に外れるので `AGREE_ALL_CANDIDATES` にならない）。
   - (2) 数えの形。`VERDICTS` は 3 値のまま。新しい定数 `EXTRA_VERDICTS = ('AGREE_ALL_CANDIDATES',)`。`CrossReading.counts['agreement']` は、`AGREE_ALL_CANDIDATES` の腕が 1 つ以上あるときだけ最後に鍵 `AGREE_ALL_CANDIDATES` を足す（0 件の出力は今と 1 バイトも同じ。`counts` の上位の鍵は増やさない）。`observe`（W3-c）は `verdict == 'AGREE'` だけを許可に使うので、`AGREE_ALL_CANDIDATES` は許可にならない（保守的な側）。
   - (3) 入口の新しい欄。定数 `ENTRY_FLAG_KEYS = ('role_flags',)`（`ENTRY_BASIS_KEYS` は変えない）。`_check` は節の鍵 `role_flags` を受け入れ、形（`{役割名: {"determiner": 空でない文字列}}`、役割名は節の `roles` にあるもの、鍵は `determiner` だけ）を確かめ、破れば `ENTRY_FLAGS_NOT_WELL_FORMED`。`_filler` は `role_flags[役割]['determiner']` があれば充填物の `flags['determiner']` に写す（`quantifier` と同じ扱い。中心 `center` には入れない）。
   - 理由と出典: チケット W3-b2 の やること 4（十字の `agreement` に `AGREE_ALL_CANDIDATES` を足す）と やること 5（指示詞を充填物の `flags.determiner` に写す）。(3) はチケットの許可（「agreement の値の追加のみ」）を超えるが、やること 5 が「充填物の `flags.determiner` に写す」と求め、充填物は十字にしか無く、入口の新しい欄を `_check` が受け入れなければ `--events` が `INPUT_REJECTED` になるため、最小の変更として採る（中間職の指示書 §3.6 が決めたもの。判断記録 H134 以降に書く）。

# docs/READING_CONVENTIONS.md §3 に追記した本文

- **追記（W3-b2。2026-10-03 21:07:46 +0900。規約の規則は変えない。散文の確認と、型の経路の出力の欄の説明だけ）**: 「の」の修飾は値に残す（変えない。「X の Y」は句全体が 1 つの値で、型の経路は主辞 Y の型で問う）。指示詞の連体詞（この・その・あの）は値から外す（変えない）。型の経路（`docs/READING_SOUNDNESS.md` §10B）で読んだ節に限り、外した指示詞を節の鍵 `role_flags.<役割>.determiner` に書く。`role_flags` は §1.1 の節の鍵ではなく、照合（§8）に使わない。`どの` は疑問なので外さない・写さない（W3-c2 の穴の型）。
