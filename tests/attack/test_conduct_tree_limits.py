"""Limit and determinism attacks for the conduct tree."""

from __future__ import annotations

import gc
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from weakref import ref

import pytest

from verantyx.conduct_tree import ARITY, Node, build, descend


def _leaves(count: int) -> dict[str, dict[str, dict[str, int]]]:
    return {
        f"law-{i:03d}": {
            f"core-{i:03d}": {f"face-{i:03d}": 1, "shared-face": 1}
        }
        for i in range(count)
    }


def _tree_shape(node: Node) -> tuple[int, int]:
    """Return leaf count and maximum node fan-out below this node."""
    leaves = 0
    max_fanout = len(node.children)
    for child in node.children.values():
        if isinstance(child, Node):
            child_leaves, child_fanout = _tree_shape(child)
            leaves += child_leaves
            max_fanout = max(max_fanout, child_fanout)
        else:
            leaves += 1
    return leaves, max_fanout


def test_empty_tree_builds_and_abstains_with_a_typed_result():
    tree = build({})

    assert tree.name == "root"
    assert tree.children == {}
    assert descend(tree, "invented") == {
        "verdict": "UNKNOWN_NO_ROUTE",
        "stopped_at": "root",
        "trail": [],
        "note": "no arm's faces are reachable from this term's "
        "surface, or two arms tied; descending further would be a guess",
    }


def test_default_builder_keeps_every_node_within_six_arms():
    leaves = _leaves(37)
    tree = build(leaves)

    count, max_fanout = _tree_shape(tree)
    assert count == len(leaves)
    assert max_fanout <= ARITY == 6


def test_sorted_grouping_is_independent_of_input_insertion_order():
    leaves = _leaves(19)

    forward = build(leaves)
    reversed_order = build(dict(reversed(list(leaves.items()))))

    assert forward == reversed_order


def test_rebuilding_the_same_leaves_is_idempotent():
    leaves = _leaves(13)

    first = build(leaves)
    second = build(leaves)

    assert first == second


def test_build_does_not_change_leaf_crosses():
    leaves = _leaves(8)
    original = deepcopy(leaves)

    build(leaves)

    assert leaves == original


def test_unknown_term_abstains_at_the_root_without_changing_the_tree():
    tree = build(_leaves(7))
    original = deepcopy(tree)

    result = descend(tree, "term-absent-from-all-crosses")

    assert result["verdict"] == "UNKNOWN_NO_ROUTE"
    assert result["stopped_at"] == "root"
    assert result["trail"] == []
    assert tree == original


def test_repeated_descent_returns_the_same_result_and_does_not_retain_trail():
    tree = build(_leaves(7))
    original = deepcopy(tree)
    supplied_trail = ["caller-prefix"]

    first = descend(tree, "term-absent-from-all-crosses", trail=supplied_trail)
    second = descend(tree, "term-absent-from-all-crosses", trail=supplied_trail)

    assert first == second
    assert first["trail"] == ["caller-prefix"]
    assert supplied_trail == ["caller-prefix"]
    assert tree == original


def test_two_concurrent_readers_keep_results_and_trails_independent():
    tree = build(_leaves(7))
    inputs = [("missing-a", ["reader-a"]), ("missing-b", ["reader-b"])]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda item: descend(tree, item[0], trail=item[1]), inputs))

    assert [result["verdict"] for result in results] == [
        "UNKNOWN_NO_ROUTE",
        "UNKNOWN_NO_ROUTE",
    ]
    assert [result["trail"] for result in results] == [["reader-a"], ["reader-b"]]
    assert [trail for _, trail in inputs] == [["reader-a"], ["reader-b"]]


def test_built_tree_can_be_collected_after_a_large_bounded_build():
    tree_ref = ref(build(_leaves(216)))

    gc.collect()

    assert tree_ref() is None


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: arity=1 keeps nesting the same leaves until _merged_view recurses",
)
def test_arity_one_is_rejected_or_terminates_without_recursive_crash():
    code = (
        "from verantyx.conduct_tree import build\n"
        "try:\n"
        "    build({'a': {}, 'b': {}}, arity=1)\n"
        "except ValueError:\n"
        "    pass\n"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-B", "-c", code],
            env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[2])},
            cwd=str(Path(__file__).resolve().parents[2]),
            capture_output=True,
            text=True,
            timeout=1.0,
            check=False,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("build({'a': {}, 'b': {}}, arity=1) exceeded 1 second")

    assert result.returncode == 0, result.stderr
