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

## 15. W16-t7c: 変形した鍵（全角・パーセント・base64）

### 15.1 事前登録（凍結は `artifacts/w16-t7c/prereg_sha256.txt` の sha256。第 2 ラウンドの再凍結は `prereg_sha256_r2.txt`、第 3 ラウンドの再凍結は `prereg_sha256_r3.txt`、第 4 ラウンドの再凍結は `prereg_sha256_r4.txt`、変更の記録は `prereg_changes.md`）
- **変形は 3 つだけ**: `nfkc`（NFKC 正規化）、`pct`（`urllib.parse.unquote` を変化が止まるまで最大 4 回。`unquote_plus` の同様の繰り返しも候補。名前は同じ `pct`）、`b64`（base64 らしい部分の復号。トークン全体と、トークン内の `[A-Za-z0-9+/_\-]{16,}={0,2}` の最大連続部分、およびその連続部分の区切り字（`/ _ - +`）の直後から始まる後ろ側（区切りの位置は後ろから 16 個まで。第 2 ラウンドの追加）。`=` を外した長さ 16 以上、`+/` と `-_` の混在は除く、長さ ≡ 1 (mod 4) は除く、`validate=True` で復号して UTF-8 strict で読めるものだけ）。（第 3 ラウンドの追加）区切り字の位置は後ろから 16 個に加えて先頭側 16 個も始点の候補にする。`-_` の最後の位置の直後と `+/` の最後の位置の直後（2 つの字集合が混ざる連続部分の後ろ側）も始点にする。各始点を 0〜3 字ずらした列も候補にする（英数字が区切り無しで前に接した形）。長さ ≡ 1 (mod 4) の候補は捨てずに末尾 1 字を落として復号する（後ろに余分な 1 字が接した形）。UTF-8 strict で読めないときは置換文字で読んだ文字列を変形後の文字列とする（前後に接した英数字が作る壊れたバイト。過剰に伏せる側）。既存の候補はすべて残り、strict で読めたものは同じ文字列を返す。（第 4 ラウンドの追加）各始点（ずらし後）の列 `r[s:]` に加え、`s` 以後で `-_` の字が最初に出る位置の手前までの列と、`+/` の字が最初に出る位置の手前までの列（どちらも長さ 16 以上のもの）も候補にする（`+/` を含む base64 の後ろに `-_` の区切りが接する形、逆向きも）。
- **印の形**: `[REDACTED:<型>:<nfkc|pct|b64>]`。変形の名前を 3 つの短い名前に固定する理由は、`[REDACTED:kv_secret:percent]` のような長い名前が `kv_secret` の規則に再び当たって冪等でなくなるため（実測、15.3）。
- **窓の規則**: 空白（`\s`、U+3000 を含む）と引用符 `"` `'` の連なりで分けたトークンの、連続する 1〜3 個（間の区切りを含む元の部分文字列）を窓とする。`b64` は 1 トークンの窓だけ。窓の変形後の文字列 `v` が `v != 窓` かつ既存の `_spans(v)` が空でないとき、窓を丸ごと 1 つの印にする（型は `_spans(v)` の最初の区間の名前、変形の名前は nfkc → pct → b64 の順で最初に当たったもの。順は表示だけで、伏せるかどうかに影響しない）。1 トークンの窓を先に見て、2・3 トークンの窓は印になっていないトークンだけで作る。置換は右から。変形の段は既存の処理（`_spans`・置換・残り滓）の後に、不動点ループの各回で 1 回走らせ、件数を足す。
- **漏れの定義**: 出力に、(a) 平文の鍵の任意の 8 文字の窓、または (b) 入力に現れた変形後の鍵の部分（全角の列・`%` を含む列・base64 の列）の任意の 8 文字の窓、が残ること。
- **C1 の変種**: 第 1 ラウンドは全角 9、パーセント 8、base64 7 の計 24 件。第 2 ラウンドで base64 に 3 件（`id_`・`x-`・URL のパスに接した形）を足して base64 10、計 27 件（`tests/test_w16t7c_redact_variants.py` の `VARIANTS`。各形 5 以上）。第 3 ラウンドで base64 に 8 件（R4: 日本語を含む JSON の base64 で `/+` が 16 個以上のものに `id_`・URL のパス・`x-` が接した 3 件。R5: 英数字が base64 の前に 1 字・3 字・4 字、後ろに `xyz`、前 `Q` と後ろ `zz` の 5 件）を足して base64 18、計 35 件。第 4 ラウンドで base64 に 6 件（R7: `+/` を含む日本語入り JSON の base64 の後ろに `-v2`・`_tail` が接した 2 件、前 `x-` と後ろ `-y`・前 `name-` と後ろ `-backup` の 2 件、urlsafe 版の後ろに `+v2`・`/x` が接した 2 件）を足して base64 24、計 41 件。
- **K721**: 2 つの欄に分けた鍵は検出しない（一般には分からない）。
- **過剰な伏せの測り方**: seed 0・10,000 件。長さ 1〜120 の一様、各断片を次から一様に選ぶ: 半角の印字可能 ASCII 1 字 / 全角 ASCII（U+FF01〜U+FF5E）1 字 / ひらがな・常用漢字の固定集合 1 字 / 空白 / `%` + 16 進 2 桁 / base64 の文字集合で長さ 16〜40 の列。「鍵を含まない」= 修正前（`ecde332`）の `redact` の件数が 0。その母数 M と、新しい `redact` の件数が 1 以上になった K、例を最大 20 件を出す。K は 0 でなくてよい。

