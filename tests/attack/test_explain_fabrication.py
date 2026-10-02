"""Adversarial provenance checks for constructed unit explanations."""

from types import SimpleNamespace
import importlib

import pytest

import verantyx.explain as explain_module
import verantyx.granularity as granularity


reach_module = importlib.import_module("verantyx.reach")


def _setup(monkeypatch, term, patterns, slots, crosses, vocab, labels=()):
    monkeypatch.setattr(granularity, "SPLITS", {len(term): patterns})
    monkeypatch.setattr(
        reach_module, "reach", lambda store, term, *, model, judge: {"verdict": "UNITS"}
    )
    model = SimpleNamespace(slots=slots)
    store = SimpleNamespace(crosses=crosses, source_labels=set(labels))
    return model, store, set(vocab)


@pytest.mark.parametrize("verdict", ["HELD", "CONTAINMENT", "UNKNOWN_NO_REACH"])
def test_non_units_result_is_returned_unchanged(monkeypatch, verdict):
    expected = {"verdict": verdict, "term": "ABCD", "detail": ["existing"]}
    monkeypatch.setattr(reach_module, "reach", lambda *args, **kwargs: expected)

    observed = explain_module.explain(None, "ABCD", model=None, vocab=set())

    assert observed is expected
    assert observed["detail"] == ["existing"]


def test_two_held_words_are_reported_with_their_shared_held_facet(monkeypatch):
    term = "ABCD"
    model, store, vocab = _setup(
        monkeypatch,
        term,
        [(2, 2)],
        {(2, "L"): {"AB"}, (2, "R"): {"CD"}},
        {"AB": {"COMMON", "LEFT_ONLY"}, "CD": {"COMMON", "RIGHT_ONLY"}},
        {"AB", "CD", "COMMON"},
    )

    out = explain_module.explain(store, term, model=model, vocab=vocab)

    assert out["verdict"] == "EXPLAINED_BY_UNITS"
    assert out["constructed"] is True
    assert out["split"] == ["AB", "CD"]
    assert out["units"] == [
        {"part": "CD", "position": "R", "held": True, "word": True},
        {"part": "AB", "position": "L", "held": True, "word": True},
    ]
    assert out["crossing"] == ["COMMON"]
    assert out["subject"] == "CD"
    assert out["subject_position"] == "R"
    assert out["text"] == (
        "ABCDは、ABとCDに分解される。両単位の十字が共有する面: "
        "COMMON。" + explain_module.CONSTRUCTED_MARK
    )


def test_single_spoken_unit_keeps_its_left_role_and_subject(monkeypatch):
    term = "ABCD"
    model, store, vocab = _setup(
        monkeypatch,
        term,
        [(2, 2)],
        {(2, "L"): {"AB"}, (2, "R"): {"CD"}},
        {"AB": set(), "CD": set()},
        {"AB"},
    )

    out = explain_module.explain(store, term, model=model, vocab=vocab)

    assert out["subject"] == "AB"
    assert out["subject_position"] == "L"
    assert out["text"].startswith("ABCDは、ABを単位に含む。")
    assert "CDを単位に含む" not in out["text"]


def test_source_label_is_not_misreported_as_a_held_unit(monkeypatch):
    term = "ABCD"
    model, store, vocab = _setup(
        monkeypatch,
        term,
        [(2, 2)],
        {(2, "L"): {"AB"}, (2, "R"): {"CD"}},
        {"AB": set(), "CD": set()},
        {"AB", "CD"},
        labels={"CD"},
    )

    out = explain_module.explain(store, term, model=model, vocab=vocab)

    assert out["verdict"] == "EXPLAINED_BY_UNITS"
    assert out["units"] == [
        {"part": "CD", "position": "R", "held": False, "word": True},
        {"part": "AB", "position": "L", "held": True, "word": True},
    ]
    assert out["subject"] == "AB"


