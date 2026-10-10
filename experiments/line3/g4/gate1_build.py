"""Gate G-1 preparation (docs/LINE3_G4_GROWTH_METER.md 9 ticket 3, L-G4-31): build the crosses of the three tiers of fulllead with the foundation ON into
a cache directory with N workers, and print, per tier, the counts next to the foundation-OFF numbers.

  python experiments/line3/g4/gate1_build.py --cache DIR [--workers 2] [--level mid] [--limit-sentences K] [--tiers RUN,WORD,CHAR]
                                             [--off-cache /Users/motonisihikoudai/Projects/vera-impl/cache/f1b] [--no-off] [--verify N]

What it does
  * data = experiments/line3/bank2/data/fulllead_sents.jsonl (all 592 sentences) or, with --limit-sentences K, its first K lines (an exact leading
    byte slice, written to DIR/prefix_K.jsonl; its sha256 is the data sha of the caches).  The same options as the F1b caches: group_insert=ordered,
    order=forward, on_collapse=stop, quotient on, level mid (as `line3 build --group-insert ordered`).
  * ON: foundation.adhesions_of_space(space) (the adhesion of each tier from the corpus), then placement.build_cross(foundation="on", adhesion=...) for
    every unit of every tier; written to DIR/placements_<sha12>_<TIER>_<level>_ordered-forward_found-<seats12>.pkl.  The format name differs from
    the plain caches (line3.placements.foundation.v1), so a loader that does not know the foundation refuses the file instead of reading it as plain.
  * OFF: with --limit-sentences the same prefix is built without the foundation in the same run (the f1b cache is for the full data and cannot be loaded for a
    prefix) and written beside it; for the full corpus the OFF numbers are read from --off-cache (the existing f1b caches, never rebuilt).  The full-corpus
    numbers of --off-cache are also printed in prefix mode, for reference.
  * Counts per tier: crosses; closed by stop (Placement.stop == "budget": the cross stopped at its first collapse, L-463) and, of those, by reason
    (max_class / max_states / max_moves); exhausted; mean and median tied class size (arrangements held as one state, len(members)); median size (units
    seated, the six particles not counted); for ON beside OFF on the same data: crosses whose contracted (n, p) differs from OFF, crosses whose size differs.
  * Size at closure (review fix, L-G4-46): median / mean units seated at the stop of the crosses that stopped by the budget (and of all crosses), the number of
    crosses budget-stopped in BOTH ON and OFF and, of those, how many ON stops smaller (and their median sizes), and the number of classes that hold more than
    max_class arrangements (`class_over_max`: the final held class; `first_class_over_max`: the placement's counter, L-G4-47 -- the search never checks the first
    class built from the terminal arrangements against max_class; counted here, not changed).  A cache written before the counter existed is read by deriving the
    count from the kept steps (flagged "derived").
  * --verify N|all: an independent re-check (placement.verify_class_foundation, with the Placement's stored key as `expected`) of ALL classes (`all`) or of a
    deterministic sample: the N largest classes plus N evenly spaced ones over the seed-sorted crosses (default 20 + 20).  Quotient classes with twins are
    checked at the label level.  --verify-workers (default = --workers, at most 4) runs the checks in a pool.
  * Cost: CPU seconds of the builds (sum of per-seed seconds), ON beside OFF, and the full-corpus estimate = the OFF CPU seconds of the f1b caches times
    the ON/OFF ratio measured here.  A prefix ratio is NOT a measurement of the full corpus (small crosses are cheap, ties multiply with size); the
    estimate is printed with that warning.
Never opens vera-impl/hidden.  No network.  Python 3.11+, PYTHONHASHSEED=0 for the recorded runs.
"""
import argparse
import json
import multiprocessing as mp
import os
import pickle
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from verantyx.line3 import foundation as fd          # noqa: E402
from verantyx.line3 import placement as pl           # noqa: E402
from verantyx.line3 import space as sp               # noqa: E402

