"""Independent contract checks for n-path differential summaries."""

from __future__ import annotations

import random
from collections import defaultdict
from types import SimpleNamespace

import pytest

from verantyx.summarize import summarize


def make_store(crosses, source_labels=()):
    return SimpleNamespace(crosses=crosses, source_labels=set(source_labels))


def reference_summarize(store, subjects, *, vocab, edges, limit=5):
    """Small set-oriented reading of summarize.py's documented contract."""
    labels = set(getattr(store, "source_labels", ()) or ())
    held = [s for s in subjects if s in store.crosses and s not in labels]
    dropped = [s for s in subjects if s not in held]
    speakable = [s for s in held if s in vocab]

    if len(held) < 2:
        return {
            "verdict": "UNKNOWN_TOO_FEW_PATHS",
            "held": held,
            "dropped_subjects": dropped,
            "note": "a crossing needs at least two held subjects",
        }

    holders = defaultdict(set)
    held_names = set(held)
    for subject in held:
        for facet in store.crosses.get(subject, ()):
            if facet not in labels and facet not in held_names:
                holders[facet].add(subject)
    crossing = {facet: paths for facet, paths in holders.items()
                if len(paths) >= 2}
    if not crossing:
        return {
            "verdict": "UNKNOWN_NO_CROSSING",
            "held": held,
            "dropped_subjects": dropped,
            "note": "no facet is shared by two subjects; these paths do not meet in this store",
        }
    if edges is None:
        return {
            "verdict": "UNKNOWN_NO_EDGE_LICENSE",
            "held": held,
            "crossing": len(crossing),
            "note": "no edge lookup supplied; co-presence is not a licence to claim a relation",
        }

    claims = []
    for subject in speakable:
        held_facets = set(store.crosses.get(subject, ()))
        allowed = {facet for facet in crossing
                   if facet in held_facets and facet in vocab}
        if len(allowed) < 2:
            continue
        try:
            licensed_pairs = edges(subject, sorted(allowed)) or ()
        except Exception:
            licensed_pairs = ()
        counts = store.crosses.get(subject, {})
        for left, right in licensed_pairs:
            claims.append({
                "subject": subject,
                "pair": [left, right],
                "width": len(crossing.get(left, ())) + len(crossing.get(right, ())),
                "mass": (counts.get(left) or 0) + (counts.get(right) or 0),
            })

    if not claims:
        return {
            "verdict": "UNKNOWN_NO_EDGE_LICENSE",
            "held": held,
            "crossing": len(crossing),
            "note": "the crossing exists but no sentence in the corpus wrote any shared pair together; silence, not invention",
        }

    by_rank = defaultdict(list)
    for claim in claims:
        by_rank[(claim["width"], claim["mass"])].append(claim)
    kept = []
    cut = []
    for rank in sorted(by_rank, reverse=True):
        group = sorted(by_rank[rank], key=lambda c: (c["subject"], c["pair"]))
        if cut or len(kept) + len(group) > limit:
            cut.extend(group)
        else:
            kept.extend(group)

    sentences = ["%s: %s と %s（同一文）" % (c["subject"], c["pair"][0], c["pair"][1])
                 for c in kept]
    return {
        "verdict": "SUMMARY",
        "held": held,
        "dropped_subjects": dropped,
        "unspoken_subjects": [s for s in held if s not in vocab],
        "crossing": len(crossing),
        "licensed": len(claims),
        "kept": kept,
        "dropped_at_cut": len(cut),
        "ranked_by": "crossing width, then subject mass; drops are whole rank groups",
        "text": "。".join(sentences) + ("。" if sentences else ""),
        "note": "each claim is recountable from the edges sidecar; the selection is this module's and says so",
    }


def test_too_few_held_paths_refuses_and_reports_dropped_subjects():
    store = make_store({"A": {"f1": 2, "f2": 1}, "Label": {"f1": 8}}, {"Label"})
    result = summarize(store, ["A", "missing", "Label"], vocab={"A", "f1", "f2"}, edges=lambda *_: [("f1", "f2")])
    assert result == {
        "verdict": "UNKNOWN_TOO_FEW_PATHS",
        "held": ["A"],
        "dropped_subjects": ["missing", "Label"],
        "note": "a crossing needs at least two held subjects",
    }


def test_disjoint_paths_return_no_crossing():
    store = make_store({"A": {"left": 1}, "B": {"right": 1}})
    result = summarize(store, ["A", "B"], vocab={"A", "B", "left", "right"}, edges=lambda *_: [])
    assert result["verdict"] == "UNKNOWN_NO_CROSSING"
    assert result["held"] == ["A", "B"]


def test_source_labels_and_subject_names_are_not_counted_as_facets():
    store = make_store(
        {"A": {"A": 9, "shared": 2, "origin": 7},
         "B": {"A": 8, "shared": 3, "origin": 6}},
        {"origin"},
    )
    result = summarize(store, ["A", "B"], vocab={"A", "B", "shared", "origin"}, edges=lambda *_: [])
    assert result["verdict"] == "UNKNOWN_NO_EDGE_LICENSE"
    assert result["crossing"] == 1


