"""Differential checks for small, independently specified reader behaviors."""
from decimal import Decimal
from itertools import product
import re

import pytest

from verantyx import semantic_reader as reader


_REFERENCE_NUMBER = re.compile(
    r"([+-]?[0-9]+(?:\.[0-9]+)?)\s*([A-Za-z%]+|[一-鿿]+)"
)


def _reference_quantity(text):
    """Parse only the exact numeric-and-unit form in the reader contract."""
    match = _REFERENCE_NUMBER.fullmatch(text.strip())
    if match is None:
        return None
    number = Decimal(match.group(1))
    if len(number.as_tuple().digits) > 128:
        return None
    return number, match.group(2)


def _reference_sentence_ranges(raw):
    """Naive quote-depth scanner for sentence-ending punctuation."""
    openers = {"「", "『"}
    closers = {"」", "』"}
    endings = {"。", "！", "？", "\n"}
    ranges = []
    start = 0
    quote_depth = 0
    for index, char in enumerate(raw):
        if char in openers:
            quote_depth += 1
        elif char in closers:
            quote_depth = max(0, quote_depth - 1)
        if quote_depth == 0 and char in endings:
            if raw[start:index + 1].strip():
                ranges.append((start, index + 1))
            start = index + 1
    if raw[start:].strip():
        ranges.append((start, len(raw)))
    return ranges


def _reference_nominal_copula(raw):
    """Read a deliberately tiny entity/attribute/value copula grammar."""
    match = re.fullmatch(
        r"(?P<lhs>[^はが。！？?]+?)(?:は|が)"
        r"(?P<value>.+?)(?P<ending>ではない|でない|じゃない|です|である|だ)?"
        r"[。！？?]*",
        raw,
    )
    if match is None:
        return None
    lhs = match.group("lhs")
    value = match.group("value")
    if not lhs or not value:
        return None
    path = lhs.split("の")
    entity = "の".join(path[:-1]) if len(path) > 1 else lhs
    attribute = path[-1] if len(path) > 1 else None
    quantity = _reference_quantity(value)
    return {
        "predicate": "property" if attribute else "identity",
        "polarity": "-" if match.group("ending") in ("ではない", "でない", "じゃない") else "+",
        "roles": (
            [("entity", entity, "literal")]
            + ([("attribute", attribute, "nominal")] if attribute else [])
            + [("value", quantity if quantity is not None else value,
                "quantity" if quantity is not None else "literal")]
        ),
    }


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   \n ",
        "猫。犬！鳥？",
        "題「猫。犬」終。",
        "『甲「乙。丙」丁』終！",
        "未完「猫。犬",
        "」先。後",
        "。 。犬。",
        "前\n中。後",
        "引用「内\n側」外\n終",
    ],
)
def test_sentence_ranges_match_independent_quote_scanner(raw):
    expected = _reference_sentence_ranges(raw)
    assert list(reader._sentences(raw)) == expected


_VALID_NUMBERS = ("0", "7", "-3", "+0.25", "99.0", "0.000", "000.01")
_VALID_UNITS = ("kg", "%", "人", "円")
_INVALID_QUANTITIES = ("", "  ", "1", "1.2.3kg", "10 m/s", "1e3kg", "１２kg")


@pytest.mark.parametrize(
    "raw", [f"{number}{unit}" for number, unit in product(_VALID_NUMBERS, _VALID_UNITS)]
    + list(_INVALID_QUANTITIES)
    + ["9" * 129 + "g"],
)
def test_quantity_matches_independent_exact_parser(raw):
    expected = _reference_quantity(raw)
    actual = reader.quantity(raw)
    if expected is None:
        assert actual is None
    else:
        assert actual is not None
        assert (actual.amount, actual.unit) == expected


_COPULA_CASES = (
    "太郎は医師です。",
    "花子は学生です。",
    "箱は箱です。",
    "犬の名前はポチです。",
    "箱の重量は12kgです。",
    "商品は25%です。",
    "木の色は0.5mです。",
    "太郎は医師ではない。",
)


@pytest.mark.parametrize("raw", _COPULA_CASES)
def test_small_nominal_copula_subset_matches_independent_reader(raw):
    expected = _reference_nominal_copula(raw)
    assert expected is not None

    view = reader.document_view({"source": raw})
    assert not view.unread
    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert clause.rule == "copula"
    assert clause.predicate == expected["predicate"]
    assert clause.polarity == expected["polarity"]
    actual_roles = []
    for role in clause.roles:
        term = role.term
        if role.rule == "quantity":
            term = (term.amount, term.unit)
        actual_roles.append((role.name, term, role.rule))
    assert actual_roles == expected["roles"]
