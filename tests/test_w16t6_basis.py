"""W16-t6 round 2: which ledger events may back a "passed" claim, the 0-collected observation, and the evidence of count/exit facts."""
import hashlib
import json

from verantyx.attest import MISMATCH, RECORD, TESTIMONY, Verifier

PASS = "def test_a():\n    assert True\n"
FAIL = "def test_a():\n    assert False\n"


import itertools

from verantyx import ledger_events as LE

_N = itertools.count()


def ledger(tmp_path, runs):
    """A T7-layout ledger (<dir>/events.jsonl + HEAD) made by T7's own append; a fresh dir per call."""
    d = tmp_path / ("led%d" % next(_N))
    for argv, code in runs:
        LE.append(d, "test_run", {"type": "agent", "id": "x"}, {"argv": argv, "exit_code": code})
    return str(d / "events.jsonl")


def tree(tmp_path, files):
    (tmp_path / "tests").mkdir(exist_ok=True)
    for n, t in files.items():
        (tmp_path / "tests" / n).write_text(t)
    (tmp_path / "pytest.ini").write_text("")
    return str(tmp_path)


def passed(v, path, n=1):
    return {f["fact"]: f for f in v.tests_facts(path, n)}["test_passed:" + path]


def test_collect_only_event_is_not_a_basis_for_passed(tmp_path):
    t = tree(tmp_path, {"f.py": FAIL})
    led = ledger(tmp_path, [(["pytest", "--collect-only", "-q", "tests/f.py"], 0)])
    assert passed(Verifier(t, ledger=led), "tests/f.py")["reason"] == "NO_EVENT"


def test_node_only_and_k_only_events_are_not_a_basis(tmp_path):
    t = tree(tmp_path, {"m.py": PASS})
    for argv in (["pytest", "-q", "tests/m.py::test_a"], ["pytest", "-q", "-k", "test_a", "tests/m.py"], ["pytest", "-q", "-m", "x", "tests/m.py"],
                 ["pytest", "-q", "--lf", "tests/m.py"], ["pytest", "-q", "--deselect", "tests/m.py::test_a", "tests/m.py"], ["pytest", "--co", "tests/m.py"]):
        r = passed(Verifier(t, ledger=ledger(tmp_path, [(argv, 0)])), "tests/m.py")
        assert r["mark"] != RECORD and r["reason"] == "NO_EVENT", argv


def test_two_file_event_failing_cannot_be_pinned_on_one_file(tmp_path):
    t = tree(tmp_path, {"g.py": PASS, "h.py": FAIL})
    led = ledger(tmp_path, [(["pytest", "-q", "tests/g.py", "tests/h.py"], 1)])
    r = passed(Verifier(t, ledger=led), "tests/g.py")
    assert r["mark"] == TESTIMONY and r["reason"] == "NO_EVENT"


def test_two_file_event_passing_backs_each_file(tmp_path):
    t = tree(tmp_path, {"g.py": PASS, "h.py": PASS})
    led = ledger(tmp_path, [(["pytest", "-q", "-p", "no:cacheprovider", "tests/g.py", "tests/h.py"], 0)])
    for p in ("tests/g.py", "tests/h.py"):
        r = passed(Verifier(t, ledger=led), p)
        assert (r["mark"], r["reason"]) == (RECORD, "MATCH")
        assert r["evidence"]["path"] == led and r["evidence"]["event_sha"]


def test_single_file_event_failing_is_a_mismatch(tmp_path):
    t = tree(tmp_path, {"g.py": FAIL})
    led = ledger(tmp_path, [(["pytest", "-q", "tests/g.py"], 1)])
    r = passed(Verifier(t, ledger=led), "tests/g.py")
    assert (r["mark"], r["reason"], r["actual"]) == (MISMATCH, "EXIT_CODE_DIFFERS", 1)
    assert len(r["evidence"]["sha256"]) == 64


