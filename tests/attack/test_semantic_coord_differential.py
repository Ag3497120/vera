"""Independent contract checks for plain predicate coordination and phrase bounds."""

from itertools import product

import pytest

from verantyx.semantic_coord import (
    chunk,
    coordination_ok,
    own_subject_phrase,
    phrase_bounded,
    topic_phrase,
)


def _token(surface, pos1, pos2="", cform="", start=0):
    return (surface, pos1, pos2, cform, start, start + len(surface))


def _line(*parts):
    """Build contiguous tagged tokens from (surface, pos1, pos2, cform) parts."""
    at = 0
    result = []
    for surface, pos1, pos2, cform in parts:
        result.append(_token(surface, pos1, pos2, cform, at))
        at += len(surface)
    return result


def _reference_coordination_ok(tagged, pred_indices):
    """Naive reading of the documented chain rule, independent of production helpers."""
    if len(pred_indices) < 2:
        return False

    for previous, following in zip(pred_indices, pred_indices[1:]):
        if previous < 0 or following >= len(tagged) or previous >= following:
            return False
        if not tagged[previous][3].startswith("連用"):
            return False

        cursor = previous + 1
        if (cursor < following and tagged[cursor][0] in ("て", "で")
                and tagged[cursor][1] == "助詞"):
            cursor += 1
        if cursor < following and tagged[cursor][0] == "、":
            cursor += 1

        separator = "".join(token[0] for token in tagged[previous + 1:cursor])
        if separator not in ("、", "て", "て、", "で", "で、"):
            return False

        clause_body = tagged[cursor:following]
        if any(token[1] == "接続詞" or
               (token[1] == "助詞" and token[2] == "接続助詞"
                and token[0] not in ("て", "で"))
               for token in clause_body):
            return False
        if not any(token[1] in ("名詞", "接尾辞", "代名詞") for token in clause_body):
            return False

    return True


def _reference_phrase_bounded(tagged, start, end):
    """Check aligned phrase edges against the stated neighboring-token boundary rule."""
    def punctuation(token):
        return token[1] == "補助記号" and not any(char.isalnum() for char in token[0])

    starts = [i for i, token in enumerate(tagged) if token[4] == start]
    ends = [i for i, token in enumerate(tagged) if token[5] == end]
    if not starts or not ends:
        return False

    first = starts[0]
    last = ends[-1]
    if first and (tagged[first - 1][5] != start
                  or not (tagged[first - 1][1] == "助詞" or punctuation(tagged[first - 1]))):
        return False

    if last + 1 < len(tagged):
        right = tagged[last + 1]
        if right[4] != end or not (right[1] in (
                "助詞", "助動詞", "動詞", "接続詞", "形容詞") or punctuation(right)):
            return False
    return True


def test_generated_coordination_cases_match_independent_reference():
    separators = (
        (("て", "助詞", "接続助詞", ""),),
        (("て", "助詞", "接続助詞", ""), ("、", "補助記号", "読点", "")),
        (("で", "助詞", "接続助詞", ""),),
        (("で", "助詞", "接続助詞", ""), ("、", "補助記号", "読点", "")),
        (("、", "補助記号", "読点", ""),),
    )
    for separator, inflection in product(separators, ("連用形", "連用タ接続")):
        tagged = _line(
            ("歩き", "動詞", "", inflection),
            *separator,
            ("猫", "名詞", "普通名詞", ""),
            ("眠る", "動詞", "", "終止形"),
        )
        pred_indices = (0, len(tagged) - 1)
        expected = _reference_coordination_ok(tagged, pred_indices)
        assert expected
        assert coordination_ok(tagged, pred_indices) == expected


def test_single_predicate_is_not_coordination():
    tagged = _line(("眠る", "動詞", "", "終止形"))
    assert not _reference_coordination_ok(tagged, (0,))
    assert not coordination_ok(tagged, (0,))


@pytest.mark.parametrize("separator", [
    (("が", "助詞", "接続助詞", ""),),
    (("しかし", "接続詞", "", ""),),
    (),
])
def test_non_te_separator_or_bare_renyo_is_rejected(separator):
    tagged = _line(
        ("歩き", "動詞", "", "連用形"),
        *separator,
        ("猫", "名詞", "普通名詞", ""),
        ("眠る", "動詞", "", "終止形"),
    )
    pred_indices = (0, len(tagged) - 1)
    expected = _reference_coordination_ok(tagged, pred_indices)
    assert not expected
    assert coordination_ok(tagged, pred_indices) == expected


