"""G3-g: ONE labelled candidate list from the flat cross, the layers and the sliding windows (ticket G3-g; docs/LINE3_LOCAL_DECISIONS.md section "G3-g", L-720..).

Owner (ops/decisions/2026-10-06_line3_faithful_build.md, 「G3-f の監査後の決定」, verbatim choices):
  「両方の候補を 1 つの一覧に並べる（出所のラベル付き）」          -- the flat cross (T10), the layers and the windows give ONE list, every candidate labelled by its origin;
  「両方を候補に並べて測る」                                        -- the windows' two evidence variants (plain, and the window's label-blind sum) are BOTH listed, marked;
  「窓の候補は常に一覧として出す（1 件でも「答え」にしない）」     -- a candidate that only windows give is never a single ANSWER.
Binding from before: I-14 / N-20 (a list is never shortened, no winner by order, nothing summed), I-16 (every source is read on its own: its own
search, its own read-out, its own typed abstentions; whether sources agree is only REPORTED), M-2 / N-18 (the user's amount of inference), the
evaluation principle (candidates for users to grade, typed abstention), P-4 (every output word traces), L-235 (entries with the same word set are one).

What this module is.  A pure COMBINER over finished source results plus a thin driver:
  * `Cand` = one entry of one source (origin, word set, centres, stability, arrangements, source sentences, per-word sentences, trace flag);
    `Source` = one source's result (verdict, its candidates, its typed abstentions, how much it read, its trace);  `combine(...)` merges them.
    The combiner never looks at how a Cand was made, so recorded results (the T10 sweep) can be replayed through it unchanged.
  * origins: `flat/<tier>` (ask.Combined, view "all"), `layers/<tier>/<layer><variant>` (matryoshka, stable-seats-path, the upper entries only: layer 0
    is the flat source), `window/plain` and `window/window-evidence` (slide_flat.ask_flat, evidence "plain" | "window").
  * ONE entry per word set: candidates with the same word set from different origins (or from different windows of one origin) are one entry that lists
    all its origins (`origins`) and every contributing candidate with its own details (`members`); nothing is summed, no stability is compared across
    members, different word sets are never merged (L-720, L-721).
  * the list order is the sources' own: flat (RUN, WORD, CHAR), layers (tier, layer, variant), window/plain, window/window-evidence; inside a source its
    own order; a merged entry stands where its first candidate stands.  No ranking.
  * the verdict (L-724): 1 entry with a non-window origin = ANSWER, 1 entry that only windows give = CHOICE (a list of one), >= 2 = CHOICE, 0 = the
    UNKNOWN of the first source that reports one, in the order flat, layers, window/plain, window/window-evidence (reporting precedence, selects nothing).
  * `ask_combined` runs the sources (ask.ask, matryoshka.ask_layered, slide_flat.ask_flat once or twice) and combines them; ask.ask(structure="combined")
    and `vera line3 ask --structure combined` call it.  Opt-in: every default of the other structures is unchanged.
G3-g2 (L-740..): the owner's decisions after G3-g.  `merge="none"` (DEFAULT) lists EVERY candidate as its own entry (I-16: no merging across sources; equal
word sets from different origins stay separate entries, L-220 / L-700 / L-740) and marks the agreement only (`also_in`: the other origins with the same word
set; never summed, never used to choose, L-741); the list is shown in per-origin BLOCKS (flat RUN, WORD, CHAR, layers, window/plain, window/window-evidence),
each block most stable first (exact Fractions; ties in the source's order, L-749), no ranking across blocks (L-743); the per-source typed abstentions are the FIRST thing shown (`header`, L-742); the
verdict rule is unchanged (L-724, applied to the entries as listed, L-744).  `merge="word_set"` is the G3-g form (one entry per word set), kept for comparison.
All numbers are int / Fraction (written "n/d"); there is no floating-point number and no random number; the canonical bytes are slide.canonical's.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

from verantyx.line3 import ask as A
from verantyx.line3 import cycle as cy
from verantyx.line3 import matryoshka as M
from verantyx.line3 import readout as ro
from verantyx.line3 import slide as SL
from verantyx.line3 import slide_flat as SF
from verantyx.line3 import slide_query as SQ
from verantyx.line3 import trace_check as TC
from verantyx.line3.space import TIERS

FORMAT = "line3.combined.v1"
ANSWER = A.ANSWER
CHOICE = A.CHOICE
UNKNOWN_NO_STATE = A.UNKNOWN_NO_STATE
NOT_STACKED = "NOT_STACKED"                           # the layers source when no layer was stacked: a report, not an UNKNOWN (L-724)

FLAT = "flat"
LAYERS = "layers"
WINDOW = "window"
WINDOW_EVIDENCES: Tuple[str, ...] = ("plain", "window", "both")      # `window_evidence` of ask_combined
EVIDENCE_LABEL = {"plain": "plain", "window": "window-evidence"}      # slide_flat's evidence -> the origin label (the second is the marked variant)
WINDOW_PLAIN = "window/plain"
WINDOW_EVID = "window/window-evidence"
MERGES: Tuple[str, ...] = ("none", "word_set")                        # G3-g2 (L-740): none = every candidate its own entry (default); word_set = G3-g's one entry per word set
MARK_WINDOW_EVIDENCE = "window_evidence_variant"                     # L-723: the mark of an entry that the window-evidence variant (L-714) gives
LAYER_VARIANTS: Tuple[str, ...] = ("A",)                              # T10's measured ssp: variant A, compress, no feedback
LAYER_GRANULARITY = "compress"
LAYER_CANDIDATE = "stable-seats-path"
SLIDE_MEMBERS = "representative"                                      # L-726: the cheap reading of G3-f (1-3 s per question); "all" is slide_flat's own default


def _fs(x: Optional[Fraction]) -> Optional[str]:
    return None if x is None else "%d/%d" % (x.numerator, x.denominator)


# --------------------------------------------------------------------------------------------------------------
# (1) origins and their order  (L-720)
# --------------------------------------------------------------------------------------------------------------
def flat_origin(tier: str) -> str:
    return "%s/%s" % (FLAT, tier)


def layer_origin(tier: str, layer: int, variant: str) -> str:
    return "%s/%s/%d%s" % (LAYERS, tier, layer, variant)


def window_origin(evidence: str) -> str:
    return "%s/%s" % (WINDOW, EVIDENCE_LABEL[evidence])


def family(origin: str) -> str:
    return origin.split("/", 1)[0]


def origin_key(origin: str) -> tuple:
    """The fixed order of origins: flat (RUN, WORD, CHAR), layers (tier, layer, variant), window/plain, window/window-evidence."""
    p = origin.split("/")
    if p[0] == FLAT:
        return (0, TIERS.index(p[1]), 0, "")
    if p[0] == LAYERS:
        i = 0
        while i < len(p[2]) and p[2][i].isdigit():
            i += 1
        return (1, TIERS.index(p[1]), int(p[2][:i]), p[2][i:])
    if p[0] == WINDOW:
        return (2, 0 if p[1] == "plain" else 1, 0, "")
    raise ValueError("unknown origin %r" % origin)


def block_of(origin: str) -> str:
    """L-743: the block an origin is shown in: flat/<tier> and the two window origins are a block each, ALL the layers origins are ONE block."""
    f = family(origin)
    return LAYERS if f == LAYERS else origin


def block_key(block: str) -> tuple:
    return (1, 0) if block == LAYERS else origin_key(block)[:2]


# --------------------------------------------------------------------------------------------------------------
# (2) a candidate and a source  (L-720)
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Cand:
    """One entry of one source."""
    origin: str
    words: Tuple[str, ...]
    centres: Tuple[str, ...] = ()
    stability: Optional[Fraction] = None
    arrangements: Optional[int] = None
    source_sids: Tuple[int, ...] = ()                                  # the sentences of the entry (as the source gives them)
    word_sources: Optional[Tuple[Tuple[str, Tuple[int, ...]], ...]] = None   # per word the sentences of its steps, when the source has them (P-4)
    trace_ok: Optional[bool] = None                                    # the source's own trace of this entry / run / read-out; None = not traced here
    detail: Mapping = field(default_factory=dict, compare=False)       # the origin's own labels (tier, layer, window, ...), JSON-able, str keys

    @property
    def key(self) -> Tuple[str, ...]:
        return tuple(sorted(set(self.words)))


@dataclass(frozen=True)
class Source:
    """One source's result: what it listed, how it ended, what it left out."""
    name: str                                                          # "flat" | "layers" | "window/plain" | "window/window-evidence"
    verdict: str
    cands: Tuple[Cand, ...]
    abstentions: Tuple[Mapping, ...] = ()                              # typed, per tier / run / window with no entry
    read: Mapping = field(default_factory=dict)                        # how much it read (counts), `partial` inside
    trace: Mapping = field(default_factory=dict)                       # {"words_checked", "ok", ...} of the source's own P-4 trace
    thought: Mapping = field(default_factory=dict)                     # the source's own thought (for the `thought` key)


