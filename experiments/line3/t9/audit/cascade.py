"""T9 audit, question 2: where does the gold get lost?  intra2 (n = 69), on the re-run records of rerun_ask.py.
Per question and tier the furthest stage the gold reached:
  0 tok      the gold is not inside ONE unit of the tier anywhere in the corpus (tokenisation: split over units / absent)
  1 noquery  a gold unit exists, but no cross holding a question unit holds it (not reachable by the V1 read at any budget)
  2 budget   a cross holding a question unit holds it, but that cross was not among those read (node budget)
  3 nofix    a read cross holds it, but no member of that cross reached a fixed point (no state carries it)
  4 noagree  a fixed-point state carries it, but only in members that do not answer (sections disagree / ambiguous /
             agreed but ungrounded): no answering state carries it
  5 select   an answering fixed-point state carries it, but it was not adopted (query-share state choice took others)
  6 path     an adopted state carries it, but it is not on a section path (read-out keeps path words only)
  7 hit      it is in an entry
A question's stage = the furthest stage over the three tiers (layer 0 = flat); for layers-ssp an upper-layer hit is a
hit (an upper layer that read bundles holding a gold unit without listing it is reported separately).
usage: cascade.py [PRESET=standard] -> cascade_<preset>.md"""
import json, os, sys
from collections import Counter, defaultdict
HERE = os.path.dirname(os.path.abspath(__file__))
T9 = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(T9)))
sys.path.insert(0, ROOT); sys.path.insert(0, T9)
import scorer as S                                  # noqa: E402
from verantyx.line3 import ask as A                 # noqa: E402
from verantyx.line3 import cycle as cy              # noqa: E402
from verantyx.line3 import matryoshka as M          # noqa: E402

PRESET = sys.argv[1] if len(sys.argv) > 1 else "standard"
FL = os.path.join(T9, "..", "bank2", "data", "fulllead_sents.jsonl")
idx = A.Index.from_jsonl(FL, os.environ["T9_CACHE"])
recs = [json.loads(l) for l in open(os.path.join(HERE, "raw", "ask_fulllead_%s.jsonl" % PRESET), encoding="utf-8")]
recs.sort(key=lambda r: r["id"])
tok = {json.loads(l)["id"]: json.loads(l) for l in open(os.path.join(HERE, "tokenisation.jsonl"), encoding="utf-8")}
NAMES = ["tok", "noquery", "budget", "nofix", "noagree", "select", "path", "hit"]
units_of = {}


def cross_units(tier, seed):
    k = (tier, seed)
    if k not in units_of:
        units_of[k] = set(M.placed_units(idx.stores[tier].cross_for(seed)))
    return units_of[k]


def tier_stage(tier, d):
    gu = set(d["gold_units"])
    if any(S.hits_words(r_gold, e["words"]) for e in d["entries"]):
        return 7
    if not gu:
        return 0
    if d["adopted_gold"]:
        return 6
    if d["ends_answering_gold"]:
        return 5
    if d["ends_gold"]:
        return 4
    if d["read_gold"]:
        return 3
    q = set(cy.make_context(tuple(d["query_units"])).energy_units)
    ts = idx.space.tiers[tier]
    for s in ts.units():
        cu = cross_units(tier, s)
        if cu & q and cu & gu:
            return 2
    return 1


L = []


def out(s=""):
    L.append(s); print(s)


rows = []
for r in recs:
    r_gold = r["gold"]
    st = {t: tier_stage(t, d) for t, d in r["layer0"].items()}
    flat = max(st.values())
    up_hit = False; up_under = False
    for t, d in r["on"]["seatsPath"]["tiers"].items():
        for run in d["runs"]:
            if any(S.hits_words(r_gold, e["words"]) for e in run["entries"]):
                up_hit = True
            if run["gold_under_read_bundles"]:
                up_under = True
    ssp = 7 if (flat == 7 or up_hit) else flat
    rows.append((r, st, flat, ssp, up_under))

for label, col in (("flat-%s" % PRESET, 2), ("layers-ssp-%s" % PRESET, 3)):
    c = Counter(NAMES[x[col]] for x in rows)
    out("### %s: furthest stage of the gold (n = %d)" % (label, len(rows)))
    out()
    out("| stage | count | ids |")
    out("|---|---|---|")
    for i, n in enumerate(NAMES):
        ids = [x[0]["id"] for x in rows if x[col] == i]
        out("| %d %s | %d | %s |" % (i, n, len(ids), ", ".join(ids)))
    out()
out("### per tier (flat-%s): stage counts" % PRESET)
out()
out("| tier | " + " | ".join(NAMES) + " |")
out("|---|" + "---|" * len(NAMES))
for t in ("RUN", "WORD", "CHAR"):
    c = Counter(NAMES[x[1][t]] for x in rows)
    out("| %s | %s |" % (t, " | ".join(str(c[n]) for n in NAMES)))
out()
out("### layers-ssp misses whose upper layer read a bundle holding a gold unit (k = 1): %s" %
    ", ".join(x[0]["id"] for x in rows if x[3] < 7 and x[4]))
out()
# verdicts of the tier that got furthest, for the non-hits
out("### verdict of each tier for the misses (flat-%s)" % PRESET)
out()
out("| id | gold | stage per tier R/W/C | RUN verdict | WORD verdict | CHAR verdict | RUN entries (first 2) |")
out("|---|---|---|---|---|---|---|")
for r, st, flat, ssp, uu in rows:
    if flat == 7:
        continue
    L0 = r["layer0"]
    out("| %s | %s | %s/%s/%s | %s | %s | %s | %s |" % (
        r["id"], r["gold"], NAMES[st["RUN"]], NAMES[st["WORD"]], NAMES[st["CHAR"]], L0["RUN"]["verdict"], L0["WORD"]["verdict"],
        L0["CHAR"]["verdict"], " ; ".join("/".join(e["words"][:8]) for e in L0["RUN"]["entries"][:2]) or "-"))
out()
json.dump([{"id": x[0]["id"], "tiers": {t: NAMES[v] for t, v in x[1].items()}, "flat": NAMES[x[2]], "ssp": NAMES[x[3]],
            "ssp_upper_gold_under": x[4]} for x in rows], open(os.path.join(HERE, "cascade_%s.json" % PRESET), "w"),
          ensure_ascii=False, indent=0)
open(os.path.join(HERE, "cascade_%s.md" % PRESET), "w", encoding="utf-8").write("\n".join(L) + "\n")
