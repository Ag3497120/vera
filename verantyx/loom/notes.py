"""LOOM-notes: typed annotations that point and let pass (docs/LINE3_LOOM_DESIGN.md 12.2 "LOOM-notes", owner 「気づきの置き方」 layer (2)),
and the self-correction metrics of layer (3), computed from the ledger.

THREE LAYERS, NEVER MIXED
  (1) prevention   the typed refusals of the core (unchanged; notes never add, remove or reorder a refusal)
  (2) notes        this module: a thread-wide consistency pass at `read` / `emit` and, since LOOM-span (L-LOOM-137), after an ok `weave_span` (a batch weave puts a whole chain in at once and
                   nothing else reads it back), that does NOT block.  It returns a list of typed notes;
                   the text, the output_sha and the refusals are untouched, and so are the bytes of every row up to the first note row
                   (later rows keep op / args / result but not `i`, `prov.at`, `state_sha`: L-LOOM-95).  The notes travel in the RESULT of
                   `read` / `emit` / `weave_span` (a top-level key `notes`, absent when there are none, never inside `annotated`) and in a row of their
                   own, op `loom_note`, actor `loom`, appended right AFTER the read / emit row (mcp.LoomServer._exec; replay re-derives
                   and checks it; the row carries `nv` = NOTES_VERSION).
  (3) noticing     `self_corrections(rows)`: what the model did that can be read as noticing, observed from the ledger only.

THE NOTES (exact definitions; L-LOOM-95..)
  CONFLICT  prose  Two LINKED crosses A, B (A != B) of one tier with the same centre surface, and an arm (same particle) that is non-empty
                   in both with different contents, where the content of an arm is the tuple of the surfaces of its data units, outer ->
                   inner (the order they are read).  Record and constructed units both count (a constructed 大阪 against a record 東京 is a
                   contradiction too).  An arm empty in one of the two is not a contradiction; the topic mark, the cross length and the other
                   arms are ignored.  One note per (tier, centre, arm); its `variants` list the distinct contents in thread order.
            code   The same name bound twice in one scope of the thread, where at least one binding is a DEFINITION (`def`, `class` or
                   `import`) and the bindings differ.  Scope = the module, or the body of one `def` / `class`.  Plain (re)assignment
                   against plain assignment is not a conflict (an accumulator `s = 0 ... s = add(s, x)` is ordinary).  A repeated identical
                   definition or identical import is not a contradiction.
                   KNOWN non-contradictions that DO fire (open points, L-LOOM-112): `try: import x` / `except ImportError: x = None`, and
                   alternative definitions of one name in the two branches of an `if` / `else`.  Prose has the same kind of case: an
                   enumeration (日本の首都 ... フランスの首都 is two centres, with a shared surface 首都) is indistinguishable from a contradiction.
  UNANCHORED prose A unit seated on a DATA seat of an arm with particle p whose corpus evidence is for another ARM particle and not for p:
                   anchor(u) = the unit itself when it is a record unit; for a constructed unit (which is in no tier, so has no adhesion of
                   its own: L-52, constructed_shadows_record) the LONGEST PROPER SUFFIX of AT LEAST 2 CHARACTERS of its surface that has
                   adhesion evidence in the tier of its cross.  Condition: adj(anchor, p) == 0 and adj(anchor, q) >= 2 (two distinct
                   sentences) for some arm particle q != p (OP-LOOM-5: the floor).  The centre relation は is not an arm and never
                   counts.  No evidence anywhere = no note (the structure has nothing to say).  Code has no adhesion tables: never.
  NO_RECORD  both  A constructed unit in the thread whose surface (NFC) was looked up before the unit was added (the LAST such `lookup` row,
                   any tier) and the lookup returned no match.  No earlier lookup of that surface = no note.  A CODE note carries a `role`
                   (what the unit is in the code): definition_name (a name the thread binds: def / class / parameter / assignment target /
                   import alias), use_of_thread_name (a use of a name the thread binds), literal (a number or string token), fallback
                   (anything else).  Only `fallback` is counted as ungrounded by note_summary.
  QUESTION_ECHO prose (notes.v2 only; a run whose begin row names notes.v1 never has it)  A unit seated in a LINKED cross, record or constructed, of at least
                   MIN_ECHO_CHARS = 2 characters, whose surface (NFKC, casefold) occurs as a substring of the question text of the task (NFKC, casefold).
                   The answer should not repeat the words of the question; the note POINTS at the unit (cid, seat, uid, unit) and never blocks.  It reads the
                   task text and the thread only: no gold, no corpus, no clock.  A thread that is a quotation of the corpus (weave_span) is flagged unit by unit.

Every list is sorted without any set / dict iteration order: (type order, thread position, cid, seat order).  Nothing here reads a
clock, a path or the environment.
"""
from __future__ import annotations

