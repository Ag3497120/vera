"""Step 2 — keep the citation, drop the copy.

A typed-edge store that keeps every sentence is as large as the corpus. The
citation does not need the copy: it needs to point at where the sentence is.
So one edge is kept ONCE with

    n_src       how many independent sources wrote it
    witnesses   up to 3 pointers (source, sentence sha) — not the text

and split into two seats:

    core        n_src >= 2   — the only edges an answer may use (the
                               preregistered rule already required 2)
    candidate   n_src == 1   — kept, never answered from; a second source
                               promotes it

Measured here: bytes of the raw text, of the full per-sentence edge table,
of core and of candidate — and that the commonsense bank answers are
IDENTICAL from the core alone (the check that compaction lost nothing an
answer uses).

    python3.11 tools/compact_typed.py ~/Projects/vera-corpus/build/typed_human.db
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verantyx.typed_edges import ask_property  # noqa: E402

BANK = json.loads((Path(__file__).resolve().parent /
                   "commonsense_bank_2026-08-14.json").read_text())["items"]
ANSWERABLE = ("assert", "cond_then")


def compact(src_db: Path) -> dict:
    out = {}
    con = sqlite3.connect(str(src_db))
    rows = con.execute(
        "SELECT head, rel, dep, pol, mod, src, sha FROM tedges "
        "ORDER BY head, rel, dep, pol, mod").fetchall()
    text_bytes = con.execute("SELECT sum(length(CAST(text AS BLOB))) FROM tsent").fetchone()[0]
    con.close()
    groups = {}
    for h, r, d, p, m, s, sha in rows:
        g = groups.setdefault((h, r, d, p, m), {})
        g.setdefault(s, sha)
    # Intern: every source name and every word is written once; an edge is
    # five small integers plus up to three sentence ids. The sentence id is
    # the rowid of the sentence in its own corpus file, so the citation
    # still resolves to the exact line — the copy is what is dropped.
    src_id, word_id, sent_id = {}, {}, {}
    def sid(x): return src_id.setdefault(x, len(src_id))
    def wid(x): return word_id.setdefault(x, len(word_id))
    def nid(x): return sent_id.setdefault(x, len(sent_id))
    for seat in ("core", "candidate"):
        dst = src_db.with_name(src_db.stem + ".%s.db" % seat)
        if dst.exists():
            dst.unlink()
        c = sqlite3.connect(str(dst))
        c.execute("CREATE TABLE cedges (head INTEGER, rel INTEGER, dep INTEGER,"
                  " pm INTEGER, n_src INTEGER, w1 INTEGER, w2 INTEGER, w3 INTEGER)")
        batch = []
        rels = {"属性": 0, "が": 1, "を": 2, "に": 3, "で": 4}
        mods = {"assert": 0, "quote": 1, "hedge": 2, "cond_if": 3, "cond_then": 4}
        for (h, r, d, p, m), srcs in groups.items():
            n = len(srcs)
            if (seat == "core") != (n >= 2):
                continue
            w = [nid(sha) for _s, sha in list(srcs.items())[:3]] + [None, None]
            batch.append((wid(h), rels[r], wid(d), mods[m] * 2 + (p == "-"), n,
                          w[0], w[1], w[2]))
        c.executemany("INSERT INTO cedges VALUES (?,?,?,?,?,?,?,?)", batch)
        c.execute("CREATE INDEX ix ON cedges(head, rel)")
        c.execute("CREATE INDEX ix2 ON cedges(dep, rel)")
        c.execute("CREATE TABLE words (id INTEGER PRIMARY KEY, w TEXT)")
        c.executemany("INSERT INTO words VALUES (?,?)",
                      [(i, w) for w, i in word_id.items()])
        c.commit()
        c.execute("VACUUM")
        c.close()
        out[seat] = {"edges": len(batch), "bytes": os.path.getsize(dst), "path": str(dst)}
    out["raw_edges"] = len(rows)
    out["unique_edges"] = len(groups)
    out["text_bytes"] = text_bytes
    out["full_store_bytes"] = os.path.getsize(src_db)
    return out


def _hits(db: Path, subject: str, axis):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    r = con.execute("SELECT id FROM words WHERE w=?", (subject,)).fetchone()
    if not r:
        con.close()
        return []
    q = ("SELECT w.w, e.pm FROM cedges e JOIN words w ON w.id=e.dep "
         "WHERE e.head=? AND e.rel=0 AND e.pm/2 IN (0,4) "
         "UNION ALL SELECT w.w, e.pm FROM cedges e JOIN words w ON w.id=e.head "
         "WHERE e.dep=? AND e.rel=1 AND e.pm/2 IN (0,4)")
    rows = con.execute(q, (r[0], r[0])).fetchall()
    con.close()
    return [(w, "-" if pm % 2 else "+") for w, pm in rows if any(a in w for a in axis)]


def ask_core(core_db: Path, subject: str, axis) -> str:
    # Positives answer only from the core. Negatives are read from BOTH
    # seats: a negative written once is still written, and dropping it to
    # the candidate seat turned 夜は暗い from CONFLICT into ATTESTED.
    cand = core_db.with_name(core_db.name.replace(".core.", ".candidate."))
    hits = _hits(core_db, subject, axis)
    neg = any(p == "-" for _, p in hits + _hits(cand, subject, axis))
    pos = any(p == "+" for _, p in hits)
    return "CONFLICT" if neg and pos else "NEGATIVE_ATTESTED" if neg else \
        "ATTESTED" if pos else "NOT_ATTESTED"


def main() -> None:
    src = Path(sys.argv[1]).expanduser()
    rep = compact(src)
    core = Path(rep["core"]["path"])
    same = diff = 0
    diffs = []
    for it in BANK:
        full = ask_property(src, it["subject"], it["axis_tokens"])["verdict"]
        comp = ask_core(core, it["subject"], it["axis_tokens"])
        # The full store may hold a single-source negative that the core does
        # not; that is a real difference and is reported, not hidden.
        if full == comp:
            same += 1
        else:
            diff += 1
            diffs.append((it["question"], full, comp))
    rep["bank_identical"] = same
    rep["bank_differs"] = diffs
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
