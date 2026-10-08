"""Rebind multigrain leaf proposals to exact original document spans.

The adapter's display source labels are intentionally ignored. A hierarchy
leaf is usable only when its node name maps one-to-one to the Bot's original
document ID, the original/index text hashes still match the construction
snapshot, the leaf CrossStore fingerprint is unchanged, and the proposed core
occurs inside a source-reader Clause with an exact original-text span.

This establishes document identity and location for local retrieval. It does
not establish independent sources or truth outside the supplied documents.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
from typing import Literal

from .semantic_ir import Clause, Span, Unread, View

VERSION = "multigrain-source-binding-v1"
MAX_HIERARCHY_NODES = 4096
MAX_FACET_LINKS = 65536
MAX_BOUND_SOURCE_EVENTS = 8


@dataclass(frozen=True)
class SourceIdentityRecord:
    source_id: str
    original_sha256: str
    indexed_text_sha256: str
    leaf_store_sha256: str
    leaf_path: tuple[str, ...]


@dataclass(frozen=True)
class SourceRegistrySnapshot:
    status: Literal["READY", "HOLD"]
    reason: str
    records: tuple[SourceIdentityRecord, ...] = ()
    sha256: str = ""


@dataclass(frozen=True)
class SelectedSourceSpan:
    source_id: str
    original_sha256: str
    leaf_id: str
    leaf_path: tuple[str, ...]
    candidate: str
    candidate_spans: tuple[tuple[int, int], ...]
    sentence_start: int
    sentence_end: int
    sentence_text: str
    clause_ids: tuple[str, ...]
    predicates: tuple[str, ...]
    request_target_anchor: str = ""
    target_role: str = ""
    target_argument_span: tuple[int, int] | None = None
    target_case_particle_span: tuple[int, int] | None = None
    candidate_role: str = ""
    candidate_argument_span: tuple[int, int] | None = None
    source_frame_id: str = ""
    source_clause_id: str = ""
    source_assertion_status: str = ""


@dataclass(frozen=True)
class SourceBindingResult:
    status: Literal["BOUND", "HOLD"]
    reason: str
    candidate: str = ""
    registry_sha256: str = ""
    selections: tuple[SelectedSourceSpan, ...] = ()
    views: tuple[View, ...] = ()

    def as_dict(self) -> dict:
        return {
            "version": VERSION,
            "status": self.status,
            "reason": self.reason,
            "candidate": self.candidate,
            "registry_sha256": self.registry_sha256,
            "scope": "document identity and original-text location only",
            "goal_relation_scope": "same-owner local explicit argument spans only",
            "source_truth_status": "UNCLASSIFIED; no truth or authority claim",
            "independent_source_count": None,
            "selections": [
                {
                    "source_id": item.source_id,
                    "original_sha256": item.original_sha256,
                    "leaf_id": item.leaf_id,
                    "leaf_path": list(item.leaf_path),
                    "candidate": item.candidate,
                    "candidate_spans": [list(span) for span in item.candidate_spans],
                    "sentence_text": item.sentence_text,
                    "sentence_span": {
                        "source": item.source_id,
                        "start": item.sentence_start,
                        "end": item.sentence_end,
                    },
                    "clause_ids": list(item.clause_ids),
                    "predicates": list(item.predicates),
                    "request_target_anchor": item.request_target_anchor or None,
                    "target_role": item.target_role or None,
                    "target_argument_span": (list(item.target_argument_span)
                                             if item.target_argument_span else None),
                    "target_case_particle_span": (
                        list(item.target_case_particle_span)
                        if item.target_case_particle_span else None),
                    "candidate_role": item.candidate_role or None,
                    "candidate_argument_span": (
                        list(item.candidate_argument_span)
                        if item.candidate_argument_span else None),
                    "source_frame_id": item.source_frame_id or None,
                    "source_frame_evidence_clause_id": item.source_clause_id or None,
                    "source_assertion_status": item.source_assertion_status or None,
                }
                for item in self.selections
            ],
        }


@dataclass(frozen=True)
class SourceEventRoleEvidence:
    role: str
    value: str
    argument_span: tuple[int, int]
    case_particle: str
    particle_span: tuple[int, int]

    def as_dict(self) -> dict:
        return {
            "role": self.role,
            "value": self.value,
            "argument_span": list(self.argument_span),
            "case_particle": self.case_particle,
            "particle_span": list(self.particle_span),
        }


@dataclass(frozen=True)
class BoundSourceEvent:
    source_id: str
    source_sha256: str
    frame_evidence_clause_id: str
    frame_id: str
    semantic_clause_id: str
    predicate: str
    predicate_span: tuple[int, int]
    clause_span: tuple[int, int]
    clause_text: str
    target_roles: tuple[SourceEventRoleEvidence, ...]
    roles: tuple[SourceEventRoleEvidence, ...]
    assertion_status: str = "UNCLASSIFIED"

    def as_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "source_sha256": self.source_sha256,
            "frame_evidence_clause_id": self.frame_evidence_clause_id,
            "frame_id": self.frame_id,
            "semantic_clause_id": self.semantic_clause_id,
            "predicate": self.predicate,
            "predicate_span": list(self.predicate_span),
            "clause_span": list(self.clause_span),
            "clause_text": self.clause_text,
            "target_roles": [item.as_dict() for item in self.target_roles],
            "roles": [item.as_dict() for item in self.roles],
            "assertion_status": self.assertion_status,
        }


@dataclass(frozen=True)
class SourceEventSetBinding:
    status: Literal["BOUND", "HOLD"]
    reason: str
    raw_request_sha256: str = ""
    request_projection: dict | None = None
    source_id: str = ""
    source_sha256: str = ""
    target_anchor: str = ""
    selection_scope: str = "all_explicit_local_mentions"
    required_sentence_count: int | None = None
    events: tuple[BoundSourceEvent, ...] = ()
    explicit_anchor_occurrence_count: int = 0

    def as_dict(self) -> dict:
        return {
            "version": VERSION,
            "status": self.status,
            "reason": self.reason,
            "raw_request_sha256": self.raw_request_sha256,
            "request_projection": self.request_projection,
            "source_id": self.source_id,
            "source_sha256": self.source_sha256,
            "target_anchor": self.target_anchor,
            "selection_scope": self.selection_scope,
            "required_sentence_count": self.required_sentence_count,
            "events": [event.as_dict() for event in self.events],
            "event_count": len(self.events),
            "explicit_anchor_occurrence_count": self.explicit_anchor_occurrence_count,
            "explicit_anchor_coverage": "COMPLETE_FOR_LITERAL_OCCURRENCES"
            if self.status == "BOUND" else "UNVERIFIED",
            "semantic_event_set_complete": None,
            "source_truth_status": "UNCLASSIFIED; no truth or authority claim",
            "goal_satisfied": None,
            "success_count_eligible": False,
        }


def _sha256(text: str) -> str | None:
    if type(text) is not str:
        return None
    try:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except UnicodeEncodeError:
        return None


def _crosses_sha256(store: object) -> str | None:
    crosses = getattr(store, "crosses", None)
    if not isinstance(crosses, Mapping):
        return None
    rows = []
    for core, facets in crosses.items():
        # CrossStore's persisted contract is core -> {facet: positive_count}.
        # Hash the counts too: they participate in the existing multi-grain
        # selector, so changing only a weight must invalidate this snapshot.
        if type(core) is not str or type(facets) is not dict:
            return None
        if any(type(facet) is not str or type(count) is not int or count < 1
               for facet, count in facets.items()):
            return None
        rows.append([core, [[facet, facets[facet]] for facet in sorted(facets)]])
    rows.sort(key=lambda row: row[0])
    try:
        payload = json.dumps(rows, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
    except (UnicodeEncodeError, TypeError, ValueError):
        return None


def _leaf_nodes(root: object) -> tuple[dict[str, tuple[tuple[str, ...], object]], str]:
    if root is None:
        return {}, "existing navigation hierarchy is absent"
    pending = [(root, ())]
    visited: set[int] = set()
    leaves: dict[str, tuple[tuple[str, ...], object]] = {}
    seen_nodes = 0
    while pending:
        node, parent_path = pending.pop()
        identity = id(node)
        if identity in visited:
            return {}, "navigation hierarchy contains a repeated node"
        visited.add(identity)
        seen_nodes += 1
        if seen_nodes > MAX_HIERARCHY_NODES:
            return {}, "navigation hierarchy exceeds the node bound"
        name = getattr(node, "name", None)
        children = getattr(node, "children", None)
        if type(name) is not str or not name or type(children) is not dict:
            return {}, "navigation node has an invalid name or children container"
        path = parent_path + (name,)
        if not children:
            if name in leaves:
                return {}, "navigation hierarchy has duplicate leaf names"
            if getattr(node, "store", None) is None:
                return {}, "source leaf has no CrossStore"
            leaves[name] = (path, node)
            continue
        for child_name, child in sorted(children.items(), key=lambda pair: str(pair[0]), reverse=True):
            if type(child_name) is not str or getattr(child, "name", None) != child_name:
                return {}, "hierarchy child key does not match its node name"
            pending.append((child, path))
    return leaves, ""


def _exact_facet_owner_rows(
    root: object, facet: str, *, limit: int,
) -> tuple[list[dict], dict, str]:
    """List exact core→facet owners as untrusted source-location hypotheses.

    This does not select a fact or infer a relation. It inverts only the
    existing CrossStore facet links so a Goal whose target is intentionally a
    facet (for example 資料 under 花子) can reach the later same-Frame span
    checks. The consumer repeats this walk and compares the complete rows.
    """
    if type(facet) is not str or not facet:
        return [], {}, "facet anchor must be exact nonempty text"
    if type(limit) is not int or limit < 1:
        return [], {}, "facet owner limit must be a positive integer"
    leaves, reason = _leaf_nodes(root)
    if reason:
        return [], {}, reason

    owners: dict[str, list[dict]] = {}
    visited_links = 0
    for leaf_id, (path, node) in sorted(leaves.items()):
        store = getattr(node, "store", None)
        crosses = getattr(store, "crosses", None)
        labels = getattr(store, "source_labels", None)
        if type(crosses) is not dict or type(labels) not in (set, frozenset):
            return [], {}, "source leaf does not expose the exact CrossStore shape"
        # A source label is display metadata, never a facet anchor.
        if facet in labels:
            continue
        for core, facets in crosses.items():
            if type(core) is not str or type(facets) is not dict:
                return [], {}, "source leaf CrossStore core/facet shape is invalid"
            visited_links += len(facets)
            if visited_links > MAX_FACET_LINKS:
                return [], {"visited_leaves": len(leaves),
                            "visited_facet_links": visited_links}, \
                    "exact facet owner scan exceeded its link bound"
            if any(type(name) is not str or type(count) is not int or count < 1
                   for name, count in facets.items()):
                return [], {}, "source leaf CrossStore contains an invalid facet link"
            if facet not in facets:
                continue
            ref = {
                "leaf": leaf_id,
                "domain_path": list(path[:-1]),
                "path": list(path),
                "source_label": None,
                "canonical_source_id": None,
                "identity_status": "identity_unverified",
                "facet_link": {
                    "core": core,
                    "facet": facet,
                    "count": facets[facet],
                    "role": "unverified_crossstore_link",
                },
            }
            owners.setdefault(core, []).append(ref)

    rows = []
    for core, refs in sorted(owners.items()):
        refs.sort(key=lambda ref: (tuple(ref["path"]), ref["leaf"]))
        rows.append({
            "item": core,
            "resolution_views": [],
            "sources": refs[:limit],
            "source_leaf_match_count": len({ref["leaf"] for ref in refs}),
            "source_reference_count": len(refs),
            "source_references_truncated": len(refs) > limit,
            "independent_source_count": None,
            "source_identity_status": "identity_unverified",
            "selected_by_existing_constellation": False,
            "selection_used_resolution_views": False,
            "selection_method": "exact_unverified_crossstore_facet_owner",
        })
    return rows, {"visited_leaves": len(leaves),
                  "visited_facet_links": visited_links}, ""


def _registry_digest(records: tuple[SourceIdentityRecord, ...]) -> str | None:
    payload = [
        {
            "source_id": item.source_id,
            "original_sha256": item.original_sha256,
            "indexed_text_sha256": item.indexed_text_sha256,
            "leaf_store_sha256": item.leaf_store_sha256,
            "leaf_path": list(item.leaf_path),
        }
        for item in records
    ]
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    except (UnicodeEncodeError, TypeError, ValueError):
        return None


def capture_source_registry(bot: object, navigation_root: object) -> SourceRegistrySnapshot:
    """Capture source IDs, raw hashes, indexed-text hashes, and leaf stores."""
    originals = getattr(bot, "original_texts", None)
    base = getattr(bot, "base", None)
    base_docs = getattr(base, "docs", None)
    if type(originals) is not dict or type(base_docs) is not dict:
        return SourceRegistrySnapshot("HOLD", "Bot originals or Base documents are not exact dictionaries")
    if not originals or len(originals) > 64 or set(originals) != set(base_docs):
        return SourceRegistrySnapshot("HOLD", "original document IDs do not exactly match bounded Base IDs")
    if any(type(key) is not str or not key or type(value) is not str
           for key, value in originals.items()):
        return SourceRegistrySnapshot("HOLD", "original source IDs/text must be exact strings")
    try:
        for key in originals:
            key.encode("utf-8")
    except UnicodeEncodeError:
        return SourceRegistrySnapshot("HOLD", "an original source ID is not valid UTF-8")
    leaves, reason = _leaf_nodes(navigation_root)
    if reason:
        return SourceRegistrySnapshot("HOLD", reason)
    if set(leaves) != set(originals):
        return SourceRegistrySnapshot("HOLD", "hierarchy leaf IDs do not exactly match original document IDs")

    records = []
    for source_id in sorted(originals):
        original = originals[source_id]
        indexed = base_docs[source_id]
        if type(indexed) is not dict or type(indexed.get("text")) is not str:
            return SourceRegistrySnapshot("HOLD", "Base source record has no exact indexed text")
        path, leaf = leaves[source_id]
        original_sha = _sha256(original)
        indexed_sha = _sha256(indexed["text"])
        leaf_sha = _crosses_sha256(getattr(leaf, "store", None))
        if not original_sha or not indexed_sha or not leaf_sha:
            return SourceRegistrySnapshot("HOLD", "a source hash or CrossStore fingerprint could not be derived")
        records.append(SourceIdentityRecord(source_id, original_sha, indexed_sha,
                                            leaf_sha, path))
    frozen = tuple(records)
    digest = _registry_digest(frozen)
    if not digest:
        return SourceRegistrySnapshot("HOLD", "source registry digest could not be derived")
    return SourceRegistrySnapshot("READY", "source IDs are bound to the captured raw/index/leaf hashes",
                                  frozen, digest)


def _registry_is_current(bot: object, root: object,
                         snapshot: SourceRegistrySnapshot) -> tuple[bool, str]:
    if (type(snapshot) is not SourceRegistrySnapshot
            or type(snapshot.status) is not str or snapshot.status != "READY"):
        return False, "no READY source identity snapshot was captured at indexing time"
    if (type(snapshot.records) is not tuple
            or any(type(item) is not SourceIdentityRecord for item in snapshot.records)
            or any(type(item.source_id) is not str
                   or type(item.original_sha256) is not str
                   or type(item.indexed_text_sha256) is not str
                   or type(item.leaf_store_sha256) is not str
                   or type(item.leaf_path) is not tuple
                   or any(type(part) is not str for part in item.leaf_path)
                   for item in snapshot.records)
            or type(snapshot.sha256) is not str
            or snapshot.sha256 != _registry_digest(snapshot.records)):
        return False, "source identity snapshot has an invalid internal shape or digest"
    current = capture_source_registry(bot, root)
    if current.status != "READY":
        return False, current.reason
    if current.records != snapshot.records or current.sha256 != snapshot.sha256:
        return False, "original text, indexed text, hierarchy path, or leaf CrossStore changed after indexing"
    return True, ""


def _span_valid(raw: str, span: object) -> bool:
    return (
        type(span) is Span
        and type(span.source) is str
        and type(span.start) is int
        and type(span.end) is int
        and 0 <= span.start < span.end <= len(raw)
        and type(span.text) is str
        and raw[span.start:span.end] == span.text
    )


def _occurrences(raw: str, start: int, end: int, candidate: str) -> tuple[tuple[int, int], ...]:
    found = []
    cursor = start
    while cursor < end:
        at = raw.find(candidate, cursor, end)
        if at < 0:
            break
        found.append((at, at + len(candidate)))
        cursor = at + 1
    return tuple(found)


def _overlap(left_start: int, left_end: int, span: object) -> bool:
    return (type(getattr(span, "start", None)) is int
            and type(getattr(span, "end", None)) is int
            and left_start < span.end and span.start < left_end)


def _hold(reason: str, *, candidate: str = "", registry_sha256: str = "") -> SourceBindingResult:
    return SourceBindingResult("HOLD", reason, candidate, registry_sha256)


@dataclass(frozen=True)
class _LocalGoalRoleProof:
    source_frame_id: str
    source_clause_id: str
    candidate_role: str
    candidate_span: tuple[int, int]
    target_span: tuple[int, int]
    target_case_span: tuple[int, int]


def _valid_frame_argument(raw: str, argument: object, *, role: str, value: str,
                          frame_id: str, source_clause: object) -> bool:
    from .frame_evidence import ArgumentEvidence, SourceSpan

    if (type(argument) is not ArgumentEvidence
            or argument.role != role or argument.value != value
            or argument.permitted is not True
            or argument.origin != "EXPLICIT_CASE"
            or argument.binding_status != "UNIQUE"
            or argument.source_owner_status != "LOCAL_TOKEN_WINDOW"
            or argument.argument_quote_status != "UNQUOTED"
            or argument.case_quote_status != "UNQUOTED"
            or argument.binding_quote_status != "UNQUOTED"
            or argument.owner_frame_id != frame_id
            or argument.source_frame_id != frame_id
            or type(argument.case_particle) is not str
            or type(argument.span) is not SourceSpan
            or type(argument.particle_span) is not SourceSpan):
        return False
    span = argument.span
    particle = argument.particle_span
    if (type(span.start) is not int or type(span.end) is not int
            or type(particle.start) is not int or type(particle.end) is not int
            or not 0 <= span.start < span.end <= len(raw)
            or not 0 <= particle.start < particle.end <= len(raw)
            or raw[span.start:span.end] != value
            or span.text != value
            or raw[particle.start:particle.end] != argument.case_particle
            or particle.text != argument.case_particle
            or span.end != particle.start):
        return False
    predicate_span = getattr(source_clause, "predicate_span", None)
    return (type(predicate_span) is SourceSpan
            and type(predicate_span.start) is int
            and span.start < predicate_span.start
            and predicate_span.end <= len(raw)
            and particle.end <= predicate_span.start)


def _local_goal_role_proof(
    raw: str, source_id: str, candidate: str, target_anchor: str,
    semantic_clause: Clause, evidence: object,
) -> tuple[_LocalGoalRoleProof | None, str]:
    """Rebind candidate and target as explicit roles of one source Frame.

    FrameEvidence permission is used only for local argument attachment. Its
    assertion_status remains UNCLASSIFIED and is deliberately not treated as
    evidence that the source proposition is true.
    """
    from .frame_evidence import (
        ClauseEvidence, FrameEvidenceDocument, FrameSnapshot, read_frame_evidence,
    )

    if type(raw) is not str or type(semantic_clause) is not Clause:
        return None, "source clause/raw text is not typed"
    if type(evidence) is not FrameEvidenceDocument:
        return None, "source FrameEvidenceDocument is missing"
    if (evidence.source_id != source_id or evidence.source_text != raw
            or evidence.source_sha256 != _sha256(raw)
            or evidence.alignment_status != "ALIGNED_BY_READER_ORDER"
            or evidence.reader_order_alignment_status != "ALIGNED_BY_READER_ORDER"
            or not evidence.token_positions_complete
            or evidence.source_coverage_status not in ("EXACT", "WHITESPACE_ONLY")
            or evidence.unmatched_frames
            or any(gap.classification != "WHITESPACE"
                   for gap in evidence.source_gaps)):
        return None, "source FrameEvidence envelope/alignment/coverage is unresolved"
    span = semantic_clause.span
    predicate_span = semantic_clause.predicate_span
    if (not _span_valid(raw, span) or span.source != source_id
            or not _span_valid(raw, predicate_span)
            or predicate_span.source != source_id):
        return None, "semantic Clause span does not point into the exact source"
    sidecars = [clause for clause in evidence.clauses
                if type(clause) is ClauseEvidence
                and type(clause.predicate_span) is not type(None)
                and clause.predicate_span.start == predicate_span.start
                and clause.predicate_span.end == predicate_span.end]
    if len(sidecars) != 1:
        return None, "source predicate span does not identify one FrameEvidence owner"
    source_clause = sidecars[0]
    frame = source_clause.frame
    if (type(frame) is not FrameSnapshot
            or source_clause.predicate != semantic_clause.predicate
            or frame.predicate != semantic_clause.predicate
            or source_clause.alignment_status != "ALIGNED_BY_READER_ORDER"
            or source_clause.scope_status != "KNOWN"
            or source_clause.polarity != "POSITIVE"
            or source_clause.local_scope_status != "KNOWN"
            or source_clause.local_polarity != "POSITIVE"
            or source_clause.quote_status != "UNQUOTED"
            or source_clause.assertion_status != "UNCLASSIFIED"
            or frame.negated or frame.ambiguous
            or frame.patient != target_anchor
            or semantic_clause.polarity != "+"
            or semantic_clause.modality != "assert"
            or semantic_clause.unsupported):
        return None, "source event scope, Frame, or target patient is not safely bound"

    patient_args = [argument for argument in source_clause.arguments
                    if getattr(argument, "role", None) == "patient"
                    and getattr(argument, "value", None) == target_anchor]
    if (len(patient_args) != 1 or not _valid_frame_argument(
            raw, patient_args[0], role="patient", value=target_anchor,
            frame_id=source_clause.frame_id, source_clause=source_clause)):
        return None, "request target is not one permitted explicit local patient argument"
    patient = patient_args[0]
    patient_span = patient.span
    patient_particle_span = patient.particle_span
    assert patient_span is not None and patient_particle_span is not None
    if not (span.start <= patient_span.start < patient_span.end
            <= patient_particle_span.start < patient_particle_span.end <= span.end):
        return None, "source patient argument/case span escapes its exact Clause"
    semantic_patients = [role for role in semantic_clause.roles
                         if role.name == "patient" and role.term == target_anchor
                         and _span_valid(raw, role.span)
                         and role.span.source == source_id
                         and (role.span.start, role.span.end)
                             == (patient_span.start, patient_span.end)]
    if len(semantic_patients) != 1:
        return None, "source semantic Clause does not preserve the exact sidecar patient span"

    candidate_args = [argument for argument in source_clause.arguments
                      if getattr(argument, "role", None) in
                      ("agent", "patient", "recipient")
                      and getattr(argument, "value", None) == candidate]
    valid_candidates = [argument for argument in candidate_args
                        if _valid_frame_argument(
                            raw, argument, role=argument.role, value=candidate,
                            frame_id=source_clause.frame_id,
                            source_clause=source_clause)]
    if len(valid_candidates) != 1:
        return None, "candidate does not identify one permitted local role of the same source Frame"
    candidate_arg = valid_candidates[0]
    candidate_span = candidate_arg.span
    assert candidate_span is not None
    if not span.start <= candidate_span.start < candidate_span.end <= span.end:
        return None, "candidate role span escapes its exact source Clause"
    semantic_candidates = [role for role in semantic_clause.roles
                           if role.name == candidate_arg.role and role.term == candidate
                           and _span_valid(raw, role.span)
                           and role.span.source == source_id
                           and (role.span.start, role.span.end)
                               == (candidate_span.start, candidate_span.end)]
    if len(semantic_candidates) != 1:
        return None, "source semantic Clause does not preserve the candidate's same-owner role span"
    return _LocalGoalRoleProof(
        source_frame_id=source_clause.frame_id,
        source_clause_id=source_clause.clause_id,
        candidate_role=candidate_arg.role,
        candidate_span=(candidate_span.start, candidate_span.end),
        target_span=(patient_span.start, patient_span.end),
        target_case_span=(patient_particle_span.start, patient_particle_span.end),
    ), ""


def retrieve_goal_candidate_navigation(
    raw_request: str,
    constellation: object,
    *,
    source_router: object = None,
    limit: int = 8,
) -> dict:
    """Search from a rederivable raw-Goal target projection, not action text.

    This is only a candidate locator. The source binder independently
    rederives and compares the projection before using any returned candidate.
    """
    from .compositional_goal import derive_request_selection_projection

    projection = derive_request_selection_projection(raw_request)
    if projection.status != "READY":
        return {
            "kind": "multigrain_candidates",
            "verdict": "UNKNOWN_REQUEST_GOAL_SELECTION_HOLD",
            "raw_question": raw_request if type(raw_request) is str else None,
            "selector_query": "",
            "selector_query_origin": "explicit_candidate_query",
            "query_terms": [],
            "selected_candidate": None,
            "resolution_verdict": "UNKNOWN_REQUEST_GOAL_SELECTION_HOLD",
            "resolution_item": None,
            "source_identity_status": "UNKNOWN_NO_SOURCE_MATCH",
            "independent_source_count": None,
            "candidates": [],
            "request_goal_selection": projection.as_dict(),
            "reason": projection.reason,
            "trace": {
                "calls": {"FullConstellation.ask": 0},
                "candidate_selection": "abstained: raw request target projection held",
                "selector_query": "",
            },
        }

    from .multigrain_adapter import retrieve_multigrain_candidates

    result = retrieve_multigrain_candidates(
        raw_request,
        constellation,
        candidate_query=projection.selector_query,
        source_router=source_router,
        limit=limit,
    )
    result["request_goal_selection"] = projection.as_dict()
    result["candidate_selection_mode"] = "full_constellation_core"
    if (result.get("resolution_verdict") == "UNKNOWN_NOT_PRESENT"
            and result.get("resolution_as_core") == []
            and result.get("resolution_as_facet_only") == result.get("query_terms")
            and result.get("query_terms") == [projection.selector_query]
            and result.get("resolution_missing") == []):
        # FullConstellation explicitly reports this anchor as known only as a
        # facet. Invert exact existing CrossStore links solely to find a
        # candidate owner; the source binder below requires the target and
        # candidate to be explicit local roles of the same Frame.
        tree = next((getattr(member, "tree", None)
                    for member in getattr(constellation, "members", ())
                    if getattr(member, "tree", None) is not None), None)
        rows, scan, reason = _exact_facet_owner_rows(
            tree, projection.selector_query, limit=limit,
        )
        result["candidate_selection_mode"] = "exact_source_facet_owner"
        result["candidate_selection_verdict"] = (
            "HOLD" if reason or len(rows) != 1 else "EXACT_FACET_OWNER_UNIQUE")
        result["candidates"] = rows
        result["facet_owner_scan"] = scan
        if reason:
            result.update(
                verdict="UNKNOWN_REQUEST_GOAL_SELECTION_HOLD",
                selected_candidate=None,
                source_identity_status="UNKNOWN_NO_SOURCE_MATCH",
                reason="exact CrossStore facet-owner scan held: " + reason,
            )
        elif len(rows) != 1:
            result.update(
                verdict="UNKNOWN_REQUEST_GOAL_SELECTION_HOLD",
                selected_candidate=None,
                source_identity_status="UNKNOWN_NO_SOURCE_MATCH",
                reason=("exact source facet has no indexed core owner" if not rows
                        else "exact source facet has multiple core owners"),
            )
        else:
            result.update(
                verdict="CANDIDATE_SOURCE_FACET_OWNER_MATCHED",
                selected_candidate=rows[0]["item"],
                source_identity_status="identity_unverified",
                independent_source_count=None,
                reason=("one exact CrossStore facet owner is a navigation hypothesis; "
                        "same-owner source Frame role checks are still required"),
            )
        trace = result.get("trace")
        if type(trace) is dict:
            calls = trace.get("calls")
            if type(calls) is dict:
                calls["CrossStore.exact_facet_owner_scan"] = 1
                calls["CrossStore.facet_links_visited"] = scan.get(
                    "visited_facet_links", 0)
            trace["candidate_selection"] = (
                "one exact source CrossStore facet owner; not a resolution vote"
                if len(rows) == 1 and not reason else
                "held: exact source facet owner is absent, ambiguous, or invalid")
    else:
        result["candidate_selection_verdict"] = (
            "FULL_CONSTELLATION_SELECTED" if result.get("selected_candidate")
            else "FULL_CONSTELLATION_ABSTAINED")
    return result


def bind_multigrain_sources(
    raw_question: str,
    documents: object,
    bot: object,
    navigation_root: object,
    snapshot: SourceRegistrySnapshot,
    navigation: object,
    semantic_view: object,
) -> SourceBindingResult:
    """Bind selected leaf proposals to original document sentence/clause spans.

    `source_label` is never read. Candidate text is accepted only when it is
    an exact key in the matched leaf and an exact substring of a parsed clause
    span in the corresponding original document.
    """
    if type(raw_question) is not str or type(documents) is not dict:
        return _hold("trusted raw question/documents have an invalid type")
    if type(navigation) is not dict or type(semantic_view) is not View:
        return _hold("adapter navigation or original semantic View is missing")
    if type(snapshot) is not SourceRegistrySnapshot:
        return _hold("source identity snapshot has an invalid type")
    if (type(semantic_view.clauses) is not tuple
            or any(type(clause) is not Clause for clause in semantic_view.clauses)
            or type(semantic_view.unread) is not tuple
            or any(type(item) is not Unread or type(item.span) is not Span
                   for item in semantic_view.unread)):
        return _hold("original semantic View has an invalid clause or unread shape")
    snapshot_sha256 = snapshot.sha256 if type(snapshot.sha256) is str else ""

    from .request_goal_route import is_request_utterance
    is_goal_request = is_request_utterance(raw_question)
    goal_projection = None
    selector_query = navigation.get("selector_query")
    if is_goal_request:
        from .compositional_goal import derive_request_selection_projection

        projection = derive_request_selection_projection(raw_question)
        goal_projection = projection
        if projection.status != "READY":
            return _hold("raw request target projection holds: " + projection.reason,
                         registry_sha256=snapshot_sha256)
        if navigation.get("request_goal_selection") != projection.as_dict():
            return _hold("adapter Goal target projection differs from raw-request rederivation",
                         registry_sha256=snapshot_sha256)
        if (selector_query != projection.selector_query
                or navigation.get("selector_query_origin") != "explicit_candidate_query"
                or navigation.get("query_terms") != list(projection.query_terms)):
            return _hold("adapter selector query/terms differ from the bound raw Goal target",
                         registry_sha256=snapshot_sha256)
        selection_mode = navigation.get("candidate_selection_mode")
        if selection_mode not in ("full_constellation_core",
                                  "exact_source_facet_owner"):
            return _hold("raw Goal candidate selection mode is outside the typed contract",
                         registry_sha256=snapshot_sha256)
    else:
        selection_mode = "full_constellation_core"
        if selector_query != raw_question:
            return _hold("ordinary QA selector query differs from its raw question",
                         registry_sha256=snapshot_sha256)
        if navigation.get("selector_query_origin") != "raw_question":
            return _hold("ordinary QA selector query origin is not the raw question",
                         registry_sha256=snapshot_sha256)
        if navigation.get("request_goal_selection") is not None:
            return _hold("ordinary QA navigation carries an unexpected Goal projection",
                         registry_sha256=snapshot_sha256)

    candidate = navigation.get("selected_candidate")
    if navigation.get("raw_question") != raw_question:
        return _hold("adapter raw-question envelope differs from the trusted request",
                     registry_sha256=snapshot_sha256)
    if selection_mode == "exact_source_facet_owner":
        if (not is_goal_request
                or getattr(goal_projection, "status", None) != "READY"):
            return _hold("facet-owner candidates are licensed only by a READY raw Goal",
                         registry_sha256=snapshot_sha256)
        if (navigation.get("verdict") != "CANDIDATE_SOURCE_FACET_OWNER_MATCHED"
                or navigation.get("candidate_selection_verdict") != "EXACT_FACET_OWNER_UNIQUE"
                or navigation.get("resolution_verdict") != "UNKNOWN_NOT_PRESENT"
                or navigation.get("resolution_item") is not None
                or navigation.get("resolution_as_core") != []
                or navigation.get("resolution_as_facet_only") != [selector_query]
                or navigation.get("resolution_missing") != []):
            return _hold("exact facet-owner candidate does not preserve FullConstellation abstention",
                         registry_sha256=snapshot_sha256)
    else:
        if navigation.get("verdict") != "CANDIDATE_SOURCE_LEAF_MATCHED":
            return _hold("adapter did not find a source-leaf candidate",
                         registry_sha256=snapshot_sha256)
        if navigation.get("resolution_verdict") not in ("ANSWER", "ANSWER_BY_COARSENING"):
            return _hold("existing FullConstellation selector abstained or was ambiguous",
                         registry_sha256=snapshot_sha256)
    if type(candidate) is not str or not candidate:
        return _hold("adapter selected-candidate field is empty or invalid",
                     registry_sha256=snapshot_sha256)
    if selection_mode != "exact_source_facet_owner" and navigation.get("resolution_item") != candidate:
        return _hold("adapter selected item differs from the resolution item",
                     candidate=candidate, registry_sha256=snapshot_sha256)
    if (navigation.get("source_identity_status") != "identity_unverified"
            or navigation.get("independent_source_count") is not None):
        return _hold("adapter candidate identity metadata is outside the limited contract",
                     candidate=candidate, registry_sha256=snapshot_sha256)

    current, reason = _registry_is_current(bot, navigation_root, snapshot)
    if not current:
        return _hold(reason, candidate=candidate, registry_sha256=snapshot_sha256)
    originals = getattr(bot, "original_texts", None)
    if type(originals) is not dict or documents != originals:
        return _hold("binding documents differ from the Bot original-document mapping",
                     candidate=candidate, registry_sha256=snapshot_sha256)
    for unread in semantic_view.unread:
        unread_source = unread.span.source
        unread_raw = originals.get(unread_source)
        if (type(unread_source) is not str or type(unread_raw) is not str
                or not _span_valid(unread_raw, unread.span)):
            return _hold("original semantic View contains an invalid unread source span",
                         candidate=candidate, registry_sha256=snapshot_sha256)
    if (type(semantic_view.sources) is not dict
            or set(semantic_view.sources) != set(originals)
            or any(type(semantic_view.sources.get(source_id)) is not str
                   or semantic_view.sources.get(source_id) != raw
                   for source_id, raw in originals.items())):
        return _hold("semantic View source bytes differ from Bot original documents",
                     candidate=candidate, registry_sha256=snapshot_sha256)

    rows = navigation.get("candidates")
    if type(rows) is not list:
        return _hold("adapter candidate collection is invalid", candidate=candidate,
                     registry_sha256=snapshot_sha256)
    matching_rows = [row for row in rows
                     if type(row) is dict and row.get("item") == candidate]
    if len(matching_rows) != 1:
        return _hold("selected candidate does not identify exactly one adapter row",
                     candidate=candidate, registry_sha256=snapshot_sha256)
    row = matching_rows[0]
    if (row.get("source_identity_status") != "identity_unverified"
            or row.get("independent_source_count") is not None
            or row.get("source_references_truncated") is not False):
        return _hold("candidate source list is incomplete or claims unlicensed identity",
                     candidate=candidate, registry_sha256=snapshot_sha256)
    refs = row.get("sources")
    ref_count = row.get("source_reference_count")
    leaf_count = row.get("source_leaf_match_count")
    if (type(refs) is not list or type(ref_count) is not int or type(leaf_count) is not int
            or ref_count != len(refs) or leaf_count < 1):
        return _hold("adapter source reference counts are invalid or incomplete",
                     candidate=candidate, registry_sha256=snapshot_sha256)

    facet_mode = selection_mode == "exact_source_facet_owner"
    if facet_mode:
        candidate_limit = navigation.get("candidate_limit")
        if (type(candidate_limit) is not int or candidate_limit < 1
                or row.get("selection_method") !=
                "exact_unverified_crossstore_facet_owner"):
            return _hold("facet-owner candidate metadata is outside the bounded contract",
                         candidate=candidate, registry_sha256=snapshot_sha256)
        expected_rows, _scan, facet_reason = _exact_facet_owner_rows(
            navigation_root, selector_query, limit=candidate_limit,
        )
        if facet_reason:
            return _hold("consumer facet-owner rederivation held: " + facet_reason,
                         candidate=candidate, registry_sha256=snapshot_sha256)
        if (len(expected_rows) != 1 or expected_rows[0]["item"] != candidate
                or expected_rows[0] != row):
            return _hold("facet-owner rows differ from trusted CrossStore rederivation",
                         candidate=candidate, registry_sha256=snapshot_sha256)

    leaves, reason = _leaf_nodes(navigation_root)
    if reason:
        return _hold(reason, candidate=candidate, registry_sha256=snapshot_sha256)
    registry = {entry.source_id: entry for entry in snapshot.records}
    refs_by_leaf: dict[str, tuple[str, ...]] = {}
    for ref in refs:
        if type(ref) is not dict:
            return _hold("adapter source reference is not a mapping", candidate=candidate,
                         registry_sha256=snapshot_sha256)
        leaf_id = ref.get("leaf")
        path = ref.get("path")
        if (type(leaf_id) is not str or type(path) is not list
                or not path or any(type(item) is not str for item in path)
                or path[-1] != leaf_id
                or ref.get("identity_status") != "identity_unverified"
                or ref.get("canonical_source_id") is not None):
            return _hold("adapter leaf path is malformed", candidate=candidate,
                         registry_sha256=snapshot_sha256)
        # Deliberately do not inspect ref['source_label'] for identity.
        identity = registry.get(leaf_id)
        node_record = leaves.get(leaf_id)
        if identity is None or node_record is None:
            return _hold("candidate leaf name does not map to an original document ID",
                         candidate=candidate, registry_sha256=snapshot_sha256)
        expected_path, node = node_record
        if tuple(path) != expected_path or identity.leaf_path != expected_path:
            return _hold("candidate path differs from the indexed original-source path",
                         candidate=candidate, registry_sha256=snapshot_sha256)
        store = getattr(node, "store", None)
        crosses = getattr(store, "crosses", None)
        if (not isinstance(crosses, Mapping) or candidate not in crosses
                or _crosses_sha256(store) != identity.leaf_store_sha256):
            return _hold("candidate core is absent from the unchanged indexed source leaf",
                         candidate=candidate, registry_sha256=snapshot_sha256)
        if facet_mode:
            facets = crosses.get(candidate)
            labels = getattr(store, "source_labels", None)
            witness = ref.get("facet_link")
            expected_witness = ({
                "core": candidate,
                "facet": selector_query,
                "count": facets.get(selector_query),
                "role": "unverified_crossstore_link",
            } if type(facets) is dict and type(labels) in (set, frozenset)
                 and selector_query in facets and selector_query not in labels else None)
            if expected_witness is None or witness != expected_witness:
                return _hold("facet-owner reference lacks its exact current core→facet link",
                             candidate=candidate, registry_sha256=snapshot_sha256)
        previous = refs_by_leaf.get(leaf_id)
        if previous is not None and previous != expected_path:
            return _hold("same original leaf has inconsistent paths", candidate=candidate,
                         registry_sha256=snapshot_sha256)
        refs_by_leaf[leaf_id] = expected_path
    if len(refs_by_leaf) != leaf_count:
        return _hold("adapter leaf count differs from unique original document IDs",
                     candidate=candidate, registry_sha256=snapshot_sha256)
    expected_leaf_ids = set()
    for leaf_id, (_path, node) in leaves.items():
        store = getattr(node, "store", None)
        crosses = getattr(store, "crosses", None)
        if not isinstance(crosses, Mapping) or candidate not in crosses:
            continue
        if facet_mode:
            facets = crosses.get(candidate)
            labels = getattr(store, "source_labels", None)
            if (type(facets) is dict and selector_query in facets
                    and type(labels) in (set, frozenset)
                    and selector_query not in labels):
                expected_leaf_ids.add(leaf_id)
        else:
            expected_leaf_ids.add(leaf_id)
    if not expected_leaf_ids or set(refs_by_leaf) != expected_leaf_ids:
        return _hold("adapter references do not cover every original leaf containing the selected core",
                     candidate=candidate, registry_sha256=snapshot_sha256)

    selections: list[SelectedSourceSpan] = []
    selected_views: list[View] = []
    originals_by_id = {entry.source_id: entry for entry in snapshot.records}
    for source_id, path in sorted(refs_by_leaf.items()):
        raw = originals.get(source_id)
        identity = originals_by_id[source_id]
        if type(raw) is not str or _sha256(raw) != identity.original_sha256:
            return _hold("original source changed after leaf selection", candidate=candidate,
                         registry_sha256=snapshot_sha256)
        matching: dict[tuple[int, int, str], list[Clause]] = {}
        spans_by_sentence: dict[tuple[int, int, str], set[tuple[int, int]]] = {}
        goal_proofs: dict[str, _LocalGoalRoleProof] = {}
        if is_goal_request:
            from .frame_evidence import read_frame_evidence

            try:
                source_evidence = read_frame_evidence(source_id, raw)
            except (TypeError, ValueError) as exc:
                return _hold("source FrameEvidence could not be rederived: " + str(exc),
                             candidate=candidate, registry_sha256=snapshot_sha256)
            for clause in semantic_view.clauses:
                span = getattr(clause, "span", None)
                if (type(clause) is not Clause or not _span_valid(raw, span)
                        or span.source != source_id):
                    continue
                proof, _proof_reason = _local_goal_role_proof(
                    raw, source_id, candidate, goal_projection.selector_query,
                    clause, source_evidence,
                )
                if proof is None:
                    continue
                candidate_start, candidate_end = proof.candidate_span
                if (not span.start <= candidate_start < candidate_end <= span.end
                        or raw[candidate_start:candidate_end] != candidate):
                    continue
                key = (span.start, span.end, span.text)
                matching.setdefault(key, []).append(clause)
                spans_by_sentence.setdefault(key, set()).add(proof.candidate_span)
                goal_proofs[clause.id] = proof
        else:
            for clause in semantic_view.clauses:
                span = getattr(clause, "span", None)
                if (type(clause) is not Clause or not _span_valid(raw, span)
                        or span.source != source_id):
                    continue
                occurrences = _occurrences(raw, span.start, span.end, candidate)
                if not occurrences:
                    continue
                key = (span.start, span.end, span.text)
                matching.setdefault(key, []).append(clause)
                spans_by_sentence.setdefault(key, set()).update(occurrences)
        if not matching:
            reason = ("candidate and raw Goal target do not bind as permitted explicit roles "
                      "of one source Frame" if is_goal_request else
                      "selected candidate has no exact occurrence in a source-reader Clause span")
            return _hold(reason, candidate=candidate, registry_sha256=snapshot_sha256)

        for (start, end, sentence_text), clauses in sorted(matching.items()):
            relevant_unread = tuple(
                unread for unread in semantic_view.unread
                if getattr(getattr(unread, "span", None), "source", None) == source_id
                and _overlap(start, end, unread.span)
            )
            if relevant_unread:
                return _hold("candidate sentence overlaps unread source content",
                             candidate=candidate, registry_sha256=snapshot_sha256)
            clauses = sorted({clause.id: clause for clause in clauses}.values(),
                             key=lambda clause: (clause.predicate_span.start, clause.id))
            if is_goal_request and len(clauses) != 1:
                return _hold("Goal target anchor is shared by multiple source Frames in one sentence",
                             candidate=candidate, registry_sha256=snapshot_sha256)
            if any(clause.unsupported or clause.modality in ("quote", "hedge", "instruction")
                   for clause in clauses):
                return _hold("candidate sentence contains an unsupported or nonasserted clause",
                             candidate=candidate, registry_sha256=snapshot_sha256)
            selected_views.append(View(
                sources={source_id: raw},
                clauses=tuple(clauses),
                unread=relevant_unread,
                ingest_ms=semantic_view.ingest_ms,
            ))
            proof = goal_proofs.get(clauses[0].id) if is_goal_request else None
            selections.append(SelectedSourceSpan(
                source_id=source_id,
                original_sha256=identity.original_sha256,
                leaf_id=source_id,
                leaf_path=path,
                candidate=candidate,
                candidate_spans=tuple(sorted(spans_by_sentence[(start, end, sentence_text)])),
                sentence_start=start,
                sentence_end=end,
                sentence_text=sentence_text,
                clause_ids=tuple(clause.id for clause in clauses),
                predicates=tuple(clause.predicate for clause in clauses),
                request_target_anchor=(goal_projection.selector_query
                                       if proof is not None else ""),
                target_role="patient" if proof is not None else "",
                target_argument_span=(proof.target_span if proof is not None else None),
                target_case_particle_span=(proof.target_case_span
                                           if proof is not None else None),
                candidate_role=(proof.candidate_role if proof is not None else ""),
                candidate_argument_span=(proof.candidate_span if proof is not None else None),
                source_frame_id=(proof.source_frame_id if proof is not None else ""),
                source_clause_id=(proof.source_clause_id if proof is not None else ""),
                source_assertion_status=("UNCLASSIFIED" if proof is not None else ""),
            ))
    if not selections:
        return _hold("candidate did not bind to an original sentence span", candidate=candidate,
                     registry_sha256=snapshot_sha256)
    frozen = tuple(sorted(selections, key=lambda item: (
        item.source_id, item.sentence_start, item.sentence_end)))
    return SourceBindingResult(
        "BOUND", "candidate leaf IDs and exact original Clause spans were rederived",
        candidate, snapshot_sha256, frozen, tuple(selected_views),
    )


def _navigation_signature(navigation: dict) -> tuple:
    candidate = navigation.get("selected_candidate")
    rows = navigation.get("candidates")
    projection = navigation.get("request_goal_selection")
    projection_json = (json.dumps(projection, ensure_ascii=False, sort_keys=True,
                                  separators=(",", ":"))
                       if type(projection) is dict else None)
    selected_rows = ([row for row in rows if type(row) is dict and row.get("item") == candidate]
                     if type(rows) is list else [])
    refs = []
    if len(selected_rows) == 1 and type(selected_rows[0].get("sources")) is list:
        for ref in selected_rows[0]["sources"]:
            if type(ref) is dict:
                facet_link = ref.get("facet_link")
                facet_signature = (
                    facet_link.get("core"), facet_link.get("facet"),
                    facet_link.get("count"), facet_link.get("role"),
                ) if type(facet_link) is dict else None
                refs.append((ref.get("leaf"), tuple(ref.get("path", ()))
                             if type(ref.get("path")) is list else (),
                             facet_signature))
    return (navigation.get("raw_question"), navigation.get("selector_query"),
            navigation.get("selector_query_origin"), projection_json,
            tuple(navigation.get("query_terms", ()))
            if type(navigation.get("query_terms")) in (list, tuple) else (),
            navigation.get("candidate_selection_mode"),
            navigation.get("candidate_selection_verdict"),
            navigation.get("candidate_limit"),
            navigation.get("verdict"),
            navigation.get("resolution_verdict"), navigation.get("resolution_item"),
            candidate, tuple(sorted(set(refs))))


def route_goal_from_bound_source(
    raw_request: str,
    documents: object,
    *,
    bot: object,
    navigation_root: object,
    snapshot: SourceRegistrySnapshot,
    constellation: object,
    initial_navigation: dict,
    initial_binding: SourceBindingResult,
    semantic_view: View,
) -> dict:
    """Use one uniquely rebound sentence, then rederive selection after C.

    `route_request_goal` still performs its own producer/consumer pass over
    the selected sentence. This wrapper verifies before and after that the
    sentence came from the trusted full-document mapping and unchanged leaf.
    """
    from .request_goal_route import route_request_goal

    def hold(reason: str, binding: SourceBindingResult | None = None) -> dict:
        result = {
            "kind": "unknown", "verdict": "UNKNOWN_REQUEST_GOAL_HOLD", "status": "HOLD",
            "text": "", "candidate_text": None, "reason": reason,
            "verified": False, "candidate_projection_verified": False,
            "full_goal_verified": False, "full_semantic_equivalent": None,
            "goal_satisfied": None, "success_count_eligible": False,
            "adoption_eligible": False, "world_assigned": False,
            "independent_source_count": 0, "trace": [],
        }
        if binding is not None:
            result["source_binding"] = binding.as_dict()
        return result

    if (type(documents) is not dict or type(initial_binding) is not SourceBindingResult
            or initial_binding.status != "BOUND"
            or type(initial_navigation) is not dict or type(semantic_view) is not View
            or type(snapshot) is not SourceRegistrySnapshot):
        return hold("no exact original-source sentence was bound", initial_binding)
    if (len(initial_binding.selections) != 1
            or len(initial_binding.selections[0].clause_ids) != 1
            or len(initial_binding.views) != 1
            or initial_binding.views[0].unread):
        return hold("Goal realization requires one fully read source event sentence", initial_binding)

    selection = initial_binding.selections[0]
    original = documents.get(selection.source_id)
    if (type(original) is not str
            or _sha256(original) != selection.original_sha256
            or original[selection.sentence_start:selection.sentence_end] != selection.sentence_text):
        return hold("selected sentence no longer matches the exact original document span", initial_binding)

    # Raw input and the full original document remain separate. The bounded
    # sentence slice is passed only after the navigation leaf/span join.
    generated = route_request_goal(raw_request, {selection.source_id: selection.sentence_text})

    # Consumer-side source rederivation: rerun candidate selection and span
    # binding from the same trusted raw request/documents after evaluation.
    after_navigation = retrieve_goal_candidate_navigation(
        raw_request, constellation, source_router=bot, limit=8,
    )
    if _navigation_signature(after_navigation) != _navigation_signature(initial_navigation):
        return hold("multigrain candidate selection changed during Goal evaluation", initial_binding)
    after_binding = bind_multigrain_sources(
        raw_request, documents, bot, navigation_root, snapshot,
        after_navigation, semantic_view,
    )
    if (after_binding.status != "BOUND"
            or after_binding.selections != initial_binding.selections):
        return hold("original source identity/span did not survive consumer rederivation",
                    after_binding)
    generated["source_binding"] = after_binding.as_dict()
    generated["source_binding"]["rederived_after_candidate"] = True
    generated["goal_route"] = "source_bound_candidate"
    generated["source_binding_success"] = True
    generated["source_binding_status"] = "BOUND"
    generated["source_binding_reason"] = after_binding.reason
    for source in generated.get("sources", []):
        if type(source) is dict and source.get("source") == selection.source_id:
            source["original_document_sha256"] = selection.original_sha256
            source["original_sentence_span"] = {
                "start": selection.sentence_start,
                "end": selection.sentence_end,
            }
    for evidence in generated.get("evidence", []):
        if type(evidence) is dict and evidence.get("source") == selection.source_id:
            evidence["original_document_sha256"] = selection.original_sha256
            evidence["original_sentence_span"] = {
                "start": selection.sentence_start,
                "end": selection.sentence_end,
            }
    return generated


def bind_request_event_set(
    raw_request: str,
    documents: object,
) -> SourceEventSetBinding:
    """Re-derive a raw all-events request and bind every literal target mention.

    ``BOUND`` means every occurrence of the request's explicit target anchor in
    the one original document is attached as a local explicit patient to a
    positive, unquoted, aligned source Frame and semantic Clause. Other roles,
    including topic-like ``に`` attachments, remain held. It does not
    prove that all semantically related events were explicitly named, that a
    source proposition is true, or that any candidate output satisfies the
    request. Those fields remain unknown for a downstream consumer.
    """
    from .compositional_goal import (
        RequestSelectionProjection, derive_request_event_set_projection,
    )
    from .content_ir import Span as GoalSpan
    from .frame_evidence import (
        ArgumentEvidence, ClauseEvidence, FrameEvidenceDocument, FrameSnapshot,
        SourceSpan, read_frame_evidence,
    )
    from .semantic_reader import document_view

    raw_sha = _sha256(raw_request)

    def valid_request_span(span: object) -> bool:
        return (type(span) is GoalSpan and span.source == "request"
                and span.sha256 == raw_sha
                and type(span.start) is int and type(span.end) is int
                and 0 <= span.start < span.end <= len(raw_request))

    def hold(reason: str, *, projection: object = None, source_id: str = "",
             source_sha: str = "", anchor: str = "", count: int = 0) -> SourceEventSetBinding:
        projection_record = (projection.as_dict()
                             if type(projection) is RequestSelectionProjection else None)
        sentence_count = getattr(projection, "required_sentence_count", None)
        return SourceEventSetBinding(
            "HOLD", reason, raw_sha or "", projection_record, source_id,
            source_sha, anchor, required_sentence_count=sentence_count,
            explicit_anchor_occurrence_count=count,
        )

    if type(raw_request) is not str or raw_sha is None:
        return hold("trusted raw request must be valid exact str")
    projection = derive_request_event_set_projection(raw_request)
    if (projection.status != "READY"
            or projection.raw_sha256 != raw_sha
            or projection.action != "summarize_events"
            or projection.selection_scope != "all_matching_events"
            or projection.target_kind != "source_event"
            or type(projection.selector_query) is not str
            or not projection.selector_query
            or projection.target_span is None
            or not valid_request_span(projection.target_span)
            or raw_request[projection.target_span.start:projection.target_span.end]
                != projection.target
            or projection.event_scope_span is None
            or not valid_request_span(projection.event_scope_span)
            or raw_request[projection.event_scope_span.start:projection.event_scope_span.end]
                not in ("すべて", "全て", "全部")
            or projection.required_sentence_count != 2):
        return hold("raw event-set Goal projection is not READY", projection=projection,
                    anchor=getattr(projection, "selector_query", ""))
    if type(documents) is not dict or len(documents) != 1:
        return hold("event-set binding accepts exactly one original source document",
                    projection=projection, anchor=projection.selector_query)
    source_id, raw_source = next(iter(documents.items()))
    source_sha = _sha256(raw_source)
    if (type(source_id) is not str or not source_id
            or type(raw_source) is not str or source_sha is None):
        return hold("original source id/text must be valid exact strings",
                    projection=projection, source_id=(source_id if type(source_id) is str else ""),
                    anchor=projection.selector_query)

    anchor = projection.selector_query
    try:
        source_evidence = read_frame_evidence(source_id, raw_source)
        semantic_view = document_view({source_id: raw_source})
    except (TypeError, ValueError, UnicodeEncodeError) as exc:
        return hold("source evidence reader rejected the exact source input: " + type(exc).__name__,
                    projection=projection, source_id=source_id, source_sha=source_sha,
                    anchor=anchor)
    if type(source_evidence) is not FrameEvidenceDocument:
        return hold("source FrameEvidenceDocument is not typed", projection=projection,
                    source_id=source_id, source_sha=source_sha, anchor=anchor)
    if (source_evidence.source_id != source_id
            or source_evidence.source_text != raw_source
            or source_evidence.source_sha256 != source_sha
            or source_evidence.alignment_status != "ALIGNED_BY_READER_ORDER"
            or source_evidence.reader_order_alignment_status != "ALIGNED_BY_READER_ORDER"
            or not source_evidence.token_positions_complete
            or source_evidence.source_coverage_status not in ("EXACT", "WHITESPACE_ONLY")
            or source_evidence.unmatched_frames
            or any(gap.classification != "WHITESPACE"
                   for gap in source_evidence.source_gaps)):
        return hold("source FrameEvidence identity, alignment, or coverage is unresolved",
                    projection=projection, source_id=source_id, source_sha=source_sha,
                    anchor=anchor)
    if (type(semantic_view) is not View
            or type(semantic_view.clauses) is not tuple
            or any(type(clause) is not Clause for clause in semantic_view.clauses)
            or type(semantic_view.unread) is not tuple
            or any(type(item) is not Unread or type(item.span) is not Span
                   for item in semantic_view.unread)):
        return hold("original semantic View has an invalid clause or unread shape",
                    projection=projection, source_id=source_id, source_sha=source_sha,
                    anchor=anchor)

    occurrences = _occurrences(raw_source, 0, len(raw_source), anchor)
    if not occurrences:
        return hold("target anchor does not occur in the original source",
                    projection=projection, source_id=source_id, source_sha=source_sha,
                    anchor=anchor)
    if len(occurrences) > MAX_BOUND_SOURCE_EVENTS * 4:
        return hold("target anchor occurrence count exceeds the local binding bound",
                    projection=projection, source_id=source_id, source_sha=source_sha,
                    anchor=anchor, count=len(occurrences))

    occurrence_owners: dict[tuple[int, int], tuple[ClauseEvidence, ArgumentEvidence]] = {}
    for occurrence in occurrences:
        start, end = occurrence
        owners = []
        for clause in source_evidence.clauses:
            if type(clause) is not ClauseEvidence:
                continue
            for argument in clause.arguments:
                span = getattr(argument, "span", None)
                if (type(argument) is ArgumentEvidence and type(span) is SourceSpan
                        and type(span.start) is int and type(span.end) is int
                        and (span.start, span.end) == occurrence):
                    owners.append((clause, argument))
        if len(owners) != 1:
            return hold("literal target occurrence lacks one unique FrameEvidence role owner",
                        projection=projection, source_id=source_id, source_sha=source_sha,
                        anchor=anchor, count=len(occurrences))
        if (type(owners[0][0].frame_id) is not str or not owners[0][0].frame_id
                or type(owners[0][0].clause_id) is not str or not owners[0][0].clause_id):
            return hold("target occurrence owner IDs are not stable strings",
                        projection=projection, source_id=source_id, source_sha=source_sha,
                        anchor=anchor, count=len(occurrences))
        occurrence_owners[occurrence] = owners[0]

    by_frame: dict[str, list[tuple[int, int]]] = {}
    for occurrence, (owner, argument) in occurrence_owners.items():
        argument_span = argument.span
        particle_span = argument.particle_span
        if (argument.value != anchor or argument.role != "patient"
                or type(argument_span) is not SourceSpan
                or type(particle_span) is not SourceSpan
                or owner.frame_id != argument.owner_frame_id
                or argument.source_frame_id != owner.frame_id
                or not _valid_frame_argument(raw_source, argument, role=argument.role,
                                             value=anchor, frame_id=owner.frame_id,
                                             source_clause=owner)):
            return hold("target occurrence is not a permitted explicit local patient role",
                        projection=projection, source_id=source_id, source_sha=source_sha,
                        anchor=anchor, count=len(occurrences))
        by_frame.setdefault(owner.frame_id, []).append(occurrence)

    semantic_by_predicate: dict[tuple[int, int], list[Clause]] = {}
    for clause in semantic_view.clauses:
        predicate_span = clause.predicate_span
        if not _span_valid(raw_source, predicate_span) or predicate_span.source != source_id:
            continue
        semantic_by_predicate.setdefault((predicate_span.start, predicate_span.end), []).append(clause)

    events: list[BoundSourceEvent] = []
    seen_evidence_clause_ids: set[str] = set()
    seen_semantic_clause_ids: set[str] = set()
    seen_frame_ids: set[str] = set()
    for frame_id, frame_occurrences in by_frame.items():
        owner_rows = {
            id(owner): owner for occurrence in frame_occurrences
            for owner, _argument in (occurrence_owners[occurrence],)
        }
        if len(owner_rows) != 1:
            return hold("one source Frame ID maps to multiple FrameEvidence records",
                        projection=projection, source_id=source_id, source_sha=source_sha,
                        anchor=anchor, count=len(occurrences))
        owner = next(iter(owner_rows.values()))
        frame = owner.frame
        if (type(owner) is not ClauseEvidence or type(frame) is not FrameSnapshot
                or type(owner.frame_id) is not str or not owner.frame_id
                or type(owner.clause_id) is not str or not owner.clause_id
                or owner.frame_id != frame_id or owner.clause_id in seen_evidence_clause_ids
                or frame_id in seen_frame_ids
                or frame.predicate != owner.predicate
                or owner.alignment_status != "ALIGNED_BY_READER_ORDER"
                or owner.quote_status != "UNQUOTED"
                or owner.assertion_status != "UNCLASSIFIED"
                or owner.scope_status != "KNOWN" or owner.polarity != "POSITIVE"
                or owner.local_scope_status != "KNOWN"
                or owner.local_polarity != "POSITIVE"
                or owner.negation_spans or frame.negated or frame.ambiguous or frame.inferred):
            return hold("target event has unresolved Frame, quote, scope, or polarity evidence",
                        projection=projection, source_id=source_id, source_sha=source_sha,
                        anchor=anchor, count=len(occurrences))
        predicate_span = owner.predicate_span
        if (type(predicate_span) is not SourceSpan
                or not 0 <= predicate_span.start < predicate_span.end <= len(raw_source)
                or raw_source[predicate_span.start:predicate_span.end] != predicate_span.text):
            return hold("target event predicate has no exact source span",
                        projection=projection, source_id=source_id, source_sha=source_sha,
                        anchor=anchor, count=len(occurrences))
        semantic_matches = semantic_by_predicate.get((predicate_span.start, predicate_span.end), [])
        if len(semantic_matches) != 1:
            return hold("target event predicate does not identify one semantic Clause",
                        projection=projection, source_id=source_id, source_sha=source_sha,
                        anchor=anchor, count=len(occurrences))
        semantic_clause = semantic_matches[0]
        clause_span = semantic_clause.span
        if (semantic_clause.id in seen_semantic_clause_ids
                or semantic_clause.predicate != owner.predicate
                or semantic_clause.polarity != "+"
                or semantic_clause.modality != "assert"
                or semantic_clause.conditions or semantic_clause.exceptions
                or semantic_clause.unsupported
                or not _span_valid(raw_source, clause_span)
                or clause_span.source != source_id
                or not clause_span.start <= predicate_span.start < predicate_span.end <= clause_span.end):
            return hold("target event semantic Clause is conditional, unsupported, or misaligned",
                        projection=projection, source_id=source_id, source_sha=source_sha,
                        anchor=anchor, count=len(occurrences))
        if any(_overlap(clause_span.start, clause_span.end, item.span)
               for item in semantic_view.unread):
            return hold("target event Clause overlaps semantic-reader unread material",
                        projection=projection, source_id=source_id, source_sha=source_sha,
                        anchor=anchor, count=len(occurrences))

        role_rows: list[SourceEventRoleEvidence] = []
        for role_name in ("agent", "patient", "recipient"):
            role_value = getattr(frame, role_name)
            if not role_value:
                continue
            role_args = [argument for argument in owner.arguments
                         if type(argument) is ArgumentEvidence
                         and argument.role == role_name and argument.value == role_value]
            if (len(role_args) != 1
                    or not _valid_frame_argument(raw_source, role_args[0],
                                                 role=role_name, value=role_value,
                                                 frame_id=owner.frame_id,
                                                 source_clause=owner)):
                return hold("target event has a non-local or non-unique Frame role",
                            projection=projection, source_id=source_id,
                            source_sha=source_sha, anchor=anchor,
                            count=len(occurrences))
            argument = role_args[0]
            argument_span = argument.span
            particle_span = argument.particle_span
            assert argument_span is not None and particle_span is not None
            if (not (clause_span.start <= argument_span.start < argument_span.end
                            <= particle_span.start < particle_span.end <= clause_span.end)):
                return hold("target event role span escapes its semantic Clause",
                            projection=projection, source_id=source_id,
                            source_sha=source_sha, anchor=anchor,
                            count=len(occurrences))
            semantic_roles = [role for role in semantic_clause.roles
                              if role.name == role_name and role.term == role_value
                              and _span_valid(raw_source, role.span)
                              and role.span.source == source_id
                              and (role.span.start, role.span.end)
                                  == (argument_span.start, argument_span.end)]
            if len(semantic_roles) != 1:
                return hold("semantic Clause does not preserve one exact local role span",
                            projection=projection, source_id=source_id,
                            source_sha=source_sha, anchor=anchor,
                            count=len(occurrences))
            role_rows.append(SourceEventRoleEvidence(
                role_name, role_value,
                (argument_span.start, argument_span.end), argument.case_particle,
                (particle_span.start, particle_span.end),
            ))

        target_roles = tuple(role for role in role_rows if role.value == anchor)
        if not target_roles:
            return hold("target Frame role is absent from its revalidated role rows",
                        projection=projection, source_id=source_id,
                        source_sha=source_sha, anchor=anchor,
                        count=len(occurrences))
        events.append(BoundSourceEvent(
            source_id=source_id,
            source_sha256=source_sha,
            frame_evidence_clause_id=owner.clause_id,
            frame_id=owner.frame_id,
            semantic_clause_id=semantic_clause.id,
            predicate=owner.predicate,
            predicate_span=(predicate_span.start, predicate_span.end),
            clause_span=(clause_span.start, clause_span.end),
            clause_text=clause_span.text,
            target_roles=target_roles,
            roles=tuple(role_rows),
            assertion_status=owner.assertion_status,
        ))
        seen_evidence_clause_ids.add(owner.clause_id)
        seen_semantic_clause_ids.add(semantic_clause.id)
        seen_frame_ids.add(frame_id)

    if len(events) < 2:
        return hold("all-event selection found fewer than two distinct explicit source clauses",
                    projection=projection, source_id=source_id, source_sha=source_sha,
                    anchor=anchor, count=len(occurrences))
    if len(events) > MAX_BOUND_SOURCE_EVENTS:
        return hold("explicit source event set exceeds the local bound",
                    projection=projection, source_id=source_id, source_sha=source_sha,
                    anchor=anchor, count=len(occurrences))
    events.sort(key=lambda event: (event.clause_span[0], event.predicate_span[0], event.frame_id))
    if any(left.clause_span[1] > right.clause_span[0]
           for left, right in zip(events, events[1:])):
        return hold("source event clauses overlap; source order is unresolved",
                    projection=projection, source_id=source_id, source_sha=source_sha,
                    anchor=anchor, count=len(occurrences))

    # Every literal occurrence must have exactly one local owner. Mapping each
    # occurrence by span above prevents the adapter from silently omitting or
    # duplicating one of the explicit source mentions.
    if len(occurrence_owners) != len(occurrences):
        return hold("not every literal target occurrence has a unique local owner",
                    projection=projection, source_id=source_id, source_sha=source_sha,
                    anchor=anchor, count=len(occurrences))
    return SourceEventSetBinding(
        "BOUND",
        "every literal target occurrence binds to an explicit local patient role",
        raw_sha,
        projection.as_dict(),
        source_id,
        source_sha,
        anchor,
        "all_explicit_local_mentions",
        projection.required_sentence_count,
        tuple(events),
        len(occurrences),
    )


__all__ = [
    "SourceIdentityRecord", "SourceRegistrySnapshot", "SelectedSourceSpan",
    "SourceBindingResult", "capture_source_registry", "bind_multigrain_sources",
    "route_goal_from_bound_source", "SourceEventRoleEvidence", "BoundSourceEvent",
    "SourceEventSetBinding", "bind_request_event_set",
]