def _source_rank(name: str) -> tuple:
    if name == FLAT:
        return (0, 0)
    if name == LAYERS:
        return (1, 0)
    if name == WINDOW_PLAIN:
        return (2, 0)
    if name == WINDOW_EVID:
        return (2, 1)
    raise ValueError("unknown source %r" % name)


# --------------------------------------------------------------------------------------------------------------
# (3) combining  (L-720 .. L-725)
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Entry:
    """One word set, with every candidate that gives it."""
    words: Tuple[str, ...]
    members: Tuple[Cand, ...]                                          # in list order (the sources' own)
    also_in: Tuple[str, ...] = ()                                      # G3-g2 (L-741), merge "none": the OTHER origins that give this word set (a mark only)

    @property
    def block(self) -> str:
        return block_of(self.members[0].origin)

    @property
    def origins(self) -> Tuple[str, ...]:
        return tuple(sorted({m.origin for m in self.members}, key=origin_key))

    @property
    def families(self) -> Tuple[str, ...]:
        return tuple(sorted({family(m.origin) for m in self.members}))

    @property
    def window_only(self) -> bool:
        return all(family(m.origin) == WINDOW for m in self.members)

    @property
    def marks(self) -> Tuple[str, ...]:
        return (MARK_WINDOW_EVIDENCE,) if any(m.origin == WINDOW_EVID for m in self.members) else ()

    @property
    def centres(self) -> Tuple[str, ...]:
        return tuple(sorted({c for m in self.members for c in m.centres}))

    @property
    def source_sids(self) -> Tuple[int, ...]:
        s = {x for m in self.members for x in m.source_sids}
        s.update(x for m in self.members if m.word_sources for _w, ss in m.word_sources for x in ss)
        return tuple(sorted(s))

    @property
    def trace_ok(self) -> Optional[bool]:
        t = [m.trace_ok for m in self.members]
        if any(x is False for x in t):
            return False
        return True if all(x is True for x in t) else None

    def word_provenance(self) -> Dict[str, List[dict]]:
        """Per word, per contributing candidate: the sentences of its steps (level "word", or "none" when the source records no step sentence for that
        word) or, where the source keeps only the entry's sentences, those (level "entry"); a candidate with no sentence recorded (a replayed record)
        gives no row."""
        out: Dict[str, List[dict]] = {}
        for w in self.words:
            rows = []
            for i, m in enumerate(self.members):
                ws = dict(m.word_sources) if m.word_sources is not None else None
                if ws is not None and w in ws:
                    # "none": the source records no step sentence for this word (a word alone on its path, or, with the window evidence, a word whose
                    # edge is evidenced only by the window's constructed pair count, L-714: the entry's trace says how many such words it holds)
                    rows.append({"origin": m.origin, "member": i, "level": "word" if ws[w] else "none", "sids": list(ws[w])})
                elif m.source_sids:
                    rows.append({"origin": m.origin, "member": i, "level": "entry", "sids": list(m.source_sids)})
            out[w] = rows
        return out

    def to_obj(self) -> dict:
        return {"words": list(self.words), "origins": list(self.origins), "families": list(self.families), "window_only": self.window_only,
                "marks": list(self.marks), "centres": list(self.centres), "source_sids": list(self.source_sids), "trace_ok": self.trace_ok,
                "members": [{"origin": m.origin, "centres": list(m.centres), "stability": _fs(m.stability), "arrangements": m.arrangements,
                             "source_sids": list(m.source_sids), "trace_ok": m.trace_ok, **{k: m.detail[k] for k in sorted(m.detail)}}
                            for m in self.members],
                "word_provenance": self.word_provenance()}