import ast
import tokenize
import unicodedata
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from verantyx.line3 import foundation as fd
from verantyx.loom import code as codelib
from verantyx.loom import read as rd
from verantyx.loom.state import AXES, CENTRE, CODE, CONSTRUCTED, PROSE, RECORD, SPEC, LoomCross, canonical, fmt_seat

CONFLICT, UNANCHORED, NO_RECORD = "CONFLICT", "UNANCHORED", "NO_RECORD"
QUESTION_ECHO = "QUESTION_ECHO"                                  # L-LOOM-147 (notes.v2): a prose thread unit that is a word of the question itself
NOTE_TYPES: Tuple[str, ...] = (CONFLICT, UNANCHORED, NO_RECORD, QUESTION_ECHO)
NOTE_OP = "loom_note"
NOTES_V1, NOTES_V2 = "notes.v1", "notes.v2"                      # v2 = v1 + QUESTION_ECHO.  A run uses ONE version for its whole life: its `begin` row names it
NOTES_VERSIONS: Tuple[str, ...] = (NOTES_V1, NOTES_V2)           # (`notes_profile`, absent = v1), so a ledger recorded under v1 still has no echo note due on any row
NOTES_VERSION = NOTES_V2                                         # what a NEW run gets; stored in every new note row as `nv` (a run's rows carry its own version)
MIN_ECHO_CHARS = 2                                               # a one-character unit (年 in 何年) is never an echo
NOTE_ACTOR = "loom"
NOTE_AFTER_OPS: Tuple[str, ...] = ("read", "emit", "weave_span")           # the model rows a note row can follow (LOOM-span: a weave is a structure change that nothing else reads back)
ARM_PARTICLES: Tuple[str, ...] = tuple(SPEC.arms)             # the six arm particles; は (the centre relation) is not one of them


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# ------------------------------------------------------------------------------------------------------------
# CONFLICT, prose
# ------------------------------------------------------------------------------------------------------------
def _arm_contents(state, cross: LoomCross) -> Dict[str, List[dict]]:
    """arm axis -> its data units outer -> inner as {uid, s, kind} (empty arms are absent)."""
    out: Dict[str, List[dict]] = {}
    for ax in AXES:
        cells = [c for c in cross.arms[AXES.index(ax)] if c is not None and not fd.is_constructed(c)]
        if cells:
            out[ax] = [{"uid": c, "s": state.units[c].surface, "kind": state.units[c].kind} for c in cells]
    return out


def conflicts_prose(run, linked: Sequence[LoomCross]) -> List[dict]:
    state = run.state
    groups: Dict[Tuple[str, str], List[LoomCross]] = {}
    order: List[Tuple[str, str]] = []
    for c in linked:
        if c.lang != PROSE or c.centre is None:
            continue
        key = (c.tier, state.units[c.centre].surface)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(c)
    out: List[dict] = []
    for key in order:
        crosses = groups[key]
        if len(crosses) < 2:
            continue
        contents = [(c, _arm_contents(state, c)) for c in crosses]
        for ax in rd.ARM_ORDER:
            variants: List[dict] = []
            seen: Dict[Tuple[str, ...], dict] = {}
            for c, arms in contents:
                if ax not in arms:
                    continue
                tup = tuple(u["s"] for u in arms[ax])
                v = seen.get(tup)
                if v is None:
                    v = seen[tup] = {"cids": [], "units": arms[ax]}
                    variants.append(v)
                v["cids"].append(c.cid)
            if len(variants) >= 2:
                out.append({"type": CONFLICT, "kind": "arm_contents", "tier": key[0], "centre": key[1], "arm": ax,
                            "particle": SPEC.arm_of_axis(ax), "variants": variants, "_pos": linked.index(crosses[0]), "_arm": rd.ARM_ORDER.index(ax)})
    return out


