"""Summarise ev6/out_<set>.json (sweep.py): per set, for evidence.v2 and evidence.v6 (and v6 without CH / SU / TW / NEG): answerable reach, wrong-admitting answerable items, unanswerable
admissions; the reach and the admissions v6 gives up against v2 with the codes that did it; and the SUBSET check (v6's passing stretches of every item are a subset of v2's: a pure filter).
    python ev6/report.py [dev129] [bank6] [bank7] [bank8]        exit status 1 if the subset check fails for any set."""
import collections, csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../../../.."))
sys.path.insert(0, HERE)
from sweep_util import norm
V2, V6 = "evidence.v2", "evidence.v6"
VERS = [V2, V6, "v6-noCH", "v6-noSU", "v6-noTW", "v6-noNEG"]
PREMISE = {"B6-U07", "B6-U09", "B6-U10"}       # premise-false items of bank6: a passing stretch counts as an admission only if it names a 市 / 区


def load(name):
    d = json.load(open(os.path.join(HERE, "out_%s.json" % name), encoding="utf-8"))
    return d, {it["id"]: it for it in d["items"]}, {iid: (out, chain) for iid, out, chain in d["res"]}


def key(x):
    return (x[0], x[1], x[2])


def summary(name):
    """{version: {reach, wrong, unans, traps, shape, adm}} of one probe output (the data the printed report and the tests use)."""
    d, items, res = load(name)
    out = {}
    if name == "dev129":
        trap = {r["#id"]: re.search(r"c\)\s*(.*)$", r["notes"]).group(1).strip()
                for r in csv.DictReader(open(os.path.join(ROOT, "experiments/line3/bank4/bank4.tsv"), encoding="utf-8"), delimiter="\t")}
    for v in VERS:
        reach, wrong, adm, traps, shape = [], [], {}, [], collections.defaultdict(lambda: [0, 0])
        for iid, it in items.items():
            p = res[iid][0][v]
            if it["kind"] == "ans":
                if name == "dev129":
                    ok, bad = any(norm(x[3]) in it["gold"] for x in p), any(norm(x[3]) not in it["gold"] for x in p)
                else:
                    cs = {"exact" if norm(x[3]) in it["gold"] else ("contains" if any(g in norm(x[3]) for g in it["gold"]) else "wrong") for x in p}
                    ok, bad = "exact" in cs, "wrong" in cs
                if ok:
                    reach.append(iid)
                if bad:
                    wrong.append(iid)
            else:
                if name == "bank6" and iid in PREMISE:
                    p = [x for x in p if "市" in x[3] or "区" in x[3]]
                shape[it["shape"]][0] += 1
                if p:
                    adm[iid] = p
                    shape[it["shape"]][1] += 1
                    if name == "dev129" and iid in trap and any(x[3] == trap[iid] for x in p):
                        traps.append(iid)
        out[v] = {"reach": reach, "wrong": wrong, "unans": sorted(adm), "traps": traps, "shape": {k: "%d/%d" % (b, a) for k, (a, b) in sorted(shape.items())}, "adm": adm}
    return out


def subset(name):
    """The pure-filter check of one probe output: {"violations": [item ids whose v6 (or ablation) passes a stretch v2 does not], "stretch_violations": the sweep's own record, "n_v2", "n_v6"}."""
    d, items, res = load(name)
    bad, n2, n6 = [], 0, 0
    for iid, (o, _chain) in res.items():
        s2 = {key(x) for x in o[V2]}
        n2 += len(s2)
        n6 += len(o[V6])
        if not all({key(x) for x in o[v]} <= s2 for v in VERS[1:]) or o["_violations"]:
            bad.append(iid)
    return {"violations": bad, "n_v2": n2, "n_v6": n6, "swept_violations": sum(len(o["_violations"]) for o, _c in res.values())}


def lost(name):
    """[(item id, kind, question, answer, codes)] v2 passes and v6 refuses (the reach and the admissions v6 gives up), in item order."""
    d, items, res = load(name)
    return [(iid, items[iid]["kind"], items[iid]["q"], x[3], x[4]) for iid in items for x in res[iid][0]["_lost"]]


def main(name):
    d, items, _ = load(name)
    n_ans = sum(it["kind"] == "ans" for it in items.values())
    n_un = len(items) - n_ans
    print("== %s (%d answerable + %d unanswerable), evidence.py sha256 %s, v6 digest %s, %ds" % (name, n_ans, n_un, d["evidence_sha"], d.get("v6_digest"), d["seconds"]))
    for v, s in summary(name).items():
        print("%s: answerable reach %d/%d %s | wrong-admitting %d %s | unanswerable admissions %d/%d %s | bank4 traps admitted %d | per shape %s"
              % (v, len(s["reach"]), n_ans, s["reach"], len(s["wrong"]), s["wrong"], len(s["unans"]), n_un, s["unans"], len(s["traps"]), s["shape"] if name == "bank6" else "-"))
        for iid in s["unans"]:
            print("    ADMITTED", iid, items[iid]["q"], [(x[0], x[3]) for x in s["adm"][iid][:4]])
    for iid, kind, q, a, codes in lost(name):
        print("    v2 passes, v6 refuses: %s %s %s [%s] %s" % (iid, "ans" if kind == "ans" else "unans", q, a, "+".join(codes)))
    sb = subset(name)
    print("SUBSET %s: v6 passing stretches (%d) subset of v2's (%d) for every item and every ablation: %s%s" % (
        name, sb["n_v6"], sb["n_v2"], "OK" if not sb["violations"] else "VIOLATED", "" if not sb["violations"] else " " + str(sb["violations"])))
    return not sb["violations"]


if __name__ == "__main__":
    ok = [main(a) for a in (sys.argv[1:] or ["dev129", "bank6", "bank7", "bank8"])]
    sys.exit(0 if all(ok) else 1)
