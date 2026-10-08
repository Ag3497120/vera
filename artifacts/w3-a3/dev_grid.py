"""W3-a3 12.8: evaluate the registered grid on the DEV data from one dev placement's stored evidence.

A word's decision is a function of its evidence rows and the config, so the grid is evaluated by
calling ``ct.decide_word`` again with the config changed (the rows are stored with a fixed floor
``rd_store_min`` and a fixed lift ``slot_lift_pct``, which do not depend on the grid).  Data read: the dev
verbs (``tests/coarse_place/data/dev_verbs.jsonl``) for the predicate settings, the dev vocabulary
(``dev_vocab.jsonl``) for the slot settings.  The frozen test data are never read here.

  dev_grid.py --placement DIR --out artifacts/w3-a3/dev_grid.txt [--write-config config_w3a3.json]

Selection (registered in docs 12.8, written before measuring):
  predicates: among the settings whose DIRECT wrong decisions are 0, the most DIRECT correct; none with 0
              wrong -> the fewest wrong, then the most correct.  A tie: fewer direct answers (stricter),
              then the earlier in the grid (the strictest first).
  slot:       among the settings whose direct wrong decisions on the dev vocabulary do not exceed those of
              the same placement WITHOUT the slot rows, the most direct correct; same tie rules.
"""
import argparse
import itertools
import json
import os
import sqlite3
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a3-S"
sys.path.insert(0, W)
from verantyx import coarse_types as ct  # noqa: E402

D = os.path.join(W, "tests/coarse_place/data")
RD_TOTAL = (100, 50, 20)
RD_PART_MIN = (10, 5)
RD_PART_SHARE = (30, 20, 10)
RD_TYPE_SHARE = (70, 50)
RD_SOURCES = (2, 1)
SLOT_MIN = (20, 10, 5)
SLOT_SHARE = (30, 20, 10)


def load(path):
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def klass(top, gold):
    gs = set(gold)
    if top and set(top) & gs and len(top) <= max(1, len(gs)):
        return "correct"
    if len(top) == 1:
        return "wrong"
    return "other"


class DB:
    def __init__(self, pl):
        self.con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % pl, uri=True)
        self.cfg = dict(ct.DEFAULT_CONFIG)
        self.cfg.update(json.loads(self.con.execute("SELECT v FROM meta WHERE k='config'").fetchone()[0]))
        self._memo = {}
        self.counters = frozenset(r[0] for r in self.con.execute("SELECT unit FROM counters"))

    def rows(self, w):
        if w not in self._memo:
            self._memo[w] = [tuple(r) for r in self.con.execute(
                "SELECT arm, src, type, n, base FROM evidence WHERE word=?", (w,))]
        return self._memo[w]

    def has_head(self, w):
        return self.con.execute("SELECT 1 FROM headwords WHERE word=?", (w,)).fetchone() is not None


def score(db, rows, cfgv, drop=()):
    """direct counts of ``rows`` (test rows with kind/gold) under ``cfgv`` (evidence rows of the arms in
    ``drop`` removed first)."""
    c = w = nd = 0
    unk_direct = 0
    ups = 0
    for g in rows:
        term = g["term"]
        nt = ct.notation_type(term, db.counters)          # the query reads the spelling first
        if nt is not None:
            d = {"origin": "direct", "state": "DECIDED", "tops": [nt[0]], "by": ["notation"]}
        else:
            import unicodedata
            norm = unicodedata.normalize("NFKC", term)       # ... and the query tries the NFKC form of an unseen word
            if norm != term and not db.has_head(term) and db.has_head(norm):
                term = norm
            ev = [r for r in db.rows(term) if r[0] not in drop]
            d = ct.decide_word(ev, cfgv)
        direct = d["origin"] == "direct" and d["state"] in ("DECIDED", "MULTIPLE")
        if g["kind"] != "typed":
            unk_direct += int(direct)
            continue
        if not direct:
            continue
        nd += 1
        k = klass(d["tops"], g["gold"])
        c += k == "correct"
        w += k == "wrong"
        ups += ct.GEN_FRAME_ARM in d["by"]
    return {"direct_correct": c, "direct_wrong": w, "direct_answers": nd, "unknown_direct": unk_direct,
            "gen_frame_direct": ups}


