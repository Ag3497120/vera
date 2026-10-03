<!-- w3b5-prereg:begin -->
登録日時: 2026-10-04 06:09:23 +0900（`date '+%F %T %z'` の出力。記録は `artifacts/w3-b5/prereg_time.txt`。直前のコミットは `7494ba21763a938f4f2c4a810f7d1f530d15b974`（dev。W3-b4・W5-e 統合済み））
この時点で `tests/reading_soundness/ja_r11.jsonl`・`tests/test_semantic_read_w3b5.py` は存在しない。この登録より前に作ったのは、r8・r7 の生成の枠の数え上げ（`artifacts/w3-b5/r8_frame_census.txt`・`r7_frame_census.txt`・`r8_frames_by_type.json`。表に依らない事実であって、検査データではない）と道具（`artifacts/w3-b5/tools/`）だけ。
出典: 中間職の指示書 `.claude/vera-audit/review-impl/W3-b5/plan.md` §2〜§3 と、チケット `W3-b5_frame_licensed_adjuncts.prompt.md`、監査役の実行上の注意（`frame_generated` は問い合わせに鍵を足すだけ。既存の鍵の値は r7・r8 で 1 語も変えない。`frame_required` の行は、述語の `frame_generated[助詞]` が行の期待する型を含み、かつ充填物が direct（または全候補一致）でその型のときだけ読む。`frame_generated` の無い述語は読まない。W3-b4 の係助詞の門はそのまま。順序: 登録 → データ凍結 → 直す前の記録 → 実装）。
目的: 述語ごとの生成の枠（「この述語のこの助詞にはこの型が来る」）を、型による読解の **付加を許すかどうかの参照系** として使う。W3-b4 が外した 3 型の `place/で/PLACE` と、W3-b1 が読まなかった に の行を、枠が許すときだけ読む行（`frame_required`）として登録する。生成の枠は構成物（証拠でない）なので、型の決定にも同点の解消にも使わず、**読む行を許すか許さないかの門** にだけ使う。誤読 0 が正読より先。誤読が出た行は外す。語・表層の規則・述語ごとの例外は足さない。
番号について: `READING_SOUNDNESS.md` に K19x・K20x・H19x・H20x は使われていないので、**この節は K200〜（事前登録・測定・既知の穴）、判断記録は H200〜** を使う。検査データの名前はチケットの `tests/reading_soundness/ja_r11.jsonl`。

### K200 制御の流れ

- 配置を指定したときだけ動く。配置なしの出力は基点（7494ba2）と 1 バイトも変わらない。
- **問い合わせ（`coarse_place.query`）**: 答えに鍵 `frame_generated` を **足すだけ**（契約は `docs/COARSE_PLACEMENT.md` §11.6・§12.10 に追記する）。既存の鍵の値と順は変えない。W3-a3 の末尾の鍵（`generated_frame`・`frame_status`・`frame`・`frame_unconfirmed`・`frame_disagreement` のうち答えにあるもの）の **最初の鍵の直前** に挿入する（凍結テスト 5 本が答えの末尾の並びを固定している）。
- **読解器（`semantic_reader.py`）は挿入だけで変える**（既存の行は 1 行も消さない・変えない。凍結テスト `test_the_reader_file_only_gains_lines` が `-` 行 0 を求める）。ファイルの末尾（並行の W1-a5 が足す場所と、W3-b4 第 4 ラウンドの名前の差し替えの 3 行）には何も足さない。名前を差し替えない: 入口が呼ぶ `typed_plan_u_w3b2_ja` は第 4 ラウンドの包み（K186 の係助詞の門）で `typed_plan_u_w3b4_ja` を呼ぶので、`typed_plan_u_w3b4_ja` を **その場で** 直せば、包んだ名前はそのまま新しい本体を呼び、K186 の門はそのまま掛かる。
- 新しい表 `TYPED_FRAMES_FRAME_REQUIRED_W3B5` は **別の辞書** に置き、`TYPED_FRAMES`・`TYPED_FRAMES_W3B4`・`typed_frames_v2()`・`TYPED_FRAMES_NOT_READ_W3B4` は変えない（W3-b4 の凍結テストが値を固定している。`typed_frames_v2()` に `frame_required` の行を入れると 3 本が落ちる）。
- **遅延の検査**: `frame_required` の行が無い（型, 助詞）の役割では、枠の答え（`frame_generated`）を見ない。したがって `frame_required` の行と無関係な文では、枠の答えが壊れていても、計画の戻り値は基点と 1 字も同じ。
- **枠が無い述語**（`frame_generated` の鍵が無い／null。seed の語・表の無い配置・偽の配置）では `frame_required` の行は無いものとして扱い、棄権の理由は基点のまま（`PLACEMENT_PARTICLE_NOT_IN_FRAME`・`PLACEMENT_TYPE_MISMATCH`）。**不在と否定は別の理由**: 枠があって許さないときだけ `FRAME_GENERATED_DOES_NOT_LICENSE:<助詞>`、枠の形が壊れていて見る必要があるときだけ `PLACEMENT_FRAME_GENERATED_INVALID:<問題>`。
- 許された行の期待する型は **行の型 ∩ 枠の型**。充填物の配置が `DECIDED direct`（または全候補が積に入る `MULTIPLE direct`）でその積に入るときだけ候補。2 行以上に合えば `PLACEMENT_ROLE_TIE`（棄権）。
- W3-b1・W3-b2 の規則と門は変えない: 述語の推定（門 3）・`gen_definition`（門 4）・付加の `role@` だけ（門 5）・CONFIRMED の `frame` による狭め・K186 の係助詞の門・読解器が名前を決めた役割と行の役割が違えば `PLACEMENT_READER_DISAGREES`。推定の述語は述語の段で従来どおり棄権する。**門を緩めて数を出さない**。

