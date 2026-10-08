"""W5-e A-1 boundary probes from the attack brief; revised after the first probe compared provenance order."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tests"))

from test_question_cross_observe import Q_SHIP, S1, S2, ask
from test_question_cross_w5d import excluded, write_pl
from test_question_cross_w5e import S3


def test_a1_agree_disagree_and_unchecked_returns_incomplete_typing(tmp_path):
    pl = write_pl(tmp_path, {
        "船長": "PERSON",
        "提督": "ANIMAL",
        "将軍": ("UNPLACED", None, []),
    })
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2, S3], placement=pl)
    assert out["answer"]["status"] == "INCOMPLETE_TYPING"
    assert [f["surface"] for f in out["answer"]["fillers"]] == ["船長"]
    assert set(excluded(out)) == {("提督", "HOLE_TYPE_DISAGREE"), ("将軍", "TYPE_UNCHECKED")}
    assert out["ranks"] == []


def test_a1_disagree_plus_unchecked_without_agreement_is_not_a_typed_answer(tmp_path):
    pl = write_pl(tmp_path, {"船長": "ANIMAL", "提督": ("UNPLACED", None, [])})
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=pl)
    assert out["answer"]["status"] == "NO_TYPED_CANDIDATE"
    assert out["answer"]["fillers"] == []
    assert set(excluded(out)) == {("船長", "HOLE_TYPE_DISAGREE"), ("提督", "TYPE_UNCHECKED")}
    assert out["ranks"] == []


def test_a1_tied_agreements_keep_no_winner_when_unchecked_candidate_order_changes(tmp_path):
    pl = write_pl(tmp_path, {
        "船長": "PERSON",
        "提督": "PERSON",
        "将軍": ("UNPLACED", None, []),
    })
    first, _ = ask(tmp_path, Q_SHIP, [S1, S2, S3], placement=pl)
    reverse, _ = ask(tmp_path, Q_SHIP, [S3, S2, S1], placement=pl)
    assert first["answer"]["status"] == reverse["answer"]["status"] == "INCOMPLETE_TYPING"
    assert {f["surface"] for f in first["answer"]["fillers"]} == {f["surface"] for f in reverse["answer"]["fillers"]}
    first_excluded = sorted((x["surface"], x["reason"]) for x in first["answer"]["excluded"])
    reverse_excluded = sorted((x["surface"], x["reason"]) for x in reverse["answer"]["excluded"])
    assert first_excluded == reverse_excluded
    assert first["ranks"] == reverse["ranks"] == []


def test_a1_all_unchecked_candidates_remain_no_typed_candidate(tmp_path):
    pl = write_pl(tmp_path, {
        "船長": ("UNPLACED", None, []),
        "提督": ("UNKNOWN", None, []),
    })
    out, _ = ask(tmp_path, Q_SHIP, [S1, S2], placement=pl)
    assert out["answer"]["status"] == "NO_TYPED_CANDIDATE"
    assert out["answer"]["fillers"] == [] and len(out["answer"]["excluded"]) == 2
    assert out["ranks"] == []
