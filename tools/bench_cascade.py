"""Two-stage verdicts on a verdict bench: same lines as PREREGISTERED_2026-09-28_verdict_contract."""
import json, sys, time
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.cascade import verify  # noqa: E402
B = Path.home() / "Projects" / "vera-corpus" / "benches"
name = sys.argv[1]
docs = json.loads((B / name).read_text())["docs"]
m, feat, esc, secs, t0 = Counter(), Counter(), 0, [], time.time()
for d in docs:
    rs = verify(d["ja"], [c["ja"] for c in d["claims"]], d["kind"])
    for c, r in zip(d["claims"], rs):
        m[(c["label"], r["verdict"])] += 1; feat[(c["feature"], c["label"] == r["verdict"])] += 1
        esc += r["stage"] == "bonsai"
        if r.get("llm_seconds"): secs.append(r["llm_seconds"])
    print(".", end="", flush=True)
n = sum(m.values()); tot = lambda *g: sum(v for (a, _), v in m.items() if a in g) or 1
harm = m[("SUPPORTED", "CONTRADICTED")] + m[("SUPPORTED", "VIOLATES")] + sum(m[(g, "SUPPORTED")] for g in ("NOT_IN_DOCS", "UNCONFIRMED", "DIFFERENT"))
ep = sum(v for (f, ok), v in feat.items() if f in ("ellipsis", "pronoun") and ok)
print()
print(json.dumps({"n": n, "1_harm": round(harm / n, 3),
    "2_contra_viol_recall": round((m[("CONTRADICTED", "CONTRADICTED")] + m[("VIOLATES", "VIOLATES")]) / tot("CONTRADICTED", "VIOLATES"), 3),
    "3_diff_not_contra": round(1 - m[("DIFFERENT", "CONTRADICTED")] / tot("DIFFERENT"), 3),
    "6_oos_held": round(m[("OUT_OF_SCOPE", "OUT_OF_SCOPE")] / tot("OUT_OF_SCOPE"), 3),
    "accuracy": round(sum(v for (a, b), v in m.items() if a == b) / n, 3),
    "escalated": esc, "escalated_share": round(esc / n, 3), "llm_calls": len(set(secs)) and len(docs),
    "llm_seconds_total": round(time.time() - t0, 1),
    "matrix": {"%s->%s" % k: v for k, v in sorted(m.items())}}, ensure_ascii=False, indent=1))
