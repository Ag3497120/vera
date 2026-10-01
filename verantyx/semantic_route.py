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
from .semantic_ir import Nominal, View

#: Below this many leaves a single routing node is no cheaper than the flat view: keep the flat behaviour.
ROUTE_MIN_LEAVES = 7
_INSTRUCTION = 'document instruction excluded'


def _grams(text):
    """Character bigrams (unigrams for one-character text) of an unread span, in their own namespace.

    Substring containment is complete: if an anchor occurs inside the text, every bigram of the anchor does,
    so a leaf whose unread text mentions the anchor is never missed, whatever the tokenizer did to it.
    """
    text = ''.join(ch for ch in text if not ch.isspace())
    if len(text) == 1: return {'§§' + text}
    return {'§' + text[i:i + 2] for i in range(len(text) - 1)}


def _pattern_terms(pattern):
    for name, term in pattern.roles:
        if name == 'attribute': continue
        if isinstance(term, Nominal): yield term.head
        elif isinstance(term, str) and term: yield term


def _guard_terms(clause):
    """Entities of a clause's condition and exception patterns: where a guard's own fact has to be looked up."""
    for pattern in (*clause.conditions, *clause.exceptions):
        yield from _pattern_terms(pattern)


def _clause_terms(clause):
    for role in clause.roles:
        if isinstance(role.term, str) and role.term: yield role.term
    for pattern in (*clause.conditions, *clause.exceptions):
        yield from _pattern_terms(pattern)