def order_blocks(cands: Sequence[Cand]) -> List[Cand]:
    """L-749: inside each block (the candidates arrive grouped by block) the entries stand in the block's own STABILITY order, most stable first (exact
    Fractions), the source's order breaking ties (a stable sort: a tie is a group in the source's order, nothing is picked among equal stabilities by
    position).  A block in which some candidate carries no stability (a replayed record that holds none) is not sorted: it stays in the source's order
    and `answer.blocks` marks it order="source"."""
    out: List[Cand] = []
    i = 0
    while i < len(cands):
        j = i
        b = block_of(cands[i].origin)
        while j < len(cands) and block_of(cands[j].origin) == b:
            j += 1
        blk = list(cands[i:j])
        if all(c.stability is not None for c in blk):
            blk.sort(key=lambda c: -c.stability)
        out.extend(blk)
        i = j
    return out


def build_entries(sources: Sequence[Source], how: str = "none") -> Tuple[Entry, ...]:
    """The list.  The candidates of the sources are taken in the fixed source order (flat, layers, window/plain, window/window-evidence), each source in its
    own order.
    how = "none" (G3-g2 default, L-740): every candidate is its own entry, in per-origin blocks (flat RUN, WORD, CHAR, layers, window/plain,
        window/window-evidence), each block ordered by its stability, most stable first, ties in the source's order (L-749); an entry carries `also_in` = the other origins
        with the same word set (a mark: nothing reads it).  Two windows of one origin with the same word set are two entries (L-700).
    how = "word_set" (G3-g, L-721): candidates with the same word set are ONE entry placed where its first candidate stands."""
    if how not in MERGES:
        raise ValueError("merge: %s" % " | ".join(MERGES))
    ordered: List[Cand] = []
    for s in sorted(sources, key=lambda s: _source_rank(s.name)):
        cs = list(s.cands)
        if how == "none":
            cs.sort(key=lambda c: block_key(block_of(c.origin)))      # stable: the source's own order survives inside a block
        ordered.extend(cs)
    if how == "none":
        ordered = order_blocks(ordered)
        by_key: Dict[tuple, set] = {}
        for c in ordered:
            by_key.setdefault(c.key, set()).add(c.origin)
        return tuple(Entry(c.key, (c,), tuple(sorted(by_key[c.key] - {c.origin}, key=origin_key))) for c in ordered)
    order: List[tuple] = []
    groups: Dict[tuple, List[Cand]] = {}
    for c in ordered:
        k = c.key
        if k not in groups:
            groups[k] = []
            order.append(k)
        groups[k].append(c)
    return tuple(Entry(k, tuple(groups[k])) for k in order)


