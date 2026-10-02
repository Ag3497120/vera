from types import SimpleNamespace

import pytest

from verantyx.lattice import (
    analyze,
    build,
    kin,
    predict_facets,
    splits_of,
)


def test_build_keeps_only_supported_length_range():
    lat = build(["x", "ab", "abcdefghijkl", "abcdefghijklm"])

    assert lat.words == {"ab", "abcdefghijkl"}


def test_documented_short_compound_split_has_attested_children():
    lat = build(["電荷密度", "電荷", "密度"])

    assert ("電荷", "密度") in splits_of(lat, "電荷密度")
    tree = analyze(lat, "電荷密度", depth=1)
    assert tree["word"] is True
    assert any(
        branch["left"]["term"] == "電荷"
        and branch["left"]["word"]
        and branch["right"]["term"] == "密度"
        and branch["right"]["word"]
        for branch in tree.get("splits", [])
    )


def test_short_compound_does_not_split_into_unattested_halves():
    lat = build(["甲乙丙丁"])

    assert splits_of(lat, "甲乙丙丁") == []


def test_long_window_accepts_only_a_cut_with_two_attested_words():
    lat = build(["甲乙丙丁戊己", "甲乙", "丙丁戊己"])

    assert splits_of(lat, "甲乙丙丁戊己") == [("甲乙", "丙丁戊己")]


def test_long_window_does_not_use_single_character_halves():
    lat = build(["甲乙丙丁戊己", "甲", "乙丙丁戊己"])

    assert "甲" not in lat.words
    assert all(left != "甲" for left, _right in splits_of(lat, "甲乙丙丁戊己"))


def test_kin_keeps_left_and_right_positions_separate():
    lat = build(["電荷", "電気", "電子", "発電"])

    related = kin(lat, "電荷")
    assert related["電@L"] == ["電子", "電気"]
    assert "発電" not in related["電@L"]
    assert "電荷" not in related["電@L"]


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: build indexes unattested multi-character fragments as kin units",
)
def test_kin_does_not_use_an_unattested_multi_character_fragment():
    lat = build(["甲乙丙丁", "甲乙戊己"])

    assert "甲乙" not in lat.words
    assert "甲乙" not in lat.atoms
    assert "甲乙@L" not in kin(lat, "甲乙丙丁")


def test_predict_facets_uses_neighbor_counts_and_filters_labels():
    lat = build(["電荷", "電気", "電子"])
    store = SimpleNamespace(
        source_labels={"source"},
        crosses={
            "電気": {"z": 2, "電荷": 70, "source": 99},
            "電子": {"a": 2, "b": 2, "z": 1},
        },
    )

    assert predict_facets(lat, store, "電荷") == ["z", "a", "b"]


def test_predict_facets_does_not_read_the_target_cross():
    lat = build(["電荷"])
    store = SimpleNamespace(
        source_labels=set(),
        crosses={"電荷": {"unsupported-own-facet": 100}},
    )

    assert predict_facets(lat, store, "電荷") == []


def test_predict_facets_returns_no_facets_without_kin():
    lat = build(["電荷", "海岸"])
    store = SimpleNamespace(
        source_labels=set(),
        crosses={"海岸": {"coast-facet": 3}},
    )

    assert predict_facets(lat, store, "電荷") == []
