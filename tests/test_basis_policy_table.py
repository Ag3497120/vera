"""W6-a P1: the basis policy table is exactly the pre-registered table in docs/BASIS_POLICY.md.

The expected values are NOT written in this file: they are parsed from the prereg section of the
document (written before this test), so the code table and the document cannot drift apart without
a failure. Synthetic data only. Helpers are copied here on purpose: tests/ is not a package.
"""
from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from verantyx import basis_policy as bp

DOC = Path(__file__).resolve().parents[1] / "docs" / "BASIS_POLICY.md"


def _prereg() -> str:
    text = DOC.read_text(encoding="utf-8")
    begin = text.index("<!-- prereg:begin -->")
    end = text.index("<!-- prereg:end -->")
    return text[begin:end]


def _doc_table() -> dict:
    rows = {}
    for line in _prereg().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.startswith("|") or cells[0] not in ("FACTUAL", "NON_FACTUAL"):
            continue
        kind_class, basis, human, ref, outcome, with_form = cells[:6]
        assert human in ("T", "F") and ref in ("T", "F"), line
        key = (kind_class, basis, human == "T", ref == "T")
        assert key not in rows, f"duplicate key in the document table: {key}"
        rows[key] = (outcome, with_form)
    return rows


def test_the_document_table_has_the_24_pre_registered_rows():
    rows = _doc_table()
    assert len(rows) == 24
    product = set(itertools.product(("FACTUAL", "NON_FACTUAL"), ("HUMAN", "GENERATED", "NONE"),
                                    (False, True), (False, True)))
    assert set(rows) == product


def test_code_table_keys_are_exactly_the_24_combinations():
    product = set(itertools.product(("FACTUAL", "NON_FACTUAL"), ("HUMAN", "GENERATED", "NONE"),
                                    (False, True), (False, True)))
    assert set(bp.TABLE) == product
    assert len(bp.TABLE) == 24


def test_code_table_equals_the_document_table_row_by_row():
    doc = _doc_table()
    assert {k: tuple(v) for k, v in bp.TABLE.items()} == doc
    for outcome, with_form in doc.values():
        assert outcome in bp.OUTCOMES and with_form in bp.OUTCOMES


def test_every_key_maps_to_exactly_one_outcome_pair_and_decide_returns_it():
    doc = _doc_table()
    kinds = {"FACTUAL": "factual", "NON_FACTUAL": "creative"}
    for (cls, basis, human, ref), (outcome, with_form) in doc.items():
        d = bp.decide(kinds[cls], basis, human, ref)
        assert d.in_table is True and d.reason is None
        assert (d.outcome, d.outcome_with_verified_form) == (outcome, with_form)
        assert (d.kind_class, d.basis, d.human_present, d.show_reference) == (cls, basis, human, ref)
        assert d.table_version == bp.TABLE_VERSION == 1


def test_only_factual_human_rows_differ_between_the_two_outcome_columns():
    differing = {k for k, (a, b) in _doc_table().items() if a != b}
    assert differing == {("FACTUAL", "HUMAN", h, r) for h in (False, True) for r in (False, True)}


def test_all_five_request_kinds_and_their_classes():
    assert bp.REQUEST_KINDS == ("factual", "creative", "paraphrase", "style", "example")
    assert bp.KIND_CLASS["factual"] == "FACTUAL"
    for kind in ("creative", "paraphrase", "style", "example"):
        assert bp.KIND_CLASS[kind] == "NON_FACTUAL"
    assert set(bp.KIND_CLASS) == set(bp.REQUEST_KINDS)
    # every non-factual kind gives the same decision as every other for the same basis
    for basis, human, ref in itertools.product(("HUMAN", "GENERATED", "NONE"), (False, True), (False, True)):
        outs = {bp.decide(k, basis, human, ref).outcome for k in ("creative", "paraphrase", "style", "example")}
        assert len(outs) == 1


@pytest.mark.parametrize("args, why", [
    (("poem", "HUMAN", False, False), "request_kind"),
    (("", "HUMAN", False, False), "request_kind"),
    (("factual", "MIXED", True, True), "MIXED"),
    (("factual", "UNKNOWN", False, False), "basis"),
    (("factual", "human", False, False), "basis"),
    (("factual", None, False, False), "basis"),
    (("factual", "HUMAN", 1, False), "human_present"),
    (("factual", "HUMAN", None, False), "human_present"),
    (("factual", "HUMAN", False, "yes"), "show_reference"),
    (("factual", "GENERATED", True, 0), "show_reference"),
    ((None, "HUMAN", False, False), "request_kind"),
    (("creative", ["HUMAN"], False, False), "basis"),
])
def test_input_not_in_the_table_abstains_without_raising(args, why):
    d = bp.decide(*args)
    assert d.outcome == "ABSTAIN" and d.outcome_with_verified_form == "ABSTAIN"
    assert d.in_table is False
    assert d.reason and d.reason.startswith("NOT_IN_TABLE:") and why in d.reason
    assert isinstance(d.to_dict(), dict)


def test_mixed_basis_has_its_own_reason_and_is_not_an_answer():
    d = bp.decide("factual", "MIXED", True, True)
    assert d.outcome == "ABSTAIN" and d.in_table is False and "BASIS_MIXED_NOT_IN_TABLE" in d.reason


