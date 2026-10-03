# 事象の十字（event cross）: 述語が中心、役割が腕、語が充填物

（この文書は段階的に書く。最初に書いたのは次の「事前登録」節だけ。ほかの節は検査データを作ったあとに足す。）

## 事前登録

<!-- prereg:begin -->
登録日時: 2026-10-03 09:35:00 +0900（`date '+%Y-%m-%d %H:%M:%S %z'` の出力。直前の同じ出力は 09:34:49 で、このファイルはその間に書いた）
`EXPECTED_TYPES_VERSION = 1`

この表は検査データを作る前に書いた（この時点で `tests/event_cross/data/` は存在しない）。出典は中間職の指示書 `.claude/vera-audit/review-impl/W3-b/plan.md` §3.3。
根拠は `docs/READING_CONVENTIONS.md` §2 の「何を入れるか」の文言だけ。規約が型を言っていない役割は表に入れない。
型の名前は W3-a2 の作業ツリー（2026-10-03 時点）の名詞の型 id。

| 役割 | 期待する型 | 根拠（規約 §2 の語） |
|---|---|---|
| `agent` | `PERSON` `GROUP_ORG` `ANIMAL` | 人・動物・組織が主語の自動詞の主語 |
| `recipient` | `PERSON` `GROUP_ORG` | 物や情報を受け取る人・組織 |
| `place` | `PLACE` | 出来事・存在の場所 |
| `time` | `TIME` | 時を表す語句 |
| `companion` | `PERSON` | 一緒に行う人 |
| `causee` | `PERSON` | 使役で実際に元の動作をした人 |
| `beneficiary` | `PERSON` | 恩恵を受ける人、for＋人 |
| `experiencer` | `PERSON` | 影響を受ける人 |

上の 8 役割以外の 12 役割（`patient` `goal` `result` `source` `instrument` `cause` `quotation` `entity` `value` `attribute` `standard` `causer`）は表に無い。
理由: 規約が型を決めていない（`goal` は「場所・物」で物の範囲が開いている、`entity` は比較で人も物も入る、など）。表に無い役割は `NOT_CHECKED(ROLE_NOT_IN_TABLE)`。

型一致の決め方（上から順に、最初に当たったもの。決定的）:

1. 腕が `ARM_TIE` -> `NOT_CHECKED(ARM_TIE)`
2. 役割が表に無い -> `NOT_CHECKED(ROLE_NOT_IN_TABLE)`
3. lookup の戻りが `PlaceResult` でない・不変条件を破る -> `NOT_CHECKED(LOOKUP_RESULT_INVALID)`（lookup が投げた例外は握りつぶさずそのまま上げる）
4. `state == NO_PLACEMENT` -> `NOT_CHECKED(NO_PLACEMENT)` / `UNKNOWN` -> `NOT_CHECKED(UNKNOWN)` / `UNPLACED` -> `NOT_CHECKED(UNPLACED)`
5. `origin == estimated` -> `estimate_basis` が `proximity` なら `NOT_CHECKED(ESTIMATED_NEAR)`、`generated` なら `NOT_CHECKED(ESTIMATED_GENERATED)`
6. `state == MULTIPLE`（直接でも）-> `NOT_CHECKED(MULTIPLE)`（割れは決めない）
7. `state == DECIDED` かつ `origin == direct` -> 型が表の集合に入れば `AGREE`、入らなければ `DISAGREE`

`DISAGREE` でも役割名・値・腕の並びを変えない（申告だけ）。

表を後で変えるときは、変更日時・前後の差・理由を下の「事前登録の変更記録」に全件書き、`EXPECTED_TYPES_VERSION` を上げる。
<!-- prereg:end -->

### 事前登録の変更記録

（2026-10-03 09:35 時点: 変更なし。出典: artifacts/w3-b/prereg.txt）

1. **2026-10-03 21:07:46 +0900（`date '+%F %T %z'` の出力。W3-b2 の事前登録 `docs/READING_SOUNDNESS.md` §10B と同じ時刻で、この記録はその間に書いた）。W3-b2 の 3 つの変更。表の中身 `EXPECTED_TYPES` と `EXPECTED_TYPES_VERSION` は変えない（変えたのは表でなく、規則と欄）。**
   - (1) 型一致の規則 6 を分ける。前: `state == MULTIPLE`（直接でも）→ `NOT_CHECKED(MULTIPLE)`。後: `state == MULTIPLE`（直接。推定は規則 5 で先に外れる）で、型が **すべて** 表の集合に入る → `AGREE_ALL_CANDIDATES`（`expected` は表の集合の辞書順、`observed` は型の辞書順。どの候補であっても期待に合う）、1 つでも外れれば `NOT_CHECKED(MULTIPLE)`。ほかの規則・順は変えない（役割が表に無い・腕が ARM_TIE などは規則 1・2 で先に外れるので `AGREE_ALL_CANDIDATES` にならない）。
   - (2) 数えの形。`VERDICTS` は 3 値のまま。新しい定数 `EXTRA_VERDICTS = ('AGREE_ALL_CANDIDATES',)`。`CrossReading.counts['agreement']` は、`AGREE_ALL_CANDIDATES` の腕が 1 つ以上あるときだけ最後に鍵 `AGREE_ALL_CANDIDATES` を足す（0 件の出力は今と 1 バイトも同じ。`counts` の上位の鍵は増やさない）。`observe`（W3-c）は `verdict == 'AGREE'` だけを許可に使うので、`AGREE_ALL_CANDIDATES` は許可にならない（保守的な側）。
   - (3) 入口の新しい欄。定数 `ENTRY_FLAG_KEYS = ('role_flags',)`（`ENTRY_BASIS_KEYS` は変えない）。`_check` は節の鍵 `role_flags` を受け入れ、形（`{役割名: {"determiner": 空でない文字列}}`、役割名は節の `roles` にあるもの、鍵は `determiner` だけ）を確かめ、破れば `ENTRY_FLAGS_NOT_WELL_FORMED`。`_filler` は `role_flags[役割]['determiner']` があれば充填物の `flags['determiner']` に写す（`quantifier` と同じ扱い。中心 `center` には入れない）。
   - 理由と出典: チケット W3-b2 の やること 4（十字の `agreement` に `AGREE_ALL_CANDIDATES` を足す）と やること 5（指示詞を充填物の `flags.determiner` に写す）。(3) はチケットの許可（「agreement の値の追加のみ」）を超えるが、やること 5 が「充填物の `flags.determiner` に写す」と求め、充填物は十字にしか無く、入口の新しい欄を `_check` が受け入れなければ `--events` が `INPUT_REJECTED` になるため、最小の変更として採る（中間職の指示書 §3.6 が決めたもの。判断記録 H134 以降に書く）。

