"""F2: build a multi-unit answer from the CONNECTIONS BETWEEN THE GRANULARITIES (docs/LINE3_F2_GRANULARITY.md).

Owner (2026-10-08): 「そのために様じまな粒度での接続があるのでそれを使って」 -- an answer that is not one unit
(ハッシュ表 = ハッシュ／表, カール・マルクス, 3万2,500キロワット) is built from the way the tiers RUN / WORD / CHAR are
connected.  The connection is the one the space already has (docs/LINE3_DESIGN.md 3.1): the three tiers cut the SAME
sentence, so a unit of one tier occupies a surface span [start, end) of that sentence, and a unit of another tier
whose span lies inside it is contained in it (RUN contains WORD contains CHAR, up to the cut each tier makes).
Nothing here is searched, scored or counted: it is a read of spans.

  occurrence  = (tier, sid, index in the tier's unit list of the sentence) with its span (L-480).
  assembling  = the occurrences that the listed entries point to in a source sentence, whose spans overlap or touch
                (the gap between them holds no letter, i.e. only characters every tier drops, L-32), are joined into
                one covering surface string; a joined string that is just one existing unit is not new (L-481).
  tiers       = each part keeps its own tier; the string is also checked against every tier: the tiers whose units tile
                it exactly (both ends on a unit boundary of that tier) are listed, `lifted_tier` is the coarsest (L-483).
  the parts are never replaced: the assembled string is an extra candidate that carries them (L-485).

Pure function of (space, entries); no float, no randomness, no hash-order dependence; the option is off by default
(`ask(..., granularity=None)`), so every existing output is byte-identical.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from verantyx.lang import ja_content_runs, strip_attribution
from verantyx.line3 import space as sp

TIER_ORDER: Tuple[str, ...] = sp.TIERS                 # RUN (coarsest), WORD, CHAR
SCOPES: Tuple[str, ...] = ("entry", "all")             # L-482
DEFAULT_SCOPE = "all"


# --------------------------------------------------------------------------------------------------------------
# spans of units in the sentence (L-480)
# --------------------------------------------------------------------------------------------------------------
def _letters(s: str) -> bool:
    return sp._has_letter(s)


def _pieces_off(text: str, lo: int, hi: int):
    """sp._pieces with offsets: the letter-like runs of text[lo:hi]."""
    cur = None
    for i in range(lo, hi):
        if sp._letterlike(text[i]):
            if cur is None:
                cur = i
        elif cur is not None:
            yield cur, i
            cur = None
    if cur is not None:
        yield cur, hi


def _raw_spans(tier: str, text: str) -> List[Tuple[str, int, int]]:
    """Every unit the tier's splitter yields (before the function-word filter), with its span in `text`."""
    out: List[Tuple[str, int, int]] = []
    if tier == sp.CHAR:
        return [(c, i, i + 1) for i, c in enumerate(text) if sp._letterlike(c)]
    if tier == sp.WORD:
        pos = 0
        for w in sp._get_tagger()(text):
            i = text.find(w.surface, pos)
            if i < 0:
                continue
            pos = i + len(w.surface)
            if sp._has_letter(w.surface):
                out.append((w.surface, i, pos))
        return out
    pos = 0                                              # RUN, as sp.units_run
    for r in ja_content_runs(text):
        i = text.find(r, pos)
        if i < 0:
            raise ValueError("content run not found in order: %r" % r)
        out.extend((text[a:b], a, b) for a, b in _pieces_off(text, pos, i))
        out.append((r, i, i + len(r)))
        pos = i + len(r)
    out.extend((text[a:b], a, b) for a, b in _pieces_off(text, pos, len(text)))
    return out


