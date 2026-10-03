"""W5-e round 2 (docs/COARSE_PLACEMENT.md section 14.2, W3-a4 note R1): a へ that the generated frame's に|PLACE covers is shown in ``frame_unconfirmed``.

W3-a4's cover rule lets a generated frame without へ pass the frame confirmation when it has に|PLACE (the arm's ``cover["he_by_ni_place"]`` is then non-empty); the
covered へ appeared in neither ``frame`` nor ``frame_unconfirmed``.  ``frame_cover_unconfirmed(dec, gen_map)`` is the pure rule; ``_direct`` adds its result to
``frame_unconfirmed`` only (never to ``frame``).  This tree's ``coarse_types.decide_word`` does not write ``cover`` (that is W3-a4), so on this tree nothing changes for
r7 or r8; the tests below (a) call the pure function with hand-made ``dec`` / ``gen_map``, (b) put ``cover`` into the real decision with a monkeypatched wrapper and query
real r7 words (nothing is skipped), and (c) check that r7 is unchanged.  Expectations are written from r7's ``generated_frames`` rows and the round-1 ``h5_frames.jsonl``.
"""
import json
from pathlib import Path

import pytest

from verantyx import coarse_place as cp
from verantyx import coarse_types as ct

R7 = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1"
# Integration (auditor, 2026-10-04): the suite runs split across two machines and the registered build lives outside the tree, so a machine without
# it SKIPS with a visible reason instead of failing (same treatment as the other r7-pinned tests). Where r7 exists nothing changes.
import os as _os
import pytest as _pytest
pytestmark = _pytest.mark.skipif(not _os.path.isdir(R7), reason="ENV_MISSING[coarse placement r7/run1]")
HERE = Path(__file__).resolve().parent
ROUND1 = HERE.parent.parent / "artifacts" / "w5-e" / "h5_frames.jsonl"          # the r7 frame fields at the end of round 1 (measured)

GEN = ct.GEN_FRAME_ARM
COVER = {"he_by_ni_place": ["role_distribution@x"], "ignored": {}}


def _dec(cover=None, with_arm=True):
    arm = {"arm": GEN}
    if cover is not None:
        arm["cover"] = cover
    return {"arms": {GEN: arm} if with_arm else {}}


# ---------------------------------------------------------------------------------------------------------------------------------
# (a) the pure function
# ---------------------------------------------------------------------------------------------------------------------------------
def test_the_particles_are_those_of_the_cover_rule_in_coarse_types():
    assert (ct.CASE_PARTICLES_9[4], ct.CASE_PARTICLES_9[2]) == ("へ", "に")


def test_a_covered_he_is_unconfirmed_with_the_type_of_the_covering_row():
    assert cp.frame_cover_unconfirmed(_dec(COVER), {"に": ["PLACE"]}) == {"へ": ["PLACE"]}
    # the type is the covering row's type PLACE, whatever else the frame says about に
    assert cp.frame_cover_unconfirmed(_dec(COVER), {"に": ["GROUP_ORG", "PERSON", "PLACE"], "を": ["ABSTRACT"]}) == {"へ": ["PLACE"]}


@pytest.mark.parametrize("dec", [
    _dec({"he_by_ni_place": [], "ignored": {}}),                    # nothing was covered
    _dec({"ignored": {}}),                                          # no he_by_ni_place key
    _dec(),                                                         # no cover at all
    _dec(with_arm=False),                                           # no gen_frame arm
    {"arms": {GEN: {"arm": GEN, "cover": None}}},                   # a null cover
    {},                                                             # no arms key
])
def test_nothing_is_added_when_the_decision_covered_no_he(dec):
    assert cp.frame_cover_unconfirmed(dec, {"に": ["PLACE"]}) == {}


def test_nothing_is_added_when_the_frame_has_he_itself():
    assert cp.frame_cover_unconfirmed(_dec(COVER), {"に": ["PLACE"], "へ": ["PLACE"]}) == {}
    assert cp.frame_cover_unconfirmed(_dec(COVER), {"へ": ["ARTIFACT"], "に": ["PLACE"]}) == {}


def test_nothing_is_added_when_the_ni_row_is_not_place():
    assert cp.frame_cover_unconfirmed(_dec(COVER), {"に": ["PERSON"]}) == {}
    assert cp.frame_cover_unconfirmed(_dec(COVER), {"を": ["PLACE"]}) == {}          # PLACE under another particle is not に|PLACE
    assert cp.frame_cover_unconfirmed(_dec(COVER), {}) == {}


def test_the_ignored_particles_are_not_shown():
    # K62's outside particles (と・まで・より) that the cover ignored are NOT shown (the ruling names the covered particle only)
    dec = _dec({"he_by_ni_place": [], "ignored": {"role_distribution@x": ["と", "まで"]}})
    assert cp.frame_cover_unconfirmed(dec, {"に": ["PLACE"]}) == {}
    dec = _dec({"he_by_ni_place": ["role_distribution@x"], "ignored": {"role_distribution@y": ["より"]}})
    assert cp.frame_cover_unconfirmed(dec, {"に": ["PLACE"]}) == {"へ": ["PLACE"]}


