from calc.ops import total


def test_total():
    assert total([1, 2, 3]) == 6 and total([]) == 0
