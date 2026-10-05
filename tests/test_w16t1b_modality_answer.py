"""W16-t1b K800: 願望・可能・推量・様態・仮定・意志・伝聞の節を出来事として読まない（ask は ANSWER にならず、読解器は readable false）。
検査データ tests/reading_soundness/w16t1b_modality.jsonl は凍結済み（artifacts/w16-t1b/freeze.sha256）。
入口は既定の verantyx.cli.main と semantic_read.read（配置なし）。判定の式は docs/READING_SOUNDNESS.md §10M の事前登録のとおり。range の行は合否に入れない。"""
import contextlib
import hashlib
import io
import json
import unicodedata
from pathlib import Path

import pytest

from verantyx import cli, semantic_read

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests" / "reading_soundness" / "w16t1b_modality.jsonl"
FREEZE = ROOT / "artifacts" / "w16-t1b" / "freeze_r2.sha256"  # 第 2 ラウンド K819: gate の 4 行の訂正で凍結を作り直した（freeze.sha256 は第 1 ラウンドの記録）
ROWS = [json.loads(l) for l in DATA.read_text(encoding="utf-8").splitlines() if l.strip()]
NFKC = lambda s: unicodedata.normalize("NFKC", s)
MODAL = [r for r in ROWS if r["kind"] == "modal"]
KINDS = ["desire", "potential", "conjecture", "appearance", "conditional", "volition", "hearsay"]


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
    assert hashlib.sha256(DATA.read_bytes()).hexdigest() == want["tests/reading_soundness/w16t1b_modality.jsonl"]
    for k in KINDS:
        assert sum(r["modality"] == k for r in MODAL) >= 10, k
        assert sum(r["kind"] == "modal_control" and r["modality"] == k for r in ROWS) >= 3, k


@pytest.mark.parametrize("row", MODAL, ids=lambda r: r["id"])
def test_modal_clause_is_not_answered(row, tmp_path):
    for q in row["questions"]:
        out = ask(tmp_path, row["document"], q)
        assert out.get("verdict") != "ANSWER", (q, out.get("verdict"), out.get("values"))


@pytest.mark.parametrize("row", MODAL, ids=lambda r: r["id"])
def test_modal_clause_is_not_read_as_an_event(row):
    assert semantic_read.read(row["document"], placement=None)["readable"] is False


@pytest.mark.parametrize("row", [r for r in MODAL if r["gate"]], ids=lambda r: r["id"])
def test_gated_form_abstains_with_the_modality_type(row, tmp_path):
    want = "MODALITY_NOT_READ:" + row["modality"]
    assert want in unsupported_reasons(semantic_read.read(row["document"], placement=None))
    out = ask(tmp_path, row["document"], row["questions"][0])
    assert want in json.dumps(out, ensure_ascii=False)


@pytest.mark.parametrize("row", [r for r in ROWS if r["kind"] == "modal_control"], ids=lambda r: r["id"])
def test_control_without_the_modal_answers_as_before(row, tmp_path):
    for spec in row["questions"]:
        out = ask(tmp_path, row["document"], spec["q"])
        assert out.get("verdict") == "ANSWER", (spec["q"], out.get("verdict"))
        assert [NFKC(v) for v in out.get("values", [])] == [NFKC(v) for v in spec["expect_values"]]