def test_the_function_does_not_change_its_arguments():
    dec, gen_map = _dec(COVER), {"に": ["PLACE"]}
    before = (json.dumps(dec, sort_keys=True), json.dumps(gen_map, sort_keys=True))
    cp.frame_cover_unconfirmed(dec, gen_map)
    assert (json.dumps(dec, sort_keys=True), json.dumps(gen_map, sort_keys=True)) == before


# ---------------------------------------------------------------------------------------------------------------------------------
# (b) through _direct, on real r7 words, with ``cover`` put into the real decision
# ---------------------------------------------------------------------------------------------------------------------------------
@pytest.fixture
def with_cover(monkeypatch):
    """The real ``decide_word`` with ``cover`` added to the gen_frame arm (this tree's decide_word writes none: that is W3-a4)."""
    real = ct.decide_word

    def wrapped(ev, cfg):
        d = real(ev, cfg)
        if GEN in d["arms"]:
            d["arms"][GEN]["cover"] = dict(WRAP_COVER["value"])
        return d

    WRAP_COVER["value"] = COVER
    monkeypatch.setattr(ct, "decide_word", wrapped)
    return WRAP_COVER


WRAP_COVER = {"value": COVER}


def test_r7_a_confirmed_word_whose_frame_has_ni_place_and_no_he_gets_he_in_unconfirmed_only(with_cover):
    # r7 generated_frames: 申し込める = {に: [GROUP_ORG, PERSON, PLACE], を: [ABSTRACT, ARTIFACT, EVENT_ACT]} (no へ).  Round-1 answer (h5_frames.jsonl):
    # frame {を: [EVENT_ACT]}, frame_unconfirmed {を: [ABSTRACT, ARTIFACT], に: [GROUP_ORG, PERSON, PLACE]}.  With a covered へ: へ is added to frame_unconfirmed
    # (keys in ROLE_PARTICLES order: を, に, へ), and nothing else moves.
    a = cp.query("申し込める", placement=R7)
    assert (a["state"], a["origin"], a["top"], a["frame_status"]) == ("DECIDED", "direct", ["P_COMMUNICATE"], "CONFIRMED")
    assert a["frame"] == {"を": ["EVENT_ACT"]}
    assert a["frame_unconfirmed"] == {"を": ["ABSTRACT", "ARTIFACT"], "に": ["GROUP_ORG", "PERSON", "PLACE"], "へ": ["PLACE"]}
    assert list(a["frame_unconfirmed"]) == ["を", "に", "へ"]
    assert "へ" not in a["frame"]


def test_r7_a_word_without_ni_place_in_its_generated_frame_is_not_changed_by_a_cover(with_cover):
    # 冠する = {を: [ABSTRACT, INFO_LANGUAGE]}: no に|PLACE, so nothing is covered whatever the arm says
    a = cp.query("冠する", placement=R7)
    assert a["frame_status"] == "CONFIRMED" and a["frame"] == {"を": ["INFO_LANGUAGE"]} and a["frame_unconfirmed"] == {"を": ["ABSTRACT"]}


def test_r7_a_word_whose_frame_has_he_is_not_changed_by_a_cover(with_cover):
    # 戻れる = {に: [PLACE], へ: [PLACE]}: へ is in the frame, so it is not covered
    a = cp.query("戻れる", placement=R7)
    assert a["frame_status"] == "CONFIRMED" and a["frame"] == {"へ": ["PLACE"]}
    assert a["frame_unconfirmed"] == {"が": ["ANIMAL", "ARTIFACT", "PERSON"], "に": ["PLACE"]}


def test_r7_a_cover_that_only_ignored_particles_does_not_add_he(with_cover):
    with_cover["value"] = {"he_by_ni_place": [], "ignored": {"role_distribution@x": ["と"]}}
    a = cp.query("申し込める", placement=R7)
    assert a["frame_unconfirmed"] == {"を": ["ABSTRACT", "ARTIFACT"], "に": ["GROUP_ORG", "PERSON", "PLACE"]}


def test_r7_the_cover_never_changes_anything_but_frame_unconfirmed(with_cover):
    rows = {json.loads(l)["word"]: json.loads(l) for l in open(ROUND1, encoding="utf-8")}
    changed = {}
    for w, r in rows.items():
        if r["frame_status"] != "CONFIRMED":
            continue
        a = cp.query(w, placement=R7)
        for k in ("state", "origin", "top", "frame_status", "frame"):
            assert a.get(k) == r[k], (w, k)
        if a["frame_unconfirmed"] != r["frame_unconfirmed"]:
            changed[w] = a["frame_unconfirmed"]
    # the words whose generated frame has に|PLACE and no へ: 申し込める only (r7 has 35 CONFIRMED words)
    assert sorted(changed) == ["申し込める"]
    assert changed["申し込める"]["へ"] == ["PLACE"]


# ---------------------------------------------------------------------------------------------------------------------------------
# (c) r7 is unchanged on this tree (decide_word writes no cover)
# ---------------------------------------------------------------------------------------------------------------------------------
def test_r7_confirmed_words_answer_exactly_as_at_the_end_of_round_1():
    n = 0
    for line in open(ROUND1, encoding="utf-8"):
        r = json.loads(line)
        if r["frame_status"] != "CONFIRMED":
            continue
        n += 1
        a = cp.query(r["word"], placement=R7)
        assert {k: a.get(k) for k in r if k != "word"} == {k: r[k] for k in r if k != "word"}, r["word"]
    assert n == 35
