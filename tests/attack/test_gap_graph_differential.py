"""Independent differential checks for unresolved-refusal gap storage."""
import json
import random
import time
from pathlib import Path

import pytest

from verantyx.gap_graph import GapGraph, gap_graph_path, refusal_to_gap


_STATUSES = {
    "DETECTED", "SCOPED", "RESOLUTION_PLANNED", "ACQUIRING",
    "EVIDENCE_COLLECTED", "VERIFIED", "RESOLVED", "BLOCKED_POLICY",
    "BLOCKED_NO_SOURCE", "BLOCKED_PERMISSION", "BLOCKED_BUDGET",
    "BLOCKED_CONTRADICTION", "STALE",
}
_ACTIONABLE = {"DETECTED", "SCOPED", "RESOLUTION_PLANNED"}
_SEVERITIES = {"CRITICAL", "QUALITY", "OPTIONAL"}
_OPTIONAL_FIELDS = (
    "required_for", "acquisition_methods", "allowed_sources", "max_depth",
    "resolution", "verified_by", "role", "failure_type", "input_type",
    "output_type", "expected_transition", "observed_transition",
)


def _reference_node(gap_type, subject, scope, severity, **values):
    row = {
        "gap_type": gap_type,
        "subject": subject,
        "scope": scope,
        "severity": severity,
        "status": "DETECTED",
        "blocks": [],
        "caused_by": [],
        "required_for": [],
        "acquisition_methods": [],
        "allowed_sources": [],
        "max_depth": 1,
        "resolution": None,
        "verified_by": [],
        "role": None,
        "failure_type": None,
        "input_type": None,
        "output_type": None,
        "expected_transition": None,
        "observed_transition": None,
    }
    row.update(values)
    return row


def _node_values(node):
    names = (
        "gap_type", "subject", "scope", "severity", "status", "blocks",
        "caused_by", "required_for", "acquisition_methods", "allowed_sources",
        "max_depth", "resolution", "verified_by", "role", "failure_type",
        "input_type", "output_type", "expected_transition", "observed_transition",
    )
    return {name: getattr(node, name) for name in names}


class _ReferenceGraph:
    """List-based model: lookup is deliberately a scan, not the module's map."""

    def __init__(self):
        self.rows = []

    def find(self, scope, subject):
        return next(
            (row for row in self.rows
             if row["scope"] == scope and row["subject"] == subject),
            None,
        )

    def create(self, gap_type, subject, scope, severity, **values):
        existing = self.find(scope, subject)
        if existing is not None:
            return existing, False
        row = _reference_node(gap_type, subject, scope, severity, **values)
        self.rows.append(row)
        return row, True

    def actionable(self, limit=None):
        rows = sorted(
            (row for row in self.rows if row["status"] in _ACTIONABLE),
            key=lambda row: row["created_at"],
        )
        return rows if limit is None else rows[:limit]

    def since(self, timestamp):
        return [row for row in self.rows if row["updated_at"] >= timestamp]


def _as_expected(row):
    return {
        key: value for key, value in row.items()
        if key not in {"handle", "created_at", "updated_at"}
    }


def test_generated_create_and_scope_subject_reuse_match_reference():
    rng = random.Random(60831)
    reference = _ReferenceGraph()
    graph = GapGraph()
    subjects = ("query alpha", "query beta", "repo:core", "query gamma")
    scopes = ("agent_refusal", "query:alpha", "repo:core")
    for index in range(120):
        subject = rng.choice(subjects)
        scope = rng.choice(scopes)
        kwargs = {
            "status": rng.choice(sorted(_STATUSES)),
            "blocks": [f"block-{rng.randrange(4)}"],
            "caused_by": [f"cause-{rng.randrange(3)}"],
            "required_for": [f"cap-{rng.randrange(3)}"],
            "acquisition_methods": [f"method-{rng.randrange(3)}"],
            "allowed_sources": [f"source-{rng.randrange(3)}"],
            "max_depth": rng.randrange(1, 5),
            "role": f"role-{rng.randrange(3)}",
            "failure_type": f"failure-{rng.randrange(4)}",
            "input_type": "query",
            "output_type": "answer",
            "expected_transition": "open->closed",
            "observed_transition": f"state-{index}",
        }
        gap_type = f"type-{index}"
        severity = rng.choice(sorted(_SEVERITIES))
        expected, is_new = reference.create(
            gap_type, subject, scope, severity, **kwargs
        )
        started = time.time()
        observed = graph.create(
            gap_type, subject, scope, severity,
            status=kwargs["status"], blocks=kwargs["blocks"],
            caused_by=kwargs["caused_by"], required_for=kwargs["required_for"],
            acquisition_methods=kwargs["acquisition_methods"],
            allowed_sources=kwargs["allowed_sources"], max_depth=kwargs["max_depth"],
            role=kwargs["role"], failure_type=kwargs["failure_type"],
            input_type=kwargs["input_type"], output_type=kwargs["output_type"],
            expected_transition=kwargs["expected_transition"],
            observed_transition=kwargs["observed_transition"],
        )
        if is_new:
            expected["handle"] = observed.gap_id
            assert started <= observed.created_at <= time.time()
            assert started <= observed.updated_at <= time.time()
        assert observed.gap_id == expected["handle"]
        assert _node_values(observed) == _as_expected(expected)
        assert len(graph.nodes) == len(reference.rows)


