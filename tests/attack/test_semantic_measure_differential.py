from decimal import Decimal
from itertools import product

import pytest

from verantyx import semantic_measure
from verantyx.semantic_ir import Variable


# The reference deliberately supports a small closed set of units whose
# dimensions are part of the measure contract. It does not call the parser.
_REFERENCE_DIMENSION = {"kg": "mass", "g": "mass", "m": "length", "cm": "length"}
_REFERENCE_PARTICLES = "はがにも"


def _reference_segments(raw, left=0, right=None):
    """Naive character scanner for generated, deliberately simple sentences."""
    if right is None:
        right = len(raw)
    text = raw[left:right]
    while text and text[-1] in "。！？!?":
        text = text[:-1]
    if not text:
        return None

    expected = []
    for segment in text.split("、"):
        particle_at = next((i for i, char in enumerate(segment) if char in _REFERENCE_PARTICLES), None)
        if particle_at is None or particle_at == 0:
            return None
        label = segment[:particle_at]
        number_at = particle_at + 1
        number_end = number_at
        while number_end < len(segment) and segment[number_end].isdigit() and segment[number_end].isascii():
            number_end += 1
        if number_end < len(segment) and segment[number_end] == ".":
            number_end += 1
            fraction_at = number_end
            while number_end < len(segment) and segment[number_end].isdigit() and segment[number_end].isascii():
                number_end += 1
            if number_end == fraction_at:
                return None
        if number_end == number_at:
            return None
        number = segment[number_at:number_end]
        unit = segment[number_end:]
        if unit not in _REFERENCE_DIMENSION:
            return None

        kind = None
        answer = label
        if label and label[-1].isascii() and label[-1].isalpha() and len(label) > 1:
            kind, answer = label[:-1], label[-1]
        elif label and label[-1].isascii() and label[-1].isdigit():
            split_at = len(label)
            while split_at and label[split_at - 1].isascii() and label[split_at - 1].isdigit():
                split_at -= 1
            if split_at and not label[split_at - 1].isascii():
                kind = label[:split_at]

        absolute = left
        expected.append({
            "label": label,
            "answer": answer,
            "kind": kind,
            "particle": segment[particle_at],
            "amount": Decimal(number),
            "unit": unit,
            "dimension": _REFERENCE_DIMENSION[unit],
            "label_start": absolute,
            "particle_start": absolute + particle_at,
            "number_start": absolute + number_at,
            "value_end": absolute + len(segment),
        })
        left += len(segment) + 1
    return expected


def _role(clause, name):
    return next(role for role in clause.roles if role.name == name)


def _assert_matches_reference(raw, clauses, expected, source="src", body=None):
    if body is None:
        body = raw
    assert len(clauses) == len(expected)
    for clause, item in zip(clauses, expected):
        assert clause.predicate == "measure." + item["dimension"]
        assert clause.rule == "measure"
        assert clause.span.text == body
        assert clause.body_span.text == body
        assert clause.predicate_span.text == item["particle"]
        assert clause.predicate_span.start == item["particle_start"]
        assert clause.predicate_span.source == source

        entity = _role(clause, "entity")
        label = _role(clause, "label")
        value = _role(clause, "value")
        assert entity.term == item["label"]
        assert entity.span.text == item["label"]
        assert entity.span.start == item["label_start"]
        assert label.term == item["answer"]
        assert value.term.amount == item["amount"]
        assert value.term.amount.as_tuple() == item["amount"].as_tuple()
        assert value.term.unit == item["unit"]
        assert value.span.text == raw[item["number_start"]:item["value_end"]]
        assert value.span.start == item["number_start"]
        assert value.span.end == item["value_end"]
        if item["kind"] is not None:
            kind = _role(clause, "kind")
            assert kind.term == item["kind"]
            assert kind.span.text == item["kind"]


def test_generated_sentences_match_independent_reference():
    labels = ("猫", "りんごA", "箱12")
    numbers = ("0", "2.50", "17", "999.9")
    units = ("kg", "g", "m", "cm")
    cases = [f"{label}は{number}{unit}。" for label, number, unit in product(labels, numbers, units)]
    assert len(cases) == 48
    for raw in cases:
        expected = _reference_segments(raw)
        clauses = semantic_measure.read_measure_sentence("src", raw, 0, 0, len(raw), True, "family")
        assert expected is not None
        _assert_matches_reference(raw, clauses, expected)


def test_list_sentences_keep_exact_amounts_and_shared_head_noun():
    raw = "りんごAは1.20kg、箱12は3.000gの水。"
    clauses = semantic_measure.read_measure_sentence("src", raw, 0, 0, len(raw), True, "family")
    assert len(clauses) == 2
    assert [_role(clause, "value").term.amount.as_tuple() for clause in clauses] == [
        Decimal("1.20").as_tuple(), Decimal("3.000").as_tuple()
    ]
    assert [_role(clause, "substance").term for clause in clauses] == ["水", "水"]
    assert [_role(clause, "substance").span.text for clause in clauses] == ["水", "水"]
    assert [_role(clause, "entity").term for clause in clauses] == ["りんごA", "箱12"]


def test_sentence_slice_offsets_stay_inside_original_source():
    prefix = "前置き。"
    body = "箱12が0.040kg。"
    raw = prefix + body + "後続"
    left = len(prefix)
    right = left + len(body)
    clauses = semantic_measure.read_measure_sentence("doc", raw, left, left, right, False, "f")
    expected = _reference_segments(raw, left, right)
    _assert_matches_reference(raw, clauses, expected, source="doc", body=body)
    assert _role(clauses[0], "entity").span.start == left
    assert _role(clauses[0], "value").span.start == raw.index("0.040")


