"""T9: bank2 questions of one corpus through the carry tower (RUN, low) + carry_query.
usage: measure_carry.py CORPUS COMBOS OUTPREFIX [WORKERS=1] [-] [IDS=all] [PO=close|defer] [KINDS=all]
       COMBOS = comma list of PRESET:FALLBACK (fast:none,fast:index,standard:none,...); one tower per process is shared by all combos;
       output files OUTPREFIX_<po>_<path|index>_<preset>.jsonl
Run from the repo root with PYTHONPATH=. (as carry/c5/measure.py, same calls)."""
import hashlib, json, multiprocessing as mp, os, sys, time
sys.path.insert(0, os.getcwd())
from verantyx.line3 import carry as C              # noqa: E402
from verantyx.line3 import carry_query as CQ       # noqa: E402
from verantyx.line3 import placement as pl         # noqa: E402
from verantyx.line3 import space as sp             # noqa: E402

CORPUS, COMBOS, OUTP = sys.argv[1:4]
workers = int(sys.argv[4]) if len(sys.argv) > 4 else 1
ids = sys.argv[6] if len(sys.argv) > 6 else "all"
po = sys.argv[7] if len(sys.argv) > 7 else "close"
kinds = sys.argv[8] if len(sys.argv) > 8 else "all"
DATA = {"fulllead": "experiments/line3/bank2/data/fulllead_sents.jsonl", "s3000": "experiments/line3/data/S3000.jsonl"}[CORPUS]
BANK = "experiments/line3/bank2/bank2.tsv"
tier, level = "RUN", "low"
G = {}


def _ask(args):
    row, preset, fb = args
    qid, kind, _c, subj, question, gold = row[:6]
    kw = {"nodes": int(preset)} if preset.isdigit() else {"effort": preset}
    a = CQ.ask(G["tw"], question, tier_space=G["ts"], fallback=None if fb == "none" else fb, **kw)
    tr = CQ.trace(G["tw"], a, G["ts"])
    o = a.answer_obj()
    return {"id": qid, "kind": kind, "corpus": CORPUS, "question": question, "gold": gold, "preset": preset, "fallback": fb, "po": po,
            "verdict": a.verdict, "listed": o["listed"],
            "entries": [{k: e[k] for k in ("words", "centres", "arrangements", "stability", "inherited")} for e in o["entries"]],
            "read": o["read"], "ms": a.ms,
            "trace": {"checked": tr.words_checked, "traced": tr.words_traced, "ok": tr.ok, "failures": list(tr.failures[:5])}}


if __name__ == "__main__":
    rows = [json.loads(l) for l in open(DATA, encoding="utf-8")]
    space = sp.build_space(rows)
    G["ts"] = space.tiers[tier]
    budget = pl.budget_level(level)
    t0 = time.process_time()
    G["tw"] = C.build_tower(tier, G["ts"], list(range(len(rows))), budget, unit_filter="default", **({} if po == "close" else {"pack_overflow": po}))
    print("tower %s %s %s po=%s: levels %s, units %d, packs %d, build %.0f s cpu, sha %s" % (
        CORPUS, tier, level, po, G["tw"].level_sizes(), len(G["tw"].units()), len(G["tw"].packs), time.process_time() - t0,
        G["tw"].sha256()[:12]), file=sys.stderr, flush=True)
    qs = [l.rstrip("\n").split("\t") for l in open(BANK, encoding="utf-8") if not l.startswith("#") and l.strip()]
    qs = [r for r in qs if r[2] == CORPUS]
    if ids != "all":
        qs = [r for r in qs if r[0] in ids.split(",")]
    if kinds != "all":
        qs = [r for r in qs if r[1] in kinds.split(",")]
    for combo in COMBOS.split(","):
        preset, fb = combo.split(":")
        OUT = "%s_%s_%s_%s.jsonl" % (OUTP, po, "index" if fb == "index" else "path", preset)
        t0 = time.time()
        jobs = [(q, preset, fb) for q in qs]
        it = map(_ask, jobs) if workers <= 1 else mp.get_context("fork").Pool(workers).imap_unordered(_ask, jobs)
        n = 0
        os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
        with open(OUT, "w", encoding="utf-8") as f:
            for rec in it:
                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"); f.flush(); n += 1
                print("%s %d/%d %s %s %d ms" % (combo, n, len(qs), rec["id"], rec["verdict"], rec["ms"]), file=sys.stderr, flush=True)
        print("done %s %d in %.0f s" % (combo, n, time.time() - t0), file=sys.stderr, flush=True)
