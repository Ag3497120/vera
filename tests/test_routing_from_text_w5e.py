"""W5-e (docs/ROUTING_FROM_TEXT.md, W5-e A-2; rewritten in round 2 after the auditor's correction of 2026-10-04 04:42:38): an estimated common noun is not routed as an agent.

A Japanese name that no naming sentence introduced is, by what the placement answers about the word:
  1 no usable answer (None / NO_PLACEMENT)           -> NAME_UNVERIFIED:<name>:NO_PLACEMENT (as in W5-d)
  2 direct DECIDED or MULTIPLE with a noun type      -> COMMON_NOUN_SUBJECT:<name>:PLACEMENT_DIRECT:<types>, counted ``flagged`` (as in W5-d: ``any``)
  3 estimated (any state, any types)                 -> COMMON_NOUN_SUBJECT:<name>:PLACEMENT_ESTIMATED:<types>, counted ``checked`` (an estimate is a construction, not a testimony)
  4 UNPLACED / UNKNOWN / direct with no noun type    -> passes to the check against declared names (as in W5-d), counted ``checked``
The round-1 reason ``COMMON_NOUN_SUBJECT_UNTYPED`` is retired (never returned).
Hand-made reading outputs and made-up placements (as tests/test_routing_from_text_w5b.py), and, for the real placement r7, the real reader.
"""
import pytest

from verantyx import routing_from_text as rt
from verantyx.event_cross import PlaceResult

from test_routing_from_text_w5b import Placement, direct, en_review, explain, ja_do, rd, cl, route

R7 = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1"
# Integration (auditor, 2026-10-04): the suite runs split across two machines and the registered build lives outside the tree, so a machine without
# it SKIPS with a visible reason instead of failing (same treatment as the other r6/r7-pinned tests). Where the build exists nothing changes.
_needs_build = pytest.mark.skipif(not __import__('os').path.isdir(R7), reason="ENV_MISSING[coarse placement r7/run1]")
SENTENCE = "ソラは実装をやる。\n"
CHECK_KEYS = {"lookup", "checked", "not_checked", "flagged", "introduced_by_naming"}


def _one(answer, name="ソラ"):
    lookup = Placement(**{name: answer}) if answer is not None else None
    explained = explain(f"{name}は実装をやる。\n", {f"{name}は実装をやる。": ja_do(name)}, lookup)
    (unit,) = explained.extraction.units
    return explained, unit


def _counts(explained):
    check = route(explained, role="implement", kind="feature")["reading"]["common_noun_check"]
    assert set(check) == CHECK_KEYS
    return (check["checked"], check["not_checked"], check["flagged"], check["introduced_by_naming"])


# ------------------------------------------------------------------ 3: estimated (any state, any types) is stopped, and counted checked
@pytest.mark.parametrize("answer,types", [
    (PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True}), "GROUP_ORG"),
    (PlaceResult("DECIDED", "estimated", "generated", ("PERSON",), {"fake": True}), "PERSON"),
    (PlaceResult("MULTIPLE", "estimated", "proximity", ("GROUP_ORG", "PERSON"), {"fake": True}), "GROUP_ORG,PERSON"),
    (PlaceResult("DECIDED", "estimated", "proximity", ("P_COMMUNICATE",), {"fake": True}), "P_COMMUNICATE"),     # whatever the type: an estimate is not a testimony
])
def test_a2_3_an_estimated_answer_stops_the_name_with_the_estimated_reason(answer, types):
    explained, unit = _one(answer)
    assert unit.status == "NAME_UNRESOLVED" and unit.reasons == [f"COMMON_NOUN_SUBJECT:ソラ:PLACEMENT_ESTIMATED:{types}"]
    assert not explained.records.agents and not explained.extraction.relations           # no agent record, no relation
    got = route(explained, role="implement", kind="feature")
    assert got["agent"] is None and got["decision"] == "undecided" and got["abstention"]["type"] == "INCOMPLETE_READING"
    assert _counts(explained) == (1, 0, 0, 0)                                              # checked (the placement answered), not flagged


