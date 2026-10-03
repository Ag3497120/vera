# 記憶のソブリン (W4-m)

人ごとの独立した貯蔵。**中は追記専用、単位としては利用者のもの**。同意のあるときだけ、繰り返し観測された未占有の升や言い回しを、出所つきで構造へ昇格できる。設計の原点は `.claude/vera-audit/DESIGN_OBSERVATION.md` §2.5。実装は `verantyx/sovereign.py` の末尾の節（W4-m の区切りコメントから下）。

事前登録: `artifacts/w4-m/PREREG_W4m_promotion.md`（時刻とハッシュは `artifacts/w4-m/prereg.txt`）。

## 名前の衝突（先に読む）
`sovereign` は dev に何度も出てくる。この文書の「ソブリン」は記憶の貯蔵で、次のどれとも別物。

- `verantyx/sovereign.py` の上半分（`build_sovereign` `assemble` `verify` ほか）: 文書から連合の木を組む機能。同じファイルの上の節で、名前も挙動も変えていない。
- `verantyx/constellation.py` の `class Sovereign` と `full_sovereign.py`: 星座の別概念。
- MCP の扉 `vera_sovereigns`・読解の出所欄 `"sovereign": "document"`: 出所の系列名。
- `content_ir.py` の `class Ledger`、`conductor_run.py` の `LedgerError`: 別の台帳。

## 階層: なぜ中は追記専用で、単位は手放せるのか
2 つの原則がぶつかる。「削除しない（退役は追記）」と「利用者はいつでも削除できる」。行を消すことと貯蔵を手放すことを **別の階層** に置いて解く。

| 階層 | 規則 | 誰が |
|---|---|---|
| 貯蔵の中（行） | 追記専用。UPDATE / DELETE / 置換は DB の層で拒否 | Vera も利用者も行は書き換えない（訂正は前進の追記） |
| 貯蔵という単位（ファイル） | 切り離す・持ち出す・手放す | 利用者のもの |

手放し（`release`）は **利用者の明示の指示**（`--confirm <store_id>`）で起きる。Vera がすることは、参照を切る、台帳に `RELEASE` とファイルのハッシュを追記する、そのソブリン由来の昇格分を退役の追記にする、の 3 つだけ。**ソブリンのファイルには触れず、消さない。消すのは持ち主の操作**。Vera のコードには `unlink` `rmtree` `DROP` `DELETE FROM` が無い（`tests/test_sovereign_store.py::test_the_new_code_never_deletes_or_drops_and_uses_no_clock_or_randomness` が節の全文を検査する）。

## ファイルの配置と表
```
<root>/structure.sqlite            構造の側の台帳（registry_log, promotion_log, retire_log）。追記専用
<root>/stores/<store_id>.sqlite    ソブリン 1 つ = 1 ファイル（meta, consent_log, event_log, promotion_log）。追記専用
```
- `<root>` は CLI では `--root` が必須で、既定値は無い。Vera が書く場所は `--root` の中だけ（`export` が利用者の指した 1 か所へ書くのは別）。
- どのソブリンが「構造から読める」かは、ソブリンのファイルの外にある `registry_log` が決める。状態は registry の行を seq 順に畳んだもの: `CREATE`/`ATTACH` → ACTIVE、`DETACH` → DETACHED、`RELEASE` → RELEASED（`EXPORT` は変えない）。RELEASED は動かない。
- 標準ライブラリだけ（`sqlite3` `hashlib` `json` `shutil` `datetime` ほか）。接続は操作ごとに開いて閉じる。WAL にしない。`VACUUM` を呼ばない。
- 全表の主キーは `seq INTEGER PRIMARY KEY` だけで、**他に UNIQUE・主キーを作らない**。全表に 3 本のトリガ: `<表>_next_seq`（次の seq 以外の INSERT を拒否: 同じ seq の置換・飛んだ seq・seq 省略・`OR IGNORE`）、`<表>_no_update`、`<表>_no_delete`。UNIQUE を持つ表では `INSERT OR REPLACE` が次の seq のトリガを通ったうえで古い行を黙って消せる（中間職が測定済み。`plan.md` §1.4）ので、UNIQUE を作らない。event id は列に持たず `"<store_id>:<seq>"` で導く。
- ソブリンの `meta` は 1 行だけ（`meta_single`）。`payload` は `sort_keys=True, ensure_ascii=False, separators=(",",":"), allow_nan=False` の json で保存する。
- ハッシュ: `file_sha256` はファイルのバイト列、`content_sha256` は 4 表を表名の固定順・seq 順に正準 json にした列。
- **構造の側の台帳の識別子 `structure_ref`**: `registry_log` の最初の行（追記専用なので動かない）の正準 json の sha256。乱数・uuid は使わない（決定的）。構造の側の台帳に書く行はすべて、`detail` に **その root の絶対パス（`root`）** を持つ（`_sov_registry_append` が入れる。行ごとに入れる方を選んだ: 最初の行にだけ入れるより、書き方の経路が 1 つで済む）。最初の行が `attach --file` のとき、path は持ち出したファイルの場所で root を含まない。root を含めないと、同じファイルを同じ秒に 2 つの新しい root へ attach した最初の行が byte 単位で同じになり、値も同じになる（レビュー第 2 ラウンドで CLI から再現した）。root の絶対パスが入るので、同時に存在する 2 つの root は値が違う。ソブリン側の `promotion_log` の back-link は `structure_seq` に加えてこの `structure_ref` を持つ。ソブリンのファイルは export → 別の root で attach で動くので、`structure_seq` だけでは「どの台帳の何行目か」が決まらず、別の人の昇格の行を指してしまう（レビュー第 1 ラウンドで再現した）。

