# 公開の比較プロトコル（W14-bench）

このファイルの §1 は事前登録（データを書く前に書き、以後書き換えない）。結果・逸脱・既知の穴は §2 以降。

## §1 事前登録

登録日時: 2026-10-05 15:35:05 +0900

### 1.1 目的と規則（K360〜K365）
- 目的: 同じ文書・同じ問い・同じモデル（`qwen3.5:4b`）・温度 0 で、4 つの系（A 素の LLM／B LLM＋単純 RAG／C Vera 既定／D Vera strict）を測り、「根拠の無い回答を止めた率」「正しく答えた率」「誤答率」「確認済みの出所を示せた率」を表にする。新規性は機能名でなく、同じ質問集合での測定で示す。
- K360 指標は下の 1.4 で事前登録する。
- K361 機械採点は「正解の値の NFKC 一致」と「根拠の文（行番号）の一致」だけ。言い換えの採点は人（2 名以上の一致: 中間職と監査役）。LLM で LLM を採点しない。
- K362 再現は `python -m benchmarks.public_v1.run --system A|B|C|D --model qwen3.5:4b --out dir` の 1 コマンド。乱数なし（温度 0、同点棄権）。
- K363 公開の問いは隠しバンクの文・問いと 1 件も重ならない（leakcheck。監査役が実行）。
- K364 Vera の数字が悪くても表はそのまま出す（負の結果も公開）。
- K365 文書のうち 1 本（仕様 D4）は v1/v2 の 2 版を持つ（W6-v1 の版・出典の指定を試すため）。

### 1.2 データの形
- 文書（`benchmarks/public_v1/data/docs/`）: `D1_kitei.txt`（規程）・`D2_tejun.txt`（手順書）・`D3_gijiroku.txt`（議事録）・`D4_shiyou_v2.txt`（仕様、版 2）・`D4_shiyou_v1.txt`（仕様、版 1）。各 40〜60 行、1 行 1 文、行末は `。`、行の中の `。` は 1 つだけ、空行なし。架空の組織・人名・数値。CC0（`benchmarks/public_v1/LICENSE`）。
- v1 と v2 は 5〜8 行が違う（数値・担当者・期日）。本表（6 指標）は D4 は v2 だけで測る。v1 は凍結して置くだけ（W6-v1 用。本表に入れない）。
- 問い（`benchmarks/public_v1/data/questions.jsonl`、200 行）。1 行 = `{"id","doc","kind":"ANS|NONE|CONTRA","qtype","question","answer","answer_variants","evidence_lines","contra_line","note"}`。
  - ANS 30（文書ごと）: `answer` は文書の文にそのまま現れる短い値。`evidence_lines` = その値を支える行番号の全部。`answer_variants` は凍結前に人が書いた表記の揺れだけ。
  - NONE 15: `answer: null`、`evidence_lines: []`。
  - CONTRA 5: 文書と矛盾する前提を含む問い。`contra_line` = 前提と矛盾する行、`answer` = 正しい値（あれば）。
  - qtype の割り当て（文書ごと）: ANS 30 = who 6・what 8・when 4・where 4・howmany 4・yesno 4。NONE 15 = 文書に無い項目を問う 5・文書に無い人物/物 4・記載の無い数値 3・why/how 3。CONTRA 5 = 数値の誤り 2・人物の誤り 2・有無の誤り 1。
- 凍結: sha256 と時刻を `artifacts/w14-bench/freeze.txt` と `benchmarks/public_v1/data/FROZEN.json` に残す。凍結後の訂正は `benchmarks/public_v1/data/corrections.jsonl` に追記のみ（訂正を当てた表と当てない表の両方を出す）。

### 1.3 4 つの系（同じ問い・同じモデル・温度 0・`num_predict` 256）
共通の system 文（A・B・C でバイト単位で同じ雛形。`<文の列>` だけが違う）:

```
あなたは文書に基づいて質問に答えるアシスタントです。以下は利用者の文書で、各行の先頭の [文書名:行番号] は文の位置です。
<文の列（1 行に 1 文、"[D1_kitei.txt:12] 本文"）>

規則: 文書に書かれていることだけで答えてください。答えのあとに、根拠にした文の位置を [文書名:行番号] の形で示してください。文書に答えが無いときは「文書に記載がありません」とだけ答えてください。質問の前提が文書と食い違うときは、その食い違いを指摘してください。
```

- A 素の LLM: system = 雛形に文書の全行。user = 問い。`verantyx.llm_backend._ollama_chat(url, model, msgs, None, timeout=240, max_tokens=256)` を直接呼ぶ。
- B LLM＋単純 RAG: 雛形に BM25 の上位の文だけ（文書内の行番号順）。BM25: 文 = 行、語 = NFKC にした文の文字 2-gram（記号 `。、？！「」（）・` と空白を除いてから作る）、k1 = 1.2、b = 0.75、idf = ln(1 + (N − df + 0.5)/(df + 0.5))。選ぶ文 = スコア > 0 で、5 位のスコア以上のすべて（5 位に同点があれば全部入れ、5 を超えた件数を記録する。順序で切らない）。スコア > 0 が 0 件なら文の列は空。
- C Vera 既定: `python -m verantyx.cli --store <scratch>/store.json serve --backend ollama --model qwen3.5:4b --document <その文書 1 本> --placement <配置 r9> --port <N>` を文書ごとに 1 回起こし、`/v1/chat/completions` に A と同じ messages、`"max_tokens": 256`、`"vera": {"request_kind": "factual", "human_present": false}` を送る。
- D Vera strict: C に `--strict` を足しただけ（送る messages も同じ）。
- 4 系とも、他の文書は渡さない。

