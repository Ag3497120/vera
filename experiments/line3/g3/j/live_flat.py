"""G3-j: the flat cross (layer 0, 3 tiers) LIVE for the questions whose gold is not one unit of any tier (T9 audit tokenisation.jsonl), with each entry's
`source_sids`, which the T10 records do not keep (measure_ask._ent writes words / centres / count / stability only).  Same index, same placement cache
and same options as T10 (fulllead, cache f1b, group_insert ordered, order forward, on_collapse stop), flat only (no layers).
usage: PYTHONPATH=. PYTHONHASHSEED=0 python live_flat.py PRESET OUT.jsonl [--workers 2] [--resume]"""
import argparse, json, multiprocessing as mp, os, sys, time, traceback
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import ask as A   # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("preset"); ap.add_argument("out")
ap.add_argument("--workers", type=int, default=2); ap.add_argument("--resume", action="store_true")
ap.add_argument("--cache", default="/Users/motonisihikoudai/Projects/vera-impl/cache/f1b")
ARGS = ap.parse_args()
DATA = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
BANK = os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv")
TOK = os.path.join(ROOT, "experiments/line3/t9/audit/tokenisation.jsonl")
G = {}


def non_unit_ids():
    tok = [json.loads(l) for l in open(TOK, encoding="utf-8")]
    return [r["id"] for r in tok if not any(r[t]["one_unit"] for t in ("RUN", "WORD", "CHAR"))]


def work(row):
    try:
        t0 = time.monotonic()
        c = A.ask(G["idx"], row[4], effort=ARGS.preset)
        return {"id": row[0], "gold": row[5], "preset": ARGS.preset, "verdict0": c.verdict, "ms": int((time.monotonic() - t0) * 1000),
                "layer0": {o.tier: {"verdict": o.verdict, "read": o.read_counts,
                                    "entries": [{"words": list(e.words), "centres": list(e.centres), "count": e.count, "stability": A._fs(e.stability),
                                                 "sids": list(e.source_sids)} for e in o.entries]} for o in c.outcomes}}
    except Exception:
        return {"id": row[0], "error": traceback.format_exc()}


if __name__ == "__main__":
    ids = non_unit_ids()
    rows = [l.rstrip("\n").split("\t") for l in open(BANK, encoding="utf-8") if not l.startswith("#") and l.strip()]
    rows = [r for r in rows if r[2] == "fulllead" and r[0] in ids]
    assert len(rows) == len(ids) == 18, (len(rows), len(ids))
    done = []
    if ARGS.resume and os.path.exists(ARGS.out):
        for l in open(ARGS.out, encoding="utf-8"):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if "error" not in r and r.get("preset") == ARGS.preset:
                done.append(r)
    have = {r["id"] for r in done}
    todo = [r for r in rows if r[0] not in have]
    G["idx"] = A.Index.from_jsonl(DATA, ARGS.cache, A.DEFAULT_LEVEL, A.TIERS, group_insert="ordered", order="forward")
    short = {t: (len(G["idx"].stores[t]._loaded), len(G["idx"].space.tiers[t].units())) for t in G["idx"].tiers}
    assert all(a == b for a, b in short.values()), short
    with open(ARGS.out, "w", encoding="utf-8") as f:
        for r in done:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    it = map(work, todo) if ARGS.workers <= 1 else mp.get_context("fork").Pool(ARGS.workers).imap_unordered(work, todo)
    with open(ARGS.out, "a", encoding="utf-8") as f:
        for n, r in enumerate(it, 1):
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n"); f.flush()
            print(n, len(todo), r["id"], r.get("ms", r.get("error", "")[-200:]), flush=True)
