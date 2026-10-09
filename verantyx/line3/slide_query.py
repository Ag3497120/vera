"""G3-e: the question path over sliding windows, `structure="slide"` (docs/LINE3_G3_SLIDING_PACKS.md 5, 6.1, 7.3; ticket G3-e).

Owner (ops/decisions/2026-10-06_line3_faithful_build.md, the binding words, verbatim):
  OP-G3-1/2 「文ごとの 3 層パック。この文と次の文。1 文ずつ重ねて進む」「同じ記事の隣り合う 2 文」 -> the windows (slide.py)
  OP-G3-4   「軸ごとに判定し、一致した軸がそれぞれラベル付きの答えを出す」 -> one labelled entry per agreeing axis, never merged
  OP-G3-5   「文法層の十字の回転を「手」にして、助詞の腕をデータの腕に合わせる」, G2-f/G3 audit 「入力があると各ソブリンに投入して
            そこから両替機のように形でタンクに入れる」 -> the grammar layer decides the READ ORDER only (candidates are not changed)
  OP-G3-6   「梯子の順に x、y、z へ。重みは辺の流れと配置の結合と読む順に」 -> the weights are in slide_ratios; here only the order of axes
  M-2 / N-18 the amount of inference is the user's choice (T7b presets fast 4 / standard 10 / full unbounded) -> counted in WINDOWS
  Evaluation principle: candidates for users to grade, typed abstention, no single confident wrong answer.

What this module is.  The entrance of the window structure: (1) a WINDOW INDEX of a corpus (the placement records of slide_place for
a tier, cached on disk under the slide spec sha + the place spec sha + the corpus sha, a mismatch is refused); (2) the question
intake (cut like ask does, V2 function-word filter, the grammar reading and its FORM); (3) the choice of the windows to read (those
that hold a question unit: V1) and their order (grammar.read_order, then the preset cap, tied blocks never split); (4) the reading of
each window with slide_ratios.read_axes for every member of its class; (5) the result: one entry per (window, axis, agreed unit) in
the shape of a T7b entry plus the axis label, the window and the strict-stability flag, typed abstentions, and the verdict.
Nothing here changes an existing output: ask.py gets an opt-in `structure` keyword, slide_place / slide_ratios / grammar are only read.
All numbers are int / Fraction (a Fraction is written "n/d"); the module has no float and no division operator; the canonical bytes are
slide.canonical's.  Judgement points are numbered from L-640 (docs/LINE3_LOCAL_DECISIONS.md, section "G3-e").
"""
from __future__ import annotations

import json
import multiprocessing as mp
import os
import pickle
import random
import time
from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from verantyx.line3 import ask as A
from verantyx.line3 import cycle as cy
from verantyx.line3 import geometry as geo
from verantyx.line3 import grammar as gr
from verantyx.line3 import slide as SL
from verantyx.line3 import slide_place as SP
from verantyx.line3 import slide_ratios as SR
from verantyx.line3 import space as sp
from verantyx.line3.funcwords import default_filter
from verantyx.line3.granularity import SpanIndex

FORMAT = "line3.slide_query.v1"
CACHE_FORMAT = "line3.slide_windows.v1"
STRUCTURES: Tuple[str, ...] = ("flat", "slide")
MEMBERS: Tuple[str, ...] = ("all", "representative")
SKIPS: Tuple[str, ...] = ("exact", "none")
STRICT_POLICIES: Tuple[str, ...] = ("abstain", "mark")
WITHINS: Tuple[str, ...] = ("qcount", "none")
HOLDS: Tuple[str, ...] = ("seats", "sentences")
STANDIN_MODES: Tuple[str, ...] = ("off", "on")
TIER = "RUN"                                             # S1: the tier of the windows (L-640)

ANSWER = cy.ANSWER
CHOICE = cy.CHOICE
UNKNOWN_NO_WINDOW = "UNKNOWN_NO_WINDOW"
UNKNOWN_NOT_READ = "UNKNOWN_NOT_READ"
UNKNOWN_RATIO_DISAGREEMENT = cy.UNKNOWN_RATIO_DISAGREEMENT
UNKNOWN_SECTION_DISAGREEMENT = cy.UNKNOWN_SECTION_DISAGREEMENT
UNKNOWN_UNSTABLE = "UNKNOWN_UNSTABLE_AXIS_IMPROVABLE"
UNKNOWN_NO_EVIDENCE = cy.UNKNOWN_NO_EVIDENCE

# the typed abstentions of one (window, axis): slide_ratios' four + the three this module adds (L-646)
NO_QUESTION_UNIT = "no_question_unit"
NOT_GROUNDED = "not_grounded"
UNSTABLE = "unstable_axis_improvable"
MIXED = "mixed"
ABSTENTION_KINDS: Tuple[str, ...] = (SR.POINTS_NOWHERE, SR.SECTION_DISAGREEMENT, SR.RATIO_DISAGREEMENT, SR.NO_EDGES,
                                     NO_QUESTION_UNIT, NOT_GROUNDED, UNSTABLE, MIXED)


def _fs(x: Optional[Fraction]) -> Optional[str]:
    return None if x is None else "%d/%d" % (x.numerator, x.denominator)


def _canon_json(doc) -> dict:
    """A document in plain JSON form (Fractions as "n/d", tuples as lists): the form the cache stores and window_cross reads."""
    return json.loads(SL.canonical(doc))


