"""W16-t7b 赤の確認: 偽の verantyx/ (cli.py が終了 2) のある cwd で、雛形の各コマンド/Codex argv を PYTHONPATH 無しで実行する。
使い方: red_before.py <作業場所> [--tree <ツリー>]  (雛形の取得だけ PYTHONPATH=<ツリー>)"""
import json, os, subprocess, sys, tomllib
from pathlib import Path

work = Path(sys.argv[1]); work.mkdir(parents=True, exist_ok=True)
tree = Path(__file__).resolve().parents[2]
PY = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
proj = work / "proj"; (proj / "verantyx").mkdir(parents=True, exist_ok=True)
(proj / "verantyx" / "__init__.py").write_text("")
(proj / "verantyx" / "cli.py").write_text("import sys\nsys.exit(2)\n")
PAY = {
 "UserPromptSubmit": {"session_id": "s", "hook_event_name": "UserPromptSubmit", "prompt": "hi"},
 "PostToolUse": {"session_id": "s", "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "true"}, "tool_response": {"exit_code": 0}},
 "Stop": {"session_id": "s", "hook_event_name": "Stop"}, "SubagentStop": {"session_id": "s", "hook_event_name": "SubagentStop"},
 "SessionStart": {"session_id": "s", "hook_event_name": "SessionStart"}, "SessionEnd": {"session_id": "s", "hook_event_name": "SessionEnd"},
}
def clean(**kw):
    e = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "PYTHONSAFEPATH")}; e.update(kw); return e
genv = dict(os.environ, PYTHONPATH=str(tree), PYTHONDONTWRITEBYTECODE="1")
def rows(d): 
    p = d / "events.jsonl"; return len(p.read_text().splitlines()) if p.exists() else 0
tpl = json.loads(subprocess.run([PY, "-m", "verantyx.cli", "hooks", "print", "--claude-code"], capture_output=True, text=True, env=genv, cwd=tree).stdout)
allrc = []
for ev, lst in tpl["hooks"].items():
    cmd = lst[0]["hooks"][0]["command"]
    led = proj / ".vera" / "ledger"
    r = subprocess.run(["/bin/sh", "-c", cmd], input=json.dumps(PAY[ev]), capture_output=True, text=True, cwd=proj, env=clean(CLAUDE_PROJECT_DIR=str(proj)), timeout=20)
    tail = (r.stderr.strip().splitlines() or [""])[-1]
    print(f"{ev}\trc={r.returncode}\tledger_rows={rows(led)}\tstderr_tail={tail[:120]}"); allrc.append(r.returncode)
cx = subprocess.run([PY, "-m", "verantyx.cli", "hooks", "print", "--codex", "--project", str(proj)], capture_output=True, text=True, env=genv, cwd=tree).stdout
argv = tomllib.loads(cx)["notify"] + [json.dumps({"type": "agent-turn-complete", "thread-id": "t"})]
r = subprocess.run(argv, capture_output=True, text=True, cwd=proj, env=clean(), timeout=20)
print(f"codex_notify\trc={r.returncode}\tledger_rows={rows(proj/'.vera'/'ledger')}\tstderr_tail={(r.stderr.strip().splitlines() or [''])[-1][:120]}"); allrc.append(r.returncode)
print("ALL_RC", allrc)
