"""Coarse type placement: ask for the rough type(s) of a content word (W3-a).

    python -m verantyx.coarse_place --term ホゲ [--context-role を]
        [--context-predicate 食べる] [--placement DIR]

or, from Python::

    from verantyx.coarse_place import query
    query("ホゲ", context_role="に", context_predicate="登る", placement=DIR)

The placement (a directory holding ``placement.sqlite`` and
``manifest.json``) is built by ``tools/build_coarse_placement.py`` from counted
evidence only -- no weights, no trained model, no external dictionary, no LLM.
If ``placement`` is omitted the environment variable ``VERA_COARSE_PLACEMENT``
is read; if neither is set the answer is ``NO_PLACEMENT`` (the home directory
and other places are never searched).

The answer
----------
``state``
    ``DECIDED``    exactly one type (``top`` has one id)
    ``MULTIPLE``   the evidence splits: several types, kept side by side
    ``UNPLACED``   the word occurs in the material but no evidence is strong
                   enough, and nothing nearby could be built on
    ``UNKNOWN``    the word is not in the material and nothing nearby gathers
                   ("do not know" -- not the same as "false" or "absent")
    ``NO_PLACEMENT`` there is no usable placement (``placement.reason`` says
                   why: UNSET, MISSING, UNREADABLE, MANIFEST_MISMATCH).  A
                   placement that exists but is empty answers ``UNKNOWN``
                   (zero hits is not the same as "no placement").

``origin``
    ``direct``     the word itself carries evidence (hand seed, spelling rule,
                   definition hypernym, alias, role distribution, ...)
    ``estimated``  a CONSTRUCTION, not a testimony.  ``constructed`` is True,
                   ``neighbors`` lists what it was built on and ``estimate_basis`` says
                   what kind of construction it is:
                   ``proximity``  from nearness (the word's shape: a placed right-hand
                                  word, units shared with placed words; and the role
                                  slot the caller passed)
                   ``generated``  from a definition sentence a MODEL wrote when asked
                                  (``axes["gen_definition"].provenance`` names the model,
                                  effort and batch).  It places only a word nothing else
                                  decided, never settles a tie, and is never passed on.
                   ``kana_variant``  from the OTHER kana spelling of the word (W5-b round 4):
                                  only when the asked spelling is ``UNPLACED`` / ``UNKNOWN``, its
                                  kana is of one script only, and the other spelling is a
                                  ``DECIDED`` and ``direct`` headword.  The type is the other
                                  spelling's, marked as an estimate (``spelling.why`` names it).
                   For ``direct`` answers ``estimate_basis`` is None.

``spelling`` (W5-b)
    The question is NFKC-normalized (full-width / half-width and compatibility forms are the
    same word) and every lookup uses that one spelling; ``term`` is the caller's string.
    Hiragana and katakana are DIFFERENT words (no reading normalization): ``state`` / ``top`` /
    ``candidates`` come from the evidence of the asked spelling alone.  ``spelling.kana_variant``
    shows what the headword row of the other kana spelling says and ``spelling.why`` is
    ``KANA_VARIANT_DIFFERS`` when that row is DECIDED / MULTIPLE and differs from the answer.
    The one exception (auditor ruling C1, W5-b round 4): an asked spelling that is ``UNPLACED`` or
    ``UNKNOWN`` and whose kana is of ONE script only (all hiragana or all katakana, other
    characters aside) takes the type of the other spelling when that headword is ``DECIDED`` and
    ``direct`` -- as an ESTIMATE (``origin`` ``estimated``, ``estimate_basis`` ``kana_variant``,
    ``constructed`` True, ``spelling.why`` ``ESTIMATED_FROM_KANA_VARIANT:<the other spelling>``),
    never as a direct answer.  A ``MULTIPLE`` or ``estimated`` variant is not borrowed, and an
    asked spelling that has an answer of its own (any ``DECIDED`` / ``MULTIPLE``) keeps it.

Evidence arms are never added to each other and sources (``jawiki`` and each
codex family) never pool their counts; a conclusion is an overlay of the arms
that met their thresholds (agree -> DECIDED, split -> MULTIPLE).  Types listed
together in ``top`` are an UNORDERED set (display order is alphabetical).
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

from . import coarse_types as ct

ENV_PLACEMENT = "VERA_COARSE_PLACEMENT"
NO_PLACEMENT_REASONS = ("UNSET", "MISSING", "UNREADABLE", "MANIFEST_MISMATCH")
EXIT_OK, EXIT_NO_PLACEMENT, EXIT_BAD_ARGS = 0, 2, 64

_CACHE: Dict[str, "_Placement"] = {}
#: the tables of a placement (a manifest may name only these)
_TABLES = frozenset(("headwords", "evidence", "unit_kin", "unit_sample", "atoms",
                     "ctx", "counters", "meta", "generated"))


def cuts_for(n: int) -> Tuple[Tuple[int, int], ...]:
    """(left, right) cut sizes for a word of n characters: the lattice's
    inventory (granularity.SPLITS for 2..5; every cut with both sides >= 2
    for the long window 6..12)."""
    from .granularity import SPLITS
    if n in SPLITS:
        return tuple(SPLITS[n])
    if 6 <= n <= 12:
        return tuple((a, n - a) for a in range(2, n - 1))
    return ()


class _Placement:
    """An opened placement (read-only)."""

    def __init__(self, path: str, con: sqlite3.Connection, manifest: dict):
        self.path = path
        self.con = con
        self.manifest = manifest
        self.sha = manifest.get("content_sha256")
        row = con.execute("SELECT v FROM meta WHERE k='config'").fetchone()
        cfg = dict(ct.DEFAULT_CONFIG)
        if row:
            try:
                cfg.update(json.loads(row[0]))
            except ValueError:
                pass
        self.cfg = cfg
        row = con.execute("SELECT v FROM meta WHERE k='ctx_global'").fetchone()
        self.ctx_global = json.loads(row[0]) if row else {}
        self.counters = frozenset(
            r[0] for r in con.execute("SELECT unit FROM counters"))
        self.ctx_srcs = [r[0] for r in con.execute(
            "SELECT DISTINCT src FROM ctx ORDER BY src")]
        self.n_headwords = con.execute("SELECT COUNT(*) FROM headwords").fetchone()[0]
        self.atoms = frozenset(r[0] for r in con.execute("SELECT ch FROM atoms"))
        # a placement built before the ``base`` column existed (round 1) still opens
        self.has_base = any(r[1] == "base" for r in con.execute("PRAGMA table_info(evidence)"))
        # likewise a placement made before the ``generated`` table existed (W3-a2)
        self.has_generated = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='generated'").fetchone() is not None

    # --- lookups ---------------------------------------------------------------
    def head(self, w: str):
        return self.con.execute(
            "SELECT ns, state, origin, top, kind, n_seen, by FROM headwords "
            "WHERE word=?", (w,)).fetchone()

    def attested(self, w: str) -> bool:
        if len(w) == 1:
            return w in self.atoms
        return self.con.execute("SELECT 1 FROM headwords WHERE word=?",
                                (w,)).fetchone() is not None

    def evidence(self, w: str):
        return self.con.execute(
            "SELECT arm, src, type, n, %s FROM evidence WHERE word=? "
            "ORDER BY arm, src, type" % ("base" if self.has_base else "NULL"), (w,)).fetchall()

    def generated(self, w: str):
        """(model, effort, batch_id, attempt, definition, hypernym, typed phrases) or None."""
        if not self.has_generated:
            return None
        r = self.con.execute(
            "SELECT model, effort, batch_id, attempt, definition, hypernym, phrases "
            "FROM generated WHERE word=?", (w,)).fetchone()
        if r is None:
            return None
        try:
            ph = json.loads(r[6])
        except ValueError:
            ph = []
        return (r[0], r[1], r[2], r[3], r[4], r[5], ph)

    def kin(self, unit: str, pos: str):
        return self.con.execute(
            "SELECT type, n FROM unit_kin WHERE unit=? AND pos=?",
            (unit, pos)).fetchall()

    def kin_sample(self, unit: str, pos: str) -> List[str]:
        r = self.con.execute("SELECT sample FROM unit_sample WHERE unit=? AND pos=?",
                             (unit, pos)).fetchone()
        return r[0].split("|") if r and r[0] else []

    def ctx(self, src: str, particle: str, pred: str):
        return self.con.execute(
            "SELECT type, n FROM ctx WHERE src=? AND particle=? AND pred=?",
            (src, particle, pred)).fetchall()


def _no_placement(term: str, reason: str, path: Optional[str],
                  role: Optional[str], pred: Optional[str]) -> Dict[str, Any]:
    return _result(term, None, "NO_PLACEMENT", None, False, [], [], {}, [],
                   None, role, pred,
                   {"path": path, "content_sha256": None, "reason": reason})


def _open(path: Optional[str]):
    """(placement, None) or (None, (reason, path))."""
    if path is None or str(path).strip() == "":
        path = os.environ.get(ENV_PLACEMENT)
    if path is None or str(path).strip() == "":
        return None, ("UNSET", None)
    path = os.path.abspath(os.path.expanduser(str(path)))
    mp = os.path.join(path, "manifest.json")
    dbp = os.path.join(path, "placement.sqlite")
    if not (os.path.isdir(path) and os.path.isfile(mp) and os.path.isfile(dbp)):
        return None, ("MISSING", path)
    try:
        key = "%s|%d|%d|%d|%d" % (path, os.stat(mp).st_mtime_ns, os.stat(mp).st_size,
                                  os.stat(dbp).st_mtime_ns, os.stat(dbp).st_size)
    except OSError:
        return None, ("MISSING", path)
    got = _CACHE.get(key)
    if got is not None:
        return got, None
    try:
        manifest = json.load(open(mp, encoding="utf-8"))
        con = sqlite3.connect("file:%s?mode=ro" % dbp, uri=True)
        tables = manifest["outputs"]["tables"]
        if not tables:
            raise KeyError("tables")
        for t, expected in tables.items():
            if t not in _TABLES:
                raise KeyError(t)
            actual = con.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]
            if expected != actual:       # every table, not only the large ones
                con.close()
                return None, ("MANIFEST_MISMATCH", path)
        pl = _Placement(path, con, manifest)
    except (sqlite3.Error, ValueError, KeyError, TypeError, OSError):
        return None, ("UNREADABLE", path)
    for k in [k for k in _CACHE if k.startswith(path + "|")]:
        try:
            _CACHE.pop(k).con.close()
        except Exception:
            pass
    _CACHE[key] = pl
    return pl, None


def _order(types) -> List[str]:
    """Display order: alphabetical (NOT a ranking)."""
    return sorted(set(types))


def _result(term, ns, state, origin, constructed, top, candidates, axes,
            neighbors, seen, role, pred, placement, extra=None, estimate_basis=None):
    out = {"term": term, "namespace": ns, "state": state, "origin": origin,
           "estimate_basis": estimate_basis,
           "constructed": bool(constructed), "top": list(top),
           "candidates": candidates, "axes": axes, "neighbors": neighbors,
           "seen_in_material": seen,
           "context": {"role": role, "predicate": pred},
           "placement": placement}
    if extra:
        out.update(extra)
    return out


def _pl_info(pl: _Placement) -> Dict[str, Any]:
    return {"path": pl.path, "content_sha256": pl.sha, "reason": None}


def _direct(pl: _Placement, term: str, row, role, pred) -> Dict[str, Any]:
    ns, state, origin, top, kind, n_seen, by = row
    tops = [t for t in top.split(",") if t]
    ev = pl.evidence(term)
    # the SAME decision function the builder used (coarse_types.decide_word):
    # an arm is "met" only when it took part in the decision
    dec = ct.decide_word([(a, s, t, n, b) for (a, s, t, n, b) in ev], pl.cfg)
    axes: Dict[str, Any] = {}
    gen_row = pl.generated(term) if any(a == ct.GEN_ARM for (a, _s, _t, _n, _b) in ev) else None
    for k, a in dec["arms"].items():
        cnts = a["counts"]
        mx = max(cnts.values())
        axes[k] = {"counts": dict(sorted(cnts.items())),
                   "top": sorted(t for t, c in cnts.items() if c == mx),
                   "met": a["met"], "threshold_met": a["threshold_met"],
                   "why": a["why"], "generated": a["src"].startswith("codex:")}
        if k == ct.GEN_ARM:
            # a sentence a model wrote: its origin stays on the answer
            if gen_row is not None:
                axes[k]["provenance"] = {"model": gen_row[0], "effort": gen_row[1],
                                         "batch_id": gen_row[2]}
            else:
                parts = a["src"].split(":")
                axes[k]["provenance"] = {"model": parts[1] if len(parts) > 1 else None,
                                         "effort": parts[2] if len(parts) > 2 else None,
                                         "batch_id": None}
    cands = []
    for t in tops:
        cands.append({"type": t, "axes": {k: a["counts"][t] for k, a in axes.items()
                                          if t in a["counts"]}})
    decided_by = [b for b in by.split("+") if b]
    gen = any(axes[k]["generated"] for k in decided_by if k in axes)
    extra = {"decided_by": decided_by, "generated": bool(gen),
             "generated_definition": ct.GEN_ARM in decided_by}
    nsv: Dict[str, Dict[str, int]] = {}
    for (a, s, t, n, b) in ev:
        if a in ct.NON_VOTE_ARMS:
            nsv.setdefault(s, {})[t] = n
    if nsv:
        extra["namespace_votes"] = {s: dict(sorted(v.items())) for s, v in sorted(nsv.items())}
    if dec.get("origin") == "estimated":
        # placed by a generated definition ALONE: a construction, marked as such
        ph = gen_row[6] if gen_row else []
        word = next((p for p, t in ph if t == tops[0]), None) or term
        batch = gen_row[2] if gen_row else None
        nbs = [{"word": word, "type": tops[0], "via": "generated:%s" % batch}]
        return _result(term, ns, state, "estimated", True, _order(tops), cands, axes, nbs,
                       True, role, pred, _pl_info(pl), extra, estimate_basis="generated")
    return _result(term, ns, state, "direct", False, _order(tops), cands, axes, [],
                   True, role, pred, _pl_info(pl), extra)


def _left_ok(pl: _Placement, left: str, memo, cfg) -> bool:
    if pl.attested(left):
        return True
    return bool(cfg.get("left_recursive", True)) and _cover(pl, left, memo)


def _cover(pl: _Placement, s: str, memo: Dict[str, bool]) -> bool:
    """True when ``s`` is a real word of the placement (or, for one character,
    an atom), or splits -- at the lattice's cut inventory, both parts at least two
    characters -- into two parts that are each covered in the same way.  A node is
    always a real word or an atom, never an invented fragment."""
    r = memo.get(s)
    if r is not None:
        return r
    ok = pl.attested(s)
    if not ok and len(s) >= 4:
        for a, b in cuts_for(len(s)):
            if a >= 2 and b >= 2 and _cover(pl, s[:a], memo) and _cover(pl, s[a:], memo):
                ok = True
                break
    memo[s] = ok
    return ok


def _estimate(pl: _Placement, term: str, row, role, pred) -> Dict[str, Any]:
    cfg = pl.cfg
    n = len(term)
    cuts = cuts_for(n)
    memo: Dict[str, bool] = {}
    stages: List[Dict[str, Any]] = []
    # ---- head: the longest right-hand word that is itself DECIDED
    best = None
    for a, b in cuts:
        left, right = term[:a], term[a:]
        if len(right) < cfg["head_min_chars"]:
            continue
        if n >= 6 and len(left) < 2:
            continue
        if cfg["left_attested"] and not _left_ok(pl, left, memo, cfg):
            continue
        r = pl.head(right)
        # only a word placed DIRECT lends its type: a placement built on a generated
        # sentence is never passed on to other words, neither an estimate (generated) nor a
        # word upgraded to "direct" by agreement (its ``by`` names ``gen_definition``)
        if r is None or r[1] != "DECIDED" or r[2] != "direct":
            continue
        if ct.GEN_ARM in (r[6] or "").split("+"):
            continue
        if best is None or len(right) > len(best[0]):
            best = (right, r[3], left)
    if best is not None:
        stages.append({"stage": "head", "types": [best[1]],
                       "axis": {"counts": {best[1]: 1}, "top": [best[1]],
                                "word": best[0], "left": best[2]},
                       "neighbors": [{"word": best[0], "type": best[1],
                                      "via": "head:%s@R" % best[0]}]})
    # ---- kin: the longest right unit whose family leans one way
    bestk = None
    for a, b in cuts:
        left, right = term[:a], term[a:]
        if len(right) < cfg["kin_min_unit_chars"]:
            continue
        if n >= 6 and len(left) < 2:
            continue
        if cfg["left_attested"] and not _left_ok(pl, left, memo, cfg):
            continue
        rows = pl.kin(right, "R")
        if not rows:
            continue
        tot = sum(c for _t, c in rows)
        mx = max(c for _t, c in rows)
        tops = [t for t, c in rows if c == mx]
        if (tot >= cfg["kin_min_count"] and len(tops) == 1
                and mx * 100 >= cfg["kin_min_share_pct"] * tot):
            if bestk is None or len(right) > len(bestk[0]):
                bestk = (right, tops[0], dict(rows), left)
    if bestk is not None:
        samp = pl.kin_sample(bestk[0], "R")
        stages.append({"stage": "kin", "types": [bestk[1]],
                       "axis": {"counts": dict(sorted(bestk[2].items())),
                                "top": [bestk[1]], "unit": bestk[0],
                                "left": bestk[3]},
                       "neighbors": [{"word": w, "type": bestk[1],
                                      "via": "kin:%s@R" % bestk[0]} for w in samp[:5]]
                       or [{"word": bestk[0], "type": bestk[1],
                            "via": "kin:%s@R" % bestk[0]}]})
    # ---- context: the role slot the caller passed
    if role:
        key_pred = pred or ""
        per_src: Dict[str, str] = {}
        ctx_counts: Dict[str, Dict[str, int]] = {}
        for src in pl.ctx_srcs:
            rows = pl.ctx(src, role, key_pred)
            if not rows:
                continue
            tot = sum(c for _t, c in rows)
            mx = max(c for _t, c in rows)
            tops = [t for t, c in rows if c == mx]
            ctx_counts[src] = dict(rows)
            g = pl.ctx_global.get(src, {})
            gtot = sum(g.values())
            if (tot >= cfg["est_ctx_min_total"] and len(tops) == 1
                    and mx * 100 >= cfg["est_ctx_min_share_pct"] * tot
                    and (not gtot or mx * gtot * 100 >=
                         cfg["est_ctx_min_lift_pct"] * g.get(tops[0], 0) * tot)):
                per_src[src] = tops[0]
        if (per_src and len(set(per_src.values())) == 1
                and len(per_src) >= cfg["est_ctx_min_sources"]):
            t = next(iter(per_src.values()))
            # counts stay per source: the slot's counts of different sources are
            # never added (a source's own numbers are shown, not their sum)
            stages.append({"stage": "context", "types": [t],
                           "axis": {"counts": {},
                                    "top": [t], "sources": sorted(per_src),
                                    "counts_by_source": {s: dict(sorted(ctx_counts[s].items()))
                                                         for s in sorted(per_src)},
                                    "generated": any(s.startswith("codex:") for s in per_src)},
                           "neighbors": [{"word": "%s/%s" % (role, key_pred or "-"),
                                          "type": t,
                                          "via": "context:" + ",".join(sorted(per_src))}]})
        elif per_src and len(set(per_src.values())) > 1:
            stages.append({"stage": "context_split", "types": [],
                           "axis": {"counts": {}, "top": [], "sources": sorted(per_src),
                                    "by_source": dict(sorted(per_src.items()))},
                           "neighbors": []})
    # ---- kin on the left: the term as a LEFT unit of placed words ("合衆" in
    # "合衆国"), only when the stages above found nothing -- a fragment the
    # tokeniser cut off a longer word.  A separate, lower tier (never mixed in).
    bestl = None
    if (not stages and cfg.get("kin_left", True)
            and len(term) >= cfg["kin_min_unit_chars"]):
        rows = pl.kin(term, "L")
        if rows:
            tot = sum(c for _t, c in rows)
            mx = max(c for _t, c in rows)
            tops = [t for t, c in rows if c == mx]
            if (tot >= cfg.get("kin_left_min_count", cfg["kin_min_count"]) and len(tops) == 1
                    and mx * 100 >= cfg.get("kin_left_min_share_pct", cfg["kin_min_share_pct"]) * tot):
                bestl = (tops[0], dict(rows))
    if bestl is not None:
        samp = pl.kin_sample(term, "L")
        stages.append({"stage": "kin_left", "types": [bestl[0]],
                       "axis": {"counts": dict(sorted(bestl[1].items())),
                                "top": [bestl[0]], "unit": term},
                       "neighbors": [{"word": w, "type": bestl[0],
                                      "via": "kin:%s@L" % term} for w in samp[:5]]
                       or [{"word": term, "type": bestl[0], "via": "kin:%s@L" % term}]})
    seen = row is not None
    fired = [s for s in stages if s["types"]]
    axes = {}
    for s in stages:
        axes["morphology:" + s["stage"] if s["stage"] in ("head", "kin", "kin_left")
              else "context"] = s["axis"]
    if not fired:
        state = "UNPLACED" if seen else "UNKNOWN"
        return _result(term, None, state, None, False, [], [], axes, [], seen,
                       role, pred, _pl_info(pl))
    types_by_stage = [(s["stage"], s["types"][0]) for s in fired]
    distinct = {t for _s, t in types_by_stage}
    neighbors = [nb for s in fired for nb in s["neighbors"]]
    if len(distinct) == 1:
        tops = [next(iter(distinct))]
    else:
        pol = cfg["conflict_policy"]
        if pol == "multiple":
            tops = sorted(distinct)
        elif pol == "prefer_stage":
            tops = [types_by_stage[0][1]]
        else:
            state = "UNPLACED" if seen else "UNKNOWN"
            return _result(term, None, state, None, False, [], [], axes, [], seen,
                           role, pred, _pl_info(pl),
                           {"conflict": sorted(types_by_stage)})
    ns = "P" if any(t.startswith("P_") for t in tops) else "N"
    cands = [{"type": t, "axes": {("morphology:" + s if s in ("head", "kin", "kin_left")
                                   else "context"): 1
                                  for s, tt in types_by_stage if tt == t}}
             for t in tops]
    state = "DECIDED" if len(tops) == 1 else "MULTIPLE"
    return _result(term, ns, state, "estimated", True, _order(tops), cands, axes,
                   neighbors, seen, role, pred, _pl_info(pl), estimate_basis="proximity")


def query(term: str, *, context_role: Optional[str] = None,
          context_predicate: Optional[str] = None,
          placement: Optional[str] = None) -> Dict[str, Any]:
    """The coarse type(s) of ``term`` (see the module docstring).

    ``context_role`` must be one of ``ct.ROLE_PARTICLES`` (or None); anything
    else raises ``ValueError`` (the CLI answers it with exit code 64)."""
    if not isinstance(term, str) or not term.strip():
        raise ValueError("EMPTY_TERM")
    if context_role is not None and context_role not in ct.ROLE_PARTICLES:
        raise ValueError("UNKNOWN_CONTEXT_ROLE:%s" % context_role)
    asked = term.strip()
    q = unicodedata.normalize("NFKC", asked).strip()
    if not q:
        raise ValueError("EMPTY_TERM")
    pl, why = _open(placement)
    if pl is None:
        out = _no_placement(q, why[0], why[1], context_role, context_predicate)
        out["term"] = asked
        out["spelling"] = _spelling(None, asked, q)
        return out
    out = _answer(pl, q, context_role, context_predicate)
    borrowed = _borrow_kana_variant(pl, q, out)
    if borrowed is not None:
        out = borrowed
    out["term"] = asked
    out["spelling"] = _spelling(pl, asked, q, out, borrowed_from=_kana_swapped(q) if borrowed is not None else None)
    return out


def _single_script_kana(s: str) -> bool:
    """True when the kana of ``s`` are of one script only: some hiragana and no katakana, or some katakana and no hiragana (other characters,
    the long-vowel mark included, are not looked at)."""
    hira = any(0x3041 <= ord(c) <= 0x3096 for c in s)
    kata = any(0x30A1 <= ord(c) <= 0x30F6 for c in s)
    return hira != kata


def _borrow_kana_variant(pl: _Placement, q: str, answer: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The answer for ``q`` rebuilt from the type of its other kana spelling, as an ESTIMATE, or None (auditor ruling C1, W5-b round 4).
    Only when the answer of the asked spelling is UNPLACED / UNKNOWN, the kana of ``q`` are of one script only, and the headword row of the
    other spelling is DECIDED and direct.  Nothing else is borrowed: a MULTIPLE or an estimated variant, a mixed-script spelling, an asked
    spelling that has an answer of its own."""
    if answer["state"] not in ("UNPLACED", "UNKNOWN") or not _single_script_kana(q):
        return None
    v = _kana_swapped(q)
    if v == q:
        return None
    row = pl.head(v)
    if row is None or row[1] != "DECIDED" or row[2] != "direct":
        return None
    tops = _order([t for t in row[3].split(",") if t])
    if len(tops) != 1:
        return None
    t = tops[0]
    axes = dict(answer["axes"])
    axes["kana_variant"] = {"term": v, "state": "DECIDED", "top": tops, "origin": "direct"}
    ctx = answer["context"]
    return _result(q, row[0], "DECIDED", "estimated", True, tops, [{"type": t, "axes": {"kana_variant": 1}}], axes,
                   [{"word": v, "type": t, "via": "kana_variant:" + v}], answer["seen_in_material"],
                   ctx["role"], ctx["predicate"], answer["placement"], estimate_basis="kana_variant")