## 形の検査
トリガは Vera 自身の経路と誤操作を止めるもので、ファイルの持ち主が `DROP TRIGGER` すれば外れる。それは **止められないが検出する**: ソブリンのファイルも構造の側の台帳も、open・attach・export・release の前に、表とトリガの名前と `sql` が期待（モジュールの定数）と一致するか、meta が 1 行で store_id が合うかを検査する。合わなければ `UNREADABLE_SCHEMA`（欠けた名前・余分な名前・違う名前を `detail` に）、SQLite でなければ `UNREADABLE_NOT_SQLITE`。

## 型で分ける「読めない」
`SovereignUnavailable(LookupError)` の下位で、どれも `.verdict` を持つ。空の列や `None` に化けない。

| 型 | verdict | 意味 |
|---|---|---|
| `UnknownStore` | `UNKNOWN_STORE` | この root に登録が無い |
| `Detached` | `DETACHED` | 利用者が切り離した |
| `Released` | `RELEASED` | 手放した（ファイルを利用者が消した後も RELEASED のまま） |
| `FileMissing` | `UNREADABLE_FILE_MISSING` | 登録は ACTIVE だがファイルが無い |
| `SchemaMismatch` | `UNREADABLE_SCHEMA` | 形が違う |
| `NotSqlite` | `UNREADABLE_NOT_SQLITE` | SQLite でない |

そのほか `UnknownSince`（`since` がこの台帳の id でない）と `LedgerRefusal`（`BAD_KIND` `BAD_PAYLOAD` `EXTRA_KEYS` `UNKNOWN_CORRECTS_TARGET`）。構造の側の台帳が無い（`status` が `structure: ABSENT`）ことと、ソブリンが無いこと（`UNKNOWN_STORE`）も別の答え。

## `Ledger` Protocol（W3-c と共有）
```python
class Ledger(Protocol):
    def append(self, event) -> str                  # {"kind","payload"} だけ。返り値は event id
    def events(self, since=None) -> Iterable        # seq の昇順
    def count(self, key, value) -> int              # payload[key] == value（型も一致）の事件の数
    def last_seq(self, key, value) -> int | None
```
`SovereignLedger`（`open_ledger(root, store_id, now=None)` だけが作る）が永続の実装。**すべての呼び出しの最初に構造の側の台帳で状態を引き直す**ので、開いたまま detach されたハンドルも読めない（`Detached`）。

