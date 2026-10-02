from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import product
from types import SimpleNamespace

import pytest

from verantyx import semantic_verify as verify
from verantyx.semantic_ir import Quantity, Variable


_OPEN_TO_CLOSE = {"「": "」", "『": "』"}
_CLOSERS = {value for value in _OPEN_TO_CLOSE.values()}
_BOUNDARIES = set("。！？\n")


def _reference_ranges(text):
    """Naive character scanner for original sentence boundaries."""
    starts = []
    begin = 0
    stack = []
    for index, char in enumerate(text):
        if char in _OPEN_TO_CLOSE:
            stack.append(_OPEN_TO_CLOSE[char])
        elif char in _CLOSERS:
            if not stack or stack.pop() != char:
                raise ValueError("unbalanced quotation")
        elif char in _BOUNDARIES and not stack:
            if text[begin:index + 1].strip():
                starts.append((begin, index + 1))
            begin = index + 1
    if stack:
        raise ValueError("unclosed quotation")
    if text[begin:].strip():
        starts.append((begin, len(text)))
    return set(starts)


def _checked_ranges(text):
    try:
        return verify._ranges(text)
    except verify.Rejected:
        return None


@pytest.mark.parametrize(
    "first,second",
    tuple(product(("。", "！", "？", "\n"), repeat=2)),
)
def test_generated_sentence_boundaries_match_naive_reference(first, second):
    text = f"alpha{first}beta{second}gamma"
    assert _checked_ranges(text) == _reference_ranges(text)


@pytest.mark.parametrize(
    "text",
    (
        "前。「引用！本文」後。",
        "「外『内。』外！」次。",
        "  前。\n   後！  ",
    ),
)
def test_quoted_punctuation_and_whitespace_match_naive_reference(text):
    assert _checked_ranges(text) == _reference_ranges(text)


@pytest.mark.parametrize("text", ("前」後。", "「閉じていない。", "「不一致』。"))
def test_unbalanced_quotes_are_rejected_by_both_scanners(text):
    with pytest.raises(ValueError):
        _reference_ranges(text)
    assert _checked_ranges(text) is None


def _reference_finite_decimal(value):
    denominator = value.denominator
    while denominator % 2 == 0:
        denominator //= 2
    while denominator % 5 == 0:
        denominator //= 5
    if denominator != 1:
        raise ValueError("non-terminating decimal")
    with localcontext() as context:
        context.prec = 400
        return Decimal(value.numerator) / Decimal(value.denominator)


@pytest.mark.parametrize(
    "value",
    tuple(
        Fraction(numerator, 2**twos * 5**fives)
        for numerator, twos, fives in product((-7, 0, 1, 19), range(5), range(4))
    ),
)
def test_generated_finite_fractions_match_naive_decimal_reference(value):
    assert verify._finite(value) == _reference_finite_decimal(value)


def test_nonterminating_fraction_is_rejected():
    with pytest.raises(ValueError):
        _reference_finite_decimal(Fraction(1, 3))
    with pytest.raises(verify.Rejected, match="non-terminating"):
        verify._finite(Fraction(1, 3))


@pytest.mark.parametrize("value", (Fraction(10**128), Fraction(1, 10**257)))
def test_exact_decimal_precision_limits_are_rejected(value):
    with pytest.raises(verify.Rejected, match="precision contract"):
        verify._finite(value)


_UNIT = {
    "m": ("length", Fraction(1)),
    "cm": ("length", Fraction(1, 100)),
    "km": ("length", Fraction(1000)),
    "g": ("mass", Fraction(1)),
}


def _reference_number(amount, source_unit, requested_unit):
    source_dimension, source_scale = _UNIT[source_unit]
    requested_dimension, requested_scale = _UNIT[requested_unit]
    if source_dimension != requested_dimension:
        raise ValueError("incompatible units")
    return Fraction(amount) * source_scale / requested_scale


@pytest.mark.parametrize(
    "amount,source_unit,requested_unit",
    (
        (Decimal("1.25"), "m", "cm"),
        (Decimal("250"), "cm", "m"),
        (Decimal("0.002"), "km", "m"),
        (Decimal("3.5"), "g", "g"),
    ),
)
def test_generated_unit_conversions_match_independent_rational_reference(
    amount, source_unit, requested_unit
):
    quantity = Quantity(amount, source_unit)
    expected = _reference_number(amount, source_unit, requested_unit)
    assert verify._number(quantity, requested_unit) == expected


def test_incompatible_unit_dimensions_are_rejected():
    quantity = Quantity(Decimal("1"), "m")
    with pytest.raises(ValueError):
        _reference_number(quantity.amount, quantity.unit, "g")
    with pytest.raises(verify.Rejected, match="incompatible units"):
        verify._number(quantity, "g")


@pytest.mark.parametrize("relation", ("=", "!=", ">", "<", ">=", "<="))
def test_quantity_comparisons_match_rational_reference(relation):
    left = Quantity(Decimal("1"), "m")
    right = Quantity(Decimal("100"), "cm")
    left_value = _reference_number(left.amount, left.unit, "m")
    right_value = _reference_number(right.amount, right.unit, "m")
    expected = {
        "=": left_value == right_value,
        "!=": left_value != right_value,
        ">": left_value > right_value,
        "<": left_value < right_value,
        ">=": left_value >= right_value,
        "<=": left_value <= right_value,
    }[relation]
    assert verify._test(left, relation, right) is expected


def test_ordered_nonquantity_comparison_is_rejected():
    with pytest.raises(verify.Rejected, match="ordered non-quantity"):
        verify._test("alpha", ">", "beta")


def test_sum_operator_replay_matches_exact_reference():
    terms = (Quantity(Decimal("100"), "cm"), Quantity(Decimal("0.5"), "m"))
    operator = SimpleNamespace(
        op="Sum", terms=terms, unit="m", target=Variable("total", "quantity"), absolute=False
    )
    env, answer = verify._calc(operator, {})
    expected = sum(
        (_reference_number(term.amount, term.unit, "m") for term in terms), Fraction(0)
    )
    assert env["total"] == Quantity(_reference_finite_decimal(expected), "m")
    assert answer == ()


def test_absolute_difference_operator_replay_matches_exact_reference():
    terms = (Quantity(Decimal("3"), "m"), Quantity(Decimal("5"), "m"))
    operator = SimpleNamespace(
        op="Difference", terms=terms, unit="m", target=Variable("gap", "quantity"), absolute=True
    )
    env, answer = verify._calc(operator, {})
    expected = abs(
        _reference_number(terms[0].amount, terms[0].unit, "m")
        - _reference_number(terms[1].amount, terms[1].unit, "m")
    )
    assert env["gap"] == Quantity(_reference_finite_decimal(expected), "m")
    assert answer == ()


@pytest.mark.parametrize("actual,expected", (("alpha", True), ("beta", False)))
def test_filter_operator_replay_matches_plain_equality(actual, expected):
    condition = SimpleNamespace(left=Variable("item"), relation="=", right="alpha")
    operator = SimpleNamespace(op="Filter", tests=(condition,), target=None)
    result = verify._calc(operator, {"item": actual})
    assert (result is not None) is expected
