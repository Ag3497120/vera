<!-- w3b6-prereg:begin -->
起票 2026-10-04（基点 dev `51c9693`）。チケット `review-impl/prompts/W3-b6_reader_role_frames.prompt.md`、中間職の指示書 `review-impl/W3-b6/plan.md`。この節は、検査データ（`tests/reading_soundness/ja_r13.jsonl`）・テスト・実装より **前** に書く（時刻は `artifacts/w3-b6/prereg_time.txt`）。

### 目的
充填物の型でも述語の型の枠でも、で・に・へ・から の役割は決まらない（K183・K220）。述語ごとには役割はほぼ決まる。配置側の W3-a6（r9、未統合）は述語ごとに `role_frame = {助詞: [{"role", "types"}]}` を分布の腕で確認した役割だけ `role_frame_status: CONFIRMED` で出す。読解器は、問い合わせの答えの **契約** にだけ依存して、その枠を読む段 R を持つ。配置 r9 がまだ無いので、検査は偽の答え（`synthetic_contract`）で行い、r9 での実測（O5）は W3-a6 統合後に監査役が行う。

### 問い合わせの答えの契約（W3-a6 §12.18 D8。読解器はこれだけを前提にする）
- 配置が `role_frames` の表を持つときだけ、答えの末尾に 3 鍵がこの順で付く: `role_frame_status` ∈ {`CONFIRMED`, `ESTIMATED`, `NO_ROLE_FRAME`}、`role_frame`（CONFIRMED のときだけ `{助詞: [{"role", "types"}]}`、他は null）、`role_frame_unconfirmed`（読解器は **読まない**）。
- 表の無い配置（r7・r8）と配置なしでは 3 鍵は無い。鍵が無ければ段 R は何もしない（K277）。
- 役割名は `event_cross.ROLE_NAMES`（20）、型は `coarse_types.NOUN_TYPES` の id、助詞は格助詞 9 種（`_CASE_PARTICLES_9`）。

### 規則
- **K270 入口**: 段 R は W3-b4 の経路 U/U3 と同じ入口（能動態・述語が正規化されていない・K186 の係助詞の門・W5-f の引用の門・並立の門・埋め込みの十字の門を通った後、単一の述語の節）でだけ呼ぶ。新しい入口は作らない。述語の答えの `role_frame_status` が無い → 基点と同じ出力（理由も出さない）。`ESTIMATED`・`NO_ROLE_FRAME` で表が読めなかった文 → `ROLE_FRAME_NOT_CONFIRMED:<status>`。
- **K271 読む助詞**: に・で・へ・から・と・まで・より（`_CASE_PARTICLES_9` から が・を を除いた 7 つ。関数の中で導く）。が・を は段 R で「読む」対象でない（既存の経路が決める）。枠が が/を に別の役割を宣言していても、読む材料には使わない。ただし K274 の食い違いの検査と、表が確かめていない既存の名前の確認（H271）には使う。
- **K272 充填物**: 充填物の主辞の配置の答えが direct の 1 型（`placement_type` の門をそのまま通す。MULTIPLE・UNPLACED・UNKNOWN・推定・候補のみ → `ROLE_FRAME_FILLER_NOT_DIRECT:<助詞>:<理由>`）。型が `RELATIVE_POSITION` → `ROLE_FRAME_FILLER_RELATIVE_POSITION:<助詞>`（枠は宣言できない型。理由を分けて数える）。
- **K273 決め方**: `role_frame[助詞]` の役割のうち `types` が充填物の型を含むものを数える。1 → その役割で読む（`role_basis` は `role_frame:<述語>:<助詞>:<型>`、`predicate_basis` は `placement_direct:<述語の型>`）。0 → `ROLE_FRAME_TYPE_NOT_DECLARED:<助詞>:<型>`。2 以上 → `ROLE_FRAME_SPLIT:<助詞>:<型>`。助詞が枠に無い → `ROLE_FRAME_PARTICLE_NOT_DECLARED:<助詞>`。枠の形が契約を外れる → `ROLE_FRAME_INVALID:<problem>`（文全体を棄権。黙って読まない。problem は下の閉じた一覧）。
- **K274 表との関係**: 既存の経路（規約の表・K62 v2・W3-b1〜b5）が同じ充填物に既に役割を与えているとき、枠の役割と一致すれば既存の読みをそのまま返す（`role_basis` は既存のまま。段 R は何も足さない）。食い違えば文を棄権 `ROLE_FRAME_TABLE_CONFLICT:<助詞>:<既存の役割>:<枠の役割>`（「食い違い」= 既存の役割の型の充填物 T について、その助詞の枠で T を含む役割がちょうど 1 つあり、それが既存と違う）。段 R が新しく読めるのは、既存の経路がその充填物を未対応に残したときだけ（`recipient`・`ambiguous`、または表が「型を読まない／助詞の行が無い／型の行が無い」と言った充填物）。枠は表を上書きしない。
- **K275 kind（項か付加か）**: 枠は kind を持たない。段 R で読んだ役割の kind は、表の値（agent・patient・goal・source = arg、place・time = adjunct）か、表に無い役割は H274 の事前登録（`table:w3b6_role_kinds`）。kind の効き目は付加の門（`role@` の腕だけの direct を使わない）だけで、出力には出ない。
- **K276 複数の充填物**: 同じ助詞の（未対応の）充填物が節に 2 つ以上あれば段 R は読まない（`ROLE_FRAME_MULTIPLE_FILLERS:<助詞>`）。並立は既存の門が先に棄権する。
- **K277 不変**: 配置なし・r7・r8（3 鍵なし）では読解の出力が基点と byte 一致。既存の凍結データはすべて不変。新しい定数は理由名の閉じた一覧 `W3B6_REASON_NAMES` と K275 の kind の表 `W3B6_ROLE_KINDS` だけ。語の一覧・表層の規則は作らない。