- `append`: `kind` は `utterance` / `observation` / `decision`。鍵が `kind`・`payload` 以外（`seq`・`ts` を呼び手が渡すのも含む）なら `EXTRA_KEYS`。payload は json 往復で変わらないものだけ。
- 訂正は `payload["corrects"] = <この台帳の既存の id>` を持つ前進の追記。元の行は残る。存在しない id は `UNKNOWN_CORRECTS_TARGET`。`count`/`last_seq` は生の数で、訂正された事件も数える（昇格の数え上げでは数えない）。
- `ts` は UTC の ISO 8601 秒精度。`now`（tz つき datetime を返す関数）を差し込める（試験用）。tz の無い時刻は拒否。CLI からは差し込めない。
- W3-c の統合は未了なので、Protocol の 4 関数だけを使う参照の読み手 `tests/sovereign/sov_protocol_reader.py` と、メモリ上の参照実装 `tests/sovereign/sov_memory_ledger.py` で確かめた。W3-c の入口（`observe.py`・`salience.py`）での確認は **未測定**（`NOT_MEASURED_W3C_NOT_INTEGRATED`）。

### W3-c へ寄せる点（寄せ待ち）
- `events(since)` の意味: ここでは「その事件より後（含まない）」で、この台帳の id でなければ `UnknownSince`。W3-c の `MemoryLedger` とずれていたら統合時に寄せる。
- 昇格の候補の鍵名 `cell` / `occupied` / `phrase` は W3-c の `Observation.cell`/`occupied` に合わせた仮の名前。
- `Ledger` の定義は、チケットの指定どおり `verantyx/sovereign.py` に自分で定義した（W3-c と同じ名前・同じ署名）。統合時に片方へ寄せる。

## 操作
入口は `python -m verantyx.cli sovereign <op>`（`--root` 必須）。出力は stdout に 1 行（`events` だけ 1 事件 1 行）。終了コード: 型つきの結果で終われば 0、拒否・不可・読めないは 1、引数の誤りは 2。

| 操作 | 成功の verdict | 拒否・不可 | 書くもの |
|---|---|---|---|
| `create --store-id S --owner O [--consent-promote]` | `CREATED` | `REFUSED_BAD_STORE_ID` `REFUSED_STORE_ID_TAKEN`（状態を問わない）`REFUSED_FILE_EXISTS` | ソブリンのファイル、registry `CREATE` |
| `consent --store-id S --promote on\|off` | `CONSENT_RECORDED` | 読めない型 | ソブリンの `consent_log` |
| `append --store-id S --kind K --payload '<json の 1 行>'` | `APPENDED` | `BAD_KIND` ほか | ソブリンの `event_log` |
| `events --store-id S [--since ID]` | （各事件の行） | `DETACHED` `RELEASED` `UNKNOWN_SINCE` ほか | 書かない |
| `detach --store-id S` | `DETACHED` / `ALREADY_DETACHED` | `UNKNOWN_STORE` `RELEASED` | registry `DETACH`。ファイルには書かない |
| `attach (--store-id S \| --file PATH)` | `ATTACHED` / `ALREADY_ACTIVE` | `REFUSED_RELEASED` `REFUSED_STORE_ID_CONFLICT` `UNKNOWN_STORE` 読めない型 | registry `ATTACH`（`same_as_detached`）。**複製しない** |
| `export --store-id S --to PATH` | `EXPORTED` | `REFUSED_DESTINATION_EXISTS` `REFUSED_DESTINATION_PARENT_MISSING` `REFUSED_HOT_JOURNAL` `DETACHED` `RELEASED` 読めない型 | `PATH` へ 1 ファイルのバイト複製、registry `EXPORT` |
| `release --store-id S --confirm S` | `RELEASED` / `ALREADY_RELEASED` | `REFUSED_NOT_CONFIRMED` `UNKNOWN_STORE` | 退役の追記、registry `RELEASE`（ハッシュ）。**ファイルに触れない** |
| `promote --store-id S [--min-count N] [--min-days D]` | `PROMOTED` / `NOTHING_TO_PROMOTE` / `NO_CONSENT` | `REFUSED_BAD_THRESHOLDS` と状態の型 | 構造の側とソブリンの側の `promotion_log` |
| `status [--store-id S]` | `ANSWER` | `UNKNOWN_STORE` | 書かない |
| `promotions [--store-id S] [--all]` | `ANSWER`（`structure: PRESENT` / `ABSENT`） | `UNKNOWN_STORE`（登録の無い store_id。rc=1） | 書かない（台帳の無い root にも何も作らない） |

