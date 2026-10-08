"""Audit of the decision rule on a whole placement (W3-a r2, review M1 + M2).

  audit_met_arms.py --placement DIR [--out JSON]

For EVERY decided headword (DECIDED / MULTIPLE; direct, and from W3-a2 also the
estimates (generated) whose origin is "estimated") re-run the shared decision
function ``coarse_types.decide_word`` on the stored evidence, then count:

  recompute_mismatch     stored (state, top, by) != the recomputed ones
  met_ne_decided_by      {arms with met=True} != set(decided_by)  (review M2)
  role_alone             decided by exactly ONE role source and no other arm (review M1)
  role_in_by_single      a role source is among the deciding arms but fewer than
                         ``role_min_sources`` role sources are
  seed_but_other_met     a seed-decided word with another arm still marked met
  origin_mismatch        the stored origin differs from the recomputed one (W3-a2)

All of these must be 0.  Reads only; nothing is written except --out.
"""
import argparse
import json
import sqlite3
import sys
from collections import Counter

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"
sys.path.insert(0, W)
from verantyx import coarse_types as ct  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % a.placement, uri=True)
    cfg = dict(ct.DEFAULT_CONFIG)
    cfg.update(json.loads(con.execute("SELECT v FROM meta WHERE k='config'").fetchone()[0]))
    heads = {w: (st, top, by) for w, st, top, by, og in con.execute(
        "SELECT word,state,top,by,origin FROM headwords WHERE state IN ('DECIDED','MULTIPLE')")}
    origin_of = {w: og for w, og in con.execute(
        "SELECT word,origin FROM headwords WHERE state IN ('DECIDED','MULTIPLE')")}
    cnt = Counter()
    examples = {}
    cur_w, cur = None, []

    def flush(w, ev):
        st, top, by = heads[w]
        d = ct.decide_word(ev, cfg)
        cnt["words"] += 1
        if (d["state"], ",".join(d["tops"]), "+".join(d["by"])) != (st, top, by):
            cnt["recompute_mismatch"] += 1
            examples.setdefault("recompute_mismatch", []).append(w)
        if d.get("origin") != origin_of[w]:
            cnt["origin_mismatch"] += 1
            examples.setdefault("origin_mismatch", []).append(w)
        met = {k for k, x in d["arms"].items() if x["met"]}
        dby = set(by.split("+")) if by else set()
        if met != dby:
            cnt["met_ne_decided_by"] += 1
            examples.setdefault("met_ne_decided_by", []).append(w)
        roles = [k for k in dby if k.startswith("role@")]
        if roles and len(roles) < cfg["role_min_sources"] and "gen_definition" not in dby:
            # (a role source below role_min_sources may join a decision only when a generated
            # definition AGREES with it: the upgrade to "direct", W3-a2 -- counted separately)
            cnt["role_in_by_single"] += 1
            examples.setdefault("role_in_by_single", []).append(w)
        if len(dby) == 1 and len(roles) == 1:
            cnt["role_alone"] += 1
            examples.setdefault("role_alone", []).append(w)
        if "seed" in dby and any(x["met"] for k, x in d["arms"].items() if k != "seed"):
            cnt["seed_but_other_met"] += 1
        if roles and len(roles) < cfg["role_min_sources"] and "gen_definition" in dby:
            cnt["role_single_source_with_generated_agreement"] += 1
        for k in dby:
            cnt["by:" + k.split("@")[0]] += 1

    for w, arm, src, typ, n, base in con.execute(
            "SELECT word,arm,src,type,n,base FROM evidence ORDER BY word"):
        if w != cur_w:
            if cur_w is not None and cur_w in heads:
                flush(cur_w, cur)
            cur_w, cur = w, []
        cur.append((arm, src, typ, n, base))
    if cur_w is not None and cur_w in heads:
        flush(cur_w, cur)
    out = {"placement": a.placement, "role_min_sources": cfg["role_min_sources"],
           "direct_headwords": sum(1 for v in origin_of.values() if v == "direct"),
           "estimated_generated_headwords": sum(1 for v in origin_of.values() if v == "estimated"),
           "decided_headwords": len(heads), "words_with_evidence_checked": cnt["words"],
           "counts": dict(sorted(cnt.items())),
           "examples": {k: v[:10] for k, v in examples.items()}}
    s = json.dumps(out, ensure_ascii=False, indent=1)
    print(s)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(s + "\n")
    bad = sum(cnt[k] for k in ("recompute_mismatch", "met_ne_decided_by", "role_alone",
                               "role_in_by_single", "seed_but_other_met", "origin_mismatch"))
    return 0 if bad == 0 and cnt["words"] == len(heads) else 1


if __name__ == "__main__":
    sys.exit(main())