## 目的と三層の中での位置

十字の設計（オーナーの最終目標の設計）: **中心は事象（述語）、腕は役割、語は腕を埋める充填物で、語の型は粗い配置から来る**。三層は、語の配置（粗い配置）、事象の十字（この文書）、談話の関係（節の間の関係）。
この層は、読解器（`verantyx/semantic_read.py`）の出力だけから、型付きの事象の十字を作り、役割と型の一致・不一致を **型で申告する（直さない）**。
既定の入口（`python -m verantyx.semantic_read --text=... --events`、`python -m verantyx.cli read-events --text=...`）から使え、決定的で、実行時に LLM を使わない。読解器の規則は変えていない。

オーナーの要望は「人間の説明を枠に入れるというのが初期バージョンでも、そこから話題や関係を汎用に意味理解して適切に処理できることが必須」。
次のチケット（W2-h2）は人間の自由文の説明から分業の記録（枠）を作る。そのときの枠に入れる前の、**話題に依存しない意味の層**がこの十字である。だから:

- `verantyx/event_cross.py` には話題ごとの語彙・規則を一切置かない（作業・分業・ソフトウェアの語を特別扱いしない）。役割は規約（`docs/READING_CONVENTIONS.md`）の閉じた一覧だけ、関係も同じ規約の閉じた一覧だけ。
- 検査データは話題を散らしてある（料理・学校・農業・医療・交通・家事・事務・工場・ソフトウェアなど）。その中に W2-h2 が受け取る形に近い「人が作業を説明する文」（誰が・何を・誰に・いつまでに）を混ぜ、タグ `explain` を付けた。読解器がそれをどれだけ十字にできるかは、下の測定結果に件数で書いた（多くが棄権する。これは W2-h2 と読解器側への実測の入力）。
- 十字は `to_dict()` で決定的に直列化でき、腕の並びは規約の役割一覧の順に固定してある。次のチケット（W3-b2、十字を鍵にした探索）はそのまま鍵に使える。

## 型の定義

実装は `verantyx/event_cross.py`（標準ライブラリだけを import する。`read_events` だけが関数の中で読解の入口を import する）。

| 型 | 中身 |
|---|---|
| `EventCross` | `index`（節の番号）、`center`（述語の辞書形・極性・時制・モダリティ・態。あれば量化・スコープ・比較をそのまま）、`arms`（役割名 -> `Arm`。規約の順）、`provenance`（`source_schema`・`clause_index`・`rule`・`span`。読解器の `clause_meta` の写し） |
| `Arm` | `kind`（`FILLER` か `ARM_TIE`）、`fillers`、`agreement`（`TypeAgreement`） |
| `Filler` | `surface`（原文の表記）、`head`（主辞。読解器は主辞を出さないので `surface` と同じで `head_basis` は `surface`）、`place`（`PlaceResult`）、`flags`（読解器が出した量化があれば `{"quantifier": 値}`） |
| `PlaceResult` | `state`・`origin`・`estimate_basis`・`types`（順位ではない集合。**構築時に辞書順に書き直す**。空でない文字列だけのタプルのときに限る。それ以外の形は直さず `invariant_problems` が拒否する。後から順序を崩された値は `TYPES_NOT_IN_ALPHABETICAL_ORDER`。W5-a A1）・`provenance`。`source` は `direct`・`estimated_near`・`estimated_generated`・`UNPLACED`・`UNKNOWN`・`NO_PLACEMENT` のどれか |
| `TypeAgreement` | `verdict`（`AGREE`・`DISAGREE`・`NOT_CHECKED`）、`reason`（`NOT_CHECKED` のときの閉じた理由）、`expected`・`observed` |
| `CrossReading` | `status`（`CROSSED`・`ABSTAINED`・`INPUT_REJECTED`）、`crosses`、`relations`（読解器の `relations` の写し）、`abstain`、`lookup_id`、`counts` |
| `PlacementLookup` | `lookup(lemma) -> PlaceResult` の Protocol。引数は語だけ（役割も述語も渡さない） |

`events` 欄（`CrossReading.to_dict()`）の形: `schema`（`verantyx.event_cross/1`）・`status`・`crosses`・`relations`・`abstain`・`lookup`（`id`）・`counts`（十字・腕・`arm_ties`・型一致の三つの判定・`NOT_CHECKED` の理由別。件数が無い理由も全部書く）。
`events` は既存の出力の最後の鍵として足す。既存の鍵の値と順は変えない。`--events` 無しの出力は一切変えない。

役割の充填物に付く配置の出所は、W3-a2 の問い合わせの語彙（`state`・`origin`・`estimate_basis`）をそのまま持ち、`source` はそこから導出する（判断記録を参照）。

## 変換の規則（`build_crosses`）

1. 入力の検査。失敗は `INPUT_REJECTED`（`abstain` は `{"kind": "input_rejected", "reasons": [...]}`、十字は作らない）。理由は型付きの文字列で、近い名前に寄せない・黙って落とさない。
   `READER_ERROR:<type>`・`BAD_SCHEMA`・`MISSING_FIELD:<鍵>`・`READABLE_NOT_BOOL`・`UNKNOWN_CLAUSE_KEY:<鍵>`・`ROLE_NOT_IN_CONVENTION:<名>`・`RELATION_TYPE_NOT_IN_CONVENTION:<種>`・`RELATION_INDEX_OUT_OF_RANGE`・`CLAUSE_META_LENGTH_MISMATCH`・`READABLE_WITHOUT_CLAUSES`・`EMPTY_ROLE_VALUE:<名>`・`ROLE_VALUE_SINGLETON_ARRAY:<名>`・`ROLE_VALUE_NOT_STRING:<名>`。
   これに加えて自分で足した形の検査（判断記録を参照）: `NOT_A_MAPPING`・`CLAUSES_NOT_A_LIST`・`RELATIONS_NOT_A_LIST`・`CLAUSE_META_NOT_A_LIST`・`UNREADABLE_WITHOUT_ABSTAIN`・`UNREADABLE_WITH_CLAUSES`・`RELATION_NOT_WELL_FORMED`・`CLAUSE_NOT_A_MAPPING`・`ROLES_NOT_A_MAPPING`。