# ------------------------------------------------------------------------------------------------------------
# CONFLICT, code: the same name bound twice in one scope
# ------------------------------------------------------------------------------------------------------------
class _Bindings:
    def __init__(self) -> None:
        self.by_key: Dict[Tuple[str, str], List[dict]] = {}
        self.order: List[Tuple[str, str]] = []

    def add(self, scope: str, name: str, how: str, line: int, sig: Any) -> None:
        k = (scope, name)
        if k not in self.by_key:
            self.by_key[k] = []
            self.order.append(k)
        self.by_key[k].append({"how": how, "line": line, "sig": sig})

    def stmts(self, stmts: Iterable[ast.stmt], scope: str) -> None:
        for n in stmts:
            line = getattr(n, "lineno", 0)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                how = "class" if isinstance(n, ast.ClassDef) else "def"
                self.add(scope, n.name, how, line, ("def", ast.dump(n)))
                self.stmts(n.body, n.name if scope == "<module>" else scope + "." + n.name)
                continue
            if isinstance(n, ast.Import):
                for a in n.names:
                    self.add(scope, a.asname or a.name.split(".")[0], "import", line, ("import", a.name, None, a.asname))
            elif isinstance(n, ast.ImportFrom):
                for a in n.names:
                    if a.name != "*":
                        self.add(scope, a.asname or a.name, "import", line, ("import", n.module, a.name, a.asname, n.level))
            else:
                targets: List[ast.Name] = []
                if isinstance(n, ast.Assign):
                    targets = [x for t in n.targets for x in codelib._binding_names(t)]
                elif isinstance(n, (ast.AnnAssign, ast.AugAssign, ast.For, ast.AsyncFor)):
                    targets = codelib._binding_names(n.target)
                for x in targets:
                    self.add(scope, x.id, "assign", getattr(x, "lineno", line), ("assign", getattr(x, "lineno", line), getattr(x, "col_offset", 0)))
            for field in ("body", "orelse", "finalbody"):
                sub = getattr(n, field, None)
                if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                    self.stmts(sub, scope)
            for h in getattr(n, "handlers", None) or []:
                self.stmts(h.body, scope)
            for case in getattr(n, "cases", None) or []:
                self.stmts(case.body, scope)


def code_text(run, linked: Sequence[LoomCross]) -> Tuple[str, List[str]]:
    """The text the code thread reads as and the cross that printed each line (the same walk as read.evaluate)."""
    segs: List[dict] = []
    line_cids: List[str] = []
    for c in linked:
        if c.lang != CODE:
            continue
        cs, _ok = rd.read_code(run.state, c)
        segs.extend(cs)
        if cs:
            line_cids.append(c.cid)
    return "".join(s["s"] for s in segs), line_cids


def conflicts_code(run, linked: Sequence[LoomCross]) -> List[dict]:
    text, line_cids = code_text(run, linked)
    if not text:
        return []
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return []                                           # the parse gate has already said so; there is no binding to compare
    b = _Bindings()
    b.stmts(tree.body, "<module>")
    n_lines = len(text.splitlines())
    out: List[dict] = []
    for k in b.order:
        bs = b.by_key[k]
        if len(bs) < 2 or all(x["how"] == "assign" for x in bs):
            continue
        if len({repr(x["sig"]) for x in bs}) < 2:
            continue                                        # the same definition twice is a repeat, not a contradiction
        binds = []
        for x in bs:
            cid = line_cids[x["line"] - 1] if n_lines == len(line_cids) and 1 <= x["line"] <= len(line_cids) else None
            binds.append({"how": x["how"], "line": x["line"], "cid": cid})
        first = next((x["cid"] for x in binds if x["cid"] is not None), None)
        out.append({"type": CONFLICT, "kind": "name_bound_twice", "name": k[1], "scope": k[0], "bindings": binds,
                    "_pos": linked.index(run.state.crosses[first]) if first is not None else 0, "_arm": bs[0]["line"]})
    return out


# ------------------------------------------------------------------------------------------------------------
# UNANCHORED
# ------------------------------------------------------------------------------------------------------------
def _evidence(adh, surface: str) -> List[Tuple[str, int]]:
    """[(arm particle, adj)] for the particles with adj > 0, in the ladder order of SPEC.arms."""
    return [(p, adh.adj(surface, p)) for p in ARM_PARTICLES if adh.adj(surface, p) > 0]


MIN_CONTRA_SENTENCES = 2         # OP-LOOM-5: the contradicting particle needs this many distinct sentences
MIN_SUFFIX_CHARS = 2             # OP-LOOM-5: a suffix anchor is at least this long


