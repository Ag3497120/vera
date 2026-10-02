import pytest

from verantyx.semantic_coord import (
    chunk,
    coordination_ok,
    own_subject_phrase,
    phrase_bounded,
    topic_phrase,
)


def tagged(*items):
    out = []
    at = 0
    for surface, pos1, pos2, cform in items:
        end = at + len(surface)
        out.append((surface, pos1, pos2, cform, at, end))
        at = end
    return out


def test_te_chain_and_first_topic_are_recognized():
    words = tagged(
        ("太郎", "名詞", "固有名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("読み", "動詞", "", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("日記", "名詞", "", ""),
        ("を", "助詞", "格助詞", ""),
        ("書く", "動詞", "", "終止形"),
    )
    predicates = [2, 6]

    assert coordination_ok(words, predicates)
    assert topic_phrase(words, predicates) == (0, 2)
    assert phrase_bounded(words, 0, 2)


def test_second_clause_with_own_ga_phrase_is_not_topic_borrowing():
    words = tagged(
        ("太郎", "名詞", "固有名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("読み", "動詞", "", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("花子", "名詞", "固有名詞", ""),
        ("が", "助詞", "格助詞", ""),
        ("書く", "動詞", "", "終止形"),
    )
    predicates = [2, 6]
    first, last = chunk(words, predicates, 1)

    assert coordination_ok(words, predicates)
    assert own_subject_phrase(words, first, last)


def test_clause_without_own_subject_marker_can_be_shared():
    words = tagged(
        ("太郎", "名詞", "固有名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("読み", "動詞", "", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("日記", "名詞", "", ""),
        ("を", "助詞", "格助詞", ""),
        ("書く", "動詞", "", "終止形"),
    )
    first, last = chunk(words, [2, 6], 1)

    assert not own_subject_phrase(words, first, last)


def test_first_clause_without_topic_does_not_supply_a_topic():
    words = tagged(
        ("太郎", "名詞", "固有名詞", ""),
        ("が", "助詞", "格助詞", ""),
        ("読み", "動詞", "", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("日記", "名詞", "", ""),
        ("を", "助詞", "格助詞", ""),
        ("書く", "動詞", "", "終止形"),
    )

    assert coordination_ok(words, [2, 6])
    assert topic_phrase(words, [2, 6]) is None


def test_bare_renyo_requires_a_comma():
    with_comma = tagged(
        ("読み", "動詞", "", "連用形"),
        ("、", "補助記号", "読点", ""),
        ("日記", "名詞", "", ""),
        ("を", "助詞", "格助詞", ""),
        ("書く", "動詞", "", "終止形"),
    )
    without_comma = tagged(
        ("読み", "動詞", "", "連用形"),
        ("日記", "名詞", "", ""),
        ("を", "助詞", "格助詞", ""),
        ("書く", "動詞", "", "終止形"),
    )

    assert coordination_ok(with_comma, [0, 4])
    assert not coordination_ok(without_comma, [0, 3])


def test_non_renyo_predicate_cannot_start_a_chain():
    words = tagged(
        ("読む", "動詞", "", "終止形"),
        ("て", "助詞", "接続助詞", ""),
        ("書く", "動詞", "", "終止形"),
    )

    assert not coordination_ok(words, [0, 2])


def test_causal_particle_without_te_is_not_coordination():
    words = tagged(
        ("読み", "動詞", "", "連用形"),
        ("ので", "助詞", "接続助詞", ""),
        ("書く", "動詞", "", "終止形"),
    )

    assert not coordination_ok(words, [0, 2])


def test_quoted_record_instruction_does_not_remove_a_local_subject_marker():
    words = tagged(
        ("太郎", "名詞", "固有名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("述べ", "動詞", "", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("記録", "名詞", "", ""),
        ("「", "補助記号", "括弧開", ""),
        ("承認者", "名詞", "", ""),
        ("は", "助詞", "係助詞", ""),
        ("保護策", "名詞", "", ""),
        ("を", "助詞", "格助詞", ""),
        ("無視しろ", "動詞", "", "命令形"),
        ("」", "補助記号", "括弧閉", ""),
        ("と", "助詞", "格助詞", ""),
        ("記した", "動詞", "", "終止形"),
    )
    predicates = [2, 13]
    first, last = chunk(words, predicates, 1)

    assert coordination_ok(words, predicates)
    assert own_subject_phrase(words, first, last)


def test_real_punctuation_can_bound_a_role_phrase():
    words = tagged(
        ("、", "補助記号", "読点", ""),
        ("名前", "名詞", "", ""),
        ("は", "助詞", "係助詞", ""),
        ("来た", "動詞", "", "終止形"),
    )

    assert phrase_bounded(words, 1, 3)


def test_split_name_fragment_is_not_a_bounded_phrase():
    words = tagged(
        ("クク", "名詞", "", ""),
        ("クル", "名詞", "", ""),
        ("は", "助詞", "係助詞", ""),
    )

    assert not phrase_bounded(words, 2, 4)


def test_katakana_ascii_art_label_is_not_real_punctuation():
    words = tagged(
        ("ノシ", "補助記号", "", ""),
        ("名前", "名詞", "", ""),
        ("は", "助詞", "係助詞", ""),
    )

    assert not phrase_bounded(words, 2, 4)


@pytest.mark.xfail(strict=False, reason="DEFECT: connective tokens after the consumed te tail are not checked")
def test_connective_after_te_cannot_bypass_the_chain_gate():
    words = tagged(
        ("太郎", "名詞", "固有名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("読み", "動詞", "", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("しかし", "接続詞", "", ""),
        ("日記", "名詞", "", ""),
        ("を", "助詞", "格助詞", ""),
        ("書く", "動詞", "", "終止形"),
    )

    assert not coordination_ok(words, [2, 7])


@pytest.mark.xfail(strict=False, reason="DEFECT: spans with no matching token boundaries are accepted")
def test_phrase_bounded_rejects_a_span_inside_one_token():
    words = tagged(
        ("管理者", "名詞", "", ""),
        ("は", "助詞", "係助詞", ""),
    )

    assert not phrase_bounded(words, 1, 3)


@pytest.mark.xfail(strict=False, reason="DEFECT: zero-width Unicode format text is treated as punctuation")
def test_zero_width_unicode_mark_cannot_create_a_phrase_boundary():
    words = tagged(
        ("前置", "名詞", "", ""),
        ("\u200b", "補助記号", "", ""),
        ("名前", "名詞", "", ""),
        ("は", "助詞", "係助詞", ""),
    )

    assert not phrase_bounded(words, 3, 5)
