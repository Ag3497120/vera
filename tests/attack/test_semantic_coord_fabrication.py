import pytest

from verantyx.semantic_coord import (
    coordination_ok,
    own_subject_phrase,
    phrase_bounded,
    topic_phrase,
)


def tok(surface, pos1, pos2, cform, start):
    return (surface, pos1, pos2, cform, start, start + len(surface))


def test_coordination_accepts_renyo_te_with_next_clause_subject():
    tagged = [
        tok("太郎", "名詞", "普通名詞", "", 0),
        tok("歩き", "動詞", "一般", "連用形", 2),
        tok("て", "助詞", "接続助詞", "", 4),
        tok("花子", "名詞", "普通名詞", "", 5),
        tok("が", "助詞", "格助詞", "", 7),
        tok("来た", "動詞", "一般", "終止形", 8),
    ]

    assert coordination_ok(tagged, [1, 5]) is True


def test_coordination_accepts_renyo_comma_with_next_clause_subject():
    tagged = [
        tok("太郎", "名詞", "普通名詞", "", 0),
        tok("が", "助詞", "格助詞", "", 2),
        tok("歩き", "動詞", "一般", "連用形", 3),
        tok("、", "補助記号", "読点", "", 5),
        tok("花子", "名詞", "普通名詞", "", 6),
        tok("が", "助詞", "格助詞", "", 8),
        tok("走った", "動詞", "一般", "終止形", 9),
    ]

    assert coordination_ok(tagged, [2, 6]) is True


def test_coordination_rejects_bare_renyo_without_comma_or_te():
    tagged = [
        tok("歩き", "動詞", "一般", "連用形", 0),
        tok("帰った", "動詞", "一般", "終止形", 2),
    ]

    assert coordination_ok(tagged, [0, 1]) is False


def test_coordination_rejects_adversative_ga():
    tagged = [
        tok("笑い", "動詞", "一般", "連用形", 0),
        tok("が", "助詞", "接続助詞", "", 2),
        tok("彼", "名詞", "普通名詞", "", 3),
        tok("戻った", "動詞", "一般", "終止形", 4),
    ]

    assert coordination_ok(tagged, [0, 3]) is False


def test_coordination_rejects_causal_node():
    tagged = [
        tok("笑い", "動詞", "一般", "連用形", 0),
        tok("ので", "助詞", "接続助詞", "", 2),
        tok("彼", "名詞", "普通名詞", "", 4),
        tok("戻った", "動詞", "一般", "終止形", 5),
    ]

    assert coordination_ok(tagged, [0, 3]) is False


def test_coordination_rejects_non_renyo_nonfinal_predicate():
    tagged = [
        tok("歩く", "動詞", "一般", "終止形", 0),
        tok("て", "助詞", "接続助詞", "", 2),
        tok("帰った", "動詞", "一般", "終止形", 3),
    ]

    assert coordination_ok(tagged, [0, 2]) is False


def test_own_subject_phrase_recognizes_clause_local_topic_and_case_markers():
    topic = [
        tok("花子", "名詞", "普通名詞", "", 0),
        tok("は", "助詞", "係助詞", "", 2),
        tok("来る", "動詞", "一般", "終止形", 3),
    ]
    case = [
        tok("花子", "名詞", "普通名詞", "", 0),
        tok("が", "助詞", "格助詞", "", 2),
        tok("来る", "動詞", "一般", "終止形", 3),
    ]

    assert own_subject_phrase(topic, 0, 2) is True
    assert own_subject_phrase(case, 0, 2) is True


def test_own_subject_phrase_does_not_read_past_clause_end():
    tagged = [
        tok("花子", "名詞", "普通名詞", "", 0),
        tok("来る", "動詞", "一般", "終止形", 2),
        tok("私", "名詞", "普通名詞", "", 4),
        tok("は", "助詞", "係助詞", "", 5),
    ]

    assert own_subject_phrase(tagged, 0, 2) is False


def test_topic_phrase_returns_first_clause_topic_span():
    tagged = [
        tok("花子", "名詞", "普通名詞", "", 0),
        tok("は", "助詞", "係助詞", "", 2),
        tok("歩き", "動詞", "一般", "連用形", 3),
        tok("て", "助詞", "接続助詞", "", 5),
        tok("太郎", "名詞", "普通名詞", "", 6),
        tok("が", "助詞", "格助詞", "", 8),
        tok("帰る", "動詞", "一般", "終止形", 9),
    ]

    assert topic_phrase(tagged, [2, 6]) == (0, 2)


def test_phrase_bounded_accepts_complete_role_phrase():
    tagged = [
        tok("太郎", "名詞", "普通名詞", "", 0),
        tok("が", "助詞", "格助詞", "", 2),
        tok("来た", "動詞", "一般", "終止形", 3),
    ]

    assert phrase_bounded(tagged, 0, 2) is True


def test_phrase_bounded_rejects_fragment_after_stray_name_token():
    tagged = [
        tok("クク", "名詞", "普通名詞", "", 0),
        tok("クル", "名詞", "普通名詞", "", 2),
        tok("が", "助詞", "格助詞", "", 4),
    ]

    assert phrase_bounded(tagged, 2, 4) is False


@pytest.mark.xfail(strict=False, reason="DEFECT: connective after a comma is ignored before the next predicate")
def test_coordination_rejects_connective_between_comma_and_next_predicate():
    tagged = [
        tok("笑い", "動詞", "一般", "連用形", 0),
        tok("、", "補助記号", "読点", "", 2),
        tok("しかし", "接続詞", "", "", 3),
        tok("帰った", "動詞", "一般", "終止形", 6),
    ]

    assert coordination_ok(tagged, [0, 3]) is False


@pytest.mark.xfail(strict=False, reason="DEFECT: a role span beginning inside a token is accepted")
def test_phrase_bounded_rejects_role_span_starting_inside_name_token():
    tagged = [
        tok("太郎", "名詞", "普通名詞", "", 0),
        tok("が", "助詞", "格助詞", "", 2),
        tok("来た", "動詞", "一般", "終止形", 3),
    ]

    assert phrase_bounded(tagged, 1, 2) is False
