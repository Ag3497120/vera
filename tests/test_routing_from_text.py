"""W2-h2: routing from a free-text explanation.  Unit tests with HAND-MADE reading outputs (the schema of docs/READING_CONVENTIONS.md),
so that the extraction, the mapping to records, the gate, the router call and the constraints are fixed whatever the reader covers.
The real reader is exercised by tests/test_routing_from_text_entry.py and the data tests."""
import dataclasses
import itertools
import json
import os
import re as _re_for_the_test_only   # the test, not the module, may read the module's source with a pattern
import unicodedata

import pytest

from verantyx import agent_routing as ar
from verantyx import routing_from_text as rt
from verantyx.event_cross import attach_events

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# --------------------------------------------------------------------------------------------------------------------------------
# hand-made reading outputs
# --------------------------------------------------------------------------------------------------------------------------------
def cl(pred, roles, pol="+", mod=None, voice="active", **extra):
    clause = {"predicate": pred, "roles": roles, "polarity": pol, "tense": "nonpast", "modality": mod, "voice": voice}
    clause.update(extra)
    return clause


def rd(lang, *clauses, relations=()):
    return {"schema": "verantyx.semantic_read/1", "lang": lang, "readable": True, "clauses": list(clauses),
            "relations": list(relations), "abstain": None, "unsupported": [],
            "clause_meta": [{"rule": "test", "span": [0, 1]} for _ in clauses]}


def no(lang, reason="NO_SUPPORTED_CLAUSE"):
    return {"schema": "verantyx.semantic_read/1", "lang": lang, "readable": False, "clauses": [], "relations": [],
            "abstain": {"kind": "not_supported", "reasons": [reason]}, "unsupported": [], "clause_meta": []}


def do(name, work, pol="+", **kw):            # "<name> does <work>" (やる)
    return rd("ja", cl("やる", {"agent": name, "patient": work}, pol, **kw))


def task(role="implement", kind="feature", size="medium", **extra):
    out = {"role": role, "kind": kind, "size": size}
    out.update(extra)
    return out


def explain_lines(*pairs, source="x.md"):
    """pairs: (sentence, reading).  The text is the sentences, one per line."""
    table = {sentence: reading for sentence, reading in pairs}
    text = "\n".join(sentence for sentence, _ in pairs) + "\n"
    return rt.explain(text, source, reader=lambda s: table[s]), text


def out_of(explained, **kw):
    return rt.route_task(explained, task(**kw))


# A standard hand-made explanation: three agents, a lineage statement, one comparison-only sentence.
STD = (
    ("ハルは実装をやる。", do("ハル", "実装")),
    ("モモがテストを書く。", rd("ja", cl("書く", {"agent": "モモ", "patient": "テスト"}))),
    ("セキがコードを確かめる。", rd("ja", cl("確かめる", {"agent": "セキ", "patient": "コード"}))),
    ("モモは検証をやらない。", do("モモ", "検証", "-")),
    ("レビューはモモがやる。", do("モモ", "レビュー")),
    ("ハルが攻撃をやる。", do("ハル", "攻撃")),
    ("ハルとセキは同じ会社だ。", rd("ja", cl("だ", {"entity": "ハルとセキ", "value": "同じ会社"}))),
    ("モモはハルより速い。", rd("ja", cl("速い", {"entity": "モモ", "standard": "ハル"}, comparison="comparative"))),
)


@pytest.fixture(scope="module")
def std():
    return explain_lines(*STD)[0]


def agent_ids(explained):
    return sorted(a.id for a in explained.records.agents)


# --------------------------------------------------------------------------------------------------------------------------------
# segment
# --------------------------------------------------------------------------------------------------------------------------------
def test_T1_segment_lines_sentence_ends_markers_and_markup():
    text = ("- ハルは実装をやる。モモは検証をやらない。\n\n---\n|---|---|\n| a | b |\n1. 番号つき\n# 見出し\n"
            "追記（翌日）：やっぱり変える。さらに変える。\nP.S. 追伸です。\nUpdate: Vale is now. Done\n追記は誰かが書く。\nVersion 5.5 is out.\n")
    units, skipped = rt.segment_with_counts(text)
    assert [u.text for u in units] == ["ハルは実装をやる。", "モモは検証をやらない。", "| a | b |", "番号つき", "見出し",
                                       "やっぱり変える。", "さらに変える。", "追伸です。", "Vale is now.", "Done",
                                       "追記は誰かが書く。", "Version 5.5 is out."]
    assert [u.marker for u in units][:5] == ["-", "-", "|", "1.", "#"]
    assert [u.override for u in units] == [False] * 5 + [True, True, True, True, True, False, False]
    assert skipped == 4            # the blank line, ---, the separator row and the final empty line
    assert [u.index for u in units] == list(range(len(units)))
    for unit in units:
        assert unit.witness in text and unit.witness == unit.witness.strip()
    assert units[0].witness == "- ハルは実装をやる。" and units[1].witness == "モモは検証をやらない。"
    assert units[5].line == 8 and units[11].line == 12


def test_T1_override_label_is_a_whole_word_never_a_part_of_one():
    for line in ("追記があります。", "Updated: it changed.", "updates: no."):
        (unit,) = rt.segment(line)
        assert unit.override is False
    (unit,) = rt.segment("追記：変える。")
    assert unit.override is True and unit.text == "変える。"


def test_T1_empty_and_markup_only_texts_make_no_unit():
    assert rt.segment("") == [] and rt.segment("\n\n---\n|---|\n") == []


# --------------------------------------------------------------------------------------------------------------------------------
# relations
# --------------------------------------------------------------------------------------------------------------------------------
def kinds_of(explained):
    return [(r.kind, r.names, r.work) for r in explained.extraction.relations if not r.held]


def test_relation_suitability_assign_recipient_and_perform_agent_and_role_verb(std):
    explained, _ = explain_lines(("実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))),
                                 ("モモがコードを読む。", rd("ja", cl("読む", {"agent": "モモ", "patient": "コード"}))))
    assert kinds_of(explained) == [("SUITABILITY", ("ハル",), {"role": "implement"}),
                                   ("SUITABILITY", ("モモ",), {"role": "read"})]
    assert [r.fallback for r in explained.records.rules] == [True, True]      # an unconditional assignment is the role's fallback
    assert out_of(explained)["agent"] == "ハル" and out_of(explained, role="read", kind="read_large_file")["agent"] == "モモ"


def test_relation_prohibition_by_polarity_and_by_modality(std):
    for kw in ({"pol": "-"}, {"pol": "+", "mod": "prohibition"}):
        explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                     ("モモは検証をやってはいけない。", do("モモ", "検証", **kw)))
        assert [(r.kind, r.names) for r in explained.extraction.relations] == [("SUITABILITY", ("ハル",)), ("PROHIBITION", ("モモ",))]
        assert explained.records.constraints[0]["kind"] == "prohibit"
        assert len(explained.records.rules) == 1       # a prohibition is not a record


