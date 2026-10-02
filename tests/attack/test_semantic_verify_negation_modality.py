import pytest

from verantyx.semantic_ir import (
    Budget,
    Clause,
    Meter,
    Operator,
    Output,
    Pattern,
    Plan,
    Span,
    Variable,
)
from verantyx.semantic_reader import document_view
from verantyx.semantic_verify import Checker, Rejected, _match, license_clause


def _audit_whether(text, predicate, roles=()):
    view = document_view({"source": text})
    answer = Variable("answer", "value")
    bind = Operator(
        id="bind",
        op="Bind",
        pattern=Pattern(predicate, roles, "*", "assert", "nonpast"),
        target=answer,
        relation="whether",
    )
    project = Operator(
        id="project",
        op="Project",
        inputs=("bind",),
        outputs=(Output("answer", answer, "answer-obligation"),),
        obligations=("answer-obligation",),
    )
    plan = Plan((bind, project), "project")
    answers = Checker(view, "document", Meter(Budget())).audit(plan)
    return answers, view


def test_explicit_event_negation_is_licensed_as_negative():
    view = document_view({"source": "太郎は来ない。"})
    clause, = view.clauses

    assert (clause.predicate, clause.polarity, clause.modality) == ("来る", "-", "assert")
    license_clause(clause, view)


def test_explicit_negative_copula_is_licensed_as_negative():
    view = document_view({"source": "東京は大阪ではない。"})
    clause, = view.clauses

    assert (clause.predicate, clause.polarity) == ("identity", "-")
    license_clause(clause, view)


def test_positive_copula_remains_positive():
    view = document_view({"source": "東京は大阪だ。"})
    clause, = view.clauses

    assert (clause.predicate, clause.polarity) == ("identity", "+")
    license_clause(clause, view)


def test_double_negation_is_not_licensed_as_an_ordinary_negative_fact():
    view = document_view({"source": "太郎は走らなくはない。"})
    assert view.clauses

    for clause in view.clauses:
        with pytest.raises(Rejected):
            license_clause(clause, view)


def test_interrogative_does_not_produce_a_yes_no_answer():
    answers, view = _audit_whether("太郎は来るか。", "来る", (("agent", "太郎"),))

    assert not answers
    assert any("interrogative" in item.reason for item in view.unread)


def test_hearsay_clause_is_not_licensed_as_an_assertion():
    view = document_view({"source": "太郎は来るそうだ。"})
    assert view.clauses
    assert all(clause.modality == "assert" for clause in view.clauses)

    for clause in view.clauses:
        with pytest.raises(Rejected):
            license_clause(clause, view)


def test_permission_and_prohibition_patterns_stay_modally_distinct():
    text = "走る"
    span = Span("source", 0, len(text), text)

    def clause(modality):
        return Clause(
            id=modality,
            event=Variable("event", "event"),
            predicate="走る",
            predicate_span=span,
            roles=(),
            span=span,
            body_span=span,
            polarity="+",
            modality=modality,
            time="nonpast",
            rule="frame",
        )

    normative = Pattern("走る", (), "+", "normative", "nonpast")
    permission = clause("permission")
    prohibition = clause("prohibition")

    assert _match(normative, permission) == {}
    assert _match(normative, prohibition) == {}
    assert _match(Pattern("走る", (), "+", "permission", "nonpast"), prohibition) is None
    assert _match(Pattern("走る", (), "+", "prohibition", "nonpast"), permission) is None


def test_unsupported_permission_and_prohibition_are_not_licensed_as_facts():
    examples = (
        ("太郎は入ってもよい。", "permission"),
        ("走ってはいけない。", "prohibition"),
    )

    for text, modality in examples:
        view = document_view({"source": text})
        clauses = [clause for clause in view.clauses if clause.modality == modality]
        assert clauses
        for clause in clauses:
            with pytest.raises(Rejected):
                license_clause(clause, view)


def test_explicit_no_and_missing_evidence_remain_distinct():
    roles = (("agent", "太郎"),)
    yes, _ = _audit_whether("太郎は来る。", "来る", roles)
    no, _ = _audit_whether("太郎は来ない。", "来る", roles)
    unknown, _ = _audit_whether("", "来る", roles)

    assert yes == {(('answer', True),)}
    assert no == {(('answer', False),)}
    assert unknown == set()


@pytest.mark.parametrize("text,predicate", (("走るな。", "走る"), ("触るな。", "触る")))
@pytest.mark.xfail(strict=False, reason="DEFECT: imperative prohibition is accepted as a positive assertion")
def test_imperative_prohibition_does_not_answer_a_factual_whether_question(text, predicate):
    answers, _ = _audit_whether(text, predicate)

    assert answers == set()


@pytest.mark.parametrize("text", ("水は冷たくない。", "部屋は暗くない。"))
@pytest.mark.xfail(strict=False, reason="DEFECT: negative ない-adjective is licensed as positive identity")
def test_negative_adjective_is_not_licensed_as_a_positive_identity(text):
    view = document_view({"source": text})
    clause, = view.clauses

    with pytest.raises(Rejected):
        license_clause(clause, view)
