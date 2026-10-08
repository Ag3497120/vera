"""Differential checks for constructed unit explanations."""
from __future__ import annotations

import importlib
from types import SimpleNamespace
from typing import Any, Dict, Iterable, Optional, Sequence, Tuple

import pytest

from verantyx.explain import explain
from verantyx.granularity import SPLITS


_MARK = "（構成的説明 — 証言ではない）"


def _allowed(term: str) -> Sequence[Tuple[int, int]]:
    return SPLITS.get(len(term), ())


def _model(term: str, enabled: Iterable[Tuple[int, int]]) -> Any:
    slots: Dict[Tuple[int, str], set] = {}
    for left_size, right_size in enabled:
        left, right = term[:left_size], term[left_size:]
        slots.setdefault((left_size, "L"), set()).add(left)
        slots.setdefault((right_size, "R"), set()).add(right)
    return SimpleNamespace(slots=slots)


def _store(crosses: Optional[dict] = None, labels: Optional[set] = None) -> Any:
    return SimpleNamespace(crosses=crosses or {}, source_labels=labels or set())


def _route(monkeypatch: pytest.MonkeyPatch, result: Optional[dict] = None) -> None:
    route_module = importlib.import_module("verantyx.reach")
    answer = result or {"verdict": "UNITS"}
    monkeypatch.setattr(route_module, "reach", lambda *args, **kwargs: answer)


def _reference(
    store: Any,
    term: str,
    model: Any,
    vocab: set,
    *,
    edges: Optional[Any] = None,
    route_result: Optional[dict] = None,
) -> dict:
    """Small direct interpreter of the documented unit-explanation rules."""
    route = route_result or {"verdict": "UNITS"}
    if route["verdict"] != "UNITS":
        return route

    labels = getattr(store, "source_labels", set()) or set()
    candidates = []
    for left_size, right_size in _allowed(term):
        left, right = term[:left_size], term[left_size:]
        left_slot = model.slots.get((left_size, "L"), ())
        right_slot = model.slots.get((right_size, "R"), ())
        if left in left_slot and right in right_slot:
            candidates.append((left, right, left_size))

    def unit(part: str, position: str) -> dict:
        return {"part": part, "position": position,
                "held": part in store.crosses and part not in labels,
                "word": part in vocab}

    usable = [candidate for candidate in candidates if len(candidate[1]) > 1]
    if not usable:
        return {"verdict": "ABSTAIN_BARE_SUFFIX_SPLIT", "constructed": True,
                "term": term,
                "units": [unit(right, "R") for _, right, _ in candidates],
                "note": "every candidate split leaves a one-character "
                        "head; the judgment is the split's, not the "
                        "vocabulary gate's"}

    def rank(candidate: Tuple[str, str, int]) -> Tuple[int, int]:
        left, right, _ = candidate
        pair = (unit(right, "R"), unit(left, "L"))
        return (sum(u["held"] and u["word"] for u in pair),
                sum(u["held"] for u in pair))

    ordered = sorted(usable, key=rank, reverse=True)
    if len(ordered) > 1 and rank(ordered[0]) == rank(ordered[1]):
        return {"verdict": "ABSTAIN_SPLIT_TIED", "constructed": True,
                "term": term,
                "splits": [[left, right] for left, right, _ in ordered[:4]],
                "note": "two splits score the same; a tie broken any "
                        "other way is manufactured agreement"}

    left, right, _ = ordered[0]
    units = [unit(right, "R"), unit(left, "L")]
    spoken = [u for u in units if u["held"] and u["word"]]
    if not spoken:
        return {"verdict": "ABSTAIN_UNIT_NOT_A_WORD", "constructed": True,
                "term": term, "units": units,
                "note": "no held unit passes the vocabulary gate; an "
                        "explanation needs a subject the corpus writes "
                        "standalone"}

    common = []
    held_parts = [u["part"] for u in units if u["held"]]
    if len(held_parts) == 2:
        first = store.crosses.get(held_parts[0]) or {}
        second = store.crosses.get(held_parts[1]) or {}
        common = sorted(facet for facet in set(first) & set(second)
                        if facet not in labels)[:8]

    subject = spoken[0]["part"]
    result = {"verdict": "EXPLAINED_BY_UNITS", "constructed": True,
              "term": term, "split": [left, right], "units": units,
              "subject": subject,
              "subject_position": spoken[0]["position"],
              "crossing": common}

    if edges is not None and subject in store.crosses:
        shown = [u["part"] for u in units if u["part"] != subject] + common
        try:
            pairs = edges(subject, shown)
            if pairs:
                result["edge_pairs"] = pairs
        except Exception:
            pass

    if len(spoken) == 2:
        frame = "%sは、%sと%sに分解される。" % (term, left, right)
    else:
        frame = "%sは、%sを単位に含む。" % (term, subject)
    visible_common = [facet for facet in common if facet in vocab]
    if visible_common:
        frame += "両単位の十字が共有する面: %s。" % "、".join(
            visible_common[:4])
    result["text"] = frame + _MARK
    result["note"] = ("constructed from unit testimony; not itself attested. "
                      "every token is a held core, a held facet, or an edge "
                      "the corpus wrote")
    return result


def _call(monkeypatch: pytest.MonkeyPatch, store: Any, term: str,
          model: Any, vocab: set, **kwargs: Any) -> dict:
    _route(monkeypatch, kwargs.pop("route_result", None))
    return explain(store, term, model=model, vocab=vocab, **kwargs)


