import pytest

from verantyx.semantic_ir import (
    Budget,
    Clause,
    Meter,
    Operator,
    Output,
    Pattern,
    Plan,
    Role,
    Span,
    Variable,
    View,
)
from verantyx.semantic_verify import Checker, Conflict, Limit


SOVEREIGN = "archive"


def _view(documents):
    sources = {}
    clauses = []
    for source, facts, terminal in documents:
        pieces = []
        positions = []
        cursor = 0
        for index, (entity, value, polarity) in enumerate(facts):
            ending = "ではない" if polarity == "-" else "です"
            punctuation = "。" if index < len(facts) - 1 or terminal else ""
            sentence = f"{entity}は{value}{ending}{punctuation}"
            pieces.append(sentence)
            positions.append((cursor, sentence, entity, value, polarity))
            cursor += len(sentence)
        raw = "".join(pieces)
        sources[source] = raw
        for index, (start, sentence, entity, value, polarity) in enumerate(positions):
            entity_start = start
            value_start = start + len(entity) + 1
            entity_span = Span(source, entity_start, entity_start + len(entity), entity)
            value_span = Span(source, value_start, value_start + len(value), value)
            clause_span = Span(source, start, start + len(sentence), sentence)
            clauses.append(
                Clause(
                    id=f"{source}:{index}",
                    event=Variable(f"event-{source}-{index}", "event"),
                    predicate="identity",
                    predicate_span=value_span,
                    roles=(
                        Role("entity", entity, entity_span),
                        Role("value", value, value_span),
                    ),
                    span=clause_span,
                    polarity=polarity,
                    rule="copula",
                    sovereign=SOVEREIGN,
                    family=SOVEREIGN,
                )
            )

    return View(sources, tuple(clauses))


def _plan(*roles, outputs=None, polarity="+"):
    pattern = Pattern(
        "identity",
        tuple((name, Variable(var)) for name, var in roles),
        polarity=polarity,
    )
    bind = Operator("bind", "Bind", pattern=pattern)
    outputs = outputs or tuple((name, var) for name, var in roles)
    project = Operator(
        "project",
        "Project",
        inputs=("bind",),
        outputs=tuple(Output(label, Variable(var), "") for label, var in outputs),
    )
    return Plan((bind, project), "project")


def _audit(documents, plan=None, budget=None):
    checker = Checker(
        _view(documents),
        SOVEREIGN,
        Meter(budget or Budget()),
    )
    return checker.audit(plan or _plan(("entity", "entity")))


def test_duplicate_sentences_across_documents_yield_one_identical_answer():
    documents = [
        (f"copy-{index}", [("Aki", "Mika", "+")], True)
        for index in range(12)
    ]

    assert _audit(documents) == {(('entity', 'Aki'),)}


def test_repeated_sentences_in_one_long_document_keep_valid_offsets():
    facts = [("Aki", "Mika", "+")] * 40

    assert _audit([("long", facts, True)]) == {(('entity', 'Aki'),)}


def test_near_duplicate_entities_remain_distinct_across_one_document():
    facts = [(f"Aki{index:02d}", "Mika", "+") for index in range(48)]
    expected = {(('entity', entity),) for entity, _, _ in facts}

    assert _audit([("near-duplicates", facts, True)]) == expected


def test_applicable_opposite_evidence_from_another_document_conflicts():
    documents = [
        ("affirm", [("Aki", "Mika", "+")], True),
        ("deny", [("Aki", "Mika", "-")], True),
    ]

    with pytest.raises(Conflict):
        _audit(documents)


def test_opposite_evidence_for_a_different_entity_does_not_conflict():
    documents = [
        ("affirm", [("Aki", "Mika", "+")], True),
        ("deny", [("Ren", "Mika", "-")], True),
    ]

    assert _audit(documents) == {(('entity', 'Aki'),)}


def test_document_order_does_not_change_the_answer_set():
    documents = [
        ("first", [("Aki", "Mika", "+")], True),
        ("second", [("Ren", "Sora", "+")], True),
        ("third", [("Yui", "Hana", "+")], True),
    ]
    expected = {
        (('entity', 'Aki'),),
        (('entity', 'Ren'),),
        (('entity', 'Yui'),),
    }

    assert _audit(documents) == expected
    assert _audit(list(reversed(documents))) == expected


def test_very_long_entity_and_value_spans_are_licensed_exactly():
    entity = "甲" * 1200
    value = "乙" * 1200
    plan = _plan(("entity", "entity"), ("value", "value"))

    assert _audit([("oversized", [(entity, value, "+")], True)], plan) == {
        (('entity', entity), ('value', value))
    }


def test_final_unpunctuated_sentence_in_long_document_is_included():
    facts = [("Aki", "Mika", "+"), ("Ren", "Sora", "+")]
    expected = {(('entity', 'Aki'),), (('entity', 'Ren'),)}

    assert _audit([("open-ended", facts, False)]) == expected


def test_repeated_entity_with_distinct_values_keeps_both_answers():
    facts = [("Aki", "Mika", "+"), ("Aki", "Sora", "+")] * 12
    plan = _plan(("entity", "entity"), ("value", "value"))

    assert _audit([("reused-name", facts, True)], plan) == {
        (('entity', 'Aki'), ('value', 'Mika')),
        (('entity', 'Aki'), ('value', 'Sora')),
    }


def test_candidate_budget_reports_large_document_collections_cleanly():
    documents = [
        (f"doc-{index}", [(f"Aki{index:03d}", "Mika", "+")], True)
        for index in range(257)
    ]

    with pytest.raises(Limit, match="candidates"):
        _audit(documents)
