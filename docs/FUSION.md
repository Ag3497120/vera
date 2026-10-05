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
   - `factual`: `doc_answer.answer`（`vera ask --mode round5`・`vera chat --mode round5` と同じ 1 つの関数。W16-t2）を呼ぶ。round5 の本読み（`one.Vera.ask`）→ 止まったときだけ質問の十字の後段。文書 0 本は `NO_RECORD`。
     本読みが ANSWER のとき（door `semantic_document`）の写し方は閉じている: `answer_values` がちょうど 1 組 `[role, value]`、`values == [value]`、`sources` の各文が文書の文にちょうど 1 つ（同じ文書）で当たる → `QUESTION_CROSS`（`state=FILLED`、`reason` は door、`hole_role=role`、`filler=value`、`sources` は 4 鍵）。それ以外（諾否・複数の値・出所が文に 1 つに当たらない）は `STRUCTURE_UNDETERMINED`（`state=ROUND5_ANSWER_NOT_MAPPED`、`reason` に型つきの理由）。同点・疑いは棄権。
     配置が使えないとき（未設定・開けない）も経路は同じ（W16-t2 第 2 ラウンド、監査役の裁定 5。配置の有無で 2 本目の経路を持たない）: 本読みが答える問いは配置なしでも記録が答える。後段だけで答える問い（型つきの穴を要る）は配置が無いと `NO_TYPED_CANDIDATE`。問いの形（`か`・`ましたか`・`？`の有無）は round5 の質問の読み（`question.read_semantic`）が吸収する。serve 側に表層の一致の規則は持たない。
     数: `artifacts/w16-t2/t2_compare_r2.txt`（配置なしは `t2_compare_noplace_r2.txt`）、serve が答えを見せずに棄権した行は `artifacts/w16-t2/t2_1_serve_withheld_r2.tsv`（第 1 ラウンドの `t2_compare.txt`・`t2_1_serve_withheld.tsv` は残してある）。
   - 非 factual: 質問の十字は使わない。記録 = 渡された文書の文（`doc_answer.records` と同じ切り方）。
3. 層 1 のみ: 文法を作る（§1.4）。作れなければ LLM を呼ばず型で返す。
4. LLM を呼ぶ（Ollama `/api/chat`、`think: false`、`stream: false`、`temperature: 0`。層 1 は `format` に JSON schema）。層 0 で記録が答えを持つとき（`QUESTION_CROSS`）は **呼ばない**（記録が答えなので。判断記録 D10）。
5. 検証（§1.5）: 本文を文に分け、各文を再読し、腕ごとに出所の型を付ける。
6. 根拠の方針（`basis_policy.apply_to_ask`）を掛け、本文と `vera` 欄を組む（§1.6）。

### 1.3 読解の型（閉じた一覧）

| `vera.reading.type` | 条件 | 層 0 の LLM | 層 1 の LLM |
|---|---|---|---|
| `QUESTION_CROSS` | factual で `doc_answer.answer` が ANSWER（door `question_cross`、または door `semantic_document` で上の写し方を満たす） | 呼ばない（記録が答え） | 呼ぶ（文法つき） |
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
- **D8** `--placement DIR` は起動時に `VERA_PLACEMENT` を設定するだけ。配置が無ければ factual は `NO_RECORD`（`NO_TYPED_CANDIDATE`）になる（正しい振る舞い）。 W16-t2（2026-10-06）: 配置なしでも round5 の本読みが答える問いは記録が答える。後段だけで答える問いは従来どおり `NO_TYPED_CANDIDATE`（元の文は歴史として残す）。
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
- 読解器が読めない問いは、記録に答えがあっても答えにならない（層 0 は LLM の証言、層 1 は `STRUCTURE_UNDETERMINED`）。検査データでは ONE 50 問のうち層 0 で 21 問、層 1 で 18 問だけが記録の答えになった（`score_layer*.txt`）。到達は読解器の到達で決まる。配置が無いと事実の問いは答えにならない（`NO_TYPED_CANDIDATE`）。（W16-t2 の後: 本読みが答える問いは配置なしでも答える。この一文は後段だけで答える問いについて残る。）
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


## 9. W16-t3: 層 0 の引用照合（K650–K653）（事前登録 2026-10-05 23:12:37 +0900）

チケット W16-t3（T3）。層 0 の事実の問いで、文書を LLM に渡し、`{answer, quotes[]}` の JSON で答えさせ、Vera が **読解なしで** 引用の実在と答えの要素（数値・日付・固有名）の食い違いを照合する。LLM の答えは **証言のまま**（`MARK_TESTIMONY` を残し、`outcome` は `TESTIMONY`、`origin` は `testimony`）。この節の「事前登録」の小節は、検査データを作る前に書いた。

### 9.1 照合の規則（事前登録）

- **正規化 norm**: NFKC → 連続する空白を半角空白 1 つ → 前後の空白を除く。
- **行の本文**: 記録で `(source, line)` が同じ文を k の順に連結。前の文が「。」で終わるときは空文字、それ以外は半角空白 1 つ。
- **出典の一致**: 引用の `source` が記録の `source` と NFKC で完全一致、または `os.path.basename` が一致すれば同じ文書。
- **引用の実在**: (1) norm(text) が空 → `fabricated`。(2) 指定の `(source, line)` の行の本文に norm で部分一致 → `exact`。(3) 他の行（全文書）のどれかに部分一致 → `relocated`（一致した行が 2 つ以上でも `relocated`。全部を `relocated_to` に残し、勝者を選ばない）。(4) どこにも無い → `fabricated`。型の違う引用（list でない・dict でない・`source`/`text` が文字列でない・`line` が int でない（bool も不可））は落とさず `fabricated` にして数え、`reason: BAD_QUOTE_TYPE` を付ける。
- **答えの要素**（答えからだけ取る。重なる範囲は 日付・時刻 → 数値 → 固有名 の順で先に取ったものが持つ）:
  - 日付・時刻 `date`: アラビア数字・漢数字の `年 月 日 時 分`（1 組ごとに 1 要素。例 `2026年4月1日` は `2026年`・`4月`・`1日` の 3 要素。`午前`／`午後` が直前にあれば値に含める）と `[月火水木金土日]曜日`。相対語（明日・来週・翌日・前日）は取らない（チケットの「相対語は除く」。判断 J1: 年月日と曜日は取る）。
  - 数値 `number`: アラビア数字（`,` 区切り・小数）と、単位が直後に付く漢数字。**値は「数の値＋単位」の文字列**（`3万円` は `3万円`。30000 には直さない。漢数字は数の値に直す: `三百円` → `300円`）。読めない漢数字の並びは要素にせず `skipped` に数える。単位・漢数字の一覧は `answer_slots._VALUE`／`answer._NUMBER` から取り出し、新しく書かない。
  - 固有名 `name`: 形態素解析の品詞 `pos2 == 固有名詞` の語の連続、カタカナ 2 文字以上の連続、`さん`・`様` の直前の名詞の連続。重なるものは、開始が早く長いものを 1 つ。
- **要素の照合**: 答えの要素と同じ `(kind, value)` が、`exact`／`relocated` の引用から **同じ関数で取り出した** 要素にあれば、その引用の位置（`source:line`。relocated は全部）を `found_in` に入れる。文字列の部分一致ではない（`3` と `30` を取り違えない）。無ければ `found_in: null`。
- **食い違い** `conflicts`: (i) 答えの要素が `found_in: null` で、実在する引用に **同じ種類（数値・日付は同じ単位）** の要素が 1 つ以上ある → `{kind, answer_value, values: [{value, source, line}]}`。(ii) 実在する引用が 2 つ以上の文書から来て、同じ種類の要素の値の集合が文書間で違う → `{kind, answer_value: null, values}`（答えに出ているかは問わない）。
- **印**（答え全体に 1 つ。上から最初に当たったもの）: 1. 引用が 0 個、または `fabricated` が 1 つでもある → `unanchored`。2. `conflicts` が 1 つ以上 → `conflict`。3. `found_in: null` の要素が 1 つでもある → `unanchored`。4. それ以外 → `anchored`（要素 0 個でもここに来る。T3-1 で数を出す）。
- **返答が JSON として読めない／`answer` が文字列でない**: `quotes = []` として照合し、`reason` に `REPLY_NOT_JSON`／`ANSWER_NOT_A_STRING` → 規則 1 で `unanchored`。本文は LLM の返答（raw）のまま。
- `quote_check` の鍵: `verdict`・`quotes`・`elements`・`conflicts`（チケットのとおり）。足してよいのは `reason`（理由があるときだけ）。`quotes` の項目に `relocated_to` が付くことがある。

### 9.2 T3-1 の集合の作り方と測る量（事前登録）

- 答えあり 40 = W14 公開データ（`benchmarks/public_v1/data/questions.jsonl`）の `cat == "ANS"` の 40 問。答え無し 20 = `cat == "NONE"` を docset（S1〜S4）ごとに id 昇順で先頭 5 問。
- 各問に候補 1 つ。id 昇順で並べた中で偶数番目（0 始まり）を誤答にする（ANS 20・NONE 10、計 30）。
- 正しい候補: ANS は `answer = q.answer`、`quotes = [{source: evidence.doc, line: evidence.line, text: その行の全文}]`。NONE は `answer = "文書に記載がありません"`、`quotes = []`。
- 誤答（ANS、誤答の中で交互に）: W1 = `answer = distractors[0].value`、引用は正しい候補のまま。W2 = 同じ答えで、引用の text を「元の行の `q.answer` を `distractors[0].value` に置き換えたもの」にした（捏造の引用）。
- 誤答（NONE、交互に）: 同じ docset の ANS を id 昇順に並べ、同じ順位の問いの `distractors[0]` を借りる。N1 = `answer = その value`、`quotes = [{distractor の doc・line・その行の全文}]`（実在する、関連の無い行を引いた形）。N2 = 同じ答えで、`quotes` の text を「問いの文末の「。」の前に value を入れた文」にした（捏造）。
- 文書は docset の全ファイル。記録は `G.load_records` で読む。
- **測る量**: 検出率 = 誤答の候補のうち印が `anchored` 以外になった数 ÷ 誤答の候補の数。(a) LLM 自身の引用を信じる = 「引用が 1 つ以上あれば正しいとみなす」。(a) の検出 = 誤答の候補のうち引用が 0 個のもの。(b) = Vera の照合。誤検出率 = 正しい ANS の候補（20）のうち印が `anchored` 以外になった数 ÷ 20。NONE の正しい候補（引用なしの「文書に記載がありません」）は印の分布だけを別に出し、誤検出の分母に入れない。誤答の型（W1/W2/N1/N2）ごとの検出率、要素 0 個で `anchored` になった候補の数も出す。
- 予想・目標値は書かない。上乗せ（(b) − (a)）が 0 ならそう報告する。

### 9.3 実装した仕様（本文の 1 行と鍵）

- **quote_mode**（`decode_grammar.quote_mode`）: 層 0・FACTUAL・LLM を呼ぶ・記録が答えない・文書が 1 つ以上読み込まれている。偽の経路（層 1・非 factual・文書なし・LLM を呼ばない・記録が答える）は基点と byte 一致（K653）。
- **K650**: `llm_messages` は quote_mode のとき、クライアントの会話の先頭に system を 1 つ足す（`[文書名:行番号] 行の本文`。同じ行の文は 1 行にまとめる）。`vera_server.fusion_turn` が `fmt = G.quote_format(turn, records)`（`G.QUOTE_SCHEMA`）を LLM に渡す。Ollama は `format`、OpenAI 互換は `response_format`（strict）。
- **K651**: `verantyx/quote_check.py: check(answer, quotes, records) -> QuoteCheck`（§9.1 の規則）。
- **K652**: `vera.quote_check = {verdict, quotes[{source,line,text,found,(relocated_to)}], elements[{kind,value,found_in}], conflicts[...], (reason)}`。`outcome` の直後・`timing` の前（`conclude` の最後の鍵）。本文は `MARK_TESTIMONY + "\n" + answer` の後に 1 行: 錨あり `（引用の出典: <source>:<line>、…）`／錨なし `（記録で確かめられません）`／食い違い `（記録と食い違います: <source>:<line>「<値>」／…）`。固定文（`LLM_EMPTY` など）には足さない。錨ありのとき、`provenance` の記録でない文に `anchored_testimony: {quotes: [source:line, …]}` を足す（`origin`・`sentence_kind`・`arms`・`evidence` は変えない。`abstain_policy` を呼んだ後に足す）。`outcome` は `TESTIMONY` のまま。
- LLM の答えは証言のまま。錨ありでも事実の問いの ANSWER の根拠は引用（人の記録）であり、LLM の文ではない。「読んだ」「正しい」とは書かない。

### 9.4 判断の記録

