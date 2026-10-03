"""W5-d (docs/ROUTING_FROM_TEXT.md, W5-d): a Japanese name is a name only when something says so, and a marker that is followed by a fragment of its own is
not a replacement.

R1  a Japanese name that no naming sentence introduced is stopped when the placement types it as a common noun (a direct type among the 17 noun types),
    and when there is no placement answer at all (NAME_UNVERIFIED:<name>:NO_PLACEMENT); one that the placement knows but cannot type still passes.
R2  after a replacement marker ("やっぱり", "ではなく") a fragment of its own ("そのまま、") is read by the same reader: a denied change is a maintenance (nothing is
    replaced), anything else is AMBIGUOUS_RELATION (nothing is replaced or added). No word of the fragment is looked at.

The hand-made readings and the made-up placement follow tests/test_routing_from_text_w5b.py. The tests of the older files that give a Japanese name no
placement at all fail by declared conflict K2 (docs W5-d); the intent of a few of them is written again here with a placement that does not type the name.
"""
import pytest

from verantyx import routing_from_text as rt
from verantyx.event_cross import NOUN_TYPE_IDS, PlaceResult

from test_routing_from_text_w5b import Placement, cl, direct, en_review, explain, ja_assign, ja_do, rd, route  # noqa: F401


@pytest.fixture(autouse=True)
def _no_outside_placement(monkeypatch):
    monkeypatch.delenv("VERA_PLACEMENT", raising=False)


class AllUnplaced:
    """A made-up placement that knows no word: every word is UNPLACED (a placement answer exists and says nothing about the word)."""
    id = "w5d-all-unplaced/1"

    def lookup(self, lemma):
        return PlaceResult("UNPLACED", provenance={"fake": True})


# ------------------------------------------------------------------ R1
def test_r1_a_common_noun_without_a_placement_is_not_a_name_and_the_unit_says_why():
    sent = "チームがテストを書く。"
    explained = explain(sent + "\n", {sent: rd("ja", cl("書く", {"agent": "チーム", "patient": "テスト"}))})
    (unit,) = explained.extraction.units
    assert unit.status == "NAME_UNRESOLVED" and unit.reasons == ["NAME_UNVERIFIED:チーム:NO_PLACEMENT"]
    assert not explained.records.agents and not explained.extraction.relations
    got = route(explained, role="implement", kind="test_authoring")
    assert got["agent"] is None and got["abstention"]["type"] == "INCOMPLETE_READING"
    assert got["reading"]["common_noun_check"]["not_checked"] == 1


def test_r1_the_real_reader_without_a_placement_does_not_route_a_common_noun():
    explained = rt.explain("チームがテストを書く。\n", "attack.md")
    result = rt.route_task(explained, {"role": "implement", "kind": "test_authoring", "size": "medium"})
    assert explained.extraction.units[0].status != "MAPPED" and result["agent"] is None


@pytest.mark.parametrize("noun,work", [("班", "実装"), ("担当者", "レビュー"), ("委員会", "実装"), ("部署", "テスト")])
def test_r1_other_common_nouns_without_a_placement_are_not_routed_either(noun, work):
    sent = f"{noun}は{work}をやる。"
    explained = explain(sent + "\n", {sent: ja_do(noun, work)})
    (unit,) = explained.extraction.units
    assert unit.status == "NAME_UNRESOLVED" and unit.reasons == [f"NAME_UNVERIFIED:{noun}:NO_PLACEMENT"]
    assert route(explained, role="implement", kind="feature")["agent"] is None


