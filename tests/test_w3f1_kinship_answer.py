"""W3-f1: 文書 QA（ask --mode round5 --document）が 2 字以上の人の名詞の主語・受け手・対象を全文字で答える。
検査データ tests/reading_soundness/w3f1_kinship.jsonl は凍結済み（artifacts/w3-f1/freeze.sha256）。
入口は既定の verantyx.cli.main。判定の式は docs/OBSERVATION.md の事前登録のとおり。"""
import contextlib
import hashlib
import io
import json
import unicodedata
from pathlib import Path

import pytest

from verantyx import cli

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "reading_soundness" / "w3f1_kinship.jsonl"
FREEZE = ROOT / "artifacts" / "w3-f1" / "freeze.sha256"
ROWS = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
NFKC = lambda s: unicodedata.normalize("NFKC", s)

CONTROL_T = {
    "agent": ("{X}が肥料を運んだ。", "誰が肥料を運んだ？"),
    "recipient": ("店員が{X}に本を渡した。", "店員は誰に本を渡した？"),
    "patient": ("医師が{X}を診察した。", "医師が誰を診察した？"),
}


def ask(tmp_path, document, question):
    doc = tmp_path / "d.txt"
    doc.write_text(document + "\n", encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.main(["--store", str(tmp_path / "st.json"), "ask", "--mode", "round5", "--document", str(doc), "--", question])
    return json.loads(buf.getvalue())


def test_data_is_frozen():
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == FREEZE.read_text().splitlines()[0].split()[0]
    assert len(ROWS) >= 60


@pytest.mark.parametrize("row", [r for r in ROWS if r["kind"] == "role"], ids=lambda r: r["id"])
def test_role_answer_is_the_whole_noun(row, tmp_path):
    out = ask(tmp_path, row["document"], row["question"])
    assert out.get("verdict") == "ANSWER", out.get("verdict")
    assert [NFKC(v) for v in out.get("values", [])] == [NFKC(v) for v in row["expect_values"]]


@pytest.mark.parametrize("row", [r for r in ROWS if r["kind"] == "polar"], ids=lambda r: r["id"])
def test_no_false_yes_between_different_nouns(row, tmp_path):
    out = ask(tmp_path, row["document"], row["question"])
    assert not (out.get("verdict") == "ANSWER" and "はい" in (out.get("text") or "")), (out.get("verdict"), out.get("text"))


@pytest.mark.parametrize("role", list(CONTROL_T))
def test_control_template_answers_with_a_plain_name(role, tmp_path):
    d, q = CONTROL_T[role]
    out = ask(tmp_path, d.format(X="田中"), q)
    assert out.get("verdict") == "ANSWER" and out.get("values") == ["田中"]