def test_unknown_flag_makes_event_unusable(tmp_path):
    t = tree(tmp_path, {"g.py": PASS})
    led = ledger(tmp_path, [(["pytest", "-q", "--pdb", "tests/g.py"], 0)])
    assert passed(Verifier(t, ledger=led), "tests/g.py")["reason"] == "NO_EVENT"


def test_zero_collected_is_an_observed_zero(tmp_path):
    t = tree(tmp_path, {"z.py": "x = 1\n"})
    f = {x["fact"]: x for x in Verifier(t).tests_facts("tests/z.py", 12)}["test_count:tests/z.py"]
    assert (f["mark"], f["reason"], f["claimed"], f["actual"]) == (MISMATCH, "COUNT_DIFFERS", 12, 0)
    f0 = {x["fact"]: x for x in Verifier(t).tests_facts("tests/z.py", 0)}["test_count:tests/z.py"]
    assert (f0["mark"], f0["reason"]) == (RECORD, "MATCH")


def test_collection_error_stays_testimony(tmp_path):
    t = tree(tmp_path, {"bad.py": "def test_a(:\n"})
    f = {x["fact"]: x for x in Verifier(t).tests_facts("tests/bad.py", 1)}["test_count:tests/bad.py"]
    assert (f["mark"], f["reason"]) == (TESTIMONY, "COLLECT_FAILED")


def test_count_mismatch_carries_test_file_path_and_sha(tmp_path):
    t = tree(tmp_path, {"a.py": PASS})
    f = {x["fact"]: x for x in Verifier(t).tests_facts("tests/a.py", 9)}["test_count:tests/a.py"]
    assert f["mark"] == MISMATCH
    assert f["evidence"]["path"] == "tests/a.py" and f["evidence"]["sha256"] == hashlib.sha256(PASS.encode()).hexdigest()


def test_exit_evidence_for_ledger_and_rerun(tmp_path, monkeypatch):
    from verantyx import attest
    t = tree(tmp_path, {"a.py": PASS})
    led = ledger(tmp_path, [(["pytest", "-q", "tests/a.py"], 0)])
    f = Verifier(t, ledger=led).exit_fact("pytest -q tests/a.py", 1)
    assert f["mark"] == MISMATCH and f["evidence"]["path"] == led and f["evidence"]["sha256"] and f["evidence"]["event_sha"]
    monkeypatch.setattr(attest, "_spawn", lambda *a, **k: (3, b"out", b""))
    f = Verifier(t, rerun=True).exit_fact("pytest -q tests/a.py", 0)
    assert f["mark"] == MISMATCH and "pytest" in f["evidence"]["argv"] and f["evidence"]["stdout_sha256"]


def _count_fact(t, rel, n):
    return {x["fact"]: x for x in Verifier(t).tests_facts(rel, n)}["test_count:" + rel]


SKIP_BODY_A = "import pytest\npytest.importorskip('no_such_module_xyz')\ndef test_a():\n    pass\ndef test_b():\n    pass\n"
SKIP_BODY_B = "import pytest\npytest.skip('env', allow_module_level=True)\ndef test_a():\n    pass\ndef test_b():\n    pass\n"


def test_module_importorskip_is_not_an_observed_zero(tmp_path):
    t = tree(tmp_path, {"k.py": SKIP_BODY_A})
    f = _count_fact(t, "tests/k.py", 2)
    assert f["mark"] == TESTIMONY and f["reason"] == "COLLECT_SKIPPED"


def test_module_level_skip_is_not_an_observed_zero(tmp_path):
    t = tree(tmp_path, {"k.py": SKIP_BODY_B})
    f = _count_fact(t, "tests/k.py", 2)
    assert f["mark"] == TESTIMONY and f["reason"] == "COLLECT_SKIPPED"


def test_true_zero_still_observed_after_skip_distinction(tmp_path):
    t = tree(tmp_path, {"z.py": "x = 1\n"})
    assert (_count_fact(t, "tests/z.py", 12)["reason"]) == "COUNT_DIFFERS"
    assert (_count_fact(t, "tests/z.py", 0)["reason"]) == "MATCH"
