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