merge = build_entries                                                  # the name G3-g used (its second argument is new)


def verdict_of(entries: Sequence[Entry], sources: Sequence[Source]) -> str:
    """L-724.  One entry some non-window origin gives = ANSWER; one entry that only windows give = CHOICE (the owner: window candidates are always a
    list); several = CHOICE; none: the first UNKNOWN a source reports, in the source order (a reporting precedence, nothing is selected by it)."""
    if len(entries) > 1:
        return CHOICE
    if len(entries) == 1:
        return CHOICE if entries[0].window_only else ANSWER
    for s in sorted(sources, key=lambda s: _source_rank(s.name)):
        if s.verdict not in (ANSWER, CHOICE):
            return s.verdict
    return UNKNOWN_NO_STATE


@dataclass(frozen=True)
class CombinedAnswer:
    question: str
    sources: Tuple[Source, ...]                       # in the fixed source order
    entries: Tuple[Entry, ...]
    verdict: str
    config: Mapping[str, object]
    sentences: Mapping[int, Tuple[str, str]]          # sid -> (text, source) of every sentence the list cites
    effort: Optional[str] = None
    ms: int = 0
    merge: str = "none"                               # G3-g2 (L-740)

    @property
    def listed(self) -> int:
        return len(self.entries)

    @property
    def listed_before_merge(self) -> int:
        return sum(len(s.cands) for s in self.sources)

    def per_source_listed(self) -> Dict[str, int]:
        return {s.name: len(s.cands) for s in self.sources}

    def abstentions(self) -> List[dict]:
        return [dict(a, source=s.name) for s in self.sources for a in s.abstentions]

    def abstention_counts(self) -> Dict[str, Dict[str, int]]:
        out: Dict[str, Dict[str, int]] = {}
        for s in self.sources:
            c: Dict[str, int] = {}
            for a in s.abstentions:
                c[a["kind"]] = c.get(a["kind"], 0) + 1
            if c:
                out[s.name] = {k: c[k] for k in sorted(c)}
        return out

    def header(self) -> List[dict]:
        """L-742: the per-source typed abstentions, shown FIRST.  One row per flat tier read, the layers, and each window variant read, in the fixed source
        order: {source, listed, kind, kinds}.  `listed` = the candidates of that source; `kind` = None when it listed something, else its typed abstention
        (the tier's / the source's verdict); `kinds` = {kind: n} over the typed abstentions of its parts (flat: the tier's; layers: runs without an entry;
        windows: windows without an entry), also where the source listed something.  Derived from the sources only; nothing is selected by it."""
        def counts(abst: Sequence[Mapping]) -> Dict[str, int]:
            c: Dict[str, int] = {}
            for a in abst:
                c[a["kind"]] = c.get(a["kind"], 0) + 1
            return {k: c[k] for k in sorted(c)}
        rows: List[dict] = []
        for s in self.sources:
            if s.name == FLAT:
                tiers = sorted({c.origin.split("/")[1] for c in s.cands} | {a["tier"] for a in s.abstentions if "tier" in a}, key=TIERS.index)
                if not tiers:
                    rows.append({"source": FLAT, "listed": 0, "kind": s.verdict, "kinds": counts(s.abstentions)})
                for t in tiers:
                    o = flat_origin(t)
                    n = sum(1 for c in s.cands if c.origin == o)
                    ab = [a for a in s.abstentions if a.get("tier") == t]
                    rows.append({"source": o, "listed": n, "kind": None if n else (ab[0]["kind"] if ab else s.verdict), "kinds": counts(ab)})
            else:
                n = len(s.cands)
                rows.append({"source": s.name, "listed": n, "kind": None if n else s.verdict, "kinds": counts(s.abstentions)})
        return rows

    def blocks(self) -> List[dict]:
        """L-743: the blocks of the list in the order shown: {block, listed, first, order} (`first` = the index of its first entry; an entry is in the
        block of its first member).  `order` (L-749) = "stability" (merge "none" and every entry of the block carries a stability: the block is sorted by it,
        most stable first, ties in the source's order) or "source" (the block stands in its source's order: merge "word_set", or a block whose candidates
        hold no stability, e.g. layers replayed from a record)."""
        out: List[dict] = []
        for i, e in enumerate(self.entries):
            if out and out[-1]["block"] == e.block:
                out[-1]["listed"] += 1
                out[-1]["_st"] = out[-1]["_st"] and e.members[0].stability is not None
            else:
                out.append({"block": e.block, "listed": 1, "first": i, "_st": e.members[0].stability is not None})
        for b in out:
            b["order"] = "stability" if self.merge == "none" and b.pop("_st") else "source"
            b.pop("_st", None)
        return out

    @property
    def partial(self) -> bool:
        return any(bool(s.read.get("partial")) for s in self.sources)

    @property
    def trace_ok(self) -> Optional[bool]:
        t = [s.trace.get("ok") for s in self.sources if s.cands]
        if any(x is False for x in t):
            return False
        return True if t and all(x is True for x in t) else None

    def answer_obj(self) -> dict:
        ents = [e.to_obj() for e in self.entries]
        if self.merge == "none":                                                 # G3-g2: the block and the agreement mark of each entry
            for d, e in zip(ents, self.entries):
                d["block"] = e.block
                d["also_in"] = list(e.also_in)
        one = self.verdict == ANSWER
        sids = sorted({s for e in self.entries for s in e.source_sids})
        return {"verdict": self.verdict, "structure": "combined", "merge": self.merge, "header": self.header(), "blocks": self.blocks(),
                "listed": len(ents), "listed_before_merge": self.listed_before_merge,
                "per_source_listed": self.per_source_listed(),
                "window_only_single": len(self.entries) == 1 and self.entries[0].window_only,
                "answer": ({"origins": ents[0]["origins"], "path_words": ents[0]["words"], "source_sids": ents[0]["source_sids"],
                            "reference_centres": ents[0]["centres"]} if one else None),
                "sources": [{"name": s.name, "verdict": s.verdict, "listed": len(s.cands), "read": dict(s.read), "trace": dict(s.trace)}
                            for s in self.sources],
                "partial": self.partial, "entries": ents, "abstentions": self.abstentions(), "abstention_counts": self.abstention_counts(),
                "cited": [{"sid": s, "text": self.sentences[s][0], "source": self.sentences[s][1]} for s in sids if s in self.sentences]}

    def rule_text(self) -> str:
        if self.merge == "none":
            return ("one list of the candidates of the flat cross (T10), the layers (stable-seats-path) and the sliding windows read flat, every one "
                    "labelled by its origin and shown in per-origin blocks (flat RUN, WORD, CHAR, layers, window/plain, window/window-evidence), each block ordered by "
                    "its stability (most stable first, ties in the source's order; a block whose candidates carry no stability stays in the source's order); candidates are NEVER merged across sources: equal word sets from different origins stay separate entries and "
                    "an agreement is shown as a mark only (also_in), never summed or used to choose; nothing is ranked across blocks or shortened; the windows' two "
                    "evidence variants are both listed, the window-evidence one marked; the per-source typed abstentions come first (header); an entry "
                    "only windows give is never a single ANSWER (a list of one is a CHOICE)")
        return ("one list of the candidates of the flat cross (T10), the layers (stable-seats-path) and the sliding windows read flat, every one "
                         "labelled by its origin; candidates with the same word set are one entry with all its origins, never merged across different "
                         "word sets; nothing is summed, ranked or shortened; the windows' two evidence variants are both listed, the window-evidence one "
                         "marked; an entry only windows give is never a single ANSWER (a list of one is a CHOICE); each source keeps its own typed "
                         "abstentions")

    def thought_obj(self) -> dict:
        return {"format": FORMAT, "question": self.question, "config": dict(self.config), "merge": self.merge,
                "rule": self.rule_text(),
                "sources": {s.name: {"verdict": s.verdict, "listed": len(s.cands), "read": dict(s.read), "trace": dict(s.trace),
                                     "abstentions": list(s.abstentions), "thought": dict(s.thought)} for s in self.sources},
                "agreement": self.agreement()}

    def agreement(self) -> dict:
        """REPORT ONLY: the families that give each word set (nothing is selected, counted or summed from it).  Counted over distinct word sets, so the
        numbers are the same in both merge modes (every candidate is in some entry in both, so `also_in` is not read here, L-741)."""
        by_key: Dict[tuple, set] = {}
        for e in self.entries:
            by_key.setdefault(e.words, set()).update(e.families)
        fam: Dict[str, int] = {}
        for fs in by_key.values():
            k = "+".join(sorted(fs))
            fam[k] = fam.get(k, 0) + 1
        return {"entries_by_families": {k: fam[k] for k in sorted(fam)}, "used_for_selection": False}

    def to_json_obj(self) -> dict:
        return json.loads(self.to_bytes().decode("utf-8"))

    def to_bytes(self) -> bytes:
        return SL.canonical({"answer": self.answer_obj(), "thought": self.thought_obj()})


