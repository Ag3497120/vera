"""W5-b / W2-h2: a common noun is not an agent's name, and an addendum adds unless it says it replaces.

The attack file (tests/attack/test_attack_w2h2_routing_from_text.py) used ``The team reviews code.`` and ``Addendum: Luna reviews code.``.
These tests use other words and other labels, hand-made reading outputs (as tests/test_routing_from_text.py) and a made-up
``PlacementLookup``.  No list of nouns is in the module: the two testimonies are a determiner in the sentence and a `direct` placement.
"""
import pytest

from verantyx import routing_from_text as rt
from verantyx.event_cross import PlaceResult


def cl(pred, roles, pol="+", tense="nonpast"):
    return {"predicate": pred, "roles": roles, "polarity": pol, "tense": tense, "modality": None, "voice": "active"}


def rd(lang, *clauses):
    return {"schema": "verantyx.semantic_read/1", "lang": lang, "readable": True, "clauses": list(clauses), "relations": [],
            "abstain": None, "unsupported": [], "clause_meta": [{"rule": "test", "span": [0, 1]} for _ in clauses]}


def en_review(name):
    return rd("en", cl("review", {"agent": name, "patient": "code"}))


def ja_do(name, work="実装"):
    return rd("ja", cl("やる", {"agent": name, "patient": work}))


def ja_assign(name, work="実装"):
    return rd("ja", cl("任せる", {"recipient": name, "patient": work}))


def explain(text, table, lookup=None):
    return rt.explain(text, "x.md", reader=lambda s: table[s], lookup=lookup)


def route(explained, role="review", kind="review"):
    return rt.route_task(explained, {"role": role, "kind": kind, "size": "medium"})


class Placement:
    """A made-up placement: word -> PlaceResult; any other word is UNKNOWN (a placement that does not know it)."""
    id = "w5b-fake-placement/1"

    def __init__(self, **by_word):
        self.by_word = by_word

    def lookup(self, lemma):
        return self.by_word.get(lemma, PlaceResult("UNKNOWN", provenance={"reason": "NOT_IN_FAKE"}))


def direct(*types):
    return PlaceResult("DECIDED" if len(types) == 1 else "MULTIPLE", "direct", None, tuple(types), {"fake": True})


# ------------------------------------------------------------------ A01 (a): a determiner before the name, in the sentence as written
@pytest.mark.parametrize("sentence,name,det", [
    ("The crew reviews code.", "crew", "The"),
    ("A squad reviews code.", "squad", "A"),
    ("An engineer reviews code.", "engineer", "An"),
    ("This group reviews code.", "group", "This"),
    ("Our staff reviews code.", "staff", "Our"),
])
def test_a_determiner_before_the_name_makes_it_a_description_not_a_name(sentence, name, det):
    explained = explain(sentence + "\n", {sentence: en_review(name)})
    (unit,) = explained.extraction.units
    assert unit.status == "NAME_UNRESOLVED" and unit.reasons == [f"COMMON_NOUN_SUBJECT:{name}:DETERMINER:{det}"]
    assert not explained.records.agents and not explained.extraction.relations        # no record is made
    got = route(explained)
    assert got["decision"] == "undecided" and got["agent"] is None and got["abstention"]["type"] == "INCOMPLETE_READING"


def test_a_name_without_a_determiner_is_read_as_before_and_one_common_noun_stops_the_whole_text():
    ok = {"Mira reviews code.": en_review("Mira")}
    explained = explain("Mira reviews code.\n", ok)
    assert [u.status for u in explained.extraction.units] == ["MAPPED"] and route(explained)["agent"] == "Mira"
    both = {**ok, "The crew reviews code.": en_review("crew")}
    explained = explain("Mira reviews code.\nThe crew reviews code.\n", both)
    assert [u.status for u in explained.extraction.units] == ["MAPPED", "NAME_UNRESOLVED"]
    assert route(explained)["agent"] is None


def test_the_determiner_test_looks_at_the_name_the_relation_uses_not_at_every_word():
    # "the" stands before "code", which is the work, not the name
    explained = explain("Mira reviews the code.\n", {"Mira reviews the code.": en_review("Mira")})
    assert [u.status for u in explained.extraction.units] == ["MAPPED"]


