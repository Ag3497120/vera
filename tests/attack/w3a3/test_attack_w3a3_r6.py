# W5-d: copied from attacks/W3-a3/test_attack_w3a3.py; revised in W5-d2 (auditor's ruling B1 2026-10-04 00:05): test_all_r6_generated_frame_upgrades; revised in W5-e2 (auditor's ruling K-A4 2026-10-04 04:42): test_all_r6_generated_frame_upgrades again
"""Read-only attacks against the registered W3-a3 r6 placement."""
import json
from pathlib import Path

from verantyx import coarse_place as cp
from verantyx import coarse_types as ct


PLACEMENT = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r6/run1"
OUT = Path(__file__).parent


def _json_bytes(value):
    return json.dumps(value, ensure_ascii=False, indent=1).encode("utf-8")


def test_all_r6_generated_frame_upgrades():
    # W5-d2 (auditor's ruling B1, K5): the invariants follow the rule of W5-d (docs/COARSE_PLACEMENT.md section 13): a predicate that a generated frame placed direct
    # is CONFIRMED only when no particle of the frame contradicts the distribution that backed it; a contradicted one is NOT_CONFIRMED (frame null, the contradiction
    # in frame_disagreement). The derivation of the 48 words, the byte identity of two queries, state/origin/generated_frame/namespace/top, the type of the
    # generated frame, and the verdict of every distribution arm are as they were; the number of NOT_CONFIRMED words is not asserted (it is written to the summary).
    pl, why = cp._open(PLACEMENT)
    assert pl is not None, why
    rows = pl.con.execute(
        "SELECT word FROM headwords WHERE origin='direct' AND by LIKE '%gen_frame%' ORDER BY word"
    ).fetchall()
    words = [row[0] for row in rows]
    assert len(words) == 48

    results, frame_conflicts, invariant_errors, byte_diffs, not_confirmed = [], [], [], [], []
    for word in words:
        answer = cp.query(word, placement=PLACEMENT)
        again = cp.query(word, placement=PLACEMENT)
        if _json_bytes(answer) != _json_bytes(again):
            byte_diffs.append(word)
        results.append(answer)

        if not (answer["state"] == "DECIDED" and answer["origin"] == "direct"
                and answer.get("generated_frame") is True
                and answer["frame_status"] in ("CONFIRMED", "NOT_CONFIRMED")
                and answer["namespace"] == "P" and answer["top"]):
            invariant_errors.append({"word": word, "answer": answer})
            continue

        gf = pl.generated_frame(word)
        generated = gf[5] if gf else {}
        if not gf or gf[4] != answer["top"][0]:
            invariant_errors.append({"word": word, "reason": "generated_type_differs",
                                     "generated_type": gf[4] if gf else None,
                                     "answer_top": answer["top"]})
        sig_particles, typed_sig = set(), []
        for key, arm in answer["axes"].items():
            if not key.startswith("role_distribution@") or not arm["met"]:
                continue
            raw = [r for r in pl.evidence(word)
                   if r[0] == "role_distribution" and key.endswith("@" + r[1])]
            counts = {r[2]: r[3] for r in raw}
            base = raw[0][4] if raw else None
            analysis = ct.rd_analyze(counts, pl.cfg, base)
            sig_particles.update(analysis["sig"])
            typed_sig.append((key, analysis["types"]))
            if ct.arm_verdict("role_distribution", counts, pl.cfg, base) != answer["top"]:
                invariant_errors.append({"word": word, "arm": key, "reason": "arm_top_differs"})

        if answer["frame_status"] == "NOT_CONFIRMED":
            not_confirmed.append(word)
            disagreement = answer.get("frame_disagreement")
            if answer["frame"] is not None or "frame_unconfirmed" in answer \
                    or not isinstance(disagreement, dict) or not disagreement:
                invariant_errors.append({"word": word, "reason": "not_confirmed_shape", "frame": answer["frame"],
                                         "frame_disagreement": disagreement,
                                         "has_frame_unconfirmed": "frame_unconfirmed" in answer})
                continue
            for particle, entry in disagreement.items():
                gen_types = set(entry.get("generated") or [])
                arms = entry.get("distribution") or {}
                if not gen_types or not arms or any(gen_types & set(dt) for dt in arms.values()):
                    invariant_errors.append({"word": word, "reason": "disagreement_types_meet",
                                             "particle": particle, "entry": entry})
            continue

        # W5-e2 (auditor's ruling K-A4, 2026-10-04 04:42): the frame keeps the generated types the distribution backs (generated frame ∩ the UNION over the deciding
        # distribution arms of the significant types, ct.rd_analyze: the rule of the decision itself, NOT cp.frame_backing); the generated types it does not back, and every
        # generated particle outside the significant ones, are in frame_unconfirmed
        backing = {}
        for _key, by_particle in typed_sig:
            for particle, dist_types in by_particle.items():
                backing.setdefault(particle, set()).update(dist_types)
        expected = {p: sorted(set(generated[p]) & backing.get(p, set())) for p in ct.ROLE_PARTICLES
                    if p in sig_particles and generated.get(p) and set(generated[p]) & backing.get(p, set())}
        expected_unconfirmed = {p: sorted(set(generated[p]) - (backing.get(p, set()) if p in sig_particles else set()))
                                for p in ct.ROLE_PARTICLES
                                if generated.get(p) and set(generated[p]) - (backing.get(p, set()) if p in sig_particles else set())}
        if answer["frame"] != expected or answer.get("frame_unconfirmed") != expected_unconfirmed:
            invariant_errors.append({"word": word, "reason": "frame_projection_differs",
                                     "expected": expected, "got": answer["frame"],
                                     "expected_unconfirmed": expected_unconfirmed, "got_unconfirmed": answer.get("frame_unconfirmed")})

        for key, by_particle in typed_sig:
            for particle, dist_types in by_particle.items():
                if not dist_types:
                    continue
                frame_types = set(answer["frame"].get(particle, []))
                if not frame_types or not frame_types.intersection(dist_types):
                    frame_conflicts.append({"word": word, "source": key, "particle": particle,
                                            "distribution_types": dist_types,
                                            "confirmed_frame_types": sorted(frame_types)})

    (OUT / "r6_48_queries.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False, separators=(",", ":")) + "\n" for x in results),
        encoding="utf-8")
    summary = {"derived_words": len(words), "queried": len(results),
               "byte_differences": byte_diffs, "invariant_errors": invariant_errors,
               "disjoint_slot_conflicts": frame_conflicts, "not_confirmed": not_confirmed}
    (OUT / "r6_audit_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    assert not byte_diffs
    assert not invariant_errors
    assert not frame_conflicts, "confirmed frame slot types contradict significant distribution types"


def test_time_inflection_compound_and_sahen_probes():
    probes = ["昨日", "来週", "毎朝", "歌う", "歌った", "歌わない", "歌い",
              "読み上げる", "読み上げた", "読み上げ", "連絡", "連絡する"]
    answers = [cp.query(term, placement=PLACEMENT) for term in probes]
    rows = [{"term": a["term"], "state": a["state"], "origin": a["origin"],
             "estimate_basis": a["estimate_basis"], "top": a["top"],
             "frame_status": a["frame_status"], "seen_in_material": a["seen_in_material"]}
            for a in answers]
    (OUT / "state_probes.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    assert all(a["frame_status"] in cp._FRAME_STATUS_VALUES
               if hasattr(cp, "_FRAME_STATUS_VALUES") else a["frame_status"] in {
                   "CONFIRMED", "NOT_CONFIRMED", "ESTIMATED", "NOT_PREDICATE",
                   "NO_ANSWER", "NO_PLACEMENT", "NO_FRAME_TABLE"} for a in answers)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