class SpanIndex:
    """Spans of the units of every tier of a Space, per sentence, computed on demand and cached.
    `spans(tier, sid)` = tuple of (start, end), one per unit of `space.tiers[tier].sentence_units[sid]`, in order;
    `text(sid)` = the string the spans refer to (the sentence after strip_attribution, what the tiers were cut from)."""

    def __init__(self, space: sp.Space) -> None:
        self.space = space
        self._text: Dict[int, str] = {}
        self._spans: Dict[Tuple[str, int], Tuple[Tuple[int, int], ...]] = {}
        self._fn: Dict[int, frozenset] = {}

    def text(self, sid: int) -> str:
        t = self._text.get(sid)
        if t is None:
            t = self._text[sid] = strip_attribution(self.space.sentences[sid][0])
        return t

    def spans(self, tier: str, sid: int) -> Tuple[Tuple[int, int], ...]:
        k = (tier, sid)
        r = self._spans.get(k)
        if r is None:
            r = self._spans[k] = self._compute(tier, sid)
        return r

    def function_cover(self, sid: int) -> frozenset:
        """Character positions inside a unit that the RUN or WORD cut made and the function-word rule (L-150) took out
        again (の, から, ...).  Used only by bridge=True (OP-F2-2)."""
        r = self._fn.get(sid)
        if r is None:
            text = self.text(sid)
            pos = set()
            for t in (sp.RUN, sp.WORD):
                flt = self.space.tiers[t].unit_filter
                if flt is None:
                    continue
                for u, a, b in _raw_spans(t, text):
                    if flt(u):
                        pos.update(range(a, b))
            r = self._fn[sid] = frozenset(pos)
        return r

    def _compute(self, tier: str, sid: int) -> Tuple[Tuple[int, int], ...]:
        ts = self.space.tiers[tier]
        units = ts.sentence_units[sid]
        text = self.text(sid)
        raw = _raw_spans(tier, text)
        flt = ts.unit_filter
        kept = [(u, a, b) for (u, a, b) in raw if not (flt is not None and flt(u))]
        if [u for u, _, _ in kept] != list(units):
            # cannot happen for a space built by space.build_space; refuse rather than guess (no silent skip)
            raise ValueError("units of %s sentence %d do not match the re-cut of its text" % (tier, sid))
        return tuple((a, b) for _, a, b in kept)


# --------------------------------------------------------------------------------------------------------------
# data
# --------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Part:
    tier: str
    idx: int                       # index in space.tiers[tier].sentence_units[sid]
    unit: str
    start: int
    end: int
    entries: Tuple[int, ...]       # indices (in the input list) of the entries whose word set holds this unit


@dataclass(frozen=True)
class Assembled:
    sid: int
    start: int
    end: int
    text: str                      # sentence[start:end]  (punctuation inside kept: it is surface)
    parts: Tuple[Part, ...]        # ordered by (start, end, tier); every part lies inside [start, end)
    aligned_tiers: Tuple[str, ...]  # tiers whose units tile the string exactly (L-483), in RUN, WORD, CHAR order
    entries: Tuple[int, ...]       # union of the parts' entries

    @property
    def lifted_tier(self) -> Optional[str]:
        return self.aligned_tiers[0] if self.aligned_tiers else None

    @property
    def part_tiers(self) -> Tuple[str, ...]:
        return tuple(t for t in TIER_ORDER if any(p.tier == t for p in self.parts))

    def obj(self) -> dict:
        return {"text": self.text, "sid": self.sid, "span": [self.start, self.end],
                "parts": [{"tier": p.tier, "unit": p.unit, "span": [p.start, p.end], "entries": list(p.entries)}
                          for p in self.parts],
                "part_tiers": list(self.part_tiers), "aligned_tiers": list(self.aligned_tiers),
                "lifted_tier": self.lifted_tier, "entries": list(self.entries)}


# --------------------------------------------------------------------------------------------------------------
# assembling
# --------------------------------------------------------------------------------------------------------------
def _tiles(index: SpanIndex, tier: str, sid: int, a: int, b: int) -> bool:
    """The units of `tier` tile [a, b): both ends are unit boundaries and every letter-like character of [a, b)
    belongs to a unit of the tier (a unit removed by the function-word filter breaks the tiling)."""
    inside = [(s, e) for s, e in index.spans(tier, sid) if s >= a and e <= b]
    if not inside or inside[0][0] != a or inside[-1][1] != b:
        return False
    text = index.text(sid)
    covered = set()
    for s, e in inside:
        covered.update(range(s, e))
    return all(i in covered for i in range(a, b) if sp._letterlike(text[i]))


def _gap_ok(index: SpanIndex, sid: int, text: str, lo: int, hi: int, bridge: bool) -> bool:
    if lo >= hi:
        return True
    if not _letters(text[lo:hi]):
        return True
    if bridge:
        fc = index.function_cover(sid)
        return all(i in fc for i in range(lo, hi) if sp._letterlike(text[i]))
    return False