### K201 第 2 表に license の列（表 `table:w3b5_frames`）

§10D の `w3b4_frames`（5 列）は W3-b4 のテストが 5 列で読むので書き換えない。ここに 6 列の新しい表を置く。先頭の 17 行は `w3b4_frames` の 17 行（1〜5 列）を 1 字も変えずに写し、6 列目を `table` にした。その後ろが `frame_required` の 16 行（型の順は `typed_frames_v2()` と同じ、型の中は place/で・recipient/に・goal/に・time/に の順）。`frame_required` の行の（型, 助詞）の組で、同じ型・同じ助詞の行（両 license を合わせて）の期待する型は互いに素（P_MOVE・P_COMMUNICATE の に: TIME｜PLACE｜PERSON GROUP_ORG。3 型の に: PERSON GROUP_ORG｜PLACE｜TIME）。助詞は が を に へ から で の 6 つ。期待する型は 17 型の部分集合。recipient の型の並びは `event_cross.EXPECTED_TYPES['recipient']` と集合が同じ。

<!-- BEGIN table:w3b5_frames -->
| 述語の型 | 役割 | 助詞 | 期待する型 | 種類 | license |
|---|---|---|---|---|---|
| `P_MOVE` | agent | が | PERSON GROUP_ORG ANIMAL | 項 | table |
| `P_MOVE` | goal | へ | PLACE | 項 | table |
| `P_MOVE` | source | から | PLACE | 項 | table |
| `P_MOVE` | place | で | PLACE | 付加 | table |
| `P_MOVE` | time | に | TIME | 付加 | table |
| `P_COMMUNICATE` | agent | が | PERSON GROUP_ORG ANIMAL | 項 | table |
| `P_COMMUNICATE` | patient | を | PERSON GROUP_ORG ANIMAL PLANT ARTIFACT SUBSTANCE_FOOD EVENT_ACT STATE_PROPERTY ABSTRACT INFO_LANGUAGE BODY_PART NATURAL_PHENOMENON WORK IDENTIFIER | 項 | table |
| `P_COMMUNICATE` | place | で | PLACE | 付加 | table |
| `P_COMMUNICATE` | time | に | TIME | 付加 | table |
| `P_ACT` | agent | が | PERSON GROUP_ORG ANIMAL | 項 | table |
| `P_ACT` | patient | を | PERSON GROUP_ORG ANIMAL PLANT ARTIFACT SUBSTANCE_FOOD EVENT_ACT STATE_PROPERTY ABSTRACT INFO_LANGUAGE BODY_PART NATURAL_PHENOMENON WORK IDENTIFIER | 項 | table |
| `P_ACT` | goal | へ | PLACE | 項 | table |
| `P_ACT` | source | から | PLACE | 項 | table |
| `P_CREATE` | agent | が | PERSON GROUP_ORG ANIMAL | 項 | table |
| `P_CREATE` | patient | を | PERSON GROUP_ORG ANIMAL PLANT ARTIFACT SUBSTANCE_FOOD EVENT_ACT STATE_PROPERTY ABSTRACT INFO_LANGUAGE BODY_PART NATURAL_PHENOMENON WORK IDENTIFIER | 項 | table |
| `P_EMOTION` | agent | が | PERSON GROUP_ORG ANIMAL | 項 | table |
| `P_EMOTION` | patient | を | PERSON GROUP_ORG ANIMAL PLANT ARTIFACT SUBSTANCE_FOOD EVENT_ACT STATE_PROPERTY ABSTRACT INFO_LANGUAGE BODY_PART NATURAL_PHENOMENON WORK IDENTIFIER | 項 | table |
| `P_MOVE` | recipient | に | PERSON GROUP_ORG | 項 | frame_required |
| `P_MOVE` | goal | に | PLACE | 項 | frame_required |
| `P_COMMUNICATE` | recipient | に | PERSON GROUP_ORG | 項 | frame_required |
| `P_COMMUNICATE` | goal | に | PLACE | 項 | frame_required |
| `P_ACT` | place | で | PLACE | 付加 | frame_required |
| `P_ACT` | recipient | に | PERSON GROUP_ORG | 項 | frame_required |
| `P_ACT` | goal | に | PLACE | 項 | frame_required |
| `P_ACT` | time | に | TIME | 付加 | frame_required |
| `P_CREATE` | place | で | PLACE | 付加 | frame_required |
| `P_CREATE` | recipient | に | PERSON GROUP_ORG | 項 | frame_required |
| `P_CREATE` | goal | に | PLACE | 項 | frame_required |
| `P_CREATE` | time | に | TIME | 付加 | frame_required |
| `P_EMOTION` | place | で | PLACE | 付加 | frame_required |
| `P_EMOTION` | recipient | に | PERSON GROUP_ORG | 項 | frame_required |
| `P_EMOTION` | goal | に | PLACE | 項 | frame_required |
| `P_EMOTION` | time | に | TIME | 付加 | frame_required |
<!-- END table:w3b5_frames -->

