"""Round-2 checks of the review's M1 and M2 on a built placement (report; nothing is tuned here).

  M1: (a) no unit_sample row lists a word whose decision includes ``gen_definition``;
      (b) for every word decided with ``gen_definition`` (direct or estimated) the
          compound "日本<word>" never gets a head stage built on it (``via head:<word>@R``);
          control: the same for words placed direct WITHOUT a generated sentence (a sample).
  M2: the review's query list (counts of what the placement answers), the Latin-script units
      in the counters table, and the unknown-word (L3 file) answers compared with another
      placement (``--compare``, e.g. the F1-F6-only r3c) word by word.

usage: py.sh m1_m2_check.py --placement DIR [--compare DIR]
"""
import argparse
import json
import random
import sqlite3
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"
sys.path.insert(0, W)
from verantyx.coarse_place import query  # noqa: E402

PREFIX = "日本"      # an attested left part (the estimate asks the left side to be a known word)
M2_EXPECT = {"4xx": "IDENTIFIER", "5xx": "IDENTIFIER", "1of": "IDENTIFIER", "3AND": "IDENTIFIER",
             "2in": None,   # may stay an inch unit or read as a code: only reported
             "2km": "QUANTITY", "3kg": "QUANTITY", "5GHz": "QUANTITY", "10ms": "QUANTITY",
             "128MiB": "QUANTITY", "40キロメートル": "QUANTITY", "30パーセント": "QUANTITY",
             "10メートル": "QUANTITY", "A1-23": "IDENTIFIER", "ABC-123": "IDENTIFIER"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", required=True)
    ap.add_argument("--compare", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    pl = a.placement
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % pl, uri=True)
    bad = []
    out = {"placement": pl}
    # ---- M1 (a)
    gen_words = {w for (w,) in con.execute("SELECT word FROM headwords WHERE state='DECIDED' AND "
                                          "(by='gen_definition' OR by LIKE 'gen_definition+%' "
                                          "OR by LIKE '%+gen_definition' OR by LIKE '%+gen_definition+%')")}
    upgraded = {w for (w,) in con.execute("SELECT word FROM headwords WHERE origin='direct' AND "
                                         "(by LIKE 'gen_definition+%' OR by LIKE '%+gen_definition' "
                                         "OR by LIKE '%+gen_definition+%')")}
    n_rows = hit = 0
    for (smp,) in con.execute("SELECT sample FROM unit_sample"):
        n_rows += 1
        if gen_words.intersection(smp.split("|")):
            hit += 1
    print("M1a unit_sample rows %d; rows listing a word decided with gen_definition: %d "
          "(words decided with gen_definition: %d, of which upgraded to direct: %d)"
          % (n_rows, hit, len(gen_words), len(upgraded)))
    out["unit_sample_rows"] = n_rows
    out["unit_sample_rows_listing_a_generated_word"] = hit
    out["words_decided_with_gen_definition"] = len(gen_words)
    out["of_which_upgraded_to_direct"] = len(upgraded)
    if hit:
        bad.append("unit_sample lists a generated word")
    # ---- M1 (b)
    leaked = []
    for w in sorted(gen_words):
        if len(w) < 2 or len(w) > 6:
            continue
        r = query(PREFIX + w, placement=pl)
        if any(n.get("via") == "head:%s@R" % w for n in r.get("neighbors", [])):
            leaked.append(w)
    print("M1b head-stage leaks through a generated word: %d %s" % (len(leaked), leaked[:10]))
    out["head_stage_leaks_through_generated_word"] = len(leaked)
    if leaked:
        bad.append("head stage used a generated word")
    plain = [w for (w,) in con.execute("SELECT word FROM headwords WHERE state='DECIDED' AND origin='direct' "
                                       "AND by NOT LIKE '%gen_definition%' AND length(word) BETWEEN 3 AND 5")]
    random.Random(0).shuffle(plain)
    used = 0
    for w in plain[:3000]:
        r = query(PREFIX + w, placement=pl)
        used += any(n.get("via") == "head:%s@R" % w for n in r.get("neighbors", []))
    print("M1b control: of 3000 plain direct words, the compound used the head stage on %d" % used)
    out["control_plain_direct_words_queried"] = min(3000, len(plain))
    out["control_head_stage_used"] = used
    if used == 0:
        bad.append("control shows the head stage never fires")
    # ---- M2
    print("M2 queries:")
    out["m2_queries"] = {}
    for t, exp in M2_EXPECT.items():
        r = query(t, placement=pl)
        got = r["top"][0] if len(r["top"]) == 1 else r["top"]
        rule = (r.get("axes") or {}).get("notation", {}).get("rule")
        ok = exp is None or got == exp
        print("  %-12s %-9s %-14s %-16s %s" % (t, r["state"], got, rule, "ok" if ok else "MISMATCH (expected %s)" % exp))
        out["m2_queries"][t] = {"state": r["state"], "top": r["top"], "rule": rule,
                                "expected": exp, "ok": ok}
        if not ok:
            bad.append("M2 " + t)
    lat = [u for (u,) in con.execute("SELECT unit FROM counters ORDER BY unit") if u.isascii()]
    print("M2 Latin units in counters table (%d): %s; all units: %d"
          % (len(lat), lat, con.execute("SELECT COUNT(*) FROM counters").fetchone()[0]))
    out["latin_units"] = lat
    out["counter_units_total"] = con.execute("SELECT COUNT(*) FROM counters").fetchone()[0]
    # ---- L3 words vs another placement
    if a.compare:
        U = [json.loads(l) for l in open(W + "/tests/coarse_place/data/unknown_words.jsonl", encoding="utf-8")]
        nd = 0
        for u in U:
            kw = dict(context_role=u.get("context_role"), context_predicate=u.get("context_predicate"))
            r1 = query(u["term"], placement=pl, **kw)
            r0 = query(u["term"], placement=a.compare, **kw)
            if (r1["top"], r1["origin"]) != (r0["top"], r0["origin"]):
                nd += 1
                print("  L3 differs from %s: %s  %s/%s -> %s/%s  neighbors %s" % (
                    a.compare.rstrip("/").split("/")[-2], u["term"], r0["top"], r0["origin"], r1["top"],
                    r1["origin"], [n.get("via") for n in r1.get("neighbors", [])][:3]))
        print("L3 words (n=%d) whose answer differs from %s: %d" % (len(U), a.compare, nd))
        out["l3_words"] = len(U)
        out["l3_differs_from_compare"] = nd
        out["compare"] = a.compare
    print("BAD", bad)
    out["bad"] = bad
    if a.json:
        json.dump(out, open(a.json, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
