from types import SimpleNamespace

import pytest

from verantyx.semantic_names import is_past_aux, name_split_in, tokens_covering


def _token(surface, pos1, pos2, start, end):
    return (surface, pos1, pos2, start, end)


def test_tokens_covering_uses_python_codepoint_offsets_around_astral_noise():
    tagged = [
        _token("🙂", "記号", "絵文字", 0, 1),
        _token("技師", "名詞", "一般", 1, 3),
        _token("ユン", "名詞", "固有名詞", 3, 5),
        _token("!", "記号", "一般", 5, 6),
    ]

    cover = tokens_covering(tagged, 1, 5)

    assert cover == tagged[1:3]
    assert name_split_in(cover, "技師ユン") == ("技師", "ユン")


def test_tokens_covering_refuses_a_gap():
    tagged = [
        _token("技", "名詞", "一般", 0, 1),
        _token("ユン", "名詞", "固有名詞", 2, 4),
    ]

    assert tokens_covering(tagged, 0, 4) is None


def test_tokens_covering_excludes_tokens_outside_requested_span():
    tagged = [
        _token("前", "名詞", "一般", 0, 1),
        _token("技師", "名詞", "一般", 1, 3),
        _token("山田", "名詞", "固有名詞", 3, 5),
        _token("後", "名詞", "一般", 5, 6),
    ]

    assert tokens_covering(tagged, 1, 5) == tagged[1:3]


def test_name_split_accepts_kanji_title_plus_one_proper_name():
    cover = [
        _token("技師", "名詞", "一般", 0, 2),
        _token("ユン", "名詞", "固有名詞", 2, 4),
    ]

    assert name_split_in(cover, "技師ユン") == ("技師", "ユン")


def test_name_split_refuses_non_kanji_descriptor():
    cover = [
        _token("tech", "名詞", "一般", 0, 4),
        _token("ユン", "名詞", "固有名詞", 4, 6),
    ]

    assert name_split_in(cover, "techユン") is None


def test_name_split_refuses_non_proper_final_token():
    cover = [
        _token("技師", "名詞", "一般", 0, 2),
        _token("ユン", "名詞", "一般", 2, 4),
    ]

    assert name_split_in(cover, "技師ユン") is None


def test_name_split_preserves_fullwidth_name_surface():
    cover = [
        _token("技師", "名詞", "一般", 0, 2),
        _token("ＡＢＣ", "名詞", "固有名詞", 2, 5),
    ]

    assert name_split_in(cover, "技師ＡＢＣ") == ("技師", "ＡＢＣ")


def test_name_split_preserves_decomposed_combining_sequence():
    decomposed_name = "か\u3099"
    cover = [
        _token("技師", "名詞", "一般", 0, 2),
        _token(decomposed_name, "名詞", "固有名詞", 2, 4),
    ]

    assert name_split_in(cover, "技師" + decomposed_name) == ("技師", decomposed_name)


def test_name_split_preserves_markup_and_emoji_in_tagged_name():
    noisy_name = "😀<b>Ａ</b>"
    cover = [
        _token("技師", "名詞", "一般", 0, 2),
        _token(noisy_name, "名詞", "固有名詞", 2, 11),
    ]

    assert name_split_in(cover, "技師" + noisy_name) == ("技師", noisy_name)


def test_name_split_refuses_zero_width_noise_inside_descriptor():
    noisy_title = "技\u200b師"
    cover = [
        _token(noisy_title, "名詞", "一般", 0, 3),
        _token("ユン", "名詞", "固有名詞", 3, 5),
    ]

    assert name_split_in(cover, noisy_title + "ユン") is None


def test_past_aux_uses_lemma_despite_noisy_surface():
    voiced_surface = SimpleNamespace(
        surface="読んだ\u200b",
        feature=SimpleNamespace(pos1="助動詞", lemma="た"),
    )
    other_auxiliary = SimpleNamespace(
        surface="読んだ",
        feature=SimpleNamespace(pos1="助動詞", lemma="だ"),
    )

    assert is_past_aux(voiced_surface) is True
    assert is_past_aux(other_auxiliary) is False


@pytest.mark.xfail(strict=False, reason="DEFECT: empty proper-name token creates a non-empty semantic split")
def test_name_split_refuses_empty_proper_name_token():
    cover = [
        _token("技師", "名詞", "一般", 0, 2),
        _token("", "名詞", "固有名詞", 2, 2),
    ]

    assert name_split_in(cover, "技師") is None
