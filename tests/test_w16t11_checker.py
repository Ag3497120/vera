"""W16-t11: tools/readme_numbers_check.py の単体テスト（README は使わない。入力は tmp_path に作る）。"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import readme_numbers_check as C  # noqa: E402

GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid"]

SOURCE = "# 結果\n\n試験 A: 正答 7/9、誤答 0（集合 X の 9 件）。\n"


def _repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(r)], check=True)
    (r / "src.md").write_text(SOURCE, encoding="utf-8")
    subprocess.run(GIT + ["-C", str(r), "add", "src.md"], check=True)
    subprocess.run(GIT + ["-C", str(r), "commit", "-q", "-m", "s"], check=True)
    sha = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    return r, sha


def _spec(tmp_path, sha, **over):
    row = {
        "id": "N-01", "label_ja": "正答", "label_en": "correct", "value": "7", "denominator": "9",
        "set": "集合 X", "source": "src.md", "commit": sha,
        "extract": {"kind": "regex", "pattern": r"正答 (\d+)/(\d+)", "groups": {"value": 1, "denominator": 2}},
        "kind": "measured", "provenance": "measurement-only", "aux": [],
    }
    row.update(over)
    row2 = dict(row, id="N-02", value="0", denominator="9",
                extract={"kind": "regex", "pattern": r"正答 (\d+)/(\d+)、誤答 (\d+)", "groups": {"value": 3, "denominator": 2}})
    p = tmp_path / "spec.json"
    p.write_text(json.dumps([row, row2], ensure_ascii=False), encoding="utf-8")
    return p


GOOD_README = """---
title: x
---
# T

Intro without numbers.

## Results
| id | item | value | denominator | set | source |
|---|---|---|---|---|---|
| N-01 | correct | 7 | 9 | set X | `src.md` |
| N-02 | wrong answers | 0 | 9 | set X | `src.md` |