def test_the_determiner_test_is_for_english_only_and_not_for_a_naming_sentence():
    explained = explain("ミラは実装をやる。\n", {"ミラは実装をやる。": ja_do("ミラ")})
    assert [u.status for u in explained.extraction.units] == ["MAPPED"]
    alias = rd("en", cl("call", {"patient": "Mira", "result": "Crew"}))
    sent = "Call Mira the Crew."
    ex = explain(f"Mira reviews code.\n{sent}\n", {"Mira reviews code.": en_review("Mira"), sent: alias})
    assert [u.status for u in ex.extraction.units] == ["MAPPED", "MAPPED"]


# ------------------------------------------------------------------ A01 (b): the placement says the word itself is typed
def test_a_word_the_placement_types_directly_is_not_an_agent_name_and_the_check_is_counted():
    lookup = Placement(チーム=direct("GROUP_ORG"))
    table = {"チームがテストを書く。": rd("ja", cl("書く", {"agent": "チーム", "patient": "テスト"})),
             "ミラは実装をやる。": ja_do("ミラ")}
    explained = explain("ミラは実装をやる。\nチームがテストを書く。\n", table, lookup)
    statuses = [(u.status, u.reasons) for u in explained.extraction.units]
    assert statuses[0] == ("MAPPED", []) and statuses[1] == ("NAME_UNRESOLVED", ["COMMON_NOUN_SUBJECT:チーム:PLACEMENT_DIRECT:GROUP_ORG"])
    got = route(explained, role="implement", kind="feature")
    assert got["abstention"]["type"] == "INCOMPLETE_READING"
    assert got["reading"]["common_noun_check"] == {"lookup": "w5b-fake-placement/1", "checked": 1, "not_checked": 0, "flagged": 1,
                                                   "introduced_by_naming": 0}


def test_a_word_introduced_by_a_naming_sentence_is_a_name_even_when_the_placement_types_it():
    lookup = Placement(チーム=direct("GROUP_ORG"))
    table = {"ミラは実装をやる。": ja_do("ミラ"),
             "ミラをチームと呼ぶ。": rd("ja", cl("呼ぶ", {"patient": "ミラ", "result": "チーム"})),
             "チームはテストを書く。": rd("ja", cl("書く", {"agent": "チーム", "patient": "テスト"}))}
    explained = explain("ミラは実装をやる。\nミラをチームと呼ぶ。\nチームはテストを書く。\n", table, lookup)
    assert [u.status for u in explained.extraction.units] == ["MAPPED", "MAPPED", "MAPPED"]
    assert route(explained, role="implement", kind="feature")["reading"]["common_noun_check"]["introduced_by_naming"] == 1
    # the same sentence without the naming one is stopped
    only = explain("チームはテストを書く。\n", {"チームはテストを書く。": table["チームはテストを書く。"]}, lookup)
    assert only.extraction.units[0].status == "NAME_UNRESOLVED"


@pytest.mark.parametrize("answer", [
    PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True}),      # a construction is not a testimony
    PlaceResult("UNPLACED", provenance={"fake": True}),
    PlaceResult("UNKNOWN", provenance={"fake": True}),
])
def test_an_estimated_unplaced_or_unknown_word_is_not_a_reason_to_stop(answer):
    lookup = Placement(ソラ=answer)
    explained = explain("ソラは実装をやる。\n", {"ソラは実装をやる。": ja_do("ソラ")}, lookup)
    assert [u.status for u in explained.extraction.units] == ["MAPPED"]
    assert route(explained, role="implement", kind="feature")["reading"]["common_noun_check"]["checked"] == 1


def test_without_a_placement_nothing_is_checked_and_that_is_counted_not_hidden():
    explained = explain("ソラは実装をやる。\n", {"ソラは実装をやる。": ja_do("ソラ")})
    assert [u.status for u in explained.extraction.units] == ["MAPPED"]
    check = route(explained, role="implement", kind="feature")["reading"]["common_noun_check"]
    assert check == {"lookup": "stub-no-placement/1", "checked": 0, "not_checked": 1, "flagged": 0, "introduced_by_naming": 0}