### 15.2 実装した規則（`verantyx/ledger_events.py` の `redact` と補助 `_variant_stage` ほか）
- `redact` の不動点ループの各回で、既存の処理（`_spans` → 置換 → 残り滓）の後に変形の段を 1 回走らせ、置換した窓の数を件数に足す。`REDACT_PATTERNS`・`_spans`・残り滓の規則・`redact_obj` 以降は変えていない。
- トークンは `[^\s"']+`。窓は連続する 1〜3 トークン（`b64` は 1 トークンだけ）。変形後の文字列が元の窓と同じなら見ない（既存の段が意図して伏せなかった形、例えば `token:` 改行 `abcdefg`、を拾い直さないため）。印だけのトークンは 3 変形とも元と同じなので自然に飛ぶ。1 トークンの窓を先に見て、2・3 トークンの窓は印になっていないトークンだけで作る。
- `_v_b64` の候補の規則（第 3 ラウンド）: 1 つの連続部分あたり、始点は先頭・区切り字の直後（先頭側 16 個と末尾側 16 個）・`-_` の最後の直後・`+/` の最後の直後で、各始点を 0〜3 字ずらす（最大 (1+32+2)×4 = 140 候補。各復号は線形なので全体も線形）。（第 4 ラウンド）各始点について、`s` 以後で `-_` の字が最初に出る位置の手前までと `+/` の字が最初に出る位置の手前までの切り出し（長さ 16 以上）も候補にする（始点あたり最大 3 候補、全体で最大 (1+32+2)×4×3 = 420 候補。`str.find` と復号は線形なので全体も連続部分の長さに対して線形）。`_b64_decode` は長さ ≡ 1 (mod 4) なら末尾 1 字を落とし、UTF-8 strict で読めなければ置換文字で読む。置換は断片を左から集めて 1 回連結する（群は重ならず昇順なので右からの置換と同じ結果）。
- 印の名前を `nfkc`・`pct`・`b64` に固定した理由（実測）: 既存の `kv_secret` は `secret`・`token` の直後の `:` に続く 8 文字以上を値として伏せる。修正前の実装（`ecde332`）で `redact('[REDACTED:kv_secret:percent]')` は `('[REDACTED:kv_secret:[REDACTED:kv_secret]', 1)` になり冪等でない。名前を 3 つの短い名前に固定して避けた（`REDACT_PATTERNS` は許可外のため直していない）。`REDACT_PATTERNS` の全部の名前 × 3 変形の印について、`redact(m)`・`x m y`・`"m"`・`m m`（空白区切り）が件数 0 であることを `tests/test_w16t7c_redact_variants.py::test_marker_safety` と `extra_probes.log` で確かめた。

