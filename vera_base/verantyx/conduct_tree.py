"""A second tree, routed by surface conduction — beside `hierarchy`, not over it.

`hierarchy` is the original: it measured the 24-word ceiling and routes by
what sits ON the faces, which is exactly why it also measured 0/60 for
terms off them. This module keeps that ceiling and repeals its routing
consequence with `surface.route`. Two modules on purpose — the first
version of this file OVERWROTE `hierarchy.py`, which broke the
SOVEREIGN_BUILD fork and shipped one commit with a fork claim that was
false; the original is restored verbatim and this lives beside it.

The capacity law says one node distinguishes 24 words and a vocabulary V
therefore needs depth ~ log6(V/4) — layers are not a choice. What blocked
the tree was routing: an upper node routed 0/60 for words off its faces,
so descending the tree lost every question the faces did not happen to
carry. `surface.route` repealed that (0/52 -> 52/52 with conduction, ties
abstaining), and this module is the tree built on it. Measured on 36
statutes in two levels (6 groups x 6 laws), 127 probes each unique to one
law:

    descent correct     121 / 127  (95%)
    descent wrong         0 / 127
    abstained             6        (5 at the trunk, 1 at a branch, named)
    out-of-corpus         6 / 6 abstained
    per-probe cost      < 0.1ms after build

Grouping was ARBITRARY (sorted-name blocks) and the router still routes —
the stronger claim, since a considered grouping can only help.

    level 0   leaf sovereigns — one store per law, data-varied
    level 1+  routing nodes — six arms each, faces from `distinct_faces`,
              descent by `surface.route`

A routing node holds NO census and NO merged store. The trajectory
measured what pooling does (three domain sovereigns voted together:
answered 284 -> 208; cut-varied readings in one census: out-of-corpus
0 -> 8 wrong), so an upper node here is only a switch: it hands the
question DOWN, typed, and the leaf answers with its own gates. Layered,
never pooled — the tree is the staircase made literal.

## Typed descent

Every hop can abstain. `UNKNOWN_NO_ROUTE` carries WHERE the descent
stopped and which arms tied, because a reader repairing the tree needs to
know whether the miss was at the trunk or a branch. An invented term
abstains at the first hop (measured 6/6), which is the subject gate's
behaviour expressed as geometry.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from . import surface
from .surface import distinct_faces

#: Six arms per node — the geometry's own arity.
ARITY = 6


@dataclass
class Node:
    """One routing node: arms to children, faces to route by."""

    name: str
    children: Dict[str, Any] = field(default_factory=dict)   # arm -> Node|store
    faces: Dict[str, List[str]] = field(default_factory=dict)
    #: Aggregate facet profile per arm, used as the "store" a parent sees.
    profile: Dict[str, Any] = field(default_factory=dict)
    # A federated hierarchy can name an arm after its sovereign while the
    # single document below it has a different leaf name. Keep that identity
    # through descent; returning the arm would hand Base an unknown document.
    leaf_names: Dict[str, str] = field(default_factory=dict)

    def is_leaf_arm(self, arm: str) -> bool:
        return not isinstance(self.children.get(arm), Node)


def _merged_view(child: Any) -> Dict[str, Dict[str, int]]:
    """What a parent node sees of one arm: the crosses beneath it, summed.

    A VIEW for face-picking and conduction only — it never answers and
    never votes, so this is not the pooling the measurements forbid. The
    same distinction as witnesses: reading a merged surface is not holding
    a merged election.
    """
    if not isinstance(child, Node):
        return child
    out: Dict[str, Dict[str, int]] = {}
    for arm in child.children:
        for c, cr in _merged_view(child.children[arm]).items():
            dst = out.setdefault(c, {})
            for f, n in cr.items():
                dst[f] = dst.get(f, 0) + n
    return out


class _RoutingView:
    """Compact arm surface over existing leaf crosses, never an answer store.

    The original tree materialises merged crosses at every level. A library
    holds millions of sentences, so this view compiles only term membership,
    four face connections, and their one-step surface adjacencies.
    """

    def __init__(self, facets: Counter):
        self.facets = facets
        self.core_terms: set[str] = set()
        self.core_mass: Counter = Counter()
        self.direct_faces: dict[str, int] = {}
        self.conducted_cores: set[str] = set()
        self.adjacent: dict[str, set[str]] = {}

    def values(self):
        # distinct_faces needs aggregate facet weight, not merged core maps.
        return (self.facets,)

    def prepare(self, faces: Sequence[str], leaf_crosses: Sequence[dict]) -> None:
        self.adjacent = {face: set() for face in faces}
        wanted = set(faces)
        masks: dict[str, int] = {}
        for crosses in leaf_crosses:
            for core, cross in crosses.items():
                self.core_terms.add(core)
                self.core_mass[core] += sum(cross.values())
                for face in wanted.intersection(cross):
                    self.adjacent[face].update(cross)
                mask = masks.get(core, 0)
                for bit, face in enumerate(faces):
                    if face in cross or face == core:
                        mask |= 1 << bit
                if mask:
                    masks[core] = mask
        self.direct_faces = {core: mask.bit_count() for core, mask in masks.items()}
        if faces:
            for crosses in leaf_crosses:
                for core, cross in crosses.items():
                    if core not in self.direct_faces and any(
                            not neighbours.isdisjoint(cross)
                            for neighbours in self.adjacent.values()):
                        self.conducted_cores.add(core)
        # A source word can enter through a held facet or a held core; neither
        # turns the routing view into a pooled answer store.

    def surface_score(self, word: str) -> int:
        direct = self.direct_faces.get(word, 0)
        if direct:
            return 2 + direct
        if word in self.conducted_cores or any(
                word in neighbours for neighbours in self.adjacent.values()):
            return 2
        if word in self.core_terms or word in self.facets:
            return 1
        return 0

    def surface_mass(self, word: str) -> int:
        return self.core_mass[word] + self.facets[word]


def _build_from_hierarchy(leaves: Dict[str, Any], hierarchy: Any) -> Node:
    """Mirror source/sovereign grouping with compact conductive surfaces."""
    def convert(source: Any):
        if source.is_leaf:
            crosses = leaves[source.name]
            facets: Counter = Counter()
            for cross in crosses.values():
                facets.update(cross)
            return crosses, facets, [crosses]

        parts = {arm: convert(child) for arm, child in source.children.items()}
        node = Node(name=source.name, children={arm: p[0] for arm, p in parts.items()})
        node.leaf_names = {arm: child.name for arm, child in source.children.items()
                           if child.is_leaf}
        views = {arm: _RoutingView(p[1]) for arm, p in parts.items()}
        node.faces = distinct_faces(views)
        for arm, view in views.items():
            view.prepare(node.faces[arm], parts[arm][2])
        node.profile = views
        facets: Counter = Counter()
        leaf_crosses: list[dict] = []
        for _, child_facets, child_crosses in parts.values():
            facets.update(child_facets)
            leaf_crosses.extend(child_crosses)
        return node, facets, leaf_crosses

    return convert(hierarchy)[0]


def build(leaves: Dict[str, Any], *, arity: int = ARITY,
          name: str = "root", hierarchy: Any = None) -> Node:
    """Grow the tree bottom-up until one node holds everything.

    Grouping is by sorted name in blocks — deliberately arbitrary. Branch
    assignment is the top placement problem and choosing "good" groups by
    similarity would be clustering, which this project keeps refusing; the
    measurement below shows the router works even against arbitrary groups,
    which is the stronger claim. A better grouping can only help.
    """
    if hierarchy is not None:
        return _build_from_hierarchy(leaves, hierarchy)
    level: Dict[str, Any] = dict(leaves)
    depth = 0
    while len(level) > arity:
        names = sorted(level)
        nxt: Dict[str, Any] = {}
        for i in range(0, len(names), arity):
            block = names[i:i + arity]
            node = Node(name=f"L{depth}:{block[0]}..")
            node.children = {b: level[b] for b in block}
            node.profile = {b: _merged_view(level[b]) for b in block}
            node.faces = distinct_faces(node.profile)
            nxt[node.name] = node
        level = nxt
        depth += 1
    root = Node(name=name)
    root.children = dict(level)
    root.profile = {a: _merged_view(c) for a, c in level.items()}
    root.faces = distinct_faces(root.profile)
    return root


def descend(node: Node, term: str | Sequence[str], *, trail: Optional[List[str]] = None,
            anchor: str | None = None
            ) -> Dict[str, Any]:
    """Route the term down to a leaf sovereign, or say where it stopped."""
    trail = list(trail or [])
    arm = surface.route(node.profile, node.faces, term)
    if arm is None:
        return {"verdict": "UNKNOWN_NO_ROUTE", "stopped_at": node.name,
                "trail": trail,
                "note": "no arm's faces are reachable from this term's "
                        "surface, or two arms tied; descending further "
                        "would be a guess"}
    view = node.profile[arm]
    if anchor and hasattr(view, "surface_mass") and not view.surface_mass(anchor):
        return {"verdict": "UNKNOWN_NO_ROUTE", "stopped_at": node.name,
                "trail": trail, "anchor": anchor,
                "note": "the selected arm does not hold the named subject"}
    trail.append(arm)
    child = node.children[arm]
    if isinstance(child, Node):
        return descend(child, term, trail=trail, anchor=anchor)
    return {"verdict": "ROUTED", "leaf": getattr(node, "leaf_names", {}).get(arm, arm),
            "trail": trail}
