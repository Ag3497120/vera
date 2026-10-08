**表 15-1 規則層で上がる問の数**（`--vocab-llm fake` ＋ 空の対応づけの台本 = 作り物の対応づけ。`mapping.outcome` が `NOT_ASKED` で始まる問を、`mapping.rule.detail` 別に数えた。前 = 基点 `5cae978` のコード、後 = 変更後のコード）

| detail | 凍結データ 期待 answer 前 | 後 | 凍結データ 期待 escalate 前 | 後 | 新データ 期待 answer 前 | 後 | 新データ 期待 escalate 前 | 後 |
|---|---|---|---|---|---|---|---|---|
| `TERM_IN_WIDER_PHRASE` | 8 | 0 | 4 | 1 | 15 | 0 | 21 | 15 |
| `NEGATED_QUESTION` | 5 | 0 | 2 | 1 | 16 | 0 | 20 | 14 |
| `INVERTED_QUESTION` | 0 | 0 | 1 | 1 | 10 | 0 | 19 | 13 |
| `BUILTIN_PROTECTED` | 2 | 2 | 1 | 1 | 11 | 0 | 19 | 13 |
| `NO_ALLOWLIST` | 0 | 0 | 0 | 0 | 10 | 0 | 18 | 16 |
| 5 つの罠の計 | 15 | 2 | 8 | 4 | 62 | 0 | 97 | 71 |
| 罠以外の規則の計 | 3 | 3 | 36 | 36 | 0 | 9 | 0 | 1 |
| 問の総数 | 249 | 249 | 100 | 100 | 62 | 62 | 97 | 97 |

**表 15-2 規則だけ（`off`）で罠の detail を返した問の数**（reason は問わない。上げ続けた問も、別の reason で上げ直した問も数える）

| detail | 凍結データ 期待 answer 前 | 後 | 凍結データ 期待 escalate 前 | 後 | 新データ 期待 answer 前 | 後 | 新データ 期待 escalate 前 | 後 |
|---|---|---|---|---|---|---|---|---|
| `TERM_IN_WIDER_PHRASE` | 8 | 5 | 4 | 2 | 15 | 11 | 21 | 20 |
| `NEGATED_QUESTION` | 5 | 0 | 2 | 1 | 16 | 0 | 20 | 14 |
| `INVERTED_QUESTION` | 0 | 0 | 1 | 1 | 10 | 0 | 19 | 13 |
| `BUILTIN_PROTECTED` | 2 | 2 | 1 | 1 | 11 | 0 | 19 | 13 |
| `NO_ALLOWLIST` | 0 | 0 | 0 | 0 | 10 | 0 | 18 | 16 |

**表 15-3 凍結データ（349 問 × 2 モード）で前後に変わった行（C1）と安全の線**

| 項目 | 値 |
|---|---|
| 比べた凍結データの問 | 349 |
| どれかの欄が変わった行（問 × モード） | 34 |
| どれかの欄が変わった問 | 17 |
| 　うち `off` で変わった問 | 17 |
| 　うち `fakemap` で変わった問 | 17 |
| 　変化の種類 `fakemap/NOT_ASKED->mapping` | 17 |
| 　変化の種類 `off/FRAME_SILENT->VOCAB_UNMAPPED` | 5 |
| 　変化の種類 `off/TERM_IN_WIDER_PHRASE->NO_RECORD_DECIDES(narrow reading also silent)` | 6 |
| 　変化の種類 `off/other` | 6 |
| S1: 期待 escalate で、前は答えず後は答えた問 | 0 |
| S2: 期待 answer で、前は答え合っていた（または答えなかった）のに後に別の答えになった行 | 0 |
| S3: `off` で escalate から answer に変わった行 | 0（全部が期待と一致: True） |

**表 15-4 新データ（`tests/conduct_ask/w2c2/`）の C2 の判定（変更後のコード）**

| 罠 | `raise` 合格/件数 | `route` 合格/件数 | `transfer` 合格/件数 |
|---|---|---|---|
| `WIDER` | 15/15 | 15/15 | 6/6 |
| `NEGATED` | 14/14 | 15/16 | 6/6 |
| `INVERTED` | 13/13 | 10/10 | 5/6 |
| `BUILTIN` | 13/13 | 11/11 | 6/6 |
| `NO_ALLOWLIST` | 12/12 | 2/10 | 2/6 |

**表 15-5 新データの同じ判定を基点のコードで取ったもの**（`raise` は基点でも上がるので合格、`route` は基点では誤って上げるので不合格になる）

| 罠 | `raise` 合格/件数 | `route` 合格/件数 | `transfer` 合格/件数 |
|---|---|---|---|
| `WIDER` | 15/15 | 0/15 | 0/6 |
| `NEGATED` | 14/14 | 0/16 | 0/6 |
| `INVERTED` | 13/13 | 0/10 | 0/6 |
| `BUILTIN` | 13/13 | 0/11 | 0/6 |
| `NO_ALLOWLIST` | 12/12 | 0/10 | 0/6 |

**表 15-6 補いのデータ（`tests/conduct_ask/w2c2/supp/`、第 2 ラウンドの凍結）の C2 の判定（変更後のコード）**

| 罠 | `raise` 合格/件数 | `route` 合格/件数 |
|---|---|---|
| `NEGATED` | 11/11 | 10/10 |
| `NO_ALLOWLIST` | 10/10 | 15/15 |

**表 15-7 補いのデータの同じ判定を基点のコードで取ったもの**

| 罠 | `raise` 合格/件数 | `route` 合格/件数 |
|---|---|---|
| `NEGATED` | 11/11 | 0/10 |
| `NO_ALLOWLIST` | 10/10 | 0/15 |
