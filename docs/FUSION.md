# FUSION — Vera と開いた重みの LLM の融合（W10-f01: 層 0・層 1）

登録日時: 2026-10-04 11:37:00 +0900（`date '+%Y-%m-%d %H:%M:%S %z'` の出力。検査データ・実装・測定より前に、この §1 を書いた）

出典: 設計書 `.claude/vera-audit/tickets/W10-fusion_design.md`、チケット `W10-f01_serve_grammar.prompt.md`（オーナーの追記、2026-10-04 11:23 を含む）、中間職の指示書 `review-impl/W10-f01/plan.md`。

## 0. 3 つの事前登録（要約。本文は §1）

1. **文法に無い語は出ない**（`--strict` のとき）。縛りを信用せず、出力は必ず検証器で再確認し、文法の外は本文に出さない。
2. **読めない入力では LLM を呼ばない**（`--strict` のとき）。読めない・穴が決まらない・記録に候補が無いときは、文法を作らず型（`STRUCTURE_UNDETERMINED`／`NO_RECORD`）で返す。
3. **事実の答えが「記録の印」で出るのは、記録で埋まった腕の文だけ**。LLM の文は、どの層でも `testimony`（証言）か `constructed`（構成）か `UNREAD`（未読）の印で出す。記録の印を LLM の文に付けない。

## 1. 事前登録

### 1.1 層と既定（オーナーの方針、2026-10-04 11:23）

融合の目的は、初期の開発で足りない研究時間を縮め、価値を伝えやすくすること。何も答えられず専用ランタイムが要るモデルは注目されない。したがって:

| 層 | 起動 | 振る舞い |
|---|---|---|
| **0（既定）** | `vera serve --backend ollama --model M --document f …` | LLM が答える。Vera は入力を読み、出力の各文・各腕に 記録／証言／構成／未読 の出所の型を付けて返す。利用者の文書に関する事実の問いで記録に答えがあれば、**記録が答え**（証拠つき）。無ければ LLM の答えを **証言の印つき** で返す。 |
| **1（`--strict`）** | 同上 `--strict` | 文法で縛る。事実の問いは、記録で埋まった腕の文（有限の候補）だけ。読めない・記録に候補が無い入力では LLM を呼ばない。 |

- `--free` は層 0 を明示する別名（既定と同じ）。`--strict` と同時なら起動時に rc=2（`STRICT_AND_FREE`）。
- 標準のランタイムで動く: OpenAI 互換 `/v1/chat/completions` と Ollama 互換 `/api/chat` の両方を既定で立てる。専用のクライアントを要求しない。

### 1.2 1 ターンの流れ

1. 入力: `messages` の最後の `role == "user"` の `content`（配列形式なら `type == "text"` をつなぐ）。それ以前の会話は読解に使わない（層 0 の LLM には渡す）。依頼の種類は本文の `vera.request_kind`（`factual`（既定）／`creative`／`paraphrase`／`style`／`example`）と `vera.human_present`（既定 false）。**自然文から依頼の種類を推定しない**。不正な値は 400 `BAD_REQUEST_KIND`。
2. 読む・記録に当てる:
   - `factual`: `cli._qc_run`（質問の十字の後段）を呼ぶ。文書 0 本は `NO_RECORD`。
   - 非 factual: 質問の十字は使わない。記録 = 渡された文書の文（`cli._qc_records` と同じ切り方）。
3. 層 1 のみ: 文法を作る（§1.4）。作れなければ LLM を呼ばず型で返す。
4. LLM を呼ぶ（Ollama `/api/chat`、`think: false`、`stream: false`、`temperature: 0`。層 1 は `format` に JSON schema）。層 0 で記録が答えを持つとき（`QUESTION_CROSS`）は **呼ばない**（記録が答えなので。判断記録 D10）。
5. 検証（§1.5）: 本文を文に分け、各文を再読し、腕ごとに出所の型を付ける。
6. 根拠の方針（`basis_policy.apply_to_ask`）を掛け、本文と `vera` 欄を組む（§1.6）。

### 1.3 読解の型（閉じた一覧）

| `vera.reading.type` | 条件 | 層 0 の LLM | 層 1 の LLM |
|---|---|---|---|
| `QUESTION_CROSS` | factual で `_qc_run` が ANSWER | 呼ばない（記録が答え） | 呼ぶ（文法つき） |
| `RECORDS` | 非 factual（文書の有無を問わない。層 1 は文書 1 本以上・語彙が空でない） | 呼ぶ | 呼ぶ（文書 0 本・語彙空・英語だけの文書は呼ばない） |
| `NO_RECORD` | 文書 0 本、または `question_cross.state ∈ {NO_ATTESTED_CELL, NO_TYPED_CANDIDATE, TYPE_EXCLUDED_ALL, DOCUMENTS_NOT_LOADED}` | 呼ぶ（証言の印） | 呼ばない |
| `STRUCTURE_UNDETERMINED` | 上以外のすべて（`QUESTION_NOT_READ`・`NOT_A_QUESTION`・`STRUCTURE_INVALID`・`HOLE_TYPE_UNDETERMINED`・`POLAR_QUESTION`・`TIE`・`AMBIGUOUS_QUESTION_CROSS_TIE`・述語の形・`ERROR`・候補の検証で 0・未知の state） | 呼ぶ（証言の印） | 呼ばない |

`reason` に元の state と理由をそのまま書く。未知の state は `STRUCTURE_UNDETERMINED`（保守側）。同点は棄権。

### 1.4 文法の規則（層 1。`decode_grammar.py`）

**factual（質問の十字が ANSWER のときだけ）**: 文法は有限の文の集合 `alternatives`。
- A2: 充填物の証拠の文（`sources[*].text`）そのもの。
- A3: 質問文の疑問語（`observe_question_records` の `answer.question.wh`）を充填物の表記に置き換え、文末の `？`/`?` を `。` にした文。疑問語が質問文にちょうど 1 回現れるときだけ作る。
- 各候補を作った時点で検証器（§1.5）に通し、(i) 再読して節が 1 つで relations が空、(ii) 日本語なら `semantic_read._w3b3_gates` が None（述語の 4 形と派生の門）、(iii) 再読の十字（center の全鍵と 役割→表記 を NFKC で）が証拠の文の再読の十字と完全に等しい、(iv) 穴の役割の表記が充填物と NFKC で等しい、をすべて満たすものだけを残す。残りが 0 は `STRUCTURE_UNDETERMINED`（`NO_VERIFIABLE_ALTERNATIVE`）。
- 重複は完全一致で 1 つに。並びは A2（出典の順）、次に A3。並びで答えを選ばない（全候補が同じ充填物を述べる）。
- チケット (a)〜(d) との対応: (a) 充填物の表記 = 記録（証拠の文）にある表記だけ。(b) 穴の型に合う配置 direct の語 = `_qc_run` の中の型の確かめそのもの（新しい語の供給源にしない）。(c) 述語 = 記録の述語の書かれた形で W3-b1 の 4 形のどれか（活用形を生成しない）。(d) 極性・時制 = 質問の十字の center と等しいもの。
- JSON schema: `{"type":"object","properties":{"answer":{"type":"string","enum":[alternatives]}},"required":["answer"],"additionalProperties":false}`。GBNF: `root ::= alt0 | alt1 …`、`altN ::= "<リテラル>"`（`\`・`"`・改行を逃がす）。**同じ alternatives の列から** 両方を作る。
- `grammar.id` = `"g-" + sha256(正規化 JSON {kind, alternatives}) の先頭 16 桁`。