**チケットの「11 型の に の 3 役割」から 5 型への逸脱（H200）**: 計画 `typed_plan_u_w3b4_ja` は、述語の型が `TYPED_FRAMES_NOT_READ_W3B4`（8 型）にあれば行を見る前に `PLACEMENT_FRAME_NOT_READ` で返す。また **節のすべての役割** に表の行を求める（が の役割も `in_frame` が空なら `PARTICLE_NOT_IN_FRAME`）。読まない 8 型には が の行が無いので、に の行だけを足しても 1 文も読めない。読まない型を読む型に変えるのは、K162（が の行が書けない型は型ごと読まない）に反し、チケットの範囲外。したがって `frame_required` の行は **読む 5 型（P_MOVE・P_COMMUNICATE・P_ACT・P_CREATE・P_EMOTION）にだけ** 16 行置く。P_MOVE・P_COMMUNICATE には `time/に/TIME`（`table`）が既にあるので、同じ行は `frame_required` で重ねない。登録したこの 16 行が **上限**（K206）。

### K202 `frame_generated` の契約（読解器の側）

問い合わせ `coarse_place.query` の答えの鍵 `frame_generated`（常に出す）は `null` か次の形:
`{"origin": "generated", "constructed": true, "ptype": <生成の枠の表の ptype>, "frame": <生成の枠の表の frame をそのまま。{助詞: [型…]}>, "provenance": {"model", "effort", "batch_id", "attempt"}}`。`null` になるのは、配置が開けない（`NO_PLACEMENT`）・配置に `generated_frames` 表が無い・表にその語の行が無いとき。引く語は答えの `spelling.normalized`（配置を引いた NFKC の形）。`frame`（CONFIRMED のときだけ）・`frame_status`・`frame_unconfirmed` の意味と値は変えない。`frame_generated` は `frame_status` と独立。

読解器は `predicate_frame_generated(answer)`（唯一の読み手。答えの `state`・`origin`・`top`・`decided_by`・`estimate_basis` を添字で読まない）で読む。戻り値は 3 種: `('absent', None)`（鍵が無い、または値が None）、`('generated', {助詞: frozenset(型)})`（形が正しい。空の `frame` `{}` は正しく、何も許さない）、`(None, 'PLACEMENT_FRAME_GENERATED_INVALID:<問題>')`。問題の閉じた一覧: `NOT_A_MAPPING`・`ORIGIN_NOT_GENERATED`・`FRAME_NOT_A_MAPPING`・`PARTICLE_NOT_CASE:<助詞>`（格助詞 9 種の外）・`TYPES_NOT_A_LIST:<助詞>`（空でない文字列の並びでない）・`TYPE_NOT_NOUN:<助詞>:<型>`（`coarse_types.NOUN_TYPES` の外）。