- `detach`: 構造からの参照を切って読めなくするだけ。ファイルは残る。`attach --store-id` で戻り、ファイルが切り離しの間に変わっていたかを `same_as_detached` に記録する（違っても拒否しない）。detach は **昇格分を退役させない**（戻せる操作だから。判断記録 D11）。
- `export`: 複製の前後でバイト列の sha256 を比べる。書き込み用に開いたままのファイルを複製しないよう、`-journal`/`-wal`/`-shm` があれば複製せず `REFUSED_HOT_JOURNAL`。宛先が在れば拒否（上書きしない）。宛先の親は作らない。
- `attach --file`: 持ち出した 1 ファイルを **その場所のまま** 登録する。私的データの写しを増やさない。登録済みの store_id なら `REFUSED_STORE_ID_CONFLICT`、この root で RELEASED なら `REFUSED_RELEASED`（別の root では読み直せる）。
- `release`: 手放した後の再 attach は同じ root では拒否する（`REFUSED_RELEASED`）。退役は取り消さない。ファイルが既に無くても `RELEASE` は書け、`file_state: MISSING` と最後に知っていたハッシュ `last_known_file_sha256` を記録する。2 回目は `ALREADY_RELEASED`（残っている未退役の昇格分があれば退役させて `retired_on_rerun` に数える）。

### 実行例（`artifacts/w4-m/cli_demo.txt` から。値は実行結果の貼り付け）
```
$ vera sovereign create --root R --store-id s1 --owner owner-a
{"consent_promote": false, "content_sha256": "3be6bd06…302a", "file_sha256": "cc2e4928…7044", "owner": "owner-a", "path": "R/stores/s1.sqlite", "registry_seq": 1, "store_id": "s1", "verdict": "CREATED"}
$ vera sovereign promote --root R --store-id s1          # 同意なし: 何も書かない, rc=0
{"consent": {"promote": false, …}, "store_id": "s1", "thresholds": {"d": 2, "n": 3, "source": "prereg"}, "verdict": "NO_CONSENT", "wrote": 0}
$ vera sovereign detach --root R --store-id s1
{"file_left_in_place": "R/stores/s1.sqlite", "file_sha256": "b1b36235…8932", "file_state": "PRESENT", "registry_seq": 2, "store_id": "s1", "verdict": "DETACHED"}
$ vera sovereign events --root R --store-id s1           # rc=1
{"store_id": "s1", "verdict": "DETACHED"}
$ vera sovereign attach --root R --store-id s1
{"…": "…", "same_as_detached": true, "store_id": "s1", "verdict": "ATTACHED"}
$ vera sovereign export --root R --store-id s1 --to R2/s1.sqlite
{"content_sha256": "e3f46283…3c9a", "file_sha256": "b1b36235…8932", "registry_seq": 4, "store_id": "s1", "to": "R2/s1.sqlite", "verdict": "EXPORTED"}
$ vera sovereign attach --root R2 --file R2/s1.sqlite
{"…": "…", "same_as_detached": null, "store_id": "s1", "verdict": "ATTACHED"}
$ shasum -a 256 R/stores/s1.sqlite R2/s1.sqlite          # 同じ
b1b36235…8932  R/stores/s1.sqlite
b1b36235…8932  R2/s1.sqlite
$ vera sovereign release --root R --store-id s1 --confirm wrong    # rc=1, 何も書かない
{"store_id": "s1", "verdict": "REFUSED_NOT_CONFIRMED", …}
$ vera sovereign release --root R --store-id s1 --confirm s1       # rc=0
{"file_left_in_place": "R/stores/s1.sqlite", "file_sha256": "b1b36235…8932", "file_state": "PRESENT", …, "verdict": "RELEASED"}
$ shasum -a 256 R/stores/s1.sqlite; test -f R/stores/s1.sqlite && echo FILE_LEFT_IN_PLACE
b1b36235…8932  R/stores/s1.sqlite
FILE_LEFT_IN_PLACE
$ vera sovereign events --root R --store-id s1                     # rc=1
{"store_id": "s1", "verdict": "RELEASED"}
```
（`…` は紙面の省略。全文は `artifacts/w4-m/cli_demo.txt`。）

