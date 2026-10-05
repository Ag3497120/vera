"""W16-t7 K702: hook の雛形（出力するだけ）・hook から呼ばれる取り込み・プロジェクト用 install。

約束:
- 利用者の全体設定（~/.claude・~/.codex）は読まない・書かない。このモジュールはホームを展開する呼び出しを持たない。
  拒否の判定に要る「ホーム」は環境変数 HOME（と pwd のホーム）を読むだけ。
- 書き込みは `_write_settings_atomic` の 1 関数だけ。書き先の組み立ては `install_project` の中だけ。
- hook から呼ばれる側（`events add … --from …`）は標準出力に何も出さず、取り込みの失敗は終了コード 0（標準エラーと rejects.jsonl に型つきで残す）。
  W16-t7b: 引数の誤りは 2 ではなく 1（--from claude-code のとき）。hook のコマンドは ` || exit 1` で、どんな失敗も 1 にする。
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Optional

from . import ledger_events as L

EVENTS_ORDER = ("UserPromptSubmit", "PostToolUse", "Stop", "SubagentStop", "SessionStart", "SessionEnd")
LEDGER_ARG = '--ledger-dir "${CLAUDE_PROJECT_DIR:-.}/.vera/ledger"'


def default_vera_cmd() -> str:
    return shlex.quote(sys.executable) + " -m verantyx.cli"


class PinError(Exception):
    """読み込むコードを固定できない（型つきの拒否）。"""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code)
        self.code, self.detail = code, detail


def _probe_python_version(python: str) -> Optional[tuple]:
    if python == sys.executable:
        return (sys.version_info[0], sys.version_info[1])
    try:
        r = subprocess.run([python, "-c", "import sys;print(sys.version_info[0], sys.version_info[1])"],
                           capture_output=True, text=True, timeout=5)
        if r.returncode == 0:
            a, b = r.stdout.split()
            return (int(a), int(b))
    except Exception:
        pass
    return None


def resolve_pin(python: Optional[str] = None, code_root: Optional[str] = None) -> dict:
    """hook のコマンドに埋め込む「どの python が、どの verantyx を読むか」。

    python は resolve しない（venv の bin/python はシンボリックリンクで、辿ると venv の外の素の Python になる）。
    code_root の既定は、いま読み込まれている verantyx パッケージの親ディレクトリ。
    """
    if getattr(sys, "frozen", False) and not (python and code_root):
        raise PinError("PIN_UNRESOLVABLE_FROZEN", "凍結された実行物では python と code_root を固定できない。--python と --code-root を渡す")
    py = str(Path(python).absolute()) if python else str(Path(sys.executable).absolute())
    root = str(Path(code_root).resolve()) if code_root else str(Path(__file__).resolve().parent.parent)
    ver = _probe_python_version(py)
    if ver is None:
        vs, form = "UNKNOWN_PROBE_FAILED", "dash_c_syspath"
    else:
        vs = f"{ver[0]}.{ver[1]}"
        form = "dash_P" if ver >= (3, 11) else "dash_c_syspath"
    return {"python": py, "python_source": "--python" if python else "sys.executable",
            "code_root": root, "code_root_source": "--code-root" if code_root else "loaded_package",
            "python_version": vs, "form": form}


def _dash_c_code(code_root: str) -> str:
    return ("import sys,runpy; sys.path[0]=" + repr(code_root)
            + "; runpy.run_module('verantyx.cli', run_name='__main__', alter_sys=True)")


def pinned_shell_prefix(pin: dict) -> str:
    q = shlex.quote
    if pin["form"] == "dash_P":
        return f"PYTHONPATH={q(pin['code_root'])} {q(pin['python'])} -P -m verantyx.cli"
    return f"{q(pin['python'])} -c {q(_dash_c_code(pin['code_root']))}"


def pinned_argv_prefix(pin: dict) -> list:
    if pin["form"] == "dash_P":
        return ["/usr/bin/env", "PYTHONPATH=" + pin["code_root"], pin["python"], "-P", "-m", "verantyx.cli"]
    return [pin["python"], "-c", _dash_c_code(pin["code_root"])]


def claude_code_template(vera_cmd: Optional[str] = None, keep_args: bool = False, pin: Optional[dict] = None) -> dict:
    """vera_cmd があればそれを前置き（固定しない。従来どおり）。無ければ pin（既定は実行中の解決）で固定する。
    どちらの場合も末尾に ` || exit 1`（どんな失敗も 1＝止めない誤り。2 は Claude Code が入力を止める特別な値）。"""
    c = vera_cmd or pinned_shell_prefix(pin or resolve_pin(None, None))

    def entry(kind, matcher=None, extra=""):
        h = {"type": "command", "command": f"{c} events add {kind} --stdin --from claude-code {LEDGER_ARG}{extra} || exit 1", "timeout": 10}
        e = {"hooks": [h]}
        if matcher:
            e = {"matcher": matcher, "hooks": [h]}
        return [e]
    return {"hooks": {
        "UserPromptSubmit": entry("owner_utterance"),
        "PostToolUse": entry("auto", "Bash", " --keep-args" if keep_args else ""),
        "Stop": entry("agent_stop"),
        "SubagentStop": entry("agent_stop"),
        "SessionStart": entry("auto"),
        "SessionEnd": entry("auto"),
    }}


_SELFTEST_PAYLOADS = {
    "UserPromptSubmit": {"session_id": "vera-selftest", "hook_event_name": "UserPromptSubmit", "prompt": "vera hook selftest"},
    "PostToolUse": {"session_id": "vera-selftest", "hook_event_name": "PostToolUse", "tool_name": "Bash",
                    "tool_input": {"command": "true"}, "tool_response": {"exit_code": 0}},
}


def selftest_cases(tpl: dict) -> list:
    """(event, command, payload_str) の 6 組。入力は固定の偽物（git を呼ばない）。"""
    out = []
    for ev in EVENTS_ORDER:
        payload = _SELFTEST_PAYLOADS.get(ev) or {"session_id": "vera-selftest", "hook_event_name": ev}
        out.append((ev, tpl[ev][0]["hooks"][0]["command"], json.dumps(payload)))
    return out


def codex_notify_line(vera_cmd: Optional[str], project: Optional[str], pin: Optional[dict] = None) -> str:
    if vera_cmd:
        base, note = shlex.split(vera_cmd), {"form": "vera_cmd_override"}
    else:
        note = pin or resolve_pin(None, None)
        base = pinned_argv_prefix(note)
    ledger = str((Path(project) if project else Path.cwd()).resolve() / ".vera" / "ledger")
    arr = base + ["events", "add", "agent_stop", "--from", "codex", "--ledger-dir", ledger]
    return ("# Codex の notify は 1 つしか置けない。既に notify がある場合は、これに置き換えると既存の通知先が止まる。\n"
            "# このコマンドは出力するだけで、~/.codex/config.toml を読まない・書かない。置くかどうかはオーナーが決める。\n"
            "# Codex は $CLAUDE_PROJECT_DIR を展開しないので --ledger-dir は絶対パス。\n"
            "# _vera: " + json.dumps(note, ensure_ascii=False, sort_keys=True) + "\n"
            "notify = " + json.dumps(arr) + "\n")


# ---- install（プロジェクトの設定にだけ書く）-------------------------------------
def _write_settings_atomic(target: Path, obj: dict) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)


def _home_candidates() -> list:
    out = []
    h = os.environ.get("HOME")
    if h:
        out.append(Path(h).resolve())
    try:
        import pwd
        out.append(Path(pwd.getpwuid(os.getuid()).pw_dir).resolve())
    except Exception:
        pass
    return out


def install_project(project, write: bool, vera_cmd: Optional[str] = None, keep_args: bool = False, pin: Optional[dict] = None) -> tuple:
    """(終了コード, 結果の辞書)。書き先は常に <project>/.claude/settings.json だけ。--write が無ければ何も書かない。"""
    proj = Path(project).resolve()
    target = proj / ".claude" / "settings.json"
    for home in _home_candidates():
        user_dir = home / ".claude"
        if proj == home or proj == user_dir or user_dir in proj.parents or target == user_dir / "settings.json":
            return 2, {"status": "REFUSED_USER_SETTINGS", "target": str(target),
                       "detail": "利用者の全体設定（ホームの .claude）には書かない。プロジェクトのディレクトリを指定する"}
    # シンボリックリンク経由の迂回を塞ぐ: 書き先の実体（.claude とファイル自体を resolve）にも同じ判定をかける
    claude_dir = proj / ".claude"
    if claude_dir.is_symlink() or target.is_symlink():
        return 2, {"status": "REFUSED_SYMLINK_SETTINGS", "target": str(target),
                   "detail": "<project>/.claude または settings.json がシンボリックリンク。実体が不明なので書かない"}
    real_target = claude_dir.resolve() / "settings.json"
    if target.exists():
        real_target = target.resolve()
    for home in _home_candidates():
        user_dir = home / ".claude"
        if real_target == user_dir / "settings.json" or user_dir in real_target.parents or real_target.parent == home:
            return 2, {"status": "REFUSED_USER_SETTINGS", "target": str(real_target),
                       "detail": "書き先の実体が利用者の全体設定（ホームの .claude）。書かない"}
    existing = {}
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
            if not isinstance(existing, dict) or not isinstance(existing.get("hooks", {}), dict):
                raise ValueError("shape")
        except Exception:
            return 2, {"status": "REFUSED_UNPARSABLE_SETTINGS", "target": str(target)}
    note = {"form": "vera_cmd_override"} if vera_cmd else (pin or resolve_pin(None, None))
    tpl = claude_code_template(vera_cmd, keep_args, pin=pin)["hooks"]
    merged = dict(existing)
    hooks = dict(existing.get("hooks", {}))
    added = 0
    for ev in EVENTS_ORDER:
        lst = list(hooks.get(ev, []))
        have = {h.get("command") for e in lst if isinstance(e, dict) for h in e.get("hooks", []) if isinstance(h, dict)}
        for e in tpl[ev]:
            if all(h["command"] in have for h in e["hooks"]):
                continue
            lst.append(e)
            added += 1
        hooks[ev] = lst
    merged["hooks"] = hooks
    if not write:
        return 0, {"status": "NOT_WRITTEN_NO_FLAG", "target": str(target), "would_add": added,
                   "would_write": merged, "detail": "書くには --write を付ける", "_vera": note}
    # 書く前の自己検査: 生成したコマンドを <project> を cwd にして偽の入力で 1 回ずつ実行する（台帳は一時ディレクトリ）
    from . import run_recorder as R
    st = R.run_hook_selftest(proj, selftest_cases(tpl))
    if not st["ok"]:
        return 2, {"status": "REFUSED_HOOK_SELFTEST", "target": str(target), "selftest": st, "_vera": note,
                   "detail": "生成した hook のコマンドが偽の入力で終了 0・台帳 1 行にならなかったので書かない"}
    stale = sum(1 for e in existing.get("hooks", {}).values() if isinstance(e, list)
                for x in e if isinstance(x, dict) for h in x.get("hooks", []) if isinstance(h, dict)
                and "-m verantyx.cli events add" in str(h.get("command", "")) and not str(h.get("command", "")).endswith(" || exit 1"))
    _write_settings_atomic(target, merged)
    return 0, {"status": "WRITTEN", "target": str(target), "added": added, "selftest": {"ok": True, "n": len(st["cases"])},
               "stale_vera_hooks": stale, "_vera": note}


def cmd_hooks(args) -> int:
    if args.vera_cmd and (getattr(args, "python", None) or getattr(args, "code_root", None)):
        print("vera hooks: error: --vera-cmd は --python／--code-root と同時に指定できない", file=sys.stderr)
        return 2
    pin = None
    if not args.vera_cmd:
        try:
            pin = resolve_pin(getattr(args, "python", None), getattr(args, "code_root", None))
        except PinError as e:
            print(json.dumps({"status": e.code, "detail": e.detail}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
            return 2
    if args.hk_cmd == "print":
        if args.claude_code:
            print(json.dumps(claude_code_template(args.vera_cmd, args.keep_args, pin=pin), ensure_ascii=False, indent=2))
            print(json.dumps({"_vera": pin or {"form": "vera_cmd_override"}}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        else:
            sys.stdout.write(codex_notify_line(args.vera_cmd, args.project, pin))
        return 0
    rc, out = install_project(args.project, args.write, args.vera_cmd, args.keep_args, pin)
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))
    return rc


# ---- hook から呼ばれる側 -------------------------------------------------------
_SEP = re.compile(r"&&|\|\||;|\||\n")
_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def _segments(cmd: str) -> list:
    out = []
    for seg in _SEP.split(cmd):
        try:
            toks = shlex.split(seg)
        except ValueError:
            toks = seg.split()
        while toks and (_ASSIGN.match(toks[0]) or toks[0] in ("env", "sudo", "time", "command", "exec")):
            toks = toks[1:]
        if toks:
            out.append(toks)
    return out


def _is_commit(t: list) -> bool:
    if os.path.basename(t[0]) != "git":
        return False
    i = 1
    while i < len(t):
        if t[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
        elif t[i].startswith("-"):
            i += 1
        else:
            return t[i] == "commit"
    return False


def _is_test(t: list) -> bool:
    b = os.path.basename(t[0])
    rest = t[1:]
    if b == "pytest":
        return True
    if b.startswith("python") and rest[:2] == ["-m", "pytest"]:
        return True
    if b == "npm" and rest[:1] in (["test"], ["t"]) or (b == "npm" and rest[:2] == ["run", "test"]):
        return True
    return (b == "go" and rest[:1] == ["test"]) or (b == "cargo" and rest[:1] == ["test"])


def classify_command(cmd: str) -> dict:
    """{'kinds': 当たった種類の集合, 'rule': 当たった規則名 or None}。両方に当たれば同点＝棄権（勝者を作らない）。"""
    kinds = set()
    for t in _segments(cmd):
        if _is_commit(t):
            kinds.add("commit")
        if _is_test(t):
            kinds.add("test_run")
    return {"kinds": kinds}


def _int_code(resp):
    if isinstance(resp, dict):
        for k in ("exit_code", "exitCode", "returncode"):
            v = resp.get(k)
            if isinstance(v, int) and not isinstance(v, bool):
                return v
    return None


def _git_head(cwd) -> tuple:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=cwd or None, capture_output=True, text=True, timeout=5)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip(), None
        return None, "GIT_REV_PARSE_FAILED"
    except Exception:
        return None, "GIT_UNAVAILABLE"


def _finalize(data: dict) -> dict:
    d, n = L.redact_obj(data)
    d["redactions"] = n
    return d


def build_claude_code_event(kind: str, p: dict, keep_args: bool) -> tuple:
    """(kind, actor, data)。作れなければ LedgerError。"""
    ev = p.get("hook_event_name")
    sid = p.get("session_id") if isinstance(p.get("session_id"), str) else "unknown"
    if kind == "auto":
        kind = {"PostToolUse": "auto_post", "SessionStart": "process_start", "SessionEnd": "process_exit",
                "Stop": "agent_stop", "SubagentStop": "agent_stop", "UserPromptSubmit": "owner_utterance"}.get(ev)
        if kind is None:
            raise L.LedgerError("UNKNOWN_HOOK_EVENT", str(ev))
    src = f"claude_code.{ev}" if isinstance(ev, str) else "claude_code"
    if kind == "owner_utterance":
        if not isinstance(p.get("prompt"), str):
            raise L.LedgerError("NO_PROMPT_IN_PAYLOAD")
        return kind, {"type": "owner", "id": sid}, _finalize({"text": p["prompt"], "source": src, "session_id": sid})
    if kind == "agent_stop":
        return kind, {"type": "agent", "id": sid}, _finalize({"source": src, "session_id": sid, "hook_event_name": ev})
    if kind in ("process_start", "process_exit"):
        d = {"source": src, "session_id": sid, "hook_event_name": ev}
        if kind == "process_exit":
            d.update({"exit_code": None, "exit_code_status": "NOT_A_PROCESS_EXIT_CODE"})
        return kind, {"type": "agent", "id": sid}, _finalize(d)
    if kind in ("auto_post", "tool_call", "commit", "test_run"):
        ti = p.get("tool_input") if isinstance(p.get("tool_input"), dict) else {}
        cmd = ti.get("command") if isinstance(ti.get("command"), str) else ""
        data = {"source": src, "session_id": sid, "tool_name": p.get("tool_name") if isinstance(p.get("tool_name"), str) else None,
                "args_sha256": L.args_sha256(p.get("tool_input")), "classified_by": None}
        k = "tool_call"
        if kind in ("commit", "test_run"):
            k = kind                               # 明示された種類はそのまま
            data["classified_by"] = "explicit"
        else:
            hit = classify_command(cmd)["kinds"] if cmd else set()
            if len(hit) == 1:
                k = next(iter(hit))
                data["classified_by"] = "git_commit_segment" if k == "commit" else "test_runner_segment"
            elif len(hit) > 1:
                data["ambiguous"] = sorted(hit)    # 同点は棄権
        code = _int_code(p.get("tool_response"))
        data["exit_code"] = code
        if code is None:
            data["exit_code_status"] = "UNKNOWN_NOT_IN_PAYLOAD"
        if k == "commit":
            head, st = _git_head(p.get("cwd") if isinstance(p.get("cwd"), str) else None)
            data["git_head"] = head
            if st:
                data["git_head_status"] = st
        if keep_args:
            data["args"] = ti
        return k, {"type": "agent", "id": sid}, _finalize(data)
    raise L.LedgerError("UNKNOWN_KIND", kind)


def build_codex_event(p: dict) -> tuple:
    if p.get("type") != "agent-turn-complete":
        raise L.LedgerError("UNSUPPORTED_CODEX_EVENT", str(p.get("type")))
    tid = p.get("thread-id") if isinstance(p.get("thread-id"), str) else "unknown"
    actor = {"type": "agent", "id": tid}
    if isinstance(p.get("model"), str):
        actor["model"] = p["model"]
    d = {"source": "codex.notify"}
    if isinstance(p.get("turn-id"), str):
        d["turn_id"] = p["turn-id"]
    if isinstance(p.get("last-assistant-message"), str):
        d["last_message_sha256"] = L.args_sha256(p["last-assistant-message"])
    if isinstance(p.get("input-messages"), list):
        d["input_messages_count"] = len(p["input-messages"])      # 入力の発話は作者が分からない: 数だけ
    return "agent_stop", actor, _finalize(d)


def ingest_cli(args, ledger: Path) -> int:
    """`events add … --from claude-code|codex`。標準出力に何も出さず、常に 0 を返す。"""
    raw = ""
    try:
        if args.src == "claude-code":
            raw = sys.stdin.read() if args.stdin else (args.payload or "")
            try:
                p = json.loads(raw)
            except Exception:
                L.reject(ledger, "PAYLOAD_NOT_JSON", source=args.src, bytes=len(raw.encode("utf-8", "replace")),
                         sha256=L.args_sha256(raw), head=L.redact(raw)[0][:80])
                return 0
            if not isinstance(p, dict):
                L.reject(ledger, "PAYLOAD_NOT_OBJECT", source=args.src, sha256=L.args_sha256(raw))
                return 0
            kind, actor, data = build_claude_code_event(args.kind, p, bool(args.keep_args))
        else:
            raw = args.payload or ""
            if not raw:
                L.reject(ledger, "NO_PAYLOAD", source=args.src)
                return 0
            try:
                p = json.loads(raw)
            except Exception:
                L.reject(ledger, "PAYLOAD_NOT_JSON", source=args.src, sha256=L.args_sha256(raw), head=L.redact(raw)[0][:80])
                return 0
            if not isinstance(p, dict):
                L.reject(ledger, "PAYLOAD_NOT_OBJECT", source=args.src, sha256=L.args_sha256(raw))
                return 0
            kind, actor, data = build_codex_event(p)
        L.append(ledger, kind, actor, data)
    except L.LedgerError as e:
        L.reject(ledger, e.code, source=args.src, detail=e.detail)
        print(f"vera events: {e.code}", file=sys.stderr)
    except Exception as e:                      # hook を絶対に失敗させない
        L.reject(ledger, "INTERNAL_ERROR", source=args.src, detail=type(e).__name__)
        print(f"vera events: INTERNAL_ERROR {type(e).__name__}", file=sys.stderr)
    return 0
