# W1-a3 攻撃報告

## 1. 対象

- `docs/READING_SOUNDNESS.md`: §4.6、K40〜K41、§9.2 の条件 1・5・6・8。見出しの K1〜K41 も確認。
- `docs/READING_CONVENTIONS.md`: §2（役割）、§3（述語の辞書形）、§4.6（態）、§5（極性・時制）。
- 入口: `verantyx/semantic_read.py`。英語フレームの語形処理: `verantyx/en_frames.py`。

## 2. 命中した攻撃

### H1 — 自発の思い起こしを passive と断定（観点 a、2 文）

「海岸が思い返された」「庭が思い起こされた」は、文脈なしでは「誰かが思い起こした」という受身と「ふと思い出された」という自発の両方に取れる。§4.6 は態が決まらないとき棄権するとし、K41 も自発動詞リストに無い語を passive と誤る穴を記録している。両方とも `readable: true`、`voice: passive`、主語を `patient` として返した。

再現コマンド（各文を個別に実行）:

```sh
PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3 PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.semantic_read '--text=昔の海岸が思い返された。'
```

実際の出力:

```json
{"schema":"verantyx.semantic_read/1","lang":"ja","readable":true,"clauses":[{"predicate":"思い返す","roles":{"patient":"昔の海岸"},"polarity":"+","tense":"past","modality":null,"voice":"passive"}],"relations":[],"abstain":null,"unsupported":[],"clause_meta":[{"rule":"frame","span":[5,9]}]}
```

```sh
PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3 PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.semantic_read '--text=昔の庭が思い起こされた。'
```

実際の出力:

```json
{"schema":"verantyx.semantic_read/1","lang":"ja","readable":true,"clauses":[{"predicate":"思い起こす","roles":{"patient":"昔の庭"},"polarity":"+","tense":"past","modality":null,"voice":"passive"}],"relations":[],"abstain":null,"unsupported":[],"clause_meta":[{"rule":"frame","span":[4,9]}]}
```

期待との差: 自発の可能性を排除する正の証拠が無く、passive だけを返す根拠がない。`_SPONTANEOUS_PREDICATES` の一覧から漏れた語が `_not_person_evidence` の主語だけで passive に進む。該当箇所: [semantic_read.py:499](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3/verantyx/semantic_read.py:499)、[semantic_read.py:562](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3/verantyx/semantic_read.py:562)。K41 の記録箇所: [READING_SOUNDNESS.md:635](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3/docs/READING_SOUNDNESS.md:635)。

### H2 — `unsupported` がある入力を `readable: true` にする（観点 a）

再現コマンド:

```sh
PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3 PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.semantic_read '--text=ふと昔の海岸が思い返された。'
```

実際の出力:

```json
{"schema":"verantyx.semantic_read/1","lang":"ja","readable":true,"clauses":[{"predicate":"思い返す","roles":{"patient":"昔の海岸"},"polarity":"+","tense":"past","modality":null,"voice":"passive"}],"relations":[],"abstain":null,"unsupported":[{"predicate":"思い返す","span":[7,11],"reasons":["unrepresented source content","unrepresented source content"]}],"clause_meta":[{"rule":"diathesis","span":[7,13]}]}
```

期待との差: `unsupported` に「unrepresented source content」があるのに `readable: true` と節を返した。§9.2 条件 1 は unsupported の節があれば棄権すると定める。`_map_ja` が述語範囲に含まれた unsupported を、比較と copula の別読み以外でも除外扱いする。該当箇所: [semantic_read.py:265](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3/verantyx/semantic_read.py:265)、[READING_SOUNDNESS.md:646](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3/docs/READING_SOUNDNESS.md:646)。

### H3 — 経路を patient にし、無生物主語を agent にする（観点 a）

再現コマンド:

```sh
PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3 PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.semantic_read '--text=自転車が細道を駆け抜けた。'
```

実際の出力:

```json
{"schema":"verantyx.semantic_read/1","lang":"ja","readable":true,"clauses":[{"predicate":"駆け抜ける","roles":{"agent":"自転車","patient":"細道"},"polarity":"+","tense":"past","modality":null,"voice":"active"}],"relations":[],"abstain":null,"unsupported":[],"clause_meta":[{"rule":"frame","span":[7,11]}]}
```

期待との差: 「細道」は移動の経路であり patient ではない。自動詞の無生物主語「自転車」は規約 §2 の `entity` で、`agent` ではない。経路の役割を表せないので入口は棄権すべきだが、`駆け抜ける` が `_PATH_VERBS` に無いため通過した。K40 が同型の既知誤読を明記している。該当箇所: [semantic_read.py:352](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3/verantyx/semantic_read.py:352)、[semantic_read.py:391](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3/verantyx/semantic_read.py:391)、[semantic_read.py:403](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3/verantyx/semantic_read.py:403)、[READING_SOUNDNESS.md:634](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3/docs/READING_SOUNDNESS.md:634)。

### H4 — 英語の過去分詞から誤った辞書形を作る（観点 a）

再現コマンド:

```sh
PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3 PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python -m verantyx.semantic_read '--text=The chair was repaired by them.'
```

実際の出力:

```json
{"schema":"verantyx.semantic_read/1","lang":"en","readable":true,"clauses":[{"predicate":"repaire","roles":{"agent":"them","patient":"chair"},"polarity":"+","tense":"past","modality":null,"voice":"passive"}],"relations":[],"abstain":null,"unsupported":[],"clause_meta":[{"rule":"en_frames","span":[0,31]}]}
```

期待との差: 書かれた動詞の原形は `repair`。§3 が要求する原形でなく、存在しない形 `repaire` を返した。`en_frames.lemma` の `-ed` 処理が `repair` の末尾 `-ir` に `e` を追加し、入口は frame の述語をそのまま採用する。該当箇所: [en_frames.py:71](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3/verantyx/en_frames.py:71)、[semantic_read.py:744](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3/verantyx/semantic_read.py:744)、[READING_CONVENTIONS.md:101](/Users/motonisihikoudai/Projects/vera-impl/wt/atk-W1-a3/docs/READING_CONVENTIONS.md:101)。

## 3. 外れた攻撃

135 文は追加の約束違反を示さなかった。日本語 80 文では単純肯定・否定の極性と past/nonpast、明示的な受身、recipient、可能・尊敬の曖昧さ、恩恵表現を試した。英語 60 文では能動・受身・否定・二重目的語・助動詞・量化・時間句・従属節を試した。残りは読みが合う構造を返すか、曖昧・未対応の型を理由付きで棄権した。

各入力を別々の CLI プロセスに通した全コマンドと出力は `probe_outputs.jsonl` に保存した。試験入力は `run_probes.py` にあり、命中例を失敗させる `test_attack_reading_entry.py` は 5 ケースすべて実行して失敗を確認した。

## 4. 数

- 命中: **5 文**（4 種の破れ。H1 は 2 文、H2 は H1 と異なる 1 文、H3・H4 は各 1 文）
- 外れ: **135 文**
- 合計: **日本語 80 文、英語 60 文、140 回の個別 CLI 実行**
