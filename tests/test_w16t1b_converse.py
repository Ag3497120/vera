"""W16-t1b 第 2 ラウンド（K817〜K819）: 転換の枠（借りる→貸す＋recipient）の主語でも、願望・可能・並列の作用域の門が届く。
検査データ tests/reading_soundness/w16t1b_converse.jsonl は凍結済み（artifacts/w16-t1b/freeze_r2.sha256）。判定の式は docs/READING_SOUNDNESS.md §10M の
第 2 ラウンドの事前登録のとおり。range の行は合否に入れない。"""
import contextlib
import hashlib
import io
import json
import unicodedata
from pathlib import Path

import pytest

from verantyx import cli, semantic_read

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "reading_soundness" / "w16t1b_converse.jsonl"
FREEZE = ROOT / "artifacts" / "w16-t1b" / "freeze_r2.sha256"
ROWS = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
NFKC = lambda s: unicodedata.normalize("NFKC", s)
MODAL = [r for r in ROWS if r["kind"] == "converse_modal"]
CONTROLS = [r for r in ROWS if r["kind"] in ("passive_control", "ichidan_control", "title_control")]


def ask(tmp_path, document, question):
    doc = tmp_path / "d.txt"
    doc.write_text(document + "\n", encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.main(["--store", str(tmp_path / "st.json"), "ask", "--mode", "round5", "--document", str(doc), "--", question])
    return json.loads(buf.getvalue())


def unsupported_reasons(read):
    out = []
    for u in read.get("unsupported") or []:
        out.extend(u.get("reasons") or [])
    return out


def test_data_is_frozen():
    want = {l.split()[1]: l.split()[0] for l in FREEZE.read_text().splitlines() if len(l.split()) == 2 and len(l.split()[0]) == 64}
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == want["tests/reading_soundness/w16t1b_converse.jsonl"]
    assert len(MODAL) >= 10
    assert sum(r["kind"] == "passive_control" for r in ROWS) >= 5
    assert sum(r["kind"] == "ichidan_control" for r in ROWS) >= 5
    assert sum(r["kind"] == "title_control" for r in ROWS) >= 2


@pytest.mark.parametrize("row", MODAL, ids=lambda r: r["id"])
def test_converse_modal_clause_is_not_answered(row, tmp_path):
    for q in row["questions"]:
        out = ask(tmp_path, row["document"], q)
        assert out.get("verdict") != "ANSWER", (q, out.get("verdict"), out.get("values"))


@pytest.mark.parametrize("row", MODAL, ids=lambda r: r["id"])
def test_converse_modal_clause_is_not_read_as_an_event(row):
    assert semantic_read.read(row["document"], placement=None)["readable"] is False


@pytest.mark.parametrize("row", [r for r in MODAL if r["gate"]], ids=lambda r: r["id"])
def test_converse_gated_form_abstains_with_the_modality_type(row, tmp_path):
    want = "MODALITY_NOT_READ:" + row["modality"]
    assert want in unsupported_reasons(semantic_read.read(row["document"], placement=None))
    out = ask(tmp_path, row["document"], row["questions"][0])
    assert want in json.dumps(out, ensure_ascii=False)


@pytest.mark.parametrize("row", CONTROLS, ids=lambda r: r["id"])
def test_control_answers_as_before(row, tmp_path):
    for spec in row["questions"]:
        out = ask(tmp_path, row["document"], spec["q"])
        assert out.get("verdict") == "ANSWER", (spec["q"], out.get("verdict"))
        assert [NFKC(v) for v in out.get("values", [])] == [NFKC(v) for v in spec["expect_values"]]
