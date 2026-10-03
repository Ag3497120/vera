# PREREG W4-m: 記憶のソブリンの昇格 — しきい値・候補の形・数え方・確かめ方（事前登録）

この文書は `tests/test_sovereign_promote.py` を書く前に固定する。値を変えるときは末尾の「変更記録」に日時と理由を追記する（消さない）。

## 1. しきい値（方針値。実測にもとづく値ではない）
- n（回数） = 3、d（別の日） = 2。
- 根拠は方針だけ: d = 2 は「別の日」の文字どおりの最小。n と d は独立の条件なので、d = 2 から自動では満たされない最小の n = d + 1 = 3。
- これは測定で選んだ値ではない。どこかの標本に当てて調整した値でもない。
- CLI の `--min-count`・`--min-days`（API では `min_count`・`min_days`）で上書きできる。上書きしたときは出力と記録（構造の側 `promotion_log.thresholds`）に `source: "override"` を残す。既定は `source: "prereg"`。

## 2. 「別の日」の定義
- `ts` は UTC の ISO 8601 秒精度（`datetime.now(timezone.utc).isoformat(timespec="seconds")`）。
- 「別の日」は `ts[:10]`（UTC の日付）の異なり数。端末の地域の時刻は使わない。
- 試験のために `now`（tz つき datetime を返す関数）を差し込める。tz の無い datetime は拒否する。CLI からは差し込めない。

## 3. 昇格の候補の形（D10）
- placement_evidence: `kind == "observation"` かつ `payload["cell"]` があり `payload["occupied"] == "UNOCCUPIED"` の事件。鍵は `cell` の正準化した文字列 `json.dumps(cell, sort_keys=True, ensure_ascii=False, separators=(",",":"))`（`cell` が文字列ならそのまま）。
- construction_evidence: `kind == "utterance"` かつ `payload["phrase"]` が空でない文字列の事件。鍵は phrase そのもの（正規化しない）。
- 同じ cell 鍵に `occupied` が `UNOCCUPIED` 以外（`ATTESTED`・`UNKNOWN_NO_INDEX` など）の事件が窓の中に 1 件でもあれば昇格しない（`conflicting_occupancy`）。
- `occupied` が無い、または `UNKNOWN_*` だけの cell は `unknown_occupancy`。
- `cell`・`occupied`・`phrase` の鍵名は W3-c の `Observation.cell`/`occupied` に合わせた仮の名前で、統合時に寄せる。

## 4. 訂正（D7）
- 訂正は `payload["corrects"] = <この台帳の既存の event id>` を持つ前進の追記。元の行は残る。存在しない id を指す訂正は拒否（`UNKNOWN_CORRECTS_TARGET`）。
- `count`/`last_seq`（Protocol）は生の数（訂正された事件も数える）。昇格の数え上げでは、訂正された側の事件を数えず `superseded_by_correction` に入れる。

## 5. 同意の窓（D8）
- 既定は同意なし。同意は `consent_log` への追記で変わり、最新の行が効く。
- 昇格で数えるのは、最新の同意（真）の `since_seq` より後の事件だけ。同意の前の事件は `outside_consent_window`。
- 同意の撤回は以後の昇格を止めるだけ。既に昇格した分は `release` まで退役させない（撤回で退役させるべきかは監査役への問い）。

## 6. 数え上げの分類と等式（読み飛ばしを残さない）
ソブリン全体の事件を、次のどれか 1 つに入れる（事件単位。判定はこの順）。
1. `outside_consent_window`: `seq <= 最新の同意の since_seq`。
2. `superseded_by_correction`: 窓の中で、後の事件の `payload["corrects"]` に指された事件。
3. 残りの窓の中の事件を (kind, 鍵) で集める。placement 形は cell 鍵ごとに、その cell の窓の中の観測を U（occupied == "UNOCCUPIED"）・X（occupied が UNOCCUPIED でも UNKNOWN_* でもない値）・K（occupied が無い、または文字列で UNKNOWN_ で始まる）に分ける。
   - U と (X または K) が両方ある cell: U・X・K のすべての事件が `conflicting_occupancy`。
   - U が無く K がある cell: K の事件が `unknown_occupancy`、X の事件は `not_a_candidate`。
   - U が無く K も無い cell（X だけ）: `not_a_candidate`。
   - U だけの cell と、construction 形の phrase 鍵: 件数 c、別の日 dd を求め、退役していない昇格が (store_id, kind, 鍵) に既にあれば `already_promoted`、なければ c < n なら `below_count`、dd < d なら `below_days`、満たせば昇格して `promoted_events`。
4. 上のどこにも入らない事件（候補の形でない・cell の無い観測など）は `not_a_candidate`。
等式: `events_total` = outside_consent_window + superseded_by_correction + not_a_candidate + below_count + below_days + conflicting_occupancy + unknown_occupancy + already_promoted + promoted_events（テストで確かめる）。
`candidates` は候補の形の事件を持つ (kind, 鍵) の組の数、`promoted` は今回昇格した組の数、`repaired_backlink` は修復した件数（事件ではない）。

## 7. 受入基準 S1〜S7 の確かめ方（要約）
- S1: 生の `sqlite3` 接続で全表に UPDATE・DELETE・`INSERT OR REPLACE`・UPSERT・飛んだ seq・seq 省略を打ち、拒否と行不変を確かめる。訂正は前進の追記で元の行が残る。
- S2: detach 後に `open_ledger` と開いていたハンドルが `Detached`、attach で戻り digest 一致、export → 別 root で attach して sha256 と digest 一致。
- S3: release で `Released`、registry に `RELEASE` とハッシュ、ファイルがバイト一致で残る（Vera が消さない）。
- S4: 同意なしで `NO_CONSENT` かつ両側の行数不変。同意ありでしきい値を満たす鍵だけ `conversation:<store_id>` で追記、`trace_promotion` で両側がたどれる。
- S5: release 後の昇格分が退役の追記になり `active_promotions` から外れ、構造の側の行は消えない。
- S6: 参照実装と永続の実装で digest が一致。各操作の前後で対象ソブリンの digest が不変。W3-c の入口では `NOT_MEASURED_W3C_NOT_INTEGRATED`。
- S7: 全体テストの失敗集合が基線 115 件から増えない。公開版 `vera_session.py` の sha256 が前後で同じ。

## 変更記録
（まだ無い）
