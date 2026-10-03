"""W3-a3 audit of a whole placement (the analogue of W3-a2's met_audit).  Read only.

  audit_w3a3.py --placement DIR

Checks, over EVERY headword / evidence row of the placement:
  A. the stored state / origin / top / by equal ``ct.decide_word`` run again on the stored evidence with the
     stored config (difference 0);
  B. no word was decided by ``role_distribution`` / ``slot`` alone (a word whose ``by`` holds only those arms);
  C. every ``gen_frame`` upgrade to direct satisfies the registered rule, recomputed here from the evidence
     rows and the config (not from the decision code): at least ``rd_min_sources`` role_distribution arms,
     every arm that reached its own threshold is among them, all vote for the generated type, and the
     generated frame holds every significant particle of each (the nine particles);
  D. every ``gen_frame`` word that stayed an estimate has a reason or no distribution to back it;
  E. every P headword asked through the public entry: the frame invariants (docs 12.10) hold and
     ``frame_status`` is one of the closed list.
"""
import argparse
import json
import sqlite3
import sys
import time

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a3-S"
sys.path.insert(0, W)
from verantyx import coarse_place as cp  # noqa: E402
from verantyx import coarse_types as ct  # noqa: E402

STATUS = {"CONFIRMED", "NOT_CONFIRMED", "ESTIMATED", "NOT_PREDICATE", "NO_ANSWER", "NO_PLACEMENT", "NO_FRAME_TABLE"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", required=True)
    a = ap.parse_args()
    t0 = time.time()
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % a.placement, uri=True)
    cfg = dict(ct.DEFAULT_CONFIG)
    cfg.update(json.loads(con.execute("SELECT v FROM meta WHERE k='config'").fetchone()[0]))
    heads = {r[0]: r[1:] for r in con.execute("SELECT word, ns, state, origin, top, by FROM headwords")}
    out = {"placement": a.placement,
           "content_sha256": json.load(open(a.placement + "/manifest.json"))["content_sha256"],
           "headwords": len(heads), "config": {k: cfg[k] for k in (
               "frame_decides", "rd_min_total", "rd_particle_min", "rd_particle_share_pct", "rd_type_share_pct",
               "rd_min_sources", "slot_min", "slot_share_pct", "slot_lift_pct", "rd_store_min")}}
    diff, alone, upg, upg_bad, est_gf, est_bad = [], [], 0, [], 0, []
    upg_codex_only = 0
    cur_w, rows = None, []

    def check(w, rows):
        nonlocal upg, est_gf, upg_codex_only
        ns, state, origin, top, by = heads[w]
        ev = [(a_, s, t, n, b) for (_w, a_, s, t, n, b) in rows]
        d = ct.decide_word(ev, cfg)
        got = (d["state"], d.get("origin"), ",".join(d["tops"]), "+".join(d["by"]))
        if got != (state, origin, top, by):
            diff.append({"word": w, "stored": [state, origin, top, by], "now": list(got)})
        arms = [x for x in by.split("+") if x]
        if arms and all(x.startswith(("role_distribution@", "slot@")) for x in arms):
            alone.append(w)
        gf = [r for r in ev if r[0] == "gen_frame"]
        if not gf:
            return
        ptypes = {r[2] for r in gf}
        gen_parts = {r[2].partition("|")[0] for r in ev if r[0] == "gen_frame_slot"}
        # recompute R from the rows (not from decide_word)
        per_src = {}
        for r in ev:
            if r[0] == "role_distribution":
                per_src.setdefault(r[1], {})[r[2]] = (r[3], r[4])
        R = {}
        for src, cnt in per_src.items():
            base = next(iter(cnt.values()))[1]
            an = ct.rd_analyze({k: v[0] for k, v in cnt.items()}, cfg, base)
            if len(an["candidates"]) == 1:
                R[src] = an
        if origin == "direct" and "gen_frame" in arms:
            upg += 1
            ok = (len(ptypes) == 1 and len(R) >= cfg["rd_min_sources"]
                  and all(an["candidates"] == [next(iter(ptypes))] for an in R.values())
                  and all(set(an["sig"]) <= gen_parts for an in R.values())
                  and sorted(["role_distribution@" + s for s in R] + ["gen_frame"]) == sorted(arms)
                  and top == next(iter(ptypes)))
            if not ok:
                upg_bad.append(w)
            elif all(s.startswith("codex:") for s in R):
                upg_codex_only += 1
        elif origin == "estimated" and "gen_frame" in arms:
            est_gf += 1
            # an estimate must not be one the rule would have upgraded
            t = next(iter(ptypes)) if len(ptypes) == 1 else None
            would = (t is not None and len(R) >= cfg["rd_min_sources"]
                     and all(an["candidates"] == [t] for an in R.values())
                     and all(set(an["sig"]) <= gen_parts for an in R.values()))
            if would:
                est_bad.append(w)

    for row in con.execute("SELECT word, arm, src, type, n, base FROM evidence ORDER BY word"):
        if row[0] != cur_w:
            if cur_w is not None and cur_w in heads:
                check(cur_w, rows)
            cur_w, rows = row[0], []
        rows.append(row)
    if cur_w is not None and cur_w in heads:
        check(cur_w, rows)
    out["A_decision_recomputed"] = {"differences": len(diff), "examples": diff[:10]}
    out["B_decided_by_new_agreement_only_arms_alone"] = {"words": len(alone), "examples": alone[:10]}
    out["C_gen_frame_direct_upgrades"] = {"words": upg, "violating_the_rule": len(upg_bad), "examples": upg_bad[:10],
                                          "all_distribution_sources_are_codex": upg_codex_only}
    out["D_gen_frame_estimates"] = {"words": est_gf, "that_the_rule_would_have_upgraded": len(est_bad), "examples": est_bad[:10]}
    # E: the frame invariants through the public entry, every predicate headword
    bad, by_status, n = [], {}, 0
    for w, (ns, state, origin, top, by) in heads.items():
        if "P" not in ns:
            continue
        r = cp.query(w, placement=a.placement)
        n += 1
        st = r["frame_status"]
        by_status[st] = by_status.get(st, 0) + 1
        problems = []
        if st not in STATUS:
            problems.append("status")
        fr = r["frame"]
        if (fr is not None) != (st == "CONFIRMED"):
            problems.append("frame/status")
        if fr is not None:
            ok = (r["namespace"] == "P" and r["state"] == "DECIDED" and r["origin"] == "direct"
                  and "gen_frame" in r["decided_by"] and fr
                  and all(p in ct.CASE_PARTICLES_9 for p in fr)
                  and all(v and v == sorted(v) and all(t in ct.NOUN_TYPES for t in v) for v in fr.values())
                  and list(fr) == [p for p in ct.ROLE_PARTICLES if p in fr])
            if not ok:
                problems.append("invariant")
        if r["origin"] == "estimated" and r["estimate_basis"] not in ("proximity", "generated"):
            problems.append("basis")
        if problems:
            bad.append({"word": w, "problems": problems})
    out["E_frame_invariants_all_predicate_headwords"] = {"queried": n, "by_frame_status": by_status,
                                                         "violations": len(bad), "examples": bad[:10]}
    out["seconds"] = round(time.time() - t0, 1)
    out["all_clear"] = not (diff or alone or upg_bad or est_bad or bad)
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if out["all_clear"] else 1


if __name__ == "__main__":
    sys.exit(main())