def test_r1_a_name_that_a_naming_sentence_introduced_passes_without_any_placement():
    table = {"ミラは実装をやる。": ja_do("ミラ"), "ミラをチームと呼ぶ。": rd("ja", cl("呼ぶ", {"patient": "ミラ", "result": "チーム"})),
             "チームはテストを書く。": rd("ja", cl("書く", {"agent": "チーム", "patient": "テスト"}))}
    # the naming sentence introduces its second name (チーム): the sentence that uses it is not stopped; the naming sentence itself is not examined
    explained = explain("ミラをチームと呼ぶ。\nチームはテストを書く。\n", {k: table[k] for k in ("ミラをチームと呼ぶ。", "チームはテストを書く。")})
    assert [u.status for u in explained.extraction.units] == ["MAPPED", "MAPPED"]
    assert route(explained, role="implement", kind="feature")["reading"]["common_noun_check"]["introduced_by_naming"] == 1
    only = explain("チームはテストを書く。\n", {"チームはテストを書く。": table["チームはテストを書く。"]})
    assert only.extraction.units[0].reasons == ["NAME_UNVERIFIED:チーム:NO_PLACEMENT"]


@pytest.mark.parametrize("answer", [PlaceResult("UNPLACED", provenance={"fake": True}), PlaceResult("UNKNOWN", provenance={"fake": True}),
                                    PlaceResult("DECIDED", "estimated", "proximity", ("GROUP_ORG",), {"fake": True})])
def test_r1_a_placed_word_that_the_placement_cannot_type_still_passes(answer):
    explained = explain("ソラは実装をやる。\n", {"ソラは実装をやる。": ja_do("ソラ")}, Placement(ソラ=answer))
    assert [u.status for u in explained.extraction.units] == ["MAPPED"]


@pytest.mark.parametrize("types", [("GROUP_ORG",), ("PERSON",), ("ARTIFACT",), ("GROUP_ORG", "PERSON"), ("P_COMMUNICATE", "PERSON")])
def test_r1_a_direct_type_among_the_noun_types_is_a_common_noun(types):
    assert all(t in NOUN_TYPE_IDS for t in types if not t.startswith("P_")) and len(NOUN_TYPE_IDS) == 17
    explained = explain("班は実装をやる。\n", {"班は実装をやる。": ja_do("班")}, Placement(班=direct(*types)))
    (unit,) = explained.extraction.units
    assert unit.status == "NAME_UNRESOLVED" and unit.reasons == ["COMMON_NOUN_SUBJECT:班:PLACEMENT_DIRECT:" + ",".join(sorted(types))]


def test_r1_a_direct_type_of_another_kind_than_a_noun_type_does_not_stop_a_name():
    explained = explain("ソラは実装をやる。\n", {"ソラは実装をやる。": ja_do("ソラ")}, Placement(ソラ=direct("P_COMMUNICATE")))
    assert [u.status for u in explained.extraction.units] == ["MAPPED"]


def test_r1_english_is_not_changed_without_a_placement():
    explained = explain("Mira reviews code.\n", {"Mira reviews code.": en_review("Mira")})
    assert [u.status for u in explained.extraction.units] == ["MAPPED"] and route(explained)["agent"] == "Mira"
    explained = explain("The crew reviews code.\n", {"The crew reviews code.": en_review("crew")})
    assert explained.extraction.units[0].reasons == ["COMMON_NOUN_SUBJECT:crew:DETERMINER:The"]


def test_r1_the_common_noun_check_keeps_its_five_keys_and_the_stop_is_counted_in_the_unit_status():
    explained = explain("班は実装をやる。\n", {"班は実装をやる。": ja_do("班")})
    got = route(explained, role="implement", kind="feature")
    assert sorted(got["reading"]["common_noun_check"]) == ["checked", "flagged", "introduced_by_naming", "lookup", "not_checked"]
    assert got["reading"]["by_status"]["NAME_UNRESOLVED"] == 1 and got["abstention"]["by_status"]["NAME_UNRESOLVED"] == 1       # the stop is counted by status
    assert explained.extraction.units[0].status == "NAME_UNRESOLVED"


# ------------------------------------------------------------------ R2
FIRST = "実装はハルに任せる。"
SECOND = "やっぱりそのまま、実装はハルに任せる。"