- **J1** 「日付・時刻（年月日・曜日・相対語は除く）」は「年月日と曜日は取る、相対語は取らない」と読む。
- **J2** `anchored_testimony` は記録でない文の項目に足す鍵。`origin` の値は増やさない（`basis_policy.DECLARED_ORIGINS` は閉じた一覧で許可パスの外）。
- **J3** `MARK_TESTIMONY` は錨ありでも残す。
- **J4** format を LLM に渡すために `vera_server.fusion_turn` の 1 行を変えた（`fmt = ... else G.quote_format(turn, cfg.records)`）。チケットの「追記だけ」を 1 行越える。K650 を満たす唯一の箇所。
- **J5** 既存試験との衝突は書き換えず、§9.7 に旧・新案の全文を残して監査役に渡す。
- **J6** 複数行に一致する引用は `relocated` にして全部を残す（勝者を選ばない）。
- **実装役の判断 I1** 日付は 1 組（数＋年／月／日／時／分）ごとに 1 要素にした（`2026年4月1日` → `2026年`・`4月`・`1日`）。答えが「4月1日」だけでも、引用の「2026年4月1日」と照合できる。
- **I2** 数値の値は「数の値＋単位」の文字列（`3万円` は `3万円`。30000 に直さない）。漢数字は数の値に直す。読めない並びは要素にせず `QuoteCheck.skipped` に数える（`to_dict` には入れない。鍵を足さないため）。
- **I3** 形態素解析は `typed_edges._tagger`（fugashi）を直接使う（`semantic_reader` は import しない。指示書のレビュー項目の grep を空にするため）。
- **I4** (ii) 文書間の食い違いは、名前にも適用する（チケットの文どおり）。2 文書から引用した答えは、名前の集合が違えばほぼ必ず `conflict` になる。これは既知の穴（§9.8）。
- **I5** quote_mode でも、LLM の返答が空（`answer` が空文字）で `LLM_EMPTY` になったときは `quote_check` の鍵を作らない（固定文の経路）。
- **I6** format を渡すと Ollama は `num_predict` を送らない（`llm_backend._ollama_chat`。許可パスの外）。W14 の `max_tokens=256` は quote_mode では効かない。
- **I7** 事前登録の文より前に `verantyx/quote_check.py` の初版を書いていた（規則は指示書のとおりで、事前登録の文と同じ）。検査データ（T3-1 の集合）は事前登録（`artifacts/w16-t3/prereg_time.txt`）より後に作り、凍結した（`data_freeze_time.txt`）。関係試験の基線は、最初の取得が実装中の木と重なったため、基点 `3a1677c` の `git archive` の写しで取り直した（`related_before.txt`）。
- **I8**（レビュー第 1 ラウンド M1）形態素解析（`typed_edges._tagger`）が使えないとき、固有名（品詞・「さん／様」）が答えからも引用からも取れず、答えの要素が 0 個になって `anchored` に落ちていた。型を付けて棄権に倒す: `reason = "NAME_TAGGER_UNAVAILABLE"`、印は `unanchored`（固有名を照合できないので「すべて引用に現れる」を確かめられない）。`_names` は `(固有名, 解析が使えたか)` を返し、`check` が印を決める。`extract` の返り値は変えない。なお答えが文字列でないとき（`ANSWER_NOT_A_STRING`）も `unanchored` にした（関数の契約。§9.1 の事前登録の文は書き換えていない）。
- **J-R3-1（第 3 ラウンド）被覆の対象は引用の text** であり、行全体ではない。裁定は「引用（指定の行）」。行全体を使うと、引用に入れなかった語まで被覆されて緩む。text は指定の行の中の逐語なので行より狭い。要素の照合も既に text からなので一貫する。
- **J-R3-2** 内容語に形状詞・接頭辞・名詞的な接尾辞を含める。裁定は「名詞・動詞・形容詞」だが、unidic では学校文法の形容動詞が形状詞、`大会議室` の `大` や `申請書` の `書` が接頭辞・接尾辞になる。含めないと普通名詞の取り違え（裁定の型）を見逃す。含めるのは狭める方向。
- **J-R3-3** `llm_backend.py`（元の許可パスの外）の 2 つの if だけ変えた: `fmt` が `decode_grammar.QUOTE_SCHEMA` と同一のオブジェクトのとき、`format`／`response_format` に加えて `num_predict`／`max_tokens` を送る（裁定 3）。文法の経路（別の dict）の送信は変わらない。format を落とす箇所はここだけ。
- **J-R3-4** 基名が同じ別ファイルは同じ文書として扱う。記録の `source` は basename で、`cli._qc_records`（T2 の範囲・未修正）が基名の同じ別ファイルの 2 つ目の本文を `where.setdefault` で失う。(ii) は立たない（狭める）側に倒れる。`line_bodies` は同じ id の記録を 1 度だけ連結する（これまで 2 度連結していた）。
- **J-R3-5** `question=None` は何も除外しない（厳しい側）。serve の経路は必ず問いを渡す（`_attach_quote_check` の引数に足した）。
- **J-R3-6** 答えが文字列でないときの `unanchored` は `reason` の文字列比較ではなく局所の真偽値で決める（第 2 ラウンドのレビューの任意改善 2）。形態素解析の呼び出しと品詞・見出し語の読み出しは同じ try の中（同改善 3）。
- **J-R4-1（第 4 ラウンド。撤回）** 応答の語を含まない答え（`そうです。`）を `NO_CONTENT_TO_CHECK` で `unanchored` にする案は、既存の試験 `test_no_elements_with_a_real_quote_is_anchored`（答え `そうです` → `anchored`）と衝突したので撤回した（§9.13b）。3c は応答の語（感動詞・`違う`）を含む答えだけ。
- **J-R4-2** `tests/test_w10f05_cli.py` 154 行目を dev `a7507b3` の行に戻した（§9.7 の末尾。T2 の merge で記録が答える経路になり、`quote_check` が作られないため。`git diff a7507b3 -- tests/test_w10f05_cli.py` は空）。
- **J-R4-3** `違う`（動詞）を応答の語に入れた。裁定の文（はい・いいえ・ええ・違う 等）の名指しどおりで、他の語は足していない。
- **J-R4-4** 3c に当たる答えでは、3b の未被覆が `違う` だけのとき理由は `YESNO_NOT_CHECKED` を優先する（verdict は同じ）。
- **J-R4-5** 3c・3d の判定に使う解析は、答えの全文（`_analyze(answer)`）と各実在引用の text。問いは、選択の問いかどうかの判定（R11）と、3c の条件 (c)（内容語が問いの語の繰り返しかどうか。R3 の `_covered(wd, qtoks)`。選択の問いでは `qtoks` は空。§9.13c）に使う。第 5 ラウンドからは R12（K654。問いの語の繰り返しを除いた残りが空かどうか。§9.16）にも使う。
- **J-R5-1（第 5 ラウンド。裁定 3 との衝突）** 裁定 2 は R28（そうです。）・E07／G13（はい、支払います。）の型を閉じることを求め、裁定 3 は「ほかの既存の試験の期待は変えない」と定める。第 4 ラウンドの凍結データの O-02（`cases_r4b.jsonl`、`そうです。` → `anchored`）と YC-02（`cases_r4c.jsonl`、`はい、社内の人が務めます。` → `anchored`）はこの 2 つの型を既知の穴として `anchored` と書いたもので、K654 を入れると必ず赤になる。裁定 2 の目的を優先し、期待を強める側（anchored → unanchored）だけ替えた。凍結済みのファイルは書き換えていない: O-02 は `tests/test_w16t3_r4.py` の読み先を `cases_r4.jsonl`（最初に凍結した版。O-02 の期待は `unanchored`／`NO_CONTENT_TO_CHECK`）に戻し、YC-02 は `r5/cases_r4c_r5.jsonl`（YC-02 の `expect`・`expect_reason_prefix`・`note` だけ替えた写し。他の 10 件は byte 一致）を読む。**監査役への申し送り: この 2 件の期待を替えたことの確認をお願いする。**
- **J-R5-2** `そう（です）` は 3c の応答の語に入れない（§9.16）。
- **J-R5-3** `その通りです。` は `通り` が名詞（普通名詞）で内容語 1 個なので 3b に落ちる（§9.16、H-03）。
- **J-R5-4** `非自立可能` の述語だけの答え（`できません。`）は内容語 0 個で、正しい答えでも `NO_CONTENT_TO_CHECK`（F-01。偽の錨なし）。
- **J-R5-5** R2（名詞と動詞の表層一致）は変えない。閉じない型は §9.8 に開示（H-01・H-02）。

### 9.5 測定結果（出力ファイルから機械で貼った）

#### T3-1（自作の集合。T3-4 の伏せた集合が本番）— `artifacts/w16-t3/t31_result.txt`・`t31_serve_path.txt`

```
T3-1（自作の集合。通っても証拠にならない。T3-4 の伏せた集合が本番）
(a) LLM 自身の引用を信じる: 検出 0/30 = 0.0%
(b) Vera の照合:            検出 19/30 = 63.3%
上乗せ (b)-(a): 19 件（+63.3 点）
誤検出（正しい ANS 20 のうち anchored 以外）: 0/20 = 0.0%
型ごとの検出（a / b）:
  W1 n=10  a=0  b=4  印={'conflict': 4, 'anchored': 6}
  W2 n=10  a=0  b=10  印={'unanchored': 10}
  N1 n=5  a=0  b=0  印={'anchored': 5}
  N2 n=5  a=0  b=5  印={'unanchored': 5}
NONE の正しい候補 10 の印の分布: {'unanchored': 10}（誤検出の分母に入れない）
要素 0 個で anchored: 全 60 件のうち 11、誤答のうち 6
取り出せなかった漢数字の並び（skipped）: 0
誤答なのに anchored（見逃し）: 11 = 要素 0 個 6（N1 1, W1 5） ＋ 要素あり 5（N1 4, W1 1）
  要素あり・見逃し: S1-NONE-01   N1  要素=[('name', '久保田澄子', ['D1_bihin_kitei.txt:5'])]
  要素あり・見逃し: S2-NONE-04   N1  要素=[('name', '山根卓哉', ['D2_shiryo_tejun.txt:45'])]
  要素あり・見逃し: S3-ANS-09    W1  要素=[('name', '緑川', ['D3_gijiroku.txt:46'])]
  要素あり・見逃し: S3-NONE-03   N1  要素=[('name', '森下裕美', ['D3_gijiroku.txt:6'])]
  要素あり・見逃し: S4-NONE-02   N1  要素=[('name', '戸田健司', ['D4_shiyou_v2.txt:25'])]
```

```
serve の経路（FusionConfig + 偽の LLM）に 60 候補を通した: 同じ 60、違う 0、LLM を呼ばなかった（記録が答えた）0
```

#### T3-2（実機 qwen3.5:4b、温度 0、W14 の C 系）— `artifacts/w16-t3/t32_result.txt`

```
T3-2: W14 の C 系（Vera 既定、qwen3.5:4b、温度 0）。run1 = /Users/motonisihikoudai/Projects/vera-impl/wt/W14-bench-S/artifacts/w14-bench/run1/C/results.jsonl、今回 = /Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S/artifacts/w16-t3/w14/C/results.jsonl
行数: run1 256、今回 256

旧の物差し（score.vera_verified_sources の合計。reading.sources と provenance の evidence）を同じスクリプトで再計算:
  run1: 出所の数の合計 0、1 つ以上ある行 0 / 256
  今回: 出所の数の合計 0、1 つ以上ある行 0 / 256

今回の行のうち vera.quote_check がある行: 255 / 256（0 なら W14 の木を測っている）
印の分布（行）: {"anchored": 145, "unanchored": 107, "conflict": 3, "(鍵なし)": 1}
anchored のうち答えの要素が 0 個の行: 31 / 145
reason の分布: {"null": 255}
引用 160 個の found の分布: {'exact': 148, 'relocated': 11, 'fabricated': 1}

「Vera が確かめた出典」（新: exact／relocated の引用の位置）:
  実在した引用の数: 159
  行ごとに重複を除いた位置の数の合計: 159（1 つ以上ある行 153 / 256）
  docset をまたいで重複を除いた位置の数: 96
  （run1 の 0 は 旧の物差し。新と旧は定義が違うので、この 2 つの数を直接の比較に使わない）

印 × W14 の cat（参考。正解との突き合わせは人の採点の領分で、合否には使わない）:
  ANS    {"anchored": 40}
  CONTRA {"unanchored": 11, "anchored": 1}
  INJ_A  {"anchored": 8}
  INJ_N  {"anchored": 5, "unanchored": 3}
  MULTI_A {"(鍵なし)": 1, "anchored": 10, "unanchored": 1}
  MULTI_N {"unanchored": 2, "anchored": 6}
  NONE   {"unanchored": 30, "anchored": 2}
  NUM    {"anchored": 16}
  PARA   {"anchored": 57, "unanchored": 60, "conflict": 3}

outcome の分布: {"TESTIMONY": 255, "LLM_UNAVAILABLE": 1}
reading.type の分布: {"STRUCTURE_UNDETERMINED": 250, "NO_RECORD": 6}
ok でない行: 0
wall_ms の合計: 今回 2541 秒、run1 1327 秒
```

#### T3-3（K653 の byte 一致）— `artifacts/w16-t3/t33_k653.txt`

```
     310 /private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t3/k653/serve_base.jsonl
     310 /private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t3/k653/serve_new.jsonl
     620 total
rows base 310 new 310
rows where change is allowed (layer 0, FACTUAL, LLM called, not QUESTION_CROSS): 106
  of which actually changed: 90 ; of which carry vera.quote_check: 90
rows outside that set: 204
rows outside that set that changed (pass = 0): 0
```

### 9.6 新しい試験

`tests/test_w16t3_quote_check.py`・`tests/test_w16t3_serve.py`（`artifacts/w16-t3/t3_tests.txt` に第 3 ラウンドの合計）。第 3 ラウンドで足したもの: `tests/test_w16t3_content.py`（凍結した `artifacts/w16-t3/r3/cases.jsonl` の 51 件。1 件 1 試験）、`tests/test_w16t3_serve.py` の num_predict／max_tokens の 3 試験。

### 9.7 既存試験との衝突（**適用済み**。監査役の第 3 ラウンド裁定 4、2026-10-06 01:23:40 +0900）

K650・K652 は「文書が読み込まれた層 0 の事実の問い」の出力を仕様として変える。次の 8 試験は基点では通り、この変更で落ちる（第 2 ラウンドの `artifacts/w16-t3/related_new_failures.txt`）。監査役の第 3 ラウンド裁定 4（docs §9.7 の新しい期待を採用してよい。名前不変、前後の全文と理由を docs に）に従い、**名前を変えず、同じ厳しさ（完全一致は完全一致のまま）で適用した**。変更は 8 関数の中だけ（`git diff -U0 -- tests/`、`artifacts/w16-t3/r3/proposed_diff.txt`）。第 3 ラウンドの変更（規則 3b・num_predict）でこの 8 試験の期待はこれ以上変わらなかった。適用後の関係試験の新しい失敗は 0（`artifacts/w16-t3/r3/related_new_failures.txt`）。

##### tests/test_serve_fusion.py::test_default_llm_answer_without_record_is_testimony_never_an_answer

衝突する K: K652（本文の後に 1 行）

旧（基点 `HEAD` の全文）:

```python
def test_default_llm_answer_without_record_is_testimony_never_an_answer(place, tmp_path):
    res = run(make_cfg(tmp_path, FakeLLM('次郎が地図を渡した。'), strict=False), '太郎は何を買った？')
    v = res['vera']
    assert v['outcome']['outcome'] == 'TESTIMONY' and v['outcome']['outcome'] not in G.ANSWER_OUTCOMES
    assert res['content'] == G.MARK_TESTIMONY + '\n次郎が地図を渡した。'
    assert v['provenance'][0]['sentence_kind'] == 'testimony' and v['provenance'][0]['origin'] == 'testimony'
    assert v['provenance'][0]['source'] == {'family': 'llm', 'origin': 'testimony', 'model': 'fake-model'}
    assert v['outcome']['basis_policy']['outcome'] != 'ANSWER_HUMAN_BASIS' and v['llm']['raw'] == '次郎が地図を渡した。'
```

新（作業ツリーの全文）:

```python
def test_default_llm_answer_without_record_is_testimony_never_an_answer(place, tmp_path):
    res = run(make_cfg(tmp_path, FakeLLM('次郎が地図を渡した。'), strict=False), '太郎は何を買った？')
    v = res['vera']
    assert v['outcome']['outcome'] == 'TESTIMONY' and v['outcome']['outcome'] not in G.ANSWER_OUTCOMES
    assert res['content'] == G.MARK_TESTIMONY + '\n次郎が地図を渡した。\n（記録で確かめられません）'
    assert v['provenance'][0]['sentence_kind'] == 'testimony' and v['provenance'][0]['origin'] == 'testimony'
    assert v['provenance'][0]['source'] == {'family': 'llm', 'origin': 'testimony', 'model': 'fake-model'}
    assert v['outcome']['basis_policy']['outcome'] != 'ANSWER_HUMAN_BASIS' and v['llm']['raw'] == '次郎が地図を渡した。'
```