def test_relation_comparison_keeps_one_agent_only_and_comparison_only_does_not_stop(std):
    explained, _ = explain_lines(("モモはハルより検証に向く。",
                                  rd("ja", cl("向く", {"entity": "モモ", "goal": "検証", "standard": "ハル"}, comparison="comparative"))),
                                 ("ハルは実装をやる。", do("ハル", "実装")))
    (rule,) = [r for r in explained.records.rules if r.role == "verify"]
    assert rule.preference == ("モモ",)                # not (モモ, ハル): "ハルでもよい" was not said
    assert explained.extraction.units[0].status == "MAPPED"
    assert [u.status for u in std.extraction.units][-1] == "COMPARISON_ONLY"
    assert std.abstention is None                       # a comparison of two names that routes nothing does not stop the gate


def test_relation_condition_from_a_size_word_and_head_by_concatenation():
    explained, _ = explain_lines(("大きなリファクタリングはクイルに任せる。",
                                  rd("ja", cl("任せる", {"recipient": "クイル", "patient": "大きなリファクタリング"}))),
                                 ("実装はルナに任せる。", rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))))
    rule = next(r for r in explained.records.rules if r.preference == ("クイル",))
    assert {(c.field, c.value) for c in rule.conditions} == {("kind", "large_refactor"), ("size", "large")} and not rule.fallback
    assert out_of(explained, kind="large_refactor", size="large")["agent"] == "クイル"
    assert out_of(explained, kind="feature", size="small")["agent"] == "ルナ"


def test_relation_independence_same_negated_distinct_and_a_different_phrase_is_held_as_ambiguous():
    same, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")), ("セキは検証をやる。", do("セキ", "検証")),
                            ("ハルとセキは同じ会社だ。", rd("ja", cl("だ", {"entity": "ハルとセキ", "value": "同じ会社"}))))
    assert [(r.a, r.b, r.relation) for r in same.records.lineage_relations] == [("ハル", "セキ", "same")]
    en, _ = explain_lines(("Rook does the review.", rd("en", cl("do", {"agent": "Rook", "patient": "review"}))),
                          ("Lark reviews the code.", rd("en", cl("review", {"agent": "Lark", "patient": "code"}))),
                          ("Rook and Lark are not the same family.",
                           rd("en", cl("be", {"entity": "Rook and Lark", "value": "same family"}, "-"))))
    assert [(r.a, r.b, r.relation) for r in en.records.lineage_relations] == [("Rook", "Lark", "distinct")]
    amb, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                           ("ハルとセキは別の会社だ。", rd("ja", cl("だ", {"entity": "ハルとセキ", "value": "別の会社"}))))
    assert amb.extraction.units[1].status == "AMBIGUOUS_RELATION" and amb.records.lineage_relations == ()
    held = [r for r in rt.route_task(amb, task())["relations"] if r["held"]]
    assert len(held) == 2 and {h["data"]["reading"] for h in held} == {"EACH_OTHER_DIFFERENT", "BOTH_DIFFERENT_FROM_A_THIRD"}
    assert out_of(amb)["abstention"]["type"] == "INCOMPLETE_READING"


def test_relation_roles_independence_is_the_routers_default_r3_and_makes_no_record():
    explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                 ("作った者と確かめる者は別の会社だ。",
                                  rd("ja", cl("だ", {"entity": "作った者と確かめる者", "value": "別の会社"}))))
    (rel,) = [r for r in explained.extraction.relations if r.kind == "INDEPENDENCE"]
    assert rel.represented_by == "ROUTER_DEFAULT_R3" and explained.records.lineage_relations == ()
    assert explained.records.constraints == () and explained.extraction.units[1].status == "MAPPED"


def test_relation_quantity_sets_concurrency_and_other_quantifier_forms_stop():
    explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                 ("ハルは同時に二つまで動かす。",
                                  rd("ja", cl("動かす", {"agent": "ハル"}, quantifiers={"event": "at_most:2"}))))
    assert explained.records.agents[0].concurrency == 2
    assert out_of(explained, running={"ハル": 2})["undecided_reason"] == "ALL_EXCLUDED"
    assert out_of(explained, running={"ハル": 1})["agent"] == "ハル"
    bad, _ = explain_lines(("ハルは全部動かす。", rd("ja", cl("動かす", {"agent": "ハル"}, quantifiers={"event": "universal"}))))
    assert bad.extraction.units[0].status == "UNREPRESENTABLE"


def two_rules_and_a_precedence(prefer_arms):
    return explain_lines(
        ("実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))),
        ("大きな修正はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな修正"}))),
        ("大きな修正はルナに任せる。", rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "大きな修正"}))),
        ("ルナをハルより優先する。", rd("ja", cl("優先する", prefer_arms))),
    )[0]


def test_relation_precedence_maps_to_one_pair_of_rules_and_resolves_the_tie():
    # two non-fallback rules with the same conditions and different agents tie; the human's precedence decides between them
    explained = two_rules_and_a_precedence({"patient": "ルナ", "standard": "ハル"})
    assert explained.extraction.units[3].status == "MAPPED" and len(explained.records.precedence) == 1
    got = out_of(explained, kind="small_fix", size="large")
    assert got["decision"] == "route" and got["agent"] == "ルナ" and got["decided_by"] == "precedence"
    assert got["basis_kind"] == "precedence"


def test_relation_precedence_that_cannot_be_written_as_one_pair_is_held_as_ambiguous():
    assert two_rules_and_a_precedence({"patient": "ルナ"}).extraction.units[3].status == "AMBIGUOUS_RELATION"
    lone, _ = explain_lines(("大きな修正はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな修正"}))),
                            ("実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))),
                            ("ルナをハルより優先する。", rd("ja", cl("優先する", {"patient": "ルナ", "standard": "ハル"}))))
    assert lone.extraction.units[2].status == "AMBIGUOUS_RELATION" and lone.records.precedence == ()


