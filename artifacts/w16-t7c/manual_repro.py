"""3 経路（vera run --keep-args・PostToolUse hook --keep-args・UserPromptSubmit hook）に全角・パーセント・base64 の鍵を通す。
使い方: manual_repro.py <ツリー> <台帳を作る親ディレクトリ>。鍵の本体は出さない（OK/漏れだけ）。"""
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

T, W = sys.argv[1], Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("v", T + "/tests/test_w16t7c_redact_variants.py")
V = importlib.util.module_from_spec(spec)
spec.loader.exec_module(V)
forms = {"fullwidth": "fw_all", "percent": "pct_dash", "base64": "b64_padded"}
env = dict(os.environ, PYTHONPATH=T, PYTHONDONTWRITEBYTECODE="1")
PY = sys.executable


def allbytes(d):
    return b"".join(p.read_bytes() for p in Path(d).rglob("*") if p.is_file())


def check(label, d, secrets):
    b = allbytes(d).decode("utf-8", "replace")
    esc = b + json.dumps(b)
    ok = bool(b) and not V.leaks(esc, secrets)
    print(f"{label}: {'OK' if ok else '漏れ'} (台帳 {len(b)} バイト)")
    return ok


def hookcmd(event, *extra):
    r = subprocess.run([PY, "-m", "verantyx.cli", "hooks", "print", "--claude-code", *extra], capture_output=True, text=True, env=env, cwd=T)
    return json.loads(r.stdout)["hooks"][event][0]["hooks"][0]["command"]


bad = 0
for form, name in forms.items():
    _f, _n, text, secrets = next(x for x in V.VARIANTS if x[1] == name)
    # 1) vera run --keep-args
    d = W / f"run_{form}"
    subprocess.run([PY, "-m", "verantyx.cli", "run", "--ledger-dir", str(d), "--keep-args", "--", "sh", "-c", "echo " + text], capture_output=True, text=True, env=env, cwd=str(W))
    bad += not check(f"run/{form}", d, secrets)
    # 2) PostToolUse --keep-args
    proj = W / f"post_{form}"
    proj.mkdir(exist_ok=True)
    pl = json.dumps({"session_id": "s", "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "echo " + text}})
    r = subprocess.run(hookcmd("PostToolUse", "--keep-args"), shell=True, input=pl, capture_output=True, text=True, env=dict(env, CLAUDE_PROJECT_DIR=str(proj)), cwd=str(proj))
    bad += not check(f"posttooluse/{form} rc={r.returncode}", proj / ".vera" / "ledger", secrets)
    # 3) UserPromptSubmit
    proj = W / f"prompt_{form}"
    proj.mkdir(exist_ok=True)
    r = subprocess.run(hookcmd("UserPromptSubmit"), shell=True, input=json.dumps({"prompt": text}), capture_output=True, text=True, env=dict(env, CLAUDE_PROJECT_DIR=str(proj)), cwd=str(proj))
    bad += not check(f"userprompt/{form} rc={r.returncode}", proj / ".vera" / "ledger", secrets)
print("BAD", bad)
