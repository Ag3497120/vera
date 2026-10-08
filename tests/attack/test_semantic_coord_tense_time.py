import pytest

from verantyx.semantic_coord import (
    chunk,
    coordination_ok,
    own_subject_phrase,
    phrase_bounded,
    topic_phrase,
)


def _tagged(*parts):
    tagged = []
    offset = 0
    for surface, pos1, pos2, cform in parts:
        tagged.append((surface, pos1, pos2, cform, offset, offset + len(surface)))
        offset += len(surface)
    return tagged


def test_te_chain_accepts_past_final_clause_and_keeps_time_word_in_chunk():
    tagged = _tagged(
        ("太郎", "名詞", "固有名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("歩い", "動詞", "自立", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("昨日", "名詞", "副詞可能", ""),
        ("帰っ", "動詞", "自立", "連用形"),
        ("た", "助動詞", "", "終止形-一般"),
    )
    assert coordination_ok(tagged, [2, 5])
    assert chunk(tagged, [2, 5], 1) == (4, 5)
    assert not own_subject_phrase(tagged, *chunk(tagged, [2, 5], 1))


def test_te_chain_accepts_nonpast_final_clause():
    tagged = _tagged(
        ("花子", "名詞", "固有名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("食べ", "動詞", "自立", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("帰る", "動詞", "自立", "終止形-一般"),
    )
    assert coordination_ok(tagged, [2, 4])


def test_bare_renyo_requires_comma():
    tagged = _tagged(
        ("起き", "動詞", "自立", "連用形"),
        ("、", "補助記号", "読点", ""),
        ("働く", "動詞", "自立", "終止形-一般"),
    )
    assert coordination_ok(tagged, [0, 2])


def test_bare_renyo_without_comma_is_not_coordination():
    tagged = _tagged(
        ("起き", "動詞", "自立", "連用形"),
        ("働く", "動詞", "自立", "終止形-一般"),
    )
    assert not coordination_ok(tagged, [0, 1])


def test_past_nonfinal_predicate_is_not_licensed_as_renyo_chain():
    tagged = _tagged(
        ("起きた", "動詞", "自立", "終止形-一般"),
        ("、", "補助記号", "読点", ""),
        ("働く", "動詞", "自立", "終止形-一般"),
    )
    assert not coordination_ok(tagged, [0, 2])


def test_later_clause_own_ga_phrase_is_detected_after_time_modifier():
    tagged = _tagged(
        ("私", "名詞", "代名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("待っ", "動詞", "自立", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("昨日", "名詞", "副詞可能", ""),
        ("彼", "名詞", "代名詞", ""),
        ("が", "助詞", "格助詞", ""),
        ("来た", "動詞", "自立", "終止形-一般"),
    )
    first, last = chunk(tagged, [2, 7], 1)
    assert first == 4
    assert own_subject_phrase(tagged, first, last)


def test_simple_relative_time_topic_span_includes_its_time_noun():
    tagged = _tagged(
        ("今年", "名詞", "副詞可能", ""),
        ("は", "助詞", "係助詞", ""),
        ("進み", "動詞", "自立", "連用形"),
        ("、", "補助記号", "読点", ""),
        ("終わる", "動詞", "自立", "終止形-一般"),
    )
    assert topic_phrase(tagged, [2, 4]) == (0, len("今年"))


def test_complete_date_quantity_phrase_is_bounded_before_topic_particle():
    phrase = "2026年の春"
    tagged = _tagged(
        ("2026", "名詞", "数", ""),
        ("年", "接尾辞", "助数詞", ""),
        ("の", "助詞", "格助詞", ""),
        ("春", "名詞", "普通名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("始まっ", "動詞", "自立", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("終わる", "動詞", "自立", "終止形-一般"),
    )
    assert phrase_bounded(tagged, 0, len(phrase))


def test_date_phrase_fragment_before_suffix_is_not_bounded():
    tagged = _tagged(
        ("2026", "名詞", "数", ""),
        ("年", "接尾辞", "助数詞", ""),
        ("の", "助詞", "格助詞", ""),
        ("春", "名詞", "普通名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("始まる", "動詞", "自立", "終止形-一般"),
    )
    assert not phrase_bounded(tagged, 0, len("2026"))


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: topic_phrase drops temporal modifiers before a genitive particle",
)
def test_topic_phrase_includes_genitive_date_modifier():
    tagged = _tagged(
        ("2026", "名詞", "数", ""),
        ("年", "接尾辞", "助数詞", ""),
        ("の", "助詞", "格助詞", ""),
        ("春", "名詞", "普通名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("始まっ", "動詞", "自立", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("終わる", "動詞", "自立", "終止形-一般"),
    )
    assert topic_phrase(tagged, [5, 7]) == (0, len("2026年の春"))
