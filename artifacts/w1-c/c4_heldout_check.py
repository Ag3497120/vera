"""C4: do heldout record bodies occur in the index? (seed 20261002, 200 uniform records)

Population: every line of every heldout file (the five structured families, code, even/code,
conversation, even/conversation). out/ has no heldout; this script records that by listing it.
Each sampled record is turned into a body by the builder's own extract_body, then
 (a) is its body_sha present in the same family's database?
 (b) is any field string / every field string a verbatim substring of some indexed row text
     (same family database, and all eight databases)? Candidates come from the FTS trigram LIKE
     (a superset: LIKE is case-insensitive and treats % and _ as wildcards) and are then verified
     with exact `in`; strings under 3 characters (no trigram) use a full instr() scan.
Every field-level match is listed with the indexed row it matched; none are hidden.
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CORPUS, FAMS, HELDOUT, HERE, IDX, SEED, db, dump, raw_lines_at  # noqa: E402
from tools import build_p4_corpus_index as bi  # noqa: E402

N = 200
CAP = 3000


def count_lines(rel: str) -> int:
    n, last = 0, b""
    with (CORPUS / rel).open("rb") as handle:
        while chunk := handle.read(8 << 20):
            n += chunk.count(b"\n")
            last = chunk[-1:]
    return n + (1 if last and last != b"\n" else 0)


def field_strings(rec: dict, fam: str) -> list[tuple[str, str]]:
    """(field name, string) for each string the builder would put into the body."""
    spec = bi.SOURCES[fam]
    kind = bi.extract_body(rec, fam, spec)[0]
    plan = spec["kinds"][kind if spec["kind_key"] else next(iter(spec["kinds"]))]
    out = []
    for field in plan["body"]:
        for value in bi._field_values(rec, field):
            out.append((bi._base(field), value))
    return out


class Finder:
    def __init__(self):
        self.cons = {f: db(f) for f in FAMS}
        self.cache: dict[tuple[str, str], list] = {}

    def find(self, fam: str, s: str) -> dict:
        key = (fam, s)
        if key in self.cache:
            return self.cache[key]
        con = self.cons[fam]
        if len(s) >= 3:
            rows = con.execute("SELECT r.id,r.source_file,r.line,r.text FROM search f JOIN rows r ON r.id=f.rowid "
                               "WHERE f.text LIKE ? LIMIT ?", ("%" + s + "%", CAP)).fetchall()
            capped = len(rows) >= CAP
        else:
            rows = con.execute("SELECT id,source_file,line,text FROM rows WHERE instr(text, ?) > 0 LIMIT ?", (s, CAP)).fetchall()
            capped = len(rows) >= CAP
        exact = [(r[1], r[2]) for r in rows if s in r[3]]
        res = dict(found=bool(exact), first=exact[0] if exact else None, candidates_capped=capped, via="fts_like" if len(s) >= 3 else "instr_scan")
        self.cache[key] = res
        return res


def main() -> int:
    t0 = time.perf_counter()
    files = [(fam, rel) for fam in FAMS for rel in HELDOUT[fam]]
    counts = {rel: count_lines(rel) for _, rel in files}
    total = sum(counts.values())
    out_dir = sorted(p.name for p in (CORPUS / "out").iterdir())
    rng = random.Random(SEED)
    picks = sorted(rng.sample(range(total), N))
    starts, acc = {}, 0
    for fam, rel in files:
        starts[rel] = acc
        acc += counts[rel]
    where: dict[str, set] = {}
    chosen = []
    for k in picks:
        for fam, rel in files:
            if starts[rel] <= k < starts[rel] + counts[rel]:
                ln = k - starts[rel] + 1
                where.setdefault(rel, set()).add(ln)
                chosen.append((fam, rel, ln))
                break
    fetched = {rel: raw_lines_at(CORPUS, rel, lns) for rel, lns in where.items()}
    finder = Finder()
    unextractable: dict[str, int] = {}
    per_family = {f: dict(sampled=0, extracted=0) for f in FAMS}
    body_hits, any_hits, all_hits, detail = [], [], [], []
    for fam, rel, ln in chosen:
        per_family[fam]["sampled"] += 1
        raw = fetched[rel].get(ln)
        try:
            rec = json.loads(raw)
            kind, body, used, _ = bi.extract_body(rec, fam, bi.SOURCES[fam])
            strings = field_strings(rec, fam)
        except (ValueError, json.JSONDecodeError, TypeError) as err:
            unextractable[str(err)] = unextractable.get(str(err), 0) + 1
            continue
        per_family[fam]["extracted"] += 1
        import hashlib
        bsha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        con = finder.cons[fam]
        same = con.execute("SELECT source_file,line FROM rows WHERE body_sha=? LIMIT 5", (bsha,)).fetchall()
        if same:
            n_same = con.execute("SELECT COUNT(*) FROM rows WHERE body_sha=?", (bsha,)).fetchone()[0]
            body_hits.append(dict(heldout=f"{rel}:{ln}", family=fam, body_chars=len(body), body_sha=bsha,
                                  indexed_rows_with_same_body=n_same,
                                  matched_rows_first5=[f"{a}:{b}" for a, b in same]))
        fieldres = []
        for name, s in strings:
            same_fam = finder.find(fam, s)
            others = {f: finder.find(f, s) for f in FAMS if f != fam}
            fieldres.append(dict(field=name, chars=len(s), in_same_family=same_fam["found"],
                                 same_family_first=same_fam["first"], same_family_candidates_capped=same_fam["candidates_capped"],
                                 in_other_families={f: r["first"] for f, r in others.items() if r["found"]}))
        in_same = [r for r in fieldres if r["in_same_family"]]
        in_any = [r for r in fieldres if r["in_same_family"] or r["in_other_families"]]
        rec_out = dict(heldout=f"{rel}:{ln}", family=fam, kind=kind, fields=fieldres)
        detail.append(dict(heldout=f"{rel}:{ln}", family=fam, kind=kind, field_chars=[r["chars"] for r in fieldres],
                           fields_in_same_family=len(in_same), fields_total=len(fieldres)))
        if in_any:
            any_hits.append(rec_out)
        if fieldres and len(in_same) == len(fieldres):
            all_hits.append(rec_out)
    result = dict(
        seed=SEED, sampled=N, population=total, population_by_file=counts,
        out_dir_listing=out_dir, out_has_heldout=any("heldout" in n for n in out_dir),
        per_family=per_family, unextractable_by_reason=unextractable,
        body_sha_hits=len(body_hits), body_sha_hit_records=body_hits,
        field_substring_hits=len(any_hits), field_substring_hit_records=any_hits,
        field_substring_hits_same_family=sum(1 for r in any_hits if any(f["in_same_family"] for f in r["fields"])),
        records_with_every_field_in_same_family=len(all_hits),
        per_record_summary=detail,
        note=("a field-level hit is a verbatim substring occurrence of one field string inside some indexed row text; "
              "chars gives that string's length"),
        elapsed_seconds=round(time.perf_counter() - t0, 3))
    dump(HERE / "c4_heldout_check.json", result)
    print(json.dumps({k: result[k] for k in ("seed", "sampled", "population", "body_sha_hits", "field_substring_hits",
                                             "field_substring_hits_same_family", "records_with_every_field_in_same_family",
                                             "unextractable_by_reason", "elapsed_seconds")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
