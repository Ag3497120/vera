"""W1-c: checks against the real codex corpus and the index built from it.

These need the real corpus (VERA_CODEX_CORPUS) and the index built from it
(VERA_P4_INDEX or VERA_W1C_INDEX). Without them every test is skipped with a reason that
starts with "環境不足:" so the skip is classified as missing environment, not as a pass.
Build the index with:
    python tools/build_p4_corpus_index.py --root $VERA_CODEX_CORPUS --out $VERA_P4_INDEX
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

import pytest

from tools import build_p4_corpus_index as bi
from verantyx.ability_corpus import Corpus, CorpusUnknown

_IDX = os.environ.get("VERA_W1C_INDEX") or os.environ.get("VERA_P4_INDEX")
_CORPUS = os.environ.get("VERA_CODEX_CORPUS")
_ready = bool(_IDX and _CORPUS and Path(_IDX).is_dir() and Path(_CORPUS).is_dir()
              and (Path(_IDX) / "pro.db").exists())
pytestmark = pytest.mark.skipif(
    not _ready, reason="環境不足: VERA_CODEX_CORPUS と、そこから作った索引 (VERA_P4_INDEX または VERA_W1C_INDEX) が必要")

FAMS = ("pro", "code", "conversation", "general_qa", "code_qa",
        "figurative_commonsense", "narrative", "paraphrase_entail")
FOUND = [("冷えた頬をマフラー", "pro"), ("湯気の中に青菜", "pro"), ("葉柄と葉身", "general_qa"),
         ("strings.HasSuffix", "code_qa"), ("strings.HasSuffix", "code"), ("重複部分文字列", "code_qa"),
         ("改札を出て左", "conversation")]


@pytest.fixture(scope="module")
def corpus():
    return Corpus(_IDX)


def _source_record(root: str, w) -> dict:
    with open(Path(root) / w.source_file, "rb") as handle:
        for n, raw in enumerate(handle, 1):
            if n == w.line:
                return json.loads(raw)
    raise AssertionError("line not found")


@pytest.mark.parametrize("phrase,family", FOUND)
def test_ticket_phrases_found_with_provenance_round_trip(corpus, phrase, family):
    hits = corpus.search(phrase, family, limit=5)
    assert hits.state == "FOUND"
    w = hits[0]
    assert w.origin == "generated" and w.source_file and w.line > 0
    rec = _source_record(_CORPUS, w)
    assert str(rec["sha"]) == w.sha
    body = bi.extract_body(rec, family, bi.SOURCES[family])[1]
    assert phrase in body


@pytest.mark.parametrize("phrase,family", [("Wi-Fiなし 携帯データ", "general_qa"), ("脱水機の異音", "conversation")])
def test_phrases_absent_from_the_corpus_are_no_match_not_unknown(corpus, phrase, family):
    hits = corpus.search(phrase, family, limit=5)
    assert hits.state == "NO_MATCH" and not isinstance(hits, CorpusUnknown)


def test_missing_family_and_missing_index_are_typed(corpus, tmp_path):
    assert corpus.search("改札を出て左", "local").state == "UNKNOWN_FAMILY_DB_MISSING"
    assert Corpus(tmp_path / "nowhere").search("改札を出て左", "conversation").state == "UNKNOWN_NO_INDEX"


def test_no_database_row_comes_from_heldout_or_overlap_dropped():
    for fam in FAMS:
        con = sqlite3.connect(f"file:{Path(_IDX) / (fam + '.db')}?mode=ro", uri=True)
        n = con.execute("SELECT COUNT(*) FROM rows WHERE source_file LIKE '%heldout%' "
                        "OR source_file LIKE '%overlap_dropped%'").fetchone()[0]
        families = {r[0] for r in con.execute("SELECT DISTINCT family FROM rows")}
        con.close()
        assert n == 0 and families == {fam}


def test_every_family_database_has_the_current_format_and_is_marked_generated():
    for fam in FAMS:
        con = sqlite3.connect(f"file:{Path(_IDX) / (fam + '.db')}?mode=ro", uri=True)
        meta = dict(con.execute("SELECT key,value FROM meta"))
        origins = {r[0] for r in con.execute("SELECT DISTINCT origin FROM rows")}
        con.close()
        assert meta["format"] == bi.FORMAT and origins == {"generated"}


# ---------------------------------------------------------------- W1-c2: R1 and decision 1
def test_no_database_row_has_a_body_equal_to_a_heldout_body_of_its_family():
    """Every family: the heldout body hashes (read by the builder's own function) and the DB's body_sha are disjoint."""
    for fam in FAMS:
        bodies, report = bi.heldout_bodies(Path(_CORPUS), fam)
        assert report["none_listed"] == (fam == "pro")
        con = sqlite3.connect(f"file:{Path(_IDX) / (fam + '.db')}?mode=ro", uri=True)
        con.execute("CREATE TEMP TABLE h(sha TEXT PRIMARY KEY)")
        con.executemany("INSERT INTO h VALUES (?)", ((s,) for s in bodies))
        n = con.execute("SELECT COUNT(*) FROM rows r JOIN h ON h.sha=r.body_sha").fetchone()[0]
        con.close()
        assert n == 0, fam


def test_manifest_with_heldout_overlap_is_balanced_and_records_the_heldout_files():
    manifest = Path(__file__).resolve().parents[1] / "artifacts/w1-c/manifest.json"
    if not manifest.exists():
        pytest.skip("環境不足: artifacts/w1-c/manifest.json がありません（実データで索引を作ると出力されます）")
    m = json.loads(manifest.read_text(encoding="utf-8"))
    assert m["heldout_unlisted"] == []
    for f in m["files"]:
        assert f["balanced"] and f["lines"] == f["indexed"] + sum(f["skipped"].values())
        if "heldout_body_overlap" in f["skipped"]:
            assert "heldout" in m["families"][f["family"]]
    assert any("heldout_body_overlap" in f["skipped"] for f in m["files"])


def test_commonsense_answer_on_the_real_index_carries_basis_origin_when_it_answers(tmp_path):
    from verantyx.abilities import Abilities
    from verantyx.chat import Chat
    chat = Chat([], general=tmp_path / "absent_general.db")
    chat._abilities = Abilities(Corpus(_IDX), general=chat.general)
    out = chat.reply("ドアを開けると、どうなりますか？")
    status = {t["family"]: t["index"] for t in out["trace"] if t.get("part") == "ability_corpus.status"}
    assert status.get("pro") == "INDEX_AVAILABLE" and "local" in status       # the states are in the trace
    generated = [s for s in out.get("sources", []) if isinstance(s, dict) and s.get("origin") == "generated"]
    if out.get("kind") in ("answer", "compose"):                       # "if it answers, the basis is typed"
        assert ("basis_origin" in out) == bool(generated)
        assert out.get("basis_origin") in (None, "generated")
