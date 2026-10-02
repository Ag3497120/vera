import pytest

from verantyx.gap_graph import GapGraph, GapNode, refusal_to_gap


def test_unresolved_refusal_keeps_query_verdict_branch_and_sources_exactly():
    graph = GapGraph()
    query = "Which witness did not sign section 4?"
    sources = ["record:deed-17", "record:page-2"]

    gap_id = refusal_to_gap(
        graph, query, "MISSING_SOURCE", "case_frame", False, sources=sources,
    )

    node = graph.get(gap_id)
    assert node is not None
    assert node.subject == query
    assert node.scope == "agent_refusal"
    assert node.status == "DETECTED"
    assert node.failure_type == "MISSING_SOURCE"
    assert node.acquisition_methods == ["case_frame"]
    assert node.allowed_sources == sources


def test_create_keeps_partial_and_negated_subject_text_without_normalizing_it():
    graph = GapGraph()
    subject = "...did not authorize transfer; clause 8 (partial span)"

    node = graph.create("MISSING_KNOWLEDGE", subject, "query:q1", "QUALITY")

    assert node.subject == subject
    assert graph.find_by_scope_subject("query:q1", subject) is node


def test_same_subject_in_different_scopes_does_not_swap_entities():
    graph = GapGraph()
    left = graph.create("MISSING_KNOWLEDGE", "the signer", "file:left", "QUALITY")
    right = graph.create("MISSING_KNOWLEDGE", "the signer", "file:right", "QUALITY")

    assert left.gap_id != right.gap_id
    assert graph.find_by_scope_subject("file:left", "the signer") is left
    assert graph.find_by_scope_subject("file:right", "the signer") is right


def test_create_reuses_only_an_exact_scope_and_subject_pair():
    graph = GapGraph()
    first = graph.create("MISSING_KNOWLEDGE", "claim A", "query:A", "QUALITY")
    second = graph.create("MISSING_KNOWLEDGE", "claim B", "query:A", "QUALITY")
    third = graph.create("MISSING_KNOWLEDGE", "claim A", "query:B", "QUALITY")

    assert len(graph.nodes) == 3
    assert graph.get(first.gap_id) is first
    assert second.subject == "claim B"
    assert third.scope == "query:B"


def test_resolving_one_exact_query_leaves_other_refusal_untouched():
    graph = GapGraph()
    first_id = refusal_to_gap(graph, "question A", "NO_SOURCE", "agent_a", False)
    second_id = refusal_to_gap(graph, "question B", "NO_SOURCE", "agent_b", False)

    touched = refusal_to_gap(graph, "question A", "NO_SOURCE", "agent_a", True)

    assert touched == first_id
    assert graph.get(first_id).status == "RESOLVED"
    assert graph.get(second_id).status == "DETECTED"
    assert graph.get(second_id).resolution is None


def test_resolving_missing_query_returns_none_without_creating_a_record():
    graph = GapGraph()

    assert refusal_to_gap(graph, "unknown query", "NO_SOURCE", "agent_a", True) is None
    assert graph.nodes == {}


def test_resolution_record_names_supplied_branch_and_answer_state():
    graph = GapGraph()
    gap_id = refusal_to_gap(graph, "question", "NO_SOURCE", "branch-7", False)

    assert refusal_to_gap(graph, "question", "NO_SOURCE", "branch-7", True) == gap_id
    node = graph.get(gap_id)
    assert node.status == "RESOLVED"
    assert node.resolution == "re-asked after branch 'branch-7'; store answers"


def test_gapnode_dict_round_trip_preserves_provenance_and_transition_fields():
    original = GapNode(
        gap_id="gap-fixed", gap_type="MISSING_KNOWLEDGE", subject="not the buyer",
        scope="file:contract", severity="CRITICAL", blocks=["answer"],
        caused_by=["gap-parent"], required_for=["SELECT_ACTION"],
        acquisition_methods=["case_frame"], allowed_sources=["record:12"],
        max_depth=3, resolution="verified from record:12", verified_by=["record:12"],
        role="blocker", failure_type="missing_output", input_type="claim",
        output_type="verified_fact", expected_transition="open->closed",
        observed_transition="open->open", created_at=12.5, updated_at=14.5,
    )

    restored = GapNode.from_dict(original.as_dict())

    assert restored.as_dict() == original.as_dict()


def test_actionable_returns_only_eligible_states_in_oldest_first_order():
    graph = GapGraph()
    later = graph.create("MISSING_KNOWLEDGE", "later", "query:later", "QUALITY")
    earlier = graph.create("MISSING_KNOWLEDGE", "earlier", "query:earlier", "QUALITY")
    blocked = graph.create(
        "MISSING_KNOWLEDGE", "blocked", "query:blocked", "QUALITY", status="BLOCKED_NO_SOURCE",
    )
    later.created_at = 20
    earlier.created_at = 10
    blocked.created_at = 1

    assert graph.actionable() == [earlier, later]


def test_create_rejects_unknown_severity_and_status():
    graph = GapGraph()

    with pytest.raises(ValueError):
        graph.create("MISSING_KNOWLEDGE", "subject", "query:q", "UNVERIFIED")
    with pytest.raises(ValueError):
        graph.create("MISSING_KNOWLEDGE", "subject", "query:q", "QUALITY", status="ANSWERED")


@pytest.mark.xfail(strict=False, reason="DEFECT: limit=0 returns all actionable nodes instead of none")
def test_actionable_zero_limit_returns_no_nodes():
    graph = GapGraph()
    graph.create("MISSING_KNOWLEDGE", "subject", "query:q", "QUALITY")

    assert graph.actionable(limit=0) == []
