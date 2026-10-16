"""Incremental pieces of the memory structure (L-PUB-160..): the same bytes as the plain code, without the per-write O(n) rebuild.

Nothing here changes a result.  Every function has a plain counterpart in `verantyx.loom` that stays the reference; `VERA_ACCEL=py` runs only that.

  IncCorpus      a `Corpus` made by APPENDING one row to the corpus of the rows before it: the Space (sentences, kinds, the three tiers, postings), the three adhesion tables
                 (evidence included) and the lazy caches (placement weights, span index, particle-after index) are carried, never rebuilt.  `Corpus(bytes)` builds the
                 same objects from scratch: equal for equal bytes (tests/line3/test_accel.py compares them object for object and by sha on random sentences).
                 `space_sha` / `adhesion_sha` / `seats_sha` are computed on first read (only a session's `begin` header reads them), the value is the plain one.
  rows_bytes     `memory.rows_bytes` with a memo of the canonical line of every row (a row is keyed by every field `row_line` reads).
  state_sha      `MemRun.mem_state_sha` with a memo of the canonical JSON of every unit and cross, keyed by a fingerprint of everything `to_obj` reads (a unit's `prov`
                 holds the snapshot list of the sids of its surface: that is what made the plain hash O(n) per row AND large).

Nothing in this module reads a clock, a file, the network or the environment; it is imported by `verantyx.accel` only when `VERA_ACCEL` is not `py`.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from verantyx.lang import strip_attribution
from verantyx.line3 import foundation as fd
from verantyx.line3 import grammar as grm
from verantyx.line3 import granularity as gr
from verantyx.line3 import placement as pl
from verantyx.line3 import space as sp
from verantyx.loom import corpus as _corpus
from verantyx.loom.corpus import Corpus, parse_rows

TIERS = sp.TIERS


# ------------------------------------------------------------------------------------------------------------
# the weights cache (the C kernels, when the library is loaded, answer the misses)
# ------------------------------------------------------------------------------------------------------------
class _CMirror:
    """A tier's postings kept in a C array (see cbind): shared by the corpora of one chain, each reads only the sentences below its own N (`limit`)."""
    __slots__ = ("h", "ids", "n_sent")

    def __init__(self, h: Any, ids: Dict[str, int], n_sent: int) -> None:
        self.h, self.ids, self.n_sent = h, ids, n_sent


def _new_weights(tier: sp.TierSpace, mirror: Optional[_CMirror], limit: int) -> pl.Weights:
    if mirror is None:
        return pl.Weights(tier)
    from verantyx.accel import cbind
    return cbind.CWeights(tier, mirror, limit)


