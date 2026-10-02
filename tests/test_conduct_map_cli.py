"""The entry: new arguments, typed refusals (exit code 2), the output keys, and that off never imports the mapping."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import map_helpers as M  # noqa: E402
from map_helpers import w2g  # noqa: E402
from verantyx import conduct_ask  # noqa: E402

H = M.H
F = w2g("w01_shelfcheck")
Q = "地元の歴史に関する資料も、確認する本に入りますか？"
GOOD = {"records": ["D3"], "decides": "決まる", "relations": {"D3": ["一致", "矛盾"]}}


@pytest.fixture(autouse=True)
def no_process(monkeypatch):
    real_run = subprocess.run

    def guarded(argv, *a, **k):
        if os.path.basename(str(argv[0])) in ("codex", "claude"):
            raise AssertionError("a real provider process must never be started")
        return real_run(argv, *a, **k)
    monkeypatch.setattr(subprocess, "run", guarded)


def run_main(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = conduct_ask.main(argv)
    return code, out.getvalue(), err.getvalue()


def base(*extra):
    return ["--frame", F, "--question", Q, "--option", "はい", "--option", "いいえ", *extra]


@pytest.fixture
def script(tmp_path):
    p = tmp_path / "map.json"
    p.write_text(json.dumps(GOOD, ensure_ascii=False), encoding="utf-8")
    return str(p)


def test_off_and_the_scripted_fake_keep_the_output_keys():
    for extra in ([], ["--vocab-llm", "off"], ["--vocab-llm", "fake"]):
        code, out, err = run_main(base(*extra))
        assert code == 0 and err == ""
        assert tuple(json.loads(out)) == H.KEYS


def test_the_mapping_key_is_last_and_only_present_when_the_mapping_is_on(script):
    code, out, err = run_main(base("--vocab-llm", "fake", "--map-fake", script))
    res = json.loads(out)
    assert code == 0 and tuple(res) == H.KEYS + ("mapping",)
    assert res["decision"] == "answer" and res["answer"] == "はい" and res["mapping"]["outcome"] == "ANSWERED"
    assert res["mapping"]["asks_cap"] == 8


def test_the_ask_cap_is_an_argument_and_a_small_one_hands_up(script):
    code, out, _ = run_main(base("--vocab-llm", "fake", "--map-fake", script, "--map-max-asks", "3"))
    res = json.loads(out)
    assert code == 0 and res["mapping"]["asks_cap"] == 3
    assert (res["escalate_reason"], res["escalate_detail"]) == ("MAPPING_UNSETTLED", "ASK_BUDGET")


@pytest.mark.parametrize("argv,detail", [
    (["--map-fake", "/nonexistent-map.json"], "MAP_FAKE_WITHOUT_FAKE_MODE"),                         # off
    (["--vocab-llm", "claude", "--map-fake", "/nonexistent-map.json"], "MAP_FAKE_WITHOUT_FAKE_MODE"),
    (["--map-second", "codex"], "MAP_SECOND_WITHOUT_REAL_MODE"),
    (["--vocab-llm", "fake", "--map-second", "claude"], "MAP_SECOND_WITHOUT_REAL_MODE"),
    (["--vocab-llm", "fake", "--map-fake", "/nonexistent-map.json"], "MAP_SCRIPT_UNUSABLE"),
    (["--vocab-llm", "codex", "--map-max-asks", "1"], "BAD_MAP_MAX_ASKS"),
    (["--vocab-llm", "fake", "--map-max-asks", "0"], "BAD_MAP_MAX_ASKS"),
    (["--map-second", "gemini", "--vocab-llm", "codex"], "BAD_ARGUMENTS"),
])
def test_typed_refusals_are_exit_code_2(argv, detail):
    code, out, _ = run_main(base(*argv))
    res = json.loads(out)
    assert code == 2 and res["escalate_detail"] == detail and res["decision"] == "escalate"
    assert detail in conduct_ask.INPUT_REFUSALS or detail == "BAD_ARGUMENTS"


def test_an_unreadable_script_is_a_typed_refusal(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("[1, 2", encoding="utf-8")
    code, out, _ = run_main(base("--vocab-llm", "fake", "--map-fake", str(bad)))
    assert code == 2 and json.loads(out)["escalate_detail"] == "MAP_SCRIPT_UNUSABLE"
    arr = tmp_path / "arr.json"
    arr.write_text("[1]", encoding="utf-8")
    code, out, _ = run_main(base("--vocab-llm", "fake", "--map-fake", str(arr)))
    assert code == 2 and json.loads(out)["escalate_detail"] == "MAP_SCRIPT_UNUSABLE"


def test_a_mapper_with_off_is_a_typed_refusal_of_the_api():
    mp = M.mapper_for(F, M.YN_JA, GOOD)
    res = conduct_ask.answer_question(F, Q, M.YN_JA, vocab_llm="off", mapper=mp)
    assert (res["escalate_reason"], res["escalate_detail"]) == ("QUESTION_UNREADABLE", "MAPPER_WITHOUT_LLM_MODE")
    assert mp.ledger.entries() == ()
    res = conduct_ask.answer_question(F, Q, M.YN_JA, vocab_llm="fake", map_second="codex")
    assert res["escalate_detail"] == "MAP_SECOND_WITHOUT_REAL_MODE"
    res = conduct_ask.answer_question(F, Q, M.YN_JA, vocab_llm="codex", map_second="gemini")
    assert res["escalate_detail"] == "BAD_MAP_SECOND"
    res = conduct_ask.answer_question(F, Q, M.YN_JA, vocab_llm="codex", map_max_asks=True)
    assert res["escalate_detail"] == "BAD_MAP_MAX_ASKS"


def test_the_real_modes_build_the_mapper_with_the_second_provider_given(monkeypatch):
    seen = []
    from verantyx import conduct_map

    def spy(mode, second, ledger, max_asks):
        seen.append((mode, second, ledger, max_asks))
        return M.mapper_for(F, M.YN_JA, GOOD)
    monkeypatch.setattr(conduct_map, "build_real_mapper", spy)
    res = conduct_ask.answer_question(F, Q, M.YN_JA, vocab_llm="codex", map_second="claude", map_max_asks=6)
    assert seen == [("codex", "claude", None, 6)] and res["decision"] == "answer"
    res = conduct_ask.answer_question(F, "雑誌の点検は今回の範囲に含めますか？", M.YN_JA, vocab_llm="claude")
    assert seen[-1] == ("claude", None, None, 8) and res["mapping"]["route"] == "CORROBORATE"


def _fresh(code):
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(H.ROOT), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
           "HOME": os.environ.get("HOME", "/tmp")}
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd="/", timeout=120)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_off_never_imports_the_mapping_module():
    code = ("import sys, verantyx.conduct_ask as c\n"
            f"r = c.answer_question({F!r}, {Q!r}, ['はい', 'いいえ'])\n"
            f"r2 = c.answer_question({F!r}, {Q!r}, ['はい', 'いいえ'], vocab_llm='off')\n"
            "print('verantyx.conduct_map' in sys.modules, 'verantyx.conduct_map' in sys.modules or 'mapping' in r)")
    assert _fresh(code) == "False False"


def test_the_fake_mode_without_a_map_script_never_imports_it_either():
    code = ("import sys, verantyx.conduct_ask as c\n"
            f"r = c.answer_question({F!r}, {Q!r}, ['はい', 'いいえ'], vocab_llm='fake')\n"
            "print('verantyx.conduct_map' in sys.modules, 'mapping' in r)")
    assert _fresh(code) == "False False"


def test_the_module_entry_runs_in_a_fresh_process_with_a_map_script(script):
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": str(H.ROOT), "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
           "HOME": os.environ.get("HOME", "/tmp")}
    proc = subprocess.run([sys.executable, "-m", "verantyx.conduct_ask", *base("--vocab-llm", "fake", "--map-fake", script)],
                          capture_output=True, text=True, env=env, cwd="/", timeout=120)
    assert proc.returncode == 0, proc.stderr
    res = json.loads(proc.stdout)
    assert proc.stdout.count("\n") == 1 and res["answer"] == "はい" and tuple(res)[-1] == "mapping"


def test_the_order_route_is_reachable_from_the_cli_with_a_map_script(tmp_path):
    """Review 1, must-fix 1: the new order route (phases step, derived statement, relations) is reached through the entry itself."""
    frame = str(Path(__file__).resolve().parent / "conduct_ask" / "w2g2" / "frames" / "x01_garden.md")
    p = tmp_path / "order.json"
    p.write_text(json.dumps({"records": ["order:ALL"], "decides": "決まる", "phases": ["P1", "P5"],
                             "relations": {"order:P1<P5": ["一致", "矛盾"]}}, ensure_ascii=False), encoding="utf-8")
    code, out, err = run_main(["--frame", frame, "--question", "お試し利用に進めるのは、区画のリストの用意が済んでからですか？",
                               "--option", "はい", "--option", "いいえ", "--vocab-llm", "fake", "--map-fake", str(p)])
    res = json.loads(out)
    assert code == 0 and err == "" and (res["decision"], res["answer"], res["resolver"]) == ("answer", "はい", ["mapping"])
    assert tuple(res)[-1] == "mapping" and res["mapping"]["order"]["picked"] == ["P1", "P5"]
    assert [b["id"] for b in res["basis"]] == [f"phase_order:P{i}->P{i + 1}" for i in range(1, 5)]