def anchor_of(adh, unit) -> Optional[Tuple[str, str, List[Tuple[str, int]]]]:
    """(anchor surface, via, evidence) or None.  A record unit anchors itself (`self`); a constructed unit has no adhesion of its own, so
    its anchor is the longest PROPER suffix of at least MIN_SUFFIX_CHARS characters that has arm evidence in the tier (`suffix`)."""
    if unit.kind == RECORD:
        ev = _evidence(adh, unit.surface)
        return (unit.surface, "self", ev) if ev else None
    s = unit.surface
    for i in range(1, len(s) - MIN_SUFFIX_CHARS + 1):
        ev = _evidence(adh, s[i:])
        if ev:
            return (s[i:], "suffix", ev)
    return None


def unanchored(run, linked: Sequence[LoomCross]) -> List[dict]:
    state, corpus = run.state, run.corpus
    out: List[dict] = []
    for pos, c in enumerate(linked):
        if c.lang != PROSE or c.tier not in corpus.adhesion:
            continue
        adh = corpus.adhesion[c.tier]
        for ax in rd.ARM_ORDER:
            p = SPEC.arm_of_axis(ax)
            arm = c.arms[AXES.index(ax)]
            for k in range(0, c.inner_k + 1):
                uid = arm[k]
                if uid is None:
                    continue
                u = state.units[uid]
                a = anchor_of(adh, u)
                if a is None:
                    continue
                surface, via, ev = a
                have = adh.adj(surface, p)
                if have == 0 and any(q != p and n >= MIN_CONTRA_SENTENCES for q, n in ev):
                    out.append({"type": UNANCHORED, "cid": c.cid, "seat": fmt_seat(ax, k), "arm": ax, "particle": p, "uid": uid, "unit": u.surface,
                                "kind": u.kind, "anchor": {"surface": surface, "via": via, "tier": c.tier},
                                "have": have, "evidence": [{"particle": q, "n": n} for q, n in ev], "_pos": pos, "_arm": rd.ARM_ORDER.index(ax) * 100 + k})
    return out


# ------------------------------------------------------------------------------------------------------------
# NO_RECORD
# ------------------------------------------------------------------------------------------------------------
def last_empty_lookup(lookups: Sequence[Tuple[int, str, bool]], surface: str, before: int) -> Optional[int]:
    """The row index of the LAST ok `lookup` row of `surface` (NFC) before row `before`, if its matches were empty; else None."""
    s = nfc(surface)
    last: Optional[Tuple[int, bool]] = None
    for i, text, empty in lookups:
        if i < before and text == s:
            last = (i, empty)
    return last[0] if last is not None and last[1] else None


ROLE_DEFINITION, ROLE_USE, ROLE_LITERAL, ROLE_FALLBACK = "definition_name", "use_of_thread_name", "literal", "fallback"
ROLES: Tuple[str, ...] = (ROLE_DEFINITION, ROLE_USE, ROLE_LITERAL, ROLE_FALLBACK)


def _binding_positions(tree: ast.AST) -> Tuple[set, set, set]:
    """({(line, byte col)} where a name is BOUND, {(line, byte col)} of Name loads, {names bound anywhere in the tree}), from the AST."""
    bound_at: set = set()
    loads: set = set()
    names: set = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name):
            if isinstance(n.ctx, ast.Load):
                loads.add((n.lineno, n.col_offset))
            else:
                bound_at.add((n.lineno, n.col_offset))
                names.add(n.id)
        elif isinstance(n, ast.arg):
            bound_at.add((n.lineno, n.col_offset))
            names.add(n.arg)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)                                   # the name token itself is found by the `def` / `class` keyword before it
        elif isinstance(n, ast.alias) and getattr(n, "lineno", None) is not None:
            if n.asname is None:
                bound_at.add((n.lineno, n.col_offset))
                names.add(n.name.split(".")[0])
            else:
                names.add(n.asname)                             # the alias token itself is found by the `as` before it
    return bound_at, loads, names


