from dataclasses import fields
from decimal import Decimal

import pytest

from verantyx.semantic_ir import Span, Variable
from verantyx.semantic_measure import read_measure_request, read_measure_sentence


def _read(source, raw):
    return read_measure_sentence(source, raw, 0, 0, len(raw), True, "measure")


def _role(clause, name):
    return next(role for role in clause.roles if role.name == name)


def _term(clause, name):
    return _role(clause, name).term


class _Builder:
    """Small typed-IR capture for checking the request expansion contract."""

    def __init__(self):
        self.roots = []
        self.nodes = []
        self.outputs = []
        self.bindings = []
        self._variables = 0

    def variable(self, sort):
        self._variables += 1
        return Variable(f"{sort}_{self._variables}", sort)

    def bind(self, pattern, span):
        self.bindings.append((pattern, span))
        self.roots.append(f"root_{len(self.roots)}")

    def obligation(self, ident, kind, span, detail):
        return f"{ident}_{kind}_{detail}"

    def project(self, ident):
        return ident


def _operator_kind(node):
    for item in fields(node):
        value = getattr(node, item.name)
        if isinstance(value, str) and value in {"Join", "Filter", "Sum", "Compare"}:
            return value
    return None


def _question(raw):
    builder = _Builder()
    span = Span("question", 0, len(raw), raw)
    assert read_measure_request(raw, builder, span) is not None
    return builder


def test_reads_every_segment_and_preserves_decimal_values():
    raw = "りんごAは1.20kg、りんごBは2.005kgです。"
    clauses = _read("doc-a", raw)

    assert len(clauses) == 2
    assert [_term(clause, "value").amount for clause in clauses] == [
        Decimal("1.20"), Decimal("2.005")
    ]
    assert [_term(clause, "value").unit for clause in clauses] == ["kg", "kg"]


def test_shared_head_noun_is_attached_to_each_segment():
    clauses = _read("doc-noun", "りんごAは1kg、りんごBは2kgの果物です。")

    assert len(clauses) == 2
    assert [_term(clause, "substance") for clause in clauses] == ["果物", "果物"]
    assert all(_role(clause, "substance").span.text == "果物" for clause in clauses)


def test_very_long_measure_sentence_keeps_all_segments_in_order():
    count = 300
    raw = "、".join(f"品{index}は{index}.001m" for index in range(count)) + "。"
    clauses = _read("doc-long", raw)

    assert len(clauses) == count
    assert [_term(clause, "value").amount for clause in clauses[:3]] == [
        Decimal("0.001"), Decimal("1.001"), Decimal("2.001")
    ]
    assert _term(clauses[-1], "entity") == "品299"
    assert _term(clauses[-1], "value").amount == Decimal("299.001")


def test_conflicting_values_from_two_documents_remain_separate():
    left = _read("doc-left", "樹Aは12.5m。")
    right = _read("doc-right", "樹Aは13m。")

    assert len(left) == len(right) == 1
    assert left[0].id != right[0].id
    assert _term(left[0], "value").amount == Decimal("12.5")
    assert _term(right[0], "value").amount == Decimal("13")
    assert left[0].sovereign == right[0].sovereign is True


def test_duplicate_sentences_from_different_documents_keep_distinct_clause_ids():
    raw = "湖Aは4km。"
    first = _read("doc-one", raw)
    second = _read("doc-two", raw)

    assert first[0].id != second[0].id
    assert _term(first[0], "value") == _term(second[0], "value")
    assert first[0].body_span.text == second[0].body_span.text == raw


def test_near_duplicate_with_unconsumed_text_is_rejected_as_a_whole():
    raw = "箱Aは1m、箱Bは2mおよび箱Cは3m。"

    assert _read("doc-near", raw) is None


def test_long_decimal_is_exact_without_binary_float_conversion():
    raw = "測定Aは9007199254740993.000000000000000001m。"
    clauses = _read("doc-decimal", raw)

    assert len(clauses) == 1
    assert _term(clauses[0], "value").amount == Decimal(
        "9007199254740993.000000000000000001"
    )


def test_sum_question_expands_to_two_length_bindings_and_sum_in_requested_unit():
    builder = _question("合計は何mですか？")

    assert len(builder.bindings) == 2
    assert all(pattern.predicate == "measure.length" for pattern, _ in builder.bindings)
    sum_node = next(node for node in builder.nodes if _operator_kind(node) == "Sum")
    bound_values = tuple(dict(pattern.roles)["value"] for pattern, _ in builder.bindings)
    assert sum_node.terms == bound_values
    assert sum_node.unit == "m"
    assert sum_node.target.sort == "quantity"


def test_longest_question_compares_quantities_and_projects_the_selected_labels():
    builder = _question("どちらが長いですか？")

    assert len(builder.bindings) == 2
    assert all(pattern.predicate == "measure.length" for pattern, _ in builder.bindings)
    compare = next(node for node in builder.nodes if _operator_kind(node) == "Compare")
    bound_values = tuple(dict(pattern.roles)["value"] for pattern, _ in builder.bindings)
    bound_labels = tuple(dict(pattern.roles)["label"] for pattern, _ in builder.bindings)
    assert compare.terms == bound_values
    assert compare.choices == bound_labels
    assert compare.relation == ">"
    assert compare.target.sort == "entity"


def test_kind_qualified_heaviness_question_binds_mass_of_that_kind():
    builder = _question("重い犬は？")

    assert len(builder.bindings) == 2
    assert all(pattern.predicate == "measure.mass" for pattern, _ in builder.bindings)
    assert all(dict(pattern.roles)["kind"] == "犬" for pattern, _ in builder.bindings)
    compare = next(node for node in builder.nodes if _operator_kind(node) == "Compare")
    assert compare.relation == ">"


@pytest.mark.parametrize(
    ("question", "dimension", "relation"),
    [("長さは違う？", "length", "!="), ("重さは同じですか？", "mass", "=")],
)
def test_same_different_questions_expand_to_dimensioned_equality(question, dimension, relation):
    builder = _question(question)

    assert len(builder.bindings) == 2
    assert all(pattern.predicate == f"measure.{dimension}" for pattern, _ in builder.bindings)
    compare = next(node for node in builder.nodes if _operator_kind(node) == "Compare")
    assert compare.relation == relation
    assert compare.target.sort == "value"
