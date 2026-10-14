# HARNESS_DESIGN — Vera をハーネス専用リポジトリとして公開する設計

設計: Opus（2026-10-14）。依頼（オーナー、逐語）: 「veraリポジトリをハーネス専用にして例えばdeepseekハーネスのような形で公開できる完成度にする自分の強みを持ったものにする」
直前の文脈（逐語）: 「仮に構造体が関係していないとしてこれに通すことでモデルが嘘をつくことなどを防ぐことができたりモデルを管理することができやすくなるならカーネルとして投稿する形で行こうと思います。エージェントツールか。」「ハーネスとしt」

## 0. 結論

- **何を出すか**: 「Vera Harness」。モデル（Claude、DeepSeek、ローカルの小型モデル）を Vera の中で動かし、**出力は Vera の操作を通したものだけ**にするハーネス。
  答えは記録の一字一句の引用だけで、根拠が読めない・食い違う・古い値のときは黙る。全操作はハッシュで連ねた台帳に残り、誰でも同じ結果で再生できる。
- **DeepSeek Harness（dsh）との違い＝強み**: dsh は「何でもプラグイン」の汎用エージェント基盤。Vera Harness は **検証のハーネス**:
  1. 出力経路の強制（自由な文は捨てる。道具の強制、許可リスト、OS サンドボックス）
  2. 引用のみ・既定で拒否の答え（「分かりません」を言える。誤答 0 の計測つき）
  3. 矛盾・更新を構造で見つける記憶（学習なし、決定的）
  4. 再生できる台帳（監査・説明責任）
  5. 中核は標準ライブラリ＋形態素解析だけ、学習なし、オフライン
- **主張しないこと**: 構造体（立体十字）の幾何の効果。研究として別に続ける（OP-PUB-8 の扱いは §9 の問い）。

## 1. 実証済みの主張と限界（README にそのまま載せる数字）

| 主張 | 数字 | 出典 |
|---|---|---|
| 答えのない問いで答えを出さない（門 v6） | bank4 0/60、bank6 0/34、bank7 0/47、bank8 0/50（bank8 は v2 時点の未見判定） | experiments/line3/loom/ev6 |
| 実際のモデル（Haiku 5.5）で答えのない問いへの確信誤答 | 0/126（門 v2） | results_h55f |
| 記憶の答えで誤答 | 0（思い出しなし・言い換え・紛らわしい書き方・橋の攻撃すべて） | pub/m6c meter |
| 矛盾の検知 | 精度 0.83、仕掛け 216 件中 137 件 | pub/m5m6 |
| 再生 | 全台帳バイト一致、PYTHONHASHSEED 0/1/12345 | CI |
| **限界** | 日本語のみ。未見の問題で答えに届くのは約 1 割。記憶は 1 書き込み 1 事実の文でしか答えない。「変わった」「延長」「XはYが担当」、同義語、別書き込みでの撤回は読めない | §1 の各報告 |

## 2. リポジトリの形（新しい main）

```
vera/                       （GitHub: Ag3497120/vera の main）
  README.md                 日本語が主、英語版 README.en.md
  pyproject.toml            name = "vera-harness", scripts: vera
  verantyx/                 パッケージ名は維持（台帳の再生互換のため）
    loom/                   織機・門・記憶（今の 31 モジュール）
    line3/                  文法層の最小部分（10 モジュール）
    lang.py, ledger_events.py
    harness/                新規: backends/, runner.py, enforce.py, plugins.py, webui/, cli.py
  examples/                 docs_qa/（文書に問う）, memory/（作業ログの記憶）, claude_code/（MCP＋サブエージェント）
  evals/                    bank4/6/7/8 と meter v1 の小さい版、`vera eval` で回る
  tests/                    ハーネスの試験＋小さい再生の固定ファイル
  docs/                     ARCHITECTURE.md, SAFETY.md（主張と限界）, PLUGINS.md, LEDGER.md
  .github/workflows/        ci.yml（試験・再生・eval）
```

研究の履歴（今の main の 26,000 ファイル、experiments 697MB、G 系の設計書）は **`research` ブランチとタグ `research-2026-10-14`** に丸ごと残す（OP-H-1）。line3 ブランチも残す。

## 3. 使い方（目標の体験）

