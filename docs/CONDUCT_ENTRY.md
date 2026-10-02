# 指揮者の入口 — 枠を1つ渡して、実エージェントの起動に到達する

人間が書いた「枠」(Markdown の DSL、または型付きレコードの JSONL)を Vera が読み、型付きの記録にして、
実装エージェントを起動する(または起動予定だけを記録する)ところまでを、既定の CLI の1コマンドで行う。
この入口が受け持つのは **起動に到達するところまで**。聞き返しへの回答精度、検証エージェントの自動起動、
語彙外の LLM 照会は別の仕事で、ここでは扱わない。

```bash
python -m verantyx.cli conduct --frame <枠.md|枠.jsonl> --repo <git の作業ツリー> \
    --adapter <codex|claude|fake> [--dry-run] [--model M] [--effort E] [--max-concurrency N] \
    [--state-dir DIR] [--codex-bin PATH] [--claude-bin PATH]
python tools/run_project.py <同じ引数>        # 上と同じ入口を呼ぶだけの薄い包み
```

Python からは `verantyx.conductor_run.conduct_entry(frame, repo, adapter, dry_run=..., ...)`
(戻り値 `ConductOutcome`)。`vera_system.VeraSystem.conduct()` は変更していない。

## 何が起きるか

1. `--repo` が在るディレクトリか確かめ、台帳 `<repo>/.verantyx-conduct/ledger.jsonl`(`--state-dir` で変更可)を開く。
2. 枠を読む。**形式は内容で判定する**(拡張子は見ない)。コメント(`#`)と空行を除いた最初の行が既知のセクション名
   `[goal]` などなら Markdown、`{"op": "write"|"supersede"|"alias", ...}` なら JSONL。どちらでもなければ拒否。
3. 足りないものがないか確かめる(許可パスと、機械的に確かめられる受入条件)。推測では補わない。
4. 型付きの記録にする(Markdown はコンパイル。JSONL は **入力を実行ディレクトリへ写して** 使う。入力ファイルは書き換えない)。
5. codex / claude は model と effort を決め(下記)、git の作業ツリーであることを確かめ、`AgentRuntime` を作る。
6. `ConductorRun` が `start()` まで進む。`--dry-run` なら実プロセスは起動せず、起動するはずのコマンドを台帳に書いて終わる。

標準出力には JSON を1つだけ出す: `{"verdict", "refusal", "ledger", "run_id", "blocking", "result"}`。

| verdict | 終了コード | 意味 |
|---|---|---|
| `DRY_RUN_PLANNED` | 0 | codex / claude の起動予定を台帳に書いた |
| `RUN_COMPLETE` | 0 | 全 GOAL タスクが検証つきで完了した |
| `RUN_INCOMPLETE` | 1 | 実行したが完了していない(`blocking` に理由。人間判定の受入条件が残る枠では必ずこうなる) |
| `REFUSED` | 2 | 型付きの拒否(`refusal.reason` と、足すべきものを書いた `refusal.missing`) |
| `REFUSED` + `INTERNAL_ERROR` | 3 | 想定外の例外(例外の型名だけを持つ。トレースバックは出さない) |

`--dry-run` を `--adapter fake` に付けても、fake は元々プロセスを起動しないので通常の fake 実行になる。

## 拒否の型(`refusal.reason`)

「無い」「読めない」「形式が分からない」「壊れている」「足りない」は別の型で返す。`missing` は「何を足せばよいか」を具体的に書く。

