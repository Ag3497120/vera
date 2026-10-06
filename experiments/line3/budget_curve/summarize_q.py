"""T4d vs T4c side by side (markdown on stdout).

For every tier/level: the seeds both runs have (T4c max ran on 48/48/20 seeds, T4d max also on 240),
capacity, exhausted/budget, class size (T4c = T4d expanded; T4d quotient), wall, and per-seed identity.
"""
import json, os, statistics as st
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
LV = ["low", "mid-low", "mid", "high", "max"]
TI = ["RUN", "WORD", "CHAR"]

def load(path):
    if not os.path.exists(path): return None
    rs = [json.loads(x) for x in open(path, encoding="utf-8")]
    return {r["seed"]: r for r in rs if "seed" in r}

def files(t, l, q):
    suf = "_q" if q else ""
    out = [os.path.join(D, "%s_%s%s.jsonl" % (t, l, suf))]
    out += [os.path.join(D, f) for f in sorted(os.listdir(D)) if f.startswith("%s_%s_n" % (t, l)) and f.endswith(suf + ".jsonl") and (f.endswith("_q.jsonl") == q)]
    return [f for f in out if os.path.exists(f)]

def fmt(rs, key="class_size"):
    c = [r["capacity"] for r in rs]; ex = sum(r["stop"] == "exhausted" for r in rs)
    cs = [r[key] for r in rs]
    return "%d / %g / %.2f / %d | %d / %d | %g / %.1f / %d | %.0f" % (
        min(c), st.median(c), st.mean(c), max(c), ex, len(rs) - ex,
        st.median(cs), st.mean(cs), max(cs), sum(r["secs"] for r in rs))

print("| tier | level | seeds | version | cap min/med/mean/max | exhausted / budget | class size med/mean/max | wall s |\n|---|---|---|---|---|---|---|---|")
notes = []
for t in TI:
    for l in LV:
        old_all = {}
        for f in files(t, l, False): old_all.update(load(f))
        new_runs = [(f, load(f)) for f in files(t, l, True)]
        for f, new in new_runs:
            seeds = [s for s in new if s in old_all]
            if not seeds: continue
            o = [old_all[s] for s in seeds]; n = [new[s] for s in seeds]
            diff = sum(1 for s in seeds if old_all[s]["capacity"] != new[s]["capacity"] or old_all[s]["stop"] != new[s]["stop"])
            tw = sum(1 for s in seeds if new[s].get("twins"))
            exp_same = sum(1 for s in seeds if new[s]["expanded_size"] == old_all[s]["class_size"])
            print("| %s | %s | %d | T4c | %s |" % (t, l, len(seeds), fmt(o)))
            print("| %s | %s | %d | T4d quotient | %s |" % (t, l, len(seeds), fmt(n)))
            print("| %s | %s | %d | T4d expanded | %s |" % (t, l, len(seeds), fmt(n, "expanded_size")))
            notes.append("%s %s (%d seeds): capacity/stop differs on %d, expanded==T4c class size on %d, seeds with twins %d" % (t, l, len(seeds), diff, exp_same, tw))
        # T4d only seeds (more seeds than T4c)
        for f, new in new_runs:
            extra = [s for s in new if s not in old_all]
            if extra:
                print("| %s | %s | %d | T4d only (no T4c) | %s |" % (t, l, len(new), fmt(list(new.values()), "expanded_size")))
print("\n" + "\n".join("- " + x for x in notes))
