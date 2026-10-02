from concurrent.futures import ThreadPoolExecutor

import pytest

from verantyx.gap_graph import GapGraph, refusal_to_gap


def test_empty_graph_has_no_actionable_or_recent_nodes():
    graph = GapGraph()

    assert graph.actionable() == []
    assert graph.since(0) == []


def test_create_reuses_exact_scope_and_subject_without_replacing_first_node():
    graph = GapGraph()
    first = graph.create(
        "unresolved_refusal", "where is the station", "agent_refusal", "QUALITY",
        acquisition_methods=["branch-a"],
    )
    again = graph.create(
        "other_type", "where is the station", "agent_refusal", "OPTIONAL",
        acquisition_methods=["branch-b"],
    )

    assert again is first
    assert len(graph.nodes) == 1
    assert first.gap_type == "unresolved_refusal"
    assert first.severity == "QUALITY"
    assert first.acquisition_methods == ["branch-a"]


def test_create_keeps_equal_subjects_in_different_scopes_separate():
    graph = GapGraph()
    query_gap = graph.create("missing", "index", "query:index", "QUALITY")
    file_gap = graph.create("missing", "index", "file:index", "QUALITY")

    assert query_gap.gap_id != file_gap.gap_id
    assert len(graph.nodes) == 2


@pytest.mark.parametrize("severity", ["", "quality", "UNKNOWN"])
def test_create_rejects_unknown_severity(severity):
    with pytest.raises(ValueError):
        GapGraph().create("missing", "x", "query:x", severity)


@pytest.mark.parametrize("status", ["", "resolved", "UNKNOWN"])
def test_create_rejects_unknown_status(status):
    with pytest.raises(ValueError):
        GapGraph().create("missing", "x", "query:x", "QUALITY", status=status)


def test_actionable_is_oldest_first_and_honors_positive_limit():
    graph = GapGraph()
    newest = graph.create("missing", "newest", "query:newest", "QUALITY")
    oldest = graph.create("missing", "oldest", "query:oldest", "QUALITY")
    middle = graph.create("missing", "middle", "query:middle", "QUALITY")
    newest.created_at, middle.created_at, oldest.created_at = 30, 20, 10
    graph.set_status(middle.gap_id, "VERIFIED")

    assert [node.gap_id for node in graph.actionable()] == [oldest.gap_id, newest.gap_id]
    assert [node.gap_id for node in graph.actionable(limit=1)] == [oldest.gap_id]


@pytest.mark.xfail(strict=False, reason="DEFECT: actionable(limit=0) returns every actionable node")
def test_actionable_zero_limit_returns_no_nodes():
    graph = GapGraph()
    graph.create("missing", "x", "query:x", "QUALITY")

    assert graph.actionable(limit=0) == []


def test_actionable_reads_do_not_mutate_nodes():
    graph = GapGraph()
    graph.create("missing", "a", "query:a", "QUALITY")
    graph.create("missing", "b", "query:b", "OPTIONAL")
    before = {gap_id: node.as_dict() for gap_id, node in graph.nodes.items()}

    for _ in range(5):
        graph.actionable()

    assert {gap_id: node.as_dict() for gap_id, node in graph.nodes.items()} == before


def test_since_includes_the_boundary_timestamp():
    graph = GapGraph()
    node = graph.create("missing", "x", "query:x", "QUALITY")
    node.updated_at = 12.5

    assert graph.since(12.5) == [node]
    assert graph.since(12.5001) == []


def test_save_load_round_trip_preserves_node_fields(tmp_path):
    graph = GapGraph()
    node = graph.create(
        "unresolved_refusal", "q", "agent_refusal", "QUALITY",
        blocks=["answer"], caused_by=["upstream"], required_for=["SELECT_ACTION"],
        acquisition_methods=["branch"], allowed_sources=["source"], max_depth=3,
        role="blocker", failure_type="missing_output", input_type="query",
        output_type="answer", expected_transition="open", observed_transition="closed",
    )
    path = tmp_path / "gaps.json"
    graph.save(path)

    loaded = GapGraph.load(path)

    assert loaded.nodes[node.gap_id].as_dict() == node.as_dict()
    original_text = path.read_text()
    graph.save(path)
    assert path.read_text() == original_text


def test_load_missing_or_invalid_json_returns_empty_graph(tmp_path):
    missing = tmp_path / "missing.json"
    malformed = tmp_path / "malformed.json"
    malformed.write_text("{")

    assert GapGraph.load(missing).nodes == {}
    assert GapGraph.load(malformed).nodes == {}


@pytest.mark.xfail(strict=False, reason="DEFECT: structurally invalid JSON payload escapes load error handling")
def test_load_parseable_non_mapping_payload_returns_empty_graph(tmp_path):
    path = tmp_path / "array.json"
    path.write_text("[]")

    assert GapGraph.load(path).nodes == {}


def test_refusal_handoff_and_resolution_are_idempotent():
    graph = GapGraph()
    first_id = refusal_to_gap(graph, "query", "NO_EVIDENCE", "branch-a", False, ["src"])
    again_id = refusal_to_gap(graph, "query", "OTHER", "branch-b", False)

    assert first_id == again_id
    assert len(graph.nodes) == 1
    node = graph.nodes[first_id]
    assert node.status == "DETECTED"
    assert node.acquisition_methods == ["branch-a"]
    assert node.allowed_sources == ["src"]

    resolved_id = refusal_to_gap(graph, "query", "NO_EVIDENCE", "branch-c", True)
    assert resolved_id == first_id
    assert node.status == "RESOLVED"
    assert refusal_to_gap(graph, "query", "NO_EVIDENCE", "branch-c", True) is None
    assert refusal_to_gap(graph, "query", "NO_EVIDENCE", "branch-d", False) == first_id
    assert len(graph.nodes) == 1
    assert node.status == "RESOLVED"


def test_two_concurrent_readers_observe_the_same_actionable_order():
    graph = GapGraph()
    nodes = [
        graph.create("missing", str(i), f"query:{i}", "QUALITY")
        for i in range(80)
    ]
    for i, node in enumerate(nodes):
        node.created_at = float(i)
    expected = [node.gap_id for node in nodes]

    with ThreadPoolExecutor(max_workers=2) as readers:
        results = list(readers.map(lambda _: [n.gap_id for n in graph.actionable()], range(8)))

    assert all(result == expected for result in results)


def test_repeated_duplicate_creates_do_not_grow_graph():
    graph = GapGraph()
    first = graph.create("missing", "same", "query:same", "QUALITY")

    for _ in range(100):
        assert graph.create("missing", "same", "query:same", "QUALITY") is first

    assert len(graph.nodes) == 1
