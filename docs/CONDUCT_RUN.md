# 指揮者が実エージェントを最後まで走らせ、受入条件を自分で確かめる(W2-a)

`python -m verantyx.cli conduct --frame <枠> --repo <ツリー> --adapter codex|claude`(`--dry-run` なし)は、
エージェントのプロセスが終わるまで待ち、枠の `command_exit` 型の受入条件を**指揮者が自分で**作業ツリーの中で実行し、
合否を型つきの `outcome` で返す。エージェントの「完了しました」や `DONE` / `CLAIM` は完了の根拠にならない。
入口と台帳の基本は `docs/CONDUCT_ENTRY.md`。この文書は W2-a で足した「待つ・確かめる・コミットする」の部分。

実装: `verantyx/conductor_run.py` の `_run_agent_process` ほか(`# W2-a` の節)。`ConductorRun` クラスは変えていない。

## 流れ

1. 枠を読み、記録に直す(従来どおり)。タスクが1つで ORDER の前段が無いことを確かめる。
2. **エージェントを起動する前に**、そのタスクの受入条件(ACCEPTANCE 記録)の写しを取る。実行中に memory が書き換わっても写しは変わらない。
   エージェントの出力に書かれたコマンドは、どんな形でも実行しない。
3. 元のリポジトリの状態(ref・HEAD・symbolic HEAD・作業ツリーの状態)を記録する(`REPO_GUARD` before)。
4. 作業用 git worktree を作ってエージェントを起動し、**終わるまで待つ**(下の「止める条件」)。
5. 終わったら、プロセスグループが空であることを確かめ(`AGENT_PROCESS_CHECK`)、元のリポジトリをもう一度記録する(`REPO_GUARD` after)。
6. 終わり方を `outcome` に分ける(下の表)。受入に進めるのは、エージェントが正常終了し、許可パスの外に書かず、
   元のリポジトリと worktree の HEAD が動いていないときだけ。
7. 受入条件を worktree の中で実行する(sandbox の下。下の「コマンドの方針」)。全部の条件を実行する(1つ落ちても途中でやめない)。
8. 全部合格なら、runtime が stage した内容**だけ**を worktree の中でコミットする。

## 止める条件

エージェントの実行を止めるのは次の3つだけ。poll が空のリストを返したことは「まだ何も無い」であり、終了とは扱わない
(旧 `ConductorRun` は最初の空の poll で止めていた)。

| 条件 | 結果 |
|---|---|
| プロセスの終了(runtime が終端を記録した) | 終わり方を分類する |
| 時間上限(`agent_timeout_seconds`) | `TIMED_OUT` |
| STOP の指示 | `STOPPED` |

- **時間上限**: 引数 `--agent-timeout-seconds` > 枠の `[agent_settings]` の `agent_timeout_seconds` > 既定値(設計値)。
  runtime の期限(supervisor が自分のプロセスグループごと殺す)に加え、指揮者側にも保険の期限を置く(上限 + `GUARD_GRACE_SECONDS`)。
  保険が働いたときは台帳の `AGENT_EXITED.guard_deadline_used` が真になる。
  supervisor は期限で自分も殺されて status を書かないので、期限を過ぎた後の終了は `SESSION_PROCESS_FAILED(-9)` ではなく
  `SESSION_TIMED_OUT` と読む(`agent_runtime._finalize_process`)。
- **STOP**: ファイル `<state>/runs/<run_id>/STOP` を作る(パスは台帳の `AGENT_WAITING.stop_file`)、または指揮者のプロセスに
  SIGTERM / SIGINT を送る。待っている間だけメインスレッドでシグナルを受け、終わったら元のハンドラに戻す。
  メインスレッドでない呼び出しではシグナルは受けない(`AGENT_WAITING.signal_handlers: false`)。
  どちらでもプロセスグループごと止める。
- 時間切れ・異常終了・STOP の後に子プロセスが残らないことは、台帳の `AGENT_PROCESS_CHECK.group_alive`(supervisor を回収した後に
  `killpg(pgid, 0)`)と、テストの pid 検査で確かめる。

## 設定と既定値

