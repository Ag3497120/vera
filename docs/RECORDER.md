2026-10-05 23:02（事前登録。数値は書かない。実測は artifacts/w16-t7/ のファイルを添えて追記する）

# 記録の自動化（W16-t7 / T7）: 追記専用・ハッシュ連鎖の台帳

起票の根拠: オーナーの中断が記憶に残らなかった、記録は監査役の手書きでオーナーの言葉が 0 件、「全停止」が計測の子プロセスを捉えなかった。
全部ローカル。ネットワークを使わない。

## 1. 台帳（K700）
- 置き場所: `<dir>/events.jsonl` と `<dir>/HEAD`（既定 `./.vera/ledger`）。決め方は `--ledger-dir` > 環境変数 `VERA_LEDGER_DIR` > `./.vera/ledger`。
- 補助: `<dir>/.lock`（flock）、`<dir>/runs/<run_id>.json`（`vera run` の採取状態。連鎖の外）、`<dir>/rejects.jsonl`（hook 経路で受け付けなかった入力。連鎖の外）。
- スキーマ名: `vera.ledger.event/1`（行には入れない。行はちょうど 6 キー）。
- 行の形: `{ts, kind, actor, data, prev, sha}`。`sha = sha256(正準JSON({ts,kind,actor,data,prev}))`、正準 JSON は `sort_keys=True, ensure_ascii=False, separators=(",",":")`。最初の行の `prev` は 64 個の `0`。
- kind（閉じた一覧）: owner_utterance, agent_stop, tool_call, process_start, process_exit, process_interrupted, process_orphaned, approval, commit, test_run。一覧外は `UNKNOWN_KIND` で拒否。
- actor.type（閉じた一覧）: owner, agent, process。`model` は在るときだけ。
- 追記は flock の中で、末尾の sha を読み、1 行を書いて fsync し、HEAD を一時ファイル＋`os.replace` で更新する。

## 2. verify の型と終了コード
- OK, EMPTY（行 0 かつ HEAD 無し）。終了コード 0。
- 行: LINE_UNPARSABLE（途中の壊れた行）、TORN_TAIL（最終行だけ改行無しで JSON 不正。書き込み中の中断の疑い）、BAD_SHAPE（キーが 6 つでない、kind・actor.type が一覧外）、SHA_MISMATCH（書き換え）、PREV_MISMATCH（削除・入れ替え・挿入）。LINE_UNPARSABLE・BAD_SHAPE・SHA_MISMATCH・PREV_MISMATCH の status は TAMPERED。TORN_TAIL だけの status は `TORN_TAIL`（TAMPERED ではない）。
- HEAD: HEAD_MISSING、HEAD_MISMATCH（最終行と違う。途中の行と一致なら `HEAD_POINTS_TO_LINE`、どれとも一致しなければ `HEAD_NOT_IN_CHAIN`）、EXPECTED_HEAD_MISMATCH（`--head <sha>` で外から固定した値と違う）。行の問題が無く HEAD だけなら status は HEAD_MISMATCH（EXPECTED_HEAD_MISMATCH もここ）。
- **status の閉じた一覧**: `OK` / `EMPTY` / `TAMPERED` / `TORN_TAIL` / `HEAD_MISMATCH`。複数当たるときの優先順は TAMPERED > TORN_TAIL > HEAD_MISMATCH（コード: `ledger_events.verify` の末尾の分岐）。終了コードは OK・EMPTY 以外は 1。T6 の `vera attest --ledger` はこの一覧に合わせる。
- 終了コード: OK/EMPTY が 0、それ以外 1。

### 検出できないこと（正直に）
- 最終行を書き換え、sha を再計算し、HEAD も作り直した改ざんは、HEAD を外に固定していなければ検出できない。連鎖全体を最初から作り直した場合も同じ。
- 対策: HEAD を git にコミットして固定し、`vera events verify --head "$(git show HEAD:.vera/ledger/HEAD)"` で照合する。
- 最終行を落として HEAD を前の行の sha に合わせて作り直した切り詰めも、外部固定が無ければ検出できない。
- 台帳は書き込む権限のある者による「過去の捏造」を防がない。検出するだけで、防止はしない。