### 段 R の手順（指示書 2.3 の具体）
`NO_OPINION` = 計画（W3-b4）の拒否理由が `PLACEMENT_FRAME_NOT_READ:`・`PLACEMENT_PARTICLE_NOT_IN_FRAME:`・`PLACEMENT_TYPE_MISMATCH:` で始まる（表が意見を持たないだけで、充填物や述語の門で止まったのではない）。
1. 計画の本体（`typed_plan_u_w3b4_body_ja`、W3-b4/W3-b5 の関数。変えない）を呼ぶ。拒否で `NO_OPINION` でない → そのまま返す（段 R の外。問い合わせもしない）。
2. `role_frame_status` の鍵が答えに無い → 計画の戻り値のオブジェクトをそのまま返す。`predicate_role_frame` が INVALID → `(None, 'ROLE_FRAME_INVALID:…')`（読めた文でも棄権）。`not_confirmed` → 読めた文はそのまま、読めなかった文は `ROLE_FRAME_NOT_CONFIRMED:<status>`。
3. 場合 A（計画が読んだ）: K274 の食い違いだけを見て、無ければ読みをそのまま返す。場合 B（`NO_OPINION`）: 役割を節の順に 1 つずつ見る。(1) その役割だけで計画に問うて表が読んだ → その役割と basis（K274 の検査）。(2) 表が `NO_OPINION` 以外の理由で止まった → その理由で棄権。(3) 表が意見を持たない → 未対応の名前（`recipient`・`ambiguous`）は助詞が K271 の 7 つで K276・充填物の門・K272・K273 を通るとき、読解器が名前を与えていた役割（agent・patient・source など）は **枠が同じ役割を一意に宣言するときだけ** 残す（H271）。枠で 1 つも読めなかったときは計画の理由のまま。