### 15.3 実測（すべて `artifacts/w16-t7c/` の下）
- **C1**（変種 41 件 = 全角 9・パーセント 8・base64 24）: 修正前 `c1_before.log`（第 1 ラウンドの 24 件）は 24 件すべて件数 0・漏れ。修正後 `c1_after.log` は 41 件すべて件数 1 以上・漏れ無し・冪等（`total 41 bad 0`）。第 3 ラウンドで足した 8 件は、r2 の実装で `r3_before_fix.log`（8 失敗・37 成功）で赤、第 4 ラウンドで足した 6 件は、第 3 ラウンドの実装で `r4_before_fix.log`（6 失敗・45 成功）で赤、第 4 ラウンドの修正後 `tests_w16t7c.log` で 51 成功。レビュー r2 のコマンド（`/+` 20 個の JSON の base64 に `id_`・URL のパス・`x-` を前置、英数字 1〜4 字の前置、`xyz` の後置）は `r3_c1c.log` で 8 行とも件数 1・漏れ無し。レビュー r3 の R7 のコマンド（`+/` 20 個の JSON の base64 の後ろに `-v2`・`_tail`、前後 `x-`…`-y`・`name-`…`-backup`、urlsafe 版の後ろに `+v2`・`/x`）は `r4_c1c.log` で 6 行とも件数 1・漏れ無し（修正前は 6 件とも件数 0・漏れ。`r4_before_fix.log` の失敗 6 件）。印の安全性は `r3_markers.log`（`markers ok`）。試験は修正前 `red_before.log` で 31 失敗・3 成功（成功は変種数の確認・K722 の確かめ・K721 の確かめ。第 1 ラウンドの 34 件）、第 2 ラウンドで足した 3 件は r1 の実装で `r2_before_fix.log`（3 失敗）、第 2 ラウンドの修正後は 37 成功。
- **回帰**: 関係テスト 5 ファイルは修正前 `regress_before.log` 107 成功、修正後 `regress_after.log` 107 成功。
- **ファズ**（seed 0/1/2 × 30,000、`artifacts/w16-t7/fuzz_r4.py` を書き換えず実行）: `fuzz_r4_after.log` はすべて leak 0・nonidempotent 0・unbounded 0。
- **K722**（同じ生成規則での新旧の出力・件数の不一致）: `k722_compare.log` は seed 0/1/2 とも diff_out 0・diff_n 0。この生成には全角・`%XX`・base64 の変形は含まれないので、これは「鍵を含む入力で変形の段が既存の結果を変えない」ことの確認。
- **過剰な伏せ**（15.1 の事前登録の生成規則、seed 0・10,000 件。第 4 ラウンドの修正後に取り直し）: `overredact_random.log` は M（修正前の件数が 0）= 10,000、K（修正後の件数が 1 以上）= 0。base64 の文字集合の列（無作為の長さ 16〜300・sha256 の 16 進・`/` 区切りのパス・英数字だけ 16〜64 を等分、seed 0・20,000 件。`overredact_b64runs.py`）も M = 20,000、K = 0（`overredact_b64runs.log`）。置換文字で読む規則を足したが、この 2 つの測りでは過剰な伏せは増えなかった。無作為の文字列には変形で鍵の形になるものが無かった（この生成は鍵の形に近い列を作らないので、地の文ごと伏せる過剰な伏せの上限を示すものではない。下の限界を参照）。
- **計算量**（`perf.log`・`perf_r2_sep.log`、旧と新を並べる。第 4 ラウンドの修正後に取り直した値）: `password=`×11,000 は旧 4.34 秒・新 4.34 秒、`sk-`×33,000 は旧 2.97 秒・新 2.97 秒、全角の `ｐａｓｓｗｏｒｄ＝`×11,000 は旧 0.00 秒（件数 0、漏れ）・新 4.34 秒（件数 1。既存の `password=` と同じ 2 乗の挙動が、変形の後に当たるようになったため）、全角の文 200,000 字は旧 0.01 秒・新 0.31 秒、空白区切りの短い語 50,000 個は旧 0.01 秒・新 0.19 秒。当たりの多い入力（空白区切りの全角の鍵）は 20,000 個（40 万字）で新 0.19 秒・40,000 個（80 万字）で新 0.39 秒（件数はそれぞれ 20,000・40,000）。第 1 ラウンドの実装では置換の再構成が 2 乗で、88 万字で 10 秒を超えた（レビュー r1 の実測）ため、第 2 ラウンドで断片を左から集めて 1 回連結する形に直した。`perf_r2_sep.log`（台本 `perf_r2_sep.py`）: 区切り字を多く含む 1 トークン 10 万字（`a-`×50,000 は 0.13 秒、`a/`×50,000 は 0.15 秒、`AbCd_`×20,000 は 0.24 秒）、`+/` を含む base64 の文字集合の無作為 10 万字 1 トークンは 0.21 秒、空白区切り 64 字のトークン 5,000 個は 0.43 秒（いずれも件数 0）。`perf.log` の最大は `password=`×11,000 の旧新 4.34 秒と全角の `ｐａｓｓｗｏｒｄ＝`×11,000 の新 4.34 秒。`perf_r2_sep.log` の 100 万字の 1 トークン: `AAA+/`×200,000 は 1.68 秒、`Ab-_`×250,000 は 1.52 秒、`a-b/`×250,000 は 0.09 秒（いずれも件数 0）。10 秒を超える入力は、既存の 2 乗の作りに由来する `password=` 系（4 秒台）を除いて無い。
- **経路**（`manual_repro.log`。第 4 ラウンドの修正後に取り直し）: `vera run --keep-args`・PostToolUse hook（`--keep-args`）・UserPromptSubmit hook の 3 経路 × 3 形すべてで、台帳の全バイトに平文の鍵も変形後の列も無い（`BAD 0`）。
- 事前登録の後の試験の変更は `prereg_changes.md`（`test_marker_safety` の `m + m` を `m + " " + m` に変えた 1 件。理由は実測つきでそこに書いた）。

