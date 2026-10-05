"""W3-f1 拡張: 場所・着点の値に時の語が連結していたら（明日東京）その値で答えない。
検査データ tests/reading_soundness/w3f1_time_place.jsonl は凍結済み（artifacts/w3-f1/freeze_ext.sha256）。
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
DATA = ROOT / "tests" / "reading_soundness" / "w3f1_time_place.jsonl"
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
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == sha["tests/reading_soundness/w3f1_time_place.jsonl"]
    assert sum(r["kind"] == "fused" for r in ROWS) >= 30
    assert sum(r["kind"] == "control" for r in ROWS) >= 8


@pytest.mark.parametrize("row", [r for r in ROWS if r["kind"] == "fused"], ids=lambda r: r["id"])
def test_time_word_is_not_fused_into_the_place(row, tmp_path):
    out = ask(tmp_path, row["document"], row["question"])
    vals = [NFKC(v) for v in out.get("values", [])]
    assert not (out.get("verdict") == "ANSWER" and any(NFKC(row["time_word"]) in v for v in vals)), (out.get("verdict"), vals)
    if out.get("verdict") == "ANSWER":
        assert vals == [NFKC(row["place"])]


@pytest.mark.parametrize("row", [r for r in ROWS if r["kind"] == "control"], ids=lambda r: r["id"])
def test_plain_place_still_answers(row, tmp_path):
    out = ask(tmp_path, row["document"], row["question"])
    assert out.get("verdict") == "ANSWER", out.get("verdict")
    assert [NFKC(v) for v in out.get("values", [])] == [NFKC(v) for v in row["expect_values"]]