DATA = os.path.join(ROOT, "experiments", "line3", "bank2", "data", "fulllead_sents.jsonl")
OFF_CACHE = "/Users/motonisihikoudai/Projects/vera-impl/cache/f1b"
CACHE_FORMAT_FOUNDATION = "line3.placements.foundation.v1"
GROUP_INSERT, ORDER, ON_COLLAPSE = "ordered", "forward", "stop"

_G: dict = {}                                        # set before the fork; the children inherit it


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def _work(seeds):
    out = []
    for s in seeds:
        t0 = time.time()
        p = pl.build_cross(_G["tier"], s, _G["w"], budget=_G["budget"], group_insert=GROUP_INSERT, order=ORDER, on_collapse=ON_COLLAPSE,
                           foundation=_G["foundation"], adhesion=_G["adhesion"])
        out.append((s, p, time.time() - t0))
    return out


def build_tier(ts, level, workers, foundation, adhesion):
    """Every unit of a tier: ({seed: Placement}, {seed: secs}, wall secs)."""
    w = pl.Weights(ts, adhesion)
    _G.update(tier=ts, w=w, budget=pl.budget_level(level), foundation=foundation, adhesion=adhesion)
    units = ts.units()
    t0 = time.time()
    if workers <= 1:
        parts = [_work(units[i:i + 4]) for i in range(0, len(units), 4)]
    else:
        chunks = [units[i:i + 4] for i in range(0, len(units), 4)]
        with mp.get_context("fork").Pool(workers) as pool:
            parts = list(pool.imap_unordered(_work, chunks))
    res, secs = {}, {}
    for part in parts:
        for s, p, dt in part:
            res[s], secs[s] = p, dt
    return {s: res[s] for s in sorted(res)}, secs, time.time() - t0


def cache_file(cache, data_sha, tier, level, found):
    key = "%s-%s" % (GROUP_INSERT, ORDER) + ("_" + fd.foundation_key() if found else "")
    return os.path.join(cache, "placements_%s_%s_%s_%s.pkl" % (data_sha[:12], tier, level, key))


def save(path, tier, level, data_sha, placements, secs, wall, found, adhesion):
    rec = {"format": CACHE_FORMAT_FOUNDATION if found else "line3.placements.v1", "data_sha256": data_sha, "tier": tier, "level": level,
           "placements": dict(placements), "secs": dict(secs), "wall_s": wall, "group_insert": GROUP_INSERT, "order": ORDER}
    if found:
        rec.update({"foundation": fd.seats_sha(), "adhesion_sha256": adhesion.sha256()})
    tmp = path + ".part"
    with open(tmp, "wb") as f:
        pickle.dump(rec, f, protocol=pickle.HIGHEST_PROTOCOL)
    os.replace(tmp, path)


def median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return None
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def first_class_over_max_of(p):
    """(count, derived): the placement's own counter, or (for a cache written before it existed) the kept steps whose class held more than max_class."""
    v = vars(p).get("first_class_over_max")
    if v is not None:
        return v, False
    return sum(1 for st in p.steps if st.status == pl.STABLE and st.class_size is not None and st.class_size > p.budget.max_class), True


def _mean(xs):
    return round(sum(xs) / len(xs), 2) if xs else None


