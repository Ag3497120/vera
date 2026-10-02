"""Differential checks for the lattice's documented, checkable cases."""
from __future__ import annotations

import random
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Set, Tuple

import pytest

from verantyx import lattice as sut


@dataclass
class RefLattice:
    words: Set[str]
    up: Dict[Tuple[str, str], Set[str]]
    atoms: Set[str]


def _ref_positions(n: int) -> Tuple[int, ...]:
    # The documented two-character atom split and the long-window rule.
    if n == 2:
        return (1,)
    if 6 <= n <= 12:
        return tuple(range(2, n - 1))
    return ()


def ref_build(vocabulary: Iterable[str]) -> RefLattice:
    """Small independent builder for pairs and licensed long-word cuts."""
    words = {word for word in vocabulary if 2 <= len(word) <= 12}
    up: Dict[Tuple[str, str], Set[str]] = {}
    for word in words:
        n = len(word)
        for cut in _ref_positions(n):
            left, right = word[:cut], word[cut:]
            if n >= 6 and (left not in words or right not in words):
                continue
            for unit, position in ((left, "L"), (right, "R")):
                # Nodes are attested words or atoms observed in attested words.
                if len(unit) > 1 and unit not in words:
                    continue
                up.setdefault((unit, position), set()).add(word)
    atoms = {unit for unit, _position in up if len(unit) == 1}
    return RefLattice(words, up, atoms)


