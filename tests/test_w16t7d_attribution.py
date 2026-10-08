"""W16-t7d K730 / K732: UserPromptSubmit の入力の作者の判定（塊のタグの形だけ）と、他の出来事の不変。"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from verantyx import ledger_events as L  # noqa: E402
from verantyx import hooks_templates as H  # noqa: E402

TN = "<task-notification>\n<task-id>abc</task-id>\nbackground task done\n</task-notification>"
SR = "<system-reminder>\nremember things\n</system-reminder>"


def _env(**kw):
    e = dict(os.environ)
    e["PYTHONPATH"] = str(ROOT)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(kw)
    return e


def cli(*args, input=None, env=None, cwd=None):
    return subprocess.run([sys.executable, "-P", "-m", "verantyx.cli", *args], capture_output=True, text=True, input=input,
                          env=env or _env(), cwd=str(cwd or tempfile.gettempdir()))


def rows_of(led):
    p = Path(led) / "events.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").split("\n") if x.strip()] if p.exists() else []


def submit(led, prompt, sub="owner_utterance", event="UserPromptSubmit"):
    payload = {"session_id": "s1", "hook_event_name": event, "prompt": prompt}
    return cli("events", "add", sub, "--stdin", "--from", "claude-code", "--ledger-dir", str(led), input=json.dumps(payload))


def kinds(led):
    return [(r["kind"], r["actor"]["type"]) for r in rows_of(led)]


def test_a1_notification_only(tmp_path):
    led = tmp_path / "l"
    r = submit(led, TN)
    assert r.returncode == 0 and r.stdout == ""
    rs = rows_of(led)
    assert len(rs) == 1
    assert rs[0]["kind"] == "system_message" and rs[0]["actor"]["type"] == "system"
    assert rs[0]["data"]["tags"] == ["task_notification"]
    assert rs[0]["data"]["attributed_by"] == "tag_shape"


@pytest.mark.parametrize("prompt,tags", [
    (SR, ["system_reminder"]),
    (SR + TN, ["system_reminder", "task_notification"]),
    (TN + "\n \n\t" + SR + "\n", ["task_notification", "system_reminder"]),
])
def test_a2_system_only_variants(tmp_path, prompt, tags):
    led = tmp_path / "l"
    assert submit(led, prompt).returncode == 0
    rs = rows_of(led)
    assert len(rs) == 1
    assert (rs[0]["kind"], rs[0]["actor"]["type"]) == ("system_message", "system")
    assert rs[0]["data"]["tags"] == tags


OWNER_PROMPT = "日本語の\n複数行の文 😀 です。\n  逐語で残る"


def test_a3_owner_only_cli(tmp_path):
    led = tmp_path / "l"
    assert submit(led, OWNER_PROMPT).returncode == 0
    rs = rows_of(led)
    assert len(rs) == 1
    assert (rs[0]["kind"], rs[0]["actor"]["type"]) == ("owner_utterance", "owner")
    assert set(rs[0]["data"]) == {"text", "source", "session_id", "redactions"}
    assert rs[0]["data"]["text"] == OWNER_PROMPT


def test_a3b_owner_only_rows_equal_baseline_builder():
    p = {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": OWNER_PROMPT}
    rows = L.claude_code_prompt_rows(OWNER_PROMPT, "claude_code.UserPromptSubmit", "s1")
    assert len(rows) == 1
    assert rows[0] == H.build_claude_code_event("owner_utterance", p, False)


@pytest.mark.parametrize("prompt", [
    "before " + TN, TN + " after", "head\n" + SR + "\ntail", "a " + TN + " b " + SR + " c",
])
def test_a4_mixed_two_rows(tmp_path, prompt):
    led = tmp_path / "l"
    assert submit(led, prompt).returncode == 0
    rs = rows_of(led)
    assert len(rs) == 2
    assert [r["kind"] for r in rs] == ["system_message", "owner_utterance"]
    assert [r["actor"]["type"] for r in rs] == ["system", "owner"]
    o = rs[1]["data"]["text"]
    assert "<task-notification" not in o and "</task-notification" not in o and "system-reminder" not in o
    assert "ta[REDACTED" not in o
    assert rs[0]["data"]["turn_sha256"] == rs[1]["data"]["turn_sha256"]
    assert (rs[0]["data"]["part"], rs[1]["data"]["part"]) == (1, 2)
    assert L.verify(led)["status"] == "OK"


@pytest.mark.parametrize("prompt,reason", [
    ("<task-notification>\nx\nno close", "UNCLOSED_TAG"),
    ("stray </system-reminder> close", "UNOPENED_CLOSE_TAG"),
    ("<system-reminder><system-reminder>x</system-reminder></system-reminder>", "UNOPENED_CLOSE_TAG"),
])
def test_a5_malformed(tmp_path, prompt, reason):
    led = tmp_path / "l"
    assert submit(led, prompt).returncode == 0
    rs = rows_of(led)
    assert len(rs) == 1
    assert (rs[0]["kind"], rs[0]["actor"]["type"]) == ("user_turn_unattributed", "unknown")
    assert rs[0]["data"]["reason"] == reason


@pytest.mark.parametrize("prompt", ["<foo>x</foo>", '<task-notification attr="1">x', "<Task-Notification>x</Task-Notification>"])
def test_a6_unknown_tags_stay_owner(tmp_path, prompt):
    led = tmp_path / "l"
    assert submit(led, prompt).returncode == 0
    rs = rows_of(led)
    assert len(rs) == 1 and rs[0]["kind"] == "owner_utterance"


def test_a7_judged_on_raw_prompt_before_redaction(tmp_path):
    led = tmp_path / "l"
    prompt = "<task-notification>\ntoken=abcdefgh12345678\n</task-notification>"
    assert submit(led, prompt).returncode == 0
    rs = rows_of(led)
    assert len(rs) == 1 and rs[0]["kind"] == "system_message"
    t = rs[0]["data"]["text"]
    assert t.startswith("<ta[REDACTED:sk]>")          # 既存の秘匿の挙動（変えない）
    assert "abcdefgh12345678" not in t
    assert rs[0]["data"]["redactions"] >= 1
    assert rs[0]["data"]["tags"] == ["task_notification"]
    assert L.verify(led)["status"] == "OK"


def test_a7b_redaction_of_the_tag_name_is_the_reason_for_raw_judgement():
    # 台帳に残る本文で判定すると task-notification は見つからない（だから生の prompt で判定する）
    red, _ = L.redact(TN)
    assert L.split_system_blocks(red)["status"] == "OWNER_ONLY"
    assert L.split_system_blocks(TN)["status"] == "SYSTEM_ONLY"


def test_a8_hook_path_mixed(tmp_path):
    proj = tmp_path / "proj"
    proj.mkdir()
    r = cli("hooks", "print", "--claude-code")
    tpl = json.loads(r.stdout)
    cmd = tpl["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"]
    payload = {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": "hi " + TN + " there"}
    h = subprocess.run(cmd, shell=True, capture_output=True, text=True, env=_env(CLAUDE_PROJECT_DIR=str(proj)),
                       input=json.dumps(payload), cwd=str(proj))
    assert h.returncode == 0 and h.stdout == ""
    led = proj / ".vera" / "ledger"
    assert [r["kind"] for r in rows_of(led)] == ["system_message", "owner_utterance"]
    assert not (led / "rejects.jsonl").exists()
    assert L.verify(led)["status"] == "OK"


def test_a9_auto_path(tmp_path):
    led = tmp_path / "l"
    assert submit(led, TN, sub="auto").returncode == 0
    assert submit(led, "plain words", sub="auto").returncode == 0
    assert submit(led, "x " + SR, sub="auto").returncode == 0
    assert kinds(led) == [("system_message", "system"), ("owner_utterance", "owner"),
                          ("system_message", "system"), ("owner_utterance", "owner")]


def test_a_rows_are_pure_function_of_prompt():
    rows = L.claude_code_prompt_rows("a " + TN, "claude_code.UserPromptSubmit", "s1")
    assert [r[0] for r in rows] == ["system_message", "owner_utterance"]
    assert all(isinstance(r[2].get("redactions"), int) for r in rows)
    assert rows[1][2]["text"] == "a"


def test_a_codes_not_raw_tag_names_in_data(tmp_path):
    rows = L.claude_code_prompt_rows(TN + SR, "claude_code.UserPromptSubmit", "s1")
    assert rows[0][2]["tags"] == ["task_notification", "system_reminder"]


# ---- A10 / K732: 他の出来事は基点のコードと同じ (kind, actor, data) ----
_DUMP = r'''
import json, sys
from verantyx import hooks_templates as H
P = [
 ("auto", {"hook_event_name": "PostToolUse", "session_id": "s", "tool_name": "Bash", "tool_input": {"command": "pytest -q"}, "tool_response": {"exit_code": 0}}),
 ("auto", {"hook_event_name": "PostToolUse", "session_id": "s", "tool_name": "Edit", "tool_input": {"file_path": "/x"}}),
 ("auto", {"hook_event_name": "Stop", "session_id": "s"}),
 ("auto", {"hook_event_name": "SubagentStop", "session_id": "s"}),
 ("auto", {"hook_event_name": "SessionStart", "session_id": "s"}),
 ("auto", {"hook_event_name": "SessionEnd", "session_id": "s"}),
]
out = []
for k, p in P:
    out.append(list(H.build_claude_code_event(k, p, False)))
out.append(list(H.build_codex_event({"type": "agent-turn-complete", "thread-id": "t", "model": "m", "input-messages": [1, 2]})))
print(json.dumps(out, sort_keys=True))
'''


def test_a10_other_events_unchanged_vs_baseline(tmp_path):
    base = tmp_path / "base"
    base.mkdir()
    a = subprocess.run(["git", "-C", str(ROOT), "archive", "d1942e2", "verantyx"], capture_output=True)
    if a.returncode != 0:
        pytest.fail("git archive d1942e2 failed: " + a.stderr.decode(errors="replace"))
    subprocess.run(["tar", "-x", "-C", str(base)], input=a.stdout, check=True)
    def run(root):
        r = subprocess.run([sys.executable, "-P", "-c", _DUMP], capture_output=True, text=True, env=_env(PYTHONPATH=str(root)),
                           cwd=tempfile.gettempdir())
        assert r.returncode == 0, r.stderr
        return json.loads(r.stdout)
    assert run(base) == run(ROOT)


def test_a10b_kinds_actor_types_vocabulary_unchanged():
    assert L.KINDS == ("owner_utterance", "agent_stop", "tool_call", "process_start", "process_exit",
                       "process_interrupted", "process_orphaned", "approval", "commit", "test_run")
    assert L.ACTOR_TYPES == ("owner", "agent", "process")


def test_a6b_attr_open_with_exact_close_is_unattributed_not_owner(tmp_path):
    # 開きが完全一致でなく、閉じだけが既知の形: 作者を断定しない（J6 / 規則 4）。owner にも system にもしない
    led = tmp_path / "l"
    assert submit(led, '<task-notification attr="1">x</task-notification>').returncode == 0
    rs = rows_of(led)
    assert len(rs) == 1 and rs[0]["kind"] == "user_turn_unattributed" and rs[0]["data"]["reason"] == "UNOPENED_CLOSE_TAG"