**非 factual**: 文法は閉じた語彙の列。語彙 = 渡された文書の全文を読解器のタガー（`semantic_reader._tokens`）で分けた表層の集合。日本語の文書だけ。JSON schema: `answer` は enum の配列（1〜120 個）。GBNF: `root ::= tok{1,120}`。記録に無い語は出ない。出た文はすべて構成。

**ソブリン**: `--sovereign-root/--sovereign-store`（D1）は環境変数を設定するだけで、`apply_to_ask` が従来どおり読む。ソブリンの記録を文法の候補の源にはしない（D3）。

### 1.5 出力の検証（層 0・層 1 共通の検証器）

1. （層 1）文法の検査: JSON として読めない・`answer` が無い・enum の外・語彙の外・個数の外は `OUTSIDE_GRAMMAR`。文法の外の出力は **本文に出さない**（`vera.llm.raw` にだけ残し `withheld: true`）。
2. 文に分ける: `cli._QC_SPLIT`（`。` の後、`.` ＋空白の前）と同じ切り方。
3. 各文を `semantic_read.read` で再読。読めない・節が 1 つでない・relations がある → その文は `UNREAD`（`mark: "UNREAD"`）。読めた文の各腕と center を、記録の文の再読と比べる:
   - 腕の型 `record`: center が等しい記録の十字に、同じ役割で NFKC で等しい表記がある。`evidence` に sentence_id。
   - 文の型 `record`: 十字全体（center 全鍵・役割の集合・各表記の NFKC）が記録の文の十字と完全に等しい。
   - それ以外の腕・文: factual は `testimony`（`{"family":"llm","origin":"testimony","model":…}`）、非 factual は `constructed`。
4. 根拠の方針:
   - factual で **答えになる** のは、(層 0) 記録が答えを持つ（`QUESTION_CROSS`）とき、(層 1) 全文が `record` で穴の役割の表記が Vera の充填物と NFKC で等しく文法の検査を通ったとき、だけ。そのとき `_qc_run` の ANSWER（記録の出所だけ）を `apply_to_ask(request_kind="factual", mode="round5", documents=…)` に通し、`basis_policy.outcome` を使う。
   - それ以外は、記録の出所と LLM の証言の出所を **同じ結果に入れない**（`classify_sources` は document＋testimony を `HUMAN` にするため。実測済み）。証言の出所だけの `{"kind":"unknown",…}` を `apply_to_ask` に通し、その結果は `vera.outcome.basis_policy` に添える。層 0 の LLM の文は outcome `TESTIMONY`、層 1 は `ABSTAIN` 系の固定文。
   - 非 factual: 使った記録の文を出所にした結果を `apply_to_ask(request_kind=<その種類>)` に通し `CONSTRUCTED`。`verdict == "ANSWER"` のままでも事実の答えとして扱わない（判定は `basis_policy.outcome`）。

### 1.6 応答の形

- `/v1/chat/completions`（`stream` 既定 false）: `{"id","object":"chat.completion","created","model","choices":[{"index":0,"message":{"role":"assistant","content":<本文>},"finish_reason":"stop"}],"usage":{…},"vera":{…}}`。`stream: true` は SSE（本文 1 塊、最後の塊に `vera`、`data: [DONE]`。検証が全文を要るのでトークン単位の流しはしない）。
- `/api/chat`（Ollama と同じく `stream` 既定 true）: true は NDJSON、最後の行が `done: true` と `vera`。false は `done: true` の 1 個。
- 本文: `ANSWER_HUMAN_BASIS` は答えの文そのもの（層 0 は記録の文、層 1 は LLM の文）。`CONSTRUCTED` は固定 1 行 `［構成: 事実の主張ではありません］` と改行のあとに LLM の文。`TESTIMONY` は固定 1 行 `［証言: LLM の答えです。記録の裏づけはありません］` と改行のあとに LLM の文。それ以外は Vera の固定文（型ごとに 1 つ）。LLM の原文は `vera.llm.raw` に残す。
- `vera` 欄: `{"schema":"verantyx.fusion/1","layer":0|1,"request_kind","reading":{"type","state","reason","hole_role","hole_type","filler","sources"},"grammar":{…}|null,"grammar_id","llm":{"called","model","ok","error","raw","withheld","skipped_reason"},"grammar_check":{"in_grammar","reason"},"provenance":[{"text","read","mark","origin","sentence_kind","arms":{役割:{"surface","kind","evidence"}},"center_kind"}],"outcome":{"outcome","content_shown","reason","basis_policy"},"timing":{"vera_ms","llm_ms"}}`。
- （r2 で `vera` 欄の全ての鍵を §1.9 (b) に列挙した。上の一覧は登録時のもの。実際の鍵は §1.9 (b) とテスト `test_vera_field_keys_are_the_documented_ones_layer0_and_layer1` が固定している）
- LLM の失敗（接続できない・時間切れ・JSON でない HTTP 応答）は `LLM_UNAVAILABLE`（本文は固定文、200 で返す）。Ollama は標準ライブラリの HTTP で呼び、時間切れと失敗の型（`TIMEOUT`・`CONNECT_FAILED`・`HTTP_ERROR`・`BAD_RESPONSE`）を付ける。

### 1.7 判断記録（実装前）

- **D1** ソブリンの指定は `--sovereign-root ROOT --sovereign-store ID`。チケットの `--store` は最上位の `--store` を上書きする罠があるので使わない（`vera --store X serve` の `X` が保たれることをテストする）。
- **D2** 文法 (b) は語の供給源ではなく既存の型の確かめ。(c)(d) は記録の書かれた形と 4 形の門・十字の一致で縛り、活用形を生成しない。
- **D3** ソブリンの記録は文法の候補にしない。方針の参照は既存どおり。
- **D4** factual の読解は質問の十字だけ（`_qc_run` を呼ぶ。規則を写し直さない）。
- **D5** 依頼の種類は本文の `vera.request_kind` で明示。推定しない。
- **D6** 構成・証言の本文には固定の印を前に付ける（クライアントを変えずに、人が事実と読み違えないため）。
- **D7** `--backend` は `ollama` だけ。GBNF は応答に出すが llama.cpp では測らない（生成に使える gguf が手元に無い）。
- **D8** `--placement DIR` は起動時に `VERA_PLACEMENT` を設定するだけ。配置が無ければ factual は `NO_RECORD`（`NO_TYPED_CANDIDATE`）になる（正しい振る舞い）。
- **D9（オーナー追記を受けて）** 既定は層 0、層 1 は `--strict`。指示書の `--free` は層 0 の別名に読み替える。
- **D10** 層 0 で記録が答えを持つとき LLM は呼ばない。答えは記録の文（証拠つき）で、LLM の言い回しを混ぜない（混ぜると記録の印と証言の印が一つの文に入る）。LLM の価値は、記録が答えを持たない問い・依頼で出る。
- **D11** 層 0 の `TESTIMONY` は事実の答えの outcome ではない（`ANSWER_*` ではない）。Z2 の「誤答」には数えないが、記録の印が付いた文の数は別に数える。