## 3. vera run（K701）と sweep
- `vera run [--label L] [--ledger-dir D] [--sample-interval S] [--keep-args] -- <cmd…>`。コマンド無しは `NO_COMMAND`（終了コード 2）。
- 子を起動し、`ps` のプロセス木を定期採取して `(pid, lstart)` の組で既知の子孫を貯める。pid だけで生死を判定しない。
- 終わりの行は run ごとにちょうど 1 つ: process_exit（正常終了）／process_interrupted（子がシグナル死: target=job、`vera run` 自身が SIGINT/SIGTERM: target=recorder）。そのとき生きている既知の子孫（と生きている子）は process_orphaned。
- `vera run` 自身が SIGKILL されたら自分では書けない。`vera events sweep` が RECORDER_VANISHED の process_interrupted と、状態ファイルの最後の採取から生きている子孫の process_orphaned を足す。
- sweep はさらに、終了の行が無い process_orphaned について、居なくなっていれば process_exit（`exit_code: null`, `exit_code_status: UNOBSERVABLE_NOT_A_CHILD`）を足す。まだ居るものは `still_alive` に出す。冪等。
- 終了コード: 子の終了コード、シグナルなら 128+番号。

## 4. hook の雛形（K702）
- `vera hooks print --claude-code` は妥当な JSON（hooks 節）を出すだけ。`vera hooks print --codex` は TOML の `notify` 1 行（コメント付き）を出すだけ。Codex の notify は 1 つしか置けない。既にある場合は置き換えると既存の通知先が止まる。ファイルは読まない・書かない。
- `vera hooks install --project <dir>` は `--write` が無ければ何も書かない（`NOT_WRITTEN_NO_FLAG`）。書き先は `<dir>/.claude/settings.json` だけ。ホーム（環境変数 HOME）自体またはその `.claude` 配下は `REFUSED_USER_SETTINGS`（終了コード 2）。壊れた既存ファイルは `REFUSED_UNPARSABLE_SETTINGS`。他のキー・既存の hooks は残し、冪等。
- hook から呼ばれる `events add … --from claude-code|codex` は、標準出力に何も出さず、常に終了コード 0。失敗は標準エラーと `rejects.jsonl` に型つきで残す。
- 写像: UserPromptSubmit は owner_utterance（逐語）。Stop/SubagentStop は agent_stop。PostToolUse(Bash) は `git commit` に当たれば commit、pytest／npm test／go test／cargo test に当たれば test_run、両方に当たれば同点で棄権し tool_call（`ambiguous`）、それ以外は tool_call。SessionStart は process_start、SessionEnd は process_exit（kind が閉じているための写像。`exit_code_status: NOT_A_PROCESS_EXIT_CODE`）。
- 終了コード: PostToolUse の `tool_response` に整数の exit_code／exitCode／returncode が在ればそれ、無ければ `UNKNOWN_NOT_IN_PAYLOAD`（推測しない）。確実な終了コードは `vera run -- pytest …` で取る。
- approval は手動の入口だけ（`vera events add approval --actor-type owner --actor-id <名> --text …`）。hook には未配線（承認の hook の形を実測で確かめられないため）。
- Codex の notify は JSON を argv の最後の引数で渡す。agent-turn-complete だけ agent_stop にする。発話は作者が不明なので owner_utterance にしない（数と sha だけ）。

## 5. 秘匿
- 引数の本文は既定で保存しない（sha256 だけ）。`--keep-args` のときだけ、`redact` を通して保存する。
- REDACT_PATTERNS の名前: sk-ant, sk, github_pat, gh_token, aws_akia, google_api_key, slack_token, bearer, kv_secret（api_key/token/secret/password の値部分）, private_key。置換は `[REDACTED:<名前>]`。
- 判断: owner_utterance の逐語も、秘密の形の部分だけ伏せる。伏せた個数は行の `data.redactions` に必ず入れる（0 でも）。見えない解決をしない。

## 6. 照会
- `vera events tail [-n N]`／`show <sha 接頭辞>`（`AMBIGUOUS_PREFIX`／`NOT_FOUND`）／`verify [--head SHA]`／`grep <kind>`／`sweep`／`add`。出力は 1 行 1 JSON。`--ledger-dir` は `events` の直後でも各サブコマンドの後ろでも受ける。

## 7. 名前
- 既存の最上位 `vera ledger`（W10-f04 の証言の台帳）と衝突するため、チケットの規則どおり本機能は `vera events` にした。`vera run`・`vera hooks` は新規。

## 8. 導入
- このプロジェクトと Codex への hook の設置は、オーナーの許可を得てから監査役が行う。この実装は何も導入しない。

