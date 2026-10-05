"""W3-d1 (5): tools/fusion/evaluate_model.py `reread_match` (no network, no model). r9 is read only."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.fusion import evaluate_model as EM
from verantyx import cross_tokens, event_cross, semantic_read

R9 = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2"
pytestmark = pytest.mark.skipif(not Path(R9).exists(), reason="ENV_MISSING[coarse placement r9/run2]")


def tokens_of(text):
    got = event_cross.build_crosses(semantic_read.read(text, "ja", placement=R9), event_cross.default_lookup(R9))
    assert got.status == "CROSSED" and len(got.crosses) == 1
    return cross_tokens.cross_to_tokens(got.crosses[0])


def test_a_realized_sentence_that_reads_back_the_same_is_a_match():
    text = "弟がこの工場で働いた。"
    result = EM.reread_match(text, tokens_of(text), placement=R9)
    assert result["status"] == "MATCH" and result["text"].endswith("働いた。")


def test_tokens_of_another_text_do_not_match_the_original():
    result = EM.reread_match("母が駅へ歩いた。", tokens_of("弟がこの工場で働いた。"), placement=R9)
    assert result["status"] == "MISMATCH" and "CROSS_MISMATCH" in result["labels"] and "PREDICATE_MISMATCH" in result["labels"]


def test_a_cross_the_realizer_cannot_say_is_not_realized_not_a_mismatch():
    text = "兄が休日、手紙を書いた。"
    result = EM.reread_match(text, tokens_of(text), placement=R9)
    assert result["status"] == "NOT_REALIZED" and result["reason"] == "ROLE_NOT_REALIZABLE"


def test_a_text_that_is_not_crossed_is_reported_as_such():
    assert EM.reread_match("2025年3月5日に東京で会議が開かれた。", "x", placement=R9)["status"] == "SOURCE_NOT_CROSSED"


def test_main_counts_the_rows(tmp_path, capsys):
    rows = tmp_path / "rows.jsonl"
    rows.write_text("".join(json.dumps({"text": t, "tokens": tokens_of(t)}, ensure_ascii=False) + "\n" for t in ("弟がこの工場で働いた。", "兄が休日、手紙を書いた。")), encoding="utf-8")
    assert EM.main([str(rows), "--placement", R9]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary == {"rows": 2, "counts": {"MATCH": 1, "NOT_REALIZED": 1}}


def test_a_refused_forms_table_comes_back_as_a_typed_answer():
    text = "弟がこの工場で働いた。"
    here = Path(__file__).resolve().parents[1] / "artifacts" / "w3-d1" / "t3_layer_override_particle.json"
    result = EM._realize_via_cli(tokens_of(text), "ja", Path(R9), here)
    assert result["status"] == "REFUSED" and result["reason"] == "FORMS_OVERRIDE_REFUSED"
    assert EM.reread_match(text, tokens_of(text), placement=R9, forms=here)["status"] == "NOT_REALIZED"