def pattern_anchors(request):
    """One anchor set per Bind pattern: its literal string role terms (Nominal heads are not anchors)."""
    sets = []
    for plan in request.plans:
        for node in plan.nodes:
            if node.pattern is None: continue
            terms = {term for name, term in node.pattern.roles
                     if name != 'attribute' and isinstance(term, str) and term}
            if terms: sets.append(terms)
    return sets


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
                leaf.setdefault(term, {}); leaf[term][clause.predicate] = leaf[term].get(clause.predicate, 0) + 1
        self.unread_by_leaf = defaultdict(list)
        for unread in view.unread:
            if unread.reason == _INSTRUCTION: continue      # excluded text never gated the flat view either
            self.unread_by_leaf[unread.span.source].append(unread)
            leaf = crosses.setdefault(unread.span.source, {})
            for core in _grams(unread.span.text):
                leaf.setdefault(core, {}); leaf[core]['<unread>'] = leaf[core].get('<unread>', 0) + 1
        self.leaves = crosses
        self.root = conduct_tree.build(crosses, arity=arity) if crosses else None
        self.nodes = self._count(self.root)
        self.build_ms = (time.perf_counter() - started) * 1000

    @staticmethod
    def _count(node):
        if not isinstance(node, conduct_tree.Node): return 0
        return 1 + sum(LeafTree._count(child) for child in node.children.values())

    def reach(self, cores, limit=None):
        """(leaves holding any core, nodes visited); leaves is None when more than `limit` leaves hold them."""
        found = set(); visited = 0
        class Over(Exception): pass
        def walk(node):
            nonlocal visited
            visited += 1
            for arm, child in node.children.items():
                held = node.profile[arm]
                if not any(core in held for core in cores): continue
                if isinstance(child, conduct_tree.Node): walk(child)
                else:
                    found.add(getattr(node, 'leaf_names', {}).get(arm, arm))
                    if limit is not None and len(found) > limit: raise Over
        try:
            if self.root is not None: walk(self.root)
        except Over:
            return None, visited
        return found, visited

    def restrict(self, request, *, anchor_cap: int = 64, expand_cap: int = 8, max_rounds: int = 8):
        """(routed View | None, trace). None means: keep the whole view (no usable anchor, or too few leaves).

        Round 1: for every Bind pattern, the leaves that hold ALL of its anchors (a clause binding the pattern, or a
        clause contradicting it, must contain every literal role value of the pattern), unioned over the patterns.
        An anchor held by more than `anchor_cap` leaves does not narrow (it is common); a pattern whose anchors are
        all common cannot narrow, and then the whole view is kept.
        Later rounds follow the plan's depth: entities of the reached clauses that few leaves hold (<= `expand_cap`)
        bring in the documents that continue the chain; common entities (係員 in every document) are not followed,
        which can only lose a derivation (abstention), never create one.
        """
        started = time.perf_counter()
        trace = {'part': 'semantic_route.LeafTree', 'leaves': len(self.leaves), 'nodes': self.nodes, 'arity': self.arity}
        if len(self.leaves) < ROUTE_MIN_LEAVES:
            return None, {**trace, 'status': 'skipped', 'reason': 'fewer leaves than one routing node'}
        patterns = pattern_anchors(request)
        if not patterns:
            return None, {**trace, 'status': 'skipped', 'reason': 'request has no entity anchor'}
        visited = 0; common = set(); cache = {}
        def held(term, cap):
            """Leaves that can mention `term`: an exact clause value, or unread text containing it. None = common."""
            nonlocal visited
            key = (term, cap)
            if key in cache: return cache[key]
            found, n = self.reach({term}, cap); visited += n
            leaves = None
            if found is not None:
                leaves = set(found)
                inter = None
                for gram in _grams(term):
                    g, n = self.reach({gram}, cap); visited += n
                    if g is None: continue                      # a common gram does not narrow
                    inter = g if inter is None else inter & g
                    if not inter: break
                if inter is None:
                    # every gram of the anchor is common: unread mentions cannot be located cheaply
                    leaves = None
                else:
                    leaves |= inter
            cache[key] = None if leaves is None or len(leaves) > cap else leaves
            return cache[key]
        reached = set()
        for terms in patterns:
            leaves = None
            for term in sorted(terms):
                found = held(term, anchor_cap)
                if found is None: common.add(term); continue
                leaves = found if leaves is None else leaves & found
            if leaves is None:
                return None, {**trace, 'status': 'skipped', 'reason': 'every anchor of a pattern is common',
                              'common_anchors': sorted(common)}
            reached |= leaves
        # A join needs one more hop per extra Bind pattern; a guard (condition/exception) needs its own fact, which
        # may sit in another document, for a few more hops. Nothing else is followed.
        binds = max((sum(1 for n in p.nodes if n.pattern is not None) for p in request.plans), default=1)
        join_rounds = max(0, min(max_rounds, binds - 1)); guard_rounds = 3
        frontier = set(reached); seen_terms = set(t for ts in patterns for t in ts); used = 1; followed = 0
        for hop in range(join_rounds + guard_rounds):
            pending = set()
            for leaf in frontier:
                for clause in self.by_leaf.get(leaf, ()):
                    pending.update(_clause_terms(clause) if hop < join_rounds else _guard_terms(clause))
            frontier = set()
            for term in pending - seen_terms:
                seen_terms.add(term)
                found = held(term, expand_cap)
                if found is None: common.add(term); continue
                followed += 1; frontier |= found - reached
            if not frontier: break
            reached |= frontier; used += 1
        clauses = tuple(c for leaf in sorted(reached) for c in self.by_leaf.get(leaf, ()))
        unread = tuple(u for leaf in sorted(reached) for u in self.unread_by_leaf.get(leaf, ()))
        unread += tuple(u for u in self.view.unread if u.reason == _INSTRUCTION and u.span.source in reached)
        sources = {leaf: self.view.sources[leaf] for leaf in reached if leaf in self.view.sources}
        routed = View(sources, clauses, unread, self.view.ingest_ms)
        return routed, {**trace, 'status': 'routed', 'patterns': len(patterns), 'rounds': used,
                        'reached_leaves': len(reached), 'common_terms': len(common), 'followed_terms': followed,
                        'nodes_visited': visited, 'clauses_in_reach': len(clauses),
                        'route_ms': (time.perf_counter() - started) * 1000}