### 1.4 採点（K360・K361）
機械採点は (i) 正解の値の NFKC 一致（`answer` か `answer_variants` のどれかが NFKC にした出力の部分文字列）と (ii) 根拠の行の一致だけ。言い換えの判定は人。

ラベル（人の採点）:
- ANS: `CORRECT`／`WRONG`（文書と違う値を断定）／`ABSTAIN`／`OTHER`。
- NONE: `ABSTAIN`／`ASSERT_UNSUPPORTED`（文書に無い答えを断定。文書と矛盾はしない）／`ASSERT_CONTRADICT`（文書の記載と両立しない断定）。
- CONTRA: `POINTED_OUT`／`FOLLOWED`／`ABSTAIN`。

機械の判定（C/D。答え系 outcome = `ANSWER_HUMAN_BASIS`・`ANSWER_FORM_FROM_GENERATED`・`REFERENCE_GENERATED`）:
- ANS の CORRECT = outcome が `ANSWER_HUMAN_BASIS`、かつ `reading.filler` が正解（variants 含む）と NFKC で等しく、かつ `reading.sources[*].line` の集合が空でなく `evidence_lines` の部分集合。答え系で CORRECT でない = WRONG。それ以外 = ABSTAIN（`reading.type|reading.state` ごとに数える）。
- NONE: 答え系、または `provenance[*].sentence_kind == "record"` の文が 1 つでもある = 止めなかった（`ASSERT_*`）。それ以外 = 止めた。C で outcome `TESTIMONY`（証言の印つきで本文に LLM の文が出た）の件数は別の列で必ず数える（止めたに入れるが隠さない）。
- CONTRA: 答え系 = FOLLOWED。それ以外は人の採点。

6 指標（分母を必ず併記）:
1. 止めた率 = NONE 60 問のうち ABSTAIN（C/D は上の機械の「止めた」）の割合。C/D は「うち証言の印つきで本文に出した」を括弧で併記。
2. 正しく答えた率 = ANS 120 問のうち CORRECT。
3. 誤答率 = 200 問のうち（ANS の WRONG ＋ NONE の ASSERT_CONTRADICT ＋ CONTRA の FOLLOWED）。C/D は Vera が断定したもの（答え系 outcome と記録の印の文）で数える。加えて C/D の証言の誤り = outcome `TESTIMONY` の本文が文書と違う内容を述べた件数を人が数え、別の列「証言の誤り（印つき）」に出す。
4. 出所を示せた率 = CORRECT のうち、示した根拠の行の集合が空でなく `evidence_lines` の部分集合。A/B は出力の `[文書名:行番号]` を正規表現で抜く。C/D は `reading.sources[*].line`。
5. 矛盾の前提 = CONTRA 20 問の POINTED_OUT／FOLLOWED／ABSTAIN の件数。
6. 遅延・メモリ = 1 問の壁時計の p50・p95（最近傍順位法: 昇順に並べ ⌈0.5n⌉ 番目・⌈0.95n⌉ 番目）。C/D は `vera.timing.vera_ms`・`llm_ms` も。メモリ = C/D は `vera serve` 子プロセスの RSS の最大（各問いの後に `ps -o rss= -p <pid>`）、全系で Ollama `/api/ps` の `size`（走行の最初と最後）。

### 1.5 人の採点（C3）
- 採点票 `artifacts/w14-bench/grading/sheet.jsonl`（1 行 = 系 × 問い。`id`・`system`・`kind`・`question`・`answer`・`evidence_lines`・出力本文・抜いた出所・機械の下書き（`machine_value_match`・`machine_label`）・空の `label_mid`・`label_aud`・`note_mid`・`note_aud`）。
- 人が採点する行: A/B は全行（400）。C/D は (a) 答え系 outcome の全行、(b) outcome `TESTIMONY` の全行、(c) 抜き取り = 問いの id の末尾の番号が 5 の倍数の全行。乱数は使わない。
- 実装役は `label_mid`・`label_aud` を埋めない。
- 一致率 = 両方が埋まった行のうち `label_mid == label_aud` の割合（系ごと・全体）。不一致は全件を `grading/disagreements.md` に列挙。表の人の採点の列は一致した行だけで数え、不一致の件数を「未決」の列に出す（どちらかに倒さない）。人の採点が無い状態の表は人の列を `未採点` とする。

### 1.6 再現（K362・C4）
- `python -m benchmarks.public_v1.run --system A|B|C|D --model qwen3.5:4b --out DIR [--port N] [--placement P] [--only-doc D1] [--limit N]` → `DIR/<system>/results.jsonl`・`meta.json`。
- `python -m benchmarks.public_v1.score --run DIR [--labels SHEET] --out DIR/table` → `table.json`・`table.md`・`table_core.md`（遅延・メモリ・時刻を除く）・採点票。
- C4 の比較は `table_core.md` と各問いの出力本文の sha256。差は件数と id を全部出す。

### 1.7 判断記録（登録時）
- J1 C には A と同じ messages を送る（層 0 の factual はクライアントの messages を LLM にそのまま渡す製品の仕様）。
- J2 A/B にも棄権と出所の指示を与える（藁人形にしない）。
- J3 C2 の「誤答率 0」は Vera が断定したもの（答え系 outcome・記録の印）に掛ける。証言の印つき本文の誤りは別列で全件を数えて公開する。監査役の確認事項。
- J4 BM25 の 5 位の同点は全部入れる（同点棄権）。
- J5 D4 は v2 だけで本表を測る。v1 は凍結して置くだけ。
- J6 文書と問いは手で書く。Ollama・Vera・codex を、書く・凍結する前に一度も通さない。

## §2 結果
（走行後に機械で貼る）

## §3 登録後の判断・逸脱
（追記のみ）

## §4 既知の穴
（走行後に書く）

## §5 監査役への引き継ぎ
（走行後に書く）