2. `readable: false` は `ABSTAINED`。`abstain` は読解器の `abstain` をそのまま写す（`unreadable_input` と `not_supported` を混ぜない）。十字も関係も作らない。
3. `readable: true` は節 i ごとに十字 i（並びも番号も読解器の `clauses` と同じ）。
   - `center` は節の `roles` 以外の鍵をそのまま。
   - `arms` は節の `roles` の各組。値が文字列なら `FILLER`。値が複数の文字列の配列なら `ARM_TIE`（充填物を配列の順のまま並べ、どれも選ばない）。単一要素の配列・空配列・文字列でない要素は `INPUT_REJECTED`（配列の意味を推測しない）。
   - 充填物の `place` は `lookup.lookup(head)` の結果（役割も述語も渡さない）。`flags` は節の `quantifiers` にその役割名の鍵があるときだけ。
   - 十字の関係は読解器の `relations` をそのまま（件数も順も向きも同じ。足さない）。
4. 入力の dict を変更しない（深い写し）。同じ入力・同じ lookup なら `to_dict()` の直列化は同じバイト列。
   **W5-a（A1・A2。攻撃役の反例）**: `to_dict()` の JSON が、等しい入力に対して**鍵の挿入順によらず**同じバイト列になるよう、次を固定した。
   - `place.types` は常に辞書順（型は集合で順位ではないので、構築時に辞書順で書くのは解決ではなく定義どおりの書き方）。lookup が `MULTIPLE` の型を逆順に返しても `PERSON, PLACE` の順で出る。
   - `relations` の各要素は `type, from, to` の順で写し、ほかの鍵があれば（落とさず）その後ろに辞書順。
   - 入力から写す入れ子の Mapping（`center` の `quantifiers`・`scope`・`comparison`、`flags` の量化、`abstain`、`provenance` の値）は鍵を辞書順にして写す（配列の順は変えない）。
   - lookup が返す `place.provenance` は入力ではないので変えない。
   - テスト: `tests/attack/test_w5a_cross_key_order.py`（入力の各 Mapping の鍵の**全順列**で直列化が同じバイト列。件数と秒数は `artifacts/w5-a/k3_permutations.txt`）。

## 型一致の決め方

事前登録の節に書いたとおり（上から順に最初に当たったもの。`NOT_CHECKED` の理由は閉じた一覧: `ARM_TIE`・`ROLE_NOT_IN_TABLE`・`LOOKUP_RESULT_INVALID`・`NO_PLACEMENT`・`UNKNOWN`・`UNPLACED`・`ESTIMATED_NEAR`・`ESTIMATED_GENERATED`・`MULTIPLE`）。
lookup が不変条件を破る値を返したときは、その充填物の `place` を `state: INVALID`（`provenance.reason` は `LOOKUP_RESULT_INVALID`、問題の名前つき）にして残し、型一致は `NOT_CHECKED(LOOKUP_RESULT_INVALID)`。lookup が投げた例外は握りつぶさずそのまま上げる。

## スタブと粗い配置の差し替え手順

**差し替えは済んだ**(W3-b1。docs/READING_SOUNDNESS.md §10)。既定の lookup は `verantyx.event_cross.default_lookup(placement=None)`: 引数 `placement`(配置のディレクトリ)があればそれ、無ければ環境変数 `VERA_PLACEMENT`、どちらも無い・空なら今までの `StubLookup`(`id` は `stub-no-placement/1`。全部 `state: NO_PLACEMENT`、`provenance.reason` は `STUB`)。配置があれば `CoarseLookup`。`build_crosses`・`attach_events` の `lookup=None` は `default_lookup()`。粗い配置自身の環境変数 `VERA_COARSE_PLACEMENT` は **読まない**(`coarse_place.query` に `None` のパスを渡すと配置の側が自分の変数を読むので、必ず実在のパスつきで呼ぶ)。

```python
from verantyx.event_cross import CoarseLookup, default_lookup, read_events

lookup = default_lookup('/path/to/placement')     # = CoarseLookup('/path/to/placement')。引数なし・VERA_PLACEMENT なしなら StubLookup
out = read_events("...", lookup=lookup)           # 読解も同じ配置で読ませるなら VERA_PLACEMENT か semantic_read.read(..., placement=...)
```

- `CoarseLookup.lookup(lemma)` は関数の中で `coarse_place` を import し、`PlaceResult.from_coarse_query(coarse_place.query(lemma, placement=self.path))` を返す(語だけ。役割も述語も渡さない)。モジュール直下の import は標準ライブラリだけのまま(テストがある)。
- `CoarseLookup.id` は `coarse-placement:<content_sha256>`(開けないときは `coarse-placement:unavailable:<reason>`。`events.lookup.id` に出る)。開けない配置は `NO_PLACEMENT`(理由は `provenance.placement.reason`)で、「型が合わない」とは混ぜない。
- 入口は `--placement <dir>`(`--` より前の完全一致の引数だけ。略記は今までどおり `BAD_ARGUMENTS`)か `VERA_PLACEMENT`。`--events` のときは同じ配置が十字の lookup にもなる(`python -m verantyx.semantic_read --text=... --events --placement=<dir>`)。
- 十字は、入口が型で決めた節の出所の欄 `ENTRY_BASIS_KEYS = ('predicate_basis', 'role_basis')` を受け入れ(`CLAUSE_KEYS` は変えない。規約 §1.1 の表と一致するテストがある)、その節の十字の `provenance` に同じ名前・同じ値で写す(`center` には入れない)。欄が壊れていれば `ENTRY_BASIS_NOT_WELL_FORMED:<鍵>` で入力を拒否する。
- 実データでの `AGREE` / `DISAGREE`(型一致は「事前登録」の表のまま。直さず申告だけ。出典: `artifacts/w3-b1/events_live.json`、`tests/reading_soundness/w3b1_events_measure.py`。コマンド: `cd <木> && VERA_PLACEMENT=<配置> python tests/reading_soundness/w3b1_events_measure.py --inputs artifacts/w3-b1/entry_inputs.txt --out artifacts/w3-b1/events_live.json`、`--inputs` は必須):