### K203 理由の型と、許可の申告

<!-- BEGIN table:w3b5_reasons -->
| 理由 | 意味 |
|---|---|
| `FRAME_GENERATED_DOES_NOT_LICENSE:<助詞>` | その助詞に読める行が `frame_required` の行だけで、述語の生成の枠がその助詞を持たないか、行の型・充填物の型を許さない |
| `PLACEMENT_FRAME_GENERATED_INVALID:<問題>` | `frame_required` の行を見る必要があり、`frame_generated` が K202 の形を破る |
<!-- END table:w3b5_reasons -->

1 列目の `:` の前の並びは `W3B5_REASON_NAMES` と同じ。出力には出ない（`semantic_read.py` を変えない）。診断 `typed_explain_ja(...)['w3b2']` に出る。

**許可の申告（H204。チケット・指示書からの逸脱を登録時に書く）**: 指示書は、生成の枠で許された役割を節の `role_flags` に `{"license": "frame_generated"}` として出力に申告するとした。しかし `event_cross._flag_well_formed` は `role_flags` の 1 役割の鍵を `determiner`・`coordination` の部分集合に **閉じており**、`license` の鍵があると `ENTRY_FLAGS_NOT_WELL_FORMED` で出力ごと拒否される（`event_cross.py` は許可パスの外で、触らない）。出力の形を壊して数を出さない。したがって許可の申告は **計画の戻り値の鍵 `role_license`**（`{役割名: 'frame_generated'}`）にだけ置き、出力（`role_flags`）には出さない（`semantic_read.reread` は `typed['role_flags']` しか写さないので、`role_license` は出力に現れない）。`role_basis` の形（K99 の正規表現）は変えない。出力に出す形は、`event_cross` の閉じた一覧を広げる別チケットが決める（申し送り）。

### K204 r8 の事実（登録時に測ったもの。出典 `artifacts/w3-b5/r8_frame_census.txt`・`r7_frame_census.txt`）

配置 r8/run2 の `generated_frames` は 8,030 語。各語を `coarse_place.query(w, placement=r8)` に通した数（`r8_frame_census.txt`）:
- DECIDED・estimated・述語の型が推定（frame_status ESTIMATED）: 7,900 語（P_ACT 2,368・P_CHANGE 1,251・P_MOVE 1,080・P_STATE 758・P_CREATE 450・P_COMMUNICATE 409・P_COGNITION 407・P_GIVE 320・P_EXIST 256・P_PERCEIVE 208・P_EMOTION 161・P_CONSUME 130・P_POSSESS 102）。
- DECIDED・direct: 130 語。P_COMMUNICATE 96（CONFIRMED 67・NOT_CONFIRMED 29）、P_MOVE 34（CONFIRMED 32・NOT_CONFIRMED 2）。**P_ACT・P_CREATE・P_EMOTION で生成の枠を持つ direct の語は 0**。表の型と答えの型は全語で同じ。
- r7（4,788 語）: DECIDED・direct 48 語（P_COMMUNICATE 38・P_MOVE 10）、残りは推定（`r7_frame_census.txt`）。

読解器の門 3（述語の推定は使わない）は述語の段で止まるので、推定の 7,900 語の枠は `frame_required` の行を働かせない。direct の 130 語のうち CONFIRMED の語は、W3-b2 の規則（`frame` に助詞が無ければ棄権）が先に止める。**r8 の入口で `frame_required` の行が働きうるのは、NOT_CONFIRMED の direct の語だけ**（census の末尾の一覧）。

ここから言えること: 3 型の `place/で`（P_ACT・P_CREATE・P_EMOTION）は、r8 の入口では 1 文も読まない（r8 に direct で枠を持つその 3 型の語が無い）。偽の配置のデータでだけ働く。L5 の見込みの数は書かない（監査役が測る）。

### K205 検査データの設計と受入基準

