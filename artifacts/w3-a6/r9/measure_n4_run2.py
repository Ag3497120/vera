#!/usr/bin/env python3
"""Remeasure N4 on the final run2 placement at all preregistered D9 thresholds."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter
from pathlib import Path

import verantyx.coarse_types as ct
from verantyx import coarse_place as cp

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/w3-a6/r9"
RUN2 = ROOT / "build/coarse-W3a/full/r9/run2"
SAMPLE = ART / "n4_claims_run2_prefreeze.jsonl"
LABELS = ART / "n4_visual_labels_run2.jsonl"
OUT = ART / "n4_d9_run2_final.json"
DETAILS = ART / "n4_confirmed_roles_run2_final.jsonl"


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


sample = read_jsonl(SAMPLE)
visual = {(r["word"], r["particle"], r["role"]): r for r in read_jsonl(LABELS)}
manifest = json.loads((RUN2 / "manifest.json").read_text(encoding="utf-8"))
cfg_base = dict(manifest["config"])
con = sqlite3.connect(f"file:{RUN2 / 'placement.sqlite'}?mode=ro", uri=True)
frames = {}
evidence = {}
for row in sample:
    word = row["word"]
    result = con.execute("SELECT frame FROM role_frames WHERE word=?", (word,)).fetchone()
    if result:
        frames[word] = json.loads(result[0])
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
        answer = cp.query(word, placement=str(RUN2)) if threshold == cfg_base["role_frame_min_sources"] else None
        if frame is None:
            word_status["NO_ROLE_FRAME"] += 1
            if answer is not None and (answer.get("role_frame_status"), answer.get("role_frame"),
                                       answer.get("role_frame_unconfirmed")) != ("NO_ROLE_FRAME", None, None):
                query_mismatches.append({"word": word, "threshold": threshold,
                                         "actual": [answer.get("role_frame_status"), answer.get("role_frame"),
                                                    answer.get("role_frame_unconfirmed")],
                                         "expected": ["NO_ROLE_FRAME", None, None]})
            continue
        checked = ct.role_frame_check(frame, evidence[word], cfg)
        word_status[checked["status"]] += 1
        if answer is not None:
            expected = (checked["status"], checked["confirmed"] if checked["status"] == "CONFIRMED" else None,
                        checked["unconfirmed"])
            actual = (answer.get("role_frame_status"), answer.get("role_frame"),
                      answer.get("role_frame_unconfirmed"))
            if actual != expected:
                query_mismatches.append({"word": word, "threshold": threshold,
                                         "actual": actual, "expected": expected})
        for particle, roles in checked["confirmed"].items():
            for role in roles:
                label = visual.get((word, particle, role["role"]))
                if label is None:
                    raise SystemExit(f"confirmed role lacks a frozen label: {word}/{particle}/{role['role']}")
                confirmed.append({
                    "word": word,
                    "particle": particle,
                    "role": role["role"],
                    "types": role["types"],
                    "backed_by": role["backed_by"],
                    "visual_label": label["visual_label"],
                    "visual_note": label["note"],
                })
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

selected = int(cfg_base["role_frame_min_sources"])
selected_row = summary[str(selected)]
result = {
    "thresholds": summary,
    "configured_role_frame_min_sources": selected,
    "n4_meets_threshold": bool(selected_row["confirmed_role_rows"]
                                 and selected_row["obvious_error_rate"] <= 0.10),
    "query_projection_mismatches": query_mismatches,
    "sample_sha256": sha(SAMPLE),
    "visual_labels_sha256": sha(LABELS),
    "run2_content_sha256": manifest["content_sha256"],
}
OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
DETAILS.write_text(
    "".join(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n" for r in details),
    encoding="utf-8",
)
result["summary_sha256"] = sha(OUT)
result["confirmed_roles_sha256"] = sha(DETAILS)
print(json.dumps(result, ensure_ascii=False, indent=2))
if query_mismatches:
    raise SystemExit("query and shared role_frame_check disagree")