OV = (("実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))),
      ("大きな修正はクイルに任せる。", rd("ja", cl("任せる", {"recipient": "クイル", "patient": "大きな修正"}))),
      ("実装はクイルに任せる。", rd("ja", cl("任せる", {"recipient": "クイル", "patient": "実装"}))))


def test_relation_override_replaces_exactly_the_same_scope_and_counts_it():
    text = "実装はハルに任せる。\n追記：実装はルナに任せる。\n"
    table = {"実装はハルに任せる。": OV[0][1], "実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    explained = rt.explain(text, "x.md", reader=lambda s: table[s])
    assert explained.extraction.auto_resolved == 1
    assert [r.superseded_by for r in explained.extraction.relations] == ["R002", None]
    assert [r.preference for r in explained.records.rules] == [("ルナ",)]
    result = rt.route_task(explained, task())
    assert result["agent"] == "ルナ" and result["reading"]["auto_resolved"] == 1
    assert [r["superseded_by"] for r in result["relations"]] == ["R002", None]      # the replaced relation is kept and says by what


def test_relation_override_that_overlaps_only_partly_is_held_as_ambiguous():
    table = {"大きな実装はハルに任せる。": rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな実装"})),
             "実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    # "大きな実装" is a size word before a head that is not a kind: the first sentence stops, so use a kind head instead
    table = {"大きなリファクタリングはハルに任せる。": rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きなリファクタリング"})),
             "実装はルナに任せる。": rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))}
    text = "大きなリファクタリングはハルに任せる。\n追記：実装はルナに任せる。\n"
    explained = rt.explain(text, "x.md", reader=lambda s: table[s])
    assert explained.extraction.units[1].status == "AMBIGUOUS_RELATION" and explained.extraction.auto_resolved == 0
    assert out_of(explained)["abstention"]["type"] == "INCOMPLETE_READING"


def test_relation_alias_returns_the_first_name_and_task_names_are_mapped_to_it():
    # another name comes from a CALL sentence only (a copula "X is Y" with two names is held as ambiguous: see the M1 tests below)
    explained, _ = explain_lines(("ルナは実装をやる。", do("ルナ", "実装")),
                                 ("ルナをクイルと呼ぶ。", rd("ja", cl("呼ぶ", {"patient": "ルナ", "result": "クイル"}))),
                                 ("ソラがコードを確かめる。", rd("ja", cl("確かめる", {"agent": "ソラ", "patient": "コード"}))))
    assert [{"canonical": g["canonical"], "aliases": g["aliases"]} for g in explained.records.aliases] == [{"canonical": "ルナ", "aliases": ["クイル"]}]
    got = rt.route_task(explained, task(role="implement", running={"クイル": 1}))
    # the alias in the task is read as the first name (ルナ, who declares no concurrency and is busy): not TASK_NAME_UNKNOWN
    assert got["agent"] is None and got["undecided_reason"] == "ALL_EXCLUDED" and got["abstention"] is None
    assert out_of(explained)["agent"] == "ルナ"


def test_relation_alias_first_called_is_by_the_order_of_the_explanation_not_by_the_alias_direction():
    explained, _ = explain_lines(("クイルは実装をやる。", do("クイル", "実装")),
                                 ("クイルをルナと呼ぶ。", rd("ja", cl("呼ぶ", {"patient": "クイル", "result": "ルナ"}))))
    assert out_of(explained)["agent"] == "クイル" and agent_ids(explained) == ["クイル"]
    explained, _ = explain_lines(("クイルは実装をやる。", do("クイル", "実装")),
                                 ("ルナをクイルと呼ぶ。", rd("ja", cl("呼ぶ", {"patient": "ルナ", "result": "クイル"}))))
    assert out_of(explained)["agent"] == "クイル" and agent_ids(explained) == ["クイル"]


def test_M1_a_copula_between_two_names_is_ambiguous_and_makes_no_alias_and_no_merge():
    for left, right in (("ハル", "東社"), ("クイル", "ルナ")):
        explained, _ = explain_lines((f"{left}は実装をやる。", do(left, "実装")),
                                     (f"{left}は{right}だ。", rd("ja", cl("だ", {"entity": left, "value": right}))))
        unit = explained.extraction.units[1]
        assert unit.status == "AMBIGUOUS_RELATION" and unit.reasons == ["COPULA_ALIAS_OR_PREDICATION"]
        assert explained.records.aliases == ()
        got = out_of(explained)
        assert got["decision"] == "undecided" and got["abstention"]["type"] == "INCOMPLETE_READING" and got["router"] is None
        held = [r for r in got["relations"] if r["held"]]
        assert {h["data"]["reading"] for h in held} == {"COPULA_IS_ANOTHER_NAME", "COPULA_IS_A_PREDICATE_OF_THE_FIRST"}
    # two agents that "are" the same third name stay two agents: nobody is routed on the strength of a merge
    explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                 ("セキはレビューをやる。", do("セキ", "レビュー")),
                                 ("ハルは東社だ。", rd("ja", cl("だ", {"entity": "ハル", "value": "東社"}))),
                                 ("セキは東社だ。", rd("ja", cl("だ", {"entity": "セキ", "value": "東社"}))))
    assert agent_ids(explained) == ["セキ", "ハル"] and explained.records.aliases == ()
    for job in (task(), task(role="review", kind="review")):
        assert rt.route_task(explained, job)["decision"] == "undecided"


def test_M2_an_english_name_of_more_than_one_word_is_not_a_name():
    for filler in ("Rook usually", "Rook sometimes", "Rook always", "Big Rook", "Rook Two"):
        explained, _ = explain_lines((f"{filler} reviews the code.", rd("en", cl("review", {"agent": filler, "patient": "code"}))),
                                     ("Rook writes tests.", rd("en", cl("write", {"agent": "Rook", "patient": "tests"}))))
        unit = explained.extraction.units[0]
        assert unit.status == "NAME_UNRESOLVED" and unit.reasons == [f"MULTI_WORD_NAME:{filler}"]
        assert agent_ids(explained) == ["Rook"]                       # no agent called "Rook usually"
        got = out_of(explained, role="review", kind="review")
        assert got["decision"] == "undecided" and got["agent"] is None and got["abstention"]["type"] == "INCOMPLETE_READING"
    explained, _ = explain_lines(("Rook and Lark are not the same family.",
                                  rd("en", cl("be", {"entity": "Rook and Lark", "value": "same family"}, "-"))))
    assert explained.extraction.units[0].status == "MAPPED"          # a parallel of single words is still read


@pytest.mark.parametrize("tense", ["past", None, "future"])
def test_M3_a_centre_that_is_not_non_past_is_not_an_assignment(tense):
    reading = rd("ja", {**cl("やる", {"agent": "ハル", "patient": "実装"}), "tense": tense})
    explained, _ = explain_lines(("ハルが実装をやった。", reading))
    unit = explained.extraction.units[0]
    assert unit.status == "UNREPRESENTABLE" and unit.reasons == [f"TENSE:{tense}"]
    assert explained.records.agents == () and out_of(explained)["decision"] == "undecided"


def test_M3_a_nonpast_centre_is_read_and_a_reading_without_a_tense_is_rejected_by_the_cross_as_unread():
    explained, _ = explain_lines(("ハルが実装をやる。", do("ハル", "実装")))
    assert explained.extraction.units[0].status == "MAPPED"
    clause = cl("やる", {"agent": "ハル", "patient": "実装"})
    del clause["tense"]
    explained, _ = explain_lines(("ハルが実装をやる。", rd("ja", clause)))
    assert explained.extraction.units[0].status == "UNREAD"       # the cross requires the key (INPUT_REJECTED): never a silent default