def code_roles(run, linked: Sequence[LoomCross]) -> Dict[Tuple[str, str], str]:
    """(cid, seat) -> role of the constructed code unit seated there (see the module doc).  Token level: the unit right after `def` /
    `class` / `as` is a definition name; with the AST (when the thread parses) also parameters, assignment / loop / with targets and
    imported names; a unit whose surface is a name the thread binds and that is a Name load is a use of it; a NUMBER / STRING token is a
    literal; everything else is `fallback`."""
    segs: List[dict] = []
    for c in linked:
        if c.lang == CODE:
            cs, _ok = rd.read_code(run.state, c)
            segs.extend(cs)
    text = "".join(sg["s"] for sg in segs)
    lines = text.split("\n")
    bound_at: set = set()
    loads: set = set()
    names: set = set()
    parsed = False
    try:
        bound_at, loads, names = _binding_positions(ast.parse(text))
        parsed = True
    except (SyntaxError, ValueError, RecursionError):
        pass
    units: List[Tuple[str, str, str, int, int, str]] = []          # (cid, seat, surface, line, byte col, previous unit surface on the line)
    off, prev_s, prev_line = 0, "", 0
    for sg in segs:
        if sg["kind"] in (RECORD, CONSTRUCTED):
            line = text.count("\n", 0, off) + 1
            col = off - (text.rfind("\n", 0, off) + 1)
            bcol = len(lines[line - 1][:col].encode("utf-8"))
            units.append((sg["cid"], sg["seat"], sg["s"], line, bcol, prev_s if prev_line == line else ""))
            prev_s, prev_line = sg["s"], line
        off += len(sg["s"])
    if not parsed:                                                  # without an AST, the names the thread defines are the ones after def / class
        names = {s for _c, _t, s, _l, _b, ps in units if ps in ("def", "class", "as")}
    out: Dict[Tuple[str, str], str] = {}
    for cid, seat, surf, line, bcol, ps in units:
        if _token_kind(surf) in ("NUMBER", "STRING"):
            role = ROLE_LITERAL
        elif ps in ("def", "class", "as") or (line, bcol) in bound_at:
            role = ROLE_DEFINITION
        elif surf in names and ((line, bcol) in loads if parsed else surf.isidentifier()):
            role = ROLE_USE
        else:
            role = ROLE_FALLBACK
        out[(cid, seat)] = role
    return out


def _token_kind(surface: str) -> str:
    """NUMBER / STRING / NAME / OP / '' for a one-token surface (a constructed code unit is exactly one token: L-LOOM-11)."""
    try:
        toks = codelib.tokens_of(surface)
    except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
        return ""
    return tokenize.tok_name.get(toks[0][0], "") if toks else ""


def no_record(run, linked: Sequence[LoomCross]) -> List[dict]:
    state = run.state
    roles = code_roles(run, linked) if run.lang == CODE else {}
    out: List[dict] = []
    for pos, c in enumerate(linked):
        cells: List[Tuple[str, str]] = []
        if c.centre is not None:
            cells.append((CENTRE, c.centre))
        for ax in (AXES if c.lang == CODE else rd.ARM_ORDER):
            arm = c.arms[AXES.index(ax)]
            for k in range(0, c.inner_k + 1):
                if arm[k] is not None:
                    cells.append((fmt_seat(ax, k), arm[k]))
        for idx, (seat, uid) in enumerate(cells):
            u = state.units[uid]
            if u.kind != CONSTRUCTED:
                continue
            at = u.prov["at"]
            li = last_empty_lookup(run.lookup_log, u.surface, at)
            if li is not None:
                note = {"type": NO_RECORD, "cid": c.cid, "seat": seat, "uid": uid, "unit": u.surface, "lookup_i": li, "added_at": at,
                        "_pos": pos, "_arm": idx}
                if c.lang == CODE:
                    note["role"] = roles.get((c.cid, seat), ROLE_FALLBACK)
                out.append(note)
    return out


def _fold(s: str) -> str:
    return unicodedata.normalize("NFKC", s).casefold()


def question_echo(run, linked: Sequence[LoomCross]) -> List[dict]:
    """QUESTION_ECHO (prose, notes.v2): the linked-thread units of >= MIN_ECHO_CHARS characters that occur in the question text."""
    q = _fold(run.task["text"])
    state = run.state
    out: List[dict] = []
    for pos, c in enumerate(linked):
        if c.lang != PROSE:
            continue
        cells: List[Tuple[str, str]] = []
        if c.centre is not None:
            cells.append((CENTRE, c.centre))
        for ax in rd.ARM_ORDER:
            arm = c.arms[AXES.index(ax)]
            for k in range(0, c.inner_k + 1):
                if arm[k] is not None:
                    cells.append((fmt_seat(ax, k), arm[k]))
        for idx, (seat, uid) in enumerate(cells):
            surf = state.units[uid].surface
            if len(surf) >= MIN_ECHO_CHARS and _fold(surf) in q:
                out.append({"type": QUESTION_ECHO, "cid": c.cid, "seat": seat, "uid": uid, "unit": surf, "_pos": pos, "_arm": idx})
    return out


