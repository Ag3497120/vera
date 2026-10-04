# Vera

**Vera is an AI with no weights that builds a frame in which a language model cannot lie.**
It reads Japanese sentences into *event crosses* (predicate, roles, typed fillers, polarity, tense), keeps the
owner's documents and decisions as append-only records, answers only with a source attached, and when it cannot
answer it says so with a typed reason instead of guessing. It runs on a CPU in milliseconds and is deterministic.

This repository is the public snapshot of the development tree (`vera_base/verantyx`, synced 2026-10-04,
40 integrated tickets). Every number below is a measurement; nothing here is estimated.

(日本語版は後半にあります / The Japanese text follows the English text.)

---

## English

### What Vera is, in one paragraph

Vera is not a neural network and it is not a hand-written rule system over word lists. It is a structure:
reading conventions (a closed set of roles, polarity, tense, quantifiers), a *coarse placement* of words into
17 types computed from the distribution of a 7-million-line generated corpus (no learned parameters, every
decision recomputable from evidence rows and thresholds), predicate frames proposed by a code model and kept
only when the corpus distribution confirms them, and human records as the only ground for facts. Where a
reading is ambiguous Vera abstains. The principle throughout is *zero misreadings over coverage*.

### What it does today

| Capability | Measured |
|---|---|
| Reads Japanese single- and two-clause sentences into event crosses; abstains with a typed reason otherwise | hidden bank B1 (reading, 296 items): correct 11, **misread 0** |
| Answers wh-questions over a document with the evidence sentence attached (question cross = a cross with a typed hole, observed over the document) | question observation, 185 items: correct 73, **wrong 0** |
| Never answers a factual question from generated text alone; separates human records / generated / unknown; asks for confirmation when a human is present | hidden bank B7 (basis policy, 100 items): wrong 0, generated-only answers 0 |
| Routes work between agents from a free-text description of each agent, undecided when unsure | hidden bank B6 (132 items): misrouted 0 (routed 0) |
| Append-only memory split into sovereigns: delete by unit, consent-gated promotion | 0 races under adversarial tests |
| Generates by *observing* a structure (moving along faces and edges of crosses); each output is typed OBSERVED / CONSTRUCTED (outside the closure) / UNKNOWN; re-observation reproduces it | 100 % reproducible |
| Chat: free conversation | hidden bank B2 (286 items): correct 0, wrong 0 |

Six adversarial waves (codex at maximum effort) produced 35 hits; all are fixed or recorded as known holes.
Nothing was ever answered wrongly on any bank.

### What it cannot do yet

- Free conversation, long documents, complex Japanese; English has no placement, so the typed path does not run.
- Adverbs and floating noun-phrase quantifiers are not read (they abstain).
- The role of a で / に / へ / から phrase is not decided by types alone (shown twice on unseen sentences; the
  next step is predicate-specific *role frames*, ticket W3-a6).
- Coverage is small: the strength is that what it says is sourced and what it does not know it says.

### Install and run

```sh
python -m pip install -r requirements.txt
python -m pip install -e .
```

Chat over your own documents (the REPL shares the exact path of `vera ask`):

```sh
vera-chat --document ./memo.txt          # = vera chat --mode round5 --document ./memo.txt
vera ask "資料を渡したのは誰ですか。" --mode round5 --document ./memo.txt
```

REPL commands: `/doc <path>` `/docs` `/read <sentence>` `/gen <sentence> [FACE_SWAP:<role>|EDGE:<relation>]`
`/route <agents.md> <task.json>` `/json on|off` `/help` `/quit`. See [docs/CHAT.md](docs/CHAT.md).

The coarse placement (a 290 MB SQLite built from the corpus) is **not** in the repository; without it the typed
reading path and typed question answering do not run. Build one with `tools/build_coarse_placement.py` (see
[docs/COARSE_PLACEMENT.md](docs/COARSE_PLACEMENT.md)) and point `VERA_PLACEMENT` at it.

### How it is built

- **Reading** — `verantyx/semantic_read.py`, `semantic_reader.py`; contract in
  [READING_CONVENTIONS](docs/READING_CONVENTIONS.md), soundness ledger (pre-registered rules, every change with
  before/after text) in [READING_SOUNDNESS](docs/READING_SOUNDNESS.md).
- **Event cross** — `verantyx/event_cross.py`, [EVENT_CROSS](docs/EVENT_CROSS.md): the predicate is the centre,
  roles are arms, words are fillers whose types come from the placement; relative clauses are crosses inside
  fillers, connectives are typed edges between crosses.
