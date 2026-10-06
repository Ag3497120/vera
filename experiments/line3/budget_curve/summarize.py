"""Summarise results/*.jsonl: the budget-capacity curve (markdown on stdout).

Table 1: every level on its full 240 seeds (max: on the subset that was run).
Table 2: PAIRED, every level restricted to the seeds the max run used (like for like).
Table 3: what the budget stops on at each level, and the group that broke (paired subset).
Table 4: growth trajectories at max (capacity after each added group).
"""
import json, os, statistics as st
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
LV = ["low", "mid-low", "mid", "high", "max"]
TI = ["RUN", "WORD", "CHAR"]

def load(t, l):
    for name in ("%s_%s.jsonl" % (t, l),):
        p = os.path.join(D, name)
        if os.path.exists(p):
            break
    else:
        cand = [f for f in os.listdir(D) if f.startswith("%s_%s_n" % (t, l))]
        if not cand: return None, None
        p = os.path.join(D, sorted(cand)[0])
    rs = [json.loads(x) for x in open(p, encoding="utf-8")]
    return [r for r in rs if "seed" in r], next((r for r in rs if r.get("summary")), None)

def row(t, l, rs, sm):
    c = [r["capacity"] for r in rs]; cs = [r["class_size"] for r in rs]
    ex = sum(r["stop"] == "exhausted" for r in rs)
    rn = {k: sum(r["reason"] == k for r in rs) for k in ("max_moves", "max_states", "max_class")}
    wall = "%.1f" % sum(r["secs"] for r in rs)
    return "| %s | %s | %d | %d / %g / %.2f / %d | %d | %d (%d/%d/%d) | %g / %.2f / %d | %s |" % (
        t, l, len(rs), min(c), st.median(c), st.mean(c), max(c), ex, len(rs) - ex,
        rn["max_moves"], rn["max_states"], rn["max_class"], st.median(cs), st.mean(cs), max(cs), wall)

H = ("| tier | level | seeds | cap min/med/mean/max | exhausted | budget (moves/states/class) "
     "| class size med/mean/max | wall s (sum of seeds) |\n|---|---|---|---|---|---|---|---|")
data = {(t, l): load(t, l) for t in TI for l in LV}
print("### Table 1: each level on its own seeds\n"); print(H)
for t in TI:
    for l in LV:
        rs, sm = data[(t, l)]
        if rs: print(row(t, l, rs, sm))
print("\n### Table 2: paired (all levels on the seeds the max run used)\n"); print(H)
paired = {}
for t in TI:
    mx = data[(t, "max")][0]
    if not mx: continue
    S = {r["seed"] for r in mx}
    for l in LV:
        rs = [r for r in (data[(t, l)][0] or []) if r["seed"] in S]
        paired[(t, l)] = {r["seed"]: r for r in rs}
        if len(rs) == len(S): print(row(t, l, rs, None))
print("\n### Table 3: paired, who is stopped by what, and how much of the ceiling is reached\n")
print("| tier | level | mean cap / mean ceiling (candidates+1) | seeds whose cap rose vs previous level | "
      "budget-stopped: breaking group size med / max | breaking group has >=2 units |")
print("|---|---|---|---|---|---|")
for t in TI:
    prev = None
    for l in LV:
        pr = paired.get((t, l))
        if not pr or len(pr) != len(paired.get((t, "max"), {})): continue
        rs = list(pr.values())
        cap = st.mean(r["capacity"] for r in rs); ceil = st.mean(r["candidates"] + 1 for r in rs)
        rose = "-" if prev is None else "%d / %d" % (sum(pr[s]["capacity"] > prev[s]["capacity"] for s in pr), len(pr))
        bg = [next(x for x in r["steps"] if x[3] == "budget")[1] for r in rs if r["stop"] == "budget"]
        bgs = "-" if not bg else "%g / %d" % (st.median(bg), max(bg))
        multi = "-" if not bg else "%d / %d" % (sum(b >= 2 for b in bg), len(bg))
        print("| %s | %s | %.2f / %.2f | %s | %s | %s |" % (t, l, cap, ceil, rose, bgs, multi))
        prev = pr
print("\n### Table 4: growth trajectory at max (capacity after each added group; first 20 seeds, even spacing)\n")
for t in TI:
    rs = data[(t, "max")][0]
    if not rs: continue
    pick = [rs[(i * len(rs)) // 20] for i in range(20)] if len(rs) > 20 else rs
    print("**%s** (seed: capacity after each group ... | stop | candidates)\n" % t)
    for r in pick:
        tr = [1] + [x[2] for x in r["steps"] if x[2] is not None]
        print("- %s: %s | %s%s | cand %d" % (r["seed"], " > ".join(map(str, tr)), r["stop"],
              "" if not r["reason"] else "(%s)" % r["reason"], r["candidates"]))
    print()
