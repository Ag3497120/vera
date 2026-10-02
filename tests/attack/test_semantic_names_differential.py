"""Independent contract checks for semantic_names token and name helpers."""

from itertools import product
from types import SimpleNamespace
import unicodedata

import pytest

from verantyx.semantic_names import is_past_aux, name_split_in, tokens_covering


def _reference_tokens_covering(tagged, start, end):
    """Walk offsets from the requested start, without using the target helper."""
    remaining = [token for token in tagged if token[3] >= start and token[4] <= end]
    covered = []
    cursor = start
    while cursor < end:
        choices = [token for token in remaining if token[3] == cursor and token[4] > cursor]
        if len(choices) != 1:
            return None
        token = choices[0]
        covered.append(token)
        remaining.remove(token)
        cursor = token[4]
    return covered if covered and not remaining else None


def _is_han(char):
    if char == "々":
        return True
    try:
        name = unicodedata.name(char)
    except ValueError:
        return False
    return name.startswith(("CJK UNIFIED IDEOGRAPH-", "CJK COMPATIBILITY IDEOGRAPH-"))


def _reference_name_split(cover, value):
    """Apply the documented descriptor + one proper noun rule independently."""
    if not cover or len(cover) < 2 or "".join(token[0] for token in cover) != value:
        return None
    head = cover[-1]
    if head[1] != "名詞" or head[2] != "固有名詞":
        return None
    if any(token[1] not in ("名詞", "接尾辞") or token[2] == "固有名詞" for token in cover[:-1]):
        return None
    descriptor = "".join(token[0] for token in cover[:-1])
    if not descriptor or not all(_is_han(char) for char in descriptor):
        return None
    return descriptor, head[0]


def _token(surface, pos1, pos2, start):
    return (surface, pos1, pos2, start, start + len(surface))


def _partitions(length):
    """Yield every positive-width segmentation of an offset interval."""
    for cuts in product((False, True), repeat=length - 1):
        widths = []
        width = 1
        for cut in cuts:
            if cut:
                widths.append(width)
                width = 1
            else:
                width += 1
        widths.append(width)
        yield widths


def test_tokens_covering_returns_exact_subspan():
    tagged = [
        ("前", "名詞", "一般", 0, 1),
        ("技師", "名詞", "一般", 1, 3),
        ("ユン", "名詞", "固有名詞", 3, 5),
        ("後", "名詞", "一般", 5, 6),
    ]
    expected = tagged[1:3]
    assert _reference_tokens_covering(tagged, 1, 5) == expected
    assert tokens_covering(tagged, 1, 5) == expected


def test_tokens_covering_rejects_gaps_and_partial_edges():
    cases = [
        ([ ("a", "名詞", "一般", 0, 1), ("c", "名詞", "一般", 2, 3) ], 0, 3),
        ([ ("ab", "名詞", "一般", 0, 2) ], 1, 2),
        ([ ("bc", "名詞", "一般", 1, 3) ], 0, 2),
    ]
    for tagged, start, end in cases:
        assert _reference_tokens_covering(tagged, start, end) is None
        assert tokens_covering(tagged, start, end) is None


def test_generated_token_tilings_match_independent_reference():
    compared = 0
    for start in range(3):
        for length in range(1, 6):
            for widths in _partitions(length):
                tagged = []
                if start:
                    tagged.append(("p" * start, "名詞", "一般", 0, start))
                cursor = start
                for width in widths:
                    tagged.append(("x" * width, "名詞", "一般", cursor, cursor + width))
                    cursor += width
                tagged.append(("z", "名詞", "一般", cursor, cursor + 1))
                expected = _reference_tokens_covering(tagged, start, start + length)
                assert expected is not None
                assert tokens_covering(tagged, start, start + length) == expected
                compared += 1
    assert compared > 0


def test_name_split_accepts_kanji_title_appositive():
    cover = [
        _token("技", "名詞", "一般", 0),
        _token("師", "接尾辞", "一般", 1),
        _token("ユン", "名詞", "固有名詞", 2),
    ]
    assert _reference_name_split(cover, "技師ユン") == ("技師", "ユン")
    assert name_split_in(cover, "技師ユン") == ("技師", "ユン")


def test_name_split_requires_one_final_proper_noun_token():
    cover = [
        _token("技師", "名詞", "一般", 0),
        _token("ユン", "名詞", "固有名詞", 2),
        _token("さん", "名詞", "固有名詞", 4),
    ]
    assert _reference_name_split(cover, "技師ユンさん") is None
    assert name_split_in(cover, "技師ユンさん") is None


def test_name_split_rejects_non_kanji_title_and_bad_head_tags():
    cases = [
        ([_token("コカ", "名詞", "一般", 0), _token("カル", "名詞", "固有名詞", 2)], "コカカル"),
        ([_token("技師", "名詞", "一般", 0), _token("ユン", "名詞", "一般", 2)], "技師ユン"),
        ([_token("技師", "名詞", "固有名詞", 0), _token("ユン", "名詞", "固有名詞", 2)], "技師ユン"),
        ([_token("技師", "名詞", "一般", 0), _token("ユン", "動詞", "固有名詞", 2)], "技師ユン"),
        ([_token("技師", "名詞", "一般", 0), _token("ユン", "名詞", "固有名詞", 2)], "技師ヨン"),
    ]
    for cover, value in cases:
        expected = _reference_name_split(cover, value)
        assert expected is None
        assert name_split_in(cover, value) == expected


def test_generated_name_splits_match_independent_reference():
    titles = ("技師", "店長", "研究員", "町々")
    names = ("ユン", "花子", "王")
    compared = 0
    for title, name in product(titles, names):
        cover = [_token(title, "名詞", "一般", 0), _token(name, "名詞", "固有名詞", len(title))]
        expected = _reference_name_split(cover, title + name)
        assert expected == (title, name)
        assert name_split_in(cover, title + name) == expected
        compared += 1
    assert compared == len(titles) * len(names)


def test_past_aux_uses_lemma_for_voiced_surface():
    word = SimpleNamespace(feature=SimpleNamespace(pos1="助動詞", lemma="た"), surface="だ")
    assert is_past_aux(word) is True


def test_past_aux_rejects_non_past_lemma_even_with_past_surface():
    word = SimpleNamespace(feature=SimpleNamespace(pos1="助動詞", lemma="ます"), surface="た")
    assert is_past_aux(word) is False


def test_past_aux_requires_auxiliary_part_of_speech():
    word = SimpleNamespace(feature=SimpleNamespace(pos1="名詞", lemma="た"), surface="た")
    assert is_past_aux(word) is False


@pytest.mark.xfail(strict=False, reason="DEFECT: supplementary-plane kanji in a common-noun title is rejected")
def test_supplementary_plane_kanji_title_is_accepted_by_contract():
    cover = [
        _token("𠮷人", "名詞", "一般", 0),
        _token("ユン", "名詞", "固有名詞", 2),
    ]
    expected = _reference_name_split(cover, "𠮷人ユン")
    assert expected == ("𠮷人", "ユン")
    assert name_split_in(cover, "𠮷人ユン") == expected
