from decimal import Decimal

import pytest

from verantyx import semantic_measure as measure


def _read(raw):
    return measure.read_measure_sentence("unicode", raw, 0, 0, len(raw), "source", "family")


def _role(clause, name):
    return next(role for role in clause.roles if role.name == name)


class _Builder:
    def __init__(self):
        self.roots = []
        self.nodes = []
        self.outputs = []
        self.serial = 0

    def variable(self, sort):
        self.serial += 1
        return measure.Variable(f"v{self.serial}", sort)

    def bind(self, pattern, span):
        self.roots.append(f"root{len(self.roots)}")

    def obligation(self, *args):
        return f"obligation{len(self.nodes)}"

    def project(self, node):
        return "projected"


def test_ascii_measures_keep_decimal_values_and_unit_spans():
    raw = "りんごは0.1kg、みかんは0.20kg"

    clauses = _read(raw)

    assert len(clauses) == 2
    assert clauses[0].predicate == "measure.mass"
    assert _role(clauses[0], "value").term.amount == Decimal("0.1")
    assert _role(clauses[1], "value").term.amount == Decimal("0.20")
    assert _role(clauses[0], "value").span.text == "0.1kg"


@pytest.mark.parametrize("raw", ["りんごは３kg", "りんごは3．5kg"])
def test_fullwidth_digits_and_decimal_separator_are_refused(raw):
    assert _read(raw) is None


def test_compatibility_unit_glyph_is_refused():
    assert _read("りんごは3㎏") is None


def test_combining_mark_in_label_is_preserved_without_normalization():
    raw = "カ\u3099ラスは3kg"

    clauses = _read(raw)

    assert len(clauses) == 1
    assert _role(clauses[0], "entity").term == "カ\u3099ラス"
    assert _role(clauses[0], "entity").span.text == "カ\u3099ラス"


def test_halfwidth_katakana_label_is_preserved():
    raw = "ｶﾀｶﾅは2m"

    clauses = _read(raw)

    assert len(clauses) == 1
    assert clauses[0].predicate == "measure.length"
    assert _role(clauses[0], "entity").term == "ｶﾀｶﾅ"


def test_zero_width_character_in_label_is_preserved():
    raw = "り\u200bんごは3kg"

    clauses = _read(raw)

    assert len(clauses) == 1
    assert _role(clauses[0], "entity").term == "り\u200bんご"
    assert _role(clauses[0], "entity").span.text == "り\u200bんご"


def test_emoji_label_is_preserved_as_literal_text():
    raw = "👨‍👩‍👧‍👦は3kg"

    clauses = _read(raw)

    assert len(clauses) == 1
    assert _role(clauses[0], "entity").term == "👨‍👩‍👧‍👦"
    assert _role(clauses[0], "entity").span.text == "👨‍👩‍👧‍👦"


def test_inline_markup_is_kept_instead_of_stripped_from_label():
    raw = "<b>りんご</b>は3kg"

    clauses = _read(raw)

    assert len(clauses) == 1
    assert _role(clauses[0], "entity").term == "<b>りんご</b>"
    assert _role(clauses[0], "entity").span.text == "<b>りんご</b>"


def test_ascii_art_residue_around_sentence_is_refused():
    assert _read("***\nりんごは3kg\n***") is None


@pytest.mark.xfail(strict=False, reason="DEFECT: arbitrary Han glyph is assigned the counter dimension")
def test_arbitrary_han_noise_is_not_assigned_a_measure_dimension():
    assert _read("りんごは3龘") is None


def test_sum_request_accepts_fullwidth_question_mark():
    builder = _Builder()

    result = measure.read_measure_request("合計は何kgですか？", builder, "question-span")

    assert result == "projected"
    assert len(builder.roots) == 2
    assert len(builder.nodes) == 3
    assert builder.outputs[0][0] == "計算結果"
    assert builder.outputs[0][3] == "kg"


@pytest.mark.parametrize("raw", ["合計は何ｋｇですか？", "合計\u200bは何kgですか？"])
def test_sum_request_rejects_fullwidth_unit_or_zero_width_insertion(raw):
    builder = _Builder()

    assert measure.read_measure_request(raw, builder, "question-span") is None
    assert builder.roots == []
    assert builder.nodes == []
    assert builder.outputs == []


def test_measure_question_rejects_combining_mark_inside_comparison_shape():
    builder = _Builder()

    assert measure.read_measure_request("長い\u0301方は？", builder, "question-span") is None
    assert builder.roots == []