## 9. 実測（追記。事前登録の後。出力は artifacts/w16-t7/ のファイル）
- 新しい試験一式 4 ファイル: 51 件すべて通過（artifacts/w16-t7/tests_w16t7.log）。実装前は ImportError で失敗（artifacts/w16-t7/red_before_impl.log。run と並行追記の試験は実装前には流していない）。
- 手での再現（SIGTERM → 孤児 → sweep → verify OK、hook の逐語、行の削除の検出、install の無書き込み）: artifacts/w16-t7/manual_repro.log。
- ホームを展開する呼び出しが 3 モジュールに無いこと: artifacts/w16-t7/static_home_grep.log（grep_rc=1）。
- 関係する既存試験 179 件通過: artifacts/w16-t7/regress_related.log。
- 凍結後の試験の変更 2 件（どちらも試験側の誤り。期待は弱めていない）: artifacts/w16-t7/prereg_changes.md。

## 10. 既知の穴
- 採取の間に生まれて消える短命なプロセスは見えない（採取間隔 `--sample-interval` が下限）。
- Claude Code の PostToolUse が、失敗したコマンドでは呼ばれない版がありうる。終了コードが payload に無ければ `UNKNOWN_NOT_IN_PAYLOAD`。確実な終了コードは `vera run -- <cmd>` で取る。
- approval は未配線（手動の入口だけ）。
- 最終行の改ざん＋sha と HEAD の再計算は、HEAD を外に固定していなければ検出できない（§2）。
- 最終行が改行で終わっていない（TORN_TAIL）台帳には、追記を拒否する（`TORN_TAIL_BLOCKS_APPEND`）。黙って直さない。人が確かめて直す。
- PostToolUse の分類は文を `&&`・`;`・`|` で割った各区間の先頭語で見る浅い規則。`bash -c "git commit"` のような入れ子は `tool_call` になる（誤って commit と言わない側に倒す）。

## 11. 第 2 ラウンドでの変更（レビュー r1 への対応）
- 追記の安全網は伏せる処理と同じ表現（文字列ごとの `redact_obj`）で判定する。正準 JSON（エスケープ後）には正規表現をかけない。
- `vera run` は子を起動する前に process_start を検査し（`preflight`）、追記できない台帳（TORN_TAIL・書けない・秘密の形が残る）なら子を起動せず、型つきの JSON を標準エラーに出して終了コード 2 で終える。起動後の追記失敗は traceback で抜けず、監督を続けて `LEDGER_APPEND_FAILED_AFTER_START` を標準エラーに出す（子の終了コードが 0 なら 3）。シグナルのハンドラは子の起動前に設定する。
- `hooks install` は `<project>/.claude` や settings.json がシンボリックリンクなら `REFUSED_SYMLINK_SETTINGS`、実体がホームの `.claude` 配下なら `REFUSED_USER_SETTINGS`（終了コード 2、`--write` の有無によらず）。

## 12. 第 3 ラウンドでの変更（レビュー r2 必須 1 への対応）
- `redact` を不動点まで繰り返す（上限 8 回。上限に達しても変わり続けるなら全体を `[REDACTED:unbounded]` にする）。つながった秘密の 2 つ目は左の境界に阻まれて 1 回目では残るため。これで `redact(redact(x)[0])[1] == 0` が成り立つ（安全網の前提）。
- 残り滓の規則: 伏せた印 `[REDACTED:…]` にすき間なく続く 8 文字以上の英数字・`_`・`-` の連なりは落とす（印は残す）。`ghp_`＋`sk-…` のように前の鍵の本体が後ろの鍵の接頭辞を飲み込み、後ろの本体が接頭辞なしで残る組を塞ぐ。安全側に倒すので、印の直後に付いた正当な長い語も落ちる（偽陽性は許容）。
- 実測: 試験 65 件通過（`artifacts/w16-t7/tests_w16t7.r3.log`）、冪等性のファズ 30 万件で非冪等 0・2 つ連結の全組み合わせで本体の残留 0（`fuzz_idempotent.r3.log`）、手の再現（`manual_repro.r3.log`）。
- 既知の穴（r2 任意 5）: 鍵語が重なる `password: password: <値>` は 2 つ目の鍵語が伏せられ値が残りうる。直していない。

## 13. 第 4 ラウンドでの変更（監査役の裁定: 秘匿の左境界）
§5 の本文は書き換えない。境界に関する §5・§12 の記述と、§12 の既知の穴（`password: password: <値>`）は、この節で上書きされる（§12 の本文は書き換えない）。