### 1.8 検査データと採点の定義

- 文書 5 本（`artifacts/w10-f01/data/docs/F01.txt`〜`F05.txt`、各 5〜10 文、1 行 1 文）。問い 120（`data/questions.jsonl`）: ONE 50（各文書 10）・NONE 50・CREATIVE 20（`creative` 10・`paraphrase` 10）。
- NONE 50 の内訳（種類ごとの数）: 別の述語・文書に無い物 12、極性の反転 6、時制の反転 6、文書の文より腕が多い 6、文書に無い人物 6、なぜ／どうやって 5、はい／いいえ 5、英語 4。
- 期待（truth）は Vera にも LLM にも通す前に書き、凍結する（`FROZEN.json`・`freeze.txt` に sha256）。凍結後に誤りを見つけたら `corrections.jsonl` に追記し、当てた採点と当てない採点の両方を出す。
- 答え系の outcome = `ANSWER_HUMAN_BASIS`・`ANSWER_FORM_FROM_GENERATED`・`REFERENCE_GENERATED`。
- ONE: **CORRECT** = outcome `ANSWER_HUMAN_BASIS` かつ `reading.filler` と本文の穴の表記が truth.filler と NFKC で等しく、証拠の sentence_id の集合 = truth.sentence_ids。答え系で CORRECT でない = **WRONG**。それ以外 = MISSED（`reading.type` と `reading.reason` ごとに数える）。
- NONE: 答え系 = **WRONG**。層 1 では本文に LLM の文が出た（`content_shown` が真）= **WRONG**。層 0 では本文に LLM の文が出てよい（outcome `TESTIMONY`）が、**記録の印が付いた文**（`provenance[*].sentence_kind == "record"`）が 1 つでもあれば **WRONG**（保守側。NONE の問いに記録の答えは無いので）。それ以外 = CORRECT。LLM を呼んだ件数と、証言として出た件数も数える。
- CREATIVE: 答え系 = **WRONG**。`CONSTRUCTED` = CONSTRUCTED。それ以外 = ABSTAINED。
- 生成だけの ANSWER = 答え系で、`provenance` に `record` の文が 1 つも無いもの（0 でなければならない）。
- Z2 の読み替え（オーナー追記）: 層 0 では「記録に無い事実が記録の印で出た件数 0」。層 1 では従来どおり、文法の外の語 0 と WRONG 0。
- 遅延: `vera_ms` と `llm_ms` の中央値・最大（LLM を呼んだ問いと呼ばない問いを分ける）。

（検査データを書く前の `ls -R artifacts/w10-f01/data` の出力は `artifacts/w10-f01/prereg.txt`。検査データの凍結時刻は `artifacts/w10-f01/data/FROZEN.json`。）

### 1.9 登録後の訂正（第 2 ラウンド。2026-10-04 13:26:10 +0900。§0・§1.1〜§1.8 は事前登録なので書き換えず、ここで置き換える）

(a) **印の規則**（§0 の 3 と §1.5 の 3 を置き換える）: 記録の印は、再読した十字が記録の文と等しい文・腕にだけ付く。LLM の文でも等しければ記録の写しとして印が付く（§0 の 3 の「記録の印を LLM の文に付けない」は実装と食い違っていたので、この規則に置き換える）。十字が等しい、とは **節の `roles` 以外の全ての鍵**（`predicate`・`polarity`・`tense`・`modality`・`voice` に加え、`quantifiers`（回数・数量）など読解器が付けた修飾の全て）の値が等しく、`roles` の集合と各表記（NFKC）が等しいこと。記録の節に無い鍵が文にあれば（例: `弟が犬を三回呼んだ。` の `quantifiers: {event: exactly:3}`）文の印は `record` にならない（閉じた一覧の外は保守側＝記録の印を付けない）。腕の印（`arms[*].kind`）は従来どおり 5 鍵（`predicate`・`polarity`・`tense`・`modality`・`voice`）の一致と、その役割の表記の NFKC 一致で付け、回数などは文の印だけに効く（腕の表記が記録に当たっていることは `弟`・`犬` のとおり本当なので）。層 1 の候補の検査（`_candidate_ok`）も同じ十字の比較を使う。

(b) **`vera` 欄の全ての鍵**（実際に出しているもの。テストで固定）:
- 最上位: `schema`・`layer`・`request_kind`・`reading`・`grammar`（層 1 で文法を作ったときだけオブジェクト、他は `null`）・`grammar_id`・`llm`・`grammar_check`・`provenance`・`outcome`・`timing`。
- `reading`: `type`・`state`・`reason`・`hole_role`・`hole_type`・`filler`・`sources`（各 `source`・`line`・`text`・`sentence_id`）。
- `grammar`: `id`・`kind`（`alternatives`／`vocabulary`）・`summary`・`json_schema`・`gbnf`。
- `llm`: `called`・`model`・`ok`・`error`・`raw`・`withheld`・`skipped_reason`。`grammar_check`: `in_grammar`・`reason`。`outcome`: `outcome`・`content_shown`・`reason`・`basis_policy`。`timing`: `vera_ms`・`llm_ms`。
- `provenance[*]`（出力の文ごと）: `text`・`read`・`mark`（`UNREAD` か `null`）・`unread_reason`・`sentence_kind`（`record`／`testimony`／`constructed`）・`origin`・`evidence`（記録の `sentence_id` の列。文の印が `record` のときだけ入る）・`arms`・`center_kind`・`via`（`cross`／`verbatim`／`null`）。再読できた文だけ `center`（十字の全ての鍵と値）。factual で `record` でない文だけ `source`（`family`・`origin`・`model`）。
- `provenance[*].arms[<役割>]`: `surface`・`kind`（`record`／`testimony`／`constructed`）・`evidence`（腕の表記が一致した記録の `sentence_id`）。

(c) **ベースモデル（§2.3）**: 登録時（11:37）は `qwen3.5:4b` が手元に無かったが、`curl http://127.0.0.1:11434/api/tags` に `qwen3.5:4b`（`modified_at` 2026-10-04T11:38:28+09:00）が加わった。§2.3 の「手元に無く」は登録時点の記述。測定の結果は §2.3 の追記と §4.1。

(d) **スレッド**（§3「できないこと」の lock の項を置き換える）: 配置の SQLite 接続は作ったスレッドでしか使えず、`ThreadingHTTPServer` はリクエストごとにスレッドを作る。そこで Vera の側の処理（文書の読み込みと再読・読解・文法・検証・根拠の方針）は **専用の 1 本のスレッド**（`FusionConfig` の `ThreadPoolExecutor(max_workers=1)`）だけで行う。LLM の呼び出しはそのスレッドの外（並行）。

