**表 15-1 規則層で上がる問の数**（`--vocab-llm fake` ＋ 空の対応づけの台本 = 作り物の対応づけ。`mapping.outcome` が `NOT_ASKED` で始まる問を、`mapping.rule.detail` 別に数えた。前 = 基点 `5cae978` のコード、後 = 第 3 ラウンドのコード）

凍結データ（349 問）

| detail | 期待 answer 前 | 後 | 期待 escalate 前 | 後 |
|---|---|---|---|---|
| `TERM_IN_WIDER_PHRASE` | 8 | 0 | 4 | 1 |
| `NEGATED_QUESTION` | 5 | 5 | 2 | 2 |
| `INVERTED_QUESTION` | 0 | 0 | 1 | 1 |
| `BUILTIN_PROTECTED` | 2 | 2 | 1 | 1 |
| `NO_ALLOWLIST` | 0 | 0 | 0 | 0 |
| 5 つの罠の計 | 15 | 7 | 8 | 5 |
| 罠以外の規則の計 | 3 | 3 | 36 | 36 |
| 問の総数 | 249 | 249 | 100 | 100 |

新データ（`w2c2`、159 問）

| detail | 期待 answer 前 | 後 | 期待 escalate 前 | 後 |
|---|---|---|---|---|
| `TERM_IN_WIDER_PHRASE` | 15 | 0 | 21 | 18 |
| `NEGATED_QUESTION` | 16 | 16 | 20 | 20 |
| `INVERTED_QUESTION` | 10 | 10 | 19 | 19 |
| `BUILTIN_PROTECTED` | 11 | 0 | 19 | 13 |
| `NO_ALLOWLIST` | 10 | 11 | 18 | 18 |
| 5 つの罠の計 | 62 | 37 | 97 | 88 |
| 罠以外の規則の計 | 0 | 0 | 0 | 0 |
| 問の総数 | 62 | 62 | 97 | 97 |

補いのデータ（`w2c2/supp`、46 問）

| detail | 期待 answer 前 | 後 | 期待 escalate 前 | 後 |
|---|---|---|---|---|
| `TERM_IN_WIDER_PHRASE` | 0 | 0 | 0 | 0 |
| `NEGATED_QUESTION` | 10 | 10 | 11 | 11 |
| `INVERTED_QUESTION` | 0 | 0 | 0 | 0 |
| `BUILTIN_PROTECTED` | 0 | 0 | 0 | 0 |
| `NO_ALLOWLIST` | 15 | 15 | 10 | 10 |
| 5 つの罠の計 | 25 | 25 | 21 | 21 |
| 罠以外の規則の計 | 0 | 0 | 0 | 0 |
| 問の総数 | 25 | 25 | 21 | 21 |

**表 15-2 凍結データ（349 問 × 2 モード）で前後に変わった行（C1）と安全の線**

| 項目 | 値 |
|---|---|
| 比べた凍結データの問 | 349 |
| どれかの欄が変わった行（問 × モード） | 11 |
| どれかの欄が変わった問 | 11 |
| 　うち `off` で変わった問 | 0 |
| 　うち `fakemap` で変わった問 | 11 |
| 　変化の種類 `fakemap/NOT_ASKED->mapping` | 11 |
| S1: 期待 escalate で、前は答えず後は答えた問 | 0 |
| S2: 期待 answer で、前は答え合っていた（または答えなかった）のに後に別の答えになった行 | 0 |
| S3: `off` で escalate から answer に変わった行 | 0（全部が期待と一致: True） |

**表 15-3 C2 の第 3 ラウンドの読み（D12）の判定**（`c2r3`。後 = 第 3 ラウンドのコードの結果、基点 = 基点の結果自身を入れたもの）

| 項目 | 後 | 基点 |
|---|---|---|
| C2-K raise（残した罠 `WIDER`・`BUILTIN`、新データ）合格/件数 | 28/28 | 28/28 |
| C2-K route（同上）合格/件数 | 26/26 | 0/26 |
| 　うち `ROUTE_STOPPED_BY_REVERTED_TRAP` | `w2c2-builtin-route-11` | なし |
| C2-R（戻した罠 3 つ、新データと補い、両モード）基点と 6 欄が一致した行/行数 | 278/278 | 278/278 |
| transfer（新データ、判定に入れない）対応づけに回った問/件数 | 9/30 | 0/30 |
| 　`WIDER` の transfer | 3/6 | 0/6 |
| 　`NEGATED` の transfer | 0/6 | 0/6 |
| 　`INVERTED` の transfer | 0/6 | 0/6 |
| 　`BUILTIN` の transfer | 6/6 | 0/6 |
| 　`NO_ALLOWLIST` の transfer | 0/6 | 0/6 |
| 判定に入れない元の新データの route 9 問（B2） | 9 問、全部が戻した罠の側: True | |
| C2R3 | PASS | FAIL |

**表 15-4 D10: 広い語句の段（`trace.resolver_outcomes.wider_phrase`）の値別の件数**（凍結 349 ＋ 新 159 ＋ 補い 46 = 554 問。`off` は規則だけ、`fakemap` は作り物の対応づけ）

| 値 | `off` | `fakemap` |
|---|---|---|
| `(no wider-phrase step)` | 499 | 499 |
| `ESCALATE:EVIDENCE:E0` | 6 | 6 |
| `ESCALATE:EVIDENCE:OTHER_RECORD` | 11 | 11 |
| `ESCALATE:UNDECIDED` | 6 | 6 |
| `ESCALATE:UNDECIDED:MAPPING_DID_NOT_DECIDE:FRAME_SILENT/MAP_NONE` | 0 | 29 |
| `ESCALATE:UNDECIDED:MAPPING_OFF` | 29 | 0 |
| `ESCALATE:UNDECIDED:NARROW_READING_HANDS_UP` | 3 | 3 |

**表 15-5 最終の出力の `FRAME_SILENT/TERM_IN_WIDER_PHRASE` と `VOCAB_UNMAPPED/TERM_IN_WIDER_PHRASE` の件数**

| 最終の (reason, detail) | `off` 前 | 後 | `fakemap` 前 | 後 |
|---|---|---|---|---|
| `FRAME_SILENT/TERM_IN_WIDER_PHRASE` | 48 | 48 | 48 | 48 |
| `VOCAB_UNMAPPED/TERM_IN_WIDER_PHRASE` | 0 | 0 | 0 | 0 |
