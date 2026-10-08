"""W16-t7 T7-3: 秘匿。偽のキーは台帳ディレクトリの全ファイルのバイト列に現れない。偽キーはここで連結して作る（完成形をソースに置かない）。"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KEY = "sk-" + "ant-" + "api03-" + "A" * 20 + "b9Z" * 5
GH = "gh" + "p_" + "Q" * 24 + "7"
AWS = "AK" + "IA" + "ABCDEFGHIJKLMNOP"
BEARER = "Bear" + "er " + "z" * 30
KV = "pass" + "word=" + "hunter2hunter2"
ALL = [KEY, GH, AWS, "z" * 30, "hunter2hunter2"]


def _env(**kw):
    e = dict(os.environ)
    e["PYTHONPATH"] = str(ROOT)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(kw)
    return e


def cli(*args, input=None, cwd=None):
    return subprocess.run([sys.executable, "-m", "verantyx.cli", *args], capture_output=True, text=True, input=input,
                          env=_env(), cwd=str(cwd or tempfile.gettempdir()))


def all_bytes(d):
    out = b""
    for p in Path(d).rglob("*"):
        if p.is_file():
            out += p.read_bytes()
    return out


def rows(d):
    return [json.loads(x) for x in (Path(d) / "events.jsonl").read_text(encoding="utf-8").split("\n") if x.strip()]


def assert_clean(d, secrets):
    b = all_bytes(d)
    assert b, "台帳に何も無い"
    for s in secrets:
        assert s.encode() not in b, "平文の秘密が残っている"


def test_redact_function_patterns():
    from verantyx import ledger_events as L
    for s in (KEY, GH, AWS, BEARER, KV, "github_" + "pat_" + "A" * 30, "AI" + "za" + "A" * 35, "xox" + "b-" + "1" * 15,
              "-----BEGIN " + "RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----"):
        out, n = L.redact("before " + s + " after")
        assert n >= 1 and "[REDACTED:" in out, s[:8]
        assert out.startswith("before ") and out.endswith(" after") or "PRIVATE" in s
    out, n = L.redact("普通の文。キー無し。")
    assert (out, n) == ("普通の文。キー無し。", 0)
    assert L.args_sha256({"a": 1, "b": [1, 2]}) == L.args_sha256({"b": [1, 2], "a": 1})


def test_events_add_tool_call_keep_args(tmp_path):
    d = tmp_path / "l"
    r = cli("events", "add", "tool_call", "--ledger-dir", str(d), "--actor-type", "agent", "--actor-id", "a",
            "--tool-name", "Bash", "--args", json.dumps({"command": f"curl -H 'x: {KEY}' https://e"}), "--keep-args")
    assert r.returncode == 0, r.stderr
    assert_clean(d, ALL)
    assert rows(d)[0]["data"]["redactions"] >= 1 and "[REDACTED:" in json.dumps(rows(d)[0]["data"]["args"])
    assert KEY not in r.stdout + r.stderr


def test_no_keep_args_stores_no_body(tmp_path):
    d = tmp_path / "l"
    harmless = "harmlesswordXYZ"
    r = cli("events", "add", "tool_call", "--ledger-dir", str(d), "--actor-type", "agent", "--actor-id", "a",
            "--tool-name", "Bash", "--args", json.dumps({"command": f"echo {harmless} {KEY}"}))
    assert r.returncode == 0
    b = all_bytes(d)
    assert harmless.encode() not in b and KEY.encode() not in b
    assert len(rows(d)[0]["data"]["args_sha256"]) == 64 and "args" not in rows(d)[0]["data"]


def _hook_cmd(*extra):
    r = cli("hooks", "print", "--claude-code", *extra)
    return json.loads(r.stdout)["hooks"]["PostToolUse"][0]["hooks"][0]["command"], json.loads(r.stdout)["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]


def test_hook_posttooluse_with_and_without_keep_args(tmp_path):
    harmless = "harmlesswordXYZ"
    pl = json.dumps({"session_id": "s", "hook_event_name": "PostToolUse", "tool_name": "Bash",
                     "tool_input": {"command": f"echo {harmless} {KEY} {KV}"}})
    for extra, key in (((), "off"), (("--keep-args",), "on")):
        proj = tmp_path / key
        proj.mkdir()
        c, _ = _hook_cmd(*extra)
        r = subprocess.run(c, shell=True, input=pl, capture_output=True, text=True, env=_env(CLAUDE_PROJECT_DIR=str(proj)), cwd=str(proj))
        assert r.returncode == 0 and r.stdout == ""
        d = proj / ".vera" / "ledger"
        assert_clean(d, ALL)
        data = rows(d)[0]["data"]
        if key == "off":
            assert harmless.encode() not in all_bytes(d) and "args" not in data
        else:
            assert data["redactions"] >= 1 and harmless in json.dumps(data["args"])


def test_owner_utterance_with_key_is_redacted_and_counted(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    _, c = _hook_cmd()
    text = f"このキーを使って: {KEY} と {GH}。よろしく"
    r = subprocess.run(c, shell=True, input=json.dumps({"session_id": "s", "hook_event_name": "UserPromptSubmit", "prompt": text}),
                       capture_output=True, text=True, env=_env(CLAUDE_PROJECT_DIR=str(proj)), cwd=str(proj))
    assert r.returncode == 0
    d = proj / ".vera" / "ledger"
    assert_clean(d, ALL)
    row = rows(d)[0]
    assert row["data"]["redactions"] >= 2
    assert row["data"]["text"].startswith("このキーを使って: ") and row["data"]["text"].endswith("よろしく")


def test_rejects_file_has_no_plaintext_secret(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    _, c = _hook_cmd()
    subprocess.run(c, shell=True, input="{broken " + KEY, capture_output=True, text=True, env=_env(CLAUDE_PROJECT_DIR=str(proj)), cwd=str(proj))
    d = proj / ".vera" / "ledger"
    assert (d / "rejects.jsonl").exists()
    assert_clean(d, ALL)


def test_vera_run_keep_args_redacts_argv_everywhere(tmp_path):
    d = tmp_path / "l"
    r = cli("run", "--ledger-dir", str(d), "--keep-args", "--", "sh", "-c", f"echo {KEY}; sleep 0")
    assert r.returncode == 0
    assert_clean(d, ALL)
    st = rows(d)[0]["data"]
    assert st["redactions"] >= 1 and "[REDACTED:" in json.dumps(st["argv"])


def test_vera_run_without_keep_args_has_no_argv(tmp_path):
    d = tmp_path / "l"
    r = cli("run", "--ledger-dir", str(d), "--", "sh", "-c", f"echo harmlesswordXYZ {KEY}; sleep 0")
    assert r.returncode == 0
    b = all_bytes(d)
    assert b"harmlesswordXYZ" not in b and KEY.encode() not in b
    assert "argv" not in rows(d)[0]["data"]


def test_argv0_is_redacted(tmp_path):
    d = tmp_path / "l"
    script = tmp_path / ("tool-" + KEY)
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(0o755)
    cli("run", "--ledger-dir", str(d), "--", str(script))
    assert_clean(d, ALL)


# ---- 第 2 ラウンド追加（レビュー必須 1）: 安全網の誤検出で逐語の発話が失われない ---------------------------
def _hook_prompt(tmp_path, prompt):
    sys.path.insert(0, str(ROOT))
    r = cli("hooks", "print", "--claude-code")
    tpl = json.loads(r.stdout)
    cmd = tpl["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                       env=_env(CLAUDE_PROJECT_DIR=str(tmp_path)), input=json.dumps({"prompt": prompt}), cwd=str(tmp_path))
    assert p.returncode == 0, p.stderr
    d = tmp_path / ".vera" / "ledger"
    rs = [json.loads(x) for x in (d / "events.jsonl").read_text(encoding="utf-8").split("\n") if x.strip()] if (d / "events.jsonl").exists() else []
    return d, rs


def test_nonsecret_token_word_newline_kept_verbatim(tmp_path):
    prompt = "新しい " + "token:" + "\n" + "abcdefg" + " を試して"
    d, rs = _hook_prompt(tmp_path, prompt)
    assert len(rs) == 1 and rs[0]["kind"] == "owner_utterance"
    assert rs[0]["data"]["text"] == prompt and rs[0]["data"]["redactions"] == 0


def test_password_tab_secret_redacted_and_kept(tmp_path):
    secret = "abcdefgh"
    prompt = "pass" + "word=" + "\t" + secret
    d, rs = _hook_prompt(tmp_path, prompt)
    assert len(rs) == 1 and rs[0]["data"]["redactions"] >= 1
    assert secret.encode() not in all_bytes(d)


def test_numeric_secret_named_key_is_accepted(tmp_path):
    sys.path.insert(0, str(ROOT))
    from verantyx import ledger_events as L
    row = L.append(tmp_path / "l", "tool_call", {"type": "agent", "id": "a"}, {"input_token": 12345678, "redactions": 0})
    assert row["data"]["input_token"] == 12345678


def test_safety_net_still_refuses_unredacted_secret(tmp_path):
    sys.path.insert(0, str(ROOT))
    from verantyx import ledger_events as L
    with pytest.raises(L.LedgerError) as e:
        L.append(tmp_path / "l", "tool_call", {"type": "agent", "id": "a"}, {"x": KEY})
    assert e.value.code == "UNREDACTED_SECRET_REFUSED"


# ---- 第 3 ラウンド（レビュー r2 必須 1: redact の冪等性）。追加のみ ----
def _bodies():
    return {
        "akia": ("AK" + "IA" + "ZZZZYYYYXXXXWWWW", "ZZZZYYYYXXXXWWWW"),
        "pat": ("github" + "_pat_" + "QQQQRRRRSSSSTTTT11112222", "QQQQRRRRSSSSTTTT11112222"),
        "ghp": ("gh" + "p_" + "MMMMNNNNOOOOPPPP11112222", "MMMMNNNNOOOOPPPP11112222"),
        "sk": ("s" + "k-" + "LLLLKKKKJJJJIIII1234", "LLLLKKKKJJJJIIII1234"),
        "xox": ("xo" + "xb-" + "1234567890-HHHHGGGGFFFF", "HHHHGGGGFFFF"),
    }


def test_redact_is_idempotent_on_adjacent_secrets():
    sys.path.insert(0, str(ROOT))
    from verantyx import ledger_events as L
    b = _bodies()
    for a in b.values():
        for c in b.values():
            for pre in ("", "日本語"):
                x = pre + a[0] + c[0]
                r, n = L.redact(x)
                assert L.redact(r)[1] == 0, x
                assert n >= 1  # 前の鍵の形が後ろを飲み込む組もあるので個数は下限だけ
                assert a[1] not in r and c[1] not in r


def test_hook_owner_utterance_with_adjacent_keys_kept(tmp_path):
    k1 = "AK" + "IA" + "ZZZZYYYYXXXXWWWW"
    k2 = "AK" + "IA" + "QQQQRRRRSSSSTTTT"
    d, rs = _hook_prompt(tmp_path, "止めて。鍵は " + k1 + k2 + " です")
    assert len(rs) == 1 and rs[0]["kind"] == "owner_utterance"
    assert rs[0]["data"]["redactions"] >= 2
    b = all_bytes(d)
    assert k1.encode() not in b and k2.encode() not in b and b"QQQQRRRRSSSSTTTT" not in b


def test_run_keep_args_descendant_adjacent_keys_not_in_any_file(tmp_path):
    d = tmp_path / "lk"
    p = "AK" + "I"
    script = 'K=' + p + 'A; sh -c "sleep 1.5; : ${K}ZZZZYYYYXXXXWWWW${K}QQQQRRRRSSSSTTTT"; true'
    r = cli("run", "--keep-args", "--sample-interval", "0.2", "--ledger-dir", str(d), "--", "sh", "-c", script)
    assert r.returncode == 0, r.stderr
    b = all_bytes(d)
    # 子の argv の本文（ここでは鍵の形になっていない断片）は残ってよい。完成した鍵の形だけが無いこと。
    assert ("AK" + "IA" + "QQQQRRRRSSSSTTTT").encode() not in b and ("AK" + "IA" + "ZZZZYYYYXXXXWWWW").encode() not in b
    assert (d / "runs").is_dir() and any((d / "runs").iterdir())


# ---- 第 4 ラウンド（監査役の裁定: 左境界を外し、鍵の形そのもので判定。過剰な伏せは許し、漏れは許さない）。追加のみ ----
_R4_KEYS = {  # 名前: (完成形, 本体)。本体だけを漏れの判定に使う
    "sk_ant": ("sk-" + "ant-api03-" + "Q7R8" * 6, "Q7R8" * 6),
    "github_pat": ("github" + "_pat_" + "W3X4" * 6, "W3X4" * 6),
    "gh_token": ("gh" + "p_" + "M5N6" * 6, "M5N6" * 6),
    "aws_akia": ("AK" + "IA" + "ZZZZYYYYXXXXWWWW", "ZZZZYYYYXXXXWWWW"),
    "google_api_key": ("AI" + "za" + "G1h2" * 8 + "G1h", "G1h2" * 8),
    "slack_token": ("xo" + "xb-" + "1234567890-" + "S9t8" * 4, "S9t8" * 4),
    "sk": ("s" + "k-" + "proj-" + "P4q5" * 5, "P4q5" * 5),
    "bearer": ("Bear" + "er " + "B7c6" * 8, "B7c6" * 8),
    "kv_secret": ("pass" + "word=" + "V2w3" * 3, "V2w3" * 3),
}
_R4_SEPS = ["", " ", "\n", "\t", "\\n", "\\t", "\\r", "%0A", "%20", "=", ":", "'", '"', "/", "?q=", ",", "日本語"]
_R4_PRES = ["", "x", "1", "abc", "K=1", "\\n", "%0A", "日本語", "ヘッダは"]

_R4_CASES = [
    'echo -e "x\\n' + AWS + '"',
    "printf 'a\\t" + "sk-" + "ant-api03-" + "Q7R8" * 6 + "'",
    "curl 'https://h/?q=1%0A" + GH + "'",
    "K=1" + "sk-" + "ant-api03-" + "Q7R8" * 6,
    "a\\n" + "s" + "k-" + "proj-" + "P4q5" * 5,
    "日本" + "Bear" + "er " + "B7c6" * 8,
    "--key=x" + AWS,
]


@pytest.mark.parametrize("src", _R4_CASES, ids=[f"case{i}" for i in range(len(_R4_CASES))])
def test_r4_redact_after_alnum_escape_urlenc_japanese(src):
    from verantyx import ledger_events as L
    out, n = L.redact(src)
    assert n >= 1, src[:6]
    for _name, (_full, body) in _R4_KEYS.items():
        assert body not in out, _name
    assert "ABCDEFGHIJKLMNOP" not in out and "Q" * 24 not in out
    assert L.redact(out)[1] == 0


def _r4_check(x, label):
    from verantyx import ledger_events as L
    out, n = L.redact(x)
    bad = [k for k, (_f, body) in _R4_KEYS.items() if body in out]
    if bad or L.redact(out)[1] != 0 or out == "[REDACTED:unbounded]":
        return f"{label} 漏れ={bad} 冪等={L.redact(out)[1] == 0} unbounded={out == '[REDACTED:unbounded]'}"
    return None


def test_r4_fuzz_single_all_combinations():
    fails = []
    for name, (full, _b) in _R4_KEYS.items():
        for sep in _R4_SEPS:
            for pre in _R4_PRES:
                r = _r4_check(pre + sep + full + " tail", f"{name}|{_R4_SEPS.index(sep)}|{_R4_PRES.index(pre)}")
                if r:
                    fails.append(r)
    assert not fails, fails[:5]


def test_r4_fuzz_pairs_all_combinations():
    fails = []
    for n1, (f1, _b1) in _R4_KEYS.items():
        for n2, (f2, _b2) in _R4_KEYS.items():
            for si, sep in enumerate(_R4_SEPS):
                for pi, pre in enumerate(_R4_PRES):
                    r = _r4_check(pre + f1 + sep + f2, f"{n1}+{n2}|{si}|{pi}")
                    if r:
                        fails.append(r)
    assert not fails, (len(fails), fails[:5])


def test_r4_nonsecret_text_unchanged():
    from verantyx import ledger_events as L
    for s in ("普通の文。キー無し。", "Bear" + "er token を使う", "新しい " + "token:" + "\n" + "abcdefg"):
        assert L.redact(s) == (s, 0), s


def test_r4_specific_name_wins_on_overlap():
    from verantyx import ledger_events as L
    out, n = L.redact("K=1" + _R4_KEYS["sk_ant"][0])
    assert out == "K=1[REDACTED:sk_ant]" and n == 1


def test_r4_ledger_run_keep_args_after_escape(tmp_path):
    d = tmp_path / "l4a"
    r = cli("run", "--ledger-dir", str(d), "--keep-args", "--", "sh", "-c", "printf 'x\\n" + AWS + "\\n' >/dev/null")
    assert r.returncode == 0, r.stderr
    assert_clean(d, [AWS, "ABCDEFGHIJKLMNOP"])
    assert rows(d)[0]["data"]["redactions"] >= 1


def test_r4_ledger_hook_posttooluse_after_escape(tmp_path):
    proj = tmp_path / "p4b"
    proj.mkdir()
    c, _ = _hook_cmd("--keep-args")
    pl = json.dumps({"session_id": "s", "hook_event_name": "PostToolUse", "tool_name": "Bash",
                     "tool_input": {"command": 'echo -e "a\\n' + AWS + '"'}})
    r = subprocess.run(c, shell=True, input=pl, capture_output=True, text=True, env=_env(CLAUDE_PROJECT_DIR=str(proj)), cwd=str(proj))
    assert r.returncode == 0 and r.stdout == ""
    d = proj / ".vera" / "ledger"
    assert_clean(d, [AWS, "ABCDEFGHIJKLMNOP"])
    assert rows(d)[0]["data"]["redactions"] >= 1


def test_r4_ledger_owner_utterance_japanese_bearer_verbatim_rest(tmp_path):
    body = "k" * 32
    d, rs = _hook_prompt(tmp_path, "ヘッダは" + "Bear" + "er " + body)
    assert len(rs) == 1 and rs[0]["kind"] == "owner_utterance"
    assert rs[0]["data"]["redactions"] >= 1
    assert rs[0]["data"]["text"] == "ヘッダは" + "Bear" + "er [REDACTED:bearer]"
    assert body.encode() not in all_bytes(d)


def test_r4_password_password_value_redacted():
    from verantyx import ledger_events as L
    # 第 4 ラウンドのレビュー必須 1: 鍵語が重なる形も値が残らない（_spans が重なりを許すため）
    val = "hunter2" + "hunter2"
    for k in (2, 3):
        src = ("pass" + "word: ") * k + val
        out, n = L.redact(src)
        assert val not in out and "hunter2" not in out
        assert n >= k
        assert L.redact(out)[1] == 0
        assert out != "[REDACTED:unbounded]"
