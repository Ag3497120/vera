#!/usr/bin/env python3
"""Measure the frozen N4 sample at the D9 source thresholds using r9 evidence."""
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
PLACEMENT = ROOT / "build/coarse-W3a/full/r9/run1"
DB = PLACEMENT / "placement.sqlite"
LABELS = ART / "n4_visual_labels_r7.jsonl"
SAMPLE = ART / "n4_claims_prefreeze.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


sample = read_jsonl(SAMPLE)
label_rows = read_jsonl(LABELS)
labels = {}
for row in label_rows:
    for item in row["roles"]:
        labels[(row["word"], item["particle"], item["role"])] = item

manifest = json.loads((PLACEMENT / "manifest.json").read_text(encoding="utf-8"))
cfg_base = dict(manifest["config"])
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
frames: dict[str, dict] = {}
evidence: dict[str, list[tuple]] = {}
for row in sample:
    word = row["word"]
    fr = con.execute("SELECT frame FROM role_frames WHERE word=?", (word,)).fetchone()
    if fr:
        frames[word] = json.loads(fr[0])
    evidence[word] = con.execute(
        "SELECT arm,src,type,n,base FROM evidence WHERE word=? ORDER BY arm,src,type", (word,)
    ).fetchall()
con.close()

summary = {}
details = []
query_mismatches = []
for threshold in (1, 2, 3):
    cfg = dict(cfg_base)
    cfg["role_frame_min_sources"] = threshold
    word_status = Counter()
    confirmed = []
    for row in sample:
        word = row["word"]
        frame = frames.get(word)
        if frame is None:
            word_status["NO_ROLE_FRAME"] += 1
            checked = None
        else:
            checked = ct.role_frame_check(frame, evidence[word], cfg)
            word_status[checked["status"]] += 1
            for particle, roles in checked["confirmed"].items():
                for role in roles:
                    visual = labels.get((word, particle, role["role"]))
                    if visual is None:
                        raise SystemExit(f"confirmed role lacks a frozen visual label: {word}/{particle}/{role['role']}")
                    confirmed.append({
                        "word": word,
                        "particle": particle,
                        "role": role["role"],
                        "types": role["types"],
                        "backed_by": role["backed_by"],
                        "visual_label": visual["visual_label"],
                    })
        if threshold == 1:
            answer = cp.query(word, placement=str(PLACEMENT))
            if frame is None:
                expected = ("NO_ROLE_FRAME", None, None)
            else:
                expected = (checked["status"], checked["confirmed"] if checked["status"] == "CONFIRMED" else None,
                            checked["unconfirmed"])
            actual = (answer.get("role_frame_status"), answer.get("role_frame"), answer.get("role_frame_unconfirmed"))
            if actual != expected:
                query_mismatches.append({"word": word, "actual": actual, "expected": expected})
    counts = Counter(item["visual_label"] for item in confirmed)
    n_confirmed = len(confirmed)
    n_errors = counts["誤り"]
    summary[str(threshold)] = {
        "role_frame_min_sources": threshold,
        "sample_words": len(sample),
        "sample_word_status": dict(sorted(word_status.items())),
        "confirmed_role_rows": n_confirmed,
        "confirmed_visual_labels": dict(sorted(counts.items())),
        "confirmed_obvious_errors": n_errors,
        "obvious_error_rate": n_errors / n_confirmed if n_confirmed else None,
        "rate_is_unmeasured": n_confirmed == 0,
    }
    details.extend({"threshold": threshold, **item} for item in confirmed)

out = ART / "n4_d9_thresholds_r7.json"
out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
details_out = ART / "n4_d9_confirmed_roles_r7.jsonl"
details_out.write_text("".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in details), encoding="utf-8")
meta = {
    "candidate_content_sha256": manifest["content_sha256"],
    "sample_sha256": sha256(SAMPLE),
    "visual_labels_sha256": sha256(LABELS),
    "thresholds_sha256": sha256(out),
    "confirmed_roles_sha256": sha256(details_out),
    "query_projection_mismatches_at_threshold_1": query_mismatches,
}
(ART / "n4_d9_thresholds_r7.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"summary": summary, "meta": meta}, ensure_ascii=False, indent=2))
if query_mismatches:
    raise SystemExit("r9 query role-frame projection differs from role_frame_check")
