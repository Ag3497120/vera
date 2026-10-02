from decimal import Decimal

import pytest

from verantyx.semantic_ir import Quantity
from verantyx.semantic_measure import read_measure_request, read_measure_sentence


def read(raw):
    return read_measure_sentence("attack", raw, 0, 0, len(raw), "source", "family")


def quantity(clause):
    return next(role.term for role in clause.roles if role.name == "value")


def test_decimal_measure_keeps_exact_decimal_value():
    clauses = read("Aは0.10mです")

    assert len(clauses) == 1
    value = quantity(clauses[0])
    assert value == Quantity(Decimal("0.10"), "m")
    amount = next(getattr(value, name) for name in ("amount", "value", "number")
                  if hasattr(value, name))
    assert isinstance(amount, Decimal)
    assert amount.as_tuple() == Decimal("0.10").as_tuple()


def test_past_plain_predicate_is_not_read_as_a_timeless_measure():
    assert read("Aは3mだった") is None


def test_past_copula_is_not_read_as_a_timeless_measure():
    assert read("Aは3mであった") is None


def test_polite_past_predicate_is_not_read_as_a_timeless_measure():
    assert read("Aは3mでした") is None


def test_change_of_state_aspect_is_not_read_as_a_timeless_measure():
    assert read("Aは3mになっている") is None


def test_relative_time_before_a_measure_is_outside_the_closed_shape():
    assert read("Aは以前3mです") is None


def test_date_and_measure_in_one_predicate_are_not_partially_consumed():
    assert read("Aは2025年3mです") is None


def test_leading_relative_time_sentence_is_not_read_as_a_measure():
    assert read("今年、Aは3mです") is None


def test_sum_question_with_relative_year_is_not_recognized():
    assert read_measure_request("今年の合計は何mですか", None, None) is None


def test_comparison_question_with_past_year_is_not_recognized():
    assert read_measure_request("去年どちらが長いですか", None, None) is None


def test_same_question_with_relative_time_is_not_recognized():
    assert read_measure_request("以前の長さは同じですか", None, None) is None


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: temporal event ordering is absorbed into an entity kind.",
)
def test_event_ordering_marker_is_not_mistaken_for_a_measure_label():
    assert read("Aは3m、後日Bは4mです") is None