- **D20** 上の (a)。印の規則の訂正の理由: 第 1 ラウンドのレビューで、記録 `弟が犬を呼んだ。` に LLM の文 `弟が犬を三回呼んだ。` が `record`（`via: cross`、証拠つき）になることが再現された。
- **D21** 上の (d)。理由: 第 1 ラウンドのレビューで、並行する 2 リクエストの 2 本目が `STRUCTURE_UNDETERMINED / ERROR`（`ProgrammingError`）になることが再現された。`ERROR` を安全側（答えない）に倒す扱いは残す。
- **D22** `GET /api/version`（`{"version": "vera-fusion"}`。Open WebUI が Ollama 接続で確かめるため）と、`Content-Length` が数でないときの 400 `bad_json` を足した（レビューの任意の改善）。
- **D23**（オーナーの判断の材料。実装は変えていない）D14（層 0 の事実の問いで記録が答えを持たないとき LLM に文書を渡さない）は安全だが価値が低い。§1.9 (a) の訂正で、記録の印が付くのは十字が全ての鍵で等しい文（記録の写し）だけになったので、文書を渡す案は以前より安全に採れる。ただし NONE の採点（記録の印の文は WRONG）との整理が要る。本ラウンドでは D14 のまま。

---

## 2. 設計書 §2〜§4 の写し（出典: `.claude/vera-audit/tickets/W10-fusion_design.md`）

### 2.1 層（設計書 §2）
| 層 | 内容 | 学習 | 重み | 状態 |
|---|---|---|---|---|
| 0 | 一つの入口: Vera の Ollama／OpenAI 互換 API（`vera_server.py` を基に）。裏で Ollama を呼び、入力の読解（十字・記録との照合）と出力の検証（各文を再読し出所の型を付ける）を挟む。クライアントは変えない | 不要 | API でも可 | 今回（**既定**） |
| 1 | 文法で縛る復号: ターンごとに Vera が「言ってよい構造」を GBNF（llama.cpp）／JSON schema（Ollama `format`）にして渡す。縛れない構造は LLM に言わせず型つきで棄権 | 不要 | 開いた重み | 今回（`--strict`） |
| 2 | LLM を証言の出所に: 未知の語の型・言い換え・一般知識を `origin: testimony` で取り込み、人の確認（D）で昇格 | 不要 | どちらでも | 次 |
| 3 | 構造トークンの微調整（LoRA → GGUF → Ollama） | LoRA | 開いた重み | W3-a6 の後 |
| 4 | 重みへの埋め込み | 本学習 | 開いた重み | 研究 |

### 2.2 高信頼の仕組み（設計書 §3、全層に共通）
- 出力の各文を Vera が再読し、十字の各腕が **記録**（人の文書・ソブリンの昇格済み）／**証言**（LLM・生成コーパス）／**構成**（観測で作った閉包の外）のどれで埋まったかを型で付ける。事実の問いでは記録だけが答え（根拠の方針 A/C/E/D/B をそのまま適用）。
- LLM が補った語は配置に証言として入り、分布か人の確認で裏づけられたときだけ direct（**層 2。このチケットでは作らない**）。
- 縛れない文（読めない・割れる）は出さない（`--strict`）。既定（層 0）では、出すが「証言」「未読」の印をつける。

### 2.3 ベースモデル（設計書 §4）と、このチケットで測ったもの
| 用途 | 設計書の推奨 | 理由（設計書） |
|---|---|---|
| 層 0・1 の既定（手元・Ollama） | **Qwen/Qwen3.5-4B**（オーナーの指定、2026-10-04）。Ollama に無ければ HF の GGUF を `ollama pull hf.co/...` か llama.cpp で載せる。手元の `qwen3.8:27b-mlx` は検証用 | 日本語・英語とも強く、Apache-2.0、llama.cpp/Ollama で GBNF・JSON schema が効く。LoRA の道具が成熟 |
| 層 3 の実験（小さく速く） | Qwen3-1.7B／Qwen2.5-3B-Instruct | 手元の Mac で LoRA が回る |
| 品質を見たいとき | Gemma 3 12B／27B | 日本語が良い。Gemma 利用規約の確認が要る |
| 大きい開いた重み | gpt-oss-20b | 英語中心。日本語は Qwen に劣る見込み |

このチケットの第 1 ラウンドで測ったのは `qwen3.8:27b-mlx` だけ。登録時（11:37）は `qwen3.5:4b` が手元に無かったが、のちに手元の Ollama に加わった（§1.9 (c)）。第 2 ラウンドで `qwen3.5:4b` も同じ検査データで測った（§4.1）。Gemma・gpt-oss は手元に無く（モデルをダウンロードしない約束）、この入口での動作・速度・日本語の質は **未測定**。設計書の「推奨」は設計時の見込みであり、この docs の測定ではない。入口は `--model` に Ollama のモデル名を渡すだけなので、Qwen3.5-4B を載せれば同じスクリプト（`artifacts/w10-f01/scripts/run_eval.py --model <名前>`）で測り直せる。

### 2.4 実装中に追加した判断（事前登録のあと。D1〜D11 は §1.7）
- **D12** `max_tokens`（OpenAI）／`options.num_predict`（Ollama 互換）は、**層 0 の自由な答え**にだけ Ollama の `num_predict` として渡す（不正な値は 400 `BAD_MAX_TOKENS`）。文法つき（`--strict`）は文法が出力の長さを縛るので渡さない。検査では速度のため層 0 に `--max-tokens 200` を付けた（長い答えは途中で切れる）。
- **D13** 文が記録の文と NFKC で逐語に等しいときは、再読できなくても `sentence_kind: record`（`via: "verbatim"`）。層 1 で答えになるには、これに加えて再読できて穴の表記が充填物と等しいことが要る。
- **D14** 層 0 の事実の問いで記録が答えを持たないとき、LLM には **文書を渡さず**、クライアントの会話だけを渡す（LLM の言い換えが記録の印になる経路を作らないため。LLM の答えは常に証言）。非 factual の依頼では文書を system として添える。代償: 読解器が問いを読めないとき、LLM は文書を知らないので「文脈が不足」と答える（§4 の層 0 の MISSED の多くがそれ）。
- **D15** 関係テスト 6 本（`pytest_related_after.txt`）は、指示書の「実装前」には取らず、実装後に 1 回だけ取った（取り損ねた）。基線との比較は全体テストの失敗集合で行う。
- **D16** 層 0 で文書 0 本の創作・言い換えは、LLM が答え outcome `CONSTRUCTED`（根拠の方針は引用元が無いので掛からない: `basis_policy.applied == false`、`NO_CITED_SOURCES`）。層 1 は文法の語彙が作れないので `NO_RECORD`。
- **D17** 層 0 の証言に、人が居るときの確認の問い返し（根拠の方針 D）はまだ付けない（証言の出所は generated ではないので、方針の表でも `CONFIRM_REQUEST` にならない）。
- **D18** 会話の文脈: 読解は最後の user メッセージだけ。層 0 は会話全体を LLM に渡す。層 1 は問いだけを渡す。
- **D19** リクエストの `model`・`format`・`options`（`num_predict` 以外）は無視する。使うモデルは `--model` だけ（応答の `model` もそれ）。

## 3. 応答の形・規則の対応
応答の形は §1.6 のとおり。`vera.outcome.outcome` の閉じた一覧: `ANSWER_HUMAN_BASIS`・`CONSTRUCTED`（根拠の方針の結果）、`TESTIMONY`（層 0 の LLM の文。事実の答えではない）、`NO_RECORD`・`STRUCTURE_UNDETERMINED`（層 1 で LLM を呼ばなかった）、`OUTSIDE_GRAMMAR`・`LLM_UNAVAILABLE`・`LLM_EMPTY`・`ABSTAIN`（固定文）。答え系は `ANSWER_HUMAN_BASIS` だけが実際に出る。

