"""T9 audit: re-run the carry systems as measure_carry.py (same calls), keeping each entry's source_sids (global) so
that entries can be graded at sentence granularity.  usage (repo root, PYTHONPATH=.):
rerun_carry.py CORPUS COMBOS OUTPREFIX PO [KINDS=intra2]"""
import json, os, sys, time
sys.path.insert(0, os.getcwd())
from verantyx.line3 import carry as C              # noqa: E402
from verantyx.line3 import carry_query as CQ       # noqa: E402
from verantyx.line3 import placement as pl         # noqa: E402
from verantyx.line3 import space as sp             # noqa: E402

CORPUS, COMBOS, OUTP, po = sys.argv[1:5]
kinds = sys.argv[5] if len(sys.argv) > 5 else "intra2"
DATA = {"fulllead": "experiments/line3/bank2/data/fulllead_sents.jsonl", "s3000": "experiments/line3/data/S3000.jsonl"}[CORPUS]
BANK = "experiments/line3/bank2/bank2.tsv"
rows = [json.loads(l) for l in open(DATA, encoding="utf-8")]
space = sp.build_space(rows)
ts = space.tiers["RUN"]
t0 = time.process_time()
tw = C.build_tower("RUN", ts, list(range(len(rows))), pl.budget_level("low"), unit_filter="default",
                   **({} if po == "close" else {"pack_overflow": po}))
print("tower built %.0f s cpu" % (time.process_time() - t0), file=sys.stderr, flush=True)
qs = [l.rstrip("\n").split("\t") for l in open(BANK, encoding="utf-8") if not l.startswith("#") and l.strip()]
qs = [r for r in qs if r[2] == CORPUS and r[1] in kinds.split(",")]
for combo in COMBOS.split(","):
    preset, fb = combo.split(":")
    out = "%s_%s_%s_%s.jsonl" % (OUTP, po, "index" if fb == "index" else "path", preset)
    with open(out, "w", encoding="utf-8") as f:
        for r in qs:
            qid, kind, _c, subj, question, gold = r[:6]
            a = CQ.ask(tw, question, tier_space=ts, fallback=None if fb == "none" else fb, effort=preset)
            o = a.answer_obj()
            f.write(json.dumps({"id": qid, "kind": kind, "gold": gold, "verdict": a.verdict, "ms": a.ms,
                                "entries": [{"words": e["words"], "sids": e["source_sids"]} for e in o["entries"]]},
                               ensure_ascii=False, sort_keys=True) + "\n")
    print("done", combo, file=sys.stderr, flush=True)
