"""W3-f1 拡張: 禁止の形（てはならない／てはいけない／ではならない 等）から偽の節で「はい」を答えない。
検査データ tests/reading_soundness/w3f1_prohibition.jsonl は凍結済み（artifacts/w3-f1/freeze_ext.sha256）。
入口は既定の verantyx.cli.main。判定の式は docs/OBSERVATION.md の拡張の事前登録のとおり。"""
import contextlib
import hashlib
import io
import json
import unicodedata
from pathlib import Path

import pytest

from verantyx import cli

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "reading_soundness" / "w3f1_prohibition.jsonl"
FREEZE = ROOT / "artifacts" / "w3-f1" / "freeze_ext.sha256"
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
    sha = {l.split()[1]: l.split()[0] for l in FREEZE.read_text().splitlines() if len(l.split()) == 2 and len(l.split()[0]) == 64}
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == sha["tests/reading_soundness/w3f1_prohibition.jsonl"]
    assert sum(r["kind"] == "aux_polar" for r in ROWS) >= 30
    assert sum(r["kind"] == "main_polar" for r in ROWS) >= 10
    assert sum(r["kind"] == "control" for r in ROWS) >= 6


@pytest.mark.parametrize("row", [r for r in ROWS if r["kind"] in ("aux_polar", "main_polar")], ids=lambda r: r["id"])
def test_prohibition_is_not_answered_as_a_polar_fact(row, tmp_path):
    out = ask(tmp_path, row["document"], row["question"])
    assert out.get("verdict") != "ANSWER", (out.get("verdict"), out.get("text"))


@pytest.mark.parametrize("row", [r for r in ROWS if r["kind"] == "control"], ids=lambda r: r["id"])
def test_plain_negation_still_answers(row, tmp_path):
    out = ask(tmp_path, row["document"], row["question"])
    assert out.get("verdict") == "ANSWER", out.get("verdict")
    assert [NFKC(v) for v in out.get("values", [])] == [NFKC(v) for v in row["expect_values"]]
