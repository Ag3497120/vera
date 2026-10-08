from types import SimpleNamespace

import pytest

from verantyx.graded import GradedJudge, band_annotation, cores_as_items


def _store(crosses, source_labels=()):
    return SimpleNamespace(crosses=crosses, source_labels=set(source_labels))


def _settings(*, depth=1, rung=("whole", 0), name="whole"):
    return ((name, {"rungs": (rung,), "grammar": "raw", "depth": depth}),)


def _judge(store, *, depth=1, read=None, settings=None):
    return GradedJudge(
        settings or _settings(depth=depth), read=read or (lambda query: [query] if query else [])
    ).build(store)


def test_items_keep_core_identity_and_remove_source_labels():
    store = _store(
        {"topic": ["facet-b", "source.xml", "facet-a"], "source.xml": ["topic"]},
        {"source.xml"},
    )

    assert cores_as_items(store) == {"topic": ["topic", "facet-a", "facet-b"]}


def test_depth_truncates_facets_after_the_core_name():
    store = _store({"topic": ["facet-b", "facet-a"]})

    assert cores_as_items(store, depth=1) == {"topic": ["topic"]}
    assert cores_as_items(store, depth=2) == {"topic": ["topic", "facet-a"]}


def test_build_coverage_excludes_source_labels_from_cores_and_held_terms():
    store = _store(
        {"topic": ["facet", "source.xml"], "source.xml": ["topic"]},
        {"source.xml"},
    )
    judge = _judge(store, depth=None)

    assert judge.cores == {"topic"}
    assert judge.held == {"topic", "facet"}


def test_strict_core_name_can_resolve_even_when_another_core_mentions_it():
    store = _store({"alpha": [], "other": ["alpha"]})
    settings = (
        ("whole", {"rungs": (("whole", 0),), "grammar": "raw", "depth": 1}),
        ("mentions", {"rungs": (("whole", 0),), "grammar": "raw"}),
    )
    judge = _judge(store, read=lambda _query: ["alpha"], settings=settings)

    result = judge.ask("alpha")
    assert result["verdict"] == "ANSWER"
    assert result["item"] == "alpha"
    assert result["readings"]["whole"] == "alpha"
    assert result["item"] in judge.cores


def test_facet_coverage_does_not_make_a_depth_one_core_answer():
    store = _store({"topic": ["facet"]})
    result = _judge(store).ask("facet")

    assert result["verdict"] == "UNKNOWN_NOT_PRESENT"
    assert result["item"] is None
    assert result["covered"] == ["facet"]
    assert result["missing"] == []


def test_answer_from_facet_is_traceable_to_its_core_record():
    store = _store({"topic": ["alias"]})
    result = _judge(store, depth=None).ask("alias")

    assert result["verdict"] == "ANSWER"
    assert result["item"] == "topic"
    assert result["item"] in store.crosses
    assert "alias" in store.crosses[result["item"]]


def test_source_label_query_is_not_resolved_as_a_core_or_facet():
    store = _store({"topic": ["source.xml"]}, {"source.xml"})
    result = _judge(store, depth=None).ask("source.xml")

    assert result["verdict"] == "UNKNOWN_NOT_PRESENT"
    assert result["item"] is None
    assert result["covered"] == []
    assert result["missing"] == ["source.xml"]


def test_shared_facet_does_not_select_one_of_two_entities():
    store = _store({"entity-a": ["handle"], "entity-b": ["handle"]})
    settings = _settings(depth=None, name="mentions")
    result = _judge(store, settings=settings).ask("handle")

    assert result["item"] is None
    assert result["agreeing"] == 0
    assert result["readings"] == {"mentions": None}


def test_negated_query_item_still_points_to_the_named_core():
    store = _store({"アルファ": []})
    judge = GradedJudge(_settings(), read=None).build(store)

    result = judge.ask("アルファではない")
    assert result["verdict"] == "ANSWER"
    assert result["item"] == "アルファ"
    assert result["terms"] == ["アルファ"]
    assert result["item"] in judge.cores


def test_partial_window_match_is_typed_as_coarsening_and_shows_missing_term():
    store = _store({"abcd": []})
    settings = (
        ("whole", {"rungs": (("whole", 0),), "grammar": "raw", "depth": 1}),
        ("g2", {"rungs": (("g2", 2),), "grammar": "raw", "depth": 1}),
    )
    judge = _judge(store, read=lambda _query: ["ab"], settings=settings)

    result = judge.ask("ab")
    assert result["verdict"] == "ANSWER_BY_COARSENING"
    assert result["item"] == "abcd"
    assert result["readings"] == {"whole": None, "g2": "abcd"}
    assert result["covered"] == []
    assert result["missing"] == ["ab"]


def test_band_is_an_annotation_without_verdict_and_temporal_queries_have_none():
    store = _store({"alpha": []})
    judge = _judge(store)

    assert band_annotation(judge, "alpha") == {
        "agree": 1,
        "of": 1,
        "item": "alpha",
        "concord": 1.0,
    }

    temporal = _judge(
        _store({"weather": []}), read=lambda _query: ["weather"]
    )
    result = temporal.ask("today")
    assert result["verdict"] == "UNKNOWN_TIME_DEPENDENT"
    assert result["item"] is None
    assert band_annotation(temporal, "today") is None


def test_empty_and_contentless_queries_have_no_band():
    judge = _judge(_store({"alpha": []}), read=lambda _query: [])

    assert judge.ask("")["verdict"] == "UNKNOWN_UNPARSED"
    assert judge.ask("hello")["verdict"] == "UNKNOWN_NO_SUBJECT"
    assert band_annotation(judge, "hello") is None
