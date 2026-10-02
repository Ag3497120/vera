"""Focused probes for the semantic coordinator's clause and span contracts."""

import pytest

from verantyx import semantic_coord as coord


def tagged(*items):
    """Build coordinator tokens from (surface, pos1, pos2, cform) tuples."""
    out = []
    at = 0
    for surface, pos1, pos2, cform in items:
        out.append((surface, pos1, pos2, cform, at, at + len(surface)))
        at += len(surface)
    return out


def test_te_chain_with_later_subject_is_coordination():
    ts = tagged(
        ("日本", "名詞", "普通名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("発展", "動詞", "", "連用形"),
        ("し", "動詞", "", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("、", "補助記号", "", ""),
        ("産業", "名詞", "普通名詞", ""),
        ("が", "助詞", "格助詞", ""),
        ("成長", "動詞", "", "終止形"),
    )
    assert coord.coordination_ok(ts, [3, 8])


def test_renyou_comma_chain_is_coordination():
    ts = tagged(
        ("進み", "動詞", "", "連用形"),
        ("、", "補助記号", "", ""),
        ("広がる", "動詞", "", "終止形"),
    )
    assert coord.coordination_ok(ts, [0, 2])


def test_single_predicate_and_nonrenyou_first_predicate_are_not_chains():
    one = tagged(("進む", "動詞", "", "終止形"))
    two = tagged(
        ("進み", "動詞", "", "終止形"),
        ("て", "助詞", "接続助詞", ""),
        ("広がる", "動詞", "", "終止形"),
    )
    assert not coord.coordination_ok(one, [0])
    assert not coord.coordination_ok(two, [0, 2])


def test_causal_particle_between_predicates_is_not_coordination():
    ts = tagged(
        ("進み", "動詞", "", "連用形"),
        ("ので", "助詞", "接続助詞", ""),
        ("広がる", "動詞", "", "終止形"),
    )
    assert not coord.coordination_ok(ts, [0, 2])


def test_later_clause_chunk_starts_after_joiner_and_detects_its_own_subject():
    ts = tagged(
        ("日本", "名詞", "普通名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("発展", "動詞", "", "連用形"),
        ("し", "動詞", "", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("、", "補助記号", "", ""),
        ("産業", "名詞", "普通名詞", ""),
        ("が", "助詞", "格助詞", ""),
        ("成長", "動詞", "", "終止形"),
    )
    assert coord.chunk(ts, [3, 8], 1) == (6, 8)
    assert coord.own_subject_phrase(ts, *coord.chunk(ts, [3, 8], 1))


def test_simple_topic_phrase_and_missing_topic():
    ts = tagged(
        ("日本", "名詞", "普通名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("進み", "動詞", "", "連用形"),
    )
    no_topic = tagged(
        ("日本", "名詞", "普通名詞", ""),
        ("が", "助詞", "格助詞", ""),
        ("進む", "動詞", "", "終止形"),
    )
    assert coord.topic_phrase(ts, [2]) == (0, 2)
    assert coord.topic_phrase(no_topic, [2]) is None


@pytest.mark.xfail(strict=False, reason="DEFECT: genitive modifiers are omitted from the topic phrase span")
def test_topic_phrase_includes_genitive_modifier():
    ts = tagged(
        ("日本", "名詞", "普通名詞", ""),
        ("の", "助詞", "格助詞", ""),
        ("首都", "名詞", "普通名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("東京", "名詞", "普通名詞", ""),
        ("で", "助詞", "格助詞", ""),
        ("ある", "動詞", "", "終止形"),
    )
    assert coord.topic_phrase(ts, [6]) == (0, 5)


def test_phrase_boundary_accepts_particle_and_predicate_edges():
    ts = tagged(
        ("日本", "名詞", "普通名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("東京", "名詞", "普通名詞", ""),
        ("だ", "助動詞", "", "終止形"),
    )
    assert coord.phrase_bounded(ts, 3, 5)


def test_phrase_boundary_rejects_adjacent_noun_fragments():
    ts = tagged(
        ("日本", "名詞", "普通名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("東京", "名詞", "普通名詞", ""),
        ("都", "名詞", "普通名詞", ""),
        ("だ", "助動詞", "", "終止形"),
    )
    assert not coord.phrase_bounded(ts, 5, 6)
    assert not coord.phrase_bounded(ts, 3, 5)


@pytest.mark.xfail(strict=False, reason="DEFECT: phrase spans cutting inside a token are accepted")
def test_phrase_boundary_rejects_span_cut_inside_a_token():
    ts = tagged(("日本", "名詞", "普通名詞", ""))
    assert not coord.phrase_bounded(ts, 0, 1)


@pytest.mark.xfail(strict=False, reason="DEFECT: a connective after the joiner is not checked")
def test_connective_after_joiner_prevents_coordination():
    ts = tagged(
        ("進み", "動詞", "", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("、", "補助記号", "", ""),
        ("しかし", "接続詞", "", ""),
        ("広がる", "動詞", "", "終止形"),
    )
    assert not coord.coordination_ok(ts, [0, 4])
