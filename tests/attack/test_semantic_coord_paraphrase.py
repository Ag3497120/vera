import pytest

from verantyx.semantic_coord import (
    chunk,
    coordination_ok,
    own_subject_phrase,
    phrase_bounded,
    topic_phrase,
)


def tokens(*items):
    """Build the module's sentence-token tuples from surface/POS/conjugation fields."""
    tagged = []
    at = 0
    for surface, pos1, pos2, cform in items:
        tagged.append((surface, pos1, pos2, cform, at, at + len(surface)))
        at += len(surface)
    return tagged


def n(surface):
    return (surface, '名詞', '一般', '')


def p(surface, pos2='格助詞'):
    return (surface, '助詞', pos2, '')


def v(surface, cform='終止形'):
    return (surface, '動詞', '一般', cform)


def punctuation(surface='、'):
    return (surface, '補助記号', '読点', '')


def test_te_chain_keeps_verdict_across_plain_and_polite_final_forms():
    plain = tokens(n('太郎'), p('は', '係助詞'), v('食べ', '連用形'), p('て', '接続助詞'), v('帰る'))
    polite = tokens(n('太郎'), p('は', '係助詞'), v('食べ', '連用形'), p('て', '接続助詞'), v('帰ります'))

    assert coordination_ok(plain, [2, 4]) is True
    assert coordination_ok(polite, [2, 4]) is True


def test_bare_renyo_with_comma_is_a_permitted_chain():
    tagged = tokens(
        n('太郎'), p('は', '係助詞'), v('歩き', '連用形'), punctuation(),
        n('花子'), p('が'), v('泳ぐ'),
    )

    assert coordination_ok(tagged, [2, 6]) is True


def test_missing_te_or_comma_does_not_join_predicates():
    tagged = tokens(v('歩き', '連用形'), v('帰る'))

    assert coordination_ok(tagged, [0, 1]) is False


def test_adversative_ga_is_not_te_or_renyo_coordination():
    tagged = tokens(v('食べる'), p('が', '接続助詞'), v('帰る'))

    assert coordination_ok(tagged, [0, 2]) is False


@pytest.mark.parametrize('marker', ['は', 'が'])
def test_later_clause_detects_its_own_subject_marker(marker):
    tagged = tokens(
        n('太郎'), p('は', '係助詞'), v('歩き', '連用形'), p('て', '接続助詞'),
        n('花子'), p(marker, '係助詞' if marker == 'は' else '格助詞'), v('帰る'),
    )
    first, last = chunk(tagged, [2, 6], 1)

    assert own_subject_phrase(tagged, first, last) is True


def test_later_clause_without_its_own_subject_marker_is_detected():
    tagged = tokens(n('太郎'), p('は', '係助詞'), v('歩き', '連用形'), p('て', '接続助詞'), n('帰宅し',), v('た'))
    first, last = chunk(tagged, [2, 5], 1)

    assert own_subject_phrase(tagged, first, last) is False


@pytest.mark.parametrize(
    ('entity', 'expected'),
    [('太郎', (0, 2)), ('猫', (0, 1))],
)
def test_topic_phrase_tracks_entity_surface_and_span(entity, expected):
    tagged = tokens(n(entity), p('は', '係助詞'), v('歩き', '連用形'), p('て', '接続助詞'), v('帰る'))

    assert topic_phrase(tagged, [2, 4]) == expected


def test_phrase_bounded_accepts_a_whole_topic_phrase_before_its_particle():
    tagged = tokens(n('太郎'), p('は', '係助詞'), v('歩く'))

    assert phrase_bounded(tagged, 0, 2) is True


def test_phrase_bounded_rejects_a_phrase_that_leaves_a_neighboring_token():
    tagged = tokens(n('クク'), n('ル'), p('は', '係助詞'), v('歩く'))

    assert phrase_bounded(tagged, 2, 3) is False


@pytest.mark.xfail(strict=False, reason='DEFECT: a connective after consumed て is ignored before the next predicate.')
def test_causal_kara_after_te_does_not_license_coordination():
    tagged = tokens(
        n('太郎'), p('は', '係助詞'), v('食べ', '連用形'),
        p('て', '接続助詞'), p('から', '接続助詞'), v('帰る'),
    )
    observed = [coordination_ok(tagged, [2, 5]) for _ in range(2)]

    assert observed == [False, False]


@pytest.mark.xfail(strict=False, reason='DEFECT: phrase_bounded accepts a start inside a token when no token ends there.')
def test_phrase_bounded_rejects_a_start_inside_a_token():
    tagged = tokens(n('クク'), p('は', '係助詞'))

    assert phrase_bounded(tagged, 1, 2) is False


@pytest.mark.xfail(strict=False, reason='DEFECT: phrase_bounded accepts an end inside a token when no token starts there.')
def test_phrase_bounded_rejects_an_end_inside_a_token():
    tagged = tokens(n('ククル'))

    assert phrase_bounded(tagged, 0, 2) is False