def _join(index: SpanIndex, sid: int, parts: List[Part], bridge: bool = False) -> List[Assembled]:
    text = index.text(sid)
    parts = sorted(parts, key=lambda p: (p.start, p.end, TIER_ORDER.index(p.tier), p.idx))
    groups: List[List[Part]] = []
    cur_end = -1
    for p in parts:
        if groups and (p.start <= cur_end or _gap_ok(index, sid, text, cur_end, p.start, bridge)):
            groups[-1].append(p)
            cur_end = max(cur_end, p.end)
        else:
            groups.append([p])
            cur_end = p.end
    out = []
    for g in groups:
        a, b = g[0].start, max(p.end for p in g)
        if any(p.start == a and p.end == b for p in g):          # one existing unit covers it: nothing new (L-481)
            continue
        al = tuple(t for t in TIER_ORDER if _tiles(index, t, sid, a, b))
        out.append(Assembled(sid, a, b, text[a:b], tuple(g), al,
                             tuple(sorted({e for p in g for e in p.entries}))))
    return out


def _occurrences(index: SpanIndex, tier: str, sid: int, words: Iterable[str], ent: int) -> Dict[Tuple[str, int], Part]:
    ws = set(words)
    units = index.space.tiers[tier].sentence_units[sid]
    sps = index.spans(tier, sid)
    return {(tier, i): Part(tier, i, u, sps[i][0], sps[i][1], (ent,)) for i, u in enumerate(units) if u in ws}


def _merge_parts(dst: Dict[Tuple[str, int], Part], src: Mapping[Tuple[str, int], Part]) -> None:
    for k, p in src.items():
        q = dst.get(k)
        dst[k] = p if q is None else Part(q.tier, q.idx, q.unit, q.start, q.end, tuple(sorted(set(q.entries) | set(p.entries))))


def assemble(space: sp.Space, entries: Sequence[Tuple[str, Sequence[str], Iterable[int]]], scope: str = DEFAULT_SCOPE,
             index: Optional[SpanIndex] = None, bridge: bool = False) -> Tuple[Assembled, ...]:
    """entries = [(tier, words, source_sids), ...] (a Combined's `entries` as (tier, e.words, e.source_sids)).
    scope "entry": each entry alone (its own tier, its own sentences).  scope "all": the occurrences of all entries
    of all tiers that point into the same sentence are pooled, so units of different tiers join (L-482).
    Result ordered by (sid, start, end)."""
    if scope not in SCOPES:
        raise ValueError("scope: %s" % " | ".join(SCOPES))
    ix = index or SpanIndex(space)
    found: Dict[Tuple[int, int, int], Assembled] = {}
    if scope == "entry":
        for n, (tier, words, sids) in enumerate(entries):
            for sid in sorted(set(sids)):
                for a in _join(ix, sid, list(_occurrences(ix, tier, sid, words, n).values()), bridge):
                    k = (a.sid, a.start, a.end)
                    f = found.get(k)
                    found[k] = a if f is None else _combine(f, a)
    else:
        by_sid: Dict[int, Dict[Tuple[str, int], Part]] = {}
        for n, (tier, words, sids) in enumerate(entries):
            for sid in sorted(set(sids)):
                _merge_parts(by_sid.setdefault(sid, {}), _occurrences(ix, tier, sid, words, n))
        for sid in sorted(by_sid):
            for a in _join(ix, sid, list(by_sid[sid].values()), bridge):
                found[(a.sid, a.start, a.end)] = a
    return tuple(found[k] for k in sorted(found))


def _combine(x: Assembled, y: Assembled) -> Assembled:
    """The same span reached from two entries (scope "entry"): one string, the union of the parts."""
    d: Dict[Tuple[str, int], Part] = {}
    _merge_parts(d, {(p.tier, p.idx): p for p in x.parts})
    _merge_parts(d, {(p.tier, p.idx): p for p in y.parts})
    ps = tuple(sorted(d.values(), key=lambda p: (p.start, p.end, TIER_ORDER.index(p.tier), p.idx)))
    return Assembled(x.sid, x.start, x.end, x.text, ps, x.aligned_tiers, tuple(sorted(set(x.entries) | set(y.entries))))


