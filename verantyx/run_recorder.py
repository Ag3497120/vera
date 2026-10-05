"""W16-t7 K701: `vera run`（子孫を含めてプロセスを台帳に記録）、`vera events`（台帳の照会・追記・sweep）、`vera hooks` の CLI 登録。

- 子は shell=False で起動し、start_new_session は使わない（端末の Ctrl-C は子にも届く）。
- 子孫は `ps` の ppid 木を定期採取し、(pid, lstart) の組で「既知の子孫」の集合に足していく（消えても集合からは消さない）。
  ジョブが死ぬと子孫は launchd に付け替わるので、死んだ後に木を引くのでは遅い。生死は必ず (pid, lstart) で判定する。
- `vera run` 自身が SIGKILL された場合は自分では書けない。`vera events sweep` が RECORDER_VANISHED として拾う。
ネットワークを使わない。利用者の設定ファイルには触れない。
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Optional

from . import ledger_events as L

PS_CMD = ["ps", "-A", "-ww", "-o", "pid=,ppid=,lstart=,command="]
GRACE_S = 2.0


# ---- プロセスの採取 ----------------------------------------------------------
def _norm_lstart(parts) -> str:
    return " ".join(parts)


def snapshot() -> Optional[list]:
    """ps を 1 回呼ぶ。[{pid, ppid, lstart, command}]。失敗は None（空とは別）。"""
    try:
        r = subprocess.run(PS_CMD, capture_output=True, text=True, timeout=20)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    out = []
    for ln in r.stdout.splitlines():
        t = ln.split(None, 7)
        if len(t) < 7:
            continue
        try:
            pid, ppid = int(t[0]), int(t[1])
        except ValueError:
            continue
        out.append({"pid": pid, "ppid": ppid, "lstart": _norm_lstart(t[2:7]), "command": t[7] if len(t) > 7 else ""})
    return out


def lstart_of(pid: int) -> Optional[str]:
    """pid の開始時刻。居なければ None。"""
    try:
        r = subprocess.run(["ps", "-p", str(int(pid)), "-o", "lstart="], capture_output=True, text=True, timeout=10)
    except Exception:
        return None
    s = r.stdout.strip()
    return " ".join(s.split()) if r.returncode == 0 and s else None


def _argv0_of(command: str) -> str:
    first = command.split(None, 1)[0] if command.split() else ""
    return L.redact(os.path.basename(first))[0]


def _cmd_sha(command: str) -> str:
    return hashlib.sha256(command.encode("utf-8", "replace")).hexdigest()


def tree_under(snap: list, root_pid: int) -> list:
    """root_pid を根とする ppid 木（root 自身は含まない）。"""
    kids = {}
    for p in snap:
        kids.setdefault(p["ppid"], []).append(p)
    out, stack, seen = [], [root_pid], {root_pid}
    while stack:
        for c in kids.get(stack.pop(), []):
            if c["pid"] in seen:
                continue
            seen.add(c["pid"])
            out.append(c)
            stack.append(c["pid"])
    return out


def _write_json_atomic(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(L.canonical(obj))
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _finalize(data: dict) -> dict:
    """data の全文字列を redact し、個数を data.redactions に入れる（0 でも）。"""
    d, n = L.redact_obj(data)
    d["redactions"] = n
    return d


def _sigName(n: int) -> str:
    try:
        return signal.Signals(n).name
    except ValueError:
        return f"SIG{n}"


# ---- vera run ---------------------------------------------------------------
def cmd_run(args) -> int:
    argv = list(args.cmd or [])
    if argv and argv[0] == "--":
        argv = argv[1:]                       # REMAINDER が残す先頭の -- を 1 個だけ外す
    if not argv:
        print(json.dumps({"error": "NO_COMMAND", "usage": "vera run [--label L] -- <cmd...>"}, ensure_ascii=False))
        return 2
    ledger = L.resolve_dir(args.ledger_dir)
    keep = bool(args.keep_args)
    interval = max(0.05, float(args.sample_interval))
    run_id = uuid.uuid4().hex
    t0 = time.monotonic()
    rec_pid = os.getpid()
    rec_ls = lstart_of(rec_pid)
    # 子を起動する前に process_start の中身を組み立てて検査する。追記できない台帳なら子を起動しない。
    start = {"run_id": run_id, "label": args.label, "pid": 0, "lstart": None,
             "argv0": os.path.basename(argv[0]), "argv_sha256": L.args_sha256(argv), "cwd": os.getcwd(),
             "recorder_pid": rec_pid, "recorder_lstart": rec_ls}
    if keep:
        start["argv"] = list(argv)
    try:
        L.preflight(ledger, "process_start", {"type": "process", "id": "0"}, _finalize(start))
    except L.LedgerError as e:
        print(json.dumps({"error": e.code, "detail": e.detail, "child_started": False}, ensure_ascii=False), file=sys.stderr)
        return 2
    errors = []

    def safe_append(kind, actor, data):
        """起動後の追記。失敗しても例外で抜けず、型つきのエラーを溜める（子の監督は続ける）。"""
        try:
            L.append(ledger, kind, actor, data)
        except L.LedgerError as e:
            errors.append({"kind": kind, "error": e.code, "detail": e.detail})
        except Exception as e:
            errors.append({"kind": kind, "error": "LEDGER_APPEND_FAILED", "detail": f"{type(e).__name__}: {e}"})

    # シグナルのハンドラは子を起動する前に設定する（起動直後の SIGTERM を取りこぼさない）
    got = []
    holder = {"child": None}

    def handler(sig, _frm):
        got.append(sig)
        c = holder["child"]
        if c is not None:
            try:
                c.send_signal(sig)
            except Exception:
                pass

    old = {s_: signal.signal(s_, handler) for s_ in (signal.SIGINT, signal.SIGTERM)}
    try:
        try:
            child = subprocess.Popen(argv)
        except (FileNotFoundError, PermissionError, OSError) as e:
            print(json.dumps({"error": "COMMAND_NOT_STARTED", "detail": L.redact(str(e))[0]}, ensure_ascii=False), file=sys.stderr)
            return 127
        holder["child"] = child
        if got:                                   # 起動の途中で届いていたシグナルを子へ
            try:
                child.send_signal(got[0])
            except Exception:
                pass
        return _supervise(args, argv, ledger, keep, interval, run_id, t0, rec_pid, rec_ls, start, child, got, safe_append, errors)
    finally:
        for s_, h in old.items():
            signal.signal(s_, h)


def _supervise(args, argv, ledger, keep, interval, run_id, t0, rec_pid, rec_ls, start, child, got, safe_append, errors) -> int:
    child_ls = lstart_of(child.pid)
    start = dict(start, pid=child.pid, lstart=child_ls)
    safe_append("process_start", {"type": "process", "id": str(child.pid)}, _finalize(start))

    known = {}                   # (pid, lstart) -> info
    state = {"samples": 0}
    state_path = ledger / "runs" / f"{run_id}.json"

    def sample():
        snap = snapshot()
        state["samples"] += 1
        if snap is not None:
            for p in tree_under(snap, child.pid):
                k = (p["pid"], p["lstart"])
                if k not in known:
                    info = {"pid": p["pid"], "lstart": p["lstart"], "argv0": _argv0_of(p["command"]), "cmd_sha256": _cmd_sha(p["command"])}
                    if keep:
                        info["cmd"] = L.redact(p["command"])[0]
                    known[k] = info
        try:
            _write_json_atomic(state_path, {"run_id": run_id, "child": {"pid": child.pid, "lstart": child_ls},
                                            "recorder": {"pid": rec_pid, "lstart": rec_ls}, "samples": state["samples"],
                                            "descendants": list(known.values()), "updated": L.now_ts()})
        except Exception:
            pass
        return snap

    deadline = None
    if True:
        while True:
            rc = child.poll()
            sample()
            if rc is not None:
                break
            if got and deadline is None:
                deadline = time.monotonic() + GRACE_S
            if deadline is not None and time.monotonic() > deadline:
                break
            try:
                child.wait(timeout=interval)
            except subprocess.TimeoutExpired:
                pass
        rc = child.poll()
        final = snapshot()
    duration = round(time.monotonic() - t0, 3)

    alive_now = {(p["pid"], p["lstart"]) for p in (final or [])}
    orphans = [info for k, info in known.items() if k in alive_now]
    if rc is None and (child.pid, child_ls) in alive_now:
        orphans.append({"pid": child.pid, "lstart": child_ls, "argv0": os.path.basename(argv[0]),
                        "cmd_sha256": L.args_sha256(argv), **({"cmd": " ".join(argv)} if keep else {})})
    actor = {"type": "process", "id": str(child.pid)}
    base = {"run_id": run_id, "duration_s": duration, "samples": state["samples"], "descendants_seen": len(known)}
    if got:
        sig = got[0]
        safe_append("process_interrupted", actor, _finalize({**base, "signal": _sigName(sig), "target": "recorder",
                 "child_exit_code": rc, "child_status": "running_at_exit" if rc is None else "exited"}))
        code = 128 + sig
    elif rc is not None and rc < 0:
        safe_append("process_interrupted", actor, _finalize({**base, "signal": _sigName(-rc), "target": "job"}))
        code = 128 - rc
    else:
        safe_append("process_exit", actor, _finalize({**base, "exit_code": rc}))
        code = rc
    for info in orphans:
        d = {"run_id": run_id, "pid": info["pid"], "lstart": info["lstart"], "argv0": info["argv0"], "cmd_sha256": info["cmd_sha256"]}
        if "cmd" in info:
            d["cmd"] = info["cmd"]
        safe_append("process_orphaned", {"type": "process", "id": str(info["pid"])}, _finalize(d))
    if errors:
        print(json.dumps({"error": "LEDGER_APPEND_FAILED_AFTER_START", "child_started": True, "child_exit_code": code,
                          "failures": errors}, ensure_ascii=False), file=sys.stderr)
        return code if code != 0 else 3
    return code


# ---- vera events sweep ------------------------------------------------------
def _read_state(ledger: Path, run_id: str) -> dict:
    try:
        return json.loads((ledger / "runs" / f"{run_id}.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def sweep(ledger_dir) -> dict:
    ledger = Path(ledger_dir)
    ledger.mkdir(parents=True, exist_ok=True)
    appended = vanished = 0
    with open(ledger / ".sweep.lock", "a") as lk:
        fcntl.flock(lk.fileno(), fcntl.LOCK_EX)
        try:
            ev = L.read_events(ledger)
            ended = {r["data"].get("run_id") for r in ev if r["kind"] == "process_interrupted"
                     or (r["kind"] == "process_exit" and "pid" not in r["data"])}
            # 1. 終わりの行が無く、記録者が居ない run
            for r in ev:
                d = r["data"]
                if r["kind"] != "process_start" or "recorder_pid" not in d or d.get("run_id") in ended:
                    continue
                if d.get("recorder_lstart") is not None and lstart_of(d["recorder_pid"]) == d["recorder_lstart"]:
                    continue                                   # 記録者は生きている（まだ走っている）
                L.append(ledger, "process_interrupted", {"type": "process", "id": str(d["recorder_pid"])},
                         {"run_id": d["run_id"], "signal": None, "cause": "RECORDER_VANISHED", "target": "recorder", "redactions": 0})
                appended += 1
                vanished += 1
                ended.add(d["run_id"])
                cands = []
                if d.get("pid") is not None:
                    cands.append({"pid": d["pid"], "lstart": d.get("lstart"), "argv0": d.get("argv0", ""), "cmd_sha256": d.get("argv_sha256", "")})
                cands += _read_state(ledger, d["run_id"]).get("descendants", [])
                seen = set()
                for c in cands:
                    k = (c.get("pid"), c.get("lstart"))
                    if k in seen or c.get("lstart") is None or lstart_of(c["pid"]) != c["lstart"]:
                        continue
                    seen.add(k)
                    od = {"run_id": d["run_id"], "pid": c["pid"], "lstart": c["lstart"], "argv0": L.redact(str(c.get("argv0", "")))[0],
                          "cmd_sha256": c.get("cmd_sha256", "")}
                    if "cmd" in c:
                        od["cmd"] = L.redact(str(c["cmd"]))[0]
                    L.append(ledger, "process_orphaned", {"type": "process", "id": str(c["pid"])}, _finalize(od))
                    appended += 1
            # 2. 終了の行が無い孤児
            ev = L.read_events(ledger)
            exited = {(r["data"].get("run_id"), r["data"].get("pid"), r["data"].get("lstart")) for r in ev
                      if r["kind"] == "process_exit" and "pid" in r["data"]}
            still = []
            for r in ev:
                d = r["data"]
                if r["kind"] != "process_orphaned":
                    continue
                k = (d.get("run_id"), d.get("pid"), d.get("lstart"))
                if k in exited:
                    continue
                if d.get("lstart") is not None and lstart_of(d["pid"]) == d["lstart"]:
                    still.append({"run_id": d["run_id"], "pid": d["pid"], "lstart": d["lstart"], "argv0": d.get("argv0")})
                    continue
                L.append(ledger, "process_exit", {"type": "process", "id": str(d["pid"])},
                         {"run_id": d["run_id"], "pid": d["pid"], "lstart": d["lstart"], "exit_code": None,
                          "exit_code_status": "UNOBSERVABLE_NOT_A_CHILD", "observed": "absent_at_sweep", "redactions": 0})
                exited.add(k)
                appended += 1
        finally:
            fcntl.flock(lk.fileno(), fcntl.LOCK_UN)
    return {"appended": appended, "still_alive": still, "recorder_vanished": vanished}


# ---- vera events ------------------------------------------------------------
def _pj(o) -> None:
    print(json.dumps(o, ensure_ascii=False, sort_keys=True))


def _json_or_text(s: str):
    try:
        return json.loads(s)
    except Exception:
        return s


def _manual_add(args, ledger: Path) -> int:
    kind = args.kind
    if kind == "auto":
        _pj({"error": "AUTO_NEEDS_FROM", "detail": "auto は --from claude-code|codex と一緒に使う"})
        return 2
    atype = args.actor_type or ("owner" if kind in ("owner_utterance", "approval") else "agent")
    actor = {"type": atype, "id": args.actor_id or "unknown"}
    if args.model:
        actor["model"] = args.model
    data = {}
    if args.data:
        o = _json_or_text(args.data)
        if not isinstance(o, dict):
            _pj({"error": "BAD_DATA", "detail": "--data は JSON のオブジェクト"})
            return 2
        data.update(o)
    text = args.text
    if args.stdin and text is None:
        text = sys.stdin.read()
    if text is not None:
        data["text"] = text
    if kind == "tool_call":
        if args.tool_name:
            data["tool_name"] = args.tool_name
        if args.args is not None:
            a = _json_or_text(args.args)
            data["args_sha256"] = L.args_sha256(a)
            if args.keep_args:
                data["args"] = a
    data = _finalize(data)
    try:
        row = L.append(ledger, kind, actor, data)
    except L.LedgerError as e:
        _pj({"error": e.code, "detail": e.detail})
        return 2
    _pj(row)
    return 0


def cmd_events(args) -> int:
    ledger = L.resolve_dir(getattr(args, "ledger_dir", None) or getattr(args, "ledger_dir_top", None))
    act = args.ev_cmd
    if act == "add":
        if args.src:
            from . import hooks_templates as H
            return H.ingest_cli(args, ledger)          # 常に 0・標準出力に何も出さない
        return _manual_add(args, ledger)
    if act == "tail":
        rows = L.read_events(ledger)
        for r in rows[-max(0, args.n):] if args.n else []:
            _pj(r)
        return 0
    if act == "grep":
        if args.kind not in L.KINDS:
            _pj({"error": "UNKNOWN_KIND", "detail": args.kind})
            return 2
        for r in L.read_events(ledger):
            if r.get("kind") == args.kind:
                _pj(r)
        return 0
    if act == "show":
        if len(args.sha) < 8:
            _pj({"error": "PREFIX_TOO_SHORT", "detail": "8 文字以上"})
            return 2
        m = L.find_by_prefix(ledger, args.sha)
        if not m:
            _pj({"error": "NOT_FOUND", "detail": args.sha})
            return 1
        if len(m) > 1:
            _pj({"error": "AMBIGUOUS_PREFIX", "candidates": [r["sha"] for r in m]})
            return 2
        _pj(m[0])
        return 0
    if act == "verify":
        v = L.verify(ledger, expected_head=args.head)
        _pj(v)
        return 0 if v["status"] in ("OK", "EMPTY") else 1
    if act == "sweep":
        _pj(sweep(ledger))
        return 0
    return 2


def _is_claude_code_argv(argv) -> bool:
    argv = list(argv)
    return any(a == "--from=claude-code" or (a == "--from" and i + 1 < len(argv) and argv[i + 1] == "claude-code")
               for i, a in enumerate(argv))


class _Intermixed(argparse.ArgumentParser):
    """オプションと位置引数の混在を許す（Codex の notify は JSON を最後の argv に付ける。argparse は既定だと任意の位置引数を取り損ねる）。

    W16-t7b: `events add` で解析中の引数列に `--from claude-code` があるときだけ、引数の誤りを終了 1 にする
    （Claude Code の hook で 2 は入力を止める特別な値）。他の場合は従来どおり 2。"""

    _inner = False
    _hook_exit1 = False
    _exit1_when_claude_code = False

    def error(self, message):
        if self._hook_exit1:
            self.print_usage(sys.stderr)
            self.exit(1, f"{self.prog}: error: {message}\n")
        super().error(message)

    def parse_known_args(self, args=None, namespace=None):
        if self._inner:                        # parse_known_intermixed_args が内側から呼ぶ
            return super().parse_known_args(args, namespace)
        argv = sys.argv[1:] if args is None else list(args)
        self._inner = True
        self._hook_exit1 = self._exit1_when_claude_code and _is_claude_code_argv(argv)
        try:
            ns, extras = self.parse_known_intermixed_args(argv, namespace)
            if extras and self._hook_exit1:    # 最上位のパーサに返すと cli.py の error（終了 2）になる
                self.error("unrecognized arguments: " + " ".join(extras))
            return ns, extras
        finally:
            self._inner = False
            self._hook_exit1 = False


# ---- 登録（cli.py からはこれだけ呼ぶ）-----------------------------------------
def register_cli(sub) -> None:
    p = sub.add_parser("run", help="run a command as a recorded child process (descendants, interrupts, orphans) into the events ledger")
    p.add_argument("--label", default=None)
    p.add_argument("--ledger-dir", default=None)
    p.add_argument("--sample-interval", type=float, default=0.5)
    p.add_argument("--keep-args", action="store_true", help="store argv (redacted); default stores only a sha256")
    p.add_argument("cmd", nargs=argparse.REMAINDER, help="-- <command...>")
    p.set_defaults(fn=cmd_run)

    p = sub.add_parser("events", help="append-only hash-chained events ledger: tail / show / verify / grep / sweep / add")
    p.add_argument("--ledger-dir", dest="ledger_dir_top", default=None)
    es = p.add_subparsers(dest="ev_cmd", required=True, parser_class=_Intermixed)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--ledger-dir", default=argparse.SUPPRESS)

    q = es.add_parser("tail", parents=[common])
    q.add_argument("-n", type=int, default=20)
    q = es.add_parser("show", parents=[common])
    q.add_argument("sha")
    q = es.add_parser("grep", parents=[common])
    q.add_argument("kind")
    q = es.add_parser("verify", parents=[common])
    q.add_argument("--head", default=None, help="externally pinned HEAD sha (e.g. git show HEAD:.vera/ledger/HEAD)")
    es.add_parser("sweep", parents=[common])
    q = es.add_parser("add", parents=[common])
    q._exit1_when_claude_code = True
    q.add_argument("kind", choices=list(L.KINDS) + ["auto"])
    q.add_argument("--from", dest="src", choices=["claude-code", "codex"], default=None)
    q.add_argument("--stdin", action="store_true")
    q.add_argument("--actor-type", default=None)
    q.add_argument("--actor-id", default=None)
    q.add_argument("--model", default=None)
    q.add_argument("--text", default=None)
    q.add_argument("--data", default=None, help="JSON object merged into data")
    q.add_argument("--tool-name", default=None)
    q.add_argument("--args", default=None, help="tool arguments (JSON or text); only its sha256 is stored unless --keep-args")
    q.add_argument("--keep-args", action="store_true")
    q.add_argument("payload", nargs="?", default=None, help="codex notify passes its JSON as the last argv")
    p.set_defaults(fn=cmd_events)

    p = sub.add_parser("hooks", help="print hook templates (Claude Code / Codex) or install them into a project's own settings")
    hs = p.add_subparsers(dest="hk_cmd", required=True)
    q = hs.add_parser("print")
    g = q.add_mutually_exclusive_group(required=True)
    g.add_argument("--claude-code", action="store_true")
    g.add_argument("--codex", action="store_true")
    q.add_argument("--keep-args", action="store_true")
    _pin_args(q)
    q.add_argument("--project", default=None, help="codex only: project dir used for the absolute --ledger-dir (default: cwd)")
    q = hs.add_parser("install")
    q.add_argument("--project", required=True)
    q.add_argument("--write", action="store_true", help="without this flag nothing is written")
    q.add_argument("--keep-args", action="store_true")
    _pin_args(q)
    p.set_defaults(fn=_cmd_hooks)


def _pin_args(q) -> None:
    # --vera-cmd は --python/--code-root と同時に指定できない（cmd_hooks の入口で終了 2）。
    # --python と --code-root は同時に指定できる。
    q.add_argument("--vera-cmd", default=None, help="command prefix used as-is (not pinned; exclusive with --python/--code-root)")
    q.add_argument("--python", default=None, help="python embedded in the hook commands (default: the running interpreter)")
    q.add_argument("--code-root", default=None, help="directory that contains the verantyx package to load (default: where the running vera loaded it)")


def _cmd_hooks(args) -> int:
    from . import hooks_templates as H
    return H.cmd_hooks(args)


# ---- hooks install の自己検査（W16-t7b / K712）---------------------------------
_SELFTEST_STRIP_ENV = ("PYTHONPATH", "PYTHONHOME", "PYTHONSAFEPATH")


def _count_lines(path: Path) -> int:
    try:
        with open(path, "rb") as f:
            return sum(1 for _ in f)
    except FileNotFoundError:
        return 0


def run_hook_selftest(project: Path, cases: list, timeout: int = 10) -> dict:
    """各コマンドを cwd=<project>・偽の入力で 1 回ずつ実行する。台帳は一時ディレクトリ（<project> の下には何も作らない）。
    環境から PYTHONPATH などを除く（呼び出し元の設定を引き継ぐと固定の誤りを隠す）。
    合格 = 終了 0・標準出力が空・events.jsonl がちょうど 1 行増える・rejects.jsonl が増えない。"""
    import tempfile
    out = []
    with tempfile.TemporaryDirectory(prefix="vera-hook-selftest-") as td:
        led = Path(td) / ".vera" / "ledger"
        env = {k: v for k, v in os.environ.items() if k not in _SELFTEST_STRIP_ENV}
        env["CLAUDE_PROJECT_DIR"] = td
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        for event, command, payload in cases:
            ev0, rj0 = _count_lines(led / "events.jsonl"), _count_lines(led / "rejects.jsonl")
            rec = {"event": event, "returncode": None, "timed_out": False, "stdout_bytes": 0, "stderr_tail": "", "rows_added": 0, "rejects_added": 0}
            try:
                r = subprocess.run(["/bin/sh", "-c", command], input=payload, capture_output=True, text=True,
                                   cwd=str(project), env=env, timeout=timeout)
                rec["returncode"] = r.returncode
                rec["stdout_bytes"] = len(r.stdout.encode("utf-8", "replace"))
                rec["stderr_tail"] = L.redact(r.stderr.strip()[-300:])[0]
            except subprocess.TimeoutExpired:
                rec["timed_out"] = True
            except Exception as e:
                rec["stderr_tail"] = f"{type(e).__name__}"
            rec["rows_added"] = _count_lines(led / "events.jsonl") - ev0
            rec["rejects_added"] = _count_lines(led / "rejects.jsonl") - rj0
            rec["pass"] = bool(rec["returncode"] == 0 and rec["stdout_bytes"] == 0 and rec["rows_added"] == 1 and rec["rejects_added"] == 0)
            out.append(rec)
    return {"ok": all(c["pass"] for c in out) and bool(out), "cases": out}