def _kana_swapped(s: str) -> str:
    """``s`` with every hiragana written as the katakana of the same sound and every katakana as the hiragana (a fixed offset of 0x60 in
    the code table, ぁ-ゖ <-> ァ-ヶ).  Nothing else changes."""
    out = []
    for ch in s:
        o = ord(ch)
        if 0x3041 <= o <= 0x3096:
            out.append(chr(o + 0x60))
        elif 0x30A1 <= o <= 0x30F6:
            out.append(chr(o - 0x60))
        else:
            out.append(ch)
    return "".join(out)


def _spelling(pl: Optional[_Placement], asked: str, q: str,
              answer: Optional[Dict[str, Any]] = None, borrowed_from: Optional[str] = None) -> Dict[str, Any]:
    """How the question was spelled and what the OTHER kana spelling of it says (W5-b).  Information only: it never
    changes ``state`` / ``top`` / ``candidates`` of the answer (the answer is decided by the evidence of the asked
    spelling alone; the one exception, an estimate borrowed from the other spelling, is made by ``_borrow_kana_variant`` and named here by
    ``why``).  ``kana_variant`` reads the headword row of the other spelling and nothing else."""
    out: Dict[str, Any] = {"query": asked, "normalized": q, "normalization": "NFKC", "kana": "DISTINCT",
                           "kana_variant": None, "why": None}
    v = _kana_swapped(q)
    if pl is None or v == q:
        return out
    row = pl.head(v)
    if row is None:
        return out
    tops = _order([t for t in row[3].split(",") if t])
    out["kana_variant"] = {"term": v, "state": row[1], "top": tops, "origin": row[2]}
    if borrowed_from is not None:
        out["why"] = "ESTIMATED_FROM_KANA_VARIANT:" + borrowed_from
    elif (answer is not None and row[1] in ("DECIDED", "MULTIPLE")
            and (row[1], tops) != (answer["state"], answer["top"])):
        out["why"] = "KANA_VARIANT_DIFFERS"
    return out


