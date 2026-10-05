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

## 穴の型（W3-c2。事前登録）

（W3-c2 = 質問の十字。疑問文を「wh 語の腕だけが穴になった十字」として読むためのもの。この節は検査データ `tests/observe/question/` を作る前に書いた。）

<!-- w3c2-prereg:begin -->
登録日時: 2026-10-03 19:39:20 +0900（`date '+%Y-%m-%d %H:%M:%S %z'` の出力。直前の同じ出力は 2026-10-03 19:39:13 +0900 で、このファイルの追記はその直後に行い、この行は追記後の `date` の出力に直した。初版は書き手が日時を実際の出力より先に書いたので、実際の出力に直した。下の変更記録）
`HOLE_TYPES_VERSION = 1`

この時点で `tests/observe/question/` は存在しない。出典は中間職の指示書 `.claude/vera-audit/review-impl/W3-c2/plan.md` の D2・D4・D5・D10。

穴の印: 和文 `Ｘ`（U+FF38 全角）、英文 `X`。wh 語（の区間）を、語を当てはめずにこの 1 記号に置き換えてから、既存の節の読みを呼ぶ。印は「型の証拠が要る位置」では読めないことが実測されている（誰に・どこで・どこへ・いつ）。それは仕様どおりの棄権で、語・助詞・読点を足して読ませることはしない。
入力に印が既にあれば `HOLE_MARK_IN_INPUT` で棄権する。読んだ後、印がちょうど 1 つの節のちょうど 1 つの役割の値と完全に一致しなければ棄権する（値に現れない = `HOLE_DROPPED`、値の一部・述語・2 か所 = `HOLE_NOT_ISOLATED`）。

役割の名前は `event_cross.ROLE_NAMES`（規約 §2）に写す。チケットの `location` は規約の `place` に写す。チケットの `theme` は規約に役割が無いので表に入れない（規約の閉じた一覧を増やさない。物・事の腕は `patient`）。
`cause`・`manner` は、読解器が出さない関係（`semantic_read.NOT_PRODUCED` の `relation:cause`・`relation:manner`）で、十字の腕ではない。どんな＋N は性質で、十字に腕が無い。従ってこの 3 つは「読まない」型として表に載せ、型付きで棄権する。
英文の where・when は、規約の英文の枠に時・場所の役割が無い（`NOT_PRODUCED['en:time and place phrases']`）ので読まない。数の問い（何人・いくつ・how many・how much）は表に無く、`WH_NOT_IN_TABLE` で棄権する。不定語（誰か・何も）は wh ではない（`WH_INDEFINITE`）。

<!-- BEGIN table:w3c2_holes -->
| 穴の型 | 和文の wh | 英文の wh | 許す腕 | 期待する型 |
|---|---|---|---|---|
| PERSON | 誰・だれ | who | agent・recipient・patient | PERSON・GROUP_ORG |
| THING | 何・なに・なん | what | patient | NOUN_TYPE_IDS から PERSON・GROUP_ORG を除いた型 |
| PLACE | どこ | where | place・goal・source | PLACE |
| TIME | いつ | when | time | TIME |
| RESTRICTOR | どの＋N | which＋N | ROLE_NAMES の全部（N の腕） | N の配置の型 |
| PROPERTY | どんな＋N | — | — | — |
| CAUSE | なぜ・どうして | why | — | — |
| MANNER | どうやって・どう | how | — | — |
<!-- END table:w3c2_holes -->

読めない型（`—` の腕）: PROPERTY は `HOLE_NOT_AN_ARM:property`、CAUSE は `HOLE_RELATION_NOT_PRODUCED:cause`、MANNER は `HOLE_RELATION_NOT_PRODUCED:manner`。英文の PLACE・TIME は `HOLE_ROLE_NOT_PRODUCED:en:place`・`:en:time`。
読解器が決めた穴の腕が「許す腕」の外なら `HOLE_ROLE_NOT_ALLOWED:<wh>:<役割>`（読解器が決めた役割を直さない）。

### 穴の型による候補の判定（D10。観測のとき）

