"""G3-k review (L-810): for every GAINED gold, the exact diff of what was read with the stand-ins and without them.

usage: gain_diff.py [--out results/gain_diff.json]   (PYTHONPATH=. PYTHONHASHSEED=0; reads results/*.jsonl, opens the same index and window index as measure_k.py)

A question is gained when its on list holds the gold in a candidate and the baseline list does not: bank3 against the ORDER-ONLY run and against off, bank2 intra2
against off.  For each gold-bearing entry of the on list (jsonl), the entry is looked up in a fresh run of the same question (flat: A.ask(grammar="on");
windows: slide_flat plan) and the read sets of the two orderings are diffed -- the ordering with the stand-ins and the SAME ordering with the stand-ins dropped from
the intake (the order-only intake), both under the fast cap:

  flat/<tier> entry : the seeds of the crosses it came from; the crosses read only with the stand-ins (A) and only without them (B); is any of its seeds read by the
                      order-only ordering (then the entry is NOT `read_via_standin`); does the order-only flat list hold the same word set (it cannot: the gold is
                      absent there).  An entry none of whose seeds is in A and that is absent from the order-only list was reached through the change of the SET read (the
                      V3 pool of the end states differs), not through a stand-in cross.
  window entry      : its window number; read with / without the stand-ins; and, if read without, whether the order-only list of that window holds the entry (the
                      starts of a window that hold only a stand-in are not gated away with the stand-ins in the query).
  layers entry      : not marked per entry (the provenance is a union over bundles): reported as such, with the layer-1 bundle SET of the question (read crosses + original
                      query units + answer units) next to the order-only one.
Writes results/gain_diff.json and prints a text table (summarize_k.py reads the json)."""
import argparse, dataclasses, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
L3 = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(L3, "t9"))
import scorer as S                                       # noqa: E402
from verantyx.line3 import ask as A                      # noqa: E402
from verantyx.line3 import cycle as cy                   # noqa: E402
from verantyx.line3 import slide_flat as SF              # noqa: E402
from verantyx.line3 import slide_query as SQ             # noqa: E402
from verantyx.line3 import wiring as W                   # noqa: E402

RES = os.path.join(HERE, "results")
ap = argparse.ArgumentParser()
ap.add_argument("--out", default=os.path.join(RES, "gain_diff.json"))
ap.add_argument("--cache", default="/Users/motonisihikoudai/Projects/vera-impl/cache/t11")
ap.add_argument("--ids", default="all")
ARGS = ap.parse_args()
DATA = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")


def jl(p): return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
def recs(n):
    p = os.path.join(RES, n)
    return {r["id"]: r for r in jl(p) if "error" not in r} if os.path.exists(p) else {}


def bank(path):
    b = {}
    for l in open(path, encoding="utf-8"):
        if l.startswith("#") or not l.strip():
            continue
        r = dict(zip("id kind corpus subject question gold evidence notes audit".split(), l.rstrip("\n").split("\t")))
        b[r["id"]] = r
    return b


BANK3, BANK2 = bank(os.path.join(L3, "bank3", "bank3.tsv")), bank(os.path.join(L3, "bank2", "bank2.tsv"))
ASSEMBLED = "flat/assembled"


def ents(r): return [e for e in r["answer"]["entries"] if e["origins"] != [ASSEMBLED]]
def gold_of(r, b):
    g = b[r["id"]]["gold"]
    return g.split("|", 1)[1] if r["kind"] == "summary-choice" else g
def gold_entries(r, b):
    g = gold_of(r, b)
    return [e for e in ents(r) if S.hits_words(g, e["words"])]
def has_gold(r, b): return bool(gold_entries(r, b))


on3, off3, oo3 = recs("bank3_uwpa_fast_on.jsonl"), recs("bank3_uwpa_fast_off.jsonl"), recs("bank3_uwpa_fast_on_order_only.jsonl")
on2, off2 = recs("bank2_fast_on.jsonl"), recs("bank2_fast_off.jsonl")
jobs = []                                                # (bank name, id, baseline name, on record, baseline record, bank)
for i in sorted(on3):
    if i in oo3 and has_gold(on3[i], BANK3) and not has_gold(oo3[i], BANK3):
        jobs.append(("bank3", i, "order-only", on3[i], oo3[i], BANK3))
    if i in off3 and has_gold(on3[i], BANK3) and not has_gold(off3[i], BANK3):
        jobs.append(("bank3", i, "off", on3[i], off3[i], BANK3))