def _reader(table, head_reading=None):
    def read(sentence):
        if sentence in table:
            return table[sentence]
        if head_reading is not None:
            return head_reading
        raise KeyError(sentence)
    return read


def _explain_two(second, table, head_reading=None, label="追記："):
    return rt.explain(f"{FIRST}\n{label}{second}\n", "x.md", reader=_reader(table, head_reading), lookup=AllUnplaced())


def test_r2_a_marker_followed_by_a_fragment_the_reader_cannot_read_is_undetermined_not_a_replacement():
    ex = _explain_two(SECOND, {FIRST: ja_assign("ハル"), SECOND: ja_assign("ハル")}).extraction          # the reader raises on "そのまま"
    assert [u.status for u in ex.units] == ["MAPPED", "AMBIGUOUS_RELATION"]
    assert ex.units[1].reasons == ["MARKER_SCOPE_UNDETERMINED:そのまま"] and ex.units[1].override is False
    assert [r.superseded_by for r in ex.relations] == [None] and ex.auto_resolved == 0 and ex.additions_kept == 0


def test_r2_the_attack_shape_with_a_reader_that_ignores_the_sentence_never_replaces():
    # the attack's reader returns the assignment clause whatever it is given (the fragment too): an affirmative clause -> undetermined
    def reader(_sentence): return ja_assign("ハル")
    ex = rt.explain(f"{FIRST}\n追記：{SECOND}\n", "x.md", reader=reader, lookup=AllUnplaced()).extraction
    assert [u.status for u in ex.units] == ["MAPPED", "AMBIGUOUS_RELATION"]
    assert all(r.superseded_by is None for r in ex.relations) and ex.auto_resolved == 0


def test_r2_a_fragment_read_as_one_negative_clause_is_a_maintenance_the_line_adds_and_replaces_nothing():
    negative = rd("ja", cl("変える", {"patient": "それ"}, pol="-"))
    explained = _explain_two(SECOND, {FIRST: ja_assign("ハル"), SECOND: ja_assign("ハル"), "そのまま": negative})
    ex = explained.extraction
    assert [u.status for u in ex.units] == ["MAPPED", "MAPPED"]
    assert ex.units[1].reasons == ["MAINTAINED_AFTER_MARKER"] and ex.units[1].override is False
    assert [r.superseded_by for r in ex.relations] == [None, None] and ex.auto_resolved == 0 and ex.additions_kept == 1


def test_r2_a_fragment_read_as_an_affirmative_clause_is_undetermined():
    positive = rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))
    ex = _explain_two(SECOND, {FIRST: ja_assign("ハル"), SECOND: ja_assign("ハル"), "そのまま": positive}).extraction
    assert [u.status for u in ex.units] == ["MAPPED", "AMBIGUOUS_RELATION"] and ex.units[1].reasons == ["MARKER_SCOPE_UNDETERMINED:そのまま"]
    assert all(r.superseded_by is None for r in ex.relations) and ex.auto_resolved == 0


def test_r2_a_fragment_of_two_clauses_is_undetermined():
    two = rd("ja", cl("変える", {"patient": "それ"}, pol="-"), cl("任せる", {"recipient": "ハル", "patient": "実装"}))
    ex = _explain_two(SECOND, {FIRST: ja_assign("ハル"), SECOND: ja_assign("ハル"), "そのまま": two}).extraction
    assert ex.units[1].status == "AMBIGUOUS_RELATION"


@pytest.mark.parametrize("second", ["やっぱり実装はルナに任せる。", "やっぱり、実装はルナに任せる。", "実装はミラではなくルナに任せる。"])
def test_r2_a_marker_that_leads_the_clause_directly_still_replaces_japanese(second):
    first = "実装はミラに任せる。"
    explained = rt.explain(f"{first}\n追記：{second}\n", "x.md", reader=_reader({first: ja_assign("ミラ"), second: ja_assign("ルナ")}), lookup=AllUnplaced())
    assert explained.extraction.auto_resolved == 1 and route(explained, role="implement", kind="feature")["agent"] == "ルナ"
    assert explained.extraction.units[1].override is True


