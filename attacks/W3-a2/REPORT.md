# W3-a2 coarse placement attack report

## 1. 対象

- `docs/COARSE_PLACEMENT.md` §1 の境界規則、§11.4 の生成定義の扱い、§11.6 の問い合わせ契約（特に `state`、`top`、`origin`）、§11.7 の既知の穴。
- 読み取り専用配置: `/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r5/run1`。
- 再現テスト: `attacks/W3-a2/test_attack_contract.py`。配置を作り直していない。

## 2. 命中した攻撃

### A1 — NFKC幅違いで state が変わる（観点 a）

再現コマンド:

```sh
PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1 \
  /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q attacks/W3-a2/test_attack_contract.py
```

実際の出力:

```text
ＮＰＯ=UNPLACED [], NPO=DECIDED ['GROUP_ORG']
```

期待との差: NFKCで同じ `NPO` になる幅違いで状態が変わる。`query` はまず生の表記を検索し、その行が存在するときは NFKC検索をしないため、全角表記の未配置行が正規形の決定結果を遮る。場所: [coarse_place.py:499](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-a2/verantyx/coarse_place.py:499)–[coarse_place.py:505](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-a2/verantyx/coarse_place.py:505)。§11.6 の状態・候補の読者契約に対し、要求されたNFKC表記ゆれ検査で不安定。

### A2 — ひらがな／カタカナで state が変わる（観点 a）

同じテストコマンド。実際の出力:

```text
あざみ=UNPLACED [], アザミ=DECIDED ['PLANT']
```

期待との差: 指定されたかな表記ゆれで `UNPLACED` と `DECIDED` が変わる。問い合わせはかな変換せず、各表記の別々の見出し行を返す（場所: [coarse_place.py:499](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-a2/verantyx/coarse_place.py:499)–[coarse_place.py:505](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-a2/verantyx/coarse_place.py:505)）。

### B1 — 時間表現 `3年後` が QUANTITY（観点 a）

同じテストコマンド。実際の出力:

```text
3年後 -> top=['QUANTITY']; notation.rule='number+counter'
```

期待との差: 「N years は `TIME`」という§1の境界規則に対して数量になる。学習された `年後` は固定 `TIME_UNITS` に含まれず、counter一致が `TIME` 判定より先に `QUANTITY` を返す。場所: [coarse_types.py:225](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-a2/verantyx/coarse_types.py:225)–[coarse_types.py:242](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-a2/verantyx/coarse_types.py:242)。これは§11.7に既知の穴として明記されたままの再現。

テスト実行の全出力は [repro.txt](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W3-a2/attacks/W3-a2/repro.txt) に保存。3件すべて `FAILED`（終了コード1）。

## 3. 外れた攻撃

- **context_role/context_predicate の逆転**: `ねこ` に context 無し、`を/食べる`、`に/登る` を渡したが、全て `DECIDED / ANIMAL / direct`。既決定語をcontextが反転する反例は得られず、contextは推定段だけで使われた。
- **MULTIPLE の順序依存**: `decide_word` に同じ3腕を6通りの順で渡した出力は全て `MULTIPLE`, `['ANIMAL','ARTIFACT','PERSON']`。実配置の `ネコ` も `['ANIMAL','BODY_PART']`。いずれも辞書順で安定。
- **生成定義の direct 昇格**: `ねこ` は `DECIDED / ANIMAL / direct`、`decided_by=['gen_definition','role@codex:code_qa']`。生成腕と閾値到達した別腕が一致した場合に直接へ上げる§11.4・§11.6の明示ルールに合致。生成単独の direct 昇格ではない。
- **UNKNOWN / UNPLACED の混同**: context無しで `いぬ` は `UNPLACED, seen_in_material=true`、未出語 `ホゲラ` は `UNKNOWN, seen_in_material=false`。区別は保たれていた。
- **数値境界の他の候補**: `4xx`, `2in`, `1of` は `IDENTIFIER`、`10ms` は学習済み counter による `QUANTITY`。この4例ではコード／単位の構造判定に反する期待を文書から確定できず、追加命中には数えない。`3年後` のみ§1と§11.7で判定可能。

## 4. 数

命中 **3**、外れ **5**。