class IncCorpus(Corpus):
    """See the module docstring.  Built by `extend` / `adopt` / `empty`; never by `__init__` (the plain constructor is the reference)."""

    def __init__(self) -> None:                       # pragma: no cover - use IncCorpus.empty / extend / adopt
        raise TypeError("IncCorpus is made by IncCorpus.empty(), .extend() or .adopt()")

    # -- lazy shas (the plain Corpus computes them in __init__) --------------------------------------------------
    @property
    def space_sha(self) -> str:                       # type: ignore[override]
        v = self.__dict__.get("_space_sha")
        if v is None:
            v = self.__dict__["_space_sha"] = self.space.sha256()
        return v

    @property
    def adhesion_sha(self) -> Dict[str, str]:         # type: ignore[override]
        v = self.__dict__.get("_adhesion_sha")
        if v is None:
            v = self.__dict__["_adhesion_sha"] = {t: self.adhesion[t].sha256() for t in TIERS}
        return v

    @property
    def seats_sha(self) -> str:                       # type: ignore[override]
        v = self.__dict__.get("_seats_sha")
        if v is None:
            v = self.__dict__["_seats_sha"] = fd.seats_sha()
        return v

    # -- construction ------------------------------------------------------------------------------------------------
    @staticmethod
    def _bare() -> "IncCorpus":
        return object.__new__(IncCorpus)

    @staticmethod
    def empty(data: bytes = b"") -> "IncCorpus":
        """The corpus of no rows (`Corpus(b"")`), built by the plain code so the empty tiers carry the plain filter objects."""
        return IncCorpus.adopt(Corpus(data))

    @staticmethod
    def adopt(c: Corpus) -> "IncCorpus":
        """A plain corpus as an IncCorpus (shares every object)."""
        n = IncCorpus._bare()
        d = dict(c.__dict__)
        for k in ("space_sha", "adhesion_sha", "seats_sha"):
            if k in d:
                d["_" + k] = d.pop(k)
        n.__dict__.update(d)
        n.__dict__.setdefault("_cm", {})
        n.__dict__["_view_gp"] = None
        return n

    def rebased(self, data: bytes) -> "IncCorpus":    # type: ignore[override]
        a = parse_rows(data)
        if len(a) != self.space.N or any((r["sent"], r.get("source") or "", r.get("kind") or "base") != (self.space.sentences[i][0], self.space.sentences[i][1], self.space.kinds[i]) for i, r in enumerate(a)):
            raise ValueError("rebased: the rows differ in what the space reads")
        return self._same_space(data)

    def _same_space(self, data: bytes) -> "IncCorpus":
        """The corpus of `data`, which differs from this corpus's bytes only in keys the space does not read: every object is shared, `corpus_sha` is the sha of `data`."""
        n = IncCorpus._bare()
        n.__dict__.update(self.__dict__)
        n.__dict__["corpus_sha"] = hashlib.sha256(data).hexdigest()
        _alias_views(self.corpus_sha, n.corpus_sha, self.space.N)
        return n

    def extend(self, row: dict, data: bytes) -> "IncCorpus":
        """The corpus of `data` = this corpus's bytes + the canonical line of `row` (`row` is the parsed line).  Exactly `Corpus(data)`."""
        space = self.space
        sid = space.N
        sentences, kinds = sp._rows([row])                 # the plain checks (an unknown kind raises ValueError)
        sent, source = sentences[0]
        kind = kinds[0]
        text = strip_attribution(sent)
        tiers: Dict[str, sp.TierSpace] = {}
        new_units: Dict[str, FrozenSet[str]] = {}
        for name in TIERS:
            ts = space.tiers[name]
            flt = ts.unit_filter
            split = sp._SPLITTERS[name]
            us = tuple(split(text)) if flt is None else tuple(u for u in split(text) if not flt(u))
            post = dict(ts.postings)
            for u in dict.fromkeys(us):
                old = post.get(u)
                post[u] = (sid,) if old is None else old + (sid,)
            tiers[name] = sp.TierSpace(name, ts.sentence_units + (us,), post, flt)
            new_units[name] = frozenset(us)
        new_space = sp.Space(space.sentences + ((sent, source),), tiers, space.kinds + (kind,))
        # -- the adhesion tables: the records of the new sentence only (a record reads its own sentence and nothing else) -------------
        recs: Dict[str, List[fd.Record]] = {t: [] for t in TIERS}
        if kind == sp.BASE:
            att = grm._build([(sid, sent)], new_space.N).attachments
            for a in att:
                recs[a.tier].append(fd.Record(a.tier, a.sid, a.start, a.end, a.unit, a.particle, a.p_start, a.p_end))
            recs[sp.CHAR] = fd.char_records([(sid, sent)])
        adhesion = {t: _adh_extend(self.adhesion[t], recs[t]) for t in TIERS}
        n = IncCorpus._bare()
        d = n.__dict__
        d["corpus_sha"] = hashlib.sha256(data).hexdigest()
        d["space"] = new_space
        d["adhesion"] = adhesion
        d["_weights"] = {}
        d["_spans"] = None
        d["_follow"] = {}
        d["_cm"] = {}
        d["_view_gp"] = self.corpus_sha
        # -- the caches the parent had built: carried, minus what the new sentence can change -------------------------------------
        for name, w in self._weights.items():
            sset = new_units[name]
            cache = {k: v for k, v in w._c.items() if k[0] not in sset and k[1] not in sset}
            m = self._cm.get(name)
            if m is not None:
                from verantyx.accel import cbind
                m = d["_cm"][name] = cbind.mirror_append(m, tiers[name], sid)
            nw = _new_weights(tiers[name], m, sid + 1)
            nw._c = cache
            d["_weights"][name] = nw
        if self._spans is not None:
            ix = gr.SpanIndex(new_space)
            ix._text = dict(self._spans._text)
            ix._spans = dict(self._spans._spans)
            ix._fn = dict(self._spans._fn)
            d["_spans"] = ix
        for tier, idx in self._follow.items():
            nidx = dict(idx)
            m: Dict[Tuple[int, int], str] = {}
            for r in recs[tier]:
                if r.particle in n_ladder():
                    m[(r.start, r.end)] = r.particle
            if m:
                nidx[sid] = m
            d["_follow"][tier] = nidx
        _alias_views(self.corpus_sha, d["corpus_sha"], space.N, drop=self.__dict__.get("_view_gp"))
        return n

    # -- weights: a Weights whose misses may be answered by the C kernels -------------------------------------------------
    def weights(self, name: str) -> pl.Weights:       # type: ignore[override]
        w = self._weights.get(name)
        if w is None:
            m = self._mirror(name)
            w = self._weights[name] = _new_weights(self.tier(name), m, self.space.N)
        return w

    def _mirror(self, name: str) -> Optional[_CMirror]:
        from verantyx import accel
        if accel.mode() != "c":
            return None
        m = self._cm.get(name)
        if m is None:
            from verantyx.accel import cbind
            m = self._cm[name] = cbind.mirror_of(self.tier(name))
        return m