def test_D13_an_override_of_another_kind_about_another_name_is_held_not_a_replacement():
    ov, text = explain_lines(("ハルはテストを書く。", rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}))),
                             ("セキもテストを書く。", rd("ja", cl("書く", {"agent": "セキ", "patient": "テスト"}))))
    # the same kind (A does it -> B does it) replaces; a different kind and a different name (A does it -> B does not) is held
    table = {"ハルはテストを書く。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"})),
             "モモはテストを書かない。": rd("ja", cl("書く", {"agent": "モモ", "patient": "テスト"}, "-"))}
    explained = rt.explain("ハルはテストを書く。\n追記：モモはテストを書かない。\n", "x.md", reader=lambda sentence: table[sentence])
    unit = explained.extraction.units[1]
    assert unit.status == "AMBIGUOUS_RELATION" and unit.reasons[0].startswith("OVERRIDE_OTHER_KIND_AND_NAME:")
    assert explained.extraction.auto_resolved == 0 and out_of(explained, kind="test_authoring")["abstention"]["type"] == "INCOMPLETE_READING"
    same_name = {"ハルはテストを書く。": table["ハルはテストを書く。"],
                 "ハルはテストを書かない。": rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}, "-"))}
    explained = rt.explain("ハルはテストを書く。\n追記：ハルはテストを書かない。\n", "x.md", reader=lambda sentence: same_name[sentence])
    assert explained.extraction.units[1].status == "MAPPED" and explained.extraction.auto_resolved == 1


def test_relation_human_and_wait_with_scope_and_residual():
    base = (("ハルは実装をやる。", do("ハル", "実装")), ("ソラがコードを確かめる。", rd("ja", cl("確かめる", {"agent": "ソラ", "patient": "コード"}))))
    human, _ = explain_lines(*base, ("生成は人がやる。", do("人", "生成")))
    assert out_of(human, role="generate", kind="bulk_generation")["undecided_reason"] == "HUMAN"
    assert out_of(human)["agent"] == "ハル"                                  # a human-does-it statement is scoped
    wait, _ = explain_lines(*base, ("生成を待つ。", rd("ja", cl("待つ", {"patient": "生成"}))))
    assert out_of(wait, role="generate", kind="bulk_generation")["undecided_reason"] == "WAIT"
    rest, _ = explain_lines(*base, ("それ以外の仕事を待つ。", rd("ja", cl("待つ", {"patient": "それ以外の仕事"}))))
    assert out_of(rest, role="generate", kind="bulk_generation")["undecided_reason"] == "WAIT"   # where the router said NOT_COVERED
    assert out_of(rest)["agent"] == "ハル"                                    # a residual scope never turns a route into a wait
    assert out_of(rest, role="verify", kind="verification")["undecided_reason"] == "ALL_EXCLUDED"   # and not ALL_EXCLUDED either


# --------------------------------------------------------------------------------------------------------------------------------
# the stops
# --------------------------------------------------------------------------------------------------------------------------------
def one_unit_status(sentence, reading):
    explained, _ = explain_lines((sentence, reading))
    return explained.extraction.units[0].status, explained.extraction.units[0].reasons


@pytest.mark.parametrize("sentence,reading,status", [
    ("ハルは速い。", rd("ja", cl("速い", {"entity": "ハル"})), "PREDICATE_CLASS_UNKNOWN"),
    ("ハルは占いをやる。", do("ハル", "占い"), "WORK_TERM_UNKNOWN"),
    ("前者は実装をやる。", do("前者", "実装"), "NAME_UNRESOLVED"),
    ("重い方は実装をやる。", do("重い方", "実装"), "NAME_UNRESOLVED"),
    ("ハルさんは実装をやる。", do("ハルさん", "実装"), "NAME_UNRESOLVED"),
    ("The quiet one does the review.", rd("en", cl("do", {"agent": "the quiet one", "patient": "review"})), "NAME_UNRESOLVED"),
    ("ハルは10ファイルを超える実装をやる。", do("ハル", "10ファイルを超える実装"), "WORK_TERM_UNKNOWN"),
    ("ハルは実装をやる。", rd("ja", cl("やる", {"agent": "ハル", "patient": "実装", "time": "明日"})), "UNREPRESENTABLE"),
    ("ハルは1日3回まで実装をやる。", rd("ja", cl("やる", {"agent": "ハル", "patient": "実装"}, quantifiers={"event": "at_most:3"})), "UNREPRESENTABLE"),
    ("ハルは実装をやりたい。", rd("ja", cl("やる", {"agent": "ハル", "patient": "実装"}, mod="desire")), "UNREPRESENTABLE"),
    ("ハルは実装をやる。", rd("ja", cl("やる", {"agent": "ハル", "patient": "実装"}, voice="passive")), "UNREPRESENTABLE"),
    ("ハルは実装をやる。", rd("ja", cl("やる", {"agent": ["ハル", "モモ"], "patient": "実装"})), "AMBIGUOUS_RELATION"),
    ("ハルは東社のモデルだ。", rd("ja", cl("だ", {"entity": "ハル", "value": "東社のモデル"})), "NAME_UNRESOLVED"),
    ("ハルは実装だ。", rd("ja", cl("だ", {"entity": "ハル", "value": "実装"})), "MAPPED"),
])
def test_stops_have_their_own_typed_status(sentence, reading, status):
    got, reasons = one_unit_status(sentence, reading)
    assert got == status, reasons


def test_stop_unread_covers_the_readers_abstention_input_rejection_and_an_exception():
    explained, _ = explain_lines(("ハルは実装をやる。", no("ja", "NO_SUPPORTED_CLAUSE")))
    assert explained.extraction.units[0].status == "UNREAD" and explained.extraction.units[0].reasons == ["NO_SUPPORTED_CLAUSE"]
    broken = {"schema": "verantyx.semantic_read/1", "readable": True, "clauses": [{"predicate": "やる"}], "relations": [],
              "abstain": None, "clause_meta": [{}]}
    ex2, _ = explain_lines(("ハルは実装をやる。", broken))
    assert ex2.extraction.units[0].status == "UNREAD" and any(r.startswith("MISSING_FIELD") for r in ex2.extraction.units[0].reasons)

    def raising(_sentence):
        raise RuntimeError("boom")

    ex3 = rt.explain("ハルは実装をやる。\n", "x.md", reader=raising)
    assert ex3.extraction.units[0].status == "UNREAD" and ex3.extraction.units[0].reasons == ["READER_ERROR:RuntimeError"]
    assert out_of(ex3)["abstention"]["by_status"]["UNREAD"] == 1


def test_stop_a_reader_relation_between_clauses_is_not_mapped():
    reading = rd("ja", cl("やる", {"agent": "ハル", "patient": "実装"}), cl("やる", {"agent": "モモ", "patient": "検証"}),
                 relations=[{"type": "condition", "from": 0, "to": 1}])
    assert one_unit_status("ハルが実装をやるなら、モモが検証をやる。", reading)[0] == "UNREPRESENTABLE"


