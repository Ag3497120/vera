import json

import pytest

from verantyx.semantic_ir import Clause, EventValue, Role, Span, View
from verantyx.semantic_unknown import unknown_candidates


def _clause(clause_id, terms, text=None):
    source = "source:" + clause_id
    if text is None:
        text = " ".join(terms)
    whole = Span(source, 0, len(text), text)
    roles = []
    for index, term in enumerate(terms):
        start = text.find(term)
        assert start >= 0
        roles.append(Role("role_%d" % index, term,
                          Span(source, start, start + len(term), term)))
    return source, text, Clause(
        clause_id, EventValue("view", "document", clause_id, ""),
        "describes", whole, tuple(roles), whole,
    )


def _view(*term_groups):
    sources = {}
    clauses = []
    for index, terms in enumerate(term_groups):
        source, text, clause = _clause("c%d" % index, list(terms))
        sources[source] = text
        clauses.append(clause)
    return View(sources, tuple(clauses))


def _unit_view():
    return _view(("損害保険", "賠償責任", "保険賠償", "損害", "賠償"))


def _term_candidate(report):
    assert report.status == "CANDIDATES"
    assert len(report.candidates) == 1
    return report.candidates[0]


def test_known_role_term_has_no_candidate():
    report = unknown_candidates(_unit_view(), "損害")
    assert report.status == "KNOWN_TERM"
    assert report.candidates == ()


def test_known_predicate_has_no_candidate():
    source, text, clause = _clause("predicate", ("制度",))
    clause = Clause(clause.id, clause.event, "保険", clause.predicate_span,
                    clause.roles, clause.span)
    report = unknown_candidates(View({source: text}, (clause,)), "保険")
    assert report.status == "KNOWN_TERM"


def test_unknown_term_gets_unit_candidate():
    candidate = _term_candidate(unknown_candidates(_unit_view(), "損害賠償"))
    assert candidate.kind == "EXPLAINED_BY_UNITS"


def test_unit_candidate_has_constructed_marker():
    candidate = _term_candidate(unknown_candidates(_unit_view(), "損害賠償"))
    assert candidate.constructed is True


def test_unit_candidate_is_not_evidence():
    candidate = _term_candidate(unknown_candidates(_unit_view(), "損害賠償"))
    assert candidate.evidence is False


def test_unit_candidate_has_a_reason():
    candidate = _term_candidate(unknown_candidates(_unit_view(), "損害賠償"))
    assert "constructed" in candidate.reason


def test_unit_candidate_has_decomposed_parts():
    candidate = _term_candidate(unknown_candidates(_unit_view(), "損害賠償"))
    assert set(candidate.units) == {"損害", "賠償"}


def test_each_unit_has_provenance():
    candidate = _term_candidate(unknown_candidates(_unit_view(), "損害賠償"))
    assert {item.unit for item in candidate.provenance} == set(candidate.units)


def test_provenance_spans_resolve_to_source_text():
    view = _unit_view()
    candidate = _term_candidate(unknown_candidates(view, "損害賠償"))
    for item in candidate.provenance:
        for clause_ref in item.clauses:
            assert clause_ref.span.valid(view.sources)


def test_provenance_names_real_clauses():
    view = _unit_view()
    candidate = _term_candidate(unknown_candidates(view, "損害賠償"))
    clause_ids = {clause.id for clause in view.clauses}
    for item in candidate.provenance:
        assert item.clauses
        assert all(ref.clause_id in clause_ids for ref in item.clauses)


def test_provenance_text_is_the_unit():
    candidate = _term_candidate(unknown_candidates(_unit_view(), "損害賠償"))
    for item in candidate.provenance:
        assert all(ref.span.text == item.unit for ref in item.clauses)


def test_candidate_serializes_as_json():
    report = unknown_candidates(_unit_view(), "損害賠償")
    decoded = json.loads(report.to_json())
    assert decoded["candidates"][0]["kind"] == "EXPLAINED_BY_UNITS"


def test_report_dict_is_json_serializable():
    json.dumps(unknown_candidates(_unit_view(), "損害賠償").to_dict(),
               ensure_ascii=False)


def test_no_candidate_type_can_be_read_as_answer():
    report = unknown_candidates(_unit_view(), "損害賠償")
    assert all(candidate.kind in {
        "EXPLAINED_BY_UNITS", "KIN_NEIGHBOURHOOD", "NO_REACH",
    } for candidate in report.candidates)


def test_result_is_deterministic():
    view = _unit_view()
    first = unknown_candidates(view, "損害賠償").to_json()
    second = unknown_candidates(view, "損害賠償").to_json()
    assert first == second


def test_unit_order_is_deterministic():
    first = _term_candidate(unknown_candidates(_unit_view(), "損害賠償"))
    second = _term_candidate(unknown_candidates(_unit_view(), "損害賠償"))
    assert first.units == second.units