def n_ladder() -> Tuple[str, ...]:
    return fd.DEFAULT_SPEC.ladder


def _adh_extend(parent: fd.Adhesion, new: List[fd.Record]) -> fd.Adhesion:
    """`Adhesion.from_records` over the records of all sentences, given the table of all but the newest sentence and the records of the newest (its sid is the largest, so its records
    come last in the sorted order that `from_records` iterates in)."""
    spec = parent.spec
    by_key: Dict[Tuple[str, str], List[fd.Record]] = {}
    for r in sorted(new):
        if r.tier != parent.tier:
            raise ValueError("record of tier %s in the table of %s" % (r.tier, parent.tier))
        if r.particle not in spec.ladder:
            continue
        by_key.setdefault((r.unit, r.particle), []).append(r)
    if not by_key:
        return parent
    a = object.__new__(fd.Adhesion)
    a.tier = parent.tier
    a.spec = spec
    counts = dict(parent.counts)
    ev = dict(parent._ev)
    rows = dict(parent._rows)
    new_key = False
    for k, rs in by_key.items():
        if k in counts:
            counts[k] += 1
        else:
            counts[k] = 1
            new_key = True
        ev[k] = ev.get(k, ()) + tuple(rs)
    if new_key:
        counts = dict(sorted(counts.items()))
    nums = spec.numerators
    new_unit = False
    for u in {k[0] for k in by_key}:
        row = [0] * len(nums)
        for p in spec.ladder:
            n = counts.get((u, p))
            if n:
                i = spec.ladder.index(p)
                row[i] = nums[i] * n
        if u not in rows:
            new_unit = True
        rows[u] = tuple(row)
    if new_unit:
        rows = dict(sorted(rows.items()))
    a.counts, a._ev, a._rows = counts, ev, rows
    return a


# ------------------------------------------------------------------------------------------------------------
# the process-wide view cache of the gate (evidence._VIEWS: (corpus sha, sid) -> SentenceView, a pure function of the sentence)
# ------------------------------------------------------------------------------------------------------------
def _alias_views(parent_sha: str, child_sha: str, n: int, drop: Optional[str] = None) -> None:
    """The view of sentence `sid` is the same object in every corpus that holds that sentence: alias the parent's views to the child, and forget the grandparent's (bounded memory)."""
    from verantyx.loom import evidence
    V = evidence._VIEWS
    if not V:
        return
    for sid in range(n):
        v = V.get((parent_sha, sid))
        if v is not None:
            V[(child_sha, sid)] = v
        if drop is not None:
            V.pop((drop, sid), None)


# ------------------------------------------------------------------------------------------------------------
# the chain of corpora: Corpus(bytes) -> IncCorpus
# ------------------------------------------------------------------------------------------------------------
_RECENT: List[Tuple[bytes, IncCorpus]] = []
_RECENT_MAX = 6
_TAIL_MAX = 8            # a tail of more rows than this is built by the plain code (the append path copies the tiers once per row)