| item | value | source (artifacts/w3-b1/) |
|---|---|---|
| event cross with the placement, event_cross_sentences: sentences read / arms / AGREE / DISAGREE / NOT_CHECKED | 70 / 174 / 36 / 1 / 137 | events_live.json |
| event cross with the placement, new_data: sentences read / arms / AGREE / DISAGREE / NOT_CHECKED | 81 / 203 / 115 / 0 / 88 | events_live.json |
| event cross with the placement, rest: sentences read / arms / AGREE / DISAGREE / NOT_CHECKED | 241 / 578 / 181 / 7 / 390 | events_live.json |
| event cross DISAGREE arms in all (and how many of them were typed by the entry) | 8 (0) | events_live.json |

  `DISAGREE` の全件は `artifacts/w3-b1/events_live_summary.txt`。どれも基点の読解器が非人の主語を `agent` と読んだ文(車が・船が・国が・風が など)と、会社・学校を `place` と読んだ文で、十字が不一致と申告している(読みは変えない)。

統合のときにやること(W3-b の時点の 4 項目の結果): (1) `lookup.id` に配置の内容のハッシュ — 済(`coarse-placement:<content_sha256>`)。(2) `NOUN_TYPE_IDS` が coarse_types.py の名詞の型の一覧と一致するテスト — 済(`tests/test_semantic_read_w3b1.py::test_the_expected_types_of_a_role_are_those_of_the_event_cross_table`)。(3) 入口が配置を使うかどうか — 済(`--placement` / `VERA_PLACEMENT`。指定が無ければ今までどおりスタブで、出力は基点とバイト一致)。(4) `PlaceResult.from_coarse_query` は契約の形の dict を写す純関数で、W3-a2 側のキーが変わったらここだけ直す — 変えていない。

## `--events` の出力例（実行出力の貼り付け）

次の 3 つは `python -m verantyx.semantic_read --text=... --events` の出力そのもの（`artifacts/w3-b/events_all.jsonl` の該当行と同じ。`recompute.py --check` が一致を確かめる）。

<!-- example: ja-039 -->
```text
{"schema": "verantyx.semantic_read/1", "lang": "ja", "readable": true, "clauses": [{"predicate": "あげる", "roles": {"agent": "先生", "patient": "ノート", "recipient": "生徒"}, "polarity": "+", "tense": "past", "modality": null, "voice": "active"}], "relations": [], "abstain": null, "unsupported": [], "clause_meta": [{"rule": "frame", "span": [10, 12]}], "events": {"schema": "verantyx.event_cross/1", "status": "CROSSED", "crosses": [{"index": 0, "center": {"predicate": "あげる", "polarity": "+", "tense": "past", "modality": null, "voice": "active"}, "arms": {"agent": {"kind": "FILLER", "fillers": [{"surface": "先生", "head": "先生", "head_basis": "surface", "place": {"state": "NO_PLACEMENT", "origin": null, "estimate_basis": null, "types": [], "source": "NO_PLACEMENT", "provenance": {"reason": "STUB"}}, "flags": {}}], "agreement": {"verdict": "NOT_CHECKED", "reason": "NO_PLACEMENT", "expected": null, "observed": null}}, "patient": {"kind": "FILLER", "fillers": [{"surface": "ノート", "head": "ノート", "head_basis": "surface", "place": {"state": "NO_PLACEMENT", "origin": null, "estimate_basis": null, "types": [], "source": "NO_PLACEMENT", "provenance": {"reason": "STUB"}}, "flags": {}}], "agreement": {"verdict": "NOT_CHECKED", "reason": "ROLE_NOT_IN_TABLE", "expected": null, "observed": null}}, "recipient": {"kind": "FILLER", "fillers": [{"surface": "生徒", "head": "生徒", "head_basis": "surface", "place": {"state": "NO_PLACEMENT", "origin": null, "estimate_basis": null, "types": [], "source": "NO_PLACEMENT", "provenance": {"reason": "STUB"}}, "flags": {}}], "agreement": {"verdict": "NOT_CHECKED", "reason": "NO_PLACEMENT", "expected": null, "observed": null}}}, "provenance": {"source_schema": "verantyx.semantic_read/1", "clause_index": 0, "rule": "frame", "span": [10, 12]}}], "relations": [], "abstain": null, "lookup": {"id": "stub-no-placement/1"}, "counts": {"crosses": 1, "arms": 3, "arm_ties": 0, "agreement": {"AGREE": 0, "DISAGREE": 0, "NOT_CHECKED": 3}, "not_checked_by_reason": {"ARM_TIE": 0, "ROLE_NOT_IN_TABLE": 1, "LOOKUP_RESULT_INVALID": 0, "NO_PLACEMENT": 2, "UNKNOWN": 0, "UNPLACED": 0, "ESTIMATED_NEAR": 0, "ESTIMATED_GENERATED": 0, "MULTIPLE": 0}}}}
```

<!-- example: ja-075 -->
```text
{"schema": "verantyx.semantic_read/1", "lang": "ja", "readable": false, "clauses": [], "relations": [], "abstain": {"kind": "not_supported", "reasons": ["NO_SUPPORTED_CLAUSE"]}, "unsupported": [{"predicate": "ござる", "span": [4, 7], "reasons": ["unrepresented source content", "event without participant or content word"]}], "clause_meta": [], "events": {"schema": "verantyx.event_cross/1", "status": "ABSTAINED", "crosses": [], "relations": [], "abstain": {"kind": "not_supported", "reasons": ["NO_SUPPORTED_CLAUSE"]}, "lookup": {"id": "stub-no-placement/1"}, "counts": {"crosses": 0, "arms": 0, "arm_ties": 0, "agreement": {"AGREE": 0, "DISAGREE": 0, "NOT_CHECKED": 0}, "not_checked_by_reason": {"ARM_TIE": 0, "ROLE_NOT_IN_TABLE": 0, "LOOKUP_RESULT_INVALID": 0, "NO_PLACEMENT": 0, "UNKNOWN": 0, "UNPLACED": 0, "ESTIMATED_NEAR": 0, "ESTIMATED_GENERATED": 0, "MULTIPLE": 0}}}}
```

