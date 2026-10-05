"""W16-t6: the verifier (docs/ATTEST.md section 3): five kinds of false claim, true claims, out-of-tree, ambiguity, folding."""
import hashlib
import os

from verantyx import attest
from verantyx.attest import MISMATCH, RECORD, TESTIMONY, Verifier

T = "def test_a():\n    assert True\n\ndef test_b():\n    assert True\n"


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()


def mk(tmp_path, files):
    for p, c in files.items():
        f = tmp_path / p
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(c)
    (tmp_path / "pytest.ini").write_text("")
    return str(tmp_path)


def test_sha_true_false_prefix_and_short(tmp_path):
    v = Verifier(mk(tmp_path, {"o/x.txt": "hello\n"}))
    real = sha("hello\n")
    f = v.file_sha("o/x.txt", real)
    assert (f["mark"], f["reason"]) == (RECORD, "MATCH")
    f = v.file_sha("o/x.txt", "0" * 64)
    assert (f["mark"], f["reason"]) == (MISMATCH, "SHA_DIFFERS") and f["claimed"] == "0" * 64 and f["actual"] == real and f["evidence"]["sha256"] == real
    assert v.file_sha("o/x.txt", real[:14] + "...")["reason"] == "MATCH_PREFIX"
    assert v.file_sha("o/x.txt", real[:11])["reason"] == "SHA_TOO_SHORT"
    assert v.file_sha("o/x.txt", "1a2b...")["mark"] == TESTIMONY


def test_missing_is_a_mismatch_but_outside_is_testimony(tmp_path):
    v = Verifier(mk(tmp_path, {"a.txt": "x"}))
    assert (v.file_sha("nope.txt", "0" * 64)["mark"], v.file_sha("nope.txt", "0" * 64)["reason"]) == (MISMATCH, "FILE_MISSING")
    for p in ("/etc/hosts", "../x.txt"):
        f = v.file_sha(p, "0" * 64)
        assert (f["mark"], f["reason"]) == (TESTIMONY, "PATH_OUTSIDE_TREE")
    # partial tree: a missing file is unknown
    assert Verifier(str(tmp_path), partial=True).file_sha("nope.txt", "0" * 64)["reason"] == "EVIDENCE_NOT_IN_TREE"


def test_symlink_escape_is_outside(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("s")
    tree = tmp_path / "tree"
    tree.mkdir()
    os.symlink(str(outside / "secret.txt"), str(tree / "link.txt"))
    f = Verifier(str(tree)).file_sha("link.txt", "0" * 64)
    assert (f["mark"], f["reason"]) == (TESTIMONY, "PATH_OUTSIDE_TREE")


def test_same_name_in_two_search_dirs_is_ambiguous_not_chosen(tmp_path):
    t = mk(tmp_path, {"artifacts/d1/o.txt": "1", "artifacts/d2/o.txt": "2"})
    f = Verifier(t, search_dirs=["artifacts/d1", "artifacts/d2"], partial=True).file_sha("o.txt", sha("1"))
    assert (f["mark"], f["reason"]) == (TESTIMONY, "AMBIGUOUS_PATH")
    f = Verifier(t, search_dirs=["artifacts/d1"], partial=True).file_sha("o.txt", sha("1"))
    assert f["mark"] == RECORD


def test_number_word_boundary_and_decimals(tmp_path):
    v = Verifier(mk(tmp_path, {"o.txt": "total 120 rows, 精度 0.95, 1,234 件\n", "p.txt": "12 passed\n"}))
    assert v.number_fact("12 件", "o.txt")["reason"] == "NUMBER_NOT_IN_OUTPUT"
    assert v.number_fact("0 件", "o.txt")["reason"] == "NUMBER_NOT_IN_OUTPUT"
    assert v.number_fact("95 件", "o.txt")["reason"] == "NUMBER_NOT_IN_OUTPUT"
    assert v.number_fact("120 行", "o.txt")["mark"] == RECORD
    assert v.number_fact("１２３４ 件", "o.txt")["mark"] == RECORD           # fullwidth, and 1,234 in the file
    assert v.number_fact("T2-1 の 12 passed", "p.txt")["mark"] == RECORD      # the 2 and 1 of the id are not numbers
    assert attest.numbers_in("T2-1 の python3.11 で 7 件") == ["7"]
    assert v.number_fact("数字が無い", "p.txt")["reason"] == "NO_NUMBER_IN_TEXT"


def test_tests_exist_count_and_not_found(tmp_path):
    t = mk(tmp_path, {"tests/test_a.py": T, "tests/test_b.py": "def test_x():\n    assert False\n"})
    v = Verifier(t)
    facts = {f["fact"]: f for f in v.tests_facts("tests/test_a.py", 2)}
    assert facts["test_exists:tests/test_a.py"]["mark"] == RECORD and facts["test_count:tests/test_a.py"]["mark"] == RECORD
    assert facts["test_passed:tests/test_a.py"]["reason"] == "NO_EVENT"          # no ledger, no --rerun: never a RECORD
    f = {f["fact"]: f for f in v.tests_facts("tests/test_a.py", 9)}["test_count:tests/test_a.py"]
    assert (f["mark"], f["reason"], f["claimed"], f["actual"]) == (MISMATCH, "COUNT_DIFFERS", 9, 2)
    g = v.tests_facts("tests/test_ghost.py", 1)
    assert [(x["mark"], x["reason"]) for x in g] == [(MISMATCH, "TEST_NOT_FOUND")]
    assert v.tests_facts("../x/test_y.py", 1)[0]["reason"] == "PATH_OUTSIDE_TREE"
    t2 = tmp_path / "pkg"
    t2.mkdir()
    (t2 / "test_z.py").write_text(T)
    assert v.tests_facts("pkg/test_z.py", 2)[0]["reason"] == "NOT_IN_TESTS_DIR"


def test_exit_code_without_a_source_is_testimony(tmp_path):
    v = Verifier(mk(tmp_path, {"tests/test_a.py": T}))
    f = v.exit_fact("pytest -q tests/test_a.py", 0)
    assert (f["mark"], f["reason"]) == (TESTIMONY, "NO_EVENT")
    f = Verifier(str(tmp_path), rerun=True).exit_fact("pytest -q tests/test_a.py", 1)
    assert (f["mark"], f["reason"], f["claimed"], f["actual"]) == (MISMATCH, "EXIT_CODE_DIFFERS", 1, 0)
    assert Verifier(str(tmp_path), rerun=True).exit_fact("pytest -q tests/test_a.py", 0)["mark"] == RECORD


def test_folding_narrows():
    assert attest.fold_marks([RECORD, RECORD]) == RECORD
    assert attest.fold_marks([RECORD, TESTIMONY]) == TESTIMONY
    assert attest.fold_marks([RECORD, TESTIMONY, MISMATCH]) == MISMATCH
    assert attest.fold_marks([]) == TESTIMONY


def test_too_large_number_file_is_testimony(tmp_path, monkeypatch):
    t = mk(tmp_path, {"o.txt": "12\n"})
    monkeypatch.setattr(attest, "NUMBER_FILE_LIMIT", 1)
    assert Verifier(t).number_fact("12 件", "o.txt")["reason"] == "TOO_LARGE"


def test_changed_needs_a_base(tmp_path):
    f = Verifier(mk(tmp_path, {"p.py": "x"})).changed("p.py")
    assert (f["mark"], f["reason"]) == (TESTIMONY, "NO_BASE")