def corpus_of(data: bytes) -> IncCorpus:
    """`Corpus(data)`, as an IncCorpus: appended to the longest recent corpus whose bytes are a prefix of `data`, else built by the plain code."""
    best: Optional[Tuple[bytes, IncCorpus]] = None
    for b, c in _RECENT:
        if len(b) <= len(data) and (not b or b.endswith(b"\n")) and data.startswith(b) and (best is None or len(b) > len(best[0])):
            best = (b, c)
    if best is not None:
        b, c = best
        if b == data:
            return c
        lines = data[len(b):].decode("utf-8").splitlines(True)
        if sum(1 for ln in lines if ln.strip()) <= _TAIL_MAX:
            pos = len(b)
            for ln in lines:
                pos += len(ln.encode("utf-8"))
                if ln.strip():
                    c = c.extend(_json_loads(ln), data[:pos])
            if c is best[1]:                                     # only blank lines were added: the space is the same, the bytes are not
                c = c._same_space(data)
            elif pos != len(data):                               # cannot happen (the lines are the whole tail); keep the plain path honest
                c = None
            if c is not None:
                _remember(data, c)
                return c
    c = IncCorpus.adopt(Corpus(data))
    _remember(data, c)
    return c


def corpus_of_rows(rows: Any, lines: List[str]) -> IncCorpus:
    """`Corpus(rows_bytes(rows))` as an IncCorpus, where `lines` are the canonical lines of `rows`.  The parent is found by what the SPACE reads (sentence, source, kind): a row whose other
    fields changed after its corpus was built (memory._write_v4 sets `clause_at` on the row it has just written) still has its corpus as the parent; only `corpus_sha` is new."""
    data = "".join(lines).encode("utf-8")
    n = len(rows)
    sents = tuple([(r["sent"], r.get("source") or "") for r in rows])
    kinds = tuple([r.get("kind") or sp.BASE for r in rows])
    best: Optional[IncCorpus] = None
    for _, c in _RECENT:
        N = c.space.N
        if N <= n and (best is None or N > best.space.N) and sents[:N] == c.space.sentences and kinds[:N] == c.space.kinds:
            best = c
    if best is not None and n - best.space.N <= _TAIL_MAX:
        c = best
        if best.space.N == n:
            c = c if c.corpus_sha == hashlib.sha256(data).hexdigest() else c._same_space(data)
        else:
            for k in range(best.space.N, n):
                c = c.extend(rows[k], data if k == n - 1 else "".join(lines[:k + 1]).encode("utf-8"))
        _remember(data, c)
        return c
    c = IncCorpus.adopt(Corpus(data))
    _remember(data, c)
    return c


def _json_loads(line: str) -> dict:
    import json
    return json.loads(line)


def _remember(data: bytes, c: IncCorpus) -> None:
    _RECENT.append((data, c))
    if len(_RECENT) > _RECENT_MAX:
        del _RECENT[0]


def reset() -> None:
    """Forget the chain (tests)."""
    del _RECENT[:]
    _ROWMEMO.clear()
    _MXMEMO.clear()
    _STATEMEMO.clear()


# ------------------------------------------------------------------------------------------------------------
# rows as bytes
# ------------------------------------------------------------------------------------------------------------
_ROWMEMO: Dict[tuple, str] = {}
_ROWMEMO_MAX = 1 << 16
_ROW_KEYS = ("kind", "sent", "source", "topic_at", "clause_at", "turn", "unshaped", "weave_refused")


def row_lines(rows: Any, row_line: Any) -> List[str]:
    """The canonical line of every row (`memory.row_line` is the reference): a line is memoised under every field it reads."""
    out: List[str] = []
    memo = _ROWMEMO
    for r in rows:
        try:
            k = (r.get("kind", "base"), r["sent"], r["source"], r.get("topic_at"), r.get("clause_at"), r.get("turn"), r.get("unshaped"), r.get("weave_refused"),
                 "topic_at" in r, "clause_at" in r, "turn" in r, "weave_refused" in r)
            ln = memo.get(k)
        except (TypeError, KeyError, AttributeError):
            ln = None
            k = None
        if ln is None:
            ln = row_line(r)                              # raises exactly what the plain code raises
            if k is not None and len(memo) < _ROWMEMO_MAX:
                memo[k] = ln
        out.append(ln)
    return out


