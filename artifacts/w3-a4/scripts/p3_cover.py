"""P3 (pre-build): r7's stored evidence decided with r7's config + frame_cover_rule (the real decide_word).
usage: p3_cover.py <outdir>   -> <outdir>/cover_<rule>.tsv for the two new rules, plus a count line per rule."""
import json, sqlite3, sys, collections
import verantyx
from verantyx import coarse_types as ct
assert verantyx.__file__.startswith('/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a4-S/'), verantyx.__file__
outdir = sys.argv[1]
R7 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1/placement.sqlite'
con = sqlite3.connect('file:%s?mode=ro' % R7, uri=True)
base = dict(ct.DEFAULT_CONFIG)
base.update(json.loads(con.execute("select v from meta where k='config'").fetchone()[0]))
words = [r[0] for r in con.execute("select distinct word from evidence where arm='gen_frame'")]
nseen = dict(con.execute("select word,n_seen from headwords").fetchall())
ev = {w: con.execute("select arm,src,type,n,base from evidence where word=?", (w,)).fetchall() for w in words}
res = {}
for rule in ("all9", "he_by_ni_place", "k62_he_by_ni_place"):
    c = dict(base, frame_cover_rule=rule)
    res[rule] = {w: ct.decide_word(ev[w], c) for w in words}
print("config:", {k: base[k] for k in sorted(base) if k.startswith('rd_')}, "rule in r7 config:", base.get("frame_cover_rule"))
for rule in ("he_by_ni_place", "k62_he_by_ni_place"):
    new = sorted((w for w in words if res[rule][w]["origin"] == "direct" and res["all9"][w]["origin"] != "direct"),
                 key=lambda w: (-nseen.get(w, 0), w))
    lost = sorted(w for w in words if res[rule][w]["origin"] != "direct" and res["all9"][w]["origin"] == "direct")
    changed_other = sorted(w for w in words if (res[rule][w]["state"], res[rule][w]["tops"], res[rule][w]["by"]) !=
                           (res["all9"][w]["state"], res["all9"][w]["tops"], res["all9"][w]["by"]) and w not in new)
    whys = collections.Counter(res[rule][w]["arms"].get("gen_frame", {}).get("why") for w in words)
    print(rule, "direct", sum(1 for w in words if res[rule][w]["origin"] == "direct"),
          "new", len(new), "lost", len(lost), "other_changes", len(changed_other), "why", dict(whys))
    print("  lost:", lost, " other:", changed_other)
    with open("%s/cover_%s.tsv" % (outdir, rule), "w", encoding="utf-8") as f:
        f.write("word\ttype\tgen_frame_slots\tarm_significant_particles\tcovered_he_arms\tignored_particles\tn_seen\n")
        for w in new:
            d = res[rule][w]
            slots = sorted(r[2] for r in ev[w] if r[1] and r[0] == "gen_frame_slot")
            arms = {k: a["sig"] for k, a in d["arms"].items() if a["arm"] == "role_distribution"}
            cov = d["arms"]["gen_frame"].get("cover", {})
            f.write("%s\t%s\t%s\t%s\t%s\t%s\t%d\n" % (
                w, d["tops"][0], " ".join(slots),
                json.dumps(arms, ensure_ascii=False), json.dumps(cov.get("he_by_ni_place"), ensure_ascii=False),
                json.dumps(cov.get("ignored"), ensure_ascii=False), nseen.get(w, 0)))