def test_two_typed_answers_that_disagree_still_mark_a_common_noun():
    lookup = Placement(班=direct("GROUP_ORG", "PERSON"))
    explained = explain("班は実装をやる。\n", {"班は実装をやる。": ja_do("班")}, lookup)
    (unit,) = explained.extraction.units
    assert unit.status == "NAME_UNRESOLVED" and unit.reasons[0].startswith("COMMON_NOUN_SUBJECT:班:PLACEMENT_DIRECT:")


# ------------------------------------------------------------------ A02: an addendum adds unless it says it replaces
FIRST_EN, SECOND_EN = "Mira reviews code.", "Nico reviews code."


@pytest.mark.parametrize("label", ["Addendum:", "P.S.", "ps:", "PS "])
def test_an_english_addendum_without_a_marker_keeps_both_statements_and_routes_nobody(label):
    text = f"{FIRST_EN}\n{label} {SECOND_EN}\n"
    explained = explain(text, {FIRST_EN: en_review("Mira"), SECOND_EN: en_review("Nico")})
    assert explained.extraction.auto_resolved == 0
    assert [r.superseded_by for r in explained.extraction.relations] == [None, None]
    assert [u.override for u in explained.extraction.units] == [False, False]
    got = route(explained)
    assert got["agent"] is None and got["decision"] == "undecided"                       # two suited agents are a tie, not a winner
    assert got["reading"]["addition_labels_kept_as_addition"] == 1


@pytest.mark.parametrize("label", ["追記：", "追伸：", "追記（翌日）："])
def test_a_japanese_addendum_without_a_marker_keeps_both_statements(label):
    first, second = "実装はミラに任せる。", "実装はルナに任せる。"
    explained = explain(f"{first}\n{label}{second}\n", {first: ja_assign("ミラ"), second: ja_assign("ルナ")})
    assert explained.extraction.auto_resolved == 0 and [r.superseded_by for r in explained.extraction.relations] == [None, None]
    assert route(explained, role="implement", kind="feature")["agent"] is None


@pytest.mark.parametrize("sentence", ["Nico reviews code instead.", "Nico replace Mira on reviews.", "Instead, Nico reviews code."])
def test_an_english_addendum_with_a_replacement_word_replaces(sentence):
    reading = en_review("Nico")
    explained = explain(f"{FIRST_EN}\nAddendum: {sentence}\n", {FIRST_EN: en_review("Mira"), sentence: reading})
    assert explained.extraction.auto_resolved == 1
    assert [r.superseded_by for r in explained.extraction.relations] == ["R002", None]
    assert route(explained)["agent"] == "Nico" and route(explained)["reading"]["addition_labels_kept_as_addition"] == 0


@pytest.mark.parametrize("second,reading_name", [("やっぱり実装はルナに任せる。", "ルナ"), ("実装はミラではなくルナに任せる。", "ルナ")])
def test_a_japanese_addendum_with_a_replacement_word_replaces(second, reading_name):
    first = "実装はミラに任せる。"
    explained = explain(f"{first}\n追記：{second}\n", {first: ja_assign("ミラ"), second: ja_assign(reading_name)})
    assert explained.extraction.auto_resolved == 1
    assert route(explained, role="implement", kind="feature")["agent"] == "ルナ"


@pytest.mark.parametrize("label,sentence", [("訂正：", "実装はルナに任せる。"), ("更新：", "実装はルナに任せる。")])
def test_the_other_labels_replace_as_before_without_any_marker(label, sentence):
    first = "実装はミラに任せる。"
    explained = explain(f"{first}\n{label}{sentence}\n", {first: ja_assign("ミラ"), sentence: ja_assign("ルナ")})
    assert explained.extraction.auto_resolved == 1 and route(explained, role="implement", kind="feature")["agent"] == "ルナ"
    assert explained.extraction.additions_kept == 0


def test_update_in_english_replaces_as_before():
    explained = explain(f"{FIRST_EN}\nUpdate: {SECOND_EN}\n", {FIRST_EN: en_review("Mira"), SECOND_EN: en_review("Nico")})
    assert explained.extraction.auto_resolved == 1 and route(explained)["agent"] == "Nico"


