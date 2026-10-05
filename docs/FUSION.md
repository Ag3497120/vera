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

## 6. W10-f04 受け入れ口の契約（事前登録 K280〜K287。2026-10-04、実装・検査データの凍結より前）

設計: `ops/decisions/2026-10-04_VERA_BASE_V1.md` §1.5・§2 A9/A10・§4、`ops/decisions/2026-10-04_fusion_design_principles.md`。方針: Vera のベース（規則）は固定。LLM は語彙が足りないときに **候補** を出す提案者で、読む・決める・答える・棄権するは Vera の規則。
この節は実装より前に書く。変えるときは前後の全文をここに残す。数値は `artifacts/w10-f04/` の出力から機械で貼る（この節の前半に数値は無い）。

### 6.1 口の一覧（契約）
| 口 | 入口 | 入力 → 出力（鍵は閉じた一覧） |
|---|---|---|
| A9 穴つきの十字 | `semantic_read.read_with_holes(text, lang=None, *, placement, max_holes=2)`、`vera read --holes` | `read()` の出力（鍵・値・順序そのまま）の末尾に `holes_status`・`holes`・`partial`。`readable` と `abstain` は変えない |
| O1 候補の問い | `fill_candidates.ask_and_gate(...)` | 穴 → 開いた申告（型・役割・近い語 K 個以内）→ 閉じた一覧（`llm_choice.LLMChooser`）→ `FillDecision` |
| O2 証言の台帳 | `testimony_ledger.TestimonyLedger`、`vera ledger list|show|confirm` | 追記のみ・ハッシュ連鎖。確認の状態 `unconfirmed|reread_agreed:<n>|distribution_backed|human_confirmed`、`promotable` |
| O4 再読の門 | `fill_candidates.gate` | (a1)(a2)(b)(c)(d) を順に。最初に落ちた門の型を `gate_log` に残す |
| O5 座標の受け渡し | `fill_candidates.coordinates` | 穴・十字の直列化。`verantyx/cross_tokens.py`（W10-f03 から byte 一致で写した 1 ファイル）。`cross_tokens_version` = `cross_tokens.SCHEMA` |
| O6 後段の差し替え | `llm_backend.chat(backend, model, messages, fmt, ...)` → `{ok, content, usage, error}` | `ollama`・`openai`（`VERA_LLM_API_BASE`／`VERA_LLM_API_KEY`）・`fake`（台本）。失敗の型 `TIMEOUT`・`CONNECT_FAILED`・`HTTP_ERROR`・`BAD_RESPONSE`（fake は `SCRIPT_EXHAUSTED`） |

`holes_status` の値（閉じた一覧）: `HOLES_FOUND`・`READ`・`NO_PLACEMENT`・`LANG_NOT_SUPPORTED`・`NOT_A_FILLER_CAUSE:<最初の理由>`・`HOLE_NOT_PROBE_READABLE`・`HOLE_NO_EXPECTED_TYPES`・`HOLE_CROSS_DEPENDS_ON_TYPE`・`HOLE_TOO_MANY`・`HOLE_COMPLEX_FILLER`。
`holes[i]` = `{arm, particle, head, expected_types, role_candidates, placement_state, why}`。`expected_types`・`role_candidates` は **集合を文字列順に書いたもの** で、順位ではない（先頭が優先、という読み方をしない）。
`FillDecision.status` は `ADOPTED`・`NOT_ADOPTED`・`BACKEND_FAILED`・`NO_HOLE`。`reason`: `GATE_A_NOT_PLACED:<理由>`・`GATE_A_TYPE_NOT_EXPECTED`・`GATE_A_DECLARED_TYPE_MISMATCH`・`GATE_A_DECLARED_TYPE_NOT_OF_HOLE_WORD`（第 2 ラウンドの置き換え）・`GATE_B_REREAD_<何が違うか>`・`GATE_C_CONTRADICTS_RECORD:<sentence_id>`・`GATE_D_TIE`・`GATE_D_CHOICE_NOT_PASSING`・`GATE_D_CHOICE_<status>`・`OPEN_DECLARATION_INVALID:<why>`・`NO_CANDIDATE_WORDS`・`NO_CANDIDATE_PASSED`・`BACKEND_FAILED:<型>`（`EMPTY_CONTENT` を含む）。

### 6.2 規則（事前登録）
- **K280 穴の条件**: 穴になるのは、読解の棄権理由が充填物の配置（`PLACEMENT_(UNPLACED|MULTIPLE|UNKNOWN):<助詞>:<語>` で助詞が 9 つの格助詞 `semantic_reader._CASE_PARTICLES_9`）に由来するときだけ。述語が読めない・構成が読めない（複文・並立・係助詞・引用・照応）文、K63 の残り部分（`part`）は穴にしない（従来どおり棄権）。手順: (1) `read` が読めれば `READ`、配置が無ければ `NO_PLACEMENT`、英語は `LANG_NOT_SUPPORTED`。(2) 棄権の理由（`abstain.reasons` と `typed_explain_ja` の `w3b1`・`w3b2`・`frame`）に上の理由が無ければ `NOT_A_FILLER_CAUSE`。(3) 探針: その語の問い合わせだけに `DECIDED / direct / decided_by ["hole_probe"]` の型 T を返す包みで、`coarse_types.NOUN_TYPES` の各 T について `read` し直す。読めて・節が 1 つ・relations が空・その語の腕の `role_basis` が T の型を示す T の集合 = `probe_types`。(4) `table_types` = その述語の型について、読解器の表（`typed_frames_w3b5_rows()`）と段 R の枠（`predicate_role_frame`）がその助詞に許す型の和。CONFIRMED の枠（`predicate_frame`）があればその助詞の型で狭める。**表は import して読むだけ**。(5) `expected_types` = `probe_types ∩ table_types`、空なら穴にしない（`HOLE_NO_EXPECTED_TYPES`）。(6) 各 T で得た節の、穴の腕以外が同じでなければ穴にしない（`HOLE_CROSS_DEPENDS_ON_TYPE`）。穴の腕の役割名の集合 = `role_candidates`（1 つなら `arm`、2 つ以上なら `arm: null`）。(7) 1 つの穴を埋めても別の充填物の理由で止まるときは、その語も 2〜6 で穴にする（最大 `max_holes`＝2、型の直積は 17×17＝289 以内）。超える・3 つ目 → `HOLE_TOO_MANY`。(8) 穴の語が `X の Y` のように腕の表記全体でないとき `HOLE_COMPLEX_FILLER`（保守側: 腕の一部だけを置き換える規則を足さない）。
- **K281 問いの形**: 開いた申告（1 回）= 後段の `fmt` に JSON schema `{type: enum(NOUN_TYPES), role: enum(role_candidates ∪ {null}), near_words: array(string, 0〜K)}`・`additionalProperties: false`（K 既定 5）。返答が JSON でない・schema 外・enum 外は `OPEN_DECLARATION_INVALID`（後段の失敗とは別の型）。閉じた一覧の問いは `llm_choice.LLMChooser.choose` をそのまま（2 回の問い・順序と文面を変える・不一致は棄権・説明や複数は無効）。一覧 = `near_words` のうち門 (a1)(a2) を通った語。台帳（`ChoiceLedger`）は証言の台帳とは別ファイル。
- **K282 採用の門**: 候補 C0 = `near_words`（NFKC で重複を除く。順序は使わない）。各語に (a1)(a2)(b)(c) をこの順でかけ、最初に落ちた門の型を `gate_log` に記録する。(a1) 配置の答えを `placement_type` に通して型が 1 つ決まり、その型が `expected_types` に入る。(a2) 開いた申告の `type` が `expected_types` に入り、かつ候補の型と一致する（J4）。(b) 元の文の穴の語を候補に置き換えた文を本物の配置で再読して、節が 1 つ・`observe.content_of_cross` が「探針の十字の穴の腕の表記を候補にしたもの」と一致・穴の腕の役割が `role_candidates` のどれか、かつ `cross_tokens.realize_tokens` が `REALIZED`。(c) 読み込んだ文書とソブリンの記録のうち、埋めた十字と述語・時制・他の腕がすべて同じで **極性だけが逆** のものがあれば不採用（記録が無いことは矛盾ではない。`records_checked` を残す）。(d) 残りが 0 なら不採用、2 つ以上なら `GATE_D_TIE`（同点棄権）、1 つなら閉じた一覧の問いをして、`ADOPTED` かつ選ばれた語がその語のときだけ採用。通ったものは `origin: testimony`、`basis: LLM_TESTIMONY_FILL:<model>:<decision_id>`。
- **K283 印**: 候補で埋めた腕は答えの中で常に `kind: testimony_fill`、根拠の方針では `testimony`（`basis_policy` は変えない。`DECLARED_NON_EVIDENCE` に入っている）。**事実の問いで候補を記録扱いした瞬間に誤答** と定義する。使ってよいのは、層 0 の LLM の出力文の腕の印、`vera.holes[i].clarify`（聞き返しの候補の提示。`content` には入れない）だけ。
- **K284 台帳**: 追記のみ。1 行の sha は前の行の sha を含む。書き換え・行の削除・末尾の切り詰め・順序の入れ替えは `LedgerIntegrityError` で検出される。行の種類: `testimony`・`reread_agreed`（同じ (語, 候補, 申告の型, 役割) が **別の文の sha** で再び門を通った）・`distribution_backed`・`human_confirmed`・`promotable`。**`promotable` の条件（凍結）**: `reread_agreed` が N（既定 3）以上、または `distribution_backed`、または `human_confirmed`。加えて狭める方向（J6）: 同じ語に別の候補が採用された行があれば `promotable` にしない（`CONFLICTING_TESTIMONY`）。人の確認は `vera ledger confirm <id>`（`store_id`・`confirm_id` を発行）。`fill_candidates` は `human_confirmed` を決して書かない。配置は変えない（W10-f05 まで）。
- **K285 後段**: 後段の失敗（接続・時間切れ・空・形式外）は型つき失敗で、「候補なし」に変換しない（`BACKEND_FAILED:<型>`）。後段を替えても K280〜K284 は変わらない（同じ台本 → 同じ判断）。
- **K286 利用者の文の秘匿**: `mask_user_text` の既定は **オン**。オンのとき後段へ渡るのは穴の型・役割・述語・穴の語・助詞・配置の語彙の候補一覧・座標（穴以外の腕の表記は `〈型〉` に置換）だけで、利用者の文そのもの・その sha256・穴以外の腕の表記は渡さない。台帳にも文は書かない（sha だけ）。「利用者の文」= 文全体と穴以外の腕の表記と解釈する（J5）。
- **K287 不変**: `--fill` を渡さない既定の `semantic_read`・`vera read`（`--holes` なし）・`vera ask`・`vera chat`・`vera observe`・`vera route`・`vera serve` の出力は基点と byte 一致。`fill` があるときだけ `vera.holes`・`vera.ledger_ids` が付く（J7）。

### 6.3 判断の記録（事前登録）
- **J1** 基点に `vera read` は無いので新設。`--holes` なしは `semantic_read.main` への委譲（byte 一致）。**J2** `CROSS_TOKENS_VERSION` は写したファイルに足さず（差分 0 を優先）、`fill_candidates` で `cross_tokens.SCHEMA` を参照。**J3** 型の enum は 17（`coarse_types.NOUN_TYPES`）。チケットの「18 型」は 17 の誤記として扱う。**J4** 門 (a2): 申告の型＝候補の型を足す（狭める方向。人・場所の語が「時」の穴になる実測への対処）。**J5** K286 の「利用者の文」の解釈（上）。監査役の確認事項。**J6** 同じ語に別の候補が採用された行があれば `promotable` にしない。**J7** `vera.holes`・`vera.ledger_ids` は fill のときだけ付く。**J8** `describe_holes` は純粋関数の追加にとどめ、`vera observe` の出力は変えない（表示は `vera read --holes` の `display` 鍵）。**J9** `serve --fill` 系の引数は、(7)(8) を既定の入口から到達させる最小の追加（監査役の確認事項）。

### 6.4 検査データ（`tests/fusion/w10f04/`。凍結の sha は `artifacts/w10-f04/data_freeze.sha256`）
`holes.jsonl`（穴になる行・ならない行。期待は手で書き、`table_types` は表から: `artifacts/w10-f04/scripts/table_types.py`）、`fake_scripts.jsonl`（fake 後段の台本。各門で落ちる行・採用される行・後段の失敗・形式外）、`real_holes.jsonl`（本物の後段で流す 30 穴。期待は書かない＝目視）。生成: `artifacts/w10-f04/scripts/make_data.py`（実装に依存しない oracle: `mine_candidates.py`・`mine_pairs.py`）。以後これらを変えたら `data_freeze.r<N>.sha256` を足し、理由をこの節に書く。