@pytest.mark.parametrize("sentence", ["Nico reviews code instead.", "Nico replace Mira on reviews.", "Instead, Nico reviews code."])
def test_r2_english_replacement_forms_are_unchanged(sentence):
    ex = rt.explain(f"Mira reviews code.\nAddendum: {sentence}\n", "x.md", reader=_reader({"Mira reviews code.": en_review("Mira"), sentence: en_review("Nico")})).extraction
    assert ex.auto_resolved == 1 and [r.superseded_by for r in ex.relations] == ["R002", None]


def test_r2_english_marker_followed_by_a_fragment_is_read_the_same_way():
    sentence = "Instead no change, Nico reviews code."            # the marker is followed by a fragment of its own (up to the comma)
    nochange = rd("en", cl("change", {"patient": "it"}, pol="-"))
    ex = rt.explain(f"Mira reviews code.\nAddendum: {sentence}\n", "x.md",
                    reader=_reader({"Mira reviews code.": en_review("Mira"), sentence: en_review("Nico"), "no change": nochange})).extraction
    assert ex.units[1].reasons == ["MAINTAINED_AFTER_MARKER"] and ex.auto_resolved == 0 and ex.additions_kept == 1
    ex = rt.explain(f"Mira reviews code.\nAddendum: {sentence}\n", "x.md", reader=_reader({"Mira reviews code.": en_review("Mira"), sentence: en_review("Nico")})).extraction
    assert ex.units[1].status == "AMBIGUOUS_RELATION" and ex.units[1].reasons == ["MARKER_SCOPE_UNDETERMINED:no change"]


def test_r2_the_other_labels_replace_as_before_even_with_a_fragment_after_a_marker():
    first = "実装はミラに任せる。"
    second = "やっぱりそのまま、実装はルナに任せる。"
    explained = rt.explain(f"{first}\n訂正：{second}\n", "x.md", reader=_reader({first: ja_assign("ミラ"), second: ja_assign("ルナ")}), lookup=AllUnplaced())
    assert explained.extraction.auto_resolved == 1 and explained.extraction.units[1].status == "MAPPED"


def test_r2_the_head_is_a_fragment_of_the_sentence_and_no_word_decides():
    assert rt._marker_head("やっぱりそのまま、実装はハルに任せる。") == "そのまま"
    assert rt._marker_head("やっぱり変えない、実装はハルに任せる。") == "変えない"           # a different fragment: the same shape, no list of words
    for text in ("やっぱり実装はルナに任せる。", "やっぱり、実装はルナに任せる。", "実装はミラではなくルナに任せる。", "Nico reviews code instead.", "やっぱり。"):
        assert rt._marker_head(text) is None


def test_r2_the_frozen_constants_and_the_output_shape_are_untouched():
    assert rt.REPLACEMENT_MARKERS == {"ja": frozenset({"やっぱり", "ではなく"}), "en": frozenset({"instead", "replace"})}
    assert rt.ADDITION_LABELS == {"追記", "追伸", "p.s.", "ps", "addendum"} and len(rt.CONSTANT_NAMES) == 21
    assert "marker_head" not in rt.dumps({"a": 1})
    assert rt.UNIT_STATUSES == ("MAPPED", "COMPARISON_ONLY", "UNREAD", "PREDICATE_CLASS_UNKNOWN", "WORK_TERM_UNKNOWN", "NAME_UNRESOLVED",
                                *rt.UNIT_STATUSES[6:])


# ------------------------------------------------------------------ the intent of a few older tests, with a placement that does not type the names (K2)
def test_k2_a_japanese_name_the_placement_does_not_type_is_routed():
    sent = "ミラは実装をやる。"
    explained = explain(sent + "\n", {sent: ja_do("ミラ")}, AllUnplaced())
    assert [u.status for u in explained.extraction.units] == ["MAPPED"]
    assert route(explained, role="implement", kind="feature")["agent"] == "ミラ"


