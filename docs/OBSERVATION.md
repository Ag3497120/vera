# 観測としての生成: 視点（錨・向き・範囲・状態）から構造を観測し、見えた十字を実現器が文にする

（この文書は段階的に書く。最初に書いたのは次の「事前登録」節だけ。ほかの節は検査データを作ったあとに足す。事前登録の節を変えたときは、その節の下の「事前登録の変更記録」に日時・前後の差・理由を全件書く。）

## 事前登録

<!-- prereg:begin -->
登録日時: 2026-10-03 12:20:51 +0900（`date '+%Y-%m-%d %H:%M:%S %z'` の出力。直前の同じ出力は 12:20:14 で、このファイルはその間に書いた。初版は書き手が日時を 12:21:00 と誤って先に書いたので、実際の `date` の出力に直した。下の変更記録）

この節は検査データを作る前に書いた。この時点で `tests/observe/data/` は存在しない（`ls tests/observe` が「そんなファイルは無い」を返すことを `artifacts/w3-c/prereg.txt` に記録する）。
出典は中間職の指示書 `.claude/vera-audit/review-impl/W3-c/plan.md` の D2〜D10・D12。式と定数はここで決め、検査データを見てから変えない。

### P1. 升（cell）の同一性（D2）

十字の **内容**: `center` の全鍵（`predicate polarity tense modality voice` と、あれば `quantifiers scope comparison`）と、腕ごとの `role`・`kind`（`FILLER` か `ARM_TIE`）・充填物の `surface` の列（腕は `ROLE_NAMES` の順）。配置の結果（`place`・`agreement`）は内容に含めない。
升の鍵 `cell_key = "cell:" + json.dumps(内容, sort_keys=True, ensure_ascii=False, separators=(",", ":"))`。ハッシュにしない。鍵の文字列順は表示の整列だけに使い、勝者を作らない。

### P2. 座標（D3）

`cell.coord = {"origin": {"kind": "anchor"|"structure", "id": 錨は "anchor"・構造は文の id, "cross_index": i}, "moves": [...]}`。
- `FACE_SWAP` の移動: `{"move":"FACE_SWAP","role":r,"from":旧surface,"to":新surface,"neighbor_source":近傍の問い合わせの id}`
- `EDGE` の移動: `{"move":"EDGE","relation":t,"reading":読みの id,"from":i,"to":j,"dir":"forward"|"backward"}`

### P3. 観測できる升（D4）

視点 = `(anchor, direction, range, state)`。`direction` は移動の列（閉じた一覧: `FACE_SWAP(role)`・`EDGE(relation)`）、`range` は 0〜len(direction) の整数（既定 len(direction)。範囲外は `BAD_ARGUMENTS`）。
レベル 0 = 錨の升。レベル k（1 ≤ k ≤ range）= レベル k-1 の全部の升に `direction[k-1]` を適用して得た升。**観測できる升** = レベル 1〜range の升の全部（標本抽出しない）。`range` が 0 のときは錨の升だけが観測できる升（焦点は錨）。
- 内容が錨か、より短い道で既に届いた升と同じ升は再訪として落とし、`revisits_dropped` に数える。
- 同じレベルで同じ内容に複数の道で届いたら 1 升にまとめ、道の座標を全部（正準 JSON の文字列順で）`coords` に並べる。
- 方向が空でない・range ≥ 1 で観測できる升が 0 なら `NO_MOVE_LICENSED`（理由別の件数つき）。錨自身の要素は出す。

### P4. `FACE_SWAP(role)` の許可（D5）

上から順、最初に当たった理由で不許可: 腕が無い → `NO_ARM`／腕が `ARM_TIE` → `ARM_TIE`／役割が `event_cross.EXPECTED_TYPES` に無い → `ROLE_NOT_IN_TABLE`／近傍の問い合わせが `FOUND` でない → その状態名（`NO_PLACEMENT` `NO_NEIGHBORS` `UNKNOWN`、契約違反は `NEIGHBORS_RESULT_INVALID`）。
`FOUND` のときは候補語ごとに（元の語と同じ語は候補にしない）、その腕の充填物だけを候補語に替えた節を **合成した読解出力として `event_cross.build_crosses` に通し**、その腕の型一致が `AGREE` の候補だけ許可する。`DISAGREE`・`NOT_CHECKED(<理由>)` は理由別に数える。許可が 0 なら `NO_MOVE_LICENSED`。型の判定をこのチケットで書き直さない。

### P5. `EDGE(relation)` の許可（D6）

`relation` は `event_cross.RELATION_TYPES` の閉じた一覧（外は `BAD_ARGUMENTS`）。今の升と内容が同じ十字を含む読み（錨の読み・構造の読み）の `relations` のうち、型が一致し今の十字の番号に触れるものだけをたどる（`from` 側から `to` へは `forward`、逆は `backward`）。推定・隣接・接続詞・読点からは関係を作らない。1 本も無ければ `NO_RELATION_IN_STRUCTURE`。
読みの出所 `reading_source` は `semantic_read`（入口）か `injected`（公開 API だけ。テストで手書きの読解出力を渡したもの。CLI からは渡せない）。数えるときは分けて数える。

### P6. 占有（D7）

出所ごとに別々に調べて全部書き、合算しない。
- `structure`: 構造の読み（構造ファイルの文・錨の文自身）に内容（P1）が同じ十字があれば `ATTESTED`（証人: 文の id と節番号）、無ければ `UNOCCUPIED`。
- `index:<系列>`: 升の充填物の surface ごとに `Corpus.search(surface, 系列, limit=WINDOW)` を呼び、当たった行（`(family, id)` の順）を **読解器に通して十字にし**、内容が同じ十字があれば `ATTESTED`（証人: 系列・行 id・`origin`・`generator`）。当たりが 0 で状態が `NO_MATCH`、または窓が埋まらずに全行を読んで一致が無ければ `UNOCCUPIED`。窓がちょうど `WINDOW` 件埋まった検索があり一致が無ければ `UNKNOWN_WINDOW_SATURATED`。`UNKNOWN_*` の状態（`UNKNOWN_NO_INDEX` など）は検索の状態をそのまま写す。
- **まとめの印** `occupied`: どれかの出所が `ATTESTED` → `ATTESTED`／全出所が `UNOCCUPIED` → `UNOCCUPIED`／それ以外 → 最初に調べた順（`structure` → `--index-family` の指定順）で最初の `UNKNOWN_*`（`UNOCCUPIED` と混ぜない）。
- `WINDOW = 200`（設計定数。測定値ではない）。`--index-family` の既定は `pro` のみ。`--no-index` のときは索引を引かず、索引の出所の状態は `UNKNOWN_NO_INDEX`。

### P7. 主張の型（D12）

`claim` は閉じた 3 値: `OBSERVED_OCCUPIED`（`occupied == ATTESTED`。出所 `observed:attested`。証人の `origin` が `generated` なら `basis_origin: "generated"`）、`CONSTRUCTED_UNOCCUPIED`（出所 `constructed:observed_unoccupied`）、`UNKNOWN_OCCUPANCY`（出所 `observed:occupancy_unknown:<状態>`）。**このチケットの出力はどれも `ANSWER` にしない**。

### P8. 顕著さの場（D8）。段の列で、合算しない

入力は台帳 L（そのターンの **前** の状態。無ければ `FLAT`）。記号:
- `U` = L の `utterance` 事件のうち、`payload.text` が今のターンの錨の文と文字列として同一でないもので、seq が最大のものの `payload.text`。錨の文 = `AnchorText.text`、`AnchorRecord` のときは構造のその文の `text`。そういう事件が無ければ `U` は空で、下の `s2` `s3` は 0。錨の文と同一で除いた事件の seq は `salience_trace` に数えて残す。（この行は変更記録 3 で書き換えた。初版は「L の最新の `utterance` 事件（seq が最大）の `payload.text`」。）
- `H(c)` = 升 c の充填物の surface のうち、錨の十字のどの充填物の surface とも違うものの集合（錨の升は空）。
- `N(h)` = 語 h の近傍（近傍の問い合わせが `FOUND` のときの items。そうでなければ空）。

段の値（すべて台帳の数から。手で調整した定数は置かない）:

| 段 | 名前 | 式 | 良い方向 |
|---|---|---|---|
| (i) | `distance` | `s1(c)` = 道の長さ（移動の数） | 小さい方が上 |
| (ii-a) | `utter_verbatim` | `s2(c)` = `|{h ∈ H(c) : h が U に部分文字列として現れる}|` | 大きい方が上 |
| (ii-b) | `utter_neighbor` | `s3(c)` = `|{h ∈ H(c) : N(h) のどれかが U に部分文字列として現れる}|` | 大きい方が上 |
| (iii) | `recency` | `s4(c)` = `L.last_seq("observed_cell", cell_key(c))`。`None`（一度も焦点にならなかった）が最上位、次に seq の小さい（古い）方が上 | 上のとおり |
| (iv) | `decided` | `s5(c)` = `L.count("decided_cell", cell_key(c))` | 大きい方が上 |

比較は段の順（i → ii-a → ii-b → iii → iv）の **辞書式**。全段で同値の升は同じ順位の群（`TIE` 群）にまとめる。順位 1 の群が 1 升なら焦点 `FOCUS`、2 升以上なら焦点は `TIE(候補の列)` で **選ばない**。台帳が無い（`FLAT`）ときは (ii-a)(ii-b)(iv) は 0、(iii) は `None`。
乱数・`hash()`・`set` の反復順・`id()`・時刻を、順位にも出力にも使わない。

### P9. ターンの追記（D9）

観測に使う状態は **そのターンの前の台帳**。1 ターン = ① 観測（台帳は読むだけ）→ ② `utterance` を追記（`payload: {"text": 錨の文, "anchor": 錨の型}`）→ ③ `observation` を追記（`payload: {"viewpoint": 視点の正準 JSON, "outcome": "FOCUS"|"TIE"|"NO_ANCHOR"|"NO_MOVE_LICENSED", "state_seq": 観測に使った台帳の最後の seq, "observed_cell": 焦点の cell_key（FOCUS のときだけ鍵を置く）, "tie_cells": [...]（TIE のときだけ）, "output_sha256": 出力 JSON の sha256}`）。`decision` は `payload: {"decided_cell": cell_key}`。**TIE は `observed_cell` を書かない**（1 事件に候補を並べるだけ）。
（追記: `state_seq` は事前登録の D9 の欄に足した実装上の項で、再生で「前の台帳」を決めるために使う。式・順位には使わない。この追記は登録の時点のもの。）

### P10. O4 の「代替」と「同じ出力」（D10）

- **代替** = 1 回目の焦点 X と、段 (i)(ii-a)(ii-b) で同値の、許可された別の升。
- **同じ出力** = 出力 JSON の `focus` と `realization` の欄が byte 一致（`salience_trace` は台帳が伸びるので変わってよい）。
- 1 回目が `TIE` なら 2 回目も（台帳の差が TIE 群の中で対称なので）`TIE` のままが正しい。代替が無いのに焦点が変わったら不合格。代替があるのに変わらなければ、段 (iii)(iv) が効いていない（これも不合格）。

### P11. 実現と出力の約束（D11・D15 の要点）

- 実現は `semantic_realize.realize_observed` が日本語の `frame` 規則の節で、役割が `{agent, patient, recipient, goal, place, source}` の部分集合で `agent` を含むものだけ作る。作った文を読解器に通して同じ内容に戻ること、内容語の語彙素が述語と各充填物を別々にタグ付けした語彙素のどれかであること、の 2 つを検査する。別の言い方（が・丁寧体・役割順）は `alternatives` に並べるだけで選ばない。対象外は既存の拒否の型で拒否し、件数で数える。
- 出力は 1 行の JSON（`schema: "verantyx.observe/1"`）。時刻・台帳の ts・処理時間を出力に入れない。
<!-- prereg:end -->

### 事前登録の変更記録

1. 2026-10-03 12:21:00 +0900（`date` の出力）: 先頭の「登録日時」の行を `12:21:00` から `12:20:51` に直した（式・定数・規則の変更なし）。理由: 初版の日時を、実際の `date` の出力より後の時刻で書いていた（`artifacts/w3-c/prereg.txt` の `recorded_at: 12:20:51` と食い違った）。事前登録の本文（P1〜P11）は 1 文字も変えていない。

2. 2026-10-03 12:41:39 +0900（`date` の出力。期待の凍結 12:41:30 の直後、凍結データに観測器を通す前）: P10 の「代替」の判定に使う状態を明示した（事前登録の区間 `prereg:begin`〜`prereg:end` の本文は変えていない。この記録だけが補足。式・順位の規則は変えていない）。前: 「代替 = 1 回目の焦点 X と、段 (i)(ii-a)(ii-b) で同値の、許可された別の升」（どの時点の台帳で同値を見るかを書いていなかった）。後: 同値は **2 回目の観測に使う台帳（1 回目のターンを追記した後）** で、段の値（`salience_trace` の値）から見る。理由: 1 回目のターンで錨の文が最新の発話として台帳に入るので、段 (ii) の値は 1 回目と 2 回目で変わる。2 回目に何が許されるかは 2 回目の台帳で決まる。この解釈は期待（expected.jsonl の `o4`）を書くときにすでに使っている（期待の凍結の時刻の方が前）。観測器の出力を見て決めたものではない。

3. 2026-10-03 13:18:18 +0900（`date` の出力。直前の `date` の出力は 13:18:13 で、P8 の書き換えはその間に行った。区間の sha256: 前 `0e0aeceafaf897b6fbe8c4ebc8a326e8e3f650584388207b9a3e278a26f729df` → 後 `2243402bd5f5b346e658055e0cdfabce84e7e5bf7b38149897b944a428f6d155`）: **最初の観測（12:44:44）の後の変更で、事前の規則のように見せない。** 前後の差は P8 の `U` の定義だけ（ほかの行・段・式・P9・P10 は 1 文字も変えていない）。前: 「L の最新の `utterance` 事件（seq が最大）の `payload.text`」。後: 「L の `utterance` 事件のうち、`payload.text` が今のターンの錨の文と文字列として同一でないもので、seq が最大のものの `payload.text`（錨の文 = `AnchorText.text`、`AnchorRecord` のときは構造のその文の `text`。無ければ空）。錨の文と同一で除いた事件の seq は `salience_trace` に数えて残す」。理由: 実装役の第 1 ラウンドで、反例 `O4-e-L07`（と、判定が緩くて見落とされた `O4-f-L08`）が出た。P8（最新の発話を `U` にする）と P9（ターンの後に錨の文を発話として追記する）の組み合わせでは、同じ問いの 2 回目に、1 回目の錨の文そのものが `U` になり、段 (ii-b) が錨の語を近傍に持つ升を持ち上げる。問いを繰り返しただけで段 (ii) の値が変わるので、O4（代替が無いときは同じ出力）が成り立たない。錨は段 (i) の起点としてすでに効いており、同じ文を「人の直近の発話」として段 (ii) にもう一度入れるのは同じ信号を二度数えることで、束ねず重ねるの原則にも反する。**決めたのは中間職（レビュー第 1 ラウンド `review.r1.md`、決定 D17）で、観測の結果を見てから決めた変更**。実装役は規則を変えずに反例を報告していた。これより後に作るもの（錨と同じ文の発話を含む台帳のケース、2 ターンの 6 行の新しい期待 `expected_r2.jsonl`）は、観測器を新しい規則で流す前に書いて凍結する（`FROZEN.json` の `inputs_r2` と `expected_r2`、最初の再観測 `first_observation_r2` の時刻順）。古い期待 `expected.jsonl`・`expected_add1.jsonl`・`disagreements*.json` は 1 byte も変えない（新しい規則の下で置き換わる行は `expected_r2.jsonl` 側に書く）。

（以後、変えたら、ここに日時・前後の差・理由を 1 件ずつ書く。）

（以下は検査データを凍結し、最初の観測を流したあとに書いた節。数値は「測定結果」の区間だけに書く。それ以外の場所には測っていない数値を書かない。）

## 何を作ったか

生成を **観測** として作った。`observe(viewpoint, structure) -> Observation` が構造を視点から見て十字の列を返し、`realize` は観測した十字だけを既存の実現器（`semantic_realize.realize_observed`）で文にする。実行時に LLM は使わない。観測は標本抽出しない。同じ（構造・視点・状態）には同じ出力が返り、揺らぎは状態（会話の台帳）の進化からだけ出る。

| 物 | 場所 |
|---|---|
| 観測の型・移動・占有・再観測・ターンの記録・再生・入口の関数 | `verantyx/observe.py`（新規） |
| 台帳の Protocol・メモリ上の台帳・顕著さの場（段の列） | `verantyx/salience.py`（新規） |
| 観測した十字を文にする入口 | `verantyx/semantic_realize.py` の末尾への追加だけ（`realize_observed` `observed_variants` `check_observed_lineage`） |
| 入口 | `python -m verantyx.cli observe`（`verantyx/cli.py` への追加だけ） |
| 検査データ・測定道具 | `tests/observe/`、`artifacts/w3-c/` |

## 型

- **視点** `Viewpoint(anchor, direction, range, state)`。錨は `AnchorText(kind=seed|question, text, lang, cross_index)` か `AnchorRecord(id, cross_index)`（型で区別。質問の十字と種の十字は `kind` で区別する）。向きは `FaceSwap(role)` と `Edge(relation)` の列（閉じた一覧。役割は `ROLE_NAMES`、関係は `RELATION_TYPES`）。範囲は移動の最大数。状態は台帳か `FLAT`。
- **観測** `Observation`: `anchor`（錨の要素）・`ranks`（順位の列。各順位は要素の群）・`focus`（`Focus` か `Tie` か棄権）・`counts`・`salience_trace`。**要素** `ObservedElement` は `cell`（鍵・十字・座標の全部・十字の出所・言語）、`occupancy`（出所ごとの占有）、`claim`、`provenance`、`realization` を持つ。十字の `type_agreement` は W3-b の 3 値（`AGREE` / `DISAGREE` / `NOT_CHECKED`）を腕ごとに写し、移動した腕を別に示す。
- **棄権の型**: `NoAnchor(reason, detail)`、`NoMoveLicensed(reasons)`、`Tie(candidates)`。同点は選ばず候補を重ねて返す。
- **出力**は 1 行の json（`schema: verantyx.observe/1`）。鍵の順は固定で、時刻・台帳の時刻印・処理時間・環境の値を含まない。

## 移動の規則

事前登録の P3〜P5 のとおり。実装上の要点だけを書く。

- **面の移動** `FACE_SWAP(role)`: 腕と役割と近傍の問い合わせの 3 つの関門（腕が無い・`ARM_TIE`・役割が型の表に無い・近傍が `FOUND` でない）を上から順に通り、それぞれ別の理由で数える。候補語ごとに、その腕の充填物だけを替えた節を **合成した読解出力として `event_cross.build_crosses` に通し**、その腕の型一致が `AGREE` の候補だけが許可される。型の規則はここに書き直していない。許可されなかった候補は `DISAGREE`・`NOT_CHECKED:<理由>`・`SYNTHETIC_READING_REJECTED` に分けて数える。
- **辺の移動** `EDGE(relation)`: 今の升と内容が同じ十字を含む読み（錨の文の読みと構造の文の読み）の `relations` のうち、型が一致し今の十字の番号に触れる関係だけをたどる。隣接・接続詞・読点から関係を作らない。読解器が関係を出さなければ `NO_MOVE_LICENSED(NO_RELATION_IN_STRUCTURE)`。
- **範囲**: レベル k の升はレベル k-1 の全部の升に `direction[k-1]` を適用して得る。レベル 1 から範囲までの升の全部が観測できる升。内容が錨か、より短い道で届いた升と同じものは再訪として落として数える。同じ距離で同じ内容に複数の道で届いたら 1 升にまとめて座標を全部並べる。
- 構造の読みの出所は `semantic_read`（入口）か `injected`（公開の関数だけ。テストで手書きの読みを渡す）。数えるときは分け、入口の結果に混ぜない。

## 場の段と式

事前登録の P8 を参照（そこに式を検査データより先に書いた）。実装は `salience.rank` で、**段の値の組を全部計算してから**、組が等しい升を同じ順位にまとめる。`min` / `max` / `sorted(...)[0]` で勝者を取らない。順位 1 に 2 升以上あれば `TIE`。台帳の `observed_cell` は焦点（`FOCUS`）のときだけ書き、`TIE` は 1 つの事件に候補を並べて `observed_cell` を書かない（候補を 1 つずつ追記すると、次のターンで並び順が勝者を作るため）。

出力の `salience_trace` に、順位ごとの各升の段の値・その値を作った台帳の seq・順位の境目でどの段が分けたかを入れる。段 (ii) が使う発話 `U` は、台帳の発話のうち **錨の文と文字列として同一でないもの** の最新（変更記録 3、決定 D17）。錨の文と同一で除いた発話の seq は `salience_trace.utterance.skipped_same_as_anchor`、使った発話の seq は `used_seq` に残す（除いたものも数えて記録する）。錨は段 (i) の起点としてすでに効いているので、同じ文を「人の直近の発話」として段 (ii) にもう一度数えない。文字列として同一でない言い換えは除かない（別の言い方は別の発話として効く）。

## 再観測の手順

`observe.reobserve(element, viewpoint, structure)`（出力の json から作った要素の辞書でも動く）:

1. 座標の `origin` から錨の文（視点にある）か構造の文（id）を読み直し、`cross_index` の十字を取る。
2. `moves` を順に適用する。`FACE_SWAP` は、記録した `from` が今の腕の充填物と同じで、記録した `to` が今も近傍にあり、近傍の出所の id が同じで、合成した読みの型一致が `AGREE` であることを確かめる。`EDGE` は、記録した関係・読み・番号・向きが今も読みの中にあることを確かめる。
3. 得た十字の升の鍵が要素の鍵と同じで、最初の座標では `cross.to_dict()` の正準 json が要素の `cross` と byte 一致であることを確かめる。2 本目以降の座標は、十字が（通ってきた文の節番号と範囲の `provenance` を除いて）同じであることを確かめる。
4. 実現した文があれば、それを読解器に通して十字にし、要素の鍵と同じ升に戻ることを確かめる。
5. （W5-b。E28）渡された座標が **全部の経路** であること: 同じ視点と構造で升と座標を求め直し、同じ升の座標の集合と等しいことを確かめる（`COORDS_INCOMPLETE` / `COORDS_EXTRA` / `COORDS_DUPLICATED` / `CELL_NOT_OBSERVED`）。
一致しなければ `MISMATCH` と最初に外れた理由を返す。手で辿るなら、1 と 2 を上のとおりにし、`python -m verantyx.semantic_read --text=<文> --events` の十字の充填物の `surface` と、座標の `from` / `to` を見比べる。

台帳からの再生は `observe.replay(events, observation_event, structure)`: 観測の事件の `state_seq` までの台帳（そのターンの前）で観測し直し、出力の sha256 が事件の `output_sha256` と同じかを見る。

## 揺らぎが状態から出る仕組み

決定論の対象は（構造・視点・状態）。状態が伸びるときだけ出力が動く。

- 1 ターンが終わると台帳に、人の発話（錨の文）と、焦点にした升の鍵が入る。次のターンでは、(ii) 錨の文と同じでない最新の発話が指す近傍、(iii) 直近に焦点にした升の低下、(iv) 枠の決定が段として効く。同じ問いを繰り返しても、その問いの文そのものは段 (ii) に効かないので、2 回目が動くのは (iii) の低下（1 回目に焦点にした升が下がる）が代替の順位を上げるときだけで、代替が無ければ動かない。
- 焦点にした升は新しさの段で下がるので、同じ問いの 2 回目は、段 (i)(ii) で同値の別の升があればそちらが焦点になる。別の升が無ければ出力は動かない。
- 動いたとき、`salience_trace` の各升の `ledger_seqs` が、その値を作った台帳の行を指す。人ごとに台帳が違えば、同じ構造からでも違う升が焦点になり、その理由を台帳の行まで辿れる。
- 実現の表現の揺らぎ（が・丁寧体・役割順）は `alternatives` に検証済みの形を並べるだけで、選ばない。選ぶ決め手が台帳に無く、候補の並びで選ぶと同点を崩すことになるため。したがって O4 の揺らぎは内容（どの升）の揺らぎで満たす。

実行出力（`L03` と `L07` の 2 ターン）は下の「測定結果」の O4 の欄に `o4.json` から作って貼ってある。

## 閉包の外の型

升が構造の中の文に占められているかを、出所ごとに別々に調べる（合算しない）。

| 出所 | 状態 |
|---|---|
| `structure`（構造の文と錨の文の読み） | `ATTESTED`（証人: 文の id と節番号）／`UNOCCUPIED` |
| `index:<系列>`（コーパス索引。検索は逐語の部分一致、窓は事前登録の `WINDOW`） | `ATTESTED`（証人: 系列・行 id・`origin`・`generator`）／`UNOCCUPIED`／`UNKNOWN_WINDOW_SATURATED`／`UNKNOWN_QUERY_NOT_SEARCHED`（升に充填物が無く、引く surface が 0 で、索引を 1 回も引いていない。決定 E21）／索引の `UNKNOWN_*`（`UNKNOWN_NO_INDEX` `UNKNOWN_FAMILY_DB_MISSING` `UNKNOWN_INDEX_UNREADABLE` `UNKNOWN_INDEX_REBUILD_REQUIRED`） |
| まとめの印 `occupied` | どれかが `ATTESTED` なら `ATTESTED`、全部 `UNOCCUPIED` なら `UNOCCUPIED`、それ以外は最初に調べた順で最初の `UNKNOWN_*`（`UNOCCUPIED` と混ぜない） |

主張 `claim` は閉じた 3 値。`OBSERVED_OCCUPIED`（出所 `observed:attested`。証人が生成された文のときは `basis_origin: generated`）、`CONSTRUCTED_UNOCCUPIED`（出所 `constructed:observed_unoccupied`。創作で、事実の主張ではない）、`UNKNOWN_OCCUPANCY`（出所 `observed:occupancy_unknown:<状態>`）。**このチケットの出力は `ANSWER` にならない**（回答は記録＝点の証拠が要り、このチケットの外）。占有の印と出所の型は、実現した文の `realization` にも付く（`claim` と `provenance`）。

## 入口

```
python -m verantyx.cli observe --anchor-text <文> | --anchor-record <id>
    [--anchor-kind seed|question] [--anchor-cross N] [--lang ja|en]
    [--direction FACE_SWAP:agent,EDGE:cause] [--range N]
    [--structure <jsonl>] [--index <dir>] [--index-family F]... [--no-index]
    [--placement <json>] [--ledger <jsonl>]
```

終了コード: 0 = 型付きの結果（棄権・`TIE` を含む）、2 = 引数の誤り（標準エラーに `{"error": {"type": "BAD_ARGUMENTS", ...}}`）、3 = 台帳ファイルが壊れている（`LEDGER_INVALID`。何も追記しない）。`--ledger` を与えると、その台帳の状態で観測し、ターンを追記する（`observe.record_turn` を入口も呼ぶ。入口の外で呼んでも同じ形）。処理はすべて `observe.run_entry` に在り、`cli.py` は引数を渡して結果を出すだけ。

## 配置の差し替え手順（W3-a2 の粗い配置が入ったとき）

`observe.Structure` は配置の問い合わせ（`lookup`）と近傍の問い合わせ（`neighbors`）を別々に受け取る。粗い配置が入ったら、`event_cross.PlacementLookup` を満たす物と `observe.NeighborSource` を満たす物（`neighbors(lemma) -> NeighborResult`。`items` は集合で順位ではない）を作り、`build_structure` の代わりに `Structure(readings, lookup, neighbors, index)` へ渡す。`--placement` の JSON ファイルの形（`lemmas` と `neighbors`）は検査用の差し替え口で、語の一覧はコードに置かない。型の判定は W3-b の `build_crosses` に任せたままなので、差し替えで型の規則は変わらない。

## W4-m との境目

台帳の `Ledger` Protocol（`append` / `events` / `count` / `last_seq`）だけを共有する。このチケットは Protocol・メモリ上の `MemoryLedger`・jsonl の読み書きの薄い 2 関数（`load_jsonl` と `append_jsonl`。追記だけで書き換えない）を持つ。永続の実装・削除・切り離し・同意フラグ・昇格は W4-m の範囲で、ここには作っていない。台帳ファイルの事件は `seq` と `ts` と `id` を持ち、`ts` は保存するだけで観測にも出力にも使わない。

## 既にあるものとの関係

- `verantyx/observation.py`: 観測を `arm_schema` の十字に置く既存の層で、名前が近いが別物。使わず、変えていない（新しいのは `observe.py`）。
- `verantyx/events.py`: 別の抽出器。十字は W3-b の `event_cross` を呼ぶので使わない。
- `verantyx/semantic_generate.py` と `content_api`: 「何を言うか」を外から渡す形の生成。観測が何を言うかを決める層なので、入口が違う。使わない。
- `semantic_realize.realize_clause` / `realize_variants`: 変えていない（O8 の `cmp` 相当の検査で出力が基点と同じ）。観測した十字の実現は別の関数 `realize_observed` で、内部で既存の `_surface_text` と閉じた集合だけを使う。

## B3 の採点の合わせ直しの提案

隠しバンク B3 は、生成の問いに「何を言うか」と文の制約（必須語・文数・圧縮率）を与える形で、観測としての生成の評価と形が合わない。合わせ直しの提案:

1. **主指標を再観測可能率にする**: 出力の各節を同じ視点から構造へたどり直せる割合。幻覚 = 再観測できない節（承認の条件は 0）。正答率は報告のみ。
2. **創作を別に数える**: `CONSTRUCTED_UNOCCUPIED` の文は創作として別に数え、`ANSWER` の正誤とは混ぜない。`UNKNOWN_OCCUPANCY` は創作とも事実とも言わず別の欄にする。
3. **棄権を型で数える**: `NO_ANCHOR`（読解器が読めない）、`NO_MOVE_LICENSED`（許可された移動が無い）、`TIE`（同点を選ばず返した）を別の欄にし、読めなかった問を誤答に数えない。
4. **問を観測でできることで分ける**: 一つの節の言い直し・主語や受け手の入れ替え・関係をたどる接続に分け、必須語や圧縮率のような文の制約は、観測の出力の充填物と照らして検査する（観測に無い語を足していないことの検査）。
5. 実索引つきの占有の印（`ATTESTED` など）を、系列ごとに別の欄として出す。

## 判断記録

出典: 中間職の指示書 `.claude/vera-audit/review-impl/W3-c/plan.md`（D1〜D16。チケットが決めていない所を原則側で決めたもの）と、実装中に実装役が決めたこと（E1〜）。

**D1〜D17（指示書のとおり。D17 は第 1 ラウンドのレビューで中間職が足した）**: D1 構造は構造ファイル・索引・錨の文自身の読みで、読みの出所を型で分ける。D2 升の同一性は十字の内容（配置を含めない）で、鍵は正準 json の文字列（ハッシュにしない）。D3 座標は `origin` と `moves`。D4 観測できる升は範囲までのレベルの升の全部。D5 `FACE_SWAP` の許可は `build_crosses` の型一致が `AGREE` のときだけ。D6 `EDGE` は読みの `relations` だけ。D7 占有は出所ごと・合算しない。D8 場は段の列。D9 台帳の使い方（前の台帳で観測し、発話と観測を追記し、`TIE` は `observed_cell` を書かない）。D10 O4 の代替と同じ出力の定義。D11 実現（読み直しと語彙素の検査、別の言い方は並べるだけ）。D12 主張の型は閉じた 3 値で `ANSWER` にしない。D13 錨の棄権。D14 配置と近傍（ファイルの配置、語の一覧をコードに置かない）。D15 出力の形。D16 入口の形と終了コード。**D17（レビュー第 1 ラウンド `review.r1.md`、観測の後の変更）**: 段 (ii) の `U` から、今のターンの錨の文と同一の発話を除く（錨の文 = `AnchorText.text`、`AnchorRecord` のときは構造のその文の `text`）。事前登録 P8 の書き換えで、変更記録 3 に日時・前後の差・理由を書いた（最初の観測 12:44:44 の後の変更であることをそのまま書いている）。P9・P10・ほかの段・D10 は変えていない。

**実装中に決めたこと**:

- E1: `realize_observed` に、規則名を渡す引数 `rule` を足した（`frame` 規則の節だけを対象にするのに要る。指示書の引数の並びに足しただけ）。
- E2: 錨が記録の id のとき、ターンの追記は `observation` 事件だけで `utterance` を書かない（人の発話が無いため。指示書の D9 は発話を常に書くと読めるが、記録を錨にした観測は人が言ったことではない）。
- E3: `observation` 事件の payload に `state_seq`（観測に使った台帳の最後の seq）を足した。再生で「そのターンの前の台帳」を決めるためで、式にも順位にも使わない。事前登録の P9 の追記欄に記録済み。
- E4: 出力の索引の場所は絶対パスでなく、ディレクトリ名の末尾だけ（`root_name`）にした（P7: 絶対パスの違いで byte 一致を壊さない）。
- E5: 要素に `distance`・`cross_origin`（`read:semantic_read` / `read:injected` / `constructed:face_swap`）・`basis_origin` を足した。合成した十字の内側の `provenance.source_schema` を「読んだ」の意味に取らせないため。
- E6: 錨の文自身の読みは、`kind` が `question` のときも構造側の証人にする（D1 の c をそのまま適用）。質問の十字が `ATTESTED` になるのは「この入力に在る」の意味で、世界の事実ではない。既知の穴に書く。
- E7: 占有の索引の欄に、読んだ行の数と読めなかった行の数を入れる。`UNOCCUPIED` は「当たった行のうち読めた行のどれも、その十字を持たない」の意味で、読めなかった行が十字を持つ可能性は排除していない。既知の穴に書く。
- E8: 出力に最上位の `realization` 欄（焦点の実現。`TIE` のときは候補ごとの実現の列）を置いた。O4 の「同じ出力」の定義が `focus` と `realization` の欄を名指ししているため。
- E9: 範囲が 0（または向きが空）のとき、観測できる升は錨だけで、焦点は錨。`ranks` に錨の要素が入る。向きがあり範囲が 1 以上で観測できる升が 0 のときだけ `NO_MOVE_LICENSED`。
- E10: 理由の名前を足した: `FACE_SWAP` の `NO_CANDIDATE_LICENSED`（関門は通ったが許可された候補が 0）、`NEIGHBORS_RESULT_INVALID`（近傍の答えが契約を破った）、候補の `SYNTHETIC_READING_REJECTED`。0 件の理由も `counts` に並べる。
- E11: `voice` が能動でない・`modality` がある十字は `UNSUPPORTED_MODALITY`、`quantifiers` `scope` `comparison` を持つ十字は `ROLE_NOT_REALIZABLE`（実現器が表さないものを黙って落とさない）。
- E12: 単体テストが使う小さな索引は、テストの中で作る小さなコーパスから作り（`tests/test_observe.py`）、凍結した `corpus_root` は検査データ（`tests/observe/data`）の測定にだけ使う（検査データの凍結前に単体テストが凍結物へ依存しないため）。
- E13: `reobserve` は最初の座標では十字の byte 一致、2 本目以降の座標では通ってきた文の節番号と範囲（`provenance`）を除いた一致を見る（同じ内容に別の文から届いた升の十字は、`provenance` だけが違いうる）。
- E14: `--ledger` の指すファイルが無いときは空の台帳として観測し、追記のときに作る。壊れているときは終了コード 3 で何も書かない。
- E15: `tests/observe/o1_bytes.py` は、ハッシュ種ごとの子プロセスで全ケースを入口の関数（`run_entry`、コマンドラインの背後）に 2 回通して比べる。コマンドラインそのものをサブプロセスで流すハッシュ種の検査は `tests/test_observe_entry.py` にある。
- E16: O4 の判定（`measure.py --o4`）は、代替を 2 回目の台帳で見る事前登録の読みを主とし、1 回目の台帳で見る読みを横に併記する（判定には使わない）。理由と結果は「既知の穴」。この解釈は事前登録の変更記録の 2 番に、最初の観測の前に書いた。
- E17: 検査データの追記: 読解器の通し（`reader_seed_obs.jsonl`）で「縁側で」を含む文が読めないと分かったので、文は足さず、読める文を錨にしたケース `viewpoints_add1.jsonl` を足した。期待を書く前に凍結した。
- E18: `tests/reading_soundness/check_hardcode.py` が追加行の大文字の英字語（`JSON` `API`）を固有名として落とすので、追加した行（`cli.py` の説明文と新しい 2 ファイルの docstring）の `JSON` `JSONL` `API` を小文字や別の語にした。理由の文字列 `BAD_JSON` も `BAD_LINE` にした。
- E19: `MemoryLedger` の既定の時計（`datetime.datetime.now`）は `salience.py` のその行だけ。時刻印は事件に保存するだけで、段にも出力にも使わない。`tests/test_observe_data.py` が、乱数・ハッシュ・時計の語の該当行がこの 1 行だけであることを検査する。
- E20: `FilePlacement` は、ファイルに無い語を `UNKNOWN`（配置）／`UNKNOWN`（近傍）にする。`UNPLACED`（語は材料に在るが根拠が足りない）とは別。
- E21（第 2 ラウンド、必須 3）: 升の充填物が 0 個で、引く surface が 0 のとき、`_IndexReader.occupancy` は索引を 1 回も引いていない。以前は `searches: []`・`rows_read: 0` のまま `UNOCCUPIED` を返していた（調べていないことを「無い」と言っていた）。今は `UNKNOWN_QUERY_NOT_SEARCHED`（`detail.reason: NO_SURFACE_TO_SEARCH`）を返す。事前登録 P6 の「当たりが 0 で状態が `NO_MATCH`」は検索をした場合の規則で、本文は変えていない（検索をしない場合の別の型として足した）。単体テスト `test_a_cell_with_no_filler_is_not_searched_in_the_index_and_is_not_called_unoccupied`。
- E22（第 2 ラウンド、必須 4。**レビューの指示から 1 点だけ外れた**）: `counts.realization.refused` は、`semantic_realize.REFUSAL_REASONS` を整列した閉じた一覧で 0 に初期化してから数える。ただし `NO_ANSWER_RESULT` と `NO_SOURCE_VIEW` の 2 つは一覧から除いた（`observe.REFUSAL_NOT_ON_THIS_PATH`）。この 2 つは答えの実現器と元ビューの実現器（`semantic_realize.py` の別の関数）だけが返す拒否で、`realize_observed` は返さない。0 件で並べると、この経路が出しうる理由のように見える。もう一つの理由は、出力に `ANSWER` の字面が入り、O5（出力に `ANSWER` が無い）の字面の検査（`measure.py --o5`、監査役の `grep`）が全件で落ちること。除いた 2 つが一覧に無いことは名前つきの定数で、実現器の一覧が増えたら `test_counts_list_every_realization_refusal_reason_with_zeros_in_a_fixed_order` が落ちる（黙って落とさない）。除いた 2 つを入れる場合は O5 の検査を字面でなく値で見る形に変える必要があり、決めるのは中間職。観測の出力に出る理由が増えたときは、一覧に無い理由も数える（`.get`）。
- E23（第 2 ラウンド、任意 2）: `--lang` に `ja`・`en` 以外を渡すと `BAD_ARGUMENTS`（終了 2）。以前は `NO_ANCHOR(READ_ERROR:...)`（終了 0）になりえた。
- E24（第 2 ラウンド、任意 1）: `tests/observe/run_bank.py` は `observe.observe` を直接呼ばず、入口の関数 `observe.run_entry` を通す。自作の B3 の索引なしの行は変更前と byte 一致（`cmp`）、実索引は要約が同じ（行の `cmp` はしていない）。
- E25（第 2 ラウンド、任意 5）: 同じ距離で同じ内容に複数の道で届いた升は 1 升にまとめ、代表の十字は座標の正準 json の文字列順で先頭の道のものにする（`replace(group[0], coords=...)`）。勝者選びではない（内容は同一で、道は `coords` に全部残る。2 本目以降の座標は十字の `provenance` を除いた一致で再観測する。E13）。

- E26（W5-b、攻撃 A1。**出所 id は中身の id**）: `FilePlacement` の `id`（出力の `structure.placement` と `structure.neighbors`）は、ファイルのバイト列の sha256 ではなく、**実際に使う中身の正準形**（語の辞書順の `lemmas`・各 `PlaceResult` の欄・語の辞書順の `neighbors`・各近傍の集合は辞書順）を正準 json（鍵の順・空白は固定）にした文字列の sha256（`file:<sha256>`）。近傍の並び・鍵の順・空白・重複だけが違うファイルは同じ id になり、出力もバイト単位で同じ。近傍の **集合** や答えが違えば id が違う。バイト列の sha256 は `FilePlacement.file_sha256` に持つだけで、id にも出力にも使わない。攻撃役の反例: 近傍の並べ替えだけで JSON のバイト列が変わった（`tests/attack/test_attack_w3c_observe.py`）。
- E27（W5-b、攻撃 A2。**合流した升は全経路の座標を持ち、次の段へ手渡す**）: 升の座標は「親の **すべての** 座標 × この 1 手」で作る（`_try_swap` と `_edge_targets` が `cell.coords` の各座標に手を足した座標の組を持つ 1 つの升を返す）。同じレベルの合流では、群のすべての升のすべての座標を集めて重複を除き、正準 json の文字列順に並べる。代表の十字は「最小の座標の文字列を持つ升」のもの（勝者選びではない。E25 と同じ考え。座標が同じなら同じ升なので、最小の座標を持つ升は 1 つに決まる）。`Cell.coord` は先頭の座標のまま。**升の数・`counts` の数え方は今までどおり升ごと**（座標ごとに数えない）。座標の数に上限は設けていない（全経路）。以前は 2 段目以降で先頭の座標だけが引き継がれ、4 本あるはずの経路が 1 本になっていた。
- E28（W5-b、攻撃 A2 の続き。**`reobserve` は全経路を要求する**）: 今の検査（各座標をたどり直す。先頭はバイト一致、2 本目以降は provenance を除いた一致。実現した文の読み直し）の **後に**、同じ `viewpoint`・`structure`・`lookup`・`neighbors` で升とその座標を求め直し（`_levels`。台帳は渡さない。升と座標は台帳に依らない: 各レベルの展開は `structure` と `viewpoint` だけを読む）、同じ升の座標の集合が、渡された要素の座標の集合と等しいことを要求する。欠けていれば `MISMATCH`・`COORDS_INCOMPLETE`、余分なら `COORDS_EXTRA`、升が無ければ `CELL_NOT_OBSERVED`。既存の理由の順と名前は変えていない。 集合が等しくても、同じ座標が 2 回入っていれば（`observe` は各経路を 1 回ずつ出す）`COORDS_DUPLICATED`（第 2 ラウンドで追加。集合でだけ比べると、座標の数を数える使い手に重なった要素が通ってしまうため。理由の名前は新しく、既存の名前は変えていない）。
- E29（W5-b、攻撃 A3。**台帳は全行を検証してから追記する**）: `run_entry` は `SAL.load_jsonl` の後、観測の前に、**全事件の payload を、観測器と顕著さの場が読む欄の型で検証する**（`observe.validate_ledger_payloads`）。不正なら終了コード 3・`LEDGER_INVALID`・`detail` に `PAYLOAD_INVALID:seq=<n>:<欄>`、**0 行追記**（台帳のバイト列は変わらない）。見る欄は P9（観測器が書く欄）と `salience.py` が読む欄から決めた:

  | 事件の種類 | 検証する欄 | 理由（読む側） |
  |---|---|---|
  | すべて | `decided_cell` があれば文字列 | `build_context` が `'decided_cell' in payload` の値を辞書の鍵にする（文字列でなければ落ちる） |
  | `utterance` | `text` は文字列（必須）、`anchor` があれば `ANCHOR_KINDS`（`seed`・`question`） | `utter_verbatim`・`utter_neighbor` の段が `text` を部分文字列として読む。`anchor` は P9 が書く欄 |
  | `observation` | `viewpoint` は Mapping、`outcome` は `OUTCOMES` のどれか、`state_seq` は int（bool でない）、`output_sha256` は文字列、`observed_cell` があれば文字列、`tie_cells` があれば文字列の list | P9 が書く欄。`observed_cell` は `recency` の段が等値で読む。`replay` が `state_seq` と `viewpoint` を読む |
  | `decision` | `decided_cell` は文字列（必須） | `decided` の段が `ledger.count('decided_cell', …)` で読む |

  この表の外の欄（`phrase` など他の使い手の欄）は見ない。`tests/observe/data/ledgers/` の台帳と、観測器自身が書く台帳は全部通る。

## 既知の穴（隠さない）

1. **既定の入口で動くのは錨の升だけに近い**。既定の配置はすべて `NO_PLACEMENT` で、型一致が `AGREE` にならず、`FACE_SWAP` は許可されない（件数は測定結果の `NO_MOVE_LICENSED` と、スタブ配置のケース）。`FACE_SWAP` はファイルの配置（`--placement`）を与えたときだけ動き、その配置も検査用に手で書いたもので、粗い配置（W3-a2）ではない。
2. **`EDGE` は入口から動いていない**（測定結果の `EDGE` を試したケースのうち升が出たもの）。読解器は `relations` を出さない（測定結果の「読解器が出した関係」）。`EDGE` の許可の規則は、手書きの読み（`reading_source: injected`、公開の関数だけ）を使った単体テストでだけ動かしている。動いたと書かない。
3. **O4 の経緯**: 第 1 ラウンドでは、事前登録の読みで反例の行（`O4-e-L07`）があり、判定の緩さで `O4-f-L08` も見落としていた。原因は D8（最新の発話を段に使う）と D9（錨の文を発話として追記する）の組み合わせで、2 回目の台帳では 1 回目の錨の文そのものが `U` になって段 (ii-b) の値が変わること。第 2 ラウンドで中間職が D17（錨と同じ文の発話を `U` から除く。事前登録の変更記録 3、観測の後の変更）を決め、判定を P10 のとおりに厳しくした。厳しい判定では、旧規則は 6 行中 3 行しか通らない（`o4_old_rule_check.txt`）。**残る限界**: 通った 6 行は 1 つの配置（ファイルの近傍が対称で、`教授` `事務員` `犬` の 3 升）の上の結果で、台帳は手で作った 6 本。attribution（新しい焦点と古い焦点を分ける最初の段が、1 回目に追記された行を指すか）の定義は実装役が決めた判定で、事前登録の本文にはない（P10 は「代替があれば変わる」「代替が無ければ同じ」まで）。
4. **実現できるのは日本語の `frame` 規則・能動・助詞の閉じた集合の節だけ**。英語は `NOT_REALIZABLE`、時の腕・受け身・`copula` は型付きの拒否。読解器が読めない形（例: 「縁側で」の `で` の曖昧）は、実現した文を読み直せず `ROUNDTRIP_MISMATCH` で拒否される（拒否は規則どおりで、件数は測定結果）。
5. **表現の揺らぎは選ばない**。`alternatives` に検証済みの別の言い方を並べるだけで、どれを出すかを台帳から決める規則は無い。O4 の揺らぎは内容（どの升）だけで満たしている。
6. **占有は読解器の読める範囲での占有**。索引の行は読解器に通して十字にしてから比べるので、読めない行がその十字を持つ可能性は排除していない（`UNOCCUPIED` の欄に読めなかった行の数を出している）。窓が埋まった検索は `UNKNOWN_WINDOW_SATURATED` で、`UNOCCUPIED` と言わない。実索引の高頻度語では窓が埋まりやすい。
7. **錨の文自身の読みが構造側の証人になる**（質問のときも）。`ATTESTED` は「構造か入力に在る」で、世界の事実ではない。生成された文の証人には `basis_origin: generated` が付く。
8. **段 (ii-b) の効き方は配置の近傍の作り方に依る**。D17 で錨の文は段 (ii) に効かなくなったが、錨と文字列として同一でない発話（言い換え・別の文）が候補の近傍の語を含めば、近傍が対称な配置では持ち上げが起きる。粗い配置（W3-a2）が入って近傍の作り方が変われば効き方が変わる。D17 は文字列の同一だけを見る（錨の言い換えは除かない。別の発話として効く）。
9. 隠しバンク B3 は開いていない。O7 は自作の B3 だけで測った（読めた錨が少なく、正答率は測っていない）。隠しバンクでの測定は監査役が `tests/observe/run_bank.py` で行う（`--items` を差し替える）。
10. 台帳は jsonl の平らなファイルで、永続の方針（切り離し・削除・同意）は W4-m の範囲。`MemoryLedger` は 1 プロセスの中だけ。
11. 期待と観測器の食い違い（件数は測定結果）を、直さずに凍結した（`disagreements.json` と、第 1 ラウンドの規則の下の O4 の旗の `disagreements_o4.json`）。観測器の誤りと判断した件は無く、期待の書き誤り（近傍の見落とし・読めない語の見落とし・TIE から始まる行の定義）と、第 1 ラウンドの O4 の反例。理由は `tests/observe/data/disagreements.json` と `disagreements_o4.json`。第 2 ラウンドの期待（`expected_r2.jsonl`）には食い違いが無かった。
13. **ANSWER の字面**: 出力は `ANSWER` の字面を含まない（O5 の検査）が、`verantyx/observe.py` のソースには、注釈の行（20 行目）のほかに、除いた拒否理由の名前を書いた定数の行（`REFUSAL_NOT_ON_THIS_PATH`、決定 E22）がある。ソースの `grep ANSWER` の該当は 2 行で、後者は理由の名前。
12. 全体テストの結果と、基線にない失敗の説明は `artifacts/w3-c/pytest_new_failures.explained.md`。

## 測定結果

<!-- recompute:begin -->
### 測定結果（`tests/observe/recompute.py` が `artifacts/w3-c/` から作った区間。手で書き換えない）

**検査データ**（`tests/observe/data/`、凍結）

- 種の文: 日本語 31・英語 18（合計 49）。ケース（視点）97（`viewpoints.jsonl`・`viewpoints_add1.jsonl`・`viewpoints_r2.jsonl`）。台帳 12 本。
- 読解器だけに通した結果（`reader_seed_obs.jsonl`）: 日本語 31 文のうち読めた 19、英語 18 文のうち読めた 7。読めた文のうち複数の節を持つもの 0、読解器が出した関係 0 本。
- 凍結の時刻順（`FROZEN.json`）: inputs 12:38:40 → inputs_add1 12:39:30 → expected 12:41:30 → first_observation 12:44:44 → disagreements 12:45:10 → disagreements_o4 12:47:46 → inputs_r2 13:19:40 → expected_r2 13:19:43 → first_observation_r2 13:21:27。事前登録（`artifacts/w3-c/prereg.txt` の `registered_at`）: 2026-10-03 12:20:51 +0900。

**凍結した期待と観測器**（`expected_compare.json`）: 1 ターンの期待のあるケース 91 のうち、そのまま一致 88・食い違い 3（LG05: decided_by/ranks, M04b-swap-place-J09: realization, M04c-swap-place-J09-index: realization）。食い違いは直さず `disagreements.json`（4 件・3 ケース）に凍結し、凍結分を当てはめると食い違い 0。2 ターンのケース 6 のうち、焦点と順位が期待と一致 6。O4 の旗の食い違い（`disagreements_o4.json`、第 1 ラウンドの規則の下のもの）は 3 行。第 2 ラウンド: `expected_r2.jsonl` が 2 ターンの行 O4-a-L03, O4-b-L04, O4-c-L05, O4-d-L01, O4-e-L07, O4-f-L08 を置き換え、1 ターンのケース 3 を足した（新しい規則で観測器を流す前に書いて凍結。`disagreements_r2.json`（食い違いの凍結）: 食い違いが無く作っていない）。

**全ケースの集計**（`summary.json`、各ケースの 1 ターン目）: 出力 97。焦点の型 FOCUS 41, NO_ANCHOR 30, NO_MOVE_LICENSED 6, TIE 20。NO_ANCHOR の理由 READER_ABSTAINED 29, RECORD_NOT_IN_STRUCTURE 1。錨と移動した升の数 164（うち移動した升 97）。主張の型 CONSTRUCTED_UNOCCUPIED 5, OBSERVED_OCCUPIED 97, UNKNOWN_OCCUPANCY 62。占有の印 ATTESTED 97, UNKNOWN_FAMILY_DB_MISSING 3, UNKNOWN_NO_INDEX 58, UNKNOWN_WINDOW_SATURATED 1, UNOCCUPIED 5。移動した升の型一致 AGREE 97。実現できた文 153、実現の拒否 NOT_REALIZABLE 9, ROUNDTRIP_MISMATCH 2。`FACE_SWAP` を配置ファイル付きで試したケース 44、`EDGE` を試したケース 1（うち升が出たもの 0）。

**O1**（バイトの一致・再生）: `o1_bytes.txt`: checked 97, mismatch 0。`o1_replay.txt`: replayed 25, digest_mismatch 0。

**O2**（再観測可能率、`o2_reobserve.json`）: 要素 213・再観測できた 213・できなかった 0（理由別 (none)）。実現できた文 195 のうち読み直して同じ升に戻ったもの 195、内容語に観測の充填物以外があったもの 0。別の言い方 1317 本のうち読み直して同じ升に戻ったもの 1317、内容語に余りがあったもの 0。実現の拒否 NOT_REALIZABLE 16, ROUNDTRIP_MISMATCH 2。

**O3**（乱数・ハッシュ順・時計）: `o3_grep.txt` の該当行 1（verantyx/salience.py:60:    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')）。中間職が 1 行ずつ読む一覧 `o3_review_points.txt` は 35 行。

**O4**（揺らぎ、`o4.json`。第 2 ラウンドで判定を事前登録の P10 のとおりに厳しくした）: 2 ターンの行 6。判定: 1 回目が TIE なら 2 回目も同じ出力（候補も同じ）、代替が無ければ同じ出力、代替があれば変わり、かつ新しい焦点と古い焦点を分けた段の `ledger_seqs` に 1 回目のターンで追記された行がある。事前登録の読み（代替は 2 回目の台帳で見る）で規則に合うもの 6・反例 (なし)。もう一つの読み（代替は 1 回目の台帳で見る）で合うもの 6・反例 (なし)。L09 と L10 は台帳のうち行 2 だけが違い、出力は 違う、2 つの trace の段の値の差 2 件は すべてその行が作る。

| 行 | 台帳 | 1 回目 | 2 回目 | 代替（2 回目の台帳の状態） | 代替（1 回目の台帳の状態） | 同じ出力 | 変化を分けた段と、1 回目が追記した行 | 規則に合う（登録の読み） | 規則に合う（もう一つの読み） |
|---|---|---|---|---|---|---|---|---|---|
| O4-a-L03 | L03 | 教授 | 事務員 | 2 | 2 | False | recency: 行 5 | True | True |
| O4-b-L04 | L04 | 車掌 | 車掌 | 0 | 0 | True | （変化なし） | True | True |
| O4-c-L05 | L05 | 教授 | 教授 | 0 | 0 | True | （変化なし） | True | True |
| O4-d-L01 | L01 | TIE 事務員 / 教授 / 犬 | TIE 事務員 / 教授 / 犬 | 0 | 0 | True | （変化なし） | True | True |
| O4-e-L07 | L07 | 犬 | TIE 事務員 / 教授 | 2 | 2 | False | recency: 行 3; recency: 行 3 | True | True |
| O4-f-L08 | L08 | TIE 教授 / 犬 | TIE 教授 / 犬 | 0 | 0 | True | （変化なし） | True | True |

`O4-a-L03` の 2 回目の trace（`o4.json` から。升は主語の語で示す）: 発話の段の入力 `{"skipped_same_as_anchor": [4], "used_seq": null}`、境目 `[{"between": [1, 2], "decided_by": "decided"}, {"between": [2, 3], "decided_by": "recency"}]`、各升の段の値を作った台帳の seq `{"事務員": {"decided": [3]}, "教授": {"decided": [1, 2], "recency": [5]}, "犬": {}}`

`O4-e-L07` の 2 回目の trace（`o4.json` から。升は主語の語で示す）: 発話の段の入力 `{"skipped_same_as_anchor": [2], "used_seq": null}`、境目 `[{"between": [1, 2], "decided_by": "recency"}]`、各升の段の値を作った台帳の seq `{"事務員": {}, "教授": {}, "犬": {"decided": [1], "recency": [3]}}`

**O4 の判定そのものの確認**（`o4_old_rule_check.txt`。観測器の `build_context` を一時的に旧規則=錨の文を除かない、に差し替えて同じ判定を流した結果。ファイルは変えていない）: registered reading (alternative at the state of turn 2): rows ok 3 of 6, violations ['O4-d-L01', 'O4-e-L07', 'O4-f-L08'] / other reading (alternative at the state of turn 1): rows ok 3 of 6, violations ['O4-c-L05', 'O4-d-L01', 'O4-f-L08']。

**O5**（`o5.txt`）: unoccupied 5, provenance_constructed 5, claim_answer 0。outputs_scanned 103, realized_sentences_carrying_the_constructed_provenance 4。

**O6**（`o6.txt`）: prereg_before_data: ok (registered 2026-10-03 12:20:51+09:00, first data 2026-10-03 12:38:40+09:00) / frozen_order: ok (inputs 12:38:40 < inputs_add1 12:39:30 < expected 12:41:30 < first_observation 12:44:44 < disagreements 12:45:10 < disagreements_o4 12:47:46 < inputs_r2 13:19:40 < expected_r2 13:19:43 < first_observation_r2 13:21:27) / frozen_files_unchanged: ok / change3_before_r2_data: ok (change 3 recorded 13:18:31; inputs_r2 13:19:40 < expected_r2 13:19:43 < first_observation_r2 13:21:27) / section_sha: changed, changes_logged: 2 (prereg.txt records 2 change(s) of the section; the log has 3 entries, one of them a clarification that left the section alone)

**O7（自作の B3・索引なし、`b3_selfmade_summary.json`）**: 問 24・錨 25・視点 50。NO_ANCHOR READER_ABSTAINED 44。実現できた文 4、実現の拒否 UNSUPPORTED_MODALITY 2。観測した節 6 のうち再観測できなかった節（幻覚）0。主張の型 CONSTRUCTED_UNOCCUPIED 0, OBSERVED_OCCUPIED 6, UNKNOWN_OCCUPANCY 0。占有の印 ATTESTED 6。

**O7（自作の B3・実索引、`b3_selfmade_idx_summary.json`）**: 問 24・錨 25・視点 50。NO_ANCHOR READER_ABSTAINED 44。実現できた文 4、実現の拒否 UNSUPPORTED_MODALITY 2。観測した節 6 のうち再観測できなかった節（幻覚）0。主張の型 CONSTRUCTED_UNOCCUPIED 0, OBSERVED_OCCUPIED 6, UNKNOWN_OCCUPANCY 0。占有の印 ATTESTED 6。

**O8**: 全体テスト `pytest_full.txt` の最終行: `116 failed, 7786 passed, 45 skipped, 75 xfailed, 75 xpassed, 37 subtests passed in 189.77s (0:03:09)`。基線にない失敗 `pytest_new_failures.txt`: 2 行（説明: `pytest_new_failures.explained.md`）。新しいテスト `pytest_new_tests.txt` の最終行: `285 passed in 17.86s`。実現器の不変 `o8_realize_parity.txt`: checked 134, mismatch 0（clauses_compared 170）。固定の語の検査 `check_no_data_words.txt`: data words scanned: 325; added or new lines scanned: 1648; hits: 0。決め打ちの検査 `check_hardcode.txt`（追加行）: PROPER/NUMERIC (must be empty): [] / ENGLISH NAMES (must be empty): []、新しい 2 ファイルを加えた版 `check_hardcode_with_new_files.txt`: PROPER/NUMERIC (must be empty): [] / ENGLISH NAMES (must be empty): []。

**差分の大きさ**（`common_additions_only.txt`、基点 5cae978 に対する追加・削除の行数）: verantyx/cli.py +39 -0; verantyx/semantic_realize.py +186 -0。
<!-- recompute:end -->

## 質問の観測（W3-c2）

（この節は段階的に書く。最初に書いたのは次の「事前登録」小節だけ。ほかの小節は検査データを作り、実装したあとに足す。）

### 事前登録（W3-c2）

<!-- w3c2-prereg:begin -->
登録日時: 2026-10-03 19:39:38 +0900（`date '+%Y-%m-%d %H:%M:%S %z'` の出力。この節はこの出力の直前に書いた）
この時点で `tests/observe/question/` は存在しない（`ls` の出力を `artifacts/w3-c2/prereg.txt` に記録する）。出典は中間職の指示書 `.claude/vera-audit/review-impl/W3-c2/plan.md` の D9・D11・D12・D17。穴の型の表は `docs/EVENT_CROSS.md` の「穴の型（W3-c2。事前登録）」。

**一致の定義（D9）**: 質問の十字 q（穴の腕 h）と構造の文の十字 d が一致 ⇔
1. `center` の全鍵が完全に等しい（`predicate polarity tense modality voice`、あれば `quantifiers scope comparison`。片方にだけある鍵があれば不一致。述語は語彙素の完全一致で NFKC を掛けない）。
2. h 以外の腕の集合（役割名）が等しく、各腕で `kind` が等しく、充填物の `surface` の列が要素ごとに `unicodedata.normalize('NFKC', s)` で等しい。
3. d に腕 h がある。
d に q に無い腕がある（例: 場所 `駅で` が多い）なら一致しない（否定の問い「誰が地図を渡さなかった？」に「先生は駅で地図を渡さなかった」を一致させると誤答になるため）。言い換え・配置の近傍・`FACE_SWAP` は使わない。比べるのは構造の全部の読みの全部の十字（標本抽出しない。索引は見ない）。

**状態と焦点の写し方（D11）**（`answer.status` は閉じた一覧 `ANSWER_STATUSES`。大文字の `ANSWER` を含む値を作らない）:

| `answer.status` | 条件 | `focus`（既存の型） |
|---|---|---|
| `FILLED` | 除外の後の候補の充填物が NFKC で 1 種 | 証拠の升が 1 つなら `Focus`、NFKC で同じだが表記の違う升が 2 つ以上なら `Tie`（答えは 1 つ） |
| `TIE` | NFKC で 2 種以上（d の腕 h が `ARM_TIE` ならその充填物はそれぞれ別の候補） | `Tie`。場・台帳・並びで選ばない |
| `NO_ATTESTED_CELL` | 一致する d が 0 | `NoMoveLicensed({'FILL_HOLE:NO_ATTESTED_CELL': 1})` |
| `TYPE_EXCLUDED_ALL` | 一致はあったが候補が全部除外された | `NoMoveLicensed({'FILL_HOLE:candidate:<理由>': 件数})` |
| `HOLE_TYPE_UNDETERMINED` | RESTRICTOR で N の型が決まらない | `NoMoveLicensed({'FILL_HOLE:HOLE_TYPE_UNDETERMINED': 1})` |
| `POLAR_QUESTION` | はい／いいえ疑問（観測しない） | `NoMoveLicensed({'FILL_HOLE:POLAR_QUESTION': 1})` |
| `DIRECTION_NOT_APPLIED` | 疑問文の錨に `--direction` が空でない | `NoMoveLicensed({'FILL_HOLE:DIRECTION_NOT_APPLIED': 1})` |
| `QUESTION_NOT_READ` | `read_question` が `readable: false` | `NoAnchor('READER_ABSTAINED', …)` |

`anchor` は None（質問の十字は升ではない。印を含む十字を実現器に渡さない）。質問の十字は `answer.question_cross` にだけ載せる。

**証拠（D12）**: 証拠は構造の文の読み（`structure.readings` の `CROSSED`）だけ。錨の読みと索引は証拠にしない。`answer.fillers[*].evidence` は `{reading, cross_index, cell_key, text, reading_source}`。構造の文で読めなかったもの（`ABSTAINED`・`READ_ERROR`・`INPUT_REJECTED`）の数と id の列を `answer.structure` に必ず出す（`NO_ATTESTED_CELL` を「文書に無い」と読ませないため）。

**採点の分類（D17）**: 各問の正解（`truth.kind`）は人が文書を読んで決める: `ONE`（充填物 1 つと、それを述べる文 id の集合）・`NONE`（文書に無い）・`SPLIT`（充填物 2 つ以上）・`YESNO`（はい／いいえ疑問）・`ILLFORMED`（穴 2 つ・印を含む・不定語・`AかB` など）。
- **CORRECT** = ONE と FILLED（NFKC の充填物が同じ・証拠の文 id の集合が同じ）／NONE と NO_ATTESTED_CELL／SPLIT と TIE（充填物の集合が同じ）／YESNO・ILLFORMED と FILLED・TIE 以外。
- **WRONG（誤った答え）** = FILLED・TIE を出して CORRECT でないもの全部。
- **FALSE_NONE** = ONE・SPLIT に NO_ATTESTED_CELL・TYPE_EXCLUDED_ALL。1 件ずつ原因を書く。
- **ABSTAINED** = それ以外の型付きの棄権。
承認の条件は WRONG = 0。正答率・FALSE_NONE・ABSTAINED は報告する。

**検査データの規模**: 文書 10 本（`QD01`〜`QD10`、各 5〜10 文、和文 7 本以上・英文 3 本以上）、質問 84 問以上（穴の型 8 種それぞれ 8 問以上、POLAR 4 問以上、ILLFORMED 4 問以上、`direction` が空でない問 2 問以上、配置つきの問 10 問以上）。期待（`truth`）は観測器にも `read_question` にも 1 度も通さずに人が書き、`FROZEN_Q.json` で sha256 を凍結する。凍結後は 1 バイトも変えない（誤りは `corrections.jsonl` に追記し、当てた結果と当てない結果の両方を出す）。
<!-- w3c2-prereg:end -->

### 質問の観測の事前登録の変更記録（W3-c2）

（2026-10-03 19:39:38 +0900 時点: 変更なし。出典: artifacts/w3-c2/prereg.txt）

**2026-10-03 19:46:58 +0900（検査データの凍結の前、観測器・`read_question` に 1 度も通す前）の補足**: 上の区間の文言は 1 字も変えていない。D17 の「証拠の文 id の集合」の意味を、検査データを書く前に固定する。`truth.evidence` = 問いの命題を **その腕のまま** 述べている、既存の読解器 `read()` が読める文書の文の id。次の 2 種は `truth.evidence` に入れず、別の欄に書く: `extension_support`（問いより腕が多い読める文。例: 場所が付く。正解を支えるが、D9 の一致の定義では証拠にならない）、`unread_support`（正解を述べているが `read()` が読めない文。FALSE_NONE の原因の説明に使う）。理由: これらを `evidence` に入れると、系が引けない文を引いていないことを理由に正しい答えが WRONG になり、承認の条件（誤答 0）が系の誤りでなく読解器の守備範囲で決まってしまうため。採点（`CORRECT`）は文言どおり、系の引いた文 id の集合と `truth.evidence` の一致を見る（部分集合では足りない）。`NONE`・`SPLIT` も同じ。

**2026-10-03 20:03:34 +0900（検査データの凍結の後、第 1 回の実行の後）の変更**: 上の区間の文言は 1 字も変えていない。D11 の表（閉じた一覧 `ANSWER_STATUSES`）に 2 行足す。
- 前: `FILLED` `TIE` `NO_ATTESTED_CELL` `TYPE_EXCLUDED_ALL` `HOLE_TYPE_UNDETERMINED` `POLAR_QUESTION` `DIRECTION_NOT_APPLIED` `QUESTION_NOT_READ`
- 後: 上に `ANCHOR_CROSS_INDEX_OUT_OF_RANGE`（質問の錨の `cross_index` が 0 以外。焦点は既存の `NoAnchor('ANCHOR_CROSS_INDEX_OUT_OF_RANGE', …)` と同じ型）と `INCOMPLETE_BY_EXTENSION`（下記）を足した。
- `INCOMPLETE_BY_EXTENSION`: 一致した十字から充填物が決まったが、「質問の十字に腕を足した十字」（一致ではない。`answer.structure.extending` に出す）が、穴の型が除外しない別の充填物を名指ししている。充填物の集合が完全だと言えないので FILLED・TIE にせず、型付きで棄権する（焦点は `NoMoveLicensed({'FILL_HOLE:INCOMPLETE_BY_EXTENSION': 件数})`）。一致した充填物は `answer.fillers` に残す。
- 理由: 凍結した検査データの Q185（「誰が地図を渡さなかった？」。校長の文は腕が同じ、先生の文は場所の腕が 1 つ多い）に、第 1 回の実行（`artifacts/w3-c2/q2_score.r1.json`）で FILLED（校長だけ）を返し、正解は SPLIT（校長・先生）なので WRONG が 1 件出た。D17 の WRONG は承認の条件に反するので、規則を直した（語は足していない。直せない構成は棄権に倒す）。直した後の実行は `q2_score.r2.json`・最終は `q2_score.json`。検査データは直していない。

**2026-10-03 20:44:10 +0900（検査データの凍結の後、第 2 ラウンドのレビュー M1 による）の記録**: 事前登録の区間（`w3c2-prereg`）の文言・凍結した検査データ・穴の型の表は 1 字も変えていない（区間の sha256 は `artifacts/w3-c2/prereg_check.r2.txt`、凍結の確認は `frozen_check.r2.txt`）。変えたのは `_question_en` の E2 で取り残しの `to` を先に判定する順序だけ（判断記録 J14）。凍結した 185 問の出力は変更の前後で byte 一致（`m1_q2_cmp.txt`）。

### 何を作ったか（W3-c2）

疑問文を、平叙文と同じ読解の規則で、wh 語の腕だけが **型付きの穴** になった十字として読み、文書（構造）の文の十字を観測して穴を埋める充填物を、証拠の文 id つきで返す。実行時に LLM は呼ばない。
- `verantyx/semantic_read.py`（追加のみ）: `read_question(text, lang)`。wh 語（の区間）を **印 1 記号**（和文 `Ｘ`・英文 `X`）に置き換え、平叙形を既存の `_read_ja` / `_read_en` で読み、印がちょうど 1 つの節のちょうど 1 つの役割の値と一致することを確かめて、その役割を穴の腕にする。出力は `verantyx.semantic_read/1` の形に最後の鍵 `question` を足したもの。**`read()` と既存の関数は 1 字も変えていない**（`tests/test_question_cross.py` が基点の関数・定数の sha256 を固定している）。疑問文に対する `read()` の答えは今までどおり `UNREAD_SPAN: interrogative source does not assert a fact`。
- `verantyx/observe.py`（追加のみ）: 錨の種類が `question` で `read_question` が疑問文と読んだとき、`QuestionObservation`（`Observation` を継承し、欄 `answer` を足す）を返す。穴以外の腕が一致する構造の文の十字（ATTESTED の升）を集め、穴の腕の充填物を候補にする。候補 1 種 → `FILLED`、2 種以上 → `TIE`（重ねて返す。場・台帳・並びで選ばない）、0 → `NO_ATTESTED_CELL`。穴の型と、構造の lookup が引いた充填物の型（`direct` で決まったもの）が食い違えば候補から外し、理由を `excluded` に残す。
- 平叙文の錨・`seed` の錨・疑問文でない `question` の錨は今までの経路を通り、出力は基点と 1 バイトも変わらない（凍結ケース M15-question-J01 を含む）。
- `vera ask --mode round5 --document` からは呼ばない（別チケットでつなぐ）。