**検査データの変更記録 r1（2026-10-04、実装の最初の測定のあと。`data_freeze.r1.sha256`）**: `holes.jsonl` の 1 行 `H-NEG-057`（本文 `abc def。`）の期待 `expect_status` を `NOT_A_FILLER_CAUSE` から `LANG_NOT_SUPPORTED` に直した。理由: 本文は ASCII だけで言語が英語と判定され、K280 の手順 (1)（言語の判定が理由より先）に従えば `LANG_NOT_SUPPORTED` が正しい。作者の期待の誤り（機械的な分類が言語を見ていなかった）で、実装の側を合わせたのではない。`is_hole: false` は変わらない。他の 137 行と `fake_scripts.jsonl`・`real_holes.jsonl` の sha は変わっていない（`diff` はこの 1 ファイル `holes.jsonl` の行だけ）。

**第 2 ラウンドの置き換え（2026-10-04 21:2x、中間職のレビュー `review.r1.md` の M1〜M3 への対応。§6.2・§6.3 の事前登録の文面は書き換えず、ここで置き換える。前の文面を残す）**
- **M1 / J12 門 (a3)（K282 に足す）**。前の文面: 「(a2) 開いた申告の `type` が `expected_types` に入り、かつ候補の型と一致する（J4）」と、開いた申告の問い「type は上の型から 1 つ」（入ってよい型を見せて選ばせていた）。問題: 申告が常に穴の位置の型と一致し、(a2) は何も落とさなかった（P4 r1 で qwen3.5:4b は人・会社・地名の穴に `TIME`、手紙の穴に `ANIMAL` を申告し、中間職の fake 台本で同じ形が誤採用になった）。置き換え: (i) 問いは「語『X』そのものの型をスキーマの型の一覧から 1 つ。この位置に入る型に合わせず、語の意味だけで決める」。位置の型 `expected_types` は `near_words` の条件の文にだけ書く。(ii) 門 (a3): 穴の語（元の文の語）の配置の答えを `event_cross.PlaceResult.from_coarse_query(...).types` で読み（答えの欄を直接読まない）、型が **1 つでもある** とき（DECIDED／MULTIPLE。推定を含む）、申告の型がその中に無ければ `GATE_A_DECLARED_TYPE_NOT_OF_HOLE_WORD`。型が無い語（UNPLACED／UNKNOWN）は比べるものが無いので通し、後の門が決める。語の一覧は足していない。**残るリスク（隠さない）**: 配置が穴の語に位置の型を候補として持つ場合（r8 の `東京` = [PLACE, TIME]）、`TIME` の申告は (a3) を通る（`F-A3R-01`）。UNPLACED／UNKNOWN の語（例 `搬出口`）は申告しだい。 **（J12 は第 3 ラウンドの裁定 A で置き換え。§6.6 を見よ。この文は消さずに残す）**
- **M2 座標**。前の文面: 座標は探針の最初の型（文字列順）で作った十字をそのまま直列化した（穴の腕の `provenance.role_basis` に `placement_direct:<試した型>` が入り、LLM への暗示になっていた）。置き換え: 座標は穴の型の直積のうち読める **すべて** の型で十字を作り、穴の腕の `role_basis` を `hole` に置き換え、全部同じ行になるときだけ送る。違うときは `tokens: null, reason: COORDINATES_DEPEND_ON_PROBE_TYPE`（型つき。最初の型を選ばない）。
- **M3 / J13 門 (c)**。前の文面: 「読み込んだ文書とソブリンの記録のうち…」。実際: ソブリンの主張は文の記録ではない（`decode_grammar._sovereign_summary` の `SOVEREIGN_CLAIM_NOT_A_SENTENCE`）ので、(c) は読み込んだ文書の十字だけと比べる。`FillDecision.sovereign_checked` は常に `false`（型つきの欄。**監査役の確認事項**）。`records_checked` は「実際に比べた記録の数」で、比べられなかったときは 0 と `gate_log[].c_note`（`GATE_C_NOT_CHECKED:NOT_READABLE`／`GATE_C_NOT_CHECKED:OTHER_HOLES_NOT_READABLE`）。2 つ穴の文では他の穴を探針で置き（門 (b) と同じ）、読める型の組すべてで比べ、どれかで矛盾すれば不採用。比べられないことは不採用の理由にしない（記録が無いことは矛盾ではない、の保守的な読み）。
- **検査データの変更記録 r2（`data_freeze.r2.sha256`、`data_freeze_time.r2.txt`）**: `fake_scripts.jsonl` の 11 行（`F-ADOPT-06/08/11/12/15`・`F-C-03/06/07`・`F-D-04/11`・`F-BACKEND-12`）は、凍結時の台本の申告の型が穴の語の型（`客`・`夫婦` = NATURAL_PHENOMENON／PERSON、`勝利` = EVENT_ACT／PLACE／TIME）に無く、(a3) で落ちるようになった。各行の **期待の種類（ADOPTED／どの門で落ちるか）は変えず**、申告の型と候補の語を穴の語の型に合う語に替えた（ANIMAL・GROUP_ORG・WORK の申告 → PERSON または EVENT_ACT。候補 犬・学校・会社・小説・猫 → 兄・姉・弟・達成・妹。記録の文も同じ語に）。前の台本は `artifacts/w10-f04/fake_scripts.r1.jsonl`。新しい行 13 件を足した（`F-A3-01〜12`: P4 r1 の申告の形で `NOT_ADOPTED` ＋ `GATE_A_DECLARED_TYPE_NOT_OF_HOLE_WORD`、`F-A3R-01`: 残るリスクの記録として `ADOPTED`）。`holes.jsonl`・`real_holes.jsonl` の sha は変わらない。

### 6.5 W10-f04 の測定結果（`artifacts/w10-f04/` の出力を機械で貼ったもの。手で書いた数値は無い）
- 追加の判断: **J10** 門 (b) の実現→再読（`cross_tokens.realize_tokens`）は、実現器が再読を配置なしで行い主題を「は」で書くため、型つきの十字（agent＋goal など）を候補に関わらず拒否する（`p4_real.txt` の `realize_status_of_passed_words`）。そのため実現の結果は `gate_log[].realize` に記録し、`require_realize=True` のときだけ門にする（既定は偽）。常に掛けるのは「候補を入れた文を本物の配置で再読し、探針の十字と内容が一致する」検査。監査役の確認事項。**J11** `holes[i]` に `span`（文中の位置）を足した（契約の鍵への追加）。`REFUSED` を `FillDecision.status` に足した（台帳の破損 `LEDGER_INTEGRITY`）。`reread_agreed` の n は「別の文の sha で再び通った行の数」（原文＋n 文）。`human_confirmed` だけは `CONFLICTING_TESTIMONY` を越える。
- P1 入口 4,149 文（配置なし・r8・問い合わせ記録）: `p1_entry.txt` = P1_ENTRY_SAME。serve（質問 120＋B7 35 件、両層）: `p1_serve.txt` = P1_SERVE_SAME。ask/chat/observe/route/read: `z1_cmp.txt`:
```
case 1: same (byte-identical, both runs)
case 2: same (byte-identical after masking ingest_ms and elapsed_ms, the only lines that differ between two runs of the base)
case 3: same (byte-identical after masking ingest_ms and elapsed_ms, the only lines that differ between two runs of the base)
case 4: same (byte-identical after masking ingest_ms and elapsed_ms, the only lines that differ between two runs of the base)
case 5: same (byte-identical, both runs)
case 6: same (byte-identical, both runs)
case 7: same (byte-identical, both runs)
case 8: same (byte-identical, both runs)
case 9: same (byte-identical, both runs)
case 10: same (byte-identical, both runs)
case 11: same (byte-identical, both runs)
case 12: same (byte-identical, both runs)
stderr: every case/run not listed as STDERR DIFFERENT above is byte-identical
```
- P2 穴の抽出（`p2_holes.txt`）:
```
rows=138 hole_expected=62 hole_got=62 wrong_hole=0 missed=0 types_outside_table=0 empty_types=0 status_mismatch=0 expected_types_differ_from_oracle=0
status_counts {'HOLES_FOUND': 62, 'NOT_A_FILLER_CAUSE': 52, 'HOLE_NOT_PROBE_READABLE': 14, 'LANG_NOT_SUPPORTED': 4, 'READ': 3, 'NO_PLACEMENT': 3}
```
- **第 2 ラウンドの測定（M1〜M3 の修正後。第 1 ラウンドの出力は `*.r1.*` に残してある）**
- P3 fake 後段（`p3_fake.txt`、`p3_pytest.txt`。台本は r2 の 103 行）:
```
rows=103 mismatch=0 adopted=16 adopted_arms_all_testimony_fill_origin=True
rows_per_gate {'ADOPT': 15, 'A1': 12, 'A2': 11, 'B': 11, 'C': 10, 'D': 11, 'BACKEND': 12, 'OPEN': 6, 'NONE': 2, 'A3': 12, 'A3R': 1}
outcomes {'A1/NOT_ADOPTED/GATE_A_NOT_PLACED': 8, 'A1/NOT_ADOPTED/GATE_A_TYPE_NOT_EXPECTED': 4, 'A2/NOT_ADOPTED/GATE_A_DECLARED_TYPE_MISMATCH': 11, 'A3/NOT_ADOPTED/GATE_A_DECLARED_TYPE_NOT_OF_HOLE_WORD': 12, 'A3R/ADOPTED/ADOPTED': 1, 'ADOPT/ADOPTED/ADOPTED': 15, 'B/NOT_ADOPTED/GATE_B_REREAD_NOT_READABLE': 11, 'BACKEND/BACKEND_FAILED/BACKEND_FAILED': 12, 'C/NOT_ADOPTED/GATE_C_CONTRADICTS_RECORD': 10, 'D/NOT_ADOPTED/GATE_D_CHOICE_ABSTAINED': 2, 'D/NOT_ADOPTED/GATE_D_CHOICE_NOT_PASSING': 3, 'D/NOT_ADOPTED/GATE_D_TIE': 6, 'NONE/NOT_ADOPTED/NO_CANDIDATE_WORDS': 2, 'OPEN/NOT_ADOPTED/OPEN_DECLARATION_INVALID': 6}
54 passed in 6.59s
```
- P4 本物の後段 qwen3.5:4b（`p4_real.txt`、目視の表 `p4_visual_review.md`。目視であり正解データではない。第 1 ラウンドは `p4_real.r1.txt`・`p4_visual_review.r1.md`）:
```
holes=32 sentences=30 adopted=1 not_adopted_by_reason={"GATE_A_NOT_PLACED": 19, "NO_CANDIDATE_WORDS": 9, "ADOPTED": 1, "GATE_A_TYPE_NOT_EXPECTED": 3} backend_failed=0
vera_ms p50=8.1 p95=37.7 total=442.3 | llm_ms p50=2174.7 p95=3301.9 total=74748.8
declared_type_vs_word {'True': 22, 'False': 7, 'None': 3}
realize_status_of_passed_words {'REFUSED': 1}
```
- P5 送信内容（`p5_sent_check.txt`、`p5_mask.txt`）:
```
rows=103 messages_checked=249 leaked_sentence=0 leaked_sentence_sha=0 leaked_other_arm=0
```
- P6 台帳・後段の差し替え（`p6_pytest.txt`）: 33 passed in 0.44s
- P1（第 2 ラウンドの取り直し）: `p1_entry.txt` = P1_ENTRY_SAME、`p1_serve.txt` = P1_SERVE_SAME、`z1_cmp.txt` は全 12 case が same（stderr も一致）。P2: `p2_holes.txt` は第 1 ラウンドと同じ（wrong_hole=0）。

### 6.6 第 3 ラウンドの置き換え（監査役の裁定 A・B。2026-10-04 22:06:03 +0900。事前登録: 検査データの r3 の凍結とコードの変更より前）
前の文面（§6.2 K282、§6.4 の J12）は書き換えず、ここで置き換える。出典: チケット末尾「監査役の判断（2026-10-04 21:53:34 +0900）」。背景: 未公開の検査で R 型の誤採用 2 件（東京→夏、税務署→夜）。候補が語ではなく構造（に の役割: 場所→時）を決めてしまう形で、誤読に当たる。

