from calc.fmt import fmt_all


def test_fmt_all():
    assert fmt_all([1, 2]) == ["1", "2"] and fmt_all([]) == []