def combine(question: str, sources: Sequence[Source], sentences: Optional[Mapping[int, Tuple[str, str]]] = None, *,
            config: Optional[Mapping[str, object]] = None, effort: Optional[str] = None, ms: int = 0, merge: str = "none") -> CombinedAnswer:
    """The combined list of finished source results (testable without a search; the experiments replay recorded results through it).  `merge` "none"
    (default, G3-g2) or "word_set" (G3-g): see build_entries."""
    names = [s.name for s in sources]
    if len(set(names)) != len(names):
        raise ValueError("a source is given twice: %s" % names)
    srcs = tuple(sorted(sources, key=lambda s: _source_rank(s.name)))
    for s in srcs:
        for c in s.cands:
            if family(c.origin) != family(s.name) or (family(s.name) == WINDOW and c.origin != s.name):
                raise ValueError("candidate origin %r does not belong to source %r" % (c.origin, s.name))
    ents = build_entries(srcs, merge)
    cited = {sid for e in ents for sid in e.source_sids}
    sent = {sid: sentences[sid] for sid in sorted(cited) if sentences is not None and sid in sentences}
    return CombinedAnswer(question, srcs, ents, verdict_of(ents, srcs), dict(config or {}), sent, effort, ms, merge)


# --------------------------------------------------------------------------------------------------------------
# (4) the adapters: a live result of each source -> Source  (L-725)
# --------------------------------------------------------------------------------------------------------------
def flat_source(c0: A.Combined, index=None) -> Source:
    """The flat cross, 3 tiers (ask.Combined, view "all"): one candidate per entry of every tier, origin flat/<tier>.  With `index` the read-out of every
    tier is traced (trace_check.trace_answer, L-153): the P-4 flag of its candidates."""
    if c0.view != "all":
        raise ValueError("the flat source is the view 'all' (every tier's candidates)")
    tr: Dict[str, dict] = {}
    cands: List[Cand] = []
    abst: List[dict] = []
    ms_ = set(c0.most_stable_tiers)
    for o in c0.outcomes:
        tok: Optional[bool] = None
        if index is not None and o.answer is not None and o.entries:
            _t, rep = TC.trace_answer(index.space.tiers[o.tier], o.answer)
            tr[o.tier] = {"words_checked": rep.words_checked, "words_traced": rep.words_traced, "ok": rep.ok}
            tok = rep.ok
        if not o.entries:
            abst.append({"tier": o.tier, "kind": o.verdict})
            continue
        for e in o.entries:
            cands.append(Cand(flat_origin(o.tier), tuple(e.words), tuple(e.centres), e.stability, e.count, tuple(e.source_sids),
                              tuple((w, tuple(ro.entry_word_sources(e, w))) for w in e.words), tok,
                              {"tier": o.tier, "tier_is_most_stable": o.tier in ms_}))
    trace = {"ok": (all(v["ok"] for v in tr.values()) if tr else None), "per_tier": tr} if index is not None else {}
    return Source(FLAT, c0.verdict, tuple(cands), tuple(abst), c0.read_obj(), trace, {})