def test_k2_two_japanese_addenda_without_a_marker_keep_both_statements():
    first, second = "実装はミラに任せる。", "実装はルナに任せる。"
    explained = explain(f"{first}\n追記：{second}\n", {first: ja_assign("ミラ"), second: ja_assign("ルナ")}, AllUnplaced())
    assert explained.extraction.auto_resolved == 0 and [r.superseded_by for r in explained.extraction.relations] == [None, None]
    assert route(explained, role="implement", kind="feature")["agent"] is None


def test_k2_the_other_labels_replace_as_before_without_a_marker():
    first, second = "実装はミラに任せる。", "実装はルナに任せる。"
    explained = explain(f"{first}\n訂正：{second}\n", {first: ja_assign("ミラ"), second: ja_assign("ルナ")}, AllUnplaced())
    assert explained.extraction.auto_resolved == 1 and route(explained, role="implement", kind="feature")["agent"] == "ルナ"
    assert explained.extraction.additions_kept == 0


def test_k2_a_common_noun_the_placement_types_is_still_stopped_next_to_a_routed_name():
    table = {"ミラは実装をやる。": ja_do("ミラ"), "チームがテストを書く。": rd("ja", cl("書く", {"agent": "チーム", "patient": "テスト"}))}
    lookup = Placement(チーム=direct("GROUP_ORG"), ミラ=PlaceResult("UNPLACED", provenance={"fake": True}))
    explained = explain("ミラは実装をやる。\nチームがテストを書く。\n", table, lookup)
    assert [(u.status, u.reasons) for u in explained.extraction.units] == [("MAPPED", []), ("NAME_UNRESOLVED", ["COMMON_NOUN_SUBJECT:チーム:PLACEMENT_DIRECT:GROUP_ORG"])]
    assert route(explained, role="implement", kind="feature")["abstention"]["type"] == "INCOMPLETE_READING"


def test_k2_a_naming_sentence_makes_the_new_name_usable_without_a_placement():
    sent1, sent2 = "ミラをチームと呼ぶ。", "チームは実装をやる。"
    table = {sent1: rd("ja", cl("呼ぶ", {"patient": "ミラ", "result": "チーム"})), sent2: ja_do("チーム")}
    explained = explain(f"{sent1}\n{sent2}\n", table)
    assert [u.status for u in explained.extraction.units] == ["MAPPED", "MAPPED"]


# ------------------------------------------------------------------ W5-d2 (D2-2): the parts of a parallel Japanese name are asked of the same placement
# The expectations below were written before the product change (artifacts/w5-d/r2/new_tests_frozen.sha256).
from test_routing_from_text import FakePlacement, STD, cons, explain_lines, out_of, task, with_constraints  # noqa: E402

PARALLEL = "ハルとセキは同じ会社だ。"
PARALLEL_READ = rd("ja", cl("だ", {"entity": "ハルとセキ", "value": "同じ会社"}))
PRE = {"ハルは実装をやる。": ja_do("ハル"), "セキは検証をやる。": ja_do("セキ", "検証"), PARALLEL: PARALLEL_READ}
PRE_TEXT = "ハルは実装をやる。\nセキは検証をやる。\n" + PARALLEL + "\n"


class Spy:
    """A placement that records every word it is asked and answers UNPLACED."""
    id = "w5d2-spy/1"

    def __init__(self):
        self.asked = []

    def lookup(self, lemma):
        self.asked.append(lemma)
        return PlaceResult("UNPLACED", provenance={"fake": True})


def test_w5d2_a_parallel_name_is_routed_when_the_placement_answers_for_each_part():
    explained = explain(PRE_TEXT, PRE, AllUnplaced())
    assert [u.status for u in explained.extraction.units] == ["MAPPED", "MAPPED", "MAPPED"]
    assert [(r.a, r.b, r.relation) for r in explained.records.lineage_relations] == [("ハル", "セキ", "same")]    # INDEPENDENCE (same)
    assert route(explained, role="implement", kind="feature")["agent"] == "ハル"


