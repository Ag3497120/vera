"""W16-t6 / T6-2: compare_table.json の全数値を生データ（t6_1_synth.json・expected.jsonl・llm_run{1,2,3}.jsonl）から独立に再計算して照合する。attest.py を import しない。
使い方: python recompute.py [比較ディレクトリ（既定: このファイルのあるディレクトリ）]"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
D = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE
SYN = HERE.parent / "synth"
exp = [json.loads(l) for l in (SYN / "expected.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
synth = json.loads((HERE.parent / "t6_1_synth.json").read_text(encoding="utf-8"))
byid = {c["id"]: c for c in synth["cases"]}
hasjson = {json.loads(l)["id"]: json.loads(l)["has_json"] for l in (SYN / "cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()}
tab = json.loads((D / "compare_table.json").read_text(encoding="utf-8"))
rows = tab["rows"]
bad = []


def check(name, got, want):
    ok = (abs(got - want) < 1e-9) if isinstance(got, float) or isinstance(want, float) else got == want
    print("%-22s recomputed=%-8s table=%-8s %s" % (name, got, want, "OK" if ok else "DIFF"))
    if not ok:
        bad.append(name)


for ex in ("V", "a", "b"):
    n = fa = det = miss = fp = ins = nx = extra = 0
    for e in exp:
        case = byid[e["id"]]
        if ex == "a" and not hasjson[e["id"]]:
            continue
        actual = {}
        for c in case["extractors"][ex]["claims"]:
            for f in c["facts"]:
                actual.setdefault(f["fact"], f["mark"])
        sigs = set()
        for c in e["claims"]:
            for f in c["facts"]:
                sigs.add(f["sig"])
                n += 1
                fa += f["truth"] == "false"
                m = actual.get(f["sig"])
                if m is None:
                    nx += 1
                elif f["truth"] == "false":
                    det += m == "MISMATCH"
                    miss += m == "RECORD"
                elif f["truth"] == "true":
                    fp += m == "MISMATCH"
                    ins += m == "TESTIMONY"
        extra += len([s for s in actual if s not in sigs])
    r = rows[ex]
    for name, got, key in (("%s facts" % ex, n, "対象の事実"), ("%s false" % ex, fa, "偽"), ("%s detected" % ex, det, "検出"), ("%s missed" % ex, miss, "見逃し"),
                           ("%s false_positive" % ex, fp, "誤検出"), ("%s insufficient" % ex, ins, "裏づけ不足"), ("%s not_extracted" % ex, nx, "未抽出"), ("%s extra" % ex, extra, "余剰")):
        check(name, got, r[key])
    check("%s rate" % ex, det / fa, r["検出率"])

truth = {(e["id"], f["sig"]): f["truth"] for e in exp for c in e["claims"] for f in c["facts"]}
runs = [[json.loads(l) for l in (D / ("llm_run%d.jsonl" % i)).read_text(encoding="utf-8").splitlines() if l.strip()] for i in (1, 2, 3)]
for i, run in enumerate(runs, 1):
    fa = det = miss = fp = ins = unp = 0
    for r in run:
        t = truth[(r["case"], r["sig"])]
        a = r["answer"]
        unp += a == "LLM_UNPARSEABLE"
        if t == "false":
            fa += 1
            det += a == "LLM_NO"
            miss += a == "LLM_YES"
        elif t == "true":
            fp += a == "LLM_NO"
            ins += a in ("LLM_UNKNOWN", "LLM_UNPARSEABLE")
    k = "c%d" % i
    for name, got, key in (("%s facts" % k, len(run), "対象の事実"), ("%s false" % k, fa, "偽"), ("%s detected" % k, det, "検出"), ("%s missed" % k, miss, "見逃し"),
                           ("%s false_positive" % k, fp, "誤検出"), ("%s insufficient" % k, ins, "裏づけ不足"), ("%s unparseable" % k, unp, "LLM_UNPARSEABLE")):
        check(name, got, rows[k][key])
    check("%s rate" % k, det / fa, rows[k]["検出率"])
per = [{(r["case"], r["sig"]): r["answer"] for r in run} for run in runs]
unstable = sum(1 for key in per[0] if len({p[key] for p in per}) > 1)
check("c unstable", unstable, rows["c"]["揺れ"])
check("c unstable denominator", len(per[0]), rows["c"]["揺れ分母"])
V = rows["V"]["検出率"]
check("lift V-a", V - rows["a"]["検出率"], tab["lift"]["V-a"])
check("lift V-b", V - rows["b"]["検出率"], tab["lift"]["V-b"])
for i in (1, 2, 3):
    check("lift V-c%d" % i, V - rows["c%d" % i]["検出率"], tab["lift"]["V-c%d" % i])
print("ALL OK" if not bad else "DIFF: %s" % bad)
sys.exit(1 if bad else 0)