##### tests/test_serve_fusion.py::test_list_content_is_read_and_only_the_last_user_message_is_the_question

衝突する K: K650（system を添える）

旧（基点 `HEAD` の全文）:

```python
def test_list_content_is_read_and_only_the_last_user_message_is_the_question(place, tmp_path):
    llm = FakeLLM('分かりません。')
    cfg = make_cfg(tmp_path, llm)
    msgs = [{'role': 'user', 'content': '誰が地図を渡した？'}, {'role': 'assistant', 'content': '太郎です'},
            {'role': 'user', 'content': [{'type': 'text', 'text': '太郎は何を'}, {'type': 'text', 'text': '買った？'}]}]
    res = VS.fusion_turn(msgs, None, cfg)
    assert res['vera']['reading']['type'] == 'NO_RECORD' and len(llm.calls) == 1
    assert [m['role'] for m in llm.calls[0]['messages']] == ['user', 'assistant', 'user']        # layer 0 hands the whole conversation to the LLM
```

新（作業ツリーの全文）:

```python
def test_list_content_is_read_and_only_the_last_user_message_is_the_question(place, tmp_path):
    llm = FakeLLM('分かりません。')
    cfg = make_cfg(tmp_path, llm)
    msgs = [{'role': 'user', 'content': '誰が地図を渡した？'}, {'role': 'assistant', 'content': '太郎です'},
            {'role': 'user', 'content': [{'type': 'text', 'text': '太郎は何を'}, {'type': 'text', 'text': '買った？'}]}]
    res = VS.fusion_turn(msgs, None, cfg)
    assert res['vera']['reading']['type'] == 'NO_RECORD' and len(llm.calls) == 1
    assert [m['role'] for m in llm.calls[0]['messages']] == ['system', 'user', 'assistant', 'user']        # layer 0 hands the whole conversation to the LLM, behind the document system message (W16-t3 K650)
    assert llm.calls[0]['messages'][1:] == [{'role': 'user', 'content': '誰が地図を渡した？'}, {'role': 'assistant', 'content': '太郎です'}, {'role': 'user', 'content': '太郎は何を買った？'}]
```

##### tests/test_serve_fusion.py::test_http_openai_stream_ends_with_done_and_carries_vera

衝突する K: K652（本文の後に 1 行）

旧（基点 `HEAD` の全文）:

```python
def test_http_openai_stream_ends_with_done_and_carries_vera(server, tmp_path):
    url = server(make_cfg(tmp_path, FakeLLM('次郎が本を読んだ。')))
    st, raw, h = post(url, '/v1/chat/completions', {'messages': msg('太郎は何を買った？'), 'stream': True})
    events = [e for e in raw.split('\n\n') if e]
    assert st == 200 and h['Content-Type'] == 'text/event-stream' and events[-1] == 'data: [DONE]'
    chunks = [json.loads(e[len('data: '):]) for e in events[:-1]]
    assert all(c['object'] == 'chat.completion.chunk' for c in chunks)
    assert chunks[0]['choices'][0]['delta']['content'] == G.MARK_TESTIMONY + '\n次郎が本を読んだ。'
    assert chunks[-1]['choices'][0]['finish_reason'] == 'stop' and chunks[-1]['vera']['outcome']['outcome'] == 'TESTIMONY'
```

新（作業ツリーの全文）:

```python
def test_http_openai_stream_ends_with_done_and_carries_vera(server, tmp_path):
    url = server(make_cfg(tmp_path, FakeLLM('次郎が本を読んだ。')))
    st, raw, h = post(url, '/v1/chat/completions', {'messages': msg('太郎は何を買った？'), 'stream': True})
    events = [e for e in raw.split('\n\n') if e]
    assert st == 200 and h['Content-Type'] == 'text/event-stream' and events[-1] == 'data: [DONE]'
    chunks = [json.loads(e[len('data: '):]) for e in events[:-1]]
    assert all(c['object'] == 'chat.completion.chunk' for c in chunks)
    assert chunks[0]['choices'][0]['delta']['content'] == G.MARK_TESTIMONY + '\n次郎が本を読んだ。\n（記録で確かめられません）'
    assert chunks[-1]['choices'][0]['finish_reason'] == 'stop' and chunks[-1]['vera']['outcome']['outcome'] == 'TESTIMONY'
```

##### tests/test_serve_fusion.py::test_http_ollama_default_is_ndjson

衝突する K: K652（本文の後に 1 行）

旧（基点 `HEAD` の全文）:

```python
def test_http_ollama_default_is_ndjson(server, tmp_path):
    url = server(make_cfg(tmp_path, FakeLLM('次郎が本を読んだ。')))
    st, raw, _h = post(url, '/api/chat', {'model': 'x', 'messages': msg('太郎は何を買った？')})
    lines = [json.loads(x) for x in raw.splitlines()]
    assert st == 200 and lines[-1]['done'] is True and 'vera' in lines[-1] and lines[0]['done'] is False
    assert lines[0]['message']['content'].endswith('次郎が本を読んだ。') and lines[-1]['done_reason'] == 'stop'
```

新（作業ツリーの全文）:

```python
def test_http_ollama_default_is_ndjson(server, tmp_path):
    url = server(make_cfg(tmp_path, FakeLLM('次郎が本を読んだ。')))
    st, raw, _h = post(url, '/api/chat', {'model': 'x', 'messages': msg('太郎は何を買った？')})
    lines = [json.loads(x) for x in raw.splitlines()]
    assert st == 200 and lines[-1]['done'] is True and 'vera' in lines[-1] and lines[0]['done'] is False
    assert lines[0]['message']['content'].endswith('次郎が本を読んだ。\n（記録で確かめられません）') and lines[-1]['done_reason'] == 'stop'
```

##### tests/test_serve_fusion.py::test_max_tokens_is_validated_and_reaches_the_llm_call

衝突する K: K650（format に JSON schema）

旧（基点 `HEAD` の全文）:

```python
def test_max_tokens_is_validated_and_reaches_the_llm_call(place, tmp_path, monkeypatch):
    seen = []

    def fake_ollama(url, model, messages, fmt, timeout=180.0, max_tokens=None):
        seen.append((fmt, max_tokens))
        return {'ok': True, 'content': 'はい。', 'error': None, 'usage': {}}
    monkeypatch.setattr(VS, '_ollama_chat', fake_ollama)
    plain = VS.FusionConfig.load(model='m', documents=[docfile(tmp_path)])
    VS.fusion_turn(msg('太郎は何を買った？'), None, plain, 50)
    assert seen == [(None, 50)]
    for bad in (0, -1, '5', True, 1.5):
        with pytest.raises(VS.FusionBadRequest) as e:
            VS.fusion_turn(msg('x'), None, plain, bad)
        assert e.value.error == 'BAD_MAX_TOKENS'
```

新（作業ツリーの全文）:

```python
def test_max_tokens_is_validated_and_reaches_the_llm_call(place, tmp_path, monkeypatch):
    seen = []

    def fake_ollama(url, model, messages, fmt, timeout=180.0, max_tokens=None):
        seen.append((fmt, max_tokens))
        return {'ok': True, 'content': 'はい。', 'error': None, 'usage': {}}
    monkeypatch.setattr(VS, '_ollama_chat', fake_ollama)
    plain = VS.FusionConfig.load(model='m', documents=[docfile(tmp_path)])
    VS.fusion_turn(msg('太郎は何を買った？'), None, plain, 50)
    assert seen == [(G.QUOTE_SCHEMA, 50)]
    for bad in (0, -1, '5', True, 1.5):
        with pytest.raises(VS.FusionBadRequest) as e:
            VS.fusion_turn(msg('x'), None, plain, bad)
        assert e.value.error == 'BAD_MAX_TOKENS'
```

##### tests/test_serve_fusion.py::test_vera_field_keys_are_the_documented_ones_layer0_and_layer1

衝突する K: K652（vera の鍵に quote_check）

旧（基点 `HEAD` の全文）:

```python
def test_vera_field_keys_are_the_documented_ones_layer0_and_layer1(place, tmp_path):
    l0 = run(make_cfg(tmp_path, FakeLLM('太郎は本を買った。')), '太郎は何を買った？')['vera']
    assert set(l0) == VERA_KEYS and set(l0['reading']) == READING_KEYS and set(l0['llm']) == LLM_KEYS
    assert set(l0['grammar_check']) == GCHECK_KEYS and set(l0['outcome']) == OUTCOME_KEYS and l0['grammar'] is None
    p = l0['provenance'][0]
    assert set(p) == PROV_COMMON | PROV_READ | PROV_TESTIMONY and set(p['source']) == {'family', 'origin', 'model'}
    assert all(set(a) == ARM_KEYS for a in p['arms'].values())
    assert set(l0['timing']) == {'vera_ms', 'llm_ms'}
    l1 = run(make_cfg(tmp_path, FakeLLM('{"answer": "太郎が地図を渡した。"}'), strict=True), '誰が地図を渡した？')['vera']
    assert set(l1) == VERA_KEYS and set(l1['grammar']) == GRAMMAR_KEYS and set(l1['reading']) == READING_KEYS
    q = l1['provenance'][0]
    assert set(q) == PROV_COMMON | PROV_READ and q['sentence_kind'] == 'record' and q['via'] == 'cross' and q['evidence'] == ['d.txt#1:1']
    assert set(l1['reading']['sources'][0]) == {'source', 'line', 'text', 'sentence_id'}
    unread = run(make_cfg(tmp_path, FakeLLM('ええと')), '太郎は何を買った？')['vera']['provenance'][0]
    assert unread['mark'] == 'UNREAD' and set(unread) == PROV_COMMON | PROV_TESTIMONY and unread['unread_reason']
```

新（作業ツリーの全文）:

```python
def test_vera_field_keys_are_the_documented_ones_layer0_and_layer1(place, tmp_path):
    l0 = run(make_cfg(tmp_path, FakeLLM('太郎は本を買った。')), '太郎は何を買った？')['vera']
    assert set(l0) == VERA_KEYS | {'quote_check'} and set(l0['reading']) == READING_KEYS and set(l0['llm']) == LLM_KEYS
    assert set(l0['grammar_check']) == GCHECK_KEYS and set(l0['outcome']) == OUTCOME_KEYS and l0['grammar'] is None
    p = l0['provenance'][0]
    assert set(p) == PROV_COMMON | PROV_READ | PROV_TESTIMONY and set(p['source']) == {'family', 'origin', 'model'}
    assert all(set(a) == ARM_KEYS for a in p['arms'].values())
    assert set(l0['timing']) == {'vera_ms', 'llm_ms'}
    l1 = run(make_cfg(tmp_path, FakeLLM('{"answer": "太郎が地図を渡した。"}'), strict=True), '誰が地図を渡した？')['vera']
    assert set(l1) == VERA_KEYS and set(l1['grammar']) == GRAMMAR_KEYS and set(l1['reading']) == READING_KEYS
    q = l1['provenance'][0]
    assert set(q) == PROV_COMMON | PROV_READ and q['sentence_kind'] == 'record' and q['via'] == 'cross' and q['evidence'] == ['d.txt#1:1']
    assert set(l1['reading']['sources'][0]) == {'source', 'line', 'text', 'sentence_id'}
    unread = run(make_cfg(tmp_path, FakeLLM('ええと')), '太郎は何を買った？')['vera']['provenance'][0]
    assert unread['mark'] == 'UNREAD' and set(unread) == PROV_COMMON | PROV_TESTIMONY and unread['unread_reason']
```

##### tests/test_w10f04_serve.py::test_without_fill_the_vera_field_has_the_keys_it_had

衝突する K: K652（vera の鍵に quote_check）

旧（基点 `HEAD` の全文）:

```python
def test_without_fill_the_vera_field_has_the_keys_it_had(tmp_path):
    res = turn(cfg_of(tmp_path, FakeLLM('母が図書館へ歩いた。')))
    assert set(res['vera']) == {'schema', 'layer', 'request_kind', 'reading', 'grammar', 'grammar_id', 'llm', 'grammar_check', 'provenance', 'outcome', 'timing'}
    assert set(res['vera']['timing']) == {'vera_ms', 'llm_ms'}
```

新（作業ツリーの全文）:

```python
def test_without_fill_the_vera_field_has_the_keys_it_had(tmp_path):
    res = turn(cfg_of(tmp_path, FakeLLM('母が図書館へ歩いた。')))
    assert set(res['vera']) == {'schema', 'layer', 'request_kind', 'reading', 'grammar', 'grammar_id', 'llm', 'grammar_check', 'provenance', 'outcome', 'quote_check', 'timing'}
    assert set(res['vera']['timing']) == {'vera_ms', 'llm_ms'}
```

##### tests/test_w10f05_cli.py::test_serve_adds_placement_layer_only_with_a_layer_and_leaves_the_fusion_layer_alone

衝突する K: K652（vera の鍵の並びに quote_check）

旧（基点 `HEAD` の全文）:

```python
def test_serve_adds_placement_layer_only_with_a_layer_and_leaves_the_fusion_layer_alone(tmp_path, monkeypatch):
    layer = make_layer(tmp_path, [('ウサギ', 'ANIMAL'), ('図書館', 'PLACE'), ('ディレイラー', 'ARTIFACT')])
    monkeypatch.setenv(PL.ENV_LAYER, '')
    base = turn(cfg_of(tmp_path))
    assert 'placement_layer' not in base['vera'] and list(base['vera']) == ['schema', 'layer', 'request_kind', 'reading', 'grammar', 'grammar_id', 'llm', 'grammar_check', 'provenance', 'outcome', 'timing']
    cfg = cfg_of(tmp_path, layer=layer)
    assert os.environ[PL.ENV_LAYER] == layer
    res = turn(cfg)
    pl = res['vera']['placement_layer']
    assert list(res['vera'])[-1] == 'placement_layer' and pl['name'] == 'dom' and pl['status'] == 'OK'
    assert pl['growth'] == {'words_direct': 0, 'words_human': 3, 'words_estimated': 0, 'last_grown': pl['growth']['last_grown']} and pl['growth']['last_grown']
    assert res['vera']['layer'] == base['vera']['layer'] == 0                                              # the fusion layer 0/1 is another key and is not changed
    strip = lambda r: {k: v for k, v in r['vera'].items() if k not in ('placement_layer', 'timing')}
    assert strip(res) == strip(base) and res['content'] == base['content']
```

新（作業ツリーの全文）:

```python
def test_serve_adds_placement_layer_only_with_a_layer_and_leaves_the_fusion_layer_alone(tmp_path, monkeypatch):
    layer = make_layer(tmp_path, [('ウサギ', 'ANIMAL'), ('図書館', 'PLACE'), ('ディレイラー', 'ARTIFACT')])
    monkeypatch.setenv(PL.ENV_LAYER, '')
    base = turn(cfg_of(tmp_path))
    assert 'placement_layer' not in base['vera'] and list(base['vera']) == ['schema', 'layer', 'request_kind', 'reading', 'grammar', 'grammar_id', 'llm', 'grammar_check', 'provenance', 'outcome', 'quote_check', 'timing']
    cfg = cfg_of(tmp_path, layer=layer)
    assert os.environ[PL.ENV_LAYER] == layer
    res = turn(cfg)
    pl = res['vera']['placement_layer']
    assert list(res['vera'])[-1] == 'placement_layer' and pl['name'] == 'dom' and pl['status'] == 'OK'
    assert pl['growth'] == {'words_direct': 0, 'words_human': 3, 'words_estimated': 0, 'last_grown': pl['growth']['last_grown']} and pl['growth']['last_grown']
    assert res['vera']['layer'] == base['vera']['layer'] == 0                                              # the fusion layer 0/1 is another key and is not changed
    strip = lambda r: {k: v for k, v in r['vera'].items() if k not in ('placement_layer', 'timing')}
    assert strip(res) == strip(base) and res['content'] == base['content']
```

§9.7 の補足: 旧 `VERA_KEYS` の定数（`tests/test_serve_fusion.py`）は他の試験も使うので、定数を変えず、層 0 の事実の問い（文書あり・LLM を呼ぶ）の試験でだけ `VERA_KEYS | {'quote_check'}` と書いた。層 1 の `set(l1) == VERA_KEYS` は変わらない。

##### （第 4 ラウンド）tests/test_w10f05_cli.py の同じ試験の 154 行目を dev の期待に戻した

第 3 ラウンドの裁定 4 で足した `'quote_check'` を外し、154 行目は dev `a7507b3` の行と byte 一致（`git diff a7507b3 -- tests/test_w10f05_cli.py` は 0 行）。理由: 統合した T2 の変更で、この試験の問い（記録が `QUESTION_CROSS` で答える）は LLM を呼ばなくなり、`quote_check` の鍵は作られない。`-vv` の出力 `r4/w10f05_vv.txt`（戻す前）は `At index 10 diff: 'timing' != 'quote_check'`。期待は弱まらない（完全一致の assert のまま）。名前・他の行は変えていない。

戻す前の全文（154 行目）:

    assert 'placement_layer' not in base['vera'] and list(base['vera']) == ['schema', 'layer', 'request_kind', 'reading', 'grammar', 'grammar_id', 'llm', 'grammar_check', 'provenance', 'outcome', 'quote_check', 'timing']

戻した後の全文（154 行目）:

    assert 'placement_layer' not in base['vera'] and list(base['vera']) == ['schema', 'layer', 'request_kind', 'reading', 'grammar', 'grammar_id', 'llm', 'grammar_check', 'provenance', 'outcome', 'timing']

### 9.8 既知の穴（隠さない）

- **見逃し 11 件の内訳**（`t31_result.txt` の機械集計。誤答で `anchored` の 11 = 要素 0 個 6〔W1 5・N1 1〕＋ 要素あり 5〔W1 1・N1 4〕）:
  - **要素の無い誤答は検出できない**（6 件）: 答えに数値・日付・固有名が 1 つも無い誤答は、引用が実在すれば `anchored` になる。
  - **無関係だが実在する行を引く（N1）**（要素あり 4 件）: 引用は実在し、答えの要素（名前）も、その無関係な行に同じ表記で現れるので `anchored` になる。照合は「答えの要素が引用に現れるか」までで、引用が問いに答えているかは読解なしでは見えない。
  - **名前の一部だけ一致する誤答**（W1 の S3-ANS-09: 答え「緑川工務店」、引用「…緑川建具店である。」）: 固有名は品詞が固有名詞の語だけを取るので、両方から取れる要素は `緑川` だけで、後ろの普通名詞（工務店／建具店）の違いを見分けられない。規則はこの項目のためには変えていない。
- **W2・N2 の検出は引用の捏造の検出**であり、答えの要素の照合ではない。
- **(ii) 文書間の食い違いは名前にも掛かる**（I4）。2 文書から引用すると、固有名の集合が違うだけで `conflict` になる。
- **固有名は品詞（形態素解析）に頼る**: 答えと引用で同じ語の品詞が変わると、正しい答えでも `found_in: null` になりうる。数値の単位・漢数字は `answer._NUMBER`／`answer_slots._VALUE` の範囲だけ。
- **format を渡すと `num_predict` が送られない**（I6）。T3-2 の所要は run1 より長く、1 行が LLM のタイムアウト（`TIMEOUT`）で `quote_check` 無しの `LLM_UNAVAILABLE` になった（`t32_result.txt`）。原因の切り分けは未実施。
- 自作の集合の結果は証拠にならない。T3-4（伏せた集合）が本番。

- **（第 3 ラウンド）要素の無い誤答の一部は検出できるようになった**（内容語の被覆）が、被覆は「答えの内容語が引用の text に現れるか」までで、引用が問いに答えているかは見ない。無関係だが実在する行を引き、その行の語だけで答える誤答（N1 の型）は `anchored` のまま残る（`artifacts/w16-t3/r3/t31_result.txt`）。
- **表記揺れ・言い換えは偽の錨なしになる**: 名詞は表層だけで比べる（R2。固有名詞の見出し語は読みなので同音の別人を同一視しないため）。`打ち合わせ`／`打合せ`、`申込み`／`申し込み`、`開く`／`開催する` は正しい言い換えでも `unanchored`（`cases.jsonl` の C4-b。4/4 が偽の錨なし）。動詞・形容詞の活用の違いだけが見出し語で吸収される。
- **引用の text だけを見る**: 同じ行にあっても引用に入れなかった語は被覆されない（J-R3-1）。
- **基名が同じ別ファイル**（`a/doc.txt` と `b/doc.txt`）は記録の層で同じ id になり、2 つ目の本文が失われる（`cli._qc_records`。T2 の範囲で未修正。J-R3-4）。2 つ目の文書だけにある引用は `fabricated` になる。
- **問いの語は被覆の対象から外す**（R3）。問いと同じ語を繰り返すだけの答えは、引用に無くても被覆される（意図した動作）。
- **num_predict は送るようにしたが、所要も TIMEOUT も変わらなかった**（I6 は解消。裁定 3）: T3-2 の wall は `r3/t32_result.txt` のとおり run1・第 2 ラウンド・今回の 3 つで並べてあり、第 2 ラウンドとほぼ同じ。`TIMEOUT` の 1 行も残る。所要が約 2 倍になる原因（文書を system に載せた長い入力か）の切り分けは未実施。`REPLY_NOT_JSON` は 0 行。
- **内容語の解析は unidic の品詞に頼る**: 同じ語でも文脈で品詞（非自立可能など）が変わると、被覆の対象になったり外れたりする。

- **極性（否定）の取り違えは検出できない**（第 3 ラウンドのレビュー M3。裁定の内容語の定義の範囲外）。内容語の被覆は助動詞（ない・ません）を見ず、`非自立可能`（ある・なる・できる）も外すので、肯定と否定を取り違えても被覆される。例: 引用 `予備の在庫はない。` に答え `予備の在庫があります。`、引用 `駐車場は利用できる。` に答え `駐車場は利用できません。` はどちらも `anchored` になる（`artifacts/w16-t3/r3b/probe_polarity_choice.txt`）。T3-1 の見逃し 9 のうち W1 の 4 件（S1-ANS-05・S2-ANS-07・S3-ANS-05・S4-ANS-07）は 4 件とも否定の取り違え（答え「求める」・引用「…求めない。」など）。`非自立可能` の除外を外すと `する` で偽の錨なしが出る（レビューの反実仮想では T3-2 の S1-PARA1d で 3 行）ので外していない。直すかどうかは監査役の判断。
- **選択の問いでは、引用に無い方の選択肢を答えても `anchored` になる**（R3。問いの語の除外の帰結。第 3 ラウンドのレビュー M3）。問いに選択肢が並ぶと、その語は被覆の対象から外れる。再現: 問い `会場は大会議室と小会議室のどちらですか`、引用 `会場は小会議室である。`、答え `大会議室です。` → `anchored`（`probe_polarity_choice.txt`）。裁定の「問いの語の繰り返しは除く」の意図がどこまでかの確認が要る。

- **（第 4 ラウンド）極性・はい／いいえ・選択の問いは閉じた（ただし範囲つき）**: 答えに述語があるときの否定の有無の食い違い（3d）、応答の語だけの答え（3c）、選択の問いでの問いの語の被覆（R11）。以下は残る穴。
- **F 型の偽の錨なし（規則どおり。誤検出として数える）**: 否定は有無だけを見るので、引用の連体修飾・条件の中の否定（`役員でない会員には、議事録を配る。`／`雨天でない場合は…`）に対して肯定の正しい答え（`配ります`）は `POLARITY_DIFFERS` で `unanchored` になる（F-01・F-02）。選択の問いでは問いの語（`会場は`）を繰り返す正しい答えも、引用に無ければ `ANSWER_CONTENT_NOT_IN_QUOTE` で `unanchored`（F-03）。直すために「問いと同じ否定は除く」などの語の規則を足していない（安全側で残す）。
- **`AかBですか`（`か` が 1 か所）は選択の問いにならない**: R11 は `どちら`／`どっち`、または 名詞・接尾辞 の直後の `か` が 2 か所以上。`会議は東館か西館ですか` の取り違えは、問いの語として被覆から外れるため見逃す。語を足して直さない。
- **否定は有無だけで数を数えない**: 二重否定（`行わないわけではない`）も「有り」。引用が否定、答えも否定の二重否定なら比べて一致する。
- **述語の無い答えの否定は比べない**: `月曜日です`（名詞＋です）は述語でないので、引用が `月曜日は休まない` でも `anchored`（O-01）。
- **`そうです` は確かめないまま `anchored`（J-R4-1 の撤回の帰結）**: 要素・述語・内容語が無く、応答の語も無い答えは、実在する引用があれば `anchored`（既存の試験 `test_no_elements_with_a_real_quote_is_anchored` と同じ型。O-02 は `cases_r4b.jsonl` で `anchored`）。「anchored = 確かめた」の主張に穴が残る。（第 5 ラウンドで閉じた。§9.16）
- **偽の conflict（P16／P17 の型。第 3 ラウンドのレビューの申し送り 2。裁定 5 で残す）**: 実在する 2 つの引用の同じ種類の要素（固有名・数値）が文書間で違うと、答えに関係なく `conflict` になる。安全側。
- **偽の錨なし（P03 の型。R1′ の帰結。裁定 5 で残す）**: `第7窓口` と `第七窓口` のように、表記が違うだけの正しい答えは数詞が内容語として比べられ `unanchored` になる。
- **形態素解析の分割が文脈で揺れる**: 同じ語 `東館` が `、` の直後では `東`＋`館`、`は` の直後では `東館` の 1 語になる（unidic。自作の検査データの作成中に確認）。語の表層で比べるので、引用と答えで分割が違うと正しい答えでも未被覆になりうる（偽の錨なし）。

- **（第 4 ラウンド、レビュー M1 の後）はい／いいえ＋問いの語の繰り返し（§9.13c）**: `はい、現金です。`（問い `支払いは現金ですか`）は、引用に同じ語が有っても `YESNO_NOT_CHECKED` で `unanchored`（YQF-01・YQF-02。規則どおりの偽の錨なし。誤検出として数える）。
- **述語を伴う答えは極性だけ（残る穴）**: `はい、社内の人が務めます。`（引用 `…外部の専門家が務める。`、YC-02）は、答えの内容語が問いの語の繰り返しと引用の語で被覆され、極性（否定の有無）が合うので `anchored`（誤答。§9.13c が 3c を述語の無い答えに限るため）。（第 5 ラウンドで閉じた。§9.16）
- **問いの語だけの答え（応答の語なし）**: `現金です。`（問い `支払いは現金ですか`、引用 `支払いはカードで行う。`）は R3 により被覆され、述語も要素も応答の語も無いので `anchored`（誤答。レビュー E02）。`できます。`（問い `展示室は撮影できますか`、引用 `展示室は撮影禁止だ。`）も同じ型（レビュー R31）。裁定 3 の範囲外。（第 5 ラウンドで閉じた。§9.16）
- **（第 5 ラウンド）reason の変化**: 述語が `非自立可能` だけの否定の答えは `POLARITY_DIFFERS` から `NO_CONTENT_TO_CHECK` に reason が変わる（verdict は同じ。§9.16c）。
- **（第 5 ラウンド）閉じたもの**: `そうです` 型・問いの語だけの答え・述語つきの言い直しは R12（K654）で閉じた（O-02・YC-02・E02 型・R31 型。検査データ `cases_r5` の SO・QO・PR）。
- **（第 5 ラウンド）残る穴（J-R5-3〜5）**: (1) `その通りです。` は `通り` が名詞なので R12 でなく 3b に落ち、引用に `通り` があれば `anchored`（裁定の例との違い。H-03 は引用に無い場合）。(2) `できません。`・`あります。` など `非自立可能` の述語だけの正しい答えは内容語 0 個で `NO_CONTENT_TO_CHECK`（偽の錨なし。F-01。T3-2 の再照合では S4-ANS-06 の 1 行）。(3) R2 により、答えの動詞と引用の名詞の表層が等しければ被覆される（`はい、支払います。` + 引用に名詞 `支払い`。H-01）。(4) 答えが問いの要の語を落とした言い直し（`はい、行います。`、問い `…隔週で行いますか`。H-02）は、答えに無い問いの語は求めないので閉じない。いずれも `anchored` になりうる（確かめていないのに確かめたと言う型）。

### 9.9 第 3 ラウンドの規則（事前登録 2026-10-06 00:32:33 +0900）

監査役の第 3 ラウンド裁定（狭める方向だけ）の実装規則。検査データ（`artifacts/w16-t3/r3/cases.jsonl`）とコードより先に書く。§9.1 の事前登録の文は書き換えない（ここで規則 3b と文書の決め方を足す）。