1. **規則**: 左の境界は無い。鍵は接頭辞・長さ・文字種だけで判定する（`_B` は空。bearer の `\b` も外した）。全部の型を **元の文字列に独立に** 当て、重なりを許して集めた区間を併せ、一度に置き換える（`_spans`）。同じ区間なら一覧で前の型の名前が残る（`K=1sk-ant-…` は `sk_ant`）。接するだけの区間は別に数える。
   - 理由: 順に置き換える作りだと、前の鍵の本体が後ろの鍵の目印（`Bearer`・`password` など）を飲み込み、後ろが残る。
   - 境界を外して英数字・`\n`・`%0A`・日本語の直後の鍵が伏せられるようになった。試験は 9 鍵 × 17 区切り × 9 前置を、単独（1,377 件）と 2 個つなぎ（12,393 件）の全組で確かめる。ファズは `artifacts/w16-t7/fuzz_r4.py`、結果は `fuzz_r4.log`（seed 0/1/2 × 30,000 件で leak 0・nonidempotent 0・unbounded 0）。
   - 手の再現は `manual_repro.r4.log`（`vera run --keep-args`・PostToolUse hook・UserPromptSubmit の 3 経路で台帳に完成形が残らない）。
2. **過剰な伏せ（裁定で許容）**: 実測（`perf_r4.log`）。`task-management-system-abcdef` → `ta[REDACTED:sk]`、`risk-assessment-procedure` → `ri[REDACTED:sk]`、`ask-questions-about-it-now` → `a[REDACTED:sk]`。owner_utterance の逐語はこの形で変わりうる。伏せたことは `data.redactions` の件数で残る（伏せた語は別に保存しない）。
3. **計算量**: 一致のたびに開始位置+1から探し直すため、病的な入力で 2 乗になる。実測（負荷 6.83、`perf_r4.log`）: `password=` ×11,000（99,000 字）5.38 秒、`sk-` ×33,000＋`a`×20（99,020 字）3.11 秒。ふつうの日本語・英字 200,000 字は 0.01 秒。速くする工夫はしていない。
4. **残る限界**:
   - 一覧に無い形式（JWT・Basic 認証など）は伏せない。
   - 安全網は actor（`session_id`・`thread-id`・`model`）を伏せずに拒否する。境界を外したので、actor に鍵の形の文字列が入ると、その行は台帳に入らず `rejects.jsonl` に回ることが前より起きやすい。変えていない。
   - 残り滓の規則（伏せた印の直後の長い英数字を落とす）による過剰な伏せ。
5. **§12 の既知の穴の解消**: `password: password: <値>` は `_spans` が重なりを許すため第 4 ラウンドで解消した（残る限界ではない）。実測: `redact("pass"+"word: pass"+"word: hunter2hunter2")` → `('password: [REDACTED:kv_secret] [REDACTED:kv_secret]', 2)`、鍵語が 3 つ重なる形 → 件数 3 で値は残らない。試験 `test_r4_password_password_value_redacted`（第 3 ラウンドの `ledger_events.py` では値が `password: [REDACTED:kv_secret] hunter2hunter2` と残って落ちる。`artifacts/w16-t7/red_before_impl.r4b.log`）。

## 14. W16-t7b: hook のコマンドの固定・終了コード 2 を返さない・導入前の自己検査
2026-10-06（起票: 監査役。再現: 雛形のコマンドを偽の/古い `verantyx/` のある cwd で実行すると `events` が無く終了 2。Claude Code の hook で終了 2 は「入力を止める」特別な値）。
既存の節は書き換えない。§4 の「常に終了コード 0」は、本節の表で補う。

