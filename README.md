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

### Update 2026-10-05 (what changed since 2026-10-04, and what we learned)

**New in the package** (all off by default unless noted; the default outputs of `vera read / ask / serve` are byte-identical to the previous release when the new options are not used):

- **Assumed reading** (`vera read/ask/chat/serve` default mode `assume`; the library function `semantic_read.read` stays strict). When the only thing missing is a *premise* — a name's type, a coined verb, an unknown noun's type — Vera reads with an explicit assumption and says so (`assumptions`, `read_mode: assumed`, the note "（ミナを人として）"). Structure is never assumed (role-splitting particles, clause attachment, anaphora still abstain). Measured on unseen sentences: strict misreads 0, wrong assumptions 0/19. `--strict-read` or `VERA_READ_MODE=strict` turns it off.
- **Compound sentences v1**: 3–4 finite/relative clauses, て-form and continuative with two subjects, quotation edges; subject sharing across clauses and anaphora abstain. Unseen sentences: misreads 0.
- **Predicate role frames and placement r9** (`role_frame` in the placement query; `RELATIVE_POSITION` noun type) — the reader consumes confirmed frames (stage R).
- **Holes and the LLM intake mouths**: typed holes in a cross, a candidate mouth (`vera serve --fill --ledger-file`), an append-only hash-chained testimony ledger (`vera ledger`), a swappable backend (`ollama` / OpenAI-compatible API / `fake`), provenance kind `testimony_fill`. Candidates never become the basis of a factual answer.
- **Placement layers and document-driven growth** (`vera placement grow --documents … --layer`, `vera ledger promote`): a per-user/domain layer that never overrides the base placement; words become `direct` only when the documents' own distribution (or a human) confirms them.
- **Realizer rules/forms split** (`verantyx/data/realize_forms_ja.json`), typed crosses realized and re-read with the same placement, `vera realize`.
- `vera serve --no-llm`, `--profile strict|assume`, `confidence_tiers` (how many independent tiers gave the same answer; abstentions are not counted as agreement).

**What we measured and did not get** (negative results are kept on purpose):

- Hidden bank B1 (reading) stays at correct 11 / misread 0 / wrong 0 across r9, compound v1 and assumed reading. The remaining abstentions are structural: multi-sentence inputs, 「」quotations with honorific names, noun-phrase-only inputs, passive/causative, quantifiers — not missing premises.
- A higher reasoning effort for the role-frame generation (r10) did **not** improve recall of adjunct particles; the bottleneck is corpus coverage (which predicate–particle pairs occur significantly), not generation effort. r10 was not adopted.
- Loading one document does not yet grow a layer (3 direct words out of 69 candidates; QA gain 0); growth needs several documents or human confirmation. Pre-built "initial layers" from the generated corpus did not capture a domain and are not shipped.

**Known defect (fix in progress, ticket W3-f1)**: document QA (`vera ask --mode round5 --document`) answers a two-character kinship noun subject with its first character only (叔父 → 「叔」, 祖母 → 「祖」). The reader itself reads the sentence correctly; the defect is in the QA path. Until it is fixed, treat answers that are a single character as suspect.

**Direction** (decided 2026-10-04/05, recorded in [docs/decisions/](docs/decisions/)): Vera is a weightless structural kernel whose rules are frozen as *base v1* and which grows by data (placements, documents, ledgers, memory); the LLM is a replaceable component that supplies words, never structure; no fine-tuning. The first product is "narrow and never lies, and grows as you use it": sourced QA over your documents, a checking front-end for an existing LLM, and a memory-and-gate for long-running agents (an Anthropic/OpenAI-compatible endpoint that IDE agents can mount). A public, adversarial comparison protocol (version conflicts, near-miss distractors, plausible-but-absent questions, prompt injection inside documents, paraphrase stability, many documents) is being built so the claim can be checked rather than believed.

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

### One endpoint with a language model (fusion, layers 0–1)

```sh
ollama pull qwen3.5:4b
vera serve --backend ollama --model qwen3.5:4b --document ./memo.txt          # layer 0: answer + provenance labels
vera serve --backend ollama --model qwen3.5:4b --document ./memo.txt --strict # layer 1: grammar-bound decoding
```

`/v1/chat/completions` (OpenAI-compatible) and `/api/chat` (Ollama-compatible). The model answers; Vera reads the
question, answers facts that are in your documents from the records with evidence, and labels every sentence and arm
of the reply as *record / testimony / constructed / unread* in the `vera` field. With `--strict` the decoder is bound
by a grammar built from the records and unreadable questions are answered with a typed abstention instead of a call.
Measured with Qwen3.5-4B on the ticket's test set: wrong answers 0 in both layers; record questions answered 21/50
(layer 0) and 18/50 (layer 1); 50/50 questions without a record abstained; 20/20 creative requests came back as
CONSTRUCTED. Details and the response schema: [docs/FUSION.md](docs/FUSION.md).

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

### 2026-10-05 の更新（10-04 以降に変わったことと、分かったこと）

**パッケージに入ったもの**（注記のないものは既定でオフ。新しい選択肢を使わなければ `vera read / ask / serve` の既定の出力は前回と byte 一致）:

