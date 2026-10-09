"""G3-b: the sliding windows and the exact counts of their three axes (docs/LINE3_G3_SLIDING_PACKS.md, ticket G3-b).

Owner (ops/decisions/2026-10-06_line3_faithful_build.md, G3 answers 1-4 and 5-6, 2026-10-09):
  OP-G3-1 「文ごとの 3 層パック。この文と次の文。1 文ずつ重ねて進む」  -> a window = sentence N + sentence N+1, slid one sentence at a time
  OP-G3-2 「同じ記事の隣り合う 2 文」                                  -> pairs only inside one article, never across an article end
  OP-G3-3 「x＝語順、y＝粒度、z＝スライド」                             -> the three axes below
  OP-G3-6 「梯子の順に x、y、z へ。重みは辺の流れと配置の結合と読む順に」 -> the foundation labels, in the spec only

What this module is.  Pure bookkeeping, nothing searched or scored: it lists the windows of a corpus, gives the pack of one
window (the units of the three tiers RUN / WORD / CHAR of both sentences, each with its sentence and its surface span from
F2's SpanIndex) and counts, per axis, the evidence that an edge between two units of the pack has.  Every count is an
int and is the LENGTH of a list of sources (sentence ids and surface offsets), so each number can be traced to the text.
No float, no randomness, nothing taken from a set or dict without an order.  Nothing here changes an existing output:
no hook into ask / placement / cycle exists (that is G3-c/d); the Space is only read.

  article   = consecutive rows with the same `title` of their `source` ("title#i"); index = previous + 1   (L-520)
  window    = (sentence N, sentence N+1) of one article, in the order of the data file; W_N has N = sid of the first  (L-521)
  pack      = occurrences (tier, sid, k, unit, start, end) of both sentences, all three tiers, repeats kept             (L-522)
  x (order) = same tier, same sentence, ordered pair (o, i): o before i / o after i by FIRST occurrence (= p_pair)      (L-523)
  y (grain) = a unit of a coarser tier whose span contains a span of a unit of a finer tier, ANY occurrence pair        (L-524)
  z (slide) = u in sentence N and v in sentence N+1 of one window (any two tiers); +z : outer o is the earlier one      (L-525)
  scope     = "window": only the evidence of this window; "corpus": the evidence over the whole corpus (L-G3-1)         (L-526)

The spec (`SlideSpec`) carries the corpus sha, the window rule, the three axis definitions and the foundation (the P7
particles on the arms in ladder order, with the Fibonacci weights as exact Fractions); its sha256 is what a cache key and an
answer will carry (L-527).  Serialisation is canonical JSON, as Space.to_bytes (L-528).
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from verantyx.line3 import space as sp
from verantyx.line3.granularity import SpanIndex

FORMAT = "line3.slide.v1"
TIERS: Tuple[str, ...] = sp.TIERS                         # RUN (coarsest), WORD, CHAR
TIER_RANK: Mapping[str, int] = {t: i for i, t in enumerate(TIERS)}
AXES: Tuple[str, ...] = ("x", "y", "z")
ARMS: Tuple[str, ...] = ("+x", "-x", "+y", "-y", "+z", "-z")   # G3 3.1 / 3.3: the order of the arms (a ring)
SCOPES: Tuple[str, ...] = ("window", "corpus")
LONE_RULES: Tuple[str, ...] = ("none", "last", "singleton")
Z_DEEPS: Tuple[str, ...] = ("slide", "order")          # G3-c4 (L-660): what a z-arm edge deeper than the innermost one counts


def canonical(doc) -> bytes:
    """Canonical JSON (sorted keys, compact, UTF-8, as Space.to_bytes).  A float anywhere is refused."""
    return json.dumps(_nofloat(doc), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _nofloat(v):
    if type(v).__name__ == "float":                  # refused by name: this module never mentions the type itself
        raise TypeError("a non-exact number in a canonical document")
    if isinstance(v, Fraction):
        return "%d/%d" % (v.numerator, v.denominator)
    if isinstance(v, Mapping):
        return {k: _nofloat(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_nofloat(x) for x in v]
    return v


# --------------------------------------------------------------------------------------------------------------
# articles and windows (L-520, L-521)
# --------------------------------------------------------------------------------------------------------------
def split_source(source) -> Tuple[str, int]:
    """'title#i' -> (title, i).  A source without '#i' is refused (no guess about where an article ends)."""
    if not isinstance(source, str) or "#" not in source:
        raise ValueError("source is not 'title#i': %r" % (source,))
    title, i = source.rsplit("#", 1)
    if not title or not i.isascii() or not i.isdigit():
        raise ValueError("source is not 'title#i': %r" % (source,))
    return title, int(i)


@dataclass(frozen=True)
class Article:
    title: str
    sids: Tuple[int, ...]                  # consecutive sentence ids, in the order of the data file
    idx: Tuple[int, ...]                   # their numbers inside the article (the i of 'title#i')


def articles(space: sp.Space, rows: Optional[Sequence[Mapping[str, str]]] = None) -> Tuple[Article, ...]:
    """L-520.  Articles of a corpus in the order of the data file.  Refused (ValueError): a source that is not 'title#i';
    a row whose `title` field disagrees with its source (when `rows` is given); a title that comes back after another
    article; an index that is not the previous one + 1 inside an article.  Nothing is merged, split or skipped silently."""
    if rows is not None:
        rows = list(rows)
        if len(rows) != space.N:
            raise ValueError("rows and space differ in length")
    out: List[Article] = []
    seen = set()
    cur_title = None
    sids: List[int] = []
    idx: List[int] = []

    def close():
        if cur_title is not None:
            out.append(Article(cur_title, tuple(sids), tuple(idx)))

    for sid in range(space.N):
        title, i = split_source(space.sentences[sid][1])
        if rows is not None:
            r = rows[sid]
            if r.get("sent") != space.sentences[sid][0]:
                raise ValueError("row %d: sentence differs from the space" % sid)
            if "title" in r and r["title"] != title:
                raise ValueError("row %d: title field %r disagrees with source %r" % (sid, r["title"], space.sentences[sid][1]))
        if title != cur_title:
            close()
            if title in seen:
                raise ValueError("article %r comes back after another article (row %d)" % (title, sid))
            seen.add(title)
            cur_title, sids, idx = title, [], []
        elif i != idx[-1] + 1:
            raise ValueError("article %r: sentence number %d follows %d (row %d)" % (title, i, idx[-1], sid))
        sids.append(sid)
        idx.append(i)
    close()
    return tuple(out)


@dataclass(frozen=True)
class Window:
    """W_N.  `n` = N = the sid of its first sentence.  A pair has two sids, a one-sentence window one."""
    n: int
    title: str
    sids: Tuple[int, ...]
    idx: Tuple[int, ...]

    def doc(self) -> dict:
        return {"n": self.n, "title": self.title, "sids": list(self.sids), "idx": list(self.idx)}


@dataclass(frozen=True)
class Occ:
    """One unit occurrence of a pack: where it is (sid, k = its position in the tier's unit list of the sentence) and its
    surface span [start, end) in SpanIndex.text(sid)."""
    tier: str
    sid: int
    k: int
    unit: str
    start: int
    end: int

    def row(self) -> list:
        return [self.tier, self.sid, self.k, self.unit, self.start, self.end]


# --------------------------------------------------------------------------------------------------------------
# the foundation: P7 labels on the arms in ladder order, Fibonacci weights as exact Fractions (L-529)
# --------------------------------------------------------------------------------------------------------------
def fibonacci(n: int) -> int:
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


# G1 3.1.1 / G3 3.5: the particles in ladder order (the default rank of OP-G1-3 (a): the order of the share of fulllead
# WORD sentences that hold them; the first is the centre side, the next six go on the arms +x -x +y -y +z -z).
P7_LADDER: Tuple[str, ...] = ("は", "の", "に", "で", "と", "を", "が")
WEIGHTS_ENTER: Tuple[str, ...] = ("edge_flow", "binding", "read_order")      # OP-G3-6: 「辺の流れと配置の結合と読む順に」
WEIGHTS_NOT_IN: Tuple[str, ...] = ("n", "N", "r0", "E_Q", "key")             # I-G3-2: made things are not evidence


@dataclass(frozen=True)
class Foundation:
    name: str
    ladder: Tuple[Tuple[str, Fraction], ...]          # (label, weight) in ladder order, strictly decreasing weights
    arms: Tuple[Tuple[str, str], ...]                 # (arm, label), arm in ARMS order

    def __post_init__(self) -> None:
        labels = [l for l, _ in self.ladder]
        weights = [w for _, w in self.ladder]
        if len(labels) != len(set(labels)):
            raise ValueError("foundation: a label twice")
        for w in weights:
            if not isinstance(w, Fraction):
                raise TypeError("foundation weights are exact Fractions, not %s" % type(w).__name__)
            if w <= 0:
                raise ValueError("foundation: a weight is not positive")
        for a, b in zip(weights, weights[1:]):
            if not a > b:
                raise ValueError("foundation: weights must be strictly decreasing along the ladder (a tie places nothing)")
        if tuple(a for a, _ in self.arms) != ARMS:
            raise ValueError("foundation: arms must be %r in this order" % (ARMS,))
        arm_labels = [l for _, l in self.arms]
        if len(set(arm_labels)) != len(arm_labels) or any(l not in labels for l in arm_labels):
            raise ValueError("foundation: arm labels must be distinct members of the ladder")

    @property
    def centre(self) -> Optional[str]:
        """The ladder label that is on no arm (the centre side), if any."""
        on = {l for _, l in self.arms}
        rest = [l for l, _ in self.ladder if l not in on]
        return rest[0] if len(rest) == 1 else None

    def weight(self, label: str) -> Fraction:
        return dict(self.ladder)[label]

    def arm_weight(self, arm: str) -> Fraction:
        return self.weight(dict(self.arms)[arm])

    def axis_weight(self, axis: str) -> Fraction:
        """Sum of the two opposite arms of an axis."""
        return self.arm_weight("+" + axis) + self.arm_weight("-" + axis)

    def common_denominator(self) -> int:
        """The least common denominator of the weights (377 for P7: a Fraction reduces 13/377 to 1/29, this keeps the ladder visible)."""
        d = 1
        for _, w in self.ladder:
            d = d * w.denominator // math.gcd(d, w.denominator)
        return d

    def doc(self) -> dict:
        d = self.common_denominator()
        return {"name": self.name, "ladder": [[l, w, int(w * d)] for l, w in self.ladder], "per": d, "centre": self.centre,
                "arms": {a: l for a, l in self.arms}, "arm_order": list(ARMS),
                "weights_enter": list(WEIGHTS_ENTER), "weights_not_in": list(WEIGHTS_NOT_IN),
                "labels": "ladder order onto x, y, z (OP-G3-6 (a)); a label sits on the arm, never as a seat"}


def p7(ladder: Sequence[str] = P7_LADDER) -> Foundation:
    """The owner's P7 foundation: the ladder F(14-k)/F(14), k = 1..7 (233/377 ... 13/377) on `ladder`; the labels after the
    first go on the arms +x, -x, +y, -y, +z, -z in ladder order."""
    ladder = tuple(ladder)
    if len(ladder) != 7:
        raise ValueError("P7 has seven labels")
    top = fibonacci(14)
    lad = tuple((l, Fraction(fibonacci(14 - k), top)) for k, l in enumerate(ladder, 1))
    return Foundation("P7", lad, tuple(zip(ARMS, ladder[1:])))


# --------------------------------------------------------------------------------------------------------------
# the spec (L-527)
# --------------------------------------------------------------------------------------------------------------
def _tup(v):
    if isinstance(v, (list, tuple)):
        return tuple(_tup(x) for x in v)
    return v


def _lst(v):
    if isinstance(v, tuple):
        return [_lst(x) for x in v]
    return v


@dataclass(frozen=True)
class AxisDef:
    axis: str
    text: str                                         # the definition in words (part of the sha)
    params: Tuple[Tuple[str, object], ...]            # the parts the counting code reads

    def param(self, key: str):
        return dict(self.params)[key]

    def doc(self) -> dict:
        return {"axis": self.axis, "text": self.text, "params": {k: _lst(v) for k, v in self.params}}


DEFAULT_Y_PAIRS: Tuple[Tuple[str, str], ...] = (("RUN", "WORD"), ("RUN", "CHAR"), ("WORD", "CHAR"))
_SUPPORTED = {("x", "occurrence"): ("first",), ("x", "tiers"): ("same",),
              ("y", "occurrence"): ("any",), ("y", "containment"): ("non-strict",),
              ("z", "occurrence"): ("first",), ("z", "tiers"): ("all", "same"), ("z", "deep"): Z_DEEPS}

Z_DEEP_TEXT = ("; z_deep=order (G3-c4): a z-arm edge deeper than the innermost one (the centre's neighbour) is not a slide edge but "
               "carries the word-order count of the pair as x does (n_x, before / after; +z forward, -z backward), the innermost "
               "z edge stays n_z")


def default_axes(y_pairs: Sequence[Sequence[str]] = DEFAULT_Y_PAIRS, z_tiers: str = "all",
                 z_deep: str = "slide") -> Tuple[AxisDef, AxisDef, AxisDef]:
    x = AxisDef("x", "word order: for two units of one tier in one sentence, the outer one before (+x) or after (-x) the inner one, "
                     "by the first occurrence of each (p_pair); n_x = the sentences that hold both", (
        ("occurrence", "first"), ("tiers", "same")))
    y = AxisDef("y", "granularity: the outer unit is of a coarser tier and its span contains a span of the inner unit (+y), or the reverse (-y); "
                     "a sentence counts once for any occurrence pair; equal spans count", (
        ("containment", "non-strict"), ("occurrence", "any"), ("pairs", _tup(y_pairs))))
    if z_deep not in Z_DEEPS:
        raise ValueError("z_deep must be one of %r" % (Z_DEEPS,))
    # the default spec keeps its bytes and its sha: the parameter and the sentence exist only under "order" (L-660)
    z = AxisDef("z", "slide: the outer unit lies in sentence N and the inner in sentence N+1 of one window (+z), or the reverse (-z); "
                     "n_z = the windows that hold both; z reaches no further than N+1" + (Z_DEEP_TEXT if z_deep == "order" else ""), (
        ("occurrence", "first"), ("tiers", z_tiers)) + ((("deep", z_deep),) if z_deep != "slide" else ()))
    return x, y, z


@dataclass(frozen=True)
class WindowRule:
    span: int = 2
    scope: str = "same-article"
    lone: str = "last"                                # L-521: which one-sentence windows exist besides the pairs

    def __post_init__(self) -> None:
        if self.span != 2:
            raise ValueError("only the two-sentence window is built (OP-G3-2 (a)); 3 sentences is OP-G3-2 (b)")
        if self.scope != "same-article":
            raise ValueError("windows stay inside one article (OP-G3-2 (a))")
        if self.lone not in LONE_RULES:
            raise ValueError("lone must be one of %r" % (LONE_RULES,))

    def doc(self) -> dict:
        return {"span": self.span, "scope": self.scope, "lone": self.lone, "step": 1, "order": "data file (stream) order",
                "article": "consecutive rows with the same source title, sentence number = previous + 1",
                "id": "W_N, N = sid of the first sentence",
                "lone_rule": {"none": "pairs only; the last sentence of an article and every one-sentence article form no window",
                              "last": "also the last sentence of every article as a one-sentence window (z arms empty)",
                              "singleton": "also every one-sentence article as a one-sentence window"}[self.lone]}


@dataclass(frozen=True)
class SlideSpec:
    corpus_sha: str
    window: WindowRule
    axes: Tuple[AxisDef, AxisDef, AxisDef]
    foundation: Foundation
    tiers: Tuple[str, ...] = TIERS

    def __post_init__(self) -> None:
        if tuple(a.axis for a in self.axes) != AXES:
            raise ValueError("axes must be x, y, z in this order")
        for a in self.axes:
            for k, v in a.params:
                if (a.axis, k) in _SUPPORTED and v not in _SUPPORTED[(a.axis, k)]:
                    raise ValueError("axis %s: %s=%r is not built (one of %r)" % (a.axis, k, v, _SUPPORTED[(a.axis, k)]))
        for c, f in self.axis("y").param("pairs"):
            if c not in TIER_RANK or f not in TIER_RANK or TIER_RANK[c] >= TIER_RANK[f]:
                raise ValueError("y pairs are (coarser tier, finer tier): %r" % ((c, f),))
        if self.tiers != TIERS:
            raise ValueError("tiers are RUN, WORD, CHAR")

    def axis(self, name: str) -> AxisDef:
        return {a.axis: a for a in self.axes}[name]

    @property
    def z_deep(self) -> str:
        """"slide" (every z-arm edge is a slide edge, n_z) or "order" (the edges deeper than the innermost carry the word-order count; L-660)."""
        return dict(self.axis("z").params).get("deep", "slide")

    def doc(self) -> dict:
        return {"format": FORMAT, "kind": "spec", "corpus_sha256": self.corpus_sha, "tiers": list(self.tiers),
                "window": self.window.doc(), "axes": [a.doc() for a in self.axes], "foundation": self.foundation.doc()}

    def to_bytes(self) -> bytes:
        return canonical(self.doc())

    def sha256(self) -> str:
        return hashlib.sha256(self.to_bytes()).hexdigest()

    def short(self) -> str:
        """The 12 hex characters of a cache key (`_slide-<sha12>`, L-G3-8)."""
        return self.sha256()[:12]


def default_spec(space: sp.Space, *, lone: str = "last", y_pairs: Sequence[Sequence[str]] = DEFAULT_Y_PAIRS,
                 z_tiers: str = "all", foundation: Optional[Foundation] = None, z_deep: str = "slide") -> SlideSpec:
    return SlideSpec(space.sha256(), WindowRule(lone=lone), default_axes(y_pairs, z_tiers, z_deep), foundation or p7())


# --------------------------------------------------------------------------------------------------------------
# counts
# --------------------------------------------------------------------------------------------------------------
XSrc = Tuple[int, int, int, int, int]                 # (sid, o_start, o_end, i_start, i_end)
YSrc = Tuple[int, int, int, int, int]                 # (sid, o_start, o_end, i_start, i_end), o is the coarser unit
ZSrc = Tuple[int, int, int, int, int, int]            # (sid_N, sid_N+1, u_start, u_end, v_start, v_end)


@dataclass(frozen=True)
class WindowCounts:
    """The exact counts of one window.  Every count is the length of its source tuple (ints).
      x[(tier, o, i)]            = (before, after): sources where o's first occurrence precedes / follows i's.  n_x = both.
                                   Both orders (o, i) and (i, o) are listed; before(o, i) = after(i, o).
      y[(tier_o, o, tier_i, i)]  = sources: o (the coarser tier) has a span that contains a span of i.  +y(o, i); -y(i, o).
      z[(tier_u, u, tier_v, v)]  = sources: u in sentence N, v in sentence N+1.  +z(o=u, i=v); -z(o=v, i=u).
      z_side[(tier, unit)]       = ("this",), ("next",) or ("this", "next"): the sentence(s) of the window the unit lies in.
      z_deep                     = the spec's z_deep ("slide" | "order", L-660): the counts themselves do not change; the readers
                                   (the placement and the ratio reader) take the evidence of a z-arm edge deeper than the innermost from
                                   `deep_z` when it is "order".
    A key with no source is absent (its count is 0)."""
    window: Window
    scope: str
    x: Mapping[Tuple[str, str, str], Tuple[Tuple[XSrc, ...], Tuple[XSrc, ...]]]
    y: Mapping[Tuple[str, str, str, str], Tuple[YSrc, ...]]
    z: Mapping[Tuple[str, str, str, str], Tuple[ZSrc, ...]]
    z_side: Mapping[Tuple[str, str], Tuple[str, ...]]
    z_deep: str = "slide"

    def deep_z(self, tier: str, arm: str, o: str, i: str) -> Tuple[int, int, Tuple[XSrc, ...]]:
        """(L-660) The evidence of a z-arm edge DEEPER than the innermost (outer unit o, inner unit i, both of `tier`) under z_deep
        "order": the word-order count of the pair, read exactly as an x arm reads it: n = n_x(o, i), omega = before (arm "+z": o before i,
        forward) or after (arm "-z": o after i, backward), and the sources are the x rows (before first, then after).  Over the
        counts' scope (corpus: every sentence that holds both units; window: this window's sentences)."""
        if arm != "+z" and arm != "-z":
            raise ValueError("deep_z reads a z arm")
        b, a = self.x.get((tier, o, i), ((), ()))
        return len(b) + len(a), len(b) if arm == "+z" else len(a), tuple(b) + tuple(a)

    def n_x(self, tier: str, o: str, i: str) -> int:
        b, a = self.x.get((tier, o, i), ((), ()))
        return len(b) + len(a)

    def before_x(self, tier: str, o: str, i: str) -> int:        # p(o, i)
        return len(self.x.get((tier, o, i), ((), ()))[0])

    def after_x(self, tier: str, o: str, i: str) -> int:         # p(i, o)
        return len(self.x.get((tier, o, i), ((), ()))[1])

    def n_y(self, tier_o: str, o: str, tier_i: str, i: str) -> int:
        """Sentences where a span of o contains a span of i (o of the coarser tier): the count of +y(o, i) / -y(i, o)."""
        return len(self.y.get((tier_o, o, tier_i, i), ()))

    def n_z(self, tier_u: str, u: str, tier_v: str, v: str) -> int:
        """Windows with u in sentence N and v in sentence N+1: the count of +z(o=u, i=v) and of -z(o=v, i=u)."""
        return len(self.z.get((tier_u, u, tier_v, v), ()))

    def doc(self) -> dict:
        def kx(k):
            return (TIER_RANK[k[0]], k[1], k[2])

        def ky(k):
            return (TIER_RANK[k[0]], k[1], TIER_RANK[k[2]], k[3])
        d = {"format": FORMAT, "kind": "counts", "scope": self.scope, "window": self.window.doc(),
                "x": [[k[0], k[1], k[2], [list(s) for s in v[0]], [list(s) for s in v[1]]] for k, v in sorted(self.x.items(), key=lambda kv: kx(kv[0]))],
                "y": [[k[0], k[1], k[2], k[3], [list(s) for s in v]] for k, v in sorted(self.y.items(), key=lambda kv: ky(kv[0]))],
                "z": [[k[0], k[1], k[2], k[3], [list(s) for s in v]] for k, v in sorted(self.z.items(), key=lambda kv: ky(kv[0]))],
                "z_side": [[k[0], k[1], list(v)] for k, v in sorted(self.z_side.items(), key=lambda kv: (TIER_RANK[kv[0][0]], kv[0][1]))]}
        if self.z_deep != "slide":                         # L-660: the default counts keep their bytes
            d["z_deep"] = self.z_deep
        return d

    def to_bytes(self) -> bytes:
        return canonical(self.doc())


class Slide:
    """The windows of a corpus and their counts, computed on demand.  Reads `space`; changes nothing in it."""

    def __init__(self, space: sp.Space, spec: Optional[SlideSpec] = None,
                 rows: Optional[Sequence[Mapping[str, str]]] = None) -> None:
        self.space = space
        self.spans = SpanIndex(space)
        self.articles = articles(space, rows)
        self.spec = spec if spec is not None else default_spec(space)
        if self.spec.corpus_sha != space.sha256():
            raise ValueError("the spec was made for another corpus")
        self._pairs: Optional[Tuple[Window, ...]] = None
        self._next: Optional[Dict[int, int]] = None
        self._occ: Dict[Tuple[str, int], Dict[str, List[int]]] = {}
        self._set: Dict[Tuple[str, int], frozenset] = {}

    # ---- windows ------------------------------------------------------------------------------------------------
    def pairs(self) -> Tuple[Window, ...]:
        """The ordered list of adjacent sentence pairs inside one article (data file order, W_N with N the first sid)."""
        if self._pairs is None:
            out = []
            for a in self.articles:
                for j in range(len(a.sids) - 1):
                    out.append(Window(a.sids[j], a.title, (a.sids[j], a.sids[j + 1]), (a.idx[j], a.idx[j + 1])))
            self._pairs = tuple(out)
        return self._pairs

    windows = pairs

    def singletons(self) -> Tuple[Window, ...]:
        """RECORDED, not decided (L-521): the one-sentence articles, each as a one-sentence window.  They form no pair."""
        return tuple(Window(a.sids[0], a.title, (a.sids[0],), (a.idx[0],)) for a in self.articles if len(a.sids) == 1)

    def lasts(self) -> Tuple[Window, ...]:
        """The last sentence of every article as a one-sentence window (L-G3-10; contains the singletons)."""
        return tuple(Window(a.sids[-1], a.title, (a.sids[-1],), (a.idx[-1],)) for a in self.articles)

    def lone(self) -> Tuple[Window, ...]:
        """The one-sentence windows the spec's rule asks for."""
        return {"none": lambda: (), "last": self.lasts, "singleton": self.singletons}[self.spec.window.lone]()

    def sequence(self) -> Tuple[Window, ...]:
        """Pairs and the spec's one-sentence windows in W_N order (N = first sid; a pair W_N before the lone W_{N+1})."""
        return tuple(sorted(self.pairs() + self.lone(), key=lambda w: (w.n, -len(w.sids))))

    def next_sid(self, sid: int) -> Optional[int]:
        """N+1 when it is the next sentence of the same article, else None."""
        if self._next is None:
            self._next = {w.sids[0]: w.sids[1] for w in self.pairs()}
        return self._next.get(sid)

    # ---- the pack -----------------------------------------------------------------------------------------------
    def pack(self, w: Window) -> Tuple[Occ, ...]:
        """Every occurrence of every tier's units in the sentences of the window, ordered (sid, tier, k)."""
        out = []
        for sid in w.sids:
            for t in TIERS:
                us = self.space.tiers[t].sentence_units[sid]
                for k, (u, (a, b)) in enumerate(zip(us, self.spans.spans(t, sid))):
                    out.append(Occ(t, sid, k, u, a, b))
        return tuple(out)

    def window_doc(self, w: Window, pack: bool = True) -> dict:
        d = w.doc()
        if pack:
            d["pack"] = [o.row() for o in self.pack(w)]
        return d

    def window_bytes(self, w: Window) -> bytes:
        return canonical(self.window_doc(w))

    def doc(self, pack: bool = True) -> dict:
        return {"format": FORMAT, "kind": "slide", "spec": self.spec.doc(), "spec_sha256": self.spec.sha256(),
                "articles": [[a.title, list(a.sids), list(a.idx)] for a in self.articles],
                "pairs": [self.window_doc(w, pack) for w in self.pairs()],
                "lone": [self.window_doc(w, pack) for w in self.lone()],
                "singletons": [w.n for w in self.singletons()]}

    def to_bytes(self, pack: bool = True) -> bytes:
        return canonical(self.doc(pack))

    # ---- helpers ------------------------------------------------------------------------------------------------
    def _occs(self, t: str, sid: int) -> Dict[str, List[int]]:
        """unit -> its positions k in the sentence's unit list (ascending)."""
        r = self._occ.get((t, sid))
        if r is None:
            r = {}
            for k, u in enumerate(self.space.tiers[t].sentence_units[sid]):
                r.setdefault(u, []).append(k)
            self._occ[(t, sid)] = r
        return r

    def _units(self, t: str, sid: int) -> frozenset:
        r = self._set.get((t, sid))
        if r is None:
            r = self._set[(t, sid)] = frozenset(self.space.tiers[t].sentence_units[sid])
        return r

    def _span(self, t: str, sid: int, k: int) -> Tuple[int, int]:
        return self.spans.spans(t, sid)[k]

    # ---- the three axes -----------------------------------------------------------------------------------------
    def counts(self, w: Window, scope: str = "corpus") -> WindowCounts:
        """The counts of the edges among the units of the window's pack.
        scope="window": the evidence inside this window only (x, y: its sentences; z: this pair).
        scope="corpus": the evidence over the whole corpus (L-G3-1: seats only from the window, counted everywhere)."""
        if scope not in SCOPES:
            raise ValueError("scope must be one of %r" % (SCOPES,))
        return WindowCounts(w, scope, self._x(w, scope), self._y(w, scope), self._z(w, scope), self._z_side(w), self.spec.z_deep)

    def _pack_units(self, w: Window) -> Dict[str, List[str]]:
        """tier -> the distinct units of the pack in code point order (an order for bytes, never to pick a winner)."""
        out = {}
        for t in TIERS:
            acc = set()
            for sid in w.sids:
                acc.update(self.space.tiers[t].sentence_units[sid])
            out[t] = sorted(acc)
        return out

    def _common(self, t_o: str, o: str, t_i: str, i: str, w: Window, scope: str) -> List[int]:
        a, b = self.space.tiers[t_o].postings[o], self.space.tiers[t_i].postings[i]
        s = set(a).intersection(b)
        if scope == "window":
            s.intersection_update(w.sids)
        return sorted(s)

    def _x(self, w: Window, scope: str):
        out = {}
        units = self._pack_units(w)
        for t in TIERS:
            us = units[t]
            for a in range(len(us)):
                for b in range(a + 1, len(us)):
                    o, i = us[a], us[b]
                    fw, bw = [], []                           # sources with o first / with i first
                    for sid in self._common(t, o, t, i, w, scope):
                        oc = self._occs(t, sid)
                        ko, ki = oc[o][0], oc[i][0]            # first occurrences (L-523)
                        so, si_ = self._span(t, sid, ko), self._span(t, sid, ki)
                        (fw if ko < ki else bw).append((sid, so[0], so[1], si_[0], si_[1]))
                    out[(t, o, i)] = (tuple(fw), tuple(bw))
                    out[(t, i, o)] = (tuple(_swap_x(bw)), tuple(_swap_x(fw)))
        return {k: v for k, v in out.items() if v[0] or v[1]}

    def _y(self, w: Window, scope: str):
        out = {}
        units = self._pack_units(w)
        for tc, tf in self.spec.axis("y").param("pairs"):
            for o in units[tc]:
                for i in units[tf]:
                    srcs = []
                    for sid in self._common(tc, o, tf, i, w, scope):
                        hit = self.contain(tc, o, tf, i, sid)
                        if hit is not None:
                            srcs.append(hit)
                    if srcs:
                        out[(tc, o, tf, i)] = tuple(srcs)
        return out

    def contain(self, tc: str, o: str, tf: str, i: str, sid: int) -> Optional[YSrc]:
        """The first (k_o, k_i) with span(o at k_o) containing span(i at k_i), or None (L-524)."""
        for ko in self._occs(tc, sid)[o]:
            a1, b1 = self._span(tc, sid, ko)
            for ki in self._occs(tf, sid)[i]:
                a2, b2 = self._span(tf, sid, ki)
                if a1 <= a2 and b2 <= b1:
                    return (sid, a1, b1, a2, b2)
        return None

    def _z(self, w: Window, scope: str):
        if len(w.sids) != 2:
            return {}
        a, b = w.sids
        same = self.spec.axis("z").param("tiers") == "same"
        out = {}
        for ta in TIERS:
            for tb in TIERS:
                if same and ta != tb:
                    continue
                ua = sorted(self._units(ta, a))
                ub = sorted(self._units(tb, b))
                for u in ua:
                    cand = [n for n in self.space.tiers[ta].postings[u] if self.next_sid(n) is not None] if scope == "corpus" else [a]
                    for v in ub:
                        srcs = []
                        for n in cand:
                            m = self.next_sid(n)
                            if v in self._units(tb, m):
                                ku, kv = self._occs(ta, n)[u][0], self._occs(tb, m)[v][0]
                                su, sv = self._span(ta, n, ku), self._span(tb, m, kv)
                                srcs.append((n, m, su[0], su[1], sv[0], sv[1]))
                        if srcs:
                            out[(ta, u, tb, v)] = tuple(srcs)
        return out

    def _z_side(self, w: Window):
        out = {}
        for j, sid in enumerate(w.sids):
            side = "this" if j == 0 else "next"
            for t in TIERS:
                for u in self._units(t, sid):
                    out[(t, u)] = out.get((t, u), ()) + (side,)
        return out