def test_a2_3_the_retired_reason_is_never_returned():
    for answer in (PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True}), PlaceResult("UNPLACED", provenance={"fake": True}),
                   PlaceResult("UNKNOWN", provenance={"fake": True}), PlaceResult("MULTIPLE", "direct", None, ("P_COMMUNICATE", "P_MOVE"), {"fake": True}),
                   PlaceResult("MULTIPLE", "estimated", "proximity", ("P_COMMUNICATE", "P_MOVE"), {"fake": True})):
        _, unit = _one(answer)
        assert not any("COMMON_NOUN_SUBJECT_UNTYPED" in r for r in unit.reasons), (answer, unit.reasons)


# ------------------------------------------------------------------ 4: UNPLACED / UNKNOWN pass (W5-d), counted checked
@pytest.mark.parametrize("answer", [PlaceResult("UNPLACED", provenance={"fake": True}), PlaceResult("UNKNOWN", provenance={"fake": True})])
def test_a2_4_an_unplaced_or_unknown_word_passes_to_the_name_check_as_in_w5d(answer):
    explained, unit = _one(answer)
    assert unit.status == "MAPPED" and unit.reasons == []
    assert route(explained, role="implement", kind="feature")["agent"] == "ソラ"
    assert _counts(explained) == (1, 0, 0, 0)


# ------------------------------------------------------------------ 1: no usable answer
def test_a2_1_no_answer_is_name_unverified_and_counted_not_checked(monkeypatch):
    monkeypatch.delenv("VERA_PLACEMENT", raising=False)
    explained, unit = _one(None)
    assert unit.status == "NAME_UNRESOLVED" and unit.reasons == ["NAME_UNVERIFIED:ソラ:NO_PLACEMENT"]
    check = route(explained, role="implement", kind="feature")["reading"]["common_noun_check"]
    assert (check["checked"], check["not_checked"], check["flagged"]) == (0, 1, 0)


class _NoPlacement:
    id = "w5e-no-placement/1"

    def lookup(self, lemma):
        return PlaceResult("NO_PLACEMENT", provenance={"fake": True})


def test_a2_1_a_no_placement_answer_is_name_unverified():
    explained = explain(SENTENCE, {SENTENCE.strip(): ja_do("ソラ")}, _NoPlacement())
    (unit,) = explained.extraction.units
    assert unit.status == "NAME_UNRESOLVED" and unit.reasons == ["NAME_UNVERIFIED:ソラ:NO_PLACEMENT"]


# ------------------------------------------------------------------ 2: a direct type with a noun type is stopped as before (``any``), counted flagged
@pytest.mark.parametrize("types", [("GROUP_ORG",), ("PERSON",), ("GROUP_ORG", "PERSON"), ("P_COMMUNICATE", "PERSON"), ("ANIMAL", "GROUP_ORG", "PERSON")])
def test_a2_2_a_direct_type_with_a_noun_type_stops_as_a_typed_common_noun(types):
    explained, unit = _one(direct(*types))
    assert unit.status == "NAME_UNRESOLVED" and len(unit.reasons) == 1 and unit.reasons[0].startswith("COMMON_NOUN_SUBJECT:ソラ:PLACEMENT_DIRECT:")
    assert set(unit.reasons[0].rsplit(":", 1)[1].split(",")) == set(types)
    assert _counts(explained) == (0, 0, 1, 0)         # flagged is for the direct noun types only (a flagged name is not also counted as checked)


# ------------------------------------------------------------------ a direct type with no noun type passes
@pytest.mark.parametrize("types", [("P_COMMUNICATE",), ("P_COMMUNICATE", "P_MOVE")])
def test_a2_4_a_direct_type_with_no_noun_type_still_passes(types):
    explained, unit = _one(direct(*types))
    assert unit.status == "MAPPED" and unit.reasons == []
    assert route(explained, role="implement", kind="feature")["agent"] == "ソラ"
    assert _counts(explained)[0:3:2] == (1, 0)       # checked 1, flagged 0


