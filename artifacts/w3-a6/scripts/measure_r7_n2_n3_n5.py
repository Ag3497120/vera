#!/usr/bin/env python3
"""Measure the frozen W3-a6 N2, N3 and N5 inputs against r8 and r9."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

import verantyx.coarse_types as ct
from verantyx import coarse_place as cp

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/w3-a6"
EXPECT = ROOT / "tests/coarse_place/data/w3a6_expect.json"
R8 = Path("/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2")
R9 = ROOT / "build/coarse-W3a/full/r9/run1"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def db(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path / 'placement.sqlite'}?mode=ro", uri=True)


expect = json.loads(EXPECT.read_text(encoding="utf-8"))
manifest = json.loads((R9 / "manifest.json").read_text(encoding="utf-8"))
cfg = manifest["config"]
con9 = db(R9)
con8 = db(R8)

# N2: one report row per preregistered particle-role expectation.
n2_rows = []
for expected in expect["roles"]:
    word, particle, role = expected["pred"], expected["particle"], expected["role"]
    raw_row = con9.execute("SELECT frame FROM role_frames WHERE word=?", (word,)).fetchone()
    raw_frame = json.loads(raw_row[0]) if raw_row else None
    ev_rows = con9.execute("SELECT arm,src,type,n,base FROM evidence WHERE word=? ORDER BY arm,src,type", (word,)).fetchall()
    checked = ct.role_frame_check(raw_frame, ev_rows, cfg) if raw_frame is not None else None
    answer = cp.query(word, placement=str(R9))
    raw_claims = (raw_frame or {}).get(particle, [])
    matching_claims = [item for item in raw_claims if item["role"] == role]
    confirmed = [item for item in (answer.get("role_frame") or {}).get(particle, []) if item["role"] == role]
    unconfirmed = [item for item in (answer.get("role_frame_unconfirmed") or {}).get(particle, []) if item["role"] == role]
    backed = []
    if checked and confirmed:
        for row in confirmed:
            for source in row["backed_by"]:
                arm = checked["arms"].get(source, {})
                backed.append({
                    "source": source,
                    "significant_types_for_particle": arm.get("types", {}).get(particle, []),
                    "voted_types_for_expected_role": arm.get("votes", {}).get(particle, {}).get(role, []),
                    "split": [s for s in arm.get("split", []) if s["particle"] == particle],
                })
    n2_rows.append({
        "predicate": word,
        "particle": particle,
        "expected_role": role,
        "generated_claims_for_particle": raw_claims,
        "expected_role_claimed": bool(matching_claims),
        "query_role_frame_status": answer.get("role_frame_status"),
        "confirmed_expected_role": confirmed,
        "unconfirmed_expected_role": unconfirmed,
        "backing_arms": backed,
        "claim_matches_expected": bool(matching_claims),
        "confirmed_is_backed": all(
            b["voted_types_for_expected_role"] and
            set(b["voted_types_for_expected_role"]).issubset(set(b["significant_types_for_particle"]))
            for b in backed
        ) if confirmed else None,
    })
write_jsonl(ART / "n2_predicate_role_rows_r7.jsonl", n2_rows)
n2_counts = Counter(r["query_role_frame_status"] for r in n2_rows)
n2_summary = {
    "expected_predicates": len({r["predicate"] for r in n2_rows}),
    "expected_role_rows": len(n2_rows),
    "claimed_expected_roles": sum(r["expected_role_claimed"] for r in n2_rows),
    "confirmed_expected_roles": sum(bool(r["confirmed_expected_role"]) for r in n2_rows),
    "unconfirmed_expected_roles": sum(bool(r["unconfirmed_expected_role"]) for r in n2_rows),
    "confirmed_backing_checks_pass": all(r["confirmed_is_backed"] for r in n2_rows if r["confirmed_expected_role"]),
    "query_status_counts_by_expected_row": dict(sorted(n2_counts.items())),
}
(ART / "n2_predicate_role_summary_r7.json").write_text(json.dumps(n2_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# N3: query the 15 frozen terms and require none to remain a lone direct PLACE.
n3_targets = []
for word in expect["relative_position"]:
    answer = cp.query(word, placement=str(R9))
    top = answer.get("top") or []
    is_lone_direct_place = answer.get("state") == "DECIDED" and answer.get("origin") == "direct" and top == ["PLACE"]
    n3_targets.append({"word": word, "state": answer.get("state"), "origin": answer.get("origin"),
                       "top": top, "lone_direct_place": is_lone_direct_place})
write_jsonl(ART / "n3_required_words_r7.jsonl", n3_targets)

# N3 full change list: every noun whose r8 top contained PLACE and whose
# state/origin/top changed in r9; labels were frozen from claims before this query.
before = {r[0]: r[1:] for r in con8.execute("SELECT word,ns,state,origin,top,n_seen FROM headwords")}
after = {r[0]: r[1:] for r in con9.execute("SELECT word,ns,state,origin,top,n_seen FROM headwords")}
visual = {r["word"]: r for r in read_jsonl(ART / "n3_relpos_visual_labels_r7.jsonl")}
n3_changes = []
for word in sorted(set(before) & set(after)):
    b, a = before[word], after[word]
    if b[0] != "N" or "PLACE" not in (b[3] or "").split(","):
        continue
    before_projection, after_projection = b[1:4], a[1:4]
    if before_projection == after_projection:
        continue
    label = visual.get(word)
    n3_changes.append({
        "word": word,
        "before": {"state": b[1], "origin": b[2], "top": (b[3] or "").split(",") if b[3] else []},
        "after": {"state": a[1], "origin": a[2], "top": (a[3] or "").split(",") if a[3] else []},
        "n_seen": b[4],
        "visual_label": label["visual_label"] if label else "未評価",
        "visual_note": label["note"] if label else None,
    })
write_jsonl(ART / "n3_place_changes_r7.jsonl", n3_changes)
n3_label_counts = Counter(r["visual_label"] for r in n3_changes)
n3_summary = {
    "required_terms": len(n3_targets),
    "required_terms_not_lone_direct_place": sum(not r["lone_direct_place"] for r in n3_targets),
    "required_terms_lone_direct_place": sum(r["lone_direct_place"] for r in n3_targets),
    "changed_nouns_from_place": len(n3_changes),
    "changed_noun_visual_labels": dict(sorted(n3_label_counts.items())),
    "changed_noun_obvious_errors": n3_label_counts["誤り"],
    "changed_noun_obvious_error_rate": n3_label_counts["誤り"] / len(n3_changes) if n3_changes else None,
    "changed_noun_unassessed": n3_label_counts["未評価"],
}
(ART / "n3_summary_r7.json").write_text(json.dumps(n3_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# N5: the 281 unique SEEDS_PRED are frozen before either query; compare the
# public query's namespace/state/origin/top without selecting a winner.
seed_words = [row["word"] for row in read_jsonl(ART / "n5_seed_words_prefreeze.jsonl")]
n5_rows, n5_diffs = [], []
for word in seed_words:
    q8 = cp.query(word, placement=str(R8))
    q9 = cp.query(word, placement=str(R9))
    projection8 = {k: q8.get(k) for k in ("namespace", "state", "origin", "top")}
    projection9 = {k: q9.get(k) for k in ("namespace", "state", "origin", "top")}
    row = {"word": word, "r8": projection8, "r9": projection9, "same": projection8 == projection9}
    n5_rows.append(row)
    if not row["same"]:
        n5_diffs.append(row)
write_jsonl(ART / "n5_seed_comparison_r7.jsonl", n5_rows)
write_jsonl(ART / "n5_seed_differences_r7.jsonl", n5_diffs)
n5_summary = {"seed_words": len(seed_words), "same": len(n5_rows) - len(n5_diffs),
              "different": len(n5_diffs), "differences": n5_diffs}
(ART / "n5_summary_r7.json").write_text(json.dumps(n5_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

con8.close()
con9.close()
print(json.dumps({"N2": n2_summary, "N3": n3_summary, "N5": n5_summary}, ensure_ascii=False, indent=2))