def test_unworded_shared_facet_stays_in_audit_data_not_draft_text(monkeypatch):
    term = "ABCD"
    model, store, vocab = _setup(
        monkeypatch,
        term,
        [(2, 2)],
        {(2, "L"): {"AB"}, (2, "R"): {"CD"}},
        {"AB": {"COMMON", "PRIVATE"}, "CD": {"COMMON", "PRIVATE"}},
        {"AB", "CD", "COMMON"},
    )

    out = explain_module.explain(store, term, model=model, vocab=vocab)

    assert out["crossing"] == ["COMMON", "PRIVATE"]
    assert "COMMON" in out["text"]
    assert "PRIVATE" not in out["text"]


def test_edge_lookup_receives_selected_subject_and_only_shown_units(monkeypatch):
    term = "ABCD"
    model, store, vocab = _setup(
        monkeypatch,
        term,
        [(2, 2)],
        {(2, "L"): {"AB"}, (2, "R"): {"CD"}},
        {"AB": {"COMMON"}, "CD": {"COMMON"}},
        {"AB", "CD", "COMMON"},
    )
    calls = []
    attested_pairs = [("CD", "AB", "same-sentence")]

    def edges(core, shown):
        calls.append((core, shown))
        return attested_pairs

    out = explain_module.explain(store, term, model=model, vocab=vocab, edges=edges)

    assert calls == [("CD", ["AB", "COMMON"])]
    assert out["edge_pairs"] == attested_pairs


def test_edge_lookup_failure_does_not_change_the_unit_explanation(monkeypatch):
    term = "ABCD"
    model, store, vocab = _setup(
        monkeypatch,
        term,
        [(2, 2)],
        {(2, "L"): {"AB"}, (2, "R"): {"CD"}},
        {"AB": set(), "CD": set()},
        {"AB", "CD"},
    )

    def broken_edges(core, shown):
        raise RuntimeError("lookup unavailable")

    out = explain_module.explain(store, term, model=model, vocab=vocab, edges=broken_edges)

    assert out["verdict"] == "EXPLAINED_BY_UNITS"
    assert "edge_pairs" not in out
    assert out["constructed"] is True


def test_bare_suffix_candidate_abstains_at_the_split(monkeypatch):
    term = "AB"
    model, store, vocab = _setup(
        monkeypatch,
        term,
        [(1, 1)],
        {(1, "L"): {"A"}, (1, "R"): {"B"}},
        {"A": set(), "B": set()},
        {"A", "B"},
    )

    out = explain_module.explain(store, term, model=model, vocab=vocab)

    assert out["verdict"] == "ABSTAIN_BARE_SUFFIX_SPLIT"
    assert out["constructed"] is True
    assert out["term"] == term


def test_no_held_unit_passing_vocabulary_gate_abstains(monkeypatch):
    term = "ABCD"
    model, store, vocab = _setup(
        monkeypatch,
        term,
        [(2, 2)],
        {(2, "L"): {"AB"}, (2, "R"): {"CD"}},
        {"AB": set(), "CD": set()},
        set(),
    )

    out = explain_module.explain(store, term, model=model, vocab=vocab)

    assert out["verdict"] == "ABSTAIN_UNIT_NOT_A_WORD"
    assert out["constructed"] is True
    assert all(unit["held"] and not unit["word"] for unit in out["units"])


def test_equal_best_splits_abstain_instead_of_swapping_roles(monkeypatch):
    term = "ABCDEFG"
    model, store, vocab = _setup(
        monkeypatch,
        term,
        [(2, 5), (3, 4)],
        {
            (2, "L"): {"AB"},
            (5, "R"): {"CDEFG"},
            (3, "L"): {"ABC"},
            (4, "R"): {"DEFG"},
        },
        {"AB": set(), "CDEFG": set(), "ABC": set(), "DEFG": set()},
        {"AB", "CDEFG", "ABC", "DEFG"},
    )

    out = explain_module.explain(store, term, model=model, vocab=vocab)

    assert out["verdict"] == "ABSTAIN_SPLIT_TIED"
    assert out["splits"] == [["AB", "CDEFG"], ["ABC", "DEFG"]]


def test_partial_slot_span_does_not_match_a_candidate_unit(monkeypatch):
    term = "ABCD"
    monkeypatch.setattr(granularity, "SPLITS", {4: [(2, 2)]})
    model = SimpleNamespace(slots={(2, "L"): {"BC"}, (2, "R"): {"CD"}})

    assert explain_module._splits_for(model, term) == []