構造の文の十字の、穴の腕の充填物の `place`（構造の lookup が引いたもの）を、本書「型一致の決め方」の規則 3〜7 と同じ順に判定する:
3. `PlaceResult` でない・不変条件違反 → `NOT_CHECKED(LOOKUP_RESULT_INVALID)`。 4. `NO_PLACEMENT`・`UNKNOWN`・`UNPLACED` → `NOT_CHECKED(<state>)`。 5. `estimated` → `NOT_CHECKED(ESTIMATED_NEAR|ESTIMATED_GENERATED)`。 6. `MULTIPLE` → `NOT_CHECKED(MULTIPLE)`。 7. `DECIDED` かつ `direct` → 型が穴の型の集合に入れば `AGREE`、入らなければ `DISAGREE`。
- `DISAGREE` の候補は候補から外し、`excluded` に理由 `HOLE_TYPE_DISAGREE` で残す（黙って捨てない）。`NOT_CHECKED` は外さない（分からないことを偽にしない）。
- RESTRICTOR だけは `AGREE` 以外を全部外す（`NOT_CHECKED` は `HOLE_TYPE_NOT_CHECKED`）。どの＋N は「N の一つ」を前提にしており、型を確かめられない候補を答えにすると前提違反になるため。N 自身（NFKC で同じ充填物）は `SAME_AS_RESTRICTOR` で外す。N の型は構造の lookup が `DECIDED`・`direct` のときのその 1 型だけ。決まらなければ状態 `HOLE_TYPE_UNDETERMINED`（候補を見ない）。
- 役割の表（`EXPECTED_TYPES`）による型一致は別の欄に写すだけで、除外に使わない（束ねず重ねる）。
<!-- w3c2-prereg:end -->

### 穴の型の事前登録の変更記録（W3-c2）

（2026-10-03 19:39:20 +0900 時点: 表・規則の変更なし。登録日時の行だけ、書き手が先に書いた日時を実際の `date` の出力に直した。出典: artifacts/w3-c2/prereg.txt）

### 穴の型の節で次のチケットが使うもの（W3-c2）

- 質問を扱う次のチケット（`vera ask --mode round5 --document` への接続など）: `semantic_read.read_question(text, lang)`（`question` 欄: `hole_role`・`hole_type`・`wh`・`kind`・`restrictor`・`hole_mark`・`declarative`）と `semantic_read.WH_TABLE`（上の表と同じ。テストが一致を確かめる）。
- 質問の十字から文書の文へ: `observe.run_entry(anchor_kind='question', ...)` の出力の `answer`（充填物・証拠の文 id・`status`）。`status` が FILLED・TIE 以外のときは答えを作らない。型の判定は本節の「穴の候補の判定」（`NOT_CHECKED` を除外にしない）。

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

## 穴の型の判定と候補（W5-d。事前登録）
<!-- w5d-prereg:begin -->
事前登録の時刻: 2026-10-03 23:07:21 +0900（`date '+%F %T %z'` の出力）。

穴の型の判定（`observe._hole_type_check`）で `NOT_CHECKED`（配置なし・UNPLACED・UNKNOWN・推定・MULTIPLE で一部が穴の外）は **候補にならない**。候補になるのは `AGREE`（direct、または MULTIPLE で全候補が穴の型の中）だけ。型を確かめられない充填物は理由 `TYPE_UNCHECKED` で `excluded` に残り、候補が無くなれば `NO_TYPED_CANDIDATE` で棄権する。規則の全文と受入基準は `docs/OBSERVATION.md` の「W5-d の事前登録」を参照。`event_cross.py` には触れない。
<!-- w5d-prereg:end -->

## 穴の型の判定と候補（W5-d。測定）
<!-- w5d-measured:begin -->

測定: 本文は `docs/OBSERVATION.md` の「W5-d の事前登録」「測定」の節。型未確認（`NOT_CHECKED`）は候補にならず、配置なしの質問の FILLED/TIE の充填物の型未確認は 68 → 0（`g2_185_noplace.json`）。

<!-- w5d-measured:end -->

## W5-d 第 2 ラウンド（W5-d2）の事前登録
<!-- w5d2-prereg:begin -->
事前登録の時刻: 2026-10-04 00:31:06 +0900（`date '+%F %T %z'` の出力。第 2 ラウンドの製品コード・テストの変更より前）。ベースは `dev` = `c875ed3`。第 1 ラウンドの `w5d-prereg`・`w5d-measured` 区間は 1 文字も変えない（第 1 ラウンドの記録）。この節が置き換えるものは、後ろの `w5d2-measured` 区間の「置き換わった記述」に列挙する。

