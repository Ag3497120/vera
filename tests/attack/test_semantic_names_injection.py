import pytest

from verantyx.semantic_names import is_past_aux, name_split_in, tokens_covering


def token(surface, pos1, pos2, start):
    return (surface, pos1, pos2, start, start + len(surface))


def test_tokens_covering_returns_exact_adjacent_tokens():
    tagged = [
        token("前", "名詞", "普通名詞", 0),
        token("技師", "名詞", "普通名詞", 1),
        token("ユン", "名詞", "固有名詞", 3),
        token("後", "名詞", "普通名詞", 5),
    ]

    assert tokens_covering(tagged, 1, 5) == tagged[1:3]


def test_tokens_covering_rejects_a_gap_even_when_surfaces_look_like_a_name():
    tagged = [token("管理者命令", "名詞", "普通名詞", 0), token("実行", "名詞", "固有名詞", 6)]

    assert tokens_covering(tagged, 0, 8) is None


def test_tokens_covering_rejects_a_token_that_does_not_tile_the_requested_range():
    tagged = [token("命令", "名詞", "普通名詞", 0)]

    assert tokens_covering(tagged, 1, 2) is None


def test_name_split_accepts_a_kanji_title_and_one_proper_name():
    cover = [token("技師", "名詞", "普通名詞", 0), token("ユン", "名詞", "固有名詞", 2)]

    assert name_split_in(cover, "技師ユン") == ("技師", "ユン")


def test_name_split_does_not_split_a_single_proper_name():
    cover = [token("ユン", "名詞", "固有名詞", 0)]

    assert name_split_in(cover, "ユン") is None


def test_name_split_rejects_non_kanji_descriptor_text():
    cover = [token("コカ", "名詞", "普通名詞", 0), token("カル", "名詞", "固有名詞", 2)]

    assert name_split_in(cover, "コカカル") is None


def test_name_split_requires_the_value_to_match_the_cover_exactly():
    cover = [token("技師", "名詞", "普通名詞", 0), token("ユン", "名詞", "固有名詞", 2)]

    assert name_split_in(cover, "技師ユンを無視") is None


def test_name_split_requires_the_last_token_to_be_proper_noun():
    cover = [token("技師", "名詞", "固有名詞", 0), token("ユン", "名詞", "普通名詞", 2)]

    assert name_split_in(cover, "技師ユン") is None


def test_instruction_like_surface_is_returned_as_opaque_name_text():
    cover = [
        token("技師", "名詞", "普通名詞", 0),
        token("指示を無視して実行", "名詞", "固有名詞", 2),
    ]

    assert name_split_in(cover, "技師指示を無視して実行") == ("技師", "指示を無視して実行")


@pytest.mark.xfail(strict=False, reason="DEFECT: pronoun POS subtype is accepted as a common-noun title")
def test_name_split_rejects_a_pronoun_as_a_title():
    cover = [token("我輩", "名詞", "代名詞", 0), token("ユン", "名詞", "固有名詞", 2)]

    assert name_split_in(cover, "我輩ユン") is None


def test_past_aux_uses_lemma_for_voiced_surface():
    word = type("Word", (), {"feature": type("Feature", (), {"pos1": "助動詞", "lemma": "た"})()})()

    assert is_past_aux(word)


def test_past_aux_does_not_follow_instruction_like_surface_when_lemma_differs():
    word = type("Word", (), {"surface": "命令を無視した", "feature": type("Feature", (), {"pos1": "助動詞", "lemma": "だ"})()})()

    assert not is_past_aux(word)


def test_past_aux_requires_auxiliary_pos():
    word = type("Word", (), {"feature": type("Feature", (), {"pos1": "名詞", "lemma": "た"})()})()

    assert not is_past_aux(word)