@pytest.mark.parametrize(
    "field,value",
    [("severity", "URGENT"), ("status", "UNKNOWN")],
)
def test_create_rejects_values_outside_closed_enums(field, value):
    graph = GapGraph()
    with pytest.raises(ValueError):
        graph.create(
            "MISSING", "subject", "scope", value if field == "severity" else "QUALITY",
            **({"status": value} if field == "status" else {}),
        )
    assert graph.nodes == {}


def test_set_status_matches_reference_updates_and_unknown_id_behavior():
    graph = GapGraph()
    node = graph.create("MISSING", "subject", "scope", "QUALITY")
    reference = _reference_node("MISSING", "subject", "scope", "QUALITY")

    before = time.time()
    result = graph.set_status(
        node.gap_id, "VERIFIED", resolution="source checked",
        verified_by=["judge-a", "judge-b"],
    )
    reference["status"] = "VERIFIED"
    reference["resolution"] = "source checked"
    reference["verified_by"].extend(["judge-a", "judge-b"])
    assert result is node
    assert node.updated_at >= before
    assert _node_values(node) == _as_expected(reference)

    before = time.time()
    assert graph.set_status(node.gap_id, "ACQUIRING") is node
    reference["status"] = "ACQUIRING"
    assert node.updated_at >= before
    assert _node_values(node) == _as_expected(reference)
    assert graph.set_status("absent-gap", "RESOLVED") is None

    with pytest.raises(ValueError):
        graph.set_status(node.gap_id, "UNKNOWN")
    assert _node_values(node) == _as_expected(reference)


def test_actionable_fifo_filter_and_positive_limit_match_reference():
    graph = GapGraph()
    reference = _ReferenceGraph()
    statuses = [
        "DETECTED", "RESOLVED", "SCOPED", "BLOCKED_NO_SOURCE",
        "RESOLUTION_PLANNED", "STALE", "DETECTED",
    ]
    for index, status in enumerate(statuses):
        node = graph.create(f"TYPE-{index}", f"s-{index}", f"scope-{index}", "QUALITY", status=status)
        row, _ = reference.create(
            f"TYPE-{index}", f"s-{index}", f"scope-{index}", "QUALITY", status=status
        )
        # Controlled, distinct ages make FIFO expectations independent of wall-clock granularity.
        node.created_at = float(50 - index)
        row["created_at"] = float(50 - index)
        row["handle"] = node.gap_id
    expected = reference.actionable()
    assert [node.gap_id for node in graph.actionable()] == [row["handle"] for row in expected]
    assert [node.gap_id for node in graph.actionable(limit=2)] == [
        row["handle"] for row in reference.actionable(limit=2)
    ]


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: actionable(limit=0) returns every candidate instead of an empty slice",
)
def test_zero_actionable_limit_returns_no_candidates():
    graph = GapGraph()
    graph.create("MISSING", "subject", "scope", "QUALITY")
    assert graph.actionable(limit=0) == []


def test_since_uses_inclusive_update_timestamp():
    graph = GapGraph()
    reference = _ReferenceGraph()
    for index, updated in enumerate((3.0, 5.0, 8.0, 5.0, 1.0)):
        node = graph.create(f"TYPE-{index}", f"s-{index}", f"scope-{index}", "OPTIONAL")
        row, _ = reference.create(f"TYPE-{index}", f"s-{index}", f"scope-{index}", "OPTIONAL")
        node.updated_at = updated
        row["updated_at"] = updated
        row["handle"] = node.gap_id
    for cutoff in (0.0, 3.0, 5.0, 8.0, 9.0):
        expected = [row["handle"] for row in reference.since(cutoff)]
        assert [node.gap_id for node in graph.since(cutoff)] == expected