| reason | 意味 |
|---|---|
| `FRAME_NOT_FOUND` | 枠のパスに何も無い |
| `FRAME_UNREADABLE` | 在るが読めない(ディレクトリ、権限、UTF-8 でない) |
| `FRAME_FORMAT_UNKNOWN` | Markdown でも JSONL でもない(空ファイルを含む) |
| `FRAME_PARSE_ERROR` | Markdown の DSL の誤り(`line` つき) |
| `FRAME_JSONL_INVALID` | JSONL の誤り(`line` つき。壊れた JSON、未知の op・kind、重複 id、許可パス・設定の不正) |
| `FRAME_COMPILE_ERROR` | 構文は通ったが型付きの記録にできない(`line` つき。ORDER の前段が不正な場合も) |
| `WRITE_ALLOWLIST_MISSING` | 許可パスが書かれていない(`[write_allowlist]` が無い) |
| `WRITE_ALLOWLIST_EMPTY` | `[write_allowlist]` が `none: none` で明示的に空 |
| `MACHINE_ACCEPTANCE_MISSING` | 受入条件がすべて `human-judged`、または 0 件 |
| `REPO_NOT_FOUND` | `--repo` が存在するディレクトリでない(`--state-dir` が無ければ台帳も書けず `ledger` は null) |
| `REPO_NOT_GIT` | codex / claude で、`--repo` が git の作業ツリーでない、またはコミットが無い |
| `AGENT_SETTING_MISSING` | codex / claude で model か effort がどこにも指定されていない |
| `AGENT_SETTING_INVALID` | model / effort / max_concurrency の値が不正、または枠の中で値が食い違っている |
| `NO_LAUNCH_PLANNED` | dry-run で、ORDER の門などにより `start()` まで届かず、起動予定が1つも作れなかった |
| `LEDGER_UNUSABLE` | 既存の台帳が壊れている(途中で切れた行、`seq` の飛び)。上書きせず拒否する |
| `INTERNAL_ERROR` | 入口自身の不具合 |

複数の不足が同時にあるときは `reason` に最初の1つを、`missing` に全部の「足すもの」を書く。

## 枠の書式の追加(すべて任意。既存の枠の意味は変わらない)

必須の9セクションと文法は変えていない。次の4セクションは **無くてよい**。無いことと `none: none`(明示的な空)は区別される。
書式の説明は `docs/frames/vera_project_frame.md` の冒頭にもある。

### `[write_allowlist]` — 書き込み許可パス
`ID: 相対パス`。意味は **前方一致**(`tests` は `tests/x.py` を許すが `tests2/x.py` は許さない。`agent_runtime` の照合と同じ)。
glob 文字 `* ? [ ]`、絶対パス、`..`、`.`、空の要素、末尾の `/`、`.git` は **行番号つきの構文エラー**にする
(glob は実行時には照合されず、黙って何にも一致しないため)。ID の重複、パスの重複もエラー。
実行時は、エージェントの終了後に作業ツリーの全差分を検査し、許可パスの外の変更があればセッションごと棄却する。

### 機械的な受入条件
新しい書式は作らず、既存の `[completion_criteria]` の JSON 証人を使う:
`C6: 文 | {"kind":"command_exit","command":["python","-m","verantyx.cli","doctor"],"expected_exit":0}`
(`file_sha256` / `text_in_file` / `git_commit` も機械的)。**(W2-a で更新: codex / claude を dry-run なしで走らせたときは、指揮者がエージェントの終了後に `command_exit` を自分で実行する。docs/CONDUCT_RUN.md。以下は fake と Python の呼び出しの話)** **この入口(CLI)は command_runner を渡さないので、`command_exit` は
コンパイルと台帳への記録までで、実行はしない**(未実行のまま `RUN_INCOMPLETE` の理由になる)。実行は Python から
`conduct_entry(..., command_runner=...)` を渡したときだけ。

### `[forbidden_actions]` と `[protected_actions]` — 承認があっても不可 / 承認があれば可
- `[forbidden_actions]`: `action => reason`。**人間が承認しても許されない**操作。型付きでは
  `INVARIANT "forbidden action F<n>"`(`<action> is not permitted even with human approval`)になり、証人に
  `authority_boundary=True`・`approval_effect="NOT_PERMITTED"` を持つ。人間が承認できないので **ESCALATE は作らない**。
