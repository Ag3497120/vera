#!/usr/bin/env python3
"""Measure registered W3-a7 r10 acceptance rows from r9/run2 and r10/run1."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

from verantyx import coarse_place as cp
import verantyx.coarse_types as ct

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/w3-a7/current-r3"
R9 = Path("/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2")
R10 = ROOT / "build/coarse-W3a/full/r10/run1"
R9_ART = ROOT / "artifacts/w3-a6/r9"
EXPECT = ROOT / "tests/coarse_place/data/w3a6_expect.json"
N4_SAMPLE = R9_ART / "n4_claims_run2_prefreeze.jsonl"
N4_OLD_LABELS = R9_ART / "n4_visual_labels_run2.jsonl"
N5_SEEDS = ROOT / "artifacts/w3-a6/n5_seed_words_prefreeze.jsonl"
PARTICLES = list(ct.CASE_PARTICLES_9)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                              for row in rows), encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def open_db(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path / 'placement.sqlite'}?mode=ro", uri=True)


def frame_and_evidence(con: sqlite3.Connection, word: str):
    got = con.execute("SELECT frame FROM role_frames WHERE word=?", (word,)).fetchone()
    frame = json.loads(got[0]) if got else None
    ev = con.execute("SELECT arm,src,type,n,base FROM evidence WHERE word=? ORDER BY arm,src,type", (word,)).fetchall()
    return frame, ev


def check_frame(frame, ev, config):
    return ct.role_frame_check(frame, ev, config) if frame is not None else None


def distribution_sources(frame, ev, config, particle):
    per_src = defaultdict(dict)
    base_by_src = {}
    for arm, src, typ, count, base in ev:
        if arm != "role_distribution":
            continue
        key = ct.arm_key(arm, src)
        per_src[key][typ] = count
        if base is not None:
            base_by_src[key] = base
    declared = (frame or {}).get(particle, [])
    results = []
    for key in sorted(per_src):
        analysis = ct.rd_analyze(per_src[key], config, base_by_src.get(key))
        significant_types = list(analysis["types"].get(particle, [])) if particle in analysis["sig"] else []
        votes = defaultdict(list)
        split = []
        undeclared = []
        for typ in significant_types:
            matching = [entry["role"] for entry in declared if typ in entry["types"]]
            if len(matching) == 1:
                votes[matching[0]].append(typ)
            elif len(matching) > 1:
                split.append({"type": typ, "roles": matching})
            else:
                undeclared.append(typ)
        results.append({
            "source": key,
            "has_significant_particle": particle in analysis["sig"],
            "significant_particles": list(analysis["sig"]),
            "significant_types_for_particle": significant_types,
            "votes_by_role": {role: sorted(types) for role, types in sorted(votes.items())},
            "split_types": split,
            "undeclared_types": undeclared,
        })
    return results


def causes_for_role(frame, check, sources, particle, role):
    causes = []
    if frame is None:
        return ["UNCLASSIFIED"]
    role_claims = [entry for entry in (frame.get(particle) or []) if entry["role"] == role]
    if not role_claims:
        causes.append("CLAIM_ABSENT")
    has_source_rows = bool(sources)
    has_sig_arm = any(src["has_significant_particle"] for src in sources)
    if not has_source_rows:
        causes.append("SOURCE_ABSENT")
    elif not has_sig_arm:
        causes.append("DISTRIBUTION_NO_ARM")
    confirmed = [entry for entry in ((check or {}).get("confirmed", {}).get(particle, []))
                 if entry["role"] == role]
    unconfirmed = [entry for entry in ((check or {}).get("unconfirmed", {}).get(particle, []))
                   if entry["role"] == role]
    if confirmed:
        causes.append("SUPPORTED")
    elif role_claims:
        if any(role in split["roles"] for source in sources for split in source["split_types"]):
            causes.append("TYPE_SPLIT")
        elif has_sig_arm:
            sig_types = {typ for source in sources for typ in source["significant_types_for_particle"]}
            claim_types = {typ for entry in role_claims for typ in entry["types"]}
            if not claim_types.intersection(sig_types):
                causes.append("NO_SHARED_TYPE")
            elif not unconfirmed:
                causes.append("UNCLASSIFIED")
            elif any(item.get("why") == "PARTLY_BACKED" for item in unconfirmed):
                causes.append("PARTLY_BACKED")
            else:
                causes.append("UNCLASSIFIED")
    return causes or ["UNCLASSIFIED"]


def role_record(placement: Path, con: sqlite3.Connection, config: dict,
                word: str, particle: str, role: str) -> dict:
    frame, ev = frame_and_evidence(con, word)
    checked = check_frame(frame, ev, config)
    answer = cp.query(word, placement=str(placement))
    entries = (frame or {}).get(particle, [])
    expected_claims = [entry for entry in entries if entry["role"] == role]
    confirmed = [entry for entry in ((checked or {}).get("confirmed", {}).get(particle, []))
                 if entry["role"] == role]
    unconfirmed = [entry for entry in ((checked or {}).get("unconfirmed", {}).get(particle, []))
                   if entry["role"] == role]
    sources = distribution_sources(frame, ev, config, particle)
    return {
        "frame_present": frame is not None,
        "claimed_roles_for_particle": entries,
        "expected_role_claimed": bool(expected_claims),
        "query_role_frame_status": answer.get("role_frame_status"),
        "confirmed_expected_role": confirmed,
        "unconfirmed_expected_role": unconfirmed,
        "causes": causes_for_role(frame, checked, sources, particle, role),
        "distribution_sources": sources,
    }


def projection(answer: dict) -> dict:
    return {key: answer.get(key) for key in ("namespace", "state", "origin", "top")}


def write_n2(expect: dict, con9, con10, config9: dict, config10: dict) -> None:
    rows = []
    for item in expect["roles"]:
        word, particle, role = item["pred"], item["particle"], item["role"]
        old = role_record(R9, con9, config9, word, particle, role)
        new = role_record(R10, con10, config10, word, particle, role)
        rows.append({"predicate": word, "particle": particle, "expected_role": role,
                     "r9_run2": old, "r10_run1": new,
                     "claim_changed": old["expected_role_claimed"] != new["expected_role_claimed"],
                     "confirmation_changed": bool(old["confirmed_expected_role"])
                     != bool(new["confirmed_expected_role"])})
    write_jsonl(OUT / "n2_r9_run2_vs_r10_run1.jsonl", rows)
    changed_claims = sum(row["claim_changed"] for row in rows)
    changed_confirmations = sum(row["confirmation_changed"] for row in rows)
    summary = {
        "expected_role_rows": len(rows),
        "expected_predicates": len({row["predicate"] for row in rows}),
        "r9_expected_roles_claimed": sum(row["r9_run2"]["expected_role_claimed"] for row in rows),
        "r10_expected_roles_claimed": sum(row["r10_run1"]["expected_role_claimed"] for row in rows),
        "r9_expected_roles_confirmed": sum(bool(row["r9_run2"]["confirmed_expected_role"]) for row in rows),
        "r10_expected_roles_confirmed": sum(bool(row["r10_run1"]["confirmed_expected_role"]) for row in rows),
        "claim_changed_rows": changed_claims,
        "confirmation_changed_rows": changed_confirmations,
        "r10_confirmed_roles_have_backing": all(
            bool(row["r10_run1"]["distribution_sources"])
            and all(item["backed_by"] for item in row["r10_run1"]["confirmed_expected_role"])
            for row in rows if row["r10_run1"]["confirmed_expected_role"]
        ),
        "r10_query_status_counts": dict(Counter(row["r10_run1"]["query_role_frame_status"] for row in rows)),
    }
    write_json(OUT / "n2_summary.json", summary)
    lines = ["|述語|助詞|期待役割|r9申告|r9確認|r10申告|r10確認|r10根拠腕|",
             "|---|---|---|---:|---|---:|---|---|"]
    for row in rows:
        old, new = row["r9_run2"], row["r10_run1"]
        backing = sorted({source for claim in new["confirmed_expected_role"]
                          for source in claim["backed_by"]})
        lines.append("|{predicate}|{particle}|{role}|{old_claim}|{old_conf}|{new_claim}|{new_conf}|{backing}|".format(
            predicate=row["predicate"], particle=row["particle"], role=row["expected_role"],
            old_claim="有" if old["expected_role_claimed"] else "無",
            old_conf="有" if old["confirmed_expected_role"] else "無",
            new_claim="有" if new["expected_role_claimed"] else "無",
            new_conf="有" if new["confirmed_expected_role"] else "無",
            backing=", ".join(backing) or "なし"))
    (OUT / "n2_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_n3_n5(expect: dict, con9, con10) -> None:
    relative = []
    for word in expect["relative_position"]:
        answer = cp.query(word, placement=str(R10))
        top = answer.get("top") or []
        lone = answer.get("state") == "DECIDED" and answer.get("origin") == "direct" and top == ["PLACE"]
        relative.append({"word": word, "state": answer.get("state"), "origin": answer.get("origin"),
                         "top": top, "lone_direct_place": lone})
    write_jsonl(OUT / "n3_relative_position_terms.jsonl", relative)
    write_json(OUT / "n3_summary.json", {
        "required_terms": len(relative),
        "lone_direct_place": sum(row["lone_direct_place"] for row in relative),
        "not_lone_direct_place": sum(not row["lone_direct_place"] for row in relative),
        "rows": relative,
    })

    seed_words = [row["word"] for row in read_jsonl(N5_SEEDS)]
    rows, diffs = [], []
    for word in seed_words:
        old = projection(cp.query(word, placement=str(R9)))
        new = projection(cp.query(word, placement=str(R10)))
        row = {"word": word, "r9_run2": old, "r10_run1": new, "same": old == new}
        rows.append(row)
        if not row["same"]:
            diffs.append(row)
    write_jsonl(OUT / "n5_seed_comparison_r9_run2_vs_r10_run1.jsonl", rows)
    write_jsonl(OUT / "n5_seed_differences.jsonl", diffs)
    write_json(OUT / "n5_summary.json", {
        "seed_words": len(seed_words), "same": len(rows) - len(diffs), "different": len(diffs),
        "different_rows": diffs,
    })


def source_causes_for_particle(frame, checked, sources, particle):
    causes = set()
    if frame is None:
        causes.add("UNCLASSIFIED")
    else:
        claims = frame.get(particle) or []
        if not claims:
            causes.add("CLAIM_ABSENT")
    if not sources:
        causes.add("SOURCE_ABSENT")
    elif not any(source["has_significant_particle"] for source in sources):
        causes.add("DISTRIBUTION_NO_ARM")
    for source in sources:
        if source["split_types"]:
            causes.add("TYPE_SPLIT")
    if checked and checked["confirmed"].get(particle):
        causes.add("SUPPORTED")
    claims = (frame or {}).get(particle, [])
    if claims and any(source["has_significant_particle"] for source in sources):
        significant = {typ for source in sources for typ in source["significant_types_for_particle"]}
        declared = {typ for claim in claims for typ in claim["types"]}
        if not significant.intersection(declared):
            causes.add("NO_SHARED_TYPE")
        unconfirmed = (checked or {}).get("unconfirmed", {}).get(particle, [])
        if any(item.get("why") == "PARTLY_BACKED" for item in unconfirmed):
            causes.add("PARTLY_BACKED")
    return sorted(causes or {"UNCLASSIFIED"})


def write_coverage(expect: dict, n4_sample: list[dict], con10, config10: dict) -> None:
    n2_rows = []
    for item in expect["roles"]:
        word, particle, role = item["pred"], item["particle"], item["role"]
        frame, ev = frame_and_evidence(con10, word)
        checked = check_frame(frame, ev, config10)
        sources = distribution_sources(frame, ev, config10, particle)
        n2_rows.append({"sample": "N2", "word": word, "particle": particle,
                        "expected_role": role, "frame_present": frame is not None,
                        "claims_for_particle": (frame or {}).get(particle, []),
                        "causes_for_expected_role": causes_for_role(frame, checked, sources, particle, role),
                        "distribution_sources": sources})
    write_jsonl(OUT / "coverage_n2_11_rows.jsonl", n2_rows)

    n4_rows = []
    for sample in n4_sample:
        word = sample["word"]
        frame, ev = frame_and_evidence(con10, word)
        checked = check_frame(frame, ev, config10)
        for particle in PARTICLES:
            sources = distribution_sources(frame, ev, config10, particle)
            n4_rows.append({"sample": "N4", "word": word, "particle": particle,
                            "frame_present": frame is not None,
                            "claims_for_particle": (frame or {}).get(particle, []),
                            "confirmed_for_particle": (checked or {}).get("confirmed", {}).get(particle, []),
                            "unconfirmed_for_particle": (checked or {}).get("unconfirmed", {}).get(particle, []),
                            "causes": source_causes_for_particle(frame, checked, sources, particle),
                            "distribution_sources": sources})
    write_jsonl(OUT / "coverage_n4_60x9.jsonl", n4_rows)
    counts = Counter(cause for row in n2_rows for cause in row["causes_for_expected_role"])
    counts.update(cause for row in n4_rows for cause in row["causes"])
    summary = {
        "n2_rows": len(n2_rows),
        "n4_word_particle_rows": len(n4_rows),
        "n4_sample_words": len(n4_sample),
        "particles_per_n4_word": len(PARTICLES),
        "cause_counts_nonexclusive": dict(sorted(counts.items())),
        "n2_r10_causes": dict(sorted(Counter(c for row in n2_rows for c in row["causes_for_expected_role"]).items())),
        "n4_causes": dict(sorted(Counter(c for row in n4_rows for c in row["causes"]).items())),
        "source_rows_are_not_combined": True,
    }
    write_json(OUT / "coverage_summary.json", summary)


def write_n4_claims(n4_sample: list[dict], con10, config10: dict) -> None:
    old_labels = {(row["word"], row["particle"], row["role"]): row
                  for row in read_jsonl(N4_OLD_LABELS)}
    words_out, claims_out, review_template = [], [], []
    for sample in n4_sample:
        word = sample["word"]
        frame, ev = frame_and_evidence(con10, word)
        checked = check_frame(frame, ev, config10)
        words_out.append({"word": word, "source_status": sample.get("source_status"),
                          "role_frame_present": frame is not None,
                          "frame": frame,
                          "confirmed": (checked or {}).get("confirmed", {}),
                          "unconfirmed": (checked or {}).get("unconfirmed", {})})
        for particle, entries in (frame or {}).items():
            confirmed_map = {entry["role"]: entry for entry in (checked or {}).get("confirmed", {}).get(particle, [])}
            unconfirmed_map = {entry["role"]: entry for entry in (checked or {}).get("unconfirmed", {}).get(particle, [])}
            sources = distribution_sources(frame, ev, config10, particle)
            for entry in entries:
                role = entry["role"]
                confirmed = confirmed_map.get(role)
                unconfirmed = unconfirmed_map.get(role)
                claim = {
                    "word": word, "particle": particle, "role": role, "types": entry["types"],
                    "confirmed": confirmed is not None,
                    "confirmed_types": confirmed["types"] if confirmed else [],
                    "backed_by": confirmed["backed_by"] if confirmed else [],
                    "unconfirmed_types": unconfirmed["types"] if unconfirmed else [],
                    "unconfirmed_why": unconfirmed["why"] if unconfirmed else None,
                    "distribution_sources": sources,
                    "evidence_type": "generated",
                }
                claims_out.append(claim)
                if confirmed:
                    old = old_labels.get((word, particle, role))
                    review_template.append({
                        "word": word, "particle": particle, "role": role,
                        "types": confirmed["types"], "backed_by": confirmed["backed_by"],
                        "previous_r9_label_reference_only": old.get("visual_label") if old else None,
                        "visual_label": "UNCLASSIFIED", "note": "未目視",
                        "evidence_type": "testimony", "reviewer": "Codex gpt-6-luna",
                    })
    write_jsonl(OUT / "n4_words_r10_v3.jsonl", words_out)
    write_jsonl(OUT / "n4_claims_v3_prefreeze.jsonl", claims_out)
    write_jsonl(OUT / "n4_visual_labels_v3_template.jsonl", review_template)
    write_json(OUT / "n4_claims_v3_prefreeze.sha256.json", {
        "path": "artifacts/w3-a7/current-r3/n4_claims_v3_prefreeze.jsonl",
        "sha256": sha(OUT / "n4_claims_v3_prefreeze.jsonl"),
        "rows": len(claims_out),
        "sample_words": len(n4_sample),
        "confirmed_roles_to_review": len(review_template),
        "visual_label_evidence_type": "testimony",
    })


def all_confirmed(placement: Path, config: dict):
    con = open_db(placement)
    ev_by_word = defaultdict(list)
    for row in con.execute("SELECT word,arm,src,type,n,base FROM evidence WHERE arm='role_distribution' ORDER BY word,src,type"):
        ev_by_word[row[0]].append(tuple(row[1:]))
    result = {}
    status_counts = Counter()
    for word, raw in con.execute("SELECT word,frame FROM role_frames ORDER BY word"):
        frame = json.loads(raw)
        check = ct.role_frame_check(frame, ev_by_word.get(word, []), config)
        status_counts[check["status"]] += 1
        for particle, roles in check["confirmed"].items():
            for role in roles:
                result[(word, particle, role["role"])] = {
                    "types": role["types"], "backed_by": role["backed_by"]}
    con.close()
    return result, status_counts


def write_all_diffs(con9, con10, config9: dict, config10: dict) -> None:
    def direct_map(con):
        return {(ns, word): {"namespace": ns, "word": word, "state": state,
                             "origin": origin, "top": top.split(",") if top else []}
                for ns, word, state, origin, top in con.execute(
                    "SELECT ns,word,state,origin,top FROM headwords") if origin == "direct"}
    old_direct, new_direct = direct_map(con9), direct_map(con10)
    direct_changes = []
    for key in sorted(set(old_direct) | set(new_direct)):
        old, new = old_direct.get(key), new_direct.get(key)
        if old != new:
            direct_changes.append({"namespace": key[0], "word": key[1],
                                   "before": old, "after": new})
    write_jsonl(OUT / "direct_changes_r9_run2_to_r10_run1.jsonl", direct_changes)
    old_confirmed, old_counts = all_confirmed(R9, config9)
    new_confirmed, new_counts = all_confirmed(R10, config10)
    role_changes = []
    for key in sorted(set(old_confirmed) | set(new_confirmed)):
        old, new = old_confirmed.get(key), new_confirmed.get(key)
        if old != new:
            role_changes.append({"word": key[0], "particle": key[1], "role": key[2],
                                 "change": "added" if old is None else "removed" if new is None else "changed",
                                 "before": old, "after": new})
    write_jsonl(OUT / "confirmed_role_changes_r9_run2_to_r10_run1.jsonl", role_changes)
    write_json(OUT / "all_diffs_summary.json", {
        "direct_rows_r9": len(old_direct), "direct_rows_r10": len(new_direct),
        "direct_changed_rows": len(direct_changes),
        "confirmed_role_rows_r9": len(old_confirmed), "confirmed_role_rows_r10": len(new_confirmed),
        "confirmed_role_added": sum(row["change"] == "added" for row in role_changes),
        "confirmed_role_removed": sum(row["change"] == "removed" for row in role_changes),
        "confirmed_role_changed": sum(row["change"] == "changed" for row in role_changes),
        "role_frame_word_status_r9": dict(old_counts), "role_frame_word_status_r10": dict(new_counts),
    })


def write_manifest_rates() -> None:
    base = read_json(R9_ART / "manifest.json")
    run9_manifest = read_json(R9 / "manifest.json")
    run10_manifest = read_json(R10 / "manifest.json")
    gen_v2 = base["generation"]["gen_role_v2"]
    gen_v3 = run10_manifest["role_frames"]["generation_summary"]
    con9, con10 = open_db(R9), open_db(R10)

    def accepted_rate_data(con):
        counts = Counter()
        words = 0
        for (raw,) in con.execute("SELECT frame FROM role_frames"):
            frame = json.loads(raw)
            words += 1
            for particle in PARTICLES:
                if frame.get(particle):
                    counts[particle] += 1
        return words, counts

    accepted9, counts9 = accepted_rate_data(con9)
    accepted10, counts10 = accepted_rate_data(con10)
    rates = {}
    for particle in PARTICLES:
        v2_accepted = base["claim_rates_by_particle_valid_answers"][particle]["v2"]["claimed_words"]
        v2_requested = base["claim_rates_by_particle"][particle]["v2"]["claimed_words"]
        v3_accepted = counts10[particle]
        rates[particle] = {
            "v2": {"requested_denominator": gen_v2["words_requested"],
                   "requested_numerator": v2_requested,
                   "requested_rate_pct": round(100 * v2_requested / gen_v2["words_requested"], 4),
                   "accepted_denominator": accepted9, "accepted_numerator": v2_accepted,
                   "accepted_rate_pct": round(100 * v2_accepted / accepted9, 4)},
            "v3": {"requested_denominator": gen_v3["words_requested"],
                   "requested_numerator": v3_accepted,
                   "requested_rate_pct": round(100 * v3_accepted / gen_v3["words_requested"], 4),
                   "accepted_denominator": accepted10, "accepted_numerator": v3_accepted,
                   "accepted_rate_pct": round(100 * v3_accepted / accepted10, 4)},
            "accepted_rate_change_percentage_points": round(
                100 * v3_accepted / accepted10 - 100 * v2_accepted / accepted9, 4),
        }
    con9.close()
    con10.close()
    result = {
        "evidence_type": "generated",
        "claim_rate_definition": "distinct accepted role-frame words with a nonempty typed claim for the particle",
        "requested_word_denominator": "all requested words; accepted-only numerator as in r9 manifest",
        "accepted_word_denominator": "distinct nonnull role-frame rows accepted by the builder",
        "v2_generation": gen_v2,
        "v3_generation": gen_v3,
        "r9_run2": {"content_sha256": run9_manifest["content_sha256"],
                    "manifest_sha256": sha(R9 / "manifest.json"),
                    "placement_sha256": sha(R9 / "placement.sqlite"),
                    "role_frame_rows": accepted9},
        "r10_run1": {"content_sha256": run10_manifest["content_sha256"],
                     "manifest_sha256": sha(R10 / "manifest.json"),
                     "placement_sha256": sha(R10 / "placement.sqlite"),
                     "role_frame_rows": accepted10},
        "effort_comparison": {"v2": gen_v2["effort"], "v3": gen_v3["effort"]},
        "claim_rates_by_particle": rates,
        "n4_visual_labels_are_gold": False,
        "role_generation_ledger_read": False,
    }
    write_json(OUT / "manifest_r10.json", result)
    lines = ["|助詞|v2 accepted|v3 accepted|差 (pp)|v2 requested|v3 requested|",
             "|---|---:|---:|---:|---:|---:|"]
    for particle in PARTICLES:
        row = rates[particle]
        lines.append("|{p}|{v2:.4f}% ({n2}/{d2})|{v3:.4f}% ({n3}/{d3})|{delta:+.4f}|{vr2:.4f}%|{vr3:.4f}%|".format(
            p=particle, v2=row["v2"]["accepted_rate_pct"], n2=row["v2"]["accepted_numerator"],
            d2=row["v2"]["accepted_denominator"], v3=row["v3"]["accepted_rate_pct"],
            n3=row["v3"]["accepted_numerator"], d3=row["v3"]["accepted_denominator"],
            delta=row["accepted_rate_change_percentage_points"],
            vr2=row["v2"]["requested_rate_pct"], vr3=row["v3"]["requested_rate_pct"]))
    (OUT / "claim_rate_comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    expect = read_json(EXPECT)
    n4_sample = read_jsonl(N4_SAMPLE)
    manifest9 = read_json(R9 / "manifest.json")
    manifest10 = read_json(R10 / "manifest.json")
    con9, con10 = open_db(R9), open_db(R10)
    try:
        write_n2(expect, con9, con10, manifest9["config"], manifest10["config"])
        write_n3_n5(expect, con9, con10)
        write_coverage(expect, n4_sample, con10, manifest10["config"])
        write_n4_claims(n4_sample, con10, manifest10["config"])
        write_all_diffs(con9, con10, manifest9["config"], manifest10["config"])
        write_manifest_rates()
    finally:
        con9.close()
        con10.close()
    print(json.dumps({
        "n2_rows": len(expect["roles"]),
        "n3_terms": len(expect["relative_position"]),
        "n4_words": len(n4_sample),
        "n5_words": len(read_jsonl(N5_SEEDS)),
        "output": str(OUT),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