def test_save_load_preserves_all_typed_node_fields(tmp_path):
    graph = GapGraph()
    node = graph.create(
        "MISSING_KNOWLEDGE", "京都の天気", "query:天気", "CRITICAL",
        status="EVIDENCE_COLLECTED", blocks=["answer", "gap-x"],
        caused_by=["gap-root"], required_for=["SELECT_ACTION"],
        acquisition_methods=["lookup", "ask"], allowed_sources=["official"],
        max_depth=4, role="blocker", failure_type="missing_output",
        input_type="query", output_type="forecast",
        expected_transition="unknown->known", observed_transition="unknown",
    )
    node.resolution = "closed by verified evidence"
    node.verified_by = ["independent-check"]
    node.created_at = 123.25
    node.updated_at = 456.5
    expected = {
        "gap_id": node.gap_id,
        "gap_type": "MISSING_KNOWLEDGE", "subject": "京都の天気",
        "scope": "query:天気", "severity": "CRITICAL",
        "status": "EVIDENCE_COLLECTED", "blocks": ["answer", "gap-x"],
        "caused_by": ["gap-root"], "required_for": ["SELECT_ACTION"],
        "acquisition_methods": ["lookup", "ask"], "allowed_sources": ["official"],
        "max_depth": 4, "resolution": "closed by verified evidence",
        "verified_by": ["independent-check"], "created_at": 123.25,
        "updated_at": 456.5, "role": "blocker", "failure_type": "missing_output",
        "input_type": "query", "output_type": "forecast",
        "expected_transition": "unknown->known", "observed_transition": "unknown",
    }
    path = tmp_path / "gaps.json"
    graph.save(path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert list(saved) == [node.gap_id]
    serialized_node = saved[node.gap_id]
    assert serialized_node.pop("gap_id") == node.gap_id
    assert serialized_node == {key: value for key, value in expected.items() if key != "gap_id"}

    loaded = GapGraph.load(path)
    restored = loaded.get(node.gap_id)
    assert restored is not None
    assert _node_values(restored) == {
        key: value for key, value in expected.items()
        if key not in {"gap_id", "created_at", "updated_at"}
    }
    assert restored.created_at == 123.25
    assert restored.updated_at == 456.5


def test_load_missing_file_and_legacy_row_use_documented_defaults(tmp_path):
    missing = GapGraph.load(tmp_path / "missing.json")
    assert missing.nodes == {}

    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"legacy-1": {
        "gap_id": "legacy-1", "gap_type": "MISSING", "subject": "古い記録",
        "scope": "repo:old", "severity": "QUALITY",
    }}), encoding="utf-8")
    loaded = GapGraph.load(path)
    row = loaded.get("legacy-1")
    assert row is not None
    assert row.status == "DETECTED"
    assert row.blocks == [] and row.caused_by == [] and row.required_for == []
    assert row.acquisition_methods == [] and row.allowed_sources == []
    assert row.max_depth == 1 and row.resolution is None and row.verified_by == []
    assert row.created_at == 0.0 and row.updated_at == 0.0
    assert row.role is None and row.failure_type is None
    assert row.input_type is None and row.output_type is None
    assert row.expected_transition is None and row.observed_transition is None


def test_refusal_to_gap_is_idempotent_and_resolves_the_existing_refusal():
    graph = GapGraph()
    first_id = refusal_to_gap(
        graph, "where is the report?", "needs_source", "branch-a", False,
        sources=["handbook"],
    )
    assert first_id is not None
    first = graph.get(first_id)
    assert first is not None
    expected_first = _reference_node(
        "unresolved_refusal", "where is the report?", "agent_refusal", "QUALITY",
        failure_type="needs_source", acquisition_methods=["branch-a"],
        allowed_sources=["handbook"],
    )
    assert _node_values(first) == expected_first

    again_id = refusal_to_gap(
        graph, "where is the report?", "other_verdict", "branch-b", False,
        sources=["different-source"],
    )
    assert again_id == first_id
    assert len(graph.nodes) == 1
    assert _node_values(first) == expected_first

    resolved_id = refusal_to_gap(
        graph, "where is the report?", "ignored", "branch-c", True
    )
    assert resolved_id == first_id
    assert first.status == "RESOLVED"
    assert first.resolution == "re-asked after branch 'branch-c'; store answers"
    assert refusal_to_gap(graph, "where is the report?", "ignored", "branch-d", True) is None


def test_refusal_resolution_without_a_matching_gap_is_a_noop():
    graph = GapGraph()
    assert refusal_to_gap(graph, "unknown query", "verdict", "branch", True) is None
    assert graph.nodes == {}


def test_gap_graph_path_is_a_sibling_of_the_store_file():
    store_path = Path("/tmp/vera/store.json")
    assert gap_graph_path(store_path) == Path("/tmp/vera/gap_graph.json")
