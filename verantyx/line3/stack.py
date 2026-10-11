"""G4-b: the frozen flat stack (docs/LINE3_G4_GROWTH_METER.md 5, OP-G4-2 「凍結した平面の積みを新しく作る」, D-5, OP-G4-3).

A document (an article) is stacked on the placements of the documents before it.  The stack is built per tier (I-16: tiers never merge).
For one tier the state after step k holds ONE cross per unit of the prefix k (the flat plane: every unit is a seed, L-63 / I-08), each an
exact `placement` class, and one step is a pure function of (state k, document k+1):

  * a unit that is NEW in document k+1 opens its own cross: the one-shot F1 build on the prefix (`build_cross(quotient=False,
    group_insert="ordered", on_collapse="stop", foundation=)`), every unit it shares a sentence with is in the document, so the prefix
    and the document give the same pool (birth equals the one-shot build, T-G4-6);
  * a unit that already has an OPEN cross and occurs in the document is GROWN: the units that first co-occur with it in the document
    (M-1(b) groups on the current counts, F1 ordered inside a group) are seated one at a time into the EMPTY seats of every member of the
    held class (L-64 insertion, ties branch), then the results are settled (L-71) with every unit seated before this step FROZEN
    (placement._settle(fixed=)); the units seated in this step may still move among themselves and the empty seats until the step ends;
  * a cross that closes (its first budget collapse, N-05) stays closed for good; its later co-occurring units are only recorded;
  * a cross whose seed is not in the document is byte-unchanged (T-G4-5).

D-5: a new unit always opens its own cross AND is seated into the open crosses of every seed it shares a sentence with; "no seat accepts"
happens only for a closed cross, and the unit is then recorded (`left`).  A seated unit never moves.  The only changes a cross can undergo
between two steps are 充填 (units seated into empty seats; L may grow, which prepends an empty outer ring and moves nothing) and 絞り (a
member of the tied class has no descendant); `arr_sha` is the sha of the canonical {L, members, seated}, so it changes exactly then.

Everything is exact (int / str / tuples); no float; no set / dict iteration order reaches a result; the fold is true by construction:
`build(docs[:k+1]) == extend(build(docs[:k]), docs[k])` in every byte (state, ledger), also across processes (`save` / `load`).

API (a Python API only; cli.py is not touched):
  build(prefix_docs, foundation=, tiers=, level=, workers=) -> StackState
  extend(state, doc, workers=) -> StackState
  save(state, root) / load(root, prefix, foundation=, level=, order=, tiers=)      keyed by the prefix content sha (steps.py prefix())
  as_placements(state, tier) -> {unit: placement.Placement}      the read view (what ask.load_placements expects: exactly the tier's units)
  prefix_sha256(docs), arr_sha, verify_cross, tier_space
"""
from __future__ import annotations

import collections
import dataclasses
import gzip
import hashlib
import json
import multiprocessing as mp
import os
import time
import types
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from verantyx.lang import strip_attribution
from verantyx.line3 import foundation as fd
from verantyx.line3 import placement as pl
from verantyx.line3 import space as sp
from verantyx.line3.geometry import N_ARMS, moves_swap, swap

FORMAT = "line3.stack.v1"
LEDGER_FORMAT = "line3.stack_ledger.v1"
FOUNDATIONS = fd.FOUNDATIONS
ORDERS = ("forward", "reverse")                  # a label of the input order (the caller orders the documents; L-G4-17)
DEFAULT_LEVEL = "mid"                            # L-G4-24
BIRTH, FILL = "birth", "fill"
CLOSE_REASONS = ("max_class", "max_states", "max_moves")
LEFT_IN_STEP, LEFT_AFTER = "left_in_step", "left_after"

Flat = pl.Flat


class StackError(Exception):
    """A state that cannot be trusted or an input the stack refuses (a mismatching identity, a document with no row, ...)."""