### 15.4 残る限界
- **K721**: 2 つの欄に分けた鍵（例えば JSON の 2 つのキーに `sk-` と本体を分けたもの。t7-secret-split）は検出しない。一般には分からない。実測: `extra_probes.log`（空白で分けた `sk- <本体>`）と試験 `test_k721_split_key_is_not_detected_and_is_disclosed`（件数 0）。
- **変形の合成は見ない**（実測、`extra_probes.log`）: 全角と `%20` を 1 トークンに混ぜた形（`ｓｋ－%20…`）、全角の `Ｂｅａｒｅｒ%20` + 本体、全角の `Ｂｅａｒｅｒ` + `%7A` の本体、base64 の中が全角の鍵は、いずれも漏れた（`extra_probes.log`）。（パーセントの外側に base64 がある形、すなわち base64 の末尾の `=` を `%3D` にし改行 `%0A` を付けた形は検出された。base64 らしい部分を `[A-Za-z0-9+/_\-]{16,}` の最大連続として元のトークンから取り出すため。実測: `extra_probes.log` の `pct of b64 (compose)` の行）
- **base64 の折り返し**: `b64` は 1 トークンの窓だけなので、改行や空白で折り返した base64（鍵が折り返しをまたぐ形）は見ない。実測: 8 字ごとに改行した鍵の base64 は件数 0・漏れ（`r2_probes.log`）。
- **base64 の前後に接する文字**: 第 1 ラウンドは `id_`・`x-`・URL のパス（`…/download/`）に直接接した base64 を見逃した（レビュー r1 の実測）。第 2 ラウンドで区切り字の直後から始まる後ろ側（末尾側 16 個）を候補にして直したが、レビュー r2 は、区切り字（`/+`）が 16 個を超える日本語入りの JSON の base64 への前置（k=20・40・80）と、英数字が区切り無しで前後に接する形（前置 1〜5 字、後置 `xyz`）が漏れることを実測した。第 3 ラウンドで候補の始点を広げ（先頭側 16 個・字集合の切り替わりの直後・0〜3 字ずらし）、`len % 4 == 1` の切り落としと置換文字での読みを足して直した。レビュー r3 は、`+/` を含む base64 の後ろに `-` `_` が接する形（`<b64>-v2`・`x-<b64>-y`・`name-<b64>-backup`。urlsafe 版の後ろに `+` `/` が接する形も）が、鍵が最後の `+/` より前にあると漏れることを実測した（候補が後ろ側の切り出しだけで、混在で捨てられるため）。第 4 ラウンドで終点の候補（始点以後でもう一方の字集合の字が最初に出る位置の手前まで）を足して直した。`extra_probes.log`（台本 `extra_probes.py`）で、`/+` が 5・20・40 個の JSON の base64 に `id_`・`https://h.example/f/`・`x-` を前置した 9 件、前置 1〜5 字・後置 `xyz`・`x`・前 `Q` 後 `zz` の 8 件、`id_abc`・`x-ab`・`a_`×20・`a/`×20・`id_`+後置 `xyz`・URL のパス 17 段・後置 `_tail` の 7 件、R7 の 13 件（`D`+`-v2`・`_tail`・`_x`・`-`、urlsafe 版+`/tail`・`+v2`・`/x`・`+`、`id_`…`_v2`、`x-`…`-y`、`name-`…`-backup`、対照の鍵が JSON の末尾側、`/+` の無い本体+`-v2`）、前置 5・8 字の英数字と区切りが混ざる前置（`abcde`・`abcdefgh`・`ab-cd`・`ab_cdef`）、b64 の連続部分が 1 トークンに 2 つあり鍵が 2 つ目の形（`&` 区切り・`.` 区切り）の計 6 件が、すべて件数 1・漏れ無し・冪等。この台本で漏れを出せた形は、改行で折り返した形（上の限界）だけだった。確かめた形の外（例えば `+/` と `-_` が両方混ざる本体、前置・後置の両方が 16 個を超える複数種の区切りを持つ形）は、この台本では確かめていない。
- **NFKC が `-` に写さない字とゼロ幅の字**: U+2010 を使った `sk‐…`、U+200B を挟んだ `sk-​…` は漏れた（実測、`extra_probes.log`）。変形の一覧を足して直すのは語の一覧を足すのと同じ作りなので、本チケットでは直していない。
- **一覧に無い符号化**: 16 進（実測: 漏れた）、base32、HTML 実体参照、`\uXXXX` の逃がし、ROT13 は確かめていない（見ない）。4 トークン以上にまたがる形も見ない。
- **過剰な伏せ**（第 3 ラウンドで、strict で読めない復号を置換文字で読む規則と始点のずらしを、第 4 ラウンドで終点の候補を足した。第 4 ラウンドの修正後も base64 の文字集合の列 20,000 件では K = 0。上の 15.3）: 実例（実測）: `設定（password：未設定）を確認する`（全角の `：` と括弧、空白なし）は修正前は件数 0、修正後は文全体が 1 つの `[REDACTED:kv_secret:nfkc]` になる（半角の `password:` なら修正前も値が伏せられるので、規則としては一貫している）。鍵の形が変形の後にだけ現れるトークンは、地の文ごと 1 つの印になる（日本語の文中にすき間なく埋まった全角の鍵では、同じトークンの文字が消える。C1 の `fw_japanese_nogap` で実測: 出力は `[REDACTED:sk:nfkc]` に置き換わる）。無作為の列では 0 件だったが、鍵の形に近い列での頻度は測っていない。
- 印の直後に区切り無しで英数字が 3 文字以上続く入力（例えば `[REDACTED:gh_token:nfkc]` に別の印が隙間なく接した形）は、既存の `kv_secret` の規則に再び当たる。変形の段は区切りで分けた窓を置き換えるので、この形を自分では作らない（`prereg_changes.md`）。
- 計算量は既存の 2 乗の挙動のまま（上の実測）。

