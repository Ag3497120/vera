from calc.ops import ZERO, add, mul, pairs


def test_add():
    assert add(2, 3) == 5 and add(ZERO, 4) == 4


def test_mul():
    assert mul(3, 4) == 12


def test_pairs():
    assert pairs([1, 2]) == [(1, 1), (2, 2)]
