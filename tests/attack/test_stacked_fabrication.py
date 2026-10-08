"""Independent provenance checks for the stacked inference path."""
from __future__ import annotations

import importlib
import sys
from types import ModuleType, SimpleNamespace

import pytest

from verantyx.stacked import (
    aspect_read,
    compare_shape,
    en_shape,
    in_words,
    quote_in_words,
    subject_check,
    yes_no,
    yes_no_en,
)


def _set_runs(monkeypatch, runs):
    lang = importlib.import_module("verantyx.lang")
    monkeypatch.setattr(lang, "ja_content_runs", lambda _query: list(runs))


def test_subject_check_reseeds_to_the_asked_held_subject(monkeypatch):
    _set_runs(monkeypatch, ["相殺", "効果"])
    store = SimpleNamespace(crosses={"相殺": {"効果": 1}, "効果": {"別件": 1}})

    out = subject_check(store, "相殺の効果は", "効果")

    assert out["subject"] == "相殺"
    assert out["reseed"] == "相殺"


def test_subject_check_refuses_a_subject_absent_from_all_records(monkeypatch):
    _set_runs(monkeypatch, ["未登録主題", "刑"])
    store = SimpleNamespace(crosses={"刑": {"処分": 1}})

    out = subject_check(store, "未登録主題の刑は", "刑")

    assert out["ok"] is False
    assert out["subject"] == "未登録主題"


def test_subject_check_allows_a_subject_named_on_the_seed_cross(monkeypatch):
    _set_runs(monkeypatch, ["背任罪", "刑"])
    store = SimpleNamespace(crosses={"利得罪": {"背任罪": 2, "刑": 1}})

    out = subject_check(store, "背任罪の刑は", "利得罪")

    assert out["ok"] is True
    assert out["via"] == "facet_of_seed"
    assert out["subject"] == "背任罪"


def test_yes_no_attests_only_the_subjects_recorded_condition(monkeypatch):
    _set_runs(monkeypatch, ["契約", "解除"])
    store = SimpleNamespace(crosses={"契約": {"解除": 3, "方式": 1}})

    out = yes_no(store, "契約は解除できますか")

    assert out["verdict"] == "ATTESTED"
    assert out["text"].split() == ["契約", "解除"]
    assert out["attested"]["解除"] == ["解除"]


def test_yes_no_gap_is_not_reported_as_negation(monkeypatch):
    _set_runs(monkeypatch, ["塩", "効能"])
    store = SimpleNamespace(crosses={"塩": {"味": 2}})

    out = yes_no(store, "塩は効能がありますか")

    assert out["verdict"] == "NOT_ATTESTED"
    assert out["unattested"] == ["効能"]
    assert out["text"] == ""
    assert out["verdict"] != "DENIED"


def test_english_yes_no_gap_stays_empty_instead_of_becoming_a_no():
    store = SimpleNamespace(crosses={"alpha": {"water": 2}})

    out = yes_no_en(store, "Can Alpha swim?")

    assert out["verdict"] == "NOT_ATTESTED"
    assert out["unattested"] == ["swim"]
    assert out["text"] == ""


def test_english_yes_no_cites_the_facet_that_contains_its_condition():
    store = SimpleNamespace(crosses={"alpha": {"can fly": 2}})

    out = yes_no_en(store, "Can Alpha fly?")

    assert out["verdict"] == "ATTESTED"
    assert out["attested"] == {"fly": ["can fly"]}
    assert out["text"] == "alpha can fly"


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: substring matching treats embedded fragments as attested conditions",
)
def test_english_substring_defect_is_reproduced_twice():
    """The two independent calls above must both refuse unsupported fragments."""
    store = SimpleNamespace(crosses={"alpha": {"house": 2, "cart": 1}})
    repeated = [yes_no_en(store, "Does Alpha use art?") for _ in range(2)]

    assert [out["verdict"] for out in repeated] == ["NOT_ATTESTED", "NOT_ATTESTED"]