| 項目 | 引数 | 枠(`[agent_settings]`) | 既定値(設計値) |
|---|---|---|---|
| エージェントの時間上限 | `--agent-timeout-seconds` | `agent_timeout_seconds` | 1800 秒(`DEFAULT_AGENT_TIMEOUT_SECONDS`) |
| 受入コマンド1つの時間上限 | `--acceptance-timeout-seconds` | `acceptance_timeout_seconds` | 600 秒(`DEFAULT_ACCEPTANCE_TIMEOUT_SECONDS`) |
| 出力の上限 | (CLI には出さない。`conduct_entry(agent_output_limit=)`) | - | 8 MiB(`DEFAULT_AGENT_OUTPUT_LIMIT`。runtime 自身の既定は 64 KiB) |
| 待つ間隔 | (`conduct_entry(poll_interval=)`。テスト用) | - | 0.2 秒(`POLL_INTERVAL_SECONDS`) |
| claude の権限モード | `--permission-mode` | `claude_permission_mode` | 無し(指定したときだけ引数に足す) |
| claude の許可ツール | `--allowed-tools` | `claude_allowed_tools` | 無し(指定したときだけ引数に足す) |

- 時間は桁で書いた 1〜86400 の整数。0・86401 以上・小数・負数は `AGENT_SETTING_INVALID`(枠の中なら行番号つきの `FRAME_PARSE_ERROR`)。
- 優先順位は 引数 > 枠 > 既定値。台帳の `RUN_LIMITS` と `LAUNCH_PLANNED` に各値の `{value, source: cli|frame|default}` を残す。
- 既定値は**設計値**で、実測から決めたものではない。
- `claude_permission_mode` は `acceptEdits` `default` `plan` `dontAsk` のみ。`bypassPermissions`(確認を全部外す)と `auto` は
  枠でも引数でも拒否する。`claude_allowed_tools` は `,` 区切りの 1〜32 個の素の道具名(`Edit,Write`)。`Bash(git *)` のような
  括弧つきの規則は、このチケットでは許さない。claude にだけ効き、codex に `--permission-mode` / `--allowed-tools` を付けると拒否。
- claude の引数配列は、指定があるときだけ末尾に `--permission-mode <mode>` と `--allowedTools <A,B>` を足す
  (`--allowedTools` は可変長なので最後)。指定が無ければ W1-d と同じ配列。

## 結果の型(`outcome`)

`conductor_run.PROCESS_OUTCOMES`。`verdict` は `COMPLETE` だけが `RUN_COMPLETE`(終了コード 0)、他はすべて `RUN_INCOMPLETE`(1)。
`blocking` は `{kind: <outcome>, task_id, reason, failed_criteria}`。fake / Python から渡したアダプター / dry-run / 拒否では `outcome` は null。

| outcome | いつ |
|---|---|
| `COMPLETE` | 全部の機械的な受入条件が PASS で、人間判定が無い。指揮者がコミットした(変更が無ければ `COMMIT_SKIPPED`) |
| `ACCEPTANCE_FAILED` | 受入条件のどれかが FAIL(`failed_criteria` に全部) |
| `ACCEPTANCE_UNVERIFIED` | FAIL は無いが、REFUSED / ERROR / NOT_EVALUATED がある(またはタスクに受入記録が無い)。「分からない」であり、偽とは混ぜない |
| `HUMAN_JUDGMENT_PENDING` | 機械的な条件は全部 PASS で、人間判定が残る。コミットしない。worktree は人が見るために残す |
| `TIMED_OUT` | 時間上限(runtime の `SESSION_TIMED_OUT`、または指揮者の保険の期限) |
| `AGENT_FAILED` | エージェントが 0 以外で終わった(`exit_code`)。待つこと自体が失敗したときも |
| `AGENT_LIMIT_REACHED` | 出力に利用上限の文言があり、かつ「0 以外で終わった」か「変更が 0 件」 |
| `ALLOWLIST_VIOLATION` | 許可パスの外の変更(runtime の棄却、またはコミット直前の再検査) |
| `AGENT_COMMITTED` | エージェントが worktree の HEAD を動かした(コミットは指揮者だけ) |
| `REPO_CHANGED` | 実行の前後で元のリポジトリの ref・HEAD・作業ツリーの状態が変わった |
| `OUTPUT_LIMIT` | 出力が上限を超えた |
| `WORKTREE_CHECK_FAILED` | runtime の差分検査そのものが失敗した |
| `STOPPED` | STOP ファイル、または SIGTERM / SIGINT |
| `AGENT_START_FAILED` | `start()` が例外を投げた、または実行ファイルが見つからない |
| `ORDER_BLOCKED` | タスクに ORDER の前段がある(この経路は前段を走らせない) |
| `MULTIPLE_TASKS_UNSUPPORTED` / `NO_TASK` | GOAL のタスクが 2 件以上 / 0 件(Markdown の枠は常に 1 件) |
| `COMMIT_FAILED` | 受入は通ったが git のコミットに失敗した(指示書の表に無い型。実装役が足した。判断記録を参照) |