def rows_bytes(rows: Any, row_line: Any) -> bytes:
    """`memory.rows_bytes(rows)`."""
    return "".join(row_lines(rows, row_line)).encode("utf-8")


# ------------------------------------------------------------------------------------------------------------
# the loom state's canonical JSON, piece by piece
# ------------------------------------------------------------------------------------------------------------
_STATEMEMO: Dict[int, tuple] = {}


def _prov_fp(p: dict) -> tuple:
    """Everything `Unit.to_obj` reads from `prov`: a list or dict value (the snapshot `sids`) by identity and length (it is made once and never changed in place), the rest by value."""
    out = []
    for k, v in p.items():
        out.append((k, (id(v), len(v)) if v.__class__ in _CONTAINERS else v))
    return tuple(out)


_CONTAINERS = (list, dict)


def loom_json(state: Any, canonical: Any, LoomState: Any) -> Optional[str]:
    """`canonical(state.to_obj())`, or None when the state is not the plain LoomState (the caller then uses the plain code).  Units and crosses whose fingerprint (every field `to_obj`
    reads; a list inside `prov` by identity and length) is unchanged since the last call keep their canonical JSON."""
    if type(state).to_obj is not LoomState.to_obj:
        return None
    memo = _STATEMEMO
    key = id(state)
    ent = memo.get(key)
    if ent is None or ent[0] is not state:
        ent = memo[key] = (state, {}, {})
        if len(memo) > 8:
            for k in list(memo)[:4]:
                if k != key:
                    del memo[k]
    um, cm = ent[1], ent[2]
    up: List[str] = []
    for uid in sorted(state.units):
        u = state.units[uid]
        s = u.seated
        fp = (u.surface, u.kind, u.tier, None if s is None else (s[0], s[1]), _prov_fp(u.prov))
        e = um.get(uid)
        if e is None or e[0] != fp:
            e = um[uid] = (fp, canonical(uid) + ":" + canonical(u.to_obj()))
        up.append(e[1])
    cp: List[str] = []
    for cid in sorted(state.crosses):
        c = state.crosses[cid]
        fp = (c.tier, c.lang, c.L, c.depth, c.topic, c.linked, c.centre, tuple(map(tuple, c.arms)))
        e = cm.get(cid)
        if e is None or e[0] != fp:
            e = cm[cid] = (fp, canonical(cid) + ":" + canonical(c.to_obj()))
        cp.append(e[1])
    if len(um) > len(state.units) + 64:                   # a dropped unit: forget it
        for k in [k for k in um if k not in state.units]:
            del um[k]
    if len(cm) > len(state.crosses) + 64:
        for k in [k for k in cm if k not in state.crosses]:
            del cm[k]
    made = ""
    if state._nu != len(state.units) or state._nc != len(state.crosses):
        made = ',"made":' + canonical({"units": state._nu, "crosses": state._nc})
    return '{"closed":%s,"counters":%s,"crosses":{%s},"guards":%s%s,"thread":%s,"units":{%s}}' % (
        canonical(None if state.closed is None else list(state.closed)), canonical(dict(state.counters)), ",".join(cp), canonical(dict(state.guards)), made,
        canonical(list(state.thread)), ",".join(up))


_MXMEMO: Dict[tuple, str] = {}


def mx_rows_bytes(rows: Any) -> bytes:
    """`memcross._rows_bytes(rows)` (the three fields kind / sent / source of every row), with the canonical line of a row memoised."""
    from verantyx.loom.state import canonical
    out: List[str] = []
    memo = _MXMEMO
    for r in rows:
        k = (r.get("kind", "base"), r["sent"], r["source"])
        ln = memo.get(k)
        if ln is None:
            ln = canonical({"kind": k[0], "sent": k[1], "source": k[2]}) + "\n"
            if len(memo) < _ROWMEMO_MAX:
                memo[k] = ln
        out.append(ln)
    return "".join(out).encode("utf-8")
