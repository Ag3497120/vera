from dataclasses import replace
from decimal import Decimal

import pytest

from verantyx.semantic_ir import Meter, Operator, Output, Pattern, Plan, Quantity, Variable
from verantyx.semantic_reader import document_view, read_request
from verantyx.semantic_verify import Checker, Rejected


def _event_answers(document, question):
    view = document_view({"source": document})
    request = read_request(question)
    assert len(request.plans) == 1
    assert not request.unread
    return Checker(view, "document", Meter()).audit(request.plans[0])


def _quantity_plan(entity="りんご"):
    quantity = Variable("q", "quantity")
    pattern = Pattern(
        "measure.counter:個",
        (("entity", entity), ("value", quantity)),
    )
    return Plan(
        (
            Operator("bind", "Bind", pattern=pattern),
            Operator(
                "project",
                "Project",
                inputs=("bind",),
                outputs=(Output("amount", quantity, "o", unit="個"),),
            ),
        ),
        "project",
    )


def _quantity_answers(document, entity="りんご"):
    view = document_view({"source": document})
    return Checker(view, "document", Meter()).audit(_quantity_plan(entity))


def test_plain_event_statement_supports_matching_question():
    assert _event_answers("太郎は図書館に行った。", "太郎は図書館に行った？") == {
        (("可否", True),)
    }


def test_polite_question_preserves_event_verdict():
    assert _event_answers("太郎は図書館に行った。", "太郎は図書館に行きましたか？") == {
        (("可否", True),)
    }


def test_polite_source_preserves_event_verdict():
    assert _event_answers("太郎は図書館に行きました。", "太郎は図書館に行った？") == {
        (("可否", True),)
    }


def test_subject_particle_variant_preserves_event_verdict():
    assert _event_answers("太郎が図書館に行った。", "太郎は図書館に行きましたか？") == {
        (("可否", True),)
    }


def test_destination_particle_variant_preserves_event_verdict():
    assert _event_answers("太郎は図書館へ行った。", "太郎は図書館に行った？") == {
        (("可否", True),)
    }


def test_coherent_entity_swap_preserves_verdict():
    assert _event_answers("花子は学校に行った。", "花子は学校に行きましたか？") == {
        (("可否", True),)
    }


def test_changed_entity_does_not_match():
    assert _event_answers("花子は図書館に行った。", "太郎は図書館に行った？") == set()


def test_changed_destination_does_not_match():
    assert _event_answers("太郎は図書館に行った。", "太郎は学校に行った？") == set()


def test_explicit_negation_changes_verdict_to_false():
    assert _event_answers("太郎は図書館に行かなかった。", "太郎は図書館に行った？") == {
        (("可否", False),)
    }


def test_time_mismatch_remains_unanswered_instead_of_false():
    assert _event_answers("太郎は図書館に行く。", "太郎は図書館に行った？") == set()


def test_measure_subject_particle_variant_preserves_quantity():
    expected = {(('amount', Quantity(Decimal("3"), "個")),)}
    assert _quantity_answers("りんごは3個。") == expected
    assert _quantity_answers("りんごが3個。") == expected


def test_changed_measure_number_changes_projected_quantity():
    three = {(('amount', Quantity(Decimal("3"), "個")),)}
    four = {(('amount', Quantity(Decimal("4"), "個")),)}
    assert _quantity_answers("りんごは3個。") == three
    assert _quantity_answers("りんごは4個。") == four


def test_changed_measure_entity_does_not_match():
    assert _quantity_answers("みかんは3個。") == set()


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: reordered locative topic for 行く is rejected as a different predicate",
)
def test_reordered_event_source_keeps_same_frame_verdict():
    source = "図書館に太郎が行った。"
    view = document_view({"source": source})
    clause = replace(view.clauses[0], predicate="行く")
    view = replace(view, clauses=(clause,))
    request = read_request("太郎は図書館に行った？")
    expected = {(("可否", True),)}
    checker = Checker(view, "document", Meter())

    observed = []
    for _ in range(2):
        try:
            observed.append(checker.audit(request.plans[0]))
        except Rejected as exc:
            observed.append(exc)
    assert observed == [expected, expected]
