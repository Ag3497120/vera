"""Compare C2 (product BlackStream) with C0's stream numbers. usage: compare.py TIER LEVEL"""
import json, sys
t, l = sys.argv[1:3]
a = json.load(open(f"experiments/line3/carry/c0/results/stream_{t}_{l}.json"))
b = json.load(open(f"experiments/line3/carry/c2/results/c2_{t}_{l}.json"))
def med(x): x = sorted(x); return x[len(x)//2]
for nm, r in (("C0", a), ("C2", b)):
    bl = r["blacks"]
    print(nm, "blacks", len(bl), "units med/max", med([x["units"] for x in bl]), max(x["units"] for x in bl),
          "sents med/max", med([x["sents"] for x in bl]), max(x["sents"] for x in bl),
          "1-sent", sum(1 for x in bl if x["sents"] == 1), "split sents", len(r["split"]))
sa, sb = set(a["split"]), set(b["split"])
print("split only C0", len(sa - sb), "only C2", len(sb - sa), "both", len(sa & sb))
ua = [x["units"] for x in a["blacks"]]; ub = [x["units"] for x in b["blacks"]]
k = 0
while k < min(len(ua), len(ub)) and a["blacks"][k] == b["blacks"][k] or (k < min(len(ua), len(ub)) and (a["blacks"][k]["units"], a["blacks"][k]["sents"], a["blacks"][k]["L"]) == (b["blacks"][k]["units"], b["blacks"][k]["sents"], b["blacks"][k]["L"])): k += 1
print("first differing black index (units,sents,L):", k, "of", len(ua), len(ub))
