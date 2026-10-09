"""G3-h regression on the real corpus: the two window caches of the G3-f/G3-c4 builds (z_deep slide and order, G3-c3 defaults; made with the tree BEFORE this ticket)
against a fresh build with the tree of this ticket in an empty directory: the 592 placement documents must be equal (every field, the runner's timing fields aside).
usage: verify_rebuild.py OLD_SLIDE_DIR OLD_ORDER_DIR SCRATCH_DIR [WORKERS=6]  -> prints one line per rule and writes results/verify_rebuild.md"""
import glob, os, pickle, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import slide_query as Q   # noqa: E402

DATA = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
TIMING = {"ms", "wall_ms", "cpu_ms", "elapsed_ms"}


def strip(x):
    return {k: v for k, v in x.items() if k not in TIMING}


if __name__ == "__main__":
    old = {"slide": sys.argv[1], "order": sys.argv[2]}
    scratch = sys.argv[3]
    w = int(sys.argv[4]) if len(sys.argv) > 4 else 6
    lines = ["# G3-h: fresh builds against the G3-f window caches (fulllead RUN mid, padding one, G3-c3 defaults)", ""]
    for zd in ("slide", "order"):
        os.makedirs(os.path.join(scratch, zd), exist_ok=True)
        wi = Q.WindowIndex.from_jsonl(DATA, os.path.join(scratch, zd), workers=w, z_deep=zd)
        f = sorted(glob.glob(os.path.join(old[zd], "slidewin_*.pkl")))[0]
        with open(f, "rb") as fh:
            d = pickle.load(fh)
        a, b = [strip(x) for x in d["windows"]], [strip(x.doc) for x in wi.windows]
        same = sum(1 for x, y in zip(a, b) if x == y)
        line = "z_deep %s: old %s (slide %s place %s) vs fresh (slide %s place %s): %d windows old, %d new, %d equal, %d different" % (
            zd, os.path.basename(f), d["slide_spec_sha256"][:12], d["place_spec_sha256"][:12], wi.slide.spec.sha256()[:12], wi.spec.sha256()[:12],
            len(a), len(b), same, len(a) - same)
        print(line, flush=True)
        lines.append("- " + line)
    open(os.path.join(HERE, "results", "verify_rebuild.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