**門の順序（K282 の置き換え）**: `(a1) → (a2) → (a3) → (a4) → (b') → (b) → [実現: require_realize のときだけ] → (c) → (d)`。各語の最初に落ちた門を `gate_log` に記録する（形は今と同じ）。

**(a4) 穴の語の配置（裁定 A。J12 を置き換える）**
- 穴の語の型 `own = EC.PlaceResult.from_coarse_query(query.query(hole["head"])).types`（(a3) と同じ読み方）。
- `own` が空、または `hole["placement_state"]` が `UNPLACED`／`UNKNOWN`（型を 1 つも与えない）→ `GATE_A_HOLE_WORD_UNPLACED`。候補と申告は台帳に証言（`not_adopted` 行）として残る。
- それ以外: `own` の各型 T について、他の穴は `expected_types` の直積のすべての組で、元の文を `_HoleProbe(query, {他の穴: 組, 穴の語: T}, shared)` で読む。読めて、かつ穴の腕の役割が 1 つに決まればその役割、読めない・決まらないなら `None`。すべての (T, 組) で役割が **同じ 1 つ**（`None` を含まない）ときだけ通る（その役割を `a4_role` として後の門へ渡す）。そうでなければ `GATE_A_ROLE_SPLIT`（K273 の同点棄権と同じ考え）。区別は `gate_log` の `split_kind` に型で残す: `ROLES_DIFFER`（読めた役割が 2 つ以上）／`TYPE_NOT_READ`（ある型で読めない）。理由の文字列は `GATE_A_ROLE_SPLIT` のまま。
- 最初に読めた型・辞書順で役割を選ばない。「読めない型」を無視して残りの型だけで同じ役割と判断しない（東京 = [PLACE, TIME] が通ってしまう）。
- (a4) は候補の語に依存しないので穴ごとに 1 回だけ計算する（記録は語ごと、(a1)〜(a3) を通った語にだけ付く）。`gate_log` の行: `{word, gate: a4, reason, hole_word_state, hole_word_types, role_by_type, split_kind}`。型と役割名だけで利用者の語は入れない（K286）。

