#!/usr/bin/env python3
"""G4-d2: gate G-2, the PER-QUESTION criterion L-G4-32 (docs/LINE3_G4_GROWTH_METER.md 9 ticket 7, 7.4), from the saved stack snapshots
(`gate2_build.py build`, arm A, no rebuild, nothing is run through the reader).

For each of the 69 intra2 questions, at its entry step e(q) and at step 300, per tier (RUN / WORD / CHAR):

  (a) 未着      no unit of the tier's space at that step spells a gold alternative (T9 scorer rule: a normalised gold alternative is a substring of the
                normalised text of ONE unit; `hits_words`).  The units of the space = the keys of `state.crosses[tier]` (stack.as_placements asserts it).
  (b) question units   the question cut like `cycle.ask_tier` does with the grammar off and the default filter on (`split_question(tier)` minus
                `default_filter(tier)`), deduplicated; those present in the space.
  (c) per question unit  its own cross (every unit is a seed): open / closed, opened_at, closed_at, closed at birth (closed_at == opened_at),
                size (units seated), whether a gold unit is SEATED in it, and how a gold unit stands to it in the ledger of the cross
                (`cooccur`: seated | left_in_step | left_after | none; the cross records every unit that shares a sentence with its seed).
  (d) whether the cross of a gold unit holds a question unit.
  (e) verdict:   未着 | reachable | closed-before-co-occurrence | other (sub-tag).

The "holding" relation is the one `cycle.plan_read` uses (V1): a cross holds a unit if it is its seed or a seated unit (`placement_units`).
reachable = a gold unit is seated in some cross that holds a question unit (its own cross included: a gold unit is seated in its own cross).
closed-before = not reachable, the question has at least one question unit in the space, and EVERY question-unit cross is closed at a step
strictly before the gold's article entered (e(q): the max step of the evidence articles, which equals e(q) for all 69).  A cross closed AT e(q)
is tagged `other:closed_at_entry`, a question with an open question-unit cross `other:open_no_cooccurrence`, none present `other:no_question_unit`.

  PYTHONPATH=<worktree> PYTHONHASHSEED=0 python experiments/line3/g4/gate2_question.py run [--cache DIR] [--selfcheck]

Never opens vera-impl/hidden.  No network.  One process.  Writes results/gate2_question.md and results/gate2_question.jsonl (no seconds, no clock).
"""
import argparse
import collections
import csv
import gzip
import hashlib
import importlib.util
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from verantyx.line3 import cycle as cy                 # noqa: E402
from verantyx.line3 import foundation as fd            # noqa: E402
from verantyx.line3 import space as sp                 # noqa: E402
from verantyx.line3 import stack as st                 # noqa: E402
from verantyx.line3.funcwords import default_filter    # noqa: E402

RESULTS = os.path.join(HERE, "results")
CACHE_A = "/Users/motonisihikoudai/Projects/vera-impl/cache/g4_stack_A"
CFG = "found-a2083d453637__mid__forward"
BANK = os.path.join(ROOT, "experiments", "line3", "bank2", "bank2.tsv")
STEPS = os.path.join(HERE, "steps.json")
TIERS = sp.TIERS
FOUNDATION, LEVEL, ORDER = "on", "mid", "forward"
FINAL = 300
COOC_RANK = {"seated": 0, "left_in_step": 1, "left_after": 2, "none": 3}
VERDICTS = ("reachable", "closed-before", "未着", "other")


