"""The base (tree + fallback over predicate-argument records) on the verdict benches: target docs mixed with others."""
import json, statistics, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.base import Base  # noqa: E402
from verantyx.verdict import judge, read_records  # noqa: E402
B = Path.home() / "Projects" / "vera-corpus" / "benches"
target = json.loads((B / sys.argv[1]).read_text())["docs"]
others = [d for f in sys.argv[2:] for d in json.loads((B / f).read_text())["docs"]]
base = Base()
for k, d in enumerate(target + others):
    base.add("文書%03d" % k, d["ja"], d["kind"])
base.build()
harm = lambda g, v: (g == "SUPPORTED" and v in ("CONTRADICTED", "VIOLATES")) or (g in ("NOT_IN_DOCS", "UNCONFIRMED", "DIFFERENT") and v == "SUPPORTED")
res, paths, ms, oracle = Counter(), Counter(), [], Counter()
for k, d in enumerate(target):
    for c in d["claims"]:
        r = base.judge(c["ja"]); g = c["label"]
        res["n"] += 1; res["ok"] += r["verdict"] == g; res["harm"] += harm(g, r["verdict"])
        paths[r["path"] + ("_right" if r["leaf"] == "文書%03d" % k else ("_none" if r["leaf"] is None else "_wrong"))] += 1
        ms.append(r["ms"])
        o = judge(read_records(d["ja"], d["kind"]), c["ja"])["verdict"]; oracle["ok"] += o == g; oracle["harm"] += harm(g, o)
n = res["n"]
print(json.dumps({"documents": len(base.docs), "base_accuracy": round(res["ok"] / n, 3), "base_harm": round(res["harm"] / n, 3),
                  "oracle_accuracy": round(oracle["ok"] / n, 3), "oracle_harm": round(oracle["harm"] / n, 3),
                  "median_ms": round(statistics.median(ms), 2), "paths": dict(paths)}, ensure_ascii=False, indent=1))