```
pipx install vera-harness            # または: uvx vera-harness
vera run                             # http://127.0.0.1:3090 に画面
vera ask --docs ./manuals "保守契約の更新期限はいつですか？"
vera mem                             # 記憶つきの対話（作業ログ）
vera mcp                             # Claude Code などに Vera を唯一の出口として渡す
vera verify runs/xxx && vera replay runs/xxx
vera eval                            # 安全の主張を手元で再計測
```

## 4. 中身

### 4.1 バックエンド（モデルの差し替え）
- Anthropic（既存の駆動部: tool_choice any、自由な文を捨てる）
- OpenAI 互換（DeepSeek、Ollama、LM Studio、vLLM、MLX サーバー）: 道具呼び出しを強制。道具呼び出しのないモデルには、JSON の操作列だけを受け付ける方式（それ以外の出力は捨てる）
- 鍵: 環境変数か OS の鍵束。表示・記録しない（既存の規則）

### 4.2 強制の段（README に段ごとの保証を書く）
- E1 既定: 駆動部が Vera の道具だけを渡し、自由な文を捨てる（全 OS）
- E2 Claude Code: MCP＋サブエージェントの許可リスト（既存 L1）
- E3 OS サンドボックス: macOS sandbox-exec（既存）。Linux は bubblewrap を後で

### 4.3 プラグイン
- 門の版、記憶の版、バックエンド、注記を、Python の entry points で差し替え可能に（`vera.plugins`）。既定は門 v6・記憶 v17（memanswer）。
- 台帳は使った版を必ず記録するので、プラグインを替えても過去の実行は再生できる。

### 4.4 画面（ローカル、外部読み込みなし）
- 左: 会話（モデルの答えは引用か「分かりません（理由）」だけ）
- 右: 操作の流れ、根拠の文、拒否の理由、台帳のハッシュ連鎖、記憶の十字と巣（既存の俯瞰図を流用、three.js は任意）

### 4.5 評価
- `vera eval` が bank と計器の小さい版を回し、§1 の数字を手元で再現する。

## 5. 安全と公開の手順

- 公開は main への push。今の main を research に退避してから入れ替える（取り消し可能、タグで固定）。push はオーナーの許可のもとで行う。
- PyPI への公開はオーナーが別途許可したときだけ（外向きの操作）。

## 6. チケット（実装 Sonnet、審査 Opus、試験・計測は CI）

| # | 内容 |
|---|---|
| H0 | `harness` ブランチを作り、中核 42 モジュールだけを持つ最小の木を組む（import の閉包で自動抽出、試験と小さい固定ファイルを選ぶ） |
| H1 | バックエンド: Anthropic＋OpenAI 互換（DeepSeek、Ollama）、道具なしモデル向けの JSON 操作方式 |
| H2 | runner と CLI（run / ask / mem / mcp / verify / replay / eval） |
| H3 | 画面（静的 1 ファイル、ローカルのみ） |
| H4 | プラグインの登録 |
| H5 | evals と `vera eval` |
| H6 | README（日本語）・README.en・docs（SAFETY に主張と限界）・例 3 つ |
| H7 | CI（試験・再生・eval）、パッケージの組み立てと素の venv での導入確認 |
| H8 | 敵対的審査（出力の抜け道、鍵の漏れ、ローカルサーバーの露出） |
| H9 | main の入れ替え（research へ退避＋タグ）、push（オーナー許可） |

## 7. 却下した案
- 研究のコードごと公開してハーネスを一部にする: 26,000 ファイルの中でハーネスが埋もれ、導入が重い。
- パッケージ名を `vera` に変える: 過去の台帳の再生互換が壊れる。CLI 名で `vera` を使い、import 名は維持。

## 8. 危険
- 答えられる範囲が狭いので、試した人は「分かりません」が多いと感じる。README の最初に「嘘をつかない代わりに黙る」ことと数字を書く。
- 日本語のみ。英語の問いには答えない（門が拒否）。

## 9. オーナーへの問い（推奨を先頭）

| # | 問い | 推奨 |
|---|---|---|
| OP-H-1 | 今の main の中身をどうするか | research ブランチとタグに退避し、main をハーネスだけにする |
| OP-H-2 | 構造の主張なしで先に公開してよいか（OP-PUB-8 との関係） | ハーネスは構造の主張なしで公開、構造は研究として続ける |
| OP-H-3 | 最初に対応するモデル | Claude と OpenAI 互換（DeepSeek・Ollama などのローカル）の両方 |
| OP-H-4 | 名前 | 「Vera Harness」、コマンドは `vera` |