def load_scorer():
    spec = importlib.util.spec_from_file_location("t9_scorer", os.path.join(ROOT, "experiments", "line3", "t9", "scorer.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


SC = load_scorer()


# ------------------------------------------------------------------------------------------------------------------------------
# the snapshots: a light loader that verifies every identity (state_sha256 recomputed from the raw canonical bytes) but keeps only what
# the criterion needs of a cross (the members are parsed away)
# ------------------------------------------------------------------------------------------------------------------------------
class Cross:
    __slots__ = ("seed", "opened_at", "closed_at", "closed_reason", "seated", "left", "units")

    def __init__(self, o):
        self.seed = o["seed"]
        self.opened_at = o["opened_at"]
        self.closed_at = o["closed_at"]
        self.closed_reason = o["closed_reason"]
        self.seated = [(u, s) for u, s in o["seated"]]
        self.left = [(s, u, r) for s, u, r in o["left"]]
        self.units = frozenset(u for u, _ in self.seated)

    @property
    def closed(self):
        return self.closed_at is not None

    @property
    def at_birth(self):
        return self.closed_at is not None and self.closed_at == self.opened_at


def load_light(root, step, entries, parse_members=False):
    """{tier: {seed: Cross}} of the snapshot of `step`, identities verified like stack.load does (state sha recomputed, docs sha, ledger not read)."""
    d = os.path.join(root, CFG)
    hit = [e for e in entries if e["step"] == step and set(e["tiers"]) >= set(TIERS)]
    if not hit:
        raise SystemExit("no snapshot for step %d" % step)
    e = hit[-1]
    p = e["prefix_sha256"]
    p12 = p[:12]
    raw = open(os.path.join(d, "docs_%s.jsonl" % p12), "rb").read()
    if hashlib.sha256(raw).hexdigest() != p:
        raise SystemExit("docs file of step %d does not hash to its key" % step)
    cfg = types.SimpleNamespace(foundation=FOUNDATION, level=LEVEL, order=ORDER)
    out, members = {}, {}
    for t in TIERS:
        h = hashlib.sha256()
        h.update(st._cj(st._header(cfg, t, step, p)).encode("utf-8"))
        h.update(b"\n")
        crosses, mem, prev = {}, {}, None
        with gzip.open(os.path.join(d, "%s_state_%s.jsonl.gz" % (t, p12)), "rb") as f:
            head = json.loads(f.readline())
            for line in f:
                line = line.rstrip(b"\n")
                o = json.loads(line)
                if prev is not None and not prev < o["seed"]:
                    raise SystemExit("%s step %d: the seeds are not sorted" % (t, step))
                prev = o["seed"]
                h.update(o["seed"].encode("utf-8"))
                h.update(b"\x00")
                h.update(line)
                h.update(b"\n")
                crosses[o["seed"]] = Cross(o)
                if parse_members:
                    mem[o["seed"]] = o["members"]
        if h.hexdigest() != head["state_sha256"] or e["tiers"][t]["state_sha256"] != head["state_sha256"] or head["n"] != len(crosses):
            raise SystemExit("%s step %d: the recomputed state identity does not match" % (t, step))
        out[t] = crosses
        members[t] = mem
    return (out, members) if parse_members else out


def selfcheck(root, entries, step):
    """The seated units of a cross are the data units of its members (what placement_units sees through `from_cross`), at one step, every cross."""
    crosses, members = load_light(root, step, entries, parse_members=True)
    n = bad = 0
    for t in TIERS:
        for s, c in crosses[t].items():
            ms = [tuple(m) for m in members[t][s]]
            n += 1
            sets = [frozenset(st._data_units(m)) for m in ms]
            if len(set(sets)) != 1 or sets[0] != c.units or len(c.seated) != len(c.units):
                bad += 1
    return {"step": step, "crosses": n, "mismatch": bad}


# ------------------------------------------------------------------------------------------------------------------------------
# the questions
# ------------------------------------------------------------------------------------------------------------------------------
def load_questions():
    steps = json.load(open(STEPS, encoding="utf-8"))
    t2i = {a["title"]: a["index"] for a in steps["articles"]}
    with open(BANK, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE))
    head = rows[0]
    assert head[0] == "#id", head
    qs = []
    for r in rows[1:]:
        if r[1] != "intra2":
            continue
        ev = [x for x in r[6].split("|") if x]
        ev_titles = [x.rsplit("#", 1)[0] for x in ev]
        ev_steps = [t2i[x] for x in ev_titles]
        e = steps["entry_steps"][r[0]]
        if max(ev_steps) != e:
            raise SystemExit("%s: the evidence steps %s do not end at the entry step %d" % (r[0], ev_steps, e))
        qs.append({"id": r[0], "subject": r[3], "question": r[4], "gold": r[5], "evidence": r[6], "audit": r[7], "e": e})
    if len(qs) != steps["question_counts"]["intra2"]:
        raise SystemExit("expected %d intra2 questions, found %d" % (steps["question_counts"]["intra2"], len(qs)))
    return qs, steps


FULLLEAD = os.path.join(ROOT, "experiments", "line3", "bank2", "data", "fulllead_sents.jsonl")


class EvidenceSpace:
    """The tier spaces of the whole 300-article corpus, only to read the units of the EVIDENCE sentence of a question (diagnostic).  The units of a
    sentence do not depend on the prefix (checked: the units of the step-k snapshot equal the units of the first k articles' sentences in this space)."""

    def __init__(self):
        with open(FULLLEAD, encoding="utf-8") as f:
            rows = [json.loads(l) for l in f if l.strip()]
        self.sid = {r["source"]: i for i, r in enumerate(rows)}
        self.space = sp.build_space(rows)

    def units(self, tier, evidence):
        """(units of the evidence sentence(s) in order, their concatenation)"""
        us = []
        for ev in [x for x in evidence.split("|") if x]:
            us += list(self.space.tiers[tier].sentence_units[self.sid[ev]])
        return us


def cut_question(tier, question):
    """The question as ask_tier cuts it with the grammar off (split_question, then the default function-word filter), deduplicated in order."""
    q = cy.split_question(tier, question)
    flt = default_filter(tier)
    if flt is not None:
        q = tuple(u for u in q if not flt(u))
    return list(dict.fromkeys(q))


# ------------------------------------------------------------------------------------------------------------------------------
# one (question, step, tier)
# ------------------------------------------------------------------------------------------------------------------------------
class TierView:
    """A tier of one snapshot: its crosses, the normalised text of every unit (cached) and the holder index (unit -> the seeds that hold it)."""

    def __init__(self, crosses):
        self.crosses = crosses
        self._norm = {}
        self.holders = collections.defaultdict(list)
        for s in sorted(crosses):
            for u in crosses[s].units:
                self.holders[u].append(s)

    def norm(self, u):
        n = self._norm.get(u)
        if n is None:
            n = self._norm[u] = SC.norm(u)
        return n

    def gold_units(self, gold):
        gs = SC.golds(gold)
        hits = sorted(u for u in self.crosses if any(g in self.norm(u) for g in gs))
        exact = [u for u in hits if self.norm(u) in gs]
        return hits, exact

    def baseline(self):
        cs = self.crosses.values()
        n = len(self.crosses)
        closed = sum(1 for c in cs if c.closed)
        birth = sum(1 for c in cs if c.at_birth)
        return {"crosses": n, "closed": closed, "closed_at_birth": birth}


def cooccur_of(x, gold_set):
    """How the gold units stand to the cross x in x's own ledger: the best category over the gold units and the step it happened at."""
    best, best_step, best_unit = "none", None, None

    def take(cat, step, u):
        nonlocal best, best_step, best_unit
        if COOC_RANK[cat] < COOC_RANK[best] or (cat == best and step is not None and (best_step is None or step < best_step)):
            best, best_step, best_unit = cat, step, u

    for u, s in x.seated:
        if u in gold_set:
            take("seated", s, u)
    for s, u, r in x.left:
        if u in gold_set:
            take("left_after" if r == st.LEFT_AFTER else "left_in_step", s, u)
    return best, best_step, best_unit


def judge(view, qrow, step, tier, evsp):
    e = qrow["e"]
    cr = view.crosses
    qcut = cut_question(tier, qrow["question"])
    qp = [u for u in qcut if u in cr]
    gold_units, gold_exact = view.gold_units(qrow["gold"])
    gset = set(gold_units)
    ev_units = evsp.units(tier, qrow["evidence"])
    ev_set = set(ev_units)
    ev_concat = any(g in SC.norm("".join(ev_units)) for g in SC.golds(qrow["gold"]))
    rec = {"id": qrow["id"], "step": step, "which": "entry" if step == e else "final", "tier": tier, "e": e, "gold": qrow["gold"],
           "q_cut": qcut, "q_present": qp, "q_missing": [u for u in qcut if u not in cr],
           "gold_units_n": len(gold_units), "gold_units": gold_units[:12], "gold_units_exact": gold_exact[:12], "gold_exact_n": len(gold_exact)}
    # (c) each question unit's own cross
    qx = []
    for q in qp:
        x = cr[q]
        cat, cstep, cunit = cooccur_of(x, gset) if gset else ("none", None, None)
        qx.append({"unit": q, "open": not x.closed, "opened_at": x.opened_at, "closed_at": x.closed_at, "closed_reason": x.closed_reason,
                   "at_birth": x.at_birth, "size": len(x.seated), "gold_seated": bool(gset & x.units),
                   "closed_before_entry": x.closed and x.closed_at < e, "cooccur": cat, "cooccur_step": cstep, "cooccur_unit": cunit})
    rec["qx"] = qx
    # the crosses that hold a question unit (V1), the gold units seated in them
    hx = sorted({s for q in qp for s in view.holders.get(q, ())})
    seated_in = {}
    for s in hx:
        g = sorted(gset & cr[s].units)
        if g:
            seated_in[s] = g
    own = [g for g in gold_units if set(qp) & cr[g].units]            # (d) the cross of a gold unit holds a question unit
    gold_ev = sorted(gset & ev_set)                   # the gold units that sit in the evidence sentence itself
    rec["gold_units_in_evidence"] = gold_ev[:12]
    rec["gold_spans_evidence_units"] = ev_concat      # the gold alternative is spelled by adjacent kept units of the evidence sentence (the tier cuts it)
    rec["reach_evidence_unit"] = any(set(gold_ev) & cr[s].units for s in hx)
    rec["holding_crosses"] = len(hx)
    rec["holding_closed"] = sum(1 for s in hx if cr[s].closed)
    rec["gold_seated_in_holding"] = {s: g[:6] for s, g in list(seated_in.items())[:8]}
    rec["gold_seated_in_holding_n"] = len(seated_in)
    rec["gold_cross_holds_q"] = own[:6]
    rec["gold_cross_holds_q_n"] = len(own)
    rec["gold_cross_info"] = [{"unit": g, "opened_at": cr[g].opened_at, "closed_at": cr[g].closed_at, "size": len(cr[g].seated),
                               "holds_q": bool(set(qp) & cr[g].units)} for g in gold_units[:6]]
    via = []
    if own:
        via.append("own_cross_holds_q")
    if any(s in set(qp) for s in seated_in):
        via.append("seated_in_q_cross")
    if any(s not in set(qp) and s not in set(gold_units) for s in seated_in):
        via.append("seated_in_other_holding_cross")
    rec["reach_via"] = via
    # (e) the verdict
    sub = None
    if not gold_units:
        verdict = "未着"
    elif seated_in:
        verdict = "reachable"
    elif not qp:
        verdict, sub = "other", "no_question_unit"
    elif all(x["closed_before_entry"] for x in qx):
        verdict = "closed-before"
    elif all(not x["open"] for x in qx):
        verdict, sub = "other", "closed_at_entry"
    else:
        verdict, sub = "other", "open_no_cooccurrence"
    rec["verdict"], rec["sub"] = verdict, sub
    if verdict == "closed-before":                    # does the gold ever share a sentence with the seed of a closed question-unit cross?
        best = min((x["cooccur"] for x in qx), key=lambda c: COOC_RANK[c])
        rec["cb_cooccur"] = best                      # left_after = a true "closed before the gold co-occurred"; none = the gold never shares a sentence with any question unit
    rec["q_n_open"] = sum(1 for x in qx if x["open"])
    rec["q_n_closed"] = sum(1 for x in qx if not x["open"])
    rec["q_n_birth"] = sum(1 for x in qx if x["at_birth"])
    return rec


# ------------------------------------------------------------------------------------------------------------------------------
# the report
# ------------------------------------------------------------------------------------------------------------------------------
def tag(rec):
    v = rec["verdict"]
    if v == "other":
        return "other:" + rec["sub"]
    return v


def pct(a, b):
    return "%.1f %%" % (100.0 * a / b) if b else "-"


def qx_text(rec):
    parts = []
    for x in rec["qx"]:
        if x["open"]:
            s = "open"
        else:
            s = "C@%d%s" % (x["closed_at"], "b" if x["at_birth"] else "")
        parts.append("%s:%s/%d%s" % (x["unit"], s, x["size"], "+G" if x["gold_seated"] else ""))
    return " ".join(parts) if parts else "-"


def write_md(path, qs, recs, base, selfchecks, meta):
    L = []
    by = collections.defaultdict(dict)
    for r in recs:
        by[(r["id"], r["which"])][r["tier"]] = r
    n = len(qs)
    L.append("# G4-d2: gate G-2, the per-question criterion L-G4-32 (arm A, saved snapshots, no rebuild)")
    L.append("")
    L.append("%d intra2 questions; foundation on, level mid, order forward; tiers RUN / WORD / CHAR; each at its entry step e(q) and at step %d." % (n, FINAL))
    L.append("Script: `experiments/line3/g4/gate2_question.py`.  Snapshots: `%s/%s` (every state identity recomputed from the raw bytes)." % (CACHE_A, CFG))
    L.append("")
    L.append("Verdicts: **reachable** = a gold unit (T9 scorer rule, a unit of the space) is seated in a cross that holds a question unit (seed or seat; the gold's own cross included).  "
             "**closed-before** = not reachable, and every cross of a question unit is closed at a step strictly before e(q).  **未着** = no unit of the space spells a gold alternative.  "
             "**other:closed_at_entry** = every question-unit cross is closed but one of them at e(q) or later (at the gold article's own step); "
             "**other:open_no_cooccurrence** = some question-unit cross is open and the gold is not in any holding cross; **other:no_question_unit** = no question unit is in the space.")
    L.append("")
    # summary
    L.append("## Summary per tier (verdict counts of %d questions)" % n)
    L.append("")
    for which, label in (("entry", "at e(q)"), ("final", "at step %d" % FINAL)):
        L.append("### %s" % label)
        L.append("")
        L.append("| tier | reachable | closed-before | 未着 | other | other:closed_at_entry | other:open_no_cooccurrence | other:no_question_unit | closed-before share | closed-before with true later co-occurrence (left_after) |")
        L.append("|---|---|---|---|---|---|---|---|---|---|")
        for t in TIERS:
            rs = [by[(q["id"], which)][t] for q in qs]
            c = collections.Counter(tag(r) for r in rs)
            other = sum(v for k, v in c.items() if k.startswith("other"))
            cb = [r for r in rs if r["verdict"] == "closed-before"]
            cbl = sum(1 for r in cb if r.get("cb_cooccur") == "left_after")
            L.append("| %s | %d | %d | %d | %d | %d | %d | %d | %s | %d of %d |" % (
                t, c["reachable"], c["closed-before"], c["未着"], other, c["other:closed_at_entry"], c["other:open_no_cooccurrence"],
                c["other:no_question_unit"], pct(c["closed-before"], n), cbl, len(cb)))
        L.append("")
    # stop condition
    L.append("## The stop condition (more than half of the questions closed-before)")
    L.append("")
    L.append("| tier | at e(q): closed-before | share | stop (> 50 %) | closed-before + closed_at_entry | share | at 300: closed-before | share | stop (> 50 %) | closed-before + closed_at_entry | share |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for t in TIERS:
        row = [t]
        for which in ("entry", "final"):
            k = sum(1 for q in qs if by[(q["id"], which)][t]["verdict"] == "closed-before")
            k2 = k + sum(1 for q in qs if tag(by[(q["id"], which)][t]) == "other:closed_at_entry")
            row += [str(k), pct(k, n), "YES" if 2 * k > n else "no", str(k2), pct(k2, n)]
        L.append("| " + " | ".join(row) + " |")
    L.append("")
    L.append("The share is of all %d questions; the two extra columns widen \"before\" to \"at or before the gold article's own step\" (every question-unit cross closed, the gold in no holding cross)." % n)
    L.append("")
    L.append("Across tiers (a question counts once): reachable in at least one tier / no tier reachable and every tier that has a gold unit is closed-before / the rest.")
    L.append("")
    L.append("| at | reachable in some tier | blocked (closed-before in every tier with a gold unit) | 未着 in every tier | other |")
    L.append("|---|---|---|---|---|")
    for which, label in (("entry", "e(q)"), ("final", str(FINAL))):
        a = b = c_ = o = 0
        for q in qs:
            vs = [by[(q["id"], which)][t]["verdict"] for t in TIERS]
            if "reachable" in vs:
                a += 1
            elif all(v == "未着" for v in vs):
                c_ += 1
            elif all(v in ("closed-before", "未着") for v in vs):
                b += 1
            else:
                o += 1
        L.append("| %s | %d | %d | %d | %d |" % (label, a, b, c_, o))
    L.append("")
    # closed at birth
    L.append("## Question-unit crosses closed AT BIRTH")
    L.append("")
    L.append("Distinct question-unit crosses (a unit asked by several questions counts once) against every cross of the tier at the same step.")
    L.append("")
    L.append("| tier | step | question-unit crosses | closed | closed at birth | share closed | share at birth | all crosses of the tier | closed | at birth |")
    L.append("|---|---|---|---|---|---|---|---|---|---|")
    for which, label in (("entry", "e(q)"), ("final", str(FINAL))):
        for t in TIERS:
            seen = {}
            for q in qs:
                r = by[(q["id"], which)][t]
                for x in r["qx"]:
                    seen[(r["step"], x["unit"])] = x
            k = len(seen)
            cl = sum(1 for x in seen.values() if not x["open"])
            bi = sum(1 for x in seen.values() if x["at_birth"])
            if which == "entry":
                L.append("| %s | e(q) | %d | %d | %d | %s | %s | - | - | - |" % (t, k, cl, bi, pct(cl, k), pct(bi, k)))
            else:
                b0 = base[(FINAL, t)]
                L.append("| %s | %d | %d | %d | %d | %s | %s | %d | %s | %s |" % (t, FINAL, k, cl, bi, pct(cl, k), pct(bi, k), b0["crosses"],
                                                                               pct(b0["closed"], b0["crosses"]), pct(b0["closed_at_birth"], b0["crosses"])))
    L.append("")
    L.append("Question-unit crosses at e(q), with multiplicity (one per question and unit): "
             + "; ".join("%s %d of %d at birth" % (t, sum(r["q_n_birth"] for q in qs for r in [by[(q['id'], 'entry')][t]]),
                                                    sum(len(r["qx"]) for q in qs for r in [by[(q['id'], 'entry')][t]])) for t in TIERS))
    L.append("")
    L.append("The baseline at e(q) (all crosses of the tier at that step) is in `gate2_A.md` per measured step; at step %d it is in the columns on the right." % FINAL)
    L.append("")
    # diagnostics
    L.append("## Diagnostics")
    L.append("")
    L.append("**未着 split.**  `spans` = the gold alternative is spelled by ADJACENT kept units of the evidence sentence in this tier (the tier cut the gold into several units, e.g. ハッシュ + 表, so no one unit spells it); "
             "`absent` = not even the concatenation of the kept units of the evidence sentence spells it (it holds a dropped function unit or a character the tier does not keep).")
    L.append("")
    L.append("| tier | 未着 | spans (cut into adjacent units) | absent |")
    L.append("|---|---|---|---|")
    for t in TIERS:
        rs = [by[(q["id"], "entry")][t] for q in qs if by[(q["id"], "entry")][t]["verdict"] == "未着"]
        sp_ = sum(1 for r in rs if r["gold_spans_evidence_units"])
        L.append("| %s | %d | %d | %d |" % (t, len(rs), sp_, len(rs) - sp_))
    L.append("")
    L.append("**reachable, by route and by the evidence sentence** (at e(q); the route is not exclusive).  `evidence unit` = a gold unit that sits in the evidence sentence itself is seated in a holding cross "
             "(otherwise the reach is through another occurrence of a gold-spelling unit).")
    L.append("")
    L.append("| tier | reachable | via the gold's own cross holding a question unit | gold seated in a question-unit cross | gold seated in another holding cross | reachable through an evidence-sentence gold unit | not through one |")
    L.append("|---|---|---|---|---|---|---|")
    for t in TIERS:
        rs = [by[(q["id"], "entry")][t] for q in qs if by[(q["id"], "entry")][t]["verdict"] == "reachable"]
        c = collections.Counter(v for r in rs for v in r["reach_via"])
        ev = sum(1 for r in rs if r["reach_evidence_unit"])
        L.append("| %s | %d | %d | %d | %d | %d | %d |" % (t, len(rs), c["own_cross_holds_q"], c["seated_in_q_cross"], c["seated_in_other_holding_cross"], ev, len(rs) - ev))
    L.append("")
    L.append("**What closure cost** (at e(q); questions that have a gold unit in the tier).  `gold left` = a question-unit cross closed and recorded a gold unit as left (the gold shares a sentence with its seed, but the cross was closed: `left_in_step` the same step, `left_after` later).  "
             "`still reachable` = such a question is nevertheless reachable (another holding cross seats the gold).  `no question-unit cross seats it` = reachable, yet no question-unit cross itself holds a gold unit.  "
             "`subject born at e(q)` = a question unit whose cross was opened at e(q) (the article's own words): its cross cannot have closed before e(q).")
    L.append("")
    L.append("| tier | questions with a gold unit | gold left in a closed question-unit cross | of which still reachable | reachable, no question-unit cross seats it | with a question-unit cross born at e(q) |")
    L.append("|---|---|---|---|---|---|")
    for t in TIERS:
        rs = [by[(q["id"], "entry")][t] for q in qs if by[(q["id"], "entry")][t]["gold_units_n"]]
        lf = [r for r in rs if any(x["cooccur"] in ("left_in_step", "left_after") for x in r["qx"])]
        lfr = sum(1 for r in lf if r["verdict"] == "reachable")
        nq = sum(1 for r in rs if r["verdict"] == "reachable" and not any(x["gold_seated"] for x in r["qx"]))
        born = sum(1 for r in rs if any(x["opened_at"] == r["e"] for x in r["qx"]))
        L.append("| %s | %d | %d | %d | %d | %d |" % (t, len(rs), len(lf), lfr, nq, born))
    L.append("")
    L.append("**The rows that are neither reachable nor 未着** (at e(q); the same at %d): the state of each question-unit cross and the best way a gold unit stands to any of them (`cooccur`: seated, left_in_step = recorded in the step the cross closed, left_after = recorded after it closed, none = never shares a sentence with the seed)." % FINAL)
    L.append("")
    L.append("| id | tier | verdict | gold units | question-unit crosses | best cooccur |")
    L.append("|---|---|---|---|---|---|")
    for q in qs:
        for t in TIERS:
            r = by[(q["id"], "entry")][t]
            if r["verdict"] in ("reachable", "未着"):
                continue
            best = min((x["cooccur"] for x in r["qx"]), key=lambda c: COOC_RANK[c]) if r["qx"] else "-"
            L.append("| %s | %s | %s | %s | %s | %s |" % (q["id"], t, tag(r), "/".join(r["gold_units"][:3]), qx_text(r), best))
    L.append("")
    # gold unit stats
    L.append("## Gold units in the space")
    L.append("")
    L.append("| tier | at | questions with a gold unit | with an exact gold unit (normalised text equals an alternative) | median gold units |")
    L.append("|---|---|---|---|---|")
    for which, label in (("entry", "e(q)"), ("final", str(FINAL))):
        for t in TIERS:
            rs = [by[(q["id"], which)][t] for q in qs]
            k = sum(1 for r in rs if r["gold_units_n"])
            ex = sum(1 for r in rs if r["gold_exact_n"])
            ns = sorted(r["gold_units_n"] for r in rs)
            L.append("| %s | %s | %d | %d | %d |" % (t, label, k, ex, ns[len(ns) // 2]))
    L.append("")
    # 69 rows
    L.append("## The %d questions" % n)
    L.append("")
    L.append("`R` reachable, `CB` closed-before, `U` 未着, `O:entry` other:closed_at_entry, `O:open` other:open_no_cooccurrence, `O:noQ` other:no_question_unit.  Columns `e` / `300`.")
    L.append("")
    L.append("| id | e(q) | gold | RUN e | RUN 300 | WORD e | WORD 300 | CHAR e | CHAR 300 |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    short = {"reachable": "R", "closed-before": "CB", "未着": "U", "other:closed_at_entry": "O:entry", "other:open_no_cooccurrence": "O:open",
             "other:no_question_unit": "O:noQ"}
    for q in qs:
        cells = []
        for t in TIERS:
            for which in ("entry", "final"):
                cells.append(short[tag(by[(q["id"], which)][t])])
        L.append("| %s | %d | %s | %s |" % (q["id"], q["e"], q["gold"].replace("|", "\\|"), " | ".join(cells)))
    L.append("")
    L.append("## Question-unit crosses at e(q) (RUN and WORD)")
    L.append("")
    L.append("`unit:state/size`: state `open`, `C@s` closed at step s, `C@sb` closed at s = its birth; `+G` a gold unit is seated in it.")
    L.append("")
    L.append("| id | gold units RUN / WORD | RUN question-unit crosses | WORD question-unit crosses |")
    L.append("|---|---|---|---|")
    for q in qs:
        r1, r2 = by[(q["id"], "entry")]["RUN"], by[(q["id"], "entry")]["WORD"]
        L.append("| %s | %d / %d | %s | %s |" % (q["id"], r1["gold_units_n"], r2["gold_units_n"], qx_text(r1), qx_text(r2)))
    L.append("")
    L.append("## Checks")
    L.append("")
    for s in selfchecks:
        L.append("- seated units == data units of the members, every cross, step %d: %d crosses, %d mismatches" % (s["step"], s["crosses"], s["mismatch"]))
    L.append("- every loaded snapshot (%d steps x 3 tiers) had its `state_sha256` recomputed from the raw canonical bytes and matched." % meta["loaded"])
    L.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run"])
    ap.add_argument("--cache", default=CACHE_A)
    ap.add_argument("--selfcheck", action="store_true")
    ap.add_argument("--out", default=RESULTS)
    a = ap.parse_args()
    qs, steps = load_questions()
    d = os.path.join(a.cache, CFG)
    entries = [json.loads(l) for l in open(os.path.join(d, "manifest.jsonl"), encoding="utf-8").read().splitlines()]
    evsp = EvidenceSpace()
    need = sorted({q["e"] for q in qs} | {FINAL})
    recs, base = [], {}
    selfchecks = []
    for step in need:
        crosses = load_light(a.cache, step, entries)
        views = {t: TierView(crosses[t]) for t in TIERS}
        for t in TIERS:
            base[(step, t)] = views[t].baseline()
        for q in qs:
            if q["e"] == step or step == FINAL:
                for t in TIERS:
                    if q["e"] == step:
                        recs.append(judge(views[t], q, step, t, evsp))
                    if step == FINAL and q["e"] != FINAL:
                        recs.append(judge(views[t], q, step, t, evsp))
        print("step %d done" % step, file=sys.stderr, flush=True)
    if a.selfcheck:
        for s in (55, 144):
            selfchecks.append(selfcheck(a.cache, entries, s))
            print("selfcheck", selfchecks[-1], file=sys.stderr, flush=True)
    # a question whose e == FINAL appears once as entry and must also appear as final: duplicate the record
    out = []
    for r in recs:
        out.append(r)
    for q in qs:
        if q["e"] == FINAL:
            for r in [x for x in recs if x["id"] == q["id"] and x["which"] == "entry"]:
                out.append(dict(r, which="final"))
    order = {t: i for i, t in enumerate(TIERS)}
    out.sort(key=lambda r: (r["id"], 0 if r["which"] == "entry" else 1, order[r["tier"]]))
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "gate2_question.jsonl"), "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    write_md(os.path.join(a.out, "gate2_question.md"), qs, out, base, selfchecks, {"loaded": len(need)})
    print("wrote %d records" % len(out), file=sys.stderr)


if __name__ == "__main__":
    main()
