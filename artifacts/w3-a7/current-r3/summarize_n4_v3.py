#!/usr/bin/env python3
"""Summarize the registered N4 visual review without treating testimony as gold."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/w3-a7/current-r3"
CLAIMS = ART / "n4_claims_v3_prefreeze.jsonl"
CLAIM_FREEZE = ART / "n4_claims_v3_prefreeze.sha256.json"
LABELS = ART / "n4_visual_labels_v3.jsonl"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    claims = read_jsonl(CLAIMS)
    frozen = read_json(CLAIM_FREEZE)
    if hashlib.sha256(CLAIMS.read_bytes()).hexdigest() != frozen["sha256"]:
        raise SystemExit("N4 claims changed after the pre-label freeze")
    labels = read_jsonl(LABELS)
    key = lambda row: (row["word"], row["particle"], row["role"])
    claim_by_key = {key(row): row for row in claims}
    label_by_key = {key(row): row for row in labels}
    if len(label_by_key) != len(labels) or set(label_by_key) != set(claim_by_key):
        raise SystemExit("N4 labels do not cover the frozen claim keys exactly once")
    for claim_key, claim in claim_by_key.items():
        label = label_by_key[claim_key]
        if label["types"] != claim["types"] or label["confirmed"] != claim["confirmed"]:
            raise SystemExit(f"N4 label does not match frozen claim: {claim_key}")
        if label.get("evidence_type") != "testimony":
            raise SystemExit(f"N4 label missing testimony type: {claim_key}")

    confirmed = [claim for claim in claims if claim["confirmed"]]
    confirmed_labels = [label_by_key[key(claim)] for claim in confirmed]
    all_counts = Counter(row["visual_label"] for row in labels)
    confirmed_counts = Counter(row["visual_label"] for row in confirmed_labels)
    errors = confirmed_counts["誤り"]
    unclassified = confirmed_counts["UNCLASSIFIED"]
    upper_rate = (errors + unclassified) / len(confirmed) if confirmed else None
    status = "PASS" if confirmed and upper_rate <= 0.10 else "UNKNOWN" if not confirmed else "FAIL"
    result = {
        "sample_words": len(read_jsonl(ART / "n4_words_r10_v3.jsonl")),
        "claims_reviewed": len(claims),
        "confirmed_roles_denominator": len(confirmed),
        "all_claim_visual_labels": dict(sorted(all_counts.items())),
        "confirmed_role_visual_labels": dict(sorted(confirmed_counts.items())),
        "confirmed_role_obvious_errors": errors,
        "confirmed_role_unclassified": unclassified,
        "confirmed_role_clear_error_rate": errors / len(confirmed) if confirmed else None,
        "conservative_upper_rate_errors_plus_unclassified": upper_rate,
        "threshold": 0.10,
        "status": status,
        "visual_labels_are_gold": False,
        "visual_label_evidence_type": "testimony",
        "reviewer": "Codex gpt-6-luna",
        "claims_sha256": frozen["sha256"],
        "labels_sha256": hashlib.sha256(LABELS.read_bytes()).hexdigest(),
        "unconfirmed_claims_not_in_N4_denominator": sum(not claim["confirmed"] for claim in claims),
    }
    (ART / "n4_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    lines = ["|語|助詞|役割|確認|目視ラベル|型 (申告)|根拠腕|判定メモ|",
             "|---|---|---|---|---|---|---|---|"]
    for claim in claims:
        label = label_by_key[key(claim)]
        lines.append("|{word}|{particle}|{role}|{confirmed}|{visual_label}|{types}|{arms}|{note}|".format(
            word=claim["word"], particle=claim["particle"], role=claim["role"],
            confirmed="CONFIRMED" if claim["confirmed"] else "unconfirmed",
            visual_label=label["visual_label"], types=", ".join(claim["types"]),
            arms=", ".join(claim["backed_by"]) or "なし", note=label["note"].replace("|", "/")))
    (ART / "n4_visual_review_v3.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