def stats(placements, secs):
    """The counts of one (variant, tier).  Means are printed as exact integer ratios rounded to 0.01 (a report, not a key)."""
    ps = list(placements.values())
    stops = [p for p in ps if p.stop == pl.BUDGET]
    reasons = {}
    for p in stops:
        r = p.broke_on.reason if p.broke_on else "?"
        reasons[r] = reasons.get(r, 0) + 1
    cls = [len(p.members) for p in ps]
    fco = [first_class_over_max_of(p) for p in ps]
    return {"crosses": len(ps), "closed_by_stop": len(stops), "by_reason": dict(sorted(reasons.items())),
            "max_class": reasons.get("max_class", 0), "exhausted": sum(1 for p in ps if p.stop == "exhausted"),
            "other_stop": sum(1 for p in ps if p.stop not in ("exhausted", pl.BUDGET)),
            "mean_class": round(sum(cls) / len(cls), 2) if cls else None, "median_class": median(cls), "max_class_size": max(cls) if cls else None,
            "median_size": median([p.size for p in ps]), "mean_size": _mean([p.size for p in ps]),
            "stop_median_size": median([p.size for p in stops]), "stop_mean_size": _mean([p.size for p in stops]),
            "median_L": median([p.L for p in ps]), "cpu_s": round(sum(secs.values()), 2) if secs else None,
            "class_over_max": sum(1 for p in ps if len(p.members) > p.budget.max_class),
            "first_class_over_max_crosses": sum(1 for v, _ in fco if v), "first_class_over_max_total": sum(v for v, _ in fco),
            "first_class_over_max_derived": any(d for _, d in fco)}


def compare(off, on):
    """ON beside OFF on the same data (G1-b acceptance: how many crosses end with another contracted (n, p)).  `np_differs` counts every cross; because
    a seated cross can stop at another size (the key is not comparable across sizes), the three `same_size*` / `both_exhausted*` counts compare only
    crosses that hold the same number of units, and `class_equal` those whose contracted class is member for member the OFF class."""
    d_np = sum(1 for s in on if on[s].score != off[s].score)
    d_size = sum(1 for s in on if on[s].size != off[s].size)
    d_stop = sum(1 for s in on if on[s].stop != off[s].stop)
    a_pos = sum(1 for s in on if on[s].a_num)
    same = [s for s in on if on[s].size == off[s].size]
    both = [s for s in on if on[s].stop == "exhausted" and off[s].stop == "exhausted"]
    bstop = [s for s in on if on[s].stop == pl.BUDGET and off[s].stop == pl.BUDGET]
    return {"contracted_np_differs": d_np, "size_differs": d_size, "stop_differs": d_stop, "a_positive": a_pos,
            "same_size": len(same), "same_size_np_differs": sum(1 for s in same if on[s].score != off[s].score),
            "same_size_class_equal": sum(1 for s in same if on[s].twin_sets == off[s].twin_sets and pl.contract_for_read(on[s]).members == off[s].members),
            "both_exhausted": len(both), "both_exhausted_np_differs": sum(1 for s in both if on[s].score != off[s].score),
            "np_lower": sum(1 for s in on if on[s].score < off[s].score), "np_higher": sum(1 for s in on if on[s].score > off[s].score),
            "same_size_np_lower": sum(1 for s in same if on[s].score < off[s].score),
            "both_budget_stopped": len(bstop), "both_stopped_on_smaller": sum(1 for s in bstop if on[s].size < off[s].size),
            "both_stopped_on_larger": sum(1 for s in bstop if on[s].size > off[s].size),
            "both_stopped_median_size_on": median([on[s].size for s in bstop]), "both_stopped_median_size_off": median([off[s].size for s in bstop]),
            "both_stopped_mean_size_on": _mean([on[s].size for s in bstop]), "both_stopped_mean_size_off": _mean([off[s].size for s in bstop])}


def load_cache(path, found, adhesion):
    """A cache this script wrote: ({seed: Placement}, {seed: secs}, wall) or None.  A foundation file is refused unless it carries this seats_sha."""
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        d = pickle.load(f)
    if found and (d.get("format") != CACHE_FORMAT_FOUNDATION or d.get("foundation") != fd.seats_sha() or d.get("adhesion_sha256") != adhesion.sha256()):
        raise ValueError("%s is not a foundation cache of this seats spec / adhesion" % path)
    return d["placements"], d["secs"], d["wall_s"]