def layers_source(lc: M.LayeredCombined) -> Source:
    """The layers (matryoshka, stable-seats-path): the UPPER entries only (layer 0 is the flat source), origin layers/<tier>/<layer><variant>."""
    cands: List[Cand] = []
    abst: List[dict] = []
    tr_ok: List[bool] = []
    words_checked = 0
    per_tier: Dict[str, dict] = {}
    partial = False
    for tl in lc.layers:
        per_tier[tl.tier] = {"triggered": tl.triggered, "runs": len(tl.runs)}
        for r in tl.runs:
            partial = partial or r.partial or r.layer_limit
            if not r.entries:
                abst.append({"tier": tl.tier, "layer": r.k, "variant": r.variant, "kind": r.verdict})
                continue
            tr_ok.append(bool(r.trace["ok"]))
            words_checked += r.trace["words_checked"]
            for e in r.entries:
                cands.append(Cand(layer_origin(tl.tier, e.layer, e.variant), tuple(e.words), tuple(e.centres), e.stability, e.arrangements,
                                  tuple(e.source_sids), e.word_sources, bool(r.trace["ok"]),
                                  {"tier": tl.tier, "layer": e.layer, "variant": e.variant, "bundles": list(e.bundles), "candidate": e.mode or "path"}))
    if cands:
        verdict = ANSWER if len(cands) == 1 else CHOICE
    elif not lc.stacked:
        verdict = NOT_STACKED                                          # the stability was kept at every read cross: nothing to report (L-724)
    else:
        verdict = next((r.verdict for tl in lc.layers for r in tl.runs), UNKNOWN_NO_STATE)
    read = {"stacked": lc.stacked, "partial": partial, "per_tier": per_tier}
    return Source(LAYERS, verdict, tuple(cands), tuple(abst), read,
                  {"ok": (all(tr_ok) if tr_ok else None), "words_checked": words_checked},
                  lc.thought_obj()["layers"])


def window_source(fa: SF.FlatAnswer, evidence: str) -> Source:
    """The sliding windows read as flat crosses (slide_flat), one evidence variant: one candidate per entry of every window read, origin
    window/plain | window/window-evidence.  The per-word sentences are there when ask_flat was asked with word_sources=True."""
    return window_source_of(evidence, fa.entries, fa.abstentions, fa.verdict, fa.read_obj(), [(r.trace_checks, r.trace_ok, bool(r.entries)) for r in fa.reads],
                            {"windows": fa.thought_obj()["windows"]})


