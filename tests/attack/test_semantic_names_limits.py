from concurrent.futures import ThreadPoolExecutor
from gc import collect
from types import SimpleNamespace
import tracemalloc

import pytest

from verantyx.semantic_names import is_past_aux, name_split_in, tokens_covering


def token(surface, pos1, pos2, start, end):
    return surface, pos1, pos2, start, end


def test_tokens_covering_exact_interval_ignores_outside_tokens():
    tagged = [
        token("前", "名詞", "一般", 0, 1),
        token("技師", "名詞", "一般", 1, 3),
        token("ユン", "名詞", "固有名詞", 3, 5),
        token("後", "名詞", "一般", 5, 6),
    ]

    assert tokens_covering(tagged, 1, 5) == tagged[1:3]


def test_tokens_covering_refuses_gaps_and_empty_ranges():
    tagged = [token("技", "名詞", "一般", 0, 1), token("ユン", "名詞", "固有名詞", 2, 4)]

    assert tokens_covering(tagged, 0, 4) is None
    assert tokens_covering(tagged, 1, 1) is None
    assert tokens_covering([], 0, 0) is None


@pytest.mark.xfail(strict=False, reason="DEFECT: tokens_covering depends on token iteration order")
def test_tokens_covering_is_independent_of_input_order():
    tagged = [token("技師", "名詞", "一般", 0, 2), token("ユン", "名詞", "固有名詞", 2, 4)]

    assert tokens_covering(list(reversed(tagged)), 0, 4) == tagged


@pytest.mark.xfail(strict=False, reason="DEFECT: tokens_covering ignores a token crossing the requested boundary")
def test_tokens_covering_rejects_a_boundary_crossing_token():
    tagged = [
        token("技師", "名詞", "一般", 0, 2),
        token("師", "名詞", "一般", 1, 2),
    ]

    assert tokens_covering(tagged, 1, 2) is None


def test_name_split_accepts_kanji_title_and_one_proper_name():
    cover = [token("研究", "名詞", "一般", 0, 2), token("員", "接尾辞", "名詞性名詞接続", 2, 3), token("玲", "名詞", "固有名詞", 3, 4)]

    assert name_split_in(cover, "研究員玲") == ("研究員", "玲")


def test_name_split_refuses_non_kanji_prefixes_and_single_token_names():
    katakana_prefix = [token("コカ", "名詞", "一般", 0, 2), token("カル", "名詞", "固有名詞", 2, 4)]
    one_token = [token("玲", "名詞", "固有名詞", 0, 1)]

    assert name_split_in(katakana_prefix, "コカカル") is None
    assert name_split_in(one_token, "玲") is None


def test_name_split_rejects_noncovering_text_and_invalid_prefix_pos():
    mismatched_text = [token("技師", "名詞", "一般", 0, 2), token("玲", "名詞", "固有名詞", 2, 3)]
    proper_prefix = [token("技師", "名詞", "固有名詞", 0, 2), token("玲", "名詞", "固有名詞", 2, 3)]

    assert name_split_in(mismatched_text, "技師別") is None
    assert name_split_in(proper_prefix, "技師玲") is None


@pytest.mark.parametrize(
    ("pos1", "lemma", "expected"),
    [("助動詞", "た", True), ("助動詞", "です", False), ("動詞", "た", False)],
)
def test_past_aux_is_decided_by_pos_and_lemma(pos1, lemma, expected):
    word = SimpleNamespace(feature=SimpleNamespace(pos1=pos1, lemma=lemma))

    assert is_past_aux(word) is expected


def test_past_aux_accepts_voiced_surface_when_lemma_is_ta():
    word = SimpleNamespace(feature=SimpleNamespace(pos1="助動詞", lemma="た"), surface="だ")

    assert is_past_aux(word) is True


def test_large_cover_and_pathological_long_nonkanji_prefix_are_bounded():
    count = 20_000
    tagged = [token("技", "名詞", "一般", i, i + 1) for i in range(count)]
    tagged.append(token("玲", "名詞", "固有名詞", count, count + 1))
    value = "技" * count + "玲"

    cover = tokens_covering(tagged, 0, count + 1)
    assert len(cover) == count + 1
    assert name_split_in(cover, value) == ("技" * count, "玲")

    long_prefix = [token("ア", "名詞", "一般", i, i + 1) for i in range(count)]
    long_prefix.append(token("玲", "名詞", "固有名詞", count, count + 1))
    assert name_split_in(long_prefix, "ア" * count + "玲") is None


def test_repeated_calls_are_idempotent_and_do_not_mutate_inputs():
    tagged = [token("技師", "名詞", "一般", 0, 2), token("玲", "名詞", "固有名詞", 2, 3)]
    before = tagged.copy()
    expected = ("技師", "玲")

    for _ in range(100):
        assert name_split_in(tokens_covering(tagged, 0, 3), "技師玲") == expected
    assert tagged == before


def test_concurrent_independent_readers_do_not_share_results():
    cases = [
        ([token("技師", "名詞", "一般", 0, 2), token("玲", "名詞", "固有名詞", 2, 3)], "技師玲", ("技師", "玲")),
        ([token("店長", "名詞", "一般", 0, 2), token("葵", "名詞", "固有名詞", 2, 3)], "店長葵", ("店長", "葵")),
    ]

    def read_case(case):
        tagged, value, expected = case
        return [name_split_in(tokens_covering(tagged, 0, 3), value) for _ in range(200)], expected

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(read_case, cases))

    assert all(all(value == expected for value in values) for values, expected in results)


def test_repeated_calls_do_not_retain_per_call_allocations():
    tagged = [token("技師", "名詞", "一般", 0, 2), token("玲", "名詞", "固有名詞", 2, 3)]
    tracemalloc.start()
    try:
        for _ in range(100):
            name_split_in(tokens_covering(tagged, 0, 3), "技師玲")
        collect()
        baseline, _ = tracemalloc.get_traced_memory()
        for _ in range(2_000):
            name_split_in(tokens_covering(tagged, 0, 3), "技師玲")
        collect()
        retained, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert retained - baseline < 64 * 1024