def test_stop_contradiction_and_conflicting_values():
    both, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")), ("ハルは実装をやらない。", do("ハル", "実装", "-")))
    assert [u.status for u in both.extraction.units] == ["CONTRADICTION", "CONTRADICTION"]
    quant, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                             ("ハルは二つまで動かす。", rd("ja", cl("動かす", {"agent": "ハル"}, quantifiers={"event": "at_most:2"}))),
                             ("ハルは三つまで動かす。", rd("ja", cl("動かす", {"agent": "ハル"}, quantifiers={"event": "at_most:3"}))))
    assert [u.status for u in quant.extraction.units][1:] == ["CONTRADICTION", "CONTRADICTION"]


# --------------------------------------------------------------------------------------------------------------------------------
# the gate
# --------------------------------------------------------------------------------------------------------------------------------
def test_gate_one_unread_unit_stops_every_job_and_the_router_is_not_called(monkeypatch):
    calls = []
    real = ar.route
    monkeypatch.setattr(ar, "route", lambda *a, **k: calls.append(1) or real(*a, **k))
    explained, _ = explain_lines(*STD, ("ただし大きい物は人がやる。", no("ja")))
    for job in (task(), task(role="verify", kind="verification", already_used={"implement": ["ハル"]}), task(role="review", kind="review")):
        got = rt.route_task(explained, job)
        assert got["decision"] == "undecided" and got["undecided_reason"] == "ABSTAINED" and got["agent"] is None
        assert got["abstention"]["type"] == "INCOMPLETE_READING" and got["router"] is None
        assert got["decided_by"] == "gate:INCOMPLETE_READING" and got["basis_kind"] is None
        assert got["abstention"]["by_status"]["UNREAD"] == 1 and got["abstention"]["by_status"]["MAPPED"] == 7
        assert [u["status"] for u in got["abstention"]["units"]] == ["UNREAD"]
    assert calls == []
    # the records of the units that were read are still reported
    assert got["records"]["agents"] and got["records"]["rules"]
    clean, _ = explain_lines(*STD)
    assert rt.route_task(clean, task())["decision"] == "route" and calls == [1]


def test_gate_every_non_passing_status_stops():
    for status in rt.UNIT_STATUSES:
        assert (status in rt.PASSING_STATUSES) == (status in ("MAPPED", "COMPARISON_ONLY"))
    rows = [("ハルは速い。", rd("ja", cl("速い", {"entity": "ハル"}))), ("ハルは占いをやる。", do("ハル", "占い")),
            ("前者は実装をやる。", do("前者", "実装")), ("ハルは実装をやる。", rd("ja", cl("やる", {"agent": ["ハル", "モモ"], "patient": "実装"}))),
            ("ハルは実装をやりたい。", rd("ja", cl("やる", {"agent": "ハル", "patient": "実装"}, mod="desire"))), ("ハルは実装をやる。", no("ja"))]
    for sentence, reading in rows:
        explained, _ = explain_lines(*STD, (sentence, reading))
        assert rt.route_task(explained, task())["abstention"]["type"] == "INCOMPLETE_READING", sentence


def test_gate_no_content_when_there_is_no_unit():
    explained = rt.explain("\n---\n", "x.md", reader=lambda s: pytest.fail("no unit, no read"))
    got = rt.route_task(explained, task())
    assert got["abstention"]["type"] == "NO_CONTENT" and got["undecided_reason"] == "ABSTAINED" and got["reading"]["units"] == 0
    assert got["reading"]["skipped_markup"] == 3


# --------------------------------------------------------------------------------------------------------------------------------
# the records (T3)
# --------------------------------------------------------------------------------------------------------------------------------
def test_T3_records_are_declared_text_with_witnesses_that_are_substrings_and_say_only_what_was_said(std):
    explained, text = explain_lines(*STD, source="/some/explanation.md")
    r = explained.records
    assert r.agents and r.rules
    for item in (*r.agents, *r.rules, *r.precedence, *r.lineage_relations):
        basis = item.basis
        assert basis.kind == "declared_text" and basis.source == "/some/explanation.md" and len(basis.witnesses) >= 1
        assert all(w in text and w.strip() for w in basis.witnesses)
    for agent in r.agents:
        assert agent.lineage is None and agent.adapter == "fake" and agent.model is None and agent.effort is None
        assert agent.note is None and agent.roles is None and agent.kinds is None and agent.concurrency is None
    for rule in r.rules:
        assert rule.reason is None and all(c.field != "independent_of" for c in rule.conditions)
    assert [c["agent"] for c in r.constructed] == [a.id for a in r.agents]
    assert all(c == {"agent": c["agent"], "field": "adapter", "value": "fake", "reason": "ADAPTER_NOT_STATED_ROUTE_ONLY"}
               for c in r.constructed)
    ar.build_routing_table(r.agents, r.rules, r.precedence, r.lineage_relations)   # the same record layer as any producer


def test_T3_an_unconditional_assignment_is_the_fallback_and_nothing_else_is_made_one(std):
    by_conditions = {tuple((c.field, c.value) for c in rule.conditions): rule for rule in std.records.rules}
    assert by_conditions[(("role", "implement"),)].fallback and by_conditions[(("role", "verify"),)].fallback
    assert by_conditions[(("role", "review"),)].fallback
    assert not by_conditions[(("kind", "test_authoring"),)].fallback and not by_conditions[(("kind", "attack"),)].fallback
    assert sorted(r.role for r in std.records.rules if r.fallback) == ["implement", "review", "verify"]