def window_source_of(evidence: str, entries: Sequence[Mapping], abstentions: Sequence[Mapping], verdict: str, read: Mapping,
                     reads_trace: Sequence[Tuple[int, bool, bool]] = (), thought: Optional[Mapping] = None) -> Source:
    """window_source on the parts of a slide_flat.FlatAnswer (its entry dicts, abstentions, verdict, read object and, per window read, (trace checks,
    trace ok, has entries)): what a recorded window read holds is enough to rebuild the source."""
    origin = window_origin(evidence)
    cands = []
    for e in entries:
        ws = e.get("word_sources")
        cands.append(Cand(origin, tuple(e["words"]), tuple(e["centres"]), _frac(e["stability"]), e["arrangements"], tuple(e["source_sids"]),
                          None if ws is None else tuple((w, tuple(ws[w])) for w in e["words"]), bool(e["trace"]["ok"]),
                          {"window": e["window"], "centre_sentence": e["centre_sentence"], "stable_strict": e["stable_strict"],
                           "members_read": e["members_read"], "class_size": e["class_size"], "starts": e["starts"], "evidence": e["evidence"],
                           "axis_labels": e["axis_labels"], "trace": e["trace"]}))
    ok = [t for _c, t, has in reads_trace if has]
    abst = tuple(dict(a) for a in abstentions)
    if not cands and not abst:                                         # no window held a question unit / the cap read none: the source's own typed verdict
        abst = ({"kind": verdict, "windows": 0},)
    return Source(origin, verdict, tuple(cands), abst, read, {"ok": (all(ok) if ok else None), "words_checked": sum(c for c, _t, _h in reads_trace)},
                  thought or {})


def _frac(s: Optional[str]) -> Optional[Fraction]:
    if s is None:
        return None
    n, d = s.split("/")
    return Fraction(int(n), int(d))