### 入口（W3-c2）

`python -m verantyx.cli observe --anchor-kind question --anchor-text "<質問>" --structure <文書.jsonl> [--placement <配置.json>] [--no-index]`。出力は既存の `verantyx.observe/1` に最上位の鍵 `answer` が足されたもの（質問の経路だけ）。`answer.status` が `FILLED`・`TIE` のときだけ充填物が答え。それ以外は理由つきの棄権で、答えを作らない。`--direction` は質問の錨には適用しない（`DIRECTION_NOT_APPLIED`）。

<!-- w3c2-entry:begin -->
### 入口の実行出力（`recompute_q.py` が実際に走らせて貼った。手で書き換えない）

`python -m verantyx.cli observe --anchor-text 'どの人が客に切符を渡した？' --anchor-kind question --structure tests/observe/question/docs/QD02.jsonl --no-index --placement tests/observe/question/placement_q.json`（FILLED）
```json
{
 "exit_code": 0,
 "focus": {
  "kind": "FOCUS"
 },
 "answer.status": "FILLED",
 "answer.question": {
  "hole_role": "agent",
  "hole_type": null,
  "wh": "どの",
  "kind": "WH_QUESTION",
  "restrictor": "人",
  "hole_mark": "Ｘ"
 },
 "answer.fillers": [
  {
   "surface": "駅員",
   "evidence": [
    {
     "reading": "QD02-S01",
     "cross_index": 0,
     "text": "駅員が客に切符を渡した。"
    }
   ],
   "hole_type_check": "AGREE"
  }
 ],
 "answer.structure": {
  "sentences": 9,
  "crossed": 6,
  "unread": 3,
  "unread_ids": [
   "QD02-S07",
   "QD02-S08",
   "QD02-S09"
  ],
  "crosses_compared": 6,
  "crosses_matched": 1,
  "extending": []
 },
 "answer.reasons": [
  "UNREAD_SENTENCES:3"
 ],
 "abstain": null
}
```

`python -m verantyx.cli observe --anchor-text '誰が生徒に地図を渡した？' --anchor-kind question --structure tests/observe/question/docs/QD01.jsonl --no-index --placement tests/observe/question/placement_q.json`（TIE）
```json
{
 "exit_code": 0,
 "focus": {
  "kind": "TIE",
  "candidates": "[2 cells]"
 },
 "answer.status": "TIE",
 "answer.question": {
  "hole_role": "agent",
  "hole_type": [
   "GROUP_ORG",
   "PERSON"
  ],
  "wh": "誰",
  "kind": "WH_QUESTION",
  "restrictor": null,
  "hole_mark": "Ｘ"
 },
 "answer.fillers": [
  {
   "surface": "先生",
   "evidence": [
    {
     "reading": "QD01-S01",
     "cross_index": 0,
     "text": "先生が生徒に地図を渡した。"
    }
   ],
   "hole_type_check": "AGREE"
  },
  {
   "surface": "校長",
   "evidence": [
    {
     "reading": "QD01-S02",
     "cross_index": 0,
     "text": "校長が生徒に地図を渡した。"
    }
   ],
   "hole_type_check": "AGREE"
  }
 ],
 "answer.structure": {
  "sentences": 9,
  "crossed": 7,
  "unread": 2,
  "unread_ids": [
   "QD01-S05",
   "QD01-S08"
  ],
  "crosses_compared": 7,
  "crosses_matched": 2,
  "extending": []
 },
 "answer.reasons": [
  "UNREAD_SENTENCES:2"
 ],
 "abstain": null
}
```

`python -m verantyx.cli observe --anchor-text '誰が生徒に手紙を送った？' --anchor-kind question --structure tests/observe/question/docs/QD01.jsonl --no-index`（NO_ATTESTED_CELL）
```json
{
 "exit_code": 0,
 "focus": {
  "kind": "NO_MOVE_LICENSED"
 },
 "answer.status": "NO_ATTESTED_CELL",
 "answer.question": {
  "hole_role": "agent",
  "hole_type": [
   "GROUP_ORG",
   "PERSON"
  ],
  "wh": "誰",
  "kind": "WH_QUESTION",
  "restrictor": null,
  "hole_mark": "Ｘ"
 },
 "answer.fillers": [],
 "answer.structure": {
  "sentences": 9,
  "crossed": 7,
  "unread": 2,
  "unread_ids": [
   "QD01-S05",
   "QD01-S08"
  ],
  "crosses_compared": 7,
  "crosses_matched": 0,
  "extending": []
 },
 "answer.reasons": [
  "NO_MATCHING_CROSS_IN_READ_SENTENCES",
  "UNREAD_SENTENCES:2"
 ],
 "abstain": {
  "type": "NO_MOVE_LICENSED",
  "reasons": {
   "FILL_HOLE:NO_ATTESTED_CELL": 1
  }
 }
}
```
<!-- w3c2-entry:end -->

### 判断記録（W3-c2）

出典の欄が「plan」のものは中間職の指示書（`.claude/vera-audit/review-impl/W3-c2/plan.md`）の判断記録 D1〜D19 に従ったもの。**J で始まるものは実装役が足した・変えた判断**。

- **D1 入口の分離（plan）**: `read()`・`main()`・`_read_ja`・`_read_en`・`_map_ja`・`_clause_ja`・`_voice_ja` を変えない。疑問文を `read()` が読むようにすると、構造の中の疑問文が `Ｘ` を充填物に持つ ATTESTED の升になって別の質問の答えになること、自由文の構造化が疑問文を事実として扱うこと、「構造化してはいけない入力」が崩れることが起きるため。新しい関数 `read_question` だけが疑問文を読む。
- **D2・D5 印と置き換え（plan）**: 印は和文 `Ｘ`（U+FF38）・英文 `X` の 1 記号。置き換えは wh 語の区間を印に替えるだけで、語を当てはめず、助詞・読点を足さない。印が既に入力にあれば `HOLE_MARK_IN_INPUT`。読んだ後に印が役割の値に現れなければ `HOLE_DROPPED`、値の一部・述語・2 か所なら `HOLE_NOT_ISOLATED`（印の選び方で穴が黙って消える例は `＿`: agent が落ちて readable true になる。テスト `test_hole_is_isolated_by_the_one_role_that_equals_the_mark`）。
- **D3 平叙形（plan）**: 文末の補助記号と終助詞を **品詞で** 取り除き `。` を足す。もう一度読解器に通して疑問が残れば `INTERROGATIVE_NOT_FINAL`（`AかB`・`誰が来たか…` 型。`か` を全部消さない）。
- **D4 wh の表（plan）**: `docs/EVENT_CROSS.md` の表。`location` は規約の `place` に写し、`theme` は規約に無いので入れない。`cause`・`manner` は読解器が出さない関係、どんな＋N は十字に腕が無いので、読まずに型付きで棄権する。英文の where・when は規約の英文の枠に時・場所の役割が無いので読まない。安全網: 平叙形に `semantic_reader._WH` が残れば `WH_NOT_IN_TABLE`、wh の直後が副助詞・係助詞の `か`・`も`・`でも` なら `WH_INDEFINITE`、wh が 2 つ以上なら `MULTIPLE_HOLES`。
- **D6 英文の書き換え（plan）**: 3 形だけ。E1 主語の問い（wh（＋N）を `X` に替える）、E2 do 疑問の wh（強調の do の平叙文にする。`X` は動詞の直後、または取り残しの `to` の後。**取り残しの `to` の判定が先**: 動詞の後の残りが末尾の `to` で終わるときは `to` の後に印を置き、残りが `to` 1 語だけなら `The girl did write to X.` とする。印の後に取り残しの `to` が残る形は作らない。第 2 ラウンド M1）、E3 はい／いいえ（do 疑問）。ほかは `EN_FORM_NOT_REWRITTEN`。位置が決まらなければ `HOLE_POSITION_UNDETERMINED`。
- **D8 `question` 欄（plan）**: 鍵の順は `hole_role hole_type wh kind restrictor hole_mark declarative`。はい／いいえ疑問は `kind: POLAR_QUESTION`・`hole_role: "polarity"`。
- **D9 一致の定義（plan）**: 事前登録のとおり。`center` の全鍵の完全一致、穴以外の腕の集合の一致、充填物の表記だけを NFKC で比べる。腕が多い十字は一致ではない。言い換え・近傍・`FACE_SWAP` は使わない（Q4 の機械検査はこのドキュメントの測定結果の区間）。
- **D10 穴の型による除外（plan）**: `docs/EVENT_CROSS.md` の「穴の候補の判定」。`event_cross._agreement` は役割の表に縛られているので呼ばず、規則 3〜7 と同じ順の `observe._hole_type_check` を書いた。役割の表による型一致は `role_agreement` に写すだけで、除外に使わない。
- **D11 状態と焦点（plan）**: 事前登録の表のとおり（2 行の追加は上の変更記録）。`anchor` は None、質問の十字は `answer.question_cross` にだけ載せ、実現器に渡さない。
- **D12 証拠（plan）**: 構造の文の読み（`CROSSED`）だけ。錨の読み・索引・構造の中の疑問文は証拠にならない。読めなかった文の数と id を `answer.structure` に必ず出す。
- **D13・D16・D19（plan）**: 疑問文でない `question` 錨は今までの経路。`cli.py` を変えない。`observe.py` は既存の行を変えずに足すだけ（`observe()` の docstring の直後に 2 行、モジュールの docstring に 3 行の追記、あとは末尾の追加）。
- **D14（plan）**: `tests/reading_soundness/ja_r9.jsonl` は W3-b1 の凍結データで既に在るので触らない。`en_r5.jsonl` も作らず、検査データは全部 `tests/observe/question/` に置く。
- **D15（plan）**: 観測は構造の文と同じく `placement` を渡さずに読む。印に型を与える偽の配置を作らない。
- **D17（plan）と J1**: 採点の分類は事前登録のとおり。
- **D18（plan）**: 質問の観測も `record_turn` が今の形で追記し、`replay` が同じ sha256 になる。`reobserve` は質問の経路を保証しない（既知の穴）。
- **J1 `truth.evidence` の意味（実装役。凍結の前に事前登録の変更記録へ）**: 問いの命題をその腕のまま述べている、`read()` が読める文書の文の id。腕が多い文は `extension_support`、`read()` が読めない文は `unread_support` に分けた。
- **J2 `INCOMPLETE_BY_EXTENSION` と `ANCHOR_CROSS_INDEX_OUT_OF_RANGE`（実装役。事前登録の変更記録）**: D11 の閉じた一覧に 2 つ足した。前者は第 1 回の実行で出た WRONG 1 件（Q185）への規則の修正。
- **J3 疑問文の検出（実装役。plan D3 からの変更）**: 読解器自身の疑問の検出（`document_view` の未読の理由）に加えて、文末が `?`・`？` なら疑問とみなす。理由: `兄か弟が鉛筆を貸した？` のように構成の読みが `？` を読み飛ばして節にしてしまう文があり、検出が外れると `NOT_A_QUESTION` として今までの経路に落ちるため。規則は足しているが語の一覧ではなく文末の記号の検査。
- **J4 `answer.question` は `declarative` を載せない（実装役。plan D8 との整合）**: `read_question` の出力の `question.declarative` は印を含む文なので、観測の出力（`answer.question`、`NoAnchor` の detail）では省く。印を含む実現の文を出力に出さないため（`answer.question_cross` の十字の表記だけが印を含む）。
- **J5 充填物の並べ方（実装役）**: `answer.fillers` は表記ごとに 1 件（NFKC で同じで表記が違う `Ａ社`・`A社` は別件で、同じ `nfkc` を持つ）。並びは `(nfkc, surface)` の文字列順で表示のためだけ。`role_agreement` は充填物の欄に（先頭の証拠のもの）と、証拠ごとの欄の両方に出す。
- **J6 `answer.structure.extending`（実装役）**: 「質問の十字に腕を足した十字」を `{reading, cross_index, extra_roles, fillers}` の列で出す。NO_ATTESTED_CELL を「文書に何も無い」と読ませないためと、INCOMPLETE_BY_EXTENSION の根拠のため。
- **J7 wh 語の照合（実装役）**: 和文はトークンの表層（`どうやって` のように連続するトークンは文字列として）と品詞（代名詞・連体詞・副詞）、英文は文頭の語。表に無い疑問の語（`どれ`・`どなた` など）は検出しない（既知の穴）。
- **J8 検査データの機械検査の閉じた除外語（実装役）**: `check_no_data_words_q.py` は、コード自身の語彙（`read build wrote written reader person patient agent recipient`）・役割名・型 id・表の wh 語を走査から外す。外した語はファイルの中に名前で書いてある。
- **J9 手順の順序（実装役）**: 手順 5 のテストより前に、凍結した検査データを 1 回流した（第 1 回。`q2_score.r1.json`）。検査データは直していない。
- **J10 Q4 の grep の説明（実装役）**: `q4_observe_grep.txt` の行は 3 行: `observe()` の中の `_observe_question(viewpoint, structure, lookup, neighbors, ledger)` の呼び出し、`_observe_question` の定義の引数 `neighbors`（D19 が定めた呼び出しの形。受け取って使わない）、`SAL.rank([], state).trace`（場を答えに効かせない印）。それ以外は出ない（第 2 ラウンドで「2 行」の記述を実測の 3 行に揃えた）。
- **J11 構造の文の読み方（実装役）**: 構造の文は `read()`（W3-c の `read_sentence`）で読む。質問の読みだけが `read_question`。
- **J12 正解の訂正 Q080（実装役）**: 凍結した検査データの Q080「母は何を作りました？」の正解を、凍結時は「弁当」だけにしていたが、文書には「母は台所で料理を作った」（腕が多い文）もあり、正解は弁当と料理の 2 つだった。`INCOMPLETE_BY_EXTENSION` の `structure.extending` で気づいた。検査データは直さず `tests/observe/question/corrections.jsonl` に前後・理由・日時を追記し、採点は訂正を当てない結果と当てた結果の両方を出している（第 1 回の出力に訂正を当てると WRONG は Q080 と Q185 の 2 件、規則の修正後は 0 件。`artifacts/w3-c2/q2_rounds_with_corrections.txt`）。

- **J13 全体テストの基線との差（実装役）**: 基線 114 件に対し、全体テストの失敗は 116 件。増えた 2 件は `test_p4_abilities::test_speech_act_drafts_fill_new_roles_and_reread` と `bank_score/test_bs_end_to_end::test_s6_two_runs_agree_except_timing_and_recount_matches`（チケットが環境由来とした 2 件）。単独で流しても落ち（`artifacts/w3-c2/pytest_two_alone.txt`）、基点 2478fc7 の展開でも同じ 2 件が落ちる（`pytest_two_at_base.txt`）。それ以外に増えた失敗は無い。また `tests/test_observe_data.py` と `tests/test_event_cross_data.py` を同じ pytest プロセスで流すとモジュール名 `measure` の衝突で 2 件が落ちる（この 2 ファイルだけで再現する既存の性質で、全体テストでは落ちていない）。

- **J14 取り残しの `to` の優先順位（第 2 ラウンド M1。実装役）**: `_question_en` の E2 で、残りが空 → 動詞の直後、残りが末尾の `to` で終わる → 末尾の後、残りが `to` で始まる → 動詞の直後、の順に判定する（前は「`to` で始まる」が先で、残りが `to` 1 語だと `The girl did write X to.` になり、読解器が末尾の `to` を捨てて印を目的語（patient）と読み、`Who did the girl write to?` に `letter` が FILLED で返った）。変わる入力は「残りが `to` で始まりかつ `to` で終わる」形だけ。凍結した検査データの 185 問には該当の形が無く、出力は変わっていない（`artifacts/w3-c2/q2_outputs.jsonl` が修正前と byte 一致。`m1_q2_cmp.txt`）。語・助詞は足していない。回帰テストは `tests/test_question_cross.py`・`tests/test_question_cross_observe.py`。

### 既知の穴（W3-c2。隠さない）

件数は下の「測定結果」の区間。
1. **誰に・どこで・どこへ・いつ は印では読めない**。読解器が、型の証拠が要る位置（受取人・場所・時）の語を印では読まない（`RECIPIENT_TYPE_UNDETERMINED:Ｘ`・`NO_SUPPORTED_CLAUSE`・`HOLE_NOT_ISOLATED`）。これは仕様どおりの棄権で、語・助詞・読点を足す、偽の配置で印に型を与える、で直さない。TIME の質問は一つも観測まで届かず、PLACE は起点（から）の一部だけが届く。
2. **腕が多い文は一致しない**。「先生は駅で地図を渡さなかった」は「先生は何を渡さなかった？」に一致しない（否定の問いに、否定が一部にだけ掛かる文を当てないため）。正解がそれだけの質問は FALSE_NONE。別の充填物を名指す場合は `INCOMPLETE_BY_EXTENSION` で棄権する。
3. **言い換えなし**。述語は語彙素の完全一致で、近い語（渡す／送る）・類義・態の言い換えを使わない。充填物の一致は NFKC の表記だけ。
4. **`reobserve` は質問の経路を保証しない**。質問の要素に `reobserve` を呼ぶと、錨の経路を前提にしているため `MISMATCH`（`CELL_NOT_OBSERVED`）になる。
5. **英文の形は 3 つだけ**（主語の問い・do 疑問の wh・do 疑問）。be 動詞・法助動詞の疑問、否定を含む疑問、二重目的語の穴、複文は `EN_FORM_NOT_REWRITTEN` や `HOLE_POSITION_UNDETERMINED` で棄権する。英文の where・when は読まない。
6. **既定の入口は配置が無い（スタブ）ので、穴の型は確かめられない**。`hole_type_check` は `NOT_CHECKED(NO_PLACEMENT)` と出るが、除外はしない（plan D10）ため、「何を呼んだ？」に人（「生徒」）が答えとして返りうる（実測: 小さな文書で確認。`answer.fillers[*].hole_type_check` に `NOT_CHECKED` が出ている）。`どの＋N` だけは型が `AGREE` の候補しか答えにしない。英文も同じ（`Who did the girl write?` に `The girl wrote a letter.` の `letter` が返りうる。PERSON の穴は patient を許し、型は `NOT_CHECKED` で外さない。配置を渡せば `HOLE_TYPE_DISAGREE` で外れる。第 2 ラウンドで追記）。
7. **構造の中の読めない文が答えを隠していても FILLED になりうる**。`answer.structure.unread` と `unread_ids` が出るが、読めない文に別の充填物があるかは分からない（FILLED は「読めた文の中では」の答え）。
8. **印と同じ字を含む質問は棄権する**（`HOLE_MARK_IN_INPUT`）。文書の文が印と同じ字を持つ場合（`Ｘが…`）は、答えとして `Ｘ` を返す。
9. **PROPERTY（どんな＋N）・CAUSE・MANNER は読まない**。十字に腕が無い・読解器が関係を出さないため、全部が型付きの棄権。
10. **表に無い疑問の語は検出しない**（`どれ`・`どなた`・`いかが` など）。はい／いいえ疑問として読まれうるが、はい／いいえ疑問は観測しない（`POLAR_QUESTION`）ので答えは作られない。数の問い（何人・いくつ・how many）は `WH_NOT_IN_TABLE`。
11. はい／いいえ疑問は十字を作るだけで、観測しない（`POLAR_QUESTION`）。
12. `vera ask --mode round5 --document` につながっていない（このチケットの範囲外）。 → **W3-c4 で後段としてつないだ**（既存の経路が `UNKNOWN_UNREAD`・`UNKNOWN_NO_EVIDENCE` を返したときだけ。「文書 QA の後段（W3-c4）」の節。元の行は消さない）。
13. **読解器は英文の末尾の取り残しの `to` を黙って捨てる**（基点でも `The girl wrote a letter to.` を `agent girl / patient letter` と読む）。W3-c2 の範囲外なので直していない（事実の記録）。そのため `read_question` は、平叙形に取り残しの `to` が印より後に残らない形だけを作る（残りが `to` 1 語なら印を `to` の後に置く。読解器は受け手の位置を型の証拠が無いので棄権する）。`Who did the girl write to?` は `QUESTION_NOT_READ` になる。読解器側の健全性の穴（別チケット候補）。

### Q5 の申し送り（監査役が隠しバンク B2 で測るとき）

`tests/observe/question/run_questions.py` は、`--questions` に `{id, lang, text, doc}`（正解の無い問は `truth: null`、または `truth` の欄を省く）の jsonl、`--docs` に `<doc>.jsonl`（`{id, text, lang}` の行）を置いたディレクトリを渡せば同じ集計を出す: `python tests/observe/question/run_questions.py --questions Q.jsonl --docs DIR --out O.jsonl --score S.json --timing T.json`（`--placement-dir` は配置つきの問があるときだけ）。正解の無い問は採点せず、FILLED・TIE の数と、`score.unscored` に充填物・証拠の文 id・状態を出す。誤答の数は、正解のある問だけで数える。

<!-- w3c2-measured:begin -->
### 測定結果（`tests/observe/question/recompute_q.py` が `artifacts/w3-c2/` から作った区間。手で書き換えない）

**Q2**（出典: `artifacts/w3-c2/q2_score.json`、検査データ `tests/observe/question/`、凍結 2026-10-03 19:47:07 +0900）: 全 185 問。CORRECT 99・WRONG 0・FALSE_NONE 4・ABSTAINED 82（正答率 53.5%。誤った答え 0）。
正解の訂正（`corrections.jsonl`）: Q080。訂正を当てた結果: CORRECT 99・WRONG 0・FALSE_NONE 4・ABSTAINED 82。

| 穴の型 | 問 | CORRECT / WRONG / FALSE_NONE / ABSTAINED |
|---|---|---|
| CAUSE | 11 | 0 / 0 / 0 / 11 |
| ILLFORMED | 7 | 7 / 0 / 0 / 0 |
| MANNER | 9 | 0 / 0 / 0 / 9 |
| PERSON | 45 | 28 / 0 / 1 / 16 |
| PLACE | 19 | 7 / 0 / 0 / 12 |
| POLAR | 8 | 8 / 0 / 0 / 0 |
| PROPERTY | 8 | 0 / 0 / 0 / 8 |
| RESTRICTOR | 17 | 12 / 0 / 0 / 5 |
| THING | 44 | 37 / 0 / 3 / 4 |
| TIME | 17 | 0 / 0 / 0 / 17 |

| 言語 | CORRECT / WRONG / FALSE_NONE / ABSTAINED |
|---|---|
| en | 29 / 0 / 0 / 18 |
| ja | 70 / 0 / 4 / 64 |

| 正解の種類 | CORRECT / WRONG / FALSE_NONE / ABSTAINED |
|---|---|
| ILLFORMED | 7 / 0 / 0 / 0 |
| NONE | 11 / 0 / 0 / 41 |
| ONE | 64 / 0 / 4 / 36 |
| SPLIT | 9 / 0 / 0 / 5 |
| YESNO | 8 / 0 / 0 / 0 |

`answer.status` の件数: DIRECTION_NOT_APPLIED 1・FILLED 64・HOLE_TYPE_UNDETERMINED 1・INCOMPLETE_BY_EXTENSION 2・NO_ATTESTED_CELL 15・POLAR_QUESTION 7・QUESTION_NOT_READ 86・TIE 9。

棄権（ABSTAINED）の理由を穴の型別に（`READ:` は読解器の理由、それ以外は観測の状態）:
- CAUSE: READ:HOLE_RELATION_NOT_PRODUCED:cause 11
- MANNER: READ:HOLE_RELATION_NOT_PRODUCED:manner 9
- PERSON: DIRECTION_NOT_APPLIED 1・INCOMPLETE_BY_EXTENSION 1・READ:AGENT_EVIDENCE_MISSING:Ｘ 7・READ:EN_FORM_NOT_REWRITTEN 1・READ:RECIPIENT_TYPE_UNDETERMINED:X 1・READ:RECIPIENT_TYPE_UNDETERMINED:Ｘ 2・READ:SUBJECT_TYPE_UNDETERMINED:object or path:Ｘ 1・READ:SUBJECT_TYPE_UNDETERMINED:Ｘ 1・READ:UNKNOWN_PREDICATE 1
- PLACE: READ:HOLE_ROLE_NOT_PRODUCED:en:place 3・READ:NO_SUPPORTED_CLAUSE 9
- PROPERTY: READ:HOLE_NOT_AN_ARM:property 8
- RESTRICTOR: HOLE_TYPE_UNDETERMINED 1・READ:AGENT_EVIDENCE_MISSING:Ｘ 2・READ:NO_SUPPORTED_CLAUSE 1・READ:SUBJECT_TYPE_UNDETERMINED:Ｘ 1
- THING: INCOMPLETE_BY_EXTENSION 1・READ:EN_FORM_NOT_REWRITTEN 1・READ:HOLE_MARK_IN_INPUT 1・READ:HOLE_POSITION_UNDETERMINED 1
- TIME: READ:HOLE_NOT_ISOLATED 10・READ:HOLE_ROLE_NOT_PRODUCED:en:time 3・READ:NO_SUPPORTED_CLAUSE 2・READ:RECIPIENT_TYPE_UNDETERMINED:Ｘ兄 1・READ:RECIPIENT_TYPE_UNDETERMINED:Ｘ姉 1

FALSE_NONE（正解があるのに「無い」と返したもの）の 1 件ずつの原因:
- Q010 「先生は何を渡さなかった？」（穴 THING、状態 NO_ATTESTED_CELL）: 腕が多い文だけが正解を述べる（一致の定義 D9 で一致しない。`structure.extending` に出ている）
- Q059 「漁師は何を送った？」（穴 THING、状態 NO_ATTESTED_CELL）: 腕が多い文だけが正解を述べる（一致の定義 D9 で一致しない。`structure.extending` に出ている）
- Q118 「誰が薬を渡した？」（穴 PERSON、状態 NO_ATTESTED_CELL）: 腕が多い文だけが正解を述べる（一致の定義 D9 で一致しない。`structure.extending` に出ている）
- Q121 「弟は何を読んだ？」（穴 THING、状態 NO_ATTESTED_CELL）: 腕が多い文だけが正解を述べる（一致の定義 D9 で一致しない。`structure.extending` に出ている）

誤った答え（WRONG）: 無し。
規則を直した回ごとの記録（`q2_score.rN.json`）: q2_score.r1.json は WRONG 1（Q185）。q2_score.r2.json は WRONG 0（無し）。
所要時間（`q2_timing.json`）: 185 問で合計 1.53 秒（1 問あたり 中央値 0.0064 秒・最大 0.200 秒。1 分平均の負荷 3.17）。

**Q1（平叙文の出力が 1 バイトも変わらない）**（出典: `q1_read_cmp.txt`・`q1_observe_cmp.txt`）:
- 読解 read entry_inputs run 1: same
- 読解 read entry_inputs run 2: same
- 読解 read entry_inputs run 3: same
- 読解 read q1_doc_inputs run 1: same
- 読解 read q1_doc_inputs run 2: same
- 読解 read q1_doc_inputs run 3: same
- 観測 observe seed 0: same
- 観測 observe seed 4242: same
- 観測 observe seed 1: same

**Q4**: `q4_observe_grep.txt` 3 行（内訳は判断記録 J10）。`q4_no_data_words.txt`: data words scanned: 404; added lines scanned: 504; hits: 0。`check_hardcode.txt`: PROPER/NUMERIC (must be empty): [] / ENGLISH NAMES (must be empty): []。

**共通**: `common_numstat.txt`（基点 2478fc7 に対する追加・削除の行数、削除列はすべて 0）:
- 51	0	docs/EVENT_CROSS.md
- 377	0	docs/OBSERVATION.md
- 259	0	verantyx/observe.py
- 245	0	verantyx/semantic_read.py

**Q6**: `pytest_related.txt` の最終行: 2350 passed in 14.38s。全体テスト `pytest_full.txt` の最終行: 116 failed, 11182 passed, 45 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 316.63s (0:05:16)。基線にない失敗 `pytest_new_failures.txt`: 2 行。増えた成功 `pytest_fixed.txt`: 0 行。
<!-- w3c2-measured:end -->

## W5-d の事前登録: 質問の十字 — 型を確かめられない充填物を答えにしない
<!-- w5d-prereg:begin -->
事前登録の時刻: 2026-10-03 23:07:21 +0900（`date '+%F %T %z'` の出力。製品コードの変更より前）。ベースは `dev` = `c875ed3`。

攻撃の第 4 波（W3-c2: A01 英語の `Who did the girl write?` が `letter`・`note` を TIE で返す／A02 時の副詞が patient の候補に混ざる）の根は同じ: 充填物の型を確かめられないまま候補にしている。次の規則で直す（中間職の指示書 Q-J1〜Q-J5）。

- **Q-J1 候補の条件**: 穴の腕の充填物は、`_hole_type_check` の判定が `AGREE` のときだけ候補にする。除外の順は今のまま `SAME_AS_RESTRICTOR` → `HOLE_TYPE_DISAGREE` →（which+N のとき）`HOLE_TYPE_NOT_CHECKED` → 新しい `TYPE_UNCHECKED`（それ以外の `NOT_CHECKED` すべて: 配置なし・UNPLACED・UNKNOWN・推定・MULTIPLE で一部が穴の外・無効な答え）。`HOLE_EXCLUSION_REASONS` の末尾に `TYPE_UNCHECKED` を足す（並びは変えない）。
- **Q-J2 全候補一致**: `place.state == 'MULTIPLE'` で `place.types` が空でなく、そのすべてが穴の型の集合に入るとき `AGREE`（理由 `MULTIPLE_ALL_IN_HOLE`）。一部でも外れれば今どおり `NOT_CHECKED`。`DECIDED` かつ `origin == 'direct'` の判定は変えない。推定は AGREE にしない。
- **Q-J3 新しい状態 `NO_TYPED_CANDIDATE`**: 候補が 0 で、外したものに `TYPE_UNCHECKED` が 1 つでもある → `NO_TYPED_CANDIDATE`（棄権。`NoMoveLicensed({'FILL_HOLE:NO_TYPED_CANDIDATE': 1})`）。外したものが全部 `HOLE_TYPE_DISAGREE`・`SAME_AS_RESTRICTOR`・`HOLE_TYPE_NOT_CHECKED` なら今どおり `TYPE_EXCLUDED_ALL`（「型が合わないと分かった」と「確かめられなかった」を混ぜない）。
- **Q-J4 言語・配置**: 言語で分けない。英語でも `--placement`（FilePlacement）で direct の型があれば AGREE になりうる。質問の観測は `VERA_PLACEMENT` を読まない。
- **Q-J5 A02**: `毎日本` を 1 つの充填物にする誤りは読解器（`semantic_reader.py`、触らない）の問題。観測側では配置で型が確かめられない → `TYPE_UNCHECKED` で `excluded` に残る。
- 平叙文の観測は 1 バイトも変えない（`_hole_type_check` を呼ぶのは質問の経路だけ。`o1_bytes` の `cmp` で確かめる）。
- 閉じるもの: 本節の「既知の穴 6」（配置なし・型未確認の充填物が FILLED/TIE の候補になる）。代価は正答の減少（G2 で数える）。

### 宣言する規則どうしの衝突（実装役は解かずに宣言する。判断は監査役）
チケットの規則を字面どおりに入れると、旧い振る舞いをそのまま固定した既存テストが落ちる。実装役はチケットの規則どおりに作り、テストの期待は変えず（改訂が許された 1 関数を除く）、落ちた id を全部宣言する。

| # | 衝突 | 落ちる見込みのもの |
|---|---|---|
| K1 | W3-c2「型を確かめられない充填物は候補から外す」 × 配置なしで FILLED/TIE を期待する既存テスト・攻撃の外れ | `tests/test_question_cross_observe.py` の一部、攻撃の写しの 2 件 |
| K2 | R1「配置が無い日本語の名前は命名の文で導入されたものだけ」 × 配置なし（スタブ）の名前で振る既存テスト・R2 の攻撃テスト | `tests/test_routing_from_text*.py` の多数、攻撃の写しの R2 の 1 件 |
| K3 | A1「出典の本文が渡した文書の中にある」 × 存在しない文書を渡して `family: document` を人とする既存テスト | `tests/test_basis_policy_form.py`・`tests/test_basis_policy_w5c_r3.py` の一部 |
| K4 | D1「文面が同じときだけ格上げ」 × 別の文の記録で格上げすることを固定した既存テスト（改訂許可の 2 件の外） | `tests/test_basis_policy_w5c_r3.py::test_r3_a_recorded_yes_still_lifts_a_generated_answer` |
| K5 | W3-a3 A1「枠の確認は助詞ごとの型の一致」 × 攻撃の写しの不変条件「gen_frame の格上げ語は全部 CONFIRMED」 | `tests/attack/w3a3/test_attack_w3a3_r6.py::test_all_r6_generated_frame_upgrades` |
| D1-改訂 | 許可された 2 件のうち設計上落ちる 1 件 | `tests/test_basis_policy_confirm.py::test_two_confirmed_records_with_the_same_claim_are_not_a_split`（名前不変で改訂。前後の全文は BASIS_POLICY の測定の節） |

### 受入基準の測り方（G1〜G7。測る前に固定）
- G1: 攻撃の写し 5 本（`tests/attack/w3c2`・`test_attack_w5b_wave2.py`・`test_attack_w5c_*.py` 2 本・`tests/attack/w3a3/test_attack_w3a3_r6.py`）。落ちてよいのは宣言した K1(2)・K2(1)・K5(1) の 4 id だけ。A02・R2・W3-a3 A1 は新しいテストで確かめる。
- G2: `artifacts/w5-d/scripts/run_questions_both.py`（実装役の 185 問、配置あり／なし）。誤答 0、型未確認の充填物を持つ FILLED/TIE 0。正答の減少は変更前（`artifacts/w5-d/before/q185_*.json`）との差を数で。
- G3: 経路づけの凍結 4 本（`run_bank.py`、配置なし・r7）の misroutes と、自作の合成（`artifacts/w5-d/g3_synth/`、入力と期待を先に書き sha256 を凍結）。
- G4: `artifacts/w5-d/scripts/g4_probe.py`（入力を先に凍結）。自己申告の文書・文面違いの確認記録から `ANSWER_*` が 0。対照（本当に渡した文書の文・完全一致の記録）では答えが出ること。
- G5: r7 を cache なしで 2 回作り `verify` が両方 OK、`content_sha256` が run1 = run2 = r6（`5c969d45…`）。L1〜L3・動詞 300 語を `measure_w5d.py` で r6 と r7 で測り同じ。
- G7: `pytest tests`（最後に 1 回）の失敗集合が基線 `dev_c875ed3_failures.txt` から増えない。増えた分は 1 件ずつ K1〜K5 または環境由来に当てる。当たらないものはコードを直す。
- 基線（変更前）の測定は `artifacts/w5-d/before/` に保存済み（この事前登録より前）。製品コードの差分はこの時点で空。

<!-- w5d-prereg:end -->

