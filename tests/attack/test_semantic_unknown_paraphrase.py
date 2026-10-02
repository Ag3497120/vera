import pytest

from verantyx.semantic_ir import Clause, Role, Span, View
from verantyx.semantic_unknown import unknown_candidates


def _view(source, role_terms, predicate="owns"):
    roles = []
    for name, term in role_terms:
        start = source.find(term)
        assert start >= 0, (term, source)
        roles.append(Role(name, term,
                          Span("s", start, start + len(term), term)))
    clause = Clause(
        "c1", None, predicate, Span("s", 0, 0, ""), tuple(roles),
        Span("s", 0, len(source), source),
    )
    return View({"s": source}, (clause,))


def _verdict(report):
    return (
        report.status,
        tuple((candidate.kind, candidate.units,
               tuple((family.slot, family.members)
                     for family in candidate.families))
              for candidate in report.candidates),
    )


def test_role_and_predicate_terms_are_known():
    view = _view("boat and house", (("object", "boat"), ("place", "house")))

    assert unknown_candidates(view, "house").status == "KNOWN_TERM"
    assert unknown_candidates(view, "owns").status == "KNOWN_TERM"


def test_invalid_or_insufficient_work_budget_refuses():
    view = _view("house and boat", (("place", "house"), ("object", "boat")))

    for budget in (0, -1, 1, 1.5, True):
        assert unknown_candidates(view, "houseboat", budget).status == "BUDGET_REFUSAL"


def test_non_string_query_is_rejected_by_contract():
    view = _view("house and boat", (("place", "house"), ("object", "boat")))

    with pytest.raises(TypeError, match="term must be a string"):
        unknown_candidates(view, None)


def test_out_of_closure_report_is_constructed_not_evidence_or_answer():
    view = _view("house and boat", (("place", "house"), ("object", "boat")))
    report = unknown_candidates(view, "houseboat")

    assert report.status == "CANDIDATES"
    assert report.candidates
    assert all(candidate.kind in {
        "EXPLAINED_BY_UNITS", "KIN_NEIGHBOURHOOD", "NO_REACH",
    } for candidate in report.candidates)
    assert all(candidate.constructed is True for candidate in report.candidates)
    assert all(candidate.evidence is False for candidate in report.candidates)


def test_candidate_provenance_spans_match_source_text():
    view = _view("house and boat", (("place", "house"), ("object", "boat")))
    report = unknown_candidates(view, "houseboat")

    assert report.candidates
    for candidate in report.candidates:
        for item in candidate.provenance:
            for clause_span in item.clauses:
                span = clause_span.span
                assert span.valid(view.sources)
                assert view.sources[span.source][span.start:span.end] == span.text


def test_word_order_paraphrase_preserves_route():
    roles = (("place", "house"), ("object", "boat"))
    left = unknown_candidates(_view("house and boat", roles), "houseboat")
    right = unknown_candidates(_view("boat and house", roles), "houseboat")

    assert _verdict(left) == _verdict(right)


def test_polite_surface_material_preserves_route():
    roles = (("place", "house"), ("object", "boat"))
    plain = unknown_candidates(_view("house and boat", roles), "houseboat")
    polite = unknown_candidates(
        _view("house please and boat", roles), "houseboat")

    assert _verdict(plain) == _verdict(polite)


def test_number_surface_variants_preserve_route():
    roles = (("place", "house"), ("object", "boat"))
    singular = unknown_candidates(_view("house and boat", roles), "houseboat")
    plural = unknown_candidates(_view("houses and boats", roles), "houseboat")

    assert _verdict(singular) == _verdict(plural)


def test_japanese_particle_and_politeness_variants_preserve_route():
    roles = (("agent", "太郎"), ("patient", "猫"))
    plain = unknown_candidates(
        _view("太郎が猫をなでる。", roles, predicate="なでる"), "猫好き")
    polite = unknown_candidates(
        _view("猫を太郎はなでます。", roles, predicate="なでる"), "猫好き")

    assert _verdict(plain) == _verdict(polite)


def test_changed_compound_meaning_changes_the_constructed_route():
    view = _view("house and boat", (("place", "house"), ("object", "boat")))

    houseboat = unknown_candidates(view, "houseboat")
    housecar = unknown_candidates(view, "housecar")

    assert houseboat.status == housecar.status == "CANDIDATES"
    assert houseboat.candidates[0].kind == "KIN_NEIGHBOURHOOD"
    assert housecar.candidates[0].kind == "NO_REACH"


def test_entity_swap_changes_the_available_neighbourhood():
    roles = (("place", "house"), ("object", "boat"))
    boat_view = _view("house and boat", roles)
    car_view = _view("house and car", (("place", "house"), ("object", "car")))

    boat_report = unknown_candidates(boat_view, "houseboat")
    car_report = unknown_candidates(car_view, "houseboat")

    assert boat_report.candidates[0].kind == "KIN_NEIGHBOURHOOD"
    assert car_report.candidates[0].kind == "NO_REACH"


def test_known_entity_and_out_of_closure_compound_remain_distinct():
    view = _view("house and boat", (("place", "house"), ("object", "boat")))

    assert unknown_candidates(view, "house").status == "KNOWN_TERM"
    assert unknown_candidates(view, "houseboat").status == "CANDIDATES"
