# W3-b4 K62 第2表・係助詞の門 攻撃報告

## 1. 攻撃対象

- 実装: [semantic_reader.py](../../verantyx/semantic_reader.py#L2663) の `TYPED_FRAMES_W3B4`、`typed_frames_v2()`、W3-b4 計画、K186 の焦点助詞門。
- 約束: [READING_SOUNDNESS.md](../../docs/READING_SOUNDNESS.md#L2247) §10D K161・K163、F1〜F3（同書 [K164](../../docs/READING_SOUNDNESS.md#L2310)）、K186（[門の定義](../../docs/READING_SOUNDNESS.md#L2440)）、K188（[読解器のみで読む範囲](../../docs/READING_SOUNDNESS.md#L2475)）。
- 事前登録: 150 文の式・期待は [PREREG.md](PREREG.md)、sha256 `4d2f9755a5b7f2934b05c6e24290f3450463b2bd56effdb5b39b407a36d9c917`。K188 の既存例、K163 の表外役割、ユーザー指定例文は別紙 [K188_PREREG.md](K188_PREREG.md)、[ROLE_OVERLAP_PREREG.md](ROLE_OVERLAP_PREREG.md)、[PROMPT_EXAMPLES_PREREG.md](PROMPT_EXAMPLES_PREREG.md) に登録した。

## 2. 命中した攻撃

### W3B4-1 — 観点 (e): 引用符で括った「も／は」が門を抜ける

- 入力: `兄が荷車を倉庫へ「も」押した。` (`A054`)、`兄が荷車を倉庫へ「は」押した。` (`A059`)。
- 再現: `PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-b4 PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q attacks/W3-b4/test_attack_w3b4.py::test_the_real_r8_run2_entry_has_no_preregistered_misread`
- 配置: 実配置 `/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2`、content hash `89bd07e6c71d883cdeafaa96e906118cbfbc3dc45b1f15f2ce65bbec783382a5`。
- 実出力（両文）: `readable: true`; roles は `agent=兄, patient=荷車, goal=倉庫`。`typed_explain_ja` は W3-b1=`PLACEMENT_FRAME_NOT_READ:P_ACT`、W3-b2=`READ`。追加の `も` / `は` は出力に残らない。
- 期待との差: K186 の門が読むべき焦点を落としたまま、W3-b4 の新しい型経路で読んだ。形態素は引用内の `も` / `は` を `記号/一般` と分類する。実装は `補助記号`・`空白` だけを除外し、後続トークンは `助詞` の場合だけ検出するため、この形は隣接ペアにならない（[semantic_reader.py:2761](../../verantyx/semantic_reader.py#L2761)–[2765](../../verantyx/semantic_reader.py#L2765)）。
- 数: 2 文。実 r8 と偽配置の両方で同じ脱落を再現。

### W3B4-2 — 観点 (a): 「右から打った」を `source` と読む

- 入力: `弟が右から倉庫へ打った。` (`D10`)。
- 再現: `PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-b4 PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python attacks/W3-b4/replay.py` または `test_the_real_r8_run2_entry_has_no_preregistered_misread`。
- 実出力: 実 r8 で `readable: true`; `agent=弟, goal=倉庫, source=右`。診断 W3-b1 は `PLACEMENT_FRAME_NOT_READ:P_ACT`、W3-b2 は `READ`。実配置は `右=PLACE` (`origin=direct`, `state=DECIDED`)、述語 `打つ=P_ACT` (`seed`)、`倉庫=PLACE`。
- 期待との差: この文の `右から` は打撃の方向を示すので、表にない方向の役割を `source` に決めず棄権する期待。第2表の `P_ACT / から / PLACE → source` が方向と起点を区別せず通した（[semantic_reader.py:2664](../../verantyx/semantic_reader.py#L2664)–[2669](../../verantyx/semantic_reader.py#L2669)、[READING_SOUNDNESS.md:2266](../../docs/READING_SOUNDNESS.md#L2266)）。
- 追加の確認: 指示書のより短い例 `兄が右から打った。` も r8 で `source=右` と読むが、診断は `w3b2=null` で基点読解器だけの出力。こちらは W3-b4 の回帰数に含めない。

### W3B4-3 — 観点 (a)/(f): 偽の直接配置で `へ` の相手を goal に固定

- 入力: `店員が店へ注文した。` (`D01`)、`兄が店へ電話した。` (`D03`)。
- 再現: `test_the_150_preregistered_safety_cases_are_not_returned_as_readings`。`MapQuery` の偽直接配置を `P_ACT`・`店=PLACE` とすると、両方とも `readable: true` で `店=goal`。
- 期待との差: `店へ` は注文先・通話相手にも読めるが、表に `recipient` 行がなく `goal/へ/PLACE` が勝つ。W5-d 方式の誤配置を使った時だけの再現である。r8 の同じ述語は `PLACEMENT_ESTIMATED_GENERATED:predicate:注文する/電話する` となって棄権したため、実配置での命中には数えていない。
- 該当箇所: P_ACT の `goal/へ` 行 [semantic_reader.py:2668](../../verantyx/semantic_reader.py#L2668)、対応する事前登録表 [READING_SOUNDNESS.md:2265](../../docs/READING_SOUNDNESS.md#L2265)。

### 別枠で確認した、基点から続く出力

ユーザー指定の例 `兄が上司から叱られた。`、`兄が右から打った。`、`兄が失敗を悔やんだ。`、`兄が穴を掘った。` は r8 でそれぞれ `agent=上司 / patient=兄`、`source=右`、`patient=失敗`、`patient=穴` と読んだ。4 文とも W3-b1 / W3-b2 の型診断は `null`。c875ed3 の入口でも出力が完全一致したため、W3-b4 の新経路の命中数からは除外する。K188 に列挙済みの焦点脱落例も、別紙の5文すべてで同節記載の出力を再現した（5/5、すべて `typed_explain_ja` は `None`）。

## 3. 外れた攻撃・確認した範囲

- 主攻撃150文: 5件で意味役割または焦点の脱落を再現。残り145件は誤読出力なし（棄権、または `D05` のように `recipient` を保つ正しい読み）。実配置 r8 では `A054`・`A059`・`D10` の3件を再現し、`D01`・`D03` は偽の直接配置のみ。
- 係助詞門の直接判定では隣接・区切り候補115文中19文が `None`。うち引用符内の `も`・`は` の2文だけが上記の読み出力まで到達。他17文は入口が別理由で棄権するか、UniDic が焦点候補を助詞以外（例: `なんか` の `なん/代名詞` + `か/副助詞`、引用内 `さえ/名詞`）に分割し、今回の実出力命中にはならなかった。
- `P_CREATE` の結果物 (`X3`)、`P_EMOTION` の原因 (`X4`)、instrument (`X1`)、purpose/time (`X2`) はすべて棄権。診断はそれぞれ `PLACEMENT_PARTICLE_NOT_IN_FRAME:P_CREATE:へ`、`PLACEMENT_PARTICLE_NOT_IN_FRAME:P_EMOTION:で`、`P_CONSUME` の未読型、または基点側の `NO_SUPPORTED_CLAUSE`。表の同型・同助詞キー重複は0件で、既存の自己素性チェック [test_semantic_read_w3b4.py:135](../../tests/test_semantic_read_w3b4.py#L135) が比較する行ペア自体が無い。これは検査の空振りだが、この追加4文では誤読出力を作れなかった。
- 配置なしF1の限定試験は、主攻撃150文の compact JSON 出力を c875ed3 と比較し、byte 差0（テスト成功）。登録データ全体・x3 は再測定していない。

## 4. 数・再現結果・判断記録

- **主攻撃の命中 N=5、外れ M=145**。命中の内訳は実配置r8で3、偽の直接配置だけで2。対象語・期待式は実装出力を見る前に登録した。
- 追加のユーザー例12文では、r8で意味を落とす読み4、棄権8。前述の4読みは基点 c875ed3 と同じで、W3-b4固有の命中には加えない。K188の既知例5文も同書の既知穴の再現として別計上。
- 攻撃テスト実行: `PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-b4 PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q attacks/W3-b4/test_attack_w3b4.py` → **5 failed, 2 passed**。5失敗は上記の出力反例・門の見逃しを再現し、2成功は配置なし比較と表外役割の棄権確認。全文は [pytest_attack.txt](pytest_attack.txt)、入力ごとの出力・形態素・r8回答は [replay_output.json](replay_output.json)、再現スクリプトは [replay.py](replay.py)。全体テストは指示どおり実行していない。F4/F5（非公開文・隠しバンク）は未実施。
- 手順上の逸脱: 主PREREGのA群区切り式に空文字を置いていたため、攻撃テストの生成コードを書いた後、初回実行より前に粒子を保持する式へ修正した。期待カテゴリと件数は変えていない。初版sha256と修正記録は [PREREG.md](PREREG.md) に残した。補足用の期待表は各テスト実行より前に登録した。
- 範囲: 作成物は `attacks/W3-b4/` のみ。`verantyx/`・既存テスト・凍結データは変更していない。禁止場所の読み取り、ネットワーク、git commit/push は行っていない。