## できないこと（実装と一致させて書く）
- **GBNF を本物の llama.cpp で動かしていない**。応答の `vera.grammar.gbnf` に出すだけ。手元の `.gguf` は語彙だけのもので生成に使えず、モデルをダウンロードしない約束のため。JSON schema（Ollama `format`）は `qwen3.8:27b-mlx` で測った（§4）。
- 読解器が読めない問いは、記録に答えがあっても答えにならない（層 0 は LLM の証言、層 1 は `STRUCTURE_UNDETERMINED`）。検査データでは ONE 50 問のうち層 0 で 21 問、層 1 で 18 問だけが記録の答えになった（`score_layer*.txt`）。到達は読解器の到達で決まる。配置が無いと事実の問いは答えにならない（`NO_TYPED_CANDIDATE`）。
- 層 1 の文法は単文の充填物の問い（質問の十字が FILLED で 1 種）だけ。はい／いいえ・なぜ・どうやって・複文・複数の充填物は作れず棄権。
- ソブリンの記録（確認済みの claim）は文法の候補の源にしない。根拠の方針の参照だけ。
- トークン単位の流しは無い。`stream: true` は本文を 1 塊で送る（検証が全文を要る）。
- 会話の文脈を読まない（最後の user メッセージだけを読む）。依頼の種類は `vera.request_kind` で明示する（自然文から推定しない）。
- 英語の創作・言い換えは層 1 では不可（`CREATIVE_LANG_NOT_SUPPORTED`）。層 0 では LLM が答える（構成の印）。
- 層 0 の `TESTIMONY`・`CONSTRUCTED` の文の真偽は保証しない。保証しているのは **出所の型を偽らない**こと（記録の印は記録に当たった文・腕だけ）。再読できない文は `UNREAD`。
- 構成（`CONSTRUCTED`）の応答でも、LLM の文の十字が記録の文と **全ての鍵で** 等しければ（§1.9 (a)）、その文には `record` の印が付く（記録の写しであって、創作の新しい主張ではない）。回数などの修飾が違えば付かない。読解器が拾わない修飾（`〜てしまった` が `〜た` と同じ十字になるなど）は検証器からも見えない（読解器は禁止ファイルで、このチケットでは直さない）。
- 文書は起動時に 1 回だけ読む（変更は再起動）。
- Vera の側の処理（文書の読み込み・読解・文法・検証・方針）は専用の 1 本のスレッドで直列（§1.9 (d)。LLM の呼び出しは並行）。リクエストが並んだときの待ち時間は `timing.vera_ms` に含まれる。
- ベースモデル: 測ったのは `qwen3.8:27b-mlx` と `qwen3.5:4b` だけ（§2.3・§4・§4.1）。Gemma・gpt-oss は未測定。

## 4. 測定結果（`artifacts/w10-f01/score_layer0.txt`・`score_layer1.txt` を機械で貼ったもの）

検査データの凍結: `data/FROZEN.json`・`freeze.txt`。LLM は `qwen3.8:27b-mlx`（Ollama）、配置は R8、入口は HTTP 経由（`scripts/run_eval.py`）。層 0 は `--max-tokens 200`（自由な答えの長さの上限。速度のため）、層 1 は文法が出力を縛る。


#### 層 0（既定） — `score_layer0.txt`

```
layers={0: 120} wrong=0 generated_only_answers=0 errors=0 missing=0
ONE   n=50 correct=21 wrong=0 missed=29
        missed  22  TESTIMONY|STRUCTURE_UNDETERMINED|QUESTION_NOT_READ
        missed   3  TESTIMONY|NO_RECORD|NO_ATTESTED_CELL
        missed   3  TESTIMONY|NO_RECORD|NO_TYPED_CANDIDATE
        missed   1  TESTIMONY|NO_RECORD|TYPE_EXCLUDED_ALL
NONE  n=50 correct=50 wrong=0 llm_called=50 testimony_shown=50 record_marked_sentences=0
CREATIVE n=20 constructed=20 abstained=0 wrong=0
latency vera_ms_llm_called       n=99 median=42.1 max=75.4
latency vera_ms_llm_not_called   n=21 median=39.1 max=165.3
latency llm_ms                   n=99 median=29223.6 max=42386.4
latency wall_ms                  n=120 median=26417.7 max=42428.7
```


#### 層 1（`--strict`） — `score_layer1.txt`

```
layers={1: 120} wrong=0 generated_only_answers=0 errors=0 missing=0
ONE   n=50 correct=18 wrong=0 missed=32
        missed  22  STRUCTURE_UNDETERMINED|STRUCTURE_UNDETERMINED|QUESTION_NOT_READ
        missed   3  NO_RECORD|NO_RECORD|NO_ATTESTED_CELL
        missed   3  STRUCTURE_UNDETERMINED|STRUCTURE_UNDETERMINED|NO_VERIFIABLE_ALTERNATIVE
        missed   3  NO_RECORD|NO_RECORD|NO_TYPED_CANDIDATE
        missed   1  NO_RECORD|NO_RECORD|TYPE_EXCLUDED_ALL
NONE  n=50 correct=50 wrong=0 llm_called=0 testimony_shown=0 record_marked_sentences=0
CREATIVE n=20 constructed=20 abstained=0 wrong=0
latency vera_ms_llm_called       n=38 median=9.2 max=183.0
latency vera_ms_llm_not_called   n=82 median=21.4 max=56.5
latency llm_ms                   n=38 median=5612.0 max=21811.5
latency wall_ms                  n=120 median=23.2 max=21819.8
```


### 4.1 `qwen3.5:4b`（第 2 ラウンドで追加。同じ検査データ・同じ入口・同じ採点。`score_q35_layer0.txt`・`score_q35_layer1.txt`）

手元の Ollama に後から加わった設計書の推奨モデル（§1.9 (c)）。`qwen3.8:27b-mlx` との比較は、上の表と下の表の同じ行を並べて読む。数値は測った出力そのもの。


#### qwen3.5:4b 層 0（既定） — `score_q35_layer0.txt`

```
layers={0: 120} wrong=0 generated_only_answers=0 errors=0 missing=0
ONE   n=50 correct=21 wrong=0 missed=29
        missed  22  TESTIMONY|STRUCTURE_UNDETERMINED|QUESTION_NOT_READ
        missed   3  TESTIMONY|NO_RECORD|NO_ATTESTED_CELL
        missed   3  TESTIMONY|NO_RECORD|NO_TYPED_CANDIDATE
        missed   1  TESTIMONY|NO_RECORD|TYPE_EXCLUDED_ALL
NONE  n=50 correct=50 wrong=0 llm_called=50 testimony_shown=50 record_marked_sentences=0
CREATIVE n=20 constructed=20 abstained=0 wrong=0
latency vera_ms_llm_called       n=99 median=56.2 max=115.9
latency vera_ms_llm_not_called   n=21 median=46.5 max=156.5
latency llm_ms                   n=99 median=7524.1 max=33690.2
latency wall_ms                  n=120 median=6417.4 max=33743.3
```


#### qwen3.5:4b 層 1（`--strict`） — `score_q35_layer1.txt`