## 同意の意味
- **既定は同意なし**。`create` は `--consent-promote` が無ければ昇格を許さない。同意は `consent_log` への追記で変わり、最新の行が効く。行は `ts`・`promote`・`since_seq`（その時点の `event_log` の最後の seq）を持つ。
- **同意の窓**: 昇格で数えるのは、最新の同意（真）の `since_seq` より後の事件だけ。同意の前に話したことは同意の対象にしない（`outside_consent_window` に数える）。再び同意し直せば窓はそこから始まり直す。**真のままもう一度「真」を記録しても窓は今に動く**（`consent` は前の状態を問わず `since_seq` をその時点の最後の seq にする。それまでの数え上げは窓の外になる）。窓を動かしたくなければ、同意は変えずに置く。
- **撤回**: 同意を偽にすると以後の `promote` は `NO_CONSENT` で何も書かない。既に昇格した分は撤回では退役させない（`release` まで退役させない）。撤回でも退役させるべきかは監査役への問い。
- **同意して昇格した言い回しは構造の側へ写り、`release` 後も退役の行として構造の側に残る。Vera は消さない**。退役は削除ではなく「以後の観測の候補から外す」追記で、昇格の行も退役の行も残る。ソブリンのファイルを持ち主が消しても、構造の側の写し（と、その出所 `conversation:<store_id>`）は残る。残したくない場合に構造の側の台帳をどう扱うかは持ち主（と監査役）の決めることで、Vera は自分からは消さない。

## 昇格 `promote` のしきい値（事前登録。方針値で、実測にもとづく値ではない）
- 回数 **n = 3**、別の日 **d = 2**。根拠は方針だけ: d = 2 は「別の日」の文字どおりの最小、n は d から自動では満たされない最小の n = d + 1。どの標本にも当てて調整していない。`artifacts/w4-m/PREREG_W4m_promotion.md` §1。
- `--min-count`・`--min-days` で上書きできる。そのとき出力と構造の側の `promotion_log.thresholds` に `"source": "override"` が残る（既定は `"prereg"`）。
- 「別の日」は `ts[:10]`（UTC の日付）の異なり数。23 時間離れていても同じ UTC の日付なら 1 日。
- 候補の形（事前登録 §3）: placement_evidence = `kind=="observation"` で `payload["cell"]` があり `payload["occupied"]=="UNOCCUPIED"`（鍵は cell の正準化した文字列）。construction_evidence = `kind=="utterance"` で `payload["phrase"]` が空でない文字列（鍵は phrase そのもの、正規化しない）。同じ cell に `UNOCCUPIED` 以外の `occupied` が 1 件でもあれば昇格しない（`conflicting_occupancy`）。`occupied` が無い・`UNKNOWN_*` だけの cell は `unknown_occupancy`。
- 昇格の宛先は **型だけ**: `PromotionRecord(store_id, kind, payload, basis="conversation:<store_id>")`。配置への実際の取り込み（W3-a2 の `generated` と同列の「推定（会話）」）は、`docs/COARSE_PLACEMENT.md` の契約が固まってから別チケット。
- 1 件ごとに、構造の側 `promotion_log`（出所・件数・日数・evidence の event id・しきい値）と、ソブリンの側 `promotion_log`（`promotion_id`・`structure_seq`・evidence）の **両方** に追記する。`promotion_id = sha256("<store_id>\x1f<kind>\x1f<key>")` の先頭 24 桁（決定的）。`trace_promotion(root, promotion_id)` が両側と退役の行をまとめて返す。ソブリン側の back-link は `structure_ref`（この root の構造の側の台帳の識別子）を持ち、`rows` に入るのは **`structure_ref` が一致し、かつ `structure_seq` の行の `promotion_id` が同じもの** だけ。別の台帳を指すもの（export → 別の root で attach したファイルが運んできた分）は `other_structures`、同じ台帳を指すのに行が合わないものは `mismatched` に、捨てずに別に返す。
- 構造の側だけ書いて落ちた状態は、次の `promote` が `repaired_backlink` として修復する（ソブリンの側だけ追記する）。修復の判定は **この root の `structure_ref` を持ち、`structure_seq` が同じ行を指す back-link があるか** だけを見る（別の root で書かれた back-link が同じ `promotion_id` を持っていても、修復を止めない）。
- `release` が退役を書いて `RELEASE` を書く前に落ちた状態（ソブリンはまだ ACTIVE）で `promote` を打つと、同じ `promotion_id` が退役の行と生きた行に分かれてしまうので、`RELEASE_IN_PROGRESS` を返して何も書かない（rc=1）。同じ `release --confirm` をもう一度打つと揃う。この判定は「ACTIVE なのに、このソブリンの退役の行がある」なので、持ち主が外から `retire_log` に正規の追記をした場合にも `promote` が止まる（止まっても `release --confirm` で解ける）。
- **読み飛ばしを残さない**: 事件はどれも 1 つの分類に入る。`events_total = outside_consent_window + superseded_by_correction + not_a_candidate + below_count + below_days + conflicting_occupancy + unknown_occupancy + already_promoted + promoted_events`（`tests/test_sovereign_promote.py` が等式を確かめる）。訂正された事件は数えず `superseded_by_correction` に入れる。
- 同点・順序で勝者を作らない: しきい値を満たすものは全部昇格し、順位づけは無い。返す `promoted` の並びは最初の evidence の seq の順で、表示のため。

