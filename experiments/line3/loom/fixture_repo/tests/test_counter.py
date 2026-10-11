from calc.counter import Counter


def test_counter():
    c = Counter(1)
    assert c.bump(2) == 3 and c.bump(4) == 7