```
layers={1: 120} wrong=0 generated_only_answers=0 errors=0 missing=0
ONE   n=50 correct=18 wrong=0 missed=32
        missed  22  STRUCTURE_UNDETERMINED|STRUCTURE_UNDETERMINED|QUESTION_NOT_READ
        missed   3  NO_RECORD|NO_RECORD|NO_ATTESTED_CELL
        missed   3  STRUCTURE_UNDETERMINED|STRUCTURE_UNDETERMINED|NO_VERIFIABLE_ALTERNATIVE
        missed   3  NO_RECORD|NO_RECORD|NO_TYPED_CANDIDATE
        missed   1  NO_RECORD|NO_RECORD|TYPE_EXCLUDED_ALL
NONE  n=50 correct=50 wrong=0 llm_called=0 testimony_shown=0 record_marked_sentences=0
CREATIVE n=20 constructed=20 abstained=0 wrong=0
latency vera_ms_llm_called       n=38 median=10.1 max=179.7
latency vera_ms_llm_not_called   n=82 median=27.2 max=68.1
latency llm_ms                   n=38 median=2723.6 max=5718.2
latency wall_ms                  n=120 median=35.3 max=5730.3
```


## 5. 応答の例（実際の応答。`eval_layer*.jsonl` から機械で選んで貼る。手で書き換えない）

選び方: (a) Q001 の層 0・層 1 の応答の全体、(b) 層 0 で outcome が TESTIMONY の応答のうち JSON が最も短いもの、(c) 層 0 の CONSTRUCTED のうち JSON が最も短いもの。


#### (a) Q001 `誰が地図を渡した？` — 層 0

```json
{
 "id": "chatcmpl-4c5c20818ddf4252b180618d82df003c",
 "object": "chat.completion",
 "created": 1791087935,
 "model": "qwen3.8:27b-mlx",
 "choices": [
  {
   "index": 0,
   "message": {
    "role": "assistant",
    "content": "太郎が地図を渡した。"
   },
   "finish_reason": "stop"
  }
 ],
 "usage": {},
 "vera": {
  "schema": "verantyx.fusion/1",
  "layer": 0,
  "request_kind": "factual",
  "reading": {
   "type": "QUESTION_CROSS",
   "state": "FILLED",
   "reason": "UNREAD_SENTENCES:11",
   "hole_role": "agent",
   "hole_type": [
    "GROUP_ORG",
    "PERSON"
   ],
   "filler": "太郎",
   "sources": [
    {
     "source": "F01.txt",
     "line": 1,
     "text": "太郎が地図を渡した。",
     "sentence_id": "F01.txt#1:1"
    }
   ]
  },
  "grammar": null,
  "grammar_id": null,
  "llm": {
   "called": false,
   "model": "qwen3.8:27b-mlx",
   "ok": null,
   "error": null,
   "raw": null,
   "withheld": false,
   "skipped_reason": "RECORD_ANSWERED"
  },
  "grammar_check": {
   "in_grammar": null,
   "reason": null
  },
  "provenance": [
   {
    "text": "太郎が地図を渡した。",
    "read": true,
    "mark": null,
    "unread_reason": null,
    "sentence_kind": "record",
    "origin": "record",
    "evidence": [
     "F01.txt#1:1"
    ],
    "arms": {
     "agent": {
      "surface": "太郎",
      "kind": "record",
      "evidence": [
       "F01.txt#1:1"
      ]
     },
     "patient": {
      "surface": "地図",
      "kind": "record",
      "evidence": [
       "F01.txt#1:1"
      ]
     }
    },
    "center_kind": "record",
    "via": "cross",
    "center": {
     "modality": null,
     "polarity": "+",
     "predicate": "渡す",
     "tense": "past",
     "voice": "active"
    }
   }
  ],
  "outcome": {
   "outcome": "ANSWER_HUMAN_BASIS",
   "content_shown": true,
   "reason": "RECORD_ANSWERED",
   "basis_policy": {
    "schema": "verantyx.basis_policy/1",
    "table_version": 1,
    "applied": true,
    "request_kind": "factual",
    "kind_class": "FACTUAL",
    "basis": "HUMAN",
    "basis_original": "HUMAN",
    "human_present": false,
    "show_reference": false,
    "outcome": "ANSWER_HUMAN_BASIS",
    "in_table": true,
    "counts": {
     "human": 1,
     "generated": 0,
     "non_evidence": 0,
     "request_text": 0,
     "unreadable": 0,
     "non_evidence_by_origin": {},
     "unknown_origin": 0,
     "unknown_origin_by_family": {},
     "unknown_origin_values": {}
    },
    "classify_version": 4,
    "confirm_id_version": 2,
    "sovereign": {
     "state": "UNKNOWN_NO_SOVEREIGN",
     "store_id": null,
     "records_read": 0,
     "rejected_by_user": 0,
     "confirmed_records_used": 0,
     "confirmed_records_not_used": 0,
     "ambiguous": false
    },
    "form": {
     "state": "UNKNOWN_NO_INDEX",
     "reasons": {
      "CAND_NOT_ONE_CROSS": 0,
      "CAND_CENTER_DIFFERS": 0,
      "CAND_ROLES_DIFFER": 0,
      "CAND_FILLER_SPAN_AMBIGUOUS": 0,
      "CAND_REREAD_DIFFERS": 0,
      "CAND_CONTENT_DIFFERS": 0
     },
     "families": {
      "local": "UNKNOWN_NO_INDEX",
      "pro": "UNKNOWN_NO_INDEX",
      "code": "UNKNOWN_NO_INDEX",
      "conversation": "UNKNOWN_NO_INDEX",
      "general_qa": "UNKNOWN_NO_INDEX",
      "code_qa": "UNKNOWN_NO_INDEX",
      "figurative_commonsense": "UNKNOWN_NO_INDEX",
      "narrative": "UNKNOWN_NO_INDEX",
      "paraphrase_entail": "UNKNOWN_NO_INDEX"
     },
     "searched_rows": 0,
     "candidates": 0,
     "distinct_forms": 0
    }
   }
  },
  "timing": {
   "vera_ms": 165.281,
   "llm_ms": 0.0
  }
 }
}
```


#### (a) Q001 `誰が地図を渡した？` — 層 1（`--strict`）