<!-- example: en-040 -->
```text
{"schema": "verantyx.semantic_read/1", "lang": "en", "readable": true, "clauses": [{"predicate": "give", "roles": {"agent": "teacher", "patient": "notebook", "recipient": "student"}, "polarity": "+", "tense": "past", "modality": null, "voice": "active"}], "relations": [], "abstain": null, "unsupported": [], "clause_meta": [{"rule": "en_frames", "span": [0, 40]}], "events": {"schema": "verantyx.event_cross/1", "status": "CROSSED", "crosses": [{"index": 0, "center": {"predicate": "give", "polarity": "+", "tense": "past", "modality": null, "voice": "active"}, "arms": {"agent": {"kind": "FILLER", "fillers": [{"surface": "teacher", "head": "teacher", "head_basis": "surface", "place": {"state": "NO_PLACEMENT", "origin": null, "estimate_basis": null, "types": [], "source": "NO_PLACEMENT", "provenance": {"reason": "STUB"}}, "flags": {}}], "agreement": {"verdict": "NOT_CHECKED", "reason": "NO_PLACEMENT", "expected": null, "observed": null}}, "patient": {"kind": "FILLER", "fillers": [{"surface": "notebook", "head": "notebook", "head_basis": "surface", "place": {"state": "NO_PLACEMENT", "origin": null, "estimate_basis": null, "types": [], "source": "NO_PLACEMENT", "provenance": {"reason": "STUB"}}, "flags": {}}], "agreement": {"verdict": "NOT_CHECKED", "reason": "ROLE_NOT_IN_TABLE", "expected": null, "observed": null}}, "recipient": {"kind": "FILLER", "fillers": [{"surface": "student", "head": "student", "head_basis": "surface", "place": {"state": "NO_PLACEMENT", "origin": null, "estimate_basis": null, "types": [], "source": "NO_PLACEMENT", "provenance": {"reason": "STUB"}}, "flags": {}}], "agreement": {"verdict": "NOT_CHECKED", "reason": "NO_PLACEMENT", "expected": null, "observed": null}}}, "provenance": {"source_schema": "verantyx.semantic_read/1", "clause_index": 0, "rule": "en_frames", "span": [0, 40]}}], "relations": [], "abstain": null, "lookup": {"id": "stub-no-placement/1"}, "counts": {"crosses": 1, "arms": 3, "arm_ties": 0, "agreement": {"AGREE": 0, "DISAGREE": 0, "NOT_CHECKED": 3}, "not_checked_by_reason": {"ARM_TIE": 0, "ROLE_NOT_IN_TABLE": 1, "LOOKUP_RESULT_INVALID": 0, "NO_PLACEMENT": 2, "UNKNOWN": 0, "UNPLACED": 0, "ESTIMATED_NEAR": 0, "ESTIMATED_GENERATED": 0, "MULTIPLE": 0}}}}
```

## 直さず申告する理由

型の不一致（`DISAGREE`）で役割を直さないのは、規約が役割を型で決めていないからである。例: 規約は「他動詞の主語」を型によらず `agent` とする（出典: docs/READING_CONVENTIONS.md の役割の節）。
だから無生物が他動詞の主語のとき（風が窓を揺らす、など）`agent` の充填物は `agent` の期待する型の外になり `DISAGREE` が出るが、それは **誤りの主張ではなく、表の外の型が入っていたという事実の申告**である。
ここで役割を直すと、規約どおりに正しく読んだ文を壊す。直すのは読解器側の別チケットの仕事で、十字の層は読解器の誤りを隠さず、型の食い違いを後段（W2-h2、W3-b2）が見える形で残す。
同じ理由で、`ARM_TIE`・`MULTIPLE` は選ばず割れたまま、`NO_PLACEMENT`・`UNKNOWN`・`UNPLACED`・推定は照合せず、別々の理由で申告する（分からないことと偽であることを混ぜない）。

## 既にあるものとの関係

- `verantyx/events.py`: 事象を core にして参与者を役割つき facet にする（CrossStore への取り込み。独自の抽出器を持つ）。このチケットの十字は「読解器の出力だけから作る」層で、別の抽出器を通すと二つ目の読解器になるので使わない。
- `verantyx/cross.py`（`LinearCross`・`ShellCross`）: 立体十字の幾何。使わない。名前の衝突を避けるため新しい名前は `event_cross` にした。
- 作る前に引いた索引の結果: `artifacts/w3-b/index_before.txt`（事象の十字）・`artifacts/w3-b/index_before_agreement.txt`（役割と型の一致は `UNKNOWN_NOT_FOUND`）。

## 検査データ

`tests/event_cross/data/` に凍結（`FROZEN.json` に sha256 と日時）。文と期待は別ファイルで、期待は 1 文ずつ人が規約を読んで書き、読解器の出力から写していない（文を凍結 -> 期待を凍結 -> 初めて読解器に通した、の順。日時は `FROZEN.json` と `artifacts/w3-b/prereg.txt`）。
読解器が棄権する文の期待は「十字 0・棄権の写し」（テストが確かめる）。読解器が読んだが期待と食い違った文は `reader_disagreements.json` に凍結し、十字の層が読解器の節を忠実に写していることだけを確かめる（`artifacts/w3-b/reader_disagreements.md`）。
期待の書き方が規約で決まらない所（期限の `までに`、`止まる` の `に`、`over` の前置詞など）は、各行の `note` に「規約が決めていない」と書いた。

### 検査データの変更記録

- 2026-10-03 09:45:13 +0900（出典: tests/event_cross/data/FROZEN.json）: 最初の文の組（`sentences_ja.jsonl`・`sentences_en.jsonl`）を読解器に通したところ、読解器が読んだ文が全体の 4 分の 1 未満だった。計画書の指示（読める型の文を新しい id で追記してよい）に従い、`*_add1.jsonl` を追記した。
  追記した文は、読解器が読んだ最初の組の型（授受の単文・否定の単文・比較・英語の単文）を見たうえで選んだ。期待は読解器に通す前に書いて凍結した（`FROZEN.json` の `sentences_add1`・`expected_add1`）。最初の組の文・期待は 1 バイトも変えていない。
