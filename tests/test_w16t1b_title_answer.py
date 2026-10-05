"""W16-t1b K801: 文書 QA（ask --mode round5 --document）が、名前＋肩書きの充填物を表記のまま答える（森田課長 → 森田課長）。
検査データ tests/reading_soundness/w16t1b_title.jsonl は凍結済み（artifacts/w16-t1b/freeze.sha256）。
入口は既定の verantyx.cli.main。判定の式は docs/READING_SOUNDNESS.md §10M の事前登録のとおり。range の行は合否に入れない。"""
import contextlib
import hashlib
import io
import json
import unicodedata
from pathlib import Path

import pytest

from verantyx import cli

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "reading_soundness" / "w16t1b_title.jsonl"
FREEZE = ROOT / "artifacts" / "w16-t1b" / "freeze.sha256"
ROWS = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
NFKC = lambda s: unicodedata.normalize("NFKC", s)


def ask(tmp_path, document, question):
    doc = tmp_path / "d.txt"
    doc.write_text(document + "\n", encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.main(["--store", str(tmp_path / "st.json"), "ask", "--mode", "round5", "--document", str(doc), "--", question])
    return json.loads(buf.getvalue())


def test_data_is_frozen():
    lines = FREEZE.read_text().splitlines()
    want = {l.split()[1]: l.split()[0] for l in lines[:4]}
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == want["tests/reading_soundness/w16t1b_title.jsonl"]
    assert sum(r["kind"] == "title" for r in ROWS) >= 30
    assert sum(r["kind"] == "title_control" for r in ROWS) >= 9
    assert sum(r["kind"] == "title_mixed" for r in ROWS) >= 5


@pytest.mark.parametrize("row", [r for r in ROWS if r["kind"] == "title"], ids=lambda r: r["id"])
def test_title_answer_is_the_whole_written_form(row, tmp_path):
    out = ask(tmp_path, row["document"], row["question"])
    assert out.get("verdict") == "ANSWER", out.get("verdict")
    assert [NFKC(v) for v in out.get("values", [])] == [NFKC(v) for v in row["expect_values"]]


@pytest.mark.parametrize("row", [r for r in ROWS if r["kind"] == "title_control"], ids=lambda r: r["id"])
def test_control_answers_as_before(row, tmp_path):
    out = ask(tmp_path, row["document"], row["question"])
    assert out.get("verdict") == "ANSWER", out.get("verdict")
    assert [NFKC(v) for v in out.get("values", [])] == [NFKC(v) for v in row["expect_values"]]


@pytest.mark.parametrize("row", [r for r in ROWS if r["kind"] == "title_mixed"], ids=lambda r: r["id"])
def test_mixed_written_forms_do_not_answer_with_the_bare_name(row, tmp_path):
    out = ask(tmp_path, row["document"], row["question"])
    assert not (out.get("verdict") == "ANSWER" and [NFKC(v) for v in out.get("values", [])] == [NFKC(n) for n in row["name_only"]]), (out.get("verdict"), out.get("values"))
