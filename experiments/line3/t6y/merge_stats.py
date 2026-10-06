"""T6y 1: effect of readout merge_sections (L-170) on the 90 S300 RUN answers (t6x default read rule).
Merging is recomputed from the recorded items with the same key the option uses:
(centre, sorted word sequences of the section paths).  Writes results/merge_stats.json + summary_merge.md."""
import collections
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "experiments", "line3"))
import grade as G                                                    # noqa: E402

SRC = os.path.join(ROOT, "experiments/line3/t6x/results/S300_RUN_query_crosses.jsonl")
rows = sorted((json.loads(l) for l in open(SRC, encoding="utf-8")), key=lambda r: r["id"])


def merge(items):
    out = collections.OrderedDict()
    for it in items:
        k = (it["centre"], tuple(sorted(tuple(p["words"]) for p in it["paths"])))
        if k in out:
            out[k]["origins"] = sorted(set(out[k]["origins"]) | set(it["origins"]))
            out[k]["merged"] += 1
        else:
            out[k] = dict(it, merged=1)
    return list(out.values())


def verdict_of(items, orig):
    if orig is None or not items:
        return orig
    return "ANSWER" if len(items) == 1 else "CHOICE"


def grade_rows(merged):
    g = []
    for r in rows:
        a = r["answer"]
        items = a.get("items", [])
        if merged:
            items = merge(items)
        v = verdict_of(items, a.get("verdict")) if merged else a.get("verdict")
        text = "\n".join("".join(p["words"]) for p in items[0]["paths"]) if v == "ANSWER" else ""
        cls = G.classify(v)
        gr, hit, _ = G.grade(cls, r["core"], text, r["subject"], r["gold"])
        g.append(dict(qid=r["id"], kind=r["kind"], cls=cls, grade=gr, gold_hit=hit))
    return g


sizes = {"before": [], "after": []}
per = []
for r in rows:
    items = r["answer"].get("items", [])
    if not items:
        continue
    m = merge(items)
    golds = [x.casefold() for x in r["gold"].split("|") if x]
    gp = any(x in "".join(p["words"]).casefold() for x in golds for it in m for p in it["paths"])
    per.append({"id": r["id"], "kind": r["kind"], "before": len(items), "after": len(m), "gold_in_path": gp})
    sizes["before"].append(len(items))
    sizes["after"].append(len(m))
L = []


def out(s=""):
    L.append(s)
    print(s)


def stat(xs):
    return "%d / %s / %d" % (min(xs), statistics.median(xs), max(xs))


out("## T6y 1: merge_sections on the 90 S300 RUN answers (default read rule query_crosses)")
out()
out("Questions with a read-out (>= 1 item): %d of 90" % len(per))
out()
out("| | min / median / max items | lists (>1 item) | single item (answer) |")
out("|---|---|---|---|")
for k in ("before", "after"):
    xs = sizes[k]
    out("| %s | %s | %d | %d |" % (k, stat(xs), sum(x > 1 for x in xs), sum(x == 1 for x in xs)))
lists = [p for p in per if p["before"] > 1]
out()
out("Lists before: %d; collapse to a single answer: %d; list stays: %d (of which gold in some path: %d)" % (
    len(lists), sum(p["after"] == 1 for p in lists), sum(p["after"] > 1 for p in lists),
    sum(p["after"] > 1 and p["gold_in_path"] for p in lists)))
out("Lists after merging, items min/median/max: %s" % stat([p["after"] for p in lists if p["after"] > 1]))
out()
out("| rule B strict (T0 grader, core-in-subject) | correct/wrong/abstain (answerable 60) | unanswerable answered (fict+attr) |")
out("|---|---|---|")
for name, mg in (("before (no merge)", False), ("after (merge_sections)", True)):
    t = G.tally(grade_rows(mg))
    out("| %s | %d/%d/%d | %d+%d = %d |" % (name, t["correct"], t["wrong"], t["abstain"], t["fict_answered"],
                                            t["attr_answered"], t["answered_unanswerable"]))
out()
out("per question (before -> after): " + ", ".join("%s %d->%d" % (p["id"], p["before"], p["after"]) for p in per if p["before"] > 1))
json.dump(per, open(os.path.join(HERE, "results", "merge_stats.json"), "w"), ensure_ascii=False, indent=1)
open(os.path.join(HERE, "results", "summary_merge.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
