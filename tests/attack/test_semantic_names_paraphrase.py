from types import SimpleNamespace

import pytest

from verantyx.semantic_names import is_past_aux, name_split_in, tokens_covering


def token(surface, pos1, pos2, start):
    return (surface, pos1, pos2, start, start + len(surface))


def test_covering_selects_exact_adjacent_span_and_ignores_context():
    tagged = [
        token("前", "名詞", "一般", 0),
        token("技師", "名詞", "一般", 1),
        token("ユン", "名詞", "固有名詞", 3),
        token("は", "助詞", "係助詞", 5),
    ]

    assert tokens_covering(tagged, 1, 5) == tagged[1:3]


def test_particle_and_clause_surface_changes_leave_the_name_split_unchanged():
    plain = [
        token("技師", "名詞", "一般", 0),
        token("ユン", "名詞", "固有名詞", 2),
        token("が", "助詞", "格助詞", 4),
        token("来る", "動詞", "自立", 5),
    ]
    polite = [
        token("技師", "名詞", "一般", 0),
        token("ユン", "名詞", "固有名詞", 2),
        token("は", "助詞", "係助詞", 4),
        token("来ました", "動詞", "自立", 5),
    ]

    plain_cover = tokens_covering(plain, 0, 4)
    polite_cover = tokens_covering(polite, 0, 4)
    assert name_split_in(plain_cover, "技師ユン") == ("技師", "ユン")
    assert name_split_in(polite_cover, "技師ユン") == ("技師", "ユン")


def test_covering_rejects_a_gap_inside_the_requested_span():
    tagged = [
        token("技師", "名詞", "一般", 0),
        token("ユン", "名詞", "固有名詞", 3),
    ]

    assert tokens_covering(tagged, 0, 4) is None


def test_covering_rejects_tokens_that_only_partially_overlap_the_span():
    tagged = [
        token("技師", "名詞", "一般", 0),
        token("ユン", "名詞", "固有名詞", 2),
    ]

    assert tokens_covering(tagged, 1, 3) is None


def test_kanji_title_and_proper_name_split():
    cover = [
        token("研究員", "名詞", "一般", 0),
        token("ユン", "名詞", "固有名詞", 3),
    ]

    assert name_split_in(cover, "研究員ユン") == ("研究員", "ユン")


def test_split_accepts_a_common_noun_followed_by_a_noun_suffix():
    cover = [
        token("研究", "名詞", "一般", 0),
        token("員", "接尾辞", "名詞性接尾辞", 2),
        token("ユン", "名詞", "固有名詞", 3),
    ]

    assert name_split_in(cover, "研究員ユン") == ("研究員", "ユン")


def test_split_rejects_a_katakana_prefix_that_could_be_a_cut_name():
    cover = [
        token("コカ", "名詞", "一般", 0),
        token("カル", "名詞", "固有名詞", 2),
    ]

    assert name_split_in(cover, "コカカル") is None


def test_split_rejects_a_cover_without_a_descriptor():
    cover = [token("ユン", "名詞", "固有名詞", 0)]

    assert name_split_in(cover, "ユン") is None


def test_split_rejects_a_non_proper_final_token():
    cover = [
        token("技師", "名詞", "一般", 0),
        token("ユン", "名詞", "一般", 2),
    ]

    assert name_split_in(cover, "技師ユン") is None


def test_split_rejects_a_proper_noun_inside_the_descriptor():
    cover = [
        token("技師", "名詞", "固有名詞", 0),
        token("ユン", "名詞", "固有名詞", 2),
    ]

    assert name_split_in(cover, "技師ユン") is None


def test_split_requires_the_cover_to_match_the_supplied_value():
    cover = [
        token("技師", "名詞", "一般", 0),
        token("ユン", "名詞", "固有名詞", 2),
    ]

    assert name_split_in(cover, "技師リン") is None


def test_entity_swap_keeps_split_shape_and_returns_the_swapped_name():
    yoon = [
        token("技師", "名詞", "一般", 0),
        token("ユン", "名詞", "固有名詞", 2),
    ]
    rin = [
        token("技師", "名詞", "一般", 0),
        token("リン", "名詞", "固有名詞", 2),
    ]

    assert name_split_in(yoon, "技師ユン") == ("技師", "ユン")
    assert name_split_in(rin, "技師リン") == ("技師", "リン")


@pytest.mark.parametrize("surface", ["た", "だ"])
def test_past_auxiliary_surface_variants_use_the_past_lemma(surface):
    word = SimpleNamespace(feature=SimpleNamespace(pos1="助動詞", lemma="た"), surface=surface)

    assert is_past_aux(word) is True


def test_non_past_auxiliary_lemma_is_not_past():
    word = SimpleNamespace(feature=SimpleNamespace(pos1="助動詞", lemma="ます"), surface="ます")

    assert is_past_aux(word) is False


def test_non_auxiliary_with_past_lemma_is_not_past_auxiliary():
    word = SimpleNamespace(feature=SimpleNamespace(pos1="動詞", lemma="た"), surface="た")

    assert is_past_aux(word) is False
