"""G3-f: the questions the members=all runs cover.  members=all settles one start per strictly stable member of every window read; at fast on z slide
that is 65128 starts over the 94 questions (about 0.4 s each: hours).  This lists the questions whose windows read at fast (qcount_first, cap 4) hold at most
LIMIT (default 700) starts together; results/all_subset_ids.txt is its output (57 questions, 17808 of the 65128 starts).
usage: subset_ids.py CACHE_ROOT [LIMIT=700]"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import slide_flat as F    # noqa: E402
from verantyx.line3 import slide_query as Q   # noqa: E402

LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else 700
wi = Q.WindowIndex.from_jsonl(os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl"), os.path.join(sys.argv[1], "slide"), build=False, z_deep="slide")
rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv"), encoding="utf-8") if not l.startswith("#") and l.strip()]
rows = [r for r in rows if r[2] == "fulllead" and r[1] in ("intra2", "unans")]
cost = {}
for r in rows:
    it = Q.intake(wi, r[4])
    n = 0
    for k in Q.plan_windows(wi, it, cap=4).read:
        w = wi.by_n[k]
        sel, _ = Q.choose_members(w, "all", "abstain")
        n += len(F.starts_of(w, sel, it.qset, "both")[0])
    cost[r[0]] = n
keep = sorted(i for i in cost if cost[i] <= LIMIT)
print("%d questions, %d starts of %d" % (len(keep), sum(cost[i] for i in keep), sum(cost.values())))
open(os.path.join(HERE, "results", "all_subset_ids.txt"), "w").write(",".join(keep) + "\n")
