"""Summarise ev5/out_dev129.json, out_bank6.json and out_bank7.json: reach / wrong-admitting / unanswerable admissions for evidence.v2, v3, v4, v5 (and v5 without SU / without TW), the reach
the two new rules cost, and the SU scan of the question sets.   python ev5/report.py [dev129] [bank6] [bank7]"""
import collections, csv, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "../../../.."))
sys.path.insert(0, HERE)
from sweep_util import norm
VERS = ["evidence.v2", "evidence.v3", "evidence.v4", "evidence.v5", "v5-noSU", "v5-noTW"]
PREMISE = {"B6-U07", "B6-U09", "B6-U10"}       # premise-false items: a passing stretch counts as an admission only if it names a 市 / 区


def load(name):
    d = json.load(open(os.path.join(HERE, "out_%s.json" % name), encoding="utf-8"))
    return d, {it["id"]: it for it in d["items"]}, {iid: (out, chain) for iid, out, chain in d["res"]}


def summary(name):
    """{version: {...numbers...}} of one probe output (the data the printed report and the tests use)."""
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


def cost(name):
    """The answerable items v5 loses against v4 (reach), and which rule loses them: [(id, question, 'SU' | 'TW' | 'both')]."""
    d, items, _ = load(name)
    s = summary(name)
    lost = [i for i in s["evidence.v4"]["reach"] if i not in s["evidence.v5"]["reach"]]
    out = []
    for i in lost:
        by = [r for r, v in (("SU", "v5-noSU"), ("TW", "v5-noTW")) if i in s[v]["reach"]]      # switching the rule off gives the item back
        out.append((i, items[i]["q"], "+".join(by) or "both-needed"))
    return out


def main(name):
    d, items, _ = load(name)
    n_ans = sum(it["kind"] == "ans" for it in items.values())
    n_un = len(items) - n_ans
    print("== %s (%d answerable + %d unanswerable), evidence.py sha256 %s, %ds" % (name, n_ans, n_un, d["evidence_sha"], d["seconds"]))
    for v, s in summary(name).items():
        print("%s: answerable reach %d/%d %s | wrong-admitting %d %s | unanswerable admissions %d/%d %s | bank4 traps admitted %d | per shape %s"
              % (v, len(s["reach"]), n_ans, s["reach"], len(s["wrong"]), s["wrong"], len(s["unans"]), n_un, s["unans"], len(s["traps"]), s["shape"] if name == "bank6" else "-"))
        for iid in s["unans"]:
            print("    ADMITTED", iid, items[iid]["q"], [(x[0], x[3], x[5]) for x in s["adm"][iid][:4]])
    for i, q, r in cost(name):
        print("    REACH LOST v4 -> v5:", i, q, "(rule: %s)" % r)


if __name__ == "__main__":
    for a in (sys.argv[1:] or ["dev129", "bank6", "bank7"]):
        main(a)