# --------------------------------------------------------------------------------------------------------------
# (1) the window index: build, cache, load  (L-641)
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class WindowRec:
    """One window of the index: its place in the stream, the placement record (plain JSON form) and what the query path reads of it."""
    window: SL.Window
    constructed: bool
    pad: Optional[str]
    doc: Mapping                       # SlidePlacement.doc(members=True), canonical JSON form
    seated: frozenset                  # units on the seats of the representative (V1: "holds a question unit" = seated)
    seated_any: frozenset              # ... of any member of the class
    sentence_units: frozenset          # units of the window's sentences (including the ones the budget left unseated)
    class_size: int
    kind: gr.Kind                      # grammar kind of the window (G3 4.2; WORD records of its sentences, L-549)
    member_seated: Optional[Tuple[frozenset, ...]] = None    # per member, ONLY when the members seat different units (two growths); else None

    @property
    def n(self) -> int:
        return self.window.n

    def member_units(self, member: Optional[int]) -> frozenset:
        """The units on the seats of one member (None = of any member: the window-level candidate test)."""
        if member is None:
            return self.seated_any
        return self.seated if self.member_seated is None else self.member_seated[member]

    def centre_side(self, member: int) -> str:
        """The sentence the member's x arms hold: "this" (centre in N) or "next" (centre in N+1).  G3-c3 writes it per member in
        `centre_search.member_x_side` (members=True form); absent = one growth, "this" (L-657)."""
        cs = self.doc.get("centre_search")
        xs = cs.get("member_x_side") if isinstance(cs, Mapping) else None
        return xs[member] if xs and 0 <= member < len(xs) else "this"

    def member_pad(self, member: int) -> int:
        """Empty OUTER seats per arm that the record pads a member with (`record L - centre_search.member_L[i]`, G3-c3 L-623): a
        reader walking from the outer end must skip them; absent = 0."""
        cs = self.doc.get("centre_search")
        ml = cs.get("member_L") if isinstance(cs, Mapping) else None
        return int(self.doc["L"]) - int(ml[member]) if ml and 0 <= member < len(ml) else 0

    def readable(self, member: int) -> bool:
        """The member is strictly stable on some axis (the owner: read ONLY the strictly stable members, L-648)."""
        return any(self.stable_member(member, a) for a in SR.AXES)

    def stable(self, axis: str) -> bool:
        """`stable_strict` of the record (G3-c3, L-626): absent = True (the committed records carry none); a bool for the window (its
        representative), or a mapping axis -> bool."""
        v = self.doc.get("stable_strict", True)
        if isinstance(v, Mapping):
            return bool(v.get(axis, True))
        return bool(v)

    def stable_member(self, member: int, axis: str) -> bool:
        """The same for one member of the class: G3-c3 records `judgement.member_judgement[i].stable_strict` per member (members=True
        form); a member without that entry takes the window's flag (L-648)."""
        j = self.doc.get("judgement")
        mj = j.get("member_judgement") if isinstance(j, Mapping) else None
        if mj and 0 <= member < len(mj) and isinstance(mj[member], Mapping) and "stable_strict" in mj[member]:
            v = mj[member]["stable_strict"]
            return bool(v.get(axis, True)) if isinstance(v, Mapping) else bool(v)
        return self.stable(axis)


def cache_name(corpus_sha: str, tier: str, slide_sha: str, place_sha: str) -> str:
    return "slidewin_%s_%s_%s_%s.pkl" % (corpus_sha[:12], tier, slide_sha[:12], place_sha[:12])


_BG: dict = {}                                    # set before the fork; the children inherit it


def _build_one(i: int):
    t0 = time.monotonic_ns()
    p = SP.place_window(_BG["slide"], _BG["pws"][i], _BG["spec"])
    return i, _canon_json(p.doc(True)), (time.monotonic_ns() - t0) // 1000000          # milliseconds