**監査役の裁定（2026-10-04 00:05）**: B1 規則の衝突で落ちる既存テスト 78 件＋攻撃の写し 4 件は改訂を許可（K1・K2 は偽の `PlacementLookup` の注入、K3・K4・K5 は期待の改訂。名前は変えず、前後の全文を docs に）。B2 D1 の比較は正規化しない完全一致を追認（チケットの文言「NFKC 正規化後」は撤回）。B3 `recompute_q.py --check` と `w3c2-entry` 区間の例は、配置を与えた例に取り直してよい（区間の規則の本文は変えない）。追加 9 質問の観測が `VERA_PLACEMENT` を読まないのは、この後では「本番では質問がほぼ全部棄権」を意味するので、`observe.py` の question の経路で、`--placement` が無く `VERA_PLACEMENT` があるときは `event_cross.default_lookup()` の lookup を使う（収まらなければ既知の穴として次のチケットへ）。

**第 2 ラウンドの判断（中間職の指示書 D2-1〜D2-8）**
- D2-1 K1（質問の十字 15 件）: 配置の JSON（穴の充填物だけに direct の型。穴の型と食い違う型は付けない）または `O.FilePlacement` を注入する。例外 1 件（`test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun`）は「配置なしで FILLED」が主題で新しい契約と正反対なので、期待を新しい契約（配置なし → `NO_TYPED_CANDIDATE`・`TYPE_UNCHECKED`・`hole_type_check` が `NOT_CHECKED/NO_PLACEMENT`）に改訂。配置あり／なしの対のテストを足す。
- D2-2 K2（自由文→記録 52 件）: テストの中だけの `FakePlacement`（固定の名前は `UNPLACED`、列挙した普通名詞は direct の型）を注入。配置なしが主題の 3 件は期待を新しい契約（配置なし → 棄権）に改訂。**裁定の申し送り（並列の名前の過剰棄権は直さず既知の穴）からの逸脱**: 偽の配置（全語 UNPLACED）を注入しても 11 件は `ハルとセキは同じ会社だ。` の部分名 `ハル`・`セキ` に配置の答えが無く `NAME_UNVERIFIED` → `INCOMPLETE_READING` で通らない。期待を書き換えれば「弱体化」になるので、`routing_from_text.py` だけで、日本語の並列の充填物の部分名それぞれを同じ lookup に問う（R-J1 の同じ規則を部分名の配置の答えに当てるだけ。新しい規則は足さない。英語は変えない）。配置が無ければ今どおり `NAME_UNVERIFIED`。
- D2-3 K3（10 件）: 期待の値は変えず、渡した文書を実在させる（`tmp_path` の `memo.txt` に出典の `text` を書く）。K4: `artifacts/w5-d/k4_proposal.diff` をそのまま当てる。K5: 48 語の導出・バイト一致・各条件は不変、`frame_status` は `CONFIRMED` か `NOT_CONFIRMED`（後者は `frame is None`・`frame_disagreement`・助詞ごとの型が交わらない）、数は assert せず出力に一覧。
- D2-4 攻撃の写し 3 本の先頭行を `revised in W5-d2` に。G1-b は「先頭行と改訂した関数を除いて同一」。`data/` は同一。
- D2-5 D1: コードは変えない（正規化しない完全一致）。BASIS_POLICY に追認の理由を書く。
- D2-6 B3: `recompute_q.py` の `EXAMPLES` を 4 つ組（期待, 文書, 問い, 配置ファイル名）にし、`QD02`『どの人が客に切符を渡した？』（FILLED）と `QD01`『誰が生徒に地図を渡した？』（TIE）を `placement_q.json` つきに、`NO_ATTESTED_CELL` の例は今のまま。`--write` は 1 回だけ。凍結データは変えない。
- D2-7 追加 9: 製品の変更は `observe.py` の `_observe_question` の中だけ。`--placement` が無い（`StubLookup`）ときだけ `EC.default_lookup()`。充填物の型の確かめは同じ lookup に `surface` を問い直した答え。出力の `structure.placement` は実際に使った lookup の id。新しい鍵は足さない。**門**（どれか 1 つでも破れたらこの変更だけを戻して既知の穴に書く）: (1) r7 で 185 問の誤答 0・型未確認の FILLED/TIE 0、攻撃 120 問でも型未確認 0 で A01 が FILLED/TIE にならない、(2) `VERA_PLACEMENT` なしの 185 問の出力が第 1 ラウンドと byte 一致、(3) 平叙文の観測（`o1_bytes.py --child`）が基点と byte 一致（配置なしと r7 の 2 通り）。FALSE_NONE の増分と TIE が FILLED に縮む件は数えて書くが門にしない。
- D2-8 置き場所: 本区間（事前登録）、`w5d2-measured`（測定）、`w5d2-amended`（改訂したテストの前後の全文。`artifacts/w5-d/r2/scripts/amended_texts.py` で生成）。K1・B3・D2-7 → OBSERVATION、K2・D2-2 → ROUTING_FROM_TEXT、K3・K4・D1 → BASIS_POLICY、K5 → COARSE_PLACEMENT、EVENT_CROSS には穴の型の節への 1 段落。

