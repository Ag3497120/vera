"""PUB-M5: detection on the memory crosses (docs/LINE3_PUBLIC_DESIGN.md 4.6; local decisions L-PUB-39..; notes profile `mem.v4`).

The detections are made by a FOLD over the clauses, in the order of the ledger, on the crosses the memory index holds: `Detector.observe_*` is called once per clause by `memcross.IndexBuilder` and returns
the notes of that clause.  The notes are part of the derived index (a replay rebuilds them from H, the nest declarations and the memory corpus of every prefix; nothing here reads a clock, a file, a
float, the environment or a set / dict order).  A note NEVER blocks a write (L-MEM-09).

A POSITION is where the crosses say what a thing IS: (tank, centre, path) = the centre phrase, the clause's arm tree and (implicitly) the value seat.  An event has no value seat: its position is
(F3 | F4, centre, the OTHER arms, the arm that varies): the arms で に と vary, the others (が を ...) are the fixed context, and at least one of が / を must be in the context (a bare 「大阪で開く」 is not
comparable with anything).  A position is read INSIDE ITS NEST (designer decision, L-PUB-39): the SCOPE of a statement is the nest that was open when it was written (None: no nest).  The same position
with different values in the same scope is a contradiction candidate; at different scopes it is an enumeration.

  SAME_SEAT     同席異値.  A clause whose value at its (position, scope) differs from a LIVE value that another sentence put there, and which is not a change clause.  Counted.  A value is live until a
                change clause replaces it (a change clause replaces everything before it at its position and scope).  A repeat of a live value is no note.
  UPDATE        a change clause (「A から B に変更」 ...) whose new value differs from a live value at its position and scope (`first`: nothing was there before, the old value lives only in the
                clause).  Not a contradiction: a column of its own.  (An UPDATE the model makes with `supersede` is read from the index: the marks.)
  REVERSAL_X    the same pair of phrases in opposite roles in two sentences: 「X の Y」 and 「Y の X」 (the two ends of a の relation), 「S が O を V」 and 「O が S を V」 (same V), 「A は P の Q」 and
                「P は A の Q」 (the same Q).  Counted.  The note records the existing KEY SWAP (`read.loom_key` of the one-arm cross as written against the cross with its centre and arm unit swapped,
                (n, p) of the memory BEFORE the sentence) and whether it AGREED (the swap improves the key: the history holds the pair in the other order).
  ENUMERATION   information only, never counted: the same attribute with a different value at another owner (`arm_owner`: 認証の期限 / 決済の期限) or the same position with a different value in
                another nest (`nest`).  It is what the old CONFLICT note flagged as a conflict.

SAME_QUESTION (the evidence-gate route of mem.v3) stays a second witness: `memory.py` annotates every note with whether the two routes agree.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from verantyx.loom import memnotes as mn

DETECT_VERSION = "detect.v1"
SAME_SEAT, UPDATE, REVERSAL_X, ENUMERATION = "SAME_SEAT", "UPDATE", "REVERSAL_X", "ENUMERATION"
CROSS_NOTE_TYPES: Tuple[str, ...] = (SAME_SEAT, UPDATE, REVERSAL_X, ENUMERATION)
COUNTED_V4: Tuple[str, ...] = (SAME_SEAT, REVERSAL_X)                 # the meter counts these two (UPDATE in its own column)
ADJUNCT_ARMS = "でにと"                                                # the arms of an event that may vary
CONTEXT_ARMS = "がを"                                                  # at least one of them must be in the fixed context of an event position
EVENT_MARK = "@"                                                       # the last element of an event position's path names the arm that varies
CITE_MAX = 8                                                           # earlier statements a note lists (`earlier_n` is the count)
ENUM_CITE_MAX = 4

Path = Tuple[Tuple[str, str], ...]
JudgeFn = Callable[[str, Sequence[str], Sequence[str]], Optional[dict]]


def _cite(o: dict) -> dict:
    d = {"sid": o["sid"], "clause": o["clause"], "value": o["value"]}
    if o.get("turn") is not None:
        d["turn"] = o["turn"]
    return d


class Detector:
    """The state of the fold.  Every dict is looked up, never iterated; every list is in the order of the ledger."""

    def __init__(self) -> None:
        self._live: Dict[Tuple[Tuple[str, str, Path], Optional[str]], List[dict]] = {}     # (position, scope) -> the live statements, in slide order
        self._attr: Dict[Tuple[str, str], List[Tuple[Path, Optional[str]]]] = {}          # (tank, centre) -> the (path, scope) groups, in creation order
        self._scopes: Dict[Tuple[str, str, Path], List[Optional[str]]] = {}               # position -> the scopes it was written in
        self._rel: Dict[Tuple[str, str, str, str], List[dict]] = {}                       # (kind, label, first, second) -> the sentences

    # -- values ----------------------------------------------------------------------------------------------------------------------
    def observe_value(self, *, tank: str, centre: str, path: Path, scope: Optional[str], value: str, sid: int, k: int, turn: Optional[str], change: Optional[dict] = None,
                      enum: bool = True, arm: Optional[str] = None) -> List[dict]:
        """One value written at (tank, centre, path) in `scope` by clause k of sentence sid.  `change` = {"old": str|None, "form": str} for a change clause.  -> the notes (SAME_SEAT / UPDATE /
        ENUMERATION), in this order."""
        pos = (tank, centre, path)
        gk = (pos, scope)
        live = self._live.get(gk)
        new_group = live is None
        if live is None:
            live = self._live[gk] = []
            self._attr.setdefault((tank, centre), []).append((path, scope))
            self._scopes.setdefault(pos, []).append(scope)
        norm = mn.norm_answer(value)
        obs = {"sid": sid, "clause": k, "turn": turn, "value": value, "norm": norm}
        differing: List[dict] = []
        for o in live:
            if o["sid"] != sid and o["norm"] != norm and all(o["norm"] != d["norm"] for d in differing):
                differing.append(o)
        same = any(o["norm"] == norm for o in live)
        base = {"sid": sid, "clause": k, "turn": turn, "tank": tank, "centre": centre, "path": [list(p) for p in path], "scope": scope, "value": value}
        if arm is not None:
            base["arm"] = arm
        notes: List[dict] = []
        if change is not None:
            if differing or not live:
                old = change.get("old")
                n = dict(base, type=UPDATE, form=change.get("form"), old=old, first=not live, earlier=[_cite(o) for o in differing[:CITE_MAX]], earlier_n=len(differing),
                         old_matches=(mn.norm_answer(old) == live[-1]["norm"]) if (old is not None and live) else None)
                notes.append(n)
            live[:] = [obs]
        elif differing and not same:
            notes.append(dict(base, type=SAME_SEAT, earlier=[_cite(o) for o in differing[:CITE_MAX]], earlier_n=len(differing)))
            live.append(obs)
        elif not same:
            live.append(obs)
        if enum and new_group and change is None:
            notes += self._enumerations(base, tank, centre, path, scope, pos, norm)
        return notes

    def _enumerations(self, base: dict, tank: str, centre: str, path: Path, scope: Optional[str], pos: Tuple[str, str, Path], norm: str) -> List[dict]:
        out: List[dict] = []
        if tank == "F1" and path:                                       # another owner of the same attribute with another value
            others = []
            for p2, s2 in self._attr.get((tank, centre), ()):
                if p2 == path:
                    continue
                l2 = self._live.get(((tank, centre, p2), s2), ())
                if l2 and all(o["norm"] != norm for o in l2):
                    others.append({"path": [list(p) for p in p2], "scope": s2, "sid": l2[-1]["sid"], "value": l2[-1]["value"]})
            if others:
                out.append(dict(base, type=ENUMERATION, reason="arm_owner", others=others[-ENUM_CITE_MAX:], others_n=len(others)))
        others = []                                                     # the same position in another nest with another value
        for s2 in self._scopes.get(pos, ()):
            if s2 == scope:
                continue
            l2 = self._live.get((pos, s2), ())
            if l2 and all(o["norm"] != norm for o in l2):
                others.append({"path": [list(p) for p in path], "scope": s2, "sid": l2[-1]["sid"], "value": l2[-1]["value"]})
        if others:
            out.append(dict(base, type=ENUMERATION, reason="nest", others=others[-ENUM_CITE_MAX:], others_n=len(others)))
        return out

    # -- events ----------------------------------------------------------------------------------------------------------------------
    def observe_event(self, *, tank: str, centre: str, arms: Sequence[Tuple[str, str]], scope: Optional[str], sid: int, k: int, turn: Optional[str]) -> List[dict]:
        """An event clause (F3, a completed F4 included; F4 when no nest completed it): `arms` = (particle, phrase) of its top-level arms.  Each adjunct arm (で に と) is a value at the position (F3, centre, the other arms,
        @arm); the context must hold a が or a を."""
        notes: List[dict] = []
        for i, (p, ph) in enumerate(arms):
            if p not in ADJUNCT_ARMS:
                continue
            fixed = tuple((q, x) for j, (q, x) in enumerate(arms) if j != i)
            if not any(q in CONTEXT_ARMS for q, _ in fixed):
                continue
            notes += self.observe_value(tank=tank, centre=centre, path=fixed + ((EVENT_MARK, p),), scope=scope, value=ph, sid=sid, k=k, turn=turn, enum=False, arm=p)
        return notes

    # -- relations (the reversal) --------------------------------------------------------------------------------------------------
    def observe_relation(self, *, kind: str, label: str, first: str, second: str, particle: str, first_units: Sequence[str], second_units: Sequence[str], sid: int, k: int, turn: Optional[str],
                         judge: Optional[JudgeFn]) -> List[dict]:
        """A relation as the clause writes it: `first` is written before `second`.  A REVERSAL_X note when ANOTHER sentence holds (kind, label, second, first)."""
        key, rkey = (kind, label, first, second), (kind, label, second, first)
        notes: List[dict] = []
        if first != second:
            earlier = [o for o in self._rel.get(rkey, ()) if o["sid"] != sid]
            if earlier:
                cites = []
                for o in earlier[:CITE_MAX]:
                    d = {"sid": o["sid"], "clause": o["clause"]}
                    if o.get("turn") is not None:
                        d["turn"] = o["turn"]
                    cites.append(d)
                key_view = judge(particle, first_units, second_units) if judge is not None else None
                notes.append({"type": REVERSAL_X, "sid": sid, "clause": k, "turn": turn, "relation": kind, "label": label, "pair": [first, second], "earlier": cites, "earlier_n": len(earlier),
                              "key": key_view})
        self._rel.setdefault(key, []).append({"sid": sid, "clause": k, "turn": turn})
        return notes


def order_notes(notes: Sequence[dict]) -> List[dict]:
    """The notes of one sentence in a fixed order: type, clause, canonical form."""
    return sorted(notes, key=lambda n: (CROSS_NOTE_TYPES.index(n["type"]), n["clause"], mn.canonical(n)))
