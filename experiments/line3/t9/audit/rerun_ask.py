"""T9 audit: re-run flat + layers (path, stable-seats-path) exactly as measure_ask.py, but keep what the T9 records
dropped: per entry the source sentences (source_sids, and word_sources for layer entries), the crosses read, and a
per-tier cascade for the gold (gold unit in the tier -> in a read cross -> in a settled end state -> in an adopted
state -> on a section path = entry).  Measurement only; nothing in verantyx/ is changed.
usage: rerun_ask.py CORPUS PRESET OUT.jsonl [WORKERS=1] [KINDS=intra2] [IDS=all]"""
import json, multiprocessing as mp, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.dirname(HERE))
from verantyx.line3 import ask as A          # noqa: E402
from verantyx.line3 import matryoshka as M   # noqa: E402
import scorer as S                           # noqa: E402

CORPUS, PRESET, OUT = sys.argv[1:4]
workers = int(sys.argv[4]) if len(sys.argv) > 4 else 1
kinds = sys.argv[5] if len(sys.argv) > 5 else "intra2"
ids = sys.argv[6] if len(sys.argv) > 6 else "all"
CACHE = os.environ["T9_CACHE"]
DATA = {"fulllead": os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl"),
        "s3000": os.path.join(ROOT, "experiments/line3/data/S3000.jsonl")}[CORPUS]
BANK = os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv")
CONFIGS = [("path", "path"), ("seatsPath", "stable-seats-path")]
G = {}


def gold_units(ts, gold):
    gs = S.golds(gold)
    return {u for u in ts.units() if any(g in S.norm(u) for g in gs)}


def flat_has(flat, gu):
    return any(c in gu for c in flat if c is not None)


def tier_cascade(idx, o, gu):
    tier = o.tier
    store = idx.stores[tier]
    res = o.result
    read = list(res.plan.read)
    read_gold = [s for s in read if set(M.placed_units(store.cross_for(s))) & gu]
    ends = ends_gold = ends_ans = ends_ans_gold = 0
    nofix = 0
    for sr in res.reads:
        for m in sr.members:
            if m.kind == "no_fixed_point":
                nofix += 1
            for e in m.settled.ends:
                ends += 1
                g = flat_has(e.flat, gu)
                ends_gold += g
                if m.kind == "candidate" and e.answer is not None:
                    ends_ans += 1; ends_ans_gold += g
    adopted = len(res.candidates)
    adopted_gold = sum(flat_has(c.end.flat, gu) for c in res.candidates)
    kinds = {}
    for sr in res.reads:
        for m in sr.members:
            kinds[m.kind] = kinds.get(m.kind, 0) + 1
    return {"verdict": o.verdict, "cycle_verdict": res.verdict, "ms": o.ms, "read": read, "cap_total": res.plan.cap_total,
            "cap_unread": res.plan.cap_unread, "boundary": res.plan.boundary,
            "order_groups": [[g, len(ss)] for g, ss in res.plan.order_groups][:30],
            "query_units": list(res.ctx.query), "members_read": res.members_read, "members_total": res.members_total,
            "member_kinds": kinds, "states_expanded": res.counts.get("states_expanded", 0),
            "cross_sizes": [store.cross_for(s).size for s in read], "class_sizes": [store.cross_for(s).expanded_size for s in read],
            "read_gold": read_gold, "ends": ends, "ends_gold": ends_gold, "ends_answering": ends_ans,
            "ends_answering_gold": ends_ans_gold, "nofix_members": nofix, "adopted": adopted, "adopted_gold": adopted_gold,
            "entries": [{"words": list(e.words), "sids": list(e.source_sids)} for e in o.entries]}


def _work(row):
    qid, kind, _c, subj, question, gold, evidence = row[:7]
    idx = G["idx"]
    kw = {"effort": PRESET}
    t0 = time.monotonic()
    c0 = A.ask(idx, question, **kw)
    ms0 = int((time.monotonic() - t0) * 1000)
    rec = {"id": qid, "kind": kind, "question": question, "gold": gold, "evidence": evidence, "preset": PRESET, "ms_layer0": ms0,
           "layer0": {}, "on": {}}
    for o in c0.outcomes:
        ts = idx.space.tiers[o.tier]
        gu = gold_units(ts, gold)
        rec["layer0"][o.tier] = dict(tier_cascade(idx, o, gu), gold_units=sorted(gu)[:50], n_gold_units=len(gu))
    for name, cand in CONFIGS:
        opts = M.LayerOptions(variants=("A",), granularity="compress", feedback="none", candidate=cand,
                              bounds=M.bounds_for(PRESET, None))
        t1 = time.monotonic()
        c = M.ask_layered(idx, question, options=opts, base=c0, **kw)
        ms = int((time.monotonic() - t1) * 1000)
        tiers = {}
        for tl in c.layers:
            ts = idx.space.tiers[tl.tier]
            gu = gold_units(ts, gold)
            store = idx.stores[tl.tier]
            runs = []
            for r in tl.runs:
                under = set()
                kmax = r.k
                if r.result is not None:
                    for sr in r.result.reads:
                        for m in sr.members:
                            for e in m.settled.ends:
                                under.update(c_ for c_ in e.flat if c_ is not None)
                        under.add(sr.seed)
                gold_under = None
                if r.k == 1:
                    gold_under = any(set(M.placed_units(store.cross_for(b[len("⟦1:"):-1]))) & gu
                                     for b in under if b.startswith("⟦1:"))
                ents = []
                for e in r.entries:
                    ws = set()
                    for _w, ss in (e.word_sources or ()):
                        ws.update(ss)
                    ents.append({"words": list(e.words), "sids": sorted(set(e.source_sids) | ws), "bundles": len(e.bundles)})
                runs.append({"k": r.k, "verdict": r.verdict, "ms": r.ms, "n_bundles": r.n_bundles, "read": len(r.read),
                             "left_unread": r.left_unread, "members_read": r.members_read, "members_total": r.members_total,
                             "no_fixed_point": r.no_fixed_point, "gold_under_read_bundles": gold_under,
                             "entries": ents})
            tiers[tl.tier] = {"triggered": tl.triggered, "ms": tl.ms, "runs": runs}
        rec["on"][name] = {"ms": ms, "tiers": tiers}
    return rec


def _init():
    G["idx"] = A.Index.from_jsonl(DATA, CACHE)


if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(BANK, encoding="utf-8") if not l.startswith("#") and l.strip()]
    rows = [r for r in rows if r[2] == CORPUS and r[1] in kinds.split(",")]
    if ids != "all":
        rows = [r for r in rows if r[0] in ids.split(",")]
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)["id"] for l in open(OUT, encoding="utf-8")}
    rows = [r for r in rows if r[0] not in done]
    t0 = time.time()
    if workers <= 1:
        _init(); it = map(_work, rows)
    else:
        it = mp.get_context("fork").Pool(workers, initializer=_init).imap_unordered(_work, rows)
    n = 0
    with open(OUT, "a", encoding="utf-8") as f:
        for rec in it:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"); f.flush(); n += 1
            print("%d/%d %s l0 %.1fs %s" % (n, len(rows), rec["id"], rec["ms_layer0"] / 1000,
                  " ".join("%s %.1fs" % (k, v["ms"] / 1000) for k, v in rec["on"].items())), file=sys.stderr, flush=True)
    print("done %d in %.0fs" % (n, time.time() - t0), file=sys.stderr)
