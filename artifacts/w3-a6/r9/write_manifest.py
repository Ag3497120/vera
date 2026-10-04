#!/usr/bin/env python3
"""Write the measured run1/run2 and generation comparison manifest without reading ledgers."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
R9 = ROOT / "build/coarse-W3a/full/r9"
ART = ROOT / "artifacts/w3-a6/r9"
R1 = R9 / "run1"
R2 = R9 / "run2"
SUMMARIES = {
    "gen_ntype": R9 / "gen_ntype/summary.json",
    "gen_role_run1": R9 / "gen_role/summary.json",
    "gen_role_v2": R9 / "gen_role_v2/summary.json",
}
OUTPUT = ART / "manifest.json"
PARTICLES = ("が", "を", "に", "で", "へ", "と", "から", "まで", "より")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generation(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "summary_path": str(path.relative_to(ROOT)),
        "summary_sha256": sha(path),
        "kind": data.get("kind"),
        "model": data.get("model"),
        "effort": data.get("effort"),
        "calls": data.get("calls"),
        "batches_total": data.get("batches_total"),
        "batches_ok": data.get("batches_ok"),
        "batches_failed": data.get("batches_failed"),
        "words_requested": data.get("words_requested"),
        "words_answered": data.get("words_answered"),
        "words_abstained": data.get("words_abstained"),
        "words_missing": data.get("words_missing"),
        "words_invalid": data.get("words_invalid"),
        "words_frame_dup_particle": data.get("words_frame_dup_particle"),
        "wall_sec": data.get("wall_sec"),
        "sum_call_sec": data.get("sum_call_sec"),
        "output_sha256": sha(path.parent / ("noun_types.jsonl" if data.get("kind") == "ntype"
                                              else "role_frames.jsonl")),
    }


def placement(path: Path, role_generation: str) -> dict:
    manifest_path = path / "manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        "path": str(path.relative_to(ROOT)),
        "source_role_generation": role_generation,
        "build_started_at_utc": data.get("build_started_at_utc"),
        "build_finished_at_utc": data.get("build_finished_at_utc"),
        "duration_sec": data.get("duration_sec"),
        "content_sha256": data.get("content_sha256"),
        "placement_file_sha256": sha(path / "placement.sqlite"),
        "manifest_file_sha256": sha(manifest_path),
        "config_role_frame_min_sources": data["config"].get("role_frame_min_sources"),
        "headwords": data["outputs"]["headwords"],
        "evidence": data["outputs"]["evidence_by_arm"],
        "role_frames": data.get("role_frames"),
        "generated_noun_types": data.get("generated_noun_types"),
    }


requested = len([line for line in (ROOT / "artifacts/w3-a6/current-r2/needs_role_v2.jsonl")
                 .read_text(encoding="utf-8").splitlines() if line.strip()])
frames_by_run = {}
accepted_frame_words = {}
for name, path in (("run1", R1), ("v2", R2)):
    con = sqlite3.connect(f"file:{path / 'placement.sqlite'}?mode=ro", uri=True)
    counts = {particle: 0 for particle in PARTICLES}
    encoded_frames = [row[0] for row in con.execute("SELECT frame FROM role_frames")]
    accepted_frame_words[name] = len(encoded_frames)
    for encoded in encoded_frames:
        frame = json.loads(encoded)
        for particle in PARTICLES:
            if frame.get(particle):
                counts[particle] += 1
    con.close()
    frames_by_run[name] = counts

claim_rates = {}
claim_rates_valid = {}
for particle in PARTICLES:
    r1_count, v2_count = frames_by_run["run1"][particle], frames_by_run["v2"][particle]
    r1_rate, v2_rate = 100 * r1_count / requested, 100 * v2_count / requested
    claim_rates[particle] = {
        "denominator_words": requested,
        "numerator_basis": "配置DBに採択された異なる述語語で、その助詞の申告が1件以上ある語数",
        "run1": {"claimed_words": r1_count, "rate_pct": round(r1_rate, 4)},
        "v2": {"claimed_words": v2_count, "rate_pct": round(v2_rate, 4)},
        "change_percentage_points": round(v2_rate - r1_rate, 4),
    }
    r1_valid, v2_valid = accepted_frame_words["run1"], accepted_frame_words["v2"]
    r1_valid_rate, v2_valid_rate = 100 * r1_count / r1_valid, 100 * v2_count / v2_valid
    claim_rates_valid[particle] = {
        "denominator_accepted_frame_words": {"run1": r1_valid, "v2": v2_valid},
        "numerator_basis": "有効回答枠で、その助詞の申告が1件以上ある異なる述語語数",
        "run1": {"claimed_words": r1_count, "rate_pct": round(r1_valid_rate, 4)},
        "v2": {"claimed_words": v2_count, "rate_pct": round(v2_valid_rate, 4)},
        "change_percentage_points": round(v2_valid_rate - r1_valid_rate, 4),
    }

summaries = {name: generation(path) for name, path in SUMMARIES.items()}
n4 = json.loads((ART / "n4_d9_run2_final.json").read_text(encoding="utf-8"))
manifest = {
    "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "ticket": "W3-a6 r9",
    "ledger_policy": "gen_role_v2 と gen_ntype は既存の統合JSONL・summaryのみ読取。台帳再実行・読取・変更なし。",
    "placement_run1": placement(R1, "gen_role"),
    "placement_run2": placement(R2, "gen_role_v2"),
    "generation": summaries,
    "claim_rate_denominators": {
        "requested_word_set": requested,
        "accepted_role_frame_words": accepted_frame_words,
        "reference_run1_rates_pct": {"で": 4.5, "へ": 2.1, "から": 5.0},
        "reference_source": "artifacts/w3-a6/current-r2/auditor_run1_rates.txt",
        "reference_matches_accepted_frame_denominator_after_rounding_1dp": {
            particle: round(claim_rates_valid[particle]["run1"]["rate_pct"], 1)
            == {"で": 4.5, "へ": 2.1, "から": 5.0}[particle]
            for particle in ("で", "へ", "から")
        },
    },
    "n4_d9": {
        "selected_role_frame_min_sources": n4["configured_role_frame_min_sources"],
        "n4_meets_threshold": n4["n4_meets_threshold"],
        "confirmed_role_rows_at_selected_threshold": n4["thresholds"][str(n4["configured_role_frame_min_sources"])]
        ["confirmed_role_rows"],
        "obvious_errors_at_selected_threshold": n4["thresholds"]
        [str(n4["configured_role_frame_min_sources"])]["confirmed_obvious_errors"],
        "visual_labels_are_gold": False,
        "n4_summary_sha256": sha(ART / "n4_d9_run2_final.json"),
        "visual_labels_sha256": sha(ART / "n4_visual_labels_run2.jsonl"),
    },
    "claim_rates_by_particle": claim_rates,
    "claim_rates_by_particle_valid_answers": claim_rates_valid,
    "measurements": {
        "n2_summary_sha256": sha(ART / "n2_run1_vs_run2_summary.json"),
        "n3_summary_sha256": sha(ART / "n3_summary_run2.json"),
        "n5_summary_sha256": sha(ART / "n5_summary_run2.json"),
        "run2_verify_sha256": sha(ART / "run2_verify.txt"),
    },
}
OUTPUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "manifest": str(OUTPUT),
    "manifest_sha256": sha(OUTPUT),
    "requested_role_words": requested,
    "run1_content_sha256": manifest["placement_run1"]["content_sha256"],
    "run2_content_sha256": manifest["placement_run2"]["content_sha256"],
    "accepted_frame_words": accepted_frame_words,
    "claim_rates_by_particle": claim_rates,
    "claim_rates_by_particle_valid_answers": claim_rates_valid,
}, ensure_ascii=False, indent=2))