def test_decide_accepts_a_classification_result_as_the_basis():
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    sc = bp.classify_sources([{"family": "memory_sovereign", "origin": "human_confirmed", "text": "x"}])
    assert sc.basis == "HUMAN"
    assert bp.decide("factual", sc, False, False).outcome == "ANSWER_HUMAN_BASIS"


def test_to_dict_is_plain_json():
    import json
    d = bp.decide("factual", "GENERATED", True, False).to_dict()
    json.dumps(d)
    assert d["outcome"] == "CONFIRM_REQUEST" and d["table_version"] == 1


# ------------------------------------------------------------------ classification (rules 1-6)
def test_rule1_a_non_dict_is_unreadable_and_counted_not_trusted():
    sc = bp.classify_sources(["text", None, 3])
    assert sc.counts["unreadable"] == 3 and sc.basis == "NONE" and sc.cited == 3


def test_rule2_generated_origin():
    sc = bp.classify_sources([{"family": "local", "origin": "generated", "text": "a"}])
    assert sc.counts["generated"] == 1 and sc.basis == "GENERATED" and sc.cited == 1


def test_rule3_human_confirmed_origin_is_human():
    sc = bp.classify_sources([{"family": "memory_sovereign", "origin": "human_confirmed"}])
    assert sc.counts["human"] == 1 and sc.basis == "HUMAN"


def test_rule4_other_origin_values_are_not_evidence_and_counted_by_value():
    sc = bp.classify_sources([{"origin": "constructed"}, {"origin": "testimony"}, {"origin": "zzz"},
                              {"origin": "constructed"}])
    assert sc.counts["non_evidence"] == 4 and sc.basis == "NONE" and sc.cited == 4
    assert sc.non_evidence_by_origin == {"constructed": 2, "testimony": 1, "zzz": 1}


def test_rule4_origin_none_falls_through_to_the_later_rules():
    sc = bp.classify_sources([{"origin": None, "family": "user"}, {"origin": None, "family": "doc"}])
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力は同じ。later rule の「それ以外」は人でなく出所不明（規則 8）
    assert sc.counts["request_text"] == 1 and sc.counts["human"] == 0 and sc.unknown_origin == 1


def test_rule5_the_request_text_is_counted_and_removed_from_cited():
    sc = bp.classify_sources([{"family": "user", "source": "user:condition"}])
    assert sc.counts["request_text"] == 1 and sc.cited == 0 and sc.basis == "NONE"


def test_rule6_anything_else_is_human():
    sc = bp.classify_sources([{"family": "document", "source": "memo.txt", "text": "花子は来た。"}])
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力は同じ。origin の無い出典は、利用者が渡した文書と分かっていなければ出所不明
    assert sc.counts["human"] == 0 and sc.unknown_origin == 1 and sc.basis == "UNKNOWN_ORIGIN" and sc.cited == 1


def test_generated_next_to_the_request_text_is_still_generated_only():
    sc = bp.classify_sources([{"family": "user", "source": "user:condition"},
                              {"family": "local", "origin": "generated"}])
    assert sc.basis == "GENERATED" and sc.cited == 1


def test_human_and_generated_together_is_mixed():
    # W5-c r3（監査役の判断 2026-10-03 20:40）: 入力の人の出典を明示の人（origin: human_confirmed）にした。期待は同じ
    sc = bp.classify_sources([{"family": "memory_sovereign", "origin": "human_confirmed"}, {"family": "local", "origin": "generated"}])
    assert sc.basis == "MIXED" and sc.cited == 2


def test_counts_always_has_every_class_even_zero_and_the_empty_input_is_none():
    sc = bp.classify_sources([])
    assert sc.basis == "NONE" and sc.cited == 0
    assert set(sc.counts) == {"human", "generated", "non_evidence", "request_text", "unreadable"}
    assert all(v == 0 for v in sc.counts.values())


def test_classification_does_not_modify_its_input():
    import copy
    src = [{"family": "local", "origin": "generated", "text": "a"}, "x"]
    before = copy.deepcopy(src)
    bp.classify_sources(src)
    assert src == before


# --------------------------------------------------------------------------- constants
def test_refusal_constants_equal_the_ones_in_one_py():
    from verantyx import one
    assert set(bp.REFUSAL_KINDS) == set(one._REFUSAL_KINDS)
    assert tuple(bp.REFUSAL_PREFIXES) == tuple(one._REFUSAL_PREFIXES)


def test_entry_request_kinds():
    assert bp.ENTRY_REQUEST_KIND == {"ask": "factual", "observe": "creative"}
    assert set(bp.ENTRY_REQUEST_KIND.values()) <= set(bp.REQUEST_KINDS)


def test_outcomes_are_the_six_closed_types():
    assert bp.OUTCOMES == ("ANSWER_HUMAN_BASIS", "ANSWER_FORM_FROM_GENERATED", "CONSTRUCTED",
                           "CONFIRM_REQUEST", "REFERENCE_GENERATED", "ABSTAIN")
    assert bp.BASES == ("HUMAN", "GENERATED", "NONE")
    assert bp.SCHEMA == "verantyx.basis_policy/1"