def test_comparison_requires_both_named_records():
    store = SimpleNamespace(crosses={"Alpha": {"shared": 1}})

    out = compare_shape(store, "AlphaとBetaの違いは")

    assert out["verdict"] == "UNKNOWN_NOT_PRESENT"
    assert out["subject"] == "Beta"
    assert "only_a" not in out and "only_b" not in out


def test_comparison_lists_only_facets_present_in_the_two_records():
    store = SimpleNamespace(crosses={
        "Alpha": {"shared": 5, "left": 4},
        "Beta": {"shared": 3, "right": 2},
    })

    out = compare_shape(store, "AlphaとBetaの違いは")

    assert out["verdict"] == "COMPARISON"
    assert out["shared"] == ["shared"]
    assert out["only_a"] == ["left"]
    assert out["only_b"] == ["right"]


def test_aspect_read_selects_only_facets_from_the_answered_core():
    store = SimpleNamespace(crosses={
        "殺人罪": {"法定刑加重": 8, "刑期": 10, "一般": 9},
    })

    out = aspect_read(
        store,
        {"verdict": "ANSWER", "core": "殺人罪", "text": "殺人罪 一般 例"},
        ["刑"],
    )

    assert out["aspect"] == ["刑"]
    assert out["aspect_facets"] == ["刑期", "法定刑加重"]
    assert out["text"].split()[1] == "刑期"
    assert out["order_evidence"] == "aspect"


def test_arbitrary_path_without_an_edge_stays_unspoken():
    out = in_words(
        SimpleNamespace(),
        {"verdict": "ANSWER", "text": "CENTER LEFT", "order_evidence": "arbitrary"},
        SimpleNamespace(),
    )

    assert out["sentences"] == []
    assert out["path"] == ["CENTER", "LEFT"]


def _install_composer(monkeypatch, calls):
    composer = ModuleType("verantyx.compose_ja")
    composer.slot_boundary_ok = lambda _template: True

    def compose(_forms, subject, rest, **_kwargs):
        calls.append((subject, list(rest)))
        return []

    composer.compose = compose
    monkeypatch.setitem(sys.modules, "verantyx.compose_ja", composer)


def test_arbitrary_path_speaks_only_the_pair_named_by_an_edge(monkeypatch):
    calls = []
    _install_composer(monkeypatch, calls)
    form = SimpleNamespace(modality="none", polarity="positive", template="x")

    class Writer:
        vocab = {"CENTER", "LEFT", "RIGHT"}
        forms = {"template": form}

        @staticmethod
        def licence(_subject):
            return "unknown"

    in_words(
        SimpleNamespace(),
        {"verdict": "ANSWER", "text": "CENTER LEFT RIGHT",
         "order_evidence": "arbitrary", "edge_pairs": [("CENTER", "LEFT")]},
        Writer(),
    )

    assert calls == [("CENTER", ["LEFT"])]


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: an edge between two facets licenses speech from an unconnected center",
)
def test_unconnected_edge_defect_is_reproduced_twice(monkeypatch):
    calls = []
    _install_composer(monkeypatch, calls)
    form = SimpleNamespace(modality="none", polarity="positive", template="x")

    class Writer:
        vocab = {"CENTER", "LEFT", "RIGHT"}
        forms = {"template": form}

        @staticmethod
        def licence(_subject):
            return "unknown"

    result = {"verdict": "ANSWER", "text": "CENTER LEFT RIGHT",
              "order_evidence": "arbitrary", "edge_pairs": [("LEFT", "RIGHT")]}
    repeated = [in_words(SimpleNamespace(), result, Writer()) for _ in range(2)]

    assert calls == []
    assert all(not out["sentences"] for out in repeated)


def test_quote_composition_is_closed_to_document_verdicts():
    assert quote_in_words({"verdict": "ANSWER", "text": "Alpha Beta"}, object()) is None


def test_english_shape_does_not_parse_mixed_japanese_as_an_english_subject():
    assert en_shape("What is 殺人罪?") is None