**(b') 型注入の再読（裁定 B。すべての採用に課す。門 (b) の代替ではなく追加）**
- 実現器が型つきの十字を拒むので実現→再読は課せない（J10。実現器は A8 で別に直す）。代わりに、(a4) を通った語の型 wtype（申告の型 = 候補の配置の型）で、他の穴の各組について **元の文** を `_HoleProbe(query, {他の穴: 組, 穴の語: wtype}, shared)` で読み直す（`semantic_reader.py` は触らない。問い合わせの差し替え）。
- 合格の条件（すべての組で）: (1) 読める、(2) 穴の腕の役割 == `a4_role`、(3) 節の `roles`・`role_basis` 以外の鍵が `hole_result["partial"]` の同じ鍵と一致（中心）、(4) 穴でない腕の `roles`・`role_basis` が `partial` のものと一致。1 つでも違えば `GATE_B_REREAD_MISMATCH`、`gate_log` に `b_prime_detail`: `NOT_READABLE`／`ARM_ROLE_DIFFERS`／`CENTER_DIFFERS`／`OTHER_ARMS_DIFFER`。合格した語の `passed` 行に `a4_role`・`b_prime: PASSED`。
- 既存の門 (b)（候補を入れた文を本物の配置で再読）とその理由の型は残す（狭める側。外すと緩む）。

**判断の記録（第 3 ラウンド。事前登録）**
- **J14** (a4) で不採用になっても、台帳の `not_adopted` 行に申告（`declaration`）と `gate_log`（語つき）が残る。`vera ledger confirm` は `testimony` 行だけを相手にする今の作りを変えない。裁定の「昇格の道は残る」は行が残ることで満たし、どう昇格させるかは W10-f05。
- **J15** `GATE_A_ROLE_SPLIT` は「ある型で読めない」場合も含む。区別は `split_kind`。
- **J16** 構造上の帰結: 読解器の `placement_fit`（K95）は、MULTIPLE の直接の答えで候補の型がすべて許されるなら既に読むので、「穴の語の候補がすべて同じ役割に落ちる」穴は、別の穴（読めない語）と同じ文にあるときだけ現れる。したがって **1 穴の文では (a4) により採用しない**。採用しうるのは 2 穴の文の、K95 で読める語の穴だけ。実測した件数は §6.6 の結果に貼る。
- **J17** 門 (b)・(c) は口の経路（2 穴の文）では到達しにくい（候補を入れた文の再読が落ちない・r8 で読める本物の記録が作れない）。門そのものの検査は関数を直接呼ぶ行（`call: gate_b|gate_c`）で保つ（期待は変えない）。口の経路で落ちた件数は実測して書く。

### 6.6 の結果（第 3 ラウンド。`artifacts/w10-f04/` の出力を機械で貼ったもの。第 2 ラウンドの出力は `r2_*` の名で退避してある）
- 時刻の順（`prereg_time.r3.txt` < `data_freeze_time.r3.txt` < コードの変更）: 事前登録 2026-10-04 22:06:03 +0900、検査データ凍結 2026-10-04 22:09:48 +0900。凍結の sha（`data_freeze.r3.sha256`）:
```
980ac8e6dc8d4cebe2db9b5c9722ca959f2f981487348c702bd429f1a5e33a4d  tests/fusion/w10f04/fake_scripts.jsonl
44625d7ea235467bfce2ce31e3a9cd1f273f7bcf41a3da4b5ccc260385186fcf  tests/fusion/w10f04/holes.jsonl
6c64886fdd726ba1198c48290ba5c6b1ec430cf4d6111925440371bbb998a3be  tests/fusion/w10f04/real_holes.jsonl
```
  `holes.jsonl`・`real_holes.jsonl` の sha は第 2 ラウンド（`data_freeze.r2.sha256`）と同じ。`fake_scripts.jsonl` だけが変わった（生成: `artifacts/w10-f04/scripts/make_data_r3.py`。実装に依存しない oracle: 配置 r8 の答えと、穴の語を型で差し替えた読解。`fill_candidates` は import しない）。前の台本は `artifacts/w10-f04/fake_scripts.r2.jsonl`。
- **検査データ r3 の変更記録**: r2 の 103 行は id を変えず、(i) A1・A2・A3・OPEN・NONE と、開いた問いで決まる BACKEND 10 行は **そのまま**（期待も変えない。`p3_r2_vs_r3_unchanged_rows.txt` で r2 の出力と突き合わせて 53 行・差 0）。(ii) B 11 行・C 10 行は `call: gate_b|gate_c` を足して門の関数を直接呼ぶ行にした（期待は変えない。`r3: direct_call`）。(iii) 裁定 A で期待が変わる 29 行（ADOPT 15・D 11・A3R-01・**BACKEND-11/12**）は `gate_r2`・`expect_r2` に前の値を残し、`gate: A4` と (a4) の結果に変えた（`r3: expect_changed_by_ruling_A`。理由は oracle の分類から機械で決めた: `GATE_A_ROLE_SPLIT` 24・`GATE_A_HOLE_WORD_UNPLACED` 5）。**BACKEND-11/12 は指示書の表に無かった**（指示書は BACKEND を不変としたが、この 2 行は開いた問いが通った後の **閉じた問いの失敗** を見る行で、1 穴の文では閉じた問いに届かなくなる）。判断 J19 として記録し、同じ性質（閉じた問いの失敗の型）を 2 穴の文で保つ新しい行 `F-BACKEND-N01/02` を足した。(iv) 新しい行 65: {"A4U": 13, "A4S": 13, "ADOPT": 12, "BP": 11, "D": 10, "C": 4, "BACKEND": 2}。
- **J18**（実装中の判断）: 採用できる語が 1 つも残らないとき、決定の理由は、(a4) が落とした場合は **その理由（`GATE_A_HOLE_WORD_UNPLACED`／`GATE_A_ROLE_SPLIT`）**、語の数に依らない（(a4) は穴の性質であって語の性質ではない）。それ以外は従来どおり（語が 1 つならその語の理由、2 つ以上なら `NO_CANDIDATE_PASSED`）。これが無いと、近い語を 2 つ返した穴の理由が `NO_CANDIDATE_PASSED` に埋もれる。
- **J19** BACKEND-11/12 の扱い（上）。**J20** 実装は `fill_candidates.py` だけ（`r3_untouched_sha.txt`）。(a4)・(b') は穴ごとに 1 回だけ計算する（候補の語に依存しないため）。
- 穴の語の配置の分類（`a4_survey.r3.txt` の末尾の Counter。検査データの全文と追加 1 文 `父が税務署に申告した。` の穴 96 個）: 
```
Counter({'UNDET': 71, 'UNPLACED': 13, 'SAME': 12})
```
  UNPLACED = 配置が型を与えない、SAME = すべての型が同じ 1 つの役割、UNDET = ある型で読めない（`TYPE_NOT_READ`）、SPLIT = 読めた型どうしで役割が違う（`ROLES_DIFFER`）。**SPLIT は 0 件**（読める型どうしで役割が違う例は検査データに無い）。`ROLES_DIFFER` の検査は、読解の関数を差し替えた単体テストだけ（`test_gate_a4_roles_that_differ_are_a_split_with_its_own_kind`）。**J16 の実測**: 採用しうる（SAME）穴は 12 個で、すべて 2 穴の文の `が` の穴。1 穴の文は SAME にならない（`a4_survey.r3.txt` の SAME 行はすべて 2 穴の文）。
- P3 fake 後段（`p3_fake.txt`、`p3_pytest.txt`）:
```
rows=168 mismatch=0 adopted=23 adopted_arms_all_testimony_fill_origin=True
rows_per_gate {'A4': 29, 'A1': 12, 'A2': 11, 'B': 11, 'C': 14, 'BACKEND': 12, 'OPEN': 6, 'NONE': 2, 'A3': 12, 'A4U': 13, 'A4S': 13, 'ADOPT': 12, 'BP': 11, 'D': 10}
outcomes {'A1/NOT_ADOPTED/GATE_A_NOT_PLACED': 8, 'A1/NOT_ADOPTED/GATE_A_TYPE_NOT_EXPECTED': 4, 'A2/NOT_ADOPTED/GATE_A_DECLARED_TYPE_MISMATCH': 11, 'A3/NOT_ADOPTED/GATE_A_DECLARED_TYPE_NOT_OF_HOLE_WORD': 12, 'A4/NOT_ADOPTED/GATE_A_HOLE_WORD_UNPLACED': 5, 'A4/NOT_ADOPTED/GATE_A_ROLE_SPLIT': 24, 'A4S/NOT_ADOPTED/GATE_A_ROLE_SPLIT': 13, 'A4U/NOT_ADOPTED/GATE_A_HOLE_WORD_UNPLACED': 13, 'ADOPT/ADOPTED/ADOPTED': 12, 'B/NOT_ADOPTED/GATE_B_REREAD_NOT_READABLE': 11, 'BACKEND/BACKEND_FAILED/BACKEND_FAILED': 12, 'BP/ADOPTED/ADOPTED': 11, 'C/NOT_ADOPTED/GATE_C_CONTRADICTS_RECORD': 14, 'D/NOT_ADOPTED/GATE_D_CHOICE_ABSTAINED': 3, 'D/NOT_ADOPTED/GATE_D_CHOICE_NOT_PASSING': 3, 'D/NOT_ADOPTED/GATE_D_TIE': 4, 'NONE/NOT_ADOPTED/NO_CANDIDATE_WORDS': 2, 'OPEN/NOT_ADOPTED/OPEN_DECLARATION_INVALID': 6}
rows_with_direct_call 21
pipeline_reached {'b_prime_failed': 0, 'b_failed': 0, 'c_failed': 7} (gate-log entries of the rows without a call)
adopted_all_b_prime_passed=True
tokyo_natsu=GATE_A_ROLE_SPLIT zeimusho_yoru=GATE_A_HOLE_WORD_UNPLACED taiin_heishi=GATE_A_ROLE_SPLIT
................................................................         [100%]
64 passed in 27.35s
```
  口の経路（`call` の無い行 147 行）で門が落とした件数（`p3_fake.json` から機械で数えた）: (b') 0、(b) 0、(c) 7（(c) は手で作った記録の行）。**(b') と (b) は口の経路では 0 件**（落ちる経路の検査は関数を直接呼ぶ単体テストと `call` の行だけ）。採用 23 行はすべて `b_prime: PASSED` と `a4_role` つき（`adopted_all_b_prime_passed=True`）。
- P4 本物の後段 qwen3.5:4b（`p4_real.txt`、目視の表 `p4_visual_review.md`。目視であり正解データではない。第 2 ラウンドは `r2_p4_real.txt`・`r2_p4_visual_review.md`）:
```
holes=32 sentences=30 adopted=0 not_adopted_by_reason={"GATE_A_NOT_PLACED": 19, "NO_CANDIDATE_WORDS": 9, "GATE_A_ROLE_SPLIT": 1, "GATE_A_TYPE_NOT_EXPECTED": 3} backend_failed=0
vera_ms p50=8.7 p95=59.5 total=539.0 | llm_ms p50=4510.4 p95=6337.4 total=148043.0
declared_type_vs_word {'True': 22, 'False': 7, 'None': 3}
r3 words_that_passed_a1_a3_and_failed_a4=1 (in 1 holes; a4 reasons {'GATE_A_ROLE_SPLIT': 1}; split_kind {'TYPE_NOT_READ': 1})
r3 words_by_first_failed_gate {'a1': 22, 'a4': 1} | holes_with_b_prime_failure=0
percentile: sorted(v)[min(n-1, int(n*p))] over the 32 holes (one value per hole; vera_ms excludes the time in the backend)
realize_status_of_passed_words {}
```
  採用 0 件（誤採用（目視）0 は、採用が無いので 0）。r2 の唯一の採用 `隊員→兵士` は (a4) で `GATE_A_ROLE_SPLIT`（`TYPE_NOT_READ`: 隊員 = [PERSON, QUANTITY]、QUANTITY は読めない）。
- P5 送信内容（`p5_sent_check.txt`、`p5_mask.txt`）:
```
rows=168 messages_checked=351 leaked_sentence=0 leaked_sentence_sha=0 leaked_other_arm=0
note: rows_with_direct_call=21 send nothing (their messages are 0); two_hole_rows=40, of which 40 sent the OTHER hole's word as a hole (J5: a hole's word is sent; `others` below = arms whose value is a string in partial.roles, so a hole is never counted as another arm)
...                                                                      [100%]
3 passed, 52 deselected in 0.93s
```
  数え方: `others` = 部分的な十字の腕のうち値が文字列のもの（穴は `{hole: i}` なので、もう一方の穴の語は他の腕と数えない）。もう一方の穴の語は穴として送られる（J5 の範囲）。呼び出し行（`call`）は後段へ何も送らない。検出器の確認（秘匿オフで流すと漏れが出る）: `p5_sent_check_unmasked_control.txt`。
- P6 台帳・後段の差し替え（`p6_pytest.txt`）: 33 passed in 0.81s
- P1: `p1_serve.txt` = P1_SERVE_SAME（`serve.after.jsonl` が `before/serve.jsonl` と cmp 一致）。`z1_cmp.txt` は全 12 case が same。入口 4,149 文（`p1_entry.txt`）は `semantic_read.py` を変えていないので取り直していない（`r3_untouched_sha.txt` の前後で `semantic_read.py` の sha は同じ）。
- P2: `p2_holes.txt` は第 1・2 ラウンドと同じ（`cmp p2_holes.json p2_holes.r1.json` 一致）。
```
rows=138 hole_expected=62 hole_got=62 wrong_hole=0 missed=0 types_outside_table=0 empty_types=0 status_mismatch=0 expected_types_differ_from_oracle=0
status_counts {'HOLES_FOUND': 62, 'NOT_A_FILLER_CAUSE': 52, 'HOLE_NOT_PROBE_READABLE': 14, 'LANG_NOT_SUPPORTED': 4, 'READ': 3, 'NO_PLACEMENT': 3}
```

- P9（`pytest_full.txt`、`pytest_failures.txt`、`pytest_new_failures.txt`）: 全体 `rc=1`、失敗 116 件（基線 114 件）。基線に無い失敗:
```
FAILED tests/bank_score/test_bs_end_to_end.py::test_s6_two_runs_agree_except_timing_and_recount_matches
FAILED tests/test_p4_abilities.py::test_speech_act_drafts_fill_new_roles_and_reread
```
  どちらもチケットが環境由来と列挙したもの（`test_s6_…`・`test_speech_act_drafts…`）。単独でも失敗する（実行して確認）。`tests/attack/w3a3/r6_48_queries.jsonl` は全体テストの副作用で書き換わったので `git checkout --` で戻した（`git status --short tests/attack/` は空）。許可パスの検査: 違反 0、`semantic_read.py`・`observe.py` の既存行の変更 0、触った製品ファイルは `fill_candidates.py` だけ（`r3_untouched_sha.txt` の前後の差は `fill_candidates.py` の 1 行）、`semantic_reader.py`・`llm_choice.py`・`basis_policy.py` の差分 0。
  注: 全体テストの要約行の経過時間（548.64s）は第 2 ラウンドと同じ値で、実際の経過（約 14 分）と合わない。時計を固定するテストが全体の実行に漏れている可能性があるが、原因は調べていない（基線の失敗集合には関係しない）。

#### 6.6 の既知の穴（隠さない）
- **採用は 2 穴の文の、K95 で読める語の穴だけになった**（J16）。1 穴の文は採用 0。P4（本物の後段）は採用 0（r2 は 1）。裁定の帰結で、候補補完の効く範囲は狭い。広げる道（実現器の修理 A8、穴の語の型の決め方）は W10-f05 以降。
- 口の経路で (b') と (b) が落ちた件数は 0（`p3_fake.json`）。落ちる経路は関数を直接呼ぶ検査だけ。(c) は手で作った記録（`record_roles`）でだけ口の経路から検査している（r8 で読める本物の記録では 2 穴の文の記録が作れない: 指示書 0.4-4）。
- `GATE_A_ROLE_SPLIT` の `ROLES_DIFFER`（読める型どうしで役割が違う）は検査データに例が無く、読解の関数を差し替えた単体テストだけで確かめた。
- 検査データ r3 の期待は oracle（配置 r8 の答えと型を差し替えた読解）から機械で書いたもので、実装の (a4) と同じ読解の部品を使っている（`_HoleProbe`・`_hole_arm`）。独立した正解データではない。
- (a4) は穴ごとに |型| × 他の穴の型の直積 回の読解を足す（2 穴の文で P4 の Vera 側 p95 が 37.7 ms → 59.5 ms: `p4_real.txt` と `r2_p4_real.txt`。計測の負荷は同じでない）。
- J13（門 (c) はソブリンを見ない）は監査役の判断どおり残る。W10-f05 で足す。
- 台帳の昇格（`not_adopted` 行の語をどう `promotable` にするか）は W10-f05（J14）。
- P7（中間職の未公開の文）・P8（監査役）は実装役は測っていない。

#### テストの変更記録 r3（関数名・前後の全文。変えたのはここに書いた分だけ。他のテスト関数・定数は 1 文字も変えていない）

##### `tests/test_w10f04_fill.py::test_frozen_scripts_every_row_as_expected` (changed)
前:
```python
def test_frozen_scripts_every_row_as_expected(r8):
    got = collections.Counter()
    for r in rows():
        ho = S.read_with_holes(r['sentence'], placement=r8)
        idx = next(i for i, h in enumerate(ho['holes']) if (h['particle'], h['head']) == (r['hole']['particle'], r['hole']['head']))
        fb = LB.FakeBackend(r['steps'])
        recs = SimpleNamespace(crosses={'rec%d' % i: G.cross_of(s)[0] for i, s in enumerate(r['records'])}) if r['records'] else None
        n = [0]

        def ids():
            n[0] += 1
            return 'id%03d' % n[0]
        d = F.ask_and_gate(ho, text=r['sentence'], chat=lambda m, msgs, f, fb=fb: LB.chat('fake', m, msgs, f, fake=fb), model='fake-model', hole=idx, placement=r8,
                           choice_ledger=LC.ChoiceLedger(None), records=recs, id_source=ids, order_source=lambda m: list(range(m)))
        e = r['expect']
        assert (d.status, d.candidate) == (e['status'], e['word']), r['id']
        assert d.reason.startswith(e['reason']), (r['id'], d.reason)
        if d.status == 'ADOPTED':
            assert d.origin == 'testimony' and d.basis.startswith('LLM_TESTIMONY_FILL:fake-model:') and d.basis.endswith(d.choice_decision_id)
        got[r['gate']] += 1
    for gate in ('A1', 'A2', 'B', 'C', 'ADOPT'):
        assert got[gate] >= 10, gate
    assert got['D'] >= 10 and got['BACKEND'] >= 10
```
後:
```python
def test_frozen_scripts_every_row_as_expected(r8):
    got = collections.Counter()
    reasons = collections.Counter()
    q = S._placement_query(r8)
    for r in rows():
        ho = S.read_with_holes(r['sentence'], placement=r8)
        idx = next(i for i, h in enumerate(ho['holes']) if (h['particle'], h['head']) == (r['hole']['particle'], r['hole']['head']))
        e = r['expect']
        recs = SimpleNamespace(crosses={'rec%d' % i: (dict(G.cross_of(s)[0], roles=dict(r['record_roles'][i])) if r.get('record_roles') else G.cross_of(s)[0]) for i, s in enumerate(r['records'])}) if r['records'] else None
        if r.get('call'):            # r3: the gate itself is called (the pipeline does not reach it in a sentence of r8: docs section 6.6, J17)
            decl0 = json.loads(r['steps'][0]['raw'])
            word, wtype = decl0['near_words'][0], decl0['type']
            reason = F._gate_b(r['sentence'], ho, idx, word, wtype, q, None, {})[0] if r['call'] == 'gate_b' else F._gate_c(r['sentence'], ho, idx, word, q, recs, {})[0]
            assert e['status'] == 'NOT_ADOPTED' and reason and reason.startswith(e['reason']), (r['id'], reason)
            got[r['gate']] += 1
            reasons[(r['gate'], reason.split(':')[0])] += 1
            continue
        fb = LB.FakeBackend(r['steps'])
        n = [0]

        def ids():
            n[0] += 1
            return 'id%03d' % n[0]
        d = F.ask_and_gate(ho, text=r['sentence'], chat=lambda m, msgs, f, fb=fb: LB.chat('fake', m, msgs, f, fake=fb), model='fake-model', hole=idx, placement=r8,
                           choice_ledger=LC.ChoiceLedger(None), records=recs, id_source=ids, order_source=lambda m: list(range(m)))
        assert (d.status, d.candidate) == (e['status'], e['word']), r['id']
        assert d.reason.startswith(e['reason']), (r['id'], d.reason)
        if d.status == 'ADOPTED':
            assert d.origin == 'testimony' and d.basis.startswith('LLM_TESTIMONY_FILL:fake-model:') and d.basis.endswith(d.choice_decision_id)
            assert any(x['gate'] == 'passed' and x.get('b_prime') == 'PASSED' and x.get('a4_role') for x in d.gate_log), r['id']       # every adoption passed (a4) and (b')
        if e.get('split_kind'):
            assert [x['split_kind'] for x in d.gate_log if x['gate'] == 'a4'], r['id']
            assert all(x['split_kind'] == e['split_kind'] for x in d.gate_log if x['gate'] == 'a4'), r['id']
        if e.get('gate_log_passed'):
            (passed,) = [x for x in d.gate_log if x['gate'] == 'passed']
            assert all(passed.get(k) == v for k, v in e['gate_log_passed'].items()), r['id']
        got[r['gate']] += 1
        reasons[(r['gate'], d.reason.split(':')[0])] += 1
    for gate in ('A1', 'A2', 'A3', 'B', 'C', 'ADOPT', 'BP', 'D', 'BACKEND'):
        assert got[gate] >= 10, gate
    assert got['A4U'] >= 10 and got['A4S'] >= 10 and got['A4'] >= 10
    assert reasons[('A4U', 'GATE_A_HOLE_WORD_UNPLACED')] >= 10 and reasons[('A4S', 'GATE_A_ROLE_SPLIT')] >= 10
    # the label of a group and the reason of its rows correspond (round 3: a group cannot be satisfied by rows of another reason)
    want = {'A1': ('GATE_A_NOT_PLACED', 'GATE_A_TYPE_NOT_EXPECTED'), 'A2': ('GATE_A_DECLARED_TYPE_MISMATCH',), 'A3': ('GATE_A_DECLARED_TYPE_NOT_OF_HOLE_WORD',),
            'A4': ('GATE_A_HOLE_WORD_UNPLACED', 'GATE_A_ROLE_SPLIT'), 'A4U': ('GATE_A_HOLE_WORD_UNPLACED',), 'A4S': ('GATE_A_ROLE_SPLIT',), 'ADOPT': ('ADOPTED',), 'BP': ('ADOPTED',),
            'B': ('GATE_B_',), 'C': ('GATE_C_CONTRADICTS_RECORD',), 'D': ('GATE_D_',), 'BACKEND': ('BACKEND_FAILED',), 'OPEN': ('OPEN_DECLARATION_INVALID',), 'NONE': ('NO_CANDIDATE_WORDS',)}
    for (gate, reason), n_ in reasons.items():
        assert any(reason.startswith(w) for w in want[gate]), (gate, reason)
```

##### `tests/test_w10f04_fill.py::test_gate_order_records_the_first_gate_that_fails` (changed)
前:
```python
def test_gate_order_records_the_first_gate_that_fails():
    p = fake()
    d, _ = decide('母が図書館へ歩いた。', [op('PLACE', ['母', '駅'])], p)
    log = {x['word']: x for x in d.gate_log}
    assert log['母'] == dict(word='母', gate='a1', reason='GATE_A_TYPE_NOT_EXPECTED') and log['駅']['gate'] == 'passed'
    d, _ = decide('母が図書館へ歩いた。', [op('GROUP_ORG', ['駅'])], p)
    assert d.reason == 'GATE_A_DECLARED_TYPE_MISMATCH' and d.gate_log[0]['gate'] == 'a2'
```
後:
```python
def test_gate_order_records_the_first_gate_that_fails():
    p = fake_two_holes()
    d, _ = decide(SENT2, [op2(['駅', '犬'])], p, HOLE2)
    log = {x['word']: x for x in d.gate_log}
    assert log['駅'] == dict(word='駅', gate='a1', reason='GATE_A_TYPE_NOT_EXPECTED') and log['犬']['gate'] == 'passed' and log['犬']['a4_role'] == 'agent' and log['犬']['b_prime'] == 'PASSED'
    d, _ = decide(SENT2, [op2(['犬'], 'PERSON')], p, HOLE2)
    assert d.reason == 'GATE_A_DECLARED_TYPE_MISMATCH' and d.gate_log[0]['gate'] == 'a2'
```

##### `tests/test_w10f04_fill.py::test_a_tie_is_an_abstention_whatever_the_order` (changed)
前:
```python
def test_a_tie_is_an_abstention_whatever_the_order():
    p = FakePlacement(dict(fake().answers, **{'公園': decided('PLACE')}))
    for words in (['駅', '公園'], ['公園', '駅']):
        d, fb = decide('母が図書館へ歩いた。', [op('PLACE', words)], p)
        assert (d.status, d.reason, d.candidate) == ('NOT_ADOPTED', 'GATE_D_TIE', None)
        assert fb.calls == 1          # the closed ask is never made: there is no winner to confirm
```
後:
```python
def test_a_tie_is_an_abstention_whatever_the_order():
    p = fake_two_holes()
    for words in (['犬', '猫'], ['猫', '犬']):
        d, fb = decide(SENT2, [op2(words)], p, HOLE2)
        assert (d.status, d.reason, d.candidate) == ('NOT_ADOPTED', 'GATE_D_TIE', None)
        assert fb.calls == 1          # the closed ask is never made: there is no winner to confirm
```

##### `tests/test_w10f04_fill.py::test_near_words_order_does_not_change_the_decision` (changed)
前:
```python
def test_near_words_order_does_not_change_the_decision():
    p = FakePlacement(dict(fake().answers, **{'公園': decided('PLACE')}))
    outs = []
    for words in (['駅', '母'], ['母', '駅']):
        d, _ = decide('母が図書館へ歩いた。', [op('PLACE', words), {'pick': '駅'}, {'pick': '駅'}], p)
        outs.append((d.status, d.reason, d.candidate))
    assert outs[0] == outs[1] == ('ADOPTED', 'ADOPTED', '駅')
```
後:
```python
def test_near_words_order_does_not_change_the_decision():
    p = fake_two_holes()
    outs = []
    for words in (['犬', '駅'], ['駅', '犬']):
        d, _ = decide(SENT2, [op2(words), {'pick': '犬'}, {'pick': '犬'}], p, HOLE2)
        outs.append((d.status, d.reason, d.candidate))
    assert outs[0] == outs[1] == ('ADOPTED', 'ADOPTED', '犬')
```

##### `tests/test_w10f04_fill.py::test_candidate_is_testimony_never_a_record` (changed)
前:
```python
def test_candidate_is_testimony_never_a_record():
    d, _ = decide('母が図書館へ歩いた。', [op('PLACE', ['駅']), {'pick': '駅'}, {'pick': '駅'}], fake())
    assert d.status == 'ADOPTED' and d.origin == 'testimony' and d.basis.startswith('LLM_TESTIMONY_FILL:')
    assert d.provenance == {'backend': 'fake', 'model': 'fake-model', 'version': ''}
```
後:
```python
def test_candidate_is_testimony_never_a_record():
    d, _ = decide(SENT2, [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}], fake_two_holes(), HOLE2)
    assert d.status == 'ADOPTED' and d.origin == 'testimony' and d.basis.startswith('LLM_TESTIMONY_FILL:')
    assert d.provenance == {'backend': 'fake', 'model': 'fake-model', 'version': ''}
```

##### `tests/test_w10f04_fill.py::test_backend_failures_are_typed_and_are_not_no_candidate` (changed)
前:
```python
@pytest.mark.parametrize('kind', ['TIMEOUT', 'CONNECT_FAILED', 'HTTP_ERROR', 'BAD_RESPONSE', 'SCRIPT_EXHAUSTED'])
def test_backend_failures_are_typed_and_are_not_no_candidate(kind):
    d, _ = decide('母が図書館へ歩いた。', [{'fail': kind}], fake())
    assert (d.status, d.reason) == ('BACKEND_FAILED', 'BACKEND_FAILED:' + kind) and d.candidate is None
    d, _ = decide('母が図書館へ歩いた。', [op('PLACE', ['駅']), {'fail': kind}], fake())            # the closed ask fails
    assert d.status == 'BACKEND_FAILED' and d.reason == 'BACKEND_FAILED:' + kind
    assert d.reason != 'NO_CANDIDATE_WORDS'
```
後:
```python
@pytest.mark.parametrize('kind', ['TIMEOUT', 'CONNECT_FAILED', 'HTTP_ERROR', 'BAD_RESPONSE', 'SCRIPT_EXHAUSTED'])
def test_backend_failures_are_typed_and_are_not_no_candidate(kind):
    d, _ = decide('母が図書館へ歩いた。', [{'fail': kind}], fake())
    assert (d.status, d.reason) == ('BACKEND_FAILED', 'BACKEND_FAILED:' + kind) and d.candidate is None
    d, _ = decide(SENT2, [op2(['犬']), {'fail': kind}], fake_two_holes(), HOLE2)            # the closed ask fails (r3: in a two-hole sentence; a one-hole sentence never reaches it)
    assert d.status == 'BACKEND_FAILED' and d.reason == 'BACKEND_FAILED:' + kind
    assert d.reason != 'NO_CANDIDATE_WORDS'
```

##### `tests/test_w10f04_fill.py::test_a_contradicting_record_stops_the_candidate` (changed)
前:
```python
def test_a_contradicting_record_stops_the_candidate(r8):
    recs = SimpleNamespace(crosses={'rec0': G.cross_of('母が駅へ歩かなかった。')[0]})
    d, _ = decide('母が図書館へ歩いた。', [op('PLACE', ['駅']), {'pick': '駅'}, {'pick': '駅'}], r8, records=recs)
    assert d.reason == 'GATE_C_CONTRADICTS_RECORD:rec0' and d.records_checked == 1
    d, _ = decide('母が図書館へ歩いた。', [op('PLACE', ['駅']), {'pick': '駅'}, {'pick': '駅'}], r8,
                  records=SimpleNamespace(crosses={'rec0': G.cross_of('兄が山へ歩かなかった。')[0]}))
    assert d.status == 'ADOPTED' and d.records_checked == 1
```
後:
```python
def test_a_contradicting_record_stops_the_candidate(r8):
    steps = [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}]
    recs = record_of('母が駅へ走らなかった。', {'agent': '犬', 'goal': '図書館'})            # the same arms, the opposite polarity
    d, _ = decide('ウサギが図書館へ走った。', steps, r8, HOLE2, records=recs)
    assert d.reason == 'GATE_C_CONTRADICTS_RECORD:rec0' and d.records_checked == 1
    d, _ = decide('ウサギが図書館へ走った。', steps, r8, HOLE2, records=record_of('母が駅へ走らなかった。', {'agent': '兄', 'goal': '図書館'}))
    assert d.status == 'ADOPTED' and d.records_checked == 1
```

##### `tests/test_w10f04_fill.py::test_the_gate_b_reread_rejects_a_slot_the_reader_does_not_read` (changed)
前:
```python
def test_the_gate_b_reread_rejects_a_slot_the_reader_does_not_read(r8):
    d, _ = decide('兄が窓口で名乗った。', [op('PLACE', ['玄関'], 'place')], r8, hole=('で', '窓口'))
    assert d.reason == 'GATE_B_REREAD_NOT_READABLE'
```
後:
```python
def test_the_gate_b_reread_rejects_a_slot_the_reader_does_not_read(r8):
    ho = S.read_with_holes('兄が窓口で名乗った。', placement=r8)            # r3: the gate itself (a one-hole sentence is stopped by (a4) before it)
    assert F._gate_b('兄が窓口で名乗った。', ho, 0, '玄関', 'PLACE', S._placement_query(r8), None, {})[0] == 'GATE_B_REREAD_NOT_READABLE'
```

##### `tests/test_w10f04_fill.py::test_realize_is_recorded_and_can_be_required` (changed)
前:
```python
def test_realize_is_recorded_and_can_be_required(r8):
    steps = [op('PLACE', ['駅']), {'pick': '駅'}, {'pick': '駅'}]
    d, _ = decide('母が図書館へ歩いた。', steps, r8)
    assert d.status == 'ADOPTED' and d.gate_log[0]['realize'] == 'REFUSED'         # J10: the realizer cannot read back a typed goal cross
    ho = S.read_with_holes('母が図書館へ歩いた。', placement=r8)
    fb = LB.FakeBackend(steps)
    d = F.ask_and_gate(ho, text='母が図書館へ歩いた。', chat=lambda m, msgs, f: LB.chat('fake', m, msgs, f, fake=fb), model='m', placement=r8, choice_ledger=LC.ChoiceLedger(None), require_realize=True,
                       order_source=lambda n: list(range(n)))
    assert d.status == 'NOT_ADOPTED' and d.reason == 'GATE_B_REALIZE_REFUSED'
```
後:
```python
def test_realize_is_recorded_and_can_be_required(r8):
    q = S._placement_query(r8)
    ho = S.read_with_holes('母が図書館へ歩いた。', placement=r8)            # r3: the gate itself, on a one-hole sentence (the realizer step exists only there)
    assert F._gate_b('母が図書館へ歩いた。', ho, 0, '駅', 'PLACE', q, r8, {}) == (None, 'REFUSED')         # J10: the realizer cannot read back a typed goal cross
    assert F._gate_b('母が図書館へ歩いた。', ho, 0, '駅', 'PLACE', q, r8, {}, True) == ('GATE_B_REALIZE_REFUSED', 'REFUSED')
    d, _ = decide('ウサギが図書館へ走った。', [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}], r8, HOLE2)
    assert d.status == 'ADOPTED' and d.gate_log[0]['realize'] == 'SKIPPED_OTHER_HOLES'                       # in a two-hole sentence the step is skipped, and the record says so
```

##### `tests/test_w10f04_fill.py::test_the_backend_name_does_not_change_the_decision` (changed)
前:
```python
def test_the_backend_name_does_not_change_the_decision():
    runs = []
    for name in ('ollama', 'openai', 'fake'):
        out = []
        for sent, steps, hole in [('母が図書館へ歩いた。', [op('PLACE', ['駅']), {'pick': '駅'}, {'pick': '駅'}], ('へ', '図書館')),
                                  ('母が図書館へ歩いた。', [op('PLACE', ['母', '駅'])] + [{'pick': None}], ('へ', '図書館')),
                                  ('母が図書館へ歩いた。', [{'fail': 'TIMEOUT'}], ('へ', '図書館'))]:
            d, _ = decide(sent, steps, fake(), hole, name=name)
            out.append((d.status, d.reason, d.candidate, d.gate_log, d.declaration))
        runs.append(out)
    assert runs[0] == runs[1] == runs[2]
```
後:
```python
def test_the_backend_name_does_not_change_the_decision():
    runs = []
    for name in ('ollama', 'openai', 'fake'):
        out = []
        for sent, steps, hole in [(SENT2, [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}], HOLE2),
                                  (SENT2, [op2(['駅', '犬'])] + [{'pick': None}], HOLE2),
                                  ('母が図書館へ歩いた。', [op('PLACE', ['駅'])], ('へ', '図書館')),            # r3: a one-hole sentence, refused by (a4)
                                  (SENT2, [{'fail': 'TIMEOUT'}], HOLE2)]:
            d, _ = decide(sent, steps, fake_two_holes(), hole, name=name)
            out.append((d.status, d.reason, d.candidate, d.gate_log, d.declaration))
        runs.append(out)
    assert runs[0] == runs[1] == runs[2]
```

##### `tests/test_w10f04_fill.py::test_mask_the_sentence_and_the_other_arms_do_not_leave` (changed)
前:
```python
def test_mask_the_sentence_and_the_other_arms_do_not_leave():
    sentence = '母が図書館へ歩いた。'
    d, fb = decide(sentence, [op('PLACE', ['駅']), {'pick': '駅'}, {'pick': '駅'}], fake())
    blob = sent_text(fb)
    assert d.mask_user_text is True and len(fb.sent) == 3
    for leaked in (sentence, sentence.rstrip('。'), hashlib.sha256(sentence.encode()).hexdigest(), '母'):
        assert leaked not in blob, leaked
    assert '図書館' in blob and '歩く' in blob and '〈PERSON〉' in blob and F.CROSS_TOKENS_VERSION in blob      # the hole's word, the predicate and the coordinates are sent
```
後:
```python
def test_mask_the_sentence_and_the_other_arms_do_not_leave():
    sentence = '母が図書館へ歩いた。'            # r3: a one-hole sentence (the open ask only: (a4) refuses it); a non-hole arm (母) exists only here
    d, fb = decide(sentence, [op('PLACE', ['駅'])], fake())
    blob = sent_text(fb)
    assert d.mask_user_text is True and len(fb.sent) == 1 and d.reason == 'GATE_A_ROLE_SPLIT'
    for leaked in (sentence, sentence.rstrip('。'), hashlib.sha256(sentence.encode()).hexdigest(), '母'):
        assert leaked not in blob, leaked
    assert '図書館' in blob and '歩く' in blob and '〈PERSON〉' in blob and F.CROSS_TOKENS_VERSION in blob      # the hole's word, the predicate and the coordinates are sent
    sentence = SENT2                           # r3: the whole flow (the open ask and the two closed asks) of an adoption
    d, fb = decide(sentence, [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}], fake_two_holes(), HOLE2)
    blob = sent_text(fb)
    assert d.status == 'ADOPTED' and len(fb.sent) == 3
    for leaked in (sentence, sentence.rstrip('。'), hashlib.sha256(sentence.encode()).hexdigest()):
        assert leaked not in blob, leaked
    assert 'ウサギ' in blob and '図書館' in blob and '歩く' in blob and F.CROSS_TOKENS_VERSION in blob          # the hole's word, the other hole's word (a hole: J5), the predicate, the coordinates
```

##### `tests/test_w10f04_fill.py::test_mask_off_sends_the_sentence_and_the_detector_sees_it` (changed)
前:
```python
def test_mask_off_sends_the_sentence_and_the_detector_sees_it():
    sentence = '母が図書館へ歩いた。'
    d, fb = decide(sentence, [op('PLACE', ['駅']), {'pick': '駅'}, {'pick': '駅'}], fake(), mask=False)
    assert d.mask_user_text is False and sentence in sent_text(fb) and '母' in sent_text(fb)
```
後:
```python
def test_mask_off_sends_the_sentence_and_the_detector_sees_it():
    sentence = '母が図書館へ歩いた。'
    d, fb = decide(sentence, [op('PLACE', ['駅']), {'pick': '駅'}, {'pick': '駅'}], fake(), mask=False)
    assert d.mask_user_text is False and sentence in sent_text(fb) and '母' in sent_text(fb)
    d, fb = decide(SENT2, [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}], fake_two_holes(), HOLE2, mask=False)            # r3: added: the whole flow of an adoption, unmasked
    assert d.status == 'ADOPTED' and SENT2 in sent_text(fb)
```

##### `tests/test_w10f04_fill.py::test_mask_the_ledgers_do_not_keep_the_sentence` (changed)
前:
```python
def test_mask_the_ledgers_do_not_keep_the_sentence(tmp_path):
    sentence = '母が図書館へ歩いた。'
    led = TestimonyLedger(tmp_path / 't.jsonl')
    ho = S.read_with_holes(sentence, placement=fake())
    fb = LB.FakeBackend([op('PLACE', ['駅']), {'pick': '駅'}, {'pick': '駅'}])
    choice = LC.ChoiceLedger(tmp_path / 'c.jsonl')
    d = F.ask_and_gate(ho, text=sentence, chat=lambda m, msgs, f: LB.chat('fake', m, msgs, f, fake=fb), model='m', placement=fake(), ledger=led, choice_ledger=choice,
                       order_source=lambda n: list(range(n)))
    assert d.status == 'ADOPTED'
    for f in (tmp_path / 't.jsonl', tmp_path / 'c.jsonl'):
        text = f.read_text(encoding='utf-8')
        assert sentence not in text and hashlib.sha256(sentence.encode()).hexdigest() not in text.replace(d.context['sentence_sha256'], '') and '"母"' not in text
    assert d.context['sentence_sha256'] in (tmp_path / 't.jsonl').read_text(encoding='utf-8')     # the sha is what the ledger keeps
```
後:
```python
def test_mask_the_ledgers_do_not_keep_the_sentence(tmp_path):
    sentence = SENT2
    led = TestimonyLedger(tmp_path / 't.jsonl')
    ho = S.read_with_holes(sentence, placement=fake_two_holes())
    fb = LB.FakeBackend([op2(['犬']), {'pick': '犬'}, {'pick': '犬'}])
    choice = LC.ChoiceLedger(tmp_path / 'c.jsonl')
    d = F.ask_and_gate(ho, text=sentence, chat=lambda m, msgs, f: LB.chat('fake', m, msgs, f, fake=fb), model='m', placement=fake_two_holes(), ledger=led, choice_ledger=choice, hole=0,
                       order_source=lambda n: list(range(n)))
    assert d.status == 'ADOPTED'
    for f in (tmp_path / 't.jsonl', tmp_path / 'c.jsonl'):
        text = f.read_text(encoding='utf-8')
        assert sentence not in text and hashlib.sha256(sentence.encode()).hexdigest() not in text.replace(d.context['sentence_sha256'], '')
    assert d.context['sentence_sha256'] in (tmp_path / 't.jsonl').read_text(encoding='utf-8')     # the sha is what the ledger keeps
    one = '母が図書館へ歩いた。'            # r3: a one-hole sentence that is not adopted is on the ledger too (J14), with no non-hole arm of the user's
    led2 = TestimonyLedger(tmp_path / 't2.jsonl')
    ho = S.read_with_holes(one, placement=fake())
    d = F.ask_and_gate(ho, text=one, chat=lambda m, msgs, f: LB.chat('fake', m, msgs, f, fake=LB.FakeBackend([op('PLACE', ['駅'])])), model='m', placement=fake(), ledger=led2,
                       choice_ledger=LC.ChoiceLedger(None))
    assert d.status == 'NOT_ADOPTED' and d.reason == 'GATE_A_ROLE_SPLIT'
    text = (tmp_path / 't2.jsonl').read_text(encoding='utf-8')
    assert one not in text and hashlib.sha256(one.encode()).hexdigest() not in text.replace(d.context['sentence_sha256'], '') and '"母"' not in text and '"not_adopted"' in text
```

##### `tests/test_w10f04_fill.py::test_gate_a3_lets_a_declaration_through_when_the_word_has_that_type_and_when_the_placement_has_no_type_for_it` (removed)
前:
```python
def test_gate_a3_lets_a_declaration_through_when_the_word_has_that_type_and_when_the_placement_has_no_type_for_it(r8):
    d, _ = _p4_shape(r8, '妹が東京に旅行した。', ('に', '東京'), 'time', 'TIME', '夏')              # r8: 東京 [PLACE, TIME]: the residual risk, kept in the frozen data (F-A3R-01)
    assert d.status == 'ADOPTED'
    d, _ = decide('母が図書館へ歩いた。', [op('PLACE', ['駅']), {'pick': '駅'}, {'pick': '駅'}], FakePlacementWithUnplaced())   # no type for the hole word: nothing to compare, the earlier gates decide
    assert d.status == 'ADOPTED'
```

##### `tests/test_w10f04_fill.py::FakePlacementWithUnplaced` (removed)
前:
```python
def FakePlacementWithUnplaced():
    p = fake()
    p.answers = dict(p.answers)
    p.answers.pop('図書館')
    p.answers['図書館'] = {'state': 'UNPLACED', 'top': [], 'origin': None, 'estimate_basis': None, 'constructed': False}
    return p
```

##### `tests/test_w10f04_fill.py::op2` (added)
後:
```python
def op2(words, type_='ANIMAL'):
    return op(type_, words, 'agent')
```

##### `tests/test_w10f04_fill.py::record_of` (added)
後:
```python
def record_of(sentence, roles):
    """A record cross made by hand: a readable sentence of the same predicate and polarity, with the arms replaced (no reader types the hole word in a record)."""
    return SimpleNamespace(crosses={'rec0': dict(G.cross_of(sentence)[0], roles=dict(roles))})
```

##### `tests/test_w10f04_fill.py::test_gate_a4_refuses_a_hole_word_the_placement_has_no_type_for` (added)
後:
```python
def test_gate_a4_refuses_a_hole_word_the_placement_has_no_type_for(r8, tmp_path):
    led = TestimonyLedger(tmp_path / 'z.jsonl')
    d, fb = decide('父が税務署に申告した。', [op('TIME', ['夜'], 'time'), {'pick': '夜'}, {'pick': '夜'}], r8, hole=('に', '税務署'), ledger=led)
    assert (d.status, d.reason, d.candidate) == ('NOT_ADOPTED', 'GATE_A_HOLE_WORD_UNPLACED', None) and fb.calls == 1        # the closed ask is never made
    row = d.gate_log[0]
    assert row['gate'] == 'a4' and row['word'] == '夜' and row['hole_word_types'] == [] and row['hole_word_state'] in ('UNPLACED', 'UNKNOWN') and row['role_by_type'] == {} and 'split_kind' not in row
    rows = [r for r in led.entries() if r['type'] == 'not_adopted']                    # J14: the declaration and the candidate stay on the ledger as testimony
    assert len(rows) == 1 and rows[0]['word'] == '税務署' and rows[0]['declaration']['near_words'] == ['夜'] and rows[0]['gate_log'][0]['gate'] == 'a4'
    d, _ = decide('母が荷物を後へ押した。', [op('INFO_LANGUAGE', ['本'], 'patient'), {'pick': '本'}, {'pick': '本'}], r8, hole=('を', '荷物'))
    assert d.reason == 'GATE_A_HOLE_WORD_UNPLACED'
```

##### `tests/test_w10f04_fill.py::test_gate_a4_refuses_when_the_types_of_the_hole_word_do_not_fall_in_one_role` (added)
後:
```python
def test_gate_a4_refuses_when_the_types_of_the_hole_word_do_not_fall_in_one_role(r8):
    d, fb = decide('妹が東京に旅行した。', [op('TIME', ['夏'], 'time'), {'pick': '夏'}, {'pick': '夏'}], r8, hole=('に', '東京'))            # 東京 [PLACE, TIME]: PLACE is not read, TIME reads `time`
    assert (d.status, d.reason, d.candidate) == ('NOT_ADOPTED', 'GATE_A_ROLE_SPLIT', None) and fb.calls == 1
    row = d.gate_log[0]
    assert row['gate'] == 'a4' and row['split_kind'] == 'TYPE_NOT_READ' and row['role_by_type'] == {'PLACE': None, 'TIME': 'time'} and row['hole_word_types'] == ['PLACE', 'TIME']
    d, _ = decide('隊員が港へ走った。', [op('PERSON', ['兵士'], 'agent'), {'pick': '兵士'}, {'pick': '兵士'}], r8, hole=('が', '隊員'))     # the adoption of P4 r2: 隊員 [PERSON, QUANTITY]
    assert d.reason == 'GATE_A_ROLE_SPLIT' and d.gate_log[0]['split_kind'] == 'TYPE_NOT_READ' and d.gate_log[0]['role_by_type']['QUANTITY'] is None
```

##### `tests/test_w10f04_fill.py::test_gate_a4_lets_through_a_hole_whose_types_all_read_the_same_role` (added)
後:
```python
def test_gate_a4_lets_through_a_hole_whose_types_all_read_the_same_role(r8):
    d, fb = decide('ウサギが図書館へ走った。', [op2(['犬']), {'pick': '犬'}, {'pick': '犬'}], r8, HOLE2)
    assert (d.status, d.reason, d.candidate) == ('ADOPTED', 'ADOPTED', '犬') and fb.calls == 3
    (passed,) = [x for x in d.gate_log if x['gate'] == 'passed']
    assert passed['a4_role'] == 'agent' and passed['b_prime'] == 'PASSED' and d.origin == 'testimony'
    d, _ = decide('ウサギが図書館へ走った。', [op('PLACE', ['駅'], 'goal'), {'pick': '駅'}, {'pick': '駅'}], r8, hole=('へ', '図書館'))      # the other hole of the same sentence: GROUP_ORG is not read
    assert d.reason == 'GATE_A_ROLE_SPLIT'
```

##### `tests/test_w10f04_fill.py::test_gate_a4_counts_a_type_that_is_not_read_as_a_split_and_the_reason_does_not_depend_on_the_number_of_words` (added)
後:
```python
def test_gate_a4_counts_a_type_that_is_not_read_as_a_split_and_the_reason_does_not_depend_on_the_number_of_words(r8):
    d, _ = decide('妹が東京に旅行した。', [op('TIME', ['夏', '夜'], 'time')], r8, hole=('に', '東京'))
    assert d.reason == 'GATE_A_ROLE_SPLIT' and [x['gate'] for x in d.gate_log] == ['a4', 'a4']          # J18: two words, the hole's reason
    d, _ = decide('父が税務署に申告した。', [op('TIME', ['夜', '駅'], 'time')], r8, hole=('に', '税務署'))
    assert d.reason == 'GATE_A_HOLE_WORD_UNPLACED' and [x['gate'] for x in d.gate_log] == ['a4', 'a1']      # a word that fails earlier never reaches (a4)
```

##### `tests/test_w10f04_fill.py::test_gate_a4_roles_that_differ_are_a_split_with_its_own_kind` (added)
後:
```python
def test_gate_a4_roles_that_differ_are_a_split_with_its_own_kind():
    class Roles:                            # a hole word whose two types are both read, as two different roles: the reader is replaced by a stub of `_HoleProbe`'s reading
        pass
    p = fake_two_holes()
    ho = S.read_with_holes(SENT2, placement=p)
    import verantyx.semantic_read as SR
    real_arm = SR._hole_arm
    try:
        SR._hole_arm = lambda clause, term, t: ('agent' if t == 'ANIMAL' else 'patient') if term == 'ウサギ' else real_arm(clause, term, t)
        a = F._gate_a4(SENT2, ho, 0, p, {})
    finally:
        SR._hole_arm = real_arm
    assert a['ok'] is False and a['reason'] == 'GATE_A_ROLE_SPLIT' and a['split_kind'] == 'ROLES_DIFFER' and a['role_by_type'] == {'ANIMAL': 'agent', 'PERSON': 'patient'}
```

##### `tests/test_w10f04_fill.py::_b_prime_inputs` (added)
後:
```python
def _b_prime_inputs(r8, text='ウサギが図書館へ走った。', hi=0):
    q = S._placement_query(r8)
    ho = S.read_with_holes(text, placement=r8)
    return q, ho, F._gate_a4(text, ho, hi, q, {})
```

##### `tests/test_w10f04_fill.py::test_gate_b_prime_passes_when_the_injected_reread_comes_back_to_the_same_cross` (added)
後:
```python
def test_gate_b_prime_passes_when_the_injected_reread_comes_back_to_the_same_cross(r8):
    q, ho, a4 = _b_prime_inputs(r8)
    assert a4['ok'] and F._gate_b_prime('ウサギが図書館へ走った。', ho, 0, 'ANIMAL', a4['role'], q, {}) == (None, None)
    assert F._gate_b_prime('ウサギが図書館へ走った。', ho, 0, 'PERSON', a4['role'], q, {}) == (None, None)
```

##### `tests/test_w10f04_fill.py::test_gate_b_prime_refuses_an_arm_with_another_role` (added)
後:
```python
def test_gate_b_prime_refuses_an_arm_with_another_role(r8):
    q, ho, a4 = _b_prime_inputs(r8)
    assert F._gate_b_prime('ウサギが図書館へ走った。', ho, 0, 'ANIMAL', 'patient', q, {}) == ('GATE_B_REREAD_MISMATCH', 'ARM_ROLE_DIFFERS')
```

##### `tests/test_w10f04_fill.py::test_gate_b_prime_refuses_a_centre_that_differs_from_the_partial` (added)
後:
```python
def test_gate_b_prime_refuses_a_centre_that_differs_from_the_partial(r8):
    import copy
    q, ho, a4 = _b_prime_inputs(r8)
    other = copy.deepcopy(ho)
    key = next(k for k, v in other['partial'].items() if k not in ('roles', 'role_basis') and isinstance(v, str))
    other['partial'][key] = other['partial'][key] + 'X'
    assert F._gate_b_prime('ウサギが図書館へ走った。', other, 0, 'ANIMAL', a4['role'], q, {}) == ('GATE_B_REREAD_MISMATCH', 'CENTER_DIFFERS')
```

##### `tests/test_w10f04_fill.py::test_gate_b_prime_refuses_an_arm_that_is_not_a_hole_and_differs` (added)
後:
```python
def test_gate_b_prime_refuses_an_arm_that_is_not_a_hole_and_differs(r8):
    import copy
    q = S._placement_query(r8)
    text = '母がウサギを図書館へ押した。'
    ho = S.read_with_holes(text, placement=r8)             # a non-hole arm (母) beside the hole 図書館
    a4 = F._gate_a4(text, ho, 0, q, {})
    assert ho['holes'][0]['head'] == '図書館' and F._gate_b_prime(text, ho, 0, 'PLACE', 'goal', q, {}) == (None, None)
    other = copy.deepcopy(ho)
    other['partial']['roles']['agent'] = '父'
    assert F._gate_b_prime(text, other, 0, 'PLACE', 'goal', q, {}) == ('GATE_B_REREAD_MISMATCH', 'OTHER_ARMS_DIFFER')
    other = copy.deepcopy(ho)
    other['partial']['role_basis']['agent'] = 'something-else'
    assert F._gate_b_prime(text, other, 0, 'PLACE', 'goal', q, {}) == ('GATE_B_REREAD_MISMATCH', 'OTHER_ARMS_DIFFER')
```

##### `tests/test_w10f04_fill.py::test_gate_b_prime_refuses_a_type_the_reader_does_not_read` (added)
後:
```python
def test_gate_b_prime_refuses_a_type_the_reader_does_not_read(r8):
    q = S._placement_query(r8)
    ho = S.read_with_holes('隊員が港へ走った。', placement=r8)
    assert ho['holes'][0]['head'] == '隊員' and F._gate_b_prime('隊員が港へ走った。', ho, 0, 'QUANTITY', 'agent', q, {}) == ('GATE_B_REREAD_MISMATCH', 'NOT_READABLE')
```

##### `tests/test_w10f04_fill.py::test_every_adoption_passed_b_prime` (added)
後:
```python
def test_every_adoption_passed_b_prime(r8):
    n = 0
    for r in rows():
        if r['expect']['status'] != 'ADOPTED' or r.get('call'):
            continue
        d, _ = decide(r['sentence'], [dict(st) for st in r['steps']], r8, (r['hole']['particle'], r['hole']['head']))
        assert d.status == 'ADOPTED' and sum(1 for x in d.gate_log if x['gate'] == 'passed') == 1
        (passed,) = [x for x in d.gate_log if x['gate'] == 'passed']
        assert passed['b_prime'] == 'PASSED' and passed['a4_role'] and not [x for x in d.gate_log if x['gate'] == 'b_prime']
        n += 1
    assert n >= 20
```

##### `tests/test_w10f04_ledger.py::test_the_backend_name_does_not_change_the_ledger_decisions` (changed)
前:
```python
def test_the_backend_name_does_not_change_the_ledger_decisions(tmp_path):
    cols = []
    for i, name in enumerate(('ollama', 'fake')):
        led = TestimonyLedger(tmp_path / ('n%d.jsonl' % i), promote_n=3)
        ho = S.read_with_holes('母が図書館へ歩いた。', placement=fake())
        fb = LB.FakeBackend([{'raw': json.dumps({'type': 'PLACE', 'role': 'goal', 'near_words': ['駅']}, ensure_ascii=False)}, {'pick': '駅'}, {'pick': '駅'}])
        F.ask_and_gate(ho, text='母が図書館へ歩いた。', chat=lambda m, msgs, f: LB.chat('fake', m, msgs, f, fake=fb), model='m', backend_name=name, placement=fake(), ledger=led,
                       order_source=lambda n: list(range(n)), choice_ledger=LC.ChoiceLedger(None))
        cols.append([(r['type'], r.get('status'), r.get('reason'), r.get('candidate'), r.get('gate_log')) for r in led.entries() if r['type'] != 'header'])
    assert cols[0] == cols[1] and cols[0][0][0] == 'testimony'
```
後:
```python
def test_the_backend_name_does_not_change_the_ledger_decisions(tmp_path):
    cols = []
    for i, name in enumerate(('ollama', 'fake')):
        led = TestimonyLedger(tmp_path / ('n%d.jsonl' % i), promote_n=3)
        ho = S.read_with_holes('ウサギが図書館へ歩いた。', placement=fake_two_holes())            # r3: a two-hole sentence (a one-hole sentence is never adopted: J16)
        fb = LB.FakeBackend([{'raw': json.dumps({'type': 'ANIMAL', 'role': 'agent', 'near_words': ['犬']}, ensure_ascii=False)}, {'pick': '犬'}, {'pick': '犬'}])
        F.ask_and_gate(ho, text='ウサギが図書館へ歩いた。', chat=lambda m, msgs, f: LB.chat('fake', m, msgs, f, fake=fb), model='m', backend_name=name, placement=fake_two_holes(), ledger=led,
                       order_source=lambda n: list(range(n)), choice_ledger=LC.ChoiceLedger(None), hole=0)
        cols.append([(r['type'], r.get('status'), r.get('reason'), r.get('candidate'), r.get('gate_log')) for r in led.entries() if r['type'] != 'header'])
    assert cols[0] == cols[1] and cols[0][0][0] == 'testimony' and cols[0][0][2] == 'ADOPTED'
```

##### `tests/test_w10f04_serve.py::DOC` (changed)
前:
```python
DOC = '母が部屋で本を読んだ。\n母が図書館へ歩いた。\n兄が窓口で名乗った。\n'
```
後:
```python
DOC = '母が部屋で本を読んだ。\nウサギが図書館へ走った。\nエリートが銀行へ歩いた。\n'            # r3: two sentences of two holes each (a one-hole sentence is never adopted: J16)
```

##### `tests/test_w10f04_serve.py::smart_fill_chat` (changed)
前:
```python
def smart_fill_chat(calls):
    """The candidate backend: an open ask is answered by the hole's word (図書館 -> 駅, 窓口 -> 公園), a closed ask picks the first candidate shown."""
    nearest = {'図書館': ('PLACE', 'goal', '駅'), '窓口': ('PLACE', 'place', '公園'), '役所': ('PLACE', 'goal', '港')}

    def chat(model, messages, fmt):
        prompt = '\n'.join(m['content'] for m in messages)
        calls.append(prompt)
        if fmt and fmt.get('properties', {}).get('near_words') is not None:
            m = re.search(r'「([^」]+)」。\n述語', prompt)
            head = m.group(1) if m else None
            t, role, word = nearest.get(head, ('PLACE', None, None))
            return {'ok': True, 'content': json.dumps({'type': t, 'role': role, 'near_words': [word] if word else []}, ensure_ascii=False), 'error': None, 'usage': {}}
        first = re.search(r'^0: (\{.*\})$', prompt, re.M)
        return {'ok': True, 'content': json.dumps({'choice': 0 if first else None}), 'error': None, 'usage': {}}
    return chat
```
後:
```python
def smart_fill_chat(calls):
    """The candidate backend: an open ask is answered by the hole's word (ウサギ -> 犬, エリート -> 兄, 図書館 -> 駅, 銀行 -> 港), a closed ask picks the first candidate shown."""
    nearest = {'図書館': ('PLACE', 'goal', '駅'), '窓口': ('PLACE', 'place', '公園'), '役所': ('PLACE', 'goal', '港'), 'ウサギ': ('ANIMAL', 'agent', '犬'), 'エリート': ('PERSON', 'agent', '兄'), 'カラス': ('ANIMAL', 'agent', '猫'),
               '銀行': ('PLACE', 'goal', '港')}

    def chat(model, messages, fmt):
        prompt = '\n'.join(m['content'] for m in messages)
        calls.append(prompt)
        if fmt and fmt.get('properties', {}).get('near_words') is not None:
            m = re.search(r'「([^」]+)」。\n述語', prompt)
            head = m.group(1) if m else None
            t, role, word = nearest.get(head, ('PLACE', None, None))
            return {'ok': True, 'content': json.dumps({'type': t, 'role': role, 'near_words': [word] if word else []}, ensure_ascii=False), 'error': None, 'usage': {}}
        first = re.search(r'^0: (\{.*\})$', prompt, re.M)
        return {'ok': True, 'content': json.dumps({'choice': 0 if first else None}), 'error': None, 'usage': {}}
    return chat
```

##### `tests/test_w10f04_serve.py::test_fill_adds_holes_ledger_ids_and_a_testimony_fill_arm_and_changes_nothing_else` (changed)
前:
```python
def test_fill_adds_holes_ledger_ids_and_a_testimony_fill_arm_and_changes_nothing_else(tmp_path):
    reply = '弟が役所へ走った。'            # not a sentence of the documents (a verbatim record sentence is a record)
    base = turn(cfg_of(tmp_path, FakeLLM(reply)))
    calls = []
    cfg = cfg_of(tmp_path, FakeLLM(reply), fill=fill_of(tmp_path, calls, max_doc_holes=0))
    res = turn(cfg)
    assert 'holes' in res['vera'] and 'ledger_ids' in res['vera'] and set(res['vera']) - set(base['vera']) == {'holes', 'ledger_ids'}
    assert res['content'] == base['content'] and res['vera']['outcome'] == base['vera']['outcome']          # K283: the candidate mouth only annotates
    item = res['vera']['provenance'][0]
    arm = item['arms']['goal']
    assert arm['kind'] == 'testimony_fill' and arm['surface'] == '港' and arm['origin'] == 'testimony' and arm['basis'].startswith('LLM_TESTIMONY_FILL:fill-model:')
    assert item['sentence_kind'] != 'record' and item['read'] is False and res['vera']['ledger_ids'] and arm['ledger_id'] in res['vera']['ledger_ids']
    assert 'fill_llm_ms' in res['vera']['timing']
    assert res['vera']['outcome']['outcome'] == 'TESTIMONY'         # an answer from the model is never ANSWER_HUMAN_BASIS
```
後:
```python
def test_fill_adds_holes_ledger_ids_and_a_testimony_fill_arm_and_changes_nothing_else(tmp_path):
    reply = 'カラスが本部へ走った。'            # not a sentence of the documents (a verbatim record sentence is a record); two holes: が:カラス is adoptable, へ:本部 is not (r3)
    base = turn(cfg_of(tmp_path, FakeLLM(reply)))
    calls = []
    cfg = cfg_of(tmp_path, FakeLLM(reply), fill=fill_of(tmp_path, calls, max_doc_holes=0))
    res = turn(cfg)
    assert 'holes' in res['vera'] and 'ledger_ids' in res['vera'] and set(res['vera']) - set(base['vera']) == {'holes', 'ledger_ids'}
    assert res['content'] == base['content'] and res['vera']['outcome'] == base['vera']['outcome']          # K283: the candidate mouth only annotates
    item = res['vera']['provenance'][0]
    arm = item['arms']['agent']
    assert arm['kind'] == 'testimony_fill' and arm['surface'] == '猫' and arm['origin'] == 'testimony' and arm['basis'].startswith('LLM_TESTIMONY_FILL:fill-model:')
    assert item['sentence_kind'] != 'record' and item['read'] is False and res['vera']['ledger_ids'] and arm['ledger_id'] in res['vera']['ledger_ids']
    assert 'fill_llm_ms' in res['vera']['timing']
    assert res['vera']['outcome']['outcome'] == 'TESTIMONY'         # an answer from the model is never ANSWER_HUMAN_BASIS
```

##### `tests/test_w10f04_serve.py::test_the_documents_get_the_mouth_but_the_record_is_not_written` (changed)
前:
```python
def test_the_documents_get_the_mouth_but_the_record_is_not_written(tmp_path):
    plain = cfg_of(tmp_path, FakeLLM(''))
    calls = []
    fill = fill_of(tmp_path, calls)
    cfg = cfg_of(tmp_path, FakeLLM(''), fill=fill)
    assert cfg.records.records == plain.records.records and cfg.records.crosses == plain.records.crosses and cfg.records.cross_reason == plain.records.cross_reason     # (8)
    assert cfg.fill_stats['holes_asked'] == 2 and cfg.fill_stats['adopted'] == 2 and cfg.fill_stats['skipped_holes'] == 0
    rows = fill.ledger.entries()
    assert [r['type'] for r in rows].count('testimony') == 2
    assert all(r['context']['doc_id'] for r in rows if r['type'] == 'testimony')
    assert (Path(tmp_path) / 'd.txt').read_text(encoding='utf-8') == DOC
```
後:
```python
def test_the_documents_get_the_mouth_but_the_record_is_not_written(tmp_path):
    plain = cfg_of(tmp_path, FakeLLM(''))
    calls = []
    fill = fill_of(tmp_path, calls)
    cfg = cfg_of(tmp_path, FakeLLM(''), fill=fill)
    assert cfg.records.records == plain.records.records and cfg.records.crosses == plain.records.crosses and cfg.records.cross_reason == plain.records.cross_reason     # (8)
    assert cfg.fill_stats['holes_asked'] == 4 and cfg.fill_stats['adopted'] == 2 and cfg.fill_stats['skipped_holes'] == 0       # r3: 2 sentences x 2 holes; the が hole is adopted, the へ hole is refused by (a4)
    rows = fill.ledger.entries()
    assert [r['type'] for r in rows].count('testimony') == 2 and [r['type'] for r in rows].count('not_adopted') == 2         # the refused へ holes are on the ledger too (J14)
    assert all(r['context']['doc_id'] for r in rows if r['type'] == 'testimony')
    assert (Path(tmp_path) / 'd.txt').read_text(encoding='utf-8') == DOC
```

##### `tests/test_w10f04_serve.py::test_the_document_hole_budget_counts_what_it_skips` (changed)
前:
```python
def test_the_document_hole_budget_counts_what_it_skips(tmp_path):
    calls = []
    cfg = cfg_of(tmp_path, FakeLLM(''), fill=fill_of(tmp_path, calls, max_doc_holes=1))
    assert cfg.fill_stats['holes_asked'] == 1 and cfg.fill_stats['skipped_holes'] == 1
```
後:
```python
def test_the_document_hole_budget_counts_what_it_skips(tmp_path):
    calls = []
    cfg = cfg_of(tmp_path, FakeLLM(''), fill=fill_of(tmp_path, calls, max_doc_holes=1))
    assert cfg.fill_stats['holes_asked'] == 1 and cfg.fill_stats['skipped_holes'] == 3
```


## J10（W3-d1 で閉じた）

W10-f04 の J10（門 (b) の実現 → 再読が、実現器が型つきの十字を拒み、再読を配置なしで行い、主題を は で書くため、候補を埋めた文に課せなかった）を W3-d1 で閉じた。上の J10 の記述（歴史として残す）は書き換えていない。

- 実現器は渡された配置で自分の文を読み直し（`semantic_realize._reread_check`、K312）、主題の助詞を表（`verantyx/data/realize_forms_ja.json` の `topic_particles`）の順に試して、**出す文そのもの** が再読一致と語の系譜の検査を通った最初の候補を出す（K315）。`cross_tokens.realize_tokens(..., placement=)` は配置を実現器に渡す。仕様は `docs/REALIZE.md`。
- `fill_candidates._gate_b` の呼び出しは変えていない（docstring だけ更新）。既定 `require_realize=False` も変えていない。オンにするかは監査役の判断。
- 実測（`artifacts/w3-d1/`）: `母が図書館へ歩いた。` ＋ `駅`/PLACE は `(None,'REALIZED')`（以前は `REFUSED`）。W10-f04 の台本と同じ型の表（`tests/test_w3d1_gate_b.py`）で、通る行 7・実現の段で落ちる行 6（`t4_pytest.txt`）。
- 期待の変更が要るテスト 1 件（`tests/test_w10f04_fill.py::test_realize_is_recorded_and_can_be_required`、197・198 行）は編集していない。旧い期待・新しい期待・実測は `artifacts/w3-d1/j10_expectation_change.md`。

## 7. W10-f05: 文書駆動の配置（口 O3・J13）（事前登録）

詳細な規則・設計は `docs/COARSE_PLACEMENT.md` §12.19（K290〜K297・J1〜J16）。ここでは入口と口の約束だけを事前登録する。

- **O3（台帳から層へ）**: `vera ledger promote --layer <name> --ledger-file L [--placement 基底] [--promote-n N]`。`promotable` の行を層へ。人の確認 → `layer_human`（direct）、再読一致だけ → `layer_estimated`（direct にしない・K291）、基底が DECIDED → `SKIP_BASE_DECIDED`、同じ (key, 層, origin) → `SKIP_ALREADY_PROMOTED`。層への書き込みは 1 件ごとに台帳へ `promoted_to_layer` 行（K294）。`vera ledger confirm`（人が呼ぶ CLI）が `layer_human` の唯一の入口。
- **文書駆動の育成**: `vera placement grow --documents f… --layer <name> --backend ollama|openai|fake --ledger-file L [--placement 基底]`。`vera placement growth --layer <name> [--ledger-file L] [--list]` が育ちの指標（§7: 層の語数・台帳の行数・昇格数・最後に育った時刻・`chain_ok`）。既存の `vera placement <store>`（面の配置のシミュレーション）は変えない（先頭の引数が `grow`／`growth` のときだけ新しい口）。
- **入口**: `vera read/ask/serve/chat --layer`（`VERA_PLACEMENT_LAYER`）。`vera serve` の `vera` 欄は、層を指定したとき（`--layer`、または環境変数 `VERA_PLACEMENT_LAYER` だけでもよい。どちらも無い・空なら鍵なし）だけ最後に `placement_layer = {name, status, growth: {words_direct, words_human, words_estimated, last_grown}}` を足す。既存の `vera.layer`（融合の層 0/1）は変えない。
- **門 (c) のソブリン（J13）**: `VERA_SOVEREIGN_*` が設定されているとき、門 (c) は文書の記録に加えて、`ACTIVE_CONSENTED` のソブリンの発話（十字にできたもの）とも矛盾を比べる。矛盾 → `GATE_C_CONTRADICTS_SOVEREIGN:<event_id>`。`sovereign_checked` は実際に 1 件以上比べたときだけ True。同意なし・設定なし・比べた数 0 は False。設定なしでは `gate_log` に鍵を足さない。


## 8. W3-e2: 仮定つきの読み（docs/READING_SOUNDNESS.md §10L）
- `vera serve`（`fusion_turn`）は LLM の返答の文を再読するとき、既定で段 E2（`--strict-read`／`VERA_READ_MODE=strict` で厳格）を使う。仮定の語が入った腕は `vera.provenance[].arms[*]` の `kind: 'assumed'`（`evidence: []`、鍵は `surface`・`kind`・`evidence` のまま）。その文には鍵 `assumptions` が付く。仮定のある文は十字の一致で `record` にならず（逐語の一致は従来どおり）、事実の問いの `ANSWER` の根拠にならない。記録（文書）の文は常に strict で読む。
- `vera placement growth --layer L --ledger-file F`: 台帳に `assumption` 行があるとき、最後の鍵 `assumption: {rows, words, promoted_words, assumption_rate}`（`assumption_rate` = 仮定した語のうち、この層への `promoted_to_layer` 行が無い語の割合）。
- `vera serve` の `--strict-read` は文法の層 1 の `--strict` とは別物。
- 第 3 ラウンド: 出所 `surface` の仮定は強い名前の形（固有名詞・未知語・見出し語が表層のひらがな）だけ、P2 の が は型のある（動物・集団・人）充填物だけ、表層の仮定は台帳で再読の一致だけでは `promotable` にならない（`blocked_by: SURFACE_ASSUMPTION`）。詳細は READING_SOUNDNESS.md §10L.6。