def test_unreachable_nonword_is_typed_no_reach():
    candidate = _term_candidate(unknown_candidates(View({}, ()), "xyz"))
    assert candidate.kind == "NO_REACH"


def test_no_reach_candidate_is_constructed():
    candidate = _term_candidate(unknown_candidates(View({}, ()), "xyz"))
    assert candidate.constructed is True


def test_no_reach_candidate_has_no_units():
    candidate = _term_candidate(unknown_candidates(View({}, ()), "xyz"))
    assert candidate.units == ()


def test_no_reach_candidate_has_reason():
    candidate = _term_candidate(unknown_candidates(View({}, ()), "xyz"))
    assert candidate.reason


def test_bare_suffix_uses_explain_abstention():
    first = _clause("bare_a", ("保険",), "保険法")
    second = _clause("bare_b", (), "法律者")
    view = View({first[0]: first[1], second[0]: second[1]},
                (first[2], second[2]))
    report = unknown_candidates(view, "保険者")
    assert report.status == "ABSTAIN_BARE_SUFFIX_SPLIT"
    assert report.candidates == ()


def test_nonword_units_use_explain_abstention():
    first = _clause("fragment_a", ("空想保険", "空想"), "空想保険")
    second = _clause("fragment_b", ("責任保障", "保障"), "責任保障")
    view = View({first[0]: first[1], second[0]: second[1]},
                (first[2], second[2]))
    report = unknown_candidates(view, "空想保障")
    assert report.status == "ABSTAIN_UNIT_NOT_A_WORD"


def test_nonword_abstention_emits_no_candidate():
    first = _clause("fragment_a", ("空想保険", "空想"), "空想保険")
    second = _clause("fragment_b", ("責任保障", "保障"), "責任保障")
    view = View({first[0]: first[1], second[0]: second[1]},
                (first[2], second[2]))
    assert unknown_candidates(view, "空想保障").candidates == ()


def test_equal_splits_use_explain_tie_abstention():
    terms = ("甲乙戊己", "辛壬丙丁", "甲乙丙", "辛乙丙丁",
             "甲乙", "丙丁", "甲", "乙丙丁")
    text = "甲乙戊己 辛壬丙丁 甲乙丙 辛乙丙丁 甲乙 乙丙丁"
    source, text, clause = _clause("tie", terms, text)
    report = unknown_candidates(View({source: text}, (clause,)), "甲乙丙丁")
    assert report.status == "ABSTAIN_SPLIT_TIED"
    assert report.candidates == ()


def test_budget_zero_refuses_even_an_empty_view():
    report = unknown_candidates(View({}, ()), "xyz", budget=0)
    assert report.status == "BUDGET_REFUSAL"
    assert report.candidates == ()


def test_small_budget_refuses_projection():
    report = unknown_candidates(_unit_view(), "損害賠償", budget=1)
    assert report.status == "BUDGET_REFUSAL"


def test_budget_refusal_is_json_serializable():
    report = unknown_candidates(_unit_view(), "損害賠償", budget=1)
    assert json.loads(report.to_json())["status"] == "BUDGET_REFUSAL"


def test_kin_neighbourhood_is_typed_separately():
    view = _view(("甲乙丙", "甲乙丁", "戊乙丙", "己乙丙"))
    candidate = _term_candidate(unknown_candidates(view, "甲乙辛"))
    assert candidate.kind == "KIN_NEIGHBOURHOOD"


def test_kin_neighbourhood_lists_shared_unit_families():
    view = _view(("甲乙丙", "甲乙丁", "戊乙丙", "己乙丙"))
    candidate = _term_candidate(unknown_candidates(view, "甲乙辛"))
    assert candidate.families
    assert any(family.slot == "甲乙@L" for family in candidate.families)


def test_kin_candidate_is_constructed_and_not_evidence():
    view = _view(("甲乙丙", "甲乙丁", "戊乙丙", "己乙丙"))
    candidate = _term_candidate(unknown_candidates(view, "甲乙辛"))
    assert candidate.constructed is True
    assert candidate.evidence is False


def test_kin_candidate_provenance_resolves():
    view = _view(("甲乙丙", "甲乙丁", "戊乙丙", "己乙丙"))
    candidate = _term_candidate(unknown_candidates(view, "甲乙辛"))
    for item in candidate.provenance:
        for clause_ref in item.clauses:
            assert clause_ref.span.valid(view.sources)


def test_non_string_term_is_rejected_as_bad_input():
    with pytest.raises(TypeError):
        unknown_candidates(_unit_view(), 12)


@pytest.mark.parametrize("term", ["", "???", "xyz", "0", "---"])
def test_nonwords_do_not_turn_into_explanations(term):
    report = unknown_candidates(View({}, ()), term)
    assert not any(c.kind == "EXPLAINED_BY_UNITS" for c in report.candidates)