def test_w5d2_a_part_of_a_parallel_name_that_the_placement_types_as_a_common_noun_stops_the_unit():
    pre = {"ハルは実装をやる。": ja_do("ハル"), "チームとハルは同じ会社だ。": rd("ja", cl("だ", {"entity": "チームとハル", "value": "同じ会社"}))}
    explained = explain("ハルは実装をやる。\nチームとハルは同じ会社だ。\n", pre, Placement(チーム=direct("GROUP_ORG"), ハル=PlaceResult("UNPLACED", provenance={"fake": True})))
    (first, second) = explained.extraction.units
    assert first.status == "MAPPED"
    assert second.status == "NAME_UNRESOLVED" and second.reasons == ["COMMON_NOUN_SUBJECT:チーム:PLACEMENT_DIRECT:GROUP_ORG"]
    assert route(explained, role="implement", kind="feature")["abstention"]["type"] == "INCOMPLETE_READING"


def test_w5d2_without_a_placement_a_part_of_a_parallel_name_is_unverified_as_before(monkeypatch):
    monkeypatch.delenv("VERA_PLACEMENT", raising=False)
    explained = explain(PRE_TEXT, PRE)
    third = explained.extraction.units[2]
    assert third.status == "NAME_UNRESOLVED" and third.reasons == ["NAME_UNVERIFIED:ハル:NO_PLACEMENT"]
    assert explained.records.lineage_relations == ()


def test_w5d2_an_english_parallel_name_is_not_asked_part_by_part():
    spy = Spy()
    sent = "Mira and Nico are the same family."
    explained = explain(sent + "\n", {sent: rd("en", cl("be", {"entity": "Mira and Nico", "value": "same family"}))}, spy)
    assert explained.extraction.units[0].status in ("MAPPED", "AMBIGUOUS_RELATION", "NAME_UNRESOLVED")
    assert "Mira" not in spy.asked and "Nico" not in spy.asked          # the language of R1 is Japanese only: English names are not asked part by part


def test_w5d2_the_parts_that_are_asked_are_exactly_the_groups_of_the_parallel_split():
    spy = Spy()
    explain(PRE_TEXT, PRE, spy)
    groups = [rt._join(g, "ja") for g in rt._split_parallel("ハルとセキ", "ja")]
    assert groups == ["ハル", "セキ"]
    assert set(spy.asked) >= {"ハルとセキ"} | set(groups)
    # a filler that is not parallel ("同じ会社") has no parts to ask
    assert [w for w in spy.asked if w not in {"ハルとセキ", "ハル", "セキ", "実装", "検証", "同じ会社"}] == []


def test_w5d2_k2_the_standard_explanation_with_and_without_a_placement(monkeypatch):
    monkeypatch.delenv("VERA_PLACEMENT", raising=False)
    placed, _ = explain_lines(*STD, lookup=FakePlacement())
    assert [u.status for u in placed.extraction.units] == ["MAPPED"] * 7 + ["COMPARISON_ONLY"]
    assert [(r.a, r.b, r.relation) for r in placed.records.lineage_relations] == [("ハル", "セキ", "same")]
    got = rt.route_task(with_constraints(placed, [cons("independent", roles=["implement", "review"])]),
                        task(role="review", kind="review", already_used={"implement": ["ハル"]}))
    assert got["abstention"]["type"] == "INDEPENDENCE_VETO"            # the same decision as before W5-d: モモ vs ハル, no relation is said
    bare, _ = explain_lines(*STD)                                      # no placement at all: every name is unverified and the whole text abstains
    assert any(u.status == "NAME_UNRESOLVED" and u.reasons == ["NAME_UNVERIFIED:ハル:NO_PLACEMENT"] for u in bare.extraction.units)
    assert out_of(bare)["abstention"]["type"] == "INCOMPLETE_READING"