# --------------------------------------------------------------------------------------------------------------
# (5) the driver  (L-726)
# --------------------------------------------------------------------------------------------------------------
def ask_combined(index, question: str, tiers: Optional[Sequence[str]] = None, budget: cy.QueryBudget = A.DEFAULT_BUDGET, *,
                 view: str = "all", effort: Optional[str] = None, nodes: Optional[int] = None, window_evidence: str = "both",
                 windows: Optional[SQ.WindowIndex] = None, slide_members: str = SLIDE_MEMBERS, read_order: str = "qcount_first",
                 layer_variants: Sequence[str] = LAYER_VARIANTS, layer_granularity: str = LAYER_GRANULARITY, z_deep: Optional[str] = None,
                 cache_dir: Optional[str] = None, workers: int = 1, place_kw: Optional[Mapping] = None, trace: bool = True, merge: str = "none") -> CombinedAnswer:
    """`structure="combined"` (G3-g, opt-in): the flat cross (ask.ask, `tiers` and `budget` as there), the layers (stable-seats-path, variants
    `layer_variants`, T10's measured configuration) on that same layer 0, and the sliding windows read flat (RUN; evidence plain, window or both),
    ONE list.  `effort` / `nodes` are each source's own amount (crosses per tier for the flat cross, the layers' bounds, WINDOWS for the windows);
    neither = the whole read.  Each source keeps its own search budget (the flat cross T7b's 64 / 8, the windows cycle's 512 / 64, L-705).
    `windows` = a slide_query.WindowIndex made beforehand, else the index's (built / loaded as ask_slide does).
    `merge` "none" (default, G3-g2: every candidate its own entry, in per-origin blocks, `also_in` marks) | "word_set" (G3-g: one entry per word set)."""
    if merge not in MERGES:
        raise ValueError("merge: %s" % " | ".join(MERGES))
    if view != "all":
        raise ValueError("structure='combined' lists every tier's candidates (view 'all'); the I-16 stable view is a different list")
    if window_evidence not in WINDOW_EVIDENCES:
        raise ValueError("window_evidence: %s" % " | ".join(WINDOW_EVIDENCES))
    if slide_members not in SQ.MEMBERS:
        raise ValueError("slide_members: %s" % " | ".join(SQ.MEMBERS))
    t0 = time.monotonic_ns()
    c0 = A.ask(index, question, tiers, budget, view="all", effort=effort, nodes=nodes)
    opts = M.LayerOptions(variants=tuple(layer_variants), granularity=layer_granularity, feedback="none", candidate=LAYER_CANDIDATE,
                          bounds=M.bounds_for(effort, nodes))
    lc = M.ask_layered(index, question, tiers, budget, options=opts, view="all", effort=effort, nodes=nodes, base=c0)
    wi = windows if windows is not None else SQ.window_index_for(index, cache_dir=cache_dir, workers=workers, place_kw=place_kw,
                                                                 z_deep=z_deep or "slide")
    evs = ("plain", "window") if window_evidence == "both" else (window_evidence,)
    fas = [(ev, SF.ask_flat(wi, question, effort=effort, nodes=nodes, members=slide_members, read_order=read_order, evidence=ev,
                            word_sources=True)) for ev in evs]
    srcs = [flat_source(c0, index if trace else None), layers_source(lc)] + [window_source(fa, ev) for ev, fa in fas]
    name, cap, _lv = A.resolve_effort(effort, nodes)
    cfg = {"effort": name, "node_budget": cap, "flat": {"tiers": [o.tier for o in c0.outcomes], "level": index.level},
           "layers": {"variants": list(opts.variants), "granularity": opts.granularity, "feedback": opts.feedback, "candidate": opts.candidate},
           "window": {"evidence": list(evs), "members": slide_members, "read_order": read_order, "z_deep": wi.z_deep,
                      "corpus_sha256": wi.space.sha256(), "slide_spec_sha256": wi.slide.spec.sha256(), "place_spec_sha256": wi.spec.sha256()}}
    if c0.placement is not None:
        cfg["flat"]["placement"] = dict(c0.placement)
    sent = _sentence_map(index, srcs)
    return combine(question, srcs, sent, config=cfg, effort=name, ms=(time.monotonic_ns() - t0) // 1000000, merge=merge)


def _sentence_map(index, srcs: Sequence[Source]) -> Dict[int, Tuple[str, str]]:
    n = len(index.space.sentences)
    sids = {x for s in srcs for c in s.cands for x in c.source_sids}
    sids.update(x for s in srcs for c in s.cands if c.word_sources for _w, ss in c.word_sources for x in ss)
    return {sid: index.space.sentences[sid] for sid in sorted(sids) if 0 <= sid < n}


# --------------------------------------------------------------------------------------------------------------
# (6) text form for the command line
# --------------------------------------------------------------------------------------------------------------
def format_text(c: CombinedAnswer, show_thought: bool = False) -> str:
    """The text form (G3-g2): the per-source typed abstentions FIRST (L-742), then the verdict and the list in per-origin blocks (L-743); an entry's
    agreement with other origins is a mark (`ほかの出所にも同じ語の集合`), not a merge."""
    a = c.answer_obj()
    L: List[str] = ["出所ごとの状況（候補の件数、または答えなしの種類）:"]
    for h in a["header"]:
        extra = ""
        if h["kinds"] and h["listed"]:
            extra = "（ほかに答えなしの部分（走り・窓）: %s）" % ", ".join("%s=%d" % kv for kv in h["kinds"].items())
        elif h["kinds"] and len(h["kinds"]) > 1:
            extra = "（内訳: %s）" % ", ".join("%s=%d" % kv for kv in h["kinds"].items())
        L.append("  %s: %s%s" % (h["source"], "候補 %d 件" % h["listed"] if h["listed"] else "答えなし %s" % h["kind"], extra))
    if a["verdict"] == ANSWER:
        L.append("答え (%s): %s" % (", ".join(a["answer"]["origins"]), " / ".join(a["answer"]["path_words"])))
        L.append("  参考の中心: %s" % ", ".join(a["answer"]["reference_centres"]))
    elif a["verdict"] == CHOICE:
        if a["merge"] == "none":
            L.append("候補 %d 件（平らな十字・層・窓の候補を出所ごとの区切りで並べています。各区切りは安定の高い順（同じ安定はその出所が出した順）です。安定の記録がない区切りは出所の順です。出所をまたいで束ねたり、足したり、順位をつけたりしていません。選んでください）:" % a["listed"])
        else:
            L.append("候補 %d 件（平らな十字・層・窓の候補を出所の印つきで 1 つの一覧に並べています。同じ語の集合は 1 件にまとめています。足したり順位をつけたりしていません。選んでください）:" % a["listed"])
        if a["window_only_single"]:
            L.append("  窓だけが出した候補が 1 件です。窓の候補は 1 件でも「答え」にしません。")
        bl = {b["first"]: b for b in a["blocks"]}
        for i, e in enumerate(a["entries"]):
            if i in bl:
                L.append(" == %s (%d 件) ==" % (bl[i]["block"], bl[i]["listed"]))
            if a["merge"] == "none":
                head = "  [%d]%s" % (i, "【窓の証拠の変種】" if e["marks"] else "")
                tail = "  中心: %s%s" % (", ".join(e["centres"]), "  ほかの出所にも同じ語の集合: %s" % ", ".join(e["also_in"]) if e["also_in"] else "")
                L.append("%s %s%s" % (head, " / ".join(e["words"]), tail))
            else:
                L.append("  [%d] (%s)%s %s  中心: %s" % (i, ", ".join(e["origins"]), "【窓の証拠の変種】" if e["marks"] else "",
                                                       " / ".join(e["words"]), ", ".join(e["centres"])))
    else:
        L.append("答えなし: %s" % a["verdict"])
    if a["merge"] == "none":
        L.append("出所ごとの件数 (一覧 %d 件、束ねていません): %s" % (a["listed"], " ".join("%s=%d" % (k, v) for k, v in a["per_source_listed"].items())))
    else:
        L.append("出所ごとの件数 (束ねる前 %d 件 -> 一覧 %d 件): %s" % (a["listed_before_merge"], a["listed"],
                                                             " ".join("%s=%d" % (k, v) for k, v in a["per_source_listed"].items())))
    for s in a["sources"]:
        L.append("  %s: 判定 %s / 候補 %d%s" % (s["name"], s["verdict"], s["listed"], " 【部分読み】" if s["read"].get("partial") else ""))
    for s in a["cited"]:
        L.append("  根拠 #%d: %s%s" % (s["sid"], s["text"], " [%s]" % s["source"] if s["source"] else ""))
    if show_thought:
        th = c.thought_obj()
        L.append("--- 思考過程 ---")
        for k, v in th["sources"].items():
            L.append("  [%s] 判定 %s / 候補 %d / 痕跡 %s" % (k, v["verdict"], v["listed"], v["trace"].get("ok")))
        L.append("出所の組み合わせ (報告のみ): %s" % ", ".join("%s=%d" % kv for kv in th["agreement"]["entries_by_families"].items()))
    return "\n".join(L)
