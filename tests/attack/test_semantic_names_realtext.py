from types import SimpleNamespace

from verantyx.semantic_names import is_past_aux, name_split_in, tokens_covering


def token(surface, pos1, pos2, start, end):
    return (surface, pos1, pos2, start, end)


def test_tokens_covering_returns_exact_contiguous_span():
    tokens = [
        token("前", "名詞", "一般", 0, 1),
        token("技師", "名詞", "一般", 1, 3),
        token("ユン", "名詞", "固有名詞", 3, 5),
        token("後", "名詞", "一般", 5, 6),
    ]

    assert tokens_covering(tokens, 1, 5) == tokens[1:3]


def test_tokens_covering_rejects_a_gap():
    tokens = [token("技", "名詞", "一般", 0, 1), token("ユン", "名詞", "固有名詞", 2, 4)]

    assert tokens_covering(tokens, 0, 4) is None


def test_tokens_covering_rejects_a_token_crossing_the_requested_start():
    tokens = [token("技師", "名詞", "一般", 0, 2), token("ユン", "名詞", "固有名詞", 2, 4)]

    assert tokens_covering(tokens, 1, 4) is None


def test_tokens_covering_rejects_overlapping_tokens():
    tokens = [token("技", "名詞", "一般", 0, 2), token("師ユン", "名詞", "固有名詞", 1, 4)]

    assert tokens_covering(tokens, 0, 4) is None


def test_name_split_accepts_kanji_title_and_one_proper_name():
    cover = [token("技師", "名詞", "一般", 0, 2), token("ユン", "名詞", "固有名詞", 2, 3)]

    assert name_split_in(cover, "技師ユン") == ("技師", "ユン")


def test_name_split_keeps_katakana_name_fragment_intact():
    cover = [token("コカ", "名詞", "一般", 0, 2), token("カル", "名詞", "固有名詞", 2, 4)]

    assert name_split_in(cover, "コカカル") is None


def test_name_split_rejects_non_proper_final_token():
    cover = [token("技師", "名詞", "一般", 0, 2), token("ユン", "名詞", "一般", 2, 3)]

    assert name_split_in(cover, "技師ユン") is None


def test_name_split_rejects_proper_name_in_descriptor_tokens():
    cover = [token("東", "名詞", "固有名詞", 0, 1), token("京", "名詞", "固有名詞", 1, 2)]

    assert name_split_in(cover, "東京") is None


def test_name_split_requires_multiple_tokens_and_exact_surface():
    proper = token("ユン", "名詞", "固有名詞", 0, 1)
    cover = [token("技師", "名詞", "一般", 0, 2), token("ユン", "名詞", "固有名詞", 2, 3)]

    assert name_split_in([proper], "ユン") is None
    assert name_split_in(cover, "技師ユンさん") is None


def test_is_past_aux_uses_lemma_for_voiced_surface():
    word = SimpleNamespace(feature=SimpleNamespace(pos1="助動詞", lemma="た"))

    assert is_past_aux(word)


def test_is_past_aux_rejects_other_lemma_or_part_of_speech():
    wrong_lemma = SimpleNamespace(feature=SimpleNamespace(pos1="助動詞", lemma="だ"))
    wrong_pos = SimpleNamespace(feature=SimpleNamespace(pos1="名詞", lemma="た"))

    assert not is_past_aux(wrong_lemma)
    assert not is_past_aux(wrong_pos)