# ------------------------------------------------------------------------------------------------------------------------------
# canonical bytes
# ------------------------------------------------------------------------------------------------------------------------------
def _cj(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def row_line(row: Mapping) -> str:
    """The line a row is written as in steps.py `prefix()`: json.dumps(row, ensure_ascii=False)."""
    return json.dumps(row, ensure_ascii=False)


def doc_title(doc: Sequence[Mapping]) -> str:
    return str(doc[0].get("title", ""))


def prefix_bytes(docs: Sequence[Sequence[Mapping]]) -> bytes:
    """The content of a prefix: the rows of the documents, one `json.dumps(row, ensure_ascii=False)` line each (as steps.py `prefix()`)."""
    return b"".join((row_line(r) + "\n").encode("utf-8") for doc in docs for r in doc)


def prefix_sha256(docs: Sequence[Sequence[Mapping]]) -> str:
    """The key of a state: the sha256 of the prefix content, exactly steps.py `prefix(k)[0]` (the empty prefix: sha256 of b"")."""
    return _sha(prefix_bytes(docs))


def title_order_sha256(titles: Sequence[str]) -> str:
    """L-G4-1: the sha256 of the canonical list of the document titles in order."""
    return _sha(_cj(list(titles)).encode("utf-8"))


def docs_of_rows(rows: Iterable[Mapping]) -> List[List[dict]]:
    """Documents = maximal runs of rows with the same `title` (L-G4-1)."""
    docs: List[List[dict]] = []
    cur = None
    for r in rows:
        t = r.get("title", "")
        if cur is None or t != cur:
            docs.append([])
            cur = t
        docs[-1].append(dict(r))
    return docs


def load_docs(path: str) -> List[List[dict]]:
    with open(path, encoding="utf-8") as f:
        return docs_of_rows(json.loads(line) for line in f if line.strip())


# ------------------------------------------------------------------------------------------------------------------------------
# the state
# ------------------------------------------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class StackCross:
    """The cross of one seed after some step.  `members` = the held class (labelled flats, constructed tokens included when the
    foundation is on), canonical sorted; `seated` = ((unit, step), ...) in seating order (the seed first); a unit is seated when the step
    that inserted it ends.  `left` = ((step, unit, reason), ...): the unit that collapsed (reason = the budget), the rest of that step's
    candidates (`left_in_step`), and every later co-occurring unit (`left_after`).  `key` = (n, p) or (n, p, a_num) of the class as keyed
    at `keyed_at` (its last growth step, with that step's counts)."""
    seed: str
    L: int
    members: Tuple[Flat, ...]
    seated: Tuple[Tuple[str, int], ...]
    opened_at: int
    closed_at: Optional[int]
    closed_reason: Optional[str]
    closed_unit: Optional[str]
    closed_explored: Optional[int]
    left: Tuple[Tuple[int, str, str], ...]
    key: Tuple[int, ...]
    keyed_at: int

    @property
    def units(self) -> Tuple[str, ...]:
        return tuple(u for u, _ in self.seated)

    @property
    def closed(self) -> bool:
        return self.closed_at is not None

    @property
    def last_step(self) -> int:
        """The last step at which this cross changed (born, a unit seated, closed, a unit recorded as left)."""
        return max([self.opened_at, self.keyed_at, self.closed_at or 0]
                   + [s for _, s in self.seated] + [s for s, _, _ in self.left])

    def to_obj(self) -> dict:
        return {"seed": self.seed, "L": self.L, "members": [list(m) for m in self.members],
                "seated": [[u, s] for u, s in self.seated], "opened_at": self.opened_at,
                "closed_at": self.closed_at, "closed_reason": self.closed_reason, "closed_unit": self.closed_unit,
                "closed_explored": self.closed_explored, "left": [[s, u, r] for s, u, r in self.left],
                "key": list(self.key), "keyed_at": self.keyed_at}

    def to_bytes(self) -> bytes:
        return _cj(self.to_obj()).encode("utf-8")

    @staticmethod
    def from_obj(o: Mapping) -> "StackCross":
        return StackCross(o["seed"], o["L"], tuple(tuple(m) for m in o["members"]), tuple((u, s) for u, s in o["seated"]),
                          o["opened_at"], o["closed_at"], o["closed_reason"], o["closed_unit"], o["closed_explored"],
                          tuple((s, u, r) for s, u, r in o["left"]), tuple(o["key"]), o["keyed_at"])


def arr_sha(c: StackCross) -> str:
    """OP-G4-3 / 5.4: the sha256 of the canonical {L, members, seated} of a cross.  It differs between two steps exactly when the cross was
    rearranged (充填 or 絞り); a cross that only recorded units as left, or was only re-counted, keeps it."""
    return _sha(_cj({"L": c.L, "members": [list(m) for m in c.members],
                     "seated": [[u, s] for u, s in c.seated]}).encode("utf-8"))


@dataclass(frozen=True)
class StackState:
    """The stack after `step` documents.  `lines` = the rows of the documents (the prefix content, per document), `crosses` = per tier
    {seed: StackCross} (exactly the units of the prefix's tier space), `ledger` = per tier the canonical JSON lines, one per step."""
    step: int
    titles: Tuple[str, ...]
    lines: Tuple[Tuple[str, ...], ...]
    foundation: str
    level: str
    order: str
    tier_names: Tuple[str, ...]
    crosses: Mapping[str, Mapping[str, StackCross]]
    ledger: Mapping[str, Tuple[str, ...]]
    shas: Mapping[str, str]

    @property
    def prefix_sha256(self) -> str:
        return _sha("".join(l + "\n" for doc in self.lines for l in doc).encode("utf-8"))

    @property
    def title_order_sha256(self) -> str:
        return title_order_sha256(self.titles)

    @property
    def seats_sha(self) -> Optional[str]:
        return fd.seats_sha() if self.foundation == "on" else None

    @property
    def docs(self) -> List[List[dict]]:
        return [[json.loads(l) for l in doc] for doc in self.lines]

    def state_sha256(self, tier: str) -> str:
        return self.shas[tier]

    def ledger_sha256(self, tier: str) -> str:
        return _sha(("".join(l + "\n" for l in self.ledger[tier])).encode("utf-8"))

    def state_bytes(self, tier: str) -> bytes:
        """Every canonical byte of the tier's state (header + one line per cross, by seed): the fold test compares these."""
        parts = [_cj(_header(self, tier, self.step, self.prefix_sha256)).encode("utf-8")]
        for seed in sorted(self.crosses[tier]):
            parts.append(self.crosses[tier][seed].to_bytes())
        return b"\n".join(parts)


def _header(state_or_cfg, tier: str, step: int, prefix_sha: str) -> dict:
    return {"format": FORMAT, "tier": tier, "step": step, "prefix_sha256": prefix_sha,
            "foundation": fd.seats_sha() if state_or_cfg.foundation == "on" else None,
            "level": state_or_cfg.level, "order": state_or_cfg.order}


def tier_state_sha(cfg, tier: str, step: int, prefix_sha: str, crosses: Mapping[str, StackCross]) -> str:
    """The step identity of a tier: the sha256 over a header and (seed, canonical StackCross bytes) sorted by seed (5.6)."""
    h = hashlib.sha256()
    h.update(_cj(_header(cfg, tier, step, prefix_sha)).encode("utf-8"))
    h.update(b"\n")
    for seed in sorted(crosses):
        h.update(seed.encode("utf-8"))
        h.update(b"\x00")
        h.update(crosses[seed].to_bytes())
        h.update(b"\n")
    return h.hexdigest()


def _check_config(foundation: str, tiers: Sequence[str], level: str, order: str) -> Tuple[str, ...]:
    fd.check_foundation(foundation)
    if level not in pl.LEVELS:
        raise ValueError("level must be one of %s" % ", ".join(pl.LEVEL_ORDER))
    if order not in ORDERS:
        raise ValueError("order must be 'forward' or 'reverse'")
    names = tuple(tiers)
    if not names or any(t not in sp.TIERS for t in names) or len(set(names)) != len(names):
        raise ValueError("tiers: a non-empty subset of RUN, WORD, CHAR")
    return tuple(t for t in sp.TIERS if t in names)


def empty_state(foundation: str = "off", tiers: Sequence[str] = sp.TIERS, level: str = DEFAULT_LEVEL, order: str = "forward") -> StackState:
    """Step 0: no sentence, so no cross (a cross needs a centre word, L-77)."""
    names = _check_config(foundation, tiers, level, order)
    st = StackState(0, (), (), foundation, level, order, names, {t: {} for t in names}, {t: () for t in names}, {})
    return dataclasses.replace(st, shas={t: tier_state_sha(st, t, 0, st.prefix_sha256, {}) for t in names})


# ------------------------------------------------------------------------------------------------------------------------------
# the prefix space (a pure cache keyed by the prefix content)
# ------------------------------------------------------------------------------------------------------------------------------
_MEMO: "collections.OrderedDict" = collections.OrderedDict()
_MEMO_SIZE = 3


def _build_space(rows: Sequence[Mapping], tier_names: Sequence[str]) -> sp.Space:
    """L-G4-23: the space of the prefix, rebuilt from its rows.  All three tiers = space.build_space; a subset (arm B builds CHAR only)
    uses the same pieces, so the CHAR tier is the same object either way and no tokeniser is needed for it."""
    if tuple(tier_names) == sp.TIERS:
        return sp.build_space(rows)
    sentences, kinds = sp._rows(rows)
    texts = [strip_attribution(t) for t, _ in sentences]
    return sp.Space(sentences, {n: sp.build_tier(n, texts) for n in tier_names}, kinds)


def _space_of(lines: Sequence[str], tier_names: Sequence[str], foundation: str):
    key = (_sha("".join(l + "\n" for l in lines).encode("utf-8")), tuple(tier_names), foundation)
    hit = _MEMO.get(key)
    if hit is not None:
        _MEMO.move_to_end(key)
        return hit
    space = _build_space([json.loads(l) for l in lines], tier_names)
    adh = fd.adhesions_of_space(space, tier_names) if foundation == "on" else {}
    _MEMO[key] = (space, adh)
    while len(_MEMO) > _MEMO_SIZE:
        _MEMO.popitem(last=False)
    return space, adh


def _flat_lines(state_lines: Sequence[Sequence[str]]) -> Tuple[str, ...]:
    return tuple(l for doc in state_lines for l in doc)


def tier_space(state: StackState, tier: str):
    """(TierSpace, Adhesion | None) of the state's prefix (the adhesion only with the foundation on)."""
    space, adh = _space_of(_flat_lines(state.lines), state.tier_names, state.foundation)
    return space.tiers[tier], adh.get(tier)


# ------------------------------------------------------------------------------------------------------------------------------
# seats
# ------------------------------------------------------------------------------------------------------------------------------
def _data_units(flat: Flat) -> List[str]:
    return [x for x in flat if x is not None and not fd.is_constructed(x)]


def seat_table(members: Sequence[Flat], L: int, seated: bool) -> Dict[str, Tuple[Tuple[str, ...], Tuple[int, ...]]]:
    """unit -> (sorted arms, sorted rings) over the members of a class.  Arm = the particle at the innermost seat of the leg (foundation
    on; the legs of a plain flat are not told apart) or "centre"; ring = the distance to the centre in the contracted cross (0 = the
    centre, 1 = next to it)."""
    arms: Dict[str, set] = {}
    rings: Dict[str, set] = {}
    for m in members:
        c = m[0]
        if c is not None:
            arms.setdefault(c, set()).add("centre")
            rings.setdefault(c, set()).add(0)
        for a in range(N_ARMS):
            part = fd.particle_of(m[1 + a * L + L - 1]) if seated else None
            for k in range(L):
                x = m[1 + a * L + k]
                if x is None or fd.is_constructed(x):
                    continue
                if part:
                    arms.setdefault(x, set()).add(part)
                rings.setdefault(x, set()).add((L - k) - (1 if seated else 0))
    return {u: (tuple(sorted(arms.get(u, ()))), tuple(sorted(rings[u]))) for u in sorted(rings)}


# ------------------------------------------------------------------------------------------------------------------------------
# one tier, one step: the tasks (independent per seed)
# ------------------------------------------------------------------------------------------------------------------------------
_G: dict = {}                                # set before the fork; the children inherit it


def _key_of(w: pl.Weights, flat: Flat, L: int, on: bool) -> Tuple[int, ...]:
    return tuple(pl.score_flat(w, flat, L))


def _open(u: str) -> StackCross:
    """A new unit opens its own cross: the one-shot F1 build on the prefix (D-5; birth equals the one-shot build)."""
    ts, w, adh, budget, on, step = _G["ts"], _G["w"], _G["adh"], _G["budget"], _G["on"], _G["step"]
    p = pl.build_cross(ts, u, w, budget=budget, quotient=False, group_insert="ordered", order="forward", on_collapse="stop",
                       foundation="on" if on else "off", adhesion=adh)
    seated = [(u, step)] + [(v, step) for st in p.steps if st.status == pl.STABLE for v in st.units]
    if len(seated) != p.size:
        raise StackError("birth of %r: %d units seated, the placement says %d" % (u, len(seated), p.size))
    closed_at = reason = unit = explored = None
    left: List[Tuple[int, str, str]] = []
    if p.stop == pl.BUDGET:
        bk = p.broke_on
        closed_at, reason, unit, explored = step, bk.reason, bk.units[0], bk.explored
        groups = pl._groups(ts, u)
        seq = p.order_log[-1][1]
        idx = seq.index(unit)
        rest = list(seq[idx + 1:]) + [v for _, g in groups[len(p.order_log):] for v in pl.group_order(ts, u, g)]   # L-G4-69: the later groups in group_order, as _grow does
        if p.left_in_group != len(seq) - idx or p.left_after != len(rest) - (len(seq) - idx - 1):
            raise StackError("birth of %r: the left counts of the placement do not match the recorded order" % (u,))
        left = [(step, unit, reason)] + [(step, v, LEFT_IN_STEP) for v in rest]
    key = tuple(p.score) + ((p.a_num,) if on else ())
    return StackCross(u, p.L, p.members, tuple(seated), step, closed_at, reason, unit, explored, tuple(left), key, step)


def _candidate_order(ts, u: str, cand: Sequence[str]) -> List[str]:
    """M-1(b) on the current counts: groups by n(u, v) descending, inside a group `group_order` (L-461)."""
    by: Dict[int, List[str]] = {}
    for v in cand:
        by.setdefault(ts.n_pair(u, v), []).append(v)
    out: List[str] = []
    for share in sorted(by, reverse=True):
        out.extend(pl.group_order(ts, u, sorted(by[share])))
    return out


def _grow(u: str) -> Optional[StackCross]:
    """An open cross: seat the units that first co-occur with its seed in this document into the EMPTY seats of every member of the
    class, one at a time in the recorded order, settling after each with every unit seated before this step frozen."""
    ts, w, budget, on, step, prev, dsids = (_G["ts"], _G["w"], _G["budget"], _G["on"], _G["step"], _G["prev"], _G["dsids"])
    sc = prev[u]
    seated_set = {v for v, _ in sc.seated}
    pu = set(ts.postings[u])
    cand = []
    for v in ts.cooccurrence(u):
        if v in seated_set:
            continue
        if not (pu & set(ts.postings[v])) <= dsids:                  # an open cross seated every earlier co-occurring unit
            raise StackError("open cross %r: %r co-occurred before this document but is not seated" % (u, v))
        cand.append(v)
    if not cand:
        return None
    seq = _candidate_order(ts, u, cand)
    fixed = frozenset(seated_set)                                    # every unit seated BEFORE this step (and, below, the constructed seats)
    state, L, size = sc.members, sc.L, len(sc.seated)
    nfound = N_ARMS if on else 0
    seated = list(sc.seated)
    closed_at = reason = unit = explored = None
    left = list(sc.left)
    for i, v in enumerate(seq):
        L2 = pl.min_L(size + 1 + nfound)
        bases = [pl.extend(s, L, L2) if L2 > L else s for s in state]
        work = pl._Work(budget)
        try:
            starts = pl._insert_group(w, bases, L2, [v], work, budget)
            new = pl._settle(w, starts, L2, work, budget, fixed)
        except pl._Over as e:
            closed_at, reason, unit, explored = step, str(e), v, work.n
            left += [(step, v, reason)] + [(step, x, LEFT_IN_STEP) for x in seq[i + 1:]]
            break
        state, L, size = new, L2, size + 1
        seated.append((v, step))
    key, keyed_at = sc.key, sc.keyed_at
    if len(seated) > len(sc.seated):
        key, keyed_at = _key_of(w, state[0], L, on), step
    return StackCross(u, L, state, tuple(seated), sc.opened_at, closed_at, reason, unit, explored, tuple(left), key, keyed_at)


def _left(u: str) -> Optional[StackCross]:
    """A closed cross never reopens: the units of this document that share a sentence with its seed are recorded (N-05)."""
    ts, step, prev, dsids = _G["ts"], _G["step"], _G["prev"], _G["dsids"]
    sc = prev[u]
    known = {v for v, _ in sc.seated} | {v for _, v, _ in sc.left}
    add: List[Tuple[int, str, str]] = []
    for sid in ts.postings[u]:
        if sid not in dsids:
            continue
        for v in dict.fromkeys(ts.sentence_units[sid]):
            if v != u and v not in known:
                known.add(v)
                add.append((step, v, LEFT_AFTER))
    if not add:
        return None
    return dataclasses.replace(sc, left=sc.left + tuple(add))


def _run_task(task: Tuple[str, str]):
    kind, u = task
    t0 = time.process_time()
    out = _open(u) if kind == "open" else _grow(u) if kind == "grow" else _left(u)
    return u, kind, out, time.process_time() - t0


def _run_tasks(tasks: Sequence[Tuple[str, str]], workers: int):
    if workers <= 1 or len(tasks) <= 1:
        return [_run_task(t) for t in tasks]
    ctx = mp.get_context("fork")
    with ctx.Pool(min(workers, len(tasks))) as pool:
        return list(pool.imap_unordered(_run_task, tasks, chunksize=1))


# ------------------------------------------------------------------------------------------------------------------------------
# rearrangement: descendants (5.4)
# ------------------------------------------------------------------------------------------------------------------------------
def _project(flat: Flat, drop: frozenset, L: int) -> Flat:
    return pl.canon(tuple(None if x in drop else x for x in flat), L)


def descendants(old: StackCross, new: StackCross, step: int) -> Tuple[bool, int]:
    """(frozen, dropped).  `frozen` = every member of `new` is a descendant of a member of `old`: with the units seated at `step` taken
    out, it equals that member (extended by the empty outer rings L grew by) -- the seated units sit on the same legs and rings.
    `dropped` = the members of `old` with no descendant (絞り)."""
    drop = frozenset(u for u, s in new.seated if s >= step)
    ext = {pl.extend(m, old.L, new.L) if new.L > old.L else m for m in old.members}
    proj = {_project(m, drop, new.L) for m in new.members}
    return proj <= ext, len(ext - proj)


def dropped_split(old: StackCross, new: StackCross, step: int, w: pl.Weights) -> Tuple[int, int]:
    """(dropped because of the new units, dropped by the recount alone) -- a diagnostic split of 絞り (L-G4-70); R / U / A are not changed by it.
    The members of `old` that have no descendant are `dropped`.  Each is scored under the NEW counts (`w` of the step's prefix) in its
    form extended to the new L, before any new unit is seated; one whose key is below the best key among the extended old members would
    have left the class by the recount alone ("recount"), the others ("new") are dropped only by what the new units did.  The two are
    attributed in that order: a member the recount already demoted is counted as recount even if the new units would also have dropped it.
    by_new + by_recount == the `dropped` of `descendants`."""
    drop = frozenset(u for u, s in new.seated if s >= step)
    ext = [pl.extend(m, old.L, new.L) if new.L > old.L else m for m in old.members]
    proj = {_project(m, drop, new.L) for m in new.members}
    gone = [m for m in ext if m not in proj]
    if not gone:
        return 0, 0
    best = max(tuple(pl.score_flat(w, m, new.L)) for m in ext)
    recount = sum(1 for m in gone if tuple(pl.score_flat(w, m, new.L)) < best)
    return len(gone) - recount, recount


# ------------------------------------------------------------------------------------------------------------------------------
# one step
# ------------------------------------------------------------------------------------------------------------------------------
def _adhesion_added(adh: Optional[fd.Adhesion], dsids) -> Optional[dict]:
    if adh is None:
        return None
    by: Dict[str, int] = {}
    total = 0
    for (u, p), _n in adh.counts.items():
        k = len({r.sid for r in adh.evidence(u, p) if r.sid in dsids})
        if k:
            by[p] = by.get(p, 0) + k
            total += k
    return {"attachments_added": total, "by_particle": dict(sorted(by.items()))}


def _extend_tier(state: StackState, tier: str, ts, adh, dsids: frozenset, step: int, title: str, doc_sids: Tuple[int, int],
                 prefix_sha: str, workers: int, stats: Optional[dict]):
    prev = state.crosses[tier]
    on = state.foundation == "on"
    budget = pl.budget_level(state.level)
    w = pl.Weights(ts, adh) if on else pl.Weights(ts)
    D = sorted({u for sid in sorted(dsids) for u in ts.sentence_units[sid]})
    new_units = [u for u in ts.units() if u not in prev]
    if not set(new_units) <= set(D) or any(u not in ts.postings for u in prev):
        raise StackError("%s: a unit is new (or gone) outside the document" % tier)
    tasks = []
    for u in D:
        sc = prev.get(u)
        tasks.append(("open" if sc is None else "grow" if not sc.closed else "left", u))
    _G.clear()
    _G.update(ts=ts, w=w, adh=adh, budget=budget, on=on, step=step, prev=prev, dsids=dsids)
    try:
        t0 = time.time()
        parts = _run_tasks(tasks, workers)
        wall = time.time() - t0
    finally:
        _G.clear()
    res = {u: (kind, out, secs) for u, kind, out, secs in parts}
    crosses = dict(prev)
    opened, births, grown, closed, left_after, seats, unchanged = [], [], [], [], {}, [], 0
    cpu = {"open": 0.0, "grow": 0.0, "left": 0.0}
    for u in D:
        kind, out, secs = res[u]
        cpu[kind] += secs
        old = prev.get(u)
        if out is None:
            unchanged += 1
            continue
        crosses[u] = out
        taken = [(v, s) for v, s in out.seated if s == step]
        tab = seat_table(out.members, out.L, on) if taken else {}
        pu = set(ts.postings[u])
        for v, _s in taken:
            ev = sorted(pu & set(ts.postings[v]))
            arms, rings = tab[v]
            seats.append({"cross": u, "unit": v, "kind": BIRTH if kind == "open" else FILL,
                          "arm": list(arms), "ring": list(rings), "sids": ev})
        if kind == "open":
            opened.append(u)
            births.append({"seed": u, "size": len(out.seated), "L": out.L, "members": len(out.members), "key": list(out.key),
                           "arr": arr_sha(out), "closed": out.closed_reason})
        elif kind == "grow":
            frozen, dropped = descendants(old, out, step)
            if not frozen:
                raise StackError("%s %r: a seated unit moved" % (tier, u))
            filled = [v for v, s in taken]
            ka, kb = out.key, old.key
            d_new, d_recount = dropped_split(old, out, step, w) if dropped else (0, 0)
            if d_new + d_recount != dropped:
                raise StackError("%s %r: the 絞り split (%d + %d) does not add up to %d" % (tier, u, d_new, d_recount, dropped))
            grown.append({"seed": u, "filled": filled, "L": [old.L, out.L], "members": [len(old.members), len(out.members)],
                          "dropped": dropped, "dropped_new": d_new, "dropped_recount": d_recount, "narrowed": dropped > 0, "key": [list(kb), list(ka)],
                          "a_gain": (ka[2] - kb[2]) if on and filled else None, "arr": [arr_sha(old), arr_sha(out)]})
        if kind != "left" and out.closed_at == step:
            rest = [v for s, v, r in out.left if s == step and r == LEFT_IN_STEP]
            closed.append({"seed": u, "at": "birth" if kind == "open" else "grow", "reason": out.closed_reason,
                           "unit": out.closed_unit, "explored": out.closed_explored, "left_in_step": rest})
        n_after = sum(1 for s, _v, r in out.left if s == step and r == LEFT_AFTER)
        if n_after:
            left_after[u] = n_after
    entry = {"format": LEDGER_FORMAT, "tier": tier, "step": step, "title": title, "sids": list(doc_sids),
             "prefix_sha256": prefix_sha, "foundation": fd.seats_sha() if on else None, "level": state.level, "order": state.order,
             "units": D, "touched": len(D), "unchanged": unchanged, "opened": opened, "births": births, "grown": grown,
             "closed": closed, "left_after": dict(sorted(left_after.items())), "seats": seats,
             "adhesion": _adhesion_added(adh, dsids)}
    if stats is not None:
        stats.setdefault("tiers", {})[tier] = {
            "tasks": len(tasks), "open": sum(1 for t in tasks if t[0] == "open"), "grow": sum(1 for t in tasks if t[0] == "grow"),
            "left": sum(1 for t in tasks if t[0] == "left"), "closed": len(closed), "wall_s": wall,
            "cpu_open_s": cpu["open"], "cpu_grow_s": cpu["grow"], "cpu_left_s": cpu["left"]}
    return crosses, entry


def extend(state: StackState, doc: Sequence[Mapping], workers: int = 1, stats: Optional[dict] = None) -> StackState:
    """One step: document k+1 stacked on the state of k.  A pure function of (state, doc): the new state holds the old documents' rows,
    the crosses and the ledger; nothing outside them (no cache, no clock, no worker count) reaches a byte."""
    if not doc:
        raise StackError("a document has no row")
    for r in doc:
        if "sent" not in r:
            raise StackError("a row has no 'sent'")
    t_start, c_start = time.time(), time.process_time()
    new_lines = tuple(row_line(r) for r in doc)
    lines = state.lines + (new_lines,)
    step = state.step + 1
    n_prev = sum(len(d) for d in state.lines)
    flat = _flat_lines(lines)
    dsids = frozenset(range(n_prev, len(flat)))
    space, adhs = _space_of(flat, state.tier_names, state.foundation)
    prefix_sha = _sha("".join(l + "\n" for l in flat).encode("utf-8"))
    crosses, ledger, shas = {}, {}, {}
    for tier in state.tier_names:
        cr, entry = _extend_tier(state, tier, space.tiers[tier], adhs.get(tier), dsids, step, doc_title(doc), (n_prev, len(flat)),
                                 prefix_sha, workers, stats)
        sha = tier_state_sha(state, tier, step, prefix_sha, cr)
        entry["state_sha256"] = sha
        crosses[tier], shas[tier] = cr, sha
        ledger[tier] = state.ledger[tier] + (_cj(entry),)
    out = StackState(step, state.titles + (doc_title(doc),), lines, state.foundation, state.level, state.order, state.tier_names,
                     crosses, ledger, shas)
    if stats is not None:
        stats.update({"step": step, "wall_s": time.time() - t_start, "cpu_main_s": time.process_time() - c_start,
                      "sentences": len(doc)})
    return out


def build(prefix_docs: Sequence[Sequence[Mapping]], foundation: str = "off", tiers: Sequence[str] = sp.TIERS,
          level: str = DEFAULT_LEVEL, workers: int = 1, order: str = "forward", save_root: Optional[str] = None,
          save_steps: Optional[Iterable[int]] = None, log=None) -> StackState:
    """The stack of the documents in the given order: the fold of `extend` over the empty state (so build(docs[:k+1]) ==
    extend(build(docs[:k]), docs[k]) by construction).  `save_root` + `save_steps` write the snapshots of those steps (all steps if
    save_steps is None) while building."""
    st = empty_state(foundation, tiers, level, order)
    want = None if save_steps is None else set(save_steps)
    for doc in prefix_docs:
        stats: dict = {}
        st = extend(st, doc, workers, stats)
        if log:
            log(st, stats)
        if save_root and (want is None or st.step in want):
            save(st, save_root)
    return st


# ------------------------------------------------------------------------------------------------------------------------------
# save / load, keyed by the prefix content sha
# ------------------------------------------------------------------------------------------------------------------------------
def _cfg_dir(root: str, foundation: str, level: str, order: str) -> str:
    return os.path.join(root, "%s__%s__%s" % (fd.foundation_key() if foundation == "on" else "off", level, order))


def _write(path: str, data: bytes) -> None:
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _gz(data: bytes) -> bytes:
    import io
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", compresslevel=6, mtime=0) as g:
        g.write(data)
    return buf.getvalue()


def save(state: StackState, root: str) -> str:
    """Write a snapshot of `state` under root/<foundation>__<level>__<order>/ , keyed by the prefix content sha: the prefix rows
    (docs_<p12>.jsonl), per tier the crosses (<tier>_state_<p12>.jsonl.gz) and the ledger (<tier>_ledger_<p12>.jsonl), and one line
    of manifest.jsonl with the identities.  Idempotent.  Returns the directory.  Only the canonical bytes are an identity; the files are
    a local cache."""
    d = _cfg_dir(root, state.foundation, state.level, state.order)
    os.makedirs(d, exist_ok=True)
    p = state.prefix_sha256
    p12 = p[:12]
    _write(os.path.join(d, "docs_%s.jsonl" % p12), "".join(l + "\n" for doc in state.lines for l in doc).encode("utf-8"))
    for t in state.tier_names:
        head = _cj({**_header(state, t, state.step, p), "state_sha256": state.shas[t], "n": len(state.crosses[t])})
        body = "\n".join([head] + [state.crosses[t][s].to_bytes().decode("utf-8") for s in sorted(state.crosses[t])]) + "\n"
        _write(os.path.join(d, "%s_state_%s.jsonl.gz" % (t, p12)), _gz(body.encode("utf-8")))
        _write(os.path.join(d, "%s_ledger_%s.jsonl" % (t, p12)), "".join(l + "\n" for l in state.ledger[t]).encode("utf-8"))
    entry = {"format": FORMAT, "step": state.step, "prefix_sha256": p, "title_order_sha256": state.title_order_sha256,
             "titles": list(state.titles), "doc_sizes": [len(x) for x in state.lines], "foundation": state.seats_sha,
             "level": state.level, "order": state.order,
             "tiers": {t: {"state_sha256": state.shas[t], "ledger_sha256": state.ledger_sha256(t)} for t in state.tier_names}}
    mpath = os.path.join(d, "manifest.jsonl")
    old = open(mpath, encoding="utf-8").read().splitlines() if os.path.exists(mpath) else []
    kept = [l for l in old if json.loads(l)["prefix_sha256"] != p or json.loads(l)["tiers"].keys() != entry["tiers"].keys()]
    # one manifest line per (prefix, tier set): a re-save replaces its own line; other tier sets (another arm) keep theirs
    _write(mpath, "".join(l + "\n" for l in kept + [_cj(entry)]).encode("utf-8"))
    return d


def load(root: str, prefix, foundation: str = "off", tiers: Sequence[str] = sp.TIERS, level: str = DEFAULT_LEVEL,
         order: str = "forward") -> StackState:
    """Load the snapshot for a prefix (its sha256, or the documents).  Refuses (StackError) a state for another prefix, order, level,
    foundation or tier set, and recomputes `state_sha256` of every tier and the sha of the prefix content: a mismatch is an error."""
    names = _check_config(foundation, tiers, level, order)
    p = prefix if isinstance(prefix, str) else prefix_sha256(prefix)
    d = _cfg_dir(root, foundation, level, order)
    mpath = os.path.join(d, "manifest.jsonl")
    if not os.path.exists(mpath):
        raise StackError("no stack for foundation=%s level=%s order=%s under %s" % (foundation, level, order, root))
    entries = [json.loads(l) for l in open(mpath, encoding="utf-8").read().splitlines()]
    hit = [e for e in entries if e["prefix_sha256"] == p and set(e["tiers"]) >= set(names)]
    if not hit:
        raise StackError("no stack for prefix %s (foundation=%s level=%s order=%s tiers=%s)" % (p[:12], foundation, level, order, ",".join(names)))
    e = hit[-1]
    p12 = p[:12]
    raw = open(os.path.join(d, "docs_%s.jsonl" % p12), "rb").read()
    if _sha(raw) != p:
        raise StackError("docs file of %s does not hash to its key" % p12)
    rows = raw.decode("utf-8").splitlines()
    sizes, lines, i = e["doc_sizes"], [], 0
    for n in sizes:
        lines.append(tuple(rows[i:i + n]))
        i += n
    if i != len(rows) or title_order_sha256(e["titles"]) != e["title_order_sha256"]:
        raise StackError("docs or titles of %s do not match the manifest" % p12)
    if e["level"] != level or e["order"] != order or e["foundation"] != (fd.seats_sha() if foundation == "on" else None):
        raise StackError("manifest of %s is for another level / order / foundation" % p12)
    crosses, ledger, shas = {}, {}, {}
    cfg = types.SimpleNamespace(foundation=foundation, level=level, order=order)
    for t in names:
        with gzip.open(os.path.join(d, "%s_state_%s.jsonl.gz" % (t, p12)), "rb") as f:
            ls = f.read().decode("utf-8").splitlines()
        head = json.loads(ls[0])
        cs = {}
        for l in ls[1:]:
            c = StackCross.from_obj(json.loads(l))
            cs[c.seed] = c
        sha = tier_state_sha(cfg, t, e["step"], p, cs)
        if head["state_sha256"] != sha or e["tiers"][t]["state_sha256"] != sha or head["n"] != len(cs):
            raise StackError("%s state of %s: the recomputed identity does not match the stored one" % (t, p12))
        lg = tuple(open(os.path.join(d, "%s_ledger_%s.jsonl" % (t, p12)), encoding="utf-8").read().splitlines())
        if _sha(("".join(x + "\n" for x in lg)).encode("utf-8")) != e["tiers"][t]["ledger_sha256"]:
            raise StackError("%s ledger of %s does not match the manifest" % (t, p12))
        crosses[t], ledger[t], shas[t] = cs, lg, sha
    return StackState(e["step"], tuple(e["titles"]), tuple(lines), foundation, level, order, names, crosses, ledger, shas)


# ------------------------------------------------------------------------------------------------------------------------------
# the read view (6.1): what ask's cache loader expects -- a Placement for exactly the units of the tier
# ------------------------------------------------------------------------------------------------------------------------------
def read_view(sc: StackCross, ts, w: pl.Weights, adh: Optional[fd.Adhesion], budget: pl.Budget) -> pl.Placement:
    """The reader's view of one cross: `contract_for_read` of the class (foundation on: the plain flats at L - 1; off: the flats).
    size = the data units seated; stop = "budget" iff closed; candidates = the units that share a sentence with the seed in the prefix;
    twin_sets = (); quotient = False; group_insert = "ordered"; `score` / `a_num` recomputed on the prefix (display only: the reader
    does not select by it, and a cross that was not touched since keyed_at may have counts that moved on)."""
    on = adh is not None
    key = pl.score_flat(w, sc.members[0], sc.L)
    nd = sum(1 for x in sc.members[0] if x is not None and not fd.is_constructed(x))
    broke = None
    if sc.closed:
        broke = pl.Step(ts.n_pair(sc.seed, sc.closed_unit), (sc.closed_unit,), pl.BUDGET, sc.closed_explored, None, None, sc.closed_reason)
    step_left = [1 for s, _u, r in sc.left if s == sc.closed_at and r != LEFT_AFTER]
    full = pl.Placement(
        seed=sc.seed, cross=pl.to_cross(sc.members[0], sc.L), members=sc.members, L=sc.L, centres=pl._centres(sc.members),
        size=nd, capacity=nd, score=(key[0], key[1]), stop=pl.BUDGET if sc.closed else "exhausted", broke_on=broke, steps=(),
        candidates=len(ts.cooccurrence(sc.seed)), budget=budget, twin_sets=(), quotient=False, group_insert="ordered",
        order="forward", order_log=(), left_in_group=len(step_left),
        left_after=sum(1 for _s, _u, r in sc.left if r == LEFT_AFTER), on_collapse="stop", skipped=(),
        foundation=fd.seats_sha() if on else None, a_num=key[2] if on else None, from_stack=True)
    return pl.contract_for_read(full) if on else full


def as_placements(state: StackState, tier: str) -> Dict[str, pl.Placement]:
    """The tier's crosses as standard Placement objects, in seed order, covering exactly the units of the prefix's tier space
    (what `ask.load_placements` requires).  With the foundation on every cross is already contracted (`contract_for_read`), so the
    reader sees plain flats; `Placement.foundation` names the seats sha.  Step 0: {}."""
    if state.step == 0:
        return {}
    ts, adh = tier_space(state, tier)
    w = pl.Weights(ts, adh) if adh is not None else pl.Weights(ts)
    budget = pl.budget_level(state.level)
    cr = state.crosses[tier]
    if set(cr) != set(ts.units()):
        raise StackError("%s: the stack holds %d crosses, the prefix has %d units" % (tier, len(cr), len(ts.units())))
    return {s: read_view(cr[s], ts, w, adh, budget) for s in sorted(cr)}


# ------------------------------------------------------------------------------------------------------------------------------
# independent check of a cross after its growth step (T-G4-8): the restricted fixed point
# ------------------------------------------------------------------------------------------------------------------------------
def verify_cross(ts, adh: Optional[fd.Adhesion], sc: StackCross) -> dict:
    """Independent code (geometry's swap, the plain key / `seated_key`, not the search's): the class of `sc` is one key, no member has an
    improving swap among the seats that are neither a foundation seat nor held by a unit seated BEFORE `sc.keyed_at`, and every
    equal-key such swap stays in the class.  Valid on the tier space of step `sc.keyed_at` (the counts the class was keyed with)."""
    L = sc.L
    on = adh is not None
    fixed = frozenset(u for u, s in sc.seated if s < sc.keyed_at)
    w = pl.Weights(ts)
    here = set(sc.members)

    def key_of(c):
        return pl.seated_key(ts, adh, c, w) if on else pl.cross_score(w, c)

    keys = {key_of(pl.to_cross(m, L)) for m in sc.members}
    base = next(iter(keys))
    fixed_ok = closed_ok = True
    tested = 0
    for m in sc.members:
        c = pl.to_cross(m, L)
        for p_, q_ in moves_swap(L):
            a, b = c.get(p_), c.get(q_)
            a = None if a is None else str(a)
            b = None if b is None else str(b)
            if a == b or fd.is_constructed(a) or fd.is_constructed(b) or a in fixed or b in fixed:
                continue
            c2 = swap(c, p_, q_)
            if c2.center is None:
                continue
            tested += 1
            k2 = key_of(c2)
            if k2 > base:
                fixed_ok = False
            elif k2 == base and pl.canon(pl.from_cross(c2), L) not in here:
                closed_ok = False
    one = len(keys) == 1
    matches = one and tuple(base) == tuple(sc.key)
    return {"size": len(here), "one_key": one, "fixed_point": fixed_ok, "closed": closed_ok, "swaps_tested": tested,
            "key": base if one else None, "matches_record": matches,
            "ok": one and fixed_ok and closed_ok and matches}
