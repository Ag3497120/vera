from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from verantyx.semantic_coord import (
    chunk,
    coordination_ok,
    own_subject_phrase,
    phrase_bounded,
    tag,
    topic_phrase,
)


def _tokens(*items):
    """Build contiguous semantic_coord tokens from (surface, pos1, pos2, cform)."""
    tagged = []
    at = 0
    for surface, pos1, pos2, cform in items:
        end = at + len(surface)
        tagged.append((surface, pos1, pos2, cform, at, end))
        at = end
    return tagged


def _word(surface, pos1, pos2, cform):
    return SimpleNamespace(
        surface=surface,
        feature=SimpleNamespace(pos1=pos1, pos2=pos2, cForm=cform),
    )


def test_coordination_accepts_te_comma_chain():
    tagged = _tokens(
        ("太郎", "名詞", "固有名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("走り", "動詞", "自立", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("、", "補助記号", "読点", ""),
        ("帰る", "動詞", "自立", "終止形"),
    )

    assert coordination_ok(tagged, [2, 5]) is True


def test_coordination_accepts_renyo_comma_chain():
    tagged = _tokens(
        ("歩き", "動詞", "自立", "連用形"),
        ("、", "補助記号", "読点", ""),
        ("帰る", "動詞", "自立", "終止形"),
    )

    assert coordination_ok(tagged, [0, 2]) is True


def test_coordination_rejects_adversative_particle():
    tagged = _tokens(
        ("歩き", "動詞", "自立", "連用形"),
        ("が", "助詞", "接続助詞", ""),
        ("帰る", "動詞", "自立", "終止形"),
    )

    assert coordination_ok(tagged, [0, 2]) is False


def test_coordination_requires_nonfinal_renyo_form():
    tagged = _tokens(
        ("歩く", "動詞", "自立", "終止形"),
        ("て", "助詞", "接続助詞", ""),
        ("帰る", "動詞", "自立", "終止形"),
    )

    assert coordination_ok(tagged, [0, 2]) is False


def test_chunk_and_topic_phrase_stay_in_first_clause():
    tagged = _tokens(
        ("太郎", "名詞", "固有名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("走り", "動詞", "自立", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("、", "補助記号", "読点", ""),
        ("花子", "名詞", "固有名詞", ""),
        ("が", "助詞", "格助詞", ""),
        ("帰る", "動詞", "自立", "終止形"),
    )

    assert topic_phrase(tagged, [2, 7]) == (0, 2)
    assert chunk(tagged, [2, 7], 1) == (5, 7)
    assert own_subject_phrase(tagged, 5, 7) is True
    assert own_subject_phrase(tagged, 5, 6) is False


def test_phrase_bounded_accepts_phrase_at_chunk_start():
    tagged = _tokens(
        ("太郎", "名詞", "固有名詞", ""),
        ("が", "助詞", "格助詞", ""),
        ("来た", "動詞", "自立", "過去形"),
    )

    assert phrase_bounded(tagged, 0, 2) is True


def test_phrase_bounded_rejects_start_after_an_unseparated_noun():
    tagged = _tokens(
        ("太郎", "名詞", "固有名詞", ""),
        ("次郎", "名詞", "固有名詞", ""),
        ("が", "助詞", "格助詞", ""),
    )

    assert phrase_bounded(tagged, 2, 4) is False


def test_tag_keeps_features_and_character_offsets():
    words = [
        _word("犬", "名詞", "一般", ""),
        _word("は", "助詞", "係助詞", ""),
    ]

    assert tag(words, [3, 4]) == [
        ("犬", "名詞", "一般", "", 3, 4),
        ("は", "助詞", "係助詞", "", 4, 5),
    ]


def test_empty_and_single_predicate_inputs_are_refused():
    assert coordination_ok([], []) is False
    assert coordination_ok([], [0]) is False


def test_large_coordination_chain_completes_with_expected_result():
    count = 2000
    tagged = []
    pred_idx = []
    at = 0
    for i in range(count):
        pred_idx.append(len(tagged))
        surface = "歩き" if i < count - 1 else "帰る"
        cform = "連用形" if i < count - 1 else "終止形"
        tagged.append((surface, "動詞", "自立", cform, at, at + len(surface)))
        at += len(surface)
        if i < count - 1:
            tagged.append(("、", "補助記号", "読点", "", at, at + 1))
            at += 1

    assert coordination_ok(tagged, pred_idx) is True


def test_repeated_and_concurrent_calls_are_deterministic():
    accepted = _tokens(
        ("太郎", "名詞", "固有名詞", ""),
        ("は", "助詞", "係助詞", ""),
        ("走り", "動詞", "自立", "連用形"),
        ("て", "助詞", "接続助詞", ""),
        ("、", "補助記号", "読点", ""),
        ("帰る", "動詞", "自立", "終止形"),
    )
    refused = _tokens(
        ("歩き", "動詞", "自立", "連用形"),
        ("が", "助詞", "接続助詞", ""),
        ("帰る", "動詞", "自立", "終止形"),
    )
    cases = [(accepted, [2, 5]), (refused, [0, 2])] * 20

    def read(case):
        tagged, pred_idx = case
        return coordination_ok(tagged, pred_idx), topic_phrase(tagged, pred_idx)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(read, cases))

    assert results == [(True, (0, 2)), (False, None)] * 20


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: accepts phrase spans whose endpoints cut through a token",
)
def test_phrase_bounded_rejects_mid_token_fragment():
    tagged = _tokens(("ククル", "名詞", "一般", ""))

    assert phrase_bounded(tagged, 1, 2) is False


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: out-of-range predicate indices raise IndexError",
)
def test_coordination_refuses_out_of_range_predicate_indices():
    tagged = _tokens(("歩き", "動詞", "自立", "連用形"))

    assert coordination_ok(tagged, [99, 100]) is False
