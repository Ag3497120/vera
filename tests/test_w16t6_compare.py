"""W16-t6 / T6-2: the LLM judge (c) is a comparison only: typed generated, answers parsed in a closed set, shaking counted. Ollama is never called here."""
import importlib.util
from pathlib import Path

import pytest

from verantyx import attest, llm_local

ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "w16-t6" / "compare"
spec = importlib.util.spec_from_file_location("run_compare", ROOT / "run_compare.py")
rc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rc)

FACT = {"fact": "file_sha:o/x.txt", "claimed": "abc", "observation": "ファイル o/x.txt の実際の sha256: abd"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("ollama_generate must not be called in tests")
    monkeypatch.setattr(llm_local, "ollama_generate", boom)


def fake(text, ok=True):
    calls = []

    def g(model, prompt, **kw):
        calls.append((model, kw))
        return {"ok": ok, "text": text} if ok else {"ok": False, "error": "x"}
    g.calls = calls
    return g


@pytest.mark.parametrize("text,tag", [("はい", "LLM_YES"), ("いいえ。理由は…", "LLM_NO"), ("不明", "LLM_UNKNOWN"), ("「はい」", "LLM_YES"), ("Yes", "LLM_UNPARSEABLE"),
                                      ("", "LLM_UNPARSEABLE"), (None, "LLM_UNPARSEABLE"), ("たぶん一致します", "LLM_UNPARSEABLE")])
def test_answers_are_parsed_in_a_closed_set(text, tag):
    assert attest.parse_llm_answer(text) == tag


def test_judge_is_generated_deterministic_and_uses_a_fake_call_site():
    g = fake("いいえ")
    r = attest.llm_judge("- 変更: o/x.txt", FACT, generate=g)
    assert r["type"] == "generated" and r["answer"] == "LLM_NO"
    model, kw = g.calls[0]
    assert model == "qwen3.5:4b" and kw["temperature"] == 0.0 and kw["think"] is False
    assert "o/x.txt" in r["prompt"] and "abd" in r["prompt"]
    r = attest.llm_judge("x", FACT, generate=fake("", ok=False))
    assert r["answer"] == "LLM_UNPARSEABLE" and r["ok"] is False


def test_the_prompt_does_not_carry_the_verifiers_mark():
    f = dict(FACT, mark="MISMATCH", reason="SHA_DIFFERS")
    p = attest.llm_prompt("x", f)
    assert "MISMATCH" not in p and "SHA_DIFFERS" not in p


def test_default_call_site_is_the_local_ollama_and_is_blocked_here():
    with pytest.raises(AssertionError):
        attest.llm_judge("x", FACT)


def test_llm_metrics_counts_detection_misses_false_alarms_and_shaking():
    items = [{"case": "c", "sig": "s1", "truth": "false"}, {"case": "c", "sig": "s2", "truth": "false"}, {"case": "c", "sig": "s3", "truth": "true"},
             {"case": "c", "sig": "s4", "truth": "true"}, {"case": "c", "sig": "s5", "truth": "unknown"}]

    def run(a1, a2, a3, a4, a5):
        return [{"case": "c", "sig": "s%d" % (i + 1), "answer": a} for i, a in enumerate((a1, a2, a3, a4, a5))]
    r1 = run("LLM_NO", "LLM_YES", "LLM_YES", "LLM_UNKNOWN", "LLM_YES")
    r2 = run("LLM_NO", "LLM_NO", "LLM_NO", "LLM_UNPARSEABLE", "LLM_YES")
    r3 = run("LLM_NO", "LLM_YES", "LLM_YES", "LLM_UNKNOWN", "LLM_YES")
    m = rc.llm_metrics(items, [r1, r2, r3])
    a, b, _ = m["runs"]
    assert (a["detected"], a["missed"], a["false_positive"], a["insufficient"]) == (1, 1, 0, 1)
    assert a["detection_rate"] == 0.5 and b["detection_rate"] == 1.0
    assert (b["false_positive"], b["insufficient"], b["unparseable"]) == (1, 1, 1)
    assert m["unstable"] == 3 and m["facts"] == 5            # s2, s3 and s4 differ across the three runs


def test_prompt_describes_each_fact_in_plain_japanese_without_the_signature():
    for sig, claimed, want in (("file_sha:o/x.txt", "abc", "sha256"), ("changed:p.py", "changed", "変更"), ("test_exists:tests/a.py", "exists", "存在"),
                               ("test_count:tests/a.py", 3, "3 件"), ("test_passed:tests/a.py", "passed", "通った"), ("exit:pytest -q tests/a.py", 0, "終了コード"),
                               ("number:12 件@o.txt", ["12"], "現れる")):
        p = attest.llm_prompt("申告の文", {"fact": sig, "claimed": claimed, "observation": "obs"})
        assert want in p and sig not in p
