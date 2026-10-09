"""F1b timing probe: 5 bank2 intra2 questions on fulllead_sents under group_insert="ordered" (order forward), fast and standard,
layers off (A.ask) and layers default (M.ask_layered, options=None = variant A / compress / path words).
usage: PYTHONHASHSEED=0 probe.py CACHE_DIR [IDS=I2-014,I2-029,I2-011,I2-031,I2-001] [GI=ordered] -> probe_<GI>.jsonl (one line per question x preset)
CACHE_DIR = the ordered placement cache that build_cache.sh wrote (the question path reads every cross of a tier: cycle.plan_read, so the
layer-0 crosses must all exist; with no cache the first question builds the whole tier on demand: > 900 s for RUN alone, see the log).
For every (question, preset) the index's upper-layer stacks are emptied (`cold`: the layer-1 / upper crosses this question needs are built
now, on demand), then the same question is asked again (`warm`: read only).  One process, no workers.  Candidates are graded with t9/scorer.py's rule
(gold alternative inside one normalised word of one entry) over layer-0 entries (flat) and layer-0 + upper entries (layers)."""
import json, os, signal, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "experiments/line3/t9"))
from verantyx.line3 import ask as A            # noqa: E402
from verantyx.line3 import matryoshka as M     # noqa: E402
from verantyx.line3.space import build_space, load_jsonl   # noqa: E402
import scorer as S                             # noqa: E402

CACHE = sys.argv[1]
IDS = (sys.argv[2] if len(sys.argv) > 2 else "I2-014,I2-029,I2-011,I2-031,I2-001").split(",")
GI = sys.argv[3] if len(sys.argv) > 3 else "ordered"
DATA = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
BANK = os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv")
rows = {r[0]: r for r in (l.rstrip("\n").split("\t") for l in open(BANK, encoding="utf-8") if not l.startswith("#") and l.strip())}


def hits(gold, words_lists):
    return [n for n, w in enumerate(words_lists, 1) if S.hits_words(gold, w)]


CAP = int(os.environ.get("F1B_CAP", "900"))          # seconds allowed for ONE stage (layer 0, or the layers on top of it); beyond it the stage is recorded as "timeout"


class _Cap(Exception):
    pass


def _alarm(*_):
    raise _Cap()


def stage(fn):
    """-> (seconds, result or None, timed_out)"""
    signal.signal(signal.SIGALRM, _alarm)
    signal.alarm(CAP)
    t0 = time.monotonic()
    try:
        r, to = fn(), False
    except _Cap:
        r, to = None, True
    finally:
        signal.alarm(0)
    return round(time.monotonic() - t0, 2), r, to


def run(idx, question, preset, tag):
    off_s, c0, to0 = stage(lambda: A.ask(idx, question, effort=preset))
    print("   %s layer0 %s %.1fs builds %s" % (tag, "TIMEOUT" if to0 else "ok", off_s,
          {t: idx.stores[t].on_demand for t in idx.tiers}), flush=True)
    out = {"off_s": off_s, "off_timeout": to0, "on_extra_s": None, "on_s": None, "on_timeout": None, "flat": [], "up": [], "flat_n": None,
           "layers_n": None, "crosses_read": None, "stacked": None, "verdict": None}
    if to0:
        return out
    flat = [list(e.words) for _, e in c0.all_entries]
    out.update(flat=flat, flat_n=len(flat), crosses_read={o.tier: o.read_counts["crosses_read"] for o in c0.outcomes}, verdict=c0.verdict)
    on_s, cl, to1 = stage(lambda: M.ask_layered(idx, question, effort=preset, base=c0))
    print("   %s layers %s %.1fs" % (tag, "TIMEOUT" if to1 else "ok", on_s), flush=True)
    out.update(on_extra_s=on_s, on_timeout=to1)
    if not to1:
        up = [list(x.to_json_obj()["words"]) for tl in cl.layers for x in tl.entries]
        out.update(up=up, on_s=round(off_s + on_s, 2), layers_n=len(flat) + len(up), stacked=cl.stacked)
    return out


if __name__ == "__main__":
    t0 = time.monotonic()
    idx = A.Index.from_jsonl(DATA, CACHE, A.DEFAULT_LEVEL, A.TIERS, group_insert=GI)
    assert all(len(idx.stores[t]._loaded) == len(idx.space.tiers[t].units()) for t in idx.tiers), "the cache is incomplete"
    print("index + cache load %.1fs" % (time.monotonic() - t0), flush=True)
    out = open(os.path.join(HERE, "probe_%s%s.jsonl" % (GI, os.environ.get("F1B_TAG", ""))), "w", encoding="utf-8")   # F1B_TAG: parallel runs of different questions
    for qid in IDS:
        _id, kind, _c, subj, question, gold = rows[qid][:6]
        for preset in ("fast", "standard"):
            idx._t8_stacks = {}                                  # cold for the upper layers
            cold = run(idx, question, preset, "cold")
            built = {t: idx.stores[t].on_demand for t in idx.tiers}   # cumulative, 0 with a full cache
            layer_builds = {t: sum(l.builds for l in M.stack_of(idx, t)._layer1.values()) for t in idx.tiers}
            clean = not cold["off_timeout"] and not cold["on_timeout"]
            warm = run(idx, question, preset, "warm") if clean and not os.environ.get("F1B_NOWARM") else None   # layer 0 is re-read in full on every ask (no read cache), so warm only shows the upper-layer builds
            rec = {"id": qid, "preset": preset, "gi": GI, "question": question, "gold": gold, "cap_s": CAP,
                   "layer0_built_on_demand": built, "layer1_crosses_built": layer_builds, "load1": os.getloadavg()[0]}
            for nm, r in (("cold", cold), ("warm", warm)):
                if r is None:
                    continue
                rec[nm] = {k: v for k, v in r.items() if k not in ("flat", "up")}
                rec[nm]["hit_flat"] = hits(gold, r["flat"])
                rec[nm]["hit_layers"] = hits(gold, r["flat"] + r["up"]) if r["on_s"] is not None else None
            if warm is not None:
                assert cold["flat"] == warm["flat"] and cold["up"] == warm["up"]      # the cache never changes a result
            out.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"); out.flush()
            print(qid, preset, json.dumps({k: v for k, v in rec.items() if k not in ("question", "gold")}, ensure_ascii=False, sort_keys=True), flush=True)