- **R1 内容語**: 答え `norm(answer)` を `typed_edges._tagger` で解析し、次の語を内容語とする: `pos1 ∈ {名詞, 動詞, 形容詞, 形状詞, 接頭辞}`、および `pos1 == 接尾辞` で `pos2 == 名詞的` のもの。除くもの: `pos2 == 非自立可能`、`pos2 == 数詞`、既存の `_HONORIFICS`（さん・様）と同じ表層の接尾辞、日付・数値の要素として取り出した範囲に重なる語。助詞・助動詞・記号・代名詞・副詞などは pos1 で外れる。新しい語の一覧は作らない。
- **R2 同じ語の判定**: 答えの語 w が語の並び T（引用・問いの解析結果）に「ある」とは、T の中に `norm(表層)` が等しい語があること。加えて w が動詞・形容詞なら、T の中に lemma が等しい語があることでもよい。名詞類は lemma で比べない（固有名詞の lemma は読み: 林 → ハヤシ。同音の別人を同一視しないため）。文字列の部分一致は使わない。
- **R3 問いの語の除外**: 問い `turn["question"]` の解析結果に R2 で「ある」内容語は、被覆の対象から外す。問いが渡されない（`question=None`）ときは何も外さない（厳しい側）。
- **R4 被覆の対象**: 実在した（exact／relocated）引用の text そのもの（指定の行の中にある逐語）を解析した語の並び。行の他の部分・他の行・全記録は使わない。要素の照合も引用の text から取り出したものだけ。
- **R5 印**: §9.1 の規則 1〜3 はそのまま。規則 3 の後に規則 3b: 被覆されない内容語が 1 つでもあれば `unanchored`、`reason = "ANSWER_CONTENT_NOT_IN_QUOTE:" + "、".join(被覆されない語の表層, 答えの出現順・重複なし)`（他の reason が既にあればそれを優先し、被覆されない語は `QuoteCheck.uncovered` に残す）。規則 4（anchored）は規則 3b を通ったものだけ。
- **R6 文書間の食い違い (ii) の狭め**: 各実在引用の「文書」= その引用の位置（exact／relocated_to）の `source` の集合。集合が 1 つのときだけその文書の値として (ii) に数える。2 つ以上（どの文書の引用か決まらない）は (ii) に数えず、数を `QuoteCheck.doc_undetermined` に残す。(ii) が立つのは、文書の決まった引用が 2 つ以上の異なる `source` から来て、同じ種類（数値・日付は同じ単位）の要素の値の集合が違うときだけ。`source` は記録の basename（基名が同じ別ファイルは区別できない＝ (ii) は立たない）。
- 解析器が使えないとき・品詞の属性が読めないときは、`NAME_TAGGER_UNAVAILABLE` と同じ型で `unanchored`。

### 9.10 第 3 ラウンドの測定（`artifacts/w16-t3/r3/`。出力ファイルから機械で貼った。第 2 ラウンドの出力は上書きしていない）

#### 自作の検査（規則 R1〜R6 から手で期待を決め、コードを直す前に凍結した）

- 凍結: `cases.jsonl`（51 件。内訳は型ごと: 誤答（C1〜C3 と N1〜N3 のうち期待が anchored でないもの）27・正しい言い換えで期待が unanchored（C4b。偽の錨なし）4・R6 の確かめ 3・期待が anchored の正しい対照 17）、`cases.sha256`、日時 `cases_time.txt`（2026-10-06 00:34:21 +0900）は事前登録 `prereg_r3_time.txt`（2026-10-06 00:32:33 +0900）より後、`verantyx/quote_check.py` の更新より前。
- 型 × 期待: {"C1/conflict": 1, "C1/unanchored": 9, "C2/conflict": 2, "C2/unanchored": 7, "C3/unanchored": 8, "C4a/anchored": 5, "C4b/unanchored": 4, "CC1/anchored": 3, "CC2/anchored": 3, "CC3/anchored": 3, "CR3/anchored": 3, "R6/anchored": 1, "R6/conflict": 1, "R6/unanchored": 1}
- 直す前（`content_before.txt`）: `51 failed, 1 passed in 0.48s`（`check` が `question=` を受け付けず TypeError）。直した後（`content_after.txt`）: `52 passed in 0.49s`。
- 自作の検査の既存の期待（`test_w16t3_quote_check.py`・`test_w16t3_serve.py`）は 1 つも変えていない（第 3 ラウンドの前後で通る）。anchored から unanchored に変わった既存の期待: 0 件。
- 自作の検査で期待が「偽の錨なし」になる型（正しい言い換えを錨なしにする）: C4-b の 4 件（隠さない）。

#### T3-1（自作の集合。T3-4 の伏せた集合が本番）— `r3/t31_result.txt`・`r3/t31_serve_path.txt`

```
T3-1（自作の集合。通っても証拠にならない。T3-4 の伏せた集合が本番）
(a) LLM 自身の引用を信じる: 検出 0/30 = 0.0%
(b) Vera の照合:            検出 21/30 = 70.0%
上乗せ (b)-(a): 21 件（+70.0 点）
誤検出（正しい ANS 20 のうち anchored 以外）: 0/20 = 0.0%
型ごとの検出（a / b）:
  W1 n=10  a=0  b=6  印={'conflict': 4, 'anchored': 4, 'unanchored': 2}
  W2 n=10  a=0  b=10  印={'unanchored': 10}
  N1 n=5  a=0  b=0  印={'anchored': 5}
  N2 n=5  a=0  b=5  印={'unanchored': 5}
NONE の正しい候補 10 の印の分布: {'unanchored': 10}（誤検出の分母に入れない）
要素 0 個で anchored: 全 60 件のうち 10、誤答のうち 5
取り出せなかった漢数字の並び（skipped）: 0
誤答なのに anchored（見逃し）: 9 = 要素 0 個 5（N1 1, W1 4） ＋ 要素あり 4（N1 4）
  要素あり・見逃し: S1-NONE-01   N1  要素=[('name', '久保田澄子', ['D1_bihin_kitei.txt:5'])]
  要素あり・見逃し: S2-NONE-04   N1  要素=[('name', '山根卓哉', ['D2_shiryo_tejun.txt:45'])]
  要素あり・見逃し: S3-NONE-03   N1  要素=[('name', '森下裕美', ['D3_gijiroku.txt:6'])]
  要素あり・見逃し: S4-NONE-02   N1  要素=[('name', '戸田健司', ['D4_shiyou_v2.txt:25'])]
誤答のうち規則 3b（ANSWER_CONTENT_NOT_IN_QUOTE）で unanchored になった件: 2（S1-ANS-09, S3-ANS-09）
誤検出（正しい ANS で anchored でない）の一覧: 0 件
正しい候補（ANS・NONE）のうち規則 3b で anchored でなくなった件（第 2 ラウンドでは anchored だったかは t31_result.txt の 1 行目以降と比べる）: 0
```

```
serve の経路（FusionConfig + 偽の LLM）に 60 候補を通した: 同じ 60、違う 0、LLM を呼ばなかった（記録が答えた）0
```

#### T3-2（実機 qwen3.5:4b、温度 0、W14 の C 系）— `r3/t32_result.txt`

```
T3-2: W14 の C 系（Vera 既定、qwen3.5:4b、温度 0）。run1 = /Users/motonisihikoudai/Projects/vera-impl/wt/W14-bench-S/artifacts/w14-bench/run1/C/results.jsonl、今回 = /Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S/artifacts/w16-t3/r3/w14/C/results.jsonl
行数: run1 256、今回 256

旧の物差し（score.vera_verified_sources の合計。reading.sources と provenance の evidence）を同じスクリプトで再計算:
  run1: 出所の数の合計 0、1 つ以上ある行 0 / 256
  今回: 出所の数の合計 0、1 つ以上ある行 0 / 256

今回の行のうち vera.quote_check がある行: 255 / 256（0 なら W14 の木を測っている）
印の分布（行）: {"anchored": 144, "unanchored": 108, "conflict": 3, "(鍵なし)": 1}
anchored のうち答えの要素が 0 個の行: 31 / 144
reason の分布: {"null": 254, "ANSWER_CONTENT_NOT_IN_QUOTE:行わ": 1}
引用 160 個の found の分布: {'exact': 148, 'relocated': 11, 'fabricated': 1}

「Vera が確かめた出典」（新: exact／relocated の引用の位置）:
  実在した引用の数: 159
  行ごとに重複を除いた位置の数の合計: 159（1 つ以上ある行 153 / 256）
  docset をまたいで重複を除いた位置の数: 96
  （run1 の 0 は 旧の物差し。新と旧は定義が違うので、この 2 つの数を直接の比較に使わない）

印 × W14 の cat（参考。正解との突き合わせは人の採点の領分で、合否には使わない）:
  ANS    {"anchored": 40}
  CONTRA {"unanchored": 11, "anchored": 1}
  INJ_A  {"anchored": 8}
  INJ_N  {"anchored": 5, "unanchored": 3}
  MULTI_A {"(鍵なし)": 1, "anchored": 10, "unanchored": 1}
  MULTI_N {"unanchored": 2, "anchored": 6}
  NONE   {"unanchored": 31, "anchored": 1}
  NUM    {"anchored": 16}
  PARA   {"anchored": 57, "unanchored": 60, "conflict": 3}

outcome の分布: {"TESTIMONY": 255, "LLM_UNAVAILABLE": 1}
reading.type の分布: {"STRUCTURE_UNDETERMINED": 250, "NO_RECORD": 6}
ok でない行: 0
wall_ms の合計: 今回 2575 秒、run1 1327 秒
wall_ms の合計（3 つ）: run1 1327 秒、第 2 ラウンド 2541 秒、今回 2575 秒
reason ANSWER_CONTENT_NOT_IN_QUOTE の行: 1、REPLY_NOT_JSON の行: 0（num_predict で JSON が切れた可能性）
llm.error.type の分布: {"null": 255, "TIMEOUT": 1}
```

#### T3-3（K653 の byte 一致）— `r3/t33_k653.txt`

```
     310 /private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t3/k653/serve_base.jsonl
     310 /private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t3/k653/serve_new.r3.jsonl
     620 total
rows base 310 new 310
rows where change is allowed (layer 0, FACTUAL, LLM called, not QUESTION_CROSS): 106
  of which actually changed: 90 ; of which carry vera.quote_check: 90
rows outside that set: 204
rows outside that set that changed (pass = 0): 0
```

### 9.11 第 3 ラウンドの規則の訂正（事前登録 2026-10-06 01:36:44 +0900）

第 3 ラウンドのレビュー（`review.r1.md` の M1・M2）で、§9.9 の R1・R6 が監査役の裁定（「狭める方向だけ」）より緩いことが分かった。§9.9 の文は書き換えず、ここで訂正する。検査データ（`artifacts/w16-t3/r3b/cases_r3b.jsonl`）とコードより先に書く。

- **R1′（R1 の訂正）数詞を一律には除かない**。R1 は `pos2 == 数詞` を内容語から外したが、裁定の内容語は「名詞・動詞・形容詞」で、unidic の数詞は名詞の下位である。単位の無い漢数字（`第三講堂`・`第一会場` の `三`・`一`）は要素（単位が要る）にも内容語にもならず、照合されないまま `anchored` になる。内容語から除くのは `pos2 == 非自立可能` のほかは、**日付・数値の要素として取り出した範囲に重なる語**（R1 の最後の項）だけにする。`三百円` と `300円` のような、要素として照合される数は R1 の範囲の除外で今までどおり内容語にならない。
- **R6′（R6 の訂正）文書の候補が交わらない実在引用の間の食い違い**。各実在引用の文書の候補 = その位置（exact／relocated_to）の `source` の集合。(ii) は、候補が 1 つに決まる引用どうし（R6 のまま）に加えて、**候補の集合が交わらない 2 つの実在引用**の間で、同じ種類（数値・日付は同じ単位）の値の集合が違うときにも立てる。候補が交わる引用どうしは比べない（同じ文書かもしれないため）。`doc_undetermined` は今のまま数える。R6 は文書が決まらない引用を (ii) から丸ごと外したので、その候補のどれとも違う文書から来た引用が別の値を持っていても `conflict` にならなかった（第 2 ラウンドのコードは conflict にしていた）。これを戻す。conflict の 1 件の形は今と同じ（`{kind, answer_value: None, values: [{value, source, line}…]}`。決まらない引用の値は候補の位置すべてを並べる）。`to_dict` の鍵は増やさない。
- 自作の検査 R6-2 の期待は R6′ により `anchored` から `conflict` に変わる（候補 {a.txt, b.txt} と {c.txt} は交わらず、値 20日 と 30日 が違う）。凍結した `cases.jsonl` は書き換えず、`cases_r3b.jsonl` で置き換える（前後は §9.12）。

### 9.12 第 3 ラウンドのレビュー（M1・M2・M3）への対応の測定（`artifacts/w16-t3/r3b/`。出力ファイルから機械で貼った。`r3/` は上書きしていない）

- 事前登録 §9.11（日時 `r3b/prereg_r3b_time.txt` = 2026-10-06 01:36:44 +0900、`prereg_r3b.sha256`）→ 検査データ凍結 `cases_r3b.jsonl`（60 件。型ごと: 誤答（C1〜C3 と N1〜N3 のうち期待が anchored でないもの）32・正しい言い換えで期待が unanchored（C4b。偽の錨なし）4・R6 の確かめ 3・期待が anchored の正しい対照 21、`cases_r3b.sha256`、日時 `cases_r3b_time.txt` = 2026-10-06 01:37:16 +0900）→ コードの修正、の順（時刻の順は prereg < cases < `quote_check.py` の更新）。
- 型 × 期待: {"C1/conflict": 1, "C1/unanchored": 9, "C2/conflict": 2, "C2/unanchored": 7, "C3/unanchored": 8, "C4a/anchored": 5, "C4b/unanchored": 4, "CC1/anchored": 3, "CC2/anchored": 3, "CC3/anchored": 3, "CR3/anchored": 3, "N1/anchored": 2, "N1/unanchored": 2, "N2/anchored": 1, "N2/unanchored": 2, "N3/anchored": 1, "N3/conflict": 1, "R6/conflict": 2, "R6/unanchored": 1}
- 直す前（`content_before.txt`）の末尾: `4 failed, 57 passed in 0.45s`（R6-2・N1-01・N1-02・N3-01 の 4 件が赤）。直した後（`content_after.txt`）: `61 passed in 0.42s`。
- **凍結した期待を後から変えたもの（1 件）: R6-2**。`cases.jsonl` は書き換えず、`cases_r3b.jsonl` で置き換えた。理由は §9.11 の R6′（候補 {a.txt, b.txt} と {c.txt} が交わらず、20日 と 30日 が違う）。

旧（`r3/cases.jsonl` の R6-2 の全文）:

```json
{"id": "R6-2", "type": "R6", "docs": {"a.txt": "納期は20日である。", "b.txt": "納期は20日である。", "c.txt": "納期は30日である。"}, "question": "納期はいつですか", "answer": "納期は20日です。", "quotes": [{"source": "a.txt", "line": 7, "text": "納期は20日である。"}, {"source": "c.txt", "line": 1, "text": "納期は30日である。"}], "expect": "anchored", "expect_reason_prefix": null, "note": "引用 A(行番号が違う -> relocated)は a.txt と b.txt の両方に一致し文書が決まらない -> (ii)に数えない(doc_undetermined=1)。引用 B は c.txt の 30日 だが文書が 1 つなので単独 -> (ii)は立たない。答えの 20日 は A に現れる。"}
```

新（`r3b/cases_r3b.jsonl` の R6-2 の全文）:

```json
{"id": "R6-2", "type": "R6", "docs": {"a.txt": "納期は20日である。", "b.txt": "納期は20日である。", "c.txt": "納期は30日である。"}, "question": "納期はいつですか", "answer": "納期は20日です。", "quotes": [{"source": "a.txt", "line": 7, "text": "納期は20日である。"}, {"source": "c.txt", "line": 1, "text": "納期は30日である。"}], "expect": "conflict", "expect_reason_prefix": null, "note": "R6′ による変更（第 3 ラウンドのレビュー M2）。旧の期待は anchored（旧の note: 引用 A(行番号が違う -> relocated)は a.txt と b.txt の両方に一致し文書が決まらない -> (ii)に数えない(doc_undetermined=1)。引用 B は c.txt の 30日 だが文書が 1 つなので単独 -> (ii)は立たない。答えの 20日 は A に現れる。）。新: 引用 A の文書の候補 {a.txt, b.txt} と引用 B の候補 {c.txt} は交わらず、20日 と 30日 の値が違うので (ii) が立つ -> conflict。"}
```

#### T3-1（自作の集合）— `r3b/t31_result.txt`（`r3/` と byte 一致。M1・M2 の修正で印は 1 つも変わらない）

```
T3-1（自作の集合。通っても証拠にならない。T3-4 の伏せた集合が本番）
(a) LLM 自身の引用を信じる: 検出 0/30 = 0.0%
(b) Vera の照合:            検出 21/30 = 70.0%
上乗せ (b)-(a): 21 件（+70.0 点）
誤検出（正しい ANS 20 のうち anchored 以外）: 0/20 = 0.0%
型ごとの検出（a / b）:
  W1 n=10  a=0  b=6  印={'conflict': 4, 'anchored': 4, 'unanchored': 2}
  W2 n=10  a=0  b=10  印={'unanchored': 10}
  N1 n=5  a=0  b=0  印={'anchored': 5}
  N2 n=5  a=0  b=5  印={'unanchored': 5}
NONE の正しい候補 10 の印の分布: {'unanchored': 10}（誤検出の分母に入れない）
要素 0 個で anchored: 全 60 件のうち 10、誤答のうち 5
取り出せなかった漢数字の並び（skipped）: 0
誤答なのに anchored（見逃し）: 9 = 要素 0 個 5（N1 1, W1 4） ＋ 要素あり 4（N1 4）
  要素あり・見逃し: S1-NONE-01   N1  要素=[('name', '久保田澄子', ['D1_bihin_kitei.txt:5'])]
  要素あり・見逃し: S2-NONE-04   N1  要素=[('name', '山根卓哉', ['D2_shiryo_tejun.txt:45'])]
  要素あり・見逃し: S3-NONE-03   N1  要素=[('name', '森下裕美', ['D3_gijiroku.txt:6'])]
  要素あり・見逃し: S4-NONE-02   N1  要素=[('name', '戸田健司', ['D4_shiyou_v2.txt:25'])]
誤答のうち規則 3b（ANSWER_CONTENT_NOT_IN_QUOTE）で unanchored になった件: 2（S1-ANS-09, S3-ANS-09）
誤検出（正しい ANS で anchored でない）の一覧: 0 件
正しい候補（ANS・NONE）のうち規則 3b で anchored でなくなった件（第 2 ラウンドでは anchored だったかは t31_result.txt の 1 行目以降と比べる）: 0
```

#### T3-2（実機は流し直さず、保存した raw を再照合）— `r3b/t32_recheck.txt`

```
保存された結果: /Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S/artifacts/w16-t3/r3/w14/C/results.jsonl
quote_check のある行: 255
今の QC.check の to_dict が保存と同一: 255
違う行: 0
```

#### T3-3（K653 の byte 一致）— `r3b/t33_k653.txt`

```
rows base 310 new 310
rows where change is allowed (layer 0, FACTUAL, LLM called, not QUESTION_CROSS): 106
  of which actually changed: 90 ; of which carry vera.quote_check: 90
rows outside that set: 204
rows outside that set that changed (pass = 0): 0
```

### 9.13 第 4 ラウンドの規則（事前登録 2026-10-06 02:13:45 +0900）

監査役の第 4 ラウンドの裁定（チケット末尾）に基づく。§9.1〜§9.12 の文は書き換えない。以下は検査データ（`artifacts/w16-t3/r4/cases_r4.jsonl`）とコードより先に書く。予想・目標値は書かない。品詞・見出し語は `typed_edges._tagger`（unidic）の `pos1`・`pos2`・`lemma`。語の一覧は作らない。使う語彙は品詞名と、裁定が名指した `ない`・`ず`・`無い`・`だ`・`です`・`違う`・`どちら`・`どっち`・`か` だけ。

- **R7 否定の有無** `neg(text)`: 解析した語に、`pos1 == 助動詞` かつ `lemma ∈ {ない, ず}`、または `pos1 == 形容詞` かつ `lemma == 無い` の語が 1 つでもあれば真。接頭辞（不・未・非）・名詞は数えない。有無だけで、数は数えない（二重否定も「有り」）。
- **R8 述語の有無** `has_pred(answer)`: 答えに `pos1 ∈ {動詞, 形容詞}` の語がある（`非自立可能` の `ある`・`できる`・`する` も含む）、または `形状詞` の直後に `pos1 == 助動詞` かつ `lemma ∈ {だ, です}` の語がある。名詞＋です（`月曜日です`）は述語なし。
- **R9 極性（規則 3d）**: `has_pred(answer)` が真のときだけ、`neg(answer)` と、実在した（exact／relocated）引用の text ごとの `neg(text)` を比べる。1 つでも違えば `unanchored`、理由 `POLARITY_DIFFERS`。引用が 2 つ以上で極性が割れていれば、答えはどちらかと必ず違うので `unanchored`（勝者を選ばない）。
- **R10 応答の語（規則 3c）**: 応答の語 = `pos1 == 感動詞` の語、および `pos1 == 動詞` かつ `lemma == 違う` の語（裁定が名指しした語）。答えが (a) 要素 0 個、(b) 述語（R8）が `違う` 以外に無い、(c) 内容語（R1′）が `違う` 以外に無い、の 3 つを満たし、かつ応答の語を 1 つ以上含むなら `unanchored`、理由 `YESNO_NOT_CHECKED`。
  - **J-R4-1**: (a)(b)(c) を満たし、応答の語を含まない答え（`そうです。` のように確かめる語が 1 つも無い）も `unanchored`、理由 `NO_CONTENT_TO_CHECK`。裁定の「確かめていないのに anchored」を閉じる狭める側の読み。
  - **J-R4-4**: `違います。` は内容語が `違う` だけで、`違う` が引用に無いと規則 3b が先に `ANSWER_CONTENT_NOT_IN_QUOTE:違う` を立てる。(a)(b)(c) を満たす答えでは、3b の未被覆が `違う` だけのとき、理由は `YESNO_NOT_CHECKED` を優先する（`違う` を応答の語として扱うため。verdict は同じ `unanchored`）。
- **R11 選択の問い**: 問いの解析結果に、表層が `どちら` または `どっち` の語がある、または「`pos1 ∈ {名詞, 接尾辞}` の語の直後に `pos1 == 助詞` で表層 `か` の語」が 2 か所以上あるとき、選択の問いとする。選択の問いでは R3（問いの語を被覆の対象から外す）を使わない。`AかBですか`（`か` が 1 か所）は選択の問いにならない（既知の穴として §9.8 に書く。語を足して直さない）。
- **印の順**（上から最初に当たったもの。既存の 1〜3b は変えない）: 1 unanchored（引用 0／捏造／答えが文字列でない）→ 2 conflict → 3 unanchored（解析不可／要素が引用に無い）→ 3b unanchored（`ANSWER_CONTENT_NOT_IN_QUOTE`）→ **3c unanchored（`YESNO_NOT_CHECKED`／`NO_CONTENT_TO_CHECK`）→ 3d unanchored（`POLARITY_DIFFERS`）** → 4 anchored。3c・3d は anchored を unanchored にするだけ（conflict と先の理由の unanchored は変えない。先の理由があれば上書きしない。J-R4-4 の場合を除く）。`to_dict` の鍵は増やさない。
- 解析できないとき（形態素解析が使えない）は既存の `NAME_TAGGER_UNAVAILABLE` の経路に入り、`unanchored`。
- **検査データ**（`cases_r4.jsonl`、期待は上の規則から手で決める。文は T3-1・W14・cases_r3b・伏せた集合の写しでなく、新しく書く）: 極性の取り違え P 8（`ない`・`ぬ`・`なかった`・形容詞 `ない`・`ではない`・`ません`・割れた 2 引用）／極性の対照 PC 4（否定どうし 2・肯定どうし 1・接頭辞を含む肯定 1）／はい・いいえ Y 4／述語つきの応答 YP 2／選択の取り違え S 4／選択の対照 SC 2／規則どおりの偽の錨なし F 3（誤検出として数える）／その他の対照 O 2。計 29。

### 9.13b 第 4 ラウンドの規則の訂正（J-R4-1 の撤回。記録 2026-10-06 02:15:53 +0900。コードを書いた後の訂正であることを隠さない）

§9.13 の J-R4-1（応答の語を含まない答え `そうです。` を `NO_CONTENT_TO_CHECK` で `unanchored` にする）を実装して関係試験を流したところ、既存の試験 `tests/test_w16t3_quote_check.py::test_no_elements_with_a_real_quote_is_anchored`（答え `そうです`・要素なし → `anchored`）が赤になった。指示書は第 3 ラウンドまでの `tests/test_w16t3_*.py` を触らないと定め、期待の変更は監査役の許可の範囲に限る。裁定 3 の文面（はい／いいえ・ええ・違う 等の応答の語だけ）は `そうです` を名指していない。よって **J-R4-1 を撤回**し、3c は応答の語（感動詞・`違う`）を含む答えだけに掛ける。`そうです` は引き続き要素・述語・内容語が無いまま `anchored` になる（既知の穴。§9.8 に書く）。
- 検査データ: 凍結済みの `cases_r4.jsonl`（直す前の赤の記録に使った）は残し、O-02 の期待だけを `anchored` に変えた `cases_r4b.jsonl` を作って試験の対象にする（`cases_r4b.sha256`）。他の 28 件は同一。
- コードは 3c の条件に「応答の語を含む」を足しただけ（`NO_CONTENT_TO_CHECK` の理由は出さない）。

### 9.13c 規則 3c (c) の訂正（事前登録 2026-10-06 02:34:17 +0900。第 4 ラウンドのレビュー r1 の必須 M1。検査データとコードより先に書く）

§9.13 と §9.13b の文は書き換えない。R10 の (c)「内容語（R1′）が `違う` 以外に無い」は、第 3 ラウンドの裁定 1 の「内容語 = 問いの語の繰り返しを除く」で読む。
- **R10 (c) の読み**: 答えの内容語（R1′）のうち、`違う` 以外のものがすべて **問いの語の繰り返し**（R3 の `_covered(wd, qtoks)` が真）であること。選択の問い（R11）では `qtoks` は空なので、何も繰り返しとはみなさない。`qtoks` は R11 を当てた後のものを使う。
- 帰結: `はい、現金です。`（問い `支払いは現金ですか`）は内容語が問いの語の繰り返しだけなので、応答の語だけの答えとして `unanchored`、理由 `YESNO_NOT_CHECKED`。**引用に同じ語がある正しい答え**（引用 `支払いは現金で行う。`）も同じく `YESNO_NOT_CHECKED` になる。これは規則どおりの偽の錨なしとして数える（誤検出に入れる）。
- 述語を伴う答え（`はい、社内の人が務めます。`）は 3c に当たらない（述語が `違う` 以外にある。(b)）。3d の極性の検査だけに掛かる。極性が合えば `anchored` になる穴が残る。§9.8 で開示する。
- 他の規則・`to_dict`・`reason` の優先順位・R10 の (a)(b)・応答の語の定義・J-R4-1 の撤回は変えない。anchored を unanchored にする方向だけ（広げない）。
- 検査データ: `artifacts/w16-t3/r4/cases_r4c.jsonl`（8 件以上。応答の語＋問いの語の繰り返しだけの誤答、同じ形の正しい答え、対照）。文は新しく書く。コードの前に凍結する（`cases_r4c.sha256`、`cases_r4c_time.txt`）。直す前の赤を `cases_r4c_before.txt` に残す。

### 9.14 第 4 ラウンドの測定（`artifacts/w16-t3/r4/`。出力ファイルから機械で貼った。`r3/`・`r3b/` は上書きしていない）

#### 順序と凍結
- 事前登録 §9.13（日時 `r4/prereg_r4_time.txt` = 2026-10-06 02:13:45 +0900、`prereg_r4.sha256`）→ 検査データ凍結 `cases_r4.jsonl`（29 件、`cases_r4.sha256`、日時 `cases_r4_time.txt` = 2026-10-06 02:14:36 +0900）→ 直す前の赤（`cases_before.txt`）→ コード。コードを書いた後に J-R4-1 を撤回した（§9.13b。`cases_r4b.jsonl`、`cases_r4b.sha256`、日時 `cases_r4b_time.txt` = 2026-10-06 02:15:53 +0900。O-02 の期待だけ違う）。
- 型 × 期待（`cases_r4b.jsonl`）: {"F/unanchored": 3, "O/anchored": 2, "P/unanchored": 8, "PC/anchored": 4, "S/unanchored": 4, "SC/anchored": 2, "Y/unanchored": 4, "YP/anchored": 1, "YP/unanchored": 1}
- 直す前（`cases_before.txt`）の末尾: `21 failed, 10 passed in 0.49s`（赤 21 件 = P 8・Y 4・YP-02・S 4・F 3・O-02 のほか、対照（PC・SC・YP-01・O-01）と凍結の試験は通った）。直した後（`cases_after.txt`）: `31 passed in 0.39s`。
- 3 つの t3 試験＋新規（`t3_tests.txt`）: `134 passed in 1.16s`。