def test_non_renyo_first_predicate_is_rejected():
    tagged = _line(
        ("歩く", "動詞", "", "終止形"),
        ("て", "助詞", "接続助詞", ""),
        ("猫", "名詞", "普通名詞", ""),
        ("眠る", "動詞", "", "終止形"),
    )
    pred_indices = (0, 3)
    assert not _reference_coordination_ok(tagged, pred_indices)
    assert not coordination_ok(tagged, pred_indices)


def test_chunk_starts_after_the_previous_clause_tail():
    tagged = _line(
        ("話し", "動詞", "", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("猫", "名詞", "普通名詞", ""),
        ("笑う", "動詞", "", "終止形"),
    )
    assert chunk(tagged, (0, 3), 0) == (0, 0)
    assert chunk(tagged, (0, 3), 1) == (2, 3)


def test_subject_phrase_requires_a_topic_or_case_particle():
    topic = _line(
        ("猫", "名詞", "普通名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("歩き", "動詞", "", "連用形"),
    )
    genitive = _line(
        ("猫", "名詞", "普通名詞", ""),
        ("が", "助詞", "格助詞", ""),
        ("歩き", "動詞", "", "連用形"),
    )
    other_particle = _line(
        ("猫", "名詞", "普通名詞", ""),
        ("を", "助詞", "格助詞", ""),
        ("歩き", "動詞", "", "連用形"),
    )
    assert own_subject_phrase(topic, 0, 2)
    assert own_subject_phrase(genitive, 0, 2)
    assert not own_subject_phrase(other_particle, 0, 2)


def test_topic_phrase_returns_the_first_noun_span_before_wa():
    tagged = _line(
        ("黒", "名詞", "普通名詞", ""),
        ("猫", "名詞", "普通名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("歩き", "動詞", "", "連用形"),
        ("庭", "名詞", "普通名詞", ""),
        ("を", "助詞", "格助詞", ""),
        ("走る", "動詞", "", "終止形"),
    )
    pred_indices = (3, 6)
    assert topic_phrase(tagged, pred_indices) == (0, 2)


def test_phrase_boundary_accepts_a_particle_bounded_name():
    tagged = _line(
        ("を", "助詞", "格助詞", ""),
        ("猫", "名詞", "普通名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("歩く", "動詞", "", "終止形"),
    )
    expected = _reference_phrase_bounded(tagged, 1, 2)
    assert expected
    assert phrase_bounded(tagged, 1, 2) == expected


def test_phrase_boundary_rejects_a_cut_name_neighbor():
    tagged = _line(
        ("クク", "名詞", "普通名詞", ""),
        ("クル", "名詞", "普通名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("歩く", "動詞", "", "終止形"),
    )
    expected = _reference_phrase_bounded(tagged, 0, 2)
    assert not expected
    assert phrase_bounded(tagged, 0, 2) == expected


@pytest.mark.xfail(strict=False, reason="DEFECT: accepts a coordinated chain without a new noun phrase chunk")
def test_coordination_requires_a_new_phrase_between_predicates():
    tagged = _line(
        ("見", "動詞", "", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("走る", "動詞", "", "終止形"),
    )
    pred_indices = (0, 2)
    expected = _reference_coordination_ok(tagged, pred_indices)
    assert not expected
    assert coordination_ok(tagged, pred_indices) == expected


@pytest.mark.xfail(strict=False, reason="DEFECT: accepts a connective after the te tail and before the next phrase")
def test_coordination_rejects_connective_inside_the_later_clause():
    tagged = _line(
        ("見", "動詞", "", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("しかし", "接続詞", "", ""),
        ("猫", "名詞", "普通名詞", ""),
        ("走る", "動詞", "", "終止形"),
    )
    pred_indices = (0, 4)
    expected = _reference_coordination_ok(tagged, pred_indices)
    assert not expected
    assert coordination_ok(tagged, pred_indices) == expected


@pytest.mark.xfail(strict=False, reason="DEFECT: accepts phrase spans that begin and end inside one token")
def test_phrase_boundary_rejects_edges_inside_a_token():
    tagged = [_token("クククル", "名詞", "普通名詞", "", 0)]
    expected = _reference_phrase_bounded(tagged, 1, 3)
    assert not expected
    assert phrase_bounded(tagged, 1, 3) == expected
