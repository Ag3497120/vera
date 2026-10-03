"""hub_spread: how far one hypernym's type spreads (W3-a2 F1).

For each hub word, the jawiki leads whose FIRST SENTENCE ends in "... の <hub>[である]。" are
looked up in a placement's headwords: the (state, top) of the article's title.  The
counts show whether one wrong definition of the hub (a hub typed wrongly) has been
handed to thousands of titles.

    hub_spread.py --placement DIR --out FILE

Reads the lead file read-only; opens the placement read-only.  The hub list is fixed
here (an aggregation script under artifacts/, not a source of the placement).
"""
import argparse
import json
import re
import sqlite3
import sys
from collections import Counter, defaultdict

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"
sys.path.insert(0, W + "/tools")
sys.path.insert(0, W)
import build_coarse_placement as b  # noqa: E402

JW = "/Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl"
HUBS = ["小説家", "僧", "大名", "武将", "僧侶", "網膜"]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % args.placement, uri=True)
    pat = {h: re.compile(r"の" + h + r"(?:である|であった|だった)?。$") for h in HUBS}
    res = defaultdict(Counter)
    for line in open(JW, encoding="utf-8"):
        if '"text"' not in line:
            continue
        d = json.loads(line)
        t = d["title"]
        tx = d.get("text") or ""
        dt, _ = b.definition_text(tx, t)
        s = b.first_sentence(dt.strip().lstrip("。、 "))
        for h, p in pat.items():
            if p.search(s):
                r = con.execute("select state,top from headwords where word=?", (t,)).fetchone()
                res[h][(r[0], r[1]) if r else ("NONE", "")] += 1
    lines = ["placement: %s" % args.placement]
    for h in HUBS:
        lines.append("%s %d %s" % (h, sum(res[h].values()), res[h].most_common(5)))
    text = "\n".join(lines) + "\n"
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