- 期待の書き誤りの疑い: ja-080（ぬめる は辞書にある語）。期待は直していない。理由は `artifacts/w3-b/reader_disagreements.md` に書き、中間職の判断に回す。
  中間職の判断（第一ラウンドのレビュー）: 規約の「辞書に無い動詞」の節は「辞書に無い動詞」が条件で、ぬめる は辞書にあるので、期待の書き誤りと見なす。読解器の出力を見た後なので直さず、(c) のまま、十字の忠実な写しだけを確かめる。
- 観測ファイル `artifacts/w3-b/reader_obs_set1.jsonl` は、追記の後に書き直したもので、最初の通しの時点のものそのままではない（レビューの指摘）。順序の証拠は `FROZEN.json` の時刻と各データファイルの更新時刻。

## 測定結果

数値はすべて下の区間にある（`tests/event_cross/recompute.py --check` が `artifacts/w3-b/` から同じ文字列を作れることを確かめる）。

<!-- recompute:begin -->
### 検査データと読解器の分類（出典: artifacts/w3-b/e2_classes.json, e2_summary.json）

検査データは日本語 103 文・英語 101 文、計 204 文。

|  | 日本語 | 英語 | 計 |
|---|---|---|---|
| (a) 読解器が棄権 | 64 | 70 | 134 |
| 　うち期待も棄権（読めない文） | 7 | 8 | 15 |
| 　うち期待は読める文（読解器の過剰棄権） | 57 | 62 | 119 |
| (b) 読解器が読み、期待と一致 | 34 | 31 | 65 |
| (c) 読解器が読み、期待と食い違う | 5 | 0 | 5 |
| 読解器が読んだ文（(b)+(c)） | 39 | 31 | 70 |

最初の 163 文（追記前。出典: artifacts/w3-b/e2_classes_set1.json）では、読解器が読んだ文は 39 文（(a) 124・(b) 35・(c) 4）。読める文が全体の 4 分の 1 未満だったので、読める型の文を新しい id で追記した（変更記録を参照）。

### `--events` の出力の集計（出典: artifacts/w3-b/e2_summary.json）

状態: CROSSED 70 文・ABSTAINED 134 文・INPUT_REJECTED 0 文。
十字 70 個・腕 174 本・ARM_TIE 0 本・関係 0 件。
関係の種類別: (実際の入口からは 0 件)
型一致（スタブの配置）: AGREE 0・DISAGREE 0・NOT_CHECKED 174。
NOT_CHECKED の理由別: ARM_TIE 0, ESTIMATED_GENERATED 0, ESTIMATED_NEAR 0, LOOKUP_RESULT_INVALID 0, MULTIPLE 0, NO_PLACEMENT 95, ROLE_NOT_IN_TABLE 79, UNKNOWN 0, UNPLACED 0
棄権の種類: not_supported 129, unreadable_input 5。
棄権の最初の理由の上位: EN_UNREAD 39, NO_SUPPORTED_CLAUSE 31, UNKNOWN_PREDICATE 19, UNCOVERED_PREDICATE 6, UNMAPPED_ROLE 6, RECIPIENT_TYPE_UNDETERMINED 5, UNREPRESENTED_CONTENT 5, RELATION_NOT_MAPPED 4。

| タグ | 文の数 | CROSSED | ABSTAINED |
|---|---|---|---|
| comparison | 20 | 9 | 11 |
| complex | 12 | 0 | 12 |
| connective | 18 | 0 | 18 |
| explain | 31 | 4 | 27 |
| fronted_time_place | 20 | 3 | 17 |
| giving | 58 | 30 | 28 |
| negation | 25 | 15 | 10 |
| passive | 16 | 2 | 14 |
| simple | 59 | 36 | 23 |
| unreadable | 16 | 1 | 15 |

話題（topic）は 14 種。話題別の CROSSED / 文の数: construction 4/7, cooking 5/15, factory 6/23, farming 3/13, greeting 0/10, housework 4/14, medical 9/20, office 5/14, school 9/26, shopping 8/11, software 3/15, sports 1/1, transport 10/25, weather 3/10。

### 「人が作業を説明する文」（タグ explain）で十字ができた数（出典: artifacts/w3-b/e2_summary.json）

|  | 文の数 | 十字ができた | 棄権 |
|---|---|---|---|
| ja | 16 | 2 | 14 |
| en | 15 | 2 | 13 |

十字ができた文の id: ja-102, ja-103, en-096, en-097。
そのうち最初に書いた文（追記前）の id: 0 件、追記した文の id: 4 件。

### `--events` 無しの出力の一致（E1。出典: artifacts/w3-b/e1_cmp.txt）

- E1a_OK
- E1b_OK
- E1c_OK
- subprocess checked 35 inputs (every 30th plus the last edge inputs), mismatch 0
- inputs:      775
- 3b7faaad4c76e166eba673374976f2e62cfda3f7bc8af7671aaad0b14f975797 verantyx/semantic_read.py@b471f5a (git show output, sha256)

自作バンクでの `--events` の有無の一致（出典: artifacts/w3-b/e5_selfmade_parity.txt）: checked 118, mismatch 0, events_not_deterministic 0, skipped 0

### 所要時間（出典: artifacts/w3-b/timing.json）

1 分平均の負荷: 測定前 7.12・測定後 7.35。1 文あたり（ms、204 文を 3 周し 1 周目は捨てた。408 回の測定）。

| 関数 | 中央値 | 最大 |
|---|---|---|
| read | 0.337 | 1.9818 |
| build_crosses_stub | 0.0179 | 0.0621 |
| read_events | 0.3867 | 1.8836 |

### 全体テストと決め打ち検査（E6。出典: artifacts/w3-b/pytest_full.txt, pytest_new_failures.txt, check_hardcode.txt, pytest_new_tests.txt）

