"""T4: B7 の生成コーパスの索引の形式。見本の generated_snippets から prepare_b7 で作った索引を、実ツリーの
verantyx.ability_corpus.Corpus が FOUND・origin == "generated" の行で返すこと（形式の漂流を検出する）。子プロセスは使わない。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tools.bank_score import adapters
from tools.bank_score.runner import B7_EXTRA_ENV_KEYS, Session
from tools.bank_score.v2 import b7
from verantyx import ability_corpus

FIX = Path(__file__).parent / "fixtures" / "B7"


def items():
    return [json.loads(l) for l in (FIX / "items.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


@pytest.fixture()
def sess(tmp_path):
    s = Session(sys.executable, str(tmp_path), None, 30.0)
    try:
        yield s
    finally:
        s.close()


def test_index_built_from_fixture_snippets_is_found_and_generated(sess):
    n_checked = 0
    for seq, it in enumerate([i for i in items() if i["generated_snippets"]], start=1):
        prep = sess.prepare_b7(seq, it["human_sources"], it["generated_snippets"])
        assert "error" not in prep, prep
        assert prep["p4_rows"] == len(it["generated_snippets"])
        corpus = ability_corpus.Corpus(prep["p4_index"])
        assert corpus.status("local") == ability_corpus.INDEX_AVAILABLE
        for sentence in it["generated_snippets"]:
            term = sentence.strip()[:5]
            hits = corpus.search(term, "local")
            assert hits.state == "FOUND", (term, hits.state, hits.reason)
            assert sentence in [h.text for h in hits], (sentence, [h.text for h in hits])
            for h in hits:
                assert h.origin == "generated" and h.family == "local"
            n_checked += 1
    assert n_checked >= 20


def test_index_directory_holds_only_the_family_database(sess):
    prep = sess.prepare_b7(1, [], ["生成の文その一です。", "Second generated sentence."])
    assert sorted(p.name for p in Path(prep["p4_index"]).iterdir()) == ["local.db"]
    assert prep["p4_rows"] == 2
    # 入力の jsonl は索引ディレクトリの外
    assert Path(prep["p4_index"]).parent.name == "p4" and (sess.work / "p4src" / "q0001.jsonl").is_file()
    corpus = ability_corpus.Corpus(prep["p4_index"])
    assert corpus.search("Second", "local").state == "FOUND"
    assert corpus.search("その一", "local").state == "FOUND"


def test_zero_generated_snippets_points_at_an_empty_directory(sess):
    prep = sess.prepare_b7(1, ["人の文。"], [])
    d = Path(prep["p4_index"])
    assert d.is_dir() and sorted(p.name for p in d.iterdir()) == []
    assert prep["p4_rows"] == 0
    corpus = ability_corpus.Corpus(d)
    assert list(d.glob("*.db")) == []
    hits = corpus.search("人の", "local")
    # J4: 実測の状態は UNKNOWN_NO_INDEX（チケットの括弧書きの UNKNOWN_FAMILY_DB_MISSING ではない）
    assert hits.state == "UNKNOWN_NO_INDEX" and len(hits) == 0


def test_every_question_gets_its_own_index_and_document_by_sequence_number(sess):
    a = sess.prepare_b7(1, ["一つ目。"], ["生成の文A。"])
    b = sess.prepare_b7(2, ["二つ目。"], ["生成の文B。"])
    c = sess.prepare_b7(3, [], [])
    assert len({a["p4_index"], b["p4_index"], c["p4_index"]}) == 3
    assert a["document"].endswith("/docs/q0001.txt") and b["document"].endswith("/docs/q0002.txt")
    assert a["p4_index"].endswith("/p4/q0001") and c["p4_index"].endswith("/p4/q0003")
    assert c["document"] is None and c["document_sha256"] is None
    assert Path(a["document"]).read_text(encoding="utf-8") == "一つ目。\n"
    assert ability_corpus.Corpus(a["p4_index"]).search("生成の文A", "local").state == "FOUND"
    assert ability_corpus.Corpus(a["p4_index"]).search("生成の文B", "local").state == "NO_MATCH"


def test_document_is_one_sentence_per_line_in_order(sess):
    prep = sess.prepare_b7(1, ["一行目。", "二行目。", "Third line."], [])
    assert Path(prep["document"]).read_text(encoding="utf-8") == "一行目。\n二行目。\nThird line.\n"
    import hashlib
    assert prep["document_sha256"] == hashlib.sha256(Path(prep["document"]).read_bytes()).hexdigest()


def test_prepare_failure_is_typed_not_an_exception(sess):
    sess.prepare_b7(1, [], [])
    prep = sess.prepare_b7(1, [], [])  # 同じ通し番号の二重作成: ディレクトリが既にある（OSError）
    assert prep == {"error": "B7_PREPARE_FAILED", "detail": "FileExistsError"}


def test_extra_env_is_closed_and_default_env_keeps_eight_keys(sess):
    prov = sess.work / "prov" / "x.json"
    base = sess.env(prov)
    assert set(base) == {"PATH", "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "HOME", "VERA_CORPUS_ROOT",
                         "BANK_SCORE_PROVENANCE", "LANG", "PYTHONIOENCODING"} | (
        {"VERA_PLACEMENT"} if "VERA_PLACEMENT" in base else set())
    assert sess.env(prov, None) == base and sess.env(prov, {}) == base
    e = sess.env(prov, {"VERA_P4_INDEX": "/x/y"})
    assert set(e) - set(base) == {"VERA_P4_INDEX"} and e["VERA_P4_INDEX"] == "/x/y"
    assert {k: v for k, v in e.items() if k != "VERA_P4_INDEX"} == base
    assert B7_EXTRA_ENV_KEYS == ("VERA_P4_INDEX",)
    for bad in ({"VERA_CORPUS_ROOT": "/x"}, {"VERA_P4_INDEX": "/x", "OTHER": "1"}, {"PATH": "/x"}):
        with pytest.raises(ValueError):
            sess.env(prov, bad)


def test_b7_entry_table_and_argv():
    assert adapters.ENTRIES["B7"] == ("cli-ask-round5-basis",)
    assert adapters.check_entry("B7", None) == "cli-ask-round5-basis"
    assert adapters.entry_module("cli-ask-round5-basis") == "verantyx.cli"
    with pytest.raises(ValueError):
        adapters.check_entry("B7", "cli")
    case = {"request": "-x 依頼", "request_kind": "style", "human_sources": ["a"], "generated_snippets": [],
            "human_present": True, "show_reference": True}
    assert adapters.reachability("B7", "cli-ask-round5-basis", case)["reachable"] is True
    call = adapters.build_call("B7", "cli-ask-round5-basis", case, document="/w/docs/q0001.txt")
    assert call == {"module": "verantyx.cli", "files": [], "argv": [
        "ask", "--mode", "round5", "--document", "/w/docs/q0001.txt", "--request-kind", "style", "--human-present",
        "--show-generated-reference", "--", "-x 依頼"]}
    case.update(human_present=False, show_reference=False, human_sources=[])
    call = adapters.build_call("B7", "cli-ask-round5-basis", case, document=None)
    assert call["argv"] == ["ask", "--mode", "round5", "--request-kind", "style", "--", "-x 依頼"]


def test_fixture_items_index_rows_match_snippet_counts():
    assert max(len(i["generated_snippets"]) for i in items()) == 2
    assert sum(1 for i in items() if not i["generated_snippets"]) >= 3
    assert b7.OUTCOMES  # 見本の 6 値の写しが読める
