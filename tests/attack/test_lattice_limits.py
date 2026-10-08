from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from verantyx.lattice import Lattice, analyze, build, kin, predict_facets, splits_of


def _snapshot(lat):
    return (
        tuple(sorted(lat.words)),
        tuple(sorted((key, tuple(sorted(value))) for key, value in lat.up.items())),
        tuple(sorted(lat.atoms)),
        lat.report(),
    )


def test_empty_input_builds_empty_lattice():
    lat = build([])

    assert lat.words == set()
    assert lat.up == {}
    assert lat.atoms == set()
    assert lat.report() == {"words": 0, "slots": 0, "atoms": 0}


def test_generator_duplicates_and_input_order_do_not_change_lattice():
    words = ["電荷密度", "電荷", "密度", "テレビ", "ドラマ", "テレビドラマ"]
    expected = _snapshot(build(words))

    assert _snapshot(build(reversed(words))) == expected
    assert _snapshot(build(w for w in words)) == expected
    assert _snapshot(build(words + words)) == expected


def test_long_compound_split_requires_both_attested_words():
    licensed = build(["テレビドラマ", "テレビ", "ドラマ"])
    unlicensed = build(["テレビドラマ", "テレビ"])

    assert ("テレビ", "ドラマ") in splits_of(licensed, "テレビドラマ")
    assert splits_of(unlicensed, "テレビドラマ") == []


def test_short_out_of_range_and_oversized_words_are_not_lattice_nodes():
    lat = build(["", "電", "電荷密度", "字" * 13, "字" * 100_000])

    assert lat.words == {"電荷密度"}
    assert "字" * 13 not in lat.words
    assert "字" * 100_000 not in lat.words


def test_analysis_depth_zero_returns_only_the_requested_node():
    lat = build(["電荷密度", "電荷", "密度", "電", "荷", "密", "度"])

    assert analyze(lat, "電荷密度", depth=0) == {
        "term": "電荷密度",
        "word": True,
        "atom": False,
    }


def test_analysis_respects_depth_and_keeps_attested_children():
    lat = build(["電荷密度", "電荷", "密度", "電", "荷", "密", "度"])

    tree = analyze(lat, "電荷密度", depth=1)
    assert tree["word"] is True
    assert tree["splits"]
    for branch in tree["splits"]:
        assert branch["left"]["term"] in lat.words | lat.atoms
        assert branch["right"]["term"] in lat.words | lat.atoms
        assert "splits" not in branch["left"]
        assert "splits" not in branch["right"]


def test_kin_is_sorted_excludes_term_and_obeys_positive_limit():
    lat = build(["電荷密度", "電荷電圧", "電荷電流"])

    families = kin(lat, "電荷密度", limit=1)
    assert "電荷密度" not in {word for values in families.values() for word in values}
    assert all(values == sorted(values) for values in families.values())
    assert all(len(values) <= 1 for values in families.values())
    assert families["電荷@L"] == ["電荷電圧"]


def test_prediction_uses_kin_counts_and_lexical_ties_with_top_budget():
    lat = Lattice(
        words={"電荷密度"},
        up={("電荷", "L"): {"電荷密度", "電荷電圧", "電荷電流"}},
    )
    store = SimpleNamespace(
        source_labels={"blocked"},
        crosses={
            "電荷電圧": {"facet-b": 2, "facet-a": 2, "blocked": 99, "電荷密度": 99},
            "電荷電流": {"facet-b": 2, "facet-a": 2, "blocked": 99, "電荷密度": 99},
        },
    )

    assert predict_facets(lat, store, "電荷密度", top=1) == ["facet-a"]
    assert predict_facets(lat, store, "電荷密度", top=0) == []


def test_repeated_queries_are_idempotent_and_do_not_mutate_lattice():
    lat = build(["電荷密度", "電荷", "密度", "電", "荷", "密", "度", "電荷電圧"])
    before = _snapshot(lat)
    first = (analyze(lat, "電荷密度"), kin(lat, "電荷密度"))

    for _ in range(20):
        assert (analyze(lat, "電荷密度"), kin(lat, "電荷密度")) == first
    assert _snapshot(lat) == before


def test_two_concurrent_readers_match_sequential_results():
    lat = build(["電荷密度", "電荷", "密度", "電", "荷", "密", "度", "電荷電圧"])
    store = SimpleNamespace(source_labels=set(), crosses={"電荷電圧": {"facet": 3}})

    def read_once(_):
        return (
            analyze(lat, "電荷密度"),
            kin(lat, "電荷密度"),
            predict_facets(lat, store, "電荷密度"),
        )

    expected = read_once(0)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(read_once, range(40)))

    assert results == [expected] * 40


def test_duplicate_heavy_build_keeps_unique_lattice_state_bounded():
    one = build(["電荷密度", "電荷", "密度"])
    repeated = build(["電荷密度", "電荷", "密度"] * 5_000)

    assert _snapshot(repeated) == _snapshot(one)


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: build leaks a raw TypeError for a non-string word instead of a typed refusal",
)
def test_non_string_word_should_produce_a_typed_refusal_not_raise():
    try:
        result = build([None])
    except Exception as exc:
        pytest.fail(f"raw {type(exc).__name__}: {exc}")

    assert hasattr(result, "refusal"), "invalid input should return a typed refusal"
