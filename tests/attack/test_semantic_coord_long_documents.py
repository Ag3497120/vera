"""Adversarial checks for long, repeated, and multi-document coordination inputs."""

import pytest

from verantyx.semantic_coord import (
    chunk,
    coordination_ok,
    own_subject_phrase,
    phrase_bounded,
    topic_phrase,
)


def _t(surface, pos1="名詞", pos2="普通名詞", cform="基本形"):
    return (surface, pos1, pos2, cform)


def _tokens(*items):
    tagged = []
    at = 0
    for surface, pos1, pos2, cform in items:
        tagged.append((surface, pos1, pos2, cform, at, at + len(surface)))
        at += len(surface)
    return tagged


def test_single_predicate_is_not_a_coordination_chain():
    tagged = _tokens(_t("進め", "動詞", "一般", "連用形"))

    assert coordination_ok(tagged, [0]) is False


def test_longer_te_and_comma_chain_accepts_only_renyo_links():
    tagged = _tokens(
        _t("調べ", "動詞", "一般", "連用形"),
        _t("て", "助詞", "接続助詞"),
        _t("記録", "名詞"),
        _t("を", "助詞", "格助詞"),
        _t("まとめ", "動詞", "一般", "連用形"),
        _t("、", "補助記号", "読点"),
        _t("送る", "動詞", "一般", "終止形"),
    )

    assert coordination_ok(tagged, [0, 4, 6]) is True
    assert chunk(tagged, [0, 4, 6], 1) == (2, 4)


def test_a_non_renyo_nonfinal_predicate_is_refused():
    tagged = _tokens(
        _t("調べ", "動詞", "一般", "終止形"),
        _t("て", "助詞", "接続助詞"),
        _t("送る", "動詞", "一般", "終止形"),
    )

    assert coordination_ok(tagged, [0, 2]) is False


@pytest.mark.parametrize("surface", ["が", "ので", "から", "ば", "たら", "と"])
def test_noncoordination_connectives_are_not_te_or_comma_separators(surface):
    tagged = _tokens(
        _t("調べ", "動詞", "一般", "連用形"),
        _t(surface, "助詞", "接続助詞"),
        _t("送る", "動詞", "一般", "終止形"),
    )

    assert coordination_ok(tagged, [0, 2]) is False


def test_first_clause_topic_span_and_later_own_subject_are_clause_local():
    tagged = _tokens(
        _t("佐藤", "名詞", "固有名詞"),
        _t("は", "助詞", "係助詞"),
        _t("調べ", "動詞", "一般", "連用形"),
        _t("て", "助詞", "接続助詞"),
        _t("田中", "名詞", "固有名詞"),
        _t("が", "助詞", "格助詞"),
        _t("発見", "動詞", "一般", "終止形"),
    )
    predicates = [2, 6]

    assert coordination_ok(tagged, predicates) is True
    assert topic_phrase(tagged, predicates) == (0, 2)
    assert chunk(tagged, predicates, 1) == (4, 6)
    assert own_subject_phrase(tagged, *chunk(tagged, predicates, 1)) is True


def test_later_clause_without_own_marker_remains_a_topic_sharing_candidate():
    tagged = _tokens(
        _t("佐藤", "名詞", "固有名詞"),
        _t("は", "助詞", "係助詞"),
        _t("調べ", "動詞", "一般", "連用形"),
        _t("て", "助詞", "接続助詞"),
        _t("発見", "動詞", "一般", "終止形"),
    )
    predicates = [2, 4]

    assert topic_phrase(tagged, predicates) == (0, 2)
    assert chunk(tagged, predicates, 1) == (4, 4)
    assert own_subject_phrase(tagged, *chunk(tagged, predicates, 1)) is False