- **Placement** — `verantyx/coarse_place.py`, `coarse_types.py`, [COARSE_PLACEMENT](docs/COARSE_PLACEMENT.md):
  17 noun types and 13 predicate types from corpus distributions; generated frames confirmed by distribution.
- **Observation** — `verantyx/observe.py`, [OBSERVATION](docs/OBSERVATION.md): generation and question
  answering are the same operation.
- **Basis policy** — `verantyx/basis_policy.py`, [BASIS_POLICY](docs/BASIS_POLICY.md): human records answer
  facts; generated text may lend wording; a human present gets a confirmation question.
- **Routing** — `verantyx/routing_from_text.py`, [ROUTING_FROM_TEXT](docs/ROUTING_FROM_TEXT.md).
- **Evaluation** — hidden banks scored by `tools/bank_score` ([BANK_SCORE](docs/BANK_SCORE.md)); the banks
  themselves are not published. Method in [EVAL.md](EVAL.md), known failures in [KNOWN_ISSUES.md](KNOWN_ISSUES.md).
- **Shadow operation** — [OPS_SHADOW](docs/OPS_SHADOW.md): Vera observes the project's own development loop
  (routing, questions) with no authority, counting agree / abstain / wrong.

### Where it is going

Vera is being fused with an open-weights language model (base: **Qwen/Qwen3.5-4B**) in layers, each one
measured before the next:

0. One endpoint (OpenAI- and Ollama-compatible): the model answers, Vera labels every sentence and arm as
   *record / testimony / constructed / unread*; facts in your documents are answered from the records with evidence.
1. Grammar-constrained decoding from the records (`--strict`).
2. Vocabulary intake with human approval (then Vera reads it alone), a feedback path back from the chat UI,
   and rule enforcement that the model cannot bypass.
3. A structure-token model: the LM emits Vera's cross tokens, Vera's realizer writes the sentence (LoRA → GGUF).

The point of the fusion is to shorten the early research time and make the value visible; the weightless core
keeps being developed in parallel.

### License

MIT (Vera). Base models keep their own licenses.

---

## 日本語

### Vera とは（一段落で）

**Vera は、言語モデルが嘘をつけない枠をつくる、重みのない AI です。** 日本語の文を事象の十字（述語・役割・型つきの充填物・極性・時制）に読み、持ち主の文書と決定を追記のみの記録として持ち、答えには必ず出所を付け、答えられないときは推測せずに型つきの理由で黙ります。CPU の上でミリ秒で動き、決定的です。

ニューラルネットではなく、語の一覧に対する手書きの if-then でもありません。構造です: 読解の規約（役割・極性・時制・量化の閉じた集合）、生成コーパス 700 万行の分布から計算した 17 型への **粗い配置**（学習したパラメータは無く、証拠の行と閾値から再計算できる）、コードモデルが申告しコーパスの分布が裏づけたときだけ採る述語の枠、そして事実の唯一の根拠である人の記録。読みが割れるところでは棄権します。全体を貫く原則は **正読より誤読ゼロ** です。

このリポジトリは開発ツリーの公開スナップショット（`vera_base/verantyx`、2026-10-04 同期、統合 40 チケット）です。以下の数字はすべて実測で、見込みの数字はありません。

### 今できること

| 能力 | 実測 |
|---|---|
| 単文〜2 節の日本語を事象の十字に読む。読めなければ型つきで棄権 | 隠しバンク B1（読解 296 問）: 正読 11、**誤読 0** |
| 文書への wh 疑問に、証拠の文を付けて答える（質問の十字＝穴の空いた十字を文書の上で観測） | 質問の観測 185 問: 正 73、**誤 0** |
| 生成テキストだけでは事実を答えない。人の記録／生成／不明を分け、人が居れば確認を問い返す | 隠しバンク B7（根拠の方針 100 問）: 誤答 0、生成だけの回答 0 |
| 各エージェントの自由文の説明から仕事を振り分け、迷えば未決 | 隠しバンク B6（132 問）: 誤ルート 0（ルート 0） |
| 追記のみの記憶をソブリンに分ける: 単位で削除、同意つきで昇格 | 攻撃テストで競合 0 |
| 構造を **観測** して生成（十字の面と辺に沿って動く）。出力は 観測された／構成した（閉包の外）／不明 の型つき。再観測で再現 | 再現 100 % |
| 自由会話 | 隠しバンク B2（286 問）: 正答 0、誤答 0 |

