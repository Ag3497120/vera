from types import SimpleNamespace

import pytest

from verantyx.summarize import summarize


def store(crosses, source_labels=()):
    return SimpleNamespace(crosses=crosses, source_labels=set(source_labels))


def common_store():
    return store({"A": {"f": 1, "g": 2}, "B": {"f": 3, "g": 4}})


def test_one_held_path_returns_typed_refusal():
    result = summarize(
        store({"A": {"f": 1}}), ["A", "missing"],
        vocab={"A", "f"}, edges=lambda _subject, _facets: [],
    )

    assert result["verdict"] == "UNKNOWN_TOO_FEW_PATHS"
    assert result["held"] == ["A"]
    assert result["dropped_subjects"] == ["missing"]


def test_disjoint_paths_return_no_crossing_without_edge_lookup():
    result = summarize(
        store({"A": {"a": 1}, "B": {"b": 1}}), ["A", "B"],
        vocab={"A", "B", "a", "b"},
        edges=lambda *_: pytest.fail("edge lookup called without a crossing"),
    )

    assert result["verdict"] == "UNKNOWN_NO_CROSSING"
    assert result["held"] == ["A", "B"]


def test_missing_edge_lookup_is_a_typed_refusal():
    result = summarize(
        common_store(), ["A", "B"], vocab={"A", "B", "f", "g"},
        edges=None,
    )

    assert result["verdict"] == "UNKNOWN_NO_EDGE_LICENSE"
    assert result["crossing"] == 2


def test_co_presence_without_any_edge_does_not_make_a_claim():
    result = summarize(
        common_store(), ["A", "B"], vocab={"A", "B", "f", "g"},
        edges=lambda _subject, _facets: [],
    )

    assert result["verdict"] == "UNKNOWN_NO_EDGE_LICENSE"
    assert "kept" not in result


def test_claim_pair_is_recountable_from_the_edge_lookup():
    def edges(subject, facets):
        assert facets == ["f", "g"]
        return [("f", "g")] if subject == "A" else []

    result = summarize(
        common_store(), ["A", "B"], vocab={"A", "B", "f", "g"},
        edges=edges,
    )

    assert result["verdict"] == "SUMMARY"
    assert result["licensed"] == 1
    assert result["kept"] == [{
        "subject": "A", "pair": ["f", "g"], "width": 4, "mass": 3,
    }]
    assert result["text"] == "A: f と g（同一文）。"


def test_subject_outside_vocab_is_silent_and_reported():
    result = summarize(
        common_store(), ["A", "B"], vocab={"B", "f", "g"},
        edges=lambda subject, _facets: [("f", "g")] if subject == "B" else [],
    )

    assert result["verdict"] == "SUMMARY"
    assert [claim["subject"] for claim in result["kept"]] == ["B"]
    assert result["unspoken_subjects"] == ["A"]


def test_source_labels_are_dropped_as_subjects_and_facets():
    result = summarize(
        store({
            "A": {"f": 1, "g": 1, "meta": 100},
            "B": {"f": 1, "g": 1},
            "meta": {"f": 100, "g": 100},
        }, source_labels={"meta"}), ["A", "B", "meta"],
        vocab={"A", "B", "meta", "f", "g"},
        edges=lambda subject, _facets: [("f", "g")] if subject == "A" else [],
    )

    assert result["held"] == ["A", "B"]
    assert result["dropped_subjects"] == ["meta"]
    assert result["crossing"] == 2


def test_unheld_subject_is_reported_without_affecting_claim():
    result = summarize(
        common_store(), ["A", "B", "missing"],
        vocab={"A", "B", "f", "g"},
        edges=lambda subject, _facets: [("f", "g")] if subject == "A" else [],
    )

    assert result["verdict"] == "SUMMARY"
    assert result["held"] == ["A", "B"]
    assert result["dropped_subjects"] == ["missing"]
    assert [claim["subject"] for claim in result["kept"]] == ["A"]


def test_rank_tie_that_does_not_fit_is_dropped_as_a_whole_group():
    result = summarize(
        store({"A": {"f": 1, "g": 1}, "B": {"f": 1, "g": 1}}),
        ["A", "B"], vocab={"A", "B", "f", "g"},
        edges=lambda _subject, _facets: [("f", "g")], limit=1,
    )

    assert result["verdict"] == "SUMMARY"
    assert result["kept"] == []
    assert result["dropped_at_cut"] == 2
    assert result["text"] == ""


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: duplicate subject IDs count as separate paths and produce an unsupported summary",
)
def test_duplicate_subject_does_not_create_a_second_path():
    data = store({"A": {"f": 1, "g": 1}})
    outputs = [
        summarize(data, ["A", "A"], vocab={"A", "f", "g"},
                  edges=lambda _subject, _facets: [("f", "g")])
        for _ in range(2)
    ]

    assert [result["verdict"] for result in outputs] == [
        "UNKNOWN_TOO_FEW_PATHS", "UNKNOWN_TOO_FEW_PATHS",
    ]


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: edge lookup pairs outside the subject's crossing facets are emitted as claims",
)
def test_edge_pair_outside_crossing_facets_is_not_emitted():
    data = store({
        "A": {"f": 1, "g": 1, "private": 1},
        "B": {"f": 1, "g": 1},
    })
    outputs = [
        summarize(
            data, ["A", "B"],
            vocab={"A", "B", "f", "g", "private"},
            edges=lambda subject, _facets: [("f", "private")] if subject == "A" else [],
        )
        for _ in range(2)
    ]

    assert [result["verdict"] for result in outputs] == [
        "UNKNOWN_NO_EDGE_LICENSE", "UNKNOWN_NO_EDGE_LICENSE",
    ]