**測り方（測る前に固定。出力はすべて `artifacts/w5-d/r2/`）**
- G1: 攻撃の写し 36 本が全部通る（`tests/attack/w3c2`・`test_attack_w5b_wave2.py`・`test_attack_w5c_*.py` 2 本・`tests/attack/w3a3/test_attack_w3a3_r6.py`）、K の 82 id が全部通る、G1-b は上のとおり。
- G2: 実装役の 185 問を（配置なしの環境 × place/noplace）と（`VERA_PLACEMENT=r7` × place/noplace）、攻撃 120 問を r7 で。誤答 0、型未確認の充填物を持つ FILLED/TIE 0。
- G3: 経路づけの凍結 4 本（配置なし）と 2 本（r7）の misroutes 0、合成 `g3_synth` を同じ入力で流し直して配置なしで誤って振った数 0。r7 は第 1 ラウンドの 1 から増えない。D2-2 の影響として r7 の 2 本の単位ごとの状態を第 1 ラウンドと比べる。
- G4: `g4_probe` の写しを流し、入力の sha256 と `summary` が第 1 ラウンドと同じ（`basis_policy.py` は第 2 ラウンドで変えない）。
- G5: r7 は作り直さない。`verify` が `OK`、`content_sha256` が第 1 ラウンドと同じ。
- G7: `pytest tests`（最後に 1 回）の失敗集合が基線から増えない。基線に無い失敗は環境由来だけ。K の id が残れば改訂を見直す。

**この文書の担当**: 穴の型の節への 1 段落。質問の穴の型の確かめは、`--placement` が無ければ `VERA_PLACEMENT` の配置（`event_cross.default_lookup()`）で行う（D2-7）。

<!-- w5d2-prereg:end -->

## W5-d 第 2 ラウンド（W5-d2）の測定
<!-- w5d2-measured:begin -->
**質問の穴の型の確かめと `VERA_PLACEMENT`（第 2 ラウンド）**: 上の「穴の型による候補の判定」と W5-d の節の穴の型の確かめ（`observe._hole_type_check`）は、`--placement` が無いとき、読解器・事象の十字と同じ `event_cross.default_lookup()`（`VERA_PLACEMENT` の粗い配置。空・未設定なら配置なし）の lookup で充填物の `surface` を問い直して行う。`--placement` や呼び手が渡した lookup があればそれが勝つ。新しい規則は足していない（質問の観測の出力 `structure.placement` が実際に使った lookup の id になるだけ）。`event_cross.py` には触れていない。測定と門は `docs/OBSERVATION.md` の `w5d2-measured`。

**第 2 ラウンドで置き換わった記述**: 第 1 ラウンドの `OBSERVATION.md` の「Q-J4: 質問の観測は `VERA_PLACEMENT` を読まない」。

測定の時刻: 2026-10-04 01:22:30 +0900。出力はすべて `artifacts/w5-d/r2/`（ファイル名を添える）。中間職のレビュー r1（`review-impl/W5-d2/review.r1.md`）の M1〜M4（改訂したテストの前後の全文・測定の区間・失敗集合のファイル・報告）に応えてこの区間と `w5d2-amended` 区間を書いた。製品とテストのコードはレビューのあとに変えていない（`code_sha_r2b_start.txt` と `code_sha_r2b_end.txt` が同じ）。受入の測定はこのとき全部流し直した（`g1_rerun_r2b.txt`・`g2_rerun_r2b.txt`・`g3_rerun_r2b.txt`・`q1_observe_cmp_r2b.txt`・`g4_compare_r2b.txt`・`q5_r7_verify_r2b.txt`・`k5_check_r2b.txt`。出力は前の流しと byte 一致。違いが無かったことの確認なので前の流しのファイルも残す）。
<!-- w5d2-measured:end -->

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