# ------------------------------------------------------------------------------------------------------------
# the pass
# ------------------------------------------------------------------------------------------------------------
def compute(run) -> List[dict]:
    """Every note of the linked thread now (a dry pass: nothing is changed, nothing is written).  [] when there is nothing to say.
    Deterministic: the order is (type, thread position, seat order)."""
    state = run.state
    linked = [state.crosses[cid] for cid in state.thread]
    found: List[dict] = []
    if run.lang == PROSE:
        found += conflicts_prose(run, linked)
        found += unanchored(run, linked)
        if run.notes_version != NOTES_V1:
            found += question_echo(run, linked)
    else:
        found += conflicts_code(run, linked)
    found += no_record(run, linked)
    found.sort(key=lambda n: (NOTE_TYPES.index(n["type"]), n["_pos"], n["_arm"], canonical({k: v for k, v in n.items() if not k.startswith("_")})))
    return [{k: v for k, v in n.items() if not k.startswith("_")} for n in found]


# ------------------------------------------------------------------------------------------------------------
# layer (3): self-corrections, from the ledger and nothing else
# ------------------------------------------------------------------------------------------------------------
_NON_RECOVERABLE = frozenset(("run_closed", "unknown_tool", "cap_exceeded", "ops_cap", "lookup_cap", "read_cap", "emit_cap", "args_too_large"))


def _model_ops():
    from verantyx.loom.ops import LEGACY_OPS, MODEL_OPS     # lazily: ops imports this module
    return MODEL_OPS + LEGACY_OPS                           # a refusal of a legacy op in an old ledger still counts


def self_corrections(rows: Sequence[dict]) -> dict:
    """The three self-corrections of the meter (design LOOM-notes (3); the canonical form of experiments/line3/loom/score.py
    `self_corrections`, L-LOOM-56, which it equals row for row), read from the ledger and nothing else:
      unseat_swap_before_close   an ok `unseat` / `swap` row of the model before the row that closes the run (all of them if it never closed)
      plan_change_after_empty    an ok `lookup` with no match, whose NEXT model row is a lookup / add with other text or tier, or a read_sentence
                                 (the next row being `abstain` is a conclusion, not a plan change)
      recovery_after_refusal     a refused model row of a recoverable op (a cap, run_closed, unknown_tool are not recoverable and are left
                                 out) that is followed later by an ok row of the SAME op (a stated approximation: the op name only)
    `refusals_recoverable` is the denominator of the recovery rate.  Rows of other actors (harness, human, loom) are ignored."""
    model_ops = _model_ops()
    model = [r for r in rows if r["actor"] == "model"]
    close_i = None
    for r in model:
        if r["op"] in ("emit", "abstain") and r["result"].get("ok") is True and r["result"].get("status") in ("emitted", "abstained"):
            close_i = r["i"]
            break
    out: Dict[str, Any] = {"unseat_swap_before_close": [], "plan_change_after_empty": [], "recovery_after_refusal": [], "refusals_recoverable": 0}
    for r in model:
        if r["op"] in ("unseat", "swap") and r["result"].get("ok") is True and (close_i is None or r["i"] < close_i):
            out["unseat_swap_before_close"].append({"i": r["i"], "op": r["op"]})
    for k, r in enumerate(model):
        if r["op"] == "lookup" and r["result"].get("ok") is True and r["result"].get("matches") == []:
            nxt = model[k + 1] if k + 1 < len(model) else None
            if nxt is None:
                continue
            if nxt["op"] == "read_sentence" or (nxt["op"] in ("lookup", "add") and
                                                (nxt["args"].get("text"), nxt["args"].get("tier")) != (r["args"].get("text"), r["args"].get("tier"))):
                out["plan_change_after_empty"].append({"i": r["i"], "next_i": nxt["i"], "next_op": nxt["op"]})
    for k, r in enumerate(model):
        res = r["result"]
        if res.get("ok") is False and res.get("refusal") not in _NON_RECOVERABLE and r["op"] in model_ops:
            out["refusals_recoverable"] += 1
            if any(q["op"] == r["op"] and q["result"].get("ok") is True for q in model[k + 1:]):
                out["recovery_after_refusal"].append({"i": r["i"], "op": r["op"], "refusal": res.get("refusal")})
    out["counts"] = {"unseat_swap_before_close": len(out["unseat_swap_before_close"]),
                     "plan_change_after_empty": len(out["plan_change_after_empty"]),
                     "recovery_after_refusal": len(out["recovery_after_refusal"]), "refusals_recoverable": out["refusals_recoverable"]}
    return out