攻撃 6 波（codex の最大努力）で命中 35。すべて修正済みか既知の穴として記録済み。どのバンクでも誤った答えを出したことはありません。

### まだできないこと

- 自由会話、長文、複雑な日本語。英語は配置が無く、型の経路が動きません。
- 副詞と名詞句にかかる遊離数量は読みません（棄権）。
- で・に・へ・から の句の役割は型だけでは決まりません（未公開の文で 2 度示された。次は述語ごとの **役割つきの枠**、チケット W3-a6）。
- 到達は小さい。強みは「言うことには出所があり、知らないことは知らないと言う」ことです。

### 導入と実行

```sh
python -m pip install -r requirements.txt
python -m pip install -e .
```

自分の文書で対話（REPL は `vera ask` と同じ経路を通ります）:

```sh
vera-chat --document ./memo.txt          # = vera chat --mode round5 --document ./memo.txt
vera ask "資料を渡したのは誰ですか。" --mode round5 --document ./memo.txt
```

REPL のコマンド: `/doc <path>` `/docs` `/read <文>` `/gen <文> [FACE_SWAP:<役割>|EDGE:<関係>]`
`/route <agents.md> <task.json>` `/json on|off` `/help` `/quit`。詳細は [docs/CHAT.md](docs/CHAT.md)。

粗い配置（コーパスから作る 290 MB の SQLite）はリポジトリに **含みません**。無いと型による読解と型つきの質問回答は動きません。`tools/build_coarse_placement.py` で作り（[docs/COARSE_PLACEMENT.md](docs/COARSE_PLACEMENT.md)）、`VERA_PLACEMENT` で指します。

### つくり

- **読解** — `verantyx/semantic_read.py`、`semantic_reader.py`。契約は [READING_CONVENTIONS](docs/READING_CONVENTIONS.md)、健全性の台帳（事前登録した規則、変更は前後の全文つき）は [READING_SOUNDNESS](docs/READING_SOUNDNESS.md)。
- **事象の十字** — `verantyx/event_cross.py`、[EVENT_CROSS](docs/EVENT_CROSS.md)。中心が述語、腕が役割、語は充填物で型は配置から来る。連体修飾節は充填物の中の十字、接続語は十字の間の型付きの辺。
- **配置** — `verantyx/coarse_place.py`、`coarse_types.py`、[COARSE_PLACEMENT](docs/COARSE_PLACEMENT.md)。名詞 17 型・述語 13 型をコーパスの分布から。生成の枠は分布で確認。
- **観測** — `verantyx/observe.py`、[OBSERVATION](docs/OBSERVATION.md)。生成と回答は同じ操作。
- **根拠の方針** — `verantyx/basis_policy.py`、[BASIS_POLICY](docs/BASIS_POLICY.md)。事実は人の記録が答え、生成テキストは言い回しを貸すだけ、人が居れば確認を問い返す。
- **分業** — `verantyx/routing_from_text.py`、[ROUTING_FROM_TEXT](docs/ROUTING_FROM_TEXT.md)。
- **評価** — 隠しバンクを `tools/bank_score` で採点（[BANK_SCORE](docs/BANK_SCORE.md)）。バンク自体は公開しません。方法は [EVAL.md](EVAL.md)、既知の失敗は [KNOWN_ISSUES.md](KNOWN_ISSUES.md)。
- **影運用** — [OPS_SHADOW](docs/OPS_SHADOW.md)。Vera がこのプロジェクト自身の開発の往復（分業・問い）を権限なしで観測し、一致／棄権／誤りを数える。

### これから

Vera は開いた重みの言語モデル（ベース: **Qwen/Qwen3.5-4B**）と層ごとに融合し、各層を測ってから次へ進みます:

0. 一つの入口（OpenAI 互換・Ollama 互換）: モデルが答え、Vera が各文・各腕に **記録／証言／構成／未読** の型を付ける。文書の事実は記録が証拠つきで答える。
1. 記録から作った文法で復号を縛る（`--strict`）。
2. 人の承認による語彙の取り込み（以後は Vera だけで読む）、チャット UI からのフィードバックの逆経路、モデルが外せない規則の強制。
3. 構造トークンのモデル: LM は Vera の十字のトークンを出し、文は Vera の実現器が書く（LoRA → GGUF）。

融合の目的は初期の研究時間を縮め、価値を見えるようにすること。重みのない本体の開発は並行して続けます。

### ライセンス

MIT（Vera）。ベースモデルはそれぞれのライセンスに従います。
