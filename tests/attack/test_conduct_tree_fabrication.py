"""Independent fabrication and provenance attacks for the conduction tree."""

from types import SimpleNamespace

import pytest

from verantyx import conduct_tree


def test_leaf_route_returns_the_selected_leaf_identity(monkeypatch):
    leaf_store = {"core": {"face": 1}}
    node = conduct_tree.Node(
        name="root",
        children={"sovereign": leaf_store},
        faces={"sovereign": ["face"]},
        profile={"sovereign": leaf_store},
        leaf_names={"sovereign": "document"},
    )
    monkeypatch.setattr(conduct_tree.surface, "route", lambda *args: "sovereign")

    result = conduct_tree.descend(node, "face")

    assert result == {"verdict": "ROUTED", "leaf": "document", "trail": ["sovereign"]}


def test_tied_or_unreachable_route_abstains_at_the_current_node(monkeypatch):
    node = conduct_tree.Node(name="root", children={"a": {}}, profile={"a": {}}, faces={"a": []})
    monkeypatch.setattr(conduct_tree.surface, "route", lambda *args: None)

    result = conduct_tree.descend(node, "unknown")

    assert result["verdict"] == "UNKNOWN_NO_ROUTE"
    assert result["stopped_at"] == "root"
    assert result["trail"] == []


def test_term_sequence_is_passed_to_router_without_reordering(monkeypatch):
    seen = []
    node = conduct_tree.Node(name="root", children={"doc": {}}, profile={"doc": {}}, faces={"doc": []})

    def choose(profile, faces, term):
        seen.append(term)
        return "doc"

    monkeypatch.setattr(conduct_tree.surface, "route", choose)
    terms = ["not", "same-order"]

    result = conduct_tree.descend(node, terms)

    assert seen == [terms]
    assert result["leaf"] == "doc"


def test_caller_trail_is_copied_before_descent(monkeypatch):
    node = conduct_tree.Node(name="root", children={"doc": {}}, profile={"doc": {}}, faces={"doc": []})
    monkeypatch.setattr(conduct_tree.surface, "route", lambda *args: "doc")
    prior = ["earlier"]

    result = conduct_tree.descend(node, "term", trail=prior)

    assert result["trail"] == ["earlier", "doc"]
    assert prior == ["earlier"]


def test_anchor_miss_abstains_before_recording_the_selected_arm(monkeypatch):
    view = SimpleNamespace(surface_mass=lambda word: 0)
    node = conduct_tree.Node(name="root", children={"doc": {}}, profile={"doc": view}, faces={"doc": []})
    monkeypatch.setattr(conduct_tree.surface, "route", lambda *args: "doc")

    result = conduct_tree.descend(node, "term", anchor="subject")

    assert result["verdict"] == "UNKNOWN_NO_ROUTE"
    assert result["stopped_at"] == "root"
    assert result["trail"] == []
    assert result["anchor"] == "subject"


def test_anchor_present_in_selected_arm_allows_descent(monkeypatch):
    view = SimpleNamespace(surface_mass=lambda word: 2 if word == "subject" else 0)
    node = conduct_tree.Node(name="root", children={"doc": {}}, profile={"doc": view}, faces={"doc": []})
    monkeypatch.setattr(conduct_tree.surface, "route", lambda *args: "doc")

    result = conduct_tree.descend(node, "term", anchor="subject")

    assert result["verdict"] == "ROUTED"
    assert result["leaf"] == "doc"


def test_multilevel_descent_records_each_arm_and_final_document(monkeypatch):
    branch = conduct_tree.Node(
        name="branch",
        children={"document-arm": {"core": {"face": 1}}},
        profile={"document-arm": {}},
        faces={"document-arm": []},
        leaf_names={"document-arm": "document-id"},
    )
    root = conduct_tree.Node(
        name="root",
        children={"group-arm": branch},
        profile={"group-arm": {}},
        faces={"group-arm": []},
    )

    def choose(profile, faces, term):
        return "group-arm" if "group-arm" in profile else "document-arm"

    monkeypatch.setattr(conduct_tree.surface, "route", choose)

    result = conduct_tree.descend(root, "term")

    assert result == {
        "verdict": "ROUTED",
        "leaf": "document-id",
        "trail": ["group-arm", "document-arm"],
    }


def test_is_leaf_arm_distinguishes_node_from_leaf_store():
    child_node = conduct_tree.Node(name="branch")
    node = conduct_tree.Node(name="root", children={"branch": child_node, "leaf": {}})

    assert node.is_leaf_arm("branch") is False
    assert node.is_leaf_arm("leaf") is True


def test_build_keeps_leaf_stores_separate(monkeypatch):
    leaves = {
        "a": {"core-a": {"face-a": 1}},
        "b": {"core-b": {"face-b": 2}},
    }
    monkeypatch.setattr(
        conduct_tree,
        "distinct_faces",
        lambda profiles: {arm: [f"face-{arm}"] for arm in profiles},
    )

    root = conduct_tree.build(leaves)

    assert root.children["a"] is leaves["a"]
    assert root.children["b"] is leaves["b"]
    assert root.profile["a"] is not root.profile["b"]


def test_build_routes_through_groups_without_changing_leaf_identity(monkeypatch):
    leaves = {letter: {f"core-{letter}": {f"face-{letter}": 1}} for letter in "abcdefg"}
    monkeypatch.setattr(
        conduct_tree,
        "distinct_faces",
        lambda profiles: {arm: [f"face-{arm}"] for arm in profiles},
    )
    root = conduct_tree.build(leaves)

    def choose(profile, faces, term):
        if "L0:a.." in profile:
            return "L0:a.."
        return "a"

    monkeypatch.setattr(conduct_tree.surface, "route", choose)

    result = conduct_tree.descend(root, "face-a")

    assert result == {"verdict": "ROUTED", "leaf": "a", "trail": ["L0:a..", "a"]}
    assert root.children["L0:a.."].children["a"] is leaves["a"]


def test_federated_build_preserves_document_name_under_sovereign_arm(monkeypatch):
    leaf = SimpleNamespace(name="document-id", is_leaf=True)
    hierarchy = SimpleNamespace(
        name="root",
        is_leaf=False,
        children={"sovereign-arm": leaf},
    )
    leaves = {"document-id": {"core": {"face": 1}}}
    monkeypatch.setattr(
        conduct_tree,
        "distinct_faces",
        lambda profiles: {arm: ["face"] for arm in profiles},
    )
    monkeypatch.setattr(conduct_tree.surface, "route", lambda *args: "sovereign-arm")

    root = conduct_tree.build(leaves, hierarchy=hierarchy)
    result = conduct_tree.descend(root, "face")

    assert result == {"verdict": "ROUTED", "leaf": "document-id", "trail": ["sovereign-arm"]}


@pytest.mark.parametrize("anchor", ["missing", "different-subject"])
@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: dict-backed profiles skip anchor membership checks",
)
def test_dict_backed_profile_does_not_route_when_anchor_is_absent(monkeypatch, anchor):
    leaf_store = {"core": {"face": 1}}
    node = conduct_tree.Node(
        name="root",
        children={"unrelated-document": leaf_store},
        profile={"unrelated-document": leaf_store},
        faces={"unrelated-document": ["face"]},
    )
    monkeypatch.setattr(conduct_tree.surface, "route", lambda *args: "unrelated-document")

    result = conduct_tree.descend(node, "face", anchor=anchor)

    assert result["verdict"] == "UNKNOWN_NO_ROUTE"