def test_the_marker_is_looked_for_in_the_sentence_that_is_replacing_not_in_the_line_before():
    # the first sentence of the line has no marker (an addition); the second says "instead" (a replacement)
    s1, s2 = "Nico reviews code.", "Ravi reviews code instead."
    explained = explain(f"{FIRST_EN}\nAddendum: {s1} {s2}\n", {FIRST_EN: en_review("Mira"), s1: en_review("Nico"), s2: en_review("Ravi")})
    assert [u.override for u in explained.extraction.units] == [False, False, True]
    assert explained.extraction.additions_kept == 1


def test_the_new_constants_are_the_tables_the_docs_list():
    assert rt.ADDITION_LABELS <= rt.OVERRIDE_MARKERS                          # an addition label is an override label
    assert rt.ADDITION_LABELS == {"追記", "追伸", "p.s.", "ps", "addendum"}
    assert rt.REPLACEMENT_MARKERS == {"ja": {"やっぱり", "ではなく"}, "en": {"instead", "replace"}}
    assert "ADDITION_LABELS" in rt.CONSTANT_NAMES and "REPLACEMENT_MARKERS" in rt.CONSTANT_NAMES


# ------------------------------------------------------------------ round 4 (auditor ruling C3): the same three inputs without a replacement marker
# tests/test_routing_from_text.py holds the three tests with a marker ("やっぱり"); these are the same inputs without it.  An addendum adds: both
# statements stay in the record, and a pair of statements about the same work is left to the router's tie handling (which abstains).
def _units(explained):
    return [u.status for u in explained.extraction.units]


def test_C3_without_a_marker_relation_override_replaces_exactly_the_same_scope_and_counts_it_both_statements_stand():
    table = {"実装はハルに任せる。": ja_assign("ハル"), "実装はルナに任せる。": ja_assign("ルナ")}
    explained = explain("実装はハルに任せる。\n追記：実装はルナに任せる。\n", table)
    assert _units(explained) == ["MAPPED", "MAPPED"]
    assert explained.extraction.auto_resolved == 0
    assert [r.superseded_by for r in explained.extraction.relations] == [None, None]
    assert [r.preference for r in explained.records.rules] == [("ハル",), ("ルナ",)]
    result = route(explained, role="implement", kind="feature")
    assert result["agent"] is None
    assert result["abstention"]["type"] == "RECORD_REFUSED" and result["abstention"]["detail"] == "DUPLICATE_FALLBACK"


def test_C3_without_a_marker_relation_override_that_overlaps_only_partly_is_held_as_ambiguous_both_declarations_stand():
    table = {"大きなリファクタリングはハルに任せる。": ja_assign("ハル", "大きなリファクタリング"),
             "実装はルナに任せる。": ja_assign("ルナ")}
    explained = explain("大きなリファクタリングはハルに任せる。\n追記：実装はルナに任せる。\n", table)
    assert _units(explained) == ["MAPPED", "MAPPED"]
    assert explained.extraction.auto_resolved == 0
    assert route(explained, role="implement", kind="feature")["agent"] == "ルナ"        # the two declarations have different scopes: both stay


def test_C3_without_a_marker_an_override_of_another_kind_about_another_name_is_held_not_a_replacement_both_statements_stand():
    table = {"ハルはテストを書く。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"})),
             "モモはテストを書かない。": rd("ja", cl("書く", {"agent": "モモ", "patient": "テスト"}, "-")),
             "ハルはテストを書かない。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}, "-"))}
    # another name, another kind: with no marker the addendum is added next to the earlier statement
    explained = explain("ハルはテストを書く。\n追記：モモはテストを書かない。\n", table)
    assert _units(explained) == ["MAPPED", "MAPPED"] and explained.extraction.auto_resolved == 0
    assert route(explained, role="implement", kind="test_authoring")["agent"] == "ハル"
    # the same name, the opposite polarity: a contradiction that stays a contradiction (nothing is replaced, nothing is chosen)
    explained = explain("ハルはテストを書く。\n追記：ハルはテストを書かない。\n", table)
    units = explained.extraction.units
    assert [u.status for u in units] == ["CONTRADICTION", "CONTRADICTION"]
    assert [u.reasons[0] for u in units] == ["CONTRADICTS:R002", "CONTRADICTS:R001"]
    assert route(explained, role="implement", kind="test_authoring")["abstention"]["type"] == "INCOMPLETE_READING"
