"""Source-leaf adapter for the existing multi-resolution constellation.

This module does not build another index. Candidate choice comes from
``FullConstellation.ask`` over its existing resolution members; the adapter
joins those candidates back to the already-built source/domain leaves and
keeps the hierarchy and surface-routing traces alongside the result.

Resolution members are structural views of one store. Their readings may be
used by the constellation's existing selection rule, but they are never
reported as independent source evidence. ``CrossStore.source_labels`` are
display labels, not canonical source identities, so this adapter keeps those
references explicitly unverified.
"""
from __future__ import annotations

from collections.abc import Mapping
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple


_SOURCE_IDENTITY_NOTE = (
    "CrossStore stores source_labels and source_meta by display label; "
    "its provenance records timestamps and sentence snippets, not a "
    "canonical source key or content hash."
)


def _as_labels(store: Any) -> List[Optional[str]]:
    labels = getattr(store, "source_labels", None) or ()
    clean = sorted({label for label in labels
                    if isinstance(label, str) and label})
    return clean or [None]


def _source_ref(leaf: str, path: Sequence[str], label: Optional[str]) -> Dict[str, Any]:
    return {
        "leaf": leaf,
        "domain_path": list(path[:-1]),
        "path": list(path),
        "source_label": label,
        "canonical_source_id": None,
        "identity_status": "identity_unverified",
        "identity_note": _SOURCE_IDENTITY_NOTE,
    }


def _walk_candidate_sources(
    root: Any,
    candidate_witnesses: Mapping[str, Sequence[Dict[str, Any]]],
    query_features: Mapping[Tuple[str, int], set],
    query_divisions: Sequence[str],
    limit: int,
) -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, int], Dict[str, int],
           List[Dict[str, Any]], int, int]:
    """Join selected cores to leaf stores by exact existing core identity.

    This is a provenance join, not candidate generation: candidates have
    already been read and selected by FullConstellation. A source occurrence
    is keyed by hierarchy path plus display label; labels shared by separate
    leaves are deliberately kept separate and remain identity_unverified.
    """
    from .resolution import grains, recut

    wanted = set(candidate_witnesses)
    wanted_divisions = set(query_divisions)
    matches: Dict[str, List[Dict[str, Any]]] = {item: [] for item in candidate_witnesses}
    leaf_counts: Dict[str, int] = {item: 0 for item in candidate_witnesses}
    reference_counts: Dict[str, int] = {item: 0 for item in candidate_witnesses}
    destinations: List[Dict[str, Any]] = []
    visited_nodes = 0
    visited_leaves = 0

    def walk(node: Any, parent_path: Tuple[str, ...]) -> None:
        nonlocal visited_nodes, visited_leaves
        if node is None:
            return
        visited_nodes += 1
        name = str(getattr(node, "name", ""))
        path = parent_path + ((name,) if name else ())
        children = getattr(node, "children", {}) or {}
        is_leaf = bool(getattr(node, "is_leaf", not children))
        if not is_leaf:
            for child_name in sorted(children, key=str):
                walk(children[child_name], path)
            return

        visited_leaves += 1
        store = getattr(node, "store", None)
        crosses = getattr(store, "crosses", {}) if store is not None else {}
        if not isinstance(crosses, Mapping):
            crosses = {}

        if name in wanted_divisions:
            for label in _as_labels(store):
                destinations.append(_source_ref(name, path, label))

        for item in wanted.intersection(crosses.keys()):
            cross = crosses[item]
            if not isinstance(cross, Mapping):
                continue
            labels = set(getattr(store, "source_labels", None) or ())
            full_terms = [item] + sorted(f for f in cross if f not in labels)
            grain_witnesses: List[Dict[str, Any]] = []
            for spec in candidate_witnesses[item]:
                grammar = spec["grammar"]
                size = spec["size"]
                depth = spec["depth"]
                local_terms = full_terms[:depth] if depth else full_terms
                local_features = {piece for term in local_terms
                                  for cut in recut(term, grammar)
                                  for piece in grains(cut, size)}
                overlap_count = len(query_features.get((grammar, size), set())
                                    .intersection(local_features))
                if overlap_count:
                    grain_witnesses.append({
                        "member": spec["member"],
                        "rung": spec["rung"],
                        "size": size,
                        "matched_feature_count": overlap_count,
                    })
            if not grain_witnesses:
                continue
            leaf_counts[item] += 1
            for label in _as_labels(store):
                reference_counts[item] += 1
                if len(matches[item]) < limit:
                    ref = _source_ref(name, path, label)
                    ref["grain_witnesses"] = grain_witnesses
                    matches[item].append(ref)

    walk(root, ())
    for item in matches:
        matches[item].sort(key=lambda row: (tuple(row["path"]), row["source_label"] or ""))
    destinations.sort(key=lambda row: (tuple(row["path"]), row["source_label"] or ""))
    return (matches, leaf_counts, reference_counts, destinations,
            visited_nodes, visited_leaves)