### 契約外の形の problem（`ROLE_FRAME_INVALID:<problem>` の閉じた一覧。検査の順）
`STATUS_UNKNOWN`（3 値の外）、`MISSING_ROLE_FRAME`（status があり `role_frame` の鍵が無い）、`FRAME_WITHOUT_CONFIRMED`（CONFIRMED でないのに `role_frame` が null でない）、`NOT_A_MAPPING`（CONFIRMED で dict でない。null を含む）、`PARTICLE_NOT_CASE:<助詞>`、`ENTRIES_NOT_A_LIST:<助詞>`（空でない list でない）、`ENTRY_NOT_A_MAPPING:<助詞>`、`ENTRY_KEYS:<助詞>`（鍵が `role`・`types` ちょうどでない）、`ROLE_NOT_IN_CONVENTION:<助詞>:<役割>`、`TYPES_NOT_A_LIST:<助詞>`（空でない文字列の list でない）、`TYPE_NOT_NOUN:<助詞>:<型>`（`RELATIVE_POSITION` は今の `NOUN_TYPES` に無いので枠に書けば INVALID）、`ROLE_DUPLICATED:<助詞>:<役割>`（同じ助詞に同じ役割が 2 つ）。読む鍵は `role_frame_status` と `role_frame` の 2 つだけ（`role_frame_unconfirmed` は読まない。コードに現れない）。

### 理由名（`W3B6_REASON_NAMES` の順。段 R の理由は出力に出ない: `typed_explain_ja(...)['w3b2']` と計画の戻り値で見る）
<!-- BEGIN table:w3b6_reasons -->
| 理由 | 書式 | 規則 |
|---|---|---|
| `ROLE_FRAME_NOT_CONFIRMED` | `ROLE_FRAME_NOT_CONFIRMED:<status>` | K270 |
| `ROLE_FRAME_FILLER_NOT_DIRECT` | `ROLE_FRAME_FILLER_NOT_DIRECT:<助詞>:<placement_type の理由>` | K272, K275 |
| `ROLE_FRAME_FILLER_RELATIVE_POSITION` | `ROLE_FRAME_FILLER_RELATIVE_POSITION:<助詞>` | K272 |
| `ROLE_FRAME_TYPE_NOT_DECLARED` | `ROLE_FRAME_TYPE_NOT_DECLARED:<助詞>:<型>` | K273 |
| `ROLE_FRAME_SPLIT` | `ROLE_FRAME_SPLIT:<助詞>:<型>` | K273 |
| `ROLE_FRAME_PARTICLE_NOT_DECLARED` | `ROLE_FRAME_PARTICLE_NOT_DECLARED:<助詞>` | K273 |
| `ROLE_FRAME_INVALID` | `ROLE_FRAME_INVALID:<problem>` | K273 |
| `ROLE_FRAME_TABLE_CONFLICT` | `ROLE_FRAME_TABLE_CONFLICT:<助詞>:<既存の役割>:<枠の役割>` | K274 |
| `ROLE_FRAME_MULTIPLE_FILLERS` | `ROLE_FRAME_MULTIPLE_FILLERS:<助詞>` | K276 |
<!-- END table:w3b6_reasons -->

再利用する既存の理由（名前を変えない）: `PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED`・`PLACEMENT_FRAME_TYPE_NOT_CONFIRMED`・`PLACEMENT_DUPLICATE_ROLE`・`PLACEMENT_INVALID:EMPTY_TERM`・`PLACEMENT_HEAD_RELATIONAL`・`PLACEMENT_DETERMINER_NOT_READ`。

### K275 の kind の表（`W3B6_ROLE_KINDS`。20 役割）
<!-- BEGIN table:w3b6_role_kinds -->
| 役割 | kind | 出所 |
|---|---|---|
| agent | arg | 表 |
| patient | arg | 表 |
| goal | arg | 表 |
| source | arg | 表 |
| place | adjunct | 表 |
| time | adjunct | 表 |
| recipient | arg | H274 |
| result | arg | H274 |
| quotation | arg | H274 |
| entity | arg | H274 |
| value | arg | H274 |
| attribute | arg | H274 |
| causer | arg | H274 |
| causee | arg | H274 |
| experiencer | arg | H274 |
| instrument | adjunct | H274 |
| companion | adjunct | H274 |
| cause | adjunct | H274 |
| standard | adjunct | H274 |
| beneficiary | adjunct | H274 |
<!-- END table:w3b6_role_kinds -->

