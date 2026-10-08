"""C1 independent re-count: do not trust the builder's own numbers.

Re-reads every input file in binary (own code, not the builder's reader), recomputes
bytes / physical lines / sha256, compares with manifest.json; reads every database with
GROUP BY source_file; checks the identity lines == indexed + skipped; checks that no
database row comes from heldout / overlap_dropped; and takes 20 random rows per family
(seed 20261002) back to their physical line in the source file.
"""
from __future__ import annotations

import hashlib
import json
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CORPUS, FAMS, HERE, IDX, SEED, db, dump, raw_lines_at  # noqa: E402


def recount(path: Path) -> dict:
    digest, size, newlines, last = hashlib.sha256(), 0, 0, b""
    with path.open("rb") as handle:
        while chunk := handle.read(8 << 20):
            digest.update(chunk)
            size += len(chunk)
            newlines += chunk.count(b"\n")
            last = chunk[-1:]
    return dict(bytes=size, lines=newlines + (1 if size and last != b"\n" else 0), sha256=digest.hexdigest(),
                newlines=newlines)


def main() -> int:
    t0 = time.perf_counter()
    m = json.loads((HERE / "manifest.json").read_text())
    out: dict = dict(manifest="artifacts/w1-c/manifest.json", seed=SEED, files=[], families=[], checks={})
    ok = True
    for f in m["files"]:
        r = recount(CORPUS / f["path"])
        row = dict(path=f["path"], recount=r, manifest=dict(bytes=f["bytes"], lines=f["lines"], sha256=f["sha256"]),
                   bytes_match=r["bytes"] == f["bytes"], lines_match=r["lines"] == f["lines"],
                   sha256_match=r["sha256"] == f["sha256"],
                   identity=f["lines"] == f["indexed"] + sum(f["skipped"].values()))
        ok &= all(row[k] for k in ("bytes_match", "lines_match", "sha256_match", "identity"))
        out["files"].append(row)
    # R1: the heldout files the builder read (families[f].heldout.files[]) re-counted independently, and compared
    # with the manifest's excluded[] entry of the same path (hashed by a different function of the builder).
    excluded = {e["path"]: e for e in m.get("excluded", [])}
    out["heldout"] = []
    for fam, info in m["families"].items():
        h = info.get("heldout")
        if h is None:
            continue
        for hf in h["files"]:
            r = recount(CORPUS / hf["path"])
            ex = excluded.get(hf["path"])
            row = dict(family=fam, path=hf["path"], recount=r,
                       manifest=dict(bytes=hf["bytes"], lines=hf["lines"], sha256=hf["sha256"]),
                       matches_recount=(r["bytes"], r["lines"], r["sha256"]) == (hf["bytes"], hf["lines"], hf["sha256"]),
                       matches_excluded_entry=ex is not None and (ex["bytes"], ex["lines"], ex["sha256"]) == (hf["bytes"], hf["lines"], hf["sha256"]),
                       unextractable=hf["unextractable"])
            ok &= row["matches_recount"] and row["matches_excluded_entry"]
            out["heldout"].append(row)
    out["heldout_unlisted"] = m.get("heldout_unlisted")
    ok &= m.get("heldout_unlisted") == []
    ok &= all(f["family"] in m["families"] and "heldout" in m["families"][f["family"]] for f in m["files"])
    # two files re-counted by the system tools
    sysrows = []
    for rel in ("figurative_commonsense/train/records.jsonl", "narrative/train/records.jsonl"):
        wc = subprocess.run(["wc", "-l", str(CORPUS / rel)], capture_output=True, text=True).stdout.split()[0]
        sh = subprocess.run(["shasum", "-a", "256", str(CORPUS / rel)], capture_output=True, text=True).stdout.split()[0]
        mf = next(x for x in m["files"] if x["path"] == rel)
        sysrows.append(dict(path=rel, wc_l=int(wc), shasum=sh, manifest_newlines_equal=int(wc) == mf["lines"] - (0 if mf["final_newline"] else 1),
                            manifest_sha_equal=sh == mf["sha256"]))
        ok &= sysrows[-1]["manifest_newlines_equal"] and sysrows[-1]["manifest_sha_equal"]
    out["system_tool_recount"] = sysrows
    rng = random.Random(SEED)
    for fam in FAMS:
        con = db(fam)
        groups = dict(con.execute("SELECT source_file, COUNT(*) FROM rows GROUP BY source_file"))
        total = con.execute("SELECT COUNT(*) FROM rows").fetchone()[0]
        meta = dict(con.execute("SELECT key,value FROM meta"))
        mine = {f["path"]: f["indexed"] for f in m["files"] if f["family"] == fam}
        bad_excluded = con.execute("SELECT COUNT(*) FROM rows WHERE source_file LIKE '%heldout%' "
                                   "OR source_file LIKE '%overlap_dropped%'").fetchone()[0]
        fam_values = [r[0] for r in con.execute("SELECT DISTINCT family FROM rows")]
        origins = [r[0] for r in con.execute("SELECT DISTINCT origin FROM rows")]
        # random round trips
        rows = [con.execute("SELECT id,source_file,line,sha,body_sha FROM rows WHERE id=?",
                            (rng.randint(1, total),)).fetchone() for _ in range(20)]
        trips = []
        per_file: dict[str, set] = {}
        for _id, sf, ln, *_ in rows:
            per_file.setdefault(sf, set()).add(ln)
        found = {sf: raw_lines_at(CORPUS, sf, lns) for sf, lns in per_file.items()}
        for rid, sf, ln, sha, body_sha in rows:
            line = found[sf].get(ln)
            rec = json.loads(line) if line else None
            trips.append(dict(id=rid, source_file=sf, line=ln, row_sha=sha,
                              source_sha=None if rec is None else rec.get("sha"),
                              match=rec is not None and str(rec.get("sha")) == sha))
        fam_ok = (groups == mine and total == sum(mine.values()) == int(meta["rows"]) and bad_excluded == 0
                  and fam_values == [fam] and origins == ["generated"] and all(t["match"] for t in trips))
        ok &= fam_ok
        out["families"].append(dict(family=fam, db_rows=total, meta_rows=int(meta["rows"]), group_by_source_file=groups,
                                    manifest_indexed=mine, group_by_matches_manifest=groups == mine,
                                    rows_from_heldout_or_overlap_dropped=bad_excluded,
                                    distinct_family_values=fam_values, distinct_origin_values=origins,
                                    random_round_trips=dict(n=len(trips), all_match=all(t["match"] for t in trips), items=trips),
                                    ok=fam_ok))
        con.close()
    out["checks"] = dict(all_ok=bool(ok), files=len(m["files"]), elapsed_seconds=round(time.perf_counter() - t0, 3))
    dump(HERE / "check_manifest.json", out)
    print(json.dumps(out["checks"], ensure_ascii=False))
    for fam in out["families"]:
        print(fam["family"], fam["db_rows"], "ok" if fam["ok"] else "NOT OK")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
