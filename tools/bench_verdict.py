"""PREREGISTERED_2026-09-28_verdict_contract — run the sealed bench."""
import json, statistics, sys, time
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.verdict import judge, read_records  # noqa: E402

B = Path.home() / "Projects" / "vera-corpus" / "benches" / (sys.argv[1] if len(sys.argv) > 1 else "verdict_heldout_raw.json")
docs = json.loads(B.read_text())["docs"]
m, feat, times, compile_ms, fails = Counter(), Counter(), [], [], []
for d in docs:
    t = time.perf_counter(); items = read_records(d["ja"], d["kind"]); compile_ms.append(1000 * (time.perf_counter() - t))
    for c in d["claims"]:
        t = time.perf_counter(); r = judge(items, c["ja"]); times.append(1000 * (time.perf_counter() - t))
        g, v = c["label"], r["verdict"]
        m[(g, v)] += 1; feat[(c["feature"], g == v)] += 1
        if g != v:
            fails.append({"doc": d["title"], "kind": d["kind"], "claim": c["ja"], "gold": g, "got": v,
                          "feature": c["feature"], "why": r.get("why", ""), "gold_evidence": c["evidence"]})
tot = lambda *gs: sum(v for (g, _), v in m.items() if g in gs) or 1
harm = (m[("SUPPORTED", "CONTRADICTED")] + m[("SUPPORTED", "VIOLATES")]
        + sum(m[(g, "SUPPORTED")] for g in ("NOT_IN_DOCS", "UNCONFIRMED", "DIFFERENT")))
n = sum(m.values())
cond_claims = [(f["feature"], f["gold"], f["got"]) for f in fails]
rep = {
    "n_claims": n, "n_docs": len(docs),
    "1_harmful_rate": round(harm / n, 3),
    "2_contradiction_violation_recall": round((m[("CONTRADICTED", "CONTRADICTED")] + m[("VIOLATES", "VIOLATES")]) / tot("CONTRADICTED", "VIOLATES"), 3),
    "3_different_not_called_contradicted": round(1 - m[("DIFFERENT", "CONTRADICTED")] / tot("DIFFERENT"), 3),
    "4_condition_exception_not_called_violates": round(1 - sum(v for (fe, ok), v in feat.items() if False) , 3),
    "5_ellipsis_pronoun_supported_recall": None,
    "6_out_of_scope_held": round(m[("OUT_OF_SCOPE", "OUT_OF_SCOPE")] / tot("OUT_OF_SCOPE"), 3),
    "7_median_ms_per_claim": round(statistics.median(times), 3),
    "compile_ms_per_doc_median": round(statistics.median(compile_ms), 1),
    "accuracy": round(sum(v for (g, x), v in m.items() if g == x) / n, 3),
    "matrix": {"%s->%s" % k: v for k, v in sorted(m.items())},
    "by_feature": {"%s:%s" % (k[0], "ok" if k[1] else "miss"): v for k, v in sorted(feat.items())},
}
# line 4: claims with feature condition/exception whose gold is not VIOLATES, judged VIOLATES
ce = [(c, d) for d in docs for c in d["claims"] if c["feature"] in ("condition", "exception") and c["label"] != "VIOLATES"]
bad4 = sum(1 for c, d in ce if judge(read_records(d["ja"], d["kind"]), c["ja"])["verdict"] == "VIOLATES")
rep["4_condition_exception_not_called_violates"] = round(1 - bad4 / max(len(ce), 1), 3)
ep = [(c, d) for d in docs for c in d["claims"] if c["feature"] in ("ellipsis", "pronoun") and c["label"] == "SUPPORTED"]
ok5 = sum(1 for c, d in ep if judge(read_records(d["ja"], d["kind"]), c["ja"])["verdict"] == "SUPPORTED")
rep["5_ellipsis_pronoun_supported_recall"] = round(ok5 / max(len(ep), 1), 3)
rep["n_line4"], rep["n_line5"] = len(ce), len(ep)
print(json.dumps(rep, ensure_ascii=False, indent=1))
B.with_suffix(".fails.json").write_text(json.dumps(fails, ensure_ascii=False, indent=1), encoding="utf-8")