def _answer(pl: _Placement, term: str, context_role: Optional[str],
            context_predicate: Optional[str]) -> Dict[str, Any]:
    """The answer for ``term`` (already NFKC-normalized): every lookup below uses this one spelling."""
    # 1. spelling
    nt = ct.notation_type(term, pl.counters)
    if nt is not None:
        t, rule = nt
        return _result(term, "N", "DECIDED", "direct", False, [t],
                       [{"type": t, "axes": {"notation": 1}}],
                       {"notation": {"counts": {t: 1}, "top": [t], "rule": rule,
                                     "met": True, "generated": False}},
                       [], None, context_role, context_predicate, _pl_info(pl),
                       {"decided_by": ["notation"], "generated": False})
    # 2. the word itself
    row = pl.head(term)
    if row is not None and row[1] in ("DECIDED", "MULTIPLE"):
        return _direct(pl, term, row, context_role, context_predicate)
    # 3. nearness (a construction)
    return _estimate(pl, term, row, context_role, context_predicate)


# --- command line -------------------------------------------------------------
class _Parser(argparse.ArgumentParser):
    def error(self, message):  # exit 64 with a JSON reason
        print(json.dumps({"state": "BAD_ARGUMENT", "reason": message},
                         ensure_ascii=False))
        sys.exit(EXIT_BAD_ARGS)


def main(argv: Optional[List[str]] = None) -> int:
    ap = _Parser(prog="python -m verantyx.coarse_place", description=__doc__.split("\n")[0])
    ap.add_argument("--term", required=True)
    ap.add_argument("--context-role", default=None)
    ap.add_argument("--context-predicate", default=None)
    ap.add_argument("--placement", default=None)
    args = ap.parse_args(argv)
    try:
        r = query(args.term, context_role=args.context_role,
                  context_predicate=args.context_predicate,
                  placement=args.placement)
    except ValueError as e:
        print(json.dumps({"state": "BAD_ARGUMENT", "reason": str(e),
                          "allowed_roles": list(ct.ROLE_PARTICLES)},
                         ensure_ascii=False))
        return EXIT_BAD_ARGS
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return EXIT_NO_PLACEMENT if r["state"] == "NO_PLACEMENT" else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