- `[protected_actions]`(既存): 承認があれば可。記録の形は変えていない。
- 同じ動作が両方にあれば構文エラー(Unicode 正規化・大文字小文字・空白を畳んで比べる)。
- 型 API `project_frame.action_authority(spec, action)` は `"FORBIDDEN"` / `"APPROVAL_REQUIRED"` / `"UNDECLARED"` を返す。
  `UNDECLARED` は「枠が何も言っていない」であって「許されている」ではない。

### `[conflict_precedence]` — 衝突したときの優先順位
`ID: HIGHER > LOWER: 理由`。HIGHER / LOWER は閉じた集合 `forbidden_actions` / `philosophy_invariants` /
`completion_criteria` / `protected_actions` から選ぶ。未知の名前、自分自身との比較、同じ組の重複、循環は構文エラー。
`protected_actions > forbidden_actions` もエラー(承認で不可を覆すのは型として矛盾する)。直接の1行だけでなく、
`protected_actions` から `forbidden_actions` へ **長さ1以上のどの連鎖** でも届くなら、経路を閉じた行の番号つきの構文エラー
(例: `protected_actions > philosophy_invariants` と `philosophy_invariants > forbidden_actions` の2行)。逆向きの連鎖は通る。
循環も連鎖をたどって検査する。検査の意味と解釈の意味は同じ(順序は連鎖でつながるものとして読む)。
**どの連鎖でもつながっていない組は順序なしのまま**: 宣言の無い組に勝者を補わない(宣言された順序をコンパイル結果から読み返すときも同じ)。
**現状(このチケットの範囲)**: 優先順位も禁止操作も、型付きの記録(と `action_authority`)として残るだけで、指揮者(`conductor.py` / `conductor_run.py`)は
まだ参照しない。衝突時に棄権して人へ回す処理、禁止操作を実行時に拒否する処理は **未実装**(別チケット)。禁止操作がエージェントへ伝わる経路は、
brief の INVARIANT だけである。

### `[agent_settings]` — エージェントの設定
`key: value`。key は `codex_model` `codex_effort` `claude_model` `claude_effort` `max_concurrency` のみ(未知の key と重複はエラー)。
W2-a で次の4つを追記した(既存の key の意味は変えない): `agent_timeout_seconds` `acceptance_timeout_seconds`(桁で書いた 1〜86400 の整数)、
`claude_permission_mode`(`acceptEdits` `default` `plan` `dontAsk` のみ。`bypassPermissions` と `auto` は拒否)、
`claude_allowed_tools`(`,` 区切りの 1〜32 個の素の道具名。括弧つきの規則は不可)。詳細と既定値は docs/CONDUCT_RUN.md。
- model は `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`、effort は `[a-z]{1,16}`、max_concurrency は桁で書いた正の整数。
  model と effort は引数配列の要素であり、effort は `codex -c` の TOML 文字列の中に入るので、エスケープではなくこの閉じた形で守る。
- **優先順位は 引数(`--model` `--effort` `--max-concurrency`)> 枠**。どちらにも無ければ `AGENT_SETTING_MISSING`
  (codex / claude のときの model と effort。max_concurrency は任意)。台帳の `LAUNCH_PLANNED` に各値の出どころ
  (`cli` / `frame` / `unset`)と、引数が上書きした枠の値を残す。枠(JSONL)の中で値が食い違えば順序で選ばず拒否。
- **max_concurrency は上限であって実効値ではない**。`ConductorRun` は逐次実行なので実効は常に1。台帳に
  `max_concurrency` と `effective_concurrency: 1` の両方を書く。

枠の例: `docs/frames/examples/`(図書館の蔵書検索、実験データの前処理、自治体の申請フォーム、組込みファームの更新ツール)。

## 起動配列