**判定の順序**(型の違うものを分ける規則で、同点を作る規則ではない):
`STOPPED` → `TIMED_OUT` → (待ちの失敗) → `OUTPUT_LIMIT` → `AGENT_LIMIT_REACHED` → `AGENT_FAILED` → `ALLOWLIST_VIOLATION` →
`WORKTREE_CHECK_FAILED` → `REPO_CHANGED` → `AGENT_COMMITTED` → 受入の判定。どの信号(`exit_code`、`limit_text_seen`、
`changed_paths`、runtime の終端の種類、`stop_source`、`guard_deadline_used`)も台帳の `AGENT_EXITED` に全部残す。

### 利用上限の文言

`conductor_run.LIMIT_TEXT` = `You(?:'|’)ve hit your\b[^\n]{0,40}?\blimit`。エージェントの出力全体と、codex の
`last_message.txt` に当てる。出どころ: codex の実行ファイルの文字列は `You’ve hit your usage limit`(アポストロフィが U+2019)、
claude は `You've hit your <名前> limit`(ASCII の `'`)。どちらも実行ファイルの文字列を読んだもので、起動して確かめたものではない。
文言が出ていても、exit 0 で変更があれば `AGENT_LIMIT_REACHED` にはしない(`limit_text_seen` に残るだけ)。

## 受入条件の状態

受入条件ごとに、次の閉じた集合のどれかを台帳に残す。

| 状態 | 意味 |
|---|---|
| `PASS` | 実行し、終了コードが期待(`expected_exit`、既定 0)どおり |
| `FAIL` | 実行し、終了コードが期待と違う |
| `REFUSED` | 方針で実行しなかった(`refusal_reason` が型) |
| `ERROR` | 実行しようとしたが結果が得られなかった(`PROGRAM_NOT_FOUND` / `COMMAND_TIMED_OUT` / `SANDBOX_UNAVAILABLE` / `OSError`) |
| `NOT_EVALUATED` | `command_exit` 以外の機械的な witness(`file_sha256` / `text_in_file` / `git_commit`)。このチケットでは評価しない |
| `HUMAN` | 人間判定 |

全体は、`FAIL` が 1 つでもあれば `ACCEPTANCE_FAILED`、次に `REFUSED` / `ERROR` / `NOT_EVALUATED` があれば `ACCEPTANCE_UNVERIFIED`、
次に `HUMAN` が残れば `HUMAN_JUDGMENT_PENDING`、それ以外が `COMPLETE`。

## コマンドの方針(既定で拒否し、理由を型で返す)

実行できるのは、枠に書かれた `command_exit` のコマンドだけ。argv の配列で実行し、シェルは使わない(`shell=True` なし)。
`cwd` は worktree の実パス、`stdin` は空、新しいセッション。環境変数は親を引き継ぎ、`PYTHONDONTWRITEBYTECODE=1`、
`GIT_TERMINAL_PROMPT=0`、`TMPDIR=<run_dir>/acceptance-tmp/<n>` を足す。stdout / stderr は先頭 `TEXT_CAP_BYTES`(65536)バイトまでを台帳に残し、
全体のバイト数と `truncated` を添える。
各コマンドが書くファイルの大きさは 256 MiB まで(`RLIMIT_FSIZE`。設計値)。時間上限を超えたコマンドは、そのプロセスグループごと SIGKILL で止める。

2段に重ねる(束ねない。別の行として残る)。

