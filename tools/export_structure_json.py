#!/usr/bin/env python
"""Export the REAL built line-3 structure as one compact JSON for the 3D overview page (docs/LINE3_STRUCTURE_OVERVIEW.md).

Reads only built data: the corpus (JSONL), the placement caches (`line3 build`: placements_*_{RUN,WORD,CHAR}_<level>*.pkl) and the
window cache (`line3 build --structure slide|combined`: slidewin_*.pkl).  Nothing is placed here except the optional layer-1
crosses (matryoshka: an upper cross packing the stable states of lower crosses), which are built from the loaded placements with
the library's own `LayerStack.layer1("same", ...)` / `Layer.cross_for` at the `fast` layer bounds.

  PYTHONPATH=. PYTHONHASHSEED=0 python tools/export_structure_json.py --data experiments/line3/data/S300.jsonl \
      --cache DIR --out structure.json --level mid --layers on \
      [--windows-data experiments/line3/bank2/data/fulllead_sents.jsonl --windows-cache DIR2 --windows-level low]

Everything numeric from the data side is an int or an exact fraction string "p/q" (no float).  See the "meta" block of the output
for what was truncated or sampled.  This script does not write anywhere but --out and never modifies a cache.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import signal
import subprocess
import sys
import time
from fractions import Fraction

from verantyx.line3 import ask as A
from verantyx.line3 import grammar as gr
from verantyx.line3 import matryoshka as M
from verantyx.line3 import slide_query as SQ
from verantyx.line3 import space as sp

ARMS = ("+x", "-x", "+y", "-y", "+z", "-z")
SEAT_CAP = 12            # seats kept per arm (nearest the centre first); the true count is kept in "n"
SID_CAP = 8              # sentence ids kept per cross; the true count is kept in "ns"
BIG = 10 ** 12           # an int above this is written as a string (JS numbers are exact only to 2**53)


def fs(x):
    return None if x is None else "%d/%d" % (x.numerator, x.denominator)


def num(n):
    return n if n < BIG else str(n)


def git_rev():
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return None


def articles_of(rows):
    """consecutive rows with the same title are one article (slide.py L-520)."""
    n, last = 0, object()
    for r in rows:
        if r.get("title") != last:
            n += 1
            last = r.get("title")
    return n


def detect_options(cache, level, gi, order, oc):
    """The cache file name carries the placement options; with --group-insert auto, take what is on disk."""
    if gi != "auto":
        return gi, order, oc
    for pat, o in (("*_RUN_%s.pkl" % level, ("whole", "forward", "stop")),
                   ("*_RUN_%s_ordered-forward.pkl" % level, ("ordered", "forward", "stop")),
                   ("*_RUN_%s_ordered-reverse.pkl" % level, ("ordered", "reverse", "stop")),
                   ("*_RUN_%s_ordered-forward-skip.pkl" % level, ("ordered", "forward", "skip"))):
        if glob.glob(os.path.join(cache, "placements_" + pat)):
            return o
    return "whole", "forward", "stop"


def cross_row(tier, i, seed, p, ts, records):
    arms = [[c for c in reversed(a) if c is not None] for a in p.cross.arms]      # nearest the centre first
    n = [len(a) for a in arms]
    sids = ts.postings.get(p.cross.center, ())
    tw = sum(len(t) - 1 for t in p.twin_sets)
    row = {"id": "%s%d" % (tier[0], i), "seed": seed, "centre": p.cross.center, "n": n, "arms": [a[:SEAT_CAP] for a in arms],
           "size": p.size, "cand": p.candidates, "stability": fs(Fraction(p.size, p.candidates + 1)),
           "stop": p.stop, "tied": p.class_size, "exp": num(p.expanded_size), "twins": tw, "L": p.L,
           "ns": len(sids), "sids": list(sids[:SID_CAP])}
    if len(p.centres) > 1:
        row["centres"] = list(p.centres[:4])
    if records is not None and tier in records.tiers():
        k = records.kind(tier, p.cross.center)
        row["kind"] = [k.label, list(k.particles), k.count]
    return row


def export_tiers(ix, records, meta):
    out = {}
    index_of = {}
    for t in ix.tiers:
        ts = ix.space.tiers[t]
        placements = ix.stores[t]._loaded
        if not placements:
            raise SystemExit("export: no placement cache loaded for %s (cache dir / level / options do not match)" % t)
        rows, idx = [], {}
        for i, seed in enumerate(sorted(placements)):
            rows.append(cross_row(t, i, seed, placements[seed], ts, records))
            idx[seed] = rows[-1]["id"]
        out[t] = {"units": len(ts.units()), "crosses": rows}
        index_of[t] = idx
        meta["truncated"][t] = {"arms_capped_at": SEAT_CAP, "crosses_with_a_capped_arm": sum(1 for r in rows if any(x > SEAT_CAP for x in r["n"])),
                                "crosses_with_sids_capped": sum(1 for r in rows if r["ns"] > SID_CAP)}
    return out, index_of


def _lazy_expand_flats(members, L, twin_sets):
    """placement.expand_flats with the SAME arrangements in the SAME order, but lazy: the original hands every permutation of a twin set to
    itertools.product, which materialises them all (k! tuples) before the first arrangement is produced; build_cross only takes the first one
    (`next(expand_flats(state[:1], ...))`), so an upper cross with a big twin set can run for minutes.  Used only while this exporter builds layer 1."""
    import itertools
    from verantyx.line3.placement import canon
    units = {t[0]: tuple(t) for t in twin_sets}

    def rec(fns, i):
        if i == len(fns):
            yield ()
            return
        for p in fns[i]():
            for rest in rec(fns, i + 1):
                yield (p,) + rest
    for f in members:
        pos = {}
        for i, x in enumerate(f):
            if x in units:
                pos.setdefault(x, []).append(i)
        labels = sorted(pos)
        for combo in rec([(lambda l=l: itertools.permutations(units[l])) for l in labels], 0):
            g = list(f)
            for l, perm in zip(labels, combo):
                for i, u in zip(pos[l], perm):
                    g[i] = u
            yield canon(tuple(g), L)


class _Slow(BaseException):
    pass


def _alarm(signum, frame):
    raise _Slow()


def export_layers(ix, index_of, tiers, per_tier_export, time_cap, sample, per_cross_cap, meta, log):
    signal.signal(signal.SIGALRM, _alarm)
    from verantyx.line3 import placement as PL
    PL.expand_flats = _lazy_expand_flats
    """Layer 1 = the matryoshka layer over EVERY stable state of the tier ("same" granularity), one upper cross per seed
    (library defaults: fast bounds, candidate = stable-seats-path reads these crosses, here only their seats are exported)."""
    bounds = M.LAYER_EFFORTS["fast"]
    layers, stats = [], {}
    for t in tiers:
        stack = M.stack_of(ix, t)
        lay = stack.layer1("same", [], bounds)
        loaded = ix.stores[t]._loaded
        allseeds = sorted(loaded)
        stride = 1 if not sample or len(allseeds) <= sample else -(-len(allseeds) // sample)
        seeds = allseeds[::stride]
        t0 = time.time()
        built, hist, stops, kept, slow = 0, {}, {}, [], []
        for s in seeds:
            if time.time() - t0 > time_cap:
                break
            signal.setitimer(signal.ITIMER_REAL, per_cross_cap)      # one upper cross can take minutes on a big bundle space: skip it, count it
            try:
                up = lay.cross_for(M.bundle_id(1, s))
            except _Slow:
                slow.append(s)
                continue
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0)
            built += 1
            hist[up.size] = hist.get(up.size, 0) + 1
            stops[up.stop] = stops.get(up.stop, 0) + 1
            if up.size >= 2:
                kept.append((s, up))
        log("layer1 %s: %d/%d upper crosses built in %.1fs, %d pack >= 2 lower crosses" % (t, built, len(seeds), time.time() - t0, len(kept)))
        # the nests that are shown: an even spread over the ranking by number of members (ties by seed, a label order), per tier
        kept.sort(key=lambda su: (-su[1].size, su[0]))
        step = max(1, -(-len(kept) // per_tier_export)) if per_tier_export else 1
        shown = kept[::step][:per_tier_export]
        for s, up in shown:
            members = [b[len("⟦1:"):-1] if b.startswith("⟦1:") else b for b in M.placed_units(up)]
            arms = [[(c[len("⟦1:"):-1] if c is not None else None) for c in reversed(a)] for a in up.cross.arms]
            arms = [[index_of[t].get(c, c) for c in a if c is not None] for a in arms]
            centre_seed = up.cross.center[len("⟦1:"):-1]
            layers.append({
                "id": "L1:%s:%s" % (t[0], s), "tier": t, "level": 1, "seed": s,
                "centre": index_of[t].get(centre_seed, centre_seed), "centre_word": centre_seed,
                "arms": [a[:SEAT_CAP] for a in arms], "n": [len(a) for a in arms],
                "members": [index_of[t][m] for m in members if m in index_of[t]], "n_members": len(members),
                "words_under": len(lay.words[M.bundle_id(1, s)]),
                "size": up.size, "cand": up.candidates, "stability": fs(Fraction(up.size, up.candidates + 1)),
                "stop": up.stop, "tied": up.class_size, "exp": num(up.expanded_size), "twins": sum(len(x) - 1 for x in up.twin_sets)})
        stats[t] = {"bundles": lay.n_bundles(), "upper_crosses_built": built, "seeds": len(allseeds), "stride": stride, "skipped_slow": len(slow), "skipped_slow_seeds": slow[:10],
                    "size_histogram": {str(k): hist[k] for k in sorted(hist)}, "stop_histogram": stops,
                    "packing_two_or_more": len(kept), "exported": len(shown)}
    meta["layers"] = {"granularity": "same", "bounds": bounds.to_json_obj(), "time_cap_s_per_tier": time_cap, "per_cross_cap_s": per_cross_cap, "sample_per_tier": sample, "sampling": "an even stride over the seeds in code-point order (the bundle space is always the whole tier)",
                      "exported_per_tier_cap": per_tier_export,
                      "selection": "per tier the upper crosses that pack >= 2 lower crosses, ranked by members (ties by seed code-point order), an even spread of them over that ranking (largest first)",
                      "stats": stats}
    return layers


def window_rows(wi, space, label):
    out = []
    for w in wi.windows:
        d = w.doc
        win = d["window"]
        sids = list(win["sids"])
        seats = [[r["arm"], r["depth"], r["unit"], r["side"], r["sid"]] for r in d["seats"]]
        row = {"id": "%s%d" % (label[0].upper(), win["n"]), "set": label, "n": win["n"], "article": win["title"], "sid_a": sids[0],
               "sid_b": sids[1] if len(sids) > 1 else None, "constructed": bool(win["constructed"]),
               "centres": list(d["centres"][:3]), "centre_sentence": d.get("centre_sentence", "this"), "L": d["L"],
               "class": d["class_size"], "stable": bool(d.get("stable_strict", True)), "improving": d["improving_moves_left"],
               "axis_key": d["axis_keys"], "evidence": d["axis_evidence"], "seats": seats,
               "stop": d.get("stop"), "kind": [w.kind.label, list(w.kind.particles), w.kind.count],
               "text_a": space.sentences[sids[0]][0][:80], "text_b": space.sentences[sids[1]][0][:80] if len(sids) > 1 else None}
        out.append(row)
    return out


def export_windows(args, ix, meta, log):
    wins = []
    meta["windows"] = {}
    try:
        wi = SQ.WindowIndex.from_space(ix.space, args.windows_cache or args.cache, level=args.level, build=False, z_deep=args.z_deep)
    except (ValueError, OSError) as e:           # e.g. S300: "source is not 'title#i'" (its rows are not article sentences), or no window cache
        meta["windows"]["corpus"] = {"windows": 0, "unavailable": str(e)[:200]}
        log("windows of the corpus: %s" % str(e)[:200])
    else:
        ws = window_rows(wi, ix.space, os.path.splitext(os.path.basename(args.data))[0])
        wins += ws
        meta["windows"]["corpus"] = {"windows": len(ws), "with_real_next_sentence": sum(1 for r in ws if r["sid_b"] is not None),
                                     "place_spec_sha256": wi.spec.sha256(), "slide_spec_sha256": wi.slide.spec.sha256()}
    if args.windows_data:
        if not args.windows_cache:
            raise SystemExit('--windows-data needs --windows-cache')
        rows = sp.load_jsonl(args.windows_data)
        space = sp.build_space(rows)
        w2 = SQ.WindowIndex.from_space(space, args.windows_cache, level=args.windows_level, build=False, z_deep=args.z_deep)
        label = "pairs"
        r2 = window_rows(w2, space, label)
        wins += r2
        meta["windows"]["pairs_sample"] = {"data": args.windows_data, "sentences": space.N, "articles": articles_of(rows), "windows": len(r2),
                                          "with_real_next_sentence": sum(1 for r in r2 if r["sid_b"] is not None),
                                          "place_spec_sha256": w2.spec.sha256(), "level": args.windows_level}
    return wins


def export_grammar(records, ix, tiers_out):
    parts = []
    for rank, p in enumerate(gr.LADDER, 1):
        arm = "centre" if p == gr.CENTRE_PARTICLE else ARMS[gr.ARM_PARTICLES.index(p)]
        parts.append({"p": p, "rank": rank, "weight": fs(gr.WEIGHTS[p]), "arm": arm,
                      "totals": {t: records.particle_totals(t)[p] for t in records.tiers()}})
    kinds = {}
    for t in records.tiers():
        d = {}
        for u in records.units(t):
            k = records.kind(t, u)
            key = k.label + (":" + "".join(k.particles) if k.label != "none" else "")
            d[key] = d.get(key, 0) + 1
        kinds[t] = {"distribution": d, "attachments": records.n_attachments(t), "follow": records.follow.get(t, {})}
    attach = {t: records.n_attachments(t) for t in records.tiers()}
    crosses_kind = {}
    for t, o in tiers_out.items():
        c = {}
        for r in o["crosses"]:
            if "kind" in r:
                k = r["kind"][0] + (":" + "".join(r["kind"][1]) if r["kind"][0] != "none" else "")
                c[k] = c.get(k, 0) + 1
        if c:
            crosses_kind[t] = c
    return {"particles": parts, "foundation_sha256": gr.foundation_sha(), "attachments": attach, "unit_kinds": kinds,
            "kinds_of_crosses": crosses_kind, "chars_have_no_records": "CHAR" not in records.tiers()}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--level", default="mid", choices=["low", "mid-low", "mid", "high", "max"])
    ap.add_argument("--tiers", default="RUN,WORD,CHAR")
    ap.add_argument("--group-insert", dest="group_insert", default="auto", choices=["auto", "whole", "ordered"])
    ap.add_argument("--order", default="forward", choices=["forward", "reverse"])
    ap.add_argument("--on-collapse", dest="on_collapse", default="stop", choices=["stop", "skip"])
    ap.add_argument("--z-deep", dest="z_deep", default="order", choices=["slide", "order"])
    ap.add_argument("--layers", default="off", choices=["on", "off"])
    ap.add_argument("--layers-per-tier", type=int, default=12, help="upper crosses exported per tier (an even spread over the ranking by members)")
    ap.add_argument("--layers-sample", type=int, default=600, help="upper crosses built per tier: an even stride over the seeds in code-point order (0 = every seed)")
    ap.add_argument("--layers-cross-cap", type=float, default=6.0, help="seconds one upper cross may take before its seed is skipped and counted")
    ap.add_argument("--layers-time-cap", type=float, default=900.0, help="seconds per tier spent building upper crosses (the rest is counted, not built)")
    ap.add_argument("--windows", default="on", choices=["on", "off"])
    ap.add_argument("--windows-data", help="a multi-sentence corpus whose window cache gives the real N / N+1 pairs (S300 has one sentence per article)")
    ap.add_argument("--windows-cache", help="directory of the slidewin_*.pkl of --data (default: --cache), or of --windows-data")
    ap.add_argument("--windows-level", default="low", choices=["low", "mid-low", "mid", "high", "max"])
    ap.add_argument("--carry-json", help="a committed carry measurement (experiments/line3/carry/c3b/results/*.json), exported as it is")
    a = ap.parse_args(argv)
    log = lambda m: print(m, file=sys.stderr)

    gi, order, oc = detect_options(a.cache, a.level, a.group_insert, a.order, a.on_collapse)
    tiers = A.parse_tiers(a.tiers)
    ix = A.Index.from_jsonl(a.data, a.cache, a.level, tiers, group_insert=gi, order=order, on_collapse=oc)
    rows = sp.load_jsonl(a.data)
    meta = {"generator": "tools/export_structure_json.py", "code_rev": git_rev(), "data": a.data, "corpus_sha256": ix.space.sha256(),
            "level": a.level, "placement_options": {"group_insert": gi, "order": order, "on_collapse": oc}, "truncated": {},
            "stability_note": ("The per-cross stability 'inv' of the line-3 design (cycle.EndState.inv, L-103) is a QUERY-TIME quantity "
                               "and is not stored in a build.  Here 'stability' is the exact fill of the stable state, placed units / (candidate units + the seed) (p/q), with 'stop' (exhausted = every candidate placed; budget = the step that broke was restored away; "
                               "max_groups) and 'tied' (arrangements in the tied class).  Windows carry the recorded per-axis judgement."),
            "arms": list(ARMS), "arm_order": "nearest the centre first", "seat_cap_per_arm": SEAT_CAP, "sid_cap_per_cross": SID_CAP}
    texts = {}
    tiers_out, index_of = export_tiers(ix, None, meta)
    records = gr.records_of_space(ix.space)
    for t, o in tiers_out.items():                              # kinds: the grammar layer decides the read order of the RUN / WORD crosses
        if t in records.tiers():
            for r in o["crosses"]:
                k = records.kind(t, r["centre"])
                r["kind"] = [k.label, list(k.particles), k.count]
    used = {sid for o in tiers_out.values() for r in o["crosses"] for sid in r["sids"]}
    texts = {str(s): ix.space.sentences[s][0][:80] for s in sorted(used)}
    doc = {"meta": meta,
           "corpus": {"n_sentences": ix.space.N, "articles": articles_of(rows), "tier_units": {t: len(ix.space.tiers[t].units()) for t in tiers},
                      "sentences": texts},
           "tiers": tiers_out, "layers": [], "windows": [], "grammar": export_grammar(records, ix, tiers_out), "carry": None}
    if a.layers == "on":
        doc["layers"] = export_layers(ix, index_of, tiers, a.layers_per_tier, a.layers_time_cap, a.layers_sample, a.layers_cross_cap, meta, log)
    if a.windows == "on":
        doc["windows"] = export_windows(a, ix, meta, log)
    if a.carry_json:
        with open(a.carry_json, encoding="utf-8") as f:
            doc["carry"] = {"source": a.carry_json, "kind": "measurement of CarryTower (stream of sentences -> blacks -> packs -> levels)", "data": json.load(f)}
    s = json.dumps(doc, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    meta["bytes"] = len(s.encode("utf-8"))
    s = json.dumps(doc, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(s)
    log("wrote %s: %d bytes; crosses %s; layers %d; windows %d" % (
        a.out, len(s.encode("utf-8")), {t: len(o["crosses"]) for t, o in tiers_out.items()}, len(doc["layers"]), len(doc["windows"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