def ref_splits(lat: RefLattice, term: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for cut in _ref_positions(len(term)):
        left, right = term[:cut], term[cut:]
        if len(term) >= 6:
            valid = left in lat.words and right in lat.words
        else:
            valid = ((left in lat.words or left in lat.atoms)
                     and (right in lat.words or right in lat.atoms))
        if valid:
            out.append((left, right))
    return out


def ref_analyze(lat: RefLattice, term: str, depth: int = 3) -> Dict[str, Any]:
    node: Dict[str, Any] = {
        "term": term,
        "word": term in lat.words,
        "atom": term in lat.atoms,
    }
    if depth <= 0 or len(term) < 2:
        return node
    branches = [
        {"left": ref_analyze(lat, left, depth - 1),
         "right": ref_analyze(lat, right, depth - 1)}
        for left, right in ref_splits(lat, term)
    ]
    if branches:
        node["splits"] = branches
    return node


def ref_kin(lat: RefLattice, term: str, min_unit: int = 1,
            limit: int = 12) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for cut in _ref_positions(len(term)):
        for unit, position in ((term[:cut], "L"), (term[cut:], "R")):
            if len(unit) < min_unit:
                continue
            others = sorted(lat.up.get((unit, position), set()) - {term})
            if others:
                out["%s@%s" % (unit, position)] = others[:limit]
    return out


def ref_predict_facets(lat: RefLattice, store: Any, term: str,
                       min_unit: int = 1, top: int = 20) -> List[str]:
    labels = getattr(store, "source_labels", set()) or set()
    weights: Dict[str, int] = {}
    for family in ref_kin(lat, term, min_unit=min_unit).values():
        for word in family:
            for facet, count in (store.crosses.get(word) or {}).items():
                if facet in labels or facet == term:
                    continue
                weights[facet] = weights.get(facet, 0) + count
    ranked = sorted(weights.items(), key=lambda item: (-item[1], item[0]))
    return [facet for facet, _count in ranked[:top]]


def _generated_vocabularies() -> List[Set[str]]:
    rng = random.Random(20261002)
    pairs = ["aa", "ab", "ac", "ba", "bb", "bc", "ca", "cb"]
    cases: List[Set[str]] = []
    for _ in range(24):
        chosen = rng.sample(pairs, 5)
        inner = "".join(rng.sample(chosen, 3))
        outer = rng.choice(chosen) + inner
        cases.append(set(chosen) | {inner, outer})
    return cases


def test_generated_cases_match_naive_reference() -> None:
    for vocabulary in _generated_vocabularies():
        expected = ref_build(vocabulary)
        actual = sut.build(vocabulary)
        assert actual.words == expected.words
        assert actual.up == expected.up
        assert actual.atoms == expected.atoms
        for term in vocabulary:
            assert sut.splits_of(actual, term) == ref_splits(expected, term)
            assert sut.analyze(actual, term, depth=2) == ref_analyze(expected, term, 2)
            assert sut.kin(actual, term) == ref_kin(expected, term)


def test_pair_build_reports_words_slots_and_distinct_atoms() -> None:
    lat = sut.build(["ab", "bc"])
    assert lat.report() == {"words": 2, "slots": 4, "atoms": 3}


def test_pair_splits_require_both_halves_to_be_nodes() -> None:
    lat = sut.build(["ab"])
    assert sut.splits_of(lat, "ab") == [("a", "b")]
    assert sut.splits_of(lat, "xy") == []


def test_pair_analysis_recurses_to_observed_atoms() -> None:
    lat = sut.build(["ab"])
    assert sut.analyze(lat, "ab", depth=1) == {
        "term": "ab", "word": True, "atom": False,
        "splits": [{
            "left": {"term": "a", "word": False, "atom": True},
            "right": {"term": "b", "word": False, "atom": True},
        }],
    }


def test_analysis_depth_zero_returns_only_the_node() -> None:
    lat = sut.build(["ab"])
    assert sut.analyze(lat, "ab", depth=0) == {
        "term": "ab", "word": True, "atom": False,
    }


def test_kin_keeps_left_and_right_positions_separate() -> None:
    lat = sut.build(["ab", "ac", "xb", "xc"])
    assert sut.kin(lat, "ab") == {"a@L": ["ac"], "b@R": ["xb"]}


def test_kin_uses_sorted_limit_and_can_drop_atomic_units() -> None:
    lat = sut.build(["ab", "az", "ay", "ax"])
    assert sut.kin(lat, "ab", limit=2) == {"a@L": ["ax", "ay"]}
    assert sut.kin(lat, "ab", min_unit=2) == {}


def test_long_split_requires_two_attested_word_halves() -> None:
    vocabulary = {"ab", "cdefgh", "abcdefgh"}
    expected = ref_build(vocabulary)
    actual = sut.build(vocabulary)
    assert actual.up == expected.up
    assert sut.splits_of(actual, "abcdefgh") == [("ab", "cdefgh")]
    assert sut.splits_of(actual, "abcdefg") == []


def test_long_kin_uses_positional_slots() -> None:
    vocabulary = {"ab", "cdefgh", "ijklmn", "abcdefgh", "abijklmn"}
    expected = ref_build(vocabulary)
    actual = sut.build(vocabulary)
    assert sut.kin(actual, "abcdefgh") == ref_kin(expected, "abcdefgh")
    assert sut.kin(actual, "abcdefgh") == {"ab@L": ["abijklmn"]}


def test_predictions_sum_family_counts_and_filter_source_and_term() -> None:
    vocabulary = {"ab", "ac", "ad", "xb"}
    expected = ref_build(vocabulary)
    actual = sut.build(vocabulary)
    store = SimpleNamespace(
        source_labels={"source"},
        crosses={
            "ac": {"noise": 9, "topic": 2, "source": 100, "ab": 11},
            "ad": {"topic": 3, "other": 1},
            "xb": {"other": 5, "topic": 1},
        },
    )
    assert sut.predict_facets(actual, store, "ab", top=2) == ref_predict_facets(
        expected, store, "ab", top=2)
    assert sut.predict_facets(actual, store, "ab", top=2) == ["noise", "other"]


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: short-word indexing admits unattested fragments as kin units",
)
def test_short_words_do_not_index_unattested_fragments() -> None:
    lat = sut.build(["abc"])
    assert all(len(unit) == 1 or unit in lat.words for unit, _position in lat.up)