for i in sorted(on2):
    if BANK2[i]["kind"] == "intra2" and i in off2 and has_gold(on2[i], BANK2) and not has_gold(off2[i], BANK2):
        jobs.append(("bank2", i, "off", on2[i], off2[i], BANK2))
if ARGS.ids != "all":
    jobs = [j for j in jobs if j[1] in ARGS.ids.split(",")]

idx = A.Index.from_jsonl(DATA, ARGS.cache, A.DEFAULT_LEVEL, A.TIERS, group_insert="ordered", order="forward")
ix, recs_ = W.context_of(idx)
wi = SQ.window_index_for(idx, workers=1)
_n, CAP, _lv = A.resolve_effort("fast", None)
out_rows = []
for bk, qid, base, onr, baser, b in jobs:
    q = b[qid]["question"]
    gi = W.intake(idx.space, q, ix)
    oo_gi = dataclasses.replace(gi, words=(), standins=())
    fresh = A.ask(idx, q, effort="fast", grammar="on", grammar_intake=gi)
    plan_on = SQ.plan_windows(wi, SQ.intake(wi, q, gi), hold="seats", standins="on" if gi.standins else "off", within="qcount", cap=CAP, read_order="qcount_first")
    plan_oo = SQ.plan_windows(wi, SQ.intake(wi, q, oo_gi), hold="seats", standins="off", within="qcount", cap=CAP, read_order="qcount_first")
    row = {"bank": bk, "id": qid, "baseline": base, "standin_units": len(gi.standins), "entries": []}
    for e in gold_entries(onr, b):
        origin = ",".join(e["origins"])
        rec = {"origin": origin, "marks": e["marks"], "words": e["words"][:6]}
        fl = [o for o in e["origins"] if o.startswith("flat/")]
        if fl:
            tier = fl[0].split("/")[1]
            o = fresh.outcome(tier)
            p = o.result.plan
            reads_on, reads_oo = set(p.read), set(p.order_only_read if p.order_only_read is not None else p.read)
            ent = [x for x in o.entries if tuple(x.words) == tuple(e["words"])]
            if ent:
                x = ent[0]
                seeds = sorted({o.answer.states[si].ref.seed for a in x.arrangements for si in a.origins})
                rec.update({"seeds": seeds, "seeds_read_by_the_order_alone": [s for s in seeds if s in reads_oo], "read_only_with_standins": sorted(reads_on - reads_oo),
                            "read_only_without_standins": sorted(reads_oo - reads_on), "n_read_on": len(reads_on), "n_read_order_only": len(reads_oo)})
                rec["path"] = ("stand-in cross (no original unit)" if all(not (cy.placement_units(idx.stores[tier].cross_for(s)) & set(gi.units)) for s in seeds)
                               else "read only through the tie-break" if not rec["seeds_read_by_the_order_alone"]
                               else "the crosses are read by the order alone too: the SET read differs (V3 pool), not a stand-in cross")
            else:
                rec["path"] = "entry not reproduced by the fresh run (differs)"
        wn = [m["window"]["n"] for m in e["members"] if m["origin"].startswith("window/") and "window" in m]
        if wn:
            n = wn[0]
            rec.update({"window": n, "read_with_standins": n in plan_on.read, "read_by_the_order_alone": n in plan_oo.read})
            bw = [m["window"]["n"] for x in ents(baser) for m in x["members"] if m["origin"].startswith("window/") and "window" in m]
            rec["baseline_lists_this_window"] = n in bw
            rec["path"] = ("window read only through the stand-ins (not read by the same order without them)" if n not in plan_oo.read
                           else "window read in both; the entry is new: a start that holds only a stand-in, or a different cycle over the window" if n not in bw
                           else "window read in both and listed in both (the gold entry is another one)")
        if all(o.startswith("layers") for o in e["origins"]):
            rec["path"] = "layers entry: not marked per entry (union over bundles)"
        row["entries"].append(rec)
    out_rows.append(row)
    print(bk, qid, "vs", base, "|", "; ".join("%s: %s" % (r["origin"], r.get("path")) for r in row["entries"]), flush=True)
json.dump(out_rows, open(ARGS.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