### W3-b3 の追記: `--events` の出力例（実行出力の抜粋。連体修飾節の文。`embedded` の入った形）
コマンド: `cd <木> && VERA_PLACEMENT=<配置 r6> PYTHONPATH=<木> python -m verantyx.semantic_read --text='母が弟に話した人を兄が呼んだ。' --events`（出力全体は `artifacts/w3-b3/entry_examples.txt` と、`events` だけの抜粋を下に貼る。`crosses[1]` の腕 `patient` の充填物 `人` の中に、関係節の十字 `crosses[0]`（話す）が入っている。`counts` は埋め込みを数え足していない）:

```json
{
 "status": "CROSSED",
 "relations": [
  {
   "type": "relative",
   "from": 0,
   "to": 1,
   "head": {
    "from_role": "patient",
    "to_role": "patient"
   }
  }
 ],
 "counts": {
  "crosses": 2,
  "arms": 5,
  "arm_ties": 0,
  "agreement": {
   "AGREE": 3,
   "DISAGREE": 0,
   "NOT_CHECKED": 2
  },
  "not_checked_by_reason": {
   "ARM_TIE": 0,
   "ROLE_NOT_IN_TABLE": 2,
   "LOOKUP_RESULT_INVALID": 0,
   "NO_PLACEMENT": 0,
   "UNKNOWN": 0,
   "UNPLACED": 0,
   "ESTIMATED_NEAR": 0,
   "ESTIMATED_GENERATED": 0,
   "MULTIPLE": 0
  }
 },
 "crosses[1].arms.patient.fillers[0]": {
  "surface": "人",
  "head": "人",
  "head_basis": "surface",
  "keys": [
   "surface",
   "head",
   "head_basis",
   "place",
   "flags",
   "embedded"
  ],
  "embedded": {
   "index": 0,
   "center": {
    "predicate": "話す",
    "polarity": "+",
    "tense": "past",
    "modality": null,
    "voice": "active"
   },
   "arms": {
    "agent": {
     "kind": "FILLER",
     "surfaces": [
      "母"
     ],
     "agreement": "AGREE"
    },
    "patient": {
     "kind": "FILLER",
     "surfaces": [
      "人"
     ],
     "agreement": "NOT_CHECKED"
    },
    "recipient": {
     "kind": "FILLER",
     "surfaces": [
      "弟"
     ],
     "agreement": "AGREE"
    }
   }
  }
 },
 "crosses[0]": {
  "index": 0,
  "center": {
   "predicate": "話す",
   "polarity": "+",
   "tense": "past",
   "modality": null,
   "voice": "active"
  },
  "arms": {
   "agent": {
    "kind": "FILLER",
    "surfaces": [
     "母"
    ],
    "agreement": "AGREE"
   },
   "patient": {
    "kind": "FILLER",
    "surfaces": [
     "人"
    ],
    "agreement": "NOT_CHECKED"
   },
   "recipient": {
    "kind": "FILLER",
    "surfaces": [
     "弟"
    ],
    "agreement": "AGREE"
   }
  }
 }
}
```

### W3-b3 の追記: 測定（出典は `artifacts/w3-b3/`。数値は `tests/reading_soundness/w3b3_recompute.py` の出力と同じ行で、`docs/READING_SOUNDNESS.md` §10C の K123 の節にも貼った）
- 埋め込みの数・`RELATION_HEAD_NOT_WELL_FORMED`・E1 は、K123 の節の次の行（`十字（…）`・`十字の E1（…）`）。この節に同じ行を貼る:

<!-- w3b3-measured-events:begin -->
- 十字（`entry_r6.jsonl` の読めた 490 文を `StubLookup` で十字にした）: `head` を持つ関係の文 13・埋め込みの十字 13・十字にできなかった文（INPUT_REJECTED を含む）0
- 十字の E1（`e1.txt`）: E1_SAME, E1_SAME_WITH_PLACEMENT, E1_EQUALS_DEV_RUN, E1_EQUALS_DEV_RUN_WITH_PLACEMENT, E1_CODES_EQUAL_DEV
<!-- w3b3-measured-events:end -->