def test_T3_two_unconditional_assignments_of_one_role_are_refused_by_the_record_layer_and_not_made_one():
    explained, _ = explain_lines(("実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "実装"}))),
                                 ("実装はルナに任せる。", rd("ja", cl("任せる", {"recipient": "ルナ", "patient": "実装"}))))
    got = out_of(explained)
    assert explained.table is None and explained.table_error[0] == "DUPLICATE_FALLBACK"
    assert got["abstention"]["type"] == "RECORD_REFUSED" and got["abstention"]["detail"] == "DUPLICATE_FALLBACK"
    assert got["records"]["table"] == "REFUSED:DUPLICATE_FALLBACK" and got["router"] is None and got["undecided_reason"] == "ABSTAINED"


def test_T3_a_role_less_conditional_rule_needs_no_fallback_and_a_size_word_before_an_unknown_head_stops():
    cond, _ = explain_lines(("大きなリファクタリングはハルに任せる。",
                             rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きなリファクタリング"}))),
                            ("ハルはレビューをやる。", do("ハル", "レビュー")))
    assert cond.table is not None and cond.abstention is None
    unknown, _ = explain_lines(("ハルは大きな占いをやる。", do("ハル", "大きな占い")))
    assert unknown.extraction.units[0].status == "WORK_TERM_UNKNOWN"


def test_T3_a_conditional_role_rule_without_the_roles_fallback_is_refused():
    # "大きな" before the role word 実装 gives role=implement & size=large: a conditional rule of a role with no fallback
    explained, _ = explain_lines(("大きな実装はハルに任せる。", rd("ja", cl("任せる", {"recipient": "ハル", "patient": "大きな実装"}))))
    assert explained.extraction.units[0].status == "MAPPED"
    assert explained.table_error[0] == "MISSING_ROLE_DEFAULT"
    got = out_of(explained)
    assert got["abstention"]["type"] == "RECORD_REFUSED" and got["abstention"]["detail"] == "MISSING_ROLE_DEFAULT"
    assert explained.records.rules[0].fallback is False


def test_T3_only_says_roles_or_kinds_and_otherwise_they_stay_unsaid():
    explained, _ = explain_lines(("ウィックは検証だけをやる。", rd("ja", cl("やる", {"agent": "ウィック", "patient": "検証"}, quantifiers={"patient": "only"}))),
                                 ("ハルはテストだけを書く。", rd("ja", cl("書く", {"agent": "ハル", "patient": "テスト"}, quantifiers={"patient": "only"}))),
                                 ("クイルは実装をやる。", do("クイル", "実装")))
    by_id = {a.id: a for a in explained.records.agents}
    assert by_id["ウィック"].roles == frozenset({"verify"}) and by_id["ウィック"].kinds is None
    assert by_id["ハル"].kinds == frozenset({"test_authoring"}) and by_id["ハル"].roles is None
    assert by_id["クイル"].roles is None and by_id["クイル"].kinds is None


def test_T3_the_same_content_as_a_hand_written_table_gives_the_same_decisions(std):
    hand = ar.table_from_dicts(
        agents=[{"id": "ハル", "adapter": "fake", "witness": "w"}, {"id": "モモ", "adapter": "fake", "witness": "w"},
                {"id": "セキ", "adapter": "fake", "witness": "w"}],
        rules=[{"id": "A", "when": {"role": "implement"}, "prefer": ["ハル"], "fallback": True, "witness": "w"},
               {"id": "B", "when": {"kind": "test_authoring"}, "prefer": ["モモ"], "witness": "w"},
               {"id": "C", "when": {"role": "verify"}, "prefer": ["セキ"], "fallback": True, "witness": "w"},
               {"id": "D", "when": {"role": "review"}, "prefer": ["モモ"], "fallback": True, "witness": "w"},
               {"id": "E", "when": {"kind": "attack"}, "prefer": ["ハル"], "witness": "w"}],
        lineage_relations=[{"a": "ハル", "b": "セキ", "relation": "same", "witness": "w"}])
    requests = [dict(role="implement", kind="feature", size="medium"), dict(role="implement", kind="test_authoring", size="small"),
                dict(role="review", kind="review", size="medium"), dict(role="verify", kind="verification", size="medium"),
                dict(role="verify", kind="verification", size="medium", used_agents={"implement": ("ハル",)}),
                dict(role="verify", kind="verification", size="medium", used_agents={"implement": ("モモ",)}),
                dict(role="read", kind="read_large_file", size="large"), dict(role="verify", kind="attack", size="small",
                                                                             used_agents={"implement": ("モモ",)})]
    assert len(requests) >= 6
    for fields in requests:
        request = ar.RoutingRequest(job_id="j", **fields)
        assert ar.route(std.table, request).essence() == ar.route(hand, request).essence(), fields


# --------------------------------------------------------------------------------------------------------------------------------
# the router call
# --------------------------------------------------------------------------------------------------------------------------------
def test_router_call_passes_used_agents_only_no_chooser_and_the_first_names(monkeypatch, std):
    seen = {}
    real = ar.route

    def spy(table, request, **kw):
        seen["request"], seen["kw"] = request, kw
        return real(table, request, **kw)

    monkeypatch.setattr(ar, "route", spy)
    got = rt.route_task(std, task(role="verify", kind="verification", already_used={"implement": "モモ"}, running={"ハル": 1}))
    request = seen["request"]
    assert request.used_agents == {"implement": ("モモ",)} and request.used_lineages == {} and request.in_use == {"ハル": 1}
    assert seen["kw"] == {} and request.job_id == "route-from-text"
    assert got["router"]["values"] == "declared"


def test_router_reasons_are_written_through_from_the_routers_types(std):
    assert out_of(std, role="read", kind="read_large_file")["undecided_reason"] == "NOT_COVERED"
    assert out_of(std, role="verify", kind="verification", already_used={"implement": ["モモ"]})["undecided_reason"] == "ALL_EXCLUDED"
    tie, _ = explain_lines(("テストはハルがやる。", do("ハル", "テスト")), ("テストはルナがやる。", do("ルナ", "テスト")),
                           ("実装はクイルに任せる。", rd("ja", cl("任せる", {"recipient": "クイル", "patient": "実装"}))))
    got = out_of(tie, kind="test_authoring", size="small")
    assert got["undecided_reason"] == "TIE" and got["decided_by"] == "router:TESTIMONY_UNAVAILABLE" and got["basis_kind"] == "precedence"
    assert got["agent"] is None and got["abstention"] is None
    assert out_of(std, kind="test_authoring", size="small")["decided_by"] == "rule:T001_1"


def test_router_unknown_task_names_abstain_with_their_own_type(std):
    for kw in ({"already_used": {"implement": ["ゲンバ"]}}, {"running": {"ゲンバ": 1}}):
        got = out_of(std, **kw)
        assert got["abstention"]["type"] == "TASK_NAME_UNKNOWN" and got["undecided_reason"] == "ABSTAINED" and got["agent"] is None
    named_only_in_a_comparison_only_sentence = explain_lines(*STD)[0]
    assert "ハル" in agent_ids(named_only_in_a_comparison_only_sentence)


# --------------------------------------------------------------------------------------------------------------------------------
# the constraints: they can only turn a decision into "not routed"
# --------------------------------------------------------------------------------------------------------------------------------
def with_constraints(explained, constraints):
    records = dataclasses.replace(explained.records, constraints=tuple(constraints))
    return dataclasses.replace(explained, records=records)


def cons(ctype, name=None, roles=None, **scope):
    return {"kind": ctype, "name": name, "scope": scope, "roles": roles, "witnesses": [f"w-{ctype}"], "relation": "R-test"}


def test_constraint_prohibition_veto_does_not_try_the_next_agent(std):
    got = rt.route_task(with_constraints(std, [cons("prohibit", "ハル", role="implement")]), task())
    assert got["abstention"]["type"] == "PROHIBITION_VETO" and got["agent"] is None and got["undecided_reason"] == "ABSTAINED"
    assert got["router"]["agent_id"] == "ハル"        # what the router had decided is reported, and nobody else is chosen


def test_constraint_human_and_wait_scopes_and_residual_and_conflict(std):
    ok = rt.route_task(with_constraints(std, [cons("human", role="generate")]), task())
    assert ok["decision"] == "route"
    for kind, label in (("human", "HUMAN"), ("wait", "WAIT")):
        got = rt.route_task(with_constraints(std, [cons(kind, role="implement")]), task())
        assert got["undecided_reason"] == label and got["decided_by"] == f"constraint:{kind}" and got["agent"] is None
    residual = cons("wait", residual=True)
    assert rt.route_task(with_constraints(std, [residual]), task())["decision"] == "route"
    assert rt.route_task(with_constraints(std, [residual]), task(role="read", kind="read_large_file"))["undecided_reason"] == "WAIT"
    clash = rt.route_task(with_constraints(std, [cons("human", role="implement"), cons("wait", kind="feature")]), task())
    assert clash["abstention"]["type"] == "CONSTRAINT_CONFLICT" and clash["undecided_reason"] == "ABSTAINED"


def test_constraint_independence_veto_for_two_other_roles():
    explained, _ = explain_lines(("ハルは検証をやる。", do("ハル", "検証")), ("モモはレビューをやる。", do("モモ", "レビュー")),
                                 ("ルナは実装をやる。", do("ルナ", "実装")),
                                 ("モモとルナは別の会社だ。", rd("ja", cl("だ", {"entity": "モモとルナ", "value": "同じ会社"}, "-"))))
    independent = cons("independent", roles=["implement", "review"])
    got = rt.route_task(with_constraints(explained, [independent]), task(role="review", kind="review", already_used={"implement": ["ハル"]}))
    assert got["abstention"]["type"] == "INDEPENDENCE_VETO" and got["agent"] is None      # モモ vs ハル: no relation is said
    got = rt.route_task(with_constraints(explained, [independent]), task(role="review", kind="review", already_used={"implement": ["ルナ"]}))
    assert got["decision"] == "route" and got["agent"] == "モモ"                            # モモ vs ルナ: said to be distinct
    got = rt.route_task(with_constraints(explained, [independent]), task(role="implement", kind="feature", already_used={"review": ["ハル"]}))
    assert got["abstention"]["type"] == "INDEPENDENCE_VETO"                                # the pair is read in both directions
    assert [(r.a, r.b, r.relation) for r in explained.records.lineage_relations] == [("モモ", "ルナ", "distinct")]


def test_constraint_brute_force_never_turns_undecided_into_route_and_never_changes_the_agent(std):
    pool = [cons("prohibit", "ハル", role="implement"), cons("prohibit", "モモ", kind="test_authoring"), cons("human", role="generate"),
            cons("human", kind="feature"), cons("wait", role="review"), cons("wait", residual=True), cons("independent", roles=["implement", "review"])]
    jobs = [task(), task(kind="test_authoring", size="small"), task(role="review", kind="review"), task(role="read", kind="read_large_file"),
            task(role="verify", kind="verification", already_used={"implement": ["モモ"]}), task(role="generate", kind="bulk_generation"),
            task(role="verify", kind="attack", already_used={"implement": ["ハル"]})]
    checked = 0
    for job in jobs:
        base = rt.route_task(std, job)
        for mask in range(1 << len(pool)):
            chosen = [c for i, c in enumerate(pool) if mask >> i & 1]
            got = rt.route_task(with_constraints(std, chosen), job)
            if base["decision"] == "undecided":
                assert got["decision"] == "undecided" and got["agent"] is None
            elif got["decision"] == "route":
                assert got["agent"] == base["agent"]
            assert got["agent"] in (None, base["agent"])
            checked += 1
    assert checked == len(jobs) * (1 << len(pool))


# --------------------------------------------------------------------------------------------------------------------------------
# hand-offs from W2-h4 and the output
# --------------------------------------------------------------------------------------------------------------------------------
def test_handoff2_a_role_less_attack_rule_and_a_verify_job_do_not_make_an_independence_cycle(std):
    assert std.table is not None
    got = out_of(std, role="verify", kind="attack", already_used={"implement": ["モモ"]})
    assert got["records"]["table"] == "BUILT"
    assert all(c.field != "independent_of" for rule in std.records.rules for c in rule.conditions)


def test_handoff3_a_role_less_closed_choice_rule_is_chosen_for_an_answer_job():
    explained, _ = explain_lines(("ハルは実装をやる。", do("ハル", "実装")),
                                 ("ハルはレビューをやる。", do("ハル", "レビュー")),
                                 ("ルナは回答をやる。", do("ルナ", "回答")))
    # a role-less rule is made from a kind word; the closed choice has no word in the table, so build the same record by hand
    rule = ar.RoutingRule("T900_1", (ar.Condition("kind", "closed_choice"),), ("ルナ",), None, ar.Basis.text("x", "w"))
    records = dataclasses.replace(explained.records, rules=tuple(explained.records.rules) + (rule,))
    table = ar.build_routing_table(records.agents, records.rules, records.precedence, records.lineage_relations)
    decision = ar.route(table, ar.RoutingRequest(job_id="j", role="answer", kind="closed_choice", size="small"))
    assert decision.decided and decision.agent_id == "ルナ"


def test_output_keys_order_and_basis_kinds(std):
    got = out_of(std)
    assert list(got) == ["schema", "decision", "agent", "undecided_reason", "abstention", "basis_kind", "evidence", "decided_by",
                         "records", "relations", "reading", "router", "ignored_fields", "task"]
    assert list(got["records"]) == ["agents", "rules", "precedence", "lineage_relations", "aliases", "constraints", "constructed", "table"]
    assert got["schema"] == rt.SCHEMA and got["reading"]["lookup"] == "stub-no-placement/1"
    assert got["basis_kind"] in rt.BASIS_KINDS_OUT and got["evidence"] == ["ハルは実装をやる。"]
    assert out_of(std, kind="test_authoring", size="small")["basis_kind"] == "condition"
    for undecided in (out_of(std, role="read", kind="read_large_file"), out_of(std, role="verify", kind="verification",
                                                                                   already_used={"implement": ["ハル"]})):
        assert undecided["undecided_reason"] in rt.UNDECIDED_OUT and undecided["basis_kind"] in rt.BASIS_KINDS_OUT + (None,)
    assert out_of(std, role="read", kind="read_large_file")["basis_kind"] == "silence"
    assert json.loads(rt.dumps(got)) == got


def test_output_ignored_fields_are_kept_with_their_values_and_their_type(std):
    got = rt.route_task(std, task(touches=["a.py"], used_today={"ハル": 2}, files=["x"], date="2026-10-03", mood="calm"))
    assert got["ignored_fields"] == [{"field": "date", "value": "2026-10-03", "reason": "NOT_USED_BY_ROUTER"},
                                     {"field": "files", "value": ["x"], "reason": "NOT_USED_BY_ROUTER"},
                                     {"field": "mood", "value": "calm", "reason": "UNKNOWN_TASK_FIELD"},
                                     {"field": "touches", "value": ["a.py"], "reason": "NOT_USED_BY_ROUTER"},
                                     {"field": "used_today", "value": {"ハル": 2}, "reason": "NOT_USED_BY_ROUTER"}]
    assert rt.route_task(std, task())["ignored_fields"] == []


@pytest.mark.parametrize("bad", [None, [], {"role": "implement"}, {"role": "x", "kind": "feature", "size": "small"},
                                 {"role": "implement", "kind": "feature", "size": "huge"},
                                 {"role": "implement", "kind": "feature", "size": "small", "already_used": ["ハル"]},
                                 {"role": "implement", "kind": "feature", "size": "small", "already_used": {"nobody": "ハル"}},
                                 {"role": "implement", "kind": "feature", "size": "small", "running": {"ハル": -1}}])
def test_output_a_bad_task_is_an_error_not_a_decision(std, bad):
    with pytest.raises(rt.TaskError):
        rt.route_task(std, bad)


def test_output_task_argument_is_json_or_the_path_of_a_json_file(tmp_path):
    path = tmp_path / "t.json"
    path.write_text(json.dumps(task()), encoding="utf-8")
    assert rt.parse_task_argument(json.dumps(task())) == task() and rt.parse_task_argument(str(path)) == task()
    with pytest.raises(rt.TaskError):
        rt.parse_task_argument(str(tmp_path / "missing.json"))


def test_output_is_deterministic_for_the_same_input(std):
    first = rt.dumps(out_of(std, running={"ハル": 1}))
    again = rt.dumps(out_of(explain_lines(*STD)[0], running={"ハル": 1}))
    assert first == again


# --------------------------------------------------------------------------------------------------------------------------------
# T4, the mechanical part, and the constants against the docs
# --------------------------------------------------------------------------------------------------------------------------------
def module_source():
    with open(os.path.join(ROOT, "verantyx", "routing_from_text.py"), encoding="utf-8") as handle:
        return handle.read()


def test_T4_the_module_uses_no_regular_expression_no_direct_table_and_no_lineage_label():
    source = module_source()
    assert not _re_for_the_test_only.search(r"^\s*(import re\b|from re\b)", source, _re_for_the_test_only.M)
    assert not _re_for_the_test_only.search(r"\bre\.(compile|search|match|fullmatch|findall|finditer|sub|split)\(", source)
    assert "RoutingTable(" not in source              # a table is made by build_routing_table only
    assert "used_lineages" not in source               # only used_agents is passed
    assert "chooser_factory" not in source.replace("no chooser_factory", "").replace("chooser_factory, so", "")
    assert "independent_of" not in source.replace("independent_of condition", "").replace("``independent_of``", "")


def doc_chapter(number):
    text = open(os.path.join(ROOT, "docs", "ROUTING_FROM_TEXT.md"), encoding="utf-8").read()
    head, _, rest = text.partition(f"\n## {number}. ")
    return rest.partition("\n## ")[0]


def test_T4_every_constant_entry_is_listed_in_the_docs():
    docs = doc_chapter(6)          # chapter 6 only: the lists of other chapters must not stand in for the tables
    assert docs
    missing = []
    for name in rt.CONSTANT_NAMES:
        value = getattr(rt, name)
        entries = []
        if isinstance(value, dict):
            for key, val in value.items():
                entries.append(key[1] if isinstance(key, tuple) else key)
                if isinstance(val, frozenset):
                    entries.extend(sorted(val))
        else:
            entries.extend(sorted(value))
        if f"`{name}`" not in docs:
            missing.append(name)
        for entry in entries:
            if str(entry) not in docs:
                missing.append(f"{name}:{entry}")
    assert not missing, missing


def test_T4_closed_lists_are_what_the_docs_say():
    assert set(rt.RELATION_KINDS) == {"SUITABILITY", "PROHIBITION", "COMPARISON", "COMPARISON_ONLY", "INDEPENDENCE", "QUANTITY",
                                      "PRECEDENCE", "ALIAS", "HUMAN", "WAIT"}
    assert set(rt.UNIT_STATUSES) >= set(rt.PASSING_STATUSES)
    docs = open(os.path.join(ROOT, "docs", "ROUTING_FROM_TEXT.md"), encoding="utf-8").read()
    for name in (*rt.UNIT_STATUSES, *rt.ABSTENTION_TYPES, *rt.RELATION_KINDS, *rt.UNDECIDED_OUT, *rt.BASIS_KINDS_OUT):
        assert name in docs, name


def test_T4_the_values_of_the_tables_are_in_the_closed_vocabulary():
    for value in rt.WORK_TERMS.values():
        assert (value[0] == "role" and value[1] in ar.ROLES) or (value[0] == "kind" and value[1] in ar.TASK_KINDS)
    for value in rt.VERB_WORK.values():
        assert (value[0] == "role" and value[1] in ar.ROLES) or (value[0] == "kind" and value[1] in ar.TASK_KINDS)
    assert set(rt.SIZE_TERMS.values()) <= set(ar.SIZES) and set(rt.ROLE_NOUNS.values()) <= set(ar.ROLES)
    assert set(rt.PREDICATE_CLASSES.values()) <= set(rt.PREDICATE_CLASS_NAMES)
    for key, cls in rt.PREDICATE_CLASSES.items():
        assert (cls in ("ROLE_VERB", "CREATE_VERB")) == (key in rt.VERB_WORK)
    for key in itertools.chain(rt.PREDICATE_CLASSES, rt.WORK_TERMS, rt.SIZE_TERMS):
        assert key[1] == unicodedata.normalize("NFKC", key[1]).casefold()      # keys are in the form the matcher compares


def test_M4_the_docs_list_every_constant_entry_that_is_a_word_of_the_first_six_explanations():
    """Chapter 7 lists the entries that occur in e1-e6 (the implementer read those texts before the freeze).  The list is the output of
    tests/routing_from_text/constants_in_data.py, recomputed here."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("constants_in_data", os.path.join(ROOT, "tests", "routing_from_text", "constants_in_data.py"))
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    directory, ids = tool.SETS["e1-e6"]
    text = tool.norm("\n".join(open(os.path.join(tool.DATA, directory, i + ".md"), encoding="utf-8").read() for i in ids))
    words, lemmas = tool.words_of(text), tool.lemmas_of(text)
    computed = {}
    for name in rt.CONSTANT_NAMES:
        if name in tool.LEFT_OUT:
            continue
        hits = sorted({f"{lang}:{term}" for lang, term in tool.entries(name) if tool.occurs(lang, term, text, words, lemmas)})
        if hits:
            computed[name] = hits
    chapter = doc_chapter(7)
    listed = {}
    for line in chapter.splitlines():
        if line.startswith("- `") and "`: " in line:
            table, _, rest = line[3:].partition("`: ")
            listed[table] = sorted(piece.strip("`") for piece in rest.split("、"))
    assert listed == computed
    for named in ("ja:作った者", "ja:確かめる者", "ja:どれにも当てはまらない仕事", "ja:系列", "ja:動かす", "en:hold"):
        assert any(named in entries for entries in computed.values()), named
