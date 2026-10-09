"""G3-e review (2026-10-09): why the agreement loses the gold on the intra2 questions whose gold is a SEATED unit of a candidate window
(the reach of summarize.py, every candidate window, no cap).  usage: gold_loss.py CACHE OUT.txt [MAXM=40] [OUT.json]   (repository root)

For every (question, gold window, gold unit, axis of a seat of the gold: x / z; the centre is on both) slide_ratios.read_axes is run on
MEMBER 0 under both agreement rules and the instance gets ONE cause, first match wins:
  agree_on_gold                    the axis agrees on the gold
  z_gold_no_evidenced_edge         z axis, B_z(gold) = 0: no edge with n_z > 0 touches the gold (R2 / R3 cannot point to it)
  x_gold_no_evidenced_edge         the same on x
  z_one_evidenced_edge             z axis with exactly one evidenced edge, the gold on it (three: cannot agree; two_if: R2 / R3 elsewhere)
  R1=gold,flows_differ             the section walk points to the gold, R2 or R3 elsewhere
  section_disagreement_incl_gold   the working sections point to several units, the gold among them
  walk_passes_gold                 a walk on the gold's arm passes the gold and ends further in (centre, drop, unproven)
  walk_outer_seat_empty            every walk on the gold's arm is "empty": its OUTER seat (position 0) is empty
  walk_stops_before_gold           a walk on the gold's arm stops before reaching the gold
  gold_centre_no_walk_reaches      the gold is the centre and no walk reaches it
  other                            none of these (x with one evidenced edge under two_if: the walk is skipped)
A question's cause = the cause of its instance closest to agreeing (the order above, agree first); "cap first" = when no gold window is
read at fast (4 windows), the cap.  Flags count the questions with at least one instance of a kind.  Members beyond 0 (up to MAXM per
window) are read only for "does any arrangement agree on the gold".  Diagnostic only: nothing here is an answer rule."""
import os, sys, json, collections
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "experiments/line3/t9"))
import scorer as S                                            # noqa: E402
from verantyx.line3 import slide_query as Q, slide_ratios as SR   # noqa: E402
CACHE, OUT = sys.argv[1], sys.argv[2]
MAXM = int(sys.argv[3]) if len(sys.argv) > 3 else 40
LINES = []
_print = print
def print(*a):                                                # noqa: A001  (to the screen and OUT)
    LINES.append(" ".join(str(x) for x in a)); _print(*a)