1. **静的な検査**(実行前。当たれば `REFUSED`、`refusal_reason` は次のどれか)

   | refusal_reason | 条件 |
   |---|---|
   | `SHELL_STRING` | witness の command が文字列(JSON の配列で書くよう `missing` に書く) |
   | `NETWORK_PROGRAM` | `argv[0]` の basename が `curl wget ssh scp sftp rsync nc ncat netcat telnet ftp aria2c gh brew` |
   | `NETWORK_SUBCOMMAND` | `git`(`clone fetch pull push ls-remote submodule remote`)、`pip`/`pip3`(`install download`)、`npm`/`yarn`/`pnpm`(`install i ci add publish`)、`python -m pip install` |
   | `NETWORK_URL` | `argv[1:]` のどれかに `://` |
   | `PATH_OUTSIDE_WORKTREE` | `argv[1:]`(と `--opt=値` の値)が `/` か `~` で始まり実パスが worktree の外、または `/` 区切りの要素に `..` |
   | `PROTECTED_ACTION` | `ProjectFrame._protected_action(" ".join(argv))` が真(`conductor.py` の既存の判定を呼ぶだけ) |

   `argv[0]` の絶対パス(例: `sys.executable`)は許す。プログラムを指すだけで、書き込み先ではないため。
2. **実行時の強制**: すべての受入コマンドを `/usr/bin/sandbox-exec` の下で実行する。プロファイル(`conductor_run.SANDBOX_PROFILE`):

   ```
   (version 1)(allow default)(deny network*)(deny file-write* (require-all (require-not (subpath (param "WT"))) (require-not (subpath (param "TMPD"))) (require-not (subpath "/dev"))))
   ```

   `WT` は worktree の実パス、`TMPD` はそのコマンドの tmp の実パス(`-D` で渡す)。受入コマンドを実行する前に1回だけ
   `sandbox-exec … /usr/bin/true` で自己検査する(`SANDBOX_CHECK`)。失敗したときと `sandbox-exec` が無いときは、どのコマンドも実行せず
   `ERROR/SANDBOX_UNAVAILABLE` とする(`ACCEPTANCE_UNVERIFIED`)。**sandbox 無しに格下げして実行することはしない。sandbox を切る
   フラグも環境変数も無い。**

静的な検査はシェルの完全な解釈ではない(CLAUDE.md の「保証していないこと」)。強制するのは sandbox である。

## 変更の取り込みとコミット(`COMPLETE` のときだけ)

- 許可パスの照合は2回: runtime の `_changed_paths`(エージェントの終了直後)と、コミット直前の `git diff --cached --name-only <base>` の全パス。
  外れがあれば `ALLOWLIST_VIOLATION` でコミットしない。
- コミットの対象は、runtime が stage した index **だけ**。受入コマンドが作ったファイルは入れない(後で増えた・変わったパスは
  `ACCEPTANCE_SIDE_EFFECTS` に数えて残す)。
- コミットは worktree(detached HEAD)の中だけで、`-c user.name="Vera conductor" -c user.email=conductor@verantyx.invalid
  -c commit.gpgsign=false -c core.hooksPath=/dev/null commit --no-verify`。どのブランチも動かない。push しない。`refs/` には何も作らない。
- コミットした worktree は残す(消すと、そのコミットに届く ref が無くなる)。パスは台帳の `COMMIT.worktree`。
  変更が無ければ `COMMIT_SKIPPED`(`reason: "no changes"`)で、worktree は消す。
- 元のリポジトリの見張り: 起動の前後で `for-each-ref` / `rev-parse HEAD` / `symbolic-ref -q HEAD` / `status --porcelain=v1 --untracked-files=all` を比べ、
  違えば `REPO_CHANGED`(エージェントは codex の workspace-write の範囲では元の `.git` に書きうる)。状態ディレクトリがリポジトリの中にあるときは、
  その下を比較から外す。
- エージェントが worktree の HEAD を動かしていれば `AGENT_COMMITTED`。
- プロンプト(`AgentRuntime._build_prompt`)に、仕事の内容・「受入条件は指揮者が自分で実行する。DONE や CLAIM は判定に使われない」・
  「履歴や参照を変える git コマンドは使わない」の3行を足した。dry-run と実起動は同じ関数を通る。