- 観測（W3-c）: `EDGE` の移動が、この経路が書いた関係（cause・contrast・condition・concession・simultaneous・relative）で動く。関係節の文は、`crosses[to]` の腕の充填物に `embedded` が入った形になるが、観測の升の鍵 `content_of_cross`（`observe.py` 80〜91 行）は充填物の `embedded` を含めないので、升の同一性は変わらない。`TE_UNDETERMINED`・`PARALLEL_UNDETERMINED` は `CrossReading` に入らず、観測の `EDGE` の対象にならない。


## W5-e の追記: `role_flags` の `coordination`（事前登録）
<!-- w5e-b-event-prereg:begin -->
事前登録の時刻: 2026-10-04 03:59:31 +0900（`date '+%F %T %z'`）。この節は `tests/test_event_cross_w5e.py` を書く前、`verantyx/event_cross.py` を直す前に確定した。上の節は 1 文字も変えない。

- 読解器の入口が節に書く `role_flags` は `{役割: {"determiner": 直前の指示詞}}`（W3-b2）。W5-e で、鍵 `coordination`（値は `と`・`や`・`か` のどれか 1 つ）を **受ける形だけ** 置く: `role_flags[役割]` の鍵の集合が `{'determiner'}`・`{'coordination'}`・その両方のどれかで、値は空でない文字列（`coordination` は 3 字のどれか）なら形は正しい。`determiner` だけの入力の判定は変えない。それ以外（空・別の鍵・`coordination` の値が 3 字以外・文字列でない）は今どおり `ENTRY_FLAGS_NOT_WELL_FORMED`。
- `role_flags[役割]` が `coordination` を持つとき、その役割は十字にしない: `INPUT_REJECTED`、理由 `COORDINATION_UNMARKED:<役割>`（`Filler.coordination` の印を作る経路は作らないので、並立・選言の印の付いた値を印なしの `FILLER` にしない）。
- 今の読解器（W5-e）は並立・選言の節を `unsupported` に入れて棄権する（READING_SOUNDNESS.md §10E）ので、この印を出さない。製品の経路でこの理由は出ない。合成の入力のテストだけで確かめる。
- 表層の字面で拒む守り（充填物に `か` を含む文字列を拒む）は **作らない**: `ハルとセキ` を 1 つの値として渡す経路づけの既存テスト・`赤坂` のような語を巻き込むため。
<!-- w5e-b-event-prereg:end -->


### W5-e の測定: `role_flags` の `coordination`
<!-- w5e-b-event-measured:begin -->
測定の時刻: 2026-10-04 04:10:06 +0900。`tests/test_event_cross_w5e.py` は `22 passed`（`artifacts/w5-e/new_tests_run.txt`。凍結 `frozen_b.sha256`、直す前に落ちる記録 `b_before_fail.txt`: 6 件が失敗、形の検査・`determiner` だけの入力・表層の字面で拒まないことの 16 件は直す前から通る）。`determiner` だけの入力は変更前と同じ判定（既存の `tests/test_semantic_read_w3b2_events.py` の `role_flags` のテストは無傷）。製品の経路で `COORDINATION_UNMARKED` が出ないこと: 読解器は並立・選言の節を `unsupported` に入れて棄権するので `role_flags` に `coordination` を書かない。変更は `event_cross.py` の定数 1 つ・`_flag_well_formed`（新設）・`_check` の `role_flags` の検査の 3 か所だけ。
<!-- w5e-b-event-measured:end -->

### W3-c7 の追記（2026-10-05 07:28）
- `RELATION_TYPES`（11 種）は変えない。`sequence`・`quote` は既にある。連用中止の種類 `parallel` は関係の型にしない（採点器の `REL_TYPES` に無く、W3-b3 の凍結データの正解は `sequence`）。種類は診断と表 `w3c7_edges`（`docs/READING_SOUNDNESS.md` §10K）にだけ書く。
- 段 C7 の出力（3〜4 節・て・連用中止・引用）は既存の `_check`・`_embed` をそのまま通る。入れ子の head は作らない（ある節が head を受け、かつ自分も次の relative の左にある文、同じ役割への 2 つの head は段 C7 が棄権する。`_check_heads` が `nested`・`duplicate_target` を拒むため）。
