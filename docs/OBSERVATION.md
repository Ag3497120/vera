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

`python -m verantyx.cli observe --anchor-text '母は台所で何を作った？' --anchor-kind question --structure tests/observe/question/docs/QD05.jsonl --no-index`（FILLED）
```json
{
 "exit_code": 0,
 "focus": {
  "kind": "FOCUS"
 },
 "answer.status": "FILLED",
 "answer.question": {
  "hole_role": "patient",
  "hole_type": [
   "ABSTRACT",
   "ANIMAL",
   "ARTIFACT",
   "BODY_PART",
   "EVENT_ACT",
   "IDENTIFIER",
   "INFO_LANGUAGE",
   "NATURAL_PHENOMENON",
   "PLACE",
   "PLANT",
   "QUANTITY",
   "STATE_PROPERTY",
   "SUBSTANCE_FOOD",
   "TIME",
   "WORK"
  ],
  "wh": "何",
  "kind": "WH_QUESTION",
  "restrictor": null,
  "hole_mark": "Ｘ"
 },
 "answer.fillers": [
  {
   "surface": "料理",
   "evidence": [
    {
     "reading": "QD05-S06",
     "cross_index": 0,
     "text": "母は台所で料理を作った。"
    }
   ],
   "hole_type_check": "NOT_CHECKED:NO_PLACEMENT"
  }
 ],
 "answer.structure": {
  "sentences": 10,
  "crossed": 9,
  "unread": 1,
  "unread_ids": [
   "QD05-S10"
  ],
  "crosses_compared": 9,
  "crosses_matched": 1,
  "extending": []
 },
 "answer.reasons": [
  "UNREAD_SENTENCES:1"
 ],
 "abstain": null
}
```

`python -m verantyx.cli observe --anchor-text '誰が生徒に地図を渡した？' --anchor-kind question --structure tests/observe/question/docs/QD01.jsonl --no-index`（TIE）
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
   "hole_type_check": "NOT_CHECKED:NO_PLACEMENT"
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
   "hole_type_check": "NOT_CHECKED:NO_PLACEMENT"
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
12. `vera ask --mode round5 --document` につながっていない（このチケットの範囲外）。
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
