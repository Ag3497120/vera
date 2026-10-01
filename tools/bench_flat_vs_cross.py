"""PREREGISTERED_2026-09-28_flat_vs_cross.
    python3.11 tools/bench_flat_vs_cross.py TARGET.json OTHER.json [OTHER.json ...]"""
import json, statistics, sys, time
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.cross_store import CrossStore  # noqa: E402
from verantyx.document_ingest import Document, ingest_documents  # noqa: E402
from verantyx.hierarchy import Node, probe, route  # noqa: E402
from verantyx.lang import ja_content_runs  # noqa: E402
from verantyx.sovereign import group_into_layers  # noqa: E402
from verantyx.verdict import judge, read_records  # noqa: E402

B = Path.home() / "Projects" / "vera-corpus" / "benches"
target = json.loads((B / sys.argv[1]).read_text())["docs"]
others = [d for f in sys.argv[2:] for d in json.loads((B / f).read_text())["docs"]]
pile = []
for k, d in enumerate(target + others):
    pile.append({**d, "key": "文書%03d" % k, "is_target": k < len(target)})

items = {d["key"]: read_records(d["ja"], d["kind"]) for d in pile}
flat = [it for d in pile for it in items[d["key"]]]
t = time.time()
leaves = {}
for d in pile:
    st = CrossStore(); ingest_documents(st, [Document(source=d["key"], text=d["ja"])])
    leaves[d["key"]] = Node(name=d["key"], store=st)
root = group_into_layers("記録", leaves)
build_s = time.time() - t


def descend(q):
    node = root
    for _ in range(16):
        if node.is_leaf:
            return node.name
        step = route(node, q)
        if step["verdict"] != "ANSWER":
            step = probe(node, ja_content_runs(q) or [q])
        if step["verdict"] != "ANSWER":
            return None
        node = node.children[step["child"]]
    return None


def harm(g, v):
    return (g == "SUPPORTED" and v in ("CONTRADICTED", "VIOLATES")) or (g in ("NOT_IN_DOCS", "UNCONFIRMED", "DIFFERENT") and v == "SUPPORTED")


res = {m: Counter() for m in ("flat", "cross", "cross_fallback", "oracle")}
ms = {m: [] for m in res}
routing = Counter()
for d in pile:
    if not d["is_target"]:
        continue
    for c in d["claims"]:
        g = c["label"]
        for m in res:
            t0 = time.perf_counter()
            if m == "flat":
                v = judge(flat, c["ja"])["verdict"]
            elif m == "oracle":
                v = judge(items[d["key"]], c["ja"])["verdict"]
            elif m == "cross_fallback":
                leaf = descend(c["ja"])
                v = judge(items[leaf] if leaf else flat, c["ja"])["verdict"]
            else:
                leaf = descend(c["ja"])
                routing["right" if leaf == d["key"] else ("refused" if leaf is None else "wrong")] += 1
                v = judge(items[leaf], c["ja"])["verdict"] if leaf else "UNCONFIRMED"
            ms[m].append(1000 * (time.perf_counter() - t0))
            res[m]["n"] += 1; res[m]["ok"] += g == v; res[m]["harm"] += harm(g, v)
            res[m]["cv_tot"] += g in ("CONTRADICTED", "VIOLATES"); res[m]["cv_ok"] += g in ("CONTRADICTED", "VIOLATES") and g == v
rep = {"documents": len(pile), "target_documents": len(target), "tree_build_s": round(build_s, 1)}
for m, r in res.items():
    rep[m] = {"accuracy": round(r["ok"] / r["n"], 3), "harm": round(r["harm"] / r["n"], 3),
              "contra_viol_recall": round(r["cv_ok"] / max(r["cv_tot"], 1), 3),
              "median_ms": round(statistics.median(ms[m]), 2)}
n = sum(routing.values())
rep["cross_routing"] = {k: round(v / n, 3) for k, v in routing.items()}
print(json.dumps(rep, ensure_ascii=False, indent=1))