## 退役
`release` で、そのソブリン由来の退役していない昇格を、構造の側の `retire_log` に追記する（`reason: RELEASED`、`registry_seq`）。昇格の行は消えない。`active_promotions(root)` は退役していないものだけを返し（これが「観測の候補」の入口）、`all_promotions(root)` は退役の行つきで全部返す。`active_promotions` / `all_promotions` は、登録の無い store_id を空の列にせず `UnknownStore` を投げる（「候補が 0 件」と「そんなソブリンは無い」は別の答え）。store_id なしで構造の側の台帳が無い root は空の列を返すが、「昇格 0 件」か「台帳が無い」かを型で知るには `promotions_answer(root, store_id=None, include_retired=False)` の `structure`（`PRESENT` / `ABSENT`）を見る（CLI の `promotions` はこちら）。退役件数は `release` の出力の `retired`（このソブリン由来の退役の総数）と `retired_this_run`（今回の実行で足した数）。

`retire_log.registry_seq` は、退役を書くときに計算した `RELEASE` 行の seq（次の seq）。退役を先に、`RELEASE` を後に書くので（失敗しても再実行で揃う順番）、その間に同じ root へ別の registry 行が入ると食い違いうる。実際の `RELEASE` 行は `registry_log` から引ける。

## 私的データの線引き
- **手放しは利用者の操作で、Vera は自分からは消さない**。`release` の確認は `--confirm <store_id>` の完全一致。Vera は参照を切り、ハッシュを残し、退役を追記するだけ。
- Vera が書く場所は `--root` の中だけ。`export` は利用者が指示した 1 か所だけ。`attach --file` は複製しない。
- release 後もファイルは残る。消すのは持ち主（`rm` などの利用者の操作）。持ち主が消した後も、状態は `RELEASED` のままで `UnknownStore` や `FileMissing` に化けない。
- テストはすべて `tmp_path` の中だけに書く。`~/.vera` や作業ツリー直下には書かない。

## 限界（隠さない）
- トリガはファイルの持ち主を止めない（`DROP TRIGGER` すれば書き換えられる）。検出は形の検査（ファイルを開く前）で、改竄の防止ではない。行の中身（payload）を書き換えられた場合の検出はしない。
- 公開版 `vera_session.py` の `id TEXT PRIMARY KEY` の表は `INSERT OR REPLACE` でトリガを通らずに行を置換できる穴を持つ（中間職が `plan.md` §1.4 で測定）。公開版はこのチケットでは直していない（報告済み）。
- 読み取り専用で開く検査でも、ホットジャーナルが残っているファイルを開くと SQLite が巻き戻す・失敗することがある。`export` だけは開く前にサイドカーを確かめる。他の操作はそこまで確かめていない。
- `structure_ref` は構造の側の台帳の最初の行（root の絶対パスを含む）から決まる。値が重なるのは次の 2 つ: (1) `structure.sqlite` のファイルそのものを別の root へ複製して使う（最初の行ごと複製される）、(2) root のディレクトリを別の場所へ移した後、元のパスに新しい root を作り、同じ秒に同じ最初の行を書いた（root の絶対パスも、ts・store_id・path・ハッシュも同じになる）。どちらの場合も back-link の区別はしない。root に symlink 経由の別名があるときは、最初の行を書いたときに渡された絶対パス（`os.path.abspath`、symlink は解決しない）が入る。ソブリンのファイルを動かすのは `export` / `attach --file` で、台帳の複製は想定していない。
- 同時に複数の Vera が同じ root に書く場合の排他は、SQLite の `BEGIN IMMEDIATE` に任せている。複数ファイルにまたがる原子性は無い（構造の側→ソブリンの側の順で書き、落ちたら次回に修復する）。
- `create` はソブリンのファイルを作った後に registry へ書く。その間に落ちるとファイルだけ残り、再度の `create` は `REFUSED_FILE_EXISTS` になる（消さない。`attach --file` で登録できる）。
- W3-c の入口での S5・S6 は未測定（`NOT_MEASURED_W3C_NOT_INTEGRATED`）。Protocol 越しには確かめた。

