"""G2 probe 2: does a before/after-the-centre criterion split the tied classes of the F1 ordered build?
Rebuild a sample of fulllead crosses (ordered, forward, mid), and for every member of the final class:
 - leg sign: + if every unit x of the leg has p(x,c) > p(c,x) (x first before the centre c in more sentences), - if every unit <, 0 otherwise
 - A1 key (one arm reads backwards, all else as now): max over legs L* of  sum_legs p_fwd - p_fwd(L*) + p_rev(L*)
   where p_fwd(leg) = sum over the leg's edges outer->inner of p(outer,inner) (centre edge: p(inner,c)), p_rev the reverse.
 - A2 key (+x forward, -x backward, the other 4 legs order-neutral): max over ordered leg pairs of p_fwd(+x) + p_rev(-x)
Counts: members, distinct sorted sign vectors, members surviving at the class max of A1 / A2 (modulo the 4 unlabelled legs)."""
import json, sys, time, statistics as st
import os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from verantyx.line3 import placement as pl
from verantyx.line3.space import build_space, load_jsonl
TIER, KIND, NS = sys.argv[1], sys.argv[2], int(sys.argv[3])
space = build_space(load_jsonl(ROOT + "/experiments/line3/bank2/data/fulllead_sents.jsonl"))
ts = space.tiers[TIER]; w = pl.Weights(ts); b = pl.budget_level("mid")
rows = [json.loads(l) for l in open(ROOT + "/experiments/line3/f1/raw/fulllead_sents_%s_ordered_mid.jsonl" % TIER, encoding="utf-8")][1:]
if KIND == "max_class": pool = [r for r in rows if r["broke_reason"] == "max_class"]
else: pool = [r for r in rows if r["stop"] == "exhausted" and r["class_size"] >= 2]
pick = pool[::max(1, len(pool) // NS)][:NS]
P = {}
def p(x, y):
    k = (x, y)
    if k not in P: P[k] = ts.p_pair(x, y) if (x in ts.postings and y in ts.postings) else 0
    return P[k]
out = []; t0 = time.time()
for r in pick:
    pc = pl.build_cross(ts, r["seed"], w, budget=b, group_insert="ordered", order="forward")
    L = pc.L; mem = pc.members
    signs = set(); a1 = []; a2 = []; mixed = 0; legs_tot = 0; plus = 0; minus = 0
    for f in mem:
        c = f[0]
        legs = [f[1 + a * L: 1 + (a + 1) * L] for a in range(6)]
        sv = []; fw = []; rv = []
        for leg in legs:
            cells = [x for x in leg if x is not None]
            if not cells: sv.append("e"); fw.append(0); rv.append(0); continue
            legs_tot += 1
            d = [p(x, c) - p(c, x) for x in cells]
            s = "+" if all(v > 0 for v in d) else "-" if all(v < 0 for v in d) else "0"
            if s == "0": mixed += 1
            elif s == "+": plus += 1
            else: minus += 1
            sv.append(s)
            chain = list(cells) + [c]          # outer -> inner -> centre
            fw.append(sum(p(chain[i], chain[i + 1]) for i in range(len(chain) - 1)))
            rv.append(sum(p(chain[i + 1], chain[i]) for i in range(len(chain) - 1)))
        signs.add(tuple(sorted(sv)))
        tot = sum(fw)
        a1.append(max(tot - fw[i] + rv[i] for i in range(6)))
        a2.append(max(fw[i] + rv[j] for i in range(6) for j in range(6) if i != j))
    m1 = max(a1); m2 = max(a2)
    out.append(dict(seed=r["seed"], size=pc.size, members=len(mem), sign_vectors=len(signs),
                    a1_survive=sum(1 for v in a1 if v == m1), a1_values=len(set(a1)),
                    a2_survive=sum(1 for v in a2 if v == m2), a2_values=len(set(a2)),
                    mixed_legs=mixed, plus_legs=plus, minus_legs=minus, legs=legs_tot, stop=pc.stop))
el = time.time() - t0
def med(k): return st.median(o[k] for o in out)
print(TIER, KIND, "crosses", len(out), "secs %.1f" % el)
print(" members median/max", med("members"), max(o["members"] for o in out))
print(" distinct sign vectors median/max", med("sign_vectors"), max(o["sign_vectors"] for o in out), "classes with >1:", sum(1 for o in out if o["sign_vectors"] > 1))
print(" A1 survivors median/max", med("a1_survive"), max(o["a1_survive"] for o in out), "share of members median %.3f" % st.median(o["a1_survive"] / o["members"] for o in out), "classes split (survivors<members):", sum(1 for o in out if o["a1_survive"] < o["members"]))
print(" A2 survivors median/max", med("a2_survive"), max(o["a2_survive"] for o in out), "share median %.3f" % st.median(o["a2_survive"] / o["members"] for o in out), "classes split:", sum(1 for o in out if o["a2_survive"] < o["members"]), "survivor==1:", sum(1 for o in out if o["a2_survive"] == 1))
print(" legs before(+)/after(-)/mixed(0):", sum(o["plus_legs"] for o in out), sum(o["minus_legs"] for o in out), sum(o["mixed_legs"] for o in out), "of", sum(o["legs"] for o in out))
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw", "ties_%s_%s.json" % (TIER, KIND)), "w"), ensure_ascii=False)
