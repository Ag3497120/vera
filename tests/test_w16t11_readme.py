"""W16-t11: public_overlay/README.md に対する R-1〜R-5（検査器を subprocess で呼ぶ）と、実例の byte 一致。"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "tools" / "readme_numbers_check.py"
README = ROOT / "public_overlay" / "README.md"
OUT = ROOT / "artifacts" / "w16-t11" / "examples" / "out"
VENV_PY = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
PUBLIC_FILES = [
    "public_overlay/README.md",
    "public_overlay/KNOWN_ISSUES.md",
    "public_overlay/EVAL.md",
    "public_overlay/docs/README_LEGACY_d25a73a.md",
    "CHANGELOG.md",
]
HOOK_PREFIX_LINES = 18


def _check(*args):
    r = subprocess.run([sys.executable, str(CHECK), *args, "--repo", str(ROOT)], capture_output=True, text=True)
    return r.returncode, r.stdout


def test_r1_numbers_recompute_from_the_sources_and_match_the_readme():
    rc, out = _check("numbers")
    assert rc == 0, out


def test_r2_no_claim_word_without_a_denominator_and_a_set():
    rc, out = _check("claims", "--files", *PUBLIC_FILES)
    assert rc == 0, out


def test_r4_prepublish_scan_is_empty():
    rc, out = _check("prepublish", "--files", *PUBLIC_FILES)
    assert rc == 0, out


def test_r5_product_code_is_unchanged():
    out = subprocess.run(["git", "-C", str(ROOT), "diff", "--stat", "4c2a2e5", "--", "verantyx/", "public_overlay/vera_base/", "public_overlay/pyproject.toml"],
                         capture_output=True, text=True, check=True).stdout
    assert out.strip() == ""


def _blocks():
    text = README.read_text(encoding="utf-8")
    found = re.findall(r"<!-- EXAMPLE (\w+) -->\n```text\n(.*?)```", text, re.S)
    return found


def _expected(name):
    cmd = (OUT / (name + ".cmd")).read_text(encoding="utf-8")
    stdout = (OUT / (name + ".stdout")).read_text(encoding="utf-8")
    code = (OUT / (name + ".exit")).read_text(encoding="utf-8").strip()
    if name == "b_hooks":
        return "$ " + cmd + "".join(stdout.splitlines(True)[:HOOK_PREFIX_LINES])
    return "$ " + cmd + stdout + "# exit code: %s\n" % code


def test_examples_in_both_languages_are_byte_equal_to_the_frozen_output():
    blocks = _blocks()
    names = [n for n, _ in blocks]
    assert sorted(set(names)) == ["a_attest", "b_hooks", "b_run", "b_verify", "b_verify_tampered"]
    assert all(names.count(n) == 2 for n in set(names)), "英語と日本語の節に 1 つずつ"
    for name, body in blocks:
        assert body == _expected(name), name


def test_examples_hook_block_is_a_prefix_of_the_full_output():
    full = (OUT / "b_hooks.stdout").read_text(encoding="utf-8")
    shown = _expected("b_hooks").split("\n", 1)[1]
    assert full.startswith(shown) and len(shown) < len(full)


def test_examples_cover_record_testimony_and_mismatch():
    out = (OUT / "a_attest.stdout").read_text(encoding="utf-8")
    assert "記録 MATCH" in out and "証言 NO_BASE" in out and "食い違い COUNT_DIFFERS" in out
    assert (OUT / "a_attest.exit").read_text().strip() == "1"
    assert (OUT / "b_verify.exit").read_text().strip() == "0"
    assert "TAMPERED" in (OUT / "b_verify_tampered.stdout").read_text(encoding="utf-8")


def test_examples_replay_normalizes_to_the_frozen_output():
    if not Path(VENV_PY).exists():
        pytest.skip("検証用の python が無い")
    with tempfile.TemporaryDirectory() as td:
        dest = Path(td) / "ex"
        r = subprocess.run(["bash", str(ROOT / "artifacts/w16-t11/examples/replay.sh"), str(dest)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        norm = Path(td) / "norm"
        subprocess.run([sys.executable, str(ROOT / "artifacts/w16-t11/examples/normalize.py"), str(dest), str(norm)], check=True)
        for f in sorted(OUT.iterdir()):
            assert (norm / f.name).read_bytes() == f.read_bytes(), f.name


def test_examples_serve_frame_is_present_once_and_no_output_is_invented():
    text = README.read_text(encoding="utf-8")
    assert text.count("<!-- AUDITOR_RUNS: serve-layer0 -->") == 1
    assert "quote_check" in text
    assert not (ROOT / "artifacts/w16-t11/examples/out/c_serve.stdout").exists()


def test_the_adopted_positioning_sentence_and_the_three_non_goals_are_present():
    text = README.read_text(encoding="utf-8")
    assert "日本語で行われる AI エージェントの仕事の、信頼できる記録と判定" in text
    assert "a trustworthy record and verdict for the work AI agents do in Japanese" in text
    for s in ("does **not** read Japanese better than an LLM", "does **not** answer or write on its own", "does **not** do general Japanese reading comprehension",
              "LLM より上手に日本語を読むことは **しません**", "自分で答えたり書いたりは **しません**", "一般の日本語の読解は **しません**"):
        assert s in text, s


def test_the_readme_never_marks_anchored_as_checked():
    text = README.read_text(encoding="utf-8")
    assert "`anchored` is a mark, not a confirmation" in text
    assert "`anchored` は印であって" in text
    assert "anchored_testimony" in text


def test_no_test_files_in_artifacts():
    bad = [p for p in (ROOT / "artifacts" / "w16-t11").rglob("*") if p.name.startswith("test_") or p.name.endswith("_test.py") or p.name == "conftest.py"]
    assert bad == []