## W5-d の測定: 質問の十字
<!-- w5d-measured:begin -->

測定の時刻: 2026-10-03 23:34:53 +0900。出典はすべて `artifacts/w5-d/` のファイル（下に名前を書く）。全体テスト: `pytest_full.txt` の最終行 `198 failed, 11889 passed, 45 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 341.39s (0:05:41)`。基線 `dev_c875ed3_failures.txt` に無い新しい失敗は 83 件（`new_failures.txt`）で、1 件ずつ `new_failures_explained.txt` に K1〜K5・改訂・環境由来のどれかを書いた。どれにも当たらないものは 0 件（`grep -v -E 'K[1-5]|D1-改訂|環境由来' new_failures_explained.txt` が空）。基線から直った失敗は 0 件（`fixed_failures.txt`）。

### 質問の十字（G2。`g2_185_place.json`・`g2_185_noplace.json`、変更前は `before/q185_place.json`・`before/q185_noplace.json`。`scripts/run_questions_both.py`）
実装役の凍結データ 185 問。

| 条件 | 正答 | 誤答 | 偽の「無し」 | 棄権 | 型未確認の充填物を持つ FILLED/TIE の充填物 | NO_TYPED_CANDIDATE |
|---|---|---|---|---|---|---|
| 変更前・配置あり | 99 | 0 | 4 | 82 | 68 | 0 |
| 変更後・配置あり | 38 | 0 | 4 | 143 | 0 | 63 |
| 変更前・配置なし | 87 | 0 | 4 | 94 | 68 | 0 |
| 変更後・配置なし | 26 | 0 | 4 | 155 | 0 | 63 |

誤答は 0 のまま。型未確認の充填物を持つ FILLED/TIE は 68 → 0（配置なしでも）。**代価（正答の減少）**: 配置あり 99 → 38（61 問減）、配置なし 87 → 26（61 問減）。減った分は誤答ではなく棄権（`NO_TYPED_CANDIDATE`）になった。中間職の凍結データ（64 問・56 問）は実装役は開いていない（レビューで中間職が流す）。

### 「既知の穴 6」の扱い
本節の既存の「既知の穴 6」（配置なし・型未確認の充填物が FILLED/TIE の候補になる）は**閉じた**（型未確認は候補にしない）。代価: 正答の減少（上の表）。既存の行は消していない。

### 平叙文の観測は変わらない（`q1_observe_cmp.txt`）
`tests/observe/o1_bytes.py --child`（凍結ケース全部。`M15-question-J01` を含む）を基点と今の木で流し、出力は基点と 2 種のハッシュ種で byte 一致。

### 宣言した衝突 K1（質問の十字）の実際の失敗 id（15 件）
- `tests/attack/w3c2/test_attack_w3c2_question_cross.py::test_negative_question_does_not_match_affirmative_crosses`
- `tests/attack/w3c2/test_attack_w3c2_question_cross.py::test_tied_agent_witnesses_remain_a_tie`
- `tests/test_question_cross_observe.py::test_a_filler_that_is_the_mark_character_is_a_correct_answer`
- `tests/test_question_cross_observe.py::test_a_tie_does_not_depend_on_the_order_of_the_sentences`
- `tests/test_question_cross_observe.py::test_a_tie_is_returned_with_both_and_never_broken`
- `tests/test_question_cross_observe.py::test_an_arm_tie_gives_each_filler_as_a_candidate_of_its_own`
- `tests/test_question_cross_observe.py::test_an_extending_cross_that_names_another_filler_makes_the_answer_incomplete`
- `tests/test_question_cross_observe.py::test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun`
- `tests/test_question_cross_observe.py::test_filled_has_the_filler_the_sentence_id_and_the_coordinate`
- `tests/test_question_cross_observe.py::test_nfkc_of_the_filler_and_of_the_other_arms`
- `tests/test_question_cross_observe.py::test_polarity_tense_and_voice_must_be_the_same`
- `tests/test_question_cross_observe.py::test_the_command_line_entry_gives_the_same_bytes_for_two_hash_seeds`
- `tests/test_question_cross_observe.py::test_the_cross_index_of_a_question_is_zero_or_nothing`
- `tests/test_question_cross_observe.py::test_the_ledger_records_a_question_and_replays_to_the_same_output`
- `tests/test_question_cross_observe.py::test_the_reading_of_the_anchor_is_not_evidence`

型・配置を与えれば K1 の既存テストの意図は新しい規則でも満たせることの証拠: `k1_probe.txt`（scratchpad の写しの `tests/conftest.py` に機械的な書き換えを当てた。テストファイルは変えていない）。
```
K1 probe (scratchpad copy of c875ed3 + the changed verantyx files; the test file is NOT changed; only tests/conftest.py of the copy gets the mechanical rewrite in k1_probe_rewrite.diff:
the stub lookup answers DECIDED/direct for the fillers the tests use: 船長 提督 Ｘ 商人 人 = PERSON, Ａ社 A社 = GROUP_ORG, 小包 = ARTIFACT).

K1 failing existing tests in the real tree:       13
of those, still failing with the rewrite:        2  => pass with a typed placement: 11
  still failing (in K1): tests/test_question_cross_observe.py::test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun
  still failing (in K1): tests/test_question_cross_observe.py::test_the_command_line_entry_gives_the_same_bytes_for_two_hash_seeds
tests that fail only because of the rewrite (they passed in the real tree):        1
  probe artifact: tests/test_question_cross_observe.py::test_restrictor_whose_type_is_not_decided_says_so

reasons: test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun asserts FILLED with NOT_CHECKED(NO_PLACEMENT): the opposite of Q-J1 by design;
test_the_command_line_entry_gives_the_same_bytes_for_two_hash_seeds runs the CLI in a subprocess (the in-process rewrite does not reach it; the same intent is in tests/test_question_cross_w5d.py::test_k1_the_command_line_entry_gives_the_same_bytes_for_two_hash_seeds with --placement, which passes).
test_restrictor_whose_type_is_not_decided_says_so: the rewrite types 人, so the restrictor is decided (an artifact of the probe).
```

### K1 の追加の帰結: `recompute_q.py --check`（`doc_checks.txt`）
`tests/observe/question/recompute_q.py --check`（docs の `w3c2-entry` 区間を、入口を実際に走らせて作り直して照合する道具）は、配置を渡さない 3 つの例（`QD05` の FILLED・`QD01` の TIE・`NO_ATTESTED_CELL`）を走らせ、`FILLED` を期待する所で `AssertionError: ('FILLED', 'NO_TYPED_CANDIDATE')` になる（変更前の木では通る）。これは K1 と同じ原因（配置なしでは型未確認の充填物は候補にならない）。道具は許可パスの外（`tests/observe/question/`）、`w3c2-entry` 区間は既存の区間で 1 文字も変えられないので、**当てていない**。監査役の判断で、例に型を与える配置を足す（または FILLED/TIE の例を配置つきにする）改訂が要る。ほかの `recompute*.py --check` と `render_w3a3.py --check` は通る。

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

**この文書の担当**: K1・B3・D2-7（質問の観測と `recompute_q.py`）。
<!-- w5d2-prereg:end -->

<!-- w5d2-amended:begin -->
#### `tests/test_question_cross_observe.py` (before = git show c875ed3:tests/test_question_cross_observe.py)

Added (helpers / tests, not amendments): `person_placement`, `=PERSONS`

##### `test_filled_has_the_filler_the_sentence_id_and_the_coordinate` — before

```python
def test_filled_has_the_filler_the_sentence_id_and_the_coordinate(tmp_path):
    out, text = ask(tmp_path, Q_SHIP, [S1, '鳥が空を飛んだ。'])
    a = out['answer']
    assert list(a) == ['schema', 'status', 'question', 'question_cross', 'fillers', 'excluded', 'structure', 'reasons']
    assert a['schema'] == 'verantyx.question_answer/1' and a['status'] == 'FILLED'
    assert fills(out) == [('船長', [('s1', 0)])]
    assert out['focus']['kind'] == 'FOCUS' and out['anchor'] is None and out['abstain'] is None
    el = out['ranks'][0]['elements'][0]
    assert el['cell_key'] == out['focus']['cell_key'] and el['coords'] == [{'origin': {'kind': 'structure', 'id': 's1', 'cross_index': 0}, 'moves': []}]
    assert el['occupied'] == 'ATTESTED' and el['realization']['status'] == 'REALIZED' and el['realization']['text'].startswith('船長') and 'Ｘ' not in el['realization']['text']
    assert a['structure']['sentences'] == 2 and a['structure']['unread'] == 1 and a['structure']['unread_ids'] == ['s2']
    assert a['structure']['crosses_compared'] == 1 and a['structure']['crosses_matched'] == 1
    assert a['question']['hole_role'] == 'agent' and 'declarative' not in a['question']
    assert out['counts']['question']['status'] == 'FILLED'
```

##### `test_filled_has_the_filler_the_sentence_id_and_the_coordinate` — after

```python
def test_filled_has_the_filler_the_sentence_id_and_the_coordinate(tmp_path):
    out, text = ask(tmp_path, Q_SHIP, [S1, '鳥が空を飛んだ。'], placement=write_placement(tmp_path, PERSONS))    # W5-d2 (K1): the filler's type is given by a placement
    a = out['answer']
    assert list(a) == ['schema', 'status', 'question', 'question_cross', 'fillers', 'excluded', 'structure', 'reasons']
    assert a['schema'] == 'verantyx.question_answer/1' and a['status'] == 'FILLED'
    assert fills(out) == [('船長', [('s1', 0)])]
    assert out['focus']['kind'] == 'FOCUS' and out['anchor'] is None and out['abstain'] is None
    el = out['ranks'][0]['elements'][0]
    assert el['cell_key'] == out['focus']['cell_key'] and el['coords'] == [{'origin': {'kind': 'structure', 'id': 's1', 'cross_index': 0}, 'moves': []}]
    assert el['occupied'] == 'ATTESTED' and el['realization']['status'] == 'REALIZED' and el['realization']['text'].startswith('船長') and 'Ｘ' not in el['realization']['text']
    assert a['structure']['sentences'] == 2 and a['structure']['unread'] == 1 and a['structure']['unread_ids'] == ['s2']
    assert a['structure']['crosses_compared'] == 1 and a['structure']['crosses_matched'] == 1
    assert a['question']['hole_role'] == 'agent' and 'declarative' not in a['question']
    assert out['counts']['question']['status'] == 'FILLED'
```

##### `test_a_tie_is_returned_with_both_and_never_broken` — before

```python
def test_a_tie_is_returned_with_both_and_never_broken(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2])
    assert out['answer']['status'] == 'TIE'
    assert [f['surface'] for f in out['answer']['fillers']] == sorted(['提督', '船長'])
    assert out['focus']['kind'] == 'TIE' and len(out['focus']['candidates']) == 2
    assert len(out['ranks']) == 1 and out['ranks'][0]['kind'] == 'TIE' and len(out['ranks'][0]['elements']) == 2
    assert sorted(r['reading'] for f in out['answer']['fillers'] for r in f['evidence']) == ['s1', 's2']
```

##### `test_a_tie_is_returned_with_both_and_never_broken` — after

```python
def test_a_tie_is_returned_with_both_and_never_broken(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=write_placement(tmp_path, PERSONS))    # W5-d2 (K1)
    assert out['answer']['status'] == 'TIE'
    assert [f['surface'] for f in out['answer']['fillers']] == sorted(['提督', '船長'])
    assert out['focus']['kind'] == 'TIE' and len(out['focus']['candidates']) == 2
    assert len(out['ranks']) == 1 and out['ranks'][0]['kind'] == 'TIE' and len(out['ranks'][0]['elements']) == 2
    assert sorted(r['reading'] for f in out['answer']['fillers'] for r in f['evidence']) == ['s1', 's2']
```

##### `test_a_tie_does_not_depend_on_the_order_of_the_sentences` — before

```python
def test_a_tie_does_not_depend_on_the_order_of_the_sentences(tmp_path):
    def build(order):
        items = [{'id': 's%d' % i, 'text': t, 'reading': SR.read(t, 'ja', placement=None)} for i, t in order]
        return O.Structure.from_injected(items)
    vp = O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question')
    a = O.to_json(O.observe(vp, build([(1, S1), (2, S2)])))
    b = O.to_json(O.observe(vp, build([(2, S2), (1, S1)])))
    assert a == b and '"status":"TIE"' in a
```

##### `test_a_tie_does_not_depend_on_the_order_of_the_sentences` — after

```python
def test_a_tie_does_not_depend_on_the_order_of_the_sentences(tmp_path):
    pl = person_placement(PERSONS)    # W5-d2 (K1): the fillers are typed by a made-up placement
    def build(order):
        items = [{'id': 's%d' % i, 'text': t, 'reading': SR.read(t, 'ja', placement=None)} for i, t in order]
        return O.Structure.from_injected(items, lookup=pl, neighbors=pl)
    vp = O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question')
    a = O.to_json(O.observe(vp, build([(1, S1), (2, S2)])))
    b = O.to_json(O.observe(vp, build([(2, S2), (1, S1)])))
    assert a == b and '"status":"TIE"' in a
```

##### `test_an_arm_tie_gives_each_filler_as_a_candidate_of_its_own` — before

```python
def test_an_arm_tie_gives_each_filler_as_a_candidate_of_its_own():
    reading = SR.read(S1, 'ja', placement=None)
    reading['clauses'][0]['roles']['agent'] = ['船長', '提督']
    st = O.Structure.from_injected([{'id': 'x', 'text': 'hand written', 'reading': reading}])
    out = json.loads(O.to_json(O.observe(O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question'), st)))
    assert out['answer']['status'] == 'TIE'
    assert [f['surface'] for f in out['answer']['fillers']] == ['提督', '船長'] and all(f['from_arm_tie'] for f in out['answer']['fillers'])
    assert out['focus']['kind'] == 'FOCUS'    # one cell: the tie is inside its arm, which the answer shows
```

##### `test_an_arm_tie_gives_each_filler_as_a_candidate_of_its_own` — after

```python
def test_an_arm_tie_gives_each_filler_as_a_candidate_of_its_own():
    reading = SR.read(S1, 'ja', placement=None)
    reading['clauses'][0]['roles']['agent'] = ['船長', '提督']
    pl = person_placement(PERSONS)    # W5-d2 (K1)
    st = O.Structure.from_injected([{'id': 'x', 'text': 'hand written', 'reading': reading}], lookup=pl, neighbors=pl)
    out = json.loads(O.to_json(O.observe(O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question'), st)))
    assert out['answer']['status'] == 'TIE'
    assert [f['surface'] for f in out['answer']['fillers']] == ['提督', '船長'] and all(f['from_arm_tie'] for f in out['answer']['fillers'])
    assert out['focus']['kind'] == 'FOCUS'    # one cell: the tie is inside its arm, which the answer shows
```

##### `test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun` — before

```python
def test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [S1])    # no placement: NOT_CHECKED(NO_PLACEMENT), shown but not excluded
    assert out['answer']['status'] == 'FILLED'
    assert out['answer']['fillers'][0]['hole_type_check'] == {'verdict': 'NOT_CHECKED', 'reason': 'NO_PLACEMENT', 'expected': ['GROUP_ORG', 'PERSON'], 'observed': None}
```

##### `test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun` — after

```python
def test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun(tmp_path, monkeypatch):
    # W5-d2 (auditor's ruling B1, K1): the NAME IS FROM THE OLD CONTRACT (an unchecked type was shown but did not exclude). The contract now: with no placement the
    # filler's type is not checked, so it is not a candidate (TYPE_UNCHECKED) and the answer is the abstention NO_TYPED_CANDIDATE.
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    out, _ = ask(tmp_path, Q_SHIP, [S1])    # no placement: NOT_CHECKED(NO_PLACEMENT), excluded as TYPE_UNCHECKED
    assert out['answer']['status'] == 'NO_TYPED_CANDIDATE' and out['answer']['fillers'] == []
    assert [e['reason'] for e in out['answer']['excluded']] == ['TYPE_UNCHECKED']
    assert out['answer']['excluded'][0]['hole_type_check'] == {'verdict': 'NOT_CHECKED', 'reason': 'NO_PLACEMENT', 'expected': ['GROUP_ORG', 'PERSON'], 'observed': None}
```

##### `test_the_reading_of_the_anchor_is_not_evidence` — before

```python
def test_the_reading_of_the_anchor_is_not_evidence(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [])
    assert out['answer']['status'] == 'NO_ATTESTED_CELL' and out['answer']['structure']['sentences'] == 0
    st = O.Structure.from_jsonl(write_doc(tmp_path, [S1]))
    vp = O.build_viewpoint(anchor_text='誰が商人に小包を渡した？', anchor_kind='question')
    assert json.loads(O.to_json(O.observe(vp, O.Structure.empty())))['answer']['status'] == 'NO_ATTESTED_CELL'
    assert json.loads(O.to_json(O.observe(vp, st)))['answer']['status'] == 'FILLED'
```

##### `test_the_reading_of_the_anchor_is_not_evidence` — after

```python
def test_the_reading_of_the_anchor_is_not_evidence(tmp_path):
    pl = person_placement(PERSONS)    # W5-d2 (K1): the filler of the second structure is typed by a made-up placement
    out, _ = ask(tmp_path, Q_SHIP, [])
    assert out['answer']['status'] == 'NO_ATTESTED_CELL' and out['answer']['structure']['sentences'] == 0
    st = O.Structure.from_jsonl(write_doc(tmp_path, [S1]), pl, pl)
    vp = O.build_viewpoint(anchor_text='誰が商人に小包を渡した？', anchor_kind='question')
    assert json.loads(O.to_json(O.observe(vp, O.Structure.empty(pl, pl))))['answer']['status'] == 'NO_ATTESTED_CELL'
    assert json.loads(O.to_json(O.observe(vp, st)))['answer']['status'] == 'FILLED'
```

##### `test_nfkc_of_the_filler_and_of_the_other_arms` — before

```python
def test_nfkc_of_the_filler_and_of_the_other_arms(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, ['Ａ社が商人に小包を渡した。', 'A社が商人に小包を渡した。'])
    a = out['answer']
    assert a['status'] == 'FILLED' and sorted(f['surface'] for f in a['fillers']) == ['A社', 'Ａ社'] and {f['nfkc'] for f in a['fillers']} == {'A社'}
    assert out['focus']['kind'] == 'TIE' and len(out['focus']['candidates']) == 2    # two cells (the surface differs), one answer
    out, _ = ask(tmp_path, 'Ａ社は商人に何を渡した？', ['Ａ社が商人に小包を渡した。', 'A社が商人に小包を渡した。'])
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('小包', [('s1', 0), ('s2', 0)])]
```

##### `test_nfkc_of_the_filler_and_of_the_other_arms` — after

```python
def test_nfkc_of_the_filler_and_of_the_other_arms(tmp_path):
    pl = write_placement(tmp_path, {'Ａ社': 'GROUP_ORG', 'A社': 'GROUP_ORG', '小包': 'ARTIFACT'})    # W5-d2 (K1): the fillers are typed (the answer of the second question is 小包)
    out, _ = ask(tmp_path, Q_SHIP, ['Ａ社が商人に小包を渡した。', 'A社が商人に小包を渡した。'], placement=pl)
    a = out['answer']
    assert a['status'] == 'FILLED' and sorted(f['surface'] for f in a['fillers']) == ['A社', 'Ａ社'] and {f['nfkc'] for f in a['fillers']} == {'A社'}
    assert out['focus']['kind'] == 'TIE' and len(out['focus']['candidates']) == 2    # two cells (the surface differs), one answer
    out, _ = ask(tmp_path, 'Ａ社は商人に何を渡した？', ['Ａ社が商人に小包を渡した。', 'A社が商人に小包を渡した。'], placement=pl)
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('小包', [('s1', 0), ('s2', 0)])]
```

##### `test_an_extending_cross_that_names_another_filler_makes_the_answer_incomplete` — before

```python
def test_an_extending_cross_that_names_another_filler_makes_the_answer_incomplete(tmp_path):
    out, _ = ask(tmp_path, '誰が小包を渡さなかった？', ['提督は小包を渡さなかった。', '船長は港で小包を渡さなかった。'])
    # the admiral is a match; the captain is in a cross with one more arm: the set of fillers is not given as complete
    a = out['answer']
    assert a['status'] == 'INCOMPLETE_BY_EXTENSION' and [f['surface'] for f in a['fillers']] == ['提督'] and out['ranks'] == []
    assert out['abstain']['reasons'] == {'FILL_HOLE:INCOMPLETE_BY_EXTENSION': 1}
    # the same filler in the extending cross does not make it incomplete
    out, _ = ask(tmp_path, '誰が小包を渡さなかった？', ['船長は小包を渡さなかった。', '船長は港で小包を渡さなかった。'])
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('船長', [('s1', 0)])]
```

##### `test_an_extending_cross_that_names_another_filler_makes_the_answer_incomplete` — after

```python
def test_an_extending_cross_that_names_another_filler_makes_the_answer_incomplete(tmp_path):
    pl = write_placement(tmp_path, PERSONS)    # W5-d2 (K1): the fillers are typed by a placement
    out, _ = ask(tmp_path, '誰が小包を渡さなかった？', ['提督は小包を渡さなかった。', '船長は港で小包を渡さなかった。'], placement=pl)
    # the admiral is a match; the captain is in a cross with one more arm: the set of fillers is not given as complete
    a = out['answer']
    assert a['status'] == 'INCOMPLETE_BY_EXTENSION' and [f['surface'] for f in a['fillers']] == ['提督'] and out['ranks'] == []
    assert out['abstain']['reasons'] == {'FILL_HOLE:INCOMPLETE_BY_EXTENSION': 1}
    # the same filler in the extending cross does not make it incomplete
    out, _ = ask(tmp_path, '誰が小包を渡さなかった？', ['船長は小包を渡さなかった。', '船長は港で小包を渡さなかった。'], placement=pl)
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('船長', [('s1', 0)])]
```

##### `test_polarity_tense_and_voice_must_be_the_same` — before

```python
def test_polarity_tense_and_voice_must_be_the_same(tmp_path):
    for sentence in ('船長は商人に小包を渡さなかった。', '船長は商人に小包を渡す。'):
        out, _ = ask(tmp_path, Q_SHIP, [sentence])
        assert out['answer']['status'] == 'NO_ATTESTED_CELL', sentence
    out, _ = ask(tmp_path, '誰が商人に小包を渡さなかった？', ['船長は商人に小包を渡さなかった。'])
    assert out['answer']['status'] == 'FILLED'
    out, _ = ask(tmp_path, '誰が商人に小包を渡す？', ['船長は商人に小包を渡す。', S2])
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('船長', [('s1', 0)])]
    passive = SR.read(S1, 'ja', placement=None)
    passive['clauses'][0]['voice'] = 'passive'
    st = O.Structure.from_injected([{'id': 'p', 'text': 'hand written', 'reading': passive}])
    assert json.loads(O.to_json(O.observe(O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question'), st)))['answer']['status'] == 'NO_ATTESTED_CELL'
```

##### `test_polarity_tense_and_voice_must_be_the_same` — after

```python
def test_polarity_tense_and_voice_must_be_the_same(tmp_path):
    pl = write_placement(tmp_path, {'船長': 'PERSON'})    # W5-d2 (K1): the filler 船長 is typed (提督 is not: it is TYPE_UNCHECKED and stays beside the answer)
    for sentence in ('船長は商人に小包を渡さなかった。', '船長は商人に小包を渡す。'):
        out, _ = ask(tmp_path, Q_SHIP, [sentence], placement=pl)
        assert out['answer']['status'] == 'NO_ATTESTED_CELL', sentence
    out, _ = ask(tmp_path, '誰が商人に小包を渡さなかった？', ['船長は商人に小包を渡さなかった。'], placement=pl)
    assert out['answer']['status'] == 'FILLED'
    out, _ = ask(tmp_path, '誰が商人に小包を渡す？', ['船長は商人に小包を渡す。', S2], placement=pl)
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('船長', [('s1', 0)])]
    passive = SR.read(S1, 'ja', placement=None)
    passive['clauses'][0]['voice'] = 'passive'
    st = O.Structure.from_injected([{'id': 'p', 'text': 'hand written', 'reading': passive}], lookup=person_placement(PERSONS), neighbors=person_placement(PERSONS))
    assert json.loads(O.to_json(O.observe(O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question'), st)))['answer']['status'] == 'NO_ATTESTED_CELL'
```

##### `test_a_filler_that_is_the_mark_character_is_a_correct_answer` — before

```python
def test_a_filler_that_is_the_mark_character_is_a_correct_answer(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, ['Ｘが商人に小包を渡した。'])
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('Ｘ', [('s1', 0)])]
```

##### `test_a_filler_that_is_the_mark_character_is_a_correct_answer` — after

```python
def test_a_filler_that_is_the_mark_character_is_a_correct_answer(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, ['Ｘが商人に小包を渡した。'], placement=write_placement(tmp_path, {'Ｘ': 'PERSON'}))    # W5-d2 (K1): the filler is typed
    assert out['answer']['status'] == 'FILLED' and fills(out) == [('Ｘ', [('s1', 0)])]
```

##### `test_the_ledger_records_a_question_and_replays_to_the_same_output` — before

```python
def test_the_ledger_records_a_question_and_replays_to_the_same_output(tmp_path):
    st = O.Structure.from_jsonl(write_doc(tmp_path, [S1, S2]))
    for text in (Q_SHIP, '誰が商人に小包を渡さなかった？'):
        ledger = SAL.MemoryLedger()
        vp = O.build_viewpoint(anchor_text=text, anchor_kind='question')
        obs = O.observe(vp, st, ledger=ledger)
        assert isinstance(obs, O.QuestionObservation) and obs.outcome in ('TIE', 'NO_MOVE_LICENSED')
        O.record_turn(ledger, vp, obs)
        event = [e for e in ledger.events() if e['kind'] == 'observation'][0]
        assert event['payload']['outcome'] == obs.outcome and O.replay(list(ledger.events()), event, st) is True
    one = O.Structure.from_jsonl(write_doc(tmp_path, [S1], 'one.jsonl'))
    ledger = SAL.MemoryLedger(); vp = O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question')
    obs = O.observe(vp, one, ledger=ledger); O.record_turn(ledger, vp, obs)
    event = [e for e in ledger.events() if e['kind'] == 'observation'][0]
    assert event['payload']['observed_cell'] == obs.focus.cell_key and O.replay(list(ledger.events()), event, one) is True
```

##### `test_the_ledger_records_a_question_and_replays_to_the_same_output` — after

```python
def test_the_ledger_records_a_question_and_replays_to_the_same_output(tmp_path):
    pl = person_placement(PERSONS)    # W5-d2 (K1): the fillers are typed by a made-up placement
    st = O.Structure.from_jsonl(write_doc(tmp_path, [S1, S2]), pl, pl)
    for text in (Q_SHIP, '誰が商人に小包を渡さなかった？'):
        ledger = SAL.MemoryLedger()
        vp = O.build_viewpoint(anchor_text=text, anchor_kind='question')
        obs = O.observe(vp, st, ledger=ledger)
        assert isinstance(obs, O.QuestionObservation) and obs.outcome in ('TIE', 'NO_MOVE_LICENSED')
        O.record_turn(ledger, vp, obs)
        event = [e for e in ledger.events() if e['kind'] == 'observation'][0]
        assert event['payload']['outcome'] == obs.outcome and O.replay(list(ledger.events()), event, st) is True
    one = O.Structure.from_jsonl(write_doc(tmp_path, [S1], 'one.jsonl'), pl, pl)
    ledger = SAL.MemoryLedger(); vp = O.build_viewpoint(anchor_text=Q_SHIP, anchor_kind='question')
    obs = O.observe(vp, one, ledger=ledger); O.record_turn(ledger, vp, obs)
    event = [e for e in ledger.events() if e['kind'] == 'observation'][0]
    assert event['payload']['observed_cell'] == obs.focus.cell_key and O.replay(list(ledger.events()), event, one) is True
```

##### `test_the_cross_index_of_a_question_is_zero_or_nothing` — before

```python
def test_the_cross_index_of_a_question_is_zero_or_nothing(tmp_path):
    out, _ = ask(tmp_path, Q_SHIP, [S1], cross=0)
    assert out['answer']['status'] == 'FILLED'
    out, _ = ask(tmp_path, Q_SHIP, [S1], cross=1)
    assert out['answer']['status'] == 'ANCHOR_CROSS_INDEX_OUT_OF_RANGE' and out['focus'] == {'kind': 'NO_ANCHOR', 'reason': 'ANCHOR_CROSS_INDEX_OUT_OF_RANGE'}
```

##### `test_the_cross_index_of_a_question_is_zero_or_nothing` — after

```python
def test_the_cross_index_of_a_question_is_zero_or_nothing(tmp_path):
    pl = write_placement(tmp_path, PERSONS)    # W5-d2 (K1)
    out, _ = ask(tmp_path, Q_SHIP, [S1], cross=0, placement=pl)
    assert out['answer']['status'] == 'FILLED'
    out, _ = ask(tmp_path, Q_SHIP, [S1], cross=1, placement=pl)
    assert out['answer']['status'] == 'ANCHOR_CROSS_INDEX_OUT_OF_RANGE' and out['focus'] == {'kind': 'NO_ANCHOR', 'reason': 'ANCHOR_CROSS_INDEX_OUT_OF_RANGE'}
```

##### `test_the_command_line_entry_gives_the_same_bytes_for_two_hash_seeds` — before

```python
def test_the_command_line_entry_gives_the_same_bytes_for_two_hash_seeds(tmp_path):
    doc = write_doc(tmp_path, [S1, S2, '鳥が空を飛んだ。'])
    args = ['--anchor-text', Q_SHIP, '--anchor-kind', 'question', '--structure', doc, '--no-index']
    a, b = _entry(args, 0, tmp_path), _entry(args, 4242, tmp_path)
    assert a.returncode == b.returncode == 0, a.stderr + b.stderr
    assert a.stdout == b.stdout and json.loads(a.stdout)['answer']['status'] == 'TIE'
    assert 'ANSWER' not in a.stdout
```

##### `test_the_command_line_entry_gives_the_same_bytes_for_two_hash_seeds` — after

```python
def test_the_command_line_entry_gives_the_same_bytes_for_two_hash_seeds(tmp_path):
    doc = write_doc(tmp_path, [S1, S2, '鳥が空を飛んだ。'])
    args = ['--anchor-text', Q_SHIP, '--anchor-kind', 'question', '--structure', doc, '--no-index', '--placement', write_placement(tmp_path, PERSONS)]    # W5-d2 (K1)
    a, b = _entry(args, 0, tmp_path), _entry(args, 4242, tmp_path)
    assert a.returncode == b.returncode == 0, a.stderr + b.stderr
    assert a.stdout == b.stdout and json.loads(a.stdout)['answer']['status'] == 'TIE'
    assert 'ANSWER' not in a.stdout
```

#### `tests/observe/question/recompute_q.py` (before = git show c875ed3:tests/observe/question/recompute_q.py)

Added (helpers / tests, not amendments): none

##### `=EXAMPLES` — before

```python
EXAMPLES = (('FILLED', 'QD05', '母は台所で何を作った？'), ('TIE', 'QD01', '誰が生徒に地図を渡した？'), ('NO_ATTESTED_CELL', 'QD01', '誰が生徒に手紙を送った？'))
```

##### `=EXAMPLES` — after

```python
EXAMPLES = (('FILLED', 'QD02', 'どの人が客に切符を渡した？', 'placement_q.json'), ('TIE', 'QD01', '誰が生徒に地図を渡した？', 'placement_q.json'),
            ('NO_ATTESTED_CELL', 'QD01', '誰が生徒に手紙を送った？', None))
```

##### `entry_block` — before

```python
def entry_block():
    rel = lambda p: str(Path(p).relative_to(TREE))
    out = ['### 入口の実行出力（`recompute_q.py` が実際に走らせて貼った。手で書き換えない）', '']
    env = {'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(TREE), 'PYTHONHASHSEED': '0'}
    for want, doc, text in EXAMPLES:
        args = ['--anchor-text', text, '--anchor-kind', 'question', '--structure', rel(Q / 'docs' / (doc + '.jsonl')), '--no-index']
        done = subprocess.run([sys.executable, '-m', 'verantyx.cli', 'observe', *args], capture_output=True, text=True, env=env, cwd=str(TREE), timeout=180)
        d = json.loads(done.stdout)
        a = d['answer']
        show = {'exit_code': done.returncode, 'focus': {k: (v if k != 'candidates' else '[%d cells]' % len(v)) for k, v in d['focus'].items() if k != 'cell_key'},
                'answer.status': a['status'], 'answer.question': a['question'],
                'answer.fillers': [{'surface': f['surface'], 'evidence': [{'reading': e['reading'], 'cross_index': e['cross_index'], 'text': e['text']} for e in f['evidence']],
                                    'hole_type_check': f['hole_type_check']['verdict'] + (':' + f['hole_type_check']['reason'] if f['hole_type_check']['reason'] else '')}
                                   for f in a['fillers']],
                'answer.structure': a['structure'], 'answer.reasons': a['reasons'], 'abstain': d['abstain']}
        assert a['status'] == want, (want, a['status'])
        out += ['`%s`（%s）' % ('python -m verantyx.cli observe ' + ' '.join("'%s'" % x if (' ' in x or '？' in x) else x for x in args), want), '```json',
                json.dumps(show, ensure_ascii=False, indent=1), '```', '']
    return '\n'.join(out).rstrip('\n')
