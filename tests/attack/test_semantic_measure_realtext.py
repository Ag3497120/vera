from decimal import Decimal

from verantyx.semantic_measure import read_measure_request, read_measure_sentence


def _read(raw):
    return read_measure_sentence("source", raw, 0, 0, len(raw), "sovereign", "family")


def _term(clause, name):
    return next(role.term for role in clause.roles if role.name == name)


class _Builder:
    def __init__(self):
        self.roots = []
        self.nodes = []
        self.outputs = []
        self.bindings = []
        self.obligations = []
        self.serial = 0

    def variable(self, sort):
        self.serial += 1
        return sort, self.serial

    def bind(self, pattern, span):
        self.roots.append("root-" + str(len(self.roots)))
        self.bindings.append((pattern, span))

    def obligation(self, ident, kind, span, reason):
        self.obligations.append((ident, kind, span, reason))
        return "obligation-" + ident

    def project(self, root):
        return {
            "root": root,
            "nodes": tuple(self.nodes),
            "outputs": tuple(self.outputs),
            "bindings": tuple(self.bindings),
            "obligations": tuple(self.obligations),
        }


def test_decimal_amount_and_source_spans_are_preserved():
    raw = "棒Aは1.20m。"
    clauses = _read(raw)

    assert len(clauses) == 1
    clause = clauses[0]
    quantity = _term(clause, "value")
    assert quantity.amount == Decimal("1.20")
    assert quantity.amount.as_tuple().exponent == -2
    assert quantity.unit == "m"
    assert clause.predicate == "measure.length"
    assert clause.predicate_span.text == "は"
    assert _term(clause, "label") == "A"
    assert clause.body_span.text == raw


def test_two_measure_segments_keep_each_exact_quantity():
    clauses = _read("棒Aは1.25m、棒Bは2.5m。")

    assert [c.predicate for c in clauses] == ["measure.length", "measure.length"]
    assert [_term(c, "value").amount for c in clauses] == [Decimal("1.25"), Decimal("2.5")]
    assert [_term(c, "label") for c in clauses] == ["A", "B"]
    assert all(c.body_span.text == "棒Aは1.25m、棒Bは2.5m。" for c in clauses)


def test_shared_head_noun_is_attached_to_every_segment():
    clauses = _read("容器Aは1L、容器Bは2Lの水です")

    assert len(clauses) == 2
    assert [_term(c, "substance") for c in clauses] == ["水", "水"]
    assert all(c.predicate == "measure.volume" for c in clauses)


def test_unit_dimensions_follow_the_ir_unit_types():
    length = _read("棒Aが2cm")
    mass = _read("荷物Aが1.5kg")

    assert length[0].predicate == "measure.length"
    assert _term(length[0], "value").unit == "cm"
    assert mass[0].predicate == "measure.mass"
    assert _term(mass[0], "value").unit == "kg"
    assert _term(mass[0], "value").amount == Decimal("1.5")


def test_unconsumed_prose_is_not_returned_as_a_measure():
    assert _read("棒Aは1mで、たぶん長い") is None


def test_signed_and_scientific_notation_are_not_silently_read():
    assert _read("棒Aは-1m") is None
    assert _read("棒Aは1e3m") is None


def test_incomplete_list_is_rejected_as_a_whole():
    assert _read("棒Aは1m、") is None


def test_sum_question_builds_two_input_sum_in_requested_unit():
    builder = _Builder()
    plan = read_measure_request("合計は何mですか", builder, "question-span")

    assert [node.op for node in plan["nodes"]] == ["Join", "Filter", "Sum"]
    operation = plan["nodes"][-1]
    assert operation.unit == "m"
    assert operation.terms[0] != operation.terms[1]
    assert [pattern.predicate for pattern, _ in plan["bindings"]] == [
        "measure.length",
        "measure.length",
    ]
    assert plan["outputs"][0][0] == "計算結果"


def test_mass_comparison_uses_mass_and_the_heavier_relation():
    builder = _Builder()
    plan = read_measure_request("重い箱は？", builder, "question-span")

    assert [pattern.predicate for pattern, _ in plan["bindings"]] == [
        "measure.mass",
        "measure.mass",
    ]
    assert [pattern.roles[-1][1] for pattern, _ in plan["bindings"]] == ["箱", "箱"]
    assert plan["nodes"][-1].op == "Compare"
    assert plan["nodes"][-1].relation == ">"


def test_same_and_different_questions_keep_the_requested_relation():
    same = read_measure_request("長さは同じですか", _Builder(), "question-span")
    different = read_measure_request("長さは違う？", _Builder(), "question-span")

    assert same["nodes"][-1].relation == "="
    assert different["nodes"][-1].relation == "!="
    assert same["nodes"][-1].terms == different["nodes"][-1].terms


def test_unrecognized_question_does_not_mutate_the_builder():
    builder = _Builder()

    assert read_measure_request("だいたい何メートル？", builder, "question-span") is None
    assert builder.nodes == []
    assert builder.bindings == []
    assert builder.outputs == []
