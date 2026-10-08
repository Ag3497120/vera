"""C4 (supplement R1): ALL heldout records, and the rule that removes train rows with a heldout body.

1. The heldout files are found by walking the corpus (a path component named ``heldout``); the set
   must equal the builder's ``HELDOUT`` and this directory's ``_common.HELDOUT``.
2. Every line of every heldout file is turned into a body with the builder's ``extract_body`` (the same
   extraction the index uses; lines that give no body are counted by reason, not hidden) and hashed.
   (a) how many index rows of the SAME family have that body_sha (pass condition: 0 for every family);
   (a') how many rows of the OTHER families' databases have it (information; examples listed, up to 20).
3. Independent recount of the rule: every train file is read again with ``classify_line``; rows that
   would have been indexed and whose body sha is in the same family's heldout set are counted per file and
   compared with manifest.json ``skipped.heldout_body_overlap`` (and with the planner's prediction).
Read-only on the corpus and the index. Output: c4_heldout_full.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import CORPUS, FAMS, HELDOUT, HERE, IDX, db, dump  # noqa: E402
from tools import build_p4_corpus_index as bi  # noqa: E402

# the planner's prediction (plan.md 1.2), written down only to compare against; not used to decide anything
PREDICTED = {"code/items.jsonl": 10, "even/code/items.jsonl": 10, "conversation/utterances.jsonl": 18461,
             "even/conversation/utterances.jsonl": 4247, "paraphrase_entail/train/records.jsonl": 6}


def walk_heldout() -> list[str]:
    found = []
    for dirpath, dirnames, filenames in os.walk(CORPUS):
        for name in filenames:
            rel = str((Path(dirpath) / name).relative_to(CORPUS))
            if "heldout" in Path(rel).parts:
                found.append(rel)
    return sorted(found)


def heldout_family(rel: str) -> str:
    parts = Path(rel).parts
    return parts[1] if parts[0] == "even" else parts[0]


def bodies_of(rel: str, fam: str) -> tuple[set[str], dict]:
    """Own loop (binary, newline-cut) + the builder's extract_body. Returns (sha set, per-file facts)."""
    spec = bi.SOURCES[fam]
    shas, lines, unextractable, records = set(), 0, {}, 0
    digest = hashlib.sha256()
    size = 0
    carry = b""
    pieces_all = []
    with (CORPUS / rel).open("rb") as handle:
        while chunk := handle.read(8 << 20):
            digest.update(chunk)
            size += len(chunk)
            parts = (carry + chunk).split(b"\n")
            carry = parts.pop()
            pieces_all.extend((p, True) for p in parts)
            if len(pieces_all) > 200000:
                lines, records = _consume(pieces_all, fam, spec, shas, unextractable, lines, records)
                pieces_all = []
    if carry:
        pieces_all.append((carry, False))
    lines, records = _consume(pieces_all, fam, spec, shas, unextractable, lines, records)
    return shas, dict(path=rel, bytes=size, lines=lines, sha256=digest.hexdigest(), records=records,
                      unextractable=unextractable)


def _consume(pieces, fam, spec, shas, unextractable, lines, records):
    for raw, nl in pieces:
        lines += 1
        reason = None
        if not nl:
            reason = "partial_final_line"
        elif not raw.strip():
            reason = "blank_line"
        else:
            try:
                rec = json.loads(raw.decode("utf-8"))
            except UnicodeDecodeError:
                reason = "bad_utf8"
            except json.JSONDecodeError:
                reason = "bad_json"
            else:
                if not isinstance(rec, dict):
                    reason = "not_object"
                else:
                    try:
                        body = bi.extract_body(rec, fam, spec)[1]
                    except ValueError as err:
                        reason = str(err)
        if reason:
            unextractable[reason] = unextractable.get(reason, 0) + 1
            continue
        records += 1
        shas.add(hashlib.sha256(body.encode("utf-8")).hexdigest())
    return lines, records


def recount_file(job: tuple) -> dict:
    """Rows of one train file that would be indexed and whose body sha is in the family's heldout set."""
    fam, rel, held = job
    held = set(held)
    spec = bi.SOURCES[fam]
    n_indexed_before_rule, overlap, lines = 0, 0, 0
    digest, counter = hashlib.sha256(), {}
    for _no, raw, nl in bi.read_lines(CORPUS / rel, digest, counter):
        lines += 1
        reason, row = bi.classify_line(raw, nl, fam, spec)
        if reason is None:
            n_indexed_before_rule += 1
            overlap += row["body_sha"] in held
    return dict(family=fam, path=rel, lines=lines, would_index_without_rule=n_indexed_before_rule,
                overlap_recount=overlap)