def assemble_combined(c, space: sp.Space, scope: str = DEFAULT_SCOPE) -> dict:
    """The object attached to an ask result (`Combined.assembled`): the strings assembled from the entries the user
    was shown (`c.entries`, every tier in view "all").  Parts stay in the entries; this only adds candidates (L-485)."""
    ents = [(t, e.words, e.source_sids) for t, e in c.entries]
    res = assemble(space, ents, scope)
    return {"scope": scope, "n": len(res), "strings": [a.obj() for a in res],
            "rule": "F2: units of the tiers RUN/WORD/CHAR that the listed entries point to in the same source sentence "
                    "and whose spans overlap or touch are joined into one surface string; the parts stay as listed"}


def format_lines(obj: dict, limit: Optional[int] = None) -> List[str]:
    """Text form for the command line (L-486): the string, its sentence and its parts with their tiers."""
    L = ["つなげた候補 %d 件（粒度のつながりで組んだ文字列。元の候補は消していません。scope=%s）:" % (obj["n"], obj["scope"])]
    for i, s in enumerate(obj["strings"]):
        if limit is not None and i >= limit:
            L.append("  ... 残り %d 件" % (len(obj["strings"]) - limit))
            break
        L.append("  <%d> %s  (文 #%d %d-%d, 揃う段 %s)  部品: %s" % (
            i, s["text"], s["sid"], s["span"][0], s["span"][1], ",".join(s["aligned_tiers"]) or "なし",
            " ".join("%s:%s" % (p["tier"], p["unit"]) for p in s["parts"])))
    return L


# --------------------------------------------------------------------------------------------------------------
# traceability (independent of the assembling above: re-derives every claim from the space)
# --------------------------------------------------------------------------------------------------------------
def trace_check(space: sp.Space, a: Assembled, bridge: bool = False) -> List[str]:
    """Problems found for one assembled string; [] = every character maps to units of some tier and to the source
    sentence.  Checks against the sentence text and the tiers' unit lists only (no SpanIndex, no re-cut by the
    splitters); with bridge=True the function-word cover is taken from SpanIndex, i.e. the assembler's own code."""
    bad: List[str] = []
    text = strip_attribution(space.sentences[a.sid][0])
    if text[a.start:a.end] != a.text:
        bad.append("text is not the sentence span")
    for p in a.parts:
        units = space.tiers[p.tier].sentence_units[a.sid]
        if not (0 <= p.idx < len(units)) or units[p.idx] != p.unit:
            bad.append("part %s#%d is not a unit of the sentence" % (p.tier, p.idx))
            continue
        if text[p.start:p.end] != p.unit:
            bad.append("part %s#%d span does not show the unit" % (p.tier, p.idx))
        elif not (_fits(units[:p.idx], text[:p.start]) and _fits(units[p.idx + 1:], text[p.end:])):
            # the same surface elsewhere in the sentence: the units before/after idx must fit before/after the span
            bad.append("part %s#%d span is not the place of unit %d" % (p.tier, p.idx, p.idx))
        if not (a.start <= p.start and p.end <= a.end):
            bad.append("part %s#%d lies outside the string" % (p.tier, p.idx))
    cov = set()
    for p in a.parts:
        cov.update(range(p.start, p.end))
    for i in range(a.start, a.end):
        if i not in cov and sp._letterlike(text[i]) and not (bridge and i in SpanIndex(space).function_cover(a.sid)):
            bad.append("letter at %d is in no part" % i)
    # the string is connected: sorted by start, each part overlaps or touches the end so far through dropped characters only
    end = a.parts[0].end if a.parts else a.start
    for p in sorted(a.parts, key=lambda p: (p.start, p.end)):
        if p.start > end and _letters(text[end:p.start]) and not (bridge and _bridged(space, a.sid, text, end, p.start)):
            bad.append("gap with a letter before part %s#%d" % (p.tier, p.idx))
        end = max(end, p.end)
    return bad


def _fits(units: Sequence[str], s: str) -> bool:
    """The units occur in s in this order without overlapping (leftmost match)."""
    pos = 0
    for u in units:
        i = s.find(u, pos)
        if i < 0:
            return False
        pos = i + len(u)
    return True


def _bridged(space: sp.Space, sid: int, text: str, lo: int, hi: int) -> bool:
    return _gap_ok(SpanIndex(space), sid, text, lo, hi, True)
