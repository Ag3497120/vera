"""R2 (K290): the base decides, the layer does not override it. From the placement's headwords (r9, read only), by sha256(word) ascending (deterministic; no word list is written by hand):
 - 50 words DECIDED / direct: a `layer_human` row with ANOTHER type of the same namespace -> the answer must not change (all but the two layer keys byte for byte; `BASE_DECIDED`);
 - 20 words MULTIPLE / direct: for the first 10 a row whose type is among the base's candidates -> `DECIDED [T]`, `LAYER_DIRECT_USED`; for the next 10 a type NOT among them -> the base answer, `LAYER_TYPE_NOT_AMONG_CANDIDATES`.
The layer and its ledger are made in --workdir through `write_entry`.
usage: k290_check.py --placement DIR --out FILE.json [--workdir DIR]"""
import argparse
import hashlib
import json
import os
import sqlite3
import sys

ap = argparse.ArgumentParser()
ap.add_argument("--placement", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--workdir", default=None)
a = ap.parse_args()
os.environ.pop("VERA_PLACEMENT_LAYER", None)
from verantyx import coarse_place as CP, coarse_types as ct, placement_layer as PL  # noqa: E402
from verantyx.testimony_ledger import TestimonyLedger  # noqa: E402

work = a.workdir or os.path.join(os.path.dirname(os.path.abspath(a.out)), "k290_work")
os.makedirs(work, exist_ok=True)
for f in ("layer.sqlite", "ledger.jsonl", "ledger.jsonl.manifest.json"):
    p = os.path.join(work, f)
    if os.path.exists(p):
        os.rename(p, p + ".old-%d" % int(os.path.getmtime(p)))
con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % a.placement, uri=True)
rows = con.execute("SELECT word, ns, state, origin, top FROM headwords WHERE origin='direct' AND state IN ('DECIDED','MULTIPLE')").fetchall()
key = lambda w: hashlib.sha256(w.encode("utf-8")).hexdigest()
direct = sorted([r for r in rows if r[2] == "DECIDED"], key=lambda r: key(r[0]))
multi = sorted([r for r in rows if r[2] == "MULTIPLE"], key=lambda r: key(r[0]))


def pick(rs, n):
    out = []
    for r in rs:
        if len(out) == n:
            break
        if CP.query(r[0], placement=a.placement, layer=False)["state"] == r[2]:      # the query agrees with the headword row (a word the query answers otherwise is not used; counted)
            out.append(r)
    return out


d50, m20 = pick(direct, 50), pick(multi, 20)
assert len(d50) == 50 and len(m20) == 20
sha = CP._open(a.placement)[0].sha
layer = os.path.join(work, "layer.sqlite")
led = TestimonyLedger(os.path.join(work, "ledger.jsonl"))
plan = []                           # (word, kind, type written)
for w, ns, st, org, top in d50:
    base_top = [t for t in top.split(",") if t][0]
    pool = list(ct.PRED_TYPES) if base_top.startswith("P_") else list(ct.NOUN_TYPES)
    other = next(t for t in pool if t != base_top)
    plan.append((w, "direct50", other))
for i, (w, ns, st, org, top) in enumerate(m20):
    tops = [t for t in top.split(",") if t]
    if i < 10:
        plan.append((w, "multi_in", tops[0]))
    else:
        pool = list(ct.PRED_TYPES) if tops[0].startswith("P_") else list(ct.NOUN_TYPES)
        plan.append((w, "multi_out", next(t for t in pool if t not in tops)))
for i, (w, kind, t) in enumerate(plan):
    PL.write_entry(layer, led, base_sha256=sha, word=w, type=t, origin="layer_human", decided_by=["layer_human"], evidence={"human": True, "k290": kind}, role_frame=None, key="k290-%d" % i)
res, bad = [], []
for w, kind, t in plan:
    base = CP.query(w, placement=a.placement, layer=False)
    got = CP.query(w, placement=a.placement, layer=layer)
    same = json.dumps({k: v for k, v in got.items() if k not in ("layer", "layer_status")}, ensure_ascii=False) == json.dumps(base, ensure_ascii=False)
    if kind == "direct50":
        ok = same and got["layer"] == "base" and got["layer_status"] == "BASE_DECIDED"
    elif kind == "multi_in":
        ok = got["state"] == "DECIDED" and got["top"] == [t] and got["layer_status"] == "LAYER_DIRECT_USED" and base["state"] == "MULTIPLE" and t in base["top"]
    else:
        ok = same and got["layer"] == "base" and got["layer_status"] == "LAYER_TYPE_NOT_AMONG_CANDIDATES" and t not in base["top"]
    res.append({"word": w, "kind": kind, "layer_type": t, "base_state": base["state"], "base_top": base["top"], "layer": got["layer"], "layer_status": got["layer_status"],
                "answer_state": got["state"], "answer_top": got["top"], "identical_but_two_keys": same, "ok": ok})
    if not ok:
        bad.append(w)
summary = {k: {"words": sum(1 for r in res if r["kind"] == k), "ok": sum(1 for r in res if r["kind"] == k and r["ok"])} for k in ("direct50", "multi_in", "multi_out")}
out = {"placement": a.placement, "placement_sha256": sha, "summary": summary, "failed": bad, "all_ok": not bad, "rows": res}
json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({"summary": summary, "failed": bad, "all_ok": not bad}, ensure_ascii=False))
sys.exit(0 if not bad else 1)
