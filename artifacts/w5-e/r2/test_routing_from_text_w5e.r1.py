"""W5-e (docs/ROUTING_FROM_TEXT.md, W5-e A-2): an estimated or unplaced common noun is not routed as an agent.

A Japanese name that no naming sentence introduced is, by what the placement answers about the word:
  1 no usable answer                                -> NAME_UNVERIFIED:<name>:NO_PLACEMENT (as before)
  2 direct DECIDED, a noun type                     -> COMMON_NOUN_SUBJECT:<name>:PLACEMENT_DIRECT:<type> (as before)
  3 direct MULTIPLE, every candidate a noun type    -> the same as 2
  4 direct DECIDED, a type that is not a noun type  -> passes (as before: R-J1)
  5 anything else (estimated, UNPLACED, UNKNOWN, a MULTIPLE with a candidate that is not a noun type, other states)
                                                    -> COMMON_NOUN_SUBJECT_UNTYPED:<name>:<ESTIMATED|UNPLACED|UNKNOWN|MULTIPLE|state>
Hand-made reading outputs and made-up placements (as tests/test_routing_from_text_w5b.py), and, for the real placement r7, the real reader.
"""
import pytest

from verantyx import routing_from_text as rt
from verantyx.event_cross import PlaceResult

from test_routing_from_text_w5b import Placement, direct, en_review, explain, ja_do, rd, cl, route

R7 = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1"
SENTENCE = "ソラは実装をやる。\n"
CHECK_KEYS = {"lookup", "checked", "not_checked", "flagged", "introduced_by_naming"}


def _one(answer, name="ソラ"):
    lookup = Placement(**{name: answer}) if answer is not None else None
    explained = explain(f"{name}は実装をやる。\n", {f"{name}は実装をやる。": ja_do(name)}, lookup)
    (unit,) = explained.extraction.units
    return explained, unit


# ------------------------------------------------------------------ 5: estimated / UNPLACED / UNKNOWN / a MULTIPLE that is not all noun types
@pytest.mark.parametrize("answer,state", [
    (PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True}), "ESTIMATED"),
    (PlaceResult("DECIDED", "estimated", "generated", ("PERSON",), {"fake": True}), "ESTIMATED"),
    (PlaceResult("UNPLACED", provenance={"fake": True}), "UNPLACED"),
    (PlaceResult("UNKNOWN", provenance={"fake": True}), "UNKNOWN"),
    (PlaceResult("MULTIPLE", "direct", None, ("GROUP_ORG", "P_COMMUNICATE"), {"fake": True}), "MULTIPLE"),
    (PlaceResult("MULTIPLE", "direct", None, ("P_COMMUNICATE", "P_ACT"), {"fake": True}), "MULTIPLE"),
])
def test_a2_5_an_untyped_answer_stops_the_name_with_a_typed_reason(answer, state):
    explained, unit = _one(answer)
    assert unit.status == "NAME_UNRESOLVED" and unit.reasons == [f"COMMON_NOUN_SUBJECT_UNTYPED:ソラ:{state}"]
    assert not explained.records.agents and not explained.extraction.relations           # no agent record, no relation
    got = route(explained, role="implement", kind="feature")
    assert got["agent"] is None and got["decision"] == "undecided" and got["abstention"]["type"] == "INCOMPLETE_READING"
    check = got["reading"]["common_noun_check"]
    assert set(check) == CHECK_KEYS and (check["checked"], check["not_checked"], check["flagged"], check["introduced_by_naming"]) == (1, 0, 0, 0)


def test_a2_5_an_estimated_word_with_a_typed_candidate_is_not_a_name_either_even_for_a_person_type():
    explained, unit = _one(PlaceResult("DECIDED", "estimated", "proximity", ("PERSON",), {"fake": True}), "ミラ")
    assert unit.status == "NAME_UNRESOLVED" and unit.reasons == ["COMMON_NOUN_SUBJECT_UNTYPED:ミラ:ESTIMATED"]


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