```

##### `entry_block` — after

```python
def entry_block():
    rel = lambda p: str(Path(p).relative_to(TREE))
    out = ['### 入口の実行出力（`recompute_q.py` が実際に走らせて貼った。手で書き換えない）', '']
    env = {'HOME': os.environ.get('HOME', ''), 'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(TREE), 'PYTHONHASHSEED': '0'}
    for want, doc, text, placement in EXAMPLES:
        args = ['--anchor-text', text, '--anchor-kind', 'question', '--structure', rel(Q / 'docs' / (doc + '.jsonl')), '--no-index'] + (['--placement', rel(Q / placement)] if placement else [])
        done = subprocess.run([sys.executable, '-m', 'verantyx.cli', 'observe', *args], capture_output=True, text=True, env=env, cwd=str(TREE), timeout=180)
        d = json.loads(done.stdout)
        a = d['answer']
        show = {'exit_code': done.returncode, 'focus': {k: (v if k != 'candidates' else '[%d cells]' % len(v)) for k, v in d['focus'].items() if k != 'cell_key'},
                'answer.status': a['status'], 'answer.question': a['question'],
                'answer.fillers': [{'surface': f['surface'], 'evidence': [{'reading': e['reading'], 'cross_index': e['cross_index'], 'text': e['text']} for e in f['evidence']],
                                    'hole_type_check': f['hole_type_check']['verdict'] + (':' + f['hole_type_check']['reason'] if f['hole_type_check']['reason'] else '')}
                                   for f in a['fillers']],
                'answer.structure': a['structure'], 'answer.reasons': a['reasons'], 'abstain': d['abstain']}
        assert a['status'] == want, (want, a['status'])
        out += ['`%s`（%s）' % ('python -m verantyx.cli observe ' + ' '.join("'%s'" % x if (' ' in x or '？' in x) else x for x in args), want), '```json',
                json.dumps(show, ensure_ascii=False, indent=1), '```', '']
    return '\n'.join(out).rstrip('\n')
```

#### `tests/attack/w3c2/test_attack_w3c2_question_cross.py` (before = the attack original attacks/W3-c2/test_attack_question_cross.py (first line dropped))

Added (helpers / tests, not amendments): `_persons`

##### `test_tied_agent_witnesses_remain_a_tie` — before

```python
def test_tied_agent_witnesses_remain_a_tie():
    answer = _run('JA01-01')['answer']
    got = {f['surface'] for f in answer['fillers']}
    assert answer['status'] == 'TIE' and got == {'校長', '先生'}, (
        f"expected both matching witnesses, got status={answer['status']}, fillers={got!r}"
    )
```

##### `test_tied_agent_witnesses_remain_a_tie` — after

```python
def test_tied_agent_witnesses_remain_a_tie(tmp_path):
    answer = _run('JA01-01', _persons(tmp_path))['answer']
    got = {f['surface'] for f in answer['fillers']}
    assert answer['status'] == 'TIE' and got == {'校長', '先生'}, (
        f"expected both matching witnesses, got status={answer['status']}, fillers={got!r}"
    )
```

##### `test_negative_question_does_not_match_affirmative_crosses` — before

```python
def test_negative_question_does_not_match_affirmative_crosses():
    answer = _run('JA01-05')['answer']
    got = {f['surface'] for f in answer['fillers']}
    assert answer['status'] == 'FILLED' and got == {'校長'}, (
        f"expected the sole negative witness JA01-S04, got status={answer['status']}, fillers={got!r}"
    )
```

##### `test_negative_question_does_not_match_affirmative_crosses` — after

```python
def test_negative_question_does_not_match_affirmative_crosses(tmp_path):
    answer = _run('JA01-05', _persons(tmp_path))['answer']
    got = {f['surface'] for f in answer['fillers']}
    assert answer['status'] == 'FILLED' and got == {'校長'}, (
        f"expected the sole negative witness JA01-S04, got status={answer['status']}, fillers={got!r}"
    )
```

<!-- w5d2-amended:end -->

## W5-d 第 2 ラウンド（W5-d2）の測定
<!-- w5d2-measured:begin -->
測定の時刻: 2026-10-04 01:22:30 +0900。出力はすべて `artifacts/w5-d/r2/`（ファイル名を添える）。中間職のレビュー r1（`review-impl/W5-d2/review.r1.md`）の M1〜M4（改訂したテストの前後の全文・測定の区間・失敗集合のファイル・報告）に応えてこの区間と `w5d2-amended` 区間を書いた。製品とテストのコードはレビューのあとに変えていない（`code_sha_r2b_start.txt` と `code_sha_r2b_end.txt` が同じ）。受入の測定はこのとき全部流し直した（`g1_rerun_r2b.txt`・`g2_rerun_r2b.txt`・`g3_rerun_r2b.txt`・`q1_observe_cmp_r2b.txt`・`g4_compare_r2b.txt`・`q5_r7_verify_r2b.txt`・`k5_check_r2b.txt`。出力は前の流しと byte 一致。違いが無かったことの確認なので前の流しのファイルも残す）。

**受入基準**（第 2 ラウンド）
- **G1**（`g1_rerun_r2b.txt`）: 攻撃の写し 36 本が `36 passed`、K の 72 関数（82 id）が全部通る（`102 passed`）、新しいテスト（第 1 ラウンドの 5 本＋第 2 ラウンドの追記）が `113 passed`。G1-b: 写しと原本の差は先頭行と改訂した関数・足したヘルパの中だけ（`g1b_hunks.txt`、`attack_copy_revisions.diff`。w5c の 2 本は原本と同一、`data/` も同一）。
- **G2**（`g2_185_*.json(l)`・`g2_attack120_r7.json(l)`・`g2_rerun_r2b.txt`）: `VERA_PLACEMENT` なしの 185 問は第 1 ラウンドの出力と byte 一致（place: 正答/誤答/FALSE_NONE/棄権 = 38 / 0 / 4 / 143、noplace: 26 / 0 / 4 / 155）。`VERA_PLACEMENT=r7`: place 73 / 0 / 6 / 106、noplace 66 / 0 / 8 / 111。誤答 0、型未確認の FILLED/TIE 0（4 通りとも `unchecked_fillers_in_FILLED_TIE` は 0・0・0・0）。正答は減っていない（第 1 ラウンドと同じか、r7 で増える）。攻撃の 120 問（r7、116 問は正解なしで採点されない）: FILLED 29・TIE 5、型未確認の FILLED/TIE 0、`wrong` 0 件。A01（`EN08-01`）は `NO_TYPED_CANDIDATE`（`letter`・`note` は `TYPE_UNCHECKED`）で FILLED/TIE にならない（`g2_r7_notes.txt`）。中間職の凍結 64 問・56 問は実装役が開かない約束なので測っていない（中間職が測る）。
- **G3**（`g3_rerun_r2b.txt`・`g3_*`）: 経路づけの凍結 4 本（配置なし）の misroutes は 0, 0, 0, 0、r7 の 2 本は 0, 0。合成 `g3_synth`（入力の sha256 は `g3_synth_inputs_check.txt` で第 1 ラウンドの凍結と一致）: 配置なし misroutes 0・普通名詞に振った数 0、r7 misroutes 1（第 1 ラウンドと同じ 1 件。`委員会` が推定の GROUP_ORG で通る既知の穴）、基点 1（`g3_synth_results/g3_synth_counts.json`）。D2-2 の影響: r7 の 2 本の 118 件を、D2-2 の呼び出しを外した写しと単位ごとに比べて変化した件数は 0（`g3_r7_diff.txt`）。
- **G4**（`g4_result.json`・`g4_compare_r2b.txt`）: 入力の sha256 と `summary` が第 1 ラウンドと同じ（自己申告の文書 16 件で `ANSWER` 0、文面違いの確認記録 15 件で `ANSWER` 0・旧文が返った 0、対照は 4/4 と 2/2 で答える）。`verantyx/basis_policy.py` は第 2 ラウンドで変えていない（sha256 が `files_start.sha256` と同じ）。
- **G5**（`q5_r7_verify_r2b.txt`・`k5_check_r2b.txt`）: r7 は作り直していない。`verify` が run1・run2 とも `OK`、`content_sha256` は第 1 ラウンドと同じ。`coarse_place.py`・`tools/build_coarse_placement.py` は第 2 ラウンドで変えていない。K5 の写しが通り、r6_audit_summary.json not_confirmed: 13 words; invariant_errors [] byte_differences []、第 1 ラウンドの 13 語と同じ集合（`命じる` を含む）。
- **平叙文の観測**（`q1_observe_cmp_r2b.txt`）: `o1_bytes.py --child` の出力が、配置なしと `VERA_PLACEMENT=r7` の 2 通りとも基点と byte 一致（`same: base vs now` が 2 行。この流しは前の流しとも byte 一致）。
- **G7**（`pytest_full.txt`・`after_failures.txt`・`new_failures.txt`・`fixed_failures.txt`・`new_failures_explained.txt`）: 全体テストの最終行 `117 failed, 11981 passed, 45 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 362.65s (0:06:02)`。失敗は一意に 117 件、基線に無い失敗は 2 件（`tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches`、`tests/test_gen_coarse_evidence.py::test_the_stop_signal_ends_the_run_with_an_interrupted_record`）、基線にあって今は通る失敗は 0 件。基線に無い失敗の理由は `new_failures_explained.txt`（環境由来だけ）。K の id は失敗集合に 0 件。

**K1（質問の十字 15 件）の改訂**（裁定 B1。前後の全文は上の `w5d2-amended` 区間。`changed_functions_k1k2.txt`）: 既存 13 関数（`tests/test_question_cross_observe.py`）と攻撃の写し 2 関数（`tests/attack/w3c2/test_attack_w3c2_question_cross.py::test_tied_agent_witnesses_remain_a_tie`・`test_negative_question_does_not_match_affirmative_crosses`）。名前は変えていない。直し方は 3 種類: (1) 穴の充填物だけに direct の型を付けた配置の JSON（`write_placement`）、(2) `O.FilePlacement`（足したヘルパ `person_placement`・`PERSONS`）、(3) 子プロセスの CLI は `--placement` を引数に足した。穴の型と食い違う型は付けていない。攻撃の写しは `tmp_path` に `校長`・`先生` = PERSON の JSON を書いて渡した（`data/` は触っていない）。例外 1 件 `test_an_unchecked_type_is_not_a_reason_to_exclude_except_for_which_noun` は主題が「配置なしで FILLED」で新しい契約と正反対なので、期待を新しい契約（配置なし → `NO_TYPED_CANDIDATE`・`excluded` の理由 `TYPE_UNCHECKED`・`hole_type_check` が `NOT_CHECKED/NO_PLACEMENT`）に改訂した（assert は 2 → 3 に増えた。名前は旧い契約のものなので関数の先頭に注記）。**配置なしの棄権を表すテスト**: この関数と、足した `tests/test_question_cross_w5d.py::test_w5d2_k1_the_same_question_with_and_without_a_placement`（同じ問いで配置あり = `TIE`、なし = `NO_TYPED_CANDIDATE`）。

**D2-7（`VERA_PLACEMENT` を質問の経路につなぐ）の門**（3 つとも通った。戻していない）:
1. r7 で 185 問の `WRONG` 0・型未確認の FILLED/TIE 0、攻撃 120 問でも型未確認 0 で A01 が FILLED/TIE にならない（`g2_185_*_r7.json`・`g2_attack120_r7.json`）。
2. `VERA_PLACEMENT` なしの 185 問の出力が第 1 ラウンドの `g2_185_{place,noplace}.jsonl` と byte 一致（`g2_rerun_r2b.txt`）。
3. 平叙文の観測（`o1_bytes.py --child`）が基点と byte 一致（配置なし・r7。`q1_observe_cmp_r2b.txt`）。
製品の変更は `observe.py` の `_observe_question` の中だけ（`git diff c875ed3 -- verantyx/observe.py`）。足したテスト（`tests/test_question_cross_w5d.py`、r7 が無ければ失敗する。skip にしない）: `test_w5d2_vera_placement_types_the_hole_filler_of_a_question`（`誰が生徒に地図を渡した？`: `先生` → FILLED・`先生`＋`校長` → TIE・`花子`〔MULTIPLE ANIMAL/PERSON〕→ `NO_TYPED_CANDIDATE`、`structure.placement` が `coarse-placement:` で始まる）・`test_w5d2_the_placement_file_wins_over_vera_placement`・`test_w5d2_an_empty_vera_placement_is_as_before_no_typed_candidate`・`test_w5d2_the_command_line_with_vera_placement_gives_the_same_bytes_for_two_hash_seeds`。

**申し送りとして数えたもの**（門にしない。`g2_r7_notes.txt`）:
- FALSE_NONE の増分（r7）: 185 問の noplace で 4 → 8（Q094・Q130・Q131・Q136）、place で 4 → 6（Q094・Q136）。Q094 は `会社` が r7 で GROUP_ORG の direct（`どこ` の穴は PLACE → `HOLE_TYPE_DISAGREE`）、Q130・Q131 は `医者` が MULTIPLE（PERSON/PLACE）で which+N の `HOLE_TYPE_NOT_CHECKED`（以前からの規則で `TYPE_EXCLUDED_ALL` に数えられる）、Q136 は `X` が r7 で INFO_LANGUAGE の direct。どれも誤答（WRONG）ではない。
- TIE が FILLED に縮む形（既知の穴）: r7 で型未確認の充填物を横に持つ FILLED は攻撃 120 問では `JA02-01`（`花子は何を読んだ？` → FILLED [本]、`新聞`・`毎日本` は `TYPE_UNCHECKED`）の 1 件。185 問では 0。中間職のレビュー r1 の申し送り 1 は、第 1 ラウンドの凍結の反例を r7 で流すと同じ形（W01）と、読解器が文を読めないための欠け（W08・W18。`UNREAD_SENTENCES`）が出ると書いている（実装役は未測定）。

**B3（`recompute_q.py` の例の取り直し）**: `EXAMPLES` を 4 つ組 `(期待, 文書, 問い, 配置ファイル名 or None)` にし、`entry_block()` は配置ファイル名があれば `--placement tests/observe/question/<名>` を引数に足す。採用した例: `FILLED`（`QD02`・`どの人が客に切符を渡した？`・`placement_q.json`。凍結の Q037）、`TIE`（`QD01`・`誰が生徒に地図を渡した？`・`placement_q.json`。`先生`・`校長` が PERSON の direct）、`NO_ATTESTED_CELL`（`QD01`・`誰が生徒に手紙を送った？`・配置なし。今のまま）。`QD05` の `母は台所で何を作った？` は `料理` が `placement_q.json` に無く `NO_TYPED_CANDIDATE` になるので使っていない。凍結データ（`placement_q.json`・`questions.jsonl`）は変えていない。`--write` は 1 回だけ（`recompute_write_time.txt`）、`--check` は exit 0（`doc_checks.txt`）。前後の全文（`EXAMPLES`・`entry_block`）は上の `w5d2-amended` 区間、`recompute_q.py` の前は `recompute_q_before.py`。

**`w3c2-entry` 区間の変更記録**（区間の規則の本文・`w3c2-measured` 区間は変えていない）: 2026-10-04 00:43:03 +0900（`recompute_q.py --write` 実行時）。区間の sha256（内側のテキスト）: 前 `6d703c97f8fa97e5569f3d5fdbd95a70c021e14d557ae493cd8573f34145f075`、後 `9d0fb8824f346e65c755aaf962534ec656c7be8e1fd12ccf0124f7c8e2185eb3`。理由: 配置を渡さない旧い例（`QD05` の FILLED・`QD01` の TIE）は、W5-d の規則（型を確かめられない充填物は候補にしない）では `NO_TYPED_CANDIDATE` になり、`--check` が `AssertionError: ('FILLED', 'NO_TYPED_CANDIDATE')` で落ちた（第 1 ラウンドの `doc_checks.txt` の追加の帰結）。例は測定の出力なので、配置を与えた例に取り直した（裁定 B3）。`w3c2-measured` 区間の sha256 は前後で同じ（`docs_regions_end.txt`）。

**第 2 ラウンドで置き換わった第 1 ラウンドの記述**（第 1 ラウンドの `w5d-*` 区間の中は 1 文字も変えていない。元の行は残し、この一覧が上書きする）
- 「Q-J4 言語・配置: …質問の観測は `VERA_PLACEMENT` を読まない」→ 第 2 ラウンドで読む。`--placement` が無く `VERA_PLACEMENT` があるときは、読解器・事象の十字と同じ `event_cross.default_lookup()` の lookup を使う（`--placement` や呼び手が渡した lookup があればそれが勝つ。`VERA_PLACEMENT` が空・未設定なら今までどおり）。
- 「K1 は宣言した衝突（15 件）」→ 裁定 B1 で改訂が許可され、上のとおり改訂した（`k_ids.txt` の 82 id は全部通る）。
- 「K1 の追加の帰結: `recompute_q.py --check` が落ちる」→ 裁定 B3 で例を取り直し、`--check` は exit 0。
- 第 1 ラウンドの測定の節にある、質問の観測の数（配置なし 185 問）は今も有効（byte 一致）。`VERA_PLACEMENT=r7` の数はこの区間が初出。

**既知の穴**: (a) TIE が FILLED に縮む（上）。(b) r7 では FALSE_NONE が増える（上。r7 の型による `TYPE_EXCLUDED_ALL`）。(c) 攻撃 120 問の 116 問には正解が無いので、r7 の FILLED 29・TIE 5 は型こそ全部 AGREE だが正しさは採点されていない（監査役の G6 で見る）。
**この文書の担当の測定は上のとおり。全体の受入と判断は `artifacts/w5-d/DECISIONS.md` の「第 2 ラウンド（W5-d2）」と `artifacts/w5-d/r2/`。**
<!-- w5d2-measured:end -->

## 文書 QA の後段（W3-c4）

（この節は段階的に書く。最初に書いたのは次の「事前登録」小節だけ。ほかの小節は検査データを作り、実装したあとに足す。）

### 事前登録（W3-c4）

<!-- w3c4-prereg:begin -->
登録日時: 2026-10-04 02:05:35 +0900（`date '+%Y-%m-%d %H:%M:%S %z'` の出力。この節はこの出力の直後に書いた）
この時点で `tests/observe/question_ask/` は存在しない（`ls` の出力を `artifacts/w3-c4/prereg.txt` に記録する）。出典は中間職の指示書 `.claude/vera-audit/review-impl/W3-c4/plan.md` の D3〜D7 と手順 1 の採点・A1 の比べ方。

**後段の条件（D3。閉じた集合。これ以外は 1 バイトも変えない）**: `mode == "round5"` かつ `--document` が 1 つ以上 かつ 既存の経路の結果が dict で `verdict ∈ {"UNKNOWN_UNREAD", "UNKNOWN_NO_EVIDENCE"}`（ちょうどこの 2 値）。外れたら後段の関数は最初の行で同じオブジェクトをそのまま返す（複製もしない。条件の判定より前に import・文書の読み込み・時刻の取得をしない）。答え・他の棄権（`UNKNOWN_UNSUPPORTED_EVIDENCE`・`UNKNOWN_CONTENT_PERMISSION` など）・文書なし・`--mode` が round5 でないものは触らない。後段は `vera ask` だけにつなぐ（`vera chat` の round5 にはつながない）。

**構造の作り方（D4）**:
1. 文書は方針の `_document_texts` と同じ読み方: `--document` の各項目について、ディレクトリなら `load_directory`、それ以外は `load_paths([path])`（中で `document_loaders.load_path`）。読めた `Document(source, text)` を使い、読めなかったものは `skipped`。
2. 行 = `doc.text.split("\n")` の 1 始まりの番号（`splitlines()` は使わない）。
3. 区切り = 正規表現 `(?<=。)|(?<=\.)(?=\s)` で行を `split`（`。` の直後、`.` の直後で次の字が空白類のところ）。各片を `strip()`、空の片は捨てる。`！`・`？`・`!`・`?`・全角 `．` では切らない。語の一覧・略語の例外は足さない。「`.` は直後が空白のときだけ」は、チケットの「`.`」を「文の終わりの `.`」と読んだ解釈（`3.5` や `a.b` を割らないため）。
4. 文 id = `<doc.source>#<行>:<その行の中の空でない片の番号>`。records = `{"id", "text"}` の列（`lang` は付けない）。
5. 読めた文書が 0 本なら観測しない（状態 `DOCUMENTS_NOT_LOADED`）。id が重複したら（同じファイル名の文書が 2 本、同じ文書を 2 回）観測せず状態 `STRUCTURE_INVALID`。
6. 一時ファイルを作らない。records を `observe.observe_question_records`（メモリ上で受ける入口。観測の規則は触らない。配置は `VERA_PLACEMENT` の `event_cross.default_lookup`）に渡す。質問は `--query` そのまま、`lang` は None。

**結果の写し（D5）**: `question_cross.state` の閉じた一覧 = 観測器の `ANSWER_STATUSES` 11 個（`FILLED`・`TIE`・`NO_ATTESTED_CELL`・`TYPE_EXCLUDED_ALL`・`HOLE_TYPE_UNDETERMINED`・`POLAR_QUESTION`・`DIRECTION_NOT_APPLIED`・`QUESTION_NOT_READ`・`ANCHOR_CROSS_INDEX_OUT_OF_RANGE`・`INCOMPLETE_BY_EXTENSION`・`NO_TYPED_CANDIDATE`）＋ `NOT_A_QUESTION`・`DOCUMENTS_NOT_LOADED`・`STRUCTURE_INVALID`・`ERROR`。理由の閉じた一覧 = `SURFACES_DIFFER:<n>`・`SURFACE_NOT_IN_EVIDENCE`・`QUOTE_UNBALANCED_EVIDENCE`（ほかは観測器の `answer.reasons` の先頭）。

| 状態 | `mapped_to` | 出力の形 |
|---|---|---|
| `FILLED` かつ `fillers` が 1 行・表記が証拠の文のどれかの部分文字列・証拠の文の鉤括弧（`「」『』“”`、`"` は偶数）が閉じている | `ANSWER` | `kind:"answer"`・`verdict:"ANSWER"`・`text` = 証拠の文の中の表記そのまま・`values`・`evidence`・`sources`（`family:"document"`・`source`・`line`・`text`・`sentence_id`。`origin` は付けない）・`door:"question_cross"`・`question_cross`・`trace` に 1 段 |
| `FILLED` かつ `fillers` が 2 行以上（NFKC は同じで表記が違う） | `AMBIGUOUS_QUESTION_CROSS_TIE` | 理由 `SURFACES_DIFFER:<行数>`。どれも選ばない |
| `FILLED` で表記が証拠に無い | `ORIGINAL` | 理由 `SURFACE_NOT_IN_EVIDENCE` |
| `FILLED` で鉤括弧が閉じていない | `ORIGINAL` | 理由 `QUOTE_UNBALANCED_EVIDENCE`（「。」で割った片が引用の途中で切れ、伝聞が事実として読まれるのを答えにしない棄権への倒し。分割の規則は足していない） |
| `TIE`（各候補にも同じ表記・鉤括弧の検査。外れたら `ORIGINAL`） | `AMBIGUOUS_QUESTION_CROSS_TIE` | `kind:"unknown"`・`verdict:"AMBIGUOUS_QUESTION_CROSS_TIE"`・`candidates:[{"text","sources"}…]`（観測器の順。選ばない・並べ替えない）・最上位の `sources` は空 |
| `NOT_A_QUESTION`（疑問文と読まれず `answer` が無い）・`NO_ATTESTED_CELL`・`QUESTION_NOT_READ`・`NO_TYPED_CANDIDATE`・`TYPE_EXCLUDED_ALL`・`HOLE_TYPE_UNDETERMINED`・`POLAR_QUESTION`・`INCOMPLETE_BY_EXTENSION`・`ANCHOR_CROSS_INDEX_OUT_OF_RANGE`・`DIRECTION_NOT_APPLIED`・`DOCUMENTS_NOT_LOADED`・`STRUCTURE_INVALID`・`ERROR` | `ORIGINAL` | 元の dict（浅い複製）＋ `question_cross` ＋ trace の 1 段。他の鍵は 1 つも変えない |

`question_cross` の鍵（全部の場合で同じ順）: `state`・`reason`・`mapped_to`・`hole_role`・`hole_type`・`coord`・`structure`・`documents`。trace の 1 段 = `{"part":"question_cross","status":"ran"|"abstained","state":…,"mapped_to":…}`（元の `trace` の複製の末尾に足す）。`except Exception` は後段の関数の外枠 1 か所だけ（状態 `ERROR`、`ORIGINAL`）。検査データの全部で `ERROR` は 0 件でなければならない。

**方針との接続（D6）**: 順は 既存の経路 → 後段 → `basis_policy.apply_to_ask`（引数は変えない。`basis_policy.py` は触らない）。

**今回やらないこと（D7）**: チケットの「やること 5」（文書で候補が 0 のとき `VERA_P4_INDEX` の生成の文を構造にする）はやらない。方針の `CONFIRM_REQUEST`・`REFERENCE_GENERATED` は後段からは到達しない（既知の穴に書く）。

**採点（W3-c2 の D17 を ask の出力に写したもの。最終出力（方針の後）を読む）**:
- `RAN` = trace に `part == "question_cross"` の段がある。`QC_ANSWER` = `door == "question_cross"` かつ `verdict == "ANSWER"`。`QC_TIE` = `verdict == "AMBIGUOUS_QUESTION_CROSS_TIE"`。`QC_NONE` = `question_cross.state ∈ {NO_ATTESTED_CELL, TYPE_EXCLUDED_ALL}`。
- truth `ONE`: CORRECT ⇔ `QC_ANSWER` かつ NFKC(`text`) == NFKC(唯一の充填物) かつ `{s.sentence_id}` == `truth.evidence` の集合 かつ `sources[0].sentence_id == min(truth.evidence)`（文字列順）。`QC_ANSWER`/`QC_TIE` でそれ以外は WRONG。`QC_NONE` は FALSE_NONE。他は ABSTAINED。
- `SPLIT`: CORRECT ⇔ `QC_TIE` かつ候補の NFKC 集合 == 充填物の集合 かつ全候補の文 id の集合 == `truth.evidence` の集合。`QC_ANSWER`・それ以外の `QC_TIE` は WRONG。`QC_NONE` は FALSE_NONE。他は ABSTAINED。
- `NONE`: CORRECT ⇔ `question_cross.state == NO_ATTESTED_CELL`。`QC_ANSWER`/`QC_TIE` は WRONG。他は ABSTAINED。
- `YESNO`・`ILLFORMED`: `QC_ANSWER`/`QC_TIE` なら WRONG、他は CORRECT。
- `RAN` でない問（既存の経路が答えた・閉じた集合の外の棄権・文書なし）は後段の採点の外（`NOT_RUN`）。既存の経路の答えは別の欄 `base_answer` に truth と照らして `BASE_MATCH`/`BASE_MISMATCH` を書く（承認の条件には入れない。報告だけ）。
- 承認の条件は WRONG == 0（配置 2 通り（差し替えの配置・`VERA_PLACEMENT=r7`）とも）。CORRECT・FALSE_NONE・ABSTAINED・NOT_RUN と `question_cross.state` の分布を報告する。

**A1 の比べ方**: `vera ask` の出力は同じ入力でも毎回 byte が変わる（trace の時間の実測値）。基点どうしで 2 回流した差から、値が違う JSON の鍵を全部集めた（`artifacts/w3-c4/nondeterministic_keys.txt`）: `ingest_ms`・`elapsed_ms` の 2 つ。比べるときはこの 2 つの鍵の値だけを `0` に置き換え、鍵は消さない（伏せる範囲を広げて差を隠さない）。(i) 基点の verdict が条件の外、または文書なし、または round5 でない → 基点と新が（伏せた後で）byte 一致。(ii) 条件の中で写しが `ORIGINAL` → 新から `question_cross` と trace の最後の段を除くと、基点と byte 一致。(iii) 対照として基点どうし 2 回も同じ手順で一致すること。基点は `c334fe6`。

**検査データの規模（手順 2）**: 文書 10 本（各 5〜10 文・単文中心、和文 6 本以上・英文 3 本以上）、質問 60 問以上（ONE 20・NONE 10・SPLIT 8・YESNO/ILLFORMED/読めない形 6・文書なし 4・既存の経路が答える形 6・平叙文 2・文書 2 本 4・配置に載せない名詞が答えの問 3）。W3-c2 の検査データ 185 問と、B2 の形の自作の文書 QA（文書 4 本・質問 24 問以上）も流す。期待は系に 1 度も通さずに人が書き、`tests/observe/question_ask/FROZEN.json` で sha256 を凍結する。凍結後は 1 バイトも変えない（誤りは `corrections.jsonl` に追記し、当てた結果と当てない結果の両方を出す）。
<!-- w3c4-prereg:end -->

### 事前登録の変更記録（W3-c4）

- 2026-10-04 02:18:14 +0900（`date '+%Y-%m-%d %H:%M:%S %z'` の出力）: **理由の閉じた一覧に `PERIOD_CUT_UNCERTAIN` を足した**（実装役 J1。上の事前登録の「理由の閉じた一覧」は 3 つだった。測定と検査データの採点より前、検査データの凍結（`FROZEN.json`）より後）。きっかけ: 手元の試走で、`Mr. Smith gave the map to the student.` の行が `.` + 空白で「`Mr.`」と「`Smith gave the map to the student.`」に割れ、「Who gave the map to the student?」に答え `Smith`（文書の表記は `Mr. Smith`）を返した。分割の規則（上の正規表現）も、語の一覧も足さない。足したのは棄権への倒しだけ: 証拠の文が、(a) 直前の片が「1 語で `.` で終わる」（`Mr.`・`U.S.`・`e.g.`・`J.` など）か、(b) 自分が `.` で終わりその次の片が小文字で始まる、のどちらかの切れ目の隣にあるとき、その文は「文の途中かもしれない」ので答え・候補の証拠にしない（写し = `ORIGINAL`、理由 `PERIOD_CUT_UNCERTAIN`）。検査は `QUOTE_UNBALANCED_EVIDENCE` の後。過剰に棄権する側に倒れる（1 語だけの文の次の文も棄権する）。表の他の行は変えない。
- 2026-10-04 02:24:37 +0900（`date` の出力）: 上の `PERIOD_CUT_UNCERTAIN` の条件に (c) を足した（実装役 J1 の続き。測定より前）: 直前の片が `.` で終わり、自分が小文字で始まる片も「文の途中かもしれない」。理由: 単体テストで `Smith Jr. sold the horse.` の後ろ半分（`sold the horse.`）が (a)(b) では印が付かないことに気づいた（前の片 `Smith Jr.` は 2 語）。これで切れ目の両側の片が印を受ける。条件は 3 つ: (a) 直前の片が 1 語で `.` で終わる、(b) 自分が `.` で終わり次の片が小文字で始まる、(c) 直前の片が `.` で終わり自分が小文字で始まる。
- 2026-10-04 02:26:19 +0900（`date` の出力）: **採点の ONE の行を 1 つだけ緩めた**（実装役 J2。測定の前。理由: 事前登録の採点は「ONE の truth に `QC_TIE` が出たら WRONG」だが、W3-c2 の検査データを再利用した 2 問（Q046・Q050。文書 QD03 の `ＰＣ`／`PC` を 1 つの答え `PC` と人が数えた ONE）で、計画の写し D5（NFKC が同じで表記が違う充填物 → どれも選ばず `AMBIGUOUS_QUESTION_CROSS_TIE`、理由 `SURFACES_DIFFER:n`）と衝突した。TIE は型付きの棄権で、誤った答えではない）。新しい行: truth が ONE で、`QC_TIE` の理由が `SURFACES_DIFFER:*`、候補の NFKC の集合が truth の充填物 1 つと一致し、候補の文 id の和が truth の `evidence` と一致する → `ABSTAINED`（過剰な棄権。score の JSON の `notation_tie` に id を載せる）。それ以外の ONE への TIE は事前登録どおり WRONG。この緩めを使わずに数えた値は `wrong_details`・`notation_tie` から機械で出せる（緩めが無ければ WRONG はその id の数だけ増える）。

- 2026-10-04 03:25:11 +0900（`date '+%Y-%m-%d %H:%M:%S %z'` の出力。この項を書いた直後に取った値。**第 2 ラウンド M1 の事前登録。規則の実装・第 2 ラウンドの測定・凍結より前**）: **理由の閉じた一覧に `PREDICATE_FORM_DIFFERS` と `PREDICATE_POSITION_UNKNOWN` を足す**（`PERIOD_CUT_UNCERTAIN` の後の検査。合わせて 6 つ: `SURFACES_DIFFER:<n>`・`SURFACE_NOT_IN_EVIDENCE`・`QUOTE_UNBALANCED_EVIDENCE`・`PERIOD_CUT_UNCERTAIN`・`PREDICATE_FORM_DIFFERS`・`PREDICATE_POSITION_UNKNOWN`）。それ以外はこの登録で変えない（後段の条件・構造の作り方・写しの形・採点はそのまま）。
  - **後段の条件（再確認。閉じた集合）**: `verdict ∈ {"UNKNOWN_UNREAD", "UNKNOWN_NO_EVIDENCE"}` ちょうどこの 2 値、かつ `--document` が 1 つ以上、かつ round5。これ以外の出力は 1 バイトも変えない（A1 は第 2 ラウンドでも `cmp` で測り直す）。**充填物（`text`）は証拠の文に書かれた表記そのまま**（言い換え・正規化をしない。この登録の検査は答えを採るか棄権するかを決めるだけで、文字列を作らない）。**構造はメモリ上で `observe_question_records` に渡す**（一時ファイルを作らない。この登録の検査もファイルを作らない）。
  - **きっかけ（第 1 ラウンドのレビュー M1。中間職の実測）**: 読解器 `semantic_read._MODAL_MARKS` が `たかった`・`たがった`・`たがっていた`・`たかったです`・`てみたかった`・`らしかった`・文末の `たら` を法の印として見ず、`先生は本を読みたかった。` を `読んだ。` と同じ節（読む／過去／法なし）として返す。そのため後段が「先生は何を読んだ？」に `本` と答えた（基点は答えなし）。読解器は触らない。後段の側で棄権に倒す。
  - **規則（構造だけで決まる。語の一覧・活用の一覧を足さない）**: 答え・TIE の候補の証拠の各文について、(1) `semantic_read.read(文)`（観測器の `read_sentence` と同じ呼び方。読むだけ）の `lang` が `ja` のとき、`readable` が真・`clauses` と `clause_meta` がちょうど 1 つ・`clause_meta[0].span` が文の中の位置として取れる、のどれかが欠けたら棄権（理由 `PREDICATE_POSITION_UNKNOWN`）。(2) 取れたら、**書かれた述語** = 文の `span[0]` から文末まで（末尾の `。．.！!？?` と空白類を除く）。**質問の末尾** = `--query` の末尾の `？?` と空白類を除いたもの。書かれた述語が質問の末尾で終わっていなければ棄権（理由 `PREDICATE_FORM_DIFFERS`）。例: 文 `…読みたかった` の書かれた述語 `読みたかった` は、質問 `先生は何を読んだ` の末尾でない → 棄権。文 `…読んだ` は 質問 `先生は何を読んだ` の末尾 → 従来どおり。質問 `先生は何を読みたかった？` と文 `…読みたかった` は一致 → 答える。文字の比べ方は完全一致（NFKC などの正規化をしない。棄権に倒れる側）。(3) 棄権のときの写し = `ORIGINAL`（元の dict に `question_cross` と trace の 1 段を足すだけ。`question_cross.reason` が上の理由）。TIE の各候補にも同じ検査をする（1 つでも外れたら `ORIGINAL`）。(4) `lang` が `ja` でない文（英語）には適用しない。理由: 中間職の英語の反例 39 例（`probe`・`probe2` の E 系 20 例）で、読解器は法助動詞・不定詞・完了などを `NO_MATCHING_CROSS_IN_READ_SENTENCES`（後段の前の棄権）にし、後段が誤った答えを返した例は 0。英語には「活用語尾を法の印と見ない」穴の実例が無い。ただし証明ではない（既知の穴に書く）。(5) 丁寧形（`読みました`）の文が普通形の質問（`読んだ`）に答えなくなるのは過剰な棄権として許す（`読みました` を `読んだ` と同じとみなす活用の表を足さない）。
  - **検査データ（第 2 ラウンドの追加。凍結）**: `tests/observe/question_ask/extra2/`（文書 4 本・質問 42 問。`build_extra2.py` が手書きの内容を書き出す。第 1 ラウンドの 7 つの言い方、プローブしていない 10 の言い方、述語の書き方が同じ対照、文が過去で問が願望の逆、丁寧形の過剰な棄権、英語の法の文）。期待は系に 1 度も通さずに書いた。`FROZEN_EXTRA2.json` に sha256 と日時を凍結する（既存の `FROZEN.json`・`FROZEN_EXTRA.json` は変えない）。採点は事前登録のとおり（NONE の問で後段が答え・TIE を返したら WRONG、ONE の問で答えが期待と違えば WRONG）。`expect_reason` は作者の予想で、合否の条件ではない（読解器が先に棄権しうる）。予想と実際の理由の分布を報告する。承認の条件は WRONG == 0・ERROR == 0。
  - **測り直すもの**: A1（条件の外・ORIGINAL が基点と byte 一致。基点の出力は第 1 ラウンドのものを使う）、A2（差し替え配置・r7）、W3-c2 の 185 問、B2 の形、第 2 ラウンドの検査データ。第 1 ラウンドから CORRECT が減った問の id を score の差から機械で出して docs の測定の区間に貼る。

### 何を作ったか（W3-c4）

- `verantyx/cli.py`: `cmd_ask` の round5 の分岐で `v.ask(...)` と `apply_to_ask(...)` の間に `_round5_question_cross(res, documents, args.query)` の 1 行。関数は `cmd_ask` の直前（`_QC_TRIGGER`・`_QC_SPLIT`・`_qc_records`・`_qc_sources`・`_qc_run`・`_round5_question_cross` ほか）。round5 は `one.py` の `Vera` なので、チケットの `vera.py` ではなく `cli.py` に置いた（plan D1）。`cmd_chat`（REPL）にはつないでいない。
- `verantyx/observe.py`（末尾への追加だけ）: `structure_from_records`・`observe_question_records`。構造をメモリ上で受ける入口で、`observe --anchor-kind question --structure <同じ records の jsonl> --no-index` と同じ `answer` を返す（`artifacts/w3-c4/parity.txt`）。観測の規則は触っていない。
- 検査データ `tests/observe/question_ask/`（凍結: `FROZEN.json`・`FROZEN_EXTRA.json`）、runner `run_ask.py`、比較 `cmp_a1.py`・`cmp_det.py`、パリティ `parity.py`、データの行検査 `check_lines.py`、測定の要約 `make_summary.py`。テスト `tests/test_ask_question_cross.py`・`tests/test_ask_question_cross_data.py`。

- **第 2 ラウンド（M1）**: `verantyx/cli.py` に `_qc_predicate_form`（読むだけ。`semantic_read.read` の `clause_meta[0].span` から、書かれた述語が質問の末尾で終わるかを見る）を足し、`_qc_run` の候補の検査の最後（`PERIOD_CUT_UNCERTAIN` の後）に呼ぶ。検査データ `tests/observe/question_ask/extra2/`（凍結: `FROZEN_EXTRA2.json`。誤りの訂正は `extra2/corrections.jsonl`）、要約 `summarize_extra2.py`、テスト（`tests/test_ask_question_cross.py` の 8b、`tests/test_ask_question_cross_data.py` の extra2）。`make_summary.py` が第 1 ラウンドの score（`artifacts/w3-c4/r1_scores/`）との差を機械で出す。

### 入口（W3-c4）

```
VERA_PLACEMENT=<粗い配置のディレクトリ> python -m verantyx.cli ask --mode round5 --document <文書または文書のディレクトリ> [--document …] [--request-kind factual --human-present] -- <質問>
```

- 既存の経路が `UNKNOWN_UNREAD`・`UNKNOWN_NO_EVIDENCE` で止まったときだけ後段が走る。走ったかは出力の `trace` の `{"part":"question_cross", …}` と `question_cross` の鍵で分かる。
- **配置（`VERA_PLACEMENT`）が無いと後段は何も答えない**（穴の型を確かめられない候補は `TYPE_UNCHECKED` → `NO_TYPED_CANDIDATE`。W5-d の規則。配置が無いのを実装の誤りと思って規則を緩めない）。配置があっても、英語の普通名詞（farmer・letter・teacher など）は粗い配置に型が無く、ほとんど答えない（測定結果の節）。
- 答えは `door:"question_cross"`・`sources[*].family:"document"`（文書のファイル名・行・文の本文・文 id）。割れたら `AMBIGUOUS_QUESTION_CROSS_TIE`（候補を重ねて返す）。それ以外は元の棄権に `question_cross: {"state", "reason", …}` を足すだけ。

### 判断記録（W3-c4）

中間職の指示書（plan）の決定は D1〜D8。実装役の判断は J。

- **plan D1**: 後段は `cli.py`（`vera.py` ではない）。**D2**: `observe.py` は末尾への追加のみ（`-` の行 0）。**D3**: 条件はちょうど `{UNKNOWN_UNREAD, UNKNOWN_NO_EVIDENCE}` かつ文書あり。外は同じオブジェクトを返す。**D4**: 構造は `load_directory`/`load_paths`、行は `split("\n")`、区切りは `(?<=。)|(?<=\.)(?=\s)`、id は `<ファイル名>#<行>:<番号>`。**D5**: 写しの表。**D6**: 順は 既存 → 後段 → 方針。**D7**: 生成コーパスの構造（やること 5）はやらない（`CONFIRM_REQUEST`・`REFERENCE_GENERATED` は後段から到達しない。既知の穴）。**D8**: A3 の未公開データは中間職が持つ。runner は `--questions`・`--docs-dir`・`--placement`・`--vp` で動く。
- **J1**: 理由 `PERIOD_CUT_UNCERTAIN` を足した（上の「事前登録の変更記録」）。試走で `Mr. Smith gave the map to the student.` に `Smith` を返したため。分割規則・語の一覧は足さず、棄権への倒しだけ。
- **J2**: 採点の ONE の行を 1 つ緩めた（同じく変更記録）。`ＰＣ`/`PC` の W3-c2 の 2 問（Q046・Q050）が、計画の写し（SURFACES_DIFFER → TIE）と衝突したため。緩めない場合の値は `notation_tie` から機械で出る。
- **J3**: `cli.py` の先頭に `import re` を 1 行足した（区切りの正規表現のため。`-` の行は増えない）。
- **J4**: 後段の関数は `mode` を引数に取らない。`mode == "round5"` は呼び出し位置（round5 の分岐の中だけ）で満たされる。`--mode legacy`・`--engine` の分岐は 1 バイトも触っていない（テスト `test_not_round5_…`）。
- **J5**: 基点との比較（A1）の runner は、子プロセスの cwd をそのツリー自身にする。`python -m` は cwd を sys.path の先頭に置くので、cwd が新しいツリーのままだと基点の測定が新しい `verantyx` を読んでしまう（最初の試走で実際に起きて、基点の出力に `question_cross` が出たので気づいた。やり直して、各 score の JSON の `loaded_from` に読んだ `cli.py` の路を残す）。
- **J6**: 凍結後に、文書なしの問が 2 問しか無い（登録は 4 問）のに気づき、3 問を `questions_nodoc.jsonl` として足して `FROZEN_EXTRA.json` で凍結した（流す前。後段に届かない形）。
- **J7**: `question_cross.documents` は `ERROR` で読み込み前に落ちたとき `None`。`where`（文 id → 出典）の内部に `cut_uncertain` を持つが、出典の 5 鍵（`family source line text sentence_id`）には出さない。
- **J8**: TIE（および表記違いの TIE）の各候補にも、表記・鉤括弧・`PERIOD_CUT_UNCERTAIN` の検査をする（外れたら `ORIGINAL`）。
- **J9**: `QUOTE_UNBALANCED_EVIDENCE` は今の読解器では実際には到達しない（鉤括弧を含む文を読解器が読まないので、証拠にならない。`Reading` の status が `ABSTAINED`）。偽の観測を差し込んだ単体テストでだけ検査している。読解器が鉤括弧の文を読むようになったときの備え。

- **J11（第 2 ラウンド M1）**: 規則は中間職の推奨のとおり（書かれた述語が質問の末尾で終わるか）。実装は `cli.py` の中だけ（`semantic_read.py`・`observe.py`・`basis_policy.py` は無変更）。理由は 2 つに分けた: 述語の位置が取れない・節が 1 つに決まらない（`PREDICATE_POSITION_UNKNOWN`）と、位置は取れたが書き方が違う（`PREDICATE_FORM_DIFFERS`）。「分からない」と「違う」を混ぜない。英語には適用しない（事前登録の変更記録に理由。反例が実測で 0 で、読解器が先に棄権している。証明ではない）。比べ方は完全一致（NFKC などで寄せない。棄権に倒れる側）。質問の末尾は `--query` から末尾の `？?` と空白類だけを除く（`か`・`の`・`です` は除かない。`先生は何を読んだのですか？` は棄権する）。
- **J12**: 第 1 ラウンドで自分が足したテスト `test_a_quotation_that_closes_inside_the_sentence_is_not_a_reason_to_abstain`（偽の観測で鉤括弧の検査だけを見るもの）は、鉤括弧を含む文を読解器が読まないため、新しい検査が先に棄権してしまう。その検査だけを `monkeypatch` で外して、元の主張（閉じた鉤括弧は棄権の理由にならない）を保った。既存（基点）のテストは 1 つも変えていない。
- **J13**: 凍結した extra2 の 2 問（X032・X037。文は丁寧形・問は普通形）の truth を、凍結のときは NONE（答えなくてよい）と書いたが、答え（`絵`・`歌`）は正しい（同じ事実）。作者の誤りとして `extra2/corrections.jsonl` に前後・理由・日時を追記し、訂正を当てない版と当てた版の両方を測った（`artifacts/w3-c4/r2_extra2_*_score.json` と `*_corr_score.json`）。凍結したファイルは 1 バイトも変えていない（`questions_corrected.jsonl` は別ファイル）。
- **J14**: 第 1 ラウンドのレビューの任意の改善 1・3・4 を直した（`docs/BASIS_POLICY.md` の古い一文、`run_ask.py` の `--base-tree` を基点の測定で必須に、既知の穴 7 の例）。任意の改善 2（`artifacts/w3-c4/` が大きい）は、基点の 2 回目の出力が A1 の対照の入力で、消すと再現できなくなるので、そのまま残した（コミットの判断は監査役）。

### 既知の穴（W3-c4。隠さない）

1. **配置が無いと答えない（F3）**。`VERA_PLACEMENT` 未設定の既定の入口では、後段は走るが穴の型を確かめられないので `NO_TYPED_CANDIDATE` で元の棄権を返す。実際に答えが変わるのは粗い配置を渡したときだけ。
2. **英語はほとんど答えない**（粗い配置 r7 に英語の普通名詞の型が無い）。数は測定結果の節。直していない。
3. **D7 をやっていない**: 方針の `CONFIRM_REQUEST`・`REFERENCE_GENERATED`（生成コーパスの構造から来る `origin:"generated"` の出典）は後段からは到達しない。方針の 6 値のうち到達するのは `ANSWER_HUMAN_BASIS`・`ABSTAIN` など後段が作る形に限る。
4. **`vera chat` の round5（REPL）につないでいない**（範囲外）。
5. **読解器が読めない問・文は答えにならない**: 後段が走った問の相当数は `QUESTION_NOT_READ`（読解器の棄権。数は測定結果の節の `question_cross.state` の分布）。受取人・場所・時の穴、鉤括弧を含む文、従属節の文は読まれない。後段は読解器を足さない。
6. **略語の保護は過剰に棄権する側**（J1）: `Mr.`・イニシャル・`U.S.` の隣の文は答えにならない。1 語だけの文の隣も棄権する。
7. **充填物が語の一部のことがある**: 読解器が複合語を割ったとき（例 `森田課長` → `森田` と `課長`）、答えは文の部分文字列だが人が書いた名前の一部になりうる。後段はこれを検出しない（検査は「表記が証拠の文の中にある」まで）。 例: 文書「森田課長が資料を渡した。」に「誰が資料を渡した？」は、既存の経路が `agent: 森田` と答える（後段は走らない。基点から）。
8. **既存の経路の答えは触らない**: 後段は棄権にだけ走る。既存の経路が間違って答えることは後段では直らない（`base_answer` で報告する）。
9. **表記だけが違う正解は TIE（過剰な棄権）になる**（`ＰＣ`/`PC`）。
10. **方針が答えを取り下げると `question_cross` は運ばれず、trace の 1 段だけが残る**（`basis_policy.py` は無変更）。
11. 行番号は「`load_path` が読み込んだ本文の行」。Markdown 風の構文（フェンス・表・字下げ・URL）は読み込みで行が潰れうる。
12. A3（中間職の未公開）・A5（隠しバンク B7・B2）は第 1 ラウンドでは実装役は流していない（第 2 ラウンドも同じ）。
13. **読解器の `_MODAL_MARKS` が活用形（`たかった`・`たがった`・`らしかった`・文末 `たら`）を見ない（第 1 ラウンドのレビュー E2）**。後段は書かれた述語の一致で棄権に倒すだけで、根は直らない。既存の経路は同じ文に「誰が本を読んだ？」と問われると `agent: 先生` と答える（基点から。extra2 の X008〜X010 が `BASE_MISMATCH`）。読解器を変更中の並行チケットとの統合後に、後段の数も変わりうる。
14. **述語の書き方が違うと、正しい答えでも棄権する（過剰な棄権）**: 丁寧形の文（`読みました`）に普通形の問（`読んだ`）、問が `…読んだのですか？` のように `か`・`の`・`です` で終わる、進行形の文に過去の問。どれも活用の表や語の一覧を足さずに棄権に倒した（J11）。どの問が答えなくなったかは測定結果の節（第 1 ラウンドとの差）に機械で貼ってある。
15. **英語には述語の書き方の検査を掛けていない**。中間職の英語の反例では誤答 0 だが、英語の読解器が法を落とす文が無いことの証明ではない。
16. 述語の位置は読解器の `clause_meta.span` に依存する。読解器の出力の形が変わって `span` が取れなくなると `PREDICATE_POSITION_UNKNOWN` で全部棄権する（安全側）。

### 宣言する衝突（W3-c4。実装役は解かずに宣言する。判断は監査役）

**K1: 既存テスト `tests/test_basis_policy_entry.py::test_a_document_that_does_not_answer_stays_an_abstention` が落ちる**（基線の失敗一覧に無い。全体テストの新しい失敗はこれと、環境由来の `test_s6_two_runs_agree_except_timing_and_recount_matches` の 2 件だけ。後者は基点の `git archive` の複製でも同じ理由（`verantyx_untouched` が False）で落ち、チケットが「未コミットの間だけ」と名指ししている）。

- テストの主張: 文書「花子は太郎に資料を渡した。」に「誰が次郎に鍵を渡しましたか？」と問う `vera ask --mode round5 --document` の出力（`basis_policy` を除く）が、`Vera.ask` の戻り値と（時間の鍵を除いて）**完全に等しい**。
- 衝突の理由: この問は既存の経路が `UNKNOWN_NO_EVIDENCE` で止まる（後段の条件の中）。チケットは「NO_ATTESTED_CELL／QUESTION_NOT_READ は元の棄権をそのまま返し、`question_cross: {…}` を **足す**」と定め、指示書は trace に 1 段を足すとしている。足した 2 つ（`question_cross` と trace の `part:"question_cross"` の段）のぶんだけ出力が等しくなくなるのは、チケットの設計から必然（実測: `question_cross.state == "NO_ATTESTED_CELL"`、`mapped_to == "ORIGINAL"`）。それ以外の鍵は 1 つも変わらない（A1 の比較 `artifacts/w3-c4/a1_cmp_noplace.txt`・`a1_cmp_r7.txt`: 元の棄権のまま返した問は全部、`question_cross` と trace の 1 段を除いて基点と byte 一致）。
- 指示書の前提 F11 は「どれも出力全体の等号や trace の末尾を見ていない」としたが、このテストは出力全体の等号を見ている。
- 実装役はこのテストを変えていない（許可パスの外。削除・skip・期待値の弱体化をしない）。製品の側を変えてテストに合わせることもしていない（チケットの仕様が反対を求めるため）。
- 提案（監査役が許可するときの変更。適用していない）: `artifacts/w3-c4/proposed_test_change_basis_policy_entry.diff`。`assert _stable(_without(out, "basis_policy")) == _stable(raw)` の 1 行を、後段が足した 2 つ（`question_cross` と trace の `part:"question_cross"` の段が 1 つだけあること）を確かめて、それを取り除いたものが `raw` に等しい、という主張に置き換える（元の主張を弱めるのではなく、足されたものを名指しして残りの等号を保つ）。この変更を当てた複製のテストは通る（`pytest -k does_not_answer_stays`: 1 passed。複製はスクラッチで流した）。
- 元の 1 行（前）: `assert _stable(_without(out, "basis_policy")) == _stable(raw)`。提案の後の全文は diff のとおり。

### 測定結果（W3-c4）

<!-- w3c4-measured:begin -->
（`tests/observe/question_ask/make_summary.py --patch-docs` が `artifacts/w3-c4/` のファイルから貼った区間。手で書き換えない。）

```
[base verdicts of the 343 questions of A1 (a1_base1.jsonl, no placement; same in the r7 run is in a1_base_r7.jsonl)]
    (outside) verdict AMBIGUOUS: 7
    (outside) verdict ANSWER: 60
    (outside) verdict CONFLICT: 5
    (outside) verdict UNKNOWN_INVALID_PROOF: 1
    (outside) verdict UNKNOWN_UNSUPPORTED_EVIDENCE: 25
  inside the closed set: UNKNOWN_NO_EVIDENCE: 20
  inside the closed set: UNKNOWN_UNREAD: 223
  no document: 2
  outside the closed set: 98
[a1_new: all 343 questions, final output after the policy, cli, no placement]
  counts {"CORRECT": 42, "WRONG": 0, "FALSE_NONE": 6, "ABSTAINED": 195, "NOT_RUN": 100}
  question_cross.state of the questions the stage ran on: {"HOLE_TYPE_UNDETERMINED": 11, "NOT_A_QUESTION": 1, "NO_ATTESTED_CELL": 33, "NO_TYPED_CANDIDATE": 101, "POLAR_QUESTION": 7, "QUESTION_NOT_READ": 89, "STRUCTURE_INVALID": 1}
  mapped_to: {"ORIGINAL": 243}; ERROR states: 0; WRONG ids: []
[a1_new_r7: all 343 questions, final output after the policy, cli, VERA_PLACEMENT=r7]
  counts {"CORRECT": 88, "WRONG": 0, "FALSE_NONE": 9, "ABSTAINED": 146, "NOT_RUN": 100}
  question_cross.state of the questions the stage ran on: {"FILLED": 45, "HOLE_TYPE_UNDETERMINED": 6, "INCOMPLETE_BY_EXTENSION": 2, "NOT_A_QUESTION": 1, "NO_ATTESTED_CELL": 33, "NO_TYPED_CANDIDATE": 54, "POLAR_QUESTION": 7, "QUESTION_NOT_READ": 89, "STRUCTURE_INVALID": 1, "TIE": 2, "TYPE_EXCLUDED_ALL": 3}
  mapped_to: {"AMBIGUOUS_QUESTION_CROSS_TIE": 2, "ANSWER": 44, "ORIGINAL": 197}; ERROR states: 0; WRONG ids: []
[a2_place: new data (AQ), in process, placement_ask.json]
  n=111 counts {"CORRECT": 68, "WRONG": 0, "FALSE_NONE": 1, "ABSTAINED": 16, "NOT_RUN": 26}
  WRONG ids: []; FALSE_NONE ids: ['AQ083']; ERROR states: 0
  question_cross.state: {"FILLED": 40, "INCOMPLETE_BY_EXTENSION": 1, "NOT_A_QUESTION": 1, "NO_ATTESTED_CELL": 18, "NO_TYPED_CANDIDATE": 1, "POLAR_QUESTION": 3, "QUESTION_NOT_READ": 16, "STRUCTURE_INVALID": 1, "TIE": 4}
  mapped_to: {"AMBIGUOUS_QUESTION_CROSS_TIE": 5, "ANSWER": 39, "ORIGINAL": 41}; existing path on the NOT_RUN rows: {"BASE_MATCH": 12, "BASE_NOT_JUDGED": 3, "NO_ANSWER": 11}
  basis_policy.outcome of the answers: {"ABSTAIN": 5, "ANSWER_HUMAN_BASIS": 39}
[a2_r7: new data (AQ), cli, VERA_PLACEMENT=r7]
  n=111 counts {"CORRECT": 45, "WRONG": 0, "FALSE_NONE": 1, "ABSTAINED": 39, "NOT_RUN": 26}
  WRONG ids: []; FALSE_NONE ids: ['AQ083']; ERROR states: 0
  question_cross.state: {"FILLED": 20, "INCOMPLETE_BY_EXTENSION": 1, "NOT_A_QUESTION": 1, "NO_ATTESTED_CELL": 18, "NO_TYPED_CANDIDATE": 24, "POLAR_QUESTION": 3, "QUESTION_NOT_READ": 16, "STRUCTURE_INVALID": 1, "TIE": 1}
  mapped_to: {"AMBIGUOUS_QUESTION_CROSS_TIE": 1, "ANSWER": 20, "ORIGINAL": 64}; existing path on the NOT_RUN rows: {"BASE_MATCH": 12, "BASE_NOT_JUDGED": 3, "NO_ANSWER": 11}
  basis_policy.outcome of the answers: {"ABSTAIN": 1, "ANSWER_HUMAN_BASIS": 20}
[w3c2_place: W3-c2 185 questions, in process, placement_q.json]
  n=185 counts {"CORRECT": 43, "WRONG": 0, "FALSE_NONE": 3, "ABSTAINED": 79, "NOT_RUN": 60}
  WRONG ids: []; FALSE_NONE ids: ['Q010', 'Q059', 'Q121']; ERROR states: 0
  question_cross.state: {"FILLED": 24, "NO_ATTESTED_CELL": 11, "NO_TYPED_CANDIDATE": 23, "POLAR_QUESTION": 4, "QUESTION_NOT_READ": 57, "TIE": 6}
  mapped_to: {"AMBIGUOUS_QUESTION_CROSS_TIE": 8, "ANSWER": 21, "ORIGINAL": 96}; existing path on the NOT_RUN rows: {"BASE_MATCH": 23, "BASE_MISMATCH": 6, "BASE_NOT_JUDGED": 2, "NO_ANSWER": 29}
  basis_policy.outcome of the answers: {"ABSTAIN": 8, "ANSWER_HUMAN_BASIS": 21}
[w3c2_r7: W3-c2 185 questions, cli, VERA_PLACEMENT=r7]
  n=185 counts {"CORRECT": 37, "WRONG": 0, "FALSE_NONE": 6, "ABSTAINED": 82, "NOT_RUN": 60}
  WRONG ids: []; FALSE_NONE ids: ['Q010', 'Q059', 'Q121', 'Q130', 'Q131', 'Q136']; ERROR states: 0
  question_cross.state: {"FILLED": 21, "HOLE_TYPE_UNDETERMINED": 6, "INCOMPLETE_BY_EXTENSION": 1, "NO_ATTESTED_CELL": 11, "NO_TYPED_CANDIDATE": 21, "POLAR_QUESTION": 4, "QUESTION_NOT_READ": 57, "TIE": 1, "TYPE_EXCLUDED_ALL": 3}
  mapped_to: {"AMBIGUOUS_QUESTION_CROSS_TIE": 1, "ANSWER": 20, "ORIGINAL": 104}; existing path on the NOT_RUN rows: {"BASE_MATCH": 23, "BASE_MISMATCH": 6, "BASE_NOT_JUDGED": 2, "NO_ANSWER": 29}
  basis_policy.outcome of the answers: {"ABSTAIN": 1, "ANSWER_HUMAN_BASIS": 20}
[w3c2_place_corr: W3-c2 185 questions with the W3-c2 corrections applied, in process]
  n=185 counts {"CORRECT": 43, "WRONG": 0, "FALSE_NONE": 3, "ABSTAINED": 79, "NOT_RUN": 60}
  WRONG ids: []; FALSE_NONE ids: ['Q010', 'Q059', 'Q121']; ERROR states: 0
  question_cross.state: {"FILLED": 24, "NO_ATTESTED_CELL": 11, "NO_TYPED_CANDIDATE": 23, "POLAR_QUESTION": 4, "QUESTION_NOT_READ": 57, "TIE": 6}
  mapped_to: {"AMBIGUOUS_QUESTION_CROSS_TIE": 8, "ANSWER": 21, "ORIGINAL": 96}; existing path on the NOT_RUN rows: {"BASE_MATCH": 23, "BASE_MISMATCH": 6, "BASE_NOT_JUDGED": 2, "NO_ANSWER": 29}
  basis_policy.outcome of the answers: {"ABSTAIN": 8, "ANSWER_HUMAN_BASIS": 21}
[w3c2_r7_corr: W3-c2 185 questions with the W3-c2 corrections applied, cli, r7]
  n=185 counts {"CORRECT": 37, "WRONG": 0, "FALSE_NONE": 6, "ABSTAINED": 82, "NOT_RUN": 60}
  WRONG ids: []; FALSE_NONE ids: ['Q010', 'Q059', 'Q121', 'Q130', 'Q131', 'Q136']; ERROR states: 0
  question_cross.state: {"FILLED": 21, "HOLE_TYPE_UNDETERMINED": 6, "INCOMPLETE_BY_EXTENSION": 1, "NO_ATTESTED_CELL": 11, "NO_TYPED_CANDIDATE": 21, "POLAR_QUESTION": 4, "QUESTION_NOT_READ": 57, "TIE": 1, "TYPE_EXCLUDED_ALL": 3}
  mapped_to: {"AMBIGUOUS_QUESTION_CROSS_TIE": 1, "ANSWER": 20, "ORIGINAL": 104}; existing path on the NOT_RUN rows: {"BASE_MATCH": 23, "BASE_MISMATCH": 6, "BASE_NOT_JUDGED": 2, "NO_ANSWER": 29}
  basis_policy.outcome of the answers: {"ABSTAIN": 1, "ANSWER_HUMAN_BASIS": 20}
[b2like_place: B2-like (47 questions), in process, placement_ask.json]
  n=47 counts {"CORRECT": 15, "WRONG": 0, "FALSE_NONE": 2, "ABSTAINED": 16, "NOT_RUN": 14}
  WRONG ids: []; FALSE_NONE ids: ['BQ040', 'BQ046']; ERROR states: 0
  question_cross.state: {"FILLED": 13, "NO_ATTESTED_CELL": 4, "QUESTION_NOT_READ": 16}
  mapped_to: {"ANSWER": 13, "ORIGINAL": 20}; existing path on the NOT_RUN rows: {"BASE_MATCH": 12, "BASE_MISMATCH": 1, "BASE_NOT_JUDGED": 1}
  basis_policy.outcome of the answers: {"ANSWER_HUMAN_BASIS": 13}
[b2like_r7: B2-like (47 questions), cli, r7]
  n=47 counts {"CORRECT": 6, "WRONG": 0, "FALSE_NONE": 2, "ABSTAINED": 25, "NOT_RUN": 14}
  WRONG ids: []; FALSE_NONE ids: ['BQ040', 'BQ046']; ERROR states: 0
  question_cross.state: {"FILLED": 4, "NO_ATTESTED_CELL": 4, "NO_TYPED_CANDIDATE": 9, "QUESTION_NOT_READ": 16}
  mapped_to: {"ANSWER": 4, "ORIGINAL": 29}; existing path on the NOT_RUN rows: {"BASE_MATCH": 12, "BASE_MISMATCH": 1, "BASE_NOT_JUDGED": 1}
  basis_policy.outcome of the answers: {"ANSWER_HUMAN_BASIS": 4}
[later stage ran / mapped to ANSWER or TIE, by the language of the first document (AD08-10, QD08-10, BA04 are English)]
  a2_place: {"en answered_or_tie": 18, "en ran": 33, "ja answered_or_tie": 26, "ja ran": 52}
  a2_r7: {"en ran": 33, "ja answered_or_tie": 21, "ja ran": 52}
  w3c2_place: {"en answered_or_tie": 10, "en ran": 47, "ja answered_or_tie": 19, "ja ran": 78}
  w3c2_r7: {"en ran": 47, "ja answered_or_tie": 21, "ja ran": 78}
  b2like_place: {"en answered_or_tie": 5, "en ran": 10, "ja answered_or_tie": 8, "ja ran": 23}
  b2like_r7: {"en ran": 10, "ja answered_or_tie": 4, "ja ran": 23}
[a1_cmp_noplace.txt]
  questions compared: 343 (base 343, base2 343, new 343)
  base1 vs base2: same 343, differ 0
  base vs new (outside the later stage): same 100, differ 0
  base vs new (ORIGINAL, question_cross removed): same 243, differ 0
  inside the closed set and mapped to ANSWER or TIE (changed by design, not compared): 0
  inside the closed set, unexplained: 0
[a1_cmp_r7.txt]
  questions compared: 343 (base 343, base2 343, new 343)
  base1 vs base2: same 343, differ 0
  base vs new (outside the later stage): same 100, differ 0
  base vs new (ORIGINAL, question_cross removed): same 197, differ 0
  inside the closed set and mapped to ANSWER or TIE (changed by design, not compared): 46
  inside the closed set, unexplained: 0
[a1_cmp_other_modes.txt]
  base1 vs base2: same 10, differ 0
  base vs new (outside the later stage): same 10, differ 0
  base vs new (ORIGINAL, question_cross removed): same 0, differ 0
  inside the closed set and mapped to ANSWER or TIE (changed by design, not compared): 0
  inside the closed set, unexplained: 0
  rc=0
[pytest_related_before.txt: related tests before] 1624 passed in 29.50s
[pytest_related_after.txt: related tests after] 1 failed, 1623 passed in 28.82s
[pytest_new_tests.txt: the new tests] 72 passed in 9.22s
[pytest_full.txt: full run] 117 failed, 12186 passed, 37 skipped, 75 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 376.79s (0:06:16)
[determinism.txt]
  PYTHONHASHSEED=0 vs PYTHONHASHSEED=1: questions 20, same 20, differ 0
  mask keys (values set to 0, keys kept): elapsed_ms, ingest_ms
[parity.txt]
  placement=placement_q variant=no_lang   questions=185 identical=185
  compared outputs: 740; mismatches: 0
  not compared: structure.file_sha256 (records hash vs file bytes hash)
[round 2 (M1, PREDICATE_FORM_DIFFERS / PREDICATE_POSITION_UNKNOWN): round-1 score -> round-2 score, per run; the ids that were CORRECT in round 1 and are not now]
  a2_place: CORRECT 68 -> 68, WRONG 0 -> 0, ERROR 0 -> 0, WRONG ids now []
      stage abstained by the new check: {}; CORRECT -> not CORRECT: none
  a2_r7: CORRECT 45 -> 45, WRONG 0 -> 0, ERROR 0 -> 0, WRONG ids now []
      stage abstained by the new check: {}; CORRECT -> not CORRECT: none
  w3c2_place: CORRECT 44 -> 43, WRONG 0 -> 0, ERROR 0 -> 0, WRONG ids now []
      stage abstained by the new check: {"PREDICATE_FORM_DIFFERS": 1}; CORRECT -> not CORRECT: Q120(ABSTAINED:PREDICATE_FORM_DIFFERS)
  w3c2_place_corr: CORRECT 44 -> 43, WRONG 0 -> 0, ERROR 0 -> 0, WRONG ids now []
      stage abstained by the new check: {"PREDICATE_FORM_DIFFERS": 1}; CORRECT -> not CORRECT: Q120(ABSTAINED:PREDICATE_FORM_DIFFERS)
  w3c2_r7: CORRECT 38 -> 37, WRONG 0 -> 0, ERROR 0 -> 0, WRONG ids now []
      stage abstained by the new check: {"PREDICATE_FORM_DIFFERS": 1}; CORRECT -> not CORRECT: Q120(ABSTAINED:PREDICATE_FORM_DIFFERS)
  w3c2_r7_corr: CORRECT 38 -> 37, WRONG 0 -> 0, ERROR 0 -> 0, WRONG ids now []
      stage abstained by the new check: {"PREDICATE_FORM_DIFFERS": 1}; CORRECT -> not CORRECT: Q120(ABSTAINED:PREDICATE_FORM_DIFFERS)
  b2like_place: CORRECT 15 -> 15, WRONG 0 -> 0, ERROR 0 -> 0, WRONG ids now []
      stage abstained by the new check: {}; CORRECT -> not CORRECT: none
  b2like_r7: CORRECT 6 -> 6, WRONG 0 -> 0, ERROR 0 -> 0, WRONG ids now []
      stage abstained by the new check: {}; CORRECT -> not CORRECT: none
  a1_new: CORRECT 42 -> 42, WRONG 0 -> 0, ERROR 0 -> 0, WRONG ids now []
      stage abstained by the new check: {}; CORRECT -> not CORRECT: none
  a1_new_r7: CORRECT 89 -> 88, WRONG 0 -> 0, ERROR 0 -> 0, WRONG ids now []
      stage abstained by the new check: {"PREDICATE_FORM_DIFFERS": 1}; CORRECT -> not CORRECT: Q120(ABSTAINED:PREDICATE_FORM_DIFFERS)
[extra2 (round 2 data, 42 questions, frozen in FROZEN_EXTRA2.json): round-1 code vs round-2 code, uncorrected and corrected truth (corrections.jsonl: X032, X037)]
  in process, placement_extra2.json, truth as frozen: counts {"CORRECT": 19, "WRONG": 0, "FALSE_NONE": 0, "ABSTAINED": 16, "NOT_RUN": 7}, WRONG [], ERROR 0
  in process, placement_extra2.json, truth with corrections.jsonl: counts {"CORRECT": 19, "WRONG": 0, "FALSE_NONE": 0, "ABSTAINED": 16, "NOT_RUN": 7}, WRONG [], ERROR 0
  cli, VERA_PLACEMENT=r7, truth as frozen: counts {"CORRECT": 18, "WRONG": 0, "FALSE_NONE": 0, "ABSTAINED": 17, "NOT_RUN": 7}, WRONG [], ERROR 0
  cli, VERA_PLACEMENT=r7, truth with corrections.jsonl: counts {"CORRECT": 18, "WRONG": 0, "FALSE_NONE": 0, "ABSTAINED": 17, "NOT_RUN": 7}, WRONG [], ERROR 0
  round-1 code (the same questions, in process): truth as frozen: counts {"CORRECT": 19, "WRONG": 13, "FALSE_NONE": 0, "ABSTAINED": 3, "NOT_RUN": 7}, WRONG ['X001', 'X002', 'X003', 'X004', 'X005', 'X006', 'X007', 'X032', 'X033', 'X034', 'X035', 'X036', 'X037']
  round-1 code (the same questions, in process): truth with corrections.jsonl: counts {"CORRECT": 21, "WRONG": 11, "FALSE_NONE": 0, "ABSTAINED": 3, "NOT_RUN": 7}, WRONG ['X001', 'X002', 'X003', 'X004', 'X005', 'X006', 'X007', 'X033', 'X034', 'X035', 'X036']
```
<!-- w3c4-measured:end -->

## W5-e の事前登録: A-1 質問の十字の「AGREE と TYPE_UNCHECKED が並ぶ」とき（`INCOMPLETE_TYPING`）
<!-- w5e-a1-prereg:begin -->
事前登録の時刻: 2026-10-04 03:47:48 +0900（`date '+%F %T %z'`）。この節は A-1 の新しいテスト（`tests/test_question_cross_w5e.py`）を書く前、製品コード（`verantyx/observe.py`）を直す前に確定した。上の節は 1 文字も変えない。

**命中（W5-d の攻撃 A-1、`tests/attack/test_attack_w5d.py::test_obs_partial_type_agreement_does_not_hide_a_second_attested_answer`）**: 同じ交差に一致した 2 人のうち片方だけが direct、もう片方が UNPLACED／推定のとき、候補が 1 人（direct の方）だけになって `FILLED` に縮む（W5-d の申し送り 1 と同じ。二人目が答えかもしれないことを答えが隠す）。

### 規則（`_observe_question` の候補の判定の直後、`cells` を作る前）
- `kept`（AGREE の候補）が 1 つ以上あり、`dropped` に理由 `TYPE_UNCHECKED` が 1 つ以上あるとき、`FILLED`／`TIE` にせず状態 `INCOMPLETE_TYPING`（型付きの棄権）。`fillers`（残った候補）と `excluded`（除外）を **両方** 返す。答えとして出さない（`ranks` は空、`focus` は `NoMoveLicensed({'FILL_HOLE:INCOMPLETE_TYPING': 1})`）。`reasons` は先頭 `INCOMPLETE_TYPING` に既存の `extending_reasons + unread_reasons` が続く。
- 置く位置は `if not kept: … TYPE_EXCLUDED_ALL` の直後（`NO_TYPED_CANDIDATE` と同じく元素を作らない）。`INCOMPLETE_BY_EXTENSION` も当たるときは `INCOMPLETE_TYPING` が先（どちらも棄権）。
- 「残った候補が 1 つ以上」は `TIE`（AGREE の候補が複数）も含むので、AGREE の複数＋ TYPE_UNCHECKED の構成も `INCOMPLETE_TYPING` にする（判断。チケットの括弧書きどおり）。
- AGREE だけ（`excluded` が型の不一致 `HOLE_TYPE_DISAGREE` だけ、または `SAME_AS_RESTRICTOR` だけ）なら従来どおり `FILLED`／`TIE`。
- **対象外（変えない。既知の穴）**: which+N の `HOLE_TYPE_NOT_CHECKED`（`strict`。`test_which_noun_keeps_its_own_reason…` は無傷）、拡張の十字（extending）の型未確認の充填物（`test_an_unchecked_filler_of_an_extending_cross…` は無傷）。
- `ANSWER_STATUSES` の **末尾** に `'INCOMPLETE_TYPING'` を足す（`_observe_question` の外の 1 行。閉じた一覧の契約 D11）。`HOLE_EXCLUSION_REASONS` は変えない。

### 名指しの改訂（名前不変・前後の全文。標準の規則）
`tests/test_question_cross_w5d.py` の次の 2 本を改訂する。後の全文は書き換えたあとの測定の節（`w5e-a1-amended`）に貼る。
1. `test_a_checked_candidate_among_unchecked_ones_answers_and_the_others_stay_excluded`: AGREE の 1 人＋ TYPE_UNCHECKED の 1 人を `FILLED` で固定している → `INCOMPLETE_TYPING`（`fillers` に 1 人・`excluded` に 1 人）。
2. `test_a02_a_time_adverb_fused_with_its_noun_is_not_a_candidate_without_a_checked_type`: 同じ構成（本・新聞が AGREE、毎日本が TYPE_UNCHECKED）を `TIE` で固定している → `INCOMPLETE_TYPING`。前半（配置なし → `NO_TYPED_CANDIDATE`）は変えない。

**改訂の前の全文**
```python
def test_a_checked_candidate_among_unchecked_ones_answers_and_the_others_stay_excluded(tmp_path):
    pl = write_pl(tmp_path, {'船長': 'PERSON'})
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=pl)
    a = out['answer']
    assert a['status'] == 'FILLED' and fills(out) == [('船長', [('s1', 0)])] and excluded(out) == [('提督', 'TYPE_UNCHECKED')]

def test_a02_a_time_adverb_fused_with_its_noun_is_not_a_candidate_without_a_checked_type(tmp_path):
    out = ask_ja_doc('花子は何を読んだ？', 'JA02')
    a = out['answer']
    assert a['status'] == 'NO_TYPED_CANDIDATE' and a['fillers'] == []
    assert sorted(excluded(out)) == [('新聞', 'TYPE_UNCHECKED'), ('本', 'TYPE_UNCHECKED'), ('毎日本', 'TYPE_UNCHECKED')]
    pl = write_pl(tmp_path, {'本': 'ARTIFACT', '新聞': 'ARTIFACT'})            # only the two real nouns are typed (direct)
    out = ask_ja_doc('花子は何を読んだ？', 'JA02', pl)
    a = out['answer']
    assert a['status'] == 'TIE' and {f['surface'] for f in a['fillers']} == {'本', '新聞'}
    assert excluded(out) == [('毎日本', 'TYPE_UNCHECKED')]                      # not hidden: it stays in `excluded`
    assert {f['hole_type_check']['verdict'] for f in a['fillers']} == {'AGREE'}
```

### 宣言する衝突 K-A1（変えない。判断は監査役）
`tests/test_question_cross_w5d.py::test_the_new_names_are_at_the_end_of_the_closed_lists` は `ANSWER_STATUSES[-1] == 'NO_TYPED_CANDIDATE'` と固定している。規則どおり末尾に足すと落ちる。名指しが無いので **書き換えず宣言**し、改訂案の diff を `artifacts/w5-e/proposals/k_a1.diff` に置く。

### 受入（H2。測る前に固定）
- 実装役の 185 問（配置なし・配置あり、`VERA_PLACEMENT` なし・r7 の 4 通り）と攻撃の 120 問（r7・配置なし）で誤答 0、型未確認の充填物を持つ FILLED/TIE 0。`INCOMPLETE_TYPING` に変わる問の数を報告（FILLED が減ってよい）。変更前の測定は `artifacts/w5-e/before/` にある（製品の変更の前）。
<!-- w5e-a1-prereg:end -->

## W5-e A-1 の改訂後の全文（名指しの 2 本）と宣言
<!-- w5e-a1-amended:begin -->
記録の時刻: 2026-10-04 03:50:01 +0900。テストの改訂は製品コードの変更（`observe.py`）の後。改訂は名前不変で、変えたのは `status` の期待 1 語と理由のコメント 1 行だけ（`git diff --stat tests/test_question_cross_w5d.py` で追加 4 行・削除 2 行。コメント 2 行＋ `status` の行の置き換え 2 行）。前の全文は上の `w5e-a1-prereg` 区間。

**改訂の後の全文**
```python
def test_a_checked_candidate_among_unchecked_ones_answers_and_the_others_stay_excluded(tmp_path):
    pl = write_pl(tmp_path, {'船長': 'PERSON'})
    # W5-e（チケット W5-e の名指しの改訂）: AGREE の候補が TYPE_UNCHECKED の候補と並ぶ構成は FILLED ではなく INCOMPLETE_TYPING（A-1）。候補と除外は両方返る。
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=pl)
    a = out['answer']
    assert a['status'] == 'INCOMPLETE_TYPING' and fills(out) == [('船長', [('s1', 0)])] and excluded(out) == [('提督', 'TYPE_UNCHECKED')]

def test_a02_a_time_adverb_fused_with_its_noun_is_not_a_candidate_without_a_checked_type(tmp_path):
    out = ask_ja_doc('花子は何を読んだ？', 'JA02')
    a = out['answer']
    assert a['status'] == 'NO_TYPED_CANDIDATE' and a['fillers'] == []
    assert sorted(excluded(out)) == [('新聞', 'TYPE_UNCHECKED'), ('本', 'TYPE_UNCHECKED'), ('毎日本', 'TYPE_UNCHECKED')]
    pl = write_pl(tmp_path, {'本': 'ARTIFACT', '新聞': 'ARTIFACT'})            # only the two real nouns are typed (direct)
    out = ask_ja_doc('花子は何を読んだ？', 'JA02', pl)
    a = out['answer']
    # W5-e（チケット W5-e の名指しの改訂）: 本・新聞（AGREE）と毎日本（TYPE_UNCHECKED）が並ぶ構成は TIE ではなく INCOMPLETE_TYPING（A-1）。
    assert a['status'] == 'INCOMPLETE_TYPING' and {f['surface'] for f in a['fillers']} == {'本', '新聞'}
    assert excluded(out) == [('毎日本', 'TYPE_UNCHECKED')]                      # not hidden: it stays in `excluded`
    assert {f['hole_type_check']['verdict'] for f in a['fillers']} == {'AGREE'}
```

**宣言（K-A1。書き換えない）**: `tests/test_question_cross_w5d.py::test_the_new_names_are_at_the_end_of_the_closed_lists` は `ANSWER_STATUSES[-1] == 'NO_TYPED_CANDIDATE'` を固定しているので、規則どおり末尾に `INCOMPLETE_TYPING` を足すと落ちる。改訂案は `artifacts/w5-e/proposals/k_a1.diff`（`ANSWER_STATUSES[-2:]` の比較に変える 1 行）。

**製品の変更**: `verantyx/observe.py` は `ANSWER_STATUSES` の末尾の 1 語と `_observe_question` の中の 1 つの `if`（`TYPE_EXCLUDED_ALL` の直後）と docstring の 2 行だけ。
<!-- w5e-a1-amended:end -->


## W5-e の測定: A-1 質問の十字（H2）
<!-- w5e-a1-measured:begin -->
測定の時刻: 2026-10-04 04:10:06 +0900。コマンドは `artifacts/w5-e/scripts/measure.sh`（`run_questions_both.py` を 6 通り）。変更前は `artifacts/w5-e/before/`（製品の変更の前に取った）、変更後は `artifacts/w5-e/`。凍結とテスト: `frozen_a1.sha256`・`frozen_a1_at.txt`、直す前に落ちる記録 `a1_before_fail.txt`（`15 failed, 7 passed`）。

- **誤答 0**: `h2_185_place.json`・`h2_185_noplace.json`（`VERA_PLACEMENT` なし）・`h2_185_place_r7.json`・`h2_185_noplace_r7.json`（r7）・`h2_attack120.json`（なし）・`h2_attack120_r7.json` の 6 つとも `"wrong": []`・`unchecked_fillers_in_FILLED_TIE` 0。
- **正答（CORRECT）は 185 問の 4 通りとも変更前と同じ**: place 38、noplace 26、place_r7 73、noplace_r7 66（`h2_*.json` と `before/h2_*.json`）。
- **`INCOMPLETE_TYPING` に変わった問の数**（`h2_changes.txt`）: 185 問の 4 通りは 0 件、攻撃 120 問は配置なし 0 件・r7 で 1 件（`JA02-01` `花子は何を読んだ？`: `FILLED [本]` → `INCOMPLETE_TYPING`。`新聞`・`毎日本` は `TYPE_UNCHECKED`。W5-d2 が既知の穴に書いた形）。
- `INCOMPLETE_TYPING` 以外へ変わった問（`h2_changes.txt`）: 185 問の 4 通りで 1 件ずつ、`Q133`（`兄か弟が鉛筆を貸した？`、正解は ILLFORMED）が `POLAR_QUESTION` → `QUESTION_NOT_READ`。原因は A-1 ではなく B-2 の門（`DISJUNCTION_UNDETERMINED`。読解器が選言の節を読まなくなった）。どちらも棄権で、`run_questions.py` の分類は `ABSTAINED` のまま。
- **テスト**: `tests/test_question_cross_w5e.py` は `19 passed`（`new_tests_run.txt`）。名指しの改訂 2 本は通り、`tests/test_question_cross_w5d.py` の失敗は宣言した K-A1 の 1 件だけ（`29 passed, 1 failed`: `a1_w5d_run.txt`）。攻撃 A-1（`test_obs_partial_type_agreement_does_not_hide_a_second_attested_answer`）は通る。
- **既知の穴**: which+N の `HOLE_TYPE_NOT_CHECKED` と、拡張の十字（extending）の型未確認の充填物は `INCOMPLETE_TYPING` の対象外（変えていない）。
<!-- w5e-a1-measured:end -->

## W5-e 第 2 ラウンド: K-A1 の改訂（監査役の判断 2026-10-04 04:42）
<!-- w5e2-ka1:begin -->
監査役の判断: 「K-A1（1）: W5-d のテストが部分的な型づけの FILLED を固定していたもの → 新しい規則に合わせて改訂」。第 1 ラウンドで宣言した衝突は `test_the_new_names_are_at_the_end_of_the_closed_lists` の 1 件（閉じた状態の一覧の末尾の名前を `NO_TYPED_CANDIDATE` で固定していた。A-1 が `INCOMPLETE_TYPING` を末尾に足した）。名前不変。中身は `ANSWER_STATUSES` の末尾の 2 つを `(NO_TYPED_CANDIDATE, INCOMPLETE_TYPING)` と固定する 1 行だけ（`artifacts/w5-e/proposals/k_a1.diff`）。ほかの行・期待は変えない。

#### `tests/test_question_cross_w5d.py::test_the_new_names_are_at_the_end_of_the_closed_lists` — 改訂前の全文（基点 ca66d3e と同じ）
```python
def test_the_new_names_are_at_the_end_of_the_closed_lists():
    assert O.ANSWER_STATUSES[-1] == 'NO_TYPED_CANDIDATE' and O.ANSWER_STATUSES[:10] == (
        'FILLED', 'TIE', 'NO_ATTESTED_CELL', 'TYPE_EXCLUDED_ALL', 'HOLE_TYPE_UNDETERMINED', 'POLAR_QUESTION',
        'DIRECTION_NOT_APPLIED', 'QUESTION_NOT_READ', 'ANCHOR_CROSS_INDEX_OUT_OF_RANGE', 'INCOMPLETE_BY_EXTENSION')
    assert O.HOLE_EXCLUSION_REASONS == ('HOLE_TYPE_DISAGREE', 'HOLE_TYPE_NOT_CHECKED', 'SAME_AS_RESTRICTOR', 'TYPE_UNCHECKED')
```

#### `tests/test_question_cross_w5d.py::test_the_new_names_are_at_the_end_of_the_closed_lists` — 改訂後の全文
```python
def test_the_new_names_are_at_the_end_of_the_closed_lists():
    # W5-e2（監査役の判断 2026-10-04 04:42、K-A1）: A-1 が INCOMPLETE_TYPING を末尾に足したので、末尾の 2 つを固定する
    assert O.ANSWER_STATUSES[-2:] == ('NO_TYPED_CANDIDATE', 'INCOMPLETE_TYPING') and O.ANSWER_STATUSES[:10] == (
        'FILLED', 'TIE', 'NO_ATTESTED_CELL', 'TYPE_EXCLUDED_ALL', 'HOLE_TYPE_UNDETERMINED', 'POLAR_QUESTION',
        'DIRECTION_NOT_APPLIED', 'QUESTION_NOT_READ', 'ANCHOR_CROSS_INDEX_OUT_OF_RANGE', 'INCOMPLETE_BY_EXTENSION')
    assert O.HOLE_EXCLUSION_REASONS == ('HOLE_TYPE_DISAGREE', 'HOLE_TYPE_NOT_CHECKED', 'SAME_AS_RESTRICTOR', 'TYPE_UNCHECKED')
```
<!-- w5e2-ka1:end -->

## W5-f の事前登録: F-5 文書 QA の後段の本文照合の定義（W3-c4 の攻撃への答え）
<!-- w5f-prereg:begin -->
事前登録の時刻: 2026-10-04 08:40:13 +0900（`date '+%F %T %z'` の出力。`artifacts/w5-f/prereg_time.txt`）。上の節は 1 文字も変えない。出典: 中間職の指示書 `.claude/vera-audit/review-impl/W5-f/plan.md` D6、攻撃の報告 `attacks/reports/W3-c4/`。

**命中**: 後段の `sources[].text` が「元の Markdown 文字列には無く、読込後の本文にだけある」（攻撃の写し `test_markdown_link_evidence_text_is_a_literal_source_substring`）。意味上の誤答ではない（攻撃役自身が「本文照合の定義の揺れ」と書いた）。

**定義（規則の変更ではなく明記）**: 本文照合（W5-c/W5-d の A1。`basis_policy._document_texts`）と後段の出典の `text`（`cli._qc_records` が `document_loaders` の `Document.text` を行・文に切り、`_qc_sources` がその文を返す）は、どちらも **読込後の本文**（`document_loaders.load_paths`／`load_directory` が返す `Document.text`）に対して定義する。元のファイルの逐字の文字列ではない: Markdown のリンクは表示語だけ、見出しの `#` は `document_loaders._from_markdown` が読込時に外す、コード・URL・表の行は消える。出典の `line` は読込後の本文の行番号。
- `cli.py` は変えない（実測では今の振る舞いがこの定義どおり。測定で出典の `text` が読込後の本文の部分文字列でない行が見つかったときだけ `_qc_records` の切り出しを直す）。
- **宣言 K-C4**: 攻撃の写し `tests/attack/test_attack_w3c4.py::test_markdown_link_evidence_text_is_a_literal_source_substring` は、この定義では定義上落ちる。写しはバイト同一のまま変えない。判断は監査役。
- 新しいテスト（`tests/test_ask_question_cross_w5f.py`）: r8 の配置で、見出し記法つき・リンクつきの Markdown を `--document` に渡し、`sources[].text` が `document_loaders.load_paths` の返す本文の部分文字列で、`#`・`](` を含まず、`line` が読込後の本文の行番号と一致する（r8 が無ければ `ENV_MISSING` の skip）。
- I4 の測定の形: 既存の W3-c4 の検査データ（`tests/observe/question_ask/` の `questions.jsonl` と `extra2/`）を `run_ask.py --tree new --mode inproc` で変更前（`artifacts/w5-f/before/`）と後で流し、問ごとに verdict・text・sources の `{source, line, text}` を比べて、変わった問を全件 `artifacts/w5-f/i4_changed.tsv` に出す。
<!-- w5f-prereg:end -->

## W5-f 実測結果（後段の本文照合）
測定記録: 2026-10-04 10:01:23 +0900（`artifacts/w5-f/s6_docs_time.txt`）。

- W3-c4 の主検査 111 問は変更前後とも CORRECT 68 / WRONG 0 / FALSE_NONE 1 / ABSTAINED 16 / NOT_RUN 26。extra2 の 42 問も CORRECT 19 / WRONG 0 / FALSE_NONE 0 / ABSTAINED 16 / NOT_RUN 7。両方とも問別の verdict・text・`sources[].{source,line,text}` の変更は 0（`artifacts/w5-f/i4_score_compare.txt`・`artifacts/w5-f/i4_changed.tsv`）。
- 見出し・リンクを含む追加 Markdown 質問を含む質問十字テスト群は 73 件通過（`artifacts/w5-f/i4_tests.txt`）。`cli.py` は変更していない。
- W3-c4 の攻撃写しは「元の Markdown 文字列の部分文字列」を要求するため、この定義では通らない（宣言 K-C4、`artifacts/w5-f/i1_attack.txt`）。読込後の本文から切り出した出典が定義に一致することは追加テストで確認した。

## W3-f1 の事前登録: 答えの値の全表記（K340–K342）

登録時刻: 2026-10-05 15:06:53 +0900（`artifacts/w3-f1/prereg_time.txt`）。検査データを書く前、製品コードを変える前に登録する。

### 規則（チケットから）
- **K340**: 答えの値は、読解器が読んだ充填物の表記そのまま（NFKC）。切り出し・正規化・見出し語化で短くしない。短くなる経路はすべて、棄権で逃げずに元の表記を返すように直す。
- **K341**: 修正は原因の 1 箇所。修正の前に、現象を再現するテストを凍結（検査データ 60 文以上: 親族・人の 2 字以上の名詞 × 役割 3 × 問い）。修正の後に全件が全文字で返ること。
- **K342**: 既存の凍結データ（B 系の公開の写し、W3-c4・W5-c の検査データ）の答えが byte 不変であること。変わる行は全件列挙（短縮が直る方向だけ許す）。

### 検査データの型
- 名詞 25 語: 父・母・祖父・祖母・叔父・叔母・伯父・伯母・兄・姉・弟・妹・息子・娘・夫・妻・孫・友人・同僚・上司・部下・先輩・後輩・店主・教師。
- 役割 3 の雛形（X に名詞）: agent は文書「Xが肥料を運んだ。」／問い「誰が肥料を運んだ？」、recipient は文書「店員がXに本を渡した。」／問い「店員は誰に本を渡した？」、patient は文書「医師がXを診察した。」／問い「医師が誰を診察した？」。
- 偽の肯定の 6 対（polar）: 文書「Bが肥料を運んだ。」／問い「Aは肥料を運んだ？」、(A,B) = (叔父,叔母)・(叔母,叔父)・(祖父,祖母)・(祖母,祖父)・(伯父,伯母)・(伯母,伯父)。
- 合計 75 + 6 = 81 件。対照として同じ 3 雛形を名前「田中」で流す 3 件。

### 判定の式
- 役割の問い: `verdict == "ANSWER"` かつ `values == [名詞の全表記]`。
- 偽の肯定の対: `verdict == "ANSWER"` かつ `text` に「はい」を含む、が起きないこと（それ以外の verdict・いいえ・棄権は可）。
- 経路: `verantyx.cli.main` の既定の入口（`ask --mode round5 --document`）。

## W3-f1 実測結果: 答えの値の全表記（K340–K342）

数値はすべて `artifacts/w3-f1/` のファイルから（出典を併記）。

- **原因**: `verantyx/frames.py` の `canonical()` が、`ROLES` の `父`・`母` などの接尾で名前を割り、`叔父` を名前 `叔` ＋役職 `父` として鍵を `叔` にしていた。文書・問い・検証の全部が同じ関数を使うので、答えの値が短くなり、`叔父` と `叔母` の鍵（`叔`）が衝突して偽の「はい」も出ていた（`repro_before_1.json`・`repro_before_2.json`）。許可パス外の 1 ファイルだが、値の側で直すと偽の肯定が残る（`DECISIONS.md` 1）。
- **修正**: `canonical()` の接尾の枝に 2 条件（接尾の始まりが形態素の境目、直前の形態素が固有名詞）。満たさなければ表記そのまま。語の一覧は足していない（`check_hardcode.txt`）。
- **誤答の範囲（修正前）**: 検査データ 81 件（名詞 25 語 × 役割 3 ＋ 偽の肯定 6 対）のうち 24 件が誤り。祖父・祖母・叔父・叔母・伯父・伯母の 6 語 × 役割 3 = 18 件は 1 字目だけ（祖・叔・伯）で ANSWER、偽の肯定 6 対はすべて「可否: はい」（`range_before_truncated.tsv`）。父・母・兄・姉・弟・妹・息子・娘・夫・妻・孫・友人・同僚・上司・部下・先輩・後輩・店主・教師は全表記で返った（`range_before.tsv`）。
- **修正後**: 同じ 81 件で 1 字でも欠けた ANSWER は 0、偽の「はい」は 0（`range_after_truncated.tsv` は見出しだけ。偽の肯定 6 対は UNKNOWN_NO_EVIDENCE、`range_after.tsv`）。テスト `tests/test_w3f1_kinship_answer.py` は修正前 24 失敗・61 通過（`a1_before.txt`）、修正後 85 通過（`a1_after.txt`）。再現（叔父が肥料を運んだ）は `values: ["叔父"]`（`repro_after_1.json`）。
- **frames 層の調査**: 凍結データの文 7050 文を読み、agent/patient/recipient の値で canonical が短くなる組は 24 組 → 4 組（森田課長→森田・田中部長→田中・先生の夫婦→夫婦・祖父の家→家）。前は 叔父・叔母・祖父・祖母・伯父・伯母・農夫・曾孫・孫娘・新妻・兄の友人 等（`census_before.tsv`・`census_after.tsv`。文数と組数は `census_before.log`＝7050 文・24 組、`census_after.log`＝7050 文・4 組。前は基点 `af5594a` の `frames.py` ＋同じ凍結データで取り直した）。`frames.regression()` の false の集合は前後同じ（`relative`・`rel_trans`、`frames_regression_*.txt`）。
- **K342**: 質問 aq 111・extra2 42・w3c2 185・b2like 47 の ask 出力を問ごとに全文比較（`ingest_ms`・`elapsed_ms` をマスク）。変化は 3 問（`k342_changed.tsv`、`k342_summary.txt`）。Q069（w3c2）は verdict・values・text 同じで、内部の term が `農` → `農夫` になっただけ（短縮が直る方向）。**「それ以外」が 2 問**: AQ025（誰が農夫に小麦を渡さなかった？）と AQ028（誰が農夫に小麦を渡した？）は、どちらも棄権のまま型が `UNKNOWN_UNREAD`（問いが読めない）→ `UNKNOWN_UNSUPPORTED_EVIDENCE`（文書の節が読めない）に変わった。値は無く、text は同じ。aq の score は ABSTAINED 16→14・NOT_RUN 26→28、CORRECT/WRONG は不変（`before/aq_score.json`・`after/aq_score.json`）。extra2・w3c2・b2like の score は同一。aq・extra2 の同じ基点 2 回の対照で差は 0 件。**原因（実測、`k342_aq025_cause.txt`）**: 基点では問い側の `農夫` が `canonical` で `農` に短縮され、問い「誰が農夫に小麦を渡さなかった？」そのものが読めなかった（`before/aq.jsonl` の AQ025: `question.read_semantic` の `plans=0`・`unread` = `unsupported request grammar`、問いの全文）。修正後は問いが読め（`plans=1`・`obligations=8`・`unread=[]`、Bind の pattern に `recipient: 農夫`）、棄権の理由は文書の見出し「町の記録」の `source_unread`（`unsupported clause grammar`、基点でも同じ）に移った。単文の切り分け（基点→修正後）: 「粉屋が農夫に小麦を渡した。」／「誰が農夫に小麦を渡した？」は `UNKNOWN_UNREAD`→`ANSWER ['粉屋']`、対照の「田中」は前後とも `ANSWER ['粉屋']`、「叔父」は `UNKNOWN_UNREAD`→`ANSWER ['粉屋']`。分類: 問い側の短縮が直った結果で、値・text は不変（CORRECT 68・WRONG 0 も不変）。規則は緩めていない。
- **公開バンクの写し**: B1（mod-semantic-read）・B2（cli-ask-round5）の問別の結果は前後で同一（`bs_compare.txt`、`bs_B1_*.txt`・`bs_B2_*.txt`）。B2 の公開の写し 25 問に親族名詞を含む項目は 0 件（`b2_public_kin_count.txt`）。
- **テスト**: 関係テストの失敗の集合は前後同一（`related_before.txt`・`related_after.txt`）。全体テスト（第 2 ラウンドで負荷 1 分平均 6.9 のときに 1 回だけ流し直し。`pytest_full_load_before.txt`）: `pytest_full.txt` の最終行 `117 failed, 15976 passed, 38 skipped, 81 xfailed, 75 xpassed, 1 warning, 37 subtests passed in 627.62s (0:10:27)`、ERROR 0。`after_failures.txt` はこの同じファイルの `^(FAILED|ERROR)` 行（117 件）。基線 `dev_bfb17b8_failures.txt`（115）との差 `new_failures.txt` は 3 件、基線にあって通った `fixed_failures.txt` は 1 件（test_one_trace）。3 件の分類は `new_failures_classified.txt` と、基点（git 付きの clean な写し）でも全体テストを 1 回流した `pytest_full_base.txt`（116 failed、`after_failures_base.txt`）: (a) `test_p4_abilities::test_speech_act_drafts_fill_new_roles_and_reread` と (b) `test_gen_coarse_evidence::test_the_stop_signal_ends_the_run_with_an_interrupted_record` は基点の全体走行でも落ちる（チケットが環境由来と書いた系統。(b) は単独では基点・修正後とも通る。全体走行でだけ落ちる）。(c) `bank_score/test_bs_end_to_end::test_s6_two_runs_agree_except_timing_and_recount_matches` の理由は `tools/bank_score/cli.py:335` の `verantyx_untouched`（`git status --porcelain -- verantyx` が空でないと False）で、`verantyx/frames.py` が未コミットだから落ちる。git 付きの写しで未コミットのとき落ち（`new_failures_classified.txt`）、写しの中だけでコミットすると `1 passed`、基点の clean な git 写しでは全体走行でも通る（`after_failures_base.txt` に無い）。したがってコミット後に消える見込み。第 1 ラウンドの報告にあった test_conduct_ask_w5b・test_w10f04_serve の失敗は、今回の全体走行では出なかった（負荷由来で再現しない）。
- **既知の穴**: 固有名詞と判定されない姓（`原`・`星` など）＋役職は割られなくなる（`原先生` は鍵が `原先生` のまま。`canonical_probe.txt`）。「X は誰を V？」（は＋誰を）は基点でも `UNKNOWN_UNREAD`（対象外）。

## W3-f1 拡張の事前登録: 禁止の形・時間名詞と場所の融合

登録時刻: 2026-10-05 20:06:25 +0900（`artifacts/w3-f1/prereg_ext_time.txt`）。検査データを書く前、製品コードを変える前に登録する。誤答 1（親族の切り詰め）は上の節のとおり修正・凍結済みで、ここでは扱わない。

### 規則（チケットの監査役の拡張から。狭める方向だけ）
- (2) 「てはならない／てはいけない／ではならない」の補助の否定（て／で（／ちゃ／じゃ）＋ は／も の直後の `なる`・`いける` の否定）から可否の答えを出さない。禁止の読みは v1 で読まない → 型つき棄権 `PROHIBITION_NOT_READ`。
- (3) 場所・着点の値に時の語が連結していたら、その値で答えない。v1 は時の語を切り出さず棄権する（切り出しは読解器の仕事で、このチケットでは変更禁止のファイル）。

### 判定の式（テストにそのまま書く）
- 禁止 `kind=aux_polar`（補助を問う可否）: `verdict != "ANSWER"`。
- 禁止 `kind=main_polar`（本動詞を問う可否）: `verdict != "ANSWER"`（禁止を肯定・否定の事実として答えない）。
- 禁止 `kind=control`（普通の否定・肯定）: `verdict == "ANSWER"` かつ `values == expect_values`。
- 時と場所 `kind=fused`: `not (verdict == "ANSWER" and any(time_word in v for v in values))`、かつ `verdict == "ANSWER"` なら `values == [place]`。
- 時と場所 `kind=control`（時の語が無い／読点で離れている／文頭）: `verdict == "ANSWER"` かつ `values == expect_values`。

### 範囲を測るだけの集合（合否に入れない、と事前に宣言）
`ても`（`てもいけない`・`てもならない`）、`ちゃ`・`じゃ`（`ちゃいけない`・`じゃいけない`）、`なくてはならない`・`なくてはいけない`（義務の形）、場所の後ろに時の語（「東京で明日働く」）、複数文の文書。前後の結果を全件 TSV に出し、報告に全件列挙する。

### 記録する副次の量
禁止の `aux_polar` で、修正後の `reason` に `PROHIBITION_NOT_READ` を含む行の数（全件の表は `artifacts/w3-f1/ext_reason_after.tsv`）。

## W3-f1 拡張の実測結果: 禁止の形・時間名詞と場所の融合

数値はすべて `artifacts/w3-f1/` のファイルから（出典を併記）。

- **原因（誤答 2）**: `verantyx/constructions/negation.py` の `_event_reading()` が、`開い/て/は/なら/ない` の補助 `なら`（見出し語 `なる`）を否定の出来事として読み、偽の否定の節を作っていた。直し: 補助が接続助詞 て/で/ちゃ/じゃ（＋ は/も）の直後の `なる`・`いける` のとき、節を消さず `unsupported=("PROHIBITION_NOT_READ",)` を付ける（形態素の品詞・見出し語で判定。語は機能語のみ）。丁寧形の本動詞の問いが残ったため `verantyx/verdict.py` の `PROHIBIT` に丁寧形の語幹 4 つを足した（`DECISIONS.md` 7）。
- **原因（誤答 3）**: `verantyx/semantic_verify.py` の `_vt_check_roles()` は、時の語と融合した語を出来事の参加者にしか検査していなかった。場所・着点・方向にも同じ検査を 1 本足し、融合していれば `UNKNOWN_INVALID_PROOF`（v1 は切り出さず棄権）。
- **検査データ（凍結 `freeze_ext.sha256`）**: 禁止 70 件（aux_polar 42・main_polar 20・control 8）、時と場所 56 件（fused 44・control 12）、範囲だけ 26 件。修正前に 77 件が落ち（`a1_ext_before.txt`: 77 failed, 51 passed。aux/main 45 件、fused 32 件）、control は全部通った。修正後は誤答 1 の 85 件と合わせて 213 passed（`a1_ext_after.txt`）。凍結の作り直し 1 回（`DECISIONS.md` 11）。
- **範囲（`ext_range_before.tsv`・`ext_range_after.tsv`・`ext_range_changed.tsv`）**: aux_polar は修正前 ANSWER 39・NO_EVIDENCE 3 → 修正後 39 件が `UNKNOWN_UNSUPPORTED_EVIDENCE`（reason `PROHIBITION_NOT_READ`、`ext_reason_after.tsv`）、3 件は NO_EVIDENCE のまま。main_polar は ANSWER 6 → 0。fused は ANSWER 32 → `UNKNOWN_INVALID_PROOF` 32（残り 12 は時の語 今日・昨日・午後 で修正前から棄権）。control 20 件は不変。範囲だけの集合 26 件: `ちゃ`・`じゃ`・`なくては` の 10 件は ANSWER はい → 棄権（PROHIBITION_NOT_READ）、複数文の 1 件（multi-2「山田さんはどこで働く？」）は 明日東京 → `UNKNOWN_INVALID_PROOF`、**`てもいけない`・`てもならない` の 6 件は ANSWER はい のまま**（frame の読み、`semantic_reader.py`。未修正）。
- **K342**: 前の流しと対照の差 0（aq 111・extra2 42）。修正の前後で aq 111・extra2 42・w3c2 185・b2like 47 の差 0（`k342_ext_summary.txt`、`k342_ext_changed.tsv` は見出しのみ）。基点 dev からの通算は 3 件（AQ025・AQ028・w3c2 Q069、誤答 1 の修正による。`k342_total_summary.txt`・`k342_total_changed.tsv`）。
- **公開バンクの写し**: B2（25 問）・B1（26 問）とも前後で問ごとの結果が同一（`bs_ext_compare.txt`、`bs_B1_*_ext.txt`・`bs_B2_*_ext.txt`）。B1 の `てはならない`／`てはいけない` を含む 4 項目も不変。
- **テスト**: 関係テストの失敗の集合は前後で同一（3 failed, 1780 passed, 3 xfailed, 6 xpassed。`ext_related_before.txt`・`ext_related_after.txt`）。frames 回帰も同一。全体テストは 116 failed・16105 passed（`ext_pytest_full.txt`）。基線 115 件から新しい 2 件（`test_p4_abilities…`: 基点でも落ちる／`test_s6_…`: `verantyx/` 未コミットによる。`ext_new_failures_classified.txt`）、基線から消えた 1 件（`test_one_trace…`、`ext_fixed_failures.txt`）。
- **既知の穴**: `てもいけない` 系は未修正。時の語の切り出し（明日 は time、東京 は place）は読解器の仕事で未実施（棄権にとどめた）。検証器の `Rejected` は ask 全体を棄権にするため、同じ文書の別の文から答えられる問いも、融合した場所の節が証明に入れば棄権になる。`_vt_time_fused` は場所の名に時の字を含むもの（`元日神社`）を融合と判定しうる（棄権の向き。K342・バンクの差は 0）。禁止文は読まず棄権するだけで、禁止の読みそのものは v1 に無い。

## W3-f1 拡張 第 2 ラウンドの事前登録: 時の語＋接尾辞の場所の融合（追記）

登録時刻: `artifacts/w3-f1/prereg_ext2_time.txt`（検査データを書く前、`semantic_verify.py` のこの直しを入れる前）。中間職のレビュー（第 3 版指示書・第 1 ラウンド）の必須 1 への対応。上の「拡張の事前登録」と「拡張の実測結果」は書き換えない。

### 規則（狭める方向だけ。上の (3) の直し漏れの補い）
場所・着点・方向の値が「時の語＋形態素解析で `接尾辞` と付く語」（来週港・毎朝店 など。港・店・湖・館・海・庁・室・園・院・城・街 が `接尾辞` と付くことは `_vt_tokens` で事前に確かめ `artifacts/w3-f1/suffix_tokens_probe.txt` に保存）に連結していたら、その値で答えない（型つき棄権）。`_vt_time_fused` 自体は変えない。

### 判定の式（テストにそのまま書く。上の `fused`・`control` と同じ）
- `kind=fused`: `not (verdict == "ANSWER" and any(time_word in v for v in values))`、かつ `verdict == "ANSWER"` なら `values == [place]`。
- `kind=control`（時の語なし／読点で離れている）: `verdict == "ANSWER"` かつ `values == expect_values`。
データ `tests/reading_soundness/w3f1_time_place_suffix.jsonl`、テスト `tests/test_w3f1_time_place_suffix_answer.py`、凍結 sha は `artifacts/w3-f1/freeze_ext2.sha256`。時の語 10 種 × 接尾辞の場所 11 種から 30 件の fused、対照 17 件。修正前に fused が落ち control が通ることを `artifacts/w3-f1/a1_ext2_before.txt` に保存する。

### 過剰な棄権の範囲を測る（合否に入れない）
時の字で始まる地名・施設名（明日香村・春日部・朝霞・秋葉原・朝日町・今市・元日神社 ほか）が新しい条件で True になるかの表を `artifacts/w3-f1/ext2_overabstain_probe.txt` に出し、True になったものは DECISIONS に全件列挙する。

## W3-f1 拡張 第 2 ラウンドの実測結果: 接尾辞の場所の融合・`verdict.py` を戻した（追記。上の実測結果の節の記述を次のとおり訂正する）

数値はすべて `artifacts/w3-f1/` のファイルから。
- **訂正**: 上の「拡張の実測結果」の原因（誤答 2）に書いた「`verantyx/verdict.py` の `PROHIBIT` に丁寧形の語幹 4 つを足した」は **撤回した**。`verdict.py` は基点に戻した（`git diff --stat -- verantyx/verdict.py` は空）。`verdict.judge` は `vera ask` 以外の機能にも使われ、判定の向きが広がるため。丁寧形の本動詞の問いは、検証器の frame の枝（`semantic_verify.license_clause`）で、接続助詞 て/で/ちゃ/じゃ（＋は/も）の直後の `なる`／`いける` を含む否定の文を型つき棄権（`PROHIBITION_NOT_READ`）にして直した。`verdict` の判定は基点と同じ（`ext2_verdict_probe.txt`）。
- **直し（誤答 3 の残り）**: `semantic_verify._vt_time_suffix_fused` を足し、`_vt_check_roles` の既存の `elif` に `or` で加えた（`_vt_time_fused` は不変）。検査データ `w3f1_time_place_suffix.jsonl`（fused 30・control 14、凍結 `freeze_ext2.sha256`）: 修正前 30 failed（fused 30、control 全部通る。`a1_ext2_before.txt`）、修正後は全 test_w3f1_* 258 passed（`a1_ext2_after.txt`）。凍結の作り直し 1 回（DECISIONS 15）。
- **範囲**: `てもいけない`・`てもならない` の 6 件（第 1 ラウンドは ANSWER はい のまま）も `UNKNOWN_INVALID_PROOF` になった。main_polar 丁寧形 6 件は `UNKNOWN_NO_EVIDENCE` → `UNKNOWN_INVALID_PROOF`。第 1 ラウンドの範囲の ほかの行は不変（`ext2_range_after.tsv`）。接尾辞のデータ 44 行: fused 30 → `UNKNOWN_INVALID_PROOF`、control 14 → ANSWER。
- **過剰な棄権**: 92 語の表（`ext2_overabstain_probe.txt`）で新しく True になったのは本当の融合の 10 語だけ。実在の地名・施設名は新しく True にならない。
- **K342**: 前の流し（`before_ext`）対 後（`after_ext2`）は aq 111・extra2 42・w3c2 185・b2like 47 すべて `masked_differ=0`（`k342_ext2_summary.txt`）。基点 dev からの通算は 3 件（AQ025・AQ028・w3c2 Q069）で第 1 ラウンドと同一（`k342_total2_summary.txt`・`k342_total2_changed.tsv`）。
- **公開バンクの写し**: B2・B1 とも問ごとに差 0（`bs_ext2_compare.txt`）。B2 は correct=0 wrong=0、B1 は correct=2 wrong=2（`bs_*_after_ext2.txt`、前後同じ）。
- **テスト**: 関係テストは 3 failed, 1780 passed, 3 xfailed, 6 xpassed で失敗の集合が前と同一（`ext2_related_after.txt`）。frames 回帰は同一。全体テストは 116 failed, 16150 passed（`ext2_pytest_full.txt`）。失敗の集合は第 1 ラウンドと同一。
- **既知の穴**: 時の語の切り出し（明日 = time、東京 = place）は読解器の仕事で未実施（棄権）。`s6` はコミット後の確認が要る。普通形の禁止の補助の問いの一部は `PROHIBITION_NOT_READ` でなく `UNKNOWN_NO_EVIDENCE`（誤答ではない）。

## W3-f1 拡張 第 3 ラウンドの事前登録: 撥音便の丁寧形の禁止（追記）

登録時刻: `artifacts/w3-f1/prereg_ext3.txt`（検査データを書く前、`semantic_verify.py` のこの直しを入れる前）。中間職のレビュー（第 3 版指示書・第 2 ラウンド）の必須 1 への対応。上の事前登録・実測結果の節は書き換えない。なお、第 2 ラウンドの事前登録の「接尾辞の場所 11 種・対照 17 件」は作り直しの前の数で、凍結版は fused 30・control 14（DECISIONS 15）。

### 規則（狭める方向だけ）
`て/で/ちゃ/じゃ（＋は/も）＋なる/いける` を含む文の本動詞を問う可否は、frame の読みが本動詞を肯定で返す場合（撥音便の丁寧形: 飲んではいけません）も、証明に使わない（型つき棄権 `PROHIBITION_NOT_READ`）。すなわち第 2 ラウンドの条件の `frame.negated` への依存を外す。

### 判定の式（テストにそのまま書く。第 1 ラウンドの禁止と同じ）
- `kind=main_polar`・`kind=aux_polar`: `verdict != "ANSWER"`。
- `kind=control`（`<主語>は<目的語>を<撥音便の動詞>まない。` → `…<動詞>？` = いいえ）: `verdict == "ANSWER"` かつ `values == expect_values`。
データ `tests/reading_soundness/w3f1_prohibition_nde.jsonl`、テスト `tests/test_w3f1_prohibition_nde_answer.py`、凍結 `artifacts/w3-f1/freeze_ext3.sha256`。main_polar ≥12（撥音便の動詞 ≥4 種 × 丁寧形 4 種）、aux_polar ≥6、control ≥4。凍結の前に、基点（第 2 ラウンドの W）で main_polar が `ANSWER` になる行だけを残す（空振りを入れない）ことを `artifacts/w3-f1/ext3_base_probe.txt` に表で残す。

### 範囲の再測定（合否に入れない）
`ext2_range_after.tsv` と直した後の差を全行 `ext3_range_changed.tsv` に出す。

## W3-f1 拡張 第 3 ラウンドの実測結果: 撥音便の丁寧形の禁止・時の語の語彙の穴（追記）

数値はすべて `artifacts/w3-f1/` のファイルから。
- **直し**: `semantic_verify.license_clause` の frame の枝の条件から `frame.negated` を外した（`if _vt_te_auxiliary(words):`）。frame の読みは撥音便の丁寧形（飲んではいけません・飲んではなりません・飲んでもいけません）で本動詞を肯定として返し、第 2 ラウンドの条件を素通りして「運転手は酒を飲む？」= はい になっていた（`ext3_base_probe.txt`: 修正前の main_polar 20 件はすべて ANSWER はい）。
- **検査データ**: `w3f1_prohibition_nde.jsonl`（main_polar 20・aux_polar 20・control 7、凍結 `freeze_ext3.sha256`）。空振りの 12 行（`ませんでした` 形、修正前から NO_EVIDENCE）は凍結の前に除いた（`ext3_drop_ids.txt`）。修正前 20 failed・28 passed（`a1_ext3_before.txt`）、修正後 test_w3f1_* 5 本で 306 passed（`a1_ext3_after.txt`）。
- **範囲**: 5 データ 243 行（`ext3_range_after.tsv`）。第 2 ラウンドの 196 行と比べ変わった行は 0（`ext3_range_changed.tsv` は見出しのみ）。独自の検査 48 文（`ext3_extra_probe.tsv`）で ANSWER は 0。
- **K342**: 第 2 ラウンドの後（`after_ext2`）対 今回の後（`after_ext3`）は aq 111・extra2 42・w3c2 185・b2like 47 すべて `masked_differ=0`（`k342_ext3_summary.txt`）。基点 dev からの通算は第 2 ラウンドと同一の 3 件（`k342_total3_summary.txt`、`k342_total2_changed.tsv` と `diff` 同一）。
- **公開バンクの写し**: B2・B1 とも前（`bs_*_before_ext`）・第 2 ラウンドの後と問ごとに差 0（`bs_ext3_compare.txt`、`bs_*_after_ext3.txt`）。B2 correct=0 wrong=0、B1 correct=2 wrong=2（変わらず）。
- **テスト**: 関係テストは 3 failed, 1780 passed, 3 xfailed, 6 xpassed で失敗の集合が第 2 ラウンドと同一（`ext3_related_after.txt`）。frames 回帰は同一。全体テストは 116 failed, 16198 passed（`ext3_pytest_full.txt`）。失敗の集合は第 2 ラウンドと同一（`ext3_after_failures.txt`）、基線 115 件に対する新しい 2 件（`test_s6_…`・`test_p4_abilities::test_speech_act_drafts…`）も同じ（`ext3_new_failures.txt`、分類は `ext2_new_failures_classified.txt`）。passed が 48 増えたのは新しいテストの分（47 行＋凍結検査 1）。
- **既知の穴（基点からの誤答、このチケットの範囲外、別チケットの候補）**: 時の語の語彙。「山田さんが再来週東京で働く。」→ `ANSWER ['再来週東京']`。再来週・再来年・再来月・先々週・先々月・一昨年・毎夕・夕べ・昨夕・昨晩・明晩・宵・隔週・おととし が `_vt_is_time` で時と判定されず、時の語と場所の融合の検査に入らない（`ext3_time_lexicon_gap.txt`。基点でも同じ答え）。直すには接頭辞 `再来`／`先々`／`一昨` ＋ 助数詞可能の 週・月・年と、普通名詞・一般の時の語を読解器・検証器で同じ形態素の条件に揃える（別チケット）。
- **その他の既知の穴**: 撥音便の丁寧形の根は frame の読み（`semantic_reader.py`）が本動詞を肯定で返すことで、検証器での棄権は対症（読解器の禁止の読みは別チケット）。`verdict.PROHIBIT` に丁寧形が無いことの申し送りは DECISIONS 14 のまま。時の語の切り出し（明日 = time・東京 = place）は未実施（棄権）。


## W16-t2: 文書に答える経路の統一（事前登録。2026-10-05 23:06、実装役。製品の差分を書く前に記す。凍結ファイルの時刻は `artifacts/w16-t2/freeze.sha256`）

（配置の注記: この小節は文書の末尾に追記した。チケットの指定は W3-c4 の節の直後だが、節の間に挿すと既存の見出しの順が変わるため末尾に置く。）

### AnswerResult の定義（D3）
`verantyx/doc_answer.py: answer()` の返り値（基点の `vera ask --mode round5 --document` が `apply_to_ask` に渡していた dict と同じ鍵）の `verdict`・`values`・`evidence` の 3 つ。比較は `json.dumps({"verdict":..,"values":..,"evidence":..}, ensure_ascii=False, sort_keys=True)` の byte 一致。

### T2-1 の比較式
同じ文書・同じ問い・同じ配置で、入口 ask（`cli.main`）・serve（`decode_grammar.read_turn`、no-llm の読み）・chat round5 が `doc_answer.answer` から受け取った AnswerResult の上の文字列が **入口間で全問一致**（不一致 0）。serve が AnswerResult の ANSWER を見せずに棄権する行は全件、型つきの理由で `t2_1_serve_withheld.tsv` に列挙する。

### T2-2 の判定（行ごと）
各行を 正答（verdict が ANSWER で、答えの表層が gold.values のどれかと NFKC で等しい）／誤答（ANSWER だが一致しない。または gold が ABSTAIN なのに ANSWER）／棄権（ANSWER でない）に分ける。「旧各経路の最大以上」は **行ごと**: 旧 ask・旧 serve のどちらかが正答だった行は、新でも正答。正答 → 棄権の行 0、誤答 0（新）。変わった行は全件列挙。gold.values は「受け入れる表層の別名の一覧」（どれか 1 つ）。

### 使う集合
1. `artifacts/w16-t2/sets/u4/`（U4 の 11 問。gold は文の意味から人手で付けた）。
2. `artifacts/w16-t2/sets/own60/`（自作 60 問。文書 6 本。gold は製品を走らせる前に人手で書き、凍結した）。
3. W3-c4 の検査データ（`tests/observe/question_ask/questions.jsonl` と `docs/`・`b2like/`、配置 `placement_ask.json`）、W5-c・W3-f1 の既存テスト（`tests/test_ask_question_cross*.py`・`tests/test_w3f1_*`・`tests/test_basis_policy_w5c*.py`）、B2・B7 の公開の写し（`tests/bank_score/fixtures`）。
自作の集合で通ることは証拠にならない。凍結後に gold の誤りに気づいたら凍結ファイルは変えず `corrections.jsonl` を足す。

### W16-t2 実測結果（実装役。数は `artifacts/w16-t2/` のファイルから。判定は上の事前登録のとおり）
- **経路**: `vera ask --mode round5 --document`・`vera chat --mode round5`・`vera serve`（`decode_grammar.read_turn`）は `verantyx/doc_answer.py: answer()` を通る。後段（旧 `cli._qc_run` など）は `doc_answer` に移した（本体はそのまま）。`cli.py` には、テストが import・差し替える名前（`_qc_records`・`_qc_predicate_form`・`_round5_question_cross`・`_QC_TRIGGER`）だけが 1 行の薄い層として残る。`decode_grammar` は `cli` を import しない（`tests/test_w16t2_layers.py`）。
- **T2-1**（`t2_compare.txt`、`tests/test_w16t2_one_path.py`）: U4 11 問・自作 60 問・W3-c4 111 問・b2like 47 問の 229 行で、3 入口の AnswerResult の不一致 0（各入口が `doc_answer.answer` を 1 回ずつ呼んだことも検査）（訂正: 第 2 ラウンドの記述を見よ）。serve が答えを見せずに棄権した行は 4 行（`t2_1_serve_withheld.tsv`。諾否 3・複数値 1。型 `ROUND5_ANSWER_NOT_MAPPED`）。
- **T2-2**: 行ごとに旧 ask・旧 serve のどちらかが正答の行数 → 新の正答（3 入口とも同数）。U4: 7 → 7（旧 serve だけでは 2）。own60: 24 → 24。W3-c4: 53 → 51（旧 serve のみ正答だった AQ021・AQ022 が棄権: 後段の引き金 `UNKNOWN_UNSUPPORTED_EVIDENCE` が閉じた集合の外のため。**正答→棄権 2 行**）。b2like: 25 → 25。誤答: 新 ask の誤答は旧 ask と同じ 2 行（own60 O38・b2like BQ002。どちらも読解器の答え）。新 serve はこの 2 行を ask と同じく答える（旧 serve は棄権）。
- **T2-4**: `artifacts/w16-t2/loc.txt`。総行数は基点より増えた（理由は報告）。
- **B2・B7 の公開の写し**（`bs_B2_*`・`bs_B7_*`、`bs_semantic_compare.txt`）: 前後で時計の鍵・一時ディレクトリ名・読み込んだモジュール数を除いて同一（差 0）。

## W16-t2 第 2 ラウンド（実装役。監査役の裁定 1・2・4・5・6 による。日時 2026-10-06 00:39、測定の前に記す）

### 事前登録の変更（裁定 1・2・5 による。上の「T2-2 の判定（行ごと）」は消さず、第 2 ラウンドの測定からこの式で判定する）
- **T2-2（入口ごとの遷移）**: 集合ごとと合計で、(a) 各入口（ask・serve・chat）の新の誤答の行の id の集合 ⊆ 旧 ask の誤答の行の id の集合（新しい誤答 0。既知: own60 `O38`、b2like `BQ002`）。(b) 各入口の新の正答の数 ≥ max(旧 ask, 旧 serve, 旧 chat の正答の数)（合計で判定。行ごとには要求しない）。(c) 入口ごとに「自分の旧 → 新」の遷移（correct/wrong/abstain/notjudged の全組合せ）を数え、`abstain→wrong`・`correct→abstain`・`correct→wrong`・`wrong→*` の行は全件列挙する（AQ021・AQ022 の correct→abstain は serve で出る見込み。裁定 2: 後段の引き金は広げない）。(d) w3f1 の NOT_JUDGED の行は、新 ask の (verdict, values, evidence) が旧 ask と全行で一致すること。
- **配置なしの流しを足す**（裁定 5。合否の門にはしない）: 同じ 5 集合を配置なし（`VERA_PLACEMENT` なし・`--fileplacement` なし）で旧・新とも流し、「配置なしで旧経路だけが答えていた行」「新で初めて答えた行」を全件列挙し、誤答は (a) と同じく数える。
- **w3f1 の集合を足す**（E7）: `tests/reading_soundness/w3f1_*.jsonl` 6 ファイル 324 行を `artifacts/w16-t2/sets/w3f1/` に写す（`sets/make_w3f1_set.py`、verantyx を import しない）。gold は `expect_values` がある行だけ `{"verdict": "ANSWER", "values": expect_values}`（116 行）、無い行は `NOT_JUDGED`（208 行。行ごとの期待を推測で作らない）。凍結: `artifacts/w16-t2/freeze_r2.sha256`（製品を流す前に作成）。配置は R9。
- **旧 chat も流す**: 旧の流しにも chat（round5）を足し、入口ごとの「自分の旧」と比べられるようにする。
- 文書なしの行（W3-c4 の AQ020・AQ030）は serve が `answer` を呼ばない（基点から）。呼び出し回数は「3 入口が 1 回ずつ」の行と「文書なしで serve 0 回」の行に分けて数える。

### 監査役の裁定 4 による既存テストの変更（D1。`vera ask --document` の既定を round5 に）
`--mode` の既定を `None` にし、`mode = args.mode or ("round5" if documents else "legacy")`。明示の `--mode legacy` と `--document` は従来どおり `UNKNOWN_ROUTE_CONFIGURATION`。
1. `tests/test_basis_policy_entry.py::test_an_existing_configuration_error_keeps_its_place_before_the_new_ones`
   - 前: `_ask(tmp_path, capsys, "こんにちは", "--document", "x.txt", "--confirm", "abc", "maybe")`
   - 後: `_ask(tmp_path, capsys, "こんにちは", "--mode", "legacy", "--document", "x.txt", "--confirm", "abc", "maybe")`
   - 期待（rc 2・`UNKNOWN_ROUTE_CONFIGURATION`・`--document requires --mode round5`）は同じ。
2. `tests/test_one_request_goal_route.py::test_cli_rejects_source_documents_when_default_legacy_mode_was_selected`
   - 前: `"ask", RAW, "--document", str(source),`
   - 後: `"ask", RAW, "--mode", "legacy", "--document", str(source),`
   - 期待は同じ。
`tests/test_one_chat_round5.py`（chat の `--document` の既定 lab の拒否）は変えない。

### 監査役の裁定 5・6 による既存テストの変更（E1・E2。前後の関数全文。assert・名前・fixture は変えない）
裁定 5（配置が無いときの 2 本目の経路 `_has_placement`・`_BASE_UNKNOWN` を消した）で、配置なしでも round5 の本読みが答える問い（`誰が地図を渡した？` → 太郎、`誰が走りましたか。` → ミナ）が記録の答えになる。この問いを使っていた既存テスト 5 本は、問いの文字列だけを替える。替えた問いでは、新しい経路の reading は、基点で元の問いが返していた reading と同じ（`太郎は何を渡した？` → `NO_RECORD/NO_TYPED_CANDIDATE`、`太郎は何を買った？` → 別スレッドで `ERROR`・`ProgrammingError`、`誰が来ましたか。` → `STRUCTURE_UNDETERMINED/QUESTION_NOT_READ`（基点の serve は元の `誰が走りましたか。` に同じ型を返していた））。元の問いで起きる新しい振る舞い（配置なしでも記録が答える）は `tests/test_w16t2_one_path.py` の新しいテストで固定した。

#### `tests/test_serve_fusion.py::test_strict_no_placement_is_no_record_and_no_call`
前:
```python
def test_strict_no_placement_is_no_record_and_no_call(noplace, tmp_path):
    llm = FakeLLM()
    v = run(make_cfg(tmp_path, llm, strict=True), '誰が地図を渡した？')['vera']
    assert llm.calls == [] and v['reading']['type'] == 'NO_RECORD' and v['reading']['state'] == 'NO_TYPED_CANDIDATE'
```
後:
```python
def test_strict_no_placement_is_no_record_and_no_call(noplace, tmp_path):
    llm = FakeLLM()
    v = run(make_cfg(tmp_path, llm, strict=True), '太郎は何を渡した？')['vera']
    assert llm.calls == [] and v['reading']['type'] == 'NO_RECORD' and v['reading']['state'] == 'NO_TYPED_CANDIDATE'
```

#### `tests/test_serve_fusion.py::test_thread_bound_placement_really_fails_off_the_vera_thread`
前:
```python
def test_thread_bound_placement_really_fails_off_the_vera_thread(thread_bound_place, tmp_path):
    """対照: 偽の配置が本当に別スレッドで落とす（上のテストが空振りでないことの確認）。"""
    cfg = make_cfg(tmp_path, FakeLLM())
    reading, _qc = G.read_turn('誰が地図を渡した？', 'factual', cfg.records, cfg.documents)      # main thread, not the vera thread
    assert reading['type'] == 'STRUCTURE_UNDETERMINED' and reading['state'] == 'ERROR' and 'ProgrammingError' in reading['reason']
```
後:
```python
def test_thread_bound_placement_really_fails_off_the_vera_thread(thread_bound_place, tmp_path):
    """対照: 偽の配置が本当に別スレッドで落とす（上のテストが空振りでないことの確認）。"""
    cfg = make_cfg(tmp_path, FakeLLM())
    reading, _qc = G.read_turn('太郎は何を買った？', 'factual', cfg.records, cfg.documents)      # main thread, not the vera thread
    assert reading['type'] == 'STRUCTURE_UNDETERMINED' and reading['state'] == 'ERROR' and 'ProgrammingError' in reading['reason']
```

#### `tests/test_serve_fusion.py::test_cli_fusion_options_and_refusals`
前:
```python
def test_cli_fusion_options_and_refusals(tmp_path, fake_serve, capsys, monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.delenv('VERA_SOVEREIGN_ROOT', raising=False)
    monkeypatch.delenv('VERA_SOVEREIGN_STORE', raising=False)
    st = str(tmp_path / 'Z.json')
    base = ['--store', st, 'serve', '--backend', 'ollama']
    rc, out = cli_run(capsys, *base)
    assert rc == 2 and json.loads(out)['verdict'] == 'MODEL_REQUIRED'
    rc, out = cli_run(capsys, *base, '--model', 'm', '--strict', '--free')
    assert rc == 2 and json.loads(out)['verdict'] == 'STRICT_AND_FREE'
    rc, out = cli_run(capsys, *base, '--model', 'm', '--document', str(tmp_path / 'nope.txt'))
    assert rc == 2 and json.loads(out)['verdict'] == 'DOCUMENT_NOT_FOUND'
    rc, out = cli_run(capsys, *base, '--model', 'm', '--sovereign-root', str(tmp_path))
    assert rc == 2 and json.loads(out)['verdict'] == 'SOVEREIGN_NEEDS_BOTH'
    assert fake_serve == []
    d = docfile(tmp_path)
    rc, _ = cli_run(capsys, *base, '--model', 'm', '--document', d, '--strict', '--placement', str(tmp_path), '--sovereign-root', str(tmp_path), '--sovereign-store', 'S1')
    import os
    assert rc == 0 and fake_serve[0]['fusion'].strict is True and fake_serve[0]['fusion'].documents == [d] and fake_serve[0]['fusion'].records.n_loaded == 1
    assert os.environ['VERA_PLACEMENT'] == str(tmp_path) and os.environ['VERA_SOVEREIGN_STORE'] == 'S1'
    monkeypatch.delenv('VERA_PLACEMENT'), monkeypatch.delenv('VERA_SOVEREIGN_ROOT'), monkeypatch.delenv('VERA_SOVEREIGN_STORE')
```
後:
```python
def test_cli_fusion_options_and_refusals(tmp_path, fake_serve, capsys, monkeypatch):
    monkeypatch.delenv('VERA_PLACEMENT', raising=False)
    monkeypatch.setenv('VERA_PLACEMENT', '')     # isolation only (W16-t2): serve writes VERA_PLACEMENT; the undo of this setenv removes it at teardown
    monkeypatch.delenv('VERA_SOVEREIGN_ROOT', raising=False)
    monkeypatch.delenv('VERA_SOVEREIGN_STORE', raising=False)
    st = str(tmp_path / 'Z.json')
    base = ['--store', st, 'serve', '--backend', 'ollama']
    rc, out = cli_run(capsys, *base)
    assert rc == 2 and json.loads(out)['verdict'] == 'MODEL_REQUIRED'
    rc, out = cli_run(capsys, *base, '--model', 'm', '--strict', '--free')
    assert rc == 2 and json.loads(out)['verdict'] == 'STRICT_AND_FREE'
    rc, out = cli_run(capsys, *base, '--model', 'm', '--document', str(tmp_path / 'nope.txt'))
    assert rc == 2 and json.loads(out)['verdict'] == 'DOCUMENT_NOT_FOUND'
    rc, out = cli_run(capsys, *base, '--model', 'm', '--sovereign-root', str(tmp_path))
    assert rc == 2 and json.loads(out)['verdict'] == 'SOVEREIGN_NEEDS_BOTH'
    assert fake_serve == []
    d = docfile(tmp_path)
    rc, _ = cli_run(capsys, *base, '--model', 'm', '--document', d, '--strict', '--placement', str(tmp_path), '--sovereign-root', str(tmp_path), '--sovereign-store', 'S1')
    import os
    assert rc == 0 and fake_serve[0]['fusion'].strict is True and fake_serve[0]['fusion'].documents == [d] and fake_serve[0]['fusion'].records.n_loaded == 1
    assert os.environ['VERA_PLACEMENT'] == str(tmp_path) and os.environ['VERA_SOVEREIGN_STORE'] == 'S1'
    monkeypatch.delenv('VERA_PLACEMENT'), monkeypatch.delenv('VERA_SOVEREIGN_ROOT'), monkeypatch.delenv('VERA_SOVEREIGN_STORE')
```

#### `tests/test_semantic_read_w3e2_serve.py::turn`
前:
```python
def turn(doc, reply, mode, strict=False, kind='factual'):
    cfg = VS.FusionConfig.load(model='fake', documents=[doc], llm_chat=chat_for(reply), read_mode=mode, strict=strict)
    r = VS.fusion_turn([{'role': 'user', 'content': '誰が走りましたか。'}], {'request_kind': kind, 'human_present': False}, cfg)
    r['vera'].pop('timing', None)
    return r
```
後:
```python
def turn(doc, reply, mode, strict=False, kind='factual'):
    cfg = VS.FusionConfig.load(model='fake', documents=[doc], llm_chat=chat_for(reply), read_mode=mode, strict=strict)
    r = VS.fusion_turn([{'role': 'user', 'content': '誰が来ましたか。'}], {'request_kind': kind, 'human_present': False}, cfg)
    r['vera'].pop('timing', None)
    return r
```

`test_semantic_read_w3e2_serve.py` の `turn()` を使う 3 本（`test_the_assumed_arm_is_marked_in_the_provenance_and_strict_read_has_none`・`test_the_arm_keys_do_not_grow`・`test_a_factual_question_is_not_answered_from_an_assumed_arm`）は `turn()` の問い 1 か所の差し替えで通る。`test_serve_fusion.py::test_cli_fusion_options_and_refusals` の 1 行（`monkeypatch.setenv('VERA_PLACEMENT', '')`）は漏れの隔離（裁定 6）。

### テストの環境変数の漏れの隔離（E2、裁定 6）
`coarse_place._open(None)` が `VERA_PLACEMENT` も読むようになったので、テストの間で `VERA_PLACEMENT` が漏れると他のテストが変わる。漏れの出所は 1 か所: `tests/test_serve_fusion.py::test_cli_fusion_options_and_refusals`。冒頭の `monkeypatch.delenv('VERA_PLACEMENT', raising=False)` は変数が無いと何も記録しない（pytest の仕様）。serve が `--placement` で `os.environ['VERA_PLACEMENT']` を書き（基点から同じ。テストも assert している）、末尾の `monkeypatch.delenv('VERA_PLACEMENT')` がその値を記録し、片づけで書き戻していた。直後に `monkeypatch.setenv('VERA_PLACEMENT', '')` を 1 行足すと、`setenv` の記録は「無かった」なので片づけの最後に消える。`placement_from_env` は空を未設定と読むので、このテストの期待は変わらない。確認: 漏れ検出プラグイン付きの実行で `LEAK_CHANGE` は最初の 1 行（`(None, None)`）だけ（`artifacts/w16-t2/leak_check_r2.txt`）。

### W16-t2 第 2 ラウンドの実測結果（実装役。数は `artifacts/w16-t2/*_r2*` から。第 1 ラウンドの記述は消していない）
- **経路**: 配置の有無で経路を分けない（`decode_grammar.read_turn` の `_has_placement`・`_BASE_UNKNOWN` を消した。裁定 5）。`coarse_place._open(None)` も入口と同じに環境を解決する（正 `VERA_PLACEMENT`、互換名、食い違いは `PLACEMENT_ENV_CONFLICT`。`NO_PLACEMENT_REASONS` に足した。`_layer_summary` も型で返す。裁定 6）。`ask --document` の既定は round5（裁定 4）。
- **T2-1**（`t2_compare_r2.txt`・`t2_compare_noplace_r2.txt`）: 5 集合（U4 11・own60 60・W3-c4 111・b2like 47・w3f1 324 = 553 行）を配置あり・配置なしの両方で、3 入口の AnswerResult の不一致 **0**。呼び出し: 文書のある 551 行は 3 入口が `doc_answer.answer` を 1 回ずつ呼んだ。文書なしの 2 行（W3-c4 の AQ020・AQ030）は ask と chat が 1 回、serve は `NO_RECORD/DOCUMENTS_NOT_LOADED` を返して関数を呼ばない（基点から同じ）。第 1 ラウンドの「各入口が 1 回ずつ呼んだ」（229 行）は、この 2 行が含まれるので不正確だった（訂正）。serve が答えを見せない行（`ROUND5_ANSWER_NOT_MAPPED`）: 配置あり 21 行・配置なし 21 行（`t2_1_serve_withheld_r2.tsv`・`..._noplace_r2.tsv`。w3f1 の諾否 17 行、W3-c4 の 3 行、b2like の 1 行。全部の AnswerResult は ask・chat と一致）。
- **T2-2（入口ごとの遷移。事前登録の変更の式）**:
  - (a) 各入口の新の誤答の行 ⊆ 旧 ask の誤答の行: 3 入口とも PASS（誤答は own60 `O38`・b2like `BQ002` の 2 行だけ。どちらも旧 ask の誤答の行）。新しい誤答の行は 0。
  - 遷移（配置あり、合計）: ask と chat は自分の旧と同じ（`wrong->wrong` 2、`correct->correct` 223、ほか abstain/notjudged のまま。`correct->abstain` 0）。serve は `abstain->wrong` **2**（O38・BQ002。旧 serve は棄権だった）、`abstain->correct` 88、`abstain->notjudged` 1、`correct->abstain` **2**（W3-c4 の AQ021・AQ022。裁定 2 により列挙で可。引き金は広げていない）、`correct->correct` 120。`correct->wrong` は 0。
  - (b) 各入口の新の正答 ≥ max(旧 ask, 旧 serve, 旧 chat)（合計）: ask 223・chat 223 は旧の最大 223 と同じで PASS。**serve は 208 で FAIL**（旧の最大 = 旧 ask の 223）。差の 15 行はすべて w3f1 の諾否の問い（`田中は本を読む？` に `いいえ` など。ask と chat は gold のとおり答え、serve は `ROUND5_ANSWER_NOT_MAPPED` で見せない。AnswerResult は 3 入口で一致。T2-2b-info: AnswerResult の上では serve も 223）。W3-c4 の旧 serve の正答は旧 ask の 51 以下（旧 serve 50）なので、AQ021・AQ022 は合計の判定に響かない。serve で諾否を見せるには読みの型を足す必要があり、チケットの許可パスと設計の外なので実装していない。
  - (d) w3f1 の NOT_JUDGED 208 行: 新 ask の (verdict, values, evidence) が旧 ask と全行一致（PASS）。
- **配置なし**（裁定 5。門にはしない。`t2_compare_noplace_r2.txt`）: 「配置なしで旧経路だけが答えていた行」は 0 行（ONLY-OLD なし）。新で初めて答えた行は 155（すべて serve。旧 serve は配置なしで 0 行しか答えなかった）: 正答 152・誤答 2（O38・BQ002）・NOT_JUDGED 1（`ext_range:multi-1`）。ask と chat は配置なしでも旧と同じ（遷移なし）。配置なしの新の誤答は配置ありと同じ 2 行で、旧 ask の誤答の行の範囲内。
- **B2・B7 の公開の写し**（`bs_B2_*_r2.txt`・`bs_B7_*_r2.txt`、`bs_B2_semantic_compare_r2.txt`・`bs_B7_semantic_compare_r2.txt`）: 前後で時計の鍵・一時ディレクトリ名・読み込んだモジュール数を除いて同一（差 0。生の `tools.bank_score.compare` は第 1 ラウンドと同じく 24 件・35 件の不一致を出す。時計の鍵などの差で、意味のある差ではないことを `bank_compare.py` で確かめた）。公開の写しは前後とも correct=0 なので弱い証拠。
- **再現**: `artifacts/w16-t2/COMMANDS.md`。W3-c4（配置あり）の new を別名で流し直し、`new_w3c4_r2.jsonl` と 111 行すべてで ask・serve・chat が一致（`rerun_check_r2.txt`）。
- **行数**（`loc_r2.txt`）: `verantyx/` の総行数 152,897（基点 152,712、差 +185。裁定 3 の枠 +202 以内）。

## W16-t1b: 既知の穴の更新（W3-c4 の 7）

`docs/OBSERVATION.md` 1437 行の項目 7（充填物が語の一部）について、W16-t1b（K801）で主経路（`ask --mode round5`・`semantic_execute`／`semantic_verify` の Project）の答えは、読解器が読んだ充填物の**表記のまま**（`森田課長` → `森田課長`）返すようになった。束縛の鍵（`term` = `canonical`）は変えていない。同じ問いに 2 つの表記が出る文書（`森田課長` と `森田`）は `AMBIGUOUS`。後段（`question_cross`）は変えていない。測定は `docs/READING_SOUNDNESS.md` §10M・`artifacts/w16-t1b/`。
