from types import SimpleNamespace

import pytest

from verantyx.semantic_names import is_past_aux, name_split_in, tokens_covering


def token(surface, pos1, pos2, start, end):
    return (surface, pos1, pos2, start, end)


def word(pos1, lemma):
    return SimpleNamespace(feature=SimpleNamespace(pos1=pos1, lemma=lemma))


def test_tokens_covering_returns_exact_contiguous_cover():
    tagged = [
        token("技師", "名詞", "一般", 0, 2),
        token("ユン", "名詞", "固有名詞", 2, 4),
    ]
    assert tokens_covering(tagged, 0, 4) == tagged


def test_tokens_covering_rejects_a_gap():
    tagged = [
        token("技", "名詞", "一般", 0, 1),
        token("ユン", "名詞", "固有名詞", 2, 4),
    ]
    assert tokens_covering(tagged, 0, 4) is None


def test_tokens_covering_rejects_a_token_crossing_the_requested_start():
    tagged = [token("研究員", "名詞", "一般", 0, 3)]
    assert tokens_covering(tagged, 1, 3) is None


def test_tokens_covering_ignores_tokens_disjoint_from_requested_span():
    tagged = [
        token("前", "名詞", "一般", 0, 1),
        token("技師", "名詞", "一般", 1, 3),
        token("ユン", "名詞", "固有名詞", 3, 5),
        token("後", "名詞", "一般", 5, 6),
    ]
    assert tokens_covering(tagged, 1, 5) == tagged[1:3]


def test_name_split_accepts_kanji_descriptor_and_one_proper_name():
    cover = [
        token("技師", "名詞", "一般", 0, 2),
        token("ユン", "名詞", "固有名詞", 2, 4),
    ]
    assert name_split_in(cover, "技師ユン") == ("技師", "ユン")


def test_name_split_rejects_non_kanji_prefix():
    cover = [
        token("コカ", "名詞", "一般", 0, 2),
        token("カル", "名詞", "固有名詞", 2, 4),
    ]
    assert name_split_in(cover, "コカカル") is None


def test_name_split_rejects_non_proper_final_token():
    cover = [
        token("技師", "名詞", "一般", 0, 2),
        token("見習い", "名詞", "一般", 2, 5),
    ]
    assert name_split_in(cover, "技師見習い") is None


def test_name_split_rejects_surface_mismatch():
    cover = [
        token("技師", "名詞", "一般", 0, 2),
        token("ユン", "名詞", "固有名詞", 2, 4),
    ]
    assert name_split_in(cover, "技師リン") is None


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: accepts an empty proper-name token and returns an unsupported empty name",
)
def test_empty_proper_name_token_cannot_fabricate_a_name():
    tagged = [
        token("技師", "名詞", "一般", 0, 2),
        token("", "名詞", "固有名詞", 2, 2),
    ]
    cover = tokens_covering(tagged, 0, 2)
    assert cover is not None
    assert name_split_in(cover, "技師") is None


def test_past_auxiliary_is_decided_by_lemma_including_voiced_surface():
    assert is_past_aux(word("助動詞", "た"))


def test_past_auxiliary_rejects_a_different_lemma():
    assert not is_past_aux(word("助動詞", "ます"))


def test_past_auxiliary_rejects_non_auxiliary_pos():
    assert not is_past_aux(word("動詞", "た"))
