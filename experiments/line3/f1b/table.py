"""F1b: table of the probe (probe_ordered.jsonl) next to the T9 numbers (t9/results/ask_fulllead_{fast,standard}.jsonl, whole placements, complete cache, 4 workers + other jobs).
T9 'off' = ms_layer0; T9 'on' = ms_layer0 + layers path ms (layer 0 reused as base, as here).  hit = Y if a candidate holds the gold (t9/scorer.py rule), else '-'; (n) = candidates flat/layers."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "experiments/line3/t9"))
import scorer as S
IDS = ["I2-014", "I2-029", "I2-011", "I2-031", "I2-001"]
t9 = {}
for p in ("fast", "standard"):
    for l in open(os.path.join(ROOT, "experiments/line3/t9/results/ask_fulllead_%s.jsonl" % p), encoding="utf-8"):
        r = json.loads(l)
        if r["id"] in IDS:
            flat = [e["words"] for t in ("RUN", "WORD", "CHAR") if t in r["layer0"] for e in r["layer0"][t]["entries"]]
            up = [e["words"] for d in r["on"]["path"]["tiers"].values() for run in d["runs"] for e in run["entries"]]
            h = lambda cs: next((n for n, w in enumerate(cs, 1) if S.hits_words(r["gold"], w)), None)
            t9[(r["id"], p)] = {"off": r["ms_layer0"] / 1000, "on": (r["ms_layer0"] + r["on"]["path"]["ms"]) / 1000,
                                "hf": h(flat), "hl": h(flat + up), "nf": len(flat), "nl": len(flat + up)}
pr = {}
import glob
for pth in sorted(glob.glob(os.path.join(HERE, "logs", "probe_f1b*.log"))):      # the probe prints one JSON record per (question, preset): the logs are the record
    for l in open(pth, encoding="utf-8"):
        m = re.match(r"^(I2-\d+|R2-I\d+) (fast|standard) (\{.*\})$", l.strip())
        if m:
            r = json.loads(m.group(3)); r["id"], r["preset"] = m.group(1), m.group(2); pr[(r["id"], r["preset"])] = r
f = lambda x: "-" if not x else "Y"
g = lambda x: "-" if x is None else "Y"
tm = lambda d, k: "-" if d is None or d.get(k) is None else ("%.1f" % d[k])
print("| id | preset | T9 whole off s | T9 whole on s | T9 hit flat/layers (n flat/layers) | ordered off s | ordered on s (cold: upper crosses built now) | ordered on s (warm) | ordered hit flat/layers (n) | upper crosses built RUN/WORD/CHAR |")
print("|---|---|---|---|---|---|---|---|---|---|")
for i in IDS:
    for p in ("fast", "standard"):
        a = t9[(i, p)]; b = pr.get((i, p))
        row = "| %s | %s | %.1f | %.1f | %s/%s (%d/%d) |" % (i, p, a["off"], a["on"], g(a["hf"]), g(a["hl"]), a["nf"], a["nl"])
        if b:
            c, w = b["cold"], b.get("warm")
            cs = lambda k: ("TIMEOUT>%ds" % b["cap_s"]) if c.get(k + "_timeout") else tm(c, k + "_s")
            hl = "-" if c["hit_layers"] is None else f(c["hit_layers"])
            row += " %s | %s | %s | %s/%s (%s/%s) | %s |" % (
                cs("off"), cs("on"), tm(w, "on_s"), f(c["hit_flat"]), hl, c["flat_n"], c["layers_n"],
                "/".join(str(b["layer1_crosses_built"][t]) for t in ("RUN", "WORD", "CHAR")))
        else:
            row += " (not run) |||||"
        print(row)
