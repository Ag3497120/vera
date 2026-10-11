from calc.fmt import fmt_list, fmt_num, fmt_pair


def test_fmt():
    assert fmt_num(3) == "3" and fmt_pair(1, 2) == "(1, 2)" and fmt_list([1, 2]) == ["1", "2"]