配列(`list[str]`)で持ち、文字列の連結や `shell=True` は使わない。プロンプトは配列に入れず、ファイルを子の標準入力に
つないで渡す(ファイルの終わりで EOF になるので、標準入力を読む子が待ち続けない)。

```
codex : [<codex>, "exec", "--ignore-user-config", "-m", <model>, "-c", 'model_reasoning_effort="<effort>"',
         "-s", "workspace-write", "-C", <worktree>, "-o", <session>/last_message.txt, "-"]      stdin = <session>/prompt.txt
claude: [<claude>, "-p", "--model", <model>, "--effort", <effort>]                               cwd = <worktree>, stdin = <session>/prompt.txt
```
- 末尾の `-` は「プロンプトを標準入力から読む」の明示。`service_tier` は付けない(既存の2か所で `"standard"` と `"default"` に食い違い、正しい値を確かめられないため)。
- `<codex>` `<claude>` は `--codex-bin` `--claude-bin`(既定は PATH 上の `codex` `claude`)。dry-run は実行ファイルの存在を確かめない。
- プロンプトは、枠の型付き記録から作った brief と、runtime のイベント約束の文、そして
  `Write allowlist (enforced after exit): <許可パス>` の1行。**dry-run と実起動は同じ関数(`AgentRuntime._build_prompt` / `_launch_spec`)を通る**。
- dry-run は `git worktree add`・mkfifo・supervisor を行わない(`git rev-parse` のような git の読み取りだけを行う)。
  予定は台帳の `LAUNCH_PLANNED`(argv、予定の cwd(作成していない)、stdin のパス・sha256・文字数、プロンプト全文、許可パス、設定の出どころ、`-o` のパス)に残る。

### 旧 `CodexExecAdapter.build_command` との関係
`CodexExecAdapter.build_command` は **変えていない**(`-s read-only`、`gpt-6-luna` 固定、`service_tier="standard"`、プロンプトは `--` の後の引数)。
runner を注入して使う読み取り専用の形として残る。`AgentRuntime` の backend `"codex"` と `"command"` も同じ。
`conduct` が使うのは新しい backend `"codex-exec"` / `"claude-print"`(純関数 `agent_adapter.codex_exec_launch` / `claude_print_launch` が配列を組み立てる)だけ。
旧 backend の FIFO 経由の標準入力は EOF が来ないので、標準入力を読んで待つ子は終わらない
(`tests/test_conduct_entry_launch.py` にその対照実験がある)。

## 台帳 `ledger.jsonl`(追記専用)

スキーマ `conduct-ledger-v1`。各行は `{schema, seq(台帳全体で連番), run_id, time, type, ...}`。追記は `O_APPEND` + 排他ロック + fsync。
読み込み時に `seq` が飛んでいる、または最終行が途中で切れていれば拒否する(上書きしない)。

| type | 内容 |
|---|---|
| `CONDUCT_INVOKED` | 引数(枠、repo、adapter、dry-run、state-dir、CLI の設定) |
| `FRAME_READ` | パス、sha256、バイト数、形式、空行・コメント行・読み飛ばした行の数 |
| `FRAME_COMPILED` | 記録数、種類ごとの件数、memory のパス、許可パス、機械的 / 人間判定の受入条件の数 |
| `REFUSED` | 型付きの拒否の全項目(reason / missing / detail / source / line) |
| `LAUNCH_PLANNED` | 起動する(した)コマンドの配列、cwd、stdin、プロンプト、許可パス、設定と出どころ、実効同時実行数 |
| `AGENT_START_CALLED` / `AGENT_START_RETURNED` / `AGENT_START_FAILED` | アダプターの `start()` の前後(adapter 名、handle の型名、brief の sha256) |
| `RUN_FINISHED` | 完了か、未完了なら pending と blocking の種類、driver ログのパス |

実行ごとのファイルは `<state>/runs/<run_id>/`(`memory.jsonl` `driver.jsonl` `runtime/`)。

## 既知の制限(隠さない)