```json
{
 "id": "chatcmpl-e58ff153478e44df95cc27fdc7201d6d",
 "object": "chat.completion",
 "created": 1791090796,
 "model": "qwen3.8:27b-mlx",
 "choices": [
  {
   "index": 0,
   "message": {
    "role": "assistant",
    "content": "太郎が地図を渡した。"
   },
   "finish_reason": "stop"
  }
 ],
 "usage": {
  "prompt_tokens": 38,
  "completion_tokens": 17,
  "total_tokens": 55
 },
 "vera": {
  "schema": "verantyx.fusion/1",
  "layer": 1,
  "request_kind": "factual",
  "reading": {
   "type": "QUESTION_CROSS",
   "state": "FILLED",
   "reason": "UNREAD_SENTENCES:11",
   "hole_role": "agent",
   "hole_type": [
    "GROUP_ORG",
    "PERSON"
   ],
   "filler": "太郎",
   "sources": [
    {
     "source": "F01.txt",
     "line": 1,
     "text": "太郎が地図を渡した。",
     "sentence_id": "F01.txt#1:1"
    }
   ]
  },
  "grammar": {
   "id": "g-9457d9730c660c1f",
   "kind": "alternatives",
   "summary": {
    "alternatives_n": 1,
    "fillers": [
     "太郎"
    ],
    "predicate_forms": [
     "渡した"
    ],
    "dictionary_form": "渡す",
    "polarity": "+",
    "tense": "past",
    "sources": [
     "F01.txt#1:1"
    ],
    "sovereign": {
     "state": "NOT_CONFIGURED",
     "used_as_grammar_source": false,
     "reason": "SOVEREIGN_CLAIM_NOT_A_SENTENCE"
    }
   },
   "json_schema": {
    "type": "object",
    "properties": {
     "answer": {
      "type": "string",
      "enum": [
       "太郎が地図を渡した。"
      ]
     }
    },
    "required": [
     "answer"
    ],
    "additionalProperties": false
   },
   "gbnf": "root ::= alt0\nalt0 ::= \"太郎が地図を渡した。\"\n"
  },
  "grammar_id": "g-9457d9730c660c1f",
  "llm": {
   "called": true,
   "model": "qwen3.8:27b-mlx",
   "ok": true,
   "error": null,
   "raw": "{\n  \"answer\": \"太郎が地図を渡した。\"\n}",
   "withheld": false,
   "skipped_reason": null
  },
  "grammar_check": {
   "in_grammar": true,
   "reason": null
  },
  "provenance": [
   {
    "text": "太郎が地図を渡した。",
    "read": true,
    "mark": null,
    "unread_reason": null,
    "sentence_kind": "record",
    "origin": "record",
    "evidence": [
     "F01.txt#1:1"
    ],
    "arms": {
     "agent": {
      "surface": "太郎",
      "kind": "record",
      "evidence": [
       "F01.txt#1:1"
      ]
     },
     "patient": {
      "surface": "地図",
      "kind": "record",
      "evidence": [
       "F01.txt#1:1"
      ]
     }
    },
    "center_kind": "record",
    "via": "cross",
    "center": {
     "modality": null,
     "polarity": "+",
     "predicate": "渡す",
     "tense": "past",
     "voice": "active"
    }
   }
  ],
  "outcome": {
   "outcome": "ANSWER_HUMAN_BASIS",
   "content_shown": true,
   "reason": "ALL_SENTENCES_RECORD_HOLE_MATCHES",
   "basis_policy": {
    "schema": "verantyx.basis_policy/1",
    "table_version": 1,
    "applied": true,
    "request_kind": "factual",
    "kind_class": "FACTUAL",
    "basis": "HUMAN",
    "basis_original": "HUMAN",
    "human_present": false,
    "show_reference": false,
    "outcome": "ANSWER_HUMAN_BASIS",
    "in_table": true,
    "counts": {
     "human": 1,
     "generated": 0,
     "non_evidence": 0,
     "request_text": 0,
     "unreadable": 0,
     "non_evidence_by_origin": {},
     "unknown_origin": 0,
     "unknown_origin_by_family": {},
     "unknown_origin_values": {}
    },
    "classify_version": 4,
    "confirm_id_version": 2,
    "sovereign": {
     "state": "UNKNOWN_NO_SOVEREIGN",
     "store_id": null,
     "records_read": 0,
     "rejected_by_user": 0,
     "confirmed_records_used": 0,
     "confirmed_records_not_used": 0,
     "ambiguous": false
    },
    "form": {
     "state": "UNKNOWN_NO_INDEX",
     "reasons": {
      "CAND_NOT_ONE_CROSS": 0,
      "CAND_CENTER_DIFFERS": 0,
      "CAND_ROLES_DIFFER": 0,
      "CAND_FILLER_SPAN_AMBIGUOUS": 0,
      "CAND_REREAD_DIFFERS": 0,
      "CAND_CONTENT_DIFFERS": 0
     },
     "families": {
      "local": "UNKNOWN_NO_INDEX",
      "pro": "UNKNOWN_NO_INDEX",
      "code": "UNKNOWN_NO_INDEX",
      "conversation": "UNKNOWN_NO_INDEX",
      "general_qa": "UNKNOWN_NO_INDEX",
      "code_qa": "UNKNOWN_NO_INDEX",
      "figurative_commonsense": "UNKNOWN_NO_INDEX",
      "narrative": "UNKNOWN_NO_INDEX",
      "paraphrase_entail": "UNKNOWN_NO_INDEX"
     },
     "searched_rows": 0,
     "candidates": 0,
     "distinct_forms": 0
    }
   }
  },
  "timing": {
   "vera_ms": 182.951,
   "llm_ms": 3229.206
  }
 }
}
```


#### (b) Q011 `誰が電話を取った？` — 層 0、証言

```json
{
 "id": "chatcmpl-1d87816b2ebf46bf83e3c8e4fce5eb65",
 "object": "chat.completion",
 "created": 1791088108,
 "model": "qwen3.8:27b-mlx",
 "choices": [
  {
   "index": 0,
   "message": {
    "role": "assistant",
    "content": "［証言: LLM の答えです。記録の裏づけはありません］\n申し訳ありませんが、私はAIアシスタントであり、あなたの現実の生活や家庭内の状況（誰が電話に出たかなど）を知ることはできません。\n\nもし特定の文脈（例えば、小説の一場面、ニュース記事、あるいは特定の会話の記録など）に基づいて質問されている場合は、その背景やテキストを提供していただければ、お答えできるかもしれません。\n\n一般的な状況であれば、電話は通常、その時点で電話機やスマートフォンにアクセスできる家族や同居人、あるいは秘書などが取るものです。"
   },
   "finish_reason": "stop"
  }
 ],
 "usage": {
  "prompt_tokens": 18,
  "completion_tokens": 104,
  "total_tokens": 122
 },
 "vera": {
  "schema": "verantyx.fusion/1",
  "layer": 0,
  "request_kind": "factual",
  "reading": {
   "type": "STRUCTURE_UNDETERMINED",
   "state": "QUESTION_NOT_READ",
   "reason": "READER_ABSTAINED",
   "hole_role": null,
   "hole_type": null,
   "filler": null,
   "sources": []
  },
  "grammar": null,
  "grammar_id": null,
  "llm": {
   "called": true,
   "model": "qwen3.8:27b-mlx",
   "ok": true,
   "error": null,
   "raw": "申し訳ありませんが、私はAIアシスタントであり、あなたの現実の生活や家庭内の状況（誰が電話に出たかなど）を知ることはできません。\n\nもし特定の文脈（例えば、小説の一場面、ニュース記事、あるいは特定の会話の記録など）に基づいて質問されている場合は、その背景やテキストを提供していただければ、お答えできるかもしれません。\n\n一般的な状況であれば、電話は通常、その時点で電話機やスマートフォンにアクセスできる家族や同居人、あるいは秘書などが取るものです。",
   "withheld": false,
   "skipped_reason": null
  },
  "grammar_check": {
   "in_grammar": null,
   "reason": null
  },
  "provenance": [
   {
    "text": "申し訳ありませんが、私はAIアシスタントであり、あなたの現実の生活や家庭内の状況（誰が電話に出たかなど）を知ることはできません。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:UNREAD_SPAN:interrogative source does not assert a fact",
    "sentence_kind": "testimony",
    "origin": "testimony",
    "evidence": [],
    "arms": {},
    "center_kind": "testimony",
    "via": null,
    "source": {
     "family": "llm",
     "origin": "testimony",
     "model": "qwen3.8:27b-mlx"
    }
   },
   {
    "text": "もし特定の文脈（例えば、小説の一場面、ニュース記事、あるいは特定の会話の記録など）に基づいて質問されている場合は、その背景やテキストを提供していただければ、お答えできるかもしれません。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:UNREAD_SPAN:interrogative source does not assert a fact",
    "sentence_kind": "testimony",
    "origin": "testimony",
    "evidence": [],
    "arms": {},
    "center_kind": "testimony",
    "via": null,
    "source": {
     "family": "llm",
     "origin": "testimony",
     "model": "qwen3.8:27b-mlx"
    }
   },
   {
    "text": "一般的な状況であれば、電話は通常、その時点で電話機やスマートフォンにアクセスできる家族や同居人、あるいは秘書などが取るものです。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:NO_SUPPORTED_CLAUSE",
    "sentence_kind": "testimony",
    "origin": "testimony",
    "evidence": [],
    "arms": {},
    "center_kind": "testimony",
    "via": null,
    "source": {
     "family": "llm",
     "origin": "testimony",
     "model": "qwen3.8:27b-mlx"
    }
   }
  ],
  "outcome": {
   "outcome": "TESTIMONY",
   "content_shown": true,
   "reason": "NO_RECORD_ANSWER:STRUCTURE_UNDETERMINED",
   "basis_policy": {
    "schema": "verantyx.basis_policy/1",
    "table_version": 1,
    "applied": true,
    "request_kind": "factual",
    "kind_class": "FACTUAL",
    "basis": "NONE",
    "basis_original": "NONE",
    "human_present": false,
    "show_reference": false,
    "outcome": "ABSTAIN",
    "in_table": true,
    "counts": {
     "human": 0,
     "generated": 0,
     "non_evidence": 3,
     "request_text": 0,
     "unreadable": 0,
     "non_evidence_by_origin": {
      "testimony": 3
     },
     "unknown_origin": 0,
     "unknown_origin_by_family": {},
     "unknown_origin_values": {}
    },
    "classify_version": 4,
    "confirm_id_version": 2,
    "sovereign": {
     "state": "UNKNOWN_NO_SOVEREIGN",
     "store_id": null,
     "records_read": 0,
     "rejected_by_user": 0,
     "confirmed_records_used": 0,
     "confirmed_records_not_used": 0,
     "ambiguous": false
    },
    "form": {
     "state": "NOT_ATTEMPTED_OUTCOME"
    }
   }
  },
  "timing": {
   "vera_ms": 48.28,
   "llm_ms": 18350.744
  }
 }
}
```


