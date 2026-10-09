"""G3-h: build (or load) the twelve window caches of the grid {arm_cap budget | x} x {z_deep slide | order | order_window} x {seat_empty_axis allow | deny}
(fulllead RUN, level mid, padding one: 592 windows, 292 pairs; centre_scope both, strict judgement, growth z_reserved, unit_sid: the module defaults).
usage: build_caches.py CACHE_DIR [WORKERS=6]    one directory holds the twelve files (their names carry the slide and place spec shas).
A cache that is present and whose headers match is loaded, not built (the build wall / cpu seconds in the header are those of the run that made it)."""
import itertools, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import slide_query as Q   # noqa: E402

DATA = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
CAPS, ZDS, SEATS = ("budget", "x"), ("slide", "order", "order_window"), ("allow", "deny")

if __name__ == "__main__":
    cache = sys.argv[1]
    w = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    os.makedirs(cache, exist_ok=True)
    for cap, zd, seat in itertools.product(CAPS, ZDS, SEATS):
        t0 = time.time()
        wi = Q.WindowIndex.from_jsonl(DATA, cache, workers=w, place_kw={"arm_cap": cap, "seat_empty_axis": seat}, z_deep=zd,
                                      log=lambda m: print("   " + m, file=sys.stderr, flush=True))
        h = wi.header
        print("%-7s %-13s %-5s slide %s place %s windows %d  %.0fs (cache wall %.0fs cpu %.0fs) load %.1f" % (
            cap, zd, seat, wi.slide.spec.sha256()[:12], wi.spec.sha256()[:12], len(wi.windows), time.time() - t0, h.get("wall_ms", 0) / 1000.0,
            h.get("cpu_ms", 0) / 1000.0, os.getloadavg()[0]), flush=True)
