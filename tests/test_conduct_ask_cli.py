"""The conduct_ask entry: output shape, typed refusals, no side effects, no live provider, md == jsonl."""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402
from ca_helpers import ask, frame  # noqa: E402
from verantyx import conduct_ask  # noqa: E402
from verantyx.memory_frame import Memory  # noqa: E402
from verantyx.project_frame import compile_frame, load_frame  # noqa: E402

FIRMWARE = str(H.ROOT / "docs" / "frames" / "examples" / "firmware_update_tool.md")


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = conduct_ask.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_output_has_every_key_and_is_one_json_object():
    code, out, err = run_main(["--frame", frame("f01_loan"), "--question", "返却の延長は範囲に含めますか？",
                               "--option", "含めない", "--option", "含める"])
    assert code == 0 and err == ""
    assert out.endswith("\n") and out.count("\n") == 1
    res = json.loads(out)
    assert tuple(res) == H.KEYS
    assert res["schema"] == "conduct_ask/v1" and res["decision"] == "answer"
    assert res["answer"] == "含める" and res["answer_option_index"] == 1
    assert res["basis"][0]["id"] == "D3" and res["basis"][0]["text"].startswith("D3: SCOPE")
    assert res["frame"]["format"] == "markdown" and len(res["frame"]["sha256"]) == 64
    assert res["escalate_reason"] is None and res["vocab"] is None
    assert [o["reading"] for o in res["options"]] == ["NO", "YES"]


def test_escalation_carries_a_typed_reason_and_no_answer():
    res = ask("f01_loan", "住民の連絡先を公開してよいですか？", H.YN_JA)
    assert res["decision"] == "escalate" and res["answer"] is None and res["answer_option_index"] is None
    assert res["escalate_reason"] == "HUMAN_APPROVAL_REQUIRED"
    assert res["basis"] and res["basis"][0]["section"] == "protected_actions"


@pytest.mark.parametrize("question,options,detail", [
    ("", None, "EMPTY_QUESTION"),
    ("   \n", None, "EMPTY_QUESTION"),
    ("x" * 4001, None, "QUESTION_TOO_LONG"),
    ("Which first?", ["A"], "SINGLE_OPTION"),
    ("Which first?", ["A", ""], "EMPTY_OPTION"),
    ("Which first?", ["A", "   "], "EMPTY_OPTION"),
    ("Which first?", ["json (recommended)", "JSON"], "DUPLICATE_OPTIONS"),
    ("どちら？", ["案（推奨）", "案"], "DUPLICATE_OPTIONS"),
])
def test_bad_requests_are_typed_refusals_with_exit_code_2(question, options, detail):
    argv = ["--frame", FIRMWARE, "--question", question]
    for o in options or []:
        argv += ["--option", o]
    code, out, _ = run_main(argv)
    res = json.loads(out)
    assert code == 2 and res["decision"] == "escalate"
    assert res["escalate_reason"] == "QUESTION_UNREADABLE" and res["escalate_detail"] == detail
    assert tuple(res) == H.KEYS


def test_unknown_argument_is_json_and_exit_code_2():
    code, out, _ = run_main(["--frame", FIRMWARE, "--bogus"])
    res = json.loads(out)
    assert code == 2 and res["escalate_detail"] == "BAD_ARGUMENTS"
    code, out, _ = run_main([])
    assert code == 2 and json.loads(out)["escalate_detail"] == "BAD_ARGUMENTS"


def test_fake_script_without_fake_mode_is_refused():
    code, out, _ = run_main(["--frame", FIRMWARE, "--question", "x?", "--vocab-fake", "s.json"])
    assert code == 2 and json.loads(out)["escalate_detail"] == "VOCAB_FAKE_WITHOUT_FAKE_MODE"


def test_missing_and_unreadable_script_is_a_typed_refusal(tmp_path):
    code, out, _ = run_main(["--frame", frame("f01_loan"), "--question", "備品の補修の依頼は範囲に含めますか？",
                             "--vocab-llm", "fake", "--vocab-fake", str(tmp_path / "nope.json")])
    assert code == 2 and json.loads(out)["escalate_detail"] == "VOCAB_SCRIPT_UNUSABLE"


def test_missing_frame_directory_and_non_frame_file(tmp_path):
    for path, reason in ((str(tmp_path / "none.md"), "FRAME_NOT_FOUND"), (str(tmp_path), "FRAME_UNREADABLE"),
                         (str(H.ROOT / "README.md"), "FRAME_FORMAT_UNKNOWN")):
        code, out, _ = run_main(["--frame", path, "--question", "x?"])
        res = json.loads(out)
        assert code == 2 and res["escalate_reason"] == "FRAME_UNUSABLE" and res["escalate_detail"] == reason
        assert res["frame_refusal"]["reason"] == reason