#### (c) Q119 `「旅人は山を越えた。」を言い換えて。` — 層 0、構成

```json
{
 "id": "chatcmpl-30b7c3d2fdff48bdaf6f130d579b501d",
 "object": "chat.completion",
 "created": 1791090775,
 "model": "qwen3.8:27b-mlx",
 "choices": [
  {
   "index": 0,
   "message": {
    "role": "assistant",
    "content": "［構成: 事実の主張ではありません］\n文書 [F05.txt:6] に記載されている「旅人は山を越えた。」を言い換えると、例えば以下のような表現になります。\n\n*   旅人は山を登った。\n*   旅人は山を越えて向こう側へ行った。\n*   旅人は山脈を通過した。"
   },
   "finish_reason": "stop"
  }
 ],
 "usage": {
  "prompt_tokens": 576,
  "completion_tokens": 71,
  "total_tokens": 647
 },
 "vera": {
  "schema": "verantyx.fusion/1",
  "layer": 0,
  "request_kind": "paraphrase",
  "reading": {
   "type": "RECORDS",
   "state": null,
   "reason": null,
   "hole_role": null,
   "hole_type": null,
   "filler": null,
   "sources": []
  },
  "grammar": null,
  "grammar_id": null,
  "llm": {
   "called": true,
   "model": "qwen3.8:27b-mlx",
   "ok": true,
   "error": null,
   "raw": "文書 [F05.txt:6] に記載されている「旅人は山を越えた。」を言い換えると、例えば以下のような表現になります。\n\n*   旅人は山を登った。\n*   旅人は山を越えて向こう側へ行った。\n*   旅人は山脈を通過した。",
   "withheld": false,
   "skipped_reason": null
  },
  "grammar_check": {
   "in_grammar": null,
   "reason": null
  },
  "provenance": [
   {
    "text": "文書 [F05.txt:6] に記載されている「旅人は山を越えた。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:UNREAD_SPAN:uninterpreted colon scope",
    "sentence_kind": "constructed",
    "origin": "constructed",
    "evidence": [],
    "arms": {},
    "center_kind": "constructed",
    "via": null
   },
   {
    "text": "」を言い換えると、例えば以下のような表現になります。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:NO_SUPPORTED_CLAUSE",
    "sentence_kind": "constructed",
    "origin": "constructed",
    "evidence": [],
    "arms": {},
    "center_kind": "constructed",
    "via": null
   },
   {
    "text": "*   旅人は山を登った。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:NO_SUPPORTED_CLAUSE",
    "sentence_kind": "constructed",
    "origin": "constructed",
    "evidence": [],
    "arms": {},
    "center_kind": "constructed",
    "via": null
   },
   {
    "text": "*   旅人は山を越えて向こう側へ行った。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:NO_SUPPORTED_CLAUSE",
    "sentence_kind": "constructed",
    "origin": "constructed",
    "evidence": [],
    "arms": {},
    "center_kind": "constructed",
    "via": null
   },
   {
    "text": "*   旅人は山脈を通過した。",
    "read": false,
    "mark": "UNREAD",
    "unread_reason": "UNREAD:NO_SUPPORTED_CLAUSE",
    "sentence_kind": "constructed",
    "origin": "constructed",
    "evidence": [],
    "arms": {},
    "center_kind": "constructed",
    "via": null
   }
  ],
  "outcome": {
   "outcome": "CONSTRUCTED",
   "content_shown": true,
   "reason": "NON_FACTUAL_REQUEST",
   "basis_policy": {
    "schema": "verantyx.basis_policy/1",
    "table_version": 1,
    "applied": true,
    "request_kind": "paraphrase",
    "kind_class": "NON_FACTUAL",
    "basis": "HUMAN",
    "basis_original": "HUMAN",
    "human_present": false,
    "show_reference": false,
    "outcome": "CONSTRUCTED",
    "in_table": true,
    "counts": {
     "human": 32,
     "generated": 0,
     "non_evidence": 0,
     "request_text": 0,
     "unreadable": 0,
     "non_evidence_by_origin": {},
     "unknown_origin": 0,
     "unknown_origin_by_family": {},
     "unknown_origin_values": {}
    },
    "classify_version": 4,
    "confirm_id_version": 2,
    "sovereign": {
     "state": "NOT_CONSULTED",
     "store_id": null,
     "records_read": 0,
     "rejected_by_user": 0,
     "confirmed_records_used": 0,
     "confirmed_records_not_used": 0,
     "ambiguous": false
    },
    "form": {
     "state": "NOT_ATTEMPTED_OUTCOME"
    }
   }
  },
  "timing": {
   "vera_ms": 16.361,
   "llm_ms": 9361.32
  }
 }
}
```
