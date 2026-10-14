"""PUB-M7 (view.v1): the WINDOW the model sees, and the per-turn BUDGET (docs/LINE3_PUBLIC_DESIGN.md 4.8, 6.2; owner OP-PUB-5; local decisions L-PUB-120..).

A write of a mem.v4 session returns (and the ledger stores) the cross JSON of the sentence: several thousand characters, the main cost of the meter v1 (the crosses were piled into the conversation).  Under
`view.v1` the MODEL-FACING result of a write is a handful of short lines -- the seats the sentence changed and the notes it fired -- and the model reads the memory through two more tools:

  view(centre)      the crosses (tanks F1-F4) whose centre is `centre`, every seat with its provenance (sid, turn, session, record | constructed), the key (n, p, a) and the rank on its arm, the values of each
                    position in slide order -- capped at `lines` lines (default 40, the last line says how many were left out);
  view_nest(topic)  the nest of a declared topic and the clauses that belong to it (kind completed | centre | path | context) -- capped the same way.

The LEDGER is not touched by the compaction: the row of a write keeps its full result (so every stored ledger and every replay is as it was); only what the DRIVER delivers to the model is the short form
(`compact_write`, a pure function of the ledger result and the index).  `view` / `view_nest` are ops of the session (rows of the ledger, read-only, counted by a cap of their own).

THE BUDGET.  A turn (one delivered message of a story session; one whole question episode) may be delivered at most `budget` characters of tool results (the JSON text of the results, as the driver puts it into
the conversation).  `BudgetDoor` wraps ANY door (the structure arms, the plain log, the context-only arm, the answer door): a result that does not fit is replaced by
{"ok": <the ok of the result>, "budget_cut": "<the first characters of the result's JSON>[budget: N chars omitted]"} (N = the characters of the result that were not delivered), and the cut is recorded:
as the harness row `budget_turn` {turn, tool, budget, chars, kept, omitted, spent} in a ledger whose begin row records the budget (a mem.v4 session with `view`; membase.v3), else in `BudgetDoor.events`
(the answer runs: their ledger format is the loom's and is not extended).  The control tools (`report`, `answer`, `emit`, `abstain`, `done`) are NOT cut and NOT counted: they are small and the driver reads
them.  The budget is soft by at most the size of the cut marker (about 60 characters) when it is already spent.  The same code for every arm.

Pure: no clock, float, process, network, environment, no set / dict order in any output.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence

from verantyx.loom import memcross as mx
from verantyx.loom.state import Refuse

VIEW_V1 = "view.v1"
VIEW_OPS = ("view", "view_nest")
BUDGET_DEFAULT = 6000
BUDGET_MIN, BUDGET_MAX = 100, 200000
LINES_DEFAULT = 40
LINES_MIN, LINES_MAX = 5, 200
LINE_CHARS = 160
EXEMPT_TOOLS = ("report", "answer", "emit", "abstain", "done")
MARKER = "[budget: %d chars omitted]"


def make_view(budget: int = BUDGET_DEFAULT, lines: int = LINES_DEFAULT) -> Dict[str, Any]:
    return check_view({"version": VIEW_V1, "budget": budget, "lines": lines})


def check_view(v: Any) -> Dict[str, Any]:
    """The `view` block of a begin row: exactly {version: view.v1, budget: int, lines: int} within the limits.  `Refuse bad_policy` otherwise."""
    ok = (isinstance(v, dict) and sorted(v) == ["budget", "lines", "version"] and v["version"] == VIEW_V1
          and all(isinstance(v[k], int) and not isinstance(v[k], bool) for k in ("budget", "lines"))
          and BUDGET_MIN <= v["budget"] <= BUDGET_MAX and LINES_MIN <= v["lines"] <= LINES_MAX)
    if not ok:
        raise Refuse("bad_policy", {"policy": "view", "value": v if isinstance(v, dict) else None, "allowed": {"version": VIEW_V1, "budget": [BUDGET_MIN, BUDGET_MAX], "lines": [LINES_MIN, LINES_MAX]}})
    return {"version": v["version"], "budget": v["budget"], "lines": v["lines"]}


def budget_args(args: Any, view: Dict[str, Any]) -> dict:
    """The args of a `budget_turn` harness row: {turn (a turn id), tool, budget (= the begin row's), chars (the full result), kept (its characters that were delivered), omitted (= chars - kept), spent (the
    characters delivered in the turn so far, this result included)}.  Raises ValueError, as every malformed harness row does."""
    if not (isinstance(args, dict) and sorted(args) == ["budget", "chars", "kept", "omitted", "spent", "tool", "turn"]):
        raise ValueError("budget_turn: arguments are turn, tool, budget, chars, kept, omitted, spent")
    ints = all(isinstance(args[k], int) and not isinstance(args[k], bool) and args[k] >= 0 for k in ("budget", "chars", "kept", "omitted", "spent"))
    if not (ints and isinstance(args["turn"], str) and 1 <= len(args["turn"]) <= 12 and isinstance(args["tool"], str) and 1 <= len(args["tool"]) <= 64
            and args["budget"] == view["budget"] and args["kept"] + args["omitted"] == args["chars"]):
        raise ValueError("budget_turn: counts are non-negative, budget is the begin row's, kept + omitted = chars")
    return dict(args)


# ------------------------------------------------------------------------------------------------------------
# lines
# ------------------------------------------------------------------------------------------------------------
def _clip(s: str, n: int = LINE_CHARS) -> str:
    return s if len(s) <= n else s[:n - 1] + "…"


def _turn(t: Optional[str], sid: int) -> str:
    return t if t else "s%d" % sid


def _path_text(path: Sequence[Sequence[str]]) -> str:
    return " ".join("%s:%s" % (p, ph) for p, ph in path)


def _cap(kind: str, key: str, lines: List[str], limit: int) -> dict:
    total = len(lines)
    if total > limit:
        lines = lines[:limit - 1] + ["… %d more lines" % (total - limit + 1)]
    return {"ok": True, "view": VIEW_V1, "kind": kind, "of": key, "lines": [_clip(x) for x in lines], "total": total, "omitted": max(0, total - limit)}


def _seat_line(s: Any, flat: bool, depth: int = 0) -> str:
    pv = s.prov
    out = "%s%s#%d %s s%d %s S%d %s" % ("  " * (depth + 1), s.slot, s.rank + 1, s.phrase, pv.sid, _turn(pv.turn, pv.sid), pv.session, pv.origin)
    if not flat and s.slot in mx.ARMS:
        out += " key=(%d,%d,%d)" % s.key
    if s.change is not None:
        out += " chg=%s>%s" % (s.change.old if s.change.old is not None else "?", s.change.new)
    if s.scope is not None:
        out += " in=%s" % s.scope
    if s.marks:
        out += " superseded_by=s%d" % s.marks[0].by
    if s.via:
        out += " via=%s" % s.via
    return out


def _cross_lines(ix: Any, c: Any) -> List[str]:
    flat = bool(getattr(ix, "flat", False))
    sids = []
    for o in c.occurrences:
        if o.sid not in sids:
            sids.append(o.sid)
    out = ["X %s %s L=%d written=%d sids=%s%s" % (c.tank, c.centre, c.L, len(c.occurrences), ",".join("s%d" % x for x in sids[:6]), "…" if len(sids) > 6 else "")]
    for slot, seats in c.slots:
        for s in seats:
            out.append(_seat_line(s, flat))
            for p, ch in s.arms:                                    # a chain 「X の Y の Z」: Z's seat Y carries X
                out.append(_seat_line(ch, flat, 1))
    for pos in ix.positions_of(c.centre, (c.tank,)):
        h = ix.history_full(pos)
        if h:
            out.append("H %s%s: %s" % (c.tank, (" " + _path_text(pos[2])) if pos[2] else "", " > ".join("%s(s%d%s)" % (e.value, e.sid, "" if e.kind == "first" else " " + e.kind) for e in h)))
    return out


def view_centre(ix: Any, phrase: str, limit: int) -> dict:
    """view(centre): the crosses of the tanks whose centre is `phrase`, else where the phrase appears.  `limit` lines at most."""
    lines: List[str] = []
    for c in ix.crosses:
        if c.centre == phrase:
            lines += _cross_lines(ix, c)
    if not lines:
        where = ix.centres_with(phrase)
        if where:
            lines.append("? %s is no centre; it sits in: %s" % (phrase, "; ".join("%s %s (%s)" % w for w in where[:8])))
        else:
            lines.append("? nothing in the memory has %s as a centre or a seat" % phrase)
    return _cap("cross", phrase, lines, limit)


def view_nest(ix: Any, topic: str, limit: int) -> dict:
    """view_nest(topic): the nest of the topic (the crosses' index) or, for the flat table, the rows whose topic column is the topic."""
    lines: List[str] = []
    if getattr(ix, "flat", False):
        rows = [c for c in ix.clauses if c.tank is not None and c.open_nest == topic]
        lines.append("T %s rows=%d (topic column of the flat table; no nest)" % (topic, len(rows)))
        for c in rows:
            lines.append("  s%d.%d %s %s: %s" % (c.sid, c.k, c.tank, c.centre, c.text))
        return _cap("table", topic, lines, limit)
    n = ix.nest(topic)
    if n is None:
        ns = ix.nests_of(topic)
        n = ns[0] if ns else None
    if n is None:
        return _cap("nest", topic, ["? no nest for %s (declare_topic opens one)" % topic], limit)
    lines.append("N %s %s centre=%s arms=%s declared=%s members=%d" % (n.id, n.topic, n.centre, _path_text(n.arms) or "-", ",".join("S%d@%d" % d for d in n.declared), len(n.members)))
    for m in n.members:
        cr = ix.clause_rec(m.sid, m.k)
        lines.append("  s%d.%d %s%s %s %s: %s" % (m.sid, m.k, m.kind, "" if m.exact else "~", m.tank, m.centre, "" if cr is None else cr.text))
    return _cap("nest", topic, lines, limit)


def _note_line(n: dict) -> Optional[str]:
    t = n.get("type")
    cur = _turn(n.get("turn"), n.get("sid", -1))
    cites = n.get("earlier") or []
    turns = ",".join([_turn(e.get("turn"), e.get("sid", -1)) for e in cites[:4]] + [cur])
    if t == "SAME_SEAT":
        return "! SAME_SEAT %s %s: %s vs %s turns=%s" % (n.get("tank"), n.get("centre"), n.get("value"), "|".join(str(e.get("value")) for e in cites[:3]), turns)
    if t == "UPDATE":
        return "~ UPDATE %s %s: %s > %s turns=%s" % (n.get("tank"), n.get("centre"), n.get("old") if n.get("old") is not None else "?", n.get("value"), turns)
    if t == "REVERSAL_X":
        return "! REVERSAL_X %s pair=%s turns=%s" % (n.get("label") or n.get("relation"), "/".join(str(x) for x in n.get("pair", [])), turns)
    if t == "ENUMERATION":
        return ". ENUMERATION %s %s: %s (information, %s)" % (n.get("tank"), n.get("centre"), n.get("value"), n.get("reason"))
    if t == "SAME_QUESTION":
        return "! SAME_QUESTION (gate route) %s" % cur
    if t == "REVERSAL":
        return "! REVERSAL (key route) %s" % cur
    return None


def compact_write(ix: Any, res: dict, drop_key_route: bool = False) -> dict:
    """The model-facing result of a write / keep_unshaped: the seats the sentence changed and the notes it fired, as short lines.  A refusal is passed on unchanged.  `drop_key_route` (the flat table): the old
    REVERSAL note is the loom's KEY route (the geometry), which the flat table does not have: it is not shown."""
    if res.get("ok") is not True or "sid" not in res:
        return res
    sid = res["sid"]
    lines: List[str] = []
    k = 0
    while True:
        c = ix.clause_rec(sid, k)
        if c is None:
            break
        if c.tank is None:
            lines.append("0 %s unshaped: %s" % (c.shape, c.reason))
        else:
            arms = _path_text(c.path)
            lines.append("+ %s %s%s%s%s" % (c.tank, c.centre, (" [" + arms + "]") if arms else "", (" = " + c.value) if c.value is not None else "",
                                           (" chg=%s>%s" % (c.change.old if c.change.old is not None else "?", c.change.new)) if c.change is not None else ""))
        k += 1
    for n in res.get("notes", []):
        if drop_key_route and n.get("type") == "REVERSAL":
            continue
        ln = _note_line(n)
        if ln is not None:
            lines.append(ln)
    out: Dict[str, Any] = {"ok": True, "sid": sid, "lines": [_clip(x) for x in lines[:12]]}
    if len(lines) > 12:
        out["more"] = len(lines) - 12
    if res.get("turn") is not None:
        out["turn"] = res["turn"]
    return out


# ------------------------------------------------------------------------------------------------------------
# the budget
# ------------------------------------------------------------------------------------------------------------
def result_text(out: Any) -> str:
    """The text the driver puts into the conversation for a result (the same `json.dumps` as memdriver / driver)."""
    return json.dumps(out, ensure_ascii=False, sort_keys=True)


def cut_result(out: dict, remaining: int) -> Any:
    """(the replacement result, kept, full_chars) of a result that does not fit `remaining` characters."""
    text = result_text(out)
    n = len(text)
    ok = bool(out.get("ok")) if isinstance(out, dict) else False
    kept = max(0, min(n, remaining - 70))
    while True:
        cut = {"ok": ok, "budget_cut": text[:kept] + MARKER % (n - kept)}
        if len(result_text(cut)) <= max(remaining, 0) or kept == 0:
            return cut, kept, n
        kept = max(0, kept - max(1, (len(result_text(cut)) - remaining)))


class BudgetDoor:
    """Wraps a door: every non-exempt result delivered in a turn is counted, and a result that would take the turn over `budget` characters is cut (see the module doc).  The turn starts again with
    `set_turn` (a story session); a door that is never told a turn (the answer door) is one turn for its whole run.  Everything else is the inner door's (attribute access passes through)."""

    def __init__(self, inner: Any, budget: int, *, ledger: bool) -> None:
        self.inner = inner
        self.budget = int(budget)
        self.ledger = bool(ledger)             # True: a cut is a `budget_turn` row of the inner ledger (its begin row records the budget); False: only `events`
        self.spent = 0
        self.turn: Optional[str] = None
        self.events: List[dict] = []
        self.tool_chars: Dict[str, int] = {}

    def __getattr__(self, name: str) -> Any:
        return getattr(self.__dict__["inner"], name)

    def set_turn(self, turn: str) -> None:
        self.turn = turn
        self.spent = 0
        self.inner.set_turn(turn)

    def call(self, tool: Any, args: Any = None) -> dict:
        out = self.inner.call(tool, args)
        if not isinstance(tool, str) or tool in EXEMPT_TOOLS or not isinstance(out, dict):
            return out
        text = result_text(out)
        n = len(text)
        if self.spent + n <= self.budget:
            self.spent += n
            self.tool_chars[tool] = self.tool_chars.get(tool, 0) + n
            return out
        cut, kept, full = cut_result(out, self.budget - self.spent)
        self.spent += len(result_text(cut))
        self.tool_chars[tool] = self.tool_chars.get(tool, 0) + len(result_text(cut))
        ev = {"turn": self.turn if self.turn is not None else "-", "tool": tool[:64], "budget": self.budget, "chars": full, "kept": kept, "omitted": full - kept, "spent": self.spent}
        self.events.append(ev)
        if self.ledger and self.turn is not None:
            self.inner.harness(None, "budget_turn", ev)
        return cut