def load_off(cache, data_sha, tier, level):
    path = os.path.join(cache, "placements_%s_%s_%s_%s-%s.pkl" % (data_sha[:12], tier, level, GROUP_INSERT, ORDER))
    if not os.path.exists(path):
        return None, None, path
    with open(path, "rb") as f:
        d = pickle.load(f)
    return d["placements"], d.get("secs"), path


def pick_verify(on, spec):
    """The seeds whose classes are re-checked: all of them (spec "all"), or the N largest classes plus N evenly spaced over the seed-sorted crosses."""
    seeds = sorted(on)
    if spec == "all":
        return seeds
    n = int(spec)
    if n <= 0:
        return []
    big = sorted(seeds, key=lambda s: (-len(on[s].members), s))[:n]
    even = [seeds[i * (len(seeds) - 1) // (n - 1)] for i in range(n)] if n > 1 and len(seeds) > 1 else seeds[:1]
    return sorted(set(big) | set(even))


def _verify_one(seed):
    p = _G["on"][seed]
    t0 = time.time()
    r = pl.verify_class_foundation(_G["ts"], [pl.to_cross(m, p.L) for m in p.members], _G["adh"], expected=tuple(p.score) + (p.a_num,))
    return seed, r.is_stable_class, r.matches_record, len(p.members), r.swaps_tested, time.time() - t0


def verify_tier(ts, adh, on, spec, workers):
    seeds = pick_verify(on, spec)
    _G.update(ts=ts, adh=adh, on=on)
    order = sorted(seeds, key=lambda s: (-len(on[s].members), s))        # biggest first: the pool stays busy
    if workers <= 1 or len(order) < 2:
        res = [_verify_one(s) for s in order]
    else:
        with mp.get_context("fork").Pool(workers) as pool:
            res = list(pool.imap_unordered(_verify_one, order))
    res.sort()
    bad = [r[0] for r in res if not r[1]]
    return {"checked": len(res), "of": len(on), "failed": bad, "key_differs_from_record": [r[0] for r in res if r[2] is False],
            "classes_checked_members": sum(r[3] for r in res), "largest_class_checked": max((r[3] for r in res), default=0),
            "with_twins": sum(1 for r in res if on[r[0]].twin_sets), "swaps_tested": sum(r[4] for r in res), "secs": round(sum(r[5] for r in res), 1)}


def row(label, st):
    return ("| %-22s | %6d | %6d | %6d | %6d | %9s | %7s | %6s | %9s |"
            % (label, st["crosses"], st["closed_by_stop"], st["max_class"], st["exhausted"], st["mean_class"], st["median_class"], st["median_size"],
               st["cpu_s"]))


def row2(label, st):
    return ("| %-22s | %6d | %7s | %7s | %7s | %7s | %8d | %9d | %6d%s |"
            % (label, st["crosses"], st["stop_median_size"], st["stop_mean_size"], st["median_size"], st["mean_size"], st["class_over_max"],
               st["first_class_over_max_crosses"], st["first_class_over_max_total"], "*" if st["first_class_over_max_derived"] else " "))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default=DATA)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--level", default="mid")
    ap.add_argument("--limit-sentences", type=int, default=0)
    ap.add_argument("--tiers", default="RUN,WORD,CHAR")
    ap.add_argument("--off-cache", default=OFF_CACHE)
    ap.add_argument("--no-off", action="store_true", help="in prefix mode, do not build the foundation-off crosses of the prefix")
    ap.add_argument("--verify", default="0", help="N = the N largest classes plus N evenly spaced ones per tier, 'all' = every class, 0 = none")
    ap.add_argument("--verify-workers", type=int, default=0, help="processes for --verify (default: --workers; at most 4)")
    ap.add_argument("--reuse", action="store_true", help="read a cache file that is already in --cache instead of building it again")
    a = ap.parse_args(argv)
    if a.verify != "all" and not a.verify.isdigit():
        raise SystemExit("--verify takes a number or 'all'")
    a.verify = a.verify if a.verify == "all" else int(a.verify)
    if a.workers > 4 or a.verify_workers > 4:
        raise SystemExit("at most 4 processes")
    tiers = [t for t in a.tiers.split(",") if t]
    for t in tiers:
        if t not in sp.TIERS:
            raise SystemExit("unknown tier %r" % t)
    os.makedirs(a.cache, exist_ok=True)
    full_sha = sha256_file(a.data)
    data_path, k = a.data, a.limit_sentences
    if k:
        with open(a.data, "rb") as f:
            lines = f.readlines()[:k]
        data_path = os.path.join(a.cache, "prefix_%d.jsonl" % k)
        with open(data_path, "wb") as f:
            f.writelines(lines)
    data_sha = sha256_file(data_path)
    rows = sp.load_jsonl(data_path)
    t0 = time.time()
    space = sp.build_space(rows)
    ads = fd.adhesions_of_space(space, tiers)
    print("data %s sentences=%d sha=%s  (full file sha %s)  seats_sha=%s" % (os.path.basename(data_path), len(rows), data_sha[:12], full_sha[:12], fd.seats_sha()[:12]))
    print("adhesion built in %.1fs: %s" % (time.time() - t0, {t: (len(ads[t].counts), len({u for u, _ in ads[t].counts})) for t in tiers}))
    report = {"data": os.path.basename(data_path), "sentences": len(rows), "data_sha256": data_sha, "seats_sha256": fd.seats_sha(), "level": a.level,
              "workers": a.workers, "tiers": {}}
    table = ["| %-22s | %6s | %6s | %6s | %6s | %9s | %7s | %6s | %9s |" % ("variant / tier", "cross", "stop", "maxcls", "exhst", "mean cls", "med cls", "med sz", "cpu s"),
             "|" + "|".join(["-" * 24] + ["-" * 8] * 4 + ["-" * 11, "-" * 9, "-" * 8, "-" * 11]) + "|"]
    table2 = ["| %-22s | %6s | %7s | %7s | %7s | %7s | %8s | %9s | %7s |" % ("size at closure", "cross", "stop med", "stop mean", "all med", "all mean", "cls>max", "1st>max x", "1st>max n"),
              "|" + "|".join(["-" * 24] + ["-" * 8, "-" * 9, "-" * 9, "-" * 9, "-" * 9, "-" * 10, "-" * 11, "-" * 9]) + "|"]
    for t in tiers:
        ts = space.tiers[t]
        got = load_cache(cache_file(a.cache, data_sha, t, a.level, True), True, ads[t]) if a.reuse else None
        if got is None:
            on, on_secs, on_wall = build_tier(ts, a.level, a.workers, "on", ads[t])
            save(cache_file(a.cache, data_sha, t, a.level, True), t, a.level, data_sha, on, on_secs, on_wall, True, ads[t])
        else:
            on, on_secs, on_wall = got
        st_on = stats(on, on_secs)
        entry = {"on": st_on, "on_wall_s": round(on_wall, 1)}
        if k and not a.no_off:
            got = load_cache(cache_file(a.cache, data_sha, t, a.level, False), False, None) if a.reuse else None
            if got is None:
                off, off_secs, off_wall = build_tier(ts, a.level, a.workers, "off", None)
                save(cache_file(a.cache, data_sha, t, a.level, False), t, a.level, data_sha, off, off_secs, off_wall, False, None)
            else:
                off, off_secs, off_wall = got
            entry["off"] = stats(off, off_secs)
            entry["off_wall_s"] = round(off_wall, 1)
            entry["on_vs_off"] = compare(off, on)
        elif not k:
            off, off_secs, path = load_off(a.off_cache, data_sha, t, a.level)
            if off is not None:
                entry["off"] = stats(off, off_secs)
                entry["off_source"] = path
                if set(off) == set(on):
                    entry["on_vs_off"] = compare(off, on)
        if k:                                                    # the full-corpus OFF numbers, for reference only
            foff, fsecs, path = load_off(a.off_cache, full_sha, t, a.level)
            if foff is not None:
                entry["off_full_corpus"] = stats(foff, fsecs)
                entry["off_full_source"] = path
        if a.verify:
            entry["verified"] = verify_tier(ts, ads[t], on, a.verify, a.verify_workers or a.workers)
        report["tiers"][t] = entry
        table.append(row("ON  %s" % t, st_on))
        table2.append(row2("ON  %s" % t, st_on))
        if "off" in entry:
            table.append(row("OFF %s%s" % (t, "" if k else " (f1b)"), entry["off"]))
            table2.append(row2("OFF %s%s" % (t, "" if k else " (f1b)"), entry["off"]))
        if "off_full_corpus" in entry:
            table.append(row("OFF %s full corpus" % t, entry["off_full_corpus"]))
            table2.append(row2("OFF %s full corpus" % t, entry["off_full_corpus"]))
        print("%s done: on wall %.1fs cpu %.1fs" % (t, on_wall, st_on["cpu_s"]), flush=True)
    print()
    print("\n".join(table))
    print()
    print("\n".join(table2))
    print("  stop med / mean = units seated (the six particles not counted) in the crosses that stopped by the budget; all = every cross; cls>max = crosses whose final held class "
          "holds more than max_class arrangements; 1st>max x / n = crosses / total kept settled classes above max_class (the first class built from the terminal arrangements "
          "is never checked against max_class, L-G4-47); * = derived from the kept steps (cache written before the counter existed)")
    print()
    for t, e in report["tiers"].items():
        if "on_vs_off" in e:
            c = e["on_vs_off"]
            print("%s final contracted (n, p) LOWER than OFF's in %d of %d crosses (higher in %d); of the %d crosses with the same size: lower in %d  [owner: the adhesion "
                  "tie-break stays at every insertion step; this is the count the gate has to read]" % (t, c["np_lower"], e["on"]["crosses"], c["np_higher"], c["same_size"],
                                                                         c["same_size_np_lower"]))
            print("%s budget-stopped in BOTH: %d; ON stops smaller in %d (larger in %d); median size at stop ON %s / OFF %s, mean ON %s / OFF %s"
                  % (t, c["both_budget_stopped"], c["both_stopped_on_smaller"], c["both_stopped_on_larger"], c["both_stopped_median_size_on"],
                     c["both_stopped_median_size_off"], c["both_stopped_mean_size_on"], c["both_stopped_mean_size_off"]))
    print()
    est = {}
    for t, e in report["tiers"].items():
        if "on_vs_off" in e:
            print("%s on vs off (same data): %s; reasons ON %s%s" % (t, e["on_vs_off"], e["on"]["by_reason"],
                                                                 " / OFF %s" % e["off"]["by_reason"] if "off" in e else ""))
        if "verified" in e:
            print("%s verify_class_foundation: %s" % (t, e["verified"]))
        if k and "off" in e and "off_full_corpus" in e and e["off"]["cpu_s"]:
            ratio_num, ratio_den = e["on"]["cpu_s"], e["off"]["cpu_s"]
            full_off = e["off_full_corpus"]["cpu_s"]
            est[t] = {"ratio_on_over_off_prefix": round(ratio_num / ratio_den, 2), "full_off_cpu_s": full_off,
                      "estimate_full_on_cpu_s": round(full_off * ratio_num / ratio_den)}
    if est:
        print("estimated full-corpus cost (ON CPU s = f1b OFF CPU s x ON/OFF ratio of the prefix; a prefix ratio understates the full cost: ties multiply with size):")
        print(json.dumps(est, sort_keys=True))
        report["estimate"] = est
        report["estimate_total_cpu_s"] = sum(v["estimate_full_on_cpu_s"] for v in est.values())
    with open(os.path.join(a.cache, "gate1_summary_%s.json" % ("full" if not k else "prefix%d" % k)), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1, sort_keys=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