def test_co_presence_without_an_edge_never_becomes_a_claim():
    store = make_store({"A": {"f1": 2, "f2": 3}, "B": {"f1": 1, "f2": 4}})
    result = summarize(store, ["A", "B"], vocab={"A", "B", "f1", "f2"}, edges=lambda *_: [])
    assert result["verdict"] == "UNKNOWN_NO_EDGE_LICENSE"
    assert result["crossing"] == 2
    assert "kept" not in result


def test_subject_and_facet_vocabulary_gates_apply_to_claims():
    store = make_store({"A": {"f1": 2, "f2": 2}, "B": {"f1": 3, "f2": 3}})
    licensed = {"A": [("f1", "f2")], "B": [("f1", "f2")]}

    def edges(subject, facets):
        allowed = set(facets)
        return [pair for pair in licensed[subject] if set(pair) <= allowed]

    subject_gated = summarize(store, ["A", "B"], vocab={"A", "f1", "f2"}, edges=edges)
    assert subject_gated["verdict"] == "SUMMARY"
    assert [c["subject"] for c in subject_gated["kept"]] == ["A"]
    assert subject_gated["unspoken_subjects"] == ["B"]

    facet_gated = summarize(store, ["A", "B"], vocab={"A", "B", "f1"}, edges=edges)
    assert facet_gated["verdict"] == "UNKNOWN_NO_EDGE_LICENSE"


def test_equal_rank_boundary_drops_the_whole_group_and_everything_below():
    store = make_store({
        "A": {"f1": 1, "f2": 1, "f3": 1, "f4": 1},
        "B": {"f1": 1, "f2": 1, "f3": 1, "f4": 1},
        "C": {"f1": 1, "f2": 1},
    })
    pair_map = {"A": [("f1", "f2"), ("f3", "f4")], "B": [("f1", "f2")], "C": []}

    def edges(subject, facets):
        allowed = set(facets)
        return [pair for pair in pair_map[subject] if set(pair) <= allowed]

    result = summarize(store, ["A", "B", "C"], vocab={"A", "B", "C", "f1", "f2", "f3", "f4"}, edges=edges, limit=1)
    assert result["verdict"] == "SUMMARY"
    assert result["licensed"] == 3
    assert result["kept"] == []
    assert result["dropped_at_cut"] == 3


def test_ties_are_sorted_by_subject_inside_the_rank_group():
    store = make_store({"B": {"f1": 1, "f2": 1}, "A": {"f1": 1, "f2": 1}})
    edge_map = {"A": [("f1", "f2")], "B": [("f1", "f2")]}
    result = summarize(store, ["B", "A"], vocab={"A", "B", "f1", "f2"}, edges=lambda s, _: edge_map[s])
    assert [(c["subject"], c["pair"]) for c in result["kept"]] == [
        ("A", ["f1", "f2"]), ("B", ["f1", "f2"]),
    ]


def test_edge_lookup_exception_is_treated_as_no_license():
    store = make_store({"A": {"f1": 1, "f2": 1}, "B": {"f1": 1, "f2": 1}})

    def broken_lookup(*_):
        raise RuntimeError("sidecar unavailable")

    result = summarize(store, ["A", "B"], vocab={"A", "B", "f1", "f2"}, edges=broken_lookup)
    assert result["verdict"] == "UNKNOWN_NO_EDGE_LICENSE"
    assert result["crossing"] == 2


def test_generated_unique_cases_match_independent_reference():
    rng = random.Random(731)
    for _ in range(50):
        names = ["s%d" % i for i in range(rng.randint(2, 5))]
        facets = ["f%d" % i for i in range(rng.randint(2, 6))]
        crosses = {}
        for subject in names:
            chosen = rng.sample(facets, rng.randint(0, len(facets)))
            crosses[subject] = {facet: rng.randint(1, 5) for facet in chosen}
        labels = {"source"} if rng.random() < 0.3 else set()
        store = make_store(crosses, labels)
        available = names + (["absent"] if rng.random() < 0.4 else [])
        vocab = {word for word in names + facets if rng.random() < 0.75}
        edge_map = {}
        for subject in names:
            present = list(crosses[subject])
            edge_map[subject] = [pair for pair in __import__("itertools").combinations(present, 2)
                                 if rng.random() < 0.45]

        def lookup(subject, allowed):
            allow = set(allowed)
            return [pair for pair in edge_map[subject] if set(pair) <= allow]

        limit = rng.randint(0, 5)
        expected = reference_summarize(store, available, vocab=vocab, edges=lookup, limit=limit)
        actual = summarize(store, available, vocab=vocab, edges=lookup, limit=limit)
        assert actual == expected


@pytest.mark.xfail(strict=False, reason="DEFECT: duplicate subject IDs are counted as separate paths")
def test_duplicate_subject_id_does_not_create_a_second_path():
    store = make_store({"A": {"f1": 1, "f2": 1}})
    result = summarize(store, ["A", "A"], vocab={"A", "f1", "f2"}, edges=lambda *_: [("f1", "f2")])
    assert result["verdict"] == "UNKNOWN_TOO_FEW_PATHS"