### 判断記録（事前登録）
- **H270 配線の位置**: チケットは「末尾に追記」「`typed_plan_u_w3b4_ja` の呼び出し元 1 箇所」と言うが、末尾で `typed_plan_u_w3b2_ja` を包み直すと既存の凍結テスト 3 本（`w3b4::test_the_name_the_entry_calls…`・`w3b5::test_the_plan_of_w3b4_only_gains_lines…`・`w1a5::test_the_function_of_the_base_entry…`）が落ちる。そこで挿入 2 か所（削除行 0）: A = `typed_plan_u_w3b2_ja = typed_plan_u_w3b4_ja` の直後に、元の関数を `typed_plan_u_w3b4_body_ja` として残し、`typed_plan_u_w3b4_ja` を「その計画、次に段 R」の包みに差し替える（`functools.update_wrapper`）。B = 段 R の本体・契約の読み手・定数をファイル末尾に追記。意味はチケットどおり。
- **H271 表が確かめていない既存の名前（チケットより厳しい側）**: 読まない型・行の無い助詞では、表は が・を の充填物を確かめておらず、override の読み直しでは読解器自身の型の検査も走らない。そこで、読解器が名前を与えていた役割は、枠が同じ役割を一意に宣言するときだけ残し（basis は `role_frame:…`）、それ以外は K272/K273 の理由で棄権する。枠が別の役割を言えば K274 の食い違い。数を減らす方向。
- **H272**: `recipient`・`ambiguous` を「未対応に残った充填物」とするのは、W3-b4 の計画が同じ 2 つを「表に任せる名前」として扱っている（`PLACEMENT_READER_DISAGREES` の検査）のに合わせる。
- **H273**: 段 R に入るのは計画の理由が `NO_OPINION` のときだけ。`FRAME_GENERATED_DOES_NOT_LICENSE` や充填物の門（`PLACEMENT_MULTIPLE:…`・`PLACEMENT_ESTIMATED_*:…` など）は上書きしない。したがって、助詞が表に行を持つ型で MULTIPLE の充填物は、段 R の理由でなく計画の理由で棄権する。
- **H274**: 表に無い 14 役割の kind は中間職の決定として上の表に事前登録した。
- **H275**: チケットの「表が読まない述語型（11 型）」は W3-b1 の v1 表 `TYPED_FRAMES_NOT_READ` の数。今の計画（W3-b4/b5）が使う表は `TYPED_FRAMES_NOT_READ_W3B4` の 8 型。
- **H276 到達の事実（`artifacts/w3-b6/reach_base.txt`、コードを触る前に測定）**: W3-a6 N2 の 11 行のうち、基点の読解器がすでに読むのは 通報する・連絡する・待つ・運ぶ（へ・から）。段 R に届くのは 停泊する（U）・打つ（U3）・驚く（U3）・確認する（で が曖昧な文。U3）・集める（U）。分ける の に は計画の引き金がどちらも掛からない（`PLACEMENT_W3B2_NOT_TRIGGERED`）。K270 が新しい入口を禁じているので引き金は足さない: 分ける の行は `NOT_REACHED:TRIGGER_NONE` として未達と報告する。K274 は、基点の読解器と W3-b1 の経路 U が読んだ文を見ない（段 R はそれらの後ろの W3-b2 の計画の中にある）: 既知の穴。K271 の と・まで・より は、段 R を呼ぶ入口の文に現れない（と は並立で、まで・より は読解器が「表せない内容」とする）: 機構は持つが入口から届かない（既知の穴）。
- **H277**: 検査の枠はすべて作り物（`frame_source: synthetic_contract`）。r9 の実物の枠は無い。普通名詞の型と述語の型は r8 の答えを写し、r8 で estimated の述語を direct にした行には `placement_source: synthetic` と note を付ける。
<!-- w3b6-prereg:end -->
