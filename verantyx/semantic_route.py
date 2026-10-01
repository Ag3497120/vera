"""Leaf routing for the Round5-A document path: the stereo-cross tree as a reach index.

Design (docs/ROUND5A_STEREO_ROUTE): one leaf per document (sovereign-sized unit). A conductive tree
(`conduct_tree.build`, arity 6, arbitrary sorted-name grouping) is built over the leaves' crosses
(core = entity/noun surface, facet = predicate). A question reads its *anchors* (string role terms and
noun heads of its patterns); every arm whose merged surface HOLDS an anchor is descended, so the reach set
contains EVERY leaf that mentions it — never one "best" leaf, because a single-leaf narrowing would hide a
contradicting or excepting document that mentions the same entity. The reach set is then closed under the
entities of the reached clauses (and their condition/exception patterns) for as many rounds as the plan is
deep, which is how a multi-hop derivation finds the next document.

Unread source spans are indexed with their nouns, so a document that mentions an anchor in a sentence the reader
could not interpret still gates the answer exactly as in the flat view; unread text elsewhere no longer blocks.

The routed View is only ever a SUBSET of the original one (same clauses, same spans); the producer and the
independent checker both run on it, so no proof can contain a clause that the flat view lacks. Routing never
adds an answer; it can only drop leaves that cannot mention the question's entities. A question without
anchors (role-only, measures) keeps the whole view.
"""
from __future__ import annotations

import time
from collections import defaultdict

from . import conduct_tree
from .answer_slots import nouns
from .semantic_ir import Nominal, View

#: Below this many leaves a single routing node is no cheaper than the flat view: keep the flat behaviour.
ROUTE_MIN_LEAVES = 7
_INSTRUCTION = 'document instruction excluded'


def _cores(text):
    """The surface and its nouns: how a role value or an unread span is found by an anchor."""
    out = {text} if text else set()
    out.update(nouns(text))
    return out


def _pattern_terms(pattern):
    for name, term in pattern.roles:
        if name == 'attribute': continue
        if isinstance(term, Nominal): yield term.head
        elif isinstance(term, str) and term: yield term


def _clause_terms(clause):
    for role in clause.roles:
        if isinstance(role.term, str) and role.term: yield role.term
    for pattern in (*clause.conditions, *clause.exceptions):
        yield from _pattern_terms(pattern)


def anchors_of(request):
    """String role terms and noun heads of every Bind pattern of the request's plans."""
    found = set()
    for plan in request.plans:
        for node in plan.nodes:
            if node.pattern is not None: found.update(_pattern_terms(node.pattern))
    return found


class LeafTree:
    def __init__(self, view: View, arity: int = conduct_tree.ARITY):
        started = time.perf_counter()
        self.view = view; self.arity = arity
        self.by_leaf = defaultdict(list)             # source -> clauses
        crosses = {}
        for clause in view.clauses:
            self.by_leaf[clause.span.source].append(clause)
            leaf = crosses.setdefault(clause.span.source, {})
            for term in _clause_terms(clause):
                for core in _cores(term):
                    leaf.setdefault(core, {}); leaf[core][clause.predicate] = leaf[core].get(clause.predicate, 0) + 1
        self.unread_by_leaf = defaultdict(list)
        for unread in view.unread:
            if unread.reason == _INSTRUCTION: continue      # excluded text never gated the flat view either
            self.unread_by_leaf[unread.span.source].append(unread)
            leaf = crosses.setdefault(unread.span.source, {})
            for core in _cores(unread.span.text):
                leaf.setdefault(core, {}); leaf[core]['<unread>'] = leaf[core].get('<unread>', 0) + 1
        self.leaves = crosses
        self.root = conduct_tree.build(crosses, arity=arity) if crosses else None
        self.nodes = self._count(self.root)
        self.build_ms = (time.perf_counter() - started) * 1000

    @staticmethod
    def _count(node):
        if not isinstance(node, conduct_tree.Node): return 0
        return 1 + sum(LeafTree._count(child) for child in node.children.values())

    def reach(self, cores):
        """Leaves whose crosses hold any of the cores, found by descending every arm that holds one."""
        found = set(); visited = 0
        def walk(node):
            nonlocal visited
            visited += 1
            for arm, child in node.children.items():
                held = node.profile[arm]
                if not any(core in held for core in cores): continue
                if isinstance(child, conduct_tree.Node): walk(child)
                else: found.add(getattr(node, 'leaf_names', {}).get(arm, arm))
        if self.root is not None: walk(self.root)
        return found, visited

    def restrict(self, request, *, max_rounds: int = 8):
        """(routed View | None, trace). None means: keep the whole view (no anchors, or too few leaves)."""
        started = time.perf_counter()
        trace = {'part': 'semantic_route.LeafTree', 'leaves': len(self.leaves), 'nodes': self.nodes, 'arity': self.arity}
        if len(self.leaves) < ROUTE_MIN_LEAVES:
            return None, {**trace, 'status': 'skipped', 'reason': 'fewer leaves than one routing node'}
        anchors = anchors_of(request)
        if not anchors:
            return None, {**trace, 'status': 'skipped', 'reason': 'request has no entity anchor'}
        rounds = min(max_rounds, max((p.depth() for p in request.plans), default=1))
        reached = set(); seen = set(); pending = set(anchors); visited = 0; used = 0
        for _ in range(rounds):
            current = {core for term in pending - seen for core in _cores(term)}
            seen |= pending
            if not current: break
            used += 1
            found, nodes = self.reach(current); visited += nodes
            new = found - reached; reached |= found
            pending = set()
            for leaf in new:
                for clause in self.by_leaf.get(leaf, ()): pending.update(_clause_terms(clause))
            if not pending - seen: break
        clauses = tuple(c for leaf in sorted(reached) for c in self.by_leaf.get(leaf, ()))
        unread = tuple(u for leaf in sorted(reached) for u in self.unread_by_leaf.get(leaf, ()))
        # keep the document-instruction exclusions of the reached leaves (they never block, but stay visible)
        unread += tuple(u for u in self.view.unread if u.reason == _INSTRUCTION and u.span.source in reached)
        sources = {leaf: self.view.sources[leaf] for leaf in reached if leaf in self.view.sources}
        routed = View(sources, clauses, unread, self.view.ingest_ms)
        return routed, {**trace, 'status': 'routed', 'anchors': sorted(anchors), 'rounds': used,
                        'reached_leaves': len(reached), 'nodes_visited': visited,
                        'clauses_in_reach': len(clauses), 'route_ms': (time.perf_counter() - started) * 1000}
