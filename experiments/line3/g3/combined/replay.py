"""G3-g: replay adapters.  A recorded result of a source -> combined.Source, so that the combiner (verantyx.line3.combined.combine) can be run on
records: T10's raw per-question records (flat cross = `layer0`, layers = `on.seatsPath`) and measure_windows.py's window records.
A replayed flat / layers candidate holds what T10 recorded (words, centres, stability, arrangement count; for the layers the run's trace flag): no source
sentences, no per-word sentences."""
import os, sys
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import combined as CB   # noqa: E402

TIERS = ("RUN", "WORD", "CHAR")


def frac(s):
    return None if s is None else Fraction(int(s.split("/")[0]), int(s.split("/")[1]))


def flat_src(rec):
    cands, abst, read = [], [], {}
    for t in TIERS:
        d = rec["layer0"].get(t)
        if d is None:
            continue
        read[t] = d["read"]
        if not d["entries"]:
            abst.append({"tier": t, "kind": d["verdict"]})
        for e in d["entries"]:
            cands.append(CB.Cand(CB.flat_origin(t), tuple(e["words"]), tuple(e["centres"]), frac(e["stability"]), e["count"]))
    partial = any(v["left_unread"] > 0 for v in read.values())
    return CB.Source(CB.FLAT, rec["verdict0"], tuple(cands), tuple(abst), {"per_tier": read, "partial": partial})


def layers_src(rec, cfg="seatsPath"):
    cands, abst = [], []
    partial = False
    for t in TIERS:
        d = rec["on"][cfg]["tiers"].get(t)
        if d is None:
            continue
        for run in d["runs"]:
            partial = partial or bool(run["partial"])
            if not run["entries"]:
                abst.append({"tier": t, "layer": run["k"], "variant": "A", "kind": run["verdict"]})
            for e in run["entries"]:
                cands.append(CB.Cand(CB.layer_origin(t, run["k"], "A"), tuple(e["words"]), trace_ok=bool(run["trace_ok"])))
    triggered = any(d["triggered"] for d in rec["on"][cfg]["tiers"].values())
    if cands:
        verdict = CB.ANSWER if len(cands) == 1 else CB.CHOICE
    elif not triggered:
        verdict = CB.NOT_STACKED                                       # as combined.layers_source: no layer was stacked
    else:
        verdict = next((run["verdict"] for t in TIERS if t in rec["on"][cfg]["tiers"] for run in rec["on"][cfg]["tiers"][t]["runs"]), CB.UNKNOWN_NO_STATE)
    return CB.Source(CB.LAYERS, verdict, tuple(cands), tuple(abst), {"partial": partial})


def win_src(wr, ev):
    return CB.window_source_of(ev, wr["entries"], wr["abstentions"], wr["verdict"], wr["read"],
                               [tuple(x) for x in wr["reads_trace"]])