# ------------------------------------------------------------------ introduced by a naming sentence, and English
def test_a2_a_name_that_a_naming_sentence_introduced_is_a_name_whatever_the_placement_says():
    lookup = Placement(ソラ=PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True}), ミラ=PlaceResult("UNPLACED", provenance={"fake": True}))
    table = {"ミラは実装をやる。": ja_do("ミラ"),
             "ミラをソラと呼ぶ。": rd("ja", cl("呼ぶ", {"patient": "ミラ", "result": "ソラ"})),
             "ソラはテストを書く。": rd("ja", cl("書く", {"agent": "ソラ", "patient": "テスト"}))}
    explained = explain("ミラは実装をやる。\nミラをソラと呼ぶ。\nソラはテストを書く。\n", table, lookup)
    # ミラ is UNPLACED (passes, as in W5-d); ソラ (estimated) is introduced by the naming sentence, so it is not examined
    assert [u.status for u in explained.extraction.units] == ["MAPPED", "MAPPED", "MAPPED"]
    only = explain("ミラをソラと呼ぶ。\nソラはテストを書く。\n", {k: v for k, v in table.items() if k != "ミラは実装をやる。"}, lookup)
    assert [u.status for u in only.extraction.units] == ["MAPPED", "MAPPED"]
    assert route(only, role="implement", kind="feature")["reading"]["common_noun_check"]["introduced_by_naming"] == 1


def test_a2_english_is_not_changed_a_name_with_an_untyped_answer_still_passes():
    for answer in (PlaceResult("UNPLACED", provenance={"fake": True}), PlaceResult("UNKNOWN", provenance={"fake": True}),
                   PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True})):
        explained = explain("Mira reviews code.\n", {"Mira reviews code.": en_review("Mira")}, Placement(Mira=answer))
        assert [u.status for u in explained.extraction.units] == ["MAPPED"], answer
        assert route(explained)["agent"] == "Mira"
    # the determiner test is as before
    explained = explain("The crew reviews code.\n", {"The crew reviews code.": en_review("crew")}, Placement())
    assert explained.extraction.units[0].reasons == ["COMMON_NOUN_SUBJECT:crew:DETERMINER:The"]


def test_a2_one_estimated_name_stops_the_whole_text_as_a_typed_common_noun_does():
    lookup = Placement(ミラ=direct("P_COMMUNICATE"), ソラ=PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True}))
    table = {"ミラは実装をやる。": ja_do("ミラ"), "ソラはテストを書く。": rd("ja", cl("書く", {"agent": "ソラ", "patient": "テスト"}))}
    explained = explain("ミラは実装をやる。\nソラはテストを書く。\n", table, lookup)
    assert [u.status for u in explained.extraction.units] == ["MAPPED", "NAME_UNRESOLVED"]
    assert route(explained, role="implement", kind="feature")["agent"] is None


# ------------------------------------------------------------------ the real placement r7 and the real reader
@pytest.mark.parametrize("sentence,noun,types", [
    ("委員会がテストを書く。", "委員会", "GROUP_ORG"),
    ("開発者がテストを書く。", "開発者", "PERSON"),
])
@_needs_build
def test_a2_r7_an_estimated_common_noun_is_not_routed(monkeypatch, sentence, noun, types):
    monkeypatch.setenv("VERA_PLACEMENT", R7)
    explained = rt.explain(sentence + "\n", "x.md")
    (unit,) = explained.extraction.units
    assert unit.status == "NAME_UNRESOLVED" and unit.reasons == [f"COMMON_NOUN_SUBJECT:{noun}:PLACEMENT_ESTIMATED:{types}"], (sentence, unit)
    routed = rt.route_task(explained, {"role": "implement", "kind": "test_authoring", "size": "medium"})
    assert routed["agent"] is None and routed["decision"] == "undecided"


@pytest.mark.parametrize("sentence,noun", [
    ("レビューは課がやる。", "課"),
    ("レビューは外注先がやる。", "外注先"),
])
@_needs_build
def test_a2_r7_an_unplaced_word_is_routed_as_in_w5d_by_the_corrected_rule(monkeypatch, sentence, noun):
    # W5-e2: r7 says UNPLACED for these words; the corrected rule (auditor, 2026-10-04 04:42:38) passes an UNPLACED word to the name check, exactly as W5-d did
    monkeypatch.setenv("VERA_PLACEMENT", R7)
    explained = rt.explain(sentence + "\n", "x.md")
    (unit,) = explained.extraction.units
    assert unit.status == "MAPPED" and unit.reasons == [], (sentence, unit)
