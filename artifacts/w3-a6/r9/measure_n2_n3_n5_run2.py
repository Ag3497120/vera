#!/usr/bin/env python3
"""Remeasure N2, N3 and N5 on run2; retain run1 as the N2 comparison."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

from verantyx import coarse_place as cp
import verantyx.coarse_types as ct

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/w3-a6"
R9_ART = ART / "r9"
EXPECT = ROOT / "tests/coarse_place/data/w3a6_expect.json"
R8 = Path("/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2")
R1 = ROOT / "build/coarse-W3a/full/r9/run1"
R2 = ROOT / "build/coarse-W3a/full/r9/run2"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                              for row in rows), encoding="utf-8")


def open_db(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path / 'placement.sqlite'}?mode=ro", uri=True)


def role_record(placement: Path, con: sqlite3.Connection, word: str, particle: str, role: str) -> dict:
    raw = con.execute("SELECT frame FROM role_frames WHERE word=?", (word,)).fetchone()
    frame = json.loads(raw[0]) if raw else None
    ev = con.execute("SELECT arm,src,type,n,base FROM evidence WHERE word=? ORDER BY arm,src,type", (word,)).fetchall()
    checked = ct.role_frame_check(frame, ev, json.loads((placement / "manifest.json").read_text())[
        "config"]) if frame is not None else None
    answer = cp.query(word, placement=str(placement))
    claims = (frame or {}).get(particle, [])
    matches = [item for item in claims if item["role"] == role]
    confirmed = [item for item in (answer.get("role_frame") or {}).get(particle, []) if item["role"] == role]
    unconfirmed = [item for item in (answer.get("role_frame_unconfirmed") or {}).get(particle, [])
                   if item["role"] == role]
    backing = []
    if checked and confirmed:
        for item in confirmed:
            for source in item["backed_by"]:
                arm = checked["arms"].get(source, {})
                backing.append({
                    "source": source,
                    "significant_types_for_particle": arm.get("types", {}).get(particle, []),
                    "voted_types_for_expected_role": arm.get("votes", {}).get(particle, {}).get(role, []),
                    "split": [s for s in arm.get("split", []) if s["particle"] == particle],
                })
    is_backed = None
    if confirmed:
        is_backed = bool(backing) and all(
            b["voted_types_for_expected_role"]
            and set(b["voted_types_for_expected_role"]).issubset(set(b["significant_types_for_particle"]))
            for b in backing
        )
    return {
        "generated_claims_for_particle": claims,
        "expected_role_claimed": bool(matches),
        "query_role_frame_status": answer.get("role_frame_status"),
        "confirmed_expected_role": confirmed,
        "unconfirmed_expected_role": unconfirmed,
        "backing_arms": backing,
        "confirmed_is_backed": is_backed,
    }


expect = json.loads(EXPECT.read_text(encoding="utf-8"))
manifest2 = json.loads((R2 / "manifest.json").read_text(encoding="utf-8"))
con1, con2 = open_db(R1), open_db(R2)
n2_rows = []
for item in expect["roles"]:
    word, particle, role = item["pred"], item["particle"], item["role"]
    one = role_record(R1, con1, word, particle, role)
    two = role_record(R2, con2, word, particle, role)
    n2_rows.append({"predicate": word, "particle": particle, "expected_role": role,
                    "run1": one, "run2": two,
                    "claim_changed": one["expected_role_claimed"] != two["expected_role_claimed"],
                    "confirmation_changed": (bool(one["confirmed_expected_role"])
                                              != bool(two["confirmed_expected_role"]))})

def n2_summary(key: str) -> dict:
    counts = Counter(row[key]["query_role_frame_status"] for row in n2_rows)
    return {
        "expected_predicates": len({row["predicate"] for row in n2_rows}),
        "expected_role_rows": len(n2_rows),
        "claimed_expected_roles": sum(row[key]["expected_role_claimed"] for row in n2_rows),
        "confirmed_expected_roles": sum(bool(row[key]["confirmed_expected_role"]) for row in n2_rows),
        "unconfirmed_expected_roles": sum(bool(row[key]["unconfirmed_expected_role"]) for row in n2_rows),
        "status_counts_by_expected_row": dict(sorted(counts.items())),
        "confirmed_backing_checks_pass": all(
            row[key]["confirmed_is_backed"] is True for row in n2_rows
            if row[key]["confirmed_expected_role"]
        ),
    }

n2_result = {"run1": n2_summary("run1"), "run2": n2_summary("run2"),
             "changed_claim_rows": sum(r["claim_changed"] for r in n2_rows),
             "changed_confirmation_rows": sum(r["confirmation_changed"] for r in n2_rows)}
write_jsonl(R9_ART / "n2_run1_vs_run2.jsonl", n2_rows)
(R9_ART / "n2_run1_vs_run2_summary.json").write_text(
    json.dumps(n2_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# N3: requery all required terms and compare every r8 PLACE noun decision with run2.
n3_required = []
for word in expect["relative_position"]:
    answer = cp.query(word, placement=str(R2))
    top = answer.get("top") or []
    lone = answer.get("state") == "DECIDED" and answer.get("origin") == "direct" and top == ["PLACE"]
    n3_required.append({"word": word, "state": answer.get("state"), "origin": answer.get("origin"),
                        "top": top, "lone_direct_place": lone})
write_jsonl(R9_ART / "n3_required_words_run2.jsonl", n3_required)

visual = {row["word"]: row for row in read_jsonl(ART / "n3_relpos_visual_labels_r7.jsonl")}
con2.execute("ATTACH DATABASE ? AS r8", (f"file:{R8 / 'placement.sqlite'}?mode=ro",))
changes = []
place_rows = con2.execute(
    "SELECT word,state,origin,top,n_seen FROM r8.headwords "
    "WHERE ns='N' AND (top='PLACE' OR top LIKE 'PLACE,%' OR top LIKE '%,PLACE,%' OR top LIKE '%,PLACE') "
    "ORDER BY word"
).fetchall()
for word, state8, origin8, top8, n_seen in place_rows:
    row2 = con2.execute("SELECT state,origin,top FROM headwords WHERE word=?", (word,)).fetchone()
    if row2 is None or (state8, origin8, top8) == row2:
        continue
    label = visual.get(word)
    changes.append({
        "word": word,
        "before": {"state": state8, "origin": origin8, "top": top8.split(",") if top8 else []},
        "after": {"state": row2[0], "origin": row2[1], "top": row2[2].split(",") if row2[2] else []},
        "n_seen": n_seen,
        "visual_label": label["visual_label"] if label else "未評価",
        "visual_note": label["note"] if label else None,
    })
write_jsonl(R9_ART / "n3_place_changes_run2.jsonl", changes)
labels = Counter(row["visual_label"] for row in changes)
n3_summary = {
    "required_terms": len(n3_required),
    "required_terms_not_lone_direct_place": sum(not row["lone_direct_place"] for row in n3_required),
    "required_terms_lone_direct_place": sum(row["lone_direct_place"] for row in n3_required),
    "changed_nouns_from_place": len(changes),
    "changed_noun_visual_labels": dict(sorted(labels.items())),
    "changed_noun_obvious_errors": labels["誤り"],
    "changed_noun_obvious_error_rate": labels["誤り"] / len(changes) if changes else None,
    "changed_noun_unassessed": labels["未評価"],
    "run2_configured_role_frame_min_sources": manifest2["config"]["role_frame_min_sources"],
}
(R9_ART / "n3_summary_run2.json").write_text(json.dumps(n3_summary, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")

# N5: compare the frozen 281 predicate seeds with r8 and also show run1->run2.
seed_words = [row["word"] for row in read_jsonl(ART / "n5_seed_words_prefreeze.jsonl")]
n5_rows, n5_diffs = [], []
for word in seed_words:
    q8, q1, q2 = (cp.query(word, placement=str(path)) for path in (R8, R1, R2))
    projection = lambda answer: {key: answer.get(key) for key in ("namespace", "state", "origin", "top")}
    p8, p1, p2 = projection(q8), projection(q1), projection(q2)
    row = {"word": word, "r8": p8, "run1": p1, "run2": p2,
           "same_r8_run2": p8 == p2, "same_run1_run2": p1 == p2}
    n5_rows.append(row)
    if not row["same_r8_run2"] or not row["same_run1_run2"]:
        n5_diffs.append(row)
write_jsonl(R9_ART / "n5_seed_comparison_run2.jsonl", n5_rows)
write_jsonl(R9_ART / "n5_seed_differences_run2.jsonl", n5_diffs)
n5_result = {
    "seed_words": len(seed_words),
    "same_r8_run2": sum(row["same_r8_run2"] for row in n5_rows),
    "different_r8_run2": sum(not row["same_r8_run2"] for row in n5_rows),
    "same_run1_run2": sum(row["same_run1_run2"] for row in n5_rows),
    "different_run1_run2": sum(not row["same_run1_run2"] for row in n5_rows),
    "differences": n5_diffs,
}
(R9_ART / "n5_summary_run2.json").write_text(json.dumps(n5_result, ensure_ascii=False, indent=2) + "\n",
                                               encoding="utf-8")
con1.close()
con2.close()
print(json.dumps({"N2": n2_result, "N3": n3_summary, "N5": n5_result}, ensure_ascii=False, indent=2))