新しいテスト（tests/test_event_cross.py, test_event_cross_entry.py, test_event_cross_data.py）: 315 passed in 4.19s
全体テストの最終行: `116 failed, 7093 passed, 44 skipped, 75 xfailed, 75 xpassed, 37 subtests passed in 174.79s (0:02:54)`
基線にない失敗: 2 件。
- `FAILED tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches`
- `FAILED tests/test_p4_abilities.py::test_speech_act_drafts_fill_new_roles_and_reread`
基線のコミットだけのクリーンなクローンで同じ 2 件を流した結果（出典: artifacts/w3-b/pytest_two_in_clean_clone_b471f5a.txt）: `1 failed, 1 passed in 3.53s`
差分をコミットしたクローンで同じ 2 件を流した結果（出典: artifacts/w3-b/pytest_two_in_scratch_clone.txt）: `1 failed, 1 passed in 3.51s`
決め打ち検査の出力: `added lines: 39 / PROPER/NUMERIC (must be empty): [] / ENGLISH NAMES (must be empty): []`
新規ファイル verantyx/event_cross.py の行も追加行に含めて同じ検査を流した出力（出典: artifacts/w3-b/check_hardcode_with_new_file.txt。git の差分は未追跡のファイルを含まないため）: `added lines: 422 / PROPER/NUMERIC (must be empty): [] / ENGLISH NAMES (must be empty): []`
<!-- recompute:end -->

### 基線にない失敗の説明（出典: artifacts/w3-b/pytest_rerun_two.txt, pytest_two_in_clean_clone_b471f5a.txt, pytest_two_in_scratch_clone.txt）

- `test_s6_two_runs_agree_except_timing_and_recount_matches`: 採点器（tools/bank_score/cli.py）が `git status --porcelain -- verantyx` が空かを `verantyx_untouched` に記録し、テストはそれが真であることを求める。作業ツリーが未コミットで verantyx/ に変更があるあいだは偽になる（このチケットが verantyx/ を変えるので避けられない）。基線のコミットだけのクローンでは通り、差分をコミットしたクローンでも通った（出典のファイル）。
- `test_speech_act_drafts_fill_new_roles_and_reread`: 基線のコミットだけのクローンで同じ環境・同じコマンドで流しても落ちる（出典のファイル）。落ちる一例は「友人から借りた傘を返すときのお礼」の文で、述語が `貸す` に正規化される（作業ツリーでもクローンでも同じ trace）。このチケットの差分に関係しない。基線の一覧にこのテストが無い理由（環境の差と思われる）は特定していない。

## 判断記録

計画書（出典: .claude/vera-audit/review-impl/W3-b/plan.md）が原則側で決めたもの:

| 記号 | 決めたこと | 理由 | 出典 |
|---|---|---|---|
| D1 | スタブは `UNPLACED` ではなく `NO_PLACEMENT`（理由 `STUB`）を返す | チケットは「全部 UNPLACED を返すスタブ」と書くが、粗い配置の契約で `UNPLACED` は「素材にはあるが証拠が足りない」、配置そのものが無いのは `NO_PLACEMENT`。「無い」と「索引が無い」を混ぜない原則に従う。型一致はどちらでも `NOT_CHECKED` なので結論は変わらない | plan.md |
| D2 | 出所の語彙は粗い配置の `state`・`origin`・`estimate_basis` をそのまま持ち、チケットの 5 値は `source` として導出する（`NO_PLACEMENT` を 6 つめに足す） | 契約の語彙に合わせる | plan.md |
| D3 | `MULTIPLE` は直接でも照合しない | 同点は棄権する | plan.md |
| D4 | lookup に役割・述語を渡さない（`lookup(lemma)` のまま） | 粗い配置は役割の位置で推定するので、渡すと役割で決めた型で役割を照合する循環になる | plan.md |
| D5 | 主辞を推定しない（`head` は `surface`、`head_basis` は `surface`） | 読解器が主辞を出すようになったら `head_basis: reader` を足す | plan.md |
| D6 | 1 要素の配列・空配列の役割値は `INPUT_REJECTED` | 配列の意味を推測しない。`ARM_TIE` は 2 つ以上の候補のときだけ | plan.md |

実装中に自分で決めたこと:

- 形が壊れた読解出力の拒否の理由を、計画書の一覧に足した（`NOT_A_MAPPING` ほか。変換の規則の節に全部書いた）。理由はどれも型付きの文字列で、近い名前に寄せない。
- lookup の戻りが契約を破るとき、充填物の `place` は `state: INVALID` として残し、問題の名前を `provenance` に書く（黙って捨てない・`NO_PLACEMENT` と混ぜない）。型一致は `LOOKUP_RESULT_INVALID`。
- `ARM_TIE` の候補ごとにも lookup を引く（どれも選ばずに、それぞれの配置を残すため）。
- `types` が空のとき `origin` は何でもよいが、`DECIDED` と `MULTIPLE` は件数（一つと複数）、`estimated` は `estimate_basis` の有無を不変条件として確かめる。型 id が `NOUN_TYPE_IDS` に無くても拒否しない（粗い配置の一覧は追記のみなので、新しい型が来ても `DISAGREE` として申告される）。
- `read-events` は `--text` と `--lang` を受けて同じ関数（`semantic_read.main`）を通す。`--text` が無いときは `--text` を渡さず `MISSING_TEXT` に任せる。
- 検査データの追記（変更記録）。期待の `note` に「規約が決めていない」を明記した行がある。
- `recompute.py --check` は、出力例の貼り付けも `events_all.jsonl` の該当行と照合する。
- `--events` は argparse に登録せず、ちょうど `--events` という引数（最初の `--` より前にあるもの）だけを取り除いてから、変更前と同じパーサーに渡す。理由: 登録すると argparse の前方一致で `--e`・`--ev`・`--eve`・`--event` も `--events` として通り、`--events` を含まない argv の出力が変わる（第一ラウンドのレビューの必須の修正）。`allow_abbrev=False` では `--te=`（`--text` の省略）の挙動が変わるので使わない。`--events=x` は変更前と同じく `BAD_ARGUMENTS`。テストは基点のコミットの本文で動かした `main` と省略形の argv の出力・終了コードを比べる。

## 既知の穴

