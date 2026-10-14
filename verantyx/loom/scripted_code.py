"""The scripted weaver for the CODE tier (docs/LINE3_LOOM_DESIGN.md 9.3, 10.2; ticket LOOM-code, L-LOOM-74).

A code script is a list of statements `(depth, [token, ...])`, one cross each (OP-LOOM-2 (a) 「文ごとに 1 十字」).  `weave_statements`
turns the tokens into units the way a model does, as a function of the results: `lookup(text, CODE)`, a match -> `add record`, no match ->
`add constructed`; the first token is the centre of the cross, the others fill the arms in AXES order (+x first, up to L = 8 tokens an
arm), inner to outer, with `seat_run`.  Nothing here is clever: it is the shortest honest use of the 18 operations.

K1..K5 are the five tasks of design 10.2 on the fixture `experiments/line3/loom/fixture_repo/`; `K_SCRIPTS[k]` holds the statements of
the reference solution and the variants the tests use.  This module opens no file and runs no process.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from verantyx.line3 import geometry as geo
from verantyx.loom.scripted import ScriptedWeaver

Stmt = Tuple[int, List[str]]
MAX_ARM = 8

K_TARGET: Dict[str, str] = {"K1": "calc/ops.py", "K2": "calc/ops.py", "K3": "calc/fmt.py", "K4": "calc/ops.py", "K5": "calc/fmt.py"}
K_TEST: Dict[str, str] = {k: "tests/test_%s.py" % k.lower() for k in K_TARGET}
K_TEXT: Dict[str, str] = {
    "K1": "calc/ops.py に double(x) を加えよ。mul(x, 2) を返すこと",
    "K2": "calc/ops.py に total(xs) を加えよ。xs の要素を add で順に足して返すこと (for 文を使う)",
    "K3": "calc/fmt.py に show_sum(a, b) を加えよ。fmt_num(add(a, b)) を返すこと (add は calc.ops にある)",
    "K4": "calc/ops.py に square(x) と、square を使う cube(x) を加えよ (cube(x) は x の 3 乗)",
    "K5": "calc/fmt.py に fmt_all(xs) を加えよ。内包表記で xs の各要素に fmt_num を適用したリストを返すこと",
}


def S(depth: int, line: str) -> Stmt:
    """A statement from its tokens written with single spaces (a STRING token must hold none)."""
    return (depth, line.split(" "))


IMPORT_ADD = S(0, "from calc . ops import add")
DEF_SQUARE = [S(0, "def square ( x ) :"), S(1, "return mul ( x , x )")]
DEF_CUBE = [S(0, "def cube ( x ) :"), S(1, "return mul ( x , square ( x ) )")]
DEF_SHOW_SUM = [S(0, "def show_sum ( a , b ) :"), S(1, "return fmt_num ( add ( a , b ) )")]

K_SCRIPTS: Dict[str, Dict[str, List[Stmt]]] = {
    "K1": {"reference": [S(0, "def double ( x ) :"), S(1, "return mul ( x , 2 )")]},
    "K2": {"reference": [S(0, "def total ( xs ) :"), S(1, "out = 0"), S(1, "for x in xs :"), S(2, "out = add ( out , x )"), S(1, "return out")]},
    # the careless first try forgets the import; "repaired" is the import first, then the function
    "K3": {"naive": list(DEF_SHOW_SUM), "reference": [IMPORT_ADD] + DEF_SHOW_SUM,
           "wrong_arity": [IMPORT_ADD, S(0, "def show_sum ( a , b ) :"), S(1, "return fmt_num ( add ( a ) )")]},
    # the careless first try writes cube before square (a forward reference); the repaired thread has square first
    "K4": {"naive": DEF_CUBE + DEF_SQUARE, "reference": DEF_SQUARE + DEF_CUBE},
    "K5": {"reference": [S(0, "def fmt_all ( xs ) :"), S(1, "return [ fmt_num ( x ) for x in xs ]")]},
}


def add_token(w: ScriptedWeaver, text: str, cache: Dict[str, bool]) -> str:
    """One unit for one token occurrence: a record when the fixture has the token, else a constructed unit.  One lookup per distinct token."""
    if text not in cache:
        r = w.call("lookup", text=text, tier="CODE")
        cache[text] = bool(r.get("ok") and r.get("matches"))
    if cache[text]:
        r = w.call("add", text=text, kind="record", tier="CODE")
    else:
        r = w.call("add", text=text, kind="constructed")
    if not r.get("ok"):
        raise RuntimeError("scripted code weaver: add %r refused: %s" % (text, r))
    return r["uid"]


def weave_statements(w: ScriptedWeaver, stmts: Sequence[Stmt], cache: Optional[Dict[str, bool]] = None) -> List[str]:
    """One cross per statement (not yet linked); returns the cids in order."""
    cache = {} if cache is None else cache
    cids: List[str] = []
    for depth, toks in stmts:
        rest = toks[1:]
        if len(rest) > MAX_ARM * len(geo.AXES):
            raise ValueError("a statement of more than %d tokens does not fit a cross" % (1 + MAX_ARM * len(geo.AXES)))
        uids = [add_token(w, t, cache) for t in toks]
        L = max(1, min(MAX_ARM, len(rest)))
        cid = w.call("open_cross", tier="CODE", L=L, depth=depth)["cid"]
        w.call("seat", cid=cid, seat="centre", uid=uids[0])
        for ai, arm in enumerate(geo.AXES):
            chunk = uids[1 + ai * MAX_ARM: 1 + (ai + 1) * MAX_ARM]
            if chunk:
                r = w.call("seat_run", cid=cid, arm=arm, uids=chunk)
                if not r.get("ok"):
                    raise RuntimeError("scripted code weaver: seat_run refused: %s" % r)
        cids.append(cid)
    return cids


def link_all(w: ScriptedWeaver, cids: Sequence[str]) -> None:
    for cid in cids:
        w.call("link", cid=cid)


def weave_k(w: ScriptedWeaver, k: str, variant: str = "reference") -> dict:
    """K1..K5, in the variant named.  Returns the last result.  `begin` is the caller's (like weave_tokyo's: it is row 0).

    reference    the solution; K3 and K4 reach it through the careless first try below (one refused emit, then the repair):
                 K3 forgets `from calc.ops import add` -> `undefined_name`; the repair adds the import cross at the head of the thread.
                 K4 writes cube before square -> `undefined_name`; the repair unlinks the two cube crosses and links them again at the end.
    naive        K3 / K4 only: the careless first try, and when emit is refused the weaver abstains (`cannot_weave`): no output.
    wrong_arity  K3 only: a call with the wrong number of arguments; every static gate passes, the tests do not.
    """
    cache: Dict[str, bool] = {}
    if variant == "wrong_arity" or k in ("K1", "K2", "K5"):
        cids = weave_statements(w, K_SCRIPTS[k]["wrong_arity" if variant == "wrong_arity" else "reference"], cache)
        link_all(w, cids)
        return w.call("emit")
    first = weave_statements(w, K_SCRIPTS[k]["naive"], cache)
    link_all(w, first)
    r = w.call("emit")
    if r.get("ok"):
        return r
    if variant == "naive":
        w.call("abstain", type="cannot_weave")
        return r
    if k == "K3":
        imp = weave_statements(w, [IMPORT_ADD], cache)[0]
        w.call("link", cid=imp, pos=0)
    else:                                                  # K4: cube's two crosses go after square's two
        for cid in first[:2]:
            w.call("unlink", cid=cid)
        for cid in first[:2]:
            w.call("link", cid=cid)
    return w.call("emit")