### 15.5 監査役の訂正と開示（2026-10-06 05:51:33 +0900、統合の前。レビュー r1（第 5 ラウンド）の申し送り R9・R10 を、監査役が現在の木で再現したうえで追記。上の本文は消さない）
- **15.2 の「全体も線形」と 15.3 末尾の「10 秒を超える入力は password= 系を除いて無い」は、次の形については正しくない（R10）**: 1 つのトークンの中に、短い base64 らしい連続部分が多数あると、候補の数が連続部分ごとに積み上がり、時間が 2 乗に伸びる。レビュアーの実測: 連続部分の数 k = 2,000・4,000・8,000 で 0.27・0.99・3.89 秒（k を 2 倍にすると約 4 倍）。10 秒を超える k は測っていないが、2 乗の伸びなので k が約 13,000 を超えると 10 秒を超える見込み（推測。測っていない）。hook には 10 秒の timeout があり、超えると hook は打ち切られ、その出来事は台帳に残らない（打ち切りのときの終了の扱いは Claude Code 側で、ここでは測っていない）。
- **未開示だった漏れの形（R9）**: 鍵の base64 の前に、別の字集合の区切り字が 16 個を超えて並び、後ろに同じ字集合の区切り字が接する形（例: ハイフンで 18 個つないだ名前＋base64＋`-v2`、URL の 17 個の `/` の区切り＋base64＋`/download`）は漏れる（レビュアーの実測で件数 0）。始点の候補を区切り字の先頭側・末尾側 16 個に限っているため。
- どちらも狭める修正は行わず、開示として残す（秘密の伏せは「過剰に伏せる側に倒す最善の努力」で、漏れない保証ではない）。