### 14.1 読み込むコードの固定（K710）
- `hooks print`／`install` は、実行中の `vera` 自身の解決を既定で埋め込む。`python = sys.executable`（`absolute()` のみ。`resolve()` しない: venv の `bin/python` はシンボリックリンクで、辿ると venv の外の Python になり site-packages を失う）、`code_root =` 読み込まれた `verantyx` パッケージの親ディレクトリ。`--python <path>` と `--code-root <dir>` で上書き（2 つは同時に指定できる。`--vera-cmd` はそのどちらとも同時に指定できず、指定すると終了 2）。
- 形 1（Python 3.11 以上、`dash_P`）: `PYTHONPATH=<root> <python> -P -m verantyx.cli events add …`。`-P` は cwd を `sys.path` に置かない。Codex は `["/usr/bin/env", "PYTHONPATH=<root>", <python>, "-P", "-m", "verantyx.cli", …]`（シェルを通らない）。
- 形 2（3.10 以下／版が読めない、`dash_c_syspath`）: `<python> -c "import sys,runpy; sys.path[0]=<root>; runpy.run_module('verantyx.cli', run_name='__main__', alter_sys=True)" events add …`。版は `sys.version_info`（自分自身）か、`--python` の子プロセス 1 回（5 秒）で読む。読めなければ `UNKNOWN_PROBE_FAILED` で形 2 に倒す。3.10 そのものでの実行はしていない（3.11 上で形 2 が動くことだけをテストで確認）。
- 引用は `shlex.quote`（空白・`$` を含むパスでも展開されない）。
- 凍結された実行物（`sys.frozen`）で `--python` と `--code-root` の **どちらか片方でも** 欠けるときは `PIN_UNRESOLVABLE_FROZEN`（終了 2、何も出さない）。凍結物の動作は検証していない。
- **`_vera` の置き場所**（チケットは「出力の JSON の注記」）: 既存テスト `validate_claude_hooks` が `hooks print --claude-code` の標準出力を `{"hooks": …}` だけに閉じているため、標準出力は変えず、**標準エラーに 1 行 `{"_vera": {…}}`**。`hooks install` の結果の JSON（標準出力）には `_vera` を入れる。`settings.json` には入れない（Claude Code の設定に未知のキーを足さない）。`print --codex` は TOML のコメント行 `# _vera: {…}`（利用者の config.toml のキーにしない）。

### 14.2 終了コード（K711）
| 呼び出し | 失敗の種類 | 終了コード |
|---|---|---|
| hook のコマンド（` … || exit 1`） | 非 0 になるあらゆる失敗（python が無い、モジュールが無い、引数の誤り） | 1 |
| `events add --from claude-code` | 引数の誤り（kind の不正、未知のオプション） | 1（今まで 2） |
| `events add --from claude-code|codex` | 取り込みの失敗（JSON でない、台帳に書けない等。rejects.jsonl／標準エラーに残す） | 0（変えない） |
| `events add`（`--from` 無し・`--from codex`）、他のサブコマンド | 引数の誤り | 2（変えない） |
- **チケットの H2（読み取り専用の台帳で各 hook が終了 1）の字面は満たしていない**: 既存テスト `test_hook_unwritable_ledger_still_exits_zero` と `test_hook_never_fails_and_logs_rejects` が 0 を要求し、既存の期待は変えない裁定のため、`ingest_cli` が 0 を返す経路は 0 のまま。実測は 0（`tests/test_w16t7b_hook_pinning.py::test_h2a_readonly_ledger_not_two`。2 ではないことは満たす）。監査役の裁定待ち（`H2_LITERAL_CONFLICTS_WITH_W16T7_TEST`）。

### 14.3 導入前の自己検査（K712）
- `hooks install --project <dir> --write` は、書く前に 6 つのコマンドを `<dir>` を cwd・偽の入力で 1 回ずつ実行する（台帳と `CLAUDE_PROJECT_DIR` は一時ディレクトリ。環境から `PYTHONPATH`・`PYTHONHOME`・`PYTHONSAFEPATH` を除く）。合格 = 終了 0・標準出力が空・`events.jsonl` がちょうど 1 行増える・`rejects.jsonl` が増えない。timeout は hook と同じ 10 秒。
- 1 つでも落ちたら何も書かず `REFUSED_HOOK_SELFTEST`（終了 2、`selftest.cases` に各コマンドの `returncode`・`stderr_tail`（秘匿済み）・`rows_added`）。`--write` が無いときは自己検査もしない。
- 既存の古い雛形（` || exit 1` の無い T7 のコマンド）は消さない・書き換えない。結果の `stale_vera_hooks` にその数を出す。

### 14.4 既知の穴
- 読み取り専用の台帳（`events.jsonl` が既にある状態）では、行は書かれるが HEAD の更新だけ失敗し、終了 0 になる（W16-t7 の既存の挙動。K713 のため直していない）。次の追記で HEAD は追いつく。
- 固定した `code_root` は絶対パス。そのクローンを動かす・消すと hook は全部落ちる（` || exit 1` で 1。止めないが記録されない）。再実行で作り直す。
- `hooks print`／`install` を別の場所の `vera` から実行すると、その場所のコードが固定される。`print` は実行する `vera` を確かめない。
- 自己検査は固定が効くこと・終了 0・台帳 1 行までを見る。Claude Code 実機の hook の環境（PATH 等）は再現しない。
- 数値の根拠: `artifacts/w16-t7b/`（`red_before.log`: 修正前 7 つすべて終了 2、`manual_repro_after.log`: 修正後すべて 0、`tests_w16t7b.log`、`regress_w16t7.log`、`time_per_hook.log`）。