wi = Q.WindowIndex.from_jsonl(os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl"), CACHE, build=False)
tsp = wi.space.tiers["RUN"]
rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv"), encoding="utf-8") if not l.startswith("#") and l.strip()]
rows = [r for r in rows if r[2] == "fulllead" and r[1] == "intra2"]
RANK = ["agree_on_gold", "R1=gold,flows_differ", "section_disagreement_incl_gold", "z_one_evidenced_edge",
        "walk_passes_gold", "walk_stops_before_gold", "walk_outer_seat_empty", "gold_centre_no_walk_reaches",
        "x_gold_no_evidenced_edge", "z_gold_no_evidenced_edge", "other"]
def fs(x): return None if x is None else "%d/%d" % (x.numerator, x.denominator)
def classify(rd, wc, g, rule):
    out = []
    seats = [s for s in wc.seats if s.unit == g]
    axes = sorted({ "x" if s.arm == "center" else SR.axis_of_arm(s.arm) for s in seats} | ({"x", "z"} if any(s.arm == "center" for s in seats) else set()))
    for a in axes:
        if a == "y": continue
        ar = rd.axis(a)
        info = dict(axis=a, status=ar.status, r1=ar.section_unit, r2=ar.edge_unit, r3=ar.binding_unit, evidenced=ar.evidenced_edges,
                    applicable=ar.section_applicable, F_g=fs(ar.edge_flow.get(g)), B_g=fs(ar.binding.get(g)),
                    F_r2=fs(ar.edge_flow.get(ar.edge_unit)) if ar.edge_unit else None, B_r3=fs(ar.binding.get(ar.binding_unit)) if ar.binding_unit else None,
                    seats=[(s.arm, s.position) for s in seats], L=wc.L)
        stops = []
        for sec in ar.sections:
            for w in sec.walks:
                if any(s.arm == w.arm for s in seats):
                    stops.append((w.arm, w.stop, [p[0] for p in w.path]))
        info["walk_detail"] = sorted({(a_, st, p[-1] if p else None, len(p)) for a_, st, p in stops})
        info["r2_is_gold"] = ar.edge_unit == g; info["r3_is_gold"] = ar.binding_unit == g
        info["walks_on_gold_arm"] = sorted({(a_, st) for a_, st, _ in stops})
        sec_units = [s.unit for s in ar.sections if s.unit is not None]
        info["section_units"] = sorted(set(sec_units))
        bg = ar.binding.get(g) or 0
        on_arm = [x for x in stops if x[0] != "center"]
        if ar.status == SR.AGREE and ar.unit == g:
            c = "agree_on_gold"
        elif a == "z" and bg == 0:
            c = "z_gold_no_evidenced_edge"
        elif bg == 0:
            c = "x_gold_no_evidenced_edge"
        elif a == "z" and ar.evidenced_edges == 1:
            c = "z_one_evidenced_edge"
        elif ar.section_unit == g:
            c = "R1=gold,flows_differ"
        elif g in sec_units:
            c = "section_disagreement_incl_gold"
        elif any(g in p for _, _, p in stops):
            c = "walk_passes_gold"
        elif stops and all(st == "empty" for _, st, _ in stops):
            c = "walk_outer_seat_empty"
        elif stops:
            c = "walk_stops_before_gold"
        elif all(s.arm == "center" for s in seats):
            c = "gold_centre_no_walk_reaches"
        else:
            c = "other"
        info["cause"] = c
        out.append(info)
    return out
res = {}
for rule in ("three", "two_if_single_edge"):
    qcause = collections.Counter(); inst = collections.Counter(); per_q = {}
    reach = reach_fast = 0
    for r in rows:
        qid, gold, question = r[0], r[5], r[4]
        it = Q.intake(wi, question)
        pa = Q.plan_windows(wi, it); pf = Q.plan_windows(wi, it, cap=4)
        gw = [n for n in pa.read if any(S.hits_words(gold, [u]) for u in wi.by_n[n].seated)]
        if not gw: continue
        reach += 1
        fast_read = [n for n in gw if n in pf.read]
        reach_fast += bool(fast_read)
        best = None; details = []
        any_member_agree = False
        for n in gw:
            w = wi.by_n[n]
            ev = SR.counts_evidence(wi.counts(w), "RUN")
            for m in range(min(w.class_size, MAXM)):
                wc = Q.member_cross(w, m)
                rd = SR.read_axes(wc, ev, tsp, it.ctx, wi.foundation, z_self_edges=True, agreement=rule)
                for g in sorted({u for u in wc.units() if S.hits_words(gold, [u])}):
                    for info in classify(rd, wc, g, rule):
                        if info["cause"] == "agree_on_gold": any_member_agree = True
                        if m == 0:
                            info.update(window=n, gold_unit=g, read_fast=n in pf.read, sids=list(w.window.sids))
                            details.append(info); inst[info["cause"]] += 1
                            if best is None or RANK.index(info["cause"]) < RANK.index(best): best = info["cause"]
        qcause[best] += 1
        per_q[qid] = dict(question=question, gold=gold, units=list(it.units), gold_windows=gw, gold_windows_read_fast=fast_read,
                          fast_read=list(pf.read), best=best, any_member_agree_upto=any_member_agree, details=details)
    res[rule] = per_q
    print("== rule", rule, "reach(no cap)", reach, "reach at fast (gold window read)", reach_fast)
    print(" question-level best cause (member 0):", dict(qcause.most_common()))
    print(" instance causes (window x gold unit x axis, member 0):", dict(inst.most_common()))
    print(" questions where some member (<=%d per window) agrees on gold:" % MAXM, sum(v["any_member_agree_upto"] for v in per_q.values()))
if len(sys.argv) > 4:
    json.dump(res, open(sys.argv[4], "w"), ensure_ascii=False, indent=1, default=str)
# ---- the cause table with the cap first (fast), and flags
for rule in ("three", "two_if_single_edge"):
    per_q = res[rule]
    prim = collections.Counter(); flags = collections.Counter(); prim_full = collections.Counter()
    for qid, v in per_q.items():
        ds = v["details"]
        read = [d for d in ds if d["read_fast"]]
        if not v["gold_windows_read_fast"]:
            p = "cap: no gold window read at fast"
        else:
            p = min((d["cause"] for d in read), key=RANK.index)
        prim[p] += 1
        prim_full[v["best"]] += 1
        fl = set()
        for d in ds:
            if d["cause"] == "walk_outer_seat_empty" or any(st == "empty" for _, st, _, _ in d["walk_detail"]): fl.add("gold arm walk is 'empty' (outer seat None)")
            if d["axis"] == "z" and d["evidenced"] == 1: fl.add("gold on z with ONE evidenced edge")
            if d["cause"] == "walk_passes_gold": fl.add("walk passes the gold, ends further in")
            if d["r2_is_gold"] or d["r3_is_gold"]: fl.add("R2 or R3 points to gold")
            if d["r2_is_gold"] and d["r3_is_gold"]: fl.add("R2 and R3 both point to gold")
            if d["status"] == "agree" and d["cause"] != "agree_on_gold": fl.add("axis agrees on another unit")
        for f in fl: flags[f] += 1
    print("== %s: primary cause, cap first (fast, member 0):" % rule, dict(prim.most_common()))
    print("   flags (questions with >=1 gold instance having it):", dict(flags.most_common()))

# ---- the best instance of every question at fast (three; the two_if cause beside it)
for qid, v in sorted(res["three"].items()):
    rd = [x for x in v["details"] if x["read_fast"]]
    if not rd:
        print("%s | gold %s | CAP: gold windows %s, read at fast %s" % (qid, v["gold"], v["gold_windows"], v["fast_read"]))
        continue
    b = min(rd, key=lambda x: RANK.index(x["cause"]))
    b2 = min([x for x in res["two_if_single_edge"][qid]["details"] if x["read_fast"]], key=lambda x: RANK.index(x["cause"]))
    print("%s | gold %s | w%d %s seat %s L%d axis %s | %s, evidenced %d | R1 %s R2 %s R3 %s | F(gold) %s vs F(R2) %s | B(gold) %s vs B(R3) %s | walks %s | %s / two_if %s" % (
        qid, b["gold_unit"], b["window"], b["sids"], b["seats"], b["L"], b["axis"], b["status"], b["evidenced"], b["r1"], b["r2"], b["r3"],
        b["F_g"], b["F_r2"], b["B_g"], b["B_r3"], [(a, st, t) for a, st, t, _ in b["walk_detail"]], b["cause"], b2["cause"]))

# ---- the structure behind the causes: arm shapes and z-edge evidence (member 0 of every window)
from verantyx.line3 import geometry as geo   # noqa: E402
sh = collections.Counter(); zev = collections.Counter()
for w in wi.windows:
    wc = Q.member_cross(w, 0); by = wc.by_seat(); ev = SR.counts_evidence(wi.counts(w), "RUN")
    for a in SR.ARM_NAMES:
        cells = [by.get(geo.Seat(a, k)) for k in range(wc.L)]
        sh["arm empty" if all(c is None for c in cells) else "seated, OUTER seat empty (walk 'empty')" if cells[0] is None
           else "seated from the outer seat"] += 1
    for o, i in geo.edges(wc.L):
        so, si = by.get(o), by.get(i)
        if SR.axis_of_arm(o.arm) == "z" and so is not None and si is not None:
            zev[("edge to the centre" if i == geo.CENTER else "outer edge") + (" n_z>0" if ev(o.arm, so.unit, si.unit)[0] > 0 else " n_z=0")] += 1
print("arms of the %d windows (6 arms each):" % len(wi.windows), dict(sh))
print("z edges with both ends seated:", dict(zev))

# ---- counterfactual (diagnostic, NOT a proposal): every walk starts at the arm's outermost SEATED cell instead of position 0
orig = SR._Reader.walk
def walk_from_first_seated(self, arm, q):
    cells = [self.by.get(geo.Seat(arm, k)) for k in range(self.wc.L)]
    k0 = next((k for k, c in enumerate(cells) if c is not None), None)
    if not k0:
        return orig(self, arm, q)
    path, steps, stop = [cells[k0]], [], "end"
    for nxt in cells[k0 + 1:] + [self.by.get(geo.CENTER)]:
        cur = path[-1]
        if nxt is None:
            stop = "gap"; break
        n, src = self.ev(arm, cur.unit, nxt.unit)
        if n <= 0:
            stop = "unproven"; break
        if self.E(nxt.unit, q) < self.E(cur.unit, q):
            stop = "drop"; break
        path.append(nxt); steps.append(SR.WalkStep(arm, cur.key, nxt.key, n, src))
    else:
        stop = "centre"
    return SR.AxisWalk(arm, tuple(p.key for p in path), path[-1].key, stop, tuple(steps))
SR._Reader.walk = walk_from_first_seated
for rule in ("three", "two_if_single_edge"):
    got = 0
    for qid, v in res[rule].items():
        it = Q.intake(wi, v["question"])
        hit = False
        for n in v["gold_windows"]:
            w = wi.by_n[n]
            rd = SR.read_axes(Q.member_cross(w, 0), SR.counts_evidence(wi.counts(w), "RUN"), tsp, it.ctx, wi.foundation,
                              z_self_edges=True, agreement=rule)
            hit = hit or any(S.hits_words(v["gold"], [a.unit]) for a in rd.answers)
        got += hit
    print("counterfactual walk from the first seated cell, %s, member 0, every candidate window: gold agreed in %d of %d" % (rule, got, len(res[rule])))
SR._Reader.walk = orig
open(OUT, "w", encoding="utf-8").write("\n".join(LINES) + "\n")
