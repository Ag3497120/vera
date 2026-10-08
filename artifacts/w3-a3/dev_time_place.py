"""W3-a3 12.5: which dev nouns of the time / place / quantity types the slot arm turned DIRECT (against the
same placement decided without the slot rows), and how those answers fare.  Dev data only; plus one query of
a high-frequency time word through the public entry (no special treatment anywhere in the code)."""
import json
import os
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a3-S"
sys.path.insert(0, W)
sys.path.insert(0, os.path.join(W, "artifacts/w3-a3"))
from verantyx import coarse_types as ct  # noqa: E402
from verantyx.coarse_place import query  # noqa: E402
from dev_grid import DB, klass, load, D  # noqa: E402

pl = sys.argv[1]
db = DB(pl)
seeds = {w for v in ct.SEEDS_NOUN.values() for w in v}
rows = [g for g in load(os.path.join(D, "dev_vocab.jsonl")) if g["term"] not in seeds
        and set(g["gold"]) & {"TIME", "PLACE", "QUANTITY"}]
print("placement:", pl)
print("config: slot_min=%s slot_share_pct=%s slot_lift_pct=%s" % (db.cfg["slot_min"], db.cfg["slot_share_pct"], db.cfg["slot_lift_pct"]))
tot = {"words": 0, "direct_before": 0, "direct_after": 0, "became_direct_by_slot": 0, "became_correct": 0, "became_wrong": 0}
for g in rows:
    ev = db.rows(g["term"])
    a = ct.decide_word([r for r in ev if r[0] != "slot"], db.cfg)
    b = ct.decide_word(ev, db.cfg)
    tot["words"] += 1
    tot["direct_before"] += a["origin"] == "direct"
    tot["direct_after"] += b["origin"] == "direct"
    if b["origin"] == "direct" and a["origin"] != "direct" and any(x.startswith("slot@") for x in b["by"]):
        tot["became_direct_by_slot"] += 1
        k = klass(b["tops"], g["gold"])
        tot["became_correct"] += k == "correct"
        tot["became_wrong"] += k == "wrong"
        print("slot -> direct: %s gold=%s top=%s %s by=%s" % (g["term"], ",".join(g["gold"]), ",".join(b["tops"]), k, "+".join(b["by"])))
print(json.dumps(tot, ensure_ascii=False))
r = query("昨日", placement=pl)
print("query 昨日:", json.dumps({k: r[k] for k in ("state", "origin", "estimate_basis", "top", "decided_by", "frame_status")}, ensure_ascii=False))

# diagnostic only (NOT a registered setting, nothing is tuned on it): the stored evidence of the word asked
# for above, decided under other slot_share_pct values, to show what the registered 30 (and the grid down to
# 10) does and does not reach for a word that is a time word by its past-tense use.
ev = db.rows("昨日")
print("diagnostic: 昨日 slot rows:", [(r[1], r[3], r[4], "%.1f%%" % (100.0 * r[3] / r[4])) for r in ev if r[0] == "slot"])
for sh in (30, 10, 8, 5):
    d = ct.decide_word(ev, dict(db.cfg, slot_share_pct=sh))
    print("diagnostic: slot_share_pct=%d -> %s %s %s by=%s" % (sh, d["state"], d.get("origin"), ",".join(d["tops"]), "+".join(d["by"])))
