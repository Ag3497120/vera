from decimal import Decimal

import pytest

from verantyx.semantic_measure import read_measure_request, read_measure_sentence


def _sentence(text):
    return read_measure_sentence("doc", text, 0, 0, len(text), True, "attack")


def _roles(clause):
    return {role.name: role.term for role in clause.roles}


class _Builder:
    def __init__(self):
        self.roots = []
        self.nodes = []
        self.patterns = []
        self.obligations = []
        self.outputs = []
        self.projected = None

    def variable(self, kind):
        return f"{kind}_{len(self.patterns)}_{len(self.nodes)}"

    def bind(self, pattern, span):
        self.patterns.append((pattern, span))
        self.roots.append(f"root_{len(self.roots)}")

    def obligation(self, ident, kind, span, evidence):
        item = (ident, kind, span, evidence)
        self.obligations.append(item)
        return item

    def project(self, ident):
        self.projected = ident
        return ("projected", ident)


def _request(text):
    builder = _Builder()
    full = object()
    result = read_measure_request(text, builder, full)
    return builder, result


def _has_operator(node, name):
    return f"'{name}'" in repr(node)


def test_polite_and_plain_measure_sentences_preserve_exact_decimal():
    plain = _sentence("箱Aは1.20m")
    polite = _sentence("箱Aは1.20mです。")

    assert len(plain) == len(polite) == 1
    for clause in (plain[0], polite[0]):
        assert clause.predicate == "measure.length"
        assert _roles(clause)["value"].amount == Decimal("1.20")
        assert _roles(clause)["label"] == "A"


@pytest.mark.parametrize("particle", ["は", "が", "に", "も"])
def test_measure_particle_variants_keep_the_same_quantity(particle):
    clauses = _sentence(f"箱A{particle}3.5kgです")

    assert len(clauses) == 1
    assert clauses[0].predicate == "measure.mass"
    assert _roles(clauses[0])["value"].amount == Decimal("3.5")
    assert _roles(clauses[0])["value"].unit == "kg"
    assert _roles(clauses[0])["label"] == "A"


def test_reordering_entities_keeps_each_entity_attached_to_its_number():
    forward = _sentence("箱Aは1m、箱Bが2m")
    reversed_order = _sentence("箱Bが2m、箱Aは1m")

    assert [(_roles(c)["entity"], _roles(c)["value"].amount) for c in forward] == [
        ("箱A", Decimal("1")), ("箱B", Decimal("2"))]
    assert [(_roles(c)["entity"], _roles(c)["value"].amount) for c in reversed_order] == [
        ("箱B", Decimal("2")), ("箱A", Decimal("1"))]


def test_shared_head_noun_is_attached_to_each_measure():
    clauses = _sentence("箱Aは1m、箱Bが2mの棒です。")

    assert len(clauses) == 2
    assert [_roles(clause)["substance"] for clause in clauses] == ["棒", "棒"]


def test_measure_sentence_must_be_consumed_completely():
    assert _sentence("箱Aは1mです。余分な説明") is None


def test_polite_and_plain_sum_questions_build_the_same_sum_shape():
    plain, plain_result = _request("合計は何m")
    polite, polite_result = _request("合計はいくつmですか？")

    for builder, result in ((plain, plain_result), (polite, polite_result)):
        assert result == ("projected", builder.projected)
        assert len(builder.roots) == 2
        assert len(builder.nodes) == 3
        assert _has_operator(builder.nodes[-1], "Sum")
        assert builder.nodes[-1].unit == "m"
        assert len(builder.nodes[-1].terms) == 2


def test_sum_unit_swap_changes_the_requested_dimension_and_output_unit():
    builder, _ = _request("合計は何kgですか")

    assert "measure.mass" in repr(builder.patterns)
    assert _has_operator(builder.nodes[-1], "Sum")
    assert builder.nodes[-1].unit == "kg"


@pytest.mark.parametrize("question", ["長い猫は？", "どちらが長いですか？", "長い方は？"])
def test_longer_question_word_order_variants_keep_greater_comparison(question):
    builder, result = _request(question)

    assert result == ("projected", builder.projected)
    assert _has_operator(builder.nodes[-1], "Compare")
    assert builder.nodes[-1].relation == ">"
    assert len(builder.nodes[-1].terms) == 2


def test_changed_comparison_word_changes_the_relation():
    longer, _ = _request("長い方は？")
    shorter, _ = _request("短い方は？")

    assert longer.nodes[-1].relation == ">"
    assert shorter.nodes[-1].relation == "<"


def test_same_and_equal_paraphrases_match_but_different_changes_relation():
    same, _ = _request("長さは同じですか")
    equal, _ = _request("長さは等しい？")
    different, _ = _request("長さは違うですか")

    assert same.nodes[-1].relation == equal.nodes[-1].relation == "="
    assert different.nodes[-1].relation == "!="


def test_unrecognized_measure_question_is_left_unhandled():
    builder, result = _request("どの箱がいちばん長いですか")

    assert result is None
    assert builder.nodes == []
    assert builder.roots == []
