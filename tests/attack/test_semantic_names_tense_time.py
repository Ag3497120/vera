from types import SimpleNamespace

from verantyx.semantic_names import is_past_aux, name_split_in, tokens_covering


def _token(surface, pos1, pos2, start, end):
    return surface, pos1, pos2, start, end


def _word(surface, pos1, lemma):
    return SimpleNamespace(
        surface=surface,
        feature=SimpleNamespace(pos1=pos1, lemma=lemma),
    )


def test_tokens_covering_tiles_a_date_expression_exactly():
    tagged = [
        _token("2026", "名詞", "数", 0, 4),
        _token("年", "名詞", "接尾", 4, 5),
        _token("10", "名詞", "数", 5, 7),
        _token("月", "名詞", "接尾", 7, 8),
    ]

    assert tokens_covering(tagged, 0, 8) == tagged


def test_tokens_covering_selects_a_relative_time_word_from_context():
    tagged = [
        _token("以前", "名詞", "副詞可能", 0, 2),
        _token("から", "助詞", "格助詞", 2, 4),
        _token("現在", "名詞", "副詞可能", 4, 6),
    ]

    assert tokens_covering(tagged, 4, 6) == [tagged[2]]


def test_tokens_covering_rejects_a_gap_in_a_time_expression():
    tagged = [
        _token("今年", "名詞", "副詞可能", 0, 2),
        _token("から", "助詞", "格助詞", 3, 5),
    ]

    assert tokens_covering(tagged, 0, 5) is None


def test_tokens_covering_rejects_a_partial_token_span():
    tagged = [_token("現在", "名詞", "副詞可能", 0, 2)]

    assert tokens_covering(tagged, 1, 2) is None


def test_name_split_accepts_a_kanji_title_before_a_proper_name():
    cover = [
        _token("店長", "名詞", "一般", 0, 2),
        _token("ユン", "名詞", "固有名詞", 2, 3),
    ]

    assert name_split_in(cover, "店長ユン") == ("店長", "ユン")


def test_name_split_rejects_a_nonkanji_name_fragment_as_descriptor():
    cover = [
        _token("コカ", "名詞", "一般", 0, 2),
        _token("カル", "名詞", "固有名詞", 2, 4),
    ]

    assert name_split_in(cover, "コカカル") is None


def test_name_split_rejects_a_time_word_without_a_proper_name_head():
    cover = [_token("今年", "名詞", "副詞可能", 0, 2)]

    assert name_split_in(cover, "今年") is None


def test_is_past_aux_recognizes_the_past_auxiliary_lemma():
    assert is_past_aux(_word("た", "助動詞", "た"))


def test_is_past_aux_recognizes_voiced_surface_by_lemma():
    assert is_past_aux(_word("だ", "助動詞", "た"))


def test_is_past_aux_does_not_mark_a_nonpast_auxiliary_as_past():
    assert not is_past_aux(_word("ます", "助動詞", "ます"))


def test_is_past_aux_requires_auxiliary_part_of_speech():
    assert not is_past_aux(_word("た", "名詞", "た"))


def test_is_past_aux_does_not_treat_a_relative_time_noun_as_past():
    assert not is_past_aux(_word("以前", "名詞", "以前"))