def pick(results, wrong_cap):
    """results: list of (grid index, setting, score).  The registered selection."""
    ok = [r for r in results if r[2]["direct_wrong"] <= wrong_cap]
    if not ok:
        mn = min(r[2]["direct_wrong"] for r in results)
        ok = [r for r in results if r[2]["direct_wrong"] == mn]
    best = max(r[2]["direct_correct"] for r in ok)
    ok = [r for r in ok if r[2]["direct_correct"] == best]
    fewest = min(r[2]["direct_answers"] for r in ok)
    ok = [r for r in ok if r[2]["direct_answers"] == fewest]
    return min(ok, key=lambda r: r[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--placement", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--write-config", default=None)
    a = ap.parse_args()
    db = DB(a.placement)
    verbs = load(os.path.join(D, "dev_verbs.jsonl"))
    seeds = {w for v in ct.SEEDS_NOUN.values() for w in v}
    vocab = [dict(g, kind="typed") for g in load(os.path.join(D, "dev_vocab.jsonl")) if g["term"] not in seeds]
    lines = ["# W3-a3 dev grid (docs 12.8).  placement: %s  content_sha256: %s" % (
        a.placement, json.load(open(os.path.join(a.placement, "manifest.json")))["content_sha256"]),
        "# stored config: frame_decides=%s rd_store_min=%s slot_lift_pct=%s" % (
            db.cfg["frame_decides"], db.cfg["rd_store_min"], db.cfg["slot_lift_pct"]),
        "# data: dev_verbs (%d rows, %d typed), dev_vocab without seeds (%d rows)" % (
            len(verbs), sum(g["kind"] == "typed" for g in verbs), len(vocab)), ""]
    # ---- predicates
    lines.append("## predicates: rd_min_total rd_particle_min rd_particle_share_pct rd_type_share_pct rd_min_sources"
                 " -> direct_correct direct_wrong direct_answers gen_frame_direct unknown_direct")
    res = []
    for i, (tot, pmin, psh, tsh, ms) in enumerate(itertools.product(
            RD_TOTAL, RD_PART_MIN, RD_PART_SHARE, RD_TYPE_SHARE, RD_SOURCES)):
        cfgv = dict(db.cfg, rd_min_total=tot, rd_particle_min=pmin, rd_particle_share_pct=psh,
                    rd_type_share_pct=tsh, rd_min_sources=ms)
        s = score(db, verbs, cfgv)
        setting = {"rd_min_total": tot, "rd_particle_min": pmin, "rd_particle_share_pct": psh,
                   "rd_type_share_pct": tsh, "rd_min_sources": ms}
        res.append((i, setting, s))
        lines.append("%2d  %3d %2d %2d %2d %d -> %d %d %d %d %d" % (
            i, tot, pmin, psh, tsh, ms, s["direct_correct"], s["direct_wrong"], s["direct_answers"],
            s["gen_frame_direct"], s["unknown_direct"]))
    # the same placement without any of the new arms: what the old arms alone give on the dev verbs
    base = score(db, verbs, db.cfg, drop=("role_distribution", "gen_frame", "gen_frame_slot", "slot"))
    lines.append("   reference, without the new arms (frame_decides=%s): %s" % (db.cfg["frame_decides"], json.dumps(base)))
    sel = pick(res, 0)
    lines.append("SELECTED predicates (grid index %d): %s -> %s" % (sel[0], json.dumps(sel[1]), json.dumps(sel[2])))
    lines.append("   (rule: fewest wrong, 0 if possible; then most direct correct; then fewer direct answers; then the earlier grid row)")
    lines.append("")
    # ---- slot
    lines.append("## slot (dev vocabulary L2): slot_min slot_share_pct -> direct_correct direct_wrong direct_answers")
    nos = score(db, vocab, db.cfg, drop=("slot",))
    lines.append("   without the slot rows (stage-1 decision): %s" % json.dumps(nos))
    sres = []
    for i, (smin, ssh) in enumerate(itertools.product(SLOT_MIN, SLOT_SHARE)):
        cfgv = dict(db.cfg, slot_min=smin, slot_share_pct=ssh)
        s = score(db, vocab, cfgv)
        sres.append((i, {"slot_min": smin, "slot_share_pct": ssh}, s))
        lines.append("%2d  %2d %2d -> %d %d %d" % (i, smin, ssh, s["direct_correct"], s["direct_wrong"], s["direct_answers"]))
    ssel = pick(sres, nos["direct_wrong"])
    lines.append("SELECTED slot (grid index %d): %s -> %s" % (ssel[0], json.dumps(ssel[1]), json.dumps(ssel[2])))
    lines.append("   (rule: wrong not above the no-slot wrong; then most direct correct; then fewer direct answers; then the earlier grid row)")
    out = {"predicates": sel[1], "slot": ssel[1]}
    lines.append("SELECTED_JSON " + json.dumps(out))
    open(a.out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(l for l in lines if l.startswith("SELECTED") or l.startswith("   ")))
    if a.write_config:
        cfg = json.load(open(a.write_config, encoding="utf-8"))
        cfg.update(sel[1])
        cfg.update(ssel[1])
        cfg["rd_store_min"] = 20
        cfg["slot_lift_pct"] = 300
        json.dump(cfg, open(a.write_config, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
        open(a.write_config, "a").write("\n")


if __name__ == "__main__":
    main()