def _surface_route(raw_question: str, source_router: Any) -> Dict[str, Any]:
    if source_router is None:
        return {"verdict": "NOT_PROVIDED", "path": [], "trail": [],
                "used_for_candidate_selection": False}

    # Callers may hand in Bot or its Base. Both use the same existing Base
    # route; no fallback router is constructed here.
    base = getattr(source_router, "base", source_router)
    lower = getattr(base, "lower", None)
    if not callable(lower):
        return {"verdict": "UNKNOWN_ROUTER_API", "path": [], "trail": [],
                "used_for_candidate_selection": False}

    leaf = lower(raw_question)
    route = getattr(base, "last_route", {}) or {}
    route = dict(route) if isinstance(route, Mapping) else {}
    route["selected_leaf"] = leaf
    route["route_kind"] = ("surface_conduction" if
                           getattr(base, "routing_root", None) is not None
                           else "single_leaf_or_unbuilt")
    route["via_api"] = (["Base.lower", "conduct_tree.descend", "surface.route"]
                        if getattr(base, "routing_root", None) is not None
                        else ["Base.lower"])
    route["used_for_candidate_selection"] = False
    return route


def retrieve_multigrain_candidates(
    raw_question: str,
    constellation: Any,
    *,
    candidate_query: str | None = None,
    source_router: Any = None,
    limit: int = 8,
) -> Dict[str, Any]:
    """Return existing constellation candidates with source and grain traces.

    ``FullConstellation.ask`` receives the untouched question and remains the
    only candidate selector. Its existing consensus can use readings across
    resolution members; this adapter adds no votes or thresholds. Exact core
    membership and an overlapping configured grain in a source leaf are
    required before ``selected_candidate`` is exposed. The leaf label stays
    ``identity_unverified`` until a canonical source registry is connected.
    """
    started = time.perf_counter()
    if not isinstance(raw_question, str):
        return {"kind": "multigrain_candidates", "verdict": "UNKNOWN_INVALID_INPUT",
                "raw_question": None, "selected_candidate": None,
                "candidates": [], "grain_trace": [],
                "reason": "raw_question must be text"}
    if not raw_question.strip():
        return {"kind": "multigrain_candidates", "verdict": "UNKNOWN_EMPTY_QUERY",
                "raw_question": raw_question, "selected_candidate": None,
                "candidates": [], "grain_trace": [],
                "reason": "raw_question is empty"}
    if candidate_query is not None and type(candidate_query) is not str:
        return {"kind": "multigrain_candidates", "verdict": "UNKNOWN_INVALID_INPUT",
                "raw_question": raw_question, "selector_query": None,
                "selected_candidate": None, "candidates": [], "grain_trace": [],
                "reason": "candidate_query must be exact str when provided"}
    selector_query = raw_question if candidate_query is None else candidate_query
    if not selector_query.strip():
        return {"kind": "multigrain_candidates", "verdict": "UNKNOWN_EMPTY_QUERY",
                "raw_question": raw_question, "selector_query": selector_query,
                "selected_candidate": None, "candidates": [], "grain_trace": [],
                "reason": "candidate_query is empty"}
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        return {"kind": "multigrain_candidates", "verdict": "UNKNOWN_INVALID_INPUT",
                "raw_question": raw_question, "selector_query": selector_query,
                "selected_candidate": None,
                "candidates": [], "grain_trace": [],
                "reason": "limit must be a positive integer"}

    members = getattr(constellation, "members", None)
    ask = getattr(constellation, "ask", None)
    if not isinstance(members, list) or not callable(ask):
        return {"kind": "multigrain_candidates", "verdict": "UNKNOWN_NO_CONSTELLATION",
                "raw_question": raw_question, "selected_candidate": None,
                "candidates": [], "grain_trace": [],
                "reason": "expected an existing FullConstellation instance"}

    names = [getattr(member, "name", None) for member in members]
    if any(not isinstance(name, str) or not name for name in names) or len(set(names)) != len(names):
        return {"kind": "multigrain_candidates", "verdict": "UNKNOWN_INVALID_CONSTELLATION",
                "raw_question": raw_question, "selected_candidate": None,
                "candidates": [], "grain_trace": [],
                "reason": "resolution member names must be nonempty and unique"}

    # This is the existing end-to-end resolution selector. It also calls the
    # constellation hierarchy's gather API when a source tree is present.
    selected = ask(selector_query)
    readings = selected.get("readings", {})
    if not isinstance(readings, Mapping):
        readings = {}
    terms = selected.get("terms", ())
    if not isinstance(terms, (list, tuple)):
        terms = ()

    grouped: Dict[str, Dict[str, Any]] = {}
    candidate_witnesses: Dict[str, List[Dict[str, Any]]] = {}
    query_features: Dict[Tuple[str, int], set] = {}
    grain_trace: List[Dict[str, Any]] = []
    rung_vote_calls = 0
    for member in members:
        name = member.name
        setting = getattr(member, "setting", {}) or {}
        if not isinstance(setting, Mapping):
            setting = {}
        link_only = bool(setting.get("links_only"))
        member_reading = readings.get(name)
        rung_readings: Dict[str, Optional[str]] = {}
        ladder = getattr(member, "ladder", None)
        if not link_only and ladder is not None and terms:
            vote = getattr(ladder, "vote", None)
            if callable(vote):
                rung_readings = vote(terms)
                rung_vote_calls += 1

        grain_trace.append({
            "member": name,
            "rungs": [list(rung) for rung in setting.get("rungs", ())],
            "grammar": setting.get("grammar", "raw"),
            "member_reading": member_reading,
            "rung_readings": rung_readings,
            "role": "citation_listing" if link_only else "resolution_view",
            "used_by_existing_candidate_selection": not link_only,
            "participated_with_candidate": (not link_only and member_reading is not None),
            "independent_source_vote": False,
        })
        if link_only or not isinstance(member_reading, str) or not member_reading:
            continue
        row = grouped.setdefault(member_reading, {
            "item": member_reading,
            "resolution_views": [],
            "sources": [],
            "source_leaf_match_count": 0,
            "independent_source_count": None,
            "source_identity_status": "identity_unverified",
            "selected_by_existing_constellation": False,
        })
        row["resolution_views"].append(name)
        from .resolution import grains, recut
        for rung in setting.get("rungs", ()):
            if not isinstance(rung, (list, tuple)) or len(rung) != 2:
                continue
            rung_name, size = rung
            if rung_readings.get(rung_name) != member_reading:
                continue
            grammar = setting.get("grammar", "raw")
            feature_key = (grammar, size)
            if feature_key not in query_features:
                query_features[feature_key] = {
                    piece for term in terms
                    for cut in recut(term, grammar)
                    for piece in grains(cut, size)
                }
            candidate_witnesses.setdefault(member_reading, []).append({
                "member": name,
                "rung": rung_name,
                "size": size,
                "grammar": grammar,
                "depth": setting.get("depth"),
            })

    chosen_item = selected.get("item")
    tree = next((getattr(member, "tree", None) for member in members
                 if getattr(member, "tree", None) is not None), None)
    query_divisions = selected.get("divisions", ())
    if not isinstance(query_divisions, (list, tuple)):
        query_divisions = ()
    source_matches: Dict[str, List[Dict[str, Any]]] = {item: [] for item in grouped}
    source_leaf_counts: Dict[str, int] = {item: 0 for item in grouped}
    source_reference_counts: Dict[str, int] = {item: 0 for item in grouped}
    query_destinations: List[Dict[str, Any]] = []
    visited_nodes = visited_leaves = 0
    if tree is not None and (grouped or query_divisions):
        (source_matches, source_leaf_counts, source_reference_counts,
         query_destinations, visited_nodes, visited_leaves) = _walk_candidate_sources(
            tree, candidate_witnesses, query_features,
            [name for name in query_divisions if isinstance(name, str)], limit)

    for item, row in grouped.items():
        row["resolution_views"] = sorted(set(row["resolution_views"]))
        row["sources"] = source_matches.get(item, [])
        row["source_leaf_match_count"] = source_leaf_counts.get(item, 0)
        row["source_reference_count"] = source_reference_counts.get(item, 0)
        row["source_references_truncated"] = (
            source_reference_counts.get(item, 0) > len(row["sources"]))
        row["selected_by_existing_constellation"] = (
            item == chosen_item and selected.get("verdict") in
            ("ANSWER", "ANSWER_BY_COARSENING"))
        row["selection_used_resolution_views"] = True
        row["independent_source_count"] = None
        row["source_identity_status"] = (
            "identity_unverified" if row["sources"] else
            ("UNKNOWN_NO_SOURCE_MATCH" if tree is not None else "UNKNOWN_NO_HIERARCHY"))

    selected_sources = source_matches.get(chosen_item, []) if isinstance(chosen_item, str) else []
    has_selected_source = bool(selected_sources)
    has_any_source = any(source_matches.values())
    if selected.get("verdict") == "AMBIGUOUS":
        verdict = "AMBIGUOUS"
    elif selected.get("verdict", "").startswith("UNKNOWN"):
        verdict = selected.get("verdict")
    elif chosen_item and tree is None:
        verdict = "UNKNOWN_NO_HIERARCHY"
    elif chosen_item and not has_selected_source:
        verdict = "UNKNOWN_NO_SOURCE_MATCH"
    elif chosen_item:
        verdict = "CANDIDATE_SOURCE_LEAF_MATCHED"
    else:
        verdict = "UNKNOWN_NO_CANDIDATE"

    # The optional Base route remains an explanation of the user's raw request.
    # It does not receive or influence the separate selector projection.
    surface_route = _surface_route(raw_question, source_router)
    selection_member_reads = sum(1 for member in members if member.name in readings)
    calls = {
        "FullConstellation.ask": 1,
        "resolution.ask_member_reads": selection_member_reads,
        "resolution.Ladder.vote_for_selection": selection_member_reads,
        "resolution.Ladder.vote_for_grain_trace": rung_vote_calls,
        "FullConstellation.ask.hierarchy.gather": int(tree is not None and bool(terms)),
        "source_tree_leaf_walk": int(visited_nodes > 0),
        "source_tree_nodes_visited": visited_nodes,
        "source_tree_leaves_visited": visited_leaves,
        "Base.lower": int(source_router is not None and
                           surface_route.get("verdict") != "UNKNOWN_ROUTER_API"),
        "conduct_tree.descend": int(surface_route.get("route_kind") == "surface_conduction"),
        "surface.route": int(surface_route.get("route_kind") == "surface_conduction"),
    }

    candidates = sorted(grouped.values(), key=lambda row: row["item"])
    return {
        "kind": "multigrain_candidates",
        "verdict": verdict,
        "raw_question": raw_question,
        "selector_query": selector_query,
        "candidate_limit": limit,
        "selector_query_origin": ("raw_question" if candidate_query is None
                                  else "explicit_candidate_query"),
        "query_terms": list(terms),
        "selected_candidate": chosen_item if has_selected_source and
            selected.get("verdict") in ("ANSWER", "ANSWER_BY_COARSENING") else None,
        "resolution_verdict": selected.get("verdict"),
        "resolution_item": chosen_item,
        # Keep the selector's own reason for abstention explicit. A Goal
        # navigation layer may inspect an exact CrossStore facet owner only
        # when every query term is known as a facet, no term is absent, and
        # FullConstellation itself did not select a core. These fields never
        # turn a facet into a resolution vote.
        "resolution_as_core": list(selected.get("as_core", ())),
        "resolution_as_facet_only": list(selected.get("as_facet_only", ())),
        "resolution_missing": list(selected.get("missing", ())),
        "resolution_agreeing": selected.get("agreeing"),
        "resolution_of": selected.get("of"),
        "candidates": candidates,
        "grain_trace": grain_trace,
        "query_destinations": query_destinations,
        "query_divisions_from_constellation": list(query_divisions),
        "query_divisions_are_partial": bool(tree is not None),
        "surface_route": surface_route,
        "source_identity_status": "identity_unverified" if has_selected_source or has_any_source else
            ("UNKNOWN_NO_SOURCE_MATCH" if tree is not None else "UNKNOWN_NO_HIERARCHY"),
        "independent_source_count": None,
        "identity_note": _SOURCE_IDENTITY_NOTE,
        "trace": {
            "calls": calls,
            "candidate_selection": (
                "FullConstellation.ask(raw_question); its existing resolution consensus is the selector"
                if candidate_query is None else
                "FullConstellation.ask(candidate_query); provenance must be rederived by the caller's Goal consumer"
            ),
            "selector_query": selector_query,
            "source_join": "exact candidate core key plus configured source-leaf grain features",
            "query_division_note": "FullConstellation.ask exposes at most six leaf names from its gather result",
            "structural_views_are_source_votes": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 3),
        },
    }