- **実起動はすぐ止まる(実測)**: (W2-a で codex / claude の実行については解消: docs/CONDUCT_RUN.md。fake と Python の run_project は従来どおり) 現在の `ConductorRun.run()` は `poll()` が最初に空を返した時点でループを抜け、エージェントを `stop()` する。
  また実行全体の上限は `MAX_RUN_SECONDS = 30`。2秒眠ってから DONE を出す偽の実行ファイルを `--adapter codex` で(dry-run なしに)実行すると、
  プロセスの起動には届くが 0.58 秒で `SESSION_CANCELLED` になった。runtime の記録は
  `SESSION_CREATED, WORKTREE_CREATED, PROCESS_STARTED, SESSION_CANCELLED, ADAPTER_STOPPED`
  (`artifacts/w1-d/real_launch_limit.txt`)。この入口の範囲(起動に到達するところまで)では直さず、別の仕事に回す。
- **Claude の書き込み権限**: (W2-a で更新: 枠の `claude_permission_mode` / `claude_allowed_tools` か引数 `--permission-mode` / `--allowed-tools` で、指定したときだけ `--permission-mode` と `--allowedTools` を足す。既定値は無く、指定しなければ以下のとおり。docs/CONDUCT_RUN.md) `claude -p` に権限の指定(`--permission-mode` など)を付けていない。実起動を禁じた環境で確かめられないため。
  非対話の claude が作業ツリーに書き込めるかは、利用者の設定に依存する。許可パスの検査は終了後に行う。
- **stderr は stdout に合流する**: supervisor は子の stderr を stdout にまとめるので、JSON でない出力は `OTHER` イベントになり、
  指揮者へ質問として渡る(`ConductorRun` が `OTHER` を質問として扱う)。進捗表示の多い codex では `OTHER` が多く出うる。
- **`[conflict_precedence]` と `[forbidden_actions]` は実行時に強制されない**: 宣言は記録と `action_authority` に残るだけで、指揮者は参照しない(衝突時の棄権・エスカレート、禁止操作の実行時拒否は未実装)。
- **`command_exit` の受入条件は CLI では実行されない**(上記)。(W2-a で codex / claude の実行については解消: docs/CONDUCT_RUN.md。fake と Python の run_project は従来どおり) 人間判定の条件が残る枠は `RUN_INCOMPLETE` で終わる。
- **brief の秘匿処理**: `compile_frame_brief` は `secret` `token` などの語を含む値を `[REDACTED]` にする。そういう語を含む
  forbidden action や許可パスは、brief 上では伏せ字になる(許可パスだけはプロンプトの `Write allowlist` の行に別に載る)。
- 行末が `]` の行は、既存の行読み取りが「セクション見出し」と見なすので、`dir/[ab]` のような glob も、許可パスの誤りではなく
  見出しの誤りとして(行番号つきで)拒否される。
- 同時に複数のエージェントを走らせる経路は無い(実効同時実行数は常に1)。
- `--repo` の下に `.verantyx-conduct/` ができる(実起動では git worktree もここに作られる)。必要なら `.gitignore` に足すか `--state-dir` で外に置く。

## demo_conduct が止まっていた原因(切り分けの結果)

`tools/demo_conduct.py` は `ORDER predecessor is outside the active GOAL frame` で止まっていた。これは **実装の不具合ではなく、枠(demo)の書き方の誤り**。
ORDER の門(`conductor_run._order_gate`、コミット `4fdab45 unit x_driver` で追加)は前段に「GOAL タスクであること」と「立会い済みの DONE」を要求する。
demo は門より前の `bc808ef unit c_conduct` で書かれ、前段 `foundation` を `add_task` だけで書いていたため、門に当たった。
門の後に書かれた `tools/demo_driver.py` は前段を GOAL にしていて通る。`foundation` を GOAL と受入条件つきにして直したところ `DEMO OK` になった。
