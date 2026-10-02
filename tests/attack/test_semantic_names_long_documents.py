from types import SimpleNamespace

import pytest

from verantyx.semantic_names import is_past_aux, name_split_in, tokens_covering


def tok(surface, pos1, pos2, start, end):
    return surface, pos1, pos2, start, end


def word(pos1, lemma):
    return SimpleNamespace(feature=SimpleNamespace(pos1=pos1, lemma=lemma))


def test_covering_selects_exact_span_from_a_long_sentence():
    prefix = "前置文" * 4000
    value = "主任研究員ユン"
    start = len(prefix)
    tagged = [
        tok(prefix, "名詞", "一般", 0, start),
        tok("主任", "名詞", "一般", start, start + 2),
        tok("研究員", "名詞", "一般", start + 2, start + 5),
        tok("ユン", "名詞", "固有名詞", start + 5, start + len(value)),
        tok("後置文", "名詞", "一般", start + len(value), start + len(value) + 3),
    ]

    cover = tokens_covering(tagged, start, start + len(value))

    assert cover == tagged[1:4]
    assert name_split_in(cover, value) == ("主任研究員", "ユン")


def test_covering_excludes_context_and_requires_contiguous_tokens():
    tagged = [
        tok("前", "名詞", "一般", 0, 1),
        tok("技師", "名詞", "一般", 1, 3),
        tok("ユン", "名詞", "固有名詞", 3, 4),
        tok("後", "名詞", "一般", 4, 5),
    ]

    assert tokens_covering(tagged, 1, 4) == tagged[1:3]
    assert tokens_covering([tagged[1], tok("隙", "名詞", "一般", 4, 5)], 1, 5) is None


def test_covering_rejects_overlapping_tokens():
    tagged = [
        tok("技師", "名詞", "一般", 0, 3),
        tok("師ユン", "名詞", "固有名詞", 2, 5),
    ]

    assert tokens_covering(tagged, 0, 5) is None


def test_covering_rejects_tokens_that_cross_requested_boundaries():
    tagged = [
        tok("技師ユン", "名詞", "固有名詞", 0, 5),
        tok("後", "名詞", "一般", 5, 6),
    ]

    assert tokens_covering(tagged, 1, 5) is None


def test_name_split_accepts_multiple_kanji_title_tokens():
    cover = [
        tok("主任", "名詞", "一般", 0, 2),
        tok("研究員", "名詞", "一般", 2, 5),
        tok("ユン", "名詞", "固有名詞", 5, 6),
    ]

    assert name_split_in(cover, "主任研究員ユン") == ("主任研究員", "ユン")


def test_name_split_does_not_cut_katakana_unknown_name():
    cover = [
        tok("コカ", "名詞", "一般", 0, 2),
        tok("カル", "名詞", "固有名詞", 2, 4),
    ]

    assert name_split_in(cover, "コカカル") is None


def test_name_split_requires_a_proper_noun_as_the_final_token():
    cover = [
        tok("店長", "名詞", "一般", 0, 2),
        tok("ユン", "名詞", "一般", 2, 3),
    ]

    assert name_split_in(cover, "店長ユン") is None


def test_name_split_requires_descriptor_tokens_to_be_kanji():
    cover = [
        tok("の", "助詞", "連体化", 0, 1),
        tok("ユン", "名詞", "固有名詞", 1, 2),
    ]

    assert name_split_in(cover, "のユン") is None


def test_name_split_requires_surface_to_match_value():
    cover = [
        tok("技師", "名詞", "一般", 0, 2),
        tok("ユン", "名詞", "固有名詞", 2, 3),
    ]

    assert name_split_in(cover, "技師リン") is None


def test_repeated_entities_and_conflicting_titles_stay_document_local():
    for index in range(64):
        prefix = "背景" * (index + 1)
        descriptor = "技師" if index % 2 == 0 else "研究員"
        start = len(prefix)
        tagged = [
            tok(prefix, "名詞", "一般", 0, start),
            tok(descriptor, "名詞", "一般", start, start + len(descriptor)),
            tok("ユン", "名詞", "固有名詞", start + len(descriptor), start + len(descriptor) + 1),
        ]

        cover = tokens_covering(tagged, start, start + len(descriptor) + 1)

        assert name_split_in(cover, descriptor + "ユン") == (descriptor, "ユン")


@pytest.mark.parametrize(
    ("pos1", "lemma", "expected"),
    [
        ("助動詞", "た", True),
        ("助動詞", "だ", False),
        ("動詞", "た", False),
    ],
)
def test_past_auxiliary_uses_auxiliary_pos_and_lemma(pos1, lemma, expected):
    assert is_past_aux(word(pos1, lemma)) is expected
