# W3-a3 attack report

## 1. 対象

- `docs/COARSE_PLACEMENT.md` §12.4、§12.6、§12.10、受入基準 Q3/Q5。特に、分布と生成の一致で述語を direct にする条件と、`frame_status` / `frame` の契約。
- 対象配置: `/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r6/run1`（読み取りのみ）。
- `PREREG.md` は検査前に記録済み（SHA-256 `f32af92de4072a248432e4d204bb6525869079de564fcd20ac9cf3d2ce13ec16`）。検査対象48語は配置の `headwords` から条件で導出した。

## 2. 命中

### A1 — (b) 同じ助詞の分布型と確認済み frame 型が矛盾

再現コマンド:

```sh
PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-a3 PYTHONDONTWRITEBYTECODE=1 \
  /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -s attacks/W3-a3/test_attack_w3a3.py
```

実出力（抜粋）:

```text
derived_words: 48
queried: 48
byte_differences: []
invariant_errors: []
disjoint_slot_conflicts: 21
conflict_words: 13
FAILED: confirmed frame slot types contradict significant distribution types
1 failed, 1 passed in 0.35s
```

代表例 `命じる`: query は `state=DECIDED`, `origin=direct`, `top=[P_COMMUNICATE]`, `generated_frame=true`, `frame_status=CONFIRMED`, `frame={"を":["GROUP_ORG","PERSON"]}` を返した。一方、同じ語の threshold-met `role_distribution@jawiki` は `を|EVENT_ACT=14`, `を|ABSTRACT=3`、有意な型を `EVENT_ACT` と判定する。したがって `を` の返却型と分布の有意型に共通部分がない。

同じ動詞の表記形 `命ずる` は `を=[ABSTRACT, EVENT_ACT]` を返す。48語全件と21件の助詞・出所別不一致は [`r6_48_queries.jsonl`](r6_48_queries.jsonl) と [`r6_audit_summary.json`](r6_audit_summary.json) に保存した。13語は うたう、たたえる、みせる、交わす、命じる、問い合わせる、潜める、示せる、薦める、見せ合う、言い換える、訴える、謳う。

測定出力の SHA-256: `r6_48_queries.jsonl` = `84c2bfa0b1fe676f201a4fcf79ed4ea381a22f54733f6099b54db7fdff53128c`; `r6_audit_summary.json` = `afd0a415f552d6c983ddfa0a6f9dd10ebc56a5fd3ef2d26e748f8e8bf822beba`; `state_probes.json` = `c27484e44b6e54d7dba1e28d3dc7ff5809bb5a07ea2b23dae8c8488380185ee0`。

差分と場所: §12.6 の direct 条件は助詞の包含だけを見る。実装も [`coarse_types.py:686`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-a3/verantyx/coarse_types.py:686) で有意助詞だけを比較し、[`coarse_place.py:342`](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-a3/verantyx/coarse_place.py:342) 以降でその助詞に対する生成側の型を `frame` にそのまま出している。`CONFIRMED` の枠型が、同じ助詞について得た分布型と食い違う。これは direct 格上げの狭い助詞包含式そのものには反しないが、攻撃対象として指定された frame の意味的矛盾を実出力で確認した。

## 3. 外れた攻撃

- (a) direct 48語の述語型: 全件の出力を読み、`P_COMMUNICATE` / `P_MOVE` に明白な誤りは特定できなかった。1出所だけの格上げは設定 `rd_min_sources=1`（§12.15.3）どおりなので、それだけでは命中にしない。
- (b) 同一助詞に複数型が並ぶこと自体、および他動詞の `を` 欠落: 型リストは許容され、確認した48語で明白な他動詞の `を` 欠落は見つからなかった。上記 A1 は複数型リスト一般ではなく、分布型との不一致を数えた。
- (c)(d) 状態と由来: [`state_probes.json`](state_probes.json) に記録した。`昨日`・`来週` は `estimated/generated`、`毎朝` は `UNPLACED`、`読み上げた`・`歌わない`・`連絡する` は `UNKNOWN`。値の違いは出たが、不明と推定を同じ型にしてはいない。`歌う` は `alias` 由来の direct `WORK`、`歌った` は proximity estimate `WORK` だったが、`歌う` が作品名の別義でもあり、文脈無しでは誤りと確定できないため命中に数えない。`連絡` は `MULTIPLE` のまま棄権。
- (e) 反復問い合わせのJSONバイト一致: 48/48語で差分なし。

## 4. 数

命中 **1**、外れ **4**（攻撃単位: a / b の残り2観点をまとめた1件 / cとd / e）。検査ファイルは [`test_attack_w3a3.py`](test_attack_w3a3.py)。配置の再作成、製品コード変更、ネットワーク、全体テスト、隠しバンクの閲覧は行っていない。Q6/隠し評価はこの攻撃環境では未検証。
