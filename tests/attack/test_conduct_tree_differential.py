"""Differential checks for the checkable structure and abstention contract."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from verantyx.conduct_tree import Node, build, descend


@dataclass
class _ReferenceNode:
    name: str
    children: dict[str, "_ReferenceNode | tuple[str, str]"]


def _reference_build(names: list[str], arity: int, root_name: str) -> _ReferenceNode:
    """Naively model sorted, fixed-width levels without using conduct_tree."""
    level: dict[str, _ReferenceNode | tuple[str, str]] = {
        leaf: ("leaf", leaf) for leaf in names
    }
    depth = 0
    while len(level) > arity:
        ordered = sorted(level)
        next_level: dict[str, _ReferenceNode | tuple[str, str]] = {}
        for start in range(0, len(ordered), arity):
            arms = ordered[start:start + arity]
            group_name = f"L{depth}:{arms[0]}.."
            next_level[group_name] = _ReferenceNode(
                group_name, {arm: level[arm] for arm in arms}
            )
        level = next_level
        depth += 1
    return _ReferenceNode(root_name, level)


def _assert_matches_reference(
    actual: Node,
    expected: _ReferenceNode,
    leaves: dict[str, object],
) -> None:
    assert actual.name == expected.name
    assert set(actual.children) == set(expected.children)
    for arm, expected_child in expected.children.items():
        actual_child = actual.children[arm]
        if isinstance(expected_child, _ReferenceNode):
            assert isinstance(actual_child, Node)
            _assert_matches_reference(actual_child, expected_child, leaves)
        else:
            kind, leaf_name = expected_child
            assert kind == "leaf"
            assert actual_child is leaves[leaf_name]


def _leaf(index: int) -> dict[str, dict[str, int]]:
    return {f"core_{index:03d}": {f"facet_{index:03d}": 2, "shared": 1}}


@pytest.mark.parametrize("leaf_count", [1, 2, 5, 6, 7, 12, 13, 36, 37])
def test_build_matches_independent_sorted_block_reference(leaf_count: int) -> None:
    leaves = {f"law_{index:03d}": _leaf(index) for index in range(leaf_count)}
    expected = _reference_build(list(leaves), arity=6, root_name="root")

    actual = build(leaves)

    _assert_matches_reference(actual, expected, leaves)


@pytest.mark.parametrize("arity", [2, 3, 5])
def test_build_matches_reference_at_configured_arities(arity: int) -> None:
    leaves = {f"case_{index:03d}": _leaf(index) for index in range(17)}
    expected = _reference_build(list(leaves), arity=arity, root_name="custom-root")

    actual = build(leaves, arity=arity, name="custom-root")

    _assert_matches_reference(actual, expected, leaves)


def test_build_grouping_does_not_depend_on_mapping_insertion_order() -> None:
    ordered = {f"doc_{index:03d}": _leaf(index) for index in range(25)}
    reversed_order = dict(reversed(list(ordered.items())))
    expected = _reference_build(list(ordered), arity=6, root_name="root")

    _assert_matches_reference(build(ordered), expected, ordered)
    _assert_matches_reference(build(reversed_order), expected, reversed_order)


def test_build_uses_requested_root_name_and_keeps_leaf_identity() -> None:
    leaves = {"only": _leaf(0)}

    actual = build(leaves, name="library")

    assert actual.name == "library"
    assert actual.children["only"] is leaves["only"]


def test_absent_term_abstains_at_root_as_unknown_no_route() -> None:
    leaves = {f"law_{index:03d}": _leaf(index) for index in range(13)}
    actual = build(leaves, name="corpus")

    result = descend(actual, "invented_token")

    assert result["verdict"] == "UNKNOWN_NO_ROUTE"
    assert result["stopped_at"] == "corpus"
    assert result["trail"] == []


def test_absent_term_sequence_abstains_without_changing_existing_trail() -> None:
    actual = build({"only": _leaf(0)}, name="corpus")
    prior_trail = ["already-visited"]

    result = descend(actual, ["invented_one", "invented_two"], trail=prior_trail)

    assert result["verdict"] == "UNKNOWN_NO_ROUTE"
    assert result["stopped_at"] == "corpus"
    assert result["trail"] == ["already-visited"]
    assert prior_trail == ["already-visited"]


def test_absent_anchor_sequence_is_still_a_typed_abstention() -> None:
    actual = build({"only": _leaf(0)}, name="corpus")

    result = descend(actual, ["invented"], anchor="missing_subject")

    assert result["verdict"] == "UNKNOWN_NO_ROUTE"
    assert result["stopped_at"] == "corpus"
    assert result["trail"] == []