#### T3-1（自作の集合。T3-4 の伏せた集合が本番）— `r4/t31_result.txt`・`r4/t31_diff.txt`・`r4/t31_serve_path.txt`
- T3-1（自作の集合。通っても証拠にならない。T3-4 の伏せた集合が本番）
- (a) LLM 自身の引用を信じる: 検出 0/30 = 0.0%
- (b) Vera の照合:            検出 25/30 = 83.3%
- 上乗せ (b)-(a): 25 件（+83.3 点）
- 誤検出（正しい ANS 20 のうち anchored 以外）: 0/20 = 0.0%
- 型ごとの検出（a / b）:
```
  W1 n=10  a=0  b=10  印={'conflict': 4, 'unanchored': 6}
  W2 n=10  a=0  b=10  印={'unanchored': 10}
  N1 n=5  a=0  b=0  印={'anchored': 5}
  N2 n=5  a=0  b=5  印={'unanchored': 5}
NONE の正しい候補 10 の印の分布: {'unanchored': 10}（誤検出の分母に入れない）
要素 0 個で anchored: 全 60 件のうち 6、誤答のうち 1
取り出せなかった漢数字の並び（skipped）: 0
誤答なのに anchored（見逃し）: 5 = 要素 0 個 1（N1 1） ＋ 要素あり 4（N1 4）
  要素あり・見逃し: S1-NONE-01   N1  要素=[('name', '久保田澄子', ['D1_bihin_kitei.txt:5'])]
  要素あり・見逃し: S2-NONE-04   N1  要素=[('name', '山根卓哉', ['D2_shiryo_tejun.txt:45'])]
  要素あり・見逃し: S3-NONE-03   N1  要素=[('name', '森下裕美', ['D3_gijiroku.txt:6'])]
  要素あり・見逃し: S4-NONE-02   N1  要素=[('name', '戸田健司', ['D4_shiyou_v2.txt:25'])]
誤答のうち規則 3b（ANSWER_CONTENT_NOT_IN_QUOTE）で unanchored になった件: 2（S1-ANS-09, S3-ANS-09）
誤検出（正しい ANS で anchored でない）の一覧: 0 件
正しい候補（ANS・NONE）のうち規則 3b で anchored でなくなった件（第 2 ラウンドでは anchored だったかは t31_result.txt の 1 行目以降と比べる）: 0
```
（上の貼り付けは第 4 ラウンドの `paste_docs_r4.py` が先頭 6 行で切れていたのを、`paste_docs_r4c.py` が `r4/t31_result.txt` の「候補ごとの印」の直前まで補った。）
- 第 3 ラウンド（`r3b/t31_result.txt`）との印の変化（全件。`t31_diff.txt`）:

```
S1-ANS-05 W1 wrong=True anchored->unanchored reason=POLARITY_DIFFERS 引用=通常の使用による摩耗や破損について、使用者に弁償を求めない。
S2-ANS-07 W1 wrong=True anchored->unanchored reason=POLARITY_DIFFERS 引用=返却を求めない依頼者には、試料を返さない。
S3-ANS-05 W1 wrong=True anchored->unanchored reason=POLARITY_DIFFERS 引用=小雨のときは、防災訓練を中止しない。
S4-ANS-07 W1 wrong=True anchored->unanchored reason=POLARITY_DIFFERS 引用=2回目の延長は、認めない。
印か reason が変わった行: 4 / 60
誤答で anchored -> 非 anchored になった数: 4
正しい ANS（wrong=false, cat=ANS）で anchored -> 非 anchored（偽の錨なしの増加）: 0
anchored 以外 -> anchored（あってはならない）: 0
```
- serve の経路（`t31_serve_path.txt` の 1 行目）: serve の経路（FusionConfig + 偽の LLM）に 60 候補を通した: 同じ 55、違う 0、LLM を呼ばなかった（記録が答えた）5。変更前（`t31_serve_path_before.txt`）: serve の経路（FusionConfig + 偽の LLM）に 60 候補を通した: 同じ 55、違う 0、LLM を呼ばなかった（記録が答えた）5。第 3 ラウンドの 60 件「同じ 60」から「記録が答えた 5」に変わったのは、統合した W16-t2 で記録が `QUESTION_CROSS` で答える問いが増えたため（T3 の規則の効果ではない。S1-ANS-04/08/09・S3-ANS-03/04）。

#### T3-2（実機は流し直さず、保存した raw を再照合）— `r4/t32_recheck.txt`
```
保存された結果: /Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S/artifacts/w16-t3/r3/w14/C/results.jsonl
quote_check のある行: 255
今の QC.check の to_dict が保存と同一: 252
違う行: 3
S2-ANS-06 rep=0 cat=ANS anchored -> unanchored reason=YESNO_NOT_CHECKED 答え=いいえ 引用=1人だけで確認した結果は、依頼者へ送らない。 問い=1人だけで確認した結果を依頼者へ送りますか。
S3-ANS-07 rep=0 cat=ANS anchored -> unanchored reason=YESNO_NOT_CHECKED 答え=いいえ 引用=役員でない会員には、議事録を配らない。 問い=役員でない会員に議事録を配りますか。
S4-ANS-05 rep=0 cat=ANS anchored -> unanchored reason=POLARITY_DIFFERS 答え=設けない 引用=返却が遅れた利用者には、延滞の罰則を設ける。 問い=予約の取り消しについて、利用者に罰則を設けますか。
保存の印の分布（255 行すべて）: {'anchored': 144, 'unanchored': 108, 'conflict': 3}
今の印の分布（255 行すべて）: {'anchored': 141, 'unanchored': 111, 'conflict': 3}
anchored 以外 -> anchored: 0
reason の分布（今）: {None: 251, 'YESNO_NOT_CHECKED': 2, 'POLARITY_DIFFERS': 1, 'ANSWER_CONTENT_NOT_IN_QUOTE:行わ': 1}
```

#### T3-3（K653 の byte 一致。基線は dev `a7507b3` の写し）— `r4/t33_k653.txt`
```
310 /private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t3/r4work/serve_base_a7507b3.jsonl
     310 /private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t3/r4work/serve_new.r4.jsonl
     620 total
rows base 310 new 310
rows where change is allowed (layer 0, FACTUAL, LLM called, not QUESTION_CROSS): 87
  of which actually changed: 71 ; of which carry vera.quote_check: 71
rows outside that set: 223
rows outside that set that changed (pass = 0): 0
```
- 基線を基点 `3a1677c` から dev `a7507b3` に替えた理由: T2 の merge で serve の出力が変わり、古い基線では「外」の 35 行が変わって見える。基線は `git archive a7507b3` の写しで取り直した（中間職の写しと `cmp` 一致）。
- 第 3 ラウンド後の写し（`serve_head.jsonl`）と今回の 310 行を比べると、違う行は 0（`r4/t33_verdict_changes.txt`）。

#### 関係試験（18 ファイル＋新規）
- 変更前（`related_before.txt`）: `1 failed, 367 passed in 67.94s (0:01:07)`（落ちた 1 件は `test_w10f05_cli.py` の 154 行目。§9.7 の第 4 ラウンドの項）。
- 変更後（`related_after.txt`）: `399 passed in 67.43s (0:01:07)`。新しい失敗 0（`related_new_failures.txt` が 0 byte）。
- 監査役の「関係テスト 236 passed」の集合には `test_w10f05_cli.py` が入っていなかったと見られる（上の 18 ファイルでは変更前に 1 件落ちた）。

### 9.15 第 4 ラウンドのレビュー M1・M2 への対応（`artifacts/w16-t3/r4c/`。出力ファイルから機械で貼った。`r4/` は上書きしていない）

#### 順序と凍結（M1）
- 事前登録 §9.13c（日時 `r4/prereg_r4c_time.txt` = 2026-10-06 02:34:17 +0900、`r4/prereg_r4c.sha256`）→ 検査データ凍結 `r4/cases_r4c.jsonl`（11 件、`cases_r4c.sha256`、日時 `r4/cases_r4c_time.txt` = 2026-10-06 02:34:35 +0900）→ 直す前の赤（`r4/cases_r4c_before.txt`）→ コード（`quote_check.py` の 3c の (c) だけ）。
- 型 × 期待: {"F/unanchored": 2, "YC/anchored": 3, "YC/unanchored": 1, "YQ/unanchored": 5}
- 直す前の末尾: `7 failed, 6 passed, 31 deselected in 0.38s`。直した後（`r4/cases_r4c_after.txt`、cases_r4b も含む）: `44 passed in 0.45s`。3 つの t3 試験＋新規（`r4/t3_tests_c.txt`）: `147 passed in 1.19s`。
- コードの前後の mtime（ナノ秒）は報告に記録した（赤の記録 < `quote_check.py`）。

#### T3-1（`r4c/t31_result.txt`）
- `t31_result.txt`・`t31_result.json`・`t31_serve_path.txt` を `r4/` のものと比べると、`t31_result.txt` は 同一（cmp 一致）、`t31_result.json` は 同一（cmp 一致）、`t31_serve_path.txt` は 同一（cmp 一致）。よって 60 件の印・誤検出 0/20・検出 25/30 は r4 から変わらない（偽の錨なしの増加 0）。
```
T3-1（自作の集合。通っても証拠にならない。T3-4 の伏せた集合が本番）
(a) LLM 自身の引用を信じる: 検出 0/30 = 0.0%
(b) Vera の照合:            検出 25/30 = 83.3%
上乗せ (b)-(a): 25 件（+83.3 点）
誤検出（正しい ANS 20 のうち anchored 以外）: 0/20 = 0.0%
型ごとの検出（a / b）:
  W1 n=10  a=0  b=10  印={'conflict': 4, 'unanchored': 6}
  W2 n=10  a=0  b=10  印={'unanchored': 10}
  N1 n=5  a=0  b=0  印={'anchored': 5}
  N2 n=5  a=0  b=5  印={'unanchored': 5}
NONE の正しい候補 10 の印の分布: {'unanchored': 10}（誤検出の分母に入れない）
要素 0 個で anchored: 全 60 件のうち 6、誤答のうち 1
取り出せなかった漢数字の並び（skipped）: 0
誤答なのに anchored（見逃し）: 5 = 要素 0 個 1（N1 1） ＋ 要素あり 4（N1 4）
  要素あり・見逃し: S1-NONE-01   N1  要素=[('name', '久保田澄子', ['D1_bihin_kitei.txt:5'])]
  要素あり・見逃し: S2-NONE-04   N1  要素=[('name', '山根卓哉', ['D2_shiryo_tejun.txt:45'])]
  要素あり・見逃し: S3-NONE-03   N1  要素=[('name', '森下裕美', ['D3_gijiroku.txt:6'])]
  要素あり・見逃し: S4-NONE-02   N1  要素=[('name', '戸田健司', ['D4_shiyou_v2.txt:25'])]
誤答のうち規則 3b（ANSWER_CONTENT_NOT_IN_QUOTE）で unanchored になった件: 2（S1-ANS-09, S3-ANS-09）
誤検出（正しい ANS で anchored でない）の一覧: 0 件
正しい候補（ANS・NONE）のうち規則 3b で anchored でなくなった件（第 2 ラウンドでは anchored だったかは t31_result.txt の 1 行目以降と比べる）: 0
```

#### T3-2（保存した raw の再照合、`r4c/t32_recheck.txt`）
- `r4/t32_recheck.txt` と 同一（cmp 一致）。255 行のうち違う 3（S2-ANS-06・S3-ANS-07・S4-ANS-05）は r4 と同じ。「anchored 以外 -> anchored」は 0。
- 3 行の分類（W14 の正解 `benchmarks/public_v1` の `answer` を読み取りで引いた）: S2-ANS-06（正解 `送らない`）・S3-ANS-07（正解 `配らない`）は答え `いいえ` が正しく、`YESNO_NOT_CHECKED` は規則どおりの偽の錨なし。S4-ANS-05（正解 `設けない`）は答えが正しいが、引用は distractor の行（`延滞の罰則を設ける`）で答えと逆のことを言っており、`unanchored`（`POLARITY_DIFFERS`）は正しい検出（以前の `anchored` は確かめていないのに anchored だった）。

#### T3-3（K653、`r4c/t33_k653.txt`）
```
310 /private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t3/r4work/serve_base_a7507b3.jsonl
     310 /private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w16t3/r4work/serve_new.r4c.jsonl
     620 total
rows base 310 new 310
rows where change is allowed (layer 0, FACTUAL, LLM called, not QUESTION_CROSS): 87
  of which actually changed: 71 ; of which carry vera.quote_check: 71
rows outside that set: 223
rows outside that set that changed (pass = 0): 0
```
- 今回の serve の 310 行は r4 の出力と 同一（`cmp`）（この句はスクリプトの固定の文言で、`cmp` は手で確かめた。J-R4c-3）。

#### 関係試験（18 ファイル＋新規、`r4c/related_after.txt`）
- `412 passed in 65.23s (0:01:05)`

#### 開示（レビュー任意 2・3）
- 検査データ F-01 の文 `役員でない会員には、議事録を配る。` は T3-1 の `items.jsonl` にある文と同一（指示書が F 型の例として出した文のため）。
- 検査データ YC-02 の文は、中間職が第 4 ラウンド r1 の指示に例として書いた文と同一。
- 凍結版 `cases_r4.jsonl` の型 × 期待は O-02 だけが `unanchored`（`NO_CONTENT_TO_CHECK`）。`cases_r4b.jsonl`（試験の対象）は O-02 が `anchored`。取り違えないこと。

### 9.16 第 5 ラウンドの規則（事前登録 2026-10-06 02:53:39 +0900。監査役の裁定 第 5 ラウンド 2）

監査役の第 5 ラウンドの裁定（チケット末尾）に基づく。§9.1〜§9.15 の文は書き換えない。以下は検査データ（`artifacts/w16-t3/r5/cases_r5.jsonl`）とコードより先に書く。予想・目標値は書かない。

- **R12（K654）確かめる中身の無い答え**: 規則 3b の準備の中で、`words` = 答えの内容語（R1′。`_content_words(answer, a_dn)`）、`qtoks` = R11 を当てた後の問いの解析（選択の問いでは空）、`rest` = `words` のうち `_covered(wd, qtoks)` でないもの。**答えの要素が空で `rest` も空**のとき:
  - (i) `words` が空でなければ、`words` のすべて（問いの語の繰り返しを含む）を被覆の対象に戻す。各語が実在引用の解析で `_covered` でなければ `uncovered` に足す。→ 既存の 3b の理由 `ANSWER_CONTENT_NOT_IN_QUOTE:<語>`。
  - (ii) `words` が空なら `no_content` を立てる。→ 新しい規則 3e: `unanchored`、理由 `NO_CONTENT_TO_CHECK`。
  - 述語のある答えは今までどおり 3d（極性）にも掛かる（条件は変えない）。`question=None` では `qtoks` が空なので `rest == words` で、(i) は起きず (ii) だけが起きうる。
- **印の順**（上から最初に当たったもの。1〜3c は変えない）: 1 unanchored（引用 0／捏造／答えが文字列でない）→ 2 conflict → 3 unanchored（解析不可／要素が引用に無い）→ 3c `YESNO_NOT_CHECKED` → 3b `ANSWER_CONTENT_NOT_IN_QUOTE`（R12 (i) を含む）→ **3e `NO_CONTENT_TO_CHECK`（R12 (ii)。新）** → 3d `POLARITY_DIFFERS` → 4 anchored。先に付いた理由は上書きしない。`to_dict` の鍵は増やさない。anchored を unanchored にする方向だけで、conflict と既存の理由の unanchored は変わらない。
- **検査データ**（`cases_r5.jsonl`、期待は上の規則から手で決める。文は T3-1・W14・既存の `cases_r4*.jsonl`・指示書の例の写しでなく、新しく書く）: `SO`（そうです型）3 以上・`QO`（問いの語だけ）3 以上・`PR`（述語つきの言い直し。誤答 2 以上と正しい言い直し 2 以上）4 以上・`C`（対照）2 以上。任意で `H`（閉じない型）と `F`（偽の錨なし）。合計 12 以上。