def main() -> int:
    t0 = time.perf_counter()
    m = json.loads((HERE / "manifest.json").read_text())
    out: dict = dict(manifest="artifacts/w1-c/manifest.json")
    walked = walk_heldout()
    builder_listed = sorted(rel for paths in bi.HELDOUT.values() for rel in paths)
    common_listed = sorted(rel for paths in HELDOUT.values() for rel in paths)
    out["heldout_files"] = dict(
        walked=walked, builder_HELDOUT=builder_listed, common_HELDOUT=common_listed,
        walked_equals_builder=walked == builder_listed, walked_equals_common=walked == common_listed,
        families_of_walked={rel: heldout_family(rel) for rel in walked},
        family_matches_builder_table=all(rel in bi.HELDOUT[heldout_family(rel)] for rel in walked),
        out_has_heldout=any(r.startswith("out/") for r in walked))

    held: dict[str, set[str]] = {f: set() for f in FAMS}
    per_file = []
    for rel in walked:
        fam = heldout_family(rel)
        shas, facts = bodies_of(rel, fam)
        held[fam] |= shas
        per_file.append(dict(family=fam, **facts, distinct_in_file=len(shas)))
    out["heldout_read"] = per_file

    fam_rows = []
    all_same_zero = True
    for fam in FAMS:
        shas = held[fam]
        row = dict(family=fam, heldout_files=[f["path"] for f in per_file if f["family"] == fam],
                   heldout_lines=sum(f["lines"] for f in per_file if f["family"] == fam),
                   heldout_records_with_body=sum(f["records"] for f in per_file if f["family"] == fam),
                   distinct_heldout_bodies=len(shas))
        con = db(fam)
        con.execute("CREATE TEMP TABLE h(sha TEXT PRIMARY KEY)")
        con.executemany("INSERT INTO h VALUES (?)", ((s,) for s in shas))
        row["same_family_index_rows_with_heldout_body"] = con.execute(
            "SELECT COUNT(*) FROM rows r JOIN h ON h.sha=r.body_sha").fetchone()[0]
        all_same_zero &= row["same_family_index_rows_with_heldout_body"] == 0
        con.close()
        other = {}
        examples = []
        for ofam in FAMS:
            if ofam == fam:
                continue
            oc = db(ofam)
            oc.execute("CREATE TEMP TABLE h(sha TEXT PRIMARY KEY)")
            oc.executemany("INSERT INTO h VALUES (?)", ((s,) for s in shas))
            n = oc.execute("SELECT COUNT(*) FROM rows r JOIN h ON h.sha=r.body_sha").fetchone()[0]
            other[ofam] = n
            if n and len(examples) < 20:
                for src, ln, text in oc.execute(
                        "SELECT r.source_file, r.line, substr(r.text,1,60) FROM rows r JOIN h ON h.sha=r.body_sha LIMIT ?",
                        (min(3, 20 - len(examples)),)):
                    examples.append(dict(heldout_family=fam, found_in_family=ofam, source_file=src, line=ln,
                                         text_head=text))
            oc.close()
        row["other_family_index_rows_with_heldout_body"] = other
        row["other_family_examples"] = examples
        fam_rows.append(row)
    out["by_family"] = fam_rows
    out["pass_same_family_all_zero"] = all_same_zero

    jobs = [(f["family"], f["path"], sorted(held[f["family"]])) for f in m["files"]]
    with ProcessPoolExecutor(max_workers=4) as pool:
        recounts = list(pool.map(recount_file, jobs))
    rule_rows = []
    rule_ok = True
    for rc in recounts:
        mf = next(f for f in m["files"] if f["path"] == rc["path"])
        manifest_n = mf["skipped"].get("heldout_body_overlap", 0)
        ok = rc["overlap_recount"] == manifest_n
        rule_ok &= ok
        rule_rows.append(dict(**rc, manifest_heldout_body_overlap=manifest_n, manifest_indexed=mf["indexed"],
                              planner_predicted=PREDICTED.get(rc["path"], 0),
                              recount_equals_manifest=ok,
                              manifest_equals_planner_prediction=manifest_n == PREDICTED.get(rc["path"], 0),
                              identity_would_index_minus_overlap=rc["would_index_without_rule"] - rc["overlap_recount"] == mf["indexed"]))
    out["rule_recount"] = rule_rows
    out["pass_rule_recount_equals_manifest"] = rule_ok
    out["pass_heldout_files_match_tables"] = (out["heldout_files"]["walked_equals_builder"]
                                              and out["heldout_files"]["walked_equals_common"])
    out["elapsed_seconds"] = round(time.perf_counter() - t0, 3)
    dump(HERE / "c4_heldout_full.json", out)
    for r in fam_rows:
        print(r["family"], "heldout_records", r["heldout_records_with_body"], "distinct", r["distinct_heldout_bodies"],
              "same_family_hits", r["same_family_index_rows_with_heldout_body"],
              "other_family_hits", sum(r["other_family_index_rows_with_heldout_body"].values()))
    for r in rule_rows:
        print(r["path"], "overlap", r["overlap_recount"], "manifest", r["manifest_heldout_body_overlap"],
              "predicted", r["planner_predicted"], r["recount_equals_manifest"])
    print("heldout files match tables:", out["pass_heldout_files_match_tables"],
          "| same-family all zero:", all_same_zero, "| rule recount == manifest:", rule_ok,
          "| elapsed", out["elapsed_seconds"])
    return 0 if (all_same_zero and rule_ok and out["pass_heldout_files_match_tables"]) else 1


if __name__ == "__main__":
    sys.exit(main())