検査データ `tests/reading_soundness/ja_r11.jsonl`（1 行 1 文）。鍵と並び: `id`・`lang`・`input`・`text`・`behavior`・`expect`・`pred_type`・`path`・`particle`・`role_group`・`construction`・`placement`・`frame_source`・`entry_expect`・`w3b5_expect`・`note`。`id` は `W3B5-<GROUP>-<R|A>-NNN`（GROUP: `DEPLACE`・`DEINSTR`・`DECAUSE`・`NIRECIP`・`NIGOAL`・`NITIME`・`NIPURP`・`NIOTHER`・`MECH`）。`role_group`: `de_place`・`de_instrument`・`de_cause`・`ni_recipient`・`ni_goal`・`ni_time`・`ni_purpose`・`ni_other`・`mechanism`。

- 件数の下限: 読む行は `de_place`・`ni_recipient`・`ni_goal`・`ni_time` の各 20 以上（H203: 引き金に届く読む行が足りない群は、足りないまま件数と理由を `data_counts.txt` と判断記録に書く。届かない文で水増ししない）。棄権の行は `de_place`・`de_instrument`・`de_cause`・`ni_recipient`・`ni_goal`・`ni_time`・`ni_purpose`・`ni_other` の各 20 以上。`mechanism` は 15 以上。
- **枠の出所の規則**: 述語の `frame_generated.frame` は `frame_source` が `r8` のとき、r8 の `generated_frames` のその語の行を **1 字も変えずに写したもの**（述語の型も r8 のその行の ptype。データでは direct の NOT_CONFIRMED として扱い、`note` に「r8 では estimated」と書く）。`absent` は枠が無い（r8 に行の無い語・seed の日常動詞）。`synthetic`（作った枠）は `mechanism` の群にだけ許す。**読む行は `frame_source: r8` だけ**（偽の枠で読ませない）。照合は `frame_source_check.txt`。
- 棄権の群に必ず入れる: (a) W3-b4 の束 d・c の 10 文（右・段差・口。枠が無い版と、で を持たない作った枠の版）、(b) 枠が許す最悪の場合（r8 の実物の枠が その助詞・その型を持つのに、充填物の役割が行と違う文。で: 手段・原因。に: 刺激・相手・受益者・与え手・結果・接触面・行き先の組織・目的の時）、(c) 枠が助詞・型を持たない（`DOES_NOT_LICENSE`）、(d) 充填物の配置（`role@` だけの付加・MULTIPLE で候補の 1 つが積の外・推定・UNPLACED）、(e) 述語の配置（推定・CONFIRMED で `frame` に助詞が無い・`frame_generated` が壊れている）、(f) 既存の門（格助詞の直後の係助詞・副助詞、受身・使役、語尾、派生）。
- 偽の配置の方針: 固有名は `UNPLACED`、普通名詞は r8 と矛盾しない direct の型。r8 で MULTIPLE・推定・UNPLACED の語を DECIDED にしない。r8 で型が誤っている語（口=PLACE など）は「配置の型の誤り」の群にだけ使う。
- 期待を先に凍結する（`bank_freeze.sha256`・`bank_freeze_time.txt`）。配置を通した入口・計画には凍結まで通さない。

受入基準（チケットの写し。L5 は監査役が測る）:
- **L1**: 配置なしの出力は基点と byte 一致。既存の凍結データ x3 で `changed=0`・`misread=0`。`query` の既存の鍵は r7・r8 で 1 語も変わらない。
- **L2**: 表の検査（互いに素・役割・型・助詞・v1 ⊂ v2・`license` の値）がテストで通る。
- **L3**: 検査データで誤読 0。右で打った・段差で驚いた・口の文が棄権、搭乗口で係員が旅券の写しを確認した の型の文が読める（述語と充填物は自作の別の語で）。
- **L4**: 中間職の未公開の文（で・に 各 30 文以上、期待を先に凍結）で誤読 0。誤読が出た行は `frame_required` でも外す。
- **L5**: B1（r8）で誤読 0・誤答 0 のまま、「ambiguous case role」が唯一の理由の 20 文のうち読める文が増える（数を報告）。
- **L6**: 既存テストの失敗集合が基線 `dev_7494ba2_failures.txt` から増えない（ハッシュ固定の衝突は申告）。

### K206 表の変更の約束

登録後の変更は **狭める方向だけ**（`frame_required` の行を消す・期待する型を減らす）。誤読が 1 件でも出た行は外す（その行だけが原因と示せないときは、その型の `frame_required` の行をすべて外す）。語・表層の規則・述語ごとの例外は足さない。変更は「表の変更記録（W3-b5）」に日時・前後・理由・出典を書く。登録した 16 行の集合を広げない。
<!-- w3b5-prereg:end -->
