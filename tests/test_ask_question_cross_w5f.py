"""W5-f F-5: document QA sources point into the loader's Markdown body."""
import contextlib
import io
import json
from pathlib import Path

import pytest

from verantyx import cli
from verantyx import document_loaders as DL
from verantyx import event_cross as EC


TREE = Path(__file__).resolve().parents[1]
INPUT = json.loads((TREE / "tests" / "reading_soundness" / "w5f_document_ask.json").read_text(encoding="utf-8"))
DOCUMENT = TREE / "tests" / "reading_soundness" / "w5f_document.md"
R8 = Path("/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2")


@pytest.fixture
def r8(monkeypatch):
    if not R8.is_dir():
        pytest.skip("ENV_MISSING[r8_placement]: %s" % R8)
    monkeypatch.delenv("VERA_PLACEMENT", raising=False)
    placement = EC.default_lookup(str(R8))
    monkeypatch.setattr(EC, "default_lookup", lambda *args, **kwargs: placement)
    return placement


def test_sources_match_the_loaded_markdown_text_and_loaded_line_numbers(tmp_path, r8):
    loaded = DL.load_paths([str(DOCUMENT)])
    assert loaded["loaded"] == 1 and loaded["skipped"] == []
    body = loaded["documents"][0].text
    output = io.StringIO()
    argv = ["--store", str(tmp_path / "store.json"), "ask", "--mode", "round5",
            "--document", str(DOCUMENT), "--", INPUT["question"]]
    with contextlib.redirect_stdout(output):
        rc = cli.main(argv)
    assert rc == 0
    result = json.loads(output.getvalue())
    expected = INPUT["expect"]
    assert result["verdict"] == expected["verdict"] and result["text"] == expected["text"], result
    assert result["door"] == "question_cross"
    source = next(item for item in result["sources"] if item.get("family") == "document")
    assert source["text"] == expected["source_text"]
    assert source["text"] in body
    assert "#" not in source["text"] and "](" not in source["text"]
    body_lines = [number for number, line in enumerate(body.splitlines(), 1) if source["text"] in line]
    assert body_lines == [source["line"]] == [expected["line"]]