class WindowIndex:
    """The placements of every window of a corpus at one tier (S1: RUN), plus the grammar kind of each window and the corpus pieces the
    reading needs (the space, the slide, the exact counts of a window on demand)."""

    def __init__(self, space: sp.Space, slide: SL.Slide, spec: "SP.PlaceSpec", docs: Sequence[Mapping], *,
                 grammar_records: Optional[gr.Records] = None, header: Optional[Mapping] = None) -> None:
        self.space, self.slide, self.spec = space, slide, spec
        self.tier = spec.tier
        self.header = dict(header or {})
        self.records = grammar_records if grammar_records is not None else gr.records_of_space(space)
        self.foundation = slide.spec.foundation
        self._counts: Dict[int, SL.WindowCounts] = {}
        self._span: Optional[SpanIndex] = None
        pws = SP.place_windows(slide, spec.padding)
        if len(pws) != len(docs):
            raise ValueError("the window cache holds %d windows, the corpus has %d" % (len(docs), len(pws)))
        recs: List[WindowRec] = []
        tsp = space.tiers[spec.tier]
        for pw, d in zip(pws, docs):
            w = pw.window
            dw = d["window"]
            if dw["n"] != w.n or tuple(dw["sids"]) != tuple(w.sids) or dw["title"] != w.title or bool(dw["constructed"]) != pw.constructed:
                raise ValueError("the window cache does not match the corpus at window %d" % w.n)
            if d.get("tier") != spec.tier or d.get("spec_sha256") != spec.sha256():
                raise ValueError("the window cache record %d is not for this place spec" % w.n)
            mem = d["members"]
            per = [frozenset(SP.unit_of(t) for t in m if t is not None) for m in mem]
            first = per[0]
            anyu = frozenset().union(*per)
            su = frozenset(u for sid in w.sids for u in tsp.sentence_units[sid])
            kind = gr.grammar_cross(self.records, w.n, w.sids).kind
            recs.append(WindowRec(w, pw.constructed, pw.pad, d, first, anyu, su, len(mem), kind,
                                  None if all(x == first for x in per) else tuple(per)))
        self.windows: Tuple[WindowRec, ...] = tuple(recs)
        self.by_n: Dict[int, WindowRec] = {r.n: r for r in recs}

    # ---- construction ---------------------------------------------------------------------------------------------
    @classmethod
    def from_space(cls, space: sp.Space, cache_dir: Optional[str] = None, *, rows: Optional[Sequence[Mapping]] = None,
                   tier: str = TIER, padding: str = "one", level: str = "mid", place_kw: Optional[Mapping] = None,
                   workers: int = 1, build: bool = True, log=None) -> "WindowIndex":
        """Load the windows of `space` from `cache_dir` (refusing any mismatch of the slide spec sha, the place spec sha, the corpus sha,
        the tier or the padding) or, when the cache file is absent and `build`, place them (fork pool, the result does not depend on the
        worker count) and write it.  `place_kw` = slide_place.make_spec's switches (None = the module defaults)."""
        if tier != TIER:
            raise ValueError("S1 reads the %s tier only (L-640)" % TIER)
        slide = SL.Slide(space, rows=rows)
        spec = SP.make_spec(slide, tier=tier, padding=padding, level=level, **dict(place_kw or {}))
        path = None if not cache_dir else os.path.join(
            cache_dir, cache_name(space.sha256(), tier, slide.spec.sha256(), spec.sha256()))
        if path and os.path.exists(path):
            with open(path, "rb") as f:
                d = pickle.load(f)
            cls._check_header(d, space, slide, spec, path)
            return cls(space, slide, spec, d["windows"], header=cls._header(d))
        if not build:
            raise FileNotFoundError("no window cache %s" % (path or "(no cache dir)"))
        docs, secs, wall = cls._place_all(slide, spec, workers, log)             # secs / wall in milliseconds
        header = {"format": CACHE_FORMAT, "corpus_sha256": space.sha256(), "slide_spec_sha256": slide.spec.sha256(),
                  "place_spec_sha256": spec.sha256(), "tier": tier, "padding": padding, "scope": spec.scope,
                  "switches": spec.switches(), "windows": len(docs), "wall_ms": wall, "cpu_ms": sum(secs)}
        if path:
            os.makedirs(cache_dir, exist_ok=True)
            tmp = path + ".part"
            with open(tmp, "wb") as f:
                pickle.dump(dict(header, windows=docs), f, protocol=pickle.HIGHEST_PROTOCOL)
            os.replace(tmp, path)
        return cls(space, slide, spec, docs, header=header)

    @classmethod
    def from_jsonl(cls, data: str, cache_dir: Optional[str] = None, **kw) -> "WindowIndex":
        rows = sp.load_jsonl(data)
        return cls.from_space(sp.build_space(rows), cache_dir, rows=rows, **kw)

    @staticmethod
    def _header(d: Mapping) -> dict:
        return {k: v for k, v in d.items() if k != "windows"}

    @staticmethod
    def _check_header(d: Mapping, space: sp.Space, slide: SL.Slide, spec: "SP.PlaceSpec", path: str) -> None:
        want = {"format": CACHE_FORMAT, "corpus_sha256": space.sha256(), "slide_spec_sha256": slide.spec.sha256(),
                "place_spec_sha256": spec.sha256(), "tier": spec.tier, "padding": spec.padding}
        for k, v in want.items():
            if d.get(k) != v:
                raise ValueError("window cache %s is not for this corpus / slide spec / place spec (%s: %r, wanted %r)"
                                 % (path, k, d.get(k), v))

    @staticmethod
    def _place_all(slide: SL.Slide, spec: "SP.PlaceSpec", workers: int, log=None):
        pws = SP.place_windows(slide, spec.padding)
        _BG.update(slide=slide, spec=spec, pws=pws)
        t0 = time.monotonic_ns()
        out: Dict[int, Tuple[dict, int]] = {}
        if workers <= 1:
            it = map(_build_one, range(len(pws)))
        else:
            it = mp.get_context("fork").Pool(workers).imap_unordered(_build_one, range(len(pws)))
        for k, (i, d, dt) in enumerate(it, 1):
            out[i] = (d, dt)
            if log and k % 50 == 0:
                log("%d/%d windows placed (%d s)" % (k, len(pws), (time.monotonic_ns() - t0) // 1000000000))
        docs = [out[i][0] for i in range(len(pws))]
        return docs, [out[i][1] for i in range(len(pws))], (time.monotonic_ns() - t0) // 1000000

    # ---- what a reading needs ---------------------------------------------------------------------------------------
    def counts(self, w: WindowRec) -> SL.WindowCounts:
        c = self._counts.get(w.n)
        if c is None:
            c = self._counts[w.n] = self.slide.counts(w.window, self.spec.scope)
        return c

    @property
    def span_index(self) -> SpanIndex:
        if self._span is None:
            self._span = self.slide.spans
        return self._span


# --------------------------------------------------------------------------------------------------------------
# (2) the question intake and the grammar FORM  (L-642, L-643)
# --------------------------------------------------------------------------------------------------------------
FORMS: Tuple[str, ...] = ("slot", "predicate", "standin", "plain")


@dataclass(frozen=True)
class Intake:
    question: str
    all_units: Tuple[str, ...]            # the question cut like the RUN tier
    units: Tuple[str, ...]                # ... after V2 (function / question words are not units)
    ctx: cy.QueryContext
    qset: frozenset                       # ctx.energy_units: the question units a window must hold (V1)
    reading: gr.QuestionReading
    form: str                             # slot | predicate | standin | plain
    slot: Optional[str]                   # the P7 particle that selects the match group (form "slot"), else None
    standins: Tuple[str, ...]             # RUN stand-in units of the unknown question units (code point order)

    def form_obj(self) -> dict:
        r = self.reading
        types: Dict[str, int] = {}
        for p in (r.pattern or ()):
            types[p.type] = types.get(p.type, 0) + 1
        return {"form": self.form, "slot": None if r.slot is None else r.slot.particle,
                "slot_phrase": None if r.slot is None else r.slot.phrase,
                "slot_after": None if r.slot is None else r.slot.after,
                "predicate": None if r.predicate is None else r.predicate.y,
                "predicate_of": None if r.predicate is None else r.predicate.x,
                "pattern_types": {k: types[k] for k in sorted(types)}, "standin_units": len(self.standins),
                "read_order": "kind of the window = the slot, then the ladder weight of the kind" if self.form == "slot"
                else "ladder weight of the kind (no slot particle)"}


def classify_form(reading: gr.QuestionReading) -> str:
    """L-642: slot (a P7 particle after the interrogative phrase) > predicate (the XのYは何ですか slot, L-548) > standin (an unknown
    RUN unit of the question: pattern type T2..T5) > plain."""
    if reading.slot_particle is not None and reading.slot_particle in gr.P7:
        return "slot"
    if reading.predicate is not None:
        return "predicate"
    if any(p.type != "T1" for p in (reading.pattern or ())):
        return "standin"
    return "plain"


def intake(index: WindowIndex, question: str) -> Intake:
    """The question as the flat path cuts it (cycle.split_question of the RUN tier, then V2: funcwords.default_filter), the QueryContext
    (I-07, cycle.make_context), and the grammar reading with its form (grammar.read_question over the same space)."""
    all_units = cy.split_question(TIER, question)
    flt = default_filter(TIER)
    units = tuple(u for u in all_units if not flt(u)) if flt is not None else tuple(all_units)
    ctx = cy.make_context(units)
    reading = gr.read_question(question, index.space, index.span_index)
    form = classify_form(reading)
    st = sorted({s.unit for p in (reading.pattern or ()) for s in p.standins if s.tier == TIER})
    return Intake(question, tuple(all_units), units, ctx, frozenset(ctx.energy_units), reading, form,
                  reading.slot_particle if form == "slot" else None, tuple(st))


def axis_order(slot: Optional[str], foundation: SL.Foundation) -> Tuple[str, ...]:
    """L-643 (G3 4.2 step 3): the axis whose arm carries the slot particle first (の: +x -> x), then the others by the axis weight
    (slide_ratios.read_order); with no slot, the axis weight order."""
    w = SR.foundation_weights(foundation)
    base = SR.read_order(w)
    if slot is None:
        return base
    lab = dict(foundation.arms)
    first = [a for a in base if any(lab[arm] == slot for arm in ("+" + a, "-" + a))]
    return tuple(first) + tuple(a for a in base if a not in first)


# --------------------------------------------------------------------------------------------------------------
# (3) which windows are read, in which order  (L-644, L-645)
# --------------------------------------------------------------------------------------------------------------
def holds(w: WindowRec, it: Intake, hold: str = "seats", standins: str = "off", member: Optional[int] = None) -> Tuple[int, int]:
    """(question units, stand-in units) the window holds.  V1: 'holds' = a unit on a seat of the window (hold "seats") or, as a variant,
    a unit of its sentences ("sentences", which includes units the budget left unseated).  Stand-ins count only when switched on."""
    units = w.member_units(member) if hold == "seats" else w.sentence_units
    h = len(units & it.qset)
    hs = len((units & frozenset(it.standins)) - it.qset) if standins == "on" else 0
    return h, hs


@dataclass(frozen=True)
class Block:
    """Windows read together or not at all (the tie that is never split): one grammar group, one value of the within-group key."""
    reason: str                           # grammar.Group.reason: match | particle | tied | none
    kind: gr.Kind
    key: Optional[Tuple[int, int]]        # (question units held, stand-in units held), None when within="none"
    windows: Tuple[int, ...]              # window numbers N, ascending (a label)

    def to_obj(self) -> list:
        return [self.reason, self.kind.to_obj(), None if self.key is None else list(self.key), list(self.windows)]


@dataclass(frozen=True)
class Plan:
    candidates: int                       # windows that hold a question unit
    blocks: Tuple[Block, ...]             # all candidate windows, in read order
    read: Tuple[int, ...]                 # the windows read (whole blocks), in read order
    unread: Tuple[int, ...]
    cap: Optional[int]                    # the node budget in windows (None = the whole read)
    boundary: int                         # windows of the first block the cap did not fit (the tie not split)
    order: str                            # "grammar" | "shuffle:<seed>"

    @property
    def partial(self) -> bool:
        return len(self.unread) > 0

    def read_obj(self) -> dict:
        return {"candidate_windows": self.candidates, "windows_read": len(self.read), "left_unread": len(self.unread),
                "would_read_in_full": self.candidates, "node_budget": self.cap, "tied_group_not_split": self.boundary,
                "order": self.order, "partial": self.partial}


def plan_windows(index: WindowIndex, it: Intake, *, hold: str = "seats", standins: str = "off", within: str = "qcount",
                 cap: Optional[int] = None, shuffle: Optional[int] = None) -> Plan:
    """The windows that hold a question unit (V1: exact skip, L-644), ordered by grammar.read_order (kind = the slot first when the
    question has a P7 slot, then the ladder weight of the kind; equal kinds are one group), then inside a group by the number of question
    units held (more first; "none" = no second key), equal values one block (L-645, L-G3-7).  `cap` windows are read as T7b reads
    crosses: whole blocks in order, the first block that does not fit stops the read.  `shuffle` (a test hook) permutes the blocks and
    the windows inside a block with a seeded generator."""
    if hold not in HOLDS or standins not in STANDIN_MODES or within not in WITHINS:
        raise ValueError("hold: %s; standins: %s; within: %s" % (HOLDS, STANDIN_MODES, WITHINS))
    if cap is not None and (isinstance(cap, bool) or not isinstance(cap, int) or cap < 0):
        raise ValueError("cap must be an integer >= 0")
    held = {w.n: holds(w, it, hold, standins) for w in index.windows}
    cand = [w for w in index.windows if held[w.n][0] > 0 or held[w.n][1] > 0]
    ro = gr.read_order(it.slot, [(w.n, w.kind) for w in cand])
    blocks: List[Block] = []
    for g in ro.groups:
        if within == "qcount":
            by: Dict[Tuple[int, int], List[int]] = {}
            for n in g.members:
                by.setdefault(held[n], []).append(n)
            for k in sorted(by, reverse=True):
                blocks.append(Block(g.reason, g.kind, k, tuple(sorted(by[k]))))
        else:
            blocks.append(Block(g.reason, g.kind, None, tuple(sorted(g.members))))
    order = "grammar"
    if shuffle is not None:
        rng = random.Random(shuffle)
        rng.shuffle(blocks)
        blocks = [Block(b.reason, b.kind, b.key, tuple(rng.sample(b.windows, len(b.windows)))) for b in blocks]
        order = "shuffle:%d" % shuffle
    rd: List[int] = []
    boundary = 0
    for b in blocks:
        if cap is not None and len(rd) + len(b.windows) > cap:
            boundary = len(b.windows)
            break
        rd.extend(b.windows)
    rs = set(rd)
    unread = tuple(n for b in blocks for n in b.windows if n not in rs)
    return Plan(len(cand), tuple(blocks), tuple(rd), unread, cap, boundary, order)


# --------------------------------------------------------------------------------------------------------------
# (4) reading one window: every member of the class, per axis, with the admission rules  (L-646..L-650)
# --------------------------------------------------------------------------------------------------------------
def _sids_of(a: SR.AxisAnswer) -> Tuple[int, ...]:
    """The sentences an answer traces to: the sentences of the unit's seats and of the counts' rows (x: (sid, ...); z: (sid N, sid N+1,
    ...); slide.XSrc / ZSrc)."""
    s = {x.sid for x in a.seats}
    for row in a.sources:
        if row[0] == "x" and len(row) > 1 and isinstance(row[1], int):
            s.add(row[1])
        elif row[0] == "z" and len(row) > 2 and isinstance(row[1], int) and isinstance(row[2], int):
            s.update((row[1], row[2]))
    return tuple(sorted(s))


def _centre(wc: SR.WindowCross) -> Optional[str]:
    c = wc.by_seat().get(geo.CENTER)
    return None if c is None else c.unit


@dataclass(frozen=True)
class WindowRead:
    window: int
    members_read: int
    class_size: int
    entries: Tuple[dict, ...]             # in axis order, units in code point order
    abstentions: Tuple[dict, ...]         # (window, axis) with no entry, typed
    tally: Tuple[Tuple[str, Tuple[Tuple[str, int], ...]], ...]    # per axis: (answered or abstained kind, members) in axis order
    trace_checks: int
    trace_ok: bool
    ms: int = 0


def member_cross(w: WindowRec, member: int) -> SR.WindowCross:
    """The cross of one member as a reader walks it.  A member that the record padded to the longest arm length (G3-c3, L-623) has
    `pad` empty OUTER seats per arm: they are skipped, the cross is read at the length the member was grown (and is stable) at.  Member 0
    keeps the seats' provenance rows; another member is read through the record's tokens (no seat sources), as slide_ratios does."""
    rec, pad = w.doc, w.member_pad(member)
    if pad == 0:
        return SR.window_cross(rec, member)
    L = int(rec["L"])
    if member == 0 and rec.get("seats") is not None:
        seats = [dict(x, position=x["position"] - pad) if x["arm"] != "centre" else dict(x) for x in rec["seats"]]
        return SR.window_cross(dict(rec, L=L - pad, seats=seats), 0)
    flat = rec["members"][member]
    cut = [flat[0]]
    for a in range(len(SR.ARM_NAMES)):
        cut.extend(flat[1 + a * L + pad: 1 + (a + 1) * L])
    d2 = {k: v for k, v in rec.items() if k != "seats"}
    d2.update(L=L - pad, members=[cut])
    return SR.window_cross(d2, 0)


def choose_members(w: WindowRec, members: str, strict: str) -> Tuple[List[int], int]:
    """(the member indices to read, the number skipped as not strictly stable).  strict "abstain" (default; the owner's rule, L-648):
    ONLY the strictly stable members are read, the others are counted `unstable_axis_improvable`; "mark" reads all and flags.
    members "all": every member read; "representative": the first member READ of each growth (centre sentence), in the order the
    growths first appear -- a window with two growths is never read on one of them (L-658)."""
    pool = [i for i in range(w.class_size) if strict == "mark" or w.readable(i)]
    skipped = w.class_size - len(pool)
    if members == "all":
        return pool, skipped
    first: Dict[str, int] = {}
    for i in pool:
        first.setdefault(w.centre_side(i), i)
    return sorted(first.values()), skipped


def read_window(index: WindowIndex, w: WindowRec, it: Intake, *, members: str = "all", agreement: str = "three",
                hold: str = "seats", standins: str = "off", gate: bool = True, strict: str = "abstain",
                axes: Optional[Sequence[str]] = None) -> WindowRead:
    """slide_ratios.read_axes on the members of the window's class (`choose_members`); per axis, one entry per distinct agreed unit
    (arrangements = the members that agree on it, the L-180 pattern; members of both growths, centre in N and centre in N+1, are read
    and an answer that both give is ONE entry, a different answer another: `centre_sentences` says which), never merged across axes.
    A member's agreement is admitted only if (1) the member holds a question unit (the window-level N-03 gate, L-646: this is what
    makes the exact skip exact), (2) the answer is grounded (L-647), (3) the axis is strictly stable for it (L-648).  What is not
    admitted is counted under its kind in the axis' typed abstention; members not read as unstable are counted there too."""
    if members not in MEMBERS or strict not in STRICT_POLICIES:
        raise ValueError("members: %s; strict: %s" % (MEMBERS, STRICT_POLICIES))
    t0 = time.monotonic_ns()
    rec = w.doc
    sel, skipped = choose_members(w, members, strict)
    wcs = [member_cross(w, i) for i in sel]
    ev = SR.counts_evidence(index.counts(w), index.tier)
    tsp = index.space.tiers[index.tier]
    axes = tuple(axes) if axes is not None else SR.read_order(SR.foundation_weights(index.foundation))
    reads = []
    checks, tr_ok = 0, True
    mem_ok: List[bool] = []
    for wc in wcs:
        r = SR.read_axes(wc, ev, tsp, it.ctx, index.foundation, z_self_edges=True, agreement=agreement)
        ok = True
        try:
            checks += SR.check_trace(r)
        except ValueError:
            ok = False
            tr_ok = False
        reads.append(r)
        mem_ok.append(ok)
    held = []
    for i in sel:
        h, hs = holds(w, it, hold, standins, i)
        held.append((h > 0 or hs > 0, h == 0))
    entries: List[dict] = []
    abst: List[dict] = []
    tally_out = []
    for ax in axes:
        by_unit: Dict[str, List[int]] = {}                 # unit -> positions in `sel` of the members that agree on it
        kinds: Dict[str, int] = {UNSTABLE: skipped} if skipped else {}
        for k, r in enumerate(reads):
            a = r.answer(ax)
            if a is None:
                kd = r.abstention(ax).kind
                kinds[kd] = kinds.get(kd, 0) + 1
                continue
            if gate and not held[k][0]:
                kinds[NO_QUESTION_UNIT] = kinds.get(NO_QUESTION_UNIT, 0) + 1
            elif a.grounded < 1 and a.section is not None:
                kinds[NOT_GROUNDED] = kinds.get(NOT_GROUNDED, 0) + 1
            elif strict == "abstain" and not w.stable_member(sel[k], ax):
                kinds[UNSTABLE] = kinds.get(UNSTABLE, 0) + 1
            else:
                by_unit.setdefault(a.unit, []).append(k)
        for u in sorted(by_unit):
            ks = by_unit[u]
            k0 = ks[0]
            a = reads[k0].answer(ax)
            sids = sorted({s for k in ks for s in _sids_of(reads[k].answer(ax))})
            path = sorted({st.frm[0] for st in a.walk_steps} | {st.to[0] for st in a.walk_steps} | {t.other[0] for t in a.edges} | {u})
            sides: Dict[str, int] = {}
            for k in ks:
                sd = w.centre_side(sel[k])
                sides[sd] = sides.get(sd, 0) + 1
            entries.append({
                "tier": index.tier, "structure": "slide", "axis": ax, "label": "slide:" + ax, "words": [u],
                "arrangements": len(ks), "centres": sorted({c for c in (_centre(wcs[k]) for k in ks) if c is not None}),
                "stability": None, "source_sids": sids,
                "window": {"n": w.n, "title": w.window.title, "sids": list(w.window.sids), "idx": list(w.window.idx),
                           "constructed": w.constructed},
                "centre_sentences": {sd: sides[sd] for sd in sorted(sides)},
                "stable_strict": all(w.stable_member(sel[k], ax) for k in ks), "via_standin": bool(held[k0][1] and standins == "on"),
                "ratios": {"section": a.section, "edge_flow": a.edge_flow, "binding": a.binding},
                "ratios_plain": {"edge_flow": a.edge_flow_plain, "binding": a.binding_plain},
                "member": sel[k0], "members_agreeing": len(ks), "members_read": len(sel), "class_size": w.class_size,
                "members_not_admitted": {kd: kinds[kd] for kd in sorted(kinds)}, "grounded": a.grounded, "agreement": agreement,
                "grammar_kind": w.kind.to_obj(), "path_words": path,
                "seats": [x.doc() for x in a.seats], "sources": [list(x) for x in a.sources],
                "trace": {"ok": all(mem_ok[k] for k in ks), "members_checked": len(ks)}})
        if not any(e["axis"] == ax for e in entries):
            kd = {k_: kinds[k_] for k_ in sorted(kinds)}
            abst.append({"window": w.n, "axis": ax, "label": "slide:" + ax, "kind": next(iter(kd)) if len(kd) == 1 else MIXED,
                         "kinds": kd, "members": len(sel) + skipped})     # read + not read as unstable (= the class under "all")
        tally_out.append((ax, tuple(sorted([("answer:" + u, len(by_unit[u])) for u in by_unit] + list(kinds.items())))))
    return WindowRead(w.n, len(sel), w.class_size, tuple(entries), tuple(abst), tuple(tally_out), checks, tr_ok,
                      (time.monotonic_ns() - t0) // 1000000)


# --------------------------------------------------------------------------------------------------------------
# (5) the result: entries, typed abstentions, the verdict, the bytes  (L-650..L-654)
# --------------------------------------------------------------------------------------------------------------
def verdict_of(n_entries: int, plan: Plan, abstentions: Sequence[Mapping]) -> str:
    """ANSWER = exactly one entry, CHOICE = a list (as ask.combine).  No entry: UNKNOWN_NO_WINDOW (no window holds a question unit),
    UNKNOWN_NOT_READ (windows hold one, the cap read none), else typed by the abstention kinds that were met, in this precedence
    (cycle._verdict_from's): ratio disagreement, section disagreement, unstable (strict), no evidence (L-651)."""
    if n_entries == 1:
        return ANSWER
    if n_entries > 1:
        return CHOICE
    if plan.candidates == 0:
        return UNKNOWN_NO_WINDOW
    if not plan.read:
        return UNKNOWN_NOT_READ
    met = {k for a in abstentions for k in a["kinds"]}
    if SR.RATIO_DISAGREEMENT in met:
        return UNKNOWN_RATIO_DISAGREEMENT
    if SR.SECTION_DISAGREEMENT in met:
        return UNKNOWN_SECTION_DISAGREEMENT
    if UNSTABLE in met:
        return UNKNOWN_UNSTABLE
    return UNKNOWN_NO_EVIDENCE


@dataclass(frozen=True)
class SlideAnswer:
    question: str
    intake: Intake
    plan: Plan
    reads: Tuple[WindowRead, ...]                   # every window read, in read order (candidates first)
    entries: Tuple[dict, ...]                       # in read order: window, then axis, then unit
    abstentions: Tuple[dict, ...]                   # of the planned windows
    verdict: str
    config: Mapping[str, object]
    spec: Mapping[str, str]                         # the shas the answer was made under (I-G3-4)
    sentences: Mapping[int, Tuple[str, str]]        # sid -> (text, source) of every sentence cited
    effort: Optional[str]
    ms: int = 0                                     # wall time, not part of the bytes

    # ---- reference helpers ----
    def entry_keys(self) -> Tuple[tuple, ...]:
        """The entries as a SET (window, axis, unit, arrangements, centres): what the order of reading must not change."""
        return tuple(sorted((e["window"]["n"], e["axis"], e["words"][0], e["arrangements"], tuple(e["centres"]),
                             SL.canonical(e["ratios"]), e["stable_strict"]) for e in self.entries))

    @property
    def windows_read(self) -> int:
        return len(self.reads)

    @property
    def partial(self) -> bool:
        return self.plan.partial

    def read_obj(self) -> dict:
        o = self.plan.read_obj()
        o.update({"effort": self.effort, "windows_read": len(self.reads), "skip": self.config["skip"],
                  "candidate_windows_read": len(self.plan.read)})
        return o

    def abstention_counts(self) -> Dict[str, int]:
        c: Dict[str, int] = {}
        for a in self.abstentions:
            c[a["kind"]] = c.get(a["kind"], 0) + 1
        return {k: c[k] for k in sorted(c)}

    # ---- output (N-08, N-10) ----
    def answer_obj(self) -> dict:
        one = self.verdict == ANSWER
        ents = list(self.entries)
        sids = sorted({s for e in ents for s in e["source_sids"]})
        return {"verdict": self.verdict, "structure": "slide", "tiers": [TIER], "listed": len(ents),
                "windows_read": len(self.reads), "partial": self.plan.partial, "grammar_form": self.intake.form_obj(),
                "read": self.read_obj(),
                "answer": ({"tier": TIER, "axis": ents[0]["axis"], "label": ents[0]["label"], "path_words": list(ents[0]["words"]),
                            "window": ents[0]["window"], "source_sids": ents[0]["source_sids"],
                            "reference_centres": ents[0]["centres"]} if one else None),
                "entries": ents, "abstentions": list(self.abstentions), "abstention_counts": self.abstention_counts(),
                "sources": [{"sid": s, "text": self.sentences[s][0], "source": self.sentences[s][1]} for s in sids]}

    def thought_obj(self) -> dict:
        it = self.intake
        reads = [{"window": r.window, "members_read": r.members_read, "class_size": r.class_size, "trace_checks": r.trace_checks,
                  "trace_ok": r.trace_ok, "tally": {a: {k: n for k, n in t} for a, t in r.tally}} for r in self.reads]
        return {"format": FORMAT, "question": self.question, "units_cut": list(it.all_units), "units": list(it.units),
                "first_layer": list(it.ctx.qcross.units), "grammar": it.reading.to_obj(), "grammar_form": it.form_obj(),
                "config": dict(self.config), "spec": dict(self.spec),
                "rule": ("windows that hold a question unit are read in grammar order (kind = the slot, then the ladder weight, then the "
                         "number of question units held); every member of a window's class is read; each agreeing axis gives its own "
                         "labelled entry, never merged across axes or windows; what is not admitted is a typed abstention"),
                "plan": {"read": self.plan.read_obj(), "blocks": [b.to_obj() for b in self.plan.blocks],
                         "read_windows": list(self.plan.read), "unread_windows": list(self.plan.unread)},
                "windows": reads, "abstentions": list(self.abstentions)}

    def to_json_obj(self) -> dict:
        return _canon_json({"answer": self.answer_obj(), "thought": self.thought_obj()})

    def to_bytes(self) -> bytes:
        return SL.canonical({"answer": self.answer_obj(), "thought": self.thought_obj()})


def window_index_for(index, *, cache_dir: Optional[str] = None, workers: int = 1, place_kw: Optional[Mapping] = None,
                     padding: str = "one", level: str = "mid") -> WindowIndex:
    """The WindowIndex of an ask.Index (kept on it): loaded from the index's cache directory when its window file is there, else placed
    in this process (slow: about 4 minutes of one core for fulllead; build it once with WindowIndex.from_jsonl(..., workers=N))."""
    if isinstance(index, WindowIndex):
        return index
    level = getattr(index, "level", level)                # the budget level of the flat index is the windows' too (cli --level)
    key = (padding, level, json.dumps(dict(place_kw or {}), sort_keys=True))
    store = index.__dict__.setdefault("_slide_windows", {})
    wi = store.get(key)
    if wi is None:
        wi = store[key] = WindowIndex.from_space(index.space, cache_dir or getattr(index, "cache_dir", None), padding=padding,
                                                 level=level, place_kw=place_kw, workers=workers)
    return wi


def ask_slide(index, question: str, *, effort: Optional[str] = None, nodes: Optional[int] = None,
              windows: Optional[WindowIndex] = None, agreement: str = "three", members: str = "all", skip: str = "exact",
              hold: str = "seats", standins: str = "off", within: str = "qcount", strict: str = "abstain", gate: bool = True,
              shuffle: Optional[int] = None, cache_dir: Optional[str] = None, workers: int = 1,
              place_kw: Optional[Mapping] = None) -> SlideAnswer:
    """`structure="slide"` (S1: tier RUN).  effort / nodes: the amount of inference as ask.resolve_effort (fast 4 / standard 10 / full
    unbounded windows; nodes N = N windows; neither = the whole read).  agreement: slide_ratios' rule ("three" | "two_if_single_edge").
    members: "all" (every member of the class) | "representative".  skip: "exact" (only the windows that hold a question unit are read)
    | "none" (every window is read; the admission gate drops what exact skip would not have read: the test of L-646).  The other
    switches are named in the module header.  Nothing is selected between axes, windows or members."""
    if skip not in SKIPS or members not in MEMBERS or strict not in STRICT_POLICIES:
        raise ValueError("skip: %s; members: %s; strict: %s" % (SKIPS, MEMBERS, STRICT_POLICIES))
    if agreement not in SR.AGREEMENTS:
        raise ValueError("agreement must be one of %r" % (SR.AGREEMENTS,))
    t0 = time.monotonic_ns()
    wi = windows if windows is not None else window_index_for(index, cache_dir=cache_dir, workers=workers, place_kw=place_kw)
    name, cap, _lv = A.resolve_effort(effort, nodes)
    it = intake(wi, question)
    plan = plan_windows(wi, it, hold=hold, standins=standins, within=within, cap=cap, shuffle=shuffle)
    ax = axis_order(it.slot, wi.foundation)
    kw = dict(members=members, agreement=agreement, hold=hold, standins=standins, gate=gate, strict=strict, axes=ax)
    reads = [read_window(wi, wi.by_n[n], it, **kw) for n in plan.read]
    if skip == "none":
        seen = {n for b in plan.blocks for n in b.windows}
        reads.extend(read_window(wi, w, it, **kw) for w in wi.windows if w.n not in seen)
    planned = set(plan.read)
    entries = tuple(e for r in reads if r.window in planned for e in r.entries)
    abst = tuple(a for r in reads if r.window in planned for a in r.abstentions)
    cited = sorted({s for e in entries for s in e["source_sids"]})
    cfg = {"agreement": agreement, "members": members, "skip": skip, "hold": hold, "standins": standins, "within": within,
           "strict": strict, "gate": gate, "z_self_edges": True, "tier": TIER, "effort": name, "node_budget": cap}
    spec = {"corpus_sha256": wi.space.sha256(), "slide_spec_sha256": wi.slide.spec.sha256(), "place_spec_sha256": wi.spec.sha256(),
            "grammar_foundation_sha256": gr.foundation_sha()}
    return SlideAnswer(question, it, plan, tuple(reads), entries, abst, verdict_of(len(entries), plan, abst), cfg, spec,
                       {s: wi.space.sentences[s] for s in cited}, name, (time.monotonic_ns() - t0) // 1000000)


# --------------------------------------------------------------------------------------------------------------
# text form for the command line
# --------------------------------------------------------------------------------------------------------------
def format_text(c: SlideAnswer, show_thought: bool = False) -> str:
    a = c.answer_obj()
    L: List[str] = []
    gf = a["grammar_form"]
    if a["verdict"] == ANSWER:
        e = a["entries"][0]
        L.append("答え (%s, 窓 %d): %s" % (e["label"], e["window"]["n"], " / ".join(e["words"])))
        L.append("  参考の中心: %s" % ", ".join(e["centres"]))
    elif a["verdict"] == CHOICE:
        L.append("候補 %d 件（窓と軸の印つきで並べています。軸どうし・窓どうしの票は足していません。選んでください）:" % a["listed"])
        for i, e in enumerate(a["entries"]):
            L.append("  [%d] (%s, 窓 %d: 文 %s) %s  中心: %s  並べ方 %d/%d  %s" % (
                i, e["label"], e["window"]["n"], "-".join(str(s) for s in e["window"]["sids"]), " / ".join(e["words"]),
                ", ".join(e["centres"]), e["members_agreeing"], e["members_read"],
                "" if e["stable_strict"] else "【厳密には不安定】"))
    else:
        L.append("答えなし: %s" % a["verdict"])
    rd = a["read"]
    if a["abstentions"]:
        L.append("棄権 (窓×軸): " + ", ".join("%s=%d" % kv for kv in sorted(a["abstention_counts"].items())))
    L.append("問いの形: %s%s  読んだ窓 %d / 候補の窓 %d" % (
        gf["form"], "（助詞 %s）" % gf["slot"] if gf["slot"] else "", rd["windows_read"], rd["candidate_windows"]))
    if a["partial"]:
        L.append("【部分読み】推論の量 %s（窓 %s 枚まで）: %d 枚読み・%d 枚は未読" % (
            rd["effort"], rd["node_budget"], rd["candidate_windows_read"], rd["left_unread"]))
        L.append("  未読の窓に正解があるかもしれません。時間をかけた答え（--effort full）で読み直せます。")
    for s in a["sources"]:
        L.append("  根拠 #%d: %s%s" % (s["sid"], s["text"], " [%s]" % s["source"] if s["source"] else ""))
    if show_thought:
        th = c.thought_obj()
        L.append("--- 思考過程 ---")
        L.append("問いの単位: %s  窓の読む順: %s" % (" ".join(th["units"]), " ".join(str(n) for n in th["plan"]["read_windows"]) or "なし"))
        L.append("設定: %s" % json.dumps(th["config"], ensure_ascii=False, sort_keys=True))
    return "\n".join(L)