- 実際の入口から出る関係は、検査データでは測定結果の区間にある件数だけで、複文・接続の文は全部読解器が棄権した（読解器は二節の `relative` しか作らず、英語は一節だけ）。複数の十字と関係の写しは、手で作った読解出力のテストでだけ確かめた。
- `ARM_TIE` は実際の入口からは出ない（読解器は一つの役割に一つの値しか返さず、二つ来ると `DUPLICATE_ROLE` で棄権する）。手で作った読解出力のテストでだけ確かめた。
- スタブなので、実際の入口の型一致は全部 `NOT_CHECKED`（`AGREE`・`DISAGREE` は偽の配置のテストでだけ出る）。
- 読解器は主辞を出さないので `head` は `surface`（「新しい機械」のような句がそのまま lookup に渡る）。粗い配置が句を引けないなら、主辞を出す読解器側の変更か、後段の主辞の取り出しが要る。
- 「人が作業を説明する文」は多くが棄権する（測定結果の区間）。棄権の理由は読解器の理由のまま写っている（語彙の外・時の句・受け手の型が決まらない、など）。W2-h2 と読解器側への入力。
- 読解器との食い違い: 比較の `attribute` 欠落（`dimension` を落とす）、指示詞（あの）の外し漏れ。差分の提案は `artifacts/w3-b/proposed_reader_dimension_attribute.patch`（適用していない）。
- 検査データの一文（ja-080）は期待の書き誤りの疑いがある（変更記録）。
- 検査データの期待のうち、規約が決めていない所（`までに`・`止まる` の `に`・`over`）は、書き方を一つ選んである。読解器とずれても書き誤りとは限らない。
- 隠しバンクでの E5 はこちらでは測っていない（`tests/event_cross/events_parity.py` で自作バンクが一致することだけ）。
- 時間は負荷が基準未満の間に測ったが、測定中も他の作業が走っていた（測定結果の区間に負荷を書いた）。

## 次のチケットが使うもの

- W2-h2（人間の自由文の説明から分業の記録を作る）: `read_events()` と `center`・`arms`・`relations`・`abstain`。棄権（読めない）は型付きでそのまま来るので、枠に入れる側が「読めなかった」を自分で扱える。
- W3-b2（十字を鍵にした探索の高速化）: `to_dict()` の直列化と、腕の並びが規約の順に固定されていること。述語の辞書形・態・極性が `center` にあり、腕の充填物の `surface`・`place.types` が鍵になりうる。

## W3-b2 の追記(型による読解の第 2 段の十字)

事前登録した変更は「事前登録の変更記録」の 1(`AGREE_ALL_CANDIDATES`・数えの鍵・`role_flags`)。`EXPECTED_TYPES` の表と `EXPECTED_TYPES_VERSION` は変えていない。既存の節の文(K87 の申し送りの 4 行を含む)は変えていない。

- 型一致の規則 6: 割れた配置(直接)で、型がすべて表の集合に入るなら `AGREE_ALL_CANDIDATES`(どの候補であっても期待に合う)、1 つでも外れれば今までどおり `NOT_CHECKED(MULTIPLE)`。推定の割れは規則 5 で先に `NOT_CHECKED(ESTIMATED_NEAR / ESTIMATED_GENERATED)` になる。`observe`(W3-c)は `AGREE` だけを許可に使うので、`AGREE_ALL_CANDIDATES` は許可にならない。
- 数え: `VERDICTS` は 3 値のまま。`AGREE_ALL_CANDIDATES` の腕が 1 つ以上あるときだけ `counts['agreement']` の最後に鍵が付く(0 件の出力は今までと同じ形)。
- `role_flags`: 入口が型の経路で読んだ節の新しい鍵(`{役割: {"determiner": "この"}}`)。形が悪ければ `ENTRY_FLAGS_NOT_WELL_FORMED`。充填物の `flags.determiner` に写す(中心・出所の欄には入れない)。
- 実データの件数(出典 `artifacts/w3-b2/events_r6.json`・`events_r6_summary.txt`。配置 r6 の実物を lookup にした。`w3b2_events_measure.py`。`AGREE_ALL_CANDIDATES` と `DISAGREE` の全件の文・役割・値・型は `events_r6_summary.txt`):

<!-- w3b2-measured-events:begin -->
- 群 `event_cross_sentences`(配置 r6 の実物を lookup にした十字): 読めた文 69・型の経路の節を持つ文 0・腕 171・AGREE 35・AGREE_ALL_CANDIDATES 0・DISAGREE 0・NOT_CHECKED 136・`flags.determiner` を持つ充填物 0。(`events_r6.json`)
- 群 `new_data`(配置 r6 の実物を lookup にした十字): 読めた文 68・型の経路の節を持つ文 56・腕 177・AGREE 103・AGREE_ALL_CANDIDATES 0・DISAGREE 0・NOT_CHECKED 74・`flags.determiner` を持つ充填物 1。(`events_r6.json`)
- 群 `rest`(配置 r6 の実物を lookup にした十字): 読めた文 198・型の経路の節を持つ文 0・腕 479・AGREE 155・AGREE_ALL_CANDIDATES 2・DISAGREE 4・NOT_CHECKED 318・`flags.determiner` を持つ充填物 0。(`events_r6.json`)
- 群 `w3b2_data`(配置 r6 の実物を lookup にした十字): 読めた文 113・型の経路の節を持つ文 112・腕 264・AGREE 168・AGREE_ALL_CANDIDATES 26・DISAGREE 0・NOT_CHECKED 70・`flags.determiner` を持つ充填物 34。(`events_r6.json`)
- `AGREE_ALL_CANDIDATES` の腕の全件数: 28、`DISAGREE` の全件数: 4。全件の文・役割・値・型は `events_r6_summary.txt`。
- `--events` なしの出力の一致(E1。`e1.txt`): E1_SAME・E1_EQUALS_BASE_COMMIT_RUN・E1_SAME_WITH_PLACEMENT。
<!-- w3b2-measured-events:end -->

- 既知の穴: 十字は値の表層全体を問い合わせるので、入口が主辞の型で読んだ役割(`role_basis` の `_head`)と十字の型の一致の判定が食い違いうる(`docs/READING_SOUNDNESS.md` K104)。`DISAGREE` の腕は今までどおり申告であって修理ではない。
