"""frame_invariants.py <placement dir>: the section 12.10 invariants over every word of generated_frames.
A violation count of 0 is the requirement.  Also lists the words whose frame the cover rule waived `he` for
(they are recomputed with the real decide_word over the stored evidence and the placement's own config)."""
import json, sqlite3, sys
import verantyx
from verantyx import coarse_place as cp, coarse_types as ct
assert verantyx.__file__.startswith('/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a4-S/')
run = sys.argv[1]
con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % run, uri=True)
pl, err = cp._open(run)
assert err is None
words = [r[0] for r in con.execute("select word from generated_frames order by word")]
case9 = set(ct.CASE_PARTICLES_9)
viol, n_conf, n_not, n_est, other = [], 0, 0, 0, 0
waived = []
for w in words:
    a = cp.query(w, placement=run)
    ev = con.execute("select arm,src,type,n,base from evidence where word=?", (w,)).fetchall()
    gen_parts = {t.partition("|")[0] for arm, s, t, n, b in ev if arm == "gen_frame_slot"}
    fr, fs = a.get("frame"), a.get("frame_status")
    if (fr is not None) != (fs == "CONFIRMED") and not (fr is None and fs != "CONFIRMED"):
        viol.append((w, "frame null-ness vs CONFIRMED", fs))
    if fs == "CONFIRMED":
        n_conf += 1
        if not (a.get("namespace") == "P" and a["state"] == "DECIDED" and a["origin"] == "direct"
                and ct.GEN_FRAME_ARM in a["decided_by"]):
            viol.append((w, "CONFIRMED but not P/DECIDED/direct/gen_frame", a["decided_by"]))
        if not isinstance(fr, dict):
            viol.append((w, "CONFIRMED without a frame dict", fr))
        else:
            if not set(fr) <= gen_parts:
                viol.append((w, "frame has a particle the generated frame lacks", sorted(set(fr) - gen_parts)))
            if not set(fr) <= case9:
                viol.append((w, "frame key not a case particle", sorted(set(fr) - case9)))
            for p, ts in fr.items():
                if not ts or ts != sorted(set(ts)) or any(t not in ct.NOUN_TYPES for t in ts):
                    viol.append((w, "frame value malformed", (p, ts)))
    elif fs == "NOT_CONFIRMED":
        n_not += 1
        if fr is not None:
            viol.append((w, "NOT_CONFIRMED with a frame", fr))
    elif fs == "ESTIMATED":
        n_est += 1
        if fr is not None:
            viol.append((w, "ESTIMATED with a frame", fr))
    else:
        other += 1
    if a.get("origin") == "direct" and ct.GEN_FRAME_ARM in (a.get("decided_by") or []):
        d = ct.decide_word(ev, pl.cfg)
        cov = d["arms"].get(ct.GEN_FRAME_ARM, {}).get("cover") or {}
        if cov.get("he_by_ni_place"):
            waived.append((w, fs, fr, a.get("frame_unconfirmed"), cov["he_by_ni_place"], gen_parts))
            if fr is not None and ct.HE_PARTICLE in fr:
                viol.append((w, "he in frame although the generated frame has none", fr))
print("generated_frames の語 %d（CONFIRMED %d・NOT_CONFIRMED %d・ESTIMATED %d・その他 %d）" % (len(words), n_conf, n_not, n_est, other))
print("不変条件の違反: %d" % len(viol))
for v in viol:
    print("VIOLATION", v)
print("へ を覆った語（cover.he_by_ni_place が空でない）: %d" % len(waived))
for w, fs, fr, fu, arms_, gp in waived:
    print("WAIVED\t%s\tframe_status=%s\tframe=%s\tframe_unconfirmed=%s\tgenerated_particles=%s\that_arms=%s" % (
        w, fs, json.dumps(fr, ensure_ascii=False), json.dumps(fu, ensure_ascii=False), sorted(gp), arms_))