- **仮定つきの読み**（`vera read/ask/chat/serve` の既定は `assume`、ライブラリ関数 `semantic_read.read` は strict のまま）。欠けているのが **前提** だけ——名前の型・造語の述語・未知の名詞の型——のとき、仮定を立てて読み、仮定を明示する（`assumptions`、`read_mode: assumed`、注記「（ミナを人として）」）。構造は仮定しない（役割が割れる助詞・節の掛かり先・照応は棄権のまま）。未公開文での実測: strict の誤読 0、仮定の誤り 0/19。`--strict-read` または `VERA_READ_MODE=strict` でオフ。
- **複文 v1**: 定形・連体の 3〜4 節、両節に主語のある て形・連用中止、引用の辺。節をまたぐ主語の共有と照応は棄権。未公開文で誤読 0。
- **述語の役割つきの枠と配置 r9**（問い合わせの `role_frame`、名詞の型 `RELATIVE_POSITION`）。読解器は確認済みの枠を使う（段 R）。
- **穴と LLM の受け入れ口**: 型つきの穴、候補の口（`vera serve --fill --ledger-file`）、追記専用・ハッシュ連鎖の証言の台帳（`vera ledger`）、差し替え可能な後段（`ollama`／OpenAI 互換 API／`fake`）、出所の印 `testimony_fill`。候補は事実の問いの根拠にならない。
- **配置の層と文書駆動の育成**（`vera placement grow --documents … --layer`、`vera ledger promote`）: 基底を上書きしない利用者・分野ごとの層。語が `direct` になるのは文書群自身の分布（または人）が確認したときだけ。
- **実現器の規則と形の表の分離**（`verantyx/data/realize_forms_ja.json`）、型つきの十字を同じ配置で実現・再読、`vera realize`。
- `vera serve --no-llm`、`--profile strict|assume`、`confidence_tiers`（独立した段のうちいくつが同じ答えを出したか。棄権の一致は数えない）。

**測って得られなかったこと**（負の結果は意図して残す）:

- 隠しバンク B1（読解）は r9・複文 v1・仮定つきの読みを入れても 正読 11／誤読 0／誤答 0 のまま。残る棄権は構造によるもの——複数文の入力、「」の引用と敬称つきの名前、名詞句だけの入力、受身・使役、数量——で、前提の欠落ではない。
- 役割の枠の生成で推論の effort を上げても（r10）付加的な格の再現は上がらなかった。律速は生成の effort ではなくコーパスの被覆（どの述語と助詞の組が有意に出るか）。r10 は採用していない。
- 文書を 1 本入れただけでは層は育たない（候補 69 のうち direct 3、QA の増分 0）。育つには複数の文書か人の確認が要る。生成コーパスから作った「初期搭載の層」は分野を捉えず、配布していない。

**既知の欠陥（修正中、チケット W3-f1）**: 文書 QA（`vera ask --mode round5 --document`）が、2 字の親族名詞の主語を 1 字目だけで答える（叔父 → 「叔」、祖母 → 「祖」）。読解器自体は正しく読んでおり、欠陥は QA の経路にある。直るまで、1 文字だけの答えは疑ってください。

**方向**（2026-10-04/05 に決定、[docs/decisions/](docs/decisions/) に記録）: Vera は無重みの構造カーネルで、規則は *ベース v1* として凍結し、データ（配置・文書・台帳・記憶）で育つ。LLM は語を供給する差し替え可能な部品で、構造は供給しない。微調整はしない。最初の製品は「狭くて嘘をつかない、使うほど育つ」: 自分の文書への根拠つき QA、既存 LLM の前段の検査器、長く走るエージェントの記憶と門（IDE のエージェントが装着できる Anthropic／OpenAI 互換の入口）。主張を信じるのでなく検証できるよう、公開の敵対的な比較プロトコル（版の衝突・近い誤り・無いが尤もらしい問い・文書内の注入・言い換えの揺れ・多文書）を作っている。

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

### 言語モデルと一つの入口（融合の層 0・1）

```sh
ollama pull qwen3.5:4b
vera serve --backend ollama --model qwen3.5:4b --document ./memo.txt          # 層 0: 答え＋出所の型
vera serve --backend ollama --model qwen3.5:4b --document ./memo.txt --strict # 層 1: 文法で縛る復号
```

`/v1/chat/completions`（OpenAI 互換）と `/api/chat`（Ollama 互換）。モデルが答え、Vera は問いを読み、文書にある事実は記録から証拠つきで答え、返答の各文・各腕に **記録／証言／構成／未読** の型を `vera` 欄で付けます。`--strict` では記録から作った文法が復号を縛り、読めない問いには LLM を呼ばずに型つきで棄権します。Qwen3.5-4B でチケットの検査データを測った結果: 両層とも誤答 0、記録にある問いの正答は層 0 で 21/50・層 1 で 18/50、記録に無い問い 50/50 棄権、創作の依頼 20/20 が構成。応答の形は [docs/FUSION.md](docs/FUSION.md)。

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