# ------------------------------------------------------------------ 2 and 3: direct noun types are stopped as before
@pytest.mark.parametrize("types", [("GROUP_ORG",), ("PERSON",), ("GROUP_ORG", "PERSON")])
def test_a2_2_3_a_direct_noun_type_or_a_multiple_of_noun_types_stops_as_a_typed_common_noun(types):
    explained, unit = _one(direct(*types))
    assert unit.status == "NAME_UNRESOLVED" and len(unit.reasons) == 1 and unit.reasons[0].startswith("COMMON_NOUN_SUBJECT:ソラ:PLACEMENT_DIRECT:")
    assert set(unit.reasons[0].rsplit(":", 1)[1].split(",")) == set(types)
    check = route(explained, role="implement", kind="feature")["reading"]["common_noun_check"]
    assert (check["checked"], check["not_checked"], check["flagged"]) == (0, 0, 1)         # flagged is for these two cases only (a flagged name is not also counted as checked)


# ------------------------------------------------------------------ 4: a direct type that is not a noun type passes
@pytest.mark.parametrize("types", [("P_COMMUNICATE",)])
def test_a2_4_a_direct_type_that_is_not_a_noun_type_still_passes(types):
    explained, unit = _one(direct(*types))
    assert unit.status == "MAPPED" and unit.reasons == []
    assert route(explained, role="implement", kind="feature")["agent"] == "ソラ"
    check = route(explained, role="implement", kind="feature")["reading"]["common_noun_check"]
    assert (check["checked"], check["flagged"]) == (1, 0)


# ------------------------------------------------------------------ introduced by a naming sentence, and English
def test_a2_a_name_that_a_naming_sentence_introduced_is_a_name_whatever_the_placement_says():
    lookup = Placement(ソラ=PlaceResult("UNPLACED", provenance={"fake": True}), ミラ=PlaceResult("UNPLACED", provenance={"fake": True}))
    table = {"ミラは実装をやる。": ja_do("ミラ"),
             "ミラをソラと呼ぶ。": rd("ja", cl("呼ぶ", {"patient": "ミラ", "result": "ソラ"})),
             "ソラはテストを書く。": rd("ja", cl("書く", {"agent": "ソラ", "patient": "テスト"}))}
    explained = explain("ミラは実装をやる。\nミラをソラと呼ぶ。\nソラはテストを書く。\n", table, lookup)
    statuses = [(u.status, u.reasons) for u in explained.extraction.units]
    # ミラ is not introduced (UNPLACED -> stopped now); ソラ is introduced by the naming sentence (passes)
    assert statuses[0] == ("NAME_UNRESOLVED", ["COMMON_NOUN_SUBJECT_UNTYPED:ミラ:UNPLACED"])
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


def test_a2_one_untyped_name_stops_the_whole_text_as_a_typed_common_noun_does():
    lookup = Placement(ミラ=direct("P_COMMUNICATE"), ソラ=PlaceResult("UNPLACED", provenance={"fake": True}))
    table = {"ミラは実装をやる。": ja_do("ミラ"), "ソラはテストを書く。": rd("ja", cl("書く", {"agent": "ソラ", "patient": "テスト"}))}
    explained = explain("ミラは実装をやる。\nソラはテストを書く。\n", table, lookup)
    assert [u.status for u in explained.extraction.units] == ["MAPPED", "NAME_UNRESOLVED"]
    assert route(explained, role="implement", kind="feature")["agent"] is None


# ------------------------------------------------------------------ the real placement r7 and the real reader
@pytest.mark.parametrize("sentence,noun,state", [
    ("委員会がテストを書く。", "委員会", "ESTIMATED"),
    ("レビューは外注先がやる。", "外注先", "UNPLACED"),
    ("レビューは課がやる。", "課", "UNPLACED"),
    ("開発者がテストを書く。", "開発者", "ESTIMATED"),
])
def test_a2_r7_an_estimated_or_unplaced_common_noun_is_not_routed(monkeypatch, sentence, noun, state):
    monkeypatch.setenv("VERA_PLACEMENT", R7)
    explained = rt.explain(sentence + "\n", "x.md")
    (unit,) = explained.extraction.units
    assert unit.status == "NAME_UNRESOLVED" and unit.reasons == [f"COMMON_NOUN_SUBJECT_UNTYPED:{noun}:{state}"], (sentence, unit)
    routed = rt.route_task(explained, {"role": "implement", "kind": "test_authoring", "size": "medium"})
    assert routed["agent"] is None and routed["decision"] == "undecided"