def _swap_x(srcs):
    """The same sources seen from the other end of the pair: (sid, o_span, i_span) -> (sid, i_span, o_span)."""
    return [(s[0], s[3], s[4], s[1], s[2]) for s in srcs]


# --------------------------------------------------------------------------------------------------------------
# provenance check (I-G3-1): every source points at text that shows what the count says
# --------------------------------------------------------------------------------------------------------------
def verify_counts(slide: Slide, wc: WindowCounts) -> int:
    """(L-530) Re-checks every source of `wc` against the sentence surfaces; ValueError at the first one that does not hold.
    Returns the number of sources checked.  x: both surfaces are at their spans, the spans are the FIRST occurrences and
    their order is the one claimed; y: the outer span contains the inner span; z: the two sids are one article's
    neighbours (N, N+1) and both surfaces are at the spans of their first occurrences.  Also: a window-scope source lies in the window; a corpus-scope x total equals the
    space's own n_pair, and its 'before' count equals p_pair."""
    sp_ = slide.spans
    n = 0

    def surf(sid, a, b, unit, what):
        if sp_.text(sid)[a:b] != unit:
            raise ValueError("%s: sentence %d [%d:%d] shows %r, not %r" % (what, sid, a, b, sp_.text(sid)[a:b], unit))

    for (t, o, i), (bef, aft) in wc.x.items():
        for claim, srcs in (("before", bef), ("after", aft)):
            for (sid, a, b, c, d) in srcs:
                surf(sid, a, b, o, "x o")
                surf(sid, c, d, i, "x i")
                us = slide.space.tiers[t].sentence_units[sid]
                if (sp_.spans(t, sid)[us.index(o)], sp_.spans(t, sid)[us.index(i)]) != ((a, b), (c, d)):
                    raise ValueError("x: a source of (%r, %r) in sentence %d is not their first occurrences" % (o, i, sid))
                if claim == "before" and not us.index(o) < us.index(i):
                    raise ValueError("x: %r is not before %r in sentence %d" % (o, i, sid))
                if claim == "after" and not us.index(i) < us.index(o):
                    raise ValueError("x: %r is not after %r in sentence %d" % (o, i, sid))
                if wc.scope == "window" and sid not in wc.window.sids:
                    raise ValueError("x: source outside the window")
                n += 1
        if wc.scope == "corpus":
            ts = slide.space.tiers[t]
            if len(bef) + len(aft) != ts.n_pair(o, i) or len(bef) != ts.p_pair(o, i):
                raise ValueError("x: counts of (%r, %r) differ from n_pair / p_pair" % (o, i))
    for (tc, o, tf, i), srcs in wc.y.items():
        if TIER_RANK[tc] >= TIER_RANK[tf]:
            raise ValueError("y: outer tier must be coarser")
        for (sid, a, b, c, d) in srcs:
            surf(sid, a, b, o, "y o")
            surf(sid, c, d, i, "y i")
            if not (a <= c and d <= b):
                raise ValueError("y: span %r does not contain %r" % ((a, b), (c, d)))
            if wc.scope == "window" and sid not in wc.window.sids:
                raise ValueError("y: source outside the window")
            n += 1
    art = {s: a.title for a in slide.articles for s in a.sids}
    for (tu, u, tv, v), srcs in wc.z.items():
        for (s1, s2, a, b, c, d) in srcs:
            if s2 != s1 + 1 or art[s1] != art[s2]:
                raise ValueError("z: sentences %d, %d are not neighbours of one article" % (s1, s2))
            surf(s1, a, b, u, "z u")
            surf(s2, c, d, v, "z v")
            if (sp_.spans(tu, s1)[slide.space.tiers[tu].sentence_units[s1].index(u)],
                    sp_.spans(tv, s2)[slide.space.tiers[tv].sentence_units[s2].index(v)]) != ((a, b), (c, d)):
                raise ValueError("z: a source of (%r, %r) is not their first occurrences" % (u, v))
            if wc.scope == "window" and (s1, s2) != tuple(wc.window.sids):
                raise ValueError("z: source is not this window's pair")
            n += 1
    return n