判断（J-R5-*）:
- **J-R5-1（裁定 3 との衝突）**: 裁定 2 は「R28（そうです。）・E07／G13（はい、支払います。）の型が閉じる」と求め、裁定 3 は「ほかの既存の試験の期待は変えない」と定める。ところが第 4 ラウンドの凍結データには、この 2 つの型を既知の穴として `anchored` と書いた項目がある（`cases_r4b.jsonl` の O-02 = `そうです。`、`cases_r4c.jsonl` の YC-02 = `はい、社内の人が務めます。`）。K654 を入れるとこの 2 件は必ず赤になる。裁定 2 の目的を優先し、期待を強める側（anchored → unanchored）だけ替える。凍結済みのファイルは書き換えない。O-02 は `tests/test_w16t3_r4.py` の読み先を `cases_r4b.jsonl` から `cases_r4.jsonl`（最初に凍結した版。O-02 の期待は `unanchored`／`NO_CONTENT_TO_CHECK`）に戻す。YC-02 は新しいファイル `r5/cases_r4c_r5.jsonl`（`cases_r4c.jsonl` の YC-02 の `expect`・`expect_reason_prefix`・`note` だけ替えた写し）を読む。監査役への申し送り: この 2 件の期待を替えたことを確認してほしい。
- **J-R5-2**: `そう（です）` は 3c の応答の語に入れない（入れると `そうです` が `YESNO_NOT_CHECKED` になり、裁定 3 の改訂後の期待 `NO_CONTENT_TO_CHECK` と食い違う）。
- **J-R5-3**: `その通りです。` は `通り` が名詞（普通名詞）で内容語 1 個なので、R12 (i) → 3b に落ちる（引用に `通り` があれば anchored）。裁定が `NO_CONTENT_TO_CHECK` の例に挙げる文との違いとして開示する。語の一覧は作らない。
- **J-R5-4**: `できる`・`ある`・`する` など `非自立可能` の述語だけの答え（`できません。`・`あります。`）は内容語 0 個なので、正しい答えでも `NO_CONTENT_TO_CHECK`（偽の錨なし。誤検出として数える）。
- **J-R5-5**: R2（名詞と動詞の表層が等しければ被覆）は変えない。引用に同じ表層の名詞があれば `はい、支払います。` は anchored のまま。答えが問いの要の語を落とす言い直し（答えに無い問いの語は求めない）も閉じない。

### 9.16b SO-03 の理由の訂正（記録 2026-10-06 02:56:08 +0900。コードを書いた後の訂正であることを隠さない）

`cases_r5.jsonl`（凍結 2026-10-06 02:55:10 +0900）の SO-03（答え `左様です。`）の期待を、私は §9.16 の規則から `NO_CONTENT_TO_CHECK` と決めたが、`左様` は形状詞で、R1′（§9.9 R1）の内容語に **入る**（`pos1 ∈ {名詞, 動詞, 形容詞, 形状詞, …}`）。内容語は 1 個で、問いの語でないので R12 でなく既存の 3b が動き、理由は `ANSWER_CONTENT_NOT_IN_QUOTE:左様` になる（印は `unanchored` で期待どおり）。期待を決めるときに内容語の定義を読み違えた（品詞は見たが、形状詞が内容語かを §9.9 で確かめなかった）。`cases_r5.jsonl` は書き換えず、SO-03 の `expect_reason_prefix` と `note` だけ替えた `cases_r5b.jsonl`（`make_cases_r5b.py`。他の 19 件は byte 一致）を凍結し、`tests/test_w16t3_r5.py` はこれを読む（凍結の検査は両方）。SO の「内容語 0 個」の型は SO-01・SO-02・SO-04 の 3 件。事前登録の順序: 事前登録 → cases_r5 凍結 → 試験の変更と赤 → コード → **cases_r5b の凍結（コードより後）**。

### 9.16c 第 5 ラウンドのレビュー r1 M2 への対応（記録 2026-10-06。§9.16 の文は書き換えず、ここで訂正する。コードは変えていない）

- **§9.16 の一文の訂正**: §9.16（印の順の行）の「anchored を unanchored にする方向だけで、conflict と既存の理由の unanchored は変わらない」は、**verdict については正しいが reason については偽**。印の順で 3e（`NO_CONTENT_TO_CHECK`）が 3d（`POLARITY_DIFFERS`）より先なので、述語が `非自立可能`（ある・できる）だけで、極性が引用と食い違う答えは、第 4 ラウンドの `POLARITY_DIFFERS` から `NO_CONTENT_TO_CHECK` に reason が変わる（verdict は unanchored のまま。`polarity` の欄も計算される）。例（レビュー r1 の実測。第 4 ラウンドの写し OLD と今のコード NEW）: `ありません。`（問い `予備の鍵はありますか`）・`いいえ、ありません。`・`できません。`（問い `会員は当日予約できますか`）・`できません。`（問い なし）は OLD `POLARITY_DIFFERS` → NEW `NO_CONTENT_TO_CHECK`。`予約できません。` は内容語 `予約` があるので R12 は動かず、OLD・NEW とも `POLARITY_DIFFERS`。裁定は reason の優先を定めていないので、指示書の印の順のままにした。
- **測定集合には該当行が無かった**: T3-1（60 件）・T3-2 の再照合（255 行）・K653（310 行）で reason だけが変わった行は 0（`artifacts/w16-t3/r5/t31_diff.txt`・`t32_recheck.txt`・`t33_k653.txt`）。だから測定からは気づけなかった。この挙動は `tests/test_w16t3_r5.py::test_r12_no_content_reason_precedes_polarity`（コードの後に書いた特性の試験。凍結データではない）で固定した。
- **SO-03 は R12 の項目ではない**: `左様です。`（SO-03）は直す前（第 4 ラウンドの写し）も `unanchored`（`ANSWER_CONTENT_NOT_IN_QUOTE:左様`。`左様` は形状詞で内容語。§9.16b）で、R12 で印も理由も変わらない。`cases_before.txt` の SO-03 の赤は reason の assert だけで、R12 の証拠ではない。R12 で anchored → unanchored に変わった SO は SO-01・SO-02・SO-04 の 3 件。`test_cases_r5_counts` は SO-03 を id で除いて数える。

### 9.17 第 5 ラウンドの測定（`artifacts/w16-t3/r5/`。出力ファイルから機械で貼った。`r3/`〜`r4c/` は上書きしていない）

#### 順序と凍結
```
prereg: 2026-10-06 02:53:39 +0900
cases_r5/cases_r4c_r5: 2026-10-06 02:55:10 +0900
cases_r5b: 2026-10-06 02:56:08 +0900
```
mtime（`mtime_order.txt`。事前登録 → cases_r5 → 直す前の赤 → quote_check.py）:
```
1791222819.965084017 /Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S/artifacts/w16-t3/r5/prereg_r5.txt
1791222910.610734622 /Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S/artifacts/w16-t3/r5/cases_r5.jsonl
1791222925.911996641 /Users/motonisihikoudai/Projects/vera-impl/wt/W16-t3-S/artifacts/w16-t3/r5/cases_before.txt
1791222937.969615250 verantyx/quote_check.py
```
凍結 sha（`cases_r5.sha256`・`cases_r5b.sha256`）:
```
dd27c18a662c8c4b068010943ff9f62e236060769280182a24c3080ff9b9adff  cases_r5.jsonl
671e94c980eff8de07d60a10e7492db295d4772f2316d88514e1212ddea5f5da  cases_r4c_r5.jsonl
9833fc4acd28409f7cb9dd2b54911497cf56ef6ea3fbe0a556ea5b6cbb7293ad  cases_r5b.jsonl
```
#### 検査データ（cases_r5b。20 件）の型 × 期待
```
{"C/anchored": 3, "C/unanchored": 1, "F/unanchored": 1, "H/anchored": 2, "H/unanchored": 1, "PR/anchored": 2, "PR/unanchored": 3, "QO/unanchored": 3, "SO/unanchored": 4}
```
#### 直す前／後（`cases_before.txt`・`cases_after.txt`。w16t3_r5・w16t3_r4・w16t3_quote_check）
```
直す前:
FAILED tests/test_w16t3_r5.py::test_case_r5[SO-01] - AssertionError: ({'verdi...
FAILED tests/test_w16t3_r5.py::test_case_r5[SO-02] - AssertionError: ({'verdi...
FAILED tests/test_w16t3_r5.py::test_case_r5[SO-03] - AssertionError: {'verdic...
FAILED tests/test_w16t3_r5.py::test_case_r5[SO-04] - AssertionError: ({'verdi...
FAILED tests/test_w16t3_r5.py::test_case_r5[QO-01] - AssertionError: ({'verdi...
FAILED tests/test_w16t3_r5.py::test_case_r5[QO-02] - AssertionError: ({'verdi...
FAILED tests/test_w16t3_r5.py::test_case_r5[QO-03] - AssertionError: ({'verdi...
FAILED tests/test_w16t3_r5.py::test_case_r5[PR-01] - AssertionError: ({'verdi...
FAILED tests/test_w16t3_r5.py::test_case_r5[PR-02] - AssertionError: ({'verdi...
FAILED tests/test_w16t3_r5.py::test_case_r5[PR-03] - AssertionError: ({'verdi...
FAILED tests/test_w16t3_r5.py::test_case_r5[F-01] - AssertionError: ({'verdic...
FAILED tests/test_w16t3_r4.py::test_case[O-02] - AssertionError: ({'verdict':...
FAILED tests/test_w16t3_r4.py::test_case_r4c[YC-02] - AssertionError: ({'verd...
FAILED tests/test_w16t3_quote_check.py::test_no_elements_with_a_real_quote_is_not_anchored
14 failed, 77 passed in 0.82s
直した後:
91 passed in 0.73s
```
#### w16t3 の試験（`t3_tests.txt`）
```
169 passed in 1.28s
```
#### T3-1（`t31_result.txt` の先頭・`t31_diff.txt` 全文）
```
T3-1（自作の集合。通っても証拠にならない。T3-4 の伏せた集合が本番）
(a) LLM 自身の引用を信じる: 検出 0/30 = 0.0%
(b) Vera の照合:            検出 25/30 = 83.3%
上乗せ (b)-(a): 25 件（+83.3 点）
誤検出（正しい ANS 20 のうち anchored 以外）: 0/20 = 0.0%
型ごとの検出（a / b）:
--- t31_diff.txt ---
印か reason が変わった行: 0 / 60
誤答で anchored -> 非 anchored になった数: 0
正しい ANS（wrong=false, cat=ANS）で anchored -> 非 anchored（偽の錨なしの増加）: 0
anchored 以外 -> anchored（あってはならない）: 0
```
#### T3-2（保存した raw の再照合。`t32_recheck.txt`）
```
今の QC.check の to_dict が保存と同一: 251
違う行: 4
S2-ANS-06 rep=0 cat=ANS anchored -> unanchored reason=YESNO_NOT_CHECKED 答え=いいえ 引用=1人だけで確認した結果は、依頼者へ送らない。 問い=1人だけで確認した結果を依頼者へ送りますか。
S3-ANS-07 rep=0 cat=ANS anchored -> unanchored reason=YESNO_NOT_CHECKED 答え=いいえ 引用=役員でない会員には、議事録を配らない。 問い=役員でない会員に議事録を配りますか。
S4-ANS-05 rep=0 cat=ANS anchored -> unanchored reason=POLARITY_DIFFERS 答え=設けない 引用=返却が遅れた利用者には、延滞の罰則を設ける。 問い=予約の取り消しについて、利用者に罰則を設けますか。
S4-ANS-06 rep=0 cat=ANS anchored -> unanchored reason=NO_CONTENT_TO_CHECK 答え=できません 引用=利用者カードを持たない者は、予約できない。 問い=利用者カードを持たない一般の利用者は、予約できますか。
保存の印の分布（255 行すべて）: {'anchored': 144, 'unanchored': 108, 'conflict': 3}
今の印の分布（255 行すべて）: {'anchored': 140, 'unanchored': 112, 'conflict': 3}
anchored 以外 -> anchored: 0
reason の分布（今）: {None: 250, 'YESNO_NOT_CHECKED': 2, 'POLARITY_DIFFERS': 1, 'NO_CONTENT_TO_CHECK': 1, 'ANSWER_CONTENT_NOT_IN_QUOTE:行わ': 1}
```
r4c との差（`t32_recheck_vs_r4c.diff`）:
```
3,4c3,4
< 今の QC.check の to_dict が保存と同一: 252
< 違う行: 3
---
> 今の QC.check の to_dict が保存と同一: 251
> 違う行: 4
7a8
> S4-ANS-06 rep=0 cat=ANS anchored -> unanchored reason=NO_CONTENT_TO_CHECK 答え=できません 引用=利用者カードを持たない者は、予約できない。 問い=利用者カードを持たない一般の利用者は、予約できますか。
9c10
< 今の印の分布（255 行すべて）: {'anchored': 141, 'unanchored': 111, 'conflict': 3}
---
> 今の印の分布（255 行すべて）: {'anchored': 140, 'unanchored': 112, 'conflict': 3}
11c12
< reason の分布（今）: {None: 251, 'YESNO_NOT_CHECKED': 2, 'POLARITY_DIFFERS': 1, 'ANSWER_CONTENT_NOT_IN_QUOTE:行わ': 1}
---
> reason の分布（今）: {None: 250, 'YESNO_NOT_CHECKED': 2, 'POLARITY_DIFFERS': 1, 'NO_CONTENT_TO_CHECK': 1, 'ANSWER_CONTENT_NOT_IN_QUOTE:行わ': 1}
```
r4c から増えた行（1 行）の分類（W14 公開バンクの正解 `answer` を引いた。読み取りのみ）:
- `S4-ANS-06` 答え `できません`、W14 の正解 `予約できない`（distractors [{"doc": "D4_shiyou_v2.txt", "line": 20, "value": "予約できる"}]）。答えは正解と同じ内容（否定）で正しい → **正しい答えの偽の錨なし**（J-R5-4。分類は私が正解の文字列を読んで判断した）。
#### K653（`t33_k653.txt`・`t33_vs_r4c.txt`）
```
310 $SC/r4work/serve_base_a7507b3.jsonl
     310 $SC/r5work/serve_new.r5.jsonl
     620 total
rows base 310 new 310
rows where change is allowed (layer 0, FACTUAL, LLM called, not QUESTION_CROSS): 87
  of which actually changed: 71 ; of which carry vera.quote_check: 71
rows outside that set: 223
rows outside that set that changed (pass = 0): 0
--- t33_vs_r4c.txt ---
違う行: 0 / 310
quote_check・本文の最後の 1 行以外も違う行: 0
```
#### 関係試験（`related_before.txt`・`related_after.txt`・`related_new_failures.txt`）
```
変更前: 412 passed in 65.17s (0:01:05)
変更後: 434 passed in 62.30s (0:01:02)
新しい失敗: 0 byte
```
