"""C2 pre-registration: fix the phrases BEFORE searching (writes c2_phrases.json).

Rule (fixed in advance, plan section D11):
  * seed 20261002, one random.Random for the whole run, families in the order of FAMS;
  * per family 5 train rows drawn uniformly by id from its database; from the stored body a
    substring of random length 6..12 at a random position; a piece containing a newline or only
    whitespace is redrawn (the redraws are counted); a repeated phrase is redrawn too;
  * negative control per family: a 6..12 character piece of a random *heldout* record body
    (extracted by the builder's own extract_body), accepted only if it occurs in NO train row of
    that family (checked by FTS LIKE + exact verification); candidates found in train are redrawn
    and counted. `pro` has no heldout file, so it has no negative control (stated in the output).
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CORPUS, FAMS, HELDOUT, HERE, IDX, SEED, db, dump, raw_lines_at  # noqa: E402
from tools import build_p4_corpus_index as bi  # noqa: E402

PER_FAMILY = 5
_PLAN = ("the plan (middle role) states its own grep found this phrase absent from every corpus file; "
         "the implementer ran no search before registration")
PRIOR = {"Wi-Fiなし 携帯データ": _PLAN, "脱水機の異音": _PLAN}

TICKET = [
    ("冷えた頬をマフラー", ["pro"]), ("湯気の中に青菜", ["pro"]),
    ("葉柄と葉身", ["general_qa"]), ("Wi-Fiなし 携帯データ", ["general_qa"]),
    ("strings.HasSuffix", ["code_qa", "code"]), ("重複部分文字列", ["code_qa", "code"]),
    ("脱水機の異音", ["conversation"]), ("改札を出て左", ["conversation"]),
]


def piece(rng: random.Random, body: str, counts: dict) -> str | None:
    length = rng.randint(6, 12)
    if len(body) < length:
        counts["too_short_body"] += 1
        return None
    start = rng.randint(0, len(body) - length)
    frag = body[start:start + length]
    if "\n" in frag or not frag.strip():
        counts["newline_or_blank_piece"] += 1
        return None
    return frag.strip()


def in_train(con, phrase: str) -> bool:
    for (text,) in con.execute("SELECT r.text FROM search f JOIN rows r ON r.id=f.rowid WHERE f.text LIKE ? LIMIT 2000",
                               ("%" + phrase + "%",)):
        if phrase in text:
            return True
    return False


def main() -> None:
    rng = random.Random(SEED)
    self_chosen, negatives = [], []
    redraws = {f: dict(too_short_body=0, newline_or_blank_piece=0, duplicate=0, neg_found_in_train=0) for f in FAMS}
    for fam in FAMS:
        con = db(fam)
        total = con.execute("SELECT COUNT(*) FROM rows").fetchone()[0]
        seen, picked = set(), 0
        while picked < PER_FAMILY:
            rid = rng.randint(1, total)
            _id, text, sf, line, kind = con.execute("SELECT id,text,source_file,line,kind FROM rows WHERE id=?", (rid,)).fetchone()
            frag = piece(rng, text, redraws[fam])
            if frag is None:
                continue
            if frag in seen:
                redraws[fam]["duplicate"] += 1
                continue
            seen.add(frag)
            picked += 1
            self_chosen.append(dict(family=fam, phrase=frag, row_id=_id, source_file=sf, line=line, kind=kind))
        files = HELDOUT[fam]
        if not files:
            negatives.append(dict(family=fam, phrase=None, state="UNKNOWN_NO_HELDOUT_FOR_FAMILY",
                                  note="out/ has no heldout file; no negative control can be drawn"))
            con.close()
            continue
        spec = bi.SOURCES[fam]
        pool = []  # (file, line_no, body)
        for rel in files:
            n = 0
            with (CORPUS / rel).open("rb") as handle:
                for raw in handle:
                    n += 1
                    try:
                        rec = json.loads(raw)
                        body = bi.extract_body(rec, fam, spec)[1]
                    except (ValueError, json.JSONDecodeError):
                        continue
                    pool.append((rel, n, body))
        for _ in range(100000):
            rel, n, body = pool[rng.randrange(len(pool))]
            frag = piece(rng, body, redraws[fam])
            if frag is None:
                continue
            if in_train(con, frag):
                redraws[fam]["neg_found_in_train"] += 1
                continue
            negatives.append(dict(family=fam, phrase=frag, heldout_file=rel, heldout_line=n,
                                  heldout_pool=len(pool), checked_absent_in="train rows of the same family (FTS LIKE + exact)"))
            break
        con.close()
    dump(HERE / "c2_phrases.json", dict(
        seed=SEED, preregistered_before_search=True, rule=__doc__.strip(),
        ticket=[dict(phrase=p, expected_families=f, ticket_requires="at least one hit with provenance",
                     prior_observation=PRIOR.get(p, "none; the implementer ran no search before registration"))
                for p, f in TICKET],
        self_chosen=self_chosen, negative_controls=negatives, redraws=redraws))
    print(len(self_chosen), "self-chosen;", sum(1 for n in negatives if n["phrase"]), "negative controls")


if __name__ == "__main__":
    main()
