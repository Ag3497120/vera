# claude_code: Claude Code に Vera を唯一の出口として渡す / Vera as the only exit of a Claude Code subagent (E2)

目的: サブエージェントが文書について答えるとき、**答えとして扱うのは検証済みの `emit` の文だけ**にする。

1. インストール: `pip install -e ".[mcp]"`（リポジトリの直下で）。`vera --version` が通ること。
2. このフォルダの `.mcp.json` を Claude Code のプロジェクトに置く（または `claude mcp add vera-loom -- vera mcp --docs … --question …`）。
   * サーバー名 `vera-loom` がツール名の前置き `mcp__vera-loom__` になる。
   * 織機のタスクは **起動時に固定** される（`--question` ごとに q1, q2, …）。問いを増やすときはサーバーを起動し直す。自由な問いには `vera ask` / `vera run` を使う。
3. `.claude/agents/vera-weaver.md` をプロジェクトの `.claude/agents/` に置く。`tools:` は `mcp__vera-loom__*` の 20 個だけ（Bash・Write・WebFetch などは無い）。本文は測定に使った織り手の指示そのもの。
4. Claude Code で: 「vera-weaver エージェントで task q1 に答えて」。
5. **答えを取り出すのは台帳から**:

   ```
   vera loom output runs/<run_id>      # 検証済みの emit の文だけ。連鎖が壊れていれば出ない
   vera verify runs/<run_id>           # 連鎖と再生
   ```

6. 記憶: `.mcp.memory.json`（サーバー名 `vera-mem`）と `.claude/agents/vera-memory-writer.md`。サブエージェントが 1 回に 1 事実を `write` し、あとで `vera mem --store ./memory-store --ask "…"` で問う。

## この段（E2）が保証すること / しないこと

* 保証する: サブエージェントが使える道具は Vera の道具だけ。自由な文は台帳に長さとハッシュだけが残り、Vera は読まない。`vera loom output` は検証済みの `emit` 以外を出さない。
* 保証しない: Claude Code の画面・会話記録には、サブエージェントが書いた文が残る。親エージェントや人がそれを読んで「答え」とみなすことは Vera には止められない。**答えは `vera loom output` で取る**という運用で初めて成り立つ。
* OS の壁ではない。強い壁が要るなら E3: `vera loom mcp --tasks … --runs-dir … --isolated`（macOS の sandbox-exec。プローブが通らなければ起動しない）。`.mcp.json` の `command` / `args` をそれに替える。タスクファイルは `vera mcp --docs …` が `runs/_tasks_*.jsonl` に書く。

Give a Claude Code subagent Vera as its only exit: the agent's tool allow-list is the loom's 20 tools; take the answer from `vera loom output`, not from the transcript. The task bank is fixed when the server starts.