def test_repeated_entities_in_many_independent_documents_do_not_pool_topic_scope():
    for i in range(48):
        if i % 2 == 0:
            first_marker = _t("は", "助詞", "係助詞")
            expected_topic = (0, 2)
        else:
            first_marker = _t("が", "助詞", "格助詞")
            expected_topic = None
        tagged = _tokens(
            _t("佐藤", "名詞", "固有名詞"),
            first_marker,
            _t("調べ", "動詞", "一般", "連用形"),
            _t("て", "助詞", "接続助詞"),
            _t(f"資料{i}", "名詞"),
            _t("は", "助詞", "係助詞"),
            _t("確認", "動詞", "一般", "終止形"),
        )
        predicates = [2, 6]

        assert topic_phrase(tagged, predicates) == expected_topic
        assert own_subject_phrase(tagged, *chunk(tagged, predicates, 1)) is True


def test_exact_duplicate_and_near_duplicate_sentences_keep_flat_results():
    original = _tokens(
        _t("佐藤", "名詞", "固有名詞"),
        _t("は", "助詞", "係助詞"),
        _t("調べ", "動詞", "一般", "連用形"),
        _t("て", "助詞", "接続助詞"),
        _t("記録", "名詞"),
        _t("を", "助詞", "格助詞"),
        _t("確認", "動詞", "一般", "終止形"),
    )
    duplicate = list(original)
    near_duplicate = _tokens(
        _t("佐藤", "名詞", "固有名詞"),
        _t("は", "助詞", "係助詞"),
        _t("調べ", "動詞", "一般", "連用形"),
        _t("ので", "助詞", "接続助詞"),
        _t("記録", "名詞"),
        _t("を", "助詞", "格助詞"),
        _t("確認", "動詞", "一般", "終止形"),
    )

    assert coordination_ok(original, [2, 6]) is True
    assert coordination_ok(duplicate, [2, 6]) is True
    assert coordination_ok(near_duplicate, [2, 6]) is False


def test_very_long_sentence_preserves_predicate_and_clause_boundaries():
    items = [_t("計画", "名詞", "普通名詞"), _t("は", "助詞", "係助詞")]
    predicates = []
    count = 256
    for i in range(count):
        predicates.append(len(items))
        form = "終止形" if i == count - 1 else "連用形"
        items.append(_t(f"検討{i}", "動詞", "一般", form))
        if i < count - 1:
            items.extend(
                [
                    _t("て", "助詞", "接続助詞"),
                    _t(f"資料{i}", "名詞"),
                    _t("を", "助詞", "格助詞"),
                ]
            )
    tagged = _tokens(*items)

    assert coordination_ok(tagged, predicates) is True
    assert topic_phrase(tagged, predicates) == (0, 2)
    assert chunk(tagged, predicates, count - 1) == (predicates[-2] + 2, predicates[-1])


def test_phrase_boundary_accepts_complete_particle_bounded_name():
    tagged = _tokens(
        _t("佐藤", "名詞", "固有名詞"),
        _t("は", "助詞", "係助詞"),
        _t("調べ", "動詞", "一般", "終止形"),
    )

    assert phrase_bounded(tagged, 0, 2) is True


def test_phrase_boundary_rejects_a_fragment_before_an_adjacent_name_token():
    tagged = _tokens(
        _t("クク", "名詞", "固有名詞"),
        _t("クル", "名詞", "固有名詞"),
        _t("は", "助詞", "係助詞"),
        _t("調べ", "動詞", "一般", "終止形"),
    )

    assert phrase_bounded(tagged, 0, 2) is False


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: a connective after the consumed te/de tail is skipped",
)
def test_connective_after_te_tail_is_not_licensed_coordination():
    examples = [
        _tokens(
            _t("調べ", "動詞", "一般", "連用形"),
            _t("て", "助詞", "接続助詞"),
            _t("から", "助詞", "接続助詞"),
            _t("送る", "動詞", "一般", "終止形"),
        ),
        _tokens(
            _t("調べ", "動詞", "一般", "連用形"),
            _t("で", "助詞", "接続助詞"),
            _t("しかし", "接続詞", "*"),
            _t("送る", "動詞", "一般", "終止形"),
        ),
    ]

    observed = [coordination_ok(tagged, [0, len(tagged) - 1]) for tagged in examples]
    assert observed == [False, False]