## 台帳の行(実起動の経路だけ。fake / dry-run の行は変えていない)

`CONDUCT_INVOKED, FRAME_READ, FRAME_COMPILED, RUN_LIMITS, REPO_GUARD(before), AGENT_START_CALLED, LAUNCH_PLANNED, AGENT_START_RETURNED,
AGENT_WAITING, AGENT_EXITED, AGENT_PROCESS_CHECK, REPO_GUARD(after), [SANDBOX_CHECK, ACCEPTANCE_COMMAND × n | ACCEPTANCE_ITEM,
ACCEPTANCE_SIDE_EFFECTS], [COMMIT | COMMIT_SKIPPED | COMMIT_FAILED], RUN_FINISHED`

- `ACCEPTANCE_COMMAND`: 各 `command_exit` 条件につき1行(`acceptance_record_id` `item` `argv` `cwd` `status` `refusal_reason` `error` `exit_code`
  `expected_exit` `stdout` `stderr` `stdout_bytes` `stderr_bytes` `truncated` `duration_seconds` `sandbox`)。人間判定と `command_exit` 以外の条件は
  `ACCEPTANCE_ITEM`(`status` は `HUMAN` / `NOT_EVALUATED`)。
- `AGENT_EXITED`: `runtime_terminal` `terminal_message` `exit_code` `elapsed_seconds` `changed_paths` `output_path` `output_bytes` `output_sha256` `output_tail`
  (末尾 4096 バイト)`last_message_path` `last_message_tail` `limit_text_seen` `events_seen`(種類ごとの数。判断には使わない)`guard_deadline_used`
  `stop_source` `wait_error`。
- `RUN_FINISHED`: 従来の項目に `outcome` `worktree_kept` `reason`(`driver_log` は null)。

## 既知の制限(隠さない)

- `run_project()` と `VeraSystem.conduct()` に `AgentRuntime` を渡したときの挙動は変わらない(旧 `ConductorRun` のまま: 最初の空の poll で止まる)。
  新しい経路は `conduct_entry` の codex / claude(dry-run なし)だけ。fake と、Python から渡したアダプターも従来どおり。
- 新しい経路は GOAL のタスク1件で、ORDER の前段が無いものだけ(`ORDER_BLOCKED` / `MULTIPLE_TASKS_UNSUPPORTED` / `NO_TASK`)。
  この3つの型は単体テストで個別には確かめていない(型は閉じた集合に入っている)。
- `setsid` などでプロセスグループの外に出た孫プロセスは追えない(supervisor のグループだけを検査・停止する)。
- 静的な検査はシェルの完全な解釈ではない。強制するのは sandbox。
- sandbox は macOS の `sandbox-exec` だけ。無い環境では受入条件は実行されず `ACCEPTANCE_UNVERIFIED`。
- `command_exit` 以外の機械的な witness(`file_sha256` / `text_in_file` / `git_commit`)は評価しない(`NOT_EVALUATED` → `ACCEPTANCE_UNVERIFIED`)。
- エージェント自身の実行(codex / claude)は sandbox の外。許可パスの検査は終了後。codex の workspace-write は元のリポジトリの `.git` に
  書ける範囲に入りうるので、`REPO_CHANGED` / `AGENT_COMMITTED` で事後に検出する(防ぐのではなく、検出して不合格にする)。
- 指揮者の保険の期限(`GUARD_GRACE_SECONDS`)と待つ間隔は設計値。
- claude は実起動で確かめていない(引数の組み立てだけをテストで確かめた)。権限を指定しないと、非対話の claude は書き込めない可能性がある。
- 受入コマンドの出力は先頭 65536 バイトだけを台帳に残す(全体のバイト数は残る)。

## 本物の codex での確認(R5)

結果は `artifacts/w2-a/live/` に保存した。記録は `docs/CONDUCT_RUN.md` ではなく、実装報告(`impl.r1.md`)と保存物に書く
(数値はその保存物の値だけを使うため)。題材の枠は `docs/frames/toy/greet.md`(`docs/frames/examples/` には置かない。
例の枠を全部検査するテストがあるため)。