## 判断記録
チケットの前提と実物の食い違いを実測した上で、中間職が決めたもの（`plan.md` §2）。

- **D1（置き場所）**: チケットの `verantyx/sovereign.py`（新規）は既に別機能で存在する（2026-10-01 の基底から）。許可パスはこのファイルだけなので、既存の行を 1 行も変えず末尾へ節を追記した（`main()` と `if __name__` の間）。新しいモジュールは許可パスの外なので作らない。
- **D2（CLI）**: 既存の `sovereign --domain ...` を保ち、同じ `sovereign` の下に入れ子の操作を足した。`--domain` の `required=True` を外した（`cli.py` で消えた行はこの 1 行だけ）代わりに、操作も `--domain` も無いときは従来と同じ最終行・終了コード 2 を出す。操作と `--domain` の併用は終了コード 2。**usage 行の文面は変わる**（`[--domain NAME=PATH]` が任意になり `OP ...` が足される）ことは受け入れた。入れ子の引数の dest はすべて `sov_` で始める（親の既定値を壊さない）。
- **D3（再利用）**: 公開版の `vera_session.py` は dev に無い。import も複製もしない。写したのは、表ごとの BEFORE UPDATE／BEFORE DELETE トリガで ABORT する形と、名前の規則 `[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}` だけ。理由: `author` と `type` の CHECK が `utterance` を入れられない、`record_turn` が重複を黙って落とす（昇格は繰り返しが信号）、引用番号が暗黙の rowid、名前つきの貯蔵が `~/.vera` に書く、`INSERT OR REPLACE` の穴。
- **D4（seq と id）**: seq は 1 から 1 ずつ増える整数で、DB のトリガが強制する。event id は `"<store_id>:<seq>"`（列に持たない）。export・attach しても変わらない。
- **D5（`events(since)`）**: since は「その事件より後」。この台帳の id でない文字列は `UnknownSince`。
- **D6（時刻と日）**: UTC の aware のみ。「別の日」は `ts[:10]`。
- **D7（訂正）**: `payload["corrects"]` の前進の追記。存在しない id は拒否。Protocol の数は生、昇格の数え上げでは訂正された側を数えない。
- **D8（同意）**: 既定は同意なし。窓は最新の同意（真）の `since_seq` より後。撤回は以後の昇格を止めるだけ。
- **D9（しきい値）**: n = 3、d = 2。方針値で実測ではない。
- **D10（候補の形）**: 上の「昇格のしきい値」の節。
- **D11（detach と昇格分）**: detach は退役させない（戻せるから）。退役は `release` だけ。
- **D12（S5・S6 の入口）**: W3-c は未統合なので Protocol の 4 関数だけを使う参照の読み手で確かめる。
- **D13（release の確認）**: `--confirm` が store_id と完全に一致すること。
- **D14（release 後の再 attach）**: 同じ root では拒否（`REFUSED_RELEASED`）。退役は取り消さない。