def recovery_rate(sc: dict) -> Optional[Tuple[int, int]]:
    """(recovered, recoverable refusals) as an exact pair, None when the run had no recoverable refusal (no float, no 0/0)."""
    d = sc["counts"]["refusals_recoverable"]
    return None if d == 0 else (sc["counts"]["recovery_after_refusal"], d)


def note_key(note: dict) -> tuple:
    """A note is identified by WHERE it is, not by its payload (a conflict that grows from two variants to three is the same note):
    CONFLICT prose (tier, centre, arm); CONFLICT code (scope, name); UNANCHORED / NO_RECORD (cid, seat, uid)."""
    if note["type"] == CONFLICT:
        if note.get("kind") == "name_bound_twice":
            return (CONFLICT, "name_bound_twice", note.get("scope"), note.get("name"))
        return (CONFLICT, "arm_contents", note.get("tier"), note.get("centre"), note.get("arm"))
    return (note.get("type"), note.get("cid"), note.get("seat"), note.get("uid"))


def is_ungrounded(note: dict) -> bool:
    """A NO_RECORD note that says something about the model's choice: a prose unit, or a code unit with role `fallback`.  The name of a
    function the thread defines, a use of it and a literal are not counted."""
    return note["type"] == NO_RECORD and note.get("role", ROLE_FALLBACK) == ROLE_FALLBACK


def note_observations(rows: Sequence[dict]) -> List[dict]:
    """One observation per ok model `read` / `emit` / `weave_span` row: {i, op, notes} where notes are those of the note row that follows it directly
    ([] when none follows)."""
    obs: List[dict] = []
    for k, r in enumerate(rows):
        if r["actor"] == "model" and r["op"] in NOTE_AFTER_OPS and r["result"].get("ok") is True:
            nxt = rows[k + 1] if k + 1 < len(rows) else None
            notes = nxt["args"]["notes"] if nxt is not None and nxt["actor"] == NOTE_ACTOR and nxt["op"] == NOTE_OP else []
            obs.append({"i": r["i"], "op": r["op"], "notes": notes})
    return obs


def note_summary(rows: Sequence[dict]) -> dict:
    """What the model did with the notes it was shown (observed, not guaranteed).  A note is identified by its location (`note_key`), so a
    note shown again with a changed payload is the same note:
      by_type          distinct notes shown, by type
      ungrounded       the distinct NO_RECORD notes that are `is_ungrounded` (role fallback, or prose)
      shown            distinct notes shown
      resolved         a note present at one observation and absent (by location) at the NEXT one although the model changed the state
                       in between (an ok state-changing model row)
      at_close         notes on the observation of the closing emit (emitted with notes: the model saw them or not, and went on)
    """
    from verantyx.loom.ops import STATE_CHANGING
    obs = note_observations(rows)
    by_type = {t: 0 for t in NOTE_TYPES}
    seen = set()
    ungrounded = set()
    for o in obs:
        for n in o["notes"]:
            k = note_key(n)
            if k not in seen:
                seen.add(k)
                by_type[n["type"]] += 1
                if is_ungrounded(n):
                    ungrounded.add(k)
    resolved = []
    for a, b in zip(obs, obs[1:]):
        changed = any(r["actor"] == "model" and r["op"] in STATE_CHANGING and r["result"].get("ok") is True and a["i"] < r["i"] < b["i"] for r in rows)
        if not changed:
            continue
        now = {note_key(n) for n in b["notes"]}
        resolved.extend({"i": a["i"], "next_i": b["i"], "type": n["type"]} for n in a["notes"] if note_key(n) not in now)
    emitted = {r["i"] for r in rows if r["actor"] == "model" and r["op"] == "emit" and r["result"].get("status") == "emitted"}
    closing = next((o for o in obs if o["i"] in emitted), None)
    return {"observations": len(obs), "shown": len(seen), "by_type": by_type, "ungrounded": len(ungrounded), "resolved": resolved,
            "at_close": None if closing is None else [n["type"] for n in closing["notes"]]}