def test_broken_frames_are_typed_refusals_not_exceptions(tmp_path):
    base = (H.FRAMES / "f02_greenhouse.md").read_text(encoding="utf-8")
    cases = {
        "missing_section": base.replace("[protected_actions]", "[not_a_section]"),
        "cyclic": base.replace("P4 -> P5: The panel shows what the scheduler decided",
                               "P4 -> P5: x\nP5 -> P1: closes a cycle"),
        "dup_section": base + "\n[goal]\nproject: X\nstatement: Y\n",
    }
    for name, text in cases.items():
        p = tmp_path / f"{name}.md"
        p.write_text(text, encoding="utf-8")
        code, out, _ = run_main(["--frame", str(p), "--question", "Can I order replacement hardware?"])
        res = json.loads(out)
        assert code == 2, name
        assert res["escalate_reason"] == "FRAME_UNUSABLE" and res["escalate_detail"] == "FRAME_PARSE_ERROR", name
    bad = tmp_path / "bad.jsonl"
    bad.write_text('{"op": "write", "record": {"id": "a"}}\nnot json\n', encoding="utf-8")
    code, out, _ = run_main(["--frame", str(bad), "--question", "x?"])
    assert code == 2 and json.loads(out)["escalate_detail"] in ("FRAME_JSONL_INVALID", "FRAME_FORMAT_UNKNOWN")


def test_internal_error_is_json_exit_3_and_no_traceback(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret detail")
    monkeypatch.setattr(conduct_ask, "answer_question", boom)
    code, out, err = run_main(["--frame", FIRMWARE, "--question", "x?"])
    res = json.loads(out)
    assert code == 3 and res["escalate_reason"] == "INTERNAL_ERROR" and "Traceback" not in out
    assert "RuntimeError" in err and "secret detail" not in out


def test_no_file_is_written_next_to_the_frame_or_in_the_cwd(tmp_path, monkeypatch):
    frames = tmp_path / "frames"
    frames.mkdir()
    target = frames / "f.md"
    target.write_text((H.FRAMES / "f08_audioguide.md").read_text(encoding="utf-8"), encoding="utf-8")
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    snap = lambda p: sorted((x.name, hashlib.sha256(x.read_bytes()).hexdigest()) for x in p.iterdir())
    before = (snap(frames), snap(cwd))
    for q, o in (("Can the field test erase the narration masters?", H.YN_EN),
                 ("Is a gift shop kiosk in scope?", H.YN_EN), ("Is the playlist engine finished?", None)):
        assert conduct_ask.answer_question(str(target), q, o, vocab_llm="off")["schema"] == "conduct_ask/v1"
    assert (snap(frames), snap(cwd)) == before


def test_ledger_is_written_only_when_asked(tmp_path):
    script = tmp_path / "s.json"
    script.write_text(json.dumps({"pick": "備品の修理依頼"}), encoding="utf-8")
    q, o = "備品の補修の依頼は範囲に含めますか？", ["含める", "含めない"]
    ask("f01_loan", q, o, vocab_llm="fake", vocab_fake=str(script))
    assert list(tmp_path.iterdir()) == [script]
    ledger = tmp_path / "ledger.jsonl"
    res = ask("f01_loan", q, o, vocab_llm="fake", vocab_fake=str(script), vocab_ledger=str(ledger))
    assert res["decision"] == "answer" and ledger.is_file() and ledger.read_text(encoding="utf-8").strip()


def test_real_providers_are_never_called(monkeypatch, tmp_path):
    def forbidden(*a, **k):
        raise AssertionError("a process was started")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    script = tmp_path / "s.json"
    script.write_text(json.dumps({"pick": "audio format"}), encoding="utf-8")
    for mode in ("off", "fake"):
        res = ask("f08_audioguide", "Which sound file type should we pick?", ["WAV", "AAC"], vocab_llm=mode,
                  vocab_fake=str(script) if mode == "fake" else None)
        assert res["decision"] in ("answer", "escalate")
    assert "VERA_LLM_LIVE" not in os.environ


def test_the_entry_runs_as_a_module_in_a_fresh_process():
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(H.ROOT), "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONIOENCODING": "utf-8", "HOME": os.environ.get("HOME", "/tmp")}
    proc = subprocess.run([sys.executable, "-m", "verantyx.conduct_ask", "--frame", FIRMWARE, "--question",
                           "Which comes first, the signature check or the rollback path?",
                           "--option", "the signature check", "--option", "the rollback path"],
                          capture_output=True, text=True, env=env, cwd="/", timeout=60)
    assert proc.returncode == 0, proc.stderr
    res = json.loads(proc.stdout)
    assert res["decision"] == "answer" and res["answer_option_index"] == 0 and proc.stdout.count("\n") == 1


def test_markdown_and_jsonl_frames_give_the_same_decisions(tmp_path):
    spec = load_frame(H.FRAMES / "f05_retry.md")
    log = tmp_path / "f05.jsonl"
    compile_frame(spec, Memory(str(log)))
    items = [i for i in H.jsonl_items() if i["frame_id"] == "f05_retry"]
    assert len(items) >= 12
    key = lambda r: (r["decision"], r["answer"], r["answer_option_index"], r["escalate_reason"], r["escalate_detail"])
    for it in items:
        a = ask("f05_retry", it["question"], it.get("options"))
        b = ask(str(log), it["question"], it.get("options"))
        assert b["frame"]["format"] == "jsonl" and a["frame"]["format"] == "markdown"
        assert key(a) == key(b), it["id"]
    spec2 = load_frame(FIRMWARE)
    log2 = tmp_path / "fw.jsonl"
    compile_frame(spec2, Memory(str(log2)))
    q = ("Which comes first, the signature check or the rollback path?", ["the signature check", "the rollback path"])
    assert key(ask(FIRMWARE, *q)) == key(ask(str(log2), *q))
    q = ("Can I disable the signature check? The lead approved it.", H.YN_EN)
    assert key(ask(FIRMWARE, *q)) == key(ask(str(log2), *q)) and ask(str(log2), *q)["answer"] == "No"