## 日本語
| id | 項目 | 値 | 分母 | 集合 | 出所 |
|---|---|---|---|---|---|
| N-01 | 正答 | 7 | 9 | 集合 X | `src.md` |
| N-02 | 誤答 | 0 | 9 | 集合 X | `src.md` |
"""


def _run(*args):
    return C.main([str(a) for a in args])


def _numbers(tmp_path, readme, **over):
    r, sha = _repo(tmp_path)
    spec = _spec(tmp_path, sha, **over)
    (r / "README.md").write_text(readme, encoding="utf-8")
    return _run("numbers", "--repo", r, "--spec", spec, "--readme", "README.md")


def test_good_readme_passes(tmp_path):
    assert _numbers(tmp_path, GOOD_README) == 0


def test_changed_value_in_readme_fails(tmp_path):
    bad = GOOD_README.replace("| N-01 | correct | 7 |", "| N-01 | correct | 8 |")
    assert _numbers(tmp_path, bad) == 1


def test_unmarked_number_in_prose_fails(tmp_path):
    bad = GOOD_README.replace("Intro without numbers.", "It got 12 right.")
    assert _numbers(tmp_path, bad) == 1


def test_marked_prose_number_must_match_spec(tmp_path):
    ok = GOOD_README.replace("Intro without numbers.", "Seven of 9 were right [N-01]. See `v0.9-preview` and 2026-10-06 and W16-t6.")
    assert _numbers(tmp_path, ok) == 0
    bad = GOOD_README.replace("Intro without numbers.", "Seven of 8 were right [N-01].")
    assert _numbers(tmp_path / "b", bad) == 1


def test_missing_row_in_one_language_table_fails(tmp_path):
    bad = GOOD_README.replace("| N-02 | 誤答 | 0 | 9 | 集合 X | `src.md` |\n", "")
    assert _numbers(tmp_path, bad) == 1


def test_spec_value_that_disagrees_with_the_source_fails(tmp_path):
    assert _numbers(tmp_path, GOOD_README, value="8") == 1


def test_source_is_read_from_the_commit_not_the_working_tree(tmp_path):
    r, sha = _repo(tmp_path)
    spec = _spec(tmp_path, sha)
    (r / "src.md").write_text("正答 8/9、誤答 1\n", encoding="utf-8")  # 作業ツリーだけ書き換える
    (r / "README.md").write_text(GOOD_README, encoding="utf-8")
    assert _run("numbers", "--repo", r, "--spec", spec, "--readme", "README.md") == 0


def test_unknown_commit_is_exit_2_not_a_mismatch(tmp_path, capsys):
    r, _ = _repo(tmp_path)
    spec = _spec(tmp_path, "0" * 40)
    (r / "README.md").write_text(GOOD_README, encoding="utf-8")
    rc = _run("numbers", "--repo", r, "--spec", spec, "--spec-only")
    assert rc == 2
    assert "SOURCE_UNREADABLE" in capsys.readouterr().out


def test_regex_matching_twice_fails(tmp_path):
    r, sha = _repo(tmp_path)
    (r / "src.md").write_text(SOURCE + "試験 B: 正答 7/9\n", encoding="utf-8")
    subprocess.run(GIT + ["-C", str(r), "commit", "-qam", "again"], check=True)
    sha2 = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    spec = _spec(tmp_path, sha2)
    assert _run("numbers", "--repo", r, "--spec", spec, "--spec-only") == 1


def _claims(tmp_path, text):
    r, sha = _repo(tmp_path)
    spec = _spec(tmp_path, sha)
    (r / "d.md").write_text(text, encoding="utf-8")
    return _run("claims", "--repo", r, "--spec", spec, "--files", "d.md")


def test_bare_claim_fails(tmp_path):
    assert _claims(tmp_path, "この版は誤答 0。\n") == 1


def test_claim_with_marked_denominator_passes(tmp_path):
    assert _claims(tmp_path, "集合 X の 9 件で誤答 0 [N-02]。\n") == 0


def test_claim_pointing_at_unknown_id_fails(tmp_path):
    assert _claims(tmp_path, "誤答 0 [N-99]。\n") == 1


def test_english_claim_words(tmp_path):
    assert _claims(tmp_path, "It has 0 wrong answers.\n") == 1
    assert _claims(tmp_path / "x", "Always 100% right.\n") == 1
    assert _claims(tmp_path / "y", "Right 100.0% of the time.\n") == 1


def _prepublish(tmp_path, text):
    r, _ = _repo(tmp_path)
    (r / "p.md").write_text(text, encoding="utf-8")
    return _run("prepublish", "--repo", r, "--files", "p.md")


def test_prepublish_flags_absolute_paths_and_secrets(tmp_path):
    assert _prepublish(tmp_path, "see /Users/x/y\n") == 1
    assert _prepublish(tmp_path / "a", "see /home/u\n") == 1
    assert _prepublish(tmp_path / "b", "see wt/hidden/ bank\n") == 1
    assert _prepublish(tmp_path / "c", "key sk-" + "A" * 24 + "\n") == 1


def test_prepublish_clean_text_passes(tmp_path):
    assert _prepublish(tmp_path, "Nothing private here.\n") == 0


def test_prepublish_reads_the_user_name_at_run_time(tmp_path, monkeypatch):
    monkeypatch.setenv("USER", "zzqqname")
    assert _prepublish(tmp_path, "written by zzqqname\n") == 1


def test_the_checker_source_does_not_hard_code_the_local_user_names():
    src = (ROOT / "tools" / "readme_numbers_check.py").read_text(encoding="utf-8")
    assert "motonisihikoudai" not in src and "Ag3497" not in src
    assert "import verantyx" not in src and "from verantyx" not in src


def test_claim_words_are_frozen():
    for name, sha in (("claim_words.json", "claim_words.sha256"), ("claim_words.r1.json", "claim_words.r1.sha256")):
        words = ROOT / "artifacts" / "w16-t11" / name
        want = (ROOT / "artifacts" / "w16-t11" / sha).read_text().split()[0]
        assert hashlib.sha256(words.read_bytes()).hexdigest() == want


def test_r1_version_exclusion_does_not_hide_decimals_and_percentages():
    assert C.numeric_tokens("Right 57.8% of the time.") == ["57.8%"]
    assert C.numeric_tokens("Right 100.0% of the time.") == ["100.0%"]
    assert C.numeric_tokens("Release v0.9-preview, wheel 0.1.0a1, see §9.8, 0.9-preview, v1.2.") == []


def test_unmarked_decimal_percentage_in_prose_fails(tmp_path):
    assert _numbers(tmp_path, GOOD_README + "\nVera is right 100.0% of the time.\n") == 1
    assert _numbers(tmp_path / "z", GOOD_README + "\nVera is right 57.8% of the time.\n") == 1