### 実装役が自分で決めたこと
- **E1（`retire_log.registry_seq`）**: 指示書は「退役を先、`RELEASE` を後」の順を求める。`RELEASE` 行の seq は退役を書く時点で未確定なので、退役の transaction の中で `MAX(registry seq)+1` を計算して入れた。その間に別の registry 行が入らない限り実際の seq と一致する（テストは一致を確かめる）。
- **E2（`consent` の snapshot）**: `describe` が DETACHED / RELEASED のソブリンについて、ファイルを開かずに同意の状態を答えるため、registry の `detail` に操作時点の同意を写した（読めないときは `promote: null`）。
- **E3（`attach --file` の `same_as_detached`）**: 切り離しの履歴が無いので `null`（真偽ではない）。
- **E4（`export` が DETACHED を拒否）**: 切り離したものは構造から読めないので持ち出せない（`DETACHED` を返す）。先に `attach` する。
- **E5（`export` のハッシュ不一致）**: 複製が壊れたときは `EXPORT_HASH_MISMATCH` を返し、registry には書かない。壊れた複製は **消さずに残し**、消すのは利用者（`note` に書く）。
- **E6（CLI の終了コード）**: `DETACHED` や `RELEASED` のような同じ文字列が、ある操作では成功（`detach` `release`）、別の操作では読めない理由（`events` `export`）になるので、成功か否かは操作ごとに判断する。`APPENDED` を成功に足した。
- **E7（`promote` の `counts`）**: 事前登録 §6 の等式のために、事件単位の数（`events_total` と各分類）と、鍵単位の数（`candidates` `promoted`）と、件数（`repaired_backlink`）を同じ辞書に置いた。事件単位かどうかは各キーの意味が文書に書いてある。
- **E8（`conflicting_occupancy` の事件）**: 割れた cell では、`UNOCCUPIED`・他の値・`UNKNOWN_*`・欠けの事件をすべて `conflicting_occupancy` に入れる。`UNOCCUPIED` が無い cell は、`UNKNOWN_*`・欠けを `unknown_occupancy`、それ以外の値だけのものを `not_a_candidate` に入れる。

### レビュー第 1 ラウンドを受けて決めたこと
- **E9（`structure_ref`）**: ソブリン側 `promotion_log` に `structure_ref TEXT NOT NULL` を列の最後に足した（形の検査の期待値が変わる。新しい表なので互換の問題は無い）。値は `registry_log` の最初の行の正準 json の sha256（`_sov_struct_ref`）。registry の最初の行は追記専用で動かず、root の絶対パスを `detail.root` に含むので root ごとに違う（第 2 ラウンドで、path だけに頼ると `attach --file` で始まった root が重なることが分かり、`root` を足した。全行に入れるか最初の行だけにするかは全行を選んだ）。別の候補（台帳を作るときに別の行を書く）は構造の側の表を増やすので採らなかった。
- **E10（`promotions` の型）**: 未登録の store_id は `UnknownStore`（API）/ `UNKNOWN_STORE` rc=1（CLI）。台帳の無い root の `--store-id なし` は `structure: ABSENT` で何も作らない。`tests/test_sovereign_units.py::test_structure_absent_is_not_the_same_as_store_unknown` の期待は、前の `all_promotions(root) == []` だけだったものに、未登録 store_id の拒否と `promotions_answer` の `ABSENT` を **足して強めた**（弱めていない）。`active_promotions(root)`（store_id なし・台帳なし）が空の列を返すことは W3-c の読み手が落ちないように残した（監査役への問い）。
- **E11（`RELEASE_IN_PROGRESS`）**: レビューの任意の改善 1 を採った。ソブリンが ACTIVE のまま `retire_log` にそのソブリンの行がある間は `promote` が何も書かない。
- **E12（同意の再記録）**: 任意の改善 2 は「真→真でも窓が動く」と文書に書く方を選んだ（D8 の文字どおり。実装は変えない）。

## 測定物
`artifacts/w4-m/` に、事前登録（`PREREG_W4m_promotion.md`、`prereg.txt`）、受入基準ごとの pytest 出力（`s1_pytest.txt` `s23_pytest.txt` `s456_pytest.txt`）、CLI の実演（`cli_demo.txt`）、変更前後の既存 `sovereign` の経路の比較（`legacy_before/` `legacy_after/` `legacy_cmp.txt`）、全体テストの失敗集合の比較（`pytest_full.txt` `pytest_failures.txt` `pytest_new_failures.txt`）、決め打ち検査（`check_hardcode.txt`）。数値はこれらのファイルにだけ出典を持つ。