@pytest.mark.parametrize("raw", [
    "猫は1kg余計な語。",
    "猫はkg。",
    "猫は1.kg。",
    "猫は-1kg。",
    "猫は1,000g。",
    "猫は1kg、",
])
def test_sentence_reader_rejects_unconsumed_or_malformed_text(raw):
    assert semantic_measure.read_measure_sentence("src", raw, 0, 0, len(raw), True, "f") is None


class _TraceBuilder:
    """Small plan sink implementing only the interface used by this reader."""

    def __init__(self):
        self.roots = []
        self.nodes = []
        self.outputs = []
        self.patterns = []
        self.obligations = []
        self._variables = 0

    def variable(self, sort):
        value = Variable(f"v{self._variables}", sort)
        self._variables += 1
        return value

    def bind(self, pattern, span):
        self.patterns.append((pattern, span))
        self.roots.append(f"root{len(self.roots)}")

    def obligation(self, ident, category, span, detail):
        value = f"obligation{len(self.obligations)}"
        self.obligations.append((ident, category, span, detail, value))
        return value

    def project(self, node):
        return ("project", node)


def _reference_question(text):
    """Reference the finite documented question shapes by explicit cases."""
    exact = {
        "合計は何kgですか": {"op": "Sum", "dimension": "mass", "relation": "", "unit": "kg", "output": "計算結果", "sort": "quantity"},
        "合計は何cmですか": {"op": "Sum", "dimension": "length", "relation": "", "unit": "cm", "output": "計算結果", "sort": "quantity"},
        "長い箱は": {"op": "Compare", "dimension": "length", "relation": ">", "unit": "", "output": "比較結果", "sort": "entity", "kind": "箱"},
        "どちらが重いですか": {"op": "Compare", "dimension": "mass", "relation": ">", "unit": "", "output": "比較結果", "sort": "entity"},
        "短い方は": {"op": "Compare", "dimension": "length", "relation": "<", "unit": "", "output": "比較結果", "sort": "entity"},
        "軽い方は": {"op": "Compare", "dimension": "mass", "relation": "<", "unit": "", "output": "比較結果", "sort": "entity"},
        "長さは違うですか": {"op": "Compare", "dimension": "length", "relation": "!=", "unit": "", "output": "可否", "sort": "value"},
        "重さは同じですか": {"op": "Compare", "dimension": "mass", "relation": "=", "unit": "", "output": "可否", "sort": "value"},
        "長さは等しいですか": {"op": "Compare", "dimension": "length", "relation": "=", "unit": "", "output": "可否", "sort": "value"},
    }
    return exact.get(text)


def _question_cases():
    return (
        "合計は何kgですか", "合計は何cmですか", "長い箱は", "どちらが重いですか",
        "短い方は", "軽い方は", "長さは違うですか", "重さは同じですか", "長さは等しいですか",
    )


@pytest.mark.parametrize("text", _question_cases())
def test_generated_question_shapes_match_reference_plan(text):
    expected = _reference_question(text)
    builder = _TraceBuilder()
    result = semantic_measure.read_measure_request(text, builder, "question-span")

    assert expected is not None
    assert result == ("project", "n2")
    assert [node.op for node in builder.nodes] == ["Join", "Filter", expected["op"]]
    join, distinct_filter, operation = builder.nodes
    assert join.inputs == ("root0", "root1")
    assert distinct_filter.tests[0].relation == "!="
    assert distinct_filter.tests[0].left.sort == "entity"
    assert distinct_filter.tests[0].right.sort == "entity"
    assert operation.relation == expected["relation"]
    assert operation.unit == expected["unit"]
    assert operation.target.sort == expected["sort"]
    assert len(operation.terms) == 2
    assert all(term.sort == "quantity" for term in operation.terms)
    assert [pattern.predicate for pattern, _span in builder.patterns] == [
        "measure." + expected["dimension"], "measure." + expected["dimension"]
    ]
    role_names = [tuple(name for name, _variable in pattern.roles) for pattern, _span in builder.patterns]
    if "kind" in expected:
        assert role_names == [("entity", "label", "value", "kind")] * 2
    else:
        assert role_names == [("entity", "label", "value")] * 2
    assert builder.outputs == [(expected["output"], operation.target, "question-span", expected["unit"])]


@pytest.mark.parametrize("text", ["合計は何mmですか", "長さは同じか", "いちばん長いのは？", "合計は何kg? 余計"])
def test_out_of_scope_question_shapes_are_not_expanded(text):
    builder = _TraceBuilder()
    before = (list(builder.roots), list(builder.nodes), list(builder.outputs), list(builder.patterns))
    assert semantic_measure.read_measure_request(text, builder, "span") is None
    assert (builder.roots, builder.nodes, builder.outputs, builder.patterns) == before


def test_request_plan_requires_two_distinct_entities_before_operation():
    builder = _TraceBuilder()
    semantic_measure.read_measure_request("合計は何kgですか", builder, "span")
    distinct_filter = builder.nodes[1]
    assert distinct_filter.op == "Filter"
    assert len(distinct_filter.tests) == 1
    assert distinct_filter.tests[0].relation == "!="
    assert builder.nodes[2].op == "Sum"
    assert builder.nodes[2].inputs == (distinct_filter.id,)