def test_generated_cases_match_independent_reference(monkeypatch):
    """Generated slot/store/vocabulary combinations follow the reference."""
    terms = ("あいう", "あいうえ", "あいうえお")
    checked = 0
    for term in terms:
        candidates = _allowed(term)
        for enabled_mask in range(1 << len(candidates)):
            enabled = [pair for bit, pair in enumerate(candidates)
                       if enabled_mask & (1 << bit)]
            model = _model(term, enabled)
            parts = sorted({term[:a] for a, _ in enabled} |
                           {term[a:] for a, _ in enabled})
            for state in range(3):
                crosses = {}
                vocab = set()
                for index, part in enumerate(parts):
                    if (enabled_mask + index + state) % 3 != 0:
                        crosses[part] = {"shared-a": 1, "shared-b": 1}
                    if (enabled_mask + index + state) % 2 == 0:
                        vocab.add(part)
                store = _store(crosses, {"shared-b"} if state == 2 else set())
                expected = _reference(store, term, model, vocab)
                observed = _call(monkeypatch, store, term, model, vocab)
                assert observed == expected
                checked += 1
    assert checked > 0


def test_one_character_right_unit_abstains_as_bare_suffix(monkeypatch):
    term = "電荷"
    right = term[1:]
    store = _store({right: {}})
    model = _model(term, _allowed(term))
    actual = _call(monkeypatch, store, term, model, {right})
    assert actual == _reference(store, term, model, {right})
    assert actual["verdict"] == "ABSTAIN_BARE_SUFFIX_SPLIT"


def test_equal_best_splits_abstain_instead_of_breaking_tie(monkeypatch):
    term = "あいうえ"
    enabled = ((2, 2), (1, 3))
    parts = {term[:a] for a, _ in enabled} | {term[a:] for a, _ in enabled}
    store = _store({part: {} for part in parts})
    model = _model(term, enabled)
    actual = _call(monkeypatch, store, term, model, parts)
    assert actual == _reference(store, term, model, parts)
    assert actual["verdict"] == "ABSTAIN_SPLIT_TIED"


def test_held_units_without_words_abstain(monkeypatch):
    term = "あいう"
    store = _store({"あ": {}, "いう": {}})
    model = _model(term, ((1, 2),))
    actual = _call(monkeypatch, store, term, model, set())
    assert actual == _reference(store, term, model, set())
    assert actual["verdict"] == "ABSTAIN_UNIT_NOT_A_WORD"


def test_word_gate_score_beats_a_candidate_with_more_held_units(monkeypatch):
    term = "あいうえ"
    enabled = ((2, 2), (1, 3))
    store = _store({"うえ": {}, "あ": {}, "いうえ": {}})
    model = _model(term, enabled)
    actual = _call(monkeypatch, store, term, model, {"うえ"})
    assert actual == _reference(store, term, model, {"うえ"})
    assert actual["verdict"] == "EXPLAINED_BY_UNITS"
    assert actual["split"] == ["あい", "うえ"]
    assert actual["subject"] == "うえ"


def test_crossing_is_sorted_capped_and_vocabulary_gated_in_text(monkeypatch):
    term = "あいうえ"
    left, right = "あい", "うえ"
    facets = {"facet-%02d" % index for index in range(10)}
    vocab = {left, right, "facet-00", "facet-03", "facet-04", "facet-09"}
    store = _store({left: dict.fromkeys(facets), right: dict.fromkeys(facets)},
                   {"facet-02"})
    model = _model(term, ((2, 2),))
    actual = _call(monkeypatch, store, term, model, vocab)
    assert actual == _reference(store, term, model, vocab)
    assert actual["crossing"] == ["facet-00", "facet-01", "facet-03",
                                  "facet-04", "facet-05", "facet-06",
                                  "facet-07", "facet-08"]
    assert "facet-02" not in actual["text"]
    assert "facet-00、facet-03、facet-04、facet-09" not in actual["text"]


def test_one_spoken_unit_uses_containment_frame_and_right_subject(monkeypatch):
    term = "あいうえ"
    store = _store({"うえ": {}, "あい": {}})
    model = _model(term, ((2, 2),))
    actual = _call(monkeypatch, store, term, model, {"うえ"})
    assert actual == _reference(store, term, model, {"うえ"})
    assert actual["subject_position"] == "R"
    assert actual["text"].startswith("あいうえは、うえを単位に含む。")
    assert actual["text"].endswith(_MARK)


def test_edge_pairs_are_attached_from_the_optional_lookup(monkeypatch):
    term = "あいうえ"
    store = _store({"あい": {"shared": 1}, "うえ": {"shared": 1}})
    model = _model(term, ((2, 2),))
    seen = []

    def lookup(subject, shown):
        seen.append((subject, shown))
        return [(subject, shown[0])]

    actual = _call(monkeypatch, store, term, model, {"あい", "うえ"},
                   edges=lookup)
    assert actual == _reference(store, term, model, {"あい", "うえ"},
                                edges=lookup)
    assert actual["edge_pairs"] == [("うえ", "あい")]
    assert seen[0] == ("うえ", ["あい", "shared"])


def test_edge_lookup_errors_are_ignored(monkeypatch):
    term = "あいうえ"
    store = _store({"あい": {}, "うえ": {}})
    model = _model(term, ((2, 2),))

    def broken_lookup(subject, shown):
        raise RuntimeError("unavailable")

    actual = _call(monkeypatch, store, term, model, {"あい", "うえ"},
                   edges=broken_lookup)
    assert actual == _reference(store, term, model, {"あい", "うえ"},
                                edges=broken_lookup)
    assert "edge_pairs" not in actual


def test_non_units_route_result_is_passed_through(monkeypatch):
    term = "対象語"
    route = {"verdict": "CONTAINMENT", "term": term, "container": "上位語"}
    actual = _call(monkeypatch, _store(), term, _model(term, ()), set(),
                   route_result=route)
    assert actual is route
